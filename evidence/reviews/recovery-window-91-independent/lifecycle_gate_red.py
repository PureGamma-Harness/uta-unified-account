"""Pure hypothetical serialized-result vectors; no native test or SQL execution."""
import ast
from hashlib import sha256
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[3]
CANDIDATE='8f25e9edcf2bcece056165ed911302a919893cac'
PATH='evidence/runs/recovery-horizon91/trace_original91_lifecycle.py'
raw=subprocess.check_output(['git','show',CANDIDATE+':'+PATH],cwd=ROOT)
assert sha256(raw).hexdigest()=='48446ef1f9f0fbc1a70d4bbcd1b2c50ce844ad7aae2a5ae14249a9c3d4aa8e21'
tree=ast.parse(raw)
assignment=next(n for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Subscript) and isinstance(t.value,ast.Name) and t.value.id=='report' and isinstance(t.slice,ast.Constant) and t.slice.value=='strict_observation_complete' for t in n.targets))
expression=compile(ast.Expression(assignment.value),'pure-hypothetical-worker-report','eval')
def vector(complete,errors,other=None):
 report={'whole_budget_met':True,'source_unchanged':True,'all_266_match_original':True,'worker_observation_complete':complete,'final_owned_identities':[]}
 worker={'errors':errors,**(other or {})}
 env={'timed_out':False,'report':report,'source_error':None,'worker_result_error':None,'cleanup':[],'session_scan_error':None,'session_members':[],'event_error':None,'spawn_balanced':True,'observation_unknown':False,'event_hash_valid':True,'worker_result':worker,'all':all}
 return eval(expression,{'__builtins__':{}},env)
positive=vector(True,0,{'tests_run':1,'failures':0,'case_passed':True})
malformed=vector('false',False,{'tests_run':0,'failures':-1,'case_passed':'false'})
boolean_error=vector(True,False)
float_error=vector(True,0.0)
assert positive is malformed is boolean_error is float_error is True
print(json.dumps({'scope':'pure extracted gate expression, no runtime/native/SQL','candidate':CANDIDATE,'driver_sha256':sha256(raw).hexdigest(),'valid_synthetic_report_strict':positive,'malformed_fields':{'worker_observation_complete':'false','errors':False,'tests_run':0,'failures':-1,'case_passed':'false'},'malformed_report_strict':malformed,'boolean_error_count_strict':boolean_error,'float_error_count_strict':float_error,'finding':'malformed worker JSON can be classified safe unless final helper/controller exact-type and one-case contract rejects it','native_run':False,'production_approved':False},indent=2))
