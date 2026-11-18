"""Bounded pure Cross calculations and selected exact service methods, once.

The caller owns hard timeout/CPU, Git binding, actual argv/exit/reap/elapsed.
This driver starts no child, thread, SQL, network or native process probe. It
does not import the service module or run admission/transaction/matching paths.
"""
import argparse
import ast
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import sys
import time
from types import ModuleType
import unittest


ROOT = Path(__file__).resolve().parents[1]
RAW_LIMIT, TRAILER_RESERVE = 262144, 512
RAW = {"reserved": 0}


class RawStream:
    encoding, errors = "utf-8", "backslashreplace"

    def __init__(self, descriptor):
        self.fd = descriptor

    def write(self, text):
        raw = text.encode(self.encoding, self.errors)
        if RAW["reserved"] + len(raw) > RAW_LIMIT - TRAILER_RESERVE:
            fail_raw()
        RAW["reserved"] += len(raw)
        try:
            written = os.write(self.fd, raw)
            if written != len(raw):
                raise OSError("incomplete raw write")
        except BaseException:
            fail_raw()
        return len(text)

    def flush(self):
        return None


def fail_raw():
    try:
        os.write(2, b'\n{"event":"CROSS_MAINTENANCE_RAW_UNKNOWN","complete":false,"exit":125}\n')
    finally:
        os._exit(125)


def read_regular(path, limit=2 * 1024 * 1024):
    if path.resolve() != path or not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError("input must be a canonical materialized regular file")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        raw = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    if len(raw) > limit or any(getattr(before, key) != getattr(after, key) for key in fields):
        raise ValueError("input exceeded bound or changed while reading")
    return raw


def exclusive(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write((json.dumps(value, sort_keys=True, indent=2) + "\n").encode())
        stream.flush()
        os.fsync(stream.fileno())


def frozen_inputs(plan):
    frozen = {}
    for name, expected in plan["input_files"].items():
        if name.startswith("/") or ".." in Path(name).parts:
            raise ValueError("input path escaped checkout")
        raw = read_regular(ROOT / name)
        if {"bytes": len(raw), "sha256": sha256(raw).hexdigest()} != expected:
            raise ValueError("input length/SHA mismatch: " + name)
        frozen[name] = raw
    return frozen


def module(name, source, relative):
    result = ModuleType(name)
    result.__file__ = str(ROOT / relative)
    result.__package__ = name.rpartition(".")[0]
    sys.modules[name] = result
    exec(compile(source, result.__file__, "exec"), result.__dict__)
    return result


def selected_service(source, plan):
    """Compile these unchanged method AST nodes; omit all SQL/native imports."""
    from decimal import Decimal
    from fractions import Fraction
    from uta.models import RiskInputError
    from uta.products import ProductKind
    parsed = ast.parse(source, filename=str(ROOT / "uta/service.py"))
    wanted = set(plan["selected_service_methods"])
    classes = [node for node in parsed.body if isinstance(node, ast.ClassDef) and node.name == "ExchangeService"]
    if len(classes) != 1:
        raise ValueError("service class identity is ambiguous")
    methods = [node for node in classes[0].body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    if len(methods) != len(wanted) or {node.name for node in methods} != wanted:
        raise ValueError("selected service method identity is incomplete")
    globals_ = [node for node in parsed.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in ("ServiceError", "_exact")
        or isinstance(node, ast.Assign) and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name) and node.targets[0].id in ("_ZERO", "_MAX_INPUT")]
    if len(globals_) != 4:
        raise ValueError("selected service globals are incomplete")
    selected = ast.Module(body=[*globals_, ast.ClassDef(name="ExchangeService", bases=[], keywords=[],
        body=methods, decorator_list=[], type_params=[])], type_ignores=[])
    ast.fix_missing_locations(selected)
    result = ModuleType("uta.service")
    result.__file__ = str(ROOT / "uta/service.py")
    result.__package__ = "uta"
    result.__dict__.update(Decimal=Decimal, Fraction=Fraction, RiskInputError=RiskInputError, ProductKind=ProductKind)
    sys.modules[result.__name__] = result
    exec(compile(selected, result.__file__, "exec"), result.__dict__)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--private-directory", required=True, type=Path)
    args = parser.parse_args()
    output = args.private_directory
    output.mkdir(mode=0o700)
    for fd, name in ((1, "first.stdout.txt"), (2, "first.stderr.txt")):
        target = os.open(output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        os.dup2(target, fd)
        os.close(target)
    sys.stdout, sys.stderr = RawStream(1), RawStream(2)
    plan_path = ROOT / "evidence/reviews/cross-maintenance-boundary/once-plan.json"
    plan_raw = read_regular(plan_path)
    if sha256(plan_raw).hexdigest() != args.plan_sha256:
        raise ValueError("plan SHA mismatch")
    plan = json.loads(plan_raw)
    frozen = frozen_inputs(plan)
    executable = Path(sys.executable).resolve()
    binary = read_regular(executable, 64 * 1024 * 1024)
    runtime = {"sys_version": sys.version, "sys_executable": sys.executable,
        "resolved_executable": str(executable), "executable_bytes": len(binary),
        "executable_sha256": sha256(binary).hexdigest(), "affinity": sorted(os.sched_getaffinity(0)),
        "flags": {"isolated": sys.flags.isolated, "no_site": sys.flags.no_site,
                  "dont_write_bytecode": sys.flags.dont_write_bytecode}}
    if runtime != plan["expected_runtime"]:
        raise ValueError("actual runtime/CPU differs from approved plan")
    exclusive(output / "intent.json", {"source_commit_invoker_label": args.source_commit,
        "plan_sha256": args.plan_sha256, "runtime": runtime, "input_files": plan["input_files"],
        "planned_methods": 6, "production_approved": False})
    package = ModuleType("uta")
    package.__path__ = []
    sys.modules["uta"] = package
    print(json.dumps({"event": "CROSS_MAINTENANCE_BEGIN", "methods": 6, "runtime": runtime}, sort_keys=True))
    started = time.monotonic_ns()
    for name in ("models", "market", "products", "risk", "scenario_margin", "portfolio"):
        relative = "uta/" + name + ".py"
        module("uta." + name, frozen[relative], relative)
    selected_service(frozen["uta/service.py"], plan)
    fixture = module("cross_maintenance_fixture", frozen["tests/test_cross_maintenance_boundary.py"],
                     "tests/test_cross_maintenance_boundary.py")
    suite = unittest.TestSuite(fixture.CrossMaintenanceBoundaryTests(name) for name in plan["methods"])
    result = unittest.TextTestRunner(stream=sys.stderr, verbosity=2).run(suite)
    elapsed = time.monotonic_ns() - started
    after = frozen_inputs(plan)
    if after != frozen or read_regular(plan_path) != plan_raw:
        raise ValueError("source or plan changed during execution")
    passed = (result.testsRun == 6 and result.wasSuccessful() and not result.skipped
              and not result.expectedFailures and not result.unexpectedSuccesses
              and fixture.COMPLETED_CASES == plan["case_ids"])
    receipt = {"complete": True, "tests_run": result.testsRun, "case_ids": fixture.COMPLETED_CASES,
        "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
        "passed": passed, "source_unchanged": True, "runtime": runtime, "elapsed_ns": elapsed,
        "source_commit_invoker_label": args.source_commit, "plan_sha256": args.plan_sha256,
        "raw_reserved_bytes_before_END": RAW["reserved"], "production_approved": False,
        "SQL_service_admission_fill_or_matching_executed": False,
        "selected_service_methods": plan["selected_service_methods"]}
    exclusive(output / "first.execution.json", receipt)
    print(json.dumps({"event": "CROSS_MAINTENANCE_END", **receipt}, sort_keys=True))
    os.fsync(1)
    os.fsync(2)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
