"""Metadata archival tests only; no financial module or database is opened."""
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.archive_recovery_evidence import archive


class RecoveryEvidenceArchiveTests(unittest.TestCase):
    def test_redacted_derivative_preserves_original_and_code_artifact(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            case = root/'private-case'
            authority = case/'cohort/authority'
            authority.mkdir(parents=True)
            database = authority/'shard.sqlite3'
            database.write_bytes(b'private database bytes must never be archived')
            nonce = 'worker:'+'a'*32
            native = json.dumps({'source_files': {'a.py': 'f'*64}, 'loaded_engine': {}, 'source_digest': 'd'*64})
            value = {'owner_nonce': nonce, 'fence_events': [[nonce]],
                     'loaded_artifacts': [['artifact:'+sha256(native.encode()).hexdigest(), native]],
                     'boot_id': '12345678-1234-1234-1234-123456789abc'}
            encoded = (json.dumps(value)+'\n').encode()
            (case/'result.json').write_bytes(encoded)
            (case/'manifest-after-test.json').write_text(json.dumps({'files': {
                'cohort/authority/shard.sqlite3': {'bytes': database.stat().st_size, 'sha256': sha256(database.read_bytes()).hexdigest()}}}))
            output = root/'public'
            report = archive((('test', case),), output)
            self.assertEqual((case/'result.json').read_bytes(), encoded)
            self.assertFalse((output/'test/cohort/authority').exists())
            public = json.loads((output/'test/result.json').read_text())
            self.assertNotEqual(public['owner_nonce'], nonce)
            self.assertEqual(public['owner_nonce'], public['fence_events'][0][0])
            self.assertEqual(public['loaded_artifacts'][0][1], native)
            self.assertNotIn(nonce, (output/'test/result.json').read_text())
            self.assertTrue(report['files']['test/result.json']['redacted_derivative'])
            self.assertFalse(report['included_database_bytes'])

    def test_public_manifest_hashes_are_public_derivatives(self):
        root = Path(__file__).resolve().parents[1]/'benchmarks/results/20261117-recovery-763-authorized'
        report = json.loads((root/'public-manifest.json').read_text())
        for name, expected in report['files'].items():
            data = (root/name).read_bytes()
            self.assertEqual(len(data), expected['public_bytes'])
            self.assertEqual(sha256(data).hexdigest(), expected['public_sha256'])
            self.assertNotIn('authority', Path(name).parts)
        for label in ('1k', '250k'):
            result = json.loads((root/label/'launcher-result.json').read_text())
            for identity, payload in result['postmortem']['loaded_artifacts']:
                self.assertEqual(identity, 'artifact:'+sha256(payload.encode()).hexdigest())
        self.assertEqual(json.loads((root/'1k/launcher-result.json').read_text())['status'], 'TOOL_COMPLETED')
        self.assertEqual(json.loads((root/'250k/launcher-result.json').read_text())['status'], 'TIME_BUDGET_ABORTED')


if __name__ == '__main__':
    unittest.main()
