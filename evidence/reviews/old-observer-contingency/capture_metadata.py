"""Owned review output only; read existing JSON/proc/source and nofollow metadata.

Never opens database contents, invokes producer status, or signals a process.
"""
from collections import Counter
from datetime import datetime,timezone
from hashlib import sha256
import json,math,os,re,signal,stat,sys,time
from pathlib import Path

JOB=Path('/workspace/uta-soak-runs/formal-20261116T213613Z-88755a9')
OBSERVER=JOB/'observer-20261116T221001Z-f96dfd8'
PRODUCER='88755a9f2ba3bb672ca5d354b3037796f00c6611'
SCRIPT=Path('/workspace/uta-soak-observer-f96dfd8/tools/soak_monitor.py')
SCRIPT_SHA='5329bcdb2668eda44635558f4153305306be608cb3803099c61e50dbc26e2efd'
BOOT='6339d4fc-a9e7-4c10-a591-1e70a14322ff'
DEADLINE=1794951373820942405
EXPECTED={4471:'210004',8784:'412799'}
FLOOR=256*1024**2
GIB=1024**3
FRESH=15


def existing_json(path):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as stream:
        first=os.fstat(stream.fileno());assert stat.S_ISREG(first.st_mode) and first.st_uid==os.geteuid()
        raw=stream.read(1024**2+1);last=os.fstat(stream.fileno())
    assert len(raw)<=1024**2 and (first.st_dev,first.st_ino,first.st_size,first.st_mtime_ns)==(last.st_dev,last.st_ino,last.st_size,last.st_mtime_ns)
    return json.loads(raw),{'bytes':len(raw),'sha256':sha256(raw).hexdigest(),'device':first.st_dev,'inode':first.st_ino}


def process(pid):
    fields=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
    status=Path(f'/proc/{pid}/status').read_text()
    uids=[int(value) for value in next(line for line in status.splitlines() if line.startswith('Uid:')).split()[1:]]
    return {'pid':pid,'birth':fields[19],'state':fields[0],'uids':uids,'affinity_observed_only':sorted(os.sched_getaffinity(pid))}


def tree(path):
    flags=os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC
    records=[]
    def walk(fd,parts):
        with os.scandir(fd) as entries:
            for entry in entries:
                metadata=os.stat(entry.name,dir_fd=fd,follow_symlinks=False)
                relative='/'.join((*parts,entry.name))
                row={'relative_path':relative,'device':metadata.st_dev,'inode':metadata.st_ino,'mode':stat.S_IMODE(metadata.st_mode),'uid':metadata.st_uid,'bytes':metadata.st_size,'allocated_bytes':metadata.st_blocks*512,'mtime_ns':metadata.st_mtime_ns}
                assert metadata.st_uid==os.geteuid()
                if stat.S_ISREG(metadata.st_mode):row['type']='regular'
                elif stat.S_ISDIR(metadata.st_mode):
                    row['type']='directory';child=os.open(entry.name,flags,dir_fd=fd)
                    try:
                        opened=os.fstat(child);assert (opened.st_dev,opened.st_ino)==(metadata.st_dev,metadata.st_ino)
                        walk(child,(*parts,entry.name))
                    finally:os.close(child)
                else:raise ValueError('unexpected symlink or special observer output')
                records.append(row)
    descriptor=os.open(path,flags)
    try:
        root=os.fstat(descriptor);assert root.st_uid==os.geteuid() and stat.S_IMODE(root.st_mode)==0o700
        walk(descriptor,())
    finally:os.close(descriptor)
    return records


def main(output):
    assert os.getpid() not in EXPECTED
    os.sched_setaffinity(0,{3})  # Review process only; old affinities are observed.
    signal.alarm(6);begin=time.monotonic();capture_start=time.time_ns()
    before={str(pid):process(pid) for pid in EXPECTED}
    progress,progress_hash=existing_json(JOB/'progress.json')
    latest,latest_hash=existing_json(OBSERVER/'latest.json')
    records=tree(OBSERVER)
    # Conservatively count all matching private external stage directories;
    # no other job directory or file contents are opened.
    stages=[]
    with os.scandir(JOB.parent) as entries:
        candidates=[entry.name for entry in entries if re.fullmatch(r'\.soak-observer-stage-[a-z0-9_]{8}',entry.name)]
    for name in candidates:
        stages.append({'name':name,'files':tree(JOB.parent/name),'attribution':'all matching stages counted conservatively; no PID attribution claimed'})
    raw=Path('/proc/8784/cmdline').read_bytes();assert len(raw)<=65536
    argv=raw.split(b'\0');allowed={}
    for index,arg in enumerate(argv):
        for key in (b'--max-bytes',b'--interval',b'--max-observations'):
            if arg==key:
                assert index+1<len(argv);allowed[key.decode()]=argv[index+1].decode('ascii')
            elif arg.startswith(key+b'='):
                allowed[key.decode()]=arg[len(key)+1:].decode('ascii')
    interval=float(allowed.get('--interval','60'));assert math.isfinite(interval) and 10<=interval<=3600
    max_bytes=int(allowed.get('--max-bytes',str(64*1024**2)))
    max_observations=int(allowed.get('--max-observations','18000'))
    after={str(pid):process(pid) for pid in EXPECTED}
    now=time.time_ns()
    regular=[r for r in records if r['type']=='regular']
    observations=[r for r in regular if re.fullmatch(r'observation-[0-9]{6}\.json',r['relative_path'])]
    stage_regular=[r for stage in stages for r in stage['files'] if r['type']=='regular']
    used=sum(r['bytes'] for r in regular);stage_used=sum(r['bytes'] for r in stage_regular)
    largest=max(r['bytes'] for r in observations)
    progress_age=(now-progress['observed_ns'])/1e9
    latest_age=(now-latest['observed_ns'])/1e9
    effective_progress=max(0,progress_age)+progress['heartbeat_age_seconds']
    effective_latest=max(0,latest_age)+latest['assessment']['heartbeat_age_seconds']
    rows_6h=math.ceil(21600/interval)+1
    remaining=max(0,(DEADLINE-now)/1e9)
    def estimate(seconds):
        rows=math.ceil(seconds/interval)+1
        # Stress assumption, not a bound:64KiB JSON +512B manifest growth per
        # sample, hourly copies, plus3MiB for latest/staging/final metadata.
        return rows*(65536+512)+(math.ceil(seconds/3600)+1)*65536+3*1024**2
    projected=estimate(21600)
    checks={'capture_duration_within15':(now-capture_start)/1e9<=FRESH,
        'boot_same':Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT,
        'PID_birth_alive_UID_affinity_same':all(before[str(pid)]==after[str(pid)] and after[str(pid)]['birth']==birth and after[str(pid)]['state'] not in ('Z','X','x') and set(after[str(pid)]['uids'])=={os.geteuid()} for pid,birth in EXPECTED.items()),
        'observer_source_same':sha256(SCRIPT.read_bytes()).hexdigest()==SCRIPT_SHA==latest['observer_script_sha256'],
        'producer_source_same':progress['source_commit']==latest['producer_source_commit']==latest['producer_status']['source_commit']==PRODUCER,
        'original_deadline_same':progress['deadline_ns']==latest['producer_status']['deadline_ns']==latest['assessment']['original_deadline_ns']==DEADLINE,
        'producer_running':progress['status']=='running' and progress['process_alive'] is True,
        'latest_no_alerts':latest['assessment']['alerts']==[],
        'current_effective_HB_30':-1<=progress_age and effective_progress<=30,
        'latest_effective_HB_30':-1<=latest_age and effective_latest<=30,
        'floor_exceeds_current_plus_stressed_next6h':used+stage_used+projected<FLOOR,
        'observed_max_record_below_stress_assumption':largest<=65536,
        'CLI_and_original_software_threshold_consistent':max_bytes==64*1024**2 and max_observations==18000}
    floor_acceptable=all(value is True for value in checks.values())
    value={'captured_utc':datetime.fromtimestamp(now/1e9,timezone.utc).isoformat(),'captured_wall_ns':now,'capture_started_wall_ns':capture_start,'review_cpu':[3],
        'review_wall_seconds':time.monotonic()-begin,'read_inputs':{'progress':progress_hash,'latest':latest_hash},
        'processes_before':before,'processes_after':after,'allowlisted_observer_CLI_fields':allowed,
        'effective_interval_seconds':interval,'source_default_software_threshold_bytes':max_bytes,'source_max_observations':max_observations,
        'observer_regular_files':len(regular),'observer_directories':len(records)-len(regular),'observation_JSON_files':len(observations),'observed_largest_observation_bytes':largest,
        'observer_current_logical_bytes':used,'observer_allocated_bytes':sum(r['allocated_bytes'] for r in regular),'all_matching_external_stage_bytes':stage_used,
        'old_observer_contingency_floor_bytes':FLOOR,'projected_additional_next6h_stress_bytes':projected,'projected_additional_until_original_deadline_stress_bytes':estimate(remaining),
        'remaining_to_original_deadline_seconds':remaining,'original_final_deadline_UTC':'2026-11-17T21:36:13.820942Z',
        'effective_HB_seconds':{'current_progress':effective_progress,'latest_original_assessment':effective_latest},'JSON_age_seconds':{'progress':progress_age,'latest':latest_age},
        'checks':checks,'engineering_floor_verdict':'ACCEPT_CONDITIONAL_SYNTHETIC_COHOSTING' if floor_acceptable else 'NO_GO_CURRENT_METADATA_OR_HEADROOM',
        'OS_hard_quota_proven':False,'disk_reservation_created':False,'guaranteed_future_growth_bound':False,
        'new_execution_GO':False,'root_final_QA_package_free_disk_recheck_required_bytes':17448304640,
        'old_or_new_stability_or_production_approved':False,'scanner_opened_SQL_or_called_status_signal':False,
        'source_proof':'source-proof.json','file_metadata':records,'external_staging_metadata':stages}
    output.write_text(json.dumps(value,indent=2)+'\n')
    signal.alarm(0)
    print(json.dumps({k:value[k] for k in ['captured_utc','engineering_floor_verdict','observer_current_logical_bytes','observer_allocated_bytes','all_matching_external_stage_bytes','projected_additional_next6h_stress_bytes','effective_HB_seconds','JSON_age_seconds','review_wall_seconds']},indent=2))


if __name__=='__main__':
    if len(sys.argv)!=3 or sys.argv[1]!='--output':raise SystemExit('explicit --output NEW_FILE only')
    output=Path(sys.argv[2]);assert not output.exists();main(output)
