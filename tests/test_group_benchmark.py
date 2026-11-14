import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import time

from benchmarks.run_group_benchmark import Configuration, capacity_gates, run
from uta.service import ExchangeService, ServiceError


class GroupBenchmarkTests(unittest.TestCase):
    def test_bounds_prevent_fake_long_feed_or_order_limit_results(self):
        for config in (Configuration(mode="other"), Configuration(policy="other"), Configuration(rate=float("nan")),
                       Configuration(duration=1800), Configuration(drain_seconds=11),
                       Configuration(accounts=1, duration=10, rate=100),
                       Configuration(shards=2, accounts=1), Configuration(queue_capacity=True),
                       Configuration(batch_delay_ms=-1), Configuration(workers=0)):
            with self.subTest(config=config), self.assertRaises(ValueError):
                config.validate()

    def test_capacity_uses_success_and_long_window_not_attempts(self):
        for duration, rate, counts in ((5, 100000, {}), (1800, 0, {"business_rejected": 20_000_000}),
                                      (1800, 10000, {"unknown": 1}), (1800, 10000, {"accepted_late": 1})):
            self.assertFalse(capacity_gates(duration, rate, counts, 1)["passed"])
        gate = capacity_gates(1800, 10000, {}, 1)
        self.assertTrue(gate["passed"])
        self.assertFalse(gate["phase1_exchange_acceptance_passed"])
        self.assertFalse(gate["production_approved"])

    def check_results(self, directory, summary):
        self.assertFalse(summary["gates"]["passed"])
        self.assertFalse(summary["gates"]["production_approved"])
        self.assertEqual(summary["counts"].get("technical_failed", 0), 0)
        self.assertEqual(summary["counts"].get("unknown", 0), 0)
        with gzip.open(directory / "arrivals.jsonl.gz", "rt") as stream:
            rows = [json.loads(line) for line in stream]
        self.assertEqual(len(rows), summary["offered_arrivals"])
        self.assertEqual(len({row["sequence"] for row in rows}), len(rows))
        self.assertTrue(all(row["latency_ns"] == row["completed_ns"] - row["scheduled_ns"] for row in rows))
        self.assertTrue(all(row["worker_started_ns"] is not None for row in rows if row["durable_committed"]))
        self.assertEqual(sum(row["unique_orders"] for row in summary["durability_checks"]),
                         summary["counts"].get("durable_accepted", 0))
        self.assertTrue(all(row["all_orders_remain_open"] and row["independent_live_reserves_verified"]
                            for row in summary["durability_checks"]))
        manifest = json.loads((directory / "manifest.json").read_text())
        for name, expected in manifest["files"].items():
            data = (directory / name).read_bytes()
            self.assertEqual(len(data), expected["bytes"])
            self.assertEqual(hashlib.sha256(data).hexdigest(), expected["sha256"])
        return rows

    def test_sync_open_loop_keeps_orders_live_and_checks_exact_reserves(self):
        with TemporaryDirectory() as temporary:
            directory = Path(temporary) / "sync"
            summary = run(Configuration(duration=.2, rate=30, accounts=4, shards=2), directory)
            rows = self.check_results(directory, summary)
            self.assertEqual(summary["offered_arrivals"], 6)
            self.assertEqual(summary["environment"]["policy"], "configured_cross")
            self.assertIn("portfolio_rules", summary["environment"]["effective_policy"])
            self.assertEqual(summary["counts"]["durable_accepted"], 6)
            self.assertEqual(len(summary["durability_checks"]), 2)
            ordered = sorted(rows, key=lambda row: row["sequence"])
            self.assertEqual(ordered[1]["scheduled_ns"] - ordered[0]["scheduled_ns"], 33333333)

    def test_batch_raw_records_real_group_commit_and_worker_timing(self):
        with TemporaryDirectory() as temporary:
            directory = Path(temporary) / "batch"
            summary = run(Configuration(mode="batch", duration=.04, rate=2500, accounts=10,
                                        queue_capacity=128, batch_size=32, batch_delay_ms=10), directory)
            rows = self.check_results(directory, summary)
            self.assertEqual(summary["counts"]["durable_accepted"], 100)
            stats = summary["batch_stats"][0]
            self.assertLess(stats["committed_batches"], stats["committed_commands"])
            self.assertTrue(all(row["receipt_published_ns"] <= row["completed_ns"] for row in rows))
            self.assertTrue(all(row["admission_enqueued_ns"] <= row["worker_started_ns"] for row in rows))

    def test_slow_sync_worker_does_not_shift_planned_arrivals_or_lose_overload(self):
        original = ExchangeService.submit_order
        def slow(service, *args, **kwargs):
            time.sleep(.005)
            return original(service, *args, **kwargs)
        with TemporaryDirectory() as temporary, patch.object(ExchangeService, "submit_order", slow):
            directory = Path(temporary) / "slow"
            summary = run(Configuration(duration=.05, rate=1000, accounts=10, workers=1,
                                        queue_capacity=1), directory)
            rows = self.check_results(directory, summary)
            self.assertGreater(summary["counts"]["overload"], 0)
            ordered = sorted(rows, key=lambda row: row["sequence"])
            self.assertEqual(ordered[-1]["scheduled_ns"] - ordered[0]["scheduled_ns"], 49_000_000)
            self.assertEqual(len(rows), 50)

    def test_cli_smoke_is_distinct_from_failed_capacity_gate(self):
        with TemporaryDirectory() as temporary:
            output = Path(temporary) / "probe"
            command = [sys.executable, str(Path(__file__).resolve().parents[1] / "benchmarks/run_group_benchmark.py"),
                       "--duration", ".1", "--rate", "20", "--accounts", "2", "--output", str(output), "--smoke"]
            process = subprocess.run(command, capture_output=True, text=True, timeout=20)
            self.assertEqual(process.returncode, 0, process.stderr)
            summary = json.loads(process.stdout)
            self.assertFalse(summary["gates"]["passed"])
            self.assertEqual(summary["counts"]["durable_accepted"], 2)

    def test_legacy_is_explicit_and_cannot_be_confused_with_configured_cross(self):
        with TemporaryDirectory() as temporary:
            summary = run(Configuration(policy="legacy_reference", duration=.1, rate=20, accounts=2),
                          Path(temporary) / "legacy")
            self.assertEqual(summary["environment"]["policy"], "legacy_reference")
            self.assertEqual(summary["environment"]["effective_policy"], {})
            self.assertEqual(summary["counts"]["durable_accepted"], 2)

    def test_lost_success_receipt_is_unknown_and_not_counted_as_acknowledged_capacity(self):
        original = ExchangeService.submit_order
        def lose_response(service, *args, **kwargs):
            original(service, *args, **kwargs)
            raise ServiceError("storage_unavailable", "synthetic lost post-commit response", 503)
        with TemporaryDirectory() as temporary, patch.object(ExchangeService, "submit_order", lose_response):
            summary = run(Configuration(duration=.1, rate=20, accounts=2), Path(temporary) / "unknown")
            self.assertEqual(summary["counts"]["unknown"], 2)
            self.assertEqual(summary["unique_durable_accepted_per_s"], 0)
            self.assertEqual(summary["unknown_resolution"]["unacknowledged_orders_found"], 2)
            self.assertFalse(summary["gates"]["passed"])

    def test_archived_probes_preserve_every_arrival_and_failed_gate(self):
        root = Path(__file__).resolve().parents[1] / "benchmarks/results"
        cohorts = (("20261114-group-cross", 5, 5000), ("20261114-group-cross-final", 2, 25000))
        for name, runs, offered in cohorts:
            cohort = root / name
            window = json.loads((cohort / "run-window.json").read_text())
            self.assertEqual(len(window["runs"]), runs)
            for entry in window["runs"]:
                directory = cohort / entry["label"]
                manifest = json.loads((directory / "manifest.json").read_text())
                for filename, evidence in manifest["files"].items():
                    raw = (directory / filename).read_bytes()
                    self.assertEqual(hashlib.sha256(raw).hexdigest(), evidence["sha256"])
                    self.assertEqual(len(raw), evidence["bytes"])
                summary = json.loads((directory / "summary.json").read_text())
                with gzip.open(directory / "arrivals.jsonl.gz", "rt") as stream:
                    rows = [json.loads(line) for line in stream]
                self.assertEqual(len(rows), offered)
                self.assertEqual(len({row["sequence"] for row in rows}), offered)
                for outcome, count in Counter(row["outcome"] for row in rows).items():
                    self.assertEqual(summary["counts"][outcome], count)
                self.assertFalse(summary["gates"]["passed"])
                self.assertFalse(summary["gates"]["phase1_exchange_acceptance_passed"])
                self.assertEqual(summary["environment"]["policy"], "configured_cross")


if __name__ == "__main__":
    unittest.main()
