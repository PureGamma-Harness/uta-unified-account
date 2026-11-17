"""Forced WAL schema/guard interleavings; leases use a fixed valid test clock."""
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Thread, current_thread
import sqlite3
import subprocess
import sys
from time import monotonic
import unittest
from unittest.mock import patch

from uta.storage import Database, StorageError
from uta.writer_fence import WriterFence, WriterFenceError
import uta.writer_fence as fence_module


class GuardSnapshotTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.database = Database(Path(temporary.name) / "snapshot.sqlite3",
                                 fence_clock_ns=lambda: 1_000_000_000, fence_boot_id="snapshot-test")
        with self.database.transaction() as connection:
            connection.execute("CREATE TABLE initial_financial_table(id INTEGER PRIMARY KEY)")
        fence = WriterFence(self.database)
        fence.enable("snapshot-authority")
        self.writer = self.database.for_writer(fence.acquire("writer", 1))

    def test_diagnostic_read_preserves_another_active_sqlite_kernel_lock(self):
        from uta.durable_process import _DiagnosticDatabase
        probe = """import fcntl,os,sys
fd=os.open(sys.argv[1],os.O_RDWR)
try:
 try:
  fcntl.lockf(fd,fcntl.LOCK_EX|fcntl.LOCK_NB,510,0x40000002,os.SEEK_SET)
  print('ACQUIRED')
 except BlockingIOError: print('BLOCKED')
finally: os.close(fd)
"""
        def state():
            return subprocess.check_output([sys.executable, "-c", probe, self.database.path], text=True, timeout=5).strip()
        for write in (False, True):
            with self.subTest(active_transaction="write" if write else "read"):
                with (self.writer.transaction() if write else self.database.read_transaction()) as holder:
                    holder.execute("SELECT COUNT(*) FROM initial_financial_table").fetchone()
                    if write:
                        holder.execute("INSERT INTO initial_financial_table VALUES (1)")
                    self.assertEqual(state(), "BLOCKED")
                    diagnostic = _DiagnosticDatabase(self.database, monotonic() + 3)
                    with diagnostic.read_transaction() as observer:
                        observer.execute("SELECT COUNT(*) FROM initial_financial_table").fetchone()
                        self.assertEqual(state(), "BLOCKED")
                    self.assertTrue(holder.in_transaction)
                    self.assertEqual(state(), "BLOCKED")

    def test_preflight_does_not_release_an_active_sqlite_posix_lock(self):
        from uta.request_signing import _ExistingAuthDatabase
        from uta.sharding import _BoundShardDatabase
        # This independent PID probes the main-file SHARED lock, not a Python
        # mutex or SQLite metadata field. POSIX byte offsets are SQLite's
        # documented default PENDING_BYTE + 2 and SHARED_SIZE.
        probe = """import fcntl,os,sys
fd=os.open(sys.argv[1],os.O_RDWR)
try:
 try:
  fcntl.lockf(fd,fcntl.LOCK_EX|fcntl.LOCK_NB,510,0x40000002,os.SEEK_SET)
  print('ACQUIRED')
 except BlockingIOError: print('BLOCKED')
finally: os.close(fd)
"""
        def state():
            return subprocess.check_output([sys.executable, "-c", probe, self.database.path], text=True, timeout=5).strip()
        checkers = (self.database, _BoundShardDatabase(self.database.path, 0, "unused-preflight-identity"),
                    _ExistingAuthDatabase(self.database.path))
        with self.writer.transaction() as connection:
            connection.execute("INSERT INTO initial_financial_table VALUES (1)")
            for checker in checkers:
                with self.subTest(checker=type(checker).__name__):
                    self.assertEqual(state(), "BLOCKED")
                    checker._private_file()
                    self.assertTrue(connection.in_transaction)
                    self.assertEqual(state(), "BLOCKED", "preflight released SQLite's active process-level file lock")

    def test_uri_open_does_not_recreate_a_path_removed_after_validation(self):
        victim = Path(self.database.path).with_name("removed.sqlite3")
        database = Database(victim)
        with database.transaction() as connection:
            connection.execute("CREATE TABLE existing_data(id INTEGER PRIMARY KEY)")
        original = database._private_file
        def removed():
            identity = original()
            victim.unlink()
            return identity
        with patch.object(database, "_private_file", removed):
            with self.assertRaises(sqlite3.OperationalError):
                with database.transaction():
                    self.fail("removed authority was recreated")
        self.assertFalse(victim.exists())

    def test_missing_read_only_authority_creates_neither_database_nor_sidecar(self):
        path = Path(self.database.path).with_name("missing-reader.sqlite3")
        database = Database(path)
        before = set(path.parent.iterdir())
        with self.assertRaises(StorageError):
            with database.read_transaction():
                self.fail("missing read-only authority was created")
        self.assertEqual(set(path.parent.iterdir()), before)
        # A failed read does not leak its policy into an explicit initializer.
        with database.transaction() as connection:
            connection.execute("CREATE TABLE explicit_initializer(id INTEGER)")
        self.assertTrue(path.is_file())

    def test_existing_empty_file_read_does_not_initialize_pages_or_sidecars(self):
        path = Path(self.database.path).with_name("empty-readonly.sqlite3")
        path.touch(mode=0o600)
        before = path.read_bytes()
        before_files = set(path.parent.iterdir())
        with Database(path).read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()[0], 0)
            self.assertEqual(connection.execute("PRAGMA journal_mode").fetchone()[0], "delete")
            self.assertEqual(set(path.parent.iterdir()), before_files)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(set(path.parent.iterdir()), before_files)

    def test_delete_mode_read_preserves_bytes_journal_mode_and_sentinel(self):
        path = Path(self.database.path).with_name("delete-readonly.sqlite3")
        connection = sqlite3.connect(path)
        try:
            self.assertEqual(connection.execute("PRAGMA journal_mode=DELETE").fetchone()[0], "delete")
            connection.execute("CREATE TABLE sentinel(value TEXT NOT NULL)")
            connection.execute("INSERT INTO sentinel VALUES ('preserve-me')")
            connection.commit()
        finally:
            connection.close()
        path.chmod(0o600)
        before = path.read_bytes()
        before_files = set(path.parent.iterdir())
        with Database(path).read_transaction() as observer:
            self.assertEqual(observer.execute("SELECT value FROM sentinel").fetchone()[0], "preserve-me")
            self.assertEqual(observer.execute("PRAGMA journal_mode").fetchone()[0], "delete")
            self.assertEqual(set(path.parent.iterdir()), before_files)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(set(path.parent.iterdir()), before_files)

    def test_committed_new_table_cannot_split_an_existing_read_guard_snapshot(self):
        registered_read, writer_committed = Event(), Event()
        original = fence_module._data_tables
        snapshots, failures = [], []
        def after_registered(connection):
            if current_thread().name == "guard-snapshot-observer":
                if not registered_read.is_set():
                    registered_read.set()
                    if not writer_committed.wait(5):
                        raise RuntimeError("writer did not reach its real COMMIT")
                tables = original(connection)
                snapshots.append(tables)
                return tables
            return original(connection)
        def observe():
            try:
                with self.database.read_transaction() as connection:
                    self.assertEqual(connection.execute("SELECT COUNT(*) FROM initial_financial_table").fetchone()[0], 0)
                    self.assertIsNone(connection.execute("SELECT 1 FROM sqlite_master WHERE name='later_financial_table'").fetchone())
            except BaseException as error:
                failures.append(error)
        with patch.object(fence_module, "_data_tables", after_registered):
            thread = Thread(target=observe, name="guard-snapshot-observer")
            thread.start()
            try:
                self.assertTrue(registered_read.wait(5))
                with self.writer.transaction() as connection:
                    connection.execute("CREATE TABLE later_financial_table(id INTEGER PRIMARY KEY)")
                    connection.execute("INSERT INTO later_financial_table VALUES (1)")
                writer_committed.set()
            finally:
                writer_committed.set()
                thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertFalse(failures, repr(failures))
        self.assertTrue(snapshots)
        self.assertTrue(all("later_financial_table" not in tables for tables in snapshots))
        with self.database.read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT actions FROM writer_fence_guard_tables WHERE name='later_financial_table'").fetchone()[0], "IUD")
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM later_financial_table").fetchone()[0], 1)

    def test_real_unregistered_table_remains_corruption_and_is_not_repaired(self):
        # A raw OS-owner connection deliberately bypasses application DDL.
        connection = sqlite3.connect(self.database.path, isolation_level=None)
        try:
            connection.execute("CREATE TABLE unregistered_financial_table(id INTEGER PRIMARY KEY)")
        finally:
            connection.close()
        with self.assertRaises(WriterFenceError) as error:
            with self.database.read_transaction():
                self.fail("corrupted inventory was accepted")
        self.assertEqual(error.exception.code, "fence_guard_corrupt")
        connection = sqlite3.connect(self.database.path)
        try:
            self.assertIsNone(connection.execute("SELECT 1 FROM writer_fence_guard_tables WHERE name='unregistered_financial_table'").fetchone())
        finally:
            connection.close()

    def test_pre_begin_schema_cache_cannot_override_the_new_transaction_snapshot(self):
        cached, writer_committed = Event(), Event()
        failures, observed = [], []
        class CachedReader(Database):
            def _connect(inner):
                connection = super()._connect()
                # Prepare both exact statements before the read transaction,
                # then commit a legal schema/registry change on another owner.
                connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                connection.execute("SELECT name,actions FROM writer_fence_guard_tables").fetchall()
                cached.set()
                if not writer_committed.wait(5):
                    connection.close()
                    raise RuntimeError("writer did not commit after pre-BEGIN schema caching")
                return connection
        reader = CachedReader(self.database.path)
        def observe():
            try:
                with reader.read_transaction() as connection:
                    observed.append(connection.execute("SELECT COUNT(*) FROM cache_boundary_table").fetchone()[0])
            except BaseException as error:
                failures.append(error)
        thread = Thread(target=observe)
        thread.start()
        try:
            self.assertTrue(cached.wait(5))
            with self.writer.transaction() as connection:
                connection.execute("CREATE TABLE cache_boundary_table(id INTEGER PRIMARY KEY)")
                connection.execute("INSERT INTO cache_boundary_table VALUES (1)")
            writer_committed.set()
        finally:
            writer_committed.set()
            thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertFalse(failures, repr(failures))
        self.assertEqual(observed, [1])


if __name__ == "__main__":
    unittest.main()
