"""Read archived files only. No SQL, native test, subprocess or process signal."""
import hashlib,json,math
from pathlib import Path
from strict_result_contract import validate_worker_result
from strict_runtime_contract import validate_case_runtime
from strict_event_contract import validate_events
HERE=Path(__file__).resolve().parent

def load(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def finite_time(value):return type(value) in (int,float) and math.isfinite(value) and 0<=value<=30

def verify(root):
    config=load(HERE/'runtime-ab16-final-preregistration.json')
    manifest=load(HERE/'ab16-80fa-sha256.json')
    files={str(p.relative_to(root)):sha(p) for p in root.rglob('*') if p.is_file()}
    batch=load(root/'batch/batch-END.json');post=load(root/'outer/postflight-source-session.json')
    begin=load(root/'outer/RUN-BEGIN.json');end=load(root/'outer/RUN-END.json')
    reference=load(HERE/'original_source266.json')['source_sha256']
    all_checks={'raw_bytes_match_manifest':files==manifest['files'] and len(files)==manifest['raw_count']==327,
      'exact_authorized_controller_registration':begin['controller_sha256']=='5ce9884cfd39238482c0282cf357aab52497b7fbacb395505eecb97f67eec15e' and begin['prereg_sha256']=='e5b67407cc1ddec6e2b85bd96037649f8803d0e714b99ff15a95f867e717b13e',
      'begin_end_exact_source_head':begin['source_head']==end['source_head_after']=='80fae18c7afafdbb0145e5e8b44741323994b74f',
      'all_fixed_sixteen_attempted':type(batch['attempted']) is int and batch['attempted']==16 and [r['slot'] for r in batch['samples']]==config['sample_order'],
      'batch_no_technical_stop':batch['safety_stop'] is None and batch['diagnostic_batch_complete'] is True,
      'no_production_or_source91_qualification':batch['production_approved'] is False and batch['source91_qualified'] is False,
      'postflight_source_and_all_sessions':post['source266_exact91'] is True and post['source266_hashes']==reference and post['all_tracked_runtime_files_count']==52 and post['all_tracked_runtime_files_exact91'] is True and post['all_fresh_sessions_empty'] is True and post['residual_matching_sessions']==[] and len(post['fresh_session_ids'])==32,
      'outer_exit_private_mode':type(end['controller_exit_code']) is int and end['controller_exit_code']==0 and end['output_mode']=='0o700'}
    samples=[]
    for slot in config['sample_order']:
        folder=root/'batch'/slot['id'];binding=config['runtimes'][slot['runtime']]
        inner=load(folder/'END.json');outer=load(root/'batch'/(slot['id']+'-OUTER-END.json'))
        worker=load(folder/'attempt/worker/result.json');launch=load(folder/'attempt/launch.json')
        events=[json.loads(line) for line in (folder/'attempt/worker/events.jsonl').read_text().splitlines()]
        original_start=[r for r in events if r['kind']=='original_case_start']
        probe=json.loads((folder/'probe.stdout').read_text());pre=load(folder/'BEGIN.json')
        source_before=load(folder/'attempt/source-before.json');source_after=load(folder/'attempt/source-after.json')
        result_contract=validate_worker_result(worker);event_contract=validate_events(events,worker)
        checks={
          'strict_one_case_PASS':result_contract['valid'] is True and result_contract['safe_to_continue'] is True and worker['case_passed'] is True and worker['outcome_stage']=='PASS',
          'original_events_complete':event_contract['valid'] is True,
          'actual_case_runtime_bound':validate_case_runtime(worker['runtime'],binding) is True and len(original_start)==1 and validate_case_runtime(original_start[0]['runtime'],binding) is True and original_start[0]['runtime']==worker['runtime'],
          'preflight_actual_runtime_source':probe['version_info']==binding['version_info'] and probe['sqlite']==binding['sqlite'] and probe['executable']==binding['executable'] and probe['environment']==binding['environment'] and probe['bound_files']==binding['files'] and probe['mapped_libpython']==binding['mapped_libpython_expected'] and probe['source_sha256']==reference and probe['source_matches_original'] is True and probe['affinity']==[2],
          'source266_before_after':source_before['source_sha256']==source_after['source_sha256']==reference and source_before['all_266_match_original'] is True and source_after['all_266_match_original'] is True,
          'bound_code_and_runtime_posthash':pre['code_sha256']==config['files'] and load(folder/'runtime-files-post.json')==binding['files'],
          'both_whole_clocks':finite_time(inner['whole_seconds']) and finite_time(outer['whole_start_to_sample_return_seconds']) and outer['whole_start_to_sample_return_seconds']>=inner['whole_seconds'] and inner['checks']['whole_external_budget'] is True and outer['whole_budget_met'] is True,
          'original_END_retained':outer['original_sample_result']==inner and outer['original_sample_END_sha256']==sha(folder/'END.json'),
          'all_literal_gate_flags':inner['all_checks'] is True and outer['all_checks'] is True and all(v is True for v in inner['checks'].values()) and launch['strict_observation_complete'] is True and launch['technical_stop_required'] is False,
          'no_technical_errors_forced_or_residual':inner['technical_errors']==[] and inner['forced_cleanup']==[] and all(rows==[] for rows in inner['final_sessions'].values()) and launch['new_own_session_members']==[]}
        samples.append({'slot':slot,'checks':checks,'all_checks':all(checks.values()),
            'native_status_calls':event_contract['status_calls'],'monitor_expiry_kills':event_contract['monitor_expiry_kills'],
            'spawn_bindings':event_contract['spawn_bindings']})
    all_checks['sixteen_sample_checks']=len(samples)==16 and all(s['all_checks'] is True for s in samples)
    return {'classification':'DIAGNOSTIC NO_REPRO only','checks':all_checks,'all_checks':all(all_checks.values()),
        'samples':samples,'historical_CI_root_cause':'UNPROVEN','source91_qualified':False,'production_approved':False,
        'scope':'read-only archived metadata/event audit; not an independent database reopen or full-source/CI/capacity qualification'}

if __name__=='__main__':
    import sys
    print(json.dumps(verify(Path(sys.argv[1]) if len(sys.argv)>1 else HERE/'ab16-80fa-actual'),indent=2))
