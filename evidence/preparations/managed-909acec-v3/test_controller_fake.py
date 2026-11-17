"""Owned memory/raw-file fixtures only. No real Popen, SQL, job or cohost read."""
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import signal
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location('controller_under_test',HERE/'smoke_controller_v3.py')
C=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(C)
FLAGS=dict(continuous_6h_stability_passed=False,continuous_24h_stability_passed=False,
           capacity_10000_per_s_passed=False,production_approved=False)


def progress(done=1,faults=0,status='running'):
    return dict(status=status,rounds={'DONE':done},fault_signals={'worker':faults,'parent':1 if status=='completed' else 0},
                unresolved_faults=0,elapsed_seconds=60.1 if status=='completed' else 5.)


def sample(done=1):
    return dict(logical_point='stable_boundary',sample_wall_ns=200_100_000_000,completed_rounds=done,
        active_rounds=[],unresolved_steps=0,unresolved_faults=0,planned_faults=[],alerts=[],
        finance={'golden':{'passed':True,'compared':True,'errors':[]}},final_evidence_eligible=False,
        worker={'process':{'pid':400001,'birth':'55','alive':True},'generation':1},**FLAGS)


def receipt(payload,code=0):
    return {'exit_code':code,'stdout_complete':True,'structured_stdout':{'exit_code':code,'timed_out':False,'response':payload}}


class FakeIO:
    def __init__(self,fail=None,secondary=False,overrun=False):
        self.events=[];self.fail=fail;self.secondary=secondary;self.overrun=overrun
        self.fault_witness=None;self.row=progress();self.producer=None;self.clock=0;self.first=None
    def wait_precondition(self,stage,producer,previous_faults):
        self.events.append(('wait',stage))
        if stage=='final':producer.ended=True;self.row=progress(15,3,'completed');self.clock=61
        elif stage=='fault-live':
            self.row=progress(4,0);self.fault_witness={'pidfd_death_observed':True,'death_wall_ns':200_000_000_000,'old_generation':1,'previous_worker_faults':0}
        return deepcopy(self.row)
    def admit(self,item):
        self.events.append(('admit',item['stage']))
        if item['stage']==self.fail:raise ValueError('synthetic_stale_admission')
        return 'snapshot','specific_delegated_GO'
    def spawn(self,item,admission):
        self.events.append(('spawn',item['stage']))
        if self.first is None:self.first=self.clock
        child=NS(stage=item['stage'],ended=False)
        if item['stage']=='produce':self.producer=child
        return child
    def alive(self,producer):return producer is not None and not producer.ended
    def progress(self):return deepcopy(self.row)
    def finish(self,child,item):
        stage=item['stage'];self.events.append(('finish',stage));self.clock+=1
        if stage=='fault-live':
            self.row=progress(5,1);s=sample(4);s.update(logical_point='inflight_or_unknown',active_rounds=[5],
                unresolved_faults=1,planned_faults=[{'kind':'worker','old_generation':1,'round':5,'state':'PLANNED'}],
                finance={'golden':{'passed':None,'compared':False}},alerts=['worker_lease_inactive_or_unknown'])
            return receipt(s)
        if stage=='final':
            s=sample(15);s['active_elapsed_seconds']=60.1;s['final_reconciliation']={
                'errors':['actual_6h_and_5400_rounds_required','producer_actual_active_duration_incomplete','producer_cold_audit_same_watermark_missing'],
                'independent_reopen_reconciliation_passed':True,'independent_reopen_same_watermark':True}
            return receipt(s)
        if stage=='cold':return {'exit_code':0,'stdout_complete':True,'structured_stdout':{'short_smoke_cold_audit_passed':True,'watermark_before':{'seq':1},'watermark_after':{'seq':1},'long_run_receipt_issued':False}}
        if stage=='strict-negative':return receipt({'error_type':'ValueError','error_digest':C.digest(b'producer_audit_requires_other_final_checks_passed'),'final_evidence_eligible':False},1)
        self.row=progress(2,0);return receipt(sample(2))
    def record_stage(self,item,value):self.events.append(('record',item['stage']))
    def finish_producer(self,p):
        self.events.append(('finish-producer','produce'))
        if self.overrun:self.clock=151
    def final_check(self):C.require(self.first is None or self.clock-self.first<150,'outer150_expired')
    def drain_owned(self,p):
        self.events.append(('drain','owned'))
        if self.secondary:raise OSError('synthetic_secondary_drain')
    def close(self):
        self.events.append(('close','owned'))
        if self.secondary:raise OSError('synthetic_secondary_close')


class OrderingTests(unittest.TestCase):
    def envelope(self):return {'stages':[{'stage':x} for x in C.ORDER]}
    def test_seven_stage_async_producer_live_observations_before_natural_final(self):
        effects=FakeIO();r=C.execute(self.envelope(),effects)
        self.assertTrue(r['full_smoke_passed'])
        self.assertLess(effects.events.index(('finish','fault-live')),effects.events.index(('finish-producer','produce')))
        self.assertEqual([v for k,v in effects.events if k=='spawn'],list(C.ORDER))
    def test_stale_admission_stops_later_stages_and_drains_without_second_producer(self):
        effects=FakeIO(fail='fault-live');r=C.execute(self.envelope(),effects)
        self.assertFalse(r['full_smoke_passed']);self.assertEqual(r['stage_states']['cold'],'NOT_RUN')
        self.assertEqual([v for k,v in effects.events if k=='spawn'].count('produce'),1)
        self.assertIn(('drain','owned'),effects.events)
    def test_cleanup_exceptions_cannot_replace_primary(self):
        effects=FakeIO(fail='normal-live',secondary=True);r=C.execute(self.envelope(),effects)
        self.assertEqual(r['stage_states']['error_type'],'ValueError')
        self.assertEqual(r['stage_states']['drain_secondary_error'],'OSError')
        self.assertEqual(r['stage_states']['close_secondary_error'],'OSError')
    def test_last_blocking_result_crossing_deadline_never_passes(self):
        r=C.execute(self.envelope(),FakeIO(overrun=True));self.assertFalse(r['full_smoke_passed'])
        self.assertEqual(r['stage_states']['error_type'],'ValueError')


class ResultTests(unittest.TestCase):
    def test_recovered_stable_with_cumulative_fault_is_not_fault_live(self):
        witness={'pidfd_death_observed':True,'death_wall_ns':200_000_000_000,'old_generation':1,'previous_worker_faults':0}
        with self.assertRaisesRegex(ValueError,'recovered_stable'):
            C.validate_result('fault-live',receipt(sample(6)),progress(6,1),progress(6,1),True,witness)
    def test_real_fatal_alerts_without_failed_substring_reject(self):
        for alert in ('internal_execution_retry_cause_unknown','terminal_rejection_or_quarantine_observed','producer_reported_error'):
            s=sample();s['alerts']=[alert]
            with self.subTest(alert=alert),self.assertRaises(ValueError):C.validate_result('startup',receipt(s),progress(),progress(),True)
    def test_live_stage_cannot_accept_after_producer_natural_end(self):
        with self.assertRaisesRegex(ValueError,'outside_actual_active'):
            C.validate_result('startup',receipt(sample()),progress(),progress(15,3,'completed'),False)
    def test_strict_negative_requires_original_nested_exact_refusal(self):
        value=receipt({'error_type':'ValueError','error_digest':C.digest(b'producer_audit_requires_other_final_checks_passed'),'final_evidence_eligible':False},1)
        self.assertTrue(C.validate_result('strict-negative',value,{}, {},False)['strict_long_refused'])
        value['structured_stdout']['response']['error_digest']='0'*64
        with self.assertRaisesRegex(ValueError,'not_expected_refusal'):C.validate_result('strict-negative',value,{}, {},False)
    def test_fault_typed_unknown_requires_current_death_and_actual_increment(self):
        s={'logical_point':'unknown','sample_wall_ns':200_100_000_000,'alerts':['observation_failed_closed'],
            'error_type':'OperationalError','error_digest':'a'*64,'final_evidence_eligible':False,**FLAGS}
        witness={'pidfd_death_observed':True,'death_wall_ns':200_000_000_000,'old_generation':1,'previous_worker_faults':0}
        self.assertTrue(C.validate_result('fault-live',receipt(s,1),progress(4,0),progress(5,1),True,witness)['inflight_or_unknown_observed'])
        with self.assertRaises(ValueError):C.validate_result('fault-live',receipt(s,1),progress(4,0),progress(4,0),True,witness)


class ConstructionAndPipeTests(unittest.TestCase):
    def test_ctor_pidfd_failure_registers_and_reaps_own_unreaped_child(self):
        process=Mock(pid=400001,returncode=None,stdout=io.BytesIO(),stderr=io.BytesIO())
        process.wait.return_value=0;registry=[]
        with patch.object(C.subprocess,'Popen',return_value=process),patch.object(C.os,'pidfd_open',side_effect=OSError('synthetic_pidfd')),patch.object(C.os,'killpg') as kill:
            with self.assertRaises(OSError):C.Child(['never-run'],Path('/owned'),Path('/owned/raw'),Mock(),registry.append)
        self.assertEqual(len(registry),1);process.wait.assert_called_once();kill.assert_called_once_with(400001,signal.SIGTERM)
    def test_constructor_timeout_cleans_group_then_bounded_kill_reap(self):
        process=Mock(pid=400001,returncode=None,stdout=io.BytesIO(),stderr=io.BytesIO())
        process.wait.side_effect=[C.subprocess.TimeoutExpired('synthetic',2),0];registry=[]
        with patch.object(C.subprocess,'Popen',return_value=process),patch.object(C.os,'pidfd_open',side_effect=OSError('synthetic')),patch.object(C.os,'killpg') as kill:
            with self.assertRaises(OSError):C.Child([],Path('/owned'),Path('/owned/raw'),Mock(),registry.append)
        self.assertEqual([c.args[1] for c in kill.call_args_list],[signal.SIGTERM,signal.SIGKILL])
        self.assertEqual(process.wait.call_count,2)
    def test_private_raw_exact_bytes_before_projection(self):
        with tempfile.TemporaryDirectory() as directory:
            child=object.__new__(C.Child);child.streams={};child.failure=C.Event();child.error=None
            data=b'synthetic-private-stderr\x00\xff\n';path=Path(directory)/'raw'
            child._drain('stderr',io.BytesIO(data),path)
            self.assertEqual(path.read_bytes(),data);self.assertTrue(child.streams['stderr']['complete'])
            self.assertEqual(child.streams['stderr']['sha256'],C.digest(data))
    def test_cap_failure_visible_before_eof_not_only_final_streams(self):
        with tempfile.TemporaryDirectory() as directory:
            child=object.__new__(C.Child);child.streams={};child.failure=C.Event();child.error=None
            class Stream(io.BytesIO):
                def read(self,size):
                    if self.tell():assert child.failure.is_set()
                    return super().read(size)
            with patch.object(C,'PIPE_CAP',8):child._drain('stdout',Stream(b'x'*9),Path(directory)/'raw')
            self.assertTrue(child.failure.is_set());self.assertFalse(child.streams['stdout']['complete'])


class ExternalApprovalTests(unittest.TestCase):
    def fixture(self):
        er=(HERE/'conditional-envelope.json').read_bytes();e=json.loads(er)
        pr=Path(e['profile_file']).read_bytes();cr=(HERE/'smoke_controller_v3.py').read_bytes()
        root={'authorized':True,'scope':'EXACT_SEVEN_SMOKE_STAGES_ONCE_NO_LONG','source_commit':C.SOURCE,
            'envelope_sha256':C.digest(er),'profile_sha256':C.digest(pr),'controller_sha256':C.digest(cr)}
        return er,root,cr,pr
    def test_exact_external_root_record_accepts_only_bound_seven_smoke_commands(self):
        er,r,cr,pr=self.fixture();e,p=C.approved(er,r,cr,pr)
        self.assertEqual(tuple(s['stage'] for s in e['stages']),C.ORDER)
        self.assertTrue(p['smoke_scratch'].endswith('-02'))
    def test_envelope_cannot_self_approve_or_use_profilehash_as_permission(self):
        er,r,cr,pr=self.fixture()
        for bad in ({},{'profile_sha256':C.digest(pr)},{**r,'authorized':False}):
            with self.subTest(root=bad),self.assertRaisesRegex(ValueError,'root_envelope_GO_missing'):C.approved(er,bad,cr,pr)
    def test_each_external_exact_hash_is_required(self):
        for key in ('envelope_sha256','controller_sha256','profile_sha256'):
            er,r,cr,pr=self.fixture();r[key]='0'*64
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'exact_hash_mismatch'):C.approved(er,r,cr,pr)
    def test_root_approval_cannot_expand_to_long_or_eighth_stage(self):
        for extra in (False,True):
            er,r,cr,pr=self.fixture();e=json.loads(er)
            if extra:e['stages'].append(deepcopy(e['stages'][-1]))
            else:e['stages'][-1]['phase']='long-start'
            er=C.encoded(e);r['envelope_sha256']=C.digest(er)
            with self.subTest(extra=extra),self.assertRaises(ValueError):C.approved(er,r,cr,pr)


if __name__=='__main__':unittest.main(verbosity=2)
