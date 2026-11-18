"""Selected-AST test support. No target module or native capability is imported."""
import ast
from copy import deepcopy
import json
import math
from pathlib import Path
from types import SimpleNamespace

BASE = Path(__file__).resolve().parents[1]
TREES = {}


class FakeLock:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class ProbePath:
    reads = []

    def __init__(self, value):
        self.value = str(value)

    def __truediv__(self, value):
        return ProbePath(self.value + "/" + str(value))

    def read_text(self):
        self.reads.append(self.value)
        raise AssertionError("unexpected fake proc read")

    def iterdir(self):
        self.reads.append(self.value)
        raise AssertionError("unexpected fake proc enumeration")


class FakeWrites:
    def __init__(self, *, initial=0, chunk=b"x" * 64, partial=False):
        self.bytes, self.chunk, self.partial = initial, chunk, partial
        self.write_calls, self.fsync_calls = 0, 0

    def write(self, fd, data):
        self.write_calls += 1
        if self.partial and self.write_calls == 2:
            raise OSError("synthetic EIO after partial write")
        size = max(1, len(data) // 2) if self.partial else len(data)
        self.bytes += size
        return size

    def fsync(self, fd):
        self.fsync_calls += 1
        if self.fsync_calls == 1:
            raise OSError("synthetic EIO after complete write")

    def read(self, fd, size):
        return self.chunk


def selected_common(*, fake_os=None, fake_signal=None, clock=None):
    names = {"PROTECTED_PIDS", "STDIO_CAP", "BIRTH_FIELDS", "ScopeUnknown", "require_before",
             "require_unprotected_pid", "encode", "_write_all", "Journal", "identity",
             "children_of", "same_birth", "BoundChild"}
    body = []
    for node in TREES["native_once_common.py"].body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names:
            body.append(deepcopy(node))
        elif isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id in names
                                                 for target in node.targets):
            body.append(deepcopy(node))
    clock = [0.0] if clock is None else clock
    namespace = {"__builtins__": __builtins__, "json": json, "math": math, "Path": ProbePath,
        "os": fake_os, "signal": fake_signal, "Lock": FakeLock,
        "monotonic": lambda: clock[0], "monotonic_ns": lambda: int(clock[0] * 1000000000)}
    exec(compile(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])),
                 "new-native-common-selected-AST", "exec"), namespace)
    return namespace


def native_run_tree():
    return next(node for node in TREES["native_once.py"].body
                if isinstance(node, ast.FunctionDef) and node.name == "native_run")


def run_nodes(nodes, namespace, label):
    exec(compile(ast.fix_missing_locations(ast.Module(body=deepcopy(nodes), type_ignores=[])),
                 label, "exec"), namespace)


def selected_drain(namespace, *, initial):
    drain = next(node for node in ast.walk(native_run_tree())
                 if isinstance(node, ast.FunctionDef) and node.name == "drain")
    factory = ast.parse("def make_drain():\n stdio_bytes = INITIAL\n stdio_failed = False\n stdio_eof = set()\n pass\n def snapshot():\n  return stdio_bytes, stdio_failed, set(stdio_eof)\n return drain, snapshot\n").body[0]
    factory.body[3] = deepcopy(drain)
    namespace["INITIAL"] = initial
    run_nodes([factory], namespace, "new-native-drain-selected-AST")
    return namespace["make_drain"]()
