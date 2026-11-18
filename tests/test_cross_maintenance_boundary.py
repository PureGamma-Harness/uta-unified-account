"""Synthetic, memory-only maintenance boundary checks; no service constructor."""
from datetime import datetime, timezone
from decimal import Decimal as D, Inexact, Rounded, localcontext
import unittest

from uta.market import MarketSnapshot
from uta.models import Account, AssetSpec, InstrumentSpec, Position
from uta.portfolio import (CollateralRule, CollateralTier, LinearExposure,
                           LinearMarginRule, LoanAccount, PortfolioRules,
                           calculate_cross_risk)
from uta.products import ProductCatalog, ProductKind, ProductSpec, TradingStatus
from uta.risk import calculate_risk
from uta.service import ExchangeService, ServiceError


NOW = datetime(2026, 11, 18, 6, tzinfo=timezone.utc)
COMPLETED_CASES = []


class CrossMaintenanceBoundaryTests(unittest.TestCase):
    def fixture(self, mm="0.1"):
        market = MarketSnapshot(7, NOW, {"USD": AssetSpec(D(1), D(1))},
                                {"X": InstrumentSpec(D(100), D("0.1"), D(mm))})
        catalog = ProductCatalog(3, {"X": ProductSpec(
            "X", ProductKind.LINEAR_PERPETUAL, "BTC", "USD", "USD",
            D("0.01"), D("0.00000001"), D(0), status=TradingStatus.ACTIVE)})
        rules = PortfolioRules(5,
            {"USD": CollateralRule("USD", (CollateralTier(None, D(1)),), D(1))},
            {}, {"tier-1": LinearMarginRule("tier-1", D("0.1"), D(mm))}, D(1000))
        # These exact, side-effect-free methods do not use database state.
        service = ExchangeService.__new__(ExchangeService)
        service.scales = {"USD": 8}
        service.fee_rate = D("0.0004")
        service.product_catalog, service.portfolio_rules = catalog, rules
        return service, market, catalog, rules

    def risk(self, values, cash, positions=None, deficit=None):
        _, market, catalog, rules = values
        account = LoanAccount({"USD": D(cash)},
            positions={symbol: LinearExposure(symbol, quantity, cost)
                       for symbol, (quantity, cost) in (positions or {}).items()},
            cash_deficits={} if deficit is None else {"USD": D(deficit)})
        return calculate_cross_risk(account, market, catalog, rules, now=NOW)

    @staticmethod
    def projected(risk):
        return {"equity": str(risk.risk_equity), "maintenance_margin": str(risk.maintenance_margin)}

    def assert_rejected(self, risk):
        with self.assertRaises(ServiceError) as caught:
            ExchangeService._require_maintenance_surplus(self.projected(risk))
        self.assertEqual((caught.exception.code, caught.exception.status), ("insufficient_margin", 409))

    def test_equal_im_mm_fee_boundary_is_unsafe(self):
        values = self.fixture()
        service, market, _, _ = values
        order = {"symbol": "X", "quantity": "1", "filled_quantity": "0",
                 "limit_price": "100", "reduce_only": False}
        before = self.risk(values, "10.04")
        self.assertEqual(service._reserve_reference(order, market), D("10.04"))
        self.assertEqual(before.available_margin, D("10.04"))
        positions, pnl = service._project_fill({}, "X", D(1), D(100))
        self.assertEqual(positions, {"X": (D(1), D(100))})
        self.assertEqual(pnl, D(0))
        self.assertEqual(service._fee(D(1), D(100)), D("0.04"))
        after = self.risk(values, "10", positions)
        self.assertEqual((after.risk_equity, after.initial_margin, after.maintenance_margin,
                          after.available_margin, after.status),
                         (D(10), D(10), D(10), D(0), "LIQUIDATION"))
        self.assert_rejected(after)
        COMPLETED_CASES.append("full_fee_boundary")

    def test_im_equality_and_one_unit_maintenance_boundaries(self):
        # USD settlement has 8 fractional digits. Constants are hand computed.
        equal_rates = self.fixture()
        positions = {"X": (D(1), D(100))}
        for cash, accepted in (("9.99999999", False), ("10", False), ("10.00000001", True)):
            with self.subTest(cash=cash), localcontext() as context:
                context.prec = 2
                context.traps[Inexact] = context.traps[Rounded] = True
                result = self.risk(equal_rates, cash, positions)
                self.assertEqual(result.risk_equity, D(cash))
                self.assertEqual(result.maintenance_margin, D(10))
                if accepted:
                    ExchangeService._require_maintenance_surplus(self.projected(result))
                else:
                    self.assert_rejected(result)
                COMPLETED_CASES.append({"9.99999999": "unit_below", "10": "unit_equal", "10.00000001": "unit_above"}[cash])
        lower_mm = self.risk(self.fixture("0.05"), "10", positions)
        self.assertEqual((lower_mm.available_margin, lower_mm.maintenance_margin, lower_mm.status),
                         (D(0), D(5), "HEALTHY"))
        ExchangeService._require_maintenance_surplus(self.projected(lower_mm))
        COMPLETED_CASES.append("im_equal_mm_lower")

    def test_partial_fill_projection_retains_unsafe_final_boundary(self):
        values = self.fixture()
        service, _, _, _ = values
        first, pnl = service._project_fill({}, "X", D("0.5"), D(100))
        self.assertEqual(first, {"X": (D("0.5"), D(50))})
        self.assertEqual((pnl, service._fee(D("0.5"), D(100))), (D(0), D("0.02")))
        partial = self.risk(values, "10.02", first)
        self.assertEqual((partial.risk_equity, partial.maintenance_margin), (D("10.02"), D(5)))
        ExchangeService._require_maintenance_surplus(self.projected(partial))
        COMPLETED_CASES.append("partial_safe")
        final, pnl = service._project_fill(first, "X", D("0.5"), D(100))
        self.assertEqual((final, pnl), ({"X": (D(1), D(100))}, D(0)))
        self.assert_rejected(self.risk(values, "10", final))
        COMPLETED_CASES.append("partial_terminal_unsafe")

    def test_zero_maintenance_still_requires_positive_equity(self):
        values = self.fixture()
        for cash, deficit, accepted in (("0", None, False), ("0", "1", False), ("0.00000001", None, True)):
            with self.subTest(cash=cash, deficit=deficit):
                result = self.risk(values, cash, deficit=deficit)
                self.assertEqual(result.maintenance_margin, D(0))
                if accepted:
                    ExchangeService._require_maintenance_surplus(self.projected(result))
                else:
                    self.assert_rejected(result)
                COMPLETED_CASES.append("zero_mm_negative_equity" if deficit else
                                       "zero_mm_positive_equity" if accepted else "zero_mm_zero_equity")

    def test_reduce_only_keeps_its_independent_surplus_policy(self):
        current = {"equity": "9", "maintenance_margin": "10"}  # surplus -1
        ExchangeService._check_reduction_surplus(current, {"equity": "4", "maintenance_margin": "5"})
        COMPLETED_CASES.append("ro_same_deficit")
        ExchangeService._check_reduction_surplus(current, {"equity": "5", "maintenance_margin": "5"})
        COMPLETED_CASES.append("ro_improved_boundary")
        with self.assertRaises(ServiceError) as caught:
            ExchangeService._check_reduction_surplus(current, {"equity": "3", "maintenance_margin": "5"})
        self.assertEqual((caught.exception.code, caught.exception.status), ("unsafe_reduction", 409))
        COMPLETED_CASES.append("ro_worsening_reject")

    def test_legacy_reference_obeys_same_maintenance_trigger(self):
        for mm, accepted in (("0.1", False), ("0.05", True)):
            with self.subTest(mm=mm):
                risk = calculate_risk(
                    Account({"USD": D(10)}, {"X": Position("X", D(1), D(100))}),
                    {"USD": AssetSpec(D(1), D(1))},
                    {"X": InstrumentSpec(D(100), D("0.1"), D(mm))})
                self.assertEqual((risk.equity, risk.initial_margin, risk.available_margin),
                                 (D(10), D(10), D(0)))
                wire = {"equity": str(risk.equity), "maintenance_margin": str(risk.maintenance_margin)}
                if accepted:
                    ExchangeService._require_maintenance_surplus(wire)
                    COMPLETED_CASES.append("legacy_im_equal_mm_lower")
                else:
                    with self.assertRaises(ServiceError) as caught:
                        ExchangeService._require_maintenance_surplus(wire)
                    self.assertEqual((caught.exception.code, caught.exception.status), ("insufficient_margin", 409))
                    COMPLETED_CASES.append("legacy_equal_mm_reject")


if __name__ == "__main__":
    unittest.main()
