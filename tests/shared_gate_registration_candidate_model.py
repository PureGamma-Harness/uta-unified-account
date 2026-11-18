"""Candidate-only finite model. Requires a new explicit run budget.

The first base RED artifact and its driver are inputs, never rerun or rewritten.
"""
from contextlib import contextmanager, ExitStack
from hashlib import sha256
import json
import multiprocessing.process
import os
from pathlib import Path
import signal
import sqlite3
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch


SOURCE_SHA256 = "f2093101f7b7cf5eaa5604639a3892bcb0fd37f7421e171e242f6157416019ca"
HELPER_SHA256 = "58134735a8a25d84fbb566316ff4b163fa3e9f4013d56c4d1d55738a8d3df3b3"
BASE_RESULT_SHA256 = "12ff60d87c5503ab947f243a3e3d021b2ecb742610119c4b69b0dd1de20641da"


class HookedDB:
    """In-memory subclass whose transaction is the only overridden DB hook."""
    def __init__(self, timeout):
        self.timeout, self.path = timeout, "/model-not-created"
        self._writer_token, self._fence_clock_ns, self._fence_boot_id = object(), object(), "model-boot"
        self.state = {"entries": [], "appends": []}

    @contextmanager
    def transaction(self):
        self.state["entries"].append(self)
        yield SimpleNamespace(execute=lambda sql, args: self.state["appends"].append(args))


def direct_record(ns, kind, original_timeout):
    database = HookedDB(original_timeout)
    control = SimpleNamespace(control=database, _descriptor="model-layout")
    identity = {"pid": 900_100, "start_ticks": 7, "boot_id": "model-boot"}
    shard = None if kind == "COORDINATOR" else 1
    ns["_record_process"](control, kind, shard, "model-nonce", 2, identity, "model-coordinator")
    if len(database.state["entries"]) != 1 or len(database.state["appends"]) != 1:
        raise AssertionError("registration did not invoke exactly one transaction/append")
    used = database.state["entries"][0]
    if database.timeout != original_timeout:
        raise AssertionError("registration mutated the shared original timeout")
    if type(used) is not type(database) or used.state is not database.state:
        raise AssertionError("shallow copy changed subclass or model hook state")
    for name in ("path", "_writer_token", "_fence_clock_ns", "_fence_boot_id"):
        if getattr(used, name) is not getattr(database, name):
            raise AssertionError("shallow copy lost an original database field")
    expected = min(original_timeout, .1) if kind == "SPAWNED" else original_timeout
    if used.timeout != expected or (used is database) != (kind != "SPAWNED"):
        raise AssertionError("SPAWNED-only copy/busy budget contract changed")
    appended = database.state["appends"][0]
    if (appended[0], appended[2], appended[3], appended[4], appended[5]) != (
            kind, shard, "model-nonce", 2, identity["pid"]):
        raise AssertionError("registry append metadata changed")
    return {"kind": kind, "original_timeout": original_timeout,
            "connection_busy_budget": used.timeout, "original_unchanged": True,
            "subclass_hook_and_fields_preserved": True, "one_append_only": True}


def main():
    root = Path(__file__).resolve().parents[1]
    source = (root / "uta/durable_process.py").read_bytes()
    helper = root / "tests/shared_gate_registration_model.py"
    baseline = root / "evidence/shared-gate-recovery/baseline-first/stdout.json"
    if (sha256(source).hexdigest() != SOURCE_SHA256
            or sha256(helper.read_bytes()).hexdigest() != HELPER_SHA256
            or sha256(baseline.read_bytes()).hexdigest() != BASE_RESULT_SHA256):
        raise AssertionError("candidate, base driver, or first base result identity changed")
    import shared_gate_registration_model as model
    base = json.loads(baseline.read_bytes())
    guards = [(sqlite3, "connect"), (multiprocessing.process.BaseProcess, "start"),
              (os, "kill"), (threading.Thread, "start"), (time, "sleep")]
    if hasattr(signal, "pidfd_send_signal"):
        guards.append((signal, "pidfd_send_signal"))
    with ExitStack() as stack:
        for owner, name in guards:
            stack.enter_context(patch.object(owner, name, model.forbidden))
        ns, ast_digests = model.load_actual_methods(source)
        if set(ast_digests) != set(base["actual_ast_sha256"]):
            raise AssertionError("candidate extracted a different actual method inventory")
        for name, digest in ast_digests.items():
            if name != "_record_process" and digest != base["actual_ast_sha256"][name]:
                raise AssertionError("candidate changed an additional actual method")
        scenarios = []
        for row in base["scenarios"]:
            scenarios.append(model.scenario(ns, order=row["order"], error_code=row["native_code_modeled"],
                lost_reply=row["lost_reply_modeled"], cleanup_stuck=row["cleanup_stuck_modeled"],
                lease=row["lease_modeled"], expiry=row["expiry_virtual_seconds"]))
        if any(row["recovery_deadline_missed"] for row in scenarios):
            raise AssertionError("candidate retains the conditional registry-starvation witness")
        direct = [direct_record(ns, kind, timeout)
                  for kind in ("SPAWNED", "OWNED", "COORDINATOR", "ORPHAN_KILLED")
                  for timeout in (10.0, .025)]
    model.bounded()
    print(json.dumps({"event": "shared_gate_registration_candidate_actual_ast_model_v1",
        "source_sha256": SOURCE_SHA256, "driver_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "base_driver_sha256": HELPER_SHA256, "first_base_result_sha256": BASE_RESULT_SHA256,
        "actual_ast_sha256": ast_digests, "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "result": "MODELED_BOUNDARY_PASS", "scenario_count": len(scenarios) + len(direct),
        "harness_checks_passed": True, "native_executed": False,
        "original_ci_cause_proven": False, "production_approved": False,
        "virtual_time_is_not_native_elapsed_time": True,
        "busy_timeout_is_not_hard_realtime_guarantee": True,
        "conflict_latency_equal_to_timeout_is_a_model_assumption": True,
        "scenarios": scenarios, "direct_record_checks": direct}, sort_keys=True))


if __name__ == "__main__":
    main()
