"""Short open-loop probes of real paired liquidation settlement, using synthetic funds.

Each victim opens 90 units against an actual counterparty at 100. One published
shock marks that instrument at 90. The task pump supplies two real 45-unit close
orders per case; only committed match receipts count as liquidation trades.
This is a <=30-second diagnostic, never a 30-minute production-capacity claim.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from hashlib import sha256
import json
import math
import os
from pathlib import Path
from queue import Empty, Full, Queue
import platform
import sqlite3
import subprocess
import sys
from threading import Event, Thread
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uta.examples import synthetic_policy
from uta.market import MarketSnapshot
from uta.matching import Matcher
from uta.models import AssetSpec, InstrumentSpec
from uta.reconciliation import reconcile_exchange
from uta.service import ExchangeService, ServiceError
from uta.storage import Database

SYMBOL = "BTC-PERP"
SCALES = {"USD": 8, "BTC": 8}
PRICE_AGE = timedelta(seconds=90)


@dataclass(frozen=True)
class Configuration:
    cases: int = 20
    duration: float = 1
    workers: int = 2
    shards: int = 1
    queue_capacity: int = 64
    drain_seconds: float = 20
    timeout_ms: float = 1000
    liquidity: str = "full"

    def validate(self):
        for name in ("cases", "workers", "shards", "queue_capacity"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError(f"{name} must be a positive integer")
        if self.cases > 512 or self.workers > 32 or self.shards > self.cases or self.queue_capacity > 100000:
            raise ValueError("short probe requires cases<=512, workers<=32, shards<=cases and queue<=100000")
        for name in ("duration", "drain_seconds", "timeout_ms"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        if self.duration > 30 or self.drain_seconds > 30:
            raise ValueError("short_probe_only: duration/drain <=30s; long runs need a measured live market-feeder path")
        if self.liquidity not in ("full", "half", "none"):
            raise ValueError("liquidity must be full, half or none")


def _service(path):
    catalog, rules = synthetic_policy()
    return ExchangeService(Database(path, timeout=2), SCALES, max_price_age=PRICE_AGE,
                           product_catalog=catalog, portfolio_rules=rules)


def _market(version, mark):
    return MarketSnapshot(version, datetime.now(timezone.utc),
        {"USD": AssetSpec(D(1), D(1)), "BTC": AssetSpec(D(mark), D(".8"))},
        {SYMBOL: InstrumentSpec(D(mark), D(".1"), D(".05"))})


def _percentiles(values):
    ordered = sorted(values)
    return {name: (ordered[max(0, math.ceil(len(ordered) * q) - 1)] / 1e6 if ordered else None)
            for name, q in (("p50", .5), ("p95", .95), ("p99", .99), ("p99_9", .999))}


def _first_recoveries(records):
    # Parallel post-fill health checks may both observe NORMAL. The first
    # confirmed observation defines recovery, not the last callback delivered.
    recovered = {}
    for row in records:
        if row["kind"] == "recovered":
            case, at = row["case"], row["at_ns"]
            recovered[case] = min(at, recovered.get(case, at))
    return recovered


def _environment(configuration):
    root = Path(__file__).resolve().parents[1]
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=root, text=True).strip()
    cgroup = {}
    for name in ("cpu.max", "memory.max"):
        p = Path("/sys/fs/cgroup") / name
        if p.exists():
            cgroup[name] = p.read_text().strip()
    return {"code_commit": git("rev-parse", "HEAD"), "working_tree_dirty": bool(git("status", "--porcelain")),
            "configuration": asdict(configuration), "python": sys.version, "sqlite": sqlite3.sqlite_version,
            "platform": platform.platform(), "cpu_affinity": len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else os.cpu_count(),
            "cgroup_limits": cgroup, "workers_type": "threads; each owns independent service connections",
            "durability": "single-host SQLite WAL/FULL; no replication", "settlement_asset": "synthetic USD",
            "risk_profile": "versioned synthetic Cross", "catalog_version": 1, "rule_version": 1,
            "source_sha256": {str(p.relative_to(root)): sha256(p.read_bytes()).hexdigest()
                              for p in [Path(__file__).resolve(), *(root / "uta").glob("*.py")]}}


def _prepare(configuration, directory):
    services, paths = [], []
    for index in range(configuration.shards):
        path = directory / f"shard-{index}.sqlite3"
        exchange = _service(path)
        exchange.publish_market(_market(1, 100))
        exchange.set_kill_switch(False)
        services.append(exchange)
        paths.append(path)
    for case in range(configuration.cases):
        service = services[case % configuration.shards]
        victim, counterparty = f"victim-{case}", f"liquidity-{case}"
        for account, cash in ((victim, D(1000)), (counterparty, D(100000))):
            service.create_account(account)
            service.deposit(account, "synthetic-funding", "USD", cash)
        service.submit_order(victim, "open", SYMBOL, D(90), D(100))
        service.submit_order(counterparty, "open", SYMBOL, D(-90), D(100))
        result = Matcher(service).match_once(SYMBOL, max_matches=1)
        if result["confirmed_trades"] != 1:
            raise RuntimeError("fixture did not open through a real paired trade")
    baselines, triggers = {}, {}
    for index, service in enumerate(services):
        with service.database.transaction() as connection:
            baselines[index] = connection.execute("SELECT COALESCE(MAX(sequence),0) FROM uta_matches").fetchone()[0]
        triggers[index] = time.monotonic_ns()
        service.publish_market(_market(2, 90))
    return paths, baselines, triggers


def _process_case(configuration, task, services, emit, recovered):
    case, scheduled, trigger = task
    shard = case % configuration.shards
    service, matcher = services[shard]
    victim, counterparty = f"victim-{case}", f"liquidity-{case}"
    started = time.monotonic_ns()
    row = {"kind": "case", "case": case, "shard": shard, "scheduled_ns": scheduled,
           "trigger_ns": trigger, "started_ns": started, "outcome": "processed"}
    try:
        plan = service.supervise_account(victim)
        if plan["state"] != "LIQUIDATING":
            raise RuntimeError("fixture failed to create a real liquidation plan")
        emit({"kind": "risk_plan", "case": case, "shard": shard, "at_ns": time.monotonic_ns(),
              "state": plan["state"], "created_orders": len(plan["created_orders"]),
              "cancelled_orders": len(plan["cancelled_orders"])})
        depth_count = {"none": 0, "half": 1, "full": 2}[configuration.liquidity]
        for part in range(depth_count):
            service.submit_order(counterparty, f"close-{part}", SYMBOL, D(45), D(90), reduce_only=True)
            outcome = matcher.match_once(SYMBOL, max_matches=1)
            returned = time.monotonic_ns()  # method returns only after COMMIT
            if outcome["blocked"]:
                emit({"kind": "execution_blocked", "case": case, "shard": shard,
                      "at_ns": returned, "details": outcome["blocked"]})
            for trade in outcome["trades"]:
                if not trade["sell_order_id"].startswith("liq:") or D(trade["quantity"]) != D(45):
                    raise RuntimeError("probe must only count a real 45-unit liquidation match")
                actual_case = int(trade["sell_account_id"].removeprefix("victim-"))
                emit({"kind": "liquidation_trade", "case": actual_case, "pump_case": case,
                      "shard": shard, "trigger_ns": trigger, "committed_observed_ns": returned,
                      "receipt": trade, "unique_liquidation_fills": 1, "settlement_legs": 2})
                state = service.supervise_account(trade["sell_account_id"])
                if state["state"] == "NORMAL":
                    recovered(actual_case, time.monotonic_ns())
        if not depth_count:
            if matcher.match_once(SYMBOL, max_matches=1)["confirmed_trades"]:
                raise RuntimeError("no liquidity fixture unexpectedly matched")
    except ServiceError as exc:
        row.update(outcome="business_rejected" if exc.status < 500 else "technical_failed", error_code=exc.code)
    except Exception as exc:
        row.update(outcome="technical_failed", error_type=type(exc).__name__)
    row["completed_ns"] = time.monotonic_ns()
    row["latency_ns"] = row["completed_ns"] - scheduled
    row["deadline_exceeded"] = row["latency_ns"] > configuration.timeout_ms * 1e6
    emit(row)


def capacity_gates(duration, unique_fills_rate, counts, unresolved, liquidity):
    checks = {"duration_at_least_1800s": duration >= 1800, "unique_committed_liquidation_fills_at_least_10000_per_s": unique_fills_rate >= 10000,
              "full_counterparty_liquidity": liquidity == "full", "no_unresolved_accounts": unresolved == 0,
              "no_technical_unknown_overload_or_deadline_failures": not any(counts.get(k, 0) for k in
                  ("technical_failed", "unknown", "overload", "deadline_exceeded", "business_rejected", "execution_blocked"))}
    return {"checks": checks, "passed": all(checks.values()), "production_approved": False,
            "phase1_exchange_acceptance_passed": False}


def run(configuration, directory):
    configuration.validate()
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    environment = _environment(configuration)
    (directory / "environment.json").write_text(json.dumps(environment, indent=2) + "\n")
    preparation_start = time.monotonic_ns()
    paths, baselines, triggers = _prepare(configuration, directory)
    preparation_finished = time.monotonic_ns()
    pending = Queue(configuration.queue_capacity)
    # At most eight records per finite case; this is an explicitly bounded
    # short probe, not an unbounded streaming collector.
    output = Queue(configuration.cases * 8 + configuration.workers)
    ready, stop = Queue(), Event()
    errors = []

    def worker(number):
        try:
            services = [(_service(path), None) for path in paths]
            services = [(service, Matcher(service, initialize=False)) for service, _ in services]
            ready.put(number)
            while not stop.is_set():
                try:
                    task = pending.get(timeout=.05)
                except Empty:
                    continue
                try:
                    _process_case(configuration, task, services, output.put,
                                  lambda case, at: output.put({"kind": "recovered", "case": case, "at_ns": at}))
                finally:
                    pending.task_done()
        except Exception as exc:
            errors.append(type(exc).__name__)
            ready.put({"error": type(exc).__name__})

    threads = [Thread(target=worker, args=(index,), name=f"liquidation-{index}", daemon=False)
               for index in range(configuration.workers)]
    for thread in threads:
        thread.start()
    try:
        for _ in threads:
            if isinstance(ready.get(timeout=30), dict):
                raise RuntimeError("liquidation worker initialization failed")
    except BaseException:
        stop.set()
        for thread in threads:
            thread.join()
        raise
    generated = []
    start = time.monotonic_ns()
    try:
        for case in range(configuration.cases):
            scheduled = start + int(configuration.duration * 1e9 * case / configuration.cases)
            remaining = scheduled - time.monotonic_ns()
            if remaining > 0:
                time.sleep(remaining / 1e9)
            try:
                pending.put_nowait((case, scheduled, triggers[case % configuration.shards]))
            except Full:
                at = time.monotonic_ns()
                generated.append({"kind": "case", "case": case, "shard": case % configuration.shards,
                                  "outcome": "overload", "scheduled_ns": scheduled,
                                  "trigger_ns": triggers[case % configuration.shards], "completed_ns": at,
                                  "latency_ns": at - scheduled, "deadline_exceeded": False})
        deadline = time.monotonic() + configuration.drain_seconds
        while pending.unfinished_tasks and time.monotonic() < deadline:
            time.sleep(.001)
    finally:
        # A soft drain deadline never kills a financial transaction. In-flight
        # work is joined; extra drain time stays in the throughput denominator.
        stop.set()
        for thread in threads:
            thread.join()
    finished = time.monotonic_ns()
    records = generated
    while not output.empty():
        records.append(output.get_nowait())
    cases = {row["case"]: row for row in records if row["kind"] == "case"}
    for case in range(configuration.cases):
        if case not in cases:
            row = {"kind": "case", "case": case, "shard": case % configuration.shards, "outcome": "unknown",
                   "scheduled_ns": start + int(configuration.duration * 1e9 * case / configuration.cases),
                   "trigger_ns": triggers[case % configuration.shards], "completed_ns": finished,
                   "deadline_exceeded": True}
            row["latency_ns"] = finished - row["scheduled_ns"]
            records.append(row)
            cases[case] = row
    verification_start = time.monotonic_ns()
    reconciliation, database_receipts, final_accounts = [], {}, {}
    for shard, path in enumerate(paths):
        service = _service(path)  # reopen storage after workers have stopped
        reconciliation.append({"shard": shard, **reconcile_exchange(service, matching_only=True)})
        with service.database.transaction() as connection:
            for receipt in connection.execute("SELECT * FROM uta_matches WHERE sequence>? ORDER BY sequence", (baselines[shard],)):
                database_receipts[receipt["trade_id"]] = dict(receipt)
        for case in range(shard, configuration.cases, configuration.shards):
            account = service.account(f"victim-{case}")
            final_accounts[case] = {"quantity": account["positions"].get(SYMBOL, {}).get("quantity", "0"),
                                    "balance_usd": account["balances"]["USD"]}
    trades = [row for row in records if row["kind"] == "liquidation_trade"]
    observed = {row["receipt"]["trade_id"]: row for row in trades}
    if len(observed) != len(trades) or not set(observed) <= set(database_receipts):
        raise RuntimeError("duplicate or uncommitted observed trade receipt")
    for identity, receipt in database_receipts.items():
        if not receipt["sell_order_id"].startswith("liq:") or D(receipt["quantity"]) != 45:
            raise RuntimeError("reopened database contains an unexpected liquidation trade")
        if identity not in observed:
            records.append({"kind": "recovered_unknown_trade", "receipt": receipt, "latency_ns": None})
    closed = sum(D(a["quantity"]) == 0 for a in final_accounts.values())
    remaining_quantity = sum((D(a["quantity"]) for a in final_accounts.values()), D(0))
    if any(D(a["quantity"]) < 0 or D(a["quantity"]) > 90 for a in final_accounts.values()):
        raise RuntimeError("liquidation reversed or increased a victim position")
    if D(len(database_receipts) * 45) + remaining_quantity != D(configuration.cases * 90):
        raise RuntimeError("confirmed receipt volume does not reconcile to remaining victim risk")
    counts = Counter(row["outcome"] for row in cases.values())
    counts["deadline_exceeded"] = sum(row["deadline_exceeded"] for row in cases.values())
    counts["execution_blocked"] = sum(row["kind"] == "execution_blocked" for row in records)
    counts["unknown_committed_trades"] = len(set(database_receipts) - set(observed))
    counts["unknown"] += counts["unknown_committed_trades"]
    measured_seconds = max(configuration.duration, (finished - start) / 1e9)
    first = defaultdict(list)
    for row in trades:
        first[row["case"]].append(row["committed_observed_ns"] - row["trigger_ns"])
    recovered = _first_recoveries(records)
    recovery_durations = [at - triggers[case % configuration.shards] for case, at in recovered.items()]
    summary = {"scope": "synthetic single-host real paired liquidation; short diagnostic, no external venue or HA",
        "configuration": asdict(configuration), "offered_cases": configuration.cases,
        "counts": dict(counts), "worker_errors": errors,
        "unique_committed_liquidation_trades": len(database_receipts), "observed_acknowledged_trades": len(observed),
        "two_sided_settlement_legs": len(database_receipts) * 2,
        "unique_committed_liquidation_fills_per_s": len(observed) / measured_seconds,
        "triggered_accounts": configuration.cases, "processed_cases": counts["processed"],
        "fully_closed_accounts": closed, "unresolved_accounts": configuration.cases - closed,
        "remaining_position_quantity": str(remaining_quantity), "final_victim_accounts": final_accounts,
        "preparation_seconds": (preparation_finished - preparation_start) / 1e9,
        "worker_startup_after_shock_seconds": (start - preparation_finished) / 1e9,
        "arrival_window_seconds": configuration.duration, "arrival_rate_per_s": configuration.cases / configuration.duration,
        "execution_and_drain_seconds": (finished - start) / 1e9, "throughput_denominator_seconds": measured_seconds,
        "verification_seconds": (time.monotonic_ns() - verification_start) / 1e9,
        "latency_ms": {"scheduled_case_to_complete": _percentiles([r["latency_ns"] for r in cases.values()]),
                       "shock_to_first_confirmed_trade": _percentiles([min(values) for values in first.values()]),
                       "shock_to_each_confirmed_trade": _percentiles([x for values in first.values() for x in values]),
                       "shock_to_recovered": _percentiles(recovery_durations)},
        "reconciliation": reconciliation,
        "gates": capacity_gates(configuration.duration, len(observed) / measured_seconds, counts,
                                 configuration.cases - closed, configuration.liquidity),
        "production_approved": False, "liquidity_model": "one common instrument per shard, real FIFO counterparties; each order quantity45",
        "trigger_timing": "all cases share a real pre-load shock; arrival pump delays are included in shock latencies"}
    (directory / "arrivals.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in records))
    (directory / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    files = [directory / name for name in ("arrivals.jsonl", "summary.json", "environment.json")]
    (directory / "manifest.json").write_text(json.dumps({"files": {p.name: {"sha256": sha256(p.read_bytes()).hexdigest(),
                                              "bytes": p.stat().st_size} for p in files}, "database_files_included": False}, indent=2) + "\n")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    for name, default in (("cases", 20), ("workers", 2), ("shards", 1), ("queue-capacity", 64)):
        parser.add_argument("--" + name, type=int, default=default)
    for name, default in (("duration", 1), ("drain-seconds", 20), ("timeout-ms", 1000)):
        parser.add_argument("--" + name, type=float, default=default)
    parser.add_argument("--liquidity", choices=("full", "half", "none"), default="full")
    parser.add_argument("--smoke", action="store_true", help="tool check; never changes failed capacity gates")
    args = parser.parse_args(argv)
    try:
        summary = run(Configuration(args.cases, args.duration, args.workers, args.shards,
                        args.queue_capacity, args.drain_seconds, args.timeout_ms, args.liquidity), args.output)
    except (ValueError, OSError, RuntimeError) as exc:
        parser.error(str(exc))
    print(json.dumps(summary, indent=2))
    return 1 if summary["worker_errors"] or summary["counts"].get("technical_failed") else (0 if args.smoke or summary["gates"]["passed"] else 2)


if __name__ == "__main__":
    raise SystemExit(main())
