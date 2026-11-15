"""Independent router batching faults through its public admission boundary.

Private hooks below inject faults only; all financial commands enter the router.
These are single-host SQLite/WAL tests, not multi-host failover certification.
"""
from __future__ import annotations

from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from pathlib import Path
import shutil
import sqlite3
from tempfile import TemporaryDirectory
from threading import Event, Thread
import unittest
from unittest.mock import patch

from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.ops import backup_database
from uta.service import ServiceError
from uta.shard_admission import RouterAdmissionBatcher
from uta.sharding import ShardRouter


NOW = datetime(2026, 11, 15, tzinfo=timezone.utc)


def causes(error):
    pending, seen = [error], set()
    while pending:
        value = pending.pop()
        if value is None or id(value) in seen:
            continue
        seen.add(id(value))
        yield value
        pending.extend((value.__cause__, value.__context__))


class ShardAdmissionFaultTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "router"
        self.now = NOW
        self.router = self.reopen()
        self.router.publish_market(MarketSnapshot(1, NOW,
            {"USD": AssetSpec(D(1), D(1))},
            {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))}))
        self.router.set_kill_switch(False)
        self.accounts = [next(f"user-{index}" for index in range(1000)
                             if self.router.shard_for(f"user-{index}") == shard)
                         for shard in range(2)]
        for account in self.accounts:
            self.router.create_account(account)
            self.router.deposit(account, "seed", "USD", D(1000))

    def reopen(self):
        return ShardRouter(self.path, 2, {"USD": 8}, clock=lambda: self.now)

    def batcher(self, router=None, **kwargs):
        settings = {"max_batch_size": 2, "max_delay_ms": 100, "queue_capacity": 8}
        settings.update(kwargs)
        engine = RouterAdmissionBatcher(router or self.router, **settings)
        self.addCleanup(engine.close)
        return engine

    def submit(self, engine, identifier, shard=0, quantity="1"):
        return engine.submit_order(self.accounts[shard], identifier, "BTC-PERP", D(quantity), D(100))

    def error(self, future, code, cause=None):
        with self.assertRaises(ServiceError) as caught:
            future.result(timeout=10)
        self.assertEqual(caught.exception.code, code)
        if cause is not None:
            self.assertTrue(any(isinstance(item, ServiceError) and item.code == cause
                                for item in causes(caught.exception)), repr(caught.exception))
        return caught.exception

    def rows(self, shard, query, parameters=()):
        with closing(sqlite3.connect(self.router._path(shard))) as connection:
            return connection.execute(query, parameters).fetchall()

    def test_shared_router_gate_covers_actual_commit_and_exclusive_halt_waits(self):
        database = self.router._services[0].database
        original = database.transaction
        at_commit, release, halted = Event(), Event(), Event()
        errors = []
        @contextmanager
        def pause_commit():
            with original() as connection:
                yield connection
                at_commit.set()
                if not release.wait(5):
                    raise RuntimeError("test did not release commit")
        def halt():
            try:
                self.router.set_kill_switch(True)
            except BaseException as failure:
                errors.append(failure)
            finally:
                halted.set()
        engine = self.batcher(max_batch_size=1)
        with patch.object(database, "transaction", side_effect=pause_commit):
            first = self.submit(engine, "before-halt")
            try:
                self.assertTrue(at_commit.wait(5))
                thread = Thread(target=halt)
                thread.start()
                self.assertFalse(halted.wait(.1), "exclusive halt crossed an uncommitted shared gate")
                self.assertFalse(first.done())
                self.assertEqual(self.rows(0, "SELECT order_id FROM uta_orders"), [])
            finally:
                release.set()
            self.assertEqual(first.result(5)["status"], "OPEN")
            thread.join(5)
            self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertTrue(self.router._state()["halted"])
        self.error(self.submit(engine, "after-halt"), "router_halted")
        self.assertEqual(engine.cancel_order(self.accounts[0], "before-halt").result(5)["status"], "CANCELLED")

    def test_pending_group_rechecks_halt_when_it_enters_gate_and_still_cancels(self):
        account = self.accounts[0]
        self.router.submit_order(account, "old", "BTC-PERP", D(1), D(100))
        original = self.router._admit_order_batch
        selected, release = Event(), Event()
        def paused(*args, **kwargs):
            selected.set()
            if not release.wait(5):
                raise RuntimeError("test did not release selected group")
            return original(*args, **kwargs)
        engine = self.batcher()
        with patch.object(self.router, "_admit_order_batch", side_effect=paused):
            admitted = self.submit(engine, "queued-before-halt")
            cancelled = engine.cancel_order(account, "old")
            try:
                self.assertTrue(selected.wait(5))
                self.router.set_kill_switch(True)
                self.assertFalse(admitted.done())
            finally:
                release.set()
            self.error(admitted, "router_halted")
            self.assertEqual(cancelled.result(5)["status"], "CANCELLED")
        self.assertEqual([row["order_id"] for row in self.router.orders(account)], ["old"])
        self.assertEqual(D(self.router.account(account)["open_order_margin"]), D(0))

    def test_runtime_identity_swap_cannot_use_prequeued_routing_to_write_wrong_shard(self):
        engine = self.batcher()
        shutil.copyfile(self.router._path(0), self.router._path(1))
        failure = self.submit(engine, "wrong-database", shard=1)
        self.error(failure, "admission_batch_failed", "shard_identity_conflict")
        self.assertTrue(self.router._state()["halted"])
        self.assertEqual(self.rows(1, "SELECT order_id FROM uta_orders"), [])

    def test_detected_same_version_wrong_payload_persists_global_halt_for_other_shards(self):
        wrong = MarketSnapshot(1, NOW, {"USD": AssetSpec(D(1), D(1))},
            {"BTC-PERP": InstrumentSpec(D(200), D(".1"), D(".05"))})
        # An uncooperative restored shard may contain a valid, decodable payload
        # with the old version but wrong bytes. The router digest is authority.
        with closing(sqlite3.connect(self.router._path(0))) as connection, connection:
            connection.execute("UPDATE uta_market SET payload=? WHERE singleton=1", (wrong.to_json(),))
        engine = self.batcher()
        self.error(self.submit(engine, "wrong-price"), "admission_batch_failed", "market_barrier_mismatch")
        self.assertTrue(self.router._state()["halted"], "detected publication inconsistency must persist a global stop")
        self.error(self.submit(engine, "other-shard-new-risk", shard=1), "router_halted")
        for shard in range(2):
            self.assertEqual(self.rows(shard, "SELECT order_id FROM uta_orders"), [])

    def test_missing_published_shard_market_is_integrity_failure_and_persists_halt(self):
        with closing(sqlite3.connect(self.router._path(0))) as connection, connection:
            connection.execute("DELETE FROM uta_market")
        engine = self.batcher()
        self.error(self.submit(engine, "missing-market"), "admission_batch_failed", "market_barrier_mismatch")
        self.assertTrue(self.router._state()["halted"])
        self.error(self.submit(engine, "after-detection", shard=1), "router_halted")
        self.assertEqual(self.rows(0, "SELECT order_id FROM uta_orders"), [])

    def test_invalid_published_shard_payload_is_integrity_failure_and_persists_halt(self):
        with closing(sqlite3.connect(self.router._path(0))) as connection, connection:
            connection.execute("UPDATE uta_market SET payload='{}' WHERE singleton=1")
        engine = self.batcher()
        self.error(self.submit(engine, "invalid-market"), "admission_batch_failed", "market_barrier_mismatch")
        self.assertTrue(self.router._state()["halted"])
        self.error(self.submit(engine, "after-detection", shard=1), "router_halted")
        self.assertEqual(self.rows(0, "SELECT order_id FROM uta_orders"), [])

    def test_ordinary_stale_publication_refuses_new_risk_without_halt_and_cancels(self):
        account = self.accounts[0]
        self.router.submit_order(account, "old", "BTC-PERP", D(1), D(100))
        self.now += timedelta(seconds=6)
        engine = self.batcher()
        refused = self.submit(engine, "stale")
        cancelled = engine.cancel_order(account, "old")
        self.error(refused, "market_unavailable")
        self.assertEqual(cancelled.result(5)["status"], "CANCELLED")
        self.assertFalse(self.router._state()["halted"], "clock age alone must not change publication authority")
        self.assertEqual(self.rows(0, "SELECT order_id,status FROM uta_orders"), [("old", "CANCELLED")])

    def test_restored_control_missing_funding_claim_halts_before_routed_batch_dml(self):
        old = self.path.parent / "old-control.sqlite3"
        backup_database(self.router.control.path, old)
        self.router.fund_credit_pool(1, "fund", "USD", D(50), source_reference="custody:synthetic:1")
        self.assertEqual(list(self.path.glob("router.sqlite3-*")), [])
        shutil.copyfile(old, self.router.control.path)
        engine = self.batcher()
        self.error(self.submit(engine, "after-invalid-restore", shard=1),
                   "admission_batch_failed", "funding_registry_conflict")
        self.assertTrue(self.router._state()["halted"])
        self.assertEqual(self.rows(1, "SELECT order_id FROM uta_orders"), [])
        self.assertEqual(self.rows(1, "SELECT command_id FROM credit_commands WHERE kind='pool_funded'"), [("fund",)])
        with self.assertRaises(ServiceError) as caught:
            self.reopen()
        self.assertEqual(caught.exception.code, "funding_registry_conflict")

    def test_post_commit_response_loss_and_cold_router_original_id_retry_are_exactly_once(self):
        database = self.router._services[0].database
        original = database.transaction
        lose_response = [True]
        @contextmanager
        def committed_then_lost():
            with original() as connection:
                yield connection
            if lose_response[0]:
                lose_response[0] = False
                raise ConnectionError("synthetic lost response after durable SQLite COMMIT")
        engine = self.batcher()
        with patch.object(database, "transaction", side_effect=committed_then_lost):
            first, second = self.submit(engine, "one"), self.submit(engine, "two")
            self.error(first, "admission_batch_failed")
            self.error(second, "admission_batch_failed")
        engine.close()
        account = self.accounts[0]
        before = (self.router.account(account), self.router.orders(account),
                  self.router.events({"shard": 0, "sequence": 0}, limit=1000))
        restarted = self.reopen()
        cold = self.batcher(restarted)
        first, second = self.submit(cold, "one"), self.submit(cold, "two")
        first.result(5)
        second.result(5)
        self.assertEqual((restarted.account(account), restarted.orders(account),
                          restarted.events({"shard": 0, "sequence": 0}, limit=1000)), before)
        self.assertEqual(D(restarted.account(account)["open_order_margin"]), D("20.08"))
        self.assertEqual(self.rows(0, "SELECT COUNT(*) FROM ledger_events"), [(1,)])
        self.assertEqual(self.rows(0, "SELECT COUNT(*) FROM uta_events WHERE event_type='ORDER_ACCEPTED'"), [(2,)])

    def test_queue_cancel_reserved_capacity_and_shutdown_preserve_every_running_promise(self):
        account = self.accounts[0]
        self.router.submit_order(account, "old", "BTC-PERP", D(1), D(100))
        entered, release = Event(), Event()
        original = self.router._admit_order_batch
        def paused(*args, **kwargs):
            entered.set()
            if not release.wait(5):
                raise RuntimeError("test did not release in-flight command")
            return original(*args, **kwargs)
        engine = self.batcher(max_batch_size=1, worker_count=1, queue_capacity=1, cancel_reserve=1)
        with patch.object(self.router, "_admit_order_batch", side_effect=paused):
            running = self.submit(engine, "running")
            try:
                self.assertTrue(entered.wait(5))
                self.assertFalse(running.cancel())
                pending = self.submit(engine, "cancelled-before-execution")
                self.assertTrue(pending.cancel())
                self.error(self.submit(engine, "overloaded"), "admission_overloaded")
                cancel = engine.cancel_order(account, "old")
                self.error(engine.cancel_order(account, "old"), "admission_overloaded")
                engine.close(wait=False)
                self.error(self.submit(engine, "after-close"), "admission_closed")
                self.assertFalse(running.done())
            finally:
                release.set()
            engine.close()
            self.assertEqual(running.result(5)["status"], "OPEN")
            self.assertEqual(cancel.result(5)["status"], "CANCELLED")
        self.assertTrue(pending.cancelled())
        self.assertEqual([row["order_id"] for row in self.router.orders(account)], ["old", "running"])
        self.assertEqual(D(self.router.account(account)["open_order_margin"]), D("10.04"))
        self.assertEqual(engine.stats()["workers_alive"], 0)

    def test_duplicate_ids_inside_one_group_reserve_once_and_conflict_has_no_effect(self):
        engine = self.batcher(max_batch_size=3)
        first = self.submit(engine, "same")
        duplicate = self.submit(engine, "same")
        conflicting = self.submit(engine, "same", quantity="2")
        self.assertEqual(first.result(5), duplicate.result(5))
        self.error(conflicting, "idempotency_conflict")
        account = self.accounts[0]
        self.assertEqual(len(self.router.orders(account)), 1)
        self.assertEqual(D(self.router.account(account)["open_order_margin"]), D("10.04"))
        self.assertEqual(self.rows(0, "SELECT COUNT(*) FROM uta_events WHERE event_type='ORDER_ACCEPTED'"), [(1,)])
        self.assertEqual(self.rows(0, "SELECT COUNT(*) FROM ledger_events"), [(1,)])


if __name__ == "__main__":
    unittest.main()
