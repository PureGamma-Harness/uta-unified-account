"""Frozen proposed zero-child PURE wrapper. Not run until root budget."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import time
import unittest

GUARD_CODE = "\nimport sys, os, signal, _signal, socket, _socket, _thread, threading, subprocess, _posixsubprocess, importlib.machinery\n_scope_denials=[]\n_scope_checks=[]\nclass ScopeDenied(BaseException):pass\ndef _scope_deny(name):\n    _scope_denials.append(name)\n    raise ScopeDenied(name)\ndef _scope_audit(event, args):\n    if event == 'subprocess.Popen':\n        if not globals().get('_scope_launch_allowed',False):_scope_deny(event)\n    elif event.startswith(('socket.','sqlite3.','ctypes.')) and event not in {'socket.gethostname'}:\n        _scope_deny(event)\n    elif event in {'os.system','os.fork','os.forkpty','os.posix_spawn','os.exec','os.kill','os.killpg',\n                   'signal.pthread_kill','signal.pidfd_send_signal','fcntl.flock'}:\n        _scope_deny(event)\nsys.addaudithook(_scope_audit)\ndef _scope_block(name):\n    def blocked(*args,**kwargs):return _scope_deny(name)\n    return blocked\nfor _name in ('system','fork','forkpty','posix_spawn','posix_spawnp','kill','killpg',\n              'execl','execle','execlp','execlpe','execv','execve','execvp','execvpe'):\n    if hasattr(os,_name):setattr(os,_name,_scope_block('os.'+_name))\nfor _signal_module in (signal,_signal):\n    for _name in ('signal','raise_signal','pthread_kill','pidfd_send_signal','setitimer','alarm','pthread_sigmask','sigwait','sigwaitinfo','sigtimedwait','set_wakeup_fd','siginterrupt','pause'):\n        if hasattr(_signal_module,_name):setattr(_signal_module,_name,_scope_block(_signal_module.__name__+'.'+_name))\n_thread.start_new_thread=_scope_block('_thread.start_new_thread')\n_thread.start_new=_scope_block('_thread.start_new')\n_thread.interrupt_main=_scope_block('_thread.interrupt_main')\nthreading._start_new_thread=_scope_block('threading._start_new_thread')\nthreading.Thread.start=_scope_block('threading.Thread.start')\nfor _socket_module in (socket,_socket):\n    if hasattr(_socket_module,'socketpair'):setattr(_socket_module,'socketpair',_scope_block(_socket_module.__name__+'.socketpair'))\n_scope_real_fork_exec=subprocess._fork_exec\ndef _scope_fork_exec(*args,**kwargs):\n    if not globals().get('_scope_launch_allowed',False):_scope_deny('raw_fork_exec')\n    return _scope_real_fork_exec(*args,**kwargs)\nsubprocess._fork_exec=_scope_fork_exec\n_posixsubprocess.fork_exec=_scope_fork_exec\nsubprocess.Popen=_scope_block('subprocess.Popen')\ndef _scope_patch_module(module):\n    targets={\n        'concurrent.futures.thread':('ThreadPoolExecutor',('submit','_adjust_thread_count')),\n        'concurrent.futures.process':('ProcessPoolExecutor',('submit','_spawn_process','_launch_processes','_start_executor_manager_thread')),\n        'multiprocessing.process':('BaseProcess',('start',)),\n        'multiprocessing.pool':('Pool',('__init__',)),\n    }\n    target=targets.get(module.__name__)\n    if target:\n        cls=getattr(module,target[0],None)\n        if cls is not None:\n            for name in target[1]:\n                if hasattr(cls,name):setattr(cls,name,_scope_block(module.__name__+'.'+target[0]+'.'+name))\n_scope_real_loader=importlib.machinery.SourceFileLoader.exec_module\ndef _scope_exec_module(loader,module):\n    _scope_real_loader(loader,module)\n    _scope_patch_module(module)\nimportlib.machinery.SourceFileLoader.exec_module=_scope_exec_module\nfor _module in tuple(sys.modules.values()):\n    if _module is not None:_scope_patch_module(_module)\nfor _event in ('sqlite3.connect','socket.connect','os.kill','os.fork','subprocess.Popen'):\n    try:sys.audit(_event)\n    except ScopeDenied:_scope_checks.append(_event)\n    else:raise AssertionError('hard guard selfcheck failed')\n_scope_denials.clear()\n"

MODULES=('test_independent_m0_d2_export','test_independent_m0_d2','test_independent_m0_diagnostics')

def main():
    os.umask(0o077);sys.dont_write_bytecode=True
    source,output,identity=map(Path,sys.argv[1:4])
    assert source.is_absolute() and output.is_absolute() and identity.is_absolute()
    assert stat.S_IMODE(output.stat().st_mode)==0o700
    assert sorted(os.sched_getaffinity(0))==[2]
    provenance=json.loads(identity.read_bytes())
    assert sha256(Path(__file__).read_bytes()).hexdigest()==provenance['runner_sha256']
    expected={'tools/independent_m0_controller.py'}|{'tests/'+name+'.py' for name in MODULES}
    assert set(provenance['materialized_sha256'])==expected
    for name,wanted in provenance['materialized_sha256'].items():
        assert sha256((source/name).read_bytes()).hexdigest()==wanted
    assert not (source/'uta').exists()
    scratch=output/'scratch';scratch.mkdir(mode=0o700);tempfile.tempdir=str(scratch)
    os.environ['TMPDIR']=str(scratch)
    executable=Path(sys.executable).resolve()
    runtime={'python':sys.version,'executable':str(executable),'binary_sha256':sha256(executable.read_bytes()).hexdigest(),
             'affinity':sorted(os.sched_getaffinity(0)),'isolated':sys.flags.isolated,'no_site':sys.flags.no_site}
    assert runtime['isolated']==1 and runtime['no_site']==1
    sys.path.insert(0,str(source/'tests'))
    exec(GUARD_CODE,globals())
    class ProductFinder:
        def find_spec(self,fullname,path=None,target=None):
            if fullname.split('.')[0] in {'sqlite3','_sqlite3','uta'}:_scope_deny('import:'+fullname)
    sys.meta_path.insert(0,ProductFinder())
    def import_audit(event,args):
        if event=='import' and args[0].split('.')[0] in {'sqlite3','_sqlite3','uta'}:_scope_deny('import:'+args[0])
    sys.addaudithook(import_audit)
    started=time.monotonic_ns();stamp=datetime.now(timezone.utc).isoformat();outcome=None
    try:
        suite=unittest.defaultTestLoader.loadTestsFromNames(list(MODULES))
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        outcome={'tests':result.testsRun,'errors':len(result.errors),'failures':len(result.failures),
                 'skipped':len(result.skipped),'successful':result.wasSuccessful()}
    finally:
        blocked=sorted(n for n in sys.modules if n.split('.')[0] in {'sqlite3','_sqlite3','uta'})
        record={'kind':'NEW_SOURCE_D2_EXPORT_ZERO_CHILD_PURE_FIRST','source':provenance,'runtime':runtime,
            'started_at_utc':stamp,'started_monotonic_ns':started,'finished_monotonic_ns':time.monotonic_ns(),
            'outcome':outcome,'guard_checks':_scope_checks,'unexpected_denials':_scope_denials,
            'blocked_module_cache':blocked,'actual_children':0,'child_creation_permission':False,
            'actual_mount_quota_SQL_native_crypto_network_probe':False}
        with (output/'first.execution.json').open('x') as f:json.dump(record,f,sort_keys=True,indent=2);f.write('\n')
    return 0 if outcome and outcome['successful'] and not _scope_denials and not blocked else 1

if __name__=='__main__':raise SystemExit(main())
