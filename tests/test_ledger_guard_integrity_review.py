"""Offline ledger guard damage; the one synthetic funding post is never edited.

The file owner is trusted. Replacing schema SQL here is deliberate offline
corruption injection, not a customer API or a way around writer fencing.
"""
from contextlib import closing
from decimal import Decimal as D
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from uta.durable_process import DurableProcessRouter
from uta.ledger import LedgerError
from uta.service import ServiceError
from uta.sharding import ShardRouter
from uta.storage import Database, DurableLedger
from uta.writer_fence import WriterFence


class LedgerGuardIntegrityReviewTests(unittest.TestCase):
    def test_disabled_same_name_posting_update_guard_is_rejected_before_takeover(self):
        with TemporaryDirectory() as temporary:
            directory = Path(temporary) / "synthetic-offline-source"
            source = ShardRouter(directory, 1, {"USD": 2}, decision_audit=True)
            source.create_account("alice")
            source.deposit("alice", "synthetic-offline-funding", "USD", D("10"))
            path = directory / "shard-0000.sqlite3"
            database = Database(path)
            ledger = DurableLedger(database, {"USD": 2})
            self.assertEqual(ledger.verify(), 1)

            def rows():
                with closing(sqlite3.connect(path)) as connection:
                    tables = [row[0] for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' "
                        "AND name NOT LIKE 'writer_fence_%' AND name NOT LIKE 'uta_command_%' "
                        "ORDER BY name")]
                    return {table: list(connection.execute('SELECT * FROM "' + table + '" ORDER BY rowid'))
                            for table in tables if table != "sqlite_sequence"}

            before = rows()
            history = {table: value for table, value in before.items() if table.startswith("ledger_")}
            self.assertEqual(history["ledger_balances"],
                [("customer:alice", "USD", "1000"), ("system:custody", "USD", "-1000")])
            trigger = "ledger_postings_no_update"
            update = "UPDATE ledger_postings SET units='1001' WHERE account='customer:alice' AND asset='USD'"
            with closing(sqlite3.connect(path, isolation_level=None)) as connection:
                connection.execute("BEGIN IMMEDIATE")
                original = connection.execute("SELECT sql FROM sqlite_master WHERE name=?", (trigger,)).fetchone()[0]
                with self.assertRaisesRegex(sqlite3.IntegrityError, "journal is immutable"):
                    connection.execute(update)
                weakened = original.replace(" BEGIN ", " WHEN 0 BEGIN ", 1)
                self.assertNotEqual(weakened, original)
                connection.execute("DROP TRIGGER " + trigger)
                connection.execute(weakened)
                connection.execute("SAVEPOINT offline_guard_behavior_probe")
                self.assertEqual(connection.execute(update).rowcount, 1)
                self.assertEqual(connection.execute(
                    "SELECT units FROM ledger_postings WHERE account='customer:alice' AND asset='USD'").fetchone()[0], "1001")
                connection.execute("ROLLBACK TO SAVEPOINT offline_guard_behavior_probe")
                connection.execute("RELEASE SAVEPOINT offline_guard_behavior_probe")
                self.assertEqual(list(connection.execute("PRAGMA foreign_key_check")), [])
                connection.commit()  # Only the deliberately damaged guard is retained.
            self.assertEqual(rows(), before)

            verified = verify_error = reopened = reopen_error = migration_error = None
            try:
                verified = ledger.verify()
            except LedgerError as error:
                verify_error = error
            try:
                reopened = DurableLedger(database, {"USD": 2}).verify()
            except LedgerError as error:
                reopen_error = error
            plan = DurableProcessRouter.inspect_takeover(directory)
            managed = None
            try:
                managed = DurableProcessRouter.take_over(directory, managed=True,
                    expected_layout_hash=plan["layout_hash"], decision_audit=True)
            except (LedgerError, ServiceError) as error:
                migration_error = error
            finally:
                if managed is not None:
                    managed.close()  # No worker or supervisor was started.
            with closing(sqlite3.connect(path)) as connection:
                preserved_sql = connection.execute("SELECT sql FROM sqlite_master WHERE name=?", (trigger,)).fetchone()[0]
            with closing(sqlite3.connect(directory / "router.sqlite3")) as connection:
                manifest_exists = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE name='router_durable_config'").fetchone() is not None
                initialized = connection.execute("SELECT initialized FROM router_durable_config").fetchone()[0] if manifest_exists else None
            after = rows()
            prior_rows_unchanged = all(after[table] == value for table, value in before.items())
            history_unchanged = all(after[table] == value for table, value in history.items())
            lease = WriterFence(database).status()
            print("ledger-guard-evidence", json.dumps({
                "fault_scope": "synthetic trusted-owner offline guard SQL damage; no customer operation",
                "guard": trigger, "original_sql": original, "weakened_sql": weakened,
                "original_update_blocked": True, "weakened_update_touched_rows": 1,
                "temporary_units": "1001", "post_rollback_customer_units": "1000",
                "verified_events": verified, "verification_exception": None if verify_error is None else type(verify_error).__name__,
                "reopened_verified_events": reopened, "reopen_exception": None if reopen_error is None else type(reopen_error).__name__,
                "migration_exception": None if migration_error is None else type(migration_error).__name__,
                "migration_code": getattr(migration_error, "code", None), "manifest_initialized": initialized,
                "managed_after_takeover": lease["managed"], "guard_damage_preserved": preserved_sql == weakened,
                "prior_source_rows_unchanged": prior_rows_unchanged, "ledger_history_unchanged": history_unchanged,
                "ledger_history_sha256": sha256(json.dumps(history, sort_keys=True).encode()).hexdigest(),
                "workers_started": 0, "production_approved": False,
            }, sort_keys=True), flush=True)
            self.assertTrue(history_unchanged)
            self.assertTrue(prior_rows_unchanged)
            self.assertEqual(preserved_sql, weakened, "inspection must preserve the damaged guard as evidence")
            self.assertIsNotNone(verify_error, "same name/table with WHEN 0 is not an immutable journal guard")
            self.assertIsNotNone(reopen_error, "reopening must not accept a semantically disabled ledger guard")
            self.assertIsNotNone(migration_error, "managed take-over must reject a damaged journal guard")
            self.assertNotEqual(initialized, 1, "corrupt source must not become a completed managed authority")
            self.assertFalse(lease["managed"], "validate source journal guards before irreversible fencing")


if __name__ == "__main__":
    unittest.main()
