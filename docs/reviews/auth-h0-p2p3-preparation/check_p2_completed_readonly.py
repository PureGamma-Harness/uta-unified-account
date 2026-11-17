"""Read only completed own P2: independent literal MAC + one AuthDB snapshot.

No product imports, constructor, signing/ingress calls, or original-data writes.
Only explicit safe aggregate evidence leaves the private input directory.
"""
import argparse
import base64
from collections import Counter
from contextlib import closing
import hashlib
import hmac
import json
import os
from pathlib import Path
import sqlite3
import subprocess

SOURCE = '912f2a4e5ed74f7a3fbf892ff0172e4eacc9c45a'
RUNTIME = '5750e12d60dbf7f8414b4e837e076a60c93a23bc'
SUPERVISOR = '670bd0a1f78e8d0f9ec656aa0bd7936368aac788f1d26c95fd35e9cfaeacae9e'
P2 = 'f2ecd948ab3b5b261282dfa1650beac60c1c610da6783c65669cd79ef133b1e1'
SUPPORT = '5498be6b04d32250128c2f1edebae339180dc99b061b84eff99c3fb01e497152'
FLAGS = ('financial_authorized', 'source_delivery_authorized', 'execution_authorized')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def document(path):
    return json.loads(path.read_bytes())


def main():
    parser = argparse.ArgumentParser()
    for name in ('outer', 'source', 'bundle-root', 'result'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    outer = args.outer
    proof = {name: document(outer / name) for name in ('start-record.json', 'supervisor-owner.json',
             'probe-actual-Popen.json', 'supervisor-result.json', 'completion.json', 'probe-result.json')}
    supervisor, completion, probe = (proof[name] for name in ('supervisor-result.json', 'completion.json', 'probe-result.json'))
    assert sha(outer / 'supervisor-result.json') == completion['supervisor_result_sha256']
    assert sha(outer / 'probe-result.json') == supervisor['probe_result_sha256']
    assert completion['accepted_scoped_probe'] is True and completion['within30seconds_at_recorded_clock'] is True
    assert supervisor['subject_exit_code'] == 0 and supervisor['subject_wait_reaped'] is True
    assert supervisor['watchdog_or_control_reason'] is None and supervisor['primary_control_error'] is None
    assert supervisor['raw_hashes_final_only_if_subject_reaped'] is True
    assert supervisor['source_and_harness_unchanged'] is True and probe['source_unchanged'] is True
    assert probe['probe'] == 'P2' and probe['status'] == 'PASS' and probe['completed_step_count'] == 7
    assert probe['progress'] == {'actual_invocations': 262, 'expected_refusals': 5,
        'ordinary_accepted': 224, 'planned_invocations': 262, 'query_accepted': 32}
    assert probe['all_retained_own_thread_handles_released'] is True and probe['affinity'] == [4]
    assert supervisor['supervisor_sha256'] == SUPERVISOR
    assert sha(args.bundle_root / 'docs/reviews/auth-h0-p2p3-preparation/detached_supervisor.py') == SUPERVISOR
    assert sha(args.bundle_root / 'tests/auth_h0_p2p3_independent/default_handles_probe.py') == P2
    assert sha(args.bundle_root / 'tests/auth_h0_p2p3_independent/support.py') == SUPPORT
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=args.source, text=True).strip() == SOURCE
    for name, digest in probe['runtime_hashes_before'].items():
        raw = (args.source / name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == digest
        assert raw == subprocess.check_output(['git', 'show', RUNTIME + ':' + name], cwd=args.source)
    assert len(probe['runtime_hashes_before']) == 64
    for name, data in supervisor['private_raw_streams'].items():
        assert (outer / name).stat().st_size == data['bytes'] and sha(outer / name) == data['sha256']
    fixture = outer / 'cases' / 'default-limits'
    path = fixture / 'auth.sqlite3'
    before = {str(p.relative_to(outer)): sha(p) for p in outer.rglob('*') if p.is_file()}
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, isolation_level=None)) as c:
        c.execute('PRAGMA query_only=ON')
        c.execute('BEGIN')
        allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_PRAGMA,
                   sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_TRANSACTION}
        c.set_authorizer(lambda action, *_: sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY)
        tables = {}
        for table in ('auth_config', 'auth_keys', 'auth_nonces', 'auth_audit', 'auth_credit_grants',
                      'auth_credit_grant_revocations', 'auth_credit_acceptances'):
            cursor = c.execute('SELECT * FROM main.' + table + ' ORDER BY 1')
            columns = [column[0] for column in cursor.description]
            tables[table] = [dict(zip(columns, row)) for row in cursor.fetchall()]
        assert c.execute('PRAGMA main.foreign_key_check').fetchall() == []
        c.rollback()
    config = tables['auth_config'][0]
    assert config['format'] == 2 and config['revision'] == 1 and config['grant_revision'] == 4
    assert len(tables['auth_credit_acceptances']) == 225 and len(tables['auth_nonces']) == 262
    assert len(tables['auth_credit_grants']) == 4 and tables['auth_credit_grant_revocations'] == []
    requests = fixture / 'parent-private-requests'
    assert len(list(requests.glob('private-request-*.json'))) == 262
    profile = document(fixture / 'private-profile.json')
    keys = {key['key_id']: key for key in profile['keys']}
    nonce_rows = {(row['key_id'], row['nonce_hash']): row for row in tables['auth_nonces']}
    outcomes = Counter()
    invoked_hashes = set()
    for index in range(1, 263):
        request = document(requests / ('private-request-' + str(index) + '.json'))
        headers = request['headers']
        body = base64.b64decode(request['body_base64'], validate=True)
        key = headers['X-UTA-Key-Id']
        message = json.dumps(['UTA-HMAC-SHA256', '1', headers['X-UTA-Tenant'],
            headers['X-UTA-Audience'], key, headers['X-UTA-Timestamp-Ms'], headers['X-UTA-Nonce'],
            request['method'], request['request_target'], hashlib.sha256(body).hexdigest()],
            separators=(',', ':'), ensure_ascii=True).encode('ascii')
        encoded = keys[key]['secret_b64']
        secret = base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4))
        assert hmac.compare_digest(hmac.new(secret, message, hashlib.sha256).hexdigest(), headers['X-UTA-Signature'])
        rh = hashlib.sha256(message).hexdigest()
        nh = hashlib.sha256(headers['X-UTA-Nonce'].encode('ascii')).hexdigest()
        assert rh not in invoked_hashes
        invoked_hashes.add(rh)
        match = [row for row in tables['auth_audit'] if row['request_hash'] == rh]
        assert len(match) == 1
        audit = match[0]
        assert audit['nonce_hash'] == nh and audit['key_id'] == key
        assert audit['request_ms'] == int(headers['X-UTA-Timestamp-Ms']) and audit['event'] == 'nonce_consumed'
        assert nonce_rows[(key, nh)]['expires_ms'] == audit['request_ms'] + config['past_window']
        assert -config['future_skew'] <= audit['server_ms'] - audit['request_ms'] <= config['past_window']
        expected = ('FIRST_ACCEPTED' if index <= 224 or index == 262 else
                    'QUERY_ORIGINAL' if 227 <= index <= 258 else
                    'PERMISSION_REJECTED' if index == 226 else 'HANDLE_CAPACITY')
        assert audit['outcome'] == expected
        outcomes[expected] += 1
        if expected == 'QUERY_ORIGINAL':
            original = next(row for row in tables['auth_credit_acceptances'] if row['command_id'] == 'normal-0')
            assert audit['original_acceptance_id'] == original['acceptance_id']
            assert audit['grant_id'] == 'g-reader' and key == 'reader'
    by_sequence = {row['sequence']: row for row in tables['auth_audit']}
    for accepted in tables['auth_credit_acceptances']:
        payload = json.loads(accepted['payload'])
        assert all(payload[name] is False for name in FLAGS)
        assert accepted['acceptance_id'] == 'auth-acceptance:' + hashlib.sha256(accepted['payload'].encode()).hexdigest()
        assert payload['command_id'] == accepted['command_id'] and payload['auth_audit_sequence'] == accepted['auth_audit_sequence']
        audit = by_sequence[accepted['auth_audit_sequence']]
        assert audit['outcome'] == 'FIRST_ACCEPTED' and audit['request_hash'] == accepted['request_hash']
        assert audit['key_id'] == accepted['key_id'] == 'funding' and audit['grant_id'] == accepted['grant_id'] == 'g-borrow'
        assert audit['nonce_hash'] == accepted['nonce_hash'] and accepted['request_hash'] in invoked_hashes
    after = {str(p.relative_to(outer)): sha(p) for p in outer.rglob('*') if p.is_file()}
    assert before == after
    result = {'status': 'PASS_COMPLETED_P2_READONLY_MAC_AND_AUTHDB_CORRELATION',
        'source_commit': SOURCE, 'runtime_commit': RUNTIME, 'supervisor_sha256': SUPERVISOR,
        'actual_private_requests_literal_MAC_valid_and_audit_linked': 262,
        'retained_nonces_linked': 262, 'first_acceptances': 225, 'grant_count': 4,
        'audit_outcomes': dict(outcomes), 'query_original_identity_links': 32,
        'acceptance_authorization_flags_all_literal_false': True,
        'foreign_key_check_empty': True, 'original_private_file_hash_inventory_unchanged': True,
        'original_private_file_count': len(before), 'DB_access': 'URI mode=ro/query_only/one consistent snapshot',
        'new_auth_requests_or_product_imports_or_DB_writes': False,
        'original_result_hashes': {name: sha(outer / name) for name in proof},
        'P2_actual_execution_count': 1, 'P3_actual_status': 'NOT_RUN', 'production_approved': False}
    assert not args.result.exists()
    args.result.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
