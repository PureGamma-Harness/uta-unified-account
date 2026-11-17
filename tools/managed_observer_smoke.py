"""Prepared PIPE launcher for an explicitly authorized 60-second smoke.

Default prepare is read-only and never starts a producer. Root GO remains an
external scheduling decision. The frozen observer's 21600-second gate is never
altered. Short cold audit calls the actual producer CLI on a private full clone.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from hashlib import sha256
import os
from pathlib import Path
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
from threading import Thread
import time

sys.dont_write_bytecode = True
try:
    from tools import managed_soak_observer as ro
except ModuleNotFoundError:
    import managed_soak_observer as ro

TARGET = "763202df9cb3ce089721e5281371aff3eab58089"
SOURCE = Path("/workspace/uta-operations-freeze-763202d")
REPORT = Path("/workspace/uta-operations-validation/763202d/python312/summary.json")
OBSERVER = Path(ro.__file__).resolve()
EXPECTED_SHORT_BLOCKERS = {"actual_6h_and_5400_rounds_required", "producer_actual_active_duration_incomplete",
                           "producer_cold_audit_same_watermark_missing"}
PUBLIC_FIELDS = {"synthetic", "redacted", "status", "mode", "planned_rounds", "rounds", "unresolved_steps",
    "unresolved_faults", "elapsed_seconds", "fault_signals", "logs_verified", "final_audit", "verified_tls",
    "controller_sessions", "format", "observation_only", "observer_is_formal_signoff", "sample_wall_ns",
    "frozen_commit", "contract_sha256", "original_start_boottime_ns", "original_deadline_boottime_ns",
    "active_elapsed_seconds", "completed_rounds", "active_rounds", "logical_point", "planned_faults", "driver",
    "listener", "worker", "control_lane", "progress_age_seconds", "financial_ready", "finance", "alerts",
    "final_evidence_eligible", "final_reconciliation", "error_type", "error_digest", *ro.FLAGS}


def identity_report(source, report, commit):
    value = ro.load_json(report)
    if value["code_commit"] != commit or any(value.get(key) is not True for key in ro.VALIDATION_FLAGS):
        raise ValueError("exact_passed_source_report_required")
    ro.integer(value["tests_run"], 1)
    if any(type(value.get(key)) is not int or value[key] != 0 for key in (*ro.VALIDATION_COUNTS, "worker_exit_code")):
        raise ValueError("literal_zero_report_outcomes_required")
    argv = value["command_argv"]
    if len(argv) != 4 or Path(argv[1]) != source / "tools/run_validation.py" or argv[2] != "--output":
        raise ValueError("exact_actual_validator_command_required")
    current = subprocess.check_output(["git", "--no-optional-locks", "rev-parse", "HEAD"], cwd=source,
        stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True, text=True).strip()
    if current != commit:
        raise ValueError("frozen_source_commit_changed")
    return value


def captured(command, *, cwd, timeout=45, launch=None):
    """Bound memory, drain both pipes, retain unknown stderr only as a digest."""
    process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, close_fds=True)
    birth = ro.process_identity(process.pid)["birth"]
    if birth is None:
        process.wait(timeout=5)
        raise ValueError("child_birth_unavailable")
    if launch is not None:
        ro.atomic_json(launch, {"synthetic": True, "driver_pid": process.pid, "driver_birth": birth,
            "launched_wall_ns": time.time_ns(), "launched_boottime_ns": time.clock_gettime_ns(time.CLOCK_BOOTTIME), **ro.FLAGS})
    streams = {}
    def drain(label, stream, retain):
        fingerprint, size, chunks, retained = sha256(), 0, [], 0
        try:
            while True:
                chunk = stream.read(65536)
                if not chunk:
                    break
                fingerprint.update(chunk)
                size += len(chunk)
                if retain and retained + len(chunk) <= 4 * 1024**2:
                    chunks.append(chunk)
                    retained += len(chunk)
        finally:
            stream.close()
        streams[label] = {"sha256": fingerprint.hexdigest(), "bytes": size,
                          "complete": not retain or retained == size, "raw": b"".join(chunks)}
    readers = [Thread(target=drain, args=("stdout", process.stdout, True), daemon=True),
               Thread(target=drain, args=("stderr", process.stderr, False), daemon=True)]
    for reader in readers:
        reader.start()
    timed_out = False
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        if process.pid in {4471, 8784}:
            raise ValueError("protected_process_identity")
        if ro.process_identity(process.pid, birth)["alive"]:
            process.send_signal(signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            if ro.process_identity(process.pid, birth)["alive"]:
                process.kill()
            process.wait(timeout=5)
    for reader in readers:
        reader.join(timeout=2)
    if set(streams) != {"stdout", "stderr"} or not streams["stdout"]["complete"]:
        raise ValueError("captured_output_unavailable_or_over_budget")
    stdout, stderr = streams["stdout"], streams["stderr"]
    response = None
    if stdout["raw"]:
        try:
            value = ro.parse(stdout["raw"])
            if isinstance(value, dict):
                response = {key: value[key] for key in PUBLIC_FIELDS if key in value}
        except (ValueError, TypeError):
            pass
    return {"synthetic": True, "redacted": True, "exit_code": process.returncode, "timed_out": timed_out,
        "ended_wall_ns": time.time_ns(),
        "response": response, "stdout_sha256": stdout["sha256"], "stderr_sha256": stderr["sha256"],
        "stderr_present": stderr["bytes"] != 0, **ro.FLAGS}


def short_state(observer):
    value = observer.sample()
    final = value.get("final_reconciliation")
    metadata = ro.load_json(observer.job / "job.json")
    if (metadata["configuration"]["duration"] != 60 or metadata["configuration"]["rate"] != .25
            or value["planned_rounds"] != 15 or value["completed_rounds"] != 15 or value["active_rounds"]
            or value["active_elapsed_seconds"] is None or value["active_elapsed_seconds"] < 60
            or value["logical_point"] != "stable_boundary" or value["final_evidence_eligible"] is not False
            or final is None or set(final["errors"]) != EXPECTED_SHORT_BLOCKERS
            or final["independent_reopen_reconciliation_passed"] is not True
            or final["independent_reopen_same_watermark"] is not True
            or any(value.get(key) is not False for key in ro.FLAGS)):
        raise ValueError("short_smoke_not_cold_and_reconciled")
    return value


@contextmanager
def private_short_clone(observer, audit_output, *, max_bytes=256 * 1024**2):
    """Complete schema/nonce-bearing clone; private, never a public archive."""
    meta = ro.load_json(observer.job / "job.json")
    manifest = ro.load_json(observer.job / "log-segments.json")
    relative_files = [Path(name) for name in ("job.json", "progress.json", "log-segments.json")]
    relative_files += [Path("validation") / name for name in ro.VALIDATION_ARTIFACTS]
    relative_files += [ro.log_relative(segment["file"]) for segment in manifest["segments"]]
    databases = [Path(name) for name in ("checkpoint.sqlite3", "managed/router.sqlite3", "managed/shard-0000.sqlite3")]
    estimate = sum((observer.job / path).stat().st_size for path in relative_files + databases)
    for path in databases:
        try:
            estimate += Path(str(observer.job / path) + "-wal").stat().st_size
        except FileNotFoundError:
            pass
    if estimate > max_bytes or shutil.disk_usage(audit_output).free < estimate + 1024**3:
        raise ValueError("short_private_clone_disk_budget_unavailable")
    private = audit_output / "private-audit"
    private.mkdir(mode=0o700, exist_ok=True)
    if private.is_symlink() or private.stat().st_uid != os.geteuid() or private.stat().st_mode & 0o777 != 0o700:
        raise ValueError("short_private_clone_not_private")
    with tempfile.TemporaryDirectory(prefix="private-full-clone-", dir=private) as temporary:
        clone = Path(temporary)
        for path in databases:
            destination = clone / path
            destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with ro.readonly(observer.job / path, cold=True) as source:
                target = sqlite3.connect(destination)
                try:
                    destination.chmod(0o600)
                    source.backup(target)
                    target.execute("PRAGMA journal_mode=DELETE")
                finally:
                    target.close()
        for path in relative_files:
            destination = clone / path
            destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            raw = (observer.job / path).read_bytes()
            if path.parent == Path("validation") and sha256(raw).hexdigest() != meta["validation_evidence"]["artifact_sha256"][path.name]:
                raise ValueError("short_clone_validation_changed")
            ro.private_write(destination, raw)
        yield clone


def short_cold(args, report, launch):
    observer = ro.Observer(args.job, args.output, args.source, args.commit, launch["driver_pid"], launch["driver_birth"])
    first = short_state(observer)
    current = first["final_reconciliation"]["watermark"]
    probe = subprocess.run([report["command_argv"][0], "-B", "-c",
        "import json,sqlite3,sys; print(json.dumps({'python':sys.version,'sqlite':sqlite3.sqlite_version}))"],
        cwd=args.source, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True,
        timeout=10, text=True)
    if probe.returncode or ro.parse(probe.stdout) != {key: report[key] for key in ("python", "sqlite")}:
        raise ValueError("short_actual_audit_runtime_mismatch")
    with private_short_clone(observer, args.audit_output) as clone:
        with ro.readonly(clone / "managed/shard-0000.sqlite3", cold=True) as connection:
            copied = ro.read_financial(connection, 15, 15, compare_golden=True)
        if (copied["watermark"] != current["financial"] or copied["golden"]["passed"] is not True
                or ro.checkpoint(clone / "checkpoint.sqlite3", cold=True)["event_head"] != current["checkpoint"]):
            raise ValueError("short_private_clone_watermark_mismatch")
        run = subprocess.run([report["command_argv"][0], "-B", "benchmarks/run_managed_soak.py", "audit",
            "--directory", str(clone)], cwd=args.source, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True, timeout=30)
    audit = ro.parse(run.stdout) if run.returncode == 0 else None
    if (audit is None or audit.get("status") != "audit_passed" or audit.get("cold_read_only") is not True
            or audit["financial"]["golden_passed"] is not True
            or audit["financial"]["completed_rounds"] != 15 or audit["logs"]["last_hash"] != current["checkpoint"]["hash"]):
        raise ValueError("short_actual_producer_cold_audit_failed")
    second = short_state(observer)
    if second["final_reconciliation"]["watermark"] != current:
        raise ValueError("short_final_watermark_changed")
    result = {"synthetic": True, "redacted": True, "smoke_only": True, "smoke_duration_seconds": 60,
        "short_smoke_cold_audit_passed": True, "long_run_receipt_issued": False, "final_evidence_eligible": False,
        "producer_audit_scope": "short_smoke_private_complete_clone", "watermark_before": current,
        "watermark_after": second["final_reconciliation"]["watermark"],
        "producer_audit_runtime": {key: report[key] for key in ("python", "sqlite")},
        "producer_audit_stdout_sha256": sha256(run.stdout).hexdigest(),
        "producer_audit_stderr_sha256": sha256(run.stderr).hexdigest(), **ro.FLAGS}
    ro.atomic_json(args.audit_output / "short-smoke-cold-audit.json", result)
    return result


def main(argv=None):
    if not ro.safe_standard_descriptors():
        return 1
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", nargs="?", choices=("prepare", "produce-60", "observe-once", "long-gate", "short-cold"), default="prepare")
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--commit", default=TARGET)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--job", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--audit-output", type=Path)
    parser.add_argument("--record", default="pipe-response.json")
    args = parser.parse_args(argv)
    try:
        os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
        args.source, args.job, args.output = args.source.resolve(), args.job.resolve(), args.output.resolve()
        if (args.output == args.job or args.output.is_relative_to(args.job) or args.job.is_relative_to(args.output)
                or args.output.is_relative_to(args.source) or args.job.is_relative_to(args.source)):
            raise ValueError("scratch_output_must_be_separate")
        report = identity_report(args.source, args.report, args.commit)
        producer = [report["command_argv"][0], "-B", "benchmarks/run_managed_soak.py", "run", "--directory", str(args.job),
            "--duration", "60", "--worker-every", "5", "--parent-every", "10", "--validation-report", str(args.report)]
        if args.operation == "prepare":
            print(ro.canonical({"synthetic": True, "prepared_only": True, "service_started": False,
                "execution_authorized": False, "source_commit": args.commit, "reported_tests_run": report["tests_run"],
                "report_sha256": sha256(args.report.read_bytes()).hexdigest(), "producer_command_argv": producer,
                "producer_cwd": str(args.source), "still_requires_root_full_QA_package_and_GO": True, **ro.FLAGS}))
            return 0
        ro.output_directory(args.job, args.output)
        record = Path(args.record)
        if len(record.parts) != 1 or record.suffix != ".json" or (args.output / record).exists():
            raise ValueError("fresh_controlled_record_filename_required")
        if args.operation == "produce-60":
            if args.job.exists() or (args.output / "launch.json").exists():
                raise ValueError("smoke_requires_fresh_job_and_launch_identity")
            result = captured(producer, cwd=args.source, timeout=100, launch=args.output / "launch.json")
        else:
            launch = ro.load_json(args.output / "launch.json")
            command = [sys.executable, "-B", str(OBSERVER), "producer-audit" if args.operation == "long-gate" else "watch",
                "--job", str(args.job), "--output", str(args.output), "--source", str(args.source),
                "--frozen-commit", args.commit, "--driver-pid", str(launch["driver_pid"]), "--driver-birth", launch["driver_birth"]]
            if args.operation == "observe-once":
                command.append("--once")
            elif args.operation == "long-gate":
                command += ["--python", report["command_argv"][0]]
            else:
                if args.audit_output is None:
                    raise ValueError("separate_short_audit_output_required")
                args.audit_output = args.audit_output.resolve()
                ro.output_directory(args.job, args.audit_output)
                if args.audit_output == args.output or args.audit_output.is_relative_to(args.source):
                    raise ValueError("short_audit_output_must_be_separate")
                if not (os.statvfs(args.job).f_flag & os.ST_RDONLY and os.statvfs(args.source).f_flag & os.ST_RDONLY):
                    executable = shutil.which("bwrap")
                    if executable is None:
                        raise ValueError("short_audit_readonly_mount_required")
                    invocation = [executable, "--ro-bind", "/", "/", "--bind", str(args.audit_output), str(args.audit_output),
                                  "--", sys.executable, "-B", str(Path(__file__).resolve()), *(sys.argv[1:] if argv is None else argv)]
                    run = subprocess.run(invocation, cwd=Path(__file__).resolve().parents[1], stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True, timeout=45)
                    if run.returncode:
                        raise ValueError("short_audit_child_failed_closed")
                    result = ro.parse(run.stdout)
                    print(ro.canonical(result))
                    return 0
                if os.statvfs(args.audit_output).f_flag & os.ST_RDONLY:
                    raise ValueError("short_audit_output_not_writable")
                result = short_cold(args, report, launch)
                print(ro.canonical(result))
                return 0
            result = captured(command, cwd=Path(__file__).resolve().parents[1])
        ro.atomic_json(args.output / record, result)
        print(ro.canonical(result))
        return 0 if result["exit_code"] == 0 and not result["timed_out"] else 1
    except (OSError, ValueError, KeyError, TypeError, ArithmeticError, sqlite3.Error, subprocess.SubprocessError) as error:
        print(ro.canonical({"synthetic": True, "redacted": True, "smoke_only": True, "final_evidence_eligible": False,
            "error_type": type(error).__name__, "error_digest": sha256(str(error).encode()).hexdigest(), **ro.FLAGS}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
