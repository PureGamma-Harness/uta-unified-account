"""Small real-spawn recovery cases, not throughput or shared-memory emulation."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import os
import fcntl
import signal
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic, sleep
import unittest
from unittest.mock import patch

from uta.durable_process import DurableProcessRouter
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ServiceError
from uta.sharding import ShardRouter, ShardWorkerView, _BoundShardDatabase
from uta.writer_fence import WriterFence, WriterFenceError


class DurableProcessTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "managed"
        def bootstrap(router):
            self.legacy = router
            self.names = [f"account-{index}" for index in range(40) if router.shard_for(f"account-{index}") == 0][:2]
            for account in self.names:
                router.create_account(account)
                router.deposit(account, "bootstrap", "USD", D("1000"))
        self.router = DurableProcessRouter.initialize(self.path, 2, {"USD": 8}, managed=True,
            bootstrap=bootstrap, lease_seconds=.6, poll_interval=.01, background_interval=.03)
        self.addCleanup(self.router.close)

    def market(self, version=1, mark="100"):
        return MarketSnapshot(version, datetime.now(timezone.utc), {"USD": AssetSpec(D(1), D(1))},
                              {"X": InstrumentSpec(D(mark), D(".1"), D(".05"))})

    def activate(self):
        self.router.start()
        publication = self.router.publish_market(self.market(), timeout=8)
        self.assertFalse(publication["publishing"])
        self.assertTrue(publication["halted"])
        self.assertFalse(self.router.set_kill_switch(False, timeout=8)["halted"])

    def eventually(self, predicate, timeout=8):
        deadline = monotonic() + timeout
        while monotonic() < deadline:
            result = predicate()
            if result:
                return result
            sleep(.02)
        self.fail("timed out waiting for a real worker/SQLite fact")

    def count_matches(self):
        with self.router._database(0).read_transaction() as connection:
            if connection.execute("SELECT 1 FROM sqlite_master WHERE name='uta_matches'").fetchone() is None:
                return 0
            return connection.execute("SELECT COUNT(*) FROM uta_matches").fetchone()[0]

    def submit(self, account, command, order, quantity):
        queued = self.router.submit_order(account, command, order, "X", D(quantity), D("100"))
        self.assertEqual((queued["ack"], queued["state"], queued["result"]), ("durably_queued", "PENDING", None))
        receipt = self.router.wait(command, account_id=account, timeout=8)
        self.assertEqual(receipt["state"], "SUCCEEDED", receipt)
        return receipt

    def test_real_independent_pids_match_then_new_owner_restarts_and_closes_positions(self):
        self.activate()
        pids = {self.router.worker_pid(0), self.router.worker_pid(1)}
        self.assertNotIn(os.getpid(), pids)
        self.assertNotIn(None, pids)
        self.assertEqual(len(pids), 2)
        buyer, seller = self.names
        first = self.submit(buyer, "buy-command", "buy", "1")
        self.submit(seller, "sell-command", "sell", "-1")
        self.eventually(lambda: self.count_matches() == 1)
        old_pid = self.router.worker_pid(0)
        old_generation = WriterFence(self.router._database(0)).status()["generation"]
        self.router.terminate_worker(0)
        self.eventually(lambda: self.router.worker_pid(0) not in (None, old_pid)
                        and WriterFence(self.router._database(0)).status()["generation"] > old_generation)
        retry = self.router.submit_order(buyer, "buy-command", "buy", "X", D(1), D(100))
        self.assertEqual(retry, first)  # Stored admission receipt is immutable.
        self.submit(buyer, "close-buyer", "close", "-1")
        self.submit(seller, "close-seller", "close", "1")
        self.eventually(lambda: self.count_matches() == 2)
        with self.router._database(0).read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_positions").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_events WHERE event_type='FILL_APPLIED'").fetchone()[0], 4)
            balances = list(connection.execute("SELECT units FROM ledger_balances WHERE asset='USD'"))
            self.assertEqual(sum(int(row[0]) for row in balances), 0)
            customer_units = [int(row[0]) for row in connection.execute("SELECT units FROM ledger_balances WHERE account LIKE 'customer:%' AND asset='USD'")]
            self.assertEqual(sum(customer_units), 199984000000)

    def test_pending_and_terminal_survive_parent_reopen_without_financial_initialization(self):
        self.activate()
        account = self.names[0]
        self.router.close()
        queued = self.router.submit_order(account, "pending", "resting", "X", D(1), D(100))
        self.assertEqual(queued["state"], "PENDING")
        with patch("uta.sharding.ExchangeService", side_effect=AssertionError("parent opened financial service")):
            restarted = DurableProcessRouter(self.path, lease_seconds=.6, poll_interval=.01)
        self.addCleanup(restarted.close)
        self.assertIsNone(restarted.status("unknown", account_id=account))
        self.assertEqual(restarted.status("pending", account_id=account), queued)
        restarted.start()
        receipt = restarted.wait("pending", account_id=account, timeout=8)
        self.assertEqual(receipt["state"], "SUCCEEDED")
        restarted.close()
        again = DurableProcessRouter(self.path)
        self.addCleanup(again.close)
        self.assertEqual(again.status("pending", account_id=account), receipt)
        self.assertIsNone(again.status("pending", account_id=self.names[1]))

    def test_partial_publication_is_closed_and_exact_pending_generation_resumes(self):
        lease = WriterFence(self.router._database(1))
        held = lease.acquire("test:hold", 5)
        self.addCleanup(lambda: self._release(lease, held))
        self.router.start()
        snapshot = self.market()
        publication = self.router.publish_market(snapshot, timeout=.25)
        self.assertTrue(publication["publishing"])
        self.assertTrue(publication["halted"])
        self.assertEqual(publication["watermarks"], {"0": 1})
        with self.assertRaises(ServiceError) as rejected:
            self.router.set_kill_switch(False, timeout=.1)
        self.assertEqual(rejected.exception.code, "publication_incomplete")
        command_ids = publication["durable_market_commands"]
        lease.release(held)
        resumed = self.router.publish_market(snapshot, timeout=8)
        self.assertEqual(resumed["durable_market_commands"], command_ids)
        self.assertFalse(resumed["publishing"])
        self.assertTrue(resumed["halted"])
        self.assertFalse(self.router.set_kill_switch(False, timeout=8)["halted"])

    @staticmethod
    def _release(fence, token):
        try:
            fence.release(token)
        except WriterFenceError:
            pass

    def test_managed_is_explicit_and_old_untokened_objects_cannot_write(self):
        with self.assertRaises(ServiceError) as error:
            DurableProcessRouter.initialize(Path(self.temporary.name) / "no-optin", 1, {"USD": 8})
        self.assertEqual(error.exception.code, "managed_opt_in_required")
        with self.assertRaises(ServiceError) as error:
            DurableProcessRouter.initialize(self.path, 2, {"USD": 8}, managed=True)
        self.assertEqual(error.exception.code, "managed_migration_required")
        with self.assertRaises(WriterFenceError):
            self.legacy.deposit(self.names[0], "stale", "USD", D(1))
        with self.assertRaises(WriterFenceError):
            ShardRouter(self.path, 2, {"USD": 8}, max_price_age=timedelta(seconds=30))
        self.assertEqual(WriterFence(self.router._database(0)).status()["generation"], 0)

    def test_guard_rejects_wrong_shard_inbox_and_persists_global_stop(self):
        self.activate()
        account = self.names[0]
        self.router._queue(1).enqueue_submit(account, "misrouted", "wrong", "X", D(1), D(100))
        self.eventually(lambda: self.router._control._state()["halted"])
        self.assertEqual(self.router._control._state()["error"], "shard_identity_conflict")
        for shard in (0, 1):
            with self.router._database(shard).read_transaction() as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_orders").fetchone()[0], 0)

    def test_controlled_worker_view_never_opens_another_managed_shard(self):
        fence = WriterFence(self.router._database(0))
        token = fence.acquire("test:single-view", 5)
        self.addCleanup(lambda: self._release(fence, token))
        original = _BoundShardDatabase._private_file
        indices = []
        def only_own(database):
            indices.append(database._index)
            self.assertEqual(database._index, 0)
            return original(database)
        with patch.object(_BoundShardDatabase, "_private_file", only_own):
            view = ShardWorkerView(self.path, 0, token, service_options={"max_price_age": self.legacy._services[0].max_price_age})
            self.assertEqual(view.shard, 0)
        self.assertTrue(indices)

    def test_expired_stopped_owner_holding_shared_gate_is_killed_and_publication_recovers(self):
        self.activate()
        pid = self.router.worker_pid(0)
        connection = sqlite3.connect(self.router._database(0).path, isolation_level=None)
        self.addCleanup(connection.close)
        connection.execute("BEGIN IMMEDIATE")
        def shared_gate_held():
            descriptor = os.open(self.path / "router.lock", os.O_RDWR)
            try:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    return True
                return False
            finally:
                os.close(descriptor)
        self.eventually(shared_gate_held)
        os.kill(pid, signal.SIGSTOP)
        connection.rollback()
        # No manual SIGCONT: supervisor must observe expiry and kill its own
        # stopped child so an EX publication gate can actually be acquired.
        before = monotonic()
        publication = self.router.publish_market(self.market(2), timeout=4)
        self.assertLess(monotonic() - before, 5)
        self.assertFalse(publication["publishing"])
        self.eventually(lambda: self.router.worker_pid(0) not in (None, pid))
        self.assertTrue(publication["halted"])

    def test_real_new_pid_repayments_use_same_fenced_credit_and_stable_receipts(self):
        path = Path(self.temporary.name) / "credit-managed"
        account = self.names[0]
        def bootstrap(router):
            router.create_account(account)
            router.deposit(account, "cash", "USD", D("1000"))
            router.publish_market(self.market())
            router.set_kill_switch(False)
            shard = router.shard_for(account)
            router.configure_credit_limit(account, "USD", D("100"))
            router.configure_credit_asset_limit(shard, "USD", D("100"))
            router.fund_credit_pool(shard, "pool", "USD", D("50"), source_reference="proof:pool")
            router.borrow(account, "loan", "USD", D("10"))
            router.accrue_interest(account, "interest", "USD", D("1"))
        router = DurableProcessRouter.initialize(path, 2, {"USD": 8}, managed=True,
                    bootstrap=bootstrap, lease_seconds=.6, poll_interval=.01)
        self.addCleanup(router.close)
        router.start()  # Global halt remains true; repayment needs no activation.
        queued = router.repay(account, "repay-4", "USD", D("4"))
        self.assertEqual(queued["state"], "PENDING")
        first = router.wait("repay-4", account_id=account, timeout=8)
        self.assertEqual(first["state"], "SUCCEEDED", first)
        self.assertEqual((first["result"]["principal_repaid"], first["result"]["interest_repaid"]), ("3", "1"))
        shard, old_pid = router.shard_for(account), router.worker_pid(router.shard_for(account))
        router.terminate_worker(shard)
        self.eventually(lambda: router.worker_pid(shard) not in (None, old_pid))
        self.assertEqual(router.repay(account, "repay-4", "USD", D("4")), first)
        router.repay(account, "repay-2", "USD", D("2"))
        second = router.wait("repay-2", account_id=account, timeout=8)
        self.assertEqual(second["state"], "SUCCEEDED", second)
        with router._database(shard).read_transaction() as conn:
            debt = conn.execute("SELECT principal,interest FROM uta_liabilities WHERE account_id=?", (account,)).fetchone()
            self.assertEqual(tuple(debt), ("5", "0"))
            balances = dict(conn.execute("SELECT account,units FROM ledger_balances WHERE asset='USD'"))
            self.assertEqual(int(balances["customer:" + account]), 100400000000)
            self.assertEqual(int(balances["system:credit-pool"]), 4500000000)
            self.assertEqual(int(balances["system:credit-interest-cash"]), 100000000)
            self.assertEqual(sum(map(int, balances.values())), 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM credit_commands WHERE kind='repaid'").fetchone()[0], 2)

    def test_explicit_existing_layout_takeover_preserves_orders_and_disables_old_writers(self):
        path = Path(self.temporary.name) / "existing"
        legacy = ShardRouter(path, 2, {"USD": 8}, max_price_age=timedelta(seconds=30))
        names = [f"legacy-{index}" for index in range(30) if legacy.shard_for(f"legacy-{index}") == 0][:2]
        for name in names:
            legacy.create_account(name)
            legacy.deposit(name, "fund", "USD", D("1000"))
        legacy.publish_market(self.market())
        legacy.set_kill_switch(False)
        legacy.submit_order(names[0], "resting-buy", "X", D("1"), D("100"))
        legacy.submit_order(names[1], "resting-sell", "X", D("-1"), D("100"))
        plan = DurableProcessRouter.inspect_takeover(path)
        self.assertTrue(all(not shard["managed"] for shard in plan["shards"]))
        self.assertEqual(sum(shard["orders"] for shard in plan["shards"]), 2)
        with self.assertRaises(ServiceError):
            DurableProcessRouter.take_over(path, managed=True, expected_layout_hash="0" * 64)
        managed = DurableProcessRouter.take_over(path, managed=True, expected_layout_hash=plan["layout_hash"],
                                                lease_seconds=.6, poll_interval=.01)
        self.addCleanup(managed.close)
        self.assertTrue(managed.diagnostics()["state"]["halted"])
        with self.assertRaises(WriterFenceError):
            legacy.deposit(names[0], "old-writer", "USD", D("1"))
        managed.start()
        self.assertFalse(managed.set_kill_switch(False, timeout=8)["halted"])
        def matched():
            with managed._database(0).read_transaction() as conn:
                return conn.execute("SELECT COUNT(*) FROM uta_matches").fetchone()[0] == 1
        self.eventually(matched)
        with managed._database(0).read_transaction() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM uta_orders").fetchone()[0], 2)
            self.assertEqual(sum(int(row[0]) for row in conn.execute("SELECT units FROM ledger_balances WHERE asset='USD'")), 0)
        with managed._control.control.read_transaction() as conn:
            stages = [row[0] for row in conn.execute("SELECT stage FROM router_durable_takeover_events ORDER BY sequence")]
            self.assertEqual(stages, ["PREPARED", "SHARD_FENCED", "SHARD_FENCED", "COMPLETED"])

    def test_incomplete_explicit_takeover_resumes_without_recreating_managed_history(self):
        path = Path(self.temporary.name) / "takeover-recovery"
        legacy = ShardRouter(path, 2, {"USD": 8}, max_price_age=timedelta(seconds=30))
        account = next(f"r-{index}" for index in range(20) if legacy.shard_for(f"r-{index}") == 0)
        legacy.create_account(account)
        legacy.deposit(account, "cash", "USD", D("10.04"))
        plan = DurableProcessRouter.inspect_takeover(path)
        original = WriterFence.enable
        def fail_second(fence, authority_id):
            if authority_id.endswith(":1"):
                raise OSError("injected take-over interruption")
            return original(fence, authority_id)
        with patch.object(WriterFence, "enable", fail_second):
            with self.assertRaisesRegex(OSError, "injected"):
                DurableProcessRouter.take_over(path, managed=True, expected_layout_hash=plan["layout_hash"])
        with self.assertRaises(ServiceError) as blocked:
            DurableProcessRouter(path)
        self.assertEqual(blocked.exception.code, "managed_bootstrap_incomplete")
        resumed = DurableProcessRouter.take_over(path, managed=True, expected_layout_hash=plan["layout_hash"])
        self.addCleanup(resumed.close)
        self.assertTrue(resumed.diagnostics()["state"]["halted"])
        with resumed._database(0).read_transaction() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM uta_deposits").fetchone()[0], 1)
            self.assertEqual(int(conn.execute("SELECT units FROM ledger_balances WHERE account=? AND asset='USD'", ("customer:" + account,)).fetchone()[0]), 1004000000)


if __name__ == "__main__":
    unittest.main()
