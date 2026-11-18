"""Bounded D1 final pure runner. No workload, Git subprocess or crypto here."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
import time
import unittest

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).with_name('d1-final-pure.observation.json')
needles=('sqlite3','uta')
for name in sys.modules:
    if any(name==stem or name.startswith(stem+'.') for stem in needles):
        raise RuntimeError('forbidden module preloaded')
blocked=[]
def audit(event,args):
    if event in {'subprocess.Popen','os.system','sqlite3.connect','socket.connect','socket.bind'}:
        blocked.append(event);raise RuntimeError('D1 forbidden execution event')
    if event=='import' and any(args[0]==stem or args[0].startswith(stem+'.') for stem in needles):
        blocked.append('forbidden_import');raise RuntimeError('D1 forbidden module import')
sys.addaudithook(audit)
inputs=[ROOT/'tools/independent_m0_controller.py',ROOT/'tools/m0_stream_escrow.py',
    ROOT/'.github/workflows/independent-m0.yml',ROOT/'.github/workflows/independent-m0-once.yml',
    *sorted((ROOT/'tests').glob('test_independent_m0_*.py'))]
hashes={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in inputs}
started=datetime.now(timezone.utc).isoformat();clock=time.monotonic_ns()
suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern='test_independent_m0_*.py')
result=unittest.TextTestRunner(verbosity=2).run(suite)
elapsed=time.monotonic_ns()-clock
observation=dict(kind='D1_SOURCE_BOUND_PURE',version=1,git_base='ab933bec61d5c4be3e40c1a337f8ce55705ba48d',
    started_at=started,finished_at=datetime.now(timezone.utc).isoformat(),elapsed_monotonic_ns=elapsed,
    tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),
    skipped=len(result.skipped),blocked_actual_execution_events=blocked,
    forbidden_modules_after=[n for n in sys.modules if any(n==s or n.startswith(s+'.') for s in needles)],
    cpu_affinity=sorted(__import__('os').sched_getaffinity(0)),input_sha256=hashes,
    runner_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),actual_financial_load=False,
    production_approved=False,capacity_approved=False,ha_approved=False)
with OUT.open('x') as f:json.dump(observation,f,indent=2,sort_keys=True);f.write('\n')
raise SystemExit(0 if result.wasSuccessful() and not blocked and not observation['forbidden_modules_after'] else 1)
