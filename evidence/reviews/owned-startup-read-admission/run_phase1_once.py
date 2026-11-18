"""One materialized-input-gated pure interpreter run; no business processes.

Invoke only with an explicit root once budget, externally bounded by timeout
and CPU affinity. No subprocess or Git command is launched by this driver.
The source-commit argument is an invoker-supplied label, not an election proof.
"""
import argparse
from contextlib import redirect_stderr, redirect_stdout
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import sys
import time
import traceback


ROOT = Path(__file__).resolve().parents[3]


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def exclusive(path, data):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def read_regular(path, limit=2 * 1024 * 1024):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode) or info.st_size > limit:
        raise ValueError("input is not a bounded materialized regular file")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        raw = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    properties = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    if len(raw) > limit or any(getattr(before, key) != getattr(after, key) for key in properties):
        raise ValueError("input changed during materialized read")
    return raw


def input_pins(plan):
    result = {}
    for name, expected in plan["input_files"].items():
        if name.startswith("/") or ".." in Path(name).parts:
            raise ValueError("input path escapes frozen source")
        raw = read_regular(ROOT / name)
        value = {"bytes": len(raw), "sha256": sha256(raw).hexdigest()}
        if value != expected:
            raise ValueError("materialized input differs from frozen length/SHA")
        result[name] = value
    return result


def pure_audit(event, args):
    if event == "import" and args:
        name = args[0]
        if isinstance(name, str) and (name == "uta" or name.startswith("uta.")
                                     or name in {"sqlite3", "_sqlite3"}):
            raise RuntimeError("pure driver rejects product/database import")
    if (event.startswith("socket.") or event in {
            "subprocess.Popen", "os.fork", "os.forkpty", "os.posix_spawn", "os.posix_spawnp",
            "os.kill", "os.killpg", "ctypes.dlopen", "ctypes.dlsym"}):
        raise RuntimeError("pure driver rejects native/process/network action")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--private-directory", required=True, type=Path)
    args = parser.parse_args()
    output = args.private_directory
    output.mkdir(mode=0o700)  # Exclusive namespace: a spent run is never overwritten.
    plan_path = ROOT / "evidence/reviews/owned-startup-read-admission/phase1-focused-plan.json"
    plan_raw = read_regular(plan_path)
    if sha256(plan_raw).hexdigest() != args.plan_sha256:
        exclusive(output / "preflight.json", encoded({"passed": False, "target_started": False,
                  "reason": "frozen_plan_SHA_mismatch"}))
        return 1
    plan = json.loads(plan_raw)
    try:
        before = input_pins(plan)
    except BaseException as error:
        exclusive(output / "preflight.json", encoded({"passed": False, "target_started": False,
                  "reason": "materialized_input_gate", "error_type": type(error).__name__}))
        raise
    exclusive(output / "intent.json", encoded({"source_commit_supplied_by_invoker": args.source_commit,
        "commit_not_resolved_by_this_driver": True, "plan_sha256": args.plan_sha256,
        "input_pins_before": before, "first_and_only": True, "planned_methods": 12,
        "planned_small_traces": 48, "scope": plan["scope"], "production_approved": False}))
    fixture = ROOT / "evidence/reviews/owned-startup-read-admission/phase1_focused_fake.py"
    raw = read_regular(fixture)
    sys.addaudithook(pure_audit)
    # These guards are defense in depth for reviewed source, not an OS sandbox.
    started = time.monotonic_ns()
    returncode = 1
    out_fd = os.open(output / "first.stdout.txt", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    err_fd = os.open(output / "first.stderr.txt", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(out_fd, "w") as out, os.fdopen(err_fd, "w") as err:
        with redirect_stdout(out), redirect_stderr(err):
            try:
                exec(compile(raw, str(fixture), "exec"), {"__name__": "__main__", "__file__": str(fixture)})
            except SystemExit as stopped:
                returncode = stopped.code if type(stopped.code) is int else 1
            except BaseException:
                traceback.print_exc()
            else:
                returncode = 0
        out.flush()
        err.flush()
        os.fsync(out.fileno())
        os.fsync(err.fileno())
    elapsed = time.monotonic_ns() - started
    after = input_pins(plan)
    exclusive(output / "first.execution.json", encoded({
        "returncode": returncode, "elapsed_ns": elapsed, "input_pins_after": after,
        "source_before_after_equal": before == after, "target_started": True,
        "native_or_financial_approved": False, "phase2_authorized": False,
        "production_approved": False}))
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
