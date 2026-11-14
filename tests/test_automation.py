import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

from uta.configuration import load_policy
from uta.market import MarketSnapshot
from uta.matching import Matcher
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ExchangeService
from uta.storage import Database
from uta.supervisor import ExchangeWorker


class AutomationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "exchange.sqlite3"
        self.now = datetime(2026, 11, 14, tzinfo=timezone.utc)
        self.exchange = self.reopen()
        self.publish(1, "100")
        self.exchange.set_kill_switch(False)
        for account, funds in (("alice", "1000"), ("bob", "100000")):
            self.exchange.create_account(account)
            self.exchange.deposit(account, "funding", "USD", D(funds))

    def reopen(self):
        return ExchangeService(Database(self.path), {"USD": 8}, clock=lambda: self.now)

    def publish(self, version, mark):
        self.exchange.publish_market(MarketSnapshot(version, self.now,
            {"USD": AssetSpec(D(1), D(1))},
            {"BTC-PERP": InstrumentSpec(D(mark), D(".1"), D(".05"))}))

    def test_real_matching_partial_liquidation_and_restart_are_automated(self):
        self.exchange.submit_order("alice", "open", "BTC-PERP", D(90), D(100))
        self.exchange.submit_order("bob", "open", "BTC-PERP", D(-90), D(100))
        worker = ExchangeWorker(self.exchange)
        self.assertEqual(worker.run_once()["linear_trades"], 1)
        self.publish(2, "90")
        self.exchange.submit_order("bob", "liquidity-one", "BTC-PERP", D(45), D(90))
        first = worker.run_once()
        self.assertEqual(first["linear_trades"], 1)
        self.assertEqual(D(self.exchange.account("alice")["positions"]["BTC-PERP"]["quantity"]), D(45))
        self.assertEqual(worker.run_once()["linear_trades"], 0, "no opposing liquidity must never fabricate a fill")
        self.exchange = self.reopen()
        self.exchange.submit_order("bob", "liquidity-two", "BTC-PERP", D(45), D(90))
        worker = ExchangeWorker(self.exchange)
        self.assertEqual(worker.run_once()["linear_trades"], 1)
        final = worker.run_once()
        self.assertIn({"account_id": "alice", "state": "NORMAL"}, final["plans"])
        account = self.exchange.account("alice")
        self.assertFalse(account["positions"])
        self.assertEqual(D(account["balances"]["USD"]), D("93.16"))
        self.assertEqual(Matcher(self.exchange).verify(strict=True)["matches"], 3)

    def test_stale_tick_preserves_pending_orders(self):
        self.exchange.submit_order("alice", "waiting", "BTC-PERP", D(1), D(90))
        worker = ExchangeWorker(self.exchange)
        before = self.exchange.orders("alice"), self.exchange.events(limit=1000)
        self.now += timedelta(seconds=6)
        result = worker.run_once()
        self.assertEqual(result["state"], "blocked")
        self.assertEqual((self.exchange.orders("alice"), self.exchange.events(limit=1000)), before)

    def test_account_cursor_rotates_and_survives_restart(self):
        worker = ExchangeWorker(self.exchange, account_batch=1)
        self.assertEqual(worker.run_once()["plans"][0]["account_id"], "alice")
        worker = ExchangeWorker(self.reopen(), account_batch=1)
        self.assertEqual(worker.run_once()["plans"][0]["account_id"], "bob")
        self.assertEqual(worker.run_once()["plans"][0]["account_id"], "alice")

    def test_configuration_limits_and_worker_bounds(self):
        for arguments in ({"account_batch": True}, {"matches_per_symbol": 0}, {"interval": float("nan")}):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                ExchangeWorker(self.exchange, **arguments)
        self.assertEqual(load_policy(), {})
        with self.assertRaises(ValueError):
            load_policy("catalog.json", None)
        document = Path(self.temporary.name) / "large.json"
        document.write_bytes(b" " * (1024 * 1024 + 1))
        with self.assertRaises(ValueError):
            load_policy(document, document)

    def test_unexpected_background_failure_persists_halt_for_operator_recovery(self):
        worker = ExchangeWorker(self.exchange)
        def fail():
            worker._stop.set()
            raise RuntimeError("synthetic worker failure")
        with patch.object(worker, "run_once", side_effect=fail):
            worker._run()
        self.assertEqual(worker.last_report, {"state": "blocked", "reason": "worker_failure",
                                             "emergency_halt_committed": True})
        self.assertTrue(self.reopen().readiness()["halted"])


if __name__ == "__main__":
    unittest.main()
