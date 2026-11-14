#!/usr/bin/env python3
"""Reproducible local workloads for PM computation and durable liquidation."""
from __future__ import annotations

import argparse
from collections import Counter, deque
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal as D, ROUND_DOWN
from functools import partial
import json
import math
import multiprocessing
import os
from pathlib import Path
import platform
import sqlite3
import sys
from tempfile import TemporaryDirectory
from time import perf_counter_ns, sleep

# Also support execution as python scripts/benchmark_pm.py from a checkout.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uta.models import Account, AssetSpec, InstrumentSpec, Position
from uta.portfolio import calculate_portfolio, position_im_bound

_START_BARRIER = None
_SIM_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)


@dataclass
class WorkloadResult:
    timings: dict[str, list[int]] = field(default_factory=dict)
    counts: Counter = field(default_factory=Counter)
    started_ns: int | None = None
    finished_ns: int | None = None

    def measure(self, name, operation):
        start = perf_counter_ns()
        try:
            return operation()
        finally:
            elapsed = perf_counter_ns() - start
            self.timings.setdefault(name, []).append(elapsed)


class BenchmarkError(RuntimeError):
    """A benchmark fixture or correctness invariant did not hold."""


def require(condition, message):
    if not condition:
        raise BenchmarkError(message)


def _set_barrier(barrier):
    global _START_BARRIER
    _START_BARRIER = barrier


def _start(result):
    if _START_BARRIER is not None:
        _START_BARRIER.wait()
    result.started_ns = perf_counter_ns()


def _arrivals(staged, result, *, target_rate, worker_id, workers, max_pending):
    """Generate each arrival by its planned timestamp, independent of completion."""
    if target_rate is None:
        for item in staged:
            yield item, None
        return

    pending = deque()
    next_index = 0
    result.counts["scheduled_arrivals"] = len(staged)
    result.counts["overload_rejections"] = 0
    result.counts["max_pending_observed"] = 0

    def scheduled(index):
        sequence = index * workers + worker_id
        return result.started_ns + sequence * 1_000_000_000 // target_rate

    while pending or next_index < len(staged):
        now = perf_counter_ns()
        while next_index < len(staged) and scheduled(next_index) <= now:
            if len(pending) >= max_pending:
                result.counts["overload_rejections"] += 1
            else:
                pending.append(next_index)
            next_index += 1
        result.counts["max_pending_observed"] = max(result.counts["max_pending_observed"], len(pending))
        if pending:
            index = pending.popleft()
            yield staged[index], scheduled(index)
        elif next_index < len(staged):
            sleep(max(0, scheduled(next_index) - perf_counter_ns()) / 1_000_000_000)


def _compute(worker_id, *, cases):
    result = WorkloadResult()
    # Marks are a deterministic 40–100% of the entry levels. Each worker mixes
    # unhedged and partially hedged portfolios to exercise binding scenarios.
    assets_by_price = []
    for scale in range(40, 101):
        assets_by_price.append((
            {"USD": AssetSpec(D("1"), D("1")),
             "BTC": AssetSpec(D(500 * scale), D("0.8")),
             "ETH": AssetSpec(D(30 * scale), D("0.7"))},
            {"BTC-PERP": InstrumentSpec(D(500 * scale), D("0.10"), D("0.05")),
             "ETH-PERP": InstrumentSpec(D(30 * scale), D("0.12"), D("0.06"))},
        ))
    accounts = [
        Account(
            balances={"USD": D(700 + index * 75), "BTC": D("0.02"), "ETH": D("0.5")},
            liabilities={"ETH": D("0.2")},
            positions={"BTC-PERP": Position("BTC-PERP", D("-0.06" if index % 4 == 0 else "0.08"),
                                            D("50000")),
                       "ETH-PERP": Position("ETH-PERP", D("-0.6" if index % 2 else "0.15"),
                                            D("3000"))},
        )
        for index in range(17)
    ]

    _start(result)
    for index in range(cases):
        account = accounts[(index + worker_id) % len(accounts)]
        assets, instruments = assets_by_price[(19 * index + worker_id) % len(assets_by_price)]

        def check():
            risk = calculate_portfolio(account, assets, instruments)
            fee = D("0.0004") * instruments["BTC-PERP"].mark_price
            reserve = D("0.01") * (position_im_bound("BTC-PERP", instruments["BTC-PERP"]) + fee)
            return risk, risk.equity > risk.maintenance_margin and risk.available_margin >= reserve

        risk, accepted = result.measure("scenario_pm_and_order_check", check)
        result.counts["requests"] += 1
        result.counts["accepted" if accepted else "risk_rejections"] += 1
        if risk.equity <= risk.maintenance_margin:
            result.counts["maintenance_breaches"] += 1
        if risk.worst_scenario:
            result.counts["worst_scenario_" + risk.worst_scenario] += 1
    result.finished_ns = perf_counter_ns()
    return result


def _text(number):
    return format(number, "f")


def _sim_time():
    # Independent of workload size: vary quotes without aging the synthetic feed.
    return _SIM_TIME


def _stage(sim, account_id):
    view = sim.bootstrap(account_id)
    initial = view["state"]
    instrument = "BTC-PERP"
    mark = D(initial["marks"][instrument])
    fee = D("0.0004")
    available = D(view["risk"]["available_margin"])
    # Approximate a reasonably severe portfolio before the shock. The per-unit
    # bound is 15% of BTC mark with the current model and default parameters.
    im_rate = D(initial["instruments"][instrument]["initial_margin_rate"])
    reserve_rate = max(im_rate, D("0.15")) + fee
    quantity = (available * D("0.7") / (mark * reserve_rate)).quantize(D("0.000001"), rounding=ROUND_DOWN)
    require(quantity > 0, "default account has insufficient opening margin for the workload")
    placed = sim.execute(
        account_id, "opening-order", initial["version"],
        {"type": "place_order", "symbol": instrument, "quantity": _text(quantity),
         "limit_price": _text(mark), "fee_rate": _text(fee)},
    )
    filled = sim.execute(
        account_id, "opening-fill", placed["version"],
        {"type": "fill_order", "order_id": "opening-order", "quantity": _text(quantity),
         "price": _text(mark)},
    )
    view = sim.view(account_id)
    require(view["state"]["version"] == filled["version"], "opening fill receipt differs from state")
    require(_position_qty(view) == quantity, "opening fill did not create the expected position")
    # Leave one resting order to exercise the cancel phase during liquidation.
    placed = sim.execute(
        account_id, "resting-order", filled["version"],
        {"type": "place_order", "symbol": instrument,
         "quantity": _text((quantity / 10).quantize(D("0.000001"), rounding=ROUND_DOWN)),
         "limit_price": _text(mark), "fee_rate": _text(fee)},
    )
    prices = {asset: (_text(D(p) * D("0.55")) if asset != "USD" else p)
              for asset, p in initial["prices"].items()}
    marks = {symbol: _text(D(price) * D("0.55")) for symbol, price in initial["marks"].items()}
    return placed["version"], {"type": "set_prices", "prices": prices, "marks": marks}


def _position_qty(view):
    position = view["state"]["positions"].get("BTC-PERP")
    return D(position["quantity"]) if position is not None else D(0)


def _admission(worker_id, *, cases, directory, shards, target_rate, workers, max_pending):
    from uta.simulator import Simulator, SimulatorError

    result = WorkloadResult()
    path = Path(directory) / "admission.sqlite3"
    sim = Simulator(path, clock=_sim_time, shards=shards)
    staged = []
    for index in range(cases):
        account_id = f"admission-{worker_id}-{index}"
        try:
            state = sim.bootstrap(account_id)["state"]
            accepted = index % 4 != 0
            command = {"type": "place_order", "symbol": "BTC-PERP",
                       "quantity": "0.1" if accepted else "100", "fee_rate": "0.0004",
                       "limit_price": state["marks"]["BTC-PERP"]}
            staged.append((account_id, state["version"], command, accepted))
            result.counts["staged_accounts"] += 1
        except Exception as exc:
            _error(result, "staging", account_id, exc)

    _start(result)
    verified = []
    for item, scheduled in _arrivals(staged, result, target_rate=target_rate,
                                     worker_id=worker_id, workers=workers, max_pending=max_pending):
        account_id, version, command, should_accept = item
        result.counts["admission_requests"] += 1
        try:
            try:
                receipt = result.measure("durable_order_check", lambda: sim.execute(
                    account_id, "admission-order", version, command,
                ))
            except SimulatorError as exc:
                if should_accept or "insufficient portfolio initial margin" not in str(exc):
                    raise
                result.counts["risk_rejections"] += 1
            else:
                require(should_accept and receipt["version"] == version + 1
                        and receipt["action"] == "order_placed", "unexpected order acceptance")
                result.counts["orders_committed"] += 1
            verified.append((account_id, version + int(should_accept)))
        except Exception as exc:
            _error(result, "processing", account_id, exc)
        finally:
            if scheduled is not None:
                result.timings.setdefault("admission_from_scheduled_arrival", []).append(
                    perf_counter_ns() - scheduled)
    result.finished_ns = perf_counter_ns()

    reopened = Simulator(path, clock=_sim_time, shards=shards)
    for account_id, version in verified:
        try:
            state = reopened.view(account_id)["state"]
            events = reopened.events(account_id)
            require(state["version"] == version and len(events) == version + 1
                    and bool(state["orders"]) == (version > 0),
                    "admission result did not match state and audit trail")
            result.counts["reopened_accounts_verified"] += 1
        except Exception as exc:
            _error(result, "persistence", account_id, exc)
    return result


def _error(result, phase, account_id, exc):
    key = phase + "_error_" + type(exc).__name__
    result.counts[key] += 1
    if result.counts[key] == 1:
        print(f"{phase} {account_id}: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)


def _durable(worker_id, *, cases, directory, shards, target_rate, workers, max_pending):
    from uta.simulator import Simulator

    result = WorkloadResult()
    path = Path(directory) / "liquidation.sqlite3"
    sim = Simulator(path, clock=_sim_time, shards=shards)
    staged = []
    for index in range(cases):
        account_id = f"burst-{worker_id}-{index}"
        try:
            version, shock = _stage(sim, account_id)
            staged.append((account_id, version, shock))
            result.counts["staged_accounts"] += 1
        except Exception as exc:
            _error(result, "staging", account_id, exc)

    _start(result)
    verified = []
    for item, scheduled in _arrivals(staged, result, target_rate=target_rate,
                                     worker_id=worker_id, workers=workers, max_pending=max_pending):
        account_id, version, shock = item
        account_started = perf_counter_ns()
        try:
            before = sim.view(account_id)
            repriced = result.measure("durable_market_update", lambda: sim.execute(
                account_id, "crash", version, shock,
            ))
            result.counts["market_updates_committed"] += 1
            breached = sim.view(account_id)
            require(D(breached["risk"]["equity"]) <= D(breached["risk"]["maintenance_margin"]),
                    "stress shock did not breach maintenance margin")
            result.counts["maintenance_breaches"] += 1
            version = repriced["version"]
            for step in range(32):
                previous = sim.view(account_id)
                if (previous["health"] == "HEALTHY"
                        or (not previous["state"]["positions"] and not any(
                            order["status"] == "OPEN" for order in previous["state"]["orders"].values()
                        ))):
                    break
                command_id = f"liquidate-{step}"
                receipt = result.measure("durable_liquidation_step", lambda: sim.execute(
                    account_id, command_id, version, {"type": "liquidate"},
                ))
                require(receipt["version"] == version + 1, "liquidation did not advance account version")
                version = receipt["version"]
                current = sim.view(account_id)
                result.counts["liquidation_commands_committed"] += 1
                old_position = _position_qty(previous)
                new_position = _position_qty(current)
                require(abs(new_position) <= abs(old_position) and new_position * old_position >= 0,
                        "liquidation increased or reversed a position")
                if abs(new_position) < abs(old_position):
                    require(receipt["action"] == "liquidation_fill" and receipt["fills"],
                            "reduced position has no liquidation fill receipt")
                    for fill in receipt["fills"]:
                        total = sum(D(posting["amount"]) for posting in fill["journal"])
                        require(total == 0, "liquidation journal does not balance")
                    result.counts["position_reductions_committed"] += 1
                    result.counts["liquidation_fills_committed"] += len(receipt["fills"])
                else:
                    require(receipt["action"] == "liquidation_cancel",
                            "liquidation made neither a fill nor an order cancellation")
                    result.counts["liquidation_cancellations_committed"] += 1
            final = sim.view(account_id)
            require(abs(_position_qty(final)) < abs(_position_qty(before)), "liquidation left exposure unchanged")
            require(final["health"] == "HEALTHY" or not final["state"]["positions"],
                    "liquidation exhausted the bounded step budget")
            require(not any(order["status"] == "OPEN" for order in final["state"]["orders"].values()),
                    "liquidation left a resting order open")
            events = sim.events(account_id)
            require([event["version"] for event in events] == list(range(version + 1)),
                    "committed events have a version gap")
            verified.append((account_id, version, _position_qty(final)))
            result.counts["account_liquidations_completed"] += 1
            result.counts["end_health_" + final["health"]] += 1
            result.counts["end_positions_open" if final["state"]["positions"] else "end_positions_flat"] += 1
        except Exception as exc:
            _error(result, "processing", account_id, exc)
        finally:
            now = perf_counter_ns()
            result.timings.setdefault("verified_account_lifecycle", []).append(
                now - account_started)
            if scheduled is not None:
                result.timings.setdefault("liquidation_from_scheduled_arrival", []).append(
                    now - scheduled)

    result.finished_ns = perf_counter_ns()
    result.counts["accounts_not_completed"] = cases - result.counts["account_liquidations_completed"]
    # Audit the completed snapshots through a fresh process-local store facade
    # outside the timer. SQLite connections used by commands are already closed.
    reopened = Simulator(path, clock=_sim_time, shards=shards)
    for account_id, version, quantity in verified:
        try:
            snapshot = reopened.view(account_id)
            require(snapshot["state"]["version"] == version and _position_qty(snapshot) == quantity,
                    "reopened snapshot differs from last committed state")
            result.counts["reopened_accounts_verified"] += 1
        except Exception as exc:
            _error(result, "persistence", account_id, exc)
    return result


def _batch_round(sim, result, operation, items):
    envelopes = [{"account_id": account, "command_id": command_id,
                  "expected_version": version, "command": command}
                 for account, command_id, version, command in items]
    replies = result.measure(operation, lambda: sim.execute_batch(envelopes))
    require(len(replies) == len(items), "group response omitted commands")
    committed = []
    for (account, _, version, _), reply in zip(items, replies):
        if reply["ok"] and reply["receipt"]["version"] == version + 1:
            committed.append((account, reply["receipt"]))
        else:
            _error(result, "processing", account, BenchmarkError(repr(reply)))
    return committed


def _durable_batch(worker_id, *, cases, directory, shards, batch_size, fused):
    from uta.simulator import Simulator

    path = Path(directory) / "group-commit.sqlite3"
    sim = Simulator(path, clock=_sim_time, shards=shards)
    result = WorkloadResult()
    staged = []
    for index in range(cases):
        account = f"group-{worker_id}-{index}"
        try:
            version, command = _stage(sim, account)
            staged.append((account, "crash", version, command))
        except Exception as exc:
            _error(result, "staging", account, exc)
    result.counts["staged_accounts"] = len(staged)

    _start(result)
    verified = []
    for offset in range(0, len(staged), batch_size):
        cohort_start = perf_counter_ns()
        items = staged[offset:offset + batch_size]
        if fused:
            combined = [(account, command_id, version, dict(command, type="mark_and_liquidate"))
                        for account, command_id, version, command in items]
            filled = _batch_round(sim, result, "group_mark_and_liquidate", combined)
            result.counts["market_updates_committed"] += len(filled)
            for account, receipt in filled:
                actions = receipt.get("liquidation_actions", [])
                if ([action["action"] for action in actions] != ["liquidation_cancel", "liquidation_fill"]
                        or receipt["liquidation_pending"]):
                    _error(result, "processing", account, BenchmarkError("incomplete combined liquidation"))
                    continue
                result.counts["maintenance_breaches"] += 1
                result.counts["liquidation_cancellations_committed"] += 1
                result.counts["liquidation_commands_committed"] += 1
        else:
            filled = _batch_liquidation_rounds(sim, result, items)
        for account, receipt in filled:
            try:
                if fused:
                    actions = receipt["liquidation_actions"]
                    fills = [fill for action in actions for fill in action.get("fills", [])]
                else:
                    require(receipt["action"] == "liquidation_fill", "unexpected liquidation receipt")
                    fills = receipt.get("fills", [])
                require(fills, "no executed liquidation fill")
                for fill in fills:
                    require(sum(D(posting["amount"]) for posting in fill["journal"]) == 0,
                            "liquidation journal does not balance")
                result.counts["liquidation_fills_committed"] += len(fills)
                view = sim.view(account)
                require(not view["state"]["positions"], "account remains positioned after crash close-out")
                require(not any(order["status"] == "OPEN" for order in view["state"]["orders"].values()),
                        "liquidation left a resting order open")
                version = receipt["version"]
                require(view["state"]["version"] == version
                        and [event["version"] for event in sim.events(account)] == list(range(version + 1)),
                        "account state or audit trail missed a group-committed result")
                verified.append((account, version))
                result.counts["account_liquidations_completed"] += 1
                result.counts["end_health_" + view["health"]] += 1
            except Exception as exc:
                _error(result, "processing", account, exc)
        result.timings.setdefault("verified_cohort_lifecycle", []).append(perf_counter_ns() - cohort_start)

    result.finished_ns = perf_counter_ns()
    result.counts["accounts_not_completed"] = cases - len(verified)
    reopened = Simulator(path, clock=_sim_time, shards=shards)
    for account, version in verified:
        try:
            state = reopened.view(account)["state"]
            require(state["version"] == version and not state["positions"],
                    "reopened positions or version differ from group-committed state")
            result.counts["reopened_accounts_verified"] += 1
        except Exception as exc:
            _error(result, "persistence", account, exc)
    return result


def _batch_liquidation_rounds(sim, result, items):
    repriced = _batch_round(sim, result, "group_market_update", items)
    result.counts["market_updates_committed"] += len(repriced)
    pending = []
    for account, receipt in repriced:
        if D(receipt["risk"]["equity"]) > D(receipt["risk"]["maintenance_margin"]):
            _error(result, "processing", account, BenchmarkError("no maintenance breach"))
            continue
        pending.append((account, "group-liquidate-0", receipt["version"], {"type": "liquidate"}))

    result.counts["maintenance_breaches"] += len(pending)
    canceled = _batch_round(sim, result, "group_liquidation_cancel", pending) if pending else []
    needs_fill = []
    for account, receipt in canceled:
        if receipt["action"] != "liquidation_cancel":
            _error(result, "processing", account, BenchmarkError("no cancellation"))
            continue
        needs_fill.append((account, "group-liquidate-1", receipt["version"], {"type": "liquidate"}))
    result.counts["liquidation_cancellations_committed"] += len(needs_fill)
    result.counts["liquidation_commands_committed"] += len(canceled)
    filled = _batch_round(sim, result, "group_liquidation_fill", needs_fill) if needs_fill else []
    result.counts["liquidation_commands_committed"] += len(filled)
    return filled


def _percentile(values, percentile):
    index = math.ceil(len(values) * percentile / 100) - 1
    return round(values[index] / 1_000_000, 3)


def _summarize(results):
    timings = {}
    counts = Counter()
    for result in results:
        counts.update(result.counts)
        for operation, samples in result.timings.items():
            timings.setdefault(operation, []).extend(samples)
    if "max_pending_observed" in counts:
        counts["max_pending_observed"] = max(r.counts["max_pending_observed"] for r in results)
    started = min(r.started_ns for r in results if r.started_ns is not None)
    finished = max(r.finished_ns for r in results if r.finished_ns is not None)
    elapsed = (finished - started) / 1_000_000_000
    latencies = {}
    for operation, samples in sorted(timings.items()):
        samples.sort()
        latencies[operation] = {
            "attempts": len(samples),
            "p50_ms": _percentile(samples, 50),
            "p95_ms": _percentile(samples, 95),
            "p99_ms": _percentile(samples, 99),
        }
    return {
        "wall_seconds": round(elapsed, 6),
        "counts": dict(sorted(counts.items())),
        "rates_per_second": {key: round(counts[key] / elapsed, 2)
                             for key in ("requests", "admission_requests", "orders_committed",
                                         "market_updates_committed",
                                         "liquidation_commands_committed", "liquidation_fills_committed",
                                         "account_liquidations_completed") if key in counts},
        "errors": sum(value for key, value in counts.items() if "_error_" in key),
        "latencies": latencies,
    }


def _run(function, workers, cases, **kwargs):
    if "target_rate" in kwargs:
        kwargs["workers"] = workers
    worker = partial(function, cases=cases, **kwargs)
    if workers == 1:
        return _summarize([worker(0)])
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(workers, timeout=120)
    with ProcessPoolExecutor(max_workers=workers, mp_context=context, initializer=_set_barrier,
                             initargs=(barrier,)) as pool:
        return _summarize(list(pool.map(worker, range(workers))))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("all", "compute", "admission", "durable", "batch"), default="all")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--checks-per-worker", type=int, default=2000)
    parser.add_argument("--accounts-per-worker", type=int, default=20)
    parser.add_argument("--shards", type=int,
                        help="SQLite file count for durable workload (default: one per worker)")
    parser.add_argument("--target-rate", type=int,
                        help="Total planned arrivals/s for each durable mode; default is closed-loop")
    parser.add_argument("--max-pending", type=int, default=64,
                        help="Per-worker queue bound for paced arrival workloads")
    parser.add_argument("--batch-size", type=int, default=32,
                        help="Group commit cohort size in batch mode")
    parser.add_argument("--fused", action="store_true",
                        help="In batch mode, atomically reprice, cancel, and liquidate each account")
    parser.add_argument("--db-dir", type=Path,
                        help="Parent directory for temporary SQLite shards; shards are removed after the run")
    args = parser.parse_args(argv)
    if not 1 <= args.workers <= 64 or args.checks_per_worker < 1 or args.accounts_per_worker < 1:
        parser.error("workers must be 1–64, and both per-worker counts must be positive")
    shards = args.shards if args.shards is not None else args.workers
    if not 1 <= shards <= args.workers:
        parser.error("shards must be between 1 and the number of workers")
    if args.target_rate is not None and args.target_rate < 1:
        parser.error("target-rate must be positive")
    if args.max_pending < 1:
        parser.error("max-pending must be positive")
    if not 1 <= args.batch_size <= 256:
        parser.error("batch-size must be between 1 and 256")
    if args.mode == "batch" and args.target_rate is not None:
        parser.error("batch mode runs closed-loop without a target-rate")
    if args.fused and args.mode != "batch":
        parser.error("--fused requires --mode batch")
    output = {
        "workload": "linear-pm-synthetic-v1",
        "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version,
        "platform": platform.platform(),
        "cpu_count": len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else os.cpu_count(),
        "workers": args.workers,
    }
    if args.mode in {"all", "compute"}:
        output["compute"] = _run(_compute, args.workers, args.checks_per_worker)
    if args.mode in {"all", "admission", "durable", "batch"}:
        with TemporaryDirectory(prefix="uta-pm-warehouse-", dir=args.db_dir) as directory:
            output["durable_shards"] = shards
            if args.target_rate is not None:
                output["offered_arrivals_per_second"] = args.target_rate
                output["max_pending_per_worker"] = args.max_pending
            workload_options = dict(directory=directory, shards=shards,
                                    target_rate=args.target_rate, max_pending=args.max_pending)
            if args.mode in {"all", "admission"}:
                output["admission"] = _run(_admission, args.workers, args.accounts_per_worker,
                                           **workload_options)
            if args.mode in {"all", "durable"}:
                output["durable"] = _run(_durable, args.workers, args.accounts_per_worker,
                                         **workload_options)
            if args.mode == "batch":
                output["batch_size"] = args.batch_size
                output["fused"] = args.fused
                output["batch"] = _run(_durable_batch, args.workers, args.accounts_per_worker,
                                       directory=directory, shards=shards, batch_size=args.batch_size,
                                       fused=args.fused)
    print(json.dumps(output, indent=2, sort_keys=True))
    return int(any(output[mode]["errors"] for mode in ("compute", "admission", "durable", "batch")
                   if mode in output))


if __name__ == "__main__":
    sys.exit(main())
