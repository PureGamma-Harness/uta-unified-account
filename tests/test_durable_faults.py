"""Independent managed-writer and durable-command failures; synthetic funds only."""
from __future__ import annotations

from contextlib import closing, contextmanager
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Event, Thread
from time import monotonic, sleep
import unittest
from unittest.mock import patch

from uta.credit import CreditService
from uta.durable_commands import CommandExecutionError, QueueStore
from uta.ledger import Posting
from uta.market import MarketSnapshot
from uta.matching import Matcher
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ExchangeService, ServiceError
from uta.storage import Database, StorageError
from uta.writer_fence import WriterFence, WriterFenceError, WriterToken


NOW = datetime(2026, 11, 16, tzinfo=timezone.utc)
FINANCIAL_TABLES = (
    "uta_accounts", "uta_orders", "uta_positions", "uta_fills", "uta_events",
    "uta_deposits", "uta_liabilities", "ledger_events", "ledger_postings",
    "ledger_balances", "uta_matches", "credit_commands",
)


def chain(error):
    pending, seen = [error], set()
    while pending:
        value = pending.pop()
        if value is None or id(value) in seen:
            continue
        seen.add(id(value))
        yield value
        pending.extend((value.__cause__, value.__context__))


def financial_snapshot(path):
    """Observe committed authority without constructing/migrating a service."""
    with closing(sqlite3.connect(Path(path).as_uri() + "?mode=ro", uri=True)) as connection:
        existing = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        return {name: sorted(connection.execute("SELECT * FROM " + name).fetchall(), key=repr)
                for name in FINANCIAL_TABLES if name in existing}


class DurableFaultFixture(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.path = self.directory / "exchange.sqlite3"
        self.database = Database(self.path)
        self.service = self.open_service(self.database)
        for account in ("alice", "bob"):
            self.service.create_account(account)
            self.service.deposit(account, "seed", "USD", D(1000))
        self.service.publish_market(MarketSnapshot(1, NOW,
            {"USD": AssetSpec(D(1), D(1))},
            {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))}))
        self.service.set_kill_switch(False)
        self.matcher = Matcher(self.service)

    @staticmethod
    def open_service(database):
        return ExchangeService(database, {"USD": 8}, clock=lambda: NOW)

    def managed(self, owner="writer-A", ttl=30, database=None):
        database = database or self.database
        fence = WriterFence(database)
        fence.enable("synthetic-authority")
        token = fence.acquire(owner, ttl)
        return fence, token, self.open_service(database.for_writer(token))

    def fenced(self, function, *args, **kwargs):
        with self.assertRaises(Exception) as caught:
            function(*args, **kwargs)
        self.assertTrue(any(isinstance(error, WriterFenceError) for error in chain(caught.exception)),
                        f"expected a storage fencing cause, got {caught.exception!r}")
        return caught.exception

    def child(self, code, *arguments, timeout=15):
        import uta.service
        root = Path(uta.service.__file__).resolve().parent.parent
        return subprocess.run([sys.executable, "-c", code, str(self.path), NOW.isoformat(),
                               *map(str, arguments)], cwd=root, text=True,
                              capture_output=True, timeout=timeout)

    def wait_file(self, path, process, timeout=8):
        deadline = monotonic() + timeout
        while not path.exists() and process.poll() is None and monotonic() < deadline:
            sleep(.01)
        self.assertTrue(path.exists(), f"child exited or timed out before publishing {path.name}")

    @staticmethod
    def cleanup_child(process):
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=5)


class StorageFencingFaultTests(DurableFaultFixture):
    def test_enabling_managed_mode_fences_existing_service_matcher_ledger_and_plain_database(self):
        self.service.submit_order("alice", "buy", "BTC-PERP", D(1), D(100))
        self.service.submit_order("bob", "sell", "BTC-PERP", D(-1), D(100))
        credit = CreditService(self.service)
        credit.configure_asset_limit("USD", D(100))
        credit.configure_limit("alice", "USD", D(100))
        credit.fund_pool("fund", "USD", D(100), source_reference="synthetic:pool")
        credit.borrow("alice", "borrow", "USD", D(10))
        _, _, current = self.managed()
        before = financial_snapshot(self.path)
        self.fenced(self.service.deposit, "alice", "legacy-deposit", "USD", D(1))
        self.fenced(self.service.submit_order, "alice", "legacy-buy", "BTC-PERP", D(1), D(100))
        self.fenced(self.matcher.match_once, "BTC-PERP")
        self.fenced(self.service.ledger.post, "legacy-post", [
            Posting("customer:alice", "USD", D(1)), Posting("system:custody", "USD", D(-1))])
        self.fenced(credit.repay, "alice", "legacy-repay", "USD", D(1))
        def plain_database_write():
            with Database(self.path).transaction() as connection:
                connection.execute("UPDATE ledger_balances SET units='0'")
        self.fenced(plain_database_write)
        self.assertEqual(financial_snapshot(self.path), before)
        # Ordinary reads stay available; the current fenced writer can settle.
        self.assertEqual(self.service.account("alice")["balances"]["USD"], "1010")
        Matcher(current).match_once("BTC-PERP")
        self.assertEqual(len(Matcher(current).trades()), 1)
        self.assertEqual(current.account("alice")["positions"]["BTC-PERP"]["quantity"], "1")
        self.assertEqual(current.account("bob")["positions"]["BTC-PERP"]["quantity"], "-1")
        current.ledger.verify()

    def test_managed_ledger_rejects_a_raw_unguarded_sqlite_transaction(self):
        self.managed()
        before = financial_snapshot(self.path)
        with closing(sqlite3.connect(self.path, isolation_level=None)) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                self.fenced(self.service.ledger.post, "unguarded-post", [
                    Posting("customer:alice", "USD", D(1)),
                    Posting("system:custody", "USD", D(-1))], connection=connection)
            finally:
                connection.rollback()
        self.assertEqual(financial_snapshot(self.path), before)

    def test_token_bound_writer_cannot_fall_back_to_legacy_after_restoring_pre_enable_database(self):
        backup = self.directory / "pre-enable.sqlite3"
        with closing(sqlite3.connect(self.path)) as source, closing(sqlite3.connect(backup)) as target:
            source.backup(target)
        _, _, current = self.managed()
        shutil.copyfile(backup, self.path)
        before = financial_snapshot(self.path)
        self.fenced(current.deposit, "alice", "after-inconsistent-restore", "USD", D(1))
        self.assertEqual(financial_snapshot(self.path), before)


class DurableCommandFaultTests(DurableFaultFixture):
    def setUp(self):
        super().setUp()
        self.queue_now = NOW
        self.queue = QueueStore(self.database, queue_capacity=4, cancel_reserve=2,
                                market_capacity=2, clock=lambda: self.queue_now, initialize=True)

    def enqueue(self, command="command-one", order="order-one", account="alice"):
        return self.queue.enqueue_submit(account, command, order, "BTC-PERP", D(1), D(100))

    def assert_one_admission(self, current, command="command-one", order="order-one"):
        receipt = self.queue.status(command, account_id="alice")
        self.assertEqual(receipt["state"], "SUCCEEDED")
        self.assertEqual(receipt["result"]["order_id"], order)
        self.assertEqual([row["order_id"] for row in current.orders("alice")], [order])
        self.assertEqual(D(current.account("alice")["open_order_margin"]), D("10.04"))
        self.assertEqual(len(current.ledger.journal()), 2)
        accepted = [row for row in current.events(limit=1000) if row["event_type"] == "ORDER_ACCEPTED"]
        self.assertEqual(len(accepted), 1)
        current.ledger.verify()

    def reacquire(self, owner="recovered", timeout=5):
        fence, deadline = WriterFence(self.database), monotonic() + timeout
        while True:
            try:
                return fence.acquire(owner, 30)
            except WriterFenceError as error:
                if error.code != "lease_busy" or monotonic() > deadline:
                    raise
                sleep(.01)

    def test_enqueue_ack_survives_real_process_exit_and_never_claims_risk_acceptance(self):
        WriterFence(self.database).enable("synthetic-authority")
        before = financial_snapshot(self.path)
        code = r'''
from datetime import datetime
from decimal import Decimal as D
import json, os, sys
from uta.durable_commands import QueueStore
from uta.storage import Database
queue = QueueStore(Database(sys.argv[1]), queue_capacity=4, cancel_reserve=2, market_capacity=2,
                   clock=lambda:datetime.fromisoformat(sys.argv[2]))
receipt = queue.enqueue_submit("alice", "command-one", "order-one", "BTC-PERP", D(1), D(100))
print(json.dumps(receipt), flush=True)
os._exit(61)
'''
        child = self.child(code)
        self.assertEqual(child.returncode, 61, child.stderr)
        receipt = json.loads(child.stdout)
        self.assertEqual((receipt["ack"], receipt["state"], receipt["result"]),
                         ("durably_queued", "PENDING", None))
        self.assertEqual(financial_snapshot(self.path), before)
        self.assertEqual(self.queue.status("command-one")["sequence"], receipt["sequence"])
        token = self.reacquire()
        current = self.open_service(self.database.for_writer(token))
        self.queue.process_one(current)
        self.assert_one_admission(current)

    def test_enqueue_ack_is_not_published_before_actual_metadata_commit(self):
        original = self.database.inbox_transaction
        at_commit, release, returned = Event(), Event(), Event()
        receipts, failures = [], []
        @contextmanager
        def pause_commit():
            with original() as connection:
                yield connection
                at_commit.set()
                if not release.wait(5):
                    raise RuntimeError("test did not release metadata COMMIT")
        def enqueue():
            try:
                receipts.append(self.enqueue())
            except BaseException as error:
                failures.append(error)
            finally:
                returned.set()
        before = financial_snapshot(self.path)
        with patch.object(self.database, "inbox_transaction", side_effect=pause_commit):
            thread = Thread(target=enqueue)
            thread.start()
            try:
                self.assertTrue(at_commit.wait(5))
                self.assertFalse(returned.is_set(), "producer acknowledged an uncommitted queue entry")
                self.assertIsNone(self.queue.status("command-one"))
                self.assertEqual(financial_snapshot(self.path), before)
            finally:
                release.set()
            thread.join(5)
            self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(receipts[0]["ack"], "durably_queued")
        self.assertEqual(self.queue.status("command-one")["state"], "PENDING")

    def test_real_worker_exit_after_dml_before_commit_and_after_commit_retries_original_id_once(self):
        code = r'''
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal as D
import os, sys
from uta.durable_commands import QueueStore
from uta.service import ExchangeService
from uta.storage import Database
from uta.writer_fence import WriterFence
database = Database(sys.argv[1])
token = WriterFence(database).acquire("crashing-worker", .5)
service = ExchangeService(database.for_writer(token), {"USD":8}, clock=lambda:datetime.fromisoformat(sys.argv[2]))
queue = QueueStore(database, queue_capacity=4, cancel_reserve=2, market_capacity=2,
                   clock=lambda:datetime.fromisoformat(sys.argv[2]))
stage = sys.argv[3]
if stage == "dml":
    original = service._admit_order
    def die_after_dml(*args, **kwargs):
        original(*args, **kwargs)
        os._exit(62)
    service._admit_order = die_after_dml
else:
    original = service.database.transaction
    @contextmanager
    def die_at_boundary():
        with original() as connection:
            yield connection
            if stage == "before": os._exit(63)
        os._exit(64)
    service.database.transaction = die_at_boundary
queue.process_one(service)
raise AssertionError("worker did not reach injected crash boundary")
'''
        for stage, expected_exit, expected_state in (("dml", 62, "PENDING"),
                                                     ("before", 63, "PENDING"),
                                                     ("after", 64, "SUCCEEDED")):
            with self.subTest(stage=stage):
                # Each crash stage has its own authority and queue, never a
                # mutated prior stage or restored partial database.
                stage_path = self.directory / (stage + ".sqlite3")
                with closing(sqlite3.connect(self.path)) as source, closing(sqlite3.connect(stage_path)) as target:
                    source.backup(target)
                stage_path.chmod(0o600)
                database = Database(stage_path)
                queue = QueueStore(database, queue_capacity=4, cancel_reserve=2,
                                   market_capacity=2, clock=lambda: NOW)
                receipt = queue.enqueue_submit("alice", "command-one", "order-one", "BTC-PERP", D(1), D(100))
                WriterFence(database).enable("synthetic-authority")
                original_path = self.path
                self.path = stage_path
                try:
                    child = self.child(code, stage)
                finally:
                    self.path = original_path
                self.assertEqual(child.returncode, expected_exit, child.stderr)
                self.assertEqual(queue.status("command-one")["state"], expected_state)
                self.assertEqual(len(financial_snapshot(stage_path)["uta_orders"]), int(stage == "after"))
                fence, deadline = WriterFence(database), monotonic() + 5
                while True:
                    try:
                        token = fence.acquire("restart-worker", 30)
                        break
                    except WriterFenceError as error:
                        if error.code != "lease_busy" or monotonic() > deadline:
                            raise
                        sleep(.01)
                current = self.open_service(database.for_writer(token))
                self.assertEqual(queue.enqueue_submit("alice", "command-one", "order-one", "BTC-PERP", D(1), D(100))["sequence"], receipt["sequence"])
                queue.process_one(current)
                before = financial_snapshot(stage_path)
                self.assertEqual(queue.status("command-one")["state"], "SUCCEEDED")
                self.assertIsNone(queue.process_one(current))
                self.assertEqual(financial_snapshot(stage_path), before)
                self.assertEqual(D(current.account("alice")["open_order_margin"]), D("10.04"))
                self.assertEqual(len(current.ledger.journal()), 2)
                current.ledger.verify()

    def test_lost_commit_response_cannot_be_overwritten_as_retry_or_business_rejection(self):
        self.enqueue()
        _, _, current = self.managed()
        original = current.database.transaction
        armed = [True]
        @contextmanager
        def lose_after_commit():
            with original() as connection:
                yield connection
            if armed[0]:
                armed[0] = False
                raise ConnectionError("synthetic response lost after actual SQLite COMMIT")
        with patch.object(current.database, "transaction", side_effect=lose_after_commit):
            with self.assertRaises(CommandExecutionError):
                self.queue.process_one(current)
        before = financial_snapshot(self.path)
        receipt = self.queue.record_failure(current, "command-one", max_attempts=1)
        self.assertEqual(receipt["state"], "SUCCEEDED")
        self.assertIsNone(self.queue.process_one(current))
        self.assertEqual(financial_snapshot(self.path), before)
        self.assert_one_admission(current)

    def test_real_sqlite_full_after_financial_dml_leaves_pending_then_recovers_once(self):
        with self.database.transaction() as connection:
            connection.execute("CREATE TABLE fault_blob (value BLOB)")
            max_pages = connection.execute("PRAGMA page_count").fetchone()[0]
        self.enqueue()
        _, _, current = self.managed()
        before = financial_snapshot(self.path)
        connect, admit = current.database._connect, current._admit_order
        def full_connection():
            connection = connect()
            connection.execute("PRAGMA max_page_count=" + str(max_pages))
            return connection
        def exhaust_after_dml(connection, *args, **kwargs):
            result = admit(connection, *args, **kwargs)
            connection.execute("INSERT INTO fault_blob VALUES (zeroblob(65536))")
            return result
        with patch.object(current.database, "_connect", side_effect=full_connection), \
                patch.object(current, "_admit_order", side_effect=exhaust_after_dml):
            with self.assertRaises(CommandExecutionError) as caught:
                self.queue.process_one(current)
        self.assertTrue(any(isinstance(error, sqlite3.Error) and (
            getattr(error, "sqlite_errorcode", None) == getattr(sqlite3, "SQLITE_FULL", 13) or
            "database or disk is full" in str(error)) for error in chain(caught.exception)))
        self.assertEqual(self.queue.status("command-one")["state"], "PENDING")
        self.assertEqual(financial_snapshot(self.path), before)
        self.queue.process_one(current)
        self.assert_one_admission(current)

    def test_real_deferred_constraint_commit_failure_rolls_back_financial_and_terminal_receipt(self):
        with self.database.transaction() as connection:
            connection.execute("CREATE TABLE fault_parent (id INTEGER PRIMARY KEY)")
            connection.execute("CREATE TABLE fault_child (id INTEGER REFERENCES fault_parent(id) DEFERRABLE INITIALLY DEFERRED)")
        self.enqueue()
        _, _, current = self.managed()
        before = financial_snapshot(self.path)
        original = current._admit_order
        def violate_at_commit(connection, *args, **kwargs):
            result = original(connection, *args, **kwargs)
            connection.execute("INSERT INTO fault_child VALUES (999)")
            return result
        with patch.object(current, "_admit_order", side_effect=violate_at_commit):
            with self.assertRaises(CommandExecutionError) as caught:
                self.queue.process_one(current)
        self.assertTrue(any(isinstance(error, sqlite3.IntegrityError) for error in chain(caught.exception)))
        self.assertEqual(self.queue.status("command-one")["state"], "PENDING")
        self.assertEqual(financial_snapshot(self.path), before)
        self.queue.process_one(current)
        self.assert_one_admission(current)

    def test_unavailable_database_cannot_ack_more_work_or_lose_existing_ack(self):
        receipt = self.enqueue()
        _, _, current = self.managed()
        before = financial_snapshot(self.path)
        offline = self.path.with_name("offline.sqlite3")
        self.path.rename(offline)
        self.path.mkdir()
        try:
            with self.assertRaises(Exception):
                self.queue.process_one(current)
            with self.assertRaises(Exception):
                self.enqueue("not-acknowledged", "not-accepted")
            self.assertEqual(financial_snapshot(offline), before)
        finally:
            self.path.rmdir()
            offline.rename(self.path)
        self.assertEqual(self.queue.status("command-one")["sequence"], receipt["sequence"])
        self.assertIsNone(self.queue.status("not-acknowledged"))
        self.queue.process_one(current)
        self.assert_one_admission(current)

    def test_poison_is_bounded_other_accounts_progress_and_same_account_cancel_waits_for_quarantine(self):
        self.service.submit_order("alice", "old", "BTC-PERP", D(1), D(100))
        self.enqueue("poison", "poison-order")
        self.queue.enqueue_cancel("alice", "cancel-old", "old")
        self.enqueue("bob-work", "bob-order", "bob")
        _, _, current = self.managed()
        original = current._admit_order
        def poison(connection, account, identifier, *args, **kwargs):
            if identifier == "poison-order":
                raise RuntimeError("synthetic deterministic poison")
            return original(connection, account, identifier, *args, **kwargs)
        with patch.object(current, "_admit_order", side_effect=poison):
            with self.assertRaises(CommandExecutionError):
                self.queue.process_one(current)
            first = self.queue.record_failure(current, "poison", max_attempts=2, backoff_seconds=1)
            self.assertEqual((first["state"], first["attempts"]), ("PENDING", 1))
            self.assertEqual(self.queue.process_one(current)["command_id"], "bob-work")
            self.assertIsNone(self.queue.process_one(current))
            self.assertEqual(current.order("alice", "old")["status"], "OPEN")
            self.queue_now += timedelta(seconds=2)
            with self.assertRaises(CommandExecutionError):
                self.queue.process_one(current)
            terminal = self.queue.record_failure(current, "poison", max_attempts=2)
            self.assertEqual((terminal["state"], terminal["attempts"]), ("QUARANTINED", 2))
            self.assertEqual(self.queue.process_one(current)["command_id"], "cancel-old")
            self.assertIsNone(self.queue.process_one(current))
        self.assertEqual(current.order("alice", "old")["status"], "CANCELLED")
        self.assertEqual([row["order_id"] for row in current.orders("alice")], ["old"])
        self.assertEqual(self.queue.status("poison")["state"], "QUARANTINED")
        self.assertEqual(self.queue.status("cancel-old")["state"], "SUCCEEDED")
        current.ledger.verify()

    def test_unsupported_commands_and_capacity_are_explicit_and_never_fall_back_to_sync(self):
        before = financial_snapshot(self.path)
        with self.assertRaises(ServiceError) as caught:
            self.queue.enqueue("REPAY", "unsupported-repay", {"account_id": "alice", "amount": "1", "asset": "USD"})
        self.assertEqual(caught.exception.code, "unsupported_durable_command")
        self.assertIsNone(self.queue.status("unsupported-repay"))
        for index in range(4):
            self.enqueue(f"normal-{index}", f"order-{index}")
        with self.assertRaises(ServiceError) as caught:
            self.enqueue("overflow", "overflow")
        self.assertEqual(caught.exception.code, "durable_queue_overloaded")
        for index in range(2):
            self.queue.enqueue_cancel("alice", f"cancel-{index}", f"order-{index}")
        with self.assertRaises(ServiceError) as caught:
            self.queue.enqueue_cancel("alice", "cancel-overflow", "order-0")
        self.assertEqual(caught.exception.code, "durable_queue_overloaded")
        self.assertEqual(financial_snapshot(self.path), before)

    def test_producer_metadata_role_cannot_forge_replace_or_update_terminal_receipts(self):
        self.enqueue()
        _, _, current = self.managed()
        self.queue.process_one(current)
        before = self.queue.status("command-one")
        financial = financial_snapshot(self.path)
        statements = (
            "INSERT INTO uta_command_inbox(command_id,account_id,kind,payload,state,result,enqueued_at,completed_at) "
            "VALUES ('forged','alice','SUBMIT_ORDER','{}','SUCCEEDED','{}','2026-11-16','2026-11-16')",
            "UPDATE uta_command_inbox SET state='PENDING',result=NULL WHERE command_id='command-one'",
            "INSERT OR REPLACE INTO uta_command_inbox(sequence,command_id,account_id,kind,payload,state,enqueued_at) "
            "SELECT sequence,command_id,account_id,kind,payload,'PENDING',enqueued_at FROM uta_command_inbox WHERE command_id='command-one'",
            "INSERT OR REPLACE INTO uta_command_config VALUES (1,1,1,0,1)",
        )
        for statement in statements:
            with self.subTest(statement=statement.split()[0:3]):
                def producer_write():
                    with self.database.inbox_transaction() as connection:
                        connection.execute(statement)
                # SQL schema guards may reject INSERT/REPLACE before the
                # role authorizer does. Either is a storage-layer rejection.
                with self.assertRaises((WriterFenceError, sqlite3.IntegrityError)):
                    producer_write()
                self.assertEqual(self.queue.status("command-one"), before)
                self.assertIsNone(self.queue.status("forged"))
                self.assertEqual(financial_snapshot(self.path), financial)

    def test_restart_with_missing_inbox_or_guard_refuses_to_recreate_history(self):
        self.enqueue()
        for missing in ("inbox", "guard"):
            with self.subTest(missing=missing):
                path = self.directory / ("missing-" + missing + ".sqlite3")
                with closing(sqlite3.connect(self.path)) as source, closing(sqlite3.connect(path)) as target:
                    source.backup(target)
                path.chmod(0o600)
                with closing(sqlite3.connect(path)) as connection, connection:
                    if missing == "inbox":
                        name, kind = "uta_command_inbox", "table"
                        connection.execute("DROP TABLE uta_command_inbox")
                    else:
                        name, = connection.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='uta_command_inbox' ORDER BY name LIMIT 1").fetchone()
                        kind = "trigger"
                        connection.execute('DROP TRIGGER "' + name + '"')
                before = financial_snapshot(path)
                with self.assertRaises(StorageError):
                    QueueStore(Database(path), queue_capacity=4, cancel_reserve=2, market_capacity=2,
                               clock=lambda: NOW)
                with closing(sqlite3.connect(path)) as connection:
                    self.assertIsNone(connection.execute("SELECT name FROM sqlite_master WHERE type=? AND name=?", (kind, name)).fetchone())
                self.assertEqual(financial_snapshot(path), before)


class StorageLeaseFaultTests(DurableFaultFixture):
    def test_two_real_processes_cannot_share_live_lease_and_expired_owner_cannot_resume_writes(self):
        WriterFence(self.database).enable("synthetic-authority")
        ready, release, acquired = (self.directory / name for name in ("old-ready", "old-release", "new-token"))
        code = r'''
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal as D
import json, sys, time
from pathlib import Path
from uta.service import ExchangeService
from uta.storage import Database
from uta.writer_fence import WriterFence, WriterFenceError
database = Database(sys.argv[1])
fence = WriterFence(database)
if sys.argv[3] == "old":
    token = fence.acquire("process-old", 2)
    service = ExchangeService(database.for_writer(token), {"USD":8}, clock=lambda:datetime.fromisoformat(sys.argv[2]))
    Path(sys.argv[4]).write_text(json.dumps(asdict(token)))
    deadline = time.monotonic() + 10
    while not Path(sys.argv[5]).exists():
        if time.monotonic() > deadline: raise RuntimeError("old writer was not released")
        time.sleep(.01)
    try:
        service.deposit("alice", "stale-writer-deposit", "USD", D(1))
    except Exception as error:
        values, pending = [], [error]
        while pending:
            value = pending.pop()
            if value is None: continue
            values.append(getattr(value, "code", type(value).__name__))
            pending.append(value.__cause__)
        print(json.dumps({"fenced":values}), flush=True)
    else: raise AssertionError("expired writer mutated funds")
else:
    try:
        fence.acquire("process-new", 10)
    except WriterFenceError as error:
        assert error.code == "lease_busy", error.code
    else: raise AssertionError("second process acquired an unexpired lease")
    deadline = time.monotonic() + 8
    while True:
        try:
            token = fence.acquire("process-new", 10)
            break
        except WriterFenceError as error:
            if error.code != "lease_busy" or time.monotonic() > deadline: raise
            time.sleep(.01)
    Path(sys.argv[4]).write_text(json.dumps(asdict(token)))
    print(json.dumps(asdict(token)), flush=True)
    fence.release(token)
'''
        import uta.service
        root = Path(uta.service.__file__).resolve().parent.parent
        args = [sys.executable, "-c", code, str(self.path), NOW.isoformat()]
        old = subprocess.Popen(args + ["old", str(ready), str(release)], cwd=root,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(self.cleanup_child, old)
        self.wait_file(ready, old)
        new = subprocess.Popen(args + ["new", str(acquired)], cwd=root,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(self.cleanup_child, new)
        try:
            output, errors = new.communicate(timeout=12)
            self.assertEqual(new.returncode, 0, errors)
            new_token = json.loads(output)
            old_token = json.loads(ready.read_text())
            self.assertGreater(new_token["generation"], old_token["generation"])
            before = financial_snapshot(self.path)
        finally:
            release.touch()
        output, errors = old.communicate(timeout=8)
        self.assertEqual(old.returncode, 0, errors)
        self.assertTrue({"writer_fenced", "lease_expired"} & set(json.loads(output)["fenced"]))
        self.assertEqual(financial_snapshot(self.path), before)
        token = WriterFence(self.database).acquire("parent-recovery", 10)
        self.assertGreater(token.generation, new_token["generation"])
        current = self.open_service(self.database.for_writer(token))
        current.deposit("alice", "new-writer-deposit", "USD", D(1))
        self.assertEqual(current.account("alice")["balances"]["USD"], "1001")
        current.ledger.verify()

    def test_lease_expiring_after_financial_dml_rolls_back_at_commit_checkpoint(self):
        tick = [1_000_000_000]
        database = Database(self.path, fence_clock_ns=lambda: tick[0], fence_boot_id="synthetic-boot")
        _, token, _ = self.managed(database=database, ttl=1)
        writer = database.for_writer(token)
        before = financial_snapshot(self.path)
        with self.assertRaises(WriterFenceError) as caught:
            with writer.transaction() as connection:
                connection.execute("UPDATE uta_accounts SET version=version+1 WHERE account_id='alice'")
                tick[0] += 1_000_000_000
        self.assertEqual(caught.exception.code, "lease_expired")
        self.assertEqual(financial_snapshot(self.path), before)

    def test_same_owner_nonce_cannot_reuse_released_generation_and_pid_bound_token_cannot_transfer(self):
        fence, token, _ = self.managed()
        fence.release(token)
        newer = fence.acquire(token.owner_nonce, 30)
        self.assertGreater(newer.generation, token.generation)
        stale = self.database.for_writer(token)
        before = financial_snapshot(self.path)
        self.fenced(self.open_service, stale)
        self.assertEqual(financial_snapshot(self.path), before)
        code = r'''
from datetime import datetime
from decimal import Decimal as D
import json, sys
from uta.service import ExchangeService
from uta.storage import Database
from uta.writer_fence import WriterToken
token = WriterToken(**json.loads(sys.argv[3]))
try:
    service = ExchangeService(Database(sys.argv[1]).for_writer(token), {"USD":8}, clock=lambda:datetime.fromisoformat(sys.argv[2]))
    service.deposit("alice", "transferred-token", "USD", D(1))
except Exception as error:
    pending, codes = [error], []
    while pending:
        value = pending.pop()
        if value is None: continue
        codes.append(getattr(value, "code", type(value).__name__))
        pending.append(value.__cause__)
    print(json.dumps(codes), flush=True)
else: raise AssertionError("a different PID used a transferred writer token")
'''
        child = self.child(code, json.dumps(asdict(newer)))
        self.assertEqual(child.returncode, 0, child.stderr)
        self.assertIn("writer_fenced", json.loads(child.stdout))
        self.assertEqual(financial_snapshot(self.path), before)


if __name__ == "__main__":
    unittest.main()
