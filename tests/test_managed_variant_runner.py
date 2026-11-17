"""Pure/synthetic runner oracles and owned short dummy lifecycle checks.

Only test_tiny_footer calls the real benchmark (one 8-arrival functional case).
No variant cohort, pressure, profile, database or service is otherwise started.
"""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import gzip
import io
import json
import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

from tools import run_managed_variants as runner

ROOT = Path(__file__).resolve().parents[1]
COMMIT = 'c' * 40


def store(path, value):
    path.write_text(json.dumps(value) + '\n')
    return {'path': str(path), 'sha256': runner.digest(path)}


def registration(path):
    return {'format': 1, 'registration_id': 'fixture-only', 'source_commit': COMMIT,
        'base_plan_sha256': runner.PLAN_HASH, 'execution_go': False,
        'registered_utc': '2026-11-17T00:00:00+00:00', 'output_root': str(path / 'must-not-exist'),
        'cpu_ids': [2, 3], 'limits': {'case_wall_seconds': 60, 'grace_seconds': 2,
        'kill_wait_seconds': 2, 'case_bytes': 16 * runner.MiB, 'aggregate_bytes': 512 * runner.MiB,
        'cleanup_bytes': 128 * runner.MiB},
        'cohosts': [{'pid': pid, 'birth_ticks': 1, 'heartbeat': str(path / 'cohosts' / ('host-' + str(pid) + '.json')),
        'heartbeat_pointer': ['observed_utc'], 'source_pointer': ['source_commit'],
        'alerts_pointer':['assessment','alerts'], 'work_age_pointer':['assessment','heartbeat_age_seconds'],
        'source_commit': 'a' * 40, 'max_age_seconds': 60} for pid in (4471, 8784)],
        'reserves': {name: {'remaining_bytes': amount, 'evidence': {'path': str(path / 'reserves.json'),
        'sha256': 'b' * 64}, 'pointer': [name]} for name, amount in runner.RESERVES.items()},
        'qualification': {'expected_tests': 2, 'local': [], 'ci': [], 'package': {}}}


def qualification_fixture(root):
    value = registration(root)
    from tests.runner_package_fixtures import create_package_evidence
    hashes,package=create_package_evidence(root,COMMIT)
    expected = {name:sha for name,sha in hashes.items() if name.endswith('.py') or name=='pyproject.toml'}
    worker = dict(tests_run=2,failures=0,errors=0,skipped=0,expected_failures=0,unexpected_successes=0,unittest_passed=True)
    def record(label, version, event=None):
        log = root/(label+'.txt'); log.write_text('Ran 2 tests in 0.1s\n\nOK\n')
        summary = dict(worker,code_commit=COMMIT,worker_exit_code=0,passed=True,source_unchanged=True,
            tracked_source_clean_before=True,tracked_source_clean_after=True,source_sha256=expected,
            source_sha256_after=expected,test_log_sha256=runner.digest(log),python=version+'.1',
            command_argv=['/fixture/python','/fixture/tools/run_validation.py','--output','/fixture/results'])
        result={'python':version,'summary':store(root/(label+'.json'),summary),
            'worker':store(root/(label+'-worker.json'),worker),'log':{'path':str(log),'sha256':runner.digest(log)}}
        if event:
            result['run']=store(root/(label+'-run.json'),{'event':event,'head_sha':COMMIT,'id':123,
                'status':'completed','conclusion':'success','html_url':'https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/123'})
            result['job']=store(root/(label+'-job.json'),{'run_id':123,'status':'completed','conclusion':'success','name':'Validate ('+version+')'})
        return result
    q=value['qualification'];q['local']=[record('local'+v,v) for v in ('3.10','3.12','3.13')]
    q['ci']=[record(event+v,v,event) for event in ('push','pull_request') for v in ('3.10','3.11','3.12','3.13')]
    q['package']=package
    return hashes,value


def raw_fixture(root,late=False):
    start=10**12; hashes={'uta/__init__.py':'a'*64,'benchmarks/run_managed_benchmark.py':'b'*64}
    config=dict(duration=10,rate=20,accounts=100,shards=2,dispatchers=2,outstanding=256,inbox_capacity=128,
        reject_every=10,feed_interval=2,control_timeout=3,drain_seconds=10,timeout_ms=1000,poll_interval=.02,
        background_interval=.1,profile=False,durable_batches=True,financial_batch_size=0,normal_cache_size=0)
    rows=[]
    for i in range(200):
        rejected=i%10==9; planned=start+i*50_000_000; latency=2*10**9 if late and i==0 else 10**6
        account='managed-probe-'+str(i%100);cid='bench:'+str(i)
        receipt={'state':'REJECTED' if rejected else 'SUCCEEDED','command_id':cid,'account_id':account,
            'attempts':0,'last_error':None,'error':{'status':400} if rejected else None,
            'result':None if rejected else {'status':'OPEN','filled_quantity':'0','reserved_margin':'.01004'}}
        rows.append(dict(sequence=i,command_id=cid,order_id='order:'+str(i),account_id=account,
            planned_ns=planned,offered_ns=planned,enqueue_started_ns=planned,enqueue_ack_ns=planned+100000,
            enqueue_call_finished_ns=planned+200000,observed_completion_ns=planned+latency,latency_ns=latency,
            deadline_exceeded=latency>10**9,outcome='business_rejected' if rejected else 'financial_succeeded',receipt=receipt))
    settings=dict(lease_seconds=5.,poll_interval=.02,background_interval=.1,account_batch=25,
        matches_per_symbol=10,max_attempts=3,financial_batch_size=0,normal_cache_size=0)
    histogram={name:{p:(.1 if name=='enqueue_ack' else 2000 if late and p=='p99_9' else 1)
        for p in ('p50','p95','p99','p99_9')} for name in ('all','financial_succeeded','enqueue_ack')}
    summary=dict(configuration=config,offered=200,outcome_counts={'financial_succeeded':180,'business_rejected':20},
        counts={'financial_succeeded':180,'business_rejected':20,'durably_enqueued':200,'financial_success_late':int(late)},
        duration_including_terminal_observation_drain=10.,drain_seconds=0.,unique_observed_financial_success_per_s=18.,
        enqueue_ack_per_s_not_financial_success=20.,latency_ms=histogram,
        environment={'code_commit':COMMIT,'working_tree_dirty':False,'generator_sha256':'b'*64,'source_sha256':{'__init__.py':'a'*64}},
        actual_runtime={'router_settings':settings,'durable_batches_capability':True,'decision_audit_required':True,
            'financial_batch_soft_budget_seconds':.005,'physical_commit_counts_measured':False},
        actual_spawned_worker_inputs=[{'pid':pid,'received_settings':settings} for pid in (101,102)],
        initial_real_pid_and_fence={'workers':[{'pid':pid,'owner_pid':pid,'lease_active':True} for pid in (101,102)]},
        readonly_reconciliation={'reopened_readonly':True,'persistent_successes':180,'pending_count':0,'unobserved_successes_found_on_reopen':0,
            'shards':[{'confirmed_matches':0,'durable_batches_capability':True,'audit_required':True,
                'independent_reserve_account_version_ledger_verified':True}]*2},
        probe_qualification={'passed':True,'financial_soft_deadline_passed':not late},
        command_technical_diagnostics={key:0 for key in ('internal_execution_attempts','commands_with_last_error','quarantined_commands','nonterminal_commands','control_commands_not_succeeded')},
        batch_dispatch_diagnostics={key:0 for key in ('failure_events','recovered_batches','unresolved_batches')},poll_errors=[],feed_publications=[])
    store(root/'summary.json',summary)
    store(root/'arrival-window.json',{'configuration':config,'offered':200,'planned_start_monotonic_ns':start})
    store(root/'measurement-footer.json',{'timing_contract_version':1,'setup_and_close_excluded':True,
        'started_monotonic_ns':start,'terminal_observation_finished_monotonic_ns':start+10**10,'planned_duration_ns':10**10})
    (root/'arrivals.jsonl.gz').write_bytes(gzip.compress(('\n'.join(json.dumps(row) for row in rows)+'\n').encode(),mtime=0))
    store(root/'manifest.json',{'files':{p.name:{'bytes':p.stat().st_size,'sha256':runner.digest(p)} for p in root.iterdir() if p.is_file()}})
    return hashes


class RunnerPureTests(unittest.TestCase):
    def test_complete_synthetic_evidence_contract_and_each_red_CI_refusal(self):
        with TemporaryDirectory() as temporary:
            root=Path(temporary);hashes,value=qualification_fixture(root)
            runner.qualification(hashes,value)
            for bad in (False,None):
                changed=deepcopy(value);ref=changed['qualification']['ci'][4]['summary']
                data=runner.read_json(ref['path']);data['passed']=bad
                changed['qualification']['ci'][4]['summary']=store(root/'failed-CI.json',data)
                with self.subTest(passed=bad),self.assertRaises(runner.GateError):runner.qualification(hashes,changed)
            changed=deepcopy(value);changed['source_commit']='a35fd56fc98126b3e5cced8a459bd04ca580e537'
            with self.assertRaises(runner.GateError):runner.qualification(hashes,changed)

    def test_raw_oracle_reconstructs_counts_N_max_denominator_and_preserves_late_red(self):
        for late in (False,True):
            with TemporaryDirectory() as temporary:
                root=Path(temporary);hashes=raw_fixture(root,late)
                result=runner.recompute(root,runner.schedule()[0],hashes,COMMIT)
                self.assertEqual(result['counts'],{'financial_succeeded':180,'business_rejected':20})
                self.assertEqual(result['groups']['all']['N'],200)
                self.assertEqual(result['groups']['financial_succeeded']['N'],180)
                self.assertEqual(result['groups']['enqueue_ack']['N'],200)
                self.assertEqual(result['denominator_ns'],10**10)
                self.assertEqual(result['financial_per_second'],18.)
                self.assertEqual(result['groups']['all']['max_ns'],2*10**9 if late else 10**6)
                self.assertIs(result['technical_and_deadline_passed'],not late)
                self.assertEqual(result['financial_success_late'],int(late))
                forensic=runner.forensic_counts(root)
                self.assertEqual(forensic['counts'],result['counts'])
                self.assertEqual(forensic['groups']['all']['N'],200)
                self.assertEqual(forensic['actual_footer_denominator_ns'],10**10)
                self.assertFalse(forensic['financial_verified'])

    def test_default_prepare_never_starts_process_opens_DB_or_creates_output(self):
        with TemporaryDirectory() as temporary:
            value = registration(Path(temporary))
            with patch.object(runner.subprocess, 'Popen', side_effect=AssertionError('no PID')), \
                    patch.object(Path, 'mkdir', side_effect=AssertionError('no output directory')), \
                    patch.object(runner.os, 'sched_setaffinity', side_effect=AssertionError('no affinity write')):
                result = runner.prepare(ROOT, value)
            self.assertEqual(result['mode'], 'PREPARE_ONLY')
            self.assertFalse(result['execution_authorized_by_prepare'])
            self.assertFalse(Path(value['output_root']).exists())
            self.assertNotIn('sqlite3', runner.__dict__)
            self.assertEqual(len(result['cases']), 24)

    def test_partial_unknown_raw_retains_complete_prefix_counts_without_inventing_denominator(self):
        with TemporaryDirectory() as temporary:
            root=Path(temporary);raw_fixture(root)
            zipped=root/'arrivals.jsonl.gz'
            data=gzip.decompress(zipped.read_bytes());zipped.unlink()
            (root/'arrivals.jsonl').write_bytes(data[:-10])
            (root/'measurement-footer.json').unlink()
            result=runner.forensic_counts(root)
            self.assertEqual(result['groups']['all']['N'],199)
            self.assertEqual(result['counts'],{'financial_succeeded':180,'business_rejected':19})
            self.assertTrue(result['partial_tail_ignored_but_original_retained'])
            self.assertIsNone(result['actual_footer_denominator_ns'])
            self.assertFalse(result['financial_verified'])

    def test_cases_are_same_capability_single_factor_AB_BA_AB(self):
        cases = runner.schedule()
        for offset, variant in enumerate(('B3', 'B8', 'C8', 'C100')):
            self.assertEqual([case.variant for case in cases[offset*6:offset*6+6]], ['A',variant,variant,'A','A',variant])
        with self.assertRaises(runner.GateError):
            runner.Case('B8-FAKE', 'B8', 8, 100).validate()
        argv = runner.case_argv(ROOT, '/unused-fixture', cases[0])
        self.assertIn('--durable-batches', argv)
        self.assertNotIn('--profile', argv)

    def test_bad_limits_and_missing_GO_reject_before_any_process_or_output(self):
        with TemporaryDirectory() as temporary:
            value = registration(Path(temporary))
            mutations = [('case_wall_seconds', True), ('case_bytes', 65*runner.MiB),
                         ('aggregate_bytes', 513*runner.MiB), ('cleanup_bytes', 0)]
            with patch.object(runner.subprocess, 'Popen', side_effect=AssertionError('no PID')):
                for key, bad in mutations:
                    changed = deepcopy(value); changed['limits'][key] = bad
                    with self.subTest(key=key), self.assertRaises(runner.GateError):
                        runner.prepare(ROOT, changed)
                with self.assertRaises(runner.GateError):
                    runner.execute(ROOT, value, store(Path(temporary)/'registration.json',value)['path'])
            self.assertFalse(Path(value['output_root']).exists())
        with self.assertRaises(runner.GateError):
            runner.strict_json('{"a":1,"a":2}')
        with self.assertRaises(runner.GateError):
            runner.strict_json('{"a":NaN}')

    def test_missing_old_and_red_qualification_fail_closed(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary); value = registration(root)
            with self.assertRaisesRegex(runner.GateError, 'three local'):
                runner.qualification({}, value)
            # A real-record-shaped fixture carries an original a35 red result.
            # Its booleans cannot be promoted by a separate all-green label.
            q = value['qualification']
            bad = {'python': '3.10', 'summary': store(root/'red.json', {'passed':False}),
                   'worker': store(root/'worker.json', {}),
                   'log': {'path': str(root/'raw.txt'), 'sha256': 'a'*64}}
            q['local'] = [bad]*3; q['ci'] = [bad]*8
            (root/'raw.txt').write_text('FAILED (failures=1)\n')
            bad['log']['sha256'] = runner.digest(root/'raw.txt')
            with self.assertRaises((runner.GateError, KeyError)):
                runner.qualification({}, value)

    def test_disk_reservations_are_additive_and_not_replaced_by_two_GiB(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary); value = registration(root)
            ref = store(root/'reserve.json', runner.RESERVES)
            for item in value['reserves'].values(): item['evidence'] = ref
            class Disk:
                f_frsize = 1
                f_bavail = 2*runner.GiB
            with patch.object(runner.os, 'statvfs', return_value=Disk()), self.assertRaisesRegex(runner.GateError, 'headroom'):
                runner.resources(value, root)
            Disk.f_bavail = 32*runner.GiB
            with patch.object(runner.os, 'statvfs', return_value=Disk()):
                result = runner.resources(value, root)
            self.assertEqual(result['retained_cohost_reservations_bytes'], sum(runner.RESERVES.values()))
            self.assertGreater(result['required_free_bytes'], 15*runner.GiB)

    def test_fresh_observer_cannot_mask_stale_underlying_work_or_cohost_alerts(self):
        with TemporaryDirectory() as temporary:
            root=Path(temporary);host=registration(root)['cohosts'][0]
            path=Path(host['heartbeat']);path.parent.mkdir()
            data={'observed_utc':datetime.now(timezone.utc).isoformat(),'source_commit':'a'*40,
                  'assessment':{'alerts':[],'heartbeat_age_seconds':.5}}
            store(path,data)
            with patch.object(runner,'process_identity',return_value={'pid':host['pid'],'birth_ticks':1,'state':'S'}):
                self.assertEqual(len(runner.cohost_observations([host])),1)
                data['assessment']['alerts']=['io_error'];store(path,data)
                with self.assertRaises(runner.GateError):runner.cohost_observations([host])
                data['assessment']={'alerts':[],'heartbeat_age_seconds':200};store(path,data)
                with self.assertRaises(runner.GateError):runner.cohost_observations([host])

    def test_technical_pass_does_not_mask_late_success_and_CLI_zero(self):
        self.assertFalse(runner.composite_gate({'probe_qualification': {
            'passed': True, 'financial_soft_deadline_passed': False}}))
        self.assertFalse(runner.composite_gate({'probe_qualification': {'passed': True}}))
        self.assertFalse(runner.composite_gate({'probe_qualification': {
            'passed': False, 'financial_soft_deadline_passed': True}}))

    def test_execute_stops_after_first_CLI_zero_but_late_case_without_starting_next(self):
        with TemporaryDirectory() as temporary:
            root=Path(temporary);value=registration(root);value['execution_go']=True
            original=store(root/'registration.json',value)
            with patch.object(runner,'source_identity',return_value={'fixture':'sha'}), \
                    patch.object(runner,'qualification'),patch.object(runner,'cohost_observations',return_value=[]), \
                    patch.object(runner,'resources',return_value={}), \
                    patch.object(runner.os,'sched_getaffinity',return_value={2,3}), \
                    patch.object(runner.os,'sched_setaffinity'), \
                    patch.object(runner,'owned_run',return_value={'outcome':'EXITED','returncode':0,'stdout_stderr_complete':True}) as child, \
                    patch.object(runner,'recompute',return_value={'technical_and_deadline_passed':False,'groups':{'all':{'N':200}}}):
                self.assertFalse(runner.execute(ROOT,value,original['path']))
            self.assertEqual(child.call_count,1)
            record=runner.read_json(Path(value['output_root'])/'execution.json')
            self.assertTrue(record['stopped'])
            self.assertEqual(len(record['cases']),1)
            self.assertFalse(record['all_short_diagnostics_passed'])
            self.assertEqual(record['cases'][0]['child']['returncode'],0)
            self.assertEqual(record['cases'][0]['recomputed']['groups']['all']['N'],200)

    def test_old_raw_has_no_new_timing_footer_and_is_never_upgraded(self):
        path = ROOT/'docs/evidence/managed-variant-wiring-20261117/raw/py312/default'
        self.assertFalse((path/'measurement-footer.json').exists())
        with self.assertRaisesRegex(runner.GateError, 'missing from manifest'):
            runner.recompute(path, runner.schedule()[0], {}, COMMIT)


class RunnerDummyTests(unittest.TestCase):
    def run_dummy(self, root, code, **changes):
        settings = dict(cpu_ids=[min(os.sched_getaffinity(0))], wall_seconds=1,
            grace_seconds=.05, kill_wait_seconds=.5, output_cap=4096, protected={os.getpid()})
        settings.update(changes)
        result = runner.owned_run([__import__('sys').executable, '-c', code], root, root/'dummy', **settings)
        if os.environ.get('UTA_VARIANT_RUNNER_EVIDENCE'):
            output = Path(os.environ['UTA_VARIANT_RUNNER_EVIDENCE'])/self._testMethodName
            output.mkdir(parents=True, exist_ok=False)
            for path in root.glob('dummy.*'):
                shutil.copy2(path, output/path.name)
            store(output/'result.json', result)
        return result

    def test_dummy_records_original_streams_owned_birth_pidfd_and_reaps(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary); result = self.run_dummy(root, 'print("owned-ok")')
            self.assertEqual(result['returncode'], 0)
            self.assertEqual(result['outcome'], 'EXITED')
            self.assertTrue(result['pidfd_used'] and result['leader_reaped'] and result['stdout_stderr_complete'])
            self.assertEqual(result['identity']['group'], result['identity']['session'])
            self.assertNotEqual(result['identity']['pid'], os.getpid())
            self.assertEqual((root/'dummy.stdout').read_text(), 'owned-ok\n')
            self.assertEqual(runner.digest(root/'dummy.stdout'), result['streams'][0]['sha256'])

    def test_dummy_timeout_kills_only_owned_session_and_preserves_parent(self):
        before = runner.process_identity(os.getpid())
        with TemporaryDirectory() as temporary:
            result = self.run_dummy(Path(temporary), 'import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(20)', wall_seconds=.15)
            self.assertEqual(result['outcome'], 'UNKNOWN')
            self.assertEqual(result['watchdog_reason'], 'wall_deadline_unknown')
            self.assertTrue(result['leader_reaped'])
        self.assertEqual(runner.process_identity(os.getpid())['birth_ticks'], before['birth_ticks'])
        self.assertTrue({4471,8784} <= runner.PROTECTED)

    def test_dummy_output_overrun_is_unknown_even_with_child_exit_zero(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary); result = self.run_dummy(root, 'print("x"*100000)', output_cap=256)
            self.assertEqual(result['outcome'], 'UNKNOWN')
            self.assertFalse(result['stdout_stderr_complete'])
            self.assertLessEqual(sum(row['bytes'] for row in result['streams']), 256)
            self.assertTrue(result['leader_reaped'])


class RunnerFooterTinyTests(unittest.TestCase):
    def test_tiny_footer_captures_real_settled_before_close_and_reconciles_eight_orders(self):
        # Exactly one actual .05s / eight-arrival functional call. No profile.
        from benchmarks.run_managed_benchmark import Configuration, run
        before = runner.digest(ROOT/'benchmarks/run_managed_benchmark.py')
        with TemporaryDirectory() as temporary:
            output = Path(os.environ.get('UTA_VARIANT_FOOTER_EVIDENCE', temporary))/'tiny-footer'
            summary = run(Configuration(duration=.05, rate=160, accounts=3, shards=1,
                reject_every=0, durable_batches=True, drain_seconds=5), output)
            footer = runner.read_json(output/'measurement-footer.json')
            window = runner.read_json(output/'arrival-window.json')
            with gzip.open(output/'arrivals.jsonl.gz','rt') as stream: rows=[json.loads(line) for line in stream]
            self.assertEqual(footer['started_monotonic_ns'],window['planned_start_monotonic_ns'])
            self.assertEqual(footer['planned_duration_ns'],50_000_000)
            self.assertTrue(footer['setup_and_close_excluded'])
            settled=footer['terminal_observation_finished_monotonic_ns']
            self.assertLessEqual(max(row['observed_completion_ns'] for row in rows),settled)
            ns=max(50_000_000,settled-footer['started_monotonic_ns'])
            self.assertEqual(summary['duration_including_terminal_observation_drain'],ns/1e9)
            self.assertEqual(summary['counts']['financial_succeeded'],8)
            self.assertEqual(summary['readonly_reconciliation']['persistent_successes'],8)
            manifest=runner.read_json(output/'manifest.json')
            self.assertEqual(manifest['files']['measurement-footer.json']['sha256'],runner.digest(output/'measurement-footer.json'))
            self.assertFalse(summary['production_approved'])
        self.assertEqual(before,runner.digest(ROOT/'benchmarks/run_managed_benchmark.py'))


if __name__ == '__main__':
    unittest.main()
