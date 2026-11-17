"""Explicit future ABBA16 diagnostic controller. No default execution."""
import hashlib,json,math,os,re,select,signal,subprocess,sys,time
from pathlib import Path
from datetime import datetime,timezone
from strict_result_contract import validate_worker_result,ORIGINAL_ASSERTION
from strict_runtime_contract import validate_case_runtime
from strict_event_contract import validate_events
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
CONFIG=HERE/'runtime-ab16-bound-preregistration.json'


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write_new(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n') if not Path(path).exists() else (_ for _ in ()).throw(FileExistsError(str(path)))
def utc():return datetime.now(timezone.utc).isoformat()
def read_json(path):return json.loads(Path(path).read_text())
def birth(pid):
    try:
        path=Path('/proc',str(pid));raw=(path/'stat').read_text();tail=raw[raw.rindex(')')+2:].split()
        return {'pid':pid,'start_ticks':tail[19],'uid':path.stat().st_uid,
            'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            'pgid':int(tail[2]),'sid':int(tail[3]),'state':tail[0]}
    except (FileNotFoundError,ProcessLookupError):return {'pid':pid,'present':False}

def same(a,b):return all(a.get(k)==b.get(k) for k in ('pid','start_ticks','uid','boot_id')) and a.get('start_ticks') is not None

def scan_session(sid):
    found=[]
    for path in Path('/proc').iterdir():
        if path.name.isdigit():
            current=birth(int(path.name))
            if current.get('pgid')==sid or current.get('sid')==sid:found.append(current)
    return found

def kill_exact(identity):
    current=birth(identity['pid'])
    if not same(identity,current):return {'identity':identity,'signal_sent':False,'current':current}
    fd=os.pidfd_open(identity['pid'])
    try:
        again=birth(identity['pid'])
        if not same(identity,again):return {'identity':identity,'signal_sent':False,'current':again}
        signal.pidfd_send_signal(fd,signal.SIGKILL)
        return {'identity':identity,'signal_sent':True}
    finally:os.close(fd)

def runtime_environment(binding):
    env=os.environ.copy()
    for key,value in binding['environment'].items():
        if value is None:env.pop(key,None)
        else:env[key]=value
    return env

def probe_checks(probe,binding,expected_sources):
    return {
      'version':probe.get('version_info')==binding['version_info'],
      'sqlite':probe.get('sqlite')==binding['sqlite'],
      'executable':probe.get('executable')==str(Path(binding['executable']).resolve()),
      'environment':probe.get('environment')==binding['environment'],
      'mapped_libpython':probe.get('mapped_libpython')==binding['mapped_libpython_expected'],
      'bound_binary_archive_library_hashes':probe.get('bound_files')==binding['files'],
      'source266':probe.get('source_sha256')==expected_sources and type(probe.get('source_members')) is int and probe['source_members']==266 and probe.get('source_matches_original') is True,
      'CPU2':probe.get('affinity')==[2],
      'no_optimization':type(probe.get('optimize')) is int and probe['optimize']==0,
      'no_bytecode_writes':probe.get('dont_write_bytecode') is True,
      'no_SQL_or_case':probe.get('sql_connections_created') is False and probe.get('financial_case_started') is False}

def sample(config,slot,output,expected_sources):
    started=time.monotonic();deadline=started+30
    output.mkdir(mode=0o700)
    binding=config['runtimes'][slot['runtime']];env=runtime_environment(binding)
    begin={'utc':utc(),'monotonic_ns':time.monotonic_ns(),'boottime_ns':time.clock_gettime_ns(time.CLOCK_BOOTTIME),
        'slot':slot,'environment':{k:env.get(k) for k in binding['recorded_environment']},
        'code_sha256':{name:digest(HERE/name) for name in config['files']},
        'controller_sha256':digest(__file__),'prereg_sha256':digest(CONFIG),
        'whole_budget_seconds':30,'worker_watchdog_seconds':27}
    write_new(output/'BEGIN.json',begin)
    checks={};technical=[];forced=[];process=None;worker_session=None;case_result=None;parent_identity=None
    try:
        probe_command=['taskset','-c','2',binding['executable'],'-B',str(HERE/'runtime_probe91.py'),slot['runtime'],str(CONFIG)]
        write_new(output/'probe-command.json',{'argv':probe_command,'environment':begin['environment']})
        probe=subprocess.run(probe_command,cwd=ROOT,env=env,capture_output=True,text=True,
                             timeout=min(2,max(.001,deadline-time.monotonic()-.75)))
        (output/'probe.stdout').write_text(probe.stdout);(output/'probe.stderr').write_text(probe.stderr)
        checks['probe_exit_zero']=type(probe.returncode) is int and probe.returncode==0
        checks['probe_stderr_empty']=probe.stderr==''
        capability=json.loads(probe.stdout)
        checks.update(probe_checks(capability,binding,expected_sources))
        if not all(value is True for value in checks.values()):raise ValueError('runtime/source preflight did not satisfy exact bindings')
        command=['taskset','-c','2',binding['executable'],'-B',str(HERE/'trace_original91_bound.py'),'--run',str(output/'attempt')]
        write_new(output/'case-command.json',{'argv':command,'environment':begin['environment']})
        with (output/'case-launcher.txt').open('x') as stream:
            process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
            parent_identity=birth(process.pid);pidfd=os.pidfd_open(process.pid)
            write_new(output/'case-launcher-identity.json',parent_identity)
            try:
                process.wait(timeout=max(.001,deadline-time.monotonic()-.75))
            except subprocess.TimeoutExpired:
                technical.append('outer deadline reserve reached; no later slot allowed')
                if same(parent_identity,birth(process.pid)):
                    signal.pidfd_send_signal(pidfd,signal.SIGKILL)
                    forced.append({'scope':'own launcher','identity':parent_identity,'signal_sent':True})
                process.wait(timeout=.2)
            finally:os.close(pidfd)
        attempt=output/'attempt'
        launch=read_json(attempt/'launch.json');case_result=read_json(attempt/'worker/result.json')
        contract=validate_worker_result(case_result);write_new(output/'result-contract.json',contract)
        checks['strict_worker_contract']=contract['valid'] is True and contract['safe_to_continue'] is True
        true_flags=('source_unchanged','all_266_match_original','whole_budget_met','spawn_calls_balanced',
                    'event_hash_valid','worker_observation_complete','strict_observation_complete')
        checks['launcher_exact_positive_flags']=all(launch.get(k) is True for k in true_flags)
        checks['launcher_exact_negative_flags']=launch.get('timed_out') is False and launch.get('observation_unknown') is False and launch.get('technical_stop_required') is False
        checks['launcher_no_unknown_errors']=all(launch.get(k,'MISSING') is None for k in ('source_error','worker_result_error','session_scan_error','event_read_error'))
        checks['launcher_new_session_empty']=type(launch.get('new_own_session_members')) is list and launch['new_own_session_members']==[]
        checks['launcher_exit_matches_original_case']=type(process.returncode) is int and process.returncode==(0 if case_result.get('case_passed') is True else 1)
        events_path=attempt/'worker/events.jsonl'
        checks['event_integrity']=digest(events_path)==case_result.get('trace_sha256')
        events=[json.loads(line) for line in events_path.read_text().splitlines()]
        event_contract=validate_events(events,case_result)
        write_new(output/'event-contract.json',event_contract)
        checks['original_events_semantically_complete']=event_contract['valid'] is True
        starts=[row for row in events if row.get('kind')=='original_case_start']
        checks['actual_case_result_runtime_bound']=validate_case_runtime(case_result.get('runtime'),binding) is True
        checks['actual_case_start_runtime_bound']=(len(starts)==1
            and validate_case_runtime(starts[0].get('runtime'),binding) is True
            and starts[0].get('python')==case_result.get('runtime',{}).get('python')
            and starts[0].get('affinity')==[2]
            and starts[0].get('runtime')==case_result.get('runtime'))
        unittest=(attempt/'unittest.txt').read_text()
        footer=re.search(r'\nRan 1 test in [0-9.]+s\n\n(OK|FAILED \(failures=1\)|FAILED \(errors=1\))\n',unittest)
        expected_footer='OK' if case_result.get('case_passed') is True else 'FAILED (errors=1)' if case_result.get('errors')==1 else 'FAILED (failures=1)'
        checks['actual_unittest_footer_consistent']=footer is not None and footer.group(1)==expected_footer
        checks['actual_historical_assertion_consistent']=(ORIGINAL_ASSERTION in unittest) is case_result.get('historical_original_assertion_reproduced')
        checks['no_unhandled_observer_thread_error']='Exception in thread' not in unittest
        for name in ('source-before.json','source-after.json'):
            source=read_json(attempt/name)
            checks[name+'_exact266']=source.get('source_sha256')==expected_sources and source.get('all_266_match_original') is True and type(source.get('members')) is int and source['members']==266
        # These raw files are diagnostic evidence, never new financial queries.
    except BaseException as error:
        technical.append({'type':type(error).__name__,'code':getattr(error,'code',None)})
    finally:
        # Only sessions created by this sample are inspected; all signals are
        # pidfd/birth bound and a signal always makes the sample technical NO_GO.
        sessions=[]
        if process is not None:sessions.append(process.pid)
        identity_path=output/'attempt/worker-identity.json'
        if identity_path.exists():
            try:
                identity=read_json(identity_path)
                if type(identity.get('pid')) is not int or identity.get('pgid')!=identity['pid'] or type(identity.get('start_ticks')) is not str:raise ValueError('invalid own worker binding')
                worker_session=identity['pid'];sessions.append(worker_session)
            except BaseException as error:technical.append({'phase':'worker binding','type':type(error).__name__})
        elif process is not None:technical.append('missing own worker identity; unknown cleanup; escalate to root')
        # A bare SID is observation, not enough authority to kill after leader
        # reuse. Only the bound launcher or original logged child births may be
        # signaled. Unknown unrecorded residuals are escalated, never guessed.
        bound_residuals=[]
        if parent_identity is not None:bound_residuals.append(parent_identity)
        trace_path=output/'attempt/worker/events.jsonl'
        if trace_path.exists():
            try:
                for line in trace_path.read_text().splitlines():
                    row=json.loads(line)
                    if row.get('kind')=='spawn_return':
                        original=row['identity'];current=birth(original['pid'])
                        if (current.get('start_ticks')==original.get('start_ticks')
                            and current.get('pgid')==original.get('pgid')==worker_session
                            and current.get('uid')==os.geteuid()):bound_residuals.append(current)
            except BaseException as error:technical.append({'phase':'original child binding','type':type(error).__name__})
        for session in sessions:
            try:
                members=scan_session(session)
                if members:
                    technical.append({'phase':'residual session observation','sid':session,'members':members})
                    for member in members:
                        if time.monotonic()>=deadline:break
                        if any(same(member,bound) for bound in bound_residuals):forced.append(kill_exact(member))
                        else:technical.append({'phase':'unbound residual; no signal; escalate to root','identity':member})
            except BaseException as error:technical.append({'phase':'own session scan/cleanup','type':type(error).__name__})
        # Reap only this controller's adopted descendants within remaining budget.
        while time.monotonic()<deadline:
            try:
                pid,status=os.waitpid(-1,os.WNOHANG)
            except ChildProcessError:break
            if not pid:break
        try:
            final_sessions={str(session):scan_session(session) for session in sessions}
            checks['external_all_new_sessions_empty']=all(members==[] for members in final_sessions.values())
        except BaseException as error:
            final_sessions=None;checks['external_all_new_sessions_empty']=False
            technical.append({'phase':'final session scan','type':type(error).__name__})
        checks['no_forced_cleanup']=forced==[]
        checks['whole_external_budget']=time.monotonic()-started<=30
        checks['all_code_still_bound']=all(digest(HERE/name)==expected for name,expected in config['files'].items())
        try:
            runtime_post={name:{'path':value['path'],'sha256':digest(value['path'])} for name,value in binding['files'].items()}
            write_new(output/'runtime-files-post.json',runtime_post)
            checks['runtime_provider_binary_lib_posthash_bound']=runtime_post==binding['files']
        except BaseException as error:
            checks['runtime_provider_binary_lib_posthash_bound']=False
            technical.append({'phase':'runtime files posthash','type':type(error).__name__})
        safe=technical==[] and len(checks)>=20 and all(value is True for value in checks.values())
        report={'slot':slot,'finished_at':utc(),'whole_seconds':time.monotonic()-started,
            'all_checks':bool(safe),'checks':checks,'technical_errors':technical,'forced_cleanup':forced,
            'final_sessions':final_sessions,'runtime_label':slot['runtime'],
            'case_passed':None if case_result is None else case_result.get('case_passed'),
            'outcome_stage':None if case_result is None else case_result.get('outcome_stage'),
            'status':'DIAGNOSTIC_SAMPLE_COMPLETE' if safe else 'TECHNICAL_NO_GO_STOP',
            'production_approved':False}
        write_new(output/'END.json',report)
        return report


def run(output):
    os.umask(0o077);os.sched_setaffinity(0,{2})
    import ctypes
    if ctypes.CDLL(None).prctl(36,1,0,0,0)!=0:raise RuntimeError('own descendant reaping unavailable')
    config=read_json(CONFIG)
    if config.get('sample_order') != [{'id':f's{i:02d}-{r}','runtime':r} for i,r in enumerate('ABBA'*4,1)] or config.get('ordinary_assertion_failure_policy')!='CONTINUE_FIXED_ORDER':raise ValueError('fixed preregistration mismatch')
    if not all(digest(HERE/name)==expected for name,expected in config['files'].items()):raise ValueError('code binding mismatch; no native samples')
    output.mkdir(mode=0o700,parents=True)
    write_new(output/'batch-BEGIN.json',{'started_at':utc(),'prereg_sha256':digest(CONFIG),'controller_sha256':digest(__file__),'preregistration':config,'production_approved':False})
    expected_sources=read_json(HERE/'original_source266.json')['source_sha256']
    reports=[];stop=None
    for slot in config['sample_order']:
        if stop is not None:
            reports.append({'slot':slot,'status':'NOT_RUN_DUE_TO_SAFETY_STOP','reason':stop});continue
        print(json.dumps({'starting':slot,'utc':utc()}),flush=True)
        result=sample(config,slot,output/slot['id'],expected_sources);reports.append(result)
        print(json.dumps({'finished':slot,'status':result['status'],'case_passed':result['case_passed'],'whole_seconds':result['whole_seconds']}),flush=True)
        write_new(output/f'batch-status-{len(reports):02d}.json',{'samples':reports,'production_approved':False})
        if result['all_checks'] is not True:stop='technical NO_GO after '+slot['id']
    batch={'samples':reports,'planned':16,'attempted':sum(r['status']!='NOT_RUN_DUE_TO_SAFETY_STOP' for r in reports),
        'safety_stop':stop,'diagnostic_batch_complete':stop is None,'production_approved':False,'source91_qualified':False,
        'interpretation':'Only diagnosis. All passing cases means NO_REPRO; original CI failure remains unresolved. Ordinary FAIL is retained; no retry or runtime fix authorized.'}
    write_new(output/'batch-END.json',batch)
    return 0 if stop is None else 2

if __name__=='__main__':
    if len(sys.argv)!=3 or sys.argv[1]!='--run':raise SystemExit('explicit --run NEW_PRIVATE_OUTPUT required; no default action')
    raise SystemExit(run(Path(sys.argv[2])))
