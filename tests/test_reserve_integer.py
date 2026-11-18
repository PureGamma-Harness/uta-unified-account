"""Compare a separate integer kernel against the unchanged exact reference."""
from dataclasses import replace
from decimal import Decimal, localcontext
import json
from pathlib import Path
import random
import unittest

from uta.reserve_integer import calculate_integer_reserve
from uta.reserve_kernel import ReserveInputs, calculate_reserve


ROOT = Path(__file__).resolve().parents[1]
DECIMAL_FIELDS = {"quantity", "filled_quantity", "limit_price", "mark_price",
                  "initial_margin_rate", "fee_notional", "charged_fee", "fee_rate"}


class IntegerReserveTests(unittest.TestCase):
    def inputs(self, values):
        return ReserveInputs(**{k: Decimal(v) if k in DECIMAL_FIELDS else v for k, v in values.items()})

    def check(self, values):
        expected, actual = calculate_reserve(values), calculate_integer_reserve(values)
        self.assertEqual(actual.as_tuple(), expected.as_tuple(), repr(values))
        self.assertEqual(str(actual), str(expected), repr(values))

    def test_frozen_manual_examples(self):
        cases = json.loads((ROOT/'evidence/reviews/reserve-integer-first/manual-cases.json').read_text())['cases']
        for case in cases:
            with self.subTest(case=case['name']):
                values = self.inputs(case['inputs'])
                actual = calculate_integer_reserve(values)
                self.assertEqual(actual, Decimal(case['expected_decimal']))
                self.check(values)

    def test_seeded_signed_decimal_differential_and_context_independence(self):
        rng = random.Random(20261117)
        for precision in (2, 9, 28):
            with localcontext() as context:
                context.prec = precision
                for index in range(1500):
                    def value():
                        return Decimal((rng.randrange(2), tuple(map(int, str(rng.randrange(100000)))), -rng.randrange(10)))
                    values = ReserveInputs(value(), value(), value(), value(), bool(rng.randrange(2)),
                                           value(), value(), value(), value(), rng.randrange(19))
                    self.check(values)

    def test_fast_domain_boundaries_and_exact_decimal_wire_shape(self):
        base = ReserveInputs(Decimal('1'), Decimal('0'), Decimal('100'), Decimal('100'), False,
                             Decimal('.1'), Decimal('0'), Decimal('0'), Decimal('.001'), 8)
        variants = ('0', '-0.000', '1E+18', '1E-18', '9'*38, '0.'+'0'*17+'1')
        for field in DECIMAL_FIELDS:
            for literal in variants:
                self.check(replace(base, **{field: Decimal(literal)}))

    def test_reference_fallback_values_and_exception_types(self):
        base = ReserveInputs(Decimal('1'), Decimal('0'), Decimal('100'), Decimal('100'), False,
                             Decimal('.1'), Decimal('0'), Decimal('0'), Decimal('.001'), 8)
        for value in (Decimal('1E-19'), Decimal('1E+19'), Decimal('9'*39), 1, '1'):
            self.check(replace(base, quantity=value))
        for value in (Decimal('NaN'), Decimal('Infinity'), Decimal('-Infinity')):
            values = replace(base, quantity=value)
            try:
                calculate_reserve(values)
            except Exception as expected:
                with self.assertRaises(type(expected)):
                    calculate_integer_reserve(values)
            else:
                self.fail('reference unexpectedly accepted nonfinite quantity')
        for scale in (True, -1, 19, 0.5):
            values = replace(base, usd_scale=scale)
            try:
                expected = calculate_reserve(values)
            except Exception as error:
                with self.assertRaises(type(error)):
                    calculate_integer_reserve(values)
            else:
                self.assertEqual(calculate_integer_reserve(values).as_tuple(), expected.as_tuple())

    def test_subclasses_delegate_without_reading_unused_margin(self):
        class ConditionalMargin(ReserveInputs):
            def __getattribute__(self, name):
                if name == 'initial_margin_rate':
                    raise RuntimeError('synthetic margin must not be read in reduce-only')
                return super().__getattribute__(name)
        values = ConditionalMargin(Decimal('1'), Decimal('0'), Decimal('100'), Decimal('100'),
                                    True, Decimal('.1'), Decimal('0'), Decimal('0'), Decimal('.001'), 8)
        self.assertEqual(calculate_integer_reserve(values).as_tuple(), calculate_reserve(values).as_tuple())
        self.assertEqual(calculate_integer_reserve(values), Decimal('.1'))


if __name__ == '__main__':
    unittest.main()
