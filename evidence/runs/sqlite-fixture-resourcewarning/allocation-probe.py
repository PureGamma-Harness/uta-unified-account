"""Focused resource ownership evidence; no application code is instrumented."""
import gc
from pathlib import Path
import sqlite3
import sys
import tracemalloc
import unittest
import warnings

ROOT = Path('/workspace/uta-sqlite-fixture-cleanup')
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
CASES = (
    'test_request_signing.SigningStoreTests.test_duplicate_signature_headers_and_corrupt_store_are_rejected',
    'test_writer_fence.WriterFenceTests.test_copy_to_another_path_cannot_reuse_managed_authority',
    'test_writer_fence.WriterFenceTests.test_unknown_control_trigger_is_corruption_without_automatic_repair',
    'test_writer_fence.WriterFenceTests.test_changed_control_trigger_definition_is_corruption',
    'test_writer_fence_legacy.LegacyBinaryFenceTests.test_missing_guard_is_rejected_without_startup_or_upgrade_repair',
    'test_writer_fence_legacy.LegacyBinaryFenceTests.test_all_guard_metadata_disappearing_cannot_be_misidentified_as_old_format',
    'test_writer_fence_legacy.LegacyBinaryFenceTests.test_python_only_managed_format_requires_explicit_offline_upgrade',
)

if __name__ == '__main__':
    print('python', sys.version, 'sqlite', sqlite3.sqlite_version, flush=True)
    tracemalloc.start(12)
    passed = True
    total_warnings = 0
    for name in CASES:
        gc.collect()
        with warnings.catch_warnings(record=True) as observed:
            warnings.simplefilter('always', ResourceWarning)
            suite = unittest.defaultTestLoader.loadTestsFromName(name)
            result = unittest.TextTestRunner(verbosity=2).run(suite)
            gc.collect()
        passed = passed and result.wasSuccessful()
        total_warnings += len(observed)
        print('CASE', name, 'unittest_success', result.wasSuccessful(), 'resource_warnings', len(observed), flush=True)
        for item in observed:
            print('CAPTURED', item.category.__name__, str(item.message), 'emitted_at', item.filename, item.lineno, flush=True)
            trace = tracemalloc.get_object_traceback(item.source)
            if trace is not None:
                print('ALLOCATION\n' + '\n'.join(trace.format()), flush=True)
    print('TOTAL unittest_success', passed, 'resource_warnings', total_warnings, flush=True)
    assert passed
    assert (total_warnings > 0) if '--expect-warnings' in sys.argv else (total_warnings == 0)
