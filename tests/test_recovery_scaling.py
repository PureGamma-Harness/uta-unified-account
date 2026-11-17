import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from benchmarks.run_recovery_scaling import check_history, run, validate


class RecoveryScalingTests(unittest.TestCase):
    def test_bounds_require_finite_short_work(self):
        for events, seconds in ((True, 1), (0, 1), (200001, 1), (1, True),
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


if __name__ == "__main__":
    unittest.main()
