"""Finite CODE-only host for one configured-Cross pilot, not production HA.

One gated parent and four sequentially acknowledged worker births. No UTA or
SQLite import, no process discovery, no raw-PID signals, and no retry/respawn.
"""
from hashlib import sha256
import argparse
import json
import os
from pathlib import Path
import select
import selectors
import signal
import stat
import subprocess
import sys
from time import monotonic_ns
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
DENY=frozenset((4471,8784,122905,122907,123007,123009,310035,310039,310266,310269))
STABLE=('pid','start_ticks','boot_id','uid')


def fresh(path,value):
    raw=(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    if len(raw)>512*1024:raise ValueError('host record too large')
    pending=path.with_name(path.name+'.pending-'+uuid4().hex)
    fd=os.open(pending,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        if os.write(fd,raw)!=len(raw):raise OSError('short host record write')
        os.fsync(fd)
    finally:os.close(fd)
    os.link(pending,path,follow_symlinks=False);pending.unlink()
    directory=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(directory)
    finally:os.close(directory)


def object_file(path,maximum=512*1024):
    details=path.lstat()
    if not stat.S_ISREG(details.st_mode) or path.resolve()!=path or details.st_size>maximum:
        raise ValueError('host record must be bounded canonical regular')
    return json.loads(path.read_bytes())


def allowed(pid):
    if type(pid) is not int or pid<=0 or pid in DENY:raise ValueError('protected/invalid numeric ID; no pidfd/proc/signal')


def identity(pid):
    allowed(pid)
    info=Path(f'/proc/{pid}').stat()
    tail=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
    return {'pid':pid,'start_ticks':int(tail[19]),'ppid':int(tail[1]),'state':tail[0],'uid':info.st_uid,
            'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()}


def dead(pidfd):
    poll=select.poll();poll.register(pidfd,select.POLLIN)
    return bool(poll.poll(0))



def registered_birth_matches(birth,held,info,session,cohort,shard):
    if (type(birth['cohort']) is not int or type(birth['shard']) is not int
        or type(held['cohort']) is not int or type(held['shard']) is not int
        or birth['host_session']!=session or birth['cohort']!=cohort or birth['shard']!=shard
        or held['host_session']!=session or held['owner_nonce']!=birth['owner_nonce']
        or held['cohort']!=cohort or held['shard']!=shard or held['held_pidfd'] is not True
        or held['registered'] is not True or held['gates_still_closed'] is not True):
        raise ValueError('registered held birth scope differs')
    stable=held['birth_identity']
    if any(type(stable[name]) is not type(info[name]) or stable[name]!=info[name] for name in STABLE):
        raise ValueError('stable birth identity differs')



def cleanup_call(errors,label,operation):
    try:return True,operation()
    except BaseException as error:
        errors.append(label+'_'+type(error).__name__)
        return False,None


def close_stdin_no_flush(stream,errors,label):
    # Discard a buffered gate on failure; close() could retry a failed flush.
    if stream is None:return
    try:
        if stream.closed:return
        raw=getattr(stream,'raw',None)
        target=raw if raw is not None else stream
    except BaseException as error:
        errors.append(label+'_inspect_'+type(error).__name__);return
    cleanup_call(errors,label+'_raw_close',target.close)


def signal_owned_before_deadline(pidfd,deadline_ns):
    if monotonic_ns()>=deadline_ns:raise TimeoutError('shared cleanup deadline expired; no signal')
    signal.pidfd_send_signal(pidfd,signal.SIGKILL)


def adopt_verified_child(children,key,birth,held,parent_pid,parent_fd,session,cohort,shard,errors):
    """Unverified pidfd is LOCAL only: failed validation closes, never signals."""
    pid=birth['owned_Popen_pid'];allowed(pid)
    candidate=None
    try:
        candidate=os.pidfd_open(pid)
        info=identity(pid)
        registered_birth_matches(birth,held,info,session,cohort,shard)
        if (info['pid']!=pid or info['ppid']!=parent_pid or info['uid']!=os.geteuid()
            or info['state'] in ('Z','X') or dead(candidate) or parent_fd is None or dead(parent_fd)):
            raise ValueError('candidate parent/identity/liveness differs; never adopt')
        owned={'key':key,'birth':birth,'pid':pid,'pidfd':candidate,'identity':info,'acked':False,'validated_owned':True}
        children[key]=owned  # Promotion only after ALL validation has succeeded.
        candidate=None
        return owned
    finally:
        if candidate is not None:cleanup_call(errors,'unverified_candidate_close',lambda:os.close(candidate))


def source_pins(manifest):
    pins={}
    for name,expected in manifest['inputs'].items():
        path=ROOT/name;details=path.lstat()
        if not stat.S_ISREG(details.st_mode) or path.resolve()!=path:raise ValueError('nonregular source')
        raw=path.read_bytes();observed={'bytes':len(raw),'sha256':sha256(raw).hexdigest()}
        if observed!=expected:raise ValueError('host source mismatch: '+name)
        pins[name]=observed
    return pins


def bytes_used(*roots):
    total=0;raw=0
    for root in roots:
        if not root.exists():continue
        for path in root.rglob('*'):
            info=path.lstat()
            if stat.S_ISREG(info.st_mode):
                total+=info.st_size
                if path.name.endswith(('.stdout','.stderr')):raw+=info.st_size
            elif not stat.S_ISDIR(info.st_mode):raise ValueError('nonregular scope file')
    if total>64*1024*1024 or raw>128*1024:raise ValueError('shared logical64MiB/raw128KiB exceeded')
    return total,raw


def main():
    start=monotonic_ns();deadline=start+80_000_000_000;cleanup_end=deadline+2_000_000_000
    parser=argparse.ArgumentParser();parser.add_argument('--plan',required=True);parser.add_argument('--approved-plan-sha256',required=True)
    args=parser.parse_args();planpath=Path(args.plan);planraw=planpath.read_bytes()
    if sha256(planraw).hexdigest()!=args.approved_plan_sha256:raise ValueError('unapproved native host plan')
    plan=json.loads(planraw);manifestpath=ROOT/plan['manifest']['path'];manifestraw=manifestpath.read_bytes()
    if sha256(manifestraw).hexdigest()!=plan['manifest']['sha256']:raise ValueError('native manifest changed')
    manifest=json.loads(manifestraw);before=source_pins(manifest)
    run=Path(plan['run_root']);host=Path(plan['host_root'])
    if any(p.parent!=Path('/workspace') or not p.is_absolute() or p.exists() for p in (run,host)):
        raise ValueError('new private workspace run/host roots required')
    os.umask(0o077);host.mkdir(mode=0o700);(host/'birth-acks').mkdir(mode=0o700)
    session=uuid4().hex;host_pid=os.getpid();allowed(host_pid)
    argv=plan['target_argv']
    fresh(host/'intent.json',{'format':1,'session':session,'host_pid':host_pid,'host_root':str(host),'run_root':str(run),
        'source_commit':plan['source_commit'],'manifest_sha256':plan['manifest']['sha256'],'source_pins':before,
        'exact_argv':argv,'monotonic_start_ns':start,'execution_deadline_ns':deadline,'cleanup_deadline_ns':cleanup_end,
        'actual_host_exit':None,'actual_host_exit_requires_external_witness':True,'actual_CPU_affinity':sorted(os.sched_getaffinity(0))})
    # Preserve used code as private evidence; the complete capsule is never public by default.
    fd=os.open(host/'used-host-source.py',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        data=Path(__file__).read_bytes()
        if os.write(fd,data)!=len(data):raise OSError('short host-source copy')
        os.fsync(fd)
    finally:os.close(fd)
    parent=None;parent_fd=None;children={};selector=selectors.DefaultSelector();raw_fds={};raw_reserved=raw_written=0
    fault=None;actual_exit=None;reaped=False;eof=False;replies=[];parent_identity=None;cleanup_errors=[];gate_stage=None
    def fail(reason):
        nonlocal fault
        if fault is None:
            fault={'reason':reason,'at_ns':monotonic_ns()}
            try:fresh(host/'stop.json',{'session':session,'reason':reason,'at_ns':monotonic_ns()})
            except BaseException:pass
    def scan_births(ack):
        # Only four fixed fresh descendant paths, never a global registry/process scan.
        for cohort in (0,1):
            for shard in (0,1):
                key=f'{cohort}:{shard}';directory=run/f'cohort-{cohort}'/'workers';birthpath=directory/f'worker-{shard}-birth.json'
                if not birthpath.exists():continue
                birth=object_file(birthpath,16384)
                if birth['host_session']!=session or birth['cohort']!=cohort or birth['shard']!=shard:raise ValueError('birth scope identity differs')
                heldpath=directory/f'worker-{shard}-held.json'
                if key not in children:
                    if not heldpath.exists():continue  # Both gates remain closed.
                    held=object_file(heldpath,16384)
                    owned=adopt_verified_child(children,key,birth,held,parent.pid,parent_fd,session,cohort,shard,cleanup_errors)
                    fresh(host/f'child-{cohort}-{shard}-held.json',{'birth':birth,'identity':owned['identity'],'held_pidfd':True,'at_ns':monotonic_ns()})
                owned=children[key]
                if birth!=owned['birth']:raise ValueError('immutable birth record changed')
                if not ack or owned['acked']:continue
                for prior in children.values():
                    if not prior['acked'] or prior['pidfd'] is None or not dead(prior['pidfd']):continue
                    pc,ps=map(int,prior['key'].split(':'));cleanup=run/f'cohort-{pc}'/'workers'/'cleanup.json'
                    if not cleanup.exists():raise ValueError('known owner death before next child ACK')
                    prior_receipt=next(r for r in object_file(cleanup)['owned_children'] if r['shard']==ps)
                    if not prior_receipt['reaped'] or prior_receipt['actual_exit']!=0 or prior_receipt['held_pidfd_kill_used']:
                        raise ValueError('prior child cleanup failed before next ACK')
                heldpath=directory/f'worker-{shard}-held.json'
                if not heldpath.exists():continue
                held=object_file(heldpath,16384)
                registered_birth_matches(birth,held,owned['identity'],session,cohort,shard)
                if dead(owned['pidfd']):raise ValueError('held child exited before ACK')
                if parent_fd is None or dead(parent_fd):raise ValueError('parent died before child ACK')
                if monotonic_ns()>=deadline:raise TimeoutError('host budget exhausted before child ACK')
                reply={'format':1,'session':session,'cohort':cohort,'shard':shard,'owner_nonce':birth['owner_nonce'],
                    'pid':owned['pid'],'identity':{name:owned['identity'][name] for name in STABLE},'host_pidfd_held':True}
                fresh(host/'birth-acks'/f'cohort-{cohort}-worker-{shard}.json',reply)
                owned['acked']=True;replies.append(reply)
    def read_raw(wait):
        nonlocal raw_reserved,raw_written
        for key,unused in selector.select(wait):
            data=os.read(key.fileobj.fileno(),4096)
            if not data:selector.unregister(key.fileobj);key.fileobj.close();continue
            if len(data)>16384-512-raw_reserved:raise ValueError('parent raw shared16KiB exceeded')
            raw_reserved+=len(data);count=os.write(raw_fds[key.data],data);raw_written+=count
            if count!=len(data):raise OSError('short parent raw write')
    try:
        if monotonic_ns()>=deadline:raise TimeoutError('known host budget exhausted before parent Popen')
        parent=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,close_fds=True)
        fresh(host/'parent-birth.json',{'owned_Popen_pid':parent.pid,'exact_argv':argv,'stdin_gate_released':False,'at_ns':monotonic_ns()})
        for label,stream in (('stdout',parent.stdout),('stderr',parent.stderr)):
            os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_READ,label)
            raw_fds[label]=os.open(host/('first.'+label),os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        allowed(parent.pid);parent_fd=os.pidfd_open(parent.pid);parent_identity=identity(parent.pid)
        if parent_identity['ppid']!=host_pid or parent_identity['uid']!=os.geteuid() or dead(parent_fd):raise ValueError('new parent identity differs')
        fresh(host/'parent-held.json',{'identity':parent_identity,'held_pidfd':True,'gate_closed':True,'at_ns':monotonic_ns()})
        if monotonic_ns()>=deadline:raise TimeoutError('known host deadline before parent gate')
        gate_stage='parent_stdin_write'
        if parent.stdin.write(b'G')!=1:raise OSError('short parent gate write')
        gate_stage='parent_stdin_flush';parent.stdin.flush()
        gate_stage='parent_stdin_close';parent.stdin.close();gate_stage=None
        while True:
            if monotonic_ns()>=deadline:fail('execution80s exceeded');break
            scan_births(True);bytes_used(run,host)
            read_raw(.02)
            if parent.poll() is not None:
                if not selector.get_map():break
            if fault is not None:break
        if fault is None:
            actual_exit=parent.wait(timeout=max(.001,(cleanup_end-monotonic_ns())/1e9));reaped=True
            eof=not selector.get_map()
            if actual_exit!=0:fail('parent actual nonzero exit')
    except BaseException as error:
        if gate_stage is not None:cleanup_errors.append(gate_stage+'_'+type(error).__name__)
        fail(type(error).__name__+':'+str(error)[:128])
    finally:
        if parent is not None:close_stdin_no_flush(parent.stdin,cleanup_errors,'parent_stdin')
        if fault is not None:
            # No new ACKs after first fault. Discover only already-published
            # fixed descendant births and let the stop marker unwind briefly.
            grace=min(cleanup_end,monotonic_ns()+1_000_000_000)
            while monotonic_ns()<grace:
                try:scan_births(False)
                except BaseException as error:cleanup_errors.append('birth_'+type(error).__name__)
                try:read_raw(.01)
                except BaseException as error:cleanup_errors.append('raw_'+type(error).__name__);break
                if parent is None:break
                ok,status=cleanup_call(cleanup_errors,'parent_cleanup_poll',parent.poll)
                if not ok or status is not None:break
            for item in list(children.values())+([{'pidfd':parent_fd}] if parent_fd is not None else []):
                handle=item.get('pidfd')
                if handle is not None:
                    ok,exited=cleanup_call(cleanup_errors,'owned_liveness',lambda handle=handle:dead(handle))
                    if ok and not exited:
                        cleanup_call(cleanup_errors,'signal',lambda handle=handle:signal_owned_before_deadline(handle,cleanup_end))
        if parent is not None and not reaped:
            try:actual_exit=parent.wait(timeout=max(.001,(cleanup_end-monotonic_ns())/1e9));reaped=True
            except BaseException as error:fail('parent_reap_'+type(error).__name__)
        while selector.get_map() and monotonic_ns()<cleanup_end:
            try:read_raw(.01)
            except BaseException as error:cleanup_errors.append('drain_'+type(error).__name__);break
        eof=not selector.get_map()
        while monotonic_ns()<cleanup_end:
            outstanding=False
            for item in children.values():
                if item['pidfd'] is None:continue
                ok,exited=cleanup_call(cleanup_errors,'child_cleanup_poll',lambda item=item:dead(item['pidfd']))
                outstanding=outstanding or (ok and not exited)
            if not outstanding:break
            cleanup_call(cleanup_errors,'cleanup_poll_delay',lambda:select.select([],[],[],.005))
        for key in list(selector.get_map().values()):
            cleanup_call(cleanup_errors,'selector_unregister',lambda key=key:selector.unregister(key.fileobj))
            cleanup_call(cleanup_errors,'pipe_close',key.fileobj.close)
        for descriptor in raw_fds.values():
            cleanup_call(cleanup_errors,'raw_fsync',lambda descriptor=descriptor:os.fsync(descriptor))
            cleanup_call(cleanup_errors,'raw_close',lambda descriptor=descriptor:os.close(descriptor))
        cleanup_call(cleanup_errors,'selector_close',selector.close)
    child_facts=[]
    for item in children.values():
        c,s=map(int,item['key'].split(':'));cleanup=run/f'cohort-{c}'/'workers'/'cleanup.json';receipt=None
        if cleanup.exists():
            try:receipt=next(r for r in object_file(cleanup)['owned_children'] if r['shard']==s)
            except BaseException as error:fail('child_cleanup_receipt_'+type(error).__name__)
        ok,exited=cleanup_call(cleanup_errors,'child_final_liveness',lambda item=item:dead(item['pidfd'])) if item['pidfd'] is not None else (False,None)
        observed_dead=ok and exited
        if not observed_dead:fail('new child death UNKNOWN')
        child_facts.append({'key':item['key'],'pid':item['pid'],'host_ack':item['acked'],'death_observed_by_held_pidfd':observed_dead,
            'actual_exit_and_reap_from_parent':receipt,'missing_parent_wait_means_UNKNOWN':receipt is None})
        if item['pidfd'] is not None:cleanup_call(cleanup_errors,'owned_child_pidfd_close',lambda item=item:os.close(item['pidfd']))
    if parent_fd is not None:cleanup_call(cleanup_errors,'parent_pidfd_close',lambda:os.close(parent_fd))
    after=None;target=None
    try:
        after=source_pins(manifest)
        if sha256(planpath.read_bytes()).hexdigest()!=args.approved_plan_sha256 or sha256(manifestpath.read_bytes()).hexdigest()!=plan['manifest']['sha256']:
            raise ValueError('plan/manifest changed')
        target=object_file(run/'result.json')
        bytes_used(run,host)
    except BaseException as error:fail('final_'+type(error).__name__)
    passed=(fault is None and not cleanup_errors and actual_exit==0 and reaped and eof and before==after and len(children)==len(replies)==4
        and raw_reserved==raw_written and monotonic_ns()<deadline and target is not None
        and target.get('both_fixed_pilot_functional_gates_passed') is True and target.get('source_unchanged') is True
        and all(r['host_ack'] and r['death_observed_by_held_pidfd'] and r['actual_exit_and_reap_from_parent'] is not None
            and r['actual_exit_and_reap_from_parent']['actual_exit']==0 and r['actual_exit_and_reap_from_parent']['reaped']
            and not r['actual_exit_and_reap_from_parent']['held_pidfd_kill_used'] for r in child_facts))
    fresh(host/'result.json',{'status':'NATIVE_PILOT_FUNCTIONAL_PASS_PENDING_ACTUAL_HOST_EXIT_AND_INDEPENDENT_RAW' if passed else 'FIRST_FAIL_OR_UNKNOWN_NO_RETRY',
        'monotonic_start_ns':start,'execution_deadline_ns':deadline,'cleanup_deadline_ns':cleanup_end,'observed_end_ns':monotonic_ns(),
        'actual_parent_exit':actual_exit,'parent_reaped':reaped,'parent_EOF_complete':eof,'actual_host_exit':None,
        'actual_host_exit_requires_external_witness':True,'raw_reserved_before_write':raw_reserved,'raw_written':raw_written,
        'source_before_after_equal':before==after,'fault':fault,'cleanup_errors':cleanup_errors,'child_facts':child_facts,'native_target_result':target,
        'C_IO_hard_realtime_proven':False,'production_capacity_approved':False})
    return 0 if passed and monotonic_ns()<cleanup_end else 1


if __name__=='__main__':raise SystemExit(main())
