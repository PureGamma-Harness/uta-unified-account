"""Offline source integrity must be checked before fencing any shard."""
from contextlib import closing
from decimal import Decimal as D
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from uta.durable_process import DurableProcessRouter, _preflight_managed_ledger_sources
from uta.service import ServiceError
from uta.sharding import ShardRouter
from uta.storage import Database, DurableLedger
from uta.writer_fence import WriterFence


class ManagedLedgerPreflightTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "authority"
        self.source = ShardRouter(self.path, 2, {"USD": 2}, decision_audit=True)
        for shard in range(2):
            account = next(f"source-{n}" for n in range(100) if self.source.shard_for(f"source-{n}") == shard)
            self.source.create_account(account)
            self.source.deposit(account, "synthetic-offline-funding", "USD", D(10))

    def assert_unsealed(self):
        with self.source.control.read_transaction() as connection:
            self.assertIsNone(connection.execute(
                "SELECT 1 FROM sqlite_master WHERE name='router_durable_config'").fetchone())
        for shard in range(2):
            database = Database(self.path / f"shard-{shard:04d}.sqlite3")
            self.assertFalse(WriterFence(database).status()["managed"])
            with database.read_transaction() as connection:
                self.assertIsNone(connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE name='uta_command_inbox'").fetchone())

    def take_over(self):
        layout = DurableProcessRouter.inspect_takeover(self.path)["layout_hash"]
        return DurableProcessRouter.take_over(self.path, managed=True,
            expected_layout_hash=layout, decision_audit=True)

    def test_bad_native_guard_on_last_shard_leaves_every_shard_unsealed(self):
        path = self.path / "shard-0001.sqlite3"
        with closing(sqlite3.connect(path)) as connection, connection:
            original = connection.execute(
                "SELECT sql FROM sqlite_master WHERE name='ledger_postings_no_update'").fetchone()[0]
            weakened = original.replace(" BEGIN ", " WHEN 0 BEGIN ", 1)
            connection.execute("DROP TRIGGER ledger_postings_no_update")
            connection.execute(weakened)
        with self.assertRaises(ServiceError) as error:
            self.take_over()
        self.assertEqual((error.exception.code, error.exception.status), ("ledger_corrupt", 503))
        self.assert_unsealed()
        with closing(sqlite3.connect(path)) as connection:
            self.assertEqual(connection.execute(
                "SELECT sql FROM sqlite_master WHERE name='ledger_postings_no_update'").fetchone()[0], weakened)

    def test_existing_hash_corruption_is_rejected_before_any_shard_fence(self):
        path = self.path / "shard-0001.sqlite3"
        with closing(sqlite3.connect(path)) as connection, connection:
            guard = connection.execute(
                "SELECT sql FROM sqlite_master WHERE name='ledger_events_seal_only'").fetchone()[0]
            connection.execute("DROP TRIGGER ledger_events_seal_only")
            connection.execute("UPDATE ledger_events SET event_hash=?", ("f" * 64,))
            connection.execute(guard)
        with self.assertRaises(ServiceError) as error:
            self.take_over()
        self.assertEqual((error.exception.code, error.exception.status), ("ledger_corrupt", 503))
        self.assert_unsealed()
        with closing(sqlite3.connect(path)) as connection:
            self.assertEqual(connection.execute("SELECT event_hash FROM ledger_events").fetchone()[0], "f" * 64)

    def test_preflight_uses_only_existing_read_snapshots_without_constructors(self):
        with patch.object(DurableLedger, "__init__", side_effect=AssertionError("financial constructor")), \
             patch.object(Database, "transaction", side_effect=AssertionError("write transaction")):
            _preflight_managed_ledger_sources(self.source)
        self.assert_unsealed()


if __name__ == "__main__":
    unittest.main()
