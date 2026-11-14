"""Independent executable references for UTA-CROSS-LOAN-v1 and stress policy.

Only public production entry points are called. Expected values use separate
cashflow equations, marginal-band integrals and a feasibility search on the
borrow quantity grid; no production helper or returned result seeds the oracle.
All inputs are synthetic. These tests do not calibrate economic parameters.
"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D, Inexact, Rounded, ROUND_UP, localcontext
from fractions import Fraction as F
import random
import unittest

from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec, RiskInputError
from uta.portfolio import (BorrowLimits, CollateralRule, CollateralTier,
                           LinearExposure, LinearMarginRule, LoanAccount,
                           PortfolioRules, StressScenario, calculate_cross_risk,
                           scenario_reference)
from uta.products import (AccountMode, ProductCatalog, ProductKind, ProductSpec,
                          TradingStatus, UnsupportedProduct)


NOW = datetime(2026, 11, 14, 12, tzinfo=timezone.utc)
ZERO = F(0)
CROSS_SEED = 931472
SCENARIO_SEED = 792416


def marginal_value(notional, tiers):
    """Integrate the marginal schedule by intersecting cumulative intervals."""
    value = F(notional)
    result, lower = ZERO, ZERO
    for tier in tiers:
        upper = value if tier.up_to is None else F(tier.up_to)
        width = max(ZERO, min(value, upper) - lower)
        result += width * F(tier.factor)
        lower = upper
    return result


def cross_reference(account, market, catalog, rules):
    """Independent revaluation plus largest feasible grid quantity per loan.

    The grid search tests the *resulting* debt, equity, IM and MM at each trial,
    rather than copying production's minimum-of-capacities expression.
    Borrow proceeds leave collateral, as specified by the project policy.
    """
    gross_value = frozen_value = collateral = loan_value = ZERO
    principal_value = interest_value = borrow_im = borrow_mm = ZERO
    for asset in set(account.gross_assets) | set(account.principal) | set(account.interest):
        price = F(market.assets[asset].price)
        gross = F(account.gross_assets.get(asset, D(0)))
        frozen = F(account.frozen_assets.get(asset, D(0)))
        gross_value += gross * price
        frozen_value += frozen * price
        if gross:
            rule = rules.collaterals[asset]
            contribution = marginal_value((gross - frozen) * price, rule.tiers)
            collateral += contribution
            loan_value += contribution * F(rule.loan_to_value)
        principal = F(account.principal.get(asset, D(0))) * price
        interest = F(account.interest.get(asset, D(0))) * price
        principal_value += principal
        interest_value += interest
        if principal or interest:
            loan = rules.borrow_limits[asset]
            borrow_im += (principal + interest) * F(loan.initial_margin_rate)
            borrow_mm += (principal + interest) * F(loan.maintenance_margin_rate)
    unrealized = linear_im = linear_mm = ZERO
    for symbol, exposure in account.positions.items():
        product = catalog.products[symbol]
        marked_units = F(exposure.quantity) * F(product.multiplier)
        marked_value = marked_units * F(market.instruments[symbol].mark_price)
        unrealized += marked_value - F(exposure.cost_basis)
        linear_rule = rules.linear_margin[product.risk_tier]
        linear_im += abs(marked_value) * F(linear_rule.initial_margin_rate)
        linear_mm += abs(marked_value) * F(linear_rule.maintenance_margin_rate)
    debt = principal_value + interest_value
    risk_equity = collateral - debt + unrealized
    initial = borrow_im + linear_im
    maintenance = borrow_mm + linear_mm
    order_margin = F(account.order_margin)
    available = risk_equity - initial - order_margin
    quoted = {}
    for asset, loan in rules.borrow_limits.items():
        price, step = F(market.assets[asset].price), F(loan.quantity_step)
        existing = F(account.principal.get(asset, D(0)))
        high = max(0, int((F(loan.max_principal) - existing) // step))

        def feasible(count):
            quantity = count * step
            candidate_debt = debt + quantity * price
            candidate_equity = risk_equity - quantity * price
            candidate_im = initial + quantity * price * F(loan.initial_margin_rate)
            candidate_mm = maintenance + quantity * price * F(loan.maintenance_margin_rate)
            return (existing + quantity <= F(loan.max_principal)
                    and candidate_debt <= F(rules.max_total_debt)
                    and candidate_debt <= loan_value
                    and candidate_equity - candidate_im - order_margin >= 0
                    and candidate_equity > candidate_mm)

        low = 0
        while low < high:
            middle = (low + high + 1) // 2
            if feasible(middle):
                low = middle
            else:
                high = middle - 1
        quoted[asset] = low * step
    return {
        "accounting_equity": gross_value - debt + unrealized,
        "collateral_value": collateral, "risk_equity": risk_equity,
        "loan_value": loan_value, "principal_value": principal_value,
        "interest_value": interest_value, "debt_value": debt,
        "unrealized_pnl": unrealized, "frozen_value": frozen_value,
        "initial_margin": initial, "maintenance_margin": maintenance,
        "order_margin": order_margin, "available_margin": available,
        "borrowable": quoted,
        "status": "LIQUIDATION" if risk_equity <= maintenance else "MARGIN_CALL" if available < 0 else "HEALTHY",
    }


def stress_reference(account, market, catalog, rules, scenarios, floor, liquidity, credit):
    """Revalue each separate risk unit before clipping its loss at zero."""
    losses, units = {}, {}
    for scenario in scenarios:
        per_unit = {}
        for asset in set(account.gross_assets) | set(account.principal) | set(account.interest):
            base_price = F(market.assets[asset].price)
            stressed_price = base_price * (1 + F(scenario.asset_shocks.get(asset, D(0))))
            gross = F(account.gross_assets.get(asset, D(0))) - F(account.frozen_assets.get(asset, D(0)))
            debt = F(account.principal.get(asset, D(0))) + F(account.interest.get(asset, D(0)))
            rule = rules.collaterals.get(asset)
            baseline = (marginal_value(gross * base_price, rule.tiers) if rule else ZERO) - debt * base_price
            stressed = (marginal_value(gross * stressed_price, rule.tiers) if rule else ZERO) - debt * stressed_price
            per_unit["collateral:" + asset] = max(ZERO, baseline - stressed)
        for symbol, exposure in account.positions.items():
            product = catalog.products[symbol]
            mark = F(market.instruments[symbol].mark_price)
            shocked = mark * (1 + F(scenario.instrument_shocks.get(symbol, D(0))))
            quantity = F(exposure.quantity) * F(product.multiplier)
            base_pnl = quantity * mark - F(exposure.cost_basis)
            stressed_pnl = quantity * shocked - F(exposure.cost_basis)
            # Build the key explicitly instead of calling ProductSpec.risk_unit.
            expiry = product.expiry.isoformat() if product.expiry else "perpetual-or-spot"
            key = "linear:" + "|".join((product.underlying, product.kind.value, expiry,
                                        product.settlement_asset, product.symbol))
            per_unit[key] = max(ZERO, base_pnl - stressed_pnl)
        units[scenario.scenario_id] = per_unit
        losses[scenario.scenario_id] = sum(per_unit.values(), ZERO)
    worst = max(losses.values())
    return losses, units, max(worst, F(floor)) + F(liquidity) + F(credit)


def product(symbol="X", multiplier="2", underlying="BTC", risk_tier="tier-1", **changes):
    values = dict(symbol=symbol, kind=ProductKind.LINEAR_PERPETUAL, underlying=underlying,
                  quote_asset="USD", settlement_asset="USD", price_tick=D("0.01"),
                  quantity_step=D("0.001"), min_notional=D("1"), multiplier=D(multiplier),
                  risk_tier=risk_tier, status=TradingStatus.ACTIVE)
    values.update(changes)
    return ProductSpec(**values)


def manual_case():
    market = MarketSnapshot(7, NOW,
        {"USD": AssetSpec(D(1), D(1)), "BTC": AssetSpec(D(100), D("0.8"))},
        {"X": InstrumentSpec(D(110), D("0.9"), D("0.8"))})
    catalog = ProductCatalog(4, {"X": product()})
    rules = PortfolioRules(3,
        {"USD": CollateralRule("USD", (CollateralTier(None, D(1)),), D("0.8")),
         "BTC": CollateralRule("BTC", (CollateralTier(D(100), D("0.8")), CollateralTier(None, D("0.5"))), D("0.5"))},
        {"USD": BorrowLimits("USD", D(1000), D("0.1"), D("0.05"), D("0.01")),
         "BTC": BorrowLimits("BTC", D(10), D("0.2"), D("0.1"), D("0.001"))},
        {"tier-1": LinearMarginRule("tier-1", D("0.1"), D("0.05"))}, D(500))
    account = LoanAccount({"USD": D(1000), "BTC": D(2)}, {"USD": D(100), "BTC": D("0.1")},
                          {"USD": D(1), "BTC": D("0.01")}, {"BTC": D("0.5")},
                          {"X": LinearExposure("X", D(2), D(400))}, D(10))
    return account, market, catalog, rules


def generated_case(generator, index):
    # Decimal construction happens outside deliberately hostile caller contexts.
    prices = {"USD": D(1), "BTC": D(generator.randint(1, 2000)) / D(4),
              "ETH": D(generator.randint(1, 1000)) / D(8)}
    marks = {"X": D(generator.randint(100, 2000)) / D(4),
             "Y": D(generator.randint(100, 2000)) / D(8)}
    market = MarketSnapshot(index, NOW, {asset: AssetSpec(price, D("0.11")) if asset != "USD" else AssetSpec(price, D(1))
                                       for asset, price in prices.items()},
        {symbol: InstrumentSpec(mark, D("0.8"), D("0.7")) for symbol, mark in marks.items()})
    catalog = ProductCatalog(100 + index, {
        "X": product(multiplier=generator.choice(("0.1", "1", "2", "5"))),
        "Y": product("Y", generator.choice(("0.1", "1", "3")), "BTC", "tier-2"),
    })
    zero_mm = index % 7 == 0
    rates = {asset: D(generator.choice(("0", "0.05", "0.1", "0.25", "0.5"))) for asset in prices}
    loan_limits = {asset: BorrowLimits(asset, D(generator.randint(0, 10000)), rate,
                                      D(0) if zero_mm else rate / D(2),
                                      D(generator.choice(("0.001", "0.01", "0.25", "1"))))
                   for asset, rate in rates.items()}
    collaterals = {"USD": CollateralRule("USD", (CollateralTier(None, D(1)),), D(generator.choice(("0", "0.5", "0.8", "1"))))}
    for asset in ("BTC", "ETH"):
        collaterals[asset] = CollateralRule(asset,
            (CollateralTier(D(100), D("0.9")), CollateralTier(D(500), D("0.6")), CollateralTier(None, D("0.2"))),
            D(generator.choice(("0", "0.25", "0.5", "0.8", "1"))))
    rules = PortfolioRules(index, collaterals, loan_limits,
        {"tier-1": LinearMarginRule("tier-1", D("0.1"), D(0) if zero_mm else D("0.05")),
         "tier-2": LinearMarginRule("tier-2", D("0.25"), D(0) if zero_mm else D("0.1"))},
        D(0) if index % 13 == 0 else D(generator.randint(1, 20000)))
    gross = {asset: D(generator.randint(0, 1000)) / D(10) for asset in prices}
    principal = {asset: D(generator.randint(0, 200)) / D(20) for asset in prices}
    interest = {asset: D(generator.randint(0, 100)) / D(1000) for asset in prices}
    frozen = {asset: amount * D(generator.choice(("0", "0.25", "0.5", "1"))) for asset, amount in gross.items()}
    positions = {}
    for symbol in ("X", "Y"):
        quantity = D(generator.randint(-20, 20)) / D(10)
        if quantity:
            entry = marks[symbol] * D(generator.choice(("0.5", "1", "2")))
            cost = quantity * catalog.products[symbol].multiplier * entry
            positions[symbol] = LinearExposure(symbol, quantity, cost)
    return LoanAccount(gross, principal, interest, frozen, positions,
                       D(generator.randint(0, 1000)) / D(10)), market, catalog, rules


class IndependentCrossReferenceTests(unittest.TestCase):
    def assert_reference(self, account, market, catalog, rules):
        expected = cross_reference(account, market, catalog, rules)
        actual = calculate_cross_risk(account, market, catalog, rules, now=NOW)
        for field, value in expected.items():
            with self.subTest(field=field):
                if field == "borrowable":
                    self.assertEqual({asset: F(amount) for asset, amount in actual.borrowable.items()}, value)
                elif field == "status":
                    self.assertEqual(actual.status, value)
                else:
                    self.assertEqual(F(getattr(actual, field)), value)
        self.assertEqual((actual.rule_version, actual.catalog_version, actual.market_version),
                         (rules.version, catalog.version, market.version))
        return actual

    def test_manual_case_matches_published_rule_numbers_and_independent_reference(self):
        account, market, catalog, rules = manual_case()
        actual = self.assert_reference(account, market, catalog, rules)
        expected = {"accounting_equity": "1128", "collateral_value": "1105", "risk_equity": "1033",
                    "loan_value": "852.5", "principal_value": "110", "interest_value": "2", "debt_value": "112",
                    "unrealized_pnl": "40", "frozen_value": "50", "initial_margin": "56.3",
                    "maintenance_margin": "28.15", "available_margin": "966.7"}
        for field, amount in expected.items():
            self.assertEqual(getattr(actual, field), D(amount), field)
        self.assertEqual(dict(actual.borrowable), {"USD": D(388), "BTC": D("3.88")})
        # The deliberately different market IM/MM (.9/.8) must not replace the
        # explicitly versioned rule rates (.1/.05).
        self.assertEqual(actual.initial_margin, D("56.3"))

    def test_320_seeded_accounts_match_feasibility_search_exactly(self):
        generator = random.Random(CROSS_SEED)
        states = set()
        for index in range(1, 321):
            case = generated_case(generator, index)
            with self.subTest(seed=CROSS_SEED, case=index):
                states.add(self.assert_reference(*case).status)
        self.assertIn("LIQUIDATION", states)
        self.assertIn("HEALTHY", states)

    def test_tier_boundaries_freezes_and_same_asset_debt_are_not_netted(self):
        account, market, catalog, rules = manual_case()
        market = replace(market, assets={"USD": market.assets["USD"], "BTC": AssetSpec(D("2.5"), D("0.01"))})
        for gross in ("0", "39.999", "40", "40.001", "80"):
            for frozen in ("0", gross):
                case = LoanAccount({"USD": D(1000), "BTC": D(gross)}, {"BTC": D(20)},
                                   {"BTC": D("0.1")}, {"BTC": D(frozen)})
                with self.subTest(gross=gross, frozen=frozen):
                    self.assert_reference(case, market, catalog, rules)
        actual = calculate_cross_risk(LoanAccount({"BTC": D(40)}, {"BTC": D(20)}), market, catalog, rules, now=NOW)
        self.assertEqual(actual.risk_equity, D(30))  # 100*.8 - 50, not (100-50)*.8.

    def test_maintenance_equality_and_borrow_grid_require_strict_surplus(self):
        _, market, catalog, _ = manual_case()
        for rate in ("0", "0.1", "0.25", "1"):
            rules = PortfolioRules(1, {"USD": CollateralRule("USD", (CollateralTier(None, D(1)),), D(1))},
                {"USD": BorrowLimits("USD", D(100), D(rate), D(rate), D("0.25"))}, {}, D(100))
            for gross, principal in (("0", "0"), ("1", "2"), ("1", "1"), ("10", "0")):
                with self.subTest(rate=rate, gross=gross, principal=principal):
                    actual = self.assert_reference(LoanAccount({"USD": D(gross)}, {"USD": D(principal)}), market, catalog, rules)
                    if D(gross) <= D(principal):
                        self.assertEqual(actual.status, "LIQUIDATION")
                        self.assertEqual(actual.borrowable["USD"], D(0))
        # With no IM/MM, a quote of ten would leave equity exactly zero. The
        # largest valid .25-grid quantity from ten USD is therefore 9.75.
        rules = replace(rules, borrow_limits={"USD": BorrowLimits("USD", D(100), D(0), D(0), D("0.25"))})
        self.assertEqual(self.assert_reference(LoanAccount({"USD": D(10)}), market, catalog, rules).borrowable["USD"], D("9.75"))

    def test_32_cases_ignore_precision_rounding_exponent_bounds_and_traps(self):
        generator = random.Random(CROSS_SEED)
        for index in range(1, 33):
            case = generated_case(generator, index)
            expected = calculate_cross_risk(*case, now=NOW)
            with self.subTest(case=index), localcontext() as context:
                context.prec = 1
                context.rounding = ROUND_UP
                context.Emax, context.Emin = 2, -2
                context.traps[Inexact] = True
                context.traps[Rounded] = True
                self.assertEqual(calculate_cross_risk(*case, now=NOW), expected)
                self.assert_reference(*case)

    def test_missing_data_and_unsupported_modes_or_products_fail_closed(self):
        account, market, catalog, rules = manual_case()
        failures = [
            (account, replace(market, assets={"USD": market.assets["USD"]}), catalog, rules),
            (account, replace(market, instruments={}), catalog, rules),
            (account, market, catalog, replace(rules, collaterals={"USD": rules.collaterals["USD"]})),
            (account, market, catalog, replace(rules, borrow_limits={"USD": rules.borrow_limits["USD"]})),
            (account, market, catalog, replace(rules, linear_margin={})),
        ]
        for case in failures:
            with self.subTest(missing=str(case[3])[:50]), self.assertRaises(RiskInputError):
                calculate_cross_risk(*case, now=NOW)
        with self.assertRaises(RiskInputError):
            calculate_cross_risk(account, market, catalog, rules, now=NOW + timedelta(seconds=6))
        for mode in (AccountMode.ISOLATED, AccountMode.PM):
            with self.subTest(mode=mode), self.assertRaises(UnsupportedProduct):
                calculate_cross_risk(replace(account, mode=mode), market, catalog, rules, now=NOW)
        for kind in (ProductKind.OPTION, ProductKind.INVERSE_PERPETUAL, ProductKind.DATED_FUTURE):
            expiry = NOW + timedelta(days=30) if kind in (ProductKind.OPTION, ProductKind.DATED_FUTURE) else None
            unsupported = ProductCatalog(5, {"X": product(kind=kind, expiry=expiry)})
            with self.subTest(kind=kind), self.assertRaises(UnsupportedProduct):
                calculate_cross_risk(account, market, unsupported, rules, now=NOW)


class IndependentStressReferenceTests(unittest.TestCase):
    def assert_stress(self, case, scenarios, floor, liquidity, credit):
        expected_losses, expected_units, requirement = stress_reference(*case, scenarios, floor, liquidity, credit)
        actual = scenario_reference(*case, scenarios, now=NOW, minimum_floor=floor,
                                    liquidity_addon=liquidity, credit_addon=credit)
        self.assertEqual({key: F(value) for key, value in actual.scenario_losses.items()}, expected_losses)
        self.assertEqual({key: {unit: F(value) for unit, value in values.items()}
                          for key, values in actual.unit_losses.items()}, expected_units)
        self.assertEqual(F(actual.worst_loss), max(expected_losses.values()))
        self.assertEqual(expected_losses[actual.worst_scenario], F(actual.worst_loss))
        self.assertEqual(F(actual.reference_requirement), requirement)
        self.assertFalse(actual.pm_activatable)
        return actual

    def test_96_seeded_stresses_revalue_separate_units_and_floor_addons(self):
        generator = random.Random(SCENARIO_SEED)
        for index in range(1, 97):
            case = generated_case(generator, index)
            scenarios = tuple(StressScenario("scenario-" + str(s),
                {asset: D(generator.choice(("-1", "-0.5", "-0.1", "0", "0.1", "0.75"))) for asset in ("BTC", "ETH")},
                {symbol: D(generator.choice(("-1", "-0.5", "-0.1", "0", "0.1", "0.75"))) for symbol in ("X", "Y")}) for s in range(4))
            floor, liquidity, credit = D(generator.randint(0, 1000)), D("1.25"), D("2.5")
            with self.subTest(seed=SCENARIO_SEED, case=index):
                self.assert_stress(case, scenarios, floor, liquidity, credit)

    def test_same_underlying_opposite_positions_never_offset_other_unit_losses(self):
        _, market, _, rules = manual_case()
        catalog = ProductCatalog(1, {"X": product(multiplier="1"), "Y": product("Y", "1")})
        market = replace(market, instruments={"X": InstrumentSpec(D(100), D("0.1"), D("0.05")),
                                             "Y": InstrumentSpec(D(100), D("0.1"), D("0.05"))})
        account = LoanAccount({"USD": D(1000), "BTC": D(1)}, positions={
            "X": LinearExposure("X", D(1), D(100)), "Y": LinearExposure("Y", D(-1), D(-100))})
        scenarios = (StressScenario("down", {"BTC": D("-0.2")}, {"X": D("-0.2"), "Y": D("-0.2")}),
                     StressScenario("up", {"BTC": D("0.2")}, {"X": D("0.2"), "Y": D("0.2")}))
        result = self.assert_stress((account, market, catalog, rules), scenarios, D(50), D(3), D(2))
        self.assertEqual(dict(result.scenario_losses), {"down": D(36), "up": D(20)})
        self.assertEqual(result.reference_requirement, D(55))
        with self.assertRaises(ValueError):
            replace(result, pm_activatable=True)

    def test_usd_depeg_pm_activation_and_unimplemented_revaluation_are_rejected(self):
        account, market, catalog, rules = manual_case()
        for mode in (AccountMode.PM, AccountMode.ISOLATED):
            with self.assertRaises(UnsupportedProduct):
                scenario_reference(replace(account, mode=mode), market, catalog, rules,
                                   (StressScenario("none", {}, {}),), now=NOW)
        with self.assertRaises(UnsupportedProduct):
            scenario_reference(account, market, catalog, rules,
                               (StressScenario("usd-depeg", {"USD": D("-0.1")}, {}),), now=NOW)
        for kind in (ProductKind.OPTION, ProductKind.INVERSE_PERPETUAL):
            expiry = NOW + timedelta(days=30) if kind is ProductKind.OPTION else None
            unsupported = ProductCatalog(2, {"X": product(kind=kind, expiry=expiry)})
            with self.subTest(kind=kind), self.assertRaises(UnsupportedProduct):
                scenario_reference(account, market, unsupported, rules,
                                   (StressScenario("none", {}, {}),), now=NOW)


if __name__ == "__main__":
    unittest.main()
