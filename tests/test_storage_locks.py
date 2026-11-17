"""Opening a peer connection must preserve SQLite's process-level file locks."""
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from uta.sharding import _BoundShardDatabase
from uta.request_signing import _ExistingAuthDatabase
from uta.storage import Database


# SQLite's Unix VFS holds a shared lock in this range, including in WAL mode.
# Probe in a separate interpreter: POSIX record locks belong to the process,
# so a same-process probe would replace its own lock instead of detecting it.
_PROBE = """
import fcntl
import os
import sys
descriptor = os.open(sys.argv[1], os.O_RDWR)
try:
    try:
        fcntl.lockf(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB, 1, 0x40000002)
    except BlockingIOError:
        print('blocked')
    else:
        print('acquired')
finally:
    os.close(descriptor)
"""


@unittest.skipUnless(os.name == "posix", "SQLite Unix VFS record locks")
class StorageLockTests(unittest.TestCase):
    def probe(self, path):
        result = subprocess.run([sys.executable, "-c", _PROBE, str(path)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout.strip()

    def assert_peer_preserves_lock(self, database, peer):
        with database.transaction() as connection:
            connection.execute("CREATE TABLE lock_probe (value INTEGER)")
            connection.execute("INSERT INTO lock_probe VALUES (1)")
        self.assertEqual(self.probe(database.path), "acquired")
        with database.read_transaction() as reader:
            self.assertEqual(reader.execute("SELECT value FROM lock_probe").fetchone()[0], 1)
            self.assertEqual(self.probe(database.path), "blocked")
            with peer.read_transaction() as other:
                self.assertEqual(other.execute("SELECT value FROM lock_probe").fetchone()[0], 1)
                self.assertEqual(self.probe(database.path), "blocked",
                                 "opening a peer dropped the active reader's SQLite lock")
            self.assertEqual(self.probe(database.path), "blocked",
                             "closing a peer dropped the active reader's SQLite lock")
        self.assertEqual(self.probe(database.path), "acquired")

    def test_database_peer_preserves_active_reader_lock(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "authority.sqlite3"
            self.assert_peer_preserves_lock(Database(path), Database(path))

    def test_bound_shard_peer_preserves_active_reader_lock(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "shard.sqlite3"
            bootstrap = _BoundShardDatabase(path, 0, "lock-test", bootstrap=True)
            bootstrap.finish_bootstrap()
            self.assert_peer_preserves_lock(_BoundShardDatabase(path, 0, "lock-test"),
                                            _BoundShardDatabase(path, 0, "lock-test"))

    def test_auth_database_peer_preserves_active_reader_lock(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "auth.sqlite3"
            with Database(path).transaction() as connection:
                connection.execute("CREATE TABLE seed (value INTEGER)")
            self.assert_peer_preserves_lock(_ExistingAuthDatabase(path), _ExistingAuthDatabase(path))


if __name__ == "__main__":
    unittest.main()
