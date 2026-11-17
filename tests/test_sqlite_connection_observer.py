from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory
import unittest

from tests.sqlite_connection_observer import trace_new_sqlite_connections


class ActualSQLiteConnectionObserverTests(unittest.TestCase):
    def test_real_constructor_is_observed_after_init_and_all_state_is_restored(self):
        previous, statements = sys.getprofile(), []
        with TemporaryDirectory(prefix="uta-sqlite-real-observer-") as directory:
            with trace_new_sqlite_connections(statements):
                connection = sqlite3.connect(Path(directory)/"observer.sqlite3")
                try:
                    self.assertEqual(connection.execute("SELECT 7").fetchone()[0], 7)
                finally:
                    connection.close()
            self.assertIs(sys.getprofile(), previous)
            before = list(statements)
            connection = sqlite3.connect(Path(directory)/"outside.sqlite3")
            try:
                self.assertEqual(connection.execute("SELECT 9").fetchone()[0], 9)
            finally:
                connection.close()
            self.assertEqual(statements, before)
        self.assertIn("SELECT 7", statements)

    def test_exception_restores_prior_profile_without_an_uninitialized_handle(self):
        previous, statements = sys.getprofile(), []
        with self.assertRaises(RuntimeError):
            with trace_new_sqlite_connections(statements):
                connection = sqlite3.connect(":memory:")
                try:
                    connection.execute("SELECT 11").fetchone()
                finally:
                    connection.close()
                raise RuntimeError("synthetic body failure")
        self.assertIs(sys.getprofile(), previous)
        self.assertIn("SELECT 11", statements)


if __name__ == "__main__":
    unittest.main()
