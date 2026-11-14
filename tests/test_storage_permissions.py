import os
from pathlib import Path
import tempfile
import unittest

from uta.storage import Database, StorageError


class StoragePermissionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "exchange.sqlite3"

    def test_database_and_sidecars_are_private_even_with_permissive_umask(self):
        previous = os.umask(0)
        try:
            with Database(self.path).transaction() as conn:
                conn.execute("CREATE TABLE example (value TEXT)")
                for path in self.path.parent.iterdir():
                    self.assertEqual(path.stat().st_mode & 0o077, 0, str(path))
        finally:
            os.umask(previous)

    def test_existing_public_database_and_symlink_are_rejected(self):
        self.path.touch(mode=0o644)
        self.path.chmod(0o644)
        with self.assertRaises(StorageError):
            with Database(self.path).transaction():
                self.fail("unsafe database opened")
        self.path.chmod(0o600)
        link = self.path.with_name("alias.sqlite3")
        link.symlink_to(self.path)
        with self.assertRaises((StorageError, OSError)):
            with Database(link).transaction():
                self.fail("database symlink followed")

    def test_permission_change_is_checked_on_each_connection(self):
        database = Database(self.path)
        with database.transaction() as conn:
            conn.execute("CREATE TABLE example (value TEXT)")
        self.path.chmod(0o644)
        with self.assertRaises(StorageError):
            with database.transaction():
                self.fail("permission change ignored")


if __name__ == "__main__":
    unittest.main()
