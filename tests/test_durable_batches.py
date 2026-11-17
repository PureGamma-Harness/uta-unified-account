"""Real SQLite batch effects, original CID semantics and restricted metadata."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from hashlib import sha256
from pathlib import Path
import sqlite3
import tempfile
import json
import os
import subprocess
import sys
import tarfile
import shutil
from time import sleep
import unittest
from unittest.mock import patch

from uta.durable_batches import BatchExecutionError, BatchRecoveryUnknown, BatchStore
from uta.durable_commands import QueueStore
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ExchangeService, ServiceError
from uta.storage import Database, StorageError
from uta.writer_fence import WriterFence, WriterFenceError


def _preseal_bootstrap(callback):
    def decorate(test):
        test._preseal_bootstrap = callback
        return test
    return decorate


def _seed_existing_loan(exchange):
    """Explicit offline fixture funding, before this authority is sealed."""
    from uta.credit import CreditService
    credit = CreditService(exchange)
    credit.fund_pool("pool", "USD", D(30), source_reference="synthetic-owned-batch-pool")
    credit.configure_asset_limit("USD", D(30))
    credit.configure_limit("alice", "USD", D(2))
    credit.borrow("alice", "borrow", "USD", D(2))


class DurableBatchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.database = Database(Path(temporary.name) / "financial.sqlite3")
        self.now = datetime(2026, 11, 17, tzinfo=timezone.utc)
        legacy = ExchangeService(self.database, {"USD": 2}, clock=lambda: self.now)
        for account in ("alice", "bob", "carol"):
            legacy.create_account(account)
            legacy.deposit(account, "fund", "USD", D("20.08"))
        legacy.publish_market(MarketSnapshot(1, self.now, {"USD": AssetSpec(D(1), D(1))},
            {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))}))
        legacy.set_kill_switch(False)
        callback = getattr(getattr(self, self._testMethodName), "_preseal_bootstrap", None)
        if callback is not None:
            callback(legacy)
        self.queue = QueueStore(self.database, initialize=True, clock=lambda: self.now)
        BatchStore.initialize(self.database)
        self.fence = WriterFence(self.database)
        self.fence.enable("batch-test")
        self.fence.enable_batches()
        self.token = self.fence.acquire("worker", 30)
        self.owned = self.database.for_writer(self.token)
        self.exchange = ExchangeService(self.owned, {"USD": 2}, clock=lambda: self.now)
        self.batch = BatchStore(self.owned, self.queue, shard=0, layout_hash="a" * 64)

    def submit(self, account, cid=None, order=None, quantity="1"):
        cid = cid or "submit:" + account
        return self.queue.enqueue_submit(account, cid, order or cid, "BTC-PERP", D(quantity), D(100))

    def three(self):
        for account in ("alice", "bob", "carol"):
            self.submit(account)
        attempt = self.batch.prepare()
        self.assertIsNotNone(attempt)
        return attempt

    def test_actual_shared_commit_and_no_precommit_visibility(self):
        attempt = self.three()
        original = self.exchange._transaction
        before_commit = []
        @contextmanager
        def observed():
            with original() as connection:
                yield connection
                with self.database.read_transaction() as other:
                    before_commit.append((other.execute("SELECT COUNT(*) FROM uta_orders").fetchone()[0],
                        other.execute("SELECT COUNT(*) FROM uta_command_inbox WHERE state='SUCCEEDED'").fetchone()[0],
                        other.execute("SELECT COUNT(*) FROM uta_command_batch_outcomes").fetchone()[0]))
        with patch.object(self.exchange, "_transaction", observed):
            receipts = self.batch.process(self.exchange, attempt, soft_budget_seconds=.1)
        self.assertEqual(before_commit, [(0, 0, 0)])
        self.assertEqual([r["state"] for r in receipts], ["SUCCEEDED"] * 3)
        self.assertEqual(self.batch.unresolved(), [])
        self.assertEqual(self.exchange.ledger.verify(), 3)
        for account in ("alice", "bob", "carol"):
            self.assertEqual(self.exchange.account(account)["open_order_margin"], "10.04")

    def test_full_current_risk_and_mixed_business_rejection(self):
        self.submit("alice", "a1", quantity="1.5")
        self.submit("alice", "a2")
        self.submit("bob", "b1")
        attempt = self.batch.prepare()
        result = {r["command_id"]: r for r in self.batch.process(self.exchange, attempt, soft_budget_seconds=.1)}
        self.assertEqual(result["a1"]["state"], "SUCCEEDED")
        self.assertEqual(result["a2"]["error"]["code"], "insufficient_margin")
        self.assertEqual(result["b1"]["state"], "SUCCEEDED")
        self.assertEqual(self.exchange.account("alice")["open_order_margin"], "15.06")
        self.assertEqual(len(self.exchange.orders("alice")), 1)
        self.assertEqual(self.exchange.ledger.verify(), 3)

    def test_true_rollback_keeps_every_original_pending_and_no_attempt_charge(self):
        attempt = self.three()
        original = self.exchange._admit_order
        def fault(connection, account, *args, **kwargs):
            value = original(connection, account, *args, **kwargs)
            if account == "bob":
                raise RuntimeError("after bob financial effect")
            return value
        with patch.object(self.exchange, "_admit_order", fault), self.assertRaises(BatchExecutionError) as caught:
            self.batch.process(self.exchange, attempt, soft_budget_seconds=.1)
        self.assertEqual(caught.exception.executing_id, "submit:bob")
        self.assertEqual(caught.exception.phase, "execute")
        self.assertEqual(self.batch.unresolved(), [attempt])
        receipts = self.batch.recover(attempt)
        self.assertEqual([r["state"] for r in receipts], ["PENDING"] * 3)
        self.assertEqual([r["attempts"] for r in receipts], [0] * 3)
        self.assertEqual(self.exchange.orders("alice"), [])
        self.assertEqual(self.exchange.orders("bob"), [])
        self.assertEqual(self.exchange.account("alice")["open_order_margin"], "0")
        self.assertEqual(self.batch.unresolved(), [])

    def test_lost_actual_commit_reply_resolves_all_without_repeating_effects(self):
        attempt = self.three()
        original = self.exchange._transaction
        @contextmanager
        def lost_reply():
            with original() as connection:
                yield connection
            raise RuntimeError("actual committed reply lost")
        with patch.object(self.exchange, "_transaction", lost_reply), self.assertRaises(BatchExecutionError) as caught:
            self.batch.process(self.exchange, attempt, soft_budget_seconds=.1)
        self.assertEqual(caught.exception.phase, "commit")
        self.assertIsNone(caught.exception.executing_id)
        results = self.batch.recover(attempt)
        self.assertEqual([r["state"] for r in results], ["SUCCEEDED"] * 3)
        self.assertEqual([r["attempts"] for r in results], [0] * 3)
        self.assertEqual(sum(len(self.exchange.orders(a)) for a in ("alice", "bob", "carol")), 3)
        self.assertEqual(self.exchange.ledger.verify(), 3)

    def test_read_failure_cannot_resolve_or_dispatch_next_manifest(self):
        attempt = self.three()
        original = self.batch._member
        def fault(row):
            if row["command_id"] == "submit:bob":
                raise sqlite3.OperationalError("database is locked")
            return original(row)
        with patch.object(self.batch, "_member", fault), self.assertRaises(BatchRecoveryUnknown):
            self.batch.recover(attempt)
        self.assertEqual(self.batch.unresolved(), [attempt])
        with self.assertRaises(BatchRecoveryUnknown):
            self.batch.prepare()
        self.assertEqual([self.queue.status("submit:" + a)["attempts"] for a in ("alice", "bob", "carol")], [0] * 3)

    def test_metadata_role_cannot_touch_finance_terminal_lease_or_schema(self):
        statements = (
            "UPDATE uta_accounts SET version=version+1 WHERE account_id='alice'",
            "UPDATE uta_command_inbox SET state='SUCCEEDED'",
            "INSERT INTO ledger_events VALUES(999,'bad','bad','bad','bad',0)",
            "UPDATE writer_fence_lease SET expires_ns=expires_ns+1",
            "CREATE TABLE uta_command_batch_forbidden(x)",
            "DELETE FROM uta_command_batch_manifests",
        )
        for sql in statements:
            with self.subTest(sql=sql), self.assertRaises(WriterFenceError):
                with self.owned._batch_metadata_transaction() as connection:
                    connection.execute(sql)
        self.assertEqual(self.exchange.ledger.verify(), 3)
        self.assertEqual(self.exchange.account("alice")["version"], 1)

    def test_manifest_cannot_be_replaced_updated_deleted_or_used_as_terminal_ack(self):
        attempt = self.three()
        for sql in ("UPDATE uta_command_batch_manifests SET content='{}' WHERE attempt_id=?",
                    "DELETE FROM uta_command_batch_manifests WHERE attempt_id=?",
                    "INSERT OR REPLACE INTO uta_command_batch_manifests SELECT * FROM uta_command_batch_manifests WHERE attempt_id=?"):
            with self.subTest(sql=sql), self.assertRaises(sqlite3.IntegrityError):
                with self.owned.transaction() as connection:
                    connection.execute(sql, (attempt,))
        self.assertEqual(self.queue.status("submit:alice")["state"], "PENDING")
        self.assertEqual(self.exchange.orders("alice"), [])

    def test_control_and_backoff_prevent_financial_head_bypass(self):
        self.three()
        self.batch.recover(self.batch.unresolved()[0])
        self.queue.enqueue_halt("halt", True)
        self.assertIsNone(self.batch.prepare())
        self.assertEqual(self.queue.process_one(self.exchange)["command_id"], "halt")
        with self.owned.transaction() as connection:
            connection.execute("UPDATE uta_command_inbox SET next_attempt_at='2099-01-01T00:00:00.000000+00:00' WHERE command_id='submit:alice'")
        self.submit("alice", "a2")
        self.assertIsNone(self.batch.prepare())  # Bob+Carol only; Alice successor cannot pass.

    def test_one_and_two_commands_do_not_create_manifest(self):
        self.submit("alice")
        self.assertIsNone(self.batch.prepare())
        self.submit("bob")
        self.assertIsNone(self.batch.prepare())
        with self.database.read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_command_batch_manifests").fetchone()[0], 0)

    def test_expired_metadata_owner_does_not_prepare_manifest(self):
        attempt = self.three()
        self.batch.recover(attempt)
        self.fence.release(self.token)
        with self.assertRaises(BatchExecutionError) as caught:
            self.batch.prepare()
        self.assertIsInstance(caught.exception.cause, WriterFenceError)

    def test_missing_capability_is_not_silently_installed(self):
        self.fence.release(self.token)
        with self.assertRaises(WriterFenceError):
            with self.database._fence_transaction() as connection:
                connection.execute("DROP TABLE writer_fence_batch_capability")
        self.assertEqual(self.fence.status()["batch_format"], 1)

    def test_actual_archived_4608_and_ad3_processes_cannot_become_writers(self):
        fixture = Path(__file__).parent / "fixtures"
        for prefix in ("legacy_4608ffe", "legacy_ad3f5b8"):
            with self.subTest(prefix=prefix), tempfile.TemporaryDirectory() as temp:
                archive = fixture / (prefix + "_uta.tar.gz")
                provenance = json.loads((fixture / (prefix + "_provenance.json")).read_text())
                self.assertEqual(sha256(archive.read_bytes()).hexdigest(), provenance["archive_sha256"])
                root = Path(temp)
                with tarfile.open(archive) as source:
                    for member in source.getmembers():
                        parts = Path(member.name).parts
                        self.assertFalse(Path(member.name).is_absolute())
                        self.assertNotIn("..", parts)
                        self.assertTrue(member.isfile() or member.isdir())
                        target = root.joinpath(*parts)
                        if member.isdir():
                            target.mkdir(parents=True, exist_ok=True)
                        else:
                            target.parent.mkdir(parents=True, exist_ok=True)
                            with source.extractfile(member) as original, target.open("wb") as output:
                                shutil.copyfileobj(original, output)
                script = r'''
import json,os,sys
from hashlib import sha256
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import uta.storage
from uta.storage import Database
from uta.service import ExchangeService
results=[]
operations=[("financial",lambda:ExchangeService(Database(sys.argv[2]),{"USD":2}))]
if sys.argv[3]=="legacy_4608ffe":
 from uta.writer_fence import WriterFence
 operations.extend([("status",lambda:WriterFence(Database(sys.argv[2])).status()),("acquire",lambda:WriterFence(Database(sys.argv[2])).acquire("old-try",30))])
for name, operation in operations:
 try: operation()
 except BaseException as error: results.append({"operation":name,"blocked":True,"type":type(error).__name__,"code":getattr(error,"code",None)})
 else: results.append({"operation":name,"blocked":False})
print(json.dumps({"pid":os.getpid(),"storage_sha256":sha256(Path(uta.storage.__file__).read_bytes()).hexdigest(),"results":results}))
'''
                child = subprocess.run([sys.executable, "-I", "-c", script, str(root), self.database.path, prefix],
                                       capture_output=True, text=True, timeout=10)
                self.assertEqual(child.returncode, 0, child.stderr)
                result = json.loads(child.stdout)
                self.assertNotEqual(result["pid"], os.getpid())
                self.assertEqual(result["storage_sha256"], sha256((root / "uta/storage.py").read_bytes()).hexdigest())
                self.assertTrue(all(row["blocked"] for row in result["results"]), result)
                if prefix == "legacy_4608ffe":
                    self.assertEqual([row["code"] for row in result["results"]], ["fence_guard_corrupt"] * 3)
        self.assertEqual(self.exchange.ledger.verify(), 3)
        self.assertEqual(self.exchange.orders("alice"), [])

    def test_existing_invalid_outcome_is_not_a_recovery_shortcut(self):
        attempt = self.three()
        with self.owned._batch_metadata_transaction() as connection:
            connection.execute("INSERT INTO uta_command_batch_outcomes VALUES(?,?,?,?)",
                               (attempt, "RECOVERED", "{}", self.now.isoformat()))
        with self.assertRaises(BatchRecoveryUnknown):
            self.batch.recover(attempt)
        with self.assertRaises(BatchExecutionError) as caught:
            self.batch.process(self.exchange, attempt)
        self.assertIsInstance(caught.exception.cause, BatchRecoveryUnknown)
        self.assertEqual(self.exchange.orders("alice"), [])

    def test_new_generation_resolves_old_manifest_before_original_ids_execute(self):
        attempt = self.three()
        self.fence.release(self.token)
        token = self.fence.acquire("replacement", 30)
        database = self.database.for_writer(token)
        replacement = ExchangeService(database, {"USD": 2}, clock=lambda: self.now)
        batches = BatchStore(database, self.queue, shard=0, layout_hash="a" * 64)
        with self.assertRaises(BatchExecutionError):
            batches.process(replacement, attempt)
        self.assertEqual(batches.unresolved(), [attempt])
        self.assertEqual([r["state"] for r in batches.recover(attempt)], ["PENDING"] * 3)
        new_attempt = batches.prepare()
        self.assertNotEqual(new_attempt, attempt)
        self.assertEqual([r["state"] for r in batches.process(replacement, new_attempt, soft_budget_seconds=.1)], ["SUCCEEDED"] * 3)
        self.assertEqual(replacement.ledger.verify(), 3)

    def test_same_order_replay_in_one_batch_keeps_one_reservation_and_event(self):
        self.submit("alice", "a1", "same")
        self.submit("alice", "a2", "same")
        self.submit("bob", "b1")
        result = self.batch.process(self.exchange, self.batch.prepare(), soft_budget_seconds=.1)
        self.assertEqual([r["state"] for r in result], ["SUCCEEDED"] * 3)
        self.assertEqual(len(self.exchange.orders("alice")), 1)
        self.assertEqual(self.exchange.account("alice")["open_order_margin"], "10.04")
        self.assertEqual(sum(e["event_type"] == "ORDER_ACCEPTED" and e["account_id"] == "alice" for e in self.exchange.events(limit=100)), 1)

    def test_failure_evidence_is_bounded_idempotent_and_charges_no_neighbor(self):
        attempt = self.three()
        with patch.object(self.exchange, "_admit_order", side_effect=RuntimeError("private-message-with-nonce-and-key")):
            with self.assertRaises(BatchExecutionError) as caught:
                self.batch.process(self.exchange, attempt)
        self.batch.recover(attempt)
        payload = self.batch.record_failure(self.exchange, caught.exception)
        self.assertEqual(self.batch.record_failure(self.exchange, caught.exception), payload)
        events = [event for event in self.exchange.events(limit=100) if event["event_type"] == "COMMAND_BATCH_EXECUTION_FAILED"]
        self.assertEqual(len(events), 1)
        self.assertNotIn("private-message", json.dumps(payload))
        self.assertEqual(payload["command_ids"], ["submit:alice", "submit:bob", "submit:carol"])
        self.assertEqual([self.queue.status(cid)["attempts"] for cid in payload["command_ids"]], [0, 0, 0])
        self.assertEqual(self.exchange.orders("alice"), [])

    def test_unknown_metadata_commit_preserves_original_attempt_query(self):
        for account in ("alice", "bob", "carol"):
            self.submit(account)
        original = self.owned._batch_metadata_transaction
        @contextmanager
        def lost():
            with original() as connection:
                yield connection
            raise RuntimeError("metadata COMMIT reply lost")
        with patch.object(self.owned, "_batch_metadata_transaction", lost), self.assertRaises(BatchExecutionError) as caught:
            self.batch.prepare()
        error = caught.exception
        self.assertEqual(error.phase, "prepare")
        self.assertEqual(self.batch.unresolved(), [error.attempt_id])
        self.assertEqual([r["state"] for r in self.batch.resolve_preparation(error.attempt_id)], ["PENDING"] * 3)
        self.assertEqual(self.exchange.orders("alice"), [])

    def test_normal_extra_index_and_reserved_view_are_not_official_batch_format(self):
        for sql in ("CREATE INDEX another_batch_index ON uta_command_batch_manifests(created_at)",
                    "CREATE VIEW uta_command_batch_extra AS SELECT attempt_id FROM uta_command_batch_manifests"):
            with self.subTest(sql=sql):
                with self.owned.transaction() as connection:
                    connection.execute(sql)
                with self.database.read_transaction() as connection:
                    with self.assertRaises(StorageError):
                        BatchStore._verify_schema(connection)
                with self.owned.transaction() as connection:
                    connection.execute("DROP " + ("INDEX another_batch_index" if "INDEX" in sql else "VIEW uta_command_batch_extra"))
                with self.database.read_transaction() as connection:
                    BatchStore._verify_schema(connection)

    def test_real_batch_failure_is_separate_from_preparation_execution_record_counts(self):
        from benchmarks.run_managed_benchmark import batch_dispatch_diagnostics
        attempt = self.three()
        with patch.object(self.exchange, "_admit_order", side_effect=RuntimeError("fault")):
            with self.assertRaises(BatchExecutionError) as caught:
                self.batch.process(self.exchange, attempt)
        self.batch.recover(attempt)
        self.batch.record_failure(self.exchange, caught.exception)
        with self.database.read_transaction() as connection:
            counts = batch_dispatch_diagnostics(connection)
        self.assertEqual((counts["prepared_batches"], counts["selected_commands"], counts["executed_commands"]), (1, 3, 0))
        self.assertEqual((counts["failure_events"], counts["recovered_batches"], counts["unresolved_batches"]), (1, 1, 0))
        self.assertTrue(counts["record_counts_are_not_commit_counts"])

    @_preseal_bootstrap(_seed_existing_loan)
    def test_cancel_and_same_currency_repay_commit_under_halt_and_stale_quote(self):
        from uta.credit import CreditService
        credit = CreditService(self.exchange)
        self.exchange.submit_order("alice", "resting", "BTC-PERP", D(1), D(100))
        self.exchange.set_kill_switch(True)
        self.now += timedelta(days=1)
        self.queue.enqueue_cancel("alice", "cancel", "resting")
        self.queue.enqueue_repay("alice", "repay", "USD", D(".5"))
        self.submit("bob", "new-risk")
        attempt = self.batch.prepare()
        result = {r["command_id"]: r for r in self.batch.process(self.exchange, attempt, credit=credit, soft_budget_seconds=.1)}
        self.assertEqual(result["cancel"]["state"], "SUCCEEDED")
        self.assertEqual(result["repay"]["state"], "SUCCEEDED")
        self.assertEqual(result["new-risk"]["error"]["code"], "market_unavailable")
        self.assertEqual(self.exchange.account("alice")["open_order_margin"], "0")
        self.assertEqual(self.exchange.ledger.balance("customer:alice", "USD"), D("21.58"))
        with self.database.read_transaction() as connection:
            self.assertEqual(tuple(connection.execute("SELECT principal,interest FROM uta_liabilities WHERE account_id='alice' AND asset='USD'").fetchone()), ("1.5", "0"))
        self.batch.process(self.exchange, attempt, credit=credit, soft_budget_seconds=.1)
        self.assertEqual(self.exchange.ledger.balance("customer:alice", "USD"), D("21.58"))
        self.assertEqual(self.exchange.ledger.verify(), 6)

    def test_reduce_only_limits_include_the_earlier_staged_order(self):
        from uta.matching import Matcher
        self.exchange.submit_order("alice", "open-long", "BTC-PERP", D("1.5"), D(100))
        self.exchange.submit_order("carol", "open-short", "BTC-PERP", D("-1.5"), D(100))
        match = Matcher(self.exchange).match_once("BTC-PERP")
        self.assertIsNotNone(match)
        self.queue.enqueue_submit("alice", "reduce1", "reduce1", "BTC-PERP", D(-1), D(100), reduce_only=True)
        self.queue.enqueue_submit("alice", "reduce2", "reduce2", "BTC-PERP", D(-1), D(100), reduce_only=True)
        self.submit("bob", "normal")
        result = {r["command_id"]: r for r in self.batch.process(self.exchange, self.batch.prepare(), soft_budget_seconds=.1)}
        self.assertEqual(result["reduce1"]["state"], "SUCCEEDED")
        self.assertEqual(result["reduce2"]["error"]["code"], "reduce_only_violation")
        self.assertEqual(result["normal"]["state"], "SUCCEEDED")
        with self.database.read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT quantity FROM uta_positions WHERE account_id='alice'").fetchone()[0], "1.5")
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_orders WHERE account_id='alice' AND status='OPEN' AND reduce_only=1").fetchone()[0], 1)

    def test_conflicting_order_id_in_same_batch_has_no_second_effect(self):
        self.submit("alice", "first", "same", quantity="1")
        self.submit("alice", "conflict", "same", quantity="2")
        self.submit("bob", "third")
        result = {r["command_id"]: r for r in self.batch.process(self.exchange, self.batch.prepare(), soft_budget_seconds=.1)}
        self.assertEqual(result["first"]["state"], "SUCCEEDED")
        self.assertEqual(result["conflict"]["error"]["code"], "idempotency_conflict")
        self.assertEqual(self.exchange.account("alice")["open_order_margin"], "10.04")
        self.assertEqual(len(self.exchange.orders("alice")), 1)

    def test_slow_first_command_seals_actual_prefix_without_claiming_remaining_effects(self):
        from benchmarks.run_managed_benchmark import batch_dispatch_diagnostics
        attempt = self.three()
        original = self.exchange._admit_order
        def slow(connection, account, *args, **kwargs):
            result = original(connection, account, *args, **kwargs)
            sleep(.01)
            return result
        with patch.object(self.exchange, "_admit_order", slow):
            result = self.batch.process(self.exchange, attempt, soft_budget_seconds=.005)
        self.assertEqual(len(result), 1)
        self.assertEqual(self.queue.status("submit:alice")["state"], "SUCCEEDED")
        self.assertEqual([self.queue.status("submit:" + a)["state"] for a in ("bob", "carol")], ["PENDING", "PENDING"])
        with self.database.read_transaction() as connection:
            counts = batch_dispatch_diagnostics(connection)
        self.assertEqual((counts["prepared_batches"], counts["selected_commands"], counts["executed_commands"], counts["partial_prefix_batches"]), (1, 3, 1, 1))
        self.assertEqual(self.batch.unresolved(), [])
        self.assertEqual([self.queue.process_one(self.exchange)["state"] for _ in range(2)], ["SUCCEEDED"] * 2)
