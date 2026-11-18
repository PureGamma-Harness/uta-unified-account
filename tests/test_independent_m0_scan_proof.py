"""New-source proof scope controls only; no old 14/20/27-case batch execution."""
from contextlib import contextmanager
import errno
import importlib.util
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / "tools/independent_m0_controller.py"
spec = importlib.util.spec_from_file_location("m0_scan_proof_contract", SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


@contextmanager
def fixture():
    with TemporaryDirectory(prefix="m0-new-single-use-proof-") as directory:
        root = Path(directory)
        private, public = root / "private", root / "public"
        private.mkdir(mode=0o700); public.mkdir(mode=0o700)
        (private / "stable.json").write_bytes(b"s")
        authority = private / "B/workload/authority"
        authority.mkdir(parents=True)
        main, aux = authority / "router.sqlite3", authority / "router.sqlite3-shm"
        main.write_bytes(b"m"); aux.write_bytes(b"x")
        yield SimpleNamespace(private=private, public=public, authority=authority, main=main, aux=aux)


def disappearance(f, error):
    real, calls = Path.lstat, []
    def lstat(path, *args, **kwargs):
        if path == f.aux and not calls:
            calls.append(True); path.unlink(); raise error
        return real(path, *args, **kwargs)
    return lstat, calls


def hint_scan(f, error):
    real = m.os.scandir
    @contextmanager
    def scandir(parent):
        with real(parent) as entries:
            def projected():
                for entry in entries:
                    if Path(entry.path) == f.aux:
                        def is_file(*, follow_symlinks):
                            if follow_symlinks is not False: raise AssertionError("nofollow required")
                            f.aux.unlink(); raise error
                        yield SimpleNamespace(path=entry.path, is_file=is_file)
                    else:
                        yield entry
            yield projected()
    return scandir


class ScanProofContract(unittest.TestCase):
    def anchors(self, f): return (("private_root", f.private),)
    def error(self, f): return FileNotFoundError(errno.ENOENT, "synthetic deliberate reuse", str(f.aux))
    def measure(self, f): return m.resource_usage(f.private, f.public)["normal"]
    def no_proof(self, error): return not hasattr(error, "_m0_enumerated_regular_proof")
    def assert_reset(self):
        self.assertTrue(m._RESOURCE_SCAN_TOKEN.get() is None, "scan context did not reset")

    def capture_unused(self, f, error, observe):
        lstat, calls = disappearance(f, error)
        with patch.object(Path, "lstat", lstat):
            try: list(m._resource_entries(f.private, observe))
            except FileNotFoundError as caught: self.assertTrue(caught is error)
            else: self.fail("expected synthetic missing entry")
        self.assertEqual(len(calls), 1)
        self.assertFalse(self.no_proof(error), "active regular ENTRY_LSTAT did not issue proof")

    def test_original_one_RED_adaptation_same_exception_across_phase_rejects(self):
        # Same owned-file/hook sequence as 31b4af9's first RED, not its other
        # nineteen groups and not the original 27-case batch.
        with fixture() as f:
            error = self.error(f)
            lstat, calls = disappearance(f, error)
            context = m._DIAGNOSTIC_CONTEXT.set({"private": f.private, "public": f.public, "phase": "CASE_B"})
            try:
                with patch.object(Path, "lstat", lstat): self.assertEqual(self.measure(f), 2)
            finally:
                m._DIAGNOSTIC_CONTEXT.reset(context)
            self.assertEqual(len(calls), 1)
            self.assertTrue(self.no_proof(error), "first valid proof was not consumed")
            f.aux.write_bytes(b"x")
            context = m._DIAGNOSTIC_CONTEXT.set({"private": f.private, "public": f.public, "phase": "ESCROW_B"})
            try:
                with patch.object(m.os, "scandir", hint_scan(f, error)):
                    with self.assertRaisesRegex(m.GateError, "resource_missing_non_aux"): self.measure(f)
            finally:
                m._DIAGNOSTIC_CONTEXT.reset(context)
            self.assertTrue(self.no_proof(error))
            self.assert_reset()

    def test_proof_is_consumed_once_inside_same_scan(self):
        with fixture() as f:
            error, accepted = self.error(f), []
            def scan(observe):
                self.capture_unused(f, error, observe)
                accepted.append(m._known_missing_sqlite_aux(error, self.anchors(f)))
                accepted.append(m._known_missing_sqlite_aux(error, self.anchors(f)))
                return 0
            m._fresh_resource_scan(scan, self.anchors(f))
            self.assertEqual(accepted, [True, False])
            self.assertTrue(self.no_proof(error)); self.assert_reset()

    def test_wrong_path_consumes_proof_and_cannot_restore_it(self):
        with fixture() as f:
            error, accepted = self.error(f), []
            def scan(observe):
                self.capture_unused(f, error, observe)
                original = error.filename
                error.filename = str(f.authority / "router.sqlite3-wal")
                accepted.append(m._known_missing_sqlite_aux(error, self.anchors(f)))
                error.filename = original
                accepted.append(m._known_missing_sqlite_aux(error, self.anchors(f)))
                return 0
            m._fresh_resource_scan(scan, self.anchors(f))
            self.assertEqual(accepted, [False, False]); self.assert_reset()

    def test_unused_proof_from_finished_scan_cannot_cross_scan(self):
        with fixture() as f:
            error = self.error(f)
            def scan(observe):
                self.capture_unused(f, error, observe)
                return 0
            m._fresh_resource_scan(scan, self.anchors(f))
            self.assert_reset()
            def reused(_observe): raise error
            with self.assertRaisesRegex(m.GateError, "resource_missing_non_aux"):
                m._fresh_resource_scan(reused, self.anchors(f))
            self.assertTrue(self.no_proof(error)); self.assert_reset()

    def test_new_unknown_hint_revokes_unused_same_scan_proof(self):
        with fixture() as f:
            error = self.error(f)
            def scan(observe):
                self.capture_unused(f, error, observe)
                f.aux.write_bytes(b"x")
                with patch.object(m.os, "scandir", hint_scan(f, error)):
                    with self.assertRaises(FileNotFoundError): list(m._resource_entries(f.private, observe))
                self.assertFalse(m._known_missing_sqlite_aux(error, self.anchors(f)))
                return 0
            m._fresh_resource_scan(scan, self.anchors(f))
            self.assertTrue(self.no_proof(error)); self.assert_reset()

    def test_new_lstat_error_revokes_unused_same_scan_proof(self):
        with fixture() as f:
            error = self.error(f)
            def scan(observe):
                self.capture_unused(f, error, observe)
                with patch.object(Path, "lstat", side_effect=error):
                    with self.assertRaises(FileNotFoundError): m._resource_lstat(f.main, "PRIVATE_ROOT", "VALIDATE_MAIN")
                self.assertFalse(m._known_missing_sqlite_aux(error, self.anchors(f)))
                return 0
            m._fresh_resource_scan(scan, self.anchors(f))
            self.assertTrue(self.no_proof(error)); self.assert_reset()

    def test_outside_scan_cannot_issue_or_accept_regular_proof(self):
        with fixture() as f:
            error = self.error(f)
            lstat, _calls = disappearance(f, error)
            with patch.object(Path, "lstat", lstat):
                with self.assertRaises(FileNotFoundError): list(m._resource_entries(f.private, lambda *_: 0))
            self.assertTrue(self.no_proof(error))
            self.assertFalse(m._known_missing_sqlite_aux(error, self.anchors(f)))
            error._m0_enumerated_regular_path = str(f.aux)  # Old bare-string field grants nothing.
            self.assertFalse(m._known_missing_sqlite_aux(error, self.anchors(f)))
            self.assert_reset()

    def test_context_resets_on_success_and_all_exception_paths(self):
        for fault in (None, RuntimeError("synthetic"), KeyboardInterrupt()):
            with self.subTest(kind=None if fault is None else type(fault).__name__):
                def scan(_observe):
                    self.assertTrue(m._RESOURCE_SCAN_TOKEN.get() is not None)
                    if fault is not None: raise fault
                    return 0
                if fault is None: m._fresh_resource_scan(scan, ())
                else:
                    with self.assertRaises(type(fault)): m._fresh_resource_scan(scan, ())
                self.assert_reset()

    def test_nested_scans_restore_outer_and_tokens_are_fresh(self):
        before = []
        def outer(_observe):
            outer_token = m._RESOURCE_SCAN_TOKEN.get()
            before.append(outer_token)
            def inner(_inner_observe):
                self.assertTrue(m._RESOURCE_SCAN_TOKEN.get() is not outer_token)
                return 0
            m._fresh_resource_scan(inner, ())
            self.assertTrue(m._RESOURCE_SCAN_TOKEN.get() is outer_token)
            return 0
        m._fresh_resource_scan(outer, ())
        m._fresh_resource_scan(outer, ())
        self.assertTrue(before[0] is not before[1]); self.assert_reset()

    def test_parent_validation_failure_consumes_proof(self):
        with fixture() as f:
            error, accepted = self.error(f), []
            def scan(observe):
                self.capture_unused(f, error, observe)
                f.main.unlink()
                with self.assertRaises(FileNotFoundError): m._known_missing_sqlite_aux(error, self.anchors(f))
                f.main.write_bytes(b"m")
                accepted.append(m._known_missing_sqlite_aux(error, self.anchors(f)))
                return 0
            m._fresh_resource_scan(scan, self.anchors(f))
            self.assertEqual(accepted, [False]); self.assert_reset()


if __name__ == "__main__":
    def no_execution(event, _arguments):
        if event in {"sqlite3.connect", "subprocess.Popen", "os.fork", "os.kill", "os.posix_spawn",
                     "socket.connect", "socket.bind", "fcntl.flock", "signal.pidfd_send_signal"}:
            raise AssertionError("metadata proof scope attempted forbidden execution")
    sys.addaudithook(no_execution)
    unittest.main()
