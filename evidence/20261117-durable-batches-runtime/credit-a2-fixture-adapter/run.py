from datetime import datetime, timezone
from hashlib import sha256
import json, os
from pathlib import Path
import subprocess
CODE=Path('/workspace/uta-capacity-next')
TESTS=Path('/workspace/uta-durable-batch-runtime/tests')
OUT=Path('/tmp/uta-batch-credit-673-d5')
executables={'python310':'/tmp/uta-python310/cpython-3.10.22-linux-x86_64-gnu/bin/python3.10','python312':'/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python','python313-sqlite346':'/usr/bin/python3.13'}
modules=['test_durable_batches.DurableBatchTests.'+name for name in ('test_cancel_and_same_currency_repay_commit_under_halt_and_stale_quote','test_reduce_only_limits_include_the_earlier_staged_order','test_conflicting_order_id_in_same_batch_has_no_second_effect','test_slow_first_command_seals_actual_prefix_without_claiming_remaining_effects')]
program='''import sys,pathlib,unittest
sys.path[:0]=[sys.argv[1],sys.argv[2]]
import uta, test_durable_batches
assert pathlib.Path(uta.__file__).resolve().is_relative_to(pathlib.Path(sys.argv[1]).resolve())
assert pathlib.Path(test_durable_batches.__file__).resolve()==pathlib.Path(sys.argv[2]).resolve()/'test_durable_batches.py'
suite=unittest.defaultTestLoader.loadTestsFromNames(sys.argv[3:])
result=unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() and result.testsRun==4 and not result.skipped else 1)
'''
def sources():
 return {str(p.relative_to(CODE)):sha256(p.read_bytes()).hexdigest() for p in sorted((CODE/'uta').rglob('*.py'))}
for name,python in executables.items():
 before=sources();test_before=sha256((TESTS/'test_durable_batches.py').read_bytes()).hexdigest();start=datetime.now(timezone.utc).isoformat()
 code_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=CODE,text=True).strip()
 argv=[python,'-I','-W','error::ResourceWarning','-c',program,str(CODE),str(TESTS),*modules]
 with (OUT/(name+'.txt')).open('x') as log:
  done=subprocess.run(argv,cwd=OUT,stdout=log,stderr=subprocess.STDOUT)
 after=sources();test_after=sha256((TESTS/'test_durable_batches.py').read_bytes()).hexdigest();raw=(OUT/(name+'.txt')).read_text()
 report={'runtime_commit':code_sha,'runtime_root':str(CODE),'test_root':str(TESTS),'test_commit':'d5b4001','test_file_sha256':test_before,'test_file_sha256_after':test_after,'source_sha256':before,'source_sha256_after':after,'started_at':start,'finished_at':datetime.now(timezone.utc).isoformat(),'command_argv':argv,'exit_code':done.returncode,'log_sha256':sha256(raw.encode()).hexdigest(),'source_unchanged':before==after and test_before==test_after,'passed':done.returncode==0 and before==after and test_before==test_after and 'ResourceWarning:' not in raw and 'Exception ignored in:' not in raw,'scope':'4 mixed-source fixture adapter cases only, not release qualification','production_approved':False}
 (OUT/(name+'.json')).write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({'runtime':name,'commit':code_sha,'passed':report['passed']}),flush=True)
