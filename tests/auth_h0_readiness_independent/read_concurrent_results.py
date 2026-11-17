"""Only read completed P1 private authorities/requests; no product import."""
import argparse,base64,hashlib,hmac,json,sqlite3
from contextlib import closing
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('--outer',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
report=json.loads((a.outer/'probe-result.json').read_text());assert report['status']=='PASS' and report['case_count']==4
supervisor=json.loads((a.outer/'supervisor-result.json').read_text());completion=json.loads((a.outer/'completion.json').read_text())
assert supervisor['owned_child_wait_reaped'] is True and supervisor['child_exit_code']==0 and supervisor['watchdog_reason'] is None
assert completion['accepted_scoped_P1'] is True
assert hashlib.sha256((a.outer/'supervisor-result.json').read_bytes()).hexdigest()==completion['supervisor_result_sha256']
for name,meta in supervisor['raw_private_streams'].items():
    raw=(a.outer/name).read_bytes();assert len(raw)==meta['bytes'] and hashlib.sha256(raw).hexdigest()==meta['sha256']
cases=[];macs=0
for directory in sorted((a.outer/'cases').iterdir()):
    with closing(sqlite3.connect((directory/'auth.sqlite3').as_uri()+'?mode=ro',uri=True,isolation_level=None)) as c:
        c.execute('PRAGMA query_only=ON');c.execute('BEGIN')
        allowed={sqlite3.SQLITE_SELECT,sqlite3.SQLITE_READ,sqlite3.SQLITE_PRAGMA,sqlite3.SQLITE_FUNCTION,sqlite3.SQLITE_TRANSACTION}
        c.set_authorizer(lambda action,*_:sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY)
        data={}
        for table in ('auth_config','auth_keys','auth_audit','auth_credit_grants','auth_credit_grant_revocations','auth_credit_acceptances'):
            cur=c.execute('SELECT * FROM main.'+table+' ORDER BY 1');names=[d[0] for d in cur.description]
            data[table]=[dict(zip(names,r)) for r in cur.fetchall()]
        assert c.execute('PRAGMA main.foreign_key_check').fetchall()==[]
        c.rollback()
    profiles=sorted((r['sequence'],r['revision']) for r in data['auth_audit']
        if r['event']=='profile_configured' and r['outcome']=='CONTROL' and r['request_kind']=='CONTROL')
    for record in data['auth_credit_acceptances']:
        latest=max(row for row in profiles if row[0]<record['auth_audit_sequence'])[1]
        assert latest==record['profile_revision']
        evidence=json.loads(record['payload']);assert all(evidence[n] is False for n in
            ('financial_authorized','source_delivery_authorized','execution_authorized'))
        assert record['acceptance_id']=='auth-acceptance:'+hashlib.sha256(record['payload'].encode()).hexdigest()
    for control in data['auth_audit']:
        if control['event'] in ('grant_created','grant_revoked'):
            assert max(row for row in profiles if row[0]<control['sequence'])[1]==control['revision']
    if directory.name=='profile-revoke-vs-capture':
        profile2=next(r for r in data['auth_audit'] if r['event']=='profile_configured' and r['revision']==2)
        assert data['auth_keys'][0]['key_id']=='funding' and data['auth_keys'][0]['revoked']==1
        if data['auth_credit_acceptances']:
            assert data['auth_credit_acceptances'][0]['auth_audit_sequence']<profile2['sequence']
    if directory.name in ('borrow-grant-revoke-vs-same-cid-retry','read-grant-revoke-vs-current-lookup'):
        assert len(data['auth_credit_acceptances'])==1 and len(data['auth_credit_grant_revocations'])==1
    profiles_private=[json.loads(path.read_text()) for path in directory.glob('private-profile*.json')]
    secrets_by_key={}
    for profile in profiles_private:
        for key in profile['keys']:
            secret=base64.urlsafe_b64decode(key['secret_b64']+'='*(-len(key['secret_b64'])%4))
            if key['key_id'] in secrets_by_key:assert secrets_by_key[key['key_id']]==secret
            secrets_by_key[key['key_id']]=secret
    for path in directory.glob('private-request-*.json'):
        request=json.loads(path.read_text());h=request['headers'];body=base64.b64decode(request['body_base64'])
        literal=json.dumps(['UTA-HMAC-SHA256','1',h['X-UTA-Tenant'],h['X-UTA-Audience'],h['X-UTA-Key-Id'],h['X-UTA-Timestamp-Ms'],h['X-UTA-Nonce'],request['method'],request['request_target'],hashlib.sha256(body).hexdigest()],separators=(',',':'),ensure_ascii=True).encode('ascii')
        assert hmac.compare_digest(hmac.new(secrets_by_key[h['X-UTA-Key-Id']],literal,hashlib.sha256).hexdigest(),h['X-UTA-Signature']);macs+=1
    cases.append({'case':directory.name,'read_only_snapshot':True,'foreign_keys_clean':True,
        'actual_audit_sequence_profile_and_control_checks_passed':True,
        'retained_auth_acceptances':len(data['auth_credit_acceptances']),
        'profile_revisions':[row[1] for row in profiles]})
out={'source_commit':report['source_commit'],'runtime_commit':report['runtime_commit'],
    'supervisor_result_and_raw_hashes_match':True,'case_count':len(cases),'cases':cases,
    'private_exact_request_macs_independently_recomputed':macs,'actual_private_secret_values_exported':False,
    'statement_authorizer_read_only':True,'consistent_snapshot_each_finished_authority':True,
    'only_observed_schedules_checked':True,'no_product_import_or_financial_scope':True,'production_approved':False}
a.output.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
