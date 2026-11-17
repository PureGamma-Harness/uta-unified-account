"""Tiny actual spawn batch/restart checks; no throughput workload."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import json
import os
from pathlib import Path
import signal
import tempfile
from time import monotonic, sleep
import unittest
from unittest.mock import patch

from uta import durable_process
from uta.durable_batches import BatchStore
from uta.durable_process import DurableProcessRouter
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ServiceError
from uta.sharding import ShardWorkerView

_REAL_RUN_WORKER = durable_process._run_worker


def _controlled_batch_worker(*args):
    directory = Path(args[0])
    original = ShardWorkerView.process_batch
    prepare = BatchStore.prepare
    def controlled(view, store, batches, *, size):
        if (directory / "test-pause").exists():
            (directory / "test-entered.tmp").write_text(str(os.getpid()))
            (directory / "test-entered.tmp").replace(directory / "test-entered")
            until = monotonic() + 2
            while (directory / "test-pause").exists() and monotonic() < until:
                sleep(.002)
            if (directory / "test-pause").exists():
                raise AssertionError("test pause was not released within original live lease")
        return original(view, store, batches, size=size)
    def prepared(batches, *, size=8):
        attempt = prepare(batches, size=size)
        if attempt is not None and (directory / "test-stop-prepared").exists():
            (directory / "test-prepared.tmp").write_text(attempt)
            (directory / "test-prepared.tmp").replace(directory / "test-prepared")
            os.kill(os.getpid(), signal.SIGSTOP)
        return attempt
    with patch.object(ShardWorkerView, "process_batch", controlled), patch.object(BatchStore, "prepare", prepared):
        _REAL_RUN_WORKER(*args)


class DurableBatchProcessTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name) / "managed"
        def bootstrap(router):
            for account in ("alice", "bob", "carol"):
                router.create_account(account)
                router.deposit(account, "fund", "USD", D(1000))
        self.router = DurableProcessRouter.initialize(self.directory, 1, {"USD": 2}, managed=True,
            durable_batches=True, financial_batch_size=8, bootstrap=bootstrap,
            max_price_age=timedelta(seconds=30), background_interval=1)
        self.addCleanup(self.router.close)
        self.addCleanup(lambda: (self.directory / "test-pause").unlink(missing_ok=True))

    def wait(self, predicate, seconds=3):
        until = monotonic() + seconds
        while monotonic() < until:
            result = predicate()
            if result:
                return result
            sleep(.005)
        self.fail("actual worker fact was not observed within bounded test window")

    def active(self):
        with patch.object(durable_process, "_run_worker", _controlled_batch_worker):
            self.router.start()
        snapshot = MarketSnapshot(1, datetime.now(timezone.utc), {"USD": AssetSpec(D(1), D(1))},
                                  {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))})
        self.router.publish_market(snapshot)
        self.router.set_kill_switch(False)
        self.wait(lambda: self.router.diagnostics()["ready"])

    def queue_three_while_paused(self):
        (self.directory / "test-pause").touch()
        self.wait(lambda: (self.directory / "test-entered").exists())
        self.assertEqual(int((self.directory / "test-entered").read_text()), self.router.worker_pid(0))
        for account in ("alice", "bob", "carol"):
            self.router.submit_order(account, "cid:" + account, "oid:" + account, "BTC-PERP", D(1), D(100))
        (self.directory / "test-pause").unlink()

    def assert_orders_once(self):
        for account in ("alice", "bob", "carol"):
            receipt = self.router.wait("cid:" + account, account_id=account, timeout=3)
            self.assertEqual(receipt["state"], "SUCCEEDED", receipt)
            self.assertEqual(receipt["attempts"], 0)
            self.assertEqual(receipt["result"]["reserved_margin"], "10.04")
        self.router.close()
        with self.router._database(0).read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_orders").fetchone()[0], 3)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_events WHERE event_type='ORDER_ACCEPTED'").fetchone()[0], 3)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_command_batch_manifests").fetchone()[0],
                             connection.execute("SELECT COUNT(*) FROM uta_command_batch_outcomes").fetchone()[0])
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_real_process_dispatch_uses_durable_manifest_and_financial_receipts(self):
        self.active()
        self.queue_three_while_paused()
        self.assert_orders_once()
        with self.router._database(0).read_transaction() as connection:
            outcomes = [json.loads(row[0]) for row in connection.execute("SELECT content FROM uta_command_batch_outcomes WHERE disposition='COMMITTED'")]
        self.assertTrue(outcomes)
        executed = sum(len(value["executed"]) for value in outcomes)
        self.assertGreaterEqual(executed, 1)
        self.assertLessEqual(executed, 3)
        self.assertTrue(all(len(value["commands"]) == 3 for value in outcomes))

    def test_killed_owner_after_prepared_commit_is_recovered_before_new_owner_ready(self):
        self.active()
        old_pid = self.router.worker_pid(0)
        (self.directory / "test-stop-prepared").touch()
        self.queue_three_while_paused()
        self.wait(lambda: (self.directory / "test-prepared").exists())
        attempt = (self.directory / "test-prepared").read_text()
        (self.directory / "test-stop-prepared").unlink()
        self.router.terminate_worker(0)
        self.wait(lambda: self.router.worker_pid(0) not in (None, old_pid), seconds=8)
        self.wait(lambda: self.router.diagnostics()["ready"], seconds=8)
        self.assert_orders_once()
        with self.router._database(0).read_transaction() as connection:
            outcome = connection.execute("SELECT disposition,content FROM uta_command_batch_outcomes WHERE attempt_id=?", (attempt,)).fetchone()
        self.assertEqual(outcome[0], "RECOVERED")
        self.assertEqual([row["state"] for row in json.loads(outcome[1])["commands"]], ["PENDING"] * 3)

    def test_batch_size_requires_explicit_capability_and_default_layout_has_no_batch_schema(self):
        path = self.directory.parent / "default"
        default = DurableProcessRouter.initialize(path, 1, {"USD": 2}, managed=True)
        self.addCleanup(default.close)
        with default._database(0).read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT name FROM sqlite_master WHERE name LIKE 'uta_command_batch_%' OR name='writer_fence_batch_capability'").fetchall(), [])
        with self.assertRaises(ServiceError) as caught:
            DurableProcessRouter(path, financial_batch_size=3)
        self.assertEqual(caught.exception.code, "batch_capability_required")

    def test_size_zero_capable_binary_still_recovers_old_unresolved_manifest(self):
        # Offline original owner is this test process; no worker is running yet.
        from hashlib import sha256
        from uta.credit import CreditService
        from uta.service import ExchangeService
        from uta.writer_fence import WriterFence
        database = self.router._database(0)
        fence = WriterFence(database)
        token = fence.acquire("prepare-offline", 5)
        owned = database.for_writer(token)
        exchange = ExchangeService(owned, {"USD": 2}, max_price_age=timedelta(seconds=30), decision_audit=True)
        CreditService(exchange)
        queue = self.router._queue(0)
        for account in ("alice", "bob", "carol"):
            queue.enqueue_cancel(account, "cancel:" + account, "absent")
        batches = BatchStore(owned, queue, shard=0, layout_hash=sha256(self.router._control._descriptor.encode()).hexdigest())
        attempt = batches.prepare()
        fence.release(token)
        self.router.close()
        self.router = DurableProcessRouter(self.directory, financial_batch_size=0)
        self.addCleanup(self.router.close)
        self.router.start()
        def recovered():
            with database.read_transaction() as connection:
                return connection.execute("SELECT disposition FROM uta_command_batch_outcomes WHERE attempt_id=?", (attempt,)).fetchone()
        self.assertEqual(self.wait(recovered)[0], "RECOVERED")
        with database.read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT disposition FROM uta_command_batch_outcomes WHERE attempt_id=?", (attempt,)).fetchone()[0], "RECOVERED")
        for account in ("alice", "bob", "carol"):
            self.assertEqual(self.router.wait("cancel:" + account, account_id=account, timeout=3)["state"], "REJECTED")
