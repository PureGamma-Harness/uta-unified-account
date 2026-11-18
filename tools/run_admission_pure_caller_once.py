"""Observe one retained PURE7 outer process; CODE proposal, explicit GO required."""
import argparse
import base64
from hashlib import sha256
import json
import os
from pathlib import Path
import selectors
import signal
import stat
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
ENTRY = "tools/run_admission_pure_once.py"
SELF = "tools/run_admission_pure_caller_once.py"
PLAN = "evidence/reviews/admission-decision-replay/pure-once-plan.json"
CALLER_PLAN = "evidence/reviews/admission-decision-replay/pure-caller-plan.json"
PROTECTED = frozenset({4471, 8784, 122905, 122907, 123007, 123009,
                       310035, 310039, 310266, 310269})
RAW_LIMIT, TRAILER = 1024, 512
CONTROL_LIMIT, CONTROL_WRITTEN = 65536, 0
GATE = "import os,sys\nif sys.stdin.buffer.read(1)!=b'G': raise SystemExit(126)\nos.execv(sys.argv[1],sys.argv[1:])\n"


def raw(path, limit=4 * 1024 * 1024):
    if path.resolve() != path or not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError("canonical regular file required")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        value = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    if len(value) > limit or any(getattr(before, key) != getattr(after, key)
            for key in ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")):
        raise ValueError("source changed or exceeded bound")
    return value


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def put(path, value):
    global CONTROL_WRITTEN
    value = encode(value)
    if CONTROL_WRITTEN + len(value) > CONTROL_LIMIT:
        raise ValueError("caller control budget exhausted")
    CONTROL_WRITTEN += len(value)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        if stream.write(value) != len(value):
            raise OSError("short caller control write")
        stream.flush()
        os.fsync(stream.fileno())


def git(*arguments):
    result = subprocess.run(["/usr/bin/git", "--no-optional-locks", "-C", str(ROOT), *arguments],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3,
        env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null"})
    if len(result.stdout) > 4 * 1024 * 1024 or result.stderr:
        raise ValueError("unexpected Git output")
    return result.stdout


def main(args):
    if not args.execute:
        raise ValueError("explicit execution flag required")
    if not hasattr(os, "pidfd_open") or not hasattr(signal, "pidfd_send_signal"):
        raise ValueError("owned outer pidfd support required")
    os.sched_setaffinity(0, {1})
    started = time.monotonic_ns()
    if git("rev-parse", "HEAD").decode().strip() != args.source_commit:
        raise ValueError("final invocation HEAD differs")
    plan_raw, caller_raw = raw(ROOT / PLAN), raw(ROOT / CALLER_PLAN)
    if (sha256(plan_raw).hexdigest() != args.plan_sha256 or
            sha256(caller_raw).hexdigest() != args.caller_plan_sha256 or
            plan_raw != git("show", args.source_commit + ":" + PLAN) or
            caller_raw != git("show", args.source_commit + ":" + CALLER_PLAN)):
        raise ValueError("approved plans differ")
    plan, control = json.loads(plan_raw), json.loads(caller_raw)
    frozen = {}
    for name, expected in {**plan["input_files"], SELF: control["caller_control_pin"]}.items():
        if name.startswith("/") or ".." in Path(name).parts:
            raise ValueError("source escapes checkout")
        value = raw(ROOT / name)
        if value != git("show", args.source_commit + ":" + name) or {"bytes": len(value), "sha256": sha256(value).hexdigest()} != expected:
            raise ValueError("physical/Git input mismatch")
        frozen[name] = value
    runtime = {"sys_executable": sys.executable, "resolved_executable": str(Path(sys.executable).resolve()),
        "executable_bytes": len(raw(Path(sys.executable).resolve(), 64 * 1024 * 1024)),
        "executable_sha256": sha256(raw(Path(sys.executable).resolve(), 64 * 1024 * 1024)).hexdigest(),
        "sys_version": sys.version, "affinity": sorted(os.sched_getaffinity(0)),
        "flags": {"isolated": sys.flags.isolated, "no_site": sys.flags.no_site, "dont_write_bytecode": sys.flags.dont_write_bytecode}}
    if runtime != plan["expected_runtime"]:
        raise ValueError("caller runtime differs")
    target, caller = Path(args.output), Path(args.caller_output)
    if (target == caller or any(not p.is_absolute() or p.resolve() != p or p.parent != Path("/workspace") for p in (target, caller))
            or os.path.lexists(target) or os.path.lexists(caller)):
        raise ValueError("two distinct new canonical workspace namespaces required")
    caller.mkdir(mode=0o700)
    args.created = caller
    command = [runtime["resolved_executable"], "-I", "-S", "-B", str(ROOT / ENTRY), "--execute",
        "--source-commit", args.source_commit, "--plan-sha256", args.plan_sha256, "--output", str(target)]
    launch = [runtime["resolved_executable"], "-I", "-S", "-B", "-c", GATE, *command]
    put(caller / "intent.json", {"source_commit": args.source_commit, "plan_sha256": args.plan_sha256,
        "caller_plan_sha256": args.caller_plan_sha256, "runtime": runtime,
        "input_files": plan["input_files"], "caller_control_pin": control["caller_control_pin"],
        "outer_argv": command, "literal_popen_argv": launch, "monotonic_start_ns": started,
        "source_origin_is_not_invocation_HEAD": True, "attempt": 1})
    streams = [os.open(caller / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
               for name in ("launcher.stdout.txt", "launcher.stderr.txt")]
    process, pidfd, selector = None, None, None
    rc, reaped, eof, error, reserved, sticky, cleanup_signal = None, False, False, None, 0, False, 0
    cleanup_attempts = 0
    released = False
    wait_end = None
    launch_started = time.monotonic_ns()
    deadline = time.monotonic() + 30
    try:
        process = subprocess.Popen(launch, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=ROOT, close_fds=True, start_new_session=True)
        if type(process.pid) is not int or process.pid <= 1 or process.pid in PROTECTED:
            raise ValueError("new outer birth refused before pidfd or signal")
        pidfd = os.pidfd_open(process.pid)
        put(caller / "owned-birth.json", {"new_outer_pid": process.pid, "held_pidfd": True,
            "start_gate_released": False, "monotonic_ns": time.monotonic_ns()})
        selector = selectors.DefaultSelector()
        for stream, destination in zip((process.stdout, process.stderr), streams):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, destination)
        if process.stdin.write(b"G") != 1:
            raise OSError("short start gate write")
        process.stdin.flush()
        process.stdin.close()
        released = True
        while selector.get_map() and time.monotonic() < deadline:
            for key, unused in selector.select(min(.05, max(0, deadline - time.monotonic()))):
                try:
                    value = os.read(key.fileobj.fileno(), 4096)
                except BlockingIOError:
                    continue
                if not value:
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
                elif not sticky:
                    if reserved + len(value) > RAW_LIMIT - TRAILER:
                        sticky = True
                    else:
                        reserved += len(value)
                        if os.write(key.data, value) != len(value):
                            sticky = True
        eof = not selector.get_map()
        rc = process.wait(timeout=max(0, deadline - time.monotonic()))
        wait_end = time.monotonic_ns()
        reaped = True
        args.outer_exit, args.outer_reaped = rc, reaped
    except BaseException as failure:
        error = type(failure).__name__
    finally:
        if process is not None:
            if process.stdin is not None and not process.stdin.closed:
                try:
                    process.stdin.close()  # Unreleased child exits on EOF; no lookup/signal fallback.
                except BaseException as cleanup:
                    error = error or type(cleanup).__name__
            if not reaped:
                if pidfd is not None:
                    try:
                        cleanup_attempts += 1
                        signal.pidfd_send_signal(pidfd, signal.SIGKILL)
                        cleanup_signal = 1
                    except ProcessLookupError:
                        pass  # Still wait on the original Popen handle below.
                    except BaseException as cleanup:
                        error = error or type(cleanup).__name__
                try:
                    rc = process.wait(timeout=2)
                    wait_end = time.monotonic_ns()
                    reaped = True
                    args.outer_exit, args.outer_reaped = rc, reaped
                except BaseException as cleanup:
                    error = error or type(cleanup).__name__
            if selector is not None:
                try:
                    until = time.monotonic() + .2
                    while selector.get_map() and time.monotonic() < until:
                        for key, unused in selector.select(.01):
                            value = os.read(key.fileobj.fileno(), 4096)
                            if not value:
                                selector.unregister(key.fileobj)
                                key.fileobj.close()
                            else:
                                sticky = True  # Late bytes cannot repair a missing deadline.
                    eof = not selector.get_map()
                except BaseException as cleanup:
                    error = error or type(cleanup).__name__
                finally:
                    try:
                        selector.close()
                    except BaseException as cleanup:
                        error = error or type(cleanup).__name__
            for stream in (process.stdout, process.stderr):
                if stream is not None and not stream.closed:
                    try:
                        stream.close()
                    except BaseException as cleanup:
                        error = error or type(cleanup).__name__
        if pidfd is not None:
            try:
                os.close(pidfd)
            except BaseException as cleanup:
                error = error or type(cleanup).__name__
    checks, outer_classification = {}, None
    try:
        def record(relative):
            return json.loads(raw(target / relative))
        execution, end, tail = record("execution.json"), record("END.json"), record("TAIL.json")
        outer_classification = execution.get("classification")
        intent, inner_intent = record("intent.json"), record("inner/intent.json")
        inner = record("inner/execution.json")
        stdout, stderr = raw(target / "first.stdout.txt", 32768), raw(target / "first.stderr.txt", 32768)
        begin, inner_end = [json.loads(line) for line in stdout.splitlines()]
        checks["BEGIN"] = begin == {"event": "ADMISSION_PURE_BEGIN", "source_commit": args.source_commit,
            "runtime": runtime, "selected_methods": plan["methods"], "input_count": 64}
        checks["inner_END"] = inner_end == {"event": "ADMISSION_PURE_END", **inner}
        checks["inner_intent"] = inner_intent == {"source_commit": args.source_commit,
            "plan_sha256": args.plan_sha256, "runtime": runtime, "input_files": plan["input_files"],
            "fixed_methods": plan["methods"], "caller_actual_exit_required": True}
        checks["seven_tests"] = inner["tests_run"] == 7 and type(inner["tests_run"]) is int and all(
            type(inner[k]) is int and inner[k] == 0 for k in ("returncode", "failures", "errors", "skipped", "expected_failures", "unexpected_successes"))
        checks["inner_binding"] = (inner["source_commit_invoker_label"] == args.source_commit and inner["runtime"] == runtime
            and inner["selected_methods"] == plan["methods"] and inner["input_pins_after"] == plan["input_files"]
            and inner["source_before_after_equal"] is True and inner["forbidden_attempts"] == []
            and inner["loaded_UTA_modules"] == plan["expected_loaded_UTA_modules"] and inner["SQL_test_methods_selected"] is False)
        capsule_raw = raw(target / "immutable-inputs.json")
        capsule = json.loads(capsule_raw)
        target_command = [part.replace("<CAPSULE>", str(target / "immutable-inputs.json")).replace("<CAPSULE_SHA256>", sha256(capsule_raw).hexdigest()).replace("<PURE_PLAN_SHA256>", args.plan_sha256).replace("<FINAL_SOURCE_HEAD>", args.source_commit).replace("<INNER_OUTPUT>", str(target / "inner")) for part in control["inner_argv_template"]]
        checks["outer_intent"] = (intent["source_commit"] == args.source_commit and intent["plan_sha256"] == args.plan_sha256
            and intent["capsule_sha256"] == sha256(capsule_raw).hexdigest() and intent["argv"] == target_command)
        checks["capsule"] = (base64.b64decode(capsule["plan"], validate=True) == plan_raw
            and set(capsule["inputs"]) == set(plan["input_files"])
            and all(base64.b64decode(capsule["inputs"][name], validate=True) == frozen[name] for name in plan["input_files"]))
        checks["outer_END_TAIL"] = (execution["source_commit"] == args.source_commit and execution["actual_host_exit"] == 0
            and execution["inner"] == inner and execution["error"] is None and execution["source_or_deadline_drift"] is None
            and execution["actual_host_reaped"] is True and execution["both_raw_pipes_EOF"] is True
            and execution["complete_inner_END"] is True and execution["classification"] == "PASS_LIMITED_PURE_ONLY"
            and execution["raw_sticky"] is False and execution["outer_return_status"] == 0
            and end["complete"] is True and end["actual_host_exit"] == 0 and end["actual_host_reaped"] is True
            and tail["late"] is False and tail["outer_return_status"] == 0 and tail["caller_must_observe_actual_outer_exit"] is True)
        checks["target_raw"] = (len(stdout) + len(stderr) + reserved + TRAILER <= 32768 and all(
            execution["raw_files"][name] == {"bytes": len(value), "sha256": sha256(value).hexdigest()}
            for name, value in (("first.stdout.txt", stdout), ("first.stderr.txt", stderr))))
        checks["source_after"] = (git("rev-parse", "HEAD").decode().strip() == args.source_commit
            and all(raw(ROOT / name) == value for name, value in frozen.items())
            and raw(ROOT / PLAN) == plan_raw and raw(ROOT / CALLER_PLAN) == caller_raw)
        names = ("immutable-inputs.json", "intent.json", "first.stdout.txt", "first.stderr.txt",
                 "actual-host-exit.txt", "execution.json", "END.json", "TAIL.json", "inner/intent.json", "inner/execution.json")
        checks["combined_logical_disk"] = sum((target / name).stat().st_size for name in names) + CONTROL_LIMIT + RAW_LIMIT <= 8 * 1024 * 1024
    except BaseException as failure:
        error = error or type(failure).__name__
    checks["caller_completion_window"] = time.monotonic() < deadline + 2.2
    passed = bool(checks) and all(checks.values()) and rc == 0 and reaped and eof and error is None and reserved == 0 and not sticky and cleanup_attempts == 0
    status = 0 if passed else 126
    trailer = encode({"event": "ADMISSION_CALLER_RAW_END", "outer_actual_exit": rc, "outer_reaped": reaped,
        "both_EOF": eof, "status": status, "sticky": sticky})
    if len(trailer) > TRAILER or os.write(streams[1], trailer) != len(trailer):
        status, sticky = 126, True
    for fd in streams:
        os.fsync(fd)
        os.close(fd)
    launcher_raw = {}
    for name in ("launcher.stdout.txt", "launcher.stderr.txt"):
        value = raw(caller / name, RAW_LIMIT)
        launcher_raw[name] = {"bytes": len(value), "sha256": sha256(value).hexdigest()}
    finished = time.monotonic_ns()
    put(caller / "actual-exit.json", {"source_commit": args.source_commit, "plan_sha256": args.plan_sha256,
        "caller_plan_sha256": args.caller_plan_sha256, "outer_actual_exit": rc, "outer_actual_reaped": reaped,
        "both_launcher_pipes_EOF": eof, "start_gate_released": released, "cleanup_signals": cleanup_signal,
        "cleanup_signal_attempts": cleanup_attempts,
        "monotonic_start_ns": started, "outer_launch_ns": launch_started, "monotonic_actual_wait_end_ns": wait_end,
        "monotonic_through_validation_ns": finished,
        "elapsed_through_wait_and_validation_ns": finished - started, "launcher_payload_bytes": reserved,
        "launcher_raw_sticky": sticky, "checks": checks, "error": error, "classification": "PASS_LIMITED_PURE_ONLY" if status == 0 else "UNKNOWN",
        "launcher_raw_files": launcher_raw,
        "preserved_outer_classification": outer_classification,
        "caller_return_status": status, "caller_own_future_exit_not_certified": True})
    put(caller / "CALLER_END.json", {"outer_actual_exit_observed": rc, "outer_actual_reaped": reaped,
        "status": status, "monotonic_after_actual_outer_wait_ns": finished,
        "this_is_not_caller_own_future_exit": True})
    return 126 if time.monotonic() >= deadline + 2.2 else status


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--caller-plan-sha256", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--caller-output", required=True)
    args = parser.parse_args()
    try:
        raise SystemExit(main(args))
    except SystemExit:
        raise
    except BaseException as failure:
        if getattr(args, "created", None) is not None:
            put(args.created / "CALLER_UNKNOWN.json", {"error": type(failure).__name__,
                "actual_outer_exit_observed": getattr(args, "outer_exit", None),
                "actual_outer_reaped": getattr(args, "outer_reaped", False), "complete": False, "status": 126})
        raise SystemExit(126)
