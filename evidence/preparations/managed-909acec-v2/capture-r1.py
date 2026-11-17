"""Metadata-only admission capture. Never status/observe/SQL/signals/mkdir.

Requires root's explicit metadata-only GO. Original JSON clocks are retained.
Frozen helper covers producer/proc; f96/latest/contingency checks are separate.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import time

sys.dont_write_bytecode = True
FROZEN = Path('/workspace/uta-credit-v2-py310-candidate')
SOURCE = '909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0'
JOB = Path('/workspace/uta-soak-runs/formal-20261116T213613Z-88755a9')
OBSERVER = JOB/'observer-20261116T221001Z-f96dfd8'
OLD_SCRIPT = Path('/workspace/uta-soak-observer-f96dfd8/tools/soak_monitor.py')
SCRIPT_SHA = '5329bcdb2668eda44635558f4153305306be608cb3803099c61e50dbc26e2efd'
OBSERVER_SOURCE = 'f96dfd8d6b1ca6f5ae28ac771c886baf4fdeb30e'
OLD_SOURCE = '88755a9f2ba3bb672ca5d354b3037796f00c6611'
DEADLINE = 1794951373820942405
THRESHOLD = 17_448_304_640
FLOOR = 256*1024**2
EXPECTED = {4471:'210004',8784:'412799'}


def need(condition, code):
    if not condition:
        raise ValueError(code)


def number(value):
    need(type(value) in (int,float) and math.isfinite(value) and value >= 0, 'clock_or_heartbeat_type_unknown')
    return value


def inventory(path):
    """Directory-FD anchored nofollow metadata only; no file contents opened."""
    flags = os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC
    result = []
    def walk(fd, parts):
        need(len(parts)<=16 and len(result)<20000, 'observer_inventory_unbounded')
        with os.scandir(fd) as entries:
            for entry in entries:
                s = os.stat(entry.name,dir_fd=fd,follow_symlinks=False)
                need(s.st_uid==os.geteuid(), 'observer_inventory_uid_changed')
                relative = '/'.join((*parts,entry.name))
                if stat.S_ISDIR(s.st_mode):
                    child = os.open(entry.name,flags,dir_fd=fd)
                    try:
                        opened = os.fstat(child)
                        need((opened.st_dev,opened.st_ino)==(s.st_dev,s.st_ino), 'observer_directory_identity_changed')
                        walk(child,(*parts,entry.name))
                    finally:
                        os.close(child)
                elif stat.S_ISREG(s.st_mode):
                    result.append({'relative_path':relative,'bytes':s.st_size,'allocated_bytes':s.st_blocks*512})
                else:
                    raise ValueError('observer_inventory_symlink_or_special')
    fd = os.open(path,flags)
    try:
        root = os.fstat(fd)
        need(root.st_uid==os.geteuid() and stat.S_IMODE(root.st_mode)==0o700,'observer_directory_not_private')
        walk(fd,())
    finally:
        os.close(fd)
    return result


def capture(profile_hash, phase, command_hash):
    started = time.time_ns()
    sys.path.insert(0,str(FROZEN))
    spec = importlib.util.spec_from_file_location('frozen_prepare_for_metadata',FROZEN/'tools/prepare_managed_stability.py')
    prepare = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prepare)
    need(Path(prepare.__file__).resolve()==FROZEN/'tools/prepare_managed_stability.py','wrong_prepare_source')
    before = {str(pid):prepare._process_metadata(pid) for pid in EXPECTED}
    # Pure JSON/proc/fs routine: never prepare(), invoke(), status or SQLite.
    helper = prepare.cohost_budget(10*1024**3)
    progress,pmtime,phash = prepare._stable_metadata(JOB/'progress.json')
    meta,_,mhash = prepare._stable_metadata(OBSERVER/'observer.json')
    latest,lmtime,lhash = prepare._stable_metadata(OBSERVER/'latest.json')
    files = inventory(OBSERVER)
    stages = []
    with os.scandir(JOB.parent) as entries:
        candidates = sorted(entry.name for entry in entries if re.fullmatch(r'\.soak-observer-stage-[a-z0-9_]{8}',entry.name))
    for name in candidates:
        stages.extend(inventory(JOB.parent/name))
    argv_raw = Path('/proc/8784/cmdline').read_bytes()
    need(len(argv_raw)<=65536,'observer_argv_oversized')
    argv = argv_raw.rstrip(b'\0').split(b'\0')
    allowed = {}
    for index,argument in enumerate(argv):
        for key in (b'--interval',b'--max-bytes',b'--max-observations'):
            if argument==key:
                need(index+1<len(argv),'observer_argv_incomplete')
                need(key.decode() not in allowed,'observer_argv_duplicate')
                allowed[key.decode()]=argv[index+1].decode('ascii')
            elif argument.startswith(key+b'='):
                need(key.decode() not in allowed,'observer_argv_duplicate')
                allowed[key.decode()]=argument[len(key)+1:].decode('ascii')
    need(str(OLD_SCRIPT).encode() in argv and b'--watch' in argv,'observer_executed_script_or_watch_changed')
    need(float(allowed.get('--interval','60'))==60 and int(allowed.get('--max-bytes',str(64*1024**2)))==64*1024**2
        and int(allowed.get('--max-observations','18000'))==18000,'observer_cli_policy_changed')
    source_fd = os.open(OLD_SCRIPT,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    with os.fdopen(source_fd,'rb') as source_stream:
        source_before = os.fstat(source_stream.fileno())
        source_raw = source_stream.read(1024**2+1)
        source_after = os.fstat(source_stream.fileno())
    need(stat.S_ISREG(source_before.st_mode) and source_before.st_uid==os.geteuid()
        and (source_before.st_dev,source_before.st_ino,source_before.st_size,source_before.st_mtime_ns)==
        (source_after.st_dev,source_after.st_ino,source_after.st_size,source_after.st_mtime_ns)
        and len(source_raw)<=1024**2 and sha256(source_raw).hexdigest()==SCRIPT_SHA,'observer_script_hash_changed')
    need(meta.get('observer_source_commit')==OBSERVER_SOURCE and meta.get('source_sha256')==SCRIPT_SHA
        and meta.get('interval_seconds')==60 and meta.get('max_bytes')==64*1024**2,'observer_original_metadata_policy_changed')
    need(latest.get('observer_script_sha256')==SCRIPT_SHA and latest.get('producer_source_commit')==OLD_SOURCE
        and latest['producer_status'].get('source_commit')==OLD_SOURCE,'observer_latest_source_changed')
    need(progress.get('deadline_ns')==latest['producer_status'].get('deadline_ns')==latest['assessment'].get('original_deadline_ns')==DEADLINE,
         'old_original_deadline_changed')
    need(progress.get('status')=='running' and progress.get('stored_status')=='running' and progress.get('process_alive') is True,'producer_not_running')
    need(latest['assessment'].get('alerts')==[],'observer_latest_alert_or_unknown')
    after = {str(pid):prepare._process_metadata(pid) for pid in EXPECTED}
    for pid,birth in EXPECTED.items():
        first,last = before[str(pid)],after[str(pid)]
        need(first['birth']==last['birth']==birth and last['state'] in {'R','S','D','I'}
            and first['uids']==last['uids'] and all(uid==os.geteuid() for uid in last['uids']), 'original_pid_birth_uid_not_live')
    now = time.time_ns()
    po,lo = progress.get('observed_ns'),latest.get('observed_ns')
    need(type(po) is int and type(lo) is int and 0<po<=now and 0<lo<=now and 0<pmtime<=now and 0<lmtime<=now,'future_or_invalid_original_clock')
    page,lage = (now-po)/1e9,(now-lo)/1e9
    phb,lhb = number(progress.get('heartbeat_age_seconds')),number(latest['assessment'].get('heartbeat_age_seconds'))
    effective_p,effective_l = phb+page,lhb+lage
    need(now-started<=15*10**9 and page<=15 and (now-pmtime)/1e9<=15 and abs(pmtime-po)<=15*10**9
         and effective_p<=15 and effective_l<=30,'original_metadata_or_effective_heartbeat_stale')
    logical = sum(row['bytes'] for row in files)
    stage = sum(row['bytes'] for row in stages)
    observations = [row for row in files if re.fullmatch(r'observation-[0-9]{6}\.json',row['relative_path'])]
    need(bool(observations) and max(row['bytes'] for row in observations)<=65536,'observer_floor_snapshot_stress_assumption_exceeded')
    projected = (math.ceil(21600/60)+1)*(65536+512)+(math.ceil(21600/3600)+1)*65536+3*1024**2
    need(logical+stage+projected<FLOOR,'conditional_observer_contingency_insufficient')
    # Fresh after inventory: do not reuse earlier helper's filesystem observation.
    free = __import__('shutil').disk_usage(JOB).free
    need(free>=THRESHOLD,'fresh_combined_free_floor_unavailable')
    now = time.time_ns()
    page,lage = (now-po)/1e9,(now-lo)/1e9
    effective_p,effective_l = phb+page,lhb+lage
    need(now-started<=15*10**9 and 0<=page<=15 and (now-pmtime)/1e9<=15
        and effective_p<=15 and effective_l<=30,'metadata_expired_during_capture')
    valid_until = min(now+15*10**9,po+15*10**9,pmtime+15*10**9,
        po+int((15-phb)*1e9),lo+int((30-lhb)*1e9))
    need(valid_until>now,'admission_has_no_remaining_lifetime')
    return {'synthetic':True,'format':1,'status':'ADMISSION_METADATA_COMPONENT_PASS_NOT_PHASE_GO',
        'source_commit':SOURCE,'profile_sha256':profile_hash,'phase':phase,'phase_command_sha256':command_hash,
        'captured_wall_ns':now,'capture_started_wall_ns':started,'captured_utc':datetime.fromtimestamp(now/1e9,timezone.utc).isoformat(),
        'captured_boottime_ns':time.clock_gettime_ns(time.CLOCK_BOOTTIME),'valid_until_wall_ns':valid_until,
        'maximum_capture_ttl_seconds':15,'use_requires_recomputed_original_heartbeat_ages':True,
        'original_progress_observed_ns':po,'original_latest_observed_ns':lo,'original_progress_mtime_ns':pmtime,
        'original_latest_mtime_ns':lmtime,'original_progress_heartbeat_age_seconds':phb,'original_latest_heartbeat_age_seconds':lhb,
        'effective_progress_heartbeat_seconds_at_capture':effective_p,'effective_latest_heartbeat_seconds_at_capture':effective_l,
        'producer_heartbeat_limit_seconds':15,'independent_latest_heartbeat_limit_seconds':30,
        'source_boot':prepare.COHOST_BOOT,'original_processes_before':before,'original_processes_after':after,
        'producer_source_commit':OLD_SOURCE,'observer_source_commit':OBSERVER_SOURCE,'observer_script_sha256':SCRIPT_SHA,
        'observer_interval_seconds':60,'observer_default_post_write_software_threshold_bytes':64*1024**2,
        'observer_max_observations':18000,'observer_original_no_alerts':True,'allowlisted_observer_cli':allowed,
        'original_progress_sha256':phash,'original_observer_metadata_sha256':mhash,'original_latest_sha256':lhash,
        'observer_current_logical_bytes':logical,'all_matching_external_staging_bytes':stage,
        'projected_additional_6h_stress_assumption_bytes':projected,'conditional_floor_bytes':FLOOR,
        'conditional_floor_is_hard_quota':False,'fresh_free_bytes':free,'required_free_bytes':THRESHOLD,
        'arithmetic_margin_bytes':free-THRESHOLD,'producer_helper_component_passed':helper['metadata_process_gate_passed'],
        'helper_does_not_cover_independent_observer_conditions':True,'new_job_started':False,'phase_execution_authorized':False,
        'financial_ready_inferred':False,'production_approved':False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile-sha256',required=True)
    parser.add_argument('--phase',required=True)
    parser.add_argument('--command-sha256',required=True)
    parser.add_argument('--output',required=True,type=Path)
    args = parser.parse_args()
    need(re.fullmatch('[0-9a-f]{64}',args.profile_sha256) and re.fullmatch('[0-9a-f]{64}',args.command_sha256),'invalid_bound_hash')
    need(re.fullmatch('[a-z][a-z0-9-]{0,63}',args.phase),'invalid_phase')
    need(args.output.is_absolute() and args.output.parent==Path('/tmp') and args.output.name.startswith('uta-909-admission-') and args.output.suffix=='.json','external_unique_tmp_record_required')
    try:
        value = capture(args.profile_sha256,args.phase,args.command_sha256)
    except (OSError,ValueError,KeyError,TypeError,MemoryError) as error:
        value = {'synthetic':True,'status':'UNKNOWN_OR_NO_GO','source_commit':SOURCE,'phase':args.phase,
            'profile_sha256':args.profile_sha256,'phase_command_sha256':args.command_sha256,
            'captured_wall_ns':time.time_ns(),'error_type':type(error).__name__,
            'error_digest':sha256(str(error).encode()).hexdigest(),
            'error_code':str(error) if type(error) is ValueError and re.fullmatch('[a-z][a-z0-9_]{0,95}',str(error)) else None,
            'phase_execution_authorized':False,'financial_ready_inferred':False,'new_job_started':False}
    raw = (json.dumps(value,sort_keys=True,indent=2)+'\n').encode()
    fd = os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    with os.fdopen(fd,'wb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())
    print(json.dumps({'file':str(args.output),'sha256':sha256(raw).hexdigest(),'status':value['status'],
        'valid_until_wall_ns':value.get('valid_until_wall_ns'),'phase_execution_authorized':False}))
    return 0 if value['status']=='ADMISSION_METADATA_COMPONENT_PASS_NOT_PHASE_GO' else 1


if __name__=='__main__':
    raise SystemExit(main())
