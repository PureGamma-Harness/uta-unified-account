"""Actual original full financial verifier with its new persistent-main check."""
from decimal import Decimal as D
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from uta.credit import CreditService
from uta.credit_native import CreditNativeError, _verify_financial_source
from uta.ledger import LedgerError
from uta.service import ExchangeService
from uta.storage import Database


class CreditCatalogVerifierIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="uta-credit-full-catalog-verifier-")
        self.addCleanup(self.temp.cleanup)
        self.database = Database(Path(self.temp.name)/"synthetic.sqlite3")
        self.exchange = ExchangeService(self.database, {"USD": 8, "BTC": 8})
        self.exchange.create_account("alice")
        self.exchange.deposit("alice", "synthetic-capital", "USD", D(100))
        CreditService(self.exchange)

    def snapshot(self, connection):
        tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {"catalog": [tuple(row) for row in connection.execute("SELECT name,type,tbl_name,sql FROM sqlite_master ORDER BY name")],
            "rows": {table: [tuple(row) for row in connection.execute('SELECT * FROM "'+table+'" ORDER BY rowid')] for table in tables}}

    def test_canonical_source_runs_original_full_verifier_on_same_read_snapshot(self):
        with self.database.read_transaction() as connection:
            before = self.snapshot(connection)
            trace = []
            connection.set_trace_callback(trace.append)
            _verify_financial_source(self.database, connection, self.exchange.scales)
            connection.set_trace_callback(None)
            self.assertEqual(self.snapshot(connection), before)
            self.assertEqual(connection.execute("PRAGMA query_only").fetchone()[0], 1)
        self.assertTrue(any("main.sqlite_master" in sql and "ledger_postings" in sql for sql in trace))
        self.assertFalse(any(sql.lstrip().upper().startswith(("CREATE", "DROP", "ALTER", "INSERT", "UPDATE", "DELETE")) for sql in trace))

    def test_missing_event_fk_with_original_rows_and_guards_is_refused_before_credit(self):
        # Explicit own unmanaged synthetic corruption, not a permitted managed
        # mutation or a fake successful native callback. Preserve the financial
        # rows and original immutable triggers to isolate the catalogue defect.
        with self.database.transaction() as connection:
            installed = connection.execute("SELECT sql FROM sqlite_master WHERE name='ledger_postings'").fetchone()[0]
            changed = installed.replace(" REFERENCES ledger_events(sequence)", "", 1)
            self.assertNotEqual(installed, changed)
            postings = [tuple(row) for row in connection.execute("SELECT * FROM ledger_postings ORDER BY sequence,ordinal")]
            guards = [row[0] for row in connection.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND tbl_name='ledger_postings' ORDER BY name")]
            connection.execute("DROP TABLE ledger_postings")
            connection.execute(changed)
            connection.executemany("INSERT INTO ledger_postings VALUES(?,?,?,?,?)", postings)
            for statement in guards:
                connection.execute(statement)
        with self.database.read_transaction() as connection:
            before = self.snapshot(connection)
            with self.assertRaises(CreditNativeError) as rejected:
                _verify_financial_source(self.database, connection, self.exchange.scales)
            self.assertEqual(rejected.exception.code, "credit_financial_source_invalid")
            self.assertIs(type(rejected.exception.__cause__), LedgerError)
            self.assertEqual(str(rejected.exception.__cause__), "journal postings table definition changed")
            self.assertEqual(self.snapshot(connection), before)


if __name__ == "__main__":
    unittest.main()
