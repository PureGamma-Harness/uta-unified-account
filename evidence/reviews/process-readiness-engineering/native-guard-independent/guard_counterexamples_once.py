"""One frozen synthetic batch; never imports or executes the target module.

Only selected, unchanged AST definitions/subtrees execute with fake proc,
pidfd, signals, file writes, fsync and time. Real os is used solely for this
fixture's affinity/deadline metadata. No target tests, UTA or SQLite imports.
"""
import ast
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
from time import monotonic
from types import SimpleNamespace
import unittest


TARGET_COMMIT = "0fbf6797b6a2f0c3bd8ed5782c303b024b48da90"
BASE = Path(__file__).resolve().parents[1]
PINS = {
    "native_once.py": "4926570fc7b86b3ea75317fc349c395724b350f3975cb24997d254eee54a8d6e",
    "native_once_common.py": "a1d4a8be96fc4694ce0679cd6beb77ab82cf7826bc1fb9a784a1c312dc9f8838",
}
REQUIRED_PROTECTED = (4471, 8784, 310035, 310039, 310266, 310269)
TREES = {}


class ProbeRead(BaseException):
    pass


class ProbePath:
    reads = []

    def __init__(self, value):
        self.value = str(value)

    def __truediv__(self, value):
        return ProbePath(self.value + "/" + str(value))

    def read_text(self):
        self.reads.append(self.value)
        raise ProbeRead(self.value)


class FakeLock:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeWrites:
    def __init__(self, *, initial=0, chunk=b"x" * 64):
        self.bytes = initial
        self.chunk = chunk
        self.fsync_calls = 0

    def write(self, fd, data):
        self.bytes += len(data)
        return len(data)

    def fsync(self, fd):
        self.fsync_calls += 1
        if self.fsync_calls == 1:
            raise OSError("synthetic fsync EIO after successful write")

    def read(self, fd, size):
        return self.chunk


def selected_common(fake_os=None, fake_signal=None):
    names = {"PROTECTED_PIDS", "STDIO_CAP", "BIRTH_FIELDS", "ScopeUnknown",
             "encode", "_write_all", "Journal", "identity", "same_birth", "BoundChild"}
    body = []
    for node in TREES["native_once_common.py"].body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names:
            body.append(deepcopy(node))
        elif isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id in names for target in node.targets):
            body.append(deepcopy(node))
    namespace = {"__builtins__": __builtins__, "json": json, "Path": ProbePath,
                 "os": fake_os, "signal": fake_signal, "Lock": FakeLock,
                 "monotonic_ns": lambda: 0}
    tree = ast.fix_missing_locations(ast.Module(body=body, type_ignores=[]))
    exec(compile(tree, "unchanged-native-common-selected-AST", "exec"), namespace)
    return namespace


def native_function(name):
    outer = next(node for node in TREES["native_once.py"].body
                 if isinstance(node, ast.FunctionDef) and node.name == "native_run")
    return next(node for node in ast.walk(outer)
                if isinstance(node, ast.FunctionDef) and node.name == name)


class GuardCounterexamples(unittest.TestCase):
    def test_existing_protected_pid_rejects_before_any_proc_read(self):
        namespace = selected_common()
        ProbePath.reads = []
        with self.assertRaises(namespace["ScopeUnknown"]):
            namespace["identity"](4471)
        self.assertEqual(ProbePath.reads, [])

    def test_current_required_protected_pids_reject_before_any_proc_read(self):
        namespace = selected_common()
        inspected = []
        for pid in REQUIRED_PROTECTED:
            ProbePath.reads = []
            try:
                namespace["identity"](pid)
            except namespace["ScopeUnknown"]:
                pass
            except ProbeRead:
                inspected.append({"pid": pid, "first_read": ProbePath.reads[0]})
        self.assertEqual(inspected, [], "actual identity reached fake /proc for protected births")

    def test_outer_signal_subtree_denies_observed_elapsed_after_40s(self):
        calls = []
        fake_signal = SimpleNamespace(SIGTERM=15, SIGKILL=9,
            pidfd_send_signal=lambda fd, signum: calls.append((fd, signum)))
        namespace = selected_common(fake_signal=fake_signal)
        bound = namespace["BoundChild"].__new__(namespace["BoundChild"])
        bound.fd, bound.birth, bound.sent = 777, {"pid": 901}, set()
        bound.verify = lambda: True
        journal = SimpleNamespace(append=lambda *args, **kwargs: None)
        namespace.update(live=[901], tracked={901: bound}, stop=True, elapsed=40.01,
                         term_sent=set(), kill_sent=set(), journal=journal,
                         unknown=lambda *args, **kwargs: None)
        outer = next(node for node in TREES["native_once.py"].body
                     if isinstance(node, ast.FunctionDef) and node.name == "native_run")
        loops = sorted((node for node in ast.walk(outer) if isinstance(node, ast.For)
                        and isinstance(node.target, ast.Name) and node.target.id == "pid"
                        and isinstance(node.iter, ast.Name) and node.iter.id == "live"),
                       key=lambda node: node.lineno)
        tree = ast.fix_missing_locations(ast.Module(body=[deepcopy(loops[0])], type_ignores=[]))
        exec(compile(tree, "unchanged-native-outer-signal-subtree", "exec"), namespace)
        self.assertEqual(calls, [], "actual signal branch sent after already observed 40s")

    def test_signal_guard_rechecks_deadline_after_before_record_fsync(self):
        clock, calls = [39.99], []
        fake_signal = SimpleNamespace(pidfd_send_signal=lambda fd, signum:
                                      calls.append((clock[0], fd, signum)))
        namespace = selected_common(fake_signal=fake_signal)
        bound = namespace["BoundChild"].__new__(namespace["BoundChild"])
        bound.fd, bound.birth, bound.sent = 778, {"pid": 902}, set()
        bound.verify = lambda: True

        def append(event, **values):
            if event == "signal_before":
                clock[0] = 40.02

        namespace["monotonic"] = lambda: clock[0]
        bound.send(15, SimpleNamespace(append=append), reason="synthetic_deadline_crossing")
        self.assertEqual(calls, [], "actual send continues after synthetic pre-signal fsync returns late")

    def test_journal_cap_counts_successful_write_when_fsync_fails(self):
        fake_os = FakeWrites()
        namespace = selected_common(fake_os=fake_os)
        journal = namespace["Journal"].__new__(namespace["Journal"])
        record = {"sequence": 0, "event": "synthetic", "monotonic_ns": 0}
        journal.fd, journal.cap = 11, len(namespace["encode"](record))
        journal.size, journal.sequence, journal.lock = 0, 0, FakeLock()
        with self.assertRaises(OSError):
            journal.append("synthetic")
        try:
            journal.append("synthetic")
        except namespace["ScopeUnknown"]:
            pass
        self.assertLessEqual(fake_os.bytes, journal.cap,
                             "actual append wrote a second allowed record after failed fsync")

    def test_stdio_cap_counts_successful_write_when_fsync_fails(self):
        namespace = selected_common()
        cap = namespace["STDIO_CAP"]
        fake_os = FakeWrites(initial=cap - 64)
        stream = SimpleNamespace(fileno=lambda: 99)
        key = SimpleNamespace(fileobj=stream, data="stdout")
        selector = SimpleNamespace(select=lambda timeout: [(key, None)])
        namespace.update(os=fake_os, selector=selector, output_fds={"stdout": 12},
                         unknown=lambda *args, **kwargs: None)
        drain = deepcopy(native_function("drain"))
        factory = ast.parse("def make_drain():\n stdio_bytes = STDIO_CAP - 64\n pass\n return drain\n").body[0]
        factory.body[1] = drain
        tree = ast.fix_missing_locations(ast.Module(body=[factory], type_ignores=[]))
        exec(compile(tree, "unchanged-native-drain-AST", "exec"), namespace)
        actual_drain = namespace["make_drain"]()
        with self.assertRaises(OSError):
            actual_drain()
        actual_drain()
        self.assertLessEqual(fake_os.bytes, cap,
                             "actual drain wrote beyond cap after successful write and failed fsync")


def main():
    started = monotonic()
    deadline = started + 10

    def budget(frame, event, arg):
        if monotonic() >= deadline:
            os.write(2, b"SYNTHETIC_WALL_BUDGET_EXCEEDED\n")
            os._exit(124)
        return budget

    sys.settrace(budget)
    try:
        affinity = sorted(os.sched_getaffinity(0))
        if affinity != [4]:
            raise RuntimeError("required exact fixture affinity [4]")
        observed = {}
        for name, expected in PINS.items():
            data = (BASE / name).read_bytes()
            observed[name] = hashlib.sha256(data).hexdigest()
            if observed[name] != expected:
                raise RuntimeError("frozen target source changed: " + name)
            TREES[name] = ast.parse(data, filename=name)
        print(json.dumps({"kind": "SYNTHETIC_ACTUAL_SELECTED_AST_NOT_NATIVE", "target_commit": TARGET_COMMIT,
                          "source_sha256": observed, "actual_affinity": affinity,
                          "methods": 6, "attempt": 1}, sort_keys=True), flush=True)
        result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(GuardCounterexamples))
        print(json.dumps({"tests_run": result.testsRun, "failures": len(result.failures),
                          "errors": len(result.errors), "elapsed_seconds": monotonic() - started,
                          "no_native_or_real_proc_signal_pidfd_children_sql": True,
                          "original_seven_methods_not_run": True, "attempt": 1}, sort_keys=True), flush=True)
        return 0 if result.wasSuccessful() else 1
    finally:
        sys.settrace(None)


if __name__ == "__main__":
    raise SystemExit(main())
