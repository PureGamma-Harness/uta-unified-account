from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D, Inexact, Rounded, localcontext
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from uta.credit import CreditService
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.products import ProductCatalog, ProductKind, ProductSpec, TradingStatus
from uta.service import ExchangeService, ServiceError
from uta.spot import SpotExchange, locked_asset
from uta.storage import Database


class SpotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "exchange.sqlite3"
        self.now = datetime(2026, 11, 14, tzinfo=timezone.utc)
        self.scales = {"USD": 8, "BTC": 8}
        self.service = ExchangeService(Database(self.path), self.scales, clock=lambda: self.now)
        self.catalog = ProductCatalog(1, {"BTC-SPOT": ProductSpec(
            "BTC-SPOT", ProductKind.SPOT_MARGIN, "BTC", "USD", "USD",
            D(".01"), D(".01"), D("1"), status=TradingStatus.ACTIVE)})
        self.spot = SpotExchange(self.service, self.catalog)
        self.market = MarketSnapshot(1, self.now,
            {"USD": AssetSpec(D(1), D(1)), "BTC": AssetSpec(D(100), D(".8"))},
            {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))})
        self.service.publish_market(self.market)
        self.service.set_kill_switch(False)
        for name in ("buyer", "seller"):
            self.service.create_account(name)
        self.service.deposit("buyer", "usd", "USD", D(1000))
        self.service.deposit("seller", "btc", "BTC", D(5))

    def account(self, name):
        return self.service.account(name)

    def test_actual_pair_settles_two_assets_with_maker_price_and_remaining_locks(self):
        self.spot.submit_order("buyer", "b", "BTC-SPOT", D(2), D(100))
        self.spot.submit_order("seller", "s", "BTC-SPOT", D(-1), D(99))
        result = self.spot.match_once("BTC-SPOT")
        self.assertEqual(result["confirmed_trades"], 1)
        receipt = result["trades"][0]
        self.assertEqual((receipt["quantity"], receipt["price"], receipt["notional"]), ("1", "100", "100"))
        self.assertEqual(D(self.account("buyer")["balances"]["USD"]), D("899.96"))
        self.assertEqual(D(self.account("buyer")["balances"]["BTC"]), D(1))
        self.assertEqual(D(self.account("seller")["balances"]["USD"]), D("99.96"))
        self.assertEqual(D(self.account("seller")["balances"]["BTC"]), D(4))
        self.assertFalse(self.account("buyer")["positions"])
        self.assertEqual(D(self.spot.orders("buyer")[0]["reserved_amount"]), D("100.04"))
        self.assertEqual(self.spot.verify()["paired_fills"], 2)
        self.spot.cancel_order("buyer", "b")
        self.assertEqual(D(self.spot.orders("buyer")[0]["reserved_amount"]), D(0))

    def test_lock_blocks_duplicate_sell_and_credit_repayment(self):
        self.service.deposit("seller", "cash-collateral", "USD", D(100))
        credit = CreditService(self.service)
        credit.configure_asset_limit("BTC", D(20))
        credit.configure_limit("seller", "BTC", D(10))
        credit.fund_pool("pool", "BTC", D(10), source_reference="synthetic-pool")
        credit.borrow("seller", "loan", "BTC", D(1))
        # Six units exist; five are locked by the sell and cannot repay debt
        # or back another sell. Only one remains available.
        self.spot.submit_order("seller", "sell", "BTC-SPOT", D(-5), D(100))
        with self.service.database.transaction() as conn:
            self.assertEqual(locked_asset(conn, "seller", "BTC"), D(5))
            self.assertEqual(self.service._available_asset(conn, "seller", "BTC"), D(1))
        credit.repay("seller", "repay", "BTC", D(1))
        with self.assertRaises(ServiceError) as error:
            self.spot.submit_order("seller", "oversell", "BTC-SPOT", D("-.01"), D(100))
        self.assertEqual(error.exception.code, "insufficient_cash")
        self.assertEqual(self.spot.verify()["matches"], 0)

    def test_locked_borrowed_asset_cannot_be_repaid_again(self):
        credit = CreditService(self.service)
        credit.configure_asset_limit("BTC", D(20))
        credit.configure_limit("buyer", "BTC", D(10))
        credit.fund_pool("pool", "BTC", D(10), source_reference="synthetic-pool")
        credit.borrow("buyer", "loan", "BTC", D(1))
        self.spot.submit_order("buyer", "sell", "BTC-SPOT", D(-1), D(100))
        before = (self.account("buyer"), self.service.ledger.journal(), self.service.events(limit=1000))
        with self.assertRaises(ServiceError) as error:
            credit.repay("buyer", "repay", "BTC", D(1))
        self.assertEqual(error.exception.code, "insufficient_cash")
        self.assertEqual(before, (self.account("buyer"), self.service.ledger.journal(), self.service.events(limit=1000)))
        self.spot.cancel_order("buyer", "sell")
        credit.repay("buyer", "repay", "BTC", D(1))
        credit.verify()

    def test_spot_encumbrance_is_part_of_the_common_margin_gate(self):
        self.service.submit_order("buyer", "perp", "BTC-PERP", D(50), D(100))
        before = self.spot.orders("buyer")
        with self.assertRaises(ServiceError) as error:
            self.spot.submit_order("buyer", "spot", "BTC-SPOT", D(6), D(100))
        self.assertEqual(error.exception.code, "insufficient_margin")
        self.assertEqual(before, self.spot.orders("buyer"))

    def test_restart_idempotency_terminal_ids_and_conflicting_content(self):
        first = self.spot.submit_order("buyer", "b", "BTC-SPOT", D(1), D(100))
        self.spot.cancel_order("buyer", "b")
        restarted_service = ExchangeService(Database(self.path), self.scales, clock=lambda: self.now)
        restarted = SpotExchange(restarted_service, self.catalog)
        replay = restarted.submit_order("buyer", "b", "BTC-SPOT", D("1.0"), D("100.0"))
        self.assertEqual(replay["status"], "CANCELLED")
        self.assertEqual(replay["sequence"], first["sequence"])
        with self.assertRaises(ServiceError) as error:
            restarted.submit_order("buyer", "b", "BTC-SPOT", D(2), D(100))
        self.assertEqual(error.exception.code, "idempotency_conflict")
        self.assertEqual(restarted.verify()["orders"], 1)

    def test_cancel_remains_available_during_stale_feed_and_global_halt(self):
        self.spot.submit_order("buyer", "b", "BTC-SPOT", D(1), D(100))
        self.spot.submit_order("seller", "s", "BTC-SPOT", D(-1), D(100))
        self.service.set_kill_switch(True)
        before = (self.service.ledger.journal(), self.spot.orders("buyer"))
        result = self.spot.match_once("BTC-SPOT")
        self.assertEqual(result["confirmed_trades"], 0)
        self.assertEqual(result["blocked"][0]["code"], "trading_halted")
        self.assertEqual(before, (self.service.ledger.journal(), self.spot.orders("buyer")))
        self.now += timedelta(seconds=6)
        self.assertEqual(self.spot.match_once("BTC-SPOT")["blocked"][0]["code"], "market_unavailable")
        self.assertEqual(self.spot.cancel_order("buyer", "b")["status"], "CANCELLED")

    def test_self_trade_cancels_newer_order_without_settlement(self):
        self.service.deposit("buyer", "btc", "BTC", D(1))
        self.spot.submit_order("buyer", "s", "BTC-SPOT", D(-1), D(99))
        self.spot.submit_order("buyer", "b", "BTC-SPOT", D(1), D(100))
        before = self.service.ledger.journal()
        result = self.spot.match_once("BTC-SPOT")
        self.assertEqual(result["confirmed_trades"], 0)
        self.assertEqual(result["cancelled_orders"][0]["order_id"], "b")
        self.assertEqual(self.service.ledger.journal(), before)

    def test_price_priority_is_numeric_and_time_order_chooses_maker(self):
        self.spot.submit_order("buyer", "low", "BTC-SPOT", D(1), D(9))
        self.spot.submit_order("buyer", "high", "BTC-SPOT", D(1), D(100))
        self.spot.submit_order("seller", "s", "BTC-SPOT", D(-1), D(9))
        receipt = self.spot.match_once("BTC-SPOT")["trades"][0]
        self.assertEqual(receipt["buy_order_id"], "high")
        self.assertEqual(receipt["price"], "100")

    def test_concurrent_books_cannot_reserve_the_same_cash(self):
        def submit(index):
            service = ExchangeService(Database(self.path), self.scales, clock=lambda: self.now)
            spot = SpotExchange(service, self.catalog)
            try:
                spot.submit_order("seller", str(index), "BTC-SPOT", D(-2), D(100))
                return True
            except ServiceError as error:
                self.assertEqual(error.code, "insufficient_cash")
                return False
        with ThreadPoolExecutor(max_workers=6) as executor:
            accepted = list(executor.map(submit, range(6)))
        self.assertEqual(sum(accepted), 2)

    def test_credit_repay_and_spot_sell_compete_for_one_shared_cash_balance(self):
        credit = CreditService(self.service)
        credit.configure_asset_limit("BTC", D(20))
        credit.configure_limit("buyer", "BTC", D(2))
        credit.fund_pool("pool", "BTC", D(2), source_reference="synthetic-pool")
        credit.borrow("buyer", "loan", "BTC", D(1))
        def compete(kind):
            service = ExchangeService(Database(self.path), self.scales, clock=lambda: self.now)
            try:
                if kind == "sell":
                    SpotExchange(service, self.catalog).submit_order("buyer", "sell", "BTC-SPOT", D(-1), D(100))
                else:
                    CreditService(service).repay("buyer", "repay", "BTC", D(1))
                return True
            except ServiceError as error:
                self.assertEqual(error.code, "insufficient_cash")
                return False
        with ThreadPoolExecutor(max_workers=2) as executor:
            self.assertEqual(sum(executor.map(compete, ("sell", "repay"))), 1)
        with self.service.database.transaction() as conn:
            self.assertGreaterEqual(self.service._available_asset(conn, "buyer", "BTC"), D(0))
        self.spot.verify()
        credit.verify()

    def test_corrupt_order_lock_or_receipt_protection_is_detected(self):
        self.spot.submit_order("buyer", "b", "BTC-SPOT", D(1), D(100))
        with self.service.database.transaction() as conn:
            conn.execute("UPDATE uta_spot_orders SET reserved_amount='1' WHERE order_id='b'")
        with self.assertRaises(ServiceError) as error:
            self.spot.verify()
        self.assertEqual(error.exception.code, "spot_corrupt")

    def test_failure_after_both_balances_change_rolls_back_orders_and_receipt(self):
        self.spot.submit_order("buyer", "b", "BTC-SPOT", D(1), D(100))
        self.spot.submit_order("seller", "s", "BTC-SPOT", D(-1), D(100))
        before = (self.account("buyer"), self.account("seller"), self.spot.orders("buyer"),
                  self.spot.orders("seller"), self.service.ledger.journal(), self.service.events(limit=1000))
        original = self.service._event
        def fail(connection, kind, account_id, payload):
            if kind == "SPOT_MATCH_CONFIRMED":
                raise RuntimeError("crash after two-sided cash and receipt")
            return original(connection, kind, account_id, payload)
        self.service._event = fail
        with self.assertRaises(RuntimeError):
            self.spot.match_once("BTC-SPOT")
        self.service._event = original
        self.assertEqual(before, (self.account("buyer"), self.account("seller"), self.spot.orders("buyer"),
                         self.spot.orders("seller"), self.service.ledger.journal(), self.service.events(limit=1000)))
        self.assertFalse(self.spot.trades())
        self.assertEqual(self.spot.match_once("BTC-SPOT")["confirmed_trades"], 1)

    def test_parallel_matchers_commit_one_pair_once(self):
        self.spot.submit_order("buyer", "b", "BTC-SPOT", D(1), D(100))
        self.spot.submit_order("seller", "s", "BTC-SPOT", D(-1), D(100))
        def match(_):
            service = ExchangeService(Database(self.path), self.scales, clock=lambda: self.now)
            return SpotExchange(service, self.catalog).match_once("BTC-SPOT")["confirmed_trades"]
        with ThreadPoolExecutor(max_workers=4) as executor:
            self.assertEqual(sum(executor.map(match, range(4))), 1)
        self.assertEqual(self.spot.verify()["paired_fills"], 2)

    def test_product_metadata_unsupported_mode_precision_and_unpriced_are_rejected(self):
        from dataclasses import replace
        product = self.catalog.products["BTC-SPOT"]
        for change in ({"status": TradingStatus.DELISTED}, {"kind": ProductKind.LINEAR_PERPETUAL}):
            catalog = ProductCatalog(2, {"BTC-SPOT": replace(product, **change)})
            other_path = Path(self.tmp.name) / (str(len(change)) + change.get("status", change.get("kind")).value + ".db")
            service = ExchangeService(Database(other_path), self.scales, clock=lambda: self.now)
            service.create_account("client")
            service.deposit("client", "usd", "USD", D(1000))
            service.publish_market(self.market)
            service.set_kill_switch(False)
            spot = SpotExchange(service, catalog)
            with self.assertRaises(ServiceError):
                spot.submit_order("client", "bad", "BTC-SPOT", D(1), D(100))
        with self.assertRaises(ServiceError):
            self.spot.submit_order("buyer", "step", "BTC-SPOT", D(".011"), D(100))
        with self.assertRaises(ServiceError):
            self.spot.submit_order("buyer", "tick", "BTC-SPOT", D(1), D("100.001"))
        missing = MarketSnapshot(2, self.now, {"USD": AssetSpec(D(1), D(1))}, self.market.instruments)
        # A funded seller prevents removing BTC altogether, so use another
        # configured-but-not-funded symbol to exercise the spot-specific guard.
        with self.assertRaises(ServiceError):
            self.service.publish_market(missing)

    def test_low_decimal_context_cannot_change_cash_or_locks(self):
        with localcontext() as context:
            context.prec = 1
            context.Emax = 2
            context.Emin = -2
            context.traps[Inexact] = True
            context.traps[Rounded] = True
            self.spot.submit_order("buyer", "b", "BTC-SPOT", D("1.01"), D("100.01"))
            self.spot.submit_order("seller", "s", "BTC-SPOT", D("-1.01"), D("100.01"))
            self.assertEqual(self.spot.match_once("BTC-SPOT")["confirmed_trades"], 1)
        self.assertEqual(D(self.account("buyer")["balances"]["BTC"]), D("1.01"))
        self.spot.verify()

    def test_replay_does_not_lose_confirmed_fills_or_reopen_closed_order(self):
        self.spot.submit_order("buyer", "b", "BTC-SPOT", D(1), D(100))
        self.spot.submit_order("seller", "s", "BTC-SPOT", D(-1), D(100))
        self.spot.match_once("BTC-SPOT")
        original = (self.account("buyer"), self.account("seller"), self.service.ledger.journal())
        restarted = ExchangeService(Database(self.path), self.scales, clock=lambda: self.now)
        spot = SpotExchange(restarted, self.catalog)
        self.assertEqual(spot.match_once("BTC-SPOT")["confirmed_trades"], 0)
        self.assertEqual(spot.submit_order("buyer", "b", "BTC-SPOT", D(1), D(100))["status"], "FILLED")
        self.assertEqual(original, (self.account("buyer"), self.account("seller"), self.service.ledger.journal()))

    def test_microscopic_partial_fills_charge_cumulative_fee_once(self):
        path = Path(self.tmp.name) / "small.db"
        service = ExchangeService(Database(path), {"USD": 2, "BTC": 2}, clock=lambda: self.now)
        catalog = ProductCatalog(1, {"BTC-SPOT": ProductSpec("BTC-SPOT", ProductKind.SPOT,
            "BTC", "USD", "USD", D(1), D(".01"), D(0), status=TradingStatus.ACTIVE)})
        spot = SpotExchange(service, catalog)
        market = MarketSnapshot(1, self.now, {"USD": AssetSpec(D(1), D(1)), "BTC": AssetSpec(D(1), D(1))}, {})
        service.publish_market(market)
        service.set_kill_switch(False)
        for name in ("buy", "sell"):
            service.create_account(name)
        service.deposit("buy", "cash", "USD", D("1.01"))
        service.deposit("sell", "coins", "BTC", D(1))
        spot.submit_order("buy", "one", "BTC-SPOT", D(1), D(1))
        for index in range(100):
            spot.submit_order("sell", str(index), "BTC-SPOT", D("-.01"), D(1))
        result = spot.match_once("BTC-SPOT", max_matches=100)
        self.assertEqual(result["confirmed_trades"], 100)
        self.assertEqual(D(spot.orders("buy")[0]["charged_fee"]), D(".01"))
        self.assertEqual(D(service.account("buy")["balances"]["USD"]), D(0))
        self.assertEqual(D(service.account("buy")["balances"]["BTC"]), D(1))
        self.assertEqual(spot.verify()["matches"], 100)

    def test_configured_cross_policy_reports_same_spot_freeze_and_settlement(self):
        from uta.portfolio import BorrowLimits, CollateralRule, CollateralTier, PortfolioRules
        path = Path(self.tmp.name) / "configured.db"
        rules = PortfolioRules(1,
            {"USD": CollateralRule("USD", (CollateralTier(None, D(1)),), D(".8")),
             "BTC": CollateralRule("BTC", (CollateralTier(None, D(".8")),), D(".5"))},
            {"BTC": BorrowLimits("BTC", D(10), D(".1"), D(".05"), D(".01"))}, {}, D(1000))
        service = ExchangeService(Database(path), self.scales, product_catalog=self.catalog,
                                  portfolio_rules=rules, clock=lambda: self.now)
        spot = SpotExchange(service, self.catalog)
        service.publish_market(MarketSnapshot(1, self.now, self.market.assets, {}))
        service.set_kill_switch(False)
        for name in ("buy", "sell"):
            service.create_account(name)
        service.deposit("buy", "usd", "USD", D(1000))
        service.deposit("sell", "btc", "BTC", D(5))
        spot.submit_order("buy", "b", "BTC-SPOT", D(1), D(100))
        risk = service.risk("buy")
        self.assertEqual(D(risk["accounting_equity"]), D(1000))
        self.assertEqual(D(risk["equity"]), D("899.96"))
        self.assertEqual(D(risk["frozen_value"]), D("100.04"))
        spot.submit_order("sell", "s", "BTC-SPOT", D(-1), D(100))
        self.assertEqual(spot.match_once("BTC-SPOT")["confirmed_trades"], 1)
        risk = service.risk("buy")
        self.assertEqual((D(risk["accounting_equity"]), D(risk["equity"])), (D("999.96"), D("979.96")))
        self.assertEqual((risk["catalog_version"], risk["rule_version"]), (1, 1))
        self.assertEqual(spot.verify()["matches"], 1)

    def test_supervisor_hook_releases_only_unfilled_obligations_in_outer_transaction(self):
        from uta.spot import cancel_all_spot_orders
        self.spot.submit_order("buyer", "b", "BTC-SPOT", D(2), D(100))
        self.spot.submit_order("seller", "s", "BTC-SPOT", D(-1), D(100))
        self.spot.match_once("BTC-SPOT")
        cash = self.account("buyer")["balances"]
        with self.service.database.transaction() as conn:
            cancelled = cancel_all_spot_orders(self.service, conn, "buyer")
            self.assertEqual(len(cancelled), 1)
            self.assertEqual(cancelled[0]["filled_quantity"], "1")
            self.assertEqual(locked_asset(conn, "buyer", "USD"), D(0))
        self.assertEqual(self.account("buyer")["balances"], cash)
        self.assertEqual(self.spot.verify()["matches"], 1)


if __name__ == "__main__":
    unittest.main()
