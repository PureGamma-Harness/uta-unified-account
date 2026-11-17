"""Original 91e case once; no added DB reads, unchanged assertions and budgets."""
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
from threading import Event, Lock, Thread, current_thread, enumerate as enumerate_threads
from time import monotonic, monotonic_ns, sleep, time_ns, clock_gettime_ns, CLOCK_BOOTTIME
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
METHOD = 'test_expired_sigstopped_shared_gate_owner_is_killed_so_publication_can_recover'
BASE = '91e4ae40b5e9b884c54026406299df5000c9c100'


def birth(pid):
    try:
        raw = Path('/proc', str(pid), 'stat').read_text()
        tail = raw[raw.rindex(')') + 2:].split()
        return {'pid': pid, 'state': tail[0], 'start_ticks': tail[19], 'pgid': int(tail[2])}
    except FileNotFoundError:
        return {'pid': pid, 'present': False}


def code_frames(frame):
    frames = []
    while frame is not None and len(frames) < 32:
        frames.append({'file':str(Path(frame.f_code.co_filename)),
                       'function':frame.f_code.co_name,'line':frame.f_lineno})
        frame = frame.f_back
    return frames


def exception_metadata(error):
    chain, seen = [], set()
    while error is not None and id(error) not in seen and len(chain) < 4:
        seen.add(id(error))
        tb, frames = error.__traceback__, []
        while tb is not None and len(frames) < 32:
            frames.append({'file':tb.tb_frame.f_code.co_filename,
                           'function':tb.tb_frame.f_code.co_name,'line':tb.tb_lineno})
            tb = tb.tb_next
        # Messages can contain arbitrary payloads. Preserve actual type, code,
        # exact originating code locations and exception chain, not message text.
        chain.append({'type':type(error).__name__,
                      'sqlite_errorcode':getattr(error,'sqlite_errorcode',None),
                      'sqlite_errorname':getattr(error,'sqlite_errorname',None),
                      'code':getattr(error,'code',None),'code_frames':frames})
        error = error.__cause__ or (None if error.__suppress_context__ else error.__context__)
    return chain


def source_guard():
    reference = json.loads((Path(__file__).parent/'original_source266.json').read_text())
    actual = {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
              for name in reference['source_sha256']}
    return {'reference_source':reference['source_commit'], 'members':len(actual),
            'all_266_match_original':actual==reference['source_sha256'],
            'source_sha256':actual,
            'driver_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()}


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
        item = {'monotonic_ns': monotonic_ns(), 'boottime_ns': clock_gettime_ns(CLOCK_BOOTTIME),
                'utc_ns': time_ns(), 'thread': current_thread().name,
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
        # Observe the existing native call only. Never open/read another DB.
        started = monotonic_ns()
        emit('fence_status_start', call_id=started)
        try:
            value = original_status(fence)
        except BaseException as error:
            emit('fence_status_error', call_id=started, elapsed_ns=monotonic_ns()-started,
                 exception=exception_metadata(error))
            raise
        emit('fence_status_return', call_id=started, elapsed_ns=monotonic_ns()-started,
             **{k: value[k] for k in ('owner_pid','generation','active','expires_ns',
                                     'observed_ns','now_ns','boot_id') if k in value})
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
    error_buckets = {}
    class RecordedThread(Thread):
        def run(self):
            # Only the explicitly named errors closure cell is read; no f_locals,
            # other cells, financial objects, arbitrary messages or payloads.
            target = getattr(self, '_target', None)
            if target is not None and hasattr(target, '__code__'):
                cells = dict(zip(target.__code__.co_freevars, target.__closure__ or ()))
                if 'errors' in cells:
                    error_buckets[self.ident] = cells['errors'].cell_contents
            emit('original_thread_start')
            try:
                return super().run()
            finally:
                emit('original_thread_end', captured_errors=[exception_metadata(e)
                     for e in list(error_buckets.get(self.ident, ()))])
    case = tests.ManagedProcessFaultTests(METHOD)
    cleanup = case.doCleanups
    def observe_cleanup():
        try:
            emit('case_observations', observation=getattr(case, '_expired_gate_observation', None))
            emit('publisher_captured_errors', errors={str(k):[exception_metadata(e) for e in list(v)]
                 for k,v in list(error_buckets.items())})
        except BaseException as error:
            emit('observation_unavailable', exception=exception_metadata(error))
        finally:
            return cleanup()
    case.doCleanups = observe_cleanup
    def sample_threads():
        while not stopped.wait(.5):
            try:
                frames = sys._current_frames()
                samples = []
                for thread in enumerate_threads():
                    if thread is current_thread() or thread is watcher:
                        continue
                    samples.append({'name':thread.name,'ident':thread.ident,
                                    'alive':thread.is_alive(),
                                    'code_frames':code_frames(frames.get(thread.ident))})
                router = getattr(case, 'router', None)
                # Do not acquire router mutex, call diagnostics, query SQL, or
                # call process.is_alive (which can reap). Read-only native birth.
                monitor = getattr(router, '_monitor', None)
                workers = []
                if router is not None:
                    for shard, triple in list(router._workers.items()):
                        workers.append({'shard':shard,'identity':birth(triple[0].pid)})
                mutex = getattr(router, '_mutex', None)
                # Python 3.13 RLock has no general locked() API. _is_owned only
                # means owned by THIS sampler; do not claim a global lock state.
                emit('parent_thread_sample', threads=samples, workers=workers,
                     supervisor_alive=None if monitor is None else monitor.is_alive(),
                     supervisor_stop=None if router is None else router._stop.is_set(),
                     mutex_global_state='unobserved; infer code-only acquire frame',
                     errors={str(k):[exception_metadata(e) for e in list(v)]
                             for k,v in list(error_buckets.items())},
                     observation=getattr(case, '_expired_gate_observation', None))
            except BaseException as error:
                emit('sampling_unavailable', exception=exception_metadata(error))
    sampler = Thread(target=sample_threads, name='independent-code-stack-observer', daemon=True)
    beginning = monotonic_ns()
    emit('original_case_start', case=METHOD, python=sys.version, affinity=sorted(os.sched_getaffinity(0)), identity=birth(os.getpid()))
    watcher.start(); sampler.start()
    with ExitStack() as stack:
        for target,name,replacement in ((DurableProcessRouter,'_spawn',spawn),(ShardRouter,'_lock',gate),
                (WriterFence,'status',status),(BaseProcess,'kill',kill),(BaseProcess,'join',join),
                (DurableProcessRouter,'publish_market',publish),(DurableProcessRouter,'_receipts',receipts),
                (tests,'Event',RecordedEvent),(tests,'Thread',RecordedThread)):
            stack.enter_context(patch.object(target,name,replacement))
        result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite([case]))
    stopped.set(); watcher.join(1); sampler.join(1)
    for pid,fd in pidfds.items():
        p=select.poll();p.register(fd,select.POLLIN)
        emit('final_owned_child', pid=pid, pidfd_exited=bool(p.poll(0)),
             identity=birth(pid), exitcode=processes[pid].exitcode)
        os.close(fd)
    emit('original_case_end', passed=result.wasSuccessful())
    stream.close()
    (output/'result.json').write_text(json.dumps({'base_source':BASE,'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
        'case_passed':result.wasSuccessful(),'test_failure_observed':not result.wasSuccessful(),
        'historical_original_assertion_reproduced':any('original bound PID did not exit within the unchanged five-second recovery horizon' in trace for _,trace in result.failures),
        'test_source_sha256':hashlib.sha256((ROOT/'tests/test_durable_faults.py').read_bytes()).hexdigest(),
        'interpretation':'PASS means NO_REPRO of historical five-second failure; any other-stage failure remains distinct. This observed single component cannot qualify release91 or prove a unique historical cause.',
        'duration_seconds':(monotonic_ns()-beginning)/1e9,'logger_failures':logger_failures,
        'trace_sha256':hashlib.sha256((output/'events.jsonl').read_bytes()).hexdigest(),
        'production_approved':False},indent=2)+'\n')
    return 0 if result.wasSuccessful() else 1


def launch(output):
    # Reap only adopted descendants of this new reproduction process.
    import ctypes
    assert ctypes.CDLL(None).prctl(36,1,0,0,0)==0
    output.mkdir(parents=True, exist_ok=False)
    before=source_guard()
    (output/'source-before.json').write_text(json.dumps(before,indent=2)+'\n')
    if not before['all_266_match_original']:
        raise SystemExit('source guard mismatch; no native run')
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
    after=source_guard()
    (output/'source-after.json').write_text(json.dumps(after,indent=2)+'\n')
    report={'command':command,'started_at':started,'finished_at':datetime.now(timezone.utc).isoformat(),
        'wall_seconds':monotonic()-beginning,'worker_identity':identity,'exit_code':code,
        'watchdog_seconds':27,'whole_budget_seconds':30,'timed_out':timed_out,
        'own_process_group_only':True,'owned_children':cleanup,
        'final_owned_identities':[birth(item['original']['pid']) for item in cleanup],
        'source_unchanged':before['source_sha256']==after['source_sha256'],
        'all_266_match_original':after['all_266_match_original'],
        'whole_budget_met':monotonic()-beginning<=30,
        'production_approved':False}
    (output/'launch.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return code


if __name__=='__main__':
    if len(sys.argv)!=3 or sys.argv[1] not in ('--run','--worker'):
        raise SystemExit('explicit --run NEW_OUTPUT is required; no default action')
    raise SystemExit(worker(Path(sys.argv[2])) if sys.argv[1]=='--worker' else launch(Path(sys.argv[2])))
