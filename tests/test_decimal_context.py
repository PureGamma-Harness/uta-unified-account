import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D, Inexact, ROUND_UP, localcontext

from uta.liquidation import LiquidationController, PositionReduction, TimedRisk
from uta.reservations import ReservationBook
from uta.risk import RiskSnapshot


class DecimalContextTests(unittest.TestCase):
    def test_reservations_ignore_caller_exponent_limits_and_traps(self):
        with localcontext() as ctx:
            ctx.prec = 1
            ctx.Emax = 2
            ctx.Emin = -2
            ctx.traps[Inexact] = True
            book = ReservationBook(D("1000"))
            book.reserve("order", D("100.123456"), expected_version=0)
            self.assertEqual(book.snapshot().available, D("899.876544"))
            book.release("order", expected_version=1)
            self.assertEqual(book.snapshot().available, D("1000"))

    def test_low_precision_cannot_round_position_up_and_allow_over_reduction(self):
        now = datetime(2026, 11, 14, tzinfo=timezone.utc)
        c = LiquidationController("account")
        risk = RiskSnapshot(D("1"), D("10"), D("10"), D("0"), D("-9"), D(".1"))
        action = c.next_action(TimedRisk(risk, now), now=now)
        c.acknowledge(action.action_id, success=True, now=now)
        later = now + timedelta(seconds=1)
        with localcontext() as ctx:
            ctx.prec = 1
            ctx.rounding = ROUND_UP
            with self.assertRaises(ValueError):
                c.next_action(TimedRisk(risk, later), now=later,
                              reduction=PositionReduction("BTC", D("1.1"), D("1.2")))


if __name__ == "__main__":
    unittest.main()
