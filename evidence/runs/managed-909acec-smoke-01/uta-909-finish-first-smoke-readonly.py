from pathlib import Path
import os,time,json,hashlib,subprocess,importlib.util
b=Path('/workspace/uta-managed-909acec-prepare');p=b/'benchmarks/profiles/managed-909acec-v2-qualified-conditional.json';c=b/'evidence/preparations/managed-909acec-v2/consume_guard.py';cap=Path('/tmp/uta-managed-909-fresh-admission-capture-r2b.py')
assert hashlib.sha256(c.read_bytes()).hexdigest()=='f31cca779de58db8fedfd31c5f48069483cffa67c803aea6327ee73fcf930602'
assert hashlib.sha256(cap.read_bytes()).hexdigest()=='57e87ce1bd10863821cbd0392957515da3b4613b2c756c1c986c947217654aa6'
s=importlib.util.spec_from_file_location('root_readonly_phase_guard',c);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
items=json.loads((b/'evidence/preparations/managed-909acec-v2/exact-phase-commands.json').read_text())['stages'];ph='8f48d7835c3b3d3ad53fbebfe955c611ba815adbddfe3281fb008fdd4b99c87a'
assert hashlib.sha256(p.read_bytes()).hexdigest()==ph
limit=75319110753889
results=[]
for stage in ('final','cold','strict-negative'):
 x=next(x for x in items if x['stage']==stage)
 while time.clock_gettime_ns(time.CLOCK_BOOTTIME)<limit:
  old=json.loads(Path('/workspace/uta-soak-runs/formal-20261116T213613Z-88755a9/observer-20261116T221001Z-f96dfd8/latest.json').read_text());age=(time.time_ns()-old['observed_ns'])/1e9
  if not 0<=age<=18:time.sleep(.05);continue
  snap=Path('/tmp')/f'uta-909-admission-root-{stage}-{time.time_ns()}.json';cmd=[json.loads(p.read_text())['python'],'-B',str(cap),'--profile-sha256',ph,'--phase',x['phase'],'--command-sha256',x['command_sha256'],'--output',str(snap)]
  r=subprocess.run(cmd,capture_output=True,text=True,timeout=10)
  if r.returncode:results.append({'stage':stage,'metadata_exit':r.returncode,'snapshot':str(snap)});time.sleep(.2);continue
  raw=snap.read_bytes();g={'authorized':True,'phase':x['phase'],'stage':stage,'profile_sha256':ph,'command_sha256':x['command_sha256'],'snapshot_sha256':hashlib.sha256(raw).hexdigest(),'snapshot_file':str(snap),'exact_argv':x['argv'],'scope':'ONLY this final readonly first-smoke stage once; live startup/normal/fault NOT_RUN; no long GO'}
  checked=m.consume_guard(p,x['argv'],snap,g,now_wall_ns=time.time_ns(),now_boottime_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME),current_boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip());g['root_approved_wall_ns']=time.time_ns();g['guard_result']=checked
  go=Path('/tmp')/f'uta-909-root-go-{x["phase"]}-{g["root_approved_wall_ns"]}.json';go.write_text(json.dumps(g,indent=2)+'\n');go.chmod(0o600)
  remaining=(limit-time.clock_gettime_ns(time.CLOCK_BOOTTIME))/1e9
  if remaining<=0:results.append({'stage':stage,'status':'NOT_RUN_OUTER_DEADLINE','go':str(go)});break
  started=time.monotonic();invoke=subprocess.run(x['argv'],capture_output=True,timeout=min(20,remaining));out=Path('/tmp')/f'uta-909-first-smoke-{stage}-{time.time_ns()}'
  for suffix,data in [('stdout',invoke.stdout),('stderr',invoke.stderr)]:f=Path(str(out)+'.'+suffix);f.write_bytes(data);f.chmod(0o600)
  result={'stage':stage,'phase':x['phase'],'go_file':str(go),'go_sha256':hashlib.sha256(go.read_bytes()).hexdigest(),'snapshot':str(snap),'snapshot_sha256':g['snapshot_sha256'],'exit_code':invoke.returncode,'wall_seconds':time.monotonic()-started,'private_raw_prefix':str(out),'stdout_sha256':hashlib.sha256(invoke.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(invoke.stderr).hexdigest()};results.append(result);print(json.dumps(result),flush=True);break
 else:results.append({'stage':stage,'status':'NOT_RUN_OUTER_DEADLINE'})
report=Path('/tmp/uta-909-first-smoke-readonly-completion.json');report.write_text(json.dumps({'results':results,'live_observations':'NOT_RUN','full_smoke_passed':False,'new_long_authorized':False},indent=2)+'\n');report.chmod(0o600);print('report',report)
