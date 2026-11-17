"""Pure/file/AST checks; never instantiate Live/Child, Popen, SQL or phase CLI."""
import ast
import copy
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import time
from types import SimpleNamespace

BASE=Path(__file__).resolve().parent
ROOT=BASE.parents[2]
FROZEN=Path('/workspace/uta-credit-v2-py310-candidate')
started=time.monotonic();checks=[]
ns={'__name__':'pure_review'}
exec(compile((BASE/'run_one_long_phase.py').read_bytes(),'reviewed_runner','exec'),ns)
profilefile=ROOT/'benchmarks/profiles/managed-909acec-v4-long-conditional.json'
profile_raw=profilefile.read_bytes();profile=json.loads(profile_raw)
planfile=Path(profile['plan']);amendfile=Path(profile['amendment'])
plan=json.loads(planfile.read_bytes());amend=json.loads(amendfile.read_bytes())
def check(ok,name):
 assert ok,name
 checks.append(name)
def rejects(call,name):
 try:call()
 except ValueError:checks.append(name);return
 raise AssertionError(name)
# Extract exact real functions, not CLI main or operational imports.
def function(path,name,globals):
 tree=ast.parse(path.read_bytes());node=next(x for x in tree.body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef)) and x.name==name)
 exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),globals)
 return globals[name]
budget_ns={};exec(compile((FROZEN/'tools/managed_output_budget.py').read_bytes(),'budget','exec'),budget_ns)
ro=SimpleNamespace(load_json=lambda p:json.loads(p.read_bytes()),parse=json.loads)
read=function(FROZEN/'tools/run_managed_long.py','read_plan',{'sha256':sha256,'ro':ro,'output_budget_bytes':budget_ns['output_budget_bytes']})
p,change,hashes=read(planfile,amendfile)
check(hashes=={'base_plan_sha256':profile['plan_sha256'],'amendment_sha256':profile['amendment_sha256']},'actual_read_plan_hashes')
check((p['producer']['duration_seconds'],p['producer']['rate_rounds_per_second'],p['producer']['planned_rounds'],p['producer']['worker_fault_every_rounds'],p['producer']['parent_fault_every_rounds'],p['observer']['interval_seconds'])==(21600,.25,5400,30,300,61),'unchanged_workload')
check((p['observer']['blocks'],p['observer']['technical_read_unknown_budget'],p['observer']['maximum_consecutive_technical_read_unknown'])==(12,3,1),'unchanged_coverage')
check((p['producer']['source_budget_bytes'],budget_ns['output_budget_bytes'](p),p['observer']['max_private_clone_bytes'],p['observer']['clone_headroom_bytes'])==(6*1024**3,2*1024**3,1024**3,1024**3),'strict_6_2_1_1_budget')
check(sum((6,2,1,1,6))*1024**3+256*1024**2==17448304640,'combined_floor_exact')
check(profile['smoke02_evidence']['independent_actual_result_acceptance_commit']=='4052b708b74786a6b8ea8648868f0714817bfa1c','actual_independent_smoke02_bound')
check(all(profile.get(k) is False for k in ('continuous_6h_stability_passed','financial_6h_passed','live_coverage_passed','capacity_10000_per_s_passed','production_approved','current_execution_authorized')),'future_flags_false')
check(not Path(profile['long_scratch']).exists(),'no_new_long_job')
commands=function(FROZEN/'tools/prepare_managed_stability.py','commands',{'Path':Path})(profile)
source_ast=ast.parse((FROZEN/'tools/run_managed_long.py').read_bytes())
pref=next(x for x in source_ast.body if isinstance(x,ast.FunctionDef) and x.name=='preflight')
return_dict=next(x.value for x in ast.walk(pref) if isinstance(x,ast.Return) and isinstance(x.value,ast.Dict))
falsekeys={k.value for k,v in zip(return_dict.keys,return_dict.values) if isinstance(k,ast.Constant) and isinstance(v,ast.Constant) and v.value is False}
pre_flags={'financial_6h_passed','live_coverage_passed','capacity_10000_per_s_passed','production_approved'}
check(pre_flags<=falsekeys and 'continuous_6h_stability_passed' not in falsekeys and 'continuous_24h_stability_passed' not in falsekeys,'actual_source_AST_preflight_flags')
check(any(isinstance(x,ast.Attribute) and x.attr=='FLAGS' for x in ast.walk(source_ast)),'actual_source_start_ro_FLAGS')

def receipt(phase):
 if phase=='long-preflight':
  body={'status':'PREFLIGHT_ONLY_NOT_STARTED','service_started':False,'producer_source_commit':ns['SOURCE'],'observer_freeze_commit':ns['SOURCE'],'base_plan_sha256':profile['plan_sha256'],'amendment_sha256':profile['amendment_sha256'],'qualification':{'code_commit':ns['SOURCE'],'tests_run':1801},**dict.fromkeys(pre_flags,False)}
 else:
  body={'status':'SUPERVISOR_STARTED_PENDING_ACTUAL_DRIVER','supervisor_pid':123456,'supervisor_birth':'99','scratch':profile['long_scratch'],'actual_driver_identity_file':profile['long_scratch']+'/control/launch.json',**dict.fromkeys(ns['FLAGS'],False)}
 return {'exit_code':0,'stdout_complete':True,'phase':phase,'structured_stdout':body}
for phase in ns['PHASES']:
 spec=json.loads((BASE/(phase+'-spec.json')).read_bytes())
 check(spec['argv']==[profile['python'],'-B',str(FROZEN/'tools/prepare_managed_stability.py'),'--profile',str(profilefile),'--invoke',phase,'--root-go-profile-sha256',sha256(profile_raw).hexdigest()],'exact_wrapper_'+phase)
 check(commands[phase]==json.loads((BASE/'exact-long-commands.json').read_bytes())['phases'][phase]['frozen_target_argv'],'actual_frozen_target_'+phase)
 check(spec['profile_sha256']==sha256(profile_raw).hexdigest() and spec['runner_sha256']==sha256((BASE/'run_one_long_phase.py').read_bytes()).hexdigest(),'spec_final_hash_'+phase)
 value=receipt(phase);ns['verify_receipt'](phase,value,spec,profile);checks.append('literal_positive_'+phase)
 for name,alter in [('nested_exit',lambda v:v.update(exit_code=1)),('timeout',lambda v:v.update(timed_out=True)),('incomplete',lambda v:v.update(stdout_complete=False)),('nested_capture_fake',lambda v:v['structured_stdout'].update(timed_out=False)),('future_flag',lambda v:v['structured_stdout'].update(production_approved=True))]:
  broken=copy.deepcopy(value);alter(broken)
  rejects(lambda:ns['verify_receipt'](phase,broken,spec,profile),name+'_'+phase)
 class Fake:
  def __init__(self,fail=None,cleanupfail=False):self.calls=[];self.fail=fail;self.cleanupfail=cleanupfail
  def call(self,name):
   self.calls.append(name)
   if self.fail==name:raise ValueError('primary_'+name)
  def wait_window(self):self.call('wait')
  def admit(self):self.call('admit');return 'admission'
  def spawn(self,admission):self.call('spawn');return 'owned_child'
  def finish(self,child):self.call('finish');return value
  def post_hash_clock(self):self.call('post_hash');return {'wall_ns':1,'boottime_ns':2}
  def stop_owned_wrapper(self):self.calls.append('stop');
  def close(self):
   self.calls.append('close')
   if self.cleanupfail:raise OSError('secondary')
 io=Fake();out=ns['execute'](spec,profile,io)
 check(out['status']=='PHASE_RECEIPT_VERIFIED' and io.calls==['wait','admit','spawn','finish','post_hash','close'] and out['next_phase_authorized'] is False,'one_phase_only_'+phase)
 for step in ('wait','admit','spawn','finish','post_hash'):
  io=Fake(step,True);out=ns['execute'](spec,profile,io)
  check(out['status']=='UNKNOWN_NO_GO_DO_NOT_REPEAT' and out['error_digest']==sha256(('primary_'+step).encode()).hexdigest() and 'stop' in io.calls and out.get('close_secondary_error')=='OSError','primary_cleanup_'+step+'_'+phase)
 specraw=(BASE/(phase+'-spec.json')).read_bytes();runnerraw=(BASE/'run_one_long_phase.py').read_bytes()
 record=json.loads((BASE/(phase+'-root-record-TEMPLATE.json')).read_bytes());record.update(authorized=True,issued_wall_ns=100,issued_boottime_ns=100,valid_until_wall_ns=1000,valid_until_boottime_ns=1000)
 def approve(r,wall=101,boot=101):
  raw=json.dumps(r).encode();return ns['approval'](specraw,profile_raw,runnerraw,raw,sha256(raw).hexdigest(),wall=wall,boot=boot,boot_id=record['source_boot'])
 approve(record);checks.append('literal_root_GO_'+phase)
 for field in ('spec_sha256','profile_sha256','runner_sha256','command_sha256'):
  wrong=copy.deepcopy(record);wrong[field]='0'*64;rejects(lambda:approve(wrong),'root_hash_reject_'+field+'_'+phase)
 rejects(lambda:approve(record,99,101),'root_wall_rollback_'+phase)
 rejects(lambda:approve(record,101,99),'root_boot_rollback_'+phase)
 rejects(lambda:approve(record,1000,101),'root_expired_'+phase)
 rejected=copy.deepcopy(record);rejected['phase']='long-start' if phase=='long-preflight' else 'long-preflight';rejects(lambda:approve(rejected),'root_phase_reject_'+phase)
fixture=ns['Live'].__new__(ns['Live']);fixture.root={'issued_wall_ns':10,'issued_boottime_ns':10,'valid_until_wall_ns':100,'valid_until_boottime_ns':100};fixture.deadline=90;fixture.children=[]
fixture.clock=lambda:{'wall_ns':50,'boottime_ns':50}
check(fixture.post_hash_clock()=={'wall_ns':50,'boottime_ns':50},'actual_same_validated_endpoint')
fixture.clock=lambda:{'wall_ns':50,'boottime_ns':90}
rejects(fixture.post_hash_clock,'actual_endpoint_deadline_rejected')
fixture.clock=lambda:{'wall_ns':9,'boottime_ns':50}
rejects(fixture.post_hash_clock,'actual_endpoint_wall_rollback_rejected')
check(ns['error_fields'](ValueError('SECRET_BODY'))['error_code'] is None,'unknown_error_redaction')
check(ns['error_fields'](ValueError('original_metadata_or_effective_heartbeat_stale'))['error_code']=='original_metadata_or_effective_heartbeat_stale','safe_unknown_code')
result={'status':'PURE_CHECKS_PASS','checks':len(checks),'check_names':checks,'elapsed_seconds':time.monotonic()-started,'real_Popen_calls':0,'SQL_calls':0,'observer_or_producer_CLI_calls':0,'new_job_created':False,'source_frozen_root':str(FROZEN)}
(BASE/'pure-check-result.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='check_names'},indent=2))
