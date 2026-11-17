"""Durable queue protocol and same-commit financial outcomes, synthetic funds."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from uta.credit import CreditService
from uta.durable_commands import CommandExecutionError, QueueStore
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ExchangeService, ServiceError
from uta.storage import Database, StorageError
from uta.writer_fence import WriterFence


class DurableCommandTests(unittest.TestCase):
    def setUp(self, *, bootstrap=None):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "financial.sqlite3"
        self.now = datetime(2026, 11, 16, tzinfo=timezone.utc)
        self.database = Database(self.path)
        self.legacy = ExchangeService(self.database, {"USD": 2}, clock=lambda: self.now)
        self.legacy.create_account("alice")
        self.legacy.deposit("alice", "fund", "USD", D("20.08"))
        self.legacy.publish_market(self.market())
        self.legacy.set_kill_switch(False)
        if bootstrap is not None:
            bootstrap(self.legacy)
        self.queue = QueueStore(self.database, clock=lambda: self.now, initialize=True)
        self.fence = WriterFence(self.database)
        self.fence.enable("test-inbox")
        token = self.fence.acquire("worker-one", ttl_seconds=30)
        self.writer = ExchangeService(self.database.for_writer(token), {"USD": 2}, clock=lambda: self.now)

    def market(self, version=1, mark="100"):
        return MarketSnapshot(version, self.now, {"USD": AssetSpec(D(1), D(1))},
                              {"BTC-PERP": InstrumentSpec(D(mark), D(".1"), D(".05"))})

    def submit(self, command="command", order="order", **changes):
        arguments = dict(account_id="alice", command_id=command, order_id=order,
                         symbol="BTC-PERP", quantity=D(1), limit_price=D(100))
        arguments.update(changes)
        return self.queue.enqueue_submit(**arguments)

    def test_queued_ack_has_no_reserve_and_survives_queue_restart(self):
        before = self.writer.account("alice")
        ack = self.submit()
        self.assertEqual(ack["ack"], "durably_queued")
        self.assertEqual(ack["state"], "PENDING")
        self.assertIsNone(ack["result"])
        self.assertEqual(self.writer.account("alice"), before)
        restarted = QueueStore(Database(self.path), clock=lambda: self.now)
        self.assertEqual(restarted.status("command"), ack)
        result = restarted.process_one(self.writer)
        self.assertEqual(result["state"], "SUCCEEDED")
        self.assertEqual(result["result"]["reserved_margin"], "10.04")
        self.assertEqual(self.writer.account("alice")["open_order_margin"], "10.04")
        self.assertEqual(restarted.status("command"), result)

    def test_canonical_identity_conflicts_and_stable_terminal_retries(self):
        first = self.submit()
        self.assertEqual(self.submit(quantity=D("1.000"), limit_price=D("100.00")), first)
        with self.assertRaises(ServiceError) as error:
            self.submit(quantity=D(2))
        self.assertEqual(error.exception.code, "idempotency_conflict")
        terminal = self.queue.process_one(self.writer)
        self.queue.enqueue_cancel("alice", "cancel", "order")
        self.queue.process_one(self.writer)
        # A command receipt describes its original transition, not today's
        # mutable order projection. The original accepted receipt stays OPEN.
        self.assertEqual(self.submit(), terminal)
        self.assertEqual(terminal["result"]["status"], "OPEN")
        self.assertEqual(self.writer.orders("alice")[0]["status"], "CANCELLED")

    def test_per_account_fifo_rejection_cancel_and_exact_capacity(self):
        for n in range(3):
            self.submit(f"c{n}", f"o{n}")
        self.queue.enqueue_cancel("alice", "cancel", "o0")
        completed = [self.queue.process_one(self.writer) for _ in range(4)]
        self.assertEqual([r["command_id"] for r in completed], ["c0", "c1", "c2", "cancel"])
        self.assertEqual([r["state"] for r in completed], ["SUCCEEDED", "SUCCEEDED", "REJECTED", "SUCCEEDED"])
        self.assertEqual(completed[2]["error"]["code"], "insufficient_margin")
        self.assertEqual(self.writer.account("alice")["open_order_margin"], "10.04")
        self.assertEqual(self.submit("c2", "o2"), completed[2])
        self.assertIsNone(self.queue.process_one(self.writer))
        self.assertEqual(self.writer.ledger.verify(), 1)

    def test_unknown_operations_and_liquidation_ids_never_enter_queue(self):
        for kind in ("BORROW", "APPLY_FILL", "MATCH", "WITHDRAW", "CONDITIONAL_ORDER"):
            with self.subTest(kind=kind), self.assertRaises(ServiceError) as error:
                self.queue.enqueue(kind, "unsupported", {})
            self.assertEqual(error.exception.code, "unsupported_durable_command")
        self.assertIsNone(self.queue.status("unsupported"))
        with self.assertRaises(ServiceError):
            self.submit(order="liq:forged")
        with self.assertRaises(ServiceError):
            self.queue.enqueue_cancel("alice", "forged-cancel", "liq:forged")

    def test_technical_failure_rolls_back_business_and_receipt_then_retries(self):
        self.submit()
        original = self.writer._event
        def crash(connection, kind, account, payload):
            original(connection, kind, account, payload)
            if kind == "ORDER_ACCEPTED":
                raise RuntimeError("injected after order and event")
        with patch.object(self.writer, "_event", side_effect=crash):
            with self.assertRaises(CommandExecutionError) as error:
                self.queue.process_one(self.writer)
        self.assertEqual(error.exception.command_id, "command")
        self.assertIsInstance(error.exception.__cause__, RuntimeError)
        self.assertEqual(self.queue.status("command")["state"], "PENDING")
        self.assertEqual(self.writer.orders("alice"), [])
        self.assertEqual(self.writer.account("alice")["open_order_margin"], "0")
        self.assertEqual(self.queue.process_one(self.writer)["state"], "SUCCEEDED")

    def test_late_business_rejection_rolls_back_order_event_and_reserve(self):
        self.submit()
        original = self.writer._event
        def reject(connection, kind, account, payload):
            original(connection, kind, account, payload)
            if kind == "ORDER_ACCEPTED":
                raise ServiceError("insufficient_margin", "injected business rejection", 409)
        with patch.object(self.writer, "_event", side_effect=reject):
            result = self.queue.process_one(self.writer)
        self.assertEqual(result["state"], "REJECTED")
        self.assertEqual(self.writer.orders("alice"), [])
        self.assertEqual(self.writer.account("alice")["version"], 1)
        self.assertFalse(any(e["event_type"] == "ORDER_ACCEPTED" for e in self.writer.events(limit=100)))

    def test_lost_commit_reply_is_queried_before_failure_recording(self):
        self.submit()
        original = self.writer._transaction
        @contextmanager
        def lost_reply():
            with original() as connection:
                yield connection
            raise RuntimeError("reply lost after real commit")
        with patch.object(self.writer, "_transaction", lost_reply):
            with self.assertRaises(CommandExecutionError):
                self.queue.process_one(self.writer)
        committed = self.queue.status("command")
        self.assertEqual(committed["state"], "SUCCEEDED")
        self.assertEqual(self.queue.record_failure(self.writer, "command", max_attempts=1), committed)
        self.assertEqual(self.writer.account("alice")["open_order_margin"], "10.04")

    def test_backoff_and_technical_quarantine_release_account_head(self):
        self.submit()
        self.queue.enqueue_cancel("alice", "cancel", "missing")
        with patch.object(self.writer, "_admit_order", side_effect=RuntimeError("poison")):
            with self.assertRaises(CommandExecutionError):
                self.queue.process_one(self.writer)
        delayed = self.queue.record_failure(self.writer, "command", max_attempts=2, backoff_seconds=5)
        self.assertEqual(delayed["state"], "PENDING")
        self.assertIsNone(self.queue.process_one(self.writer))
        self.now += timedelta(seconds=5)
        with patch.object(self.writer, "_admit_order", side_effect=RuntimeError("poison")):
            with self.assertRaises(CommandExecutionError):
                self.queue.process_one(self.writer)
        quarantined = self.queue.record_failure(self.writer, "command", max_attempts=2)
        self.assertEqual(quarantined["state"], "QUARANTINED")
        self.assertEqual(quarantined["error"]["status"], 503)
        self.assertEqual(self.queue.process_one(self.writer)["command_id"], "cancel")
        self.assertEqual(self.writer.orders("alice"), [])

    def test_control_lane_publishes_fresh_market_and_halt_atomically(self):
        self.submit()
        self.queue.enqueue_market("market", self.market(2, "200"))
        self.queue.enqueue_halt("halt", True)
        market = self.queue.process_one(self.writer)
        halt = self.queue.process_one(self.writer)
        order = self.queue.process_one(self.writer)
        self.assertEqual([r["command_id"] for r in (market, halt, order)], ["market", "halt", "command"])
        self.assertEqual(market["result"]["version"], 2)
        self.assertEqual(halt["result"], {"enabled": True})
        self.assertEqual(order["error"]["code"], "trading_halted")

    def test_producer_cannot_forge_replace_or_update_terminal_receipt(self):
        self.submit()
        terminal = self.queue.process_one(self.writer)
        with self.assertRaises((sqlite3.DatabaseError, StorageError)):
            with self.database.inbox_transaction() as connection:
                connection.execute("UPDATE uta_command_inbox SET state='REJECTED' WHERE command_id='command'")
        with self.assertRaises(sqlite3.DatabaseError):
            with self.writer.database.transaction() as connection:
                connection.execute("INSERT OR REPLACE INTO uta_command_inbox SELECT * FROM uta_command_inbox WHERE command_id='command'")
        with self.assertRaises(sqlite3.DatabaseError):
            with self.database.inbox_transaction() as connection:
                connection.execute("INSERT INTO uta_command_inbox(command_id,kind,payload,state,result,enqueued_at,completed_at) VALUES ('forged','SET_HALT','{}','SUCCEEDED','{}','now','now')")
        self.assertIsNone(self.queue.status("forged"))
        self.assertEqual(self.queue.status("command"), terminal)

    def test_bounded_financial_cancel_and_separate_control_capacity(self):
        database = Database(self.path.parent / "capacity.sqlite3")
        ExchangeService(database, {"USD": 2})
        queue = QueueStore(database, queue_capacity=1, cancel_reserve=1, market_capacity=1,
                           clock=lambda: self.now, initialize=True)
        queue.enqueue_submit("alice", "a", "o", "BTC-PERP", D(1), D(100))
        with self.assertRaises(ServiceError) as error:
            queue.enqueue_submit("alice", "b", "p", "BTC-PERP", D(1), D(100))
        self.assertEqual(error.exception.code, "durable_queue_overloaded")
        queue.enqueue_cancel("alice", "cancel", "o")
        with self.assertRaises(ServiceError):
            queue.enqueue_cancel("alice", "cancel-two", "o")
        queue.enqueue_market("market", self.market())
        with self.assertRaises(ServiceError):
            queue.enqueue_halt("halt", True)
        self.assertIsNone(queue.status("b"))
        self.assertEqual(queue.status("cancel")["state"], "PENDING")

    def test_guard_and_precommit_market_age_share_financial_receipt_transaction(self):
        self.submit()
        @contextmanager
        def advances_time(connection, command):
            yield
            self.now += timedelta(seconds=6)
        with self.assertRaises(CommandExecutionError):
            self.queue.process_one(self.writer, guard=advances_time)
        self.assertEqual(self.queue.status("command")["state"], "PENDING")
        self.assertEqual(self.writer.orders("alice"), [])
        self.assertEqual(self.writer.account("alice")["open_order_margin"], "0")

    def test_old_writer_and_unmanaged_worker_cannot_change_financial_state(self):
        self.submit()
        with self.assertRaises((ServiceError, StorageError)):
            self.legacy.submit_order("alice", "old-writer", "BTC-PERP", D(1), D(100))
        with self.assertRaises(CommandExecutionError):
            self.queue.process_one(self.legacy)
        self.assertEqual(self.queue.status("command")["state"], "PENDING")
        self.assertEqual(self.writer.orders("alice"), [])


class DurableRepaymentTests(unittest.TestCase):
    market = DurableCommandTests.market

    def setUp(self):
        def bootstrap(legacy):
            credit = CreditService(legacy)
            credit.configure_asset_limit("USD", D(100))
            credit.configure_limit("alice", "USD", D(100))
            credit.fund_pool("pool", "USD", D(100), source_reference="synthetic-pool-capital")
            if self._testMethodName in {
                    "test_repayment_pays_interest_then_principal_during_halt_and_price_outage",
                    "test_repayment_ledger_and_receipt_rollback_together_on_technical_failure"}:
                credit.borrow("alice", "loan", "USD", D(10))
        # Existing loans are source obligations before sealing; a managed owner
        # does not manufacture new unaudited credit to test debt repayment.
        DurableCommandTests.setUp(self, bootstrap=bootstrap)
        self.credit = CreditService(self.writer)

    def test_repayment_pays_interest_then_principal_during_halt_and_price_outage(self):
        self.credit.accrue_interest("alice", "interest", "USD", D(1))
        self.writer.set_kill_switch(True)
        self.now += timedelta(seconds=6)
        queued = self.queue.enqueue_repay("alice", "repay", "USD", D(2))
        self.assertEqual(queued["state"], "PENDING")
        self.assertEqual(self.writer.account("alice")["balances"]["USD"], "30.08")
        result = self.queue.process_one(self.writer, credit=self.credit)
        self.assertEqual(result["state"], "SUCCEEDED")
        self.assertEqual(result["result"]["interest_repaid"], "1")
        self.assertEqual(result["result"]["principal_repaid"], "1")
        self.assertEqual(self.writer.account("alice")["balances"]["USD"], "28.08")
        self.assertEqual(self.writer.account("alice")["liabilities"]["USD"]["total"], "9")
        self.assertEqual(self.queue.enqueue_repay("alice", "repay", "USD", D("2.00")), result)
        self.assertEqual(self.credit.verify()["nonzero_liabilities"], 1)

    def test_repayment_business_rejections_and_missing_worker_credit(self):
        self.queue.enqueue_repay("alice", "too-much", "USD", D(1))
        with self.assertRaises(CommandExecutionError):
            self.queue.process_one(self.writer)
        self.assertEqual(self.queue.status("too-much")["state"], "PENDING")
        rejected = self.queue.process_one(self.writer, credit=self.credit)
        self.assertEqual(rejected["state"], "REJECTED")
        self.assertEqual(rejected["error"]["code"], "repayment_exceeds_debt")
        for amount in (D(".001"), D(-1), D(0)):
            with self.subTest(amount=amount), self.assertRaises(ServiceError):
                self.queue.enqueue_repay("alice", "invalid", "USD", amount)
        self.assertIsNone(self.queue.status("invalid"))

    def test_repayment_uses_the_same_reserved_pending_budget_as_cancel(self):
        database = Database(self.path.parent / "repay-capacity.sqlite3")
        ExchangeService(database, {"USD": 2})
        queue = QueueStore(database, queue_capacity=1, cancel_reserve=1, initialize=True)
        first = queue.enqueue_submit("alice", "order", "o", "BTC-PERP", D(1), D(100))
        repayment = queue.enqueue_repay("alice", "repay", "USD", D(1))
        self.assertGreater(repayment["sequence"], first["sequence"])
        with self.assertRaises(ServiceError) as rejected:
            queue.enqueue_cancel("alice", "cancel", "o")
        self.assertEqual(rejected.exception.code, "durable_queue_overloaded")
        self.assertIsNone(queue.status("cancel"))

    def test_repayment_ledger_and_receipt_rollback_together_on_technical_failure(self):
        before = self.writer.account("alice")
        journal = self.writer.ledger.journal()
        self.queue.enqueue_repay("alice", "repay", "USD", D(2))
        original = self.credit._record
        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("after credit and ledger mutation")
        with patch.object(self.credit, "_record", side_effect=fail):
            with self.assertRaises(CommandExecutionError):
                self.queue.process_one(self.writer, credit=self.credit)
        self.assertEqual(self.queue.status("repay")["state"], "PENDING")
        self.assertEqual(self.writer.account("alice"), before)
        self.assertEqual(self.writer.ledger.journal(), journal)
        self.assertEqual(self.queue.process_one(self.writer, credit=self.credit)["state"], "SUCCEEDED")


if __name__ == "__main__":
    unittest.main()
