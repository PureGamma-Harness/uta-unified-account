"""Open-loop synthetic load generator with durable-admission evidence.

No scenario implements matching. A successful order operation consists of one
durable admission followed by local cancellation; rejects are never throughput.
Every offered arrival retains its original scheduled timestamp, including when
workers or the generator fall behind. Raw JSONL is the evidence of the run.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import platform
from queue import Empty, Full
import sqlite3
import subprocess
import sys
import threading
import time
import traceback

# Always benchmark the selected checkout, rather than an unrelated installed
# uta wheel. The override supports development worktrees; the resolved module
# source and hashes are recorded in every environment report.
sys.path.insert(0, str(Path(os.environ.get("UTA_BENCH_SOURCE_ROOT",
                                        Path(__file__).resolve().parent.parent)).resolve()))


@dataclass(frozen=True)
class Configuration:
    scenario: str = "order"
    duration: float = 1800
    rate: float = 10000
    workers: int = 4
    shards: int = 1
    accounts: int = 100
    account_skew: float = 0
    queue_capacity: int = 4096
    timeout_ms: float = 1000
    drain_seconds: float = 30
    min_accepted_rate: float = 10000
    min_duration: float = 1800
    max_p99_ms: float = 100
    profile: bool = False
    router_mode: bool = False

    def validate(self):
        if self.scenario not in {"compute", "order", "liquidation"}:
            raise ValueError("unsupported scenario")
        for name in ("duration", "rate", "timeout_ms", "drain_seconds",
                     "min_accepted_rate", "min_duration", "max_p99_ms"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        for name in ("workers", "shards", "accounts", "queue_capacity"):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if self.workers > 256 or self.shards > self.accounts or self.queue_capacity > 1000000:
            raise ValueError("workers <=256, shards <= accounts, queue_capacity <=1000000 required")
        if not 0 <= self.account_skew <= 1 or not math.isfinite(self.account_skew):
            raise ValueError("account_skew must be between zero and one")
        if int(self.duration * self.rate) < 1:
            raise ValueError("scenario must offer at least one arrival")
        if self.router_mode and (self.scenario != "order" or self.duration > 10 or self.drain_seconds > 10):
            raise ValueError("router probe requires order scenario, duration <=10s and drain <=10s; no long matching acceptance")


class LatencyHistogram:
    """Upper-bound percentiles with <=0.1% relative bin width, bounded memory.

    Raw rows keep exact nanoseconds. This histogram avoids retaining millions of
    Python integers and reports its approximation instead of hiding sampling.
    """
    _log_width = math.log1p(0.001)

    def __init__(self):
        self.buckets = Counter()
        self.count = 0

    def observe(self, nanoseconds: int):
        if type(nanoseconds) is not int or nanoseconds < 0:
            raise ValueError("latency must be nonnegative integer nanoseconds")
        key = math.ceil(math.log1p(nanoseconds) / self._log_width) if nanoseconds else 0
        self.buckets[key] += 1
        self.count += 1

    def percentile_ns(self, fraction: float):
        if not self.count:
            return None
        rank = max(1, math.ceil(fraction * self.count))
        seen = 0
        for key, count in sorted(self.buckets.items()):
            seen += count
            if seen >= rank:
                return math.ceil(math.expm1(key * self._log_width))

    def report(self):
        return {name: None if (value := self.percentile_ns(percentile)) is None else value / 1e6
                for name, percentile in (("p50", .5), ("p95", .95), ("p99", .99), ("p99_9", .999))}


PRODUCTS = (("BTC-PERP", "100"), ("ETH-PERP", "200"), ("SOL-PERP", "10"))


def _snapshot(version):
    from uta.market import MarketSnapshot
    from uta.models import AssetSpec, InstrumentSpec
    return MarketSnapshot(version, datetime.now(timezone.utc),
                          {"USD": AssetSpec(Decimal(1), Decimal(1))},
                          {symbol: InstrumentSpec(Decimal(price), Decimal(".1"), Decimal(".05"))
                           for symbol, price in PRODUCTS})


def _service(path):
    from uta.service import ExchangeService
    from uta.storage import Database
    return ExchangeService(Database(path, timeout=2), {"USD": 8})


def _router(directory, shard_count):
    from uta.sharding import ShardRouter
    # This is a short capacity probe with one fresh initial synthetic market,
    # not a market-feed throughput test. All shard counts use identical policy.
    return ShardRouter(directory, shard_count, {"USD": 8}, max_price_age=timedelta(seconds=30))


def _setup(configuration, directory):
    paths = []
    if configuration.scenario != "order":
        return paths
    if configuration.router_mode:
        router = _router(directory / "authority", configuration.shards)
        router.publish_market(_snapshot(1))
        for account in range(configuration.accounts):
            customer = f"benchmark-{account}"
            router.create_account(customer)
            router.deposit(customer, "synthetic-funding", "USD", Decimal("100000000"))
        router.set_kill_switch(False)
        return [str(router._path(index)) for index in range(configuration.shards)]
    for shard in range(configuration.shards):
        path = directory / f"shard-{shard}.sqlite3"
        service = _service(path)
        service.publish_market(_snapshot(1))
        for account in range(shard, configuration.accounts, configuration.shards):
            account_id = f"benchmark-{account}"
            service.create_account(account_id)
            service.deposit(account_id, "synthetic-funding", "USD", Decimal("100000000"))
        service.set_kill_switch(False)
        paths.append(str(path))
    return paths


def _feeder(paths, output, stopped):
    try:
        services = [_service(path) for path in paths]
        version = 2
        output.put({"kind": "feeder_ready"})
        while not stopped.is_set():
            for shard, service in enumerate(services):
                try:
                    service.publish_market(_snapshot(version))
                except Exception as exc:
                    output.put({"kind": "market_feed_error", "shard": shard,
                                "error_type": type(exc).__name__, "at_ns": time.monotonic_ns()})
            version += 1
            stopped.wait(.5)
    except BaseException as exc:
        output.put({"kind": "worker_fatal", "worker": "market_feeder", "error_type": type(exc).__name__})


def _worker(number, configuration, paths, pending, output, profile_path):
    profiler = None
    if configuration.profile:
        import cProfile
        profiler = cProfile.Profile()
    try:
        router = _router(Path(paths[0]).parent, configuration.shards) if configuration.router_mode else None
        services = [_service(path) for path in paths] if router is None else []
        from uta.models import Account, AssetSpec, InstrumentSpec, Position
        from uta.risk import calculate_risk, RiskSnapshot
        from uta.liquidation import LiquidationController, TimedRisk, PositionReduction
        assets = {"USD": AssetSpec(Decimal(1), Decimal(1))}
        instruments = {symbol: InstrumentSpec(Decimal(price), Decimal(".1"), Decimal(".05"))
                       for symbol, price in PRODUCTS}
        account = Account({"USD": Decimal("100000")},
                          {symbol: Position(symbol, Decimal("1"), Decimal(price)) for symbol, price in PRODUCTS})
        distress = RiskSnapshot(Decimal(5), Decimal(20), Decimal(10), Decimal(0), Decimal(-15), Decimal(".5"))
        output.put({"kind": "worker_ready", "worker": number})
        if profiler:
            profiler.enable()
        while (task := pending.get()) is not None:
            sequence, scheduled, account_index = task
            started = time.monotonic_ns()
            committed = False
            row = {"kind": "arrival", "sequence": sequence, "scheduled_ns": scheduled,
                   "started_ns": started, "worker": number, "account": account_index,
                   "symbol": PRODUCTS[sequence % len(PRODUCTS)][0], "durable_committed": False}
            try:
                if configuration.scenario == "compute":
                    calculate_risk(account, assets, instruments)
                    outcome = "compute_completed"
                elif configuration.scenario == "liquidation":
                    now = datetime.now(timezone.utc)
                    controller = LiquidationController(f"simulation-{sequence}")
                    action = controller.next_action(TimedRisk(distress, now), now=now)
                    controller.acknowledge(action.action_id, success=True, now=now)
                    controller.next_action(TimedRisk(distress, now), now=now,
                                           reduction=PositionReduction("BTC-PERP", Decimal(1), Decimal(".1")))
                    outcome = "simulation_completed"
                else:
                    customer, order_id = f"benchmark-{account_index}", f"order-{sequence}"
                    service = router if router is not None else services[account_index % configuration.shards]
                    row["shard"] = router.shard_for(customer) if router is not None else account_index % configuration.shards
                    symbol, price = PRODUCTS[sequence % len(PRODUCTS)]
                    service.submit_order(customer, order_id, symbol, Decimal(".001"), Decimal(price))
                    committed = True
                    # A separate cancellation transaction bounds outstanding
                    # orders. Its cost is deliberately included in latency/rate.
                    service.cancel_order(customer, order_id)
                    outcome = "durable_accepted"
            except Exception as exc:
                from uta.service import ServiceError
                row["error_type"] = type(exc).__name__
                row["error_code"] = getattr(exc, "code", None)
                if isinstance(exc, ServiceError) and exc.status < 500:
                    outcome = "business_rejected"
                else:
                    outcome = "technical_failed"
                    if configuration.scenario == "order" and not committed:
                        row["durability_unknown"] = True
            completed = time.monotonic_ns()
            row.update(completed_ns=completed, latency_ns=completed - scheduled,
                       service_ns=completed - started, durable_committed=committed,
                       outcome=outcome, deadline_exceeded=completed - scheduled > configuration.timeout_ms * 1e6)
            output.put(row)
    except BaseException as exc:
        output.put({"kind": "worker_fatal", "worker": number, "error_type": type(exc).__name__,
                    "traceback": traceback.format_exc(limit=3)})
    finally:
        if profiler:
            profiler.disable()
            profiler.dump_stats(profile_path)


def environment(paths):
    import uta
    source = Path(uta.__file__).resolve().parent.parent
    def command(*args):
        try:
            return subprocess.check_output(args, cwd=source, text=True, stderr=subprocess.DEVNULL).strip()
        except (OSError, subprocess.CalledProcessError):
            return None
    cpu = None
    memory_kib = None
    try:
        cpu = next(line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                   if line.startswith("model name"))
        memory_kib = int(next(line.split()[1] for line in Path("/proc/meminfo").read_text().splitlines()
                              if line.startswith("MemTotal:")))
    except (OSError, StopIteration, ValueError):
        pass
    stores = []
    for path in paths:
        with sqlite3.connect(Path(path).as_uri() + "?mode=ro", uri=True) as connection:
            stores.append({"path": path, "journal_mode": connection.execute("PRAGMA journal_mode").fetchone()[0],
                           "synchronous_configured": "FULL (every Database connection)",
                           "sqlite_version": sqlite3.sqlite_version,
                           "filesystem": command("df", "-T", path)})
    cgroup = {}
    for name in ("cpu.max", "memory.max"):
        try:
            cgroup[name] = Path("/sys/fs/cgroup", name).read_text().strip()
        except OSError:
            cgroup[name] = None
    return {"commit_sha": command("git", "rev-parse", "HEAD"),
            "working_tree_dirty": bool(command("git", "status", "--porcelain")),
            "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "source_sha256": {name: hashlib.sha256((source / "uta" / name).read_bytes()).hexdigest()
                              for name in ("service.py", "storage.py", "models.py", "market.py", "risk.py", "liquidation.py", "sharding.py")
                              if (source / "uta" / name).exists()},
            "source": str(source), "python": sys.version, "platform": platform.platform(),
            "cpu_model": cpu, "cpu_count": os.cpu_count(), "memory_kib": memory_kib,
            "cgroup_limits": cgroup,
            "cpu_affinity_count": len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
            "storage": stores, "multiprocessing_start_method": "spawn"}


def gates(configuration, duration, accepted_rate, p99, counts):
    failures = []
    if configuration.scenario != "order":
        failures.append("scenario does not measure durable order admission")
    if duration < configuration.min_duration:
        failures.append("duration below required minimum")
    if accepted_rate < configuration.min_accepted_rate:
        failures.append("unique successful durable admission rate below required minimum")
    if p99 is None or p99 > configuration.max_p99_ms:
        failures.append("p99 latency above threshold or unavailable")
    if any(counts.get(name, 0) for name in ("technical_failed", "unknown", "overload", "deadline_exceeded", "worker_fatal", "duplicate_results", "source_changed")):
        failures.append("technical failures, timeouts, unknown results or overload occurred")
    return {"passed": not failures, "failures": failures,
            "min_accepted_per_s": configuration.min_accepted_rate,
            "min_duration_s": configuration.min_duration, "max_p99_ms": configuration.max_p99_ms,
            "latency_policy": "temporary benchmark target; user has not supplied a production latency SLO",
            "scope": "synthetic durable admission plus local cancellation only; excludes matching",
            "phase1_exchange_acceptance_passed": False,
            "phase1_blocker": "No real matching workload or production acceptance is implemented by this benchmark"}


def run(configuration: Configuration, directory: Path):
    configuration.validate()
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    paths = _setup(configuration, directory)
    metadata = environment(paths)
    (directory / "environment.json").write_text(json.dumps(metadata, indent=2) + "\n")
    total = int(configuration.rate * configuration.duration)
    seen = bytearray(total)
    counts = Counter()
    outcomes = Counter()
    products = Counter()
    histograms = {name: LatencyHistogram() for name in ("all", "successful", "durable", "service")}
    ctx = mp.get_context("spawn")
    pending = ctx.Queue(configuration.queue_capacity)
    results = ctx.Queue(configuration.queue_capacity)
    stopped = ctx.Event()
    processes = [ctx.Process(target=_worker, args=(number, configuration, paths, pending, results,
                                                  str(directory / f"worker-{number}.prof")))
                 for number in range(configuration.workers)]
    feeder = ctx.Process(target=_feeder, args=(paths, results, stopped)) if paths and not configuration.router_mode else None
    raw = (directory / "arrivals.jsonl").open("x", encoding="utf-8")
    fatal_collector = []
    last_completion = [0]

    def collect():
        try:
            while True:
                row = results.get()
                if row.get("kind") == "collector_stop":
                    break
                raw.write(json.dumps(row, separators=(",", ":")) + "\n")
                if row.get("kind") != "arrival":
                    counts[row["kind"]] += 1
                    continue
                sequence = row["sequence"]
                if not 0 <= sequence < total or seen[sequence]:
                    counts["duplicate_results"] += 1
                    continue
                seen[sequence] = 1
                counts["received_unique"] += 1
                outcomes[row["outcome"]] += 1
                products[row["symbol"]] += 1
                counts["durable_committed_acknowledged"] += int(row.get("durable_committed", False))
                counts["deadline_exceeded"] += int(row.get("deadline_exceeded", False))
                if row["outcome"] == "durable_accepted":
                    histograms["durable"].observe(row["latency_ns"])
                if row["outcome"] != "overload":
                    histograms["all"].observe(row["latency_ns"])
                    histograms["service"].observe(row["service_ns"])
                if row["outcome"] in {"compute_completed", "simulation_completed", "durable_accepted"} and not row["deadline_exceeded"]:
                    counts["successful_on_time"] += 1
                    histograms["successful"].observe(row["latency_ns"])
                last_completion[0] = max(last_completion[0], row["completed_ns"])
        except BaseException as exc:
            fatal_collector.append(str(exc))

    collector = threading.Thread(target=collect, daemon=True)
    start = time.monotonic_ns()
    try:
        for process in processes + ([feeder] if feeder else []):
            process.start()
        ready_count = len(processes) + int(feeder is not None)
        for _ in range(ready_count):
            row = results.get(timeout=30)
            raw.write(json.dumps(row, separators=(",", ":")) + "\n")
            if row["kind"] not in {"worker_ready", "feeder_ready"}:
                raise RuntimeError(f"worker initialization failed: {row}")
        collector.start()
        start = time.monotonic_ns() + 100000000
        for sequence in range(total):
            scheduled = start + int(sequence * 1e9 / configuration.rate)
            remaining = (scheduled - time.monotonic_ns()) / 1e9
            if remaining > 0:
                time.sleep(remaining)
            mixed = ((sequence + 1) * 11400714819323198485) & ((1 << 64) - 1)
            account = 0 if mixed % 10000 < int(configuration.account_skew * 10000) else (
                (mixed >> 32) % configuration.accounts)
            try:
                pending.put_nowait((sequence, scheduled, account))
            except Full:
                completed = time.monotonic_ns()
                results.put({"kind": "arrival", "sequence": sequence, "scheduled_ns": scheduled,
                             "started_ns": completed, "completed_ns": completed,
                             "latency_ns": completed - scheduled, "service_ns": 0,
                             "account": account, "symbol": PRODUCTS[sequence % len(PRODUCTS)][0],
                             "outcome": "overload", "durable_committed": False,
                             "deadline_exceeded": False})
            if fatal_collector:
                raise RuntimeError("raw evidence writer failed")
        # Give only a bounded drain interval. Unreported operations after a
        # forced stop are UNKNOWN, because a commit may precede lost response.
        drain_deadline = time.monotonic() + configuration.drain_seconds
        for _ in processes:
            while time.monotonic() < drain_deadline:
                try:
                    pending.put(None, timeout=.1)
                    break
                except Full:
                    continue
        for process in processes:
            process.join(max(0, drain_deadline - time.monotonic()))
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(5)
        stopped.set()
        if feeder:
            feeder.join(5)
            if feeder.is_alive():
                feeder.terminate()
                feeder.join(5)
        results.put({"kind": "collector_stop"})
        collector.join(10)
        if collector.is_alive() or fatal_collector:
            raise RuntimeError("raw evidence collector did not finish")
        for sequence, received in enumerate(seen):
            if not received:
                outcomes["unknown"] += 1
                raw.write(json.dumps({"kind": "arrival", "sequence": sequence, "outcome": "unknown",
                                      "scheduled_ns": start + int(sequence * 1e9 / configuration.rate),
                                      "durability_unknown": configuration.scenario == "order"}) + "\n")
        raw.flush()
        os.fsync(raw.fileno())
        elapsed = max(configuration.duration, (last_completion[0] - start) / 1e9)
        accepted = outcomes["durable_accepted"] if configuration.scenario == "order" else 0
        combined = counts + outcomes
        for name in ("durable_accepted", "business_rejected", "technical_failed", "unknown", "overload",
                     "deadline_exceeded", "worker_fatal", "duplicate_results", "successful_on_time"):
            combined.setdefault(name, 0)
        durable_latency = histograms["durable"].report()
        final_environment = environment(paths)
        if metadata["source_sha256"] != final_environment["source_sha256"]:
            combined["source_changed"] = 1
        durability = []
        for path in paths:
            with sqlite3.connect(Path(path).as_uri() + "?mode=ro", uri=True) as connection:
                durability.append({"shard": path, "unique_orders_in_database": connection.execute(
                    "SELECT COUNT(*) FROM uta_orders").fetchone()[0],
                    "accepted_events_in_database": connection.execute(
                    "SELECT COUNT(*) FROM uta_events WHERE event_type='ORDER_ACCEPTED'").fetchone()[0]})
        summary = {"configuration": asdict(configuration), "environment": metadata,
                   "routing": "real ShardRouter SHA-256 + flock/control gate" if configuration.router_mode else "direct independent databases; idealized shard bound",
                   "market_feed": "one initial fresh snapshot, 30s age policy; excludes fanout throughput" if configuration.router_mode else "synthetic 0.5s feeder",
                   "scope": {"compute": "three-position risk arithmetic only",
                             "order": "durable local admission + cancellation, no fill/matching",
                             "liquidation": "in-memory cancellation/reduction state-machine simulation"}[configuration.scenario],
                   "offered_arrivals": total, "arrival_window_s": configuration.duration,
                   "completion_window_s": elapsed, "counts": dict(combined),
                   "successful_completions_per_s": counts["successful_on_time"] / elapsed,
                   "unique_durable_accepted_per_s": accepted / elapsed,
                   "on_time_durable_accepted_per_s": counts["successful_on_time"] / elapsed if paths else 0,
                   "acknowledged_durable_commits_per_s": counts["durable_committed_acknowledged"] / elapsed,
                   "final_source_commit_sha": final_environment["commit_sha"],
                   "product_distribution": dict(products), "durability_checks": durability,
                   "latency_ms": {name: histogram.report() for name, histogram in histograms.items()},
                   "quantile_method": "log histogram upper bounds; <=0.1% relative bin width; raw ns exact",
                   "timeout_semantics": "soft scheduled-arrival deadline; late durable commits remain recorded",
                   "gates": gates(configuration, configuration.duration, accepted / elapsed,
                                  durable_latency["p99"], combined)}
        (directory / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        return summary
    finally:
        stopped.set()
        for process in processes + ([feeder] if feeder else []):
            if process.is_alive():
                process.terminate()
                process.join(5)
        raw.close()
        pending.cancel_join_thread()
        results.cancel_join_thread()
        pending.close()
        results.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="new directory for raw evidence and databases")
    parser.add_argument("--scenario", choices=("compute", "order", "liquidation"), default="order")
    for name, kind, default in (("duration", float, 1800), ("rate", float, 10000),
                                ("workers", int, 4), ("shards", int, 1), ("accounts", int, 100),
                                ("account-skew", float, 0), ("queue-capacity", int, 4096),
                                ("timeout-ms", float, 1000), ("drain-seconds", float, 30),
                                ("min-accepted-rate", float, 10000), ("min-duration", float, 1800),
                                ("max-p99-ms", float, 100)):
        parser.add_argument("--" + name, type=kind, default=default)
    parser.add_argument("--profile", action="store_true", help="write per-worker cProfile artifacts (adds overhead)")
    parser.add_argument("--router-mode", action="store_true", help="short real ShardRouter probe; duration/drain <=10s, no feeder")
    parser.add_argument("--smoke", action="store_true", help="tool check only; does not turn failed gates into a pass")
    args = vars(parser.parse_args(argv))
    directory, smoke = args.pop("output"), args.pop("smoke")
    try:
        summary = run(Configuration(**args), directory)
    except (ValueError, OSError, RuntimeError, Empty) as exc:
        parser.exit(1, f"benchmark failed: {exc}\n")
    print(json.dumps({"summary": str(directory / "summary.json"),
                      "unique_durable_accepted_per_s": summary["unique_durable_accepted_per_s"],
                      "successful_completions_per_s": summary["successful_completions_per_s"],
                      "latency_ms": summary["latency_ms"], "gates": summary["gates"]}, indent=2))
    return 0 if smoke or summary["gates"]["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
