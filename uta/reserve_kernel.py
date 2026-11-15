"""Bounded memoization of exact, account-independent order reserve arithmetic.

This module has no database, account, product-admission or market-age authority.
Callers must resolve and validate current products and market data on every call.
"""
from collections import OrderedDict
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from threading import Lock


MAX_CAPACITY = 65536


@dataclass(frozen=True, slots=True)
class ReserveInputs:
    """Complete economic inputs; quantity minus filled is evaluated exactly.

    Keeping both quantities in the key avoids ambient Decimal-context rounding.
    Identifiers, versions and balances are deliberately not cache keys.
    """

    quantity: Decimal
    filled_quantity: Decimal
    limit_price: Decimal
    mark_price: Decimal
    reduce_only: bool
    initial_margin_rate: Decimal
    fee_notional: Decimal
    charged_fee: Decimal
    fee_rate: Decimal
    usd_scale: int


def _decimal(value: Fraction) -> Decimal:
    """Build a terminating Decimal without consulting the ambient context."""
    denominator, twos, fives = value.denominator, 0, 0
    while denominator % 2 == 0:
        denominator //= 2
        twos += 1
    while denominator % 5 == 0:
        denominator //= 5
        fives += 1
    if denominator != 1:
        raise ValueError("reserve is not a terminating decimal")
    scale = max(twos, fives)
    coefficient = value.numerator * 2 ** (scale - twos) * 5 ** (scale - fives)
    return Decimal((int(coefficient < 0), tuple(map(int, str(abs(coefficient)))), -scale))


def calculate_reserve(inputs: ReserveInputs) -> Decimal:
    """Exact IM + adverse execution loss + unpaid cumulative fee ceiling.

    The service's original Fraction expression remains available independently
    when reserve_cache_size=0. This function only evaluates the supplied values.
    """
    remaining = Fraction(inputs.quantity) - Fraction(inputs.filled_quantity)
    mark, limit = Fraction(inputs.mark_price), Fraction(inputs.limit_price)
    loss = max(Fraction(0), remaining * (limit - mark))
    im = (Fraction(0) if inputs.reduce_only else
          abs(remaining) * max(mark, limit) * Fraction(inputs.initial_margin_rate))
    scale = 10 ** inputs.usd_scale
    fee_units = ((Fraction(inputs.fee_notional) + abs(remaining) * limit)
                 * Fraction(inputs.fee_rate) * scale)
    ceiling_units = -(-fee_units.numerator // fee_units.denominator)
    fee = Fraction(ceiling_units, scale) - Fraction(inputs.charged_fee)
    return _decimal(im + loss + fee)


class ReserveKernel:
    """Per-instance, thread-safe LRU of immutable pure-arithmetic results.

    Cold calculations run outside the lock. Concurrent misses may compute the
    same result twice, but entries and counters remain bounded and consistent.
    A clear may be followed by an already-running pure calculation repopulating
    the cache. Neither eviction nor clearing affects any authoritative state.
    """

    def __init__(self, capacity: int = 4096):
        if type(capacity) is not int or not 0 <= capacity <= MAX_CAPACITY:
            raise ValueError(f"reserve cache capacity must be an integer from 0 through {MAX_CAPACITY}")
        self._capacity = capacity
        self._entries: OrderedDict[ReserveInputs, Decimal] = OrderedDict()
        self._lock = Lock()
        self._hits = self._misses = self._evictions = 0

    @property
    def capacity(self) -> int:
        return self._capacity

    def calculate(self, inputs: ReserveInputs) -> Decimal:
        if not isinstance(inputs, ReserveInputs):
            raise TypeError("reserve calculation requires ReserveInputs")
        with self._lock:
            if self._capacity and inputs in self._entries:
                self._hits += 1
                self._entries.move_to_end(inputs)
                return self._entries[inputs]
            self._misses += 1
        result = calculate_reserve(inputs)
        if self._capacity:
            with self._lock:
                self._entries[inputs] = result
                self._entries.move_to_end(inputs)
                if len(self._entries) > self._capacity:
                    self._entries.popitem(last=False)
                    self._evictions += 1
        return result

    def stats(self) -> dict:
        """Process-local diagnostics, never financial or admission receipts."""
        with self._lock:
            return {"capacity": self._capacity, "size": len(self._entries),
                    "hits": self._hits, "misses": self._misses,
                    "evictions": self._evictions}

    def clear(self, *, reset_stats: bool = False) -> None:
        if type(reset_stats) is not bool:
            raise TypeError("reset_stats must be a bool")
        with self._lock:
            self._entries.clear()
            if reset_stats:
                self._hits = self._misses = self._evictions = 0
