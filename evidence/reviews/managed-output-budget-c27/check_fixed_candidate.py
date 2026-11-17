"""Independent two-counter closure against exact author module bytes; pure only."""
from hashlib import sha256
import json,os,sys
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
from unittest.mock import patch
SOURCE=Path('/workspace/uta-managed-output-budget')
OUT=Path(__file__).parent
sys.path.insert(0,str(SOURCE))
sys.dont_write_bytecode=True
from tools import run_managed_long as runner
from tools import managed_output_budget as policy
from tests.test_managed_output_budget import OutputIntegrationTests
os.sched_setaffinity(0,{3})
started=monotonic()
files=['tools/run_managed_long.py','tools/managed_output_budget.py','tools/prepare_managed_stability.py','tests/test_managed_output_budget.py']
before={name:sha256((SOURCE/name).read_bytes()).hexdigest() for name in files}
plan=json.loads((SOURCE/'benchmarks/plans/20261117-managed-d421df3-six-hours.json').read_text())
plan['observer']['output_budget_bytes']=2*1024**3;plan['producer']['source_budget_bytes']=1024**3
with TemporaryDirectory() as directory:
 root=Path(directory);path=root/'plan.json';raw=json.dumps(plan).encode();path.write_bytes(raw)
 amendment=root/'change.json';amendment.write_text(json.dumps({'original_plan_sha256':sha256(raw).hexdigest(),'observer_interval_seconds_effective':61}))
 refused=False
 with patch.object(runner.subprocess,'Popen',side_effect=AssertionError('no producer process permitted')):
  try:runner.read_plan(path,amendment)
  except ValueError as error:
   assert str(error)=='explicit_output_policy_requires_actual_six_gib_source_budget'
   refused=True
 assert refused
case=OutputIntegrationTests()
with TemporaryDirectory() as directory:
 events,producer=case.exercise_one_collect(Path(directory),measure_error=MemoryError('controlled metadata allocation unknown'),control_size=0)
assert producer.terminate_owned.call_count==1
record=next(event for event in events if isinstance(event,tuple) and event[2].get('code')=='observer_output_budget_measurement_unknown')
assert record[2]['error_type']=='MemoryError' and record[2]['financial_corruption_inferred'] is False
assert events.index('drain')<events.index(record)
assert before=={name:sha256((SOURCE/name).read_bytes()).hexdigest() for name in files}
value={'reviewed_fixed_candidate':'499fd357ada91a7eefbb78d00a4763a4c2cc60d9','source_binding_fix':'08cdef397a44037cca9235a800fee58949574e8f','passed':True,
 'wrong_source_declaration_rejected':refused,'metadata_MemoryError_drain_calls':1,'drain_precedes_technical_log':True,
 'source_sha256':before,'source_unchanged':True,'all_producer_children_mocked':True,
 'SQL_native_service_benchmark_physical_OOM_or_oldjob_exercised':False,'cpu_ids':sorted(os.sched_getaffinity(0)),'wall_seconds':monotonic()-started,'long_run_approved':False,'production_approved':False}
(OUT/'fixed-candidate-pure-closure.json').write_text(json.dumps(value,indent=2)+'\n')
print(json.dumps(value,indent=2))
