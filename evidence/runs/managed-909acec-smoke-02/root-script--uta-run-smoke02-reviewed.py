from pathlib import Path
import json,hashlib,subprocess,time,os,datetime
base=Path('/workspace/uta-managed-909acec-prepare');folder=base/'evidence/preparations/managed-909acec-v3';controller=folder/'smoke_controller_v3.py';envelope=folder/'conditional-envelope.json';profile=base/'benchmarks/profiles/managed-909acec-v3-smoke02-conditional.json'
expected={'controller_sha256':'e88a575ef31f12d60f1c42bfdc86e003b013620488b5ac9b4685a1a1a5a445b3','envelope_sha256':'17902f4669a81761354a68a7ea23be670b1e2547502c0d4a2eadd44d5cad79aa','profile_sha256':'0d4beaafd20dcc1f3f4627db17ad3ea3ec72bb66377da0f7a9e69bfc1cc39850'}
for key,path in [('controller_sha256',controller),('envelope_sha256',envelope),('profile_sha256',profile)]:assert hashlib.sha256(path.read_bytes()).hexdigest()==expected[key]
source=Path('/workspace/uta-credit-v2-py310-candidate');assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()=='909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0';assert subprocess.check_output(['git','status','--porcelain'],cwd=source,text=True)==''
e=json.loads(envelope.read_text());p=json.loads(profile.read_text());assert not Path(e['smoke_scratch']).exists() and not Path(e['private_controller_output']).exists()
root=Path('/workspace/uta-managed-observer-runs/909acec-smoke-20261117-02-root-private');root.mkdir(mode=0o700,exist_ok=False)
go={**expected,'authorized':True,'scope':'EXACT_SEVEN_SMOKE_STAGES_ONCE_NO_LONG','source_commit':'909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0','root_approved_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'root_approved_wall_ns':time.time_ns(),'root_approved_boot_ns':time.clock_gettime_ns(time.CLOCK_BOOTTIME),'independent_review_commit':'91ad2f204b4ba1f56ae071dc5169b07ab7a74990','controller_preparation_commit':'f2ad840f91a41bc098fedadc3ffc30c590f38bc6','maximum_producer_starts':1,'whole_smoke_seconds_from_first_Popen':150,'stage_snapshot_and_guard_required':True,'no_production_capacity_ha_or_long_approval':True}
record=root/'root-approved-envelope.json';record.write_text(json.dumps(go,indent=2)+'\n');record.chmod(0o600)
command=[p['python'],'-B',str(controller),'--envelope',str(envelope),'--root-approved-envelope-record',str(record)]
start=time.monotonic_ns();started=datetime.datetime.now(datetime.timezone.utc).isoformat()
with (root/'controller.stdout').open('xb') as out,(root/'controller.stderr').open('xb') as err:
 os.chmod(out.name,0o600);os.chmod(err.name,0o600)
 child=subprocess.Popen(command,cwd=source,stdout=out,stderr=err,stdin=subprocess.DEVNULL,close_fds=True,start_new_session=True)
 (root/'launcher-started.json').write_text(json.dumps({'command':command,'controller_PID':child.pid,'started_at':started,'launcher_start_monotonic_ns':start,'first_producer_deadline_not_reset':True},indent=2)+'\n')
 print(json.dumps({'actual_controller_PID':child.pid,'root_go_file':str(record),'root_go_sha256':hashlib.sha256(record.read_bytes()).hexdigest(),'started_at':started,'scope':'ONLY smoke02 seven stages once NO_LONG'}),flush=True)
 rc=child.wait();out.flush();err.flush();os.fsync(out.fileno());os.fsync(err.fileno())
raw=(root/'controller.stdout').read_bytes();stderr=(root/'controller.stderr').read_bytes()
try:result=json.loads(raw)
except Exception:result={'full_smoke_passed':False,'controller_stdout_unknown':True}
first=Path(e['private_controller_output'])/'produce-actual-Popen.json';first_boot=json.loads(first.read_text())['first_Popen_boottime_ns'] if first.exists() else None
end_boot=time.clock_gettime_ns(time.CLOCK_BOOTTIME);elapsed=(end_boot-first_boot)/1e9 if first_boot is not None else None
final={'source_commit':go['source_commit'],'controller_preparation_commit':go['controller_preparation_commit'],'root_approval_sha256':hashlib.sha256(record.read_bytes()).hexdigest(),'controller_exit_code':rc,'started_at':started,'finished_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'launcher_elapsed_seconds_including_initial_admission_wait':(time.monotonic_ns()-start)/1e9,'actual_first_producer_to_closed_streams_and_hashes_seconds':elapsed,'actual_outer_150_passed':elapsed is not None and elapsed<=150,'controller_original_result':result,'controller_stdout_sha256':hashlib.sha256(raw).hexdigest(),'controller_stderr_sha256':hashlib.sha256(stderr).hexdigest(),'final_smoke_passed':rc==0 and result.get('full_smoke_passed') is True and elapsed is not None and elapsed<=150,'attestation_serialization_follows_recorded_endpoint':True,'long_authorized':False,'production_approved':False}
(root/'final-outer-attestation.json').write_text(json.dumps(final,indent=2)+'\n');print(json.dumps(final),flush=True)
