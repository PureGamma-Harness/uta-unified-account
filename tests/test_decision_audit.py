"""Append-only evidence and reconstruction tests using synthetic accounts."""
from datetime import datetime, timezone
from decimal import Decimal as D
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from uta.decision_audit import DecisionAudit, DecisionAuditError
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ExchangeService
from uta.storage import Database


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


if __name__ == "__main__":
    unittest.main()
