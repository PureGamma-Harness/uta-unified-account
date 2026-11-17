"""Prepared independent AuthDB ordering cases. Never imported as a product oracle.

Requires root's separate execution GO. No work occurs until main() invocation.
"""
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
import subprocess
import sys
import time
from threading import Barrier, Event, Thread

SOURCE_REF='912f2a4e5ed74f7a3fbf892ff0172e4eacc9c45a'
RUNTIME_REF='5750e12d60dbf7f8414b4e837e076a60c93a23bc'


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

    def __init__(self, name, prepare_grants=True):
        self.root = args.private / name
        self.root.mkdir(mode=448)
        self.path = self.root / 'auth.sqlite3'
        self.profile_path = self.root / 'private-profile.json'
        self.tenant = 'independent-tenant'
        self.account = 'independent-account'
        self.domain = 'independent-domain'
        self.secret = {'funding': secrets.token_bytes(32), 'reader': secrets.token_bytes(32)}
        self.roles = {'funding': 'funding', 'reader': 'reader'}
        self.requests = 0
        self.revision = 0
        store = CreditNonceStoreV2.initialize(self.path, tenant_id=self.tenant, producer_binding='8' * 64, domain_id=self.domain, account_id=self.account)
        self.audience = store.audience
        self.expires = time.time_ns() // 1000000 + 3600000
        self.write_profile(1)
        self.scope = dict(tenant_id=self.tenant, producer_binding='8' * 64, domain_id=self.domain, domain_epoch=1, account_id=self.account, enabled=True)
        self.issuer = CreditHmacIngressV2(self.path, self.profile_path, **self.scope)
        self.store = self.issuer.store
        if prepare_grants:
            for name, operation in [('borrow', 'credit.borrow'), ('read', 'credit.read'), ('repay', 'credit.repay')]:
                self.grant('g-' + name, 'funding', operation)

    def write_profile(self, revision):
        profile = {'format': 1, 'tenant_id': self.tenant, 'audience': self.audience, 'revision': revision, 'keys': [{'key_id': key, 'secret_b64': base64.urlsafe_b64encode(secret).decode().rstrip('='), 'role': self.roles[key], 'account_id': self.account, 'not_before_ms': 0, 'expires_at_ms': self.expires, 'revoked': False} for key, secret in self.secret.items()]}
        fd = os.open(self.profile_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 384)
        with os.fdopen(fd, 'w') as stream:
            json.dump(profile, stream)

    def grant(self, identity, key, operation):
        observed = self.store.put_grant(identity, key_id=key, account_id=self.account, asset='BTC', operation=operation, expected_grant_revision=self.revision)
        self.revision += 1
        assert observed['grant_epoch'] == self.revision

    def revoke(self, identity):
        observed = self.store.revoke_grant(identity, expected_grant_revision=self.revision)
        self.revision += 1
        assert observed['revocation_revision'] == self.revision

    def signed(self, cid, lookup=False, key='funding', kind='borrow'):
        self.requests += 1
        method = 'GET' if lookup else 'POST'
        target = '/v2/accounts/' + self.account + ('/credit/commands/' + cid if lookup else '/' + kind)
        body = b'' if lookup else canonical({'command_id': cid, 'asset': 'BTC', 'amount': '0.4'}).encode()
        stamp = time.time_ns() // 1000000
        nonce = secrets.token_urlsafe(24)
        message = json.dumps(['UTA-HMAC-SHA256', '1', self.tenant, self.audience, key, str(stamp), nonce, method, target, hashlib.sha256(body).hexdigest()], separators=(',', ':'), ensure_ascii=True).encode('ascii')
        headers = {'Authorization': 'UTA-HMAC-SHA256', 'X-UTA-Version': '1', 'X-UTA-Tenant': self.tenant, 'X-UTA-Audience': self.audience, 'X-UTA-Key-Id': key, 'X-UTA-Timestamp-Ms': str(stamp), 'X-UTA-Nonce': nonce, 'X-UTA-Signature': hmac.new(self.secret[key], message, hashlib.sha256).hexdigest()}
        private = {'headers': headers, 'method': method, 'request_target': target, 'body_base64': base64.b64encode(body).decode()}
        fd = os.open(self.root / ('private-request-' + str(self.requests) + '.json'), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 384)
        with os.fdopen(fd, 'w') as stream:
            json.dump(private, stream)
        return (headers, dict(method=method, request_target=target, body=body))

    def capture(self, cid='baseline', kind='borrow', key='funding'):
        headers, request = self.signed(cid, kind=kind, key=key)
        return self.issuer.capture(headers, **request)

    def lookup(self, cid='baseline', key='funding'):
        headers, request = self.signed(cid, lookup=True, key=key)
        return self.issuer.lookup(headers, **request)

    def consume_handle(self, handle):
        record = dict(self.issuer.inspect(handle))
        assert all((record[name] is False for name in FLAGS))
        self.issuer.release(handle)
        return record

    def positive(self):
        result = self.consume_handle(self.capture())
        assert result['receipt_kind'] == 'auth_first_observation'
        return result


class TechnicalUnknown(Exception):
    pass


def prepare_profile2(fixture, revoke_funding=False):
    profile=json.loads(fixture.profile_path.read_text())
    profile['revision']=2
    if revoke_funding:
        next(key for key in profile['keys'] if key['key_id']=='funding')['revoked']=True
    else:
        secret=secrets.token_bytes(32)
        profile['keys'].append({'key_id':'unrelated','secret_b64':base64.urlsafe_b64encode(secret).decode().rstrip('='),
            'role':'funding','account_id':fixture.account,'not_before_ms':0,'expires_at_ms':fixture.expires,'revoked':False})
    path=fixture.root/'private-profile-next.json'
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as stream:json.dump(profile,stream)
    return path


def race(case_name, first, second, directory):
    barrier=Barrier(3);done=[Event(),Event()];boxes={}
    def worker(index,call):
        try:
            barrier.wait(timeout=2)
            boxes[index]={'returned':True,'value':call()}
        except SigningError as error:
            boxes[index]={'returned':False,'code':error.code,'status':error.status}
        except AssertionError:
            boxes[index]={'returned':False,'known_assertion_failure':True}
        except BaseException as error:
            boxes[index]={'returned':False,'technical_exception':type(error).__name__}
        finally:
            done[index].set()
    threads=[Thread(target=worker,args=(n,call),name='independent-'+case_name+'-'+str(n),daemon=True)
             for n,call in enumerate((first,second))]
    for thread in threads:thread.start()
    try:barrier.wait(timeout=2)
    except BaseException:pass
    deadline=time.monotonic()+4
    for event in done:event.wait(max(0,deadline-time.monotonic()))
    for thread in threads:thread.join(timeout=.1 if all(e.is_set() for e in done) else 0)
    if not all(event.is_set() for event in done) or any(thread.is_alive() for thread in threads):
        status={'case':case_name,'status':'UNKNOWN_UNJOINED_OWNED_DAEMON_THREADS',
            'self_pid':os.getpid(),'no_external_pid_signalled':True,'current_test_process_exit':91}
        (directory/'private-incomplete.json').write_text(json.dumps(status,indent=2)+'\n')
        args.result.write_text(json.dumps(status,indent=2)+'\n');print(json.dumps(status),flush=True)
        # Only this newly started probe process exits; auth outcomes stay UNKNOWN.
        os._exit(91)
    (directory/'private-thread-results.json').write_text(json.dumps(boxes,indent=2)+'\n')
    if any(box.get('known_assertion_failure') for box in boxes.values()):
        raise AssertionError('a worker failed a known auth observation invariant')
    if any('technical_exception' in box or box.get('status')==503 for box in boxes.values()):
        raise TechnicalUnknown('actual bounded thread/auth-store outcome unknown')
    return boxes[0],boxes[1]


def control_audit(data, event, **equal):
    matches=[row for row in data['auth_audit'] if row['event']==event
        and all(row[key]==value for key,value in equal.items())]
    assert len(matches)==1
    return matches[0]


def latest_profile(data, sequence):
    preceding=[row for row in data['auth_audit'] if row['event']=='profile_configured'
        and row['outcome']=='CONTROL' and row['request_kind']=='CONTROL' and row['sequence']<sequence]
    assert preceding
    return max(preceding,key=lambda row:row['sequence'])['revision']


def new_fixture(name):
    fixture=Fixture(name)
    fixture.grant('g-reader-read','reader','credit.read')
    return fixture


def profile_race(revoke):
    name='profile-revoke-vs-capture' if revoke else 'unrelated-profile-vs-capture'
    f=new_fixture(name);next_profile=prepare_profile2(f,revoke_funding=revoke)
    headers,request=f.signed('profile-race')
    result,changed=race(name,lambda:f.consume_handle(f.issuer.capture(headers,**request)),
        lambda:f.issuer.replace_profile(next_profile),f.root)
    assert changed['returned'] is True
    data=snapshot(f.path)['data'];profile=control_audit(data,'profile_configured',revision=2)
    accepted=[row for row in data['auth_credit_acceptances'] if row['command_id']=='profile-race']
    if result['returned']:
        assert len(accepted)==1 and result['value']['receipt_kind']=='auth_first_observation'
        row=accepted[0];assert latest_profile(data,row['auth_audit_sequence'])==row['profile_revision']
        if revoke:assert row['profile_revision']==1 and row['auth_audit_sequence']<profile['sequence']
    else:
        assert revoke and result['status']==401 and result['code']=='signing_key_inactive' and accepted==[]
        denial=control_audit(data,'signing_key_inactive')
        assert denial['sequence']>profile['sequence'] and denial['revision']==2
    query=f.consume_handle(f.lookup('profile-race',key='reader'))
    assert query['found'] is bool(accepted)
    return {'case':name,'passed':True,'request_outcome':
        ('accepted-before-revocation' if revoke else 'accepted-with-recorded-current-profile') if result['returned'] else 'key-inactive-after-profile',
        'profile2_committed':True,'audit_order_matches_actual_profile':True,
        'current_independent_reader_query_correct':True,'financial_authorization':False}


def grant_retry_race():
    name='borrow-grant-revoke-vs-same-cid-retry';f=new_fixture(name);original=f.positive()
    headers,request=f.signed('baseline')
    result,revoked=race(name,lambda:f.consume_handle(f.issuer.capture(headers,**request)),lambda:f.revoke('g-borrow'),f.root)
    assert revoked['returned'] is True
    data=snapshot(f.path)['data'];revoke=control_audit(data,'grant_revoked',grant_id='g-borrow')
    assert len(data['auth_credit_acceptances'])==1
    if result['returned']:
        observed=result['value'];assert observed['receipt_kind']=='auth_query_only'
        assert observed['first_acceptance_payload_or_null']==original['first_acceptance_payload_or_null']
        assert observed['query_audit_sequence']<revoke['sequence']
    else:
        assert result['status']==403 and result['code']=='credit_auth_forbidden'
        denied=[row for row in data['auth_audit'] if row['outcome']=='PERMISSION_REJECTED']
        assert len(denied)==1 and denied[0]['sequence']>revoke['sequence']
    current=f.consume_handle(f.lookup(key='reader'))
    assert current['first_acceptance_payload_or_null']==original['first_acceptance_payload_or_null']
    return {'case':name,'passed':True,'retry_outcome':'query-before-revoke' if result['returned'] else 'refused-after-revoke',
        'first_acceptance_count':1,'first_identity_unchanged':True,'current_reader_query_correct':True,'financial_authorization':False}


def current_read_race():
    name='read-grant-revoke-vs-current-lookup';f=new_fixture(name);original=f.positive()
    headers,request=f.signed('baseline',lookup=True,key='reader')
    result,revoked=race(name,lambda:f.consume_handle(f.issuer.lookup(headers,**request)),lambda:f.revoke('g-reader-read'),f.root)
    assert revoked['returned'] is True
    data=snapshot(f.path)['data'];revoke=control_audit(data,'grant_revoked',grant_id='g-reader-read')
    if result['returned']:
        observed=result['value'];assert observed['receipt_kind']=='auth_query_only'
        assert observed['query_audit_sequence']<revoke['sequence']
    else:
        assert result['status']==403 and result['code']=='credit_auth_forbidden'
        denied=[row for row in data['auth_audit'] if row['outcome']=='PERMISSION_REJECTED']
        assert len(denied)==1 and denied[0]['sequence']>revoke['sequence']
    try:f.lookup(key='reader')
    except SigningError as error:assert error.status==403 and error.code=='credit_auth_forbidden'
    else:raise AssertionError('revoked current query grant remained permitted')
    independent=f.consume_handle(f.lookup(key='funding'))
    assert independent['first_acceptance_payload_or_null']==original['first_acceptance_payload_or_null']
    return {'case':name,'passed':True,'read_outcome':'query-before-revoke' if result['returned'] else 'refused-after-revoke',
        'subsequent_revoked_reader_denied':True,'other_current_read_grant_succeeds':True,'financial_authorization':False}


def main():
    global args,CreditNonceStoreV2,CreditHmacIngressV2,SigningError
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--private',type=Path,required=True);parser.add_argument('--result',type=Path,required=True)
    args=parser.parse_args()
    if not all(path.is_absolute() for path in (args.source,args.private,args.result)):
        parser.error('source/private/result must be absolute paths')
    if args.private.exists():parser.error('fresh private path required')
    actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=args.source,text=True).strip()
    if actual!=SOURCE_REF:parser.error('exact reviewed source head required')
    paths=subprocess.check_output(['git','ls-tree','-r','--name-only',RUNTIME_REF,'--','uta'],cwd=args.source,text=True).splitlines()
    hashes={}
    for path in paths:
        data=(args.source/path).read_bytes()
        if data!=subprocess.check_output(['git','show',RUNTIME_REF+':'+path],cwd=args.source):parser.error('runtime source bytes differ')
        hashes[path]=hashlib.sha256(data).hexdigest()
    args.private.mkdir(mode=0o700)
    sys.path.insert(0,str(args.source))
    from uta.credit_auth_h0 import CreditNonceStoreV2,CreditHmacIngressV2
    from uta.request_signing import SigningError
    start=datetime.now(timezone.utc).isoformat();mono=time.monotonic_ns();cases=[];status='PASS'
    for name,call in [('profile-revoke',lambda:profile_race(True)),('profile-unrelated',lambda:profile_race(False)),
                      ('grant-retry',grant_retry_race),('current-read',current_read_race)]:
        try:cases.append(call())
        except TechnicalUnknown:
            cases.append({'case':name,'passed':False,'status':'TECHNICAL_UNKNOWN'});status='UNKNOWN';break
        except BaseException as error:
            cases.append({'case':name,'passed':False,'status':'FAILED','exception_type':type(error).__name__});status='FAIL';break
        args.result.write_text(json.dumps({'status':'RUNNING','completed_cases':cases},indent=2)+'\n')
    unchanged=all(hashlib.sha256((args.source/path).read_bytes()).hexdigest()==digest for path,digest in hashes.items())
    report={'source_commit':SOURCE_REF,'runtime_commit':RUNTIME_REF,'status':status,'cases':cases,
        'case_count':len(cases),'source_unchanged':unchanged,'runtime_hashes_before':hashes,
        'started_at':start,'finished_at':datetime.now(timezone.utc).isoformat(),'monotonic_ns_before_report_write':time.monotonic_ns()-mono,
        'python':sys.version,'sqlite':sqlite3.sqlite_version,'affinity':sorted(os.sched_getaffinity(0)),
        'fresh_private_authdb_only':True,'financial_permission':False,'production_approved':False}
    args.result.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='runtime_hashes_before'}))
    return 0 if status=='PASS' and len(cases)==4 and unchanged else 2 if status=='UNKNOWN' else 1


if __name__=='__main__':
    raise SystemExit(main())
