from pathlib import Path
from hashlib import sha256
import json,os,subprocess,time,datetime
ROOT=Path('/workspace/uta-numeric-contract')
OUT=Path('/tmp/uta-numeric-contract-3c4f553')
OUT.mkdir(mode=0o700)
os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
assert commit.startswith('3c4f553')
assert not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)
def sources():
 paths=sorted(Path(ROOT/'uta').glob('*.py'))+[ROOT/'uta/dashboard.html',ROOT/'tests/test_numeric_contract_reference.py',ROOT/'docs/numeric-contract-independent-review.md',ROOT/'docs/accounting-spec.md',ROOT/'evidence/rules.csv']
 return {str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in paths}
before=sources(); runs=[]
for name,py in [('python312','/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python'),('python310','/tmp/uta-python310/cpython-3.10.22-linux-x86_64-gnu/bin/python3.10'),('python313-sqlite346','/usr/bin/python3.13')]:
 metadata=json.loads(subprocess.check_output([py,'-c','import json,sys,sqlite3; print(json.dumps({"python":sys.version,"sqlite":sqlite3.sqlite_version}))'],text=True))
 argv=[py,'-W','error::ResourceWarning','-m','unittest','tests.test_numeric_contract_reference','-v']; log=OUT/(name+'.txt');start=time.monotonic(); utc=datetime.datetime.now(datetime.timezone.utc).isoformat()
 with log.open('x') as f:result=subprocess.run(argv,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
 raw=log.read_text();passed=result.returncode==0 and 'Ran 10 tests' in raw and '\nOK\n' in raw and 'ResourceWarning' not in raw and 'Exception ignored' not in raw
 runs.append({'name':name,'command':argv,'cwd':str(ROOT),'started_utc':utc,'duration_seconds':time.monotonic()-start,'returncode':result.returncode,'passed':passed,'tests':10,'test_log_sha256':sha256(log.read_bytes()).hexdigest(),**metadata})
report={'code_commit':commit,'affinity':sorted(os.sched_getaffinity(0)),'sources_before':before,'sources_after':sources(),'git_clean_after':not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True),'runs':runs,'production_approved':False,'not_release_qualification':True}
report['source_unchanged']=report['sources_before']==report['sources_after']
report['passed']=all(r['passed'] for r in runs) and report['source_unchanged'] and report['git_clean_after']
(OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ('code_commit','affinity','passed','source_unchanged','git_clean_after','runs')},indent=2))
raise SystemExit(0 if report['passed'] else 1)
