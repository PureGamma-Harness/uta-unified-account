"""Independent synthetic managed-soak observer. Never imports application code.

Only the explicitly requested ``producer-audit`` command runs the frozen
producer's audited read-only CLI, after proving the authority has stopped.
Observation itself uses SQLite read transactions and /proc/stat, never HTTP,
auth storage, private files, service constructors, schema repair or signals.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import errno
from hashlib import sha256
import gzip
import json
import math
import os
from pathlib import Path
import re
import resource
import signal
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
from threading import Event
import time

sys.dont_write_bytecode = True
try:
    from tools.managed_observer_finance import read_financial
except ModuleNotFoundError:
    from managed_observer_finance import read_financial

ACCOUNTS = ["managed-soak-alice", "managed-soak-bob", "managed-soak-credit"]
FLAGS = {"continuous_6h_stability_passed": False, "continuous_24h_stability_passed": False,
         "production_approved": False, "capacity_10000_per_s_passed": False}
COMMAND_STEPS = {"open-buy", "open-sell", "cancel-partial", "close-sell", "close-buy", "repay"}
VALIDATION_COUNTS = ("failures", "errors", "skipped", "expected_failures", "unexpected_successes")
VALIDATION_FLAGS = ("passed", "unittest_passed", "source_unchanged", "tracked_source_clean_before", "tracked_source_clean_after")
VALIDATION_ARTIFACTS = ("summary.json", "worker-result.json", "unittest.txt")
PRODUCER_AUDIT_SCOPE = "private_complete_sqlite_clone_of_stopped_authority"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return sha256(canonical(value).encode()).hexdigest()


def parse(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate_json_key")
            result[key] = value
        return result
    def invalid(_):
        raise ValueError("nonfinite_json")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def load_json(path):
    return parse(Path(path).read_text())


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("finite_number_required")
    return value


def integer(value, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError("integer_required")
    return value


def public_code(value):
    # Never copy exception text, URLs, SQL payloads or unknown command IDs.
    if value is None:
        return None
    if value in {"worker", "parent", "market_fanout_incomplete", "market_barrier_mismatch",
                 "publication_incomplete", "activation_incomplete", "activation_market_invalid"}:
        return value
    return "redacted:" + digest(value)


def process_identity(pid, expected_birth=None, *, proc=Path("/proc")):
    integer(pid, 1)
    try:
        fields = (proc / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()
        state, birth = fields[0], fields[19]
    except OSError as error:
        absent = error.errno in {errno.ENOENT, errno.ESRCH}
        return {"pid": pid, "birth": None, "state": "missing" if absent else "unavailable",
            "visibility": "absent" if absent else "unknown", "identity_matches": False,
            "alive": False, "known_stopped": absent}
    except IndexError:
        return {"pid": pid, "birth": None, "state": "malformed", "visibility": "unknown",
            "identity_matches": False, "alive": False, "known_stopped": False}
    if not birth.isdecimal() or state not in {"R", "S", "D", "Z", "T", "t", "X", "x", "K", "W", "P", "I"}:
        return {"pid": pid, "birth": None, "state": "malformed", "visibility": "unknown",
            "identity_matches": False, "alive": False, "known_stopped": False}
    matches = expected_birth is not None and str(expected_birth) == birth
    stopped = state in {"Z", "X", "x"} or expected_birth is not None and not matches
    return {"pid": pid, "birth": birth, "state": state, "visibility": "observed", "identity_matches": matches,
            "alive": matches and not stopped, "known_stopped": stopped}


def safe_standard_descriptors():
    """Do not emit even an error through a pre-opened regular-file writer.

    Mount read-only flags do not constrain an inherited writable descriptor.
    Trusted launchers must use pipes/TTYs and save output only in their explicit
    observer directory. subprocess close_fds removes every nonstandard FD.
    """
    for descriptor in (0, 1, 2):
        try:
            if stat.S_ISREG(os.fstat(descriptor).st_mode):
                return False
        except OSError:
            return False
    return True


@contextmanager
def readonly(path, *, cold=False):
    """SQLite owns and closes its descriptor; never raw-open/close its inode.

    No immutable/nolock shortcut: live WAL must be visible and locks respected.
    Live reads require existing WAL sidecars; CLI additionally enforces a
    kernel read-only mount to close the sidecar stat/open race. Immutable is
    allowed only for a stopped authority with no sidecars, never for live WAL.
    """
    path = Path(path).absolute()
    if path.is_symlink() or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("sqlite_regular_file_required")
    wal, shm = Path(str(path) + "-wal"), Path(str(path) + "-shm")
    deadline = time.monotonic() + (0 if cold else 5)
    while not cold and not (wal.exists() and shm.exists()) and time.monotonic() < deadline:
        time.sleep(.02)
    complete = wal.exists() and shm.exists()
    if not complete and (not cold or wal.exists() or shm.exists()):
        raise ValueError("wal_sidecar_snapshot_unavailable")
    uri = path.as_uri() + "?mode=ro" + ("&immutable=1" if cold and not complete else "")
    connection = sqlite3.connect(uri, uri=True, timeout=2, isolation_level=None)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only=ON")
        def authorize(action, first, second, _db, _source):
            if action in {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION,
                          sqlite3.SQLITE_TRANSACTION, getattr(sqlite3, "SQLITE_RECURSIVE", 33)}:
                return sqlite3.SQLITE_OK
            if action == sqlite3.SQLITE_PRAGMA and first.lower() in {
                    "query_only", "quick_check", "foreign_key_check", "table_info"} and second is None:
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY
        connection.set_authorizer(authorize)
        connection.execute("BEGIN")
        yield connection
    finally:
        connection.close()


def checkpoint(path, *, cold=False):
    with readonly(path, cold=cold) as connection:
        states = {row[0]: parse(row[1]) for row in connection.execute(
            "SELECT key,value FROM state WHERE key IN ('started_boottime_ns','boot_id','controller_sessions','logs_verified','listener')")}
        rows = [dict(row) for row in connection.execute(
            "SELECT sequence,planned_ns,state,completed_ns FROM rounds ORDER BY sequence")]
        steps = []
        for row in connection.execute("SELECT round,name,state,plan FROM steps ORDER BY round,name"):
            plan = parse(row[3])
            step = {"round": row[0], "name": row[1], "state": row[2]}
            if row[1] in COMMAND_STEPS:
                step.update(command_id=plan["payload"]["command_id"], account=plan["account"],
                            payload_sha256=plan["payload_sha256"])
                if sha256(canonical(plan["payload"]).encode()).hexdigest() != step["payload_sha256"]:
                    raise ValueError("original_checkpoint_payload_digest_invalid")
            steps.append(step)
        faults = [dict(row) for row in connection.execute("SELECT round,kind,state,evidence FROM faults ORDER BY round,kind")]
        head = connection.execute("SELECT sequence,event_hash FROM events ORDER BY sequence DESC LIMIT 1").fetchone()
        controller = connection.execute(
            "SELECT payload FROM events WHERE kind='CONTROLLER_STARTED' ORDER BY sequence DESC LIMIT 1").fetchone()
        ended = connection.execute(
            "SELECT payload FROM events WHERE kind='CONTROLLER_ENDED' ORDER BY sequence DESC LIMIT 1").fetchone()
    for key in ("started_boottime_ns", "boot_id", "controller_sessions", "logs_verified", "listener"):
        if key not in states:
            raise ValueError("checkpoint_required_state_missing")
    integer(states["controller_sessions"], 1)
    if type(states["logs_verified"]) is not bool or not isinstance(states["boot_id"], str):
        raise ValueError("checkpoint_required_state_type_invalid")
    integer(states["listener"]["pid"], 1)
    if not str(states["listener"]["birth"]).isdecimal():
        raise ValueError("listener_birth_missing")
    if head is None or controller is None:
        raise ValueError("checkpoint_event_head_missing")
    for index, row in enumerate(rows, 1):
        if row["sequence"] != index or row["state"] not in {"ACTIVE", "DONE"}:
            raise ValueError("round_sequence_or_state_invalid")
        integer(row["planned_ns"])
        if row["state"] == "DONE":
            integer(row["completed_ns"])
            if row["completed_ns"] < row["planned_ns"]:
                raise ValueError("round_completion_clock_regressed")
    done = sum(row["state"] == "DONE" for row in rows)
    if any(row["state"] == "DONE" for row in rows[done:]):
        raise ValueError("round_completion_gap")
    public_faults = []
    for row in faults:
        evidence = parse(row["evidence"])
        public_faults.append({"round": row["round"], "kind": public_code(row["kind"]), "state": row["state"],
            "signal_sent": evidence.get("signal_sent"), "old_generation": evidence.get("old_generation"),
            "new_generation": evidence.get("new_generation")})
    return {"states": states, "rounds": rows, "steps": steps, "faults": public_faults,
        "completed": done, "active_rounds": [row["sequence"] for row in rows if row["state"] != "DONE"],
        "unresolved_steps": sum(row["state"] != "DONE" for row in steps),
        "unresolved_faults": sum(row["state"] != "DONE" for row in faults),
        "event_head": {"sequence": head[0], "hash": head[1]}, "driver_pid": parse(controller[0])["pid"],
        "controller_ended": None if ended is None else parse(ended[0])}


def original_command_coverage(meta, cp, finance):
    expected = {f"ms:{meta['job_id']}:r{sequence:09d}:{name}"
                for sequence in range(1, cp["completed"] + 1) for name in COMMAND_STEPS}
    planned = [step["command_id"] for step in cp["steps"] if step["name"] in COMMAND_STEPS]
    actual = [item["command_id"] for item in finance["command_inbox"] if not item["control_lane"]]
    return len(planned) == len(actual) == len(expected) and set(planned) == set(actual) == expected


def logical_checkpoint(snapshot):
    return digest({key: snapshot[key] for key in ("event_head", "rounds", "steps", "faults", "states")})


def read_control(path, *, cold=False):
    with readonly(path, cold=cold) as connection:
        row = connection.execute("SELECT descriptor,payload FROM router_layout JOIN router_state USING(singleton) WHERE singleton=1").fetchone()
        if row is None:
            raise ValueError("router_state_missing")
        layout, state = parse(row[0]), parse(row[1])
        for key in ("halted", "publishing", "epoch", "market_version", "market_digest", "watermarks", "error"):
            if key not in state:
                raise ValueError("router_state_field_missing")
        if layout["shard_count"] != 1 or layout["scales"] != {"USD": 8, "BTC": 8}:
            raise ValueError("fixed_single_shard_layout_changed")
        if type(state["halted"]) is not bool or type(state["publishing"]) is not bool:
            raise ValueError("control_boolean_invalid")
        integer(state["epoch"])
        for key in ("market_version", "target_version"):
            if state.get(key) is not None:
                integer(state[key], 1)
        for key in ("market_digest", "target_digest"):
            if state.get(key) is not None and not re.fullmatch(r"[0-9a-f]{64}", state[key]):
                raise ValueError("control_market_digest_invalid")
        if not isinstance(state["watermarks"], dict) or not set(state["watermarks"]) <= {"0"}:
            raise ValueError("control_watermark_map_invalid")
        for value in state["watermarks"].values():
            integer(value, 1)
        # Explicit projection excludes coordinator/worker nonces and audience.
        owners = [dict(row) for row in connection.execute(
            "SELECT kind,shard,generation,pid,start_ticks,boot_id,observed_at FROM router_process_owners ORDER BY sequence")]
    control = {key: state[key] for key in ("halted", "publishing", "epoch", "market_version", "market_digest", "watermarks")}
    for key in ("durable_market_commands", "durable_halt_commands"):
        mapping = state.get(key, {})
        if not isinstance(mapping, dict) or not set(mapping) <= {"0"} or not all(isinstance(value, str) for value in mapping.values()):
            raise ValueError("control_command_map_invalid")
        control[key] = {shard: "sha256:" + digest(cid) for shard, cid in mapping.items()}
    control["error"] = public_code(state["error"])
    return control, owners


def read_health(connection, owners, now_ns, boot, wall_ns):
    row = connection.execute(
        "SELECT generation,owner_pid,boot_id,expires_ns,observed_ns FROM writer_fence_lease WHERE singleton=1").fetchone()
    if row is None:
        raise ValueError("writer_lease_missing")
    lease = dict(row)
    registration = next((item for item in reversed(owners)
                         if (lease["owner_pid"] is None or item["pid"] == lease["owner_pid"])
                         and item["generation"] == lease["generation"] and item["kind"] == "OWNED"), None)
    observed_pid = lease["owner_pid"] if lease["owner_pid"] is not None else (None if registration is None else registration["pid"])
    process = None if observed_pid is None else process_identity(observed_pid,
        None if registration is None else registration["start_ticks"])
    local = connection.execute("SELECT value FROM uta_config WHERE key='halted'").fetchone()
    market = connection.execute("SELECT payload FROM uta_market WHERE singleton=1").fetchone()
    if local is None or market is None:
        raise ValueError("local_market_or_halt_missing")
    market = parse(market[0])
    timestamp = datetime.fromisoformat(market["observed_at"].replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        raise ValueError("market_timezone_missing")
    age = wall_ns / 1e9 - timestamp.timestamp()
    heartbeat_age = (now_ns - lease["observed_ns"]) / 1e9
    same_boot = lease["boot_id"] == boot
    return {"generation": lease["generation"], "process": process,
        "registered_birth": registration is not None,
        "lease_same_boot": same_boot, "lease_active": same_boot and lease["owner_pid"] is not None
            and lease["observed_ns"] <= now_ns < lease["expires_ns"],
        "heartbeat_age_seconds": heartbeat_age, "heartbeat_future": heartbeat_age < 0,
        "locally_active": local[0] == "false", "market_version": market["version"],
        "market_digest": sha256(canonical(market).encode()).hexdigest(),
        "market_observed_at": timestamp.isoformat(), "market_age_seconds": age,
        "market_fresh": 0 <= age <= 30, "market_future": age < 0}


def validate_metadata(meta, cp, frozen_commit):
    config, env = meta["configuration"], meta["environment"]
    duration, rate = number(config["duration"]), number(config["rate"])
    planned = integer(meta["planned_rounds"], 1)
    started = integer(cp["states"]["started_boottime_ns"], 1)
    if duration < 4 or duration > 86400 or rate != .25 or planned != math.ceil(duration * rate):
        raise ValueError("immutable_workload_budget_invalid")
    if meta["accounts"] != ACCOUNTS or env["synthetic"] is not True or meta["bootstrap"]["synthetic_only"] is not True:
        raise ValueError("synthetic_workload_identity_invalid")
    if env["commit"] != frozen_commit or not re.fullmatch(r"[0-9a-f]{40}", frozen_commit):
        raise ValueError("frozen_commit_changed")
    if meta["bootstrap"]["initial_principal_satoshi"] != 2 * planned:
        raise ValueError("gross_bootstrap_budget_changed")
    deadline = started + int(duration * 1e9)
    for row in cp["rounds"]:
        if row["sequence"] > planned or row["planned_ns"] != started + (row["sequence"] - 1) * 4_000_000_000:
            raise ValueError("original_round_schedule_changed")
    return {"job_id_sha256": digest(meta["job_id"]), "job_manifest_sha256": digest(meta),
        "frozen_commit": frozen_commit, "source_sha256": env["source_sha256"],
        "workload_spec_sha256": env["workload_spec_sha256"], "started_boottime_ns": started,
        "deadline_boottime_ns": deadline, "boot_id": cp["states"]["boot_id"],
        "duration_seconds": duration, "planned_rounds": planned,
        "file_identities_sha256": digest(meta["file_identities"])}


def check_source(source, meta, frozen_commit):
    source = Path(source).resolve()
    def git(*args):
        return subprocess.check_output(["git", "--no-optional-locks", *args], cwd=source, text=True,
            stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, close_fds=True).strip()
    if git("rev-parse", "HEAD") != frozen_commit or git("status", "--porcelain", "--untracked-files=all"):
        raise ValueError("frozen_source_changed_or_dirty")
    manifests = [meta["environment"]["source_sha256"]]
    evidence = meta["validation_evidence"]
    if evidence is None or evidence["code_commit"] != frozen_commit or evidence["engineering_test_qualified"] is not True:
        raise ValueError("exact_release_validation_missing")
    if set(evidence["artifact_sha256"]) != {"summary.json", "worker-result.json", "unittest.txt"}:
        raise ValueError("validation_artifact_name_invalid")
    for manifest in manifests:
        for relative, expected in manifest.items():
            path = source / relative
            if path.resolve().is_relative_to(source) is False or sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError("frozen_source_bytes_changed")
    if sha256((source / "docs/managed-soak-golden.md").read_bytes()).hexdigest() != meta["environment"]["workload_spec_sha256"]:
        raise ValueError("frozen_workload_spec_changed")


def validation_manifest(job, source, meta):
    evidence = meta["validation_evidence"]
    if evidence is None:
        raise ValueError("exact_release_validation_missing")
    artifacts = {name: (job / "validation" / name).read_bytes() for name in VALIDATION_ARTIFACTS}
    for name, raw in artifacts.items():
        if sha256(raw).hexdigest() != evidence["artifact_sha256"][name]:
            raise ValueError("validation_artifact_changed")
    report, worker = parse(artifacts["summary.json"]), parse(artifacts["worker-result.json"])
    if (report["code_commit"] != meta["environment"]["commit"] or report["source_sha256"] != report["source_sha256_after"]
            or evidence["code_commit"] != report["code_commit"] or evidence["engineering_test_qualified"] is not True):
        raise ValueError("validation_source_manifest_changed")
    if any(report.get(key) is not True for key in VALIDATION_FLAGS) or worker.get("unittest_passed") is not True:
        raise ValueError("validation_literal_success_required")
    if report.get("production_approved") is not False:
        raise ValueError("validation_cannot_grant_production_approval")
    integer(report["tests_run"], 1)
    if evidence["tests_run"] != report["tests_run"] or type(evidence["tests_run"]) is not int:
        raise ValueError("validation_executed_count_changed")
    for key in ("tests_run", *VALIDATION_COUNTS, "unittest_passed"):
        if worker.get(key) != report.get(key) or type(worker.get(key)) is not type(report.get(key)):
            raise ValueError("validation_worker_summary_disagree")
    for key in (*VALIDATION_COUNTS, "worker_exit_code"):
        if type(report.get(key)) is not int or report[key] != 0:
            raise ValueError("validation_nonzero_or_unexecuted_outcome")
    for key in ("python", "sqlite"):
        if report[key] != meta["environment"][key] or report[key] != evidence[key]:
            raise ValueError("validation_exact_producer_runtime_changed")
    argv = report["command_argv"]
    if (not isinstance(argv, list) or len(argv) != 4 or not all(isinstance(value, str) for value in argv)
            or Path(argv[1]).parts[-2:] != ("tools", "run_validation.py") or argv[2] != "--output"):
        raise ValueError("validation_complete_runner_command_required")
    if report["test_log_sha256"] != sha256(artifacts["unittest.txt"]).hexdigest():
        raise ValueError("validation_raw_log_digest_changed")
    if not re.search(r"^Ran " + str(report["tests_run"]) + r" tests? in .+\n\nOK\s*\Z",
                     artifacts["unittest.txt"].decode(), re.MULTILINE):
        raise ValueError("validation_raw_log_not_successful")
    root = source.resolve()
    paths = {path for folder in ("uta", "tests", "formal", "tools", "benchmarks", "scripts")
             for path in (root / folder).rglob("*.py")}
    paths.update(path for path in (root / "tests/fixtures").rglob("*") if path.is_file())
    paths.update(root / name for name in ("pyproject.toml", "MANIFEST.in", "LICENSE") if (root / name).exists())
    expected_paths = {path.relative_to(root).as_posix() for path in paths}
    required = {"tools/run_validation.py", "benchmarks/run_managed_soak.py", "benchmarks/managed_qualification.py",
                "benchmarks/run_soak.py", "benchmarks/run_benchmark.py"}
    if (set(report["source_sha256"]) != expected_paths or not required <= expected_paths
            or not any(name.startswith("uta/") for name in expected_paths)):
        raise ValueError("validation_complete_source_inventory_required")
    tracked = set(subprocess.check_output(["git", "--no-optional-locks", "ls-files", "-z"], cwd=root,
        text=True, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, close_fds=True).split("\0"))
    if not expected_paths <= tracked:
        raise ValueError("validation_input_not_in_frozen_commit")
    for relative, expected in report["source_sha256"].items():
        path = root / relative
        if not path.resolve().is_relative_to(root) or sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("complete_validation_source_bytes_changed")


def verify_logs(job, head):
    manifest = load_json(job / "log-segments.json")
    sequence, previous = 0, "0" * 64
    for segment in manifest["segments"]:
        relative = log_relative(segment["file"])
        target = job / relative
        if target.is_symlink() or segment["first"] != sequence + 1 or sha256(target.read_bytes()).hexdigest() != segment["sha256"]:
            raise ValueError("log_segment_continuity_or_digest_failed")
        with gzip.open(target, "rt") as stream:
            for line in stream:
                row = parse(line)
                sequence += 1
                fingerprint = digest([sequence, row["kind"], row["payload"], previous])
                if row["sequence"] != sequence or row["previous_hash"] != previous or row["event_hash"] != fingerprint:
                    raise ValueError("log_event_chain_failed")
                previous = fingerprint
        if segment["last"] != sequence:
            raise ValueError("log_segment_end_failed")
    if head != {"sequence": sequence, "hash": previous}:
        raise ValueError("final_logs_do_not_cover_checkpoint")
    return {"events": sequence, "last_hash": previous, "verified": True}


def log_relative(value):
    relative = Path(value)
    if relative.is_absolute() or len(relative.parts) != 2 or relative.parts[0] != "logs" or relative.suffix != ".gz":
        raise ValueError("log_segment_path_invalid")
    return relative


def identity_files(job, meta):
    # Explicit allowlist; do not open/stat the auth DB or private directory.
    for relative in ("checkpoint.sqlite3", "managed/router.sqlite3", "managed/shard-0000.sqlite3"):
        path = job / relative
        details = path.stat()
        if path.is_symlink() or [details.st_dev, details.st_ino] != meta["file_identities"][str(path)]:
            raise ValueError("original_authority_file_identity_changed")


def watermark(cp, finance, contract):
    return {"checkpoint": cp["event_head"], "financial": finance["watermark"],
        "contract_sha256": digest(contract)}


def atomic_json(path, value):
    path = Path(path)
    descriptor, temporary = tempfile.mkstemp(prefix=".observer-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(canonical(value) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        Path(temporary).unlink(missing_ok=True)


def private_write(path, raw):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)


def output_directory(job, output):
    job, output = Path(job).resolve(), Path(output).resolve()
    if output == job or output.is_relative_to(job) or job.is_relative_to(output):
        raise ValueError("observer_output_must_be_separate_from_job")
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    details = output.stat()
    if details.st_uid != os.geteuid() or stat.S_IMODE(details.st_mode) != 0o700:
        raise ValueError("observer_output_must_be_private_owned_0700")
    return job, output


class Observer:
    def __init__(self, job, output, source, frozen_commit, driver_pid, driver_birth, *, producer_receipt=None,
                 max_private_clone_bytes=6 * 1024**3, min_private_free_bytes=1024**3,
                 collector_input_v2=False, report_protocol="legacy"):
        self.job, self.output = output_directory(job, output)
        self.source, self.frozen_commit = Path(source), frozen_commit
        if self.output.is_relative_to(self.source.resolve()):
            raise ValueError("observer_output_must_be_outside_source")
        self.driver_pid, self.driver_birth = integer(driver_pid, 1), str(driver_birth)
        if not self.driver_birth.isdecimal():
            raise ValueError("explicit_driver_birth_required")
        self.producer_receipt = None if producer_receipt is None else Path(producer_receipt)
        self.cold = False
        self.max_private_clone_bytes = integer(max_private_clone_bytes, 1)
        self.min_private_free_bytes = integer(min_private_free_bytes)
        self.collector_input_v2 = collector_input_v2
        if report_protocol not in {"legacy", "compact-v2"}:
            raise ValueError("unsupported_observer_report_protocol")
        self.report_protocol = report_protocol

    def contract(self, meta, cp):
        result = validate_metadata(meta, cp, self.frozen_commit)
        result.update(driver_pid=self.driver_pid, driver_birth=self.driver_birth)
        result["observer_code_sha256"] = {path.name: sha256(path.read_bytes()).hexdigest()
            for path in (Path(__file__), Path(__file__).with_name("managed_observer_finance.py"))}
        if getattr(self, "report_protocol", "legacy") == "compact-v2":
            result["observer_output_protocol"] = "full-input-v2-to-post-consumer-compact-v2"
            for name in ("managed_observer_report.py", "managed_observer_transport.py",
                         "managed_observer_coverage.py", "run_managed_long.py"):
                result["observer_code_sha256"][name] = sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
        return result

    def recheck_final_contract(self, contract, progress, cp):
        latest_meta, latest_progress = load_json(self.job / "job.json"), load_json(self.job / "progress.json")
        check_source(self.source, latest_meta, self.frozen_commit)
        validation_manifest(self.job, self.source, latest_meta)
        identity_files(self.job, latest_meta)
        return self.contract(latest_meta, cp) == contract and latest_progress == progress

    def sample(self):
        wall_ns, now_ns = time.time_ns(), time.clock_gettime_ns(time.CLOCK_BOOTTIME)
        boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        meta, progress = load_json(self.job / "job.json"), load_json(self.job / "progress.json")
        # Only an already observed driver can transition to cold immutable
        # reads. A new observer cannot invent a baseline after the driver exits.
        initial_driver = process_identity(self.driver_pid, self.driver_birth)
        self.cold = (progress["status"] == "completed" and initial_driver["known_stopped"]
                     and (self.output / "baseline.json").exists())
        before = checkpoint(self.job / "checkpoint.sqlite3", cold=self.cold)
        contract = self.contract(meta, before)
        baseline_path = self.output / "baseline.json"
        if baseline_path.exists():
            if load_json(baseline_path) != contract:
                raise ValueError("original_source_start_deadline_or_identity_changed")
        else:
            process = process_identity(self.driver_pid, self.driver_birth)
            if not process["alive"] or before["driver_pid"] != self.driver_pid:
                raise ValueError("initial_actual_driver_birth_not_verified")
            atomic_json(baseline_path, contract)
        check_source(self.source, meta, self.frozen_commit)
        validation_manifest(self.job, self.source, meta)
        identity_files(self.job, meta)
        control, owners = read_control(self.job / "managed/router.sqlite3", cold=self.cold)
        with readonly(self.job / "managed/shard-0000.sqlite3", cold=self.cold) as connection:
            finance = read_financial(connection, contract["planned_rounds"], before["completed"], compare_golden=False)
            now_ns, wall_ns = time.clock_gettime_ns(time.CLOCK_BOOTTIME), time.time_ns()
            health = read_health(connection, owners, now_ns, boot, wall_ns)
        after = checkpoint(self.job / "checkpoint.sqlite3", cold=self.cold)
        stable = logical_checkpoint(before) == logical_checkpoint(after)
        boundary = stable and not (after["active_rounds"] or after["unresolved_steps"] or after["unresolved_faults"])
        if boundary:
            # A second bracket is necessary: time between transactions can admit
            # the next round even when the first checkpoint pair was stable.
            with readonly(self.job / "managed/shard-0000.sqlite3", cold=self.cold) as connection:
                finance2 = read_financial(connection, contract["planned_rounds"], after["completed"], compare_golden=True)
            last = checkpoint(self.job / "checkpoint.sqlite3", cold=self.cold)
            boundary = logical_checkpoint(after) == logical_checkpoint(last) and finance["watermark"] == finance2["watermark"]
            if boundary:
                finance = finance2
                if not original_command_coverage(meta, after, finance):
                    finance["golden"]["passed"] = False
                    finance["golden"]["errors"].append("checkpoint_financial_original_command_identity")
        driver = process_identity(self.driver_pid, self.driver_birth)
        listener = after["states"]["listener"]
        listener_state = process_identity(listener["pid"], listener["birth"])
        elapsed = (now_ns - contract["started_boottime_ns"]) / 1e9 if boot == contract["boot_id"] else None
        if progress["status"] == "completed" and elapsed is not None:
            elapsed = min(elapsed, number(progress["elapsed_seconds"]))
        alerts = []
        if elapsed is None or elapsed < 0:
            alerts.append("original_boot_or_clock_invalid")
        if before["driver_pid"] != self.driver_pid:
            alerts.append("driver_controller_changed")
        progress_age = (wall_ns - (self.job / "progress.json").stat().st_mtime_ns) / 1e9
        if progress_age < 0 or progress_age > max(60, 3 * meta["configuration"]["heartbeat_interval"]):
            alerts.append("progress_future_or_stale")
        if not health["market_fresh"]:
            alerts.append("market_future" if health["market_future"] else "market_stale")
        if health["heartbeat_future"]:
            alerts.append("worker_heartbeat_future")
        if progress["status"] != "completed" and not health.get("lease_active", False):
            alerts.append("worker_lease_inactive_or_unknown")
        if any(row["state"] == "DONE" and row["completed_ns"] > now_ns for row in after["rounds"]):
            alerts.append("round_completion_clock_future")
        if not driver["alive"] and progress["status"] != "completed":
            alerts.append("driver_missing_zombie_or_birth_changed")
        if driver["visibility"] == "unknown" or listener_state["visibility"] == "unknown":
            alerts.append("process_visibility_unknown")
        if health.get("process") is not None and health["process"]["visibility"] == "unknown":
            alerts.append("worker_process_visibility_unknown")
        if finance["retry_alerts"]:
            alerts.append("internal_execution_retry_cause_unknown")
        if any(item["state"] in {"REJECTED", "QUARANTINED"} for item in finance.get("command_inbox", [])):
            alerts.append("terminal_rejection_or_quarantine_observed")
        if progress["error"] is not None:
            alerts.append("producer_reported_error")
        # Raw lease/process/market facts cannot establish claim reconciliation,
        # schema guards or funding registry readiness. Never infer financial ready.
        result = {"format": 1, "synthetic": True, "redacted": True, "observation_only": True,
            "observer_is_formal_signoff": False, "sample_wall_ns": wall_ns,
            "frozen_commit": self.frozen_commit, "contract_sha256": digest(contract),
            "original_start_boottime_ns": contract["started_boottime_ns"],
            "original_deadline_boottime_ns": contract["deadline_boottime_ns"],
            "active_elapsed_seconds": elapsed, "planned_rounds": contract["planned_rounds"],
            "completed_rounds": after["completed"], "active_rounds": after["active_rounds"],
            "logical_point": "stable_boundary" if boundary else "inflight_or_unknown",
            "unresolved_steps": after["unresolved_steps"], "unresolved_faults": after["unresolved_faults"],
            "planned_faults": after["faults"], "driver": driver, "listener": listener_state,
            "worker": health, "control_lane": control, "progress_age_seconds": progress_age,
            "financial_ready": "unknown_independent_observer_has_no_readiness_authority",
            "finance": finance, "alerts": alerts, "final_evidence_eligible": False, **FLAGS}
        if progress["status"] == "completed":
            result["final_reconciliation"] = self.final_check(meta, progress, after, contract, finance, boundary, elapsed, listener_state, health)
            result["final_evidence_eligible"] = result["final_reconciliation"]["eligible"]
        return result

    def final_check(self, meta, progress, cp, contract, finance, boundary, elapsed, listener, health):
        errors = []
        required = {"logs_verified", "controller_sessions", "verified_tls", "final_audit", "unresolved_steps", "unresolved_faults"}
        if not required <= progress.keys():
            raise ValueError("final_progress_required_field_missing")
        if not boundary or cp["completed"] != contract["planned_rounds"] or cp["active_rounds"]:
            errors.append("final_round_boundary_incomplete")
        if not process_identity(self.driver_pid, self.driver_birth)["known_stopped"]:
            errors.append("final_driver_not_stopped_or_unknown")
        worker = health.get("process")
        if (not listener.get("known_stopped", False) or worker is None or not worker.get("known_stopped", False)
                or health["lease_active"]):
            errors.append("final_authority_not_cold")
        if cp["states"]["logs_verified"] is not True or progress["logs_verified"] is not True:
            errors.append("final_logs_verified_missing")
        if (cp["states"]["controller_sessions"] != 1 or type(progress["controller_sessions"]) is not int
                or progress["controller_sessions"] != 1
                or progress["verified_tls"] is not True or progress["error"] is not None):
            errors.append("final_session_or_transport_or_error_invalid")
        if progress["final_audit"] is None or progress["final_audit"].get("golden_passed") is not True:
            errors.append("producer_final_golden_missing")
        if elapsed is None or elapsed < 21600 or contract["duration_seconds"] < 21600 or contract["planned_rounds"] != 5400:
            errors.append("actual_6h_and_5400_rounds_required")
        ended = cp["controller_ended"]
        # Current uptime can grow after the producer exits. Require the original
        # producer's measured active duration too, never extend it with observation.
        if ended is None or ended["status"] != "completed" or number(progress["elapsed_seconds"]) < 21600:
            errors.append("producer_actual_active_duration_incomplete")
        if (cp["unresolved_steps"] or cp["unresolved_faults"] or progress["unresolved_steps"] or progress["unresolved_faults"]):
            errors.append("final_unresolved_effects")
        signals = {kind: sum(item["kind"] == kind and item["state"] == "DONE" and item["signal_sent"] is True
                           and type(item["new_generation"]) is int and item["new_generation"] > item["old_generation"]
                           for item in cp["faults"]) for kind in ("worker", "parent")}
        if not all(signals.values()):
            errors.append("both_real_fault_recoveries_required")
        if not finance["golden"]["compared"] or not finance["golden"]["passed"] or finance["retry_alerts"]:
            errors.append("independent_final_golden_or_retry_failed")
        logs = verify_logs(self.job, cp["event_head"])
        current = watermark(cp, finance, contract)
        # Independent reopen must cover the same checkpoint and business head.
        with readonly(self.job / "managed/shard-0000.sqlite3", cold=self.cold) as connection:
            reopened = read_financial(connection, contract["planned_rounds"], cp["completed"], compare_golden=True)
        later = checkpoint(self.job / "checkpoint.sqlite3", cold=self.cold)
        if watermark(later, reopened, contract) != current:
            errors.append("independent_reopen_watermark_changed")
        if (reopened["golden"].get("compared") is not True or reopened["golden"].get("passed") is not True
                or reopened["retry_alerts"]):
            errors.append("independent_reopen_golden_failed")
        producer = None
        if self.producer_receipt is None or not self.producer_receipt.exists():
            errors.append("producer_cold_audit_same_watermark_missing")
        else:
            receipt = load_json(self.producer_receipt)
            producer = receipt.get("audit_sha256")
            if (receipt.get("format") != 1 or receipt.get("watermark_before") != current
                    or receipt.get("watermark_after") != current or receipt.get("producer_cold_audit_passed") is not True
                    or receipt.get("frozen_commit") != self.frozen_commit
                    or receipt.get("producer_audit_scope") != PRODUCER_AUDIT_SCOPE
                    or receipt.get("producer_audit_runtime") != {key: meta["environment"][key] for key in ("python", "sqlite")}
                    or not isinstance(producer, str) or re.fullmatch(r"[0-9a-f]{64}", producer) is None):
                errors.append("producer_cold_audit_watermark_mismatch")
        if not self.recheck_final_contract(contract, progress, later):
            errors.append("final_original_contract_or_progress_changed")
        return {"eligible": not errors, "errors": errors, "watermark": current,
            "independent_reopen_same_watermark": "independent_reopen_watermark_changed" not in errors,
            "independent_reopen_reconciliation_passed": "independent_reopen_golden_failed" not in errors,
            "logs": logs, "producer_audit_sha256": producer, "observer_is_formal_signoff": False, **FLAGS}

    def publish(self, result):
        with (self.output / "timeline.jsonl").open("a") as stream:
            stream.write(canonical(result) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        atomic_json(self.output / "latest.json", result)


def producer_audit(observer, python):
    """Explicit stopped-authority wrapper; stdout is hashed, never copied raw."""
    first = observer.sample()
    final = first.get("final_reconciliation")
    if final is None or any(error != "producer_cold_audit_same_watermark_missing" for error in final["errors"]):
        raise ValueError("producer_audit_requires_other_final_checks_passed")
    # The producer's legacy mode=ro helper may create WAL sidecars on a cold
    # WAL database. Root explicitly authorized complete private SQLite backups,
    # including historical writer/control nonce columns, rather than rebuilding
    # a projected authority. Never publish/archive these opaque full DB clones.
    # No auth/TLS/signing/HTTP nonce-store/private stderr files are copied.
    meta = load_json(observer.job / "job.json")
    manifest = load_json(observer.job / "log-segments.json")
    relatives = [Path(name) for name in ("checkpoint.sqlite3", "managed/router.sqlite3", "managed/shard-0000.sqlite3",
        "job.json", "progress.json", "log-segments.json")]
    relatives.extend(Path("validation") / name for name in VALIDATION_ARTIFACTS)
    relatives.extend(log_relative(segment["file"]) for segment in manifest["segments"])
    estimate = 0
    for relative in relatives:
        estimate += (observer.job / relative).stat().st_size
        if relative.suffix == ".sqlite3":
            try:
                estimate += Path(str(observer.job / relative) + "-wal").stat().st_size
            except FileNotFoundError:
                pass
    if (estimate > observer.max_private_clone_bytes
            or shutil.disk_usage(observer.output).free < estimate + observer.min_private_free_bytes):
        raise ValueError("private_complete_clone_disk_budget_unavailable")
    probe = subprocess.run([python, "-B", "-c",
        "import json,sqlite3,sys; print(json.dumps({'python':sys.version,'sqlite':sqlite3.sqlite_version}))"],
        cwd=observer.source, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        close_fds=True, text=True, timeout=15)
    audit_runtime = parse(probe.stdout) if probe.returncode == 0 else None
    expected_runtime = {key: meta["environment"][key] for key in ("python", "sqlite")}
    if (audit_runtime != expected_runtime
            or audit_runtime != {key: meta["validation_evidence"][key] for key in ("python", "sqlite")}):
        raise ValueError("producer_audit_exact_runtime_mismatch")
    private = observer.output / "private-audit"
    private.mkdir(mode=0o700, exist_ok=True)
    details = private.stat()
    if private.is_symlink() or details.st_uid != os.geteuid() or stat.S_IMODE(details.st_mode) != 0o700:
        raise ValueError("private_complete_clone_directory_not_private")
    with tempfile.TemporaryDirectory(prefix="private-full-clone-", dir=private) as temporary:
        clone = Path(temporary)
        for relative in ("checkpoint.sqlite3", "managed/router.sqlite3", "managed/shard-0000.sqlite3"):
            destination = clone / relative
            destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with readonly(observer.job / relative, cold=observer.cold) as source:
                target = sqlite3.connect(destination)
                try:
                    destination.chmod(0o600)
                    source.backup(target)
                    target.execute("PRAGMA journal_mode=DELETE")
                finally:
                    target.close()
        for relative in ("job.json", "progress.json", "log-segments.json"):
            private_write(clone / relative, (observer.job / relative).read_bytes())
        (clone / "validation").mkdir(mode=0o700)
        for name in VALIDATION_ARTIFACTS:
            raw = (observer.job / "validation" / name).read_bytes()
            if sha256(raw).hexdigest() != meta["validation_evidence"]["artifact_sha256"][name]:
                raise ValueError("private_complete_clone_validation_changed")
            private_write(clone / "validation" / name, raw)
        (clone / "logs").mkdir(mode=0o700)
        for segment in manifest["segments"]:
            relative = log_relative(segment["file"])
            # verify_logs has already constrained these names and checksums.
            private_write(clone / relative, (observer.job / relative).read_bytes())
        with readonly(clone / "managed/shard-0000.sqlite3", cold=True) as connection:
            copied = read_financial(connection, first["planned_rounds"], first["completed_rounds"], compare_golden=True)
        if copied["watermark"] != final["watermark"]["financial"] or not copied["golden"]["passed"]:
            raise ValueError("producer_private_clone_watermark_mismatch")
        if checkpoint(clone / "checkpoint.sqlite3", cold=True)["event_head"] != final["watermark"]["checkpoint"]:
            raise ValueError("producer_private_checkpoint_watermark_mismatch")
        if shutil.disk_usage(observer.output).free < observer.min_private_free_bytes:
            raise ValueError("private_complete_clone_free_space_exhausted")
        run = subprocess.run([python, "-B", "benchmarks/run_managed_soak.py", "audit", "--directory", str(clone)],
            cwd=observer.source, text=True, capture_output=True, timeout=120,
            stdin=subprocess.DEVNULL, close_fds=True)
    if run.returncode:
        raise ValueError("producer_cold_audit_failed")
    audit = parse(run.stdout)
    if (audit["status"] != "audit_passed" or audit["cold_read_only"] is not True
            or audit["financial"]["golden_passed"] is not True or audit["logs"]["last_hash"] != final["watermark"]["checkpoint"]["hash"]):
        raise ValueError("producer_cold_audit_result_invalid")
    second = observer.sample()["final_reconciliation"]
    if (second["watermark"] != final["watermark"]
            or any(error != "producer_cold_audit_same_watermark_missing" for error in second["errors"])):
        raise ValueError("producer_cold_audit_crossed_watermark")
    receipt = {"format": 1, "synthetic": True, "redacted": True, "producer_cold_audit_passed": True,
        "audit_sha256": sha256(run.stdout.encode()).hexdigest(), "frozen_commit": observer.frozen_commit,
        "producer_audit_scope": PRODUCER_AUDIT_SCOPE,
        "producer_audit_runtime": audit_runtime,
        "private_clone_estimated_bytes": estimate, "private_clone_max_bytes": observer.max_private_clone_bytes,
        "watermark_before": final["watermark"], "watermark_after": second["watermark"], **FLAGS}
    atomic_json(observer.output / "producer-cold-audit-receipt.json", receipt)
    return receipt


def readonly_mount_or_reexec(job, output, source, argv):
    """Enforce no job/source writes in the kernel, including SQLite sidecars.

    Filesystem permissions are unchanged. A private mount namespace exposes /
    read-only and binds only the external output directory writable. This also
    closes the existing-sidecar check/open race. Failure is never a downgrade.
    """
    job, output = output_directory(job, output)
    source = Path(source).resolve()
    if output.is_relative_to(source):
        raise ValueError("observer_output_must_be_outside_source")
    if os.statvfs(job).f_flag & os.ST_RDONLY and os.statvfs(source).f_flag & os.ST_RDONLY:
        if os.statvfs(output).f_flag & os.ST_RDONLY:
            raise ValueError("observer_output_mount_not_writable")
        return None
    executable = shutil.which("bwrap")
    if executable is None:
        raise ValueError("kernel_readonly_mount_required_bwrap_unavailable")
    command = [executable, "--ro-bind", "/", "/", "--bind", str(output), str(output), "--",
               sys.executable, "-B", str(Path(__file__).resolve()), *argv]
    run = subprocess.run(command, cwd=Path(__file__).resolve().parents[1], stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, close_fds=True, text=True)
    if run.returncode and run.stderr:
        raise ValueError("readonly_mount_or_child_failed")
    if run.stdout:
        # safe_standard_descriptors was checked before any CLI output. The
        # launcher receives a pipe and decides where its own external logs go.
        sys.stdout.write(run.stdout)
    return run.returncode


def main(argv=None):
    if not safe_standard_descriptors():
        # A diagnostic printed here could itself overwrite the inherited file.
        return 1
    argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("watch", "producer-audit"))
    parser.add_argument("--job", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--frozen-commit", required=True)
    parser.add_argument("--driver-pid", type=int, required=True)
    parser.add_argument("--driver-birth", required=True)
    parser.add_argument("--producer-receipt", type=Path)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--collector-input-v2", action="store_true",
                        help="send complete transient samples to an explicit post-consumer compact collector")
    parser.add_argument("--report-protocol", choices=("legacy", "compact-v2"), default="legacy",
                        help="same immutable report contract for watch/final/audit, independent of wire emission")
    parser.add_argument("--interval", type=float, default=60)
    parser.add_argument("--max-private-clone-bytes", type=int, default=6 * 1024**3)
    parser.add_argument("--min-private-free-bytes", type=int, default=1024**3)
    parser.add_argument("--max-address-space-bytes", type=int, default=2 * 1024**3)
    args = parser.parse_args(argv)
    if args.collector_input_v2 and (args.command != "watch" or not stat.S_ISFIFO(os.fstat(1).st_mode)):
        parser.error("collector input v2 requires watch and a pipe stdout")
    if args.command == "watch" and args.collector_input_v2 != (args.report_protocol == "compact-v2"):
        parser.error("watch report protocol and collector input must agree")
    if number(args.interval) < 60:
        parser.error("observation interval must be at least 60 seconds")
    integer(args.max_private_clone_bytes, 1)
    integer(args.min_private_free_bytes)
    integer(args.max_address_space_bytes, 256 * 1024**2)
    _, hard = resource.getrlimit(resource.RLIMIT_AS)
    limit = args.max_address_space_bytes if hard == resource.RLIM_INFINITY else min(hard, args.max_address_space_bytes)
    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    try:
        reexecuted = readonly_mount_or_reexec(args.job, args.output, args.source, argv)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(canonical({"synthetic": True, "redacted": True, "final_evidence_eligible": False,
            "alerts": ["kernel_readonly_mount_not_established"], "error_type": type(error).__name__, **FLAGS}))
        return 1
    if reexecuted is not None:
        return reexecuted
    observer = Observer(args.job, args.output, args.source, args.frozen_commit, args.driver_pid,
                        args.driver_birth, producer_receipt=args.producer_receipt,
                        max_private_clone_bytes=args.max_private_clone_bytes,
                        min_private_free_bytes=args.min_private_free_bytes,
                        collector_input_v2=args.collector_input_v2, report_protocol=args.report_protocol)
    if args.command == "producer-audit":
        try:
            print(canonical(producer_audit(observer, args.python)))
            return 0
        except (OSError, ValueError, KeyError, TypeError, ArithmeticError, RecursionError, MemoryError,
                sqlite3.Error, subprocess.SubprocessError) as error:
            print(canonical({"synthetic": True, "redacted": True, "final_evidence_eligible": False,
                "observer_is_formal_signoff": False, "alerts": ["producer_cold_audit_failed_closed"],
                "error_type": type(error).__name__, "error_digest": sha256(str(error).encode()).hexdigest(), **FLAGS}))
            return 1
    stop = Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    input_sequence = 0
    while not stop.is_set():
        sample_started = time.monotonic()
        result = None  # Release the preceding full-CID sample before reading another.
        try:
            result = observer.sample()
        except (OSError, ValueError, KeyError, TypeError, ArithmeticError, RecursionError, MemoryError,
                sqlite3.Error, subprocess.SubprocessError) as error:
            result = {"synthetic": True, "redacted": True, "observation_only": True,
                "observer_is_formal_signoff": False, "sample_wall_ns": time.time_ns(),
                "logical_point": "unknown", "final_evidence_eligible": False,
                "alerts": ["observation_failed_closed"], "error_type": type(error).__name__,
                "error_digest": sha256(str(error).encode()).hexdigest(), **FLAGS}
        if args.collector_input_v2:
            try:
                from tools.managed_observer_transport import input_frame
            except ModuleNotFoundError:
                from managed_observer_transport import input_frame
            input_sequence += 1
            sys.stdout.buffer.write(input_frame(result, input_sequence))
            sys.stdout.buffer.flush()
        else:
            observer.publish(result)
        if args.once:
            if not args.collector_input_v2:
                print(canonical(result))
            return 0 if "observation_failed_closed" not in result["alerts"] else 1
        deadline = sample_started + args.interval
        if deadline <= time.monotonic():
            deadline = time.monotonic() + args.interval
        while not stop.is_set() and time.monotonic() < deadline:
            stop.wait(min(60, max(0, deadline - time.monotonic())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
