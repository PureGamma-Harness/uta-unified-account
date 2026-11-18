"""Git/files/AST-only PREP materializer. Never creates an executable marker."""
import ast
from hashlib import sha256
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent
BASE='665e178db90dd729954e5cffa7897f9db6958132'
SOURCE='909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0'
BRANCH='refs/heads/perf/approved-m0-20261117-04';REGISTRATION='independent-m0-20261117-04'
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def old(path):return git('show',BASE+':'+path)
def digest(raw):return sha256(raw).hexdigest()
controller_path='tools/independent_m0_controller.py';workflow_path='.github/workflows/independent-m0-once.yml'
controller=(ROOT/controller_path).read_bytes();workflow=(ROOT/workflow_path).read_bytes()
expected=old(controller_path).replace(b"APPROVED_BRANCH = 'refs/heads/perf/approved-m0-20261117-03'",b"APPROVED_BRANCH = 'refs/heads/perf/approved-m0-20261117-04'").replace(b"REGISTRATION_ID = 'independent-m0-20261117-03'",b"REGISTRATION_ID = 'independent-m0-20261117-04'")
assert controller==expected
assert workflow==old(workflow_path).replace(b'perf/approved-m0-20261117-03',b'perf/approved-m0-20261117-04')
assert workflow.count(b'perf/approved-m0-20261117-04')==2
tree=ast.parse(controller);prior=ast.parse(old(controller_path))
functions=lambda value:{n.name:ast.dump(n) for n in value.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
assert functions(tree)==functions(prior)
assert b'ref: 909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0\n          path: workload' in workflow
assert b'uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683' in workflow
unchanged_paths=['.github/workflows/independent-m0.yml','tools/m0_stream_escrow.py',
    'config/m0-stream-recipient-public.pem','config/m0-stream-recipient-public-metadata.json',
    'docs/evidence/independent-actions-m0/once-registration-template.json']
unchanged={p:{'sha256':digest((ROOT/p).read_bytes()),'same_as_665e':old(p)==(ROOT/p).read_bytes()} for p in unchanged_paths}
assert all(v['same_as_665e'] for v in unchanged.values())
template=json.loads(old('docs/evidence/independent-actions-m0/once-registration-template.json'))
template.update(execution_authorized=False,registration_id=REGISTRATION,branch=BRANCH,
    control_commit='0'*40,controller_sha256=digest(controller),workflow_sha256=digest(workflow),
    workspace_boot_id='00000000-0000-0000-0000-000000000000',workspace_hostname_sha256='0'*64,
    workspace_recorded_at='1970-01-01T00:00:00+00:00')
expected_keys=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='validate_once_manifest').body[0].value
assert set(template)==ast.literal_eval(expected_keys) and len(template)==19
assert template['source_commit']==SOURCE and template['budgets']['minimum_fresh_free_bytes']==2348810240
assert template['execution_authorized'] is False and template['control_commit']=='0'*40
assert git('ls-tree','HEAD','config/independent-m0-approved.json')==b''
assert subprocess.run(['git','show-ref','--verify','--quiet',BRANCH],cwd=ROOT).returncode==1
assert not (ROOT/'uta').exists()
needed=[SOURCE,'39151b745418e70c23fc786a484beee3dc429594',BASE,
    'c71ed1756168072e0d8daea207a0d086a6dd1171','07c3dc6c3d8a6cbd239e3463b55f8904cac99340',
    'dfd62ae6fbbdad51b5e1b3507318b343cdc314b5','598f6719dd529ff3db359415f1cdd256a49c11b2',
    '85bdc4ef2e9a3298a711cf70f9a179e8dd1557ec','f605b96c4714c744b65403bbfe3861f68f62d768']
for ref in needed:assert git('cat-file','-t',ref).strip()==b'commit'
sparse=Path(git('rev-parse','--git-path','info/sparse-checkout').decode().strip())
source_tree=git('rev-parse',SOURCE+'^{tree}').decode().strip()
assert source_tree=='cee60bc0b5413551030300e065d0dcaac6a7ff55'
required=[controller_path,workflow_path,*unchanged_paths,
    'tests/test_independent_m0_controller.py','tests/test_independent_m0_integrity.py',
    'tests/test_independent_m0_checkout_ref.py','tests/test_independent_m0_escrow.py',
    'tests/test_independent_m0_resource_race.py','tests/test_independent_m0_diagnostics.py']
assert all((ROOT/p).is_file() for p in required)
spent=[{'registration':'01','marker':'c71ed1756168072e0d8daea207a0d086a6dd1171','run_id':'44169093697','outcome':'FIRST_CHECKOUT_FAILURE_RUNTIME_SKIPPED'},
    {'registration':'02','marker':'07c3dc6c3d8a6cbd239e3463b55f8904cac99340','run_id':'44172126501','outcome':'B_UNKNOWN_P_NOT_RUN'},
    {'registration':'03','marker':'dfd62ae6fbbdad51b5e1b3507318b343cdc314b5','run_id':'44179679904','outcome':'B_UNKNOWN_P_NOT_RUN_3_OF_4_CIPHERS'}]
policy=dict(kind='M04_PREP_ONLY',version=1,next_run_permitted=False,execution_authorized=False,
    next_run_permitted_is_prep_status_not_runtime_gate=True,registration_id=REGISTRATION,branch=BRANCH,
    marker_path='config/independent-m0-approved.json',marker_created=False,trigger_ref_created=False,
    push_performed=False,workflow_dispatched=False,network_performed=False,tests_executed_for_namespace_candidate=False,
    final_root_execution_approval='REQUIRED_AFTER_FIXED_C_INDEPENDENT_REVIEW',
    d1_component={'candidate_commit':BASE,'independent_review_status_at_prep':'PENDING_NOT_ATTESTED_BY_AUTHOR'},
    source_commit=SOURCE,source_tree=source_tree,controller_sha256=digest(controller),workflow_sha256=digest(workflow),
    marker_format=2,marker_exact_field_count=19,spent_registrations=spent,
    first_push_consumes_registration_even_on_failure=True,rerun_recreate_or_supplement_P_allowed=False,
    command_spec=template['command_spec'],budgets=template['budgets'],
    retention={'mode':template['retention_mode'],'escrow_tool_sha256':template['escrow_tool_sha256'],
        'recipient_spki_sha256':template['recipient_spki_sha256'],'cipher_origin_is_provider_chain_not_recipient_encryption':True},
    production_approved=False,capacity_approved=False,ha_approved=False)
provenance=dict(kind='M04_STATIC_PREP_PROVENANCE',version=1,base_commit=BASE,source_commit=SOURCE,source_tree=source_tree,
    controller_sha256=digest(controller),once_workflow_sha256=digest(workflow),
    all_controller_functions_AST_equal_to_665e=True,function_count=len(functions(tree)),
    controller_change='Only APPROVED_BRANCH and REGISTRATION_ID constants',
    once_workflow_change='Only two exact branch literals03->04',unchanged_bytes=unchanged,
    original03_template_unchanged=True,needed_commit_objects_present=needed,
    required_materialized_files={p:digest((ROOT/p).read_bytes()) for p in required},
    sparse_rule_lines=len(sparse.read_text().splitlines()),sparse_rules_sha256=digest(sparse.read_bytes()),
    runtime_directory_materialized=False,full_restore_performed=False,
    global93_cleanup_recounted=False,scope='Only required refs/files checked; cleanup global count not independently recounted.',
    static_checks_passed=True,pure_tests_executed=False,actual_workload_or_crypto_or_SQL=False,
    actual_root_private_key_read=False,next_run_permitted=False)
for name,value in [('once04-registration-template.json',template),('once04-policy.json',policy),('once04-prep-provenance.json',provenance)]:
    with (OUT/name).open('x') as f:json.dump(value,f,indent=2,sort_keys=True);f.write('\n')
print(json.dumps({'phase':'PREP_ONLY','next_run_permitted':False,'functions_AST_same':len(functions(tree)),
    'necessary_history_objects':len(needed),'marker_fields':len(template),'static_checks_passed':True,'tests_executed':False},sort_keys=True))
