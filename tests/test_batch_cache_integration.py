"""Tiny actual-process combination checks at 74e03a8; no performance claim."""
from contextlib import redirect_stderr
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from io import StringIO
import json
import os
from pathlib import Path
import signal
from tempfile import TemporaryDirectory
from time import monotonic, monotonic_ns, sleep
import unittest
from unittest.mock import patch

from uta import durable_cli, durable_process
from uta.credit import CreditService
from uta.durable_batches import BatchStore
from uta.durable_process import DurableProcessRouter
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.sharding import ShardWorkerView
from uta.startup import _OwnedStartup
from uta.storage import Database, DurableLedger
from uta.supervisor import ExchangeWorker


_REAL_WORKER = durable_process._run_worker
ACCOUNTS = ("alice", "bob", "carol")


def _observed_combined_worker(*arguments):
    directory = Path(arguments[0])
    observations = directory / "test-observations"
    state = {"ddl": []}
    original_take, original_scope_verify = _OwnedStartup.take_worker, _OwnedStartup.verify_ledger
    original_ledger, original_credit = DurableLedger.verify, CreditService._verify
    original_connect, original_background = Database._connect, ExchangeWorker.run_once
    original_dispatch, original_prepare = ShardWorkerView.process_batch, BatchStore.prepare
    original_recover = ShardWorkerView.recover_batch
    def record(stage, data):
        path = observations / (stage + "-" + str(os.getpid()) + ".json")
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(dict(pid=os.getpid(), observed_ns=monotonic_ns(), **data)))
        temporary.replace(path)
    def scope_verify(scope, exchange):
        state["scope"] = scope
        return original_scope_verify(scope, exchange)
    def ledger(owned, *, connection=None):
        result = original_ledger(owned, connection=connection)
        record("ledger", dict(events=result, query_only=connection.execute("PRAGMA query_only").fetchone()[0]))
        return result
    def credit(owned, connection):
        result = original_credit(owned, connection)
        record("credit", dict(nonzero=result, query_only=connection.execute("PRAGMA query_only").fetchone()[0]))
        return result
    def connect(database):
        connection = original_connect(database)
        def trace(sql):
            scope = state.get("scope")
            if scope is not None and scope._ledger_verified and sql.lstrip().upper().startswith(("CREATE ", "ALTER ", "DROP ", "REINDEX ")):
                state["ddl"].append(sql)
        connection.set_trace_callback(trace)
        return connection
    def take(scope, exchange, **options):
        worker = original_take(scope, exchange, **options)
        state.update(worker=worker, database=exchange.database, generation=scope.token.generation)
        record("native", dict(generation=scope.token.generation,
            same_prepared=worker is scope._prepared_worker, stats=worker.normal_cache_stats(),
            thread_started=worker._thread is not None, report=worker.last_report,
            settings=arguments[2], ddl=list(state["ddl"])))
        return worker
    def background(worker):
        result = original_background(worker)
        record("background", dict(stats=worker.normal_cache_stats(), report=result, ddl=list(state["ddl"])))
        return result
    def dispatch(view, store, batches, *, size):
        if (directory / "test-pause").exists():
            record("paused", dict(size=size))
            until = monotonic() + 2
            while (directory / "test-pause").exists() and monotonic() < until:
                sleep(.002)
            if (directory / "test-pause").exists():
                raise AssertionError("bounded test dispatch pause was not released")
        return original_dispatch(view, store, batches, size=size)
    def prepare(batches, *, size=8):
        result = original_prepare(batches, size=size)
        if result is not None and (directory / "test-stop-prepared").exists():
            record("prepared", dict(attempt_id=result, size=size))
            os.kill(os.getpid(), signal.SIGSTOP)
        return result
    def recover(view, batches, attempt_id):
        result = original_recover(view, batches, attempt_id)
        with view.database.read_transaction() as connection:
            outcome = connection.execute("SELECT disposition FROM uta_command_batch_outcomes WHERE attempt_id=?", (attempt_id,)).fetchone()
        record("recovered", dict(attempt_id=attempt_id, disposition=outcome[0]))
        return result
    class ReadyObserver:
        def __init__(self, inner):
            self.inner = inner
        def send(self, value):
            if value.get("state") == "ready":
                with state["database"].read_transaction() as connection:
                    unresolved = connection.execute("SELECT COUNT(*) FROM uta_command_batch_manifests m LEFT JOIN uta_command_batch_outcomes o USING(attempt_id) WHERE o.attempt_id IS NULL").fetchone()[0]
                    outcomes = dict(connection.execute("SELECT attempt_id,disposition FROM uta_command_batch_outcomes"))
                record("ready", dict(generation=value["generation"], unresolved=unresolved,
                    outcomes=outcomes, stats=state["worker"].normal_cache_stats(), ddl=list(state["ddl"])))
            return self.inner.send(value)
        def close(self):
            self.inner.close()
    call_arguments = list(arguments)
    call_arguments[4] = ReadyObserver(arguments[4])
    with patch.object(_OwnedStartup, "verify_ledger", scope_verify), patch.object(DurableLedger, "verify", ledger), \
            patch.object(CreditService, "_verify", credit), patch.object(Database, "_connect", connect), \
            patch.object(_OwnedStartup, "take_worker", take), patch.object(ExchangeWorker, "run_once", background), \
            patch.object(ShardWorkerView, "process_batch", dispatch), patch.object(BatchStore, "prepare", prepare), \
            patch.object(ShardWorkerView, "recover_batch", recover):
        return _REAL_WORKER(*call_arguments)


class BatchCacheIntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name) / "managed"

    def initialize(self, size):
        def bootstrap(router):
            for account in ACCOUNTS:
                router.create_account(account)
                router.deposit(account, "synthetic-funding", "USD", D(1000))
        self.router = DurableProcessRouter.initialize(self.directory, 1, {"USD": 2}, managed=True,
            durable_batches=True, financial_batch_size=size, normal_cache_size=8,
            bootstrap=bootstrap, background_interval=.05, max_price_age=timedelta(seconds=30))
        self.addCleanup(self.router.close)
        self.observations = self.directory / "test-observations"
        self.observations.mkdir()
        self.addCleanup(lambda: (self.directory / "test-pause").unlink(missing_ok=True))

    def observation(self, stage, pid):
        path = self.observations / (stage + "-" + str(pid) + ".json")
        return json.loads(path.read_text()) if path.exists() else None

    def wait(self, predicate, timeout=8):
        until = monotonic() + timeout
        while monotonic() < until:
            value = predicate()
            if value:
                return value
            sleep(.005)
        self.fail("bounded combined worker fact missing: " + repr(self.router.diagnostics()))

    def activate(self):
        observer = patch.object(durable_process, "_run_worker", _observed_combined_worker)
        observer.start()
        self.addCleanup(observer.stop)
        self.addCleanup(self.router.close)  # Drain before removing spawn observation.
        self.router.start()
        self.router.publish_market(MarketSnapshot(1, datetime.now(timezone.utc),
            {"USD": AssetSpec(D(1), D(1))},
            {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))}), timeout=5)
        self.router.set_kill_switch(False, timeout=5)
        self.wait(lambda: self.router.diagnostics()["ready"])

    def assert_native(self, pid, size):
        native = self.wait(lambda: self.observation("native", pid))
        self.assertTrue(native["same_prepared"])
        self.assertFalse(native["thread_started"])
        self.assertEqual(native["report"], {"state": "not_started"})
        self.assertEqual(native["stats"], dict(capacity=8, size=0, hits=0, misses=0, evictions=0, ineligible=0))
        self.assertEqual((native["settings"]["financial_batch_size"], native["settings"]["normal_cache_size"]), (size, 8))
        for stage in ("ledger", "credit"):
            self.assertEqual(self.wait(lambda: self.observation(stage, pid))["query_only"], 1)
        self.assertEqual(self.observation("ledger", pid)["events"], 3)
        self.assertEqual(native["ddl"], [])
        ready = self.wait(lambda: self.observation("ready", pid))
        self.assertEqual((ready["stats"]["capacity"], ready["stats"]["size"], ready["unresolved"]), (8, 0, 0))
        self.assertEqual(ready["ddl"], [])
        return ready

    def enqueue_three(self, pid):
        (self.directory / "test-pause").touch()
        self.wait(lambda: self.observation("paused", pid))
        for account in ACCOUNTS:
            ack = self.router.submit_order(account, "cid:" + account, "oid:" + account, "BTC-PERP", D(1), D(100))
            self.assertEqual((ack["ack"], ack["state"]), ("durably_queued", "PENDING"))
        with self.router._database(0).read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_orders").fetchone()[0], 0)
        (self.directory / "test-pause").unlink()

    def assert_financial_once(self):
        receipts = []
        for account in ACCOUNTS:
            receipt = self.router.wait("cid:" + account, account_id=account, timeout=5)
            self.assertIsNotNone(receipt)
            self.assertEqual((receipt["state"], receipt["result"]["reserved_margin"]), ("SUCCEEDED", "10.04"))
            receipts.append(receipt)
            self.assertEqual(self.router.submit_order(account, "cid:" + account, "oid:" + account, "BTC-PERP", D(1), D(100)), receipt)
        self.router.close()
        with self.router._database(0).read_transaction() as connection:
            orders = list(connection.execute("SELECT account_id,order_id,admission_decision_id FROM uta_orders ORDER BY account_id"))
            self.assertEqual([(row[0], row[1]) for row in orders], [(a, "oid:" + a) for a in ACCOUNTS])
            self.assertTrue(all(row[2] for row in orders))
            events = list(connection.execute("SELECT account_id,payload FROM uta_events WHERE event_type='ORDER_ACCEPTED' ORDER BY account_id"))
            self.assertEqual([(row[0], json.loads(row[1])["order_id"]) for row in events], [(a, "oid:" + a) for a in ACCOUNTS])
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM ledger_events").fetchone()[0], 3)
            balances = list(connection.execute("SELECT account,units FROM ledger_balances WHERE asset='USD'"))
            self.assertEqual(sum(int(row[1]) for row in balances), 0)
            self.assertEqual({row[0]: int(row[1]) for row in balances if row[0].startswith("customer:")}, {"customer:" + a: 100000 for a in ACCOUNTS})
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
            committed = [json.loads(row[0]) for row in connection.execute("SELECT content FROM uta_command_batch_outcomes WHERE disposition='COMMITTED'")]
        self.assertTrue(committed)
        self.assertTrue(all(len(row["commands"]) == 3 and 1 <= len(row["executed"]) <= 3 for row in committed))
        self.assertTrue(all(set(row["executed"]) <= {"cid:" + a for a in ACCOUNTS} for row in committed))
        if os.environ.get("UTA_BATCH_CACHE_TEST_EVIDENCE"):
            output = Path(os.environ["UTA_BATCH_CACHE_TEST_EVIDENCE"])
            output.mkdir(parents=True, exist_ok=True)
            (output / (self._testMethodName + ".json")).write_text(json.dumps(dict(
                source_base="74e03a8", receipts=receipts, committed_outcomes=committed,
                orders=[dict(row) for row in orders], balances=[tuple(row) for row in balances],
                order_events=[dict(row) for row in events],
                observations={path.name: json.loads(path.read_text()) for path in sorted(self.observations.glob("*.json"))}), indent=2) + "\n")

    def test_batch_three_with_enabled_cache_keeps_actual_financial_receipts(self):
        self.initialize(3)
        self.activate()
        pid = self.router.worker_pid(0)
        self.assertNotEqual(pid, os.getpid())
        self.assert_native(pid, 3)
        self.wait(lambda: (value := self.observation("background", pid)) and value["stats"]["hits"] > 0)
        self.enqueue_three(pid)
        self.assert_financial_once()

    def test_batch_eight_and_cache_eight_recover_prepared_before_new_ready(self):
        self.initialize(8)
        self.activate()
        old_pid = self.router.worker_pid(0)
        old_ready = self.assert_native(old_pid, 8)
        self.wait(lambda: (value := self.observation("background", old_pid)) and value["stats"]["hits"] > 0)
        (self.directory / "test-stop-prepared").touch()
        self.enqueue_three(old_pid)
        prepared = self.wait(lambda: self.observation("prepared", old_pid))
        with self.router._database(0).read_transaction() as connection:
            manifest = json.loads(connection.execute("SELECT content FROM uta_command_batch_manifests WHERE attempt_id=?", (prepared["attempt_id"],)).fetchone()[0])
            self.assertEqual({member["command_id"] for member in manifest["members"]}, {"cid:" + a for a in ACCOUNTS})
            self.assertEqual(len(manifest["members"]), 3)
            self.assertIsNone(connection.execute("SELECT * FROM uta_command_batch_outcomes WHERE attempt_id=?", (prepared["attempt_id"],)).fetchone())
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_orders").fetchone()[0], 0)
        (self.directory / "test-stop-prepared").unlink()
        self.router.terminate_worker(0)
        new_pid = self.wait(lambda: (pid := self.router.worker_pid(0)) not in (None, old_pid) and pid)
        new_ready = self.assert_native(new_pid, 8)
        self.assertGreater(new_ready["generation"], old_ready["generation"])
        self.assertEqual(new_ready["outcomes"][prepared["attempt_id"]], "RECOVERED")
        recovered = self.wait(lambda: self.observation("recovered", new_pid))
        self.assertEqual((recovered["attempt_id"], recovered["disposition"]), (prepared["attempt_id"], "RECOVERED"))
        self.assertLess(recovered["observed_ns"], new_ready["observed_ns"])
        with self.router._database(0).read_transaction() as connection:
            outcome = json.loads(connection.execute("SELECT content FROM uta_command_batch_outcomes WHERE attempt_id=?", (prepared["attempt_id"],)).fetchone()[0])
        self.assertEqual(outcome["commands"], [{"command_id": "cid:" + a, "state": "PENDING"} for a in ACCOUNTS])
        self.assert_financial_once()

    def test_cli_keeps_both_flags_and_rejects_invalid_values_without_changing_defaults(self):
        common = ["serve", "--directory", str(self.directory)]
        combined = durable_cli._parser().parse_args(common + ["--financial-batch-size", "3", "--normal-cache-size", "8"])
        runtime = durable_cli._runtime(combined)
        self.assertEqual((runtime["financial_batch_size"], runtime["normal_cache_size"]), (3, 8))
        for flag, bad in (("--financial-batch-size", "True"), ("--financial-batch-size", "9"),
                          ("--normal-cache-size", "True"), ("--normal-cache-size", "-1"),
                          ("--normal-cache-size", "65537")):
            with self.subTest(flag=flag, bad=bad), redirect_stderr(StringIO()), self.assertRaises(SystemExit) as rejected:
                durable_cli._parser().parse_args(common + [flag, bad])
            self.assertEqual(rejected.exception.code, 2)
        for batch, cache in ((True, 8), (False, 8), (3, True), (3, False), (9, 8), (3, -1), (3, 65537)):
            with self.subTest(batch=batch, cache=cache), self.assertRaises(ValueError) as rejected:
                DurableProcessRouter(self.directory, financial_batch_size=batch, normal_cache_size=cache)
            self.assertIs(type(rejected.exception), ValueError)
            self.assertFalse(self.directory.exists())
        defaults = durable_cli._runtime(durable_cli._parser().parse_args(common))
        self.assertEqual((defaults["financial_batch_size"], defaults["normal_cache_size"]), (0, 0))


if __name__ == "__main__":
    unittest.main()
