"""Independent saved ABBA16 file/source/proc inspection. No SQL, signals or replay."""
from collections import Counter
from datetime import datetime,timezone
from hashlib import sha256
import json,os
from pathlib import Path
import subprocess,sys,time

ROOT=Path(__file__).resolve().parents[3];SOURCE='80fae18c7afafdbb0145e5e8b44741323994b74f';PREFIX='evidence/runs/recovery-horizon91/'
CONTROLLER='5ce9884cfd39238482c0282cf357aab52497b7fbacb395505eecb97f67eec15e';PREREG='e5b67407cc1ddec6e2b85bd96037649f8803d0e714b99ff15a95f867e717b13e'
def blob(name):return subprocess.check_output(['git','show',SOURCE+':'+name],cwd=ROOT)
def read(path):return json.loads(path.read_bytes())
def digest(path):
 h=sha256()
 with path.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def exactly_true(items):return type(items) is dict and bool(items) and all(type(v) is bool and v is True for v in items.values())
def verify(raw,outer):
 started=time.monotonic();os.sched_setaffinity(0,{3})
 cfgraw=blob(PREFIX+'runtime-ab16-final-preregistration.json');assert sha256(cfgraw).hexdigest()==PREREG
 config=json.loads(cfgraw);order=[{'id':f's{i:02d}-{r}','runtime':r} for i,r in enumerate('ABBA'*4,1)];assert config['sample_order']==order
 assert sha256(blob(PREFIX+'run_runtime_ab16_final.py')).hexdigest()==CONTROLLER
 assert all(sha256(blob(PREFIX+n)).hexdigest()==d for n,d in config['files'].items())
 expected=read(raw/'batch-BEGIN.json');assert expected['prereg_sha256']==PREREG and expected['controller_sha256']==CONTROLLER and expected['preregistration']==config
 source=json.loads(blob(PREFIX+'original_source266.json'))['source_sha256'];assert len(source)==266
 assert all(sha256(blob(n)).hexdigest()==d for n,d in source.items())
 begin,end=read(outer/'RUN-BEGIN.json'),read(outer/'RUN-END.json')
 assert begin['source_head']==end['source_head_after']==SOURCE and begin['controller_sha256']==CONTROLLER and begin['prereg_sha256']==PREREG
 assert end['controller_exit_code']==0 and 0<end['whole_seconds']<480
 assert 0<(end['monotonic_ns']-begin['monotonic_ns'])/1e9<480
 batch=read(raw/'batch-END.json');assert batch['planned']==batch['attempted']==16 and batch['safety_stop'] is None and batch['diagnostic_batch_complete'] is True and batch['source91_qualified'] is False
 assert len(batch['samples'])==16
 rows=[];sessions=set();native_errors=[];raw_hashes={};all_cids=[]
 for index,slot in enumerate(order):
  folder=raw/slot['id'];binding=config['runtimes'][slot['runtime']]
  sb,se=read(folder/'BEGIN.json'),read(folder/'END.json');so=read(raw/(slot['id']+'-OUTER-END.json'))
  probe=read(folder/'probe.stdout');post=read(folder/'runtime-files-post.json')
  launch=read(folder/'attempt/launch.json');worker=read(folder/'attempt/worker/result.json')
  before,after=(read(folder/'attempt'/name) for name in ('source-before.json','source-after.json'))
  assert sb['slot']==se['slot']==so['slot']==slot
  assert sb['code_sha256']==config['files'] and sb['controller_sha256']==CONTROLLER and sb['prereg_sha256']==PREREG
  assert exactly_true(se['checks']) and se['all_checks'] is True and se['technical_errors']==se['forced_cleanup']==[]
  assert type(se['whole_seconds']) is float and 0<se['whole_seconds']<=30
  assert so['all_checks'] is True and so['whole_budget_met'] is True and 0<so['whole_start_to_sample_return_seconds']<=30
  assert so['original_sample_result']==se and so['original_sample_END_sha256']==digest(folder/'END.json')
  saved=batch['samples'][index];assert saved['slot']==slot and saved['original_sample_result']==se and saved['all_checks'] is True and saved['outer_whole_budget_met'] is True
  assert read(raw/f'batch-status-{index+1:02d}.json')['samples']==batch['samples'][:index+1]
  for runtime in (probe,worker['runtime']):
   assert runtime['version_info']==binding['version_info'] and all(type(v) is int for v in runtime['version_info'])
   assert runtime['python'].split(' ',1)[0]=='.'.join(map(str,binding['version_info']))
   assert runtime['executable']==str(Path(binding['executable']).resolve()) and runtime['sqlite']==binding['sqlite']
   assert runtime['environment']==binding['environment'] and runtime['mapped_libpython']==binding['mapped_libpython_expected']
   assert runtime['affinity']==[2] and type(runtime['optimize']) is int and runtime['optimize']==0 and runtime['dont_write_bytecode'] is True
  assert probe['bound_files']==post==binding['files']
  assert probe['source_sha256']==before['source_sha256']==after['source_sha256']==source
  assert probe['source_members']==before['members']==after['members']==266 and before['head']==after['head']==SOURCE
  assert probe['source_matches_original'] is before['all_266_match_original'] is after['all_266_match_original'] is True
  assert worker['tests_run']==1 and all(type(worker[k]) is int and worker[k]==0 for k in ('failures','errors','skipped','expected_failures','unexpected_successes'))
  assert all(worker[k] is True for k in ('case_passed','was_successful','worker_observation_complete')) and worker['test_failure_observed'] is False and worker['historical_original_assertion_reproduced'] is False
  assert worker['outcome_stage']=='PASS' and worker['production_approved'] is False and worker['logger_failures']==[]
  assert worker['source_commit']==SOURCE and worker['test_source_sha256']==source['tests/test_durable_faults.py']
  flags=worker['evidence_flags'];assert flags['both_observers_joined'] is True and flags['fixture_forced_cleanup'] is flags['fixture_cleanup_error'] is False
  assert all(flags[k]==[] for k in ('logger_failures','sampling_failures','observer_failures'))
  assert set(flags['observer_post_join'])=={'pidfd','code_stack'}
  assert all(v['is_alive'] is False and v['lifecycle']=={'started':True,'ended':True,'error':None} for v in flags['observer_post_join'].values())
  assert launch['strict_observation_complete'] is True and launch['timed_out'] is False and launch['technical_stop_required'] is False and launch['new_own_session_members']==[]
  assert all(v is None for k,v in launch.items() if k in ('source_error','worker_result_error','session_scan_error','event_read_error'))
  assert all(c['forced_cleanup'] is False for c in launch['owned_children'])
  assert 0<launch['wall_seconds']<=30 and launch['exit_code']==0
  event_path=folder/'attempt/worker/events.jsonl';assert digest(event_path)==worker['trace_sha256']
  events=[json.loads(line) for line in event_path.read_text().splitlines()]
  kinds=Counter(e['kind'] for e in events)
  for event in events:assert all(type(event[k]) is int for k in ('monotonic_ns','boottime_ns','utc_ns'))
  assert not any(kinds[k] for k in ('observer_lifecycle_error','sampling_unavailable','observation_unavailable','pidfd_open_unavailable'))
  starts=[e for e in events if e['kind']=='original_case_start'];assert len(starts)==1 and starts[0]['runtime']==worker['runtime'] and starts[0]['affinity']==[2]
  assert worker['runtime']['mapped_libpython_sha256']=={p:binding['files']['libpython']['sha256'] for p in binding['mapped_libpython_expected']}
  for name in ('pidfd','code_stack'):
   beginnings=[e for e in events if e['kind']=='observer_lifecycle_start' and e['observer']==name]
   endings=[e for e in events if e['kind']=='observer_lifecycle_end' and e['observer']==name]
   joined=[e for e in events if e['kind']=='observer_post_join' and e['observer']==name]
   assert len(beginnings)==len(endings)==len(joined)==1
   assert joined[0]['is_alive'] is False and joined[0]['lifecycle']==flags['observer_post_join'][name]['lifecycle']
   assert beginnings[0]['monotonic_ns']<=endings[0]['monotonic_ns']<=joined[0]['monotonic_ns']
  status_open=Counter((e['thread'],e['call_id']) for e in events if e['kind']=='fence_status_start')
  status_done=Counter((e['thread'],e['call_id']) for e in events if e['kind'] in ('fence_status_return','fence_status_error'))
  assert status_open==status_done and all(v==1 for v in status_open.values())
  status_errors=[e for e in events if e['kind']=='fence_status_error'];native_errors.extend({'slot':slot['id'],'event':e} for e in status_errors)
  spawns=[e for e in events if e['kind']=='spawn_return'];assert len(spawns)>=2
  assert Counter(e['shard'] for e in spawns)==Counter(e['shard'] for e in events if e['kind']=='spawn_start')
  pids={e['identity']['pid'] for e in spawns};assert len(pids)==len(spawns)
  finals=[e for e in events if e['kind']=='final_owned_child'];assert {e['pid'] for e in finals}==pids
  assert all(e['pidfd_exited'] is True and e['identity'].get('present') is False for e in finals)
  latest=None;kills=[]
  for e in events:
   if e['kind'] in ('fence_status_return','fence_status_error') and e['thread']=='uta-process-supervisor':latest=e if e['kind']=='fence_status_return' else None
   if e['kind']=='kill_start':
    assert e['thread']=='uta-process-supervisor' and e['pid'] in pids
    assert latest is not None and latest['owner_pid']==e['pid'] and latest['active'] is False and latest['expires_ns']<=latest['now_ns']
    kills.append(e)
  assert Counter((e['thread'],e['pid']) for e in kills)==Counter((e['thread'],e['pid']) for e in events if e['kind']=='kill_return')
  observations=[e['observation'] for e in events if e['kind']=='case_observations'];assert len(observations)==1;obs=observations[0]
  assert all(obs[k]==v for k,v in {'fixture_lease_seconds':5,'capture_horizon_seconds':5,'recovery_horizon_seconds':5,'api_phase_timeout_seconds':5,'publication_lifecycle_watchdog_seconds':15}.items())
  assert obs['cleanup_forced_kill'] is False and obs['cleanup_errors']==[]
  assert obs['finance']['ledger_and_debt_unchanged'] is True and all(type(obs['finance'][k]) is int and obs['finance'][k] in (0,1) for k in ('orders','accepted_events'))
  assert obs['publication_thread_entry_lease']['active'] is True and obs['unexpired_control_lease']['active'] is True
  assert any(c['candidate'] and c['retained_after_stop'] and c['writer_availability_probe']['available'] is True and c['writer_availability_probe']['classification']=='begin_immediate_rolled_back_zero_dml' for c in obs['capture_attempts'])
  timings={k:obs[n]-obs['publication_started_at'] for k,n in [('publication_start_to_old_pidfd_observation','old_pidfd_exit_observed_at'),('publication_start_to_EX','publication_first_ex_entered_at'),('publication_start_to_new_generation','new_generation_observed_at'),('publication_start_to_finish','publication_finished_at')]}
  assert all(0<=v<=5 for k,v in timings.items() if k!='publication_start_to_finish') and 0<=timings['publication_start_to_finish']<=15
  timings['capture_to_old_pidfd_observation']=obs['old_pidfd_exit_observed_at']-obs['captured_at']
  pubs=[e for e in events if e['kind']=='publication_return' and e['version']==2];assert len(pubs)==1 and set(pubs[0]['receipts'])=={'0','1'}
  for shard,receipt in pubs[0]['receipts'].items():
   cid=f"market:3:{shard}:{obs['original_snapshot_sha256'][:16]}";assert receipt['command_id']==cid and receipt['state']=='SUCCEEDED' and type(receipt['sequence']) is int
   all_cids.append(cid)
  assert [e for e in events if e['kind']=='original_thread_end'][0]['captured_errors']==[]
  assert all(errors==[] for e in events if e['kind']=='publisher_captured_errors' for errors in e['errors'].values())
  log=(folder/'attempt/unittest.txt').read_text();assert '\nRan 1 test in ' in log and log.endswith('\nOK\n') and 'Exception in thread' not in log
  for session,members in se['final_sessions'].items():assert members==[];sessions.add(int(session))
  for p in folder.rglob('*'):
   if p.is_file():raw_hashes[str(p.relative_to(raw))]={'bytes':p.stat().st_size,'sha256':digest(p)}
  raw_hashes[slot['id']+'-OUTER-END.json']={'bytes':(raw/(slot['id']+'-OUTER-END.json')).stat().st_size,'sha256':digest(raw/(slot['id']+'-OUTER-END.json'))}
  rows.append({'slot':slot,'runtime':worker['runtime']['python'],'event_count':len(events),'native_status_calls':sum(status_open.values()),'native_status_errors':len(status_errors),'spawned_children':len(spawns),'supervisor_expiry_kills':len(kills),'sample_seconds':se['whole_seconds'],'sample_return_seconds':so['whole_start_to_sample_return_seconds'],'timings':timings,'classification':'NO_REPRO','recorded_technical_gates_complete':True})
 assert len(set(all_cids))==32
 residual=[]
 for p in Path('/proc').iterdir():
  if p.name.isdecimal():
   try:
    text=(p/'stat').read_text();tail=text[text.rindex(')')+2:].split()
   except (FileNotFoundError,ProcessLookupError):continue
   if int(tail[2]) in sessions or int(tail[3]) in sessions:residual.append({'pid':int(p.name),'pgid':int(tail[2]),'sid':int(tail[3]),'state':tail[0]})
 assert residual==[]
 assert read(outer/'postflight-source-session.json')['source266_hashes']==source
 runtime_live={label:{name:digest(Path(item['path'])) for name,item in binding['files'].items()} for label,binding in config['runtimes'].items()}
 assert all(runtime_live[label][name]==item['sha256'] for label,binding in config['runtimes'].items() for name,item in binding['files'].items())
 return {'checked_at':datetime.now(timezone.utc).isoformat(),'source':SOURCE,'controller_sha256':CONTROLLER,'prereg_sha256':PREREG,'fixed_samples':16,'runtime_counts':dict(Counter(r['slot']['runtime'] for r in rows)),'all_recorded_gates_and_independent_checks_passed':True,'whole_batch_seconds':end['whole_seconds'],'samples':rows,'native_status_error_count':len(native_errors),'native_status_error_events':native_errors,'new_session_count':len(sessions),'current_matching_sessions':residual,'raw_file_hashes':raw_hashes,'unique_original_publication_CIDs':32,'financial_proof_scope':'original fixed test conservation assertions reached; no independent SQL reopen or replay','interpretation':'16 NO_REPRO; original CI failure and cause unresolved; no runtime fix established','next_candidate_recommendation':'May continue as diagnostic-only fresh full QA/CI/package and separately authorized synthetic observation; unresolved five-second CI failure remains a release blocker','inspection_seconds':time.monotonic()-started,'SQL_or_native_replay_executed':False,'source91_qualified':False,'production_approved':False}
if __name__=='__main__':print(json.dumps(verify(Path(sys.argv[1]),Path(sys.argv[2])),indent=2,sort_keys=True))
