"""One root-authorized six-method pure batch. No proc reads or data child."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
SOURCE = 'c076b0dc1feb765686de9c78683a4e4bea5429e2'
HEAD = '44e298456922975529a4e7d194e0c964b9f3d01b'
OUT = ROOT / 'evidence/observer-compact-report-v2/stdin-ownership-first-once01'
PLAN = 'evidence/observer-compact-report-v2/stdin-ownership-c076-preparation/source-budget.json'
ARGV = ['taskset', '-c', '1', 'timeout', '--signal=KILL', '10s', 'python', '-B',
        'tests/test_observer_v2_stdin_ownership_pure.py', '-v']


def git(*args):
    return subprocess.check_output(['git', '--no-optional-locks', *args], cwd=ROOT,
        stdin=0, stderr=subprocess.PIPE)


def utc():
    return datetime.now(timezone.utc).isoformat()


def seal(name, value):
    descriptor = os.open(OUT / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


plan_raw = (ROOT / PLAN).read_bytes()
if git('rev-parse', 'HEAD').decode().strip() != HEAD or git('show', HEAD + ':' + PLAN) != plan_raw:
    raise RuntimeError('frozen_HEAD_or_plan_changed')
plan = json.loads(plan_raw)
if plan['source_commit'] != SOURCE or plan['proposed_pure_argv'] != ARGV:
    raise RuntimeError('frozen_source_or_argv_changed')


def closure():
    result = {}
    for name, expected_hash in plan['source_sha256'].items():
        path = ROOT / name
        if path.is_symlink(): raise RuntimeError('source_symlink_rejected:' + name)
        expected, actual = git('show', SOURCE + ':' + name), path.read_bytes()
        if expected != actual or sha256(actual).hexdigest() != expected_hash:
            raise RuntimeError('source_byte_closure_changed:' + name)
        result[name] = {'bytes': len(actual), 'sha256': expected_hash}
    if len(result) != 2: raise RuntimeError('two_input_closure_required')
    return result


before = closure()
OUT.mkdir(mode=0o700, exist_ok=False)
seal('intent.json', {'source': SOURCE, 'frozen_HEAD': HEAD, 'argv': ARGV,
    'inputs_before': before, 'started_utc': utc(), 'launcher_pid': os.getpid(),
    'launcher_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
    'root_authorization': 'one fixed c076 six-method CPU1 outer10s KILL actual-AST/fakes batch after independent CODE closure',
    'allowed_runs_added': 1, 'no_second_budget': True,
    'real_null_data_child_threads_pipe_adapterFS_SQL_native_network_proc_olddata': 'FORBIDDEN',
    'source_reads_and_fresh_evidence_writes_only': True,
    'per_regular_file_capture_limit_bytes': 49152, 'combined_raw_limit_bytes': 102400})
descriptors = [os.open(OUT / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
               for name in ('stdout.txt', 'stderr.txt')]
started, tick, old_limit = utc(), time.monotonic_ns(), resource.getrlimit(resource.RLIMIT_FSIZE)
soft = min(49152, old_limit[0]) if old_limit[0] != resource.RLIM_INFINITY else 49152
resource.setrlimit(resource.RLIMIT_FSIZE, (soft, old_limit[1]))
try:
    process = subprocess.Popen(ARGV, cwd=ROOT, stdin=0,
        stdout=descriptors[0], stderr=descriptors[1], close_fds=True, start_new_session=True,
        env={'PATH': str(Path(sys.executable).parent) + os.pathsep + os.defpath,
             'PYTHONDONTWRITEBYTECODE': '1', 'LC_ALL': 'C.UTF-8'})
finally:
    resource.setrlimit(resource.RLIMIT_FSIZE, old_limit)
status = process.wait()
elapsed, finished = time.monotonic_ns() - tick, utc()
for descriptor in descriptors:
    os.fsync(descriptor); os.close(descriptor)
after = closure()
raw = {name: {'bytes': (OUT / name).stat().st_size,
              'sha256': sha256((OUT / name).read_bytes()).hexdigest()}
       for name in ('stdout.txt', 'stderr.txt')}
bounded = sum(item['bytes'] for item in raw.values()) <= 102400 and all(item['bytes'] < soft for item in raw.values())
seal('execution.json', {'source': SOURCE, 'frozen_HEAD': HEAD, 'argv': ARGV,
    'started_utc': started, 'finished_utc': finished, 'elapsed_ns': elapsed, 'exit': status,
    'timeout_process_PID_only': process.pid, 'proc_identity_not_read_or_assumed': True,
    'inputs_before': before, 'inputs_after': after, 'source_unchanged': before == after,
    'raw': raw, 'original_raw_bounded': bounded, 'first_batch_only': True, 'automatic_retry': False,
    'actual_adapter_once02_execution': 'NOT_RUN', 'production_approved': False,
    'financial_6h_passed': False, 'system_qualification': 'NO_GO'})
print(json.dumps({'source': SOURCE, 'exit': status, 'elapsed_ns': elapsed, 'raw': raw,
    'source_unchanged': before == after, 'raw_bounded': bounded}, sort_keys=True))
raise SystemExit(status if status != 0 else 0 if before == after and bounded else 1)
