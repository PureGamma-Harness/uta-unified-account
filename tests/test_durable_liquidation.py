import concurrent.futures
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D, localcontext
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from uta.durable_liquidation import DurableLiquidationController, LiquidationStateError
from uta.liquidation import ActionType, PositionReduction, TimedRisk
from uta.storage import Database


@dataclass(frozen=True)
class Risk:
    equity: D
    maintenance_margin: D


class DurableLiquidationTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "liquidation.sqlite3"
        self.database = Database(self.path)
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.controller = DurableLiquidationController(self.database, "acct")

    def restart(self, **kwargs):
        return DurableLiquidationController(Database(self.path), "acct", **kwargs)

    def snap(self, equity="100", mm="100", at=None, complete=True):
        return TimedRisk(Risk(D(equity), D(mm)), at or self.now, complete)

    def test_initial_status_is_blocked_and_json_safe(self):
        status = self.controller.status()
        self.assertEqual(status["phase"], "blocked")
        self.assertFalse(status["trading_allowed"])
        self.assertIsNone(status["pending_action"])
        self.assertIsNone(status["last_evaluated_at"])
        self.assertEqual(json.loads(json.dumps(status)), status)

    def test_pending_action_and_history_survive_restart(self):
        action = self.controller.next_action(self.snap(), now=self.now)
        restored = self.restart()
        before = restored.status()
        self.assertEqual(restored.next_action(self.snap(), now=self.now), action)
        self.assertEqual(restored.status(), before)
        self.assertEqual(restored.status()["pending_action"]["action_id"], action.action_id)
        self.assertTrue(restored.acknowledge(action.action_id, success=True, now=self.now))
        restored = self.restart()
        before = restored.status()
        self.assertFalse(restored.acknowledge(action.action_id, success=True, now=self.now))
        self.assertEqual(restored.status(), before)
        self.assertEqual(restored.status()["completed_action_count"], 1)
        self.assertIsNone(restored.status()["pending_action"])
        self.assertEqual(restored.status()["phase"], "reduce_exposure")

    def test_fresh_after_ack_is_enforced_across_restart(self):
        action = self.controller.next_action(self.snap(), now=self.now)
        self.controller.acknowledge(action.action_id, success=True, now=self.now)
        restored = self.restart()
        reduction = PositionReduction("BTC-PERP", D("-2"), D("0.5"))
        self.assertIsNone(restored.next_action(self.snap(), now=self.now, reduction=reduction))
        self.assertEqual(restored.status()["phase"], "blocked")
        later = self.now + timedelta(microseconds=1)
        action2 = restored.next_action(self.snap(at=later), now=later, reduction=reduction)
        self.assertEqual(action2.kind, ActionType.REDUCE_POSITION)
        self.assertEqual((action2.side, action2.quantity, action2.reduce_only), ("buy", D("0.5"), True))
        self.assertNotEqual(action.action_id, action2.action_id)
        self.assertEqual(self.restart().status()["pending_action"]["quantity"], "0.5")

    def test_recovery_hysteresis_and_new_cycle_survive_restart(self):
        action = self.controller.next_action(self.snap(), now=self.now)
        self.controller.acknowledge(action.action_id, success=True, now=self.now)
        later = self.now + timedelta(seconds=1)
        restored = self.restart()
        self.assertIsNone(restored.next_action(self.snap("110", at=later), now=later))
        self.assertEqual(restored.status()["phase"], "reduce_exposure")
        self.assertFalse(restored.status()["trading_allowed"])
        restored = self.restart()
        self.assertIsNone(restored.next_action(self.snap("110.00000000000000000000001", at=later), now=later))
        self.assertEqual(restored.status()["phase"], "recovered")
        self.assertTrue(restored.status()["trading_allowed"])
        restored = self.restart()
        next_action = restored.next_action(self.snap(at=later), now=later)
        self.assertEqual(next_action.action_id, "acct:2:2")

    def test_stale_and_invalid_data_block_without_losing_pending(self):
        action = self.controller.next_action(self.snap(), now=self.now)
        later = self.now + timedelta(seconds=20)
        for snapshot in (None, self.snap(), self.snap(at=later, complete=1),
                         self.snap(at=later, complete="true"), self.snap("NaN", at=later)):
            restored = self.restart()
            self.assertIsNone(restored.next_action(snapshot, now=later))
            status = restored.status()
            self.assertFalse(status["trading_allowed"])
            self.assertEqual(status["phase"], "blocked")
            self.assertEqual(status["pending_action"]["action_id"], action.action_id)
        self.assertEqual(self.restart().next_action(self.snap(at=later), now=later), action)

    def test_failed_acknowledgement_and_invalid_bool_never_complete(self):
        action = self.controller.next_action(self.snap(), now=self.now)
        for value in (1, 0, "true", "false", None):
            before = self.controller.status()
            with self.assertRaisesRegex(ValueError, "boolean"):
                self.controller.acknowledge(action.action_id, success=value, now=self.now)
            self.assertEqual(self.controller.status(), before)
        self.assertFalse(self.controller.acknowledge(action.action_id, success=False, now=self.now))
        restored = self.restart()
        self.assertEqual(restored.status()["pending_action"]["action_id"], action.action_id)
        self.assertEqual(restored.status()["completed_action_count"], 0)
        self.assertTrue(restored.acknowledge(action.action_id, success=True, now=self.now))

    def test_concurrent_instances_share_action_and_acknowledgement(self):
        peers = [self.restart() for _ in range(4)]
        def evaluate(index):
            return peers[index % len(peers)].next_action(self.snap(), now=self.now)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            actions = list(executor.map(evaluate, range(40)))
        self.assertTrue(all(action == actions[0] for action in actions))
        def acknowledge(index):
            return peers[index % len(peers)].acknowledge(actions[0].action_id, success=True, now=self.now)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(acknowledge, range(40)))
        self.assertEqual(sum(results), 1)
        self.assertEqual(self.restart().status()["completed_action_count"], 1)

    def test_concurrent_processes_propose_one_durable_action(self):
        script = """
from datetime import datetime, timezone
from decimal import Decimal as D
from types import SimpleNamespace
import sys
from uta.durable_liquidation import DurableLiquidationController
from uta.liquidation import TimedRisk
from uta.storage import Database
controller = DurableLiquidationController(Database(sys.argv[1]), 'acct')
now = datetime(2026, 1, 1, tzinfo=timezone.utc)
action = controller.next_action(TimedRisk(SimpleNamespace(equity=D('99'), maintenance_margin=D('100')), now), now=now)
print(action.action_id)
"""
        processes = [subprocess.Popen([sys.executable, "-c", script, str(self.path)],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(4)]
        try:
            for process in processes:
                output, error = process.communicate(timeout=20)
                self.assertEqual(process.returncode, 0, error)
                self.assertEqual(output.strip(), "acct:1:1")
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.wait()
        self.assertEqual(self.restart().status()["pending_action"]["action_id"], "acct:1:1")

    def test_commit_and_rollback_survive_abrupt_process_exit(self):
        script = """
from datetime import datetime, timezone
from decimal import Decimal as D
import os
import sys
from types import SimpleNamespace
from uta.durable_liquidation import DurableLiquidationController
from uta.liquidation import TimedRisk
from uta.storage import Database
class CrashDatabase(Database):
    def _connect(self):
        connection = super()._connect()
        connection.create_function('crash_now', 0, lambda: os._exit(17))
        return connection
database = CrashDatabase(sys.argv[1])
controller = DurableLiquidationController(database, 'acct')
now = datetime(2026, 1, 1, tzinfo=timezone.utc)
controller.next_action(TimedRisk(SimpleNamespace(equity=D('100'), maintenance_margin=D('100')), now), now=now)
os._exit(17)
"""
        with self.database.transaction() as connection:
            connection.execute("""CREATE TRIGGER injected_crash BEFORE UPDATE ON durable_liquidation_controllers
                BEGIN SELECT crash_now(); END""")
        result = subprocess.run([sys.executable, "-c", script, str(self.path)],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 17, result.stderr)
        self.assertIsNone(self.restart().status()["pending_action"])
        with self.database.transaction() as connection:
            connection.execute("DROP TRIGGER injected_crash")
        result = subprocess.run([sys.executable, "-c", script, str(self.path)],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 17, result.stderr)
        self.assertEqual(self.restart().status()["pending_action"]["action_id"], "acct:1:1")

    def test_configuration_is_persisted_and_conflicting_policies_fail(self):
        self.assertEqual(self.restart(recovery_buffer=D("1.1000")).status()["phase"], "blocked")
        for policy in ({"recovery_buffer": D("1.2")}, {"max_age": timedelta(seconds=11)}):
            with self.assertRaisesRegex(LiquidationStateError, "policy differs"):
                self.restart(**policy)
        for statement in ("DELETE FROM durable_liquidation_controllers",
                          "UPDATE durable_liquidation_controllers SET max_age_us = '1'"):
            with self.database.transaction() as connection:
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(statement)
        self.assertEqual(self.controller.status()["phase"], "blocked")

    def test_corrupt_state_fails_closed_without_resetting_or_acknowledging(self):
        action = self.controller.next_action(self.snap(), now=self.now)
        with self.database.transaction() as connection:
            connection.execute("UPDATE durable_liquidation_controllers SET state = '{}' WHERE account_id = 'acct'")
        for operation in (self.controller.status,
                          lambda: self.controller.next_action(self.snap("120"), now=self.now),
                          lambda: self.controller.acknowledge(action.action_id, success=True, now=self.now),
                          self.restart):
            with self.assertRaisesRegex(LiquidationStateError, "checksum"):
                operation()

    def test_state_validation_rejects_inconsistent_flags_even_with_recomputed_digest(self):
        with self.database.transaction() as connection:
            row = connection.execute("SELECT revision, state FROM durable_liquidation_controllers").fetchone()
            state = json.loads(row[1])
            state["can_trade"] = True
            encoded = json.dumps(state, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            connection.execute("UPDATE durable_liquidation_controllers SET state = ?, digest = ?",
                               (encoded, self.controller._digest(row[0], encoded)))
        with self.assertRaisesRegex(LiquidationStateError, "trading flag contradicts"):
            self.controller.status()

    def test_schema_version_is_checked_on_every_method(self):
        with self.database.transaction() as connection:
            connection.execute("UPDATE durable_liquidation_schema SET version = 999")
        with self.assertRaisesRegex(LiquidationStateError, "schema version"):
            self.controller.status()
        with self.assertRaisesRegex(LiquidationStateError, "schema version"):
            self.restart()

    def test_decimal_and_utc_serialization_ignore_callers_context(self):
        # A non-UTC caller timestamp is stored explicitly as UTC, with no float
        # conversion. Very large scientific-notation Decimals stay bounded.
        shifted = self.now.astimezone(timezone(timedelta(hours=8)))
        action = self.controller.next_action(self.snap(at=shifted), now=shifted)
        self.controller.acknowledge(action.action_id, success=True, now=shifted)
        later = shifted + timedelta(seconds=1)
        with localcontext() as context:
            context.prec = 2
            context.Emax = 2
            context.Emin = -2
            quantity = D("1.2345678901234567890123456789012345678901E+50")
            action = self.controller.next_action(self.snap(at=later), now=later,
                reduction=PositionReduction("BTC-PERP", quantity.copy_negate(), quantity))
            self.assertEqual(action.quantity, quantity)
            self.assertEqual(self.restart().status()["pending_action"]["quantity"], str(quantity))
        self.assertEqual(self.controller.status()["last_observed_at"], "2026-01-01T00:00:01.000000+00:00")
        self.assertEqual(json.loads(json.dumps(self.controller.status())), self.controller.status())

    def test_invalid_reduction_does_not_advance_durable_action_sequence(self):
        action = self.controller.next_action(self.snap(), now=self.now)
        self.controller.acknowledge(action.action_id, success=True, now=self.now)
        later = self.now + timedelta(seconds=1)
        before = self.controller.status()
        with self.assertRaises(ValueError):
            self.controller.next_action(self.snap(at=later), now=later,
                reduction=PositionReduction("BTC-PERP", D("1"), D("2")))
        self.assertEqual(self.controller.status(), before)
        action = self.restart().next_action(self.snap(at=later), now=later,
            reduction=PositionReduction("BTC-PERP", D("1"), D("0.5")))
        self.assertEqual(action.action_id, "acct:1:2")


if __name__ == "__main__":
    unittest.main()
