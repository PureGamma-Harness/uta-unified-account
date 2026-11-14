from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import stat
import tempfile
import unittest
from unittest.mock import patch

from uta.ops import OperationsError, backup_database, check_database, main, restore_database


class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / "exchange #snapshot?.sqlite3"
        self.writer = sqlite3.connect(self.source)
        self.addCleanup(self.writer.close)
        self.writer.execute("PRAGMA journal_mode=WAL")
        self.writer.execute("PRAGMA foreign_keys=ON")
        self.writer.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)")
        self.writer.execute("CREATE TABLE detail (id INTEGER REFERENCES events(id))")
        self.writer.execute("INSERT INTO events VALUES (1, 'committed before backup')")
        self.writer.commit()

    def test_consistent_wal_snapshot_includes_committed_rows_and_excludes_uncommitted(self):
        self.writer.execute("INSERT INTO events VALUES (2, 'uncommitted')")
        target = self.root / "backup.sqlite3"
        result = backup_database(self.source, target)
        with sqlite3.connect(target) as connection:
            self.assertEqual(connection.execute("SELECT id FROM events").fetchall(), [(1,)])
            self.assertEqual(connection.execute("PRAGMA journal_mode").fetchone()[0], "delete")
        self.assertEqual(result["sha256"], hashlib.sha256(target.read_bytes()).hexdigest())
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        self.assertFalse(Path(str(target) + "-wal").exists())
        self.assertEqual(result["tables"], ["detail", "events"])

    def test_restore_to_new_path_and_check_without_mutating_rows(self):
        backup = self.root / "backup.sqlite3"
        backup_database(self.source, backup)
        restored = self.root / "restored.sqlite3"
        result = restore_database(backup, restored)
        self.assertEqual(result["operation"], "restore")
        self.assertTrue(result["requires_reconciliation"])
        before = restored.read_bytes()
        self.assertEqual(check_database(restored)["integrity"], "ok")
        self.assertEqual(restored.read_bytes(), before)
        with sqlite3.connect(restored) as connection:
            self.assertEqual(connection.execute("SELECT payload FROM events").fetchone()[0],
                             "committed before backup")

    def test_destination_and_sidecars_never_overwritten(self):
        target = self.root / "backup.sqlite3"
        target.write_bytes(b"existing-file")
        with self.assertRaises(OperationsError):
            backup_database(self.source, target)
        self.assertEqual(target.read_bytes(), b"existing-file")
        target.unlink()
        sidecar = Path(str(target) + "-wal")
        sidecar.write_bytes(b"live WAL")
        with self.assertRaises(OperationsError):
            restore_database(self.source, target)
        self.assertEqual(sidecar.read_bytes(), b"live WAL")
        self.assertFalse(target.exists())

    def test_missing_corrupt_empty_and_symlink_sources_are_rejected(self):
        missing = self.root / "missing.sqlite3"
        corrupt = self.root / "corrupt.sqlite3"
        corrupt.write_bytes(b"not a SQLite database")
        empty = self.root / "empty.sqlite3"
        empty.touch()
        link = self.root / "alias.sqlite3"
        link.symlink_to(self.source)
        for source in (missing, corrupt, empty, link):
            with self.subTest(source=source):
                with self.assertRaises(OperationsError):
                    check_database(source)
                with self.assertRaises(OperationsError):
                    backup_database(source, self.root / "output.sqlite3")
                self.assertFalse((self.root / "output.sqlite3").exists())
                self.assertEqual(list(self.root.glob(".uta-snapshot-*")), [])
        self.assertFalse(missing.exists())

    def test_foreign_key_violation_is_not_a_publishable_backup(self):
        self.writer.execute("PRAGMA foreign_keys=OFF")
        self.writer.execute("INSERT INTO detail VALUES (999)")
        self.writer.commit()
        with self.assertRaisesRegex(OperationsError, "foreign key"):
            check_database(self.source)
        output = self.root / "invalid.sqlite3"
        with self.assertRaisesRegex(OperationsError, "foreign key"):
            backup_database(self.source, output)
        self.assertFalse(output.exists())
        self.assertEqual(list(self.root.glob(".uta-snapshot-*")), [])

    def test_exclusive_publication_handles_concurrent_destination_creation(self):
        output = self.root / "backup.sqlite3"
        real_link = os.link

        def race(source, target):
            Path(target).write_bytes(b"created by another process")
            return real_link(source, target)

        with patch("uta.ops.os.link", side_effect=race):
            with self.assertRaises(OperationsError):
                backup_database(self.source, output)
        self.assertEqual(output.read_bytes(), b"created by another process")
        self.assertEqual(list(self.root.glob(".uta-snapshot-*")), [])

    def test_cli_outputs_parseable_report_and_nonzero_for_invalid_storage(self):
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["check", "--database", str(self.source)]), 0)
        self.assertEqual(json.loads(output.getvalue())["foreign_keys"], "ok")
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            main(["check", "--database", str(self.root / "missing")])
        self.assertEqual(raised.exception.code, 1)

    def test_invalid_timeouts_fail_before_creating_output(self):
        for timeout in (0, -1, float("nan"), float("inf"), True, 3601, "10"):
            with self.subTest(timeout=timeout):
                with self.assertRaises(OperationsError):
                    backup_database(self.source, self.root / "backup.sqlite3", timeout=timeout)


if __name__ == "__main__":
    unittest.main()
