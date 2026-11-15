"""Cache-boundary tests; independent financial cases live in a separate suite."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D, Inexact, Rounded, localcontext
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from uta.examples import synthetic_policy
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.reserve_kernel import ReserveInputs, ReserveKernel, calculate_reserve
from uta.service import ExchangeService, ServiceError
from uta.storage import Database


def inputs(**changes):
    return replace(ReserveInputs(
        quantity=D(2), filled_quantity=D(".5"), limit_price=D(110),
        mark_price=D(100), reduce_only=False, initial_margin_rate=D(".1"),
        fee_notional=D(25), charged_fee=D(".01"), fee_rate=D(".0004"),
        usd_scale=2,
    ), **changes)


class ReserveKernelTests(unittest.TestCase):
    def test_manual_cumulative_fee_case_and_read_only_key(self):
        # Remaining 1.5; IM 16.5; adverse loss 15; ceil(.076)-.01=.07.
        kernel = ReserveKernel(2)
        self.assertEqual(kernel.calculate(inputs()), D("31.57"))
        self.assertEqual(kernel.calculate(inputs()), D("31.57"))
        self.assertEqual(kernel.stats(), {"capacity": 2, "size": 1,
                                         "hits": 1, "misses": 1, "evictions": 0})
        with self.assertRaises(FrozenInstanceError):
            inputs().quantity = D(9)

    def test_every_economic_input_participates_in_the_key(self):
        kernel = ReserveKernel(32)
        changes = {
            "quantity": D(3), "filled_quantity": D(".6"), "limit_price": D(111),
            "mark_price": D(99), "reduce_only": True,
            "initial_margin_rate": D(".2"), "fee_notional": D(50),
            "charged_fee": D(".02"), "fee_rate": D(".001"), "usd_scale": 3,
        }
        kernel.calculate(inputs())
        for name, value in changes.items():
            with self.subTest(name=name):
                before = kernel.stats()
                key = inputs(**{name: value})
                self.assertEqual(kernel.calculate(key), calculate_reserve(key))
                self.assertEqual(kernel.stats()["misses"], before["misses"] + 1)
        # Numeric Decimal equality can safely share the same exact result.
        before = kernel.stats()
        self.assertEqual(kernel.calculate(inputs(quantity=D("2.000"))), D("31.57"))
        self.assertEqual(kernel.stats()["hits"], before["hits"] + 1)

    def test_lru_bound_clear_and_disabled_mode(self):
        kernel = ReserveKernel(2)
        a, b, c = (inputs(quantity=D(n)) for n in (2, 3, 4))
        for key in (a, b, a, c, b):
            kernel.calculate(key)
        self.assertEqual(kernel.stats(), {"capacity": 2, "size": 2,
                                         "hits": 1, "misses": 4, "evictions": 2})
        kernel.clear()
        self.assertEqual(kernel.stats()["size"], 0)
        self.assertEqual(kernel.stats()["misses"], 4)
        kernel.clear(reset_stats=True)
        self.assertEqual(kernel.stats(), {"capacity": 2, "size": 0,
                                         "hits": 0, "misses": 0, "evictions": 0})
        disabled = ReserveKernel(0)
        self.assertEqual(disabled.calculate(a), disabled.calculate(a))
        self.assertEqual(disabled.stats(), {"capacity": 0, "size": 0,
                                           "hits": 0, "misses": 2, "evictions": 0})

    def test_invalid_capacity_and_failed_math_are_not_cached(self):
        for capacity in (True, -1, 65537, 1.5, "4", None):
            with self.subTest(capacity=capacity), self.assertRaises(ValueError):
                ReserveKernel(capacity)
        kernel = ReserveKernel(1)
        invalid = inputs(quantity=D("Infinity"))
        for _ in range(2):
            with self.assertRaises((ValueError, OverflowError)):
                kernel.calculate(invalid)
        self.assertEqual(kernel.stats()["size"], 0)
        self.assertEqual(kernel.stats()["hits"], 0)
        self.assertEqual(kernel.stats()["misses"], 2)

    def test_miss_and_hit_ignore_decimal_precision_and_traps(self):
        kernel = ReserveKernel(1)
        with localcontext() as context:
            context.prec = 1
            context.traps[Inexact] = context.traps[Rounded] = True
            self.assertEqual(kernel.calculate(inputs()), D("31.57"))
            self.assertEqual(kernel.calculate(inputs()), D("31.57"))

    def test_parallel_misses_and_evictions_remain_bounded(self):
        kernel = ReserveKernel(3)
        keys = [inputs(quantity=D(n)) for n in range(1, 9)]
        expected = {key: calculate_reserve(key) for key in keys}
        def compute(index):
            key = keys[index % len(keys)]
            return kernel.calculate(key), expected[key]
        with ThreadPoolExecutor(max_workers=8) as workers:
            results = list(workers.map(compute, range(160)))
        self.assertTrue(all(actual == reference for actual, reference in results))
        self.assertLessEqual(kernel.stats()["size"], 3)
        self.assertEqual(kernel.stats()["hits"] + kernel.stats()["misses"], 160)


class ReserveServiceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.now = datetime(2026, 11, 15, tzinfo=timezone.utc)

    def open(self, name="account.sqlite3", *, cache=32, market_cache=4, configured=False):
        kwargs = {}
        if configured:
            catalog, rules = synthetic_policy()
            kwargs.update(product_catalog=catalog, portfolio_rules=rules)
        service = ExchangeService(Database(self.directory / name), {"USD": 2, "BTC": 8},
                                  clock=lambda: self.now, reserve_cache_size=cache,
                                  market_cache_size=market_cache, **kwargs)
        return service

    def market(self, mark="100", version=1):
        return MarketSnapshot(version, self.now,
            {"USD": AssetSpec(D(1), D(1)), "BTC": AssetSpec(D(100), D(".8"))},
            {"BTC-PERP": InstrumentSpec(D(mark), D(".1"), D(".05"))})

    def fund(self, service):
        service.create_account("alice")
        service.publish_market(self.market())
        service.deposit("alice", "fund", "USD", D(1000))
        service.set_kill_switch(False)

    def test_invalid_size_fails_before_database_file_creation(self):
        for index, size in enumerate((True, -1, 65537, 1.5, "1", None)):
            path = self.directory / f"invalid-{index}.sqlite3"
            with self.subTest(size=size), self.assertRaises(ServiceError) as rejected:
                ExchangeService(Database(path), {"USD": 2}, reserve_cache_size=size)
            self.assertEqual(rejected.exception.code, "invalid_configuration")
            self.assertFalse(path.exists())

    def test_default_path_remains_the_original_reference(self):
        service = ExchangeService(Database(self.directory / "default.sqlite3"), {"USD": 2})
        row = {"quantity": "2", "filled_quantity": ".5", "limit_price": "110",
               "reduce_only": False, "fee_notional": "25", "charged_fee": ".01", "symbol": "BTC-PERP"}
        with patch.object(service, "_reserve_reference", wraps=service._reserve_reference) as reference:
            self.assertEqual(service._reserve(row, self.market()), D("31.57"))
            self.assertEqual(reference.call_count, 1)
        self.assertEqual(service.reserve_cache_stats()["size"], 0)

    def test_invalid_market_size_fails_before_database_file_creation(self):
        for index, size in enumerate((True, -1, 65, 1.5, "1", None)):
            path = self.directory / f"invalid-market-{index}.sqlite3"
            with self.subTest(size=size), self.assertRaises(ServiceError) as rejected:
                ExchangeService(Database(path), {"USD": 2}, market_cache_size=size)
            self.assertEqual(rejected.exception.code, "invalid_configuration")
            self.assertFalse(path.exists())

    def test_warm_market_decode_rechecks_freshness_and_same_version_row(self):
        service = self.open()
        self.fund(service)
        service.submit_order("alice", "order", "BTC-PERP", D(2), D(100))
        service.risk("alice")
        before = service.market_cache_stats()
        self.assertGreater(before["hits"], 0)
        # Simulate a same-version persisted edit. A version-keyed cache would
        # incorrectly retain the old quote and underreserve the live order.
        with service.database.transaction() as connection:
            connection.execute("UPDATE uta_market SET payload=? WHERE singleton=1",
                               (self.market("200").to_json(),))
        self.assertEqual(service.risk("alice")["open_order_margin"], "40.08")
        self.assertGreater(service.market_cache_stats()["misses"], before["misses"])
        self.now += timedelta(seconds=6)
        with self.assertRaises(ServiceError) as rejected:
            service.risk("alice")
        self.assertEqual(rejected.exception.code, "market_unavailable")

    def test_market_cache_clear_and_configured_policy_are_rechecked(self):
        service = self.open(configured=True)
        self.fund(service)
        service.submit_order("alice", "order", "BTC-PERP", D(1), D(100))
        service.risk("alice")
        self.assertGreater(service.market_cache_stats()["size"], 0)
        service.clear_market_cache(reset_stats=True)
        self.assertEqual(service.market_cache_stats(), {"capacity": 4, "size": 0,
            "hits": 0, "misses": 0, "errors": 0, "evictions": 0})
        service.risk("alice")
        with patch.object(service, "_validate_policy_market", side_effect=ServiceError("margin_rule_conflict", "test policy conflict", 409)):
            with self.assertRaises(ServiceError) as rejected:
                service.risk("alice")
        self.assertEqual(rejected.exception.code, "margin_rule_conflict")

    def test_seeded_cached_and_original_fraction_formulas_agree(self):
        service = self.open()
        rng = random.Random(918715)
        for index in range(150):
            row = {"quantity": str(rng.choice((-1, 1)) * rng.randrange(1, 100)),
                   "filled_quantity": str(rng.randrange(-10, 11)),
                   "limit_price": str(rng.randrange(1, 200)),
                   "reduce_only": bool(index % 2), "fee_notional": str(rng.randrange(100)),
                   "charged_fee": str(D(rng.randrange(5)) / D(100)), "symbol": "BTC-PERP"}
            market = self.market(str(rng.randrange(1, 200)))
            expected = service._reserve_reference(row, market)
            self.assertEqual(service._reserve(row, market), expected)
            self.assertEqual(service._reserve(row, market), expected)
        self.assertEqual(service.reserve_cache_stats()["hits"], 150)
        self.assertLessEqual(service.reserve_cache_stats()["size"], 32)

    def test_current_product_rules_are_checked_even_on_a_warm_entry(self):
        service = self.open(configured=True)
        self.fund(service)
        service.submit_order("alice", "order", "BTC-PERP", D(2), D(100))
        service.account("alice")
        with patch.object(type(service.product_catalog), "require_risk_supported", side_effect=KeyError("removed")):
            with self.assertRaises(ServiceError) as error:
                service.account("alice")
        self.assertEqual(error.exception.code, "risk_unavailable")

    def test_partial_fill_repricing_restart_and_reference_reconciliation(self):
        service = self.open()
        self.fund(service)
        order = service.submit_order("alice", "order", "BTC-PERP", D(2), D(100))
        self.assertEqual(order["reserved_margin"], "20.08")
        service.apply_fill("alice", "order", "fill", D(".5"), D(100))
        self.assertEqual(service.account("alice")["open_order_margin"], "15.06")
        service.publish_market(self.market("110", version=2))
        self.assertEqual(service.account("alice")["open_order_margin"], "16.56")
        reference = self.open(cache=0, market_cache=0)
        self.assertEqual(service.account("alice"), reference.account("alice"))
        self.assertEqual(service.risk("alice"), reference.risk("alice"))
        self.assertEqual(service.ledger.verify(), 2)
        self.assertEqual(reference.reserve_cache_stats()["size"], 0)
        self.assertEqual(service.cancel_order("alice", "order")["reserved_margin"], "0")
        self.now += timedelta(seconds=6)
        with self.assertRaises(ServiceError) as rejected:
            service.submit_order("alice", "stale", "BTC-PERP", D(1), D(100))
        self.assertEqual(rejected.exception.code, "market_unavailable")


if __name__ == "__main__":
    unittest.main()
