"""Independent oracle and human-readable golden case, not exchange parity tests."""
import json
import random
import unittest
from decimal import Decimal as D, localcontext
from fractions import Fraction
from pathlib import Path

from reference_calculator import fill, value
from uta.models import Account, AssetSpec, InstrumentSpec, Position, RiskInputError
from uta.risk import calculate_risk, check_order


def decimal_fraction(value):
    with localcontext() as ctx:
        ctx.prec = 40
        return D(value.numerator) / D(value.denominator)


def build(account, assets, instruments):
    return (Account({k: D(v) for k, v in account['balances'].items()},
                    {k: Position(k, D(v[0]), D(v[1])) for k, v in account['positions'].items()}, D(account['reserve']),
                    {k: D(v) for k, v in account.get('liabilities', {}).items()}),
            {k: AssetSpec(*map(D, v)) for k, v in assets.items()},
            {k: InstrumentSpec(*map(D, v)) for k, v in instruments.items()})


class ReferenceValidationTests(unittest.TestCase):
    def test_hand_computed_golden_case(self):
        fixture = json.loads((Path(__file__).parent / 'fixtures/risk_golden.json').read_text())
        account, assets, instruments = build(fixture['account'], fixture['assets'], fixture['instruments'])
        expected = fixture['expected']
        result = calculate_risk(account, assets, instruments)
        self.assertEqual((result.equity, result.initial_margin, result.maintenance_margin, result.available_margin),
                         tuple(D(expected[k]) for k in ('equity', 'initial', 'maintenance', 'available')))
        independent = value(fixture['account'], fixture['assets'], fixture['instruments'])
        self.assertEqual(independent, tuple(Fraction(expected[k]) for k in ('equity', 'initial', 'maintenance', 'available')))
        order = fixture['order']
        actual = check_order(account, assets, instruments, symbol=order['symbol'], quantity=D(order['quantity']),
                             execution_price=D(order['execution']), fee_rate=D(order['fee_rate']))
        projected = fill(fixture['account'], fixture['assets'], fixture['instruments'], order['symbol'], order['quantity'], order['execution'], order['fee_rate'])
        self.assertEqual(projected, tuple(Fraction(order[k]) for k in ('expected_equity', 'expected_initial', 'expected_available')))
        self.assertEqual((actual.projected_equity, actual.projected_initial_margin, actual.projected_available_margin),
                         tuple(D(order[k]) for k in ('expected_equity', 'expected_initial', 'expected_available')))
        self.assertEqual(actual.accepted, order['accepted'])

    def test_seeded_differential_order_checks(self):
        rng = random.Random(8231)
        for _ in range(500):
            old_qty = rng.randint(-40, 40)
            order_qty = rng.choice([n for n in range(-40, 41) if n])
            acct = {'balances': {'USD': str(rng.randint(-1000, 5000))},
                    'positions': {'X': [str(old_qty), str(rng.randint(1, 200))]},
                    'reserve': str(rng.randint(0, 10))}
            assets = {'USD': ['1', '1']}
            specs = {'X': [str(rng.randint(1, 200)), '0.1', '0.05']}
            execution = str(rng.randint(1, 200))
            fee = '0.001'
            account, asset_models, instrument_models = build(acct, assets, specs)
            expected = fill(acct, assets, specs, 'X', str(order_qty), execution, fee)
            actual = check_order(account, asset_models, instrument_models, symbol='X',
                                 quantity=D(order_qty), execution_price=D(execution), fee_rate=D(fee))
            for a, e in zip((actual.projected_equity, actual.projected_initial_margin, actual.projected_available_margin), expected):
                self.assertLessEqual(abs(a - decimal_fraction(e)), D('0.000000000000000001'))
            self.assertEqual(actual.accepted, expected[2] >= 0)

    def test_arithmetic_ignores_callers_low_decimal_precision(self):
        assets = {'USD': AssetSpec(D('1'), D('1'))}
        instrument = {'X': InstrumentSpec(D('100'), D('0.1'), D('0.05'))}
        with localcontext() as ctx:
            ctx.prec = 2
            account = Account({'USD': D('9999')}, {'X': Position('X', D('1'), D('100'))})
            result = calculate_risk(account, assets, instrument)
            self.assertEqual(result.equity, D('9999'))
            self.assertEqual(result.available_margin, D('9989'))
            projected = check_order(account, assets, instrument, symbol='X', quantity=D('1'),
                                    execution_price=D('100'), fee_rate=D('0.001'))
            self.assertEqual(projected.projected_equity, D('9998.9'))
            self.assertEqual(projected.projected_available_margin, D('9978.9'))

    def test_ratio_rounding_is_fixed_at_34_significant_digits(self):
        account = Account({'USD': D('1')}, {'X': Position('X', D('3'), D('1'))})
        assets = {'USD': AssetSpec(D('1'), D('1'))}
        specs = {'X': InstrumentSpec(D('1'), D('1'), D('1'))}
        with localcontext() as ctx:
            ctx.prec = 2
            self.assertEqual(calculate_risk(account, assets, specs).margin_ratio,
                             D('0.3333333333333333333333333333333333'))

    def test_out_of_range_inputs_rejected(self):
        for value in (D('1e101'), D('1e-101'), D('1' * 81)):
            with self.subTest(value=value), self.assertRaises(RiskInputError):
                Account({'USD': value})


if __name__ == '__main__':
    unittest.main()
