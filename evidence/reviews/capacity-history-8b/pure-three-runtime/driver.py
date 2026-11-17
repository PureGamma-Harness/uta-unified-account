from datetime import datetime,timezone
from hashlib import sha256
import json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path('/workspace/uta-capacity-history-8b-fix')
OUTPUT=Path(__file__).parent
os.sched_setaffinity(0,{3})
files=['tests/test_capacity_review_data_reference.py','evidence/runs/capacity-independent-review/recompute.py','evidence/runs/capacity-independent-review/historical-source/provenance.json','evidence/runs/capacity-independent-review/historical-source/run_managed_benchmark.5caf874.py.txt','evidence/runs/capacity-independent-review/historical-source/LICENSE.Apache-2.0.txt','benchmarks/run_managed_benchmark.py']
def hashes():return {name:sha256((ROOT/name).read_bytes()).hexdigest() for name in files}
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
runtimes=[('py310','/tmp/uta-python310/cpython-3.10.22-linux-x86_64-gnu/bin/python3.10'),('py312',sys.executable),('py313','/usr/bin/python3.13')]
records=[];allstarted=time.monotonic()
for label,interpreter in runtimes:
 before=hashes();started=datetime.now(timezone.utc).isoformat();begin=time.monotonic()
 command=[interpreter,'-B','-W','error::ResourceWarning','-m','unittest','discover','-s','tests','-p','test_capacity_review_data_reference.py','-v']
 env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONWARNINGS='error::ResourceWarning');env.pop('PYTHONPATH',None)
 result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,timeout=max(.1,9-(time.monotonic()-allstarted)))
 (OUTPUT/(label+'.stdout.txt')).write_bytes(result.stdout);(OUTPUT/(label+'.stderr.txt')).write_bytes(result.stderr)
 assert before==hashes()
 records.append({'source_commit':commit,'runtime':label,'command':command,'started_utc':started,'finished_utc':datetime.now(timezone.utc).isoformat(),'wall_seconds':time.monotonic()-begin,'returncode':result.returncode,'CPU_ids':sorted(os.sched_getaffinity(0)),'source_before':before,'source_after':hashes(),'stdout_sha256':sha256(result.stdout).hexdigest(),'stderr_sha256':sha256(result.stderr).hexdigest()})
summary={'scope':'one small pure reference group in three actual runtimes; no SQL/services/benchmark','records':records,'total_wall_seconds':time.monotonic()-allstarted,'production_approved':False,'capacity_10000_per_s_passed':False}
(OUTPUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps([{k:r[k] for k in ['runtime','returncode','wall_seconds']} for r in records],indent=2))
