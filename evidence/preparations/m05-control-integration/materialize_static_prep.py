"""M05 Git/files/AST materialization only; never imports target modules."""
import ast
from hashlib import sha256
import fnmatch
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent
BASE='6010e920a168b35fccfc9ef9ee34e030b28b11d9';FS='3cc254db1d59f805a6d64825d75360a7f31aad41'
SOURCE='909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0'
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def blob(ref,path):return git('show',ref+':'+path)
def h(raw):return sha256(raw).hexdigest()
controller=(ROOT/'tools/independent_m0_controller.py').read_bytes();tree=ast.parse(controller)
expected=blob(FS,'tools/independent_m0_controller.py').replace(b"APPROVED_BRANCH = 'refs/heads/perf/approved-m0-20261117-04'",b"APPROVED_BRANCH = 'refs/heads/perf/approved-m0-20261117-05'").replace(b"REGISTRATION_ID = 'independent-m0-20261117-04'",b"REGISTRATION_ID = 'independent-m0-20261117-05'")
assert controller==expected
functions=lambda t:{n.name:ast.dump(n) for n in t.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
assert functions(tree)==functions(ast.parse(blob(FS,'tools/independent_m0_controller.py')))
assert git('diff','--name-only',BASE,'HEAD','--','uta')==b''
runtime=git('rev-parse',BASE+':uta').decode().strip();assert runtime==git('rev-parse','ff814d4bcaee079b0e0503ea8072c24e3563c443:uta').decode().strip()
assert not (ROOT/'uta').exists()
assert git('ls-tree','HEAD','config/independent-m0-approved.json')==b''
assert git('log','--format=','--name-status',SOURCE+'..HEAD','--','config/independent-m0-approved.json').strip()==b''
assert subprocess.run(['git','merge-base','--is-ancestor','e643661dbafdff76e66c50d20eecc2fdef4bf9e1','HEAD'],cwd=ROOT).returncode==1
branch='refs/heads/perf/approved-m0-20261117-05';registration='independent-m0-20261117-05'
assert subprocess.run(['git','show-ref','--verify','--quiet',branch],cwd=ROOT).returncode==1
template=json.loads((ROOT/'docs/evidence/independent-actions-m0/once04-registration-template.json').read_text())
template.update(registration_id=registration,branch=branch,execution_authorized=False,control_commit='0'*40,
    controller_sha256=h(controller),workflow_sha256=h((ROOT/'.github/workflows/independent-m0-once.yml').read_bytes()),
    workspace_boot_id='00000000-0000-0000-0000-000000000000',workspace_hostname_sha256='0'*64,workspace_recorded_at='1970-01-01T00:00:00+00:00')
manifest_function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='validate_once_manifest')
assert set(template)==ast.literal_eval(manifest_function.body[0].value) and len(template)==19
assert template['source_commit']==SOURCE and template['budgets']['minimum_fresh_free_bytes']==2348810240
tests=sorted(p.name for p in (ROOT/'tests').glob('test_independent_m0_*.py'));assert len(tests)==9
workflow={}
for path in ['.github/workflows/independent-m0.yml','.github/workflows/independent-m0-once.yml']:
    raw=(ROOT/path).read_text();command=next(line.strip() for line in raw.splitlines() if 'python -m unittest discover' in line)
    assert "-p 'test_independent_m0_*.py'" in command
    assert all('/tests/'+name in raw and fnmatch.fnmatch(name,'test_independent_m0_*.py') for name in tests)
    assert '/tools/cold_import_contract.py' in raw
    blocks=raw.split('      - ')
    selected=[b for b in blocks if '\n          path: workload\n' in b];assert len(selected)==1
    block=selected[0];assert 'ref: '+SOURCE+'\n' in block and 'uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683' in block
    workflow[path]={'sha256':h(raw.encode()),'actual_pure_command':command,'tests':tests,'source40':SOURCE}
checks={}
for p in ['tools/m0_stream_escrow.py','tools/cold_import_contract.py','config/m0-stream-recipient-public.pem','config/m0-stream-recipient-public-metadata.json','docs/evidence/independent-actions-m0/once-registration-template.json','docs/evidence/independent-actions-m0/once04-registration-template.json']:
    checks[p]=h((ROOT/p).read_bytes())
assert checks['tools/m0_stream_escrow.py']==template['escrow_tool_sha256']
assert checks['config/m0-stream-recipient-public.pem']==template['recipient_certificate_sha256']
policy=dict(kind='M05_INTEGRATION_PREP_ONLY',version=1,next_run_permitted=False,execution_authorized=False,
    source_runtime_base=BASE,runtime_uta_tree=runtime,runtime_zero_diff_to6010=True,runtime_same_as_delivered_ff814=True,
    control_commit='0'*40,controller_sha256=h(controller),branch=branch,registration_id=registration,
    actual_marker_created=False,trigger_ref_created=False,push_or_dispatch_performed=False,
    combined_new_tree_PURE='NOT_RUN_REQUIRES_SEPARATE_ROOT_BUDGET',
    component_review={'cold':{'code':'87c9675d9852d709782d7f461661c66f2e0ba80d','review':'173accf5472e49bd7dcec4a18fbd7383960654a3','scope':'original4coldchildtargets+6newparentstub only'},
        'packaging':{'integrated':'8735668289ff739894b0318d391ce5409b7e6df4','peer':'0c1808a8ee8a5914286e4bbadde8046f343c72e1','scope':'actualf3a build7checks; not integratedtree build'},
        'FS':{'code':'4f316a89da1a001a9670a41cfeca754e67de1401','tip':FS,'status':'INDEPENDENT_TOKEN_PROOF_REVIEW_PENDING','old_c524_19PASS1RED_preserved':True}},
    M04_safe='69d2c069fadd446a6a84648dc8fcbb8d6a8ce7ad',CI_first_docs_only_cherry='ed929d38648486ec01a01094b772b2c9c1072573',
    CI_original_owner='dc9e42ababfd29106129d85ecd00ae4c38ebbb8c',CI_true_marker_parent_not_merged=True,
    spent_registrations=['01','02','03','04'],external_persistent_spent_registry=False,
    command_spec=template['command_spec'],budgets=template['budgets'],source_commit=SOURCE,source_tree=template['source_tree'],
    public_recipient_spki=template['recipient_spki_sha256'],escrow_tool_sha256=template['escrow_tool_sha256'],
    actual_SQL_native_owner_crypto_network_or_CI=False,production_approved=False,capacity_approved=False,HA_approved=False)
provenance=dict(kind='M05_STATIC_SOURCE_SCOPE',version=1,base=BASE,merge_stage_commit=git('rev-parse','HEAD').decode().strip(),
    runtime_zero_diff=True,runtime_uta_tree=runtime,runtime_directory_materialized=False,full_restore=False,
    controller_only_namespace_constants_changed_from_fixedFS=True,controller_function_AST_count=len(functions(tree)),
    workflow_discovery=workflow,unaffected_assets_sha256=checks,MANIFEST_sha256=h((ROOT/'MANIFEST.in').read_bytes()),
    test_sha256={name:h((ROOT/'tests'/name).read_bytes()) for name in tests},
    actual_marker_absent=True,actual_marker_ancestor_path_changes_absent=True,actualMe643_not_ancestor=True,
    no_business_or_controller_imports_by_preparation=True,combined_PURE_or_build_or_load_executed=False,next_run_permitted=False)
for name,value in [('once05-registration-template.json',template),('policy-first-pending.json',policy),('static-provenance.json',provenance)]:
    with (OUT/name).open('x') as f:json.dump(value,f,indent=2,sort_keys=True);f.write('\n')
print(json.dumps({'phase':'CODE_METADATA_AST_ONLY','runtime6010_zero_diff':True,'functions_AST_same_fixedFS':len(functions(tree)),
    'both_workflows_cover_selected_tests':len(tests),'strict_marker_fields':len(template),'FS_independent_review':'PENDING','next_run_permitted':False},sort_keys=True))
