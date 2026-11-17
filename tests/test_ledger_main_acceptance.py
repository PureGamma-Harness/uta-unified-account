"""Independent MAIN-verification controls; import performs no SQL."""
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


TABLES = ("ledger_schema", "ledger_assets", "ledger_events", "ledger_postings", "ledger_balances")
WRITES = re.compile(r"\s*(CREATE|DROP|ALTER|INSERT|UPDATE|DELETE|REPLACE|COMMIT|ROLLBACK|SAVEPOINT|RELEASE)\b", re.I)


class ReadMethodAliases:
    """Same read-method protocol as PR19; not the unavailable M3 integration."""
    _normalize = DurableLedger._normalize
    _fingerprint = staticmethod(DurableLedger._fingerprint)
    _hash = staticmethod(DurableLedger._hash)
    _stored_units = staticmethod(DurableLedger._stored_units)
    _verify_postings_definition = staticmethod(DurableLedger._verify_postings_definition)
    _verify_protection = staticmethod(DurableLedger._verify_protection)
    verify = DurableLedger.verify

    def __init__(self, original):
        self.database, self.scales, self._codec = original.database, original.scales, original._codec


class IndependentMainAcceptance(unittest.TestCase):
    def setUp(self):
        retained = os.environ.get("UTA_LEDGER_MAIN_ACCEPTANCE_CASES")
        if retained:
            parent = Path(retained)
            if not parent.is_absolute():
                raise ValueError("retained independent MAIN cases require an absolute path")
        else:
            temporary = TemporaryDirectory(prefix="uta-independent-main-")
            self.addCleanup(temporary.cleanup)
            parent = Path(temporary.name)
        self.directory = parent / self._testMethodName
        self.directory.mkdir(parents=True, mode=0o700, exist_ok=False)
        self.path = self.directory / "synthetic.sqlite3"
        self.database = Database(self.path, timeout=1)
        self.ledger = DurableLedger(self.database, {"USD": 2})
        self.ledger.post("ind-main:1", self.postings("a", "b", "9.00"))
        self.ledger.post("ind-main:2", self.postings("b", "c", "2.00"))
        with closing(self.raw()) as connection:
            self.good = self.snapshot(connection, "main")
        self.assertEqual(self.good["rows"]["ledger_balances"],
                         [["a", "USD", "-900"], ["b", "USD", "700"], ["c", "USD", "200"]])

    @staticmethod
    def postings(source, target, amount):
        amount = Decimal(amount)
        return [Posting(source, "USD", -amount), Posting(target, "USD", amount)]

    def raw(self, path=None):
        connection = sqlite3.connect((path or self.path).as_uri() + "?mode=rw", uri=True,
                                     isolation_level=None, timeout=1)
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @staticmethod
    def snapshot(connection, schema):
        assert schema in ("main", "temp")
        present = {row[0] for row in connection.execute("SELECT name FROM " + schema + ".sqlite_master")}
        return {"catalogue": [list(row) for row in connection.execute(
                    "SELECT type,name,tbl_name,sql FROM " + schema + ".sqlite_master ORDER BY type,name")],
                "rows": {name: [list(row) for row in connection.execute(
                    'SELECT * FROM ' + schema + '."' + name + '" ORDER BY 1,2')] if name in present else None
                    for name in TABLES}}

    def record(self, name, value):
        (self.directory / (name + ".json")).write_text(json.dumps(value, indent=2) + "\n")

    def genuine_temp_copy(self):
        connection = self.raw()
        connection.execute("BEGIN")
        for name in TABLES:
            connection.execute('CREATE TEMP TABLE "' + name + '" AS SELECT * FROM main."' + name + '"')
        self.assertEqual(self.snapshot(connection, "temp")["rows"], self.good["rows"])
        connection.commit()
        return connection

    def mutate_main(self, sql, params=(), *, trigger=None, foreign_keys=True):
        with closing(self.raw()) as connection:
            if not foreign_keys:
                connection.execute("PRAGMA foreign_keys=OFF")
            connection.execute("BEGIN IMMEDIATE")
            if trigger:
                original = next(row[3] for row in self.good["catalogue"] if row[1] == trigger)
                connection.execute('DROP TRIGGER main."' + trigger + '"')
            connection.execute(sql, params)
            if trigger:
                connection.execute(original)
            connection.commit()
            self.assertEqual(self.snapshot(connection, "main")["catalogue"], self.good["catalogue"])

    def assert_direct_error(self, message):
        with self.assertRaisesRegex(LedgerError, "^" + re.escape(message) + "$"):
            self.ledger.verify()

    def joined(self, connection, *, message=None, view=None, active=False):
        connection.execute("PRAGMA query_only=ON")
        if not active:
            connection.execute("BEGIN")
        main_before, temp_before = self.snapshot(connection, "main"), self.snapshot(connection, "temp")
        trace, reads, denials = [], [], []
        def authorizer(action, first, second, database, source):
            if action == sqlite3.SQLITE_READ:
                reads.append([database, first, second])
                if database == "temp":
                    denials.append([database, first, second])
                    return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        connection.set_trace_callback(trace.append)
        connection.set_authorizer(authorizer)
        try:
            if message is None:
                self.assertEqual((view or self.ledger).verify(connection=connection), 2)
                observed = {"events": 2}
            else:
                with self.assertRaisesRegex(LedgerError, "^" + re.escape(message) + "$"):
                    (view or self.ledger).verify(connection=connection)
                observed = {"error_type": "LedgerError", "message": message}
        finally:
            connection.set_authorizer(None)
            connection.set_trace_callback(None)
        self.assertTrue(connection.in_transaction)
        self.assertEqual(connection.execute("PRAGMA query_only").fetchone()[0], 1)
        self.assertEqual(self.snapshot(connection, "main"), main_before)
        self.assertEqual(self.snapshot(connection, "temp"), temp_before)
        self.assertEqual(denials, [])
        self.assertTrue(reads)
        self.assertTrue(all(row[0] == "main" for row in reads), reads)
        self.assertFalse(any(WRITES.match(sql) for sql in trace), trace)
        if active:
            self.assertEqual(connection.execute("SELECT value FROM temp.independent_marker").fetchone()[0], "outer-uncommitted")
        self.record("joined", {"observed": observed, "main": main_before, "temp": temp_before,
                    "actual_read_database_table_column": reads, "denied_temp_reads": denials,
                    "verification_trace": trace, "query_only_unchanged": True,
                    "caller_transaction_remained_active": True, "both_logical_states_unchanged": True,
                    "uncommitted_caller_marker_checked": active})
        connection.rollback()

    def test_01_bad_main_hash_refuses_despite_genuine_good_temp(self):
        with closing(self.genuine_temp_copy()) as connection:
            self.mutate_main("UPDATE main.ledger_events SET event_hash=? WHERE sequence=1",
                             ("c" * 64,), trigger="ledger_events_seal_only")
            message = "journal event hash changed"
            self.assert_direct_error(message)
            self.joined(connection, message=message)

    def test_02_bad_main_balance_refuses_despite_genuine_good_temp(self):
        with closing(self.genuine_temp_copy()) as connection:
            self.mutate_main("UPDATE main.ledger_balances SET units='701' WHERE account='b' AND asset='USD'")
            message = "materialized balances differ from journal replay"
            self.assert_direct_error(message)
            self.joined(connection, message=message)

    def test_03_healthy_main_ignores_malformed_temp_views_without_temp_read_permission(self):
        with closing(self.genuine_temp_copy()) as connection:
            for name in TABLES:
                connection.execute('DROP TABLE temp."' + name + '"')
                connection.execute('CREATE TEMP VIEW "' + name + '" AS SELECT 99 AS invalid_column,0 AS invalid_other')
            self.joined(connection)
        self.assertEqual(self.ledger.verify(), 2)

    def test_04_f01_bad_main_definition_with_orphan_still_refuses_before_repair(self):
        with closing(self.genuine_temp_copy()) as connection, closing(self.raw()) as offline:
            original = next(row[3] for row in self.good["catalogue"] if row[1] == "ledger_postings")
            triggers = [row[3] for row in self.good["catalogue"] if row[0] == "trigger" and row[2] == "ledger_postings"]
            offline.execute("PRAGMA foreign_keys=OFF")
            offline.execute("BEGIN IMMEDIATE")
            offline.execute("DROP TABLE main.ledger_postings")
            offline.execute(original.replace(" REFERENCES ledger_events(sequence)", "", 1))
            offline.executemany("INSERT INTO main.ledger_postings VALUES(?,?,?,?,?)", self.good["rows"]["ledger_postings"])
            for trigger in triggers:
                offline.execute(trigger)
            offline.execute("INSERT INTO main.ledger_postings VALUES(99,0,'ind-orphan','USD','1')")
            offline.commit()
            before = self.snapshot(offline, "main")
            message = "journal postings table definition changed"
            self.assert_direct_error(message)
            with self.assertRaisesRegex(LedgerError, "^" + message + "$"):
                DurableLedger(self.database, {"USD": 2})
            self.assertEqual(self.snapshot(offline, "main"), before)
            self.joined(connection, message=message)

    def test_05_main_version_error_precedes_hash_and_balance_errors(self):
        with closing(self.genuine_temp_copy()) as connection:
            self.mutate_main("UPDATE main.ledger_schema SET version=99")
            self.mutate_main("UPDATE main.ledger_events SET event_hash=? WHERE sequence=1", ("c" * 64,), trigger="ledger_events_seal_only")
            self.mutate_main("UPDATE main.ledger_balances SET units='701' WHERE account='b'")
            self.assert_direct_error("ledger schema version changed")
            self.joined(connection, message="ledger schema version changed")

    def test_06_main_scales_error_precedes_hash_error(self):
        with closing(self.genuine_temp_copy()) as connection:
            self.mutate_main("UPDATE main.ledger_assets SET scale=3", trigger="ledger_assets_no_update")
            self.mutate_main("UPDATE main.ledger_events SET event_hash=? WHERE sequence=1", ("c" * 64,), trigger="ledger_events_seal_only")
            self.assert_direct_error("ledger asset scales changed")
            self.joined(connection, message="ledger asset scales changed")

    def test_07_main_trigger_error_precedes_hash_error(self):
        with closing(self.genuine_temp_copy()) as connection:
            self.mutate_main("UPDATE main.ledger_events SET event_hash=? WHERE sequence=1", ("c" * 64,), trigger="ledger_events_seal_only")
            with closing(self.raw()) as offline:
                offline.execute("DROP TRIGGER main.ledger_postings_no_update")
            self.assert_direct_error("journal protection trigger is missing")
            self.joined(connection, message="journal protection trigger is missing")

    def test_08_query_only_verification_preserves_uncommitted_callers_marker(self):
        with closing(self.genuine_temp_copy()) as connection:
            connection.execute("CREATE TEMP TABLE independent_marker(value TEXT)")
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("INSERT INTO temp.independent_marker VALUES('outer-uncommitted')")
            self.joined(connection, active=True)
            self.assertEqual(connection.execute("SELECT count(*) FROM temp.independent_marker").fetchone()[0], 0)
        self.assertEqual(self.ledger.verify(), 2)
        self.record("caller-rollback", {"main_events_after_caller_rollback": 2, "marker_rows_after_caller_rollback": 0})

    def test_09_real_managed_bound_constructor_and_native_read_role(self):
        fence = WriterFence(self.database)
        fence.enable("independent-f02-managed")
        token = fence.acquire("independent-f02-owner", 5)
        try:
            bound_database = self.database.for_writer(token)
            bound = DurableLedger(bound_database, {"USD": 2})
            with bound_database.read_transaction() as connection:
                before = self.snapshot(connection, "main")
                trace = []
                connection.set_trace_callback(trace.append)
                self.assertEqual(bound.verify(connection=connection), 2)
                connection.set_trace_callback(None)
                self.assertTrue(connection.in_transaction)
                self.assertEqual(connection.execute("PRAGMA query_only").fetchone()[0], 1)
                self.assertEqual(self.snapshot(connection, "main"), before)
                self.assertFalse(any(WRITES.match(sql) for sql in trace))
            self.assertEqual(before["rows"], self.good["rows"])
            self.record("managed-read", {"events": 2, "native_authorizer_retained": True, "base_state": before, "trace": trace})
        finally:
            fence.release(token)

    def test_10_read_only_schema_helpers_grant_no_managed_join_or_write_authority(self):
        fence = WriterFence(self.database)
        fence.enable("independent-f02-no-grant")
        with closing(self.genuine_temp_copy()) as connection:
            connection.execute("PRAGMA query_only=ON")
            connection.execute("BEGIN")
            before_main, before_temp = self.snapshot(connection, "main"), self.snapshot(connection, "temp")
            self.assertIsNone(DurableLedger._verify_postings_definition(connection))
            self.assertIsNone(DurableLedger._verify_protection(connection))
            with self.assertRaises(WriterFenceError) as rejected:
                self.ledger.verify(connection=connection)
            self.assertEqual(rejected.exception.code, "unguarded_connection")
            self.assertTrue(connection.in_transaction)
            self.assertEqual(self.snapshot(connection, "main"), before_main)
            self.assertEqual(self.snapshot(connection, "temp"), before_temp)
            connection.rollback()
        with self.assertRaises(WriterFenceError) as rejected:
            self.ledger.post("ind-main:unauthorized", self.postings("a", "b", "1.00"))
        self.assertEqual(rejected.exception.code, "writer_fenced")
        with self.database.read_transaction() as connection:
            self.assertEqual(self.snapshot(connection, "main")["rows"], self.good["rows"])
        self.record("no-grant", {"schema_helpers_read_only": True, "raw_join_error": "unguarded_connection",
                    "unbound_post_error": "writer_fenced", "base_rows_unchanged": True})

    def test_11_other_main_path_still_refuses_before_any_ledger_lookup(self):
        other = self.directory / "other.sqlite3"
        DurableLedger(Database(other, timeout=1), {"USD": 2})
        with closing(self.raw(other)) as connection:
            connection.execute("BEGIN")
            with self.assertRaisesRegex(StorageError, "^the supplied connection belongs to another database$"):
                self.ledger.verify(connection=connection)
            self.assertTrue(connection.in_transaction)
        self.record("foreign-main", {"error": "the supplied connection belongs to another database", "caller_transaction_preserved": True})

    def test_12_read_method_alias_protocol_uses_original_main_checkers(self):
        view = ReadMethodAliases(self.ledger)
        self.assertIs(ReadMethodAliases._verify_postings_definition, DurableLedger._verify_postings_definition)
        self.assertIs(ReadMethodAliases._verify_protection, DurableLedger._verify_protection)
        self.assertFalse(hasattr(view, "post"))
        with closing(self.genuine_temp_copy()) as connection:
            self.mutate_main("UPDATE main.ledger_events SET event_hash=? WHERE sequence=1", ("c" * 64,), trigger="ledger_events_seal_only")
            self.joined(connection, view=view, message="journal event hash changed")
        self.record("alias-scope", {"direct_checker_binding_identity": True, "protocol_only": True,
                    "actual_M3_credit_module_not_present_in_this_52_source_tree": True})

    def test_13_supported_real_sqlite_backup_preserves_canonical_ledger(self):
        backup = self.directory / "supported-backup.sqlite3"
        metadata = backup_database(self.path, backup, timeout=1)
        self.assertEqual(DurableLedger(Database(backup, timeout=1), {"USD": 2}).verify(), 2)
        self.record("backup", {"verified_events": 2, "supported_backup_metadata": metadata})

    def test_14_main_foreign_key_failure_precedes_version_and_hash_errors(self):
        with closing(self.genuine_temp_copy()) as connection:
            self.mutate_main("INSERT INTO main.ledger_postings VALUES(99,0,'main-fk-orphan','USD','1')", foreign_keys=False)
            self.mutate_main("UPDATE main.ledger_schema SET version=99")
            self.mutate_main("UPDATE main.ledger_events SET event_hash=? WHERE sequence=1", ("c" * 64,), trigger="ledger_events_seal_only")
            message = "database foreign-key check failed"
            self.assert_direct_error(message)
            self.joined(connection, message=message)


if __name__ == "__main__":
    unittest.main()
