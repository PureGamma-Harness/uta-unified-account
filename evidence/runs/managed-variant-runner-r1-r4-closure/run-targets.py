from pathlib import Path
from datetime import datetime,timezone
from hashlib import sha256
import json,os,subprocess,time
root=Path('/workspace/uta-managed-variant-runner-fix');out=Path('/tmp/uta-runner-r1-r4-closure');out.mkdir(exist_ok=False)
items=['tools/run_managed_variants.py','tests/test_managed_variant_runner.py','tests/test_managed_variant_runner_red_closure.py']
hashes={name:sha256((root/name).read_bytes()).hexdigest() for name in items};runs=[]
for label,exe,dummy in [('py312','/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python',True),('py310','/tmp/uta-python310/cpython-3.10.22-linux-x86_64-gnu/bin/python3.10',False),('py313','/usr/bin/python3.13',False)]:
 classes='RunnerPureTests,RunnerDummyTests' if dummy else 'RunnerPureTests'
 fixes='RunnerRedDataClosureTests,RunnerAffinityClosureTests' if dummy else 'RunnerRedDataClosureTests'
 code='import os,sys,unittest,gc;os.sched_setaffinity(0,{3,4});print({"actual_parent_cpu_ids":sorted(os.sched_getaffinity(0)),"scope":"pure data + owned print-only CPU binding dummy; no financial workload"},flush=True);sys.path.insert(0,"tests");from test_managed_variant_runner import '+classes+';from test_managed_variant_runner_red_closure import '+fixes+';suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in ('+classes+','+fixes+',)]);result=unittest.TextTestRunner(verbosity=2).run(suite);gc.collect();raise SystemExit(not result.wasSuccessful())'
 env=dict(os.environ,PYTHONWARNINGS='error::ResourceWarning',UTA_RUNNER_RED_CLOSURE_EVIDENCE=str(out/'affinity-real'))
 argv=[exe,'-W','error::ResourceWarning','-c',code];started=datetime.now(timezone.utc).isoformat();at=time.monotonic()
 with (out/(label+'.log')).open('w') as log:p=subprocess.run(argv,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT)
 record={'argv':argv,'source_before':hashes,'source_after':{name:sha256((root/name).read_bytes()).hexdigest() for name in items},'started_utc':started,'finished_utc':datetime.now(timezone.utc).isoformat(),'wall_seconds':time.monotonic()-at,'returncode':p.returncode,'dummy_processes':dummy,'no_financial_workload':True};runs.append(record)
 (out/'execution.json').write_text(json.dumps(runs,indent=2)+'\n');print(label,p.returncode,record['wall_seconds'],flush=True)
 if p.returncode:raise SystemExit(p.returncode)
