from dataclasses import replace
from copy import deepcopy
import gzip
from hashlib import sha256
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from time import sleep
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from benchmarks.run_managed_benchmark import Configuration, observe_startup_ready, run, terminal_outcome
from uta.durable_process import DurableProcessRouter
from uta.service import ServiceError


class ManagedBenchmarkTests(unittest.TestCase):
    def diagnostic(self, reason="worker_unready"):
        return {"ready": reason == "ready", "financial_ready": reason == "ready",
                "reason": reason, "decision_audit_required": True,
                "workers": [{"reason": "ready", "report": {}}]}

    def test_startup_only_retries_known_observation_races_with_full_telemetry(self):
        reports = [self.diagnostic(), self.diagnostic("diagnostic_timeout"), self.diagnostic("ready")]
        router = SimpleNamespace(diagnostics=Mock(side_effect=reports))
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "startup.jsonl"
            report, metadata = observe_startup_ready(router, path, timeout=.2, interval=.001)
            rows = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual(report, reports[-1])
        self.assertEqual(metadata["observation_count"], 3)
        self.assertEqual([row["report"] for row in rows if row["event"] == "observation"], reports)
        self.assertEqual(rows[-1]["outcome"], "ready")
        self.assertGreater(metadata["elapsed_seconds"], 0)
        self.assertTrue(all(0 < call.kwargs["timeout"] <= .2 for call in router.diagnostics.call_args_list))

    def test_startup_fails_immediately_for_fatal_or_inconsistent_observations(self):
        fatal_reports = [self.diagnostic(reason) for reason in
                         ("market_stale", "market_future", "shard_unavailable", "storage_unavailable",
                          "fence_control_corrupt", "router_halted", "publication_incomplete")]
        audit = self.diagnostic("ready")
        audit["decision_audit_required"] = False
        masked = self.diagnostic("diagnostic_timeout")
        masked["workers"][0]["reason"] = "market_stale"
        failed_owner = self.diagnostic()
        failed_owner["workers"][0]["report"] = {"state": "failed", "code": "storage_unavailable"}
        inconsistent = self.diagnostic("ready")
        inconsistent["financial_ready"] = False
        fatal_reports.extend((audit, masked, failed_owner, inconsistent))
        with TemporaryDirectory() as temporary:
            for index, report in enumerate(fatal_reports):
                with self.subTest(report=report):
                    router = SimpleNamespace(diagnostics=Mock(return_value=report))
                    path = Path(temporary) / f"failure-{index}.jsonl"
                    with self.assertRaisesRegex(RuntimeError, "last complete diagnostic") as caught:
                        observe_startup_ready(router, path, timeout=.2, interval=.001)
                    router.diagnostics.assert_called_once()
                    self.assertIn(json.dumps(report, sort_keys=True), str(caught.exception))
                    rows = [json.loads(line) for line in path.read_text().splitlines()]
                    self.assertEqual(rows[1]["report"], report)
                    self.assertNotEqual(rows[-1]["outcome"], "ready")

    def test_startup_deadline_is_bounded_and_keeps_last_complete_report(self):
        report = self.diagnostic("diagnostic_timeout")
        router = SimpleNamespace(diagnostics=Mock(return_value=report))
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "deadline.jsonl"
            with self.assertRaisesRegex(RuntimeError, "deadline_exceeded") as caught:
                observe_startup_ready(router, path, timeout=.025, interval=.005)
            rows = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertIn(json.dumps(report, sort_keys=True), str(caught.exception))
        self.assertGreater(router.diagnostics.call_count, 0)
        self.assertEqual(rows[-1]["outcome"], "deadline_exceeded")
        self.assertEqual(rows[-2]["report"], report)
        self.assertTrue(all(0 < call.kwargs["timeout"] <= .025 for call in router.diagnostics.call_args_list))

    def test_startup_diagnostic_exception_is_not_silently_retried(self):
        router = SimpleNamespace(diagnostics=Mock(side_effect=ServiceError("storage_unavailable", "fault", 503)))
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "exception.jsonl"
            with self.assertRaisesRegex(RuntimeError, "diagnostic_exception"):
                observe_startup_ready(router, path, timeout=.2)
            rows = [json.loads(line) for line in path.read_text().splitlines()]
        router.diagnostics.assert_called_once()
        self.assertEqual(rows[1]["error_code"], "storage_unavailable")
        self.assertEqual(rows[-1]["outcome"], "diagnostic_exception")

    def test_startup_cannot_accept_a_ready_report_returning_after_total_deadline(self):
        report = self.diagnostic("ready")
        def late_diagnostic(**kwargs):
            sleep(.015)
            return report
        router = SimpleNamespace(diagnostics=Mock(side_effect=late_diagnostic))
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "late-ready.jsonl"
            with self.assertRaisesRegex(RuntimeError, "deadline_exceeded"):
                observe_startup_ready(router, path, timeout=.005)
            rows = [json.loads(line) for line in path.read_text().splitlines()]
        router.diagnostics.assert_called_once()
        self.assertTrue(rows[-2]["report"]["ready"])
        self.assertEqual(rows[-1]["outcome"], "deadline_exceeded")

    def test_bounds_reject_long_or_unbounded_component_capacity_claims(self):
        for values in ({"duration": 1800}, {"shards": 5}, {"accounts": 1, "shards": 2},
                       {"duration": float("nan")}, {"outstanding": True}, {"rate": 10000}, {"profile": 1}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                replace(Configuration(), **values).validate()

    def test_queued_ack_cannot_be_counted_as_financial_success(self):
        with self.assertRaisesRegex(ValueError, "not a financial terminal"):
            terminal_outcome({"state": "PENDING", "ack": "durably_queued", "result": None})
        self.assertEqual(terminal_outcome({"state": "QUARANTINED"}), "technical_quarantined")
        self.assertEqual(terminal_outcome({"state": "REJECTED", "error": {"code": "router_halted", "status": 503}}),
                         "control_or_market_rejected")
        self.assertEqual(terminal_outcome({"state": "REJECTED", "error": {"status": 409}}), "business_rejected")

    def inspect(self, directory, summary, expected, *, live=True):
        with gzip.open(directory / "arrivals.jsonl.gz", "rt") as stream:
            rows = [json.loads(line) for line in stream]
        self.assertEqual(len(rows), expected)
        self.assertEqual(len({row["command_id"] for row in rows}), expected)
        self.assertTrue(all(row["latency_ns"] == row["observed_completion_ns"] - row["planned_ns"] for row in rows))
        self.assertTrue(summary["readonly_reconciliation"]["reopened_readonly"])
        self.assertFalse(summary["production_approved"])
        self.assertFalse(summary["capacity_10000_per_s_passed"])
        self.assertTrue(summary["initial_real_pid_and_fence"]["decision_audit_required"])
        if live:
            self.assertEqual(sum(summary["outcome_counts"].values()), expected)
            startup = summary["startup_readiness_observation"]
            observations = [json.loads(line) for line in (directory / startup["observations_file"]).read_text().splitlines()]
            self.assertEqual(observations[-1]["outcome"], "ready")
            self.assertEqual(observations[-2]["report"], summary["initial_real_pid_and_fence"])
            self.assertGreaterEqual(rows[0]["planned_ns"], startup["finished_monotonic_ns"])
            self.assertLess(startup["elapsed_seconds"], startup["budget_seconds"])
        self.assertTrue(all((not live or row["pid"] != os.getpid()) and row["owner_pid"] == row["pid"] and row["lease_active"]
                            for row in summary["initial_real_pid_and_fence"]["workers"]))
        for name, proof in json.loads((directory / "manifest.json").read_text())["files"].items():
            data = (directory / name).read_bytes()
            self.assertEqual(sha256(data).hexdigest(), proof["sha256"])
        return rows

    def test_real_spawn_audited_commit_reject_and_per_pid_profile(self):
        with TemporaryDirectory() as temporary:
            directory = Path(temporary) / "managed"
            summary = run(Configuration(duration=.2, rate=10, accounts=2, shards=1, outstanding=4,
                inbox_capacity=4, reject_every=2, drain_seconds=5, profile=True), directory)
            rows = self.inspect(directory, summary, 2)
            self.assertEqual(summary["counts"].get("financial_succeeded"), 1)
            self.assertEqual(summary["counts"].get("business_rejected"), 1)
            self.assertEqual(summary["readonly_reconciliation"]["persistent_successes"], 1)
            self.assertEqual(summary["readonly_reconciliation"]["pending_count"], 0)
            self.assertEqual(set(summary["latency_ms"]["financial_succeeded"]), {"p50", "p95", "p99", "p99_9"})
            profiles = list((directory / "profiles").glob("worker-0-pid-*.prof"))
            self.assertEqual(len(profiles), 1)
            self.assertTrue(all(row["enqueue_ack_ns"] is not None for row in rows))
            self.assertLess(rows[0]["planned_ns"], rows[1]["planned_ns"])
            technical = summary["command_technical_diagnostics"]
            self.assertGreaterEqual(technical["stored_commands"], 4)
            self.assertGreater(technical["commands_by_kind"]["PUBLISH_MARKET"], 0)
            self.assertGreater(technical["commands_by_kind"]["SET_HALT"], 0)
            self.assertEqual(technical["internal_execution_attempts"], 0)
            self.assertTrue(summary["probe_qualification"]["passed"])

    def test_missing_enqueue_ack_queries_original_cid_and_preserves_error_count(self):
        original = DurableProcessRouter.submit_order
        def lost(router, *args, **kwargs):
            original(router, *args, **kwargs)
            raise ServiceError("storage_unavailable", "synthetic missing metadata response", 503)
        with TemporaryDirectory() as temporary, patch.object(DurableProcessRouter, "submit_order", lost):
            directory = Path(temporary) / "unknown-ack"
            summary = run(Configuration(duration=.1, rate=10, accounts=1, shards=1, reject_every=0,
                outstanding=2, inbox_capacity=2, drain_seconds=5), directory)
            rows = self.inspect(directory, summary, 1)
            self.assertEqual(summary["counts"]["durably_enqueued"], 0)
            self.assertEqual(summary["counts"]["enqueue_technical_errors"], 1)
            self.assertEqual(summary["counts"]["financial_succeeded"], 1)
            self.assertIsNone(rows[0]["enqueue_ack_ns"])
            self.assertEqual(rows[0]["receipt"]["command_id"], "bench:0")
            self.assertFalse(summary["probe_qualification"]["passed"])
            self.assertIn("enqueue_technical_error", summary["probe_qualification"]["reasons"])

    def test_real_pid_startup_observes_delayed_parent_ready_pipe_then_reconciles(self):
        entered, deliver = Event(), Event()
        original_supervise = DurableProcessRouter._supervise
        original_diagnostics = DurableProcessRouter.diagnostics
        held = []
        def delayed_monitor(router):
            entered.set()
            deliver.wait(10)
            original_supervise(router)
        def observe_and_deliver(router, **kwargs):
            report = original_diagnostics(router, **kwargs)
            if not deliver.is_set():
                self.assertTrue(entered.is_set())
                self.assertTrue(all(worker[2].poll() for worker in router._workers.values()))
                held.append(deepcopy(report))
                deliver.set()
            return report
        try:
            with TemporaryDirectory() as temporary, \
                    patch.object(DurableProcessRouter, "_supervise", delayed_monitor), \
                    patch.object(DurableProcessRouter, "diagnostics", observe_and_deliver):
                directory = Path(temporary) / "delayed-ready"
                summary = run(Configuration(duration=.1, rate=10, accounts=1, shards=1,
                    reject_every=0, outstanding=2, inbox_capacity=2, drain_seconds=5), directory)
                self.inspect(directory, summary, 1)
                startup = summary["startup_readiness_observation"]
                reports = [json.loads(line)["report"] for line in
                           (directory / startup["observations_file"]).read_text().splitlines()
                           if json.loads(line)["event"] == "observation"]
                self.assertGreaterEqual(len(reports), 2)
                self.assertEqual(reports[0], held[0])
                self.assertEqual(held[0]["reason"], "worker_unready")
                self.assertFalse(held[0]["ready"])
                worker = held[0]["workers"][0]
                self.assertFalse(worker["owner_ready"])
                self.assertTrue(worker["lease_active"] and worker["market_ready"] and worker["locally_active"])
                self.assertEqual(worker["pid"], worker["owner_pid"])
                self.assertNotEqual(worker["pid"], os.getpid())
                self.assertEqual(worker["pid"], reports[-1]["workers"][0]["pid"])
                self.assertEqual(worker["generation"], reports[-1]["workers"][0]["generation"])
                self.assertTrue(reports[-1]["ready"])
                self.assertEqual(summary["counts"].get("financial_succeeded"), 1)
                self.assertEqual(summary["readonly_reconciliation"]["persistent_successes"], 1)
        finally:
            deliver.set()

    def test_archived_real_probe_preserves_all_arrivals_and_known_profile_limits(self):
        root = Path(__file__).resolve().parents[1] / "benchmarks/results/20261116-managed-inbox-profile"
        directory = root / "raw"
        summary = json.loads((directory / "summary.json").read_text())
        self.assertEqual(summary["environment"]["code_commit"], "7a06c0532ba510653b1feccd7e80030d3cb19f8a")
        rows = self.inspect(directory, summary, 200, live=False)
        self.assertEqual(summary["counts"]["durably_enqueued"], 200)
        self.assertEqual(summary["counts"]["financial_succeeded"], 171)
        self.assertEqual(summary["counts"]["business_rejected"], 18)
        self.assertEqual(summary["counts"]["control_or_market_rejected"], 11)
        self.assertEqual(summary["readonly_reconciliation"]["pending_count"], 0)
        self.assertEqual(summary["readonly_reconciliation"]["unobserved_successes_found_on_reopen"], 0)
        self.assertEqual(sum(row["outcome"] == "financial_succeeded" for row in rows), 171)
        self.assertEqual(summary["poll_errors"][0]["sqlite_errorcode"], 522)
        self.assertEqual(summary["poll_errors"][0]["sqlite_errorname"], "SQLITE_IOERR_SHORT_READ")
        analysis = json.loads((root / "analysis.json").read_text())
        self.assertTrue(analysis["parent_profile_has_mixed_thread_frames"])
        self.assertEqual(len(analysis["profile_timing_anomalies"]["dispatcher-0.prof"]), 5)
        self.assertTrue(all(not value for name, value in analysis["profile_timing_anomalies"].items() if name.startswith("worker-")))


if __name__ == "__main__":
    unittest.main()
