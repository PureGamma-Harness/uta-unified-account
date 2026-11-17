from pathlib import Path
from hashlib import sha256
import datetime,importlib.util,json,multiprocessing,os,signal,sqlite3,stat,subprocess,sys,time,unittest
from unittest.mock import patch
ROOT=Path('/workspace/uta-deployment-preflight')
OUT=Path('/workspace/uta-deployment-preflight-private-20261117-parser-refusal-fixed')
os.umask(0o077)
os.sched_setaffinity(0,{2})
signal.alarm(8)
planraw=(OUT/'plan.json').read_bytes();plan=json.loads(planraw)
code=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
assert code==plan['source_commit']
pins={p:sha256((ROOT/p).read_bytes()).hexdigest() for p in plan['source_sha256']}
assert pins==plan['source_sha256']
spec=importlib.util.spec_from_file_location('deployment_parser_fixed',ROOT/'tests/test_deployment_manifest.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
proof={'source_commit':code,'source_sha256':pins,'plan_sha256':sha256(planraw).hexdigest(),'pid':os.getpid(),'cpu_ids':sorted(os.sched_getaffinity(0)),'python':sys.version,'int_max_str_digits':getattr(sys,'get_int_max_str_digits',lambda:0)(),'sqlite_runtime_version_only':sqlite3.sqlite_version,'test_import_path':module.__file__,'tool_import_path':module.CHECK.__file__,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
(OUT/'source-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
forbidden=[];manifest_reads=[];real_read=Path.read_bytes

def deny(name):
 def denied(*args,**kwargs):
  forbidden.append(name)
  raise AssertionError('forbidden API '+name)
 return denied

def manifest_only_read(path):
 if path.name!='manifest.json' or not path.parent.name.startswith('uta-deploy-metadata-'):
  return deny('nonmanifest_body_read')()
 details=path.lstat()
 if not stat.S_ISREG(details.st_mode) or details.st_uid!=os.getuid():
  return deny('nonregular_manifest_read')()
 manifest_reads.append(details.st_size)
 return real_read(path)

begin=time.monotonic_ns()
with patch.object(sqlite3,'connect',side_effect=deny('sqlite_connect')),patch.object(subprocess,'Popen',side_effect=deny('Popen')),patch.object(multiprocessing.Process,'start',side_effect=deny('Process.start')),patch.object(os,'fork',side_effect=deny('fork')),patch.object(os,'kill',side_effect=deny('kill')),patch.object(os,'pidfd_open',side_effect=deny('pidfd_open')),patch.object(signal,'pidfd_send_signal',side_effect=deny('pidfd_send_signal')),patch.object(Path,'read_bytes',manifest_only_read):
 result=unittest.TextTestRunner(stream=sys.stderr,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(module))
elapsed=time.monotonic_ns()-begin
report={'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),'passed':result.wasSuccessful() and result.testsRun==plan['expected_test_methods'] and not forbidden,'elapsed_ns_before_result_write':elapsed,'source_unchanged':pins=={p:sha256((ROOT/p).read_bytes()).hexdigest() for p in pins},'forbidden_api_calls':forbidden,'fresh_manifest_read_count':len(manifest_reads),'maximum_actual_manifest_bytes_read':max(manifest_reads,default=0),'actual_secret_artifact_database_bodies_read':False,'SQL_process_signal_denied_during_tests':True,'production_approved':False}
(OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report));signal.alarm(0)
raise SystemExit(0 if report['passed'] and report['source_unchanged'] else 1)
