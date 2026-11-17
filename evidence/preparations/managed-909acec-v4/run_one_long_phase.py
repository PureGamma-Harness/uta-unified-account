"""One explicitly root-approved long admission phase; no automatic next phase.

Code-only preparation. Live execution needs an external exact root record. The
reviewed E88 owned child persists bounded private pipes; frozen source is unchanged.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import time

SOURCE = '909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0'
FROZEN = Path('/workspace/uta-credit-v2-py310-candidate')
E88_SHA = 'e88a575ef31f12d60f1c42bfdc86e003b013620488b5ac9b4685a1a1a5a445b3'
CAP_SHA = '57e87ce1bd10863821cbd0392957515da3b4613b2c756c1c986c947217654aa6'
GUARD_SHA = 'f31cca779de58db8fedfd31c5f48069483cffa67c803aea6327ee73fcf930602'
PHASES = ('long-preflight', 'long-start')
FLAGS = ('continuous_6h_stability_passed', 'continuous_24h_stability_passed',
         'capacity_10000_per_s_passed', 'production_approved')


def need(ok, code):
    if not ok: raise ValueError(code)


SAFE_CODES = {'original_metadata_or_effective_heartbeat_stale', 'fresh_combined_free_floor_unavailable',
              'observer_latest_alert_or_unknown', 'observer_inventory_entry_budget_exceeded',
              'no_fresh_old_observer_window', 'private_pipe_capture_failed', 'single_phase_timeout_UNKNOWN'}


def error_fields(error):
    code = str(error) if type(error) is ValueError and str(error) in SAFE_CODES else None
    return {'error_type':type(error).__name__, 'error_digest':digest(str(error).encode()), 'error_code':code}


def digest(raw): return sha256(raw).hexdigest()


def encoded(value): return (json.dumps(value, sort_keys=True, indent=2)+'\n').encode()


def command_hash(argv): return digest(json.dumps(argv, separators=(',', ':')).encode())


def verified(path, expected, name):
    from types import ModuleType
    raw = Path(path).read_bytes()
    need(digest(raw) == expected, 'fixed_code_hash_changed')
    module = ModuleType(name); module.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def approval(spec_raw, profile_raw, runner_raw, root_raw, expected_root_sha, *, wall, boot, boot_id):
    need(digest(root_raw) == expected_root_sha, 'external_root_record_hash_changed')
    spec, profile, root = (json.loads(raw) for raw in (spec_raw, profile_raw, root_raw))
    need(root.get('authorized') is True and root.get('scope') == 'ONE_EXACT_LONG_PHASE_NO_NEXT_PHASE', 'specific_root_phase_GO_missing')
    need(spec['phase'] in PHASES and root.get('phase') == spec['phase'], 'one_long_phase_required')
    for key, raw in (('spec_sha256',spec_raw), ('profile_sha256',profile_raw), ('runner_sha256',runner_raw)):
        need(root.get(key) == digest(raw), 'root_exact_hash_binding_changed')
    need(spec['runner_sha256'] == digest(runner_raw) and spec['profile_sha256'] == digest(profile_raw), 'spec_code_profile_binding_changed')
    need(spec['source_commit'] == profile['source_commit'] == root.get('source_commit') == SOURCE
         and profile['source_root'] == str(FROZEN), 'exact_source_required')
    argv = spec['argv']
    expected = [profile['python'],'-B',str(FROZEN/'tools/prepare_managed_stability.py'),
        '--profile',spec['profile_file'],'--invoke',spec['phase'],'--root-go-profile-sha256',digest(profile_raw)]
    need(argv == expected and command_hash(argv) == spec['command_sha256'] == root.get('command_sha256'), 'exact_wrapper_command_changed')
    need(spec['wait_fresh_window_seconds'] == 75 and spec['phase_timeout_seconds'] == 75, 'single_phase_bounds_changed')
    need(root.get('private_output') == spec['private_output'] and root.get('long_scratch') == profile['long_scratch'], 'new_owned_paths_changed')
    need(root.get('source_boot') == boot_id, 'root_GO_boot_changed')
    iw, ib, ew, eb = (root.get(k) for k in ('issued_wall_ns','issued_boottime_ns','valid_until_wall_ns','valid_until_boottime_ns'))
    need(all(type(x) is int and x>0 for x in (iw,ib,ew,eb,wall,boot)) and iw<=wall<ew and ib<=boot<eb
         and 0<ew-iw<=180*10**9 and 0<eb-ib<=180*10**9, 'root_GO_expired_or_clock_rolled_back')
    need(profile['qualification']['status'] == 'COMPLETE_ALL_GATES_PASSED'
         and all(profile['qualification'].get(k) is True for k in ('all_three_local_passed','all_eight_ci_passed','independent_new_package_passed'))
         and profile['resource_review'].get('old_observer_floor_approved') is True, 'static_source_or_floor_policy_incomplete')
    return spec, profile, root


def verify_receipt(phase, value, spec, profile):
    """prepare outer exit is checked by Child; target stdout is direct, not captured()."""
    need(type(value) is dict and type(value.get('exit_code')) is int and value['exit_code'] == 0
         and value.get('stdout_complete') is True and value.get('phase') == phase
         and value.get('timed_out', False) is False, 'prepare_receipt_failed_or_timeout')
    body = value.get('structured_stdout')
    need(type(body) is dict and 'exit_code' not in body and 'timed_out' not in body,
         'frozen_long_direct_stdout_schema_required')
    flag_keys = ('financial_6h_passed','live_coverage_passed','capacity_10000_per_s_passed','production_approved') if phase == 'long-preflight' else FLAGS
    need(all(body.get(k) is False for k in flag_keys), 'future_flags_not_false')
    if phase == 'long-preflight':
        need(body.get('status') == 'PREFLIGHT_ONLY_NOT_STARTED' and body.get('service_started') is False
             and body.get('producer_source_commit') == body.get('observer_freeze_commit') == SOURCE
             and body.get('base_plan_sha256') == profile['plan_sha256']
             and body.get('amendment_sha256') == profile['amendment_sha256']
             and body.get('qualification',{}).get('code_commit') == SOURCE
             and body['qualification'].get('tests_run') == profile['qualification']['actual_executed_tests_each'],
             'actual_preflight_contract_not_met')
        return {'status':body['status'],'service_started':False,'financial_6h_passed':False}
    need(phase == 'long-start' and body.get('status') == 'SUPERVISOR_STARTED_PENDING_ACTUAL_DRIVER'
         and body.get('scratch') == profile['long_scratch']
         and type(body.get('supervisor_pid')) is int and body['supervisor_pid']>0 and body['supervisor_pid'] not in {4471,8784}
         and type(body.get('supervisor_birth')) is str and body['supervisor_birth'].isdecimal()
         and int(body['supervisor_birth'])>0, 'actual_start_supervisor_receipt_not_met')
    return {k:body[k] for k in ('status','supervisor_pid','supervisor_birth','scratch','actual_driver_identity_file')}


def execute(spec, profile, io):
    """One captured phase, including raw closure/hash and final clock; fake IO is pure."""
    result = {'phase':spec['phase'],'status':'NOT_RUN','next_phase_authorized':False,'financial_6h_passed':False,
              'live_coverage_passed':False,'production_approved':False,'repeat_start_allowed':False}
    try:
        io.wait_window()
        admission = io.admit()
        child = io.spawn(admission)
        value = io.finish(child)
        result['response'] = verify_receipt(spec['phase'],value,spec,profile)
        endpoint = io.post_hash_clock()  # After closed/fsynced raw streams and actual hashes.
        result.update(status='PHASE_RECEIPT_VERIFIED',post_hash_clock=endpoint)
    except BaseException as error:
        result.update(status='UNKNOWN_NO_GO_DO_NOT_REPEAT', **error_fields(error),
                      started_job_may_still_run=spec['phase']=='long-start')
        try: io.stop_owned_wrapper()
        except BaseException as secondary: result['cleanup_secondary_error']=type(secondary).__name__
    finally:
        try: io.close()
        except BaseException as secondary:
            result['close_secondary_error']=type(secondary).__name__;result['status']='UNKNOWN_NO_GO_DO_NOT_REPEAT'
    return result


class Live:
    def __init__(self,spec,profile,root,root_sha):
        sys.dont_write_bytecode=True
        self.s,self.profile,self.root,self.root_sha=spec,profile,root,root_sha
        self.lib=verified(spec['owned_child_file'],E88_SHA,'reviewed_e88_owned_child')
        self.capture=verified(spec['capture_file'],CAP_SHA,'fixed57_capture')
        self.guard=verified(spec['guard_file'],GUARD_SHA,'fixedf31_guard')
        self.base=Path(spec['private_output']);need(not self.base.exists(),'new_private_phase_output_required')
        need(not Path(profile['long_scratch']).exists(),'new_long_job_required_no_resume')
        self.base.mkdir(mode=0o700)
        self.children=[];self.first=None;self.deadline=None
        self.boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()

    def save(self,name,value):
        path=self.base/name
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as stream:stream.write(encoded(value));stream.flush();os.fsync(stream.fileno())
        return path

    def clock(self):return {'wall_ns':time.time_ns(),'boottime_ns':time.clock_gettime_ns(time.CLOCK_BOOTTIME)}

    def budget(self):
        c=self.clock()
        need(self.root['issued_wall_ns']<=c['wall_ns']<self.root['valid_until_wall_ns']
             and self.root['issued_boottime_ns']<=c['boottime_ns']<self.root['valid_until_boottime_ns'],'root_GO_expired_or_rollback')
        need(self.deadline is None or c['boottime_ns']<self.deadline,'single_phase_timeout_UNKNOWN')
        need(not any(x.failure.is_set() for x in self.children),'private_pipe_capture_failed')
        return c

    def identity(self,pid,expected):
        return self.lib.Live.identity(self,pid,expected)

    def wait_window(self):
        limit=time.monotonic()+75
        while True:
            self.budget()
            row=json.loads((self.capture.OBSERVER/'latest.json').read_bytes())
            age=(time.time_ns()-row['observed_ns'])/1e9
            if 0<=age<=2:return
            need(time.monotonic()<limit,'no_fresh_old_observer_window')
            time.sleep(.025)

    def admit(self):
        self.budget();stamp=str(time.time_ns())
        try:row=self.capture.capture(self.s['profile_sha256'],self.s['phase'],self.s['command_sha256'])
        except BaseException as error:
            self.save(stamp+'-admission-UNKNOWN.json',{'status':'UNKNOWN_OR_NO_GO','phase':self.s['phase'],'profile_sha256':self.s['profile_sha256'],'command_sha256':self.s['command_sha256'],**self.clock(),**error_fields(error)});raise
        snapshot=self.save(stamp+'-admission.json',row)
        go={'authorized':True,'phase':self.s['phase'],'profile_sha256':self.s['profile_sha256'],
            'command_sha256':self.s['command_sha256'],'snapshot_sha256':digest(snapshot.read_bytes()),
            'root_phase_delegation_record_sha256':self.root_sha,'root_approved_spec_sha256':self.root['spec_sha256']}
        self.guard.consume_guard(self.s['profile_file'],self.s['argv'],snapshot,go,
            now_wall_ns=time.time_ns(),now_boottime_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME),current_boot=self.boot)
        self.save(stamp+'-root-delegated-phaseGO.json',go)
        return snapshot,go

    def spawn(self,admission):
        self.budget();snapshot,go=admission
        self.guard.consume_guard(self.s['profile_file'],self.s['argv'],snapshot,go,
            now_wall_ns=time.time_ns(),now_boottime_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME),current_boot=self.boot)
        self.first=time.clock_gettime_ns(time.CLOCK_BOOTTIME);self.deadline=self.first+75*10**9
        child=self.lib.Child(self.s['argv'],FROZEN,self.base/'actual-wrapper',self.identity,self.children.append)
        self.save('actual-Popen.json',{'identity':child.identity,'first_Popen_boottime_ns':self.first,
            'phase_deadline_boottime_ns':self.deadline,'command_sha256':self.s['command_sha256']})
        return child

    def finish(self,child):
        while not child.done():self.budget();time.sleep(.025)
        self.budget();value=child.result();self.budget()
        # Child hashed while reading; independently hash persisted, closed raw bytes.
        for row in child.streams.values():
            raw=Path(row['file']).read_bytes()
            need(len(raw)==row['bytes']==row['retained_bytes'] and digest(raw)==row['sha256'],'closed_raw_hash_mismatch')
        self.save('closed-private-stream-manifest.json',child.streams);self.budget()
        return value

    def post_hash_clock(self):
        return self.budget()

    def stop_owned_wrapper(self):
        # New, unreaped wrapper session only. A detached supervisor may already
        # exist after unknown start; never infer its birth or repeat the start.
        errors=[]
        for child in self.children:
            try:child.stop()
            except BaseException as error:errors.append(type(error).__name__)
        need(not errors,'owned_wrapper_cleanup_unknown')

    def close(self):
        errors=[]
        for child in self.children:
            try:child.close()
            except BaseException as error:errors.append(type(error).__name__)
        need(not errors,'owned_pidfd_close_unknown')


def main(argv=None):
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec',required=True,type=Path)
    parser.add_argument('--root-approved-phase-record',required=True,type=Path)
    parser.add_argument('--expected-root-record-sha256',required=True)
    args=parser.parse_args(argv)
    spec_raw=args.spec.read_bytes();spec=json.loads(spec_raw)
    root_raw=args.root_approved_phase_record.read_bytes()
    boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    spec,profile,root=approval(spec_raw,Path(spec['profile_file']).read_bytes(),Path(__file__).read_bytes(),root_raw,
        args.expected_root_record_sha256,wall=time.time_ns(),boot=time.clock_gettime_ns(time.CLOCK_BOOTTIME),boot_id=boot_id)
    io=Live(spec,profile,root,digest(root_raw));result=execute(spec,profile,io)
    try:io.save('phase-outcome.json',result)
    except BaseException as error:
        result['status']='UNKNOWN_NO_GO_DO_NOT_REPEAT';result['outcome_write_secondary_error']=type(error).__name__
    # Outcome serialization follows the explicitly recorded post-hash endpoint.
    print(json.dumps(result,sort_keys=True))
    return 0 if result['status']=='PHASE_RECEIPT_VERIFIED' else 1


if __name__=='__main__':raise SystemExit(main())
