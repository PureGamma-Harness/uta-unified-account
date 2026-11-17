"""Independent oracle omissions at the immutable operations review origin.

Public bootstrap drift and explicit in-memory archive faults are synthetic test
inputs, not ordinary customer exploits or real-funds observations. No source
checkout, old soak authority, file guard, or live writer token is modified.
"""
from contextlib import contextmanager
from decimal import Decimal as D
import gzip
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from benchmarks import run_managed_soak as soak
from benchmarks.run_soak import readonly
from uta.sharding import ShardRouter


REVIEW_ORIGIN = "8e1de5c4d79e9a45f638b67b65cbed87b7ad3d09"
SCALE = 100_000_000


class FixedBudgetOracleReferenceTests(unittest.TestCase):
    def bootstrap_fixture(self, *, credit_usd_extra=0, extra_account=False):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        authority = Path(temporary.name) / "authority"
        original = ShardRouter.deposit
        def source_deposit(router, account, event_id, asset, amount):
            if account == soak.ACCOUNTS[2] and asset == "USD":
                amount += D(credit_usd_extra)
                if extra_account:
                    router.create_account("unexpected-fourth-account")
            return original(router, account, event_id, asset, amount)
        # All source changes use real public router administration before
        # management seals the source. Only the expected genesis input drifts.
        with patch.object(ShardRouter, "deposit", source_deposit):
            soak.bootstrap(authority, 1, "synthetic:oracle-reference:fixed-budget")
        view = soak.ManagedSoak.__new__(soak.ManagedSoak)
        view.financial = authority / "shard-0000.sqlite3"
        view.configuration = soak.Configuration(duration=4)
        return view

    def facts(self, view):
        with readonly(view.financial) as connection:
            return {
                "accounts": [row[0] for row in connection.execute("SELECT account_id FROM uta_accounts ORDER BY account_id")],
                "credit_usd": int(connection.execute("SELECT units FROM ledger_balances WHERE account=? AND asset='USD'",
                    ("customer:" + soak.ACCOUNTS[2],)).fetchone()[0]),
                "ledger_events": connection.execute("SELECT COUNT(*) FROM ledger_events").fetchone()[0],
            }

    def test_exact_public_bootstrap_is_a_valid_control(self):
        view = self.bootstrap_fixture()
        self.assertTrue(view.verify(0, full=True)["golden_passed"])
        self.assertEqual(self.facts(view), {"accounts": sorted(soak.ACCOUNTS),
            "credit_usd": 1_000_000 * SCALE, "ledger_events": 6})

    def test_credit_usd_budget_drift_is_rejected_without_changing_it(self):
        view = self.bootstrap_fixture(credit_usd_extra=1)
        self.assertEqual(self.facts(view)["credit_usd"], 1_000_001 * SCALE)
        self.assertEqual(self.facts(view)["ledger_events"], 6)
        with self.assertRaisesRegex(RuntimeError, "fixed-budget"):
            view.verify(0, full=True)
        self.assertEqual(self.facts(view)["credit_usd"], 1_000_001 * SCALE)

    def test_unexpected_account_is_rejected_without_deleting_it(self):
        view = self.bootstrap_fixture(extra_account=True)
        self.assertEqual(set(self.facts(view)["accounts"]), set(soak.ACCOUNTS) | {"unexpected-fourth-account"})
        with self.assertRaisesRegex(RuntimeError, "fixed-account"):
            view.verify(0, full=True)
        self.assertIn("unexpected-fourth-account", self.facts(view)["accounts"])

    def test_original_combined_reproduction_keeps_all_four_accounts_and_wrong_usd(self):
        view = self.bootstrap_fixture(credit_usd_extra=1, extra_account=True)
        actual = self.facts(view)
        self.assertEqual(len(actual["accounts"]), 4)
        self.assertEqual(actual["credit_usd"], 100_000_100_000_000)
        self.assertEqual(actual["ledger_events"], 6)
        with self.assertRaisesRegex(RuntimeError, "fixed-account"):
            view.verify(0, full=True)
        self.assertEqual(self.facts(view), actual)


class ArchivedEvidenceOracleReferenceTests(unittest.TestCase):
    def setUp(self):
        # This committed historical synthetic snapshot is test input only. It
        # does not qualify the current release or endorse its historical run.
        fixture = Path(__file__).resolve().parents[1] / "benchmarks/results/20261116-managed-smoke-final/smoke10/financial-snapshot.json.gz"
        snapshot = json.loads(gzip.decompress(fixture.read_bytes()))
        self.connection = sqlite3.connect(":memory:")
        self.addCleanup(self.connection.close)
        self.connection.row_factory = sqlite3.Row
        for item in snapshot["schema"]:
            if item["type"] == "table" and item["sql"] and not item["name"].startswith("sqlite_"):
                self.connection.execute(item["sql"])
        for table, rows in snapshot["tables"].items():
            for row in rows:
                columns = ",".join('"' + field + '"' for field in row)
                parameters = ",".join("?" for _ in row)
                self.connection.execute(f'INSERT INTO "{table}" ({columns}) VALUES ({parameters})', tuple(row.values()))
        # The historical export omitted this immutable codec table's rows.
        # Restore the documented USD/BTC=8 fixture scales before either baseline
        # or negative inspection; do not infer them from a current engine.
        self.connection.executemany("INSERT INTO ledger_assets(asset,scale) VALUES (?,8)", (("USD",), ("BTC",)))
        self.connection.commit()
        self.view = soak.ManagedSoak.__new__(soak.ManagedSoak)
        self.view.configuration = soak.Configuration(duration=10)
        self.view.financial = Path("/unused-memory-only-oracle-fixture")
        @contextmanager
        def memory_read(_):
            yield self.connection
        self.reader = patch.object(soak, "readonly", memory_read)
        self.reader.start()
        self.addCleanup(self.reader.stop)
        self.assertTrue(self.view.verify(3, full=True)["golden_passed"])

    def test_original_historical_fixture_is_a_valid_oracle_control_only(self):
        self.assertTrue(self.view.verify(3, full=True)["golden_passed"])

    def test_wrong_artifact_content_id_is_rejected_without_repair(self):
        self.connection.execute("UPDATE uta_code_artifacts SET manifest='{}'")
        row = self.connection.execute("SELECT artifact_id,manifest FROM uta_code_artifacts LIMIT 1").fetchone()
        self.assertNotEqual(row[0], "artifact:" + sha256(row[1].encode()).hexdigest())
        with self.assertRaisesRegex(RuntimeError, "artifact content digest"):
            self.view.verify(3, full=True)
        self.assertEqual(self.connection.execute("SELECT manifest FROM uta_code_artifacts LIMIT 1").fetchone()[0], "{}")

    def test_wrong_policy_content_id_is_rejected_without_repair(self):
        self.connection.execute("UPDATE uta_risk_policies SET payload='{}'")
        row = self.connection.execute("SELECT policy_id,payload FROM uta_risk_policies LIMIT 1").fetchone()
        self.assertNotEqual(row[0], "policy:" + sha256(row[1].encode()).hexdigest())
        with self.assertRaisesRegex(RuntimeError, "policy content digest"):
            self.view.verify(3, full=True)
        self.assertEqual(self.connection.execute("SELECT payload FROM uta_risk_policies LIMIT 1").fetchone()[0], "{}")

    def test_missing_decision_artifact_is_already_rejected(self):
        self.connection.execute("UPDATE uta_code_artifacts SET artifact_id=?", ("artifact:" + sha256(b"{}").hexdigest(),))
        with self.assertRaisesRegex(RuntimeError, "reference"):
            self.view.verify(3, full=True)

    def test_market_content_digest_damage_is_already_rejected(self):
        self.connection.execute("UPDATE uta_market_history SET payload='{}'")
        with self.assertRaisesRegex(RuntimeError, "digest"):
            self.view.verify(3, full=True)

    def test_rehashed_artifact_with_old_decision_reference_is_rejected(self):
        self.connection.execute("UPDATE uta_code_artifacts SET artifact_id=?,manifest='{}'",
                                ("artifact:" + sha256(b"{}").hexdigest(),))
        with self.assertRaisesRegex(RuntimeError, "reference"):
            self.view.verify(3, full=True)

    def test_rehashed_policy_with_old_decision_reference_is_rejected(self):
        self.connection.execute("UPDATE uta_risk_policies SET policy_id=?,payload='{}'",
                                ("policy:" + sha256(b"{}").hexdigest(),))
        with self.assertRaisesRegex(RuntimeError, "reference"):
            self.view.verify(3, full=True)

    def test_duplicate_keys_noncanonical_and_nonfinite_archive_json_are_rejected(self):
        for raw in ('{"a":1,"a":2}', '{} ', '{"a":NaN}', '{"a":1e9999}', '[]'):
            with self.subTest(raw=raw):
                original = self.connection.execute("SELECT artifact_id,manifest FROM uta_code_artifacts LIMIT 1").fetchone()
                self.connection.execute("UPDATE uta_code_artifacts SET manifest=? WHERE artifact_id=?", (raw, original[0]))
                with self.assertRaisesRegex(RuntimeError, "canonical JSON"):
                    self.view.verify(3, full=True)
                self.connection.execute("UPDATE uta_code_artifacts SET manifest=? WHERE artifact_id=?", (original[1], original[0]))

    def test_ambiguous_archive_id_is_rejected(self):
        # Memory-only schema fault removes the primary-key constraint so the
        # audit's own ambiguity check can be observed; no live guard is removed.
        self.connection.execute("CREATE TABLE duplicated_artifacts AS SELECT * FROM uta_code_artifacts")
        self.connection.execute("DROP TABLE uta_code_artifacts")
        self.connection.execute("ALTER TABLE duplicated_artifacts RENAME TO uta_code_artifacts")
        self.connection.execute("INSERT INTO uta_code_artifacts SELECT * FROM uta_code_artifacts LIMIT 1")
        with self.assertRaisesRegex(RuntimeError, "ambiguous archived artifact"):
            self.view.verify(3, full=True)

    def test_corrupt_unreferenced_archive_is_not_silently_discarded(self):
        self.connection.execute("INSERT INTO uta_code_artifacts(artifact_id,manifest) VALUES (?,?)",
                                ("artifact:" + "0" * 64, "{}"))
        with self.assertRaisesRegex(RuntimeError, "artifact content digest"):
            self.view.verify(3, full=True)

    def test_content_verification_does_not_call_the_production_audit_replay(self):
        with patch("uta.decision_audit.DecisionAudit.artifact", side_effect=AssertionError("production artifact helper")), \
                patch("uta.decision_audit.DecisionAudit.policy_record", side_effect=AssertionError("production policy helper")), \
                patch("uta.decision_audit.DecisionAudit.replay", side_effect=AssertionError("production financial replay")):
            self.assertTrue(self.view.verify(3, full=True)["golden_passed"])

    def test_extra_gross_debt_row_is_rejected_even_when_its_amounts_are_zero(self):
        self.connection.execute("INSERT INTO uta_liabilities(account_id,asset,principal,interest) VALUES (?,?,?,?)",
                                (soak.ACCOUNTS[0], "USD", "0", "0"))
        with self.assertRaisesRegex(RuntimeError, "gross principal/interest"):
            self.view.verify(3, full=True)
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM uta_liabilities").fetchone()[0], 2)

    def test_initial_funding_receipt_drift_is_rejected_even_with_unchanged_ledger_cash(self):
        self.connection.execute("UPDATE credit_commands SET amount='2' WHERE kind='pool_funded'")
        with self.assertRaisesRegex(RuntimeError, "funding/loan/repayment"):
            self.view.verify(3, full=True)
        self.assertEqual(self.connection.execute("SELECT amount FROM credit_commands WHERE kind='pool_funded'").fetchone()[0], "2")


if __name__ == "__main__":
    unittest.main()
