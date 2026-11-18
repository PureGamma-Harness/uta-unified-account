"""Pure file/metadata races only; no SQLite import or workload process."""
import errno
from contextlib import contextmanager
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
        with patch.object(Path,'lstat',lambda path,*a,**k:self.disappearing(path,*a,**k)):
            self.assertEqual(m.resource_usage(self.private,self.public),dict(normal=1,escrow=0,cleanup=0,total=1))
    def test_case_tree_aux_disappears_between_enumeration_and_stat(self):
        with patch.object(Path,'lstat',lambda path,*a,**k:self.disappearing(path,*a,**k)):self.assertEqual(m.case_bytes(self.private,self.public,'B'),1)
    def test_generic_tree_has_no_implicit_private_authority_role(self):
        with patch.object(Path,'lstat',lambda path,*a,**k:self.disappearing(path,*a,**k)):
            with self.assertRaises(m.GateError):m.tree_bytes(self.case)
    def test_public_nested_private_layout_never_gets_aux_exception(self):
        public_case=self.public/'case-B-safe';authority=public_case/'B/workload/authority';authority.mkdir(parents=True)
        (authority/'shard-0000.sqlite3').write_bytes(b'm');self.aux=authority/'shard-0000.sqlite3-shm';self.aux.write_bytes(b'aux')
        with patch.object(Path,'lstat',lambda path,*a,**k:self.disappearing(path,*a,**k)):
            with self.assertRaises(m.GateError):m.case_bytes(self.private,self.public,'B')
    def test_private_case_cannot_borrow_nested_other_case_layout(self):
        authority=self.case/'P/workload/authority';authority.mkdir(parents=True)
        (authority/'shard-0000.sqlite3').write_bytes(b'm');self.aux=authority/'shard-0000.sqlite3-shm';self.aux.write_bytes(b'aux')
        with patch.object(Path,'lstat',lambda path,*a,**k:self.disappearing(path,*a,**k)):
            with self.assertRaises(m.GateError):m.case_bytes(self.private,self.public,'B')
    def test_explicit_private_case_role_does_not_accept_global_root_layout(self):
        authority=self.case/'B/workload/authority';authority.mkdir(parents=True)
        (authority/'shard-0000.sqlite3').write_bytes(b'm');self.aux=authority/'shard-0000.sqlite3-shm';self.aux.write_bytes(b'aux')
        with patch.object(Path,'lstat',lambda path,*a,**k:self.disappearing(path,*a,**k)):
            with self.assertRaises(m.GateError):m.tree_bytes(self.case,sqlite_aux_role='private_case')
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
        with patch.object(Path,'lstat',lambda path,*a,**k:self.disappearing(path,*a,**k)):
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
        with patch.object(Path,'lstat',lambda path,*a,**k:self.disappearing(path,*a,**k)),patch.object(m.time,'monotonic_ns',side_effect=[0,50_000_001]):
            with self.assertRaises(m.GateError):m.resource_usage(self.private,self.public)
    def test_successful_retry_over_deadline_is_not_accepted(self):
        with patch.object(Path,'lstat',lambda path,*a,**k:self.disappearing(path,*a,**k)),patch.object(m.time,'monotonic_ns',side_effect=[0,1,50_000_001]):
            with self.assertRaisesRegex(m.GateError,'resource_aux_retry_deadline'):m.resource_usage(self.private,self.public)
    def test_unstable_directory_is_not_an_aux_exception(self):
        calls=[]
        def missing(path,*args,**kwargs):
            if path==self.authority:calls.append(1);raise FileNotFoundError(errno.ENOENT,'directory disappeared',str(path))
            return self.real(path,*args,**kwargs)
        with patch.object(Path,'lstat',missing):
            with self.assertRaises((m.GateError,FileNotFoundError)):m.resource_usage(self.private,self.public)
        self.assertEqual(len(calls),1)
    def test_scandir_permission_error_propagates(self):
        def denied(root):raise PermissionError(errno.EACCES,'synthetic directory denied',str(root))
        with patch.object(m.os,'scandir',denied):
            with self.assertRaises(PermissionError):m.resource_usage(self.private,self.public)
    def test_runtime_probe_aux_disappearance_uses_same_bounded_policy(self):
        probe=self.private/'runtime-probe';probe.mkdir();(probe/'private.sqlite3').write_bytes(b'q')
        self.aux=probe/'private.sqlite3-wal';self.aux.write_bytes(b'aux')
        with patch.object(Path,'lstat',lambda path,*a,**k:self.disappearing(path,*a,**k)):
            self.assertEqual(m.resource_usage(self.private,self.public),dict(normal=5,escrow=0,cleanup=0,total=5))
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
    def ordered_scandir(self,real_scandir):
        @contextmanager
        def scan(*args,**kwargs):
            with real_scandir(*args,**kwargs) as entries:
                yield iter(sorted(entries,key=lambda entry:entry.name.endswith('-shm')))
        return scan
    def test_previously_seen_stable_path_cannot_vanish_between_attempts(self):
        stable=self.authority/'stable.json';stable.write_bytes(b's')
        def racing(path,*args,**kwargs):
            if path==self.aux and not getattr(self,'removed',False):
                self.removed=True;path.unlink();stable.unlink()
                raise FileNotFoundError(errno.ENOENT,'synthetic sidecar closed',str(path))
            return self.real(path,*args,**kwargs)
        with patch.object(m.os,'scandir',self.ordered_scandir(m.os.scandir)),patch.object(Path,'lstat',racing):
            with self.assertRaisesRegex(m.GateError,'resource_stable_disappeared_during_retry'):m.resource_usage(self.private,self.public)
    def test_prior_partial_size_lower_bound_survives_retry(self):
        stable=self.authority/'stable.bin';stable.write_bytes(b's');growth=self.authority/'growth.bin'
        def racing(path,*args,**kwargs):
            if path==self.aux and not getattr(self,'removed',False):
                self.removed=True;path.unlink();growth.write_bytes(b'new')
                raise FileNotFoundError(errno.ENOENT,'synthetic sidecar closed',str(path))
            if path==stable:return SimpleNamespace(st_mode=stat.S_IFREG|0o600,st_size=1 if getattr(self,'removed',False) else m.AGGREGATE_CAP-2)
            return self.real(path,*args,**kwargs)
        with patch.object(m.os,'scandir',self.ordered_scandir(m.os.scandir)),patch.object(Path,'lstat',racing):
            with self.assertRaisesRegex(m.GateError,'resource_compartment_cap'):m.resource_usage(self.private,self.public)
    def test_previously_seen_stable_type_cannot_change_on_retry(self):
        stable=self.authority/'stable.json';stable.write_bytes(b's')
        def racing(path,*args,**kwargs):
            if path==self.aux and not getattr(self,'removed',False):
                self.removed=True;path.unlink();stable.unlink();stable.mkdir()
                raise FileNotFoundError(errno.ENOENT,'synthetic sidecar closed',str(path))
            return self.real(path,*args,**kwargs)
        with patch.object(m.os,'scandir',self.ordered_scandir(m.os.scandir)),patch.object(Path,'lstat',racing):
            with self.assertRaisesRegex(m.GateError,'resource_stable_type_changed'):m.resource_usage(self.private,self.public)

class RouterAuxContract(ResourceRaceContract):
    """Apply every existing strict resource boundary to the exact router name."""
    def setUp(self):
        super().setUp();self.main.unlink();self.aux.unlink()
        self.main=self.authority/'router.sqlite3';self.main.write_bytes(b'm')
        self.aux=self.authority/'router.sqlite3-shm';self.aux.write_bytes(b'aux')
    def test_router_exact_B_P_WAL_SHM_root_and_case_matrix(self):
        for case in ('B','P'):
          for suffix in ('wal','shm'):
           for role in ('private_root','private_case'):
            with self.subTest(case=case,suffix=suffix,role=role),TemporaryDirectory(prefix='new-router-exact-matrix-') as directory:
                private=Path(directory)/'private';public=Path(directory)/'public';private.mkdir();public.mkdir()
                authority=private/case/'workload/authority';authority.mkdir(parents=True)
                (authority/'router.sqlite3').write_bytes(b'm');aux=authority/('router.sqlite3-'+suffix);aux.write_bytes(b'x')
                real=Path.lstat;gone=False
                def missing(path,*a,**k):
                    nonlocal gone
                    if path==aux and not gone:
                        gone=True;path.unlink();raise FileNotFoundError(errno.ENOENT,'synthetic last-close',str(path))
                    return real(path,*a,**k)
                with patch.object(Path,'lstat',missing):
                    observed=m.resource_usage(private,public)['normal'] if role=='private_root' else m.case_bytes(private,public,case)
                self.assertEqual(observed,1);self.assertTrue(gone)
    def test_router_public_and_nested_wrong_case_do_not_borrow_role(self):
        for root,api in ((self.public/'case-B-safe/B',lambda:m.case_bytes(self.private,self.public,'B')),
                         (self.case/'P',lambda:m.case_bytes(self.private,self.public,'B')),
                         (self.private/'C',lambda:m.resource_usage(self.private,self.public))):
            with self.subTest(scope=root.relative_to(self.tmp.name)):
                authority=root/'workload/authority';authority.mkdir(parents=True)
                (authority/'router.sqlite3').write_bytes(b'm');self.aux=authority/'router.sqlite3-shm';self.aux.write_bytes(b'x');self.removed=False
                with patch.object(Path,'lstat',lambda path,*a,**k:self.disappearing(path,*a,**k)):
                    with self.assertRaises(m.GateError):api()
    def test_router_unrecognized_names_are_not_granted(self):
        anchors=(('private_root',self.private),)
        for relative in ('B/workload/authority/router0.sqlite3-shm','B/workload/authority/router.sqlite-shm',
                         'B/workload/authority/router.sqlite3.tmp-shm','B/workload/authority/router.sqlite3',
                         'B/workload/authority/router.sqlite3-journal','B/other/authority/router.sqlite3-shm'):
            with self.subTest(relative=relative):self.assertIsNone(m._sqlite_aux_location(self.private/relative,anchors))
    def test_router_EIO_is_not_retried(self):
        original=OSError(errno.EIO,'synthetic IO',str(self.aux));calls=[]
        def failed(path,*a,**k):
            if path==self.aux:calls.append(1);raise original
            return self.real(path,*a,**k)
        with patch.object(Path,'lstat',failed):
            with self.assertRaises(OSError) as caught:m.resource_usage(self.private,self.public)
        self.assertIs(caught.exception,original);self.assertEqual(len(calls),1)
    def test_router_aux_symlink_is_rejected(self):
        self.aux.unlink();self.aux.symlink_to(self.main)
        with self.assertRaises(m.GateError):m.resource_usage(self.private,self.public)
    def test_router_parent_symlink_is_rejected(self):
        moved=self.case/'workload/moved';self.authority.rename(moved);self.authority.symlink_to(moved,target_is_directory=True)
        with self.assertRaises(m.GateError):m.resource_usage(self.private,self.public)
    def test_router_retry_50ms_equality_is_not_admitted(self):
        with patch.object(Path,'lstat',lambda path,*a,**k:self.disappearing(path,*a,**k)),patch.object(m.time,'monotonic_ns',side_effect=[0,50_000_000]):
            with self.assertRaisesRegex(m.GateError,'resource_aux_retry_deadline'):m.resource_usage(self.private,self.public)

if __name__=='__main__':unittest.main()
