"""Actual SQLite catalog checks only; no fabricated successful credit decision."""
from datetime import datetime, timezone
from decimal import Decimal as D
from hashlib import sha256
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from uta.credit_audit_v2 import (CreditAuditError, OBJECT_SQL, TABLE_SQL, TRIGGER_SQL,
                                 borrow_operation_id, canonical, verify_schema)
from uta.durable_commands import QueueStore
from uta.credit_artifact import credit_artifact_id, credit_code_artifact
from uta.decision_audit import DecisionAudit
from uta.market import MarketSnapshot
from uta.models import AssetSpec
from uta.service import ExchangeService
from uta.storage import Database


class CreditAuditV2SchemaTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="credit-audit-v2-schema-")
        self.addCleanup(self.temp.cleanup)
        self.database = Database(Path(self.temp.name) / "synthetic.sqlite3")
        self.service = ExchangeService(self.database, {"USD": 8, "BTC": 8},
            clock=lambda: datetime(2026, 11, 17, tzinfo=timezone.utc), decision_audit=True)
        QueueStore(self.database, initialize=True)

    def install_test_catalog(self, connection):
        # Unfenced self-created component DB only. The production module has no
        # installer/activation API; native-v2 must install with real guards.
        for definition in OBJECT_SQL.values():
            connection.execute(definition)

    def test_import_and_validation_do_not_create_or_repair_schema(self):
        with self.database.transaction() as connection:
            before = connection.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()[0]
            with self.assertRaises(CreditAuditError) as rejected:
                verify_schema(connection)
            self.assertEqual(rejected.exception.code, "credit_audit_schema_corrupt")
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()[0], before)

    def test_actual_exact_catalog_is_readable_and_requires_all_original_parents(self):
        with self.database.transaction() as connection:
            self.install_test_catalog(connection)
            verify_schema(connection)
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            parents = {row[2] for row in connection.execute("PRAGMA foreign_key_list(uta_credit_decisions)")}
            self.assertEqual(parents, {"uta_accounts", "ledger_assets", "uta_market_history",
                "uta_credit_code_artifacts", "uta_credit_risk_policies", "uta_command_inbox", "ledger_events"})
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_credit_decisions").fetchone()[0], 0)
        with self.database.read_transaction() as connection:
            verify_schema(connection)

    def test_missing_guard_is_rejected_without_repair(self):
        with self.database.transaction() as connection:
            self.install_test_catalog(connection)
            name = next(iter(TRIGGER_SQL))
            connection.execute(f"DROP TRIGGER {name}")
            with self.assertRaises(CreditAuditError):
                verify_schema(connection)
            self.assertIsNone(connection.execute("SELECT name FROM sqlite_master WHERE name=?", (name,)).fetchone())

    def test_unexpected_reserved_object_is_rejected(self):
        with self.database.transaction() as connection:
            self.install_test_catalog(connection)
            connection.execute("CREATE TABLE credit_audit_v2_unexpected(value TEXT)")
            with self.assertRaises(CreditAuditError):
                verify_schema(connection)

    def test_all_unique_decision_identities_reject_replace_before_any_commit(self):
        self.service.create_account("alice")
        now = datetime(2026, 11, 17, tzinfo=timezone.utc)
        market = MarketSnapshot(1, now, {"USD": AssetSpec(D(1), D(1)),
                                        "BTC": AssetSpec(D(100), D(".8"))}, {})
        self.service.publish_market(market)
        manifest = credit_code_artifact()
        artifact_id = credit_artifact_id(manifest)
        policy = DecisionAudit.policy(self.service)
        policy_id = "policy:" + sha256(canonical(policy).encode()).hexdigest()
        with self.database.transaction() as connection:
            self.install_test_catalog(connection)
            connection.execute("PRAGMA recursive_triggers=OFF")
            connection.execute("SAVEPOINT catalog_identity_candidate")
            try:
                connection.execute("INSERT INTO uta_credit_code_artifacts VALUES(?,?)",
                    (artifact_id, canonical(manifest)))
                connection.execute("INSERT INTO uta_credit_risk_policies VALUES(?,?)",
                    (policy_id, canonical(policy)))
                # Deliberately incomplete SQL catalog candidate, not an audit
                # record. No source/intent/financial effect or decision API is
                # fabricated; deferred inbox/journal parents remain absent.
                # Always ROLLBACK this savepoint, so no candidate/archive row
                # can be committed or queried as a real credit decision.
                row = {"decision_id": "SQL_COMPONENT_ONLY:a", "operation_id": borrow_operation_id("alice", "a"),
                    "format": 2, "kind": "CREDIT_BORROWED", "account_id": "alice", "command_id": "a",
                    "inbox_kind": "BORROW", "terminal_state": "SUCCEEDED", "asset": "BTC", "amount": ".4",
                    "payload_hash": "0"*64, "source_id": "NO_SOURCE_SQL_ONLY", "market_snapshot_id": DecisionAudit.market_ref(connection, market),
                    "artifact_id": artifact_id, "policy_id": policy_id, "descriptor_id": "NO_NATIVE_SQL_ONLY",
                    "allocation_id": "NO_ALLOCATION_SQL_ONLY", "journal_id": "NO_JOURNAL_SQL_ONLY", "journal_sealed": 1,
                    "pre_version": 0, "post_version": 1, "selected_at": now.isoformat(),
                    "last_checked_at": now.isoformat(), "recorded_at": now.isoformat(),
                    "payload": "SQL_COMPONENT_ONLY_NOT_A_VALID_AUDIT"}
                columns = ",".join(row)
                values = ",".join("?" for _ in row)
                connection.execute(f"INSERT INTO uta_credit_decisions({columns}) VALUES({values})", tuple(row.values()))
                for collision in ("decision_id", "operation_id", "business_identity"):
                    changed = {**row, "decision_id": "SQL_COMPONENT_ONLY:b", "operation_id": borrow_operation_id("alice", "b"), "command_id": "b"}
                    if collision == "decision_id": changed["decision_id"] = row["decision_id"]
                    elif collision == "operation_id": changed["operation_id"] = row["operation_id"]
                    else: changed["command_id"] = row["command_id"]
                    with self.subTest(collision=collision), self.assertRaisesRegex(sqlite3.IntegrityError, "credit audit identity cannot replace"):
                        connection.execute(f"INSERT OR REPLACE INTO uta_credit_decisions({columns}) VALUES({values})", tuple(changed.values()))
                    self.assertEqual(connection.execute("SELECT decision_id FROM uta_credit_decisions").fetchall()[0][0], row["decision_id"])
            finally:
                connection.execute("ROLLBACK TO catalog_identity_candidate")
                connection.execute("RELEASE catalog_identity_candidate")
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_credit_decisions").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_credit_code_artifacts").fetchone()[0], 0)

    def test_operation_identity_is_stable_business_key_not_unknown_content_hash(self):
        expected = "credit-operation:" + sha256(canonical(["BORROW", "alice", "loan:1"]).encode()).hexdigest()
        self.assertEqual(borrow_operation_id("alice", "loan:1"), expected)
        self.assertNotEqual(borrow_operation_id("alice", "loan:2"), expected)
        for value in (True, 1, "", "alice\n", "Ａ", "x" * 129):
            with self.subTest(kind=type(value).__name__), self.assertRaises(CreditAuditError):
                borrow_operation_id(value, "loan:1")
        self.assertEqual(len(TABLE_SQL), 3)
