"""Independent real auth-COMMIT/unknown-reply boundary; no financial database."""
from contextlib import contextmanager
import hashlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tests import test_credit_hmac_source as fixtures
from uta.request_signing import SigningError
from uta.storage import StorageError


class IndependentNonceReplyBoundaryTests(unittest.TestCase):
    def test_committed_nonce_with_unknown_reply_mints_no_candidate_and_requires_new_nonce(self):
        fixture = fixtures.CreditHmacSourceTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        headers, request = fixture.request()
        database = fixture.issuer._authenticator.store.database
        transaction = database.transaction
        completed = []

        @contextmanager
        def committed_then_reply_unknown(*args, **kwargs):
            with transaction(*args, **kwargs) as connection:
                yield connection
            completed.append('real_auth_transaction_committed')
            raise StorageError('synthetic lost authentication transaction response')

        with patch.object(database, 'transaction', committed_then_reply_unknown):
            with self.assertRaises(SigningError) as unknown:
                fixture.issuer.issue(headers, **request)
        self.assertEqual(unknown.exception.code, 'signing_store_unavailable')
        self.assertEqual(completed, ['real_auth_transaction_committed'])
        self.assertEqual(len(fixture.issuer._commands), 0)
        self.assertEqual(len(fixture.issuer._receipts), 0)
        nonce_hash = hashlib.sha256(headers['X-UTA-Nonce'].encode('ascii')).hexdigest()
        with fixture.store.database.read_transaction() as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM auth_nonces').fetchone()[0], 1)
            actual = connection.execute('SELECT event,nonce_hash FROM auth_audit WHERE event=\'nonce_consumed\'').fetchall()
            self.assertEqual([tuple(row) for row in actual], [('nonce_consumed', nonce_hash)])
        # The original signed request was consumed despite the missing reply.
        with self.assertRaises(SigningError) as replayed:
            fixture.issuer.issue(headers, **request)
        self.assertEqual(replayed.exception.code, 'request_replayed')
        self.assertEqual(len(fixture.issuer._commands), 0)
        # A fresh nonce keeps the same business CID; no durable source is claimed.
        receipt = fixture.issue()
        exported = fixture.issuer.inspect(receipt, **fixture.identity())
        self.assertEqual(exported['command_id'], 'c1')
        self.assertFalse(exported['financial_authorized'])
        self.assertEqual(exported['revocation_barrier'], 'NO_GO')
        self.assertNotEqual(exported['nonce_hash'], nonce_hash)
        self.assertEqual(len(fixture.issuer._commands), 1)
        with fixture.store.database.read_transaction() as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM auth_nonces').fetchone()[0], 2)
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertFalse(any('credit' in name or 'inbox' in name for name in tables))


if __name__ == '__main__':
    unittest.main(verbosity=2)
