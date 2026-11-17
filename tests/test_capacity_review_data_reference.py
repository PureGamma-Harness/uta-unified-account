"""Pure independent artifact checks; no service, SQLite, load or runtime import."""
import importlib.util
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest

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


if __name__=='__main__': unittest.main()
