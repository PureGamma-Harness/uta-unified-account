"""Actual joined borrowing effects, receipt rollback and shared margin budgets."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from uta.credit import CreditService
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.portfolio import (BorrowLimits, CollateralRule, CollateralTier,
                           LinearMarginRule, PortfolioRules)
from uta.products import ProductCatalog, ProductKind, ProductSpec, TradingStatus
from uta.service import ExchangeService, ServiceError
from uta.storage import Database, StorageError
from uta.writer_fence import WriterFenceError


class JoinedBorrowTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "authority.sqlite3"
        self.now = datetime(2026, 11, 17, tzinfo=timezone.utc)
        self.catalog = ProductCatalog(1, {"BTC-PERP": ProductSpec(
            "BTC-PERP", ProductKind.LINEAR_PERPETUAL, "BTC", "USD", "USD",
            D(".01"), D(".01"), D(1), status=TradingStatus.ACTIVE)})
        self.rules = PortfolioRules(1,
            {"USD": CollateralRule("USD", (CollateralTier(None, D(1)),), D(".5")),
             "BTC": CollateralRule("BTC", (CollateralTier(None, D(".8")),), D(".5"))},
            {"BTC": BorrowLimits("BTC", D(10), D(".2"), D(".1"), D(".01"))},
            {"tier-1": LinearMarginRule("tier-1", D(".1"), D(".05"))}, D(10000))

    def reopen(self):
        return ExchangeService(Database(self.path), {"USD": 8, "BTC": 8},
            product_catalog=self.catalog, portfolio_rules=self.rules,
            fee_rate=D(0), clock=lambda: self.now)

    def prepare(self, *, limit="100", pool=".5"):
        self.exchange = self.reopen()
        for account in ("alice", "bob"):
            self.exchange.create_account(account)
            self.exchange.deposit(account, "cash", "USD", D(100))
        self.exchange.publish_market(MarketSnapshot(1, self.now,
            {"USD": AssetSpec(D(1), D(1)), "BTC": AssetSpec(D(100), D(".8"))},
            {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))}))
        self.exchange.set_kill_switch(False)
        self.credit = CreditService(self.exchange)
        self.credit.configure_asset_limit("BTC", D(limit))
        for account in ("alice", "bob"):
            self.credit.configure_limit(account, "BTC", D(10))
        self.credit.fund_pool("pool", "BTC", D(pool), source_reference="synthetic:joined-borrow:pool")
        with self.exchange._transaction() as connection:
            connection.execute("CREATE TABLE test_borrow_receipts(id TEXT PRIMARY KEY,result TEXT NOT NULL)")

    def state(self):
        return (self.exchange.account("alice"), self.exchange.account("bob"),
                self.exchange.ledger.journal(), self.exchange.events(limit=1000), self.credit.verify())

    def assert_code(self, code, action):
        with self.assertRaises(ServiceError) as rejected:
            action()
        self.assertEqual(rejected.exception.code, code)

    def test_receipt_failure_rolls_back_cash_pool_debt_journal_and_id(self):
        self.prepare()
        before = self.state()
        with self.assertRaises(ServiceError) as rejected:
            with self.exchange._transaction() as connection:
                self.credit._borrow(connection, "alice", "joint", "BTC", D(".4"))
                connection.execute("INSERT INTO test_borrow_receipts VALUES ('joint','success')")
                connection.execute("INSERT INTO missing_borrow_receipts VALUES (1)")
        self.assertEqual((rejected.exception.code, rejected.exception.status), ("storage_unavailable", 503))
        self.assertIsInstance(rejected.exception.__cause__, sqlite3.OperationalError)
        self.assertEqual(self.state(), before)
        with self.exchange._transaction() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM test_borrow_receipts").fetchone()[0], 0)
            result = self.credit._borrow(connection, "alice", "joint", "BTC", D(".4"))
            connection.execute("INSERT INTO test_borrow_receipts VALUES ('joint','success')")
        self.assertEqual((result["principal"], result["interest"]), ("0.4", "0"))
        self.assertEqual(self.exchange.account("alice")["balances"]["BTC"], "0.4")
        self.assertEqual(self.exchange.ledger.balance("system:credit-pool", "BTC"), D(".1"))
        self.assertEqual(self.exchange.ledger.balance("liability:principal:alice", "BTC"), D("-.4"))
        self.assertEqual(self.exchange.ledger.balance("system:credit-principal-receivable", "BTC"), D(".4"))

    def test_real_commit_then_same_id_reopen_replays_exactly_once(self):
        self.prepare()
        with self.exchange._transaction() as connection:
            result = self.credit._borrow(connection, "alice", "joint", "BTC", D(".4"))
            self.assertEqual(self.credit._borrow(connection, "alice", "joint", "BTC", D(".400")), result)
            connection.execute("INSERT INTO test_borrow_receipts VALUES ('joint','success')")
        before = self.state()
        restarted = CreditService(self.reopen())
        self.assertEqual(restarted.borrow("alice", "joint", "BTC", D(".4000")), result)
        self.assertEqual(self.state(), before)
        self.assertEqual(sum(event["event_type"] == "CREDIT_BORROWED" for event in before[3]), 1)
        self.assertEqual(self.exchange.ledger.verify(), 4)  # two deposits, pool, one loan
        self.assert_code("idempotency_conflict", lambda: restarted.borrow("alice", "joint", "BTC", D(".3")))

    def test_same_connection_order_cannot_reuse_new_loan_margin(self):
        self.prepare()
        with self.exchange._transaction() as connection:
            self.credit._borrow(connection, "alice", "joint", "BTC", D(".4"))
            # USD100 + BTC.4*100*.8 - debt40 = equity92; loan IM8 =>84.
            risk = self.exchange._risk(connection, "alice", self.exchange._market(connection))
            self.assertEqual((risk["accounting_equity"], risk["equity"], risk["available_margin"]),
                             ("100", "92", "84"))
            self.assert_code("insufficient_margin", lambda: self.exchange._admit_order(
                connection, "alice", "too-large", "BTC-PERP", D(9), D(100)))
            accepted = self.exchange._admit_order(connection, "alice", "safe", "BTC-PERP", D(8), D(100))
            self.assertEqual(accepted["status"], "OPEN")
            self.assert_code("credit_limit", lambda: self.credit._borrow(
                connection, "alice", "margin-reused", "BTC", D(".04")))
        risk = self.exchange.risk("alice")
        self.assertEqual((risk["open_order_margin"], risk["available_margin"]), ("80", "4"))
        self.assertEqual(self.credit.verify()["nonzero_liabilities"], 1)
        self.assertEqual([order["order_id"] for order in self.exchange.orders("alice")], ["safe"])

    def test_two_accounts_share_actual_pool_cash_in_one_transaction(self):
        self.prepare(pool=".5")
        with self.exchange._transaction() as connection:
            self.credit._borrow(connection, "alice", "loan-a", "BTC", D(".4"))
            self.assert_code("credit_pool_empty", lambda: self.credit._borrow(
                connection, "bob", "loan-b", "BTC", D(".2")))
            self.credit._borrow(connection, "bob", "loan-b", "BTC", D(".1"))
        self.assertEqual(self.exchange.ledger.balance("system:credit-pool", "BTC"), D(0))
        self.assertEqual(self.credit.verify()["nonzero_liabilities"], 2)

    def test_two_accounts_share_database_asset_limit_in_one_transaction(self):
        self.prepare(limit=".5", pool="1")
        with self.exchange._transaction() as connection:
            self.credit._borrow(connection, "alice", "loan-a", "BTC", D(".4"))
            self.assert_code("credit_limit", lambda: self.credit._borrow(
                connection, "bob", "loan-b", "BTC", D(".2")))
            self.credit._borrow(connection, "bob", "loan-b", "BTC", D(".1"))
        self.assertEqual(self.exchange.ledger.balance("system:credit-pool", "BTC"), D(".5"))
        self.assertEqual(self.credit.verify()["nonzero_liabilities"], 2)

    def test_halt_and_stale_quote_reject_joined_new_risk_without_effects(self):
        self.prepare()
        self.exchange.set_kill_switch(True)
        before = self.state()
        with self.exchange._transaction() as connection:
            self.assert_code("trading_halted", lambda: self.credit._borrow(connection, "alice", "halted", "BTC", D(".1")))
        self.assertEqual(self.state(), before)
        self.exchange.set_kill_switch(False)
        self.now += timedelta(hours=1)
        before = self.state()
        with self.exchange._transaction() as connection:
            self.assert_code("market_unavailable", lambda: self.credit._borrow(connection, "alice", "stale", "BTC", D(".1")))
        self.assertEqual(self.state(), before)

    def test_public_invalid_input_does_not_open_storage(self):
        self.prepare()
        with patch.object(self.exchange, "_transaction", side_effect=AssertionError("opened storage")):
            self.assert_code("invalid_input", lambda: self.credit.borrow("alice", "invalid", "BTC", D(0)))

    def test_missing_or_inactive_connection_cannot_start_a_private_transaction(self):
        self.prepare()
        before = self.state()
        with self.assertRaises(StorageError):
            self.credit._borrow(None, "alice", "none", "BTC", D(".1"))
        with self.exchange.database.transaction() as connection:
            pass
        with self.assertRaises((StorageError, sqlite3.ProgrammingError)):
            self.credit._borrow(connection, "alice", "closed", "BTC", D(".1"))
        self.assertEqual(self.state(), before)

    def test_other_database_or_raw_connection_cannot_join_borrowing(self):
        self.prepare()
        before = self.state()
        other = Database(self.path.with_name("other.sqlite3"))
        with other.transaction() as connection:
            with self.assertRaises(StorageError):
                self.credit._borrow(connection, "alice", "wrong", "BTC", D(".1"))
        raw = sqlite3.connect(self.path)
        try:
            raw.execute("BEGIN IMMEDIATE")
            with self.assertRaises(WriterFenceError) as rejected:
                self.credit._borrow(raw, "alice", "raw", "BTC", D(".1"))
            self.assertEqual(rejected.exception.code, "unguarded_connection")
            raw.rollback()
        finally:
            raw.close()
        self.assertEqual(self.state(), before)

    def test_read_inbox_and_control_roles_cannot_be_elevated(self):
        self.prepare()
        before = self.state()
        for role, transaction in (("read", self.exchange.database.read_transaction),
                                  ("inbox", self.exchange.database.inbox_transaction),
                                  ("control", self.exchange.database._fence_transaction)):
            with self.subTest(role=role):
                with transaction() as connection:
                    with self.assertRaises(WriterFenceError) as rejected:
                        self.credit._borrow(connection, "alice", role, "BTC", D(".1"))
                    self.assertEqual(rejected.exception.code, "unguarded_connection")
        self.assertEqual(self.state(), before)
