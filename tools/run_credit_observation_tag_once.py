"""One explicitly authorized in-memory credit-artifact/tag suite, never SQL.

The caller binds actual Git/argv/exit/reap and supplies the hard20s/CPU1 envelope.
Target imports execute only retained verified bytes. This is trusted-source
verification, not an OS sandbox, native-library attestation or financial gate.
"""
import argparse
from hashlib import sha256
import importlib.abc
import importlib.util
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
RAW_LIMIT, TRAILER_RESERVE = 262144, 512
RAW_RESERVED = 0


class RawStream:
    encoding, errors = "utf-8", "backslashreplace"

    def __init__(self, descriptor):
        self.descriptor = descriptor

    def write(self, text):
        global RAW_RESERVED
        raw = text.encode(self.encoding, self.errors)
        if RAW_RESERVED + len(raw) > RAW_LIMIT - TRAILER_RESERVE:
            fail_raw()
        RAW_RESERVED += len(raw)
        while raw:
            try:
                count = os.write(self.descriptor, raw)
                if type(count) is not int or not 0 < count <= len(raw):
                    raise OSError("invalid raw write")
                raw = raw[count:]
            except BaseException:
                fail_raw()
        return len(text)

    def flush(self):
        pass


def fail_raw():
    try:
        os.write(2, b'\n{"event":"CREDIT_TAG_RAW_UNKNOWN","complete":false,"exit":125}\n')
    finally:
        os._exit(125)  # This interpreter has no target children.


def read_regular(path, limit=2 * 1024 * 1024):
    if path.resolve() != path or not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError("input is not a materialized canonical regular file")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as handle:
        before = os.fstat(handle.fileno())
        raw = handle.read(limit + 1)
        after = os.fstat(handle.fileno())
    keys = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    if len(raw) > limit or any(getattr(before, key) != getattr(after, key) for key in keys):
        raise ValueError("input exceeds bound or changed while read")
    return raw


def exclusive(path, value):
    raw = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    if len(raw) > 1024 * 1024:
        raise ValueError("control record exceeds bound")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def inputs(plan):
    frozen = {}
    for name, expected in plan["input_files"].items():
        if name.startswith("/") or ".." in Path(name).parts:
            raise ValueError("input path escapes checkout")
        raw = read_regular(ROOT / name)
        if {"bytes": len(raw), "sha256": sha256(raw).hexdigest()} != expected:
            raise ValueError("input pin mismatch: " + name)
        frozen[name] = raw
    return frozen


class FrozenLoader(importlib.abc.Loader):
    def __init__(self, name, path, frozen):
        self.name, self.path, self.frozen = name, path, frozen

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        exec(compile(self.frozen[self.path], str(ROOT / self.path), "exec"), module.__dict__)


class FrozenUTA(importlib.abc.MetaPathFinder):
    def __init__(self, frozen):
        self.frozen = frozen

    def find_spec(self, fullname, path=None, target=None):
        if fullname != "uta" and not fullname.startswith("uta."):
            return None
        name = "uta/__init__.py" if fullname == "uta" else fullname.replace(".", "/") + ".py"
        if name not in self.frozen:
            raise ImportError("unretained UTA module: " + fullname)
        return importlib.util.spec_from_file_location(fullname, ROOT / name,
            loader=FrozenLoader(fullname, name, self.frozen),
            submodule_search_locations=[str(ROOT / "uta")] if fullname == "uta" else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--private-directory", required=True, type=Path)
    args = parser.parse_args()
    output = args.private_directory
    if not output.is_absolute() or output.resolve() != output:
        raise ValueError("private output must be a new canonical absolute directory")
    output.mkdir(mode=0o700)
    for descriptor, name in ((1, "first.stdout.txt"), (2, "first.stderr.txt")):
        target = os.open(output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        os.dup2(target, descriptor)
        os.close(target)
    sys.stdout, sys.stderr = RawStream(1), RawStream(2)
    plan_path = ROOT / "evidence/reviews/credit-observation-tag/once-plan.json"
    raw = read_regular(plan_path)
    if sha256(raw).hexdigest() != args.plan_sha256:
        raise ValueError("unapproved plan")
    plan = json.loads(raw)
    frozen = inputs(plan)
    executable = Path(sys.executable).resolve()
    binary = read_regular(executable, 64 * 1024 * 1024)
    runtime = {"sys_executable": sys.executable, "resolved_executable": str(executable),
        "executable_bytes": len(binary), "executable_sha256": sha256(binary).hexdigest(),
        "sys_version": sys.version, "affinity": sorted(os.sched_getaffinity(0)),
        "flags": {"isolated": sys.flags.isolated, "no_site": sys.flags.no_site,
                  "dont_write_bytecode": sys.flags.dont_write_bytecode}}
    if runtime != plan["expected_runtime"]:
        raise ValueError("runtime/CPU differs from plan")
    if any(name == "uta" or name.startswith("uta.") for name in sys.modules):
        raise ValueError("target module preloaded outside frozen loader")
    exclusive(output / "intent.json", {"source_commit_invoker_label": args.source_commit,
        "plan_sha256": args.plan_sha256, "input_files": plan["input_files"], "runtime": runtime,
        "requires_actual_caller_Git_argv_exit_reap": True})
    forbidden = []
    def audit(event, arguments):
        if event in {"sqlite3.connect", "subprocess.Popen", "os.fork", "os.forkpty", "os.exec",
                     "os.posix_spawn", "os.system", "os.kill", "os.killpg", "socket.__new__"}:
            forbidden.append(event)
            raise RuntimeError("out-of-scope operation: " + event)
        if event == "open" and arguments and isinstance(arguments[0], (str, bytes)):
            name = os.fsdecode(arguments[0])
            if name.startswith("/proc/") or name.endswith((".sqlite", ".sqlite3", ".db", "-wal", "-shm")):
                forbidden.append("open:authority_or_proc")
                raise RuntimeError("out-of-scope authority/process read")
    def no_thread(*arguments, **keywords):
        forbidden.append("thread_start")
        raise RuntimeError("target thread start forbidden")
    sys.addaudithook(audit)
    threading.Thread.start = no_thread
    finder = FrozenUTA(frozen)
    sys.meta_path.insert(0, finder)
    namespace = ModuleType("credit_observation_tag_once")
    namespace.__file__ = str(ROOT / "tests/test_credit_lease_observation_tag.py")
    namespace.__dict__["_FROZEN_VALIDATION_SOURCE"] = frozen["tools/run_validation.py"]
    sys.modules[namespace.__name__] = namespace
    print(json.dumps({"event": "CREDIT_TAG_BEGIN", "source_commit": args.source_commit,
        "runtime": runtime, "selected_methods": plan["methods"], "input_count": len(frozen)}), flush=True)
    started = time.monotonic_ns()
    exec(compile(frozen["tests/test_credit_lease_observation_tag.py"], namespace.__file__, "exec"), namespace.__dict__)
    case = namespace.LeaseObservationTagArtifactTests
    result = unittest.TextTestRunner(stream=sys.stderr, verbosity=2).run(unittest.TestSuite(
        case(name) for name in plan["methods"]))
    elapsed = time.monotonic_ns() - started
    after = inputs(plan)
    plan_after = read_regular(plan_path)
    unchanged = frozen == after and raw == plan_after
    passed = (result.testsRun == 6 and result.wasSuccessful() and not result.skipped
              and not result.expectedFailures and not result.unexpectedSuccesses and unchanged and not forbidden)
    receipt = {"source_commit_invoker_label": args.source_commit, "runtime": runtime,
        "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
        "skipped": len(result.skipped), "elapsed_ns": elapsed, "input_pins_after": plan["input_files"],
        "source_before_after_equal": unchanged, "forbidden_attempts": forbidden,
        "raw_reserved_before_END": RAW_RESERVED, "returncode": 0 if passed else 1,
        "SQL_workers_network_financial_production_approved": False}
    exclusive(output / "execution.json", receipt)
    print(json.dumps({"event": "CREDIT_TAG_END", **receipt}), flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
