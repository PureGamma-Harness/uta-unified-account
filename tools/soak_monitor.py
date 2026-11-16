"""Independent read-only observer of a fixed-source synthetic soak producer.

Only observer artifacts and private external staging are writable. The fixed
producer's status action and read-only SQLite are evidence inputs, not commands.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import gzip
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import tempfile
from threading import Event
import time


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def process_state(pid, expected_birth, *, proc_root=Path("/proc")):
    if type(pid) is not int or pid <= 0:
        return {"pid": pid, "present": False, "state": None, "birth": None,
                "birth_matches": False, "alive": False}
    try:
        # comm may contain whitespace or parentheses. Fields after its LAST ')'
        # begin at state(3); starttime(22) is therefore index19.
        fields = (proc_root / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()
        state, birth = fields[0], fields[19]
        matches = expected_birth is not None and str(expected_birth) == birth
        return {"pid": pid, "present": True, "state": state, "birth": birth,
                "birth_matches": matches, "alive": matches and state not in ("Z", "X", "x")}
    except (OSError, IndexError):
        return {"pid": pid, "present": False, "state": None, "birth": None,
                "birth_matches": False, "alive": False}


def producer_source(job, definition, source=None):
    launch_path = job / "launch.json"
    launch = json.loads(launch_path.read_text()) if launch_path.exists() else {}
    source = Path(source or launch.get("source_worktree", "")).absolute()
    expected = definition["environment"]["commit"]
    if launch.get("source_commit", expected) != expected:
        raise RuntimeError("launch and immutable producer source disagree")
    actual = subprocess.check_output(("git", "rev-parse", "HEAD"), cwd=source, text=True).strip()
    if actual != expected:
        raise RuntimeError("producer checkout HEAD differs from recorded producer source")
    changes = subprocess.check_output(("git", "--no-optional-locks", "status", "--porcelain", "--untracked-files=no"),
        cwd=source, text=True).strip()
    if changes:
        raise RuntimeError("producer tracked source differs from its immutable commit")
    for name, digest in definition["environment"]["source_sha256"].items():
        path = source / name
        if source not in path.resolve().parents or sha256(path.read_bytes()).hexdigest() != digest:
            raise RuntimeError("producer source content differs from original fingerprint")
    return source


def read_database(job):
    path = job / "authority.sqlite3"
    if path.is_symlink():
        raise RuntimeError("producer authority must not be a symlink")
    connection = sqlite3.connect(path.absolute().as_uri() + "?mode=ro", uri=True,
        isolation_level=None, timeout=2)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        counts = dict(connection.execute("SELECT status,COUNT(*) FROM soak_arrivals GROUP BY status"))
        sessions = [dict(row) for row in connection.execute("SELECT * FROM soak_sessions ORDER BY started_ns")]
        meta = dict(connection.execute("SELECT key,value FROM soak_meta"))
        done = [row[0] for row in connection.execute("SELECT sequence FROM soak_arrivals WHERE status='done'")]
        financial = {table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                     for table in ("uta_orders", "uta_matches", "uta_fills", "uta_positions")}
        financial["cancelled_orders"] = connection.execute("SELECT COUNT(*) FROM uta_orders WHERE status='CANCELLED'").fetchone()[0]
        financial["live_orders"] = connection.execute("SELECT COUNT(*) FROM uta_orders WHERE status IN ('OPEN','PARTIALLY_FILLED')").fetchone()[0]
        financial["partial_cancelled_orders"] = sum(row[0] != "0" for row in connection.execute("SELECT filled_quantity FROM uta_orders WHERE status='CANCELLED'"))
        financial["credit"] = dict(connection.execute("SELECT kind,COUNT(*) FROM credit_commands GROUP BY kind"))
        errors = connection.execute("SELECT COUNT(*) FROM soak_evidence WHERE kind='ROUND_UNKNOWN_OR_FAILED'").fetchone()[0]
        full = next((row for row in connection.execute("SELECT sequence,at_ns,payload FROM soak_evidence WHERE kind='VERIFIED' ORDER BY sequence DESC")
                     if json.loads(row["payload"]).get("full") is True), None)
        last = connection.execute("SELECT MAX(sequence) FROM soak_evidence").fetchone()[0]
        market = json.loads(connection.execute("SELECT payload FROM uta_market WHERE singleton=1").fetchone()[0])
        expected = {"uta_matches": 2 * len(done), "uta_fills": 4 * len(done),
            "uta_orders": 4 * len(done) + 2 * sum(i % 10 == 5 for i in done), "uta_positions": 0,
            "cancelled_orders": sum(i % 10 == 0 for i in done) + 2 * sum(i % 10 == 5 for i in done),
            "partial_cancelled_orders": sum(i % 10 == 0 for i in done), "live_orders": 0}
        expected_credit = sum(i % 60 == 0 for i in done)
        golden_matches = (all(financial[key] == value for key, value in expected.items())
            and all(financial["credit"].get(kind, 0) == expected_credit for kind in ("borrowed", "interest_accrued", "repaid")))
        return {"counts": counts, "sessions": sessions, "stored_status": meta["status"],
            "logs_verified": meta.get("logs_verified") == "true", "financial_counts": financial,
            "inflight": sum(counts.get(name, 0) for name in ("queued", "active", "pending")),
            "expected_for_completed_rounds": expected, "golden_matches": golden_matches,
            "round_errors": errors, "export_cursor": int(meta["export_cursor"]),
            "last_evidence_sequence": last,
            "latest_full_verification": dict(full) if full else None,
            "market": {"version": market["version"], "observed_at": market["observed_at"]}}
    finally:
        connection.close()


def audit_logs(job, checkpoint):
    """Final-only audit. A live exporter may still legitimately have a tail."""
    manifest = json.loads((job / "logs/manifest.json").read_text())
    next_sequence = 1
    for name, proof in sorted(manifest["segments"].items()):
        path = job / "logs" / name
        if (job / "logs").resolve() not in path.resolve().parents:
            raise RuntimeError("log manifest path escapes its evidence directory")
        data = path.read_bytes()
        if len(data) != proof["bytes"] or sha256(data).hexdigest() != proof["sha256"]:
            raise RuntimeError("final log segment checksum mismatch")
        sequences = [json.loads(line)["sequence"] for line in gzip.decompress(data).splitlines()]
        if (proof["first"] != next_sequence or proof["rows"] != len(sequences)
                or sequences != list(range(next_sequence, proof["last"] + 1))):
            raise RuntimeError("final log sequence has a gap or duplicate")
        next_sequence = proof["last"] + 1
    if next_sequence - 1 != checkpoint["export_cursor"] or checkpoint["export_cursor"] != checkpoint["last_evidence_sequence"]:
        raise RuntimeError("final log coverage differs from durable evidence checkpoint")
    return {"passed": True, "rows": next_sequence - 1, "segments": len(manifest["segments"])}


def assess(definition, status, database, process, *, now_ns, final_audit=None):
    started = definition["started_ns"]
    duration = definition["configuration"]["duration"]
    expected_deadline = started + int(duration * 1e9)
    if (definition["deadline_ns"] != expected_deadline or status["original_started_ns"] != started
            or status["deadline_ns"] != expected_deadline or status["source_commit"] != definition["environment"]["commit"]):
        raise RuntimeError("actual original start/deadline/source binding changed")
    sessions = database["sessions"]
    latest = sessions[-1] if sessions else None
    earliest = min((session["started_ns"] for session in sessions), default=0)
    if not latest or not started <= earliest <= started + 60_000_000_000:
        raise RuntimeError("producer sessions contradict original start")
    heartbeat_age = (now_ns - latest["heartbeat_ns"]) / 1e9
    threshold = max(30, 3 * definition["configuration"]["heartbeat_interval"])
    active_ns = sum(session["active_ns"] for session in sessions)
    wall_ns = now_ns - started
    if active_ns < 0 or active_ns > wall_ns + 1_000_000_000 or heartbeat_age < -1:
        raise RuntimeError("producer active/heartbeat clocks contradict actual observation")
    alerts = []
    running = database["stored_status"] in ("initialized", "running")
    if running and not process["alive"]:
        alerts.append("producer_exited_or_pid_reused")
    if running and heartbeat_age > threshold:
        alerts.append("heartbeat_stale")
    if database["round_errors"]:
        alerts.append("recorded_unknown_round")
    if any(database["counts"].get(key, 0) for key in ("overload", "missed_downtime", "missed_deadline")):
        alerts.append("arrival_gap_or_overload")
    # queued/active/pending can legitimately contribute extra orders, positions
    # and credit obligations beyond the completed-round golden. Never call this
    # a financial mismatch while a round is in flight.
    golden_state = "inflight_indeterminate" if database["inflight"] else ("quiescent_matches" if database["golden_matches"] else "quiescent_requires_review")
    if not database["inflight"] and not database["golden_matches"]:
        alerts.append("quiescent_golden_requires_review")
    terminal = database["stored_status"] == "completed"
    elapsed = duration >= 86400 and wall_ns >= int(duration * 1e9) and active_ns >= int(duration * 1e9)
    full = json.loads(database["latest_full_verification"]["payload"]) if database["latest_full_verification"] else {}
    verified = full.get("counts", {})
    independent = verified.get("independent_reconciliation", {})
    final_replay_covers_state = (full.get("full") is True and independent.get("status") == "passed"
        and independent.get("unpaired_fills") == 0
        and all(verified.get(key) == database["financial_counts"][key] for key in ("uta_orders", "uta_matches", "uta_fills")))
    eligible = bool(terminal and elapsed and len(sessions) == 1 and sessions[0]["status"] == "completed"
        and database["counts"] == {"done": definition["planned_rounds"]}
        and golden_state == "quiescent_matches" and database["logs_verified"]
        and final_replay_covers_state and not alerts and final_audit and final_audit.get("passed"))
    return {"observer_state": "final_review_eligible" if eligible else ("attention" if alerts else "observing_pending"),
        "alerts": alerts, "process": process, "heartbeat_age_seconds": heartbeat_age,
        "heartbeat_threshold_seconds": threshold, "golden_state": golden_state,
        "actual_wall_seconds": wall_ns / 1e9, "confirmed_active_seconds": active_ns / 1e9,
        "original_start_ns": started, "original_deadline_ns": expected_deadline,
        "actual_24h_elapsed": elapsed, "final_audit": final_audit,
        "final_independent_replay_covers_financial_state": final_replay_covers_state,
        "eligible_for_independent_final_review": eligible,
        "stability_24h_approved": False, "production_approved": False, "capacity_10000_approved": False}


def observe(directory, *, source=None, expected_definition_hash=None):
    job = Path(directory).absolute()
    data = (job / "job.json").read_bytes()
    digest = sha256(data).hexdigest()
    if expected_definition_hash is not None and digest != expected_definition_hash:
        raise RuntimeError("immutable job definition changed during observation")
    definition = json.loads(data)
    if (job / "authority.sqlite3").stat().st_ino != definition["database_inode"]:
        raise RuntimeError("original financial authority was replaced")
    root = producer_source(job, definition, source)
    command = [sys.executable, str(root / "benchmarks/run_soak.py"), "status", "--directory", str(job)]
    call_started = time.time_ns()
    result = subprocess.run(command, capture_output=True, text=True, timeout=30,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    call_finished = time.time_ns()
    if result.returncode:
        raise RuntimeError("fixed producer status failed: " + result.stderr[-2000:])
    status = json.loads(result.stdout)
    if not call_started - 1_000_000_000 <= status["observed_ns"] <= call_finished + 1_000_000_000:
        raise RuntimeError("producer status is outside its actual invocation window")
    database = read_database(job)
    latest = database["sessions"][-1] if database["sessions"] else {}
    process = process_state(latest.get("pid"), latest.get("process_identity"))
    final_audit = None
    if database["stored_status"] == "completed" and database["logs_verified"] and not database["inflight"]:
        final_audit = audit_logs(job, database)
    now = time.time_ns()
    assessment = assess(definition, status, database, process, now_ns=now, final_audit=final_audit)
    if (job / "job.json").read_bytes() != data:
        raise RuntimeError("job definition changed within observation")
    return {"observed_utc": datetime.fromtimestamp(now / 1e9, timezone.utc).isoformat(), "observed_ns": now,
        "producer_source_commit": definition["environment"]["commit"], "producer_source": str(root),
        "job_directory": str(job), "job_definition_sha256": digest, "producer_status_command": command,
        "producer_status_call_ns": {"started": call_started, "finished": call_finished},
        "producer_status": status, "read_only_database_snapshot": database, "assessment": assessment,
        "observer_script_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}


def atomic(path, value, staging):
    # The producer recursively stats its job directory. Never expose an
    # observer temporary file there that can disappear between glob and stat.
    descriptor, name = tempfile.mkstemp(prefix="observation-", dir=staging)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(json.dumps(value, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def watch(directory, output, *, source=None, duration=86400, interval=60, stop=None, max_bytes=64 * 1024**2):
    if (isinstance(duration, bool) or isinstance(interval, bool) or not math.isfinite(duration)
            or not math.isfinite(interval) or not 0 < duration <= 172800 or not 10 <= interval <= 3600):
        raise ValueError("watch duration must be in (0,172800], interval in [10,3600]")
    if type(max_bytes) is not int or not 1024**2 <= max_bytes <= 256 * 1024**2:
        raise ValueError("observer budget must be 1..256MiB")
    job, output = Path(directory).resolve(), Path(output).resolve()
    if job not in output.parents or not output.relative_to(job).parts[0].startswith("observer"):
        raise ValueError("observer output must be a distinct observer* subdirectory of the job")
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(output, 0o700)
    lock = os.open(output / "observer.lock", os.O_RDWR | os.O_CREAT, 0o600)
    staging = None
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (output / "observer.json").exists():
            raise ValueError("existing observations cannot be overwritten; use a new observer directory")
        staging = Path(tempfile.mkdtemp(prefix=".soak-observer-stage-", dir=job.parent))
        if staging.stat().st_dev != output.stat().st_dev:
            raise ValueError("observer staging must share the job filesystem for atomic rename")
        save = lambda name, value: atomic(output / name, value, staging)
        stop = stop or Event()
        definition_hash = sha256((job / "job.json").read_bytes()).hexdigest()
        started = time.monotonic()
        metadata = {"pid": os.getpid(), "started_utc": datetime.now(timezone.utc).isoformat(),
            "requested_duration_seconds": duration, "interval_seconds": interval, "max_bytes": max_bytes,
            "job_definition_sha256": definition_hash, "source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
            "observer_source_commit": subprocess.check_output(("git", "rev-parse", "HEAD"), cwd=Path(__file__).resolve().parents[1], text=True).strip(),
            "readonly_producer": True, "stability_24h_approved": False}
        save("observer.json", metadata)
        manifest, observations, hours = {"observations": {}}, 0, set()
        end_reason = "operator_stop"
        while not stop.is_set() and not (output / "STOP").exists():
            at = time.monotonic()
            try:
                row = observe(job, source=source, expected_definition_hash=definition_hash)
            except Exception as error:
                row = {"observed_utc": datetime.now(timezone.utc).isoformat(),
                    "observer_error": {"type": type(error).__name__, "message": str(error)},
                    "stability_24h_approved": False, "production_approved": False}
            observations += 1
            name = f"observation-{observations:06d}.json"
            save(name, row)
            data = (output / name).read_bytes()
            manifest["observations"][name] = {"bytes": len(data), "sha256": sha256(data).hexdigest()}
            save("manifest.json", manifest)
            save("latest.json", row)
            if "assessment" in row:
                hour = max(0, int(row["assessment"]["actual_wall_seconds"] // 3600))
                if hour not in hours:
                    save(f"producer-hour-{hour:03d}.json", row)
                    hours.add(hour)
            size = sum(path.stat().st_size for path in output.iterdir() if path.is_file())
            if size > max_bytes or observations >= 18000:
                raise RuntimeError("bounded observer evidence budget exhausted")
            if row.get("assessment", {}).get("eligible_for_independent_final_review"):
                end_reason = "producer_final_review_eligible"
                break
            if time.monotonic() - started >= duration:
                end_reason = "requested_observer_duration_elapsed"
                break
            stop.wait(min(interval - min(interval, time.monotonic() - at), max(0, duration - (time.monotonic() - started))))
        result = {**metadata, "ended_utc": datetime.now(timezone.utc).isoformat(),
            "actual_watch_seconds": time.monotonic() - started, "observations": observations,
            "end_reason": end_reason,
            "scope": "read-only observations; final stability acceptance is a separate review"}
        save("observer-ended.json", result)
        return result
    finally:
        os.close(lock)
        if staging is not None:
            staging.rmdir()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--producer-source", type=Path)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--duration", type=float, default=86400)
    parser.add_argument("--interval", type=float, default=60)
    args = parser.parse_args(argv)
    try:
        if args.watch:
            if args.output is None:
                raise ValueError("--output observer directory is required for watch")
            stop = Event()
            for signum in (signal.SIGTERM, signal.SIGINT):
                signal.signal(signum, lambda number, frame: stop.set())
            result = watch(args.directory, args.output, source=args.producer_source,
                           duration=args.duration, interval=args.interval, stop=stop)
        else:
            result = observe(args.directory, source=args.producer_source)
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError, sqlite3.Error, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
