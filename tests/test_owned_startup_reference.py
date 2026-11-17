"""Independent small-fixture owned-startup interleavings at immutable d9afd46.

Every context/token/service is real. Pauses wrap and eventually call the original
complete verifier; no private verification flags or attestation objects are made.
"""
from contextlib import contextmanager
from decimal import Decimal as D
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from threading import Event, Thread, current_thread
import time
import unittest
from unittest.mock import patch

from uta.credit import CreditService
from uta.ledger import Posting
from uta.matching import Matcher
from uta.service import ExchangeService
from uta.startup import StartupError, _OwnedStartup
from uta.storage import Database, DurableLedger, StorageError
from uta.supervisor import ExchangeWorker
from uta.writer_fence import WriterFence


SUBJECT = "d9afd4636a044d52bb1786eac3fd06550957ed76"


class OwnedStartupReferenceTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.database = Database(Path(temporary.name) / "authority.sqlite3")
        self.source = ExchangeService(self.database, {"USD": 2})
        self.source.create_account("account")
        self.source.deposit("account", "seed", "USD", D(100))
        CreditService(self.source)
        Matcher(self.source)
        ExchangeWorker(self.source)
        self.fence = WriterFence(self.database)
        self.fence.enable("independent-owned-startup")
        self.stop = Event()
        self.token = None

    def bind(self, ttl=.6):
        self.token = self.fence.acquire("reference-owner", ttl)
        self.bound = self.database.for_writer(self.token)
        return _OwnedStartup(self.bound, lease_seconds=ttl, stop=self.stop,
                             parent_pid=os.getppid(), timeout=3)

    def financial(self):
        with self.database.read_transaction() as connection:
            return {table: [tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY rowid")]
                    for table in ("uta_accounts", "uta_orders", "uta_positions", "uta_liabilities", "uta_events",
                                  "ledger_events", "ledger_postings", "ledger_balances", "credit_commands")}

    def construct(self, scope):
        exchange = ExchangeService(self.bound, {"USD": 2}, _startup=scope)
        credit = CreditService(exchange, _startup=scope)
        exchange.credit = credit
        return exchange

    def test_complete_ro_replay_has_multiple_actual_renewals_and_no_financial_change(self):
        scope = self.bind()
        before = self.financial()
        initial_expiry = self.fence.status()["expires_ns"]
        ledger_verify, credit_verify = DurableLedger.verify, CreditService._verify
        calls = []
        def paused(ledger, *, connection=None):
            self.assertIsNotNone(connection)
            self.assertEqual(connection.execute("PRAGMA query_only").fetchone()[0], 1)
            deadline = time.monotonic() + 1.5
            while time.monotonic() < deadline:
                with self.database.read_transaction() as fresh:
                    renewals = fresh.execute("SELECT COUNT(*) FROM writer_fence_events WHERE kind='renewed'").fetchone()[0]
                if renewals >= 5:
                    break
                Event().wait(.015)
            self.assertGreaterEqual(renewals, 5)
            self.assertGreater(time.clock_gettime_ns(time.CLOCK_BOOTTIME), initial_expiry)
            result = ledger_verify(ledger, connection=connection)
            calls.append(("ledger", result))
            return result
        def credit(owned, connection):
            self.assertEqual(connection.execute("PRAGMA query_only").fetchone()[0], 1)
            result = credit_verify(owned, connection)
            calls.append(("credit", result))
            return result
        with patch.object(DurableLedger, "verify", paused), patch.object(CreditService, "_verify", credit):
            with scope:
                self.construct(scope)
                scope.finish()
        self.assertEqual(calls, [("ledger", 1), ("credit", 0)])
        self.assertEqual(before, self.financial())
        self.assertFalse(scope._keeper.is_alive())  # Observation, never a forged lifecycle flag.
        self.assertTrue(self.fence.status()["active"])

    def test_other_thread_with_actual_current_token_cannot_mutate_during_ro_verification(self):
        scope = self.bind()
        before = self.financial()
        original = DurableLedger.verify
        outcomes = []
        def actor():
            try:
                with self.bound.transaction() as connection:
                    connection.execute("UPDATE uta_accounts SET version=version+1 WHERE account_id='account'")
            except Exception as error:
                outcomes.append(error)
        def inspect(ledger, *, connection=None):
            thread = Thread(target=actor)
            thread.start()
            thread.join(1)
            self.assertFalse(thread.is_alive())
            return original(ledger, connection=connection)
        with patch.object(DurableLedger, "verify", inspect):
            with scope:
                self.construct(scope)
                scope.finish()
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes[0].code, "initialization_in_progress")
        self.assertEqual(before, self.financial())

    def test_old_inflight_writer_is_drained_before_complete_ro_replay(self):
        scope = self.bind(ttl=.8)
        entered, release = Event(), Event()
        failures, observed = [], []
        def old_writer():
            try:
                with self.bound.transaction() as connection:
                    self.source.ledger.post("old-inflight", [Posting("system:old", "USD", D(1)),
                        Posting("system:offset", "USD", D(-1))], connection=connection)
                    entered.set()
                    self.assertTrue(release.wait(1))
            except Exception as error:
                failures.append(error)
        thread = Thread(target=old_writer)
        thread.start()
        self.assertTrue(entered.wait(1))
        original_renew, original_verify = WriterFence.renew, DurableLedger.verify
        def renewal(fence, token, ttl):
            release.set()  # Let the already-open real writer COMMIT; do not fake its result.
            return original_renew(fence, token, ttl)
        def replay(ledger, *, connection=None):
            observed.append(connection.execute("SELECT COUNT(*) FROM ledger_events WHERE event_id='old-inflight'").fetchone()[0])
            return original_verify(ledger, connection=connection)
        try:
            with patch.object(WriterFence, "renew", renewal), patch.object(DurableLedger, "verify", replay):
                with scope:
                    self.construct(scope)
                    scope.finish()
        finally:
            release.set()
            thread.join(1)
        self.assertFalse(failures)
        self.assertEqual(observed, [1])

    def test_final_barrier_rejects_a_new_schema_object_and_preserves_it(self):
        scope = self.bind()
        before = self.financial()
        with self.assertRaises(StartupError) as caught:
            with scope:
                self.construct(scope)
                with self.bound.transaction() as connection:
                    connection.execute("CREATE TABLE independent_unexpected(value INTEGER)")
                scope.finish()
        self.assertEqual(caught.exception.code, "startup_schema_changed")
        self.assertEqual(before, self.financial())
        with self.database.read_transaction() as connection:
            self.assertIsNotNone(connection.execute("SELECT name FROM sqlite_master WHERE name='independent_unexpected'").fetchone())

    def test_missing_matching_guard_is_rejected_without_repair(self):
        scope = self.bind()
        with self.bound.transaction() as connection:
            connection.execute("DROP TRIGGER uta_matches_no_update")
        with self.assertRaises(StartupError) as caught:
            with scope:
                self.construct(scope)
                scope.finish()
        self.assertEqual(caught.exception.code, "startup_module_corrupt")
        with self.database.read_transaction() as connection:
            self.assertIsNone(connection.execute("SELECT name FROM sqlite_master WHERE name='uta_matches_no_update'").fetchone())

    def test_changed_credit_guard_definition_is_rejected_without_repair(self):
        scope = self.bind()
        weakened = "CREATE TRIGGER credit_commands_no_delete BEFORE DELETE ON credit_commands BEGIN SELECT 1; END"
        with self.bound.transaction() as connection:
            connection.execute("DROP TRIGGER credit_commands_no_delete")
            connection.execute(weakened)
        with self.assertRaises(StartupError) as caught:
            with scope:
                self.construct(scope)
                scope.finish()
        self.assertEqual(caught.exception.code, "startup_module_corrupt")
        with self.database.read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT sql FROM sqlite_master WHERE name='credit_commands_no_delete'").fetchone()[0], weakened)

    def test_real_keeper_commit_with_lost_reply_poison_is_not_washed_to_success(self):
        scope = self.bind()
        before, verified, committed = self.financial(), Event(), Event()
        original_renew, original_verify = WriterFence.renew, DurableLedger.verify
        def unknown(fence, token, ttl):
            result = original_renew(fence, token, ttl)
            if current_thread().name == "uta-startup-lease" and verified.is_set():
                committed.set()
                raise StorageError("synthetic lost renewal COMMIT reply")
            return result
        def replay(ledger, *, connection=None):
            result = original_verify(ledger, connection=connection)
            verified.set()
            self.assertTrue(committed.wait(.8))
            return result
        with patch.object(WriterFence, "renew", unknown), patch.object(DurableLedger, "verify", replay):
            with self.assertRaises(StartupError) as caught:
                with scope:
                    self.construct(scope)
                    scope.finish()
        self.assertEqual(caught.exception.code, "startup_keeper_failed")
        self.assertTrue(committed.is_set())
        self.assertEqual(before, self.financial())

    def test_final_writer_commit_with_lost_reply_does_not_finish(self):
        scope = self.bind()
        before = self.financial()
        committed = Event()
        with self.assertRaises(StorageError):
            with scope:
                self.construct(scope)
                transaction = self.bound.transaction
                @contextmanager
                def lost_reply():
                    with transaction() as connection:
                        yield connection
                    committed.set()
                    raise StorageError("synthetic lost final writer COMMIT reply")
                with patch.object(self.bound, "transaction", lost_reply):
                    scope.finish()
        self.assertTrue(committed.is_set())
        self.assertFalse(scope._finished)
        self.assertEqual(before, self.financial())

    def test_stop_during_complete_ro_verification_rejects_before_finish(self):
        scope = self.bind()
        original = DurableLedger.verify
        def stopping(ledger, *, connection=None):
            result = original(ledger, connection=connection)
            self.stop.set()
            return result
        with patch.object(DurableLedger, "verify", stopping):
            with self.assertRaises(StartupError):
                with scope:
                    self.construct(scope)
                    scope.finish()
        self.assertFalse(scope._finished)

    def test_real_expired_renewal_cannot_revive_the_initialization_generation(self):
        scope = self.bind(ttl=.6)
        before, verifying, expired = self.financial(), Event(), Event()
        original_renew, original_verify = WriterFence.renew, DurableLedger.verify
        def delayed(fence, token, ttl):
            if current_thread().name == "uta-startup-lease" and verifying.is_set():
                Event().wait(.75)  # Actual wall time, longer than this real token's TTL.
            try:
                return original_renew(fence, token, ttl)
            except Exception as error:
                if getattr(error, "code", None) == "lease_expired":
                    expired.set()
                raise
        def replay(ledger, *, connection=None):
            result = original_verify(ledger, connection=connection)
            verifying.set()
            self.assertTrue(expired.wait(1.5))
            scope._keeper.join(.2)  # Observe/drain the actual failed keeper; never alter its flags.
            self.assertFalse(scope._keeper.is_alive())
            return result
        with patch.object(WriterFence, "renew", delayed), patch.object(DurableLedger, "verify", replay):
            with self.assertRaises(StartupError) as caught:
                with scope:
                    self.construct(scope)
                    scope.finish()
        self.assertEqual(caught.exception.code, "startup_keeper_failed")
        self.assertTrue(verifying.is_set())
        self.assertTrue(expired.is_set())
        self.assertFalse(self.fence.status()["active"])
        self.assertEqual(before, self.financial())

    def test_replaced_authority_inode_is_rejected_after_real_verification(self):
        scope = self.bind()
        before = self.financial()
        with self.assertRaises(StartupError) as caught:
            with scope:
                self.construct(scope)
                replacement = Path(self.database.path).with_name("replacement.sqlite3")
                # SQLite backup, not raw open/close of a published SQLite inode.
                with self.database.read_transaction() as source:
                    target = sqlite3.connect(replacement)
                    try:
                        source.backup(target)
                    finally:
                        target.close()
                replacement.chmod(0o600)
                os.replace(replacement, self.database.path)
                scope.finish()
        self.assertIn(caught.exception.code, ("startup_identity_changed", "startup_keeper_failed"))
        self.assertEqual(before, self.financial())

    def test_wholly_absent_fixed_modules_are_prepared_without_starting_background(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        database = Database(Path(temporary.name) / "fresh.sqlite3")
        source = ExchangeService(database, {"USD": 2})
        source.create_account("fresh-account")
        source.deposit("fresh-account", "seed", "USD", D(100))
        def finance():
            with database.read_transaction() as connection:
                return {table: [tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY rowid")]
                        for table in ("uta_accounts", "uta_events", "ledger_events", "ledger_postings", "ledger_balances")}
        before = finance()
        fence = WriterFence(database)
        fence.enable("independent-empty-modules")
        token = fence.acquire("fresh-owner", .6)
        bound = database.for_writer(token)
        scope = _OwnedStartup(bound, lease_seconds=.6, stop=Event(), parent_pid=os.getppid(), timeout=3)
        with patch.object(ExchangeWorker, "start", side_effect=AssertionError("background started")), \
                patch.object(ExchangeWorker, "run_once", side_effect=AssertionError("background ran")):
            with scope:
                exchange = ExchangeService(bound, {"USD": 2}, _startup=scope)
                CreditService(exchange, _startup=scope)
                scope.finish()
        self.assertIsNone(scope._prepared_worker._thread)
        self.assertEqual(scope._prepared_worker.last_report["state"], "not_started")
        self.assertEqual(before, finance())

    def test_prepared_worker_transfer_is_the_same_object_and_post_replay_has_no_ddl(self):
        scope = self.bind()
        original_connect, original_verify = Database._connect, DurableLedger.verify
        frozen, later_ddl = Event(), []
        def trace(statement):
            if frozen.is_set() and statement.lstrip().upper().startswith(("CREATE", "ALTER", "DROP", "REINDEX")):
                later_ddl.append(statement)
        def connect(database):
            connection = original_connect(database)
            connection.set_trace_callback(trace)
            return connection
        def replay(ledger, *, connection=None):
            result = original_verify(ledger, connection=connection)
            frozen.set()
            return result
        with patch.object(Database, "_connect", connect), patch.object(DurableLedger, "verify", replay):
            with scope:
                exchange = self.construct(scope)
                worker = scope.take_worker(exchange, account_batch=7, matches_per_symbol=3)
                self.assertIs(worker, scope._prepared_worker)
                self.assertEqual((worker.account_batch, worker.matches_per_symbol), (7, 3))
                self.assertIsNone(worker._thread)
                scope.finish()
        self.assertFalse(later_ddl)


if __name__ == "__main__":
    unittest.main()
