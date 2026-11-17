from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess,time

root=Path('/workspace/uta-batch-recovery-review')
output=Path('/tmp/uta-batch-recovery-6730')
def source():
 return {str(p.relative_to(root)):sha256(p.read_bytes()).hexdigest() for p in sorted([*root.glob('uta/*.py'),root/'tests/test_batch_recovery_reference.py'])}
def git(*args):
 return subprocess.check_output(['git',*args],cwd=root,text=True).strip()
start=source();before=git('status','--porcelain');commit=git('rev-parse','HEAD');runs=[]
for label,python in [('python312','/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python'),('python310','/tmp/uta-python310/cpython-3.10.22-linux-x86_64-gnu/bin/python3.10'),('python313-sqlite346','/usr/bin/python3.13')]:
 command=[python,'-B','-W','error::ResourceWarning','-c','import os,unittest; os.sched_setaffinity(0,{min(os.sched_getaffinity(0))}); unittest.main(module=None,argv=["unittest","tests.test_batch_recovery_reference","-v"])']
 runtime=json.loads(subprocess.check_output([python,'-c','import json,sys,sqlite3;print(json.dumps({"python":sys.version,"sqlite":sqlite3.sqlite_version}))'],text=True))
 beginning=datetime.now(timezone.utc).isoformat();mono=time.monotonic()
 with (output/(label+'.txt')).open('x') as log:
  done=subprocess.run(command,cwd=root,stdout=log,stderr=subprocess.STDOUT)
 raw=(output/(label+'.txt')).read_text()
 runs.append({'label':label,'command':command,**runtime,'started_at':beginning,'finished_at':datetime.now(timezone.utc).isoformat(),'duration_seconds':time.monotonic()-mono,'exit_code':done.returncode,'seven_tests_footer':'Ran 7 tests in ' in raw,'ok_footer':raw.rstrip().endswith('OK'),'resource_warning':'ResourceWarning' in raw,'log_sha256':sha256(raw.encode()).hexdigest()})
end=source();after=git('status','--porcelain')
report={'source_commit':commit,'source_before':start,'source_after':end,'source_unchanged':start==end,'git_clean_before':not before,'git_clean_after':not after,'scope':'seven independent batch recovery cases; no full suite, service soak or throughput','runs':runs,'production_approved':False}
(output/'matrix.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if not k.startswith('source_')},indent=2))
assert start==end and not before and not after
assert all(r['exit_code']==0 and r['seven_tests_footer'] and r['ok_footer'] and not r['resource_warning'] for r in runs)
