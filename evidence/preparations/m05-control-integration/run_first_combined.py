"""One fixed-source guarded unittest discovery; no financial/native execution.

The caller materializes the narrow control tree and supplies an exclusive private
output. This wrapper preserves test selection and helper source, adds hard guards
to parent and every permitted cold interpreter, and retains every helper result.
"""
import ast
import atexit
from datetime import datetime, timezone
from hashlib import sha256
import importlib.machinery
import json
import os
from pathlib import Path
import platform
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
import unittest
import _thread

GUARD_CODE = r'''
import sys, os, signal, _signal, socket, _socket, _thread, threading, subprocess, _posixsubprocess, importlib.machinery
_scope_denials=[]
_scope_checks=[]
class ScopeDenied(BaseException):pass
def _scope_deny(name):
    _scope_denials.append(name)
    raise ScopeDenied(name)
def _scope_audit(event, args):
    if event == 'subprocess.Popen':
        if not globals().get('_scope_launch_allowed',False):_scope_deny(event)
    elif event.startswith(('socket.','sqlite3.','ctypes.')) and event not in {'socket.gethostname'}:
        _scope_deny(event)
    elif event in {'os.system','os.fork','os.forkpty','os.posix_spawn','os.exec','os.kill','os.killpg',
                   'signal.pthread_kill','signal.pidfd_send_signal','fcntl.flock'}:
        _scope_deny(event)
sys.addaudithook(_scope_audit)
def _scope_block(name):
    def blocked(*args,**kwargs):return _scope_deny(name)
    return blocked
for _name in ('system','fork','forkpty','posix_spawn','posix_spawnp','kill','killpg',
              'execl','execle','execlp','execlpe','execv','execve','execvp','execvpe'):
    if hasattr(os,_name):setattr(os,_name,_scope_block('os.'+_name))
for _signal_module in (signal,_signal):
    for _name in ('signal','raise_signal','pthread_kill','pidfd_send_signal','setitimer','alarm','pthread_sigmask','sigwait','sigwaitinfo','sigtimedwait','set_wakeup_fd','siginterrupt','pause'):
        if hasattr(_signal_module,_name):setattr(_signal_module,_name,_scope_block(_signal_module.__name__+'.'+_name))
_thread.start_new_thread=_scope_block('_thread.start_new_thread')
_thread.start_new=_scope_block('_thread.start_new')
_thread.interrupt_main=_scope_block('_thread.interrupt_main')
threading._start_new_thread=_scope_block('threading._start_new_thread')
threading.Thread.start=_scope_block('threading.Thread.start')
for _socket_module in (socket,_socket):
    if hasattr(_socket_module,'socketpair'):setattr(_socket_module,'socketpair',_scope_block(_socket_module.__name__+'.socketpair'))
_scope_real_fork_exec=subprocess._fork_exec
def _scope_fork_exec(*args,**kwargs):
    if not globals().get('_scope_launch_allowed',False):_scope_deny('raw_fork_exec')
    return _scope_real_fork_exec(*args,**kwargs)
subprocess._fork_exec=_scope_fork_exec
_posixsubprocess.fork_exec=_scope_fork_exec
subprocess.Popen=_scope_block('subprocess.Popen')
def _scope_patch_module(module):
    targets={
        'concurrent.futures.thread':('ThreadPoolExecutor',('submit','_adjust_thread_count')),
        'concurrent.futures.process':('ProcessPoolExecutor',('submit','_spawn_process','_launch_processes','_start_executor_manager_thread')),
        'multiprocessing.process':('BaseProcess',('start',)),
        'multiprocessing.pool':('Pool',('__init__',)),
    }
    target=targets.get(module.__name__)
    if target:
        cls=getattr(module,target[0],None)
        if cls is not None:
            for name in target[1]:
                if hasattr(cls,name):setattr(cls,name,_scope_block(module.__name__+'.'+target[0]+'.'+name))
_scope_real_loader=importlib.machinery.SourceFileLoader.exec_module
def _scope_exec_module(loader,module):
    _scope_real_loader(loader,module)
    _scope_patch_module(module)
importlib.machinery.SourceFileLoader.exec_module=_scope_exec_module
for _module in tuple(sys.modules.values()):
    if _module is not None:_scope_patch_module(_module)
for _event in ('sqlite3.connect','socket.connect','os.kill','os.fork','subprocess.Popen'):
    try:sys.audit(_event)
    except ScopeDenied:_scope_checks.append(_event)
    else:raise AssertionError('hard guard selfcheck failed')
_scope_denials.clear()
'''

def dump_new(path, value):
    raw=(json.dumps(value,sort_keys=True,indent=2)+'\n').encode()
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as stream:stream.write(raw)

def main():
    os.umask(0o077)
    source,output,identity=map(Path,sys.argv[1:4])
    assert source.is_absolute() and output.is_absolute() and identity.is_absolute()
    assert stat.S_IMODE(output.stat().st_mode)==0o700
    assert not (source/'uta').exists()
    provenance=json.loads(identity.read_bytes())
    for name,wanted in provenance['materialized_sha256'].items():
        assert sha256((source/name).read_bytes()).hexdigest()==wanted
    executable=Path(sys.executable).resolve()
    runtime=dict(python=sys.version,implementation=platform.python_implementation(),
        executable=str(executable),executable_sha256=sha256(executable.read_bytes()).hexdigest(),
        affinity=sorted(os.sched_getaffinity(0)),isolated=sys.flags.isolated,no_site=sys.flags.no_site)
    assert runtime['affinity']==[2] and runtime['isolated']==1 and runtime['no_site']==1
    scratch=output/'scratch';scratch.mkdir(mode=0o700)
    children_root=output/'children';children_root.mkdir(mode=0o700)
    probes_root=output/'probes';probes_root.mkdir(mode=0o700)
    tempfile.tempdir=str(scratch);os.environ['TMPDIR']=str(scratch)
    sys.dont_write_bytecode=True
    helper_ast=ast.parse((source/'tools/cold_import_contract.py').read_bytes())
    helper_code=ast.literal_eval(next(n.value for n in helper_ast.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CHILD_CODE' for t in n.targets)))
    original_popen=subprocess.Popen
    original_fork_exec=subprocess._fork_exec
    records=[];probes=[];launches=[]
    expected=['deny_sqlite3','deny_uta','controller','escrow','escrow','controller']
    state={'active':False}
    sys.path.insert(0,str(source/'tests'))
    # Guards become active before any controller, helper or test import.
    exec(GUARD_CODE,globals())
    original_loader=importlib.machinery.SourceFileLoader.exec_module
    class ProductFinder:
        def find_spec(self,fullname,path=None,target=None):
            if fullname.split('.')[0] in {'sqlite3','_sqlite3','uta'}:_scope_deny('import:'+fullname)
    sys.meta_path.insert(0,ProductFinder())
    def parent_audit(event,args):
        if event=='import' and args[0].split('.')[0] in {'sqlite3','_sqlite3','uta'}:_scope_deny('import:'+args[0])
    sys.addaudithook(parent_audit)
    def fork_exec(*args,**kwargs):
        if not state['active']:_scope_deny('raw_fork_exec')
        return original_fork_exec(*args,**kwargs)
    subprocess._fork_exec=fork_exec
    import _posixsubprocess
    _posixsubprocess.fork_exec=fork_exec
    def guarded_popen(argv,*args,**kwargs):
        global _scope_launch_allowed
        mode=argv[5] if isinstance(argv,list) and len(argv)==7 else None
        idx=len(launches)
        if not (idx<6 and argv==[sys.executable,'-I','-S','-c',helper_code,expected[idx],str(source)]
                and not args and kwargs.get('stdin')==subprocess.DEVNULL
                and kwargs.get('close_fds') is True and isinstance(kwargs.get('env'),dict)
                and not any(k.startswith('PYTHON') for k in kwargs['env'])
                and Path(kwargs['cwd']).is_relative_to(output)
                and kwargs['stdout'].name.startswith(str(output))
                and kwargs['stderr'].name.startswith(str(output))):
            _scope_deny('unapproved_Popen')
        guard_path=children_root/('child-%02d.guard.json'%(idx+1))
        prefix=GUARD_CODE+'\nimport json, atexit\n'
        prefix+='def _save_guard():\n    with open('+repr(str(guard_path))+",'x') as f: json.dump({'kind':'CHILD_HARD_GUARD','checks':_scope_checks,'unexpected_denials':_scope_denials},f,sort_keys=True)\n"
        prefix+='atexit.register(_save_guard)\n'
        guarded=list(argv);guarded[4]=prefix+helper_code
        entry=dict(index=idx+1,mode=mode,original_code_sha256=sha256(helper_code.encode()).hexdigest(),
            guarded_code_sha256=sha256(guarded[4].encode()).hexdigest(),start_monotonic_ns=time.monotonic_ns())
        launches.append(entry)
        _scope_launch_allowed=True;state['active']=True
        try:child=original_popen(guarded,**kwargs)
        finally:_scope_launch_allowed=False;state['active']=False
        entry['pid']=child.pid;records.append((entry,child,guard_path))
        return child
    subprocess.Popen=guarded_popen
    def load(loader,module):
        original_loader(loader,module)
        if Path(getattr(module,'__file__','')).resolve()==source/'tools/cold_import_contract.py':
            original_probe=module.probe_import
            def captured(mode,*args,**kwargs):
                entry={'mode':mode,'source_module':module.__name__}
                probes.append(entry)
                if kwargs.get('evidence_root') is None:
                    path=probes_root/('probe-%02d'%len(probes));path.mkdir(mode=0o700)
                    kwargs['evidence_root']=path
                value=original_probe(mode,*args,**kwargs);entry['result']=value
                return value
            module.probe_import=captured
    importlib.machinery.SourceFileLoader.exec_module=load
    started=time.monotonic_ns();started_utc=datetime.now(timezone.utc).isoformat()
    outcome=None
    try:
        suite=unittest.defaultTestLoader.discover(str(source/'tests'),pattern='test_independent_m0_*.py')
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        outcome=dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),
                     skipped=len(result.skipped),successful=result.wasSuccessful())
    finally:
        finished=time.monotonic_ns()
        child_details=[]
        for entry,child,path in records:
            entry.update(returncode=child.returncode,reaped=child.returncode is not None,
                guard=json.loads(path.read_bytes()) if path.exists() else None)
            child_details.append(entry)
        blocked_cache=sorted(n for n in sys.modules if n.split('.')[0] in {'sqlite3','_sqlite3','uta'})
        hard_ok=(len(launches)==6 and len(records)==6 and not _scope_denials and not blocked_cache
            and all(e['returncode']==0 and e['reaped'] and e['guard'] and not e['guard']['unexpected_denials'] for e in child_details))
        summary=dict(kind='M05_FIRST_GUARDED_COMBINED_PURE',source=provenance,runtime=runtime,
            started_at_utc=started_utc,started_monotonic_ns=started,finished_monotonic_ns=finished,
            elapsed_ns=finished-started,discovery_pattern='test_independent_m0_*.py',outcome=outcome,
            actual_stdlib_children=len(launches),child_details=child_details,probe_results=probes,
            guard_checks=_scope_checks,unexpected_denials=_scope_denials,blocked_module_cache=blocked_cache,
            hard_guard_acceptance=hard_ok,financial_workload_executed=False,sql_or_crypto_or_network_executed=False)
        dump_new(output/'first.execution.json',summary)
    return 0 if outcome and outcome['successful'] and hard_ok else 1

if __name__=='__main__':raise SystemExit(main())
