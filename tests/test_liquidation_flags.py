import copy
import unittest
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

from uta.liquidation import (ActionType, LiquidationController, Phase,
                             PositionReduction, TimedRisk)


@dataclass(frozen=True)
class Risk:
    equity: D
    maintenance_margin: D


class LiquidationFlagTests(unittest.TestCase):
    invalid_flags = ("false", "true", "0", 1, 0, 1.0, 0.0, D(1),
                     None, "", [], [False], {}, {"success": False})

    def setUp(self):
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def snapshot(self, *, at=None, healthy=False, complete=True):
        return TimedRisk(Risk(D(120 if healthy else 100), D(100)),
                         at or self.now, complete)

    def pending(self, kind):
        controller = LiquidationController("flags")
        action = controller.next_action(self.snapshot(), now=self.now)
        at = self.now
        if kind == ActionType.REDUCE_POSITION:
            self.assertTrue(controller.acknowledge(action.action_id, success=True, now=at))
            at += timedelta(seconds=1)
            action = controller.next_action(
                self.snapshot(at=at), now=at,
                reduction=PositionReduction("BTC", D("-2"), D("0.5")))
        self.assertEqual(action.kind, kind)
        return controller, action, at

    def test_non_boolean_completeness_blocks_without_losing_pending_action(self):
        later = self.now + timedelta(seconds=1)
        for flag in self.invalid_flags:
            for healthy in (True, False):
                with self.subTest(flag=repr(flag), type=type(flag).__name__, healthy=healthy):
                    controller = LiquidationController("flags")
                    valid = self.snapshot(healthy=healthy)
                    pending = controller.next_action(valid, now=self.now)
                    self.assertEqual(controller.trading_allowed, healthy)

                    self.assertIsNone(controller.next_action(
                        self.snapshot(at=later, healthy=healthy, complete=flag), now=later))
                    self.assertEqual(controller.phase, Phase.BLOCKED)
                    self.assertFalse(controller.trading_allowed)
                    self.assertIs(controller.pending_action, pending)

                    # Invalid input must not advance the accepted snapshot time.
                    self.assertIs(controller.next_action(valid, now=later), pending)
                    self.assertEqual(controller.trading_allowed, healthy)
                    self.assertEqual(controller.phase, Phase.NORMAL if healthy else Phase.CANCEL_ORDERS)

    def test_non_boolean_success_never_acknowledges_pending_actions(self):
        for flag in self.invalid_flags:
            for kind in (ActionType.CANCEL_ALL_ORDERS, ActionType.REDUCE_POSITION):
                with self.subTest(flag=repr(flag), type=type(flag).__name__, kind=kind):
                    controller, action, at = self.pending(kind)
                    before = copy.deepcopy(vars(controller))
                    with self.assertRaisesRegex(ValueError, "boolean success"):
                        controller.acknowledge(action.action_id, success=flag, now=at)
                    self.assertEqual(vars(controller), before)
                    self.assertIs(controller.pending_action, action)

                    self.assertFalse(controller.acknowledge(action.action_id, success=False, now=at))
                    self.assertEqual(vars(controller), before)
                    self.assertTrue(controller.acknowledge(action.action_id, success=True, now=at))
                    self.assertIsNone(controller.pending_action)
                    self.assertEqual(controller.phase, Phase.REDUCE_EXPOSURE)
                    completed = copy.deepcopy(vars(controller))
                    self.assertFalse(controller.acknowledge(action.action_id, success=True, now=at))
                    self.assertEqual(vars(controller), completed)

    def test_invalid_success_does_not_hide_behind_duplicate_acknowledgements(self):
        for flag in self.invalid_flags:
            with self.subTest(flag=repr(flag), type=type(flag).__name__):
                controller, action, at = self.pending(ActionType.CANCEL_ALL_ORDERS)
                self.assertTrue(controller.acknowledge(action.action_id, success=True, now=at))
                completed = copy.deepcopy(vars(controller))
                with self.assertRaisesRegex(ValueError, "boolean success"):
                    controller.acknowledge(action.action_id, success=flag, now=at)
                self.assertEqual(vars(controller), completed)
                for success in (True, False):
                    self.assertFalse(controller.acknowledge(action.action_id, success=success, now=at))
                    self.assertEqual(vars(controller), completed)


if __name__ == "__main__":
    unittest.main()
