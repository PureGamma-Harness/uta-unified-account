"""Synthetic local matching only; not an external exchange adapter test."""
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uta.market import MarketSnapshot
from uta.matching import Matcher
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ExchangeService
from uta.storage import Database


class PartialCancelRecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "synthetic.sqlite3"
        self.now = datetime(2026, 11, 14, tzinfo=timezone.utc)
        self.service = self.reopen()
        self.service.publish_market(MarketSnapshot(1, self.now,
            {"USD": AssetSpec(D(1), D(1))},
            {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))}))
        self.service.set_kill_switch(False)
        for account in ("seller", "buyer", "late-buyer"):
            self.service.create_account(account)
            self.service.deposit(account, "seed", "USD", D(10000))

    def reopen(self):
        return ExchangeService(Database(self.path), {"USD": 8}, clock=lambda: self.now)

    def snapshot(self, service):
        return (service.accounts(), service.ledger.journal(), service.events(limit=1000),
                Matcher(service).trades(limit=1000))

    def matched(self, sell_quantity):
        self.service.submit_order("seller", "sell", "BTC-PERP", D(sell_quantity), D(100))
        self.service.submit_order("buyer", "buy", "BTC-PERP", D(2), D(100))
        self.assertEqual(Matcher(self.service).match_once("BTC-PERP")["confirmed_trades"], 1)

    def test_partial_cancel_restart_and_retries_do_not_revive_remainder(self):
        self.matched("-3")
        before = self.service.account("seller")
        self.assertEqual(D(before["open_order_margin"]), D("10.04"))
        journal = self.service.ledger.journal()
        cancelled = self.service.cancel_order("seller", "sell")
        self.assertEqual((cancelled["status"], cancelled["filled_quantity"]), ("CANCELLED", "-2"))
        after = self.service.account("seller")
        self.assertEqual(after["positions"], before["positions"])
        self.assertEqual(after["balances"], before["balances"])
        self.assertEqual(D(after["open_order_margin"]), 0)
        self.assertEqual(self.service.ledger.journal(), journal)
        reopened = self.reopen()
        stable = self.snapshot(reopened)
        self.assertEqual(reopened.cancel_order("seller", "sell"), cancelled)
        self.assertEqual(reopened.submit_order("seller", "sell", "BTC-PERP", D(-3), D(100)), cancelled)
        self.assertEqual(self.snapshot(reopened), stable)
        reopened.submit_order("late-buyer", "late", "BTC-PERP", D(1), D(100))
        matcher = Matcher(reopened)
        self.assertEqual(matcher.match_once("BTC-PERP")["confirmed_trades"], 0)
        self.assertEqual(len(matcher.trades()), 1)
        self.assertEqual(matcher.verify(strict=True)["paired_fills"], 2)
        self.assertEqual(reopened.account("seller")["positions"]["BTC-PERP"]["quantity"], "-2")
        self.assertEqual(D(reopened.account("seller")["balances"]["USD"]), D("9999.92"))
        reopened.ledger.verify()

    def test_cancel_after_complete_fill_is_noop_after_restart(self):
        self.matched("-2")
        reopened = self.reopen()
        stable = self.snapshot(reopened)
        result = reopened.cancel_order("seller", "sell")
        self.assertEqual((result["status"], result["filled_quantity"]), ("FILLED", "-2"))
        self.assertEqual(self.snapshot(reopened), stable)

    def test_partial_cancel_racing_remainder_match_has_only_serialized_outcomes(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        self.matched("-3")
        self.service.submit_order("late-buyer", "late", "BTC-PERP", D(1), D(100))
        barrier = Barrier(2)

        def cancel():
            service = self.reopen()
            barrier.wait(timeout=5)
            return service.cancel_order("seller", "sell")

        def match():
            service = self.reopen()
            barrier.wait(timeout=5)
            return Matcher(service).match_once("BTC-PERP")

        with ThreadPoolExecutor(max_workers=2) as pool:
            cancellation, matching = pool.submit(cancel), pool.submit(match)
            cancelled, matched = cancellation.result(timeout=10), matching.result(timeout=10)
        reopened = self.reopen()
        order = reopened.orders("seller")[0]
        self.assertIn((order["status"], order["filled_quantity"], matched["confirmed_trades"]),
                      (("CANCELLED", "-2", 0), ("FILLED", "-3", 1)))
        self.assertEqual(cancelled["status"], order["status"])
        trades = 1 + matched["confirmed_trades"]
        matcher = Matcher(reopened)
        self.assertEqual(len(matcher.trades()), trades)
        self.assertEqual(matcher.verify(strict=True)["paired_fills"], 2 * trades)
        account = reopened.account("seller")
        self.assertEqual(D(account["open_order_margin"]), 0)
        self.assertEqual(D(account["positions"]["BTC-PERP"]["quantity"]), D(order["filled_quantity"]))
        self.assertEqual(D(account["balances"]["USD"]),
                         D(10000) - abs(D(order["filled_quantity"])) * D(".04"))
        reopened.ledger.verify()
