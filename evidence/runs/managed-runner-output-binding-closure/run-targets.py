from pathlib import Path
from hashlib import sha256
from datetime import datetime,timezone
import json,os,subprocess,time
root=Path('/workspace/uta-managed-variant-runner-final-fix');out=root/'evidence/runs/managed-runner-output-binding-closure';records=[]
names=['tools/run_managed_variants.py','tests/test_managed_variant_runner_package_closure.py'];before={n:sha256((root/n).read_bytes()).hexdigest() for n in names}
for label,exe in [('py312','/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python'),('py310','/tmp/uta-python310/cpython-3.10.22-linux-x86_64-gnu/bin/python3.10'),('py313','/usr/bin/python3.13')]:
 command=[exe,'-W','error::ResourceWarning','-m','unittest','tests.test_managed_variant_runner_package_closure','-v'];start=datetime.now(timezone.utc).isoformat();at=time.monotonic()
 with (out/(label+'.log')).open('w') as log:p=subprocess.run(command,cwd=root,env=dict(os.environ,PYTHONWARNINGS='error::ResourceWarning'),stdout=log,stderr=subprocess.STDOUT)
 records.append({'argv':command,'started_utc':start,'finished_utc':datetime.now(timezone.utc).isoformat(),'returncode':p.returncode,'seconds':time.monotonic()-at,'cpu_ids':sorted(os.sched_getaffinity(0)),'source_before':before,'source_after':{n:sha256((root/n).read_bytes()).hexdigest() for n in names},'pure_data_only':True});(out/'execution.json').write_text(json.dumps(records,indent=2)+'\n');print(label,p.returncode,records[-1]['seconds'])
 if p.returncode:raise SystemExit(p.returncode)
