from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D, Inexact, localcontext
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from uta.credit import CreditService
from uta.cutover import ClassicImporter
from uta.market import MarketSnapshot
from uta.migration import build_shadow
from uta.models import AssetSpec, InstrumentSpec
from uta.portfolio import BorrowLimits, CollateralRule, CollateralTier, LinearMarginRule, PortfolioRules
from uta.products import ProductCatalog, ProductKind, ProductSpec, TradingStatus
from uta.service import ExchangeService, ServiceError
from uta.storage import Database


class ConfiguredCutoverTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.now = datetime(2026, 11, 14, tzinfo=timezone.utc)
        self.product = ProductSpec("X", ProductKind.LINEAR_PERPETUAL, "BTC", "USD", "USD",
                                   D(".01"), D(".01"), D(1), status=TradingStatus.ACTIVE)
        self.rules = PortfolioRules(13, {
            "USD": CollateralRule("USD", (CollateralTier(None, D(1)),), D(".5")),
            "BTC": CollateralRule("BTC", (CollateralTier(D(100), D(".9")), CollateralTier(None, D(".5"))), D(".5"))},
            {"USD": BorrowLimits("USD", D(500), D(".2"), D(".1"), D(".01"))},
            {"tier-1": LinearMarginRule("tier-1", D(".1"), D(".05"))}, D(500))

    def service(self, name="main", product=None, *, catalog=None):
        catalog = catalog or ProductCatalog(7, {"X": product or self.product})
        service = ExchangeService(Database(Path(self.directory.name) / (name + ".sqlite3")), {"USD": 8, "BTC": 8},
                                  clock=lambda: self.now, product_catalog=catalog, portfolio_rules=self.rules)
        service.publish_market(MarketSnapshot(1, self.now,
            {"USD": AssetSpec(D(1), D(1)), "BTC": AssetSpec(D(200), D(".8"))},
            {"X": InstrumentSpec(D(110), D(".1"), D(".05"))}))
        service.set_kill_switch(False)
        return service

    def source(self, principal="100"):
        return build_shadow({"account_id": "classic", "version": 4, "captured_at": self.now.isoformat(),
            "compartments": {
                "spot": {"balances": [{"asset": "USD", "free": "1000", "locked": "0", "borrowed": "0", "interest": "0"},
                                      {"asset": "BTC", "free": "2", "locked": "0", "borrowed": "0", "interest": "0"}]},
                "margin": {"balances": [{"asset": "USD", "free": "0", "locked": "0", "borrowed": principal, "interest": "1"}]},
                "futures": {"balances": [], "positions": [{"symbol": "X", "quantity": "2", "entry_price": "100"}]}}},
            now=self.now)

    def import_it(self, service, *, shadow=None):
        return ClassicImporter(service).import_shadow(shadow or self.source(), "cutover", source_fence_reference="classic:fenced-epoch-4",
            open_orders=[], conditional_orders=[], pending_settlements=[], transfers_in_flight=[])

    def financial_state(self, service):
        with service.database.transaction() as conn:
            return {table: [tuple(row) for row in conn.execute(f"SELECT * FROM {table}")]
                    for table in ("uta_accounts", "uta_positions", "uta_liabilities", "uta_events", "ledger_events", "ledger_balances")}

    def test_versioned_loan_margin_can_differ_from_legacy_without_discarding_source_finances(self):
        service = self.service()
        receipt = self.import_it(service)
        risk = receipt["risk_at_import"]
        # Independent hand calculation: gross accounting 1000 + 400 - 101 +20.
        self.assertEqual(risk["accounting_equity"], "1319")
        # BTC collateral: first100*.9 + remaining300*.5 =240, not400*.8.
        self.assertEqual(risk["equity"], "1159")
        self.assertEqual(risk["initial_margin"], "42.2")  # 22 linear +101*.2 borrow.
        self.assertEqual(risk["maintenance_margin"], "21.1")
        self.assertEqual((risk["rule_version"], risk["catalog_version"], risk["risk_mode"]), (13, 7, "phase1_cross"))
        self.assertEqual(receipt["reconciliation_basis"], "configured_gross_accounting_equity")
        self.assertEqual(service.account("classic")["balances"], {"BTC": "2", "USD": "1000"})
        self.assertEqual(ClassicImporter(service).verify(), 1)

    def test_imported_cross_debt_repayment_preserves_cashflow_and_reduces_configured_loan_margin(self):
        service = self.service()
        self.import_it(service)
        credit = CreditService(service)
        repayment = credit.repay("classic", "repay", "USD", D(101))
        self.assertEqual((repayment["principal_repaid"], repayment["interest_repaid"]), ("100", "1"))
        account, risk = service.account("classic"), service.risk("classic")
        self.assertEqual(account["balances"]["USD"], "899")
        self.assertEqual((risk["accounting_equity"], risk["equity"], risk["initial_margin"], risk["maintenance_margin"]),
                         ("1319", "1159", "22", "11"))
        self.assertEqual(credit.verify()["nonzero_liabilities"], 0)
        self.assertEqual(ClassicImporter(service).verify(), 1)

    def test_existing_debt_above_new_borrow_limit_is_retained_frozen_without_netting(self):
        service = self.service()
        receipt = self.import_it(service, shadow=self.source("2000"))
        self.assertEqual(receipt["liabilities"]["USD"], {"principal": "2000", "interest": "1"})
        self.assertEqual(receipt["assets"]["USD"], "1000")
        self.assertEqual(receipt["risk_at_import"]["accounting_equity"], "-581")
        self.assertEqual(receipt["risk_at_import"]["equity"], "-741")
        self.assertEqual(receipt["risk_at_import"]["borrowable"], {"USD": "0"})
        self.assertEqual(receipt["state"], "BLOCKED")
        self.assertEqual(ClassicImporter(service).verify(), 1)

    def test_same_market_symbol_cannot_smuggle_option_inverse_spot_or_multiplier_positions(self):
        unsupported = (
            replace(self.product, kind=ProductKind.OPTION, expiry=self.now + timedelta(days=30)),
            replace(self.product, kind=ProductKind.INVERSE_PERPETUAL),
            replace(self.product, kind=ProductKind.DATED_FUTURE, expiry=self.now + timedelta(days=30)),
            replace(self.product, kind=ProductKind.SPOT),
            replace(self.product, kind=ProductKind.SPOT_MARGIN),
            replace(self.product, multiplier=D(2)),
            replace(self.product, settlement_asset="USDT"),
            replace(self.product, quote_asset="USDT"),
        )
        for index, product in enumerate(unsupported):
            with self.subTest(product=product):
                service = self.service(str(index), product)
                before = self.financial_state(service)
                with self.assertRaises(ServiceError) as caught:
                    self.import_it(service)
                self.assertEqual(caught.exception.code, "migration_product")
                self.assertEqual(self.financial_state(service), before)
                self.assertEqual(ClassicImporter(service).verify(), 0)

    def test_unlisted_symbol_is_rejected_even_if_market_retains_a_price(self):
        catalog = ProductCatalog(7, {"OTHER": replace(self.product, symbol="OTHER")})
        service = self.service(catalog=catalog)
        before = self.financial_state(service)
        with self.assertRaises(ServiceError) as caught:
            self.import_it(service)
        self.assertEqual(caught.exception.code, "migration_product")
        self.assertEqual(self.financial_state(service), before)

    def test_existing_halted_supported_exposure_is_imported_frozen_and_can_be_valued(self):
        service = self.service(product=replace(self.product, status=TradingStatus.HALTED))
        receipt = self.import_it(service)
        self.assertEqual(receipt["state"], "BLOCKED")
        self.assertEqual(service.risk("classic")["accounting_equity"], "1319")
        self.assertEqual(service.account("classic")["positions"]["X"]["quantity"], "2")
        with self.assertRaises(ServiceError):
            service.submit_order("classic", "new", "X", D(1), D(110))
        self.assertEqual(ClassicImporter(service).verify(), 1)

    def test_restart_and_expired_retry_keep_original_rules_and_receipt(self):
        service = self.service()
        shadow = self.source()
        receipt = self.import_it(service, shadow=shadow)
        self.now += timedelta(seconds=60)
        restarted = ExchangeService(Database(service.database.path), {"USD": 8, "BTC": 8}, clock=lambda: self.now,
                                    product_catalog=service.product_catalog, portfolio_rules=service.portfolio_rules)
        self.assertEqual(self.import_it(restarted, shadow=shadow), receipt)
        self.assertEqual(ClassicImporter(restarted).status("cutover")["import"]["risk_at_import"]["rule_version"], 13)
        self.assertEqual(ClassicImporter(restarted).verify(), 1)

    def test_configured_reconciliation_is_independent_of_decimal_context(self):
        service = self.service()
        with localcontext() as context:
            context.prec = 1
            context.Emax = 2
            context.traps[Inexact] = True
            receipt = self.import_it(service)
            self.assertEqual(receipt["risk_at_import"]["accounting_equity"], "1319")
            self.assertEqual(ClassicImporter(service).verify(), 1)


if __name__ == "__main__":
    unittest.main()
