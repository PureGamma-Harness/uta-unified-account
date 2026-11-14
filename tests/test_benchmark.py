from dataclasses import replace
from collections import Counter
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from benchmarks.run_benchmark import Configuration, LatencyHistogram, gates


class BenchmarkTests(unittest.TestCase):
    def test_histogram_tail_percentiles_and_empty_report(self):
        histogram = LatencyHistogram()
        self.assertIsNone(histogram.report()["p99"])
        for value in range(1, 1001):
            histogram.observe(value * 1000)
        for percentile, expected in ((.5, 500000), (.95, 950000), (.99, 990000), (.999, 999000)):
            actual = histogram.percentile_ns(percentile)
            self.assertGreaterEqual(actual, expected)
            self.assertLessEqual(actual, expected * 1.001 + 1)

    def test_only_durable_success_can_satisfy_default_capacity_gate(self):
        configuration = Configuration()
        self.assertFalse(gates(configuration, 5, 100000, 1, {})["passed"])
        self.assertFalse(gates(configuration, 1800, 0, 1, {"business_rejected": 18000000})["passed"])
        self.assertFalse(gates(replace(configuration, scenario="compute"), 1800, 100000, 1, {})["passed"])
        self.assertFalse(gates(configuration, 1800, 10000, 1, {"unknown": 1})["passed"])
        self.assertFalse(gates(configuration, 1800, 10000, 1, {"deadline_exceeded": 1})["passed"])
        sufficient = gates(configuration, 1800, 10000, 1, {})
        self.assertTrue(sufficient["passed"])
        self.assertFalse(sufficient["phase1_exchange_acceptance_passed"])

    def test_nonfinite_or_impossible_configuration_rejected(self):
        for configuration in (Configuration(rate=float("nan")), Configuration(duration=-1),
                              Configuration(workers=0), Configuration(shards=101),
                              Configuration(account_skew=1.1), Configuration(queue_capacity=0)):
            with self.subTest(configuration=configuration), self.assertRaises(ValueError):
                configuration.validate()

    def test_real_open_loop_compute_smoke_keeps_every_arrival_and_fails_capacity_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "compute"
            self._run(output, "compute", "--duration", ".2", "--rate", "20", "--workers", "1")
            summary = json.loads((output / "summary.json").read_text())
            rows = [json.loads(line) for line in (output / "arrivals.jsonl").read_text().splitlines()]
            arrivals = sorted((row for row in rows if row["kind"] == "arrival"), key=lambda row: row["sequence"])
            self.assertEqual(len(arrivals), 4)
            self.assertEqual([row["sequence"] for row in arrivals], list(range(4)))
            self.assertEqual(arrivals[1]["scheduled_ns"] - arrivals[0]["scheduled_ns"], 50000000)
            self.assertTrue(all(row["latency_ns"] == row["completed_ns"] - row["scheduled_ns"] for row in arrivals))
            self.assertEqual(summary["unique_durable_accepted_per_s"], 0)
            self.assertFalse(summary["gates"]["passed"])
            self.assertEqual(summary["counts"]["compute_completed"], 4)

    def test_durable_smoke_reconciles_unique_orders_across_two_shards(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "order"
            self._run(output, "order", "--duration", ".3", "--rate", "10", "--workers", "2",
                      "--shards", "2", "--accounts", "4")
            summary = json.loads((output / "summary.json").read_text())
            self.assertEqual(summary["counts"]["durable_accepted"], 3)
            self.assertEqual(summary["counts"]["business_rejected"], 0)
            self.assertEqual(sum(row["unique_orders_in_database"] for row in summary["durability_checks"]), 3)
            self.assertEqual(sum(row["accepted_events_in_database"] for row in summary["durability_checks"]), 3)
            self.assertTrue(all(row["journal_mode"] == "wal" for row in summary["environment"]["storage"]))
            self.assertFalse(summary["gates"]["phase1_exchange_acceptance_passed"])

    def test_recorded_raw_evidence_hashes_unique_ids_and_result_counts(self):
        evidence = Path(__file__).resolve().parent.parent / "benchmarks" / "results"
        directories = sorted(evidence.glob("20261114-v1-*"))
        self.assertEqual(len(directories), 2)
        for directory in directories:
            with self.subTest(directory=directory):
                manifest = json.loads((directory / "manifest.json").read_text())
                for name, expected in manifest["files"].items():
                    data = (directory / name).read_bytes()
                    self.assertEqual(hashlib.sha256(data).hexdigest(), expected["sha256"])
                    self.assertEqual(len(data), expected["bytes"])
                summary = json.loads((directory / "summary.json").read_text())
                with gzip.open(directory / "arrivals.jsonl.gz", "rt") as source:
                    arrivals = [row for line in source if (row := json.loads(line))["kind"] == "arrival"]
                self.assertEqual(len(arrivals), summary["offered_arrivals"])
                self.assertEqual(len({row["sequence"] for row in arrivals}), summary["offered_arrivals"])
                outcomes = Counter(row["outcome"] for row in arrivals)
                for name, count in outcomes.items():
                    self.assertEqual(count, summary["counts"][name])
                self.assertFalse(summary["gates"]["passed"])
                self.assertFalse(summary["gates"]["phase1_exchange_acceptance_passed"])

    def _run(self, output, scenario, *extra):
        script = Path(__file__).resolve().parent.parent / "benchmarks" / "run_benchmark.py"
        result = subprocess.run([sys.executable, str(script), "--output", str(output), "--scenario", scenario,
                                 "--smoke", *extra], env=dict(os.environ),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
