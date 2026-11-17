"""New credit is unavailable even to the trusted local managed owner interface.

This is not an ordinary HTTP route: managed HTTP already rejects borrowing.
The old trusted owner could commit loans without full credit decision audit.
"""
import json
import unittest
from decimal import Decimal as D

from tests import test_borrow_joined as fixture
from uta.credit import CreditService
from uta.decision_audit import DecisionAudit
from uta.service import ExchangeService, ServiceError
from uta.writer_fence import WriterFence


class ManagedBorrowBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.JoinedBorrowTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.prepare(pool="1")
        self.existing = self.fixture.credit.borrow("alice", "existing", "BTC", D(".1"))
        database = self.fixture.exchange.database
        audit = DecisionAudit(database)
        with database.transaction() as connection:
            audit.install(connection, policy=DecisionAudit.policy(self.fixture.exchange),
                          recorded_at=self.fixture.now.isoformat())
        fence = WriterFence(database)
        fence.enable("synthetic:managed-credit-boundary")
        token = fence.acquire("synthetic:trusted-owner", ttl_seconds=30)
        self.writer = ExchangeService(database.for_writer(token), {"USD": 8, "BTC": 8},
            product_catalog=self.fixture.catalog, portfolio_rules=self.fixture.rules,
            fee_rate=D(0), clock=lambda: self.fixture.now, decision_audit=True)
        self.credit = CreditService(self.writer)

    def financial_state(self):
        with self.writer.database.read_transaction() as connection:
            return {"account": self.writer.account("alice"),
                "ledger_events": connection.execute("SELECT COUNT(*) FROM ledger_events").fetchone()[0],
                "borrow_commands": connection.execute("SELECT COUNT(*) FROM credit_commands WHERE kind='borrowed'").fetchone()[0],
                "borrow_events": connection.execute("SELECT COUNT(*) FROM uta_events WHERE event_type='CREDIT_BORROWED'").fetchone()[0],
                "risk_decisions": connection.execute("SELECT COUNT(*) FROM uta_risk_decisions").fetchone()[0],
                "pool_balance": str(self.writer.ledger.balance("system:credit-pool", "BTC", connection=connection))}

    def assert_new_borrow_rejected(self, *, joined):
        before, result, error = self.financial_state(), None, None
        if joined:
            with self.writer._transaction() as connection:
                try:
                    result = self.credit._borrow(connection, "alice", "unsupported-joined", "BTC", D(".1"))
                except ServiceError as rejected:
                    error = rejected
        else:
            try:
                result = self.credit.borrow("alice", "unsupported-public", "BTC", D(".1"))
            except ServiceError as rejected:
                error = rejected
        # Assert after the actual transaction returns. In the red version both
        # paths really COMMIT, and the failure includes their actual balances.
        after = self.financial_state()
        self.assertIsNotNone(error, json.dumps({"joined": joined, "unexpected_committed_receipt": result,
            "before": before, "after": after}, sort_keys=True))
        self.assertEqual((error.code, error.status), ("unsupported_credit_operation", 501))
        self.assertEqual(after, before)

    def test_public_trusted_managed_owner_cannot_create_unaudited_credit(self):
        self.assert_new_borrow_rejected(joined=False)

    def test_private_joined_owner_cannot_create_unaudited_credit(self):
        self.assert_new_borrow_rejected(joined=True)

    def test_real_schema3_capability_still_declares_new_credit_not_captured(self):
        with self.writer.database.read_transaction() as connection:
            capability = json.loads(connection.execute("SELECT gaps FROM uta_audit_capability").fetchone()[0])
            self.assertIn("new credit decisions", capability["not_captured"])
            self.assertEqual(connection.execute("SELECT version FROM uta_schema").fetchone()[0], 3)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM writer_fence_authority").fetchone()[0], 1)
        self.assertTrue(WriterFence(self.writer.database).status()["active"])

    def test_old_command_replay_precedes_unsupported_halt_and_stale_checks(self):
        self.writer.set_kill_switch(True)
        self.fixture.now += fixture.timedelta(hours=1)
        before = self.financial_state()
        self.assertEqual(self.credit.borrow("alice", "existing", "BTC", D(".1000")), self.existing)
        with self.writer._transaction() as connection:
            self.assertEqual(self.credit._borrow(connection, "alice", "existing", "BTC", D(".10")), self.existing)
        self.assertEqual(self.financial_state(), before)
        with self.assertRaises(ServiceError) as conflict:
            self.credit.borrow("alice", "existing", "BTC", D(".2"))
        self.assertEqual((conflict.exception.code, conflict.exception.status), ("idempotency_conflict", 409))

    def test_existing_debt_same_asset_repayment_remains_supported(self):
        self.writer.set_kill_switch(True)
        self.fixture.now += fixture.timedelta(hours=1)
        repaid = self.credit.repay("alice", "repay-existing", "BTC", D(".05"))
        self.assertEqual((repaid["principal"], repaid["principal_repaid"]), ("0.05", "0.05"))
        self.assertEqual(self.writer.account("alice")["balances"]["BTC"], "0.05")
        self.writer.ledger.verify()
