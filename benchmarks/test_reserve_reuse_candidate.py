"""Four fixed arithmetic-only contracts; no service/SQLite import or SQL.

Expected values use a separately expressed rational oracle and hand cases.
This does not prove admission, freshness, product capability or crash safety.
"""
from dataclasses import replace
from decimal import Decimal as D, Inexact, Rounded, localcontext
from fractions import Fraction as F
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from uta.reserve_kernel import ReserveInputs, ReserveKernel


def value(**changes):
    fields = dict(quantity=D(1), filled_quantity=D(0), limit_price=D(100),
                  mark_price=D(100), reduce_only=False, initial_margin_rate=D('.1'),
                  fee_notional=D(0), charged_fee=D(0), fee_rate=D('.0004'), usd_scale=2)
    fields.update(changes)
    return ReserveInputs(**fields)


def independent(v):
    outstanding = F(v.quantity) - F(v.filled_quantity)
    price, quote = F(v.limit_price), F(v.mark_price)
    im = F(0) if v.reduce_only else abs(outstanding) * max(price, quote) * F(v.initial_margin_rate)
    adverse = max(F(0), outstanding * (price - quote))
    exact_units = (F(v.fee_notional) + abs(outstanding) * price) * F(v.fee_rate) * 10**v.usd_scale
    whole, residue = divmod(exact_units, 1)
    cumulative = F(int(whole) + bool(residue), 10**v.usd_scale)
    return im + adverse + cumulative - F(v.charged_fee)


class ReserveReuseContracts(unittest.TestCase):
    def test_manual_cumulative_fee_signed_and_zero_cases(self):
        cases = [
            (value(), '10.04'),
            (value(quantity=D(2), filled_quantity=D('.5'), limit_price=D(110),
                   fee_notional=D(25), charged_fee=D('.01')), '31.57'),
            (value(limit_price=D(101)), '11.15'),
            (value(limit_price=D(101), usd_scale=8), '11.1404'),
            (value(limit_price=D(102)), '12.25'),
            (value(limit_price=D(101), mark_price=D(120)), '12.05'),
            (value(quantity=D(-1), limit_price=D(99)), '11.04'),
            (value(quantity=D(-1), limit_price=D(99), reduce_only=True), '1.04'),
            (value(filled_quantity=D('.99'), fee_notional=D(99), charged_fee=D('.04')), '.1'),
            (value(filled_quantity=D(1), fee_notional=D(100), charged_fee=D('.04')), '0'),
            (value(quantity=D(0)), '0'),
            # Pure arithmetic must preserve a negative carry. This synthetic
            # overpaid state is outside native order admission, not a refund.
            (value(quantity=D(0), charged_fee=D('.01')), '-.01'),
        ]
        kernel = ReserveKernel(128)
        for supplied, expected in cases:
            with self.subTest(supplied=supplied):
                self.assertEqual(independent(supplied), F(expected))
                self.assertEqual(F(kernel.calculate(supplied)), F(expected))
                self.assertEqual(F(kernel.calculate(supplied)), F(expected))

    def test_all_ten_economic_key_inputs_remain_exact(self):
        base = value(quantity=D(2), filled_quantity=D('.5'), limit_price=D(101),
                     fee_notional=D(50), charged_fee=D('.02'), usd_scale=8)
        changes = dict(quantity=D('2.25'), filled_quantity=D('.75'), limit_price=D(102),
                       mark_price=D(120), reduce_only=True, initial_margin_rate=D('.2'),
                       fee_notional=D(55), charged_fee=D('.01'), fee_rate=D('.001'), usd_scale=2)
        kernel = ReserveKernel(128)
        self.assertEqual(F(kernel.calculate(base)), independent(base))
        for field, changed in changes.items():
            supplied = replace(base, **{field: changed})
            with self.subTest(field=field):
                self.assertEqual(F(kernel.calculate(supplied)), independent(supplied))
                self.assertEqual(F(kernel.calculate(base)), independent(base))
        self.assertEqual(kernel.stats(), dict(capacity=128, size=11, hits=10, misses=11, evictions=0))

    def test_lru_eviction_and_numeric_equal_keys(self):
        kernel = ReserveKernel(2)
        a, b, c = value(), value(limit_price=D(101)), value(limit_price=D(102))
        for supplied, expected in zip((a, b, a, c, b), ('10.04', '11.15', '10.04', '12.25', '11.15')):
            self.assertEqual(F(kernel.calculate(supplied)), F(expected))
        self.assertEqual(kernel.stats(), dict(capacity=2, size=2, hits=1, misses=4, evictions=2))
        same = replace(b, quantity=D('1.000'), mark_price=D('100.00'))
        self.assertEqual(F(kernel.calculate(same)), independent(b))
        self.assertEqual(kernel.stats()['hits'], 2)
        # Direct capacity0 kernel computes misses. Native service capacity0
        # bypasses this kernel, so its diagnostic counters instead stay zero.
        disabled = ReserveKernel(0)
        for _ in range(2):
            self.assertEqual(F(disabled.calculate(a)), independent(a))
        self.assertEqual(disabled.stats(), dict(capacity=0, size=0, hits=0, misses=2, evictions=0))

    def test_exact_arithmetic_ignores_ambient_context_and_failed_math_is_not_cached(self):
        kernel = ReserveKernel(128)
        supplied = value(quantity=D('1.12345678'), limit_price=D('101.12345678'), usd_scale=8)
        expected = independent(supplied)
        with localcontext() as context:
            context.prec, context.Emax, context.Emin = 1, 2, -2
            context.traps[Inexact] = context.traps[Rounded] = True
            self.assertEqual(F(kernel.calculate(supplied)), expected)
            self.assertEqual(F(kernel.calculate(supplied)), expected)
        prior = kernel.stats()
        with self.assertRaises((ValueError, OverflowError)):
            kernel.calculate(replace(supplied, mark_price=D('NaN')))
        self.assertEqual(kernel.stats()['size'], prior['size'])
        self.assertEqual(kernel.stats()['hits'], prior['hits'])
        self.assertEqual(kernel.stats()['misses'], prior['misses'] + 1)


if __name__ == '__main__':
    forbidden = {'sqlite3', '_sqlite3', 'uta.service', 'uta.storage', 'subprocess', 'multiprocessing'}
    if forbidden & sys.modules.keys():
        raise RuntimeError('arithmetic-only scope imported a forbidden module')
    unittest.main()
