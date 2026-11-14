from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D, Inexact, localcontext
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from uta.market import MarketSnapshot
from uta.matching import Matcher
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ExchangeService, ServiceError
from uta.storage import Database


class MatchingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "exchange.sqlite3"
        self.now = datetime(2026, 11, 14, tzinfo=timezone.utc)
        self.exchange = self.reopen()
        self.publish()
        self.exchange.set_kill_switch(False)
        self.matcher = Matcher(self.exchange)
        for account in ("alice", "bob", "carol", "dave"):
            self.fund(account)

    def reopen(self):
        return ExchangeService(Database(self.path), {"USD": 8}, clock=lambda: self.now)

    def publish(self, version=1, mark="100"):
        self.exchange.publish_market(MarketSnapshot(version, self.now,
            {"USD": AssetSpec(D(1), D(1))},
            {"BTC-PERP": InstrumentSpec(D(mark), D(".1"), D(".05"))}))

    def fund(self, account, amount="10000"):
        self.exchange.create_account(account)
        self.exchange.deposit(account, "funding", "USD", D(amount))

    def order(self, account, identifier, quantity, price="100", reduce_only=False):
        return self.exchange.submit_order(account, identifier, "BTC-PERP", D(quantity), D(price), reduce_only=reduce_only)

    def financial(self):
        return (self.exchange.accounts(), self.exchange.ledger.journal(),
                self.exchange.events(limit=1000), self.matcher.trades(limit=1000))

    def test_real_opposing_orders_partial_settlement_and_maker_price(self):
        self.order("alice", "maker-sell", "-3", "100")
        self.order("bob", "taker-buy", "2", "110")
        result = self.matcher.match_once("BTC-PERP")
        self.assertEqual(result["confirmed_trades"], 1)
        receipt = result["trades"][0]
        self.assertEqual((receipt["quantity"], receipt["price"]), ("2", "100"))
        self.assertEqual(self.exchange.orders("alice")[0]["filled_quantity"], "-2")
        self.assertEqual(self.exchange.orders("alice")[0]["status"], "PARTIALLY_FILLED")
        self.assertEqual(self.exchange.orders("bob")[0]["status"], "FILLED")
        self.assertEqual(self.exchange.account("alice")["positions"]["BTC-PERP"]["quantity"], "-2")
        self.assertEqual(self.exchange.account("bob")["positions"]["BTC-PERP"]["quantity"], "2")
        self.assertEqual(D(self.exchange.account("alice")["balances"]["USD"]), D("9999.92"))
        self.assertEqual(self.matcher.verify(strict=True)["paired_fills"], 2)

    def test_price_priority_is_numeric_not_lexical_and_time_breaks_ties(self):
        self.order("alice", "low", "1", "9")
        self.order("bob", "high-first", "1", "100")
        self.order("carol", "high-second", "1", "100")
        self.order("dave", "seller", "-2", "90")
        result = self.matcher.match_once("BTC-PERP")
        self.assertEqual([trade["buy_order_id"] for trade in result["trades"]], ["high-first", "high-second"])
        self.assertEqual([trade["price"] for trade in result["trades"]], ["100", "100"])
        self.assertEqual(self.exchange.orders("alice")[0]["status"], "OPEN")
        self.assertEqual(self.matcher.verify(strict=True)["matches"], 2)

    def test_uncrossed_or_one_sided_book_never_creates_mark_fills(self):
        self.order("alice", "bid", "1", "90")
        before = self.financial()
        self.assertEqual(self.matcher.match_once("BTC-PERP")["confirmed_trades"], 0)
        self.assertEqual(self.financial(), before)
        self.order("bob", "ask", "-1", "110")
        before = self.financial()
        self.assertEqual(self.matcher.match_once("BTC-PERP")["confirmed_trades"], 0)
        self.assertEqual(self.financial(), before)

    def test_self_trade_prevention_cancels_taker_without_financial_effect(self):
        self.order("alice", "maker", "-1")
        self.order("alice", "taker", "1")
        journal = self.exchange.ledger.journal()
        result = self.matcher.match_once("BTC-PERP")
        self.assertEqual(result["confirmed_trades"], 0)
        self.assertEqual(result["cancelled_orders"][0]["order_id"], "taker")
        self.assertEqual(result["cancelled_orders"][0]["reason"], "self_trade_prevention")
        self.assertEqual(self.exchange.ledger.journal(), journal)
        self.assertFalse(self.exchange.account("alice")["positions"])
        self.assertEqual(self.matcher.trades(), [])

    def test_second_side_risk_failure_rolls_back_first_side_before_cancelling_rejected_order(self):
        self.publish(2, "1")
        self.fund("thin", ".1004")
        self.order("bob", "buy", "1", "1")
        self.order("thin", "sell", "-1", "1")
        self.publish(3, "2")
        buyer_before = self.exchange.account("bob")
        journal_before = self.exchange.ledger.journal()
        result = self.matcher.match_once("BTC-PERP")
        self.assertEqual(result["confirmed_trades"], 0)
        self.assertEqual(result["blocked"][0]["account_id"], "thin")
        self.assertEqual(result["blocked"][0]["code"], "insufficient_margin")
        self.assertEqual(result["cancelled_orders"][0]["account_id"], "thin")
        self.assertEqual(self.exchange.account("bob"), buyer_before)
        self.assertEqual(self.exchange.orders("bob")[0]["filled_quantity"], "0")
        self.assertEqual(self.exchange.ledger.journal(), journal_before)
        self.assertEqual(self.matcher.trades(), [])
        with self.exchange._transaction() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_fills").fetchone()[0], 0)

    def test_unexpected_second_side_failure_rolls_back_whole_batch(self):
        self.order("alice", "buy", "1")
        self.order("bob", "sell", "-1")
        before = self.financial()
        original = self.exchange._apply_fill
        calls = 0
        def fail_second(*args):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("injected settlement crash")
            return original(*args)
        with patch.object(self.exchange, "_apply_fill", fail_second):
            with self.assertRaisesRegex(RuntimeError, "settlement crash"):
                self.matcher.match_once("BTC-PERP")
        self.assertEqual(self.financial(), before)
        self.assertEqual(self.matcher.match_once("BTC-PERP")["confirmed_trades"], 1)

    def test_failure_after_receipt_before_event_rolls_back_both_financial_legs(self):
        self.order("alice", "buy", "1")
        self.order("bob", "sell", "-1")
        before = self.financial()
        original = self.exchange._event
        def reject_event(connection, kind, account, payload):
            if kind == "MATCH_CONFIRMED":
                raise RuntimeError("injected receipt publication failure")
            return original(connection, kind, account, payload)
        with patch.object(self.exchange, "_event", reject_event):
            with self.assertRaises(RuntimeError):
                self.matcher.match_once("BTC-PERP")
        self.assertEqual(self.financial(), before)

    def test_restart_and_competing_matchers_cannot_settle_one_trade_twice(self):
        self.order("alice", "buy", "1")
        self.order("bob", "sell", "-1")
        matchers = [Matcher(self.reopen()) for _ in range(6)]
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda matcher: matcher.match_once("BTC-PERP"), matchers))
        self.assertEqual(sum(result["confirmed_trades"] for result in results), 1)
        restarted = Matcher(self.reopen())
        before = self.financial()
        self.assertEqual(restarted.match_once("BTC-PERP")["confirmed_trades"], 0)
        self.assertEqual(self.financial(), before)
        self.assertEqual(restarted.verify(strict=True)["matches"], 1)

    def test_halt_and_stale_preserve_unexecuted_orders_and_margin(self):
        self.order("alice", "buy", "1")
        self.order("bob", "sell", "-1")
        self.exchange.set_kill_switch(True)
        before = self.financial()
        halted = self.matcher.match_once("BTC-PERP")
        self.assertEqual(halted["confirmed_trades"], 0)
        self.assertEqual(halted["blocked"][0]["code"], "trading_halted")
        self.assertEqual(self.financial(), before)
        self.exchange.set_kill_switch(False)
        self.now += timedelta(seconds=6)
        before = self.financial()
        stale = self.matcher.match_once("BTC-PERP")
        self.assertEqual(stale["confirmed_trades"], 0)
        self.assertEqual(stale["blocked"][0]["code"], "market_unavailable")
        self.assertEqual(self.financial(), before)

    def test_confirmed_partial_liquidation_survives_restart_and_reconciles_four_sides(self):
        # Seed exposure through real opposing orders, not the mark-price model.
        self.fund("distressed", "1000")
        self.order("distressed", "open", "90")
        self.order("bob", "initial-counterparty", "-90")
        self.assertEqual(self.matcher.match_once("BTC-PERP")["confirmed_trades"], 1)
        self.publish(2, "90")
        plan = self.exchange.supervise_account("distressed")
        self.assertEqual(plan["state"], "LIQUIDATING")
        self.assertEqual(plan["created_orders"][0]["quantity"], "-90")
        self.order("carol", "partial-liquidity", "45", "90")
        partial = self.matcher.match_once("BTC-PERP")
        self.assertEqual(partial["confirmed_trades"], 1)
        self.assertTrue(partial["trades"][0]["sell_order_id"].startswith("liq:"))
        self.assertEqual(self.exchange.account("distressed")["positions"]["BTC-PERP"]["quantity"], "45")
        self.exchange = self.reopen()
        self.matcher = Matcher(self.exchange)
        self.assertEqual(self.matcher.match_once("BTC-PERP")["confirmed_trades"], 0)
        self.assertEqual(self.exchange.account("distressed")["positions"]["BTC-PERP"]["quantity"], "45")
        self.order("dave", "remaining-liquidity", "45", "90")
        final = self.matcher.match_once("BTC-PERP")
        self.assertEqual(final["confirmed_trades"], 1)
        self.assertFalse(self.exchange.account("distressed")["positions"])
        self.assertEqual(D(self.exchange.account("distressed")["balances"]["USD"]), D("93.16"))
        self.assertEqual(self.exchange.supervise_account("distressed")["state"], "NORMAL")
        verified = self.matcher.verify(strict=True)
        self.assertEqual((verified["matches"], verified["paired_fills"], verified["unpaired_fills"]), (3, 6, 0))

    def test_strict_reconciliation_rejects_standalone_fill_and_detects_missing_receipt_protection(self):
        self.order("alice", "manual", "1")
        self.exchange.apply_fill("alice", "manual", "manual", D(1), D(100))
        self.assertEqual(self.matcher.verify()["unpaired_fills"], 1)
        with self.assertRaises(ServiceError) as unpaired:
            self.matcher.verify(strict=True)
        self.assertEqual(unpaired.exception.code, "unpaired_execution")
        with self.exchange._transaction() as connection:
            connection.execute("DROP TRIGGER uta_matches_no_delete")
        with self.assertRaises(ServiceError) as corrupt:
            self.matcher.verify()
        self.assertEqual(corrupt.exception.code, "matching_corruption")

    def test_trade_receipts_are_immutable_and_paginated(self):
        self.order("alice", "buy", "2")
        self.order("bob", "sell-one", "-1")
        self.order("carol", "sell-two", "-1")
        first_batch = self.matcher.match_once("BTC-PERP", max_matches=1)
        self.assertTrue(first_batch["batch_exhausted"])
        self.assertEqual(first_batch["confirmed_trades"], 1)
        self.matcher.match_once("BTC-PERP")
        first = self.matcher.trades(limit=1)
        second = self.matcher.trades(after=first[0]["sequence"], limit=1)
        self.assertEqual([first[0]["sequence"], second[0]["sequence"]], [1, 2])
        with self.assertRaises(sqlite3.IntegrityError):
            with self.exchange._transaction() as connection:
                connection.execute("UPDATE uta_matches SET price='1'")
        with self.assertRaises(sqlite3.IntegrityError):
            with self.exchange._transaction() as connection:
                connection.execute("DELETE FROM uta_matches")

    def test_matching_financial_arithmetic_ignores_callers_decimal_context(self):
        self.order("alice", "buy", "1.12345678", "100.12345678")
        self.order("bob", "sell", "-1.12345678", "100")
        with localcontext() as context:
            context.prec = 1
            context.Emax = 1
            context.traps[Inexact] = True
            result = self.matcher.match_once("BTC-PERP")
            self.assertEqual(result["confirmed_trades"], 1)
            self.assertEqual(result["trades"][0]["quantity"], "1.12345678")
            self.matcher.verify(strict=True)

    def test_inputs_and_independent_cli_help(self):
        for symbol, maximum in (("", 1), ("BTC-PERP", True), ("BTC-PERP", 0), ("BTC-PERP", 1001)):
            with self.subTest(symbol=symbol, maximum=maximum), self.assertRaises(ServiceError):
                self.matcher.match_once(symbol, maximum)
        with self.assertRaises(ServiceError):
            self.matcher.match_once("MISSING")
        result = subprocess.run([sys.executable, "-m", "uta.matching", "--help"],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--database", result.stdout)


if __name__ == "__main__":
    unittest.main()
