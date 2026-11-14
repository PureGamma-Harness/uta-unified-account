import unittest
from decimal import Decimal as D

from uta.models import Account, AssetSpec, InstrumentSpec, Position, RiskInputError
from uta.risk import calculate_risk, check_order


class RiskEngineTest(unittest.TestCase):
    def setUp(self):
        self.assets = {
            'BTC': AssetSpec(D('100'), D('.8')),
            'USD': AssetSpec(D('1'), D('1')),
        }
        self.instruments = {
            'BTC-PERP': InstrumentSpec(D('100'), D('.1'), D('.05')),
        }
        self.account = Account({'BTC': D('1'), 'USD': D('-10')},
                               {'BTC-PERP': Position('BTC-PERP', D('2'), D('80'))},
                               D('3'))

    def test_collateral_liability_unrealized_pnl_and_margins(self):
        r = calculate_risk(self.account, self.assets, self.instruments)
        self.assertEqual(r.equity, D('110'))
        self.assertEqual(r.initial_margin, D('20'))
        self.assertEqual(r.maintenance_margin, D('10'))
        self.assertEqual(r.available_margin, D('87'))
        self.assertEqual(r.margin_ratio, D('11'))

    def test_negative_asset_balance_is_not_discounted(self):
        account = Account({'BTC': D('-1')})
        r = calculate_risk(account, self.assets, {})
        self.assertEqual(r.equity, D('-100'))
        self.assertIsNone(r.margin_ratio)

    def test_marked_short_position(self):
        account = Account({'USD': D('100')},
                          {'BTC-PERP': Position('BTC-PERP', D('-2'), D('120'))})
        r = calculate_risk(account, self.assets, self.instruments)
        self.assertEqual(r.equity, D('140'))
        self.assertEqual(r.initial_margin, D('20'))

    def test_order_reduction_accounts_for_execution_and_fee(self):
        result = check_order(self.account, self.assets, self.instruments,
                             symbol='BTC-PERP', quantity=D('-1'),
                             execution_price=D('95'), fee_rate=D('.01'))
        self.assertTrue(result.accepted)
        self.assertEqual(result.projected_equity, D('104.05'))
        self.assertEqual(result.projected_initial_margin, D('10'))
        self.assertEqual(result.projected_available_margin, D('91.05'))

    def test_crossing_position_uses_resulting_absolute_notional(self):
        result = check_order(self.account, self.assets, self.instruments,
                             symbol='BTC-PERP', quantity=D('-5'), execution_price=D('100'))
        self.assertEqual(result.projected_initial_margin, D('30'))
        self.assertEqual(result.projected_available_margin, D('77'))

    def test_large_order_is_rejected(self):
        result = check_order(self.account, self.assets, self.instruments,
                             symbol='BTC-PERP', quantity=D('20'), execution_price=D('100'))
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, 'insufficient initial margin')

    def test_missing_specs_fail_closed(self):
        with self.assertRaises(RiskInputError):
            calculate_risk(self.account, {}, self.instruments)
        with self.assertRaises(RiskInputError):
            calculate_risk(self.account, self.assets, {})
        with self.assertRaises(RiskInputError):
            check_order(Account(), {}, {}, symbol='X', quantity=D('1'), execution_price=D('1'))

    def test_invalid_values_rejected(self):
        for invalid in (D('NaN'), D('Infinity'), 1.5):
            with self.subTest(invalid=invalid), self.assertRaises(RiskInputError):
                Account({'USD': invalid})
        with self.assertRaises(RiskInputError):
            AssetSpec(D('1'), D('1.1'))
        with self.assertRaises(RiskInputError):
            InstrumentSpec(D('1'), D('.05'), D('.1'))
        with self.assertRaises(RiskInputError):
            Position('BTC-PERP', D('1'), D('0'))
        with self.assertRaises(RiskInputError):
            Account(positions={'A': Position('B', D('1'), D('1'))})
        with self.assertRaises(RiskInputError):
            check_order(self.account, self.assets, self.instruments,
                        symbol='BTC-PERP', quantity=D('0'), execution_price=D('100'))


if __name__ == '__main__':
    unittest.main()
