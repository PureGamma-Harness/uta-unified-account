"""One fresh no-Git replay of the new archived-source binding contract."""
from datetime import datetime,timezone
from pathlib import Path
import json,os,subprocess,time,sys
root=Path("/workspace/uta-package-91e4ae4")
work=Path("/workspace/uta-package-91e4ae4-work.txt").read_text().strip();work=Path(work)
source=work/"sdist-unpacked/uta_reference_exchange-0.5.0a1"
assert not (source/".git").exists()
os.sched_setaffinity(0,{2})
env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1");env.pop("PYTHONPATH",None)
command=[str(work/"venv/bin/python"),"-m","unittest","discover","-s","tests","-p","test_capacity_review_data_reference.py","-v"]
started=datetime.now(timezone.utc).isoformat();at=time.monotonic_ns()
with (root/"history-reference.stdout.txt").open("x") as out,(root/"history-reference.stderr.txt").open("x") as err:
 result=subprocess.run(command,cwd=source,env=env,stdout=out,stderr=err,timeout=60)
log=(root/"history-reference.stderr.txt").read_text()
passed=result.returncode==0 and "Ran 10 tests" in log and log.rstrip().endswith("OK")
report={"source_commit":"91e4ae40b5e9b884c54026406299df5000c9c100","started_utc":started,"finished_utc":datetime.now(timezone.utc).isoformat(),"duration_seconds":(time.monotonic_ns()-at)/1e9,"command":command,"cwd":str(source),"affinity":[2],"cohosted":True,"source_has_git":False,"returncode":result.returncode,"tests":10,"passed":passed,"scope":"new historical reference source/provenance contract only; pure no DB/runtime/service","production_approved":False}
(root/"history-reference-execution.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report));raise SystemExit(0 if passed else 2)
