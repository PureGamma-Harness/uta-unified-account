"""One root-authorized new pure batch; exclusive raw evidence, no retry."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
PIN = "a7c9d0f8daf014efdab45d35e4cd94f2d0041cb9"
OUT = ROOT / "evidence/observer-compact-report-v2/pipeline-first-once01"
ARGV = ["taskset", "-c", "1", "timeout", "--signal=KILL", "10s", "python", "-B",
        "tests/test_observer_v2_pipeline_pure.py", "-v"]
INPUTS = ["tools/managed_observer_report.py", "tools/managed_observer_transport.py",
          "tools/managed_observer_coverage.py", "tools/run_managed_long.py",
          "tools/managed_soak_observer.py", "tools/managed_output_budget.py",
          "tests/test_observer_v2_pipeline_pure.py", "tests/fixtures/managed_soak_observer_909.py",
          "tests/fixtures/run_managed_long_909.py", "tests/fixtures/managed_observer_coverage_909.py"]


def git(*args):
    return subprocess.check_output(["git", "--no-optional-locks", *args], cwd=ROOT,
        stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def utc():
    return datetime.now(timezone.utc).isoformat()


def identity(pid):
    tail = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    return {"pid": pid, "birth": tail[19], "state": tail[0],
            "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip()}


def seal(name, value):
    descriptor = os.open(OUT / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n"); stream.flush(); os.fsync(stream.fileno())


def closure():
    result = {}
    for name in INPUTS:
        path = ROOT / name
        if path.is_symlink(): raise RuntimeError("source_symlink_rejected")
        expected, actual = git("show", PIN + ":" + name), path.read_bytes()
        if expected != actual: raise RuntimeError("Git_source_closure_mismatch:" + name)
        result[name] = {"sha256": sha256(actual).hexdigest(), "bytes": len(actual)}
    return result


if git("rev-parse", "HEAD").decode().strip() != PIN:
    raise RuntimeError("fixed_source_HEAD_changed")
before = closure()
OUT.mkdir(mode=0o700, exist_ok=False)
seal("intent.json", {"source": PIN, "argv": ARGV, "inputs": before,
    "root_authorization": "one new 12-method CPU1/10s KILL pure batch after independent protocol CODE closure",
    "authorization_adds_no_second_budget": True, "started_intent_utc": utc(),
    "launcher": identity(os.getpid()), "old_author_or_independent_batch_rerun": False,
    "actual_watch_SQL_FSadapter_native_workers_crypto_keys_network_CI": "NOT_AUTHORIZED"})
descriptors = [os.open(OUT / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
               for name in ("stdout.txt", "stderr.txt")]
started, tick, old_limit = utc(), time.monotonic_ns(), resource.getrlimit(resource.RLIMIT_FSIZE)
# 48KiB each regular output file gives a stricter96KiB combined bound.
soft = min(49152, old_limit[0]) if old_limit[0] != resource.RLIM_INFINITY else 49152
resource.setrlimit(resource.RLIMIT_FSIZE, (soft, old_limit[1]))
try:
    process = subprocess.Popen(ARGV, cwd=ROOT, stdin=subprocess.DEVNULL,
        stdout=descriptors[0], stderr=descriptors[1], close_fds=True, start_new_session=True)
finally:
    resource.setrlimit(resource.RLIMIT_FSIZE, old_limit)
supervisor = identity(process.pid)
children = {}
while process.poll() is None:
    try:
        values = Path(f"/proc/{process.pid}/task/{process.pid}/children").read_text().split()
        for value in values:
            pid = int(value)
            if pid not in children:
                children[pid] = identity(pid)
    except (FileNotFoundError, ProcessLookupError):
        pass
    time.sleep(.001)
status, elapsed, finished = process.wait(), time.monotonic_ns() - tick, utc()
for descriptor in descriptors:
    os.fsync(descriptor); os.close(descriptor)
after = closure()
raw = {name: {"bytes": (OUT / name).stat().st_size,
              "sha256": sha256((OUT / name).read_bytes()).hexdigest()} for name in ("stdout.txt", "stderr.txt")}
if sum(item["bytes"] for item in raw.values()) > 102400:
    raise RuntimeError("combined_output_budget_exceeded")
seal("execution.json", {"source": PIN, "argv": ARGV, "started_utc": started,
    "finished_utc": finished, "elapsed_ns": elapsed, "exit": status,
    "timeout_supervisor_identity": supervisor, "observed_direct_children": list(children.values()),
    "Python_child_not_observed_is_not_assumed": True, "inputs_before": before, "inputs_after": after,
    "source_unchanged": before == after, "raw": raw, "system_qualification": "NO_GO",
    "actual_watch_SQL_FSadapter_native_workers_crypto_keys_network_CI": "NOT_RUN"})
print(json.dumps({"source": PIN, "exit": status, "elapsed_ns": elapsed, "raw": raw,
                  "source_unchanged": before == after}, sort_keys=True))
raise SystemExit(status)
