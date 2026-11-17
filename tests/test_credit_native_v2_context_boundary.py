"""Actual financial/read/raw guards cannot be replaced by caller view flags."""
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from uta.credit import CreditService
from uta.credit_native_v2 import CreditV2Error, assert_operation_context
from uta.service import ExchangeService
from uta.storage import Database


class CreditNativeV2ContextBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(prefix="uta-credit-v2-context-")
        self.addCleanup(self.directory.cleanup)
        self.db = Database(Path(self.directory.name) / "authority.sqlite3")
        self.service = ExchangeService(self.db, {"USD": 8, "BTC": 8},
            clock=lambda: datetime(2026, 11, 17, 12, tzinfo=timezone.utc))
        self.service.create_account("alice")
        self.credit = CreditService(self.service)

    def assert_refused(self, connection, expected):
        with self.assertRaises(CreditV2Error) as refused:
            assert_operation_context(self.credit, connection, command_id="credit:1",
                account_id="alice", asset="BTC", amount=Decimal("0.4"))
        self.assertEqual(refused.exception.code, expected)

    def test_actual_uncapped_financial_role_has_no_native_v2_authority(self):
        with self.db.transaction() as connection:
            self.assert_refused(connection, "credit_v2_not_active")
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM credit_commands").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_liabilities").fetchone()[0], 0)

    def test_actual_read_role_cannot_join_credit_even_on_same_database(self):
        with self.db.read_transaction() as connection:
            self.assert_refused(connection, "credit_v2_context_invalid")

    def test_raw_transaction_on_actual_private_database_has_no_registry_context(self):
        connection = self.db._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self.assert_refused(connection, "credit_v2_context_invalid")
            connection.rollback()
        finally:
            connection.close()

    def test_caller_service_flags_never_become_a_native_scope(self):
        self.credit.credit_v2_operation = object()
        self.credit.native_ready = True
        self.credit.capability_id = "credit-internal-v2:" + "a" * 64
        with self.db.transaction() as connection:
            self.assert_refused(connection, "credit_v2_not_active")
            self.assertEqual(connection.execute("SELECT version FROM uta_accounts WHERE account_id='alice'").fetchone()[0], 0)
