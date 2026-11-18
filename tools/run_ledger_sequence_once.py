"""One bounded, pure reference-ledger run, only after root's exact once GO.

The invoker owns timeout/taskset and records actual host exit and reap. This
driver starts no process, thread, network client or database. Its source-commit
argument is a label checked against Git by the invoker, not an election proof.
"""
import argparse
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
            while raw:
                written = os.write(self.fd, raw)
                if written <= 0:
                    raise OSError("short write")
                raw = raw[written:]
        except BaseException:
            fail_raw()
        return len(text)

    def flush(self):
        return None


def fail_raw():
    try:
        os.write(2, b'\n{"event":"LEDGER_SEQUENCE_RAW_UNKNOWN","complete":false,"exit":125}\n')
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
    plan_path = ROOT / "evidence/reviews/ledger-sequence-integrity/once-plan.json"
    plan_raw = read_regular(plan_path)
    if sha256(plan_raw).hexdigest() != args.plan_sha256:
        raise ValueError("plan SHA mismatch")
    plan = json.loads(plan_raw)
    frozen = frozen_inputs(plan)
    executable = Path(sys.executable).resolve()
    binary = read_regular(executable, 64 * 1024 * 1024)
    runtime = {"sys_version": sys.version, "sys_executable": sys.executable,
               "resolved_executable": str(executable), "executable_bytes": len(binary),
               "executable_sha256": sha256(binary).hexdigest(),
               "affinity": sorted(os.sched_getaffinity(0)),
               "flags": {"isolated": sys.flags.isolated, "no_site": sys.flags.no_site,
                         "dont_write_bytecode": sys.flags.dont_write_bytecode}}
    if runtime != plan["expected_runtime"]:
        raise ValueError("actual runtime/CPU differs from approved plan")
    exclusive(output / "intent.json", {"source_commit_invoker_label": args.source_commit,
        "plan_sha256": args.plan_sha256, "runtime": runtime, "input_files": plan["input_files"],
        "planned_methods": 4, "production_approved": False})
    # The standard imports below resolve uta.ledger only from these verified bytes.
    package = ModuleType("uta")
    package.__path__ = []
    sys.modules["uta"] = package
    ledger = ModuleType("uta.ledger")
    ledger.__file__ = str(ROOT / "uta/ledger.py")
    sys.modules["uta.ledger"] = ledger
    fixture = ModuleType("ledger_sequence_fixture")
    fixture.__file__ = str(ROOT / "tests/test_ledger_sequence_integrity.py")
    sys.modules[fixture.__name__] = fixture
    print(json.dumps({"event": "LEDGER_SEQUENCE_BEGIN", "methods": 4, "runtime": runtime}, sort_keys=True))
    started = time.monotonic_ns()
    exec(compile(frozen["uta/ledger.py"], ledger.__file__, "exec"), ledger.__dict__)
    exec(compile(frozen["tests/test_ledger_sequence_integrity.py"], fixture.__file__, "exec"), fixture.__dict__)
    selected = plan["methods"]
    suite = unittest.TestSuite(fixture.LedgerSequenceIntegrityTests(name) for name in selected)
    result = unittest.TextTestRunner(stream=sys.stderr, verbosity=2).run(suite)
    elapsed = time.monotonic_ns() - started
    after = frozen_inputs(plan)
    if after != frozen or read_regular(plan_path) != plan_raw:
        raise ValueError("source or plan changed during execution")
    passed = (result.testsRun == 4 and result.wasSuccessful() and not result.skipped
              and not result.expectedFailures and not result.unexpectedSuccesses)
    receipt = {"complete": True, "tests_run": result.testsRun, "failures": len(result.failures),
        "errors": len(result.errors), "skipped": len(result.skipped), "passed": passed,
        "source_unchanged": True, "runtime": runtime, "elapsed_ns": elapsed,
        "source_commit_invoker_label": args.source_commit, "plan_sha256": args.plan_sha256,
        "raw_reserved_bytes_before_END": RAW["reserved"], "production_approved": False}
    exclusive(output / "first.execution.json", receipt)
    print(json.dumps({"event": "LEDGER_SEQUENCE_END", **receipt}, sort_keys=True))
    os.fsync(1)
    os.fsync(2)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
