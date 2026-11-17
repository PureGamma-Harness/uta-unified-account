"""Read-only binding of the author's first fixed-source test; never runs tests."""
import ast
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess

ROOT = Path('/workspace/uta-deployment-preflight')
OUT = Path('/workspace/uta-deployment-preflight-private-20261117-parser-refusal-fixed')
FIXED = 'fb54a5aa0907e9113e1ead75bba93b05e9ad8899'
OLD = 'ebe9e28d3707042cb51ae8ca818a0d5cc1fe1fc2'
def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)
def read(path):
    before = path.stat()
    fd = os.open(path, os.O_RDONLY | os.O_NOATIME | os.O_NOFOLLOW)
    try:
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            data = stream.read()
    finally:
        os.close(fd)
    after = path.stat()
    assert all(getattr(before, k) == getattr(after, k) for k in ('st_ino', 'st_size', 'st_atime_ns', 'st_mtime_ns', 'st_ctime_ns'))
    return data
raw = {name: read(OUT / name) for name in ('plan.json', 'source-proof.json', 'result.json', 'run_fixed.py', 'stdout.txt', 'stderr.txt')}
plan, proof, result = (json.loads(raw[name]) for name in ('plan.json', 'source-proof.json', 'result.json'))
source = git('show', FIXED + ':tools/check_deployment_manifest.py')
old = git('show', OLD + ':tools/check_deployment_manifest.py')
funcs = lambda data: {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(data).body if isinstance(n, ast.FunctionDef)}
nf, of = funcs(source), funcs(old)
checks = {
    'same_process_source_identity_and_plan_hash': proof['source_commit'] == plan['source_commit'] == FIXED
        and proof['plan_sha256'] == sha256(raw['plan.json']).hexdigest(),
    'tool_and_tests_match_exact_fixed_git_blobs': all(proof['source_sha256'][name] == plan['source_sha256'][name]
        == sha256(git('show', FIXED + ':' + name)).hexdigest() for name in plan['source_sha256']),
    'fixed_tool_hash_exact': sha256(source).hexdigest() == '522899317db7b7d4a1a3369621cbf690a9ff553b45a908121f5ed55c64f63753',
    'only_load_manifest_function_changed': set(nf) == set(of)
        and all(nf[name] == of[name] for name in nf if name != 'load_manifest'),
    'specific_manifest_errors_preserved_before_generic_valueerror': source.index(b'except ManifestError:')
        < source.index(b'except (UnicodeDecodeError, ValueError, RecursionError)'),
    'manifest_path_checked_before_lstat': source.index(b'path = declared_path(str(path))') < source.index(b'details = path.lstat()'),
    'actual_import_paths_and_cpu_match': proof['tool_import_path'] == str(ROOT / 'tools/check_deployment_manifest.py')
        and proof['test_import_path'] == str(ROOT / 'tests/test_deployment_manifest.py')
        and proof['cpu_ids'] == plan['cpu_ids'] == [2],
    'actual_default_integer_limit_observed': proof['int_max_str_digits'] == 4300,
    'fixed_original_result_is_21_pass': type(result['tests_run']) is int and result['tests_run'] == 21
        and all(type(result[key]) is int and result[key] == 0 for key in ('failures', 'errors', 'skipped'))
        and result['passed'] is True and result['source_unchanged'] is True,
    'raw_stderr_confirms_21_pass': b'Ran 21 tests' in raw['stderr.txt'] and raw['stderr.txt'].endswith(b'\nOK\n')
        and raw['stderr.txt'].count(b' ... ok\n') == 21,
    'no_forbidden_api_or_referenced_body_read_reported': result['forbidden_api_calls'] == []
        and result['actual_secret_artifact_database_bodies_read'] is False
        and result['SQL_process_signal_denied_during_tests'] is True,
    'manifest_reads_are_bounded_and_fixed_result_not_production': result['fresh_manifest_read_count'] == 6
        and result['maximum_actual_manifest_bytes_read'] == 4512 and result['production_approved'] is False,
    'driver_hash_exact': sha256(raw['run_fixed.py']).hexdigest() == '6219a4d5dead40998f4e4afd1a962fd8c8da9ea46a7085342497ad2fac113a25',
    'no_product_runtime_or_service_unit_changed': not git('diff', '--name-only', '909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0', FIXED,
        '--', 'uta', 'deploy/uta.service', 'deploy/uta-durable.service'),
}
print(json.dumps({'reviewed_fixed_source': FIXED, 'checks': checks, 'all_checks': all(checks.values()),
    'author_first_original_hashes': {name: {'bytes': len(data), 'sha256': sha256(data).hexdigest()} for name, data in raw.items()},
    'first_red_retained': '679320943d8186260f07a4225afae0b2c2bee31c',
    'author_measured_test_interval_ns': result['elapsed_ns_before_result_write'],
    'scope': 'Read original first fixed-source result/proof/driver and Git/AST. Reviewer did not execute fixed tests.',
    'limits': ['No actual deployment, artifact digest, storage setting or approval authenticity validated.',
               'Original independent red has exception type/arguments but no captured full traceback.',
               'Patch denial is for listed known API calls, not a general capability sandbox.'],
    'production_approved': False}, indent=2, sort_keys=True))
assert all(checks.values())
