"""First baseline-only AST disposition counterexamples; never imports UTA or SQLite."""
import ast
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path('/workspace/uta-batch-disposition-contract')
PINS = {
 'uta/durable_batches.py':'14d80716062832b3529512ca14cc9df03043a50f5550197b0a30af261ea11d32',
 'uta/durable_commands.py':'64e49fe427506bfd22031b31e35d0e9665b2eb3a9d2b32ec89ffab2eb3c15fd8',
 'uta/service.py':'9c68ee82b07b66d5272cb820399c7bf6971759bfe1497acf46ac839e95ba7034',
}
class DenyProductImports:
 def find_spec(self, fullname, path=None, target=None):
  if fullname.split('.')[0] in {'uta','sqlite3','_sqlite3'}:
   raise RuntimeError('unauthorized product/SQLite import')
sys.meta_path.insert(0,DenyProductImports())
def audit(event,args):
 if event.startswith(('sqlite3.','socket.','subprocess.','ctypes.')) or event in {'os.fork','os.forkpty','os.posix_spawn','os.kill','os.killpg'}:
  raise RuntimeError('unauthorized execution capability')
sys.addaudithook(audit)
assert os.sched_getaffinity(0)=={1}
assert not {'uta','sqlite3','_sqlite3'} & set(sys.modules)
started=time.monotonic_ns()
trees={}
for name,pin in PINS.items():
 data=(ROOT/name).read_bytes()
 assert sha256(data).hexdigest()==pin,name
 trees[name]=ast.parse(data)
cls=next(n for n in trees['uta/durable_batches.py'].body if isinstance(n,ast.ClassDef) and n.name=='BatchStore')
method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_verify_outcome')
json_def=next(n for n in trees['uta/service.py'].body if isinstance(n,ast.FunctionDef) and n.name=='_json')
term_def=next(n for n in trees['uta/durable_commands.py'].body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='_TERMINAL' for t in n.targets))
# Only these exact definitions execute, not any module imports/DB methods.
class BatchRecoveryUnknown(Exception):pass
ns={'json':json,'BatchRecoveryUnknown':BatchRecoveryUnknown}
standalone=ast.ClassDef(name='BatchStore',bases=[],keywords=[],body=[method],decorator_list=[])
module=ast.fix_missing_locations(ast.Module(body=[json_def,term_def,standalone],type_ignores=[]))
exec(compile(module,'<frozen-disposition-AST-only>','exec'),ns)
store=ns['BatchStore']()
ids=['cmd:A','cmd:B','cmd:C']
content={'members':[{'command_id':cid} for cid in ids]}
def case(name,executed,recorded,actual,expected,disposition='COMMITTED'):
 value={'executed':executed,'commands':[{'command_id':cid,'state':state} for cid,state in zip(ids,recorded)]}
 row={'disposition':disposition,'content':json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)}
 current=[{'command_id':cid,'state':state} for cid,state in zip(ids,actual)]
 try:
  result=store._verify_outcome(row,deepcopy(content),current)
  observed=True
  assert result==value
 except BatchRecoveryUnknown:
  observed=False
 return {'name':name,'executed':executed,'recorded_states':recorded,'actual_states':actual,'disposition':disposition,
         'expected_acceptance':expected,'observed_acceptance':observed,'passed':observed is expected}
cases=[
 case('legal_nonprefix_subsequence',['cmd:A','cmd:C'],['SUCCEEDED','PENDING','REJECTED'],['SUCCEEDED','PENDING','REJECTED'],True),
 case('legal_no_execution',[],['PENDING']*3,['PENDING']*3,True),
 case('legal_prior_quarantine_not_executed',['cmd:B'],['QUARANTINED','SUCCEEDED','PENDING'],['QUARANTINED','SUCCEEDED','PENDING'],True),
 case('legal_recovered_pending_later_terminal',[],['PENDING']*3,['SUCCEEDED','PENDING','REJECTED'],True,'RECOVERED'),
 case('illegal_reversed_execution_order',['cmd:C','cmd:A'],['SUCCEEDED']*3,['SUCCEEDED']*3,False),
 case('illegal_execution_claims_quarantine',['cmd:A'],['QUARANTINED','PENDING','PENDING'],['QUARANTINED','PENDING','PENDING'],False),
 case('existing_rule_rejects_duplicate_execution',['cmd:A','cmd:A'],['SUCCEEDED']*3,['SUCCEEDED']*3,False),
 case('existing_rule_rejects_nonmember_execution',['cmd:Z'],['SUCCEEDED']*3,['SUCCEEDED']*3,False),
]
passed=all(c['passed'] for c in cases)
print(json.dumps({'scope':'ONCE_BASELINE_AST_METHOD_ONLY_FAKE_ROWS_NO_SQL_OR_PRODUCT_IMPORT','baseline':'909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0','source_pins':PINS,
 'method_AST_sha256':sha256(ast.dump(method,include_attributes=False).encode()).hexdigest(),
 'actual_cpu_ids':sorted(os.sched_getaffinity(0)),'elapsed_ns':time.monotonic_ns()-started,
 'cases':cases,'passed':passed,'counterexamples':sum(not c['passed'] for c in cases),
 'full_module_imports':0,'actual_SQL_CLI_worker_signal_network_attempts':0,'production_approved':False},sort_keys=True))
raise SystemExit(0 if passed else 1)
