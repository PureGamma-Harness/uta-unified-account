from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import json
import sqlite3
from threading import Barrier
import unittest
from unittest.mock import patch

from uta.market import MAX_JSON_BYTES, MarketSnapshot
from uta.market_cache import MAX_CACHE_CAPACITY, MarketDecodeCache
from uta.models import AssetSpec, InstrumentSpec, RiskInputError


class MarketDecodeCacheTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 15, 10, tzinfo=timezone.utc)

    def payload(self, *, version=7, mark="100"):
        return MarketSnapshot(version, self.now,
                              {"USD": AssetSpec(D("1"), D("1"))},
                              {"X": InstrumentSpec(D(mark), D("0.1"), D("0.05"))}).to_json()

    def test_default_zero_runs_reference_parser_every_time(self):
        cache = MarketDecodeCache()
        payload = self.payload()
        with patch.object(MarketSnapshot, "from_json", wraps=MarketSnapshot.from_json) as parser:
            first = cache.parse(payload)
            second = cache.parse(payload)
        self.assertEqual(first, second)
        self.assertIsNot(first, second)
        self.assertEqual(parser.call_count, 2)
        self.assertEqual(cache.stats(), {"capacity": 0, "size": 0, "hits": 0, "misses": 2, "errors": 0, "evictions": 0})

    def test_enabled_exact_payload_reuses_only_successful_decode(self):
        cache = MarketDecodeCache(4)
        payload = self.payload()
        with patch.object(MarketSnapshot, "from_json", wraps=MarketSnapshot.from_json) as parser:
            first = cache.parse(payload)
            self.assertIs(cache.parse(payload), first)
            # Equal JSON values in different persisted strings are separate
            # keys: the cache does not silently normalize database content.
            other_spelling = json.dumps(json.loads(payload), indent=1)
            second = cache.parse(other_spelling)
        self.assertEqual(first, second)
        self.assertIsNot(first, second)
        self.assertEqual(parser.call_args_list[0].args, (payload,))
        self.assertEqual(parser.call_args_list[1].args, (other_spelling,))
        self.assertEqual(cache.stats(), {"capacity": 4, "size": 2, "hits": 1, "misses": 2, "errors": 0, "evictions": 0})

    def test_actual_sqlite_payload_changes_with_same_version_do_not_reuse_price(self):
        connection = sqlite3.connect(":memory:")
        self.addCleanup(connection.close)
        connection.execute("CREATE TABLE uta_market(singleton INTEGER PRIMARY KEY,payload TEXT)")
        first_payload = self.payload(mark="100")
        connection.execute("INSERT INTO uta_market VALUES (1,?)", (first_payload,))
        cache = MarketDecodeCache(4)
        first = cache.parse(connection.execute("SELECT payload FROM uta_market WHERE singleton=1").fetchone()[0])
        connection.execute("UPDATE uta_market SET payload=? WHERE singleton=1", (self.payload(mark="250"),))
        second = cache.parse(connection.execute("SELECT payload FROM uta_market WHERE singleton=1").fetchone()[0])
        self.assertEqual((first.version, second.version), (7, 7))
        self.assertEqual((first.instruments["X"].mark_price, second.instruments["X"].mark_price), (D("100"), D("250")))
        corrupted = json.loads(first_payload)
        corrupted["instruments"]["X"]["mark_price"] = "NaN"
        connection.execute("UPDATE uta_market SET payload=? WHERE singleton=1", (json.dumps(corrupted),))
        for _ in range(2):
            payload = connection.execute("SELECT payload FROM uta_market WHERE singleton=1").fetchone()[0]
            with self.assertRaises(RiskInputError):
                cache.parse(payload)
        self.assertEqual(cache.stats()["size"], 2)
        self.assertEqual(cache.stats()["errors"], 2)
        self.assertEqual(cache.stats()["hits"], 0)

    def test_lru_hit_changes_eviction_order_and_failed_decode_does_not_evict(self):
        cache = MarketDecodeCache(2)
        a, b, c = (self.payload(version=version) for version in (1, 2, 3))
        first_a = cache.parse(a)
        first_b = cache.parse(b)
        self.assertIs(cache.parse(a), first_a)  # B is now least recently used.
        with self.assertRaises(RiskInputError):
            cache.parse("{")
        cache.parse(c)
        self.assertEqual(cache.stats()["evictions"], 1)
        self.assertIs(cache.parse(a), first_a)
        replacement_b = cache.parse(b)
        self.assertEqual(replacement_b, first_b)
        self.assertIsNot(replacement_b, first_b)
        self.assertEqual(cache.stats()["size"], 2)
        self.assertEqual(cache.stats()["evictions"], 2)

    def test_maps_and_nested_financial_specs_remain_immutable_after_hit(self):
        cache = MarketDecodeCache(4)
        payload = self.payload()
        snapshot = cache.parse(payload)
        with self.assertRaises(TypeError):
            snapshot.assets["USD"] = AssetSpec(D("2"), D("1"))
        with self.assertRaises(TypeError):
            snapshot.instruments["X"] = InstrumentSpec(D("1"), D("0.1"), D("0.05"))
        with self.assertRaises(FrozenInstanceError):
            snapshot.assets["USD"].price = D("2")
        with self.assertRaises(FrozenInstanceError):
            snapshot.instruments["X"].mark_price = D("1")
        with self.assertRaises(FrozenInstanceError):
            snapshot.version = 999
        self.assertIs(cache.parse(payload), snapshot)
        self.assertEqual(snapshot.instruments["X"].mark_price, D("100"))

    def test_caching_a_parse_never_caches_freshness_or_future_clock_decision(self):
        cache = MarketDecodeCache(4)
        payload = self.payload()
        cache.parse(payload).validate(now=self.now)
        # A warm decode is still subjected to the caller's current clock on
        # every use, including a clock which moved backward.
        with self.assertRaisesRegex(RiskInputError, "stale"):
            cache.parse(payload).validate(now=self.now + timedelta(seconds=5, microseconds=1))
        with self.assertRaisesRegex(RiskInputError, "future"):
            cache.parse(payload).validate(now=self.now - timedelta(seconds=1, microseconds=1))
        cache.parse(payload).validate(now=self.now)
        self.assertEqual((cache.stats()["hits"], cache.stats()["errors"]), (3, 0))

    def test_service_owned_instances_do_not_share_cached_models_or_statistics(self):
        # Separate services/databases can carry identical versions with entirely
        # different payloads. The module has no global state or version index.
        first_cache, second_cache = MarketDecodeCache(4), MarketDecodeCache(4)
        first = first_cache.parse(self.payload(mark="100"))
        second = second_cache.parse(self.payload(mark="200"))
        equal_but_separate = second_cache.parse(self.payload(mark="100"))
        self.assertEqual((first.instruments["X"].mark_price, second.instruments["X"].mark_price), (D("100"), D("200")))
        self.assertEqual(equal_but_separate, first)
        self.assertIsNot(equal_but_separate, first)
        first_cache.clear()
        self.assertEqual((first_cache.stats()["size"], second_cache.stats()["size"]), (0, 2))

    def test_reference_errors_and_unhashable_inputs_are_not_negative_cached(self):
        cache = MarketDecodeCache(4)
        good = self.payload()
        retained = cache.parse(good)
        bad_number = json.loads(good)
        bad_number["assets"]["USD"]["price"] = 1
        cases = (None, 1, b"{}", {}, [], "\ud800", "NaN", '{"version":7,"version":7}', json.dumps(bad_number))
        for payload in cases:
            for _ in range(2):
                with self.subTest(payload=repr(payload)), self.assertRaises(RiskInputError):
                    cache.parse(payload)
        self.assertEqual(cache.stats()["errors"], 2 * len(cases))
        self.assertEqual(cache.stats()["size"], 1)
        self.assertIs(cache.parse(good), retained)

    def test_arbitrary_decoder_exceptions_propagate_without_evicting_or_caching(self):
        cache = MarketDecodeCache(1)
        a, b = self.payload(version=1), self.payload(version=2)
        retained = cache.parse(a)
        with patch.object(MarketSnapshot, "from_json", side_effect=RuntimeError("decoder unavailable")) as parser:
            for _ in range(2):
                with self.assertRaisesRegex(RuntimeError, "decoder unavailable"):
                    cache.parse(b)
            self.assertEqual(parser.call_count, 2)
        self.assertIs(cache.parse(a), retained)
        self.assertEqual((cache.stats()["size"], cache.stats()["evictions"], cache.stats()["errors"]), (1, 0, 2))

    def test_capacity_and_one_mebibyte_payload_bound(self):
        for capacity in (-1, MAX_CACHE_CAPACITY + 1, True, False, None, "4", 4.0):
            with self.subTest(capacity=capacity), self.assertRaises(ValueError):
                MarketDecodeCache(capacity)
        cache = MarketDecodeCache(1)
        payload = self.payload()
        padded = " " * (MAX_JSON_BYTES - len(payload.encode("utf-8"))) + payload
        retained = cache.parse(padded)
        self.assertEqual(cache.stats()["size"], 1)
        with self.assertRaises(RiskInputError):
            cache.parse(padded + " ")
        self.assertIs(cache.parse(padded), retained)
        self.assertEqual(cache.stats()["evictions"], 0)
        with self.assertRaises(AttributeError):
            cache.capacity = 10

    def test_clear_is_explicit_about_resetting_detached_statistics(self):
        cache = MarketDecodeCache(4)
        payload = self.payload()
        first = cache.parse(payload)
        cache.parse(payload)
        detached = cache.stats()
        detached["size"] = 100
        self.assertEqual(cache.stats()["size"], 1)
        cache.clear()
        self.assertEqual(cache.stats(), {"capacity": 4, "size": 0, "hits": 1, "misses": 1, "errors": 0, "evictions": 0})
        self.assertIsNot(cache.parse(payload), first)
        cache.clear(reset_stats=True)
        self.assertEqual(cache.stats(), {"capacity": 4, "size": 0, "hits": 0, "misses": 0, "errors": 0, "evictions": 0})
        for value in (None, 1, "true"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                cache.clear(reset_stats=value)

    def test_concurrent_same_payload_decodes_once_and_preserves_lru_bound(self):
        cache = MarketDecodeCache(4)
        payload = self.payload()
        barrier = Barrier(8)
        def parse_once(_):
            barrier.wait(timeout=5)
            return cache.parse(payload)
        with patch.object(MarketSnapshot, "from_json", wraps=MarketSnapshot.from_json) as parser:
            with ThreadPoolExecutor(max_workers=8) as pool:
                snapshots = list(pool.map(parse_once, range(8)))
        self.assertEqual(parser.call_count, 1)
        self.assertEqual(len({id(snapshot) for snapshot in snapshots}), 1)
        self.assertEqual(cache.stats(), {"capacity": 4, "size": 1, "hits": 7, "misses": 1, "errors": 0, "evictions": 0})

    def test_custom_unhashable_string_subclass_uses_reference_path(self):
        class UnhashableString(str):
            __hash__ = None
        cache = MarketDecodeCache(4)
        payload = UnhashableString(self.payload())
        self.assertEqual(cache.parse(payload), MarketSnapshot.from_json(str(payload)))
        self.assertEqual(cache.stats()["size"], 0)


if __name__ == "__main__":
    unittest.main()
