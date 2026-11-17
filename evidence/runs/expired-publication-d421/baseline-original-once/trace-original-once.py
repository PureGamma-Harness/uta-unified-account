"""One original test, real call-through observations, own process-group only."""
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
from threading import Event, Lock, Thread, current_thread
from time import monotonic, monotonic_ns, sleep
import unittest
from unittest.mock import patch

ROOT = Path('/workspace/uta-expired-publication-review')
METHOD = 'test_expired_sigstopped_shared_gate_owner_is_killed_so_publication_can_recover'
BASE = 'd421df3fc5123e8267f0eecf8bb5efdc37cd0dc6'


def birth(pid):
    try:
        raw = Path('/proc', str(pid), 'stat').read_text()
        tail = raw[raw.rindex(')') + 2:].split()
        return {'pid': pid, 'state': tail[0], 'start_ticks': tail[19], 'pgid': int(tail[2])}
    except FileNotFoundError:
        return {'pid': pid, 'present': False}


def worker(output):
    sys.path.insert(0, str(ROOT))
    from tests import test_durable_faults as tests
    from uta.durable_process import DurableProcessRouter
    from uta.sharding import ShardRouter
    from uta.writer_fence import WriterFence
    from multiprocessing.process import BaseProcess
    output.mkdir(parents=True, exist_ok=False)
    stream = (output / 'events.jsonl').open('x', buffering=1)
    lock = Lock()
    logger_failures, processes, pidfds = [], {}, {}
    stopped = Event()
    def emit(kind, **fields):
        item = {'monotonic_ns': monotonic_ns(), 'thread': current_thread().name,
                'kind': kind, **fields}
        try:
            with lock:
                stream.write(json.dumps(item, sort_keys=True) + '\n')
        except BaseException as error:
            logger_failures.append(type(error).__name__)
    def watch_exits():
        observed = set()
        while not stopped.wait(.01):
            with lock:
                copies = list(pidfds.items())
            for pid, fd in copies:
                if pid not in observed:
                    p = select.poll(); p.register(fd, select.POLLIN)
                    if p.poll(0):
                        observed.add(pid)
                        emit('kernel_pidfd_exit', pid=pid, identity=birth(pid))
    watcher = Thread(target=watch_exits, name='independent-pidfd-observer', daemon=True)
    original_spawn = DurableProcessRouter._spawn
    def spawn(router, shard):
        emit('spawn_start', shard=shard)
        result = original_spawn(router, shard)
        process = router._workers[shard][0]
        info = birth(process.pid)
        processes[process.pid] = process
        try:
            fd = os.pidfd_open(process.pid)
            with lock:
                pidfds[process.pid] = fd
        except OSError as error:
            emit('pidfd_open_unavailable', pid=process.pid, error_type=type(error).__name__)
        emit('spawn_return', shard=shard, identity=info)
        return result
    original_lock = ShardRouter._lock
    @contextmanager
    def gate(router, *, exclusive=False, timeout=None):
        # Record the real operation's interval; never replace the flock result.
        emit('gate_wait_start', exclusive=exclusive, timeout=timeout)
        try:
            with original_lock(router, exclusive=exclusive, timeout=timeout):
                emit('gate_acquired', exclusive=exclusive, timeout=timeout)
                yield
            emit('gate_released', exclusive=exclusive, timeout=timeout)
        except BaseException as error:
            emit('gate_error', exclusive=exclusive, timeout=timeout,
                 error_type=type(error).__name__, code=getattr(error, 'code', None))
            raise
    original_status = WriterFence.status
    def status(fence):
        try:
            value = original_status(fence)
        except BaseException as error:
            emit('fence_status_error', error_type=type(error).__name__, code=getattr(error, 'code', None))
            raise
        emit('fence_status', **{k: value[k] for k in ('owner_pid','generation','active','expires_ns','observed_ns') if k in value})
        return value
    original_kill, original_join = BaseProcess.kill, BaseProcess.join
    def kill(process):
        emit('kill_start', pid=process.pid, identity=birth(process.pid))
        value = original_kill(process)
        emit('kill_return', pid=process.pid)
        return value
    def join(process, timeout=None):
        emit('join_start', pid=process.pid, timeout=timeout)
        value = original_join(process, timeout)
        emit('join_return', pid=process.pid, exitcode=process.exitcode,
             identity=birth(process.pid))
        return value
    original_publication = DurableProcessRouter.publish_market
    def publish(router, snapshot, *, timeout=10):
        emit('publication_start', version=snapshot.version, timeout=timeout)
        try:
            value = original_publication(router, snapshot, timeout=timeout)
        except BaseException as error:
            emit('publication_error', version=snapshot.version, error_type=type(error).__name__, code=getattr(error,'code',None))
            raise
        emit('publication_return', version=snapshot.version, publishing=value.get('publishing'),
             receipts={s: None if r is None else {k:r.get(k) for k in ('command_id','state','sequence')}
                       for s,r in value.get('receipts',{}).items()})
        return value
    original_receipts = DurableProcessRouter._receipts
    def receipts(router, commands, timeout):
        emit('receipts_start', commands=commands, timeout=timeout)
        value = original_receipts(router, commands, timeout)
        emit('receipts_return', states={s:None if r is None else r.get('state') for s,r in value.items()})
        return value
    class RecordedEvent(Event):
        def wait(self, timeout=None):
            emit('original_event_wait_start', timeout=timeout)
            value = super().wait(timeout)
            emit('original_event_wait_return', timeout=timeout, value=value)
            return value
    class RecordedThread(Thread):
        def run(self):
            emit('original_thread_start')
            try:
                return super().run()
            finally:
                emit('original_thread_end')
    case = tests.ManagedProcessFaultTests(METHOD)
    cleanup = case.doCleanups
    def observe_cleanup():
        try:
            if hasattr(case, 'router'):
                for shard in (0,1):
                    database = case.router._database(shard)
                    with database.read_transaction() as connection:
                        count = connection.execute('SELECT COUNT(*) FROM uta_orders').fetchone()[0]
                        accepted = connection.execute("SELECT COUNT(*) FROM uta_events WHERE event_type='ORDER_ACCEPTED'").fetchone()[0]
                        owner = connection.execute('SELECT generation,owner_pid FROM writer_fence_lease').fetchone()
                    emit('own_finance_before_cleanup', shard=shard, orders=count, accepted=accepted,
                         generation=owner[0], owner_pid=owner[1])
        except BaseException as error:
            emit('own_finance_observation_unavailable', error_type=type(error).__name__)
        finally:
            return cleanup()
    case.doCleanups = observe_cleanup
    beginning = monotonic_ns()
    emit('original_case_start', case=METHOD, python=sys.version, affinity=sorted(os.sched_getaffinity(0)), identity=birth(os.getpid()))
    watcher.start()
    with ExitStack() as stack:
        for target,name,replacement in ((DurableProcessRouter,'_spawn',spawn),(ShardRouter,'_lock',gate),
                (WriterFence,'status',status),(BaseProcess,'kill',kill),(BaseProcess,'join',join),
                (DurableProcessRouter,'publish_market',publish),(DurableProcessRouter,'_receipts',receipts),
                (tests,'Event',RecordedEvent),(tests,'Thread',RecordedThread)):
            stack.enter_context(patch.object(target,name,replacement))
        result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite([case]))
    stopped.set(); watcher.join(1)
    for pid,fd in pidfds.items():
        p=select.poll();p.register(fd,select.POLLIN)
        emit('final_owned_child', pid=pid, pidfd_exited=bool(p.poll(0)),
             identity=birth(pid), exitcode=processes[pid].exitcode)
        os.close(fd)
    emit('original_case_end', passed=result.wasSuccessful())
    stream.close()
    (output/'result.json').write_text(json.dumps({'base_source':BASE,'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
        'original_case_passed':result.wasSuccessful(),'historical_failure_reproduced':not result.wasSuccessful(),
        'interpretation':'NO_REPRO if original case passes; not proof of a unique historical cause',
        'duration_seconds':(monotonic_ns()-beginning)/1e9,'logger_failures':logger_failures,
        'trace_sha256':hashlib.sha256((output/'events.jsonl').read_bytes()).hexdigest(),
        'production_approved':False},indent=2)+'\n')
    return 0 if result.wasSuccessful() else 1


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
        raise SystemExit('explicit --run NEW_OUTPUT is required; no default action')
    raise SystemExit(worker(Path(sys.argv[2])) if sys.argv[1]=='--worker' else launch(Path(sys.argv[2])))
