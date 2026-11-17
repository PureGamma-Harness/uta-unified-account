"""Pure synthetic closure of immutable e444 review; never starts a process."""
from collections import Counter
from contextlib import nullcontext
from copy import deepcopy
import gzip
import importlib.util
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('m0_fixture',ROOT/'tests/test_independent_m0_controller.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
m=fixture.m

class IntegrityClosure(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory(prefix='m0-pure-closure-')
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'synthetic.gz'
        self.summary=fixture.PureM0Controls().summary()
        self.summary['latency_ms']['enqueue_ack']={k:.003 for k in ('p50','p95','p99','p99_9')}
        self.rows=[]
        for n in range(200):
            planned=1_000_000_000+n*50_000_000
            outcome='business_rejected' if n%10==0 else 'control_or_market_rejected' if n%10==1 else 'financial_succeeded'
            self.rows.append(dict(sequence=n,command_id=f'bench:{n}',order_id=f'order:{n}',outcome=outcome,
                planned_ns=planned,offered_ns=planned+1000,enqueue_started_ns=planned+2000,
                enqueue_ack_ns=planned+3000,enqueue_call_finished_ns=planned+4000,
                observed_completion_ns=planned+1_000_000,latency_ns=1_000_000,deadline_exceeded=False,
                intended_product_rejection=n%10==0,receipt=dict(command_id=f'bench:{n}',attempts=0,
                state='SUCCEEDED' if outcome=='financial_succeeded' else 'REJECTED',last_error=None)))
            self.rows[-1]['receipt']['error']=None if outcome=='financial_succeeded' else {
                'status':400 if outcome=='business_rejected' else 503,'code':'synthetic_only','message':'synthetic receipt'}
    def parsed(self):
        self.path.write_bytes(gzip.compress(b''.join((json.dumps(r)+'\n').encode() for r in self.rows),mtime=0))
        return m.project_arrivals(self.path)
    def checked(self):
        summary=m.project_summary(deepcopy(self.summary),False)
        rows=self.parsed()
        m.verify_population(summary,rows)
        return summary,rows
    def test_coherent_original_review_positive(self):
        self.assertEqual(len(self.checked()[1]),200)
    def test_original_1_outcomes_vs_counts(self):
        self.summary['outcome_counts'].update(financial_succeeded=159,control_or_market_rejected=21)
        with self.assertRaises(m.GateError):m.project_summary(self.summary,False)
    def test_original_2_negative_elapsed(self):
        self.summary['duration_including_terminal_observation_drain']=-1
        with self.assertRaises(m.GateError):m.project_summary(self.summary,False)
    def test_original_3_false_rate(self):
        self.summary['unique_observed_financial_success_per_s']=9999
        with self.assertRaises(m.GateError):m.project_summary(self.summary,False)
    def test_original_4_quantile_order(self):
        self.summary['latency_ms']['all'].update(p50=100,p95=1)
        with self.assertRaises(m.GateError):m.project_summary(self.summary,False)
    def test_original_5_wrong_receipt_cid(self):
        self.rows[2]['receipt']['command_id']='bench:199'
        with self.assertRaises(m.GateError):self.parsed()
    def test_original_6_rejected_financial(self):
        self.rows[2]['receipt']['state']='REJECTED'
        with self.assertRaises(m.GateError):self.parsed()
    def test_original_7_latency_and_ack(self):
        self.rows[2].update(latency_ns=1,enqueue_ack_ns=self.rows[2]['planned_ns']-1)
        with self.assertRaises(m.GateError):self.parsed()
    def test_original_8_cross_file_population(self):
        self.rows[199]['outcome']='business_rejected';self.rows[199]['receipt']['state']='REJECTED'
        self.rows[199]['receipt']['error']={'status':400,'code':'synthetic_only','message':'synthetic receipt'}
        with self.assertRaises(m.GateError):self.checked()
    def test_business_label_cannot_carry_control_error(self):
        self.rows[0]['receipt']['error']['status']=503
        with self.assertRaisesRegex(m.GateError,'receipt_rejection_classification'):self.parsed()
    def test_control_label_cannot_carry_business_error(self):
        self.rows[1]['receipt']['error']['status']=400
        with self.assertRaisesRegex(m.GateError,'receipt_rejection_classification'):self.parsed()
    def test_rejected_error_invalid_json(self):
        self.rows[0]['receipt']['error']='SYNTHETIC-NOT-JSON'
        with self.assertRaisesRegex(m.GateError,'rejection_error_json'):self.parsed()
    def test_rejected_error_missing_status(self):
        del self.rows[0]['receipt']['error']['status']
        with self.assertRaisesRegex(m.GateError,'rejection_error_shape'):self.parsed()
    def test_rejected_error_wrong_status_type(self):
        for value in (True,400.0,'400',float('nan'),float('inf'),99,600):
            with self.subTest(value=value):
                self.rows[0]['receipt']['error']['status']=value
                with self.assertRaises(m.GateError):self.parsed()
    def test_rejected_error_duplicate_json_keys(self):
        self.rows[0]['receipt']['error']='{"status":400,"status":503,"code":"synthetic","message":"stub"}'
        with self.assertRaises(m.GateError):self.parsed()
    def test_valid_rejected_error_json_string(self):
        self.rows[0]['receipt']['error']=json.dumps(self.rows[0]['receipt']['error'])
        self.assertEqual(self.parsed()[0]['receipt_error_status'],400)
    def test_success_cannot_have_error(self):
        self.rows[2]['receipt']['error']={'status':400,'code':'synthetic','message':'stub'}
        with self.assertRaisesRegex(m.GateError,'success_receipt_error'):self.parsed()
    def test_bool_counts_are_not_ints(self):
        for name in ('offered','duration_including_terminal_observation_drain'):
            with self.subTest(name=name):
                row=deepcopy(self.summary);row[name]=True
                with self.assertRaises(m.GateError):m.project_summary(row,False)
    def test_nonfinite_and_negative_quantiles(self):
        for value in (float('nan'),float('inf'),-1,True):
            with self.subTest(value=value):
                row=deepcopy(self.summary);row['latency_ms']['all']['p50']=value
                with self.assertRaises(m.GateError):m.project_summary(row,False)
    def test_false_ordered_quantiles_do_not_match_rows(self):
        self.summary['latency_ms']['all']={k:10 for k in ('p50','p95','p99','p99_9')}
        with self.assertRaises(m.GateError):self.checked()
    def test_ack_cannot_precede_enqueue(self):
        self.rows[2]['enqueue_ack_ns']=self.rows[2]['enqueue_started_ns']-1
        with self.assertRaises(m.GateError):self.parsed()
    def test_latency_exact_difference_and_deadline(self):
        self.rows[2]['latency_ns']+=1
        with self.assertRaises(m.GateError):self.parsed()
    def test_gzip_line_memory_bound_before_decode(self):
        self.path.write_bytes(gzip.compress(b'x'*65537,mtime=0))
        with self.assertRaises(m.GateError):m.project_arrivals(self.path)
    def test_decompress_whole_file_is_never_used(self):
        with patch.object(m.gzip,'decompress',side_effect=AssertionError('unbounded allocation')):
            self.assertEqual(len(self.parsed()),200)
    def test_total_unpacked_cap_is_checked_incrementally(self):
        with gzip.open(self.path,'wb') as stream:
            for row in self.rows:
                stream.write((json.dumps(dict(row,synthetic_padding='x'*45000))+'\n').encode())
        with self.assertRaisesRegex(m.GateError,'arrival_unpacked_cap'):m.project_arrivals(self.path)
    def test_footer_binds_actual_elapsed_to_source_window(self):
        summary,rows=self.checked()
        footer=dict(timing_contract_version=1,started_monotonic_ns=1_000_000_000,
            terminal_observation_finished_monotonic_ns=11_100_000_000,planned_duration_ns=10_000_000_000,setup_and_close_excluded=True)
        with self.assertRaisesRegex(m.GateError,'footer_elapsed_identity'):m.verify_timing_footer(summary,rows,footer)
    def test_footer_rejects_boolean_clock(self):
        summary,rows=self.checked()
        footer=dict(timing_contract_version=True,started_monotonic_ns=1_000_000_000,
            terminal_observation_finished_monotonic_ns=10_960_000_000,planned_duration_ns=10_000_000_000,setup_and_close_excluded=True)
        with self.assertRaises(m.GateError):m.verify_timing_footer(summary,rows,footer)
    def test_no_workload_or_sql_import(self):
        self.assertFalse(any(n=='uta' or n.startswith('uta.') or n=='sqlite3' for n in sys.modules))
    def exercise_owner(self, fail_phase=None, late_ns=None):
        root=Path(self.tmp.name);private=root/'private';public=root/'public'
        private.mkdir();public.mkdir();case=private/'B';staged=case/'safe-staged'
        events=[];active=False;finished=False
        real_write=m.public_write;real_read=m.read_json
        def write(folder,name,value):
            if active:events.append(('fsync',name))
            if active and fail_phase=='fsync' and name=='arrivals-B.json':raise m.GateError('stub_owner_deadline_during_fsync')
            return real_write(folder,name,value)
        def snapshot(source):
            self.assertTrue(active);events.append(('hash','source'))
            if fail_phase=='hash':raise m.GateError('stub_owner_deadline_during_hash')
            return {}
        def driver(command,source,where):
            self.assertTrue(active);events.append(('driver','inherited_session'))
            (where/'workload/profiles').mkdir(parents=True)
            (where/'driver.stdout').write_bytes(b'{}\n');(where/'driver.stderr').write_bytes(b'')
            return {'pid':98765,'birth_ticks':55,'session':98764}
        def arrivals(path):
            self.assertTrue(active);events.append(('parser','complete_population'))
            if fail_phase=='parser':raise m.GateError('stub_owner_deadline_during_parser')
            return deepcopy(self.rows_as_safe())
        def read(path,limit=4*1024**2):
            if Path(path).name=='measurement-footer.json':
                return dict(timing_contract_version=1,started_monotonic_ns=1_000_000_000,
                    terminal_observation_finished_monotonic_ns=10_960_000_000,planned_duration_ns=10_000_000_000,setup_and_close_excluded=True)
            return deepcopy(self.summary) if Path(path).name=='summary.json' else real_read(path,limit)
        def owner(argv,cwd,logs,**kw):
            nonlocal active,finished
            self.assertEqual(kw['wall_seconds'],56);self.assertEqual(kw['grace_seconds'],2);self.assertEqual(kw['kill_wait_seconds'],2)
            self.assertIn('--case-worker',argv);events.append(('owner','start'));active=True
            case.mkdir();(case/'tmp').mkdir();staged.mkdir()
            outcome='EXITED';code=0
            try:
                result=m.case_pipeline(Path('/synthetic/source'),case,staged,'B',False,{},[3])
                (public/'case-B-safe').parent.mkdir(exist_ok=True)
                staged.rename(public/'case-B-safe');write(case,'completed.json',result)
            except m.GateError:
                outcome='UNKNOWN';code=-15
            finally:active=False;finished=True;events.append(('owner','cleaned'))
            (private/'case-owner-B.stderr').write_bytes(b'')
            return dict(outcome=outcome,returncode=code,watchdog_reason=None if code==0 else 'wall_deadline_unknown',
                leader_reaped=True,stdout_stderr_complete=True,identity={'pid':98764,'birth_ticks':54})
        owned=SimpleNamespace(owned_run=owner,process_identity=lambda pid:{'birth_ticks':53})
        clock=patch.object(m.time,'monotonic_ns',side_effect=lambda:late_ns if finished else 0) if late_ns is not None else nullcontext()
        with clock,patch.dict(m.os.environ,{'RUNNER_TEMP':str(root)}),patch.object(m,'source_snapshot',snapshot),\
                patch.object(m,'case_driver',driver),patch.object(m,'project_arrivals',arrivals),\
                patch.object(m,'public_write',write),patch.object(m,'read_json',read):
            result=m.supervised_case(owned,Path('/synthetic/source'),private,public,'B',False,{},
                {'control_commit':'a'*40},{'boot_id':'synthetic','hostname_sha256':'b'*64},[3],lambda _:None)
        return result,events,private,public
    def rows_as_safe(self):
        # Actual parser is exercised separately; no credentials/payload in stubs.
        return [{**{k:v for k,v in r.items() if k not in ('receipt','order_id')},
                 'receipt_state':r['receipt']['state'],'receipt_attempts':0,'receipt_last_error_present':False} for r in self.rows]
    def test_owner_encloses_hash_parser_and_fsync_pipeline(self):
        result,events,private,public=self.exercise_owner()
        self.assertEqual(result['status'],'PASS');self.assertEqual(events[0],('owner','start'))
        self.assertEqual(events[-1],('owner','cleaned'))
        self.assertTrue({'hash','driver','parser','fsync'}<={event[0] for event in events})
        self.assertTrue((public/'case-B-safe/case-B.json').is_file())
    def test_owner_unknown_during_last_fsync_preserves_partial_private(self):
        result,events,private,public=self.exercise_owner('fsync')
        self.assertEqual(result['status'],'UNKNOWN');self.assertTrue(result['owner_cleanup']['leader_reaped'])
        self.assertTrue((private/'B/safe-staged/case-B.json').is_file());self.assertFalse(list(public.iterdir()))
    def test_owner_unknown_during_parser_stops(self):
        result,events,private,public=self.exercise_owner('parser')
        self.assertEqual(result['status'],'UNKNOWN');self.assertEqual(result['error_code'],'whole_case_unknown')
        self.assertFalse(list(public.iterdir()))
    def test_owner_unknown_during_source_hash_stops(self):
        result,events,private,public=self.exercise_owner('hash')
        self.assertEqual(result['status'],'UNKNOWN');self.assertFalse(list(public.iterdir()))
    def test_postprocessing_past_sixty_seconds_is_unknown(self):
        result,events,private,public=self.exercise_owner(late_ns=61_000_000_000)
        self.assertEqual(result['status'],'UNKNOWN');self.assertEqual(result['error_code'],'case_complete_outer_deadline')
        self.assertTrue((private/'B/safe-quarantined/case-B.json').is_file());self.assertFalse(list(public.iterdir()))
    def test_nested_public_manifest_is_exact(self):
        root=Path(self.tmp.name);folder=root/'case-B-safe';folder.mkdir()
        record=m.public_write(folder,'safe.json',{'count':1});record['name']='case-B-safe/safe.json'
        m.public_write(root,'manifest.json',dict(files=[record],source_commit=m.SOURCE,
            private_authorities_requests_keys_nonces_signatures_streams_not_uploaded=True))
        self.assertTrue(m.verify_public(root))
        (folder/'unlisted.json').write_bytes(b'{}')
        with self.assertRaises(m.GateError):m.verify_public(root)

if __name__=='__main__':unittest.main()
