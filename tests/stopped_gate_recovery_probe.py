"""Prepare-only by default. A separate explicit GO permits one bounded case.

Uses the original owned_run cleanup implementation, exact kernel SH evidence,
fresh authorities and only their own pidfds. Never opens an existing authority.
"""
from __future__ import annotations

import argparse
import ast
from hashlib import sha256, sha1
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CONTROL_COMMIT = "b02a4e45ec0132e43d0c94fb7c7ab3490d9edea3"
BASE = "e4396b4b1fd9c2e3a138e48a045feffe158705cc"
PROTECTED = {4471, 8784, 310035, 310039, 310266, 310269}
STATE = {"instrumented_diagnostic": True, "original_ci_cause_proven": False,
         "events": [], "trace_truncated": False}


def write(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def source_proof():
    tree = subprocess.check_output(["git", "ls-tree", "-r", CONTROL_COMMIT, "--", "uta"],
                                   cwd=ROOT, text=True)
    hashes = {}
    for line in tree.splitlines():
        header, name = line.split("\t", 1)
        expected = header.split()[2]
        data = (ROOT / name).read_bytes()
        if sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() != expected:
            raise ValueError("runtime bytes moved after fixed control commit")
        hashes[name] = sha256(data).hexdigest()
    helpers = {}
    for name in ("tools/run_managed_variants.py", "tests/test_durable_process.py",
                 "tests/test_durable_faults.py"):
        original = subprocess.check_output(["git", "show", BASE + ":" + name], cwd=ROOT)
        if (ROOT / name).read_bytes() != original:
            raise ValueError("owned cleanup or kernel evidence helper differs from reviewed baseline")
        helpers[name] = sha256(original).hexdigest()
    return {"base": BASE, "control_commit": CONTROL_COMMIT, "runtime_sha256": hashes,
            "helper_sha256": helpers,
            "driver_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
            "test_sha256": sha256((ROOT / "tests/test_spawn_registration_recovery.py").read_bytes()).hexdigest()}


def record(phase, **values):
    if len(STATE["events"]) >= 768:
        STATE["trace_truncated"] = True
        return
    STATE["events"].append({"phase": phase, "monotonic_ns": time.monotonic_ns(),
                            "thread": "monitor" if threading.current_thread().name == "uta-process-supervisor" else "main",
                            **values})


def trace(frame, event, arg):
    name, filename = frame.f_code.co_name, frame.f_code.co_filename
    if name not in {"_spawn", "_supervise", "_record_process", "status", "_lock"}:
        return None
    if not filename.startswith(str(ROOT / "uta") + os.sep):
        return None
    if event == "call" and name in {"_spawn", "_record_process"}:
        record(name + "_call", shard=frame.f_locals.get("shard"))
    elif event == "exception":
        error = arg[1]
        native = getattr(error, "sqlite_errorcode", None) if isinstance(error, sqlite3.Error) else None
        record(name + "_exception", error_type=type(error).__name__,
               sqlite_errorcode=native if type(native) is int else None,
               shard=frame.f_locals.get("shard"))
    elif event == "return" and name == "status" and type(arg) is dict:
        record("lease_status_return", **{key: arg[key] for key in
            ("owner_pid", "generation", "active", "expires_ns", "now_ns") if key in arg})
    elif event == "return" and name in {"_spawn", "_record_process"}:
        record(name + "_return", shard=frame.f_locals.get("shard"))
    elif (event == "line" and name == "_lock" and frame.f_locals.get("exclusive") is True
          and frame.f_lineno in STATE.get("flock_lines", ())):
        record("exclusive_flock_attempt")
    elif event == "line" and name == "_supervise" and frame.f_lineno in STATE.get("supervise_lines", {}):
        process = frame.f_locals.get("process")
        record("monitor_" + STATE["supervise_lines"][frame.f_lineno],
               shard=frame.f_locals.get("shard"), pid=getattr(process, "pid", None))
    return trace


def inner(output, case):
    from tests.test_spawn_registration_recovery import NativeSpawnRegistrationTests
    from tests.test_durable_process import DurableProcessTests
    from tests.test_durable_faults import bound_router_shared_flocks
    from uta.durable_process import _process_identity
    from uta.writer_fence import WriterFence
    output = Path(output)
    proof = source_proof()
    write(output / "inner-source-proof.json", proof)
    NativeSpawnRegistrationTests._artifact_root = output / "native"
    sharding = ROOT / "uta/sharding.py"
    module = ast.parse(sharding.read_text())
    STATE["flock_lines"] = [node.lineno for node in ast.walk(module)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr == "flock"]
    process_module = ast.parse((ROOT / "uta/durable_process.py").read_text())
    supervisor = next(node for node in ast.walk(process_module)
                      if isinstance(node, ast.FunctionDef) and node.name == "_supervise")
    STATE["supervise_lines"] = {node.lineno: node.func.attr for node in ast.walk(supervisor)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"kill", "join", "_spawn"}}
    class KernelGateCase(DurableProcessTests):
        def test_one_pinned_actual_sh_holder(self):
            self.activate()
            observer = self.router._database(0)
            observer.timeout = .1
            with self.router._mutex:
                process = self.router._workers[0][0]
                if not process.is_alive():
                    raise RuntimeError("UNKNOWN: selected new child exited")
                pid, identity = process.pid, _process_identity(process.pid)
                if pid in PROTECTED:
                    raise RuntimeError("protected PID is never a probe target")
                pidfd = os.pidfd_open(pid)
            self.addCleanup(os.close, pidfd)
            current = _process_identity(pid)
            self.assertTrue(all(current[k] == identity[k] for k in ("pid", "start_ticks", "boot_id", "uid")))
            lock = self.path / "router.lock"
            info = lock.stat(follow_symlinks=False)
            file_id = info.st_dev, info.st_ino
            connection = sqlite3.connect(observer.path, isolation_level=None)
            self.addCleanup(connection.close)
            connection.execute("BEGIN IMMEDIATE")
            capture_until = time.monotonic() + 1
            candidate = []
            while time.monotonic() < capture_until:
                lease = WriterFence(observer).status()
                if lease["owner_pid"] != pid or not lease["active"]:
                    raise RuntimeError("UNKNOWN: original target lease moved during capture")
                candidate = bound_router_shared_flocks(pid, identity, lock, file_id)
                if candidate:
                    break
                time.sleep(.001)
            if not candidate:
                raise RuntimeError("UNKNOWN: no exact new child's kernel SH capture")
            record("bound_sh_before_stop", pid=pid, start_ticks=identity["start_ticks"],
                   generation=lease["generation"], kernel_sh_count=len(candidate))
            signal.pidfd_send_signal(pidfd, signal.SIGSTOP)
            stopped_until = time.monotonic() + .2
            while time.monotonic() < stopped_until and _process_identity(pid)["state"] != "T":
                time.sleep(.001)
            self.assertEqual(_process_identity(pid)["state"], "T")
            retained = bound_router_shared_flocks(pid, identity, lock, file_id)
            if not retained:
                raise RuntimeError("UNKNOWN: stopped child did not retain exact SH; no recapture")
            record("bound_sh_retained_after_stop", pid=pid, kernel_sh_count=len(retained))
            connection.rollback()
            started = time.monotonic()
            publication = self.router.publish_market(self.market(2), timeout=4)
            record("publication_return", elapsed_seconds=time.monotonic() - started,
                   publishing=publication["publishing"], halted=publication["halted"])
            self.assertFalse(publication["publishing"])
            self.eventually(lambda: self.router.worker_pid(0) not in (None, pid), timeout=4)
    suite = unittest.TestSuite()
    if case in {"registry", "all"}:
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(NativeSpawnRegistrationTests))
    if case in {"gate", "all"}:
        suite.addTest(KernelGateCase("test_one_pinned_actual_sh_holder"))
    def deadline(signum, frame):
        raise TimeoutError("inner diagnostic budget expired; outcome UNKNOWN")
    signal.signal(signal.SIGALRM, deadline)
    signal.setitimer(signal.ITIMER_REAL, 15)
    sys.settrace(trace)
    threading.settrace(trace)
    try:
        result = unittest.TextTestRunner(verbosity=2, failfast=True).run(suite)
    finally:
        sys.settrace(None)
        threading.settrace(None)
        signal.setitimer(signal.ITIMER_REAL, 0)
        STATE.pop("flock_lines", None)
        STATE.pop("supervise_lines", None)
        write(output / "trace.json", STATE)
    write(output / "inner-result.json", {"tests_run": result.testsRun, "failures": len(result.failures),
        "errors": len(result.errors), "passed": result.wasSuccessful(),
        "instrumented_diagnostic": True, "original_ci_cause_proven": False,
        "production_approved": False})
    return 0 if result.wasSuccessful() else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--inner", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--case", choices=("registry", "gate", "all"), default="registry")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cpu", type=int, default=1)
    args = parser.parse_args()
    if args.inner:
        return inner(args.output, args.case)
    proof = source_proof()
    if not args.execute:
        print(json.dumps({"prepare_only": True, "case": args.case, "cpu_ids": [args.cpu],
            "inner_seconds": 15, "owned_wall_seconds": 20, "outer_budget_including_reap_seconds": 30,
            "sql_or_signals_executed": False, "source": proof}, indent=2))
        return 0
    if args.output is None or not args.output.is_absolute() or ROOT == args.output or ROOT in args.output.parents:
        raise ValueError("new absolute private output outside checkout is required")
    args.output.mkdir(parents=True, mode=0o700, exist_ok=False)
    from tools.run_managed_variants import owned_run
    from tests.test_durable_process import _orphan_reaper
    write(args.output / "source-proof.json", proof)
    with _orphan_reaper():
        outcome = owned_run([sys.executable, "-B", str(Path(__file__)), "--inner", "--case", args.case,
            "--output", str(args.output)], str(ROOT), args.output / "native",
            cpu_ids=[args.cpu], wall_seconds=20, grace_seconds=1, kill_wait_seconds=1,
            output_cap=512 * 1024, protected=PROTECTED)
    write(args.output / "ownership-outcome.json", outcome)
    print(json.dumps({"outcome": outcome["outcome"], "returncode": outcome["returncode"],
        "wall_seconds": outcome["wall_seconds"], "instrumented_diagnostic": True,
        "production_approved": False}))
    return 0 if outcome["outcome"] == "EXITED" and outcome["returncode"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
