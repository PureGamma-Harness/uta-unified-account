"""Actual SQLite lock contention must remain an unknown, bounded observation."""
from contextlib import closing, contextmanager
import json
import select
import sqlite3
import subprocess
import sys
from time import monotonic
import unittest
from unittest.mock import patch

import test_process_readiness as fixtures
import test_readiness_sampling as sampling
from uta import durable_process
from uta.writer_fence import WriterFenceError


_LOCK_DATABASES = r"""
from pathlib import Path
import sqlite3, sys
connections = []
try:
    for path in sys.argv[1:]:
        connection = sqlite3.connect(Path(path).as_uri() + '?mode=rw', uri=True,
                                     isolation_level=None, timeout=2)
        connections.append(connection)
        connection.execute('PRAGMA locking_mode=EXCLUSIVE')
        connection.execute('BEGIN EXCLUSIVE')
    print('locked', flush=True)
    sys.stdin.buffer.read(1)
finally:
    for connection in connections:
        connection.rollback()
        connection.close()
"""


class DiagnosticContentionTests(unittest.TestCase):
    def fixture(self):
        fixture = fixtures.ProcessReadinessTests(
            "test_healthy_real_workers_and_read_only_original_observation")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        return fixture

    @contextmanager
    def locked(self, *paths):
        # A different process owns SQLite's actual WAL exclusive lock. No
        # Database hook manufactures an OperationalError or steals a PID token.
        child = subprocess.Popen([sys.executable, "-c", _LOCK_DATABASES, *map(str, paths)],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
        try:
            self.assertTrue(select.select([child.stdout], [], [], 3)[0], "SQLite lock holder did not become ready")
            self.assertEqual(child.stdout.readline(), b"locked\n")
            yield
        finally:
            if child.poll() is None:
                try:
                    child.stdin.write(b"x")
                    child.stdin.flush()
                except BrokenPipeError:
                    pass  # It may exit between poll() and the release write.
            try:
                _, errors = child.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                child.kill()
                child.communicate(timeout=3)
                self.fail("SQLite lock holder did not exit after release; killed and reaped")
            self.assertEqual(child.returncode, 0, errors.decode())

    def test_real_busy_is_unknown_then_release_recovers_current_readiness(self):
        fixture = self.fixture()
        fixture.activate()
        router, caught = fixture.router, []
        original = durable_process._DiagnosticDatabase.read_transaction
        @contextmanager
        def capture_actual_error(database):
            try:
                with original(database) as connection:
                    yield connection
            except sqlite3.OperationalError as error:
                caught.append({"type": type(error).__name__,
                               "sqlite_errorcode": getattr(error, "sqlite_errorcode", None),
                               "canonical_lock_message": error.args == ("database is locked",)})
                raise
        with router._mutex, self.locked(router._database(1).path):
            with patch.object(durable_process._DiagnosticDatabase, "read_transaction", capture_actual_error):
                started = monotonic()
                report = router.diagnostics(timeout=.2)
                duration = monotonic() - started
        def current_ready():
            value = router.diagnostics()
            return value if value["ready"] else None
        recovered = fixture.eventually(current_ready)
        print("diagnostic-contention-evidence " + json.dumps({
            "python": sys.version.split()[0], "sqlite": sqlite3.sqlite_version,
            "actual_sql_errors": caught, "elapsed_seconds": duration,
            "contended": report, "released": recovered}, sort_keys=True), flush=True)
        self.assertEqual(len(caught), 1)
        self.assertTrue(caught[0]["canonical_lock_message"])
        # The configured read budget remains .2; allow scheduling/return
        # overhead in the external clock assertion. The actual exception and
        # future-deadline classification tests establish the busy disposition.
        self.assertLess(duration, .6)
        self.assertEqual(report["reason"], "diagnostic_timeout")
        self.assertFalse(report["ready"])
        self.assertFalse(report["financial_ready"])
        self.assertTrue(report["workers_alive"])
        self.assertTrue(report["state_observed"])
        row = report["workers"][1]
        self.assertTrue(row["alive"])
        self.assertEqual(row["report"]["state"], "ready")
        self.assertEqual(row["reason"], "diagnostic_timeout")
        self.assertIsNone(row["owner_pid"])
        self.assertIsNone(row["generation"])
        self.assertFalse(any(row[key] for key in (
            "lease_active", "locally_active", "market_ready", "owner_ready", "funding_registry_ready")))
        self.assertEqual(row["observation_error"]["type"], "sqlite_operational_error")
        self.assertEqual(row["observation_error"]["sqlite_errorcode"], caught[0]["sqlite_errorcode"])
        self.assertNotIn(str(fixture.path), json.dumps(report))
        self.assertEqual([row["pid"] for row in report["workers"]],
                         [row["pid"] for row in recovered["workers"]])

    def test_two_actual_busy_shards_share_one_deadline(self):
        fixture = self.fixture()
        fixture.activate()
        router, deadlines = fixture.router, []
        original = durable_process._DiagnosticDatabase.__init__
        def record_deadline(database, source, deadline):
            deadlines.append(deadline)
            original(database, source, deadline)
        with router._mutex, self.locked(*(router._database(shard).path for shard in range(2))):
            with patch.object(durable_process._DiagnosticDatabase, "__init__", record_deadline):
                started = monotonic()
                report = router.diagnostics(timeout=.035)
                duration = monotonic() - started
        self.assertLess(duration, .35)
        self.assertEqual(len(deadlines), 3)
        self.assertEqual(len(set(deadlines)), 1)
        self.assertEqual(report["reason"], "diagnostic_timeout")
        self.assertFalse(report["ready"])
        self.assertTrue(all(not row["market_ready"] and not row["owner_ready"] for row in report["workers"]))

    def test_repeated_actual_busy_samples_exhaust_one_observation_budget(self):
        fixture = self.fixture()
        fixture.activate()
        router, budgets, reports = fixture.router, [], []
        original = router.diagnostics
        def observe(*, timeout):
            budgets.append(timeout)
            result = original(timeout=timeout)
            reports.append(result)
            return result
        with router._mutex, self.locked(router._database(1).path):
            with patch.object(router, "diagnostics", observe):
                started = monotonic()
                with self.assertRaises(AssertionError) as failed:
                    sampling.ReadinessSamplingTests.wait_ready(self, router, timeout=.09)
                duration = monotonic() - started
        self.assertIn("within the observation budget", str(failed.exception))
        self.assertLess(duration, .4)
        self.assertGreaterEqual(len(budgets), 2)
        self.assertTrue(all(later < earlier for earlier, later in zip(budgets, budgets[1:])))
        self.assertTrue(all(report["reason"] == "diagnostic_timeout" and not report["ready"]
                            and not report["financial_ready"] for report in reports))

    def test_real_guard_corruption_is_fatal_even_with_another_busy_shard(self):
        fixture = self.fixture()
        fixture.activate()
        router = fixture.router
        router.close()  # Trusted offline damage; no live writer token is stolen.
        with closing(sqlite3.connect(router._database(1).path)) as connection:
            trigger = connection.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'writer_fence_data_%' ORDER BY name LIMIT 1").fetchone()[0]
            connection.execute('DROP TRIGGER "' + trigger + '"')
            connection.commit()
        with self.locked(router._database(0).path):
            with patch.object(router, "diagnostics", wraps=router.diagnostics) as observe:
                with self.assertRaises(AssertionError) as failed:
                    sampling.ReadinessSamplingTests.wait_ready(self, router, timeout=.2)
        self.assertEqual(observe.call_count, 1)
        self.assertIn('"reason": "fence_guard_corrupt"', str(failed.exception))
        self.assertNotIn(str(fixture.path), str(failed.exception))

    def test_fatal_native_io_error_does_not_enter_readiness_retry(self):
        fixture = self.fixture()
        fixture.activate()
        router, calls = fixture.router, []
        original = durable_process._DiagnosticDatabase._connect
        def fail_shard_zero(database):
            if database.path.endswith("shard-0000.sqlite3"):
                calls.append(database.path)
                error = sqlite3.OperationalError("private path/nonce must never escape")
                # Typed fault injection tests IOERR disposition; it is not
                # evidence of a real disk failure or the original CI cause.
                error.sqlite_errorcode = 10 | (1 << 8)  # SQLITE_IOERR_READ
                raise error
            return original(database)
        with patch.object(durable_process._DiagnosticDatabase, "_connect", fail_shard_zero):
            with patch.object(router, "diagnostics", wraps=router.diagnostics) as observe:
                with self.assertRaises(AssertionError) as failed:
                    sampling.ReadinessSamplingTests.wait_ready(self, router, timeout=.2)
        self.assertEqual(observe.call_count, 1)
        self.assertEqual(len(calls), 1)
        self.assertIn('"reason": "shard_unavailable"', str(failed.exception))
        self.assertIn('"sqlite_errorcode": 266', str(failed.exception))
        self.assertNotIn("private path/nonce", str(failed.exception))


class DiagnosticFailureClassificationTests(unittest.TestCase):
    def classify(self, error, *, expired=False):
        return durable_process._diagnostic_failure(error, monotonic() + (-1 if expired else 1),
                                                   "shard_unavailable")

    def test_actual_sqlite_locked_result_is_classified(self):
        first = sqlite3.connect("file:diagnostic-locked?mode=memory&cache=shared", uri=True,
                                isolation_level=None)
        second = sqlite3.connect("file:diagnostic-locked?mode=memory&cache=shared", uri=True,
                                 isolation_level=None)
        try:
            first.execute("CREATE TABLE locked_test(value)")
            first.execute("BEGIN IMMEDIATE")
            first.execute("INSERT INTO locked_test VALUES (1)")
            with self.assertRaises(sqlite3.OperationalError) as caught:
                second.execute("BEGIN IMMEDIATE")
            reason, detail = self.classify(caught.exception)
            self.assertEqual(reason, "diagnostic_timeout")
            if detail["sqlite_errorcode"] is not None:
                self.assertEqual(detail["sqlite_errorcode"] & 255, 6)
        finally:
            second.close()
            first.close()

    def test_native_codes_take_precedence_over_lock_text(self):
        for native in (5, 6, 5 | (2 << 8), 6 | (1 << 8), 10, 10 | (1 << 8), 11, 1, True, "5", None):
            for expired in (False, True):
                with self.subTest(native=native, expired=expired):
                    error = sqlite3.OperationalError("database is locked")
                    error.sqlite_errorcode = native
                    reason, _ = self.classify(error, expired=expired)
                    expected = "diagnostic_timeout" if type(native) is int and native & 255 in {5, 6} else "shard_unavailable"
                    self.assertEqual(reason, expected)

    def test_codeless_fallback_is_exact_builtin_operational_error_only(self):
        class NotBuiltin(sqlite3.OperationalError):
            pass
        for error in (sqlite3.OperationalError("database is locked"),
                      sqlite3.OperationalError("database table is locked"),
                      sqlite3.OperationalError("database is locked: /private"),
                      sqlite3.OperationalError("disk I/O error"),
                      sqlite3.OperationalError("no such table: /private"),
                      sqlite3.OperationalError(["database is locked"]),
                      sqlite3.OperationalError("database is locked", "extra"),
                      sqlite3.DatabaseError("database is locked"),
                      RuntimeError("database is locked"), NotBuiltin("database is locked")):
            with self.subTest(error_type=type(error).__name__, args=error.args):
                reason, detail = self.classify(error, expired=True)
                expected = (type(error) is sqlite3.OperationalError and error.args in
                            (("database is locked",), ("database table is locked",)))
                self.assertEqual(reason, "diagnostic_timeout" if expected else "shard_unavailable")
                self.assertNotIn("private", json.dumps(detail))

    def test_deadline_only_reclassifies_known_sqlite_interrupt(self):
        for error in (sqlite3.OperationalError("interrupted"),
                      sqlite3.OperationalError("disk I/O error"),
                      OSError("private path"), RuntimeError("private nonce"),
                      WriterFenceError("fence_guard_corrupt", "private guard detail")):
            with self.subTest(error_type=type(error).__name__, args=error.args):
                fatal = "fence_guard_corrupt" if isinstance(error, WriterFenceError) else "shard_unavailable"
                self.assertEqual(self.classify(error)[0], fatal)
                expected = "diagnostic_timeout" if error.args == ("interrupted",) else fatal
                self.assertEqual(self.classify(error, expired=True)[0], expected)


if __name__ == "__main__":
    unittest.main()
