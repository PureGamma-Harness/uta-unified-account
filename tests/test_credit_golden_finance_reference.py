"""Small tests of oracle independence and scope; no production/SQL imports."""

from copy import deepcopy
from fractions import Fraction
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "credit_golden_finance_reference", ROOT / "scripts/review_credit_golden_finance.py")
REFERENCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REFERENCE)


class IndependentOracleTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads((ROOT / "tests/fixtures/managed_credit_v1_golden.json").read_text())

    def test_expected_value_mutation_is_detected(self):
        # This is a deliberate false expected value, not an implementation-derived expectation.
        self.fixture["cases"][0]["expected"]["risk_equity_USD"] = "999"
        result = REFERENCE.build_report(self.fixture)
        mismatches = [c for c in result["numeric_field_comparisons"] if not c["matches"]]
        self.assertEqual([(c["field"], c["computed"]) for c in mismatches],
                         [("expected.risk_equity_USD", "92")])

    def test_changing_input_moves_oracle_without_using_expected(self):
        self.fixture["assumptions"]["baseline_customer_cash"]["USD"] = "120"
        report = REFERENCE.build_report(self.fixture)
        self.assertEqual(report["cases"]["CREDIT-MANUAL-001"]["after"]["risk"]["risk_equity_USD"], "112")
        self.assertGreater(report["numeric_mismatches"], 0)

    def test_gross_assets_are_haircut_before_full_debt_subtraction(self):
        ref = REFERENCE.Reference(self.fixture["assumptions"])
        state = ref.borrow(ref.baseline(), Fraction(2, 5))
        self.assertEqual(ref.risk(state)["risk_equity_USD"], Fraction(92))
        # The incorrect same-coin netting model erases the haircut loss.
        incorrectly_netted = state["customer_USD"] + (state["customer_BTC"] - state["principal_BTC"]) * ref.price * Fraction(4, 5)
        self.assertEqual(incorrectly_netted, Fraction(100))
        self.assertNotEqual(ref.risk(state)["risk_equity_USD"], incorrectly_netted)

    def test_opening_interest_repayment_is_not_all_principal_pool_cash(self):
        report = REFERENCE.build_report(self.fixture)
        extra = report["supplemental_opening_interest_repayment"]
        self.assertEqual(extra["interest_repaid_BTC"], "0.05")
        self.assertEqual(extra["principal_repaid_BTC"], "0.05")
        self.assertEqual(extra["allocation_headroom_release_BTC"], "0.1")
        self.assertEqual(extra["pool_cash_increase_BTC"], "0.05")
        self.assertEqual(extra["posting_sum_BTC"], "0")

    def test_bad_global_certificate_is_rejected_before_arithmetic(self):
        assumptions = deepcopy(self.fixture["assumptions"])
        assumptions["shard_allocations_BTC"]["1"] = "0.50000001"
        with self.assertRaisesRegex(ValueError, "allocation certificate"):
            REFERENCE.Reference(assumptions)

    def test_model_proves_only_static_truth_caps_and_exposes_unsafe_reclamation(self):
        graph = REFERENCE.tiny_budget_graph()
        self.assertEqual(graph["reachable_states"], 36)
        self.assertEqual(len(graph["truth_debt_pairs"]), 9)
        self.assertTrue(graph["all_truth_states_within_local_and_global_caps"])
        unsafe = graph["unsafe_reclamation_counterexample"][-1]
        self.assertGreater(unsafe["actual_global_debt"], graph["global_budget"])

    def test_zero_minor_unit_rounding_and_case_branching_are_explicit(self):
        report = REFERENCE.build_report(self.fixture)
        ten = report["cases"]["CREDIT-MANUAL-010"]
        self.assertEqual(ten["request_minor_units"], 1)
        self.assertEqual(ten["step_minor_units"], 1000000)
        self.assertFalse(ten["predicates"]["quantity_step"])
        # Case007 starts from001, not from003's .5 debt.
        self.assertEqual(report["cases"]["CREDIT-MANUAL-007"]["after"]["state"]["principal_BTC"], "0.3")


if __name__ == "__main__":
    unittest.main()
