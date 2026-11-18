"""Proposed focused companion contracts; KB fixtures/fake ownership only.

Not run until a separate root budget for this new source. No SQL or child.
"""
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('m0_d2_export_contract',ROOT/'tools/independent_m0_controller.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class D2ExportContract(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory(prefix='m0-d2-export-pure-');self.addCleanup(self.tmp.cleanup)
        self.private=Path(self.tmp.name)/'private';self.public=Path(self.tmp.name)/'public'
        self.private.mkdir(mode=0o700);self.public.mkdir(mode=0o700)
        enabled=patch.object(m,'D2_COMPANION_EXPORT_ENABLED',True);enabled.start();self.addCleanup(enabled.stop)

    def snapshot(self,phase='CASE_B',post=False):
        return {'kind':'M0_RESOURCE_SCAN_D2','version':1,'phase':phase,'scope':'PRIVATE_ROOT',
            'catalogue_label':'AUTH_ROUTER_SHM','context_origin':'LAST_QUALIFIED_AUX' if post else 'CURRENT_QUALIFIED_AUX',
            'gate':'POST_RETRY_SCAN_RETURN' if post else 'QUALIFIED_AUX_ENOENT',
            'comparison':'LE' if post else 'LT','legacy_gate':'C933_L377' if post else 'C933_L382',
            'attempt':2 if post else 1,'elapsed_ns':50_000_001 if post else 50_000_000,'deadline_ns':50_000_000,
            'attempts':([{'attempt':1,'scan_wall_ns':2_000_000,'scan_result':'ENOENT'},
                         {'attempt':2,'scan_wall_ns':7_000_000,'scan_result':'RETURNED'}] if post else
                        [{'attempt':1,'scan_wall_ns':8_000_000,'scan_result':'ENOENT'}]),
            'primary_code':'resource_aux_retry_deadline'}

    def ready(self):
        state=m.new_resource_scan_d2_export_state()
        original={'leader_reaped':True,'stdout_stderr_complete':True,'outcome':'UNKNOWN','returncode':-15}
        observed=m.ResourceScanD2OwnedObserver(SimpleNamespace(owned_run=lambda *a,**k:original),state).owned_run(['synthetic'])
        self.assertIs(observed,original);return state

    def path(self,phase='CASE_B'):return self.public/f'resource-scan-d2-{phase}.json'

    def publish(self,state=None,value=None):
        return m.write_resource_scan_d2_companion(self.private,self.public,value or self.snapshot(),state or self.ready())

    def envelope(self):
        value=self.snapshot()
        return dict(kind='M0_RESOURCE_SCAN_D2_COMPANION',version=1,phase=value['phase'],
            predicate_site='AFTER_AUX_MISS',source_commit=m.SOURCE,controller_sha256=m.digest(Path(m.__file__)),scan=value)

    def manifest(self,records):
        m.public_write(self.public,'manifest.json',dict(files=records,source_commit=m.SOURCE,
            private_authorities_requests_keys_nonces_signatures_streams_not_uploaded=True))

    def install(self,name,value=None,raw=None):
        p=self.public/name;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_bytes(raw if raw is not None else (json.dumps(value)+'\n').encode())
        self.manifest([dict(name=name,bytes=p.stat().st_size,sha256=m.digest(p))]);return p

    def test_default_off_no_environment_or_IO_activation(self):
        with patch.object(m,'D2_COMPANION_EXPORT_ENABLED',False),patch.dict(m.os.environ,{'M0_D2_EXPORT':'1'}),\
                patch.object(m.os,'open',side_effect=AssertionError('no open')):
            self.assertEqual(m.write_resource_scan_d2_companion(self.private,self.public,self.snapshot(),None),'DISABLED')
            self.assertEqual(m.flush_resource_scan_d2_companions(self.private,self.public,None,[]),dict(status='DISABLED',phases={}))
        self.assertFalse(list(self.public.iterdir()));self.assertFalse(list(self.private.iterdir()))

    def test_plain_JSON_cleanup_boolean_cannot_authorize_export(self):
        fake={'pending_owners':0,'cleanup_unproven':False,'cleanup_proofs':[dict(leader_reaped=True,stdout_stderr_complete=True,source_contract=m.SOURCE)]}
        with patch.object(m,'digest',side_effect=AssertionError('no IO before barrier')):
            with self.assertRaisesRegex(m.GateError,'d2_cleanup_unproven'):
                m.write_resource_scan_d2_companion(self.private,self.public,self.snapshot(),fake)

    def test_observer_preserves_exact_return_and_calls_delegate_once(self):
        state=m.new_resource_scan_d2_export_state();calls=[];original={'leader_reaped':False,'stdout_stderr_complete':False}
        def run(*args,**kwargs):calls.append((args,kwargs));return original
        proxy=m.ResourceScanD2OwnedObserver(SimpleNamespace(owned_run=run),state)
        self.assertIs(proxy.owned_run(['synthetic'],wall_seconds=56),original)
        self.assertEqual(len(calls),1);self.assertFalse(m.resource_scan_d2_cleanup_barrier(state))
        state['cleanup_unproven']=False
        self.assertFalse(m.resource_scan_d2_cleanup_barrier(state))  # sticky observer proof remains unproven

    def test_observer_preserves_exact_primary_throw_no_retry(self):
        state=m.new_resource_scan_d2_export_state();calls=[];primary=RuntimeError('synthetic primary')
        def run(*a,**k):calls.append(1);raise primary
        proxy=m.ResourceScanD2OwnedObserver(SimpleNamespace(owned_run=run),state)
        with self.assertRaises(RuntimeError) as caught:proxy.owned_run(['synthetic'])
        self.assertIs(caught.exception,primary);self.assertEqual(calls,[1]);self.assertFalse(m.resource_scan_d2_cleanup_barrier(state))

    def test_tracking_failure_still_calls_original_once(self):
        calls=[];original={'leader_reaped':True,'stdout_stderr_complete':True}
        proxy=m.ResourceScanD2OwnedObserver(SimpleNamespace(owned_run=lambda *a,**k:(calls.append(1) or original)),None)
        self.assertIs(proxy.owned_run(['synthetic']),original);self.assertEqual(calls,[1])

    def test_tracking_cancel_before_delegate_never_launches_new_owner(self):
        calls=[]
        class InterruptedState(dict):
            def __getitem__(self,key):raise KeyboardInterrupt()
        proxy=m.ResourceScanD2OwnedObserver(SimpleNamespace(owned_run=lambda *a,**k:calls.append(1)),InterruptedState())
        with self.assertRaises(KeyboardInterrupt):proxy.owned_run(['synthetic'])
        self.assertEqual(calls,[])

    def test_post_return_cancel_is_not_swallowed(self):
        state=m.new_resource_scan_d2_export_state();calls=[];cancel=KeyboardInterrupt()
        class InterruptedProof(dict):
            def get(self,key):raise cancel
        proxy=m.ResourceScanD2OwnedObserver(SimpleNamespace(owned_run=lambda *a,**k:(calls.append(1) or InterruptedProof())),state)
        with self.assertRaises(KeyboardInterrupt) as caught:proxy.owned_run(['synthetic'])
        self.assertIs(caught.exception,cancel);self.assertEqual(calls,[1]);self.assertFalse(m.resource_scan_d2_cleanup_barrier(state))

    def test_final_counter_cancel_propagates_only_without_existing_primary(self):
        class InterruptedCounter(dict):
            def __init__(self):super().__init__(pending_owners=0,cleanup_proofs=[]);self.writes=0
            def __setitem__(self,key,value):
                if key=='pending_owners':
                    self.writes+=1
                    if self.writes==2:raise KeyboardInterrupt()
                return super().__setitem__(key,value)
        for primary in (None,RuntimeError('synthetic original')):
            with self.subTest(primary=primary is not None):
                calls=[]
                def run(*a,**k):
                    calls.append(1)
                    if primary is not None:raise primary
                    return {'leader_reaped':True,'stdout_stderr_complete':True}
                proxy=m.ResourceScanD2OwnedObserver(SimpleNamespace(owned_run=run),InterruptedCounter())
                if primary is None:
                    with self.assertRaises(KeyboardInterrupt):proxy.owned_run(['synthetic'])
                else:
                    with self.assertRaises(RuntimeError) as caught:proxy.owned_run(['synthetic'])
                    self.assertIs(caught.exception,primary)
                self.assertEqual(calls,[1])

    def test_health_queues_without_D2_IO_then_tail_after_cleanup(self):
        state=m.new_resource_scan_d2_export_state();events=[];real_fsync=m.os.fsync
        def fsync(fd):events.append(('fsync',state['pending_owners']));return real_fsync(fd)
        def check():
            m._scan_deadline_need(50_000_000,1,'QUALIFIED_AUX_ENOENT',
                [{'attempt':1,'scan_wall_ns':8_000_000,'scan_result':'ENOENT'}],('PRIVATE_ROOT','AUTH_ROUTER_SHM'))
        def owned(*a,**k):
            events.append(('owner','start'))
            with self.assertRaises(m.ResourceHealthFailure):
                m.resource_health_check_with_d2(self.private,self.public,'CASE_B',check,state=state)
            self.assertFalse(self.path().exists());events.append(('owner','cleanup'))
            return {'leader_reaped':True,'stdout_stderr_complete':True,'outcome':'UNKNOWN','returncode':-15}
        proxy=m.ResourceScanD2OwnedObserver(SimpleNamespace(owned_run=owned),state)
        with patch.object(m.os,'fsync',fsync):
            observed=proxy.owned_run(['synthetic']);records=[]
            status=m.flush_resource_scan_d2_companions(self.private,self.public,state,records)
        self.assertEqual(observed['outcome'],'UNKNOWN');self.assertEqual(status['status'],'COMPLETE')
        self.assertEqual([value for kind,value in events if kind=='fsync'],[1,0])  # old D1 I/O, then only post-cleanup D2 I/O
        self.assertEqual(len(records),1);self.assertEqual(json.loads(self.path().read_bytes())['scan']['elapsed_ns'],50_000_000)

    def test_capture_setup_failure_does_not_recall_old_health(self):
        calls=[];primary=m.GateError('synthetic_primary');state=self.ready()
        setup_error=OSError('synthetic setup')
        setup_error._m0_resource_origin=dict(kind='M0_RESOURCE_DIAGNOSTIC',version=1,phase='CASE_B',scope='PRIVATE_ROOT',
            operation='ENTRY_LSTAT',errno=2,catalogue_label='AUTH_ROUTER_SHM',unknown_relative_path_sha256=None,primary_code='resource_missing_non_aux')
        class BrokenContext:
            def set(self,value):raise setup_error
        def check():calls.append(1);raise primary
        with patch.object(m,'_RESOURCE_SCAN_D2_CAPTURE',BrokenContext()):
            with self.assertRaises(m.ResourceHealthFailure) as caught:
                m.resource_health_check_with_d2(self.private,self.public,'CASE_B',check,state=state)
        self.assertIs(caught.exception.primary_error,primary);self.assertEqual(calls,[1])
        self.assertEqual(state['status'],{'CASE_B':'UNAVAILABLE'})
        capsule=json.loads((self.public/'resource-diagnostic-CASE_B.json').read_bytes())
        self.assertEqual((capsule['scope'],capsule['operation']),('UNKNOWN','HEALTH_VALIDATION'))

    def test_successful_companion_closed_capped_source_bound_and_verifiable(self):
        self.assertEqual(self.publish(),'RECORDED');p=self.path();raw=p.read_bytes();v=json.loads(raw)
        self.assertLessEqual(len(raw),4096);self.assertEqual(p.stat().st_mode&0o777,0o600)
        self.assertTrue(m.validate_resource_scan_d2_companion(v,m.digest(Path(m.__file__))))
        self.assertEqual(v['predicate_site'],'AFTER_AUX_MISS');self.assertNotIn('path',raw.decode())
        records=[];self.assertEqual(m.collect_resource_scan_d2_companions(self.public,records),'COMPLETE')
        self.manifest(records);self.assertTrue(m.verify_public(self.public))

    def test_retry_return_predicate_is_scan_only_not_case_success(self):
        self.assertEqual(self.publish(value=self.snapshot(post=True)),'RECORDED')
        v=json.loads(self.path().read_bytes());self.assertEqual(v['predicate_site'],'AFTER_RETRY_SUCCESS')
        self.assertEqual(v['scan']['primary_code'],'resource_aux_retry_deadline')

    def test_first_O_EXCL_record_never_rewritten(self):
        self.publish();original=self.path().read_bytes();later=self.snapshot();later['elapsed_ns']=60_000_000
        self.assertEqual(self.publish(value=later),'ALREADY_RECORDED');self.assertEqual(self.path().read_bytes(),original)

    def test_fsync_failure_stays_private_and_primary_case_unchanged(self):
        state=self.ready();state['capsules']['CASE_B']=self.snapshot();case={'status':'UNKNOWN','error_code':'whole_case_unknown'}
        with patch.object(m.os,'fsync',side_effect=OSError('SYNTHETIC_PRIVATE_KEY_NONCE')):
            status=m.flush_resource_scan_d2_companions(self.private,self.public,state,[])
        self.assertEqual(status['status'],'UNAVAILABLE');self.assertEqual(case,{'status':'UNKNOWN','error_code':'whole_case_unknown'})
        self.assertFalse(self.path().exists());self.assertTrue((self.private/'resource-scan-d2-incomplete-CASE_B.json').exists())

    def test_close_failure_cannot_publish(self):
        original=m.os.fdopen
        class CloseFailure:
            def __init__(self,*a,**k):self.stream=original(*a,**k)
            def __enter__(self):return self.stream.__enter__()
            def __exit__(self,*a):self.stream.__exit__(*a);raise OSError('synthetic close')
        with patch.object(m.os,'fdopen',CloseFailure):
            with self.assertRaises(OSError):self.publish()
        self.assertFalse(self.path().exists())

    def test_link_failure_cannot_publish_or_fallback_copy(self):
        with patch.object(m.os,'link',side_effect=OSError('synthetic EXDEV')):
            with self.assertRaises(OSError):self.publish()
        self.assertFalse(self.path().exists());self.assertTrue((self.private/'resource-scan-d2-incomplete-CASE_B.json').exists())

    def test_private_alias_cleanup_failure_keeps_valid_public_and_double_charge(self):
        with patch.object(Path,'unlink',side_effect=PermissionError('synthetic alias cleanup')):
            self.assertEqual(self.publish(),'RECORDED')
        size=self.path().stat().st_size;usage=m.resource_usage(self.private,self.public)
        self.assertEqual(usage,dict(normal=0,escrow=0,cleanup=2*size,total=2*size))

    def test_single_alias_headroom_cannot_fund_publication(self):
        raw=(json.dumps(self.envelope(),sort_keys=True,separators=(',',':'))+'\n').encode()
        with patch.object(m,'_diagnostic_cleanup_bytes',return_value=m.CLEANUP_RESERVE-len(raw)):
            with self.assertRaisesRegex(m.GateError,'diagnostic_cleanup_cap'):self.publish()
        self.assertFalse(list(self.private.iterdir()));self.assertFalse(list(self.public.iterdir()))

    def test_schema_phase_predicate_version_extra_and_source_reject(self):
        value=self.envelope()
        for edit in [{'version':True},{'predicate_site':'AFTER_RETRY_SUCCESS'},{'phase':'CASE_P'},
                     {'controller_sha256':'a'*64},{'source_commit':'a'*40},{'key':'SYNTHETIC_PRIVATE'}]:
            with self.subTest(edit=edit):
                with self.assertRaises(m.GateError):m.validate_resource_scan_d2_companion(dict(value,**edit),value['controller_sha256'])

    def test_nested_fixed_name_cannot_borrow_generic_JSON_route(self):
        self.install('case-B-safe/resource-scan-d2-CASE_B.json',self.envelope())
        with self.assertRaises(m.GateError):m.verify_public(self.public)

    def test_renamed_kind_cannot_borrow_generic_JSON_route(self):
        self.install('otherwise-safe.json',self.envelope())
        with self.assertRaisesRegex(m.GateError,'scan_d2_companion_public_name'):m.verify_public(self.public)

    def test_renamed_duplicate_kind_cannot_hide_behind_last_value(self):
        raw=json.dumps(self.envelope(),separators=(',',':')).replace('"kind":"M0_RESOURCE_SCAN_D2_COMPANION"',
            '"kind":"M0_RESOURCE_SCAN_D2_COMPANION","kind":"other"',1).encode()
        self.install('otherwise-safe.json',raw=raw)
        with self.assertRaisesRegex(m.GateError,'duplicate_json_key'):m.verify_public(self.public)

    def test_generic_NaN_cannot_hide_from_strict_JSON_detector(self):
        self.install('otherwise-safe.json',raw=b'{"kind":"other","value":NaN}')
        with self.assertRaisesRegex(m.GateError,'json_nonfinite'):m.verify_public(self.public)

    def test_default_off_verifier_rejects_even_wellformed_companion(self):
        self.install('resource-scan-d2-CASE_B.json',self.envelope())
        with patch.object(m,'D2_COMPANION_EXPORT_ENABLED',False):
            with self.assertRaises(m.GateError):m.verify_public(self.public)

    def test_duplicate_JSON_keys_reject(self):
        raw=json.dumps(self.envelope(),separators=(',',':')).replace('"version":1','"version":1,"version":1',1).encode()
        self.install('resource-scan-d2-CASE_B.json',raw=raw)
        with self.assertRaises(m.GateError):m.verify_public(self.public)

    def test_size_cap_is_checked_before_staging_open(self):
        with patch.object(m.json,'dumps',return_value='x'*4097),patch.object(m.os,'open',side_effect=AssertionError('no staging')):
            with self.assertRaisesRegex(m.GateError,'scan_d2_companion_cap'):self.publish()

    def test_unproven_cleanup_and_arbitrary_phase_do_not_publish_or_leak(self):
        state=m.new_resource_scan_d2_export_state();state['capsules']['CASE_B']=self.snapshot();records=[]
        status=m.flush_resource_scan_d2_companions(self.private,self.public,state,records)
        self.assertEqual(status,dict(status='UNAVAILABLE',phases={'CASE_B':'CLEANUP_UNPROVEN'}));self.assertFalse(records)
        state['capsules']={'/SYNTHETIC_PRIVATE_KEY_NONCE':self.snapshot()}
        status=m.flush_resource_scan_d2_companions(self.private,self.public,state,records)
        self.assertEqual(status,dict(status='UNAVAILABLE',phases={}))

    def test_legacy_D1_meter_does_not_add_pre_stop_D2_lstat(self):
        paths=[];original=Path.lstat
        def lstat(path,*a,**k):paths.append(path.name);return original(path,*a,**k)
        with patch.object(Path,'lstat',lstat):self.assertEqual(m._diagnostic_cleanup_bytes(self.private,self.public),0)
        self.assertFalse(any(n.startswith('resource-scan-d2-') for n in paths))

    def test_main_PREP_ignores_export_environment_and_starts_no_observer(self):
        with patch.object(m,'D2_COMPANION_EXPORT_ENABLED',False),patch.dict(m.os.environ,{'M0_D2_EXPORT':'1'}),\
                patch.object(m,'new_resource_scan_d2_export_state',side_effect=AssertionError('no observer')),\
                patch.object(m,'write_resource_scan_d2_companion',side_effect=AssertionError('no export')),redirect_stdout(io.StringIO()) as output:
            self.assertEqual(m.main([]),0)
        self.assertIs(json.loads(output.getvalue())['execution_authorized'],False)

if __name__=='__main__':unittest.main()
