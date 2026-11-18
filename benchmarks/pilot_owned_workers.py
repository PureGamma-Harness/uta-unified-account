"""Finite two-child adapter for the unchanged native managed worker.

No respawn, orphan discovery, bare-PID signal or generic supervisor. stdin is
an extra pre-import gate; native lifecycle pipes and _run_worker stay intact.
"""
from datetime import datetime, timezone
import json
from multiprocessing.connection import Connection
import os
from pathlib import Path
import signal
import subprocess
import sys
from time import monotonic, monotonic_ns
from uuid import uuid4

from benchmarks.cross_open_loop_checks import require_gate_budget

PROTECTED_PIDS = frozenset((4471, 8784, 122905, 122907, 123007, 123009, 310035, 310039, 310266, 310269))


def private_json(path, value):
    raw = (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()
    pending = path.with_name(path.name + '.pending-' + uuid4().hex)
    descriptor = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        if os.write(descriptor, raw) != len(raw):
            raise OSError('short private lifecycle write')
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.link(pending, path, follow_symlinks=False); pending.unlink()
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(directory)
    finally: os.close(directory)



def cleanup_call(errors,label,operation):
    try:return True,operation()
    except BaseException as error:
        errors.append(label+'_'+type(error).__name__)
        return False,None


def close_stdin_no_flush(stream,errors,label):
    if stream is None:return
    try:
        if stream.closed:return
        raw=getattr(stream,'raw',None);target=raw if raw is not None else stream
    except BaseException as error:
        errors.append(label+'_inspect_'+type(error).__name__);return
    cleanup_call(errors,label+'_raw_close',target.close)


def guarded_popen(check_outer,deadline,outer_deadline,**arguments):
    check_outer()  # Recheck stop/host AFTER pipe/config/fsync/raw-file setup.
    require_gate_budget(monotonic(),deadline,outer_deadline)
    return subprocess.Popen(**arguments)


def signal_owned_before_deadline(pidfd,deadline,shared_deadline_ns):
    if monotonic()>=deadline:raise TimeoutError('owned cleanup budget expired; no signal')
    if monotonic_ns()>=shared_deadline_ns:raise TimeoutError('shared cleanup deadline expired; no signal')
    signal.pidfd_send_signal(pidfd,signal.SIGKILL)


class OwnedWorkers:
    def __init__(self, router, directory, script, binding):
        self.router, self.directory, self.script = router, Path(directory), str(script)
        self.directory.mkdir(mode=0o700)
        self.binding = binding
        self.owned = []
        self.coordinator = uuid4().hex
        self.cleanup_receipts = None
        self.cleanup_errors = []

    def _outer_check(self):
        if os.getppid() != self.binding['host_pid'] or monotonic() >= self.binding['outer_deadline_monotonic']:
            raise TimeoutError('outer host lost or budget exhausted')
        if (Path(self.binding['host_root']) / 'stop.json').exists():
            raise RuntimeError('outer first-failure stop; no next birth or gate')

    def _host_ack(self, shard, nonce, identity, deadline):
        path=Path(self.binding['host_root'])/'birth-acks'/f"cohort-{self.binding['cohort']}-worker-{shard}.json"
        while not path.exists():
            self._outer_check(); require_gate_budget(monotonic(), deadline, self.binding['outer_deadline_monotonic'])
            from time import sleep
            sleep(.005)
        raw=path.read_bytes()
        if len(raw)>4096: raise ValueError('oversized host birth ACK')
        ack=json.loads(raw)
        expected={'format':1,'session':self.binding['host_session'],'cohort':self.binding['cohort'],'shard':shard,
            'owner_nonce':nonce,'pid':identity['pid'],'identity':{k:identity[k] for k in ('pid','start_ticks','boot_id','uid')},'host_pidfd_held':True}
        if json.dumps(ack,sort_keys=True,separators=(',',':')) != json.dumps(expected,sort_keys=True,separators=(',',':')):
            raise ValueError('host ACK does not bind this exact typed new birth')
        self._outer_check()

    def start(self, deadline):
        from uta.durable_process import _process_identity, _record_process, _registry_schema
        if os.getpid() in PROTECTED_PIDS:
            raise RuntimeError('protected coordinator numeric ID; no proc access')
        self.router._claim_supervisor()
        with self.router._control.control.transaction() as connection:
            _registry_schema(connection)
        _record_process(self.router._control, 'COORDINATOR', None, self.coordinator, 0,
                        _process_identity(os.getpid()), self.coordinator)
        entry=None;stage='startup'
        try:
            for shard in (0, 1):
                self._outer_check()
                if monotonic() >= deadline:
                    raise TimeoutError('worker birth deadline; no next child')
                entry = {'shard': shard, 'process': None, 'pidfd': None, 'gate_released': False, 'stdin_gate_released': False, 'fds': [], 'raw_files': [], 'cleanup_errors': []}
                self.owned.append(entry)  # Own every FD before the next fallible operation.
                stop_read, stop_write = os.pipe(); entry['fds'].extend((stop_read, stop_write))
                gate_read, gate_write = os.pipe(); entry['fds'].extend((gate_read, gate_write))
                ready_read, ready_write = os.pipe(); entry['fds'].extend((ready_read, ready_write))
                nonce = 'worker:' + uuid4().hex
                config = self.directory / f'worker-{shard}-settings.json'
                private_json(config, {'directory': str(self.router.directory), 'shard': shard,
                    'settings': self.router._settings, 'parent_pid': os.getpid(), 'nonce': nonce,
                    'coordinator': self.coordinator, 'source_manifest': self.binding['path'],
                    'manifest_sha256': self.binding['sha256'], 'stop_fd': stop_read, 'gate_fd': gate_read,
                    'ready_fd': ready_write, 'clock_output': str(self.directory / f'worker-{shard}-clock')})
                argv = [sys.executable, '-I', '-S', '-B', self.script, '--worker-settings', str(config)]
                out = open(self.directory / f'worker-{shard}.stdout', 'xb', buffering=0); entry['raw_files'].append(out)
                err = open(self.directory / f'worker-{shard}.stderr', 'xb', buffering=0); entry['raw_files'].append(err)
                stage='Popen'
                process = guarded_popen(self._outer_check,deadline,self.binding['outer_deadline_monotonic'],
                    args=argv, stdin=subprocess.PIPE, stdout=out, stderr=err,
                    pass_fds=(stop_read, gate_read, ready_write), close_fds=True)
                entry['process'] = process
                private_json(self.directory / f'worker-{shard}-birth.json', {
                    'owned_Popen_pid': process.pid, 'argv': argv, 'monotonic_ns': monotonic_ns(),
                    'host_session':self.binding['host_session'],'cohort':self.binding['cohort'],'shard':shard,'owner_nonce':nonce,
                    'pidfd_held': False, 'stdin_gate_released': False, 'native_gate_released': False})
                for descriptor in (stop_read, gate_read, ready_write):
                    os.close(descriptor); entry['fds'].remove(descriptor)
                if process.pid in PROTECTED_PIDS:
                    # Pre-import stdin EOF returns without entering any native service.
                    raise RuntimeError('protected worker numeric ID; no pidfd/proc/signal')
                entry['pidfd'] = os.pidfd_open(process.pid)
                identity = _process_identity(process.pid)
                _record_process(self.router._control, 'SPAWNED', shard, nonce, 0, identity, self.coordinator)
                private_json(self.directory / f'worker-{shard}-held.json', {
                    'held_pidfd': True, 'birth_identity': identity, 'registered': True,
                    'host_session':self.binding['host_session'],'cohort':self.binding['cohort'],'shard':shard,'owner_nonce':nonce,
                    'gates_still_closed': True, 'monotonic_ns': monotonic_ns()})
                entry['stop'] = Connection(stop_write, readable=False); entry['fds'].remove(stop_write)
                entry['gate'] = Connection(gate_write, readable=False); entry['fds'].remove(gate_write)
                entry['ready'] = Connection(ready_read, writable=False); entry['fds'].remove(ready_read)
                entry['fds'].clear()  # Connection objects now own exactly these descriptors.
                self._host_ack(shard,nonce,identity,deadline)
                self._outer_check(); require_gate_budget(monotonic(),deadline,self.binding['outer_deadline_monotonic'])
                stage='stdin_write';process.stdin.write(b'G')
                stage='stdin_flush';process.stdin.flush();entry['stdin_gate_released']=True
                stage='stdin_close';process.stdin.close()
                self._outer_check(); require_gate_budget(monotonic(),deadline,self.binding['outer_deadline_monotonic'])
                stage='native_gate';entry['gate'].send_bytes(b'1');entry['gate_released']=True;stage='ready'
            for entry in self.owned:
                remaining = deadline - monotonic()
                if remaining <= 0 or not entry['ready'].poll(remaining):
                    raise TimeoutError('native readiness deadline')
                report = entry['ready'].recv()
                if (set(report) != {'state','shard','pid','generation'} or report.get('state') != 'ready'
                        or report.get('pid') != entry['process'].pid or report.get('shard') != entry['shard']
                        or type(report.get('generation')) is not int or report['generation'] < 1):
                    raise RuntimeError('native worker failed or readiness identity changed')
                entry['ready_report'] = report
                private_json(self.directory / f"worker-{entry['shard']}-ready.json", {
                    'native_report': report, 'observed_monotonic_ns': monotonic_ns(),
                    'observed_utc': datetime.now(timezone.utc).isoformat()})
        except BaseException as error:
            if entry is not None:entry['cleanup_errors'].append('start_'+stage+'_'+type(error).__name__)
            self.close(deadline=min(deadline, monotonic() + 3))
            raise
        return self

    def check(self):
        self._outer_check()
        if any(e['process'] is None or e['process'].poll() is not None for e in self.owned):
            raise RuntimeError('owned worker exited; no replacement authorized')

    def close(self, *, deadline):
        if self.cleanup_receipts is not None:return self.cleanup_receipts
        receipts=[]
        for entry in self.owned:
            errors=entry['cleanup_errors'];process=entry['process']
            if process is not None:close_stdin_no_flush(process.stdin,errors,'stdin')
            if 'stop' in entry:cleanup_call(errors,'stop_send',lambda entry=entry:entry['stop'].send_bytes(b'1'))
            for descriptor in entry['fds']:cleanup_call(errors,'initial_fd_close',lambda descriptor=descriptor:os.close(descriptor))
            entry['fds'].clear()
        for entry in self.owned:
            errors=entry['cleanup_errors'];process=entry['process'];killed=False
            reaped=process is None;actual_exit=None
            if process is not None:
                try:
                    actual_exit=process.wait(timeout=max(.001,min(.5,deadline-monotonic())));reaped=True
                except subprocess.TimeoutExpired:
                    if entry['pidfd'] is not None:
                        sent,_=cleanup_call(errors,'owned_signal',lambda entry=entry:signal_owned_before_deadline(
                            entry['pidfd'],deadline,self.binding['outer_cleanup_deadline_ns']))
                        killed=sent
                    ok,value=cleanup_call(errors,'post_signal_wait',lambda:process.wait(timeout=max(.001,deadline-monotonic())))
                    if ok:actual_exit=value;reaped=True
                except BaseException as error:errors.append('initial_wait_'+type(error).__name__)
            for name in ('stop','gate','ready'):
                if name in entry:cleanup_call(errors,name+'_close',entry[name].close)
            if entry['pidfd'] is not None:
                cleanup_call(errors,'owned_pidfd_close',lambda entry=entry:os.close(entry['pidfd']));entry['pidfd']=None
            for stream in entry.get('raw_files',()):cleanup_call(errors,'raw_close',stream.close)
            receipts.append({'shard':entry['shard'],'owned_pid':process.pid if process else None,
                'gate_released':entry['gate_released'],'stdin_gate_released':entry['stdin_gate_released'],
                'reaped':reaped,'actual_exit':actual_exit,'held_pidfd_kill_used':killed,
                'cleanup_error':errors[0] if errors else None,'cleanup_errors':list(errors)})
        cleanup_call(self.cleanup_errors,'router_close',self.router.close)
        self.cleanup_receipts=receipts
        private_json(self.directory/'cleanup.json',{'owned_children':receipts,'global_cleanup_errors':self.cleanup_errors,'no_respawn':True})
        return receipts
