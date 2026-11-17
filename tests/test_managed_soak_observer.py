"""Observer tests use only tiny private SQLite fixtures, never a running job."""
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import managed_soak_observer as observer
from tests.test_managed_observer_finance import fixture as financial_fixture


COMMIT = "4" * 40


def metadata():
    return {"job_id": "synthetic", "configuration": {"duration": 21600, "rate": .25, "heartbeat_interval": 5},
        "planned_rounds": 5400, "accounts": observer.ACCOUNTS,
        "environment": {"commit": COMMIT, "synthetic": True, "source_sha256": {}, "workload_spec_sha256": "a" * 64},
        "bootstrap": {"synthetic_only": True, "initial_principal_satoshi": 10800},
        "validation_evidence": {"code_commit": COMMIT, "engineering_test_qualified": True,
            "artifact_sha256": {name: "0" * 64 for name in ("summary.json", "worker-result.json", "unittest.txt")}},
        "file_identities": {}}


def cp_snapshot(active=False):
    return {"states": {"started_boottime_ns": 1_000_000_000, "boot_id": "synthetic-boot", "controller_sessions": 1,
        "logs_verified": True, "listener": {"pid": 1234, "birth": "9"}},
        "rounds": [{"sequence": 1, "planned_ns": 1_000_000_000, "state": "ACTIVE" if active else "DONE",
                    "completed_ns": None if active else 2_000_000_000}],
        "steps": [], "faults": [], "completed": 0 if active else 1,
        "active_rounds": [1] if active else [], "unresolved_steps": 0, "unresolved_faults": 0,
        "event_head": {"sequence": 1, "hash": "0" * 64}, "driver_pid": os.getpid(),
        "controller_ended": None}


def finance(compared=False):
    return {"watermark": {"sha256": "a" * 64}, "golden": {"compared": compared, "passed": compared},
            "retry_alerts": [], "counts": {}, "synthetic": True}


class ReadOnlyTests(unittest.TestCase):
    def test_missing_never_creates_file_or_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "missing.sqlite3"
            with self.assertRaises(FileNotFoundError):
                with observer.readonly(target):
                    self.fail("opened missing database")
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_real_sqlite_has_no_writes_ddl_mtime_or_open_connection(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "authority.sqlite3"
            writer = sqlite3.connect(target)
            writer.execute("CREATE TABLE facts(value INTEGER)")
            writer.execute("INSERT INTO facts VALUES(1)")
            writer.commit()
            writer.close()
            before = target.stat()
            contents = target.read_bytes()
            with patch.object(observer.os, "open", side_effect=AssertionError("raw inode descriptor forbidden")):
                with observer.readonly(target, cold=True) as reader:
                    self.assertTrue(reader.in_transaction)
                    self.assertEqual(reader.execute("PRAGMA query_only").fetchone()[0], 1)
                    self.assertEqual(reader.execute("SELECT value FROM facts").fetchone()[0], 1)
                    for query in ("CREATE TABLE extra(value)", "INSERT INTO facts VALUES(2)",
                                  "PRAGMA journal_mode=WAL", "ATTACH ':memory:' AS other"):
                        with self.assertRaises(sqlite3.DatabaseError):
                            reader.execute(query)
            with self.assertRaises(sqlite3.ProgrammingError):
                reader.execute("SELECT 1")
            self.assertEqual(before.st_mtime_ns, target.stat().st_mtime_ns)
            self.assertEqual(contents, target.read_bytes())
            self.assertEqual([item.name for item in Path(directory).iterdir()], [target.name])

    def test_live_wal_uses_snapshot_and_allows_progress_between_connections(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "authority.sqlite3"
            writer = sqlite3.connect(target)
            try:
                writer.execute("PRAGMA journal_mode=WAL")
                writer.execute("CREATE TABLE facts(value INTEGER)")
                writer.execute("INSERT INTO facts VALUES(1)")
                writer.commit()
                names = {item.name for item in Path(directory).iterdir()}
                with observer.readonly(target) as reader:
                    self.assertEqual(reader.execute("SELECT value FROM facts").fetchone()[0], 1)
                    writer.execute("UPDATE facts SET value=2")
                    writer.commit()
                    self.assertEqual(reader.execute("SELECT value FROM facts").fetchone()[0], 1)
                with observer.readonly(target) as reader:
                    self.assertEqual(reader.execute("SELECT value FROM facts").fetchone()[0], 2)
                self.assertEqual(names, {item.name for item in Path(directory).iterdir()})
            finally:
                writer.close()

    def test_missing_wal_sidecar_fails_before_sqlite_open(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "authority.sqlite3"
            target.touch()
            Path(str(target) + "-wal").touch()
            with self.assertRaisesRegex(ValueError, "wal_sidecar_snapshot_unavailable"):
                with observer.readonly(target, cold=True):
                    self.fail()
            self.assertFalse(Path(str(target) + "-shm").exists())

    def test_closed_wal_without_sidecars_is_immutable_only_after_cold_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "closed-wal.sqlite3"
            writer = sqlite3.connect(target)
            writer.execute("PRAGMA journal_mode=WAL")
            writer.execute("CREATE TABLE facts(value)")
            writer.execute("INSERT INTO facts VALUES(1)")
            writer.commit()
            writer.close()
            before = target.stat().st_mtime_ns
            with patch.object(observer.time, "monotonic", side_effect=[0, 10]):
                with self.assertRaisesRegex(ValueError, "wal_sidecar_snapshot_unavailable"):
                    with observer.readonly(target):
                        self.fail()
            with observer.readonly(target, cold=True) as reader:
                self.assertEqual(reader.execute("SELECT value FROM facts").fetchone()[0], 1)
            self.assertEqual({path.name for path in Path(directory).iterdir()}, {target.name})
            self.assertEqual(target.stat().st_mtime_ns, before)

    def test_kernel_readonly_mount_prevents_sqlite_sidecar_creation_race(self):
        executable = shutil.which("bwrap")
        if executable is None:
            self.fail("observer runtime requires bwrap; no unsandboxed fallback")
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "closed-wal.sqlite3"
            writer = sqlite3.connect(target)
            writer.execute("PRAGMA journal_mode=WAL")
            writer.execute("CREATE TABLE facts(value)")
            writer.commit()
            writer.close()
            # Deliberately use plain mode=ro to reproduce the original SQLite
            # creation attempt. Kernel mount protection must stop it regardless
            # of a Python sidecar precheck and without changing file permissions.
            script = "import pathlib,sqlite3,sys; p=pathlib.Path(sys.argv[1]); c=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True); c.execute('SELECT * FROM facts')"
            run = subprocess.run([executable, "--ro-bind", "/", "/", "--", sys.executable, "-B", "-c", script, str(target)],
                                 capture_output=True, text=True)
            self.assertNotEqual(run.returncode, 0)
            self.assertIn("OperationalError", run.stderr)
            self.assertEqual({path.name for path in Path(directory).iterdir()}, {target.name})


class ProcessAndClockTests(unittest.TestCase):
    def test_pid_birth_zombie_and_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            proc = Path(directory)
            (proc / "123").mkdir()
            target = proc / "123/stat"
            def record(state):
                target.write_text("123 (name with ) spaces) " + " ".join([state] + ["0"] * 18 + ["77"]))
            record("S")
            self.assertTrue(observer.process_identity(123, "77", proc=proc)["alive"])
            self.assertFalse(observer.process_identity(123, "78", proc=proc)["alive"])
            record("Z")
            self.assertFalse(observer.process_identity(123, "77", proc=proc)["alive"])
            target.unlink()
            self.assertEqual(observer.process_identity(123, "77", proc=proc)["state"], "missing")

    def test_market_future_stale_and_lease_future(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        try:
            connection.executescript("CREATE TABLE writer_fence_lease(singleton,generation,owner_pid,boot_id,expires_ns,observed_ns);"
                "INSERT INTO writer_fence_lease VALUES(1,2,NULL,'boot',90000000000,20000000000);"
                "CREATE TABLE uta_config(key,value); INSERT INTO uta_config VALUES('halted','false');"
                "CREATE TABLE uta_market(singleton,payload);")
            for offset, future, fresh in ((1, True, False), (-31, False, False), (-1, False, True)):
                timestamp = datetime.fromtimestamp(100 + offset, timezone.utc).isoformat()
                connection.execute("DELETE FROM uta_market")
                connection.execute("INSERT INTO uta_market VALUES(1,?)", (json.dumps({"version": 4, "observed_at": timestamp}),))
                result = observer.read_health(connection, [], 10_000_000_000, "boot", 100_000_000_000)
                self.assertEqual(result["market_future"], future)
                self.assertEqual(result["market_fresh"], fresh)
                self.assertTrue(result["heartbeat_future"])
                self.assertFalse(result["lease_active"])
        finally:
            connection.close()

    def test_original_source_start_deadline_schedule_are_immutable(self):
        meta, cp = metadata(), cp_snapshot()
        contract = observer.validate_metadata(meta, cp, COMMIT)
        self.assertEqual(contract["deadline_boottime_ns"], 21_601_000_000_000)
        for mutation in (lambda m, c: m["environment"].update(commit="5" * 40),
                         lambda m, c: m["configuration"].update(duration=21601),
                         lambda m, c: c["rounds"][0].update(planned_ns=2_000_000_000)):
            changed_meta, changed_cp = copy.deepcopy(meta), copy.deepcopy(cp)
            mutation(changed_meta, changed_cp)
            with self.assertRaises(ValueError):
                observer.validate_metadata(changed_meta, changed_cp, COMMIT)
        del cp["states"]["started_boottime_ns"]
        with self.assertRaises(KeyError):
            observer.validate_metadata(meta, cp, COMMIT)

    def test_source_dirty_or_changed_fails_closed(self):
        meta = metadata()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            (source / "docs").mkdir()
            (source / "docs/managed-soak-golden.md").write_text("golden")
            meta["environment"]["workload_spec_sha256"] = observer.sha256(b"golden").hexdigest()
            with patch.object(observer.subprocess, "check_output", side_effect=[COMMIT, " M changed.py"]):
                with self.assertRaisesRegex(ValueError, "frozen_source_changed_or_dirty"):
                    observer.check_source(source, meta, COMMIT)
            with patch.object(observer.subprocess, "check_output", side_effect=[COMMIT, ""]):
                observer.check_source(source, meta, COMMIT)
            (source / "docs/managed-soak-golden.md").write_text("changed")
            with patch.object(observer.subprocess, "check_output", side_effect=[COMMIT, ""]):
                with self.assertRaisesRegex(ValueError, "frozen_workload_spec_changed"):
                    observer.check_source(source, meta, COMMIT)


class ObservationTests(unittest.TestCase):
    def make_observer(self, directory):
        job, output = Path(directory) / "job", Path(directory) / "observation"
        job.mkdir()
        (job / "progress.json").write_text(json.dumps({"status": "running", "error": None}))
        (job / "job.json").write_text(json.dumps(metadata()))
        (job / "managed").mkdir()
        db = sqlite3.connect(job / "managed/shard-0000.sqlite3")
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE fixture(value)")
        db.commit()
        self.addCleanup(db.close)
        pid = os.getpid()
        birth = observer.process_identity(pid)["birth"]
        return observer.Observer(job, output, job, COMMIT, pid, birth)

    def test_midround_never_compares_golden_or_calls_status(self):
        with tempfile.TemporaryDirectory() as directory:
            instance = self.make_observer(directory)
            cp = cp_snapshot(active=True)
            health = {"market_fresh": True, "market_future": False, "heartbeat_future": False}
            with patch.object(observer, "checkpoint", return_value=cp), \
                 patch.object(observer, "check_source"), patch.object(observer, "validation_manifest"), \
                 patch.object(observer, "identity_files"), patch.object(observer, "read_control", return_value=({}, [])), \
                 patch.object(observer, "read_health", return_value=health), \
                 patch.object(observer, "read_financial", return_value=finance()) as read:
                result = instance.sample()
            self.assertEqual(result["logical_point"], "inflight_or_unknown")
            self.assertEqual(read.call_count, 1)
            self.assertFalse(read.call_args.kwargs["compare_golden"])
            self.assertFalse(result["production_approved"])
            self.assertEqual(result["financial_ready"], "unknown_independent_observer_has_no_readiness_authority")

    def test_changed_checkpoint_does_not_report_bad_debt(self):
        with tempfile.TemporaryDirectory() as directory:
            instance = self.make_observer(directory)
            before, after = cp_snapshot(), cp_snapshot(active=True)
            after["event_head"]["sequence"] = 2
            with patch.object(observer, "checkpoint", side_effect=[before, after]), \
                 patch.object(observer, "check_source"), patch.object(observer, "validation_manifest"), \
                 patch.object(observer, "identity_files"), patch.object(observer, "read_control", return_value=({}, [])), \
                 patch.object(observer, "read_health", return_value={"market_fresh": True, "heartbeat_future": False}), \
                 patch.object(observer, "read_financial", return_value=finance()) as read:
                result = instance.sample()
            self.assertEqual(result["logical_point"], "inflight_or_unknown")
            self.assertEqual(read.call_count, 1)

    def test_atomic_temporaries_are_outside_job_and_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            instance = self.make_observer(directory)
            before = set(instance.job.rglob("*"))
            instance.publish({"synthetic": True, **observer.FLAGS})
            self.assertEqual(before, set(instance.job.rglob("*")))
            self.assertEqual({p.name for p in instance.output.iterdir()}, {"latest.json", "timeline.jsonl"})
            self.assertFalse(observer.load_json(instance.output / "latest.json")["continuous_6h_stability_passed"])
            for output in (instance.job, instance.job / "observer", instance.job.parent):
                with self.assertRaises(ValueError):
                    observer.output_directory(instance.job, output)

    def test_changed_original_start_fails_against_external_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            instance = self.make_observer(directory)
            cp = cp_snapshot(active=True)
            with patch.object(observer, "checkpoint", return_value=cp), \
                 patch.object(observer, "check_source"), patch.object(observer, "validation_manifest"), \
                 patch.object(observer, "identity_files"), patch.object(observer, "read_control", return_value=({}, [])), \
                 patch.object(observer, "read_health", return_value={"market_fresh": True, "heartbeat_future": False}), \
                 patch.object(observer, "read_financial", return_value=finance()):
                instance.sample()
                cp["states"]["started_boottime_ns"] += 10
                cp["rounds"][0]["planned_ns"] += 10
                with self.assertRaisesRegex(ValueError, "original_source_start_deadline_or_identity_changed"):
                    instance.sample()

    def test_original_checkpoint_and_financial_cids_cover_same_job(self):
        meta, cp = metadata(), cp_snapshot()
        meta["job_id"] = "a" * 24
        cids = [f"ms:{meta['job_id']}:r000000001:{name}" for name in sorted(observer.COMMAND_STEPS)]
        cp["steps"] = [{"name": cid.rsplit(":", 1)[1], "command_id": cid} for cid in cids]
        facts = {"command_inbox": [{"command_id": cid, "control_lane": False} for cid in cids]}
        self.assertTrue(observer.original_command_coverage(meta, cp, facts))
        facts["command_inbox"][0]["command_id"] = "ms:" + "b" * 24 + ":r000000001:open-buy"
        self.assertFalse(observer.original_command_coverage(meta, cp, facts))

    def test_actual_once_cli_mounts_job_readonly_and_missing_fields_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job, output = root / "job", root / "observer"
            job.mkdir()
            pid = os.getpid()
            birth = observer.process_identity(pid)["birth"]
            script = Path(observer.__file__).resolve()
            run = subprocess.run([sys.executable, "-B", str(script), "watch", "--once", "--job", str(job),
                "--output", str(output), "--source", str(script.parents[1]), "--frozen-commit", COMMIT,
                "--driver-pid", str(pid), "--driver-birth", birth], cwd=script.parents[1], capture_output=True, text=True)
            self.assertEqual(run.returncode, 1, run.stderr)
            report = observer.parse(run.stdout)
            self.assertEqual(report["alerts"], ["observation_failed_closed"])
            self.assertEqual(list(job.iterdir()), [])
            self.assertEqual({path.name for path in output.iterdir()}, {"latest.json", "timeline.jsonl"})
            self.assertFalse(any(report[key] for key in observer.FLAGS))

    def test_final_missing_logs_midround_short_job_and_retries_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            instance = self.make_observer(directory)
            cp = cp_snapshot(active=True)
            cp["states"]["logs_verified"] = False
            contract = observer.validate_metadata(metadata(), cp, COMMIT)
            progress = {"logs_verified": False, "controller_sessions": 1, "verified_tls": True,
                "final_audit": {"golden_passed": True}, "error": None, "elapsed_seconds": 10,
                "unresolved_steps": 0, "unresolved_faults": 0}
            facts = finance()
            facts["retry_alerts"] = [{"cause": "unknown"}]
            with patch.object(observer, "verify_logs", return_value={"verified": True}), \
                 patch.object(observer, "checkpoint", return_value=cp), \
                 patch.object(observer, "read_financial", return_value=finance(True)):
                result = instance.final_check(metadata(), progress, cp, contract, facts, False, 10,
                                              {"alive": True}, {"process": None, "lease_active": True})
            self.assertFalse(result["eligible"])
            self.assertIn("final_logs_verified_missing", result["errors"])
            self.assertIn("actual_6h_and_5400_rounds_required", result["errors"])
            self.assertIn("independent_final_golden_or_retry_failed", result["errors"])
            self.assertIn("producer_cold_audit_same_watermark_missing", result["errors"])
            self.assertFalse(result["continuous_6h_stability_passed"])
            del progress["logs_verified"]
            with self.assertRaisesRegex(ValueError, "final_progress_required_field_missing"):
                instance.final_check(metadata(), progress, cp, contract, facts, False, 10, {"alive": False}, {})

    def test_only_matching_actual_final_watermark_is_eligible_without_signoff_flags(self):
        with tempfile.TemporaryDirectory() as directory:
            instance = self.make_observer(directory)
            cp = cp_snapshot()
            cp.update(completed=5400, controller_ended={"status": "completed"})
            cp["faults"] = [{"kind": kind, "state": "DONE", "signal_sent": True,
                "old_generation": 1, "new_generation": 2} for kind in ("worker", "parent")]
            contract = observer.validate_metadata(metadata(), cp, COMMIT)
            progress = {"logs_verified": True, "controller_sessions": 1, "verified_tls": True,
                "final_audit": {"golden_passed": True}, "error": None, "elapsed_seconds": 21600,
                "unresolved_steps": 0, "unresolved_faults": 0}
            facts = finance(True)
            current = observer.watermark(cp, facts, contract)
            receipt = {"format": 1, "frozen_commit": COMMIT, "audit_sha256": "a" * 64,
                "producer_cold_audit_passed": True, "watermark_before": current, "watermark_after": current,
                "producer_audit_scope": "exact_sqlite_backup_of_stopped_public_job"}
            target = instance.output / "producer-cold-audit-receipt.json"
            instance.producer_receipt = target
            observer.atomic_json(target, receipt)
            with patch.object(observer, "verify_logs", return_value={"verified": True}), \
                 patch.object(observer, "checkpoint", return_value=cp), \
                 patch.object(observer, "read_financial", return_value=facts):
                result = instance.final_check(metadata(), progress, cp, contract, facts, True, 21600,
                                              {"alive": False}, {"process": None, "lease_active": False})
                self.assertTrue(result["eligible"])
                self.assertFalse(any(result[key] for key in observer.FLAGS))
                receipt["watermark_before"] = {}
                observer.atomic_json(target, receipt)
                result = instance.final_check(metadata(), progress, cp, contract, facts, True, 21600,
                                              {"alive": False}, {"process": None, "lease_active": False})
                self.assertFalse(result["eligible"])
                self.assertIn("producer_cold_audit_watermark_mismatch", result["errors"])
                progress["elapsed_seconds"] = 10
                result = instance.final_check(metadata(), progress, cp, contract, facts, True, 50000,
                                              {"alive": False}, {"process": None, "lease_active": False})
                self.assertIn("producer_actual_active_duration_incomplete", result["errors"])

    def test_raw_unknown_error_redacted_and_duplicate_json_rejected(self):
        raw = "secret = internal-host token"
        self.assertNotIn(raw, observer.public_code(raw))
        with self.assertRaisesRegex(ValueError, "duplicate_json_key"):
            observer.parse('{"synthetic":true,"synthetic":false}')

    def test_producer_audit_cannot_run_while_not_final(self):
        with tempfile.TemporaryDirectory() as directory:
            instance = self.make_observer(directory)
            with patch.object(instance, "sample", return_value={}), patch.object(observer.subprocess, "run") as run:
                with self.assertRaisesRegex(ValueError, "producer_audit_requires_other_final_checks_passed"):
                    observer.producer_audit(instance, "python")
                run.assert_not_called()

    def test_producer_cold_audit_backup_preserves_original_and_rejects_later_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job, output = root / "job", root / "observer"
            (job / "managed").mkdir(parents=True)
            financial_fixture(job / "managed/shard-0000.sqlite3", completed=1)
            router = sqlite3.connect(job / "managed/router.sqlite3")
            router.execute("CREATE TABLE public_fact(value)")
            router.close()
            database = sqlite3.connect(job / "checkpoint.sqlite3")
            database.executescript("CREATE TABLE state(key,value); CREATE TABLE rounds(sequence,planned_ns,state,completed_ns);"
                "CREATE TABLE steps(round,name,state,plan); CREATE TABLE faults(round,kind,state,evidence);"
                "CREATE TABLE events(sequence,kind,payload,event_hash);")
            states = cp_snapshot()["states"]
            database.executemany("INSERT INTO state VALUES(?,?)", [(key, json.dumps(value)) for key, value in states.items()])
            database.execute("INSERT INTO events VALUES(1,'CONTROLLER_STARTED',? ,?)", (json.dumps({"pid": os.getpid()}), "0" * 64))
            database.commit()
            database.close()
            for name, value in (("job.json", metadata()), ("progress.json", {"status": "completed"}),
                                ("log-segments.json", {"segments": []})):
                (job / name).write_text(json.dumps(value))
            (job / "private").mkdir()
            (job / "private/key.pem").write_text("synthetic-sensitive-sentinel")
            instance = observer.Observer(job, output, root / "source", COMMIT, os.getpid(), "1")
            instance.cold = True
            with observer.readonly(job / "managed/shard-0000.sqlite3", cold=True) as connection:
                facts = observer.read_financial(connection, 1, 1, compare_golden=True)
            watermark = {"financial": facts["watermark"], "checkpoint": {"sequence": 1, "hash": "0" * 64}, "contract_sha256": "a" * 64}
            final = {"errors": ["producer_cold_audit_same_watermark_missing"], "watermark": watermark}
            sample = {"planned_rounds": 1, "completed_rounds": 1, "final_reconciliation": final}
            audit = {"status": "audit_passed", "cold_read_only": True, "financial": {"golden_passed": True},
                     "logs": {"last_hash": "0" * 64}}
            before = {p.relative_to(job): (p.stat().st_mtime_ns, p.read_bytes())
                      for p in job.rglob("*") if p.is_file() and "private" not in p.parts}
            result = subprocess.CompletedProcess([], 0, json.dumps(audit), "")
            with patch.object(instance, "sample", return_value=sample), patch.object(observer.subprocess, "run", return_value=result) as run:
                receipt = observer.producer_audit(instance, "synthetic-python")
                self.assertTrue(receipt["producer_cold_audit_passed"])
                self.assertEqual(receipt["watermark_before"], receipt["watermark_after"])
                self.assertTrue(Path(run.call_args.args[0][-1]).is_relative_to(output))
                self.assertFalse(Path(run.call_args.args[0][-1]).exists())
            after = {p.relative_to(job): (p.stat().st_mtime_ns, p.read_bytes())
                     for p in job.rglob("*") if p.is_file() and "private" not in p.parts}
            self.assertEqual(before, after)
            self.assertFalse(any("auth" in p.name or p.suffix == ".pem" for p in output.rglob("*")))
            (output / "producer-cold-audit-receipt.json").unlink()
            later = copy.deepcopy(sample)
            later["final_reconciliation"]["errors"].append("final_authority_not_cold")
            with patch.object(instance, "sample", side_effect=[sample, later]), patch.object(observer.subprocess, "run", return_value=result):
                with self.assertRaisesRegex(ValueError, "producer_cold_audit_crossed_watermark"):
                    observer.producer_audit(instance, "synthetic-python")
            self.assertFalse((output / "producer-cold-audit-receipt.json").exists())


if __name__ == "__main__":
    unittest.main()
