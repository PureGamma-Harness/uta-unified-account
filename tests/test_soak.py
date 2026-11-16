from dataclasses import replace
from decimal import Decimal as D
import gzip
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

from benchmarks import run_soak as soak


class SoakTests(unittest.TestCase):
    def make(self, directory, **changes):
        return soak.Soak(directory, replace(soak.Configuration(duration=.6, rate=2,
            feed_interval=.05, heartbeat_interval=.1, verify_interval=900, min_free_bytes=0), **changes),
            strict_source=False)

    def test_resource_and_rate_bounds(self):
        for change in ({"duration": float("nan")}, {"rate": 10000}, {"queue_capacity": True},
                       {"feed_interval": 4}, {"max_database_bytes": 100}, {"min_free_bytes": -1}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                replace(soak.Configuration(), **change).validate()

    def test_short_real_roundtrip_credit_feed_and_readonly_reopen(self):
        with TemporaryDirectory() as directory:
            job = self.make(directory)
            report = job.run()
            self.assertEqual(report["status"], "completed", report)
            self.assertEqual(report["counts"], {"done": 1})
            self.assertEqual(report["financial_counts"]["uta_matches"], 2)
            self.assertEqual(report["financial_counts"]["uta_fills"], 4)
            self.assertEqual(report["financial_counts"]["partial_cancelled_orders"], 1)
            self.assertTrue(report["completed_round_golden_matches_financial_state"])
            self.assertGreater(report["market_version"], 2)
            self.assertFalse(report["production_approved"])
            self.assertFalse(report["capacity_10000_per_s_passed"])
            with soak.readonly(Path(directory) / "authority.sqlite3") as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM soak_evidence WHERE kind='VERIFIED'").fetchone()[0], 2)
                with self.assertRaises(Exception):
                    connection.execute("DELETE FROM uta_orders")

    def test_partial_non_crossing_and_full_round_have_two_actual_matches_each(self):
        with TemporaryDirectory() as directory:
            job = self.make(directory)
            try:
                for sequence in (0, 1, 5):
                    job.roundtrip(sequence)
                report = job._validate(full=True)["independent_reconciliation"]
                self.assertEqual((report["matches"], report["paired_fills"], report["positions"]), (6, 12, 0))
                with soak.readonly(job.path) as connection:
                    self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_orders WHERE status='CANCELLED'").fetchone()[0], 3)
                    self.assertEqual(connection.execute("SELECT COUNT(*) FROM soak_steps WHERE step='no-liquidity' AND status='done'").fetchone()[0], 1)
            finally:
                job.close()

    def test_lost_order_receipt_replays_original_id_after_checkpoint_gap(self):
        with TemporaryDirectory() as directory:
            job = self.make(directory)
            original = job.exchange.submit_order
            def lost(*args, **kwargs):
                original(*args, **kwargs)
                raise RuntimeError("lost receipt after order COMMIT")
            with patch.object(job.exchange, "submit_order", side_effect=lost), self.assertRaises(RuntimeError):
                job.roundtrip(0)
            job.close()
            recovered = soak.Soak(directory, resume=True, strict_source=False)
            try:
                recovered.roundtrip(0)
                self.assertEqual(recovered._validate(full=True)["uta_matches"], 2)
                with soak.readonly(recovered.path) as connection:
                    self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_orders").fetchone()[0], 4)
            finally:
                recovered.close()

    def test_lost_match_receipt_queries_confirmed_partial_quantity_before_retry(self):
        with TemporaryDirectory() as directory:
            job = self.make(directory)
            original = job._matched
            def lost(*args, **kwargs):
                original(*args, **kwargs)
                raise RuntimeError("lost real paired match receipt")
            with patch.object(job, "_matched", side_effect=lost), self.assertRaises(RuntimeError):
                job.roundtrip(0)
            with soak.readonly(job.path) as connection:
                original_trade = connection.execute("SELECT trade_id FROM uta_matches").fetchone()[0]
            job.close()
            recovered = soak.Soak(directory, resume=True, strict_source=False)
            try:
                recovered.roundtrip(0)
                recovered.roundtrip(0)
                report = recovered._validate(full=True)["independent_reconciliation"]
                self.assertEqual((report["matches"], report["paired_fills"]), (2, 4))
                with soak.readonly(recovered.path) as connection:
                    self.assertEqual(connection.execute("SELECT trade_id FROM uta_matches ORDER BY sequence LIMIT 1").fetchone()[0], original_trade)
            finally:
                recovered.close()

    def test_interest_commit_before_checkpoint_does_not_accrue_twice(self):
        with TemporaryDirectory() as directory:
            job = self.make(directory)
            original = job.credit.accrue_interest
            def lost(*args, **kwargs):
                original(*args, **kwargs)
                raise RuntimeError("lost credit receipt")
            with patch.object(job.credit, "accrue_interest", side_effect=lost), self.assertRaises(RuntimeError):
                job.roundtrip(0)
            job.close()
            recovered = soak.Soak(directory, resume=True, strict_source=False)
            try:
                recovered.roundtrip(0)
                self.assertEqual(recovered.exchange.account("soak-credit")["balances"]["BTC"], "0.99999999")
                self.assertEqual(recovered.credit.verify()["nonzero_liabilities"], 0)
                with soak.readonly(recovered.path) as connection:
                    self.assertEqual(connection.execute("SELECT COUNT(*) FROM credit_commands WHERE kind='interest_accrued'").fetchone()[0], 1)
            finally:
                recovered.close()

    def test_export_crash_before_cursor_preserves_nonoverlapping_segment_ranges(self):
        with TemporaryDirectory() as directory:
            job = self.make(directory)
            original = soak._atomic
            def crash(path, value):
                if path.name == "manifest.json":
                    raise RuntimeError("export crash after file fsync")
                return original(path, value)
            with patch.object(soak, "_atomic", side_effect=crash), self.assertRaises(RuntimeError):
                job.export()
            with job.database.transaction() as connection:
                job._event(connection, "AFTER_CRASH", {})
            job.export()
            manifest = json.loads((Path(directory) / "logs/manifest.json").read_text())
            sequences = []
            for filename, proof in manifest["segments"].items():
                data = (Path(directory) / "logs" / filename).read_bytes()
                self.assertEqual(sha256(data).hexdigest(), proof["sha256"])
                sequences += [json.loads(line)["sequence"] for line in gzip.decompress(data).splitlines()]
            self.assertEqual(sequences, list(range(1, len(sequences) + 1)))
            job.close()

    def test_schema_damage_is_rejected_before_any_constructor_can_repair_it(self):
        with TemporaryDirectory() as directory:
            job = self.make(directory)
            with job.database.transaction() as connection:
                connection.execute("DROP TRIGGER uta_matches_no_delete")
            job.close()
            with self.assertRaisesRegex(RuntimeError, "schema changed"):
                soak.Soak(directory, resume=True, strict_source=False)
            with soak.readonly(Path(directory) / "authority.sqlite3") as connection:
                self.assertIsNone(connection.execute("SELECT 1 FROM sqlite_master WHERE name='uta_matches_no_delete'").fetchone())

    def test_single_process_writer_and_original_start_survive_pause_resume(self):
        with TemporaryDirectory() as directory:
            job = self.make(directory)
            start = job.meta["started_ns"]
            with self.assertRaisesRegex(RuntimeError, "another soak writer"):
                soak.Soak(directory, resume=True, strict_source=False)
            job.stop.set()
            self.assertEqual(job.run()["status"], "paused")
            resumed = soak.Soak(directory, resume=True, strict_source=False)
            self.assertEqual(resumed.meta["started_ns"], start)
            self.assertEqual(soak.read_status(directory)["original_started_ns"], start)
            self.assertFalse(soak.read_status(directory)["stability_target_passed"])
            resumed.close()

    def test_dead_process_is_pending_instead_of_claiming_running(self):
        with TemporaryDirectory() as directory:
            job = self.make(directory)
            with job.database.transaction() as connection:
                connection.execute("UPDATE soak_meta SET value='running' WHERE key='status'")
                connection.execute("UPDATE soak_sessions SET pid=999999999,process_identity='missing'")
            self.assertEqual(soak.read_status(directory)["status"], "interrupted_pending")
            self.assertFalse(soak.read_status(directory)["stability_target_passed"])
            job.close()

    def test_bounded_outstanding_records_overload_without_losing_arrivals(self):
        with TemporaryDirectory() as directory:
            job = self.make(directory, duration=1.6, queue_capacity=1)
            original = job.roundtrip
            def slow(sequence):
                time.sleep(.7)
                return original(sequence)
            with patch.object(job, "roundtrip", side_effect=slow):
                report = job.run()
            self.assertEqual(sum(report["counts"].values()), 3)
            self.assertGreater(report["counts"].get("overload", 0), 0)
            self.assertFalse(report["stability_target_passed"])

    def test_disk_budget_failure_keeps_authority_and_reports_failed(self):
        with TemporaryDirectory() as directory:
            job = self.make(directory, min_free_bytes=10**30)
            report = job.run()
            self.assertEqual(report["status"], "failed")
            self.assertTrue((Path(directory) / "authority.sqlite3").exists())
            self.assertFalse(report["stability_target_passed"])


if __name__ == "__main__":
    unittest.main()
