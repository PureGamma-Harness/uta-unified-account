"""Bounded private H0 batches; original raw stays private, public is allowlisted."""
import argparse,datetime,hashlib,json,os,pathlib,signal,subprocess,sys,time
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);p.add_argument('--mode',choices=['legacy','h0'],required=True);p.add_argument('--test',action='append',default=[]);p.add_argument('--python',required=True);a=p.parse_args()
source=pathlib.Path(a.source).resolve();out=pathlib.Path(a.output).resolve();out.mkdir(mode=0o700,parents=True,exist_ok=False);os.umask(0o077)
def git(*v):return subprocess.check_output(['git',*v],cwd=source,text=True).strip()
def hashes():return {str(f.relative_to(source)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted((source/'uta').glob('*')) if f.is_file() and f.suffix in ['.py','.html']} | {str(f.relative_to(source)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted((source/'tests').glob('test_credit_auth_h0*.py'))}
assert not git('status','--porcelain','--untracked-files=no')
initial=hashes();sha=git('rev-parse','HEAD');cases=out/'private-cases';cases.mkdir(mode=0o700)
runner=out/'private-runner.py'
if a.mode=='legacy':
 code='''import sys,pathlib,os,secrets,time,json,base64
sys.path.insert(0,sys.argv[1])
from uta.request_signing import NonceStore,RequestAuthenticator,SigningKey,SigningProfile,load_profile,sign_headers,SigningError
from uta.gateway import Credential
root=pathlib.Path(sys.argv[2]);store=NonceStore.initialize(root/'legacy-auth.sqlite3',tenant_id='h0-baseline',producer_binding='9'*64)
now=time.time_ns()//1000000;key=SigningKey('baseline-key',secrets.token_bytes(32),'funding','alice',0,now+60000)
data={'format':1,'tenant_id':'h0-baseline','audience':store.audience,'revision':1,'keys':[{'key_id':key.key_id,'secret_b64':base64.urlsafe_b64encode(key.secret).decode().rstrip('='),'role':key.role,'account_id':key.account_id,'not_before_ms':key.not_before_ms,'expires_at_ms':key.expires_at_ms,'revoked':False}]}
path=root/'private-profile.json';fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as f:json.dump(data,f)
profile=load_profile(path);auth=RequestAuthenticator(store,profile)
headers=sign_headers(profile,key.key_id,timestamp_ms=time.time_ns()//1000000,nonce=secrets.token_urlsafe(24),method='GET',request_target='/auth-baseline',body=b'')
principal=auth.authenticate(headers,method='GET',request_target='/auth-baseline',body=b'');assert type(principal) is Credential
try:auth.authenticate(headers,method='GET',request_target='/auth-baseline',body=b'')
except SigningError as e:assert e.code=='request_replayed'
else:raise AssertionError('expected nonce replay')
with store.database.read_transaction() as c:assert c.execute('SELECT COUNT(*) FROM auth_nonces').fetchone()[0]==1
print(json.dumps({'legacy_actual_positive':True,'credential_return_type':True,'real_replay_refusal':True,'financial_database_opened':False,'synthetic_only':True}))
'''
 args=[str(source),str(cases)]
else:
 code='''import sys,pathlib,json,unittest,os,sqlite3,platform
sys.path.insert(0,sys.argv[1]);sys.path.insert(0,str(pathlib.Path(sys.argv[1])/'tests'))
SAFE_CODES={'credit_auth_outcome_unknown','credit_auth_disabled','credit_auth_forbidden','credit_auth_input_invalid','credit_auth_handle_invalid','credit_auth_thread_mismatch','credit_auth_process_mismatch','credit_auth_handle_capacity','credit_auth_reservation_capacity','signing_capacity_exhausted','request_replayed','invalid_signature','idempotency_conflict','grant_identity_conflict','grant_revision_conflict','auth_clock_regressed'}
SAFE_TYPES={'AssertionError','ValueError','TypeError','CreditAuthError','SigningError','StorageError','OperationalError','DatabaseError','IntegrityError','ResourceWarning','OSError','RuntimeError','AttributeError','ImportError'}
class R(unittest.TextTestResult):
 def __init__(self,*args,**kw):super().__init__(*args,**kw);self.records=[]
 def addSuccess(self,t):super().addSuccess(t);self.records.append({'test_id':t.id(),'status':'PASS'})
 def addFailure(self,t,e):super().addFailure(t,e);self.record(t,e,'FAIL')
 def addError(self,t,e):super().addError(t,e);self.record(t,e,'ERROR')
 def record(self,t,e,status):
  typ=e[0].__name__;code=getattr(e[1],'code',None);sql=getattr(e[1],'sqlite_errorcode',None)
  self.records.append({'test_id':t.id(),'status':status,'exception_type':typ if typ in SAFE_TYPES else 'OTHER','error_code':code if code in SAFE_CODES else None,'sqlite_errorcode':sql if type(sql) is int and 0<=sql<=65535 else None})
names=sys.argv[3:] or ['test_credit_auth_h0.CreditAuthH0Tests']
suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(n) for n in names)
result=unittest.TextTestRunner(verbosity=2,resultclass=R).run(suite)
report={'python':platform.python_version(),'sqlite':sqlite3.sqlite_version,'affinity':sorted(os.sched_getaffinity(0)),'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),'records':result.records,'passed':result.wasSuccessful(),'financial_database_opened':False,'scope':'H0 fresh private AuthDB only; not production'}
pathlib.Path(sys.argv[2]).write_text(json.dumps(report,indent=2)+'\\n')
sys.exit(0 if result.wasSuccessful() else 1)
'''
 args=[str(source),str(out/'public-tests.json'),*a.test]
runner.write_text(code)
env=os.environ.copy();env.update(PYTHONDONTWRITEBYTECODE='1',UTA_H0_PRIVATE_CASES=str(cases),UTA_H0_LEGACY_SOURCE='/workspace/uta-credit-v2-py310-candidate',TMPDIR=str(cases))
cmd=['taskset','-c','4',a.python,'-I','-B','-W','error::ResourceWarning',str(runner),*args]
started=datetime.datetime.now(datetime.timezone.utc).isoformat();begin=time.monotonic_ns();timed=False
with (out/'private-stdout.txt').open('x') as stdout,(out/'private-stderr.txt').open('x') as stderr:
 child=subprocess.Popen(cmd,cwd=source,env=env,stdout=stdout,stderr=stderr,start_new_session=True)
 try:code_return=child.wait(timeout=30)
 except subprocess.TimeoutExpired:
  timed=True;os.killpg(child.pid,signal.SIGKILL);code_return=child.wait()
ended=time.monotonic_ns();finished=datetime.datetime.now(datetime.timezone.utc).isoformat();after=hashes()
report={'source_commit':sha,'command':cmd,'cwd':str(source),'started_at':started,'finished_at':finished,'outer_monotonic_ns':ended-begin,'hard_timeout_seconds':30,'watchdog_triggered':timed,'exit_code':code_return,'source_unchanged':initial==after,'tracked_source_clean_after':not git('status','--porcelain','--untracked-files=no'),'source_sha256':initial,'launcher_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'private_runner_sha256':hashlib.sha256(runner.read_bytes()).hexdigest(),'raw_private_only':{n:{'bytes':(out/n).stat().st_size,'sha256':hashlib.sha256((out/n).read_bytes()).hexdigest()} for n in ['private-stdout.txt','private-stderr.txt']},'production_approved':False,'financial_execution_authorized':False}
(out/'execution.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['source_commit','started_at','finished_at','outer_monotonic_ns','hard_timeout_seconds','watchdog_triggered','exit_code','source_unchanged','production_approved']}))
if (out/'public-tests.json').exists():print((out/'public-tests.json').read_text())
sys.exit(code_return if code_return in range(256) else 1)
