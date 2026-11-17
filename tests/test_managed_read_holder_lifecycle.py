"""Holder lifecycle on real temp control SQLite; server calls are explicit stubs."""
import json
from pathlib import Path
import sqlite3
import ssl
from tempfile import TemporaryDirectory
from threading import Event
import unittest
from unittest.mock import patch

from benchmarks.managed_read_holders import IdleReadHolders, WARM_READS
from benchmarks.run_managed_soak import Configuration, ManagedSoak
from uta.storage import Database


class PassiveControlFixture(ManagedSoak):
    """No bootstrap/server/business verification; an already-stopped unit fixture."""
    def __init__(self, root):
        self.directory = root
        self.configuration = Configuration(duration=4, worker_every=0, parent_every=0, min_free_bytes=0)
        self.stop = Event()
        self.stop.set()
        self.strict_source, self.validation = False, None
        self.process = self.listener = self.stderr = self.lock = self.read_holders = None
        self.tls = ssl.create_default_context()
        self.checkpoint = Database(root / 'checkpoint.sqlite3')
        self.financial = root / 'managed/shard-0000.sqlite3'
        self.stages, self.observed_connections = [], []
        self.start_error = self.drain_error = None
        self.meta = {'validation_evidence': None, 'file_identities': {str(path): [path.stat().st_dev, path.stat().st_ino]
            for path in [root / relative for relative, _ in WARM_READS] + [root / 'private/auth.sqlite3']}}

    def _start_server(self):
        self.stages.append('start_stub')
        assert self.read_holders is not None and len(self.read_holders.connections) == 3
        assert self._state('started_boottime_ns') is None
        self.observed_connections = list(self.read_holders.connections)
        if self.start_error:
            raise self.start_error

    def _stop_server(self, **_):
        self.stages.append('drain_stub')
        if self.read_holders is not None:
            assert all(not connection.in_transaction for connection in self.read_holders.connections)
        if self.drain_error:
            raise self.drain_error

    def status(self, *args, **kwargs):
        self.stages.append('before_real_status')
        if self.read_holders is not None:
            assert len(self.read_holders.connections) == 3
        result = super().status(*args, **kwargs)
        assert json.loads((self.directory / 'progress.json').read_text()) == result
        self.stages.append('after_real_progress_publication')
        return result


class ManagedReadHolderLifecycleTests(unittest.TestCase):
    def make(self):
        temporary = TemporaryDirectory(prefix='uta-holder-lifecycle-')
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        for relative, schema in [
            ('checkpoint.sqlite3', '''CREATE TABLE state(key TEXT PRIMARY KEY,value TEXT);
                CREATE TABLE rounds(sequence INTEGER PRIMARY KEY,planned_ns INTEGER,state TEXT,completed_ns INTEGER);
                CREATE TABLE steps(round INTEGER,name TEXT,state TEXT,plan TEXT);
                CREATE TABLE faults(round INTEGER,kind TEXT,state TEXT,evidence TEXT);
                CREATE TABLE events(sequence INTEGER PRIMARY KEY,kind TEXT,payload TEXT,previous_hash TEXT,event_hash TEXT);
                INSERT INTO state VALUES('fixture','true');
                INSERT INTO rounds VALUES(1,0,'ACTIVE',NULL);'''),
            ('managed/router.sqlite3', 'CREATE TABLE router_layout(singleton INTEGER); INSERT INTO router_layout VALUES(1);'),
            ('managed/shard-0000.sqlite3', 'CREATE TABLE ledger_events(sequence INTEGER); INSERT INTO ledger_events VALUES(1);'),
            ('private/auth.sqlite3', 'CREATE TABLE fixture_only(value INTEGER);')]:
            path = root / relative
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            connection = sqlite3.connect(path, isolation_level=None)
            try:
                path.chmod(0o600)
                connection.execute('PRAGMA journal_mode=WAL')
                connection.executescript(schema)
            finally:
                connection.close()
        fixture = PassiveControlFixture(root)
        self.addCleanup(fixture.close)
        return fixture

    def assert_connections_closed(self, connections):
        for connection in connections:
            with self.assertRaises(sqlite3.ProgrammingError):
                connection.execute('SELECT 1')

    def test_run_keeps_holders_through_real_progress_then_closes_without_changing_flags(self):
        fixture = self.make()
        report = fixture.run()
        self.assertEqual(report['status'], 'paused')
        self.assertEqual(fixture.stages, ['start_stub', 'drain_stub', 'before_real_status', 'after_real_progress_publication'])
        self.assertTrue(report['logs_verified'])
        self.assertLess(report['elapsed_seconds'], 4)
        self.assertFalse(report['continuous_6h_stability_passed'])
        self.assertFalse(report['production_approved'])
        self.assertIsNone(fixture.read_holders)
        self.assert_connections_closed(fixture.observed_connections)

    def test_start_failure_retains_original_error_and_holders_until_drain_and_progress(self):
        fixture = self.make()
        fixture.start_error = RuntimeError('original start failure')
        report = fixture.run()
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['error'], {'type': 'RuntimeError', 'message': 'original start failure'})
        self.assertEqual(fixture.stages[-1], 'after_real_progress_publication')
        self.assertIsNone(fixture.read_holders)
        self.assert_connections_closed(fixture.observed_connections)

    def test_original_metadata_mismatch_fails_before_server_and_closes_partial_holders(self):
        fixture = self.make()
        path = fixture.directory / 'managed/router.sqlite3'
        fixture.meta['file_identities'][str(path)][1] += 1
        original, captured = sqlite3.connect, []
        def capture(*args, **kwargs):
            connection = original(*args, **kwargs)
            if '?mode=ro' in str(args[0]) and 'checkpoint.sqlite3' in str(args[0]):
                captured.append(connection)
            return connection
        with patch('benchmarks.managed_read_holders.sqlite3.connect', capture):
            report = fixture.run()
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['error']['type'], 'ValueError')
        self.assertNotIn('start_stub', fixture.stages)
        self.assertIsNone(fixture.read_holders)
        self.assertTrue(captured)
        self.assert_connections_closed(captured)

    def test_constructor_failure_never_opens_holders_before_initialization(self):
        with TemporaryDirectory(prefix='uta-holder-init-failure-') as directory:
            failure = RuntimeError('original initialization failure')
            with patch('benchmarks.run_managed_soak.environment', return_value={'source_sha256': {}}), \
                    patch.object(ManagedSoak, '_initialize', side_effect=failure), \
                    patch('benchmarks.run_managed_soak.IdleReadHolders', side_effect=AssertionError('premature holder')) as holders:
                with self.assertRaises(RuntimeError) as caught:
                    ManagedSoak(Path(directory) / 'job', Configuration(duration=4), strict_source=False)
            self.assertIs(caught.exception, failure)
            holders.assert_not_called()

    def test_close_still_closes_real_holders_when_drain_raises(self):
        fixture = self.make()
        fixture.read_holders = IdleReadHolders(fixture.directory, expected_identities=fixture.meta['file_identities'])
        connections = list(fixture.read_holders.connections)
        fixture.process = object()  # Only selects close's drain branch; no actual process exists.
        failure = RuntimeError('original drain failure')
        fixture.drain_error = failure
        with self.assertRaises(RuntimeError) as caught:
            fixture.close()
        self.assertIs(caught.exception, failure)
        self.assertIsNone(fixture.read_holders)
        self.assert_connections_closed(connections)
        fixture.process, fixture.drain_error = None, None
