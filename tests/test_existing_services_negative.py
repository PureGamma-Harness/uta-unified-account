"""Author negative matrix on real existing sources, not independent acceptance."""
from decimal import Decimal as D
from pathlib import Path
import sqlite3
import unittest

from tests import test_existing_services as fixtures
from uta.credit import CreditService
from uta.existing_services import open_existing_services
from uta.ledger import LedgerError
from uta.service import ExchangeService, ServiceError
from uta.storage import Database, DurableLedger, StorageError
from uta.writer_fence import WriterFence, WriterFenceError


class ExistingServicesNegativeTests(unittest.TestCase):
    setUp = fixtures.ExistingServicesTests.setUp
    source = fixtures.ExistingServicesTests.source
    snapshot = fixtures.ExistingServicesTests.snapshot

    def refused_unchanged(self, error, message):
        before = self.snapshot()
        with self.assertRaisesRegex(error, message) as refused:
            open_existing_services(self.db)
        self.assertEqual(before, self.snapshot())
        return refused.exception

    def replace_empty_table(self, table, change):
        # Corrupt a table in an authority created by the real public service.
        # This is never used as an accepted schema model or positive authority.
        with self.db.transaction() as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM "' + table + '"').fetchone()[0], 0)
            original = connection.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()[0]
            dependent = [row[0] for row in connection.execute("SELECT sql FROM sqlite_master WHERE tbl_name=? AND type IN ('index','trigger') AND sql IS NOT NULL ORDER BY name", (table,))]
            altered = change(original)
            self.assertNotEqual(original, altered)
            connection.execute('DROP TABLE "' + table + '"')
            connection.execute(altered)
            for statement in dependent:
                connection.execute(statement)

    def test_missing_file_is_not_created(self):
        self.assertFalse(Path(self.db.path).exists())
        with self.assertRaises(StorageError):
            open_existing_services(self.db)
        self.assertFalse(Path(self.db.path).exists())

    def test_wholly_missing_credit_module_is_not_initialized(self):
        self.source()
        with self.db.transaction() as connection:
            connection.execute("DROP TABLE credit_schema")
        self.refused_unchanged(StorageError, "credit_schema")

    def test_unchanged_columns_do_not_hide_removed_table_constraint(self):
        self.source()
        check = "CHECK(status IN ('OPEN','PARTIALLY_FILLED','FILLED','CANCELLED'))"
        self.replace_empty_table("uta_orders", lambda sql: sql.replace(check, ""))
        self.refused_unchanged(StorageError, "definition.*uta_orders")

    def test_extra_table_constraint_is_not_silently_accepted(self):
        self.source()
        self.replace_empty_table("uta_orders", lambda sql: sql[:-1] + ", CHECK(quantity IS NOT NULL))")
        self.refused_unchanged(StorageError, "definition.*uta_orders")

    def test_unknown_extra_unique_index_is_not_an_official_constraint(self):
        self.source()
        with self.db.transaction() as connection:
            connection.execute("CREATE UNIQUE INDEX extra_credit_amount ON credit_commands(amount)")
        self.refused_unchanged(StorageError, "unexpected constraint or guard: extra_credit_amount")

    def test_full_ledger_replay_refuses_corrupt_pool_projection(self):
        self.source()
        with self.db.transaction() as connection:
            connection.execute("UPDATE ledger_balances SET units='99999999' WHERE account='system:credit-pool' AND asset='BTC'")
        self.refused_unchanged(LedgerError, "materialized balances differ from journal replay")

    def test_full_credit_reconciliation_refuses_masked_account_debts(self):
        source = self.source()
        source.create_account("bob")
        with self.db.transaction() as connection:
            connection.execute("INSERT INTO uta_liabilities VALUES('alice','BTC','0.1','0')")
            connection.execute("INSERT INTO uta_liabilities VALUES('bob','BTC','-0.1','0')")
        error = self.refused_unchanged(ServiceError, "gross debt projection differs")
        self.assertEqual(error.code, "credit_corrupt")

    def test_absent_current_artifact_is_not_written_or_backfilled(self):
        source = self.source(audited=True)
        with self.db.transaction() as connection:
            sql = connection.execute("SELECT sql FROM sqlite_master WHERE name='audit_uta_code_artifacts_no_delete'").fetchone()[0]
            connection.execute("DROP TRIGGER audit_uta_code_artifacts_no_delete")
            connection.execute("DELETE FROM uta_code_artifacts WHERE artifact_id=?", (source.audit.artifact_id,))
            connection.execute(sql)
        self.refused_unchanged(StorageError, "no stored current-build base artifact")

    def test_multiple_real_archived_execution_options_are_not_guessed(self):
        self.source(audited=True)
        ExchangeService(self.db, {"USD": 2, "BTC": 8}, fee_rate=D(0), clock=lambda: self.now,
                        decision_audit=True, reserve_cache_size=1)
        error = self.refused_unchanged(StorageError, "configuration cannot be reconstructed")
        self.assertIn("ambiguous", str(error.__cause__))

    def test_each_public_constructor_rejects_a_real_financial_join(self):
        source = self.source()
        before = self.snapshot()
        calls = (
            lambda connection: ExchangeService(self.db, {"USD": 2, "BTC": 8}, fee_rate=D(0), _existing_connection=connection),
            lambda connection: DurableLedger(self.db, {"USD": 2, "BTC": 8}, _existing_connection=connection),
            lambda connection: CreditService(source, _existing_connection=connection),
        )
        for call in calls:
            with self.subTest(constructor=call), self.db.transaction() as connection, self.assertRaises(WriterFenceError) as refused:
                call(connection)
            self.assertEqual(refused.exception.code, "unguarded_connection")
        self.assertEqual(before, self.snapshot())

    def test_closed_read_connection_cannot_be_reused(self):
        self.source()
        with self.db.read_transaction() as connection:
            pass
        with self.assertRaises(WriterFenceError) as refused:
            open_existing_services(self.db, connection=connection)
        self.assertEqual(refused.exception.code, "unguarded_connection")

    def test_raw_sqlite_connection_is_not_a_read_constructor_scope(self):
        self.source()
        raw = sqlite3.connect(self.db.path)
        try:
            raw.execute("BEGIN")
            with self.assertRaises(WriterFenceError) as refused:
                open_existing_services(self.db, connection=raw)
            self.assertEqual(refused.exception.code, "unguarded_connection")
            raw.rollback()
        finally:
            raw.close()


if __name__ == "__main__":
    unittest.main()
