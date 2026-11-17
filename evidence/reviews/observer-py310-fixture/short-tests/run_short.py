"""Bounded actual-runtime fixture checks; only fresh in-memory SQLite errors."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
STAGE = sys.argv[1]
OUT = Path(__file__).parent / STAGE
OUT.mkdir()
os.sched_setaffinity(0, {2})
RUNTIMES = [("py310", "/tmp/uta-python310/cpython-3.10.22-linux-x86_64-gnu/bin/python3.10"), ("py312", sys.executable), ("py313", "/usr/bin/python3.13")]
FILES = ["tests/test_observer_read_diagnostic.py", "tools/diagnose_observer_read.py", "tools/managed_soak_observer.py"]
def hashes():
    return {name: sha256((ROOT/name).read_bytes()).hexdigest() for name in FILES}
code = """import gc,json,os,sqlite3,sys,unittest
sys.path.insert(0, 'tests')
import test_observer_read_diagnostic as tests
native = None
connection = sqlite3.connect(':memory:')
try:
    connection.execute('SELECT value FROM facts')
except sqlite3.Error as error:
    native = {'type':type(error).__name__, 'has_code':hasattr(error,'sqlite_errorcode'), 'code':getattr(error,'sqlite_errorcode',None), 'has_name':hasattr(error,'sqlite_errorname'), 'name':getattr(error,'sqlite_errorname',None)}
finally:
    connection.close()
fallback = sqlite3.OperationalError('private fallback detail')
result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(tests.ObserverReadDiagnosticTests))
gc.collect()
print(json.dumps({'python':sys.version,'cpu_ids':sorted(os.sched_getaffinity(0)),'module_exports_SQLITE_ERROR':hasattr(sqlite3,'SQLITE_ERROR'),'actual_native_exception':native,'actual_python_exception':{'has_code':hasattr(fallback,'sqlite_errorcode'),'has_name':hasattr(fallback,'sqlite_errorname')},'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),'passed':result.wasSuccessful(),'scope':'small fixture tests; fresh :memory: only; no job DB/service/benchmark'}))
raise SystemExit(not result.wasSuccessful())
"""
records = []
for label, interpreter in RUNTIMES:
    before = hashes();started = datetime.now(timezone.utc).isoformat();t0=time.monotonic()
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONWARNINGS='error::ResourceWarning')
    environment.pop('PYTHONPATH',None)
    process = subprocess.run([interpreter,'-B','-W','error::ResourceWarning','-c',code],cwd=ROOT,env=environment,capture_output=True,timeout=5)
    (OUT/(label+'.stdout.txt')).write_bytes(process.stdout)
    (OUT/(label+'.stderr.txt')).write_bytes(process.stderr)
    assert before == hashes()
    record = {'runtime':label,'command':[interpreter,'-B','-W','error::ResourceWarning','-c',code], 'started_utc':started,'finished_utc':datetime.now(timezone.utc).isoformat(),'wall_seconds':time.monotonic()-t0,'returncode':process.returncode,'before_sha256':before,'after_sha256':hashes(),'observed':json.loads(process.stdout.splitlines()[-1])}
    records.append(record)
(OUT/'summary.json').write_text(json.dumps({'stage':STAGE,'records':records,'actual_30s_total_limit':True,'runtime_module_edited':False,'no_existing_job_database_opened':True},indent=2)+'\n')
print(json.dumps([{'runtime':r['runtime'],'returncode':r['returncode'],'tests':r['observed']['tests_run'],'failures':r['observed']['failures'],'errors':r['observed']['errors'],'native':r['observed']['actual_native_exception'],'wall_seconds':r['wall_seconds']} for r in records],indent=2))
