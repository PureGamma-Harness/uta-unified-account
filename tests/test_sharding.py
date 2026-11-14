from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal as D
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import shutil
from tempfile import TemporaryDirectory
from threading import Event
import unittest
from unittest.mock import patch

from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ServiceError
from uta.sharding import HASH_VERSION, ShardRouter


class ShardingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "router"
        self.now = datetime(2026, 11, 14, tzinfo=timezone.utc)
        self.router = self.reopen()

    def reopen(self, **kwargs):
        return ShardRouter(self.path, 2, {"USD": 8}, clock=lambda: self.now, **kwargs)

    def market(self, version=1):
        return MarketSnapshot(version, self.now, {"USD": AssetSpec(D(1), D(1))},
                              {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))})

    def activate(self):
        self.router.publish_market(self.market())
        self.router.set_kill_switch(False)

    def assert_code(self, code, function, *args, **kwargs):
        with self.assertRaises(ServiceError) as raised:
            function(*args, **kwargs)
        self.assertEqual(raised.exception.code, code)

    def test_fixed_hash_layout_policy_and_schema_are_immutable_across_restart(self):
        self.assertEqual(self.router.layout["hash_version"], HASH_VERSION)
        for account in ("alice", "bob", "abc:001"):
            self.assertEqual(self.router.shard_for(account), int.from_bytes(sha256(account.encode()).digest(), "big") % 2)
        restarted = self.reopen()
        self.assertEqual(restarted.shard_for("alice"), self.router.shard_for("alice"))
        self.assert_code("layout_conflict", ShardRouter, self.path, 4, {"USD": 8})
        self.assert_code("layout_conflict", ShardRouter, self.path, 2, {"USD": 6})
        self.assert_code("layout_conflict", self.reopen, fee_rate=D(".001"))
        with self.router.control.transaction() as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("UPDATE router_layout SET descriptor='{}'")

    def test_fresh_layout_starts_halted_and_publication_never_auto_activates(self):
        self.router.create_account("alice")
        self.router.deposit("alice", "fund", "USD", D(1000))
        self.assert_code("publication_incomplete", self.router.set_kill_switch, False)
        self.router.publish_market(self.market())
        self.assert_code("router_halted", self.router.submit_order, "alice", "o1", "BTC-PERP", D(1), D(100))
        self.router.set_kill_switch(False)
        self.router.submit_order("alice", "o1", "BTC-PERP", D(1), D(100))
        self.assertEqual(self.router.risk("alice")["open_order_margin"], "10.04")
        self.router.cancel_order("alice", "o1")
        self.assertEqual(self.router.account("alice")["open_order_margin"], "0")
        shard = self.router.shard_for("alice")
        other = 1 - shard
        self.assert_code("account_not_found", self.router._services[other].account, "alice")

    def test_partial_market_fanout_stays_closed_after_restart_and_new_version_recovers(self):
        self.activate()
        with patch.object(self.router._services[1], "publish_market", side_effect=OSError("injected disk error")):
            with self.assertRaises(OSError):
                self.router.publish_market(self.market(2))
        state = self.router.diagnostics()["state"]
        self.assertTrue(state["halted"])
        self.assertTrue(state["publishing"])
        self.assertEqual(state["watermarks"], {"0": 2})
        restarted = self.reopen()
        self.assert_code("publication_incomplete", restarted.set_kill_switch, False)
        self.assert_code("router_halted", restarted.submit_order, "alice", "o", "BTC-PERP", D(1), D(100))
        restarted.publish_market(self.market(3))
        self.assertFalse(restarted.diagnostics()["ready"])
        restarted.set_kill_switch(False)
        self.assertTrue(restarted.diagnostics()["ready"])

    def test_partial_activation_cannot_open_global_gate(self):
        self.router.publish_market(self.market())
        with patch.object(self.router._services[1], "set_kill_switch", side_effect=OSError("injected")):
            with self.assertRaises(OSError):
                self.router.set_kill_switch(False)
        self.assertFalse(self.router.diagnostics()["ready"])
        self.assertTrue(self.reopen().diagnostics()["state"]["halted"])

    def test_credit_debt_pool_and_funding_proof_have_explicit_shard_ownership(self):
        self.activate()
        self.router.create_account("alice")
        self.router.deposit("alice", "fund", "USD", D(1000))
        shard = self.router.shard_for("alice")
        self.router.configure_credit_limit("alice", "USD", D(100))
        self.router.configure_credit_asset_limit(shard, "USD", D(100))
        funded = self.router.fund_credit_pool(shard, "capital", "USD", D(100), source_reference="capital:one")
        self.assertEqual(funded, self.router.fund_credit_pool(shard, "capital", "USD", D("100.00"), source_reference="capital:one"))
        self.assert_code("funding_source_conflict", self.router.fund_credit_pool, 1-shard, "other", "USD", D(100), source_reference="capital:one")
        self.router.borrow("alice", "loan", "USD", D(10))
        self.assertEqual(self.router.account("alice")["liabilities"]["USD"]["principal"], "10")
        self.router.set_kill_switch(True)
        self.assert_code("router_halted", self.router.borrow, "alice", "another", "USD", D(1))
        self.router.repay("alice", "repay", "USD", D(10))
        self.assertEqual(self.router.account("alice")["liabilities"]["USD"]["total"], "0")

    def test_same_shard_matches_atomically_and_cross_shard_transfer_is_rejected(self):
        self.activate()
        names = [f"account-{index}" for index in range(20)]
        group = [name for name in names if self.router.shard_for(name) == 0]
        outsider = next(name for name in names if self.router.shard_for(name) == 1)
        for name in group[:2]:
            self.router.create_account(name)
            self.router.deposit(name, "fund", "USD", D(1000))
        buyer, seller = group[:2]
        self.router.submit_order(buyer, "buy", "BTC-PERP", D(1), D(100))
        self.router.submit_order(seller, "sell", "BTC-PERP", D(-1), D(100))
        self.assertEqual(self.router.match_once(0, "BTC-PERP")["confirmed_trades"], 1)
        self.assert_code("cross_shard_unsupported", self.router.require_same_shard, buyer, outsider)
        self.assert_code("cross_shard_unsupported", self.router.transfer, buyer, outsider, "USD", D(1))
        result = self.router.events({"shard": 0, "sequence": 0}, limit=1000)
        self.assertTrue(result["events"])
        self.assertTrue(all(row["cursor"]["shard"] == 0 for row in result["events"]))
        self.assert_code("invalid_cursor", self.router.events, {"sequence": 0})

    def test_halt_excludes_inflight_admission_and_other_router_instances(self):
        self.activate()
        self.router.create_account("alice")
        self.router.deposit("alice", "fund", "USD", D(1000))
        restarted = self.reopen()
        service = self.router._services[self.router.shard_for("alice")]
        entered, release = Event(), Event()
        original = service.submit_order
        def delayed(*args, **kwargs):
            entered.set()
            if not release.wait(3):
                raise RuntimeError("test release timed out")
            return original(*args, **kwargs)
        with ThreadPoolExecutor(max_workers=2) as executor, patch.object(service, "submit_order", side_effect=delayed):
            operation = executor.submit(self.router.submit_order, "alice", "before-halt", "BTC-PERP", D(1), D(100))
            self.assertTrue(entered.wait(2))
            halted = executor.submit(restarted.set_kill_switch, True)
            self.assertFalse(halted.done())
            release.set()
            operation.result(timeout=3)
            halted.result(timeout=3)
        self.assert_code("router_halted", self.router.submit_order, "alice", "after-halt", "BTC-PERP", D(1), D(100))

    def test_missing_persisted_shard_is_not_silently_recreated(self):
        self.router._path(1).unlink()
        self.assert_code("shard_unavailable", self.reopen)
        self.assertFalse(self.router._path(1).exists())
        self.assertTrue(self.router._state()["halted"])

    def test_empty_or_exchanged_database_cannot_impersonate_a_persisted_shard(self):
        self.router._path(1).write_bytes(b"")
        self.assert_code("shard_unavailable", self.reopen)
        self.assertEqual(self.router._path(1).stat().st_size, 0)
        shutil.copyfile(self.router._path(0), self.router._path(1))
        self.assert_code("shard_identity_conflict", self.reopen)
        self.assertTrue(self.router._state()["halted"])

    def test_funding_proof_claim_survives_ambiguous_local_funding_failure(self):
        with patch("uta.sharding.CreditService.fund_pool", side_effect=OSError("injected after proof claim")):
            with self.assertRaises(OSError):
                self.router.fund_credit_pool(0, "fund", "USD", D(10), source_reference="proof:one")
        restarted = self.reopen()
        self.assert_code("funding_source_conflict", restarted.fund_credit_pool, 1, "fund", "USD", D(10), source_reference="proof:one")
        self.assertEqual(restarted.fund_credit_pool(0, "fund", "USD", D(10), source_reference="proof:one")["amount"], "10")


if __name__ == "__main__":
    unittest.main()
