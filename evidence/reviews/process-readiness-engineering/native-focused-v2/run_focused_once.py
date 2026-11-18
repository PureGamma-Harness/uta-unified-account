"""Frozen selected-AST fake batch. Preparing this file is not execution GO."""
import os
import sys
from time import monotonic

STARTED = monotonic()
DEADLINE = STARTED + 10
RAW_LIMIT = 256 * 1024
RAW_TRAILER_RESERVE = 512
RAW_STATE = {"reserved": 0, "failed": False}


def raw_failure():
    RAW_STATE["failed"] = True
    marker = b'\n{"event":"FOCUSED_RAW_CAPTURE_UNKNOWN","complete":false,"exit_status":125}\n'
    try:
        os.write(2, marker)  # Only the already-open private raw stderr stream.
    finally:
        os._exit(125)


class RawStream:
    encoding, errors = "utf-8", "backslashreplace"

    def __init__(self, fd):
        self.fd = fd

    def write(self, text):
        data = text.encode(self.encoding, self.errors)
        if RAW_STATE["failed"] or RAW_STATE["reserved"] + len(data) > RAW_LIMIT - RAW_TRAILER_RESERVE:
            raw_failure()
        RAW_STATE["reserved"] += len(data)
        try:
            remaining = data
            while remaining:
                written = os.write(self.fd, remaining)
                if written <= 0:
                    raise OSError("raw capture short write")
                remaining = remaining[written:]
        except BaseException:
            raw_failure()
        return len(text)

    def flush(self):
        return None  # Writes go directly to the existing descriptor, without a buffer.

    def fileno(self):
        return self.fd

    def isatty(self):
        return False


sys.stdout, sys.stderr = RawStream(1), RawStream(2)


def budget(frame, event, arg):
    if monotonic() >= DEADLINE:
        print('{"event":"FOCUSED_FAKE_BUDGET_EXHAUSTED","wall_seconds":10}', flush=True)
        os._exit(124)
    return budget


sys.settrace(budget)
import ast
import hashlib
import json
from pathlib import Path
import stat
import unittest

HERE = Path(__file__).resolve().parent
TARGET_NAMES = {"native_once_common.py", "native_once.py", "native_case_once.py", "native_safe_export.py"}
FIXTURE_NAMES = {"fake_support.py", "guard_fakes.py", "terminal_fakes.py", "run_focused_once.py"}


def audit(event, args):
    if event in {"sqlite3.connect", "subprocess.Popen", "os.fork", "os.posix_spawn", "os.kill",
                 "os.pidfd_open", "signal.pidfd_send_signal", "socket.__new__", "socket.connect",
                 "os.mkdir", "os.link", "os.remove", "os.rename", "os.rmdir", "os.truncate"}:
        raise AssertionError("focused fake attempted a forbidden native effect: " + event)
    if event == "open":
        _, mode, flags = args
        if (mode and any(character in mode for character in "wax+")) or flags & (os.O_WRONLY | os.O_RDWR):
            raise AssertionError("focused fake attempted a filesystem writer")


def emit(event, **values):
    print(json.dumps({"event": event, **values}, sort_keys=True), flush=True)


def regular_bytes(path, expected_bytes=None):
    try:
        details = path.stat(follow_symlinks=False)
        if (not stat.S_ISREG(details.st_mode) or path.resolve() != path
                or expected_bytes is not None and (type(expected_bytes) is not int
                                                   or details.st_size != expected_bytes)):
            raise ValueError("declared input is not the regular materialized Git-sized file")
        return path.read_bytes()
    except (OSError, ValueError):
        emit("SOURCE_INPUT_PREPARATION_BLOCKED", name=path.name,
             fixture_started=False, native_case_started=False)
        raise


def main():
    if len(sys.argv) != 2 or len(sys.argv[1]) != 40 or any(character not in "0123456789abcdef" for character in sys.argv[1]):
        raise ValueError("supply the frozen target-source commit")
    plan_path = HERE / "source-plan.json"
    plan_data = regular_bytes(plan_path)
    plan = json.loads(plan_data)
    if plan["target_source_commit"] != sys.argv[1]:
        raise AssertionError("reviewed target source label changed")
    if set(plan["targets_sha256"]) != TARGET_NAMES or set(plan["fixtures_sha256"]) != FIXTURE_NAMES:
        raise AssertionError("declared selected-AST input inventory changed")
    if set(plan["targets_bytes"]) != TARGET_NAMES or set(plan["fixtures_bytes"]) != FIXTURE_NAMES:
        raise AssertionError("declared materialized input byte lengths changed")
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    emit("BEGIN_FOCUSED_SYNTHETIC_ONLY", attempt=1, target_source_commit=sys.argv[1],
         plan_sha256=hashlib.sha256(plan_data).hexdigest(), runtime=sys.version,
         actual_affinity=sorted(os.sched_getaffinity(0)), wall_budget_seconds=10,
         raw_stdout_stderr_hard_limit_bytes=RAW_LIMIT,
         methods=20, target_module_imports_authorized=False, native_execution_authorized=False)
    parsed, observed = {}, {}
    for name, expected in plan["targets_sha256"].items():
        data = regular_bytes(HERE.parent / name, plan["targets_bytes"][name])
        observed[name] = hashlib.sha256(data).hexdigest()
        if observed[name] != expected:
            raise AssertionError("frozen target hash changed: " + name)
        parsed[name] = ast.parse(data, filename="target-source-only/" + name)
    for name, expected in plan["fixtures_sha256"].items():
        observed[name] = hashlib.sha256(regular_bytes(HERE / name, plan["fixtures_bytes"][name])).hexdigest()
        if observed[name] != expected:
            raise AssertionError("frozen fixture hash changed: " + name)
    emit("SOURCE_PINS", sha256=observed)
    sys.path.insert(0, str(HERE))
    sys.addaudithook(audit)
    import fake_support
    fake_support.TREES.update(parsed)
    from guard_fakes import GuardFocusedCases
    from terminal_fakes import TerminalFocusedCases
    suite = unittest.TestSuite([
        unittest.defaultTestLoader.loadTestsFromTestCase(GuardFocusedCases),
        unittest.defaultTestLoader.loadTestsFromTestCase(TerminalFocusedCases)])
    if suite.countTestCases() != 20:
        raise AssertionError("exact twenty-method selector changed")
    result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
    forbidden = sorted(name for name in sys.modules if name.split(".", 1)[0]
                       in {"uta", "sqlite3", "_sqlite3", "multiprocessing", "subprocess"})
    after = {name: hashlib.sha256(regular_bytes((HERE.parent if name in TARGET_NAMES else HERE) / name,
                (plan["targets_bytes"] if name in TARGET_NAMES else plan["fixtures_bytes"])[name])).hexdigest()
             for name in observed}
    status = 0 if result.wasSuccessful() and not forbidden and after == observed else 1
    emit("END_FOCUSED_SYNTHETIC_ONLY", tests_run=result.testsRun, failures=len(result.failures),
         errors=len(result.errors), skipped=len(result.skipped), forbidden_runtime_imports=forbidden,
         source_after_sha256=after, before_after_source_pins_equal=after == observed,
         elapsed_seconds=monotonic() - STARTED, exit_status=status, attempt=1,
         original_pure7_and_original_peer_fixture_executables_not_run=True)
    return status


try:
    STATUS = main()
finally:
    sys.settrace(None)
raise SystemExit(STATUS)
