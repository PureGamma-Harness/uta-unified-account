"""One authorized small interpreter batch; synthetic cache only, no SQL."""
from datetime import datetime,timezone
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import unittest

ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).parent
PRIVATE=Path('/workspace/uta-cold-import-contract-20261118-first-private');PRIVATE.mkdir(mode=0o700)
spec=importlib.util.spec_from_file_location('first_cold_import_tests',ROOT/'tests/test_independent_m0_cold_import.py')
tests=importlib.util.module_from_spec(spec);spec.loader.exec_module(tests);tests.RETAIN_ROOT=PRIVATE
events=[]
def audit(event,args):
    if event=='import' and (args[0] in ('uta','sqlite3','_sqlite3') or args[0].startswith(('uta.','sqlite3.','_sqlite3.'))):raise RuntimeError('actual forbidden import in parent')
    if event in {'os.system','sqlite3.connect','socket.connect','socket.bind'}:raise RuntimeError('forbidden operation')
    if event=='subprocess.Popen':
        argv=args[1]
        if not (len(argv)==7 and argv[0]==sys.executable and argv[1:4]==['-I','-S','-c'] and argv[4]==tests.m.CHILD_CODE and argv[5] in tests.m.MODES):raise RuntimeError('unexpected interpreter command')
        events.append({'mode':argv[5],'flags':['-I','-S'],'child_code_sha256':sha256(argv[4].encode()).hexdigest()})
sys.addaudithook(audit)
inputs=['tools/independent_m0_controller.py','tools/m0_stream_escrow.py','tools/cold_import_contract.py',
    'tests/test_independent_m0_escrow.py','tests/test_independent_m0_integrity.py','tests/test_independent_m0_cold_import.py',
    '.github/workflows/independent-m0.yml','.github/workflows/independent-m0-once.yml']
hashes={p:sha256((ROOT/p).read_bytes()).hexdigest() for p in inputs}
started=datetime.now(timezone.utc).isoformat();clock=time.monotonic_ns()
result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(tests))
streams=[]
for p in sorted(PRIVATE.rglob('*.bin')):
    raw=p.read_bytes();streams.append({'relative_path':str(p.relative_to(PRIVATE)),'bytes':len(raw),'sha256':sha256(raw).hexdigest()})
value=dict(kind='COLD_IMPORT_FIRST_PURE_INTERPRETERS',version=1,base_commit='1d727b9d8e121611d0227dbee162192c13a76769',
    prior_general_CI_evidence_owned='dc9e42ababfd29106129d85ecd00ae4c38ebbb8c',
    started_at=started,finished_at=datetime.now(timezone.utc).isoformat(),elapsed_monotonic_ns=time.monotonic_ns()-clock,
    cpu_affinity=sorted(os.sched_getaffinity(0)),tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),
    real_child_spawn_events=events,case_results=tests.RESULTS,closed_private_streams=streams,input_sha256=hashes,
    runner_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
    original_CI_rerun=False,actual_SQL_UTA_import_in_children=False,actual_financial_owner_crypto_network=False,
    production_approved=False,M05_created=False)
with (HERE/'first.observation.json').open('x') as f:json.dump(value,f,indent=2,sort_keys=True);f.write('\n')
print(json.dumps({'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'real_children':len(events),'all_expected_child_proofs':[r['result']['status'] for r in tests.RESULTS[:4]],'private_streams':len(streams)},sort_keys=True))
raise SystemExit(0 if result.wasSuccessful() and len(events)==4 else 1)
