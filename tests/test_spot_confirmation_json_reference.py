"""Original strict-confirmation JSON failures at 3729b562, without runtime edits.

All faults modify only private synthetic temporary databases while offline,
restore the original event guard, and preserve the exact raw malformed payload.
No json.dumps roundtrip normalizes duplicate keys or nonstandard number tokens.
"""
import json
import re
import unittest

from tests import test_managed_migration_scope as fixtures
from uta.service import ServiceError


ORIGINAL_SOURCE = "3729b562f0935509322e8cffd684520069145420"


class SpotConfirmationJSONReferenceTests(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.ManagedMigrationScopeTests(
            "test_terminal_history_preflight_and_verifier_open_no_financial_constructor_or_writer")
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.case.source()
        self.exchange, self.spot = self.case.add_offline_standalone_spot_extension()
        self.case.cancel_source_spot(self.spot)

    def require_typed_rejection(self, token=None, *, global_event=False, duplicate=False):
        kind = "SPOT_MATCH_CONFIRMED" if global_event else "SPOT_TRADE_CONFIRMED"
        with self.exchange.database.transaction() as connection:
            row = connection.execute("SELECT sequence,payload FROM uta_events WHERE event_type=? ORDER BY sequence DESC LIMIT 1",
                                     (kind,)).fetchone()
            original = row["payload"]
            self.assertIn('"market_version":1', original)
            if duplicate:
                raw = original.replace('"market_version":1', '"market_version":999,"market_version":1', 1)
                self.assertEqual(raw.count('"market_version":'), 2)
            else:
                raw = re.sub(r'("market_version":)1(?=[,}])', lambda match: match[1] + token, original, count=1)
                self.assertIn('"market_version":' + token, raw)
            self.assertNotEqual(raw, original)
            guard = connection.execute("SELECT sql FROM sqlite_master WHERE name='uta_events_no_update'").fetchone()[0]
            connection.execute("DROP TRIGGER uta_events_no_update")
            connection.execute("UPDATE uta_events SET payload=? WHERE sequence=?", (raw, row["sequence"]))
            connection.execute(guard)
        before = self.case.financial_state()
        spot_before = self.case.spot_state()
        verification_error = migration_error = None
        verification_result = None
        try:
            verification_result = self.spot.verify()
        except Exception as error:
            verification_error = error
        try:
            self.case.take_over()
        except Exception as error:
            migration_error = error
        manifest_present = bool(self.case.read(
            "SELECT name FROM sqlite_master WHERE name='router_durable_config'", control=True))
        current_raw = self.case.read("SELECT payload FROM uta_events WHERE sequence=?", (row["sequence"],))[0]["payload"]
        print("strict-confirmation-json", json.dumps({
            "event_kind": kind, "raw_number_token": token, "duplicate_key": duplicate,
            "raw_payload_preserved": current_raw == raw,
            "verification_result": verification_result,
            "verification_exception": None if verification_error is None else type(verification_error).__name__,
            "verification_code": getattr(verification_error, "code", None),
            "migration_exception": None if migration_error is None else type(migration_error).__name__,
            "migration_code": getattr(migration_error, "code", None),
            "manifest_present": manifest_present,
            "financial_rows_unchanged": self.case.financial_state() == before,
        }), flush=True)
        self.assertEqual(current_raw, raw, "inspection must preserve the malformed raw evidence")
        self.assertEqual(self.case.financial_state(), before)
        self.assertEqual(self.case.spot_state(), spot_before)
        self.assertIsInstance(verification_error, ServiceError,
            "malformed confirmation JSON requires a typed verifier rejection, never a raw error or acceptance")
        self.assertEqual((verification_error.code, verification_error.status), ("spot_corrupt", 503))
        self.assertIsInstance(migration_error, ServiceError)
        self.assertEqual((migration_error.code, migration_error.status), ("spot_corrupt", 503))
        self.case.assert_unsealed()

    def test_private_nan_is_a_typed_corruption_error(self):
        self.require_typed_rejection("NaN")

    def test_private_positive_infinity_is_a_typed_corruption_error(self):
        self.require_typed_rejection("Infinity")

    def test_private_negative_infinity_is_a_typed_corruption_error(self):
        self.require_typed_rejection("-Infinity")

    def test_private_exponent_overflow_is_a_typed_corruption_error(self):
        self.require_typed_rejection("1e999")

    def test_global_nan_is_a_typed_corruption_error(self):
        self.require_typed_rejection("NaN", global_event=True)

    def test_global_positive_infinity_is_a_typed_corruption_error(self):
        self.require_typed_rejection("Infinity", global_event=True)

    def test_global_negative_infinity_is_a_typed_corruption_error(self):
        self.require_typed_rejection("-Infinity", global_event=True)

    def test_global_exponent_overflow_is_a_typed_corruption_error(self):
        self.require_typed_rejection("1e999", global_event=True)

    def test_private_duplicate_key_is_rejected_before_sealing(self):
        self.require_typed_rejection(duplicate=True)

    def test_global_duplicate_key_is_rejected_before_sealing(self):
        self.require_typed_rejection(global_event=True, duplicate=True)


if __name__ == "__main__":
    unittest.main()
