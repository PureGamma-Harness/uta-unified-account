from dataclasses import replace
from decimal import Decimal as D
import hashlib
import gzip
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from benchmarks.run_matched_liquidation import Configuration, _first_recoveries, capacity_gates, run
from uta.service import ExchangeService


class MatchedLoadTests(unittest.TestCase):
    def execute(self, **kwargs):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name) / "result"
        result = run(Configuration(cases=2, duration=.02, workers=2, **kwargs), directory)
        rows = [json.loads(line) for line in (directory / "arrivals.jsonl").read_text().splitlines()]
        return result, rows, directory

    def test_real_paired_partial_liquidations_reconcile_unique_trades_not_legs(self):
        with patch.object(ExchangeService, "apply_fill", side_effect=AssertionError("manual fill forbidden")):
            result, rows, directory = self.execute()
        self.assertEqual(result["unique_committed_liquidation_trades"], 4)
        self.assertEqual(result["two_sided_settlement_legs"], 8)
        self.assertEqual(result["fully_closed_accounts"], 2)
        self.assertEqual(result["remaining_position_quantity"], "0")
        self.assertEqual(result["unresolved_accounts"], 0)
        self.assertEqual(result["counts"]["unknown"], 0)
        for account in result["final_victim_accounts"].values():
            self.assertEqual(D(account["balance_usd"]), D("93.16"))
        trades = [row for row in rows if row["kind"] == "liquidation_trade"]
        self.assertEqual(len({row["receipt"]["trade_id"] for row in trades}), 4)
        self.assertTrue(all(D(row["receipt"]["quantity"]) == 45 for row in trades))
        self.assertTrue(all(row["receipt"]["sell_order_id"].startswith("liq:") for row in trades))
        self.assertTrue(all(row["committed_observed_ns"] > row["trigger_ns"] for row in trades))
        self.assertEqual(result["reconciliation"][0]["matches"], 6)  # two initial opens excluded from the four liquidations
        self.assertEqual(result["reconciliation"][0]["unpaired_fills"], 0)
        self.assertFalse(result["gates"]["passed"])
        self.assertFalse(result["production_approved"])
        self.assertIsNotNone(result["latency_ms"]["shock_to_recovered"]["p99_9"])

    def test_no_liquidity_preserves_actual_risk_and_never_creates_mark_fills(self):
        result, rows, _ = self.execute(liquidity="none")
        self.assertEqual(result["unique_committed_liquidation_trades"], 0)
        self.assertEqual(result["unresolved_accounts"], 2)
        self.assertEqual(D(result["remaining_position_quantity"]), 180)
        self.assertEqual(result["reconciliation"][0]["matches"], 2)
        self.assertEqual(result["latency_ms"]["shock_to_first_confirmed_trade"]["p50"], None)
        self.assertFalse(any(row["kind"] == "liquidation_trade" for row in rows))
        self.assertFalse(result["gates"]["checks"]["full_counterparty_liquidity"])

    def test_half_liquidity_reports_actual_fifo_volume_and_residual_not_attempt_count(self):
        result, rows, _ = self.execute(liquidity="half")
        self.assertEqual(result["unique_committed_liquidation_trades"], 2)
        self.assertEqual(D(result["remaining_position_quantity"]), 90)
        self.assertGreater(result["unresolved_accounts"], 0)
        self.assertTrue(all(D(account["quantity"]) >= 0 for account in result["final_victim_accounts"].values()))
        self.assertEqual(sum(row["kind"] == "liquidation_trade" for row in rows), 2)

    def test_shards_are_independent_books_and_all_reopen_for_four_side_replay(self):
        result, rows, directory = self.execute(shards=2)
        self.assertEqual(len(result["reconciliation"]), 2)
        self.assertTrue(all(row["status"] == "passed" for row in result["reconciliation"]))
        manifest = json.loads((directory / "manifest.json").read_text())
        for name, expected in manifest["files"].items():
            content = (directory / name).read_bytes()
            self.assertEqual(len(content), expected["bytes"])
            self.assertEqual(hashlib.sha256(content).hexdigest(), expected["sha256"])
        environment = json.loads((directory / "environment.json").read_text())
        self.assertEqual(environment["durability"], "single-host SQLite WAL/FULL; no replication")
        self.assertEqual(environment["risk_profile"], "versioned synthetic Cross")

    def test_long_or_unbounded_probe_is_explicitly_rejected_without_creating_state(self):
        configuration = Configuration()
        for values in ({"duration": 1800}, {"drain_seconds": 31}, {"cases": 513}, {"cases": True},
                       {"workers": 0}, {"liquidity": "mark-fill"}, {"duration": float("nan")}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                replace(configuration, **values).validate()
        gates = capacity_gates(5, 100000, {}, 0, "full")
        self.assertFalse(gates["passed"])
        self.assertFalse(capacity_gates(1800, 10000, {"overload": 1}, 0, "full")["passed"])
        self.assertFalse(capacity_gates(1800, 10000, {}, 1, "full")["passed"])
        self.assertFalse(capacity_gates(1800, 10000, {}, 0, "none")["passed"])
        self.assertFalse(gates["phase1_exchange_acceptance_passed"])

    def test_open_loop_overload_is_retained_as_unresolved_not_hidden_as_rejection_success(self):
        with TemporaryDirectory() as temporary:
            result = run(Configuration(cases=12, duration=.0001, workers=1, queue_capacity=1), Path(temporary) / "overload")
        self.assertGreater(result["counts"].get("overload", 0), 0)
        self.assertEqual(result["counts"]["processed"] + result["counts"]["overload"], 12)
        self.assertGreater(result["unresolved_accounts"], 0)
        self.assertLess(result["unique_committed_liquidation_trades"], 24)
        self.assertFalse(result["gates"]["passed"])

    def test_archived_probe_counts_receipts_sizes_hashes_and_unfilled_risk(self):
        root = Path(__file__).resolve().parents[1] / "benchmarks/results/20261114-matched-liquidation"
        for name, cases, fills in (("full", 20, 40), ("none", 4, 0)):
            directory = root / name
            manifest = json.loads((directory / "manifest.json").read_text())
            for filename, metadata in manifest["files"].items():
                content = (directory / filename).read_bytes()
                self.assertEqual(hashlib.sha256(content).hexdigest(), metadata["sha256"])
                self.assertEqual(len(content), metadata["bytes"])
            summary = json.loads((directory / "summary.json").read_text())
            rows = [json.loads(line) for line in gzip.decompress((directory / "arrivals.jsonl.gz").read_bytes()).splitlines()]
            case_rows = [row for row in rows if row["kind"] == "case"]
            trade_rows = [row for row in rows if row["kind"] == "liquidation_trade"]
            self.assertEqual(len(case_rows), cases)
            self.assertEqual(len({row["case"] for row in case_rows}), cases)
            self.assertEqual(len(trade_rows), fills)
            self.assertEqual(len({row["receipt"]["trade_id"] for row in trade_rows}), fills)
            self.assertEqual(summary["unique_committed_liquidation_trades"], fills)
            self.assertEqual(summary["two_sided_settlement_legs"], fills * 2)
            self.assertTrue(all(D(row["receipt"]["quantity"]) == 45 for row in trade_rows))
            self.assertEqual(sum(D(a["quantity"]) for a in summary["final_victim_accounts"].values()), D(cases * 90 - fills * 45))
            self.assertFalse(summary["gates"]["passed"])
            if fills:
                self.assertTrue(all(D(a["balance_usd"]) == D("93.16") for a in summary["final_victim_accounts"].values()))
            else:
                self.assertEqual(summary["unresolved_accounts"], cases)

    def test_parallel_duplicate_health_observations_use_first_recovery(self):
        records = [{"kind": "recovered", "case": 1, "at_ns": 30},
                   {"kind": "case", "case": 1},
                   {"kind": "recovered", "case": 1, "at_ns": 10},
                   {"kind": "recovered", "case": 2, "at_ns": 20},
                   {"kind": "recovered", "case": 1, "at_ns": 50}]
        self.assertEqual(_first_recoveries(records), {1: 10, 2: 20})

    def test_cli_smoke_success_is_not_capacity_success_and_default_exit_is_gate_failure(self):
        root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as temporary:
            for smoke, expected in ((True, 0), (False, 2)):
                command = [sys.executable, str(root / "benchmarks/run_matched_liquidation.py"),
                           "--cases", "1", "--duration", ".01", "--workers", "1",
                           "--output", str(Path(temporary) / str(smoke))]
                if smoke:
                    command.append("--smoke")
                process = subprocess.run(command, cwd="/tmp", text=True, capture_output=True, timeout=30)
                self.assertEqual(process.returncode, expected, process.stdout + process.stderr)
                self.assertFalse(json.loads(process.stdout)["gates"]["passed"])


if __name__ == "__main__":
    unittest.main()
