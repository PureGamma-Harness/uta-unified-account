"""One finite pure scope per invocation; pinned source, original raw and reap."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import selectors
import stat
import subprocess
import sys
from time import monotonic_ns

ROOT=Path(__file__).resolve().parents[1]


def fresh(directory,name,data):
    descriptor=os.open(directory/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        if os.write(descriptor,data)!=len(data):raise OSError('short private capture write')
        os.fsync(descriptor)
    finally:os.close(descriptor)


def record(directory,name,value):
    fresh(directory,name,(json.dumps(value,sort_keys=True,indent=2)+'\n').encode())


def pins(binding,planpath,plansha,bindingpath,bindingsha):
    observed={}
    for name,expected in binding['inputs'].items():
        path=ROOT/name;info=path.lstat()
        if not stat.S_ISREG(info.st_mode) or path.resolve()!=path:raise ValueError('nonregular capture input')
        raw=path.read_bytes();value={'bytes':len(raw),'sha256':sha256(raw).hexdigest()}
        if value!=expected:raise ValueError('capture source changed: '+name)
        observed[name]=value
    raw=planpath.read_bytes()
    if sha256(raw).hexdigest()!=plansha:raise ValueError('scope plan changed')
    observed['used_scope_plan']={'bytes':len(raw),'sha256':plansha}
    raw=bindingpath.read_bytes()
    if sha256(raw).hexdigest()!=bindingsha:raise ValueError('pure binding changed')
    observed['used_binding']={'bytes':len(raw),'sha256':bindingsha}
    return observed


def main():
    host_start=monotonic_ns();host_deadline=host_start+12_000_000_000
    parser=argparse.ArgumentParser()
    parser.add_argument('--plan',required=True)
    parser.add_argument('--approved-plan-sha256',required=True)
    parser.add_argument('--scope',choices=('model4','negative3'),required=True)
    args=parser.parse_args()
    planpath=Path(args.plan);raw=planpath.read_bytes()
    if sha256(raw).hexdigest()!=args.approved_plan_sha256:raise ValueError('unapproved pure plan bytes')
    plan=json.loads(raw);scope=plan['scopes'][args.scope]
    bindingpath=ROOT/plan['binding']['path'];bindingraw=bindingpath.read_bytes()
    if sha256(bindingraw).hexdigest()!=plan['binding']['sha256']:raise ValueError('pure binding differs')
    binding=json.loads(bindingraw);before=pins(binding,planpath,args.approved_plan_sha256,bindingpath,plan['binding']['sha256'])
    argv=scope['outer_prefix']+scope['target_argv']
    directory=Path(scope['fresh_capture_root']);os.umask(0o077);directory.mkdir(mode=0o700)
    fresh(directory,'capture-source.py',Path(__file__).read_bytes())
    record(directory,'pins-before.json',before)
    record(directory,'intent.json',{'exact_argv':argv,'caller_argv':sys.argv,'scope':args.scope,'source_commit':plan['source_commit'],
        'shared_raw_cap_bytes':32768,'target_raw_bytes':30720,'outer_bytes_including512reserve':2048,
        'capture_semantics':'first attempt only; no discovery/retry; trusted local read pins, not immutable attestation'})
    start=monotonic_ns();child=None;reaped=False;actual_exit=None;eof=False;fault=None
    selector=selectors.DefaultSelector();descriptors={};reserved=written=writes=0;stream_bytes={'stdout':0,'stderr':0}
    try:
        if monotonic_ns()>=host_deadline:raise TimeoutError('known host budget exhausted before launch')
        child=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,close_fds=True)
        for label,stream in (('stdout',child.stdout),('stderr',child.stderr)):
            os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_READ,label)
            descriptors[label]=os.open(directory/('first.'+label),os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        exited_at=None
        while selector.get_map():
            now=monotonic_ns()
            if child.poll() is not None and exited_at is None:exited_at=now
            if now>=host_deadline or exited_at is not None and now-exited_at>2_000_000_000:
                fault='DEADLINE_OR_INCOMPLETE_EOF_UNKNOWN';break
            for key,unused in selector.select(.05):
                data=os.read(key.fileobj.fileno(),4096)
                if not data:selector.unregister(key.fileobj);key.fileobj.close();continue
                if len(data)>30720-reserved:
                    fault='RAW_CAP_UNKNOWN';break  # Never truncate then label PASS.
                reserved+=len(data);count=os.write(descriptors[key.data],data);written+=count;writes+=1;stream_bytes[key.data]+=count
                if count!=len(data):fault='SHORT_RAW_WRITE_UNKNOWN';break
            if fault:break
        eof=not selector.get_map()
    except BaseException as error:fault=type(error).__name__+':'+str(error)[:128]
    finally:
        for key in list(selector.get_map().values()):
            selector.unregister(key.fileobj);key.fileobj.close()
        if child is not None:
            try:actual_exit=child.wait(timeout=max(.001,(host_deadline-monotonic_ns())/1e9));reaped=True
            except BaseException as error:fault=fault or 'WAIT_'+type(error).__name__
        for descriptor in descriptors.values():
            try:os.fsync(descriptor)
            except BaseException as error:fault=fault or 'FSYNC_'+type(error).__name__
            finally:os.close(descriptor)
        selector.close()
    end=monotonic_ns();after=None;target=None
    try:
        after=pins(binding,planpath,args.approved_plan_sha256,bindingpath,plan['binding']['sha256'])
        record(directory,'pins-after.json',after)
        lines=(directory/'first.stdout').read_text().splitlines()
        if len(lines)!=1:raise ValueError('missing or extra pure result rows')
        target=json.loads(lines[0])
    except BaseException as error:fault=fault or 'FINAL_'+type(error).__name__
    passed=(monotonic_ns()<host_deadline and fault is None and actual_exit==0 and reaped and eof and end-start<=12_000_000_000 and before==after
        and target is not None and target.get('event')=='FIXED_PURE_SCOPE_RESULT' and target.get('scope')==args.scope
        and target.get('methods')==scope['methods'] and target.get('tests_run')==len(scope['methods'])
        and target.get('actual_success_IDs')==scope['expected_success_IDs']
        and target.get('counts')=={'failures':0,'errors':0,'skipped':0,'expectedFailures':0,'unexpectedSuccesses':0}
        and target.get('passed') is True and reserved==written)
    receipt={'status':'PURE_SCOPE_FUNCTIONAL_PASS_PENDING_CAPTURE_EXIT_AND_INDEPENDENT_RAW' if passed else 'FIRST_FAIL_OR_UNKNOWN_NO_RETRY',
        'host_start_ns':host_start,'host_before_receipt_end_ns':monotonic_ns(),'actual_host_exit':None,
        'actual_host_exit_requires_external_observation':True,'scope':args.scope,'exact_argv':argv,'actual_prefix_exit':actual_exit,'reaped':reaped,'EOF_complete':eof,
        'monotonic_start_ns':start,'monotonic_end_ns':end,'elapsed_ns':end-start,'elapsed_semantics':'before Popen through real wait/EOF/raw fsync; metadata pins outside interval',
        'live_raw_bytes_reserved_before_write':reserved,'live_raw_bytes_written':written,'write_calls':writes,'stream_bytes':stream_bytes,
        'source_before_after_equal':before==after,'fault':fault,'target_result':target,'target_output_may_be_incomplete_on_cap_or_short_write':fault is not None,
        'native_SQL_or_worker_runs':0}
    record(directory,'receipt.json',receipt)
    summary=(json.dumps({k:receipt[k] for k in ('status','scope','actual_prefix_exit','reaped','EOF_complete','elapsed_ns','fault')},sort_keys=True)+'\n').encode()
    if len(summary)>512 or reserved+2*len(summary)>32768:raise ValueError('outer raw reserve exceeded')
    fresh(directory,'caller-summary.stdout',summary)
    if os.write(1,summary)!=len(summary):raise OSError('short outer summary')
    files={p.name:{'bytes':p.stat().st_size,'sha256':sha256(p.read_bytes()).hexdigest()} for p in directory.iterdir() if p.is_file()}
    record(directory,'inventory.json',{'files':files,'excludes_this_inventory':True,'outer_summary_duplicate_bytes_charged':2*len(summary)})
    if sum(p.stat().st_size for p in directory.iterdir() if p.is_file())>8*1024*1024:raise ValueError('pure logical8MiB exceeded')
    return 0 if passed and monotonic_ns()<host_deadline else 1


def entry():
    try:return main()
    except Exception as error:
        # Metadata failure is never repaired/retried. Child lifetime is inside
        # main's finally; an external caller must retain actual exit/this raw.
        trailer=(json.dumps({'event':'PURE_CAPTURE_FIRST_FAILURE','type':type(error).__name__,
            'message':str(error)[:96],'status':'FAIL_OR_UNKNOWN_NO_RETRY'},sort_keys=True)+'\n').encode()
        if len(trailer)<=512:os.write(2,trailer)
        return 125


if __name__=='__main__':raise SystemExit(entry())
