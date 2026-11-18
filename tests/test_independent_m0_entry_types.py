"""Narrow new-source metadata contract: own tiny files/fakes, no SQLite/owner."""
from contextlib import contextmanager
import errno
from pathlib import Path
import stat
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

_FORBIDDEN_BEFORE = {name for name in sys.modules if name == "sqlite3" or name == "uta" or name.startswith("uta.")}
import test_independent_m0_resource_race as legacy
_FORBIDDEN_BY_METADATA_IMPORT = {name for name in sys.modules if name == "sqlite3" or name == "uta" or name.startswith("uta.")} - _FORBIDDEN_BEFORE


m = legacy.m


class EntryTypeProvenance(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory(prefix="m0-entry-type-new-source-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.private, self.public = self.root / "private", self.root / "public"
        self.private.mkdir(mode=0o700)
        self.public.mkdir(mode=0o700)
        self.authority = self.private / "B/workload/authority"
        self.authority.mkdir(parents=True)
        self.main = self.authority / "router.sqlite3"
        self.main.write_bytes(b"m")
        self.aux = self.authority / "router.sqlite3-shm"
        self.aux.write_bytes(b"x")
        self.real_lstat = Path.lstat
        self.real_scandir = m.os.scandir

    def measure(self):
        return m.resource_usage(self.private, self.public)["normal"]

    def disappear(self, target, kind="regular", mutate=None):
        calls = []
        def lstat(path, *args, **kwargs):
            if path == target:
                calls.append(path)
                if len(calls) == 1:
                    path.rmdir() if kind == "directory" else path.unlink()
                    if mutate is not None:
                        mutate()
                    raise FileNotFoundError(errno.ENOENT, "synthetic entry vanished", str(path))
            return self.real_lstat(path, *args, **kwargs)
        return calls, lstat

    def hint_scandir(self, hint):
        target = self.aux
        real = self.real_scandir
        @contextmanager
        def scandir(parent):
            with real(parent) as entries:
                def projected():
                    for entry in entries:
                        if Path(entry.path) == target:
                            def is_file(*, follow_symlinks):
                                self.assertIs(follow_symlinks, False)
                                if isinstance(hint, BaseException):
                                    raise hint
                                return hint
                            yield SimpleNamespace(path=entry.path, is_file=is_file)
                        else:
                            yield entry
                yield projected()
        return scandir

    def test_known_regular_aux_all_three_families_and_explicit_roles(self):
        self.aux.unlink()
        self.main.unlink()
        for stem in ("router", "shard-0000"):
            for case in ("B", "P"):
                for suffix in ("wal", "shm"):
                    for role in ("private_root", "private_case"):
                        with self.subTest(stem=stem, case=case, suffix=suffix, role=role), TemporaryDirectory(
                                prefix="m0-new-regular-matrix-") as directory:
                            private, public = Path(directory) / "private", Path(directory) / "public"
                            private.mkdir(); public.mkdir()
                            authority = private / case / "workload/authority"
                            authority.mkdir(parents=True)
                            (authority / (stem + ".sqlite3")).write_bytes(b"m")
                            aux = authority / (stem + ".sqlite3-" + suffix)
                            aux.write_bytes(b"x")
                            calls, lstat = self.disappear(aux)
                            with patch.object(Path, "lstat", lstat):
                                value = (m.resource_usage(private, public)["normal"] if role == "private_root"
                                         else m.tree_bytes(private / case, sqlite_aux_role="private_case"))
                            self.assertEqual(value, 1)
                            self.assertEqual(len(calls), 1)
        probe = self.private / "runtime-probe"
        probe.mkdir()
        (probe / "private.sqlite3").write_bytes(b"m")
        for suffix in ("wal", "shm"):
            with self.subTest(runtime_probe=suffix):
                aux = probe / ("private.sqlite3-" + suffix)
                aux.write_bytes(b"x")
                calls, lstat = self.disappear(aux)
                with patch.object(Path, "lstat", lstat):
                    self.assertEqual(self.measure(), 1)
                self.assertEqual(len(calls), 1)

    def test_enumerated_directory_and_symlink_disappearance_reject(self):
        for kind in ("directory", "symlink"):
            with self.subTest(kind=kind):
                if self.aux.exists() or self.aux.is_symlink(): self.aux.unlink()
                self.aux.mkdir() if kind == "directory" else self.aux.symlink_to(self.main)
                calls, lstat = self.disappear(self.aux, kind)
                with patch.object(Path, "lstat", lstat):
                    with self.assertRaisesRegex(m.GateError, "resource_missing_non_aux"):
                        self.measure()
                self.assertEqual(len(calls), 1)

    def test_present_known_aux_directory_and_symlink_reject(self):
        self.aux.unlink()
        self.aux.mkdir()
        with self.assertRaises(m.GateError): self.measure()
        self.aux.rmdir()
        self.aux.symlink_to(self.main)
        with self.assertRaises(m.GateError): self.measure()

    def test_own_DirEntry_retains_nofollow_regular_evidence_after_removal(self):
        with self.real_scandir(self.authority) as entries:
            entry = next(entry for entry in entries if Path(entry.path) == self.aux)
            self.assertIs(entry.is_file(follow_symlinks=False), True)
            self.aux.unlink()
            self.assertIs(entry.is_file(follow_symlinks=False), True)

    def test_unknown_or_non_boolean_regular_hint_cannot_admit_missing_aux(self):
        for hint in (False, None, 1):
            with self.subTest(hint=hint):
                if not self.aux.exists(): self.aux.write_bytes(b"x")
                calls, lstat = self.disappear(self.aux)
                with patch.object(m.os, "scandir", self.hint_scandir(hint)), patch.object(Path, "lstat", lstat):
                    with self.assertRaisesRegex(m.GateError, "resource_missing_non_aux"):
                        self.measure()
                self.assertEqual(len(calls), 1)

    def test_unknown_type_fallback_missing_cannot_admit_retry(self):
        missing = FileNotFoundError(errno.ENOENT, "synthetic unknown type fallback", str(self.aux))
        with patch.object(m.os, "scandir", self.hint_scandir(missing)):
            with self.assertRaisesRegex(m.GateError, "resource_missing_non_aux"):
                self.measure()

    def test_type_hint_permission_and_EIO_remain_original_errors(self):
        for kind, code in ((PermissionError, errno.EACCES), (OSError, errno.EIO)):
            original = kind(code, "synthetic type metadata error", str(self.aux))
            with self.subTest(errno=code), patch.object(m.os, "scandir", self.hint_scandir(original)):
                with self.assertRaises(kind) as caught:
                    self.measure()
                self.assertIs(caught.exception, original)

    def test_unprovenanced_direct_handler_defaults_to_reject(self):
        original = FileNotFoundError(errno.ENOENT, "synthetic bare exception", str(self.aux))
        self.assertFalse(m._known_missing_sqlite_aux(original, (("private_root", self.private),)))
        original._m0_enumerated_regular_path = str(self.main)
        self.assertFalse(m._known_missing_sqlite_aux(original, (("private_root", self.private),)))

    def test_unknown_filename_and_public_tree_cannot_borrow_regular_hint(self):
        self.aux.unlink()
        targets = [self.authority / "router2.sqlite3-shm",
                   self.public / "B/workload/authority/router.sqlite3-shm"]
        for target in targets:
            with self.subTest(target=target.relative_to(self.root)):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"x")
                calls, lstat = self.disappear(target)
                with patch.object(Path, "lstat", lstat):
                    with self.assertRaisesRegex(m.GateError, "resource_missing_non_aux"):
                        self.measure()
                self.assertEqual(len(calls), 1)

    def test_directory_enumeration_errors_remain_rejections(self):
        for kind, code in ((PermissionError, errno.EACCES), (FileNotFoundError, errno.ENOENT)):
            original = kind(code, "synthetic enumeration error", str(self.authority))
            def scandir(parent):
                if Path(parent) == self.authority: raise original
                return self.real_scandir(parent)
            with self.subTest(errno=code), patch.object(m.os, "scandir", scandir):
                with self.assertRaises((m.GateError, kind)):
                    self.measure()

    def test_flat_scandir_stops_at_entry_cap_without_prefetch(self):
        produced = []
        info = SimpleNamespace(st_mode=stat.S_IFREG | 0o600, st_size=1)
        directory = SimpleNamespace(st_mode=stat.S_IFDIR | 0o700, st_size=0)
        @contextmanager
        def scandir(parent):
            def entries():
                for index in range(10):
                    produced.append(index)
                    yield SimpleNamespace(path=str(Path(parent) / str(index)), is_file=lambda **_: True)
            yield entries()
        with patch.object(m.os, "scandir", scandir), patch.object(Path, "lstat",
                lambda path: directory if path == self.private else info):
            with self.assertRaisesRegex(m.GateError, "tree_entries_cap"):
                m.tree_bytes(self.private, entries_limit=2)
        self.assertEqual(produced, [0, 1, 2])

    def test_retry_policy_constants_and_50ms_success_boundary_unchanged(self):
        self.assertEqual((m.RESOURCE_SCAN_ATTEMPTS, m.RESOURCE_SCAN_RETRY_NS), (3, 50_000_000))
        self.assertEqual(m.SOURCE, "909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0")
        calls, lstat = self.disappear(self.aux)
        with patch.object(Path, "lstat", lstat), patch.object(m.time, "monotonic_ns", side_effect=[0, 1, 50_000_000]):
            self.assertEqual(self.measure(), 1)
        self.assertEqual(len(calls), 1)

    def test_preserved_strict_resource_boundaries_on_new_source(self):
        # Select only these existing contracts on fresh own fixtures. This is
        # not the old 27-case batch or the broader author 186-test suite.
        names = (
            "test_stable_main_disappearance_is_not_retried", "test_aux_missing_with_missing_main_is_fail_closed",
            "test_symlink_main_is_fail_closed", "test_unstable_directory_is_not_an_aux_exception",
            "test_continuous_aux_churn_has_three_attempt_limit", "test_retry_elapsed_budget_does_not_reset",
            "test_successful_retry_over_deadline_is_not_accepted", "test_growth_seen_on_fresh_scan_still_trips_normal_cap",
            "test_previously_seen_stable_path_cannot_vanish_between_attempts",
            "test_prior_partial_size_lower_bound_survives_retry", "test_previously_seen_stable_type_cannot_change_on_retry",
        )
        for name in names:
            with self.subTest(contract=name):
                legacy.ResourceRaceContract(name).debug()
        legacy.RouterAuxContract("test_router_retry_50ms_equality_is_not_admitted").debug()
        legacy.RouterAuxContract("test_router_parent_symlink_is_rejected").debug()

    def test_metadata_module_imports_no_SQL_or_product(self):
        self.assertEqual(_FORBIDDEN_BY_METADATA_IMPORT, set())


if __name__ == "__main__":
    def deny_execution(event, arguments):
        if event in {"sqlite3.connect", "subprocess.Popen", "os.fork", "os.kill", "os.posix_spawn",
                     "socket.connect", "socket.bind", "fcntl.flock", "signal.pidfd_send_signal"}:
            raise AssertionError("metadata-only scope attempted forbidden effect: " + event)
    sys.addaudithook(deny_execution)
    unittest.main()
