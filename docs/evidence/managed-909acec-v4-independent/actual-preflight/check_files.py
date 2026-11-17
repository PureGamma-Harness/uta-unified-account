"""Independent retained-file/math check; no product import, SQL, capture, or invoke."""
from datetime import datetime,timezone
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
P=Path('/workspace/uta-managed-observer-runs/909acec-v4-long-preflight-private')
R=Path('/workspace/uta-managed-observer-runs/909acec-v4-long-preflight-root-private')
V=Path('/workspace/uta-managed-909acec-prepare/evidence/preparations/managed-909acec-v4')
SOURCE='909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0';BOOT='6339d4fc-a9e7-4c10-a591-1e70a14322ff'
checks=[];inputs={}
def need(ok,label):
 if not ok:raise AssertionError(label)
 checks.append(label)
def raw(p):
 b=p.read_bytes();inputs[str(p)]={'bytes':len(b),'sha256':sha256(b).hexdigest()};return b
def h(p):return sha256(raw(p)).hexdigest()
def load(p):return json.loads(raw(p))
s=load(V/'long-preflight-spec.json');profile=load(Path(s['profile_file']));root=load(R/'root-approved-phase.json')
need(h(V/'long-preflight-spec.json')=='154010e82fe48d8a63380de34e0df75557a04a6c3385aff10aa74174076c9c4c','reviewed_spec')
need(h(V/'run_one_long_phase.py')==s['runner_sha256']=='49c34950c38056be2fdef534a7d252a579fde20bd1d0f5195ec39df0ae527210','reviewed_runner')
need(h(Path(s['profile_file']))==s['profile_sha256']=='9ecd5476c347fbf1d767445f6c73a26fde46b026c7008d9b0f24f36e8801213d','reviewed_profile')
go=load(next(P.glob('*-root-delegated-phaseGO.json')));ap=next(P.glob('*-admission.json'));a=load(ap);pop=load(P/'actual-Popen.json');i=pop['identity']
need(root['authorized'] is True and root['phase']=='long-preflight' and root['scope']=='ONE_EXACT_LONG_PHASE_NO_NEXT_PHASE','single_phase_root_GO')
need(root['spec_sha256']==h(V/'long-preflight-spec.json') and root['runner_sha256']==s['runner_sha256'] and root['profile_sha256']==s['profile_sha256'],'root_three_hashes')
cmdh=sha256(json.dumps(s['argv'],separators=(',',':')).encode()).hexdigest()
need(root['command_sha256']==go['command_sha256']==pop['command_sha256']==a['phase_command_sha256']==s['command_sha256']==cmdh,'exact_command_binding')
need(go['authorized'] is True and go['root_phase_delegation_record_sha256']==h(R/'root-approved-phase.json') and go['root_approved_spec_sha256']==root['spec_sha256'] and go['snapshot_sha256']==h(ap),'durable_GO_binding')
need(h(ap)=='f14d020356143c2196523cca10528601a5c1a3e6a31aef2c37a0969c1f137851','exact_original_admission')
need(root['source_commit']==a['source_commit']==SOURCE and root['source_boot']==a['source_boot']==i['boot']==BOOT and a['phase']==go['phase']=='long-preflight','source_phase_boot')
cw,cb,vw,vb=(a[k] for k in ('captured_wall_ns','captured_boottime_ns','valid_until_wall_ns','valid_until_boottime_ns'));nw,nb=i['captured_wall_ns'],i['captured_boottime_ns']
need(cw<=nw<vw and cb<=nb<vb and 0<=nw-cw<=15*10**9 and 0<=nb-cb<=15*10**9,'dual_clock_fresh_after_Popen')
po,lo,pm,lm=(a[k] for k in ('original_progress_observed_ns','original_latest_observed_ns','original_progress_mtime_ns','original_latest_mtime_ns'))
ph,lh=(Fraction(str(a[k])) for k in ('original_progress_heartbeat_age_seconds','original_latest_heartbeat_age_seconds'))
need(all(0<t<=cw for t in (po,lo,pm,lm)) and a['capture_started_wall_ns']<=cw,'no_future_original_timestamps')
need(0<=ph+Fraction(nw-po,10**9)<=15 and 0<=lh+Fraction(nw-lo,10**9)<=30 and 0<=nw-pm<=15*10**9 and 0<=nw-lm<=30*10**9,'original_effective_HB_mtime_at_Popen')
need(vb-cb==vw-cw and vw<=cw+15*10**9 and vw<=po+15*10**9 and vw<=pm+15*10**9 and vw<=lm+30*10**9,'minimum_validity_deadline')
need(a['fresh_free_bytes']==17653497856 and a['fresh_free_bytes']-17448304640==205193216 and a['required_free_bytes']==17448304640,'full_combined_floor')
need(a['observer_source_commit']=='f96dfd8d6b1ca6f5ae28ac771c886baf4fdeb30e' and a['observer_interval_seconds']==60 and a['allowlisted_observer_cli']=={'--interval':'60'} and a['observer_default_post_write_software_threshold_bytes']==64*1024**2 and a['observer_original_no_alerts'] is True,'old_observer_source_CLI')
for side in ('original_processes_before','original_processes_after'):
 need(all(a[side][str(pid)]['birth']==birth and a[side][str(pid)]['uids']==[1000]*4 and a[side][str(pid)]['state']=='S' for pid,birth in [(4471,'210004'),(8784,'412799')]),'protected_identity:'+side)
need(a['conditional_floor_is_hard_quota'] is False and a['observer_current_logical_bytes']+a['all_matching_external_staging_bytes']+a['projected_additional_6h_stress_assumption_bytes']<256*1024**2,'conditional_contingency_not_quota')
m=load(P/'closed-private-stream-manifest.json')
for stream in ('stdout','stderr'):
 b=raw(P/('actual-wrapper.'+stream));d=m[stream]
 need(d['complete'] is True and d['error'] is None and len(b)==d['bytes']==d['retained_bytes'] and len(b)<=4*1024**2 and sha256(b).hexdigest()==d['sha256'],'complete_actual_raw:'+stream)
need(raw(P/'actual-wrapper.stderr')==b'','actual_empty_stderr')
r=load(P/'actual-wrapper.stdout');b=r['structured_stdout']
need(type(r['exit_code']) is int and r['exit_code']==0 and r['stdout_complete'] is True and r['stderr_present'] is False and r['phase']=='long-preflight','actual_outer_receipt')
need('exit_code' not in b and 'timed_out' not in b and b['status']=='PREFLIGHT_ONLY_NOT_STARTED' and b['service_started'] is False,'actual_direct_shape')
need(b['producer_source_commit']==b['observer_freeze_commit']==SOURCE and b['base_plan_sha256']==profile['plan_sha256'] and b['amendment_sha256']==profile['amendment_sha256'],'actual_source_plan_amendment')
need(b['qualification']['engineering_test_qualified'] is True and b['qualification']['code_commit']==SOURCE and type(b['qualification']['tests_run']) is int and b['qualification']['tests_run']==1801,'actual_1801_qualification')
need(b['source_readonly_device_probe']=={'source_readonly':True,'devnull_character_device':True,'devnull_child_exit':0},'actual_readonly_devnull_probe')
need(b['selected_cpu']==0 and b['observer_cli_interval_seconds']==61 and b['conservative_required_free_bytes']==10*1024**3 and b['source_budget_bytes']==6*1024**3 and b['observer_output_budget_bytes']==2*1024**3 and b['private_clone_budget_bytes']==b['clone_headroom_bytes']==1024**3,'actual_CPU_61_interval_and_10GiB_new_budget')
expected=[profile['python'],'-B','benchmarks/run_managed_soak.py','run','--directory',profile['long_scratch']+'/job','--duration','21600','--allow-long-run','--validation-report',profile['validation_report']]
need(b['producer_command_argv']==expected,'actual_default_21600_argv')
need(b['expected_business_counts']=={'account_commands':32400,'orders':21600,'fills':21600,'matches':10800,'risk_decisions':43200,'ledger_events':27006,'partial_cancelled_orders':5400,'worker_fault_signals':180,'parent_fault_signals':18},'expected_not_completed_counts')
need(all(b[k] is False for k in ('financial_6h_passed','live_coverage_passed','production_approved','capacity_10000_per_s_passed','continuous_resume_allowed')),'future_flags_false')
out=load(P/'phase-outcome.json');att=load(R/'root-phase-attestation.json');outer=load(R/'runner.stdout')
need(out==outer==att['result'] and out['status']=='PHASE_RECEIPT_VERIFIED' and out['response']['service_started'] is False,'retained_outcome_consistent')
need(att['runner_exit_code']==0 and att['primary_error'] is None and att['cleanup_secondary_errors']==[] and att['root_watchdog_reason'] is None and att['status']=='RUNNER_RETURNED','no_outer_errors_or_watchdog')
for stream in ('stdout','stderr'):
 content=raw(R/('runner.'+stream));need(len(content)==att['raw_private_only'][stream]['bytes'] and sha256(content).hexdigest()==att['raw_private_only'][stream]['sha256'],'actual_root_raw_hash:'+stream)
need(raw(R/'runner.stderr')==b'','root_empty_stderr')
pc=out['post_hash_clock'];end=att['root_post_stream_close_fsync_read_hash_parse_endpoint'];first=pop['first_Popen_boottime_ns']
need(pop['phase_deadline_boottime_ns']==first+75*10**9 and first<=nb<=pc['boottime_ns']<=end['boottime_ns']<pop['phase_deadline_boottime_ns'],'same_fixed_75s_deadline_post_hash')
need(root['issued_wall_ns']<=pc['wall_ns']<=end['wall_ns']<root['valid_until_wall_ns'] and root['issued_boottime_ns']<=first<=end['boottime_ns']<root['valid_until_boottime_ns'],'root_dual_clock_valid')
need(out['next_phase_authorized'] is False and out['repeat_start_allowed'] is False and att['next_phase_authorized'] is False,'no_start_or_repeat_authority')
need(not Path(profile['long_scratch']).exists(),'new_long_job_absent_at_review')
print(json.dumps({'status':'ACTUAL_PREFLIGHT_RETAINED_FILE_SCOPE_ACCEPT','reviewed_at_utc':datetime.now(timezone.utc).isoformat(),'checks_passed':len(checks),'checks':checks,'input_hashes':inputs,'source_commit':SOURCE,'fresh_free_capture_bytes':a['fresh_free_bytes'],'combined_floor_margin_bytes':a['fresh_free_bytes']-17448304640,'remaining_snapshot_after_Popen_ns':min(vw-nw,vb-nb),'first_to_phase_post_hash_ns':pc['boottime_ns']-first,'first_to_root_post_hash_ns':end['boottime_ns']-first,'new_job_absent_at_review':True,'supports_separate_root_fresh_start_admission_only':True,'preflight_snapshot_reusable_for_start':False,'SQL_or_capture_or_Popen_or_product_import':False,'long_start_authorized':False,'financial_6h_passed':False,'production_approved':False},indent=2,sort_keys=True))
