"""Temporary-file resource races only; no service or pre-existing authority."""
from dataclasses import replace
import errno
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from benchmarks.run_managed_soak import Configuration, ManagedSoak


DATABASES = ('checkpoint.sqlite3', 'managed/router.sqlite3',
             'managed/shard-0000.sqlite3', 'private/auth.sqlite3')
TEMPORARIES = ('bootstrap-plan.json.tmp', 'job.json.tmp', 'progress.json.tmp',
               'pending-market.json.tmp', 'log-segments.json.tmp', 'private/signing.json.tmp',
               'logs/events-000000001-000000256.jsonl.tmp')


class ManagedSoakResourceTests(unittest.TestCase):
    def make(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        for name in DATABASES:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b'main')
        return SimpleNamespace(directory=root, configuration=Configuration(min_free_bytes=0))

    def remove_after_discovery(self, job, target):
        original = os.walk
        def entries(path, *args, **kwargs):
            found = list(original(path, *args, **kwargs))
            if Path(path) == job.directory:
                self.assertTrue(any(target == Path(root) / name
                    for root, directories, files in found for name in directories + files))
                target.unlink()
            return iter(found)
        return patch.object(os, 'walk', entries)

    def test_real_sqlite_last_close_between_first_stat_and_size_does_not_abort(self):
        job = self.make()
        database = job.directory / 'managed/shard-0000.sqlite3'
        database.unlink()
        connection = sqlite3.connect(database)
        self.addCleanup(connection.close)
        self.assertEqual(connection.execute('PRAGMA journal_mode=WAL').fetchone()[0], 'wal')
        connection.execute('CREATE TABLE synthetic(value INTEGER)')
        connection.execute('INSERT INTO synthetic VALUES(1)')
        connection.commit()
        wal = database.with_name(database.name + '-wal')
        self.assertTrue(wal.exists())
        original_stat, calls = Path.stat, []
        def disappearing(path, *args, **kwargs):
            details = original_stat(path, *args, **kwargs)
            if path == wal:
                calls.append(path)
                connection.close()  # Real SQLite checkpoint/removal, never unlink an active DB.
            return details
        with patch.object(Path, 'stat', disappearing):
            report = ManagedSoak._resources(job)
        self.assertEqual(calls, [wal])
        self.assertFalse(wal.exists())
        self.assertFalse(report['budget_exceeded'])
        self.assertGreaterEqual(report['directory_bytes'], 4 * len(b'main'))

    def test_all_known_sidecars_may_disappear_after_discovery(self):
        for database in DATABASES:
            for suffix in ('-wal', '-shm'):
                with self.subTest(database=database, suffix=suffix):
                    job = self.make()
                    target = job.directory / (database + suffix)
                    target.write_bytes(b'transient')
                    with self.remove_after_discovery(job, target):
                        report = ManagedSoak._resources(job)
                    self.assertEqual(report['directory_bytes'], 4 * len(b'main'))

    def test_known_atomic_temporary_removal_is_bounded_to_exact_publishers(self):
        for name in TEMPORARIES:
            with self.subTest(name=name):
                job = self.make()
                target = job.directory / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b'transient')
                with self.remove_after_discovery(job, target):
                    self.assertEqual(ManagedSoak._resources(job)['directory_bytes'], 16)

    def test_main_disappearance_after_discovery_is_fatal(self):
        for name in DATABASES:
            with self.subTest(name=name):
                job = self.make()
                target = job.directory / name
                with self.remove_after_discovery(job, target), self.assertRaises(FileNotFoundError):
                    ManagedSoak._resources(job)

    def test_missing_required_main_before_discovery_is_fatal(self):
        for name in DATABASES:
            with self.subTest(name=name):
                job = self.make()
                (job.directory / name).unlink()
                with self.assertRaises(FileNotFoundError):
                    ManagedSoak._resources(job)

    def test_required_main_replaced_with_directory_is_fatal(self):
        job = self.make()
        target = job.directory / 'managed/shard-0000.sqlite3'
        target.unlink()
        target.mkdir()
        with self.assertRaisesRegex(RuntimeError, 'required managed database'):
            ManagedSoak._resources(job)

    def test_required_main_direct_or_dangling_symlink_is_fatal(self):
        for dangling in (False, True):
            with self.subTest(dangling=dangling):
                job = self.make()
                target = job.directory / 'managed/shard-0000.sqlite3'
                replacement = job.directory / 'replacement.dat'
                if not dangling:
                    replacement.write_bytes(b'not the required main')
                target.unlink()
                target.symlink_to(replacement)
                with self.assertRaisesRegex(RuntimeError, 'required managed database'):
                    ManagedSoak._resources(job)

    def test_dangling_auxiliary_and_atomic_temporary_symlinks_are_not_followed(self):
        job = self.make()
        for name in ('managed/shard-0000.sqlite3-wal', 'progress.json.tmp'):
            (job.directory / name).symlink_to(job.directory / 'absent-target')
        report = ManagedSoak._resources(job)
        self.assertEqual(report['directory_bytes'], 16)
        self.assertFalse(report['budget_exceeded'])

    def test_initialization_failure_is_preserved_before_required_databases_exist(self):
        with TemporaryDirectory() as directory:
            target = Path(directory) / 'job'
            failure = RuntimeError('original initialization failure')
            with patch('benchmarks.run_managed_soak.environment', return_value={'source_sha256': {}}), \
                    patch.object(ManagedSoak, '_initialize', side_effect=failure), \
                    patch.object(ManagedSoak, '_resources', side_effect=AssertionError('premature metric')) as metric:
                with self.assertRaises(RuntimeError) as caught:
                    ManagedSoak(target, Configuration(duration=4), strict_source=False)
            self.assertIs(caught.exception, failure)
            metric.assert_not_called()
            self.assertFalse((target / 'checkpoint.sqlite3').exists())

    def test_unrelated_missing_files_are_not_sidecar_or_temporary_exemptions(self):
        for name in ('unrelated.sqlite3-wal', 'unrelated.tmp',
                     'logs/unrelated.jsonl.tmp', 'managed/other.sqlite3-shm', 'progress.json'):
            with self.subTest(name=name):
                job = self.make()
                target = job.directory / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b'required')
                with self.remove_after_discovery(job, target), self.assertRaises(FileNotFoundError):
                    ManagedSoak._resources(job)

    def test_permission_and_other_io_failures_are_not_ignored_for_aux_or_main(self):
        for name in ('managed/shard-0000.sqlite3', 'managed/shard-0000.sqlite3-wal'):
            for error in (PermissionError(errno.EACCES, 'denied'), OSError(errno.EIO, 'I/O failure')):
                with self.subTest(name=name, errno=error.errno):
                    job = self.make()
                    target = job.directory / name
                    target.touch()
                    original = Path.stat
                    def failing(path, *args, **kwargs):
                        if path == target:
                            raise error
                        return original(path, *args, **kwargs)
                    with patch.object(Path, 'stat', failing), self.assertRaises(type(error)) as caught:
                        ManagedSoak._resources(job)
                    self.assertEqual(caught.exception.errno, error.errno)

    def test_directory_enumeration_permission_and_io_failures_are_fatal(self):
        for error in (PermissionError(errno.EACCES, 'directory denied'), OSError(errno.EIO, 'directory I/O')):
            with self.subTest(errno=error.errno):
                job = self.make()
                target = job.directory / 'managed'
                original = os.scandir
                def failing(path):
                    if Path(path) == target:
                        raise error
                    return original(path)
                with patch.object(os, 'scandir', failing), self.assertRaises(type(error)) as caught:
                    ManagedSoak._resources(job)
                self.assertEqual(caught.exception.errno, error.errno)

    def test_surviving_auxiliary_and_temporary_bytes_still_exhaust_original_budgets(self):
        job = self.make()
        total = 16
        for name in [database + suffix for database in DATABASES for suffix in ('-wal', '-shm')] + list(TEMPORARIES):
            target = job.directory / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b'auxiliary')
            total += len(b'auxiliary')
        report = ManagedSoak._resources(job)
        self.assertEqual(report['directory_bytes'], total)
        self.assertFalse(report['budget_exceeded'])
        job.configuration = replace(job.configuration, min_free_bytes=10**30)
        self.assertTrue(ManagedSoak._resources(job)['budget_exceeded'])
        job.configuration = replace(job.configuration, min_free_bytes=0, max_directory_bytes=1024**2)
        (job.directory / 'large.log').write_bytes(b'x' * (1024**2 + 1))
        self.assertTrue(ManagedSoak._resources(job)['budget_exceeded'])


if __name__ == '__main__':
    unittest.main()
