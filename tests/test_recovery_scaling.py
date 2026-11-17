from hashlib import sha256
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from benchmarks.run_recovery_scaling import check_history, run, validate


class RecoveryScalingTests(unittest.TestCase):
    def test_bounds_require_finite_short_work(self):
        for events, seconds in ((True, 1), (0, 1), (250001, 1), (1, True),
                                (1, 0), (1, 14), (1, float("nan")), (1, float("inf"))):
            with self.subTest(events=events, seconds=seconds), self.assertRaises(ValueError):
                validate(events, seconds)

    def test_real_spawn_retains_exact_history_and_actual_terminal_receipt(self):
        with TemporaryDirectory() as temporary:
            output = Path(temporary)/"probe"
            summary = run(20, output, observe_seconds=3)
            self.assertTrue(summary["history_unchanged"])
            self.assertEqual(summary["initial_history"]["events"], 20)
            self.assertEqual(summary["initial_query"]["state"], "PENDING")
            self.assertEqual(summary["final_query"]["state"], "REJECTED")
            self.assertEqual(summary["final_query"]["error"]["code"], "order_not_found")
            self.assertIsNotNone(summary["ready_observed_ns"])
            self.assertFalse(summary["production_approved"])
            self.assertFalse(summary["ha_approved"])
            self.assertFalse(summary["capacity_passed"])
            traces = [json.loads(line) for path in (output/"traces").glob("*.jsonl")
                      for line in path.read_text().splitlines()]
            verifies = [row for row in traces if row["phase"] == "ledger_verify" and row["event"] == "end"]
            self.assertEqual([row["verified_events"] for row in verifies], [20])
            self.assertTrue(all(row["pid"] != os.getpid() for row in traces))
            reports = [row["value"] for row in traces if row["phase"] == "report"]
            self.assertEqual(reports[0]["state"], "ready")
            acquisitions = [row for row in summary["final_history"]["lease_events"] if row["kind"] == "acquired"]
            self.assertEqual(len(acquisitions), 1)
            self.assertEqual(acquisitions[0]["owner_pid"], reports[0]["pid"])
            self.assertEqual(acquisitions[0]["expires_ns"]-acquisitions[0]["observed_ns"], 5_000_000_000)
            self.assertEqual(summary["initial_history"]["ledger_hash"], summary["final_history"]["ledger_hash"])
            with self.assertRaises(AssertionError):
                check_history(output/"authority/shard-0000.sqlite3", 19)

    def test_archived_expiry_is_distinct_from_late_ready_and_pending(self):
        root = Path(__file__).resolve().parents[1]/"benchmarks/results/20261117-recovery-scaling"
        manifest = json.loads((root/"manifest.json").read_text())
        for name, expected in manifest["files"].items():
            value = (root/name).read_bytes()
            self.assertEqual(len(value), expected["bytes"])
            self.assertEqual(sha256(value).hexdigest(), expected["sha256"])
        analysis = json.loads((root/"analysis.json").read_text())
        self.assertFalse(analysis["production_approved"])
        self.assertFalse(analysis["ha_approved"])
        self.assertFalse(analysis["capacity_passed"])
        self.assertEqual([row["events"] for row in analysis["cohorts"]], [1000, 10000, 50000, 200000, 250000])
        for cohort in analysis["cohorts"]:
            self.assertTrue(cohort["history_unchanged"])
            self.assertEqual(cohort["initial_hash"], cohort["final_hash"])
            self.assertEqual(cohort["child_pids_still_present_after_cleanup"], [])
            self.assertLess(cohort["total_ns"], 45_000_000_000)
        expiry = analysis["cohorts"][-1]
        self.assertIsNone(expiry["observed_ready_ns"])
        self.assertIsNone(expiry["observed_terminal_ns"])
        self.assertEqual(expiry["final_query"]["state"], "PENDING")
        self.assertIsNone(expiry["final_query"]["error"])
        self.assertEqual(len(expiry["acquisitions"]), 2)
        self.assertTrue(expiry["expired_alive_observations"])
        first, second = expiry["acquisitions"]
        self.assertGreater(second["observed_ns"], first["expires_ns"])
        reports = expiry["all_child_ready_emissions"]
        self.assertEqual([row["value"]["generation"] for row in reports], [2])
        observed = [json.loads(line) for line in (root/"250000/observations.jsonl").read_text().splitlines()]
        self.assertGreater(reports[0]["monotonic_ns"], observed[-1]["monotonic_ns"])


if __name__ == "__main__":
    unittest.main()
