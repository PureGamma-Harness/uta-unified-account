"""One explicitly authorized memory-only fixture execution; no implicit GO."""
import os
from pathlib import Path
import sys
from time import monotonic

STARTED = monotonic()
DEADLINE = STARTED + 10
ROOT = Path(__file__).resolve().parents[3]
RAW_CAP = 262144
RAW_TRAILER_RESERVE = 512
RAW_RESERVED = 0
RAW_FAILED = False


def raw_abort(reason):
    global RAW_FAILED
    RAW_FAILED = True
    trailer = ('{"event":"PURE_RAW_CAPTURE_ABORT","reason":"' + reason
               + '","exit_status":125}\n').encode("ascii")
    # All normal bytes were reserved below CAP-512 before their first write.
    # One direct trailer attempt remains inside that independently held space.
    try:
        os.write(2, trailer)
    except BaseException:
        pass
    os._exit(125)


class BoundedRaw:
    encoding = "utf-8"
    errors = "backslashreplace"

    def __init__(self, descriptor):
        self.descriptor = descriptor

    def write(self, value):
        global RAW_RESERVED
        if RAW_FAILED:
            os._exit(125)
        if type(value) is not str:
            raise TypeError("bounded raw writer requires plain text")
        data = value.encode(self.encoding, self.errors)
        if len(data) > RAW_CAP - RAW_TRAILER_RESERVE - RAW_RESERVED:
            raw_abort("combined_capacity")
        RAW_RESERVED += len(data)  # Reserve the whole request before any FD write.
        remaining = memoryview(data)
        try:
            while remaining:
                written = os.write(self.descriptor, remaining)
                if type(written) is not int or written <= 0 or written > len(remaining):
                    raw_abort("short_or_invalid_write")
                remaining = remaining[written:]
        except BaseException:
            raw_abort("fd_write_failure")
        return len(value)

    def flush(self):
        # os.write is already unbuffered; do not claim filesystem fsync here.
        if RAW_FAILED:
            os._exit(125)

    def isatty(self):
        return False

    def fileno(self):
        return self.descriptor


# The frozen fixture writes via Python's streams and has no native FD emitter.
# Install before imports/main/fixture execution; interpreter pre-exec failures
# are a separate preparation scope. Keep Python's fallback streams bounded too.
sys.stdout = sys.__stdout__ = BoundedRaw(1)
sys.stderr = sys.__stderr__ = BoundedRaw(2)


def budget(frame, event, argument):
    filename = frame.f_code.co_filename
    if filename.startswith((str(ROOT), "selected-")):
        if monotonic() >= DEADLINE:
            print('{"event":"PURE_BUDGET_EXHAUSTED","wall_seconds":10}', flush=True)
            os._exit(124)
        return budget
    return None


sys.settrace(budget)
import hashlib
import json
import runpy
import stat
import unittest


def emit(event, **values):
    print(json.dumps({"event": event, **values}, sort_keys=True), flush=True)


def regular_bytes(relative, expected_size=None):
    path = ROOT / relative
    details = path.stat(follow_symlinks=False)
    if (not stat.S_ISREG(details.st_mode) or path.resolve() != path
            or expected_size is not None and details.st_size != expected_size):
        raise ValueError("input is not the declared materialized regular Git-sized file")
    return path.read_bytes()


def audit(event, arguments):
    if event in {"sqlite3.connect", "subprocess.Popen", "os.fork", "os.posix_spawn", "os.kill",
                 "os.pidfd_open", "signal.pidfd_send_signal", "socket.__new__", "socket.connect",
                 "os.mkdir", "os.link", "os.remove", "os.rename", "os.rmdir", "os.truncate"}:
        raise AssertionError("forbidden native effect in selected-AST memory fixture: " + event)
    if event == "open":
        path, mode, flags = arguments
        if ((mode and any(character in mode for character in "wax+"))
                or flags & (os.O_WRONLY | os.O_RDWR)):
            raise AssertionError("forbidden filesystem writer in selected-AST memory fixture")


def main():
    if len(sys.argv) != 2 or len(sys.argv[1]) != 40 or any(c not in "0123456789abcdef" for c in sys.argv[1]):
        raise ValueError("supply the frozen target-source commit")
    plan_data = regular_bytes("evidence/reviews/matching-selection-snapshot/source-plan.json")
    plan = json.loads(plan_data)
    if plan["source_commit"] != sys.argv[1]:
        raise ValueError("source label differs from frozen plan")
    expected = {"uta/matching.py", "uta/service.py", "tests/test_matching_selection_snapshot.py",
                "evidence/reviews/matching-selection-snapshot/run_once.py"}
    if set(plan["inputs"]) != expected:
        raise ValueError("declared four-file source inventory changed")
    before = {}
    for name, pin in plan["inputs"].items():
        before[name] = hashlib.sha256(regular_bytes(name, pin["bytes"])).hexdigest()
        if before[name] != pin["sha256"]:
            raise ValueError("frozen input digest changed: " + name)
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    emit("BEGIN_FIRST_PURE_ONCE", attempt=1, source_commit=sys.argv[1], runtime=sys.version,
         actual_affinity=sorted(os.sched_getaffinity(0)), inputs_sha256=before,
         plan_sha256=hashlib.sha256(plan_data).hexdigest(), methods=12,
         native_execution_authorized=False, sql_authorized=False, wall_seconds=10,
         combined_raw_cap_bytes=RAW_CAP, trailer_reserve_bytes=RAW_TRAILER_RESERVE)
    sys.addaudithook(audit)
    values = runpy.run_path(str(ROOT / "tests/test_matching_selection_snapshot.py"),
                            run_name="matching_selection_memory_fixture")
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(values["SnapshotSelectionTests"])
    if suite.countTestCases() != 12:
        raise AssertionError("frozen twelve-method selector changed")
    result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
    forbidden = sorted(name for name in sys.modules if name.split(".", 1)[0] in
                       {"uta", "sqlite3", "_sqlite3", "multiprocessing", "subprocess"})
    after = {name: hashlib.sha256(regular_bytes(name, plan["inputs"][name]["bytes"])).hexdigest()
             for name in before}
    status = 0 if result.wasSuccessful() and not forbidden and after == before else 1
    emit("END_FIRST_PURE_ONCE", attempt=1, tests_run=result.testsRun, failures=len(result.failures),
         errors=len(result.errors), skipped=len(result.skipped), forbidden_runtime_imports=forbidden,
         inputs_after_sha256=after, source_unchanged=after == before,
         elapsed_seconds=monotonic() - STARTED, exit_status=status,
         settlement_sql_concurrency_and_throughput_acceptance=False)
    return status


try:
    STATUS = main()
finally:
    sys.settrace(None)
raise SystemExit(STATUS)
