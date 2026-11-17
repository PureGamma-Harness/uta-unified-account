"""Deterministic real SQLite writer ordering, without synthetic busy errors."""
import json
import sqlite3
from threading import Event, current_thread
from time import sleep
import unittest
from unittest.mock import patch

from tests import test_owned_startup as fixture
from uta.startup import StartupError
from uta.writer_fence import WriterFence


def describe_error(error):
    result, seen = [], set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        result.append(dict(type=type(error).__name__, code=getattr(error, "code", None),
            message=str(error), sqlite_errorcode=getattr(error, "sqlite_errorcode", None),
            sqlite_errorname=getattr(error, "sqlite_errorname", None)))
        error = error.__cause__ if error.__cause__ is not None else error.__context__
    return result


class StartupWriteContentionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.OwnedStartupTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_own_short_financial_writer_does_not_poison_live_startup_renewal(self):
        initialization = self.fixture.context()
        held, requested = Event(), Event()
        original = WriterFence.renew
        phases = dict(entered=False, constructed=False, writer_held=False,
                      renewal_requested=False, finished=False)
        def observe(fence, token, ttl):
            if current_thread().name == "uta-startup-lease" and held.is_set():
                requested.set()
            return original(fence, token, ttl)
        failure = None
        try:
            with patch.object(WriterFence, "renew", observe):
                with initialization:
                    phases["entered"] = True
                    self.fixture.construct(initialization)
                    phases["constructed"] = True
                    initialization.check()
                    # A real owned financial BEGIN IMMEDIATE retains the writer
                    # lock through COMMIT. The pause is >.4/12 busy wait, but
                    # comfortably below the unchanged .4-second lease.
                    with self.fixture.bound.transaction() as conn:
                        conn.execute("UPDATE uta_schema SET version=version")
                        held.set()
                        phases["writer_held"] = True
                        self.assertTrue(requested.wait(.3), "keeper did not actually request renewal")
                        phases["renewal_requested"] = True
                        sleep(.08)
                    held.clear()
                    initialization.finish()
                    phases["finished"] = initialization._finished
        except BaseException as error:
            failure = error
        evidence = dict(phases=phases, error=describe_error(failure),
                        keeper_error=describe_error(initialization._failure))
        self.assertIsNone(failure, json.dumps(evidence, sort_keys=True))
        self.assertEqual(phases, dict(entered=True, constructed=True, writer_held=True,
                                     renewal_requested=True, finished=True))
        self.assertTrue(self.fixture.fence.status()["active"])
        with self.fixture.database.read_transaction() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM ledger_events").fetchone()[0], 0)
            self.assertGreaterEqual(conn.execute("SELECT COUNT(*) FROM writer_fence_events WHERE kind='renewed'").fetchone()[0], 2)

    def test_uncoordinated_producer_writer_busy_is_still_technical_poison(self):
        initialization = self.fixture.context()
        held, requested = Event(), Event()
        original = WriterFence.renew
        def observe(fence, token, ttl):
            if current_thread().name == "uta-startup-lease" and held.is_set():
                requested.set()
            return original(fence, token, ttl)
        with patch.object(WriterFence, "renew", observe):
            with self.assertRaises(StartupError) as rejected:
                with initialization:
                    self.fixture.construct(initialization)
                    initialization.check()
                    # The separate producer role is not an owned financial actor.
                    # Do not retry or hide its genuine SQLite contention.
                    with self.fixture.database.inbox_transaction():
                        held.set()
                        self.assertTrue(requested.wait(.3))
                        sleep(.08)
                    held.clear()
                    initialization.finish()
        self.assertEqual(rejected.exception.code, "startup_keeper_failed", describe_error(rejected.exception))
        self.assertIsInstance(rejected.exception.__cause__, sqlite3.OperationalError)
        self.assertIn("locked", str(rejected.exception.__cause__))
        self.assertFalse(initialization._finished)


if __name__ == "__main__":
    unittest.main()
