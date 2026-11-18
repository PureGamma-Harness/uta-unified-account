"""Fixed once-only parent FD capture for four local admission SQL methods.

Four new synthetic DBs only, with read-only reopen of those newly created here.
The sole target is an owned timeout/taskset interpreter executing retained buffers.
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
PLAN = "evidence/reviews/admission-sql4/once-plan.json"
INNER = "tools/run_admission_sql4_once.py"
RAW_LIMIT, TRAILER_RESERVE = 262144, 512
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
driver = "tools/run_admission_sql4_once.py"
namespace = {"__name__": "admission_sql4_retained_inner", "__file__": str(root / driver),
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
        # The retained child has three fixed control writes, sharing 1MiB.
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
    """Four original direct SQL tests, fixed retained paths and RO post-checks."""
    import _thread
    import importlib.abc
    import importlib.util
    import linecache
    import resource
    import sqlite3
    import threading
    from types import ModuleType, SimpleNamespace
    import unittest

    parser = argparse.ArgumentParser(description=inner.__doc__)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--private-directory", required=True, type=Path)
    parser.add_argument("--parent-captured-stdio", action="store_true")
    args = parser.parse_args(argv)
    capsule = globals().get("_PARENT_CAPTURE_CAPSULE")
    if not args.parent_captured_stdio or type(capsule) is not dict:
        raise ValueError("retained parent-captured mode required")
    plan_raw, frozen = capsule["plan_raw"], capsule["inputs"]
    plan = json.loads(plan_raw)
    methods = (
        "test_ordinary_capture_and_known_id_retry_preserve_original_decision",
        "test_mm_equality_rejection_has_no_fabricated_accepted_evidence",
        "test_configured_projection_and_reduce_only_have_explicit_coverage",
        "test_synthetic_coexisting_policy_candidates_reject_read_arguments",
    )
    labels = ("ordinary", "mm-equality", "configured", "coexist")
    if sha256(plan_raw).hexdigest() != args.plan_sha256 or plan["methods"] != list(methods) or set(frozen) != set(plan["input_files"]):
        raise ValueError("approved four-method/input scope differs")
    for name, pin in plan["input_files"].items():
        value = frozen[name]
        if {"bytes": len(value), "sha256": sha256(value).hexdigest()} != pin:
            raise ValueError("retained pin differs")
        if name.endswith(".py"):
            linecache.cache[str(ROOT / name)] = (len(value), None, value.decode().splitlines(True), str(ROOT / name))
    oracle = json.loads(frozen["evidence/reviews/admission-sql4/manual-oracle.json"])
    if oracle["fixture_order"] != list(labels) or oracle["methods"] != list(methods):
        raise ValueError("fixed manual oracle differs")
    output = args.private_directory
    if not output.is_absolute() or output.resolve() != output or output.name != "inner" or output.parent.parent != Path("/workspace"):
        raise ValueError("fresh canonical inner namespace required")
    output.mkdir(mode=0o700)
    dbroot = output / "cases"
    dbroot.mkdir(mode=0o700)
    os.umask(0o077)
    resource.setrlimit(resource.RLIMIT_FSIZE, (FILE_LIMIT, FILE_LIMIT))
    expected_db = {label: dbroot / label / "admission.sqlite3" for label in labels}
    parents = {p.parent for p in expected_db.values()}
    families = {str(p) + suffix for p in expected_db.values() for suffix in ("", "-wal", "-shm", "-journal")}
    uris = {p.as_uri() + "?mode=" + mode for p in expected_db.values() for mode in ("rw", "ro")}
    executable = Path(sys.executable).resolve()
    binary = read_regular(executable, 64 * 1024 * 1024)
    runtime = {"sys_executable": sys.executable, "resolved_executable": str(executable),
        "executable_bytes": len(binary), "executable_sha256": sha256(binary).hexdigest(),
        "sys_version": sys.version, "affinity": sorted(os.sched_getaffinity(0)),
        "flags": {"isolated": sys.flags.isolated, "no_site": sys.flags.no_site, "dont_write_bytecode": sys.flags.dont_write_bytecode}}
    if runtime != plan["expected_runtime"] or any(n == "uta" or n.startswith("uta.") for n in sys.modules):
        raise ValueError("runtime differs or UTA preloaded outside retained source")
    new_file(output / "intent.json", encoded({"source_commit": args.source_commit,
        "plan_sha256": args.plan_sha256, "runtime": runtime, "input_files": plan["input_files"],
        "fixed_methods": list(methods), "exact_DB_files": sorted(families),
        "RLIMIT_FSIZE_each_file": list(resource.getrlimit(resource.RLIMIT_FSIZE)), "caller_actual_exit_required": True}))
    forbidden, handles, connections = [], [], []
    observed, peak_bytes, peak_files, disk_problem = 0, 0, 0, None

    def denied(event):
        if len(forbidden) < 16:
            forbidden.append(event)
        raise RuntimeError("SQL4 scope forbids " + event)

    def publication_temp(path):
        return path.parent in parents and path.name.startswith(".uta-create-")

    def disk_snapshot():
        nonlocal observed, peak_bytes, peak_files, disk_problem
        facts, size = [], 0
        for path in sorted(dbroot.rglob("*")):
            info = path.lstat()
            if stat.S_ISDIR(info.st_mode):
                if path not in parents:
                    raise ValueError("unexpected authority directory")
                continue
            if (path.resolve() != path or not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                    or stat.S_IMODE(info.st_mode) & 0o077 or info.st_size > FILE_LIMIT
                    or (str(path) not in families and not publication_temp(path))
                    or publication_temp(path) and info.st_size != 0):
                disk_problem = "unexpected/nonprivate/oversize resource"
                raise ValueError(disk_problem)
            size += info.st_size
            facts.append({"path": str(path.relative_to(dbroot)), "bytes": info.st_size, "mode": stat.S_IMODE(info.st_mode)})
        observed += 1
        peak_bytes, peak_files = max(peak_bytes, size), max(peak_files, len(facts))
        if size > 64 * 1024 * 1024 or len(facts) > 20:
            disk_problem = "logical DB bound exceeded"
            raise ValueError(disk_problem)
        return facts

    def audit(event, arguments):
        if event in {"subprocess.Popen", "os.fork", "os.forkpty", "os.exec", "os.posix_spawn",
                     "os.system", "os.kill", "os.killpg", "os.rmdir", "os.truncate",
                     "socket.__new__", "socket.connect", "socket.bind", "socket.getaddrinfo"}:
            denied(event)
        if event == "sqlite3.connect":
            if not arguments or arguments[0] not in uris:
                denied("sqlite3.connect:outside_exact_four")
            disk_snapshot()
            connections.append(arguments[0])
            if len(connections) > 512:
                denied("sqlite3.connect:count_limit")
        if event == "sqlite3.connect/handle":
            if not arguments or type(arguments[0]) is not sqlite3.Connection:
                denied("sqlite3.connect/handle:not_native")
            handles.append(arguments[0])  # Do not inspect an incompletely initialized handle.
        if event == "open" and arguments and isinstance(arguments[0], (str, bytes)):
            path = Path(os.fsdecode(arguments[0])); flags = arguments[2] if len(arguments) > 2 else 0
            if str(path).startswith("/proc/"):
                denied("open:proc")
            if str(path).endswith((".sqlite", ".sqlite3", ".db", "-wal", "-shm", "-journal")) and str(path) not in families:
                denied("open:foreign_authority")
            if type(flags) is int and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC):
                if path not in {output / n for n in ("intent.json", "execution.json", "oracle-details.json")} and not publication_temp(path):
                    denied("open:unapproved_write")
        if event in {"os.remove", "os.unlink"} and (not arguments or not publication_temp(Path(os.fsdecode(arguments[0])))):
            denied("unlink:outside_empty_publication_temp")
        if event == "os.link" and (len(arguments) < 2 or not publication_temp(Path(os.fsdecode(arguments[0])))
                or Path(os.fsdecode(arguments[1])) not in expected_db.values()
                or Path(os.fsdecode(arguments[0])).parent != Path(os.fsdecode(arguments[1])).parent):
            denied("link:outside_exact_four")
        if event in {"os.rename", "os.symlink"}:
            denied(event)
        if event == "os.mkdir" and (not arguments or Path(os.fsdecode(arguments[0])) not in parents):
            denied("mkdir:outside_exact_four")

    def no_thread(*args, **kwargs):
        denied("thread_start")
    sys.addaudithook(audit)
    threading.Thread.start = no_thread
    _thread.start_new_thread = no_thread
    if hasattr(threading, "_start_new_thread"):
        threading._start_new_thread = no_thread

    class FrozenLoader(importlib.abc.Loader):
        def __init__(self, relative): self.relative = relative
        def create_module(self, spec): return None
        def exec_module(self, module):
            exec(compile(frozen[self.relative], str(ROOT / self.relative), "exec"), module.__dict__)
    class FrozenUTA(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname != "uta" and not fullname.startswith("uta."): return None
            relative = "uta/__init__.py" if fullname == "uta" else fullname.replace(".", "/") + ".py"
            if relative not in frozen: raise ImportError("unretained UTA module")
            return importlib.util.spec_from_file_location(fullname, ROOT / relative,
                loader=FrozenLoader(relative), submodule_search_locations=[] if fullname == "uta" else None)
    def closed_handles():
        opened = 0
        for handle in handles:
            try: handle.in_transaction
            except sqlite3.ProgrammingError as error:
                if str(error) != "Cannot operate on a closed database.": raise
            else: opened += 1
        return {"observed_handles": len(handles), "open_handles_before_cleanup": opened,
                "all_observed_handles_already_closed": opened == 0}
    created, retained, owned = [], [], {}
    class RetainedDirectory:
        def __init__(self):
            if len(created) >= 4: raise ValueError("extra test fixture directory")
            label = labels[len(created)]
            expected_db[label].parent.mkdir(mode=0o700)
            self.name, self.label = str(expected_db[label].parent), label
            created.append(label)
        def cleanup(self):
            if self.label in retained: raise ValueError("duplicate directory cleanup")
            retained.append(self.label)  # Declared evidence retention; no financial or SQL patch.
    sys.meta_path.insert(0, FrozenUTA())
    fixture = ModuleType("admission_sql4_fixture")
    fixture.__file__ = str(ROOT / "tests/test_decision_admission_capture.py")
    sys.modules[fixture.__name__] = fixture
    print(json.dumps({"event": "ADMISSION_SQL4_BEGIN", "source_commit": args.source_commit,
        "runtime": runtime, "selected_methods": list(methods), "input_count": len(frozen)}), flush=True)
    started = time.monotonic_ns()
    exec(compile(frozen["tests/test_decision_admission_capture.py"], fixture.__file__, "exec"), fixture.__dict__)
    fixture.tempfile = SimpleNamespace(TemporaryDirectory=RetainedDirectory)
    original_fixture = fixture.DecisionAdmissionCaptureTests.fixture
    def once_fixture(test, **kwargs):
        index = len(owned)
        if index >= 4 or test._testMethodName != methods[index]: raise ValueError("extra/reordered SQL fixture")
        data = original_fixture(test, **kwargs)
        owned[labels[index]] = {"service": data[0], "database": data[1], "times": data[2]}
        disk_snapshot()
        return data
    fixture.DecisionAdmissionCaptureTests.fixture = once_fixture
    result = unittest.TextTestRunner(stream=sys.stderr, verbosity=2, failfast=True).run(
        unittest.TestSuite(fixture.DecisionAdmissionCaptureTests(name) for name in methods))
    tests_elapsed = time.monotonic_ns() - started
    closure_before = closed_handles()
    details, oracle_passed, oracle_error = {}, False, None
    try:
        if not (result.testsRun == 4 and result.wasSuccessful() and not result.skipped
                and not result.expectedFailures and not result.unexpectedSuccesses):
            raise ValueError("first method failure stops; no post-SQL oracle")
        if created != list(labels) or retained != list(labels) or list(owned) != list(labels) or not closure_before["all_observed_handles_already_closed"]:
            raise ValueError("missing fixtures/cleanups or open pre-reopen handle")
        helper = ModuleType("admission_sql4_oracle")
        helper.__file__ = str(ROOT / "tools/admission_sql4_oracle.py")
        sys.modules[helper.__name__] = helper
        exec(compile(frozen["tools/admission_sql4_oracle.py"], helper.__file__, "exec"), helper.__dict__)
        details = helper.verify_cases(owned, expected_db, oracle, read_regular, closed_handles, disk_snapshot)
        oracle_passed = details["oracle_passed"] is True
    except BaseException as failure:
        oracle_error = type(failure).__name__ + ": " + str(failure)
    closure_after = closed_handles()
    cleaned = 0
    if not closure_after["all_observed_handles_already_closed"]:
        for handle in handles:
            try: handle.in_transaction
            except sqlite3.ProgrammingError: continue
            handle.close(); cleaned += 1
    facts = disk_snapshot()
    if any(publication_temp(dbroot / f["path"]) for f in facts):
        oracle_passed, oracle_error = False, "publication temp remained"
    accounting = len(connections) == len(handles) > 0 and len({u.rsplit("?mode=", 1)[0] for u in connections}) == 4
    resources = {"before_reopen": closure_before, "after_reopen_before_cleanup": closure_after,
        "own_leaked_handles_closed_after_failure": cleaned, "connect_count": len(connections),
        "all_observed_handles_closed_after_cleanup": closed_handles()["all_observed_handles_already_closed"],
        "connection_events_and_handles_and_four_paths_match": accounting,
        "exact_distinct_DB_URIs": sorted(set(connections)), "disk_observations": observed,
        "peak_observed_logical_DB_bytes": peak_bytes, "peak_observed_DB_files": peak_files,
        "disk_problem": disk_problem, "aggregate_quota_claimed": False,
        "actual_RLIMIT_FSIZE": list(resource.getrlimit(resource.RLIMIT_FSIZE)),
        "final_DB_files": [{**f, "sha256": sha256(read_regular(dbroot / f["path"])).hexdigest()} for f in facts]}
    new_file(output / "oracle-details.json", encoded({"oracle": details, "resources": resources,
        "oracle_passed": oracle_passed, "oracle_error": oracle_error,
        "directory_cleanup_semantics": "original callbacks invoked, adapted to retain four test-owned directories"}))
    loaded = sorted(n for n in sys.modules if n == "uta" or n.startswith("uta."))
    required = {"uta", "uta.service", "uta.storage", "uta.decision_audit", "uta.writer_fence", "uta.existing_services"}
    loaded_ok = required <= set(loaded) and all(n == "uta" or n.replace(".", "/") + ".py" in frozen for n in loaded)
    unchanged = {n: read_regular(ROOT / n) for n in frozen} == frozen and read_regular(ROOT / PLAN) == plan_raw
    passed = (result.testsRun == 4 and result.wasSuccessful() and not result.skipped and not result.expectedFailures
        and not result.unexpectedSuccesses and not forbidden and unchanged and loaded_ok
        and sorted(os.sched_getaffinity(0)) == [1] and oracle_passed and accounting
        and closure_before["all_observed_handles_already_closed"] and closure_after["all_observed_handles_already_closed"] and not disk_problem)
    receipt = {"source_commit_invoker_label": args.source_commit, "runtime": runtime,
        "selected_methods": list(methods), "tests_run": result.testsRun, "failures": len(result.failures),
        "errors": len(result.errors), "skipped": len(result.skipped), "expected_failures": len(result.expectedFailures),
        "unexpected_successes": len(result.unexpectedSuccesses), "tests_elapsed_ns": tests_elapsed,
        "elapsed_ns": time.monotonic_ns() - started, "input_pins_after": plan["input_files"],
        "source_before_after_equal": unchanged, "forbidden_attempts": forbidden,
        "loaded_UTA_modules": loaded, "loaded_UTA_modules_all_retained": loaded_ok,
        "actual_affinity_after": sorted(os.sched_getaffinity(0)), "returncode": 0 if passed else 1,
        "SQL_test_methods_selected": True, "workers_or_server_or_network_authorized": False,
        "oracle_passed": oracle_passed, "oracle_error": oracle_error, "oracle_case_count": len(details.get("cases", {})),
        "expected_fresh_DBs": 4, "expected_local_apply_fill_calls": 1, "Matcher_calls": 0,
        "paired_fill_throughput_claim": False,
        "all_owned_handles_closed_before_cleanup": closure_after["all_observed_handles_already_closed"],
        "connection_events_and_handles_and_four_paths_match": accounting,
        "private_DB_and_capsule_export_authorized": False, "production_approved": False}
    new_file(output / "execution.json", encoded(receipt))
    print(json.dumps({"event": "ADMISSION_SQL4_END", **receipt}), flush=True)
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
    command = ["/usr/bin/timeout", "--signal=KILL", "30s", "/usr/bin/taskset", "-c", "1",
        plan["expected_runtime"]["resolved_executable"], "-I", "-S", "-B", "-c", BOOTSTRAP,
        str(capsule), sha256(capsule_raw).hexdigest(), args.plan_sha256, args.source_commit, str(output / "inner")]
    new_file(output / "intent.json", encoded({"source_commit": args.source_commit,
        "plan_sha256": args.plan_sha256, "capsule_sha256": sha256(capsule_raw).hexdigest(),
        "argv": command, "actual_outer_affinity": sorted(os.sched_getaffinity(0)),
        "raw_limit": RAW_LIMIT, "trailer_reserve": TRAILER_RESERVE, "attempt": 1,
        "SQL_exact_four_fresh_authorities_only": True, "worker_authorized": False}))
    out_fd = new_file(output / "first.stdout.txt")
    err_fd = new_file(output / "first.stderr.txt")
    capture, process, host_exit, reaped, eof = SharedRaw(), None, None, False, False
    started = time.monotonic_ns()
    deadline = time.monotonic() + 35
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
        if len(records) == 2 and records[0]["event"] == "ADMISSION_SQL4_BEGIN" and records[1]["event"] == "ADMISSION_SQL4_END":
            inner = json.loads(read_regular(output / "inner/execution.json"))
            valid_end = (records[1] == {"event": "ADMISSION_SQL4_END", **inner}
                and inner["source_commit_invoker_label"] == args.source_commit
                and inner["input_pins_after"] == plan["input_files"]
                and type(inner["tests_run"]) is int and inner["tests_run"] == 4
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
              and inner["loaded_UTA_modules_all_retained"] is True
              and inner["SQL_test_methods_selected"] is True and inner["forbidden_attempts"] == []
              and inner["oracle_passed"] is True and inner["oracle_case_count"] == 4
              and inner["all_owned_handles_closed_before_cleanup"] is True
              and inner["connection_events_and_handles_and_four_paths_match"] is True)
    classification = "PASS_LIMITED_SQL_ONLY" if passed else "FAIL" if complete and host_exit == 1 else "UNKNOWN"
    status = 0 if passed else 1 if classification == "FAIL" else 125 if capture.failed else 126
    capture.trailer(err_fd, {"event": "ADMISSION_SQL4_HOST_END", "host_exit": host_exit,
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
    new_file(output / "END.json", encoded({"event": "ADMISSION_SQL4_ENVELOPE_END", "classification": classification,
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
