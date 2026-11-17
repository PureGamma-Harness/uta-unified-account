"""Pure JSON counter cases; no SQLite, service, subprocess or clock waiting."""
import copy
import unittest

from tools.managed_observer_coverage import Coverage, FLAGS, fatal_financial_codes


def plan():
    return {"producer": {"duration_seconds": 21600}, "observer": {
        "interval_seconds": 61, "blocks": 12,
        "independent_finance_golden_required_each_1800_second_block": 1,
        "technical_read_unknown_budget": 3, "maximum_consecutive_technical_read_unknown": 1}}


def stable():
    return {"logical_point": "stable_boundary", "alerts": [], "active_rounds": [],
        "planned_faults": [], "unresolved_faults": 0, "unresolved_steps": 0,
        "finance": {"golden": {"compared": True, "passed": True, "errors": []},
                    "retry_alerts": [], "command_inbox": []}}


def inflight(planned=False):
    value = stable()
    value.update(logical_point="inflight_or_unknown", active_rounds=[5], unresolved_faults=1 if planned else 0,
                 planned_faults=[{"kind": "worker", "state": "PLANNED"}] if planned else [])
    value["finance"]["golden"] = {"compared": False, "passed": False, "errors": []}
    return value


def technical():
    return {"logical_point": "unknown", "alerts": ["observation_failed_closed"],
            "error_type": "OperationalError", "error_digest": "a" * 64}


class CoverageCases(unittest.TestCase):
    def test_not_started_never_invents_zero_measurements(self):
        report = Coverage(plan()).report()
        self.assertEqual(report["coverage_status"], "NOT_STARTED")
        for key in ("samples_observed", "counts", "technical_error_types", "logical_point_counts"):
            self.assertIsNone(report[key])
        self.assertTrue(all(block["stable_golden_samples"] is None for block in report["blocks"]))
        self.assertFalse(any(report[key] for key in FLAGS))

    def test_twelve_actual_window_goldens_are_evidence_without_signoff(self):
        coverage = Coverage(plan())
        for index in range(12):
            value = stable()
            value.update(observation_attempt_started_elapsed_seconds=index * 1800 + 60,
                         observation_attempt_ended_elapsed_seconds=index * 1800 + 62)
            classified = coverage.observe(value, job_elapsed_seconds=index * 1800 + 62,
                                          sample_attempt_id=index + 1)
            self.assertEqual(classified["credited_block"], index)
        report = coverage.report(completed_active_seconds=21600.5, final=True)
        self.assertEqual(report["coverage_status"], "COMPLETE_WITHIN_COVERAGE_BUDGET")
        self.assertEqual(report["samples_observed"], 12)
        self.assertEqual(report["counts"]["technical_read_unknown_samples"], 0)
        self.assertEqual(report["preregistered_interval_seconds"], 61)
        self.assertTrue(all(block["state"] == "SATISFIED" for block in report["blocks"]))
        self.assertFalse(report["coverage_budget_requests_stop"])
        self.assertFalse(any(report[key] for key in FLAGS))

    def test_alertless_active_round_is_still_financial_unknown(self):
        coverage = Coverage(plan())
        result = coverage.observe(inflight(), job_elapsed_seconds=5, sample_attempt_id=1)
        self.assertEqual(result["financial_golden_state"], "not_compared_inflight_or_unproven")
        self.assertIsNone(result["credited_block"])
        self.assertEqual(result["fatal_financial_codes"], [])
        report = coverage.report(5)
        self.assertEqual(report["blocks"][0]["stable_golden_samples"], 0)
        self.assertEqual(report["counts"]["active_round_inflight_unknown_samples"], 1)
        self.assertEqual(report["counts"]["technical_read_unknown_samples"], 0)
        self.assertTrue(report["alerts_are_not_financial_evidence"])

    def test_planned_fault_does_not_hide_a_real_read_error(self):
        coverage = Coverage(plan())
        failed = technical()
        failed.update(logical_point="inflight_or_unknown", active_rounds=[5],
                      planned_faults=[{"state": "PLANNED", "kind": "worker"}], unresolved_faults=1)
        result = coverage.observe(failed, job_elapsed_seconds=120, sample_attempt_id=1)
        self.assertTrue(result["planned_fault_inflight_unknown"])
        self.assertTrue(result["technical_read_unknown"])
        self.assertEqual(result["fatal_financial_codes"], [])
        coverage.observe(inflight(planned=True), job_elapsed_seconds=121, sample_attempt_id=2)
        report = coverage.report(121)
        self.assertEqual(report["counts"]["planned_fault_inflight_unknown_samples"], 2)
        self.assertEqual(report["counts"]["technical_read_unknown_samples"], 1)
        self.assertEqual(report["technical_error_types"], {"OperationalError": 1})
        self.assertEqual(report["consecutive_technical_read_unknown"], 0)

    def test_consecutive_budget_miss_is_permanent_but_never_requests_stop(self):
        coverage = Coverage(plan())
        coverage.observe(technical(), job_elapsed_seconds=1, sample_attempt_id=1)
        coverage.observe(technical(), job_elapsed_seconds=2, sample_attempt_id=2)
        coverage.observe(stable(), job_elapsed_seconds=3, sample_attempt_id=3)
        report = coverage.report(3)
        self.assertEqual(report["coverage_status"], "NO_GO")
        self.assertIn("consecutive_technical_read_unknown_budget_exceeded", report["coverage_no_go_reasons"])
        self.assertEqual(report["maximum_observed_consecutive_technical_read_unknown"], 2)
        self.assertEqual(report["consecutive_technical_read_unknown"], 0)
        self.assertFalse(report["coverage_budget_requests_stop"])

    def test_four_isolated_errors_exceed_budget_even_after_successful_reads(self):
        coverage = Coverage(plan())
        for index in range(4):
            coverage.observe(technical(), job_elapsed_seconds=index * 20 + 1, sample_attempt_id=2 * index + 1)
            coverage.observe(inflight(), job_elapsed_seconds=index * 20 + 2, sample_attempt_id=2 * index + 2)
        report = coverage.report(100)
        self.assertEqual(report["counts"]["technical_read_unknown_samples"], 4)
        self.assertEqual(report["maximum_observed_consecutive_technical_read_unknown"], 1)
        self.assertIn("technical_read_unknown_budget_exceeded", report["coverage_no_go_reasons"])
        self.assertEqual(report["coverage_status"], "NO_GO")

    def test_span_crossing_window_does_not_credit_either_side(self):
        coverage = Coverage(plan())
        value = stable()
        value.update(observation_attempt_started_elapsed_seconds=1799.9,
                     observation_attempt_ended_elapsed_seconds=1800.1)
        result = coverage.observe(value, job_elapsed_seconds=1800.1, sample_attempt_id=1)
        self.assertIsNone(result["credited_block"])
        coverage.observe(stable(), job_elapsed_seconds=1801, sample_attempt_id=2)
        report = coverage.report(1801)
        self.assertEqual(report["blocks"][0]["stable_golden_samples"], 0)
        self.assertEqual(report["blocks"][1]["stable_golden_samples"], 1)
        self.assertEqual(report["counts"]["stable_golden_cross_block_samples"], 1)
        self.assertIn("closed_block_0_missing_stable_golden", report["coverage_no_go_reasons"])
        # A later timestamp claiming an earlier window cannot erase the miss.
        coverage.observe(stable(), job_elapsed_seconds=1700, sample_attempt_id=3)
        self.assertEqual(coverage.report(1801)["coverage_status"], "NO_GO")

    def test_final_sample_is_not_clamped_back_into_missing_last_window(self):
        coverage = Coverage(plan())
        for index in range(11):
            coverage.observe(stable(), job_elapsed_seconds=index * 1800 + 60, sample_attempt_id=index + 1)
        result = coverage.observe(stable(), job_elapsed_seconds=21600.1, sample_attempt_id=12)
        self.assertIsNone(result["credited_block"])
        report = coverage.report(21600.1, final=True)
        self.assertEqual(report["blocks"][11]["stable_golden_samples"], 0)
        self.assertEqual(report["coverage_status"], "NO_GO")
        self.assertIn("final_block_11_missing_stable_golden", report["coverage_no_go_reasons"])

    def test_literal_golden_contract_and_missing_finance_fail_closed(self):
        for change in (lambda value: value["finance"]["golden"].update(passed=1),
                       lambda value: value["finance"]["golden"].update(compared=1),
                       lambda value: value["finance"]["golden"].update(errors=[{}]),
                       lambda value: value.pop("finance")):
            coverage, value = Coverage(plan()), stable()
            change(value)
            result = coverage.observe(value, job_elapsed_seconds=1, sample_attempt_id=1)
            self.assertIsNone(result["credited_block"])
            self.assertTrue(result["technical_read_unknown"])
            self.assertEqual(fatal_financial_codes(value), [])
            self.assertEqual(coverage.report(1)["counts"]["technical_read_unknown_samples"], 1)

    def test_inconsistent_stable_marker_does_not_credit_or_assert_bad_debt(self):
        for mutation in (lambda value: value.update(active_rounds=[5]),
                         lambda value: value.update(unresolved_steps=True),
                         lambda value: value.pop("unresolved_steps"),
                         lambda value: value.update(unresolved_faults=1),
                         lambda value: value.update(unresolved_faults=False)):
            coverage, value = Coverage(plan()), stable()
            mutation(value)
            result = coverage.observe(value, job_elapsed_seconds=60, sample_attempt_id=1)
            self.assertIsNone(result["credited_block"])
            self.assertTrue(result["technical_read_unknown"])
            self.assertEqual(result["fatal_financial_codes"], [])
            self.assertEqual(coverage.report(60)["coverage_status"], "NO_GO")
            value["finance"]["golden"].update(passed=False, errors=["journal_conservation_projection"])
            self.assertEqual(fatal_financial_codes(value), [])

    def test_error_maps_are_bounded_and_raw_unknown_labels_are_not_published(self):
        coverage = Coverage(plan())
        for index in range(100):
            value = technical()
            value.update(error_type="Type" + str(index), error_digest=f"{index:064x}")
            coverage.observe(value, job_elapsed_seconds=index, sample_attempt_id=index + 1)
        value = technical()
        value.update(error_type="synthetic-secret/error URL", error_digest="raw-secret")
        coverage.observe(value, job_elapsed_seconds=101, sample_attempt_id=101)
        report = coverage.report(101)
        self.assertLessEqual(len(report["technical_error_types"]), 33)
        self.assertLessEqual(len(report["technical_error_digests"]), 65)
        self.assertEqual(sum(report["technical_error_types"].values()), 101)
        self.assertNotIn("synthetic-secret/error URL", report["technical_error_types"])
        self.assertNotIn("raw-secret", report["technical_error_digests"])
        self.assertEqual(len(coverage._goldens), 12)

    def test_attempt_ids_cannot_hide_gap_or_double_count(self):
        coverage = Coverage(plan())
        coverage.observe(stable(), job_elapsed_seconds=1, sample_attempt_id=2)
        with self.assertRaisesRegex(ValueError, "attempt_id_must_increase"):
            coverage.observe(stable(), job_elapsed_seconds=2, sample_attempt_id=2)
        report = coverage.report(2)
        self.assertEqual(report["samples_observed"], 1)
        self.assertIn("sample_attempt_sequence_gap", report["coverage_no_go_reasons"])

    def test_ended_short_run_does_not_turn_unobserved_blocks_into_success(self):
        coverage = Coverage(plan())
        coverage.observe(stable(), job_elapsed_seconds=60, sample_attempt_id=1)
        report = coverage.report(60, final=True)
        self.assertEqual(report["coverage_status"], "NO_GO")
        self.assertIn("actual_active_duration_incomplete_or_unknown", report["coverage_no_go_reasons"])
        self.assertEqual(report["blocks"][11]["state"], "UNOBSERVED_FINAL")


class FinancialAlertCases(unittest.TestCase):
    def test_unavailable_checks_are_technical_unknown_not_financial_damage(self):
        value = stable()
        value["finance"]["golden"].update(passed=False, errors=["sqlite_foreign_key_check_failed_unavailable"])
        self.assertEqual(fatal_financial_codes(value), [])
        coverage = Coverage(plan())
        result = coverage.observe(value, job_elapsed_seconds=60, sample_attempt_id=1)
        self.assertTrue(result["technical_read_unknown"])
        self.assertEqual(result["financial_golden_state"], "unavailable_verification")
        for error in ("sqlite_quick_check_failed", "sqlite_foreign_key_check_failed", "journal_conservation_projection"):
            changed = copy.deepcopy(value)
            changed["finance"]["golden"]["errors"] = [error]
            self.assertEqual(fatal_financial_codes(changed), ["stable_financial_golden_failed"])
        value["finance"]["golden"]["errors"] = ["another_verification_unavailable"]
        self.assertEqual(fatal_financial_codes(value), [])

    def test_plain_read_exceptions_and_inflight_false_golden_are_not_fatal(self):
        self.assertEqual(fatal_financial_codes(technical()), [])
        self.assertEqual(fatal_financial_codes(inflight(planned=True)), [])
        value = technical()
        value["error_type"] = "ValueError"
        self.assertEqual(fatal_financial_codes(value), [])

    def test_internal_retry_and_terminal_failure_include_control_lane(self):
        value = inflight()
        value["finance"]["command_inbox"] = [{"account": None, "control_lane": True,
            "state": "SUCCEEDED", "attempts": 1, "last_error_present": False, "last_error_code": None}]
        self.assertEqual(fatal_financial_codes(value), ["internal_execution_retry"])
        value["finance"]["command_inbox"][0].update(state="QUARANTINED", attempts=0)
        self.assertEqual(fatal_financial_codes(value), ["terminal_command_failure"])
        value["finance"]["command_inbox"][0].update(state="PENDING", quarantined=False)
        self.assertEqual(fatal_financial_codes(value), [])

    def test_explicit_fatal_facts_cannot_credit_an_inconsistent_pass_flag(self):
        value = stable()
        value["finance"]["retry_alerts"] = [{"attempts": 1, "cause": "unknown"}]
        coverage = Coverage(plan())
        result = coverage.observe(value, job_elapsed_seconds=60, sample_attempt_id=1)
        self.assertIsNone(result["credited_block"])
        self.assertEqual(result["fatal_financial_codes"], ["internal_execution_retry"])
        self.assertEqual(result["financial_golden_state"], "stable_compared_failed")


if __name__ == "__main__":
    unittest.main()
