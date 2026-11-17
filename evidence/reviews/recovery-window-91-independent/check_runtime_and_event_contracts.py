"""Independent synthetic runtime/event controls only; no native workload or SQL."""
from copy import deepcopy
from hashlib import sha256
import json,os
from pathlib import Path
import subprocess

os.sched_setaffinity(0,{3})
ROOT=Path(__file__).resolve().parents[3];CANDIDATE='1e6e7f7c35d9803b13358010d3e984b0acfc1567';PREFIX='evidence/runs/recovery-horizon91/'
def blob(name):return subprocess.check_output(['git','show',CANDIDATE+':'+PREFIX+name],cwd=ROOT)
def pure(name):
 raw=blob(name);space={};exec(compile(raw,name,'exec'),space);return space,sha256(raw).hexdigest()
runtime,runtime_hash=pure('strict_runtime_contract.py');event,event_hash=pure('strict_event_contract.py')
config=json.loads(blob('runtime-ab16-bound-preregistration.json'));binding=config['runtimes']['B']
actual={'version_info':[3,13,18],'python':'3.13.18 (synthetic control)','executable':binding['executable'],'sqlite':'3.46.1','optimize':0,'dont_write_bytecode':True,'flags':'sys.flags(synthetic)','affinity':[2],'environment':deepcopy(binding['environment']),'mapped_libpython':deepcopy(binding['mapped_libpython_expected']),'mapped_libpython_sha256':{p:binding['files']['libpython']['sha256'] for p in binding['mapped_libpython_expected']}}
runtime_results=[]
def check_runtime(name,mutate,expected):
 value=deepcopy(actual);mutate(value);valid=runtime['validate_case_runtime'](value,binding);assert valid is expected,(name,valid)
 runtime_results.append({'name':name,'accepted':valid})
check_runtime('synthetic B exact worker metadata',lambda v:None,True)
check_runtime('actual A version in B slot',lambda v:v.update(version_info=[3,13,5],python='3.13.5 (synthetic)'),False)
check_runtime('resolved wrong executable',lambda v:v.update(executable='/usr/bin/python3.13'),False)
check_runtime('wrong SQLite',lambda v:v.update(sqlite='3.40.1'),False)
check_runtime('wrong library path',lambda v:v.update(mapped_libpython=['/host/libpython3.13.so.1.0']),False)
check_runtime('wrong mapped library hash',lambda v:v.update(mapped_libpython_sha256={p:'0'*64 for p in v['mapped_libpython']}),False)
check_runtime('wrong per-process loader environment',lambda v:v['environment'].update(LD_LIBRARY_PATH='/host/lib'),False)
check_runtime('boolean CPU field',lambda v:v.update(affinity=[True]),False)
check_runtime('float optimization count',lambda v:v.update(optimize=0.0),False)
check_runtime('string bytecode bool',lambda v:v.update(dont_write_bytecode='true'),False)
life={'started':True,'ended':True,'error':None}
worker={'case_passed':False,'evidence_flags':{'observer_post_join':{n:{'is_alive':False,'lifecycle':deepcopy(life)} for n in ('pidfd','code_stack')}}}
events=[]
def add(kind,thread='MainThread',**fields):
 i=len(events)+1;events.append({'kind':kind,'thread':thread,'monotonic_ns':i,'boottime_ns':i,'utc_ns':1000+i,**fields})
for shard,pid in [(0,101),(1,102)]:
 add('spawn_start',shard=shard);add('spawn_return',shard=shard,identity={'pid':pid,'start_ticks':str(pid)})
add('fence_status_start','uta-process-supervisor',call_id=123)
add('fence_status_return','uta-process-supervisor',call_id=123,owner_pid=101,active=False,expires_ns=10,now_ns=20)
add('kill_start','uta-process-supervisor',pid=101);add('kill_return','uta-process-supervisor',pid=101)
for pid in (101,102):add('final_owned_child',pid=pid,pidfd_exited=True,exitcode=0)
for name in ('pidfd','code_stack'):
 add('observer_lifecycle_start',observer=name);add('observer_lifecycle_end',observer=name)
 add('observer_post_join',observer=name,is_alive=False,lifecycle=deepcopy(life))
event_results=[]
def check_event(name,mutate,expected,case=None):
 rows=deepcopy(events);value=deepcopy(worker if case is None else case);mutate(rows,value)
 result=event['validate_events'](rows,value);assert result['valid'] is expected,(name,result)
 event_results.append({'name':name,'accepted':result['valid'],'errors':result['errors']})
check_event('synthetic ordinary FAIL complete original observations',lambda e,w:None,True)
def main_kill(e,w):
 for row in e:
  if row['kind'] in ('kill_start','kill_return'):row['thread']='MainThread'
check_event('router.close MainThread fallback kill',main_kill,False)
def unexpired(e,w):
 for row in e:
  if row['kind']=='fence_status_return':row.update(active=True,expires_ns=30,now_ns=20)
check_event('supervisor kill without expired native witness',unexpired,False)
def wrong_owner(e,w):
 for row in e:
  if row['kind']=='fence_status_return':row['owner_pid']=999
check_event('supervisor kill with another owner witness',wrong_owner,False)
check_event('missing original spawn return',lambda e,w:e.pop(3),False)
check_event('missing final original pidfd exit',lambda e,w:next(r for r in e if r['kind']=='final_owned_child').update(pidfd_exited=False),False)
check_event('missing observer postjoin',lambda e,w:e.pop(),False)
check_event('observer still live',lambda e,w:next(r for r in e if r['kind']=='observer_post_join').update(is_alive=True),False)
check_event('sampling evidence unknown',lambda e,w:e.append({'kind':'sampling_unavailable','thread':'observer','monotonic_ns':100,'boottime_ns':100,'utc_ns':1100}),False)
check_event('unfinished original status call',lambda e,w:e.append({'kind':'fence_status_start','thread':'supervisor','call_id':999,'monotonic_ns':100,'boottime_ns':100,'utc_ns':1100}),False)
check_event('boolean event clock',lambda e,w:e[0].update(monotonic_ns=True),False)
def paired_status_error(e,w):
 for row in e:
  if row['kind']=='fence_status_return':row['kind']='fence_status_error'
 e[:]=[r for r in e if r['kind'] not in ('kill_start','kill_return')]
check_event('fully observed native status error is observation, no kill grant',paired_status_error,True)
print(json.dumps({'candidate':CANDIDATE,'runtime_contract_sha256':runtime_hash,'event_contract_sha256':event_hash,'runtime_controls':runtime_results,'event_controls':event_results,'all_controls_passed':True,'records_are_synthetic_controls_not_native_evidence':True,'native_or_SQL_run':False,'whole_batch_approved':False,'production_approved':False},indent=2))
