"""Deterministic readiness observations; successful control is not a cached ACK.

Only the parent monitor's scheduling is controlled. Real spawned owners acquire
their own PID tokens, initialize, renew and execute market/activation commands.
The production readiness predicates and timeouts are left unchanged.
"""
from contextlib import closing
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import fcntl
import json
import os
from pathlib import Path
import select
import signal
import sqlite3
from tempfile import TemporaryDirectory
from threading import Event
from time import monotonic, sleep
import unittest
from unittest.mock import patch

import test_durable_faults as fault_fixtures
from uta import durable_process
from uta.durable_process import DurableProcessRouter
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.writer_fence import WriterFence


class ReadinessSamplingTests(unittest.TestCase):
    def original_fixture(self):
        fixture = fault_fixtures.ManagedProcessFaultTests(
            "test_real_worker_quarantines_persisted_poison_and_then_processes_same_account_cancel")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        return fixture

    def wait_ready(self, router, *, timeout=1):
        deadline, samples = monotonic() + timeout, []
        while monotonic() < deadline:
            report = router.diagnostics(timeout=min(.1, max(.001, deadline - monotonic())))
            samples.append(report)
            if report["ready"]:
                self.assertIs(report["ready"], True, report)
                self.assertIs(report["financial_ready"], True, report)
                return report
            self.assertIs(report["ready"], False, report)
            self.assertIs(report["financial_ready"], False, report)
            inactive = [row for row in report["workers"]
                        if row["generation"] is not None and row["owner_pid"] == row["pid"]
                        and row["owner_pid"] is not None and not row["lease_active"]]
            self.assertFalse(inactive, "observed inactive native lease: " + json.dumps(report, sort_keys=True))
            if report.get("reason") not in {"worker_unready", "diagnostic_timeout"}:
                self.fail("non-transient readiness observation: " + json.dumps(report, sort_keys=True))
            sleep(min(.01, max(0, deadline - monotonic())))
        self.fail("readiness did not become true within the observation budget: " + json.dumps(samples, sort_keys=True))

    def observe_market_rejection(self, router, reason, *, timeout=1):
        deadline = monotonic() + timeout
        self.market_observations = []
        while monotonic() < deadline:
            report = router.diagnostics(timeout=min(.1, max(.001, deadline - monotonic())))
            self.market_observations.append(report)
            message = json.dumps(report, sort_keys=True)
            self.assertIs(report["ready"], False, message)
            self.assertIs(report["financial_ready"], False, message)
            inactive = [row for row in report["workers"]
                        if row["generation"] is not None and not row["lease_active"]]
            self.assertFalse(inactive, "observed inactive native lease: " + message)
            for row in report["workers"]:
                if row["generation"] is None:
                    self.assertIs(row["owner_ready"], False, message)
                    self.assertIs(row["lease_active"], False, message)
                else:
                    self.assertTrue(row["alive"], message)
                    self.assertEqual(row["pid"], row["owner_pid"], message)
                    self.assertEqual(row["report"].get("state"), "ready", message)
                    self.assertEqual(row["report"].get("pid"), row["owner_pid"], message)
                    self.assertEqual(row["report"].get("generation"), row["generation"], message)
            if all(row["owner_ready"] and row["funding_registry_ready"] for row in report["workers"]):
                self.assertTrue(all(row["lease_active"] for row in report["workers"]), message)
                self.assertEqual([row["reason"] for row in report["workers"]], [reason] * len(report["workers"]), message)
                return report
            transient = (report["reason"] == "diagnostic_timeout"
                         or report["reason"] == reason and any(row["reason"] == "diagnostic_timeout"
                                                               for row in report["workers"]))
            self.assertTrue(transient, "non-transient incomplete owner observation: " + message)
            sleep(min(.01, max(0, deadline - monotonic())))
        self.fail("complete owner observation budget exhausted: " + json.dumps(self.market_observations, sort_keys=True))

    def test_real_activation_precedes_parent_ready_pipe_consumption(self):
        fixture = self.original_fixture()
        router = fixture.router
        monitor_entered, deliver = Event(), Event()
        original_supervise = router._supervise
        def delayed_pipe_observation():
            monitor_entered.set()
            deliver.wait(3)
            original_supervise()
        try:
            with patch.object(router, "_supervise", delayed_pipe_observation):
                router.start()
            self.assertTrue(monitor_entered.wait(1))
            publication = router.publish_market(fixture.market(), timeout=10)
            self.assertFalse(publication["publishing"])
            activation = router.set_kill_switch(False, timeout=10)
            self.assertFalse(activation["halted"])
            self.assertTrue(all(worker[2].poll() for worker in router._workers.values()),
                            "actual READY frames must already be queued in both child pipes")
            self.held_observation = router.diagnostics()
            report = self.held_observation
            self.assertFalse(report["ready"], report)
            self.assertFalse(report["financial_ready"])
            self.assertEqual(report["reason"], "worker_unready")
            self.assertTrue(report["workers_alive"])
            self.assertFalse(report["state"]["halted"])
            self.assertFalse(report["state"]["publishing"])
            for row in report["workers"]:
                self.assertEqual(row["pid"], row["owner_pid"])
                self.assertTrue(row["lease_active"])
                self.assertTrue(row["locally_active"])
                self.assertTrue(row["market_ready"])
                self.assertTrue(row["funding_registry_ready"])
                self.assertEqual(row["report"], {})
                self.assertFalse(row["owner_ready"])
        finally:
            deliver.set()
        self.delivered_observation = self.wait_ready(router)
        self.assertTrue(all(row["owner_ready"] and row["report"].get("state") == "ready"
                            for row in self.delivered_observation["workers"]))
        self.assertEqual([row["generation"] for row in report["workers"]],
                         [row["generation"] for row in self.delivered_observation["workers"]])
        self.assertEqual([row["pid"] for row in report["workers"]],
                         [row["pid"] for row in self.delivered_observation["workers"]])

    def test_delivered_ready_frames_cannot_override_future_or_stale_market(self):
        fixture = self.original_fixture()
        fixture.active()
        router = fixture.router
        self.wait_ready(router)
        with router._database(0).read_transaction() as connection:
            snapshot = MarketSnapshot.from_json(connection.execute("SELECT payload FROM uta_market WHERE singleton=1").fetchone()[0])
        for offset, reason in ((-2, "market_future"), (61, "market_stale")):
            class ShiftedClock(datetime):
                @classmethod
                def now(cls, tz=None):
                    return snapshot.observed_at + timedelta(seconds=offset)
            with self.subTest(reason=reason), patch.object(durable_process, "datetime", ShiftedClock):
                self.observe_market_rejection(router, reason)
        restored = self.wait_ready(router)
        self.assertTrue(restored["ready"])
        self.assertTrue(all(row["owner_ready"] and row["lease_active"] for row in restored["workers"]))

    def test_market_probe_observes_actual_control_timeout_before_complete_owner_sample(self):
        fixture = self.original_fixture()
        fixture.active()
        router = fixture.router
        self.wait_ready(router)
        with router._database(0).read_transaction() as connection:
            snapshot = MarketSnapshot.from_json(connection.execute("SELECT payload FROM uta_market WHERE singleton=1").fetchone()[0])
        class ShiftedClock(datetime):
            @classmethod
            def now(cls, tz=None):
                return snapshot.observed_at - timedelta(seconds=2)
        original, observations = router.diagnostics, []
        def contend_once(*args, **kwargs):
            if not observations:
                with router._control._lock(exclusive=True):
                    report = original(*args, **kwargs)
            else:
                report = original(*args, **kwargs)
            observations.append(report)
            return report
        with patch.object(durable_process, "datetime", ShiftedClock), \
             patch.object(router, "diagnostics", side_effect=contend_once):
            report = self.observe_market_rejection(router, "market_future")
        self.assertGreaterEqual(len(observations), 2)
        unknown = observations[0]
        self.assertEqual(unknown["reason"], "diagnostic_timeout", unknown)
        self.assertFalse(unknown["state_observed"])
        self.assertFalse(unknown["ready"])
        self.assertFalse(unknown["financial_ready"])
        self.assertTrue(all(row["generation"] is None and not row["lease_active"]
                            and not row["owner_ready"] for row in unknown["workers"]))
        self.assertTrue(all(row["lease_active"] and row["owner_ready"] for row in report["workers"]))

    def test_market_probe_never_promotes_persistently_unknown_native_owners(self):
        fixture = self.original_fixture()
        fixture.active()
        router = fixture.router
        self.wait_ready(router)
        with router._control._lock(exclusive=True):
            with self.assertRaisesRegex(AssertionError, "complete owner observation"):
                self.observe_market_rejection(router, "market_future", timeout=.15)
        self.assertTrue(self.market_observations)
        for report in self.market_observations:
            self.assertEqual(report["reason"], "diagnostic_timeout", report)
            self.assertFalse(report["ready"])
            self.assertFalse(report["financial_ready"])
            self.assertTrue(all(row["generation"] is None and not row["lease_active"]
                                and not row["owner_ready"] for row in report["workers"]))

    def test_market_probe_rejects_a_real_expired_owner_lease_without_retry(self):
        fixture = self.original_fixture()
        fixture.active()
        router = fixture.router
        self.wait_ready(router)
        pid = router.worker_pid(0)
        protected = {4471, 8784, 122905, 122907, 123007, 123009}
        self.assertNotIn(pid, protected)
        self.assertTrue(router._workers[0][0].is_alive())
        def birth():
            return (Path("/proc") / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()[19]
        original_birth = birth()
        pidfd = os.pidfd_open(pid)
        paused = False
        try:
            self.assertEqual(birth(), original_birth)
            print("owned-lease-control " + json.dumps({"pid": pid, "birth": original_birth,
                                                       "pidfd_bound": True, "fixture_only": True}), flush=True)
            # As in the original fixture helper: stop only while our gate and
            # SQLite writer are free. A pidfd binds both signals to this owner.
            gate = os.open(fixture.path / "router.lock", os.O_RDWR)
            try:
                fcntl.flock(gate, fcntl.LOCK_EX)
                with closing(sqlite3.connect(fixture.shard_path(0), timeout=5, isolation_level=None)) as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    try:
                        self.assertEqual(router.worker_pid(0), pid)
                        self.assertEqual(birth(), original_birth)
                        signal.pidfd_send_signal(pidfd, signal.SIGSTOP)
                        paused = True
                    finally:
                        connection.rollback()
            finally:
                os.close(gate)
            deadline, expired = monotonic() + 2, None
            while monotonic() < deadline:
                report = router.diagnostics(timeout=.1)
                if any(row["owner_pid"] == pid and row["generation"] is not None
                       and not row["lease_active"] for row in report["workers"]):
                    expired = report
                    break
                sleep(.01)
            self.assertIsNotNone(expired, "native lease did not expire within its unchanged TTL")
            self.assertFalse(expired["ready"])
            self.assertFalse(expired["financial_ready"])
            original = router.diagnostics
            with patch.object(router, "diagnostics", wraps=original) as observed:
                with self.assertRaisesRegex(AssertionError, "observed inactive native lease"):
                    self.observe_market_rejection(router, "market_future")
            self.assertEqual(observed.call_count, 1)
            self.assertTrue(any(row["owner_pid"] == pid and not row["owner_ready"]
                                and not row["lease_active"] for row in self.market_observations[0]["workers"]))
        finally:
            try:
                if paused:
                    terminal = select.poll()
                    terminal.register(pidfd, select.POLLIN)
                    if terminal.poll(0):
                        print("owned-lease-cleanup " + json.dumps({"pid": pid, "birth": original_birth,
                            "outcome": "bound_old_owner_exited", "resume_sent": False}), flush=True)
                    else:
                        try:
                            observed_birth = birth()
                        except OSError:
                            self.assertTrue(terminal.poll(0), "old owner exit is not proven by bound pidfd")
                            print("owned-lease-cleanup " + json.dumps({"pid": pid, "birth": original_birth,
                                "outcome": "bound_old_owner_exited", "resume_sent": False}), flush=True)
                        else:
                            self.assertEqual(observed_birth, original_birth)
                            try:
                                signal.pidfd_send_signal(pidfd, signal.SIGCONT)
                            except ProcessLookupError:
                                self.assertTrue(terminal.poll(0), "old owner exit is not proven by bound pidfd")
                                print("owned-lease-cleanup " + json.dumps({"pid": pid, "birth": original_birth,
                                    "outcome": "bound_old_owner_exited", "resume_sent": False}), flush=True)
                            else:
                                print("owned-lease-cleanup " + json.dumps({"pid": pid, "birth": original_birth,
                                    "outcome": "same_bound_owner_resumed", "resume_sent": True}), flush=True)
            finally:
                os.close(pidfd)

    def test_successful_activation_does_not_force_a_contended_observation_true(self):
        fixture = self.original_fixture()
        fixture.active()
        router = fixture.router
        self.wait_ready(router)
        with router._control._lock(exclusive=True):
            report = router.diagnostics(timeout=.02)
        self.assertFalse(report["ready"])
        self.assertEqual(report["reason"], "diagnostic_timeout")
        self.assertFalse(report["state_observed"])
        self.assertIsNone(report["state"])
        self.assertTrue(self.wait_ready(router)["ready"])

    def test_bounded_eventual_observation_cannot_pass_partial_or_actual_stale_quotes(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        router = DurableProcessRouter.initialize(Path(temporary.name) / "router", 2, {"USD": 8},
            managed=True, max_price_age=timedelta(seconds=1), lease_seconds=1,
            poll_interval=.01, background_interval=.05)
        self.addCleanup(router.close)
        def market(version):
            return MarketSnapshot(version, datetime.now(timezone.utc), {"USD": AssetSpec(D(1), D(1))},
                                  {"X": InstrumentSpec(D(100), D(".1"), D(".05"))})
        fence = WriterFence(router._database(1))
        token = fence.acquire("sampling:external-owner", 5)
        try:
            router.start()
            # Warm the unblocked native owner before starting the one-second quote
            # clock. Shard1 remains deliberately owned by the original test fence.
            deadline, initialized = monotonic() + 1, None
            while monotonic() < deadline:
                # Do not repeatedly acquire the diagnostic SQL/router gate
                # while the actual child is still importing and initializing.
                with router._mutex:
                    ready_frame = router._reports.get(0, {}).get("state") == "ready"
                if not ready_frame:
                    sleep(.01)
                    continue
                report = router.diagnostics(timeout=min(.1, max(.001, deadline-monotonic())))
                self.assertIs(report["ready"], False, report)
                self.assertIs(report["financial_ready"], False, report)
                row = report["workers"][0]
                if row["owner_pid"] is not None and row["owner_pid"] == row["pid"]:
                    self.assertTrue(row["lease_active"], "observed inactive native lease: " + json.dumps(report))
                if row["owner_ready"]:
                    self.assertTrue(row["lease_active"], report)
                    self.assertEqual(row["report"].get("state"), "ready", report)
                    self.assertEqual(row["pid"], row["owner_pid"], report)
                    self.assertEqual(row["report"].get("generation"), row["generation"], report)
                    with router._mutex:
                        process = router._workers[0][0]
                        self.assertTrue(process.is_alive(), report)
                        self.assertEqual(process.pid, row["owner_pid"], report)
                        owner_birth = (Path("/proc") / str(process.pid) / "stat").read_text().rsplit(")", 1)[1].split()[19]
                    self.initial_native_owner = {"pid": process.pid, "birth_ticks": owner_birth,
                        "generation": row["generation"], "witness_utc": datetime.now(timezone.utc).isoformat()}
                    initialized = report
                    break
                self.assertIn(row["reason"], {"market_missing", "diagnostic_timeout", "not_observed"}, report)
                sleep(.01)
            self.assertIsNotNone(initialized, "unblocked native owner did not initialize within one second")
            snapshot = market(1)
            self.assertGreaterEqual(snapshot.observed_at.isoformat(), self.initial_native_owner["witness_utc"])
            self.assertEqual(router.worker_pid(0), self.initial_native_owner["pid"])
            self.assertEqual((Path("/proc") / str(self.initial_native_owner["pid"]) / "stat").read_text().rsplit(")", 1)[1].split()[19],
                             self.initial_native_owner["birth_ticks"])
            self.assertTrue(router.publish_market(snapshot, timeout=.1)["publishing"])
            with self.assertRaises(AssertionError) as caught:
                self.wait_ready(router, timeout=.1)
            self.assertIn("publication_incomplete", str(caught.exception))
        finally:
            fence.release(token)
        publication = router.publish_market(snapshot, timeout=10)
        self.assertFalse(publication["publishing"], publication)
        self.assertTrue(all(receipt is not None and receipt["state"] == "SUCCEEDED"
                            for receipt in publication["receipts"].values()), publication)
        for shard in range(2):
            with router._database(shard).read_transaction() as connection:
                self.assertEqual(connection.execute("SELECT payload FROM uta_market WHERE singleton=1").fetchone()[0],
                                 snapshot.to_json())
        # SID1 is complete, even if its original timestamp is now stale. A new
        # current generation supplies the separate activation precondition.
        current = market(2)
        self.assertFalse(router.publish_market(current, timeout=10)["publishing"])
        self.assertFalse(router.set_kill_switch(False, timeout=10)["halted"])
        self.wait_ready(router)
        sleep(max(0, (current.observed_at + timedelta(seconds=1) - datetime.now(timezone.utc)).total_seconds()) + .03)
        with self.assertRaises(AssertionError) as caught:
            self.wait_ready(router, timeout=.1)
        self.assertIn("market_stale", str(caught.exception))
        self.assertFalse(router.publish_market(market(3), timeout=10)["publishing"])
        self.assertFalse(router.set_kill_switch(False, timeout=10)["halted"])
        self.assertTrue(self.wait_ready(router)["ready"])


if __name__ == "__main__":
    unittest.main()
