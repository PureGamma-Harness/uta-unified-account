"""Independent integer ledger and hand-formula checks for joined credit.

The oracle below imports no production valuation, rounding or ledger function.
Production calls are only the system under test; expected values are derived
from explicit synthetic business actions and a small published hand example.
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D, localcontext
from fractions import Fraction as F
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from uta.credit import CreditService
from uta.decision_audit import DecisionAudit
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.portfolio import BorrowLimits, CollateralRule, CollateralTier, LinearMarginRule, PortfolioRules
from uta.products import ProductCatalog, ProductKind, ProductSpec, TradingStatus
from uta.service import ExchangeService, ServiceError
from uta.storage import Database, StorageError
from uta.writer_fence import WriterFence, WriterFenceError


SCALE = 100_000_000


def units(value):
    result = F(str(value)) * SCALE
    if result.denominator != 1:
        raise AssertionError("reference example is not representable in native units")
    return result.numerator


class ClosedCreditReference:
    """Business-action journal, using native integers and explicit owner legs."""
    def __init__(self):
        self.balances = defaultdict(int)
        self.principal = defaultdict(int)
        self.interest = defaultdict(int)

    def post(self, asset, legs):
        if sum(amount for _, amount in legs) != 0:
            raise AssertionError("reference event is not balanced")
        for owner, amount in legs:
            self.balances[owner, asset] += amount

    def deposit(self, account, asset, amount):
        n = units(amount)
        self.post(asset, [("customer:" + account, n), ("system:custody", -n)])

    def fund(self, amount):
        n = units(amount)
        self.post("BTC", [("system:credit-pool", n), ("system:credit-capital", -n)])

    def borrow(self, account, amount):
        n = units(amount)
        self.post("BTC", [("customer:" + account, n), ("system:credit-pool", -n),
                         ("liability:principal:" + account, -n),
                         ("system:credit-principal-receivable", n)])
        self.principal[account] += n

    def accrue(self, account, amount):
        n = units(amount)
        self.post("BTC", [("liability:interest:" + account, -n),
                         ("system:credit-interest-receivable", n)])
        self.interest[account] += n

    def repay(self, account, amount):
        n = units(amount)
        paid_interest = min(n, self.interest[account])
        paid_principal = n - paid_interest
        if paid_principal > self.principal[account]:
            raise AssertionError("reference repayment exceeds its debt")
        self.post("BTC", [("customer:" + account, -n),
            ("system:credit-interest-cash", paid_interest),
            ("liability:interest:" + account, paid_interest),
            ("system:credit-interest-receivable", -paid_interest),
            ("system:credit-pool", paid_principal),
            ("liability:principal:" + account, paid_principal),
            ("system:credit-principal-receivable", -paid_principal)])
        self.interest[account] -= paid_interest
        self.principal[account] -= paid_principal
        return paid_interest, paid_principal

    def hand_risk(self, account, *, tiered=False, order_quantity=0):
        cash = F(self.balances["customer:" + account, "USD"], SCALE)
        btc = F(self.balances["customer:" + account, "BTC"], SCALE)
        principal = F(self.principal[account], SCALE) * 100
        interest = F(self.interest[account], SCALE) * 100
        gross = btc * 100
        discounted = (min(gross, 25) * F(9, 10) + max(gross - 25, 0) * F(3, 5)
                      if tiered else gross * F(4, 5))
        debt = principal + interest
        reserve = abs(F(order_quantity)) * 10  # mark=limit=100, IM=10%, fee=0.
        equity = cash + discounted - debt
        return {"accounting_equity": cash + gross - debt,
            "collateral_value": cash + discounted, "equity": equity,
            "principal_value": principal, "interest_value": interest,
            "debt_value": debt, "initial_margin": debt / 5,
            "maintenance_margin": debt / 10, "open_order_margin": reserve,
            "available_margin": equity - debt / 5 - reserve}


class IndependentCreditReviewTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "credit.sqlite3"
        self.now = datetime(2026, 11, 17, tzinfo=timezone.utc)

    def build(self, *, tiered=False, pool="1", limit="10", cash="100", btc="0", configured=True):
        self.reference = ClosedCreditReference()
        self.database = Database(self.path)
        self.catalog = ProductCatalog(1, {"BTC-PERP": ProductSpec("BTC-PERP",
            ProductKind.LINEAR_PERPETUAL, "BTC", "USD", "USD", D(".01"), D(".01"), D(1),
            status=TradingStatus.ACTIVE)})
        tiers = ((CollateralTier(D(25), D(".9")), CollateralTier(None, D(".6")))
                 if tiered else (CollateralTier(None, D(".8")),))
        self.rules = PortfolioRules(1,
            {"USD": CollateralRule("USD", (CollateralTier(None, D(1)),), D(".5")),
             "BTC": CollateralRule("BTC", tiers, D(".5"))},
            {"BTC": BorrowLimits("BTC", D(10), D(".2"), D(".1"), D(".00000001"))},
            {"tier-1": LinearMarginRule("tier-1", D(".1"), D(".05"))}, D(10000))
        self.configured = configured
        self.exchange = self.reopen()
        for account in ("alice", "bob"):
            self.exchange.create_account(account)
            if D(cash):
                self.exchange.deposit(account, "usd", "USD", D(cash))
                self.reference.deposit(account, "USD", cash)
        if D(btc):
            self.exchange.deposit("alice", "owned-btc", "BTC", D(btc))
            self.reference.deposit("alice", "BTC", btc)
        self.exchange.publish_market(MarketSnapshot(1, self.now,
            {"USD": AssetSpec(D(1), D(1)), "BTC": AssetSpec(D(100), D(".8"))},
            {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))}))
        self.exchange.set_kill_switch(False)
        self.credit = CreditService(self.exchange)
        self.credit.configure_asset_limit("BTC", D(limit))
        for account in ("alice", "bob"):
            self.credit.configure_limit(account, "BTC", D(10))
        self.credit.fund_pool("pool", "BTC", D(pool), source_reference="synthetic:independent-credit")
        self.reference.fund(pool)

    def reopen(self, database=None, *, audited=False):
        return ExchangeService(database or self.database, {"USD": 8, "BTC": 8},
            product_catalog=self.catalog if self.configured else None,
            portfolio_rules=self.rules if self.configured else None,
            fee_rate=D(0), clock=lambda: self.now, decision_audit=audited)

    def snapshot(self):
        tables = ("ledger_events", "ledger_postings", "ledger_balances", "uta_accounts",
                  "uta_liabilities", "uta_events", "credit_commands", "uta_orders")
        with self.database.read_transaction() as connection:
            return {table: sorted(tuple(row) for row in connection.execute("SELECT * FROM " + table))
                    for table in tables}

    def assert_reference(self, *, tiered=False, quantities=None):
        with self.database.read_transaction() as connection:
            actual = {(row["account"], row["asset"]): int(row["units"])
                      for row in connection.execute("SELECT * FROM ledger_balances") if int(row["units"])}
            expected = {key: value for key, value in self.reference.balances.items() if value}
            self.assertEqual(actual, expected)
            replay, event_totals = defaultdict(int), defaultdict(int)
            for row in connection.execute("SELECT * FROM ledger_postings ORDER BY sequence,ordinal"):
                self.assertEqual(str(int(row["units"])), row["units"])
                replay[row["account"], row["asset"]] += int(row["units"])
                event_totals[row["sequence"], row["asset"]] += int(row["units"])
            self.assertTrue(all(total == 0 for total in event_totals.values()))
            self.assertEqual({key: value for key, value in replay.items() if value}, expected)
            actual_debt = {(row["account_id"], row["asset"]): (units(row["principal"]), units(row["interest"]))
                           for row in connection.execute("SELECT * FROM uta_liabilities")
                           if units(row["principal"]) or units(row["interest"])}
            expected_debt = {(a, "BTC"): (self.reference.principal[a], self.reference.interest[a])
                             for a in ("alice", "bob")
                             if self.reference.principal[a] or self.reference.interest[a]}
            self.assertEqual(actual_debt, expected_debt)
        if self.configured:
            for account in ("alice", "bob"):
                actual_risk = self.exchange.risk(account)
                expected_risk = self.reference.hand_risk(account, tiered=tiered,
                    order_quantity=(quantities or {}).get(account, 0))
                self.assertEqual({key: F(actual_risk[key]) for key in expected_risk}, expected_risk)

    def test_gross_borrow_interest_and_interest_first_repay_match_closed_integer_journal(self):
        self.build()
        self.credit.borrow("alice", "loan", "BTC", D(".4")); self.reference.borrow("alice", ".4")
        self.assert_reference()
        self.credit.accrue_interest("alice", "interest", "BTC", D(".01")); self.reference.accrue("alice", ".01")
        self.assert_reference()
        repaid = self.credit.repay("alice", "repay", "BTC", D(".015"))
        paid_interest, paid_principal = self.reference.repay("alice", ".015")
        self.assertEqual((units(repaid["interest_repaid"]), units(repaid["principal_repaid"])),
                         (paid_interest, paid_principal))
        self.assert_reference()
        self.assertEqual(self.reference.hand_risk("alice")["accounting_equity"], 99)
        self.assertEqual(self.reference.hand_risk("alice")["equity"], F(913, 10))
        self.exchange = self.reopen(Database(self.path)); self.credit = CreditService(self.exchange)
        self.assert_reference()
        before = self.snapshot()
        self.assertEqual(self.credit.repay("alice", "repay", "BTC", D(".0150")), repaid)
        self.assertEqual(self.snapshot(), before)

    def test_same_coin_gross_asset_tiers_are_applied_before_full_debt(self):
        self.build(tiered=True, btc=".25")
        with localcontext() as context:
            context.prec = 4
            self.credit.borrow("alice", "tiered-loan", "BTC", D(".4"))
            self.reference.borrow("alice", ".4")
            self.assert_reference(tiered=True)
        self.assertEqual(self.reference.hand_risk("alice", tiered=True)["equity"], F(213, 2))
        # Netting .65 BTC assets with .4 debt before applying the tier haircut
        # would give USD122.5, rather than the required USD106.5.
        self.assertNotEqual(self.reference.hand_risk("alice", tiered=True)["equity"], F(245, 2))

    def test_two_accounts_share_one_transaction_pool_and_asset_limit(self):
        for pool, limit, rejected_code in ((".5", "10", "credit_pool_empty"), ("1", ".5", "credit_limit")):
            with self.subTest(pool=pool, limit=limit):
                # Each subcase has its own authority; neither borrows capacity
                # or state from the earlier subcase.
                self.path = self.path.with_name("authority-" + rejected_code + ".sqlite3")
                self.build(pool=pool, limit=limit)
                with self.exchange._transaction() as connection:
                    self.credit._borrow(connection, "alice", "a", "BTC", D(".3"))
                    self.reference.borrow("alice", ".3")
                    self.credit._borrow(connection, "bob", "b", "BTC", D(".2"))
                    self.reference.borrow("bob", ".2")
                    connection.execute("SAVEPOINT third")
                    with self.assertRaises(ServiceError) as rejected:
                        self.credit._borrow(connection, "alice", "third", "BTC", D(".01"))
                    self.assertEqual(rejected.exception.code, rejected_code)
                    connection.execute("ROLLBACK TO third"); connection.execute("RELEASE third")
                self.assert_reference()
                with self.database.read_transaction() as connection:
                    self.assertEqual(connection.execute("SELECT COUNT(*) FROM credit_commands WHERE kind='borrowed'").fetchone()[0], 2)

    def test_same_transaction_loan_and_order_consume_one_margin_budget(self):
        self.build()
        with self.exchange._transaction() as connection:
            self.credit._borrow(connection, "alice", "loan", "BTC", D(".4"))
            self.reference.borrow("alice", ".4")
            self.exchange._admit_order(connection, "alice", "reserved", "BTC-PERP", D(8), D(100))
            # The independent hand budget is 100 + 32 - 40 - 8 - 80 = 4.
            connection.execute("SAVEPOINT excess")
            with self.assertRaises(ServiceError) as rejected:
                self.exchange._admit_order(connection, "alice", "excess", "BTC-PERP", D(1), D(100))
            self.assertEqual(rejected.exception.code, "insufficient_margin")
            connection.execute("ROLLBACK TO excess"); connection.execute("RELEASE excess")
        self.assert_reference(quantities={"alice": 8})
        self.assertEqual(self.reference.hand_risk("alice", order_quantity=8)["available_margin"], 4)

    def test_actual_late_rejection_requires_caller_savepoint_to_remove_staged_loan(self):
        self.build(cash="0", configured=False)
        before = self.snapshot()
        with self.exchange._transaction() as connection:
            connection.execute("SAVEPOINT rejected_loan")
            with self.assertRaises(ServiceError) as rejected:
                self.credit._borrow(connection, "alice", "late", "BTC", D(".1"))
            self.assertEqual(rejected.exception.code, "insufficient_margin")
            staged = connection.execute("SELECT principal,interest FROM uta_liabilities WHERE account_id='alice'").fetchone()
            self.assertEqual(tuple(staged), ("0.1", "0"))
            connection.execute("ROLLBACK TO rejected_loan"); connection.execute("RELEASE rejected_loan")
        self.assertEqual(self.snapshot(), before)
        self.assert_reference()
        self.exchange.deposit("alice", "collateral", "USD", D(20)); self.reference.deposit("alice", "USD", "20")
        self.credit.borrow("alice", "late", "BTC", D(".1")); self.reference.borrow("alice", ".1")
        self.assert_reference()

    def test_real_persistent_managed_state_blocks_new_loans_but_keeps_original_replay_and_repayment(self):
        self.build()
        old = self.credit.borrow("alice", "preseal", "BTC", D(".4")); self.reference.borrow("alice", ".4")
        audit = DecisionAudit(self.database)
        with self.database.transaction() as connection:
            audit.install(connection, policy=DecisionAudit.policy(self.exchange), recorded_at=self.now.isoformat())
        fence = WriterFence(self.database); fence.enable("synthetic:independent-credit")
        token = fence.acquire("synthetic:independent-owner", 30)
        self.addCleanup(lambda: fence.release(token))
        self.exchange = self.reopen(self.database.for_writer(token), audited=True)
        self.credit = CreditService(self.exchange)
        self.exchange.set_kill_switch(True); self.now += timedelta(hours=1)
        before = self.snapshot()
        self.assertEqual(self.credit.borrow("alice", "preseal", "BTC", D(".4000")), old)
        for joined in (False, True):
            with self.subTest(joined=joined):
                with self.assertRaises(ServiceError) as rejected:
                    if joined:
                        with self.exchange._transaction() as connection:
                            self.credit._borrow(connection, "alice", "new", "BTC", D(".01"))
                    else:
                        self.credit.borrow("alice", "new", "BTC", D(".01"))
                self.assertEqual((rejected.exception.code, rejected.exception.status), ("unsupported_credit_operation", 501))
                self.assertEqual(self.snapshot(), before)
        with self.assertRaises(ServiceError) as conflict:
            self.credit.borrow("alice", "preseal", "BTC", D(".41"))
        self.assertEqual((conflict.exception.code, conflict.exception.status), ("idempotency_conflict", 409))
        self.credit.repay("alice", "safe-repay", "BTC", D(".1")); self.reference.repay("alice", ".1")
        # Risk computation deliberately needs a fresh quote; cash/debt/ledger
        # reconciliation does not create one during the outage.
        self.configured = False
        self.assert_reference()

    def test_only_a_matching_existing_financial_connection_can_join(self):
        self.build()
        before = self.snapshot()
        for transaction in (self.database.read_transaction, self.database.inbox_transaction,
                            self.database._fence_transaction):
            with transaction() as connection:
                with self.assertRaises(WriterFenceError) as rejected:
                    self.credit._borrow(connection, "alice", "not-financial", "BTC", D(".01"))
                self.assertEqual(rejected.exception.code, "unguarded_connection")
        raw = sqlite3.connect(self.path)
        try:
            raw.execute("BEGIN IMMEDIATE")
            with self.assertRaises(WriterFenceError):
                self.credit._borrow(raw, "alice", "raw", "BTC", D(".01"))
            raw.rollback()
        finally:
            raw.close()
        with Database(self.path.with_name("other.sqlite3")).transaction() as connection:
            with self.assertRaises(StorageError):
                self.credit._borrow(connection, "alice", "other", "BTC", D(".01"))
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
