"""Pure stub controls only: no SQL/product/profile/workload/Actions execution."""
from contextlib import nullcontext, redirect_stdout
from datetime import datetime, timezone, timedelta
import importlib.util
import io
import json
import marshal
import os
from pathlib import Path
import stat
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

PATH=Path(__file__).resolve().parents[1]/'tools/independent_m0_controller.py'
spec=importlib.util.spec_from_file_location('m0_controller_under_pure_test',PATH)
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)

class PureM0Controls(unittest.TestCase):
    def approval(self):
        return {'operator_approval_id':'synthetic-review-1','control_commit':'a'*40,
            'controller_sha256':'b'*64,'workspace_boot_id':'11111111-1111-1111-1111-111111111111',
            'workspace_hostname_sha256':'c'*64,'workspace_recorded_at':datetime.now(timezone.utc).isoformat(),
            'source_commit':m.SOURCE}
    def env(self):
        return {'GITHUB_ACTIONS':'true','RUNNER_ENVIRONMENT':'github-hosted','GITHUB_EVENT_NAME':'workflow_dispatch',
            'GITHUB_SHA':'a'*40,'RUNNER_OS':'Linux','GITHUB_RUN_ATTEMPT':'1','GITHUB_RUN_ID':'12345'}
    def actual(self):
        return {'boot_id':'22222222-2222-2222-2222-222222222222','hostname_sha256':'d'*64,
            'filesystem_type':'ext4','free_bytes':m.MIN_FREE,'network_external_exchange_configured':False}
    def reject(self,approval=None,env=None,actual=None):
        with self.assertRaises(m.GateError):m.validate_dispatch(approval or self.approval(),env or self.env(),actual or self.actual(),'b'*64)
    def summary(self):
        settings={'normal_cache_size':0,'financial_batch_size':0,'account_batch':25,'matches_per_symbol':10,'max_attempts':3,'lease_seconds':5,'poll_interval':.02,'background_interval':.1}
        return {'configuration':{'duration':10,'rate':20,'accounts':100,'shards':2,'normal_cache_size':0,'financial_batch_size':0,'durable_batches':True,'profile':False},'offered':200,
            'outcome_counts':{'financial_succeeded':160,'business_rejected':20,'control_or_market_rejected':20},
            'counts':{'financial_succeeded':160,'business_rejected':20,'control_or_market_rejected':20,'durably_enqueued':200,'enqueue_technical_errors':0,'financial_success_late':0},
            'command_technical_diagnostics':{k:0 for k in ('internal_execution_attempts','commands_with_internal_attempts','commands_with_last_error','quarantined_commands','nonterminal_commands','control_commands_not_succeeded')},
            'batch_dispatch_diagnostics':{k:0 for k in ('failure_events','unresolved_batches','recovered_batches')},'poll_errors':[],
            'probe_qualification':{'passed':True,'financial_soft_deadline_passed':True},
            'readonly_reconciliation':{'reopened_readonly':True,'pending_count':0,'unobserved_successes_found_on_reopen':0,'observed_financial_successes':160,'persistent_successes':160,'durable_enqueue_acknowledgements_verified':200},
            'environment':{'code_commit':m.SOURCE,'working_tree_dirty':False,'cpu_affinity_count':1},
            'actual_runtime':{'durable_batches_capability':True,'decision_audit_required':True,'router_settings':settings},
            'actual_spawned_worker_inputs':[{'pid':9876541,'received_settings':settings},{'pid':9876542,'received_settings':settings}],
            'latency_ms':{name:{key:1 for key in ('p50','p95','p99','p99_9')} for name in ('all','financial_succeeded','enqueue_ack')},
            'duration_including_terminal_observation_drain':10,'drain_seconds':0,'close_seconds_excluded':.1,'startup_seconds_excluded':.5,
            'unique_observed_financial_success_per_s':16,'enqueue_ack_per_s_not_financial_success':20}
    def test_summary_valid_stub_projects_no_requests_or_credentials(self):
        row=self.summary();row['private_request']='STUB-PRIVATE';safe=m.project_summary(row,False)
        self.assertNotIn('private_request',safe);self.assertNotIn('STUB-PRIVATE',json.dumps(safe));self.assertFalse(safe['production_approved'])
    def test_internal_retry_is_not_erased_by_terminal_success(self):
        row=self.summary();row['command_technical_diagnostics']['internal_execution_attempts']=1
        with self.assertRaises(m.GateError):m.project_summary(row,False)
    def test_late_success_is_not_qualified(self):
        row=self.summary();row['probe_qualification']['financial_soft_deadline_passed']=False
        with self.assertRaises(m.GateError):m.project_summary(row,False)
    def test_unknown_count_key_cannot_exfiltrate_numeric_private_data(self):
        row=self.summary();row['counts']['private_nonce']=123
        with self.assertRaises(m.GateError):m.project_summary(row,False)
    def test_actual_worker_settings_not_requested_only(self):
        row=self.summary();row['actual_spawned_worker_inputs'][0]['received_settings']={'normal_cache_size':10}
        with self.assertRaises(m.GateError):m.project_summary(row,False)
    def test_readonly_actual_success_count_is_required(self):
        row=self.summary();row['readonly_reconciliation']['persistent_successes']=159
        with self.assertRaises(m.GateError):m.project_summary(row,False)
    def once(self):
        a=self.approval()
        return {'format':2,'kind':'ROOT_REVIEWED_ONCE_M0_V2_ESCROW','execution_authorized':True,
            'registration_id':m.REGISTRATION_ID,'branch':m.APPROVED_BRANCH,
            'control_commit':a['control_commit'],'controller_sha256':a['controller_sha256'],'workflow_sha256':'e'*64,
            'source_commit':m.SOURCE,'source_tree':m.SOURCE_TREE,'command_spec':m.command_spec(),'budgets':m.budget_spec(),
            'workspace_boot_id':a['workspace_boot_id'],'workspace_hostname_sha256':a['workspace_hostname_sha256'],
            'workspace_recorded_at':a['workspace_recorded_at'],'retention_mode':'four_closed_streams_CMS_AES256GCM_RSA_OAEP_SHA256',
            'escrow_tool_sha256':'d'*64,'recipient_certificate_sha256':m.RECIPIENT_PEM,'recipient_spki_sha256':m.RECIPIENT_SPKI}
    def once_context(self):
        e=self.env();e.update(GITHUB_EVENT_NAME='push',GITHUB_REF=m.APPROVED_BRANCH,GITHUB_SHA='f'*40)
        event={'ref':m.APPROVED_BRANCH,'created':True,'deleted':False,'forced':False,'before':'0'*40,'after':'f'*40}
        relation={'execution_commit':'f'*40,'parents':['a'*40],'changed_paths':[m.APPROVAL_PATH],'changed_status':['A']}
        return e,event,relation
    def test_once_manifest_valid_stub(self):
        e,event,relation=self.once_context();self.assertTrue(m.validate_once_manifest(self.once(),e,event,relation))
    def test_other_push_branch_has_no_workload_permission(self):
        e,event,relation=self.once_context();e['GITHUB_REF']='refs/heads/plan/unapproved'
        with self.assertRaises(m.GateError):m.validate_once_manifest(self.once(),e,event,relation)
    def test_existing_branch_update_is_rejected(self):
        e,event,relation=self.once_context();event['created']=False;event['before']='1'*40
        with self.assertRaises(m.GateError):m.validate_once_manifest(self.once(),e,event,relation)
    def test_second_attempt_on_once_branch_is_rejected(self):
        e,event,relation=self.once_context();e['GITHUB_RUN_ATTEMPT']='2'
        with self.assertRaises(m.GateError):m.validate_once_manifest(self.once(),e,event,relation)
    def test_manifest_child_cannot_change_code_or_workflow(self):
        e,event,relation=self.once_context();relation['changed_paths'].append(m.ONCE_WORKFLOW);relation['changed_status'].append('M')
        with self.assertRaises(m.GateError):m.validate_once_manifest(self.once(),e,event,relation)
    def test_manifest_is_added_not_modification(self):
        e,event,relation=self.once_context();relation['changed_status']=['M']
        with self.assertRaises(m.GateError):m.validate_once_manifest(self.once(),e,event,relation)
    def test_manifest_only_child_single_reviewed_parent(self):
        e,event,relation=self.once_context();relation['parents'].append('b'*40)
        with self.assertRaises(m.GateError):m.validate_once_manifest(self.once(),e,event,relation)
    def test_false_or_numeric_approval_cannot_execute(self):
        e,event,relation=self.once_context()
        for flag in (False,1):
            with self.subTest(flag=flag):
                v=self.once();v['execution_authorized']=flag
                with self.assertRaises(m.GateError):m.validate_once_manifest(v,e,event,relation)
    def test_once_command_or_budget_mutation_rejected(self):
        e,event,relation=self.once_context();v=self.once();v['budgets']['case_bytes']+=1
        with self.assertRaises(m.GateError):m.validate_once_manifest(v,e,event,relation)
    def test_once_case_profile_bool_is_not_numeric(self):
        e,event,relation=self.once_context();v=self.once();v['command_spec']['case_order'][1][1]=1
        with self.assertRaises(m.GateError):m.validate_once_manifest(v,e,event,relation)
    def test_unimplemented_encryption_mode_not_claimed(self):
        e,event,relation=self.once_context();v=self.once();v['retention_mode']='encrypted-fullraw'
        with self.assertRaises(m.GateError):m.validate_once_manifest(v,e,event,relation)
    def test_once_workflow_exact_branch_and_no_manual_main_requirement(self):
        text=(PATH.parents[1]/'.github/workflows/independent-m0-once.yml').read_text()
        self.assertIn('      - perf/approved-m0-20261117-04',text)
        self.assertNotIn('workflow_dispatch:',text)
        self.assertIn("github.event.before == '0000000000000000000000000000000000000000'",text)
        self.assertIn('github.event.created == true',text)
        self.assertIn('git',text);self.assertIn('manifest-only',text)
    def test_old_actual_registration_cannot_be_reused(self):
        e,event,relation=self.once_context()
        for old in ('independent-m0-20261117-once','independent-m0-20261117-02','independent-m0-20261117-03'):
            value=self.once();value['registration_id']=old
            with self.assertRaises(m.GateError):m.validate_once_manifest(value,e,event,relation)
    def test_old_actual_branch_cannot_be_recreated_for_new_registration(self):
        for old in ('refs/heads/perf/approved-m0-20261117-once','refs/heads/perf/approved-m0-20261117-02','refs/heads/perf/approved-m0-20261117-03'):
            e,event,relation=self.once_context();e['GITHUB_REF']=event['ref']=old
            with self.assertRaises(m.GateError):m.validate_once_manifest(self.once(),e,event,relation)
    def test_prep_has_no_metadata_process_or_sql(self):
        before={name for name in sys.modules if name=='uta' or name.startswith('uta.') or name=='sqlite3'}
        with patch.object(m,'source_snapshot',side_effect=AssertionError('source call')),patch.object(m,'collect_host',side_effect=AssertionError('host call')),patch.object(m.subprocess,'Popen',side_effect=AssertionError('spawn')),redirect_stdout(io.StringIO()) as output:
            self.assertEqual(m.main([]),0)
        self.assertEqual(before,{name for name in sys.modules if name=='uta' or name.startswith('uta.') or name=='sqlite3'})
        self.assertEqual(json.loads(output.getvalue())['status'],'PREP_ONLY')
    def test_rerun_of_same_dispatch_is_rejected(self):
        e=self.env();e['GITHUB_RUN_ATTEMPT']='2';self.reject(env=e)
    def test_frozen_stdlib_profile_metadata_is_supported(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/'stub.prof';p.write_bytes(marshal.dumps({('<frozen importlib._bootstrap>',1,'_find_and_load'):(1,1,.01,.02,{})}))
            result=m.profile_semantic(p);self.assertEqual(len(result['rows']),1)
    def test_exact_independent_dispatch_stub_pass(self):
        self.assertTrue(m.validate_dispatch(self.approval(),self.env(),self.actual(),'b'*64))
    def test_same_boot_rejected(self):
        a=self.actual();a['boot_id']=self.approval()['workspace_boot_id'];self.reject(actual=a)
    def test_same_host_rejected(self):
        a=self.actual();a['hostname_sha256']=self.approval()['workspace_hostname_sha256'];self.reject(actual=a)
    def test_selfhosted_rejected(self):
        e=self.env();e['RUNNER_ENVIRONMENT']='self-hosted';self.reject(env=e)
    def test_push_cannot_execute(self):
        e=self.env();e['GITHUB_EVENT_NAME']='push';self.reject(env=e)
    def test_control_commit_mismatch(self):
        e=self.env();e['GITHUB_SHA']='e'*40;self.reject(env=e)
    def test_controller_hash_mismatch(self):
        a=self.approval();a['controller_sha256']='e'*64;self.reject(approval=a)
    def test_source_not_floating_or_other_candidate(self):
        a=self.approval();a['source_commit']='f'*40;self.reject(approval=a)
    def test_reference_expired(self):
        a=self.approval();a['workspace_recorded_at']=(datetime.now(timezone.utc)-timedelta(seconds=901)).isoformat();self.reject(approval=a)
    def test_reference_future(self):
        a=self.approval();a['workspace_recorded_at']=(datetime.now(timezone.utc)+timedelta(seconds=30)).isoformat();self.reject(approval=a)
    def test_remote_and_memory_filesystems_rejected(self):
        for kind in ['nfs','nfs4','cifs','9p','tmpfs','ramfs','fuse.sshfs']:
            with self.subTest(kind=kind):
                a=self.actual();a['filesystem_type']=kind;self.reject(actual=a)
    def test_fresh_free_equality_and_lower_boundary(self):
        self.assertEqual(m.MIN_FREE,2348810240)
        self.assertEqual(m.LEGACY_MIN_FREE,2214592512)
        a=self.actual();a['free_bytes']-=1;self.reject(actual=a)
    def test_external_exchange_rejected(self):
        a=self.actual();a['network_external_exchange_configured']=True;self.reject(actual=a)
    def test_approval_extra_fields_rejected(self):
        a=self.approval();a['private_data']='synthetic-untrusted';self.reject(approval=a)
    def test_first_unknown_stops_before_profile(self):
        calls=[]
        rows=m.cases_sequence(lambda name,profile:(calls.append((name,profile)) or {'status':'UNKNOWN'}))
        self.assertEqual(calls,[('B',False)]);self.assertEqual(len(rows),1)
    def test_both_cases_are_serial_fixed_order(self):
        calls=[]
        rows=m.cases_sequence(lambda name,profile:(calls.append((name,profile)) or {'status':'PASS'}))
        self.assertEqual(calls,[('B',False),('P',True)]);self.assertEqual(len(rows),2)
    def test_actual_child_commands_only_profile_and_output_differ(self):
        a=m.child_argv(Path('/synthetic/source'),Path('/synthetic/B'),False)
        b=m.child_argv(Path('/synthetic/source'),Path('/synthetic/P'),True)
        self.assertEqual(b[-1],'--profile');b=b[:-1];b[b.index('/synthetic/P')]='/synthetic/B';self.assertEqual(a,b)
        self.assertEqual(a[a.index('--shards')+1],'2');self.assertEqual(a[a.index('--cpu-limit')+1],'1')
        self.assertNotIn('ordered_postings',' '.join(a))
    def test_child_environment_scrubs_provider_credentials(self):
        with patch.dict(os.environ,{'GITHUB_TOKEN':'STUB-NOT-A-REAL-TOKEN','ACTIONS_RUNTIME_TOKEN':'STUB-NOT-A-REAL-TOKEN'},clear=False):
            with m.child_environment(Path('/synthetic/tmp')):
                self.assertNotIn('GITHUB_TOKEN',os.environ);self.assertNotIn('ACTIONS_RUNTIME_TOKEN',os.environ)
                self.assertEqual(os.environ['TMPDIR'],'/synthetic/tmp')
            self.assertIn('GITHUB_TOKEN',os.environ)
    def test_duplicate_or_nonfinite_json_rejected(self):
        for raw in ['{"a":1,"a":2}','{"x":NaN}']:
            with self.assertRaises(m.GateError):m.strict_json(raw)
    def test_public_writer_rejects_path_escape(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(m.GateError):m.public_write(Path(tmp),'../private.json',{'x':1})
    def test_public_manifest_rejects_extra_files(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);r=m.public_write(root,'safe.json',{'count':1})
            m.public_write(root,'manifest.json',{'files':[r],'source_commit':m.SOURCE,'private_authorities_requests_keys_nonces_signatures_streams_not_uploaded':True})
            self.assertTrue(m.verify_public(root))
            (root/'extra.json').write_text('{}')
            with self.assertRaises(m.GateError):m.verify_public(root)
    def test_public_manifest_rejects_mutation(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);r=m.public_write(root,'safe.json',{'count':1})
            m.public_write(root,'manifest.json',{'files':[r],'source_commit':m.SOURCE,'private_authorities_requests_keys_nonces_signatures_streams_not_uploaded':True})
            (root/'safe.json').write_text('{}')
            with self.assertRaises(m.GateError):m.verify_public(root)
    def test_flat_tree_scan_is_bounded_per_entry(self):
        with TemporaryDirectory() as tmp:
            fake=SimpleNamespace(st_mode=stat.S_IFREG|0o600,st_size=0)
            directory=SimpleNamespace(st_mode=stat.S_IFDIR|0o700,st_size=0)
            entries=(SimpleNamespace(path=str(Path(tmp)/f'f{i}'),is_file=lambda **kwargs:True) for i in range(20001))
            with patch.object(m.os,'scandir',side_effect=lambda root:nullcontext(entries)),patch.object(Path,'lstat',lambda path:directory if path==Path(tmp) else fake):
                with self.assertRaisesRegex(m.GateError,'tree_entries_cap'):m.tree_bytes(Path(tmp))
    def test_profile_schema_has_only_function_counters_no_arguments(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/'stub.prof';p.write_bytes(marshal.dumps({('~',0,'<built-in method len>'):(1,1,.01,.02,{})}))
            result=m.profile_semantic(p)
            self.assertEqual(len(result['rows']),1);self.assertFalse(result['raw_binary_uploaded'])
    def test_profile_trailing_private_bytes_rejected(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/'stub.prof';p.write_bytes(marshal.dumps({})+b'STUB-PRIVATE-DATA')
            with self.assertRaises(m.GateError):m.profile_semantic(p)
    def test_profile_private_filename_rejected(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/'stub.prof';p.write_bytes(marshal.dumps({('/private/key.txt',1,'x'):(1,1,.01,.02,{})}))
            with self.assertRaises(m.GateError):m.profile_semantic(p)
    def test_profile_non_metadata_function_name_rejected(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp)/'stub.prof';p.write_bytes(marshal.dumps({('~',0,'nonce=STUB'):(1,1,.01,.02,{})}))
            with self.assertRaises(m.GateError):m.profile_semantic(p)
    def test_workflow_is_dispatch_only_and_upload_is_verified_public_only(self):
        text=(PATH.parents[1]/'.github/workflows/independent-m0.yml').read_text()
        self.assertIn('  workflow_dispatch:',text);self.assertNotIn('\n  push:',text);self.assertNotIn('\n  pull_request:',text)
        self.assertIn("steps.public_check.outcome == 'success'",text)
        upload=text.split('          path: |')[-1]
        self.assertIn('*.json',upload);self.assertIn('*.cms',upload);self.assertNotIn('/uta-m0-private-',upload)
        self.assertIn(m.SOURCE,text);self.assertIn('persist-credentials: false',text)

if __name__=='__main__':unittest.main()
