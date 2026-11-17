"""Exercise the evidence recorder in a separate, minimal committed checkout."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


class ValidationRecorderTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name in ("tools", "tests", "formal", "uta"):
            (self.root / name).mkdir()
        script = Path(__file__).resolve().parents[1] / "tools" / "run_validation.py"
        shutil.copyfile(script, self.root / "tools" / "run_validation.py")
        self.source = self.root / "tests" / "test_probe.py"

    def run_probe(self, code, *, dirty=False):
        self.source.write_text(code)
        for arguments in (("init", "-q"), ("add", "."),
                          ("-c", "user.name=synthetic", "-c", "user.email=synthetic@example.invalid",
                           "commit", "-qm", "synthetic recorder fixture")):
            subprocess.run(["git", *arguments], cwd=self.root, check=True, capture_output=True)
        if dirty:
            self.source.write_text(code + "\n# uncommitted source\n")
        output = self.root / "results"
        process = subprocess.run([sys.executable, "tools/run_validation.py", "--output", str(output)],
                                 cwd=self.root, capture_output=True, text=True, timeout=15)
        return process, json.loads((output / "summary.json").read_text()), (output / "unittest.txt").read_text()

    def test_raw_os_child_stderr_is_archived_and_real_test_count_retained(self):
        process, report, log = self.run_probe('''import subprocess, sys, unittest
class Probe(unittest.TestCase):
    def test_child(self):
        subprocess.run([sys.executable, '-c', 'import os; os.write(2,b"child-fd2-evidence")'], check=True)
''')
        self.assertEqual(process.returncode, 0, (process.stderr, report, log))
        self.assertEqual(report["tests_run"], 1)
        self.assertTrue(report["passed"])
        self.assertTrue(report["source_unchanged"])
        self.assertIn("child-fd2-evidence", log)
        self.assertFalse(report["production_approved"])

    def test_real_failure_count_and_worker_exit_are_preserved(self):
        process, report, log = self.run_probe('''import unittest
class Probe(unittest.TestCase):
    def test_failure(self): self.assertEqual(1, 2)
''')
        self.assertEqual(process.returncode, 1)
        self.assertEqual((report["tests_run"], report["failures"], report["errors"]), (1, 1, 0))
        self.assertEqual(report["worker_exit_code"], 1)
        self.assertFalse(report["passed"])
        self.assertIn("AssertionError", log)

    def test_passing_tests_cannot_approve_sources_changed_during_execution(self):
        process, report, _ = self.run_probe('''from pathlib import Path
import unittest
class Probe(unittest.TestCase):
    def test_mutation(self):
        path = Path(__file__)
        path.write_text(path.read_text() + "\\n# changed while executing\\n")
''')
        self.assertEqual(process.returncode, 1)
        self.assertTrue(report["unittest_passed"])
        self.assertFalse(report["source_unchanged"])
        self.assertFalse(report["passed"])

    def test_uncommitted_sources_cannot_be_certified_as_the_recorded_commit(self):
        process, report, _ = self.run_probe('''import unittest
class Probe(unittest.TestCase):
    def test_pass(self): pass
''', dirty=True)
        self.assertEqual(process.returncode, 1)
        self.assertTrue(report["unittest_passed"])
        self.assertTrue(report["source_unchanged"])
        self.assertFalse(report["tracked_source_clean_before"])
        self.assertFalse(report["passed"])

    def test_loader_failure_is_recorded_as_an_error_not_a_fake_success(self):
        process, report, log = self.run_probe('raise RuntimeError("synthetic discovery failure")\n')
        self.assertEqual(process.returncode, 1)
        self.assertEqual((report["tests_run"], report["errors"]), (1, 1))
        self.assertFalse(report["passed"])
        self.assertIn("synthetic discovery failure", log)
