import unittest
from decimal import Decimal as D

from uta.api import evaluate
from uta.models import Account, AssetSpec, RiskInputError
from uta.risk import calculate_risk


class GrossLiabilityTests(unittest.TestCase):
    def test_asset_and_borrow_haircut_separately(self):
        # 1 BTC asset at $100 with 80% collateral factor; 0.5 BTC debt
        # is valued in full. Netting first would incorrectly produce $40.
        account = Account({'BTC': D('1')}, liabilities={'BTC': D('0.5')})
        specs = {'BTC': AssetSpec(D('100'), D('0.8'))}
        self.assertEqual(calculate_risk(account, specs, {}).equity, D('30'))
        self.assertEqual(evaluate('/risk', {
            'balances': {'BTC': '1'}, 'liabilities': {'BTC': '0.5'},
            'assets': {'BTC': {'price': '100', 'collateral_factor': '0.8'}}
        })['equity'], '30')

    def test_legacy_negative_balance_and_new_liabilities(self):
        specs = {'BTC': AssetSpec(D('100'), D('0.8'))}
        self.assertEqual(calculate_risk(Account({'BTC': D('-0.5')}), specs, {}).equity, D('-50'))
        self.assertEqual(calculate_risk(Account(liabilities={'BTC': D('0.5')}), specs, {}).equity, D('-50'))
        with self.assertRaises(RiskInputError):
            Account({'BTC': D('-0.5')}, liabilities={'BTC': D('0.5')})
        with self.assertRaises(RiskInputError):
            Account(liabilities={'BTC': D('-0.5')})
        with self.assertRaises(RiskInputError):
            calculate_risk(Account(liabilities={'BTC': D('0.5')}), {}, {})


if __name__ == '__main__':
    unittest.main()
