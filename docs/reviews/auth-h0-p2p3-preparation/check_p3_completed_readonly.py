"""Read only own completed P3: independent real-request/marker/audit evidence."""
import argparse
import base64
from collections import Counter
from contextlib import closing
import hashlib
import hmac
import json
from pathlib import Path
import sqlite3
import subprocess

SOURCE = '912f2a4e5ed74f7a3fbf892ff0172e4eacc9c45a'
RUNTIME = '5750e12d60dbf7f8414b4e837e076a60c93a23bc'
SUPERVISOR = '670bd0a1f78e8d0f9ec656aa0bd7936368aac788f1d26c95fd35e9cfaeacae9e'
P3 = '7fd73d8a77173528f21dd94604e50437f4e91dfce4a4ab744b617cf4bf9a668d'
SUPPORT = '5498be6b04d32250128c2f1edebae339180dc99b061b84eff99c3fb01e497152'
FLAGS = ('financial_authorized', 'source_delivery_authorized', 'execution_authorized')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def document(path):
    return json.loads(path.read_bytes())


def same(first, second):
    return all(first[key] == second[key] for key in ('pid', 'birth', 'boot', 'uid'))


def main():
    parser = argparse.ArgumentParser()
    for name in ('outer', 'source', 'bundle-root', 'result'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    outer, cases = args.outer, args.outer / 'cases'
    before = {str(path.relative_to(outer)): sha(path) for path in outer.rglob('*') if path.is_file()}
    supervisor = document(outer / 'supervisor-result.json')
    completion = document(outer / 'completion.json')
    probe = document(outer / 'probe-result.json')
    subject = document(outer / 'probe-actual-Popen.json')
    worker = document(cases / 'private-worker-actual-Popen.json')
    marker = document(cases / 'private-after-commit-return.json')
    assert sha(outer / 'supervisor-result.json') == completion['supervisor_result_sha256']
    assert sha(outer / 'probe-result.json') == supervisor['probe_result_sha256']
    assert completion['accepted_scoped_probe'] is True and completion['within30seconds_at_recorded_clock'] is True
    assert supervisor['subject_exit_code'] == 0 and supervisor['subject_wait_reaped'] is True
    assert supervisor['watchdog_or_control_reason'] is None and supervisor['primary_control_error'] is None
    assert supervisor['raw_hashes_final_only_if_subject_reaped'] is True
    assert supervisor['source_and_harness_unchanged'] is True and probe['source_unchanged'] is True
    assert probe['status'] == 'PASS' and probe['completed_step_count'] == 3 and probe['affinity'] == [4]
    assert probe['detail'] == {'actual_request_count': 3, 'first_acceptance_count': 1,
        'original_first_identity_unchanged': True, 'worker_actual_exit_code': 73, 'worker_wait_reaped': True}
    assert probe['owned_worker_cleanup']['forced'] is False and probe['owned_worker_cleanup']['reaped'] is True
    assert probe['owned_worker_cleanup']['exit_code'] == 73 and probe['owned_worker_cleanup']['signals'] == []
    assert subject['pidfd_bound'] is True and worker['pidfd_bound'] is True
    assert same(subject['identity'], worker['parent_identity'])
    assert same(worker['identity'], marker['worker']) and marker['worker']['ppid'] == subject['identity']['pid']
    ready_lines = (cases / 'private-worker-stdout.txt').read_bytes().splitlines()
    assert len(ready_lines) == 1
    ready = json.loads(ready_lines[0])
    assert ready['event'] == 'READY' and same(ready['identity'], worker['identity'])
    assert ready['source_commit'] == SOURCE and ready['runtime_commit'] == RUNTIME
    assert marker['observed_real_public_capture_return'] is True and marker['next_action_self_exit'] == 73
    assert marker['physical_commit_time_inferred'] is False
    original = marker['receipt_private']
    assert all(original[name] is False for name in FLAGS)
    assert original['receipt_kind'] == 'auth_first_observation' and original['found'] is True
    assert supervisor['supervisor_sha256'] == SUPERVISOR
    assert sha(args.bundle_root / 'docs/reviews/auth-h0-p2p3-preparation/detached_supervisor.py') == SUPERVISOR
    assert sha(args.bundle_root / 'tests/auth_h0_p2p3_independent/reply_loss_probe.py') == P3
    assert sha(args.bundle_root / 'tests/auth_h0_p2p3_independent/support.py') == SUPPORT
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=args.source, text=True).strip() == SOURCE
    for name, digest in probe['runtime_hashes_before'].items():
        raw = (args.source / name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == digest
        assert raw == subprocess.check_output(['git', 'show', RUNTIME + ':' + name], cwd=args.source)
    assert len(probe['runtime_hashes_before']) == 64
    for name, data in supervisor['private_raw_streams'].items():
        assert sha(outer / name) == data['sha256'] and (outer / name).stat().st_size == data['bytes']
    fixture = cases / 'fixture'
    with closing(sqlite3.connect((fixture / 'auth.sqlite3').as_uri() + '?mode=ro', uri=True, isolation_level=None)) as c:
        c.execute('PRAGMA query_only=ON')
        c.execute('BEGIN')
        allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_PRAGMA,
                   sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_TRANSACTION}
        c.set_authorizer(lambda action, *_: sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY)
        tables = {}
        for name in ('auth_config', 'auth_keys', 'auth_nonces', 'auth_audit', 'auth_credit_grants',
                     'auth_credit_grant_revocations', 'auth_credit_acceptances'):
            cur = c.execute('SELECT * FROM main.' + name + ' ORDER BY 1')
            columns = [column[0] for column in cur.description]
            tables[name] = [dict(zip(columns, row)) for row in cur.fetchall()]
        assert c.execute('PRAGMA main.foreign_key_check').fetchall() == []
        c.rollback()
    assert len(tables['auth_credit_acceptances']) == 1 and len(tables['auth_nonces']) == 3
    assert len(tables['auth_credit_grants']) == 4 and tables['auth_credit_grant_revocations'] == []
    accepted = tables['auth_credit_acceptances'][0]
    assert accepted['payload'] == original['first_acceptance_payload_or_null']
    assert accepted['acceptance_id'] == original['first_acceptance_id']
    assert accepted['acceptance_id'] == 'auth-acceptance:' + hashlib.sha256(accepted['payload'].encode()).hexdigest()
    assert all(json.loads(accepted['payload'])[name] is False for name in FLAGS)
    config = tables['auth_config'][0]
    assert config['format'] == 2 and config['revision'] == 1 and config['grant_revision'] == 4
    keys = {key['key_id']: key for key in document(fixture / 'private-profile.json')['keys']}
    inputs = [(fixture / 'worker-private-requests/private-request-1.json', 'FIRST_ACCEPTED', 'g-borrow'),
              (fixture / 'parent-private-requests/private-request-1.json', 'QUERY_ORIGINAL', 'g-reader'),
              (fixture / 'parent-private-requests/private-request-2.json', 'QUERY_ORIGINAL', 'g-read')]
    assert len(list(fixture.rglob('private-request-*.json'))) == 3
    outcomes = Counter()
    sequences, request_hashes = [], set()
    for path, expected, grant in inputs:
        request = document(path)
        h = request['headers']
        body = base64.b64decode(request['body_base64'], validate=True)
        key = h['X-UTA-Key-Id']
        message = json.dumps(['UTA-HMAC-SHA256', '1', h['X-UTA-Tenant'], h['X-UTA-Audience'], key,
            h['X-UTA-Timestamp-Ms'], h['X-UTA-Nonce'], request['method'], request['request_target'],
            hashlib.sha256(body).hexdigest()], separators=(',', ':'), ensure_ascii=True).encode('ascii')
        encoded = keys[key]['secret_b64']
        secret = base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4))
        assert hmac.compare_digest(hmac.new(secret, message, hashlib.sha256).hexdigest(), h['X-UTA-Signature'])
        rh, nh = hashlib.sha256(message).hexdigest(), hashlib.sha256(h['X-UTA-Nonce'].encode('ascii')).hexdigest()
        assert rh not in request_hashes
        request_hashes.add(rh)
        matches = [row for row in tables['auth_audit'] if row['request_hash'] == rh]
        assert len(matches) == 1
        audit = matches[0]
        assert audit['outcome'] == expected and audit['event'] == 'nonce_consumed'
        assert audit['key_id'] == key and audit['nonce_hash'] == nh and audit['grant_id'] == grant
        assert audit['request_ms'] == int(h['X-UTA-Timestamp-Ms'])
        nonces = [row for row in tables['auth_nonces'] if row['key_id'] == key and row['nonce_hash'] == nh]
        assert len(nonces) == 1 and nonces[0]['expires_ms'] == audit['request_ms'] + config['past_window']
        assert -config['future_skew'] <= audit['server_ms'] - audit['request_ms'] <= config['past_window']
        if expected == 'QUERY_ORIGINAL':
            assert audit['original_acceptance_id'] == accepted['acceptance_id']
        else:
            assert audit['sequence'] == accepted['auth_audit_sequence'] and rh == accepted['request_hash']
        sequences.append(audit['sequence'])
        outcomes[expected] += 1
    assert sequences == sorted(sequences) and len(set(sequences)) == 3
    after = {str(path.relative_to(outer)): sha(path) for path in outer.rglob('*') if path.is_file()}
    assert before == after
    result = {'status': 'PASS_COMPLETED_P3_READONLY_MAC_MARKER_AUTHDB_CORRELATION',
        'source_commit': SOURCE, 'runtime_commit': RUNTIME, 'supervisor_sha256': SUPERVISOR,
        'literal_MAC_valid_and_audit_nonce_linked_private_requests': 3,
        'first_acceptances': 1, 'query_original_links': 2, 'grant_count': 4,
        'audit_outcomes': dict(outcomes), 'worker_exit73_actual_parent_wait_reaped': True,
        'worker_parent_ready_marker_identity_linked': True, 'application_receipt_in_worker_stdout': False,
        'GO_order_scope': 'fixed source path plus READY/marker/exit73; no separately timestamped GO record',
        'physical_commit_epoch_claimed': False, 'all_acceptance_flags_literal_false': True,
        'foreign_key_check_empty': True, 'original_private_file_hash_inventory_unchanged': True,
        'original_private_file_count': len(before), 'DB_access': 'URI mode=ro/query_only/one consistent snapshot',
        'new_auth_requests_or_product_imports_or_DB_writes': False,
        'worker_identity_safe': worker['identity'], 'parent_identity_safe': worker['parent_identity'],
        'actual_run_count': 1, 'midCOMMIT_powerloss_financial_or_HA_tested': False,
        'original_result_hashes': {name: sha(outer / name) for name in
            ('start-record.json','supervisor-owner.json','probe-actual-Popen.json','supervisor-result.json','completion.json','probe-result.json')},
        'private_marker_and_READY_hashes_only': {'marker': sha(cases / 'private-after-commit-return.json'),
                                               'READY': sha(cases / 'private-worker-stdout.txt'),
                                               'worker_Popen': sha(cases / 'private-worker-actual-Popen.json')},
        'production_approved': False}
    assert not args.result.exists()
    args.result.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
