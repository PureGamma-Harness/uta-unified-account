"""Artificial retained-wire mapping tests; no actual SQL/capture claim."""
from copy import deepcopy
from fractions import Fraction as F
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("independent_capture_adapter", ROOT/"scripts/credit_v2_capture_reference.py")
ADAPTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADAPTER)
REF = ADAPTER.REF


def manual_gross_wire():
    # M3 before: explicit hand constants, not produced by a real service.
    return {"account": {"version": 7, "balances": {"USD": "-1", "BTC": "1"},
        "frozen_assets": {}, "positions": {}, "liabilities": [{"asset": "BTC", "principal": "0.1", "interest": "0.01"}],
        "orders": [], "halted": False, "liquidation_state": None},
        "credit": {"version": 7, "cash_units": "100000000", "principal_units": "10000000", "interest_units": "1000000",
            "principal_ledger_units": "-10000000", "interest_ledger_units": "-1000000", "shard_principal_units": "10000000",
            "shard_interest_units": "1000000", "pool_units": "90000000", "principal_receivable_units": "10000000",
            "interest_receivable_units": "1000000"},
        "limits": {"account_limit_units": "1000000000", "local_asset_limit_units": "10000000000"}}


class IndependentCaptureMappingTests(unittest.TestCase):
    def test_manual_negative_cash_and_gross_principal_interest_map_without_netting(self):
        mapped = ADAPTER.retained_state(manual_gross_wire(), account_id="alice")
        self.assertEqual(mapped, REF.state(usd="-1", btc="1", principal="0.1", interest="0.01", pool="0.9", version=7))
        self.assertEqual(REF.gross_components(mapped), {"assets": {"BTC": "1"}, "cash_deficits": {"USD": "1"},
            "principal": {"BTC": "0.1"}, "interest": {"BTC": "0.01"}})

    def test_manual_frozen_position_partial_and_signed_reduce_order_mapping(self):
        wire = manual_gross_wire()
        wire["account"].update(frozen_assets={"BTC": "0.2"},
            positions={"BTC-PERP": {"quantity": "0.3", "cost_basis": "27"}},
            orders=[{"account_id": "alice", "order_id": "partial", "symbol": "BTC-PERP", "quantity": "2",
                "filled_quantity": "0.5", "limit_price": "105", "reduce_only": 0, "status": "PARTIALLY_FILLED"},
                {"account_id": "alice", "order_id": "reduce", "symbol": "BTC-PERP", "quantity": "-0.1",
                 "filled_quantity": "0", "limit_price": "90", "reduce_only": 1, "status": "OPEN"}])
        mapped = ADAPTER.retained_state(wire, account_id="alice")
        self.assertEqual(mapped["frozen_assets"], {"BTC": 20_000_000})
        self.assertEqual(mapped["positions"], {"BTC-PERP": {"quantity_units": 30_000_000, "cost_basis_usd_units": 2_700_000_000}})
        self.assertEqual(mapped["orders"], [
            {"order_id": "partial", "symbol": "BTC-PERP", "quantity_units": 200_000_000, "filled_units": 50_000_000,
             "limit_price": "105", "reduce_only": False, "status": "PARTIALLY_FILLED"},
            {"order_id": "reduce", "symbol": "BTC-PERP", "quantity_units": -10_000_000, "filled_units": 0,
             "limit_price": "90", "reduce_only": True, "status": "OPEN"}])

    def test_bool_alternate_units_missing_credit_and_inconsistent_cash_refuse(self):
        for field, value in (("version", True), ("cash_units", "0100000000"), ("cash_units", "99999999"),
                             ("principal_ledger_units", "-0")):
            wire = manual_gross_wire()
            wire["credit"][field] = value
            with self.subTest(field=field), self.assertRaises(REF.ReferenceInputError):
                ADAPTER.retained_state(wire, account_id="alice")
        wire = manual_gross_wire()
        del wire["credit"]["pool_units"]
        with self.assertRaises(REF.ReferenceInputError):
            ADAPTER.retained_state(wire, account_id="alice")

    def test_duplicate_or_mismatched_debt_and_foreign_order_refuse(self):
        for debts in ([{"asset": "BTC", "principal": "0", "interest": "0"}],
                      [{"asset": "BTC", "principal": "0.1", "interest": "0.01"}]*2, []):
            wire = manual_gross_wire()
            wire["account"]["liabilities"] = debts
            with self.subTest(debts=debts), self.assertRaises(REF.ReferenceInputError):
                ADAPTER.retained_state(wire, account_id="alice")
        wire = manual_gross_wire()
        wire["account"]["orders"] = [{"account_id": "bob"}]
        with self.assertRaisesRegex(REF.ReferenceInputError, "foreign order"):
            ADAPTER.retained_state(wire, account_id="alice")

    def test_34_digit_integer_half_even_handles_ties_negative_and_repeating(self):
        for final, expected in (("25", "2"), ("35", "4")):
            value = F("1."+"0"*32+final)
            rounded = F("1."+"0"*32+expected)
            self.assertEqual(ADAPTER.ratio_34_half_even(value), rounded)
            self.assertEqual(ADAPTER.ratio_34_half_even(-value), -rounded)
        self.assertEqual(ADAPTER.ratio_34_half_even(F(23, 3)), F("7."+"6"*32+"7"))
        self.assertEqual(ADAPTER.ratio_34_half_even(F(0)), F(0))
        self.assertEqual(ADAPTER.ratio_34_half_even(F(10**38)), F(10**38))

    def test_hand_m3_after_risk_components_and_quote_are_independently_checked(self):
        state = REF.state(usd="-1", btc="1.1", principal="0.2", interest="0.01", pool="0.8", version=8)
        market = {"version": 11, "observed_at": "2026-11-17T00:00:00+00:00"}
        base = {"rules": {"rule_id": "manual-rule", "version": 1}, "catalog": {"version": 1}}
        risk = {"accounting_equity": "88", "collateral_value": "88", "risk_equity": "66", "loan_value": "44",
                "principal_value": "20", "interest_value": "1", "cash_deficit_value": "1", "debt_value": "22",
                "unrealized_pnl": "0", "frozen_value": "0", "initial_margin": "4.2", "maintenance_margin": "2.1",
                "available_margin": "61.8", "open_order_margin": "0", "account_version": 8, "equity": "66",
                "market_version": 11, "observed_at": market["observed_at"], "rule_id": "manual-rule", "rule_version": 1,
                "catalog_version": 1, "status": "HEALTHY", "risk_mode": "phase1_cross", "borrowable": {"BTC": "0.22"},
                "market_id": "market-11@"+market["observed_at"], "margin_ratio": "31."+"428571"*5+"43"}
        # 66/2.1 = 220/7; 34 significant digits ends ...429.
        risk["margin_ratio"] = "31.42857142857142857142857142857143"
        ADAPTER.compare_risk(risk, REF.POLICY, state, market=market, base=base)
        for key, value in (("principal_value", "19"), ("cash_deficit_value", "0"), ("initial_margin", "4"),
                           ("account_version", True), ("margin_ratio", "31.42857142857142857142857142857142")):
            altered = deepcopy(risk)
            altered[key] = value
            with self.subTest(key=key), self.assertRaises(REF.ReferenceInputError):
                ADAPTER.compare_risk(altered, REF.POLICY, state, market=market, base=base)

    def test_decimal_units_refuse_fractional_satoshi_and_nondecimal_types(self):
        for value in (True, 1, 0.1, "0.000000001", "NaN", "1e99999"):
            with self.subTest(value=value), self.assertRaises(REF.ReferenceInputError):
                ADAPTER.decimal_units(value, "manual")
        self.assertEqual(ADAPTER.decimal_units("-0.00000001", "manual"), -1)

    def test_missing_or_extra_observation_fields_cannot_fabricate_pass(self):
        for value in ({}, {"financial_content_passed": True}, {name: None for name in ADAPTER.OBSERVATION} | {"oracle_passed": True}):
            with self.subTest(value=list(value)), self.assertRaises(REF.ReferenceInputError):
                ADAPTER.check_observation(value)


if __name__ == "__main__":
    unittest.main()
