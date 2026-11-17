"""Offline corruption cases for complete, typed spot confirmation evidence."""
import json
import unittest

from tests import test_managed_migration_scope as fixtures
from uta.service import ServiceError


class SpotConfirmationIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.ManagedMigrationScopeTests(
            "test_terminal_history_preflight_and_verifier_open_no_financial_constructor_or_writer")
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.case.source()
        self.exchange, self.spot = self.case.add_offline_standalone_spot_extension()
        self.case.cancel_source_spot(self.spot)

    def corrupt_event(self, change, *, global_event=False):
        # Deliberate offline corruption, never a supported customer write.
        kind = "SPOT_MATCH_CONFIRMED" if global_event else "SPOT_TRADE_CONFIRMED"
        with self.exchange.database.transaction() as connection:
            rows = connection.execute("SELECT * FROM uta_events WHERE event_type=? ORDER BY sequence", (kind,)).fetchall()
            guard = connection.execute("SELECT sql FROM sqlite_master WHERE name='uta_events_no_update'").fetchone()[0]
            connection.execute("DROP TRIGGER uta_events_no_update")
            account, payload = change(rows)
            connection.execute("UPDATE uta_events SET account_id=?,payload=? WHERE sequence=?",
                               (account, json.dumps(payload, separators=(",", ":")), rows[-1]["sequence"]))
            connection.execute(guard)
        financial, spot = self.case.financial_state(), self.case.spot_state()
        events = self.case.read("SELECT * FROM uta_events WHERE event_type GLOB 'SPOT_*' ORDER BY sequence")
        with self.assertRaises(ServiceError) as verify:
            self.spot.verify()
        self.assertEqual((verify.exception.code, verify.exception.status), ("spot_corrupt", 503))
        with self.assertRaises(ServiceError) as migrate:
            self.case.take_over()
        self.assertEqual((migrate.exception.code, migrate.exception.status), ("spot_corrupt", 503))
        self.case.assert_unsealed()
        self.assertEqual(self.case.financial_state(), financial)
        self.assertEqual(self.case.spot_state(), spot)
        self.assertEqual(self.case.read("SELECT * FROM uta_events WHERE event_type GLOB 'SPOT_*' ORDER BY sequence"), events)

    def test_duplicate_customer_confirmation_cannot_replace_the_other_side(self):
        self.corrupt_event(lambda rows: (rows[0]["account_id"], json.loads(rows[0]["payload"])))

    def test_private_market_reference_must_match_the_actual_execution(self):
        def change(rows):
            payload = json.loads(rows[-1]["payload"])
            payload["market_version"] += 1
            return rows[-1]["account_id"], payload
        self.corrupt_event(change)

    def test_boolean_is_not_an_integer_private_market_version(self):
        def change(rows):
            payload = json.loads(rows[-1]["payload"])
            self.assertEqual(payload["market_version"], 1)
            payload["market_version"] = True
            return rows[-1]["account_id"], payload
        self.corrupt_event(change)

    def test_boolean_is_not_an_integer_global_market_version(self):
        def change(rows):
            payload = json.loads(rows[-1]["payload"])
            self.assertEqual(payload["market_version"], 1)
            payload["market_version"] = True
            return None, payload
        self.corrupt_event(change, global_event=True)

    def test_scalar_confirmation_is_a_typed_corruption_error(self):
        self.corrupt_event(lambda rows: (rows[-1]["account_id"], []))

    def test_execution_confirmation_cannot_reference_an_unknown_trade(self):
        def change(rows):
            payload = json.loads(rows[-1]["payload"])
            payload["trade_id"] = "nonexistent-offline-fault"
            return rows[-1]["account_id"], payload
        self.corrupt_event(change)

    def test_private_payload_uses_the_recorded_event_contract(self):
        def change(rows):
            payload = json.loads(rows[-1]["payload"])
            payload["unexpected_account"] = "offline-fault"
            return rows[-1]["account_id"], payload
        self.corrupt_event(change)


if __name__ == "__main__":
    unittest.main()
