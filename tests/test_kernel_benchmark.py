import contextlib
from dataclasses import asdict, replace
from decimal import Decimal
from fractions import Fraction
import gzip
from hashlib import sha256
import io
import json
from pathlib import Path
from collections import Counter
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from benchmarks import run_group_benchmark as group
from benchmarks import run_kernel_benchmark as kernel


class KernelBenchmarkTests(unittest.TestCase):
    def test_hot_schedule_preserves_exact_counts_and_live_order_headroom(self):
        configuration = group.Configuration(mode="batch", rate=5000, batch_size=64,
            hot_accounts=10, hot_fraction=.3)
        configuration.validate()
        schedule = group._account_schedule(configuration, 25000)
        counts = Counter(schedule)
        self.assertEqual(counts, group._account_counts(configuration, 25000))
        self.assertEqual(sum(counts[index] for index in range(10)), 7500)
        self.assertEqual({counts[index] for index in range(10)}, {750})
        self.assertLessEqual(max(counts.values()), 900)
        self.assertEqual(schedule, group._account_schedule(configuration, 25000))
        with self.assertRaises(ValueError):
            replace(configuration, hot_accounts=1).validate()

    def test_cache_and_workload_bounds_are_explicit(self):
        for changes in ({"reserve_cache_size": True}, {"market_cache_size": -1},
                        {"market_cache_size": 65}, {"reserve_cache_size": 65537}, {"hot_accounts": 10},
                        {"hot_fraction": .3}, {"hot_fraction": float("nan")},
                        {"hot_accounts": 100, "hot_fraction": .3},
                        {"hot_accounts": True, "hot_fraction": .3},
                        {"order_distribution": "random"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(group.Configuration(), **changes).validate()
        replace(group.Configuration(), reserve_cache_size=65536, market_cache_size=64).validate()

    def test_unsupported_optimization_is_never_silently_ignored(self):
        class OldRuntime:
            def __init__(self, database, scales):
                pass
        with patch.object(group, "ExchangeService", OldRuntime):
            self.assertEqual(group._cache_arguments(), {})
            with self.assertRaisesRegex(RuntimeError, "reserve_cache_size"):
                group._cache_arguments(reserve_cache_size=4096)
            with self.assertRaisesRegex(RuntimeError, "market_cache_size"):
                group._cache_arguments(market_cache_size=8)

    def test_service_plumbing_passes_both_capacities_including_reopen_zero(self):
        class ConstructorProbe:
            def __init__(self, database, scales, *, reserve_cache_size=0, market_cache_size=0, **kwargs):
                self.capacities = reserve_cache_size, market_cache_size
        with TemporaryDirectory() as temporary, patch.object(group, "ExchangeService", ConstructorProbe):
            path = Path(temporary) / "plumbing.sqlite3"
            self.assertEqual(group._service(path, reserve_cache_size=4096, market_cache_size=8).capacities, (4096, 8))
            self.assertEqual(group._service(path).capacities, (0, 0))

    def test_counter_delta_excludes_setup_and_rejects_reset(self):
        def snapshot(hits):
            return {name: {"supported": True, "capacity": 8, "size": 2, "hits": hits, "misses": 3, "evictions": 1}
                    for name in ("reserve", "market")}
        reports = group._cache_report([snapshot(10)], [snapshot(25)])
        self.assertEqual(reports[0]["timed_delta"]["reserve"], {"hits": 15, "misses": 0, "evictions": 0})
        with self.assertRaisesRegex(RuntimeError, "reset"):
            group._cache_report([snapshot(10)], [snapshot(9)])

    def test_varied_terms_are_40_legal_economic_keys_and_reference_is_independent(self):
        terms = [group._order_terms(index, "varied") for index in range(40)]
        self.assertEqual(len(set(terms)), 40)
        self.assertEqual({Decimal(quantity) > 0 for quantity, _ in terms}, {True, False})
        for quantity, price in terms:
            self.assertEqual(Decimal(quantity) % Decimal(".001"), 0)
            self.assertEqual(Decimal(price) % Decimal(".01"), 0)
            self.assertGreaterEqual(abs(Decimal(quantity)) * Decimal(price), Decimal(".01"))
        self.assertEqual(group._reference_reserve(".001", "100"), Fraction(251, 25000))
        self.assertEqual(group._reference_reserve("-.002", "99"), Fraction(27599, 1250000))
        self.assertEqual(group._reference_reserve(".001", "100.5"), Fraction(264755, 25000000))
        # A sub-unit fee must round up without using Decimal's current context.
        self.assertEqual(group._reference_reserve(".000000001", "100"), Fraction(1, 50000000))

    def test_short_varied_probe_reopens_uncached_and_checks_every_request(self):
        with TemporaryDirectory() as temporary:
            directory = Path(temporary) / "unit-probe"
            summary = group.run(group.Configuration(mode="batch", duration=.04, rate=1000, accounts=10,
                queue_capacity=64, batch_size=64, batch_delay_ms=10, hot_accounts=2,
                hot_fraction=.4, order_distribution="varied"), directory)
            with gzip.open(directory / "arrivals.jsonl.gz", "rt") as stream:
                rows = [json.loads(line) for line in stream]
            self.assertEqual(len(rows), 40)
            self.assertEqual(summary["counts"]["durable_accepted"], 40)
            self.assertEqual(summary["workload"]["economic_key_count"], 40)
            self.assertEqual(sum(summary["workload"]["offered_by_account"].values()), 40)
            self.assertEqual({(row["quantity"], row["limit_price"]) for row in rows},
                             {group._order_terms(index, "varied") for index in range(40)})
            self.assertEqual(set(summary["latency_ms"]["all"]), {"p50", "p95", "p99", "p99_9"})
            self.assertEqual(set(summary["latency_ms"]["accepted"]), {"p50", "p95", "p99", "p99_9"})
            self.assertTrue(all(row["verification_caches_disabled"] for row in summary["durability_checks"]))
            self.assertTrue(all(row["all_orders_remain_open"] for row in summary["durability_checks"]))
            self.assertFalse(summary["gates"]["passed"])

    def test_paired_plan_alternates_order_and_only_changes_cache_sizes(self):
        entries = kernel.plan()
        self.assertEqual([entry["variant"] for entry in entries],
                         ["base", "optimized", "optimized", "base", "base", "optimized"])
        for entry in entries:
            config = entry["configuration"].copy()
            reserve, market = config.pop("reserve_cache_size"), config.pop("market_cache_size")
            self.assertEqual((reserve, market), (0, 0) if entry["variant"] == "base" else (4096, 8))
            self.assertEqual(config, {key: value for key, value in entries[0]["configuration"].items()
                                      if key not in ("reserve_cache_size", "market_cache_size")})
        for arguments in ({"repetitions": 1}, {"reserve_cache_size": 0}, {"market_cache_size": 0}):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                kernel.plan(**arguments)

    @staticmethod
    def fake_summary(configuration):
        # This synthetic return value tests the reporting driver only, never capacity.
        return {"configuration": asdict(configuration), "counts": {"durable_accepted": 1},
                "unique_durable_accepted_per_s": 2 if configuration.reserve_cache_size else 1,
                "on_time_durable_accepted_per_s": 1, "measured_seconds_including_drain": 5,
                "latency_ms": {"all": {"p99": 1}, "accepted": {"p99": 1}}, "cache_stats": [],
                "workload": {"account_schedule_sha256": "account-hash", "order_schedule_sha256": "order-hash"},
                "unknown_resolution": {}, "gates": {"passed": False, "production_approved": False}}

    def test_cohort_keeps_source_identity_each_run_and_hashes_all_evidence(self):
        expected = "1" * 40
        identity = {"commit": expected, "tracked_changes": "", "source_sha256": {"uta/service.py": "hash"}}
        def fake_run(configuration, directory):
            directory.mkdir()
            summary = self.fake_summary(configuration)
            (directory / "summary.json").write_text(json.dumps(summary))
            return summary
        with (TemporaryDirectory() as temporary,
              patch.object(kernel, "_source_identity", return_value=identity) as source,
              patch.object(kernel, "run", side_effect=fake_run) as execute):
            directory = Path(temporary) / "cohort"
            report = kernel.run_cohort(directory, expected, kernel.plan())
            self.assertTrue(report["complete"])
            self.assertFalse(report["production_approved"])
            self.assertEqual(len(report["pairs"]), 3)
            self.assertEqual([row["optimized_to_base_ratio"] for row in report["pairs"]], [2, 2, 2])
            self.assertEqual(execute.call_count, 6)
            self.assertEqual(source.call_count, 13)
            manifest = json.loads((directory / "manifest.json").read_text())
            for filename, proof in manifest["files"].items():
                raw = (directory / filename).read_bytes()
                self.assertEqual(sha256(raw).hexdigest(), proof["sha256"])

    def test_source_change_or_dirty_frozen_tree_stops_before_load(self):
        expected = "1" * 40
        clean = {"commit": expected, "tracked_changes": "", "source_sha256": {"runtime": "first"}}
        for identity in ({**clean, "commit": "2" * 40}, {**clean, "tracked_changes": " M uta/service.py"}):
            with (TemporaryDirectory() as temporary,
                  patch.object(kernel, "_source_identity", return_value=identity),
                  patch.object(kernel, "run") as execute):
                with self.assertRaisesRegex(RuntimeError, "frozen source"):
                    kernel.run_cohort(Path(temporary) / "cohort", expected, kernel.plan())
                execute.assert_not_called()
        with patch.object(kernel, "_source_identity", return_value={**clean, "source_sha256": {"runtime": "second"}}):
            with self.assertRaisesRegex(RuntimeError, "changed"):
                kernel._assert_source(expected, clean)

    def test_plan_only_does_not_create_services_or_start_load(self):
        with patch.object(kernel, "run_cohort") as execute, contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(kernel.main(["--expected-source", "1" * 40, "--plan-only", "--hot-accounts", "10",
                "--hot-fraction", ".3", "--order-distribution", "varied"]), 0)
        execute.assert_not_called()
        self.assertFalse(json.loads(output.getvalue())["load_started"])


if __name__ == "__main__":
    unittest.main()
