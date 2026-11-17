"""Existing mixed metadata keys on real owned-temp paths; no service runs."""
from copy import deepcopy
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch

from benchmarks.managed_read_holders import IdleReadHolders
from tests import test_managed_read_holder_lifecycle as fixtures


class ManagedReadHolderPathTests(unittest.TestCase):
    def make(self, alias=None):
        factory = fixtures.ManagedReadHolderLifecycleTests()
        self.addCleanup(factory.doCleanups)
        return factory.make(alias=alias)

    def test_dotdot_and_parent_alias_keep_original_mixed_metadata_and_lifecycle(self):
        for alias in ('dotdot', 'parent_alias'):
            with self.subTest(alias=alias):
                fixture = self.make(alias)
                original_directory = fixture.directory
                original_meta = deepcopy(fixture.meta)
                checkpoint_key = str(Path(fixture.checkpoint.path))
                self.assertIn(checkpoint_key, original_meta['file_identities'])
                self.assertNotEqual(checkpoint_key, str(fixture.directory / 'checkpoint.sqlite3'))
                self.assertFalse(fixture.directory.is_symlink())
                report = fixture.run()
                self.assertEqual(report['status'], 'paused', report['error'])
                self.assertIn('start_stub', fixture.stages)
                self.assertEqual(fixture.directory, original_directory)
                self.assertEqual(fixture.meta, original_meta)
                self.assertIsNone(fixture.read_holders)
                self.assertFalse(report['continuous_6h_stability_passed'])

    def test_canonical_key_collision_rejects_even_identical_identity_before_sqlite(self):
        for same_identity in (True, False):
            with self.subTest(same_identity=same_identity):
                fixture = self.make()
                (fixture.directory / 'step').mkdir(mode=0o700)
                meta = deepcopy(fixture.meta['file_identities'])
                original = meta[str(Path(fixture.checkpoint.path))]
                meta[str(fixture.directory / 'step' / '..' / 'checkpoint.sqlite3')] = (
                    list(original) if same_identity else [original[0], original[1] + 1])
                before = deepcopy(meta)
                with patch('benchmarks.managed_read_holders.sqlite3.connect', wraps=sqlite3.connect) as connect:
                    with self.assertRaisesRegex(ValueError, 'ambiguous'):
                        IdleReadHolders(fixture.directory, expected_identities=meta)
                    connect.assert_not_called()
                self.assertEqual(meta, before)

    def test_missing_or_invalid_original_identity_metadata_is_typed_failure_before_sqlite(self):
        fixture = self.make()
        original = fixture.meta['file_identities']
        checkpoint = str(Path(fixture.checkpoint.path))
        missing = deepcopy(original)
        del missing[checkpoint]
        cases = [None, [], 'invalid', missing]
        for value in (None, [], [1], [1, True], [-1, 1], [1, 0], [1, '2'], [1, 2.0], (1, 2)):
            malformed = deepcopy(original)
            malformed[checkpoint] = value
            cases.append(malformed)
        for key in (1, 'relative.sqlite3', ''):
            malformed = deepcopy(original)
            malformed[key] = [1, 1]
            cases.append(malformed)
        for number, metadata in enumerate(cases):
            with self.subTest(case=number):
                with patch('benchmarks.managed_read_holders.sqlite3.connect', wraps=sqlite3.connect) as connect:
                    made = None
                    try:
                        with self.assertRaises(ValueError):
                            made = IdleReadHolders(fixture.directory, expected_identities=metadata)
                    finally:
                        if made is not None:
                            made.close()
                    connect.assert_not_called()

    def test_parent_alias_does_not_resolve_final_main_symlink(self):
        fixture = self.make('parent_alias')
        main = Path(fixture.checkpoint.path)
        replacement = main.with_name('replacement.sqlite3')
        main.rename(replacement)  # All owned fixture connections are closed.
        main.symlink_to(replacement)
        before = deepcopy(fixture.meta)
        with patch('benchmarks.managed_read_holders.sqlite3.connect', wraps=sqlite3.connect) as connect:
            with self.assertRaisesRegex(ValueError, 'direct regular'):
                IdleReadHolders(fixture.directory, expected_identities=fixture.meta['file_identities'])
            connect.assert_not_called()
        self.assertTrue(main.is_symlink())
        self.assertEqual(fixture.meta, before)


if __name__ == '__main__':
    unittest.main()
