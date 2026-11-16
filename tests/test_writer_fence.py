from dataclasses import asdict, replace
from datetime import datetime, timezone
from decimal import Decimal as D
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Event
import unittest

from uta.credit import CreditService
from uta.ledger import Posting
from uta.market import MarketSnapshot
from uta.matching import Matcher
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ExchangeService
from uta.storage import Database, DurableLedger, StorageError
from uta.writer_fence import WriterFence, WriterFenceError, WriterToken


class FakeClock:
    def __init__(self):
        self.now = 1_000_000_000
    def __call__(self):
        return self.now


class WriterFenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "authority.sqlite3"
        self.clock = FakeClock()
        self.database = Database(self.path, fence_clock_ns=self.clock, fence_boot_id="test-boot")
        self.exchange = ExchangeService(self.database, {"USD": 8})
        self.exchange.create_account("alice")
        self.exchange.create_account("bob")
        self.exchange.deposit("alice", "seed", "USD", D(1000))
        self.exchange.deposit("bob", "seed", "USD", D(1000))
        self.exchange.publish_market(MarketSnapshot(1, datetime.now(timezone.utc),
            {"USD": AssetSpec(D(1), D(1))}, {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))}))
        self.exchange.set_kill_switch(False)
        self.matcher = Matcher(self.exchange)
        self.credit = CreditService(self.exchange)
        self.fence = WriterFence(self.database)

    def enable(self):
        return self.fence.enable("authority:one")

    def snapshot(self):
        with self.database.read_transaction() as connection:
            tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'writer_fence_%' ORDER BY name")]
            return {table: [tuple(row) for row in connection.execute('SELECT * FROM "' + table + '" ORDER BY rowid')]
                    for table in tables if table != "sqlite_sequence"}

    def code(self, code, operation, *args, **kwargs):
        with self.assertRaises(WriterFenceError) as caught:
            operation(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def test_enable_irreversible_and_old_exchange_credit_matcher_ledger_writers_are_denied(self):
        self.exchange.submit_order("alice", "buy", "BTC-PERP", D(1), D(100))
        self.exchange.submit_order("bob", "sell", "BTC-PERP", D(-1), D(100))
        before = self.snapshot()
        self.enable()
        operations = [
            lambda: self.exchange.deposit("alice", "old-deposit", "USD", D(1)),
            lambda: self.exchange.cancel_order("alice", "buy"),
            lambda: self.matcher.match_once("BTC-PERP"),
            lambda: self.credit.configure_limit("alice", "USD", D(10)),
            lambda: self.exchange.ledger.post("old-ledger", [Posting("external", "USD", D(-1)), Posting("customer:alice", "USD", D(1))]),
            lambda: ExchangeService(Database(self.path), {"USD": 8}),
        ]
        for operation in operations:
            self.code("writer_fenced", operation)
            self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.exchange.account("alice")["balances"]["USD"], "1000")
        self.code("authority_conflict", self.fence.enable, "another-authority")
        self.assertEqual(self.fence.enable("authority:one")["generation"], 0)
        self.assertEqual(self.snapshot(), before)

    def test_live_token_writes_and_release_then_monotonic_acquire_fences_old_token(self):
        self.enable()
        first = self.fence.acquire("owner:one", 1)
        bound = self.database.for_writer(first)
        self.assertIsNone(self.database.writer_token)
        self.assertIs(bound.writer_token, first)
        current = ExchangeService(bound, {"USD": 8})
        current.deposit("alice", "authorized", "USD", D(2))
        self.fence.renew(first, 1)
        self.assertEqual(self.fence.status()["generation"], 1)
        self.fence.release(first)
        second = self.fence.acquire("owner:two", 1)
        self.assertEqual(second.generation, 2)
        self.code("writer_fenced", current.deposit, "alice", "stale", "USD", D(1))
        self.code("writer_fenced", self.fence.renew, first, 1)
        self.assertEqual(self.exchange.account("alice")["balances"]["USD"], "1002")
        with self.database.for_writer(second).transaction() as connection:
            self.assertEqual(self.fence.assert_writer(connection, second)["generation"], 2)

    def test_expiry_equal_now_prevents_renew_and_reacquire_increments_generation(self):
        self.enable()
        first = self.fence.acquire("one", .001)
        self.clock.now = self.fence.status()["expires_ns"]
        self.assertFalse(self.fence.status()["active"])
        self.code("lease_expired", self.fence.renew, first, 1)
        self.code("lease_expired", self.fence.release, first)
        second = self.fence.acquire("two", 1)
        self.assertEqual(second.generation, first.generation + 1)

    def test_expiring_lease_at_commit_rolls_back_financial_rows_and_version(self):
        self.enable()
        token = self.fence.acquire("one", 1)
        bound = self.database.for_writer(token)
        expiry = self.fence.status()["expires_ns"]
        before = self.snapshot()
        with self.assertRaises(WriterFenceError) as caught:
            with bound.transaction() as connection:
                self.exchange.ledger.post("expiry", [Posting("external", "USD", D(-1)), Posting("customer:alice", "USD", D(1))], connection=connection)
                connection.execute("UPDATE uta_accounts SET version=version+1 WHERE account_id='alice'")
                self.clock.now = expiry
        self.assertEqual(caught.exception.code, "lease_expired")
        self.assertEqual(self.snapshot(), before)

    def test_control_and_read_roles_cannot_write_finance_and_financial_token_cannot_edit_lease(self):
        self.enable()
        token = self.fence.acquire("one", 1)
        for role in (self.database.read_transaction, self.database.inbox_transaction, self.database._fence_transaction):
            with self.subTest(role=role.__name__), self.assertRaises(WriterFenceError):
                with role() as connection:
                    connection.execute("UPDATE uta_accounts SET version=100")
        for sql in ("DELETE FROM writer_fence_lease", "DROP TABLE writer_fence_authority",
                    "UPDATE writer_fence_lease SET generation=99", "PRAGMA writable_schema=ON"):
            with self.subTest(sql=sql), self.assertRaises(WriterFenceError):
                with self.database.for_writer(token).transaction() as connection:
                    connection.execute(sql)
        with self.assertRaises(WriterFenceError):
            with self.database._fence_transaction() as connection:
                connection.execute("CREATE TRIGGER writer_fence_unrelated AFTER INSERT ON uta_accounts BEGIN SELECT 1; END")
        self.assertEqual(self.fence.status()["generation"], 1)

    def test_old_unbound_ddl_and_swallowed_denial_cannot_commit(self):
        self.enable()
        with self.assertRaises(WriterFenceError):
            with self.database.transaction() as connection:
                connection.execute("CREATE TABLE unauthorized (x INTEGER)")
        with self.assertRaises(WriterFenceError):
            with self.database.transaction() as connection:
                try:
                    connection.execute("UPDATE uta_accounts SET version=999")
                except sqlite3.DatabaseError:
                    pass
        with self.database.read_transaction() as connection:
            self.assertIsNone(connection.execute("SELECT name FROM sqlite_master WHERE name='unauthorized'").fetchone())

    def test_managed_ledger_refuses_bare_sqlite_supplied_connection(self):
        self.enable()
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("BEGIN IMMEDIATE")
        try:
            self.code("unguarded_connection", self.exchange.ledger.post, "bare", [Posting("external", "USD", D(-1)), Posting("customer:alice", "USD", D(1))], connection=connection)
        finally:
            connection.rollback()
            connection.close()

    def test_boot_change_and_clock_regression_are_fail_closed(self):
        self.enable()
        token = self.fence.acquire("one", 1)
        self.clock.now -= 1
        self.code("fence_clock_regressed", self.fence.renew, token, 1)
        self.clock.now += 1
        other_boot = Database(self.path, fence_clock_ns=self.clock, fence_boot_id="new-boot")
        self.code("writer_fenced", WriterFence(other_boot).renew, token, 1)
        newer = WriterFence(other_boot).acquire("new-owner", 1)
        self.assertEqual(newer.generation, token.generation + 1)
        self.code("writer_fenced", self.fence.renew, token, 1)

    def test_process_identity_cannot_be_transferred_by_serializing_a_token(self):
        self.enable()
        token = self.fence.acquire("one", 1)
        restored = WriterToken(**asdict(token))
        self.assertEqual(token, restored)
        wrong = replace(token, process_id=os.getpid() + 1)
        self.code("writer_fenced", self.fence.renew, wrong, 1)

    def test_real_processes_compete_and_only_one_acquires_a_live_lease(self):
        # These instances use the real boot clock, not the deterministic fixture.
        database = Database(self.path)
        WriterFence(database).enable("authority:one")
        script = '''
import json,sys
from dataclasses import asdict
from uta.storage import Database
from uta.writer_fence import WriterFence,WriterFenceError
try:
 token=WriterFence(Database(sys.argv[1])).acquire(sys.argv[2],2)
 print(json.dumps({'token':asdict(token)}),flush=True)
except WriterFenceError as error:
 print(json.dumps({'code':error.code}),flush=True)
'''
        processes = [subprocess.Popen([sys.executable, "-c", script, str(self.path), f"child-{i}"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for i in range(2)]
        try:
            results = []
            for process in processes:
                output, error = process.communicate(timeout=10)
                self.assertEqual(process.returncode, 0, error)
                results.append(json.loads(output))
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.wait()
        self.assertEqual(sum("token" in result for result in results), 1)
        self.assertEqual([result["code"] for result in results if "code" in result], ["lease_busy"])

    def test_real_expired_process_resumes_but_cannot_write_after_takeover(self):
        WriterFence(Database(self.path)).enable("authority:one")
        script = '''
import json,sys
from decimal import Decimal as D
from uta.storage import Database
from uta.service import ExchangeService
from uta.writer_fence import WriterFence,WriterFenceError
db=Database(sys.argv[1]);fence=WriterFence(db)
token=fence.acquire('paused-child',.25)
service=ExchangeService(db.for_writer(token),{'USD':8})
print(json.dumps({'generation':token.generation}),flush=True)
sys.stdin.readline()
try:
 service.deposit('alice','stale-child','USD',D(1))
 print(json.dumps({'unexpected':'wrote'}),flush=True)
except WriterFenceError as error:
 print(json.dumps({'code':error.code}),flush=True)
'''
        process = subprocess.Popen([sys.executable, "-c", script, str(self.path)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            first = json.loads(process.stdout.readline())
            Event().wait(.3)
            fence = WriterFence(Database(self.path))
            second = fence.acquire("takeover-parent", 2)
            self.assertEqual(second.generation, first["generation"] + 1)
            ExchangeService(Database(self.path).for_writer(second), {"USD": 8}).deposit("alice", "new-owner", "USD", D(3))
            output, error = process.communicate("resume\n", timeout=10)
            self.assertEqual(process.returncode, 0, error)
            self.assertEqual(json.loads(output)["code"], "writer_fenced")
            self.assertEqual(self.exchange.account("alice")["balances"]["USD"], "1003")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()

    def test_invalid_settings_and_no_managed_worker_assertion(self):
        self.code("fence_not_managed", self.fence.acquire, "one", 1)
        with self.database.transaction() as connection:
            self.code("fence_not_managed", self.fence.assert_writer, connection)
        self.enable()
        for ttl in (0, True, float("inf"), .0001, 3601):
            with self.subTest(ttl=ttl), self.assertRaises(ValueError):
                self.fence.acquire("one", ttl)
        with self.assertRaises(ValueError):
            self.fence.enable("bad name")
        with self.assertRaises(StorageError):
            self.database.for_writer(object())

    def test_bound_token_cannot_fall_back_to_legacy_when_managed_marker_is_missing(self):
        self.enable()
        token = self.fence.acquire("one", 1)
        separate = Database(Path(self.temporary.name) / "unmanaged.sqlite3")
        with separate.transaction() as connection:
            connection.execute("CREATE TABLE business(value INTEGER)")
        with self.assertRaises(WriterFenceError) as caught:
            with separate.for_writer(token).transaction() as connection:
                connection.execute("INSERT INTO business VALUES(1)")
        self.assertEqual(caught.exception.code, "fence_not_managed")
        with separate.read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM business").fetchone()[0], 0)

    def test_copy_to_another_path_cannot_reuse_managed_authority(self):
        self.enable()
        token = self.fence.acquire("one", 1)
        cloned = Path(self.temporary.name) / "clone.sqlite3"
        # SQLite backup produces a complete copy, including the lease history.
        with sqlite3.connect(self.path) as source, sqlite3.connect(cloned) as target:
            source.backup(target)
        cloned.chmod(0o600)
        self.code("authority_path_conflict", WriterFence(Database(cloned)).status)
        with self.assertRaises(WriterFenceError) as caught:
            with Database(cloned).for_writer(token).transaction() as connection:
                connection.execute("UPDATE uta_accounts SET version=version+1")
        self.assertEqual(caught.exception.code, "authority_path_conflict")

    def test_inbox_bootstrap_allows_only_required_implicit_sqlite_schema(self):
        # Exercise SQLite's actual AUTOINCREMENT/UNIQUE authorizer callbacks.
        with self.database.inbox_transaction() as connection:
            connection.execute("CREATE TABLE uta_command_config(singleton INTEGER PRIMARY KEY)")
            connection.execute("CREATE TABLE uta_command_inbox(sequence INTEGER PRIMARY KEY AUTOINCREMENT,command_id TEXT UNIQUE,state TEXT)")
            connection.execute("CREATE INDEX uta_command_pending ON uta_command_inbox(state,sequence)")
            connection.execute("INSERT INTO uta_command_config VALUES(1)")
            connection.execute("INSERT INTO uta_command_inbox(command_id,state) VALUES('one','PENDING')")
        self.enable()
        with self.database.inbox_transaction() as connection:
            connection.execute("INSERT INTO uta_command_inbox(command_id,state) VALUES('two','PENDING')")
        with self.database.read_transaction() as connection:
            self.assertEqual([tuple(row) for row in connection.execute("SELECT sequence,command_id FROM uta_command_inbox ORDER BY sequence")], [(1, "one"), (2, "two")])
        for sql in ("CREATE TABLE unrelated(value TEXT)",
                    "CREATE INDEX unauthorized_index ON uta_command_inbox(state)",
                    "UPDATE uta_command_inbox SET state='SUCCEEDED'"):
            with self.subTest(sql=sql), self.assertRaises(WriterFenceError):
                with self.database.inbox_transaction() as connection:
                    connection.execute(sql)


if __name__ == "__main__":
    unittest.main()
