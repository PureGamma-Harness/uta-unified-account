"""Independent finite Cross oracle; borrow limits are enumerated, never divided.

No reference calculator or production rounding/discount/borrow helper is used.
This synthetic specialization has two collateral assets and one linear product.
"""
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal as D, Inexact, Rounded, localcontext
from fractions import Fraction as F
import unittest

from uta.cross_decimal_kernel import calculate_cross_risk_decimal
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.portfolio import (BorrowLimits, CollateralRule, CollateralTier,
                           LinearExposure, LinearMarginRule, LoanAccount, PortfolioRules)
from uta.products import ProductCatalog, ProductKind, ProductSpec


NOW = datetime(2026, 11, 18, 11, tzinfo=timezone.utc)


def dec(coefficient, exponent=0):
    """Construct exact inputs without arithmetic in the active Decimal context."""
    return D((int(coefficient < 0), tuple(map(int, str(abs(coefficient)))), exponent))


def models(*, cash=10000, btc=20000, frozen_usd=0, frozen_btc=0,
           usd_principal=0, btc_principal=0, usd_interest=0, btc_interest=0,
           deficit=0, quantity=0, cost=0, reserve=0, spot=100, mark=100):
    account = LoanAccount(
        {"USD": dec(cash, -2), "BTC": dec(btc, -4)},
        {"USD": dec(usd_principal, -2), "BTC": dec(btc_principal, -4)},
        {"USD": dec(usd_interest, -4), "BTC": dec(btc_interest, -6)},
        {"USD": dec(frozen_usd, -2), "BTC": dec(frozen_btc, -4)},
        {"BTC-PERP": LinearExposure("BTC-PERP", dec(quantity, -1), dec(cost, -4))} if quantity else {},
        dec(reserve, -2), cash_deficits={"USD": dec(deficit, -2)})
    market = MarketSnapshot(11, NOW,
        {"USD": AssetSpec(D(1), D(1)), "BTC": AssetSpec(dec(spot), D(".8"))},
        {"BTC-PERP": InstrumentSpec(dec(mark), D(".1"), D(".05"))})
    catalog = ProductCatalog(7, {"BTC-PERP": ProductSpec(
        "BTC-PERP", ProductKind.LINEAR_PERPETUAL, "BTC", "USD", "USD",
        D(".0001"), D(".1"), D(0))})
    rules = PortfolioRules(13,
        {"USD": CollateralRule("USD", (CollateralTier(None, D(1)),), D(".8")),
         "BTC": CollateralRule("BTC", (CollateralTier(D(100), D(".8")),
                                                CollateralTier(None, D(".5"))), D(".5"))},
        {"USD": BorrowLimits("USD", D(20), D(".1"), D(".05"), D(1)),
         "BTC": BorrowLimits("BTC", D(1), D(".2"), D(".1"), D(".1"))},
        {"tier-1": LinearMarginRule("tier-1", D(".1"), D(".05"))}, D(50))
    return account, market, catalog, rules


def independent_values(account, market):
    """Direct two-asset valuation and exhaustive positive-quantity feasibility."""
    usd, btc = map(F, (account.gross_assets["USD"], account.gross_assets["BTC"]))
    locked_usd, locked_btc = map(F, (account.frozen_assets["USD"], account.frozen_assets["BTC"]))
    spot, mark = F(market.assets["BTC"].price), F(market.instruments["BTC-PERP"].mark_price)
    usd_debt = F(account.principal["USD"]) + F(account.interest["USD"])
    btc_debt = (F(account.principal["BTC"]) + F(account.interest["BTC"])) * spot
    principal = F(account.principal["USD"]) + F(account.principal["BTC"]) * spot
    interest = F(account.interest["USD"]) + F(account.interest["BTC"]) * spot
    deficit = F(account.cash_deficits["USD"])
    free_btc_notional = (btc - locked_btc) * spot
    btc_collateral = min(free_btc_notional, F(100)) * F(4, 5) + max(F(0), free_btc_notional - 100) / 2
    usd_collateral = usd - locked_usd
    collateral = usd_collateral + btc_collateral
    lending = usd_collateral * F(4, 5) + btc_collateral / 2
    exposure = account.positions.get("BTC-PERP")
    marked = F(exposure.quantity) * mark if exposure else F(0)
    pnl = marked - F(exposure.cost_basis) if exposure else F(0)
    debt = principal + interest + deficit
    equity = collateral - debt + pnl
    im = usd_debt / 10 + btc_debt / 5 + abs(marked) / 10
    mm = usd_debt / 20 + btc_debt / 10 + abs(marked) / 20
    available = equity - im - F(account.order_margin)
    borrowable, feasible_units = {}, {}
    for asset, price, step, upper, im_rate, mm_rate in (
            ("USD", F(1), F(1), 20, F(1, 10), F(1, 20)),
            ("BTC", spot, F(1, 10), 10, F(1, 5), F(1, 10))):
        valid = [0]
        # Check every representable positive quote in this finite domain.
        # In particular, the maximum is not obtained with floor/ceil algebra.
        for units in range(1, upper + 1):
            quantity, cap = units * step, upper * step
            value = quantity * price
            if (F(account.principal[asset]) + quantity <= cap and
                    debt + value <= 50 and debt + value <= lending and
                    available - value - value * im_rate >= 0 and
                    equity - value > mm + value * mm_rate):
                valid.append(units)
        feasible_units[asset] = valid
        borrowable[asset] = max(valid) * step
    return dict(accounting_equity=usd + btc * spot - debt + pnl,
                collateral_value=collateral, risk_equity=equity, loan_value=lending,
                principal_value=principal, interest_value=interest, debt_value=debt,
                unrealized_pnl=pnl, frozen_value=locked_usd + locked_btc * spot,
                initial_margin=im, maintenance_margin=mm, order_margin=F(account.order_margin),
                available_margin=available, cash_deficit_value=deficit,
                borrowable=borrowable,
                status="LIQUIDATION" if equity <= mm else "MARGIN_CALL" if available < 0 else "HEALTHY"), feasible_units


def deterministic_cases(count):
    """Fixed integer generator: no random dependency or Decimal input rounding."""
    state = 20261118
    def draw(limit):
        nonlocal state
        state = (1664525 * state + 1013904223) & 0xffffffff
        return state % limit
    for index in range(count):
        cash, btc = draw(20001), draw(30001)
        quantity = (-10, -1, 0, 1, 10)[draw(5)]
        entry = 50 + draw(101)
        dust = (-1, 0, 1)[draw(3)] if quantity else 0
        yield dict(cash=cash, btc=btc, frozen_usd=draw(cash + 1), frozen_btc=draw(btc + 1),
                   usd_principal=draw(2501), btc_principal=draw(15001),
                   usd_interest=draw(101), btc_interest=draw(101), deficit=draw(501),
                   quantity=quantity, cost=quantity * entry * 1000 + dust,
                   reserve=draw(1001), spot=1 + draw(200), mark=1 + draw(200))


class CrossDecimalEnumerationTests(unittest.TestCase):
    def setUp(self):
        self.completed_vectors = []

    def check(self, parameters):
        account, market, catalog, rules = models(**parameters)
        expected, feasible = independent_values(account, market)
        actual = calculate_cross_risk_decimal(account, market, catalog, rules, now=NOW)
        for name, value in expected.items():
            if name == "borrowable":
                self.assertEqual({a: F(v) for a, v in actual.borrowable.items()}, value)
            elif name == "status":
                self.assertEqual(actual.status, value)
            else:
                self.assertEqual(F(getattr(actual, name)), value, name)
        self.assertEqual((actual.rule_id, actual.rule_version, actual.catalog_version, actual.market_version),
                         (rules.rule_id, 13, 7, 11))
        self.assertEqual(actual.market_id, "market-11@" + NOW.isoformat())
        # Finite exact values can be archived by a future retained entry; no
        # production calls or side effects are introduced by this test module.
        self.completed_vectors.append(dict(inputs=parameters, feasible_units=feasible,
            expected={k: ({a: str(v) for a, v in x.items()} if k == "borrowable" else str(x))
                      for k, x in expected.items()},
            actual={k: ({a: str(F(v)) for a, v in actual.borrowable.items()} if k == "borrowable"
                        else actual.status if k == "status" else str(F(getattr(actual, k))))
                    for k in expected}))

    def test_512_seeded_values_and_exhaustively_maximal_quotes(self):
        for index, parameters in enumerate(deterministic_cases(512)):
            with self.subTest(index=index):
                self.check(parameters)
        self.assertEqual(len(self.completed_vectors), 512)

    def test_collateral_tier_crossing_and_full_freeze(self):
        for btc in (9999, 10000, 10001):
            for frozen in (0, btc):
                with self.subTest(btc=btc, frozen=frozen):
                    self.check(dict(btc=btc, frozen_btc=frozen, spot=100))
        self.assertEqual(len(self.completed_vectors), 6)

    def test_maintenance_equality_and_order_reserve_boundaries(self):
        for cash in (0, 500, 501, 1101):
            for reserve in (0, 300):
                with self.subTest(cash=cash, reserve=reserve):
                    self.check(dict(cash=cash, btc=0, quantity=10, cost=1000000, reserve=reserve))
        self.assertEqual(len(self.completed_vectors), 8)

    def test_hostile_decimal_context_uses_independent_exact_oracle(self):
        with localcontext() as context:
            context.prec = 2
            context.traps[Inexact] = context.traps[Rounded] = True
            for index, parameters in enumerate(deterministic_cases(8)):
                with self.subTest(index=index):
                    self.check(parameters)
        self.assertEqual(len(self.completed_vectors), 8)

    def test_zero_rate_strict_borrow_boundary_is_not_inclusive(self):
        for cash, maximum in ((1000, 9), (1001, 10)):
            with self.subTest(cash=cash):
                account, market, catalog, rules = models(cash=cash, btc=0)
                rules = replace(rules, collaterals={**rules.collaterals,
                    "USD": CollateralRule("USD", (CollateralTier(None, D(1)),), D(1))},
                    borrow_limits={"USD": BorrowLimits("USD", D(20), D(0), D(0), D(1))})
                equity = F(cash, 100)
                feasible = [n for n in range(21) if n <= equity and (n == 0 or equity - n > 0)]
                self.assertEqual(max(feasible), maximum)
                actual = calculate_cross_risk_decimal(account, market, catalog, rules, now=NOW)
                self.assertEqual(actual.borrowable["USD"], D(maximum))
                self.completed_vectors.append(dict(inputs=dict(cash=cash, zero_rate_boundary=True),
                    feasible_units={"USD": feasible}, expected={"borrowable_USD": str(maximum)},
                    actual={"borrowable_USD": str(F(actual.borrowable["USD"]))}))
        self.assertEqual(len(self.completed_vectors), 2)


if __name__ == "__main__":
    unittest.main()
