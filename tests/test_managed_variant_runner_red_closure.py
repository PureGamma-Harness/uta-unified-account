"""Independent red invariants, new synthetic controls, and one owned CPU dummy.

No benchmark, service, SQL, long job or old artifact is executed here.
"""
from copy import deepcopy
import gzip
import io
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tools import run_managed_variants as runner
from tests.test_managed_variant_runner import COMMIT, raw_fixture


class BinaryReadProbe(io.BytesIO):
    def __init__(self, content):
        super().__init__(content)
        self.read_sizes = []

    def readline(self, size=-1):
        if not 0 < size <= 65537:
            raise AssertionError('unbounded or overlarge decompressed read')
        self.read_sizes.append(size)
        if len(self.read_sizes) > 201:
            raise AssertionError('reader attempted arrival202 before rejecting extra row')
        return super().readline(size)


class RunnerRedDataClosureTests(unittest.TestCase):
    def refresh_manifest(self, directory):
        path = directory/'manifest.json'
        value=json.loads(path.read_text())
        for name in value['files']:
            item=directory/name
            value['files'][name]={'bytes':item.stat().st_size,'sha256':runner.digest(item)}
        path.write_text(json.dumps(value)+'\n')

    def test_RUN_R2_raw_late_success_is_red_even_with_consistently_hashed_green_flag(self):
        with TemporaryDirectory() as temporary:
            directory=Path(temporary);hashes=raw_fixture(directory,late=True)
            path=directory/'summary.json';data=json.loads(path.read_text())
            data['probe_qualification']['financial_soft_deadline_passed']=True
            path.write_text(json.dumps(data)+'\n');self.refresh_manifest(directory)
            result=runner.recompute(directory,runner.schedule()[0],hashes,COMMIT)
            self.assertEqual(result['financial_success_late'],1)
            self.assertFalse(result['technical_and_deadline_passed'])
            self.assertIn('raw_financial_success_late',result['stop_reasons'])
            self.assertIn('summary_deadline_flag_contradicts_raw',result['stop_reasons'])
            self.assertEqual(result['groups']['financial_succeeded']['max_ns'],2_000_000_000)

    def test_RUN_R3_each_consumed_original_requires_manifest_membership(self):
        for missing in ('summary.json','arrival-window.json','arrivals.jsonl.gz','measurement-footer.json'):
            with TemporaryDirectory() as temporary,self.subTest(missing=missing):
                directory=Path(temporary);hashes=raw_fixture(directory)
                path=directory/'manifest.json';data=json.loads(path.read_text());del data['files'][missing]
                path.write_text(json.dumps(data)+'\n')
                with self.assertRaisesRegex(runner.GateError,'missing from manifest'):
                    runner.recompute(directory,runner.schedule()[0],hashes,COMMIT)

    def test_RUN_R3_consumed_JSON_and_gzip_are_the_exact_verified_bytes(self):
        with TemporaryDirectory() as temporary:
            directory=Path(temporary);hashes=raw_fixture(directory)
            path=directory/'summary.json';path.write_bytes(path.read_bytes()+b' ')
            with self.assertRaisesRegex(runner.GateError,'consumed original hash mismatch'):
                runner.recompute(directory,runner.schedule()[0],hashes,COMMIT)

    def test_RUN_R4_excess_row_is_rejected_on_the_201st_bounded_read(self):
        with TemporaryDirectory() as temporary:
            directory=Path(temporary);hashes=raw_fixture(directory)
            content=gzip.decompress((directory/'arrivals.jsonl.gz').read_bytes())
            probe=BinaryReadProbe(content+content.splitlines(keepends=True)[0])
            with patch.object(runner.gzip,'open',return_value=probe):
                with self.assertRaisesRegex(runner.GateError,'arrival count exceeds plan'):
                    runner.recompute(directory,runner.schedule()[0],hashes,COMMIT)
            self.assertEqual(len(probe.read_sizes),201)

    def test_RUN_R4_line_and_total_bytes_are_bounded_before_JSON_decode(self):
        for content,total,reads in ((b'"'+b'x'*65536+b'"\n',8*runner.MiB,1),
                                   (b'{"x":1}\n'*4,15,2)):
            probe=BinaryReadProbe(content)
            with self.subTest(total=total),patch.object(runner.gzip,'open',return_value=probe):
                with self.assertRaisesRegex(runner.GateError,'byte bound exceeded'):
                    runner.bounded_arrivals('/unused',maximum_total_bytes=total)
            self.assertEqual(len(probe.read_sizes),reads)

    def test_untampered_control_still_has_literal_counts_and_real_footer_denominator(self):
        with TemporaryDirectory() as temporary:
            directory=Path(temporary);hashes=raw_fixture(directory)
            result=runner.recompute(directory,runner.schedule()[0],hashes,COMMIT)
            self.assertTrue(result['technical_and_deadline_passed'])
            self.assertEqual(result['groups']['financial_succeeded']['N'],180)
            self.assertEqual(result['groups']['financial_succeeded']['max_ns'],1_000_000)
            self.assertEqual(result['denominator_ns'],10_000_000_000)
            self.assertEqual(result['financial_per_second'],18.)


class RunnerAffinityClosureTests(unittest.TestCase):
    def test_RUN_R1_real_launcher_ack_precedes_kernel_affinity_assertion(self):
        before=sorted(os.sched_getaffinity(0));child=[min(before)]
        parent_birth=runner.process_identity(os.getpid())['birth_ticks']
        with TemporaryDirectory() as temporary:
            directory=Path(temporary)
            result=runner.owned_run([sys.executable,'-c','import json,os;print(json.dumps(sorted(os.sched_getaffinity(0))))'],
                directory,directory/'affinity',cpu_ids=child,wall_seconds=2,grace_seconds=.1,
                kill_wait_seconds=.5,output_cap=4096,protected={os.getpid()})
            self.assertEqual(result['returncode'],0)
            self.assertEqual(result['outcome'],'EXITED')
            self.assertTrue(result['launcher_affinity_acknowledged'])
            self.assertEqual(result['observed_child_cpu_ids'],child)
            self.assertEqual(json.loads((directory/'affinity.stdout').read_text()),child)
            self.assertEqual(sorted(os.sched_getaffinity(0)),before)
            self.assertEqual(runner.process_identity(os.getpid())['birth_ticks'],parent_birth)
            evidence=os.environ.get('UTA_RUNNER_RED_CLOSURE_EVIDENCE')
            if evidence:
                import shutil
                output=Path(evidence);output.mkdir(parents=True,exist_ok=False)
                for path in directory.glob('affinity.*'):
                    shutil.copy2(path,output/(path.name+('.txt' if path.suffix in ('.stdout','.stderr') else '')))
                (output/'result.json').write_text(json.dumps({'parent_cpu_ids':before,'requested_cpu_ids':child,
                    'parent_birth_unchanged':True,'child':result,'scope':'owned print-only dummy; no financial runtime'},indent=2)+'\n')


if __name__=='__main__':
    unittest.main(verbosity=2)
