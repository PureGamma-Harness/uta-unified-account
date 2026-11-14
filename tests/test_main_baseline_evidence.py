"""Integrity checks for the untouched published-main benchmark rerun."""
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1] / "evidence/main-baseline-20261114"
NAMES = ("compute-eight-workers", "wal-four-shards", "wal-single-file",
         "paced-overload", "wal-group-commit", "wal-fused-liquidation")
BASELINE = "f8d72efaac69353113740d34d7ae5c39e3828c7a"


def read(name):
    return json.loads((ROOT / name).read_text())


class PublishedMainEvidenceTests(unittest.TestCase):
    def test_original_outputs_and_invocations_have_integrity_and_no_technical_errors(self):
        manifest = read("manifest.json")
        self.assertEqual(manifest["baseline_commit"], BASELINE)
        self.assertEqual(read("environment.json")["baseline_commit"], BASELINE)
        for name, expected in manifest["files"].items():
            data = (ROOT / name).read_bytes()
            self.assertEqual(sha256(data).hexdigest(), expected["sha256"], name)
            self.assertEqual(len(data), expected["bytes"], name)
        previous = None
        for name in NAMES:
            invocation = read(name + ".invocation.json")
            self.assertEqual(invocation["returncode"], 0)
            started = datetime.fromisoformat(invocation["started_at"])
            finished = datetime.fromisoformat(invocation["finished_at"])
            self.assertGreater(finished, started)
            if previous is not None:
                self.assertGreaterEqual(started, previous)
            previous = finished
            output = read(name + ".stdout.json")
            for mode in ("compute", "admission", "durable", "batch"):
                if mode in output:
                    self.assertEqual(output[mode]["errors"], 0, (name, mode))
                    self.assertGreaterEqual(invocation["process_wall_seconds"], output[mode]["wall_seconds"])

    def test_full_published_computation_and_admission_scales_are_preserved(self):
        compute = read("compute-eight-workers.stdout.json")
        self.assertEqual(compute["workers"], 8)
        counts = compute["compute"]["counts"]
        self.assertEqual(counts["requests"], 160000)
        self.assertEqual(counts["accepted"], 139010)
        self.assertEqual(counts["risk_rejections"], 20990)
        self.assertEqual(counts["maintenance_breaches"], 17133)
        admission = read("wal-four-shards.stdout.json")
        self.assertEqual(admission["workers"], 4)
        self.assertEqual(admission["durable_shards"], 4)
        self.assertEqual(admission["admission"]["counts"]["admission_requests"], 320)
        self.assertEqual(admission["admission"]["counts"]["orders_committed"], 240)
        self.assertEqual(admission["admission"]["counts"]["risk_rejections"], 80)
        self.assertEqual(admission["admission"]["counts"]["reopened_accounts_verified"], 320)

    def test_simulated_liquidations_and_paced_overload_are_never_conflated(self):
        for name, mode in (("wal-four-shards", "durable"), ("wal-single-file", "durable"),
                           ("wal-group-commit", "batch"), ("wal-fused-liquidation", "batch")):
            output = read(name + ".stdout.json")
            self.assertNotIn("offered_arrivals_per_second", output)
            counts = output[mode]["counts"]
            self.assertEqual(counts["liquidation_fills_committed"], 320)
            self.assertEqual(counts["account_liquidations_completed"], 320)
            self.assertEqual(counts["reopened_accounts_verified"], 320)
            self.assertEqual(counts["accounts_not_completed"], 0)
            self.assertEqual(counts["end_health_INSOLVENT"], 320)
        paced = read("paced-overload.stdout.json")
        self.assertEqual(paced["offered_arrivals_per_second"], 10000)
        counts = paced["durable"]["counts"]
        self.assertEqual(counts["scheduled_arrivals"], 400)
        self.assertEqual(counts["account_liquidations_completed"] + counts["overload_rejections"], 400)
        self.assertEqual(counts["liquidation_fills_committed"], counts["account_liquidations_completed"])
        self.assertEqual(counts["accounts_not_completed"], counts["overload_rejections"])
        self.assertGreater(counts["overload_rejections"], 0)
        self.assertLessEqual(counts["max_pending_observed"], 8)


if __name__ == "__main__":
    unittest.main()
