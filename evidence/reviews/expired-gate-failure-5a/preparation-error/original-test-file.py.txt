"""Failure evidence is internal, bounded and atomic with retry accounting."""
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from uta.durable_commands import CommandExecutionError, QueueStore
from uta.durable_views import ManagedAccountViews
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ExchangeService, ServiceError
from uta.storage import Database
from uta.writer_fence import WriterFence, WriterFenceError


class FailureDiagnosticTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "financial.sqlite3"
        self.now = datetime(2026, 11, 17, tzinfo=timezone.utc)
        self.database = Database(self.path)
        bootstrap = ExchangeService(self.database, {"USD": 2}, clock=lambda: self.now)
        bootstrap.create_account("alice")
        bootstrap.deposit("alice", "fund", "USD", Decimal("1000"))
        bootstrap.publish_market(MarketSnapshot(1, self.now,
            {"USD": AssetSpec(Decimal(1), Decimal(1))},
            {"X": InstrumentSpec(Decimal(100), Decimal(".1"), Decimal(".05"))}))
        bootstrap.set_kill_switch(False)
        self.queue = QueueStore(self.database, initialize=True, clock=lambda: self.now)
        self.fence = WriterFence(self.database)
        self.fence.enable("diagnostic-test")
        self.token = self.fence.acquire("writer", 30)
        self.writer = ExchangeService(self.database.for_writer(self.token), {"USD": 2}, clock=lambda: self.now)
        self.queue.enqueue_submit("alice", "original-cid", "order", "X", Decimal(1), Decimal(100))

    def diagnostics(self):
        with self.database.read_transaction() as connection:
            return [{**dict(row), "payload": json.loads(row["payload"])} for row in connection.execute(
                "SELECT * FROM uta_events WHERE event_type='COMMAND_EXECUTION_FAILED' ORDER BY sequence")]

    def financial(self):
        with self.database.read_transaction() as connection:
            names = [r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
            return {name: [tuple(r) for r in connection.execute('SELECT * FROM "' + name + '" ORDER BY rowid')]
                    for name in names if name.startswith(("uta_", "ledger_"))
                    and name not in {"uta_command_inbox", "uta_events"}}

    def fail_execution(self):
        original = self.writer._event
        def fail_after_dml(connection, kind, account_id, payload):
            original(connection, kind, account_id, payload)
            if kind == "ORDER_ACCEPTED":
                try:
                    connection.execute("SELECT * FROM missing_diagnostic_test_table")
                except sqlite3.Error as cause:
                    raise ServiceError("storage_unavailable", "sensitive SQL/account/key message", 503) from cause
        with patch.object(self.writer, "_event", side_effect=fail_after_dml):
            with self.assertRaises(CommandExecutionError) as caught:
                self.queue.process_one(self.writer)
        return caught.exception

    def test_legacy_caller_retains_generic_fields_and_explicit_missing_cause(self):
        receipt = self.queue.record_failure(self.writer, "original-cid")
        self.assertEqual((receipt["attempts"], receipt["last_error"]), (1, "technical_execution_failure"))
        events = self.diagnostics()
        self.assertEqual(len(events), 1, "generic last_error alone cannot identify the actual cause")
        self.assertEqual(events[0]["payload"]["diagnostic"]["status"], "cause_not_supplied")

    def test_real_cause_digest_attempt_and_global_visibility_without_financial_effect(self):
        before = self.financial()
        failure = self.fail_execution()
        self.assertEqual((failure.command_id, failure.attempt), ("original-cid", 1))
        receipt = self.queue.record_failure(self.writer, failure.command_id, cause=failure.cause, attempt=failure.attempt)
        self.assertEqual(self.financial(), before)
        self.assertEqual(self.writer.orders("alice"), [])
        event, = self.diagnostics()
        self.assertIsNone(event["account_id"])
        payload = event["payload"]
        self.assertEqual((payload["event_version"], payload["command_id"], payload["command_kind"], payload["attempt"]),
                         (1, "original-cid", "SUBMIT_ORDER", 1))
        with self.database.read_transaction() as connection:
            row = connection.execute("SELECT sequence,payload FROM uta_command_inbox WHERE command_id=?", ("original-cid",)).fetchone()
        self.assertEqual(payload["command_sequence"], row["sequence"])
        self.assertEqual(payload["canonical_payload_sha256"], sha256(row["payload"].encode("utf-8")).hexdigest())
        chain = payload["diagnostic"]["chain"]
        self.assertEqual([r["type"] for r in chain], ["uta.service.ServiceError", "sqlite3.OperationalError"])
        self.assertEqual(chain[0]["public_code"], "storage_unavailable")
        if hasattr(failure.cause.__cause__, "sqlite_errorcode"):
            self.assertEqual((chain[1]["sqlite_errorcode"], chain[1]["sqlite_errorname"]), (1, "SQLITE_ERROR"))
        self.assertTrue(any(frame["function"] == "fail_after_dml" for node in chain for frame in node["frames"]))
        encoded = json.dumps(payload)
        for secret in ("sensitive", "missing_diagnostic_test_table", "SELECT", str(self.path), "locals", "snapshot"):
            self.assertNotIn(secret, encoded)
        self.assertFalse(any(e["event_type"] == "COMMAND_EXECUTION_FAILED" for e in self.writer.account_events("alice")))
        view = ManagedAccountViews(self.database, clock=lambda: self.now).read("alice", "events")
        self.assertFalse(any(e["event_type"] == "COMMAND_EXECUTION_FAILED" for e in view["events"]))
        self.assertEqual(self.queue.record_failure(self.writer, failure.command_id, cause=failure.cause, attempt=1), receipt)
        self.assertEqual(len(self.diagnostics()), 1)
        recovered = QueueStore(Database(self.path))
        self.assertEqual(recovered.status("original-cid")["attempts"], 1)
        self.assertEqual(recovered.process_one(self.writer)["state"], "SUCCEEDED")
        self.assertEqual(len(self.diagnostics()), 1)

    def test_terminal_commit_reply_unknown_is_never_rewritten_or_diagnosed(self):
        original = self.writer._transaction
        @contextmanager
        def lose_reply():
            with original() as connection:
                yield connection
            raise ConnectionError("secret after COMMIT")
        with patch.object(self.writer, "_transaction", lose_reply):
            with self.assertRaises(CommandExecutionError) as caught:
                self.queue.process_one(self.writer)
        terminal = self.queue.status("original-cid")
        self.assertEqual(terminal["state"], "SUCCEEDED")
        self.assertEqual(self.queue.record_failure(self.writer, "original-cid", cause=caught.exception.cause, attempt=1), terminal)
        self.assertEqual(self.diagnostics(), [])
        self.assertIsNone(self.queue.process_one(self.writer))
        self.assertEqual(len(self.writer.orders("alice")), 1)

    def test_failure_record_commit_reply_unknown_recovery_is_idempotent_for_same_attempt(self):
        original = self.writer._transaction
        @contextmanager
        def lose_reply():
            with original() as connection:
                yield connection
            raise ConnectionError("after failure COMMIT")
        with patch.object(self.writer, "_transaction", lose_reply), self.assertRaises(ConnectionError):
            self.queue.record_failure(self.writer, "original-cid", cause=RuntimeError("private"), attempt=1)
        self.assertEqual(self.queue.status("original-cid")["attempts"], 1)
        self.assertEqual(len(self.diagnostics()), 1)
        self.queue.record_failure(self.writer, "original-cid", cause=RuntimeError("private"), attempt=1)
        self.assertEqual(len(self.diagnostics()), 1)
        self.queue.record_failure(self.writer, "original-cid", cause=RuntimeError("private"), attempt=2, max_attempts=2)
        self.assertEqual(self.queue.status("original-cid")["state"], "QUARANTINED")
        self.assertEqual([e["payload"]["attempt"] for e in self.diagnostics()], [1, 2])

    def test_before_commit_failure_rolls_back_event_and_attempt_then_can_recover(self):
        original = self.writer._event
        def interrupt(connection, kind, account_id, payload):
            original(connection, kind, account_id, payload)
            if kind == "COMMAND_EXECUTION_FAILED":
                raise ConnectionError("before COMMIT")
        before = self.financial()
        with patch.object(self.writer, "_event", side_effect=interrupt), self.assertRaises(ConnectionError):
            self.queue.record_failure(self.writer, "original-cid", cause=RuntimeError("private"), attempt=1)
        self.assertEqual(self.queue.status("original-cid")["attempts"], 0)
        self.assertEqual(self.diagnostics(), [])
        self.assertEqual(self.financial(), before)
        self.queue.record_failure(self.writer, "original-cid", cause=RuntimeError("private"), attempt=1)
        self.assertEqual(len(self.diagnostics()), 1)

    def test_real_sqlite_full_rolls_back_attempt_and_diagnostic(self):
        with self.writer.database.transaction() as connection:
            connection.execute("CREATE TABLE diagnostic_full_blob (value BLOB)")
            pages = connection.execute("PRAGMA page_count").fetchone()[0]
        original_connect, original_event = self.writer.database._connect, self.writer._event
        def restricted_connection():
            connection = original_connect()
            connection.execute("PRAGMA max_page_count=" + str(pages))
            return connection
        def fill_after_event(connection, kind, account_id, payload):
            original_event(connection, kind, account_id, payload)
            if kind == "COMMAND_EXECUTION_FAILED":
                connection.execute("INSERT INTO diagnostic_full_blob VALUES (zeroblob(65536))")
        with patch.object(self.writer.database, "_connect", side_effect=restricted_connection), \
                patch.object(self.writer, "_event", side_effect=fill_after_event):
            with self.assertRaises(ServiceError) as caught:
                self.queue.record_failure(self.writer, "original-cid", cause=RuntimeError("private"), attempt=1)
        self.assertEqual(caught.exception.code, "storage_unavailable")
        self.assertEqual(self.queue.status("original-cid")["attempts"], 0)
        self.assertEqual(self.diagnostics(), [])

    def test_expired_lease_cannot_claim_a_diagnostic_or_attempt(self):
        self.fence.release(self.token)
        with self.assertRaises(WriterFenceError):
            self.queue.record_failure(self.writer, "original-cid", cause=RuntimeError("private"), attempt=1)
        self.assertEqual(self.queue.status("original-cid")["attempts"], 0)
        self.assertEqual(self.diagnostics(), [])

    def test_lease_expiring_after_diagnostic_insert_rolls_back_at_commit(self):
        tick = [1_000_000_000]
        database = Database(self.path.with_name("lease.sqlite3"),
                            fence_clock_ns=lambda: tick[0], fence_boot_id="synthetic-boot")
        ExchangeService(database, {"USD": 2}, clock=lambda: self.now)
        queue = QueueStore(database, initialize=True)
        queue.enqueue_halt("expiry", True)
        fence = WriterFence(database)
        fence.enable("diagnostic-expiry")
        token = fence.acquire("expiry-writer", 1)
        writer = ExchangeService(database.for_writer(token), {"USD": 2}, clock=lambda: self.now)
        original = writer._event
        def expire(connection, kind, account_id, payload):
            original(connection, kind, account_id, payload)
            if kind == "COMMAND_EXECUTION_FAILED":
                tick[0] += 1_000_000_000
        with patch.object(writer, "_event", side_effect=expire), self.assertRaises(WriterFenceError) as caught:
            queue.record_failure(writer, "expiry", cause=RuntimeError("private"), attempt=1)
        self.assertEqual(caught.exception.code, "lease_expired")
        self.assertEqual(queue.status("expiry")["attempts"], 0)
        with database.read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_events WHERE event_type='COMMAND_EXECUTION_FAILED'").fetchone()[0], 0)

    def test_deep_cycles_frames_and_hostile_exception_access_are_bounded(self):
        class Hostile(RuntimeError):
            def __str__(self):
                raise AssertionError("must never stringify exception")
            def __getattribute__(self, name):
                raise AssertionError("must never invoke exception attribute hooks")
        current = Hostile("private-secret")
        for _ in range(40):
            parent = Hostile("private-secret")
            BaseException.__dict__["__cause__"].__set__(parent, current)
            current = parent
        self.queue.record_failure(self.writer, "original-cid", cause=current, attempt=1)
        diagnostic = self.diagnostics()[0]["payload"]["diagnostic"]
        self.assertEqual(len(diagnostic["chain"]), 8)
        self.assertTrue(diagnostic["chain_truncated"])
        self.assertNotIn("private-secret", json.dumps(diagnostic))
        cycle = Hostile("private-secret")
        BaseException.__dict__["__cause__"].__set__(cycle, cycle)
        self.queue.record_failure(self.writer, "original-cid", cause=cycle, attempt=2)
        self.assertTrue(self.diagnostics()[1]["payload"]["diagnostic"]["chain_cycle"])

    def test_unknown_public_code_is_not_copied_from_exception_data(self):
        self.queue.record_failure(self.writer, "original-cid", cause=ServiceError("PRIVATE_API_KEY", "private"), attempt=1)
        diagnostic = self.diagnostics()[0]["payload"]["diagnostic"]
        self.assertIsNone(diagnostic["chain"][0]["public_code"])
        self.assertNotIn("PRIVATE_API_KEY", json.dumps(diagnostic))

    def test_deep_traceback_is_bounded_and_attempt_gaps_cannot_invent_failures(self):
        def recurse(depth):
            if depth:
                return recurse(depth - 1)
            raise RuntimeError("private-secret")
        try:
            recurse(40)
        except RuntimeError as cause:
            self.queue.record_failure(self.writer, "original-cid", cause=cause, attempt=1)
        node = self.diagnostics()[0]["payload"]["diagnostic"]["chain"][0]
        self.assertEqual(node["type"], "builtins.RuntimeError")
        self.assertEqual(len(node["frames"]), 8)
        self.assertTrue(node["frames_truncated"])
        self.assertTrue(all(set(frame) == {"module", "function", "lineno"} for frame in node["frames"]))
        with self.assertRaises(ValueError):
            self.queue.record_failure(self.writer, "original-cid", cause=RuntimeError("private"), attempt=3)
        self.assertEqual(self.queue.status("original-cid")["attempts"], 1)
        self.assertEqual(len(self.diagnostics()), 1)

    def test_native_metadata_access_does_not_call_dict_key_or_metaclass_hooks(self):
        class BadDict(dict):
            def get(self, *args):
                raise AssertionError("must not call overridden dict.get")
        class BadKey:
            def __hash__(self):
                return hash("code")
            def __eq__(self, other):
                raise AssertionError("must not compare arbitrary metadata keys")
        class BadMeta(type):
            @property
            def __module__(cls):
                raise AssertionError("must not execute module property")
            def __eq__(cls, other):
                raise AssertionError("must not compare arbitrary exception types")
        class Hostile(RuntimeError, metaclass=BadMeta):
            pass
        cause = Hostile("private")
        data = BadDict()
        data[BadKey()] = "private"
        for i in range(20):
            data[str(i)] = "private"
        cause.__dict__ = data
        self.queue.record_failure(self.writer, "original-cid", cause=cause, attempt=1)
        node = self.diagnostics()[0]["payload"]["diagnostic"]["chain"][0]
        self.assertTrue(node["attributes_truncated"])
        self.assertEqual(node["type"], __name__ + ".Hostile")
        self.assertNotIn("private", json.dumps(node))

    def test_invalid_persisted_kind_does_not_make_event_unbounded(self):
        oversized = "PRIVATE_KIND_" * 4096
        with self.database.inbox_transaction() as connection:
            connection.execute("INSERT INTO uta_command_inbox(command_id,kind,payload,state,enqueued_at) VALUES (?,?,'{}','PENDING',?)",
                               ("invalid-kind", oversized, self.now.isoformat()))
        self.queue.record_failure(self.writer, "invalid-kind", cause=RuntimeError("private"), attempt=1)
        event, = self.diagnostics()
        self.assertIsNone(event["payload"]["command_kind"])
        self.assertEqual(event["payload"]["command_kind_sha256"], sha256(oversized.encode("utf-8")).hexdigest())
        self.assertLess(len(json.dumps(event)), 4096)


if __name__ == "__main__":
    unittest.main()
