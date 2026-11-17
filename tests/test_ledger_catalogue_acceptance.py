"""Independent synthetic controls. Importing this module performs no SQL."""
from contextlib import closing
from decimal import Decimal
import json
import os
from pathlib import Path
import re
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from uta.ledger import LedgerError, Posting
from uta.ops import backup_database
from uta.storage import Database, DurableLedger, StorageError
from uta.writer_fence import WriterFence, WriterFenceError


BASE_TABLES = ("ledger_schema", "ledger_assets", "ledger_events", "ledger_postings", "ledger_balances")
CHANGED = "journal postings table definition changed"


class TracedDatabase(Database):
    def _connect(self):
        connection = super()._connect()
        connection.set_trace_callback(self.trace.append)
        return connection


class IndependentCatalogueAcceptance(unittest.TestCase):
    def setUp(self):
        retained = os.environ.get("UTA_LEDGER_ACCEPTANCE_CASES")
        if retained:
            root = Path(retained)
            if not root.is_absolute():
                raise ValueError("retained acceptance cases require an absolute path")
        else:
            temporary = TemporaryDirectory(prefix="uta-independent-catalogue-")
            self.addCleanup(temporary.cleanup)
            root = Path(temporary.name)
        self.directory = root / self._testMethodName
        self.directory.mkdir(parents=True, mode=0o700, exist_ok=False)
        self.path = self.directory / "synthetic.sqlite3"
        self.database = TracedDatabase(self.path, timeout=1)
        self.database.trace = []
        self.ledger = DurableLedger(self.database, {"USD": 2})
        self.ledger.post("independent:1", self.postings("a", "b", "2.50"))
        self.ledger.post("independent:2", self.postings("b", "c", "0.25"))
        self.original = self.snapshot()
        self.assertEqual(self.original["rows"]["ledger_balances"],
                         [["a", "USD", "-250"], ["b", "USD", "225"], ["c", "USD", "25"]])

    @staticmethod
    def postings(source, target, amount):
        value = Decimal(amount)
        return [Posting(source, "USD", -value), Posting(target, "USD", value)]

    def raw(self, *, readonly=False):
        connection = sqlite3.connect(self.path.as_uri() + ("?mode=ro" if readonly else "?mode=rw"),
                                     uri=True, isolation_level=None, timeout=1)
        connection.row_factory = sqlite3.Row
        return connection

    def record(self, name, value):
        (self.directory / (name + ".json")).write_text(json.dumps(value, indent=2) + "\n")

    def snapshot(self):
        with closing(self.raw(readonly=True)) as connection:
            connection.execute("BEGIN")
            catalogue = [list(row) for row in connection.execute(
                "SELECT type,name,tbl_name,sql FROM main.sqlite_master ORDER BY type,name")]
            present = {row[1] for row in catalogue if row[0] in ("table", "view")}
            rows = {name: [list(row) for row in connection.execute(
                'SELECT * FROM main."' + name + '" ORDER BY 1,2')] if name in present else None
                for name in BASE_TABLES}
            return {"catalogue": catalogue, "rows": rows,
                    "columns": [list(row) for row in connection.execute("PRAGMA main.table_xinfo(ledger_postings)")],
                    "foreign_keys": [list(row) for row in connection.execute("PRAGMA main.foreign_key_list(ledger_postings)")]}

    def rebuild(self, change=None, *, kind="table", orphan=False):
        sql = next(row[3] for row in self.original["catalogue"] if row[1] == "ledger_postings")
        triggers = [row[3] for row in self.original["catalogue"]
                    if row[0] == "trigger" and row[2] == "ledger_postings"]
        with closing(self.raw()) as connection:
            connection.execute("PRAGMA foreign_keys=OFF")
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DROP TABLE main.ledger_postings")
            if kind == "table":
                changed = change(sql)
                self.assertNotEqual(changed, sql)
                connection.execute(changed)
                connection.executemany("INSERT INTO main.ledger_postings(sequence,ordinal,account,asset,units) VALUES(?,?,?,?,?)",
                                       self.original["rows"]["ledger_postings"])
                for trigger in triggers:
                    connection.execute(trigger)
                if orphan:
                    connection.execute("INSERT INTO main.ledger_postings VALUES(99,0,'independent-orphan','USD','1')")
            elif kind == "view":
                connection.execute("CREATE VIEW ledger_postings AS SELECT 1 sequence,0 ordinal,'a' account,'USD' asset,'1' units WHERE 0")
            else:
                self.assertEqual(kind, "missing")
            connection.commit()

    def assert_refused(self, message=CHANGED):
        before = self.snapshot()
        traces = {}
        for label, call in (("retained_verify", self.ledger.verify),
                            ("existing_constructor", lambda: DurableLedger(self.database, {"USD": 2}))):
            self.database.trace.clear()
            with self.assertRaisesRegex(LedgerError, "^" + re.escape(message) + "$"):
                call()
            traces[label] = list(self.database.trace)
            self.assertFalse(any(re.match(r"\s*(CREATE|DROP|ALTER|INSERT|UPDATE|DELETE|REPLACE|REINDEX|VACUUM)\b", sql, re.I)
                                 for sql in self.database.trace), self.database.trace)
            self.assertEqual(self.snapshot(), before)
        self.record("refusal", {"message": message, "unchanged_main_state": before, "traces": traces})

    def test_01_canonical_real_supported_backup_and_exact_metadata(self):
        self.assertEqual(self.ledger.verify(), 2)
        backup = self.directory / "supported-backup.sqlite3"
        metadata = backup_database(self.path, backup, timeout=1)
        self.assertEqual(DurableLedger(Database(backup, timeout=1), {"USD": 2}).verify(), 2)
        with closing(sqlite3.connect(backup.as_uri() + "?mode=ro", uri=True)) as connection:
            backed_sql = connection.execute("SELECT sql FROM main.sqlite_master WHERE name='ledger_postings'").fetchone()[0]
        canonical = next(row[3] for row in self.original["catalogue"] if row[1] == "ledger_postings")
        self.assertEqual(backed_sql, canonical)
        self.assertEqual([(row[1], row[2], row[3], row[5], row[6]) for row in self.original["columns"]],
                         [("sequence", "INTEGER", 1, 1, 0), ("ordinal", "INTEGER", 1, 2, 0),
                          ("account", "TEXT", 1, 0, 0), ("asset", "TEXT", 1, 0, 0), ("units", "TEXT", 1, 0, 0)])
        self.assertEqual({tuple(row[2:]) for row in self.original["foreign_keys"]},
                         {("ledger_events", "sequence", "sequence", "NO ACTION", "NO ACTION", "NONE"),
                          ("ledger_assets", "asset", "asset", "NO ACTION", "NO ACTION", "NONE")})
        self.assertEqual(self.snapshot(), self.original)
        self.record("positive", {"events": 2, "canonical_sql": canonical, "backup_metadata": metadata})

    def test_02_original_missing_event_fk_with_orphan_no_ddl(self):
        self.rebuild(lambda sql: sql.replace(" REFERENCES ledger_events(sequence)", ""), orphan=True)
        self.assertEqual(len(self.snapshot()["foreign_keys"]), 1)
        self.assertIn([99, 0, "independent-orphan", "USD", "1"], self.snapshot()["rows"]["ledger_postings"])
        self.assert_refused()

    def test_03_missing_asset_fk_no_ddl(self):
        self.rebuild(lambda sql: sql.replace(" REFERENCES ledger_assets(asset)", ""))
        self.assert_refused()

    def test_04_wrong_fk_target_has_typed_error_before_sqlite_fk_scan(self):
        self.rebuild(lambda sql: sql.replace("REFERENCES ledger_events(sequence)", "REFERENCES missing_parent(id)"))
        self.assert_refused()

    def test_05_missing_pk_no_ddl(self):
        self.rebuild(lambda sql: sql.replace(",\n        PRIMARY KEY (sequence, ordinal)", ""))
        self.assert_refused()

    def test_06_nullable_column_no_ddl(self):
        self.rebuild(lambda sql: sql.replace("account TEXT NOT NULL", "account TEXT"))
        self.assert_refused()

    def test_07_hidden_generated_column_no_ddl(self):
        self.rebuild(lambda sql: sql.replace("PRIMARY KEY (sequence, ordinal))",
                    "extra TEXT GENERATED ALWAYS AS (account) VIRTUAL, PRIMARY KEY (sequence, ordinal))"))
        self.assert_refused()

    def test_08_missing_check_no_ddl(self):
        self.rebuild(lambda sql: sql.replace(" CHECK (ordinal >= 0)", ""))
        self.assert_refused()

    def test_09_view_substitution_no_ddl(self):
        self.rebuild(kind="view")
        self.assert_refused()

    def test_10_missing_table_no_ddl(self):
        self.rebuild(kind="missing")
        self.assert_refused("journal postings table is missing")

    def test_11_semantically_equivalent_whitespace_is_deliberately_rejected(self):
        self.rebuild(lambda sql: sql.replace("account TEXT NOT NULL", "account  TEXT NOT NULL"))
        self.assertEqual(self.snapshot()["columns"], self.original["columns"])
        self.assertEqual(self.snapshot()["foreign_keys"], self.original["foreign_keys"])
        self.assert_refused()

    def test_12_joined_bad_catalogue_keeps_callers_transaction_active(self):
        self.rebuild(lambda sql: sql.replace(" REFERENCES ledger_events(sequence)", ""), orphan=True)
        before = self.snapshot()
        with closing(self.raw()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("CREATE TABLE independent_marker(value TEXT)")
            connection.execute("INSERT INTO independent_marker VALUES('outer-still-active')")
            trace = []
            connection.set_trace_callback(trace.append)
            with self.assertRaisesRegex(LedgerError, "^" + CHANGED + "$"):
                self.ledger.verify(connection=connection)
            self.assertTrue(connection.in_transaction)
            self.assertEqual(connection.execute("SELECT value FROM independent_marker").fetchone()[0], "outer-still-active")
            self.assertFalse(any(re.match(r"\s*(COMMIT|ROLLBACK|CREATE|DROP|ALTER|INSERT|UPDATE|DELETE)\b", sql, re.I) for sql in trace))
            verification_trace = list(trace)
            connection.rollback()
        self.assertEqual(self.snapshot(), before)
        self.record("joined", {"caller_transaction_preserved": True, "trace_before_caller_rollback": verification_trace, "state": before})

    def test_13_joined_canonical_post_and_verify_are_rolled_back_by_caller(self):
        with self.database.transaction() as connection:
            self.assertEqual(self.ledger.verify(connection=connection), 2)
        with closing(self.raw()) as connection:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("BEGIN IMMEDIATE")
            self.ledger.post("independent:rolled-back", self.postings("a", "b", "1.00"), connection=connection)
            self.assertEqual(self.ledger.verify(connection=connection), 3)
            self.assertTrue(connection.in_transaction)
            connection.rollback()
        self.assertEqual(self.ledger.verify(), 2)
        self.assertEqual(self.snapshot(), self.original)
        self.record("joined", {"joined_events": 3, "after_caller_rollback": 2, "state": self.original})

    def test_14_constructor_version_error_precedes_catalogue_error(self):
        self.rebuild(lambda sql: sql.replace(" REFERENCES ledger_events(sequence)", ""))
        with closing(self.raw()) as connection:
            connection.execute("UPDATE main.ledger_schema SET version=99")
        before = self.snapshot()
        self.database.trace.clear()
        with self.assertRaisesRegex(StorageError, "^unsupported ledger schema version: 99$"):
            DurableLedger(self.database, {"USD": 2})
        self.assertFalse(any(re.match(r"\s*(CREATE|DROP|ALTER|INSERT|UPDATE|DELETE)\b", sql, re.I) for sql in self.database.trace))
        with self.assertRaisesRegex(LedgerError, "^" + CHANGED + "$"):
            self.ledger.verify()
        self.assertEqual(self.snapshot(), before)
        self.record("precedence", {"constructor": "unsupported ledger schema version: 99", "verify": CHANGED, "state": before})

    def test_15_new_catalogue_error_precedes_original_trigger_error(self):
        self.rebuild(lambda sql: sql.replace(" REFERENCES ledger_events(sequence)", ""))
        with closing(self.raw()) as connection:
            connection.execute("DROP TRIGGER main.ledger_postings_no_update")
        self.assert_refused()

    def test_16_main_bad_definition_cannot_be_hidden_by_canonical_temp_table(self):
        self.rebuild(lambda sql: sql.replace(" REFERENCES ledger_events(sequence)", ""), orphan=True)
        with closing(self.raw()) as connection:
            canonical = next(row[3] for row in self.original["catalogue"] if row[1] == "ledger_postings")
            connection.execute(canonical.replace("CREATE TABLE ledger_postings", "CREATE TEMP TABLE ledger_postings", 1))
            connection.executemany("INSERT INTO temp.ledger_postings VALUES(?,?,?,?,?)", self.original["rows"]["ledger_postings"])
            connection.execute("BEGIN")
            with self.assertRaisesRegex(LedgerError, "^" + CHANGED + "$"):
                self.ledger.verify(connection=connection)
            self.assertTrue(connection.in_transaction)
        self.record("main_guard", {"malformed_main_refused_despite_canonical_temp": True})

    def test_17_scope_observation_unmanaged_temp_shadow_is_not_validated(self):
        with closing(self.raw()) as connection:
            connection.execute("CREATE TEMP TABLE ledger_postings(sequence,ordinal,account,asset,units)")
            connection.executemany("INSERT INTO temp.ledger_postings VALUES(?,?,?,?,?)", self.original["rows"]["ledger_postings"])
            connection.execute("INSERT INTO temp.ledger_postings VALUES(99,0,'temp-orphan','USD','1')")
            connection.execute("BEGIN")
            # A positive observation of the legacy raw-join boundary, NOT a
            # claim that the effective TEMP catalogue has passed validation.
            actual = self.ledger.verify(connection=connection)
            self.assertEqual(actual, 2)
            self.assertEqual(connection.execute("SELECT count(*) FROM temp.ledger_postings").fetchone()[0], 5)
            self.assertEqual(connection.execute("PRAGMA temp.foreign_key_list(ledger_postings)").fetchall(), [])
            self.assertTrue(connection.in_transaction)
        self.assertEqual(self.snapshot(), self.original)
        self.record("scope-gap", {"main_canonical": True, "temp_has_no_fk_or_pk": True,
                    "temp_posting_rows": 5, "temp_orphan_sequence": 99, "returned_events": actual,
                    "independent_acceptance": "ROOT_MUST_REVIEW_RAW_UNMANAGED_TEMP_BOUNDARY"})

    def test_18_real_managed_guards_and_raw_join_boundary(self):
        clock = [10_000_000_000]
        database = Database(self.path, timeout=1, fence_clock_ns=lambda: clock[0], fence_boot_id="independent-test")
        fence = WriterFence(database)
        fence.enable("independent-synthetic-authority")
        token = fence.acquire("independent-owner", 2)
        try:
            bound_database = database.for_writer(token)
            bound = DurableLedger(bound_database, {"USD": 2})
            self.assertEqual(bound.verify(), 2)
            with bound_database.read_transaction() as connection:
                self.assertEqual(bound.verify(connection=connection), 2)
            with closing(self.raw()) as connection:
                connection.execute("BEGIN")
                with self.assertRaises(WriterFenceError) as error:
                    bound.verify(connection=connection)
                self.assertEqual(error.exception.code, "unguarded_connection")
                self.assertTrue(connection.in_transaction)
            rows = self.snapshot()
            self.assertEqual(rows["rows"], self.original["rows"])
            self.assertTrue(any(row[0] == "trigger" and row[2] == "ledger_postings" and row[1].startswith("writer_fence_data_")
                                for row in rows["catalogue"]))
            self.record("managed", {"verified_events": 2, "raw_join_error": "unguarded_connection", "base_state": rows})
        finally:
            fence.release(token)


if __name__ == "__main__":
    unittest.main()
