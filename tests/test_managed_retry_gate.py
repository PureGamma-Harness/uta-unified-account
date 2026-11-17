"""Independent fixed-evidence oracle for a retry hidden by safe final rejection."""
from collections import Counter
from copy import deepcopy
import gzip
from hashlib import sha256
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from benchmarks.run_managed_benchmark import command_technical_diagnostics, main, probe_qualification


class ManagedRetryGateTests(unittest.TestCase):
    @staticmethod
    def summary(technical):
        return {"counts": {"financial_succeeded": 1, "enqueue_technical_errors": 0},
                "command_technical_diagnostics": technical, "poll_errors": [], "feed_publications": [],
                "readonly_reconciliation": {"reopened_readonly": True, "pending_count": 0,
                                            "unobserved_successes_found_on_reopen": 0}}

    @staticmethod
    def command(**changes):
        row = dict(shard=0, command_id="same-cid", kind="SUBMIT_ORDER", state="SUCCEEDED",
                   attempts=0, last_error=None, error=None)
        row.update(changes)
        return row

    def test_original_S1_receipts_expose_one_internal_retry_despite_safe_terminal_and_zero_enqueue_errors(self):
        directory = Path(__file__).resolve().parents[1] / "benchmarks/results/20261117-managed-corrected-7200097/raw/S1"
        path = directory / "arrivals.jsonl.gz"
        self.assertEqual(sha256(path.read_bytes()).hexdigest(),
                         "689ab5d8fe261b75b0cb57d18f37e676d5977cc8e059862df5984e2801ab2a53")
        with gzip.open(path, "rt") as stream:
            rows = [json.loads(line) for line in stream]
        # These literal expectations come from the separately archived real
        # probe and independent RO review, not from the production classifier.
        self.assertEqual(dict(Counter(row["outcome"] for row in rows)),
                         {"financial_succeeded": 508, "business_rejected": 58,
                          "control_or_market_rejected": 321, "local_outstanding_full": 113})
        self.assertEqual(len(rows), 1000)
        self.assertEqual(sum(row["outcome"] == "financial_succeeded" and row["latency_ns"] > 1_000_000_000
                             for row in rows), 418)
        affected = [row for row in rows if row["receipt"] and
                    (row["receipt"]["attempts"] != 0 or row["receipt"]["last_error"] is not None)]
        self.assertEqual(len(affected), 1)
        original = affected[0]
        self.assertEqual((original["command_id"], original["shard"], original["latency_ns"]),
                         ("bench:684", 0, 3928396842))
        self.assertEqual((original["receipt"]["state"], original["receipt"]["attempts"], original["receipt"]["last_error"]),
                         ("REJECTED", 1, "technical_execution_failure"))
        self.assertEqual(json.loads(original["receipt"]["error"])["code"], "market_unavailable")
        historical = json.loads((directory / "summary.json").read_text())
        self.assertEqual(historical["counts"]["enqueue_technical_errors"], 0)
        self.assertEqual(historical["poll_errors"], [])
        self.assertNotIn("command_technical_diagnostics", historical)
        self.assertIn("missing_all_cid_technical_diagnostics", probe_qualification(historical)["reasons"])

        receipts = [{"shard": row["shard"], **row["receipt"]} for row in rows if row["receipt"]]
        # Original arrival receipts cover 887 financial CIDs, not the separate
        # market/control lane. The runtime now reads all persisted inbox rows.
        diagnostics = command_technical_diagnostics(receipts)
        self.assertEqual(diagnostics["stored_commands"], 887)
        self.assertEqual(diagnostics["internal_execution_attempts"], 1)
        self.assertEqual(diagnostics["commands_with_internal_attempts"], 1)
        self.assertEqual(diagnostics["commands_with_last_error"], 1)
        self.assertEqual(diagnostics["affected_commands"], [{"shard": 0, "command_id": "bench:684",
            "kind": "SUBMIT_ORDER", "state": "REJECTED", "attempts": 1,
            "last_error": "technical_execution_failure", "terminal_error_code": "market_unavailable",
            "terminal_error_status": 503}])
        evaluated = deepcopy(historical)
        evaluated["command_technical_diagnostics"] = diagnostics
        gate = probe_qualification(evaluated)
        self.assertFalse(gate["passed"])
        self.assertTrue(gate["stop_remaining_cases"])
        self.assertIn("internal_execution_attempts", gate["reasons"])
        self.assertIn("persisted_last_error", gate["reasons"])
        self.assertFalse(gate["financial_soft_deadline_passed"])
        self.assertEqual(evaluated["counts"], historical["counts"], "do not reclassify financial or business outcomes")

    def test_eventual_success_does_not_erase_internal_failure_or_double_count_affected_commands(self):
        diagnostics = command_technical_diagnostics([self.command(attempts=2, last_error="technical_execution_failure")])
        self.assertEqual(diagnostics["internal_execution_attempts"], 2)
        self.assertEqual(diagnostics["commands_with_internal_attempts"], 1)
        self.assertEqual(diagnostics["commands_with_last_error"], 1)
        self.assertEqual(len(diagnostics["affected_commands"]), 1)
        summary = self.summary(diagnostics)
        self.assertFalse(probe_qualification(summary)["passed"])
        self.assertEqual(summary["counts"]["financial_succeeded"], 1)

    def test_control_lane_retries_and_last_error_without_attempts_also_stop(self):
        diagnostics = command_technical_diagnostics([
            self.command(kind="PUBLISH_MARKET", attempts=1),
            self.command(shard=1, kind="PUBLISH_MARKET"),
            self.command(command_id="halt", kind="SET_HALT", last_error="")])
        self.assertEqual(diagnostics["stored_commands"], 3)
        self.assertEqual(diagnostics["commands_by_kind"], {"PUBLISH_MARKET": 2, "SET_HALT": 1})
        self.assertEqual(diagnostics["internal_execution_attempts"], 1)
        self.assertEqual(diagnostics["commands_with_last_error"], 1)
        gate = probe_qualification(self.summary(diagnostics))
        self.assertFalse(gate["passed"])
        self.assertIn("internal_execution_attempts", gate["reasons"])
        self.assertIn("persisted_last_error", gate["reasons"])

    def test_safe_business_rejection_is_separate_from_technical_gate_and_latency(self):
        diagnostics = command_technical_diagnostics([self.command(state="REJECTED",
            error={"code": "router_halted", "status": 503})])
        summary = self.summary(diagnostics)
        summary["counts"] = {"financial_succeeded": 1, "control_or_market_rejected": 1, "financial_success_late": 1}
        gate = probe_qualification(summary)
        self.assertTrue(gate["passed"])
        self.assertFalse(gate["financial_soft_deadline_passed"])
        self.assertFalse(gate["production_approved"])
        self.assertFalse(gate["stability_passed"])

    def test_pending_or_rejected_control_cid_cannot_pass_without_retry_metadata(self):
        for state in ("PENDING", "REJECTED"):
            with self.subTest(state=state):
                diagnostics = command_technical_diagnostics([self.command(kind="SET_HALT", state=state,
                    error={"code": "router_halted", "status": 503} if state == "REJECTED" else None)])
                self.assertEqual(diagnostics["internal_execution_attempts"], 0)
                self.assertEqual(diagnostics["commands_with_last_error"], 0)
                self.assertEqual(diagnostics["control_commands_not_succeeded"], 1)
                gate = probe_qualification(self.summary(diagnostics))
                self.assertFalse(gate["passed"])
                self.assertTrue(gate["stop_remaining_cases"])
                self.assertIn("control_command_not_succeeded", gate["reasons"])
                if state == "PENDING":
                    self.assertIn("persisted_nonterminal_command", gate["reasons"])

    def test_duplicate_observations_or_invalid_attempts_are_not_silently_accepted(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            command_technical_diagnostics([self.command(), self.command()])
        for value in (-1, True, "1"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "attempt count"):
                command_technical_diagnostics([self.command(attempts=value)])

    def test_cli_exits_nonzero_after_a_failed_probe_qualification(self):
        summary = self.summary(command_technical_diagnostics([self.command(attempts=1)]))
        summary["probe_qualification"] = probe_qualification(summary)
        with patch("benchmarks.run_managed_benchmark.run", return_value=summary), \
                patch("benchmarks.run_managed_benchmark.os.sched_setaffinity"), \
                patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(main(["--output", "/unused-new-test-output", "--cpu-limit", "1"]), 2)


if __name__ == "__main__":
    unittest.main()
