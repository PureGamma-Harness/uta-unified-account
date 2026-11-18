"""Pure file/metadata races only; no SQLite import or workload process."""
import errno
import importlib.util
from pathlib import Path
import stat
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('resource_race_controller',ROOT/'tools/independent_m0_controller.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class ResourceRaceContract(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory(prefix='m0-pure-resource-race-');self.addCleanup(self.tmp.cleanup)
        self.private=Path(self.tmp.name)/'private';self.public=Path(self.tmp.name)/'public'
        self.private.mkdir();self.public.mkdir();self.case=self.private/'B'
        self.authority=self.case/'workload/authority';self.authority.mkdir(parents=True)
        self.main=self.authority/'shard-0000.sqlite3';self.main.write_bytes(b'm')
        self.aux=self.authority/'shard-0000.sqlite3-shm';self.aux.write_bytes(b'aux')
        self.real=Path.lstat
    def disappearing(self,path,*args,**kwargs):
        if path==self.aux and not getattr(self,'removed',False):
            self.removed=True;path.unlink()
            raise FileNotFoundError(errno.ENOENT,'synthetic auxiliary disappeared',str(path))
        return self.real(path,*args,**kwargs)
    def test_aggregate_aux_disappears_between_enumeration_and_stat(self):
        with patch.object(Path,'lstat',self.disappearing):
            self.assertEqual(m.resource_usage(self.private,self.public),dict(normal=1,escrow=0,cleanup=0,total=1))
    def test_case_tree_aux_disappears_between_enumeration_and_stat(self):
        with patch.object(Path,'lstat',self.disappearing):self.assertEqual(m.tree_bytes(self.case),1)
    def test_stable_main_disappearance_is_not_retried(self):
        calls=[]
        def missing(path,*args,**kwargs):
            if path==self.main:calls.append(1);raise FileNotFoundError(errno.ENOENT,'stable main missing',str(path))
            return self.real(path,*args,**kwargs)
        with patch.object(Path,'lstat',missing):
            with self.assertRaises((m.GateError,FileNotFoundError)):m.resource_usage(self.private,self.public)
        self.assertEqual(len(calls),1)
    def test_unknown_aux_name_is_not_retried(self):
        other=self.authority/'unexpected.sqlite3-shm';other.write_bytes(b'x');calls=[]
        def missing(path,*args,**kwargs):
            if path==other:calls.append(1);raise FileNotFoundError(errno.ENOENT,'unknown missing',str(path))
            return self.real(path,*args,**kwargs)
        with patch.object(Path,'lstat',missing):
            with self.assertRaises((m.GateError,FileNotFoundError)):m.resource_usage(self.private,self.public)
        self.assertEqual(len(calls),1)
    def test_permission_error_is_never_retried(self):
        calls=[]
        def denied(path,*args,**kwargs):
            if path==self.aux:calls.append(1);raise PermissionError(errno.EACCES,'synthetic denied',str(path))
            return self.real(path,*args,**kwargs)
        with patch.object(Path,'lstat',denied):
            with self.assertRaises(PermissionError):m.resource_usage(self.private,self.public)
        self.assertEqual(len(calls),1)
    def test_aux_missing_with_missing_main_is_fail_closed(self):
        self.main.unlink()
        with patch.object(Path,'lstat',self.disappearing):
            with self.assertRaises((m.GateError,FileNotFoundError)):m.resource_usage(self.private,self.public)
    def test_symlink_main_is_fail_closed(self):
        self.main.unlink();self.main.symlink_to(self.aux)
        with self.assertRaises(m.GateError):m.resource_usage(self.private,self.public)
    def test_continuous_aux_churn_has_three_attempt_limit(self):
        calls=[]
        def missing(path,*args,**kwargs):
            if path==self.aux:calls.append(1);raise FileNotFoundError(errno.ENOENT,'synthetic churn',str(path))
            return self.real(path,*args,**kwargs)
        with patch.object(Path,'lstat',missing):
            with self.assertRaises(m.GateError):m.resource_usage(self.private,self.public)
        self.assertEqual(len(calls),3)
    def test_retry_elapsed_budget_does_not_reset(self):
        with patch.object(Path,'lstat',self.disappearing),patch.object(m.time,'monotonic_ns',side_effect=[0,50_000_001]):
            with self.assertRaises(m.GateError):m.resource_usage(self.private,self.public)
    def test_growth_seen_on_fresh_scan_still_trips_normal_cap(self):
        growth=self.authority/'growth.bin'
        def racing(path,*args,**kwargs):
            if path==self.aux and not getattr(self,'removed',False):
                self.removed=True;path.unlink();growth.write_bytes(b'x')
                raise FileNotFoundError(errno.ENOENT,'synthetic disappeared',str(path))
            if path==growth:return SimpleNamespace(st_mode=stat.S_IFREG|0o600,st_size=m.AGGREGATE_CAP+1)
            return self.real(path,*args,**kwargs)
        with patch.object(Path,'lstat',racing):
            with self.assertRaises(m.GateError):m.resource_usage(self.private,self.public)

if __name__=='__main__':unittest.main()
