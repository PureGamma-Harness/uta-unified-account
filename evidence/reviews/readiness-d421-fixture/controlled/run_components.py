"""Two explicit controlled component rounds; real temporary workers/SQL only.

No existing job path is opened. No report, exception, lease or snapshot is
fabricated. Test controls delay actual observations or hold owned fixture gates.
"""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import signal
import sys
from threading import Event
from time import monotonic
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import test_readiness_sampling as sampling
import test_process_readiness as process
from uta import durable_process

EVENTS = []

def record(kind, **value):
    EVENTS.append({"kind": kind, "monotonic": monotonic(), **value})

def capture(router):
    original = router.diagnostics
    def observed(*args, **kwargs):
        report = original(*args, **kwargs)
        record("actual_diagnostic", report=report)
        return report
    router.diagnostics = observed


class ExpiredPartialGeneration(sampling.ReadinessSamplingTests):
    def test_controlled_original_sampling(self):
        original = sampling.DurableProcessRouter.publish_market
        injected = []
        def completed_after_expiry(router, snapshot, **kwargs):
            result = original(router, snapshot, **kwargs)
            record("actual_publication_return", snapshot_json=snapshot.to_json(), publication=result)
            if snapshot.version == 1 and not result["publishing"] and not injected:
                self.assertTrue(all(receipt is not None and receipt["state"] == "SUCCEEDED"
                                    for receipt in result["receipts"].values()), result)
                injected.append(snapshot.to_json())
                expiry = snapshot.observed_at + timedelta(seconds=1.06)
                Event().wait(max(0, (expiry-datetime.now(timezone.utc)).total_seconds()))
                record("actual_completed_SID1_delayed_beyond_original_TTL", snapshot_json=snapshot.to_json(), original_observed_at=snapshot.observed_at.isoformat())
            return result
        original_diagnostics = sampling.DurableProcessRouter.diagnostics
        def witnessed(router, *args, **kwargs):
            report = original_diagnostics(router, *args, **kwargs)
            record("actual_sampling_diagnostic", report=report)
            return report
        try:
            with patch.object(sampling.DurableProcessRouter, "publish_market", completed_after_expiry), \
                    patch.object(sampling.DurableProcessRouter, "diagnostics", witnessed):
                self.test_bounded_eventual_observation_cannot_pass_partial_or_actual_stale_quotes()
            self.assertEqual(len(injected), 1)
        finally:
            if hasattr(self, "initial_native_owner"):
                record("actual_prequote_owner_witness", **self.initial_native_owner)


class PartialStaleRead(process.ProcessReadinessTests):
    def setUp(self):
        super().setUp()
        self.control_snapshot = None
        self.delayed = False
        self.stale_reads = 0
        capture(self.router)

    def activate(self, *args, **kwargs):
        snapshot = super().activate(*args, **kwargs)
        self.control_snapshot = snapshot
        return snapshot

    def test_controlled_original_actual_expiration(self):
        original = durable_process._diagnostic_market
        def delay_real_second_read(connection, state, deadline):
            value = original(connection, state, deadline)
            if (self.control_snapshot is not None and not self.delayed
                    and datetime.now(timezone.utc) > self.control_snapshot.observed_at + timedelta(seconds=2)):
                self.stale_reads += 1
                if self.stale_reads == 2:
                    self.delayed = True
                    Event().wait(max(0, deadline-monotonic()) + .015)
                    record("actual_second_shard_read_crossed_original_deadline", deadline=deadline, snapshot_json=self.control_snapshot.to_json())
            return value
        with patch.object(durable_process, "_diagnostic_market", delay_real_second_read):
            self.test_actual_expiration_keeps_workers_alive_and_new_price_recovers()
        self.assertTrue(self.delayed)


class RestoredClockContention(process.ProcessReadinessTests):
    def test_controlled_original_clock_rollback(self):
        original = self.router.diagnostics
        future_seen, contended = [], []
        def contend_original_restore(*args, **kwargs):
            if future_seen and durable_process.datetime is datetime and not contended:
                contended.append(True)
                with self.router._control._lock(exclusive=True):
                    report = original(*args, **kwargs)
                record("actual_restored_clock_control_gate_timeout", report=report)
            else:
                report = original(*args, **kwargs)
            if durable_process.datetime is not datetime and report["reason"] == "market_future":
                future_seen.append(True)
            record("actual_diagnostic", report=report)
            return report
        with patch.object(self.router, "diagnostics", contend_original_restore):
            self.test_clock_rollback_detects_future_without_relabeling_prices()
        self.assertTrue(future_seen)
        self.assertEqual(contended, [True])


def main():
    os.sched_setaffinity(0, {2})
    stage = sys.argv[1]
    def watchdog(signum, frame):
        raise TimeoutError("owned component observation watchdog expired")
    signal.signal(signal.SIGALRM, watchdog)
    signal.alarm(8 if stage == "sampling-native-frame" else 29)
    output = Path(__file__).parent/stage
    output.mkdir()
    paths = ["tests/test_readiness_sampling.py", "tests/test_process_readiness.py", "uta/durable_process.py"]
    source = {name: sha256((ROOT/name).read_bytes()).hexdigest() for name in paths}
    cases = [
        ExpiredPartialGeneration("test_controlled_original_sampling"),
        PartialStaleRead("test_controlled_original_actual_expiration"),
        RestoredClockContention("test_controlled_original_clock_rollback"),
        sampling.ReadinessSamplingTests("test_market_probe_never_promotes_persistently_unknown_native_owners"),
        sampling.ReadinessSamplingTests("test_market_probe_rejects_a_real_expired_owner_lease_without_retry"),
    ]
    # The original extra gate-only control already passed. The restored-clock
    # control exercises that gate again; retain only persistent unknown/native
    # inactive controls in the final narrow round.
    if stage == "original-red":
        cases.append(sampling.ReadinessSamplingTests("test_successful_activation_does_not_force_a_contended_observation_true"))
    if stage == "sampling-native-frame":
        cases = [cases[0]]
    suite = unittest.TestSuite(cases)
    t0 = monotonic()
    with (output/"unittest.txt").open("w") as log:
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    after = {name: sha256((ROOT/name).read_bytes()).hexdigest() for name in paths}
    assert source == after
    value = {"stage": stage, "python": sys.version, "cpu_ids": sorted(os.sched_getaffinity(0)),
        "wall_seconds": monotonic()-t0, "tests_run": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
        "passed": result.wasSuccessful(), "source_before": source, "source_after": after,
        "events": EVENTS, "no_existing_job_or_live_SQL": True, "temporary_component_only": True,
        "runtime_TTL_timeout_snapshot_content_not_relaxed": True,
        "unique_historical_cause_proven": False, "production_approved": False}
    (output/"summary.json").write_text(json.dumps(value, indent=2)+"\n")
    signal.alarm(0)
    print(json.dumps({k:value[k] for k in ("stage", "tests_run", "failures", "errors", "wall_seconds", "passed")},indent=2))
    return not result.wasSuccessful()


if __name__ == "__main__":
    raise SystemExit(main())
