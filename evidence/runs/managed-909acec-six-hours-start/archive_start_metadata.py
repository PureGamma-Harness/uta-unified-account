"""One authorized metadata/closed-file archive; no SQL, operational CLI or signals."""
from datetime import datetime,timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import time

HERE=Path(__file__).resolve().parent
BASE=Path('/workspace/uta-managed-observer-runs')
JOB=BASE/'909acec-six-hours-20261117'
SOURCE='909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0'
BOOT='6339d4fc-a9e7-4c10-a591-1e70a14322ff'
manifest={'original_exact_copies':[],'private_closed_streams':[],'no_SQL_observer_signal_restart_or_job_write':True}

def read(path,limit=8*1024**2):
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
 with os.fdopen(fd,'rb') as stream:
  before=os.fstat(stream.fileno());raw=stream.read(limit+1);after=os.fstat(stream.fileno())
 assert stat.S_ISREG(before.st_mode) and before.st_uid==os.geteuid() and len(raw)<=limit
 assert (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)
 return raw,{'dev':before.st_dev,'ino':before.st_ino,'bytes':len(raw),'mtime_ns':before.st_mtime_ns,'sha256':sha256(raw).hexdigest()}

def save(name,raw):
 with (HERE/name).open('xb') as f:f.write(raw)

def archive(path,name):
 raw,meta=read(path);value=json.loads(raw)
 # Known synthetic metadata schemas only, never authority/config/authentication bodies.
 def clean(v):
  if isinstance(v,dict):
   assert not set(v)&{'owner_nonce','writer_nonce','nonce','hmac_secret','secret','private_key','password','authorization','signature','auth_nonce'}
   for x in v.values():clean(x)
  elif isinstance(v,list):
   for x in v:clean(x)
 clean(value)
 save(name,raw);manifest['original_exact_copies'].append({'original_path':str(path),'copy':name,**meta})
 return value

for phase in ('long-preflight','long-start'):
 inner=BASE/('909acec-v4-'+phase+'-private');outer=BASE/('909acec-v4-'+phase+'-root-private')
 for folder,prefix in ((inner,phase+'--'),(outer,phase+'--root--')):
  for f in sorted(folder.iterdir()):
   if f.name.endswith('.json'):archive(f,prefix+f.name)
 closed=json.loads((inner/'closed-private-stream-manifest.json').read_bytes())
 for label,row in closed.items():
  raw,meta=read(Path(row['file']),4*1024**2)
  assert row['complete'] is True and row['error'] is None and row['bytes']==row['retained_bytes']==len(raw) and row['sha256']==meta['sha256']
  manifest['private_closed_streams'].append({'phase':phase,'stream':'wrapper-'+label,'original_path':row['file'],**meta,'complete':True,'raw_published':False})
 att=json.loads((outer/'root-phase-attestation.json').read_bytes())
 for label,row in att['raw_private_only'].items():
  raw,meta=read(outer/('runner.'+label),4*1024**2)
  assert row['bytes']==len(raw) and row['sha256']==meta['sha256']
  manifest['private_closed_streams'].append({'phase':phase,'stream':'root-runner-'+label,'original_path':str(outer/('runner.'+label)),**meta,'complete':True,'raw_published':False})
 assert att['runner_exit_code']==0 and att['primary_error'] is None and att['result']['status']=='PHASE_RECEIPT_VERIFIED'

current={}
for rel in ('control/preflight.json','control/preregistered-plan.json','control/observer-amendment.json',
            'control/launch.json','control/supervisor-identity.json','control/observer-identity.json',
            'control/supervisor-heartbeat.json','control/live-coverage.json','observer/baseline.json',
            'observer/latest.json','observer/watch-cli-identity.json','job/progress.json'):
 current[rel]=archive(JOB/rel,'job--'+rel.replace('/','--'))
base=current['observer/baseline.json'];launch=current['control/launch.json'];latest=current['observer/latest.json']
assert base['frozen_commit']==SOURCE and base['driver_pid']==launch['driver_pid']==310039
assert base['driver_birth']==launch['driver_birth']=='8086955' and base['boot_id']==BOOT
assert base['duration_seconds']==21600 and base['planned_rounds']==5400
assert base['deadline_boottime_ns']-base['started_boottime_ns']==21600*10**9
assert latest['synthetic'] is True and latest['redacted'] is True
assert current['job/progress.json']['validation_evidence']['code_commit']==SOURCE
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT

identities=[]
for role,pid,birth in (('supervisor',310035,'8086947'),('original-driver',310039,'8086955'),
                       ('observer-bwrap-monitor',310266,'8087358'),('observer-actual-watch-CLI',310269,'8087359')):
 def proc():
  raw=Path(f'/proc/{pid}/stat').read_text();fields=raw.rsplit(')',1)[1].split()
  return fields[0],fields[19]
 before=proc();status=Path(f'/proc/{pid}/status').read_text().splitlines()
 uids=[int(x) for x in next(x for x in status if x.startswith('Uid:')).split()[1:]]
 argv=Path(f'/proc/{pid}/cmdline').read_bytes();after=proc()
 assert before[1]==after[1]==birth and before[0] in 'RSDI' and after[0] in 'RSDI' and all(x==os.geteuid() for x in uids)
 row={'role':role,'pid':pid,'birth':birth,'boot':BOOT,'state_before':before[0],'state_after':after[0],'uids':uids,'argv_sha256':sha256(argv).hexdigest(),'argv_bytes':len(argv)}
 if role=='observer-actual-watch-CLI':
  args=[x.decode() for x in argv.rstrip(b'\0').split(b'\0')]
  for flag in ('--interval','--frozen-commit','--driver-pid','--driver-birth','--source','--job','--output','--max-private-clone-bytes','--min-private-free-bytes','--max-address-space-bytes'):
   assert args.count(flag)==1;row[flag]=args[args.index(flag)+1]
  assert row['--interval']=='61' and row['--frozen-commit']==SOURCE and row['--driver-pid']=='310039' and row['--driver-birth']=='8086955'
 identities.append(row)
w0=time.time_ns();boot=time.clock_gettime_ns(time.CLOCK_BOOTTIME);w1=time.time_ns()
def stamp(n):return datetime.fromtimestamp(n/1e9,timezone.utc).isoformat()
progress=current['job/progress.json'];coverage=current['control/live-coverage.json']
record={'status':'ACTUALLY_STARTED_FINANCIAL_AND_COVERAGE_STILL_RUNNING_NOT_FINAL','source_commit':SOURCE,'source_root':'/workspace/uta-credit-v2-py310-candidate',
 'profile_sha256':'9ecd5476c347fbf1d767445f6c73a26fde46b026c7008d9b0f24f36e8801213d','preregistration_commit':'923b37845bcb588d8e953d49be978034f28a0de8',
 'preflight_independent_acceptance_commit':'43222eca2bc5c1948fb9ff2de7c07ce772e0838d','single_phase_runner_review_commit':'d0e964ddc58ba62893454d629aa241550141bd2f',
 'actual_clock':{'original_start_boottime_ns':base['started_boottime_ns'],'original_deadline_boottime_ns':base['deadline_boottime_ns'],'duration_seconds':21600,'planned_rounds':5400,'boot':BOOT,
 'UTC_mapping_is_handoff_wall_boot_anchor_not_original_stored_UTC':True,'anchor_wall_before_ns':w0,'anchor_boottime_ns':boot,'anchor_wall_after_ns':w1,
 'mapped_start_utc_range':[stamp(w+base['started_boottime_ns']-boot) for w in (w0,w1)],'mapped_deadline_utc_range':[stamp(w+base['deadline_boottime_ns']-boot) for w in (w0,w1)],'may_cross_Nov18':True},
 'process_metadata':identities,'launch_metadata':launch,'progress_projection':{k:progress.get(k) for k in ('status','elapsed_seconds','planned_rounds','rounds','fault_signals','unresolved_steps','unresolved_faults','resources','verified_tls','logs_verified','final_audit','error')},
 'observer_latest_projection':{k:latest.get(k) for k in ('sample_wall_ns','logical_point','completed_rounds','alerts','active_elapsed_seconds','original_start_boottime_ns','original_deadline_boottime_ns','financial_ready','final_evidence_eligible')},
 'coverage_projection':{k:coverage.get(k) for k in ('coverage_status','samples_observed','counts','financial_golden_counts','logical_point_counts','maximum_observed_consecutive_technical_read_unknown','coverage_no_go_reasons','technical_error_types','technical_error_digests')},
 'snapshots_are_from_different_logical_points':True,'financial_comparisons_across_these_snapshots_not_performed':True,'current_df_free_bytes':__import__('shutil').disk_usage(JOB).free,
 'preflight_service_started_false_is_historical_not_current':True,'all_long_financial_coverage_stability_production_capacity_flags_false':True,
 'financial_6h_passed':False,'live_coverage_passed':False,'continuous_6h_stability_passed':False,'production_approved':False,'capacity_10000_per_s_passed':False,
 'new_start_or_resume_authorized_by_this_archive':False,'original_763_and_first01_remain_NO_GO':True,'no_SQL_additional_observer_status_signal_or_write_to_job':True}
save('actual-start-handoff.json',(json.dumps(record,indent=2,sort_keys=True)+'\n').encode())
save('original-copy-and-private-stream-manifest.json',(json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode())
print(json.dumps({'record':str(HERE/'actual-start-handoff.json'),'copied_JSON':len(manifest['original_exact_copies']),'closed_private_raw_hashes':len(manifest['private_closed_streams']),'actual_clock':record['actual_clock'],'processes':[(x['role'],x['pid'],x['birth']) for x in identities],'progress':record['progress_projection'],'coverage':record['coverage_projection']},indent=2))
