"""Read only exact local Git/files/AST; writes D1 contract + invariant report."""
import ast
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent
BASE='ab933bec61d5c4be3e40c1a337f8ce55705ba48d'
def blob(path):return subprocess.check_output(['git','show',BASE+':'+path],cwd=ROOT)
def hashed(raw):return sha256(raw).hexdigest()
path='tools/independent_m0_controller.py'
old=ast.parse(blob(path));new=ast.parse((ROOT/path).read_bytes())
def functions(tree):return {node.name:node for node in tree.body if isinstance(node,(ast.FunctionDef,ast.ClassDef))}
a,b=functions(old),functions(new)
names=['_sqlite_aux_location','_fresh_resource_scan','tree_bytes','resource_usage','child_argv','command_spec','budget_spec',
    'validate_once_manifest','validate_environment','registration_proof','source_snapshot','load_owned_runner',
    'case_driver','case_pipeline','case_worker','supervised_case','cases_sequence','project_summary','project_arrivals',
    'verify_population','verify_timing_footer','profile_semantic']
same={name:ast.dump(a[name])==ast.dump(b[name]) for name in names}
assert all(same.values())
class AnnotationOnly(ast.NodeTransformer):
    def visit_Assign(self,node):
        if len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id=='scope':return None
        return self.generic_visit(node)
    def visit_Call(self,node):
        node=self.generic_visit(node)
        if isinstance(node.func,ast.Name) and node.func.id=='_resource_need':
            return ast.Call(func=ast.Name(id='need',ctx=ast.Load()),args=node.args[:2],keywords=[])
        if isinstance(node.func,ast.Name) and node.func.id=='_resource_lstat':
            return ast.Call(func=ast.Attribute(value=node.args[0],attr='lstat',ctx=ast.Load()),args=[],keywords=[])
        if isinstance(node.func,ast.Name) and node.func.id=='_resource_entries':
            node.keywords=[k for k in node.keywords if k.arg!='diagnostic_scope']
        return node
normal={name:ast.dump(a[name])==ast.dump(AnnotationOnly().visit(deepcopy(b[name]))) for name in ['_known_missing_sqlite_aux','_tree_bytes_once','case_bytes']}
assert all(normal.values())
unchanged_paths=['tools/m0_stream_escrow.py','tools/test_m0_stream_escrow_fixture.py',
    'config/m0-stream-recipient-public.pem','config/m0-stream-recipient-public-metadata.json',
    'docs/evidence/independent-actions-m0/once-registration-template.json']
unchanged={p:{'unchanged':blob(p)==(ROOT/p).read_bytes(),'sha256':hashed((ROOT/p).read_bytes())} for p in unchanged_paths}
assert all(v['unchanged'] for v in unchanged.values())
workflow={}
for p in ['.github/workflows/independent-m0.yml','.github/workflows/independent-m0-once.yml']:
    raw=(ROOT/p).read_bytes();prior=blob(p)
    assert raw.replace(b'            /tests/test_independent_m0_diagnostics.py\n',b'')==prior
    assert raw.count(b'ref: 909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0')==1
    workflow[p]={'sha256':hashed(raw),'only_change':'new pure D1 test sparse path','source_ref_exact':True}
spec=importlib.util.spec_from_file_location('static_d1',ROOT/path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
schema={'kind':'M0_RESOURCE_DIAGNOSTIC','version':1,
    'exact_fields':['kind','version','phase','scope','operation','errno','catalogue_label','unknown_relative_path_sha256','primary_code'],
    'phase_enum':sorted(m.DIAGNOSTIC_PHASES),'scope_enum':sorted(m.DIAGNOSTIC_SCOPES),
    'operation_enum':sorted(m.DIAGNOSTIC_OPERATIONS),'catalogue_label_enum':sorted(m.DIAGNOSTIC_LABELS),
    'primary_code_enum':sorted(m.DIAGNOSTIC_CODES),'errno':'exact int 0..4095; bool/float/nonfinite forbidden',
    'unknown_relative_path_sha256':'null or 64 lowercase hex; known label requires null',
    'maximum_record_bytes':4096,'creation':'owner-only directory; O_EXCL/O_NOFOLLOW 0600; flush/fsync',
    'write_status_enum':['RECORDED','ALREADY_RECORDED','UNAVAILABLE'],
    'collection_status_enum':['COMPLETE','UNAVAILABLE'],
    'active_emission_phases':['CRYPTO_CAPABILITY','RUNTIME_PROBE','CASE_B','ESCROW_B','CASE_P','ESCROW_P'],
    'reserved_not_emitted_by_current_main':['PREFLIGHT','FINAL_PUBLIC_VERIFY'],
    'child_terminal_gate_diagnostic_coverage':False,'original_four_streams_modified':False,
    'new_resource_exemptions':False,'existing_false_template_changed':False,'new_registration_created':False,
    'budget_spec':m.budget_spec(),'resource_scan_attempts':m.RESOURCE_SCAN_ATTEMPTS,'resource_scan_retry_ns':m.RESOURCE_SCAN_RETRY_NS,
    'source_commit':m.SOURCE,'source_tree':m.SOURCE_TREE,'controller_sha256':hashed((ROOT/path).read_bytes()),
    'crypto_sha256':unchanged['tools/m0_stream_escrow.py']['sha256'],'command_spec':m.command_spec(),
    'historical_M03_precise_missing_path':'NOT_RECORDED; root cause remains unknown',
    'actual_financial_or_crypto_load_executed_for_D1':False,'production_approved':False}
changed=subprocess.check_output(['git','diff','--name-only',BASE],cwd=ROOT).decode().splitlines()
assert set(changed)=={'tools/independent_m0_controller.py',*workflow}
report={'kind':'D1_STATIC_INVARIANTS','version':1,'git_base':BASE,
    'recorded_at':datetime.now(timezone.utc).isoformat(),'ast_exact_equal':same,'annotation_normalized_ast_equal':normal,
    'unchanged_bytes':unchanged,'workflow_diffs':workflow,
    'normalization_limit':'Only declared annotation wrappers removed; not a proof of arbitrary semantic equivalence.',
    'resource_bucket_change':'Only exact D1 root names are newly metered as existing cleanup; no old rule removed.',
    'tracked_dirty_paths':changed,'runtime_source_modified':False,'actual_financial_load':False,
    'actual_private_key_or_quarantine_read':False,'passed':True}
for name,value in [('d1-contract.json',schema),('d1-static-invariants.json',report)]:
    with (OUT/name).open('x') as f:json.dump(value,f,indent=2,sort_keys=True);f.write('\n')
print(json.dumps({'ast_exact_equal':len(same),'annotation_normalized_equal':len(normal),'unchanged_files':len(unchanged),
    'workflow_only_D1_test_path':len(workflow),'passed':True},sort_keys=True))
