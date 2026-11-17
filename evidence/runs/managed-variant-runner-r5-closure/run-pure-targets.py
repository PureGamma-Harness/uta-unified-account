from pathlib import Path
from hashlib import sha256
from datetime import datetime,timezone
import json,os,subprocess,time
root=Path('/workspace/uta-managed-variant-runner-fix');out=Path('/tmp/uta-runner-R5-final-pure');out.mkdir(exist_ok=False)
inputs=['tools/run_managed_variants.py','tests/test_managed_variant_runner.py','tests/runner_package_fixtures.py','tests/test_managed_variant_runner_package_closure.py','benchmarks/plans/20261117-managed-variants-execution-template.json'];before={name:sha256((root/name).read_bytes()).hexdigest() for name in inputs};runs=[]
for label,exe in [('py312','/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python'),('py310','/tmp/uta-python310/cpython-3.10.22-linux-x86_64-gnu/bin/python3.10'),('py313','/usr/bin/python3.13')]:
 code='import os,sys,gc,unittest;os.sched_setaffinity(0,{3});sys.path.insert(0,"tests");from test_managed_variant_runner import RunnerPureTests;from test_managed_variant_runner_red_closure import RunnerRedDataClosureTests;from test_managed_variant_runner_package_closure import RunnerPackageOmissionClosureTests;suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in (RunnerPureTests,RunnerRedDataClosureTests,RunnerPackageOmissionClosureTests)]);r=unittest.TextTestRunner(verbosity=2).run(suite);gc.collect();raise SystemExit(not r.wasSuccessful())'
 argv=[exe,'-W','error::ResourceWarning','-c',code];started=datetime.now(timezone.utc).isoformat();at=time.monotonic()
 with (out/(label+'.log')).open('w') as log:p=subprocess.run(argv,cwd=root,env=dict(os.environ,PYTHONWARNINGS='error::ResourceWarning'),stdout=log,stderr=subprocess.STDOUT)
 runs.append({'argv':argv,'started_utc':started,'finished_utc':datetime.now(timezone.utc).isoformat(),'wall_seconds':time.monotonic()-at,'returncode':p.returncode,'source_before':before,'source_after':{name:sha256((root/name).read_bytes()).hexdigest() for name in inputs},'pure_data_only':True,'no_collector_build_install_SQL_or_benchmark':True,'cpu_ids':[3]})
 (out/'execution.json').write_text(json.dumps(runs,indent=2)+'\n');print(label,p.returncode,runs[-1]['wall_seconds'],flush=True)
 if p.returncode:raise SystemExit(p.returncode)
