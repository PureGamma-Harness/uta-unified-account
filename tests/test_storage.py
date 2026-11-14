import concurrent.futures
from decimal import Decimal, localcontext
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from uta.ledger import Ledger, LedgerError, Posting
from uta.storage import Database, DurableLedger, StorageError


D = Decimal


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "ledger.sqlite3"
        self.database = Database(self.path)
        self.ledger = DurableLedger(self.database, {"USD": 6, "BTC": 8})

    @staticmethod
    def transfer(amount=D("12.500000")):
        return [Posting("external", "USD", amount.copy_negate()), Posting("customer", "USD", amount)]

    def test_restart_preserves_journal_exact_balances_and_idempotency(self):
        first = self.ledger.post("deposit:1", self.transfer())
        restored = DurableLedger(Database(self.path), {"USD": 6, "BTC": 8})
        self.assertEqual(restored.balance("customer", "USD"), D("12.5"))
        self.assertEqual(restored.post("deposit:1", self.transfer()[::-1]), first)
        self.assertEqual(restored.journal(), (first,))
        self.assertEqual(restored.verify(), 1)
        replay = Ledger.replay({"USD": 6, "BTC": 8}, restored.journal())
        self.assertEqual(replay.balance("external", "USD"), D("-12.5"))
        with self.assertRaises(LedgerError):
            restored.post("deposit:1", self.transfer(D("99")))
        self.assertEqual(restored.verify(), 1)

    def test_rejected_post_does_not_consume_id_or_change_balances(self):
        self.ledger.post("initial", self.transfer())
        for postings in (
            [Posting("a", "USD", D("1")), Posting("b", "USD", D("-2"))],
            self.transfer(D("0.0000001")),
            self.transfer(D("NaN")),
            [Posting("a", "USD", D("1")), Posting("b", "BTC", D("-1"))],
        ):
            with self.assertRaises(LedgerError):
                self.ledger.post("rejected", postings)
            self.assertEqual(self.ledger.verify(), 1)
            self.assertEqual(self.ledger.balance("customer", "USD"), D("12.5"))
        self.ledger.post("rejected", self.transfer(D("1")))
        self.assertEqual(self.ledger.verify(), 2)

    def test_outer_transaction_rollback_includes_ledger_and_business_rows(self):
        with self.database.transaction() as connection:
            connection.execute("CREATE TABLE business (id TEXT PRIMARY KEY)")
        with self.assertRaisesRegex(RuntimeError, "crash"):
            with self.database.transaction() as connection:
                connection.execute("INSERT INTO business VALUES ('order-1')")
                self.ledger.post("deposit", self.transfer(), connection=connection)
                self.assertEqual(self.ledger.balance("customer", "USD", connection=connection), D("12.5"))
                self.assertEqual(len(self.ledger.journal(connection=connection)), 1)
                raise RuntimeError("crash before commit")
        self.assertEqual(self.ledger.balance("customer", "USD"), 0)
        self.assertEqual(self.ledger.verify(), 0)
        with self.database.transaction() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM business").fetchone()[0], 0)

    def test_abrupt_process_exit_rolls_back_uncommitted_writes_and_keeps_commits(self):
        script = """
from decimal import Decimal as D
import os
import sys
from uta.ledger import Posting
from uta.storage import Database, DurableLedger
database = Database(sys.argv[1])
ledger = DurableLedger(database, {"USD": 6, "BTC": 8})
with database.transaction() as connection:
    ledger.post(sys.argv[2], [Posting('external', 'USD', D('-7')), Posting('customer', 'USD', D('7'))],
                connection=connection)
    if sys.argv[2] == 'uncommitted':
        os._exit(17)
os._exit(17)
"""
        for event, expected in (("uncommitted", D("0")), ("committed", D("7"))):
            result = subprocess.run([sys.executable, "-c", script, str(self.path), event],
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 17, result.stdout + result.stderr)
            restored = DurableLedger(Database(self.path), {"USD": 6, "BTC": 8})
            self.assertEqual(restored.balance("customer", "USD"), expected)
            self.assertEqual(restored.verify(), int(bool(expected)))

    def test_sql_failure_rolls_back_only_ledger_savepoint(self):
        with self.database.transaction() as connection:
            connection.execute("CREATE TABLE business (id TEXT PRIMARY KEY)")
            connection.execute("""CREATE TRIGGER reject_customer BEFORE INSERT ON ledger_postings
                               WHEN NEW.account = 'customer' BEGIN SELECT RAISE(ABORT, 'injected failure'); END""")
        with self.database.transaction() as connection:
            connection.execute("INSERT INTO business VALUES ('kept')")
            with self.assertRaisesRegex(sqlite3.IntegrityError, "injected failure"):
                self.ledger.post("failed", self.transfer(), connection=connection)
            self.assertEqual(self.ledger.journal(connection=connection), ())
            connection.execute("DROP TRIGGER reject_customer")
        self.assertEqual(self.ledger.verify(), 0)
        self.ledger.post("failed", self.transfer())
        with self.database.transaction() as connection:
            self.assertEqual(connection.execute("SELECT id FROM business").fetchone()[0], "kept")
        self.assertEqual(self.ledger.verify(), 1)

    def test_exactness_and_balance_limit_are_independent_of_decimal_context(self):
        amount = D("12345678901234567890.123456")
        with localcontext() as context:
            context.prec = 3
            self.ledger.post("large", self.transfer(amount))
            self.assertEqual(self.ledger.balance("customer", "USD"), amount)
            self.assertEqual(self.ledger.verify(), 1)
        almost_limit = D("99999999999999999999999999999999.999999")
        ledger = DurableLedger(Database(Path(self.directory.name) / "limit.db"), {"USD": 6})
        ledger.post("first", self.transfer(almost_limit))
        with self.assertRaisesRegex(LedgerError, "balance exceeds"):
            ledger.post("overflow", self.transfer(D("0.000001")))
        self.assertEqual(ledger.verify(), 1)

    def test_cross_instance_concurrent_retries_commit_once(self):
        peers = [DurableLedger(Database(self.path), {"USD": 6, "BTC": 8}) for _ in range(4)]
        def attempt(index):
            return peers[index % len(peers)].post("shared", self.transfer())
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(attempt, range(64)))
        self.assertTrue(all(result == results[0] for result in results))
        self.assertEqual(self.ledger.verify(), 1)
        self.assertEqual(self.ledger.balance("customer", "USD"), D("12.5"))

    def test_concurrent_processes_retry_and_distinct_events_without_lost_updates(self):
        script = """
from decimal import Decimal as D
import sys
from uta.ledger import Posting
from uta.storage import Database, DurableLedger
ledger = DurableLedger(Database(sys.argv[1]), {"USD": 6, "BTC": 8})
for number in range(12):
    for event in ('shared', sys.argv[2] + ':' + str(number)):
        ledger.post(event, [Posting('external', 'USD', D('-1')), Posting('customer', 'USD', D('1'))])
"""
        processes = [subprocess.Popen([sys.executable, "-c", script, str(self.path), str(index)],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                     for index in range(4)]
        try:
            for process in processes:
                output, error = process.communicate(timeout=30)
                self.assertEqual(process.returncode, 0, output + error)
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.wait()
        self.assertEqual(self.ledger.balance("customer", "USD"), D("49"))
        self.assertEqual(self.ledger.verify(), 49)

    def test_journal_and_scale_mutation_protection(self):
        self.ledger.post("deposit", self.transfer())
        statements = (
            "UPDATE ledger_events SET event_id = 'changed'",
            "DELETE FROM ledger_events",
            "UPDATE ledger_postings SET units = '1'",
            "DELETE FROM ledger_postings",
            "INSERT INTO ledger_postings VALUES (1, 2, 'extra', 'USD', '1')",
            "UPDATE ledger_assets SET scale = 2 WHERE asset = 'USD'",
            "DELETE FROM ledger_assets WHERE asset = 'BTC'",
        )
        for statement in statements:
            with self.database.transaction() as connection:
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(statement)
            self.assertEqual(self.ledger.verify(), 1)
        with self.assertRaisesRegex(LedgerError, "scales differ"):
            DurableLedger(Database(self.path), {"USD": 2, "BTC": 8})

    def test_verify_detects_balance_corruption_hash_corruption_and_missing_triggers(self):
        self.ledger.post("deposit", self.transfer())
        with self.database.transaction() as connection:
            connection.execute("UPDATE ledger_balances SET units = '0' WHERE account = 'customer'")
        with self.assertRaisesRegex(LedgerError, "materialized balances"):
            self.ledger.verify()
        with self.database.transaction() as connection:
            connection.execute("UPDATE ledger_balances SET units = '12500000' WHERE account = 'customer'")
            connection.execute("DROP TRIGGER ledger_events_seal_only")
        with self.assertRaisesRegex(LedgerError, "trigger is missing"):
            self.ledger.verify()
        # A file owner can replace protections; hash verification must still
        # detect a changed journal even after protections have been reinstalled.
        with self.database.transaction() as connection:
            connection.execute("UPDATE ledger_events SET event_hash = ?", ("f" * 64,))
        restored = DurableLedger(Database(self.path), {"USD": 6, "BTC": 8})
        with self.assertRaisesRegex(LedgerError, "event hash changed"):
            restored.verify()

    def test_configuration_and_connection_contract(self):
        for path in ("", ":memory:", "file:ledger?mode=memory", None):
            with self.assertRaises(StorageError):
                Database(path)
        for timeout in (0, -1, True, float("nan"), float("inf"), 301):
            with self.assertRaises(StorageError):
                Database(self.path, timeout=timeout)
        with self.database.transaction() as connection:
            self.assertEqual(connection.execute("PRAGMA journal_mode").fetchone()[0], "wal")
            self.assertEqual(connection.execute("PRAGMA synchronous").fetchone()[0], 2)
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        outside = sqlite3.connect(self.path)
        self.addCleanup(outside.close)
        with self.assertRaisesRegex(StorageError, "active transaction"):
            self.ledger.balance("customer", "USD", connection=outside)
        with Database(Path(self.directory.name) / "wrong.db").transaction() as connection:
            with self.assertRaisesRegex(StorageError, "another database"):
                self.ledger.post("wrong", self.transfer(), connection=connection)

    def test_database_schema_version_cannot_silently_downgrade(self):
        with self.database.transaction() as connection:
            connection.execute("UPDATE ledger_schema SET version = 999")
        with self.assertRaisesRegex(StorageError, "unsupported ledger schema"):
            DurableLedger(Database(self.path), {"USD": 6, "BTC": 8})

    def test_verify_uses_event_net_deltas_as_post_does(self):
        # A balancing event can transiently exceed a balance if considered in
        # posting order; its atomic net change is the applicable bound.
        ledger = DurableLedger(Database(Path(self.directory.name) / "net.db"), {"USD": 0})
        maximum = D("99999999999999999999999999999999999999")
        ledger.post("initial", [Posting("a", "USD", maximum.copy_negate()), Posting("b", "USD", maximum)])
        ledger.post("net", [Posting("a", "USD", D("-1")), Posting("a", "USD", D("2")),
                            Posting("b", "USD", D("-1"))])
        self.assertEqual(ledger.verify(), 2)


if __name__ == "__main__":
    unittest.main()
