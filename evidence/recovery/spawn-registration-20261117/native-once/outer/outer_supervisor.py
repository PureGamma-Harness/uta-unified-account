from pathlib import Path
import hashlib,json,os,sys,time,traceback
ROOT=Path('/workspace/uta-stopped-owner-gate')
OUT=Path('/workspace/uta-spawn-native-once-supervisor-20261117')
sys.path.insert(0,str(ROOT))
os.sched_setaffinity(0,{1})
from tools.run_managed_variants import owned_run,process_identity
from tests.test_durable_process import _orphan_reaper
started=time.monotonic()
expected='7c60c774c283e43dcd72c36cb357abee42d23bcab09c516de4d7d559b4afbaa8'
assert hashlib.sha256((ROOT/'tests/stopped_gate_recovery_probe.py').read_bytes()).hexdigest()==expected
argv=[sys.executable,'-B','tests/stopped_gate_recovery_probe.py','--execute','--case','all','--cpu','1','--output','/workspace/uta-spawn-native-once-private-20261117']
(OUT/'wrapper-identity.json').write_text(json.dumps({'identity':process_identity(os.getpid()),'argv':argv,'driver_sha256':expected,'outer_wall_seconds':23,'term_grace_seconds':.25,'kill_wait_seconds':.25,'subreaper_budget_seconds':5,'instrumented_diagnostic':True},indent=2)+'\n')
try:
 with _orphan_reaper():
  result=owned_run(argv,str(ROOT),OUT/'driver',cpu_ids=[1],wall_seconds=23,grace_seconds=.25,kill_wait_seconds=.25,output_cap=512*1024,protected={4471,8784,310035,310039,310266,310269})
 result['outer_total_seconds']=time.monotonic()-started
 result['under_30s']=result['outer_total_seconds']<=30
 (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
except BaseException as error:
 (OUT/'outer-error.txt').write_text(traceback.format_exc())
 (OUT/'result.json').write_text(json.dumps({'outcome':'UNKNOWN','error_type':type(error).__name__,'outer_total_seconds':time.monotonic()-started},indent=2)+'\n')
 raise
