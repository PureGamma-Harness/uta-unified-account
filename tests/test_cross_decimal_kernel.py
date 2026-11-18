"""CODE-only contracts for the opt-in Cross decimal candidate; not a load test."""
from dataclasses import fields, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D, Inexact, Rounded, localcontext
from itertools import product
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from uta.cross_decimal_kernel import (DecimalKernelUnsupported, _Arithmetic,
                                      calculate_cross_risk_decimal)
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec, RiskInputError
from uta.portfolio import (BorrowLimits, CollateralRule, CollateralTier, CrossRisk,
                           LinearExposure, LinearMarginRule, LoanAccount,
                           PortfolioRules, calculate_cross_risk)
from uta.products import (AccountMode, ProductCatalog, ProductKind, ProductSpec,
                          TradingStatus, UnsupportedProduct)


NOW = datetime(2026, 11, 18, 10, tzinfo=timezone.utc)
MANUAL = json.loads((Path(__file__).resolve().parents[1]
    / "evidence/reviews/cross-decimal-kernel/manual-cases.json").read_bytes())


def fixture(*, btc_price="100", mark="100", multiplier="1", im=".1", mm=".05",
            borrow=False, step=".01", debt_cap="10000", tiered=False):
    market = MarketSnapshot(7, NOW,
        {"USD": AssetSpec(D(1), D(1)), "BTC": AssetSpec(D(btc_price), D(".2"))},
        {"BTC-PERP": InstrumentSpec(D(mark), D(im), D(mm))})
    catalog = ProductCatalog(3, {"BTC-PERP": ProductSpec(
        "BTC-PERP", ProductKind.LINEAR_PERPETUAL, "BTC", "USD", "USD", D(".00000001"),
        D(".00000001"), D(0), multiplier=D(multiplier), status=TradingStatus.ACTIVE)})
    rules = PortfolioRules(5,
        {"USD": CollateralRule("USD", (CollateralTier(None, D(1)),), D(1)),
         "BTC": CollateralRule("BTC", ((CollateralTier(D(100), D(".8")),
             CollateralTier(None, D(".5"))) if tiered else (CollateralTier(None, D(".8")),)), D(".5"))},
        {"BTC": BorrowLimits("BTC", D(100), D(".1"), D(".05"), D(step))} if borrow else {},
        {"tier-1": LinearMarginRule("tier-1", D(im), D(mm))}, D(debt_cap))
    return market, catalog, rules


class CrossDecimalKernelTests(unittest.TestCase):
    def compare(self, account, values):
        market, catalog, rules = values
        expected = calculate_cross_risk(account, market, catalog, rules, now=NOW)
        actual = calculate_cross_risk_decimal(account, market, catalog, rules, now=NOW)
        # The reference is a differential oracle, not the source of manual values.
        for descriptor in fields(CrossRisk):
            key = descriptor.name
            left, right = getattr(expected, key), getattr(actual, key)
            self.assertEqual(left, right, key)
            if isinstance(left, D):
                self.assertEqual(left.as_tuple(), right.as_tuple(), key)
            elif key == "borrowable":
                for asset in left:
                    self.assertEqual(left[asset].as_tuple(), right[asset].as_tuple(), (key, asset))
        return actual

    def manual(self, value, expected):
        for key, literal in expected.items():
            actual = getattr(value, key)
            if key == "borrowable":
                self.assertEqual(dict(actual), {asset: D(amount) for asset, amount in literal.items()})
            elif key == "status":
                self.assertEqual(actual, literal)
            else:
                self.assertEqual(actual, D(literal), key)

    def test_full_manual_multi_asset_and_same_coin_gross_debt(self):
        market, catalog, rules = fixture(mark="110", multiplier="2", borrow=True, tiered=True, debt_cap="500")
        rules = replace(rules, collaterals={
            "USD": CollateralRule("USD", (CollateralTier(None, D(1)),), D(".8")),
            "BTC": rules.collaterals["BTC"]}, borrow_limits={
            "USD": BorrowLimits("USD", D(1000), D(".1"), D(".05"), D(".01")),
            "BTC": BorrowLimits("BTC", D(10), D(".2"), D(".1"), D(".01"))})
        account = LoanAccount({"USD": D(1000), "BTC": D(2)},
            {"USD": D(100), "BTC": D(".1")}, {"USD": D(1), "BTC": D(".01")},
            {"BTC": D(".5")}, {"BTC-PERP": LinearExposure("BTC-PERP", D(2), D(400))}, D(10))
        self.manual(self.compare(account, (market, catalog, rules)), MANUAL["M01"]["expected"])
        account = LoanAccount({"BTC": D(2)}, {"BTC": D("1.25")}, {"BTC": D(".05")})
        self.manual(self.compare(account, fixture(borrow=True)), MANUAL["M02"]["expected"])

    def test_subcurrency_tier_and_separate_cash_deficit_manual_cases(self):
        market, catalog, rules = fixture(tiered=True, borrow=True)
        rules = replace(rules, borrow_limits={"BTC": BorrowLimits("BTC", D(100), D(0), D(0))})
        account = LoanAccount({"BTC": D("1.00000000001")}, {"BTC": D(".00000000001")},
                              order_margin=D(".0000000001"))
        self.manual(self.compare(account, (market, catalog, rules)), MANUAL["M03"]["expected"])
        account = LoanAccount({"USD": D(1)}, cash_deficits={"USD": D(2), "BTC": D(".01")})
        self.manual(self.compare(account, fixture()), MANUAL["M04"]["expected"])

    def test_linear_long_short_multiplier_and_legitimate_cost_dust(self):
        for quantity, cost, key in (("2", "400", "long"), ("-2", "-400", "short")):
            account = LoanAccount({"USD": D(1000)}, positions={
                "BTC-PERP": LinearExposure("BTC-PERP", D(quantity), D(cost))})
            self.manual(self.compare(account, fixture(mark="110", multiplier="2")), MANUAL["M05"][key])
        account = LoanAccount({"USD": D(1)}, positions={
            "BTC-PERP": LinearExposure("BTC-PERP", D(".0001"), D("-.00000001"))})
        self.manual(self.compare(account, fixture(mark="1")), MANUAL["M06"]["expected"])

    def test_zero_maintenance_equal_maintenance_and_order_reserve_boundaries(self):
        for cash, deficits, expected in (("0", {}, "LIQUIDATION"),
                ("1e-100", {}, "HEALTHY"), ("0", {"USD": D(1)}, "LIQUIDATION")):
            self.assertEqual(self.compare(LoanAccount({"USD": D(cash)}, cash_deficits=deficits), fixture()).status, expected)
        for cash, expected in (("10", "LIQUIDATION"), ("10.00000001", "HEALTHY")):
            account = LoanAccount({"USD": D(cash)}, positions={
                "BTC-PERP": LinearExposure("BTC-PERP", D(1), D(100))})
            self.assertEqual(self.compare(account, fixture(mm=".1")).status, expected)
        self.manual(self.compare(LoanAccount({"USD": D(10)}, order_margin=D(20)), fixture()), MANUAL["M11"]["expected"])

    def test_integer_borrow_floor_and_strict_maintenance_cap_manual_cases(self):
        market, catalog, rules = fixture()
        rules = replace(rules, max_total_debt=D(100), borrow_limits={
            "USD": BorrowLimits("USD", D(100), D(".1"), D(".1"), D(1))})
        actual = self.compare(LoanAccount({"USD": D(11)}), (market, catalog, rules))
        self.assertEqual(actual.borrowable["USD"], D(MANUAL["M09"]["expected_borrowable_USD"]))
        actual = self.compare(LoanAccount({"USD": D(12)}), fixture(btc_price="3", borrow=True, step=".1"))
        self.assertEqual(actual.borrowable["BTC"], D(MANUAL["M10"]["expected_borrowable_BTC"]))
        rules = replace(rules, borrow_limits={"USD": BorrowLimits("USD", D(100), D(0), D(0), D(".01"))})
        self.assertEqual(self.compare(LoanAccount({"USD": D(10)}), (market, catalog, rules)).borrowable["USD"], D("9.99"))

    def test_fixed_differential_grid_under_hostile_context_and_model_immutability(self):
        # Fixed96 cases: this is finite CODE, not a property/load execution claim.
        cases = product(("0", "11", "100"), ("0", ".5"), ("0", ".01"),
                        ("-1", "1"), ("-.00000001", "100"), (".05", ".1"))
        for cash, principal, deficit, quantity, cost, mm in cases:
            with self.subTest(cash=cash, principal=principal, deficit=deficit,
                              quantity=quantity, cost=cost, mm=mm):
                account = LoanAccount({"USD": D(cash), "BTC": D(2)}, {"BTC": D(principal)},
                    frozen_assets={"BTC": D(".5")}, cash_deficits={"USD": D(deficit)},
                    positions={"BTC-PERP": LinearExposure("BTC-PERP", D(quantity), D(cost))}, order_margin=D(".1"))
                values = fixture(borrow=True, tiered=True, mm=mm)
                before = (dict(account.gross_assets), dict(account.principal), dict(account.positions),
                          values[0].to_json(), values[1].to_json(), values[2].to_json())
                with localcontext() as context:
                    context.prec = 2
                    context.traps[Inexact] = context.traps[Rounded] = True
                    self.compare(account, values)
                self.assertEqual(before, (dict(account.gross_assets), dict(account.principal), dict(account.positions),
                    values[0].to_json(), values[1].to_json(), values[2].to_json()))

    def test_large_model_bounded_values_and_zero_representation_are_exact(self):
        account = LoanAccount({"USD": D("1e100")}, positions={
            "BTC-PERP": LinearExposure("BTC-PERP", D("1e100"), D("-1e100"))})
        self.compare(account, fixture(mark="1e100", multiplier="1e100"))
        account = LoanAccount({"USD": D("-0.000")}, order_margin=D("0.000000"))
        self.compare(account, fixture())
        account = LoanAccount({"USD": D("1e-100")}, positions={
            "BTC-PERP": LinearExposure("BTC-PERP", D("1e-100"), D("-1e-100"))})
        self.compare(account, fixture(mark="1e-100", multiplier="1e-100", im="1e-100", mm="0"))

    def test_invalid_scalar_and_explicit_unsupported_specializations(self):
        arithmetic = _Arithmetic()
        for value in (True, False, 1, 1.0, D("NaN"), D("sNaN"), D("Infinity"), D("-Infinity"), D("1e101")):
            with self.subTest(value=repr(value)), self.assertRaises(RiskInputError):
                arithmetic.read(value, "synthetic scalar")
        class OtherDecimal(D):
            pass
        with self.assertRaises(DecimalKernelUnsupported):
            arithmetic.read(OtherDecimal("1"), "subclass")
        market, catalog, rules = fixture()
        for mode in (AccountMode.ISOLATED, AccountMode.PM):
            with self.assertRaises(UnsupportedProduct):
                calculate_cross_risk_decimal(LoanAccount(mode=mode), market, catalog, rules, now=NOW)
        with self.assertRaisesRegex(RiskInputError, "stale"):
            calculate_cross_risk_decimal(LoanAccount(), market, catalog, rules, now=NOW + timedelta(seconds=6))
        with self.assertRaisesRegex(RiskInputError, "missing_price"):
            calculate_cross_risk_decimal(LoanAccount({"UNKNOWN": D(1)}), market, catalog, rules, now=NOW)
        other = replace(catalog.products["BTC-PERP"], kind=ProductKind.INVERSE_PERPETUAL)
        with self.assertRaises(UnsupportedProduct):
            calculate_cross_risk_decimal(LoanAccount(positions={
                "BTC-PERP": LinearExposure("BTC-PERP", D(1), D(100))}),
                market, replace(catalog, products={"BTC-PERP": other}), rules, now=NOW)

    def test_candidate_does_not_call_reference_arithmetic_or_collateral_method(self):
        account = LoanAccount({"USD": D(100), "BTC": D(2)}, principal={"BTC": D(".1")})
        values = fixture(borrow=True, tiered=True)
        expected = calculate_cross_risk(account, *values, now=NOW)
        with patch("uta.portfolio.calculate_cross_risk", side_effect=AssertionError("reference called")), \
                patch("uta.portfolio.Fraction", side_effect=AssertionError("reference Fraction called")), \
                patch.object(CollateralRule, "discounted", side_effect=AssertionError("collateral arithmetic reused")):
            self.assertEqual(calculate_cross_risk_decimal(account, *values, now=NOW), expected)


if __name__ == "__main__":
    unittest.main()
