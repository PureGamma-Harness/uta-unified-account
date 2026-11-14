import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D, Inexact, localcontext

from uta.bridge import calculate_shadow_risk, shadow_to_account
from uta.market import MarketSnapshot
from uta.migration import MigrationError, build_shadow
from uta.models import AssetSpec, InstrumentSpec, RiskInputError


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 14, tzinfo=timezone.utc)
        source = {"account_id": "classic", "version": 1, "captured_at": self.now.isoformat(),
                  "compartments": {
                      "spot": {"balances": [{"asset": "USD", "free": "100.01", "locked": "10.02",
                                               "borrowed": "0", "interest": "0"}]},
                      "margin": {"balances": [{"asset": "USD", "free": "20.03", "locked": "0",
                                                 "borrowed": "80.04", "interest": ".05"}]},
                      "futures": {"balances": [], "positions": [
                          {"symbol": "BTC", "quantity": "2", "entry_price": "10"}]}}}
        self.shadow = build_shadow(source, now=self.now)
        self.market = MarketSnapshot(1, self.now, {"USD": AssetSpec(D(1), D(".5"))},
                                     {"BTC": InstrumentSpec(D(11), D(".1"), D(".05"))})

    def test_gross_assets_liabilities_and_reserves_are_preserved(self):
        account = shadow_to_account(self.shadow, open_order_margin=D(3), now=self.now)
        self.assertEqual(account.balances["USD"], D("130.06"))
        self.assertEqual(account.liabilities["USD"], D("80.09"))
        risk = calculate_shadow_risk(self.shadow, self.market, open_order_margin=D(3), now=self.now)
        self.assertEqual(risk.equity, D("-13.06"))
        self.assertEqual(risk.available_margin, D("-18.26"))

    def test_no_implicit_zero_order_reserve(self):
        with self.assertRaises(TypeError):
            shadow_to_account(self.shadow, now=self.now)
        with self.assertRaises(RiskInputError):
            shadow_to_account(self.shadow, open_order_margin=D(-1), now=self.now)

    def test_both_source_and_market_must_still_be_fresh(self):
        with self.assertRaises(MigrationError):
            shadow_to_account(self.shadow, open_order_margin=D(0), now=self.now + timedelta(seconds=31))
        with self.assertRaises(RiskInputError):
            calculate_shadow_risk(self.shadow, self.market, open_order_margin=D(0),
                                  now=self.now + timedelta(seconds=6))

    def test_corrupt_shadow_cannot_be_used_as_reconciled_risk(self):
        for bad in (replace(self.shadow, source_digest="0" * 64),
                    replace(self.shadow, balances=self.shadow.balances + self.shadow.balances),
                    replace(self.shadow, balances=(replace(self.shadow.balances[0], compartment="other"),))):
            with self.subTest(bad=bad), self.assertRaises(MigrationError):
                shadow_to_account(bad, open_order_margin=D(0), now=self.now)

    def test_exact_aggregation_ignores_low_precision_and_inexact_traps(self):
        with localcontext() as context:
            context.prec = 1
            context.traps[Inexact] = True
            account = shadow_to_account(self.shadow, open_order_margin=D(0), now=self.now)
            self.assertEqual(account.balances["USD"], D("130.06"))
            self.assertEqual(account.liabilities["USD"], D("80.09"))


if __name__ == "__main__":
    unittest.main()
