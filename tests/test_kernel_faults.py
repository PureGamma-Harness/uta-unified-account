"""Independent transaction/cache faults. All money and prices are synthetic."""
from __future__ import annotations

from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Barrier, Event, Thread
import unittest
from unittest.mock import patch

from uta.admission import AdmissionBatcher
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ExchangeService, ServiceError
from uta.storage import Database


NOW = datetime(2026, 11, 15, tzinfo=timezone.utc)


class UnknownCommitDatabase(Database):
    lose_response = False
    defer_constraints = False
    max_pages = None
    pause_commit = False

    def __init__(self, path):
        super().__init__(path)
        self.at_commit, self.release_commit = Event(), Event()

    def _connect(self):
        connection = super()._connect()
        if self.defer_constraints:
            connection.execute("PRAGMA defer_foreign_keys=ON")
        if self.max_pages is not None:
            connection.execute("PRAGMA max_page_count=" + str(self.max_pages))
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
        if self.lose_response:
            self.lose_response = False
            raise OSError("synthetic response loss after actual SQLite COMMIT")


class KernelCacheFaultTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "exchange.sqlite3"
        self.database = UnknownCommitDatabase(self.path)
        self.now = NOW
        self.service = self.reopen()
        self.service.create_account("alice")
        self.service.publish_market(self.market())
        self.service.set_kill_switch(False)
        self.service.deposit("alice", "seed", "USD", D("1000"))

    def reopen(self, database=None, scale=8):
        return ExchangeService(database or self.database, {"USD": scale},
            clock=lambda: self.now, reserve_cache_size=32, market_cache_size=4)

    def market(self, version=1, mark="100", im=".1"):
        return MarketSnapshot(version, self.now, {"USD": AssetSpec(D(1), D(1))},
            {"BTC-PERP": InstrumentSpec(D(mark), D(im), D(".05"))})

    def batcher(self, service=None, **kwargs):
        settings = {"max_batch_size": 2, "max_delay_ms": 100, "queue_capacity": 8}
        settings.update(kwargs)
        result = AdmissionBatcher(service or self.service, **settings)
        self.addCleanup(result.close)
        return result

    def submit(self, engine, identifier, account="alice", quantity="1"):
        return engine.submit_order(account, identifier, "BTC-PERP", D(quantity), D(100))

    def error(self, future, code):
        with self.assertRaises(ServiceError) as caught:
            future.result(timeout=10)
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def state(self, service=None):
        service = service or self.service
        return (service.account("alice"), service.orders("alice"),
                service.ledger.journal(), service.events(limit=1000))

    def assert_orders(self, identifiers, margin, service=None):
        service = service or self.service
        self.assertEqual([row["order_id"] for row in service.orders("alice")], identifiers)
        self.assertEqual(D(service.account("alice")["open_order_margin"]), D(margin))
        # Admission changes reservations and events, never customer cash.
        self.assertEqual(len(service.ledger.journal()), 1)
        service.ledger.verify()
        accepted = [event for event in service.events(limit=1000)
                    if event["event_type"] == "ORDER_ACCEPTED"]
        self.assertEqual(len(accepted), len(identifiers))

    def test_savepoint_rollback_cannot_leave_a_ghost_order_or_cached_account_reserve(self):
        original = self.service._admit_order
        def reject_after_mutation(connection, account, identifier, *args, **kwargs):
            result = original(connection, account, identifier, *args, **kwargs)
            if identifier == "rolled-back":
                raise ServiceError("insufficient_margin", "synthetic policy rejection after DML", 409)
            return result
        with patch.object(self.service, "_admit_order", side_effect=reject_after_mutation):
            engine = self.batcher(max_batch_size=3)
            first = self.submit(engine, "one")
            rejected = self.submit(engine, "rolled-back")
            last = self.submit(engine, "two")
            self.assertEqual(first.result(5)["status"], "OPEN")
            self.error(rejected, "insufficient_margin")
            self.assertEqual(last.result(5)["status"], "OPEN")
        self.assert_orders(["one", "two"], "20.08")
        self.assertGreater(self.service.reserve_cache_stats()["hits"], 0)

    def test_enabled_caches_cannot_publish_success_or_business_rejection_before_real_commit(self):
        engine = self.batcher()
        self.database.pause_commit = True
        accepted = self.submit(engine, "valid")
        rejected = self.submit(engine, "too-large", quantity="1000")
        try:
            self.assertTrue(self.database.at_commit.wait(5))
            self.assertFalse(accepted.done())
            self.assertFalse(rejected.done())
            with closing(sqlite3.connect(self.path)) as reader:
                self.assertEqual(reader.execute("SELECT COUNT(*) FROM uta_orders").fetchone()[0], 0)
            self.assertGreater(self.service.reserve_cache_stats()["size"], 0)
        finally:
            self.database.release_commit.set()
        self.assertEqual(accepted.result(5)["status"], "OPEN")
        self.error(rejected, "insufficient_margin")
        self.assert_orders(["valid"], "10.04")

    def test_real_sqlite_full_rolls_back_cached_admissions_and_original_ids_can_recover(self):
        with self.database.transaction() as connection:
            connection.execute("CREATE TABLE fault_blob (value BLOB)")
            self.database.max_pages = connection.execute("PRAGMA page_count").fetchone()[0]
        before = self.state()
        original = self.service._admit_order
        def exhaust_storage(connection, account, identifier, *args, **kwargs):
            result = original(connection, account, identifier, *args, **kwargs)
            if identifier == "two":
                connection.execute("INSERT INTO fault_blob VALUES (zeroblob(65536))")
            return result
        engine = self.batcher()
        with patch.object(self.service, "_admit_order", side_effect=exhaust_storage):
            first, second = self.submit(engine, "one"), self.submit(engine, "two")
            failure = self.error(first, "admission_batch_failed")
            self.error(second, "admission_batch_failed")
        chain, seen = [failure], set()
        found_full = False
        while chain:
            item = chain.pop()
            if item is None or id(item) in seen:
                continue
            seen.add(id(item))
            found_full |= isinstance(item, sqlite3.Error) and (
                getattr(item, "sqlite_errorcode", None) == sqlite3.SQLITE_FULL or
                "database or disk is full" in str(item))
            chain.extend((item.__cause__, item.__context__))
        self.assertTrue(found_full, "failure must include SQLite's actual SQLITE_FULL")
        self.database.max_pages = None
        self.assertEqual(self.state(), before)
        first, second = self.submit(engine, "one"), self.submit(engine, "two")
        first.result(5)
        second.result(5)
        self.assert_orders(["one", "two"], "20.08")

    def test_whole_batch_rollback_and_worker_restart_do_not_preserve_mutated_state(self):
        before = self.state()
        original = self.service._admit_order
        def fail_after_mutation(connection, account, identifier, *args, **kwargs):
            result = original(connection, account, identifier, *args, **kwargs)
            if identifier == "two":
                raise sqlite3.OperationalError("synthetic failed storage write")
            return result
        engine = self.batcher()
        with patch.object(self.service, "_admit_order", side_effect=fail_after_mutation):
            first, second = self.submit(engine, "one"), self.submit(engine, "two")
            self.error(first, "admission_batch_failed")
            self.error(second, "admission_batch_failed")
        engine.close()
        self.assertEqual(self.state(), before)
        restarted = self.batcher()
        first, second = self.submit(restarted, "one"), self.submit(restarted, "two")
        first.result(5)
        second.result(5)
        self.assert_orders(["one", "two"], "20.08")

    def test_real_commit_constraint_failure_does_not_turn_warm_cache_into_committed_reserve(self):
        with self.database.transaction() as connection:
            connection.execute("CREATE TABLE fault_parent (id INTEGER PRIMARY KEY)")
            connection.execute("CREATE TABLE fault_child (id INTEGER REFERENCES fault_parent(id))")
        self.database.defer_constraints = True
        before = self.state()
        original = self.service._admit_order
        def break_commit(connection, account, identifier, *args, **kwargs):
            result = original(connection, account, identifier, *args, **kwargs)
            if identifier == "two":
                connection.execute("INSERT INTO fault_child VALUES (999)")
            return result
        engine = self.batcher()
        with patch.object(self.service, "_admit_order", side_effect=break_commit):
            first, second = self.submit(engine, "one"), self.submit(engine, "two")
            self.error(first, "admission_batch_failed")
            self.error(second, "admission_batch_failed")
        self.assertEqual(self.state(), before)
        self.assertGreater(self.service.reserve_cache_stats()["hits"], 0)
        self.submit(engine, "one").result(5)
        self.assert_orders(["one"], "10.04")

    def test_post_commit_unknown_is_reconciled_by_original_ids_after_cold_restart(self):
        self.database.lose_response = True
        engine = self.batcher()
        first, second = self.submit(engine, "one"), self.submit(engine, "two")
        self.error(first, "admission_batch_failed")
        self.error(second, "admission_batch_failed")
        engine.close()
        self.assert_orders(["one", "two"], "20.08")
        before = self.state()
        cold_service = self.reopen(Database(self.path))
        self.assertEqual(cold_service.reserve_cache_stats()["size"], 0)
        cold = self.batcher(cold_service)
        first, second = self.submit(cold, "one"), self.submit(cold, "two")
        first.result(5)
        second.result(5)
        self.assertEqual(self.state(cold_service), before)

    def test_two_cached_instances_cannot_spend_the_same_accounts_last_margin(self):
        self.service.create_account("small")
        self.service.deposit("small", "small-seed", "USD", D("10.04"))
        other = self.reopen(Database(self.path))
        # Prewarm identical pure arithmetic in both services using another account.
        self.service.submit_order("alice", "warm", "BTC-PERP", D(1), D(100))
        other.risk("alice")
        engines = [self.batcher(self.service, max_batch_size=1),
                   self.batcher(other, max_batch_size=1)]
        start = Barrier(3)
        futures = [None, None]
        def run(index):
            start.wait(5)
            futures[index] = self.submit(engines[index], f"competing-{index}", "small")
        threads = [Thread(target=run, args=(index,)) for index in range(2)]
        for thread in threads:
            thread.start()
        start.wait(5)
        for thread in threads:
            thread.join(5)
            self.assertFalse(thread.is_alive())
        outcomes = []
        for future in futures:
            try:
                outcomes.append(future.result(5)["status"])
            except ServiceError as failure:
                outcomes.append(failure.code)
        self.assertCountEqual(outcomes, ["OPEN", "insufficient_margin"])
        self.assertEqual(len(other.orders("small")), 1)
        account = other.account("small")
        self.assertEqual(D(account["open_order_margin"]), D("10.04"))
        self.assertEqual(D(account["balances"]["USD"]), D("10.04"))
        other.ledger.verify()

    def test_same_account_and_market_version_in_distinct_databases_have_no_cache_alias(self):
        other_database = Database(self.path.with_name("other.sqlite3"))
        other = self.reopen(other_database)
        other.create_account("alice")
        other.publish_market(self.market(mark="200", im=".2"))
        other.set_kill_switch(False)
        other.deposit("alice", "seed", "USD", D(1000))
        first = self.service.submit_order("alice", "same-id", "BTC-PERP", D(1), D(100))
        second = other.submit_order("alice", "same-id", "BTC-PERP", D(1), D(100))
        self.assertEqual(D(first["reserved_margin"]), D("10.04"))
        self.assertEqual(D(second["reserved_margin"]), D("40.04"))
        for _ in range(3):
            self.assertEqual(D(self.service.risk("alice")["open_order_margin"]), D("10.04"))
            self.assertEqual(D(other.risk("alice")["open_order_margin"]), D("40.04"))

    def replace_payload(self, payload):
        # Fault injection bypasses publication deliberately, emulating restored
        # or corrupted persisted market data. It is never a production writer.
        with self.database.transaction() as connection:
            connection.execute("UPDATE uta_market SET payload=? WHERE singleton=1", (payload,))

    def test_same_version_changed_valid_payload_is_decoded_before_each_decision(self):
        self.service.create_account("small")
        self.service.deposit("small", "d", "USD", D("30.08"))
        self.service.submit_order("small", "one", "BTC-PERP", D(1), D(100))
        self.service.risk("small")
        self.replace_payload(self.market(mark="200").to_json())
        self.assertEqual(D(self.service.account("small")["open_order_margin"]), D("20.04"))
        engine = self.batcher()
        self.error(self.submit(engine, "two", "small"), "insufficient_margin")
        self.assertEqual(len(self.service.orders("small")), 1)

    def test_same_version_corrupt_payload_cannot_hit_prior_valid_decode_or_poison_repair(self):
        good = self.market().to_json()
        self.service.submit_order("alice", "warm", "BTC-PERP", D(1), D(100))
        self.service.risk("alice")
        corrupt = good.replace('"mark_price":"1E+2"', '"mark_price":"broken"')
        if corrupt == good:
            corrupt = good.replace('"mark_price":"100"', '"mark_price":"broken"')
        self.assertNotEqual(corrupt, good)
        self.replace_payload(corrupt)
        engine = self.batcher()
        self.error(self.submit(engine, "not-accepted"), "market_unavailable")
        self.replace_payload(good)
        self.submit(engine, "after-repair").result(5)
        self.assert_orders(["warm", "after-repair"], "20.08")

    def test_cached_decode_never_caches_freshness_and_stale_cancel_remains_available(self):
        engine = self.batcher()
        self.submit(engine, "one").result(5)
        self.service.risk("alice")
        self.now += timedelta(seconds=6)
        rejected = self.submit(engine, "stale")
        cancelled = engine.cancel_order("alice", "one")
        self.error(rejected, "market_unavailable")
        self.assertEqual(cancelled.result(5)["status"], "CANCELLED")
        self.assertEqual(self.submit(engine, "one").result(5)["status"], "CANCELLED")
        self.assertEqual(D(self.service.account("alice")["open_order_margin"]), D(0))

    def test_warm_decoding_still_rechecks_freshness_at_group_commit(self):
        self.service.submit_order("alice", "old", "BTC-PERP", D(1), D(100))
        before = self.state()
        original = self.service._cancel_order
        def late_cancel(*args, **kwargs):
            result = original(*args, **kwargs)
            self.now += timedelta(seconds=6)
            return result
        engine = self.batcher()
        with patch.object(self.service, "_cancel_order", side_effect=late_cancel):
            admitted = self.submit(engine, "new")
            cancelled = engine.cancel_order("alice", "old")
            self.error(admitted, "admission_batch_failed")
            self.error(cancelled, "admission_batch_failed")
        self.now = NOW
        self.assertEqual(self.state(), before)

    def test_partial_fill_fee_rounding_and_reprice_are_not_reused_from_old_order(self):
        service = self.reopen(Database(self.path.with_name("cents.sqlite3")), scale=2)
        service.create_account("alice")
        service.publish_market(self.market(mark="1"))
        service.set_kill_switch(False)
        service.deposit("alice", "seed", "USD", D(10))
        first = service.submit_order("alice", "buy", "BTC-PERP", D(1), D(1))
        self.assertEqual(D(first["reserved_margin"]), D(".11"))
        first = service.apply_fill("alice", "buy", "fill-1", D(".01"), D(1))
        # Hand calculation: .99 remaining * 1 * 10% = .099; the initial
        # cent ceiling was paid by fill-1, so remaining fee reserve is zero.
        self.assertEqual(D(first["reserved_margin"]), D(".099"))
        service.publish_market(self.market(2, mark="2"))
        self.assertEqual(D(service.account("alice")["open_order_margin"]), D(".198"))
        second = service.apply_fill("alice", "buy", "fill-2", D(".49"), D(1))
        self.assertEqual(D(second["reserved_margin"]), D(".1"))
        before = (service.account("alice"), service.events(limit=1000), service.ledger.journal())
        service.apply_fill("alice", "buy", "fill-2", D(".49"), D(1))
        self.assertEqual((service.account("alice"), service.events(limit=1000), service.ledger.journal()), before)
        service.ledger.verify()

    def test_process_exit_with_warm_caches_reopens_only_durable_orders_and_retries_once(self):
        code = r'''
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal as D
import os, sys
from uta.admission import AdmissionBatcher
from uta.service import ExchangeService
from uta.storage import Database
class CrashDatabase(Database):
    armed = False
    @contextmanager
    def transaction(self):
        with super().transaction() as connection:
            yield connection
            if self.armed and sys.argv[3] == "before":
                os._exit(71)
        if self.armed and sys.argv[3] == "after":
            os._exit(72)
database = CrashDatabase(sys.argv[1])
service = ExchangeService(database, {"USD":8}, clock=lambda:datetime.fromisoformat(sys.argv[2]),
                          reserve_cache_size=32, market_cache_size=4)
service.risk("alice")
assert service.reserve_cache_stats()["size"] > 0
database.armed = True
engine = AdmissionBatcher(service, max_batch_size=2, max_delay_ms=100)
first = engine.submit_order("alice", "one", "BTC-PERP", D(1), D(100))
second = engine.submit_order("alice", "two", "BTC-PERP", D(1), D(100))
first.result(5)
second.result(5)
raise AssertionError("fault injection did not terminate child")
'''
        import uta.service
        repository = Path(uta.service.__file__).resolve().parent.parent
        for stage, expected_exit, expected_orders in (("before", 71, ["warm"]),
                                                      ("after", 72, ["warm", "one", "two"])):
            with self.subTest(stage=stage):
                database = Database(self.path.with_name(f"crash-{stage}.sqlite3"))
                service = self.reopen(database)
                service.create_account("alice")
                service.publish_market(self.market())
                service.set_kill_switch(False)
                service.deposit("alice", "seed", "USD", D(1000))
                service.submit_order("alice", "warm", "BTC-PERP", D(1), D(100))
                child = subprocess.run([sys.executable, "-c", code, database.path,
                                        self.now.isoformat(), stage], cwd=repository,
                                       capture_output=True, text=True, timeout=15)
                self.assertEqual(child.returncode, expected_exit, child.stderr)
                recovered = self.reopen(database)
                self.assertEqual([row["order_id"] for row in recovered.orders("alice")], expected_orders)
                engine = self.batcher(recovered)
                first, second = self.submit(engine, "one"), self.submit(engine, "two")
                first.result(5)
                second.result(5)
                self.assert_orders(["warm", "one", "two"], "30.12", recovered)


if __name__ == "__main__":
    unittest.main()
