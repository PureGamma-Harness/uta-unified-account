"""Repayment and its durable command receipt share an owned transaction."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from uta.credit import CreditService
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ExchangeService, ServiceError
from uta.storage import Database


class JoinedRepaymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = datetime(2026, 11, 16, tzinfo=timezone.utc)
        self.service = ExchangeService(Database(Path(self.temp.name) / "authority.sqlite3"),
            {"USD": 8, "BTC": 8}, clock=lambda: self.now)
        self.service.create_account("alice")
        self.service.deposit("alice", "cash", "USD", D(1000))
        self.service.publish_market(MarketSnapshot(1, self.now,
            {"USD": AssetSpec(D(1), D(1)), "BTC": AssetSpec(D(100), D(".8"))},
            {"X": InstrumentSpec(D(100), D(".1"), D(".05"))}))
        self.service.set_kill_switch(False)
        self.credit = CreditService(self.service)
        self.credit.configure_asset_limit("BTC", D(100))
        self.credit.configure_limit("alice", "BTC", D(10))
        self.credit.fund_pool("pool", "BTC", D(50), source_reference="synthetic:joined:pool")
        self.credit.borrow("alice", "borrow", "BTC", D(2))
        self.credit.accrue_interest("alice", "interest", "BTC", D(".01"))
        with self.service._transaction() as connection:
            connection.execute("CREATE TABLE test_command_receipts(id TEXT PRIMARY KEY,result TEXT NOT NULL)")

    def state(self):
        return (self.service.account("alice"), self.service.ledger.journal(),
                self.service.events(limit=1000), self.credit.verify())

    def test_receipt_failure_rolls_back_cash_debt_interest_and_idempotent_effect(self):
        before = self.state()
        with self.assertRaises(ServiceError) as rejected:
            with self.service._transaction() as connection:
                self.credit._repay(connection, "alice", "joint", "BTC", D(".5"))
                connection.execute("INSERT INTO test_command_receipts VALUES('joint','success')")
                connection.execute("INSERT INTO absent_command_receipt_table VALUES(1)")
        self.assertEqual((rejected.exception.code, rejected.exception.status), ("storage_unavailable", 503))
        self.assertIsInstance(rejected.exception.__cause__, sqlite3.OperationalError)
        self.assertEqual(self.state(), before)
        with self.service._transaction() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM test_command_receipts").fetchone()[0], 0)
            result = self.credit._repay(connection, "alice", "joint", "BTC", D(".5"))
            connection.execute("INSERT INTO test_command_receipts VALUES('joint','success')")
        after = self.state()
        self.assertEqual(result["interest_repaid"], "0.01")
        self.assertEqual(result["principal_repaid"], "0.49")
        self.assertEqual(after[0]["balances"]["BTC"], "1.5")
        self.assertEqual(after[0]["liabilities"]["BTC"], {"principal": "1.51", "interest": "0", "total": "1.51"})
        self.assertEqual(self.credit.repay("alice", "joint", "BTC", D(".50")), result)
        self.assertEqual(self.state(), after)

    def test_joined_repayment_remains_available_during_halt_and_stale_market(self):
        self.service.set_kill_switch(True)
        self.now += timedelta(hours=1)
        with self.service._transaction() as connection:
            result = self.credit._repay(connection, "alice", "stale-repay", "BTC", D(".5"))
        self.assertEqual(result["principal"], "1.51")
        self.assertEqual(result["interest"], "0")
        self.assertEqual(self.service.account("alice")["balances"]["BTC"], "1.5")
        self.service.ledger.verify()
