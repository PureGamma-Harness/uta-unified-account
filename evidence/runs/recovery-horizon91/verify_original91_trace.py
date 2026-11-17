"""Read saved evidence only. Never execute a test, touch SQL, or signal a process."""
import hashlib
import json
from pathlib import Path
from collections import Counter


def verify(directory):
    root = Path(directory)
    events = [json.loads(line) for line in (root/'actual/worker/events.jsonl').read_text().splitlines()]
    launch = json.loads((root/'actual/launch.json').read_text())
    result = json.loads((root/'actual/worker/result.json').read_text())
    begin = json.loads((root/'BEGIN.json').read_text())
    end = json.loads((root/'END.json').read_text())
    post = json.loads((root/'postflight-own-session.json').read_text())
    before = json.loads((root/'actual/source-before.json').read_text())
    after = json.loads((root/'actual/source-after.json').read_text())
    kinds = Counter(event['kind'] for event in events)
    observations = [event['observation'] for event in events if event['kind']=='case_observations']
    observed = observations[0] if len(observations)==1 else {}
    starts = Counter(event['shard'] for event in events if event['kind']=='spawn_start')
    returns = Counter(event['shard'] for event in events if event['kind']=='spawn_return')
    statuses_started = {event['call_id'] for event in events if event['kind']=='fence_status_start'}
    statuses_finished = {event['call_id'] for event in events if event['kind'] in ('fence_status_return','fence_status_error')}
    samples = [event for event in events if event['kind']=='parent_thread_sample']
    publications = [event for event in events if event['kind']=='publication_return' and event['version']==2]
    publication = publications[0] if len(publications)==1 else {}
    receipt = publication.get('receipts',{})
    original_digest = observed.get('original_snapshot_sha256','')
    expected_cids = {str(shard):f'market:3:{shard}:{original_digest[:16]}' for shard in (0,1)}
    target_thread_end = [event for event in events if event['kind']=='original_thread_end']
    target_errors = [event for event in events if event['kind']=='publisher_captured_errors']
    selected = observed.get('selected_binding',{}).get('pid')
    exits = [event for event in events if event['kind']=='kernel_pidfd_exit' and event['pid']==selected]
    case_start = [event for event in events if event['kind']=='original_case_start']
    finance = observed.get('finance',{})
    checks = {
      'one_original_case_passed_no_historical_reproduction':result['tests_run']==1 and result['case_passed'] and not result['historical_original_assertion_reproduced'],
      'exact_approved_driver':begin['driver_sha256']=='81b9a0c8ee7ed45f58f38174895ad2fa4e7d3043fd6ab7c03903016d69cae2ee',
      'cpu2':len(case_start)==1 and case_start[0]['affinity']==[2],
      'whole_external_budget':end['whole_budget_met'] and end['whole_seconds']<=30 and not end['outer_watchdog_triggered'],
      'inner_budget':launch['whole_budget_met'] and launch['wall_seconds']<=30 and not launch['timed_out'],
      'private_output_modes':begin['outer_mode']=='0o700' and end['actual_mode']=='0o700' and end['worker_output_mode']=='0o700',
      'source266_unchanged':before['members']==after['members']==266 and before['all_266_match_original'] and after['all_266_match_original'] and before['source_sha256']==after['source_sha256'],
      'original_test_hash':result['test_source_sha256']=='389ab057ab0e12fc0eb73d9f990a084c82565e2cb76dd0e8ac8c2fe8325309f6',
      'event_hash':hashlib.sha256((root/'actual/worker/events.jsonl').read_bytes()).hexdigest()==result['trace_sha256'],
      'no_logger_or_sampling_unknown':not result['logger_failures'] and not kinds['sampling_unavailable'] and not kinds['observation_unavailable'],
      'no_thread_exception_printed':'Exception in thread' not in (root/'actual/unittest.txt').read_text(),
      'three_spawn_calls_balanced':sum(starts.values())==sum(returns.values())==3 and starts==returns,
      'every_original_status_has_return_or_error':statuses_started==statuses_finished and len(statuses_started)==323,
      'no_original_status_error_this_run':not kinds['fence_status_error'],
      'monitor_and_two_workers_observed':len(samples)==14 and any(s['supervisor_alive'] is True and s['supervisor_stop'] is False and len(s['workers'])==2 for s in samples),
      'three_clocks_all_events':all(all(isinstance(event.get(k),int) for k in ('monotonic_ns','boottime_ns','utc_ns')) for event in events),
      'exact_bound_old_pid_kernel_exit':len(exits)==1 and exits[0]['pid']==selected,
      'all_tracked_own_children_pidfd_exited':kinds['final_owned_child']==3 and all(e['pidfd_exited'] for e in events if e['kind']=='final_owned_child'),
      'all_own_sid_and_pgid_empty':post['new_worker_sid']==launch['worker_identity']['pgid'] and post['no_residual'] and post['residual_matching_sid_or_pgid']==[],
      'no_forced_or_fixture_cleanup_error':not observed.get('cleanup_forced_kill',True) and observed.get('cleanup_errors')==[] and all(not c['forced_cleanup'] for c in launch['owned_children']),
      'native_SH_and_real_zero_DML_probe':any(c['candidate'] and c['retained_after_stop'] and c['writer_availability_probe']['available'] is True for c in observed.get('capture_attempts',[])),
      'original_unexpired_control_and_entry':observed.get('unexpired_control_lease',{}).get('active') is True and observed.get('publication_thread_entry_lease',{}).get('active') is True,
      'five_second_recovery_milestones':all(0<=observed[key]-observed['publication_started_at']<=5 for key in ('old_pidfd_exit_observed_at','publication_first_ex_entered_at','new_generation_observed_at')),
      'fifteen_second_publication_lifecycle':0<=observed['publication_finished_at']-observed['publication_started_at']<=15,
      'publisher_original_errors_empty':len(target_thread_end)==1 and target_thread_end[0]['captured_errors']==[] and len(target_errors)==1 and all(v==[] for v in target_errors[0]['errors'].values()),
      'original_two_actual_CIDs_SUCCEEDED':set(receipt)=={'0','1'} and all(receipt[s]['command_id']==expected_cids[s] and receipt[s]['state']=='SUCCEEDED' for s in ('0','1')),
      'original_financial_assertions_reached_and_conserved':finance.get('orders')==0 and finance.get('accepted_events')==0 and finance.get('ledger_and_debt_unchanged') is True,
    }
    times = {name:observed[key]-observed['publication_started_at'] for name,key in (
        ('publication_start_to_old_exit_seconds','old_pidfd_exit_observed_at'),
        ('publication_start_to_EX_seconds','publication_first_ex_entered_at'),
        ('publication_start_to_new_generation_seconds','new_generation_observed_at'),
        ('publication_start_to_finish_seconds','publication_finished_at'))}
    times.update({'capture_to_old_exit_seconds':observed['old_pidfd_exit_observed_at']-observed['captured_at'],
                  'capture_to_publication_finish_seconds':observed['publication_finished_at']-observed['captured_at']})
    return {'classification':'NO_REPRO; original single testcase PASS',
            'observed_checks':checks,'all_observed_checks':all(checks.values()),
            'observer_join_positive_evidence':'UNKNOWN: source calls both join(1), but did not record post-join is_alive; worker and full SID are now gone',
            'strict_observation_component_complete':False,
            'strict_component_gate':'NO_GO for missing explicit observer-thread post-join observation; no rerun',
            'historical_CI_failure_root_cause':'UNPROVEN',
            'timings':times,'actual_receipts':receipt,'event_count':len(events),
            'runtime_mismatch':'CI Python3.13.18 versus local3.13.5; both SQLite3.46.1',
            'source91_release_qualified':False,'production_approved':False}


if __name__=='__main__':
    import sys
    print(json.dumps(verify(Path(sys.argv[1])),indent=2,sort_keys=True))
