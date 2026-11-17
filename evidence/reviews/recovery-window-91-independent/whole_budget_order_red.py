"""Pure extracted-finalizer counterexample with synthetic clock and IO functions."""
import ast
from hashlib import sha256
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[3]
CANDIDATE='1e6e7f7c35d9803b13358010d3e984b0acfc1567'
NAME='evidence/runs/recovery-horizon91/run_runtime_ab16_bound.py'
raw=subprocess.check_output(['git','show',CANDIDATE+':'+NAME],cwd=ROOT)
assert sha256(raw).hexdigest()=='2114cb40d74e9899cad8b67473192ae0c3529106e3650c0085b96aa603348202'
tree=ast.parse(raw);sample=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='sample')
final=next(n for n in sample.body if isinstance(n,ast.Try)).finalbody
start=next(i for i,n in enumerate(final) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Subscript) and isinstance(t.value,ast.Name) and t.value.id=='checks' and isinstance(t.slice,ast.Constant) and t.slice.value=='whole_external_budget' for t in n.targets))
stop=next(i for i,n in enumerate(final) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='report' for t in n.targets))+1
clock={'now':29.95}
class SyntheticTime:
 @staticmethod
 def monotonic():return clock['now']
def digest(path):
 if str(path)=='/synthetic/runtime-binary':clock['now']=30.10
 return 'exact-hash'
context={'time':SyntheticTime,'started':0,'checks':{f'prior-{i}':True for i in range(20)},'config':{'files':{'helper.py':'exact-hash'}},'HERE':Path('/synthetic'),'binding':{'files':{'executable':{'path':'/synthetic/runtime-binary','sha256':'exact-hash'}}},'digest':digest,'write_new':lambda *args:None,'output':Path('/synthetic/output'),'technical':[],'forced':[],'slot':{'id':'synthetic','runtime':'A'},'utc':lambda:'synthetic','case_result':{'case_passed':False,'outcome_stage':'OTHER_ASSERTION_FAILURE'},'final_sessions':{}}
module=ast.fix_missing_locations(ast.Module(body=final[start:stop],type_ignores=[]))
exec(compile(module,'pure-controller-finalizer','exec'),context)
report=context['report']
assert report['all_checks'] is True and report['checks']['whole_external_budget'] is True and report['whole_seconds']>30
print(json.dumps({'candidate':CANDIDATE,'controller_sha256':sha256(raw).hexdigest(),'scope':'pure extracted finalizer; synthetic hash/clock/IO only','budget_check_clock':29.95,'posthash_clock':30.10,'captured_report':report,'finding':'stale pre-hash budget flag permits DIAGNOSTIC_SAMPLE_COMPLETE beyond whole30','native_or_SQL_run':False,'production_approved':False},indent=2))
