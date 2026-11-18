"""Root-authorized one actual c076 synthetic adapter; preserve every first fact."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import resource
import stat
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
SOURCE = 'c076b0dc1feb765686de9c78683a4e4bea5429e2'
HEAD = 'c146dc94749ea1bb06474bbb4358b745dfe59ea6'
PARENT = Path('/workspace/uta-observer-v2-adapter-runs')
OUTPUT = PARENT / 'read1-c076b0d-once02'
EVIDENCE = ROOT / 'evidence/observer-compact-report-v2/adapter-second-once02'
ARGV = ['taskset', '-c', '1', 'timeout', '--signal=KILL', '10s', 'python', '-B',
        'tools/probe_observer_v2_adapters.py', '--execute-synthetic-adapters', '--new-output', str(OUTPUT)]
INPUTS = {
    'tools/probe_observer_v2_adapters.py': '4624f4cd5181d5ef526f60cb6c2b126421eace16741537d7a021775397a12bcc',
    'tools/emit_observer_v2_fixture.py': 'a1edce1adabdcb9f1ecf3fb23ce40cb68ff8ce046f60eb1ace7dc44c782702de',
    'tools/managed_observer_report.py': 'ae81dc4140cb7fdbfc00ed7937267b7897d050f5fee73257cbb373739d0154b1',
    'tools/managed_observer_transport.py': 'ca393795ff3424543659a0892bdc8575472e5a27f6ebdea4e78d4fa2df5fda37',
    'tools/managed_observer_coverage.py': '1cde10c376bdb0c9cb42884eee808f815a1633dceb87ff0c66ec92d17cab3a30',
    'tools/run_managed_long.py': '03b4437e2d20a35182b74f6aadad417b9bb830df011731ea97ae7f7e050cbc55',
    'tools/managed_soak_observer.py': '3e6536413abec22a5bda71887ce228b7d7d584bd71bd950d525d84525398adeb',
    'tools/managed_output_budget.py': '8044707e4ff20dc54c9b9b7663689e2a3a0b15915c64c72e54c63b13466e9f58'}


def git(*args):
    return subprocess.check_output(['git', '--no-optional-locks', *args], cwd=ROOT,
        stdin=0, stderr=subprocess.PIPE)


def utc():
    return datetime.now(timezone.utc).isoformat()


def identity(pid):
    try:
        tail = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
    except FileNotFoundError:
        return {'pid': pid, 'observed': False}
    return {'pid': pid, 'birth': tail[19], 'state': tail[0], 'observed': True,
            'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip()}


def seal(name, value):
    descriptor = os.open(EVIDENCE / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


def closure():
    result = {}
    for name, checksum in INPUTS.items():
        path = ROOT / name
        if path.is_symlink(): raise RuntimeError('source_symlink:' + name)
        actual, expected = path.read_bytes(), git('show', SOURCE + ':' + name)
        if actual != expected or sha256(actual).hexdigest() != checksum:
            raise RuntimeError('source_byte_closure_changed:' + name)
        result[name] = {'bytes': len(actual), 'sha256': checksum}
    return result


if git('rev-parse', 'HEAD').decode().strip() != HEAD:
    raise RuntimeError('execution_before_freeze_HEAD_changed')
before = closure()
details = PARENT.lstat()
if (not stat.S_ISDIR(details.st_mode) or details.st_uid != os.geteuid()
        or stat.S_IMODE(details.st_mode) != 0o700 or PARENT.is_symlink()
        or OUTPUT.exists() or OUTPUT.is_symlink()):
    raise RuntimeError('owned_private_parent_and_fresh_once02_required_no_retry')
EVIDENCE.mkdir(mode=0o700, exist_ok=False)
seal('intent.json', {'source': SOURCE, 'frozen_HEAD': HEAD, 'argv': ARGV, 'inputs_before': before,
    'root_authorization': 'one fixed c076 actual once02 synthetic readonly-null/live-pipe/report-FS adapter; CPU1 outer10s KILL; first result no retry',
    'allowed_actual_runs_added': 1, 'no_second_budget': True, 'intent_utc': utc(),
    'launcher': identity(os.getpid()), 'launcher_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
    'output': str(OUTPUT), 'parent_identity': {'dev': details.st_dev, 'ino': details.st_ino, 'uid': details.st_uid, 'mode': '0700'},
    'actual_watch_SQL_financial_workers_crypto_keys_network_CI_6h': 'FORBIDDEN',
    'old_once01_dc1e_3e42_or_pure_batch_rerun': False,
    'new_probe_readonly_null_FD_is_only_null_device_open_in_this_launcher_and_probe_path': True,
    'max_data_children': 1, 'max_Pipes_threads': 2, 'max_frames': 4, 'commands_per_frame': 3,
    'max_pipe_bytes': 32768, 'max_CAS_bytes': 65536, 'max_measured_probe_bytes': 131072,
    'outer_raw_diagnostic_scope_separate': True, 'max_combined_outer_raw_bytes': 102400,
    'stricter_per_regular_file_RLIMIT_FSIZE_bytes': 49152})
descriptors = [os.open(EVIDENCE / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
               for name in ('stdout.txt', 'stderr.txt')]
started, tick, old_limit = utc(), time.monotonic_ns(), resource.getrlimit(resource.RLIMIT_FSIZE)
soft = min(49152, old_limit[0]) if old_limit[0] != resource.RLIM_INFINITY else 49152
resource.setrlimit(resource.RLIMIT_FSIZE, (soft, old_limit[1]))
try:
    process = subprocess.Popen(ARGV, cwd=ROOT, stdin=0, stdout=descriptors[0], stderr=descriptors[1],
        close_fds=True, start_new_session=True,
        env={'PATH': str(Path(sys.executable).parent) + os.pathsep + os.defpath,
             'PYTHONDONTWRITEBYTECODE': '1', 'LC_ALL': 'C.UTF-8'})
finally:
    resource.setrlimit(resource.RLIMIT_FSIZE, old_limit)
supervisor = identity(process.pid)
status = process.wait()
elapsed, finished = time.monotonic_ns() - tick, utc()
for descriptor in descriptors:
    os.fsync(descriptor); os.close(descriptor)
try: after, source_error = closure(), None
except BaseException as error: after, source_error = None, {'type': type(error).__name__, 'text': str(error)}
raw = {name: {'bytes': (EVIDENCE / name).stat().st_size, 'sha256': sha256((EVIDENCE / name).read_bytes()).hexdigest()}
       for name in ('stdout.txt', 'stderr.txt')}
artifacts, specials = {}, []
for path in sorted(OUTPUT.rglob('*')):
    detail = path.lstat()
    if stat.S_ISREG(detail.st_mode):
        artifacts[str(path.relative_to(OUTPUT))] = {'bytes': detail.st_size,
            'sha256': sha256(path.read_bytes()).hexdigest() if detail.st_size <= 131072 else None,
            'mode': oct(stat.S_IMODE(detail.st_mode))}
    elif not stat.S_ISDIR(detail.st_mode): specials.append(str(path.relative_to(OUTPUT)))


def saved(name):
    path = OUTPUT / 'control' / name
    if not path.exists(): return None
    try: return json.loads(path.read_bytes())
    except (ValueError, OSError): return None


cleanup, provisional, live, queue = map(saved, ('cleanup.json', 'result.json', 'first-frame-live.json', 'backpressure.json'))
owned = identity(cleanup['owned_child']['pid']) if cleanup and cleanup.get('owned_child') else None
birth_absent = bool(owned is not None and (not owned['observed'] or owned.get('birth') != cleanup['owned_child']['birth']))
try: final_stdout = json.loads((EVIDENCE / 'stdout.txt').read_bytes())
except ValueError: final_stdout = None
probe_bytes = sum(item['bytes'] for item in artifacts.values())
criteria = {
    'outer_exit_zero': status == 0, 'source_unchanged': before == after,
    'original_raw_complete_below_limit': sum(item['bytes'] for item in raw.values()) <= 102400 and all(item['bytes'] < soft for item in raw.values()),
    'all_probe_bytes_counted_below_131072': probe_bytes <= 131072 and not specials,
    'post_cleanup_stdout_reports_pass': bool(final_stdout and final_stdout.get('adapter_scope_passed') is True),
    'provisional_checks_recorded': bool(provisional and provisional.get('checks_before_cleanup_passed') is True),
    'live_small_frame_before_EOF_and_release': bool(live and live.get('classified_while_child_alive') is True
        and live.get('stdout_EOF_observed') is False and live.get('under_64KiB') is True
        and live.get('identity', {}).get('alive') is True and live['identity'].get('identity_matches') is True),
    'real_two_frame_queue_recorded': bool(queue and queue.get('pipe_state', {}).get('queued_raw_frames') == 2),
    'actual_hash_EOF_reopen_idempotency_quota_checks_finished': bool(provisional and provisional.get('frames') == 4
        and provisional.get('pipe_state', {}).get('frames_complete') is True and provisional.get('expected_zero_quota_rejection') is True),
    'cleanup_constructor_identity_exit_threads_complete': bool(cleanup and cleanup.get('Pipes_constructor_completed') is True
        and cleanup.get('Pipes_identity_binding_matches') is True and cleanup.get('birth_identity_established') is True
        and cleanup.get('child_exit') == 0 and cleanup.get('threads_created') == 2 and cleanup.get('owned_threads_alive') is False),
    'original_owned_child_birth_no_longer_present': birth_absent}
seal('execution.json', {'source': SOURCE, 'frozen_HEAD': HEAD, 'argv': ARGV, 'started_utc': started,
    'finished_utc': finished, 'elapsed_ns': elapsed, 'exit': status, 'timeout_supervisor': supervisor,
    'inputs_before': before, 'inputs_after': after, 'source_error': source_error, 'raw': raw,
    'probe_artifacts': artifacts, 'unexpected_special_files': specials, 'measured_probe_regular_file_bytes': probe_bytes,
    'separate_outer_raw_bytes': sum(item['bytes'] for item in raw.values()), 'owned_child_after_exit': owned,
    'criteria': criteria, 'all_declared_native_adapter_criteria_passed': all(criteria.values()),
    'first_attempt_at_this_source': True, 'automatic_retry': False,
    'actual_watch_SQL_financial_workers_crypto_keys_network_CI_6h': 'NOT_RUN',
    'production_approved': False, 'financial_6h_passed': False, 'system_qualification': 'NO_GO'})
print(json.dumps({'source': SOURCE, 'exit': status, 'elapsed_ns': elapsed, 'raw': raw,
    'measured_probe_bytes': probe_bytes, 'criteria': criteria}, sort_keys=True))
raise SystemExit(status if status != 0 else 0 if all(criteria.values()) else 1)
