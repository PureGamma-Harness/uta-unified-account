from pathlib import Path
from hashlib import sha256, sha1
import contextlib
import datetime
import importlib.util
import json
import multiprocessing.process
import os
import signal
import sqlite3
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

ROOT = Path('/workspace/uta-interest-accrual-kernel')
OUT = Path(__file__).resolve().parent
SOURCE = 'c507e0b458f24d2434ed2c24df597ba171113d3c'
os.umask(0o077)
started = time.monotonic_ns()
signal.alarm(10)
os.sched_setaffinity(0, {2})
assert set(os.sched_getaffinity(0)) == {2}
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == SOURCE
assert not subprocess.check_output(['git', 'status', '--porcelain=v1'], cwd=ROOT, text=True)
pins = {}
for line in subprocess.check_output(['git', 'ls-tree', '-r', SOURCE, '--', 'uta', 'tests/test_interest_accrual.py'], cwd=ROOT, text=True).splitlines():
    header, name = line.split('\t', 1)
    raw = (ROOT / name).read_bytes()
    assert sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == header.split()[2]
    pins[name] = sha256(raw).hexdigest()
identity = Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()
proof = {'source_commit': SOURCE, 'pid': os.getpid(), 'birth_ticks': int(identity[19]),
    'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
    'cpu_ids': sorted(os.sched_getaffinity(0)), 'python': sys.version,
    'python_executable': str(Path(sys.executable).resolve()), 'sqlite_build': sqlite3.sqlite_version,
    'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'driver_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
    'source_sha256': pins, 'financial_source_or_scheduler_activated': False}
(OUT / 'source-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
sys.path.insert(0, str(ROOT))
with contextlib.ExitStack() as stack:
    denied = {}
    for target in ['sqlite3.connect', 'subprocess.Popen', 'multiprocessing.process.BaseProcess.start', 'os.kill']:
        denied[target] = stack.enter_context(patch(target, side_effect=AssertionError('forbidden effect in pure interest tests')))
    for target in ['os.fork', 'signal.pidfd_send_signal']:
        module, field = target.split('.')
        if hasattr(sys.modules[module], field):
            denied[target] = stack.enter_context(patch(target, side_effect=AssertionError('forbidden effect in pure interest tests')))
    spec = importlib.util.spec_from_file_location('interest_component_cases', ROOT / 'tests/test_interest_accrual.py')
    cases = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cases)
    module = sys.modules['uta.interest_accrual']
    assert Path(module.__file__).resolve() == ROOT / 'uta/interest_accrual.py'
    proof['actual_import_path'] = str(Path(module.__file__).resolve())
    (OUT / 'same-process-import-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    suite = unittest.defaultTestLoader.loadTestsFromModule(cases)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    effects = {name: mock.call_count for name, mock in denied.items()}
    assert not any(effects.values())
assert {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in pins} == pins
assert sorted(name for name in sys.modules if name == 'uta' or name.startswith('uta.')) == ['uta', 'uta.interest_accrual']
report = {'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
    'skipped': len(result.skipped), 'passed': result.wasSuccessful(), 'effects_attempted': effects,
    'source_unchanged': True, 'elapsed_ns_before_report': time.monotonic_ns() - started,
    'ended_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'actual_sql_or_business_worker': False, 'production_approved': False}
(OUT / 'test-result.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report), flush=True)
signal.alarm(0)
raise SystemExit(0 if result.wasSuccessful() else 1)
