"""One selected m08-only materialized-input-gated pure run; no business processes.

Invoke only with an explicit root once budget, externally bounded by timeout
and CPU affinity. No subprocess or Git command is launched by this driver.
The source-commit argument is an invoker-supplied label, not an election proof.
"""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import sys
import time
import traceback
from types import MappingProxyType


ROOT = Path(__file__).resolve().parents[3]
STARTED = time.monotonic()
DEADLINE = STARTED + 10
RAW_LIMIT = 256 * 1024
RAW_TRAILER_RESERVE = 512
RAW_STATE = {"reserved": 0, "failed": False}


def raw_failure():
    # Reuses the independently reviewed 19eebff RawStream protocol: reserve
    # before FD write, one shared stdout/stderr budget, sticky unknown exit125.
    RAW_STATE["failed"] = True
    marker = b'\n{"event":"STARTUP_PHASE1_M08_RAW_CAPTURE_UNKNOWN","complete":false,"exit_status":125}\n'
    try:
        os.write(2, marker)  # Reserved trailer on the already-open private FD.
    finally:
        os._exit(125)


class RawStream:
    encoding, errors = "utf-8", "backslashreplace"

    def __init__(self, descriptor):
        self.fd = descriptor

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
        return None

    def fileno(self):
        return self.fd

    def isatty(self):
        return False


def budget(frame, event, arg):
    if time.monotonic() >= DEADLINE:
        print('{"event":"STARTUP_PHASE1_M08_WALL_BUDGET_EXHAUSTED","wall_seconds":10}', flush=True)
        os._exit(124)
    return budget


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
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise ValueError("opened input is not a bounded regular file")
        raw = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    properties = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    if len(raw) > limit or any(getattr(before, key) != getattr(after, key) for key in properties):
        raise ValueError("input changed during materialized read")
    return raw


def input_pins(plan, *, retain_bytes=False):
    result, frozen = {}, {}
    for name, expected in plan["input_files"].items():
        if name.startswith("/") or ".." in Path(name).parts:
            raise ValueError("input path escapes frozen source")
        raw = read_regular(ROOT / name)
        value = {"bytes": len(raw), "sha256": sha256(raw).hexdigest()}
        if value != expected:
            raise ValueError("materialized input differs from frozen length/SHA")
        result[name] = value
        if retain_bytes:
            frozen[name] = raw
    return (result, MappingProxyType(frozen)) if retain_bytes else result


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
    out_fd = os.open(output / "first.stdout.txt", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    err_fd = os.open(output / "first.stderr.txt", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.dup2(out_fd, 1)
    os.dup2(err_fd, 2)
    os.close(out_fd)
    os.close(err_fd)
    sys.stdout, sys.stderr = RawStream(1), RawStream(2)
    sys.settrace(budget)
    plan_path = ROOT / "evidence/reviews/owned-startup-read-admission/phase1-m08-focused-plan.json"
    plan_raw = read_regular(plan_path)
    if sha256(plan_raw).hexdigest() != args.plan_sha256:
        exclusive(output / "preflight.json", encoded({"passed": False, "target_started": False,
                  "reason": "frozen_plan_SHA_mismatch"}))
        return 1
    plan = json.loads(plan_raw)
    try:
        before, frozen_bytes = input_pins(plan, retain_bytes=True)
    except BaseException as error:
        exclusive(output / "preflight.json", encoded({"passed": False, "target_started": False,
                  "reason": "materialized_input_gate", "error_type": type(error).__name__}))
        raise
    actual_affinity = sorted(os.sched_getaffinity(0))
    executable = Path(sys.executable).resolve()
    executable_raw = read_regular(executable, limit=64 * 1024 * 1024)
    runtime = {"sys_version": sys.version, "sys_executable": sys.executable,
               "resolved_executable": str(executable), "executable_bytes": len(executable_raw),
               "executable_sha256": sha256(executable_raw).hexdigest(),
               "flags": {"isolated": sys.flags.isolated, "no_site": sys.flags.no_site,
                         "dont_write_bytecode": sys.flags.dont_write_bytecode},
               "binary_only_not_all_shared_libraries_QA": True, "actual_affinity": actual_affinity}
    expected_runtime = plan["host_orchestration"]["expected_runtime"]
    runtime_matches = all(runtime[key] == value for key, value in expected_runtime.items())
    if actual_affinity != [1] or not runtime_matches:
        exclusive(output / "preflight.json", encoded({"passed": False, "target_started": False,
            "reason": "actual_affinity_or_runtime_mismatch", "runtime": runtime}))
        return 1
    fixture_name = "evidence/reviews/owned-startup-read-admission/phase1_focused_fake.py"
    fixture = ROOT / fixture_name
    raw = frozen_bytes[fixture_name]
    exec_pin = {"bytes": len(raw), "sha256": sha256(raw).hexdigest()}
    if exec_pin != plan["input_files"][fixture_name]:
        exclusive(output / "preflight.json", encoded({"passed": False, "target_started": False,
            "reason": "actual_exec_bytes_mismatch", "observed_exec_pin": exec_pin}))
        return 1
    exclusive(output / "intent.json", encoded({"source_commit_supplied_by_invoker": args.source_commit,
        "commit_not_resolved_by_this_driver": True, "plan_sha256": args.plan_sha256,
        "input_pins_before": before, "first_and_only": True, "planned_methods": 1,
        "planned_small_traces": 4, "scope": plan["scope"], "runtime": runtime,
        "exact_exec_fixture_pin": exec_pin, "raw_stdout_stderr_shared_limit_bytes": RAW_LIMIT,
        "raw_reserved_trailer_bytes": RAW_TRAILER_RESERVE,
        "host_argv_template": plan["host_orchestration"]["argv_template"],
        "outer_host_invocation_not_self_attested": True, "production_approved": False}))
    print(json.dumps({"event": "BEGIN_STARTUP_PHASE1_M08_PURE_ONCE", "source_commit": args.source_commit,
        "runtime": runtime, "input_pins_before": before, "exact_exec_fixture_pin": exec_pin,
        "shared_raw_cap_bytes": RAW_LIMIT, "wall_budget_seconds": 10,
        "methods": 1, "small_traces": 4, "native_or_financial_authorized": False}, sort_keys=True))
    sys.addaudithook(pure_audit)
    # These guards are defense in depth for reviewed source, not an OS sandbox.
    started = time.monotonic_ns()
    returncode = 1
    try:
        # Load definitions without the original __main__ whole-suite runner.
        # No method body is discovered or selected except this fixed m08 name.
        namespace = {"__name__": "_startup_phase1_m08_frozen", "__file__": str(fixture),
                     "_FROZEN_INPUT_BYTES": frozen_bytes}
        exec(compile(raw, str(fixture), "exec"), namespace)
        selected = "test_08_owned_same_token_last_known_and_postcommit_wrapper_unknown"
        if plan["selected_method"] != selected:
            raise ValueError("m08 selector differs from frozen plan")
        unittest = namespace["unittest"]
        suite = unittest.TestSuite([namespace["Phase1FocusedFakeTests"](selected)])
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        complete = result.testsRun == 1 and namespace["TRACES"] == 4
        passed = result.wasSuccessful() and complete
        print(json.dumps({"scope": "ONE_SELECTED_M08_ACTUAL_OBSERVATION_CODE_WITH_MEMORY_FAKES_ONLY",
            "selected_method": selected, "methods": result.testsRun, "small_traces": namespace["TRACES"],
            "failures": len(result.failures), "errors": len(result.errors), "passed": passed,
            "expected_method_and_four_selector_counts_complete": complete,
            "other_eleven_method_bodies_executed": False, "SQL_or_UTA_module_import": False,
            "native_thread_process_signal_network_or_real_sleep": False,
            "phase2_authorized": False, "native_or_financial_approved": False,
            "production_approved": False}, sort_keys=True))
        returncode = 0 if passed else 1
    except SystemExit:
        # A definition-time stop is never a completed single-method result.
        traceback.print_exc()
        returncode = 1
    except BaseException:
        traceback.print_exc()
    elapsed = time.monotonic_ns() - started
    after = input_pins(plan)
    print(json.dumps({"event": "END_STARTUP_PHASE1_M08_PURE_ONCE", "exit_status": returncode,
        "source_pins_after": after, "before_after_equal": before == after,
        "raw_capture_complete": not RAW_STATE["failed"], "production_approved": False}, sort_keys=True))
    os.fsync(1)
    os.fsync(2)
    exclusive(output / "first.execution.json", encoded({
        "returncode": returncode, "elapsed_ns": elapsed, "input_pins_after": after,
        "source_before_after_equal": before == after, "target_started": True,
        "runtime": runtime, "exact_exec_fixture_pin": exec_pin,
        "shared_raw_reserved_bytes": RAW_STATE["reserved"], "raw_capture_complete": not RAW_STATE["failed"],
        "native_or_financial_approved": False, "phase2_authorized": False,
        "production_approved": False}))
    return returncode


if __name__ == "__main__":
    try:
        status = main()
    finally:
        sys.settrace(None)
    raise SystemExit(status)
