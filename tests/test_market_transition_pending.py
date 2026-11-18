"""Bounded protocol contracts; SQL cases use one local owner, never workers.

No test has been run as part of this candidate's CODE freeze. The SQL class
requires a separate scope allowing fresh control/financial SQLite, native
fencing identity, and a real but unstarted DurableProcessRouter. Its fake
receipt waiter drives the real single-owner command executor synchronously.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from hashlib import sha256
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uta.durable_batches import BatchStore
from uta.durable_commands import CommandExecutionError, QueueStore
from uta.durable_process import DurableProcessRouter, _options
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ServiceError
from uta.sharding import ShardRouter, ShardWorkerView, _market_transition_pending
from uta.storage import Database
from uta.writer_fence import WriterFence, WriterFenceError


class MarketTransitionStateContracts(unittest.TestCase):
    def test_missing_marker_is_legacy_false_and_invalid_marker_is_rejected(self):
        self.assertFalse(_market_transition_pending({"halted": True, "publishing": True}))
        for value in (None, 0, 1, "true", [], {}):
            with self.subTest(value=value), self.assertRaises(ServiceError) as caught:
                _market_transition_pending({"halted": True, "market_transition_pending": value})
            self.assertEqual(caught.exception.code, "control_corruption")
            with self.assertRaises(ValueError):
                QueueStore.process_one(None, None, allow_submit=value)
        for state in ({"halted": False}, {"halted": True, "error": "market_barrier_mismatch"}):
            with self.subTest(state=state), self.assertRaises(ServiceError):
                _market_transition_pending({**state, "market_transition_pending": True})

    def test_all_control_writes_clear_activation_and_unrelated_stops(self):
        saved = []
        class Connection:
            def execute(self, sql, parameters):
                saved.append(json.loads(parameters[0]))
        @contextmanager
        def transaction():
            yield Connection()
        owner = SimpleNamespace(control=SimpleNamespace(transaction=transaction))
        cases = [(True, None, True), (True, "market_fanout_incomplete", True),
                 (True, "halt_fanout_incomplete", True), (False, None, False)]
        cases += [(True, error, False) for error in (
            "market_barrier_mismatch", "missing_shard", "shard_initialization_failed",
            "managed_bootstrap_incomplete", "takeover_in_progress", "takeover_incomplete",
            "decision_audit_upgrade_requested", "decision_audit_upgrade_incomplete",
            "managed_shard_unavailable", "funding_registry_conflict", "unknown_stop")]
        for halted, error, expected in cases:
            state = {"halted": halted, "error": error, "market_transition_pending": True}
            ShardRouter._write_state(owner, state)
            self.assertIs(saved[-1]["market_transition_pending"], expected)
            self.assertIs(state["market_transition_pending"], expected)
        for value in (None, 0, 1, "true"):
            count = len(saved)
            with self.assertRaises(ServiceError):
                ShardRouter._write_state(owner, {"halted": True, "market_transition_pending": value})
            self.assertEqual(len(saved), count)


class MarketTransitionPendingSQLContracts(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name) / "managed"
        self.version = 1
        def bootstrap(router):
            for account in ("alice", "bob", "carol"):
                router.create_account(account)
                router.deposit(account, "fund", "USD", D(1000))
            router.publish_market(self.market(1))
            router.set_kill_switch(False)
            router.fund_credit_pool(0, "pool", "USD", D(30),
                                    source_reference="synthetic-market-transition-pool")
            router.configure_credit_asset_limit(0, "USD", D(30))
            for account in ("bob", "carol"):
                router.configure_credit_limit(account, "USD", D(1))
                router.borrow(account, "loan", "USD", D(1))
            router.submit_order("bob", "resting", "BTC-PERP", D(1), D(100))
        self.router = DurableProcessRouter.initialize(self.directory, 1, {"USD": 2},
            managed=True, durable_batches=True, financial_batch_size=0,
            max_price_age=timedelta(seconds=5), bootstrap=bootstrap)
        self.addCleanup(self.router.close)
        self.fence = WriterFence(self.router._database(0))
        self.token = self.fence.acquire("market-transition-test-owner", 60)
        self.addCleanup(self.release)
        self.view = ShardWorkerView(self.directory, 0, self.token,
                                   service_options=_options(self.router._config["service"]))
        self.queue = self.router._queue(0)
        self.batches = BatchStore(self.view.database, self.queue, shard=0,
            layout_hash=sha256(self.router._control._descriptor.encode()).hexdigest())
        # No parent thread, OS child, or worker lifecycle is started. This
        # waiter has a fixed step count; it executes actual SQL/guards/COMMIT.
        waiter = patch.object(self.router, "_receipts", side_effect=self.receipts)
        waiter.start()
        self.addCleanup(waiter.stop)
        self.assertFalse(self.router.set_kill_switch(False)["halted"])

    def release(self):
        try:
            self.fence.release(self.token)
        except WriterFenceError as error:
            if error.code != "writer_fenced":
                raise

    @staticmethod
    def market(version):
        return MarketSnapshot(version, datetime.now(timezone.utc),
            {"USD": AssetSpec(D(1), D(1))},
            {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))})

    def receipts(self, commands, timeout):
        for _ in range(32):
            result = {index: self.queue.status(command) for index, command in commands.items()}
            if all(row is not None and row["state"] in ("SUCCEEDED", "REJECTED", "QUARANTINED")
                   for row in result.values()):
                return result
            if self.view.process_one(self.queue) is None:
                return result
        self.fail("fixed control step budget exhausted")

    def submit(self, command="pending", account="alice", order="new-order", quantity=D(1)):
        return self.router.submit_order(account, command, order, "BTC-PERP", quantity, D(100))

    def row(self, command="pending"):
        with self.router._database(0).read_transaction() as connection:
            value = connection.execute("SELECT * FROM uta_command_inbox WHERE command_id=?", (command,)).fetchone()
            return dict(value)

    def pause(self):
        self.version += 1
        snapshot = self.market(self.version)
        with patch.object(self.router, "_receipts", return_value={"0": None}):
            publication = self.router.publish_market(snapshot, timeout=0)
        self.assertTrue(publication["publishing"])
        self.assertTrue(publication["market_transition_pending"])
        return snapshot, publication

    def finish_publication(self, snapshot):
        publication = self.router.publish_market(snapshot)
        self.assertFalse(publication["publishing"])
        self.assertTrue(publication["halted"])
        self.assertTrue(publication["market_transition_pending"])
        return publication

    def test_fanout_and_activation_gap_keep_original_row_then_commit_once_and_reopen(self):
        original = self.submit()
        before = self.row()
        snapshot, publication = self.pause()
        # Apply the exact queued publication; its global watermark is still
        # incomplete until the parent repeats the original generation.
        self.assertEqual(self.view.process_one(self.queue)["kind"], "PUBLISH_MARKET")
        for _ in range(32):
            self.assertIsNone(self.view.process_one(self.queue))
        self.assertEqual(self.row(), before)
        resumed = self.finish_publication(snapshot)
        self.assertEqual(resumed["durable_market_commands"], publication["durable_market_commands"])
        for _ in range(8):
            self.assertIsNone(self.view.process_one(self.queue))
        self.assertEqual(self.row(), before)
        self.assertEqual(self.submit(), original)
        self.assertFalse(self.router.set_kill_switch(False)["market_transition_pending"])
        result = self.view.process_one(self.queue)
        self.assertEqual((result["command_id"], result["state"], result["attempts"]), ("pending", "SUCCEEDED", 0))
        self.assertEqual(result["result"]["reserved_margin"], "10.04")
        self.assertEqual(self.submit(), result)
        fresh = Database(self.router._database(0).path)
        self.assertEqual(QueueStore(fresh).status("pending"), result)
        with fresh.read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_orders WHERE account_id='alice'").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_events WHERE event_type='ORDER_ACCEPTED' AND account_id='alice'").fetchone()[0], 1)
            self.assertGreater(self.view._exchange.ledger.verify(connection=connection), 0)

    def test_force_halt_during_publication_keeps_router_halted_terminal_rejection(self):
        self.submit()
        later = []
        def halt_before_original_receipts_return(commands, timeout):
            self.assertTrue(self.router._control._state()["market_transition_pending"])
            with patch.object(self.router, "_receipts", side_effect=self.receipts):
                halted = self.router.set_kill_switch(True)
            self.assertFalse(halted["market_transition_pending"])
            later.append(self.router._control._state())
            return self.receipts(commands, timeout)
        with patch.object(self.router, "_receipts", side_effect=halt_before_original_receipts_return):
            with self.assertRaises(ServiceError) as caught:
                self.router.publish_market(self.market(2))
        # Revision 2 intentionally supersedes the old publisher: no global
        # bookkeeping is allowed after another operator changed its phase.
        self.assertEqual((caught.exception.code, caught.exception.status), ("control_superseded", 409))
        self.assertEqual(self.router._control._state(), later[-1])
        self.assertTrue(later[-1]["halted"])
        self.assertFalse(later[-1]["market_transition_pending"])
        result = self.view.process_one(self.queue)
        self.assertEqual((result["state"], result["error"]["code"], result["error"]["status"]),
                         ("REJECTED", "router_halted", 503))
        self.assertEqual(self.view._exchange.orders("alice"), [])

    def test_integrity_freeze_clears_pending_marker_without_risk_acceptance(self):
        self.submit()
        self.pause()
        self.view._freeze("market_barrier_mismatch")
        self.assertFalse(self.router._control._state()["market_transition_pending"])
        # The queued publication remains a priority control; finish it before
        # observing the explicit freeze's terminal SUBMIT rejection.
        self.assertEqual(self.view.process_one(self.queue)["kind"], "PUBLISH_MARKET")
        result = self.view.process_one(self.queue)
        self.assertEqual((result["state"], result["error"]["code"]), ("REJECTED", "router_halted"))
        self.assertEqual(self.view._exchange.orders("alice"), [])

    def test_other_account_cancel_repay_progress_and_same_account_successors_stay_fifo(self):
        self.submit()
        self.queue.enqueue_cancel("alice", "behind", "new-order")
        self.queue.enqueue_cancel("bob", "cancel", "resting")
        self.queue.enqueue_repay("carol", "repay", "USD", D(1))
        self.pause()
        results = [self.view.process_one(self.queue) for _ in range(3)]
        self.assertEqual([row["kind"] for row in results], ["PUBLISH_MARKET", "CANCEL_ORDER", "REPAY"])
        self.assertTrue(all(row["state"] == "SUCCEEDED" for row in results))
        self.assertEqual(results[2]["result"]["principal_repaid"], "1")
        self.assertIsNone(self.view.process_one(self.queue))
        self.assertEqual((self.queue.status("pending")["state"], self.queue.status("behind")["state"]), ("PENDING", "PENDING"))

    def test_original_cid_payload_conflict_is_rejected_while_submission_is_paused(self):
        original = self.submit()
        self.pause()
        with self.assertRaises(ServiceError) as caught:
            self.submit(quantity=D(-1))
        self.assertEqual(caught.exception.code, "idempotency_conflict")
        self.assertEqual(self.queue.status("pending"), original)

    def test_stale_quote_after_activation_cannot_accept_the_deferred_order(self):
        self.submit()
        snapshot, _ = self.pause()
        self.finish_publication(snapshot)
        self.router.set_kill_switch(False)
        with patch.object(self.view._exchange, "clock", return_value=snapshot.observed_at + timedelta(seconds=6)):
            result = self.view.process_one(self.queue)
        self.assertEqual((result["state"], result["error"]["code"]), ("REJECTED", "market_unavailable"))
        self.assertEqual(self.view._exchange.orders("alice"), [])

    def test_prepared_batch_race_recovers_all_members_without_failure_charge_or_poll_churn(self):
        self.submit()
        self.submit("second", "carol", "second-order")
        self.submit("third", "bob", "third-order")
        before = {name: self.row(name) for name in ("pending", "second", "third")}
        prepare = self.batches.prepare
        def pause_after_prepare(*, size):
            attempt = prepare(size=size)
            self.assertIsNotNone(attempt)
            self.pause()
            return attempt
        with patch.object(self.batches, "prepare", side_effect=pause_after_prepare):
            results = self.view.process_batch(self.queue, self.batches, size=3)
        self.assertEqual([row["kind"] for row in results], ["PUBLISH_MARKET"])
        for _ in range(32):
            self.assertEqual(self.view.process_batch(self.queue, self.batches, size=3), [])
        self.assertEqual({name: self.row(name) for name in before}, before)
        with self.router._database(0).read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_command_batch_manifests").fetchone()[0], 1)
            outcomes = connection.execute("SELECT disposition,content FROM uta_command_batch_outcomes").fetchall()
            self.assertEqual(len(outcomes), 1)
            self.assertEqual(outcomes[0][0], "RECOVERED")
            self.assertEqual([row["state"] for row in json.loads(outcomes[0][1])["commands"]], ["PENDING"] * 3)

    def test_paused_selection_still_requires_the_original_live_writer_token(self):
        self.submit()
        self.pause()
        before = self.row()
        self.fence.release(self.token)
        with self.assertRaises(CommandExecutionError) as caught:
            self.view.process_one(self.queue)
        self.assertIsInstance(caught.exception.cause, WriterFenceError)
        self.assertEqual(self.row(), before)

    def test_legacy_and_malformed_persisted_marker_fail_closed(self):
        self.submit()
        with self.router._control._lock(exclusive=True):
            state = self.router._control._state()
            state.update(halted=True, publishing=True)
            state.pop("market_transition_pending")
            with self.router._control.control.transaction() as connection:
                connection.execute("UPDATE router_state SET payload=? WHERE singleton=1", (json.dumps(state, sort_keys=True, separators=(",", ":")),))
        self.assertFalse(_market_transition_pending(self.router._control._state()))
        result = self.view.process_one(self.queue)
        self.assertEqual((result["state"], result["error"]["code"]), ("REJECTED", "router_halted"))
        with self.router._control.control.transaction() as connection:
            state["market_transition_pending"] = 1
            connection.execute("UPDATE router_state SET payload=? WHERE singleton=1", (json.dumps(state, sort_keys=True, separators=(",", ":")),))
        with self.assertRaises(ServiceError) as caught:
            self.router._control._state()
        self.assertEqual(caught.exception.code, "control_corruption")


STATE_METHODS = (
    "MarketTransitionStateContracts.test_missing_marker_is_legacy_false_and_invalid_marker_is_rejected",
    "MarketTransitionStateContracts.test_all_control_writes_clear_activation_and_unrelated_stops",
)
SQL_METHODS = (
    "MarketTransitionPendingSQLContracts.test_fanout_and_activation_gap_keep_original_row_then_commit_once_and_reopen",
    "MarketTransitionPendingSQLContracts.test_force_halt_during_publication_keeps_router_halted_terminal_rejection",
    "MarketTransitionPendingSQLContracts.test_integrity_freeze_clears_pending_marker_without_risk_acceptance",
    "MarketTransitionPendingSQLContracts.test_other_account_cancel_repay_progress_and_same_account_successors_stay_fifo",
    "MarketTransitionPendingSQLContracts.test_original_cid_payload_conflict_is_rejected_while_submission_is_paused",
    "MarketTransitionPendingSQLContracts.test_stale_quote_after_activation_cannot_accept_the_deferred_order",
    "MarketTransitionPendingSQLContracts.test_prepared_batch_race_recovers_all_members_without_failure_charge_or_poll_churn",
    "MarketTransitionPendingSQLContracts.test_paused_selection_still_requires_the_original_live_writer_token",
    "MarketTransitionPendingSQLContracts.test_legacy_and_malformed_persisted_marker_fail_closed",
)

if __name__ == "__main__":
    if tuple(sys.argv[1:]) not in (STATE_METHODS, SQL_METHODS, STATE_METHODS + SQL_METHODS):
        raise SystemExit("requires an exact fixed method tuple; no discovery or retry")
    unittest.main(verbosity=2)
