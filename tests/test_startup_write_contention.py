"""Deterministic real SQLite writer ordering, without synthetic busy errors."""
import json
import sqlite3
from collections import deque
from decimal import Decimal
from pathlib import Path
from threading import Event, current_thread
from time import monotonic, monotonic_ns, sleep
import unittest
from unittest.mock import patch

from tests import test_owned_startup as fixture
from uta.startup import StartupError
from uta.service import ExchangeService
from uta.storage import Database
from uta.writer_fence import WriterFence, WriterFenceError


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
        if self._testMethodName == "test_uncoordinated_producer_writer_busy_is_still_technical_poison":
            # This negative tests external SQLite BUSY after healthy setup,
            # using the real production-default lease from FIRST acquisition.
            self.fixture._lease_seconds = 5.0
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_own_short_financial_writer_does_not_poison_live_startup_renewal(self):
        initialization = self.fixture.context()
        held, requested = Event(), Event()
        original = WriterFence.renew
        phases = dict(entered=False, constructed=False, writer_held=False,
                      renewal_requested=False, finished=False)
        timeline_limit = 64
        timeline = deque(maxlen=timeline_limit)
        timeline_capacity_reached = timeline_failed = False
        timeline_snapshot_failure = dict(events=[], limit=timeline_limit,
            capacity_reached=None, truncated=True, collection_failed=True, snapshot_failed=True,
            retention="bounded tail in append order; snapshot unavailable",
            semantics="test observation overhead; no exact loss count, lease-clock or commit attestation")
        def mark(stage, error=None):
            nonlocal timeline_capacity_reached, timeline_failed
            try:
                observed = monotonic_ns()
                if type(observed) is not int or not 0 <= observed <= 2**63 - 1:
                    timeline_failed = True
                    return
                item = dict(stage=stage, monotonic_ns=observed)
                if error is not None:
                    kind = ("startup_error" if type(error) is StartupError else
                            "writer_fence_error" if type(error) is WriterFenceError else
                            "sqlite_operational_error" if type(error) is sqlite3.OperationalError else "other")
                    code = error.code if type(error) in (StartupError, WriterFenceError) else None
                    item.update(error_type=kind, error_code=code if code in {
                        "startup_keeper_failed", "lease_expired", "writer_fenced",
                        "startup_write_gate_timeout", "initialization_in_progress",
                        "fence_clock_regressed", "startup_keeper_stuck", "startup_cancelled",
                        "startup_deadline"} else "other")
                timeline.append(item)
                if len(timeline) == timeline_limit:
                    timeline_capacity_reached = True
            except BaseException:
                timeline_failed = True  # Observation must not replace the original result.
        def snapshot_timeline():
            nonlocal timeline_failed
            try:
                events = list(timeline)
                capacity_reached = timeline_capacity_reached or len(events) == timeline_limit
                return dict(events=events, limit=timeline_limit,
                    capacity_reached=capacity_reached, truncated=capacity_reached or timeline_failed,
                    collection_failed=timeline_failed, snapshot_failed=False,
                    retention="bounded tail in append order; capacity means possible truncation",
                    semantics="test observation overhead; no exact loss count, lease-clock or commit attestation")
            except BaseException:
                timeline_failed = True
                return timeline_snapshot_failure
        def observe(fence, token, ttl):
            mark("renew_request")
            if current_thread().name == "uta-startup-lease" and held.is_set():
                requested.set()
                mark("held_renewal_requested")
            try:
                result = original(fence, token, ttl)
            except BaseException as error:
                mark("renew_raise", error)
                raise
            mark("renew_return")
            return result
        failure = None
        try:
            with patch.object(WriterFence, "renew", observe):
                mark("enter_before")
                with initialization:
                    phases["entered"] = True
                    mark("enter_return")
                    mark("construct_before")
                    self.fixture.construct(initialization)
                    phases["constructed"] = True
                    mark("construct_return")
                    initialization.check()
                    # A real owned financial BEGIN IMMEDIATE retains the writer
                    # lock through COMMIT. The pause is >.4/12 busy wait, but
                    # comfortably below the unchanged .4-second lease.
                    mark("writer_before")
                    with self.fixture.bound.transaction() as conn:
                        mark("writer_body_enter")
                        conn.execute("UPDATE uta_schema SET version=version")
                        held.set()
                        phases["writer_held"] = True
                        mark("writer_held")
                        self.assertTrue(requested.wait(.3), "keeper did not actually request renewal")
                        phases["renewal_requested"] = True
                        mark("requested_wait_return")
                        sleep(.08)
                        mark("sleep_return")
                    held.clear()
                    mark("writer_return_and_held_cleared")
                    mark("finish_before")
                    initialization.finish()
                    phases["finished"] = initialization._finished
                    mark("finish_return")
        except BaseException as error:
            failure = error
            mark("main_raise", error)
        evidence = dict(phases=phases, error=describe_error(failure),
                        keeper_error=describe_error(initialization._failure),
                        timeline=snapshot_timeline())
        self.assertIsNone(failure, json.dumps(evidence, sort_keys=True))
        self.assertEqual(phases, dict(entered=True, constructed=True, writer_held=True,
                                     renewal_requested=True, finished=True))
        self.assertTrue(self.fixture.fence.status()["active"])
        with self.fixture.database.read_transaction() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM ledger_events").fetchone()[0], 0)
            self.assertGreaterEqual(conn.execute("SELECT COUNT(*) FROM writer_fence_events WHERE kind='renewed'").fetchone()[0], 2)

    def test_uncoordinated_producer_writer_busy_is_still_technical_poison(self):
        initialization = self.fixture.context()
        held, requested, failed = Event(), Event(), Event()
        original = WriterFence.renew
        original_failure = initialization._fail
        attempts = []
        def observe(fence, token, ttl):
            if current_thread().name == "uta-startup-lease" and held.is_set():
                attempts.append((ttl, fence.database.timeout))
                requested.set()
            return original(fence, token, ttl)
        def observe_failure(error):
            original_failure(error)  # Store the genuine error before observation.
            failed.set()
        with self.fixture.database.read_transaction() as conn:
            acquired = list(conn.execute("SELECT expires_ns-observed_ns FROM writer_fence_events WHERE kind='acquired'"))
        self.assertEqual([row[0] for row in acquired], [5_000_000_000])
        self.assertEqual(initialization.lease_seconds, 5.0)
        with patch.object(WriterFence, "renew", observe), patch.object(initialization, "_fail", observe_failure):
            initialization.__enter__()
            try:
                self.fixture.construct(initialization)
                initialization.check()
                # The separate producer role is not an owned financial actor.
                # Do not retry or hide its genuine SQLite contention.
                with self.fixture.database.inbox_transaction():
                    held_since = monotonic()
                    held.set()
                    # The real five-second keeper loop can wait up to TTL/3.
                    # This is an observation budget, not a lease extension.
                    self.assertTrue(requested.wait(2.5), "keeper did not request the actual producer contention")
                    sleep(.2)  # Beyond the unchanged production .1s busy wait.
                    self.assertTrue(failed.wait(1), "actual keeper failure was not observed while the writer remained held")
                    self.assertGreaterEqual(monotonic() - held_since, .2)
                held.clear()
                with self.assertRaises(StartupError) as rejected:
                    initialization.finish()
            finally:
                initialization._cleanup()
        self.assertEqual(rejected.exception.code, "startup_keeper_failed", describe_error(rejected.exception))
        self.assertIsInstance(rejected.exception.__cause__, sqlite3.OperationalError)
        self.assertIn("locked", str(rejected.exception.__cause__))
        self.assertTrue(attempts)
        self.assertTrue(all(ttl == 5.0 and busy == .1 for ttl, busy in attempts), attempts)
        self.assertFalse(initialization._finished)

    def test_owned_financial_writer_past_actual_expiry_still_rolls_back(self):
        initialization = self.fixture.context()
        initialization.__enter__()
        try:
            self.fixture.construct(initialization)
            initialization.check()
            with self.assertRaises(WriterFenceError) as expired:
                with self.fixture.bound.transaction() as conn:
                    conn.execute("INSERT INTO startup_fk_parent VALUES (11)")
                    sleep(.55)  # Beyond the unchanged .4-second current lease.
            self.assertEqual(expired.exception.code, "lease_expired")
            with self.assertRaises((StartupError, WriterFenceError)) as rejected:
                initialization.finish()
            self.assertIn(rejected.exception.code, ("startup_keeper_failed", "lease_expired"),
                          describe_error(rejected.exception))
            self.assertFalse(initialization._finished)
        finally:
            initialization._cleanup()
        with self.fixture.database.read_transaction() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM startup_fk_parent WHERE id=11").fetchone()[0], 0)
        self.assertFalse(self.fixture.fence.status()["active"])

    def test_an_unrelated_new_authority_keeps_its_normal_financial_path(self):
        with self.fixture.context() as initialization:
            self.fixture.construct(initialization)
            other = ExchangeService(Database(Path(self.fixture.tmp.name) / "other.sqlite3"), {"USD": 2})
            other.create_account("independent")
            other.deposit("independent", "synthetic-funding", "USD", Decimal(10))
            self.assertEqual(other.account("independent")["balances"]["USD"], "10")
            initialization.finish()
        with self.fixture.database.read_transaction() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM ledger_events").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
