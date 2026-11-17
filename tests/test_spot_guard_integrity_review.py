"""Independent offline-corruption checks for semantic spot receipt guards.

Weakening SQL is fault injection, not a customer trading operation. Behavioral
probes roll back, retaining every order, fill, match, event and settled unit.
"""
import json
import sqlite3
import unittest

from tests import test_managed_migration_scope as fixtures
from uta.service import ServiceError
from uta.storage import Database


class SpotGuardIntegrityReviewTests(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.ManagedMigrationScopeTests(
            "test_terminal_history_preflight_and_verifier_open_no_financial_constructor_or_writer")
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)

    def reject_semantically_disabled_guard(self, table, action):
        case = self.case
        case.source()
        _, spot = case.add_offline_standalone_spot_extension()
        case.cancel_source_spot(spot)
        financial, business = case.financial_state(), case.spot_state()
        name = table + "_no_" + action.lower()
        where = " WHERE rowid=(SELECT MIN(rowid) FROM " + table + ")"
        statement = (("UPDATE " + table + " SET price=price") if action == "UPDATE"
                     else ("DELETE FROM " + table)) + where
        with Database(case.path / "shard-0000.sqlite3").transaction() as connection:
            original = connection.execute("SELECT sql FROM sqlite_master WHERE name=?", (name,)).fetchone()[0]
            if action == "DELETE":
                # Defer only this test transaction's FK check so the receipt
                # DELETE probe can be rolled back without deleting its fills.
                connection.execute("PRAGMA defer_foreign_keys=ON")
            with self.assertRaisesRegex(sqlite3.IntegrityError, "spot .* immutable"):
                connection.execute(statement)
            weakened = original.replace(" BEGIN ", " WHEN 0 BEGIN ", 1)
            self.assertNotEqual(original, weakened)
            connection.execute("DROP TRIGGER " + name)
            connection.execute(weakened)
            connection.execute("SAVEPOINT semantic_guard_probe")
            before = connection.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
            touched = connection.execute(statement).rowcount
            self.assertEqual(touched, 1, "the exact protected operation must actually pass the weakened guard")
            if action == "DELETE":
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM " + table).fetchone()[0], before - 1)
            connection.execute("ROLLBACK TO SAVEPOINT semantic_guard_probe")
            connection.execute("RELEASE SAVEPOINT semantic_guard_probe")
            self.assertEqual(list(connection.execute("PRAGMA foreign_key_check")), [])
        self.assertEqual(case.spot_state(), business)
        self.assertEqual(case.financial_state(), financial)
        verified = verifier_error = migration_error = None
        try:
            verified = spot.verify()
        except ServiceError as error:
            verifier_error = error
        try:
            case.take_over()
        except ServiceError as error:
            migration_error = error
        exists = case.read("SELECT name FROM sqlite_master WHERE name='router_durable_config'", control=True)
        manifest = case.read("SELECT initialized FROM router_durable_config", control=True) if exists else []
        print("spot-guard-evidence", json.dumps({
            "guard": name, "protected_operation": action,
            "original_operation_blocked": True, "weakened_operation_succeeded_then_rolled_back": True,
            "verifier_result": verified, "verifier_error": None if verifier_error is None else verifier_error.code,
            "migration_error": None if migration_error is None else migration_error.code,
            "manifest": manifest, "business_rows_unchanged": case.spot_state() == business,
            "financial_rows_unchanged": case.financial_state() == financial,
            "weak_sql_preserved": case.read("SELECT sql FROM sqlite_master WHERE name=?", (name,))[0]["sql"] == weakened,
        }), flush=True)
        self.assertEqual(case.spot_state(), business)
        self.assertEqual(case.financial_state(), financial)
        self.assertEqual(case.read("SELECT sql FROM sqlite_master WHERE name=?", (name,))[0]["sql"], weakened,
                         "verification must preserve corrupt evidence instead of repairing it")
        self.assertIsNotNone(verifier_error, "a guard name does not establish its immutable-receipt semantics")
        self.assertEqual((verifier_error.code, verifier_error.status), ("spot_corrupt", 503))
        self.assertIsNotNone(migration_error, "corrupt receipt guards must be rejected before sealing")
        self.assertEqual((migration_error.code, migration_error.status), ("spot_corrupt", 503))
        case.assert_unsealed()

    def test_weakened_match_update_guard_is_rejected(self):
        self.reject_semantically_disabled_guard("uta_spot_matches", "UPDATE")

    def test_weakened_match_delete_guard_is_rejected(self):
        self.reject_semantically_disabled_guard("uta_spot_matches", "DELETE")

    def test_weakened_fill_update_guard_is_rejected(self):
        self.reject_semantically_disabled_guard("uta_spot_fills", "UPDATE")

    def test_weakened_fill_delete_guard_is_rejected(self):
        self.reject_semantically_disabled_guard("uta_spot_fills", "DELETE")


if __name__ == "__main__":
    unittest.main()
