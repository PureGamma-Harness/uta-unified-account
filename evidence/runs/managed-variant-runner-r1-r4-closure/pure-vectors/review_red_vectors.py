"""Independent bounded JSON controls for frozen runner 35e; no SQL or child.

The immutable author's raw_fixture constructs synthetic rows only; assertions
below are reviewer-owned invariants. This is an intentionally RED historical
review executable, outside unittest discovery. Do not turn it into release QA
or rerun a benchmark to erase the original findings.
"""
from __future__ import annotations
import gzip
import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(SOURCE))
from tools import run_managed_variants as runner
from tests.test_managed_variant_runner import COMMIT, raw_fixture


class ReaderExceededBound(RuntimeError):
    pass


class IterationProbe(io.StringIO):
    def __init__(self, text):
        super().__init__(text)
        self.iteration_reads = 0

    def __next__(self):
        self.iteration_reads += 1
        if self.iteration_reads > 201:
            raise ReaderExceededBound("reader attempted arrival 202 before planned-count refusal")
        return super().__next__()


class IndependentRunnerDataContracts(unittest.TestCase):
    def manifest(self, root):
        target = root / "manifest.json"
        value = json.loads(target.read_text())
        for name in list(value["files"]):
            item = root / name
            value["files"][name] = {"bytes": item.stat().st_size, "sha256": runner.digest(item)}
        target.write_text(json.dumps(value) + "\n")

    def test_raw_late_success_must_override_contradictory_green_summary_flag(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            hashes = raw_fixture(root, late=True)
            path = root / "summary.json"
            value = json.loads(path.read_text())
            value["probe_qualification"]["financial_soft_deadline_passed"] = True
            path.write_text(json.dumps(value) + "\n")
            self.manifest(root)
            result = runner.recompute(root, runner.schedule()[0], hashes, COMMIT)
            self.assertEqual(result["financial_success_late"], 1)
            self.assertFalse(result["technical_and_deadline_passed"],
                "raw 2s success must refuse a 1s deadline despite supplied green flag")

    def test_every_consumed_original_artifact_must_be_manifest_covered(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            hashes = raw_fixture(root)
            manifest = root / "manifest.json"
            value = json.loads(manifest.read_text())
            value["files"] = {"measurement-footer.json": value["files"]["measurement-footer.json"]}
            manifest.write_text(json.dumps(value) + "\n")
            with self.assertRaises(runner.GateError,
                    msg="summary, schedule and arrivals cannot be accepted without manifest hashes"):
                runner.recompute(root, runner.schedule()[0], hashes, COMMIT)

    def test_raw_reader_must_refuse_extra_rows_before_reading_an_unbounded_tail(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            hashes = raw_fixture(root)
            text = gzip.decompress((root / "arrivals.jsonl.gz").read_bytes()).decode()
            text += text.splitlines()[0] + "\n"  # one actual excess row only
            probe = IterationProbe(text)
            with patch.object(runner.gzip, "open", return_value=probe):
                with self.assertRaises(runner.GateError,
                        msg="planned 200-row reader must bound reads before materializing tail"):
                    runner.recompute(root, runner.schedule()[0], hashes, COMMIT)

    def test_untampered_synthetic_control_has_derived_N_max_and_denominator(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            hashes = raw_fixture(root)
            result = runner.recompute(root, runner.schedule()[0], hashes, COMMIT)
            self.assertIs(result["technical_and_deadline_passed"], True)
            self.assertEqual(result["groups"]["financial_succeeded"]["N"], 180)
            self.assertEqual(result["groups"]["financial_succeeded"]["max_ns"], 1000000)
            self.assertEqual(result["denominator_ns"], 10000000000)
            self.assertEqual(result["financial_per_second"], 18.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
