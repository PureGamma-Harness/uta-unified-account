"""Independent read-only file/source/proc evidence checker; no SQL or signals."""
from collections import Counter
from datetime import datetime,timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
AUTHOR='b5707fe319cf4f07c64e34e8a62f130e5a135803'
APPROVED='5e26f0acd04b47cdafad942464e70b537c70d30b'
BASE='91e4ae40b5e9b884c54026406299df5000c9c100'
PREFIX='evidence/runs/recovery-horizon91/'
EXPECTED_DRIVER='81b9a0c8ee7ed45f58f38174895ad2fa4e7d3043fd6ab7c03903016d69cae2ee'
def blob(commit,name):
 return subprocess.check_output(['git','show',commit+':'+name],cwd=ROOT)
def verify(raw):
 manifest=json.loads(blob(AUTHOR,PREFIX+'actual-once-sha256.json'))
 assert len(manifest)==10
 for relative,digest in manifest.items():
  data=(raw/relative).read_bytes()
  assert sha256(data).hexdigest()==digest
  assert data==blob(AUTHOR,PREFIX+'actual-once/'+relative)
 before=json.loads((raw/'actual/source-before.json').read_bytes());after=json.loads((raw/'actual/source-after.json').read_bytes())
 reference=json.loads(blob(APPROVED,PREFIX+'original_source266.json'))
 assert before['source_sha256']==after['source_sha256']==reference['source_sha256']
 assert len(reference['source_sha256'])==266 and reference['source_commit']==BASE
 assert all(sha256(blob(APPROVED,name)).hexdigest()==digest for name,digest in reference['source_sha256'].items())
 assert all(sha256(blob(BASE,name)).hexdigest()==digest for name,digest in reference['source_sha256'].items())
 begin=json.loads((raw/'BEGIN.json').read_bytes());end=json.loads((raw/'END.json').read_bytes())
 launch=json.loads((raw/'actual/launch.json').read_bytes());result=json.loads((raw/'actual/worker/result.json').read_bytes())
 events=[json.loads(x) for x in (raw/'actual/worker/events.jsonl').read_text().splitlines()]
 bykind={k:[e for e in events if e['kind']==k] for k in {e['kind'] for e in events}}
 def one(kind):
  assert len(bykind.get(kind,[]))==1,kind
  return bykind[kind][0]
 observed=one('case_observations')['observation']
 original_cids={str(i):f"market:3:{i}:{observed['original_snapshot_sha256'][:16]}" for i in (0,1)}
 returns=[e for e in bykind['publication_return'] if e['version']==2];assert len(returns)==1
 receipts=returns[0]['receipts']
 starts=Counter((e['thread'],e['call_id']) for e in bykind['fence_status_start'])
 finishes=Counter((e['thread'],e['call_id']) for k in ('fence_status_return','fence_status_error') for e in bykind.get(k,[]))
 spawns=Counter(e['shard'] for e in bykind['spawn_start']);spawn_returns=Counter(e['shard'] for e in bykind['spawn_return'])
 selected=observed['selected_binding']['pid'];exits=[e for e in bykind['kernel_pidfd_exit'] if e['pid']==selected]
 assert len(exits)==1
 kills=[e for e in bykind['kill_start'] if e['pid']==selected]
 assert len(kills)==1 and kills[0]['thread']=='uta-process-supervisor'
 statuses=[e for e in bykind['fence_status_return'] if e['thread']=='uta-process-supervisor' and e.get('owner_pid')==selected and e.get('active') is False and e['monotonic_ns']<kills[0]['monotonic_ns']]
 finance=observed['finance'];samples=bykind.get('parent_thread_sample',[])
 sid=launch['worker_identity']['pgid'];residual=[]
 for p in Path('/proc').iterdir():
  if p.name.isdecimal():
   try:
    text=(p/'stat').read_text();tail=text[text.rindex(')')+2:].split()
   except (FileNotFoundError,ProcessLookupError):continue
   if int(tail[2])==sid or int(tail[3])==sid:residual.append({'pid':int(p.name),'state':tail[0],'pgid':int(tail[2]),'sid':int(tail[3])})
 checks={
  'ten_original_raw_members_byte_exact':True,
  'approved_driver_hash':begin['driver_sha256']==EXPECTED_DRIVER and sha256(blob(APPROVED,PREFIX+'trace_original91.py')).hexdigest()==EXPECTED_DRIVER,
  'source266_prepost_exact_and_bound_to_both_approved_and_base_Git':True,
  'recorded_heads_approved':before['head']==after['head']==APPROVED and result['source_commit']==APPROVED,
  'one_original_case_pass_no_reproduction':result['tests_run']==1 and result['failures']==result['errors']==0 and result['case_passed'] is True and result['historical_original_assertion_reproduced'] is False,
  'cpu2':one('original_case_start')['affinity']==[2],
  'local_runtime_recorded':result['runtime']['python'].startswith('3.13.5 ') and result['runtime']['sqlite']=='3.46.1',
  'outer_under30_no_watchdog':0<end['whole_seconds']<=30 and end['whole_budget_met'] is True and end['outer_watchdog_triggered'] is False,
  'outer_native_monotonic_delta_under30':0<(end['monotonic_ns']-begin['monotonic_ns'])/1e9<=30,
  'inner_under30_no_watchdog':0<launch['wall_seconds']<=30 and launch['whole_budget_met'] is True and launch['timed_out'] is False,
  'recorded_modes_private':begin['outer_mode']==end['actual_mode']==end['worker_output_mode']=='0o700',
  'raw_modes_current_private':all((raw/p).stat().st_mode&0o777==0o700 for p in ('','actual','actual/worker')),
  'trace_physical_hash':sha256((raw/'actual/worker/events.jsonl').read_bytes()).hexdigest()==result['trace_sha256'],
  'original_status323_all_once_finished':starts==finishes and sum(starts.values())==323 and all(v==1 for v in starts.values()),
  'original_status_no_error':not bykind.get('fence_status_error'),
  'no_logger_sampling_observation_error':result['logger_failures']==[] and not bykind.get('sampling_unavailable') and not bykind.get('observation_unavailable'),
  'no_printed_observer_exception':'Exception in thread' not in (raw/'actual/unittest.txt').read_text(),
  'fourteen_samples_monitor_and_both_workers':len(samples)==14 and any(s['supervisor_alive'] is True and s['supervisor_stop'] is False and len(s['workers'])==2 for s in samples),
  'all_events_three_native_clock_integers':all(type(e[k]) is int for e in events for k in ('monotonic_ns','boottime_ns','utc_ns')),
  'three_spawn_starts_returns_balanced':spawns==spawn_returns and sum(spawns.values())==3,
  'all_three_owned_children_final_pidfd_exit':len(bykind['final_owned_child'])==3 and all(e['pidfd_exited'] is True and e['identity'].get('present') is False for e in bykind['final_owned_child']),
  'no_forced_cleanup_or_fixture_errors':observed['cleanup_forced_kill'] is False and observed['cleanup_errors']==[] and all(c['forced_cleanup'] is False for c in launch['owned_children']),
  'current_own_PGID_SID_empty':not residual,
  'real_retained_SH_and_zeroDML':any(c['candidate'] and c['retained_after_stop'] and c['writer_availability_probe']['classification']=='begin_immediate_rolled_back_zero_dml' and c['writer_availability_probe']['available'] is True for c in observed['capture_attempts']),
  'unexpired_control_and_actual_entry':observed['unexpired_control_lease']['active'] is True and observed['publication_thread_entry_lease']['active'] is True,
  'actual_supervisor_expired_lease_before_kill':bool(statuses) and statuses[-1]['expires_ns']<=statuses[-1]['now_ns'],
  'original_recovery_milestones_all_under5':all(0<=observed[k]-observed['publication_started_at']<=5 for k in ('old_pidfd_exit_observed_at','publication_first_ex_entered_at','new_generation_observed_at')),
  'separate_publication_lifecycle_under15':0<=observed['publication_finished_at']-observed['publication_started_at']<=15,
  'publisher_errors_empty':one('original_thread_end')['captured_errors']==[] and all(not errors for errors in one('publisher_captured_errors')['errors'].values()),
  'original_actual_two_CIDs_SUCCEEDED':set(receipts)=={'0','1'} and all(receipts[k]['command_id']==v and receipts[k]['state']=='SUCCEEDED' for k,v in original_cids.items()),
  'original_financial_assertions_reached':finance['orders']==finance['accepted_events']==0 and finance['ledger_and_debt_unchanged'] is True,
 }
 assert all(v is True for v in checks.values()),checks
 timings={
  'capture_to_parent_pidfd_observation_seconds':observed['old_pidfd_exit_observed_at']-observed['captured_at'],
  'publication_start_to_parent_pidfd_observation_seconds':observed['old_pidfd_exit_observed_at']-observed['publication_started_at'],
  'capture_to_independent_watcher_pidfd_observation_seconds':exits[0]['monotonic_ns']/1e9-observed['captured_at'],
  'publication_start_to_parent_EX_observation_seconds':observed['publication_first_ex_entered_at']-observed['publication_started_at'],
  'publication_start_to_new_native_generation_observation_seconds':observed['new_generation_observed_at']-observed['publication_started_at'],
  'publication_start_to_publication_finish_seconds':observed['publication_finished_at']-observed['publication_started_at'],
 }
 return {'checked_at':datetime.now(timezone.utc).isoformat(),'author_evidence_commit':AUTHOR,'checks':checks,'observed_checks_passed':True,'event_count':len(events),'timings':timings,'old_pid':selected,'own_sid':sid,'current_matching_PGID_SID':residual,'observer_post_join_is_alive':'NOT_RECORDED; process exit does not establish join completion','strict_observation_component_complete':False,'strict_gate':'NO_GO/incomplete','original_case_outcome':'PASS; NO_REPRO','historical_failure_cause':'UNPROVEN','native_or_SQL_rerun':False,'production_approved':False}
if __name__=='__main__':
 print(json.dumps(verify(Path(sys.argv[1])),indent=2,sort_keys=True))
