from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from uta.credit import CreditService
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.portfolio import BorrowLimits, CollateralRule, CollateralTier, LinearMarginRule, PortfolioRules
from uta.products import ProductCatalog, ProductKind, ProductSpec, TradingStatus
from uta.service import ExchangeService, ServiceError
from uta.spot import SpotExchange
from uta.storage import Database


class CreditSupervisorTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "credit-risk.sqlite3"
        self.now = datetime(2026, 11, 14, tzinfo=timezone.utc)
        common = dict(underlying="BTC", quote_asset="USD", settlement_asset="USD",
                      price_tick=D("0.01"), quantity_step=D("0.01"), min_notional=D("1"),
                      status=TradingStatus.ACTIVE)
        self.catalog = ProductCatalog(1, {
            "BTC-PERP": ProductSpec("BTC-PERP", ProductKind.LINEAR_PERPETUAL, **common),
            "BTC-SPOT": ProductSpec("BTC-SPOT", ProductKind.SPOT_MARGIN, **common)})
        self.rules = PortfolioRules(1,
            {"USD": CollateralRule("USD", (CollateralTier(None, D(1)),), D("0.5")),
             "BTC": CollateralRule("BTC", (CollateralTier(None, D("0.8")),), D("0.5"))},
            {"BTC": BorrowLimits("BTC", D(100), D("0.2"), D("0.1"), D("0.01"))},
            {"tier-1": LinearMarginRule("tier-1", D("0.1"), D("0.05"))}, D(100000))
        self.exchange = self.reopen()
        self.exchange.create_account("alice")
        self.exchange.deposit("alice", "cash", "USD", D(100))
        self.publish()
        self.exchange.set_kill_switch(False)
        self.credit = CreditService(self.exchange)
        self.credit.configure_asset_limit("BTC", D(100))
        self.credit.configure_limit("alice", "BTC", D(10))
        self.credit.fund_pool("capital", "BTC", D(50), source_reference="synthetic:credit-risk-pool")
        self.credit.borrow("alice", "borrow", "BTC", D(1))

    def reopen(self):
        return ExchangeService(Database(self.path), {"USD": 8, "BTC": 8},
                               product_catalog=self.catalog, portfolio_rules=self.rules,
                               fee_rate=D(0), clock=lambda: self.now)

    def publish(self, version=1, price="100"):
        self.exchange.publish_market(MarketSnapshot(version, self.now,
            {"USD": AssetSpec(D(1), D(1)), "BTC": AssetSpec(D(price), D("0.8"))},
            {"BTC-PERP": InstrumentSpec(D(100), D("0.1"), D("0.05"))}))

    def assert_code(self, code, call, *args, **kwargs):
        with self.assertRaises(ServiceError) as error:
            call(*args, **kwargs)
        self.assertEqual(error.exception.code, code)

    def test_positive_equity_loan_distress_blocks_and_cancels_without_fake_settlement(self):
        self.exchange.submit_order("alice", "pending", "BTC-PERP", D(1), D(100))
        self.publish(2, "400")
        before = self.exchange.account("alice"), self.exchange.ledger.journal()
        result = self.exchange.supervise_account("alice")
        self.assertEqual((result["equity"], result["maintenance_margin"]), ("20", "40"))
        self.assertEqual(result["state"], "BLOCKED")
        self.assertEqual(result["reason"], "loan_liquidation_adapter_required")
        self.assertEqual(result["created_orders"], [])
        self.assertEqual([order["order_id"] for order in result["cancelled_orders"]], ["pending"])
        self.assertEqual(self.exchange.account("alice")["balances"], before[0]["balances"])
        self.assertEqual(self.exchange.account("alice")["liabilities"], before[0]["liabilities"])
        self.assertEqual(self.exchange.ledger.journal(), before[1])
        self.assert_code("account_frozen", self.credit.borrow, "alice", "another", "BTC", D("0.01"))
        self.assert_code("account_frozen", self.exchange.submit_order, "alice", "risk", "BTC-PERP", D(1), D(100))
        events = self.exchange.events(limit=1000)
        self.assertEqual(events[-1]["payload"]["reason"], "loan_liquidation_adapter_required")
        repeated = self.reopen().supervise_account("alice")
        self.assertEqual(repeated["state"], "BLOCKED")
        self.assertEqual(repeated["cycle"], result["cycle"])
        self.assertEqual(repeated["created_orders"], [])
        self.assertEqual(self.exchange.events(limit=1000), events)

    def test_zero_equity_with_debt_is_blocked_but_empty_account_remains_normal(self):
        self.publish(2, "500")
        result = self.exchange.supervise_account("alice")
        self.assertEqual((result["equity"], result["state"]), ("0", "BLOCKED"))
        self.exchange.create_account("empty")
        self.assertEqual(self.exchange.supervise_account("empty")["state"], "NORMAL")

    def test_negative_equity_is_bankrupt_and_real_repayment_can_resolve_it(self):
        self.publish(2, "600")
        result = self.exchange.supervise_account("alice")
        self.assertEqual((result["equity"], result["state"]), ("-20", "BANKRUPT"))
        self.credit.repay("alice", "repay", "BTC", D(1))
        recovered = self.exchange.supervise_account("alice")
        self.assertEqual((recovered["equity"], recovered["state"]), ("100", "NORMAL"))

    def test_loan_recovery_obeys_maintenance_hysteresis(self):
        self.publish(2, "400")
        self.exchange.supervise_account("alice")
        self.exchange.deposit("alice", "atmm", "USD", D(20))
        self.assertEqual(self.exchange.supervise_account("alice")["state"], "BLOCKED")
        self.exchange.deposit("alice", "atbuffer", "USD", D(4))
        self.assertEqual(self.exchange.supervise_account("alice")["state"], "BLOCKED")
        self.exchange.deposit("alice", "overbuffer", "USD", D("0.01"))
        self.assertEqual(self.exchange.supervise_account("alice")["state"], "NORMAL")
        with self.exchange._transaction() as connection:
            self.exchange._require_exposure_allowed(connection, "alice")

    def test_release_spot_locks_then_revalue_prevents_false_loan_liquidation(self):
        spot = SpotExchange(self.exchange, self.catalog)
        spot.submit_order("alice", "sell", "BTC-SPOT", D("-0.5"), D(100))
        self.publish(2, "300")
        self.assertEqual(self.exchange.risk("alice")["equity"], "-80")
        before = self.exchange.account("alice"), self.exchange.ledger.journal()
        result = self.exchange.supervise_account("alice")
        self.assertEqual((result["state"], result["equity"], result["maintenance_margin"]), ("NORMAL", "40", "30"))
        self.assertEqual([order["order_id"] for order in result["cancelled_spot_orders"]], ["sell"])
        self.assertEqual(result["created_orders"], [])
        self.assertEqual(spot.orders("alice")[0]["status"], "CANCELLED")
        self.assertEqual(spot.orders("alice")[0]["reserved_amount"], "0")
        self.assertEqual(self.exchange.account("alice")["balances"], before[0]["balances"])
        self.assertEqual(self.exchange.ledger.journal(), before[1])

    def test_release_spot_locks_before_deciding_on_existing_perpetual_position(self):
        self.exchange.submit_order("alice", "open", "BTC-PERP", D(1), D(100))
        self.exchange.apply_fill("alice", "open", "openfill", D(1), D(100))
        spot = SpotExchange(self.exchange, self.catalog)
        spot.submit_order("alice", "sell", "BTC-SPOT", D("-0.3"), D(100))
        self.publish(2, "300")
        self.assertEqual(self.exchange.risk("alice")["equity"], "-32")
        result = self.exchange.supervise_account("alice")
        self.assertEqual((result["state"], result["equity"], result["maintenance_margin"]), ("NORMAL", "40", "35"))
        self.assertEqual(result["created_orders"], [])
        self.assertEqual(self.exchange.account("alice")["positions"]["BTC-PERP"]["quantity"], "1")

    def test_true_loan_distress_remains_blocked_after_spot_cancellation(self):
        spot = SpotExchange(self.exchange, self.catalog)
        spot.submit_order("alice", "sell", "BTC-SPOT", D("-0.3"), D(100))
        self.publish(2, "400")
        result = self.exchange.supervise_account("alice")
        self.assertEqual(result["state"], "BLOCKED")
        self.assertEqual(result["reason"], "loan_liquidation_adapter_required")
        self.assertEqual(len(result["cancelled_spot_orders"]), 1)
        self.assertEqual(result["created_orders"], [])

    def test_spot_cancel_and_supervisor_state_share_one_rollback_boundary(self):
        spot = SpotExchange(self.exchange, self.catalog)
        spot.submit_order("alice", "sell", "BTC-SPOT", D("-0.3"), D(100))
        self.publish(2, "400")
        before = spot.orders("alice"), self.exchange.account("alice"), self.exchange.events(limit=1000)
        with patch.object(self.exchange, "_liquidation_state", side_effect=RuntimeError("injected")):
            with self.assertRaisesRegex(RuntimeError, "injected"):
                self.exchange.supervise_account("alice")
        self.assertEqual((spot.orders("alice"), self.exchange.account("alice"), self.exchange.events(limit=1000)), before)

    def test_single_order_requery_preserves_original_id_during_market_outage(self):
        admitted = self.exchange.submit_order("alice", "client:42", "BTC-PERP", D(1), D(100))
        self.now += timedelta(seconds=6)
        self.assertEqual(self.exchange.order("alice", "client:42"), admitted)
        self.assert_code("order_not_found", self.exchange.order, "alice", "unknown")
        self.exchange.cancel_order("alice", "client:42")
        self.assertEqual(self.exchange.order("alice", "client:42")["status"], "CANCELLED")


if __name__ == "__main__":
    unittest.main()
