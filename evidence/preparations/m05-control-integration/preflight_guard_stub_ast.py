"""One guard-only pure stub/AST preflight; never loads product/helper/tests.

Raw launch/signal/thread APIs are first replaced by unreachable sentinels. The
guard string and parent import guards are extracted as AST, not by importing the
runner. Standard library imports are real passive imports; forbidden API probes
exercise denial before the underlying sentinel. No interpreter child is run.
"""
import ast
from datetime import datetime, timezone
from hashlib import sha256
import importlib.machinery
import json
import os
from pathlib import Path
import signal
import _signal
import socket
import _socket
import stat
import subprocess
import sys
import threading
import time
import _posixsubprocess
import _thread

def main():
    os.umask(0o077)
    runner,output,identity=map(Path,sys.argv[1:4])
    assert stat.S_IMODE(output.stat().st_mode)==0o700
    raw=runner.read_bytes();provenance=json.loads(identity.read_bytes())
    assert sha256(raw).hexdigest()==provenance['runner_sha256']
    assert sorted(os.sched_getaffinity(0))==[2]
    tree=ast.parse(raw)
    guard=ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='GUARD_CODE' for t in n.targets)))
    main_ast=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
    import_nodes=[n for n in main_ast.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in {'ProductFinder','parent_audit'}]
    assert len(import_nodes)==2
    guard_ast=ast.parse(guard)
    audit=next(n for n in guard_ast.body if isinstance(n,ast.FunctionDef) and n.name=='_scope_audit')
    assert not any(isinstance(n,ast.Constant) and n.value=='import' for n in ast.walk(audit))
    raw_calls=[];checks=[];imports=[]
    class RawEffectReached(BaseException):pass
    def sentinel(name):
        def invoke(*args,**kwargs):
            raw_calls.append(name);raise RawEffectReached(name)
        return invoke
    # Even a faulty guard cannot reach these real capabilities in this preflight.
    for name in ('system','fork','forkpty','posix_spawn','posix_spawnp','kill','killpg','execl','execle','execlp','execlpe','execv','execve','execvp','execvpe'):
        if hasattr(os,name):setattr(os,name,sentinel('os.'+name))
    for module in (signal,_signal):
        for name in ('signal','raise_signal','pthread_kill','pidfd_send_signal','setitimer','alarm','pthread_sigmask','sigwait','sigwaitinfo','sigtimedwait','set_wakeup_fd','siginterrupt','pause'):
            if hasattr(module,name):setattr(module,name,sentinel(module.__name__+'.'+name))
    for name in ('start_new_thread','start_new','interrupt_main'):
        if hasattr(_thread,name):setattr(_thread,name,sentinel('_thread.'+name))
    threading.Thread.start=sentinel('threading.Thread.start')
    threading._start_new_thread=sentinel('threading._start_new_thread')
    for module in (socket,_socket):
        if hasattr(module,'socketpair'):setattr(module,'socketpair',sentinel(module.__name__+'.socketpair'))
    subprocess.Popen=sentinel('subprocess.Popen')
    subprocess._fork_exec=sentinel('subprocess._fork_exec')
    _posixsubprocess.fork_exec=sentinel('_posixsubprocess.fork_exec')
    started=time.monotonic_ns();started_utc=datetime.now(timezone.utc).isoformat()
    namespace={'__name__':'guard_stub_scope'}
    outcome='ERROR';error=None
    try:
        exec(compile(guard,'<guard-under-test>','exec'),namespace)
        # These imports caused the original failure; no test module is loaded.
        from unittest.mock import patch
        import asyncio
        import concurrent.futures
        from concurrent.futures import ThreadPoolExecutor,ProcessPoolExecutor
        import multiprocessing.pool
        imports.extend(['unittest.mock','asyncio','concurrent.futures','concurrent.futures.thread','concurrent.futures.process','multiprocessing.pool'])
        exec(compile(ast.Module(body=import_nodes,type_ignores=[]),'<parent-import-guards>','exec'),namespace)
        sys.meta_path.insert(0,namespace['ProductFinder']())
        sys.addaudithook(namespace['parent_audit'])
        Denied=namespace['ScopeDenied']
        def rejected(name,call):
            before=len(namespace['_scope_denials'])
            try:call()
            except Denied:
                assert len(namespace['_scope_denials'])==before+1
                checks.append({'case':name,'status':'DENIED_BEFORE_RAW_EFFECT','audit_or_monkeyguard':namespace['_scope_denials'][-1]})
            else:raise AssertionError('scope guard allowed '+name)
        for name in ('sqlite3','_sqlite3','uta'):
            assert name not in sys.modules
            rejected('active_import_'+name,lambda name=name:__import__(name))
            assert name not in sys.modules
        cases=[
            ('unapproved_openssl',lambda:subprocess.Popen(['openssl','version'])),
            ('unapproved_python_child',lambda:subprocess.Popen([sys.executable,'-I','-S','-c','pass'])),
            ('os_system',lambda:os.system('UNREACHABLE_STUB')),
            ('os_fork',lambda:os.fork()),
            ('raw_subprocess_fork_exec',lambda:subprocess._fork_exec()),
            ('raw_posix_fork_exec',lambda:_posixsubprocess.fork_exec()),
            ('thread_start',lambda:threading.Thread.start(object())),
            ('thread_alias',lambda:threading._start_new_thread(lambda:None,())),
            ('raw_thread',lambda:_thread.start_new_thread(lambda:None,())),
            ('threadpool_submit',lambda:ThreadPoolExecutor.submit(object(),lambda:None)),
            ('processpool_submit',lambda:ProcessPoolExecutor.submit(object(),lambda:None)),
            ('multiprocessing_start',lambda:sys.modules['multiprocessing.process'].BaseProcess.start(object())),
            ('multiprocessing_pool',lambda:multiprocessing.pool.Pool.__init__(object())),
            ('os_kill',lambda:os.kill(0,0)),
            ('signal_handler',lambda:signal.signal(signal.SIGTERM,signal.SIG_DFL)),
            ('signal_wakeup_fd',lambda:signal.set_wakeup_fd(-1)),
            ('signal_alarm',lambda:signal.alarm(0)),
            ('raw_signal_handler',lambda:_signal.signal(_signal.SIGTERM,_signal.SIG_DFL)),
            ('raw_signal_wakeup_fd',lambda:_signal.set_wakeup_fd(-1)),
            ('raw_signal_raise',lambda:_signal.raise_signal(_signal.SIGTERM)),
            ('socketpair',lambda:socket.socketpair()),
            ('raw_socketpair',lambda:_socket.socketpair()),
        ]
        for name,call in cases:rejected(name,call)
        # Audit-only effects are represented by API stubs that emit the same
        # event then would reach the sentinel; no real socket/SQL/FFI is invoked.
        def audited_stub(event):
            def invoke():
                sys.audit(event);sentinel('unreachable_'+event)()
            return invoke
        for event in ('socket.__new__','socket.connect','socket.getaddrinfo','sqlite3.connect','ctypes.dlopen','ctypes.dlsym','ctypes.call_function','subprocess.Popen'):
            rejected('stub_api_'+event,audited_stub(event))
        assert not raw_calls
        outcome='PASS_STUB_AST_ONLY'
    except BaseException as exc:
        error={'type':type(exc).__name__,'message':str(exc)}
        raise
    finally:
        value=dict(kind='M05_GUARD_FIRST_STUB_AST_PREFLIGHT',status=outcome,error=error,
            source=provenance,runtime={'python':sys.version,'executable':str(Path(sys.executable).resolve()),'binary_sha256':sha256(Path(sys.executable).resolve().read_bytes()).hexdigest(),'affinity':sorted(os.sched_getaffinity(0))},
            started_at_utc=started_utc,started_monotonic_ns=started,finished_monotonic_ns=time.monotonic_ns(),
            standard_library_imports=imports,denied_api_cases=checks,raw_effect_sentinel_calls=raw_calls,
            guard_audit_selfchecks=namespace.get('_scope_checks',[]),all_scope_denials=namespace.get('_scope_denials',[]),
            actual_children=0,virtual_children=0,product_or_test_modules_loaded=False,cold_helper_executed=False,
            whole_suite_executed=False,next_run_permitted=False)
        with (output/'first.stub.execution.json').open('x') as f:json.dump(value,f,sort_keys=True,indent=2);f.write('\n')
    print(json.dumps({'status':outcome,'denied_api_cases':len(checks),'actual_children':0,'whole_suite_executed':False},sort_keys=True))
    return 0

if __name__=='__main__':raise SystemExit(main())
