"""Real CLI/worker/TLS smoke and checkpoint failure tests; no long job is started."""
from dataclasses import replace
from contextlib import redirect_stderr
import io
import json
from pathlib import Path
import ssl
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from benchmarks.run_managed_soak import ACCOUNTS, Configuration, ManagedSoak, audit_job, inspect_job, main
from benchmarks.run_soak import readonly


class ManagedSoakTests(unittest.TestCase):
    def make(self, directory, **changes):
        configuration = replace(Configuration(duration=4, worker_every=0, parent_every=0,
            command_timeout=8, min_free_bytes=0), **changes)
        return ManagedSoak(Path(directory) / "job", configuration, strict_source=False)

    def test_bounded_low_rate_and_durations(self):
        for changes in ({"duration": float("nan")}, {"duration": 86401}, {"duration": 0},
                        {"rate": 10000}, {"rate": True}, {"command_timeout": 0},
                        {"worker_every": True}, {"parent_every": -1}, {"min_free_bytes": -1}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(Configuration(), **changes).validate()
        self.assertEqual(Configuration(duration=10).rounds, 3)
        self.assertEqual(Configuration(duration=86400).rounds, 21600)

    def test_long_job_requires_explicit_frozen_opt_in_before_creating_state(self):
        with TemporaryDirectory() as directory:
            target = Path(directory) / "must-not-start"
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(["run", "--directory", str(target), "--duration", "21600"])
            self.assertFalse(target.exists())

    def test_long_job_release_report_gate_has_no_cli_or_direct_api_bypass(self):
        with TemporaryDirectory() as directory:
            target = Path(directory) / "blocked-unverified-release"
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(["run", "--directory", str(target), "--duration", "21600", "--allow-long-run"])
            self.assertFalse(target.exists())
            with self.assertRaisesRegex(RuntimeError, "release validation"):
                ManagedSoak(target, Configuration(duration=86400), allow_long_run=True)
            self.assertFalse(target.exists())
            with self.assertRaisesRegex(RuntimeError, "frozen clean"):
                ManagedSoak(target, Configuration(duration=86400), allow_long_run=True, strict_source=False)
            self.assertFalse(target.exists())
            # Resume must inspect its persisted duration before touching a
            # listener, checkpoint, lock file, or financial authority.
            target.mkdir(mode=0o700)
            original = json.dumps({"configuration": Configuration(duration=21600).__dict__})
            (target / "job.json").write_text(original)
            with self.assertRaisesRegex(RuntimeError, "release validation"):
                ManagedSoak(target, resume=True, allow_long_run=True)
            self.assertEqual([entry.name for entry in target.iterdir()], ["job.json"])
            self.assertEqual((target / "job.json").read_text(), original)

    def test_real_tls_cli_matching_debt_and_both_process_faults(self):
        with TemporaryDirectory() as directory:
            job = self.make(directory, worker_every=1, parent_every=1)
            try:
                report = job.run()
            finally:
                job.close()
            self.assertEqual(report["status"], "completed", report)
            self.assertEqual(report["fault_signals"], {"worker": 1, "parent": 1})
            self.assertEqual(report["rounds"], {"DONE": 1})
            self.assertEqual(report["unresolved_steps"], 0)
            self.assertTrue(report["verified_tls"])
            self.assertEqual(job.tls.verify_mode, ssl.CERT_REQUIRED)
            self.assertTrue(job.tls.check_hostname)
            self.assertTrue(report["logs_verified"])
            counts = report["final_audit"]["financial_counts"]
            self.assertEqual({key: counts[key] for key in ("uta_orders", "uta_fills", "uta_matches", "uta_risk_decisions", "partial_cancelled_orders")},
                {"uta_orders": 4, "uta_fills": 4, "uta_matches": 2, "uta_risk_decisions": 8, "partial_cancelled_orders": 1})
            self.assertEqual(report["final_audit"]["remaining_principal_satoshi"], 0)
            for flag in ("continuous_6h_stability_passed", "continuous_24h_stability_passed",
                         "capacity_10000_per_s_passed", "production_approved"):
                self.assertFalse(report[flag])
            with readonly(job.financial) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_command_inbox WHERE account_id IS NOT NULL AND state='SUCCEEDED'").fetchone()[0], 6)
                # Independent raw integer goldens, not production fee/PnL helpers.
                for account in ACCOUNTS[:2]:
                    self.assertEqual(int(connection.execute("SELECT units FROM ledger_balances WHERE account=? AND asset='USD'", ("customer:" + account,)).fetchone()[0]), 99999999920000)
                self.assertEqual(int(connection.execute("SELECT units FROM ledger_balances WHERE account='system:fees' AND asset='USD'").fetchone()[0]), 160000)
                self.assertEqual(connection.execute("SELECT principal,interest FROM uta_liabilities WHERE account_id=? AND asset='BTC'", (ACCOUNTS[2],)).fetchone()[0], "0")
            with readonly(job.authority / "router.sqlite3") as connection:
                claims = connection.execute("SELECT source_reference,command FROM router_pool_sources").fetchall()
                self.assertEqual(len(claims), 1)
                self.assertEqual(claims[0][0], job.meta["bootstrap"]["source_reference"])
            self.assertNotIn("secret_b64", (job.directory / "job.json").read_text())
            self.assertFalse(inspect_job(job.directory)["recorded_listener_alive"])
            self.assertEqual(audit_job(job.directory)["status"], "audit_passed")
            self.assertGreater(job.audit_logs()["events"], 10)
            manifest = json.loads((job.directory / "log-segments.json").read_text())
            first = job.directory / manifest["segments"][0]["file"]
            altered = bytearray(first.read_bytes())
            altered[-1] ^= 1
            first.write_bytes(altered)
            with self.assertRaisesRegex(RuntimeError, "checksum"):
                job.audit_logs()

    def test_financial_commit_checkpoint_gap_queries_original_id_and_does_not_skip_partial_history(self):
        with TemporaryDirectory() as directory:
            job = self.make(directory)
            original = job._append_event
            def fail_checkpoint(connection, kind, payload):
                original(connection, kind, payload)
                if kind == "STEP_CONFIRMED" and payload.get("step") == "cancel-partial":
                    raise RuntimeError("injected failure after local row and event writes before checkpoint COMMIT")
            with patch.object(job, "_append_event", fail_checkpoint):
                report = job.run()
            self.assertEqual(report["status"], "failed")
            with readonly(job.financial) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_orders").fetchone()[0], 2)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_orders WHERE status='CANCELLED'").fetchone()[0], 1)
            with job.checkpoint.read_transaction() as connection:
                plan = json.loads(connection.execute("SELECT plan FROM steps WHERE name='cancel-partial'").fetchone()[0])
                self.assertEqual(connection.execute("SELECT state FROM steps WHERE name='cancel-partial'").fetchone()[0], "PLANNED")
                self.assertFalse(any(json.loads(row[0]).get("step") == "cancel-partial" for row in connection.execute("SELECT payload FROM events WHERE kind='STEP_CONFIRMED'")))
            resumed = ManagedSoak(job.directory, resume=True, strict_source=False)
            try:
                with self.assertRaisesRegex(RuntimeError, "differs"):
                    resumed._plan(1, "cancel-partial", {**plan, "payload": {"command_id": "replacement-is-forbidden"}})
                final = resumed.run()
            finally:
                resumed.close()
            self.assertEqual(final["status"], "completed", final)
            self.assertEqual(final["controller_sessions"], 2)
            self.assertEqual(final["final_audit"]["financial_counts"]["uta_matches"], 2)
            with readonly(resumed.financial) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_orders").fetchone()[0], 4)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_command_inbox WHERE command_id=?", (plan["payload"]["command_id"],)).fetchone()[0], 1)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM credit_commands WHERE kind='repaid'").fetchone()[0], 1)
            self.assertFalse(final["continuous_24h_stability_passed"])
            self.assertTrue(final["logs_verified"])


if __name__ == "__main__":
    unittest.main()
