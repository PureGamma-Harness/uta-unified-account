"""Actual SQLite catalog checks only; no fabricated successful credit decision."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from uta.credit_audit_v2 import (CreditAuditError, OBJECT_SQL, TABLE_SQL, TRIGGER_SQL,
                                 borrow_operation_id, canonical, verify_schema)
from uta.durable_commands import QueueStore
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

    def test_operation_identity_is_stable_business_key_not_unknown_content_hash(self):
        expected = "credit-operation:" + sha256(canonical(["BORROW", "alice", "loan:1"]).encode()).hexdigest()
        self.assertEqual(borrow_operation_id("alice", "loan:1"), expected)
        self.assertNotEqual(borrow_operation_id("alice", "loan:2"), expected)
        for value in (True, 1, "", "alice\n", "Ａ", "x" * 129):
            with self.subTest(kind=type(value).__name__), self.assertRaises(CreditAuditError):
                borrow_operation_id(value, "loan:1")
        self.assertEqual(len(TABLE_SQL), 3)
