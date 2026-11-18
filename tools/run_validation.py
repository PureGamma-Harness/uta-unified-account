"""Record a reproducible full unittest run without third-party test dependencies."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
from itertools import islice
import json
from pathlib import Path
import platform
import re
import sqlite3
import subprocess
import sys
import time
import unittest
from types import MappingProxyType, ModuleType

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Independent publication allowlist: never import UTA to collect diagnostics.
_LEASE_CAPTURE_INTS = frozenset({
    "version", "assert_generation", "assert_row_observed_ns", "assert_row_expires_ns", "assert_now_ns",
    "guard_load_started_ns", "guard_lease_fetch_started_ns", "guard_lease_fetch_finished_ns",
    "guard_load_finished_ns", "guard_validation_finished_ns", "guard_generation",
    "guard_row_observed_ns", "guard_row_expires_ns", "assert_load_started_ns",
    "assert_lease_fetch_started_ns", "assert_lease_fetch_finished_ns", "assert_load_finished_ns",
    "renew_generation", "renew_observed_ns", "renew_expires_ns", "renew_attempt",
    "renew_attempt_started_ns", "renew_attempt_finished_ns", "last_known_renew_attempt",
    "last_known_renew_generation", "last_known_renew_observed_ns", "last_known_renew_expires_ns",
    "last_known_renew_started_ns", "last_known_renew_finished_ns",
})
_LEASE_CAPTURE_BOOLS = frozenset({
    "identity_matches", "snapshot_time_known", "renew_known_commit", "last_known_renew_same_token",
})
_LEASE_CAPTURE_ENUMS = {
    "lease_clock": frozenset({"fence_clock_ns"}), "elapsed_clock": frozenset({"monotonic_ns"}),
    "phase": frozenset({"ledger_read_entry", "credit_read_entry", "renew"}),
    "renew_attempt_state": frozenset({"pending", "known_commit", "returned_unobserved", "failed_or_unknown"}),
}


def _lease_error_fields(error):
    module = sys.modules.get("uta.writer_fence")
    if type(module) is not ModuleType or not isinstance(error, BaseException):
        return None
    tag = None
    for index, (key, value) in enumerate(dict.items(vars(module))):
        if index >= 256:
            break
        if type(key) is str and key == "_LEASE_OBSERVATION_TAG":
            tag = value
            break
    if tag is None:
        return None
    payload = None
    data = BaseException.__dict__["__dict__"].__get__(error, BaseException)
    for index, (key, value) in enumerate(dict.items(data)):
        if index >= 64:
            break
        if type(key) is str and key == "_uta_lease_observation_v1":
            payload = value
            break
    if not (type(payload) is tuple and len(payload) == 2 and payload[0] is tag
            and type(payload[1]) is MappingProxyType):
        return None
    return _lease_capture_fields(payload[1])


def _lease_capture_fields(values):
    if type(values) is dict:
        items = dict.items(values)
    elif type(values) is MappingProxyType:
        items = MappingProxyType.items(values)
    else:
        return None
    fields = {}
    for index, (key, value) in enumerate(items):
        if index >= 64:
            break
        if type(key) is not str:
            continue
        if key in _LEASE_CAPTURE_INTS and type(value) is int and 0 <= value <= 2**63 - 1:
            fields[key] = value
        elif key in _LEASE_CAPTURE_BOOLS and type(value) is bool:
            if key != "snapshot_time_known" or value is False:
                fields[key] = value
        elif (key in _LEASE_CAPTURE_ENUMS and type(value) is str
              and value in _LEASE_CAPTURE_ENUMS[key]):
            fields[key] = value
    if not fields or len(json.dumps(fields, separators=(",", ":"))) > 4096:
        return None
    return fields


def _lease_test_key(test):
    """Read native TestCase/type metadata, not a user-overridden id()/repr()."""
    cls = type(test)
    namespace = type.__dict__["__dict__"].__get__(cls, type)
    module = next((value for key, value in islice(MappingProxyType.items(namespace), 64)
                   if type(key) is str and key == "__module__"), None)
    name = type.__dict__["__name__"].__get__(cls, type)
    data = unittest.TestCase.__dict__["__dict__"].__get__(test, unittest.TestCase)
    method = next((value for key, value in islice(dict.items(data), 64)
                   if type(key) is str and key == "_testMethodName"), None)
    if (type(module) is str and len(module) <= 128
            and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*){0,8}", module)
            and type(name) is str and len(name) <= 128 and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name)
            and type(method) is str and len(method) <= 128 and re.fullmatch(r"test_[A-Za-z0-9_]+", method)):
        value = module + "." + name + "." + method
        if len(value) <= 256:
            return value
    return "test_identity_unavailable"


def _lease_result_projection(result):
    """Revalidate worker output; mutable result state is not publication input."""
    try:
        data = unittest.TestResult.__dict__["__dict__"].__get__(result, unittest.TestResult)
        raw = {}
        for key, value in islice(dict.items(data), 64):
            if type(key) is str and key in {"lease_observations", "lease_observations_truncated"}:
                raw[key] = value
        values = raw.get("lease_observations")
        if type(values) is not list:
            return {"lease_observations": [], "lease_observations_truncated": True}
        copied, total = [], 0
        truncated = raw.get("lease_observations_truncated") is not False or len(values) > 16
        for capsule in islice(values, 16):
            if type(capsule) is not dict:
                truncated = True
                continue
            parts = {key: value for key, value in islice(dict.items(capsule), 8)
                     if type(key) is str and key in {"test", "lease"}}
            test = parts.get("test")
            fields = _lease_capture_fields(parts.get("lease"))
            if (type(test) is not str or len(test) > 256
                    or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*){0,8}", test)
                    or fields is None):
                truncated = True
                continue
            value = {"test": test, "lease": fields}
            size = len(json.dumps(value, separators=(",", ":")))
            if total + size > 65536:
                truncated = True
                break
            copied.append(value)
            total += size
        return {"lease_observations": copied, "lease_observations_truncated": truncated}
    except Exception:
        return {"lease_observations": [], "lease_observations_truncated": True}


class _LeaseObservedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lease_observations = []
        self.lease_observations_truncated = False
        self._lease_observation_bytes = 0

    def addError(self, test, err):
        super().addError(test, err)  # Original error bookkeeping/traceback exactly once, first.
        try:
            fields = _lease_error_fields(err[1])
            if fields is None:
                return
            value = {"test": _lease_test_key(test), "lease": fields}
            size = len(json.dumps(value, separators=(",", ":")))
            if len(self.lease_observations) >= 16 or self._lease_observation_bytes + size > 65536:
                self.lease_observations_truncated = True
                return
            self.lease_observations.append(value)
            self._lease_observation_bytes += size
        except BaseException:
            pass  # An existing test error cannot be replaced by optional collection.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="new result directory")
    parser.add_argument("--_worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args._worker:
        # Parent redirects the actual OS descriptors. Spawned processes and
        # native-library stderr therefore belong to the same raw log as tests.
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
        result = unittest.TextTestRunner(stream=sys.stderr, verbosity=2,
                                         resultclass=_LeaseObservedResult).run(suite)
        (args.output / "worker-result.json").write_text(json.dumps({
            "tests_run": result.testsRun, "failures": len(result.failures),
            "errors": len(result.errors), "skipped": len(result.skipped),
            "expected_failures": len(result.expectedFailures),
            "unexpected_successes": len(result.unexpectedSuccesses),
            "unittest_passed": result.wasSuccessful(),
            **_lease_result_projection(result)}, indent=2) + "\n")
        return 0 if result.wasSuccessful() else 1
    args.output = args.output.expanduser().absolute()
    args.output.mkdir(parents=True, exist_ok=False)
    started = datetime.now(timezone.utc).isoformat()
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    def sources():
        paths = {path for folder in ("uta", "tests", "formal", "tools", "benchmarks", "scripts")
                 for path in (ROOT / folder).rglob("*.py")}
        paths.update(path for path in (ROOT / "tests" / "fixtures").rglob("*") if path.is_file())
        paths.update(ROOT / name for name in ("pyproject.toml", "MANIFEST.in", "LICENSE") if (ROOT / name).exists())
        return {path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest()
                for path in sorted(paths)}
    def clean(manifest):
        paths = ("uta", "tests", "formal", "tools", "benchmarks", "scripts", "pyproject.toml", "MANIFEST.in", "LICENSE")
        tracked = set(subprocess.check_output(["git", "ls-files", "-z", "--", *paths], cwd=ROOT).decode().split("\0"))
        return set(manifest) <= tracked and subprocess.run(
            ["git", "diff", "--quiet", "HEAD", "--", *paths], cwd=ROOT).returncode == 0
    before = sources()
    clean_before = clean(before)
    beginning = time.perf_counter()
    with (args.output / "unittest.txt").open("x", encoding="utf-8") as log:
        completed = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--_worker",
                                    "--output", str(args.output)], cwd=ROOT,
                                   stdout=log, stderr=subprocess.STDOUT)
    elapsed = time.perf_counter() - beginning
    after = sources()
    clean_after = clean(after)
    result_path = args.output / "worker-result.json"
    result = json.loads(result_path.read_text()) if result_path.exists() else {
        "tests_run": None, "failures": None, "errors": None, "skipped": None,
        "expected_failures": None, "unexpected_successes": None, "unittest_passed": False}
    unchanged = before == after
    report = {"code_commit": sha, "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
              "command_argv": [sys.executable, str(Path(__file__).resolve()), "--output", str(args.output)],
              "python": sys.version, "platform": platform.platform(), "sqlite": sqlite3.sqlite_version,
              **result, "duration_seconds": elapsed, "worker_exit_code": completed.returncode,
              "passed": result["unittest_passed"] and completed.returncode == 0 and unchanged and clean_before and clean_after,
              "source_unchanged": unchanged, "tracked_source_clean_before": clean_before,
              "tracked_source_clean_after": clean_after,
              "source_sha256": before, "source_sha256_after": after,
              "test_log_sha256": sha256((args.output / "unittest.txt").read_bytes()).hexdigest(),
              "production_approved": False}
    (args.output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if not key.startswith("source_sha256")}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
