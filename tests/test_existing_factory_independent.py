"""Independent snapshot/lifetime/fencing vectors on actual public sources.

No factory-author fixtures, native-V2 authorities or fabricated permissions.
"""
from decimal import Decimal as D
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from uta.credit import CreditService
from uta.existing_services import open_existing_services
from uta.service import ExchangeService, ServiceError
from uta.storage import Database, StorageError
from uta.writer_fence import WriterFence, WriterFenceError


class ObservedDatabase(Database):
    def __init__(self, path):
        super().__init__(path)
        self.observed_connections = []
        self.statements = []

    def _connect(self):
        connection = super()._connect()
        self.observed_connections.append(connection)
        connection.set_trace_callback(self.statements.append)
        return connection


class IndependentExistingFactoryTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory(prefix="uta-independent-existing-")
        self.addCleanup(directory.cleanup)
        self.db = ObservedDatabase(Path(directory.name) / "authority.sqlite3")
        self.original = ExchangeService(self.db, {"USD": 2, "BTC": 8}, fee_rate=D(0))
        self.original.create_account("independent")
        self.original.deposit("independent", "seed", "USD", D(100))
        self.credit = CreditService(self.original)
        self.credit.configure_asset_limit("USD", D(10))
        self.credit.configure_limit("independent", "USD", D(10))
        self.credit.fund_pool("fund", "USD", D(10), source_reference="synthetic:independent:factory")
        self.db.observed_connections.clear()
        self.db.statements.clear()

    def assert_closed(self, connections):
        for connection in connections:
            with self.assertRaises(sqlite3.ProgrammingError):
                connection.execute("SELECT 1")

    def snapshot(self):
        with self.db.read_transaction() as connection:
            schema = tuple(tuple(row) for row in connection.execute("SELECT name,type,tbl_name,sql FROM sqlite_master ORDER BY name"))
            tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
            return schema, {table: tuple(tuple(row) for row in connection.execute('SELECT * FROM "'+table+'" ORDER BY rowid')) for table in tables}

    def test_one_owned_connection_closes_and_returned_service_opens_fresh(self):
        services = open_existing_services(self.db)
        first = tuple(self.db.observed_connections)
        self.assertEqual(len(first), 1)
        self.assert_closed(first)
        self.assertFalse([sql for sql in self.db.statements if sql.split()[0].upper() in
                          {"CREATE", "ALTER", "DROP", "INSERT", "UPDATE", "DELETE", "REPLACE"}])
        self.assertIs(services.exchange.database, self.db)
        self.assertIs(services.credit.ledger, services.ledger)
        self.original.deposit("independent", "later", "USD", D(1))
        self.assertEqual(services.ledger.balance("customer:independent", "USD"), D(101))
        self.assert_closed(self.db.observed_connections)

    def test_real_wal_commit_does_not_mix_existing_read_snapshot(self):
        with self.db.read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT units FROM ledger_balances WHERE account='customer:independent' AND asset='USD'").fetchone()[0], "10000")
            self.original.deposit("independent", "concurrent-real-commit", "USD", D(1))
            services = open_existing_services(self.db, connection=connection)
            self.assertEqual(services.ledger.balance("customer:independent", "USD", connection=connection), D(100))
            self.assertEqual(services.ledger.verify(connection=connection), 2)
        self.assertEqual(services.ledger.balance("customer:independent", "USD"), D(101))
        self.assert_closed(self.db.observed_connections)

    def test_failure_closes_its_only_connection_without_schema_repair(self):
        with self.db.transaction() as connection:
            connection.execute("DROP TRIGGER credit_commands_no_delete")
        before = self.snapshot()
        self.db.observed_connections.clear()
        with self.assertRaisesRegex(StorageError, "credit_commands_no_delete"):
            open_existing_services(self.db)
        failed = tuple(self.db.observed_connections)
        self.assertEqual(len(failed), 1)
        self.assert_closed(failed)
        self.assertEqual(self.snapshot(), before)

    def test_caught_forbidden_read_write_stays_poisoned_for_factory(self):
        before = self.snapshot()
        with self.assertRaises(WriterFenceError) as terminal:
            with self.db.read_transaction() as connection:
                with self.assertRaises(sqlite3.DatabaseError):
                    connection.execute("DELETE FROM credit_commands")
                with self.assertRaises(WriterFenceError) as joined:
                    open_existing_services(self.db, connection=connection)
                self.assertEqual(joined.exception.code, "read_only_transaction")
                denied = joined.exception
        self.assertIs(terminal.exception, denied)
        self.assertEqual(self.snapshot(), before)
        self.assert_closed(self.db.observed_connections)

    def test_audit_prefix_does_not_authorize_unknown_core_trigger(self):
        with self.db.transaction() as connection:
            connection.execute("CREATE TRIGGER audit_credit_decoy BEFORE INSERT ON credit_commands BEGIN SELECT 1; END")
        before = self.snapshot()
        with self.assertRaisesRegex(StorageError, "unexpected constraint or guard: audit_credit_decoy"):
            open_existing_services(self.db)
        self.assertEqual(self.snapshot(), before)

    def test_actual_release_denies_old_bound_token_during_construction(self):
        fence = WriterFence(self.db)
        fence.enable("independent-native-base")
        token = fence.acquire("independent-owner", 5)
        bound = self.db.for_writer(token)
        services = open_existing_services(bound)
        self.assertIs(services.exchange.database, bound)
        fence.release(token)
        with self.assertRaises(WriterFenceError) as stale:
            open_existing_services(bound)
        self.assertEqual(stale.exception.code, "writer_fenced")

    def test_reconstructed_managed_public_borrow_remains_501_no_effects(self):
        fence = WriterFence(self.db)
        fence.enable("independent-native-deny")
        token = fence.acquire("independent-deny-owner", 5)
        bound = self.db.for_writer(token)
        services = open_existing_services(bound)
        before = self.snapshot()
        with self.assertRaises(ServiceError) as denied:
            services.credit.borrow("independent", "public-still-closed", "USD", D(1))
        self.assertEqual((denied.exception.code, denied.exception.status), ("unsupported_credit_operation", 501))
        self.assertEqual(self.snapshot(), before)
        fence.release(token)


if __name__ == "__main__":
    unittest.main()
