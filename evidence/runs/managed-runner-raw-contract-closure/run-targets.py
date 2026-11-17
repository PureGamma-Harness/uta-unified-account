from pathlib import Path
from hashlib import sha256
from datetime import datetime,timezone
import json,os,subprocess,time
root=Path('/workspace/uta-managed-variant-runner-final-fix');out=root/'evidence/runs/managed-runner-raw-contract-closure';names=['tools/run_managed_variants.py','tests/test_managed_variant_runner_raw_contract.py'];before={n:sha256((root/n).read_bytes()).hexdigest() for n in names};records=[]
for label,exe in [('py312','/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python'),('py310','/tmp/uta-python310/cpython-3.10.22-linux-x86_64-gnu/bin/python3.10'),('py313','/usr/bin/python3.13')]:
 code='import unittest,gc;from tests.test_managed_variant_runner import RunnerPureTests;from tests.test_managed_variant_runner_red_closure import RunnerRedDataClosureTests;from tests.test_managed_variant_runner_package_closure import RunnerPackageOmissionClosureTests;from tests.test_managed_variant_runner_raw_contract import RunnerRawContractTests;suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in (RunnerPureTests,RunnerRedDataClosureTests,RunnerPackageOmissionClosureTests,RunnerRawContractTests)]);result=unittest.TextTestRunner(verbosity=2).run(suite);gc.collect();raise SystemExit(not result.wasSuccessful())'
 argv=[exe,'-W','error::ResourceWarning','-c',code];started=datetime.now(timezone.utc).isoformat();at=time.monotonic()
 with (out/(label+'.log')).open('w') as log:p=subprocess.run(argv,cwd=root,env=dict(os.environ,PYTHONWARNINGS='error::ResourceWarning'),stdout=log,stderr=subprocess.STDOUT)
 records.append({'argv':argv,'started_utc':started,'finished_utc':datetime.now(timezone.utc).isoformat(),'returncode':p.returncode,'seconds':time.monotonic()-at,'source_before':before,'source_after':{n:sha256((root/n).read_bytes()).hexdigest() for n in names},'cpu_ids':sorted(os.sched_getaffinity(0)),'pure_data_only':True,'dummy_SQL_service_collector_build_install_or_benchmark_executed':False});(out/'execution.json').write_text(json.dumps(records,indent=2)+'\n');print(label,p.returncode,records[-1]['seconds'],flush=True)
 if p.returncode:raise SystemExit(p.returncode)
