"""Bounded, process-local decoding of immutable persisted market snapshots.

The cache key is the complete, unmodified payload string read by the caller's
current SQLite transaction. No version-only, database-global, freshness, policy,
or authorization result is cached. A hit replaces only ``from_json``; callers
must still fetch the row and validate its clock and policy on every use.
"""
from __future__ import annotations

from collections import OrderedDict
from threading import RLock

from .market import MAX_JSON_BYTES, MarketSnapshot


MAX_CACHE_CAPACITY = 64


class MarketDecodeCache:
    """Thread-safe LRU of successfully decoded, deeply immutable snapshots.

    Capacity defaults to zero: the reference decoder runs for every request.
    An enabled instance retains at most ``capacity`` payload/model pairs; each
    payload is limited by the decoder to 1 MiB of UTF-8. Parsed model objects and
    Python container overhead are additional memory, not a hard RSS budget.
    Construct one instance per service; there is no module or class-wide cache.

    The lock also covers decoding on a miss. Concurrent readers of the same
    cold payload therefore perform one successful decode. A failed decode
    never inserts or evicts an entry, and its original exception propagates.
    """

    def __init__(self, capacity: int = 0):
        if type(capacity) is not int or not 0 <= capacity <= MAX_CACHE_CAPACITY:
            raise ValueError(f"market cache capacity must be an integer in 0..{MAX_CACHE_CAPACITY}")
        self._capacity = capacity
        self._entries: OrderedDict[str, MarketSnapshot] = OrderedDict()
        self._lock = RLock()
        self._hits = self._misses = self._errors = self._evictions = 0

    @property
    def capacity(self) -> int:
        return self._capacity

    def parse(self, payload: str) -> MarketSnapshot:
        """Decode the actual row payload; do not substitute a version or digest.

        Successful plain-string inputs can enter the LRU. Other input types
        are passed to the reference decoder so malformed, even unhashable,
        inputs retain its rejection behavior. String subclasses bypass the
        LRU so custom hashing/equality cannot alter cache identity.
        """
        with self._lock:
            cacheable = (self._capacity > 0 and type(payload) is str
                         and len(payload) <= MAX_JSON_BYTES)
            if cacheable:
                cached = self._entries.get(payload)
                if cached is not None:
                    self._entries.move_to_end(payload)
                    self._hits += 1
                    return cached
            self._misses += 1
            try:
                snapshot = MarketSnapshot.from_json(payload)
            except Exception:
                self._errors += 1
                raise
            if cacheable:
                self._entries[payload] = snapshot
                if len(self._entries) > self._capacity:
                    self._entries.popitem(last=False)
                    self._evictions += 1
            return snapshot

    def stats(self) -> dict[str, int]:
        """Return detached counters; misses include failed and disabled decodes."""
        with self._lock:
            return {"capacity": self._capacity, "size": len(self._entries),
                    "hits": self._hits, "misses": self._misses,
                    "errors": self._errors, "evictions": self._evictions}

    def clear(self, *, reset_stats: bool = False) -> None:
        """Clear entries, optionally counters, atomically with concurrent parses."""
        if type(reset_stats) is not bool:
            raise ValueError("reset_stats must be a boolean")
        with self._lock:
            self._entries.clear()
            if reset_stats:
                self._hits = self._misses = self._errors = self._evictions = 0
