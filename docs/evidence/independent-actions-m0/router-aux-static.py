"""Git/files/AST-only exact router addition proof; no workload or SQL."""
import ast
from hashlib import sha256
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).parent
BASE='8295aaca4b4d254c438b228bb9da5591dafceee3';SOURCE='909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0'
def blob(path,ref=BASE):return subprocess.check_output(['git','show',ref+':'+path],cwd=ROOT)
path='tools/independent_m0_controller.py';old=blob(path);new=(ROOT/path).read_bytes()
expected=old.replace(b"r'[BP]/workload/authority/shard-[0-9]{4}\\.sqlite3-(wal|shm)'",b"r'[BP]/workload/authority/(?:router|shard-[0-9]{4})\\.sqlite3-(wal|shm)'").replace(b"r'workload/authority/shard-[0-9]{4}\\.sqlite3-(wal|shm)'",b"r'workload/authority/(?:router|shard-[0-9]{4})\\.sqlite3-(wal|shm)'")
assert new==expected and new!=old
def functions(raw):return {n.name:ast.dump(n) for n in ast.parse(raw).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
a,b=functions(old),functions(new);assert set(a)==set(b)
changes=[k for k in a if a[k]!=b[k]];assert changes==['_sqlite_aux_location']
unchanged={}
for p in ['tools/m0_stream_escrow.py','.github/workflows/independent-m0.yml','.github/workflows/independent-m0-once.yml','docs/evidence/independent-actions-m0/once-registration-template.json','docs/evidence/independent-actions-m0/once04-registration-template.json','config/m0-stream-recipient-public.pem','config/m0-stream-recipient-public-metadata.json']:
    raw=(ROOT/p).read_bytes();assert raw==blob(p);unchanged[p]=sha256(raw).hexdigest()
observation=json.loads((HERE/'router-aux-new-first.observation.json').read_text());assert observation['tests_run']==186 and observation['failures']==observation['errors']==observation['skipped']==0
for p,h in observation['input_sha256'].items():assert sha256((ROOT/p).read_bytes()).hexdigest()==h
raw=blob('uta/sharding.py',SOURCE);lines=raw.decode().splitlines();assert 'router.sqlite3' in lines[148]
catalogue={'source_path':'uta/sharding.py','source_commit':SOURCE,'bytes':len(raw),'sha256':sha256(raw).hexdigest(),'git_blob':subprocess.check_output(['git','rev-parse',SOURCE+':uta/sharding.py'],cwd=ROOT).decode().strip(),'line':149,'source_line':lines[148]}
report=dict(kind='EXACT_ROUTER_AUX_STATIC_PROOF',version=1,base=BASE,controller_sha256=sha256(new).hexdigest(),
    changed_functions=changes,other_functions_AST_equal=len(a)-1,whole_file_only_two_pattern_literals_changed=True,
    unaffected_file_sha256=unchanged,actual_source_catalogue=catalogue,
    old_RED_observation_sha256=sha256((HERE/'router-aux-old-first.observation.json').read_bytes()).hexdigest(),
    new_pure_observation_sha256=sha256((HERE/'router-aux-new-first.observation.json').read_bytes()).hexdigest(),
    main_parent_dev_ino_replacement_detection_added=False,M04_spent=True,M05_created_or_execution_authorized=False,
    actual_SQL_native_owner_crypto_network_CI=False,production_approved=False)
with (HERE/'router-aux-static.json').open('x') as f:json.dump(report,f,indent=2,sort_keys=True);f.write('\n')
print(json.dumps({'only_changed_function':changes,'other_AST_same':len(a)-1,'two_literals_only':True,'source_catalogue_line':149},sort_keys=True))
