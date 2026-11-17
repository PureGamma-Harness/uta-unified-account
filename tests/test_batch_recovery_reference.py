"""Independent small financial/recovery contracts on real temporary SQLite.

Expected reserves and cash are hand-derived integers, never production risk
calculations. Lost replies are raised only after the original real COMMIT.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from time import sleep
import unittest
from unittest.mock import patch

from uta.durable_batches import BatchExecutionError, BatchRecoveryUnknown, BatchStore
from uta.durable_commands import QueueStore
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ExchangeService
from uta.storage import Database
from uta.writer_fence import WriterFence


ACCOUNTS = ("alice", "bob", "carol")


class IndependentBatchRecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.database = Database(Path(temporary.name) / "synthetic.sqlite3")
        self.now = datetime(2026, 11, 17, tzinfo=timezone.utc)
        legacy = ExchangeService(self.database, {"USD": 2}, clock=lambda: self.now)
        for account in ACCOUNTS:
            legacy.create_account(account)
            legacy.deposit(account, "deposit", "USD", D("20.08"))
        legacy.publish_market(MarketSnapshot(1, self.now,
            {"USD": AssetSpec(D(1), D(1))},
            {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))}))
        legacy.set_kill_switch(False)
        with self.database.transaction() as connection:
            connection.execute("CREATE TABLE review_commit_parent(id INTEGER PRIMARY KEY)")
            connection.execute("CREATE TABLE review_commit_child(id INTEGER REFERENCES review_commit_parent(id) DEFERRABLE INITIALLY DEFERRED)")
        self.queue = QueueStore(self.database, initialize=True, clock=lambda: self.now)
        BatchStore.initialize(self.database)
        self.fence = WriterFence(self.database)
        self.fence.enable("independent-batch-recovery")
        self.fence.enable_batches()
        self.token = self.fence.acquire("review-original", 30)
        self.bind()
        self.addCleanup(self.release)

    def release(self):
        self.fence.release(self.token)

    def bind(self):
        self.owned = self.database.for_writer(self.token)
        self.exchange = ExchangeService(self.owned, {"USD": 2}, clock=lambda: self.now)
        self.batches = BatchStore(self.owned, self.queue, shard=0, layout_hash="b" * 64)

    def replace_owner(self):
        old_generation = self.token.generation
        self.fence.release(self.token)
        self.token = self.fence.acquire("review-replacement", 30)
        self.assertGreater(self.token.generation, old_generation)
        self.bind()

    def enqueue(self, account, cid=None):
        cid = cid or "review:" + account
        return self.queue.enqueue_submit(account, cid, "order:" + cid,
                                         "BTC-PERP", D(1), D(100))

    def prepare_three(self):
        for account in ACCOUNTS:
            self.enqueue(account)
        attempt = self.batches.prepare()
        self.assertIsNotNone(attempt)
        return attempt

    def states(self):
        return [self.queue.status("review:" + account)["state"] for account in ACCOUNTS]

    def outcome(self, attempt):
        with self.database.read_transaction() as connection:
            row = connection.execute("SELECT disposition,content FROM uta_command_batch_outcomes WHERE attempt_id=?", (attempt,)).fetchone()
        return None if row is None else (row[0], json.loads(row[1]))

    def assert_finance(self, accounts):
        """USD100 notional: IM10 + worst fee .04 =1004 cents/order."""
        with self.database.read_transaction() as connection:
            orders = [tuple(row) for row in connection.execute(
                "SELECT account_id,quantity,filled_quantity,status FROM uta_orders ORDER BY account_id,order_id")]
            self.assertEqual(orders, [(account, "1", "0", "OPEN") for account in accounts])
            events = [row[0] for row in connection.execute(
                "SELECT account_id FROM uta_events WHERE event_type='ORDER_ACCEPTED' ORDER BY account_id,sequence")]
            self.assertEqual(events, list(accounts))
            balances = {row[0]: int(row[1]) for row in connection.execute(
                "SELECT account,units FROM ledger_balances WHERE asset='USD'")}
            self.assertEqual(balances, {**{"customer:" + account: 2008 for account in ACCOUNTS},
                                        "system:custody": -6024})
            self.assertEqual(sum(balances.values()), 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM ledger_events").fetchone()[0], 3)
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        for account in ACCOUNTS:
            self.assertEqual(self.exchange.account(account)["open_order_margin"],
                             "10.04" if account in accounts else "0")

    def finish_single(self):
        for _ in range(8):
            if self.queue.process_one(self.exchange) is None:
                return
        self.fail("bounded finite original-CID queue did not drain")

    def test_actual_sqlite_commit_failure_rolls_back_all_effects_and_terminals(self):
        attempt = self.prepare_three()
        original = self.exchange._transaction
        @contextmanager
        def invalid_deferred_reference():
            with original() as connection:
                yield connection
                connection.execute("INSERT INTO review_commit_child VALUES(7)")
        with patch.object(self.exchange, "_transaction", invalid_deferred_reference):
            with self.assertRaises(BatchExecutionError) as error:
                self.batches.process(self.exchange, attempt, soft_budget_seconds=.1)
        self.assertEqual(error.exception.phase, "commit")
        self.assertIsNone(error.exception.executing_id)
        self.assertIsInstance(error.exception.cause, sqlite3.IntegrityError)
        self.assertEqual(self.states(), ["PENDING"] * 3)
        self.assertIsNone(self.outcome(attempt))
        self.assert_finance(())
        self.assertEqual([row["attempts"] for row in self.batches.recover(attempt)], [0] * 3)
        self.finish_single()
        self.assert_finance(ACCOUNTS)

    def test_prepare_lost_reply_and_last_member_read_failure_preserve_unknown(self):
        for account in ACCOUNTS:
            self.enqueue(account)
        original = self.owned._batch_metadata_transaction
        @contextmanager
        def committed_reply_lost():
            with original() as connection:
                yield connection
            raise RuntimeError("test metadata reply was lost after actual commit")
        with patch.object(self.owned, "_batch_metadata_transaction", committed_reply_lost):
            with self.assertRaises(BatchExecutionError) as error:
                self.batches.prepare()
        attempt = error.exception.attempt_id
        self.assertEqual(error.exception.phase, "prepare")
        original_member, observed = self.batches._member, []
        def last_read_unavailable(row):
            observed.append(row["command_id"])
            if row["command_id"] == "review:carol":
                raise sqlite3.OperationalError("test read unavailable")
            return original_member(row)
        with patch.object(self.batches, "_member", last_read_unavailable):
            with self.assertRaises(BatchRecoveryUnknown):
                self.batches.resolve_preparation(attempt)
        self.assertEqual(observed, ["review:" + account for account in ACCOUNTS])
        self.assertIsNone(self.outcome(attempt))
        with self.assertRaises(BatchRecoveryUnknown):
            self.batches.prepare()
        self.assert_finance(())
        recovered = self.batches.resolve_preparation(attempt)
        self.assertEqual([row["state"] for row in recovered], ["PENDING"] * 3)
        self.assertEqual(self.outcome(attempt)[0], "RECOVERED")
        self.finish_single()
        self.assert_finance(ACCOUNTS)

    def test_financial_lost_reply_queries_every_terminal_before_reuse(self):
        attempt = self.prepare_three()
        original = self.exchange._transaction
        @contextmanager
        def committed_reply_lost():
            with original() as connection:
                yield connection
            raise RuntimeError("test financial reply was lost after actual commit")
        with patch.object(self.exchange, "_transaction", committed_reply_lost):
            with self.assertRaises(BatchExecutionError):
                self.batches.process(self.exchange, attempt, soft_budget_seconds=.1)
        self.assert_finance(ACCOUNTS)
        original_member, observed = self.batches._member, []
        def last_read_unavailable(row):
            observed.append(row["command_id"])
            if row["command_id"] == "review:carol":
                raise sqlite3.OperationalError("test last terminal unreadable")
            return original_member(row)
        with patch.object(self.batches, "_member", last_read_unavailable):
            with self.assertRaises(BatchRecoveryUnknown):
                self.batches.recover(attempt)
        self.assertEqual(observed, ["review:" + account for account in ACCOUNTS])
        results = self.batches.recover(attempt)
        self.assertEqual([row["state"] for row in results], ["SUCCEEDED"] * 3)
        self.assertEqual([row["attempts"] for row in results], [0] * 3)
        # Original enqueue replay returns the identical terminal facts.
        for account, original_result in zip(ACCOUNTS, results):
            self.assertEqual(self.enqueue(account), original_result)
        self.assertEqual(self.queue.process_one(self.exchange), None)
        self.assert_finance(ACCOUNTS)

    def test_control_arrival_after_prepare_seals_zero_prefix_without_acceptance(self):
        attempt = self.prepare_three()
        self.queue.enqueue_halt("review:halt", True)
        self.assertEqual(self.batches.process(self.exchange, attempt), [])
        self.assertEqual(self.outcome(attempt), ("COMMITTED", {
            "commands": [{"command_id": "review:" + account, "state": "PENDING"} for account in ACCOUNTS],
            "executed": []}))
        self.assertEqual(self.states(), ["PENDING"] * 3)
        self.assert_finance(())
        self.assertEqual(self.queue.process_one(self.exchange)["command_id"], "review:halt")
        self.queue.enqueue_halt("review:resume", False)
        self.assertEqual(self.queue.process_one(self.exchange)["command_id"], "review:resume")
        self.finish_single()
        self.assert_finance(ACCOUNTS)

    def test_real_slow_first_command_seals_one_prefix_and_new_generation_continues(self):
        attempt = self.prepare_three()
        original = self.exchange._admit_order
        def real_slow_first(*args, **kwargs):
            value = original(*args, **kwargs)
            sleep(.01)  # Actual work exceeds unchanged 5ms soft budget.
            return value
        with patch.object(self.exchange, "_admit_order", real_slow_first):
            results = self.batches.process(self.exchange, attempt)
        self.assertEqual([row["command_id"] for row in results], ["review:alice"])
        self.assertEqual(self.outcome(attempt)[1]["executed"], ["review:alice"])
        self.assertEqual(self.states(), ["SUCCEEDED", "PENDING", "PENDING"])
        self.replace_owner()
        self.assertEqual(self.batches.startup_unresolved, ())
        self.assertIsNone(self.batches.prepare())  # Two remaining CIDs: no new metadata commit.
        self.finish_single()
        self.assert_finance(ACCOUNTS)

    def test_mixed_terminal_and_pending_manifest_is_resolved_across_real_generation(self):
        attempt = self.prepare_three()
        self.assertEqual(self.queue.process_one(self.exchange)["command_id"], "review:alice")
        self.replace_owner()
        self.assertEqual(self.batches.startup_unresolved, (attempt,))
        recovered = self.batches.recover(attempt)
        self.assertEqual([row["state"] for row in recovered], ["SUCCEEDED", "PENDING", "PENDING"])
        self.assertEqual(self.outcome(attempt)[0], "RECOVERED")
        self.assertEqual(self.outcome(attempt)[1]["executed"], [])
        self.finish_single()
        self.assert_finance(ACCOUNTS)

    def test_backoff_head_never_releases_same_account_successor_in_batch(self):
        self.enqueue("alice", "review:a1")
        self.enqueue("alice", "review:a2")
        self.enqueue("bob", "review:b1")
        attempt = self.batches.prepare()
        # Record this one known failure before batch execution, without charging
        # the other original CIDs. It makes the account head not-yet-due.
        self.queue.record_failure(self.exchange, "review:a1", max_attempts=3,
                                  backoff_seconds=1, cause=RuntimeError("test known failure"))
        results = self.batches.process(self.exchange, attempt, soft_budget_seconds=.1)
        self.assertEqual([row["command_id"] for row in results], ["review:b1"])
        self.assertEqual(self.queue.status("review:a1")["state"], "PENDING")
        self.assertEqual(self.queue.status("review:a2")["state"], "PENDING")
        self.assertEqual([self.queue.status(cid)["attempts"] for cid in ("review:a1", "review:a2", "review:b1")], [1, 0, 0])
        self.now += timedelta(seconds=2)
        self.assertEqual(self.queue.process_one(self.exchange)["command_id"], "review:a1")
        self.assertEqual(self.queue.process_one(self.exchange)["command_id"], "review:a2")
        self.assertEqual(self.exchange.account("alice")["open_order_margin"], "20.08")
        self.assertEqual(self.exchange.ledger.verify(), 3)


if __name__ == "__main__":
    unittest.main()
