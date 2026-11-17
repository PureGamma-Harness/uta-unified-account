"""Small current-startup integration checks; not a load or startup cache."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import os
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from time import monotonic, sleep
import unittest
from unittest.mock import patch

from uta.credit import CreditService
from uta import durable_process
from uta.durable_process import DurableProcessRouter
from uta.ledger import LedgerError
from uta.market import MarketSnapshot
from uta.matching import Matcher
from uta.models import AssetSpec, InstrumentSpec
from uta.products import ProductCatalog, ProductKind, ProductSpec, TradingStatus
from uta.service import ExchangeService, ServiceError
from uta.spot import SpotExchange
from uta.startup import StartupError, _OwnedStartup
from uta.storage import Database, DurableLedger
from uta.supervisor import ExchangeWorker
from uta.writer_fence import WriterFence


class FullSupervisionRequired(Exception):
    pass


ORIGINAL_WORKER = durable_process._run_worker


def capture_native_worker(*arguments):
    """Child lifecycle observer; every operation calls the original first."""
    directory = Path(os.environ["UTA_CACHE_STARTUP_OBSERVATIONS"])
    take = _OwnedStartup.take_worker
    verify_spot = durable_process._verify_managed_spot_source
    def record(stage, generation, data):
        path = directory / (stage + "-" + str(os.getpid()) + "-" + str(generation) + ".json")
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"pid": os.getpid(), "generation": generation, **data}))
        temporary.replace(path)
    def observed_take(scope, exchange, **options):
        worker = take(scope, exchange, **options)
        record("native-worker", scope.token.generation,
            {"stats": worker.normal_cache_stats(), "same_prepared_object": worker is scope._prepared_worker,
             "thread_started": worker._thread is not None, "report": worker.last_report})
        return worker
    def observed_spot(connection, database, scales):
        result = verify_spot(connection, database, scales)
        token = database.writer_token
        record("spot-verified", token.generation if token is not None else 0,
               {"bound": token is not None, "query_only": connection.execute("PRAGMA query_only").fetchone()[0]})
        return result
    _OwnedStartup.take_worker = observed_take
    durable_process._verify_managed_spot_source = observed_spot
    try:
        return ORIGINAL_WORKER(*arguments)
    finally:
        _OwnedStartup.take_worker = take
        durable_process._verify_managed_spot_source = verify_spot


class OwnedSupervisionCacheTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)

    def fixture(self, name, *, spot=False):
        database = Database(self.directory / (name + ".sqlite3"))
        exchange = ExchangeService(database, {"USD": 8, "BTC": 8}, decision_audit=True,
                                   max_price_age=timedelta(seconds=30))
        exchange.create_account("alice")
        exchange.deposit("alice", "seed", "USD", D(1000))
        exchange.publish_market(MarketSnapshot(1, datetime.now(timezone.utc),
            {"USD": AssetSpec(D(1), D(1)), "BTC": AssetSpec(D(100), D(".8"))},
            {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))}))
        exchange.set_kill_switch(False)
        CreditService(exchange)
        Matcher(exchange)
        ExchangeWorker(exchange)
        if spot:
            catalog = ProductCatalog(1, {"BTC-USD": ProductSpec("BTC-USD", ProductKind.SPOT,
                "BTC", "USD", "USD", D(".01"), D(".001"), D(".01"), status=TradingStatus.ACTIVE)})
            exchange.spot = SpotExchange(exchange, catalog)
        fence = WriterFence(database)
        fence.enable("owned-cache:" + name)
        token = fence.acquire("actual-owner", 30)
        return database, database.for_writer(token), exchange

    @staticmethod
    def financial(database):
        with database.read_transaction() as connection:
            return {name: sorted(tuple(row) for row in connection.execute("SELECT * FROM " + name))
                    for name in ("uta_accounts", "uta_positions", "uta_liabilities", "uta_orders", "uta_events",
                                 "ledger_events", "ledger_postings", "ledger_balances", "credit_commands")}

    @staticmethod
    def construct(bound, scope):
        exchange = ExchangeService(bound, {"USD": 8, "BTC": 8}, decision_audit=True,
                                   max_price_age=timedelta(seconds=30), _startup=scope)
        exchange.credit = CreditService(exchange, _startup=scope)
        return exchange

    @staticmethod
    def context(bound, capacity):
        return _OwnedStartup(bound, lease_seconds=5, stop=Event(), parent_pid=os.getppid(),
                             timeout=15, normal_cache_size=capacity)

    def test_native_prepared_worker_is_cold_and_reused_without_post_freeze_ddl_for_zero_and_enabled(self):
        for capacity in (0, 8):
            with self.subTest(capacity=capacity):
                database, bound, _ = self.fixture(str(capacity))
                before = self.financial(database)
                scope = self.context(bound, capacity)
                original_connect = Database._connect
                original_ledger = DurableLedger.verify
                original_credit = CreditService._verify
                verified, ddl = [], []
                def traced(candidate):
                    connection = original_connect(candidate)
                    def trace(statement):
                        if scope._ledger_verified and statement.lstrip().upper().startswith(("CREATE ", "ALTER ", "DROP ", "REINDEX ")):
                            ddl.append(statement)
                    connection.set_trace_callback(trace)
                    return connection
                def ledger(owned, *, connection=None):
                    self.assertEqual(connection.execute("PRAGMA query_only").fetchone()[0], 1)
                    result = original_ledger(owned, connection=connection)
                    verified.append("ledger")
                    return result
                def credit(owned, connection):
                    self.assertEqual(connection.execute("PRAGMA query_only").fetchone()[0], 1)
                    result = original_credit(owned, connection)
                    verified.append("credit")
                    return result
                with scope, patch.object(Database, "_connect", traced), \
                        patch.object(DurableLedger, "verify", ledger), patch.object(CreditService, "_verify", credit):
                    exchange = self.construct(bound, scope)
                    native = scope._prepared_worker
                    self.assertEqual(native.normal_cache_stats(), dict(capacity=capacity, size=0,
                        hits=0, misses=0, evictions=0, ineligible=0))
                    worker = scope.take_worker(exchange, account_batch=7, matches_per_symbol=3,
                                               normal_cache_size=capacity)
                    self.assertIs(worker, native)
                    self.assertIsNone(worker._thread)
                    self.assertEqual(worker.last_report, {"state": "not_started"})
                    scope.finish()
                self.assertEqual(verified, ["ledger", "credit"])
                self.assertEqual(ddl, [])
                self.assertEqual(before, self.financial(database))
                self.assertEqual(worker.normal_cache_stats()["size"], 0)
                worker.run_once()
                second = worker.run_once()
                if capacity:
                    self.assertEqual(second["normal_cache"]["skipped"], 1)

    def test_capacity_is_checked_before_preparation_and_mismatch_cannot_transfer_worker(self):
        database, bound, _ = self.fixture("bounds")
        before = self.financial(database)
        for value in (-1, True, 65537, 1.0):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.context(bound, value)
        scope = self.context(bound, 8)
        with scope:
            exchange = self.construct(bound, scope)
            with self.assertRaises(StartupError) as caught:
                scope.take_worker(exchange, account_batch=1, matches_per_symbol=1, normal_cache_size=0)
            self.assertEqual(caught.exception.code, "startup_worker_configuration_conflict")
            self.assertFalse(scope._worker_taken)
            worker = scope.take_worker(exchange, account_batch=1, matches_per_symbol=1, normal_cache_size=8)
            self.assertEqual(worker.normal_cache_stats()["capacity"], 8)
            scope.finish()
        self.assertEqual(before, self.financial(database))

    def test_preparation_cannot_transfer_a_worker_of_another_exchange(self):
        _, bound, _ = self.fixture("native")
        _, other_bound, _ = self.fixture("other")
        other = ExchangeService(other_bound, {"USD": 8, "BTC": 8}, decision_audit=True,
                                max_price_age=timedelta(seconds=30))
        foreign = ExchangeWorker(other, normal_cache_size=8)
        scope = self.context(bound, 8)
        with self.assertRaises(StartupError) as caught:
            with scope:
                exchange = self.construct(bound, scope)
                scope._prepared_worker = foreign  # Deliberate object-rebinding fault, not a forged verification flag.
                scope.take_worker(exchange, account_batch=1, matches_per_symbol=1, normal_cache_size=8)
        self.assertEqual(caught.exception.code, "startup_worker_configuration_conflict")

    def test_ledger_guard_corruption_still_fails_complete_native_replay_with_cache_enabled(self):
        database, bound, _ = self.fixture("bad-ledger")
        with bound.transaction() as connection:
            name = connection.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'ledger_%' ORDER BY name LIMIT 1").fetchone()[0]
            connection.execute('DROP TRIGGER "' + name + '"')
        before = self.financial(database)
        scope = self.context(bound, 8)
        with self.assertRaisesRegex(LedgerError, "journal protection trigger is missing"):
            with scope:
                self.construct(bound, scope)
        self.assertFalse(scope._finished)
        self.assertFalse(scope._worker_taken)
        self.assertEqual(before, self.financial(database))
        with database.read_transaction() as connection:
            self.assertIsNone(connection.execute("SELECT name FROM sqlite_master WHERE name=?", (name,)).fetchone())

    def test_schema_rows_spot_policy_and_relevant_trigger_changes_cannot_reuse_old_normal_proof(self):
        mutations = (
            "UPDATE ledger_schema SET version=version+1",
            "UPDATE uta_spot_schema SET version=version+1",
            "UPDATE uta_spot_config SET fee_rate='0.0005'",
            "CREATE TRIGGER cache_dependency_probe BEFORE INSERT ON uta_positions BEGIN SELECT 1; END")
        for index, statement in enumerate(mutations):
            with self.subTest(statement=statement):
                _, bound, _ = self.fixture("key-" + str(index), spot=True)
                exchange = ExchangeService(bound, {"USD": 8, "BTC": 8}, decision_audit=True,
                                           max_price_age=timedelta(seconds=30))
                worker = ExchangeWorker(exchange, normal_cache_size=8)
                worker.run_once()
                self.assertEqual(worker.run_once()["normal_cache"]["skipped"], 1)
                with bound.transaction() as connection:
                    connection.execute(statement)
                before = worker.normal_cache_stats()["hits"]
                # The test proves invalidation/fallback, not authorization of
                # an unsupported raw schema/policy edit as a new live release.
                with patch.object(exchange, "supervise_account", side_effect=FullSupervisionRequired), \
                        self.assertRaises(FullSupervisionRequired):
                    worker.run_once()
                self.assertEqual(worker.normal_cache_stats()["hits"], before)
                self.assertEqual(worker.normal_cache_stats()["size"], 0)

    def bootstrap_spot(self, router, *, live=False):
        router.create_account("alice")
        router.deposit("alice", "seed", "USD", D(1000))
        source = router._services[0]
        source.publish_market(MarketSnapshot(1, datetime.now(timezone.utc),
            {"USD": AssetSpec(D(1), D(1)), "BTC": AssetSpec(D(100), D(".8"))},
            {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))}))
        source.set_kill_switch(False)
        catalog = ProductCatalog(1, {"BTC-USD": ProductSpec("BTC-USD", ProductKind.SPOT,
            "BTC", "USD", "USD", D(".01"), D(".001"), D(".01"), status=TradingStatus.ACTIVE)})
        spot = SpotExchange(source, catalog)
        if live:
            spot.submit_order("alice", "retained-live", "BTC-USD", D(".001"), D(100))

    def test_real_managed_owner_uses_cold_native_enabled_worker_and_verifies_spot_on_restart(self):
        observations = self.directory / "observations"
        observations.mkdir()
        router = DurableProcessRouter.initialize(self.directory / "managed", 1, {"USD": 8, "BTC": 8},
            managed=True, bootstrap=self.bootstrap_spot, normal_cache_size=8,
            max_price_age=timedelta(seconds=30))
        initial_generation = WriterFence(router._database(0)).status()["generation"]
        def rows():
            return [(path.name, json.loads(path.read_text())) for path in observations.glob("*.json")]
        def wait_for(predicate):
            deadline = monotonic() + 8
            while monotonic() < deadline:
                if predicate():
                    return
                sleep(.01)
            self.fail("native owner observation not reached: " + repr(rows()))
        def ready():
            report = router.diagnostics(timeout=.2)
            if not report["ready"] and report["reason"] not in {"worker_unready", "diagnostic_timeout"}:
                self.fail("non-transient readiness failure: " + repr(report))
            return report["ready"]
        with patch.dict(os.environ, {"UTA_CACHE_STARTUP_OBSERVATIONS": str(observations)}), \
                patch.object(durable_process, "_run_worker", capture_native_worker):
            try:
                router.start()
                router.publish_market(MarketSnapshot(2, datetime.now(timezone.utc),
                    {"USD": AssetSpec(D(1), D(1)), "BTC": AssetSpec(D(100), D(".8"))},
                    {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))}), timeout=8)
                router.set_kill_switch(False, timeout=8)
                wait_for(lambda: any(name.startswith("native-worker-") for name, _ in rows()))
                old_pid = router.worker_pid(0)
                self.assertNotEqual(old_pid, os.getpid())
                router.terminate_worker(0)
                wait_for(lambda: len([name for name, _ in rows() if name.startswith("native-worker-")]) == 2)
                wait_for(lambda: len([row for name, row in rows()
                    if name.startswith("spot-verified-") and row["bound"]]) == 2)
                wait_for(ready)
                native = [row for name, row in rows() if name.startswith("native-worker-")]
                self.assertEqual(sorted(row["generation"] for row in native),
                                 [initial_generation + 1, initial_generation + 2])
                self.assertEqual(len({row["pid"] for row in native}), 2)
                for row in native:
                    self.assertEqual(row["stats"], dict(capacity=8, size=0, hits=0, misses=0, evictions=0, ineligible=0))
                    self.assertTrue(row["same_prepared_object"])
                    self.assertFalse(row["thread_started"])
                    self.assertEqual(row["report"], {"state": "not_started"})
                self.assertTrue(all(row["query_only"] == 1 for name, row in rows() if name.startswith("spot-verified-")))
            finally:
                router.close()

    def test_enabling_cache_cannot_seal_live_spot_obligations(self):
        with self.assertRaisesRegex(ServiceError, "live|spot") as caught:
            DurableProcessRouter.initialize(self.directory / "unsupported", 1, {"USD": 8, "BTC": 8},
                managed=True, bootstrap=lambda router: self.bootstrap_spot(router, live=True), normal_cache_size=8)
        self.assertEqual(caught.exception.code, "managed_spot_state_unsupported")


if __name__ == "__main__":
    unittest.main()
