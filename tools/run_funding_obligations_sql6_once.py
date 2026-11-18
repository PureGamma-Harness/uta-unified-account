"""Fixed once-only parent FD capture for six local funding-obligation SQL methods.

Nine new synthetic DBs only; no existing authority or service. The sole target
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
PLAN = "evidence/reviews/funding-obligations-local/sql6-once-plan.json"
INNER = "tools/run_funding_obligations_sql6_once.py"
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
driver = "tools/run_funding_obligations_sql6_once.py"
namespace = {"__name__": "funding_retained_inner", "__file__": str(root / driver),
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
        # The retained child has four fixed control writes, sharing 1MiB.
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


def _inner_scoped(argv):
    """Run six fixed SQL methods once, then reopen exactly nine owned DBs."""
    import _thread
    import dataclasses
    import datetime
    import decimal
    import fractions
    import hashlib
    import importlib.abc
    import importlib.util
    import linecache
    import re
    import resource
    import sqlite3
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
        "test_schedule_apply_command_queries_and_reopen",
        "test_missing_data_and_no_backdated_cut",
        "test_real_capital_wait_and_unique_proof",
        "test_competing_executors_expiry_and_clock_regression",
        "test_trades_after_cut_and_unknown_response_query",
        "test_review_rollback_code_binding_and_old_capability_rejection",
    )
    labels = ("normal", "missing", "current-data", "capital", "competition",
              "changed-positions", "new-empty", "old-empty", "review")
    if plan["methods"] != list(methods) or set(frozen) != set(plan["input_files"]):
        raise ValueError("fixed six-method/input scope differs")
    for name, expected in plan["input_files"].items():
        value = frozen[name]
        if type(value) is not bytes or {"bytes": len(value), "sha256": sha256(value).hexdigest()} != expected:
            raise ValueError("retained source pin differs")
        if name.endswith(".py"):
            linecache.cache[str(ROOT / name)] = (
                len(value), None, value.decode("utf-8").splitlines(True), str(ROOT / name))
    oracle = json.loads(frozen["evidence/reviews/funding-obligations-local/sql6-manual-oracle.json"])
    if oracle["fixture_order"] != list(labels):
        raise ValueError("fixed nine-case oracle differs")
    output = args.private_directory
    if (not output.is_absolute() or output.resolve() != output
            or output.name != "inner" or output.parent.parent != Path("/workspace")):
        raise ValueError("new canonical inner namespace required")
    output.mkdir(mode=0o700)
    dbroot = output / "cases"
    dbroot.mkdir(mode=0o700)
    # Inherited environment never selects an old test authority or temp root.
    os.environ["UTA_FUNDING_OBLIGATION_CASE_ROOT"] = str(dbroot)
    os.umask(0o077)
    # Per-file native write ceiling; this is explicitly NOT an aggregate quota.
    resource.setrlimit(resource.RLIMIT_FSIZE, (FILE_LIMIT, FILE_LIMIT))
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
    expected_db = {label: dbroot / label / "obligations.sqlite3" for label in labels}
    families = {str(path) + suffix for path in expected_db.values()
                for suffix in ("", "-wal", "-shm", "-journal")}
    uris = {path.as_uri() + "?mode=" + mode
            for path in expected_db.values() for mode in ("rw", "ro")}
    new_file(output / "intent.json", encoded({"source_commit": args.source_commit,
        "plan_sha256": args.plan_sha256, "runtime": runtime, "input_files": plan["input_files"],
        "fixed_methods": list(methods), "exact_DB_files": sorted(families),
        "RLIMIT_FSIZE_each_file": resource.getrlimit(resource.RLIMIT_FSIZE),
        "caller_actual_exit_required": True}))
    forbidden, handles, connections = [], [], []
    observations, peak_observed_bytes, peak_observed_files = 0, 0, 0
    disk_problem = None

    def denied(event):
        if len(forbidden) < 16:
            forbidden.append(event)
        raise RuntimeError("funding SQL scope forbids " + event)

    def temp_name(path):
        return (path.parent in {value.parent for value in expected_db.values()}
                and path.name.startswith(".uta-create-"))

    def disk_snapshot():
        nonlocal observations, peak_observed_bytes, peak_observed_files, disk_problem
        facts, total = [], 0
        for path in sorted(dbroot.rglob("*")):
            info = path.lstat()
            if stat.S_ISDIR(info.st_mode):
                if path not in {value.parent for value in expected_db.values()}:
                    disk_problem = "unexpected DB directory"
                    raise ValueError(disk_problem)
                continue
            if (path.resolve() != path or not stat.S_ISREG(info.st_mode)
                    or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077
                    or (str(path) not in families and not temp_name(path))
                    or info.st_size > FILE_LIMIT or temp_name(path) and info.st_size != 0):
                disk_problem = "unexpected/nonprivate/oversize DB resource"
                raise ValueError(disk_problem)
            total += info.st_size
            facts.append({"path": str(path.relative_to(dbroot)), "bytes": info.st_size,
                          "mode": stat.S_IMODE(info.st_mode)})
        observations += 1
        peak_observed_bytes = max(peak_observed_bytes, total)
        peak_observed_files = max(peak_observed_files, len(facts))
        if total > 64 * 1024 * 1024 or len(facts) > 45:
            disk_problem = "DB logical resource bound exceeded"
            raise ValueError(disk_problem)
        return facts

    def audit(event, arguments):
        if event in {"subprocess.Popen", "os.fork", "os.forkpty", "os.exec", "os.posix_spawn",
                     "os.system", "os.kill", "os.killpg", "os.rmdir", "os.truncate",
                     "socket.__new__", "socket.connect", "socket.bind", "socket.getaddrinfo"}:
            denied(event)
        if event == "sqlite3.connect":
            if not arguments or arguments[0] not in uris:
                denied("sqlite3.connect:outside_exact_nine")
            disk_snapshot()
            connections.append(arguments[0])
            if len(connections) > 2048:
                denied("sqlite3.connect:count_limit")
        if event == "sqlite3.connect/handle":
            if not arguments or type(arguments[0]) is not sqlite3.Connection:
                denied("sqlite3.connect/handle:not_native_connection")
            handles.append(arguments[0])
        if event == "open" and arguments and isinstance(arguments[0], (str, bytes)):
            path = Path(os.fsdecode(arguments[0]))
            flags = arguments[2] if len(arguments) > 2 else 0
            if str(path).startswith("/proc/"):
                denied("open:proc")
            if str(path).endswith((".sqlite", ".sqlite3", ".db", "-wal", "-shm", "-journal")) and str(path) not in families:
                denied("open:foreign_authority")
            if type(flags) is int and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC):
                controls = {output / name for name in ("intent.json", "execution.json", "oracle-details.json", "restoration.json")}
                if path not in controls and not temp_name(path):
                    denied("open:unapproved_write")
        if event in {"os.remove", "os.unlink"}:
            if not arguments or not temp_name(Path(os.fsdecode(arguments[0]))):
                denied("unlink:not_private_empty_publication_temp")
        if event == "os.link":
            if (len(arguments) < 2 or not temp_name(Path(os.fsdecode(arguments[0])))
                    or Path(os.fsdecode(arguments[1])) not in expected_db.values()
                    or Path(os.fsdecode(arguments[0])).parent != Path(os.fsdecode(arguments[1])).parent):
                denied("link:outside_exact_nine")
        if event in {"os.rename", "os.symlink"}:
            denied(event)
        if event == "os.mkdir":
            if not arguments or Path(os.fsdecode(arguments[0])) not in {value.parent for value in expected_db.values()}:
                denied("mkdir:outside_exact_nine")

    # Resource-only observers. No connect/factory/close/financial function is replaced.
    # Native close success is observed in its owning thread, never by probing a
    # worker connection from this main thread. First failure cannot become PASS.
    successful_close_ids, thread_starts = set(), []
    close_returns, native_thread_starts = 0, 0
    observer_error = False
    current_method, opening_native = None, False
    original_thread_start = threading.Thread.start
    original_native_start = threading._start_new_thread

    def close_profile(frame, event, function):
        nonlocal close_returns, observer_error
        try:
            if event == "c_return" and getattr(function, "__name__", None) == "close":
                owner = getattr(function, "__self__", None)
                if type(owner) is sqlite3.Connection:
                    close_returns += 1
                    if close_returns > 4096:
                        denied("native_close_return_limit")
                    if not any(owner is handle for handle in handles):
                        denied("native_close_return_without_observed_connect_handle")
                    successful_close_ids.add(id(owner))
        except BaseException:
            observer_error = True  # Sticky even if Python disables this profile.
            raise

    def no_thread(*arguments, **keywords):
        denied("direct_native_thread_start")

    def scoped_native(function, arguments, keywords=None):
        nonlocal native_thread_starts
        if not opening_native or native_thread_starts >= 2:
            denied("native_thread_outside_two_declared_executor_threads")
        native_thread_starts += 1  # Reserved before the only attempted start.
        if keywords is None:
            return original_native_start(function, arguments)
        return original_native_start(function, arguments, keywords)

    def scoped_thread_start(thread):
        nonlocal opening_native
        if (current_method != methods[3] or len(thread_starts) >= 2
                or getattr(getattr(thread, "_target", None), "__module__", None) != "concurrent.futures.thread"
                or getattr(getattr(thread, "_target", None), "__name__", None) != "_worker"):
            denied("thread_start_outside_declared_competition_executor")
        thread_starts.append(thread)
        opening_native = True
        try:
            return original_thread_start(thread)
        finally:
            opening_native = False

    sys.addaudithook(audit)
    sys.setprofile(close_profile)
    threading.setprofile(close_profile)
    threading.Thread.start = scoped_thread_start
    _thread.start_new_thread = no_thread
    threading._start_new_thread = scoped_native

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

    def closed_handles():
        missing = sum(id(handle) not in successful_close_ids for handle in handles)
        return {"observed_handles": len(handles), "open_handles_before_cleanup": missing,
                "all_observed_handles_already_closed": missing == 0,
                "native_successful_close_returns": close_returns,
                "observation": "owning_thread_native_close_c_return_not_cross_thread_SQL_probe"}

    sys.meta_path.insert(0, FrozenUTA())
    fixture = ModuleType("funding_obligations_sql6_fixture")
    fixture.__file__ = str(ROOT / "tests/test_funding_obligations_local.py")
    sys.modules[fixture.__name__] = fixture
    print(json.dumps({"event": "FUNDING_OBLIGATIONS_SQL6_BEGIN", "source_commit": args.source_commit,
        "runtime": runtime, "selected_methods": list(methods), "input_count": len(frozen)}), flush=True)
    started = time.monotonic_ns()
    exec(compile(frozen["tests/test_funding_obligations_local.py"], fixture.__file__, "exec"), fixture.__dict__)
    original_scenario, owned = fixture.scenario, {}

    def once_scenario(test, label, **keywords):
        if len(owned) >= len(labels) or label != labels[len(owned)] or label in owned:
            raise ValueError("scenario repeated, extra, or reordered")
        data = original_scenario(test, label, **keywords)
        owned[label] = data
        disk_snapshot()
        return data

    fixture.scenario = once_scenario  # Only retains original objects; no extra financial setup.

    class CountedResult(unittest.TextTestResult):
        def __init__(self, *arguments, **keywords):
            super().__init__(*arguments, **keywords)
            self.successful_ids, self.actual_ids = [], []
        def startTest(self, test):
            nonlocal current_method
            current_method = test._testMethodName
            self.actual_ids.append(test.id())
            super().startTest(test)
        def addSuccess(self, test):
            self.successful_ids.append(test.id())
            super().addSuccess(test)
        def stopTest(self, test):
            nonlocal current_method
            current_method = None
            super().stopTest(test)

    result = unittest.TextTestRunner(stream=sys.stderr, verbosity=2, failfast=True,
        resultclass=CountedResult).run(unittest.TestSuite(fixture.FundingObligationTests(name) for name in methods))
    tests_elapsed = time.monotonic_ns() - started
    closure_before = closed_handles()
    details, oracle_passed, oracle_error = {}, False, None
    try:
        if not (result.testsRun == 6 and result.wasSuccessful() and not result.skipped
                and not result.expectedFailures and not result.unexpectedSuccesses):
            raise ValueError("first method failure/unknown stops SQL; no post-SQL oracle")
        if list(owned) != list(labels) or not closure_before["all_observed_handles_already_closed"]:
            raise ValueError("missing cases or live SQL resource before reopen")
        if (len(thread_starts) != 2 or native_thread_starts != 2 or any(thread.is_alive() for thread in thread_starts)
                or sys.getprofile() is not close_profile or threading.getprofile() is not close_profile):
            raise ValueError("declared two competition threads/profile did not close exactly")
        oracle_module = ModuleType("funding_obligations_sql6_independent_oracle")
        oracle_path = "tools/funding_obligations_sql6_oracle.py"
        exec(compile(frozen[oracle_path], str(ROOT / oracle_path), "exec"), oracle_module.__dict__)
        from uta.storage import Database
        from uta.perpetual_funding import FundingError
        from decimal import Decimal
        from fractions import Fraction
        totals = {key: 0 for key in ("journals", "matches", "paired_fills", "tasks", "applied", "outstanding")}
        fee_total, custody_total = Fraction(), Fraction()
        for label in labels:
            data, expected = owned[label], oracle["cases"][label]
            database = Database(expected_db[label])
            with database.read_transaction() as connection:
                # Only a new ro URI/snapshot. No service or Matcher constructor,
                # schema creation, market repair, or fixture expected functions.
                before_schema = list(connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"))
                verified = oracle_module.check(connection, label, expected)
                if label == "review":
                    try:
                        data.funding.verify(connection=connection)
                    except FundingError as error:
                        if error.code != "funding_reconciliation":
                            raise
                        component = {"expected_deliberate_orphan_rejected": True, "code": error.code}
                    else:
                        raise ValueError("deliberate orphan was silently accepted")
                else:
                    component = data.funding.verify(connection=connection)
                    if label != "old-empty" and (component["obligations"], component["applied"], component["outstanding"]) != (verified["tasks"], verified["applied"], verified["outstanding"]):
                        raise ValueError("component/independent task counts disagree")
                after_schema = list(connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"))
                if before_schema != after_schema or connection.execute("PRAGMA query_only").fetchone()[0] != 1:
                    raise ValueError("read-only reopen schema/role changed")
                for key in totals:
                    totals[key] += verified[key]
                balances = {(r[0], r[1]): Fraction(int(r[2]), 100) for r in connection.execute("SELECT account,asset,units FROM ledger_balances")}
                fee_total += balances.get(("system:fees", "USD"), Fraction())
                custody_total += balances.get(("system:custody", "USD"), Fraction())
                details[label] = {"independent": verified, "component_verifier": component,
                    "fresh_ro_snapshot": True, "schema_unchanged_without_constructors_or_repair": True}
            disk_snapshot()
        if (totals != {key: oracle["aggregate"][key] for key in totals}
                or fee_total != Fraction(Decimal(oracle["aggregate"]["fees_USD"]))
                or custody_total != Fraction(Decimal(oracle["aggregate"]["custody_USD"]))):
            raise ValueError("independent manual aggregate differs")
        oracle_passed = True
    except BaseException as failure:
        oracle_error = type(failure).__name__ + ": " + str(failure)
    closure_after = closed_handles()
    # Do not access/close a connection from a different owning thread. All
    # unclosed observations are sticky UNKNOWN/FAIL; process termination is the
    # outer containment. An observed close after failure never repairs PASS.
    cleaned = 0
    facts = disk_snapshot()
    if any(temp_name(dbroot / fact["path"]) for fact in facts):
        oracle_passed, oracle_error = False, "private publication temp remained"
    connection_accounting_ok = (len(connections) == len(handles) and len(handles) > 0
        and len({uri.rsplit("?mode=", 1)[0] for uri in connections}) == 9)
    resources = {"before_reopen": closure_before, "after_reopen_before_cleanup": closure_after,
        "own_leaked_handles_closed_after_failure": cleaned, "connect_count": len(connections),
        "all_observed_handles_closed_after_cleanup": closed_handles()["all_observed_handles_already_closed"],
        "connection_events_and_handles_and_nine_paths_match": connection_accounting_ok,
        "exact_distinct_DB_URIs": sorted(set(connections)), "disk_observations": observations,
        "peak_observed_logical_DB_bytes": peak_observed_bytes,
        "peak_observed_DB_files": peak_observed_files, "disk_problem": disk_problem,
        "actual_final_DB_files": len(facts), "actual_final_DB_logical_bytes": sum(fact["bytes"] for fact in facts),
        "observation_is_not_continuous_native_write_monitoring": True,
        "aggregate_quota_claimed": False, "actual_RLIMIT_FSIZE": list(resource.getrlimit(resource.RLIMIT_FSIZE))}
    # Closing an ordinary FD for a live SQLite inode can drop this process's
    # fcntl locks. A comment/PASS=false is insufficient: do not even open DB
    # bytes unless closure, complete observation and quiescent threads are proven.
    byte_hashing_permitted = (closure_after["all_observed_handles_already_closed"]
        and not observer_error and not forbidden and connection_accounting_ok
        and sys.getprofile() is close_profile and threading.getprofile() is close_profile
        and not any(thread.is_alive() for thread in thread_starts))
    resources["DB_byte_hashing_permitted"] = byte_hashing_permitted
    resources["observer_error"] = observer_error
    if byte_hashing_permitted:
        resources["final_DB_files"] = [{**fact, "sha256": sha256(read_regular(dbroot / fact["path"])).hexdigest()}
                                         for fact in facts]
        resources["DB_byte_hash_status"] = "HASHED_AFTER_PROVEN_NATIVE_CLOSURE"
    else:
        # Stat facts and all original bytes remain untouched for later separately
        # authorized inspection. No cleanup, hashing, or late close repairs PASS.
        resources["final_DB_files"] = list(facts)
        resources["DB_byte_hash_status"] = "NOT_OPENED_CLOSURE_OR_OBSERVATION_UNKNOWN"
        oracle_passed = False
        oracle_error = oracle_error or "DB closure/observation not proven; byte hashing refused"
    resources["competition_threads"] = {"declared_starts": len(thread_starts), "native_starts": native_thread_starts,
        "alive_after_methods": sum(thread.is_alive() for thread in thread_starts),
        "profile_close_identity_is_audit_observed_native_handle": True,
        "strong_handle_references_prevent_identity_reuse": True,
        "callback_reads_frame_locals": False, "max_close_returns": 4096}
    new_file(output / "oracle-details.json", encoded({"cases": details, "resources": resources,
        "oracle_passed": oracle_passed, "oracle_error": oracle_error}))
    loaded = sorted(name for name in sys.modules if name == "uta" or name.startswith("uta."))
    required = {"uta", "uta.perpetual_funding", "uta.funding_local", "uta.funding_obligations", "uta.service", "uta.storage",
                "uta.credit_artifact", "uta.matching", "uta.writer_fence", "uta.existing_services"}
    loaded_ok = required <= set(loaded) and all(
        name == "uta" or name.replace(".", "/") + ".py" in frozen for name in loaded)
    after = {name: read_regular(ROOT / name) for name in frozen}
    unchanged = after == frozen and read_regular(ROOT / PLAN) == plan_raw
    actual_runtime_after = sorted(os.sched_getaffinity(0))
    passed = (result.testsRun == 6 and result.wasSuccessful() and not result.skipped
        and not result.expectedFailures and not result.unexpectedSuccesses
        and not forbidden and unchanged and actual_runtime_after == [1] and loaded_ok
        and result.successful_ids == ["funding_obligations_sql6_fixture.FundingObligationTests." + name for name in methods]
        and len(thread_starts) == native_thread_starts == 2 and not any(t.is_alive() for t in thread_starts)
        and oracle_passed and closure_before["all_observed_handles_already_closed"]
        and closure_after["all_observed_handles_already_closed"] and not disk_problem
        and connection_accounting_ok and byte_hashing_permitted and not observer_error)
    receipt = {"source_commit_invoker_label": args.source_commit, "runtime": runtime,
        "selected_methods": list(methods), "tests_run": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors),
        "skipped": len(result.skipped), "expected_failures": len(result.expectedFailures),
        "unexpected_successes": len(result.unexpectedSuccesses), "tests_elapsed_ns": tests_elapsed,
        "elapsed_ns": time.monotonic_ns() - started, "input_pins_after": plan["input_files"],
        "source_before_after_equal": unchanged, "forbidden_attempts": forbidden,
        "loaded_UTA_modules": loaded, "loaded_UTA_modules_all_retained": loaded_ok,
        "actual_affinity_after": actual_runtime_after, "returncode": 0 if passed else 1,
        "SQL_test_methods_selected": True, "actual_test_ids": result.actual_ids,
        "successful_test_ids": result.successful_ids, "declared_thread_starts": len(thread_starts),
        "native_thread_starts": native_thread_starts, "threads_alive_after_methods": sum(t.is_alive() for t in thread_starts), "workers_or_server_or_network_authorized": False,
        "oracle_passed": oracle_passed, "oracle_error": oracle_error,
        "oracle_case_count": len(details), "expected_fresh_DBs": 9,
        "expected_matches": 9, "expected_paired_fills": 18,
        "all_owned_handles_closed_before_cleanup": closure_after["all_observed_handles_already_closed"],
        "connection_events_and_handles_and_nine_paths_match": connection_accounting_ok,
        "DB_byte_hashing_permitted": byte_hashing_permitted, "observer_error": observer_error,
        "private_DB_and_capsule_export_authorized": False, "production_approved": False}
    new_file(output / "execution.json", encoded(receipt))
    print(json.dumps({"event": "FUNDING_OBLIGATIONS_SQL6_END", **receipt}), flush=True)
    return 0 if passed else 1


def inner(argv):
    """Restore the resource observers even when the first test/oracle fails."""
    import _thread
    import threading
    saved = (sys.getprofile(), threading.getprofile(), threading.Thread.start,
             threading._start_new_thread, _thread.start_new_thread)
    if saved[0] is not None or saved[1] is not None:
        raise ValueError("profile already installed before bounded entry")
    try:
        return _inner_scoped(argv)
    finally:
        # This only restores new-scope observers. It never closes a foreign
        # thread's SQLite handle, suppresses failure, joins an unbounded thread,
        # retries a method, or repairs a target result.
        sys.setprofile(saved[0])
        threading.setprofile(saved[1])
        threading.Thread.start = saved[2]
        threading._start_new_thread = saved[3]
        _thread.start_new_thread = saved[4]
        restored = (sys.getprofile() is saved[0] and threading.getprofile() is saved[1]
            and threading.Thread.start is saved[2] and threading._start_new_thread is saved[3]
            and _thread.start_new_thread is saved[4])
        output = Path(argv[argv.index("--private-directory") + 1])
        if output.is_dir():
            new_file(output / "restoration.json", encoded({"resource_observers_restored": restored,
                "original_profiles_were_none": True, "financial_functions_replaced": False}))
        if not restored:
            raise ValueError("resource observer restoration failed")


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
    command = ["/usr/bin/timeout", "--signal=KILL", "45s", "/usr/bin/taskset", "-c", "1",
        plan["expected_runtime"]["resolved_executable"], "-I", "-S", "-B", "-c", BOOTSTRAP,
        str(capsule), sha256(capsule_raw).hexdigest(), args.plan_sha256, args.source_commit, str(output / "inner")]
    new_file(output / "intent.json", encoded({"source_commit": args.source_commit,
        "plan_sha256": args.plan_sha256, "capsule_sha256": sha256(capsule_raw).hexdigest(),
        "argv": command, "actual_outer_affinity": sorted(os.sched_getaffinity(0)),
        "raw_limit": RAW_LIMIT, "trailer_reserve": TRAILER_RESERVE, "attempt": 1,
        "SQL_exact_nine_fresh_authorities_only": True, "worker_authorized": False}))
    out_fd = new_file(output / "first.stdout.txt")
    err_fd = new_file(output / "first.stderr.txt")
    capture, process, host_exit, reaped, eof = SharedRaw(), None, None, False, False
    started = time.monotonic_ns()
    deadline = time.monotonic() + 50
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
        if len(records) == 2 and records[0]["event"] == "FUNDING_OBLIGATIONS_SQL6_BEGIN" and records[1]["event"] == "FUNDING_OBLIGATIONS_SQL6_END":
            inner = json.loads(read_regular(output / "inner/execution.json"))
            valid_end = (records[1] == {"event": "FUNDING_OBLIGATIONS_SQL6_END", **inner}
                and inner["source_commit_invoker_label"] == args.source_commit
                and inner["input_pins_after"] == plan["input_files"]
                and type(inner["tests_run"]) is int and inner["tests_run"] == 6
                and inner["source_before_after_equal"] is True
                and inner["selected_methods"] == plan["methods"]
                and inner["runtime"] == plan["expected_runtime"]
                and all(type(inner[field]) is int for field in
                    ("returncode", "failures", "errors", "skipped", "expected_failures", "unexpected_successes")))
    except BaseException:
        pass
    restoration_ok = False
    try:
        restoration = json.loads(read_regular(output / "inner/restoration.json"))
        restoration_ok = restoration == {"resource_observers_restored": True,
            "original_profiles_were_none": True, "financial_functions_replaced": False}
    except BaseException:
        pass
    complete = restoration_ok and valid_end and reaped and eof and error is None and drift is None and not capture.failed
    passed = (complete and host_exit == 0 and inner["returncode"] == 0 and inner["failures"] == 0
              and inner["errors"] == 0 and inner["skipped"] == 0
              and inner["expected_failures"] == 0 and inner["unexpected_successes"] == 0
              and inner["loaded_UTA_modules_all_retained"] is True
              and inner["successful_test_ids"] == ["funding_obligations_sql6_fixture.FundingObligationTests." + name for name in plan["methods"]]
              and inner["declared_thread_starts"] == inner["native_thread_starts"] == 2
              and inner["threads_alive_after_methods"] == 0
              and inner["SQL_test_methods_selected"] is True and inner["forbidden_attempts"] == []
              and inner["oracle_passed"] is True and inner["oracle_case_count"] == 9
              and inner["all_owned_handles_closed_before_cleanup"] is True
              and inner["connection_events_and_handles_and_nine_paths_match"] is True
              and inner["DB_byte_hashing_permitted"] is True and inner["observer_error"] is False)
    classification = "PASS_LIMITED_SQL_ONLY" if passed else "FAIL" if complete and host_exit == 1 else "UNKNOWN"
    status = 0 if passed else 1 if classification == "FAIL" else 125 if capture.failed else 126
    capture.trailer(err_fd, {"event": "FUNDING_OBLIGATIONS_SQL6_HOST_END", "host_exit": host_exit,
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
        "inner": inner, "complete_inner_END": valid_end, "resource_observers_restored": restoration_ok, "error": error, "source_or_deadline_drift": drift,
        "raw_reserved": capture.reserved, "raw_written": capture.written, "raw_sticky": capture.failed,
        "raw_files": raw_facts, "classification": classification, "outer_return_status": status,
        "production_approved": False}))
    new_file(output / "END.json", encoded({"event": "FUNDING_OBLIGATIONS_SQL6_ENVELOPE_END", "classification": classification,
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
