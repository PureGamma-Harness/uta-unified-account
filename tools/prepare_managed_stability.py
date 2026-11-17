"""Prepare explicit target recipes; execution needs complete QA and exact root GO.

Default CLI only reads JSON/git/filesystem metadata. It never imports a SQLite
module, starts a producer, creates a job, or invokes a frozen operational CLI.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import importlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

FLAGS = dict(continuous_6h_stability_passed=False, continuous_24h_stability_passed=False,
             capacity_10000_per_s_passed=False, production_approved=False)
PHASES = ('smoke-produce', 'smoke-observe', 'smoke-cold', 'smoke-strict-negative',
          'long-preflight', 'long-start')


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


def cohost_budget(new_reservation, *, observer_floor=256 * 1024**2):
    """Metadata only; capture time never substitutes for producer freshness."""
    root = Path('/workspace/uta-soak-runs/formal-20261116T213613Z-88755a9')
    meta_path, progress_path = root / 'job.json', root / 'progress.json'
    meta = load(meta_path)
    before = progress_path.stat()
    progress = load(progress_path)
    after = progress_path.stat()
    stable = (before.st_dev, before.st_ino, before.st_mtime_ns, before.st_size) == (
        after.st_dev, after.st_ino, after.st_mtime_ns, after.st_size)
    maximum = meta['configuration']['max_directory_bytes']
    current = progress.get('directory_bytes')
    if type(maximum) is not int or type(current) is not int or not 0 <= current <= maximum:
        raise ValueError('old_job_budget_metadata_unknown')
    observed_ns = time.time_ns()
    free = shutil.disk_usage(root).free
    # Reserve the whole old limit, covering the reported remaining lower bound
    # even if ephemeral files disappear or the separately published report ages.
    required = new_reservation + maximum + observer_floor
    return dict(capture_wall_ns=observed_ns, old_job_json_sha256=fingerprint(meta_path),
        old_max_directory_bytes=maximum, producer_reported_directory_bytes=current,
        old_reported_remaining_lower_bound_bytes=maximum-current,
        old_future_reservation_bytes=maximum, producer_progress_mtime_ns=before.st_mtime_ns,
        producer_progress_read_stable=stable,
        producer_progress_age_seconds=(observed_ns-before.st_mtime_ns)/1e9 if stable else None,
        producer_reported_observed_ns=progress.get('observed_ns'),
        producer_reported_heartbeat_age_seconds=progress.get('heartbeat_age_seconds'),
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
    reserve = plan['producer']['source_budget_bytes'] + 6 * 1024**3 + plan['observer']['max_private_clone_bytes'] + plan['observer']['clone_headroom_bytes']
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
                  source_bytes=plan['producer']['source_budget_bytes'], observer_bytes=6 * 1024**3,
                  private_clone_admission_estimate_bytes=plan['observer']['max_private_clone_bytes'],
                  actual_private_clone_peak_hard_quota_enforced=False,
                  headroom_bytes=1024**3, reservation_created=False, must_recheck_actual_preflight=True),
        cohost=cohost_budget(reserve),
        source_job_sql_executed=False, service_started=False, execution_authorized=False, **FLAGS)


def _original_smoke_drain(value):
    launch = Path(value['smoke_scratch']) / 'observer/launch.json'
    if not launch.exists():
        return False
    identity = load(launch)
    pid, birth = identity['driver_pid'], identity['driver_birth']
    if pid in {4471, 8784}:
        raise ValueError('protected_old_process')
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
    except FileNotFoundError:
        return False
    if fields[19] == str(birth) and fields[0] not in {'Z', 'X', 'x'}:
        os.kill(pid, signal.SIGTERM)
        return True
    return False


def invoke(path, phase, root_go, *, record='observation-001.json'):
    """Only call after root's phase-specific GO; never an automatic sequence."""
    value = profile(path)
    authorized(value, path, root_go)  # Before imports, child start or directory creation.
    if phase not in PHASES:
        raise ValueError('unsupported_reviewed_phase')
    source = Path(value['source_root'])
    if subprocess.check_output(['git', '--no-optional-locks', 'rev-parse', 'HEAD'], cwd=source, text=True).strip() != value['source_commit']:
        raise ValueError('frozen_source_commit_changed')
    if subprocess.check_output(['git', '--no-optional-locks', 'status', '--porcelain', '--untracked-files=all'], cwd=source):
        raise ValueError('frozen_source_dirty')
    if phase in PHASES:
        plan = load(value['plan'])
        clone_limit = plan['observer']['max_private_clone_bytes'] if phase.startswith('long-') else 256 * 1024**2
        reserve = plan['producer']['source_budget_bytes'] + 6 * 1024**3 + clone_limit + plan['observer']['clone_headroom_bytes']
        budget = cohost_budget(reserve)
        if value.get('resource_review', {}).get('old_observer_floor_approved') is not True:
            raise ValueError('unbounded_old_observer_floor_not_independently_reviewed')
        if budget['additional_free_bytes_required']:
            raise ValueError('combined_new_and_old_reservation_unavailable')
    os.umask(0o077)
    os.sched_setaffinity(0, {0})  # Only this new wrapper and its future children.
    timeout = 120 if phase == 'smoke-produce' else 45 if phase.startswith('smoke-') else 60
    smoke = Path(value['smoke_scratch'])
    if phase == 'smoke-produce':
        smoke.mkdir(mode=0o700)
        for name in ('control', 'observer', 'audit'):
            (smoke / name).mkdir(mode=0o700)
        budget = dict(boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
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
            _original_smoke_drain(value)
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
