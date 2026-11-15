"""Opt-in computation caches preserve the router's authority and rollback."""
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from uta.examples import synthetic_policy
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ServiceError
from uta.shard_admission import RouterAdmissionBatcher
from uta.sharding import ShardRouter


class ShardKernelTests(unittest.TestCase):
    def test_invalid_capacities_fail_before_layout_or_database_creation(self):
        with TemporaryDirectory() as directory:
            target = Path(directory) / "never-created"
            for sizes in ((-1, 0), (65537, 0), (False, 0), (0, -1), (0, 65), (0, True)):
                with self.subTest(sizes=sizes), self.assertRaises(ServiceError) as rejected:
                    ShardRouter(target, 2, {"USD": 8}, reserve_cache_size=sizes[0], market_cache_size=sizes[1])
                self.assertEqual(rejected.exception.code, "invalid_configuration")
                self.assertFalse(target.exists())

    def test_cached_grouped_route_revalues_and_reopens_uncached_without_layout_change(self):
        with TemporaryDirectory() as directory:
            now = datetime(2026, 11, 15, tzinfo=timezone.utc)
            catalog, rules = synthetic_policy()
            def reopen(reserve=0, market=0):
                return ShardRouter(directory, 2, {"USD": 8, "BTC": 8}, clock=lambda: now,
                    product_catalog=catalog, portfolio_rules=rules,
                    reserve_cache_size=reserve, market_cache_size=market)
            def snapshot(version, mark):
                return MarketSnapshot(version, now, {"USD": AssetSpec(D(1), D(1)),
                    "BTC": AssetSpec(D(100), D(".8"))},
                    {"BTC-PERP": InstrumentSpec(D(mark), D(".1"), D(".05"))})
            router = reopen(32, 2)
            accounts = [next(f"account-{i}" for i in range(100) if router.shard_for(f"account-{i}") == shard)
                        for shard in range(2)]
            for account in accounts:
                router.create_account(account)
                router.deposit(account, "seed", "USD", D(1000))
            router.publish_market(snapshot(1, 100))
            router.set_kill_switch(False)
            with RouterAdmissionBatcher(router, worker_count=2, max_batch_size=4) as batcher:
                futures = [batcher.submit_order(account, order, "BTC-PERP", D(1), D(100))
                           for account in accounts for order in ("one", "two")]
                self.assertTrue(all(f.result(timeout=5)["status"] == "OPEN" for f in futures))
                router.publish_market(snapshot(2, 101))
                blocked = batcher.submit_order(accounts[0], "three", "BTC-PERP", D(1), D(100))
                with self.assertRaises(ServiceError) as rejected:
                    blocked.result(timeout=5)
                self.assertEqual(rejected.exception.code, "router_halted")
                router.set_kill_switch(False)
                batcher.submit_order(accounts[0], "three", "BTC-PERP", D(1), D(100)).result(timeout=5)
            self.assertEqual(D(router.account(accounts[0])["open_order_margin"]), D("30.42"))
            for entry in router.cache_stats().values():
                self.assertEqual(entry["reserve"]["capacity"], 32)
                self.assertEqual(entry["market"]["capacity"], 2)
                self.assertGreater(entry["reserve"]["hits"], 0)
                self.assertGreater(entry["market"]["hits"], 0)
            before = [router.account(account) for account in accounts]
            layout = dict(router.layout)
            journals = [service.ledger.journal() for service in router._services]
            reference = reopen()
            self.assertEqual(dict(reference.layout), layout)
            self.assertEqual([reference.account(account) for account in accounts], before)
            with RouterAdmissionBatcher(reference) as batcher:
                batcher.submit_order(accounts[0], "one", "BTC-PERP", D(1), D(100)).result(timeout=5)
            self.assertEqual([reference.account(account) for account in accounts], before)
            self.assertEqual([service.ledger.journal() for service in reference._services], journals)
            for service in reference._services:
                service.ledger.verify()
            self.assertTrue(all(entry["reserve"]["capacity"] == entry["market"]["capacity"] == 0
                                for entry in reference.cache_stats().values()))
