"""Six owned synthetic golden groups for first-batch policy, not exchange PM."""
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal as D
from fractions import Fraction as Q
import importlib.util
from pathlib import Path
import unittest

from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.portfolio import (BorrowLimits, CollateralRule, CollateralTier, LinearExposure,
                           LinearMarginRule, LoanAccount, PortfolioRules, StressScenario,
                           calculate_cross_risk, scenario_reference)
from uta.products import (AccountMode, ProductCatalog, ProductKind, ProductSpec,
                          TradingStatus, UnsupportedProduct)


SPEC = importlib.util.spec_from_file_location("owned_pm_next_oracle",
    Path(__file__).with_name("pm_independent_next_oracle.py"))
REF = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REF)
NOW = datetime(2026, 11, 17, 12, tzinfo=timezone.utc)


def spec(symbol, **changes):
    values = dict(symbol=symbol, kind=ProductKind.LINEAR_PERPETUAL, underlying="BTC",
                  quote_asset="USD", settlement_asset="USD", price_tick=D("0.01"),
                  quantity_step=D("0.001"), min_notional=D(1), multiplier=D(1),
                  risk_tier="manual", status=TradingStatus.ACTIVE)
    values.update(changes)
    return ProductSpec(**values)


def sut_inputs(raw, *, zero_rates=False, full_ltv=False):
    """Translate raw strings only. The oracle never receives these SUT models."""
    market = MarketSnapshot(41, NOW,
        {asset: AssetSpec(D(price), D(1) if asset == "USD" else D("0.01"))
         for asset, price in REF.PRICES.items()},
        {symbol: InstrumentSpec(D(100), D("0.9"), D("0.8")) for symbol in ("X", "Y")})
    catalog = ProductCatalog(17, {symbol: spec(symbol) for symbol in ("X", "Y")})
    rules = PortfolioRules(23, {
        "USD": CollateralRule("USD", (CollateralTier(None, D(1)),), D(1)),
        "BTC": CollateralRule("BTC", (CollateralTier(D(100), D("0.8")),
                                    CollateralTier(None, D("0.5"))), D(1) if full_ltv else D("0.5")),
        "ETH": CollateralRule("ETH", (CollateralTier(D(50), D("0.9")),
                                    CollateralTier(None, D("0.6"))), D(1) if full_ltv else D("0.5"))},
        {asset: BorrowLimits(asset, D(1000), D(0) if zero_rates else D(rates[0]),
                             D(0) if zero_rates else D(rates[1]), D(step))
         for (asset, rates), step in zip(REF.RATES.items(), ("0.25", "0.001", "0.01"))},
        {"manual": LinearMarginRule("manual", D("0.1"), D("0.05"))}, D(10000))
    decimal_map = lambda values: {asset: D(value) for asset, value in values.items()}
    account = LoanAccount(decimal_map(raw["gross"]), decimal_map(raw["principal"]),
        decimal_map(raw["interest"]), decimal_map(raw["frozen"]),
        {symbol: LinearExposure(symbol, D(quantity), D(cost))
         for symbol, (quantity, cost) in raw["positions"].items()}, D(raw["order"]),
        cash_deficits=decimal_map(raw["deficits"]))
    return account, market, catalog, rules


class OwnedManualGoldenTests(unittest.TestCase):
    def setUp(self):
        # Manual constants must agree with our own arithmetic before every SUT
        # group. This catches reference transcription errors independently.
        self.assertTrue(REF.self_check()["all_match"])

    def assert_cross(self, raw, **options):
        expected = REF.cross(raw, **options)
        actual = calculate_cross_risk(*sut_inputs(raw, **options), now=NOW)
        for field, value in expected.items():
            with self.subTest(field=field):
                observed = getattr(actual, field)
                self.assertEqual(observed if field == "status" else Q(observed), value)
        self.assertEqual((actual.catalog_version, actual.rule_version, actual.market_version), (17, 23, 41))
        return actual

    def assert_stress(self, raw, shocks, **addons):
        expected = REF.stress(raw, shocks, **addons)
        scenarios = tuple(StressScenario(name,
            {asset: D(value) for asset, value in assets.items()},
            {symbol: D(value) for symbol, value in instruments.items()})
            for name, (assets, instruments) in shocks.items())
        names = {"floor": "minimum_floor", "liquidity": "liquidity_addon", "credit": "credit_addon"}
        actual = scenario_reference(*sut_inputs(raw), scenarios, now=NOW,
            **{names[name]: D(value) for name, value in addons.items()})
        self.assertEqual({name: Q(loss) for name, loss in actual.scenario_losses.items()}, expected["losses"])
        for name, units in expected["units"].items():
            for unit, value in units.items():
                if unit in raw["positions"]:
                    key = "linear:BTC|linear_perpetual|perpetual-or-spot|USD|" + unit
                else:
                    key = "collateral:" + unit
                    # The production unit map omits assets absent from the raw
                    # account. The independent full-price table includes zeros.
                    if not any(unit in raw[field] for field in ("gross", "principal", "interest", "deficits")):
                        self.assertEqual(value, 0)
                        self.assertNotIn(key, actual.unit_losses[name])
                        continue
                self.assertEqual(Q(actual.unit_losses[name][key]), value, (name, unit))
        self.assertEqual(Q(actual.reference_requirement), expected["requirement"])
        self.assertFalse(actual.pm_activatable)
        return actual

    def test_v1_multicurrency_gross_debt_interest_freeze_and_cash_deficit(self):
        actual = self.assert_cross(REF.GROSS_DEBT)
        # Deliberately wrong net-first counterfactual: BTC 100-60=40 ->32,
        # ETH 100-15=85 ->66, USD50-3=47; 145 overstates true E127 by18.
        wrong_net_first = Q(47) + REF.discounted("BTC", Q(40)) + REF.discounted("ETH", Q(85))
        self.assertEqual(wrong_net_first - Q(actual.risk_equity), 18)
        self.assertEqual(actual.cash_deficit_value, D(3))
        self.assertEqual(actual.initial_margin, D("13.5"))  # No loan IM on deficit3.

    def test_v2_stress_crosses_marginal_band_and_btc_loses_in_both_directions(self):
        actual = self.assert_stress(REF.GROSS_DEBT, REF.TIER_SHOCKS,
                                    floor="8", liquidity="2", credit="1")
        self.assertEqual(dict(actual.scenario_losses), {"down": D(11), "up": D(1)})
        self.assertEqual(actual.unit_losses["up"]["collateral:BTC"], D(1))

    def test_v3_opposite_symbols_and_removed_leg_have_different_reference_gaps(self):
        cross_gaps, stress_gaps, maintenance_gaps = [], [], []
        for raw in (REF.HEDGE, REF.without_leg("X"), REF.without_leg("Y")):
            with self.subTest(symbols=tuple(raw["positions"])):
                current = self.assert_cross(raw)
                stressed = self.assert_stress(raw, REF.HEDGE_SHOCKS)
                cross_gaps.append(Q(current.available_margin))
                maintenance_gaps.append(Q(current.risk_equity) - Q(current.maintenance_margin))
                stress_gaps.append(Q(current.risk_equity) - Q(stressed.reference_requirement))
        self.assertEqual(cross_gaps, list(map(Q, (88, 98, 98))))
        self.assertEqual(maintenance_gaps, list(map(Q, (104, 109, 109))))
        self.assertEqual(stress_gaps, list(map(Q, (96, 98, 96))))

    def test_v4_positive_mm_equality_and_reserved_im_equality_are_distinct(self):
        for gross in ("10.5", "10.51", "12"):
            with self.subTest(usd=gross):
                raw = REF.boundary(gross)
                actual = self.assert_cross(raw)
                self.assertEqual(actual.borrowable["USD"], D(0))
                self.assertFalse(REF.feasible_extra_loan(raw, "USD", "0.25"))
        self.assertEqual(self.assert_cross(REF.boundary("12")).available_margin, D(0))

    def test_v5_zero_margin_negative_zero_and_positive_equity_with_grid_equality(self):
        for usd in ("0.25", "20.25", "20.5"):
            with self.subTest(usd=usd):
                actual = self.assert_cross(REF.zero_boundary(usd), zero_rates=True, full_ltv=True)
                wanted = {"USD": D(0), "BTC": D("0.002") if usd == "20.5" else D(0), "ETH": D(0)}
                self.assertEqual(dict(actual.borrowable), wanted)
        raw = REF.zero_boundary("20.5")
        self.assertTrue(REF.feasible_extra_loan(raw, "BTC", "0.002", zero_rates=True, full_ltv=True))
        for asset, quantity in (("BTC", "0.003"), ("USD", "0.25")):
            self.assertFalse(REF.feasible_extra_loan(raw, asset, quantity, zero_rates=True, full_ltv=True))

    def test_v6_modes_settlement_quote_and_hedge_declarations_fail_closed(self):
        base, market, catalog, rules = sut_inputs(REF.HEDGE)
        for kind in (ProductKind.SPOT_MARGIN, ProductKind.LINEAR_PERPETUAL):
            for changes in ({}, {"quote_asset": "EUR"}, {"settlement_asset": "BTC"},
                            {"eligible_hedges": ("Y",)}):
                product = spec("X", kind=kind, **changes)
                modified = ProductCatalog(17, {"X": product, "Y": spec("Y")})
                expected = REF.rejection(quote=product.quote_asset, settlement=product.settlement_asset,
                                          hedges=product.eligible_hedges)
                with self.subTest(kind=kind, changes=changes):
                    for gate in (modified.require_supported, modified.require_risk_supported):
                        if expected:
                            with self.assertRaisesRegex(UnsupportedProduct, expected):
                                gate("X")
                        else:
                            self.assertEqual(gate("X"), product)
        # A zero aggregate position does not rescue an unsupported second leg.
        for changes in ({"settlement_asset": "BTC"}, {"quote_asset": "EUR"}, {"eligible_hedges": ("X",)}):
            modified = ProductCatalog(17, {"X": spec("X"), "Y": spec("Y", **changes)})
            expected = REF.rejection(quote=modified.products["Y"].quote_asset,
                                      settlement=modified.products["Y"].settlement_asset,
                                      hedges=modified.products["Y"].eligible_hedges)
            with self.subTest(second_leg=changes), self.assertRaisesRegex(UnsupportedProduct, expected):
                calculate_cross_risk(base, market, modified, rules, now=NOW)
            with self.subTest(stress_second_leg=changes), self.assertRaisesRegex(UnsupportedProduct, expected):
                scenario_reference(base, market, modified, rules, (StressScenario("none", {}, {}),), now=NOW)
        unsupported = replace(catalog, settlement_asset="BTC")
        with self.assertRaisesRegex(UnsupportedProduct, REF.rejection(catalog_settlement="BTC")):
            calculate_cross_risk(base, market, unsupported, rules, now=NOW)
        for mode in (AccountMode.PM, AccountMode.ISOLATED):
            for raw in (REF.HEDGE, REF.account({})):
                account = replace(sut_inputs(raw)[0], mode=mode)
                with self.subTest(mode=mode, empty=not raw["gross"]):
                    expected = REF.rejection(mode=mode.value)
                    with self.assertRaisesRegex(UnsupportedProduct, expected):
                        calculate_cross_risk(account, market, catalog, rules, now=NOW)
                    with self.assertRaisesRegex(UnsupportedProduct, expected):
                        scenario_reference(account, market, catalog, rules, (StressScenario("none", {}, {}),), now=NOW)
            with self.assertRaisesRegex(UnsupportedProduct, REF.rejection(mode=mode.value)):
                catalog.require_supported("X", mode=mode)


if __name__ == "__main__":
    unittest.main()
