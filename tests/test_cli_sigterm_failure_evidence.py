"""Pure fake-Popen/clock checks; no runtime module, SQL, worker or signal."""
import ast
from copy import deepcopy
from hashlib import sha256
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cli_failure_helper", ROOT / "tests/cli_sigterm_failure_evidence.py")
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


class Tick:
    def __init__(self):
        self.value = 1000
    def __call__(self):
        self.value += 10
        return self.value


class FakeProcess:
    def __init__(self, *, timeout=False, known_exit=True):
        self.pid, self.returncode = 900001, None
        self.args = ["python", "-m", "uta", "exchange", "--credentials", "/private/credentials.json"]
        self.timeout, self.known_exit = timeout, known_exit
        self.kills, self.communications = 0, []
        self.suffix = b"S" * 40000 + b"synthetic-private-stream-marker"
        self.error = b"E" * 40000 + b"synthetic-private-stream-marker"
    def poll(self):
        return self.returncode
    def kill(self):
        self.kills += 1
    def communicate(self, *, timeout):
        self.communications.append(timeout)
        if self.timeout:
            raise subprocess.TimeoutExpired(self.args, timeout,
                                            output=b"partial-out", stderr=b"partial-err")
        if self.known_exit:
            self.returncode = -9
        return self.suffix, self.error


def fake_identity(pid):
    return {"observed": True, "pid": pid, "start_ticks": 100,
            "boot_id": "synthetic-boot", "uid": 1000, "parent": 900000, "state": "S"}


def normalized_method(text):
    tree = ast.parse(text)
    method = deepcopy(next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        and node.name == "test_cli_explicit_automation_starts_with_synthetic_policy_and_stops_cleanly"))
    result = []
    for node in method.body:
        if isinstance(node, ast.FunctionDef) and node.name == "cleanup":
            continue
        if isinstance(node, ast.ImportFrom) and node.module == "tests.cli_sigterm_failure_evidence":
            continue
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "evidence" for target in node.targets):
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if isinstance(call.func, ast.Attribute) and call.func.attr == "addCleanup":
                continue
        parts = node.body if isinstance(node, ast.Try) else [node]
        for item in parts:
            if (isinstance(item, ast.Expr) and isinstance(item.value, ast.Call)
                    and isinstance(item.value.func, ast.Attribute)
                    and isinstance(item.value.func.value, ast.Name)
                    and item.value.func.value.id == "evidence"):
                continue
            result.append(item)
    method.body = result
    for node in ast.walk(method):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "Popen":
            node.keywords = [item for item in node.keywords if item.arg not in {"text", "bufsize"}]
    return ast.dump(method, include_attributes=False)


class CliFailureEvidencePureTests(unittest.TestCase):
    def fixture(self, root, **kwargs):
        process, notice = FakeProcess(**kwargs), io.StringIO()
        capture = helper.CliFailureEvidence(process, artifact_root=root, clock=Tick(),
                                          identity_reader=fake_identity, notice_stream=notice)
        return process, capture, notice

    def test_complete_first_streams_preserve_banner_suffix_and_original_exception(self):
        prefix = b'{"port":123,"automated":true}\n'
        with TemporaryDirectory() as root:
            process, capture, notice = self.fixture(root)
            capture.banner(prefix)
            original = subprocess.TimeoutExpired(process.args, 5)
            try:
                try:
                    raise original
                except BaseException as error:
                    capture.primary_failure(error)
                    raise
                finally:
                    capture.cleanup()
            except subprocess.TimeoutExpired as observed:
                self.assertIs(observed, original)
            capture.cleanup()  # A second cleanup cannot overwrite first streams.
            self.assertEqual(process.communications, [5])
            self.assertEqual(process.kills, 1)
            self.assertEqual((capture.directory / "stdout.bin").read_bytes(), prefix + process.suffix)
            self.assertEqual((capture.directory / "stderr.bin").read_bytes(), process.error)
            self.assertEqual(capture.directory.stat().st_mode & 0o777, 0o700)
            row = json.loads((capture.directory / "evidence.json").read_text())
            self.assertTrue(row["streams_complete"])
            self.assertTrue(row["child_exit_and_reap_confirmed"])
            self.assertEqual(row["returncode"], -9)
            ticks = [item["monotonic_ns"] for item in row["phases"]]
            self.assertEqual(ticks, sorted(set(ticks)))
            self.assertNotIn("synthetic-private-stream-marker", notice.getvalue())
            self.assertNotIn("/private/credentials.json", notice.getvalue())

    def test_cleanup_timeout_preserves_partial_streams_and_unknown_exit(self):
        with TemporaryDirectory() as root:
            process, capture, _ = self.fixture(root, timeout=True)
            capture.banner(b"banner\n")
            original = ValueError("private primary message")
            capture.primary_failure(original)
            capture.cleanup()
            row = json.loads((capture.directory / "evidence.json").read_text())
            self.assertFalse(row["streams_complete"])
            self.assertFalse(row["child_exit_and_reap_confirmed"])
            self.assertEqual(row["cleanup"], "UNKNOWN")
            self.assertEqual((capture.directory / "stdout.bin").read_bytes(), b"banner\npartial-out")
            self.assertEqual((capture.directory / "stderr.bin").read_bytes(), b"partial-err")
            self.assertEqual(process.communications, [5])

    def test_communicate_without_confirmed_exit_cannot_pass_cleanup(self):
        with TemporaryDirectory() as root:
            _, capture, _ = self.fixture(root, known_exit=False)
            with self.assertRaises(helper.CleanupEvidenceError):
                capture.cleanup()
            row = json.loads((capture.directory / "evidence.json").read_text())
            self.assertFalse(row["streams_complete"])
            self.assertFalse(row["child_exit_and_reap_confirmed"])

    def test_archive_exception_never_masks_the_original_primary(self):
        with TemporaryDirectory() as root:
            _, capture, notice = self.fixture(root)
            original = RuntimeError("synthetic-private-primary")
            with patch.object(capture, "_write", side_effect=OSError("synthetic-private-filesystem")):
                try:
                    try:
                        raise original
                    except BaseException as error:
                        capture.primary_failure(error)
                        raise
                    finally:
                        capture.cleanup()
                except RuntimeError as observed:
                    self.assertIs(observed, original)
            self.assertNotIn("synthetic-private-primary", notice.getvalue())
            self.assertNotIn("synthetic-private-filesystem", notice.getvalue())
            self.assertIn('"archive_retained": false', notice.getvalue())

    def test_cleanup_exception_preserves_primary_and_never_claims_reap(self):
        with TemporaryDirectory() as root:
            process, capture, _ = self.fixture(root)
            original = ValueError("private-primary")
            with patch.object(process, "communicate", side_effect=OSError("private-cleanup")):
                try:
                    try:
                        raise original
                    except BaseException as error:
                        capture.primary_failure(error)
                        raise
                    finally:
                        capture.cleanup()
                except ValueError as observed:
                    self.assertIs(observed, original)
            row = json.loads((capture.directory / "evidence.json").read_text())
            self.assertEqual(row["cleanup"], "UNKNOWN")
            self.assertFalse(row["child_exit_and_reap_confirmed"])
            self.assertFalse(row["streams_complete"])

    def test_confirmed_success_never_creates_an_artifact_or_notice(self):
        with TemporaryDirectory() as root:
            _, capture, notice = self.fixture(root)
            capture.cleanup()
            self.assertIsNone(capture.directory)
            self.assertEqual(list(Path(root).iterdir()), [])
            self.assertEqual(notice.getvalue(), "")

    def test_original_business_case_is_preserved_except_documented_observation(self):
        expected = json.loads((ROOT / "evidence/reviews/cli-sigterm-failure-evidence/original-case-ast.json").read_text())
        actual = normalized_method((ROOT / "tests/test_runtime_review.py").read_text())
        self.assertEqual(sha256(actual.encode()).hexdigest(), expected["normalized_method_sha256"])
        tree = ast.parse((ROOT / "tests/test_runtime_review.py").read_text())
        method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                      and node.name == expected["method"])
        popen = next(node for node in ast.walk(method) if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Attribute) and node.func.attr == "Popen")
        self.assertNotIn("text", {item.arg for item in popen.keywords})
        self.assertEqual(next(item.value.value for item in popen.keywords if item.arg == "bufsize"), 0)


if __name__ == "__main__":
    import sqlite3
    from threading import Thread
    with patch.object(subprocess, "Popen", side_effect=AssertionError("pure attempted Popen")), \
            patch.object(sqlite3, "connect", side_effect=AssertionError("pure attempted SQL")), \
            patch.object(os, "kill", side_effect=AssertionError("pure attempted signal")), \
            patch.object(Thread, "start", side_effect=AssertionError("pure attempted thread")):
        unittest.main(verbosity=2)
