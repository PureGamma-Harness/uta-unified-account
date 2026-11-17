"""Persistent supervisor for the preregistered exact-source synthetic six-hour job.

preflight is read-only. start is used only after root's separate explicit GO.
The original producer and supported observer CLI remain separate child processes.
"""
from __future__ import annotations
import argparse
import copy
from hashlib import sha256
import json
import os
from pathlib import Path
import resource
import signal
import sqlite3
import subprocess
import sys
from threading import Event, Thread
import time

sys.dont_write_bytecode = True
try:
    from tools import managed_soak_observer as ro
    from tools.managed_observer_coverage import Coverage, fatal_financial_codes
    from tools.managed_observer_smoke import PUBLIC_FIELDS
except ModuleNotFoundError:
    import managed_soak_observer as ro
    from managed_observer_coverage import Coverage, fatal_financial_codes
    from managed_observer_smoke import PUBLIC_FIELDS

ROOT = Path(__file__).resolve().parents[1]
PLAN = Path('/workspace/uta-next-integration/benchmarks/plans/20261117-managed-763202d-six-hours.json')
AMENDMENT = PLAN.with_name('20261117-managed-763202d-six-hours-observer-amendment.json')
SCRATCH = Path('/workspace/uta-managed-observer-runs/763202d-six-hours-20261117')
OUTPUT_CAP = 6 * 1024**3
LINE_CAP = 64 * 1024**2
RESULT_FIELDS = PUBLIC_FIELDS | {'producer_cold_audit_passed', 'audit_sha256', 'producer_audit_scope',
    'producer_audit_runtime', 'watermark_before', 'watermark_after', 'private_clone_estimated_bytes', 'private_clone_max_bytes'}


def append(path, value):
    with Path(path).open('a') as stream:
        stream.write(ro.canonical(value) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


def classify_safely(coverage, sample, *, elapsed, attempt):
    """Keep malformed telemetry from corrupting counters or ending collection."""
    previous = copy.deepcopy(coverage)
    try:
        return coverage, coverage.observe(sample, job_elapsed_seconds=elapsed, sample_attempt_id=attempt), None
    except (ValueError, TypeError, KeyError, ArithmeticError) as error:
        marker = {'synthetic': True, 'logical_point': 'unknown', 'alerts': ['observation_failed_closed'],
            'record_origin': 'supervisor_classification_error_marker', 'error_type': type(error).__name__,
            'error_digest': sha256(str(error).encode()).hexdigest(), **ro.FLAGS}
        return previous, previous.observe(marker, job_elapsed_seconds=elapsed, sample_attempt_id=attempt), marker


def financial_drain_before_log(producer, fatal, history, path):
    """A full output disk must never suppress a known financial safety action."""
    history.update(fatal)
    sent = producer.terminate_owned()
    try:
        append(path, {'synthetic': True, 'at_wall_ns': time.time_ns(),
            'action': 'SIGTERM_ORIGINAL_DRIVER_FOR_OFFICIAL_DRAIN', 'fatal_codes': fatal,
            'driver_identity': producer.identity(), 'signal_sent': sent})
    except OSError:
        pass
    return sent


def git(root, *args):
    return subprocess.check_output(['git', '--no-optional-locks', *args], cwd=root, stdin=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, close_fds=True, text=True).strip()


def read_plan(path, amendment):
    raw, change = path.read_bytes(), ro.load_json(amendment)
    plan = ro.parse(raw)
    if sha256(raw).hexdigest() != change['original_plan_sha256']:
        raise ValueError('original_preregistration_bytes_changed')
    expected = (plan['producer']['duration_seconds'], plan['producer']['rate_rounds_per_second'],
        plan['producer']['planned_rounds'], plan['producer']['worker_fault_every_rounds'],
        plan['producer']['parent_fault_every_rounds'], change['observer_interval_seconds_effective'])
    if expected != (21600, .25, 5400, 30, 300, 61):
        raise ValueError('unsupported_preregistered_workload')
    if (plan['observer']['blocks'] != 12 or plan['observer']['technical_read_unknown_budget'] != 3
            or plan['observer']['maximum_consecutive_technical_read_unknown'] != 1):
        raise ValueError('preregistered_coverage_budget_changed')
    plan['observer']['interval_seconds'] = change['observer_interval_seconds_effective']
    return plan, change, {'base_plan_sha256': sha256(raw).hexdigest(),
        'amendment_sha256': sha256(amendment.read_bytes()).hexdigest()}


def producer_command(plan, job):
    # Rate .25 and faults 30/300 are the unchanged original Configuration defaults.
    return [plan['python'], '-B', 'benchmarks/run_managed_soak.py', 'run', '--directory', str(job),
        '--duration', '21600', '--allow-long-run', '--validation-report', plan['validation_report']]


def observer_command(plan, scratch, launch, *, audit=False, persistent=True):
    output, job = scratch / 'observer', scratch / 'job'
    command = [plan['python'], '-B', str(ROOT / 'tools/managed_soak_observer.py'),
        'producer-audit' if audit else 'watch', '--job', str(job), '--output', str(output),
        '--source', plan['source_root'], '--frozen-commit', plan['source_commit'],
        '--driver-pid', str(launch['driver_pid']), '--driver-birth', launch['driver_birth'],
        '--interval', str(plan['observer']['interval_seconds']), '--max-private-clone-bytes',
        str(plan['observer']['max_private_clone_bytes']), '--min-private-free-bytes',
        str(plan['observer']['clone_headroom_bytes']), '--max-address-space-bytes',
        str(plan['observer']['max_address_space_bytes'])]
    if audit:
        command += ['--python', plan['python']]
    elif persistent:
        # Record the actual CLI exec PID/birth, not merely Bubblewrap's monitor.
        prefix = "import os,sys; from tools.managed_soak_observer import atomic_json,process_identity; atomic_json(sys.argv[1],{'pid':os.getpid(),'birth':process_identity(os.getpid())['birth']}); os.execv(sys.executable,[sys.executable,'-B',*sys.argv[2:]])"
        command = [plan['python'], '-B', '-c', prefix, str(output / 'watch-cli-identity.json'), *command[2:]]
    return ['bwrap', '--ro-bind', '/', '/', '--dev', '/dev', '--die-with-parent',
            '--bind', str(output), str(output), '--', *command]


def preflight(args):
    plan, amendment, fingerprints = read_plan(args.plan, args.amendment)
    source, scratch = Path(plan['source_root']).resolve(), args.scratch.resolve()
    if scratch.exists() or scratch.is_relative_to(source) or scratch.is_relative_to(ROOT):
        raise ValueError('new_external_private_scratch_required')
    if git(ROOT, 'status', '--porcelain', '--untracked-files=all'):
        raise ValueError('observer_checkout_must_be_frozen_clean')
    if git(source, 'rev-parse', 'HEAD') != plan['source_commit']:
        raise ValueError('producer_frozen_commit_changed')
    environment = dict(os.environ, GIT_OPTIONAL_LOCKS='0', PYTHONDONTWRITEBYTECODE='1')
    code = "from benchmarks.managed_qualification import qualify; import json,sys; print(json.dumps(qualify(sys.argv[1]).evidence,sort_keys=True))"
    run = subprocess.run(['bwrap', '--ro-bind', '/', '/', '--dev', '/dev', '--', plan['python'], '-B', '-c', code,
        plan['validation_report']], cwd=source, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, close_fds=True, env=environment, timeout=30)
    if run.returncode:
        raise ValueError('actual_exact_source_qualification_failed:' + sha256(run.stderr).hexdigest())
    evidence = ro.parse(run.stdout)
    if evidence['code_commit'] != plan['source_commit'] or evidence['tests_run'] != plan['qualification']['tests_each']:
        raise ValueError('qualified_report_does_not_match_preregistration')
    probe = subprocess.run(['bwrap', '--ro-bind', '/', '/', '--dev', '/dev', '--', plan['python'], '-B', '-c',
        "import json,os,stat,subprocess,sys; r=subprocess.run(['git','--version'],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,close_fds=True); print(json.dumps({'source_readonly':bool(os.statvfs(sys.argv[1]).f_flag & os.ST_RDONLY),'devnull_character_device':stat.S_ISCHR(os.stat('/dev/null').st_mode),'devnull_child_exit':r.returncode}))", str(source)],
        cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True, timeout=10)
    mount = ro.parse(probe.stdout) if probe.returncode == 0 else None
    if mount != {'source_readonly': True, 'devnull_character_device': True, 'devnull_child_exit': 0}:
        raise ValueError('readonly_device_preflight_failed')
    parent = scratch.parent
    if not parent.exists() or parent.stat().st_uid != os.geteuid() or parent.stat().st_mode & 0o777 != 0o700:
        raise ValueError('private_scratch_parent_required')
    free = __import__('shutil').disk_usage(parent).free
    required = (plan['producer']['source_budget_bytes'] + OUTPUT_CAP + plan['observer']['max_private_clone_bytes']
                + plan['observer']['clone_headroom_bytes'])
    if free < required:
        raise ValueError('conservative_source_output_clone_disk_reservation_unavailable')
    return {'synthetic': True, 'status': 'PREFLIGHT_ONLY_NOT_STARTED', 'service_started': False,
        'producer_source_commit': plan['source_commit'], 'observer_freeze_commit': git(ROOT, 'rev-parse', 'HEAD'),
        **fingerprints, 'qualification': evidence, 'source_readonly_device_probe': mount,
        'producer_command_argv': producer_command(plan, scratch / 'job'), 'producer_cwd': str(source),
        'observer_cli_interval_seconds': 61, 'replay_scope': amendment['replay_scope'],
        'expected_business_counts': {'account_commands': 32400, 'orders': 21600, 'fills': 21600,
            'matches': 10800, 'risk_decisions': 43200, 'ledger_events': 27006,
            'partial_cancelled_orders': 5400, 'worker_fault_signals': 180, 'parent_fault_signals': 18},
        'disk_free_bytes': free, 'conservative_required_free_bytes': required,
        'source_budget_bytes': plan['producer']['source_budget_bytes'], 'observer_output_budget_bytes': OUTPUT_CAP,
        'private_clone_budget_bytes': plan['observer']['max_private_clone_bytes'],
        'clone_headroom_bytes': plan['observer']['clone_headroom_bytes'],
        'observer_address_space_limit_bytes': plan['observer']['max_address_space_bytes'],
        'supervisor_post_duration_grace_seconds': 600, 'official_drain_warning_after_seconds': 120,
        'selected_cpu': min(os.sched_getaffinity(0)), 'continuous_resume_allowed': False,
        'coverage_counters': None, 'known_failed_gate': plan['known_failed_gate'],
        'production_approved': False, 'capacity_10000_per_s_passed': False,
        'financial_6h_passed': False, 'live_coverage_passed': False}


class Pipes:
    """Keep six-hour pipes drained, retaining bounded final stdout and no stderr."""
    def __init__(self, command, cwd, stdout_limit=4 * 1024**2):
        self.process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, close_fds=True)
        self.birth = ro.process_identity(self.process.pid)['birth']
        if self.birth is None:
            raise ValueError('new_child_birth_unavailable')
        self.started_wall_ns, self.started_boottime_ns = time.time_ns(), time.clock_gettime_ns(time.CLOCK_BOOTTIME)
        self.results = {}
        def drain(label, stream, retain):
            checksum, count, kept, chunks = sha256(), 0, 0, []
            try:
                while True:
                    raw = stream.read(65536)
                    if not raw:
                        break
                    checksum.update(raw); count += len(raw)
                    if retain and kept + len(raw) <= stdout_limit:
                        chunks.append(raw); kept += len(raw)
            finally:
                stream.close()
            self.results[label] = {'sha256': checksum.hexdigest(), 'bytes': count,
                'complete': not retain or count == kept, 'raw': b''.join(chunks)}
        self.threads = [Thread(target=drain, args=('stdout', self.process.stdout, True), daemon=True),
                        Thread(target=drain, args=('stderr', self.process.stderr, False), daemon=True)]
        for thread in self.threads:
            thread.start()

    def identity(self):
        return {'pid': self.process.pid, 'birth': self.birth, 'started_wall_ns': self.started_wall_ns,
                'started_boottime_ns': self.started_boottime_ns}

    def terminate_owned(self):
        if self.process.pid in {4471, 8784}:
            raise ValueError('protected_old_process')
        if ro.process_identity(self.process.pid, self.birth)['alive']:
            self.process.send_signal(signal.SIGTERM)
            return True
        return False

    def result(self):
        if self.process.poll() is None:
            raise ValueError('child_not_finished')
        for thread in self.threads:
            thread.join(timeout=2)
        if set(self.results) != {'stdout', 'stderr'}:
            raise ValueError('child_pipe_not_closed')
        out, err = self.results['stdout'], self.results['stderr']
        value = None
        if out['complete'] and out['raw']:
            try:
                raw = ro.parse(out['raw'])
                value = {key: raw[key] for key in RESULT_FIELDS if key in raw}
            except (ValueError, TypeError):
                pass
        return {'synthetic': True, 'exit_code': self.process.returncode, 'identity': self.identity(),
            'ended_wall_ns': time.time_ns(), 'stdout_sha256': out['sha256'], 'stdout_complete': out['complete'],
            'stderr_present': err['bytes'] > 0, 'stderr_sha256': err['sha256'], 'response': value, **ro.FLAGS}


class Timeline:
    def __init__(self, path):
        self.path, self.offset, self.pending = path, 0, b''
        self.invalid_rows = 0

    def read(self):
        if not self.path.exists():
            return []
        with self.path.open('rb') as stream:
            stream.seek(self.offset)
            raw = stream.read(LINE_CAP)
        self.offset += len(raw)
        data, values = self.pending + raw, []
        lines = data.split(b'\n'); self.pending = lines.pop()
        if len(self.pending) > LINE_CAP:
            raise ValueError('observer_jsonl_line_over_budget')
        for line in lines:
            try:
                values.append(ro.parse(line))
            except (ValueError, TypeError) as error:
                self.invalid_rows += 1
                values.append({'synthetic': True, 'logical_point': 'unknown', 'alerts': ['observation_failed_closed'],
                    'record_origin': 'supervisor_invalid_jsonl_marker', 'error_type': type(error).__name__,
                    'error_digest': sha256(line).hexdigest(), **ro.FLAGS})
        return values


def final_once(plan, scratch, launch, name, *, receipt=False):
    command = observer_command(plan, scratch, launch, persistent=False)
    command += ['--once']
    if receipt:
        command += ['--producer-receipt', str(scratch / 'observer/producer-cold-audit-receipt.json')]
    child = Pipes(command, ROOT, stdout_limit=LINE_CAP)
    try:
        child.process.wait(timeout=300)
    except subprocess.TimeoutExpired:
        child.terminate_owned(); raise ValueError('final_observer_timeout')
    result = child.result(); ro.atomic_json(scratch / 'control' / name, result)
    return result


def request_observer_stop(observer, output):
    path = output / 'watch-cli-identity.json'
    if path.exists():
        identity = ro.load_json(path)
        if identity['pid'] in {4471, 8784}:
            raise ValueError('protected_old_process')
        if ro.process_identity(identity['pid'], identity['birth'])['alive']:
            os.kill(identity['pid'], signal.SIGTERM)
    else:
        observer.terminate_owned()
    try:
        observer.process.wait(timeout=180)
        return True
    except subprocess.TimeoutExpired:
        observer.terminate_owned()
        try:
            observer.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            return False
        return False


def supervise(args):
    scratch = args.scratch.resolve()
    registered = ro.load_json(scratch / 'control/preflight.json')
    plan, amendment, fingerprints = read_plan(args.plan, args.amendment)
    if any(registered[key] != value for key, value in fingerprints.items()) or registered['observer_freeze_commit'] != git(ROOT, 'rev-parse', 'HEAD'):
        raise ValueError('frozen_launcher_or_plan_changed')
    os.sched_setaffinity(0, {registered['selected_cpu']})
    control, output, job = scratch / 'control', scratch / 'observer', scratch / 'job'
    producer = Pipes(producer_command(plan, job), Path(plan['source_root']))
    identity = producer.identity()
    launch = {'synthetic': True, 'driver_pid': identity['pid'], 'driver_birth': identity['birth'],
        'launched_wall_ns': identity['started_wall_ns'], 'launched_boottime_ns': identity['started_boottime_ns'], **ro.FLAGS}
    ro.atomic_json(control / 'launch.json', launch)
    ro.atomic_json(control / 'supervisor-identity.json', {'synthetic': True, 'pid': os.getpid(),
        'birth': ro.process_identity(os.getpid())['birth'], 'cpu': sorted(os.sched_getaffinity(0))})
    coverage, timeline = Coverage(plan), Timeline(output / 'timeline.jsonl')
    stop, observer, drained, attempt = Event(), None, False, 0
    observer_start_attempted = False
    historical_financial_alerts = set()
    drain_requested_ns = None
    for number in (signal.SIGTERM, signal.SIGINT):
        signal.signal(number, lambda *_: stop.set())
    collection_errors = []
    last_budget_check = 0
    last_sample_elapsed = None
    last_coverage_record = None
    def coverage_report(elapsed, final=False):
        value = coverage.report(completed_active_seconds=elapsed, final=final)
        if collection_errors:
            value['coverage_status'] = 'NO_GO'
            value['coverage_no_go_reasons'] = sorted(set(value['coverage_no_go_reasons']) | set(collection_errors))
        value['watch_timeline_count_scope_complete'] = not collection_errors and not timeline.pending
        return value
    def collect():
        nonlocal attempt, drained, last_budget_check, last_sample_elapsed, coverage, drain_requested_ns, last_coverage_record
        try:
            samples = timeline.read()
        except (OSError, ValueError, TypeError) as error:
            code = 'observer_timeline_unreadable_or_invalid'
            if code not in collection_errors:
                collection_errors.append(code)
                append(control / 'collection-errors.jsonl', {'synthetic': True, 'code': code,
                    'at_wall_ns': time.time_ns(), 'error_type': type(error).__name__,
                    'error_digest': sha256(str(error).encode()).hexdigest(), 'financial_drain_requested': False})
            samples = []
        for sample in samples:
            attempt += 1
            elapsed = sample.get('active_elapsed_seconds') if isinstance(sample, dict) else None
            timing_source = 'sample_active_elapsed_seconds'
            if elapsed is None and (output / 'baseline.json').exists():
                baseline = ro.load_json(output / 'baseline.json')
                # This is receipt time, not an invented finance snapshot time.
                elapsed = (time.clock_gettime_ns(time.CLOCK_BOOTTIME) - baseline['started_boottime_ns']) / 1e9
                timing_source = 'receipt_boottime_for_unavailable_sample'
            last_sample_elapsed = elapsed
            coverage, classified, marker = classify_safely(coverage, sample, elapsed=elapsed, attempt=attempt)
            if marker is not None or isinstance(sample, dict) and sample.get('record_origin') == 'supervisor_invalid_jsonl_marker':
                if 'invalid_observer_record_or_classification' not in collection_errors:
                    collection_errors.append('invalid_observer_record_or_classification')
            classified.update(sample_wall_ns=sample.get('sample_wall_ns') if isinstance(sample, dict) else None, job_elapsed_seconds=elapsed,
                              timing_source=timing_source)
            fatal = classified['fatal_financial_codes']
            historical_financial_alerts.update(fatal)
            if fatal and not drained and producer.process.poll() is None:
                drained = True
                drain_requested_ns = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
                financial_drain_before_log(producer, fatal, historical_financial_alerts, control / 'safety-events.jsonl')
            append(control / 'sample-classification.jsonl', classified)
        # Close a block only after processing the next snapshot in stream order;
        # a slow sample timestamped in the preceding block must not be discarded.
        live = coverage_report(last_sample_elapsed)
        encoded = ro.canonical(live)
        if encoded != last_coverage_record:
            ro.atomic_json(control / 'live-coverage.json', live)
            last_coverage_record = encoded
        if time.monotonic() - last_budget_check >= 30:
            last_budget_check = time.monotonic()
            ro.atomic_json(control / 'supervisor-heartbeat.json', {'synthetic': True, 'at_wall_ns': time.time_ns(),
                'driver_pid': producer.process.pid, 'driver_birth': producer.birth,
                'driver_running': producer.process.poll() is None, 'samples_classified': attempt,
                'financial_readiness_not_inferred': True})
            size = 0
            for name in ('timeline.jsonl', 'latest.json', 'baseline.json'):
                try:
                    size += (output / name).stat().st_size
                except FileNotFoundError:
                    pass
            if size > OUTPUT_CAP and 'observer_output_budget_exceeded' not in collection_errors:
                collection_errors.append('observer_output_budget_exceeded')
                append(control / 'collection-errors.jsonl', {'synthetic': True,
                    'code': 'observer_output_budget_exceeded', 'at_wall_ns': time.time_ns(),
                    'measured_known_output_bytes': size, 'financial_drain_requested': False})
    try:
        while producer.process.poll() is None:
            try:
                if not observer_start_attempted and (job / 'progress.json').exists():
                    observer_start_attempted = True
                    observer = Pipes(observer_command(plan, scratch, launch), ROOT)
                    ro.atomic_json(control / 'observer-identity.json', observer.identity())
                collect()
                if observer is not None and observer.process.poll() is not None:
                    if 'observer_exited_without_restart' not in collection_errors:
                        collection_errors.append('observer_exited_without_restart')
                        ro.atomic_json(control / 'observer-exit.json', observer.result())
                if stop.is_set() and not drained:
                    drained = True
                    drain_requested_ns = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
                    append(control / 'safety-events.jsonl', {'synthetic': True, 'at_wall_ns': time.time_ns(),
                        'action': 'OPERATOR_STOP_OFFICIAL_DRAIN', 'signal_sent': producer.terminate_owned()})
                if time.clock_gettime_ns(time.CLOCK_BOOTTIME) - producer.started_boottime_ns > (21600 + 600) * 10**9:
                    if not drained:
                        drained = True; producer.terminate_owned()
                        drain_requested_ns = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
                        collection_errors.append('producer_overrun_official_drain_requested')
                if drain_requested_ns is not None and time.clock_gettime_ns(time.CLOCK_BOOTTIME) - drain_requested_ns > 120 * 10**9:
                    if 'official_drain_still_pending_after_120_seconds' not in collection_errors:
                        collection_errors.append('official_drain_still_pending_after_120_seconds')
                        append(control / 'safety-events.jsonl', {'synthetic': True, 'at_wall_ns': time.time_ns(),
                            'action': 'DRAIN_STILL_PENDING_NO_UNSAFE_FORCE_KILL', 'driver_identity': producer.identity()})
            except (OSError, ValueError, KeyError, TypeError, MemoryError, sqlite3.Error, subprocess.SubprocessError) as error:
                if 'supervision_collection_error' not in collection_errors:
                    collection_errors.append('supervision_collection_error')
                try:
                    append(control / 'collection-errors.jsonl', {'synthetic': True, 'at_wall_ns': time.time_ns(),
                        'code': 'supervision_collection_error', 'error_type': type(error).__name__,
                        'error_digest': sha256(str(error).encode()).hexdigest(), 'financial_drain_requested': False})
                except OSError:
                    pass
            time.sleep(.5)
        ro.atomic_json(control / 'producer-result.json', producer.result())
        if observer is not None:
            if not request_observer_stop(observer, output):
                collection_errors.append('readonly_observer_stop_timeout')
            collect()
            if timeline.pending:
                collection_errors.append('observer_jsonl_truncated_at_shutdown')
        before = final_once(plan, scratch, launch, 'final-before-cold.json')
        collect()
        audit = Pipes(observer_command(plan, scratch, launch, audit=True), ROOT)
        try:
            audit.process.wait(timeout=300)
        except subprocess.TimeoutExpired:
            audit.terminate_owned(); raise ValueError('strict_producer_cold_audit_timeout')
        ro.atomic_json(control / 'strict-producer-cold-result.json', audit.result())
        after = final_once(plan, scratch, launch, 'final-after-cold.json', receipt=True)
        collect()
        final = after.get('response') or {}
        progress = ro.load_json(job / 'progress.json')
        duration = progress.get('elapsed_seconds')
        live = coverage_report(duration, final=True)
        expected_faults = {'worker': 180, 'parent': 18}
        actual_faults = progress.get('fault_signals')
        fault_schedule_complete = actual_faults == expected_faults
        ro.atomic_json(control / 'live-coverage.json', live)
        ro.atomic_json(control / 'final-summary.json', {'synthetic': True, 'status': 'COLLECTION_FINISHED',
            'financial_final_evidence_eligible': final.get('final_evidence_eligible') is True,
            'live_coverage': live, 'collection_errors': collection_errors,
            'historical_financial_alert_codes': sorted(historical_financial_alerts),
            'official_driver_drain_requested': drained, 'expected_fault_signals': expected_faults,
            'actual_fault_signals': actual_faults, 'fault_schedule_complete': fault_schedule_complete,
            'overall_engineering_evidence_within_gates': final.get('final_evidence_eligible') is True
                and live['coverage_status'] == 'COMPLETE_WITHIN_COVERAGE_BUDGET' and not collection_errors
                and not historical_financial_alerts and not drained and fault_schedule_complete,
            'known_failed_gate': plan['known_failed_gate'], 'replay_scope': amendment['replay_scope'],
            'no_automatic_resume_or_next_job': True, **ro.FLAGS})
    except (OSError, ValueError, KeyError, TypeError, MemoryError, sqlite3.Error, subprocess.SubprocessError) as error:
        # A supervisor/read/coverage defect is not proof of a financial defect.
        # Keep the original producer collecting; never turn coverage NO_GO into
        # an unrequested interruption or an automatic controller resume.
        ro.atomic_json(control / 'supervisor-failure.json', {'synthetic': True, 'at_wall_ns': time.time_ns(),
            'error_type': type(error).__name__, 'error_digest': sha256(str(error).encode()).hexdigest(),
            'financial_drain_requested': drained, 'original_driver_may_still_run': producer.process.poll() is None,
            'no_resume_attempted': True, **ro.FLAGS})
        return 1
    finally:
        if observer is not None and observer.process.poll() is None:
            request_observer_stop(observer, output)
    return 0


def main(argv=None):
    if not ro.safe_standard_descriptors():
        return 1
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('preflight', 'start', '_supervise'))
    parser.add_argument('--plan', type=Path, default=PLAN)
    parser.add_argument('--amendment', type=Path, default=AMENDMENT)
    parser.add_argument('--scratch', type=Path, default=SCRATCH)
    args = parser.parse_args(argv)
    try:
        if args.operation == '_supervise':
            return supervise(args)
        report = preflight(args)
        if args.operation == 'preflight':
            print(ro.canonical(report)); return 0
        scratch = args.scratch.resolve(); scratch.mkdir(mode=0o700)
        for name in ('control', 'observer'):
            (scratch / name).mkdir(mode=0o700)
        ro.atomic_json(scratch / 'control/preflight.json', report)
        ro.private_write(scratch / 'control/preregistered-plan.json', args.plan.read_bytes())
        ro.private_write(scratch / 'control/observer-amendment.json', args.amendment.read_bytes())
        command = [sys.executable, '-B', str(Path(__file__).resolve()), '_supervise', '--plan', str(args.plan),
            '--amendment', str(args.amendment), '--scratch', str(scratch)]
        process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, close_fds=True, start_new_session=True)
        print(ro.canonical({'synthetic': True, 'status': 'SUPERVISOR_STARTED_PENDING_ACTUAL_DRIVER',
            'supervisor_pid': process.pid, 'supervisor_birth': ro.process_identity(process.pid)['birth'],
            'scratch': str(scratch), 'actual_driver_identity_file': str(scratch / 'control/launch.json'), **ro.FLAGS}))
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        value = {'synthetic': True, 'status': 'PREFLIGHT_FAILED_NOT_STARTED', 'error_type': type(error).__name__,
            'error_digest': sha256(str(error).encode()).hexdigest(), **ro.FLAGS}
        if args.operation == '_supervise':
            value['status'] = 'SUPERVISOR_STARTUP_FAILED'
            try:
                ro.atomic_json(args.scratch / 'control/supervisor-startup-failure.json', value)
            except OSError:
                pass
        print(ro.canonical(value))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
