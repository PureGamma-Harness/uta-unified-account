"""Prepare explicit target recipes; execution needs complete QA and exact root GO.

Default CLI only reads JSON/git/filesystem metadata. It never imports a SQLite
module, starts a producer, creates a job, or invokes a frozen operational CLI.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import importlib
import json
import math
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import sys
import time

try:
    from tools.managed_output_budget import explicit_output_budget, output_budget_bytes
except ModuleNotFoundError:
    from managed_output_budget import explicit_output_budget, output_budget_bytes

FLAGS = dict(continuous_6h_stability_passed=False, continuous_24h_stability_passed=False,
             capacity_10000_per_s_passed=False, production_approved=False)
PHASES = ('smoke-produce', 'smoke-observe', 'smoke-cold', 'smoke-strict-negative',
          'long-preflight', 'long-start')
COHOST_JOB = Path('/workspace/uta-soak-runs/formal-20261116T213613Z-88755a9')
COHOST_SOURCE = '88755a9f2ba3bb672ca5d354b3037796f00c6611'
COHOST_BOOT = '6339d4fc-a9e7-4c10-a591-1e70a14322ff'
COHOST_PRODUCER = (4471, '210004')
COHOST_OBSERVER = (8784, '412799')
PROC_ROOT = Path('/proc')
LIVE_STATES = {'R', 'S', 'D', 'T', 't', 'K', 'W', 'P', 'I'}


def load(path):
    return json.loads(Path(path).read_text())


def fingerprint(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def profile(path):
    value = load(path)
    required = {'source_root', 'source_commit', 'python', 'validation_report', 'plan', 'amendment',
                'plan_sha256', 'amendment_sha256', 'smoke_scratch', 'long_scratch', 'qualification'}
    if not required <= value.keys() or len(value['source_commit']) != 40:
        raise ValueError('explicit_complete_new_target_profile_required')
    if value['source_commit'] == '763202df9cb3ce089721e5281371aff3eab58089':
        raise ValueError('old_stopped_attempt_is_not_a_new_target')
    for name in ('source_root', 'python', 'validation_report', 'plan', 'amendment', 'smoke_scratch', 'long_scratch'):
        if not Path(value[name]).is_absolute():
            raise ValueError('explicit_absolute_target_paths_required')
    source = Path(value['source_root']).resolve()
    targets = [Path(value[key]).resolve() for key in ('smoke_scratch', 'long_scratch')]
    if any(path == source or path.is_relative_to(source) for path in targets) or targets[0] == targets[1]:
        raise ValueError('new_separate_external_scratch_targets_required')
    plan, amendment = load(value['plan']), load(value['amendment'])
    output_budget_bytes(plan)
    if (fingerprint(value['plan']) != value['plan_sha256']
            or fingerprint(value['amendment']) != value['amendment_sha256']
            or amendment['original_plan_sha256'] != value['plan_sha256']):
        raise ValueError('immutable_preregistration_hash_changed')
    if any(plan[key] != value[key] for key in ('source_root', 'source_commit', 'python', 'validation_report')):
        raise ValueError('plan_and_explicit_target_disagree')
    expected = (plan['producer']['duration_seconds'], plan['producer']['rate_rounds_per_second'],
        plan['producer']['planned_rounds'], plan['producer']['worker_fault_every_rounds'],
        plan['producer']['parent_fault_every_rounds'], amendment['observer_interval_seconds_effective'])
    if expected != (21600, .25, 5400, 30, 300, 61):
        raise ValueError('supported_frozen_supervisor_contract_required')
    if (plan['observer']['blocks'], plan['observer']['technical_read_unknown_budget'],
            plan['observer']['maximum_consecutive_technical_read_unknown']) != (12, 3, 1):
        raise ValueError('original_live_coverage_gates_changed')
    return value


def commands(value, *, record='observation-001.json'):
    if Path(record).name != record or not record.endswith('.json'):
        raise ValueError('fresh_single_record_name_required')
    source, py = Path(value['source_root']), value['python']
    smoke = Path(value['smoke_scratch'])
    common = [py, '-B', str(source / 'tools/managed_observer_smoke.py')]
    target = ['--source', str(source), '--commit', value['source_commit'], '--report', value['validation_report'],
              '--job', str(smoke / 'job'), '--output', str(smoke / 'observer')]
    long_target = ['--plan', value['plan'], '--amendment', value['amendment'], '--scratch', value['long_scratch']]
    return {
        'smoke-produce': common + ['produce-60', *target, '--record', 'producer.json'],
        'smoke-observe': common + ['observe-once', *target, '--record', record],
        'smoke-cold': common + ['short-cold', *target, '--audit-output', str(smoke / 'audit')],
        'smoke-strict-negative': common + ['long-gate', *target, '--record', 'strict-long-negative.json'],
        'long-preflight': [py, '-B', str(source / 'tools/run_managed_long.py'), 'preflight', *long_target],
        'long-start': [py, '-B', str(source / 'tools/run_managed_long.py'), 'start', *long_target],
    }


def authorized(value, path, root_go):
    qa = value['qualification']
    if (qa.get('status') != 'COMPLETE_ALL_GATES_PASSED' or qa.get('blocked_reason') is not None
            or any(qa.get(key) is not True for key in ('all_three_local_passed', 'all_eight_ci_passed',
                                                       'independent_new_package_passed'))):
        raise ValueError('full_exact_source_qualification_not_complete')
    if root_go != fingerprint(path):
        raise ValueError('separate_root_GO_must_bind_exact_reviewed_profile')


def _stable_metadata(path):
    try:
        before = path.stat(follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode) or before.st_uid != os.geteuid():
            raise ValueError('cohost_metadata_not_owned_regular_file')
        raw = path.read_bytes()
        after = path.stat(follow_symlinks=False)
        if ((before.st_dev, before.st_ino, before.st_mtime_ns, before.st_ctime_ns, before.st_size, before.st_uid, before.st_mode)
                != (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_ctime_ns, after.st_size, after.st_uid, after.st_mode)):
            raise ValueError('cohost_metadata_changed_during_read')
        def unique_pairs(items):
            value = {}
            for key, item in items:
                if key in value:
                    raise ValueError('cohost_duplicate_metadata_key')
                value[key] = item
            return value
        value = json.loads(raw, object_pairs_hook=unique_pairs)
        if type(value) is not dict or type(before.st_mtime_ns) is not int:
            raise ValueError('cohost_metadata_type_unknown')
        return value, before.st_mtime_ns, sha256(raw).hexdigest()
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError('cohost_metadata_unavailable') from error


def _parse_proc_stat(raw, pid):
    try:
        actual_pid = int(raw.split(' ', 1)[0])
        fields = raw.rsplit(')', 1)[1].split()
        state, birth = fields[0], fields[19]
        if actual_pid != pid or not birth.isdecimal() or int(birth) <= 0:
            raise ValueError()
        return state, birth
    except (ValueError, IndexError):
        raise ValueError('process_identity_unknown') from None


def _process_metadata(pid, *, proc=Path('/proc')):
    try:
        root = proc / str(pid)
        before = _parse_proc_stat((root / 'stat').read_text(), pid)
        status = (root / 'status').read_text()
        uid_lines = [line.split()[1:] for line in status.splitlines() if line.startswith('Uid:')]
        if len(uid_lines) != 1 or len(uid_lines[0]) != 4 or any(not value.isdecimal() for value in uid_lines[0]):
            raise ValueError('process_uid_unknown')
        uids = [int(value) for value in uid_lines[0]]
        after = _parse_proc_stat((root / 'stat').read_text(), pid)
        if before[1] != after[1] or before[0] not in LIVE_STATES or after[0] not in LIVE_STATES:
            raise ValueError('process_stopped_or_changed')
        return dict(pid=pid, birth=after[1], state=after[0], uids=uids)
    except OSError as error:
        raise ValueError('process_metadata_unavailable') from error


def cohost_budget(new_reservation, *, observer_floor=256 * 1024**2,
                  _job_root=None, _proc_root=None, _now_ns=None, _free_bytes=None):
    """Metadata only; capture time never substitutes for producer freshness."""
    root = COHOST_JOB if _job_root is None else _job_root
    _proc_root = PROC_ROOT if _proc_root is None else _proc_root
    if type(new_reservation) is not int or new_reservation <= 0 or type(observer_floor) is not int or observer_floor <= 0:
        raise ValueError('cohost_reservation_type_unknown')
    meta_path, progress_path = root / 'job.json', root / 'progress.json'
    meta, meta_mtime, meta_hash = _stable_metadata(meta_path)
    progress, progress_mtime, _ = _stable_metadata(progress_path)
    if (type(meta.get('environment')) is not dict or type(meta.get('configuration')) is not dict
            or meta['environment'].get('commit') != COHOST_SOURCE
            or progress.get('source_commit') != COHOST_SOURCE):
        raise ValueError('cohost_original_source_changed_or_unknown')
    configuration = meta.get('configuration', {})
    maximum, interval = configuration.get('max_directory_bytes'), configuration.get('heartbeat_interval')
    if (type(maximum) is not int or maximum != 6 * 1024**3
            or type(interval) not in {int, float} or interval != 5):
        raise ValueError('cohost_original_budget_or_cadence_changed')
    if (progress.get('status') != 'running' or progress.get('stored_status') != 'running'
            or progress.get('process_alive') is not True):
        raise ValueError('cohost_terminal_or_nonrunning_requires_new_policy')
    current = progress.get('directory_bytes')
    if type(maximum) is not int or type(current) is not int or not 0 <= current <= maximum:
        raise ValueError('old_job_budget_metadata_unknown')
    observed_ns = time.time_ns() if _now_ns is None else _now_ns
    original_observed = progress.get('observed_ns')
    heartbeat = progress.get('heartbeat_age_seconds')
    if (type(observed_ns) is not int or type(original_observed) is not int
            or not 0 < original_observed <= 2**63-1 or not 0 < observed_ns <= 2**63-1
            or meta_mtime <= 0 or progress_mtime <= 0 or type(heartbeat) not in {int, float}
            or not math.isfinite(heartbeat) or heartbeat < 0):
        raise ValueError('cohost_clock_or_heartbeat_type_unknown')
    try:
        boot = (_proc_root / 'sys/kernel/random/boot_id').read_text().strip()
    except OSError as error:
        raise ValueError('cohost_boot_unknown') from error
    if boot != COHOST_BOOT:
        raise ValueError('cohost_original_boot_changed')
    identities = []
    for pid, birth in (COHOST_PRODUCER, COHOST_OBSERVER):
        identity = _process_metadata(pid, proc=_proc_root)
        if (identity['birth'] != birth or identity['state'] not in {'R', 'S', 'D', 'I'}
                or any(uid != os.geteuid() for uid in identity['uids'])):
            raise ValueError('cohost_process_birth_or_uid_changed')
        identities.append(identity)
    free = shutil.disk_usage(root).free if _free_bytes is None else _free_bytes
    if type(free) is not int or free < 0:
        raise ValueError('cohost_free_space_unknown')
    observed_ns = time.time_ns() if _now_ns is None else _now_ns
    report_age = (observed_ns-original_observed)/1e9
    file_age = (observed_ns-progress_mtime)/1e9
    maximum_age = 3 * interval
    if report_age < 0 or file_age < 0 or meta_mtime > observed_ns:
        raise ValueError('cohost_future_observed_or_file_clock')
    if report_age > maximum_age or file_age > maximum_age or abs(progress_mtime-original_observed)/1e9 > maximum_age:
        raise ValueError('cohost_producer_report_stale_or_clock_skewed')
    effective_heartbeat = heartbeat + report_age
    if effective_heartbeat > maximum_age:
        raise ValueError('cohost_effective_heartbeat_stale')
    # Reserve the whole old limit, covering the reported remaining lower bound
    # even if ephemeral files disappear or the separately published report ages.
    required = new_reservation + maximum + observer_floor
    return dict(capture_wall_ns=observed_ns, old_job_json_sha256=meta_hash,
        old_max_directory_bytes=maximum, producer_reported_directory_bytes=current,
        old_reported_remaining_lower_bound_bytes=maximum-current,
        old_future_reservation_bytes=maximum, producer_progress_mtime_ns=progress_mtime,
        producer_progress_read_stable=True, producer_progress_age_seconds=file_age,
        producer_reported_observed_ns=original_observed, producer_reported_heartbeat_age_seconds=heartbeat,
        effective_heartbeat_age_seconds=effective_heartbeat, maximum_metadata_age_seconds=maximum_age,
        metadata_process_gate_passed=True, cohost_processes=identities, original_boot_verified=True,
        producer_freshness_inferred_from_capture_timestamp=False,
        old_observer_declared_byte_cap=None, old_observer_additional_floor_bytes=observer_floor,
        observer_floor_is_hard_cap=False, observer_floor_operator_review_required=True,
        required_combined_bytes=required, observed_free_bytes=free,
        additional_free_bytes_required=max(0, required-free),
        resource_admission='NO_GO_PENDING_RESOURCE_REVIEW_AND_RECHECK')


def prepare(path):
    value = profile(path)
    source = Path(value['source_root'])
    head = subprocess.check_output(['git', '--no-optional-locks', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
    if head != value['source_commit']:
        raise ValueError('frozen_source_commit_changed')
    report_path = Path(value['validation_report'])
    report = load(report_path) if report_path.exists() else None
    if report is not None and report.get('code_commit') != value['source_commit']:
        raise ValueError('report_is_not_the_explicit_new_source')
    observed = None if report is None else {key: report.get(key) for key in
        ('code_commit', 'tests_run', 'failures', 'errors', 'skipped', 'passed')}
    plan = load(value['plan'])
    output_budget = output_budget_bytes(plan)
    reserve = plan['producer']['source_budget_bytes'] + output_budget + plan['observer']['max_private_clone_bytes'] + plan['observer']['clone_headroom_bytes']
    return dict(status='PREP_ONLY_NO_EXECUTION', prepared_at_utc=datetime.now(timezone.utc).isoformat(),
        profile_sha256=fingerprint(path), source_commit=head, qualification=value['qualification'],
        matching_312_report_observed=observed, observed_report_sha256=fingerprint(report_path) if report else None,
        commands=commands(value), selected_cpu=0, old_job_affinity_changed=False,
        smoke=dict(duration_seconds=60, planned_rounds=15, worker_every=5, parent_every=10,
                   outer_budget_seconds=150, startup_normal_fault_observations_required=True,
                   absent_phase_means_incomplete=True, strict_long_receipt_must_be_refused=True),
        long=dict(duration_seconds=21600, planned_rounds=5400, worker_every=30, parent_every=300,
                  actual_supported_cli_interval=61, financial_and_live_coverage_separate=True),
        disk=dict(observed_free_bytes=shutil.disk_usage(Path(value['long_scratch']).parent).free,
                  long_conservative_required_bytes=reserve,
                  source_bytes=plan['producer']['source_budget_bytes'], observer_bytes=output_budget,
                  observer_measurement_scope=('control_and_observer_except_validated_private_clones'
                    if explicit_output_budget(plan) else 'historical_timeline_latest_baseline_only'),
                  observer_output_physical_hard_quota_enforced=False,
                  private_clone_admission_estimate_bytes=plan['observer']['max_private_clone_bytes'],
                  actual_private_clone_peak_hard_quota_enforced=False,
                  headroom_bytes=plan['observer']['clone_headroom_bytes'], reservation_created=False, must_recheck_actual_preflight=True),
        cohost=cohost_budget(reserve),
        source_job_sql_executed=False, service_started=False, execution_authorized=False, **FLAGS)


def _pidfd_term(identity, *, proc=Path('/proc')):
    """Bind kernel identity before proc validation; never fall back to PID kill."""
    pid, birth, boot, uid = (identity.get(key) for key in ('pid', 'birth', 'boot', 'uid'))
    if (type(pid) is not int or pid <= 0 or pid in {4471, 8784} or type(birth) is not str
            or not birth.isdecimal() or int(birth) <= 0 or type(boot) is not str or not boot
            or type(uid) is not int or uid < 0 or not hasattr(os, 'pidfd_open')
            or not hasattr(signal, 'pidfd_send_signal')):
        return False
    descriptor = None
    try:
        descriptor = os.pidfd_open(pid, 0)
        if (proc / 'sys/kernel/random/boot_id').read_text().strip() != boot:
            return False
        current = _process_metadata(pid, proc=proc)
        if current['birth'] != birth or any(value != uid for value in current['uids']):
            return False
        signal.pidfd_send_signal(descriptor, signal.SIGTERM, None, 0)
        return True
    except (OSError, ValueError):
        return False
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _original_smoke_drain(value, *, approved_profile_sha256):
    if (type(approved_profile_sha256) is not str or len(approved_profile_sha256) != 64
            or any(character not in '0123456789abcdef' for character in approved_profile_sha256)):
        return False
    launch = Path(value['smoke_scratch']) / 'observer/launch.json'
    control = Path(value['smoke_scratch']) / 'control/outer-budget.json'
    if not launch.exists() or not control.exists():
        return False
    try:
        identity, _, _ = _stable_metadata(launch)
        expected, _, _ = _stable_metadata(control)
        if (expected.get('profile_sha256') != approved_profile_sha256
                or expected.get('source_commit') != value['source_commit']):
            return False
    except (OSError, ValueError, KeyError, TypeError):
        return False
    return _pidfd_term(dict(pid=identity.get('driver_pid'), birth=identity.get('driver_birth'),
                            boot=expected.get('boot'), uid=expected.get('owner_uid')))


def invoke(path, phase, root_go, *, record='observation-001.json'):
    """Only call after root's phase-specific GO; never an automatic sequence."""
    value = profile(path)
    authorized(value, path, root_go)  # Before imports, child start or directory creation.
    if phase not in PHASES:
        raise ValueError('unsupported_reviewed_phase')
    source = Path(value['source_root'])
    if phase in PHASES:
        plan = load(value['plan'])
        clone_limit = plan['observer']['max_private_clone_bytes'] if phase.startswith('long-') else 256 * 1024**2
        reserve = plan['producer']['source_budget_bytes'] + output_budget_bytes(plan) + clone_limit + plan['observer']['clone_headroom_bytes']
        budget = cohost_budget(reserve)
        if value.get('resource_review', {}).get('old_observer_floor_approved') is not True:
            raise ValueError('unbounded_old_observer_floor_not_independently_reviewed')
        if budget['additional_free_bytes_required']:
            raise ValueError('combined_new_and_old_reservation_unavailable')
    if subprocess.check_output(['git', '--no-optional-locks', 'rev-parse', 'HEAD'], cwd=source, text=True).strip() != value['source_commit']:
        raise ValueError('frozen_source_commit_changed')
    if subprocess.check_output(['git', '--no-optional-locks', 'status', '--porcelain', '--untracked-files=all'], cwd=source):
        raise ValueError('frozen_source_dirty')
    os.umask(0o077)
    os.sched_setaffinity(0, {0})  # Only this new wrapper and its future children.
    timeout = 120 if phase == 'smoke-produce' else 45 if phase.startswith('smoke-') else 60
    smoke = Path(value['smoke_scratch'])
    if phase == 'smoke-produce':
        smoke.mkdir(mode=0o700)
        for name in ('control', 'observer', 'audit'):
            (smoke / name).mkdir(mode=0o700)
        budget = dict(boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                      owner_uid=os.geteuid(), source_commit=value['source_commit'], profile_sha256=fingerprint(path),
                      deadline_boottime_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME) + 150_000_000_000)
        (smoke / 'control/outer-budget.json').write_text(json.dumps(budget))
    if phase.startswith('smoke-'):
        budget = load(smoke / 'control/outer-budget.json')
        remaining = (budget['deadline_boottime_ns'] - time.clock_gettime_ns(time.CLOCK_BOOTTIME)) / 1e9
        if budget['boot'] != Path('/proc/sys/kernel/random/boot_id').read_text().strip() or remaining <= 1:
            raise ValueError('smoke_outer_budget_exhausted_or_boot_changed')
        timeout = min(timeout, remaining - 1)
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(source))
    transport = importlib.import_module('tools.run_managed_long')
    if (Path(transport.__file__).resolve() != source / 'tools/run_managed_long.py'
            or Path(transport.ro.__file__).resolve() != source / 'tools/managed_soak_observer.py'):
        raise ValueError('cached_transport_is_not_the_exact_new_frozen_source')
    child = transport.Pipes(commands(value, record=record)[phase], source)
    try:
        child.process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        if phase.startswith('smoke-'):
            _original_smoke_drain(value, approved_profile_sha256=fingerprint(path))
        child.terminate_owned()
        try:
            child.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            if transport.ro.process_identity(child.process.pid, child.birth)['alive']:
                child.process.kill()
            child.process.wait(timeout=2)
        raise ValueError('owned_cli_timeout_unknown_do_not_repeat_start')
    receipt = child.result()
    if not receipt['stdout_complete']:
        raise ValueError('bounded_public_stdout_incomplete')
    raw = child.results['stdout']['raw']
    receipt['structured_stdout'] = json.loads(raw) if raw else None
    receipt['phase'] = phase
    return receipt  # Unknown stderr is only a digest in the frozen PIPE transport.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--invoke', choices=PHASES)
    parser.add_argument('--root-go-profile-sha256')
    parser.add_argument('--record', default='observation-001.json')
    args = parser.parse_args()
    value = (invoke(args.profile, args.invoke, args.root_go_profile_sha256, record=args.record)
             if args.invoke else prepare(args.profile))
    print(json.dumps(value, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
