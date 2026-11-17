"""Seven exact smoke stages under an externally approved conditional envelope.

No execution occurs on import. Never authorizes long runs or repeats a producer.
"""
from hashlib import sha256
import importlib.util
import json
import math
import os
from pathlib import Path
import signal
import select
import subprocess
import sys
from threading import Event, Thread
import time

SOURCE = '909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0'
FROZEN = Path('/workspace/uta-credit-v2-py310-candidate')
ORDER = ('produce', 'startup', 'normal-live', 'fault-live', 'final', 'cold', 'strict-negative')
PHASES = ('smoke-produce', 'smoke-observe', 'smoke-observe', 'smoke-observe', 'smoke-observe', 'smoke-cold', 'smoke-strict-negative')
CAPTURE_SHA = '57e87ce1bd10863821cbd0392957515da3b4613b2c756c1c986c947217654aa6'
GUARD_SHA = 'f31cca779de58db8fedfd31c5f48069483cffa67c803aea6327ee73fcf930602'
PIPE_CAP = 4 * 1024**2
CLASSIFIER_SHA = '15e4f97c1d3541c2ee076e618b19ce5442f42290b3ffefd63e29985942485699'


def require(condition, code):
    if not condition:
        raise ValueError(code)


def digest(raw):
    return sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def command_hash(argv):
    return digest(json.dumps(list(argv), separators=(',', ':')).encode())


def approved(envelope_raw, root_record, controller_raw, profile_raw):
    """A root-authored external record is required; envelope cannot self-approve."""
    require(type(root_record) is dict and root_record.get('authorized') is True, 'root_envelope_GO_missing')
    envelope, profile = json.loads(envelope_raw), json.loads(profile_raw)
    for key, raw in (('envelope_sha256', envelope_raw), ('controller_sha256', controller_raw), ('profile_sha256', profile_raw)):
        require(root_record.get(key) == digest(raw), 'root_envelope_exact_hash_mismatch')
    require(envelope['source_commit'] == profile['source_commit'] == root_record.get('source_commit') == SOURCE, 'source_binding_changed')
    require(profile['source_root']==envelope['source_root']==str(FROZEN),'exact_frozen_source_path_required')
    require(profile['qualification']['status']=='COMPLETE_ALL_GATES_PASSED' and profile['qualification'].get('blocked_reason') is None
        and all(profile['qualification'].get(k) is True for k in ('all_three_local_passed','all_eight_ci_passed','independent_new_package_passed'))
        and profile['resource_review'].get('old_observer_floor_approved') is True,'source_qualification_or_conditional_policy_incomplete')
    require(envelope['controller_sha256'] == digest(controller_raw) == profile['orchestration_controller_sha256'], 'controller_binding_changed')
    require(envelope['profile_sha256'] == digest(profile_raw), 'profile_binding_changed')
    require(tuple(s['stage'] for s in envelope['stages']) == ORDER, 'exact_seven_stage_order_required')
    require(tuple(s['phase'] for s in envelope['stages']) == PHASES, 'exact_smoke_only_phases_required')
    require(root_record.get('scope') == 'EXACT_SEVEN_SMOKE_STAGES_ONCE_NO_LONG', 'delegation_scope_changed')
    require(envelope['outer_seconds'] == 150 and envelope['maximum_producer_starts'] == 1, 'original_smoke_bounds_changed')
    require((envelope['producer_duration_seconds'],envelope['planned_rounds'],envelope['worker_every'],envelope['parent_every'])==(60,15,5,10)
        and envelope['raw_stdout_cap_bytes']==envelope['raw_stderr_cap_bytes']==PIPE_CAP,'exact_smoke_or_raw_bounds_changed')
    require(envelope['smoke_scratch'] == profile['smoke_scratch'] and profile['smoke_scratch'].endswith('smoke-20261117-02'), 'new_job02_required')
    records = set()
    for item in envelope['stages']:
        argv = item['argv']
        require(item['command_sha256'] == command_hash(argv), 'stage_command_hash_changed')
        require(argv[:3] == [profile['python'], '-B', str(FROZEN/'tools/prepare_managed_stability.py')], 'frozen_wrapper_required')
        for flag, value in (('--profile', envelope['profile_file']), ('--invoke', item['phase']),
                            ('--root-go-profile-sha256', digest(profile_raw)), ('--record', item['record'])):
            require(argv.count(flag) == 1 and argv[argv.index(flag)+1] == value, 'exact_stage_argument_changed')
        require(Path(item['record']).name == item['record'] and item['record'].endswith('.json'), 'fresh_record_name_required')
        require(item['record'] not in records, 'stage_record_reused')
        records.add(item['record'])
        require(not any(x in argv for x in ('long-start', 'long-preflight', '_supervise')), 'long_scope_forbidden')
    return envelope, profile


def active(progress):
    return type(progress) is dict and progress.get('status') == 'running'


def precondition(stage, progress, producer_alive, previous_faults=0):
    """Facts from actual progress, never a stage filename or projected clock."""
    if stage == 'startup':
        return producer_alive and active(progress) and type(progress.get('elapsed_seconds')) in (int, float)
    if stage == 'normal-live':
        return (producer_alive and active(progress) and progress.get('rounds', {}).get('DONE', 0) >= 1
                and progress.get('fault_signals') == {'worker': 0, 'parent': 0}
                and progress.get('unresolved_faults') == 0)
    if stage == 'fault-live':
        return (producer_alive and active(progress) and
                (progress.get('fault_signals', {}).get('worker', 0) > previous_faults or progress.get('unresolved_faults', 0) > 0))
    if stage == 'final':
        return not producer_alive and progress.get('status') == 'completed' and progress.get('rounds') == {'DONE': 15}
    return True


def nested_payload(value, required):
    for _ in range(5):
        if type(value) is not dict:
            break
        if required <= value.keys():
            return value
        value = value.get('structured_stdout') if type(value.get('structured_stdout')) is dict else value.get('response')
    raise ValueError('required_original_response_missing')


def receipt_payload(stage, data):
    """Validate the frozen prepare -> managed-smoke -> captured-command schema.

    Child.result checks the actual outer prepare process exit. prepare prints a
    receipt even if its managed-smoke child failed. short-cold is direct stdout,
    whereas produce/observe/strict stdout is captured() with timed_out.
    """
    require(type(data) is dict and type(data.get('exit_code')) is int
            and data.get('stdout_complete') is True, 'prepare_receipt_exit_or_capture_missing')
    require(data.get('timed_out', False) is False, 'prepare_receipt_timeout_not_allowed')
    body = data.get('structured_stdout')
    require(type(body) is dict, 'managed_smoke_original_stdout_missing')
    if stage == 'cold':
        require(data['exit_code'] == 0 and 'exit_code' not in body and 'timed_out' not in body,
                'cold_requires_successful_direct_stdout_contract')
        return body
    require(type(body.get('exit_code')) is int and body.get('timed_out') is False,
            'captured_exit_or_literal_no_timeout_missing')
    payload = body.get('response')
    require(type(payload) is dict, 'captured_response_missing')
    typed_fault_unknown = (stage == 'fault-live' and payload.get('logical_point') == 'unknown'
        and payload.get('alerts') == ['observation_failed_closed'] and type(payload.get('error_type')) is str
        and bool(payload['error_type']) and type(payload.get('error_digest')) is str
        and len(payload['error_digest']) == 64 and all(c in '0123456789abcdef' for c in payload['error_digest']))
    if stage == 'fault-live' and payload.get('logical_point') == 'unknown':
        require(typed_fault_unknown, 'fault_unknown_transport_not_typed')
    expected = 1 if stage == 'strict-negative' or typed_fault_unknown else 0
    require(data['exit_code'] == body['exit_code'] == expected, 'nested_command_exit_not_expected')
    return payload


def validate_result(stage, data, before, after, alive_after, witness=None):
    payload = receipt_payload(stage, data)
    if stage in ('startup', 'normal-live', 'fault-live', 'final'):
        sample = payload
        require({'logical_point','sample_wall_ns'} <= sample.keys(), 'sample_response_missing')
        require(type(sample.get('alerts')) is list, 'sample_alerts_unknown')
        classifier = verified_module(FROZEN/'tools/managed_observer_coverage.py', 'frozen_json_classifier', CLASSIFIER_SHA)
        require(not classifier.fatal_financial_codes(sample), 'fatal_financial_code_observed')
        require('producer_reported_error' not in sample['alerts'], 'producer_reported_error')
        technical = {'observation_failed_closed', 'worker_lease_inactive_or_unknown', 'process_visibility_unknown',
                     'worker_process_visibility_unknown', 'market_stale'}
        require(not sample['alerts'] or stage in ('startup','fault-live') and set(sample['alerts']) <= technical,
                'unexpected_stage_alert')
        if stage != 'final':
            require(active(before) and active(after) and alive_after, 'live_observation_outside_actual_active_run')
        if stage == 'normal-live':
            require(sample['logical_point'] == 'stable_boundary' and sample.get('finance', {}).get('golden', {}).get('passed') is True
                    and sample.get('finance',{}).get('golden',{}).get('compared') is True,
                    'normal_stable_golden_not_observed')
            require(after.get('fault_signals')=={'worker':0,'parent':0} and sample.get('planned_faults')==[],
                    'normal_observation_not_before_actual_fault')
        if stage == 'fault-live':
            require(type(witness) is dict and witness.get('pidfd_death_observed') is True, 'current_fault_pidfd_witness_missing')
            require(witness['death_wall_ns'] <= sample['sample_wall_ns'] <= witness['death_wall_ns']+5*10**9,
                    'sample_outside_actual_fault_window')
            require(sample['logical_point'] in ('inflight_or_unknown', 'unknown'), 'recovered_stable_sample_is_not_fault_live')
            if sample['logical_point'] == 'unknown':
                require('observation_failed_closed' in sample['alerts'] and after.get('fault_signals',{}).get('worker',0) > witness['previous_worker_faults'],
                        'typed_fault_unknown_requires_actual_fault_increment')
            else:
                require(any(f.get('kind')=='worker' and f.get('old_generation')==witness['old_generation']
                    and (f.get('state')=='PLANNED' or f.get('round') in sample.get('active_rounds',[]))
                    for f in sample.get('planned_faults',[])), 'sample_current_fault_round_or_generation_missing')
        if stage == 'final':
            require(sample.get('finance', {}).get('golden', {}).get('passed') is True and sample['completed_rounds'] == 15, 'final_independent_golden_missing')
            require(type(sample.get('active_elapsed_seconds')) in (int,float) and sample['active_elapsed_seconds']>=60,
                    'short_actual_active_time_incomplete')
            final=sample.get('final_reconciliation',{})
            require(set(final.get('errors',[]))=={'actual_6h_and_5400_rounds_required','producer_actual_active_duration_incomplete','producer_cold_audit_same_watermark_missing'}
                and final.get('independent_reopen_reconciliation_passed') is True and final.get('independent_reopen_same_watermark') is True,
                'final_full_reopen_or_expected_short_blockers_missing')
        require(sample.get('final_evidence_eligible') is not True, 'short_run_must_not_issue_long_evidence')
        require(all(sample.get(k) is False for k in ('continuous_6h_stability_passed','continuous_24h_stability_passed',
                    'capacity_10000_per_s_passed','production_approved')), 'short_run_future_flags_invalid')
        return {'logical_point': sample['logical_point'], 'completed_rounds': sample.get('completed_rounds'),
                'inflight_or_unknown_observed': sample['logical_point'] != 'stable_boundary',
                'actual_fault_signals_after': after.get('fault_signals'), 'financial_6h_passed': False,
                'normal_worker_process': sample.get('worker',{}).get('process') if stage=='normal-live' else None,
                'normal_worker_generation': sample.get('worker',{}).get('generation') if stage=='normal-live' else None,
                'fault_witness': witness if stage=='fault-live' else None}
    if stage == 'cold':
        cold = payload
        require({'short_smoke_cold_audit_passed','watermark_before','watermark_after'} <= cold.keys(), 'cold_response_missing')
        require(cold['short_smoke_cold_audit_passed'] is True and cold['watermark_before'] == cold['watermark_after']
                and cold.get('long_run_receipt_issued') is False, 'actual_private_cold_same_watermark_required')
        return {'short_smoke_cold_audit_passed': True, 'long_run_receipt_issued': False}
    if stage == 'strict-negative':
        error = payload
        require(data.get('exit_code') == 1 and error['error_type'] == 'ValueError'
                and error['error_digest'] == digest(b'producer_audit_requires_other_final_checks_passed')
                and error.get('final_evidence_eligible') is False, 'strict_long_negative_not_expected_refusal')
        return {'strict_long_refused': True, 'financial_6h_passed': False}
    return {}


def execute(envelope, io):
    """Small ordering core; fake IO tests never instantiate the live boundary."""
    state = {name: 'NOT_RUN' for name in ORDER}
    producer = None
    normal_faults = 0
    try:
        for item in envelope['stages']:
            stage = item['stage']
            before = io.wait_precondition(stage, producer, normal_faults)
            admission = io.admit(item)  # fixed57 then f31; this does not Popen business work.
            child = io.spawn(item, admission)  # f31 again at this exact Popen boundary.
            if stage == 'produce':
                producer = child
                state[stage] = 'STARTED_ASYNC'
                continue
            data = io.finish(child, item)
            after = io.progress()
            projection = validate_result(stage, data, before, after, io.alive(producer), io.fault_witness)
            if stage == 'normal-live':
                normal_faults = after['fault_signals']['worker']
            state[stage] = 'PASS'
            io.record_stage(item, projection)
        io.finish_producer(producer)
        io.final_check()
        state['produce'] = 'PASS'
    except BaseException as error:
        # Safe action precedes fallible diagnostics; never signal protected/unknown PID.
        state['failed_stage'] = item['stage']
        state['error_type'] = type(error).__name__
        state['error_digest'] = digest(str(error).encode())
        try: io.drain_owned(producer)
        except BaseException as secondary: state['drain_secondary_error'] = type(secondary).__name__
    finally:
        try: io.close()
        except BaseException as secondary: state['close_secondary_error'] = type(secondary).__name__
        try: io.final_check()
        except BaseException as secondary: state['final_budget_error'] = type(secondary).__name__
    if getattr(io,'cleanup_errors',[]): state['cleanup_errors']=io.cleanup_errors
    return {'stage_states': state, 'full_smoke_passed': set(state)==set(ORDER) and all(state.get(name) == 'PASS' for name in ORDER),
            'financial_6h_passed': False, 'production_approved': False, 'new_long_authorized': False}


class Child:
    """Actual pipes persist bounded private bytes before any JSON projection."""
    def __init__(self, argv, directory, raw_prefix, identity, register):
        self.fd, self.identity, self.streams, self.threads, self.failure, self.error = None, None, {}, [], Event(), None
        self.p = subprocess.Popen(argv, cwd=directory, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, close_fds=True, start_new_session=True)
        register(self)  # Own the unreaped Popen before any fallible pidfd/identity/thread setup.
        try:
            require(self.p.pid not in {4471,8784}, 'protected_old_PID')
            self.fd = os.pidfd_open(self.p.pid)
            self.identity = identity(self.p.pid, None)
            for name, stream in (('stdout', self.p.stdout), ('stderr', self.p.stderr)):
                thread = Thread(target=self._drain, args=(name, stream, Path(str(raw_prefix)+'.'+name)), daemon=True)
                thread.start(); self.threads.append(thread)
        except BaseException:
            try: self.stop()
            except BaseException: pass
            try: self.close()
            except BaseException: pass
            raise

    def fail(self, code):
        self.error = self.error or code
        self.failure.set()

    def _drain(self, name, stream, path):
        checksum, count, retained, failure = sha256(), 0, 0, None
        target = None
        try:
            target = os.fdopen(os.open(path, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600), 'wb')
            while True:
                chunk = stream.read(65536)
                if not chunk: break
                checksum.update(chunk); count += len(chunk)
                if failure is None:
                    if retained+len(chunk)>PIPE_CAP: failure = 'private_pipe_budget_exceeded'; self.fail(failure)
                    else:
                        try: target.write(chunk); retained += len(chunk)
                        except OSError: failure = 'private_pipe_write_failed'; self.fail(failure)
            try: target.flush(); os.fsync(target.fileno())
            except OSError: failure = failure or 'private_pipe_flush_failed'; self.fail(failure)
        except OSError:
            failure = failure or 'private_pipe_open_failed'; self.fail(failure)
            for chunk in iter(lambda: stream.read(65536), b''):
                checksum.update(chunk); count += len(chunk)
        finally:
            stream.close()
            if target is not None:
                try: target.close()
                except OSError: failure = failure or 'private_pipe_close_failed'; self.fail(failure)
            self.streams[name] = {'file': str(path), 'bytes': count, 'retained_bytes': retained,
                                  'sha256': checksum.hexdigest(), 'error': failure, 'complete': failure is None and count == retained}

    def done(self):
        if self.p.returncode is not None: return True
        return os.waitid(os.P_PIDFD,self.fd,os.WEXITED|os.WNOHANG|os.WNOWAIT) is not None

    def result(self):
        for thread in self.threads: thread.join(timeout=1)
        require(set(self.streams) == {'stdout', 'stderr'} and all(x['complete'] for x in self.streams.values()), 'private_pipe_raw_incomplete')
        require(self.p.wait(timeout=1) == 0, 'outer_wrapper_failed')
        return json.loads(Path(self.streams['stdout']['file']).read_bytes())

    def stop(self):
        require(self.p.pid not in {4471,8784}, 'protected_old_PID')
        # Unreaped Popen reserves this new session-leader PID; never target a reused group.
        if self.p.returncode is None:
            try: os.killpg(self.p.pid,signal.SIGTERM)
            except ProcessLookupError: pass
            try: self.p.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try: os.killpg(self.p.pid,signal.SIGKILL)
                except ProcessLookupError: pass
                self.p.wait(timeout=2)
        for thread in self.threads: thread.join(timeout=1)
        for stream in (self.p.stdout,self.p.stderr):
            if not stream.closed: stream.close()

    def close(self):
        if self.fd is not None: os.close(self.fd); self.fd = None


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


def verified_module(path, name, expected):
    from types import ModuleType
    raw = Path(path).read_bytes()
    require(digest(raw)==expected, 'verified_module_bytes_changed')
    module = ModuleType(name); module.__file__=str(path)
    exec(compile(raw,str(path),'exec'),module.__dict__)
    return module


class Live:
    def __init__(self, envelope, profile, root_record, root_sha):
        sys.dont_write_bytecode = True; sys.path.insert(0, str(FROZEN))
        self.e, self.profile, self.root_record, self.root_sha = envelope, profile, root_record, root_sha
        self.capture = verified_module(envelope['capture_file'], 'fixed_admission_capture', CAPTURE_SHA)
        self.guard = verified_module(envelope['guard_file'], 'fixed_consume_guard', GUARD_SHA)
        self.job = Path(profile['smoke_scratch'])/'job'
        self.base = Path(envelope['private_controller_output'])
        require(not self.base.exists() and not Path(profile['smoke_scratch']).exists(), 'fresh_job_and_private_output_required')
        self.base.mkdir(mode=0o700)
        self.children, self.driver, self.worker, self.fault_witness, self.deadline, self.first = [], None, None, None, None, None
        self.cleanup_errors=[]
        self.boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()

    def save(self, name, value):
        path = self.base/name
        with path.open('xb') as stream: stream.write(encoded(value)); stream.flush(); os.fsync(stream.fileno())
        path.chmod(0o600)
        return path

    def identity(self, pid, expected):
        require(type(pid) is int and pid not in {4471,8784} and pid > 0, 'protected_or_invalid_new_PID')
        stat_fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
        uids = [int(x) for x in next(s for s in Path(f'/proc/{pid}/status').read_text().splitlines() if s.startswith('Uid:')).split()[1:]]
        require(stat_fields[0] not in {'Z','X','x'} and all(x == os.geteuid() for x in uids)
                and (expected is None or expected == stat_fields[19]), 'owned_PID_birth_UID_not_live')
        return {'pid':pid,'birth':stat_fields[19],'uid':os.geteuid(),'boot':self.boot,
                'captured_wall_ns':time.time_ns(),'captured_boottime_ns':time.clock_gettime_ns(time.CLOCK_BOOTTIME)}

    def alive(self, child): return child is not None and not child.done()

    def progress(self):
        path = self.job/'progress.json'
        return json.loads(path.read_bytes()) if path.exists() else {}

    def budget(self):
        require(self.deadline is None or time.clock_gettime_ns(time.CLOCK_BOOTTIME) < self.deadline, 'outer150_expired')
        require(not any(c.failure.is_set() for c in self.children), 'private_pipe_capture_failed')

    def bind_driver(self):
        path = Path(self.profile['smoke_scratch'])/'observer/launch.json'
        if self.driver is None and path.exists():
            row = json.loads(path.read_bytes()); pid, birth = row['driver_pid'], row['driver_birth']
            require(type(pid) is int and pid not in {4471,8784}, 'protected_driver_PID')
            fd = os.pidfd_open(pid)
            try: identity = self.identity(pid, birth)
            except BaseException: os.close(fd); raise
            self.driver = (fd, identity)
            self.save('actual-driver-identity.json', identity)

    def wait_precondition(self, stage, producer, previous_faults):
        limit = time.monotonic()+75 if stage == 'produce' else None
        while True:
            self.budget()
            if stage == 'produce':
                latest = json.loads((self.capture.OBSERVER/'latest.json').read_bytes())
                age = (time.time_ns()-latest['observed_ns'])/1e9
                if 0 <= age <= 2: return {}
                require(time.monotonic()<limit, 'no_fresh_initial_window')
            else:
                self.bind_driver(); row = self.progress()
                if stage=='fault-live':
                    require(self.worker is not None,'normal_worker_pidfd_missing')
                    if select.select([self.worker[0]],[],[],0)[0]:
                        require(self.alive(producer) and active(row),'worker_death_outside_active_run')
                        self.fault_witness={**self.worker[1],'pidfd_death_observed':True,
                            'death_wall_ns':time.time_ns(),'death_boottime_ns':time.clock_gettime_ns(time.CLOCK_BOOTTIME),
                            'previous_worker_faults':previous_faults}
                        return row
                elif precondition(stage, row, self.alive(producer), previous_faults): return row
                require(self.alive(producer) or stage == 'final', 'producer_ended_before_live_phase')
                if stage == 'final' and producer.done():
                    require(row.get('status') == 'completed', 'producer_not_naturally_completed')
            time.sleep(.025)

    def admit(self, item):
        self.budget()
        name = item['stage']+'-'+str(time.time_ns())
        snapshot = self.base/(name+'-admission.json')
        try:
            row = self.capture.capture(self.e['profile_sha256'], item['phase'], item['command_sha256'])
        except BaseException as error:
            self.save(name+'-admission-UNKNOWN.json', {'status':'UNKNOWN_OR_NO_GO','error_type':type(error).__name__,'error_digest':digest(str(error).encode())})
            raise
        self.save(snapshot.name, row)
        go = {'authorized':True,'phase':item['phase'],'stage':item['stage'],'profile_sha256':self.e['profile_sha256'],
              'command_sha256':item['command_sha256'],'snapshot_sha256':digest(snapshot.read_bytes()),
              'root_approved_envelope_sha256':self.root_record['envelope_sha256'],'root_delegation_record_sha256':self.root_sha}
        self.guard.consume_guard(self.e['profile_file'],item['argv'],snapshot,go,now_wall_ns=time.time_ns(),
            now_boottime_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME),current_boot=self.boot)
        self.save(name+'-delegated-stageGO.json', go)
        return snapshot, go

    def spawn(self, item, admission):
        self.budget(); snapshot, go = admission
        self.guard.consume_guard(self.e['profile_file'],item['argv'],snapshot,go,now_wall_ns=time.time_ns(),
            now_boottime_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME),current_boot=self.boot)
        now = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
        if self.first is None:
            require(item['stage'] == 'produce', 'producer_must_be_first_Popen')
            self.first, self.deadline = now, now+150*10**9
        child = Child(item['argv'], FROZEN, self.base/item['stage'], self.identity, self.children.append)
        self.save(item['stage']+'-actual-Popen.json', {'identity':child.identity,'first_Popen_boottime_ns':self.first,
            'unchanged_controller_deadline_boottime_ns':self.deadline,'phase':item['phase'],'command_sha256':item['command_sha256']})
        return child

    def finish(self, child, item):
        while not child.done(): self.budget(); self.bind_driver(); time.sleep(.025)
        self.budget()
        data = child.result()
        self.budget()
        self.save(item['stage']+'-raw-stream-manifest.json', child.streams)
        if item['stage']=='fault-live':
            while self.progress().get('fault_signals',{}).get('worker',0)<=self.fault_witness['previous_worker_faults']:
                self.budget()
                require(time.time_ns()<=self.fault_witness['death_wall_ns']+5*10**9,'fault_increment_not_witnessed_in_window')
                time.sleep(.025)
        self.budget()
        return data

    def finish_producer(self, producer):
        data = self.finish(producer, {'stage':'produce'})
        original = receipt_payload('produce', data)
        require(original.get('status') == 'completed' and original.get('planned_rounds') == 15
            and original.get('rounds') == {'DONE':15}, 'producer_original_stdout_not_complete')
        row = self.progress()
        require(row.get('status') == 'completed' and row.get('rounds') == {'DONE':15}
            and row.get('fault_signals') == {'worker':3,'parent':1} and row.get('elapsed_seconds',0) >= 60, 'producer_original_schedule_incomplete')

    def record_stage(self, item, value):
        if item['stage']=='normal-live':
            worker=value['normal_worker_process']
            require(type(worker) is dict and worker.get('alive') is True,'normal_worker_identity_unavailable')
            require(type(value['normal_worker_generation']) is int and value['normal_worker_generation']>=1,'normal_worker_generation_unknown')
            pid,birth=worker['pid'],worker['birth']
            require(type(pid) is int and pid not in {4471,8784},'protected_worker_PID')
            fd=os.pidfd_open(pid)
            try: identity=self.identity(pid,birth)
            except BaseException: os.close(fd); raise
            ancestor=pid
            for _ in range(8):
                if ancestor==self.driver[1]['pid']: break
                ancestor=int(Path(f'/proc/{ancestor}/stat').read_text().rsplit(')',1)[1].split()[1])
            else:
                os.close(fd);raise ValueError('normal_worker_not_owned_driver_descendant')
            self.worker=(fd,{**identity,'old_generation':value['normal_worker_generation']})
        self.save(item['stage']+'-public-projection.json', value)
        self.budget()

    def drain_owned(self, producer):
        if self.driver is not None:
            fd, row = self.driver
            try:
                self.identity(row['pid'],row['birth']); signal.pidfd_send_signal(fd,signal.SIGTERM)
                select.select([fd],[],[],2)  # Official driver drain gets a bounded grace first.
            except (OSError,ValueError): pass
        for child in self.children:
            try: child.stop()
            except (OSError,ValueError,subprocess.TimeoutExpired) as error:
                self.cleanup_errors.append(type(error).__name__)

    def close(self):
        errors=[]
        for fd in [row[0] for row in (self.driver,self.worker) if row is not None]:
            try: os.close(fd)
            except OSError as error: errors.append(type(error).__name__)
        for child in self.children:
            try: child.close()
            except OSError as error: errors.append(type(error).__name__)
        require(not errors,'owned_descriptor_cleanup_unknown')

    def final_check(self): self.budget()


def main(argv=None):
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--envelope',required=True,type=Path)
    parser.add_argument('--root-approved-envelope-record',required=True,type=Path)
    args=parser.parse_args(argv)
    root_raw=args.root_approved_envelope_record.read_bytes(); root_record=json.loads(root_raw)
    env_raw=args.envelope.read_bytes(); env=json.loads(env_raw)
    envelope,profile=approved(env_raw,root_record,Path(__file__).read_bytes(),Path(env['profile_file']).read_bytes())
    io=Live(envelope,profile,root_record,digest(root_raw))
    result=execute(envelope,io)
    try:
        io.save('outcome-provisional.json',{**result,'pending_post_write_deadline_check':True})
        io.final_check()
    except BaseException as error:
        result['full_smoke_passed']=False
        result['outcome_write_or_final_budget_error']=type(error).__name__
    print(json.dumps(result,sort_keys=True))
    return 0 if result['full_smoke_passed'] else 1


if __name__=='__main__': raise SystemExit(main())
