"""One independent auth-only integrity negative, real constructors/literal MAC."""
import argparse
import base64
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--private', type=Path, required=True)
parser.add_argument('--result', type=Path, required=True)
args = parser.parse_args()
args.private.mkdir(mode=0o700, exist_ok=False)
sys.path.insert(0, str(args.source))
from uta.credit_auth_h0 import CreditNonceStoreV2, CreditHmacIngressV2
from uta.request_signing import SigningError

tenant, account, domain, key_id = 'independent-tenant', 'independent-account', 'independent-domain', 'independent-funding'
producer = '9' * 64
secret = secrets.token_bytes(32)
now = time.time_ns() // 1000000
store = CreditNonceStoreV2.initialize(args.private/'auth.sqlite3', tenant_id=tenant,
    producer_binding=producer, domain_id=domain, account_id=account)
profile = {'format':1, 'tenant_id':tenant, 'audience':store.audience, 'revision':1,
    'keys':[{'key_id':key_id, 'secret_b64':base64.urlsafe_b64encode(secret).decode().rstrip('='),
        'role':'funding', 'account_id':account, 'not_before_ms':0,
        'expires_at_ms':now+3600000, 'revoked':False}]}
profile_path = args.private/'private-profile.json'
fd = os.open(profile_path, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as stream:
    json.dump(profile, stream)
scope = dict(tenant_id=tenant, producer_binding=producer, domain_id=domain,
             domain_epoch=1, account_id=account, enabled=True)
issuer = CreditHmacIngressV2(store.database.path, profile_path, **scope)
for index, operation in enumerate(('credit.borrow', 'credit.read')):
    issuer.store.put_grant('independent-grant-'+str(index), key_id=key_id,
        account_id=account, asset='BTC', operation=operation, expected_grant_revision=index)

request_index = 0
def request(command_id, lookup=False):
    global request_index
    request_index += 1
    method = 'GET' if lookup else 'POST'
    target = '/v2/accounts/'+account+('/credit/commands/'+command_id if lookup else '/borrow')
    body = b'' if lookup else json.dumps({'command_id':command_id, 'asset':'BTC', 'amount':'0.4'},
                                        sort_keys=True, separators=(',', ':')).encode()
    timestamp = time.time_ns() // 1000000
    nonce = secrets.token_urlsafe(24)
    # Literal public v1 specification, not a production signer/canonical helper.
    canonical = json.dumps(['UTA-HMAC-SHA256', '1', tenant, store.audience, key_id,
        str(timestamp), nonce, method, target, hashlib.sha256(body).hexdigest()],
        separators=(',', ':'), ensure_ascii=True).encode('ascii')
    headers = {'Authorization':'UTA-HMAC-SHA256', 'X-UTA-Version':'1', 'X-UTA-Tenant':tenant,
        'X-UTA-Audience':store.audience, 'X-UTA-Key-Id':key_id,
        'X-UTA-Timestamp-Ms':str(timestamp), 'X-UTA-Nonce':nonce,
        'X-UTA-Signature':hmac.new(secret, canonical, hashlib.sha256).hexdigest()}
    # Real request bytes remain private, so this fresh path can be replay-checked.
    private_record = {'headers':headers, 'method':method, 'request_target':target,
                      'body_base64':base64.b64encode(body).decode()}
    descriptor = os.open(args.private/f'private-request-{request_index}.json',
                         os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as stream:json.dump(private_record, stream)
    return headers, dict(method=method, request_target=target, body=body)

def capture(command_id, current=issuer):
    headers, fields = request(command_id)
    return current.capture(headers, **fields)

handle = capture('independent-baseline')
baseline = issuer.inspect(handle)
assert baseline['receipt_kind'] == 'auth_first_observation'
assert all(baseline[name] is False for name in
    ('financial_authorized','source_delivery_authorized','execution_authorized'))
issuer.release(handle)
path = Path(store.database.path)
with closing(sqlite3.connect(path, isolation_level=None)) as connection:
    before_catalogue = connection.execute('SELECT type,name,tbl_name,sql FROM main.sqlite_master ORDER BY type,name').fetchall()
    before_count = connection.execute('SELECT COUNT(*) FROM main.auth_credit_acceptances').fetchone()[0]
    original = connection.execute("SELECT sql FROM main.sqlite_master WHERE name='auth_credit_grants_no_update'").fetchone()[0]
    original_payload = connection.execute("SELECT payload FROM main.auth_credit_grants WHERE grant_id='independent-grant-0'").fetchone()[0]
    original_copy = args.private/'original-before-corruption.sqlite3'
    with closing(sqlite3.connect(original_copy)) as target:connection.backup(target)
    os.chmod(original_copy, 0o600)
    connection.execute('BEGIN IMMEDIATE')
    connection.execute('DROP TRIGGER main.auth_credit_grants_no_update')
    connection.execute("UPDATE main.auth_credit_grants SET payload='{}' WHERE grant_id='independent-grant-0'")
    connection.execute(original)
    connection.commit()
    after_catalogue = connection.execute('SELECT type,name,tbl_name,sql FROM main.sqlite_master ORDER BY type,name').fetchall()
    after_fk = connection.execute('PRAGMA main.foreign_key_check').fetchall()
    assert before_catalogue == after_catalogue and after_fk == []
    assert original_payload != '{}'

result = {'case':'independent-grant-payload-corruption',
    'source_runtime_commit':'072cc77c5a96b48c81a143020ab8ac6c9a794a9b',
    'baseline_literal_hmac_authentication_succeeded':True,
    'all_baseline_authorization_flags_false':True,
    'only_one_grant_payload_changed':True,
    'exact_main_catalogue_unchanged':before_catalogue==after_catalogue,
    'foreign_key_check_empty':after_fk==[], 'loader_reopened':False,
    'query_issued_after_corruption':False, 'new_acceptance_after_corruption':False,
    'corruption_refused':False, 'no_financial_authority_or_effect':True}
try:
    CreditNonceStoreV2(path)
    result['loader_reopened'] = True
    restarted = CreditHmacIngressV2(path, profile_path, **scope)
    headers, fields = request('independent-baseline', lookup=True)
    query = restarted.lookup(headers, **fields)
    query_record = restarted.inspect(query)
    result['query_issued_after_corruption'] = query_record['receipt_kind'] == 'auth_query_only'
    restarted.release(query)
    new_handle = capture('independent-after-corruption', current=restarted)
    new_record = restarted.inspect(new_handle)
    result['new_acceptance_after_corruption'] = new_record['receipt_kind'] == 'auth_first_observation'
    result['all_new_authorization_flags_false'] = all(new_record[name] is False for name in
        ('financial_authorized','source_delivery_authorized','execution_authorized'))
    restarted.release(new_handle)
except SigningError as error:
    result['corruption_refused'] = True
    result['typed_error_code'] = error.code
with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as connection:
    connection.execute('PRAGMA query_only=ON')
    connection.execute('BEGIN')
    result['acceptances_before_corruption'] = before_count
    result['acceptances_after_probe'] = connection.execute('SELECT COUNT(*) FROM main.auth_credit_acceptances').fetchone()[0]
    result['corrupt_payload_still_present'] = connection.execute("SELECT payload FROM main.auth_credit_grants WHERE grant_id='independent-grant-0'").fetchone()[0] == '{}'
    connection.rollback()
result['finished_at'] = datetime.now(timezone.utc).isoformat()
args.result.write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result))
assert result['corruption_refused'], 'grant payload corruption was accepted despite normative full grant payload equality'
