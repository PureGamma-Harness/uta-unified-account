"""One bounded three-runtime owned-temp prototype experiment."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import resource
import signal
import sqlite3
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
RUNTIMES = {
    'python310': '/tmp/uta-python310/cpython-3.10.22-linux-x86_64-gnu/bin/python3.10',
    'python312': '/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python',
    'python313': '/usr/bin/python3.13',
}
INPUTS = ['benchmarks/managed_read_holders.py', 'benchmarks/run_managed_soak.py', 'tests/test_managed_read_holders.py', 'tests/test_managed_read_holder_lifecycle.py', 'tests/test_managed_read_holder_paths.py']


def utc():
    return datetime.now(timezone.utc).isoformat()


def hashes():
    return {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in INPUTS}


def worker(name):
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
    sys.path.insert(0, str(ROOT))
    start, beginning = utc(), time.monotonic()
    suite = unittest.defaultTestLoader.loadTestsFromNames([
        'tests.test_managed_read_holder_lifecycle',
        'tests.test_managed_read_holder_paths',
        'tests.test_managed_read_holders.IdleReadHolderPrototypeTests.test_warm_three_real_readers_preserve_aux_and_actual_kernel_ro_read',
    ])
    count = suite.countTestCases()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    record = dict(started_at=start, finished_at=utc(), duration_seconds=time.monotonic()-beginning,
        python=sys.version, sqlite=sqlite3.sqlite_version, affinity=sorted(os.sched_getaffinity(0)),
        planned_tests=count, tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
        skipped=len(result.skipped), expected_failures=len(result.expectedFailures),
        unexpected_successes=len(result.unexpectedSuccesses), passed=result.wasSuccessful())
    (OUT / (name + '-result.json')).write_text(json.dumps(record, indent=2) + '\n')
    return 0 if result.wasSuccessful() and count == 10 else 1


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        return worker(sys.argv[2])
    initial = hashes()
    beginning, start = time.monotonic(), utc()
    deadline, runs = beginning + 29, []
    for name, executable in RUNTIMES.items():
        command = ['taskset', '-c', '2', executable, '-B', '-W', 'error::ResourceWarning',
                   str(Path(__file__).resolve()), '--worker', name]
        record = dict(name=name, argv=command, started_at=utc(), timed_out=False)
        with (OUT / (name + '-unittest.txt')).open('x') as stream:
            process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL,
                stdout=stream, stderr=subprocess.STDOUT, close_fds=True, start_new_session=True)
            try:
                record['exit_code'] = process.wait(timeout=max(.001, deadline-time.monotonic()))
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                record['exit_code'], record['timed_out'] = process.wait(), True
        record['finished_at'] = utc()
        runs.append(record)
        print(json.dumps(record), flush=True)
        if record['exit_code'] != 0 or record['timed_out']:
            break
    final = hashes()
    result = dict(started_at=start, finished_at=utc(), duration_seconds=time.monotonic()-beginning,
        shared_hard_child_budget_seconds=29, authorized_total_ceiling_seconds=30, runs=runs,
        source_before=initial, source_after=final, source_unchanged=initial == final,
        all_three_runtime_experiments_passed=len(runs) == 3 and all(r['exit_code'] == 0 and not r['timed_out'] for r in runs),
        candidate_service_lifecycle_wired=True, service_started=False, original_job_or_source_sql=False,
        original_historical_error_cause_proven=False, production_approved=False,
        continuous_6h_stability_passed=False)
    (OUT / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
    return 0 if result['all_three_runtime_experiments_passed'] and result['source_unchanged'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
