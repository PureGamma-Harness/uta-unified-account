"""Read-only constructor joins use real registry identity, never role flags."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from uta.storage import Database
from uta.writer_fence import WriterFence, WriterFenceError, _assert_existing_read_joinable


class ExistingReadJoinableTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(prefix="uta-existing-read-")
        self.addCleanup(self.directory.cleanup)
        self.clock = [1_000_000_000]
        self.db = Database(Path(self.directory.name) / "actual.sqlite3", fence_clock_ns=lambda: self.clock[0], fence_boot_id="synthetic-boot")
        with self.db.transaction() as con:
            con.execute("CREATE TABLE actual_data(value INTEGER NOT NULL)")
            con.execute("INSERT INTO actual_data VALUES(1)")

    def test_real_read_and_control_snapshots_join_without_financial_authority(self):
        for method in (self.db.read_transaction, self.db._fence_transaction):
            with method() as con:
                self.assertIsNone(_assert_existing_read_joinable(self.db, con))
                self.assertEqual(con.execute("SELECT value FROM actual_data").fetchone()[0], 1)
        with self.assertRaises(WriterFenceError):
            with self.db._fence_transaction() as con:
                _assert_existing_read_joinable(self.db, con)
                try:
                    con.execute("UPDATE actual_data SET value=2")
                except sqlite3.DatabaseError:
                    pass
        with self.db.read_transaction() as con:
            self.assertEqual(con.execute("SELECT value FROM actual_data").fetchone()[0], 1)

    def test_financial_inbox_raw_and_same_path_other_database_are_rejected(self):
        for method in (self.db.transaction, self.db.inbox_transaction):
            with method() as con, self.assertRaises(WriterFenceError):
                _assert_existing_read_joinable(self.db, con)
        raw = self.db._connect()
        try:
            raw.execute("BEGIN")
            with self.assertRaises(WriterFenceError):
                _assert_existing_read_joinable(self.db, raw)
            raw.rollback()
        finally:
            raw.close()
        with self.db.read_transaction() as con, self.assertRaises(WriterFenceError):
            _assert_existing_read_joinable(Database(self.db.path), con)

    def test_foreign_thread_cannot_use_a_real_guarded_read_connection(self):
        def call(con):
            try:
                _assert_existing_read_joinable(self.db, con)
            except WriterFenceError as error:
                return error.code
            return "incorrectly_allowed"
        with self.db.read_transaction() as con, ThreadPoolExecutor(max_workers=1) as pool:
            self.assertEqual(pool.submit(call, con).result(timeout=1), "unguarded_connection")

    def test_bound_actual_token_is_checked_and_expiry_is_not_accepted(self):
        fence = WriterFence(self.db)
        fence.enable("synthetic:existing")
        token = fence.acquire("synthetic:owner", 1)
        bound = self.db.for_writer(token)
        with bound.read_transaction() as con:
            _assert_existing_read_joinable(bound, con)
            self.clock[0] += 1_000_000_000
            with self.assertRaises(WriterFenceError) as refused:
                _assert_existing_read_joinable(bound, con)
            self.assertEqual(refused.exception.code, "lease_expired")
