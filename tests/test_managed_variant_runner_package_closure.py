"""RUN-R5 pure archive/report controls. No package build/install or verifier run."""
from copy import deepcopy
import json
import io
import tarfile
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import zipfile

from tools import run_managed_variants as runner
from tests.runner_package_fixtures import create_package_evidence,facts,reference,save
from tests.test_managed_variant_runner import COMMIT


class RunnerPackageOmissionClosureTests(unittest.TestCase):
    def fixture(self,root):
        hashes,package=create_package_evidence(root,COMMIT)
        return hashes,package,runner.proof(package['archives'])

    def check(self,hashes,package,archives):
        runner.omission_binding(package,archives,hashes,COMMIT)

    def test_new_positive_physical_packages_and_four_exact_omissions_are_accepted(self):
        with TemporaryDirectory() as temporary:
            hashes,package,archives=self.fixture(Path(temporary))
            self.check(hashes,package,archives)
            self.assertEqual(len(runner.proof(package['runtime_controls'])['cases']),2)
            self.assertEqual(len(runner.proof(package['zip_controls'])['omission_controls']),2)

    def test_original_archive_size_and_SHA_must_equal_the_qualified_manifest(self):
        for field,bad in [('bytes',1),('sha256','f'*64)]:
            with TemporaryDirectory() as temporary,self.subTest(field=field):
                hashes,package,archives=self.fixture(Path(temporary))
                name=Path(package['artifact_files']['wheel']['path']).name
                archives['artifacts'][name][field]=bad
                with self.assertRaisesRegex(runner.GateError,'original wheel/sdist SHA or size'):
                    self.check(hashes,package,archives)

    def test_different_version_wheel_still_containing_removable_member_is_rejected(self):
        with TemporaryDirectory() as temporary:
            root=Path(temporary);hashes,package,archives=self.fixture(root)
            original=Path(package['artifact_files']['wheel']['path']);old=root/'fixture-0.4.0a1.whl'
            with zipfile.ZipFile(original) as source,zipfile.ZipFile(old,'w') as target:
                for item in source.infolist():
                    data=source.read(item.filename)
                    if item.filename.endswith('/METADATA'):data=data.replace(b'0.5.0a1',b'0.4.0a1')
                    target.writestr(item,data)
            with zipfile.ZipFile(old) as source:self.assertIn('uta/failure_diagnostics.py',source.namelist())
            package['artifact_files']['wheel']=reference(old)
            with self.assertRaisesRegex(runner.GateError,'original wheel/sdist SHA or size'):
                self.check(hashes,package,archives)

    def test_extra_false_checks_cannot_pass_either_runtime_direction(self):
        for direction,index,extra in [('wheel',0,'version'),('sdist',1,'wheel_runtime_exact')]:
            with TemporaryDirectory() as temporary,self.subTest(direction=direction):
                root=Path(temporary);hashes,package,archives=self.fixture(root)
                collector=runner.proof(package['runtime_controls'])
                collector['cases'][index]['checks'][extra]=False
                package['runtime_controls']=save(root/'controls-extra-false.json',collector)
                report=runner.proof(package['runtime_reports'][direction]);report['checks'][extra]=False
                package['runtime_reports'][direction]=save(root/'report-extra-false.json',report)
                self.assertTrue(collector['cases'][index]['passed'])
                self.assertEqual(collector['cases'][index]['returncode'],1)
                with self.assertRaisesRegex(runner.GateError,'full check matrix'):
                    self.check(hashes,package,archives)

    def test_report_cannot_claim_a_different_unmodified_positive_side(self):
        with TemporaryDirectory() as temporary:
            root=Path(temporary);hashes,package,archives=self.fixture(root)
            report=runner.proof(package['runtime_reports']['wheel'])
            sdist=Path(package['artifact_files']['sdist']['path']).name
            report['artifacts'][sdist]['sha256']='0'*64
            package['runtime_reports']['wheel']=save(root/'report-wrong-other-input.json',report)
            with self.assertRaisesRegex(runner.GateError,'actual two input artifacts'):
                self.check(hashes,package,archives)

    def test_negative_archives_cannot_modify_another_member_despite_consistent_hashes_and_labels(self):
        for kind,index in [('wheel',0),('sdist',1)]:
            with TemporaryDirectory() as temporary,self.subTest(kind=kind):
                root=Path(temporary);hashes,package,archives=self.fixture(root)
                collector=runner.proof(package['runtime_controls']);case=collector['cases'][index]
                negative=Path(case['argv'][7 if kind=='wheel' else 9])
                replacement=root/('replacement.whl' if kind=='wheel' else 'replacement.tar.gz')
                if kind=='wheel':
                    with zipfile.ZipFile(negative) as source,zipfile.ZipFile(replacement,'w') as target:
                        for item in source.infolist():
                            data=source.read(item.filename)
                            if item.filename=='uta/__init__.py':data+=b'# unintended change\n'
                            target.writestr(item,data)
                else:
                    with tarfile.open(negative) as source,tarfile.open(replacement,'w:gz') as target:
                        for item in source.getmembers():
                            data=source.extractfile(item).read() if item.isfile() else None
                            if item.name.endswith('/uta/__init__.py'):
                                data+=b'# unintended change\n';item.size=len(data)
                            target.addfile(item,io.BytesIO(data) if data is not None else None)
                replacement.replace(negative)
                case['negative_archive_sha256']=facts(negative)['sha256']
                package['runtime_controls']=save(root/'controls-modified-member.json',collector)
                report=runner.proof(package['runtime_reports'][kind])
                report['artifacts'][negative.name]=facts(negative)
                package['runtime_reports'][kind]=save(root/'report-modified-member.json',report)
                with self.assertRaisesRegex(runner.GateError,'beyond the single removed target'):
                    self.check(hashes,package,archives)

    def test_verifier_argv_and_all_tracked_ZIP_negative_reports_are_required(self):
        for mutation in ('verifier','ZIP report'):
            with TemporaryDirectory() as temporary,self.subTest(mutation=mutation):
                root=Path(temporary);hashes,package,archives=self.fixture(root)
                if mutation=='verifier':
                    controls=runner.proof(package['runtime_controls']);controls['cases'][0]['argv'][1]='/different/verifier.py'
                    package['runtime_controls']=save(root/'controls-wrong-verifier.json',controls)
                else:
                    del package['zip_reports']['evidence/ci-b.zip']
                with self.assertRaises(runner.GateError):self.check(hashes,package,archives)

    def test_boolean_exit_or_removed_count_is_not_actual_integer_rejection_evidence(self):
        for field in ('returncode','removed_count'):
            with TemporaryDirectory() as temporary,self.subTest(field=field):
                root=Path(temporary);hashes,package,archives=self.fixture(root)
                controls=runner.proof(package['runtime_controls']);controls['cases'][0][field]=True
                package['runtime_controls']=save(root/'controls-boolean-count.json',controls)
                with self.assertRaisesRegex(runner.GateError,'actual rejection'):
                    self.check(hashes,package,archives)


if __name__=='__main__':
    unittest.main(verbosity=2)
