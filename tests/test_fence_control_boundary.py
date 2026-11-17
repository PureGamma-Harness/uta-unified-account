"""Independent control-role denial and financial-conservation regression.

All added triggers contain SELECT 1 only. No projection-writing payload or
external target is constructed; every database contains synthetic balances.
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal as D
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from uta.matching import Matcher
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ExchangeService
from uta.storage import Database
from uta.writer_fence import WriterFence, WriterFenceError


NOW = datetime(2026, 11, 16, tzinfo=timezone.utc)


def stored(path, *, financial_only=False):
    with closing(sqlite3.connect(Path(path).as_uri() + "?mode=ro", uri=True)) as connection:
        definitions = connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
        if financial_only:
            definitions = [row for row in definitions if not row[1].startswith("writer_fence_")]
        tables = [row[1] for row in definitions if row[0] == "table"]
        return definitions, {name: sorted(connection.execute('SELECT * FROM "' + name + '"').fetchall(), key=repr)
                             for name in tables}


class ControlBoundaryTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "control.sqlite3"
        self.tick = 1_000_000_000
        self.database = Database(self.path, fence_clock_ns=lambda: self.tick,
                                 fence_boot_id="independent-control-boot")
        self.service = self.open(self.database)
        for account in ("alice", "bob"):
            self.service.create_account(account)
            self.service.deposit(account, "seed", "USD", D(1000))
        self.service.publish_market(MarketSnapshot(1, NOW, {"USD": AssetSpec(D(1), D(1))},
            {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))}))
        self.service.set_kill_switch(False)
        self.matcher = Matcher(self.service)
        self.fence = WriterFence(self.database)

    @staticmethod
    def open(database):
        return ExchangeService(database, {"USD": 8}, clock=lambda: NOW)

    def enable(self):
        return self.fence.enable("independent-control-authority")

    def assert_control_rejected(self, statement):
        before = stored(self.path)
        executed, error = False, None
        try:
            with self.database._fence_transaction() as connection:
                connection.execute(statement)
                executed = True
        except WriterFenceError as caught:
            error = caught
        self.assertFalse(executed, f"control role executed unexpected statement: {statement}")
        self.assertIsNotNone(error, f"control role accepted unexpected statement: {statement}")
        self.assertEqual(error.code, "writer_fenced")
        self.assertEqual(stored(self.path), before)

    def test_control_role_cannot_create_any_additional_main_or_temporary_schema_objects(self):
        self.enable()
        statements = (
            "CREATE TABLE writer_fence_extra (marker INTEGER)",
            "CREATE TABLE unrelated_extra (marker INTEGER)",
            "CREATE INDEX writer_fence_extra_index ON writer_fence_events(kind)",
            "CREATE VIEW writer_fence_extra_view AS SELECT 1 AS marker",
            "CREATE TEMP TABLE writer_fence_extra_temp (marker INTEGER)",
            "CREATE TEMP VIEW writer_fence_extra_temp_view AS SELECT 1 AS marker",
            "CREATE TRIGGER writer_fence_extra AFTER UPDATE ON writer_fence_lease BEGIN SELECT 1; END",
            "CREATE TRIGGER unrelated_extra AFTER UPDATE ON writer_fence_lease BEGIN SELECT 1; END",
            "CREATE TEMP TRIGGER writer_fence_extra_temp_trigger AFTER UPDATE ON main.writer_fence_lease BEGIN SELECT 1; END",
        )
        for statement in statements:
            with self.subTest(statement=statement):
                self.assert_control_rejected(statement)

    def test_control_role_cannot_rewrite_official_schema_or_financial_projections(self):
        self.enable()
        statements = (
            "DROP TRIGGER writer_fence_lease_no_delete",
            "ALTER TABLE writer_fence_lease ADD COLUMN unexpected INTEGER",
            "DROP TABLE writer_fence_guard_tables",
            "CREATE TABLE IF NOT EXISTS writer_fence_lease (unexpected INTEGER)",
            "UPDATE ledger_balances SET units='0'",
            "UPDATE uta_accounts SET version=version+1",
            "INSERT INTO uta_positions VALUES ('alice','BTC-PERP','1','100')",
            "PRAGMA writable_schema=ON",
        )
        for statement in statements:
            with self.subTest(statement=statement):
                self.assert_control_rejected(statement)

    def test_swallowed_ddl_denial_does_not_commit_following_control_dml(self):
        self.enable()
        before = stored(self.path)
        with self.assertRaises(WriterFenceError):
            with self.database._fence_transaction() as connection:
                try:
                    connection.execute("CREATE TRIGGER writer_fence_extra AFTER UPDATE ON writer_fence_lease BEGIN SELECT 1; END")
                except sqlite3.DatabaseError:
                    pass
                connection.execute("UPDATE writer_fence_lease SET observed_ns=observed_ns+1")
        self.assertEqual(stored(self.path), before)

    def test_unknown_attached_control_triggers_reject_at_begin_without_repair(self):
        self.enable()
        token = self.fence.acquire("valid-worker", 30)
        tables = ("writer_fence_authority", "writer_fence_lease", "writer_fence_events",
                  "writer_fence_guard_config", "writer_fence_guard_tables")
        for index, table in enumerate(tables):
            name = "independent_unknown_observer_" + str(index)
            with self.subTest(table=table):
                with closing(sqlite3.connect(self.path)) as raw, raw:
                    raw.execute(f"CREATE TRIGGER {name} AFTER UPDATE ON {table} BEGIN SELECT 1; END")
                before = stored(self.path)
                for role in ("financial", "control", "read", "inbox"):
                    with self.subTest(role=role):
                        entered, error = False, None
                        try:
                            transaction = {"financial": self.database.for_writer(token).transaction,
                                           "control": self.database._fence_transaction,
                                           "read": self.database.read_transaction,
                                           "inbox": self.database.inbox_transaction}[role]
                            with transaction():
                                entered = True
                        except WriterFenceError as caught:
                            error = caught
                        self.assertIsNotNone(error, "unknown control trigger was accepted")
                        self.assertEqual(error.code, "fence_control_corrupt")
                        self.assertFalse(entered, "unknown control trigger reached caller transaction body")
                        self.assertEqual(stored(self.path), before)
                with closing(sqlite3.connect(self.path)) as raw, raw:
                    self.assertIsNotNone(raw.execute("SELECT name FROM sqlite_master WHERE name=?", (name,)).fetchone())
                    raw.execute("DROP TRIGGER " + name)

    def test_weakened_official_control_trigger_and_extra_index_are_corruption_without_repair(self):
        self.enable()
        for defect in ("weakened_trigger", "extra_index"):
            with self.subTest(defect=defect):
                with closing(sqlite3.connect(self.path)) as raw, raw:
                    original, = raw.execute("SELECT sql FROM sqlite_master WHERE name='writer_fence_lease_monotonic'").fetchone()
                    if defect == "weakened_trigger":
                        raw.execute("DROP TRIGGER writer_fence_lease_monotonic")
                        raw.execute("CREATE TRIGGER writer_fence_lease_monotonic BEFORE UPDATE ON writer_fence_lease BEGIN SELECT 1; END")
                    else:
                        raw.execute("CREATE INDEX independent_control_index ON writer_fence_events(kind)")
                before = stored(self.path)
                for operation in (self.fence.status, self.fence.upgrade_guards,
                                  lambda: self.fence.enable("independent-control-authority")):
                    with self.assertRaises(WriterFenceError) as caught:
                        operation()
                    self.assertEqual(caught.exception.code, "fence_control_corrupt")
                    self.assertEqual(stored(self.path), before)
                with closing(sqlite3.connect(self.path)) as raw, raw:
                    if defect == "weakened_trigger":
                        raw.execute("DROP TRIGGER writer_fence_lease_monotonic")
                        raw.execute(original)
                    else:
                        raw.execute("DROP INDEX independent_control_index")

    def test_changed_official_control_table_definition_is_rejected_before_any_caller_sql(self):
        self.enable()
        with closing(sqlite3.connect(self.path)) as raw, raw:
            raw.execute("ALTER TABLE writer_fence_lease ADD COLUMN unexpected INTEGER")
        before = stored(self.path)
        entered = False
        with self.assertRaises(WriterFenceError) as caught:
            with self.database._fence_transaction():
                entered = True
        self.assertEqual(caught.exception.code, "fence_control_corrupt")
        self.assertFalse(entered)
        for operation in (self.fence.status, self.fence.upgrade_guards,
                          lambda: self.fence.enable("independent-control-authority")):
            with self.assertRaises(WriterFenceError) as caught:
                operation()
            self.assertEqual(caught.exception.code, "fence_control_corrupt")
            self.assertEqual(stored(self.path), before)

    def test_legal_lease_lifecycle_preserves_finance_and_real_matching_remains_durable(self):
        self.service.submit_order("alice", "buy", "BTC-PERP", D(1), D(100))
        self.service.submit_order("bob", "sell", "BTC-PERP", D(-1), D(100))
        before = stored(self.path, financial_only=True)
        status = self.enable()
        self.assertEqual(status["guard_format"], 1)
        token = self.fence.acquire("first", 30)
        self.tick += 100_000_000
        self.fence.renew(token, 30)
        self.assertEqual(stored(self.path, financial_only=True), before)
        self.fence.release(token)
        self.assertFalse(self.fence.status()["active"])
        next_token = self.fence.acquire("second", 30)
        self.assertGreater(next_token.generation, token.generation)
        current = self.open(self.database.for_writer(next_token))
        matcher = Matcher(current)
        matcher.match_once("BTC-PERP")
        self.assertEqual(len(matcher.trades()), 1)
        self.assertEqual(current.account("alice")["balances"]["USD"], "999.96")
        self.assertEqual(current.account("bob")["balances"]["USD"], "999.96")
        self.assertEqual(current.ledger.balance("system:fees", "USD"), D(".08"))
        matcher.verify(strict=True)
        current.ledger.verify()
        self.fence.release(next_token)
        reopened_token = self.fence.acquire("reopened", 30)
        reopened = self.open(self.database.for_writer(reopened_token))
        self.assertEqual(len(Matcher(reopened).trades()), 1)
        reopened.ledger.verify()

    def test_complete_published_format_zero_schema_upgrades_offline_without_financial_changes(self):
        # Exact first managed schema from c05e10f, including all SIX protections.
        with closing(sqlite3.connect(self.path)) as raw, raw:
            raw.execute("CREATE TABLE writer_fence_authority (singleton INTEGER PRIMARY KEY CHECK(singleton=1),format INTEGER NOT NULL CHECK(format=1),authority_id TEXT NOT NULL,canonical_path TEXT NOT NULL)")
            raw.execute("CREATE TABLE writer_fence_lease (singleton INTEGER PRIMARY KEY CHECK(singleton=1),generation INTEGER NOT NULL CHECK(generation>=0),owner_nonce TEXT,owner_pid INTEGER,boot_id TEXT NOT NULL,expires_ns INTEGER NOT NULL,observed_ns INTEGER NOT NULL)")
            raw.execute("CREATE TABLE writer_fence_events (sequence INTEGER PRIMARY KEY,kind TEXT NOT NULL,authority_id TEXT NOT NULL,owner_nonce TEXT,generation INTEGER NOT NULL,owner_pid INTEGER,boot_id TEXT NOT NULL,observed_ns INTEGER NOT NULL,expires_ns INTEGER NOT NULL)")
            raw.execute("INSERT INTO writer_fence_authority VALUES (1,1,?,?)", ("independent-control-authority", str(self.path)))
            raw.execute("INSERT INTO writer_fence_lease VALUES (1,0,NULL,NULL,'independent-control-boot',1000000000,1000000000)")
            raw.execute("INSERT INTO writer_fence_events VALUES (1,'enabled','independent-control-authority',NULL,0,NULL,'independent-control-boot',1000000000,1000000000)")
            for table in ("writer_fence_authority", "writer_fence_events"):
                for action in ("UPDATE", "DELETE"):
                    raw.execute(f"CREATE TRIGGER {table}_no_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'fence authority and audit are immutable'); END")
            raw.execute("CREATE TRIGGER writer_fence_lease_no_delete BEFORE DELETE ON writer_fence_lease BEGIN SELECT RAISE(ABORT,'managed lease cannot be deleted'); END")
            raw.execute("CREATE TRIGGER writer_fence_lease_monotonic BEFORE UPDATE ON writer_fence_lease WHEN NEW.generation<OLD.generation BEGIN SELECT RAISE(ABORT,'fence generation cannot regress'); END")
            self.assertEqual(raw.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='trigger' AND tbl_name IN ('writer_fence_authority','writer_fence_lease','writer_fence_events')").fetchone()[0], 6)
        before = stored(self.path, financial_only=True)
        self.assertEqual(self.fence.status()["guard_format"], 0)
        with self.assertRaises(WriterFenceError) as caught:
            self.fence.acquire("before-upgrade", 30)
        self.assertEqual(caught.exception.code, "fence_upgrade_required")
        self.fence.upgrade_guards()
        self.assertEqual(self.fence.status()["guard_format"], 1)
        self.assertEqual(stored(self.path, financial_only=True), before)
        token = self.fence.acquire("after-upgrade", 30)
        current = self.open(self.database.for_writer(token))
        current.deposit("alice", "after-explicit-upgrade", "USD", D(1))
        self.assertEqual(current.account("alice")["balances"]["USD"], "1001")
        current.ledger.verify()


if __name__ == "__main__":
    unittest.main()
