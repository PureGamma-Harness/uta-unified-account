"""New candidate/fresh fake-FS suite, not a rerun of the actual M04 job."""
from datetime import datetime,timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import time
import unittest

ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).parent
events=[]
def audit(event,args):
    if event in {'subprocess.Popen','os.system','sqlite3.connect','socket.connect','socket.bind'}:
        events.append(event);raise RuntimeError('forbidden actual execution')
    if event=='import' and (args[0]=='sqlite3' or args[0]=='uta' or args[0].startswith(('uta.','sqlite3.'))):
        events.append('forbidden_import');raise RuntimeError('forbidden product import')
sys.addaudithook(audit)
inputs=[ROOT/'tools/independent_m0_controller.py',ROOT/'tools/m0_stream_escrow.py',*sorted((ROOT/'tests').glob('test_independent_m0_*.py'))]
hashes={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in inputs}
started=datetime.now(timezone.utc).isoformat();clock=time.monotonic_ns()
result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern='test_independent_m0_*.py'))
value=dict(kind='NEW_EXACT_ROUTER_POLICY_FRESH_FAKE_FS',version=1,
    evidence_parent_commit='4596fe49004171b893a26a850bf4bac6a3fd6414',
    old_original_controller='8295aaca4b4d254c438b228bb9da5591dafceee3',old_first_RED_preserved=True,
    started_at=started,finished_at=datetime.now(timezone.utc).isoformat(),elapsed_monotonic_ns=time.monotonic_ns()-clock,
    cpu_affinity=sorted(os.sched_getaffinity(0)),tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),
    blocked_execution_events=events,forbidden_modules=[n for n in sys.modules if n=='uta' or n.startswith('uta.') or n=='sqlite3'],
    input_sha256=hashes,runner_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
    main_parent_dev_ino_identity_replacement_protection_added=False,
    actual_M04_rerun_or_M05_registration=False,actual_SQL_native_owner_crypto_network_CI=False,
    production_or_capacity_approved=False)
with (HERE/'router-aux-new-first.observation.json').open('x') as f:json.dump(value,f,indent=2,sort_keys=True);f.write('\n')
print(json.dumps({'new_setup_tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'old_RED_unchanged':True},sort_keys=True))
raise SystemExit(0 if result.wasSuccessful() and not events and not value['forbidden_modules'] else 1)
