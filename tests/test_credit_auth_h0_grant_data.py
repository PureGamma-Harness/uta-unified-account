"""Actual retained-data corruption regressions on self-owned AuthDBs only."""
from contextlib import closing
from dataclasses import replace
import hashlib
import json
import secrets
import time
import sqlite3
import unittest

import test_credit_auth_h0 as base
from uta.credit_auth_h0 import CreditNonceStoreV2
from uta.request_signing import SigningError, SigningKey
from uta.storage import StorageError


class GrantDataVerificationTests(unittest.TestCase):
    def setUp(self):
        self.fx = base.CreditAuthH0Tests('test_H0_I01_legacy_format1_real_positive_and_return_contract')
        self.fx.setUp()
        self.addCleanup(self.fx.doCleanups)

    def mutate(self, store, table, clause, parameters):
        """Only a completed owned fixture is changed; exact guards are restored."""
        with closing(sqlite3.connect(store.database.path, isolation_level=None)) as connection:
            connection.execute('PRAGMA foreign_keys=ON')
            before = connection.execute('SELECT type,name,tbl_name,sql FROM main.sqlite_master ORDER BY type,name').fetchall()
            guard = connection.execute('SELECT sql FROM main.sqlite_master WHERE name=?', (table+'_no_update',)).fetchone()[0]
            connection.execute('BEGIN IMMEDIATE')
            connection.execute('DROP TRIGGER main.'+table+'_no_update')
            connection.execute('UPDATE main.'+table+' '+clause, parameters)
            connection.execute(guard)
            connection.commit()
            after = connection.execute('SELECT type,name,tbl_name,sql FROM main.sqlite_master ORDER BY type,name').fetchall()
            self.assertTrue(before == after)
            self.assertTrue(connection.execute('PRAGMA main.foreign_key_check').fetchall() == [])

    def refused(self, function, *args, **kwargs):
        with self.assertRaises(SigningError) as caught:function(*args, **kwargs)
        self.assertTrue(caught.exception.code == 'credit_auth_outcome_unknown')
        cause = caught.exception.__cause__
        self.assertIsInstance(cause, StorageError)
        self.assertTrue(str(cause).startswith(('retained authentication grant', 'retained authentication revocation')))

    def test_empty_payload_is_not_ignored_on_reopen_capture_query_or_control(self):
        fx = self.fx
        fx.issuer.release(fx.capture('before-corruption'))
        before = fx.counts()
        self.mutate(fx.store, 'auth_credit_grants', "SET payload='{}' WHERE grant_id=?", ('grant-0',))
        self.refused(CreditNonceStoreV2, fx.store.database.path)
        self.refused(fx.capture, 'after-corruption')
        self.refused(fx.lookup, 'before-corruption')
        self.refused(fx.store.put_grant, 'grant-0', key_id='funding', account_id='alice',
            asset='BTC', operation='credit.borrow', expected_grant_revision=4)
        self.refused(fx.store.revoke_grant, 'grant-0', expected_grant_revision=4)
        self.refused(fx.issuer.replace_profile, fx.profile_path)
        self.assertTrue(fx.counts() == before)
        with fx.store.database.read_transaction() as connection:
            self.assertTrue(connection.execute("SELECT payload FROM auth_credit_grants WHERE grant_id='grant-0'").fetchone()[0] == '{}')

    def test_canonical_wrong_epoch_bool_and_extra_field_are_refused(self):
        fx = self.fx
        for index, mutation in enumerate(('wrong-epoch', 'bool-epoch', 'extra-field', 'noncanonical')):
            store, profile, _, issuer = fx.fixture('payload-variant-'+str(index))
            with store.database.read_transaction() as connection:
                document = json.loads(connection.execute("SELECT payload FROM auth_credit_grants WHERE grant_id='grant-0'").fetchone()[0])
            if mutation == 'wrong-epoch':document['grant_epoch'] += 1
            if mutation == 'bool-epoch':document['grant_epoch'] = True
            if mutation == 'extra-field':document['unexpected'] = 'not-a-grant'
            payload = json.dumps(document, sort_keys=True, separators=(',', ':'))
            if mutation == 'noncanonical':payload += ' '
            self.mutate(store, 'auth_credit_grants', 'SET payload=? WHERE grant_id=?', (payload, 'grant-0'))
            self.refused(CreditNonceStoreV2, store.database.path)
            self.refused(fx.capture, 'new-cid', issuer=issuer, profile=profile)
            self.assertTrue(fx.counts(store)[2] == 0)

    def test_original_control_audit_epoch_key_and_event_are_verified(self):
        fx = self.fx
        for index, mutation in enumerate(('wrong-revision', 'other-key', 'wrong-event')):
            store, profile, _, issuer = fx.fixture('audit-variant-'+str(index))
            with store.database.read_transaction() as connection:
                sequence = connection.execute("SELECT audit_sequence FROM auth_credit_grants WHERE grant_id='grant-0'").fetchone()[0]
                other_identity = connection.execute("SELECT identity FROM auth_keys WHERE key_id='reader'").fetchone()[0]
            if mutation == 'wrong-revision':
                clause, parameters = 'SET grant_revision=2 WHERE sequence=?', (sequence,)
            elif mutation == 'other-key':
                clause, parameters = "SET key_id='reader',key_identity=? WHERE sequence=?", (other_identity, sequence)
            else:
                clause, parameters = "SET event='profile_configured' WHERE sequence=?", (sequence,)
            self.mutate(store, 'auth_audit', clause, parameters)
            self.refused(CreditNonceStoreV2, store.database.path)
            self.refused(fx.lookup, 'missing-cid', issuer=issuer, profile=profile)
            self.assertTrue(fx.counts(store)[2] == 0)

    def test_healthy_revoked_grant_history_keeps_original_acceptance_queryable(self):
        fx = self.fx
        original = dict(fx.issuer.inspect(fx.capture('historical-first')))
        fx.store.revoke_grant('grant-0', expected_grant_revision=4)
        fx.store.put_grant('replacement-borrow', key_id='funding', account_id='alice', asset='BTC',
            operation='credit.borrow', expected_grant_revision=5)
        unrelated = SigningKey('unrelated-reader', secrets.token_bytes(32), 'reader', 'alice',
            0, time.time_ns()//1000000+3600000)
        updated = replace(fx.profile, revision=2, keys=fx.profile.keys+(unrelated,))
        fx.write_profile(fx.profile_path, updated)
        fx.issuer.replace_profile(fx.profile_path)
        reopened = CreditNonceStoreV2(fx.store.database.path)
        self.assertTrue(reopened.audience == fx.store.audience)
        query = dict(fx.issuer.inspect(fx.lookup('historical-first')))
        self.assertTrue(query['receipt_kind'] == 'auth_query_only')
        self.assertTrue(query['first_acceptance_payload_or_null'] == original['first_acceptance_payload_or_null'])
        self.assertTrue(fx.counts()[2] == 1)


    def test_revocation_payload_refuses_reopen_idempotent_control_and_queries(self):
        fx = self.fx
        fx.issuer.release(fx.capture('before-revocation-corruption'))
        fx.store.revoke_grant('grant-0', expected_grant_revision=4)
        before = fx.counts()
        self.mutate(fx.store, 'auth_credit_grant_revocations', "SET payload='{}' WHERE grant_id=?", ('grant-0',))
        self.refused(CreditNonceStoreV2, fx.store.database.path)
        self.refused(fx.lookup, 'before-revocation-corruption')
        self.refused(fx.capture, 'still-permitted-repay', kind='repay')
        self.refused(fx.store.revoke_grant, 'grant-0', expected_grant_revision=5)
        self.assertTrue(fx.counts() == before)
        with fx.store.database.read_transaction() as connection:
            self.assertTrue(connection.execute("SELECT payload FROM auth_credit_grant_revocations WHERE grant_id='grant-0'").fetchone()[0] == '{}')

    def test_revocation_canonical_semantics_and_original_audit_binding(self):
        fx = self.fx
        for index, mutation in enumerate(('wrong-revision-payload', 'extra-field', 'audit-key', 'audit-revision', 'audit-event')):
            store, profile, _, issuer = fx.fixture('revoke-variant-'+str(index))
            store.revoke_grant('grant-0', expected_grant_revision=4)
            with store.database.read_transaction() as connection:
                row = connection.execute("SELECT * FROM auth_credit_grant_revocations WHERE grant_id='grant-0'").fetchone()
                document = json.loads(row['payload'])
                sequence = row['audit_sequence']
                identity = connection.execute("SELECT identity FROM auth_keys WHERE key_id='funding'").fetchone()[0]
            if mutation in ('wrong-revision-payload', 'extra-field'):
                if mutation == 'wrong-revision-payload':document['revocation_revision'] += 1
                else:document['unexpected'] = False
                self.mutate(store, 'auth_credit_grant_revocations', 'SET payload=? WHERE grant_id=?',
                    (json.dumps(document, sort_keys=True, separators=(',', ':')), 'grant-0'))
            else:
                if mutation == 'audit-key':clause, values = "SET key_id='funding',key_identity=? WHERE sequence=?", (identity, sequence)
                elif mutation == 'audit-revision':clause, values = 'SET grant_revision=6 WHERE sequence=?', (sequence,)
                else:clause, values = "SET event='nonce_consumed' WHERE sequence=?", (sequence,)
                self.mutate(store, 'auth_audit', clause, values)
            self.refused(CreditNonceStoreV2, store.database.path)
            self.refused(fx.capture, 'new-repay-cid', issuer=issuer, profile=profile, kind='repay')
            self.assertTrue(fx.counts(store)[2] == 0)


    def test_first_acceptance_integer_bool_with_consistent_content_id_is_refused(self):
        fx = self.fx
        fx.issuer.release(fx.capture('integer-profile-case'))
        with fx.store.database.read_transaction() as connection:
            original = connection.execute("SELECT * FROM auth_credit_acceptances WHERE command_id='integer-profile-case'").fetchone()
            document = json.loads(original['payload'])
        self.assertTrue(document['profile_revision'] == 1)
        document['profile_revision'] = True
        payload = json.dumps(document, sort_keys=True, separators=(',', ':'))
        new_id = 'auth-acceptance:'+hashlib.sha256(payload.encode()).hexdigest()
        self.mutate(fx.store, 'auth_credit_acceptances', 'SET payload=?,acceptance_id=? WHERE command_id=?',
            (payload, new_id, 'integer-profile-case'))
        before = fx.counts()
        with self.assertRaises(SigningError) as caught:fx.lookup('integer-profile-case')
        self.assertTrue(caught.exception.code == 'credit_auth_outcome_unknown')
        self.assertIsInstance(caught.exception.__cause__, StorageError)
        self.assertTrue(str(caught.exception.__cause__) == 'first authentication integer is noncanonical')
        self.assertTrue(fx.counts() == before)


if __name__ == '__main__':unittest.main()
