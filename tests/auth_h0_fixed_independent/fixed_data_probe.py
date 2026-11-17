"""Independent source-pinned fresh AuthDB cases; literal protocol/HMAC reference."""
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

parser=argparse.ArgumentParser()
parser.add_argument('--source',type=Path,required=True)
parser.add_argument('--private',type=Path,required=True)
parser.add_argument('--result',type=Path,required=True)
args=parser.parse_args();args.private.mkdir(mode=0o700,exist_ok=False)
sys.path.insert(0,str(args.source))
from uta.credit_auth_h0 import CreditNonceStoreV2,CreditHmacIngressV2
from uta.request_signing import SigningError
REF='61258109e10f4ea4609e03010d5f25716b2c4256'
FLAGS=('financial_authorized','source_delivery_authorized','execution_authorized')
TABLES=('auth_config','auth_keys','auth_nonces','auth_audit','auth_credit_grants',
        'auth_credit_grant_revocations','auth_credit_acceptances')
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True)

def snapshot(path):
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,isolation_level=None)) as c:
        c.execute('PRAGMA query_only=ON');c.execute('BEGIN')
        allowed={sqlite3.SQLITE_SELECT,sqlite3.SQLITE_READ,sqlite3.SQLITE_PRAGMA,
                 sqlite3.SQLITE_FUNCTION,sqlite3.SQLITE_TRANSACTION}
        c.set_authorizer(lambda action,*_:sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY)
        data={name:[dict(zip([d[0] for d in cur.description],row)) for row in cur.fetchall()]
              for name in TABLES for cur in [c.execute('SELECT * FROM main.'+name+' ORDER BY 1')]}
        catalogue=c.execute('SELECT type,name,tbl_name,sql FROM main.sqlite_master ORDER BY type,name').fetchall()
        fk=c.execute('PRAGMA main.foreign_key_check').fetchall();c.rollback()
    return {'data':data,'catalogue':catalogue,'fk':fk}

class Fixture:
    def __init__(self,name,prepare_grants=True):
        self.root=args.private/name;self.root.mkdir(mode=0o700)
        self.path=self.root/'auth.sqlite3';self.profile_path=self.root/'private-profile.json'
        self.tenant='independent-tenant';self.account='independent-account';self.domain='independent-domain'
        self.secret={'funding':secrets.token_bytes(32),'reader':secrets.token_bytes(32)}
        self.roles={'funding':'funding','reader':'reader'};self.requests=0;self.revision=0
        store=CreditNonceStoreV2.initialize(self.path,tenant_id=self.tenant,
            producer_binding='8'*64,domain_id=self.domain,account_id=self.account)
        self.audience=store.audience;self.expires=time.time_ns()//1000000+3600000
        self.write_profile(1)
        self.scope=dict(tenant_id=self.tenant,producer_binding='8'*64,domain_id=self.domain,
                        domain_epoch=1,account_id=self.account,enabled=True)
        self.issuer=CreditHmacIngressV2(self.path,self.profile_path,**self.scope)
        self.store=self.issuer.store
        if prepare_grants:
            for name,operation in [('borrow','credit.borrow'),('read','credit.read'),('repay','credit.repay')]:
                self.grant('g-'+name,'funding',operation)
    def write_profile(self,revision):
        profile={'format':1,'tenant_id':self.tenant,'audience':self.audience,'revision':revision,
            'keys':[{'key_id':key,'secret_b64':base64.urlsafe_b64encode(secret).decode().rstrip('='),
                'role':self.roles[key],'account_id':self.account,'not_before_ms':0,
                'expires_at_ms':self.expires,'revoked':False} for key,secret in self.secret.items()]}
        fd=os.open(self.profile_path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,'w') as stream:json.dump(profile,stream)
    def advance_profile(self):
        self.secret['unrelated']=secrets.token_bytes(32);self.roles['unrelated']='funding'
        self.write_profile(2);self.issuer.replace_profile(self.profile_path)
    def grant(self,identity,key,operation):
        observed=self.store.put_grant(identity,key_id=key,account_id=self.account,asset='BTC',
            operation=operation,expected_grant_revision=self.revision)
        self.revision+=1;assert observed['grant_epoch']==self.revision
    def revoke(self,identity):
        observed=self.store.revoke_grant(identity,expected_grant_revision=self.revision)
        self.revision+=1;assert observed['revocation_revision']==self.revision
    def signed(self,cid,lookup=False,key='funding',kind='borrow'):
        self.requests+=1;method='GET' if lookup else 'POST'
        target='/v2/accounts/'+self.account+('/credit/commands/'+cid if lookup else '/'+kind)
        body=b'' if lookup else canonical({'command_id':cid,'asset':'BTC','amount':'0.4'}).encode()
        stamp=time.time_ns()//1000000;nonce=secrets.token_urlsafe(24)
        # Independent literal public v1 wire contract, not production helpers.
        message=json.dumps(['UTA-HMAC-SHA256','1',self.tenant,self.audience,key,str(stamp),nonce,
            method,target,hashlib.sha256(body).hexdigest()],separators=(',',':'),ensure_ascii=True).encode('ascii')
        headers={'Authorization':'UTA-HMAC-SHA256','X-UTA-Version':'1','X-UTA-Tenant':self.tenant,
            'X-UTA-Audience':self.audience,'X-UTA-Key-Id':key,'X-UTA-Timestamp-Ms':str(stamp),
            'X-UTA-Nonce':nonce,'X-UTA-Signature':hmac.new(self.secret[key],message,hashlib.sha256).hexdigest()}
        private={'headers':headers,'method':method,'request_target':target,'body_base64':base64.b64encode(body).decode()}
        fd=os.open(self.root/('private-request-'+str(self.requests)+'.json'),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as stream:json.dump(private,stream)
        return headers,dict(method=method,request_target=target,body=body)
    def capture(self,cid='baseline',kind='borrow',key='funding'):
        headers,request=self.signed(cid,kind=kind,key=key)
        return self.issuer.capture(headers,**request)
    def lookup(self,cid='baseline'):
        headers,request=self.signed(cid,lookup=True)
        return self.issuer.lookup(headers,**request)
    def consume_handle(self,handle):
        record=dict(self.issuer.inspect(handle));assert all(record[name] is False for name in FLAGS)
        self.issuer.release(handle);return record
    def positive(self):
        result=self.consume_handle(self.capture());assert result['receipt_kind']=='auth_first_observation'
        return result
    def corrupt(self,table,column,new_value,key_column,key_value):
        before=snapshot(self.path)
        with closing(sqlite3.connect(self.path,isolation_level=None)) as c:
            trigger=table+'_no_update'
            ddl=c.execute('SELECT sql FROM main.sqlite_master WHERE name=?',(trigger,)).fetchone()[0]
            with closing(sqlite3.connect(self.root/'before-corruption.sqlite3')) as target:c.backup(target)
            c.execute('BEGIN IMMEDIATE');c.execute('DROP TRIGGER main.'+trigger)
            c.execute('UPDATE main.'+table+' SET '+column+'=? WHERE '+key_column+'=?',(new_value,key_value))
            c.execute(ddl);c.commit()
        after=snapshot(self.path)
        assert before['catalogue']==after['catalogue'] and before['fk']==after['fk']==[]
        differences=[]
        for name in TABLES:
            assert len(before['data'][name])==len(after['data'][name])
            for b,a in zip(before['data'][name],after['data'][name]):
                differences.extend((name,col) for col in b if b[col]!=a[col])
        assert differences==[(table,column)]
        (self.root/'private-pre-probe-snapshot.json').write_text(json.dumps(after,indent=2)+'\n')
        return after
    def refusal(self,after_fault):
        methods=[('reopen',lambda:CreditNonceStoreV2(self.path)),('lookup',self.lookup),
            ('capture',lambda:self.capture('after-fault',kind='repay')),
            ('control',lambda:self.store.put_grant('g-read',key_id='funding',account_id=self.account,
                asset='BTC',operation='credit.read',expected_grant_revision=self.revision))]
        results=[]
        for name,call in methods:
            try:
                value=call();row={'operation':name,'refused':False}
                if name in ('lookup','capture'):
                    record=self.consume_handle(value);row.update(receipt_kind=record['receipt_kind'],authorization_flags_all_false=True)
            except SigningError as error:
                row={'operation':name,'refused':error.status==503,'typed_code':error.code,'status':error.status}
            results.append(row)
        final=snapshot(self.path)
        return {'operations':results,'all_refused_503':all(row['refused'] for row in results),
            'no_auth_rows_changed_after_refusal_attempts':final==after_fault,
            'acceptances_before_probe':len(after_fault['data']['auth_credit_acceptances']),
            'acceptances_after_probe':len(final['data']['auth_credit_acceptances']),
            'exact_schema_restored_and_fk_clean':final['catalogue']==after_fault['catalogue'] and final['fk']==[]}

results=[]
f=Fixture('healthy-history');original=f.positive();first=json.loads(original['first_acceptance_payload_or_null'])
assert first['profile_revision']==1
f.advance_profile();f.grant('g-unrelated-borrow','unrelated','credit.borrow')
new=f.consume_handle(f.capture('after-profile-advance',key='unrelated'))
assert json.loads(new['first_acceptance_payload_or_null'])['profile_revision']==2
query=f.consume_handle(f.lookup());assert query['first_acceptance_payload_or_null']==original['first_acceptance_payload_or_null']
CreditNonceStoreV2(f.path)
results.append({'case':'healthy-history-with-unrelated-profile-advance','passed':True,
    'original_first_identity_unchanged':True,'historical_profile1_and_new_profile2_both_retained':True,
    'all_authorization_flags_false':True})

for case,mutation in [('grant-empty','empty'),('grant-boolean-epoch','boolean'),('grant-noncanonical-space','space')]:
    f=Fixture(case);f.positive();state=snapshot(f.path)
    payload=next(row['payload'] for row in state['data']['auth_credit_grants'] if row['grant_id']=='g-borrow')
    if mutation=='empty':damaged='{}'
    elif mutation=='space':damaged=' '+payload
    else:
        value=json.loads(payload);assert value['grant_epoch']==1;value['grant_epoch']=True;damaged=canonical(value)
    changed=f.corrupt('auth_credit_grants','payload',damaged,'grant_id','g-borrow')
    outcome=f.refusal(changed);outcome.update(case=case,passed=outcome['all_refused_503'] and outcome['no_auth_rows_changed_after_refusal_attempts'])
    results.append(outcome)

f=Fixture('revocation-empty');f.positive();f.revoke('g-borrow')
try:f.capture('revoked-borrow-positive')
except SigningError as error:assert error.code=='credit_auth_forbidden'
else:raise AssertionError('real revocation did not deny borrow')
changed=f.corrupt('auth_credit_grant_revocations','payload','{}','grant_id','g-borrow')
outcome=f.refusal(changed);outcome.update(case='revocation-empty',real_revocation_positive_control=True,
    passed=outcome['all_refused_503'] and outcome['no_auth_rows_changed_after_refusal_attempts']);results.append(outcome)

f=Fixture('grant-audit-link');f.positive();state=snapshot(f.path)
grant=next(row for row in state['data']['auth_credit_grants'] if row['grant_id']=='g-borrow')
changed=f.corrupt('auth_audit','grant_id','g-read','sequence',grant['audit_sequence'])
outcome=f.refusal(changed);outcome.update(case='grant-audit-link',passed=outcome['all_refused_503'] and outcome['no_auth_rows_changed_after_refusal_attempts']);results.append(outcome)

# New integrity negative: latest preceding profile2 must govern a later grant.
f=Fixture('grant-audit-stale-prior-profile',prepare_grants=False);f.advance_profile()
for name,op in [('borrow','credit.borrow'),('read','credit.read'),('repay','credit.repay')]:f.grant('g-'+name,'funding',op)
original=f.positive();state=snapshot(f.path)
grant=next(row for row in state['data']['auth_credit_grants'] if row['grant_id']=='g-borrow')
audit=next(row for row in state['data']['auth_audit'] if row['sequence']==grant['audit_sequence'])
assert audit['revision']==2
profiles=[row for row in state['data']['auth_audit'] if row['event']=='profile_configured']
assert [(row['revision']) for row in profiles]==[1,2] and profiles[-1]['sequence']<audit['sequence']
changed=f.corrupt('auth_audit','revision',1,'sequence',grant['audit_sequence'])
outcome=f.refusal(changed);outcome.update(case='grant-audit-stale-prior-profile',
    actual_profile2_committed_before_original_grant=True,only_one_audit_revision_changed_2_to_1=True,
    passed=outcome['all_refused_503'] and outcome['no_auth_rows_changed_after_refusal_attempts']);results.append(outcome)

report={'runtime_commit':REF,'case_count':len(results),'passed_cases':sum(row['passed'] for row in results),
    'results':results,'all_passed':all(row['passed'] for row in results),'finished_at':datetime.now(timezone.utc).isoformat(),
    'literal_hmac_reference_used':True,'fresh_owned_authdb_only':True,'financial_or_source_permission':False}
args.result.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
assert report['all_passed'],'independent retained-auth data refusal checks failed'
