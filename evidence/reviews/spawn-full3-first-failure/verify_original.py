"""Read first-run evidence with O_NOATIME; no UTA import, SQL, test or signal."""
import ast
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess

REPO = Path('/workspace/uta-spawn-full3-clean')
EVIDENCE = '8ad9bf67e8890489b5276a319b7e41845a5c4b7b'
SOURCE = '6b7d473c0fbf92b17c146140c88eb2c25d38dce1'
PREFIX = 'evidence/plans/spawn-recovery-full3/first-execution-no-go/'
PRIVATE = Path('/workspace/uta-spawn-full3-validation/6b7d473-first')
def git(*args):
    return subprocess.check_output(['git', *args], cwd=REPO)
def blob(name):
    return git('show', EVIDENCE + ':' + PREFIX + name)
def load(name):
    return json.loads(blob(name))
def noatime(path):
    before = path.stat()
    fd = os.open(path, os.O_RDONLY | os.O_NOATIME | os.O_NOFOLLOW)
    try:
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            data = stream.read()
    finally:
        os.close(fd)
    after = path.stat()
    assert (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns,
            before.st_atime_ns) == (after.st_ino, after.st_size, after.st_mtime_ns,
                                   after.st_ctime_ns, after.st_atime_ns)
    return data

manifest = load('manifest.json')['files']
manifest_ok, private_compared = [], []
for name, row in manifest.items():
    data = blob(name)
    manifest_ok.append(len(data) == row['bytes'] and sha256(data).hexdigest() == row['sha256'])
    if (PRIVATE / name).is_file():
        private_compared.append({'name': name, 'bytes_equal': noatime(PRIVATE / name) == data})
provenance = load('raw-provenance.json')
raw = noatime(PRIVATE / 'python310/unittest.txt')
lines = raw.splitlines(keepends=True)
sections = [b''.join(lines[row['first_line'] - 1:row['last_line']])
            for row in provenance['error_sections']]
paths = [match.decode() for section in sections for match in re.findall(
    rb"FileNotFoundError: \[Errno 2\] No such file or directory: '/workspace/uta-stopped-owner-gate/([^']+)'", section)]
tracked = set(git('ls-tree', '-r', '--name-only', SOURCE).decode().splitlines())
module = ast.parse(git('show', SOURCE + ':tests/test_capacity_review_data_reference.py'))
module_cases = [node.name for node in ast.walk(module)
                if isinstance(node, ast.FunctionDef) and node.name.startswith('test_')]
summary, worker, outer = load('python310/summary.json'), load('python310/worker-result.json'), load('python310-first-outcome.json')
matrix, end, post = load('matrix-summary.json'), load('matrix-end.json'), load('matrix-post-end.json')
launch, exited = load('supervisor-launch.json')['identity'], load('actual-supervisor-exit-first.json')
checks = {
    'all_archived_metadata_match_manifest': all(manifest_ok),
    'all_compared_private_originals_equal_git_bytes_without_atime_change': all(row['bytes_equal'] for row in private_compared),
    'complete_raw_bytes_and_sha_match_provenance': len(raw) == provenance['original_raw_bytes'] == 260921
        and sha256(raw).hexdigest() == provenance['original_raw_sha256']
        == 'fe173f0d54c176c4cd1d47e64e37d7f75b08d943b4eb89ad89aad1f29662db81',
    'sixteen_sections_match_original_line_range_hashes': len(sections) == 16 and all(
        sha256(data).hexdigest() == row['sha256'] for data, row in zip(sections, provenance['error_sections'])),
    'all_reported_errors_have_exactly_one_missing_public_tracked_input': len(paths) == 16
        and all(path in tracked and path.startswith(('docs/', 'evidence/')) for path in paths),
    'actual_raw_footer_is_failed_1804_errors16': b'Ran 1804 tests in 408.835s\n\nFAILED (errors=16)' in raw
        and sum(line.startswith(b'ERROR: ') for line in lines) == 16,
    'summary_and_worker_agree_on_failed_counts': all(summary[key] == worker[key] == value
        for key, value in {'tests_run': 1804, 'failures': 0, 'errors': 16, 'skipped': 0,
                           'expected_failures': 0, 'unexpected_successes': 0}.items())
        and summary['passed'] is False and worker['unittest_passed'] is False,
    'missing_import_module_ten_cases_explains_nine_count_difference': len(module_cases) == 10
        and sections[0].startswith(b'ERROR: test_capacity_review_data_reference (unittest.loader._FailedTest)')
        and 1813 - summary['tests_run'] == len(module_cases) - 1,
    'first_outer_result_failed_normally_without_watchdog': outer['outcome'] == 'FAIL'
        and outer['exit_code'] == 1 and outer['watchdog_reason'] is None
        and outer['leader_reaped'] is True and outer['source_and_binary_unchanged'] is True,
    'later_runtimes_not_started_in_records_or_private_files': len(matrix['records']) == 1
        and matrix['records'][0]['label'] == 'python310'
        and not any((PRIVATE / label).exists() for label in ('python312', 'python313-sqlite346')),
    'actual_supervisor_birth_boot_and_exit1_match_saved_launch': all(exited[key] == launch[key]
        for key in ('pid', 'birth_ticks', 'boot_id')) and exited['state'] == 'Z'
        and exited['parent'] == 1 and exited['linux_encoded_exit_status'] == 256 and exited['exit_code'] == 1,
    'end_and_post_end_never_claim_complete_pass': matrix['all_three_first_full_runs_passed'] is False
        and end['all_three_first_full_runs_passed'] is False and end['outcome'] == 'UNKNOWN'
        and post['planned_exit_code'] == 1,
}
print(json.dumps({'evidence_commit': EVIDENCE, 'source_commit': SOURCE, 'checks': checks,
    'all_checks': all(checks.values()), 'archived_metadata_files': len(manifest_ok),
    'private_originals_compared_noatime': private_compared,
    'missing_input_paths_with_multiplicity': paths, 'module_test_methods': module_cases,
    'scope': 'Observed 16 errors attributable to missing public tracked inputs; no claim about unexecuted cases or old CI cause.',
    'raw_sha256': sha256(raw).hexdigest(), 'new_sql_test_signal_or_qa_execution': False,
    'result': 'FIRST_FULL3_FAIL_RETAINED', 'production_approved': False}, indent=2, sort_keys=True))
assert all(checks.values())
