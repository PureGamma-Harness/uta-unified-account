"""Micro component constraints, not managed online lending acceptance."""
import json
import unittest
from pathlib import Path

from tools.credit_obligation_probe import LEGS, observe_case, old_binary_controls


OBSERVATIONS = []


class CandidateCreditObligationTests(unittest.TestCase):
    def run_case(self, **options):
        result = observe_case(**options)
        OBSERVATIONS.append({"test": self._testMethodName, "options": options, "result": result})
        self.assertTrue(result["temporary_authority_removed"])
        return result

    def assert_no_effect(self, result, native_code):
        self.assertFalse(result["committed"], json.dumps(result, sort_keys=True))
        self.assertEqual(result["error"]["sqlite_errorcode"], native_code, json.dumps(result, sort_keys=True))
        self.assertTrue(result["financial_unchanged"], json.dumps(result, sort_keys=True))
        self.assertEqual(result["after_reopen"]["inbox"], "PENDING")

    def test_complete_candidate_tuple_really_commits_four_legs(self):
        result = self.run_case()
        self.assertTrue(result["committed"], json.dumps(result, sort_keys=True))
        self.assertTrue(result["native_commit_attempted"])
        self.assertEqual(result["after_reopen"]["inbox"], "SUCCEEDED")
        self.assertEqual(result["after_reopen"]["loan_legs"], [tuple(leg) for leg in LEGS])
        self.assertEqual(result["after_reopen"]["liabilities"], [("alice", "BTC", "0.4", "0")])
        self.assertEqual(result["core_ledger_verified_events"], 3)
        self.assertEqual(result["core_credit_nonzero_liabilities"], 1)
        self.assertEqual(result["base_decision_reader"]["kind"], "CREDIT_BORROWED")
        self.assertEqual(result["base_decision_reader"]["account_id"], "alice")

    def test_missing_parent_tuples_fail_real_deferred_commit(self):
        for missing in ("decision", "terminal", "credit", "journal", "source", "allocation", "policy"):
            with self.subTest(missing=missing):
                result = self.run_case(missing=missing)
                self.assert_no_effect(result, 787)
                self.assertTrue(result["native_commit_attempted"])
                self.assertTrue(result["native_rollback_observed"])
                self.assertTrue(result["fk_violations_before_commit"])
                if missing == "journal":
                    self.assertEqual(result["statement_errors"][0]["sqlite_errorcode"], 1811)

    def test_null_and_check_bypasses_are_not_fk_safety_passes(self):
        for overrides, code in (({12: None}, 1299), ({4: "REJECTED"}, 275),
                                ({8: "-1"}, 275), ({11: 0}, 275)):
            with self.subTest(overrides=overrides):
                result = self.run_case(overrides=overrides)
                self.assert_no_effect(result, code)
                self.assertFalse(result["native_commit_attempted"])

    def test_wrong_decision_identity_cannot_satisfy_composite_fk(self):
        result = self.run_case(wrong_decision=True)
        self.assert_no_effect(result, 787)

    def test_effect_without_staged_intent_is_rejected_by_actual_trigger(self):
        result = self.run_case(missing="intent")
        self.assert_no_effect(result, 1811)

    def test_customer_counterparty_substitution_fails_posting_gate(self):
        legs = [("customer:dummy" if account == "customer:alice" else account, asset, units)
                for account, asset, units in LEGS]
        result = self.run_case(legs=legs)
        self.assert_no_effect(result, 1811)

    def test_closing_gate_rejects_balanced_wrong_customer_even_without_posting_gate(self):
        legs = [("customer:dummy" if account == "customer:alice" else account, asset, units)
                for account, asset, units in LEGS]
        result = self.run_case(legs=legs, posting_gate=False)
        self.assert_no_effect(result, 787)
        self.assertEqual(result["statement_errors"][0]["sqlite_errorcode"], 1811)

    def test_full_tuple_caught_late_freshness_failure_rechecked_before_commit(self):
        result = self.run_case(late_stale=True)
        self.assertFalse(result["committed"], json.dumps(result, sort_keys=True))
        self.assertEqual(result["caught_late_error"]["code"], "market_unavailable")
        self.assertEqual(result["error"]["code"], "market_unavailable")
        self.assertFalse(result["native_commit_attempted"])
        self.assertTrue(result["native_rollback_observed"])
        self.assertTrue(result["financial_unchanged"])

    def test_real_caller_savepoint_removes_obligations_and_commits_rejection(self):
        result = self.run_case(late_stale=True, rollback_to=True)
        self.assertTrue(result["committed"], json.dumps(result, sort_keys=True))
        self.assertTrue(result["native_commit_attempted"])
        self.assertEqual(result["after_reopen"]["inbox"], "REJECTED")
        self.assertEqual(result["after_reopen"]["intents"], 0)
        self.assertTrue(result["financial_unchanged"])

    def test_actual_old_binary_base_batch_positive_credit_markers_negative(self):
        controls = old_binary_controls()
        OBSERVATIONS.append({"test": self._testMethodName, "old_binary": controls})
        self.assertEqual(len(controls), 4)
        for control in controls:
            self.assertEqual(control["exit_code"], 0, control)
            if control["prototype_credit_marker"]:
                self.assertTrue(control["rejected"], control)
                self.assertFalse(control["acquired_and_wrote"], control)
                self.assertEqual(control["actual_ledger_events"], 1)
                self.assertIn(control["code"], ("fence_guard_corrupt", "fence_corrupt"))
            else:
                self.assertFalse(control["rejected"], control)
                self.assertTrue(control["acquired_and_wrote"], control)
                self.assertEqual(control["actual_ledger_events"], 2)


if __name__ == "__main__":
    import sys
    report = Path(sys.argv.pop(1))
    try:
        program = unittest.main(verbosity=2, exit=False)
    finally:
        report.write_text(json.dumps(OBSERVATIONS, indent=2) + "\n")
    raise SystemExit(0 if program.result.wasSuccessful() else 1)
