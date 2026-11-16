"""Append-only evidence and reconstruction tests using synthetic accounts."""
from datetime import datetime, timezone
from decimal import Decimal as D, Inexact, Rounded, localcontext
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from uta.decision_audit import DecisionAudit, DecisionAuditError
from uta.durable_commands import CommandExecutionError, QueueStore
from uta.examples import synthetic_policy
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ExchangeService, ServiceError
from uta.storage import Database, StorageError
from uta.writer_fence import WriterFence


class AuditArchiveTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "audit.sqlite3"
        self.database = Database(self.path)
        self.now = datetime(2026, 11, 16, tzinfo=timezone.utc)
        self.legacy = ExchangeService(self.database, {"USD": 2}, clock=lambda: self.now)
        self.legacy.create_account("alice")
        self.legacy.deposit("alice", "fund", "USD", D(100))
        self.market = MarketSnapshot(1, self.now, {"USD": AssetSpec(D(1), D(1))},
                                    {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))})
        self.legacy.publish_market(self.market)
        self.legacy.set_kill_switch(False)

    def install(self):
        audit = DecisionAudit(self.database)
        with self.database.transaction() as connection:
            audit.install(connection, policy=DecisionAudit.policy(self.legacy), recorded_at=self.now.isoformat())
        return audit

    def test_explicit_upgrade_keeps_legacy_gap_and_current_observation(self):
        self.legacy.submit_order("alice", "old", "BTC-PERP", D(1), D(100))
        self.legacy.apply_fill("alice", "old", "old-fill", D(1), D(100))
        audit = self.install()
        with self.database.read_transaction() as connection:
            capability = dict(connection.execute("SELECT * FROM uta_audit_capability").fetchone())
            self.assertEqual(connection.execute("SELECT version FROM uta_schema").fetchone()[0], 3)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_risk_decisions").fetchone()[0], 0)
            self.assertIsNone(connection.execute("SELECT admission_decision_id FROM uta_orders").fetchone()[0])
            self.assertIsNone(connection.execute("SELECT execution_decision_id FROM uta_fills").fetchone()[0])
            history = dict(connection.execute("SELECT * FROM uta_market_history").fetchone())
        self.assertEqual(capability["legacy_order_count"], 1)
        self.assertEqual(capability["legacy_fill_count"], 1)
        self.assertIn("unavailable", json.loads(capability["gaps"])["before_upgrade"])
        self.assertEqual(history["origin"], "UPGRADE_OBSERVED")
        self.assertEqual(history["payload"], self.market.to_json())
        self.assertEqual(history["snapshot_id"], "market:" + sha256(history["payload"].encode()).hexdigest())
        self.assertEqual(audit.market(history["snapshot_id"]), history)
        self.assertFalse(audit.artifact(audit.artifact_id)["signed"])

    def test_content_archives_are_immutable_including_replace(self):
        self.install()
        for statement in (
            "UPDATE uta_market_history SET origin='FABRICATED'",
            "DELETE FROM uta_market_history",
            "INSERT OR REPLACE INTO uta_market_history SELECT * FROM uta_market_history",
            "UPDATE uta_code_artifacts SET manifest='{}'",
            "DELETE FROM uta_risk_policies",
            "UPDATE uta_audit_capability SET legacy_order_count=0",
        ):
            with self.subTest(statement=statement), self.assertRaises(sqlite3.IntegrityError):
                with self.database.transaction() as connection:
                    connection.execute(statement)

    def test_old_protocol_new_order_and_unarchived_market_writes_fail_closed(self):
        self.install()
        with self.assertRaises(sqlite3.IntegrityError):
            self.legacy.submit_order("alice", "old-protocol", "BTC-PERP", D(1), D(100))
        changed = MarketSnapshot(2, self.now, self.market.assets,
                                {"BTC-PERP": InstrumentSpec(D(110), D(".1"), D(".05"))})
        with self.assertRaises(sqlite3.IntegrityError):
            self.legacy.publish_market(changed)
        with self.database.read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_orders").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT payload FROM uta_market").fetchone()[0], self.market.to_json())

    def test_missing_required_guard_is_rejected_without_automatic_repair(self):
        audit = self.install()
        with self.database.transaction() as connection:
            connection.execute("DROP TRIGGER audit_fill_requires_decision")
        with self.assertRaises(DecisionAuditError):
            with self.database.transaction() as connection:
                audit.install(connection, policy=DecisionAudit.policy(self.legacy), recorded_at=self.now.isoformat())


class AuditedServiceTests(unittest.TestCase):
    setUp = AuditArchiveTests.setUp

    def required(self):
        return ExchangeService(self.database, {"USD": 2}, clock=lambda: self.now, decision_audit=True)

    def test_acceptance_replays_archived_market_and_account_after_later_changes(self):
        service = self.required()
        accepted = service.submit_order("alice", "order", "BTC-PERP", D(2), D(100))
        identity = accepted["decision_id"]
        decision = service.audit.decision(identity)
        self.assertEqual(decision["pre_version"], 1)
        self.assertEqual(decision["post_version"], 2)
        self.assertEqual(decision["summary"]["reserved_margin"], "20.08")
        service.publish_market(MarketSnapshot(2, self.now, self.market.assets,
            {"BTC-PERP": InstrumentSpec(D(200), D(".1"), D(".05"))}))
        service.deposit("alice", "later-funding", "USD", D(50))
        service.cancel_order("alice", "order")
        replay = service.audit.replay(identity)
        self.assertTrue(replay["matches"], replay["differences"])
        self.assertEqual(replay["operation"]["reserved_margin"], "20.08")
        self.assertEqual(replay["values"]["before"]["equity"], "100")
        self.assertEqual(replay["values"]["after"]["open_order_margin"], "20.08")
        self.assertEqual(replay["values"]["after"]["available_margin"], "79.92")
        self.assertEqual(service.audit.market(decision["market_snapshot_id"])["payload"], self.market.to_json())
        events = service.events(limit=100)
        event = next(e for e in events if e["event_type"] == "ORDER_ACCEPTED")
        self.assertEqual(event["payload"]["decision_id"], identity)

    def test_partial_fill_replays_cash_position_fees_and_remaining_reserve(self):
        service = self.required()
        order = service.submit_order("alice", "order", "BTC-PERP", D(2), D(100))
        fill = service.apply_fill("alice", "order", "fill", D(".5"), D(100))
        identity = fill["execution_decision_id"]
        self.assertEqual(fill["decision_id"], order["decision_id"])
        decision = service.audit.decision(identity)
        self.assertEqual(decision["summary"]["fee"], "0.02")
        self.assertEqual(decision["inputs"]["after"]["positions"]["BTC-PERP"], {"quantity": "0.5", "cost_basis": "50"})
        service.publish_market(MarketSnapshot(2, self.now, self.market.assets,
            {"BTC-PERP": InstrumentSpec(D(200), D(".1"), D(".05"))}))
        replay = service.audit.replay(identity)
        self.assertTrue(replay["matches"], replay["differences"])
        self.assertEqual(replay["values"]["after"], {"equity": "99.98", "initial_margin": "5",
            "maintenance_margin": "2.5", "open_order_margin": "15.06", "available_margin": "79.92"})
        retry = service.apply_fill("alice", "order", "fill", D(".50"), D("100.00"))
        self.assertEqual(retry["execution_decision_id"], identity)
        with self.database.read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_risk_decisions").fetchone()[0], 2)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_code_artifacts").fetchone()[0], 1)

    def test_audit_write_failure_and_missing_deferred_record_rollback_financial_effects(self):
        service = self.required()
        before = service.account("alice")
        with patch.object(service.audit, "record", side_effect=StorageError("audit disk fault")):
            with self.assertRaises(StorageError):
                service.submit_order("alice", "failed", "BTC-PERP", D(1), D(100))
        self.assertEqual(service.account("alice"), before)
        self.assertEqual(service.orders("alice"), [])
        with patch.object(service.audit, "record", return_value=None):
            with self.assertRaises(sqlite3.IntegrityError):
                service.submit_order("alice", "missing", "BTC-PERP", D(1), D(100))
        self.assertEqual(service.account("alice"), before)
        service.submit_order("alice", "order", "BTC-PERP", D(1), D(100))
        before = service.account("alice")
        journal = service.ledger.journal()
        with patch.object(service.audit, "record", side_effect=StorageError("audit disk fault")):
            with self.assertRaises(StorageError):
                service.apply_fill("alice", "order", "failed-fill", D(1), D(100))
        self.assertEqual(service.account("alice"), before)
        self.assertEqual(service.ledger.journal(), journal)

    def test_schema_three_rejects_legacy_constructor_and_preserves_legacy_row_gaps(self):
        self.legacy.submit_order("alice", "legacy", "BTC-PERP", D(1), D(100))
        service = self.required()
        self.assertEqual(service.orders("alice")[0]["decision_evidence"], "legacy_missing")
        with self.assertRaises(ServiceError) as error:
            ExchangeService(self.database, {"USD": 2}, clock=lambda: self.now)
        self.assertEqual(error.exception.code, "schema_version")
        self.assertEqual(service.cancel_order("alice", "legacy")["status"], "CANCELLED")
        self.assertEqual(self.required().account("alice"), service.account("alice"))

    def test_fenced_upgrade_installs_data_guards_for_new_archive_tables(self):
        fence = WriterFence(self.database)
        fence.enable("audit-authority")
        token = fence.acquire("audit-writer", ttl_seconds=30)
        service = ExchangeService(self.database.for_writer(token), {"USD": 2},
                                  clock=lambda: self.now, decision_audit=True)
        result = service.submit_order("alice", "order", "BTC-PERP", D(1), D(100))
        self.assertTrue(service.audit.replay(result["decision_id"])["matches"])
        with self.assertRaises((StorageError, ServiceError)):
            self.legacy.submit_order("alice", "old", "BTC-PERP", D(1), D(100))
        self.assertEqual(len(service.orders("alice")), 1)

    def test_configured_cross_audit_reconstructs_full_rule_based_values(self):
        database = Database(self.path.parent / "configured.sqlite3")
        catalog, rules = synthetic_policy()
        service = ExchangeService(database, {"USD": 2, "BTC": 8}, clock=lambda: self.now,
            product_catalog=catalog, portfolio_rules=rules, decision_audit=True)
        market = MarketSnapshot(1, self.now,
            {"USD": AssetSpec(D(1), D(1)), "BTC": AssetSpec(D(100), D(".8"))}, self.market.instruments)
        service.create_account("alice")
        service.publish_market(market)
        service.deposit("alice", "fund", "USD", D(100))
        service.set_kill_switch(False)
        order = service.submit_order("alice", "order", "BTC-PERP", D(1), D(100))
        fill = service.apply_fill("alice", "order", "fill", D(".5"), D(100))
        for identity in (order["decision_id"], fill["execution_decision_id"]):
            replay = service.audit.replay(identity)
            self.assertTrue(replay["matches"], replay["differences"])
            self.assertIn("collateral_value", replay["values"]["after"])

    def test_durable_terminal_receipt_and_audit_link_commit_atomically(self):
        queue = QueueStore(self.database, initialize=True, clock=lambda: self.now)
        fence = WriterFence(self.database)
        fence.enable("durable-audit")
        service = ExchangeService(self.database.for_writer(fence.acquire("worker", ttl_seconds=30)),
                                  {"USD": 2}, clock=lambda: self.now, decision_audit=True)
        queue.enqueue_submit("alice", "command", "order", "BTC-PERP", D(1), D(100))
        with patch.object(service.audit, "record", side_effect=StorageError("audit unavailable")):
            with self.assertRaises(CommandExecutionError):
                queue.process_one(service)
        self.assertEqual(queue.status("command")["state"], "PENDING")
        self.assertEqual(service.orders("alice"), [])
        receipt = queue.process_one(service)
        self.assertEqual(receipt["state"], "SUCCEEDED")
        self.assertTrue(service.audit.replay(receipt["result"]["decision_id"])["matches"])
        self.assertEqual(queue.status("command"), receipt)

    def test_low_decimal_context_preserves_recorded_and_replayed_numbers(self):
        service = self.required()
        with localcontext() as context:
            context.prec = 1
            context.traps[Inexact] = context.traps[Rounded] = True
            order = service.submit_order("alice", "order", "BTC-PERP", D(1), D(100))
            fill = service.apply_fill("alice", "order", "fill", D(".3"), D(100))
            for identity in (order["decision_id"], fill["execution_decision_id"]):
                result = service.audit.replay(identity)
                self.assertTrue(result["matches"], result["differences"])
        self.assertEqual(service.account("alice")["balances"]["USD"], "99.98")

    def test_replay_refuses_claims_from_a_different_artifact(self):
        service = self.required()
        order = service.submit_order("alice", "order", "BTC-PERP", D(1), D(100))
        with patch.object(service.audit, "manifest", {"different_runtime": True}):
            with self.assertRaises(DecisionAuditError) as error:
                service.audit.replay(order["decision_id"])
        self.assertEqual(error.exception.code, "audit_artifact_mismatch")


if __name__ == "__main__":
    unittest.main()
