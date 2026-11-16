"""Independent exact-money and durable-command contract checks.

All fixtures are synthetic. Expected balances and capacity use integer minor
units or Fraction, never production valuation/reserve/admission helpers.
"""
from decimal import Decimal as D, Inexact, Rounded, localcontext
from fractions import Fraction as F
import unittest

from uta.ledger import Ledger, LedgerError, Posting
from formal.explore_durable_commands import explore


def minor_units(value, scale):
    return D((int(value < 0), tuple(map(int, str(abs(value)))), -scale))


class IndependentReplayPrecisionTests(unittest.TestCase):
    def test_original_precision_replays_exactly_and_keeps_future_balance_limit(self):
        for width in (38, 40, 60):
            scale, maximum = 18, 10**width - 1
            amount, one = minor_units(maximum, scale), minor_units(1, scale)
            ledger = Ledger({'USD': scale}, unit_digits=width)
            original = [Posting('customer', 'USD', amount),
                        Posting('source', 'USD', amount.copy_negate())]
            ledger.post('capital', original)
            ledger.post('one-unit-payment', [Posting('customer', 'USD', one.copy_negate()),
                                             Posting('merchant', 'USD', one)])
            with self.subTest(width=width), localcontext() as context:
                context.prec, context.Emax, context.Emin = 1, 2, -2
                context.traps[Inexact] = context.traps[Rounded] = True
                restored = Ledger.replay({'USD': scale}, ledger.journal(), unit_digits=width)
                self.assertEqual(F(restored.balance('customer', 'USD')), F(maximum - 1, 10**scale))
                self.assertEqual(F(restored.balance('merchant', 'USD')), F(1, 10**scale))
                self.assertEqual(F(restored.balance('source', 'USD')), F(-maximum, 10**scale))
                self.assertEqual(restored.journal(), ledger.journal())
                self.assertIs(restored.post('capital', list(reversed(original))), restored.journal()[0])
                before = restored.journal()
                two = minor_units(2, scale)
                with self.assertRaisesRegex(LedgerError, 'balance exceeds supported range'):
                    restored.post('overflow', [Posting('customer', 'USD', two),
                                               Posting('new-source', 'USD', two.copy_negate())])
                self.assertEqual(restored.journal(), before)
                self.assertEqual(F(restored.balance('customer', 'USD')), F(maximum - 1, 10**scale))

    def test_wide_history_cannot_implicitly_expand_default_precision(self):
        amount = minor_units(10**40 - 1, 18)
        ledger = Ledger({'USD': 18}, unit_digits=60)
        ledger.post('wide', [Posting('customer', 'USD', amount),
                             Posting('source', 'USD', amount.copy_negate())])
        with self.assertRaises(LedgerError):
            Ledger.replay({'USD': 18}, ledger.journal())

    def test_replay_rejects_invalid_precision_instead_of_inferencing_history(self):
        for width in (True, 37, 61, 40.0, '40', None):
            with self.subTest(width=width), self.assertRaises(LedgerError):
                Ledger.replay({'USD': 18}, (), unit_digits=width)


class IndependentDurableProtocolModelTests(unittest.TestCase):
    def test_safe_bounded_protocol_and_four_negative_controls(self):
        safe = explore()
        self.assertIsNone(safe['violation'])
        self.assertEqual((safe['states'], safe['transitions']), (817, 2372))
        for mutant in ('early_accept', 'split_terminal', 'duplicate_retry', 'skip_fence'):
            with self.subTest(mutant=mutant):
                result = explore(mutant)
                self.assertIsNotNone(result['violation'])
                self.assertTrue(result['counterexample'])
