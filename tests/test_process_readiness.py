"""Readiness must observe actual persistent prices, even with live child PIDs."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Thread
from time import monotonic, sleep
import unittest
from unittest.mock import patch

import test_readiness_sampling as readiness_fixtures

from uta import durable_process
from uta.durable_process import DurableProcessRouter
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ServiceError
from uta.writer_fence import WriterFence


def _readiness_failure_message(report):
    """Finite existing-result projection; identifiers and arbitrary text stay out."""
    try:
        if type(report) is not dict:
            return '{"diagnostic_projection_failed":true}'
        codes = {"not_observed", "observed", "ready", "market_stale", "market_future",
                 "worker_unready", "local_halt", "supervisor_unavailable",
                 "publication_incomplete", "router_halted", "diagnostic_timeout",
                 "diagnostic_unavailable", "managed_authority_conflict",
                 "decision_audit_capability_mismatch", "market_missing", "market_invalid",
                 "market_barrier_mismatch", "market_fanout_incomplete", "halt_fanout_incomplete",
                 "shard_unavailable", "lease_expired", "writer_fenced"}
        def code(value):
            return value if type(value) is str and value in codes else "other"
        def flag(value):
            return value if type(value) is bool else None
        rows = report.get("workers")
        rows = rows if type(rows) in (list, tuple) else ()
        selected = [row for row in rows[:2] if type(row) is dict]
        reasons = {}
        for row in selected:
            reason = code(row.get("reason"))
            reasons[reason] = reasons.get(reason, 0) + 1
        gates = {}
        for key in ("alive", "lease_active", "market_ready", "owner_ready",
                    "locally_active", "funding_registry_ready"):
            gates[key] = dict(true=sum(row.get(key) is True for row in selected),
                              false=sum(row.get(key) is False for row in selected),
                              unknown=sum(type(row.get(key)) is not bool for row in selected))
        state = report.get("state")
        state = state if type(state) is dict else {}
        return json.dumps(dict(reason=code(report.get("reason")),
            flags={key: flag(report.get(key)) for key in
                   ("ready", "financial_ready", "workers_alive", "supervisor_alive", "state_observed")},
            control={key: flag(state.get(key)) for key in ("halted", "publishing")},
            control_error=None if state.get("error") is None else code(state.get("error")),
            worker_reasons=reasons, worker_gate_counts=gates,
            worker_rows_included=len(selected), worker_rows_truncated=len(rows) > 2), sort_keys=True)
    except BaseException:
        return '{"diagnostic_projection_failed":true}'


class ProcessReadinessTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "authority"
        self.initialize()

    def initialize(self, *, decision_audit=True):
        def bootstrap(router):
            router.create_account("customer")
            router.deposit("customer", "synthetic-bootstrap", "USD", D(100))
        self.router = DurableProcessRouter.initialize(
            self.path, 2, {"USD": 8}, managed=True, bootstrap=bootstrap,
            max_price_age=timedelta(seconds=2), lease_seconds=1,
            poll_interval=.01, background_interval=.03, decision_audit=decision_audit)
        self.addCleanup(self.router.close)

    def development_fault_profile(self):
        # Required history guards intentionally forbid malformed price writes.
        # Keep those guards intact; use an explicit development authority solely
        # to inject persistent price faults, still under a valid offline token.
        self.router.close()
        self.path = self.path.parent / "development-fault-profile"
        self.initialize(decision_audit=False)

    def market(self, version=1, *, observed_at=None, mark="100"):
        return MarketSnapshot(version, observed_at or datetime.now(timezone.utc),
                              {"USD": AssetSpec(D(1), D(1))},
                              {"X": InstrumentSpec(D(mark), D(".1"), D(".05"))})

    def eventually(self, predicate):
        deadline = monotonic() + 8
        while monotonic() < deadline:
            value = predicate()
            if value:
                return value
            sleep(.02)
        self.fail("real process readiness did not reach the expected state")

    def wait_ready(self):
        return readiness_fixtures.ReadinessSamplingTests.wait_ready(self, self.router)

    def observe_market_rejection(self, reason):
        return readiness_fixtures.ReadinessSamplingTests.observe_market_rejection(self, self.router, reason)

    def activate(self, snapshot=None):
        if self.router._monitor is None:
            self.router.start()
        # Explicit snapshots retain their exact SID/time/content; only a new
        # default quote is created after the real worker start call.
        snapshot = snapshot or self.market()
        self.assertFalse(self.router.publish_market(snapshot, timeout=8)["publishing"])
        self.assertFalse(self.router.set_kill_switch(False, timeout=8)["halted"])
        self.wait_ready()
        return snapshot

    def payload(self, shard):
        with self.router._database(shard).read_transaction() as connection:
            row = connection.execute("SELECT payload FROM uta_market WHERE singleton=1").fetchone()
            return row[0] if row else None

    def offline_fault(self, payload):
        """Inject corruption with an explicit offline test owner, never a stolen token."""
        self.router.close()
        database = self.router._database(0)
        fence = WriterFence(database)
        token = fence.acquire("test:readiness-fault", 5)
        try:
            with database.for_writer(token).transaction() as connection:
                if payload is None:
                    connection.execute("DELETE FROM uta_market WHERE singleton=1")
                else:
                    connection.execute("UPDATE uta_market SET payload=? WHERE singleton=1", (payload,))
        finally:
            fence.release(token)

    def test_healthy_real_workers_and_read_only_original_observation(self):
        snapshot = self.activate()
        original = [self.payload(shard) for shard in range(2)]
        with patch("uta.sharding.ExchangeService", side_effect=AssertionError("financial constructor called")):
            with patch("uta.storage.Database._connect", side_effect=AssertionError("read changed WAL mode")):
                result = self.router.diagnostics()
        self.assertTrue(result["ready"], result)
        self.assertTrue(result["financial_ready"])
        self.assertTrue(result["workers_alive"])
        self.assertEqual({row["pid"] for row in result["workers"]},
                         {self.router.worker_pid(0), self.router.worker_pid(1)})
        self.assertNotIn(os.getpid(), {row["pid"] for row in result["workers"]})
        self.assertTrue(all(row["market_observed_at"] == snapshot.observed_at.isoformat()
                            and row["market_ready"] and row["owner_ready"] for row in result["workers"]))
        self.assertEqual([self.payload(shard) for shard in range(2)], original)
        self.assertNotIn(str(self.path), json.dumps(result))

    def test_actual_expiration_keeps_workers_alive_and_new_price_recovers(self):
        snapshot = self.activate()
        wait = (snapshot.observed_at + timedelta(seconds=2) - datetime.now(timezone.utc)).total_seconds()
        sleep(max(0, wait) + .04)
        result = self.observe_market_rejection("market_stale")
        self.assertTrue(result["workers_alive"], result)
        self.assertIs(result["financial_ready"], False, result)
        self.assertIs(result["ready"], False, result)
        self.assertEqual([row["reason"] for row in result["workers"]], ["market_stale"] * 2)
        self.assertEqual([self.payload(shard) for shard in range(2)], [snapshot.to_json()] * 2)
        self.activate(self.market(2, mark="101"))
        self.assertIs(self.wait_ready()["ready"], True)

    def test_clock_rollback_detects_future_without_relabeling_prices(self):
        snapshot = self.activate()
        class EarlierClock(datetime):
            @classmethod
            def now(cls, tz=None):
                return snapshot.observed_at - timedelta(seconds=2)
        with patch.object(durable_process, "datetime", EarlierClock):
            result = self.observe_market_rejection("market_future")
            self.assertEqual([self.payload(shard) for shard in range(2)], [snapshot.to_json()] * 2)
        self.assertTrue(result["workers_alive"], result)
        self.assertIs(result["ready"], False, result)
        self.assertEqual([row["reason"] for row in result["workers"]], ["market_future"] * 2)
        self.assertEqual([self.payload(shard) for shard in range(2)], [snapshot.to_json()] * 2)
        # The original quote may age during a real bounded observation. Keep
        # its bytes intact, then recover with a distinct current generation.
        self.activate(self.market(snapshot.version + 1))
        self.assertIs(self.wait_ready()["ready"], True)

    def test_same_version_changed_persistent_content_is_not_reused(self):
        self.development_fault_profile()
        original = self.activate()
        changed = self.market(observed_at=original.observed_at, mark="101")
        self.offline_fault(changed.to_json())
        self.router.start()
        result = self.router.diagnostics()
        self.assertFalse(result["ready"], result)
        self.assertEqual(result["workers"][0]["reason"], "market_barrier_mismatch")
        self.assertEqual(self.payload(0), changed.to_json())
        self.activate(self.market(2, mark="102"))
        recovered = self.router.diagnostics()
        self.assertTrue(recovered["financial_ready"], _readiness_failure_message(recovered))

    def test_malformed_missing_and_oversize_persistent_quotes_fail_closed(self):
        self.development_fault_profile()
        self.activate()
        for payload, expected in (("{broken", "market_invalid"), (None, "market_missing"),
                                  (" " * (1024 * 1024 + 1), "market_invalid")):
            with self.subTest(expected=expected, missing=payload is None):
                # Restore the singleton before each independent offline fault.
                self.offline_fault(payload)
                self.router.start()
                result = self.router.diagnostics()
                self.assertFalse(result["ready"], result)
                self.assertEqual(result["workers"][0]["reason"], expected)
                if payload is None:
                    self.router.close()
                    database = self.router._database(0)
                    fence = WriterFence(database)
                    token = fence.acquire("test:restore-singleton", 5)
                    try:
                        with database.for_writer(token).transaction() as connection:
                            connection.execute("INSERT INTO uta_market VALUES (1,?)", (self.market().to_json(),))
                    finally:
                        fence.release(token)

    def test_partial_fanout_is_unready_until_exact_generation_finishes(self):
        fence = WriterFence(self.router._database(1))
        token = fence.acquire("test:blocked-shard", 5)
        try:
            self.router.start()
            snapshot = self.market()
            self.assertTrue(self.router.publish_market(snapshot, timeout=.25)["publishing"])
            result = self.router.diagnostics()
            self.assertFalse(result["ready"], result)
            self.assertEqual(result["reason"], "publication_incomplete")
        finally:
            fence.release(token)
        self.activate(snapshot)
        final = self.router.diagnostics()
        message = None if final["ready"] else _readiness_failure_message(final)
        self.assertTrue(final["ready"], message)

    def test_gate_and_mutex_observations_have_one_bounded_timeout(self):
        self.activate()
        with self.router._control._lock(exclusive=True):
            started = monotonic()
            result = self.router.diagnostics(timeout=.05)
            self.assertLess(monotonic() - started, .5)
            self.assertFalse(result["ready"])
            self.assertFalse(result["state_observed"])
            self.assertIsNone(result["state"])
        entered, release = Event(), Event()
        def locked_supervisor():
            with self.router._mutex:
                entered.set()
                release.wait(2)
        thread = Thread(target=locked_supervisor)
        thread.start()
        try:
            self.assertTrue(entered.wait(2))
            started = monotonic()
            result = self.router.diagnostics(timeout=.05)
            self.assertLess(monotonic() - started, .5)
            self.assertFalse(result["ready"])
            self.assertEqual(result["reason"], "diagnostic_timeout")
        finally:
            release.set()
            thread.join(timeout=2)

    def test_guard_sql_is_interrupted_and_exception_details_are_redacted(self):
        self.activate()
        original = durable_process._diagnostic_claims
        def expensive_claims(connection, control, deadline):
            # Real SQLite VM work, interrupted by the shared deadline handler.
            connection.execute("WITH RECURSIVE n(x) AS (VALUES(0) UNION ALL SELECT x+1 FROM n WHERE x<100000000) SELECT sum(x) FROM n").fetchone()
            return original(connection, control, deadline)
        with patch.object(durable_process, "_diagnostic_claims", expensive_claims):
            started = monotonic()
            result = self.router.diagnostics(timeout=.05)
            self.assertLess(monotonic() - started, .5)
            self.assertFalse(result["ready"])
            self.assertEqual(result["reason"], "diagnostic_timeout")
        with patch.object(durable_process, "_diagnostic_claims", side_effect=OSError(str(self.path) + "/secret")):
            result = self.router.diagnostics()
        self.assertFalse(result["ready"])
        self.assertNotIn(str(self.path), json.dumps(result))
        self.assertTrue(self.router.diagnostics()["ready"])

    def test_freshness_is_checked_after_last_shard_and_slow_claim_work(self):
        snapshot = self.activate()
        original = durable_process._diagnostic_market
        class ExpiredAtEnd(datetime):
            @classmethod
            def now(cls, tz=None):
                return snapshot.observed_at + timedelta(seconds=3 if len(calls) == 2 else 0)
        calls = []
        def read_market(connection, state, deadline):
            value = original(connection, state, deadline)
            calls.append(value[0].version)
            return value
        with patch.object(durable_process, "_diagnostic_market", read_market):
            with patch.object(durable_process, "datetime", ExpiredAtEnd):
                result = self.router.diagnostics()
        self.assertEqual(calls, [1, 1])
        self.assertFalse(result["ready"], result)
        self.assertEqual([row["reason"] for row in result["workers"]], ["market_stale"] * 2)

    def test_read_guard_failure_after_payload_cannot_report_ready(self):
        self.activate()
        original = durable_process._DiagnosticDatabase.read_transaction
        @contextmanager
        def guard_fails_at_exit(database):
            with original(database) as connection:
                yield connection
                if database.path.endswith("shard-0000.sqlite3"):
                    raise RuntimeError(str(self.path) + "/private-guard-detail")
        with patch.object(durable_process._DiagnosticDatabase, "read_transaction", guard_fails_at_exit):
            result = self.router.diagnostics()
        self.assertFalse(result["ready"], result)
        self.assertFalse(result["workers"][0]["market_ready"])
        self.assertNotIn(str(self.path), json.dumps(result))

    def test_incomplete_watermarks_and_invalid_control_flags_are_unready(self):
        self.activate()
        self.router.close()  # Corrupt metadata offline without noisy child crashes.
        with self.router._control._lock(exclusive=True):
            original = self.router._control._state()
            self.router._control._write_state({**original, "watermarks": {"0": 1}})
            # Reentrant lock acquisition is deliberately not attempted here;
            # release EX before diagnosis, while preserving test restoration.
        try:
            result = self.router.diagnostics()
            self.assertFalse(result["ready"], result)
            self.assertEqual(result["reason"], "publication_incomplete")
            for fault in ({"halted": "invalid"}, {"market_transition_pending": 1},
                          {"watermarks": {str(self.path): 1}},
                          {"market_version": None, "market_digest": str(self.path)}):
                with self.subTest(fault=list(fault)):
                    with self.router._control._lock(exclusive=True):
                        self.router._control._write_state(dict(original))
                        if "halted" in fault or "market_transition_pending" in fault:
                            # Normal control writers must keep rejecting bad
                            # flags. Corrupt only this closed test authority's
                            # storage to exercise the independent read path.
                            with self.assertRaises(ServiceError) as rejected:
                                self.router._control._write_state({**original, **fault})
                            self.assertEqual(rejected.exception.code, "control_corruption")
                            self.assertEqual(self.router._control._state(), original)
                        with self.router._control.control.transaction() as connection:
                            connection.execute("UPDATE router_state SET payload=? WHERE singleton=1",
                                (json.dumps({**original, **fault}, sort_keys=True,
                                            separators=(",", ":"), allow_nan=False),))
                    result = self.router.diagnostics()
                    self.assertFalse(result["ready"], result)
                    self.assertFalse(result["state_observed"])
                    self.assertIsNone(result["state"])
                    self.assertEqual(result["reason"], "control_corruption")
                    self.assertNotIn(str(self.path), json.dumps(result))
        finally:
            with self.router._control._lock(exclusive=True):
                self.router._control._write_state(original)

    def test_diagnostic_timeout_rejects_unsafe_inputs(self):
        for timeout in (True, 0, -1, 6, float("inf"), float("nan"), "1", None):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                self.router.diagnostics(timeout=timeout)


if __name__ == "__main__":
    unittest.main()
