from datetime import datetime,timezone
from hashlib import sha256
import json,os,pathlib,subprocess,sys

ROOT=pathlib.Path('/workspace/uta-cache-fixture-closing')
os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
stage,executable=sys.argv[1:]
base=pathlib.Path('/tmp/uta-cache-guard-closing-'+stage)
program='''import gc,json,os,sqlite3,sys,unittest,warnings
warnings.simplefilter("error",ResourceWarning)
unraisables=[]
def unraisable(event):
    unraisables.append({"type":event.exc_type.__name__,"message":str(event.exc_value),"err_msg":event.err_msg})
sys.unraisablehook=unraisable
class ForcedGCResult(unittest.TextTestResult):
    def stopTest(self,test):
        super().stopTest(test)
        gc.collect()
print({"python":sys.version,"sqlite":sqlite3.sqlite_version,"affinity":sorted(os.sched_getaffinity(0)),"resource_warning_policy":"error; explicit parent GC after each test; inherited by child"},flush=True)
suite=unittest.defaultTestLoader.discover("tests",pattern="test_supervision_cache_guard_validation.py")
result=unittest.TextTestRunner(verbosity=2,resultclass=ForcedGCResult).run(suite)
gc.collect()
print(json.dumps({"forced_gc_unraisables":unraisables}),flush=True)
raise SystemExit(not result.wasSuccessful() or bool(unraisables))
'''
environment=dict(os.environ,PYTHONWARNINGS='error::ResourceWarning',UTA_CACHE_GUARD_EVIDENCE=str(base/'cases'))
base.mkdir()
metadata={'stage':stage,'started_utc':datetime.now(timezone.utc).isoformat(),'interpreter':executable,
          'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
          'test_sha256':sha256((ROOT/'tests/test_supervision_cache_guard_validation.py').read_bytes()).hexdigest(),
          'driver_sha256':sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'benchmark_load_run':False,'cpu_affinity':sorted(os.sched_getaffinity(0))}
with (base/'test-output.log').open('x') as output:
    result=subprocess.run([executable,'-c',program],cwd=ROOT,env=environment,stdout=output,stderr=subprocess.STDOUT)
log=(base/'test-output.log').read_text()
metadata.update(finished_utc=datetime.now(timezone.utc).isoformat(),returncode=result.returncode,
                resource_warning_seen='ResourceWarning' in log,forced_gc_qualified=result.returncode==0 and 'ResourceWarning' not in log)
(base/'run.json').write_text(json.dumps(metadata,indent=2)+'\n')
print(log,flush=True)
print(json.dumps(metadata,indent=2),flush=True)
