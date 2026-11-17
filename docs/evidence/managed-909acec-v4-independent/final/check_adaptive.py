"""Independent pure JSON/hash/AST and in-memory adapter checks. No operational IO."""
import ast
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

PREP=Path('/workspace/uta-managed-909acec-prepare')
V4=PREP/'evidence/preparations/managed-909acec-v4'
SRC=Path('/workspace/uta-credit-v2-py310-candidate')
SOURCE='909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0'
checks=[];inputs={}
def need(ok,label):
 if not ok:raise AssertionError(label)
 checks.append(label)
def raw(p):
 b=p.read_bytes();inputs[str(p)]={'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()};return b
def sha(b):return hashlib.sha256(b).hexdigest()
def load(p):return json.loads(raw(p))
def ch(cmd):return sha(json.dumps(cmd,separators=(',',':')).encode())
profilefile=PREP/'benchmarks/profiles/managed-909acec-v4-long-conditional.json'
p=load(profilefile);plan=load(Path(p['plan']));amend=load(Path(p['amendment']));commands=load(V4/'exact-long-commands.json')
runner_raw=raw(V4/'run_one_long_phase.py');runner_tree=ast.parse(runner_raw)
need(sha(runner_raw)=='49c34950c38056be2fdef534a7d252a579fde20bd1d0f5195ec39df0ae527210','exact_final_runner')
need(sha(raw(profilefile))=='9ecd5476c347fbf1d767445f6c73a26fde46b026c7008d9b0f24f36e8801213d','exact_final_profile')
need(p['source_commit']==plan['source_commit']==commands['source_commit']==SOURCE,'exact_909_no_cross_source')
need(sha(raw(Path(p['plan'])))==p['plan_sha256']==commands['plan_sha256']==amend['original_plan_sha256'],'immutable_plan_binding')
need(sha(raw(Path(p['amendment'])))==p['amendment_sha256']==commands['amendment_sha256'],'immutable_amendment_binding')
need(commands['profile_sha256']==sha(raw(profilefile)),'commands_profile_binding')
for obj in (p,plan,plan['smoke']['actual_predecessor_evidence']):
 if 'smoke02_evidence' in obj:obj=obj['smoke02_evidence']
 need(obj['independent_actual_result_acceptance_commit']=='4052b708b74786a6b8ea8648868f0714817bfa1c','actual_smoke02_independent_commit')
 need(obj['root_auxiliary_hash_and_final_attestation_full_latency_seconds'] is None,'timing_gap_not_fabricated')
 need(obj['full_business_event_or_every_decision_risk_reexecution_passed'] is None,'reexecution_not_falsely_claimed')
for k in ('execution_authorized','current_execution_authorized','phase_execution_authorized','service_started','long_service_started','long_preflight_executed','long_start_executed','financial_6h_passed','continuous_6h_stability_passed','continuous_24h_stability_passed','production_approved','capacity_10000_approved'):
 need(p[k] is False,'pending_profile:'+k)
q=p['qualification'];need(q['status']=='COMPLETE_ALL_GATES_PASSED' and q['actual_executed_tests_each']==1801 and q['blocked_reason'] is None,'qualified_same_source_references')
need(q['local_evidence_commit']=='841b5cc908e7e15e9461c0ecc91a173e2162cada' and q['ci_evidence_commit']=='85e96b63813e0b993e532f054ef97740e64176cd'
 and q['package_author_commit']=='721e9d02308d900cd39db2a209d0130394f78338' and q['package_peer_commit']=='5c98110359f293413ebe561b3cb2f5683ee26863','existing_qualification_refs_unchanged_not_rerun')
pd=plan['producer'];ob=plan['observer'];res=plan['resource_policy']
need((pd['duration_seconds'],pd['rate_rounds_per_second'],pd['planned_rounds'],pd['worker_fault_every_rounds'],pd['parent_fault_every_rounds'],amend['observer_interval_seconds_effective'])==(21600,.25,5400,30,300,61),'full_original_workload')
need((ob['blocks'],ob['technical_read_unknown_budget'],ob['maximum_consecutive_technical_read_unknown'],ob['independent_finance_golden_required_each_1800_second_block'])==(12,3,1,1),'complete_coverage_budgets')
need(plan['independent_new_clock']['required_actual_active_seconds']==21600 and plan['independent_new_clock']['shorten_to_old_job_deadline_allowed'] is False,'no_truncation_at_old_deadline')
need(pd['source_budget_bytes']==6*1024**3 and ob['output_budget_bytes']==2*1024**3 and ob['max_private_clone_bytes']==ob['clone_headroom_bytes']==1024**3,'unchanged_6_2_1_1_budget')
need(res['new_total_bytes']==10*1024**3 and res['combined_conservative_required_bytes']==(16*1024**3+256*1024**2)==17448304640,'exact_cohost_conditional_floor')
need(res['space_reserved'] is False and res['floor_is_hard_cap'] is False and ob['output_physical_hard_quota_enforced'] is False and ob['output_budget_overshoot_guaranteed_bound_bytes'] is None,'no_quota_or_reservation_claim')
need(plan['first_smoke01']['never_resume_or_reclassify'] is True,'first_smoke01_permanent_NO_GO')
need(plan['cohost']['old_producer_pid']==4471 and plan['cohost']['old_producer_birth']=='210004' and plan['cohost']['old_observer_pid']==8784 and plan['cohost']['old_observer_birth']=='412799','protected_cohost_identity_contract')

# Execute only the reviewed pure receipt function and clock methods, extracted by AST.
parts=[n for n in runner_tree.body if isinstance(n,ast.FunctionDef) and n.name in {'need','verify_receipt'}]
parts += [n for n in runner_tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='FLAGS' for t in n.targets)]
ns={'SOURCE':SOURCE};exec(compile(ast.Module(body=parts,type_ignores=[]),'<pure adapter>','exec'),ns)
source_tree=ast.parse(raw(SRC/'tools/run_managed_long.py'))
f=next(n for n in source_tree.body if isinstance(n,ast.FunctionDef) and n.name=='preflight')
ret=next(n for n in f.body if isinstance(n,ast.Return));keys={k.value for k in ret.value.keys if isinstance(k,ast.Constant)}
need({'financial_6h_passed','live_coverage_passed','production_approved','capacity_10000_per_s_passed'}<=keys and not {'continuous_6h_stability_passed','continuous_24h_stability_passed'}&keys,'actual_preflight_AST_shape')
pre={'status':'PREFLIGHT_ONLY_NOT_STARTED','service_started':False,'producer_source_commit':SOURCE,'observer_freeze_commit':SOURCE,'base_plan_sha256':p['plan_sha256'],'amendment_sha256':p['amendment_sha256'],'qualification':{'code_commit':SOURCE,'tests_run':1801},'financial_6h_passed':False,'live_coverage_passed':False,'production_approved':False,'capacity_10000_per_s_passed':False}
flags_tree=ast.parse(raw(SRC/'tools/managed_soak_observer.py'))
startflags=next(ast.literal_eval(n.value) for n in flags_tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='FLAGS' for t in n.targets))
need(set(startflags)==set(ns['FLAGS']) and all(v is False for v in startflags.values()),'actual_start_flags_AST_shape')
start=dict(startflags,status='SUPERVISOR_STARTED_PENDING_ACTUAL_DRIVER',scratch=p['long_scratch'],supervisor_pid=999999,supervisor_birth='123',actual_driver_identity_file=p['long_scratch']+'/control/launch.json')
for phase,body in [('long-preflight',pre),('long-start',start)]:
 spec=load(V4/(phase+'-spec.json'));entry=commands['phases'][phase]
 need(spec['runner_sha256']==sha(runner_raw) and spec['profile_sha256']==sha(raw(profilefile)),'final_spec_binding:'+phase)
 need(spec['argv']==entry['wrapper_argv'] and ch(spec['argv'])==spec['command_sha256']==entry['wrapper_command_sha256'],'wrapper_exact:'+phase)
 expected=[p['python'],'-B',str(SRC/'tools/prepare_managed_stability.py'),'--profile',str(profilefile),'--invoke',phase,'--root-go-profile-sha256',sha(raw(profilefile))]
 need(spec['argv']==expected,'literal_wrapper:'+phase)
 target=[p['python'],'-B',str(SRC/'tools/run_managed_long.py'),phase.removeprefix('long-'),'--plan',p['plan'],'--amendment',p['amendment'],'--scratch',p['long_scratch']]
 need(entry['frozen_target_argv']==target and ch(target)==entry['frozen_target_command_sha256'],'frozen_target_exact:'+phase)
 need(entry['root_specific_GO'] is None and entry['fresh_snapshot'] is None and entry['execution_authorized'] is False,'no_actual_phase_authority:'+phase)
 value={'phase':phase,'exit_code':0,'stdout_complete':True,'structured_stdout':body}
 ns['verify_receipt'](phase,value,spec,p);need(True,'real_phase_schema_fixed:'+phase)
 for field,bad in [('exit_code',True),('exit_code',-15),('stdout_complete',False),('timed_out',True)]:
  v=copy.deepcopy(value);v[field]=bad
  try:ns['verify_receipt'](phase,v,spec,p)
  except ValueError:need(True,'literal_bad_receipt_rejected:'+phase+':'+field+':'+str(bad))
  else:raise AssertionError('bad receipt accepted')
cls=next(n for n in runner_tree.body if isinstance(n,ast.ClassDef) and n.name=='Live')
methods=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in {'budget','post_hash_clock'}]
c=ast.ClassDef(name='ClockSubject',bases=[],keywords=[],body=methods,decorator_list=[])
exec(compile(ast.fix_missing_locations(ast.Module(body=[c],type_ignores=[])),'<pure endpoint>','exec'),ns)
for tick,allowed in [(74,True),(75,False),(76,False),(0,False),(101,False)]:
 obj=ns['ClockSubject']();obj.root={'issued_wall_ns':1,'valid_until_wall_ns':100,'issued_boottime_ns':1,'valid_until_boottime_ns':100};obj.deadline=75;obj.children=[];calls=[]
 def clock():calls.append(tick);return {'wall_ns':tick,'boottime_ns':tick}
 obj.clock=clock
 try:r=obj.post_hash_clock()
 except ValueError:need(not allowed,'clock_reject:'+str(tick))
 else:need(allowed and r['boottime_ns']==tick,'clock_accept:'+str(tick))
 need(len(calls)==1,'single_verified_endpoint_read:'+str(tick))

# Root launcher exact ownership structure: try is first executable statement
# after local setup following Popen; both metadata operations are within it.
launcher_raw=raw(Path('/workspace/uta-root-run-one-long-phase.py'))
need(sha(launcher_raw)=='aab22dc68a389d1b4bc4f83c1a59eee1315191e1f4f522546f043e8c36ac6b44','exact_root_launcher_fixed')
lt=ast.parse(launcher_raw);main=next(n for n in lt.body if isinstance(n,ast.FunctionDef) and n.name=='main')
block=next(n for n in main.body if isinstance(n,ast.With) and any(isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute) and x.func.attr=='Popen' for x in ast.walk(n)))
protected=next(n for n in block.body if isinstance(n,ast.Try));segment=ast.get_source_segment(launcher_raw.decode(),protected)
need('birth = stat.read_text()' in segment and "'root-launcher-Popen.json'" in segment and protected.finalbody,'post_Popen_metadata_inside_cleanup_try')
need("if child.returncode is None:" in segment and 'os.killpg(child.pid' in segment and 'timeout=2' in segment and 'cleanup_errors.append' in segment,'only_unreaped_owned_group_cleanup')
need("successful_outer = code == 0 and watchdog is None and primary is None and not cleanup_errors" in launcher_raw.decode(),'primary_and_cleanup_errors_cannot_pass')
print(json.dumps({'status':'PURE_ADAPTIVE_CONTRACT_ACCEPT_NO_PHASE_AUTHORITY','checked_at_utc':datetime.now(timezone.utc).isoformat(),'checks_passed':len(checks),'checks':checks,'inputs':inputs,'SQL':False,'real_Popen':False,'new_job_created':False,'new_long_authorized':False},indent=2,sort_keys=True))
