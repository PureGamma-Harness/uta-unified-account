"""Pure AST/literal witnesses against retained initial runner; no product import."""
import ast
import json
from pathlib import Path

here = Path(__file__).resolve().parent
runner = ast.parse((here/'run_one_long_phase.py').read_text())
source = ast.parse(Path('/workspace/uta-credit-v2-py310-candidate/tools/run_managed_long.py').read_text())
preflight = next(n for n in source.body if isinstance(n,ast.FunctionDef) and n.name=='preflight')
ret = next(n for n in preflight.body if isinstance(n,ast.Return))
actual_keys = [k.value for k in ret.value.keys if isinstance(k,ast.Constant) and type(k.value) is str]
pre = {'status':'PREFLIGHT_ONLY_NOT_STARTED','service_started':False,
       'producer_source_commit':'909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0',
       'observer_freeze_commit':'909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0',
       'base_plan_sha256':'plan','amendment_sha256':'amend',
       'qualification':{'code_commit':'909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0','tests_run':1801},
       'production_approved':False,'capacity_10000_per_s_passed':False,
       'financial_6h_passed':False,'live_coverage_passed':False}
assert set(pre)-{'base_plan_sha256','amendment_sha256'} <= set(actual_keys)
parts=[n for n in runner.body if isinstance(n,ast.FunctionDef) and n.name in {'need','verify_receipt'}]
parts += [n for n in runner.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='FLAGS' for t in n.targets)]
ns={'SOURCE':pre['producer_source_commit']}
exec(compile(ast.Module(body=parts,type_ignores=[]),'<retained pure receipt functions>','exec'),ns)
try:
 ns['verify_receipt']('long-preflight',{'exit_code':0,'stdout_complete':True,'phase':'long-preflight','structured_stdout':pre},
                      {},{'plan_sha256':'plan','amendment_sha256':'amend','qualification':{'actual_executed_tests_each':1801}})
except ValueError as e:
 receipt={'observed':'REJECTED_REAL_SOURCE_SHAPE','code':str(e),'actual_missing_keys':sorted(set(ns['FLAGS'])-set(actual_keys))}
else:raise AssertionError('initial missing-fields counterexample did not reject')
cls=next(n for n in runner.body if isinstance(n,ast.ClassDef) and n.name=='Live')
methods=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in {'budget','post_hash_clock'}]
compiled=ast.ClassDef(name='ClockSubject',bases=[],keywords=[],body=methods,decorator_list=[])
exec(compile(ast.fix_missing_locations(ast.Module(body=[compiled],type_ignores=[])),'<retained pure clock methods>','exec'),ns)
obj=ns['ClockSubject']();obj.root={'issued_wall_ns':1,'valid_until_wall_ns':100,'issued_boottime_ns':1,'valid_until_boottime_ns':100}
obj.deadline=75;obj.children=[];ticks=iter([{'wall_ns':74,'boottime_ns':74},{'wall_ns':76,'boottime_ns':76}]);obj.clock=lambda:next(ticks)
endpoint=obj.post_hash_clock()
assert endpoint['boottime_ns']>=obj.deadline
print(json.dumps({'kind':'PURE_COUNTEREXAMPLES_NOT_EXECUTION','runner_sha256':'960ddbcc09a46052706c732526d923f5bdd5caaaf3287782cd21e11521c632de',
 'R1_actual_preflight_shape':receipt,'R2_post_hash_clock':{'accepted_endpoint':endpoint,'phase_deadline':obj.deadline,
 'witness':'budget validates first clock74 but returned second clock76 is unchecked'}},indent=2,sort_keys=True))
