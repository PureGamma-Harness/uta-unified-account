from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess,sys,time
base=Path('/workspace/uta-ci-a35-all')
artifact=next(x for x in json.loads((base/'artifact-catalog.json').read_text())['artifacts'] if x['id']==int(sys.argv[1]))
directory=base/str(artifact['run'])/artifact['name']; directory.mkdir(mode=0o700,parents=True,exist_ok=True)
zip_path=directory/'original-artifact.zip'; assert not zip_path.exists()
pending=directory/'gh-api-download.pending'; assert not pending.exists()
started=datetime.now(timezone.utc).isoformat(); mono=time.monotonic()
with pending.open('xb') as output:
 try:
  result=subprocess.run(['gh','api',f"repos/PureGamma-Harness/uta-unified-account/actions/artifacts/{artifact['id']}/zip"],stdout=output,stderr=subprocess.PIPE,timeout=45)
 except subprocess.TimeoutExpired:
  result=None
raw=pending.read_bytes(); observed=hashlib.sha256(raw).hexdigest()
passed=result is not None and result.returncode==0 and observed==artifact['sha256']
receipt={'artifact_id':artifact['id'],'method':'gh api artifact zip; fresh direct retrieval; no signed URL retained','started_utc':started,'finished_utc':datetime.now(timezone.utc).isoformat(),'wall_seconds':time.monotonic()-mono,'returncode':None if result is None else result.returncode,'bytes':len(raw),'observed_sha256':observed,'expected_sha256':artifact['sha256'],'passed':passed,'stderr_bytes':None if result is None else len(result.stderr),'stderr_sha256':None if result is None else hashlib.sha256(result.stderr).hexdigest()}
(directory/'retrieval-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
if passed: pending.rename(zip_path)
print(json.dumps(receipt))
raise SystemExit(0 if passed else 1)
