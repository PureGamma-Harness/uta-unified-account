"""External sequential validation launcher; never mutates frozen tracked sources."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

parser=argparse.ArgumentParser()
parser.add_argument('--source',type=Path,required=True)
parser.add_argument('--sha',required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
source=args.source.resolve()
def git(*parts):
 return subprocess.check_output(['git',*parts],cwd=source,text=True).strip()
assert git('rev-parse','HEAD') == args.sha
assert git('status','--porcelain') == ''
args.output.mkdir(parents=True,exist_ok=False)
os.sched_setaffinity(0,{1})
started=datetime.now(timezone.utc).isoformat()
launch_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
records=[]
runtimes=[('python312','/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python'),('python310','/tmp/uta-python310/cpython-3.10.22-linux-x86_64-gnu/bin/python3.10'),('python313-sqlite346','/usr/bin/python3.13')]
for label,python in runtimes:
 assert git('rev-parse','HEAD') == args.sha and git('status','--porcelain') == ''
 command=[python,str(source/'tools/run_validation.py'),'--output',str(args.output/label)]
 begin=datetime.now(timezone.utc).isoformat(); mono=time.monotonic()
 with (args.output/(label+'-launcher.txt')).open('x') as log:
  result=subprocess.run(command,cwd=source,stdout=log,stderr=subprocess.STDOUT)
 record={'label':label,'command':command,'started_at':begin,'finished_at':datetime.now(timezone.utc).isoformat(),'exit_code':result.returncode,'wall_seconds':time.monotonic()-mono}
 records.append(record)
 (args.output/'matrix-progress.json').write_text(json.dumps({'source_commit':args.sha,'started_at':started,'cpu_affinity':sorted(os.sched_getaffinity(0)),'records':records,'production_approved':False},indent=2)+'\n')
 print(json.dumps(record),flush=True)
assert git('rev-parse','HEAD') == args.sha and git('status','--porcelain') == ''
report={'source_commit':args.sha,'source_path':str(source),'started_at':started,'finished_at':datetime.now(timezone.utc).isoformat(),'cpu_affinity':sorted(os.sched_getaffinity(0)),'cohosted':True,'platform':platform.platform(),'launcher_sha256':launch_hash,'source_clean_after':True,'records':records,'all_exit_zero':all(x['exit_code']==0 for x in records),'production_approved':False,'capacity_10000_per_s_passed':False,'ha_approved':False}
(args.output/'matrix-summary.json').write_text(json.dumps(report,indent=2)+'\n')
sys.exit(0 if report['all_exit_zero'] else 1)
