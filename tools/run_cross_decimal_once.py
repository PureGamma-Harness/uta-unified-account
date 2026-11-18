"""Fixed nine-method, whole-module retained Cross differential run, once.

No target child/thread/SQL/network/probe starts. The external caller owns Git
binding and actual timeout/taskset exit/reap/EOF; this receipt cannot prove a
future successful exit. Fixed trusted Python sources, not an OS sandbox.
"""
import argparse
import _thread
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import sys
import threading
import time
from types import ModuleType
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "evidence/reviews/cross-decimal-kernel/pure-once-plan.json"
RAW_LIMIT, TRAILER = 64512, 512  # Plus caller-owned prefix reserve1024 =64KiB.
RAW = {"reserved": 0, "writes": 0}
MODULES = ("models", "market", "products", "risk", "scenario_margin", "portfolio", "cross_decimal_kernel")
METHODS = (
    "test_full_manual_multi_asset_and_same_coin_gross_debt",
    "test_subcurrency_tier_and_separate_cash_deficit_manual_cases",
    "test_linear_long_short_multiplier_and_legitimate_cost_dust",
    "test_zero_maintenance_equal_maintenance_and_order_reserve_boundaries",
    "test_integer_borrow_floor_and_strict_maintenance_cap_manual_cases",
    "test_fixed_differential_grid_under_hostile_context_and_model_immutability",
    "test_large_model_bounded_values_and_zero_representation_are_exact",
    "test_invalid_scalar_and_explicit_unsupported_specializations",
    "test_candidate_does_not_call_reference_arithmetic_or_collateral_method",
)


def fail_raw():
    try:
        os.write(2, b'\n{"event":"CROSS_DECIMAL_RAW_UNKNOWN","complete":false,"exit":125}\n')
    finally:
        os._exit(125)


class RawStream:
    encoding, errors = "utf-8", "backslashreplace"

    def __init__(self, descriptor):
        self.fd = descriptor

    def write(self, text):
        value = text.encode(self.encoding, self.errors)
        if RAW["reserved"] + len(value) > RAW_LIMIT - TRAILER:
            fail_raw()
        RAW["reserved"] += len(value)
        try:
            if os.write(self.fd, value) != len(value):
                fail_raw()
            RAW["writes"] += 1
        except BaseException:
            fail_raw()
        return len(text)

    def flush(self):
        return None


def read_regular(path, limit=2 * 1024 * 1024):
    if path.resolve() != path or not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError("input must be canonical regular, without a symlink")
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as stream:
        before = os.fstat(stream.fileno())
        value = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    facts = {name: getattr(before, name) for name in fields}
    if len(value) > limit or facts != {name: getattr(after, name) for name in fields}:
        raise ValueError("input changed during bounded read")
    return value, facts


def exclusive(path, value):
    encoded = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    if len(encoded) > 1024 * 1024:
        raise ValueError("control record exceeds1MiB")
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "wb") as stream:
        if stream.write(encoded) != len(encoded):
            raise OSError("incomplete control write")
        stream.flush()
        os.fsync(stream.fileno())


def frozen_inputs(plan):
    frozen, facts = {}, {}
    for name, expected in plan["input_files"].items():
        if name.startswith("/") or ".." in Path(name).parts:
            raise ValueError("source path escaped checkout")
        value, identity = read_regular(ROOT / name)
        if {"bytes": len(value), "sha256": sha256(value).hexdigest()} != expected:
            raise ValueError("source length/SHA mismatch: " + name)
        frozen[name], facts[name] = value, identity
    return frozen, facts


def module(name, value, relative, package=False):
    result = ModuleType(name)
    result.__file__ = str(ROOT / relative)
    result.__package__ = name if package else name.rpartition(".")[0]
    if package:
        result.__path__ = []  # No filesystem UTA fallback beyond retained modules.
    sys.modules[name] = result
    exec(compile(value, result.__file__, "exec"), result.__dict__)
    parent, unused, leaf = name.rpartition(".")
    if parent:
        setattr(sys.modules[parent], leaf, result)
    return result


def install_guard():
    forbidden = []
    def deny(event):
        if len(forbidden) < 16:
            forbidden.append(event)
        raise RuntimeError("pure Cross scope forbids " + event)
    def audit(event, args):
        if event == "import" and args[0] in ("sqlite3", "_sqlite3"):
            deny("SQLite import")
        if event in {"subprocess.Popen", "os.fork", "os.forkpty", "os.exec", "os.posix_spawn",
                     "socket.__new__", "socket.connect", "socket.bind", "os.kill", "os.killpg",
                     "signal.pthread_kill", "sys.settrace", "sys.setprofile", "sys.monitoring.register_callback"}:
            deny(event)
        if event in ("open", "os.listdir", "os.scandir") and args and isinstance(args[0], str):
            if args[0] == "/proc" or args[0].startswith("/proc/"):
                deny("proc access")
    sys.addaudithook(audit)
    def no_thread(*args, **kwargs):
        deny("thread start")
    threading.Thread.start = no_thread
    _thread.start_new_thread = no_thread
    threading._start_new_thread = no_thread
    return forbidden


class CountedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.success_ids, self.grid_completed = [], 0

    def addSuccess(self, test):
        super().addSuccess(test)
        self.success_ids.append(test.id())

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if test._testMethodName == METHODS[5] and err is None:
            self.grid_completed += 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--private-directory", required=True, type=Path)
    args = parser.parse_args()
    output = args.private_directory
    if output.resolve() != output or output.parent != Path("/workspace"):
        raise ValueError("private output must be a fresh canonical workspace child")
    output.mkdir(mode=0o700)
    for fd, name in ((1, "first.stdout.txt"), (2, "first.stderr.txt")):
        target = os.open(output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        os.dup2(target, fd)
        os.close(target)
    sys.stdout, sys.stderr = RawStream(1), RawStream(2)
    plan_raw, plan_facts = read_regular(PLAN)
    if sha256(plan_raw).hexdigest() != args.plan_sha256:
        raise ValueError("plan SHA mismatch")
    plan = json.loads(plan_raw)
    if plan["methods"] != list(METHODS) or plan["module_order"] != list(MODULES):
        raise ValueError("fixed nine-method/full-module scope differs")
    frozen, before = frozen_inputs(plan)
    executable = Path(sys.executable).resolve()
    binary, unused = read_regular(executable, 64 * 1024 * 1024)
    runtime = {"sys_version": sys.version, "sys_executable": sys.executable,
        "resolved_executable": str(executable), "executable_bytes": len(binary),
        "executable_sha256": sha256(binary).hexdigest(), "affinity": sorted(os.sched_getaffinity(0)),
        "flags": {"isolated": sys.flags.isolated, "no_site": sys.flags.no_site,
                  "dont_write_bytecode": sys.flags.dont_write_bytecode}}
    if runtime != plan["expected_runtime"] or any(name == "uta" or name.startswith("uta.")
            or name in ("sqlite3", "_sqlite3") for name in sys.modules):
        raise ValueError("runtime/CPU differs or target imports are not fresh")
    exclusive(output / "intent.json", {"source_commit_invoker_label": args.source_commit,
        "plan_sha256": args.plan_sha256, "runtime": runtime, "input_files": plan["input_files"],
        "before": before, "planned_methods": list(METHODS), "production_approved": False})
    print(json.dumps({"event": "CROSS_DECIMAL_BEGIN", "source_commit_invoker_label": args.source_commit,
        "plan_sha256": args.plan_sha256, "methods": list(METHODS), "runtime": runtime}, sort_keys=True))
    forbidden = install_guard()
    started = time.monotonic_ns()
    module("uta", frozen["uta/__init__.py"], "uta/__init__.py", package=True)
    for name in MODULES:
        relative = "uta/" + name + ".py"
        module("uta." + name, frozen[relative], relative)
    fixture = module("test_cross_decimal_kernel", frozen["tests/test_cross_decimal_kernel.py"], "tests/test_cross_decimal_kernel.py")
    suite = unittest.TestSuite(fixture.CrossDecimalKernelTests(name) for name in METHODS)
    result = unittest.TextTestRunner(stream=sys.stderr, verbosity=2, failfast=True, resultclass=CountedResult).run(suite)
    elapsed = time.monotonic_ns() - started
    loaded = sorted(name for name in sys.modules if name == "uta" or name.startswith("uta."))
    expected = ["uta"] + sorted("uta." + name for name in MODULES)
    after, after_facts = frozen_inputs(plan)
    if after != frozen or after_facts != before or read_regular(PLAN) != (plan_raw, plan_facts):
        raise ValueError("input bytes/metadata or plan changed during execution")
    complete = (result.testsRun == 9 and result.success_ids == [
        "test_cross_decimal_kernel.CrossDecimalKernelTests." + name for name in METHODS]
        and result.grid_completed == 96 and not result.skipped and not result.expectedFailures
        and not result.unexpectedSuccesses and result.wasSuccessful())
    passed = complete and loaded == expected and not forbidden and threading.active_count() == 1
    receipt = {"complete": complete, "passed": passed, "tests_run": result.testsRun,
        "success_ids": result.success_ids, "grid_subtests_completed": result.grid_completed,
        "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
        "manual_case_ids_declared_in_source": plan["manual_case_ids"], "manual_ids_individually_instrumented": False,
        "source_unchanged": True, "after": after_facts, "runtime": runtime, "elapsed_ns": elapsed,
        "loaded_UTA_modules": loaded, "forbidden_listed_events": forbidden, "Python_thread_count": threading.active_count(),
        "source_commit_invoker_label": args.source_commit, "plan_sha256": args.plan_sha256,
        "raw_reserved_bytes_before_END": RAW["reserved"], "raw_writes_before_END": RAW["writes"],
        "production_approved": False, "SQL_or_native_or_admission_executed": False}
    exclusive(output / "first.execution.json", receipt)
    print(json.dumps({"event": "CROSS_DECIMAL_END", **receipt}, sort_keys=True))
    os.fsync(1)
    os.fsync(2)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
