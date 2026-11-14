"""Thread-safe in-memory margin reservations, for a single process only.

The caller supplies an account-level risk capacity *before* order reservations,
from a fresh, consistent risk snapshot. All amounts use one reporting currency.
This class does not fetch prices, prove freshness, integrate an order gateway,
persist data, fence multiple processes, or coordinate with fills or liquidations.
Never use it as a production risk gate.
"""
from dataclasses import dataclass
from decimal import Decimal, localcontext
from threading import RLock


class ReservationError(ValueError):
    pass


class VersionConflict(ReservationError):
    pass


class InsufficientMargin(ReservationError):
    pass


class IdempotencyConflict(ReservationError):
    pass


def _amount(value: Decimal, *, positive: bool = False) -> None:
    # Explicit bounds keep exact decimal arithmetic within the local precision.
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ReservationError("amount must be a finite Decimal")
    if (not -18 <= value.as_tuple().exponent <= 18
            or (value != 0 and value.adjusted() >= 18)):
        raise ReservationError("amount exceeds supported 18 integer / 18 fractional digits")
    if positive and value <= 0:
        raise ReservationError("reservation amount must be positive")


def _id(value: str) -> None:
    if not isinstance(value, str) or not value or len(value) > 128:
        raise ReservationError("reservation ID must be a non-empty string of at most 128 characters")


def _version(value: int) -> None:
    if type(value) is not int or value < 0:
        raise ReservationError("version must be a non-negative integer")


@dataclass(frozen=True)
class Reservation:
    reservation_id: str
    amount: Decimal
    active: bool


@dataclass(frozen=True)
class BookSnapshot:
    version: int
    capacity: Decimal
    reserved: Decimal
    available: Decimal


class ReservationBook:
    """One account's reservation book. All public methods hold one process lock.

    Capacity can be updated downward below outstanding reserves: available then
    becomes negative and additional reservations fail. This book never mutates
    on rejected requests. IDs are retained after release, so replay cannot
    accidentally reopen an old order. A restart loses all state and all IDs.
    """

    def __init__(self, capacity: Decimal):
        _amount(capacity)
        self._capacity = capacity
        self._reserved = Decimal(0)
        self._version = 0
        self._entries: dict[str, Reservation] = {}
        self._lock = RLock()

    def _check_version(self, expected_version: int) -> None:
        _version(expected_version)
        if expected_version != self._version:
            raise VersionConflict(f"expected version {expected_version}, current {self._version}")

    def snapshot(self) -> BookSnapshot:
        with self._lock, localcontext() as ctx:
            ctx.prec = 80
            return BookSnapshot(self._version, self._capacity, self._reserved,
                                self._capacity - self._reserved)

    def update_capacity(self, capacity: Decimal, *, expected_version: int) -> BookSnapshot:
        """Publish a caller-validated account risk capacity; may become negative."""
        _amount(capacity)
        with self._lock:
            self._check_version(expected_version)
            self._capacity = capacity
            self._version += 1
            return self.snapshot()

    def reserve(self, reservation_id: str, amount: Decimal, *, expected_version: int) -> Reservation:
        """Atomically reserve funds, or replay the same ID and amount.

        Replays return the current reservation state, even if the expected
        version is stale. A released ID stays released and cannot be reused.
        """
        _id(reservation_id)
        _amount(amount, positive=True)
        _version(expected_version)
        with self._lock, localcontext() as ctx:
            ctx.prec = 80
            existing = self._entries.get(reservation_id)
            if existing is not None:
                if existing.amount != amount:
                    raise IdempotencyConflict("reservation ID already used with another amount")
                return existing
            self._check_version(expected_version)
            if amount > self._capacity - self._reserved:
                raise InsufficientMargin("insufficient available margin")
            item = Reservation(reservation_id, amount, True)
            self._entries[reservation_id] = item
            self._reserved += amount
            self._version += 1
            return item

    def release(self, reservation_id: str, *, expected_version: int) -> Reservation:
        """Release an entire reservation once; repeated releases are no-ops."""
        _id(reservation_id)
        _version(expected_version)
        with self._lock, localcontext() as ctx:
            ctx.prec = 80
            existing = self._entries.get(reservation_id)
            if existing is None:
                raise ReservationError("unknown reservation")
            if not existing.active:
                return existing
            self._check_version(expected_version)
            item = Reservation(existing.reservation_id, existing.amount, False)
            self._entries[reservation_id] = item
            self._reserved -= existing.amount
            self._version += 1
            return item
