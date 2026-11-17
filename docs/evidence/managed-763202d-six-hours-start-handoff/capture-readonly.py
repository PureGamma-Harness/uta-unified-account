"""One-off handoff export: JSON and birth-matched proc metadata only; no SQL."""
from pathlib import Path
from hashlib import sha256
from datetime import datetime, timezone
import json
import os
import stat
import time

RUN = Path('/workspace/uta-managed-observer-runs/763202d-six-hours-20261117')
OUT = Path(__file__).resolve().parent
STARTED = time.time_ns()
MANIFEST, VALUES = {}, {}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def write(name, value):
    raw = (canonical(value) + '\n').encode()
    (OUT / name).write_bytes(raw)
    return raw


def capture(name, relative, projection=None):
    descriptor = os.open(RUN / relative, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as stream:
        before = os.fstat(stream.fileno())
        assert stat.S_ISREG(before.st_mode)
        raw = stream.read(64 * 1024**2 + 1)
        after = os.fstat(stream.fileno())
    assert len(raw) <= 64 * 1024**2
    value = json.loads(raw)
    value = value if projection is None else projection(value)
    exported = write(name, value)
    MANIFEST[name] = {'source_allowlist': relative, 'source_sha256': sha256(raw).hexdigest(),
        'source_bytes': len(raw), 'source_mtime_ns': before.st_mtime_ns,
        'source_open_object_stable': (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns),
        'projection_applied': projection is not None, 'export_bytes': len(exported),
        'export_sha256': sha256(exported).hexdigest()}
    VALUES[name] = value
    return value


def identity(pid, birth):
    assert pid not in {4471, 8784}
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        matches = fields[19] == str(birth)
        value = {'pid': pid, 'expected_birth': str(birth), 'observed_birth': fields[19],
            'birth_matches': matches, 'state': fields[0], 'parent_pid': int(fields[1]),
            'alive_observed': matches and fields[0] not in ('Z', 'X', 'x')}
        if matches:
            value['cpu_affinity'] = sorted(os.sched_getaffinity(pid))
        return value
    except (OSError, IndexError, ValueError) as error:
        return {'pid': pid, 'expected_birth': str(birth), 'visibility': 'unknown_or_absent',
            'metadata_error_type': type(error).__name__}


def progress_projection(value):
    value = dict(value)
    error = value.pop('error', None)
    value['error_present'] = error is not None
    value['error_sha256'] = None if error is None else sha256(canonical(error).encode()).hexdigest()
    return value


capture('actual-preflight.json', 'control/preflight.json')
PLAN_KEYS = ('status', 'scope', 'source_commit', 'source_root', 'observer_core_commit',
    'reviewed_observer_and_wrapper_commit', 'python', 'validation_report', 'qualification', 'producer',
    'observer', 'financial_gates', 'reporting', 'known_failed_gate', 'production_approved',
    'capacity_10000_approved', 'financial_6h_passed', 'live_coverage_passed')
capture('original-plan-gates.json', 'control/preregistered-plan.json',
        lambda value: {key: value[key] for key in PLAN_KEYS})
amendment = capture('observer-amendment.json', 'control/observer-amendment.json')
launch = capture('actual-launch.json', 'control/launch.json')
supervisor = capture('supervisor-identity.json', 'control/supervisor-identity.json')
monitor = capture('observer-monitor-identity.json', 'control/observer-identity.json')
cli = capture('observer-cli-identity.json', 'observer/watch-cli-identity.json')
capture('supervisor-heartbeat.snapshot.json', 'control/supervisor-heartbeat.json')
initial = capture('initial-handoff.original.json', 'control/initial-handoff.json')
coverage = capture('live-coverage.snapshot.json', 'control/live-coverage.json')
latest = capture('observer-latest.snapshot.json', 'observer/latest.json')
baseline = capture('observer-baseline.json', 'observer/baseline.json')
progress = capture('producer-progress.snapshot.json', 'job/progress.json', progress_projection)
identities = {'supervisor': identity(supervisor['pid'], supervisor['birth']),
    'original_driver': identity(launch['driver_pid'], launch['driver_birth']),
    'observer_monitor': identity(monitor['pid'], monitor['birth']),
    'observer_actual_cli': identity(cli['pid'], cli['birth'])}
parent = supervisor['pid']
drain = {'scope': 'birth-matched new-job PID metadata; no stream contents opened',
    'queued_pipe_bytes': None, 'raw_stream_contents_archived': False,
    'supervisor_read_fds_by_pipe': {}, 'child_streams': {}, 'supervisor_thread_waits': [],
    'direct_child_list': None}
if identities['supervisor'].get('birth_matches'):
    for entry in Path(f'/proc/{parent}/fd').iterdir():
        try:
            link = os.readlink(entry)
            if not link.startswith('pipe:['):
                continue
            fields = Path(f'/proc/{parent}/fdinfo/{entry.name}').read_text().splitlines()
            flags = next(row.split()[1] for row in fields if row.startswith('flags:'))
            if int(flags, 8) & os.O_ACCMODE == os.O_RDONLY:
                drain['supervisor_read_fds_by_pipe'].setdefault(link, []).append(int(entry.name))
        except (OSError, StopIteration):
            pass
    for task in Path(f'/proc/{parent}/task').iterdir():
        try:
            channel = (task / 'wchan').read_text().strip()
            known = channel if channel in {'pipe_read', 'anon_pipe_read', 'hrtimer_nanosleep',
                'do_nanosleep', 'futex_wait_queue', 'futex_wait_queue_me'} else 'other_or_unavailable'
            drain['supervisor_thread_waits'].append({'tid': int(task.name), 'wait_channel': known})
        except OSError:
            pass
    try:
        drain['direct_child_list'] = [int(value) for value in
            Path(f'/proc/{parent}/task/{parent}/children').read_text().split()]
        drain['direct_child_list_visibility'] = 'available'
    except OSError as error:
        drain['direct_child_list_visibility'] = 'unavailable'
        drain['direct_child_list_error_type'] = type(error).__name__
    for label in ('original_driver', 'observer_monitor', 'observer_actual_cli'):
        row = identities[label]
        if not row.get('birth_matches'):
            continue
        streams = {}
        for descriptor in (1, 2):
            try:
                link = os.readlink(f"/proc/{row['pid']}/fd/{descriptor}")
                streams[str(descriptor)] = {'pipe': link if link.startswith('pipe:[') else 'nonpipe_redacted',
                    'matched_supervisor_read_fds': drain['supervisor_read_fds_by_pipe'].get(link, [])}
            except OSError as error:
                streams[str(descriptor)] = {'visibility': 'unknown', 'metadata_error_type': type(error).__name__}
        drain['child_streams'][label] = streams
drain['observed_supervisor_threads'] = len(drain['supervisor_thread_waits'])
drain['observed_pipe_wait_threads'] = sum(row['wait_channel'] in {'pipe_read', 'anon_pipe_read'}
    for row in drain['supervisor_thread_waits'])
drain['expected_driver_and_observer_pipe_read_ends_present'] = all(
    drain['child_streams'].get(label, {}).get(str(descriptor), {}).get('matched_supervisor_read_fds')
    for label in ('original_driver', 'observer_actual_cli') for descriptor in (1, 2))
drain['scope_limit'] = ('Matched read descriptors/kernel waits support current bounded draining; '
    'queued bytes/cumulative drain totals/future operation are not measured.')
proc = {'synthetic': True, 'captured_wall_ns': time.time_ns(), 'identities': identities,
    'pipe_drain_metadata': drain, 'protected_old_pids_not_read': True,
    'no_cmdline_environment_or_private_stream_data_read': True, 'financial_readiness_inferred_from_proc': False}
raw = write('matching-pid-pipe-metadata.json', proc)
MANIFEST['matching-pid-pipe-metadata.json'] = {'export_bytes': len(raw),
    'export_sha256': sha256(raw).hexdigest(), 'source': 'allowlisted birth-matched /proc metadata'}
ended = time.time_ns()
utc = lambda value: datetime.fromtimestamp(value / 1e9, timezone.utc).isoformat()
summary = {'synthetic': True, 'redacted': True,
    'archive_base_commit': 'ce3045f66456c1592858d0297f90a9552c7500dd',
    'active_root_not_modified': '/workspace/uta-managed-observer',
    'source_commit': '763202df9cb3ce089721e5281371aff3eab58089',
    'capture_started_utc': utc(STARTED), 'capture_ended_utc': utc(ended),
    'capture_is_multiple_json_publication_points_not_financial_SQL_snapshot': True,
    'actual_driver_launch_utc': utc(launch['launched_wall_ns']),
    'original_started_boottime_ns': baseline['started_boottime_ns'],
    'original_deadline_boottime_ns': baseline['deadline_boottime_ns'],
    'initial_recorded_start_utc_mapping': initial['start_utc_clock_mapping'],
    'initial_recorded_deadline_utc_mapping': initial['deadline_utc_clock_mapping'],
    'deadline_is_not_actual_completion': True, 'producer_reported_status': progress['status'],
    'producer_reported_active_seconds': progress.get('elapsed_seconds'),
    'producer_reported_rounds': progress.get('rounds'),
    'producer_reported_fault_signals': progress.get('fault_signals'),
    'producer_logs_verified': progress.get('logs_verified'),
    'financial_final_status': 'PENDING_NOT_COMPLETE' if progress['status'] == 'running' else 'REQUIRES_REVIEW',
    'independent_current_financial_golden': latest.get('finance', {}).get('golden'),
    'latest_observer_logical_point': latest.get('logical_point'),
    'latest_observer_read_error_type': latest.get('error_type'),
    'live_coverage_status': coverage['coverage_status'], 'coverage_no_go_reasons': coverage['coverage_no_go_reasons'],
    'samples_observed': coverage['samples_observed'], 'coverage_counts': coverage['counts'],
    'maximum_consecutive_technical_read_unknown': coverage['maximum_observed_consecutive_technical_read_unknown'],
    'read_error_cause': 'unknown_unless_separately_evidenced', 'replay_scope': amendment['replay_scope'],
    'known_failed_large_history_gate': VALUES['original-plan-gates.json']['known_failed_gate'],
    'all_new_job_births_match': all(row.get('birth_matches') for row in identities.values()),
    'all_new_job_processes_alive_observed': all(row.get('alive_observed') for row in identities.values()),
    'pipe_read_end_matches': bool(drain['expected_driver_and_observer_pipe_read_ends_present']),
    'observed_pipe_wait_threads': drain['observed_pipe_wait_threads'],
    'child_list_visibility': drain.get('direct_child_list_visibility'), 'queued_stream_bytes': None,
    'no_SQL_no_new_observer_sample_no_control_write': True, 'no_restart_resume_stop_or_new_job': True,
    'private_auth_TLS_nonce_clone_not_archived': True, 'production_approved': False,
    'capacity_10000_per_s_passed': False, 'continuous_6h_stability_passed': False,
    'continuous_24h_stability_passed': False}
raw = write('summary.json', summary)
MANIFEST['summary.json'] = {'export_bytes': len(raw), 'export_sha256': sha256(raw).hexdigest()}
write('manifest.json', {'synthetic': True, 'redacted': True, 'allowlist_only': True,
    'source_read_only': True, 'capture_started_wall_ns': STARTED, 'capture_ended_wall_ns': ended,
    'artifacts': MANIFEST})
print(canonical(summary))
