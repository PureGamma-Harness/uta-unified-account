from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from uta.ledger import Posting
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.portfolio import BorrowLimits, CollateralRule, CollateralTier, LinearMarginRule, PortfolioRules
from uta.products import ProductCatalog, ProductKind, ProductSpec, TradingStatus
from uta.service import ExchangeService, ServiceError
from uta.storage import Database


class ServiceCatalogTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "exchange.db"
        self.now = datetime(2026, 11, 14, 12, tzinfo=timezone.utc)
        common = dict(underlying="BTC", quote_asset="USD", settlement_asset="USD", price_tick=D("0.01"),
                      quantity_step=D("0.01"), min_notional=D("10"), status=TradingStatus.ACTIVE)
        products = {"X": ProductSpec("X", ProductKind.LINEAR_PERPETUAL, **common),
                    "SPOT": ProductSpec("SPOT", ProductKind.SPOT, **common),
                    "INV": ProductSpec("INV", ProductKind.INVERSE_PERPETUAL, **common),
                    "FUT": ProductSpec("FUT", ProductKind.DATED_FUTURE, expiry=datetime(2027, 1, 1, tzinfo=timezone.utc), **common),
                    "OPT": ProductSpec("OPT", ProductKind.OPTION, expiry=datetime(2027, 1, 1, tzinfo=timezone.utc), **common)}
        products["MULT"] = replace(products["X"], symbol="MULT", multiplier=D("2"))
        products["HALT"] = replace(products["X"], symbol="HALT", status=TradingStatus.HALTED)
        products["RED"] = replace(products["X"], symbol="RED", status=TradingStatus.REDUCE_ONLY)
        self.catalog = ProductCatalog(4, products)
        self.rules = PortfolioRules(3,
            {"USD": CollateralRule("USD", (CollateralTier(None, D("1")),), D("0.5")),
             "BTC": CollateralRule("BTC", (CollateralTier(None, D("0.8")),), D("0.5"))},
            {"USD": BorrowLimits("USD", D("1000"), D("0.2"), D("0.1"), D("0.01"))},
            {"tier-1": LinearMarginRule("tier-1", D("0.1"), D("0.05"))}, D("500"))

    def create(self, *, configured=True, catalog=None, rules=None, path=None):
        kwargs = {"product_catalog": catalog or self.catalog, "portfolio_rules": rules or self.rules} if configured else {}
        return ExchangeService(Database(path or self.path), {"USD": 8, "BTC": 8},
                               clock=lambda: self.now, fee_rate=D("0"), **kwargs)

    def market(self, version=1):
        return MarketSnapshot(version, self.now,
                              {"USD": AssetSpec(D("1"), D("1")), "BTC": AssetSpec(D("100"), D("0.8"))},
                              {symbol: InstrumentSpec(D("100"), D("0.1"), D("0.05")) for symbol in self.catalog.products})

    def funded(self, **kwargs):
        service = self.create(**kwargs)
        service.publish_market(self.market())
        service.create_account("alice")
        service.deposit("alice", "funds", "USD", D("1000"))
        service.set_kill_switch(False)
        return service

    def assert_code(self, code, call, *args, **kwargs):
        with self.assertRaises(ServiceError) as error:
            call(*args, **kwargs)
        self.assertEqual(error.exception.code, code)

    def test_pair_required_and_canonical_persisted_policy_cannot_downgrade(self):
        for kwargs in ({"product_catalog": self.catalog}, {"portfolio_rules": self.rules}):
            with self.assertRaises(ServiceError):
                ExchangeService(Database(self.path), {"USD": 8}, **kwargs)
        self.funded()
        self.create()  # Identical configuration can restart.
        equivalent = replace(self.rules, max_total_debt=D("500.000"))
        self.create(rules=equivalent)
        self.assert_code("configuration_conflict", self.create, configured=False)
        self.assert_code("configuration_conflict", self.create, rules=replace(self.rules, version=4))
        self.assert_code("configuration_conflict", self.create, catalog=replace(self.catalog, version=5))

    def test_legacy_mode_is_explicit_and_cannot_silently_activate_phase_one(self):
        service = self.funded(configured=False)
        self.assertEqual(service.risk("alice")["risk_mode"], "legacy_reference")
        self.assert_code("configuration_conflict", self.create)

    def test_live_risk_uses_gross_principal_interest_and_one_rule_version(self):
        service = self.funded()
        service.deposit("alice", "btc", "BTC", D("1"))
        service.submit_order("alice", "open", "X", D("2"), D("100"))
        service.apply_fill("alice", "open", "fill", D("2"), D("100"))
        with service.database.transaction() as connection:
            connection.execute("INSERT INTO uta_liabilities VALUES ('alice','USD','100','1')")
        risk = service.risk("alice")
        expected = {"accounting_equity": "999", "risk_equity": "979", "equity": "979", "loan_value": "540",
                    "principal_value": "100", "interest_value": "1", "initial_margin": "40.2", "maintenance_margin": "20.1"}
        for name, value in expected.items():
            self.assertEqual(D(risk[name]), D(value), name)
        self.assertEqual(risk["borrowable"], {"USD": "399"})
        self.assertEqual((risk["rule_version"], risk["catalog_version"]), (3, 4))
        rejected_market = replace(self.market(2), instruments={"X": InstrumentSpec(D("100"), D("0.2"), D("0.05"))})
        self.assert_code("margin_rule_conflict", service.publish_market, rejected_market)
        with self.assertRaises(AttributeError):
            service.portfolio_rules = replace(self.rules, version=4)

    def test_perpetual_execution_never_treats_spot_inverse_options_or_multiplier_as_linear(self):
        service = self.funded()
        before = service.account("alice"), service.events(limit=1000)
        for symbol in ("SPOT", "INV", "FUT", "OPT", "MULT", "HALT", "RED"):
            with self.subTest(symbol=symbol), self.assertRaises(ServiceError):
                service.submit_order("alice", f"bad-{symbol}", symbol, D("1"), D("100"))
        self.assertEqual((service.account("alice"), service.events(limit=1000)), before)

    def test_tick_step_minimum_and_partial_fill_dust_gate_real_execution(self):
        service = self.funded()
        for order_id, quantity, price in (("step", "0.101", "100"), ("tick", "0.1", "99.999"), ("min", "0.09", "100")):
            self.assert_code("product_rejected", service.submit_order, "alice", order_id, "X", D(quantity), D(price))
        service.submit_order("alice", "valid", "X", D("0.1"), D("100"))
        self.assert_code("product_rejected", service.apply_fill, "alice", "valid", "badstep", D("0.005"), D("100"))
        self.assert_code("product_rejected", service.apply_fill, "alice", "valid", "badtick", D("0.01"), D("99.999"))
        # One-dollar executions are below order min_notional=10 but are valid
        # parts of the already-admitted ten-dollar order.
        for index in range(10):
            service.apply_fill("alice", "valid", f"good{index}", D("0.01"), D("100"))
        self.assertEqual(service.orders("alice")[0]["status"], "FILLED")
        self.assertEqual(service.risk("alice")["rule_version"], 3)

    def test_existing_halted_order_cannot_fill_and_reduce_only_remains_strict(self):
        service = self.funded()
        with service.database.transaction() as connection:
            # Restored legacy order fixtures exercise fill-side gates directly.
            connection.execute("INSERT INTO uta_orders(account_id,order_id,symbol,quantity,limit_price,reduce_only,filled_quantity,status,version,created_at) VALUES ('alice','oldhalt','HALT','1','100',0,'0','OPEN',1,?)", (self.now.isoformat(),))
            connection.execute("INSERT INTO uta_positions VALUES ('alice','RED','1','100')")
        self.assert_code("product_rejected", service.apply_fill, "alice", "oldhalt", "no", D("1"), D("100"))
        self.assert_code("reduce_only_violation", service.submit_order, "alice", "oversize", "RED", D("-2"), D("100"), reduce_only=True)
        service.submit_order("alice", "close", "RED", D("-1"), D("100"), reduce_only=True)
        service.apply_fill("alice", "close", "yes", D("-1"), D("100"))
        self.assertNotIn("RED", service.account("alice")["positions"])
        service.cancel_order("alice", "oldhalt")

    def test_negative_settled_cash_remains_visible_without_fabricating_loan_principal(self):
        service = self.funded()
        service.ledger.post("loss", [Posting("customer:alice", "USD", D("-1020")), Posting("system:test", "USD", D("1020"))])
        risk = service.risk("alice")
        self.assertEqual((risk["equity"], risk["accounting_equity"], risk["cash_deficit_value"], risk["principal_value"]),
                         ("-20", "-20", "20", "0"))
        self.assertEqual(risk["status"], "LIQUIDATION")
        self.assertEqual(service.supervise_account("alice")["state"], "BANKRUPT")

    def test_shared_spot_locks_reduce_available_cash_and_risk_not_gross_accounting(self):
        service = self.funded()
        service.deposit("alice", "btc", "BTC", D("1"))
        with service.database.transaction() as connection:
            connection.execute("CREATE TABLE uta_spot_orders(account_id TEXT,reserved_asset TEXT,reserved_amount TEXT,status TEXT)")
            connection.executemany("INSERT INTO uta_spot_orders VALUES ('alice',?,?,'OPEN')", [("USD", "30"), ("BTC", "0.1")])
            self.assertEqual(service._available_asset(connection, "alice", "USD"), D("970"))
            self.assertEqual(service._available_asset(connection, "alice", "BTC"), D("0.9"))
        risk = service.risk("alice")
        self.assertEqual((risk["accounting_equity"], risk["equity"], risk["frozen_value"]), ("1100", "1042", "40"))

    def test_corrupt_or_missing_kill_switch_blocks_new_and_reducing_execution(self):
        for index, value in enumerate(("garbage", "TRUE", "", "0", None)):
            with self.subTest(value=value):
                service = self.funded(path=Path(self.directory.name) / f"bad-{index}.db")
                service.submit_order("alice", "open", "X", D("1"), D("100"))
                service.apply_fill("alice", "open", "initial", D("1"), D("100"))
                service.submit_order("alice", "pending", "X", D("1"), D("100"))
                service.submit_order("alice", "reduce", "X", D("-1"), D("100"), reduce_only=True)
                with service.database.transaction() as connection:
                    if value is None:
                        connection.execute("DELETE FROM uta_config WHERE key='halted'")
                    else:
                        connection.execute("UPDATE uta_config SET value=? WHERE key='halted'", (value,))
                self.assertFalse(service.readiness()["ready"])
                self.assert_code("configuration_corrupt", service.submit_order, "alice", "new", "X", D("1"), D("100"))
                self.assert_code("configuration_corrupt", service.submit_order, "alice", "newred", "X", D("-0.1"), D("100"), reduce_only=True)
                self.assert_code("configuration_corrupt", service.apply_fill, "alice", "pending", "bad", D("1"), D("100"))
                self.assert_code("configuration_corrupt", service.apply_fill, "alice", "reduce", "badred", D("-1"), D("100"))
                self.assertEqual(service.cancel_order("alice", "pending")["status"], "CANCELLED")
                service.set_kill_switch(False)
                self.assertTrue(service.readiness()["ready"])


if __name__ == "__main__":
    unittest.main()
