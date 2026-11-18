"""Retained four-method inert diagnostic checks; no discovery or UTA imports."""
import argparse
from hashlib import sha256
from importlib.machinery import ModuleSpec
import json
import os
from pathlib import Path
import stat
import sys
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
HELPER = "monitor_registry_failure_evidence"
TEST = "test_monitor_registry_failure_evidence_pure"
CLASS = "MonitorRegistryFailureEvidenceTests"
METHODS = (
    "test_two_owned_threads_have_eight_frames_and_no_arbitrary_payload",
    "test_original_exception_object_survives_diagnostic_failure",
    "test_busy_mutex_and_worker_cache_are_never_acquired_or_read",
    "test_quota_or_blocking_sink_denial_never_retries_output",
)


def read_regular(path, limit=2 * 1024 * 1024):
    if path.resolve() != path or not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError("canonical regular source required")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        value = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    keys = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    if len(value) > limit or any(getattr(before, k) != getattr(after, k) for k in keys):
        raise ValueError("input changed during bounded source read")
    return value


def pins(path, approved):
    raw = read_regular(path)
    if sha256(raw).hexdigest() != approved:
        raise ValueError("unapproved binding")
    binding, frozen = json.loads(raw), {}
    for name, expected in binding["inputs"].items():
        if name.startswith("/") or ".." in Path(name).parts:
            raise ValueError("source escaped root")
        value = read_regular(ROOT / name)
        if {"bytes": len(value), "sha256": sha256(value).hexdigest()} != expected:
            raise ValueError("source pin differs: " + name)
        frozen[name] = value
    return frozen


def retained(name, relative, frozen):
    if name in sys.modules:
        raise ValueError("retained module already loaded")
    module = ModuleType(name)
    module.__file__ = str(ROOT / relative)
    module.__package__ = ""
    module.__spec__ = ModuleSpec(name, loader=None, origin=module.__file__)
    sys.modules[name] = module
    exec(compile(frozen[relative], module.__file__, "exec"), module.__dict__)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", choices=("diagnostic4",), required=True)
    parser.add_argument("--binding", required=True, type=Path)
    parser.add_argument("--approved-binding-sha256", required=True)
    parser.add_argument("methods", nargs="+")
    args = parser.parse_args()
    methods = [CLASS + "." + method for method in METHODS]
    if args.methods != methods:
        raise ValueError("only four original methods in fixed order; no discovery")
    if not (sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise ValueError("-I -S -B required")
    before = pins(args.binding, args.approved_binding_sha256)
    forbidden = []
    def deny(event):
        if len(forbidden) < 16:
            forbidden.append(event)
        raise RuntimeError("inert pure scope forbids " + event)
    def audit(event, arguments):
        if event == "import" and (arguments[0] == "uta" or arguments[0].startswith("uta.")
                or arguments[0] in ("sqlite3", "_sqlite3")):
            deny("financial_or_SQLite_import")
        if event in {"subprocess.Popen", "os.fork", "os.forkpty", "os.exec", "os.posix_spawn",
                     "os.system", "os.kill", "os.killpg", "sys._current_frames",
                     "socket.__new__", "socket.connect", "socket.bind", "socket.getaddrinfo"}:
            deny(event)
        if event in ("open", "os.listdir", "os.scandir") and arguments and isinstance(arguments[0], (str, bytes)):
            name = os.fsdecode(arguments[0])
            if name == "/proc" or name.startswith("/proc/"):
                deny("proc_access")
    sys.addaudithook(audit)
    import _thread
    import signal
    import threading
    def no_thread(*unused, **kwargs):
        deny("thread_start")
    def no_signal(*unused, **kwargs):
        deny("signal_call_or_handler_install")
    threading.Thread.start = no_thread
    _thread.start_new_thread = no_thread
    if hasattr(threading, "_start_new_thread"):
        threading._start_new_thread = no_thread
    for name in ("signal", "setitimer", "alarm", "pthread_kill", "raise_signal", "pidfd_send_signal"):
        if hasattr(signal, name):
            setattr(signal, name, no_signal)
    helper = retained(HELPER, "tests/" + HELPER + ".py", before)
    exports = {name: getattr(helper, name) for name in
               ("_walk", "_thread_packets", "_primary", "build_packet", "render", "write_packet", "emit_once")}
    test = retained(TEST, "tests/" + TEST + ".py", before)
    def identities():
        if (sys.modules.get(HELPER) is not helper or sys.modules.get(TEST) is not test
                or test.evidence is not helper or helper.__file__ != str(ROOT / "tests" / (HELPER + ".py"))):
            raise ValueError("retained helper/test identity changed")
        if any(getattr(helper, name) is not value for name, value in exports.items()):
            raise ValueError("retained helper function changed")
    identities()
    import unittest
    actual_success, actual_failure = [], []
    class RecordedResult(unittest.TextTestResult):
        def addSuccess(self, case):
            actual_success.append(case.id())
            super().addSuccess(case)
        def addFailure(self, case, error):
            actual_failure.append(case.id())
            super().addFailure(case, error)
        def addError(self, case, error):
            actual_failure.append(case.id())
            super().addError(case, error)
        def addSubTest(self, case, subtest, error):
            if error is not None:
                actual_failure.append(subtest.id())
            super().addSubTest(case, subtest, error)
    kind = getattr(test, CLASS)
    if not isinstance(kind, type) or not issubclass(kind, unittest.TestCase):
        raise ValueError("fixed test class changed")
    cases = [kind(name) for name in METHODS]
    expected_ids = [case.id() for case in cases]
    result = unittest.TextTestRunner(verbosity=2, failfast=True, resultclass=RecordedResult).run(unittest.TestSuite(cases))
    identities()
    after = pins(args.binding, args.approved_binding_sha256)
    counts = {name: len(getattr(result, name)) for name in
              ("failures", "errors", "skipped", "expectedFailures", "unexpectedSuccesses")}
    financial = sorted(name for name in sys.modules if name == "uta" or name.startswith("uta.") or name in ("sqlite3", "_sqlite3"))
    guards_unchanged = threading.Thread.start is no_thread and _thread.start_new_thread is no_thread and signal.signal is no_signal
    passed = (before == after and result.testsRun == 4 and actual_success == expected_ids
              and not any(counts.values()) and result.wasSuccessful() and not forbidden and not financial and guards_unchanged)
    print(json.dumps({"event": "FIXED_PURE_SCOPE_RESULT", "scope": args.scope,
        "methods": methods, "expected_IDs": expected_ids, "actual_success_IDs": actual_success,
        "actual_failure_IDs": actual_failure, "tests_run": result.testsRun, "counts": counts,
        "source_pins_unchanged": before == after, "retained_helper_identity_unchanged": True,
        "forbidden_imports": financial, "forbidden_listed_attempts": forbidden,
        "guards_unchanged": guards_unchanged, "passed": passed,
        "stdlib_dependency_imports": {name: name in sys.modules for name in ("signal", "threading", "asyncio", "subprocess")},
        "operation_limit": "Listed audit/guard and reviewed source only; no kernel syscall or ownership attestation.",
        "native_recovery_or_CI_cause_proven": False}, sort_keys=True), flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
