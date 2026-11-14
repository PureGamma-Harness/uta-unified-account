"""Independent real-storage failures of grouped admission; synthetic funds only."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Event, Thread
import unittest
from unittest.mock import patch

from uta.admission import AdmissionBatcher
from uta.ledger import LedgerError
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ExchangeService, ServiceError
from uta.storage import Database


NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)


class FaultDatabase(Database):
    max_pages = None
    defer_foreign_keys = False
    pause_commit = False
    lose_commit_response = False

    def __init__(self, path):
        super().__init__(path)
        self.at_commit = Event()
        self.release_commit = Event()

    def _connect(self):
        connection = super()._connect()
        if self.max_pages is not None:
            connection.execute("PRAGMA max_page_count=" + str(self.max_pages))
        if self.defer_foreign_keys:
            connection.execute("PRAGMA defer_foreign_keys=ON")
        return connection

    @contextmanager
    def transaction(self):
        with super().transaction() as connection:
            yield connection
            if self.pause_commit:
                self.pause_commit = False
                self.at_commit.set()
                if not self.release_commit.wait(5):
                    raise RuntimeError("test did not release COMMIT")
        if self.lose_commit_response:
            self.lose_commit_response = False
            raise RuntimeError("synthetic connection response lost after SQLite COMMIT")


def exception_chain(error):
    pending, seen = [error], set()
    while pending:
        value = pending.pop()
        if value is None or id(value) in seen:
            continue
        seen.add(id(value))
        yield value
        pending.extend((value.__cause__, value.__context__))


class GroupedAdmissionFaultTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "exchange.sqlite3"
        self.database = FaultDatabase(self.path)
        self.now = NOW
        self.service = self.reopen()
        self.service.create_account("alice")
        self.service.publish_market(MarketSnapshot(1, self.now,
            {"USD": AssetSpec(D(1), D(1))},
            {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))}))
        self.service.set_kill_switch(False)
        self.service.deposit("alice", "seed", "USD", D(100000))

    def reopen(self, database=None):
        return ExchangeService(database or self.database, {"USD": 8}, clock=lambda: self.now)

    def batcher(self, **kwargs):
        values = {"max_batch_size": 2, "max_delay_ms": 100, "queue_capacity": 16}
        values.update(kwargs)
        engine = AdmissionBatcher(self.service, **values)
        self.addCleanup(engine.close)
        return engine

    def submit(self, engine, identifier, quantity="1", account="alice"):
        return engine.submit_order(account, identifier, "BTC-PERP", D(quantity), D(100))

    def state(self):
        return (self.service.account("alice"), self.service.orders("alice"),
                self.service.ledger.journal(), self.service.events(limit=1000))

    def fatal(self, future):
        with self.assertRaises(ServiceError) as rejected:
            future.result(timeout=10)
        self.assertEqual((rejected.exception.code, rejected.exception.status),
                         ("admission_batch_failed", 503))
        return rejected.exception

    def test_no_future_reports_success_until_outer_commit_is_visible(self):
        engine = self.batcher(max_batch_size=3)
        self.database.pause_commit = True
        first, second = self.submit(engine, "one"), self.submit(engine, "two")
        rejected = self.submit(engine, "oversize", "100000")
        self.assertTrue(self.database.at_commit.wait(5))
        self.assertFalse(first.done())
        self.assertFalse(second.done())
        self.assertFalse(rejected.done(), "even a queued business rejection waits for the outer commit outcome")
        # A separate read connection sees the pre-COMMIT snapshot while the
        # actual managed writer transaction is paused before SQLite COMMIT.
        with sqlite3.connect(self.path) as observer:
            self.assertEqual(observer.execute("SELECT COUNT(*) FROM uta_orders").fetchone()[0], 0)
        self.database.release_commit.set()
        self.assertEqual(first.result(timeout=5)["status"], "OPEN")
        self.assertEqual(second.result(timeout=5)["status"], "OPEN")
        with self.assertRaises(ServiceError) as failure:
            rejected.result(timeout=5)
        self.assertEqual(failure.exception.code, "insufficient_margin")
        self.assertEqual(engine.stats()["committed_batches"], 1)
        self.assertEqual(D(self.service.account("alice")["open_order_margin"]), D("20.08"))

    def test_real_deferred_foreign_key_commit_failure_cannot_publish_early_receipts(self):
        with self.database.transaction() as conn:
            conn.execute("CREATE TABLE fault_parent (id INTEGER PRIMARY KEY)")
            conn.execute("CREATE TABLE fault_child (parent_id INTEGER REFERENCES fault_parent(id))")
        before = self.state()
        self.database.defer_foreign_keys = True
        original = self.service._admit_order
        def invalidate(connection, account_id, order_id, *args, **kwargs):
            result = original(connection, account_id, order_id, *args, **kwargs)
            if order_id == "two":
                connection.execute("INSERT INTO fault_child VALUES (999)")
            return result
        with patch.object(self.service, "_admit_order", side_effect=invalidate):
            engine = self.batcher()
            first, second = self.submit(engine, "one"), self.submit(engine, "two")
            failures = [self.fatal(first), self.fatal(second)]
        self.assertIsNot(failures[0], failures[1])
        self.assertTrue(any(isinstance(cause, sqlite3.IntegrityError)
                            for error in failures for cause in exception_chain(error)))
        self.assertEqual(self.state(), before)
        self.assertEqual(engine.stats()["committed_batches"], 0)
        with sqlite3.connect(self.path) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM fault_child").fetchone()[0], 0)

    def test_later_sql_failure_rolls_back_an_earlier_valid_admission(self):
        before = self.state()
        original = self.service._admit_order
        def fail(connection, account_id, order_id, *args, **kwargs):
            result = original(connection, account_id, order_id, *args, **kwargs)
            if order_id == "two":
                raise sqlite3.OperationalError("synthetic write failure after successful mutation")
            return result
        with patch.object(self.service, "_admit_order", side_effect=fail):
            engine = self.batcher()
            first, second = self.submit(engine, "one"), self.submit(engine, "two")
            self.fatal(first)
            self.fatal(second)
        self.assertEqual(self.state(), before)
        self.assertEqual(engine.stats()["committed_batches"], 0)

    def test_undeclared_409_policy_error_cannot_be_treated_as_safe_business_rejection(self):
        before = self.state()
        original = self.service._admit_order
        def fail(connection, account_id, order_id, *args, **kwargs):
            result = original(connection, account_id, order_id, *args, **kwargs)
            if order_id == "two":
                raise ServiceError("new_unclassified_policy_error", "synthetic unknown policy failure", 409)
            return result
        with patch.object(self.service, "_admit_order", side_effect=fail):
            engine = self.batcher()
            first, second = self.submit(engine, "one"), self.submit(engine, "two")
            self.fatal(first)
            self.fatal(second)
        self.assertEqual(self.state(), before)

    def test_error_after_real_commit_is_unknown_and_original_ids_resolve_once(self):
        engine = self.batcher()
        self.database.lose_commit_response = True
        first, second = self.submit(engine, "one"), self.submit(engine, "two")
        self.fatal(first)
        self.fatal(second)
        # The observer saw an error, but SQLite already committed. Never turn
        # this into a promise that retrying NEW IDs has no duplicate effects.
        self.assertEqual([order["order_id"] for order in self.service.orders("alice")], ["one", "two"])
        before = self.state()
        for identifier in ("one", "two"):
            self.assertEqual(self.submit(engine, identifier).result(timeout=5)["status"], "OPEN")
        self.assertEqual(self.state(), before)

    def test_ledger_corruption_wrapped_as_409_is_a_whole_batch_failure(self):
        self.service.create_account("bob")
        self.service.deposit("bob", "seed", "USD", D(1000))
        with self.database.transaction() as conn:
            conn.execute("UPDATE ledger_balances SET units='corrupt' WHERE account='customer:bob'")
        before = self.state()
        engine = self.batcher()
        first, second = self.submit(engine, "one"), self.submit(engine, "two", account="bob")
        failures = [self.fatal(first), self.fatal(second)]
        self.assertTrue(any(isinstance(cause, LedgerError)
                            for error in failures for cause in exception_chain(error)))
        self.assertEqual(self.state(), before)

    def test_business_rejection_isolated_between_valid_commands(self):
        engine = self.batcher(max_batch_size=3)
        first = self.submit(engine, "one")
        rejected = self.submit(engine, "oversize", "100000")
        third = self.submit(engine, "three")
        self.assertEqual(first.result(timeout=5)["status"], "OPEN")
        with self.assertRaises(ServiceError) as failure:
            rejected.result(timeout=5)
        self.assertEqual((failure.exception.code, failure.exception.status), ("insufficient_margin", 409))
        self.assertEqual(third.result(timeout=5)["status"], "OPEN")
        self.assertEqual([order["order_id"] for order in self.service.orders("alice")], ["one", "three"])
        self.assertEqual(D(self.service.account("alice")["open_order_margin"]), D("20.08"))
        self.assertEqual(engine.stats()["committed_batches"], 1)
        self.assertEqual(len(self.service.ledger.journal()), 1)

    def test_stale_admission_rejection_still_allows_cancellation_to_commit(self):
        self.service.submit_order("alice", "old", "BTC-PERP", D(1), D(100))
        self.now += timedelta(seconds=6)
        engine = self.batcher()
        rejected = self.submit(engine, "new")
        cancellation = engine.cancel_order("alice", "old")
        with self.assertRaises(ServiceError) as failure:
            rejected.result(timeout=5)
        self.assertEqual((failure.exception.code, failure.exception.status), ("market_unavailable", 503))
        self.assertEqual(cancellation.result(timeout=5)["status"], "CANCELLED")
        self.assertEqual([o["order_id"] for o in self.service.orders("alice")], ["old"])
        self.assertEqual(engine.stats()["committed_batches"], 1)

    def test_market_expiring_after_an_earlier_admission_aborts_before_commit_checkpoint(self):
        self.service.submit_order("alice", "old", "BTC-PERP", D(1), D(100))
        before = self.state()
        original_cancel = self.service._cancel_order
        def expire(connection, *args, **kwargs):
            result = original_cancel(connection, *args, **kwargs)
            self.now += timedelta(seconds=6)
            return result
        with patch.object(self.service, "_cancel_order", side_effect=expire):
            engine = self.batcher()
            first = self.submit(engine, "new")
            cancellation = engine.cancel_order("alice", "old")
            self.fatal(first)
            self.fatal(cancellation)
        self.assertEqual(self.state(), before)
        # A cancellation-only retry remains available during the outage. A
        # later replay of that closed ID is not a fresh exposure decision.
        self.assertEqual(engine.cancel_order("alice", "old").result(timeout=5)["status"], "CANCELLED")
        self.assertEqual(self.submit(engine, "old").result(timeout=5)["status"], "CANCELLED")

    def test_real_sqlite_full_rejects_whole_batch_and_ids_can_retry_after_recovery(self):
        with self.database.transaction() as conn:
            self.database.max_pages = conn.execute("PRAGMA page_count").fetchone()[0]
        engine = self.batcher()
        failed_ids = None
        for index in range(100):
            identifiers = [f"full-{index}-{side}-" + "x" * 105 for side in (0, 1)]
            before = self.state()
            futures = [self.submit(engine, identifier) for identifier in identifiers]
            errors = [future.exception(timeout=5) for future in futures]
            if any(errors):
                self.assertTrue(all(isinstance(error, ServiceError) and error.code == "admission_batch_failed"
                                    and error.status == 503 for error in errors), errors)
                self.assertTrue(any(isinstance(cause, sqlite3.OperationalError)
                                    and (getattr(cause, "sqlite_errorcode", None) == 13
                                         or str(cause) == "database or disk is full")
                                    for error in errors for cause in exception_chain(error)))
                self.assertEqual(self.state(), before)
                failed_ids = identifiers
                break
        self.assertIsNotNone(failed_ids, "test must exercise SQLite's actual FULL error")
        self.database.max_pages = None
        engine.close()
        self.service = self.reopen(Database(self.path))
        recovery = self.batcher()
        once = [self.submit(recovery, identifier).result(timeout=5) for identifier in failed_ids]
        count = len(self.service.orders("alice"))
        for identifier, original in zip(failed_ids, once):
            self.assertEqual(self.submit(recovery, identifier).result(timeout=5), original)
        self.assertEqual(len(self.service.orders("alice")), count)

    def test_queue_cancel_overload_and_close_do_not_lose_running_work(self):
        entered, release = Event(), Event()
        original = self.service._admit_order
        def wait(connection, account_id, order_id, *args, **kwargs):
            if order_id == "running":
                entered.set()
                if not release.wait(5):
                    raise RuntimeError("test did not release admission")
            return original(connection, account_id, order_id, *args, **kwargs)
        with patch.object(self.service, "_admit_order", side_effect=wait):
            engine = self.batcher(max_batch_size=1, max_delay_ms=0, queue_capacity=1)
            running = self.submit(engine, "running")
            self.assertTrue(entered.wait(5))
            self.assertFalse(running.cancel())
            queued = self.submit(engine, "cancel-before-running")
            overloaded = self.submit(engine, "not-queued")
            with self.assertRaises(ServiceError) as failure:
                overloaded.result(timeout=1)
            self.assertEqual((failure.exception.code, failure.exception.status), ("admission_overloaded", 503))
            self.assertTrue(queued.cancel())
            closed = Event()
            thread = Thread(target=lambda: (engine.close(), closed.set()))
            thread.start()
            self.assertFalse(closed.wait(.05))
            release.set()
            self.assertEqual(running.result(timeout=5)["status"], "OPEN")
            thread.join(5)
            self.assertFalse(thread.is_alive())
            self.assertTrue(closed.is_set())
        self.assertTrue(queued.cancelled())
        self.assertEqual([order["order_id"] for order in self.service.orders("alice")], ["running"])

    def test_panicking_or_reentrant_callback_cannot_lose_another_committed_receipt(self):
        engine = self.batcher()
        first = self.submit(engine, "one")
        observed = []
        def callback(future):
            nested = self.submit(engine, "reentrant")
            with self.assertRaises(ServiceError) as failure:
                nested.result(timeout=.2)
            observed.append(failure.exception.code)
            with self.assertRaises(RuntimeError):
                engine.close()
            raise SystemExit("synthetic callback panic")
        first.add_done_callback(callback)
        second = self.submit(engine, "two")
        self.assertEqual(first.result(timeout=5)["status"], "OPEN")
        self.assertEqual(second.result(timeout=5)["status"], "OPEN")
        engine.close()
        self.assertEqual(observed, ["admission_reentrant"])
        self.assertEqual(engine.stats()["callback_failures"], 1)
        self.assertEqual([order["order_id"] for order in self.service.orders("alice")], ["one", "two"])

    def test_reserved_cancel_capacity_is_bounded_and_does_not_overtake_queued_orders(self):
        self.service.submit_order("alice", "old", "BTC-PERP", D(1), D(100))
        entered, release = Event(), Event()
        original_submit, original_cancel = self.service._admit_order, self.service._cancel_order
        calls = []
        def submit(connection, account_id, order_id, *args, **kwargs):
            calls.append(("submit", order_id))
            if order_id == "running":
                entered.set()
                if not release.wait(5):
                    raise RuntimeError("test did not release admission")
            return original_submit(connection, account_id, order_id, *args, **kwargs)
        def cancel(connection, account_id, order_id, *args, **kwargs):
            calls.append(("cancel", order_id))
            return original_cancel(connection, account_id, order_id, *args, **kwargs)
        with patch.object(self.service, "_admit_order", side_effect=submit), \
                patch.object(self.service, "_cancel_order", side_effect=cancel):
            engine = self.batcher(max_batch_size=1, max_delay_ms=0, queue_capacity=1, cancel_reserve=1)
            running = self.submit(engine, "running")
            self.assertTrue(entered.wait(5))
            queued = self.submit(engine, "queued")
            protected_cancel = engine.cancel_order("alice", "old")
            self.assertFalse(protected_cancel.done(), "reserved slot must accept cancellation behind the queue")
            for overloaded in (self.submit(engine, "not-admitted"), engine.cancel_order("alice", "not-admitted")):
                with self.assertRaises(ServiceError) as failure:
                    overloaded.result(timeout=.5)
                self.assertEqual(failure.exception.code, "admission_overloaded")
            self.assertEqual(engine.stats()["queued"], 2)
            release.set()
            self.assertEqual(running.result(timeout=5)["status"], "OPEN")
            self.assertEqual(queued.result(timeout=5)["status"], "OPEN")
            self.assertEqual(protected_cancel.result(timeout=5)["status"], "CANCELLED")
            engine.close()
        self.assertEqual(calls, [("submit", "running"), ("submit", "queued"), ("cancel", "old")])
        self.assertEqual(D(self.service.account("alice")["open_order_margin"]), D("20.08"))

    def test_process_exit_at_batch_boundaries_and_lost_receipts_recover_exactly_once(self):
        code = r'''
import json, os, sys
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal as D
from uta.admission import AdmissionBatcher
from uta.service import ExchangeService
from uta.storage import Database
class CrashDatabase(Database):
    armed=False
    @contextmanager
    def transaction(self):
        with super().transaction() as connection:
            yield connection
            if self.armed and sys.argv[3]=='before-commit':os._exit(72)
        if self.armed and sys.argv[3]=='after-commit':os._exit(73)
db=CrashDatabase(sys.argv[1])
s=ExchangeService(db,{'USD':8},clock=lambda:datetime.fromisoformat(sys.argv[2]))
original=s._admit_order
def command(connection,account_id,order_id,*args,**kwargs):
    result=original(connection,account_id,order_id,*args,**kwargs)
    if sys.argv[3]=='during-batch' and order_id.endswith('-two'):os._exit(71)
    return result
s._admit_order=command
engine=AdmissionBatcher(s,max_batch_size=2,max_delay_ms=100,queue_capacity=8)
db.armed=True
ids=[sys.argv[3]+'-'+side for side in ('one','two')]
futures=[engine.submit_order('alice',i,'BTC-PERP',D(1),D(100)) for i in ids]
receipts=[future.result(timeout=5) for future in futures]
if sys.argv[3]=='acknowledged':print(json.dumps([r['order_id'] for r in receipts]),flush=True)
os._exit(74)
'''
        import uta.admission
        repository = Path(uta.admission.__file__).resolve().parent.parent
        for stage, expected_exit, committed in (("during-batch", 71, False), ("before-commit", 72, False),
                                                 ("after-commit", 73, True), ("acknowledged", 74, True)):
            with self.subTest(stage=stage):
                before = self.state()
                result = subprocess.run([sys.executable, "-c", code, str(self.path), self.now.isoformat(), stage],
                                        cwd=repository, capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, expected_exit, result.stdout + result.stderr)
                if stage == "acknowledged":
                    self.assertEqual(json.loads(result.stdout), [stage + "-one", stage + "-two"])
                else:
                    self.assertEqual(result.stdout, "")
                self.service = self.reopen(Database(self.path))
                if not committed:
                    self.assertEqual(self.state(), before)
                engine = self.batcher()
                ids = [stage + "-" + side for side in ("one", "two")]
                futures = [self.submit(engine, identifier) for identifier in ids]
                for future in futures:
                    self.assertEqual(future.result(timeout=5)["status"], "OPEN")
                settled = self.state()
                self.assertEqual(len(self.service.orders("alice")), len(before[1]) + 2)
                for identifier in ids:
                    self.submit(engine, identifier).result(timeout=5)
                self.assertEqual(self.state(), settled)
                engine.close()


if __name__ == "__main__":
    unittest.main()
