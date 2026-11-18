"""Root-owned once-only PURE envelope. No implicit authorization or native case.

Outer mode binds Git/physical bytes, creates one new private output namespace,
and owns a timeout/taskset interpreter. Inner mode executes selected pinned AST
with inert dependencies; it never rereads a target from the filesystem.
"""
import argparse
import ast
import base64
import builtins
from contextlib import ExitStack, contextmanager
from hashlib import sha256
import hashlib
import io
import itertools
import json
import linecache
import os
from pathlib import Path
import selectors
import stat
import subprocess
import sys
import threading
import time
import types
import unittest
from unittest.mock import patch


DRIVER = "tests/native_sh_capture_pure_once.py"
PLAN = "evidence/reviews/native-sh-capture-handshake/pure-once-plan.json"
RAW_LIMIT, TRAILER_RESERVE, FILE_LIMIT = 256 * 1024, 512, 2 * 1024 * 1024
ROOT = Path(__file__).resolve().parents[1]
INPUT_NAMES = {DRIVER, "uta/durable_process.py", "tests/native_sh_capture_fixture.py",
    "tests/test_native_sh_capture_protocol_pure.py", "tests/test_durable_faults.py",
    "tests/test_expired_gate_failure_evidence.py", "evidence/reviews/expired-gate-failure-5a/original-ast.json",
    "evidence/reviews/native-sh-capture-handshake/source-closure.json",
    "docs/native-sh-capture-pure-once-envelope.md"}
OUTPUT_CREATED = False
HOST_FACTS = {"attempted": False, "exit": None, "reaped": False}
BOOTSTRAP = r'''
import base64, hashlib, json, os, stat, sys
fd = os.open(sys.argv[1], os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
try:
    before = os.fstat(fd)
    if not stat.S_ISREG(before.st_mode) or before.st_size > 8*1024*1024:
        raise RuntimeError('capsule is not a bounded regular file')
    parts = []
    while True:
        block = os.read(fd, 65536)
        if not block: break
        parts.append(block)
        if sum(map(len, parts)) > 8*1024*1024: raise RuntimeError('capsule overflow')
    after = os.fstat(fd)
finally:
    os.close(fd)
raw = b''.join(parts)
if ((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)
    != (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)
    or len(raw) != before.st_size or hashlib.sha256(raw).hexdigest() != sys.argv[2]):
    raise RuntimeError('capsule identity changed')
capsule = json.loads(raw)
source = base64.b64decode(capsule['files']['tests/native_sh_capture_pure_once.py'], validate=True)
if hashlib.sha256(source).hexdigest() != capsule['pins']['tests/native_sh_capture_pure_once.py']['sha256']:
    raise RuntimeError('inner driver bytes differ')
scope = {'__name__':'nshc_pinned_inner', '__file__':capsule['root']+'/tests/native_sh_capture_pure_once.py'}
exec(compile(source, scope['__file__'], 'exec', dont_inherit=True), scope)
raise SystemExit(scope['inner'](capsule, int(sys.argv[3])))
'''


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("ascii")


def private_file(path, data=None, *, read_write=False):
    fd = os.open(path, (os.O_RDWR if read_write else os.O_WRONLY) | os.O_CREAT | os.O_EXCL
                 | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    os.fchmod(fd, 0o600)
    if data is not None:
        try:
            if os.write(fd, data) != len(data):
                raise OSError("private metadata short write")
            os.fsync(fd)
        finally:
            os.close(fd)
        return None
    return fd


def regular_bytes(path, limit=FILE_LIMIT):
    path = Path(path)
    if not path.is_absolute() or path.resolve() != path:
        raise ValueError("source path is not the exact physical path")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise ValueError("source is not a bounded regular file")
        chunks, size = [], 0
        while True:
            block = os.read(fd, 65536)
            if not block:
                break
            size += len(block)
            if size > limit:
                raise ValueError("source grew beyond bound")
            chunks.append(block)
        after = os.fstat(fd)
    finally:
        os.close(fd)
    keys = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns",
            "st_mode", "st_uid", "st_gid", "st_nlink")
    identity = {key: getattr(before, key) for key in keys}
    raw = b"".join(chunks)
    if identity != {key: getattr(after, key) for key in keys} or len(raw) != before.st_size:
        raise ValueError("source changed during physical read")
    return raw, {"bytes": len(raw), "sha256": sha256(raw).hexdigest(), "physical": identity}


def git(*arguments):
    result = subprocess.run(["/usr/bin/git", "--no-optional-locks", "-C", str(ROOT), *arguments],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3,
        env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null"})
    if len(result.stdout) > FILE_LIMIT or result.stderr:
        raise ValueError("unexpected Git output")
    return result.stdout


def snapshot(plan, revision):
    if git("rev-parse", "HEAD").decode().strip() != revision:
        raise ValueError("actual Git HEAD differs from frozen revision")
    frozen, facts = {}, {}
    for name, pin in plan["input_files"].items():
        if name.startswith("/") or ".." in Path(name).parts:
            raise ValueError("source escapes checkout")
        raw, fact = regular_bytes(ROOT / name)
        if {key: fact[key] for key in ("bytes", "sha256")} != pin:
            raise ValueError("physical length/SHA differs: " + name)
        if int(git("cat-file", "-s", revision + ":" + name)) != pin["bytes"]:
            raise ValueError("Git blob length differs before content read")
        blob = git("show", revision + ":" + name)
        if raw != blob:
            raise ValueError("physical source differs from Git blob: " + name)
        frozen[name], facts[name] = raw, fact
    return frozen, facts


class SharedRaw:
    """Charge whole request before os.write; never refund after uncertainty."""
    def __init__(self, stdout_fd, stderr_fd):
        self.fds = {"stdout": stdout_fd, "stderr": stderr_fd}
        self.reserved, self.written, self.failed = 0, 0, False

    def write(self, label, data):
        if self.failed:
            return  # Failure is sticky; only the independently reserved trailer remains.
        available = RAW_LIMIT - TRAILER_RESERVE - self.reserved
        if len(data) > available:
            self.failed = True
            data = data[:available]
        self.reserved += len(data)  # Includes every byte even if the write is short.
        if not data:
            return
        try:
            count = os.write(self.fds[label], data)
            if type(count) is not int or count != len(data):
                self.failed = True
            if type(count) is int and 0 < count <= len(data):
                self.written += count
        except BaseException:
            self.failed = True

    def trailer(self, value):
        data = encoded(value)
        if len(data) > TRAILER_RESERVE:
            self.failed = True
            data = b'{"event":"NSHC_HOST_END","complete":false,"status":125}\n'
        # The independent 512-byte reservation was never available to write().
        try:
            count = os.write(self.fds["stderr"], data)
            if count != len(data):
                self.failed = True
        except BaseException:
            self.failed = True


def forbidden(*args, **kwargs):
    raise AssertionError("selected pure AST attempted a forbidden native capability")


def inner(capsule, control_fd):
    """Only immutable snapshots enter compile/exec; no product module imports."""
    source = {name: base64.b64decode(value, validate=True) for name, value in capsule["files"].items()}
    for name, raw in source.items():
        if {"bytes": len(raw), "sha256": sha256(raw).hexdigest()} != capsule["pins"][name]:
            raise ValueError("immutable input differs before AST selection")
    if sorted(os.sched_getaffinity(0)) != [1] or not (
            sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode
            and str(Path(sys.executable).resolve()) == capsule["python"]):
        raise ValueError("inner runtime flags or actual CPU affinity differ")
    paths = {str(Path(capsule["root"]) / name): raw for name, raw in source.items()}
    for name, raw in paths.items():
        if name.endswith(".py"):
            linecache.cache[name] = (len(raw), None, raw.decode("utf-8").splitlines(True), name)

    def frozen_read(path):
        name = os.path.normpath(os.fspath(path))
        if name not in paths:
            raise AssertionError("pure source read is not in immutable closure")
        return paths[name]

    def frozen_text(path, encoding=None, errors=None):
        return frozen_read(path).decode(encoding or "utf-8", errors or "strict")

    fixture_name = "tests/native_sh_capture_fixture.py"
    case_name = "tests/test_native_sh_capture_protocol_pure.py"
    fixture = types.ModuleType("native_sh_capture_fixture")
    fixture.__file__ = str(Path(capsule["root"]) / fixture_name)
    fixture.__dict__.update(ast=ast, sha256=sha256, json=json, os=os, Path=Path, sys=sys,
        threading=threading, monotonic=time.monotonic, CodeType=types.CodeType)
    fixture_tree = ast.parse(source[fixture_name])
    selected = [node for node in fixture_tree.body if (
        isinstance(node, ast.Assign) or isinstance(node, ast.ClassDef)
        or isinstance(node, ast.FunctionDef) and node.name != "capture_worker")]
    fixture.capture_worker = forbidden  # Inert target identity, never a real entry.
    exec(compile(ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[])),
                 fixture.__file__, "exec", dont_inherit=True), fixture.__dict__)
    namespace = {"__name__": "nshc_selected_cases", "__file__": str(Path(capsule["root"]) / case_name),
        "ast": ast, "contextmanager": contextmanager, "hashlib": hashlib, "itertools": itertools,
        "json": json, "Path": Path, "CodeType": types.CodeType, "FunctionType": types.FunctionType,
        "SimpleNamespace": types.SimpleNamespace, "unittest": unittest, "patch": patch,
        "fixture": fixture, "ROOT": Path(capsule["root"])}
    case_tree = ast.parse(source[case_name])
    selected_cases = [node for node in case_tree.body if isinstance(node, ast.ClassDef)
        or isinstance(node, ast.Assign) and any(isinstance(item, ast.Name) and item.id == "OWNER" for item in node.targets)]
    exec(compile(ast.fix_missing_locations(ast.Module(body=selected_cases, type_ignores=[])),
                 namespace["__file__"], "exec", dont_inherit=True), namespace)
    case = namespace["NativeSHCaptureProtocolPureTests"]
    selected_names = sorted(unittest.defaultTestLoader.getTestCaseNames(case))
    if selected_names != capsule["methods"] or len(selected_names) != 8:
        raise AssertionError("eight-method selector changed")

    def audit(event, arguments):
        if event == "import" and arguments and str(arguments[0]).split(".", 1)[0] in {
                "uta", "sqlite3", "_sqlite3", "multiprocessing", "ctypes"}:
            forbidden()
        if event.startswith("socket.") or event in {"open", "subprocess.Popen", "os.fork", "os.forkpty",
                "os.posix_spawn", "os.posix_spawnp", "os.kill", "os.killpg", "os.pidfd_open",
                "signal.pidfd_send_signal", "fcntl.flock", "sys.settrace", "sys.setprofile",
                "ctypes.dlopen", "ctypes.dlsym", "os.mkdir", "os.link", "os.remove", "os.rename",
                "os.rmdir", "os.truncate"}:
            forbidden()

    print(json.dumps({"event": "NSHC_PURE_BEGIN", "attempt": capsule["attempt"],
        "source_commit": capsule["revision"], "actual_affinity": sorted(os.sched_getaffinity(0)),
        "methods": 8, "trace_upper_bound_exclusive": 64, "actual_trace_or_native_authorized": False}), flush=True)
    sys.addaudithook(audit)
    started = time.monotonic_ns()
    with ExitStack() as guards:
        guards.enter_context(patch.object(Path, "read_bytes", frozen_read))
        guards.enter_context(patch.object(Path, "read_text", frozen_text))
        for owner, name in ((builtins, "open"), (io, "open"), (os, "open"), (os, "write"),
                (os, "waitpid"), (os, "kill"), (os, "killpg"), (os, "sched_setaffinity"),
                (threading.Thread, "start"), (time, "sleep"), (sys, "settrace"), (sys, "setprofile")):
            guards.enter_context(patch.object(owner, name, forbidden))
        for owner, name in ((os, "pidfd_open"),):
            if hasattr(owner, name):
                guards.enter_context(patch.object(owner, name, forbidden))
        result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(case))
    forbidden_loaded = sorted(name for name in sys.modules if name.split(".", 1)[0] in
                              {"uta", "sqlite3", "_sqlite3", "multiprocessing"})
    end = {"event": "NSHC_PURE_END", "attempt": capsule["attempt"], "source_commit": capsule["revision"],
        "complete": True, "tests_run": result.testsRun, "failures": len(result.failures),
        "errors": len(result.errors), "skipped": len(result.skipped),
        "passed": result.wasSuccessful() and not forbidden_loaded, "forbidden_runtime_imports": forbidden_loaded,
        "elapsed_ns": time.monotonic_ns() - started, "actual_affinity": sorted(os.sched_getaffinity(0)),
        "actual_executable": str(Path(sys.executable).resolve()), "actual_runtime": sys.version,
        "flags": {"isolated": sys.flags.isolated, "no_site": sys.flags.no_site,
                  "dont_write_bytecode": sys.flags.dont_write_bytecode},
        "native_executed": False, "original_ci_cause_proven": False, "production_approved": False}
    sys.stdout.flush()
    sys.stderr.flush()
    data = encoded(end)
    if len(data) > 4096 or os.write(control_fd, data) != len(data):
        raise OSError("inner END control short write")
    os.fsync(control_fd)
    return 0 if end["passed"] and end["tests_run"] == 8 and not end["skipped"] else 1


def outer(args):
    global OUTPUT_CREATED
    if not args.execute:
        raise ValueError("execution requires an explicit root once GO and --execute")
    for value, length in ((args.source_commit, 40), (args.plan_sha256, 64), (args.driver_sha256, 64)):
        if len(value) != length or any(character not in "0123456789abcdef" for character in value):
            raise ValueError("source and hash arguments must be exact hexadecimal identities")
    output = Path(args.output)
    if not output.is_absolute() or output.parent.resolve() != output.parent or ROOT == output or ROOT in output.parents:
        raise ValueError("new physical private output must be outside the checkout")
    os.mkdir(output, 0o700)  # Existing/spent namespace is always rejected.
    OUTPUT_CREATED = True
    os.chmod(output, 0o700)
    plan_raw, plan_fact = regular_bytes(ROOT / PLAN)
    if plan_fact["sha256"] != args.plan_sha256:
        raise ValueError("plan SHA differs before target attempt")
    plan = json.loads(plan_raw)
    if (plan["schema"] != 1 or plan["methods_count"] != 8 or plan["cpu"] != 1 or plan["wall_seconds"] != 10
            or plan["shared_raw_limit"] != RAW_LIMIT or plan["trailer_reserve"] != TRAILER_RESERVE):
        raise ValueError("frozen pure envelope differs")
    os.sched_setaffinity(0, {1})  # Own orchestration and Git children also use only CPU 1.
    if sorted(os.sched_getaffinity(0)) != [1]:
        raise ValueError("outer actual CPU affinity differs")
    if set(plan["input_files"]) != INPUT_NAMES:
        raise ValueError("exact immutable input inventory differs")
    frozen, before = snapshot(plan, args.source_commit)
    if Path(__file__).resolve() != ROOT / DRIVER or before[DRIVER]["sha256"] != args.driver_sha256:
        raise ValueError("executed outer driver differs from frozen Git/physical bytes")
    if git("show", args.source_commit + ":" + PLAN) != plan_raw:
        raise ValueError("plan differs from exact Git source")
    python = str(Path(sys.executable).resolve())
    if python != plan["python_executable"]:
        raise ValueError("absolute Python differs from the frozen host plan")
    attempt = sha256(str(output).encode()).hexdigest()
    pins = {name: {key: fact[key] for key in ("bytes", "sha256")} for name, fact in before.items()}
    capsule = {"root": str(ROOT), "revision": args.source_commit, "attempt": attempt, "python": python,
        "pins": pins, "methods": plan["methods"],
        "files": {name: base64.b64encode(raw).decode("ascii") for name, raw in frozen.items()}}
    capsule_raw = encoded(capsule)
    if len(capsule_raw) > 8 * 1024 * 1024:
        raise ValueError("immutable capsule exceeds bound")
    private_file(output / "immutable-inputs.json", capsule_raw)
    control = private_file(output / "inner-END.raw.json", read_write=True)
    out_fd, err_fd = private_file(output / "first.stdout.txt"), private_file(output / "first.stderr.txt")
    capture = SharedRaw(out_fd, err_fd)
    command = ["/usr/bin/timeout", "--signal=KILL", "10s", "/usr/bin/taskset", "-c", "1",
        python, "-I", "-S", "-B", "-c", BOOTSTRAP, str(output / "immutable-inputs.json"),
        sha256(capsule_raw).hexdigest(), str(control)]
    intent = {"attempt": attempt, "source_commit": args.source_commit, "source_tree": git("rev-parse", "HEAD^{tree}").decode().strip(),
        "plan_sha256": args.plan_sha256, "driver_sha256": args.driver_sha256,
        "before": before, "plan_physical_before": plan_fact, "python": python, "outer_runtime": sys.version,
        "actual_outer_affinity": sorted(os.sched_getaffinity(0)),
        "host_argv_without_inline_bootstrap": [*command[:11], "<pinned-bootstrap>", *command[12:]],
        "bootstrap_sha256": sha256(BOOTSTRAP.encode()).hexdigest(),
        "shared_raw_limit": RAW_LIMIT, "trailer_reserve": TRAILER_RESERVE,
        "actual_native_target_authorized": False, "first_and_only": True}
    private_file(output / "intent.json", encoded(intent))
    process, host_exit, reaped, eof, end, after, drift = None, None, False, False, None, None, None
    host_exit_recorded = False
    host_deadline = time.monotonic() + 13
    try:
        process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, pass_fds=(control,), close_fds=True)
        HOST_FACTS["attempted"] = True
        selector = selectors.DefaultSelector()
        for label, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, label)
        # Timeout owns the interpreter's hard 10 s. This extra drain/reap
        # classification window never extends target execution or accepts PASS.
        drain_deadline = host_deadline - 1
        while selector.get_map() and time.monotonic() < drain_deadline:
            for key, _ in selector.select(.05):
                block = os.read(key.fileobj.fileno(), 8192)
                if block:
                    capture.write(key.data, block)
                else:
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
        eof = not selector.get_map()
        selector.close()
        for stream in (process.stdout, process.stderr):
            if not stream.closed:
                stream.close()
        try:
            host_exit = process.wait(timeout=max(0, host_deadline - time.monotonic()))
            reaped = True
        except subprocess.TimeoutExpired:
            pass
        HOST_FACTS.update(exit=host_exit, reaped=reaped)
        private_file(output / "actual-host-exit.txt", ("UNKNOWN" if host_exit is None else str(host_exit)).encode() + b"\n")
        host_exit_recorded = True
        os.lseek(control, 0, os.SEEK_SET)
        control_raw = os.read(control, 4097)
        if len(control_raw) <= 4096 and control_raw.endswith(b"\n"):
            try:
                end = json.loads(control_raw)
            except (ValueError, UnicodeError):
                pass
        try:
            _, after = snapshot(plan, args.source_commit)
            plan_after, plan_after_fact = regular_bytes(ROOT / PLAN)
            if after != before or plan_after != plan_raw or plan_after_fact != plan_fact:
                drift = "source_or_plan_changed"
        except BaseException as error:
            drift = type(error).__name__
        valid_end = (type(end) is dict and end.get("event") == "NSHC_PURE_END"
            and end.get("attempt") == attempt and end.get("source_commit") == args.source_commit
            and end.get("complete") is True and end.get("actual_affinity") == [1]
            and type(end.get("tests_run")) is int and end["tests_run"] == 8)
        passed = (valid_end and host_exit == 0 and reaped and eof and drift is None
                  and end.get("passed") is True and not end.get("skipped") and not capture.failed)
        classification = "PASS_CONDITIONAL_PURE_ONLY" if passed else (
            "FAIL" if valid_end and host_exit == 1 and reaped and eof and drift is None and not capture.failed else "UNKNOWN")
        status = 125 if capture.failed else (0 if passed else 1 if classification == "FAIL" else 126)
        capture.trailer({"event": "NSHC_HOST_END", "host_exit": host_exit, "reaped": reaped,
            "eof": eof, "complete_inner_END": valid_end, "classification": classification,
            "capture_sticky_125": capture.failed, "status": status})
        if capture.failed:
            classification, status = "UNKNOWN", 125
        for fd in (out_fd, err_fd):
            os.fsync(fd)
        raw_files = {name: regular_bytes(output / name, RAW_LIMIT)[1]
                     for name in ("first.stdout.txt", "first.stderr.txt")}
        if sum(fact["bytes"] for fact in raw_files.values()) > RAW_LIMIT:
            classification, status, capture.failed = "UNKNOWN", 125, True
        execution = {"attempt": attempt, "actual_host_exit": host_exit, "actual_host_reaped": reaped,
            "both_raw_pipes_EOF": eof, "inner_END": end, "source_after": after, "source_drift": drift,
            "classification": classification, "envelope_exit": status, "shared_raw_reserved": capture.reserved,
            "payload_actual_written": capture.written, "trailer_reserved": TRAILER_RESERVE,
            "raw_capture_sticky_125": capture.failed, "raw_files": raw_files,
            "actual_native_target_executed": False,
            "old_47b_attempts": 0, "production_approved": False}
        private_file(output / "execution.json", encoded(execution))
        private_file(output / "END.json", encoded({"event": "NSHC_ENVELOPE_END",
            "complete": bool(valid_end and reaped and eof and drift is None and not capture.failed),
            "attempt": attempt, "classification": classification, "envelope_exit": status,
            "actual_host_exit": host_exit, "actual_host_reaped": reaped, "production_approved": False}))
        return status
    finally:
        if process is not None and not reaped:
            for stream in (process.stdout, process.stderr):
                if stream is not None and not stream.closed:
                    stream.close()
            try:
                host_exit = process.wait(timeout=max(0, host_deadline - time.monotonic()))
                reaped = True
            except subprocess.TimeoutExpired:
                pass
            HOST_FACTS.update(exit=host_exit, reaped=reaped)
        if process is not None and not host_exit_recorded:
            private_file(output / "actual-host-exit.txt", ("UNKNOWN" if host_exit is None else str(host_exit)).encode() + b"\n")
        for fd in (control, out_fd, err_fd):
            os.close(fd)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--output", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--driver-sha256", required=True)
    arguments = parser.parse_args()
    try:
        status = outer(arguments)
    except BaseException as error:
        if OUTPUT_CREATED:
            private_file(Path(arguments.output) / "ENVELOPE_UNKNOWN.json", encoded({
                "event": "NSHC_ENVELOPE_UNKNOWN", "complete": False, "host": HOST_FACTS,
                "error_type": type(error).__name__, "envelope_exit": 126,
                "no_retry_authorized": True, "production_approved": False}))
        status = 126
    raise SystemExit(status)
