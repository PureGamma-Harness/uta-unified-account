"""Archive already downloaded public CI evidence; never runs test or SQL code."""
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import zipfile

SOURCE = Path('/workspace/uta-observer-freeze-d421df3')
DOWNLOADS = Path('/workspace/uta-ci-d421-all')
OUTPUT = Path('/workspace/uta-observer-delivery/evidence/runs/observer-qa-d421df3')
SHA = 'd421df3fc5123e8267f0eecf8bb5efdc37cd0dc6'
MERGE = '7114617951b6b4e4313c19439f853fdd115e35d0'
OUTPUT.mkdir(parents=True, exist_ok=False)
records = []
for run, metadata_name in ((44085180665, 'push'), (44085188612, 'pr')):
    provider = next(x for x in json.loads((DOWNLOADS / 'provider-artifacts.json').read_text()) if x['run'] == run)
    selected = {item['name']: item for item in provider['artifacts'] if not item['name'].startswith('uta-wheel')}
    assert len(selected) == 7
    for name, item in sorted(selected.items()):
        original = DOWNLOADS / str(run) / (name + '.zip')
        raw = original.read_bytes()
        assert len(raw) == item['size_in_bytes']
        assert 'sha256:' + sha256(raw).hexdigest() == item['digest']
        target = OUTPUT / 'ci' / str(run) / name
        target.mkdir(parents=True)
        with zipfile.ZipFile(original) as archive:
            assert archive.testzip() is None
            names = archive.namelist()
            assert len(names) == len(set(names))
            assert all(not PurePosixPath(n).is_absolute() and '..' not in PurePosixPath(n).parts for n in names)
            if name.startswith('uta-unit-'):
                assert set(names) == {'summary.json', 'worker-result.json', 'unittest.txt'}
                report = json.loads(archive.read('summary.json'))
                worker = json.loads(archive.read('worker-result.json'))
                assert report['code_commit'] == (SHA if metadata_name == 'push' else MERGE)
                assert report['source_unchanged'] and report['source_sha256'] == report['source_sha256_after']
                assert len(report['source_sha256']) == 252
                assert all(sha256((SOURCE / path).read_bytes()).hexdigest() == digest for path, digest in report['source_sha256'].items())
                assert sha256(archive.read('unittest.txt')).hexdigest() == report['test_log_sha256']
                for key in ('tests_run', 'failures', 'errors', 'skipped', 'unittest_passed'):
                    assert report[key] == worker[key]
                failures = 2 if metadata_name == 'pr' and name.endswith('3.13') else 0
                errors = 1 if metadata_name == 'push' and name.endswith('3.11') else 0
                assert (report['tests_run'], report['failures'], report['errors'], report['skipped']) == (1413, failures, errors, 0)
                assert report['passed'] is (not failures and not errors)
                outcome = {key: report[key] for key in ('code_commit', 'tests_run', 'failures', 'errors', 'skipped', 'passed')}
            else:
                assert len(names) == 19
                assert set(names) == {'uta-package-artifact-manifest.json', 'uta-installed-validation/installed-report.json', 'uta-installed-validation/installed-cli-tests.txt'} | {
                    'uta-installed-validation/' + command + '.' + stream + '.txt'
                    for command in ('uta-acceptance', 'uta-demo', 'uta-durable---help', 'uta-durable-init', 'uta-durable-inspect', 'uta-durable-status', 'uta-ops---help', 'uta-scenario')
                    for stream in ('stdout', 'stderr')}
                report = json.loads(archive.read('uta-package-artifact-manifest.json'))
                installed = json.loads(archive.read('uta-installed-validation/installed-report.json'))
                assert report['source_commit'] == installed['source_commit'] == (SHA if metadata_name == 'push' else MERGE)
                assert report['passed'] is installed['passed'] is True
                assert len(report['sdist_required_files']) == 2753 and len(report['runtime_files']) == 52
                assert installed['tests'] == {'run': 8, 'errors': 0, 'failures': 0, 'skipped': 0} and installed['expected_tests'] == 8
                outcome = {'source_commit': report['source_commit'], 'package_passed': True, 'installed_passed': True, 'tracked_files': 2753, 'runtime_files': 52, 'installed_tests': 8}
            members = []
            for member in names:
                data = archive.read(member)
                path = target / member
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                members.append({'path': str(path.relative_to(OUTPUT)), 'bytes': len(data), 'sha256': sha256(data).hexdigest()})
        records.append({'provider': item, 'download_sha256': sha256(raw).hexdigest(), 'outcome': outcome, 'members': members})
(OUTPUT / 'index.json').write_text(json.dumps({'candidate_source_commit': SHA, 'actual_pr_validation_commit': MERGE,
    'pr_validation_and_head_full_tree': 'b16694a163e0483b843dbeaa41d39d0e7ddf5017', 'artifacts': records,
    'ci_jobs_successful': 6, 'ci_jobs_failed': 2, 'candidate_accepted': False,
    'reason': 'Push Python3.11 retains one actual stale activation ERROR; PR Python3.13 retains two readiness FAILs.',
    'production_approved': False}, indent=2, sort_keys=True) + '\n')
print(json.dumps({'artifacts': len(records), 'members': sum(len(x['members']) for x in records), 'candidate_accepted': False}))
