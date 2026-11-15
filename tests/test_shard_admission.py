from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Thread
import unittest
from unittest.mock import patch

from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.reconciliation import reconcile_exchange
from uta.service import ServiceError
from uta.shard_admission import RouterAdmissionBatcher
from uta.sharding import ShardRouter


class ShardAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "router"
        self.now = datetime(2026, 11, 14, tzinfo=timezone.utc)
        self.router = self.reopen()
        self.accounts = {shard: next(f"account-{i}" for i in range(100)
            if self.router.shard_for(f"account-{i}") == shard) for shard in range(2)}
        for account in self.accounts.values():
            self.router.create_account(account)
            self.router.deposit(account, "seed", "USD", D(1000))
        self.router.publish_market(self.market())
        self.router.set_kill_switch(False)

    def reopen(self):
        return ShardRouter(self.path, 2, {"USD": 8}, clock=lambda: self.now)

    def market(self, version=1):
        return MarketSnapshot(version, self.now, {"USD": AssetSpec(D(1), D(1))},
            {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))})

    def batcher(self, **kwargs):
        batcher = RouterAdmissionBatcher(self.router, **kwargs)
        self.addCleanup(batcher.close)
        return batcher

    def submit(self, batcher, order_id="one", shard=0, quantity="1"):
        return batcher.submit_order(self.accounts[shard], order_id, "BTC-PERP", D(quantity), D(100))

    def error(self, future, code):
        with self.assertRaises(ServiceError) as caught:
            future.result(5)
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_group_commits_once_with_business_savepoints_and_fifo_cancel(self):
        batcher = self.batcher(max_batch_size=4, max_delay_ms=1000)
        first = self.submit(batcher, "one")
        rejected = self.submit(batcher, "large", quantity="1000")
        cancel = batcher.cancel_order(self.accounts[0], "one")
        second = self.submit(batcher, "two")
        batcher.close()
        self.assertEqual(first.result()["status"], "OPEN")
        self.error(rejected, "insufficient_margin")
        self.assertEqual(cancel.result()["status"], "CANCELLED")
        self.assertEqual(second.result()["status"], "OPEN")
        self.assertEqual(batcher.stats()["committed_batches"], 1)
        self.assertEqual(batcher.stats()["committed_commands"], 3)
        self.assertEqual(batcher.stats()["business_rejected"], 1)
        self.assertEqual(batcher.stats()["inflight"], 0)
        for future in (first, rejected, cancel, second):
            self.assertLessEqual(future.admission_enqueued_ns, future.admission_started_ns)
            self.assertLessEqual(future.admission_started_ns, future.admission_completed_ns)

    def test_receipts_wait_for_commit_and_exclusive_market_publication(self):
        database = self.router._services[0].database
        original = database.transaction
        entered, release, publishing, published = Event(), Event(), Event(), Event()

        @contextmanager
        def pause_commit():
            with original() as connection:
                yield connection
                entered.set()
                if not release.wait(5):
                    raise RuntimeError("commit not released")

        other = self.reopen()
        batcher = self.batcher(max_batch_size=2, max_delay_ms=1000)
        def publish():
            publishing.set()
            other.publish_market(self.market(2))
            published.set()
        try:
            with patch.object(database, "transaction", pause_commit), ThreadPoolExecutor(1) as executor:
                accepted, rejected = self.submit(batcher), self.submit(batcher, "large", quantity="1000")
                self.assertTrue(entered.wait(3))
                publication = executor.submit(publish)
                self.assertTrue(publishing.wait(1))
                self.assertFalse(published.wait(.05))
                self.assertFalse(accepted.done())
                self.assertFalse(rejected.done())
                self.assertFalse(accepted.cancel())
                release.set()
                self.assertEqual(accepted.result(3)["status"], "OPEN")
                self.error(rejected, "insufficient_margin")
                publication.result(3)
        finally:
            release.set()
        self.error(self.submit(batcher, "new-generation"), "router_halted")
        self.assertEqual(batcher.cancel_order(self.accounts[0], "one").result(3)["status"], "CANCELLED")
        self.assertEqual(other.diagnostics()["state"]["market_version"], 2)

    def test_workers_parallelize_shards_but_never_overtake_same_shard(self):
        batcher = self.batcher(max_batch_size=1, worker_count=2, max_delay_ms=0)
        original = self.router._admit_order_batch
        entered, release = Event(), Event()
        def block(shard, commands):
            if commands[0][1][1] == "blocked":
                entered.set()
                if not release.wait(5):
                    raise RuntimeError("worker not released")
            return original(shard, commands)
        try:
            with patch.object(self.router, "_admit_order_batch", block):
                blocked = self.submit(batcher, "blocked")
                self.assertTrue(entered.wait(3))
                same = batcher.cancel_order(self.accounts[0], "blocked")
                other = self.submit(batcher, "independent", shard=1)
                self.assertEqual(other.result(3)["status"], "OPEN")
                self.assertFalse(same.done())
                self.assertEqual(batcher.stats()["active_shards"], 1)
                release.set()
                self.assertEqual(blocked.result(3)["status"], "OPEN")
                self.assertEqual(same.result(3)["status"], "CANCELLED")
        finally:
            release.set()

    def test_pending_cancel_overload_reserved_capacity_and_close_drain(self):
        batcher = self.batcher(max_batch_size=1, worker_count=1, max_delay_ms=0,
                               queue_capacity=1, cancel_reserve=1)
        entered, release = Event(), Event()
        original = self.router._admit_order_batch
        def block(*args):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("worker not released")
            return original(*args)
        try:
            with patch.object(self.router, "_admit_order_batch", block):
                first = self.submit(batcher, "first")
                self.assertTrue(entered.wait(3))
                pending = self.submit(batcher, "pending")
                self.error(self.submit(batcher, "overflow"), "admission_overloaded")
                cancel = batcher.cancel_order(self.accounts[0], "first")
                self.error(batcher.cancel_order(self.accounts[0], "overflow"), "admission_overloaded")
                stats = batcher.stats()
                self.assertEqual((stats["queued"], stats["inflight"], stats["max_outstanding"]), (2, 1, 3))
                self.assertTrue(pending.cancel())
                batcher.close(wait=False)
                self.error(self.submit(batcher, "closed"), "admission_closed")
                release.set()
                batcher.close()
                self.assertEqual(first.result()["status"], "OPEN")
                self.assertEqual(cancel.result()["status"], "CANCELLED")
                self.assertEqual(batcher.stats()["cancelled_pending"], 1)
                self.assertEqual(batcher.stats()["workers_alive"], 0)
        finally:
            release.set()

    def test_rollback_is_group_wide_and_original_ids_retry_after_restart(self):
        batcher = self.batcher(max_batch_size=2, max_delay_ms=1000)
        service = self.router._services[0]
        original = service._admit_order
        def fail_after_write(connection, account, order, *args, **kwargs):
            result = original(connection, account, order, *args, **kwargs)
            if order == "fault":
                raise RuntimeError("injected after financial writes")
            return result
        with patch.object(service, "_admit_order", fail_after_write):
            first, failed = self.submit(batcher, "retry"), self.submit(batcher, "fault")
            self.assertIsInstance(self.error(first, "admission_batch_failed").__cause__, RuntimeError)
            self.error(failed, "admission_batch_failed")
        batcher.close()
        self.assertEqual(self.router.orders(self.accounts[0]), [])
        self.router = self.reopen()
        restarted = self.batcher(max_delay_ms=0)
        first = self.submit(restarted, "retry").result(3)
        self.assertEqual(self.submit(restarted, "retry").result(3), first)
        self.assertEqual(len(self.router.orders(self.accounts[0])), 1)

    def test_halt_rejects_submit_but_cancel_can_commit_same_group(self):
        account = self.accounts[0]
        self.router.submit_order(account, "live", "BTC-PERP", D(1), D(100))
        self.router.set_kill_switch(True)
        batcher = self.batcher(max_batch_size=2, max_delay_ms=1000)
        submit = self.submit(batcher, "halted")
        cancel = batcher.cancel_order(account, "live")
        batcher.close()
        self.error(submit, "router_halted")
        self.assertEqual(cancel.result()["status"], "CANCELLED")
        self.assertEqual(batcher.stats()["committed_batches"], 1)

    def test_last_freshness_check_rolls_back_whole_group(self):
        batcher = self.batcher(max_batch_size=2, max_delay_ms=1000)
        service = self.router._services[0]
        original = service._admit_order
        def advance(*args, **kwargs):
            result = original(*args, **kwargs)
            if args[2] == "last":
                self.now += timedelta(seconds=6)
            return result
        with patch.object(service, "_admit_order", advance):
            first, last = self.submit(batcher, "first"), self.submit(batcher, "last")
            self.error(first, "admission_batch_failed")
            self.error(last, "admission_batch_failed")
        self.assertEqual(self.router.orders(self.accounts[0]), [])

    def test_real_matching_receipts_positions_and_orders_survive_reopen(self):
        buyer = self.accounts[0]
        seller = next(f"seller-{i}" for i in range(100) if self.router.shard_for(f"seller-{i}") == 0)
        self.router.create_account(seller)
        self.router.deposit(seller, "seed", "USD", D(1000))
        batcher = self.batcher(max_batch_size=2, max_delay_ms=1000)
        buy = batcher.submit_order(buyer, "buy", "BTC-PERP", D(1), D(100))
        sell = batcher.submit_order(seller, "sell", "BTC-PERP", D(-1), D(100))
        batcher.close()
        self.assertEqual((buy.result()["status"], sell.result()["status"]), ("OPEN", "OPEN"))
        self.assertEqual(self.router.match_once(0, "BTC-PERP")["confirmed_trades"], 1)
        before = self.router.account(buyer), self.router.account(seller)
        restarted = self.reopen()
        self.assertEqual((restarted.account(buyer), restarted.account(seller)), before)
        self.assertEqual(restarted.orders(buyer)[0]["status"], "FILLED")
        events = restarted.events({"shard": 0, "sequence": 0}, limit=1000)["events"]
        self.assertEqual(sum(row["event_type"] == "FILL_APPLIED" for row in events), 2)
        verified = reconcile_exchange(restarted._services[0])
        self.assertEqual((verified["status"], verified["matches"], verified["paired_fills"]), ("passed", 1, 2))

    def test_callback_reentrancy_and_pool_wait_are_rejected_without_worker_loss(self):
        batcher = self.batcher(max_batch_size=2, max_delay_ms=1000, worker_count=1)
        first, second = self.submit(batcher, "first"), self.submit(batcher, "second")
        completed = Event()
        def callback(_future):
            self.error(self.submit(batcher, "recursive"), "admission_reentrant")
            with self.assertRaises(RuntimeError):
                second.result()
            with self.assertRaises(RuntimeError):
                batcher.close()
            completed.set()
            raise SystemExit("faulty callback")
        first.add_done_callback(callback)
        self.assertEqual(second.result(3)["status"], "OPEN")
        self.assertTrue(completed.wait(1))
        self.assertEqual(batcher.stats()["callback_failures"], 1)
        self.assertEqual(self.submit(batcher, "after").result(3)["status"], "OPEN")

    def test_validation_bounds_do_not_create_workers_or_queue_invalid_commands(self):
        for kwargs in ({"worker_count": 0}, {"worker_count": 3}, {"worker_count": True},
                       {"max_batch_size": 257}, {"max_delay_ms": float("nan")},
                       {"queue_capacity": 0}, {"cancel_reserve": 4097}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                RouterAdmissionBatcher(self.router, **kwargs)
        batcher = self.batcher(max_delay_ms=0)
        self.error(batcher.submit_order(self.accounts[0], "liq:reserved", "BTC-PERP", D(1), D(100)), "invalid_input")
        self.error(batcher.cancel_order(self.accounts[0], "liq:reserved"), "liquidation_order_protected")
        self.assertEqual(batcher.stats()["committed_batches"], 0)
        with self.assertRaises(ValueError):
            batcher.close(wait=1)

    def test_partial_worker_start_failure_joins_already_started_threads(self):
        original = Thread.start
        attempted = []
        def fail_second(thread):
            attempted.append(thread)
            if len(attempted) == 2:
                raise RuntimeError("injected thread start failure")
            return original(thread)
        with patch("uta.shard_admission.Thread.start", fail_second), self.assertRaises(RuntimeError):
            RouterAdmissionBatcher(self.router, worker_count=2)
        self.assertEqual(len(attempted), 2)
        self.assertTrue(all(not thread.is_alive() for thread in attempted))
        self.assertEqual(self.router.orders(self.accounts[0]), [])


if __name__ == "__main__":
    unittest.main()
