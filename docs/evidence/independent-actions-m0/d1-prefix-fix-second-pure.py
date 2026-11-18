"""One bounded D1 commit-boundary pure batch; no SQL/native/crypto/owner."""
import ast
from datetime import datetime, timezone
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys
import time
import unittest

ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).parent
blocked=[]
def audit(event,args):
    if event in {'subprocess.Popen','os.system','sqlite3.connect','socket.connect','socket.bind'}:
        blocked.append(event);raise RuntimeError('forbidden execution')
    if event=='import' and (args[0]=='sqlite3' or args[0]=='uta' or args[0].startswith(('uta.','sqlite3.'))):
        blocked.append('forbidden_import');raise RuntimeError('forbidden import')
sys.addaudithook(audit)
inputs=[ROOT/'tools/independent_m0_controller.py',ROOT/'tools/m0_stream_escrow.py',
    ROOT/'evidence/reviews/m0-d1-3e586/first_prefix_boundary.py',HERE/'d1-prefix-fix-second-adapted.py',
    HERE/'d1-prefix-fix-second-adapter.patch',*sorted((ROOT/'tests').glob('test_independent_m0_*.py'))]
hashes={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in inputs}
started=datetime.now(timezone.utc).isoformat();clock=time.monotonic_ns()
suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern='test_independent_m0_*.py')
result=unittest.TextTestRunner(verbosity=2).run(suite)
spec=importlib.util.spec_from_file_location('prefix_fix_original',HERE/'d1-prefix-fix-second-adapted.py')
adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
cases=[adapter.scenario(False),adapter.scenario(True)]
value=dict(kind='D1_PREFIX_FIX_PURE',version=1,base='fe9a9249647b6c15c4c74a38a7e8ea0c153f306c',
    rejected_controller='3e586f99c4ed750766461d4212cd17d9501cea84',first_red_preserved='f605b96c4714c744b65403bbfe3861f68f62d768',
    started_at=started,finished_at=datetime.now(timezone.utc).isoformat(),elapsed_monotonic_ns=time.monotonic_ns()-clock,
    tests_run=result.testsRun,errors=len(result.errors),failures=len(result.failures),skipped=len(result.skipped),
    original_boundary_cases=cases,blocked_execution_events=blocked,
    forbidden_modules_after=[n for n in sys.modules if n=='sqlite3' or n=='uta' or n.startswith(('uta.','sqlite3.'))],
    cpu_affinity=sorted(__import__('os').sched_getaffinity(0)),input_sha256=hashes,
    runner_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
    actual_financial_native_owner_crypto_SQL_network=False,production_approved=False)
with (HERE/'d1-prefix-fix-second.observation.json').open('x') as f:json.dump(value,f,indent=2,sort_keys=True);f.write('\n')
print(json.dumps({'tests':value['tests_run'],'boundary_cases':cases,'events':blocked},sort_keys=True))
raise SystemExit(0 if result.wasSuccessful() and all(c['status']=='PASS' for c in cases) and not blocked and not value['forbidden_modules_after'] else 1)
