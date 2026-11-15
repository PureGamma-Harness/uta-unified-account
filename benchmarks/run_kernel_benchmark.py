"""Repeat short, same-source cache A/B probes with alternating pair order.

This driver does not provide a long-lived market feeder or approve production.
Each run has a new database, fresh synthetic snapshot and empty service caches.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmarks.run_group_benchmark import Configuration, run


def plan(configuration=None, *, repetitions=3, reserve_cache_size=4096, market_cache_size=8):
    configuration = configuration or Configuration(mode="batch", rate=5000, batch_size=64)
    if configuration.mode != "batch" or configuration.policy != "configured_cross":
        raise ValueError("kernel comparison requires batch admission with configured_cross policy")
    if type(repetitions) is not int or not 2 <= repetitions <= 10:
        raise ValueError("repetitions must be an integer in 2..10")
    if reserve_cache_size <= 0 or market_cache_size <= 0:
        raise ValueError("optimized reserve and market cache capacities must both be positive")
    base = replace(configuration, reserve_cache_size=0, market_cache_size=0)
    optimized = replace(base, reserve_cache_size=reserve_cache_size, market_cache_size=market_cache_size)
    base.validate()
    optimized.validate()
    result = []
    for pair in range(repetitions):
        order = ("base", "optimized") if pair % 2 == 0 else ("optimized", "base")
        for position, variant in enumerate(order):
            result.append({"label": f"pair-{pair + 1:02d}-{variant}", "pair": pair + 1,
                           "position": position + 1, "variant": variant,
                           "configuration": asdict(base if variant == "base" else optimized)})
    return result


def _source_identity():
    def git(*args):
        return subprocess.check_output(("git", *args), cwd=ROOT, text=True).strip()
    files = [*(ROOT / "uta").glob("*.py"), *(ROOT / "benchmarks").glob("*.py")]
    return {"commit": git("rev-parse", "HEAD"),
            "tracked_changes": git("status", "--porcelain", "--untracked-files=no"),
            "source_sha256": {str(path.relative_to(ROOT)): sha256(path.read_bytes()).hexdigest()
                              for path in sorted(files)}}


def _assert_source(expected, reference=None):
    if len(expected) != 40 or any(character not in "0123456789abcdef" for character in expected):
        raise ValueError("expected source must be a complete lower-case 40-character commit SHA")
    identity = _source_identity()
    if identity["commit"] != expected or identity["tracked_changes"]:
        raise RuntimeError("frozen source SHA or clean tracked working tree check failed")
    if reference is not None and identity != reference:
        raise RuntimeError("runtime or generator source changed within paired cohort")
    return identity


def _observation(entry, summary, started_utc, finished_utc, elapsed):
    return {**{key: entry[key] for key in ("label", "pair", "position", "variant")},
            "configuration": summary["configuration"], "started_utc": started_utc, "finished_utc": finished_utc,
            "driver_wall_seconds": elapsed, "counts": summary["counts"],
            "unique_durable_accepted_per_s": summary["unique_durable_accepted_per_s"],
            "on_time_durable_accepted_per_s": summary["on_time_durable_accepted_per_s"],
            "measured_seconds_including_drain": summary["measured_seconds_including_drain"],
            "latency_ms": summary["latency_ms"], "cache_stats": summary["cache_stats"],
            "account_schedule_sha256": summary["workload"]["account_schedule_sha256"],
            "order_schedule_sha256": summary["workload"]["order_schedule_sha256"],
            "unknown_resolution": summary["unknown_resolution"], "gates": summary["gates"]}


def run_cohort(directory, expected_source, entries):
    reference = _assert_source(expected_source)
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "plan.json").write_text(json.dumps({"source": reference, "runs": entries}, indent=2) + "\n")
    observations = []
    # Rewrite the journal after every completed run; a failed cohort retains
    # earlier observations and each run's complete, separately hashed evidence.
    journal = {"source": reference, "runs": observations, "complete": False,
               "production_approved": False, "scope": "short admission-only cache comparison"}
    journal_path = directory / "run-window.json"
    journal_path.write_text(json.dumps(journal, indent=2) + "\n")
    try:
        for entry in entries:
            _assert_source(expected_source, reference)
            started_utc = datetime.now(timezone.utc).isoformat()
            started = time.monotonic()
            summary = run(Configuration(**entry["configuration"]), directory / entry["label"])
            elapsed = time.monotonic() - started
            finished_utc = datetime.now(timezone.utc).isoformat()
            _assert_source(expected_source, reference)
            if summary["configuration"] != entry["configuration"]:
                raise RuntimeError("executed configuration differs from planned comparison")
            observations.append(_observation(entry, summary, started_utc, finished_utc, elapsed))
            journal_path.write_text(json.dumps(journal, indent=2) + "\n")
        schedules = {(row["account_schedule_sha256"], row["order_schedule_sha256"]) for row in observations}
        if len(schedules) != 1:
            raise RuntimeError("paired runs used different account arrival schedules")
        pairs = []
        for pair in sorted({row["pair"] for row in observations}):
            rows = {row["variant"]: row for row in observations if row["pair"] == pair}
            base, optimized = rows["base"], rows["optimized"]
            base_rate = base["unique_durable_accepted_per_s"]
            pairs.append({"pair": pair, "execution_order": [row["variant"] for row in observations if row["pair"] == pair],
                          "base_acknowledged_per_s": base_rate,
                          "optimized_acknowledged_per_s": optimized["unique_durable_accepted_per_s"],
                          "optimized_to_base_ratio": optimized["unique_durable_accepted_per_s"] / base_rate if base_rate else None,
                          "base_counts": base["counts"], "optimized_counts": optimized["counts"]})
        journal.update(complete=True, pairs=pairs,
                       median_acknowledged_per_s={variant: statistics.median(row["unique_durable_accepted_per_s"]
                           for row in observations if row["variant"] == variant) for variant in ("base", "optimized")},
                       interpretation="Repeated short observations; no statistical significance, maximum capacity or production acceptance claim")
    except BaseException as exc:
        journal["failure"] = {"type": type(exc).__name__, "message": str(exc)}
        raise
    finally:
        journal_path.write_text(json.dumps(journal, indent=2) + "\n")
        files = [path for path in directory.rglob("*") if path.is_file()
                 and path.suffix not in (".sqlite3", ".db") and not path.name.endswith(("-wal", "-shm"))
                 and path != directory / "manifest.json"]
        (directory / "manifest.json").write_text(json.dumps({"database_files_included": False, "files": {
            str(path.relative_to(directory)): {"bytes": path.stat().st_size, "sha256": sha256(path.read_bytes()).hexdigest()}
            for path in sorted(files)}}, indent=2) + "\n")
    return journal


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-source", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--reserve-cache-size", type=int, default=4096)
    parser.add_argument("--market-cache-size", type=int, default=8)
    parser.add_argument("--hot-accounts", type=int, default=0)
    parser.add_argument("--hot-fraction", type=float, default=0)
    parser.add_argument("--order-distribution", choices=("constant", "varied"), default="constant")
    parser.add_argument("--plan-only", action="store_true", help="print schedule without creating services, files or load")
    args = parser.parse_args(argv)
    try:
        entries = plan(Configuration(mode="batch", rate=5000, batch_size=64,
            hot_accounts=args.hot_accounts, hot_fraction=args.hot_fraction,
            order_distribution=args.order_distribution), repetitions=args.repetitions,
            reserve_cache_size=args.reserve_cache_size, market_cache_size=args.market_cache_size)
        if args.plan_only:
            print(json.dumps({"expected_source": args.expected_source, "runs": entries,
                              "load_started": False, "production_approved": False}, indent=2))
            return 0
        if args.output is None:
            raise ValueError("--output is required unless --plan-only")
        result = run_cohort(args.output, args.expected_source, entries)
    except (ValueError, RuntimeError, ImportError, OSError) as exc:
        parser.exit(1, str(exc) + "\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
