"""Bounded synthetic journal-size probe of real managed-worker startup.

The fixture contains balanced system-account ledger postings, not matched trades.
All financial constructors, verification, fencing and the supervisor run unchanged.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from functools import wraps
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import resource
import sqlite3
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from uta import durable_process
from uta.credit import CreditService
from uta.durable_process import DurableProcessRouter
from uta.ledger import Posting
from uta.service import ExchangeService
from uta.sharding import ShardRouter, ShardWorkerView
from uta.storage import DurableLedger
from uta.writer_fence import WriterFence

ORIGINAL_WORKER = durable_process._run_worker
TERMINAL = {"SUCCEEDED", "REJECTED", "QUARANTINED"}


def stamp():
    return {"monotonic_ns": time.monotonic_ns(),
            "boottime_ns": time.clock_gettime_ns(time.CLOCK_BOOTTIME),
            "utc": datetime.now(timezone.utc).isoformat(), "pid": os.getpid()}


def emit(path, **values):
    # Separate files per worker PID avoid a shared log lock in the measured path.
    with Path(path).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({**stamp(), **values}, sort_keys=True) + "\n")


class ObservedPipe:
    def __init__(self, pipe, path):
        self.pipe, self.path = pipe, path

    def send(self, value):
        emit(self.path, phase="report", event="send", value=value)
        return self.pipe.send(value)

    def close(self):
        return self.pipe.close()


def observed_worker(*arguments):
    """Call-through timing only; no sleeps, lease changes or verification flags."""
    path = Path(os.environ["UTA_RECOVERY_TRACE"]) / f"worker-{os.getpid()}.jsonl"
    arguments = list(arguments)
    arguments[4] = ObservedPipe(arguments[4], path)
    replacements = []

    def instrument(owner, name, phase):
        original = getattr(owner, name)

        @wraps(original)
        def measured(*args, **kwargs):
            started = time.monotonic_ns()
            emit(path, phase=phase, event="begin")
            try:
                value = original(*args, **kwargs)
            except BaseException as error:
                emit(path, phase=phase, event="error", elapsed_ns=time.monotonic_ns()-started,
                     error_type=type(error).__name__, code=getattr(error, "code", None))
                raise
            details = {}
            if phase == "fence_acquire":
                details = {"generation": value.generation, "owner_pid": value.process_id}
            elif phase == "ledger_verify":
                details = {"verified_events": value}
            emit(path, phase=phase, event="end", elapsed_ns=time.monotonic_ns()-started, **details)
            return value

        replacements.append((owner, name, original))
        setattr(owner, name, measured)

    instrument(DurableProcessRouter, "__init__", "child_router_constructor")
    instrument(WriterFence, "acquire", "fence_acquire")
    instrument(ShardWorkerView, "__init__", "worker_view_constructor")
    instrument(ShardWorkerView, "_reconcile", "shard_reconcile")
    instrument(ShardRouter, "_batch_funding_claims", "funding_claims")
    instrument(ExchangeService, "__init__", "exchange_constructor")
    instrument(DurableLedger, "__init__", "ledger_constructor")
    instrument(DurableLedger, "verify", "ledger_verify")
    instrument(CreditService, "__init__", "credit_constructor")
    instrument(CreditService, "_verify", "credit_verify")
    instrument(WriterFence, "renew", "fence_renew")
    emit(path, phase="worker_lifecycle", event="begin")
    try:
        return ORIGINAL_WORKER(*arguments)
    finally:
        emit(path, phase="worker_lifecycle", event="end")
        for owner, name, original in reversed(replacements):
            setattr(owner, name, original)


@contextmanager
def readonly(path):
    connection = sqlite3.connect(Path(path).absolute().as_uri()+"?mode=ro", uri=True,
                                 isolation_level=None, timeout=.2)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        yield connection
    finally:
        connection.close()


def encoded(value):
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def check_history(path, expected_events):
    """Independent integer/hash replay through an existing-file RO connection."""
    started = time.monotonic_ns()
    with readonly(path) as connection:
        assert [row[0] for row in connection.execute("PRAGMA integrity_check")] == ["ok"]
        assert connection.execute("PRAGMA foreign_key_check").fetchone() is None
        balances, prior, count = {}, "0"*64, 0
        for event in connection.execute("SELECT * FROM ledger_events ORDER BY sequence"):
            sequence, event_id, fingerprint, previous_hash, event_hash, sealed = tuple(event)
            count += 1
            assert sequence == count and sealed == 1 and previous_hash == prior
            assert event_id == f"recovery-system:{sequence-1}"
            postings = [tuple(row) for row in connection.execute(
                "SELECT ordinal,account,asset,units FROM ledger_postings WHERE sequence=? ORDER BY ordinal", (sequence,))]
            assert [row[0] for row in postings] == [0, 1]
            direction = 1 if sequence % 2 else -1
            canonical = [("system:recovery:a", "USD", direction),
                         ("system:recovery:b", "USD", -direction)]
            assert [(row[1], row[2], int(row[3])) for row in postings] == canonical
            assert all(str(int(row[3])) == row[3] for row in postings)
            assert sha256(encoded(canonical).encode()).hexdigest() == fingerprint
            assert sha256(encoded([sequence, event_id, prior, fingerprint]).encode()).hexdigest() == event_hash
            for account, asset, units in canonical:
                balances[account, asset] = balances.get((account, asset), 0)+units
            prior = event_hash
        assert count == expected_events
        stored = {(row[0], row[1]): int(row[2]) for row in connection.execute("SELECT * FROM ledger_balances")}
        assert stored == balances
        assert [tuple(row) for row in connection.execute("SELECT account_id,version FROM uta_accounts ORDER BY account_id")] == [("recovery-a", 0), ("recovery-b", 0)]
        assert connection.execute("SELECT COUNT(*) FROM uta_orders").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM uta_positions").fetchone()[0] == 0
        lease_events = [dict(row) for row in connection.execute("SELECT * FROM writer_fence_events ORDER BY sequence")]
        queues = [dict(row) for row in connection.execute("SELECT command_id,state,attempts,result,error FROM uta_command_inbox ORDER BY sequence")]
    return {"events": count, "ledger_hash": prior, "balances": [[*key, value] for key, value in sorted(balances.items())],
            "accounts": 2, "orders": 0, "positions": 0, "readonly": True,
            "integrity_check": "ok", "foreign_key_check": "ok", "elapsed_ns": time.monotonic_ns()-started,
            "lease_events": lease_events, "queue": queues}


def validate(events, observe_seconds):
    if type(events) is not int or not 1 <= events <= 200000:
        raise ValueError("events must be an integer in 1..200000")
    if isinstance(observe_seconds, bool) or not isinstance(observe_seconds, (int, float)) or not 1 <= observe_seconds <= 13:
        raise ValueError("observe_seconds must be in 1..13")


def environment():
    def git(*parts):
        return subprocess.check_output(["git", *parts], cwd=ROOT, text=True).strip()
    return {"code_commit": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain")),
            "source_root": str(ROOT), "python": sys.version, "sqlite": sqlite3.sqlite_version,
            "platform": platform.platform(), "affinity": sorted(os.sched_getaffinity(0)),
            "source_sha256": {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest()
                              for p in sorted((ROOT/"uta").glob("*.py"))},
            "tool_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
            "cgroup": {name: (Path("/sys/fs/cgroup")/name).read_text().strip()
                       for name in ("cpu.max", "memory.max") if (Path("/sys/fs/cgroup")/name).exists()},
            "cpu_model": next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                               if line.startswith("model name")), "unknown")}


def run(events, output, *, observe_seconds=12):
    validate(events, observe_seconds)
    output = Path(output).absolute()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    traces = output/"traces"
    traces.mkdir(mode=0o700)
    started = time.monotonic_ns()
    deadline = time.monotonic()+45
    summary = {"events_requested": events, "observe_seconds": observe_seconds, "started": stamp(),
               "environment": environment(), "lease_seconds": 5.0,
               "instrumentation": "call-through wrappers change loaded audit code artifact identity; sources, guards, verification, clocks and default runtime settings unchanged",
               "resource_bounds": {"cohort_work_budget_seconds": 45, "cli_cpu_affinity_count": 1,
                                   "cli_address_space_bytes": 1024**3, "cli_max_file_bytes": 256*1024**2,
                                   "cli_cpu_seconds_per_process": 55},
               "fixture": "two zero-funded customer accounts; balanced alternating USD minor-unit system transfers via DurableLedger.post with real batched connection; no trades or customer funding",
               "production_approved": False, "ha_approved": False, "capacity_passed": False}
    router = None
    previous_target, previous_trace = durable_process._run_worker, os.environ.get("UTA_RECOVERY_TRACE")
    try:
        def bootstrap(offline):
            offline.create_account("recovery-a")
            offline.create_account("recovery-b")
            service = offline._services[0]
            for begin in range(0, events, 256):
                if time.monotonic() >= deadline:
                    raise TimeoutError("fixture exceeded 45-second work budget")
                with service.database.transaction() as connection:
                    for index in range(begin, min(begin+256, events)):
                        direction = Decimal(".00000001") if index % 2 == 0 else Decimal("-.00000001")
                        service.ledger.post(f"recovery-system:{index}", [
                            Posting("system:recovery:a", "USD", direction),
                            Posting("system:recovery:b", "USD", -direction)], connection=connection)

        setup_started = time.monotonic_ns()
        router = DurableProcessRouter.initialize(output/"authority", 1, {"USD": 8}, managed=True, bootstrap=bootstrap)
        summary["initialize_ns"] = time.monotonic_ns()-setup_started
        shard = output/"authority/shard-0000.sqlite3"
        summary["initial_history"] = check_history(shard, events)
        enqueue_started = time.monotonic_ns()
        summary["enqueue_ack"] = router.cancel_order("recovery-a", "recovery-probe", "absent-order")
        summary["enqueue_ns"] = time.monotonic_ns()-enqueue_started
        summary["initial_query"] = router.status("recovery-probe", account_id="recovery-a")
        durable_process._run_worker = observed_worker
        os.environ["UTA_RECOVERY_TRACE"] = str(traces)
        startup_started = time.monotonic_ns()
        router.start()
        summary["start_return_ns"] = time.monotonic_ns()-startup_started
        observation_end = min(deadline, time.monotonic()+observe_seconds)
        observed, ready_at, terminal_at = [], None, None
        while time.monotonic() < observation_end:
            query = router.status("recovery-probe", account_id="recovery-a")
            with readonly(shard) as connection:
                lease = dict(connection.execute("SELECT * FROM writer_fence_lease").fetchone())
            with router._mutex:
                reports = {str(key): dict(value) for key, value in router._reports.items()}
                workers = {str(key): {"pid": worker[0].pid, "alive": worker[0].is_alive(), "exitcode": worker[0].exitcode}
                           for key, worker in router._workers.items()}
            row = {**stamp(), "elapsed_ns": time.monotonic_ns()-startup_started,
                   "query": query, "lease": lease, "workers": workers, "reports": reports}
            observed.append(row)
            if ready_at is None and any(report.get("state") == "ready" for report in reports.values()):
                ready_at = row["elapsed_ns"]
            if query["state"] in TERMINAL:
                terminal_at = row["elapsed_ns"]
                if ready_at is not None:
                    break
            time.sleep(.1)
        summary.update(ready_observed_ns=ready_at, terminal_observed_ns=terminal_at,
                       last_query=observed[-1]["query"] if observed else None)
        (output/"observations.jsonl").write_text("".join(json.dumps(row, sort_keys=True)+"\n" for row in observed))
        summary["diagnostics"] = router.diagnostics(timeout=.2)
    except BaseException as error:
        summary["error"] = {"type": type(error).__name__, "code": getattr(error, "code", None), "message": str(error)}
        raise
    finally:
        close_started = time.monotonic_ns()
        if router is not None:
            router.close()
        summary["close_ns"] = time.monotonic_ns()-close_started
        durable_process._run_worker = previous_target
        if previous_trace is None:
            os.environ.pop("UTA_RECOVERY_TRACE", None)
        else:
            os.environ["UTA_RECOVERY_TRACE"] = previous_trace
        if router is not None:
            try:
                summary["final_query"] = router.status("recovery-probe", account_id="recovery-a")
                summary["final_history"] = check_history(output/"authority/shard-0000.sqlite3", events)
                if "initial_history" in summary:
                    summary["history_unchanged"] = all(summary["initial_history"][key] == summary["final_history"][key]
                                                        for key in ("events", "ledger_hash", "balances", "accounts", "orders", "positions"))
            except BaseException as error:
                summary["cleanup_error"] = {"type": type(error).__name__, "message": str(error)}
        summary["total_ns"] = time.monotonic_ns()-started
        summary["completed"] = stamp()
        (output/"summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True)+"\n")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--observe-seconds", type=float, default=12)
    arguments = parser.parse_args()
    validate(arguments.events, arguments.observe_seconds)
    # Children inherit affinity and hard limits. No global cgroup/job changes.
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (256*1024**2, 256*1024**2))
    resource.setrlimit(resource.RLIMIT_CPU, (55, 55))
    summary = run(arguments.events, arguments.output, observe_seconds=arguments.observe_seconds)
    print(json.dumps({key: summary[key] for key in ("events_requested", "initialize_ns", "ready_observed_ns", "terminal_observed_ns", "total_ns", "history_unchanged")}))


if __name__ == "__main__":
    main()
