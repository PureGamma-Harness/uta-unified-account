"""Verify MAIN identity on real raw joins; no SQL executes at import time."""
from decimal import Decimal
import json
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from uta.ledger import LedgerError, Posting
from uta.storage import Database, DurableLedger, StorageError


TABLES = ("ledger_schema", "ledger_assets", "ledger_events", "ledger_postings", "ledger_balances")


class LedgerMainSchemaTests(unittest.TestCase):
    def setUp(self):
        retained = os.environ.get("UTA_LEDGER_MAIN_SCHEMA_CASES")
        if retained:
            parent = Path(retained)
            if not parent.is_absolute():
                raise ValueError("retained MAIN cases require an absolute private path")
            self.directory = parent / self._testMethodName
            self.directory.mkdir(mode=0o700, parents=True, exist_ok=False)
        else:
            temporary = TemporaryDirectory(prefix="uta-ledger-main-")
            self.addCleanup(temporary.cleanup)
            self.directory = Path(temporary.name)
        self.path = self.directory / "main.sqlite3"
        self.database = Database(self.path)
        self.ledger = DurableLedger(self.database, {"USD": 2})
        self.ledger.post("manual:1", [Posting("a", "USD", Decimal("-12.50")), Posting("b", "USD", Decimal("12.50"))])
        self.ledger.post("manual:2", [Posting("b", "USD", Decimal("-3.00")), Posting("c", "USD", Decimal("3.00"))])
        raw = self.raw()
        self.good = self.snapshot(raw, "main")
        raw.close()
        self.assertEqual(self.good["tables"]["ledger_balances"],
                         [["a", "USD", "-1250"], ["b", "USD", "950"], ["c", "USD", "300"]])
        self.assertEqual([row[4] for row in self.good["tables"]["ledger_events"]],
                         ["f0201ec2d6f7eaa23b3872bb381810108b5e4a4ef0ac1eae07d7573a534deab6",
                          "afe93ccca88c18e947e5bb4c62d8422da53bff3445986888a3a772ec82137d8c"])

    def raw(self):
        connection = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, isolation_level=None)
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @staticmethod
    def snapshot(connection, schema):
        assert schema in {"main", "temp"}
        present = {row[0] for row in connection.execute('SELECT name FROM ' + schema + '.sqlite_master')}
        return {"tables": {name: ([list(row) for row in connection.execute(
                    'SELECT * FROM ' + schema + '."' + name + '" ORDER BY 1,2')] if name in present else None)
                    for name in TABLES},
                "catalogue": [list(row) for row in connection.execute(
                    'SELECT type,name,tbl_name,sql FROM ' + schema + '.sqlite_master ORDER BY type,name')]}

    def temp_copy(self):
        connection = self.raw()
        connection.execute("BEGIN")
        for name in TABLES:
            connection.execute('CREATE TEMP TABLE "' + name + '" AS SELECT * FROM main."' + name + '"')
        self.assertEqual(self.snapshot(connection, "temp")["tables"], self.good["tables"])
        connection.commit()
        return connection

    def mutate_main(self, table, sql, params=(), *, trigger=None):
        connection = self.raw()
        try:
            connection.execute("BEGIN IMMEDIATE")
            if trigger:
                definition = next(row[3] for row in self.good["catalogue"] if row[1] == trigger)
                connection.execute('DROP TRIGGER main."' + trigger + '"')
            connection.execute(sql, params)
            if trigger:
                connection.execute(definition)
            connection.commit()
            self.assertEqual(self.snapshot(connection, "main")["catalogue"], self.good["catalogue"])
        finally:
            connection.close()

    def joined(self, connection, *, error=None, message=None, deny_temp=False, code=None):
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        before_main, before_temp = self.snapshot(connection, "main"), self.snapshot(connection, "temp")
        reads, denied = [], []
        def authorizer(action, first, second, database, source):
            if action == sqlite3.SQLITE_READ:
                reads.append([first, second, database])
                if database == "temp":
                    denied.append([first, second, database])
                    return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        if deny_temp:
            connection.set_authorizer(authorizer)
        try:
            if error is None:
                self.assertEqual(self.ledger.verify(connection=connection), 2)
                observed = {"returned": 2, "error_type": None, "code": None}
            else:
                with self.assertRaisesRegex(error, message) as caught:
                    self.ledger.verify(connection=connection)
                if code is not None:
                    self.assertEqual(caught.exception.code, code)
                observed = {"returned": None, "error_type": type(caught.exception).__name__,
                            "code": getattr(caught.exception, "code", None), "error_message": str(caught.exception)}
        finally:
            if deny_temp:
                connection.set_authorizer(None)
        self.assertTrue(connection.in_transaction)
        self.assertEqual(self.snapshot(connection, "main"), before_main)
        self.assertEqual(self.snapshot(connection, "temp"), before_temp)
        if deny_temp:
            self.assertEqual(denied, [])
            self.assertTrue(reads)
            self.assertTrue(all(row[2] == "main" for row in reads))
        connection.rollback()
        (self.directory / "joined-state.json").write_text(json.dumps(
            {"observed": observed, "caller_transaction_remained_active": True,
             "main_unchanged": True, "temp_unchanged": True, "main": before_main, "temp": before_temp,
             "actual_sqlite_authorizer_reads": reads, "denied_temp_reads": denied}, indent=2) + "\n")

    def test_ms001_healthy_main_raw_join_without_temp(self):
        connection = self.raw()
        try:
            self.joined(connection)
        finally:
            connection.close()

    def test_ms002_healthy_temp_copies_need_no_temp_read_permission(self):
        connection = self.temp_copy()
        try:
            self.joined(connection, deny_temp=True)
        finally:
            connection.close()

    def test_ms003_bad_main_hash_not_hidden_by_healthy_temp(self):
        connection = self.temp_copy()
        try:
            self.mutate_main("ledger_events", "UPDATE main.ledger_events SET event_hash=? WHERE sequence=1",
                             ("f" * 64,), trigger="ledger_events_seal_only")
            self.joined(connection, error=LedgerError, message="^journal event hash changed$")
        finally:
            connection.close()

    def test_ms004_bad_main_balance_not_hidden_by_healthy_temp(self):
        connection = self.temp_copy()
        try:
            self.mutate_main("ledger_balances", "UPDATE main.ledger_balances SET units='951' WHERE account='b' AND asset='USD'")
            self.joined(connection, error=LedgerError, message="^materialized balances differ from journal replay$")
        finally:
            connection.close()

    def test_ms005_bad_main_postings_not_hidden_by_healthy_temp(self):
        connection = self.temp_copy()
        try:
            self.mutate_main("ledger_postings", "UPDATE main.ledger_postings SET units='-301' WHERE sequence=2 AND ordinal=0",
                             trigger="ledger_postings_no_update")
            self.joined(connection, error=LedgerError, message="^event must balance independently for every asset$")
        finally:
            connection.close()

    def test_ms006_bad_main_version_not_hidden_by_healthy_temp(self):
        connection = self.temp_copy()
        try:
            self.mutate_main("ledger_schema", "UPDATE main.ledger_schema SET version=999 WHERE singleton=1")
            self.joined(connection, error=LedgerError, message="^ledger schema version changed$")
        finally:
            connection.close()

    def test_ms007_bad_main_scale_not_hidden_by_healthy_temp(self):
        connection = self.temp_copy()
        try:
            self.mutate_main("ledger_assets", "UPDATE main.ledger_assets SET scale=3 WHERE asset='USD'",
                             trigger="ledger_assets_no_update")
            self.joined(connection, error=LedgerError, message="^ledger asset scales changed$")
        finally:
            connection.close()

    def test_ms008_bad_temp_does_not_change_healthy_main_verdict(self):
        connection = self.temp_copy()
        try:
            connection.execute("UPDATE temp.ledger_events SET event_hash=? WHERE sequence=1", ("f" * 64,))
            connection.execute("UPDATE temp.ledger_balances SET units='951' WHERE account='b' AND asset='USD'")
            connection.execute("INSERT INTO temp.ledger_postings VALUES(99,0,'orphan','USD','1')")
            self.joined(connection)
        finally:
            connection.close()

    def test_ms009_f01_bad_main_catalogue_not_hidden_by_temp(self):
        connection = self.temp_copy()
        offline = self.raw()
        try:
            definition = next(row[3] for row in self.good["catalogue"] if row[1] == "ledger_postings")
            triggers = [row[3] for row in self.good["catalogue"] if row[0] == "trigger" and row[2] == "ledger_postings"]
            offline.execute("PRAGMA foreign_keys=OFF")
            offline.execute("BEGIN IMMEDIATE")
            offline.execute("DROP TABLE main.ledger_postings")
            offline.execute(definition.replace("sequence INTEGER NOT NULL REFERENCES ledger_events(sequence)", "sequence INTEGER NOT NULL"))
            offline.executemany("INSERT INTO main.ledger_postings VALUES(?,?,?,?,?)", self.good["tables"]["ledger_postings"])
            for sql in triggers:
                offline.execute(sql)
            offline.execute("INSERT INTO main.ledger_postings VALUES(99,0,'orphan','USD','1')")
            offline.commit()
            self.joined(connection, error=LedgerError, message="^journal postings table definition changed$")
        finally:
            offline.close()
            connection.close()

    def test_ms010_real_managed_read_transaction_still_verifies_main(self):
        from uta.writer_fence import WriterFence
        fence = WriterFence(self.database)
        fence.enable("synthetic-main-read")
        token = fence.acquire("main-reader-owner", 5)
        try:
            with self.database.read_transaction() as connection:
                self.assertEqual(self.ledger.verify(connection=connection), 2)
                self.assertTrue(connection.in_transaction)
                # Serialize only the five financial tables, never owner/token rows.
                financial = self.snapshot(connection, "main")["tables"]
                self.assertEqual(financial, self.good["tables"])
            (self.directory / "managed-read.json").write_text(json.dumps(
                {"verified_events": 2, "financial_tables": financial}, indent=2) + "\n")
        finally:
            fence.release(token)

    def test_ms011_real_managed_raw_join_remains_unguarded(self):
        from uta.writer_fence import WriterFence, WriterFenceError
        fence = WriterFence(self.database)
        fence.enable("synthetic-main-raw-refusal")
        connection = self.temp_copy()
        try:
            self.joined(connection, error=WriterFenceError, message="managed ledger connections must originate",
                        code="unguarded_connection")
        finally:
            connection.close()

    def test_ms012_different_main_path_still_rejects_raw_join(self):
        path = self.directory / "different.sqlite3"
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(descriptor)
        connection = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, isolation_level=None)
        try:
            connection.execute("BEGIN")
            with self.assertRaisesRegex(StorageError, "another database") as caught:
                self.ledger.verify(connection=connection)
            self.assertTrue(connection.in_transaction)
            (self.directory / "foreign-main.json").write_text(json.dumps(
                {"error_type": type(caught.exception).__name__, "error_message": str(caught.exception),
                 "caller_transaction_remained_active": True,
                 "actual_database_list": [list(row) for row in connection.execute("PRAGMA database_list")]}, indent=2) + "\n")
            connection.rollback()
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
