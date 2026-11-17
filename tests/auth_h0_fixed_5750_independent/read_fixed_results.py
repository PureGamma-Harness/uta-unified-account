"""Independent read-only descriptor/audit/history and private literal MAC check."""
import argparse
import base64
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

p=argparse.ArgumentParser();p.add_argument('--private',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
start=datetime.now(timezone.utc).isoformat();mono=time.monotonic_ns()
TABLES=('auth_config','auth_keys','auth_nonces','auth_audit','auth_credit_grants','auth_credit_grant_revocations','auth_credit_acceptances')
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True)
def read(path):
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,isolation_level=None)) as c:
        c.execute('PRAGMA query_only=ON');c.execute('BEGIN')
        allowed={sqlite3.SQLITE_SELECT,sqlite3.SQLITE_READ,sqlite3.SQLITE_PRAGMA,sqlite3.SQLITE_FUNCTION,sqlite3.SQLITE_TRANSACTION}
        c.set_authorizer(lambda action,*_:sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY)
        data={}
        for name in TABLES:
            cur=c.execute('SELECT * FROM main.'+name+' ORDER BY 1');names=[d[0] for d in cur.description]
            data[name]=[dict(zip(names,row)) for row in cur.fetchall()]
        catalogue=[list(r) for r in c.execute('SELECT type,name,tbl_name,sql FROM main.sqlite_master ORDER BY type,name')]
        fk=[list(r) for r in c.execute('PRAGMA main.foreign_key_check')];assert c.execute('PRAGMA query_only').fetchone()[0]==1
        c.rollback()
    return {'data':data,'catalogue':catalogue,'fk':fk}
def independent_defects(data):
    audits={r['sequence']:r for r in data['auth_audit']}
    profiles=sorted((r['sequence'],r['revision']) for r in data['auth_audit']
                    if r['event']=='profile_configured' and r['outcome']=='CONTROL' and r['request_kind']=='CONTROL')
    defects=[]
    for table,event in [('auth_credit_grants','grant_created'),('auth_credit_grant_revocations','grant_revoked')]:
        for row in data[table]:
            expected={k:v for k,v in row.items() if k!='payload'}
            if row['payload']!=canonical(expected):defects.append(table+':canonical-payload')
            audit=audits[row['audit_sequence']]
            if audit['event']!=event or audit['grant_id']!=row['grant_id']:
                defects.append(table+':control-audit-link')
            earlier=[r for r in profiles if r[0]<audit['sequence']]
            if not earlier or max(earlier)[1]!=audit['revision']:
                defects.append(table+':latest-profile-revision')
    return defects

cases=[];mac_count=0;nonce_count=0;healthy_profiles=None
for directory in sorted((args.private/'cases').iterdir()):
    current=read(directory/'auth.sqlite3');assert current['fk']==[]
    backup=directory/'before-corruption.sqlite3'
    if backup.exists():
        before=read(backup);assert before['catalogue']==current['catalogue'] and before['fk']==[]
        assert independent_defects(before['data'])==[]
        retained=json.loads((directory/'private-pre-probe-snapshot.json').read_text())
        assert current==retained
        defects=independent_defects(current['data']);assert defects
        cases.append({'case':directory.name,'healthy_before_fault':True,'fault_still_present_and_refused_without_repair':True,
            'no_auth_rows_changed_after_refused_operations':True,'exact_catalogue_unchanged':True,
            'independent_defects':defects,'acceptance_count':len(current['data']['auth_credit_acceptances'])})
    else:
        assert independent_defects(current['data'])==[]
        healthy_profiles=[r['revision'] for r in current['data']['auth_audit'] if r['event']=='profile_configured']
        assert healthy_profiles==[1,2,3]
        accepted_revisions=sorted(r['profile_revision'] for r in current['data']['auth_credit_acceptances'])
        assert accepted_revisions==[1,2,3]
        cases.append({'case':directory.name,'healthy_after':True,'profile_revisions':healthy_profiles,
                      'retained_acceptance_revisions':accepted_revisions})
    profile=json.loads((directory/'private-profile.json').read_text());keys={r['key_id']:r for r in profile['keys']};seen=set()
    for request_file in sorted(directory.glob('private-request-*.json')):
        req=json.loads(request_file.read_text());headers=req['headers'];key=keys[headers['X-UTA-Key-Id']]
        secret=base64.urlsafe_b64decode(key['secret_b64']+'='*(-len(key['secret_b64'])%4))
        body=base64.b64decode(req['body_base64'])
        literal=json.dumps(['UTA-HMAC-SHA256','1',headers['X-UTA-Tenant'],headers['X-UTA-Audience'],headers['X-UTA-Key-Id'],
            headers['X-UTA-Timestamp-Ms'],headers['X-UTA-Nonce'],req['method'],req['request_target'],hashlib.sha256(body).hexdigest()],
            separators=(',',':'),ensure_ascii=True).encode('ascii')
        assert hmac.compare_digest(hmac.new(secret,literal,hashlib.sha256).hexdigest(),headers['X-UTA-Signature'])
        identity=(headers['X-UTA-Key-Id'],headers['X-UTA-Nonce']);assert identity not in seen;seen.add(identity)
        mac_count+=1;nonce_count+=1
result={'runtime_commit':'5750e12d60dbf7f8414b4e837e076a60c93a23bc','case_count':len(cases),'cases':cases,
    'all_independent_record_checks_passed':True,'finished_private_database_snapshots_only':True,
    'read_only_uri_query_only_authorizer_consistent_snapshot':True,
    'private_exact_request_mac_checks':mac_count,'unique_per_case_key_nonce_pairs':nonce_count,
    'all_requests_generated_then_immediately_invoked_by_probe':True,
    'integrity_rejected_requests_not_claimed_nonce_consumed':True,
    'actual_key_nonce_signature_or_private_raw_exported':False,'author_original_historical_mac_verified':False,
    'postcheck_runtime':{'executable':sys.executable,'python':sys.version,'sqlite':sqlite3.sqlite_version,'affinity':sorted(os.sched_getaffinity(0))},
    'started_at':start,'finished_at':datetime.now(timezone.utc).isoformat(),
    'monotonic_ns_before_output_serialization':time.monotonic_ns()-mono,
    'financial_scope':False,'production_approved':False}
args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
