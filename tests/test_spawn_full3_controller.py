"""Pure ownership/report-policy tests; no SQL, workers, signals or QA run."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
import subprocess
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("full3_controller", Path(__file__).resolve().parents[1] / "tools/run_spawn_recovery_full3.py")
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)


class Full3ControllerPureTests(unittest.TestCase):
    def identities(self):
        original = {"pid": 900001, "birth_ticks": 22, "boot_id": "synthetic-boot", "group": 900001, "session": 900001}
        process = SimpleNamespace(pid=original["pid"])
        helpers = SimpleNamespace(PROTECTED=set(), _same_group=lambda pid, group: False)
        return original, process, helpers

    def report(self):
        source = {"uta/test-only.py": "a" * 64}
        report = {"passed": True, "code_commit": control.COMMIT, "tests_run": control.EXPECTED_TESTS,
                  "source_sha256": source, "source_sha256_after": source, "worker_exit_code": 0,
                  "unittest_passed": True}
        report.update({key: 0 for key in ("failures", "errors", "skipped", "expected_failures", "unexpected_successes")})
        report.update({key: True for key in ("source_unchanged", "tracked_source_clean_before", "tracked_source_clean_after")})
        return report, dict(report), {"standard_runner_source_sha256": source}

    def test_exact_identity_allows_only_the_owned_group_signal(self):
        original, process, helpers = self.identities()
        with patch.object(control, "identity", return_value=original), patch.object(control.os, "killpg") as kill:
            control.group_signal(process, original, 12, 9, helpers)
        kill.assert_called_once_with(process.pid, 9)

    def test_changed_birth_rejects_signal(self):
        original, process, helpers = self.identities()
        changed = {**original, "birth_ticks": 23}
        with patch.object(control, "identity", return_value=changed), patch.object(control.os, "killpg") as kill:
            with self.assertRaises(RuntimeError):
                control.group_signal(process, original, 12, 9, helpers)
        kill.assert_not_called()

    def test_new_session_identity_is_required_before_group_signal(self):
        original, process, helpers = self.identities()
        changed = {**original, "session": 900002}
        with patch.object(control, "identity", return_value=changed), patch.object(control.os, "killpg") as kill:
            with self.assertRaises(RuntimeError):
                control.group_signal(process, original, 12, 9, helpers)
        kill.assert_not_called()

    def test_protected_cohost_in_group_rejects_signal(self):
        original, process, helpers = self.identities()
        helpers._same_group = lambda pid, group: pid == 4471
        with patch.object(control, "identity", return_value=original), patch.object(control.os, "killpg") as kill:
            with self.assertRaises(RuntimeError):
                control.group_signal(process, original, 12, 9, helpers)
        kill.assert_not_called()

    def test_full_pinned_report_is_accepted(self):
        report, worker, pin = self.report()
        self.assertTrue(control.validate_report(report, worker, pin, 0))

    def test_missing_or_changed_source_report_is_rejected(self):
        for changed in ({"source_sha256_after": {}}, {"source_unchanged": False}, {"code_commit": "wrong"}):
            report, worker, pin = self.report()
            report.update(changed)
            self.assertFalse(control.validate_report(report, worker, pin, 0))

    def test_worker_or_skip_or_exit_failure_is_rejected(self):
        report, worker, pin = self.report()
        for changed in ({"skipped": 1}, {"errors": 1}, {"tests_run": 0}):
            self.assertFalse(control.validate_report({**report, **changed}, worker, pin, 0))
        self.assertFalse(control.validate_report(report, {**worker, "unittest_passed": False}, pin, 0))
        self.assertFalse(control.validate_report(report, worker, pin, 1))

    def test_bool_counter_or_exit_code_is_not_a_typed_success(self):
        report, worker, pin = self.report()
        self.assertFalse(control.validate_report({**report, "errors": False}, worker, pin, 0))
        self.assertFalse(control.validate_report(report, worker, pin, False))

    def test_cleanup_group_failure_still_reaps_direct_child_and_closes_pidfd(self):
        original, process, helpers = self.identities()
        process.returncode = None
        calls = []
        def wait(timeout):
            calls.append(timeout)
            if len(calls) == 1:
                raise subprocess.TimeoutExpired("synthetic-owned-child", timeout)
            process.returncode = -9
            return -9
        process.wait = wait
        process.kill = unittest.mock.Mock()
        with patch.object(control, "group_signal", side_effect=RuntimeError("modeled group proof failure")), \
                patch.object(control.os, "close") as close:
            result = control.finalize_child(process, original, 203, helpers)
        process.kill.assert_called_once_with()
        close.assert_called_once_with(203)
        self.assertTrue(result["leader_reaped"])
        self.assertEqual(result["cleanup_error_types"], ["RuntimeError", "TimeoutExpired"])

    def test_visible_ack_with_fsync_failure_never_releases_go_and_reaps_new_supervisor(self):
        original, process, _ = self.identities()
        process.args, process.returncode = ["synthetic-controller"], None
        process.wait = unittest.mock.Mock(return_value=-9)
        process.kill = unittest.mock.Mock()
        real_save = control.save
        with TemporaryDirectory() as directory:
            output = Path(directory)
            def fail_ack(path, value):
                if path.name == "supervisor-launch.json":
                    path.write_text("{}")  # Visible file is not a successful durable record.
                    raise OSError("modeled fsync failure")
                return real_save(path, value)
            with patch.object(control, "OUTPUT", output), patch.object(control.os, "pipe", return_value=(201, 202)), \
                    patch.object(control.os, "close"), patch.object(control.os, "write") as go, \
                    patch.object(control.os, "pidfd_open", return_value=203), \
                    patch.object(control, "identity", return_value=original), \
                    patch.object(control.subprocess, "Popen", return_value=process), \
                    patch.object(control.signal, "pidfd_send_signal") as kill, \
                    patch.object(control, "save", side_effect=fail_ack):
                with self.assertRaises(OSError):
                    control.launch_detached({})
            self.assertTrue((output / "supervisor-launch.json").exists())
            self.assertTrue((output / "launch-unknown.json").exists())
        go.assert_not_called()
        kill.assert_called_once_with(203, control.signal.SIGKILL)
        process.wait.assert_called_once_with(timeout=2)

    def test_commands_keep_standard_runner_and_runtime_order(self):
        self.assertEqual([label for label, _, _ in control.RUNTIMES], ["python310", "python312", "python313-sqlite346"])
        self.assertEqual(control.RUNTIME_SECONDS, 900)
        self.assertEqual(control.MATRIX_SECONDS, 2730)
        self.assertEqual(control.CPU, 4)
        for argv, (_, executable, _) in zip(control.commands(), control.RUNTIMES):
            self.assertEqual(argv[:3], [executable, "-B", str(control.SOURCE / "tools/run_validation.py")])
            self.assertEqual(len(argv), 5)


if __name__ == "__main__":
    with patch.object(control.subprocess, "Popen", side_effect=AssertionError("pure test attempted a process")), \
            patch.object(control.os, "kill", side_effect=AssertionError("pure test attempted a signal")):
        unittest.main(verbosity=2)
