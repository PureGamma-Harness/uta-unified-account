"""Actual read/control construction, without constructor attestation fixtures."""
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from uta.credit import CreditService
from uta.existing_services import open_existing_services
from uta.service import ExchangeService
from uta.storage import Database, StorageError
from uta.writer_fence import WriterFence, WriterFenceError


class ExistingServicesTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(prefix="uta-existing-services-")
        self.addCleanup(self.directory.cleanup)
        self.db = Database(Path(self.directory.name) / "authority.sqlite3")
        self.now = datetime(2026, 11, 17, tzinfo=timezone.utc)

    def source(self, *, audited=False, fee=D(0), reserve_cache_size=0, market_cache_size=0):
        source = ExchangeService(self.db, {"USD": 2, "BTC": 8}, fee_rate=fee, clock=lambda: self.now,
            decision_audit=audited, reserve_cache_size=reserve_cache_size, market_cache_size=market_cache_size)
        source.create_account("alice")
        source.deposit("alice", "synthetic-owned-cash", "USD", D(100))
        credit = CreditService(source)
        credit.configure_asset_limit("BTC", D(1))
        credit.configure_limit("alice", "BTC", D(1))
        credit.fund_pool("synthetic-pool", "BTC", D(1), source_reference="synthetic:existing-services:funding")
        return source

    def snapshot(self):
        with self.db.read_transaction() as connection:
            tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
            return {"schema": [tuple(row) for row in connection.execute("SELECT name,type,tbl_name,sql FROM sqlite_master ORDER BY name")],
                    "rows": {name: [tuple(row) for row in connection.execute('SELECT * FROM "' + name + '" ORDER BY rowid')] for name in tables}}

    def assert_no_writes(self, statements):
        denied = ("CREATE", "ALTER", "DROP", "INSERT", "UPDATE", "DELETE", "REPLACE", "VACUUM", "ATTACH")
        self.assertFalse([sql for sql in statements if sql.lstrip().upper().startswith(denied)])

    def test_unmanaged_existing_constructor_uses_one_real_read_snapshot(self):
        self.source()
        before = self.snapshot()
        statements = []
        with self.db.read_transaction() as connection:
            connection.set_trace_callback(statements.append)
            services = open_existing_services(self.db, clock=lambda: self.now, connection=connection)
            self.assertIs(services.exchange.database, self.db)
            self.assertIs(services.credit.exchange, services.exchange)
            self.assertIs(services.ledger, services.exchange.ledger)
            self.assertIs(services.credit.ledger, services.ledger)
            self.assertEqual(services.ledger.balance("customer:alice", "USD", connection=connection), D(100))
            self.assertEqual(connection.execute("PRAGMA query_only").fetchone()[0], 1)
        self.assert_no_writes(statements)
        self.assertEqual(before, self.snapshot())

    def test_base_control_snapshot_constructs_without_a_financial_actor(self):
        self.source()
        fence = WriterFence(self.db)
        fence.enable("synthetic:existing:base")
        before = self.snapshot()
        statements = []
        with self.db._fence_transaction() as connection:
            connection.set_trace_callback(statements.append)
            services = open_existing_services(self.db, connection=connection)
            self.assertIs(services.exchange.database, self.db)
            self.assertIsNone(services.exchange.database.writer_token)
        self.assert_no_writes(statements)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(fence.status()["generation"], 0)
        self.assertIsNone(fence.status()["owner_nonce"])

    def test_current_audit_artifact_and_archived_execution_options_are_read(self):
        source = self.source(audited=True, fee=D(".00040000"), reserve_cache_size=7, market_cache_size=2)
        before = self.snapshot()
        services = open_existing_services(self.db, clock=lambda: self.now)
        self.assertEqual(str(services.exchange.fee_rate), "0.00040000")
        self.assertEqual(services.exchange._reserve_kernel.capacity, 7)
        self.assertEqual(services.exchange._market_decode_cache.capacity, 2)
        self.assertEqual(services.exchange.audit.policy_id, source.audit.policy_id)
        self.assertEqual(services.exchange.audit.artifact_id, source.audit.artifact_id)
        self.assertEqual(before, self.snapshot())

    def test_missing_existing_guard_is_rejected_without_repair(self):
        self.source()
        with self.db.transaction() as connection:
            connection.execute("DROP TRIGGER credit_commands_no_update")
        before = self.snapshot()
        with self.assertRaisesRegex(StorageError, "credit_commands_no_update"):
            open_existing_services(self.db)
        self.assertEqual(before, self.snapshot())

    def test_financial_and_wrong_database_connections_never_become_read_joins(self):
        self.source()
        with self.db.transaction() as connection, self.assertRaises(WriterFenceError):
            open_existing_services(self.db, connection=connection)
        with self.db.read_transaction() as connection, self.assertRaises(WriterFenceError):
            open_existing_services(Database(self.db.path), connection=connection)


if __name__ == "__main__":
    unittest.main()
