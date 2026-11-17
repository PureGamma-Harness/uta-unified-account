"""Small real SQLite/lease interleavings; no synthetic verification receipts."""
from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from threading import Event, Thread, enumerate as threads
from time import sleep
import unittest
from unittest.mock import patch

from uta.credit import CreditService
from uta.ledger import LedgerError
from uta.service import ExchangeService, ServiceError
from uta.matching import Matcher
from uta.startup import StartupError, _OwnedStartup
from uta.storage import Database, DurableLedger
from uta.writer_fence import WriterFence, WriterToken


class _CommitFaultDatabase(Database):
    fail_final = False

    @contextmanager
    def transaction(self):
        with super().transaction() as connection:
            yield connection
            if self.fail_final:
                connection.execute("INSERT INTO startup_fk_child VALUES (123)")


class OwnedStartupTests(unittest.TestCase):
    _lease_seconds = .4  # Test-fixture parameter; production defaults are untouched.

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.database = _CommitFaultDatabase(Path(self.tmp.name) / "authority.sqlite3")
        exchange = ExchangeService(self.database, {"USD": 2})
        CreditService(exchange)
        with self.database.transaction() as conn:
            conn.execute("CREATE TABLE startup_fk_parent (id INTEGER PRIMARY KEY)")
            conn.execute("CREATE TABLE startup_fk_child (id INTEGER REFERENCES startup_fk_parent(id) DEFERRABLE INITIALLY DEFERRED)")
        self.fence = WriterFence(self.database)
        self.fence.enable("startup:test")
        self.token = self.fence.acquire("startup:test-owner", self._lease_seconds)
        self.bound = self.database.for_writer(self.token)
        self.addCleanup(self.release)

    def release(self):
        try:
            self.fence.release(self.token)
        except Exception:
            pass

    def context(self, **kwargs):
        return _OwnedStartup(self.bound, lease_seconds=self._lease_seconds, stop=Event(),
                             parent_pid=os.getppid(), **kwargs)

    def construct(self, initialization):
        exchange = ExchangeService(self.bound, {"USD": 2}, _startup=initialization)
        CreditService(exchange, _startup=initialization)
        return exchange

    def test_full_real_read_verification_spans_multiple_ordinary_leases(self):
        original = DurableLedger.verify
        observed = {}
        def pause(ledger, *, connection=None):
            self.assertTrue(connection.in_transaction)
            self.assertEqual(connection.execute("PRAGMA query_only").fetchone()[0], 1)
            with ledger.database.read_transaction() as conn:
                before = conn.execute("SELECT COUNT(*) FROM writer_fence_events WHERE kind='renewed'").fetchone()[0]
            # Hold the actual SQLite snapshot for >2 configured TTLs. Renewals
            # must really COMMIT on another connection during this interval.
            sleep(.9)
            with ledger.database.read_transaction() as conn:
                after = conn.execute("SELECT COUNT(*) FROM writer_fence_events WHERE kind='renewed'").fetchone()[0]
            observed["renewals"] = after - before
            return original(ledger, connection=connection)
        with self.context() as initialization:
            with patch.object(DurableLedger, "verify", pause):
                self.construct(initialization)
            initialization.finish()
        self.assertGreaterEqual(observed["renewals"], 3)
        state = self.fence.status()
        self.assertEqual(state["generation"], 1)
        self.assertTrue(state["active"])
        with self.database.read_transaction() as conn:
            self.assertFalse(conn.execute("SELECT 1 FROM writer_fence_events WHERE kind IN ('acquired','renewed') AND expires_ns-observed_ns != 400000000").fetchone())
        self.assertFalse(any(t.name == "uta-startup-lease" for t in threads()))

    def test_same_pid_other_thread_token_reuse_is_rejected_then_registry_drains(self):
        errors = []
        def competitor():
            try:
                with self.bound.transaction() as conn:
                    conn.execute("UPDATE uta_schema SET version=version")
            except BaseException as exc:
                errors.append(exc)
        with self.context() as initialization:
            thread = Thread(target=competitor)
            thread.start()
            thread.join(2)
            self.assertFalse(thread.is_alive())
            self.assertEqual(len(errors), 1)
            self.assertEqual(errors[0].code, "initialization_in_progress")
            self.construct(initialization)
            initialization.finish()
        errors.clear()
        thread = Thread(target=competitor)
        thread.start()
        thread.join(2)
        self.assertFalse(errors)

    def test_context_nested_reused_and_wrong_nonce_are_not_success_capabilities(self):
        initialization = self.context()
        with initialization:
            with self.assertRaises(StartupError) as nested:
                with self.context():
                    pass
            self.assertEqual(nested.exception.code, "startup_nested")
            wrong = self.database.for_writer(WriterToken(self.token.authority_id, "different-nonce", self.token.generation))
            with self.assertRaises(StartupError) as conflict:
                with wrong.transaction():
                    pass
            self.assertEqual(conflict.exception.code, "startup_token_conflict")
            self.construct(initialization)
            initialization.finish()
        with self.assertRaises(StartupError):
            with initialization:
                pass
        missing = Path(self.tmp.name) / "not-created.sqlite3"
        with self.assertRaises(ServiceError):
            ExchangeService(Database(missing), {"USD": 2}, _startup=True)
        self.assertFalse(missing.exists())

    def test_real_renew_commit_with_lost_response_poisoned_no_success(self):
        original = WriterFence.renew
        def unknown(fence, token, ttl):
            original(fence, token, ttl)
            raise OSError("synthetic lost renewal response after actual COMMIT")
        initialization = self.context()
        with patch.object(WriterFence, "renew", unknown), self.assertRaises(StartupError):
            with initialization:
                self.construct(initialization)
                initialization.finish()
        self.assertFalse(initialization._finished)
        self.assertFalse(any(t.name == "uta-startup-lease" for t in threads()))
        with self.database.read_transaction() as conn:
            self.assertGreaterEqual(conn.execute("SELECT COUNT(*) FROM writer_fence_events WHERE kind='renewed'").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM ledger_events").fetchone()[0], 0)

    def test_real_deferred_foreign_key_commit_failure_cannot_finish(self):
        initialization = self.context()
        with self.assertRaises(sqlite3.IntegrityError):
            with initialization:
                self.construct(initialization)
                self.bound.fail_final = True
                initialization.finish()
        self.bound.fail_final = False
        self.assertFalse(initialization._finished)
        with self.database.read_transaction() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM startup_fk_child").fetchone()[0], 0)

    def test_balance_corruption_is_still_rejected_by_full_original_replay(self):
        with self.bound.transaction() as conn:
            conn.execute("INSERT INTO ledger_balances VALUES ('customer:corrupt','USD','1')")
        initialization = self.context()
        with self.assertRaises(LedgerError):
            with initialization:
                self.construct(initialization)
                initialization.finish()
        self.assertFalse(initialization._ledger_verified)

    def test_credit_projection_corruption_rejected_after_successful_full_ledger_replay(self):
        with self.bound.transaction() as conn:
            conn.execute("INSERT INTO uta_accounts VALUES ('corrupt-debt',0)")
            conn.execute("INSERT INTO uta_liabilities VALUES ('corrupt-debt','USD','1','0')")
        initialization = self.context()
        with self.assertRaises(ServiceError) as rejected:
            with initialization:
                self.construct(initialization)
                initialization.finish()
        self.assertEqual(rejected.exception.code, "credit_corrupt")
        self.assertTrue(initialization._ledger_verified)
        self.assertIsNone(initialization._credit)
        self.assertFalse(initialization._finished)

    def test_stop_before_start_leaves_no_registry_or_keeper_and_allows_clean_retry(self):
        initialization = self.context()
        initialization.stop.set()
        with self.assertRaises(StartupError):
            with initialization:
                self.construct(initialization)
                initialization.finish()
        self.assertFalse(initialization._finished)
        self.assertFalse(any(t.name == "uta-startup-lease" for t in threads()))
        with self.context() as retry:
            self.construct(retry)
            retry.finish()

    def test_existing_missing_credit_business_guard_is_not_repaired(self):
        with self.bound.transaction() as conn:
            conn.execute("DROP TRIGGER credit_commands_no_delete")
        with self.assertRaises(StartupError) as rejected:
            with self.context() as initialization:
                self.construct(initialization)
                initialization.finish()
        self.assertEqual(rejected.exception.code, "startup_module_corrupt")
        with self.database.read_transaction() as conn:
            self.assertIsNone(conn.execute("SELECT sql FROM sqlite_master WHERE name='credit_commands_no_delete'").fetchone())

    def test_existing_same_name_weak_match_guard_is_not_repaired(self):
        Matcher(ExchangeService(self.bound, {"USD": 2}))
        weak = "CREATE TRIGGER uta_matches_no_delete BEFORE DELETE ON uta_matches BEGIN SELECT 1; END"
        with self.bound.transaction() as conn:
            conn.execute("DROP TRIGGER uta_matches_no_delete")
            conn.execute(weak)
        with self.assertRaises(StartupError) as rejected:
            with self.context() as initialization:
                self.construct(initialization)
                initialization.finish()
        self.assertEqual(rejected.exception.code, "startup_module_corrupt")
        with self.database.read_transaction() as conn:
            self.assertEqual(conn.execute("SELECT sql FROM sqlite_master WHERE name='uta_matches_no_delete'").fetchone()[0], weak)

    def test_additional_guarded_schema_after_full_replay_cannot_extend_frozen_manifest(self):
        with self.assertRaises(StartupError) as rejected:
            with self.context() as initialization:
                self.construct(initialization)
                with self.bound.transaction() as conn:
                    conn.execute("CREATE TABLE unexpected_after_verify (id INTEGER PRIMARY KEY)")
                initialization.finish()
        self.assertEqual(rejected.exception.code, "startup_schema_changed")

    def test_changed_existing_business_schema_after_full_replay_cannot_finish(self):
        with self.assertRaises(StartupError) as rejected:
            with self.context() as initialization:
                self.construct(initialization)
                with self.bound.transaction() as conn:
                    conn.execute("DROP TRIGGER credit_commands_no_delete")
                    conn.execute("CREATE TRIGGER credit_commands_no_delete BEFORE DELETE ON credit_commands BEGIN SELECT 1; END")
                initialization.finish()
        self.assertEqual(rejected.exception.code, "startup_schema_changed")

    def test_real_verified_context_cannot_be_rebound_to_a_different_ledger_object(self):
        initialization = self.context()
        initialization.__enter__()
        try:
            # Setup failures must remain setup failures, with their original
            # keeper cause. They are not evidence that ledger rebinding failed.
            exchange = self.construct(initialization)
            initialization.check()
            initialization._stop_keeper()
            initialization._renew()  # Genuine successful ACK, unchanged .4 TTL.
            initialization.check()
            self.assertIs(exchange.ledger, initialization._ledger)
            substituted = object()
            exchange.ledger = substituted
            self.assertIs(exchange.ledger, substituted)
            with self.assertRaises(StartupError) as rejected:
                initialization.finish()
            self.assertEqual(rejected.exception.code, "startup_not_verified",
                             {"substituted": exchange.ledger is substituted,
                              "keeper_failure": repr(initialization._failure)})
            self.assertFalse(initialization._finished)
        finally:
            # A caught expected rejection is not a successful context exit.
            # Use the same failure cleanup without inventing _finished=True.
            initialization._cleanup()

    def test_private_startup_rejects_historical_migration_before_any_version_change(self):
        with self.bound.transaction() as conn:
            conn.execute("UPDATE uta_schema SET version=1")
        with self.assertRaises(StartupError) as rejected:
            with self.context() as initialization:
                self.construct(initialization)
                initialization.finish()
        self.assertEqual(rejected.exception.code, "startup_offline_upgrade_required")
        with self.database.read_transaction() as conn:
            self.assertEqual(conn.execute("SELECT version FROM uta_schema").fetchone()[0], 1)

    def test_prepared_worker_is_reused_without_any_post_freeze_ddl(self):
        ddl = []
        original = _CommitFaultDatabase._connect
        initialization = self.context()
        def traced(database):
            connection = original(database)
            def observe(sql):
                if initialization._ledger_verified and sql.lstrip().upper().startswith(("CREATE ", "ALTER ", "DROP ", "REINDEX ")):
                    ddl.append(sql)
            connection.set_trace_callback(observe)
            return connection
        with initialization:
            with patch.object(_CommitFaultDatabase, "_connect", traced):
                exchange = self.construct(initialization)
                worker = initialization.take_worker(exchange, account_batch=1, matches_per_symbol=2)
                self.assertIs(worker, initialization._prepared_worker)
                self.assertIsNone(worker._thread)
                self.assertEqual((worker.account_batch, worker.matches_per_symbol), (1, 2))
                initialization.finish()
        self.assertEqual(ddl, [])

    def test_finite_deadline_stops_renewing_and_cannot_finish(self):
        original = DurableLedger.verify
        def slow(ledger, *, connection=None):
            sleep(.15)
            return original(ledger, connection=connection)
        initialization = self.context(timeout=.08)
        with patch.object(DurableLedger, "verify", slow), self.assertRaises(StartupError):
            with initialization:
                self.construct(initialization)
                initialization.finish()
        self.assertFalse(initialization._finished)
        self.assertFalse(any(t.name == "uta-startup-lease" for t in threads()))


if __name__ == "__main__":
    unittest.main()
