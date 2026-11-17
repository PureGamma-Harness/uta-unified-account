"""Pure extracted finalizer/caller controls using synthetic clocks, paths and IO."""
import ast
from copy import deepcopy
from hashlib import sha256
import json,math,os
from pathlib import Path
import subprocess

os.sched_setaffinity(0,{3})
ROOT=Path(__file__).resolve().parents[3]
CANDIDATE='80fae18c7afafdbb0145e5e8b44741323994b74f'
NAME='evidence/runs/recovery-horizon91/run_runtime_ab16_final.py'
raw=subprocess.check_output(['git','show',CANDIDATE+':'+NAME],cwd=ROOT)
assert sha256(raw).hexdigest()=='5ce9884cfd39238482c0282cf357aab52497b7fbacb395505eecb97f67eec15e'
tree=ast.parse(raw);functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
final=next(n for n in functions['sample'].body if isinstance(n,ast.Try)).finalbody
start=next(i for i,n in enumerate(final) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Subscript) and isinstance(t.value,ast.Name) and t.value.id=='checks' and isinstance(t.slice,ast.Constant) and t.slice.value=='all_code_still_bound' for t in n.targets))
stop=next(i for i,n in enumerate(final) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='report' for t in n.targets))+1
final_module=compile(ast.fix_missing_locations(ast.Module(body=final[start:stop],type_ignores=[])),'pure-final-clock','exec')
def finalizer(posthash_clock):
 clock={'now':29.95}
 class Time:
  @staticmethod
  def monotonic():return clock['now']
 def digest(path):
  if str(path)=='/synthetic/runtime-binary':clock['now']=posthash_clock
  return 'exact-hash'
 env={'time':Time,'math':math,'started':0,'checks':{f'prior-{i}':True for i in range(20)},'config':{'files':{'helper.py':'exact-hash'}},'HERE':Path('/synthetic'),'binding':{'files':{'executable':{'path':'/synthetic/runtime-binary','sha256':'exact-hash'}}},'digest':digest,'write_new':lambda *args:None,'output':Path('/synthetic/output'),'technical':[],'forced':[],'slot':{'id':'synthetic','runtime':'A'},'utc':lambda:'synthetic','case_result':{'case_passed':False,'outcome_stage':'OTHER_ASSERTION_FAILURE'},'final_sessions':{}}
 exec(final_module,env);return env['report']
late=finalizer(30.10);on_time=finalizer(29.99)
assert late['all_checks'] is False and late['checks']['whole_external_budget'] is False and late['whole_seconds']==30.10
assert on_time['all_checks'] is True and on_time['whole_seconds']==29.99
loop=next(n for n in functions['run'].body if isinstance(n,ast.For))
loop_module=compile(ast.fix_missing_locations(ast.Module(body=[loop],type_ignores=[])),'pure-outer-clock','exec')
order=[{'id':f's{i:02d}-{label}','runtime':label} for i,label in enumerate('ABBA'*4,1)]
def caller(sample_elapsed,ordinary_fail=False,raise_after_END=False):
 clock={'now':0.0};files={};called=[]
 class Time:
  @staticmethod
  def monotonic():return clock['now']
 class SavedPath:
  def __init__(self,path):self.path=path
  def __truediv__(self,other):return SavedPath(self.path+'/'+str(other))
  def __str__(self):return self.path
  def exists(self):return self.path in files
 def write_new(path,value):
  assert str(path) not in files
  files[str(path)]=deepcopy(value)
 def digest(path):return sha256(json.dumps(files[str(path)],sort_keys=True).encode()).hexdigest()
 def sample(config,slot,output,sources):
  called.append(slot['id'])
  record={'slot':slot,'status':'DIAGNOSTIC_SAMPLE_COMPLETE','all_checks':True,'case_passed':not ordinary_fail,'outcome_stage':'OTHER_ASSERTION_FAILURE' if ordinary_fail else 'PASS','whole_seconds':29.95}
  write_new(output/'END.json',record);clock['now']+=sample_elapsed
  if raise_after_END:raise OSError('synthetic END tail failure')
  return record
 env={'time':Time,'math':math,'config':{'sample_order':order},'slot':None,'stop':None,'reports':[],'print':lambda *args,**kwargs:None,'json':json,'utc':lambda:'synthetic','sample':sample,'output':SavedPath('/synthetic'),'expected_sources':{},'write_new':write_new,'digest':digest}
 exec(loop_module,env)
 return {'reports':env['reports'],'stop':env['stop'],'called':called,'files':files}
late_END=caller(30.10);ordinary=caller(29.99,ordinary_fail=True);write_error=caller(.1,raise_after_END=True)
assert late_END['called']==['s01-A'] and len(late_END['reports'])==16
assert late_END['reports'][0]['all_checks'] is False and all(r['status']=='NOT_RUN_DUE_TO_SAFETY_STOP' for r in late_END['reports'][1:])
original=late_END['files']['/synthetic/s01-A/END.json'];outer=late_END['files']['/synthetic/s01-A-OUTER-END.json']
assert original['all_checks'] is True and original['whole_seconds']==29.95 and outer['all_checks'] is False
assert outer['original_sample_result']==original and outer['original_sample_END_sha256']==sha256(json.dumps(original,sort_keys=True).encode()).hexdigest()
assert ordinary['called']==[x['id'] for x in order] and ordinary['stop'] is None and all(r['case_passed'] is False and r['all_checks'] is True for r in ordinary['reports'])
assert write_error['called']==['s01-A'] and write_error['reports'][0]['all_checks'] is False and all(r['status']=='NOT_RUN_DUE_TO_SAFETY_STOP' for r in write_error['reports'][1:])
print(json.dumps({'candidate':CANDIDATE,'controller_sha256':sha256(raw).hexdigest(),'scope':'pure extracted finalizer/caller; no native test, SQL, signal or actual runtime invocation','controls':{'late_posthash_stops':late['all_checks'] is False,'on_time_posthash_can_pass':on_time['all_checks'] is True,'same_final_elapsed_for_budget_and_report':late['whole_seconds']==30.10,'late_END_write_stops_remaining15':late_END['reports'][0]['all_checks'] is False,'original_END_preserved_and_hashed':True,'technically_complete_ordinary_FAIL_preserves_ABBA16':True,'END_exception_stops_remaining15':True},'original_1e_red_preserved':True,'all_controls_passed':True,'whole_batch_runtime_approved':False,'production_approved':False},indent=2))
