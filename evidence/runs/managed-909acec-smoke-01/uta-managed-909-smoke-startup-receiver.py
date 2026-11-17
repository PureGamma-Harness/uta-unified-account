"""One-shot receiver for root-authored startup observation only."""
import importlib.util,json,os,sys,time
from pathlib import Path
from hashlib import sha256
BASE=Path('/workspace/uta-managed-909acec-prepare')
SOURCE=Path('/workspace/uta-credit-v2-py310-candidate')
PROFILE=BASE/'benchmarks/profiles/managed-909acec-v2-qualified-conditional.json'
GUARD=BASE/'evidence/preparations/managed-909acec-v2/consume_guard.py'
assert sha256(GUARD.read_bytes()).hexdigest()=='f31cca779de58db8fedfd31c5f48069483cffa67c803aea6327ee73fcf930602'
assert sha256(PROFILE.read_bytes()).hexdigest()=='8f48d7835c3b3d3ad53fbebfe955c611ba815adbddfe3281fb008fdd4b99c87a'
spec=importlib.util.spec_from_file_location('phase_guard',GUARD);guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
sys.dont_write_bytecode=True;sys.path.insert(0,str(SOURCE))
from tools import run_managed_long as transport
assert Path(transport.__file__).resolve()==SOURCE/'tools/run_managed_long.py'
run=time.time_ns();prefix=Path('/tmp')/f'uta-909-smoke-startup-receiver-{run}'
def save(label,value):
 p=Path(str(prefix)+'-'+label+'.json');raw=(json.dumps(value,sort_keys=True,indent=2)+'\n').encode()
 fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
 with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 print(json.dumps({'receipt':str(p),'sha256':sha256(raw).hexdigest(),**{k:v for k,v in value.items() if k in ('status','wrapper_identity','driver_identity','outer_budget','exit_code')}}),flush=True)
 return p
save('ready',{'status':'WAITING_ROOT_SPECIFIC_GO_NO_JOB_STARTED','receiver_pid':os.getpid(),'source_commit':'909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0'})
seen=set();deadline=time.monotonic()+180;child=None
while time.monotonic()<deadline:
 for path in sorted(Path('/tmp').glob('uta-909-root-go-smoke-observe-*.json')):
  if str(path) in seen:continue
  try:
   raw=path.read_bytes();go=json.loads(raw);argv=go['exact_argv'];snapshot=Path(go['snapshot_file'])
   if go.get('phase')!='smoke-observe' or go.get('stage')!='startup':continue
   assert go['command_sha256']=='01ee5675028f081843196c3e645603af0973f44294affa48cb45008b39d5691d'
   checked=guard.consume_guard(PROFILE,argv,snapshot,go,now_wall_ns=time.time_ns(),now_boottime_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME),current_boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
  except (ValueError,KeyError,TypeError,AssertionError,OSError):
   seen.add(str(path));continue
  # The parent root explicitly authorized this exact root-authored file scope.
  child=transport.Pipes(argv,SOURCE)
  save('started',{'status':'ACTUAL_AUTHORIZED_STARTUP_OBSERVATION_STARTED','root_go_file':str(path),
   'root_go_sha256':sha256(raw).hexdigest(),'snapshot_file':str(snapshot),'snapshot_sha256':go['snapshot_sha256'],
   'exact_argv':argv,'wrapper_identity':child.identity(),'admission_guard':checked,'actual_popen_wall_ns':time.time_ns(),
   'other_phase_or_long_authorized':False})
  break
 if child is not None:break
 time.sleep(.05)
if child is None:
 save('no-go',{'status':'NO_VALID_ROOT_GO_NO_PROCESS_STARTED'});raise SystemExit(1)
smoke=Path('/workspace/uta-managed-observer-runs/909acec-smoke-20261117-01');recorded=False
while child.process.poll() is None:
 launch=smoke/'observer/launch.json';budget=smoke/'control/outer-budget.json'
 if not recorded and launch.exists() and budget.exists():
  data=json.loads(launch.read_bytes());outer=json.loads(budget.read_bytes())
  save('driver',{'status':'ACTUAL_ORIGINAL_DRIVER_IDENTITY','driver_identity':data,'outer_budget':outer});recorded=True
 time.sleep(.1)
result=child.result();result['structured_stdout']=json.loads(child.results['stdout']['raw']) if child.results['stdout']['complete'] and child.results['stdout']['raw'] else None
save('result',{'status':'STARTUP_OBSERVE_INVOKE_FINISHED','result':result,'exit_code':result['exit_code'],'no_other_phase_executed':True})
raise SystemExit(0 if result['exit_code']==0 else 1)
