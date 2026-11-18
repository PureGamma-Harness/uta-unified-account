"""Finite new activation-failure contracts; CODE-only, no executions recorded.

Real SQL fixtures never start a worker/thread. Read-verifier fault injections
are explicit negatives; they do not replace valuation, quote, fee or COMMIT
functions in the implementation. Legacy blocked-source inputs remain intact.
"""
from datetime import datetime, timezone
from decimal import Decimal as D
import json
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import test_market_transition_pending as fixtures
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec, RiskInputError
from uta.service import ServiceError
from uta.sharding import (ShardRouter, _record_transition_failure,
                          _transition_failure_cause, _transition_identity)


def state():
    return dict(halted=True, publishing=False, market_transition_pending=True,
                epoch=2, target_version=2, target_digest="a" * 64, error=None,
                market_version=2, market_digest="a" * 64, watermarks={"0": 2},
                durable_market_commands={"0": "market:2"}, durable_halt_commands={},
                durable_desired_halt=True)


class ActivationFailureStateContracts(unittest.TestCase):
    def test_quote_timeout_busy_and_superseded_are_narrowly_classified(self):
        stale = ServiceError("market_unavailable", "synthetic stale", 503)
        self.assertIsNone(_transition_failure_cause(stale, "quote_freshness"))
        self.assertEqual(_transition_failure_cause(stale, "activation_integrity"), "control_transition_failed")
        quote = RiskInputError("synthetic age")
        self.assertIsNone(_transition_failure_cause(quote, "quote_freshness"))
        self.assertEqual(_transition_failure_cause(quote, "activation_integrity"), "control_transition_failed")
        self.assertIsNone(_transition_failure_cause(TimeoutError(), "halt_receipts"))
        self.assertEqual(_transition_failure_cause(TimeoutError(), "control_persistence"), "control_transition_failed")
        for code, status in (("router_busy", 503), ("durable_queue_overloaded", 503),
                             ("publication_incomplete", 503), ("control_superseded", 409)):
            self.assertIsNone(_transition_failure_cause(ServiceError(code, "synthetic", status), "activation_integrity"))
        busy = sqlite3.OperationalError("synthetic busy")
        busy.sqlite_errorcode = 5  # SQLITE_BUSY, including pre-3.11 module APIs.
        self.assertIsNone(_transition_failure_cause(busy, "activation_integrity"))
        self.assertIsNone(_transition_failure_cause(sqlite3.OperationalError("database is locked"), "activation_integrity"))
        self.assertEqual(_transition_failure_cause(RuntimeError("unknown"), "activation_integrity"), "control_transition_failed")

    def test_fatal_stop_write_failure_keeps_original_error_and_first_cause_unknown(self):
        original = ServiceError("market_barrier_mismatch", "synthetic original", 503)
        first_cause = ValueError("synthetic source cause")
        original.__cause__ = first_cause
        stop = sqlite3.OperationalError("synthetic full")
        stop.sqlite_errorcode = 13  # SQLITE_FULL.
        control = SimpleNamespace(_write_state=lambda value: (_ for _ in ()).throw(stop))
        with self.assertRaises(ServiceError) as caught:
            _record_transition_failure(control, state(), original, phase="activation_integrity")
        self.assertIs(caught.exception, original)
        self.assertEqual(original.code, "market_barrier_mismatch")
        self.assertIs(original.__cause__, stop)
        self.assertIs(stop.__cause__, first_cause)
        self.assertTrue(any("UNKNOWN" in note for note in original.__notes__))

    def test_old_waiter_cannot_change_new_operator_or_publication_identity(self):
        before = state()
        expected = _transition_identity(before)
        original = ServiceError("spot_corrupt", "synthetic original", 503)
        writes = []
        control = SimpleNamespace(_write_state=lambda value: writes.append(dict(value)))
        for changes in (
            dict(market_transition_pending=False, durable_halt_commands={"0": "operator-stop"}),
            dict(epoch=3, durable_market_commands={"0": "new-publication"}),
            dict(watermarks={"0": 2, "1": 2}),  # Same generation/flags; progress must never regress.
            dict(market_version=3), dict(market_digest="b" * 64),
            dict(unknown_native_field=[1, True, None]),
        ):
            current = {**before, **changes}
            exact = json.dumps(current, sort_keys=True)
            self.assertFalse(_record_transition_failure(control, current, original,
                phase="activation_integrity", expected=expected))
            self.assertEqual(json.dumps(current, sort_keys=True), exact)
        self.assertEqual(writes, [])
        legacy = {**before, "market_transition_pending": False}
        without = dict(legacy)
        without.pop("market_transition_pending")
        self.assertEqual(_transition_identity(legacy), _transition_identity(without))
        for invalid in (float("nan"), float("inf"), object(), 2**63):
            with self.assertRaises(ServiceError) as caught:
                _transition_identity({**before, "unknown_native_field": invalid})
            self.assertEqual(caught.exception.code, "control_corruption")
        current = state()
        self.assertTrue(_record_transition_failure(control, current, original,
            phase="activation_integrity", expected=_transition_identity(current)))
        self.assertEqual((current["halted"], current["market_transition_pending"], current["error"]), (True, False, "spot_corrupt"))


class SyncActivationFailureSQLContracts(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.router = ShardRouter(Path(temporary.name) / "sync", 1, {"USD": 2})
        self.router.create_account("account")
        self.router.deposit("account", "fund", "USD", D(1000))
        self.router.publish_market(self.market(1))
        self.router.set_kill_switch(False)
        self.router.publish_market(self.market(2))
        self.assertTrue(self.router._state()["market_transition_pending"])

    @staticmethod
    def market(version):
        return MarketSnapshot(version, datetime.now(timezone.utc),
            {"USD": AssetSpec(D(1), D(1))},
            {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))})

    def stopped(self, code):
        observed = self.router._state()
        self.assertEqual((observed["halted"], observed["market_transition_pending"], observed["error"]), (True, False, code))

    def test_sync_bad_local_generation_records_stop_before_original_raise(self):
        # Fault fixture deliberately bypasses the global router in this fresh
        # authority. The local publish itself is native, valid and auditable.
        self.router._services[0].publish_market(self.market(3))
        with self.assertRaises(ServiceError) as caught:
            self.router.set_kill_switch(False)
        self.assertEqual(caught.exception.code, "market_barrier_mismatch")
        self.stopped("market_barrier_mismatch")

    def test_sync_funding_reconcile_error_records_stop_and_preserves_original(self):
        original = ServiceError("funding_registry_conflict", "synthetic verifier fault", 503)
        with patch.object(self.router, "_reconcile_funding", side_effect=original):
            with self.assertRaises(ServiceError) as caught:
                self.router.set_kill_switch(False)
        self.assertIs(caught.exception, original)
        self.stopped("funding_registry_conflict")


class ManagedActivationFailureSQLContracts(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.MarketTransitionPendingSQLContracts()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.submit()
        snapshot, _ = self.fixture.pause()
        self.fixture.finish_publication(snapshot)

    def stopped(self, code):
        observed = self.fixture.router._control._state()
        self.assertEqual((observed["halted"], observed["market_transition_pending"], observed["error"]), (True, False, code))
        self.assertEqual(self.fixture.queue.status("pending")["state"], "PENDING")
        # The marker no longer hides the guard. Original explicit-stop refusal
        # is observable on the next poll, with no order accepted.
        result = self.fixture.view.process_one(self.fixture.queue)
        self.assertEqual((result["state"], result["error"]["code"]), ("REJECTED", "router_halted"))
        self.assertEqual(self.fixture.view._exchange.orders("alice"), [])

    def test_managed_bad_local_generation_after_receipts_clears_pending(self):
        fixture = self.fixture
        def settle_then_change_local(commands, timeout):
            receipts = fixture.receipts(commands, timeout)
            fixture.view._exchange.publish_market(fixture.market(3))
            return receipts
        with patch.object(fixture.router, "_receipts", side_effect=settle_then_change_local):
            with self.assertRaises(ServiceError) as caught:
                fixture.router.set_kill_switch(False)
        self.assertEqual(caught.exception.code, "market_barrier_mismatch")
        self.stopped("market_barrier_mismatch")

    def test_managed_source_error_only_in_second_EX_is_persisted_and_rethrown(self):
        fixture = self.fixture
        original = ServiceError("spot_corrupt", "synthetic second-phase source fault", 503)
        def settle_then_arm(commands, timeout):
            receipts = fixture.receipts(commands, timeout)
            checker = patch("uta.durable_process._verify_managed_spot_source", side_effect=original)
            checker.start()
            self.addCleanup(checker.stop)
            return receipts
        with patch.object(fixture.router, "_receipts", side_effect=settle_then_arm):
            with self.assertRaises(ServiceError) as caught:
                fixture.router.set_kill_switch(False)
        self.assertIs(caught.exception, original)
        self.stopped("spot_corrupt")

    def test_managed_funding_reconcile_only_in_second_EX_clears_pending(self):
        fixture = self.fixture
        original = ServiceError("funding_registry_conflict", "synthetic second-phase funding fault", 503)
        def settle_then_arm(commands, timeout):
            receipts = fixture.receipts(commands, timeout)
            checker = patch.object(fixture.router._control, "_batch_reconcile_shard", side_effect=original)
            checker.start()
            self.addCleanup(checker.stop)
            return receipts
        with patch.object(fixture.router, "_receipts", side_effect=settle_then_arm):
            with self.assertRaises(ServiceError) as caught:
                fixture.router.set_kill_switch(False)
        self.assertIs(caught.exception, original)
        self.stopped("funding_registry_conflict")

    def test_late_publication_exception_does_not_overwrite_later_operator_halt(self):
        fixture = self.fixture
        # Open a new generation from active control, so this publication owns
        # a real True marker before the later operator stop.
        fixture.router.set_kill_switch(False)
        original = ServiceError("spot_corrupt", "synthetic late publication read fault", 503)
        snapshot = fixture.market(3)
        later = []
        def stop_then_raise(commands, timeout):
            with patch.object(fixture.router, "_receipts", side_effect=fixture.receipts):
                fixture.router.set_kill_switch(True)
            later.append(fixture.router._control._state())
            self.assertEqual(later[-1]["durable_market_commands"], commands)
            raise original
        with patch.object(fixture.router, "_receipts", side_effect=stop_then_raise):
            with self.assertRaises(ServiceError) as caught:
                fixture.router.publish_market(snapshot)
        self.assertEqual((caught.exception.code, caught.exception.status), ("control_superseded", 409))
        self.assertIs(caught.exception.__cause__, original)
        self.assertEqual(fixture.router._control._state(), later[-1])
        self.assertFalse(later[-1]["market_transition_pending"])

        # A new explicit request after querying current control may finish the
        # generation. The superseded waiter itself never retries or mutates.
        fixture.router.publish_market(snapshot)
        fixture.router.set_kill_switch(False)
        snapshot4 = fixture.market(4)
        active = []
        def complete_activate_then_return_old_partial(commands, timeout):
            with patch.object(fixture.router, "_receipts", side_effect=fixture.receipts):
                completed = fixture.router.publish_market(snapshot4)
                fixture.router.set_kill_switch(False)
            self.assertEqual(completed["durable_market_commands"], commands)
            active.append(fixture.router._control._state())
            return {"0": None}  # Deliberately stale partial observation.
        with self.subTest(scenario="late_partial_after_same_generation_activation"):
            with patch.object(fixture.router, "_receipts", side_effect=complete_activate_then_return_old_partial):
                with self.assertRaises(ServiceError) as caught:
                    fixture.router.publish_market(snapshot4)
            self.assertEqual((caught.exception.code, caught.exception.status), ("control_superseded", 409))
            self.assertEqual(fixture.router._control._state(), active[-1])
            self.assertFalse(active[-1]["halted"])
            self.assertFalse(active[-1]["publishing"])
            self.assertEqual(active[-1]["watermarks"], {"0": 4})

    def test_late_activation_exception_does_not_overwrite_later_operator_halt(self):
        fixture = self.fixture
        original = ServiceError("funding_registry_conflict", "synthetic late activation read fault", 503)
        later = []
        def stop_then_raise(commands, timeout):
            with patch.object(fixture.router, "_receipts", side_effect=fixture.receipts):
                fixture.router.set_kill_switch(True)
            later.append(fixture.router._control._state())
            self.assertNotEqual(later[-1]["durable_halt_commands"], commands)
            raise original
        with patch.object(fixture.router, "_receipts", side_effect=stop_then_raise):
            with self.assertRaises(ServiceError) as caught:
                fixture.router.set_kill_switch(False)
        self.assertEqual((caught.exception.code, caught.exception.status), ("control_superseded", 409))
        self.assertIs(caught.exception.__cause__, original)
        self.assertEqual(fixture.router._control._state(), later[-1])
        self.assertFalse(later[-1]["market_transition_pending"])

    def test_late_successful_activation_receipts_cannot_reopen_integrity_freeze(self):
        fixture = self.fixture
        later = []
        def settle_then_freeze(commands, timeout):
            receipts = fixture.receipts(commands, timeout)
            fixture.view._freeze("market_barrier_mismatch")
            later.append(fixture.router._control._state())
            return receipts
        with patch.object(fixture.router, "_receipts", side_effect=settle_then_freeze):
            with self.assertRaises(ServiceError) as caught:
                fixture.router.set_kill_switch(False)
        self.assertEqual(caught.exception.code, "control_superseded")
        self.assertEqual(fixture.router._control._state(), later[-1])
        self.stopped("market_barrier_mismatch")


STATE_METHODS = (
    "ActivationFailureStateContracts.test_quote_timeout_busy_and_superseded_are_narrowly_classified",
    "ActivationFailureStateContracts.test_fatal_stop_write_failure_keeps_original_error_and_first_cause_unknown",
    "ActivationFailureStateContracts.test_old_waiter_cannot_change_new_operator_or_publication_identity",
)
SQL_METHODS = (
    "SyncActivationFailureSQLContracts.test_sync_bad_local_generation_records_stop_before_original_raise",
    "SyncActivationFailureSQLContracts.test_sync_funding_reconcile_error_records_stop_and_preserves_original",
    "ManagedActivationFailureSQLContracts.test_managed_bad_local_generation_after_receipts_clears_pending",
    "ManagedActivationFailureSQLContracts.test_managed_source_error_only_in_second_EX_is_persisted_and_rethrown",
    "ManagedActivationFailureSQLContracts.test_managed_funding_reconcile_only_in_second_EX_clears_pending",
    "ManagedActivationFailureSQLContracts.test_late_publication_exception_does_not_overwrite_later_operator_halt",
    "ManagedActivationFailureSQLContracts.test_late_activation_exception_does_not_overwrite_later_operator_halt",
    "ManagedActivationFailureSQLContracts.test_late_successful_activation_receipts_cannot_reopen_integrity_freeze",
)

if __name__ == "__main__":
    if tuple(sys.argv[1:]) not in (STATE_METHODS, SQL_METHODS, STATE_METHODS + SQL_METHODS):
        raise SystemExit("requires an exact fixed method tuple; no discovery or retry")
    unittest.main(verbosity=2)
