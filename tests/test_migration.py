import copy
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from uta.migration import MigrationError, ShadowMigrationStore, build_shadow

NOW = datetime(2026, 11, 14, 0, 0, tzinfo=timezone.utc)


def sample():
    return {
        "account_id": "classic-1", "version": 4,
        "captured_at": "2026-11-14T00:00:00Z",
        "compartments": {
            "spot": {"balances": [{"asset": "BTC", "free": "2", "locked": "0.1", "borrowed": "0", "interest": "0"}]},
            "margin": {"balances": [{"asset": "USDT", "free": "100", "locked": "10", "borrowed": "30", "interest": "0.25"}]},
            "futures": {"balances": [], "positions": [{"symbol": "BTCUSDT", "quantity": "-0.2", "entry_price": "90000"}]},
        },
    }


class MigrationTests(unittest.TestCase):
    def test_reconciles_each_field_and_preserves_source_compartment(self):
        result = build_shadow(sample(), now=NOW)
        self.assertEqual(result.account_id, "classic-1")
        balances = {(b.compartment, b.asset): b for b in result.balances}
        self.assertEqual((balances[('spot', 'BTC')].free, balances[('spot', 'BTC')].locked),
                         (Decimal('2'), Decimal('0.1')))
        self.assertEqual((balances[('margin', 'USDT')].borrowed, balances[('margin', 'USDT')].interest),
                         (Decimal('30'), Decimal('0.25')))
        self.assertEqual((result.positions[0].quantity, result.positions[0].entry_price),
                         (Decimal('-0.2'), Decimal('90000')))

    def test_incomplete_invalid_or_stale_snapshot_fails_closed(self):
        bad = []
        x = sample(); del x['compartments']['margin']; bad.append(x)
        x = sample(); del x['compartments']['spot']['balances'][0]['interest']; bad.append(x)
        x = sample(); x['compartments']['spot']['balances'][0]['free'] = 2.0; bad.append(x)
        x = sample(); x['compartments']['spot']['balances'][0]['free'] = 'NaN'; bad.append(x)
        x = sample(); x['compartments']['spot']['balances'][0]['borrowed'] = '-1'; bad.append(x)
        x = sample(); x['compartments']['futures']['positions'][0]['entry_price'] = '0'; bad.append(x)
        x = sample(); x['compartments']['futures']['positions'][0]['quantity'] = '0'; bad.append(x)
        x = sample(); x['captured_at'] = '2026-11-13T23:59:29Z'; bad.append(x)
        x = sample(); x['captured_at'] = '2026-11-14T00:00:03Z'; bad.append(x)
        x = sample(); x['captured_at'] = '2026-11-14T00:00:00'; bad.append(x)
        x = sample(); x['version'] = True; bad.append(x)
        x = sample(); x['compartments']['spot']['balances'].append(copy.deepcopy(x['compartments']['spot']['balances'][0])); bad.append(x)
        x = sample(); x['compartments']['futures']['positions'].append(copy.deepcopy(x['compartments']['futures']['positions'][0])); bad.append(x)
        store = ShadowMigrationStore()
        for snapshot in bad:
            with self.subTest(snapshot=snapshot), self.assertRaises(MigrationError):
                store.apply(snapshot, 'k', now=NOW)
        self.assertIsNone(store.get('classic-1'))

    def test_idempotency_and_version_ordering(self):
        store = ShadowMigrationStore()
        original = sample()
        mirror = store.apply(original, 'request-1', now=NOW)
        equivalent = sample(); equivalent['compartments']['spot']['balances'][0]['free'] = '2.00'
        self.assertIs(store.apply(equivalent, 'request-1', now=NOW), mirror)
        self.assertIs(store.apply(equivalent, 'request-2', now=NOW), mirror)
        conflict = sample(); conflict['compartments']['spot']['balances'][0]['free'] = '3'
        with self.assertRaises(MigrationError): store.apply(conflict, 'request-1', now=NOW)
        with self.assertRaises(MigrationError): store.apply(conflict, 'new-key', now=NOW)
        newer = sample(); newer['version'] = 5
        latest = store.apply(newer, 'request-3', now=NOW)
        with self.assertRaises(MigrationError): store.apply(original, 'unused-key', now=NOW)
        # A retry is an immutable receipt, not a rollback of the current state.
        self.assertIs(store.apply(original, 'request-1', now=NOW), mirror)
        self.assertIs(store.get('classic-1'), latest)

    def test_decimal_digest_preserves_precision_beyond_default_context(self):
        a = sample(); b = sample()
        a['compartments']['spot']['balances'][0]['free'] = '1.1234567890123456789012345678901'
        b['compartments']['spot']['balances'][0]['free'] = '1.1234567890123456789012345678902'
        self.assertNotEqual(build_shadow(a, now=NOW).source_digest, build_shadow(b, now=NOW).source_digest)

    def test_retry_must_still_be_fresh(self):
        store = ShadowMigrationStore()
        store.apply(sample(), 'k', now=NOW)
        with self.assertRaises(MigrationError):
            store.apply(sample(), 'k', now=NOW + timedelta(seconds=31))


if __name__ == '__main__':
    unittest.main()
