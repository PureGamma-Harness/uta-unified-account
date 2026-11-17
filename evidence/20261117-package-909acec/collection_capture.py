"""Record one safe text collection process; retain the complete first outcome."""
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import argparse,json,os,shutil,subprocess,sys,time
parser=argparse.ArgumentParser();parser.add_argument('--config',type=Path,required=True)
args=parser.parse_args();config=json.loads(args.config.read_text())
work=Path(config['work_directory']);dest=Path(config['evidence_directory'])
os.sched_setaffinity(0,{2});environment=dict(os.environ,PYTHONDONTWRITEBYTECODE='1');environment.pop('PYTHONPATH',None)
argv=[sys.executable,str(dest/'collect_public.py'),'--config',str(args.config.resolve())]
stdout,stderr,execution=(work/name for name in ('collection.stdout.txt','collection.stderr.txt','collection-execution.json'))
assert not any(path.exists() for path in (stdout,stderr,execution)), 'retain previous collection evidence'
record={'source_commit':config['source_commit'],'argv':argv,'cwd':str(work),'started_utc':datetime.now(timezone.utc).isoformat(),'started_monotonic_ns':time.monotonic_ns(),'affinity':sorted(os.sched_getaffinity(0)),'cohosted':True,'scope':'safe text/JSON collection and physical archive hashing; no product import or SQL','timeout_seconds':180,'expected_returncode':0,'capture_path':str(Path(__file__).resolve()),'capture_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),'collector_sha256':sha256((dest/'collect_public.py').read_bytes()).hexdigest(),'config_sha256':sha256(args.config.read_bytes()).hexdigest(),'environment':{'PYTHONPATH':None,'PYTHONDONTWRITEBYTECODE':'1'}}
execution.write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
print('BEGIN collection',record['started_utc'],flush=True)
try:
 with stdout.open('xb') as out,stderr.open('xb') as err:
  process=subprocess.run(argv,cwd=work,env=environment,stdout=out,stderr=err,timeout=180)
 record['returncode']=process.returncode
except subprocess.TimeoutExpired:
 record['returncode']=124;record['timed_out']=True
record.update(finished_utc=datetime.now(timezone.utc).isoformat(),finished_monotonic_ns=time.monotonic_ns())
record['seconds']=(record['finished_monotonic_ns']-record['started_monotonic_ns'])/1e9
for name,path in (('stdout',stdout),('stderr',stderr)):
 record[name]={'path':str(path),'sha256':sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size}
execution.write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
print('END collection',record['returncode'],round(record['seconds'],3),flush=True)
if record['returncode']:raise SystemExit(record['returncode'])
allowlist=dest/'public-allowlist.json';published=json.loads(allowlist.read_text())
for original in (stdout,stderr,execution):
 target=dest/original.name;assert not target.exists()
 data=original.read_bytes();data.decode('utf-8');shutil.copyfile(original,target);assert target.read_bytes()==data
 published['copied_files'][original.name]={'original_path':str(original),'sha256':sha256(data).hexdigest(),'bytes':len(data)}
allowlist.write_text(json.dumps(published,indent=2,sort_keys=True)+'\n')
