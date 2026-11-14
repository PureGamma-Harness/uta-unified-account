from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D, Inexact, localcontext
from pathlib import Path
import sqlite3
import tempfile
from threading import Event, Thread
import unittest
from unittest.mock import patch

from uta.admission import AdmissionBatcher
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ExchangeService, ServiceError
from uta.storage import Database


class CommitGate(Database):
    armed = False

    def __init__(self, path):
        super().__init__(path)
        self.before_commit = Event()
        self.release_commit = Event()

    @contextmanager
    def transaction(self):
        with super().transaction() as connection:
            yield connection
            if self.armed:
                self.before_commit.set()
                if not self.release_commit.wait(5):
                    raise RuntimeError("test did not release commit")


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "exchange.sqlite3"
        self.now = datetime(2026, 11, 14, tzinfo=timezone.utc)
        self.database = CommitGate(self.path)
        self.exchange = self.reopen()
        self.exchange.create_account("alice")
        self.exchange.deposit("alice", "seed", "USD", D(1000))
        self.exchange.publish_market(MarketSnapshot(1, self.now, {"USD": AssetSpec(D(1), D(1))},
            {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))}))
        self.exchange.set_kill_switch(False)

    def reopen(self):
        return ExchangeService(self.database, {"USD": 8}, clock=lambda: self.now)

    def batcher(self, **kwargs):
        batcher = AdmissionBatcher(self.exchange, **kwargs)
        self.addCleanup(batcher.close)
        return batcher

    def submit(self, batcher, identifier="order", quantity="1"):
        return batcher.submit_order("alice", identifier, "BTC-PERP", D(quantity), D(100))

    def code(self, future, expected):
        with self.assertRaises(ServiceError) as caught:
            future.result(5)
        self.assertEqual(caught.exception.code, expected)
        return caught.exception

    def state(self):
        return self.exchange.account("alice"), self.exchange.orders("alice"), self.exchange.events(limit=1000)

    def test_groups_share_one_commit_and_match_sync_receipts(self):
        batcher = self.batcher(max_batch_size=3, max_delay_ms=1000)
        futures = [self.submit(batcher, str(index)) for index in range(3)]
        batcher.close()
        self.assertEqual([f.result()["order_id"] for f in futures], ["0", "1", "2"])
        self.assertEqual(batcher.stats()["committed_batches"], 1)
        self.assertEqual(batcher.stats()["committed_commands"], 3)
        self.assertFalse(batcher.stats()["worker_alive"])
        for f in futures:
            self.assertLessEqual(f.admission_enqueued_ns, f.admission_started_ns)
            self.assertLessEqual(f.admission_started_ns, f.admission_completed_ns)

    def test_no_future_or_business_rejection_is_released_before_commit(self):
        batcher = self.batcher(max_batch_size=2, max_delay_ms=1000)
        self.database.armed = True
        good, bad = self.submit(batcher), self.submit(batcher, "too-big", "1000")
        try:
            self.assertTrue(self.database.before_commit.wait(3))
            self.assertTrue(good.running())
            self.assertFalse(good.done())
            self.assertFalse(bad.done())
            with sqlite3.connect(self.path) as reader:
                self.assertEqual(reader.execute("SELECT COUNT(*) FROM uta_orders").fetchone()[0], 0)
        finally:
            self.database.armed = False
            self.database.release_commit.set()
        batcher.close()
        self.assertEqual(good.result()["status"], "OPEN")
        self.code(bad, "insufficient_margin")

    def test_business_rejection_isolated_by_savepoint(self):
        batcher = self.batcher(max_batch_size=3, max_delay_ms=1000)
        first = self.submit(batcher, "one")
        rejected = self.submit(batcher, "huge", "1000")
        last = self.submit(batcher, "two")
        batcher.close()
        self.assertEqual(first.result()["status"], "OPEN")
        self.code(rejected, "insufficient_margin")
        self.assertEqual(last.result()["status"], "OPEN")
        self.assertEqual(len(self.exchange.orders("alice")), 2)
        self.assertEqual(batcher.stats()["business_rejected"], 1)
        self.assertEqual(batcher.stats()["committed_batches"], 1)

    def test_programmer_failure_rolls_back_entire_group_and_same_ids_can_retry(self):
        batcher = self.batcher(max_batch_size=2, max_delay_ms=1000)
        before = self.state()
        original = self.exchange._admit_order
        def fail_after_write(connection, account_id, order_id, *args, **kwargs):
            result = original(connection, account_id, order_id, *args, **kwargs)
            if order_id == "fail":
                raise RuntimeError("injected after order, version and event writes")
            return result
        with patch.object(self.exchange, "_admit_order", side_effect=fail_after_write):
            futures = [self.submit(batcher, "one"), self.submit(batcher, "fail")]
            for future in futures:
                error = self.code(future, "admission_batch_failed")
                self.assertIsInstance(error.__cause__, RuntimeError)
        self.assertEqual(self.state(), before)
        self.assertEqual(batcher.stats()["committed_batches"], 0)
        self.assertEqual(self.submit(batcher, "one").result(3)["order_id"], "one")

    def test_sql_failure_is_not_misreported_as_business_rejection(self):
        batcher = self.batcher(max_batch_size=2, max_delay_ms=1000)
        before = self.state()
        original = self.exchange._admit_order
        def fail(connection, account_id, order_id, *args, **kwargs):
            result = original(connection, account_id, order_id, *args, **kwargs)
            if order_id == "fail":
                raise sqlite3.OperationalError("synthetic storage failure")
            return result
        with patch.object(self.exchange, "_admit_order", side_effect=fail):
            futures = [self.submit(batcher, "one"), self.submit(batcher, "fail")]
            for future in futures:
                self.code(future, "admission_batch_failed")
        self.assertEqual(self.state(), before)
        self.assertEqual(batcher.stats()["business_rejected"], 0)
        self.assertEqual(batcher.stats()["technical_failed"], 2)

    def test_stale_market_rejects_submit_but_allows_same_group_cancel(self):
        self.exchange.submit_order("alice", "old", "BTC-PERP", D(1), D(100))
        self.now += timedelta(seconds=6)
        batcher = self.batcher(max_batch_size=2, max_delay_ms=1000)
        new = self.submit(batcher, "new")
        cancel = batcher.cancel_order("alice", "old")
        batcher.close()
        self.code(new, "market_unavailable")
        self.assertEqual(cancel.result()["status"], "CANCELLED")
        self.assertEqual(batcher.stats()["market_rejected"], 1)
        self.assertEqual(batcher.stats()["business_rejected"], 0)

    def test_submit_cancel_and_replay_are_sequential_within_group(self):
        batcher = self.batcher(max_batch_size=3, max_delay_ms=1000)
        opened = self.submit(batcher)
        cancelled = batcher.cancel_order("alice", "order")
        replayed = self.submit(batcher)
        batcher.close()
        self.assertEqual(opened.result()["status"], "OPEN")
        self.assertEqual(cancelled.result()["status"], "CANCELLED")
        self.assertEqual(replayed.result()["status"], "CANCELLED")
        self.assertEqual(self.exchange.risk("alice")["open_order_margin"], "0")
        restarted = self.reopen()
        self.assertEqual(restarted.submit_order("alice", "order", "BTC-PERP", D(1), D(100))["status"], "CANCELLED")

    def test_expiring_market_before_commit_rolls_back_new_admission_and_cancel(self):
        self.exchange.submit_order("alice", "old", "BTC-PERP", D(1), D(100))
        batcher = self.batcher(max_batch_size=2, max_delay_ms=1000)
        before = self.state()
        original = self.exchange._cancel_order
        def advance_clock(*args, **kwargs):
            result = original(*args, **kwargs)
            self.now += timedelta(seconds=6)
            return result
        with patch.object(self.exchange, "_cancel_order", side_effect=advance_clock):
            admitted = self.submit(batcher, "new")
            cancelled = batcher.cancel_order("alice", "old")
            self.code(admitted, "admission_batch_failed")
            self.code(cancelled, "admission_batch_failed")
        self.assertEqual(self.state(), before)
        self.assertEqual(batcher.stats()["committed_batches"], 0)

    def test_stale_idempotent_replay_does_not_require_new_market(self):
        original = self.exchange.submit_order("alice", "old", "BTC-PERP", D(1), D(100))
        self.now += timedelta(seconds=6)
        batcher = self.batcher()
        self.assertEqual(self.submit(batcher, "old").result(3), original)

    def test_unknown_service_code_is_not_silently_classified_as_business(self):
        batcher = self.batcher()
        before = self.state()
        with patch.object(self.exchange, "_admit_order", side_effect=ServiceError("new_configuration_damage", "unknown invariant", 409)):
            self.code(self.submit(batcher), "admission_batch_failed")
        self.assertEqual(self.state(), before)
        self.assertEqual(batcher.stats()["business_rejected"], 0)

    def test_pending_future_cancellation_has_no_financial_effect(self):
        batcher = self.batcher(max_batch_size=1, queue_capacity=2)
        self.database.armed = True
        first = self.submit(batcher, "first")
        try:
            self.assertTrue(self.database.before_commit.wait(3))
            pending = self.submit(batcher, "cancel-before-start")
            self.assertTrue(pending.cancel())
            self.assertFalse(first.cancel())
        finally:
            self.database.armed = False
            self.database.release_commit.set()
        batcher.close()
        self.assertTrue(pending.cancelled())
        self.assertEqual([o["order_id"] for o in self.exchange.orders("alice")], ["first"])
        self.assertEqual(batcher.stats()["cancelled_pending"], 1)

    def test_overload_is_nonblocking_and_close_drains_accepted_work(self):
        batcher = self.batcher(max_batch_size=1, queue_capacity=1)
        self.database.armed = True
        first = self.submit(batcher, "first")
        try:
            self.assertTrue(self.database.before_commit.wait(3))
            second = self.submit(batcher, "second")
            self.code(self.submit(batcher, "overload"), "admission_overloaded")
            batcher.close(wait=False)
            self.code(self.submit(batcher, "closed"), "admission_closed")
            self.assertFalse(first.done())
        finally:
            self.database.armed = False
            self.database.release_commit.set()
        batcher.close()
        self.assertEqual(first.result()["status"], "OPEN")
        self.assertEqual(second.result()["status"], "OPEN")
        self.assertEqual(batcher.stats()["overloaded"], 1)
        self.assertFalse(batcher.stats()["worker_alive"])

    def test_duplicate_ids_and_conflicts_cannot_double_reserve_under_concurrency(self):
        batcher = self.batcher(max_delay_ms=5)
        with ThreadPoolExecutor(max_workers=12) as pool:
            futures = list(pool.map(lambda _: self.submit(batcher), range(24)))
        self.assertTrue(all(f.result(5)["order_id"] == "order" for f in futures))
        self.code(self.submit(batcher, quantity="2"), "idempotency_conflict")
        self.assertEqual(len(self.exchange.orders("alice")), 1)
        self.assertEqual(self.exchange.risk("alice")["open_order_margin"], "10.04")

    def test_cancel_reserve_remains_bounded_without_overtaking_queued_submit(self):
        batcher = self.batcher(max_batch_size=1, queue_capacity=1, cancel_reserve=1)
        self.database.armed = True
        first = self.submit(batcher, "first")
        try:
            self.assertTrue(self.database.before_commit.wait(3))
            queued = self.submit(batcher, "queued")
            self.code(self.submit(batcher, "ordinary-full"), "admission_overloaded")
            cancel = batcher.cancel_order("alice", "queued")
            self.assertFalse(cancel.done())
            self.code(batcher.cancel_order("alice", "first"), "admission_overloaded")
            self.assertEqual(batcher.stats()["queued"], 2)
            self.assertEqual(batcher.stats()["total_queue_capacity"], 2)
        finally:
            self.database.armed = False
            self.database.release_commit.set()
        batcher.close()
        self.assertEqual(first.result()["status"], "OPEN")
        self.assertEqual(queued.result()["status"], "OPEN")
        self.assertEqual(cancel.result()["status"], "CANCELLED")
        self.assertEqual(self.exchange.order("alice", "queued")["status"], "CANCELLED")

    def test_input_validation_and_liquidation_id_protection_match_core(self):
        batcher = self.batcher()
        self.code(batcher.submit_order("alice", "bad", "BTC-PERP", 1.0, D(100)), "invalid_input")
        self.code(self.submit(batcher, "liq:fake"), "invalid_input")
        self.code(batcher.cancel_order("alice", "liq:protected"), "liquidation_order_protected")
        self.assertEqual(batcher.stats()["committed_commands"], 0)
        self.assertEqual(self.exchange.orders("alice"), [])

    def test_callback_cannot_reenter_worker_and_baseexception_does_not_strand_group(self):
        batcher = self.batcher(max_batch_size=2, max_delay_ms=1000)
        self.database.armed = True
        first, second = self.submit(batcher, "first"), self.submit(batcher, "second")
        callback_done = Event()
        def callback(_):
            self.code(self.submit(batcher, "callback-submit"), "admission_reentrant")
            with self.assertRaises(RuntimeError):
                batcher.close()
            callback_done.set()
            raise SystemExit("do not kill the writer")
        try:
            self.assertTrue(self.database.before_commit.wait(3))
            first.add_done_callback(callback)
        finally:
            self.database.armed = False
            self.database.release_commit.set()
        self.assertEqual(second.result(5)["status"], "OPEN")
        self.assertTrue(callback_done.wait(3))
        self.assertEqual(self.submit(batcher, "after-callback").result(5)["status"], "OPEN")
        self.assertEqual(batcher.stats()["callback_failures"], 1)

    def test_financial_results_are_independent_of_callers_decimal_context(self):
        with localcontext() as context:
            context.prec = 1
            context.traps[Inexact] = True
            batcher = self.batcher()
            result = self.submit(batcher, quantity="1.23").result(5)
        self.assertEqual(result["reserved_margin"], "12.3492")

    def test_configuration_bounds_and_thread_start_failure_do_not_write(self):
        before = self.state()
        for kwargs in ({"max_batch_size": True}, {"max_batch_size": 257}, {"max_delay_ms": float("nan")},
                       {"max_delay_ms": -1}, {"queue_capacity": 0}, {"queue_capacity": 65537},
                       {"cancel_reserve": True}, {"cancel_reserve": -1}, {"cancel_reserve": 4097}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                AdmissionBatcher(self.exchange, **kwargs)
        with patch("uta.admission.Thread.start", side_effect=RuntimeError("no threads")):
            with self.assertRaises(RuntimeError):
                AdmissionBatcher(self.exchange)
        self.assertEqual(self.state(), before)


if __name__ == "__main__":
    unittest.main()
