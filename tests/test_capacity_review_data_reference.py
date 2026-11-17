"""Pure independent artifact checks; no service, SQLite, load or runtime import."""
from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

PATH=Path(__file__).resolve().parents[1]/'evidence/runs/capacity-independent-review/recompute.py'
spec=importlib.util.spec_from_file_location('capacity_review_pure',PATH)
reference=importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)


class CapacityReviewDataTests(unittest.TestCase):
    def case_copy(self,root):
        return shutil.copytree(reference.ARCHIVE/'raw/py312/samecap-baseline',root/'case')

    def test_all_original_microcases_recompute_without_runtime_import(self):
        with TemporaryDirectory() as temporary:
            output=Path(temporary)/'report.json'
            reference.main(output)
            report=json.loads(output.read_text())
        self.assertEqual((report['raw_cases_checked'],report['financial_receipt_rows_checked']),(17,136))
        self.assertFalse(report['database_opened'])
        self.assertFalse(report['new_load_executed'])
        self.assertFalse(report['counterfactual_only_not_a_new_load']['composite_diagnostic_gate'])

    def test_underreported_tail_cannot_satisfy_exact_raw_rank(self):
        with self.assertRaises(AssertionError):
            reference.percentile_check([1_000_000,9_000_000],{'p50':1,'p95':1,'p99':1,'p99_9':1})

    def test_inflated_success_denominator_is_not_trusted_summary(self):
        with TemporaryDirectory() as temporary:
            case=self.case_copy(Path(temporary))
            summary=json.loads((case/'summary.json').read_text())
            summary['unique_observed_financial_success_per_s']*=2
            (case/'summary.json').write_text(json.dumps(summary))
            # Remove only this copied manifest's summary fingerprint to reach
            # independent numerical validation. Original evidence never changes.
            manifest=json.loads((case/'manifest.json').read_text())
            del manifest['files']['summary.json']
            (case/'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaises(AssertionError): reference.recompute_case(case)

    def test_acknowledgements_are_not_an_extra_financial_outcome(self):
        with TemporaryDirectory() as temporary:
            case=self.case_copy(Path(temporary))
            summary=json.loads((case/'summary.json').read_text())
            summary['outcome_counts']['durably_enqueued']=8
            (case/'summary.json').write_text(json.dumps(summary))
            manifest=json.loads((case/'manifest.json').read_text())
            del manifest['files']['summary.json']
            (case/'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaises(AssertionError): reference.recompute_case(case)

    def test_empty_latency_group_is_explicitly_unmeasured(self):
        values=reference.percentile_check([],{'p50':None,'p95':None,'p99':None,'p99_9':None})
        self.assertTrue(all(item['exact_nanoseconds'] is None for item in values.values()))
        with self.assertRaises(AssertionError):
            reference.percentile_check([],{'p50':0,'p95':None,'p99':None,'p99_9':None})


    def test_missing_pinned_original_material_is_rejected(self):
        for name in (reference.GENERATOR_FILE, 'provenance.json', reference.LICENSE_FILE):
            with self.subTest(missing=name), TemporaryDirectory() as temporary:
                historical=shutil.copytree(reference.HISTORICAL_SOURCE,Path(temporary)/'historical')
                (historical/name).unlink()
                with patch.object(reference,'HISTORICAL_SOURCE',historical):
                    with self.assertRaises(FileNotFoundError): reference.historical_source()

    def test_corrupt_original_generator_is_rejected_before_pure_gate(self):
        with TemporaryDirectory() as temporary:
            historical=shutil.copytree(reference.HISTORICAL_SOURCE,Path(temporary)/'historical')
            path=historical/reference.GENERATOR_FILE
            path.write_bytes(path.read_bytes()+b'\n')
            with patch.object(reference,'HISTORICAL_SOURCE',historical):
                with self.assertRaises(AssertionError): reference.observed_technical_gate({})

    def test_pinned_provenance_cannot_redirect_history_to_current_source(self):
        with TemporaryDirectory() as temporary:
            historical=shutil.copytree(reference.HISTORICAL_SOURCE,Path(temporary)/'historical')
            current=reference.ROOT/'benchmarks/run_managed_benchmark.py'
            path=historical/'provenance.json'
            value=json.loads(path.read_text())
            value['archived_generator_sha256']=sha256(current.read_bytes()).hexdigest()
            value['archived_source_commit']='8b7f544fcbdfd540d43de1d6560022c6ebbd3799'
            path.write_text(json.dumps(value))
            (historical/reference.GENERATOR_FILE).write_bytes(current.read_bytes())
            with patch.object(reference,'HISTORICAL_SOURCE',historical):
                with self.assertRaises(AssertionError): reference.historical_source()

    def test_raw_identity_cannot_claim_current_or_clean_source(self):
        environment=json.loads((reference.ARCHIVE/'raw/py312/samecap-baseline/environment.json').read_text())
        changes=[('generator_sha256',sha256((reference.ROOT/'benchmarks/run_managed_benchmark.py').read_bytes()).hexdigest()),
                 ('code_commit','8b7f544fcbdfd540d43de1d6560022c6ebbd3799'),
                 ('working_tree_dirty',False),('source_sha256',{})]
        for name,value in changes:
            with self.subTest(field=name):
                changed=deepcopy(environment);changed[name]=value
                with self.assertRaises(AssertionError): reference.historical_environment(changed)

    def test_no_git_replay_uses_pinned_source_when_current_generator_changes(self):
        with TemporaryDirectory() as temporary:
            root=Path(temporary)
            path=root/'evidence/runs/capacity-independent-review/recompute.py'
            path.parent.mkdir(parents=True)
            shutil.copyfile(PATH,path)
            shutil.copytree(reference.HISTORICAL_SOURCE,path.parent/'historical-source')
            shutil.copytree(reference.ARCHIVE,root/'docs/evidence/managed-variant-wiring-20261117')
            plan=root/'benchmarks/plans/20261117-managed-variants.json'
            plan.parent.mkdir(parents=True)
            shutil.copyfile(reference.ROOT/'benchmarks/plans/20261117-managed-variants.json',plan)
            # A future current generator is neither imported nor its gate used.
            (root/'benchmarks/run_managed_benchmark.py').write_text(
                'raise AssertionError("current generator must never be imported")\n'
                'def probe_qualification(summary):\n'
                '    raise AssertionError("current gate must never be executed")\n')
            self.assertFalse((root/'.git').exists())
            self.assertFalse((root/'uta').exists())
            spec=importlib.util.spec_from_file_location('capacity_review_offline',path)
            offline=importlib.util.module_from_spec(spec);spec.loader.exec_module(offline)
            output=root/'report.json';offline.main(output)
            report=json.loads(output.read_text())
            self.assertEqual((report['raw_cases_checked'],report['financial_receipt_rows_checked']),(17,136))
            self.assertEqual(report['archived_generator_identity']['sha256'],reference.GENERATOR_SHA256)
            self.assertIs(report['archived_generator_identity']['recorded_raw_working_tree_dirty'],True)
            self.assertFalse(report['counterfactual_only_not_a_new_load']['composite_diagnostic_gate'])
            self.assertFalse(report['database_opened'])


if __name__=='__main__': unittest.main()
