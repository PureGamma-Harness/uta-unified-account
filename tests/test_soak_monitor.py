import gzip
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
import unittest
from unittest.mock import patch

from benchmarks.run_soak import Configuration, Soak
from tools import soak_monitor as monitor


class SoakMonitorTests(unittest.TestCase):
    def test_proc_birth_and_terminal_states_are_checked_independently(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            process = root / "123"
            process.mkdir()
            for state in ("S", "Z", "X", "x"):
                fields = [state, *(["0"] * 18), "4567", "0"]
                (process / "stat").write_text("123 (worker ) with spaces) " + " ".join(fields))
                result = monitor.process_state(123, "4567", proc_root=root)
                self.assertTrue(result["birth_matches"])
                self.assertEqual(result["alive"], state == "S")
            self.assertFalse(monitor.process_state(123, "wrong-birth", proc_root=root)["alive"])
            self.assertFalse(monitor.process_state(999, "4567", proc_root=root)["alive"])
            self.assertFalse(monitor.process_state(0, None, proc_root=root)["alive"])

    @staticmethod
    def fixture():
        started = 10_000_000_000
        duration = 86400
        now = started + (duration + 2) * 1_000_000_000
        definition = {"started_ns": started, "deadline_ns": started + duration * 1_000_000_000,
            "planned_rounds": 1, "configuration": {"duration": duration, "heartbeat_interval": 5},
            "environment": {"commit": "1" * 40}}
        status = {"original_started_ns": started, "deadline_ns": definition["deadline_ns"], "source_commit": "1" * 40,
                  "stability_target_passed": True}  # Observer never trusts this flag.
        financial = {"uta_orders": 4, "uta_matches": 2, "uta_fills": 4}
        full = {"full": True, "counts": {**financial,
            "independent_reconciliation": {"status": "passed", "unpaired_fills": 0}}}
        database = {"sessions": [{"started_ns": started + 1, "heartbeat_ns": now - 1_000_000_000,
            "active_ns": duration * 1_000_000_000, "status": "completed"}], "stored_status": "completed",
            "round_errors": 0, "counts": {"done": 1}, "inflight": 0, "golden_matches": True,
            "logs_verified": True, "financial_counts": financial,
            "latest_full_verification": {"payload": json.dumps(full)}}
        return definition, status, database, {"alive": False, "state": "Z"}, now

    def test_final_review_requires_actual_24h_and_entire_log_audit(self):
        definition, status, database, process, now = self.fixture()
        result = monitor.assess(definition, status, database, process, now_ns=now)
        self.assertFalse(result["eligible_for_independent_final_review"])
        result = monitor.assess(definition, status, database, process, now_ns=now, final_audit={"passed": True})
        self.assertTrue(result["eligible_for_independent_final_review"])
        self.assertFalse(result["stability_24h_approved"])
        self.assertFalse(result["production_approved"])
        database["sessions"][0]["active_ns"] = 60 * 1_000_000_000
        self.assertFalse(monitor.assess(definition, status, database, process, now_ns=now,
            final_audit={"passed": True})["eligible_for_independent_final_review"])

    def test_mid_round_golden_difference_is_not_reported_as_financial_fault(self):
        definition, status, database, process, now = self.fixture()
        database.update(stored_status="running", inflight=1, golden_matches=False, counts={"active": 1})
        database["sessions"][0]["status"] = "running"
        result = monitor.assess(definition, status, database, {"alive": True}, now_ns=now)
        self.assertEqual(result["golden_state"], "inflight_indeterminate")
        self.assertNotIn("quiescent_golden_requires_review", result["alerts"])
        self.assertFalse(result["eligible_for_independent_final_review"])
        database["inflight"] = 0
        result = monitor.assess(definition, status, database, {"alive": True}, now_ns=now)
        self.assertIn("quiescent_golden_requires_review", result["alerts"])

    def test_exited_or_reused_pid_and_stale_heartbeat_are_observer_alerts(self):
        definition, status, database, process, now = self.fixture()
        database["stored_status"] = "running"
        database["sessions"][0]["heartbeat_ns"] -= 60 * 1_000_000_000
        result = monitor.assess(definition, status, database, process, now_ns=now)
        self.assertIn("producer_exited_or_pid_reused", result["alerts"])
        self.assertIn("heartbeat_stale", result["alerts"])

    def test_changed_original_timing_or_source_and_impossible_clocks_are_rejected(self):
        definition, status, database, process, now = self.fixture()
        for field in ("deadline_ns", "original_started_ns", "source_commit"):
            changed = {**status, field: "changed"}
            with self.subTest(field=field), self.assertRaisesRegex(RuntimeError, "binding changed"):
                monitor.assess(definition, changed, database, process, now_ns=now)
        database["sessions"][0]["active_ns"] = now * 2
        with self.assertRaisesRegex(RuntimeError, "clocks contradict"):
            monitor.assess(definition, status, database, process, now_ns=now)

    def test_old_full_replay_cannot_cover_new_financial_activity(self):
        definition, status, database, process, now = self.fixture()
        database["financial_counts"]["uta_matches"] += 1
        result = monitor.assess(definition, status, database, process, now_ns=now, final_audit={"passed": True})
        self.assertFalse(result["final_independent_replay_covers_financial_state"])
        self.assertFalse(result["eligible_for_independent_final_review"])

    def test_final_log_audit_rehashes_every_segment_and_checks_complete_sequence(self):
        with TemporaryDirectory() as directory:
            job = Path(directory)
            logs = job / "logs"
            logs.mkdir()
            data = gzip.compress(b'{"sequence":1}\n{"sequence":2}\n', mtime=0)
            (logs / "prefix.gz").write_bytes(data)
            (logs / "manifest.json").write_text(json.dumps({"segments": {"prefix.gz": {
                "sha256": sha256(data).hexdigest(), "bytes": len(data), "first": 1, "last": 2, "rows": 2}}}))
            checkpoint = {"export_cursor": 2, "last_evidence_sequence": 2}
            self.assertTrue(monitor.audit_logs(job, checkpoint)["passed"])
            with self.assertRaisesRegex(RuntimeError, "coverage differs"):
                monitor.audit_logs(job, {**checkpoint, "last_evidence_sequence": 3})
            (logs / "prefix.gz").write_bytes(data + b"tampered")
            with self.assertRaisesRegex(RuntimeError, "checksum"):
                monitor.audit_logs(job, checkpoint)

    def test_observe_uses_fixed_status_action_and_does_not_change_authority(self):
        with TemporaryDirectory() as directory:
            job = Soak(directory, Configuration(duration=.6, rate=2, min_free_bytes=0), strict_source=False)
            try:
                before = sha256(job.path.read_bytes()).hexdigest()
                original = (Path(directory) / "job.json").read_bytes()
                # The financial fixture may live in a developer's dirty test
                # checkout. Source-policy rejection is covered independently.
                root = Path(__file__).resolve().parents[1]
                with patch.object(monitor, "producer_source", return_value=root):
                    row = monitor.observe(directory, source=root)
                self.assertEqual(row["producer_status_command"][-3], "status")
                self.assertEqual(row["read_only_database_snapshot"]["financial_counts"]["uta_matches"], 0)
                self.assertEqual(row["assessment"]["golden_state"], "quiescent_matches")
                self.assertFalse(row["assessment"]["stability_24h_approved"])
                self.assertEqual(sha256(job.path.read_bytes()).hexdigest(), before)
                self.assertEqual((Path(directory) / "job.json").read_bytes(), original)
                self.assertFalse((Path(directory) / "STOP").exists())
            finally:
                job.close()

    def test_watch_pins_definition_and_never_overwrites_old_observations(self):
        with TemporaryDirectory() as directory:
            job = Path(directory)
            (job / "job.json").write_text('{"fixture":"only observer planner, no financial state"}')
            output = job / "observer-test"
            stop = Event()
            def fake(*args, **kwargs):
                stop.set()
                return {"assessment": {"actual_wall_seconds": 120, "eligible_for_independent_final_review": False}}
            with patch.object(monitor, "observe", side_effect=fake) as observe:
                result = monitor.watch(job, output, stop=stop)
            self.assertEqual(result["observations"], 1)
            self.assertEqual(observe.call_args.kwargs["expected_definition_hash"], sha256((job / "job.json").read_bytes()).hexdigest())
            before = (output / "observation-000001.json").read_bytes()
            with self.assertRaisesRegex(ValueError, "cannot be overwritten"):
                monitor.watch(job, output)
            self.assertEqual((output / "observation-000001.json").read_bytes(), before)
            self.assertFalse((job / "STOP").exists())

    def test_changed_job_definition_is_rejected_before_status_subprocess(self):
        with TemporaryDirectory() as directory:
            job = Path(directory)
            (job / "job.json").write_text('{"changed":true}')
            with patch.object(monitor.subprocess, "run") as command, self.assertRaisesRegex(RuntimeError, "definition changed"):
                monitor.observe(job, expected_definition_hash="0" * 64)
            command.assert_not_called()

    def test_source_content_must_match_producer_fingerprint(self):
        with TemporaryDirectory() as directory:
            job = Path(directory)
            source = job / "source"
            (source / "uta").mkdir(parents=True)
            path = source / "uta/frozen.py"
            path.write_text("frozen")
            definition = {"environment": {"commit": "1" * 40,
                "source_sha256": {"uta/frozen.py": sha256(path.read_bytes()).hexdigest()}}}
            with patch.object(monitor.subprocess, "check_output", side_effect=lambda args, **kwargs:
                    "1" * 40 if args[1] == "rev-parse" else ""):
                self.assertEqual(monitor.producer_source(job, definition, source), source)
                path.write_text("changed")
                with self.assertRaisesRegex(RuntimeError, "source content differs"):
                    monitor.producer_source(job, definition, source)
            with patch.object(monitor.subprocess, "check_output", side_effect=["1" * 40, " M benchmarks/run_benchmark.py"]):
                with self.assertRaisesRegex(RuntimeError, "tracked source differs"):
                    monitor.producer_source(job, definition, source)

    def test_observer_cannot_write_at_producer_root_or_unbounded_rate(self):
        with TemporaryDirectory() as directory:
            job = Path(directory)
            for output, interval in ((job, 60), (job / "logs", 60), (job / "observer", .001)):
                with self.subTest(output=output, interval=interval), self.assertRaises(ValueError):
                    monitor.watch(job, output, interval=interval)

    def test_atomic_staging_is_outside_producer_scan_and_leaves_no_temporary_path(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            job = root / "job"
            output = job / "observer-test"
            output.mkdir(parents=True)
            staging = root / "private-stage"
            staging.mkdir()
            original = monitor.os.replace
            seen = []
            def check(source, target):
                self.assertNotIn(job, Path(source).parents)
                self.assertIn(job, Path(target).parents)
                self.assertEqual(list(job.rglob("*.tmp")), [])
                seen.append(True)
                return original(source, target)
            with patch.object(monitor.os, "replace", side_effect=check):
                monitor.atomic(output / "latest.json", {"readonly": True}, staging)
            self.assertEqual(seen, [True])
            self.assertEqual(list(staging.iterdir()), [])
            self.assertEqual(json.loads((output / "latest.json").read_text()), {"readonly": True})


if __name__ == "__main__":
    unittest.main()
