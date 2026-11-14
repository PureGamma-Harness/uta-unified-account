"""Reviewable scenarios and invariants for the linear PM model."""
from dataclasses import replace
from decimal import Decimal as D, localcontext
from fractions import Fraction
from itertools import product
import json
import unittest

from uta.api import json_value
from uta.models import Account, AssetSpec, InstrumentSpec, Position, RiskInputError
from uta.portfolio import calculate_portfolio, position_im_bound


ASSETS = {
    "USD": AssetSpec(D(1), D(1)),
    "BTC": AssetSpec(D(100), D("0.8")),
    "ETH": AssetSpec(D(200), D("0.7")),
}
INSTRUMENTS = {
    "BTC-PERP": InstrumentSpec(D(100), D("0.1"), D("0.05")),
    "ETH-PERP": InstrumentSpec(D(200), D("0.1"), D("0.05")),
}


class PortfolioTests(unittest.TestCase):
    def test_gross_asset_debt_and_position_stress_matches_hand_calculation(self):
        account = Account(
            balances={"USD": D(1000), "BTC": D(2)},
            liabilities={"BTC": D(1), "ETH": D("0.5")},
            positions={"BTC-PERP": Position("BTC-PERP", D(1), D(90)),
                       "ETH-PERP": Position("ETH-PERP", D(-1), D(180))},
            open_order_margin=D(7),
        )
        result = calculate_portfolio(account, ASSETS, INSTRUMENTS)
        # Base: 1000 + 2*100*.8 - 1*100 - .5*200 + 10 - 20 = 950.
        self.assertEqual(result.equity, D(950))
        self.assertEqual(result.initial_margin_floor, D(30))
        self.assertEqual(result.maintenance_margin_floor, D(15))
        self.assertEqual(result.worst_scenario, "btc_down_eth_up")
        scenarios = {scenario.name: scenario for scenario in result.scenarios}
        expected = {
            "market_down": ("-24", "35", "25", "-36"),
            "market_up": ("24", "-35", "-25", "36"),
            "btc_down_eth_up": ("-19.2", "0", "-36", "55.2"),
            "btc_up_eth_down": ("19.2", "0", "36", "-55.2"),
            "collateral_gap_down": ("-28.8", "43", "-16", "1.8"),
            "collateral_gap_up": ("28.8", "-43", "16", "-1.8"),
        }
        self.assertEqual(set(scenarios), set(expected))
        for name, values in expected.items():
            scenario = scenarios[name]
            self.assertEqual((scenario.collateral_change, scenario.liability_change,
                              scenario.position_change, scenario.loss), tuple(map(D, values)))
            self.assertEqual(scenario.equity, D(950) - scenario.loss)
        self.assertEqual(result.initial_margin, D("55.2"))
        self.assertEqual(result.maintenance_margin, D("44.16"))
        self.assertEqual(result.available_margin, D("887.8"))
        trace = json.loads(json.dumps(json_value(result)))
        self.assertEqual(trace["scenarios"][0]["mark_shocks"]["BTC-PERP"], "-0.15")

    def test_joint_offset_survives_but_decorrelation_preserves_margin(self):
        btc = Position("BTC-PERP", D(1), D(100))
        eth = Position("ETH-PERP", D("0.5"), D(200))
        account = Account(positions={btc.symbol: btc, eth.symbol: eth})
        directional = calculate_portfolio(account, ASSETS, INSTRUMENTS)
        hedged = calculate_portfolio(
            replace(account, positions={btc.symbol: btc, eth.symbol: replace(eth, quantity=D("-0.5"))}),
            ASSETS, INSTRUMENTS,
        )
        self.assertEqual(directional.initial_margin, D(35))
        self.assertEqual(hedged.initial_margin, D(24))
        self.assertEqual(hedged.worst_scenario, "btc_down_eth_up")

    def test_usd_settlement_moves_all_equities_equally_and_does_not_change_margin(self):
        account = Account(balances={"USD": D(500), "BTC": D(1)},
                          positions={"ETH-PERP": Position("ETH-PERP", D(1), D(195))})
        base = calculate_portfolio(account, ASSETS, INSTRUMENTS)
        settled = calculate_portfolio(replace(account, balances={"USD": D(-120), "BTC": D(1)}),
                                      ASSETS, INSTRUMENTS)
        self.assertEqual(base.initial_margin, settled.initial_margin)
        self.assertEqual(base.maintenance_margin, settled.maintenance_margin)
        for before, after in zip(base.scenarios, settled.scenarios):
            self.assertEqual(before.loss, after.loss)
            self.assertEqual(before.equity - after.equity, D(620))

    def test_position_change_bound_covers_floor_and_scenario_regimes(self):
        for floor, btc_qty, eth_qty, symbol, delta in product(
            ("0.02", "0.25"), (-2, -1, 0, 1, 2), (-1, 0, 1), INSTRUMENTS, (-2, -1, 1, 2),
        ):
            instruments = {key: replace(spec, initial_margin_rate=D(floor),
                                        maintenance_margin_rate=D("0.01"))
                           for key, spec in INSTRUMENTS.items()}
            positions = {"BTC-PERP": Position("BTC-PERP", D(btc_qty), D(90)),
                         "ETH-PERP": Position("ETH-PERP", D(eth_qty), D(190))}
            account = Account(balances={"BTC": D(1)}, liabilities={"ETH": D("0.3")},
                              positions=positions)
            before = calculate_portfolio(account, ASSETS, instruments)
            positions = dict(positions)
            positions[symbol] = replace(positions[symbol], quantity=positions[symbol].quantity + D(delta))
            after = calculate_portfolio(replace(account, positions=positions), ASSETS, instruments)
            bound = Fraction(position_im_bound(symbol, instruments[symbol])) * abs(delta)
            self.assertLessEqual(abs(Fraction(after.initial_margin) - Fraction(before.initial_margin)), bound)

    def test_numeric_context_and_invalid_universe(self):
        with localcontext() as context:
            context.prec = 2
            self.assertEqual(position_im_bound("BTC-PERP", INSTRUMENTS["BTC-PERP"]), D(15))
            portfolio = calculate_portfolio(Account(balances={"USD": D(9999)}), ASSETS, INSTRUMENTS)
            self.assertEqual(portfolio.available_margin, D(9999))
            self.assertIsNone(portfolio.worst_scenario)
            self.assertIsNone(portfolio.margin_ratio)
        with self.assertRaises(RiskInputError):
            calculate_portfolio(Account(balances={"SOL": D(10)}), ASSETS, INSTRUMENTS)
        with self.assertRaises(RiskInputError):
            calculate_portfolio(Account(), dict(ASSETS, USD=AssetSpec(D(1), D("0.9"))), INSTRUMENTS)
        with self.assertRaises(RiskInputError):
            position_im_bound("SOL-PERP", INSTRUMENTS["BTC-PERP"])
