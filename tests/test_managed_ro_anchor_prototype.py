"""Owned-temp SQLite/kernel-RO experiments; never starts a service or old job."""
import errno
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from unittest.mock import patch

from tools.managed_ro_anchor_prototype import IdleReadHolders, WARM_READS


SCHEMAS = (
    'CREATE TABLE state(key TEXT PRIMARY KEY)',
    'CREATE TABLE router_layout(singleton INTEGER PRIMARY KEY)',
    'CREATE TABLE ledger_events(sequence INTEGER PRIMARY KEY)',
)
INSERTS = ('INSERT INTO state VALUES(?)', 'INSERT INTO router_layout VALUES(?)',
           'INSERT INTO ledger_events VALUES(?)')
TABLES = ('state', 'router_layout', 'ledger_events')
CHILD = r'''
import errno,json,os,sqlite3,sys
from pathlib import Path
root=Path(sys.argv[1]); expected=int(sys.argv[2]); counts=[]
assert os.statvfs(root).f_flag & os.ST_RDONLY
try:
    (root/'forbidden-write-probe').write_bytes(b'never')
except OSError as error:
    assert error.errno==errno.EROFS
else:
    raise AssertionError('kernel RO missing')
for relative,table in [('checkpoint.sqlite3','state'),('managed/router.sqlite3','router_layout'),('managed/shard-0000.sqlite3','ledger_events')]:
    connection=sqlite3.connect((root/relative).as_uri()+'?mode=ro',uri=True,isolation_level=None)
    try:
        connection.execute('PRAGMA query_only=ON')
        connection.execute('BEGIN')
        counts.append(connection.execute('SELECT COUNT(*) FROM '+table).fetchone()[0])
    finally:
        connection.close()
assert counts==[expected]*3,counts
print(json.dumps({'kernel_readonly':True,'counts':counts,'immutable_used':False}))
'''


class IdleReadHolderPrototypeTests(unittest.TestCase):
    def make(self):
        temporary = TemporaryDirectory(prefix='uta-ro-anchor-')
        self.addCleanup(temporary.cleanup)
        root, writers = Path(temporary.name), []
        self.addCleanup(lambda: [connection.close() for connection in writers])
        for number, (relative, _) in enumerate(WARM_READS):
            path = root / relative
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            connection = sqlite3.connect(path, isolation_level=None)
            writers.append(connection)
            path.chmod(0o600)
            self.assertEqual(connection.execute('PRAGMA journal_mode=WAL').fetchone()[0], 'wal')
            connection.execute(SCHEMAS[number])
            connection.execute(INSERTS[number], (1,))
        return root, writers

    def holders(self, root):
        holders = IdleReadHolders(root)
        self.addCleanup(holders.close)
        return holders

    def kernel_read(self, root, count):
        result = subprocess.run(['bwrap', '--die-with-parent', '--ro-bind', '/', '/',
            '--dev', '/dev', '--proc', '/proc', '--', sys.executable, '-B', '-c', CHILD,
            str(root), str(count)], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, close_fds=True, timeout=3)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(json.loads(result.stdout)['counts'], [count] * 3)
        self.assertFalse((root / 'forbidden-write-probe').exists())

    def test_warm_three_real_readers_preserve_aux_and_actual_kernel_ro_read(self):
        root, writers = self.make()
        self.holders(root)
        for connection in writers:
            connection.close()
        for relative, _ in WARM_READS:
            for suffix in ('-wal', '-shm'):
                self.assertTrue((root / (relative + suffix)).exists())
        self.kernel_read(root, 1)

    def test_no_pinned_snapshot_actual_writer_truncate_checkpoint_succeeds(self):
        root, writers = self.make()
        holders = self.holders(root)
        self.assertTrue(all(not connection.in_transaction for connection in holders.connections))
        for number, writer in enumerate(writers):
            for value in range(2, 10):
                writer.execute(INSERTS[number], (value,))
            self.assertEqual(writer.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone(), (0, 0, 0))
            self.assertEqual((root / (WARM_READS[number][0] + '-wal')).stat().st_size, 0)

    def test_reopened_real_writer_generation_keeps_reader_contract(self):
        root, writers = self.make()
        self.holders(root)
        for connection in writers:
            connection.close()
        for number, (relative, _) in enumerate(WARM_READS):
            connection = sqlite3.connect((root / relative).as_uri() + '?mode=rw', uri=True, isolation_level=None)
            try:
                connection.execute(INSERTS[number], (2,))
            finally:
                connection.close()
        self.kernel_read(root, 2)

    def test_every_real_warm_cursor_is_closed_before_idle_connection_is_retained(self):
        root, _ = self.make()
        original, cursors, statements = sqlite3.connect, [], []
        class TracedConnection(sqlite3.Connection):
            def execute(self, statement, *args, **kwargs):
                statements.append(statement)
                cursor = super().execute(statement, *args, **kwargs)
                cursors.append(cursor)
                return cursor
        def connect(*args, **kwargs):
            return original(*args, factory=TracedConnection, **kwargs)
        with patch('tools.managed_ro_anchor_prototype.sqlite3.connect', connect):
            holders = self.holders(root)
        self.assertTrue(all(query in statements for _, query in WARM_READS))
        for cursor in cursors:
            with self.assertRaises(sqlite3.ProgrammingError):
                cursor.fetchone()
        self.assertTrue(all(not connection.in_transaction for connection in holders.connections))

    def test_missing_main_fails_without_implicit_creation_or_aux(self):
        with TemporaryDirectory(prefix='uta-ro-anchor-missing-') as directory:
            root = Path(directory)
            with self.assertRaises(FileNotFoundError):
                IdleReadHolders(root)
            self.assertEqual(list(root.iterdir()), [])

    def test_direct_and_dangling_main_symlinks_are_rejected(self):
        for dangling in (False, True):
            with self.subTest(dangling=dangling):
                root, writers = self.make()
                for connection in writers:
                    connection.close()
                main = root / WARM_READS[0][0]
                replacement = root / 'replacement.sqlite3'
                main.rename(replacement)
                if dangling:
                    replacement.unlink()
                main.symlink_to(replacement)
                with self.assertRaises(ValueError):
                    IdleReadHolders(root)
                self.assertTrue(main.is_symlink())

    def test_actual_identity_replacement_after_original_sqlite_open_is_rejected(self):
        root, writers = self.make()
        for connection in writers:
            connection.close()
        replacement = root / 'replacement.sqlite3'
        connection = sqlite3.connect(replacement, isolation_level=None)
        connection.execute('PRAGMA journal_mode=WAL')
        connection.execute(SCHEMAS[0])
        connection.execute(INSERTS[0], (2,))
        connection.close()
        replacement.chmod(0o600)
        original, captured = sqlite3.connect, []
        def replace_after_open(*args, **kwargs):
            connection = original(*args, **kwargs)
            captured.append(connection)
            os.replace(replacement, root / WARM_READS[0][0])
            return connection
        with patch('tools.managed_ro_anchor_prototype.sqlite3.connect', replace_after_open):
            with self.assertRaises((ValueError, sqlite3.DatabaseError)):
                IdleReadHolders(root)
        for connection in captured:
            with self.assertRaises(sqlite3.ProgrammingError):
                connection.execute('SELECT 1')

    def test_wrong_format_or_nonwal_main_is_rejected_without_conversion(self):
        for invalid in (True, False):
            with self.subTest(invalid=invalid), TemporaryDirectory(prefix='uta-ro-anchor-format-') as directory:
                root, main = Path(directory), Path(directory) / WARM_READS[0][0]
                if invalid:
                    main.write_bytes(b'not a SQLite database')
                else:
                    connection = sqlite3.connect(main, isolation_level=None)
                    connection.execute(SCHEMAS[0])
                    connection.execute(INSERTS[0], (1,))
                    connection.close()
                main.chmod(0o600)
                before = main.read_bytes()  # Closed fixture only, no active SQLite inode.
                with self.assertRaises((ValueError, sqlite3.DatabaseError)):
                    IdleReadHolders(root)
                self.assertEqual(main.read_bytes(), before)

    def test_query_only_denies_real_dml_and_ddl(self):
        root, writers = self.make()
        holders = self.holders(root)
        for number, connection in enumerate(holders.connections):
            self.assertEqual(connection.execute('PRAGMA query_only').fetchone()[0], 1)
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute(INSERTS[number], (99,))
            with self.assertRaises(sqlite3.OperationalError):
                connection.execute('CREATE TABLE forbidden(value INTEGER)')
            self.assertFalse(connection.in_transaction)
            self.assertEqual(writers[number].execute('SELECT COUNT(*) FROM ' + TABLES[number]).fetchone()[0], 1)

    def test_partial_open_closes_all_and_owner_thread_controls_idempotent_cleanup(self):
        root, writers = self.make()
        for connection in writers:
            connection.close()
        bad = root / WARM_READS[1][0]
        bad.write_bytes(b'bad second database')
        original, captured = sqlite3.connect, []
        def capture(*args, **kwargs):
            connection = original(*args, **kwargs)
            captured.append(connection)
            return connection
        with patch('tools.managed_ro_anchor_prototype.sqlite3.connect', capture):
            with self.assertRaises(sqlite3.DatabaseError):
                IdleReadHolders(root)
        self.assertEqual(len(captured), 2)
        for connection in captured:
            with self.assertRaises(sqlite3.ProgrammingError):
                connection.execute('SELECT 1')
        second, _ = self.make()
        holders, errors = self.holders(second), []
        def wrong_thread():
            try:
                holders.close()
            except Exception as error:
                errors.append(error)
        thread = Thread(target=wrong_thread)
        thread.start()
        thread.join(1)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], RuntimeError)
        self.assertEqual(len(holders.connections), 3)
        holders.close()
        holders.close()
        self.assertEqual(holders.connections, [])


if __name__ == '__main__':
    unittest.main()
