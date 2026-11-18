"""Root-authorized one new synthetic FS/pipe run, first evidence and no retry."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import resource
import stat
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "dc1e8e6c37e98a0d33c7d2aafc8af96ffca7ee4d"
HEAD = "cef70d81fabb530dbc8c36509558aff8d7412693"
PARENT = Path("/workspace/uta-observer-v2-adapter-runs")
OUTPUT = PARENT / "read1-dc1e8e6-once01"
EVIDENCE = ROOT / "evidence/observer-compact-report-v2/adapter-first-once01"
BUDGET_PATH = "evidence/observer-compact-report-v2/adapter-preparation-dc1e/source-budget.json"
ARGV = ["taskset", "-c", "1", "timeout", "--signal=KILL", "10s", "python", "-B",
        "tools/probe_observer_v2_adapters.py", "--execute-synthetic-adapters", "--new-output", str(OUTPUT)]


def git(*args):
    return subprocess.check_output(["git", "--no-optional-locks", *args], cwd=ROOT,
        stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def utc():
    return datetime.now(timezone.utc).isoformat()


def identity(pid):
    try:
        tail = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    except FileNotFoundError:
        return {"pid": pid, "observed": False}
    return {"pid": pid, "birth": tail[19], "state": tail[0], "observed": True,
            "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip()}


def seal(name, value):
    descriptor = os.open(EVIDENCE / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n"); stream.flush(); os.fsync(stream.fileno())


budget_raw = (ROOT / BUDGET_PATH).read_bytes()
if git("rev-parse", "HEAD").decode().strip() != HEAD or git("show", HEAD + ":" + BUDGET_PATH) != budget_raw:
    raise RuntimeError("fixed_HEAD_or_frozen_plan_changed")
budget = json.loads(budget_raw)
if budget["source_commit"] != SOURCE or budget["proposed_argv"] != ARGV:
    raise RuntimeError("frozen_source_or_argv_changed")


def closure():
    values = {}
    for name, expected_hash in budget["source_sha256"].items():
        path = ROOT / name
        if path.is_symlink(): raise RuntimeError("source_symlink_rejected:" + name)
        expected, actual = git("show", SOURCE + ":" + name), path.read_bytes()
        if actual != expected or sha256(actual).hexdigest() != expected_hash:
            raise RuntimeError("source_closure_changed:" + name)
        values[name] = {"sha256": expected_hash, "bytes": len(actual)}
    if len(values) != 8: raise RuntimeError("eight_input_closure_required")
    return values


before = closure()
if PARENT.exists() or PARENT.is_symlink() or OUTPUT.exists():
    raise RuntimeError("one_fresh_parent_and_output_required_no_retry")
EVIDENCE.mkdir(mode=0o700, exist_ok=False)
seal("intent.json", {"source": SOURCE, "frozen_HEAD": HEAD, "argv": ARGV, "inputs": before,
    "root_authorization": "one actual synthetic filesystem/live-small-frame pipe adapter at dc1e input source; CPU1 and outer10s KILL; no retry",
    "scope": "ONLY_FIXED_DATA_EMITTER_AND_REPORT_FS_ADAPTERS",
    "old_mock_or_source_3e42_execution": False, "actual_watch_SQL_finance_network_crypto_CI_6h": "FORBIDDEN",
    "allowed_runs_added": 1, "no_second_budget": True, "launcher": identity(os.getpid()),
    "intent_utc": utc(), "launcher_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
    "new_parent": str(PARENT), "new_output": str(OUTPUT), "raw_file_limit_each_bytes": 49152,
    "combined_raw_budget_bytes": 102400, "raw_diagnostic_bytes_are_separate_from_probe_measurement": True})
PARENT.mkdir(mode=0o700, exist_ok=False)
details = PARENT.lstat()
if not stat.S_ISDIR(details.st_mode) or details.st_uid != os.geteuid() or stat.S_IMODE(details.st_mode) != 0o700:
    raise RuntimeError("created_parent_identity_unknown")
descriptors = [os.open(EVIDENCE / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
               for name in ("stdout.txt", "stderr.txt")]
started, tick, original_limit = utc(), time.monotonic_ns(), resource.getrlimit(resource.RLIMIT_FSIZE)
soft = min(49152, original_limit[0]) if original_limit[0] != resource.RLIM_INFINITY else 49152
resource.setrlimit(resource.RLIMIT_FSIZE, (soft, original_limit[1]))
try:
    process = subprocess.Popen(ARGV, cwd=ROOT, stdin=subprocess.DEVNULL,
        stdout=descriptors[0], stderr=descriptors[1], close_fds=True, start_new_session=True,
        env={"PATH": str(Path(sys.executable).parent) + os.pathsep + os.defpath,
             "PYTHONDONTWRITEBYTECODE": "1", "LC_ALL": "C.UTF-8"})
finally:
    resource.setrlimit(resource.RLIMIT_FSIZE, original_limit)
supervisor = identity(process.pid)
children = {}
while process.poll() is None:
    try:
        for value in Path(f"/proc/{process.pid}/task/{process.pid}/children").read_text().split():
            pid = int(value)
            if pid not in children: children[pid] = identity(pid)
    except FileNotFoundError:
        pass
    time.sleep(.001)
status, elapsed, finished = process.wait(), time.monotonic_ns() - tick, utc()
for descriptor in descriptors:
    os.fsync(descriptor); os.close(descriptor)
try:
    after, closure_error = closure(), None
except BaseException as error:
    after, closure_error = None, {"type": type(error).__name__, "text": str(error)}
raw = {name: {"bytes": (EVIDENCE / name).stat().st_size,
              "sha256": sha256((EVIDENCE / name).read_bytes()).hexdigest()}
       for name in ("stdout.txt", "stderr.txt")}
artifacts = {}
for path in sorted(OUTPUT.rglob("*")):
    details = path.lstat()
    if stat.S_ISREG(details.st_mode):
        artifacts[str(path.relative_to(OUTPUT))] = {"bytes": details.st_size,
            "sha256": sha256(path.read_bytes()).hexdigest(), "mode": oct(stat.S_IMODE(details.st_mode))}
    elif not stat.S_ISDIR(details.st_mode):
        artifacts[str(path.relative_to(OUTPUT))] = {"unexpected_special_file": True}
cleanup_path = OUTPUT / "control/cleanup.json"
cleanup = json.loads(cleanup_path.read_bytes()) if cleanup_path.exists() else None
owned = identity(cleanup["owned_child"]["pid"]) if cleanup is not None else None
not_remaining = bool(owned is not None and (not owned["observed"] or owned.get("birth") != cleanup["owned_child"]["birth"]))
originals_bounded = sum(value["bytes"] for value in raw.values()) <= 102400 and all(value["bytes"] < soft for value in raw.values())
probe_bytes = sum(value.get("bytes", 0) for value in artifacts.values())
summary = {"source": SOURCE, "argv": ARGV, "started_utc": started, "finished_utc": finished,
    "elapsed_ns": elapsed, "exit": status, "timeout_supervisor_identity": supervisor,
    "observed_direct_children": list(children.values()), "direct_child_observation_may_be_incomplete": True,
    "inputs_before": before, "inputs_after": after, "source_unchanged": before == after,
    "closure_error": closure_error, "raw": raw, "raw_originals_bounded": originals_bounded,
    "probe_artifacts": artifacts, "probe_control_and_observer_bytes": probe_bytes,
    "probe_measured_byte_budget": 131072, "diagnostic_raw_bytes": sum(item["bytes"] for item in raw.values()),
    "owned_data_child_after_exit": owned, "owned_data_child_birth_no_longer_present": not_remaining,
    "first_attempt_only": True, "automatic_retry": False,
    "system_qualification": "NO_GO", "production_approved": False, "financial_6h_passed": False,
    "actual_watch_SQL_finance_network_crypto_CI_6h": "NOT_RUN"}
seal("execution.json", summary)
print(json.dumps({key: summary[key] for key in ("source", "exit", "elapsed_ns", "raw", "source_unchanged",
    "probe_control_and_observer_bytes", "owned_data_child_birth_no_longer_present")}, sort_keys=True))
raise SystemExit(status if status != 0 else 0 if before == after and originals_bounded and probe_bytes <= 131072 and not_remaining else 1)
