import unittest
from decimal import Decimal as D, Inexact, Rounded, ROUND_CEILING, localcontext

from uta.models import Account, AssetSpec, InstrumentSpec, Position, RiskInputError
from uta.risk import calculate_risk, check_order


class RiskBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.assets = {"USD": AssetSpec(D("1"), D("1"))}
        self.instruments = {"X": InstrumentSpec(D("100"), D("0.1"), D("0.05"))}

    def test_validated_account_cannot_be_changed_through_original_mappings(self):
        balances = {"USD": D("100")}
        liabilities = {"USD": D("10")}
        positions = {"X": Position("X", D("1"), D("100"))}
        account = Account(balances, positions, liabilities=liabilities)
        before = calculate_risk(account, self.assets, self.instruments)
        balances["USD"] = D("1000000")
        liabilities.clear()
        positions.clear()
        self.assertEqual(calculate_risk(account, self.assets, self.instruments), before)
        with self.assertRaises(TypeError):
            account.balances["USD"] = D("1000000")
        with self.assertRaises(TypeError):
            account.liabilities["USD"] = D("0")
        with self.assertRaises(TypeError):
            account.positions["X"] = Position("X", D("2"), D("100"))

    def test_non_mapping_and_invalid_identifier_inputs_are_domain_errors(self):
        for data in (None, [], 1):
            for field in ("balances", "liabilities", "positions"):
                with self.subTest(data=data, field=field), self.assertRaises(RiskInputError):
                    Account(**{field: data})
        for key in ("", " ", "X\n", "X Y", "X" * 129, 1, True, None, "资产"):
            with self.subTest(key=key), self.assertRaises(RiskInputError):
                Account({key: D("1")})
            with self.subTest(key=key), self.assertRaises(RiskInputError):
                Position(key, D("1"), D("1"))
            with self.subTest(key=key), self.assertRaises(RiskInputError):
                check_order(Account(), self.assets, self.instruments, symbol=key,
                            quantity=D("1"), execution_price=D("100"))

    def test_arithmetic_under_rounding_and_inexact_traps_is_deterministic(self):
        account = Account({"USD": D("1000.123456789012345678901234567890")},
                          {"X": Position("X", D("1.123456789012345678901234567890"), D("99.123"))})
        baseline = calculate_risk(account, self.assets, self.instruments)
        order = dict(symbol="X", quantity=D("0.123456789012345678901234567890"),
                     execution_price=D("100.987654321"), fee_rate=D("0.00123456789"))
        projected = check_order(account, self.assets, self.instruments, **order)
        with localcontext() as context:
            context.prec = 2
            context.rounding = ROUND_CEILING
            context.traps[Inexact] = True
            context.traps[Rounded] = True
            self.assertEqual(calculate_risk(account, self.assets, self.instruments), baseline)
            self.assertEqual(check_order(account, self.assets, self.instruments, **order), projected)

    def test_ordinary_risk_check_does_not_bypass_deficit_for_reducing_order(self):
        account = Account({"USD": D("-1")}, {"X": Position("X", D("1"), D("100"))})
        checked = check_order(account, self.assets, self.instruments, symbol="X", quantity=D("-1"),
                              execution_price=D("100"))
        self.assertFalse(checked.accepted)
        self.assertEqual(checked.projected_initial_margin, D("0"))
        self.assertEqual(checked.projected_available_margin, D("-1"))

    def test_unsupported_types_fail_with_domain_errors(self):
        with self.assertRaises(RiskInputError):
            calculate_risk({}, self.assets, self.instruments)
        for invalid in (None, [], 1):
            with self.subTest(invalid=invalid), self.assertRaises(RiskInputError):
                calculate_risk(Account(), invalid, self.instruments)
            with self.subTest(invalid=invalid), self.assertRaises(RiskInputError):
                calculate_risk(Account(), self.assets, invalid)


if __name__ == "__main__":
    unittest.main()
