"""Independent read-only finished-state and retained private MAC checks."""
import argparse
import base64
from contextlib import closing
import hashlib
import hmac
import json
from pathlib import Path
import sqlite3

p=argparse.ArgumentParser();p.add_argument('--private',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
def read(path):
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,isolation_level=None)) as c:
        c.execute('PRAGMA query_only=ON');c.execute('BEGIN')
        allowed={sqlite3.SQLITE_SELECT,sqlite3.SQLITE_READ,sqlite3.SQLITE_PRAGMA,sqlite3.SQLITE_FUNCTION,sqlite3.SQLITE_TRANSACTION}
        c.set_authorizer(lambda action,*_:sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY)
        data={}
        for table in ('auth_config','auth_keys','auth_nonces','auth_audit','auth_credit_grants','auth_credit_grant_revocations','auth_credit_acceptances'):
            cursor=c.execute('SELECT * FROM main.'+table+' ORDER BY 1');names=[d[0] for d in cursor.description]
            data[table]=[dict(zip(names,row)) for row in cursor.fetchall()]
        catalogue=c.execute('SELECT type,name,tbl_name,sql FROM main.sqlite_master ORDER BY type,name').fetchall()
        fk=c.execute('PRAGMA main.foreign_key_check').fetchall();c.rollback()
    return data,catalogue,fk
private=args.private/'cases';name='grant-audit-stale-prior-profile'
before,bcat,bfk=read(private/name/'before-corruption.sqlite3');after,acat,afk=read(private/name/'auth.sqlite3')
assert bcat==acat and bfk==afk==[]
for table in ('auth_keys','auth_credit_grants','auth_credit_grant_revocations'):
    assert before[table]==after[table]
ba={r['sequence']:r for r in before['auth_audit']};aa={r['sequence']:r for r in after['auth_audit']}
deltas=[(seq,key) for seq,row in ba.items() for key,value in row.items() if aa[seq][key]!=value]
assert len(deltas)==1 and deltas[0][1]=='revision'
assert ba[deltas[0][0]]['revision']==2 and aa[deltas[0][0]]['revision']==1
old_accept={r['acceptance_id']:r for r in before['auth_credit_acceptances']}
new_accept={r['acceptance_id']:r for r in after['auth_credit_acceptances']}
assert all(new_accept[key]==row for key,row in old_accept.items())
def latest_mismatches(data):
    profiles=sorted((r['sequence'],r['revision']) for r in data['auth_audit'] if r['event']=='profile_configured' and r['outcome']=='CONTROL')
    mismatches=[]
    for control in data['auth_audit']:
        if control['event'] not in ('grant_created','grant_revoked'):continue
        preceding=[r for r in profiles if r[0]<control['sequence']]
        expected=max(preceding)[1] if preceding else None
        if control['revision']!=expected:
            mismatches.append({'event':control['event'],'audit_sequence':control['sequence'],
                'expected_latest_preceding_profile_revision':expected,'actual_control_revision':control['revision']})
    return mismatches
assert latest_mismatches(before)==[]
mismatches=latest_mismatches(after);assert len(mismatches)==1
checks=0
for directory in sorted(private.iterdir()):
    profile=json.loads((directory/'private-profile.json').read_text());keys={r['key_id']:r for r in profile['keys']}
    for request_file in sorted(directory.glob('private-request-*.json')):
        row=json.loads(request_file.read_text());headers=row['headers'];key=keys[headers['X-UTA-Key-Id']]
        secret=base64.urlsafe_b64decode(key['secret_b64']+'='*(-len(key['secret_b64'])%4))
        body=base64.b64decode(row['body_base64'])
        message=json.dumps(['UTA-HMAC-SHA256','1',headers['X-UTA-Tenant'],headers['X-UTA-Audience'],
            headers['X-UTA-Key-Id'],headers['X-UTA-Timestamp-Ms'],headers['X-UTA-Nonce'],
            row['method'],row['request_target'],hashlib.sha256(body).hexdigest()],
            separators=(',',':'),ensure_ascii=True).encode('ascii')
        assert hmac.compare_digest(hmac.new(secret,message,hashlib.sha256).hexdigest(),headers['X-UTA-Signature'])
        assert headers['X-UTA-Tenant']==profile['tenant_id'] and headers['X-UTA-Audience']==profile['audience']
        checks+=1
result={'runtime_commit':'61258109e10f4ea4609e03010d5f25716b2c4256',
 'finished_independent_databases_only':True,'read_only_uri_query_only_authorizer_one_snapshot_each':True,
 'exact_catalogue_equal':True,'foreign_key_checks_empty':True,'all_key_grant_revocation_rows_unchanged':True,
 'all_original_acceptance_rows_unchanged':True,'only_old_audit_row_delta':'one grant_created revision 2 -> 1',
 'healthy_before_latest_profile_check_passed':True,'new_stale_profile_mismatches':mismatches,
 'before_table_counts':{k:len(v) for k,v in before.items()},'after_table_counts':{k:len(v) for k,v in after.items()},
 'independent_exact_private_request_mac_checks':checks,'actual_key_nonce_signature_values_exported':False,
 'author_original_historical_mac_verified':False,'financial_scope':False,'production_approved':False}
args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
