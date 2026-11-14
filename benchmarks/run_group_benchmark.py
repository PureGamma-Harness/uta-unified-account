"""Open-loop, funded admission-only comparison of synchronous and group commits.

Every accepted order remains OPEN and reserved. There is no cancellation,
matching, simulated fill, or shortcut that releases margin inside an arrival.
These bounded short probes cannot approve production capacity or real funds.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import CancelledError
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from fractions import Fraction
import gzip
from hashlib import sha256
import importlib
import json
import math
import os
from pathlib import Path
import platform
from queue import Queue
import sqlite3
import subprocess
import sys
from threading import BoundedSemaphore, Lock, Thread
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmarks.run_benchmark import LatencyHistogram
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.portfolio import CollateralRule, CollateralTier, LinearMarginRule, PortfolioRules
from uta.products import ProductCatalog, ProductKind, ProductSpec, TradingStatus
from uta.service import ExchangeService, ServiceError
from uta.storage import Database


@dataclass(frozen=True)
class Configuration:
    mode: str = "sync"
    policy: str = "configured_cross"
    duration: float = 5
    rate: float = 1000
    accounts: int = 100
    shards: int = 1
    workers: int = 4
    queue_capacity: int = 1024
    batch_size: int = 32
    batch_delay_ms: float = 2
    timeout_ms: float = 1000
    drain_seconds: float = 10

    def validate(self):
        if self.mode not in ("sync", "batch"):
            raise ValueError("mode must be sync or batch")
        if self.policy not in ("configured_cross", "legacy_reference"):
            raise ValueError("policy must be configured_cross or legacy_reference")
        for name in ("duration", "rate", "timeout_ms", "drain_seconds"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        if self.duration > 10 or self.drain_seconds > 10:
            raise ValueError("short-probe duration and soft drain budget must each be <=10s; no long market feeder is implemented")
        for name, maximum in (("accounts", 10000), ("shards", 64), ("workers", 64),
                              ("queue_capacity", 65536), ("batch_size", 256)):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError(f"{name} must be an integer in 1..{maximum}")
        if self.shards > self.accounts:
            raise ValueError("shards cannot exceed accounts")
        if (isinstance(self.batch_delay_ms, bool) or not isinstance(self.batch_delay_ms, (int, float))
                or not math.isfinite(self.batch_delay_ms) or not 0 <= self.batch_delay_ms <= 1000):
            raise ValueError("batch_delay_ms must be finite and in 0..1000")
        offered = int(self.duration * self.rate)
        if offered < 1 or offered > 1_000_000:
            raise ValueError("probe must offer 1..1000000 arrivals")
        if math.ceil(offered / self.accounts) > 900:
            raise ValueError("admission-only probe permits at most 900 offered live orders/account; use more accounts")


def capacity_gates(duration, durable_rate, counts, p99_ms):
    """The user's long-run capacity gate cannot pass from a short probe."""
    requirements = {"min_duration_seconds": 1800, "min_unique_durable_admissions_per_s": 10000,
                    "temporary_p99_target_ms": 100}
    forbidden = ("overload", "technical_failed", "safety_rejected", "unknown", "cancelled_not_executed",
                 "accepted_late", "business_rejected", "drain_budget_exceeded")
    passed = (duration >= 1800 and durable_rate >= 10000 and p99_ms is not None and p99_ms <= 100
              and not any(counts.get(key, 0) for key in forbidden))
    return {"passed": passed, "requirements": requirements,
            "phase1_exchange_acceptance_passed": False, "production_approved": False,
            "scope": "funded admission-only component; excludes matching, liquidation and market-feed capacity"}


def _policy(mode):
    if mode == "legacy_reference":
        return {}
    catalog = ProductCatalog(1, {"BTC-PERP": ProductSpec("BTC-PERP", ProductKind.LINEAR_PERPETUAL,
        "BTC", "USD", "USD", Decimal(".01"), Decimal(".001"), Decimal(".01"),
        status=TradingStatus.ACTIVE)})
    rules = PortfolioRules(1,
        {"USD": CollateralRule("USD", (CollateralTier(None, Decimal(1)),), Decimal(1))}, {},
        {"tier-1": LinearMarginRule("tier-1", Decimal(".1"), Decimal(".05"))}, Decimal(0))
    return {"product_catalog": catalog, "portfolio_rules": rules}


def _service(path, policy="configured_cross"):
    return ExchangeService(Database(path, timeout=2), {"USD": 8}, max_price_age=timedelta(seconds=30),
                           **_policy(policy))


def _environment(directory):
    def command(*parts):
        return subprocess.check_output(parts, cwd=ROOT, text=True).strip()
    quota = {}
    for name in ("cpu.max", "memory.max"):
        p = Path("/sys/fs/cgroup") / name
        if p.exists():
            quota[name] = p.read_text().strip()
    cpu_model = next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                      if line.startswith("model name")), "unknown") if Path("/proc/cpuinfo").exists() else platform.processor()
    return {"code_commit": command("git", "rev-parse", "HEAD"),
            "working_tree_dirty": bool(command("git", "status", "--porcelain")),
            "python": sys.version, "platform": platform.platform(), "sqlite": sqlite3.sqlite_version,
            "cpu_model": cpu_model, "cpu_affinity_count": len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else os.cpu_count(),
            "cgroup_limits": quota, "source_root": str(ROOT),
            "generator_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
            "source_sha256": {p.name: sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT / "uta").glob("*.py"))},
            "filesystem": command("df", "-T", str(directory)),
            "storage": "local SQLite WAL/FULL; each batch COMMIT retains FULL synchronous; no replication",
            "sqlite_busy_timeout_seconds": 2,
            "market_max_age_seconds": 30,
            "timing": "planned monotonic arrival to post-COMMIT observation; p99 histogram upper bound width <=0.1%",
            "queue_model": "one shared outstanding budget across dispatcher queue, database calls, batch queues and result collection"}


class Recorder:
    def __init__(self, path, timeout_ns):
        self.path = path
        self.source = path.open("x", encoding="utf-8")
        self.lock = Lock()
        self.timeout_ns = timeout_ns
        self.counts = Counter()
        self.all_latency = LatencyHistogram()
        self.accepted_latency = LatencyHistogram()
        self.service_latency = LatencyHistogram()
        self.durable = set()
        self.unknown = set()
        self.outcomes = {}
        self.completed_ns = 0

    def record(self, row):
        row["latency_ns"] = row["completed_ns"] - row["scheduled_ns"]
        row["deadline_exceeded"] = row["latency_ns"] > self.timeout_ns
        with self.lock:
            sequence = row["sequence"]
            if sequence in self.outcomes:
                raise RuntimeError("duplicate benchmark result")
            self.outcomes[sequence] = row["outcome"]
            self.counts[row["outcome"]] += 1
            self.all_latency.observe(row["latency_ns"])
            if row["durable_committed"]:
                self.durable.add((row["account_id"], row["order_id"]))
                self.accepted_latency.observe(row["latency_ns"])
                if row["deadline_exceeded"]:
                    self.counts["accepted_late"] += 1
            if row["outcome"] == "unknown":
                self.unknown.add((row["account_id"], row["order_id"]))
            if row.get("worker_started_ns") is not None:
                self.service_latency.observe(row["completed_ns"] - row["worker_started_ns"])
            self.completed_ns = max(self.completed_ns, row["completed_ns"])
            self.source.write(json.dumps(row, separators=(",", ":")) + "\n")

    def close(self):
        self.source.close()


def _verify(paths, accounts, recorder, policy):
    """Independently check every accepted ID, event, balance and live reserve."""
    all_orders = set()
    reports = []
    for shard, path in enumerate(paths):
        reopened = _service(path, policy)
        with reopened.database.transaction() as conn:
            journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            synchronous = conn.execute("PRAGMA synchronous").fetchone()[0]
            if journal_mode != "wal" or synchronous != 2:
                raise RuntimeError("probe did not preserve SQLite WAL/FULL")
            orders = conn.execute("SELECT account_id,order_id,symbol,quantity,limit_price,status,filled_quantity FROM uta_orders").fetchall()
            ids = {(r["account_id"], r["order_id"]) for r in orders}
            accepted = [json.loads(row[0]) for row in conn.execute("SELECT payload FROM uta_events WHERE event_type='ORDER_ACCEPTED'")]
            accepted_ids = {(row["account_id"], row["order_id"]) for row in accepted}
            if len(orders) != len(ids) or len(accepted) != len(accepted_ids) or ids != accepted_ids:
                raise RuntimeError("orders and durable acceptance events do not reconcile")
            for order in orders:
                if (order["symbol"], Decimal(order["quantity"]), Decimal(order["limit_price"]),
                        order["status"], Decimal(order["filled_quantity"])) != ("BTC-PERP", Decimal(".001"), Decimal(100), "OPEN", Decimal(0)):
                    raise RuntimeError("admission-only probe unexpectedly modified or closed an order")
            counts = Counter(account for account, _ in ids)
            for account in range(shard, accounts, len(paths)):
                account_id = f"probe-{account}"
                actual = reopened._account(conn, account_id)
                # Per order: .001*100*.1 + .001*100*.0004 = .01004 USD.
                expected_reserve = counts[account_id] * Fraction(251, 25000)
                if (Fraction(Decimal(actual["open_order_margin"])) != expected_reserve
                        or Decimal(actual["balances"]["USD"]) != Decimal(100000000)
                        or actual["positions"] or actual["version"] != 1 + counts[account_id]):
                    raise RuntimeError("reopened account reserve/balance/version does not reconcile")
            ledger_events = reopened.ledger.verify(connection=conn)
        all_orders.update(ids)
        reports.append({"shard": shard, "unique_orders": len(ids), "acceptance_events": len(accepted),
                        "ledger_events": ledger_events, "all_orders_remain_open": True,
                        "independent_live_reserves_verified": True,
                        "journal_mode": journal_mode, "synchronous": synchronous})
    if not recorder.durable <= all_orders or all_orders - recorder.durable - recorder.unknown:
        raise RuntimeError("database effects disagree with post-COMMIT success receipts")
    return reports, {"unacknowledged_orders_found": len((all_orders - recorder.durable) & recorder.unknown),
                     "unknown_ids_without_order_on_reopen": len(recorder.unknown - all_orders)}


def run(configuration: Configuration, directory: Path):
    configuration.validate()
    directory.mkdir(parents=True, exist_ok=False)
    environment = _environment(directory)
    environment["policy"] = configuration.policy
    environment["effective_policy"] = {key: json.loads(model.to_json()) for key, model in _policy(configuration.policy).items()}
    (directory / "environment.json").write_text(json.dumps(environment, indent=2) + "\n")
    setup_started = time.monotonic_ns()
    paths, services = [], []
    for shard in range(configuration.shards):
        path = directory / f"shard-{shard}.sqlite3"
        service = _service(path, configuration.policy)
        for index in range(shard, configuration.accounts, configuration.shards):
            account_id = f"probe-{index}"
            service.create_account(account_id)
            service.deposit(account_id, "synthetic-funding", "USD", Decimal(100000000))
        paths.append(path)
        services.append(service)
    # Publish AFTER funding setup. This short probe has no background feeder.
    for service in services:
        service.publish_market(MarketSnapshot(1, datetime.now(timezone.utc),
            {"USD": AssetSpec(Decimal(1), Decimal(1))},
            {"BTC-PERP": InstrumentSpec(Decimal(100), Decimal(".1"), Decimal(".05"))}))
        service.set_kill_switch(False)
    batchers = []
    if configuration.mode == "batch":
        module = importlib.import_module("uta.admission")
        try:
            for service in services:
                batchers.append(module.AdmissionBatcher(service, max_batch_size=configuration.batch_size,
                    max_delay_ms=configuration.batch_delay_ms, queue_capacity=configuration.queue_capacity))
        except BaseException:
            for batcher in batchers:
                batcher.close(wait=True)
            raise
    setup_elapsed = time.monotonic_ns() - setup_started
    pending = Queue(maxsize=configuration.queue_capacity)
    completed = Queue(maxsize=configuration.queue_capacity + configuration.workers + 1)
    slots = BoundedSemaphore(configuration.queue_capacity)
    future_lock = Lock()
    futures = {}
    recorder = Recorder(directory / "arrivals.jsonl", int(configuration.timeout_ms * 1_000_000))
    collector_error = []

    def outcome(row, error=None):
        row.update(completed_ns=time.monotonic_ns(), durable_committed=error is None,
                   outcome="durable_accepted" if error is None else "technical_failed")
        if isinstance(error, CancelledError):
            row["outcome"] = "cancelled_not_executed"
        elif isinstance(error, ServiceError):
            row["error_code"] = error.code
            if error.code == "admission_overloaded":
                row["outcome"] = "overload"
            elif error.code in ("market_unavailable", "invalid_clock"):
                row["outcome"] = "safety_rejected"
            elif error.code in ("command_result_unknown", "commit_unknown", "admission_batch_failed", "storage_unavailable"):
                row["outcome"] = "unknown"
            elif error.code == "ledger_rejected":
                row["outcome"] = "technical_failed"
            elif error.status < 500:
                row["outcome"] = "business_rejected"
        elif error is not None:
            row["error_type"] = type(error).__name__
        if error is not None:
            chain, seen = [error], set()
            while chain and len(seen) < 16:
                current = chain.pop()
                if current is None or id(current) in seen:
                    continue
                seen.add(id(current))
                code = getattr(current, "sqlite_errorcode", None)
                if code is not None:
                    row["sqlite_errorcode"] = code
                    row["sqlite_errorname"] = getattr(current, "sqlite_errorname", None)
                    break
                chain.extend((current.__cause__, current.__context__))
        return row

    def callback(future, row):
        row["admission_enqueued_ns"] = getattr(future, "admission_enqueued_ns", None)
        row["worker_started_ns"] = getattr(future, "admission_started_ns", None)
        row["receipt_published_ns"] = getattr(future, "admission_completed_ns", None)
        try:
            future.result()
            result = outcome(row)
        except BaseException as exc:
            result = outcome(row, exc)
        # Inflight slots are only released by collection. Thus at most the
        # configured outstanding budget can enqueue completions here.
        completed.put_nowait(result)

    def dispatch():
        while True:
            row = pending.get()
            if row is None:
                return
            row["dispatch_started_ns"] = time.monotonic_ns()
            args = row["account_id"], row["order_id"], "BTC-PERP", Decimal(".001"), Decimal(100)
            if batchers:
                try:
                    future = batchers[row["shard"]].submit_order(*args)
                    with future_lock:
                        futures[row["sequence"]] = future
                    future.add_done_callback(lambda future, row=row: callback(future, row))
                except BaseException as exc:
                    completed.put_nowait(outcome(row, exc))
            else:
                row["worker_started_ns"] = time.monotonic_ns()
                try:
                    services[row["shard"]].submit_order(*args)
                    result = outcome(row)
                except BaseException as exc:
                    result = outcome(row, exc)
                completed.put_nowait(result)

    def collect():
        while True:
            row = completed.get()
            if row is None:
                return
            try:
                recorder.record(row)
            except BaseException as exc:
                collector_error.append(str(exc))
            finally:
                with future_lock:
                    futures.pop(row["sequence"], None)
                slots.release()

    collector = Thread(target=collect, name="probe-results")
    workers = [Thread(target=dispatch, name=f"probe-dispatch-{n}") for n in range(configuration.workers)]
    collector.start()
    for worker in workers:
        worker.start()
    offered = int(configuration.duration * configuration.rate)
    started = time.monotonic_ns()
    try:
        for sequence in range(offered):
            scheduled = started + int(sequence * 1e9 / configuration.rate)
            delay = scheduled - time.monotonic_ns()
            if delay > 0:
                time.sleep(delay / 1e9)
            account = sequence % configuration.accounts
            row = {"kind": "arrival", "sequence": sequence, "account_id": f"probe-{account}",
                   "order_id": f"arrival-{sequence}", "shard": account % configuration.shards,
                   "scheduled_ns": scheduled, "offered_ns": time.monotonic_ns(),
                   "dispatch_started_ns": None, "worker_started_ns": None, "receipt_published_ns": None,
                   "durable_committed": False}
            if slots.acquire(blocking=False):
                pending.put_nowait(row)
            else:
                row.update(outcome="overload", error_code="shared_outstanding_budget", completed_ns=time.monotonic_ns())
                recorder.record(row)
    finally:
        arrivals_finished = time.monotonic_ns()
        # Even an interrupted generator must drain its already-admitted local
        # operations; silently abandoning a writer could leave unknown effects.
        for _ in workers:
            pending.put(None)
        for worker in workers:
            worker.join()
        for batcher in batchers:
            batcher.close(wait=True)
        batch_stats = [batcher.stats() for batcher in batchers]
        completed.put(None)
        collector.join()
        finished = time.monotonic_ns()
        recorder.close()
    if collector_error:
        raise RuntimeError("result recording failed: " + collector_error[0])
    if set(recorder.outcomes) != set(range(offered)):
        raise RuntimeError("offered arrivals were lost or duplicated")
    checks, unknown_resolution = _verify(paths, configuration.accounts, recorder, configuration.policy)
    elapsed = max(configuration.duration, (max(finished, recorder.completed_ns) - started) / 1e9)
    drain = max(0, (finished - (started + int(configuration.duration * 1e9))) / 1e9)
    counts = dict(recorder.counts)
    counts["drain_budget_exceeded"] = int(drain > configuration.drain_seconds)
    rate = len(recorder.durable) / elapsed
    all_latency = recorder.all_latency.report()
    summary = {"configuration": asdict(configuration), "offered_arrivals": offered,
               "arrival_window_seconds": configuration.duration, "measured_seconds_including_drain": elapsed,
               "generator_finished_seconds": (arrivals_finished - started) / 1e9,
               "setup_seconds_excluded": setup_elapsed / 1e9, "drain_seconds": drain,
               "counts": counts, "unique_durable_accepted_per_s": rate,
               "on_time_durable_accepted_per_s": (len(recorder.durable) - counts.get("accepted_late", 0)) / elapsed,
               "latency_ms": {"all": all_latency, "accepted": recorder.accepted_latency.report(),
                              "worker_start_to_observation": recorder.service_latency.report()},
               "batch_stats": batch_stats, "durability_checks": checks, "unknown_resolution": unknown_resolution,
               "gates": capacity_gates(configuration.duration, rate, counts, all_latency["p99"]),
               "scope": "single-process threaded admission-only; all successful orders remain live; no matching/liquidation",
               "market_feed": "one initial synthetic snapshot, 30s max age; <=10s arrival probe, no ongoing market fanout",
               "drain_policy": "soft budget only; always join admitted work to determine final state; actual excess fails gate",
               "environment": environment}
    (directory / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    raw = directory / "arrivals.jsonl"
    compressed = directory / "arrivals.jsonl.gz"
    compressed.write_bytes(gzip.compress(raw.read_bytes(), mtime=0))
    raw.unlink()
    manifest = {"database_files_included": False, "files": {
        p.name: {"bytes": p.stat().st_size, "sha256": sha256(p.read_bytes()).hexdigest()}
        for p in (compressed, directory / "summary.json", directory / "environment.json")}}
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("sync", "batch"), default="sync")
    parser.add_argument("--policy", choices=("configured_cross", "legacy_reference"), default="configured_cross")
    parser.add_argument("--duration", type=float, default=5)
    parser.add_argument("--rate", type=float, default=1000)
    for name, default in (("accounts", 100), ("shards", 1), ("workers", 4),
                          ("queue-capacity", 1024), ("batch-size", 32)):
        parser.add_argument("--" + name, type=int, default=default)
    parser.add_argument("--batch-delay-ms", type=float, default=2)
    parser.add_argument("--timeout-ms", type=float, default=1000)
    parser.add_argument("--drain-seconds", type=float, default=10)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--smoke", action="store_true", help="tool integrity only; does not make capacity gates pass")
    args = parser.parse_args(argv)
    values = vars(args).copy()
    output, smoke = values.pop("output"), values.pop("smoke")
    try:
        summary = run(Configuration(**values), output)
    except (ValueError, RuntimeError, ImportError, OSError) as exc:
        parser.exit(1, str(exc) + "\n")
    print(json.dumps(summary, indent=2))
    return 0 if smoke or summary["gates"]["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
