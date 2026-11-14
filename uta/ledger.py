"""In-memory, per-asset double-entry journal for deterministic simulations.

All signed postings in a journal event must sum to zero *for each asset*.
Amounts are stored as integer minor units, not rounded Decimal arithmetic.
This is an educational ledger, not durable storage or an exchange settlement
system. Negative balances are permitted: credit and risk policy are separate.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from threading import RLock
from types import MappingProxyType
from typing import Mapping, Sequence


class LedgerError(ValueError):
    """Journal event is invalid or conflicts with a previous event."""


@dataclass(frozen=True)
class Posting:
    account: str
    asset: str
    amount: Decimal  # Positive credits this named internal account.


@dataclass(frozen=True)
class JournalEvent:
    event_id: str
    sequence: int
    postings: tuple[Posting, ...]


class Ledger:
    """A process-local journal with atomic validation and idempotent event IDs.

    Scales give each asset's number of fractional decimal places. The signed
    convention is algebraic: a transfer credits one account and debits another.
    It is not a substitute for an accounting chart or external reconciliation.
    """

    def __init__(self, scales: Mapping[str, int], *, unit_digits: int = 38):
        if not scales:
            raise LedgerError("at least one asset scale is required")
        if any(not isinstance(asset, str) or not asset.strip()
               or type(scale) is not int or not 0 <= scale <= 18
               for asset, scale in scales.items()):
            raise LedgerError("asset scales require a name and integer scale 0..18")
        if type(unit_digits) is not int or not 38 <= unit_digits <= 60:
            raise LedgerError("journal unit digits must be between 38 and 60")
        self._unit_digits = unit_digits
        self._limit = 10 ** unit_digits
        self._scales = MappingProxyType(dict(scales))
        self._balances: dict[tuple[str, str], int] = {}
        self._events: list[JournalEvent] = []
        self._by_id: dict[str, tuple[tuple[tuple[str, str, int], ...], JournalEvent]] = {}
        self._lock = RLock()

    def _units(self, asset: str, amount: Decimal) -> int:
        if asset not in self._scales:
            raise LedgerError(f"unknown asset: {asset}")
        if not isinstance(amount, Decimal) or not amount.is_finite():
            raise LedgerError("amount must be a finite Decimal")
        parts = amount.as_tuple()
        if len(parts.digits) > self._unit_digits or not -38 <= parts.exponent <= 38:
            raise LedgerError("amount exceeds supported precision")
        coefficient = int(''.join(str(d) for d in parts.digits))
        shift = parts.exponent + self._scales[asset]
        if shift >= 0:
            units = coefficient * 10 ** shift
        else:
            divisor = 10 ** -shift
            units, remainder = divmod(coefficient, divisor)
            if remainder:
                raise LedgerError(f"amount exceeds {asset} scale")
        if units >= self._limit:
            raise LedgerError("amount exceeds supported range")
        return -units if parts.sign else units

    def _amount(self, asset: str, units: int) -> Decimal:
        # Decimal tuple construction is exact even if the global context is small.
        digits = tuple(int(ch) for ch in str(abs(units)))
        return Decimal((int(units < 0), digits, -self._scales[asset]))

    def post(self, event_id: str, postings: Sequence[Posting]) -> JournalEvent:
        if not isinstance(event_id, str) or not event_id.strip():
            raise LedgerError("event_id is required")
        if not isinstance(postings, (list, tuple)) or len(postings) < 2:
            raise LedgerError("at least two postings are required")
        normalized = []
        for posting in postings:
            if not isinstance(posting, Posting) or not isinstance(posting.account, str) or not posting.account.strip():
                raise LedgerError("each posting requires an account")
            if not isinstance(posting.asset, str):
                raise LedgerError("asset must be a string")
            units = self._units(posting.asset, posting.amount)
            if not units:
                raise LedgerError("zero postings are not allowed")
            normalized.append((posting.account, posting.asset, units))
        canonical = tuple(sorted(normalized))
        totals: dict[str, int] = {}
        deltas: dict[tuple[str, str], int] = {}
        for account, asset, units in canonical:
            totals[asset] = totals.get(asset, 0) + units
            key = (account, asset)
            deltas[key] = deltas.get(key, 0) + units
        if any(totals.values()):
            raise LedgerError("event must balance independently for every asset")
        with self._lock:
            existing = self._by_id.get(event_id)
            if existing is not None:
                if existing[0] != canonical:
                    raise LedgerError("event ID reused with different postings")
                return existing[1]
            changes = {key: self._balances.get(key, 0) + delta
                       for key, delta in deltas.items()}
            if any(abs(value) >= self._limit for value in changes.values()):
                raise LedgerError("balance exceeds supported range")
            event = JournalEvent(event_id, len(self._events) + 1, tuple(
                Posting(account, asset, self._amount(asset, units))
                for account, asset, units in canonical))
            # Validation completes before any mutation, including deduplication.
            self._balances.update(changes)
            self._events.append(event)
            self._by_id[event_id] = (canonical, event)
            return event

    def balance(self, account: str, asset: str) -> Decimal:
        if asset not in self._scales:
            raise LedgerError(f"unknown asset: {asset}")
        with self._lock:
            return self._amount(asset, self._balances.get((account, asset), 0))

    def journal(self) -> tuple[JournalEvent, ...]:
        with self._lock:
            return tuple(self._events)

    @classmethod
    def replay(cls, scales: Mapping[str, int], events: Sequence[JournalEvent]) -> Ledger:
        result = cls(scales)
        for expected, event in enumerate(events, 1):
            if not isinstance(event, JournalEvent) or event.sequence != expected:
                raise LedgerError("journal sequence is missing or out of order")
            posted = result.post(event.event_id, event.postings)
            if posted.sequence != expected:
                raise LedgerError("duplicate event in journal")
        return result
