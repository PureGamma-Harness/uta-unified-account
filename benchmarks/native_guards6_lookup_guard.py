"""Test-control only: retain real stdlib classes, poison unmocked OS actions.

This does not replace native70 source or controller functions. The six fixed
fixtures patch these same module attribute lookups with their own fakes.
"""
import os
from pathlib import Path
import sys


class UnexpectedOperation(BaseException):
    pass


class LookupGuard:
    def __init__(self):
        self.attempts=[];self.bindings=[]

    def reject(self,label):
        def denied(*args,**kwargs):
            self.attempts.append(label)
            raise UnexpectedOperation('unmocked operation: '+label)
        return denied

    def install(self,obj,name,label):
        if not hasattr(obj,name):return
        original=getattr(obj,name);own=name in vars(obj)
        denied=self.reject(label)
        setattr(obj,name,denied)
        self.bindings.append((obj,name,original,own,denied))

    def restrict_proc_stat(self,name):
        original=getattr(os,name)
        def checked(path,*args,**kwargs):
            if isinstance(path,(str,bytes,os.PathLike)):
                value=os.fsdecode(path)
                if value=='/proc' or value.startswith('/proc/'):self.reject('proc '+name)()
            return original(path,*args,**kwargs)
        setattr(os,name,checked);self.bindings.append((os,name,original,True,checked))

    def install_apis(self):
        import _thread
        import multiprocessing as mp
        import multiprocessing.connection as connection
        import signal
        import socket
        import subprocess
        import threading
        for name in ('pidfd_open','kill','killpg','fork','forkpty','posix_spawn','posix_spawnp','getppid',
                     'geteuid','open','close','pipe','pipe2','read','write','fsync','link','unlink','rename','replace','mkdir','rmdir'):
            self.install(os,name,'os.'+name)
        for name in ('pidfd_send_signal','signal','set_wakeup_fd','alarm','setitimer'):
            self.install(signal,name,'signal.'+name)
        self.restrict_proc_stat('stat');self.restrict_proc_stat('lstat')
        self.install(subprocess,'Popen','subprocess.Popen')
        self.install(_thread,'start_new_thread','_thread.start_new_thread')
        self.install(threading,'_start_new_thread','threading._start_new_thread')
        for name in ('socket','socketpair','fromfd','create_connection'):
            self.install(socket,name,'socket.'+name)
        for name in ('get_context','Pipe','Lock','RLock','Semaphore','BoundedSemaphore','Event','Condition','Manager'):
            self.install(mp,name,'multiprocessing.'+name)
        self.install(mp.Process,'start','multiprocessing.Process.start')
        # Preserve the real class/close path. No selected fixture constructs it.
        self.install(connection.Connection,'__init__','real Connection construction')
        self.install(connection.Listener,'__init__','real Listener construction')
        self.install(connection,'Client','real Client connection')

    def identities_intact(self):
        return all(getattr(obj,name) is denied for obj,name,original,own,denied in self.bindings)

    def restore(self):
        for obj,name,original,own,denied in reversed(self.bindings):
            if own:setattr(obj,name,original)
            else:delattr(obj,name)

    def audit(self,event,args):
        if event=='import' and args and str(args[0]).split('.')[0] in ('uta','sqlite3','_sqlite3'):
            self.reject('forbidden import '+str(args[0]))()
        if event=='open' and args and isinstance(args[0],(str,bytes,os.PathLike)):
            path=os.fsdecode(args[0])
            if path=='/proc' or path.startswith('/proc/'):
                self.reject('proc open')()
        if event in ('subprocess.Popen','os.fork','os.forkpty','os.posix_spawn','os.kill','os.killpg','socket.__new__','socket.connect','socket.bind'):
            self.reject('audit '+event)()
