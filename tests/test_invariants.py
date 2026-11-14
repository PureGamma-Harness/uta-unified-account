"""Adversarial regressions for the reference liquidation and migration edges.

These checks use independent expected values rather than copying production
formulas, so changes cannot silently relax the recovery or input boundaries.
"""
import copy
import unittest
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D, Inexact, ROUND_DOWN, ROUND_UP, localcontext

from uta.liquidation import LiquidationController, Phase, TimedRisk
from uta.migration import MigrationError, build_shadow


NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)


@dataclass(frozen=True)
class ObservedRisk:
    equity: D
    maintenance_margin: D


def snapshot():
    return {
        "account_id": "classic-1", "version": 4,
        "captured_at": NOW.isoformat(),
        "compartments": {
            "spot": {"balances": [{"asset": "BTC", "free": "2", "locked": "0.1",
                                    "borrowed": "0", "interest": "0"}]},
            "margin": {"balances": []},
            "futures": {"balances": [], "positions": []},
        },
    }


class LiquidationSafetyInvariants(unittest.TestCase):
    def distressed_controller(self):
        controller = LiquidationController("acct", recovery_buffer=D("1.10"))
        cancel = controller.next_action(
            TimedRisk(ObservedRisk(D("100"), D("100")), NOW), now=NOW)
        controller.acknowledge(cancel.action_id, success=True, now=NOW)
        return controller

    def test_recovery_threshold_is_independent_of_decimal_context(self):
        # MM=100 and a 1.10 recovery buffer require equity strictly above 110.
        # Rounding 100 * 1.10 to one significant digit used to recover at 105.
        later = NOW + timedelta(seconds=1)
        for precision, rounding in ((1, ROUND_DOWN), (1, ROUND_UP), (3, ROUND_DOWN)):
            for equity, recovered in (("105", False), ("110", False), ("110.01", True)):
                with self.subTest(precision=precision, rounding=rounding, equity=equity):
                    controller = self.distressed_controller()
                    with localcontext() as context:
                        context.prec = precision
                        context.rounding = rounding
                        context.traps[Inexact] = True
                        controller.next_action(
                            TimedRisk(ObservedRisk(D(equity), D("100")), later), now=later)
                    self.assertEqual(controller.trading_allowed, recovered)
                    self.assertEqual(controller.phase,
                                     Phase.RECOVERED if recovered else Phase.REDUCE_EXPOSURE)

    def test_ack_requires_a_real_boolean_without_consuming_pending_action(self):
        for value in ("false", "true", 0, 1, None, [], {}):
            with self.subTest(value=value):
                controller = LiquidationController("acct")
                cancel = controller.next_action(
                    TimedRisk(ObservedRisk(D("100"), D("100")), NOW), now=NOW)
                with self.assertRaises(ValueError):
                    controller.acknowledge(cancel.action_id, success=value, now=NOW)
                self.assertEqual(controller.pending_action, cancel)
                self.assertTrue(controller.acknowledge(cancel.action_id, success=True, now=NOW))

    def test_complete_must_be_true_boolean_to_permit_trading(self):
        for complete in ("true", "false", 1, [], {}, None):
            with self.subTest(complete=complete):
                controller = LiquidationController("acct")
                self.assertIsNone(controller.next_action(
                    TimedRisk(ObservedRisk(D("1000"), D("100")), NOW, complete), now=NOW))
                self.assertEqual(controller.phase, Phase.BLOCKED)
                self.assertFalse(controller.trading_allowed)

    def test_extreme_risk_is_blocked_before_financial_arithmetic(self):
        for value in (D("1e101"), D("1e-101"), D("1" * 81)):
            with self.subTest(value=value):
                controller = LiquidationController("acct")
                self.assertIsNone(controller.next_action(
                    TimedRisk(ObservedRisk(value, D("1")), NOW), now=NOW))
                self.assertEqual(controller.phase, Phase.BLOCKED)
                self.assertFalse(controller.trading_allowed)

    def test_extreme_recovery_buffer_is_rejected(self):
        with self.assertRaises(ValueError):
            LiquidationController("acct", recovery_buffer=D("1e101"))


class MigrationSafetyInvariants(unittest.TestCase):
    def test_decimal_inputs_are_bounded_before_fixed_point_digest_expansion(self):
        for value in ("1e100001", "1e-100001", "9" * 10000):
            with self.subTest(value=value[:30]):
                raw = snapshot()
                raw["compartments"]["spot"]["balances"][0]["free"] = value
                with self.assertRaises(MigrationError):
                    build_shadow(raw, now=NOW)

    def test_identifiers_and_versions_are_bounded(self):
        bad = []
        raw = snapshot(); raw["account_id"] = "a" * 10000; bad.append(raw)
        raw = snapshot(); raw["version"] = 2 ** 128; bad.append(raw)
        raw = snapshot(); raw["compartments"]["spot"]["balances"][0]["asset"] = "X" * 10000; bad.append(raw)
        raw = snapshot(); raw["compartments"]["futures"]["positions"] = [
            {"symbol": "X" * 10000, "quantity": "1", "entry_price": "1"}]; bad.append(raw)
        for raw in bad:
            with self.subTest(account_id=raw["account_id"][:20], version=raw["version"]):
                with self.assertRaises(MigrationError):
                    build_shadow(raw, now=NOW)

    def test_rejected_input_cannot_mutate_supplied_snapshot(self):
        raw = snapshot()
        before = copy.deepcopy(raw)
        build_shadow(raw, now=NOW)
        self.assertEqual(raw, before)


if __name__ == "__main__":
    unittest.main()
