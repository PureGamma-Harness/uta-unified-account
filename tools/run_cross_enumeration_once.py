"""Fixed five-method independent Cross enumeration, once.

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
PLAN = ROOT / "evidence/reviews/cross-decimal-enumeration/pure-once-plan.json"
RAW_LIMIT, TRAILER = 31744, 512  # Plus caller prefix reserve1024 =32KiB.
CONTROL_RESERVED = 0
RAW = {"reserved": 0, "writes": 0}
MODULES = ("models", "market", "products", "risk", "scenario_margin", "portfolio", "cross_decimal_kernel")
METHODS = (
    'test_512_seeded_values_and_exhaustively_maximal_quotes',
    'test_collateral_tier_crossing_and_full_freeze',
    'test_maintenance_equality_and_order_reserve_boundaries',
    'test_hostile_decimal_context_uses_independent_exact_oracle',
    'test_zero_and_equal_rate_strict_borrow_boundaries',
)


def fail_raw():
    try:
        os.write(2, b'\n{"event":"CROSS_ENUMERATION_RAW_UNKNOWN","complete":false,"exit":125}\n')
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
    global CONTROL_RESERVED
    encoded = (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    if len(encoded) > 4 * 1024 * 1024 or CONTROL_RESERVED + len(encoded) > 8 * 1024 * 1024 - 32768:
        raise ValueError("control/vector record exceeds registered budget")
    CONTROL_RESERVED += len(encoded)
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
        self.success_ids, self.completed_counts, self.vector_groups = [], [], []
        self.failure_vectors = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.success_ids.append(test.id())
        vectors = test.completed_vectors
        self.completed_counts.append(len(vectors))
        self.vector_groups.append({"test_id": test.id(), "vectors": vectors})

    def retain_failure(self, test, error, subtest=None):
        self.failure_vectors.append({"test_id": test.id(),
            "subtest_id": None if subtest is None else subtest.id(),
            "error_type": error[0].__name__,
            "active_vector": getattr(test, "active_vector", None),
            "completed_vectors_before_failure": getattr(test, "completed_vectors", [])})

    def addFailure(self, test, err):
        self.retain_failure(test, err)
        super().addFailure(test, err)

    def addError(self, test, err):
        self.retain_failure(test, err)
        super().addError(test, err)

    def addSubTest(self, test, subtest, err):
        if err is not None:
            self.retain_failure(test, err, subtest)
        super().addSubTest(test, subtest, err)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent-captured-stdio", action="store_true")
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--private-directory", required=True, type=Path)
    args = parser.parse_args()
    output = args.private_directory
    if output.resolve() != output or output.parent != Path("/workspace"):
        raise ValueError("private output must be a fresh canonical workspace child")
    if not args.parent_captured_stdio:
        raise ValueError("external capture of inherited stdout/stderr required")
    output.mkdir(mode=0o700)
    sys.stdout, sys.stderr = RawStream(1), RawStream(2)
    plan_raw, plan_facts = read_regular(PLAN)
    if sha256(plan_raw).hexdigest() != args.plan_sha256:
        raise ValueError("plan SHA mismatch")
    plan = json.loads(plan_raw)
    if plan["methods"] != list(METHODS) or plan["module_order"] != list(MODULES):
        raise ValueError("fixed five-method/full-module scope differs")
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
    print(json.dumps({"event": "CROSS_ENUMERATION_BEGIN", "source_commit_invoker_label": args.source_commit,
        "plan_sha256": args.plan_sha256, "methods": list(METHODS), "runtime": runtime}, sort_keys=True))
    forbidden = install_guard()
    started = time.monotonic_ns()
    module("uta", frozen["uta/__init__.py"], "uta/__init__.py", package=True)
    for name in MODULES:
        relative = "uta/" + name + ".py"
        module("uta." + name, frozen[relative], relative)
    fixture = module("test_cross_decimal_enumeration", frozen["tests/test_cross_decimal_enumeration.py"], "tests/test_cross_decimal_enumeration.py")
    suite = unittest.TestSuite(fixture.CrossDecimalEnumerationTests(name) for name in METHODS)
    result = unittest.TextTestRunner(stream=sys.stderr, verbosity=2, failfast=True, resultclass=CountedResult).run(suite)
    elapsed = time.monotonic_ns() - started
    loaded = sorted(name for name in sys.modules if name == "uta" or name.startswith("uta."))
    expected = ["uta"] + sorted("uta." + name for name in MODULES)
    after, after_facts = frozen_inputs(plan)
    if after != frozen or after_facts != before or read_regular(PLAN) != (plan_raw, plan_facts):
        raise ValueError("input bytes/metadata or plan changed during execution")
    complete = (result.testsRun == 5 and result.success_ids == [
        "test_cross_decimal_enumeration.CrossDecimalEnumerationTests." + name for name in METHODS]
        and result.completed_counts == [512, 6, 8, 8, 4] and not result.skipped and not result.expectedFailures
        and not result.unexpectedSuccesses and result.wasSuccessful())
    passed = complete and loaded == expected and not forbidden and threading.active_count() == 1
    vector_record = {"source_commit_invoker_label": args.source_commit,
        "plan_sha256": args.plan_sha256, "completed_counts": result.completed_counts,
        "vector_groups": result.vector_groups, "failure_vectors": result.failure_vectors,
        "all_538_required": complete}
    exclusive(output / "vectors.json", vector_record)
    vector_raw, unused = read_regular(output / "vectors.json", 4 * 1024 * 1024)
    receipt = {"complete": complete, "passed": passed, "tests_run": result.testsRun,
        "success_ids": result.success_ids, "completed_vectors_by_method": result.completed_counts, "completed_vectors": sum(result.completed_counts),
        "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
        "vector_file": {"bytes": len(vector_raw), "sha256": sha256(vector_raw).hexdigest()},
        "oracle_uses_reference_core": False, "borrow_quote_candidates_exhaustively_enumerated": True,
        "source_unchanged": True, "after": after_facts, "runtime": runtime, "elapsed_ns": elapsed,
        "loaded_UTA_modules": loaded, "forbidden_listed_events": forbidden, "Python_thread_count": threading.active_count(),
        "source_commit_invoker_label": args.source_commit, "plan_sha256": args.plan_sha256,
        "raw_reserved_bytes_before_END": RAW["reserved"], "raw_writes_before_END": RAW["writes"],
        "production_approved": False, "SQL_or_native_or_admission_executed": False}
    exclusive(output / "first.execution.json", receipt)
    print(json.dumps({"event": "CROSS_ENUMERATION_END", **receipt}, sort_keys=True))
    os.fsync(1)
    os.fsync(2)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
