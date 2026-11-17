"""Historical profile/control associations, with real fresh AuthDB fixtures."""
from dataclasses import replace
import secrets
import time
import unittest

import test_credit_auth_h0_grant_data as data
from uta.credit_auth_h0 import CreditNonceStoreV2
from uta.request_signing import SigningKey


class ProfileHistoryVerificationTests(unittest.TestCase):
    def setUp(self):
        self.data = data.GrantDataVerificationTests('test_healthy_revoked_grant_history_keeps_original_acceptance_queryable')
        self.data.setUp()
        self.addCleanup(self.data.doCleanups)
        self.fx = self.data.fx
        self.profile = self.fx.profile

    def advance(self, revision):
        unrelated = SigningKey('unrelated-history-'+str(revision), secrets.token_bytes(32),
            'reader', 'alice', 0, time.time_ns()//1000000+3600000)
        self.profile = replace(self.profile, revision=revision,
                               keys=self.profile.keys+(unrelated,))
        self.fx.write_profile(self.fx.profile_path, self.profile)
        self.fx.issuer.replace_profile(self.fx.profile_path)

    def test_grant_audit_cannot_claim_old_profile_after_profile2_commit(self):
        fx = self.fx
        fx.issuer.release(fx.capture('first-before-profile2'))
        self.advance(2)
        fx.store.put_grant('after-profile2', key_id='other-funding', account_id='alice',
            asset='BTC', operation='credit.borrow', expected_grant_revision=4)
        with fx.store.database.read_transaction() as connection:
            row = connection.execute("SELECT a.sequence,a.revision FROM auth_audit a JOIN auth_credit_grants g ON g.audit_sequence=a.sequence WHERE g.grant_id='after-profile2'").fetchone()
            self.assertTrue(row['revision'] == 2)
            sequence = row['sequence']
        self.data.mutate(fx.store, 'auth_audit', 'SET revision=1 WHERE sequence=?', (sequence,))
        before = fx.counts()
        self.data.refused(CreditNonceStoreV2, fx.store.database.path)
        self.data.refused(fx.lookup, 'first-before-profile2')
        self.data.refused(fx.capture, 'new-after-corruption')
        self.data.refused(fx.store.put_grant, 'after-profile2', key_id='other-funding',
            account_id='alice', asset='BTC', operation='credit.borrow', expected_grant_revision=5)
        self.assertTrue(fx.counts() == before)

    def test_revoke_audit_cannot_claim_old_profile_after_profile2_commit(self):
        fx = self.fx
        fx.issuer.release(fx.capture('first-before-revoke'))
        self.advance(2)
        fx.store.revoke_grant('grant-0', expected_grant_revision=4)
        healthy = fx.lookup('first-before-revoke')
        fx.auth_only(fx.issuer, healthy, 'auth_query_only')
        fx.issuer.release(healthy)
        with fx.store.database.read_transaction() as connection:
            row = connection.execute("SELECT a.sequence,a.revision FROM auth_audit a JOIN auth_credit_grant_revocations r ON r.audit_sequence=a.sequence WHERE r.grant_id='grant-0'").fetchone()
            self.assertTrue(row['revision'] == 2)
            sequence = row['sequence']
        self.data.mutate(fx.store, 'auth_audit', 'SET revision=1 WHERE sequence=?', (sequence,))
        before = fx.counts()
        self.data.refused(CreditNonceStoreV2, fx.store.database.path)
        self.data.refused(fx.lookup, 'first-before-revoke')
        self.data.refused(fx.capture, 'new-repay-after-corruption', kind='repay')
        self.data.refused(fx.store.revoke_grant, 'grant-0', expected_grant_revision=5)
        self.assertTrue(fx.counts() == before)

    def test_healthy_profile1_profile2_profile3_controls_preserve_old_first(self):
        fx = self.fx
        first = dict(fx.issuer.inspect(fx.capture('original-profile1')))
        self.advance(2)
        fx.store.put_grant('healthy-after-profile2', key_id='other-funding', account_id='alice',
            asset='BTC', operation='credit.borrow', expected_grant_revision=4)
        fx.store.revoke_grant('healthy-after-profile2', expected_grant_revision=5)
        self.advance(3)
        fx.store.revoke_grant('grant-0', expected_grant_revision=6)
        reopened = CreditNonceStoreV2(fx.store.database.path)
        self.assertTrue(reopened.audience == fx.store.audience)
        result = dict(fx.issuer.inspect(fx.lookup('original-profile1')))
        self.assertTrue(result['receipt_kind'] == 'auth_query_only')
        self.assertTrue(result['first_acceptance_payload_or_null'] == first['first_acceptance_payload_or_null'])
        with fx.store.database.read_transaction() as connection:
            grant = connection.execute("SELECT a.revision FROM auth_audit a JOIN auth_credit_grants g ON a.sequence=g.audit_sequence WHERE g.grant_id='healthy-after-profile2'").fetchone()[0]
            prior = connection.execute("SELECT a.revision FROM auth_audit a JOIN auth_credit_grants g ON a.sequence=g.audit_sequence WHERE g.grant_id='grant-0'").fetchone()[0]
            revocations = {r[0]:r[1] for r in connection.execute("SELECT r.grant_id,a.revision FROM auth_credit_grant_revocations r JOIN auth_audit a ON a.sequence=r.audit_sequence")}
        self.assertTrue(prior == 1 and grant == 2)
        self.assertTrue(revocations == {'healthy-after-profile2':2, 'grant-0':3})
        self.assertTrue(fx.counts()[2] == 1)


if __name__ == '__main__':unittest.main()
