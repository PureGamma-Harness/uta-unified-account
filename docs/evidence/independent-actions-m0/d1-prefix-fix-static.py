"""Read-only Git/AST + KB pure allowlist canaries for D1 commit boundary."""
import ast
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import stat
import subprocess
from tempfile import TemporaryDirectory

ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).parent
BASE='3e586f99c4ed750766461d4212cd17d9501cea84'
def old(p):return subprocess.check_output(['git','show',BASE+':'+p],cwd=ROOT)
def h(p):return sha256(p.read_bytes()).hexdigest()
def functions(raw):return {n.name:ast.dump(n) for n in ast.parse(raw).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
controller=ROOT/'tools/independent_m0_controller.py';a,b=functions(old('tools/independent_m0_controller.py')),functions(controller.read_bytes())
assert set(a)==set(b)
changed=[k for k in a if a[k]!=b[k]];assert changed==['write_resource_diagnostic']
paths=['tools/m0_stream_escrow.py','.github/workflows/independent-m0.yml','.github/workflows/independent-m0-once.yml',
    'config/m0-stream-recipient-public.pem','config/m0-stream-recipient-public-metadata.json',
    'docs/evidence/independent-actions-m0/once-registration-template.json']
unchanged={p:h(ROOT/p) for p in paths};assert all(old(p)==(ROOT/p).read_bytes() for p in paths)
spec=importlib.util.spec_from_file_location('d1_fixed_static',controller);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
value=dict(kind='M0_RESOURCE_DIAGNOSTIC',version=1,phase='CASE_B',scope='PRIVATE_ROOT',operation='ENTRY_LSTAT',
    errno=2,catalogue_label='UNKNOWN',unknown_relative_path_sha256='a'*64,primary_code='resource_missing_non_aux')
canaries=[]
for name in ['resource-diagnostic-incomplete-CASE_B.json','resource-diagnostic-CASE_B.json.part','case-B-safe/resource-diagnostic-CASE_B.json']:
    with TemporaryDirectory(prefix='d1-public-route-') as directory:
        public=Path(directory)/'public';public.mkdir(mode=0o700);p=public/name;p.parent.mkdir(exist_ok=True)
        raw=(json.dumps(value)+'\n').encode();p.write_bytes(raw)
        record=dict(name=name,bytes=len(raw),sha256=sha256(raw).hexdigest())
        m.public_write(public,'manifest.json',dict(files=[record],source_commit=m.SOURCE,private_authorities_requests_keys_nonces_signatures_streams_not_uploaded=True))
        try:m.verify_public(public)
        except m.GateError as error:canaries.append({'route':name,'rejected':True,'code':str(error)})
        else:raise AssertionError('private/nested route accepted')
with TemporaryDirectory(prefix='d1-public-dir-') as directory:
    public=Path(directory)/'public';public.mkdir(mode=0o700);(public/'resource-diagnostic-stage').mkdir()
    m.public_write(public,'manifest.json',dict(files=[],source_commit=m.SOURCE,private_authorities_requests_keys_nonces_signatures_streams_not_uploaded=True))
    try:m.verify_public(public)
    except m.GateError as error:canaries.append({'route':'resource-diagnostic-stage/','rejected':True,'code':str(error)})
    else:raise AssertionError('private stage directory accepted')
observation=json.loads((HERE/'d1-prefix-fix-second.observation.json').read_text())
for p,digest in observation['input_sha256'].items():assert h(ROOT/p)==digest
assert observation['tests_run']==158 and not observation['failures'] and not observation['errors']
result=dict(kind='D1_PREFIX_FIX_STATIC',version=1,base_controller=BASE,controller_sha256=h(controller),
    changed_functions=changed,unchanged_function_count=len(a)-1,unchanged_bytes=unchanged,
    public_staging_routes=canaries,diagnostic_schema_version=1,diagnostic_record_cap_bytes=4096,
    private_staging='resource-diagnostic-incomplete-PHASE.json',public_record='resource-diagnostic-PHASE.json',
    publication_order=['private O_EXCL/NOFOLLOW0600','write','flush','file fsync success','close success','no-overwrite link success'],
    cleanup_reservation_multiplier=2,cleanup_cap_bytes=m.CLEANUP_RESERVE,budget_spec=m.budget_spec(),
    directory_fsync_performed=False,directory_entry_crash_durability='NOT_CLAIMED',financial_receipt=False,
    first_red_owned_commit='f605b96c4714c744b65403bbfe3861f68f62d768',first_red_local_pick='fe9a9249647b6c15c4c74a38a7e8ea0c153f306c',
    source_commit=m.SOURCE,source_tree=m.SOURCE_TREE,command_spec=m.command_spec(),
    current_pure_observation_sha256=h(HERE/'d1-prefix-fix-second.observation.json'),
    actual_SQL_native_owner_crypto_network=False,production_approved=False,passed=True)
with (HERE/'d1-prefix-fix-static.json').open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
print(json.dumps({'only_function_changed':changed,'other_functions_unchanged':len(a)-1,'public_staging_negative_canaries':len(canaries),'passed':True},sort_keys=True))
