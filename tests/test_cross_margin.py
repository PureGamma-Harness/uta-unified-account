from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D, Inexact, Rounded, localcontext
import unittest

from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec, RiskInputError
from uta.portfolio import (BorrowLimits, CollateralRule, CollateralTier, LinearExposure,
                           LinearMarginRule, LoanAccount, PortfolioError, PortfolioRules,
                           StressScenario, calculate_cross_risk, scenario_reference)
from uta.products import (AccountMode, ProductCatalog, ProductKind, ProductSpec,
                          TradingStatus, UnsupportedProduct)


class PortfolioTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 14, 12, tzinfo=timezone.utc)
        self.market = MarketSnapshot(7, self.now,
                                     {"USD": AssetSpec(D("1"), D("1")), "BTC": AssetSpec(D("100"), D("0.8"))},
                                     {"X": InstrumentSpec(D("110"), D("0.1"), D("0.05"))})
        self.catalog = ProductCatalog(4, {"X": ProductSpec("X", ProductKind.LINEAR_PERPETUAL, "BTC", "USD", "USD",
                                                         D("0.01"), D("0.001"), D("1"), D("2"), status=TradingStatus.ACTIVE)})
        self.rules = PortfolioRules(3,
            {"USD": CollateralRule("USD", (CollateralTier(None, D("1")),), D("0.8")),
             "BTC": CollateralRule("BTC", (CollateralTier(D("100"), D("0.8")), CollateralTier(None, D("0.5"))), D("0.5"))},
            {"USD": BorrowLimits("USD", D("1000"), D("0.1"), D("0.05"), D("0.01")),
             "BTC": BorrowLimits("BTC", D("10"), D("0.2"), D("0.1"), D("0.001"))},
            {"tier-1": LinearMarginRule("tier-1", D("0.1"), D("0.05"))}, D("500"))

    def calculate(self, account, **changes):
        values = dict(market=self.market, catalog=self.catalog, rules=self.rules, now=self.now)
        values.update(changes)
        return calculate_cross_risk(account, **values)

    def test_hand_computed_tiers_gross_loans_interest_freeze_and_multiplier(self):
        account = LoanAccount({"USD": D("1000"), "BTC": D("2")},
                              {"USD": D("100"), "BTC": D("0.1")},
                              {"USD": D("1"), "BTC": D("0.01")}, {"BTC": D("0.5")},
                              {"X": LinearExposure("X", D("2"), D("400"))}, D("10"))
        result = self.calculate(account)
        # Independently hand computed: available BTC = 1.5, marginal haircut =
        # 100*.8 + 50*.5 = 105. Debt = 100+10+1+1=112; linear PnL=2*2*110-400=40.
        expected = {"accounting_equity": "1128", "collateral_value": "1105", "risk_equity": "1033",
                    "loan_value": "852.5", "principal_value": "110", "interest_value": "2", "debt_value": "112",
                    "unrealized_pnl": "40", "frozen_value": "50", "initial_margin": "56.3",
                    "maintenance_margin": "28.15", "available_margin": "966.7"}
        for name, value in expected.items():
            with self.subTest(name=name):
                self.assertEqual(getattr(result, name), D(value))
        self.assertEqual(dict(result.borrowable), {"USD": D("388"), "BTC": D("3.88")})
        self.assertEqual((result.rule_id, result.rule_version, result.catalog_version, result.market_version),
                         ("UTA-CROSS-LOAN-v1", 3, 4, 7))
        self.assertIn("market-7@", result.market_id)

    def test_assets_and_liabilities_are_never_netted_before_haircut(self):
        result = self.calculate(LoanAccount({"BTC": D("1")}, {"BTC": D("0.5")}))
        self.assertEqual(result.accounting_equity, D("50"))
        self.assertEqual(result.risk_equity, D("30"))  # 100*.8-50, NOT (100-50)*.8.
        self.assertEqual(result.initial_margin, D("10"))
        self.assertEqual(result.borrowable["BTC"], D("0"))

    def test_borrow_capacity_uses_full_liability_loss_and_incremental_im(self):
        rules = PortfolioRules(4, {"USD": CollateralRule("USD", (CollateralTier(None, D("1")),), D("1"))},
                               {"USD": BorrowLimits("USD", D("10000"), D("0.25"), D("0.1"), D("0.01"))},
                               {}, D("10000"))
        result = self.calculate(LoanAccount({"USD": D("1000")}), rules=rules)
        # Borrowed proceeds are excluded: b <= 1000/(1+.25)=800, not 1000/.25.
        self.assertEqual(result.borrowable["USD"], D("800"))

    def test_maintenance_equality_is_unsafe_even_with_zero_mm(self):
        for account in (LoanAccount(), LoanAccount(principal={"USD": D("1")})):
            result = self.calculate(account)
            self.assertEqual(result.status, "LIQUIDATION")
            self.assertEqual(result.borrowable["USD"], D("0"))
        rules = PortfolioRules(4, {"USD": CollateralRule("USD", (CollateralTier(None, D("1")),), D("1"))},
                               {"USD": BorrowLimits("USD", D("100"), D("0"), D("0"), D("1"))}, {}, D("100"))
        self.assertEqual(self.calculate(LoanAccount({"USD": D("10")}), rules=rules).borrowable["USD"], D("9"))

    def test_immutable_models_round_trip_and_low_precision(self):
        self.assertEqual(PortfolioRules.from_json(self.rules.to_json()), self.rules)
        assets = {"USD": D("1234.56789")}
        account = LoanAccount(assets)
        baseline = self.calculate(account)
        assets.clear()
        with localcontext() as context:
            context.prec = 2
            context.traps[Inexact] = True
            context.traps[Rounded] = True
            self.assertEqual(self.calculate(account), baseline)
        with self.assertRaises(TypeError):
            self.rules.collaterals["USD"] = self.rules.collaterals["USD"]

    def test_unsupported_modes_products_prices_and_bad_rules_fail_closed(self):
        for mode in (AccountMode.PM, AccountMode.ISOLATED):
            with self.assertRaises(UnsupportedProduct):
                self.calculate(LoanAccount(mode=mode))
        market = MarketSnapshot(8, self.now, {"USD": self.market.assets["USD"]}, self.market.instruments)
        with self.assertRaisesRegex(PortfolioError, "missing_price"):
            self.calculate(LoanAccount(), market=market)
        with self.assertRaises(RiskInputError):
            self.calculate(LoanAccount(), now=self.now + timedelta(seconds=6))
        for tiers in ((CollateralTier(D("1"), D("1")),),
                      (CollateralTier(D("1"), D("0.5")), CollateralTier(None, D("0.8")))):
            with self.assertRaises(PortfolioError):
                CollateralRule("BTC", tiers, D("0.5"))
        with self.assertRaises(PortfolioError):
            LoanAccount({"USD": D("1")}, frozen_assets={"USD": D("2")})

    def test_stress_reference_has_no_spot_perpetual_offsets_and_cannot_activate_pm(self):
        catalog = ProductCatalog(5, {"X": replace(self.catalog.products["X"], multiplier=D("1"))})
        market = MarketSnapshot(8, self.now, dict(self.market.assets, USDC=AssetSpec(D("1"), D("1"))),
                                {"X": InstrumentSpec(D("100"), D("0.1"), D("0.05"))})
        rules = replace(self.rules, collaterals=dict(self.rules.collaterals,
                        USDC=CollateralRule("USDC", (CollateralTier(None, D("1")),), D("0.8"))),
                        borrow_limits=dict(self.rules.borrow_limits,
                        USDC=BorrowLimits("USDC", D("1000"), D("0.1"), D("0.05"))))
        account = LoanAccount({"USDC": D("100"), "BTC": D("1")}, {"USDC": D("20")},
                              positions={"X": LinearExposure("X", D("-1"), D("-100"))})
        result = scenario_reference(account, market, catalog, rules, (
            StressScenario("down", {"BTC": D("-0.2")}, {"X": D("-0.2")}),
            StressScenario("up", {"BTC": D("0.2")}, {"X": D("0.2")}),
            StressScenario("depeg", {"USDC": D("-0.1")}, {}),
        ), now=self.now, minimum_floor=D("25"), liquidity_addon=D("3"), credit_addon=D("2"))
        self.assertEqual(dict(result.scenario_losses), {"down": D("16"), "up": D("20"), "depeg": D("8")})
        self.assertEqual(result.worst_scenario, "up")
        self.assertEqual(result.reference_requirement, D("30"))
        self.assertFalse(result.pm_activatable)
        self.assertEqual(result.unit_losses["down"]["collateral:BTC"], D("16"))


if __name__ == "__main__":
    unittest.main()
