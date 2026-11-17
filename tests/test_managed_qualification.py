"""Gate fixtures are synthetic runner records, never actual acceptance evidence."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from benchmarks.managed_qualification import qualify, source_manifest
from benchmarks.run_managed_soak import Configuration, ManagedSoak, require_long_run_ready


class ManagedQualificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "checkout"
        self.root.mkdir()
        for name in ("uta/storage.py", "uta/other.py", "tests/test_one.py", "tests/fixtures/old.tar.gz",
                     "tools/run_validation.py", "benchmarks/run_managed_soak.py", "benchmarks/managed_qualification.py",
                     "benchmarks/run_soak.py", "benchmarks/run_benchmark.py", "scripts/example.py",
                     "formal/check.py", "pyproject.toml", "MANIFEST.in", "LICENSE", "docs/guide.md"):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"synthetic gate fixture\n")
        self.git("init", "-q")
        self.git("add", ".")
        self.commit()
        self.output = Path(self.tmp.name) / "validation"
        self.output.mkdir()
        self.path = self.output / "summary.json"
        self.worker = {"tests_run": 3, "failures": 0, "errors": 0, "skipped": 0,
            "expected_failures": 0, "unexpected_successes": 0, "unittest_passed": True}
        self.log = b"test fixture output\n----------------------------------------------------------------------\nRan 3 tests in 0.01s\n\nOK\n"
        self.report = {"code_commit": self.git("rev-parse", "HEAD"), **self.worker,
            "command_argv": [sys.executable, str(self.root / "tools/run_validation.py"), "--output", str(self.output)],
            "python": sys.version, "sqlite": sqlite3.sqlite_version, "worker_exit_code": 0, "passed": True,
            "source_unchanged": True, "tracked_source_clean_before": True, "tracked_source_clean_after": True,
            "source_sha256": source_manifest(self.root), "source_sha256_after": source_manifest(self.root),
            "test_log_sha256": sha256(self.log).hexdigest(), "production_approved": False}
        self.write()

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, text=True, stderr=subprocess.DEVNULL).strip()

    def commit(self):
        self.git("-c", "user.name=Gate Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture")

    def write(self):
        self.path.write_text(json.dumps(self.report))
        (self.output / "worker-result.json").write_text(json.dumps(self.worker))
        (self.output / "unittest.txt").write_bytes(self.log)

    def test_complete_matching_evidence_is_preserved_without_granting_duration_or_production(self):
        result = qualify(self.path, root=self.root)
        self.assertTrue(result.evidence["engineering_test_qualified"])
        for key in ("production_approved", "continuous_6h_stability_passed", "continuous_24h_stability_passed"):
            self.assertFalse(result.evidence[key])
        target = Path(self.tmp.name) / "evidence"
        result.record(target)
        self.assertEqual(qualify(target / "summary.json", root=self.root).evidence, result.evidence)
        for name, raw in result.artifacts.items():
            self.assertEqual((target / name).read_bytes(), raw)

    def test_false_passed_flags_and_nonzero_missing_or_boolean_counts_are_rejected(self):
        original = deepcopy(self.report)
        for key in ("passed", "unittest_passed", "source_unchanged", "tracked_source_clean_before", "tracked_source_clean_after"):
            for value in (False, 1, "true", None):
                with self.subTest(key=key, value=value):
                    self.report = {**original, key: value}; self.write()
                    with self.assertRaises(RuntimeError):
                        qualify(self.path, root=self.root)
        for key in ("failures", "errors", "skipped", "expected_failures", "unexpected_successes", "worker_exit_code", "tests_run"):
            for value in (None, True, False, -1, "0", 0 if key == "tests_run" else 1):
                with self.subTest(key=key, value=value):
                    self.report = {**original, key: value}; self.write()
                    with self.assertRaises(RuntimeError):
                        qualify(self.path, root=self.root)

    def test_missing_sidecars_and_dishonest_log_or_worker_cannot_be_hidden_by_passed(self):
        for name in ("summary.json", "worker-result.json", "unittest.txt"):
            self.write(); (self.output / name).unlink()
            with self.subTest(missing=name), self.assertRaises(RuntimeError):
                qualify(self.path, root=self.root)
        self.write()
        (self.output / "unittest.txt").write_bytes(self.log + b"changed")
        with self.assertRaisesRegex(RuntimeError, "checksum"):
            qualify(self.path, root=self.root)
        self.log = b"Ran 3 tests in .01s\n\nFAILED (failures=1)\n"
        self.report["test_log_sha256"] = sha256(self.log).hexdigest(); self.write()
        with self.assertRaisesRegex(RuntimeError, "raw log"):
            qualify(self.path, root=self.root)
        self.log = b"Ran 3 tests in .01s\n\nOK\n"
        self.report["test_log_sha256"] = sha256(self.log).hexdigest()
        self.worker["tests_run"] = 4; self.write()
        with self.assertRaisesRegex(RuntimeError, "disagree"):
            qualify(self.path, root=self.root)

    def test_entire_git_tree_and_exact_commit_are_required_even_when_runtime_bytes_match(self):
        for name in ("docs/guide.md", "uta/storage.py", "untracked.txt"):
            path = self.root / name
            original = path.read_bytes() if path.exists() else None
            path.write_bytes(b"changed")
            with self.subTest(path=name), self.assertRaisesRegex(RuntimeError, "clean"):
                qualify(self.path, root=self.root)
            if original is None:
                path.unlink()
            else:
                path.write_bytes(original)
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "--allow-empty", "-qm", "same bytes new SHA")
        with self.assertRaisesRegex(RuntimeError, "code_commit"):
            qualify(self.path, root=self.root)

    def test_full_manifest_keyset_and_all_dependency_digests_must_match(self):
        original = deepcopy(self.report)
        for field in ("source_sha256", "source_sha256_after"):
            for name in original[field]:
                for change in ("missing", "wrong"):
                    self.report = deepcopy(original)
                    if change == "missing":
                        del self.report[field][name]
                    else:
                        self.report[field][name] = "0" * 64
                    self.write()
                    with self.subTest(field=field, path=name, change=change), self.assertRaisesRegex(RuntimeError, "manifest"):
                        qualify(self.path, root=self.root)
        self.report = deepcopy(original)
        self.report["source_sha256"]["extra.py"] = "0" * 64; self.write()
        with self.assertRaisesRegex(RuntimeError, "manifest"):
            qualify(self.path, root=self.root)

    def test_different_runtime_partial_command_duplicate_keys_and_nan_are_rejected(self):
        original = deepcopy(self.report)
        for changes in ({"python": "other"}, {"sqlite": "other"}, {"command_argv": ["python", "partial.py"]},
                        {"production_approved": True}):
            self.report = {**original, **changes}; self.write()
            with self.subTest(changes=changes), self.assertRaises(RuntimeError):
                qualify(self.path, root=self.root)
        self.report = original; self.write()
        for content in ('{"passed":true,"passed":false}', '{"passed": NaN}'):
            self.path.write_text(content)
            with self.assertRaises(RuntimeError):
                qualify(self.path, root=self.root)

    def test_failed_qualification_precedes_all_job_state_on_run_and_resume(self):
        target = Path(self.tmp.name) / "must-not-create"
        self.report["skipped"] = self.worker["skipped"] = 1; self.write()
        with patch("benchmarks.run_managed_soak.qualify", lambda path: qualify(path, root=self.root)):
            with self.assertRaises(RuntimeError):
                ManagedSoak(target, Configuration(duration=21600), allow_long_run=True, validation_report=self.path)
            self.assertFalse(target.exists())
            target.mkdir(mode=0o700)
            original = json.dumps({"configuration": Configuration(duration=21600).__dict__, "validation_evidence": None})
            (target / "job.json").write_text(original)
            with self.assertRaises(RuntimeError):
                ManagedSoak(target, resume=True, allow_long_run=True, validation_report=self.path)
            self.assertEqual([p.name for p in target.iterdir()], ["job.json"])
            self.assertEqual((target / "job.json").read_text(), original)

    def test_explicit_opt_in_is_independent_of_valid_report(self):
        with patch("benchmarks.run_managed_soak.qualify", lambda path: qualify(path, root=self.root)):
            for changes in ({}, {"allow_long_run": 1}, {"allow_long_run": "true"},
                            {"allow_long_run": True, "strict_source": False}):
                with self.assertRaises(RuntimeError):
                    require_long_run_ready(21600, validation_report=self.path, **changes)
            self.assertIsNotNone(require_long_run_ready(21600, allow_long_run=True, validation_report=self.path))

    def test_source_movement_during_qualification_and_changed_evidence_are_detected(self):
        actual = source_manifest(self.root)
        with patch("benchmarks.managed_qualification.source_manifest", side_effect=[actual, {}]):
            with self.assertRaisesRegex(RuntimeError, "changed during qualification"):
                qualify(self.path, root=self.root)
        accepted = qualify(self.path, root=self.root)
        job = object.__new__(ManagedSoak)
        job.validation = accepted
        job.directory = Path(self.tmp.name) / "job"
        accepted.record(job.directory / "validation")
        job._assert_validation_evidence()
        (job.directory / "validation/worker-result.json").write_text("{}")
        with self.assertRaisesRegex(RuntimeError, "evidence changed"):
            job._assert_validation_evidence()


if __name__ == "__main__":
    unittest.main()
