"""Finite actual-method model; never a native recovery or CI-cause claim.

Execute only with an explicit per-run budget. No runtime module is imported.
The SHA argument pins the exact source whose selected AST methods are executed.
"""
from __future__ import annotations

import argparse
import ast
from contextlib import contextmanager, ExitStack
from copy import copy
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


BASE_SHA256 = "46905e06af8e6ee12e16b71ad6ebce50847a7d77c03c1e7fb3e73fd165897219"
METHODS = ("_spawn", "_cleanup_gated_spawn", "_note_spawn_failure", "_supervise")
TOP_LEVEL = ("_SpawnRegistrationFailure", "_retryable_spawn_registration", "_authority",
             "_record_process", "_SignalReceiver", "_SignalSender")
WALL_DEADLINE = time.monotonic() + 9


def bounded():
    if time.monotonic() >= WALL_DEADLINE:
        raise AssertionError("pure-model wall budget exhausted")


def forbidden(*args, **kwargs):
    raise AssertionError("pure model attempted a native side effect")


class ModelServiceError(Exception):
    def __init__(self, code, message, status=400):
        self.code = code
        super().__init__(message)


class Clock:
    def __init__(self):
        self.now, self.events, self.nonces = 0.0, [], 0

    def advance(self, value):
        bounded()
        self.now += value

    def event(self, kind, **values):
        self.events.append({"at": round(self.now, 6), "kind": kind, **values})
        if len(self.events) > 128:
            raise AssertionError("model trace exceeded finite event cap")

    def uuid(self):
        self.nonces += 1
        return SimpleNamespace(hex="model-nonce-" + str(self.nonces))


class ModelDB:
    def __init__(self, clock, error_code, lost_reply, *, timeout=10.0):
        self.clock, self.error_code, self.lost_reply = clock, error_code, lost_reply
        self.timeout, self.shared = timeout, {"attempts": [], "appends": []}

    @contextmanager
    def transaction(self):
        self.shared["attempts"].append(self.timeout)
        if self.lost_reply:
            yield self
        self.clock.advance(self.timeout)
        self.clock.event("registry_conflict_return", busy_budget=self.timeout,
                         modeled_append=self.lost_reply, native_code=self.error_code)
        error = sqlite3.OperationalError("modeled registry conflict")
        error.sqlite_errorcode = self.error_code
        raise error

    def execute(self, sql, values):
        self.shared["appends"].append((values[0], values[2], values[3]))


class Wire:
    def __init__(self):
        self.messages = []


class Connection:
    def __init__(self, wire):
        self.wire, self.closed = wire, False

    def send_bytes(self, value):
        self.wire.messages.append(value)

    def recv_bytes(self):
        return self.wire.messages.pop(0)

    def poll(self, timeout=0):
        return bool(self.wire.messages)

    def close(self):
        self.closed = True


class ModelProcess:
    def __init__(self, context, args, name):
        self.context, self.args, self.name = context, args, name
        self.pid, self.alive, self.closed = None, False, False
        self.is_selected = False

    def start(self):
        self.pid = 900_000 + len(self.context.processes)
        self.alive = True
        self.context.clock.event("gated_model_child_started", pid=self.pid)

    def is_alive(self):
        return self.alive

    def join(self, timeout=None):
        if self.alive and not self.context.cleanup_stuck and self.args[3].is_set():
            self.alive = False

    def kill(self):
        clock = self.context.clock
        if self.is_selected:
            clock.event("selected_model_kill", lease_expiry=self.context.expiry)
            self.alive = False
        elif not self.context.cleanup_stuck:
            self.alive = False

    def close(self):
        if self.alive:
            raise AssertionError("model closed a still-live child")
        self.closed = True


class Context:
    def __init__(self, clock, *, cleanup_stuck=False, expiry=.25):
        self.clock, self.cleanup_stuck, self.expiry = clock, cleanup_stuck, expiry
        self.processes, self.gate_wires = [], []
        self.pipe_count = 0

    def Pipe(self, duplex=False):
        wire = Wire()
        self.pipe_count += 1
        if self.pipe_count % 3 == 2:
            self.gate_wires.append(wire)
        return Connection(wire), Connection(wire)

    def Process(self, *, target, args, name):
        process = ModelProcess(self, args, name)
        self.processes.append(process)
        return process


class Stop:
    def __init__(self, clock):
        self.clock, self.turns = clock, 0

    def wait(self, timeout):
        self.clock.advance(timeout)
        self.turns += 1
        return self.turns > 4

    def is_set(self):
        return False


def load_actual_methods(source):
    tree = ast.parse(source)
    original_class = next(node for node in tree.body
                          if isinstance(node, ast.ClassDef) and node.name == "DurableProcessRouter")
    methods = [node for node in original_class.body
               if isinstance(node, ast.FunctionDef) and node.name in METHODS]
    definitions = [node for node in tree.body
                   if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in TOP_LEVEL]
    if len(methods) != len(METHODS) or len(definitions) != len(TOP_LEVEL):
        raise AssertionError("actual method inventory changed")
    definitions.append(ast.ClassDef(name="ActualRouter", bases=[], keywords=[],
                                    body=methods, decorator_list=[]))
    module = ast.fix_missing_locations(ast.Module(body=definitions, type_ignores=[]))
    ns = {"ServiceError": ModelServiceError, "sha256": sha256, "sqlite3": sqlite3,
          "copy": copy, "_run_worker": forbidden,
          "datetime": SimpleNamespace(now=lambda zone: SimpleNamespace(isoformat=lambda: "model-time")),
          "timezone": SimpleNamespace(utc=None)}
    exec(compile(module, "<actual-reviewed-runtime-ast>", "exec"), ns)
    ast_digests = {node.name: sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
                   for node in [*methods, *definitions[:-1]]}
    return ns, ast_digests


def scenario(ns, *, order, error_code, lost_reply=False, cleanup_stuck=False,
             lease="matching", expiry=.25):
    bounded()
    clock = Clock()
    context = Context(clock, cleanup_stuck=cleanup_stuck, expiry=expiry)
    db = ModelDB(clock, error_code, lost_reply)
    router = ns["ActualRouter"].__new__(ns["ActualRouter"])
    router.directory, router._settings = Path("/model-not-created"), {}
    router._context, router._coordinator = context, "model-coordinator"
    router._control = SimpleNamespace(control=db, _descriptor="model-layout")
    router._workers, router._start_gates, router._reports = {}, {}, {}
    router._spawn_retry_at, router._spawn_failures = {}, {}
    router._spawn_blocked, router._spawn_pending_cleanup = set(), {}
    router._mutex, router._stop = ExitStack(), Stop(clock)
    selected = ModelProcess(context, (None,) * 9, "selected")
    selected.pid, selected.alive, selected.is_selected = 800_000, True, True
    dead = ModelProcess(context, (None,) * 9, "dead-sibling")
    dead.pid = 800_001
    router._database = lambda shard: SimpleNamespace(timeout=10, shard=shard)
    for shard in ((0, 1) if order == "held_first" else (1, 0)):
        if shard == 1 and order == "retry_first":
            router._spawn_retry_at[1] = 0
            continue
        router._workers[shard] = (selected if shard == 0 else dead,
                                 SimpleNamespace(close=lambda: None), Connection(Wire()))
        router._start_gates[shard] = SimpleNamespace(close=lambda: None)

    def lease_status(database):
        if lease == "unknown":
            raise sqlite3.OperationalError("modeled unknown lease")
        owner_pid = selected.pid if lease == "matching" else selected.pid + 99
        return {"owner_pid": owner_pid, "active": clock.now < expiry}

    ns.update(monotonic=lambda: clock.now, uuid4=clock.uuid,
              os=SimpleNamespace(getpid=lambda: 700_000),
              _process_identity=lambda pid: {"pid": pid, "start_ticks": 1,
                                            "boot_id": "model-boot", "uid": 1},
              WriterFence=lambda database: SimpleNamespace(status=lambda: lease_status(database)))
    router._supervise()
    kills = [row for row in clock.events if row["kind"] == "selected_model_kill"]
    if lease == "matching":
        if not kills or kills[0]["at"] < expiry:
            raise AssertionError("matching expired model owner was not killed safely")
    elif kills:
        raise AssertionError("unknown or mismatched lease authorized a kill")
    if db.timeout != 10:
        raise AssertionError("shared control database timeout changed")
    if any(wire.messages for wire in context.gate_wires):
        raise AssertionError("failed registry attempt released a child gate")
    appends = db.shared["appends"]
    if len({nonce for _, _, nonce in appends}) != len(appends):
        raise AssertionError("uncertain model append nonce was retried")
    if cleanup_stuck and (1 not in router._spawn_pending_cleanup or 1 not in router._spawn_blocked):
        raise AssertionError("unconfirmed cleanup permitted sibling replacement")
    if any(value["registration_outcome"] != "UNKNOWN" for value in router._spawn_failures.values()):
        raise AssertionError("model conflict falsely claimed an append outcome")
    return {"order": order, "native_code_modeled": error_code, "lost_reply_modeled": lost_reply,
            "cleanup_stuck_modeled": cleanup_stuck, "lease_modeled": lease,
            "expiry_virtual_seconds": expiry, "old_kill_virtual_seconds": kills[0]["at"] if kills else None,
            "recovery_deadline_missed": bool(kills and kills[0]["at"] > 5),
            "registry_busy_budgets": db.shared["attempts"],
            "model_append_count": len(appends), "events": clock.events}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-sha256", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = (root / "uta/durable_process.py").read_bytes()
    digest = sha256(source).hexdigest()
    if digest != args.source_sha256:
        raise AssertionError("source bytes do not match frozen run identity")
    guards = [(sqlite3, "connect"), (multiprocessing.process.BaseProcess, "start"),
              (os, "kill"), (threading.Thread, "start"), (time, "sleep")]
    if hasattr(signal, "pidfd_send_signal"):
        guards.append((signal, "pidfd_send_signal"))
    with ExitStack() as stack:
        for owner, name in guards:
            stack.enter_context(patch.object(owner, name, forbidden))
        ns, ast_digests = load_actual_methods(source)
        scenarios = []
        for order in ("held_first", "dead_first", "retry_first"):
            for code in (5, 6, 15):
                scenarios.append(scenario(ns, order=order, error_code=code))
        for lost_reply in (False, True):
            for stuck in (False, True):
                scenarios.append(scenario(ns, order="held_first", error_code=5,
                                          lost_reply=lost_reply, cleanup_stuck=stuck))
        for lease in ("unknown", "mismatched"):
            scenarios.append(scenario(ns, order="held_first", error_code=5, lease=lease))
        scenarios.append(scenario(ns, order="dead_first", error_code=5, expiry=0))
    witnesses = sum(row["recovery_deadline_missed"] for row in scenarios)
    is_base = digest == BASE_SHA256
    if is_base and witnesses == 0:
        raise AssertionError("baseline lost the required RED witness")
    if not is_base and witnesses:
        raise AssertionError("candidate retains modeled registry starvation")
    result = {"event": "shared_gate_registration_actual_ast_model_v1",
              "source_sha256": digest, "driver_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
              "actual_ast_sha256": ast_digests, "cpu_affinity": sorted(os.sched_getaffinity(0)),
              "result": "RED_CONDITIONAL_LIVENESS_WITNESS" if is_base else "MODELED_BOUNDARY_PASS",
              "scenario_count": len(scenarios), "baseline_deadline_miss_witnesses": witnesses,
              "harness_checks_passed": True, "native_executed": False,
              "original_ci_cause_proven": False, "production_approved": False,
              "virtual_time_is_not_native_elapsed_time": True,
              "busy_timeout_is_not_hard_realtime_guarantee": True,
              "scenarios": scenarios}
    bounded()
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
