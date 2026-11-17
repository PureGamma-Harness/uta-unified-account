"""Strict JSON integer domains and terminal identity; pure data only."""
from copy import deepcopy
import gzip
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools import run_managed_variants as runner
from tests.test_managed_variant_runner import COMMIT,raw_fixture


def rehash(directory):
    path=directory/'manifest.json';value=json.loads(path.read_text())
    for name in value['files']:
        content=(directory/name).read_bytes()
        value['files'][name]={'bytes':len(content),'sha256':runner.sha256(content).hexdigest()}
    path.write_text(json.dumps(value)+'\n')


def edit_rows(directory,change):
    path=directory/'arrivals.jsonl.gz'
    rows=[json.loads(line) for line in gzip.decompress(path.read_bytes()).splitlines()]
    change(rows)
    path.write_bytes(gzip.compress(('\n'.join(json.dumps(row) for row in rows)+'\n').encode(),mtime=0))
    rehash(directory)


class RunnerRawContractTests(unittest.TestCase):
    def test_all_raw_nanoseconds_reject_float_and_bool_before_arithmetic(self):
        fields=('planned_ns','offered_ns','enqueue_started_ns','enqueue_ack_ns','enqueue_call_finished_ns',
                'observed_completion_ns','latency_ns')
        for field in fields:
            for conversion in (float,lambda _:False):
                with TemporaryDirectory() as temporary,self.subTest(field=field,conversion=conversion):
                    directory=Path(temporary);hashes=raw_fixture(directory)
                    edit_rows(directory,lambda rows:rows[0].__setitem__(field,conversion(rows[0][field])))
                    with self.assertRaisesRegex(runner.GateError,'invalid integer'):
                        runner.recompute(directory,runner.schedule()[0],hashes,COMMIT)

    def test_boolean_and_float_sequences_cannot_construct_alternate_canonical_IDs(self):
        for value in (True,1.0):
            with TemporaryDirectory() as temporary,self.subTest(value=value):
                directory=Path(temporary);hashes=raw_fixture(directory)
                def change(rows):
                    rows[1]['sequence']=value
                    rows[1]['command_id']=rows[1]['receipt']['command_id']='bench:'+str(value)
                    rows[1]['order_id']='order:'+str(value)
                edit_rows(directory,change)
                with self.assertRaisesRegex(runner.GateError,'arrival sequence'):
                    runner.recompute(directory,runner.schedule()[0],hashes,COMMIT)
        with TemporaryDirectory() as temporary:
            directory=Path(temporary);hashes=raw_fixture(directory)
            edit_rows(directory,lambda rows:rows[0]['receipt'].__setitem__('sequence',True))
            with self.assertRaisesRegex(runner.GateError,'invalid integer'):
                runner.recompute(directory,runner.schedule()[0],hashes,COMMIT)

    def test_every_receipt_state_binds_original_CID_and_account_before_classification(self):
        for state,index in [('SUCCEEDED',0),('REJECTED',9),('QUARANTINED',9),('PENDING',9)]:
            with TemporaryDirectory() as temporary,self.subTest(state=state):
                directory=Path(temporary);hashes=raw_fixture(directory)
                def change(rows):
                    rows[index]['receipt'].update(state=state,command_id='different-CID',account_id='different-account')
                edit_rows(directory,change)
                with self.assertRaisesRegex(runner.GateError,'receipt identity for original arrival'):
                    runner.recompute(directory,runner.schedule()[0],hashes,COMMIT)
                # The original business label is retained for unqualified
                # forensic counts; the checker never changes it to technical.
                forensic=runner.forensic_counts(directory)
                self.assertEqual(forensic['counts']['business_rejected'],20)
                self.assertFalse(forensic['financial_verified'])

    def test_consumed_counts_and_timing_anchors_reject_numeric_aliases(self):
        mutations=[('summary.json',['counts','financial_success_late'],False),
            ('summary.json',['counts','financial_succeeded'],180.0),
            ('summary.json',['outcome_counts','business_rejected'],20.0),
            ('summary.json',['command_technical_diagnostics','nonterminal_commands'],False),
            ('summary.json',['batch_dispatch_diagnostics','recovered_batches'],False),
            ('summary.json',['readonly_reconciliation','pending_count'],False),
            ('summary.json',['readonly_reconciliation','shards',0,'confirmed_matches'],False),
            ('summary.json',['actual_spawned_worker_inputs',0,'received_settings','financial_batch_size'],False),
            ('summary.json',['offered'],200.0),
            ('measurement-footer.json',['timing_contract_version'],True),
            ('measurement-footer.json',['planned_duration_ns'],10_000_000_000.0),
            ('arrival-window.json',['planned_start_monotonic_ns'],1_000_000_000_000.0)]
        for filename,keys,bad in mutations:
            with TemporaryDirectory() as temporary,self.subTest(path=keys):
                directory=Path(temporary);hashes=raw_fixture(directory)
                path=directory/filename;value=json.loads(path.read_text());target=value
                for key in keys[:-1]:target=target[key]
                target[keys[-1]]=bad;path.write_text(json.dumps(value)+'\n');rehash(directory)
                with self.assertRaisesRegex(runner.GateError,'invalid integer'):
                    runner.recompute(directory,runner.schedule()[0],hashes,COMMIT)

    def test_unqualified_forensic_footer_also_requires_integer_anchors(self):
        with TemporaryDirectory() as temporary:
            directory=Path(temporary);raw_fixture(directory)
            path=directory/'measurement-footer.json';footer=json.loads(path.read_text())
            footer['started_monotonic_ns']=float(footer['started_monotonic_ns'])
            footer['terminal_observation_finished_monotonic_ns']=float(footer['terminal_observation_finished_monotonic_ns'])
            path.write_text(json.dumps(footer)+'\n')
            with self.assertRaisesRegex(runner.GateError,'invalid integer'):
                runner.forensic_counts(directory)

    def test_valid_business_rejections_keep_the_original_outcome_mix_and_green_gate(self):
        with TemporaryDirectory() as temporary:
            directory=Path(temporary);hashes=raw_fixture(directory)
            result=runner.recompute(directory,runner.schedule()[0],hashes,COMMIT)
            self.assertEqual(result['counts'],{'financial_succeeded':180,'business_rejected':20})
            self.assertTrue(result['technical_and_deadline_passed'])
            self.assertNotIn('technical_quarantined',result['counts'])
            self.assertEqual(result['groups']['all']['N'],200)
            self.assertEqual(result['denominator_ns'],10_000_000_000)


if __name__=='__main__':
    unittest.main(verbosity=2)
