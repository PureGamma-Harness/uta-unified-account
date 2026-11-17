"""Small real-spawn recovery cases, not throughput or shared-memory emulation."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from contextlib import contextmanager
import ctypes
import os
import fcntl
import signal
import sqlite3
import multiprocessing
from multiprocessing import resource_tracker
import select
from pathlib import Path
from tempfile import TemporaryDirectory
from time import CLOCK_BOOTTIME, clock_gettime_ns, monotonic, sleep
import unittest
from unittest.mock import patch

from uta.durable_process import DurableProcessRouter
from uta import durable_process
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ServiceError
from uta.sharding import ShardRouter, ShardWorkerView, _BoundShardDatabase
from uta.writer_fence import WriterFence, WriterFenceError
from uta.service import ExchangeService


_REAL_RUN_WORKER = durable_process._run_worker


def _orphan_worker(*args):
    """Test-only spawn entry; initialization, fencing and commands stay real."""
    directory, shard = args[:2]
    original = ShardWorkerView.process_one

    def stop_when_armed(view, store):
        if (Path(directory) / f"test-orphan-arm-{shard}").exists():
            if shard == 0:
                # The stopped process itself owns the actual router SH flock.
                with view._control._lock():
                    (Path(directory) / "test-orphan-sh-held").touch()
                    os.kill(os.getpid(), signal.SIGSTOP)
            else:
                # Between real process_one calls: no router/SQLite lock held.
                os.kill(os.getpid(), signal.SIGSTOP)
        return original(view, store)

    with patch.object(ShardWorkerView, "process_one", stop_when_armed):
        _REAL_RUN_WORKER(*args)


def _wait_orphan_fact(predicate, timeout=3):
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        result = predicate()
        if result:
            return result
        sleep(.01)
    raise AssertionError("orphan fixture did not reach its confirmed safe point")


def _same_birth(left, right):
    return all(left[key] == right[key] for key in ("pid", "start_ticks", "boot_id"))


def _pin_birth(identity):
    """Anchor signals before checking /proc again; never signal a bare old PID."""
    pidfd = os.pidfd_open(identity["pid"])
    try:
        current = durable_process._process_identity(identity["pid"])
        if not _same_birth(current, identity) or current["uid"] != os.geteuid():
            raise AssertionError("orphan fixture birth identity changed")
        return pidfd
    except BaseException:
        os.close(pidfd)
        raise


@contextmanager
def _orphan_reaper():
    """Reap killed grandchildren in this test instead of leaving them to PID 1."""
    # Keep multiprocessing's long-lived infrastructure outside this scope.
    resource_tracker.ensure_running()
    libc = ctypes.CDLL(None, use_errno=True)
    previous = ctypes.c_int()
    if libc.prctl(37, ctypes.byref(previous), 0, 0, 0) or libc.prctl(36, 1, 0, 0, 0):
        raise OSError(ctypes.get_errno(), "cannot establish test orphan subreaper")
    def children():
        result = []
        for entry in Path("/proc").iterdir():
            if entry.name.isdigit():
                try:
                    tail = (entry / "stat").read_text().rsplit(")", 1)[1].split()
                    if int(tail[1]) == os.getpid():
                        result.append(durable_process._process_identity(int(entry.name)))
                except (ProcessLookupError, FileNotFoundError):
                    pass  # A concurrently exiting process is not an owned child.
        return result

    baseline = None
    adopted = []
    try:
        baseline = {(row["pid"], row["start_ticks"], row["boot_id"]) for row in children()}
        yield adopted
    finally:
        try:
            # Include newly adopted children even if their coordinator died in
            # the process.start -> SPAWNED registration interval. Never reap a
            # pre-existing child or use waitpid(-1) across other test handles.
            deadline = monotonic() + 5
            while baseline is not None:
                remaining = [row for row in children()
                             if (row["pid"], row["start_ticks"], row["boot_id"]) not in baseline]
                if not remaining:
                    break
                if monotonic() >= deadline:
                    raise AssertionError("orphan fixture left an unreaped descendant")
                for identity in remaining:
                    pidfd = _pin_birth(identity)
                    try:
                        exited = select.poll()
                        exited.register(pidfd, select.POLLIN)
                        if not exited.poll(0):
                            signal.pidfd_send_signal(pidfd, signal.SIGKILL)
                        if not exited.poll(1000):
                            raise AssertionError("orphan fixture descendant did not exit")
                        os.waitpid(identity["pid"], os.WNOHANG)
                    finally:
                        os.close(pidfd)
        finally:
            if libc.prctl(36, previous.value, 0, 0, 0):
                raise OSError(ctypes.get_errno(), "cannot restore test subreaper")


def _orphan_coordinator(directory, buyer, report):
    """Report only current registered workers already in intended stopped states."""
    router = DurableProcessRouter(directory, lease_seconds=.6, poll_interval=.01)
    try:
        with patch.object(durable_process, "_run_worker", _orphan_worker):
            router.start()
            snapshot = MarketSnapshot(1, datetime.now(timezone.utc), {"USD": AssetSpec(D(1), D(1))},
                                      {"X": InstrumentSpec(D(100), D(".1"), D(".05"))})
            router.publish_market(snapshot, timeout=8)
            router.set_kill_switch(False, timeout=8)
            router.submit_order(buyer, "orphan-original", "resting", "X", D(1), D(100))
            receipt = router.wait("orphan-original", account_id=buyer, timeout=8)
            # The real supervisor must not expire/replace our deliberately
            # stopped children while the fixture is preparing the crash.
            with router._mutex:
                workers = [router._workers[shard][0] for shard in range(2)]
                identities = [durable_process._process_identity(worker.pid) for worker in workers]
                (Path(directory) / "test-orphan-arm-1").touch()
                _wait_orphan_fact(lambda: durable_process._process_identity(workers[1].pid)["state"] == "T")
                with router._control._lock(exclusive=True, timeout=3):
                    # EX success also proves stopped shard 1 holds no SH gate.
                    (Path(directory) / "test-orphan-arm-0").touch()
                _wait_orphan_fact(lambda: durable_process._process_identity(workers[0].pid)["state"] == "T")
                if not (Path(directory) / "test-orphan-sh-held").exists():
                    raise AssertionError("shard zero did not enter the real shared gate")
                with router._control.control.read_transaction() as connection:
                    registered = []
                    for shard, identity in enumerate(identities):
                        spawned = dict(connection.execute("SELECT * FROM router_process_owners WHERE kind='SPAWNED' AND shard=? ORDER BY sequence DESC LIMIT 1", (shard,)).fetchone())
                        owned = dict(connection.execute("SELECT * FROM router_process_owners WHERE kind='OWNED' AND shard=? ORDER BY sequence DESC LIMIT 1", (shard,)).fetchone())
                        lease = WriterFence(router._database(shard)).status()
                        if (not _same_birth(spawned, identity) or not _same_birth(owned, identity)
                                or spawned["nonce"] != owned["nonce"] or owned["coordinator"] != router._coordinator
                                or spawned["coordinator"] != owned["coordinator"]
                                or (owned["generation"], owned["nonce"], owned["pid"], owned["authority_id"]) !=
                                   (lease["generation"], lease["owner_nonce"], lease["owner_pid"], lease["authority_id"])
                                or not workers[shard].is_alive()):
                            raise AssertionError("stopped worker is not the current registered owner")
                        registered.append(owned)
                report.send({"parent": os.getpid(), "workers": registered, "receipt": receipt})
                report.recv()  # Mutex stays held until deliberate parent death or cleanup.
    except BaseException as exc:
        report.send({"error": repr(exc)})
        raise
    finally:
        router.close()
        report.close()


def _cleanup_orphan_fixture(coordinator, report, control, adopted, pinned):
    if coordinator.is_alive():
        try:
            report.send("close")
        except (BrokenPipeError, EOFError, OSError):
            pass
        coordinator.join(timeout=8)
        if coordinator.is_alive():
            coordinator.kill()  # Still our own unreaped Process handle.
    coordinator.join(timeout=3)
    # This also covers timeout/failure before the coordinator's ready report.
    try:
        with control.control.read_transaction() as connection:
            exists = connection.execute("SELECT 1 FROM sqlite_master WHERE name='router_process_owners'").fetchone()
            records = [] if exists is None else [dict(row) for row in connection.execute("SELECT * FROM router_process_owners WHERE kind='SPAWNED'")]
        for identity in records:
            key = (identity["pid"], identity["start_ticks"], identity["boot_id"])
            if key not in pinned:
                try:
                    current = durable_process._process_identity(identity["pid"])
                    if not _same_birth(current, identity):
                        continue
                    pinned[key] = _pin_birth(identity)
                except (ProcessLookupError, FileNotFoundError):
                    continue  # Cleanup only; absence never counts as recovery.
            if not any(_same_birth(identity, old) for old in adopted):
                adopted.append(identity)
            pidfd = pinned[key]
            exited = select.poll()
            exited.register(pidfd, select.POLLIN)
            if not exited.poll(0):
                signal.pidfd_send_signal(pidfd, signal.SIGKILL)
            if not exited.poll(3000):
                raise AssertionError("fixture worker did not exit during cleanup")
    finally:
        for pidfd in pinned.values():
            os.close(pidfd)
        report.close()


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
        if receipt is None:
            self.fail(repr({"command": command, "diagnostics": self.router.diagnostics()}))
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
        command_ids = publication["durable_market_commands"]
        def partial_progress():
            # Keep shard 1 fenced while observing actual shard 0 progress; a
            # short response deadline does not guarantee worker startup speed.
            lease.renew(held, 5)
            observed = self.router.publish_market(snapshot, timeout=.25)
            self.assertTrue(observed["publishing"], observed)
            self.assertTrue(observed["halted"], observed)
            self.assertNotIn("1", observed["watermarks"], observed)
            self.assertEqual(observed["durable_market_commands"], command_ids)
            return observed if observed["watermarks"] == {"0": 1} else None
        if publication["watermarks"] != {"0": 1}:
            publication = self.eventually(partial_progress)
        self.assertEqual(publication["watermarks"], {"0": 1})
        with self.assertRaises(ServiceError) as rejected:
            self.router.set_kill_switch(False, timeout=.1)
        self.assertEqual(rejected.exception.code, "publication_incomplete")
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
            view = ShardWorkerView(self.path, 0, token, service_options={"max_price_age": self.legacy._services[0].max_price_age,
                                                                         "decision_audit": True})
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
            self.assertEqual(conn.execute("SELECT legacy_order_count FROM uta_audit_capability WHERE singleton=1").fetchone()[0], 2)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM uta_risk_decisions WHERE kind='ORDER_ACCEPTED'").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM uta_risk_decisions WHERE kind='FILL_CONFIRMED'").fetchone()[0], 2)
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

    def test_new_parent_uses_registered_birth_identity_to_recover_sigstopped_orphans(self):
        self._assert_registered_orphan_recovery(expire_before_crash=True)

    def test_new_parent_waits_for_unexpired_registered_orphans_before_pidfd_kill(self):
        self._assert_registered_orphan_recovery(expire_before_crash=False)

    def _assert_registered_orphan_recovery(self, *, expire_before_crash):
        context = multiprocessing.get_context("spawn")
        receive, send = context.Pipe()
        coordinator = context.Process(target=_orphan_coordinator, args=(str(self.path), self.names[0], send))
        pinned = {}
        with _orphan_reaper() as adopted:
            coordinator.start()
            send.close()
            recovered = None
            try:
                self.assertTrue(receive.poll(8), "coordinator did not confirm stopped registered workers")
                prior = receive.recv()
                self.assertNotIn("error", prior, prior)
                self.assertEqual(prior["receipt"]["state"], "SUCCEEDED")
                self.assertEqual(len(prior["workers"]), 2)
                self.assertEqual(len({owner["pid"] for owner in prior["workers"]}), 2)
                for owner in prior["workers"]:
                    identity = durable_process._process_identity(owner["pid"])
                    self.assertTrue(_same_birth(identity, owner))
                    self.assertEqual(identity["state"], "T")
                    key = (owner["pid"], owner["start_ticks"], owner["boot_id"])
                    pinned[key] = _pin_birth(owner)
                    adopted.append(owner)
                # Observe actual SH: SH is compatible, while EX must be blocked.
                with self.router._control._lock(timeout=.1):
                    pass
                with self.assertRaises(ServiceError) as held:
                    with self.router._control._lock(exclusive=True, timeout=.1):
                        self.fail("stopped shard zero did not retain the shared router gate")
                self.assertEqual(held.exception.code, "router_busy")
                if expire_before_crash:
                    # Cross the unchanged .6s TTL while the coordinator owns
                    # its monitor mutex; neither stopped child may be replaced.
                    self.eventually(lambda: all(not WriterFence(self.router._database(shard)).status()["active"]
                                                for shard in range(2)))
                for owner in prior["workers"]:
                    identity = durable_process._process_identity(owner["pid"])
                    self.assertTrue(_same_birth(identity, owner))
                    self.assertEqual(identity["state"], "T")
                coordinator.kill()
                coordinator.join(timeout=3)
                self.assertEqual(coordinator.exitcode, -signal.SIGKILL)
                # Both exact old owners really remain alive/stopped as orphans.
                for owner in prior["workers"]:
                    self.assertEqual(durable_process._process_identity(owner["pid"])["state"], "T")
                recovered = DurableProcessRouter(self.path, lease_seconds=.6, poll_interval=.01)
                before = [WriterFence(recovered._database(shard)).status() for shard in range(2)]
                if not expire_before_crash:
                    self.assertTrue(any(lease["active"] for lease in before),
                                    "fixture did not reach recovery with a still-active old owner")
                actual_signal = signal.pidfd_send_signal
                killed_at = []
                def kill_after_persisted_expiry(pidfd, sig, *args):
                    info = dict(line.split(":", 1) for line in Path(f"/proc/self/fdinfo/{pidfd}").read_text().splitlines())
                    pid = int(info["Pid"])
                    owner = next(row for row in prior["workers"] if row["pid"] == pid)
                    lease = WriterFence(recovered._database(owner["shard"])).status()
                    self.assertEqual((lease["owner_pid"], lease["owner_nonce"], lease["generation"]),
                                     (owner["pid"], owner["nonce"], owner["generation"]))
                    now = clock_gettime_ns(CLOCK_BOOTTIME)
                    self.assertEqual(sig, signal.SIGKILL)
                    self.assertGreaterEqual(now, lease["expires_ns"])
                    killed_at.append((pid, now, lease["expires_ns"]))
                    return actual_signal(pidfd, sig, *args)
                with patch.object(signal, "pidfd_send_signal", kill_after_persisted_expiry):
                    recovered.start(recovery_timeout=4)
                self.assertEqual({row[0] for row in killed_at}, {row["pid"] for row in prior["workers"]})
                self.assertEqual(len(killed_at), 2)
                if not expire_before_crash:
                    print("orphan-recovery-expiry-evidence", {"active_at_start": [lease["active"] for lease in before],
                          "pid_boottime_ns_expires_ns": killed_at}, flush=True)
                publication = recovered.publish_market(self.market(2), timeout=8)
                self.assertFalse(publication["publishing"])
                self.assertEqual(publication["watermarks"], {"0": 2, "1": 2})
                self.assertFalse(recovered.set_kill_switch(False, timeout=8)["halted"])
                orphans = recovered.diagnostics()["recovered_orphans"]
                self.assertEqual({(row["pid"], row["start_ticks"]) for row in orphans},
                                 {(owner["pid"], owner["start_ticks"]) for owner in prior["workers"]})
                self.assertEqual(len(orphans), 2)
                for owner in prior["workers"]:
                    current = WriterFence(recovered._database(owner["shard"])).status()
                    self.assertGreater(current["generation"], owner["generation"])
                    self.assertNotEqual(current["owner_pid"], owner["pid"])
                    self.assertNotEqual(current["owner_nonce"], owner["nonce"])
                    poller = select.poll()
                    poller.register(pinned[(owner["pid"], owner["start_ticks"], owner["boot_id"])], select.POLLIN)
                    self.assertTrue(poller.poll(0), "claimed orphan recovery must mean the exact old process exited")
                self.assertEqual(recovered.status("orphan-original", account_id=self.names[0]), prior["receipt"])
                recovered.submit_order(self.names[1], "orphan-counterparty", "sell", "X", D(-1), D(100))
                self.assertEqual(recovered.wait("orphan-counterparty", account_id=self.names[1], timeout=8)["state"], "SUCCEEDED")
                def has_trade():
                    with recovered._database(0).read_transaction() as conn:
                        return conn.execute("SELECT COUNT(*) FROM uta_matches").fetchone()[0] == 1
                self.eventually(has_trade)
                with recovered._database(0).read_transaction() as conn:
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM uta_fills").fetchone()[0], 2)
                    self.assertEqual(conn.execute("SELECT COUNT(*) FROM uta_events WHERE event_type='FILL_APPLIED'").fetchone()[0], 2)
                    self.assertEqual(sum(int(row[0]) for row in conn.execute("SELECT units FROM ledger_balances WHERE asset='USD'")), 0)
                    self.assertEqual(sum(int(row[0]) for row in conn.execute("SELECT units FROM ledger_balances WHERE account LIKE 'customer:%' AND asset='USD'")), 199992000000)
                with recovered._control.control.read_transaction() as conn:
                    killed = list(conn.execute("SELECT * FROM router_process_owners WHERE kind='ORPHAN_KILLED'"))
                    self.assertEqual(len(killed), 2)
                    self.assertEqual({(row["pid"], row["start_ticks"], row["boot_id"]) for row in killed}, set(pinned))
                    self.assertTrue(all(row["coordinator"] != prior["workers"][0]["coordinator"] for row in killed))
            finally:
                try:
                    if recovered is not None:
                        recovered.close()
                finally:
                    _cleanup_orphan_fixture(coordinator, receive, self.router._control, adopted, pinned)

    def test_fresh_required_audit_is_persisted_and_explicit_false_is_development_only(self):
        self.assertTrue(self.router.decision_audit_required)
        for shard in (0, 1):
            with self.router._database(shard).read_transaction() as conn:
                self.assertEqual(conn.execute("SELECT version FROM uta_schema").fetchone()[0], 3)
                self.assertEqual(conn.execute("SELECT legacy_order_count FROM uta_audit_capability").fetchone()[0], 0)
        legacy = DurableProcessRouter.initialize(Path(self.temporary.name) / "development", 1, {"USD": 8},
                                                  managed=True, decision_audit=False)
        self.addCleanup(legacy.close)
        self.assertFalse(legacy.decision_audit_required)
        self.assertEqual(legacy.diagnostics()["profile"], "managed_development_legacy_gap")
        with legacy._database(0).read_transaction() as conn:
            self.assertEqual(conn.execute("SELECT version FROM uta_schema").fetchone()[0], 2)

    def test_offline_audit_upgrade_preserves_config_legacy_gaps_and_monies_then_audits_new_fills(self):
        path = Path(self.temporary.name) / "audit-promotion"
        buyer, seller = self.names
        def bootstrap(router):
            for account in (buyer, seller):
                router.create_account(account)
                router.deposit(account, "seed", "USD", D("1000"))
            router.publish_market(self.market())
            router.set_kill_switch(False)
            router.submit_order(buyer, "legacy-buy", "X", D(1), D(100))
        legacy = DurableProcessRouter.initialize(path, 2, {"USD": 8}, managed=True,
                        bootstrap=bootstrap, decision_audit=False, lease_seconds=.6, poll_interval=.01)
        self.addCleanup(legacy.close)
        with legacy._control.control.read_transaction() as conn:
            original_config = conn.execute("SELECT payload FROM router_durable_config").fetchone()[0]
        with legacy._database(0).read_transaction() as conn:
            original_head = tuple(conn.execute("SELECT sequence,event_hash FROM ledger_events ORDER BY sequence DESC LIMIT 1").fetchone())
        plan = DurableProcessRouter.plan_decision_audit_upgrade(path)
        self.assertEqual({row["trading_schema"] for row in plan["shards"]}, {2})
        upgraded = DurableProcessRouter.upgrade_decision_audit(path, managed=True,
                    expected_layout_hash=plan["layout_hash"], lease_seconds=.6, poll_interval=.01)
        self.addCleanup(upgraded.close)
        self.assertTrue(upgraded.decision_audit_required)
        with upgraded._control.control.read_transaction() as conn:
            self.assertEqual(conn.execute("SELECT payload FROM router_durable_config").fetchone()[0], original_config)
            self.assertEqual(conn.execute("SELECT state FROM router_decision_audit_capability").fetchone()[0], "READY")
        with upgraded._database(0).read_transaction() as conn:
            self.assertEqual(tuple(conn.execute("SELECT sequence,event_hash FROM ledger_events ORDER BY sequence DESC LIMIT 1").fetchone()), original_head)
            self.assertEqual(conn.execute("SELECT legacy_order_count FROM uta_audit_capability").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM uta_risk_decisions").fetchone()[0], 0)
        with self.assertRaises(ServiceError) as stale:
            legacy.start()
        self.assertEqual(stale.exception.code, "configuration_refresh_required")
        upgraded.start()
        self.assertFalse(upgraded.set_kill_switch(False, timeout=8)["halted"])
        upgraded.submit_order(seller, "new-sell", "sell", "X", D(-1), D(100))
        self.assertEqual(upgraded.wait("new-sell", account_id=seller, timeout=8)["state"], "SUCCEEDED")
        def matched():
            with upgraded._database(0).read_transaction() as conn:
                return conn.execute("SELECT COUNT(*) FROM uta_matches").fetchone()[0] == 1
        self.eventually(matched)
        with upgraded._database(0).read_transaction() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM uta_risk_decisions WHERE kind='ORDER_ACCEPTED'").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM uta_fills WHERE execution_decision_id IS NOT NULL").fetchone()[0], 2)
            self.assertEqual(sum(int(row[0]) for row in conn.execute("SELECT units FROM ledger_balances WHERE asset='USD'")), 0)

    def test_partial_audit_upgrade_blocks_start_and_resumes_without_fake_backfill(self):
        path = Path(self.temporary.name) / "audit-partial"
        legacy = DurableProcessRouter.initialize(path, 2, {"USD": 8}, managed=True, decision_audit=False)
        self.addCleanup(legacy.close)
        plan = DurableProcessRouter.plan_decision_audit_upgrade(path)
        original = ExchangeService
        def interrupted(database, scales, **options):
            if database._index == 1:
                raise OSError("injected audit promotion stop")
            return original(database, scales, **options)
        with patch("uta.service.ExchangeService", side_effect=interrupted):
            with self.assertRaisesRegex(OSError, "injected"):
                DurableProcessRouter.upgrade_decision_audit(path, managed=True, expected_layout_hash=plan["layout_hash"])
        with self.assertRaises(ServiceError) as error:
            DurableProcessRouter(path)
        self.assertEqual(error.exception.code, "decision_audit_upgrade_incomplete")
        with self.assertRaises(ServiceError) as error:
            legacy.start()
        self.assertEqual(error.exception.code, "decision_audit_upgrade_incomplete")
        upgraded = DurableProcessRouter.upgrade_decision_audit(path, managed=True, expected_layout_hash=plan["layout_hash"])
        self.addCleanup(upgraded.close)
        self.assertTrue(upgraded.decision_audit_required)
        again = DurableProcessRouter.upgrade_decision_audit(path, managed=True, expected_layout_hash=plan["layout_hash"])
        self.addCleanup(again.close)
        self.assertTrue(again.diagnostics()["state"]["halted"])

    def test_first_wave_config_without_flag_requires_explicit_promotion_and_remains_byte_exact(self):
        path = Path(self.temporary.name) / "old-config-shape"
        original_prepare = durable_process._prepare_config
        def first_wave_manifest(connection, config):
            old = {**config, "service": dict(config["service"])}
            old["service"].pop("decision_audit")
            original_prepare(connection, old)
        # Reproduce the first wave's persisted configuration shape. This is a
        # schema fixture, separate from the real archived-binary fence tests.
        with patch.object(durable_process, "_prepare_config", first_wave_manifest):
            old = DurableProcessRouter.initialize(path, 1, {"USD": 8}, managed=True, decision_audit=False)
        self.addCleanup(old.close)
        with old._control.control.read_transaction() as conn:
            before = conn.execute("SELECT payload FROM router_durable_config").fetchone()[0]
        with self.assertRaises(ServiceError) as denied:
            old.start()
        self.assertEqual(denied.exception.code, "decision_audit_upgrade_required")
        plan = DurableProcessRouter.plan_decision_audit_upgrade(path)
        required = DurableProcessRouter.upgrade_decision_audit(path, managed=True, expected_layout_hash=plan["layout_hash"])
        self.addCleanup(required.close)
        self.assertTrue(required.decision_audit_required)
        with required._control.control.read_transaction() as conn:
            self.assertEqual(conn.execute("SELECT payload FROM router_durable_config").fetchone()[0], before)

    def test_audit_upgrade_stops_globally_but_never_promotes_with_a_live_coordinator(self):
        path = Path(self.temporary.name) / "live-upgrade"
        legacy = DurableProcessRouter.initialize(path, 1, {"USD": 8}, managed=True,
                            decision_audit=False, lease_seconds=.6, poll_interval=.01)
        self.addCleanup(legacy.close)
        legacy.start()
        legacy.publish_market(self.market(), timeout=8)
        legacy.set_kill_switch(False, timeout=8)
        plan = DurableProcessRouter.plan_decision_audit_upgrade(path)
        with self.assertRaises(ServiceError) as denied:
            DurableProcessRouter.upgrade_decision_audit(path, managed=True, expected_layout_hash=plan["layout_hash"])
        self.assertEqual(denied.exception.code, "supervisor_busy")
        self.assertTrue(legacy.diagnostics()["state"]["halted"])
        with legacy._database(0).read_transaction() as conn:
            self.assertEqual(conn.execute("SELECT version FROM uta_schema").fetchone()[0], 2)

    def test_required_control_does_not_silently_upgrade_a_restored_pre_promotion_snapshot(self):
        path = Path(self.temporary.name) / "audit-restore"
        legacy = DurableProcessRouter.initialize(path, 1, {"USD": 8}, managed=True, decision_audit=False)
        self.addCleanup(legacy.close)
        backup = Path(self.temporary.name) / "old-shard.sqlite3"
        descriptor = os.open(backup, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
        os.close(descriptor)
        with legacy._database(0).read_transaction() as source:
            target = sqlite3.connect(backup)
            try:
                source.backup(target)
            finally:
                target.close()
        plan = DurableProcessRouter.plan_decision_audit_upgrade(path)
        required = DurableProcessRouter.upgrade_decision_audit(path, managed=True, expected_layout_hash=plan["layout_hash"])
        self.addCleanup(required.close)
        # This deliberately restores an old snapshot at its original path;
        # canonical-path binding alone cannot detect this version mismatch.
        os.replace(backup, legacy._database(0).path)
        with self.assertRaises(ServiceError) as denied:
            DurableProcessRouter(path)
        self.assertEqual(denied.exception.code, "decision_audit_capability_mismatch")
        raw = sqlite3.connect(legacy._database(0).path)
        try:
            self.assertEqual(raw.execute("SELECT version FROM uta_schema").fetchone()[0], 2)
        finally:
            raw.close()


if __name__ == "__main__":
    unittest.main()
