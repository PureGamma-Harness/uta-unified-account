"""One-shot detached P1 supervisor; never rewrite an original run or launch twice."""
from datetime import datetime,timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import sys
import time

SOURCE_REF='912f2a4e5ed74f7a3fbf892ff0172e4eacc9c45a'
RUNTIME_REF='5750e12d60dbf7f8414b4e837e076a60c93a23bc'
HARNESS_SHA='c8de834b0dcd96a1617ab5d32f593088de871923497052bde53104998b4eab90'
FLOOR=17448304640

def utc():return datetime.now(timezone.utc).isoformat()
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,data):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as stream:
        json.dump(data,stream,sort_keys=True,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
def identity(pid):
    proc=Path('/proc')/str(pid);raw=(proc/'stat').read_text();fields=raw[raw.rfind(')')+2:].split()
    return {'pid':pid,'birth':fields[19],'state':fields[0],'ppid':int(fields[1]),
            'uid':proc.stat().st_uid,'boot':Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
def validate(args):
    assert all(p.is_absolute() for p in (args.source,args.harness,args.outer))
    assert sha(args.harness)==HARNESS_SHA
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=args.source,text=True).strip();assert head==SOURCE_REF
    assert subprocess.check_output(['git','status','--porcelain'],cwd=args.source,text=True)==''
    files={}
    for name in subprocess.check_output(['git','ls-tree','-r','--name-only',RUNTIME_REF,'--','uta'],cwd=args.source,text=True).splitlines():
        raw=(args.source/name).read_bytes();assert raw==subprocess.check_output(['git','show',RUNTIME_REF+':'+name],cwd=args.source)
        files[name]=hashlib.sha256(raw).hexdigest()
    assert len(files)==64
    return files
def start(args):
    validate(args)
    assert not args.outer.exists() and not args.outer.is_symlink()
    parent=args.outer.parent.stat();assert parent.st_uid==os.geteuid() and not stat.S_IMODE(parent.st_mode)&0o077
    free=shutil.disk_usage('/workspace').free;assert free>=FLOOR+16*1024**2
    args.outer.mkdir(mode=0o700)
    command=[sys.executable,'-I','-B',str(Path(__file__).resolve()),'supervise',
             '--source',str(args.source),'--harness',str(args.harness),'--outer',str(args.outer)]
    with (args.outer/'supervisor-stdout.txt').open('xb') as out,(args.outer/'supervisor-stderr.txt').open('xb') as err:
        child=subprocess.Popen(command,cwd=Path(__file__).resolve().parent,stdin=subprocess.DEVNULL,
                               stdout=out,stderr=err,start_new_session=True,close_fds=True)
        try:owned=identity(child.pid)
        except FileNotFoundError:owned={'pid':child.pid,'parent_birth_capture_missing':True,'returncode_if_observed':child.poll()}
    record={'started_at':utc(),'supervisor_actual_Popen':owned,'supervisor_command':command,
        'supervisor_code_sha256':sha(Path(__file__)),'source_commit':SOURCE_REF,'runtime_commit':RUNTIME_REF,
        'harness_sha256':HARNESS_SHA,'stdin':'DEVNULL','stdout_stderr':'exclusive private files',
        'start_new_session':True,'free_bytes_before_start':free,'no_exec_server_pipe_for_supervisor_streams':True}
    save(args.outer/'start-record.json',record)
    print(json.dumps({'status':'STARTED_ONE_SHOT','outer':str(args.outer),'supervisor':owned,
                      'supervisor_code_sha256':record['supervisor_code_sha256']}),flush=True)
def supervise(args):
    os.sched_setaffinity(0,{4});begin=utc();mono=time.monotonic_ns()
    owned_supervisor=identity(os.getpid());save(args.outer/'supervisor-owner.json',owned_supervisor)
    hashes=validate(args)
    command=[sys.executable,'-I','-B',str(args.harness),'--source',str(args.source),
             '--private',str(args.outer/'cases'),'--result',str(args.outer/'probe-result.json')]
    reason=None;reaped=False;pidfd=None
    with (args.outer/'probe-stdout.txt').open('xb') as out,(args.outer/'probe-stderr.txt').open('xb') as err:
        child=subprocess.Popen(command,cwd=args.harness.parents[2],stdin=subprocess.DEVNULL,
                               stdout=out,stderr=err,start_new_session=True,close_fds=True)
        child_identity=identity(child.pid)
        if hasattr(os,'pidfd_open'):
            try:pidfd=os.pidfd_open(child.pid)
            except OSError:pidfd=None
        save(args.outer/'probe-actual-Popen.json',{'identity':child_identity,'command':command,
            'affinity_inherited_from_supervisor':[4],'pidfd_bound':pidfd is not None})
        try:
            code=child.wait(timeout=max(.001,30-(time.monotonic_ns()-mono)/1e9));reaped=True
        except subprocess.TimeoutExpired:
            reason='P1_WATCHDOG_30_SECONDS'
            current=identity(child.pid)
            assert all(current[k]==child_identity[k] for k in ('pid','birth','uid','boot'))
            if pidfd is not None and hasattr(signal,'pidfd_send_signal'):
                signal.pidfd_send_signal(pidfd,signal.SIGKILL)
            else:
                # Still-unreaped direct Popen child plus identical birth; no old PID lookup.
                child.kill()
            try:code=child.wait(timeout=1);reaped=True
            except subprocess.TimeoutExpired:code=None;reason='P1_WATCHDOG_OWNED_CHILD_REAP_UNKNOWN'
        finally:
            if pidfd is not None:os.close(pidfd)
        out.flush();os.fsync(out.fileno());err.flush();os.fsync(err.fileno())
    streams={name:{'bytes':(args.outer/name).stat().st_size,'sha256':sha(args.outer/name)}
             for name in ('probe-stdout.txt','probe-stderr.txt')}
    report_path=args.outer/'probe-result.json';probe=json.loads(report_path.read_bytes()) if report_path.exists() else None
    source_same=all(sha(args.source/name)==digest for name,digest in hashes.items()) and sha(args.harness)==HARNESS_SHA
    subject_passed=(reason is None and reaped and code==0 and probe is not None and
        probe.get('status')=='PASS' and probe.get('case_count')==4 and probe.get('source_unchanged') is True and source_same)
    result={'source_commit':SOURCE_REF,'runtime_commit':RUNTIME_REF,'harness_sha256':HARNESS_SHA,
        'supervisor_code_sha256':sha(Path(__file__)),'supervisor_identity':owned_supervisor,
        'actual_probe_identity':child_identity,'started_at':begin,'raw_closed_hashed_at':utc(),
        'child_exit_code':code,'owned_child_wait_reaped':reaped,'watchdog_reason':reason,
        'raw_private_streams':streams,'source_runtime_unchanged':source_same,
        'probe_result_present':probe is not None,'probe_result_sha256':sha(report_path) if report_path.exists() else None,
        'probe_case_count':probe.get('case_count') if probe else None,'probe_status':probe.get('status') if probe else None,
        'subject_passed_before_final_result_serialization':subject_passed,
        'no_original_or_long_job_authority_touched':True,'production_approved':False}
    save(args.outer/'supervisor-result.json',result)
    # Measure after result fsync, without fabricating its own future write time.
    elapsed=time.monotonic_ns()-mono
    completion={'completed_at':utc(),'elapsed_ns_after_result_fsync':elapsed,
        'supervisor_result_sha256':sha(args.outer/'supervisor-result.json'),
        'raw_close_fsync_hash_and_result_fsync_precede_clock':True,
        'completion_record_serialization_follows_clock':True,
        'within30seconds_at_recorded_clock':elapsed<=30*10**9,
        'accepted_scoped_P1':subject_passed and elapsed<=30*10**9,'production_approved':False}
    save(args.outer/'completion.json',completion)
    return 0 if completion['accepted_scoped_P1'] else 1
def status(args):
    report={}
    for name in ('start-record.json','supervisor-owner.json','probe-actual-Popen.json','supervisor-result.json','completion.json'):
        path=args.outer/name
        report[name]=json.loads(path.read_bytes()) if path.exists() else None
    print(json.dumps(report,indent=2))
def main():
    os.umask(0o077)
    p=argparse.ArgumentParser();p.add_argument('operation',choices=('start','supervise','status'))
    p.add_argument('--source',type=Path,required=True);p.add_argument('--harness',type=Path,required=True);p.add_argument('--outer',type=Path,required=True)
    args=p.parse_args()
    if args.operation=='start':start(args);return 0
    if args.operation=='supervise':return supervise(args)
    status(args);return 0
if __name__=='__main__':raise SystemExit(main())
