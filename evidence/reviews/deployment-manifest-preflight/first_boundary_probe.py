"""Small fresh synthetic boundary probe; no SQL/network/worker/child process."""
from contextlib import redirect_stdout
from hashlib import sha256
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from time import perf_counter_ns
from unittest.mock import patch

SOURCE = Path('/workspace/uta-deployment-preflight/tools/check_deployment_manifest.py')
started = perf_counter_ns()
source_bytes = SOURCE.read_bytes()
spec = importlib.util.spec_from_file_location('review_offline_manifest', SOURCE)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)
assert os.sched_getaffinity(0) == {3}
path_cases = []
for suffix, expected in (('/bad\x00name', 'path_nul_refused'),
                         ('/bad\ud800name', 'path_utf8_required')):
    with patch.object(Path, 'read_bytes', side_effect=AssertionError('role content read forbidden')), \
            patch.object(Path, 'lstat', side_effect=AssertionError('malformed role path reached metadata')):
        try:
            check.declared_path('/synthetic-review-root' + suffix)
        except check.ManifestError as error:
            path_cases.append({'expected': expected, 'actual': str(error), 'passed': str(error) == expected})
        else:
            raise AssertionError('malformed synthetic role path accepted')

original_read = Path.read_bytes
with TemporaryDirectory(prefix='uta-independent-preflight-') as directory:
    manifest = Path(directory) / 'oversized-number.json'
    body = b'{"format":' + b'1' * 4501 + b'}'
    manifest.write_bytes(body)
    contents_read = []
    def only_synthetic_manifest(path):
        assert path == manifest, 'referenced content read forbidden'
        contents_read.append('new-synthetic-manifest-only')
        return original_read(path)
    capture = io.StringIO()
    result, failure = None, None
    with redirect_stdout(capture), patch.object(Path, 'read_bytes', only_synthetic_manifest), \
            patch.object(check, 'metadata', side_effect=AssertionError('referenced role metadata forbidden')):
        try:
            result = check.main(['--manifest', str(manifest)])
        except BaseException as error:
            failure = {'type': type(error).__module__ + '.' + type(error).__name__,
                       'args': list(error.args)}
    number_case = {'synthetic_manifest_bytes': len(body), 'integer_digits': 4501,
                  'return_code': result, 'stdout': capture.getvalue(), 'original_exception': failure,
                  'only_manifest_body_read': contents_read == ['new-synthetic-manifest-only'],
                  'typed_refusal_returned': result == 2 and failure is None}
elapsed = perf_counter_ns() - started
report = {'source_commit': 'ebe9e28d3707042cb51ae8ca818a0d5cc1fe1fc2',
          'source_path': str(SOURCE), 'source_sha256': sha256(source_bytes).hexdigest(),
          'actual_python': sys.version, 'actual_executable': sys.executable,
          'cpu_ids': sorted(os.sched_getaffinity(0)), 'int_max_str_digits': sys.get_int_max_str_digits(),
          'new_path_subcases': path_cases, 'oversized_number_case': number_case,
          'elapsed_ns': elapsed, 'within_ten_seconds': elapsed < 10_000_000_000,
          'no_secret_or_role_contents_read': True, 'no_sql_network_worker_or_child_started': True,
          'original_seventeen_suite_rerun': False,
          'finding': 'BOUNDED_JSON_INTEGER_VALUEERROR_ESCAPES_REFUSAL_CONTRACT',
          'production_approved': False}
print(json.dumps(report, indent=2, sort_keys=True))
assert all(row['passed'] for row in path_cases)
assert elapsed < 10_000_000_000
assert number_case['only_manifest_body_read'] and failure is not None
assert failure['type'] == 'builtins.ValueError' and result is None and capture.getvalue() == ''
