"""Damaged SQLite storage classes must not poison failure recording itself."""
from datetime import datetime, timezone
from decimal import Decimal as D
from hashlib import sha256
from http.client import HTTPConnection
import json
from pathlib import Path
import tempfile
from threading import Thread
import unittest

from uta.durable_commands import CommandExecutionError, QueueStore, _stored_digest
from uta.durable_gateway import make_server
from uta.gateway import Credential
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ExchangeService
from uta.storage import Database
from uta.writer_fence import WriterFence


class DiagnosticStorageTypeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.database = Database(Path(temporary.name) / "financial.sqlite3")
        self.now = datetime(2026, 11, 17, tzinfo=timezone.utc)
        bootstrap = ExchangeService(self.database, {"USD": 8}, clock=lambda: self.now)
        bootstrap.create_account("alice")
        bootstrap.deposit("alice", "fund", "USD", D(1000))
        bootstrap.publish_market(MarketSnapshot(1, self.now, {"USD": AssetSpec(D(1), D(1))},
            {"X": InstrumentSpec(D(100), D(".1"), D(".05"))}))
        bootstrap.set_kill_switch(False)
        bootstrap.submit_order("alice", "standing-order", "X", D(1), D(100))
        self.queue = QueueStore(self.database, initialize=True, clock=lambda: self.now)
        fence = WriterFence(self.database)
        fence.enable("blob-diagnostic-research")
        token = fence.acquire("blob-writer", 30)
        self.writer = ExchangeService(self.database.for_writer(token), {"USD": 8}, clock=lambda: self.now)
        self.reader_token = "R" * 43
        self.server = make_server(self.queue, port=0, credentials=(Credential(self.reader_token, "reader", "alice"),))
        self.thread = Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01})
        self.thread.start()
        def close_http():
            self.server.shutdown(); self.server.server_close(); self.thread.join(3)
        self.addCleanup(close_http)

    def http_status(self, expected):
        connection = HTTPConnection(*self.server.server_address, timeout=3)
        try:
            connection.request("GET", "/v2/accounts/alice/commands/blob-poison", headers={"Authorization": "Bearer " + self.reader_token})
            response = connection.getresponse()
            result = json.loads(response.read())
            self.assertEqual(response.status, expected)
            return result
        finally:
            connection.close()

    def rows(self):
        with self.database.read_transaction() as connection:
            names = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
            return {name: [tuple(row) for row in connection.execute('SELECT * FROM "' + name + '" ORDER BY rowid')]
                    for name in names if name.startswith(("uta_", "ledger_")) and name != "uta_command_inbox"}

    def poison_then_cancel(self, kind, payload):
        # This is an internal damaged-row fixture. The customer enqueue API
        # cannot supply a BLOB kind/payload or bypass canonicalization this way.
        with self.database.inbox_transaction() as connection:
            connection.execute("INSERT INTO uta_command_inbox(command_id,account_id,kind,payload,state,enqueued_at) VALUES (?,?,?,?,'PENDING',?)",
                               ("blob-poison", "alice", kind, payload, self.now.isoformat()))
        self.queue.enqueue_cancel("alice", "cancel-after-blob", "standing-order")
        pending_http = self.http_status(202)
        if type(kind) is bytes:
            self.assertEqual((pending_http["kind"], pending_http["kind_status"], pending_http["kind_storage_type"]),
                             (None, "typed_corrupt", "blob"))
        before = self.rows()
        for attempt in (1, 2):
            with self.assertRaises(CommandExecutionError) as caught:
                self.queue.process_one(self.writer)
            self.assertEqual((caught.exception.command_id, caught.exception.attempt), ("blob-poison", attempt))
            receipt = self.queue.record_failure(self.writer, "blob-poison", cause=caught.exception.cause,
                                               attempt=attempt, max_attempts=2)
            self.assertEqual(receipt["state"], "PENDING" if attempt == 1 else "QUARANTINED")
            self.assertEqual(self.queue.record_failure(self.writer, "blob-poison", cause=caught.exception.cause,
                                                      attempt=attempt, max_attempts=2), receipt)
            self.assertEqual(self.queue.status("cancel-after-blob")["state"], "PENDING")
        after = self.rows()
        diagnostics = [row for row in after["uta_events"] if row[1] == "COMMAND_EXECUTION_FAILED"]
        self.assertEqual(len(diagnostics), 2)
        self.assertTrue(all(row[2] is None for row in diagnostics))
        for row in diagnostics:
            event = json.loads(row[3])
            self.assertEqual(event["command_kind_sha256"], sha256(kind if type(kind) is bytes else kind.encode()).hexdigest())
            self.assertEqual(event["command_kind_storage_type"], "blob" if type(kind) is bytes else "text")
            self.assertEqual(event["command_kind_digest_encoding"], "raw_bytes" if type(kind) is bytes else "utf8")
            payload_hash = sha256(payload if type(payload) is bytes else payload.encode()).hexdigest()
            self.assertEqual(event["canonical_payload_sha256"], payload_hash if type(payload) is str else None)
            self.assertEqual(event["stored_payload_sha256"], payload_hash)
            self.assertEqual(event["payload_storage_type"], "blob" if type(payload) is bytes else "text")
            self.assertEqual(event["payload_digest_encoding"], "raw_bytes" if type(payload) is bytes else "utf8")
        after["uta_events"] = [row for row in after["uta_events"] if row[1] != "COMMAND_EXECUTION_FAILED"]
        self.assertEqual(after, before)
        terminal_http = self.http_status(200)
        self.assertEqual((terminal_http["command_id"], terminal_http["state"], terminal_http["attempts"]), ("blob-poison", "QUARANTINED", 2))
        terminal = self.queue.process_one(self.writer)
        self.assertEqual((terminal["command_id"], terminal["state"], terminal["result"]["status"]),
                         ("cancel-after-blob", "SUCCEEDED", "CANCELLED"))
        with self.database.read_transaction() as connection:
            stored = connection.execute("SELECT kind,payload,typeof(kind),typeof(payload) FROM uta_command_inbox WHERE command_id='blob-poison'").fetchone()
        self.assertEqual((stored[0], stored[1]), (kind, payload))
        self.assertEqual((stored[2], stored[3]), ("blob" if type(kind) is bytes else "text", "blob" if type(payload) is bytes else "text"))
        self.assertEqual(self.writer.ledger.verify(), 1)

    def test_blob_kind_can_quarantine_and_unblock_same_account_cancel(self):
        self.poison_then_cancel(b"SUBMIT_ORDER", "{}")

    def test_blob_payload_can_quarantine_without_changing_original_bytes(self):
        self.poison_then_cancel("SUBMIT_ORDER", b"\xff\x00private-binary\xfe")

    def test_both_blob_fields_can_quarantine_without_false_business_rejection(self):
        self.poison_then_cancel(b"\xffKIND", b"{}")

    def test_typed_primitive_digests_and_unsupported_objects_do_not_call_hooks(self):
        self.assertEqual(_stored_digest("abc"), (sha256(b"abc").hexdigest(), "text", "utf8"))
        self.assertEqual(_stored_digest(b"abc"), (sha256(b"abc").hexdigest(), "blob", "raw_bytes"))
        self.assertEqual(_stored_digest(1), (sha256(b"\x00\x00\x00\x00\x00\x00\x00\x01").hexdigest(), "integer", "signed_be64"))
        self.assertEqual(_stored_digest(1.0), (sha256(bytes.fromhex("3ff0000000000000")).hexdigest(), "real", "ieee754_be64"))
        self.assertEqual(_stored_digest(None), (sha256(b"").hexdigest(), "null", "empty"))
        class Hostile:
            def __str__(self):
                raise AssertionError("must not coerce to text")
            def __repr__(self):
                raise AssertionError("must not format object")
            def __getattribute__(self, name):
                raise AssertionError("must not read object hooks")
        self.assertEqual(_stored_digest(Hostile()), (None, "unsupported", None))
        self.assertEqual(_stored_digest(2**1000), (None, "integer", None))


if __name__ == "__main__":
    unittest.main()
