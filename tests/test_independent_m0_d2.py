"""Unexecuted D2 memory-only contracts. No SQL, child, mount or file fixture."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('m0_d2_contract',ROOT/'tools/independent_m0_controller.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class ScanD2Contract(unittest.TestCase):
    def missing(self,name='router.sqlite3-shm'):
        return FileNotFoundError(2,'SYNTHETIC_PRIVATE_KEY_NONCE',str(Path('/synthetic-private/B/workload/authority')/name))

    def anchors(self):return (('private_root',Path('/synthetic-private')),)

    def retry(self,error):
        calls=[]
        def scan(_observe):
            calls.append(True)
            if len(calls)==1:raise error
            return 7
        return scan

    def enoent_failure(self,clock=(0,1_000_000,9_000_000,50_000_000),name='router.sqlite3-shm'):
        error=self.missing(name)
        with m.resource_scan_d2_capture('CASE_B') as captured,patch.object(m,'_known_missing_sqlite_aux',return_value=True),\
                patch.object(m.time,'monotonic_ns',side_effect=clock):
            with self.assertRaisesRegex(m.GateError,'resource_aux_retry_deadline') as caught:
                m._fresh_resource_scan(lambda _observe:(_ for _ in ()).throw(error),self.anchors())
        return captured,caught.exception

    def test_disabled_uses_original_two_clock_reads_and_primary(self):
        with patch.object(m,'_known_missing_sqlite_aux',return_value=True),patch.object(m.time,'monotonic_ns',side_effect=[0,50_000_000]) as clock:
            with self.assertRaisesRegex(m.GateError,'resource_aux_retry_deadline') as caught:
                m._fresh_resource_scan(lambda _observe:(_ for _ in ()).throw(self.missing()),self.anchors())
        self.assertEqual(clock.call_count,2)
        self.assertFalse(hasattr(caught.exception,'_m0_resource_scan_d2'))
        self.assertIsNone(m._RESOURCE_SCAN_D2_CAPTURE.get())

    def test_qualified_ENOENT_equality_rejects_and_records_same_clock(self):
        captured,error=self.enoent_failure()
        self.assertEqual(captured['status'],'RECORDED');v=captured['records'][0]
        self.assertTrue(m.validate_resource_scan_d2(v))
        self.assertEqual((v['gate'],v['legacy_gate'],v['comparison']),('QUALIFIED_AUX_ENOENT','C933_L382','LT'))
        self.assertEqual((v['attempt'],v['elapsed_ns'],v['deadline_ns']),(1,50_000_000,50_000_000))
        self.assertEqual(v['attempts'],[{'attempt':1,'scan_wall_ns':8_000_000,'scan_result':'ENOENT'}])
        self.assertEqual((v['scope'],v['catalogue_label'],v['context_origin']),('PRIVATE_ROOT','AUTH_ROUTER_SHM','CURRENT_QUALIFIED_AUX'))
        self.assertIs(error._m0_resource_scan_d2,v)

    def test_post_retry_return_records_two_walls_and_separate_total(self):
        clock=[0,1_000_000,3_000_000,4_000_000,5_000_000,12_000_000,50_000_001]
        with m.resource_scan_d2_capture('CASE_B') as captured,patch.object(m,'_known_missing_sqlite_aux',return_value=True),\
                patch.object(m.time,'monotonic_ns',side_effect=clock):
            with self.assertRaisesRegex(m.GateError,'resource_aux_retry_deadline'):
                m._fresh_resource_scan(self.retry(self.missing()),self.anchors())
        v=captured['records'][0]
        self.assertEqual((v['gate'],v['legacy_gate'],v['comparison']),('POST_RETRY_SCAN_RETURN','C933_L377','LE'))
        self.assertEqual(v['attempt'],2);self.assertEqual(v['elapsed_ns'],50_000_001)
        self.assertEqual(v['attempts'],[{'attempt':1,'scan_wall_ns':2_000_000,'scan_result':'ENOENT'},
                                     {'attempt':2,'scan_wall_ns':7_000_000,'scan_result':'RETURNED'}])
        self.assertEqual(v['context_origin'],'LAST_QUALIFIED_AUX')

    def test_post_retry_equality_still_passes(self):
        clock=[0,1,2,3,4,5,50_000_000]
        with m.resource_scan_d2_capture('CASE_B') as captured,patch.object(m,'_known_missing_sqlite_aux',return_value=True),\
                patch.object(m.time,'monotonic_ns',side_effect=clock):
            self.assertEqual(m._fresh_resource_scan(self.retry(self.missing()),self.anchors()),7)
        self.assertEqual(captured,{'status':'NOT_OBSERVED','records':[]})

    def test_diagnostic_failure_does_not_replace_primary_or_D1(self):
        with patch.object(m,'validate_resource_scan_d2',side_effect=ValueError('SYNTHETIC_PRIVATE_KEY_NONCE')):
            captured,error=self.enoent_failure()
        self.assertEqual(str(error),'resource_aux_retry_deadline')
        self.assertEqual(captured,{'status':'UNAVAILABLE','records':[]})
        self.assertFalse(hasattr(error,'_m0_resource_scan_d2'))

    def test_no_arbitrary_filename_path_hash_key_or_nonce_is_serialized(self):
        captured,_error=self.enoent_failure(name='shard-9999.sqlite3-shm')
        v=captured['records'][0];self.assertEqual(v['catalogue_label'],'UNKNOWN')
        raw=json.dumps(v)
        for forbidden in ['/synthetic-private','9999','SYNTHETIC_PRIVATE_KEY_NONCE','filename','path_sha256']:
            self.assertNotIn(forbidden,raw)

    def test_unknown_or_extra_schema_fields_reject(self):
        captured,_error=self.enoent_failure();v=captured['records'][0]
        for key,value in [('path','synthetic'),('nonce',1),('key',2),('opaque_token',3)]:
            with self.subTest(key=key):
                with self.assertRaises(m.GateError):m.validate_resource_scan_d2(dict(v,**{key:value}))

    def test_bool_actual_times_and_attempts_reject(self):
        captured,_error=self.enoent_failure();v=captured['records'][0]
        for key in ['attempt','elapsed_ns','deadline_ns']:
            with self.subTest(key=key):
                with self.assertRaises(m.GateError):m.validate_resource_scan_d2(dict(v,**{key:True}))

    def test_wrong_gate_operator_and_nonfailure_reject(self):
        captured,_error=self.enoent_failure();v=captured['records'][0]
        for changes in [{'comparison':'LE'},{'legacy_gate':'C933_L377'},{'elapsed_ns':49_999_999},{'attempt':3}]:
            with self.subTest(changes=changes):
                with self.assertRaises(m.GateError):m.validate_resource_scan_d2(dict(v,**changes))

    def test_first_record_preserved_across_later_deadline_in_same_capture(self):
        with m.resource_scan_d2_capture('CASE_B') as captured,patch.object(m,'_known_missing_sqlite_aux',return_value=True):
            for end in [50_000_000,60_000_000]:
                with patch.object(m.time,'monotonic_ns',side_effect=[0,1,2,end]):
                    with self.assertRaises(m.GateError):
                        m._fresh_resource_scan(lambda _observe:(_ for _ in ()).throw(self.missing()),self.anchors())
        self.assertEqual(len(captured['records']),1)
        self.assertEqual(captured['records'][0]['elapsed_ns'],50_000_000)

    def test_no_retry_granted_for_unqualified_missing_and_original_token_reset(self):
        with m.resource_scan_d2_capture('CASE_B') as captured,patch.object(m,'_known_missing_sqlite_aux',return_value=False):
            with self.assertRaisesRegex(m.GateError,'resource_missing_non_aux'):
                m._fresh_resource_scan(lambda _observe:(_ for _ in ()).throw(self.missing()),self.anchors())
        self.assertEqual(captured['status'],'NOT_OBSERVED')
        self.assertIsNone(m._RESOURCE_SCAN_TOKEN.get());self.assertIsNone(m._RESOURCE_SCAN_D2_CAPTURE.get())

    def test_nested_capture_and_BaseException_restore_context(self):
        with m.resource_scan_d2_capture('CASE_B'):
            outer=m._RESOURCE_SCAN_D2_CAPTURE.get()
            with self.assertRaises(KeyboardInterrupt):
                with m.resource_scan_d2_capture('CASE_P'):
                    raise KeyboardInterrupt()
            self.assertIs(m._RESOURCE_SCAN_D2_CAPTURE.get(),outer)
        self.assertIsNone(m._RESOURCE_SCAN_D2_CAPTURE.get())

    def test_D2_cannot_be_passed_as_legacy_D1(self):
        captured,_error=self.enoent_failure()
        with self.assertRaisesRegex(m.GateError,'diagnostic_fields'):m.validate_resource_diagnostic(captured['records'][0])

    def test_missing_collector_key_cannot_replace_primary(self):
        with m.resource_scan_d2_capture('CASE_B') as captured:
            captured.pop('records')
            with self.assertRaisesRegex(m.GateError,'resource_aux_retry_deadline'):
                m._scan_deadline_need(50_000_000,1,'QUALIFIED_AUX_ENOENT',[],None)
        self.assertEqual(captured['status'],'UNAVAILABLE')

    def test_append_failure_cannot_replace_primary(self):
        class BadList(list):
            def append(self,value):raise OSError('SYNTHETIC_PRIVATE_KEY_NONCE')
        with m.resource_scan_d2_capture('CASE_B') as captured:
            captured['records']=BadList()
            with self.assertRaisesRegex(m.GateError,'resource_aux_retry_deadline'):
                m._scan_deadline_need(50_000_000,1,'QUALIFIED_AUX_ENOENT',
                    [{'attempt':1,'scan_wall_ns':1,'scan_result':'ENOENT'}],None)
        self.assertEqual(captured['status'],'UNAVAILABLE');self.assertEqual(captured['records'],[])

    def test_invalid_collector_and_fallback_failure_cannot_replace_primary(self):
        token=m._RESOURCE_SCAN_D2_CAPTURE.set({'value':None})
        try:
            with self.assertRaisesRegex(m.GateError,'resource_aux_retry_deadline'):
                m._scan_deadline_need(50_000_000,1,'QUALIFIED_AUX_ENOENT',[],None)
        finally:m._RESOURCE_SCAN_D2_CAPTURE.reset(token)

    def test_cancel_at_optin_clock_start_never_calls_scan(self):
        calls=[]
        with m.resource_scan_d2_capture('CASE_B'),patch.object(m.time,'monotonic_ns',side_effect=[0,KeyboardInterrupt()]):
            with self.assertRaises(KeyboardInterrupt):m._fresh_resource_scan(lambda _:calls.append(True),())
        self.assertEqual(calls,[]);self.assertIsNone(m._RESOURCE_SCAN_TOKEN.get())

    def test_cancel_at_optin_clock_end_after_success_propagates(self):
        with m.resource_scan_d2_capture('CASE_B'),patch.object(m.time,'monotonic_ns',side_effect=[0,1,KeyboardInterrupt()]):
            with self.assertRaises(KeyboardInterrupt):m._fresh_resource_scan(lambda _:7,())
        self.assertIsNone(m._RESOURCE_SCAN_TOKEN.get())

    def test_optin_clock_end_failure_preserves_existing_scan_primary(self):
        primary=RuntimeError('synthetic scan primary')
        with m.resource_scan_d2_capture('CASE_B'),patch.object(m.time,'monotonic_ns',side_effect=[0,1,KeyboardInterrupt()]):
            with self.assertRaises(RuntimeError) as caught:
                m._fresh_resource_scan(lambda _:(_ for _ in ()).throw(primary),())
        self.assertIs(caught.exception,primary);self.assertIsNone(m._RESOURCE_SCAN_TOKEN.get())

class KernelSpaceDesignContract(unittest.TestCase):
    def test_design_is_disabled_and_does_not_claim_capability(self):
        value=m.kernel_space_design_spec();self.assertTrue(m.validate_kernel_space_design_spec(value))
        self.assertEqual(value['implementation'],'NOT_IMPLEMENTED')
        for key in ['execution_enabled','legacy_format2_compatible','prior_625_baseline_directly_comparable',
                    'fallback_to_ordinary_directory','lazy_or_forced_unmount_allowed',
                    'logical_scan_UNKNOWN_may_be_silently_upgraded','next_run_permitted','production_approved']:
            self.assertIs(value[key],False)

    def test_exact_original_byte_caps_and_backing_free_are_kept(self):
        value=m.kernel_space_design_spec()
        self.assertEqual(value['logical_limits'],dict(case_B=33554432,case_P=33554432,normal=67108864,
            escrow=100663296,cleanup=33554432,total=201326592))
        self.assertEqual(sum(value['volume_address_space_limits'].values()),201326592)
        self.assertEqual(value['backing_host_minimum_free_bytes'],2348810240)

    def test_valid_design_still_cannot_acquire_backend(self):
        with self.assertRaisesRegex(m.GateError,'kernel_space_backend_not_implemented'):
            m.request_kernel_space_backend(m.kernel_space_design_spec())

    def test_budget_boolean_extra_or_activation_change_rejects(self):
        for edit in [{'execution_enabled':True},{'version':True},{'root_attested':True}]:
            with self.subTest(edit=edit):
                value=m.kernel_space_design_spec();value.update(edit)
                with self.assertRaises(m.GateError):m.validate_kernel_space_design_spec(value)
        value=m.kernel_space_design_spec();value['volume_address_space_limits']['cleanup']+=1
        with self.assertRaises(m.GateError):m.validate_kernel_space_design_spec(value)

    def test_design_returns_independent_mutable_projection(self):
        value=m.kernel_space_design_spec();value['logical_limits']['normal']=0
        self.assertEqual(m.kernel_space_design_spec()['logical_limits']['normal'],67108864)

if __name__=='__main__':unittest.main()
