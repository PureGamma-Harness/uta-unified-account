"""Canonical postings catalogue controls; no SQL is executed at import time."""
from decimal import Decimal
import json
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from uta.ledger import LedgerError, Posting
from uta.storage import Database, DurableLedger


class LedgerPostingsCatalogueTests(unittest.TestCase):
    def setUp(self):
        retained = os.environ.get("UTA_LEDGER_CATALOGUE_CASES")
        if retained:
            parent = Path(retained)
            if not parent.is_absolute():
                raise ValueError("retained catalogue cases require an absolute private path")
            self.directory = parent / self._testMethodName
            self.directory.mkdir(parents=True, exist_ok=False, mode=0o700)
        else:
            temporary = TemporaryDirectory(prefix="uta-ledger-catalogue-")
            self.addCleanup(temporary.cleanup)
            self.directory = Path(temporary.name)
        self.path = self.directory / "ledger.sqlite3"
        self.database = Database(self.path)
        self.ledger = DurableLedger(self.database, {"USD": 2})
        self.ledger.post("manual:1", [Posting("a", "USD", Decimal("-12.50")),
                                      Posting("b", "USD", Decimal("12.50"))])
        self.ledger.post("manual:2", [Posting("b", "USD", Decimal("-3.00")),
                                      Posting("c", "USD", Decimal("3.00"))])
        self.original = self.snapshot()
        self.assertEqual(self.original["tables"]["ledger_balances"],
                         [["a", "USD", "-1250"], ["b", "USD", "950"], ["c", "USD", "300"]])

    def snapshot(self, path=None):
        connection = sqlite3.connect((path or self.path).as_uri() + "?mode=ro", uri=True,
                                     isolation_level=None)
        try:
            connection.execute("PRAGMA query_only=ON")
            connection.execute("BEGIN")
            catalogue = [list(row) for row in connection.execute(
                "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")]
            present = {row[1] for row in catalogue if row[0] in {"table", "view"}}
            result = {
                "catalogue": catalogue,
                "tables": {name: ([list(row) for row in connection.execute(
                    'SELECT * FROM "' + name + '" ORDER BY 1,2')] if name in present else None)
                    for name in ("ledger_schema", "ledger_assets", "ledger_events",
                                 "ledger_postings", "ledger_balances")},
                "columns": [list(row) for row in connection.execute("PRAGMA table_xinfo(ledger_postings)")],
                "foreign_keys": [list(row) for row in connection.execute("PRAGMA foreign_key_list(ledger_postings)")],
            }
            connection.rollback()
            return result
        finally:
            connection.close()

    def rebuild(self, change=None, *, kind="table", orphan=False):
        original_sql = next(row[3] for row in self.original["catalogue"]
                            if row[1] == "ledger_postings")
        triggers = [row[3] for row in self.original["catalogue"]
                    if row[0] == "trigger" and row[2] == "ledger_postings"]
        connection = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True,
                                     isolation_level=None)
        try:
            connection.execute("PRAGMA foreign_keys=OFF")
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DROP TABLE ledger_postings")
            if kind == "table":
                statement = change(original_sql)
                self.assertNotEqual(statement, original_sql, "a negative control must actually change its declaration")
                connection.execute(statement)
                connection.executemany(
                    "INSERT INTO ledger_postings(sequence,ordinal,account,asset,units) VALUES(?,?,?,?,?)",
                    self.original["tables"]["ledger_postings"])
                for sql in triggers:
                    connection.execute(sql)
                if orphan:
                    connection.execute("INSERT INTO ledger_postings(sequence,ordinal,account,asset,units) VALUES(99,0,'orphan','USD','1')")
            elif kind == "view":
                connection.execute("CREATE VIEW ledger_postings AS SELECT 1 AS sequence,0 AS ordinal,'a' AS account,'USD' AS asset,'1' AS units WHERE 0")
            elif kind != "missing":
                raise AssertionError("unknown catalogue fixture kind")
            connection.commit()
        finally:
            connection.close()

    def refused_without_repair(self, *, message="journal postings table definition changed"):
        before = self.snapshot()
        for label, call in (("retained_object_verify", self.ledger.verify),
                            ("existing_constructor", lambda: DurableLedger(Database(self.path), {"USD": 2}))):
            with self.subTest(path=label):
                with self.assertRaisesRegex(LedgerError, "^" + message + "$"):
                    call()
                self.assertEqual(self.snapshot(), before, "refusal must not repair catalogue or rows")
        (self.directory / "refusal-state.json").write_text(json.dumps(
            {"expected_error": message, "logical_state_unchanged": True, "state": before}, indent=2) + "\n")
        return before

    def test_lc001_canonical_public_join_reopen_and_backup(self):
        self.assertEqual(self.ledger.verify(), 2)
        with self.database.transaction() as connection:
            self.assertEqual(self.ledger.verify(connection=connection), 2)
        self.assertEqual(DurableLedger(Database(self.path), {"USD": 2}).verify(), 2)
        self.assertEqual(self.snapshot(), self.original)
        backup = self.directory / "canonical-backup.sqlite3"
        descriptor = os.open(backup, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(descriptor)
        source = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True)
        target = sqlite3.connect(backup.as_uri() + "?mode=rw", uri=True)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
        self.assertEqual(DurableLedger(Database(backup), {"USD": 2}).verify(), 2)
        self.assertEqual(self.snapshot(backup), self.original)
        columns = self.original["columns"]
        self.assertEqual([(r[1], r[2], r[3], r[5], r[6]) for r in columns],
                         [("sequence", "INTEGER", 1, 1, 0), ("ordinal", "INTEGER", 1, 2, 0),
                          ("account", "TEXT", 1, 0, 0), ("asset", "TEXT", 1, 0, 0),
                          ("units", "TEXT", 1, 0, 0)])
        self.assertEqual({tuple(r[2:]) for r in self.original["foreign_keys"]},
                         {("ledger_events", "sequence", "sequence", "NO ACTION", "NO ACTION", "NONE"),
                          ("ledger_assets", "asset", "asset", "NO ACTION", "NO ACTION", "NONE")})
        (self.directory / "positive-state.json").write_text(json.dumps(
            {"verified_events": 2, "current": self.snapshot(), "backup": self.snapshot(backup)}, indent=2) + "\n")

    def test_lc002_missing_event_fk_with_orphan_refuses(self):
        self.rebuild(lambda sql: sql.replace("sequence INTEGER NOT NULL REFERENCES ledger_events(sequence)",
                                             "sequence INTEGER NOT NULL"), orphan=True)
        state = self.refused_without_repair()
        self.assertEqual(len(state["foreign_keys"]), 1)
        self.assertIn([99, 0, "orphan", "USD", "1"], state["tables"]["ledger_postings"])

    def test_lc003_missing_asset_fk_refuses(self):
        self.rebuild(lambda sql: sql.replace("asset TEXT NOT NULL REFERENCES ledger_assets(asset)", "asset TEXT NOT NULL"))
        self.assertEqual(len(self.refused_without_repair()["foreign_keys"]), 1)

    def test_lc004_retargeted_event_fk_refuses_before_fk_scan(self):
        self.rebuild(lambda sql: sql.replace("REFERENCES ledger_events(sequence)", "REFERENCES ledger_assets(asset)"))
        state = self.refused_without_repair()
        self.assertTrue(all(row[2] == "ledger_assets" for row in state["foreign_keys"]))

    def test_lc005_missing_composite_pk_refuses(self):
        self.rebuild(lambda sql: sql.replace(",\n        PRIMARY KEY (sequence, ordinal)", ""))
        self.assertTrue(all(row[5] == 0 for row in self.refused_without_repair()["columns"]))

    def test_lc006_reversed_pk_refuses(self):
        self.rebuild(lambda sql: sql.replace("PRIMARY KEY (sequence, ordinal)", "PRIMARY KEY (ordinal, sequence)"))
        state = self.refused_without_repair()
        self.assertEqual([row[5] for row in state["columns"][:2]], [2, 1])

    def test_lc007_nullable_account_refuses(self):
        self.rebuild(lambda sql: sql.replace("account TEXT NOT NULL", "account TEXT"))
        self.assertEqual(self.refused_without_repair()["columns"][2][3], 0)

    def test_lc008_units_type_drift_refuses(self):
        self.rebuild(lambda sql: sql.replace("units TEXT NOT NULL", "units INTEGER NOT NULL"))
        self.assertEqual(self.refused_without_repair()["columns"][4][2], "INTEGER")

    def test_lc009_missing_ordinal_check_refuses(self):
        self.rebuild(lambda sql: sql.replace(" CHECK (ordinal >= 0)", ""))
        state = self.refused_without_repair()
        self.assertNotIn("CHECK", next(row[3] for row in state["catalogue"] if row[1] == "ledger_postings"))

    def test_lc010_extra_ordinary_column_refuses(self):
        self.rebuild(lambda sql: sql.replace("PRIMARY KEY (sequence, ordinal))", "extra TEXT, PRIMARY KEY (sequence, ordinal))"))
        self.assertEqual(len(self.refused_without_repair()["columns"]), 6)

    def test_lc011_extra_generated_column_refuses(self):
        self.rebuild(lambda sql: sql.replace("PRIMARY KEY (sequence, ordinal))",
                                             "extra TEXT GENERATED ALWAYS AS (account) VIRTUAL, PRIMARY KEY (sequence, ordinal))"))
        state = self.refused_without_repair()
        self.assertEqual(len(state["columns"]), 6)
        self.assertEqual(state["columns"][5][6], 2)

    def test_lc012_view_substitution_refuses_before_trigger_access(self):
        self.rebuild(kind="view")
        state = self.refused_without_repair()
        self.assertEqual(next(row[0] for row in state["catalogue"] if row[1] == "ledger_postings"), "view")

    def test_lc013_missing_postings_table_is_not_recreated(self):
        self.rebuild(kind="missing")
        state = self.refused_without_repair(message="journal postings table is missing")
        self.assertIsNone(state["tables"]["ledger_postings"])

    def test_lc014_missing_original_trigger_still_refuses(self):
        with self.database.transaction() as connection:
            connection.execute("DROP TRIGGER ledger_postings_no_update")
        self.refused_without_repair(message="journal protection trigger is missing")

    def test_lc015_changed_original_trigger_still_refuses(self):
        original = next(row[3] for row in self.original["catalogue"] if row[1] == "ledger_postings_no_update")
        with self.database.transaction() as connection:
            connection.execute("DROP TRIGGER ledger_postings_no_update")
            changed = original.replace("'journal is immutable'", "'changed synthetic trigger'")
            self.assertNotEqual(changed, original)
            connection.execute(changed)
        self.refused_without_repair(message="journal protection trigger definition changed")

    def test_lc016_managed_extension_guards_keep_their_native_boundary(self):
        from uta.writer_fence import WriterFence
        fence = WriterFence(self.database)
        fence.enable("synthetic-ledger-catalogue")
        token = fence.acquire("catalogue-owner", 5)
        try:
            bound = DurableLedger(self.database.for_writer(token), {"USD": 2})
            self.assertEqual(bound.verify(), 2)
            rows = self.snapshot()["catalogue"]
            self.assertTrue(any(row[0] == "trigger" and row[2] == "ledger_postings"
                                and row[1].startswith("writer_fence_data_") for row in rows))
            self.assertEqual(self.snapshot()["tables"], self.original["tables"])
            # Only base-ledger rows are serialized; control/owner/token rows stay private.
            (self.directory / "positive-state.json").write_text(json.dumps(
                {"verified_events": 2, "current": self.snapshot()}, indent=2) + "\n")
        finally:
            fence.release(token)


if __name__ == "__main__":
    unittest.main()
