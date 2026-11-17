"""Explicit one-shot synthetic schema-BUSY conformance; no default native run."""
from contextlib import closing
from datetime import datetime,timezone
from hashlib import sha256
import fcntl,json,multiprocessing,os
from pathlib import Path
import select,signal,sqlite3,subprocess,sys,traceback
from time import monotonic,sleep
from unittest.mock import patch

ROOT=Path('/workspace/uta-shared-gate-busy-read-review')

def birth(pid):
    try:
        raw=Path('/proc',str(pid),'stat').read_text();tail=raw[raw.rindex(')')+2:].split()
        return {'pid':pid,'state':tail[0],'start_ticks':tail[19],'pgid':int(tail[2])}
    except FileNotFoundError:
        return {'pid':pid,'present':False}

def exclusive_child(directory,channel):
    sys.path.insert(0,str(ROOT))
    from uta.storage import Database
    from uta.writer_fence import WriterFence
    from uta.durable_process import _process_identity
    database=Database(directory/'authority.sqlite3');fence=WriterFence(database)
    token=fence.acquire('synthetic-schema-owner',5)
    descriptor=os.open(directory/'router.lock',os.O_RDWR|os.O_CLOEXEC|os.O_NOFOLLOW)
    connection=None
    try:
        fcntl.flock(descriptor,fcntl.LOCK_SH)
        channel.send({'phase':'owner_ready','identity':_process_identity(os.getpid()),'generation':token.generation})
        if channel.recv()!='lock':raise AssertionError('unexpected synthetic child command')
        connection=sqlite3.connect((directory/'authority.sqlite3').as_uri()+'?mode=rw',uri=True,timeout=.1,isolation_level=None)
        assert connection.execute('PRAGMA locking_mode=EXCLUSIVE').fetchone()[0]=='exclusive'
        connection.execute('BEGIN IMMEDIATE')
        connection.execute('SELECT COUNT(*) FROM sqlite_master').fetchone()
        assert connection.total_changes==0
        channel.send({'phase':'exclusive_locked','identity':_process_identity(os.getpid()),'changes':connection.total_changes})
        if channel.recv()!='release':raise AssertionError('unexpected lock release command')
        connection.rollback();assert not connection.in_transaction and connection.total_changes==0
        connection.close();connection=None
        fcntl.flock(descriptor,fcntl.LOCK_UN);os.close(descriptor);descriptor=None
        channel.send({'phase':'locks_released','identity':_process_identity(os.getpid()),'changes':0})
        if channel.recv()!='done':raise AssertionError('unexpected final command')
    finally:
        if connection is not None:connection.close()
        if descriptor is not None:os.close(descriptor)
        fence.release(token)
        channel.close()

def worker(output):
    sys.path.insert(0,str(ROOT))
    from decimal import Decimal
    from uta.storage import Database
    from uta.service import ExchangeService
    from uta.writer_fence import WriterFence
    from tests.test_durable_faults import (undo_owned_test_stop,bound_router_shared_flocks,financial_snapshot)
    output.mkdir(parents=True,exist_ok=False)
    directory=output/'private-scratch';directory.mkdir(mode=0o700)
    lock=directory/'router.lock';lock.touch(mode=0o600)
    database=Database(directory/'authority.sqlite3');service=ExchangeService(database,{'USD':2})
    service.create_account('scratch');service.deposit('scratch','seed','USD',Decimal(10))
    before=financial_snapshot(database.path)
    WriterFence(database).enable('synthetic-busy-observation')
    observer=Database(database.path,timeout=.1)
    context=multiprocessing.get_context('spawn');parent,child=context.Pipe()
    process=context.Process(target=exclusive_child,args=(directory,child))
    events=[];observation={'cleanup_forced_kill':False,'cleanup_errors':[]}
    logger_failures=[];status_calls=[];native_errors=[];checks={};pidfd=None;stopped=False;normal_exit=False
    def emit(kind,**fields):events.append({'kind':kind,'monotonic':monotonic(),**fields})
    def receive(phase):
        assert parent.poll(2),'own child protocol deadline'
        value=parent.recv();assert value['phase']==phase,value
        emit('child_phase',**value);return value
    original=WriterFence.status;current_phase=['initial']
    def counted_status(fence):
        status_calls.append(current_phase[0])
        try:return original(fence)
        except BaseException as error:
            native_errors.append(error);raise
    def lease(phase):
        current_phase[0]=phase;value=WriterFence(observer).status()
        return {k:value[k] for k in ('owner_pid','generation','active','expires_ns','now_ns')}
    started=datetime.now(timezone.utc).isoformat();beginning=monotonic()
    process.start();child.close();pid=process.pid
    identity=birth(pid);emit('spawn_return',identity=identity)
    try:
        pidfd=os.pidfd_open(pid);exited=select.poll();exited.register(pidfd,select.POLLIN)
        ready=receive('owner_ready');binding=ready['identity']
        assert binding['pid']==pid and str(binding['start_ticks'])==identity['start_ticks']
        with patch.object(WriterFence,'status',counted_status):
            known=lease('fresh_before_exclusive');assert known['active'] and known['owner_pid']==pid
            assert known['generation']==ready['generation']
            parent.send('lock');receive('exclusive_locked')
            signal.pidfd_send_signal(pidfd,signal.SIGSTOP);stopped=True
            deadline=monotonic()+.2
            while monotonic()<deadline and birth(pid).get('state')!='T':sleep(.001)
            assert birth(pid)['state']=='T'
            info=lock.stat();held=bound_router_shared_flocks(pid,binding,lock,(info.st_dev,info.st_ino));assert held
            primary=None;undo_reads=None
            try:
                try:
                    lease('expected_real_busy')
                    raise AssertionError('the real exclusive lock did not block native status')
                finally:
                    primary=sys.exc_info()[1]
                    count=len(status_calls)
                    assert undo_owned_test_stop(pid,pidfd,binding,observation,reason='controlled_actual_busy_primary',known_lease=known,expected_generation=known['generation'],cleanup=True)
                    stopped=False;undo_reads=len(status_calls)-count
            except sqlite3.OperationalError as error:
                code=getattr(error,'sqlite_errorcode',None)
                strict_busy=(type(code)is int and code&255==5) or (not hasattr(error,'sqlite_errorcode') and type(error)is sqlite3.OperationalError and error.args==('database is locked',))
                assert strict_busy
                checks['actual_busy_primary_preserved']=error is primary and native_errors[-1] is error
                emit('actual_busy',error_type=type(error).__name__,native_errorcode=code,native_errorname=getattr(error,'sqlite_errorname',None))
            else:raise AssertionError('expected native primary exception was absent')
            assert undo_reads==0
            parent.send('release');receive('locks_released')
            assert birth(pid)['state'] not in ('T','t','Z','X')
            assert not bound_router_shared_flocks(pid,binding,lock,(info.st_dev,info.st_ino))
            fresh=lease('once_fresh_after_real_release')
            checks['fresh_original_owner_generation_active']=fresh['active'] is True and fresh['owner_pid']==pid and fresh['generation']==known['generation']
            checks['expiry_not_changed_or_renewed']=fresh['expires_ns']==known['expires_ns']
            checks['cleanup_performs_zero_lease_reads']=undo_reads==0
            checks['unobserved_is_not_authority']=all(x['lease_observed'] is False and x['financial_authority_granted'] is False for x in observation['injection_undos'])
            checks['exact_three_parent_native_reads']=status_calls==['fresh_before_exclusive','expected_real_busy','once_fresh_after_real_release']
            parent.send('done');process.join(2);normal_exit=not process.is_alive() and process.exitcode==0
            checks['native_child_normal_exit']=normal_exit and bool(exited.poll(100))
            checks['financial_rows_unchanged']=financial_snapshot(database.path)==before
            with database.read_transaction() as connection:
                balances={r[0]:int(r[1]) for r in connection.execute("SELECT account,units FROM ledger_balances WHERE asset='USD'")}
            checks['integer_cash_oracle']=balances=={'customer:scratch':1000,'system:custody':-1000}
            emit('fresh_native_lease',known=known,fresh=fresh,held_kernel_records=held,status_calls=status_calls)
    except BaseException as error:
        checks['unexpected_error_absent']=False
        emit('unexpected_error',error_type=type(error).__name__)
        traceback.print_exc()
    finally:
        if process.is_alive():
            observation['cleanup_forced_kill']=True
            try:
                if pidfd is not None:signal.pidfd_send_signal(pidfd,signal.SIGKILL)
                else:process.kill()
            except ProcessLookupError:pass
            process.join(1)
        parent.close()
        if pidfd is not None:os.close(pidfd)
    emit('final_owned_child',pid=pid,identity=birth(pid),exitcode=process.exitcode)
    checks['no_forced_or_residual_cleanup']=observation['cleanup_forced_kill'] is False and not process.is_alive() and birth(pid).get('present') is False
    checks['logger_and_cleanup_errors_absent']=logger_failures==[] and observation['cleanup_errors']==[]
    raw=''.join(json.dumps(x,sort_keys=True)+'\n' for x in events)
    (output/'events.jsonl').write_text(raw)
    report={'scope':'one independent synthetic exclusive-schema-lock conformance; not historical unique WAL cause or full original case','source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'started_at':started,'finished_at':datetime.now(timezone.utc).isoformat(),'duration_seconds':monotonic()-beginning,'checks':checks,'component_passed':all(v is True for v in checks.values()) and len(checks)==11,'observations':observation,'trace_sha256':sha256(raw.encode()).hexdigest(),'logger_failures':logger_failures,'production_approved':False}
    (output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2));return 0 if report['component_passed'] else 2

def launch(output):
    # Reap only adopted descendants of this new reproduction process.
    import ctypes
    assert ctypes.CDLL(None).prctl(36,1,0,0,0)==0
    output.mkdir(parents=True, exist_ok=False)
    command=['taskset','-c','2',sys.executable,str(Path(__file__).resolve()),'--worker',str(output/'worker')]
    started=datetime.now(timezone.utc).isoformat();beginning=monotonic()
    with (output/'unittest.txt').open('x') as log:
        process=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        identity=birth(process.pid);pidfd=os.pidfd_open(process.pid)
        timed_out=False
        try:
            code=process.wait(timeout=27)
        except subprocess.TimeoutExpired:
            timed_out=True
            if birth(process.pid).get('start_ticks')==identity.get('start_ticks'):
                os.killpg(process.pid,signal.SIGKILL)
            code=process.wait(timeout=1)
        finally:
            os.close(pidfd)
        cleanup=[]
        trace=output/'worker/events.jsonl'
        spawned=[]
        if trace.exists():
            for line in trace.read_text().splitlines():
                try:
                    event=json.loads(line)
                except ValueError:
                    continue
                if event.get('kind')=='spawn_return':
                    spawned.append(event['identity'])
        for original in spawned:
            current=birth(original['pid'])
            same=(current.get('start_ticks')==original.get('start_ticks') and current.get('pgid')==process.pid)
            entry={'original':original,'current':current,'forced_cleanup':False}
            if same and current.get('state') not in ('Z','X'):
                try:
                    childfd=os.pidfd_open(original['pid'])
                    try:
                        if birth(original['pid']).get('start_ticks')==original.get('start_ticks'):
                            signal.pidfd_send_signal(childfd,signal.SIGKILL)
                            entry['forced_cleanup']=True
                    finally:
                        os.close(childfd)
                except ProcessLookupError:
                    pass
            cleanup.append(entry)
        until=monotonic()+1
        while monotonic()<until:
            try:
                child,status=os.waitpid(-1,os.WNOHANG)
            except ChildProcessError:
                break
            if not child:sleep(.01)
    report={'command':command,'started_at':started,'finished_at':datetime.now(timezone.utc).isoformat(),
        'wall_seconds':monotonic()-beginning,'worker_identity':identity,'exit_code':code,
        'watchdog_seconds':27,'whole_budget_seconds':30,'timed_out':timed_out,
        'own_process_group_only':True,'owned_children':cleanup,
        'final_owned_identities':[birth(item['original']['pid']) for item in cleanup],
        'production_approved':False}
    (output/'launch.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return code


if __name__=='__main__':
    if len(sys.argv)!=3 or sys.argv[1] not in ('--run','--worker'):
        raise SystemExit('explicit --run NEW_OUTPUT is required; no default native action')
    raise SystemExit(worker(Path(sys.argv[2])) if sys.argv[1]=='--worker' else launch(Path(sys.argv[2])))
