"""Preserve evidence of an optimization that did not meet its merge threshold."""
import gzip
from hashlib import sha256
import json
from pathlib import Path
import unittest


class WALDiagnosticEvidenceTests(unittest.TestCase):
    def test_six_repeated_runs_preserve_unique_raw_results_and_failed_gates(self):
        root = Path(__file__).resolve().parents[1] / "benchmarks/results/20261114-wal-lifetime"
        runs = []
        for variant in ("before", "after"):
            for index in (1, 2, 3):
                directory = root / f"{variant}-{index}"
                manifest = json.loads((directory / "manifest.json").read_text())
                for filename, expected in manifest["files"].items():
                    data = (directory / filename).read_bytes()
                    self.assertEqual(sha256(data).hexdigest(), expected["sha256"])
                    self.assertEqual(len(data), expected["bytes"])
                summary = json.loads((directory / "summary.json").read_text())
                with gzip.open(directory / "arrivals.jsonl.gz", "rt") as stream:
                    arrivals = [row for line in stream if (row := json.loads(line))["kind"] == "arrival"]
                self.assertEqual(len(arrivals), 5000)
                self.assertEqual(len({row["sequence"] for row in arrivals}), 5000)
                self.assertEqual(sum(row["outcome"] == "durable_accepted" for row in arrivals),
                                 summary["counts"]["durable_accepted"])
                with gzip.open(directory / "storage-source.py.gz", "rb") as stream:
                    self.assertEqual(sha256(stream.read()).hexdigest(),
                                     summary["environment"]["source_sha256"]["storage.py"])
                self.assertFalse(summary["gates"]["passed"])
                self.assertFalse(summary["gates"]["phase1_exchange_acceptance_passed"])
                runs.append((variant, index))
        comparison = json.loads((root / "comparison.json").read_text())
        self.assertEqual(len(comparison["runs"]), len(runs))
        self.assertFalse(comparison["production_approved"])


if __name__ == "__main__":
    unittest.main()
