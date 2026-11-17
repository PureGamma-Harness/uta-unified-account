import ast,copy,hashlib,importlib.util,json,os,pathlib,sys,tempfile
ROOT=pathlib.Path.cwd();sys.path.insert(0,str(ROOT/'tools'))
import bind_managed_terminal_evidence as binder
spec=importlib.util.spec_from_file_location('schema_builder_only',ROOT/'tests/test_managed_terminal_binding.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
assert os.sched_getaffinity(0)=={3}
original=ROOT/'evidence/reviews/terminal-binder-alias-followup/first_challenge.py'
tree=ast.parse(original.read_bytes(),filename=str(original))
functions=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
namespace={'copy':copy,'hashlib':hashlib,'json':json,'Path':pathlib.Path,'tempfile':tempfile,'binder':binder,'fixture':fixture}
exec(compile(ast.Module(body=functions,type_ignores=[]),str(original),'exec'),namespace)
cases=[]
def run(name,expected,mutator):
 records=fixture.synthetic_chain();mutator(records)
 result,manifest,pins=namespace['sealed_bundle_result'](records)
 okay=result.get('metadata_chain_bound') is expected and all(result.get(k) is False for k in ('candidate_for_independent_terminal_review','financial_6h_passed','continuous_6h_stability_passed','continuous_24h_stability_passed','capacity_10000_per_s_passed','production_approved','full_risk_engine_reexecution_passed','whole_business_event_reexecution_passed'))
 cases.append({'case':name,'expected_bound':expected,'passed':okay,'result':result,'synthetic_manifest_sha256':manifest})
for name,expected in (('same_numeric_birth_with_leading_zero',False),('finance_watermark_float_alias',False),('same_pid_new_numeric_birth_is_legal',True)):
 run(name,expected,lambda r,name=name:namespace['mutate'](r,name))
for token in (False,'','２','0','0002','1'*20):
 run('invalid_birth_'+str(len(cases)),False,lambda r,token=token:r['cold']['identity'].update(birth=token))
def finance_bool(r):
 wm=copy.deepcopy(r['after']['response']['finance']['watermark']);wm['ledger_sequence']=False
 r['after']['response']['finance']['watermark']=wm
run('financial_watermark_boolean_is_not_zero_count',False,finance_bool)
def wm_extra(r):
 wm=copy.deepcopy(r['after']['response']['finance']['watermark']);wm['unexpected']=0
 r['after']['response']['finance']['watermark']=wm
run('financial_watermark_extra_field_rejected',False,wm_extra)
def receipt_missing(r):
 receipt=copy.deepcopy(r['receipt']);del receipt['watermark_after']['financial']['ledger_hash'];r['receipt']=receipt
run('receipt_nested_structure_mismatch',False,receipt_missing)
run('canonical_largest_allowed_birth_is_distinct',True,lambda r:r['cold']['identity'].update(birth=str(binder.MAX_INTEGER)))
helper_tests=[(True,1,False),(27006,27006.0,False),({'a':[{'n':0}]},{'a':[{'n':False}]},False),({'a':[1,2]},{'a':[1,2]},True),({'a':[1,2]},{'a':[1,2,3]},False)]
helper_okay=all(binder.strict_equal(a,b) is expected for a,b,expected in helper_tests)
cases.append({'case':'recursive_type_and_structure_controls','passed':helper_okay,'comparisons':len(helper_tests)})
result={'source_commit':'4f9efc9e16da108fabe3be0eaec4d9f922dad948','cases':cases,'total_cases':len(cases),'passed_cases':sum(c['passed'] for c in cases),'passed':all(c['passed'] for c in cases),'original12_or18_rerun':False,'live_sql_observer_audit_process_actions':'NOT_RUN','production_approved':False}
print(json.dumps(result,sort_keys=True,indent=2));raise SystemExit(0 if result['passed'] else 1)
