"""Real frozen wrapper nesting, with synthetic data and zero live processes."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest

HERE=Path(__file__).resolve().parent
S=importlib.util.spec_from_file_location('controller_receipt_test',HERE/'smoke_controller_v3.py')
C=importlib.util.module_from_spec(S);S.loader.exec_module(C)
FLAGS=dict(continuous_6h_stability_passed=False,continuous_24h_stability_passed=False,
           capacity_10000_per_s_passed=False,production_approved=False)


def running(done=2,worker=0):
    return dict(status='running',rounds={'DONE':done},fault_signals={'worker':worker,'parent':0},unresolved_faults=0)


def stable():
    return dict(logical_point='stable_boundary',sample_wall_ns=200_100_000_000,completed_rounds=2,
        active_rounds=[],unresolved_steps=0,unresolved_faults=0,planned_faults=[],alerts=[],
        finance={'golden':{'passed':True,'compared':True,'errors':[]}},final_evidence_eligible=False,
        worker={'process':{'pid':400001,'birth':'55','alive':True},'generation':1},**FLAGS)


def captured(payload,code=0,timeout=False):
    # prepare prints its Pipes receipt. The managed-smoke stdout is captured(...).
    return {'exit_code':code,'stdout_complete':True,'structured_stdout':{
        'exit_code':code,'timed_out':timeout,'response':payload}}


def cold(code=0):
    # short-cold prints a direct payload, not captured() with invented timeout.
    return {'exit_code':code,'stdout_complete':True,'structured_stdout':{
        'short_smoke_cold_audit_passed':True,'watermark_before':{'seq':1},'watermark_after':{'seq':1},
        'long_run_receipt_issued':False,**FLAGS}}


def strict(timeout=False):
    return captured({'error_type':'ValueError','error_digest':C.digest(b'producer_audit_requires_other_final_checks_passed'),
        'final_evidence_eligible':False,**FLAGS},1,timeout)


def unknown_fault(timeout=False):
    sample={'logical_point':'unknown','sample_wall_ns':200_100_000_000,'alerts':['observation_failed_closed'],
        'error_type':'OperationalError','error_digest':'a'*64,'final_evidence_eligible':False,**FLAGS}
    witness={'pidfd_death_observed':True,'death_wall_ns':200_000_000_000,'old_generation':1,'previous_worker_faults':0}
    return captured(sample,1,timeout),witness


class ReceiptContractTests(unittest.TestCase):
    def test_strict_timeout_cannot_be_expected_refusal(self):
        with self.assertRaises(ValueError):C.validate_result('strict-negative',strict(True),{}, {},False)
    def test_normal_prepare_failure_cannot_hide_healthy_payload(self):
        data=captured(stable());data['exit_code']=1
        with self.assertRaises(ValueError):C.validate_result('normal-live',data,running(),running(),True)
    def test_cold_prepare_failure_cannot_hide_direct_cold_pass(self):
        with self.assertRaises(ValueError):C.validate_result('cold',cold(1),{}, {},False)
    def test_fault_timeout_cannot_be_typed_unknown_pass(self):
        data,witness=unknown_fault(True)
        with self.assertRaises(ValueError):C.validate_result('fault-live',data,running(4),running(5,1),True,witness)
    def test_completed_progress_cannot_hide_failed_producer_capture(self):
        live=object.__new__(C.Live)
        live.finish=lambda *_:captured({'status':'completed'},1)
        live.progress=lambda:{'status':'completed','rounds':{'DONE':15},'fault_signals':{'worker':3,'parent':1},'elapsed_seconds':60.1}
        with self.assertRaises(ValueError):live.finish_producer('pure-fake')
    def test_actual_first_producer_original_projected_receipt_shape(self):
        import json
        root=HERE.parents[2]
        first=root/'evidence/runs/managed-909acec-smoke-01/uta-909-smoke-produce-receiver-1794937955003028316-result.json'
        data=json.loads(first.read_bytes())['result']['structured_stdout']
        original=C.receipt_payload('produce',data)
        self.assertEqual(original['status'],'completed');self.assertEqual(original['rounds'],{'DONE':15})
        live=object.__new__(C.Live);live.finish=lambda *_:data
        live.progress=lambda:original
        live.finish_producer('pure-fake')
    def test_positive_real_direct_and_captured_shapes(self):
        self.assertEqual(C.receipt_payload('normal-live',captured(stable()))['logical_point'],'stable_boundary')
        self.assertTrue(C.validate_result('cold',cold(),{}, {},False)['short_smoke_cold_audit_passed'])
        self.assertTrue(C.validate_result('strict-negative',strict(),{}, {},False)['strict_long_refused'])
        data,witness=unknown_fault()
        self.assertTrue(C.validate_result('fault-live',data,running(4),running(5,1),True,witness)['inflight_or_unknown_observed'])
    def test_each_captured_exit_and_timeout_is_required_and_exact(self):
        for stage,data in (('normal-live',captured(stable())),('strict-negative',strict())):
            vectors=[]
            for path in (('exit_code',),('structured_stdout','exit_code')):
                for value in (-15,True,None):
                    bad=deepcopy(data);target=bad
                    for key in path[:-1]:target=target[key]
                    target[path[-1]]=value;vectors.append(bad)
            for value in (True,None,0,'false'):
                bad=deepcopy(data);bad['structured_stdout']['timed_out']=value;vectors.append(bad)
            missing=deepcopy(data);del missing['structured_stdout']['timed_out'];vectors.append(missing)
            for index,bad in enumerate(vectors):
                with self.subTest(stage=stage,vector=index),self.assertRaises(ValueError):C.receipt_payload(stage,bad)
    def test_cold_direct_payload_must_not_be_falsely_treated_as_capture(self):
        good=cold();self.assertNotIn('timed_out',good['structured_stdout'])
        self.assertTrue(C.receipt_payload('cold',good)['short_smoke_cold_audit_passed'])
        for key in ('exit_code','timed_out'):
            bad=cold();bad['structured_stdout'][key]=1
            with self.subTest(field=key),self.assertRaises(ValueError):C.receipt_payload('cold',bad)
    def test_fault_expected_one_is_only_typed_unknown_never_zero_or_timeout(self):
        good,witness=unknown_fault()
        for change in ('zero','untyped','timeout'):
            bad=deepcopy(good)
            if change=='zero':bad['exit_code']=bad['structured_stdout']['exit_code']=0
            if change=='untyped':del bad['structured_stdout']['response']['error_type']
            if change=='timeout':bad['structured_stdout']['timed_out']=True
            with self.subTest(change=change),self.assertRaises(ValueError):C.validate_result('fault-live',bad,running(4),running(5,1),True,witness)


if __name__=='__main__':unittest.main(verbosity=2)
