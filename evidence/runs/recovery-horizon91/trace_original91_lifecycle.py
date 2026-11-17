"""Future original-91e observation with explicit observer lifecycle; never retrofit old raw."""
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
    os.umask(0o077)
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    stream = (output / 'events.jsonl').open('x', buffering=1)
    lock = Lock()
    logger_failures, processes, pidfds = [], {}, {}
    sampling_failures, observer_failures = [], []
    observer_lifecycle = {}
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
    def observer_run(name, target):
        state = observer_lifecycle[name] = {'started':True, 'ended':False, 'error':None}
        emit('observer_lifecycle_start', observer=name)
        try:
            target()
        except BaseException as error:
            state['error'] = exception_metadata(error)
            observer_failures.append({'observer':name,'exception':state['error']})
            emit('observer_lifecycle_error', observer=name, exception=state['error'])
        finally:
            state['ended'] = True
            emit('observer_lifecycle_end', observer=name)
    watcher = Thread(target=lambda:observer_run('pidfd',watch_exits),
                     name='independent-pidfd-observer', daemon=True)
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
                failure = exception_metadata(error)
                sampling_failures.append(failure)
                emit('sampling_unavailable', exception=failure)
    sampler = Thread(target=lambda:observer_run('code_stack',sample_threads),
                     name='independent-code-stack-observer', daemon=True)
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
    stopped.set()
    observer_post_join = {}
    for name, observer in (('pidfd',watcher),('code_stack',sampler)):
        observer.join(1)
        observed = {'is_alive':observer.is_alive(),
                    'lifecycle':dict(observer_lifecycle.get(name,{}))}
        observer_post_join[name] = observed
        emit('observer_post_join', observer=name, **observed)
    observers_joined = all(not state['is_alive'] and state['lifecycle'].get('started') is True
                           and state['lifecycle'].get('ended') is True
                           and state['lifecycle'].get('error') is None
                           for state in observer_post_join.values())
    for pid,fd in pidfds.items():
        p=select.poll();p.register(fd,select.POLLIN)
        emit('final_owned_child', pid=pid, pidfd_exited=bool(p.poll(0)),
             identity=birth(pid), exitcode=processes[pid].exitcode)
        os.close(fd)
    emit('original_case_end', passed=result.wasSuccessful())
    try:
        stream.close()
    except BaseException as error:
        logger_failures.append(type(error).__name__)
    observation = getattr(case, '_expired_gate_observation', None)
    observation_technical_flags = {
        'fixture_forced_cleanup':bool(observation and observation.get('cleanup_forced_kill')),
        'fixture_cleanup_error':bool(observation and observation.get('cleanup_errors'))}
    evidence_flags = {'observer_post_join':observer_post_join,
                      'both_observers_joined':observers_joined,
                      'observer_failures':observer_failures,
                      'sampling_failures':sampling_failures,
                      'logger_failures':list(logger_failures),
                      **observation_technical_flags}
    evidence_complete = (observers_joined and not observer_failures and not sampling_failures
                         and not logger_failures and not any(observation_technical_flags.values()))
    (output/'result.json').write_text(json.dumps({'base_source':BASE,'runtime':{'python':sys.version,'executable':sys.executable,'sqlite':__import__('sqlite3').sqlite_version},'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
        'case_passed':result.wasSuccessful(),'test_failure_observed':not result.wasSuccessful(),
        'historical_original_assertion_reproduced':any('original bound PID did not exit within the unchanged five-second recovery horizon' in trace for _,trace in result.failures),
        'test_source_sha256':hashlib.sha256((ROOT/'tests/test_durable_faults.py').read_bytes()).hexdigest(),
        'interpretation':'PASS means NO_REPRO of historical five-second failure; any other-stage failure remains distinct. This observed single component cannot qualify release91 or prove a unique historical cause.',
        'duration_seconds':(monotonic_ns()-beginning)/1e9,'logger_failures':logger_failures,
        'evidence_flags':evidence_flags, 'worker_observation_complete':evidence_complete,
        'trace_sha256':hashlib.sha256((output/'events.jsonl').read_bytes()).hexdigest(),
        'production_approved':False},indent=2)+'\n')
    return (0 if result.wasSuccessful() else 1) if evidence_complete else 2


def own_session_scan(sid):
    """Read native metadata only; never signal an unregistered process."""
    members = []
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():
            continue
        try:
            raw = (path/'stat').read_text()
            tail = raw[raw.rindex(')')+2:].split()
            if int(tail[2]) == sid or int(tail[3]) == sid:
                members.append({'pid':int(path.name),'state':tail[0],
                                'pgid':int(tail[2]),'sid':int(tail[3]),
                                'start_ticks':tail[19]})
        except (FileNotFoundError,ProcessLookupError):
            continue  # Process really ended during this read-only scan.
    return members


def launch(output):
    beginning=monotonic()
    started=datetime.now(timezone.utc).isoformat()
    # Reap only adopted descendants of this new reproduction process.
    import ctypes
    assert ctypes.CDLL(None).prctl(36,1,0,0,0)==0
    os.umask(0o077)
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    try:
        before=source_guard()
        (output/'source-before.json').write_text(json.dumps(before,indent=2)+'\n')
        if not before['all_266_match_original']:
            raise ValueError('source guard mismatch')
    except BaseException as error:
        report={'started_at':started,'finished_at':datetime.now(timezone.utc).isoformat(),
                'native_case_started':False,'source_error':exception_metadata(error),
                'source_verified':False,'strict_observation_complete':False,
                'technical_stop_required':True,'production_approved':False,
                'wall_seconds':monotonic()-beginning}
        (output/'launch.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
        return 2
    command=['taskset','-c','2',sys.executable,str(Path(__file__).resolve()),'--worker',str(output/'worker')]
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
    source_error = None
    try:
        after=source_guard()
        (output/'source-after.json').write_text(json.dumps(after,indent=2)+'\n')
    except BaseException as error:
        after={'source_sha256':None,'all_266_match_original':False}
        source_error=exception_metadata(error)
    result_path=output/'worker/result.json'
    worker_result_error = None
    try:
        worker_result=json.loads(result_path.read_text())
    except BaseException as error:
        worker_result={}
        worker_result_error=exception_metadata(error)
    session_scan_error = None
    try:
        session_members = own_session_scan(process.pid)
    except BaseException as error:
        session_members = None
        session_scan_error = exception_metadata(error)
    event_error = None
    try:
        events = [json.loads(line) for line in trace.read_text().splitlines()]
        from collections import Counter
        spawn_starts = Counter(row['shard'] for row in events if row['kind']=='spawn_start')
        spawn_returns = Counter(row['shard'] for row in events if row['kind']=='spawn_return')
        spawn_balanced = bool(spawn_starts) and spawn_starts == spawn_returns
        observation_unknown = any(row['kind'] in ('pidfd_open_unavailable',
            'sampling_unavailable','observation_unavailable') for row in events)
        event_hash_valid = hashlib.sha256(trace.read_bytes()).hexdigest() == worker_result.get('trace_sha256')
    except BaseException as error:
        spawn_balanced,observation_unknown,event_hash_valid = False,True,False
        event_error = exception_metadata(error)
    report={'command':command,'started_at':started,'finished_at':datetime.now(timezone.utc).isoformat(),
        'wall_seconds':monotonic()-beginning,'worker_identity':identity,'exit_code':code,
        'watchdog_seconds':27,'whole_budget_seconds':30,'timed_out':timed_out,
        'own_process_group_only':True,'owned_children':cleanup,
        'final_owned_identities':[birth(item['original']['pid']) for item in cleanup],
        'source_unchanged':before['source_sha256']==after['source_sha256'],
        'all_266_match_original':after['all_266_match_original'],
        'whole_budget_met':monotonic()-beginning<=30,
        'source_error':source_error,'worker_result_error':worker_result_error,
        'session_scan_error':session_scan_error,'new_own_session_members':session_members,
        'spawn_calls_balanced':spawn_balanced,'observation_unknown':observation_unknown,
        'event_read_error':event_error,'event_hash_valid':event_hash_valid,
        'unittest_errors':worker_result.get('errors'),
        'native_case_started':True,
        'worker_observation_complete':worker_result.get('worker_observation_complete',False),
        'evidence_flags':worker_result.get('evidence_flags'),
        'production_approved':False}
    report['strict_observation_complete'] = (
        not timed_out and report['whole_budget_met'] and report['source_unchanged']
        and report['all_266_match_original'] and source_error is None
        and worker_result_error is None and report['worker_observation_complete']
        and all(not row['forced_cleanup'] for row in cleanup)
        and all(not row.get('present',True) for row in report['final_owned_identities'])
        and session_scan_error is None and session_members == []
        and event_error is None and spawn_balanced and not observation_unknown
        and event_hash_valid and worker_result.get('errors') == 0)
    report['technical_stop_required'] = not report['strict_observation_complete']
    report['external_whole_budget_and_runtime_identity_still_required'] = True
    (output/'launch.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return code if report['strict_observation_complete'] else 2


if __name__=='__main__':
    if len(sys.argv)!=3 or sys.argv[1] not in ('--run','--worker'):
        raise SystemExit('explicit --run NEW_OUTPUT is required; no default action')
    raise SystemExit(worker(Path(sys.argv[2])) if sys.argv[1]=='--worker' else launch(Path(sys.argv[2])))
