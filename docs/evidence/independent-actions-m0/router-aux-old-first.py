"""Exact8295 pure omission probe, fresh synthetic files, no SQL or workload."""
from datetime import datetime,timezone
import errno
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time
from unittest.mock import patch
import os
import sys

ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).parent
SOURCE_SHA='7a0253a0d93d64efcc3e0fc3742a1d95759471614efced66aa1f7343ffbc2cce'
path=ROOT/'tools/independent_m0_controller.py';assert sha256(path.read_bytes()).hexdigest()==SOURCE_SHA
spec=importlib.util.spec_from_file_location('old8295_router_omission',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
events=[]
def audit(event,args):
    if event in {'subprocess.Popen','os.system','sqlite3.connect','socket.connect','socket.bind'}:
        events.append(event);raise RuntimeError('forbidden probe execution')
sys.addaudithook(audit)
started=datetime.now(timezone.utc).isoformat();clock=time.monotonic_ns();cases=[]
for stem in ('shard-0000','router'):
    with TemporaryDirectory(prefix='old8295-router-omission-') as directory:
        private=Path(directory)/'private';public=Path(directory)/'public';private.mkdir(mode=0o700);public.mkdir(mode=0o700)
        authority=private/'B/workload/authority';authority.mkdir(parents=True)
        (authority/(stem+'.sqlite3')).write_bytes(b'm');aux=authority/(stem+'.sqlite3-shm');aux.write_bytes(b'x')
        original=Path.lstat;gone=False
        def lstat(p,*a,**k):
            global gone
            if p==aux and not gone:
                gone=True;p.unlink();raise FileNotFoundError(errno.ENOENT,'synthetic disappearance',str(p))
            return original(p,*a,**k)
        observed=None;code=None
        try:
            with patch.object(Path,'lstat',lstat):observed=m.resource_usage(private,public)
        except m.GateError as error:code=str(error)
        cases.append(dict(stem=stem,role='private_root',case='B',sidecar='shm',fresh_fake_FS=True,
            expected=dict(normal=1,escrow=0,cleanup=0,total=1),observed=observed,error_code=code,
            status='PASS' if observed==dict(normal=1,escrow=0,cleanup=0,total=1) else 'RED'))
value=dict(kind='EXACT8295_ROUTER_OMISSION_FIRST_RED',version=1,control_commit='8295aaca4b4d254c438b228bb9da5591dafceee3',
    controller_sha256=SOURCE_SHA,script_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
    started_at=started,finished_at=datetime.now(timezone.utc).isoformat(),elapsed_monotonic_ns=time.monotonic_ns()-clock,
    cpu_affinity=sorted(os.sched_getaffinity(0)),cases=cases,blocked_execution_events=events,
    actual_M04_rerun=False,actual_SQL_native_owner_crypto_network=False,
    forbidden_modules=[n for n in sys.modules if n=='uta' or n.startswith('uta.') or n=='sqlite3'])
with (HERE/'router-aux-old-first.observation.json').open('x') as f:json.dump(value,f,indent=2,sort_keys=True);f.write('\n')
print(json.dumps(value,sort_keys=True))
raise SystemExit(1 if any(c['status']=='RED' for c in cases) else 0)
