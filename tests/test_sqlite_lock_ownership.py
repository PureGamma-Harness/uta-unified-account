"""Independent POSIX/SQLite lock ownership regression; temporary synthetic DBs.

Process A is this test runner. Its second thread exercises the normal database
API while an actual SQLite transaction is open. Every kernel probe runs in a
new process B, which never consults SQLite's in-process lock bookkeeping.
"""
from __future__ import annotations

from contextlib import closing
from copy import copy
from datetime import datetime, timezone
from decimal import Decimal as D
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Barrier, Thread
import unittest

from uta.request_signing import _ExistingAuthDatabase
from uta.service import ExchangeService, ServiceError
from uta.sharding import ShardRouter, _BoundShardDatabase
from uta.storage import Database, StorageError
from uta.writer_fence import WriterFence, WriterFenceError


KERNEL_PROBE = r'''
import errno,fcntl,json,os,sys
descriptor=os.open(sys.argv[1],os.O_RDWR|os.O_CLOEXEC|os.O_NOFOLLOW)
try:
    # Standard Unix SQLite main-file SHARED range: PENDING_BYTE + 2, 510 bytes.
    try:
        fcntl.lockf(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB,510,0x40000002,os.SEEK_SET)
    except OSError as error:
        if error.errno not in (errno.EACCES,errno.EAGAIN): raise
        print(json.dumps({"pid":os.getpid(),"exclusive":False}),flush=True)
    else:
        print(json.dumps({"pid":os.getpid(),"exclusive":True}),flush=True)
        fcntl.lockf(descriptor,fcntl.LOCK_UN,510,0x40000002,os.SEEK_SET)
finally:
    os.close(descriptor)
'''

SQLITE_WRITE_PROBE = r'''
import json,os,sqlite3,sys
connection=sqlite3.connect(sys.argv[1],timeout=.05,isolation_level=None)
try:
    connection.execute("PRAGMA busy_timeout=50")
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("UPDATE lock_counter SET value=value+100 WHERE singleton=1")
        connection.commit()
    except sqlite3.OperationalError as error:
        if connection.in_transaction: connection.rollback()
        if "locked" not in str(error).lower() and "busy" not in str(error).lower(): raise
        print(json.dumps({"pid":os.getpid(),"committed":False,"reason":"busy"}),flush=True)
    else:
        print(json.dumps({"pid":os.getpid(),"committed":True}),flush=True)
finally:
    connection.close()
'''


class SQLiteLockOwnershipTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.plain = Database(self.directory / "plain.sqlite3", timeout=.05)
        auth_path = self.directory / "auth.sqlite3"
        with Database(auth_path).transaction() as connection:
            connection.execute("CREATE TABLE auth_fixture (singleton INTEGER PRIMARY KEY)")
        self.auth = _ExistingAuthDatabase(auth_path, timeout=.05)
        self.router = ShardRouter(self.directory / "shards", 2, {"USD": 8})
        self.bound = self.router._services[0].database
        self.targets = (self.plain, self.auth, self.bound)
        for database in self.targets:
            with database.transaction() as connection:
                connection.execute("CREATE TABLE lock_counter (singleton INTEGER PRIMARY KEY,value INTEGER NOT NULL)")
                connection.execute("INSERT INTO lock_counter VALUES (1,0)")

    def probe(self, database, *, sqlite_writer=False):
        child = subprocess.run([sys.executable, "-I", "-c",
                                SQLITE_WRITE_PROBE if sqlite_writer else KERNEL_PROBE,
                                str(database.path)], capture_output=True, text=True, timeout=5)
        self.assertEqual(child.returncode, 0, child.stderr)
        result = json.loads(child.stdout)
        self.assertNotEqual(result["pid"], os.getpid())
        return result

    def second_thread(self, action):
        errors = []
        def run():
            try:
                action()
            except BaseException as error:
                errors.append(error)
        thread = Thread(target=run)
        thread.start()
        thread.join(5)
        self.assertFalse(thread.is_alive(), "second database thread did not finish")
        if errors:
            raise errors[0]

    def hold_and_probe(self, database, *, writer, action):
        with (database.transaction() if writer else database.read_transaction()) as held:
            held.execute("SELECT value FROM lock_counter WHERE singleton=1").fetchone()
            if writer:
                held.execute("UPDATE lock_counter SET value=value+1 WHERE singleton=1")
            self.assertFalse(self.probe(database)["exclusive"], "real SQLite baseline did not hold the standard main-file lock")
            self.second_thread(action)
            self.assertTrue(held.in_transaction, "the holder transaction ended unexpectedly")
            self.assertFalse(self.probe(database)["exclusive"],
                "a second thread's ordinary database access released process A's SQLite main-file lock")
        self.assertTrue(self.probe(database)["exclusive"], "lock remained held after the SQLite connection closed")

    def test_private_checks_cannot_release_another_threads_actual_sqlite_read_or_write_locks(self):
        for database in self.targets:
            for writer in (False, True):
                with self.subTest(database=type(database).__name__, writer=writer):
                    other = copy(database)
                    self.hold_and_probe(database, writer=writer, action=other._private_file)

    def test_normal_second_read_transaction_cannot_release_a_live_main_file_lock(self):
        for database in self.targets:
            for writer in (False, True):
                with self.subTest(database=type(database).__name__, writer=writer):
                    other = copy(database)
                    def read():
                        with other.read_transaction() as connection:
                            connection.execute("SELECT value FROM lock_counter WHERE singleton=1").fetchone()
                    self.hold_and_probe(database, writer=writer, action=read)

    def test_rejected_second_writer_preserves_existing_kernel_lock_and_holder_commit(self):
        for database in self.targets:
            with self.subTest(database=type(database).__name__):
                other = copy(database)
                other.timeout = .05
                def rejected_writer():
                    with self.assertRaises(sqlite3.OperationalError) as caught:
                        with other.transaction():
                            self.fail("second writer crossed a live writer transaction")
                    self.assertIn("locked", str(caught.exception).lower())
                self.hold_and_probe(database, writer=True, action=rejected_writer)
                with database.read_transaction() as connection:
                    self.assertEqual(connection.execute("SELECT value FROM lock_counter").fetchone()[0], 1)

    def test_separate_pid_sqlite_writer_stays_busy_until_original_writer_releases(self):
        for database in self.targets:
            with self.subTest(database=type(database).__name__):
                with database.transaction() as held:
                    held.execute("UPDATE lock_counter SET value=1 WHERE singleton=1")
                    self.assertFalse(self.probe(database, sqlite_writer=True)["committed"])
                    self.second_thread(copy(database)._private_file)
                    self.assertFalse(self.probe(database, sqlite_writer=True)["committed"])
                    self.assertEqual(held.execute("SELECT value FROM lock_counter").fetchone()[0], 1)
                self.assertTrue(self.probe(database, sqlite_writer=True)["committed"])
                with database.read_transaction() as connection:
                    self.assertEqual(connection.execute("SELECT value FROM lock_counter").fetchone()[0], 101)

    def test_existing_public_or_symlink_database_is_rejected_without_modifying_its_bytes(self):
        for database in self.targets:
            with self.subTest(database=type(database).__name__):
                path = Path(database.path)
                before = hashlib.sha256(path.read_bytes()).hexdigest()
                path.chmod(0o666)
                try:
                    with self.assertRaises((StorageError, ServiceError, OSError)):
                        with database.transaction():
                            self.fail("public database reached a transaction body")
                    self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)
                finally:
                    path.chmod(0o600)
                link = path.with_name("link-" + path.name)
                link.symlink_to(path.name)
                alias = copy(database)
                alias.path = str(link)
                with self.assertRaises((StorageError, ServiceError, OSError)):
                    with alias.transaction():
                        self.fail("symlink database reached a transaction body")
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)
                self.assertTrue(link.is_symlink())

    def test_missing_read_only_targets_never_create_main_database_or_sidecars(self):
        for index, template in enumerate(self.targets):
            with self.subTest(database=type(template).__name__):
                database = copy(template)
                database.path = str(self.directory / ("missing-" + str(index) + ".sqlite3"))
                before = {path.name for path in self.directory.iterdir()}
                with self.assertRaises((StorageError, ServiceError, OSError, sqlite3.Error)):
                    with database.read_transaction():
                        self.fail("missing read-only database reached a transaction body")
                self.assertFalse(Path(database.path).exists())
                self.assertEqual({path.name for path in self.directory.iterdir()}, before)

    def test_shard_identity_and_managed_writer_fencing_remain_mandatory(self):
        shard_path = Path(self.bound.path)
        other_path = self.router._services[1].database.path
        shutil.copyfile(other_path, shard_path)
        with self.assertRaises(ServiceError) as caught:
            with self.bound.transaction():
                self.fail("wrong shard identity reached financial writes")
        self.assertEqual(caught.exception.code, "shard_identity_conflict")
        service = ExchangeService(self.plain, {"USD": 8}, clock=lambda: datetime(2026, 11, 16, tzinfo=timezone.utc))
        service.create_account("alice")
        service.deposit("alice", "seed", "USD", D(10))
        fence = WriterFence(self.plain)
        fence.enable("independent-lock-authority")
        token = fence.acquire("legitimate-writer", 30)
        with self.assertRaises(WriterFenceError):
            with self.plain.transaction() as connection:
                connection.execute("UPDATE lock_counter SET value=999")
        current = ExchangeService(self.plain.for_writer(token), {"USD": 8}, clock=lambda: datetime(2026, 11, 16, tzinfo=timezone.utc))
        current.deposit("alice", "legitimate", "USD", D(1))
        self.assertEqual(current.account("alice")["balances"]["USD"], "11")
        current.ledger.verify()

    def test_bounded_concurrent_dml_and_ddl_conserve_balances_and_reopen_cleanly(self):
        database = Database(self.directory / "concurrent.sqlite3", timeout=2)
        with database.transaction() as connection:
            connection.execute("CREATE TABLE lock_balances(account TEXT PRIMARY KEY,units INTEGER NOT NULL CHECK(units>=0))")
            connection.executemany("INSERT INTO lock_balances VALUES (?,?)", (("alice", 1000), ("bob", 1000)))
            connection.execute("CREATE TABLE lock_events(worker INTEGER,command INTEGER,PRIMARY KEY(worker,command))")
        barrier, errors = Barrier(3), []
        def transfer(worker):
            barrier.wait(5)
            try:
                local = Database(database.path, timeout=2)
                for command in range(12):
                    with local.transaction() as connection:
                        connection.execute(f"CREATE TABLE IF NOT EXISTS lock_ddl_{worker}_{command // 3}(marker INTEGER)")
                        source, target = (("alice", "bob") if command % 2 == 0 else ("bob", "alice"))
                        connection.execute("UPDATE lock_balances SET units=units-1 WHERE account=?", (source,))
                        connection.execute("UPDATE lock_balances SET units=units+1 WHERE account=?", (target,))
                        connection.execute("INSERT INTO lock_events VALUES (?,?)", (worker, command))
            except BaseException as error:
                errors.append(error)
        program = r'''
import sys
sys.path.insert(0,sys.argv[1])
from uta.storage import Database
print("READY",flush=True)
assert sys.stdin.readline().strip()=="GO"
database=Database(sys.argv[2],timeout=2)
for command in range(12):
    with database.transaction() as connection:
        connection.execute(f"CREATE TABLE IF NOT EXISTS lock_ddl_2_{command//3}(marker INTEGER)")
        source,target=(("alice","bob") if command%2==0 else ("bob","alice"))
        connection.execute("UPDATE lock_balances SET units=units-1 WHERE account=?",(source,))
        connection.execute("UPDATE lock_balances SET units=units+1 WHERE account=?",(target,))
        connection.execute("INSERT INTO lock_events VALUES (2,?)",(command,))
print("COMPLETED",flush=True)
'''
        import uta.storage
        repository = Path(uta.storage.__file__).resolve().parent.parent
        child = subprocess.Popen([sys.executable, "-I", "-c", program, str(repository), database.path],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        threads = [Thread(target=transfer, args=(worker,)) for worker in (0, 1)]
        try:
            self.assertEqual(child.stdout.readline().strip(), "READY")
            for thread in threads:
                thread.start()
            child.stdin.write("GO\n")
            child.stdin.flush()
            barrier.wait(5)
            for thread in threads:
                thread.join(10)
                self.assertFalse(thread.is_alive())
            output, stderr = child.communicate(timeout=10)
            self.assertEqual(child.returncode, 0, stderr)
            self.assertIn("COMPLETED", output)
            self.assertEqual(errors, [])
        finally:
            if child.poll() is None:
                child.kill()
            child.communicate(timeout=5)
        with database.read_transaction() as connection:
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(connection.execute("SELECT * FROM lock_balances ORDER BY account").fetchall()[0]["units"], 1000)
            self.assertEqual(connection.execute("SELECT SUM(units) FROM lock_balances").fetchone()[0], 2000)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM lock_events").fetchone()[0], 36)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name LIKE 'lock_ddl_%'").fetchone()[0], 12)
            for suffix in ("", "-wal", "-shm"):
                path = Path(database.path + suffix)
                if path.exists():
                    details = path.lstat()
                    self.assertTrue(stat.S_ISREG(details.st_mode))
                    self.assertEqual(stat.S_IMODE(details.st_mode) & 0o077, 0)
            unexpected = [path.name for path in self.directory.glob("concurrent.sqlite3-*")
                          if path.name not in {"concurrent.sqlite3-wal", "concurrent.sqlite3-shm"}]
            self.assertEqual(unexpected, [])


if __name__ == "__main__":
    unittest.main()
