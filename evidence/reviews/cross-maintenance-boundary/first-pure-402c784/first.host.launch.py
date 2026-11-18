from pathlib import Path
from hashlib import sha256
from datetime import datetime,timezone
import os,json,subprocess,time
H=Path('/workspace/uta-cross-maintenance-402c784-once01-host-once01')
R=Path('/workspace/uta-risk-linear-cost-sign')
P=Path('/workspace/uta-cross-maintenance-402c784-once01')
COMMAND=['/usr/bin/timeout','--signal=KILL','10s','/usr/bin/taskset','-c','1','/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python3.12','-I','-S','-B','/workspace/uta-risk-linear-cost-sign/tools/run_cross_maintenance_once.py','--plan-sha256','92fc36f7c1ea2f98d91f518fe93667c4a8ad907600a8e32c0070631c34fdcdc6','--source-commit','402c78412df53cb91e0f7f7d463fdd7026cf7cac','--private-directory',str(P)]
def write(name,value):
    fd=os.open(H/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as s:
        s.write((json.dumps(value,sort_keys=True,indent=2)+'\n').encode());s.flush();os.fsync(s.fileno())
def pin(path):
    b=path.read_bytes();return {'bytes':len(b),'sha256':sha256(b).hexdigest()}
os.umask(0o077)
assert not P.exists()
before=json.loads((H/'binding-before.json').read_bytes())
assert before['source_commit']=='402c78412df53cb91e0f7f7d463fdd7026cf7cac'
intent_ns=time.monotonic_ns()
write('first.host.intent.json',{'kind':'ROOT_AUTHORIZED_FIRST_ONCE_HOST_INTENT','argv':COMMAND,'cwd':str(R),'source_commit':before['source_commit'],'plan_sha256':before['plan_sha256'],'intent_monotonic_ns':intent_ns,'utc':datetime.now(timezone.utc).isoformat(),'launch_script':pin(Path(__file__)),'binding_before':pin(H/'binding-before.json'),'first_and_only':True,'production_approved':False})
fds=[os.open(H/n,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600) for n in ['first.launcher.stdout.txt','first.launcher.stderr.txt']]
started_ns=time.monotonic_ns()
process=None
try:
    process=subprocess.Popen(COMMAND,cwd=R,stdin=subprocess.DEVNULL,stdout=fds[0],stderr=fds[1],close_fds=True)
    code=process.wait()
    ended_ns=time.monotonic_ns()
finally:
    if process is not None and process.returncode is None:
        process.wait()
    for fd in fds:os.fsync(fd);os.close(fd)
raw={n:pin(H/n) for n in ['first.launcher.stdout.txt','first.launcher.stderr.txt']}
after={}
for name,prior in before['inputs'].items():
    f=R/name;fact=f.stat()
    after[name]={**pin(f),'mode':fact.st_mode&0o7777,'device':fact.st_dev,'inode':fact.st_ino,'mtime_ns':fact.st_mtime_ns,'ctime_ns':fact.st_ctime_ns}
same=all(all(after[n][k]==v for k,v in prior.items() if k!='Git_equal') for n,prior in before['inputs'].items())
inner_path=P/'first.execution.json'
inner=json.loads(inner_path.read_bytes()) if inner_path.is_file() else None
receipt={'kind':'ACTUAL_HOST_PREFIX_COMPLETION','argv':COMMAND,'actual_prefix_exit':code,'actual_prefix_reaped':process.returncode is not None,'intent_monotonic_ns':intent_ns,'launch_monotonic_ns':started_ns,'wait_return_monotonic_ns':ended_ns,'actual_prefix_elapsed_ns':ended_ns-started_ns,'launcher_raw':raw,'input_facts_after':after,'input_full_metadata_unchanged':same,'inner_receipt_pin':pin(inner_path) if inner else None,'inner_complete':inner.get('complete') if inner else None,'inner_passed':inner.get('passed') if inner else None,'scope':'pure selected methods only; not admission/SQL/matching integration','production_approved':False}
write('first.host.execution.json',receipt)
print(json.dumps({'event':'CROSS_MAINTENANCE_HOST_TERMINAL','actual_prefix_exit':code,'actual_prefix_reaped':receipt['actual_prefix_reaped'],'actual_prefix_elapsed_ns':receipt['actual_prefix_elapsed_ns'],'input_full_metadata_unchanged':same,'inner_complete':receipt['inner_complete'],'inner_passed':receipt['inner_passed']},sort_keys=True))
raise SystemExit(code if code>=0 else 128-code)
