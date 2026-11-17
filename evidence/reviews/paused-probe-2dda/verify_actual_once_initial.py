"""Read only the existing one-shot artifacts and source. Never SQL or signals."""
from datetime import datetime, timezone
import hashlib, json, subprocess
from pathlib import Path

COMMIT='2dda177fc023c023f7a7d246f03c1530e4511f9d'
ROOT=Path('/workspace/uta-shared-gate-busy-read-review')
RAW=Path('/tmp/uta-shared-gate-2dda-once')
PRE=Path('/tmp/uta-shared-gate-2dda-preflight.json')
TARGETS={'tests/test_durable_faults.py':'389ab057ab0e12fc0eb73d9f990a084c82565e2cb76dd0e8ac8c2fe8325309f6','evidence/runs/shared-gate-busy-read-8b/controlled_lease_busy.py':'0768f4bc76e808dab4eb05f2844dface420de335ed146bb2c673d75db08236e1'}
EXPECTED={'actual_busy_primary_preserved','fresh_original_owner_generation_active','expiry_not_changed_or_renewed','cleanup_performs_zero_lease_reads','unobserved_is_not_authority','exact_three_parent_native_reads','native_child_normal_exit','financial_rows_unchanged','integer_cash_oracle','no_forced_or_residual_cleanup','logger_and_cleanup_errors_absent'}
sha=lambda raw:hashlib.sha256(raw).hexdigest()
launch=json.loads((RAW/'launch.json').read_bytes());result=json.loads((RAW/'worker/result.json').read_bytes())
pre=json.loads(PRE.read_bytes());post=json.loads((RAW/'postflight.json').read_bytes())
trace_raw=(RAW/'worker/events.jsonl').read_bytes();events=[json.loads(line) for line in trace_raw.splitlines()]
checks={}
checks['exact_reviewed_source']=pre['source_commit']==post['source_commit']==result['source_commit']==COMMIT
checks['all265_source_maps_equal']=len(pre['source_before'])==265 and pre['source_before']==post['source_after']
actual_sources={};git_sources={}
for path,expected in pre['source_before'].items():
    actual_sources[path]=sha((ROOT/path).read_bytes())
    git_sources[path]=sha(subprocess.check_output(['git','show',COMMIT+':'+path],cwd=ROOT))
checks['all265_actual_bytes_and_git_blobs_match']=actual_sources==git_sources==pre['source_before']
checks['target_hashes']=all(actual_sources[p]==expected for p,expected in TARGETS.items())
checks['all52_runtime_same8b']=len([p for p in actual_sources if p.startswith('uta/')])==52 and all(sha(subprocess.check_output(['git','show','8b7f544fcbdfd540d43de1d6560022c6ebbd3799:'+p],cwd=ROOT))==h for p,h in actual_sources.items() if p.startswith('uta/'))
checks['source_clean_pre_post']=pre['source_tree_clean'] is True and post['source_tree_clean'] is True and post['source_unchanged'] is True and post['helper_unchanged'] is True
checks['cpu2_py313']=launch['command'][:3]==['taskset','-c','2'] and launch['command'][3]=='/usr/bin/python3.13' and pre['cpu']==2
checks['exact11_worker_checks_true']=set(result['checks'])==EXPECTED and all(v is True for v in result['checks'].values()) and result['component_passed'] is True
start=datetime.fromisoformat(launch['started_at']);end=datetime.fromisoformat(launch['finished_at'])
checks['actual_whole30']=0<=launch['wall_seconds']<=30 and 0<=(end-start).total_seconds()<=30 and abs((end-start).total_seconds()-launch['wall_seconds'])<.001
checks['watchdog_and_exit']=launch['exit_code']==0 and launch['timed_out'] is False and launch['watchdog_seconds']==27 and launch['whole_budget_seconds']==30
checks['trace_sha_exact']=sha(trace_raw)==result['trace_sha256']
checks['trace_monotonic']=all(a['monotonic']<=b['monotonic'] for a,b in zip(events,events[1:]))
busy=[x for x in events if x['kind']=='actual_busy']
checks['actual_native_BUSY5_trace']=len(busy)==1 and busy[0]['error_type']=='OperationalError' and type(busy[0]['native_errorcode']) is int and busy[0]['native_errorcode']==5 and busy[0]['native_errorname']=='SQLITE_BUSY'
freshs=[x for x in events if x['kind']=='fresh_native_lease'];assert len(freshs)==1
fresh=freshs[0];known=fresh['known'];current=fresh['fresh']
checks['same_owner_gen_expiry_active']=known['active'] is True and current['active'] is True and all(known[k]==current[k] for k in ['owner_pid','generation','expires_ns']) and current['now_ns']>known['now_ns'] and current['expires_ns']>current['now_ns']
checks['exact_three_native_status_phases']=fresh['status_calls']==['fresh_before_exclusive','expected_real_busy','once_fresh_after_real_release']
phases=[x for x in events if x['kind']=='child_phase']
checks['two_actual_zero_DML_barriers']=[x['phase'] for x in phases]==['owner_ready','exclusive_locked','locks_released'] and all(x['changes']==0 for x in phases[1:]) and all(x['identity']['pid']==known['owner_pid'] for x in phases)
undos=result['observations']['injection_undos']
checks['no_unobserved_financial_authority']=len(undos)==1 and undos[0]['lease_observed'] is False and undos[0]['financial_authority_granted'] is False and undos[0]['action']=='SIGCONT_undo_own_injection'
checks['no_forced_cleanup']=result['observations']['cleanup_forced_kill'] is False and result['observations']['cleanup_errors']==[] and result['logger_failures']==[] and all(x['forced_cleanup'] is False and x['current'].get('present') is False for x in launch['owned_children'])
finals=[x for x in events if x['kind']=='final_owned_child'];assert len(finals)==1
checks['normal_child_exit_and_recorded_absence']=finals[0]['exitcode']==0 and finals[0]['identity'].get('present') is False and all(x.get('present') is False for x in launch['final_owned_identities'])
pids={launch['worker_identity']['pid'],known['owner_pid']}
checks['reviewer_proc_absent']=all(not Path('/proc',str(pid)).exists() for pid in pids)
ps=subprocess.run(['ps','--sid',str(launch['worker_identity']['pid']),'-o','pid=,ppid=,pgid=,stat=,comm='],capture_output=True,text=True)
checks['reviewer_session_empty']=ps.returncode==1 and not ps.stdout.strip() and ps.stderr==''
checks['original_postflight_session_empty']=post['remaining_session']['exit_code']==1 and post['remaining_session']['rows']==[] and post['remaining_session']['stderr_empty'] is True
checks['stdout_result_byte_equal']=(RAW/'unittest.txt').read_bytes()==(RAW/'worker/result.json').read_bytes()
checks['scope_not_production']=result['production_approved'] is False and launch['production_approved'] is False and pre['production_approved'] is False and post['production_approved'] is False
paths=[PRE,RAW/'launch.json',RAW/'postflight.json',RAW/'unittest.txt',RAW/'worker/result.json',RAW/'worker/events.jsonl']
report={'verified_at':datetime.now(timezone.utc).isoformat(),'reviewed_source':COMMIT,'checks':checks,'all_passed':all(v is True for v in checks.values()),'check_count':len(checks),'raw_sha256':{str(p):sha(p.read_bytes()) for p in paths},'trace_sha256':sha(trace_raw),'whole_seconds':launch['wall_seconds'],'worker_seconds':result['duration_seconds'],'seed_cash_oracle':'Original unchanged driver performed actual SQL and asserted customer:scratch=1000,system:custody=-1000; worker integer_cash_oracle=true. This reviewer does not reopen SQLite or claim independent journal reconciliation.','native_retries':0,'reviewer_native_sql':False,'reviewer_signals':False,'production_approved':False}
print(json.dumps(report,indent=2))
assert report['all_passed']
