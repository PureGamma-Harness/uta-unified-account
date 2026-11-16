from dataclasses import replace
import gzip
from hashlib import sha256
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from benchmarks.run_managed_benchmark import Configuration, run, terminal_outcome
from uta.durable_process import DurableProcessRouter
from uta.service import ServiceError


class ManagedBenchmarkTests(unittest.TestCase):
    def test_bounds_reject_long_or_unbounded_component_capacity_claims(self):
        for values in ({"duration": 1800}, {"shards": 5}, {"accounts": 1, "shards": 2},
                       {"duration": float("nan")}, {"outstanding": True}, {"rate": 10000}, {"profile": 1}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                replace(Configuration(), **values).validate()

    def test_queued_ack_cannot_be_counted_as_financial_success(self):
        with self.assertRaisesRegex(ValueError, "not a financial terminal"):
            terminal_outcome({"state": "PENDING", "ack": "durably_queued", "result": None})
        self.assertEqual(terminal_outcome({"state": "QUARANTINED"}), "technical_quarantined")
        self.assertEqual(terminal_outcome({"state": "REJECTED", "error": {"code": "router_halted", "status": 503}}),
                         "control_or_market_rejected")
        self.assertEqual(terminal_outcome({"state": "REJECTED", "error": {"status": 409}}), "business_rejected")

    def inspect(self, directory, summary, expected):
        with gzip.open(directory / "arrivals.jsonl.gz", "rt") as stream:
            rows = [json.loads(line) for line in stream]
        self.assertEqual(len(rows), expected)
        self.assertEqual(len({row["command_id"] for row in rows}), expected)
        self.assertTrue(all(row["latency_ns"] == row["observed_completion_ns"] - row["planned_ns"] for row in rows))
        self.assertTrue(summary["readonly_reconciliation"]["reopened_readonly"])
        self.assertFalse(summary["production_approved"])
        self.assertFalse(summary["capacity_10000_per_s_passed"])
        self.assertTrue(summary["initial_real_pid_and_fence"]["decision_audit_required"])
        self.assertTrue(all(row["pid"] != os.getpid() and row["owner_pid"] == row["pid"] and row["lease_active"]
                            for row in summary["initial_real_pid_and_fence"]["workers"]))
        for name, proof in json.loads((directory / "manifest.json").read_text())["files"].items():
            data = (directory / name).read_bytes()
            self.assertEqual(sha256(data).hexdigest(), proof["sha256"])
        return rows

    def test_real_spawn_audited_commit_reject_and_per_pid_profile(self):
        with TemporaryDirectory() as temporary:
            directory = Path(temporary) / "managed"
            summary = run(Configuration(duration=.2, rate=10, accounts=2, shards=1, outstanding=4,
                inbox_capacity=4, reject_every=2, drain_seconds=5, profile=True), directory)
            rows = self.inspect(directory, summary, 2)
            self.assertEqual(summary["counts"].get("financial_succeeded"), 1)
            self.assertEqual(summary["counts"].get("business_rejected"), 1)
            self.assertEqual(summary["readonly_reconciliation"]["persistent_successes"], 1)
            self.assertEqual(summary["readonly_reconciliation"]["pending_count"], 0)
            self.assertEqual(set(summary["latency_ms"]["financial_succeeded"]), {"p50", "p95", "p99", "p99_9"})
            profiles = list((directory / "profiles").glob("worker-0-pid-*.prof"))
            self.assertEqual(len(profiles), 1)
            self.assertTrue(all(row["enqueue_ack_ns"] is not None for row in rows))
            self.assertLess(rows[0]["planned_ns"], rows[1]["planned_ns"])

    def test_missing_enqueue_ack_queries_original_cid_and_preserves_error_count(self):
        original = DurableProcessRouter.submit_order
        def lost(router, *args, **kwargs):
            original(router, *args, **kwargs)
            raise ServiceError("storage_unavailable", "synthetic missing metadata response", 503)
        with TemporaryDirectory() as temporary, patch.object(DurableProcessRouter, "submit_order", lost):
            directory = Path(temporary) / "unknown-ack"
            summary = run(Configuration(duration=.1, rate=10, accounts=1, shards=1, reject_every=0,
                outstanding=2, inbox_capacity=2, drain_seconds=5), directory)
            rows = self.inspect(directory, summary, 1)
            self.assertEqual(summary["counts"]["durably_enqueued"], 0)
            self.assertEqual(summary["counts"]["enqueue_technical_errors"], 1)
            self.assertEqual(summary["counts"]["financial_succeeded"], 1)
            self.assertIsNone(rows[0]["enqueue_ack_ns"])
            self.assertEqual(rows[0]["receipt"]["command_id"], "bench:0")


if __name__ == "__main__":
    unittest.main()
