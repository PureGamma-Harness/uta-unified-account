"""Fixed once-only parent FD capture for the seven fixed linear-admission replay tests.

No native case or SQL mode exists. Git preparation is read-only; the sole target
is an owned timeout/taskset interpreter executing retained approved buffers.
"""
import argparse
import base64
from hashlib import sha256
import json
import os
from pathlib import Path
import selectors
import stat
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
PLAN = "evidence/reviews/admission-decision-replay/pure-once-plan.json"
INNER = "tools/run_admission_pure_once.py"
RAW_LIMIT, TRAILER_RESERVE = 32768, 512
FILE_LIMIT = 4 * 1024 * 1024
LOGICAL_LIMIT = 8 * 1024 * 1024
CONTROL_RESERVED = 0
INNER_MODE = bool(globals().get("_RETAINED_INNER_MODE", False))
BOOTSTRAP = r'''
import base64, hashlib, json, os, pathlib, stat, sys
path = pathlib.Path(sys.argv[1])
if path.resolve() != path or not stat.S_ISREG(path.lstat().st_mode):
    raise ValueError("nonregular retained capsule")
fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
with os.fdopen(fd, "rb") as handle:
    before = os.fstat(handle.fileno())
    raw = handle.read(4 * 1024 * 1024 + 1)
    after = os.fstat(handle.fileno())
if len(raw) > 4 * 1024 * 1024 or any(getattr(before, k) != getattr(after, k)
        for k in ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")):
    raise ValueError("retained capsule changed")
if hashlib.sha256(raw).hexdigest() != sys.argv[2]:
    raise ValueError("retained capsule SHA differs")
capsule = json.loads(raw)
plan_raw = base64.b64decode(capsule["plan"], validate=True)
if hashlib.sha256(plan_raw).hexdigest() != sys.argv[3]:
    raise ValueError("approved plan SHA differs")
plan = json.loads(plan_raw)
frozen = {name: base64.b64decode(value, validate=True) for name, value in capsule["inputs"].items()}
if set(frozen) != set(plan["input_files"]):
    raise ValueError("retained input set differs")
for name, expected in plan["input_files"].items():
    value = frozen[name]
    if {"bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()} != expected:
        raise ValueError("retained input pin differs")
root = pathlib.Path(capsule["root"])
driver = "tools/run_admission_pure_once.py"
namespace = {"__name__": "admission_retained_inner", "__file__": str(root / driver),
    "_RETAINED_INNER_MODE": True,
    "_PARENT_CAPTURE_CAPSULE": {"plan_raw": plan_raw, "inputs": frozen}}
exec(compile(frozen[driver], str(root / driver), "exec"), namespace)
raise SystemExit(namespace["inner"](["--parent-captured-stdio", "--source-commit", sys.argv[4],
    "--plan-sha256", sys.argv[3], "--private-directory", sys.argv[5]]))
'''


def read_regular(path, limit=FILE_LIMIT):
    if path.resolve() != path or not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError("not a canonical regular file")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as handle:
        before = os.fstat(handle.fileno())
        raw = handle.read(limit + 1)
        after = os.fstat(handle.fileno())
    keys = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_mode")
    if len(raw) > limit or any(getattr(before, key) != getattr(after, key) for key in keys):
        raise ValueError("file exceeded limit or changed during read")
    return raw


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def new_file(path, raw=None):
    global CONTROL_RESERVED
    if raw is not None:
        # The retained child has only two fixed control writes, sharing 1MiB.
        # Parent control/capsule bytes reserve that allowance and all raw bytes.
        limit = 1024 * 1024 if INNER_MODE else LOGICAL_LIMIT - 1024 * 1024 - RAW_LIMIT
        if len(raw) > FILE_LIMIT or CONTROL_RESERVED + len(raw) > limit:
            raise ValueError("fixed logical control-file budget exhausted")
        CONTROL_RESERVED += len(raw)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    if raw is None:
        return fd
    with os.fdopen(fd, "wb") as handle:
        if handle.write(raw) != len(raw):
            raise OSError("short control-file write")
        handle.flush()
        os.fsync(handle.fileno())


def git(*arguments, seconds=3):
    result = subprocess.run(["/usr/bin/git", "--no-optional-locks", "-C", str(ROOT), *arguments],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=seconds,
        env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null"})
    if len(result.stdout) > FILE_LIMIT or result.stderr:
        raise ValueError("unexpected Git output")
    return result.stdout


class SharedRaw:
    def __init__(self):
        self.reserved, self.written, self.failed = 0, 0, False

    def payload(self, fd, raw):
        if self.failed:
            return
        if self.reserved + len(raw) > RAW_LIMIT - TRAILER_RESERVE:
            self.failed = True
            return
        self.reserved += len(raw)  # Charged before the only attempted FD write.
        try:
            count = os.write(fd, raw)
            if type(count) is not int or not 0 <= count <= len(raw):
                self.failed = True
                return
            self.written += count
            if count != len(raw):
                self.failed = True  # No refund, continuation, or later payload.
        except BaseException:
            self.failed = True

    def trailer(self, fd, value):
        raw = encoded(value)
        if len(raw) > TRAILER_RESERVE:
            self.failed = True
            return
        try:
            if os.write(fd, raw) != len(raw):
                self.failed = True
        except BaseException:
            self.failed = True


def inner(argv):
    """Execute only the seven named financial-predicate methods from retained bytes."""
    import _thread
    import dataclasses
    import datetime
    import decimal
    import fractions
    import hashlib
    import linecache
    import importlib.abc
    import importlib.util
    import re
    import threading
    from types import ModuleType
    import unittest

    parser = argparse.ArgumentParser(description=inner.__doc__)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--private-directory", required=True, type=Path)
    parser.add_argument("--parent-captured-stdio", action="store_true")
    args = parser.parse_args(argv)
    capsule = globals().get("_PARENT_CAPTURE_CAPSULE")
    if not args.parent_captured_stdio or type(capsule) is not dict:
        raise ValueError("retained parent-captured mode is mandatory")
    plan_raw, frozen = capsule["plan_raw"], capsule["inputs"]
    if sha256(plan_raw).hexdigest() != args.plan_sha256:
        raise ValueError("unapproved plan")
    plan = json.loads(plan_raw)
    methods = (
        "test_manual_strict_mm_and_legal_im_equality",
        "test_full_fee_and_existing_live_order_reserves",
        "test_reduce_only_allocation_and_surplus_are_separate",
        "test_settlement_dust_flip_and_short_close_manual_values",
        "test_reduce_only_requires_native_boolean_halt_state",
        "test_missing_legacy_and_unknown_contract_never_verify",
        "test_projection_fee_versions_and_control_tampering_fail",
    )
    if plan["methods"] != list(methods) or set(frozen) != set(plan["input_files"]):
        raise ValueError("fixed seven-method/input scope differs")
    for name, expected in plan["input_files"].items():
        value = frozen[name]
        if type(value) is not bytes or {"bytes": len(value), "sha256": sha256(value).hexdigest()} != expected:
            raise ValueError("retained source pin differs")
        linecache.cache[str(ROOT / name)] = (
            len(value), None, value.decode("utf-8").splitlines(True), str(ROOT / name))
    output = args.private_directory
    if (not output.is_absolute() or output.resolve() != output
            or output.name != "inner" or output.parent.parent != Path("/workspace")):
        raise ValueError("new canonical inner namespace required")
    output.mkdir(mode=0o700)
    executable = Path(sys.executable).resolve()
    binary = read_regular(executable, 64 * 1024 * 1024)
    runtime = {"sys_executable": sys.executable, "resolved_executable": str(executable),
        "executable_bytes": len(binary), "executable_sha256": sha256(binary).hexdigest(),
        "sys_version": sys.version, "affinity": sorted(os.sched_getaffinity(0)),
        "flags": {"isolated": sys.flags.isolated, "no_site": sys.flags.no_site,
                  "dont_write_bytecode": sys.flags.dont_write_bytecode}}
    if runtime != plan["expected_runtime"]:
        raise ValueError("actual runtime/CPU differs from plan")
    if any(name == "uta" or name.startswith("uta.") for name in sys.modules):
        raise ValueError("UTA preloaded outside retained source")
    new_file(output / "intent.json", encoded({"source_commit": args.source_commit,
        "plan_sha256": args.plan_sha256, "runtime": runtime, "input_files": plan["input_files"],
        "fixed_methods": list(methods), "caller_actual_exit_required": True}))
    forbidden = []

    def denied(event):
        if len(forbidden) < 16:
            forbidden.append(event)
        raise RuntimeError("pure admission scope forbids " + event)

    def audit(event, arguments):
        if event in {"sqlite3.connect", "subprocess.Popen", "os.fork", "os.forkpty", "os.exec",
                     "os.posix_spawn", "os.system", "os.kill", "os.killpg",
                     "socket.__new__", "socket.connect", "socket.bind"}:
            denied(event)
        if event == "open" and arguments and isinstance(arguments[0], (str, bytes)):
            path = os.fsdecode(arguments[0])
            if path.startswith("/proc/") or path.endswith((".sqlite", ".sqlite3", ".db", "-wal", "-shm")):
                denied("open:authority_or_proc")

    def no_thread(*arguments, **keywords):
        denied("thread_start")

    sys.addaudithook(audit)
    threading.Thread.start = no_thread
    _thread.start_new_thread = no_thread
    if hasattr(threading, "_start_new_thread"):
        threading._start_new_thread = no_thread

    class FrozenLoader(importlib.abc.Loader):
        def __init__(self, relative):
            self.relative = relative
        def create_module(self, spec):
            return None
        def exec_module(self, module):
            exec(compile(frozen[self.relative], str(ROOT / self.relative), "exec"), module.__dict__)

    class FrozenUTA(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname != "uta" and not fullname.startswith("uta."):
                return None
            relative = "uta/__init__.py" if fullname == "uta" else fullname.replace(".", "/") + ".py"
            if relative not in frozen:
                raise ImportError("unretained UTA module: " + fullname)
            return importlib.util.spec_from_file_location(fullname, ROOT / relative,
                loader=FrozenLoader(relative), submodule_search_locations=[] if fullname == "uta" else None)

    sys.meta_path.insert(0, FrozenUTA())
    fixture = ModuleType("admission_pure_fixture")
    fixture.__file__ = str(ROOT / "tests/test_admission_policy_reference.py")
    sys.modules[fixture.__name__] = fixture

    print(json.dumps({"event": "ADMISSION_PURE_BEGIN", "source_commit": args.source_commit,
        "runtime": runtime, "selected_methods": list(methods), "input_count": len(frozen)}), flush=True)
    started = time.monotonic_ns()
    exec(compile(frozen["tests/test_admission_policy_reference.py"], fixture.__file__, "exec"), fixture.__dict__)
    result = unittest.TextTestRunner(stream=sys.stderr, verbosity=2).run(
        unittest.TestSuite(fixture.AdmissionPolicyReferenceTests(name) for name in methods))
    elapsed = time.monotonic_ns() - started
    loaded = sorted(name for name in sys.modules if name == "uta" or name.startswith("uta."))
    after = {name: read_regular(ROOT / name) for name in frozen}
    unchanged = after == frozen and read_regular(ROOT / PLAN) == plan_raw
    actual_runtime_after = sorted(os.sched_getaffinity(0))
    passed = (result.testsRun == 7 and result.wasSuccessful() and not result.skipped
        and not result.expectedFailures and not result.unexpectedSuccesses
        and not forbidden and unchanged and actual_runtime_after == [1]
        and loaded == ["uta", "uta.decision_audit", "uta.ledger", "uta.market", "uta.models", "uta.portfolio", "uta.products", "uta.reserve_kernel", "uta.risk", "uta.scenario_margin", "uta.storage"])
    receipt = {"source_commit_invoker_label": args.source_commit, "runtime": runtime,
        "selected_methods": list(methods), "tests_run": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors),
        "skipped": len(result.skipped), "expected_failures": len(result.expectedFailures),
        "unexpected_successes": len(result.unexpectedSuccesses), "elapsed_ns": elapsed,
        "input_pins_after": plan["input_files"], "source_before_after_equal": unchanged,
        "forbidden_attempts": forbidden, "loaded_UTA_modules": loaded,
        "actual_affinity_after": actual_runtime_after, "returncode": 0 if passed else 1,
        "SQL_or_workers_or_server_or_network_authorized": False,
        "SQL_test_methods_selected": False, "production_approved": False}
    new_file(output / "execution.json", encoded(receipt))
    print(json.dumps({"event": "ADMISSION_PURE_END", **receipt}), flush=True)
    return 0 if passed else 1


def run(args):
    if not args.execute:
        raise ValueError("explicit once-only execution flag required")
    os.sched_setaffinity(0, {1})
    if sorted(os.sched_getaffinity(0)) != [1]:
        raise ValueError("CPU1 binding failed")
    if git("rev-parse", "HEAD").decode().strip() != args.source_commit:
        raise ValueError("actual source HEAD differs")
    plan_raw = read_regular(ROOT / PLAN)
    if sha256(plan_raw).hexdigest() != args.plan_sha256 or plan_raw != git("show", args.source_commit + ":" + PLAN):
        raise ValueError("plan differs from approved SHA/Git")
    plan = json.loads(plan_raw)
    frozen = {}
    for name, pin in plan["input_files"].items():
        if name.startswith("/") or ".." in Path(name).parts:
            raise ValueError("source path escapes checkout")
        raw = read_regular(ROOT / name)
        if {"bytes": len(raw), "sha256": sha256(raw).hexdigest()} != pin or raw != git("show", args.source_commit + ":" + name):
            raise ValueError("source physical/Git pin differs: " + name)
        frozen[name] = raw
    output = Path(args.output)
    if (not output.is_absolute() or output.resolve() != output
            or output.parent != Path("/workspace")):
        raise ValueError("output is not new canonical absolute namespace")
    output.mkdir(mode=0o700)
    args.output_created = True
    capsule_raw = encoded({"root": str(ROOT), "plan": base64.b64encode(plan_raw).decode(),
        "inputs": {name: base64.b64encode(raw).decode() for name, raw in frozen.items()}})
    if len(capsule_raw) > FILE_LIMIT:
        raise ValueError("capsule exceeds bound")
    capsule = output / "immutable-inputs.json"
    new_file(capsule, capsule_raw)
    command = ["/usr/bin/timeout", "--signal=KILL", "10s", "/usr/bin/taskset", "-c", "1",
        plan["expected_runtime"]["resolved_executable"], "-I", "-S", "-B", "-c", BOOTSTRAP,
        str(capsule), sha256(capsule_raw).hexdigest(), args.plan_sha256, args.source_commit, str(output / "inner")]
    new_file(output / "intent.json", encoded({"source_commit": args.source_commit,
        "plan_sha256": args.plan_sha256, "capsule_sha256": sha256(capsule_raw).hexdigest(),
        "argv": command, "actual_outer_affinity": sorted(os.sched_getaffinity(0)),
        "raw_limit": RAW_LIMIT, "trailer_reserve": TRAILER_RESERVE, "attempt": 1,
        "SQL_service_worker_authorized": False}))
    out_fd = new_file(output / "first.stdout.txt")
    err_fd = new_file(output / "first.stderr.txt")
    capture, process, host_exit, reaped, eof = SharedRaw(), None, None, False, False
    started = time.monotonic_ns()
    deadline = time.monotonic() + 12
    error, drift = None, None
    try:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, cwd=ROOT, close_fds=True)
        args.host_started = True
        selector = selectors.DefaultSelector()
        for stream, destination in ((process.stdout, out_fd), (process.stderr, err_fd)):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, destination)
        while selector.get_map() and time.monotonic() < deadline:
            for key, unused in selector.select(min(.05, max(0, deadline - time.monotonic()))):
                try:
                    raw = os.read(key.fileobj.fileno(), 65536)
                except BlockingIOError:
                    continue
                if raw:
                    capture.payload(key.data, raw)
                else:
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
        eof = not selector.get_map()
        selector.close()
        host_exit = process.wait(timeout=max(0, deadline - time.monotonic()))
        reaped = True
    except BaseException as failure:
        error = type(failure).__name__
    finally:
        if process is not None:
            for stream in (process.stdout, process.stderr):
                if not stream.closed:
                    stream.close()
            if not reaped:
                try:
                    host_exit = process.wait(timeout=max(0, deadline - time.monotonic()))
                    reaped = True
                except BaseException:
                    pass
        args.host_exit, args.host_reaped = host_exit, reaped
        new_file(output / "actual-host-exit.txt", ("UNKNOWN" if host_exit is None else str(host_exit)).encode() + b"\n")
    finished = time.monotonic_ns()
    try:
        if time.monotonic() >= deadline:
            raise ValueError("outer target/drain deadline exceeded")
        if git("rev-parse", "HEAD", seconds=max(.001, min(1, deadline - time.monotonic()))).decode().strip() != args.source_commit:
            raise ValueError("source HEAD changed")
        for name, expected in frozen.items():
            if read_regular(ROOT / name) != expected:
                raise ValueError("source changed")
        if read_regular(ROOT / PLAN) != plan_raw or time.monotonic() >= deadline:
            raise ValueError("plan changed or outer completion late")
    except BaseException as failure:
        drift = type(failure).__name__
    inner, valid_end = None, False
    try:
        lines = read_regular(output / "first.stdout.txt", RAW_LIMIT).splitlines()
        records = [json.loads(line) for line in lines]
        if len(records) == 2 and records[0]["event"] == "ADMISSION_PURE_BEGIN" and records[1]["event"] == "ADMISSION_PURE_END":
            inner = json.loads(read_regular(output / "inner/execution.json"))
            valid_end = (records[1] == {"event": "ADMISSION_PURE_END", **inner}
                and inner["source_commit_invoker_label"] == args.source_commit
                and inner["input_pins_after"] == plan["input_files"]
                and type(inner["tests_run"]) is int and inner["tests_run"] == 7
                and inner["source_before_after_equal"] is True
                and inner["selected_methods"] == plan["methods"]
                and inner["runtime"] == plan["expected_runtime"]
                and all(type(inner[field]) is int for field in
                    ("returncode", "failures", "errors", "skipped", "expected_failures", "unexpected_successes")))
    except BaseException:
        pass
    complete = valid_end and reaped and eof and error is None and drift is None and not capture.failed
    passed = (complete and host_exit == 0 and inner["returncode"] == 0 and inner["failures"] == 0
              and inner["errors"] == 0 and inner["skipped"] == 0
              and inner["expected_failures"] == 0 and inner["unexpected_successes"] == 0
              and inner["loaded_UTA_modules"] == ["uta", "uta.decision_audit", "uta.ledger", "uta.market", "uta.models", "uta.portfolio", "uta.products", "uta.reserve_kernel", "uta.risk", "uta.scenario_margin", "uta.storage"]
              and inner["SQL_test_methods_selected"] is False and inner["forbidden_attempts"] == [])
    classification = "PASS_LIMITED_PURE_ONLY" if passed else "FAIL" if complete and host_exit == 1 else "UNKNOWN"
    status = 0 if passed else 1 if classification == "FAIL" else 125 if capture.failed else 126
    capture.trailer(err_fd, {"event": "ADMISSION_PURE_HOST_END", "host_exit": host_exit,
        "reaped": reaped, "EOF": eof, "classification": classification, "status": status,
        "raw_sticky": capture.failed})
    if capture.failed:
        classification, status = "UNKNOWN", 125
    for fd in (out_fd, err_fd):
        os.fsync(fd)
        os.close(fd)
    raw_facts = {}
    for name in ("first.stdout.txt", "first.stderr.txt"):
        raw = read_regular(output / name, RAW_LIMIT)
        raw_facts[name] = {"bytes": len(raw), "sha256": sha256(raw).hexdigest()}
    if sum(item["bytes"] for item in raw_facts.values()) > RAW_LIMIT:
        classification, status = "UNKNOWN", 125
    new_file(output / "execution.json", encoded({"source_commit": args.source_commit,
        "actual_host_exit": host_exit, "actual_host_reaped": reaped, "both_raw_pipes_EOF": eof,
        "monotonic_start_ns": started, "monotonic_end_ns": finished, "elapsed_ns": finished - started,
        "inner": inner, "complete_inner_END": valid_end, "error": error, "source_or_deadline_drift": drift,
        "raw_reserved": capture.reserved, "raw_written": capture.written, "raw_sticky": capture.failed,
        "raw_files": raw_facts, "classification": classification, "outer_return_status": status,
        "production_approved": False}))
    new_file(output / "END.json", encoded({"event": "ADMISSION_PURE_ENVELOPE_END", "classification": classification,
        "outer_return_status": status, "actual_host_exit": host_exit, "actual_host_reaped": reaped,
        "complete": bool(complete and not capture.failed), "production_approved": False}))
    # Final publication/fsync is in the same completion guard. An earlier END
    # cannot certify a successful future process exit; caller must observe it.
    tail_ns = time.monotonic_ns()
    late = time.monotonic() >= deadline
    new_file(output / "TAIL.json", encoded({"monotonic_through_final_publication_ns": tail_ns,
        "late": late, "caller_must_observe_actual_outer_exit": True,
        "outer_return_status": 126 if late else status, "production_approved": False}))
    if late or time.monotonic() >= deadline:
        return 126
    return status


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        raise SystemExit(run(args))
    except SystemExit:
        raise
    except BaseException as error:
        if getattr(args, "output_created", False):
            new_file(Path(args.output) / "ENVELOPE_UNKNOWN.json", encoded({"error_type": type(error).__name__,
                "host_started": getattr(args, "host_started", False), "actual_host_exit": getattr(args, "host_exit", None),
                "actual_host_reaped": getattr(args, "host_reaped", False), "complete": False, "status": 126}))
        raise SystemExit(126)
