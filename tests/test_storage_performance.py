"""WAL lifetime optimization must preserve the existing transaction contract."""
import gc
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
import weakref

from uta.storage import Database, StorageError


class StoragePerformanceTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "database.sqlite3"

    def database(self, **kwargs):
        database = Database(self.path, **kwargs)
        self.addCleanup(database.close)
        return database

    def test_keeper_never_writes_or_weakens_transaction_connection_durability(self):
        database = self.database()
        connections = []
        for index in range(2):
            with database.transaction() as connection:
                connections.append(connection)
                self.assertEqual(connection.execute("PRAGMA journal_mode").fetchone()[0], "wal")
                self.assertEqual(connection.execute("PRAGMA synchronous").fetchone()[0], 2)
                self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
                self.assertTrue(connection.in_transaction)
                connection.execute("CREATE TABLE IF NOT EXISTS example(value INTEGER)")
                connection.execute("INSERT INTO example VALUES (?)", (index,))
        self.assertIsNot(connections[0], connections[1])
        self.assertEqual(database._keeper.execute("PRAGMA query_only").fetchone()[0], 1)
        self.assertFalse(database._keeper.in_transaction)
        with self.assertRaises(sqlite3.OperationalError):
            database._keeper.execute("INSERT INTO example VALUES (9)")
        with database.transaction() as connection:
            self.assertEqual([row[0] for row in connection.execute("SELECT value FROM example")], [0, 1])

    def test_explicit_close_and_context_manager_release_keeper(self):
        with self.database() as database:
            with database.transaction():
                pass
            keeper = database._keeper
        with self.assertRaises(sqlite3.ProgrammingError):
            keeper.execute("SELECT 1")
        with self.assertRaises(StorageError):
            with database.transaction():
                self.fail("closed database admitted another transaction")
        database.close()  # Repeated shutdown is idempotent.

    def test_unreferenced_database_closes_keeper_without_global_reference_leak(self):
        database = Database(self.path)
        with database.transaction():
            pass
        keeper = database._keeper
        reference = weakref.ref(database)
        del database
        gc.collect()
        self.assertIsNone(reference())
        with self.assertRaises(sqlite3.ProgrammingError):
            keeper.execute("SELECT 1")

    def test_keeper_can_be_disabled_and_file_replacement_never_switches_authority(self):
        database = self.database(keep_wal_open=False)
        with database.transaction() as connection:
            connection.execute("CREATE TABLE original(value INTEGER)")
        self.assertIsNone(database._keeper)
        old_path = self.path.with_name("old.sqlite3")
        self.path.rename(old_path)
        self.path.touch(mode=0o600)
        with self.assertRaises(StorageError):
            with database.transaction():
                self.fail("replaced database became authority")

    def test_deleted_database_is_not_recreated_behind_a_live_instance(self):
        database = self.database()
        with database.transaction():
            pass
        self.path.unlink()
        with self.assertRaises(StorageError):
            with database.transaction():
                self.fail("deleted authority was recreated")
        self.assertFalse(self.path.exists())

    def test_keeper_is_shared_only_as_idle_resource_across_threads(self):
        database = self.database()
        with database.transaction() as connection:
            connection.execute("CREATE TABLE counter(value INTEGER)")
        errors = []
        def append(index):
            try:
                with database.transaction() as connection:
                    connection.execute("INSERT INTO counter VALUES (?)", (index,))
            except BaseException as exc:
                errors.append(exc)
        threads = [threading.Thread(target=append, args=(index,)) for index in range(12)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(5)
            self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        with database.transaction() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM counter").fetchone()[0], 12)

    @unittest.skipUnless(hasattr(os, "fork"), "fork is unavailable on this platform")
    def test_child_discards_inherited_keeper_and_reopens_its_own_connections(self):
        database = self.database()
        with database.transaction() as connection:
            connection.execute("CREATE TABLE counter(value INTEGER)")
        inherited = database._keeper
        child = os.fork()
        if child == 0:
            try:
                if database._keeper is not None:
                    os._exit(11)
                try:
                    inherited.execute("SELECT 1")
                except sqlite3.ProgrammingError:
                    pass
                else:
                    os._exit(12)
                with database.transaction() as connection:
                    connection.execute("INSERT INTO counter VALUES (1)")
                database.close()
                os._exit(0)
            except BaseException:
                os._exit(13)
        _, status = os.waitpid(child, 0)
        self.assertEqual(os.waitstatus_to_exitcode(status), 0)
        self.assertIs(database._keeper, inherited)
        with database.transaction() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM counter").fetchone()[0], 1)
            connection.execute("INSERT INTO counter VALUES (2)")


if __name__ == "__main__":
    unittest.main()
