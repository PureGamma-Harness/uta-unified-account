"""Small JSON/PIPE fixtures only; never start the real producer or a service."""
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tools import run_managed_long as runner


def plan():
    return {'python': 'exact-python', 'validation_report': '/exact/summary.json', 'source_root': '/source',
        'source_commit': '7' * 40,
        'producer': {'duration_seconds': 21600, 'rate_rounds_per_second': .25, 'planned_rounds': 5400,
            'worker_fault_every_rounds': 30, 'parent_fault_every_rounds': 300},
        'observer': {'blocks': 12, 'technical_read_unknown_budget': 3,
            'maximum_consecutive_technical_read_unknown': 1, 'interval_seconds': 61,
            'max_private_clone_bytes': 6 * 1024**3, 'clone_headroom_bytes': 1024**3,
            'max_address_space_bytes': 2 * 1024**3}}


class LongPreparationTests(unittest.TestCase):
    def test_original_plan_hash_and_supported_amended_cadence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = json.dumps(plan()).encode()
            (root / 'plan.json').write_bytes(raw)
            amendment = {'original_plan_sha256': sha256(raw).hexdigest(), 'observer_interval_seconds_effective': 61}
            (root / 'amendment.json').write_text(json.dumps(amendment))
            value, _, fingerprints = runner.read_plan(root / 'plan.json', root / 'amendment.json')
            self.assertEqual(value['observer']['interval_seconds'], 61)
            self.assertEqual(fingerprints['base_plan_sha256'], sha256(raw).hexdigest())
            amendment['observer_interval_seconds_effective'] = 59
            (root / 'amendment.json').write_text(json.dumps(amendment))
            with self.assertRaisesRegex(ValueError, 'unsupported_preregistered_workload'):
                runner.read_plan(root / 'plan.json', root / 'amendment.json')

    def test_producer_is_original_run_with_exact_report_and_no_resume(self):
        command = runner.producer_command(plan(), Path('/fresh/job'))
        self.assertEqual(command[0], 'exact-python')
        self.assertEqual(command[command.index('--duration') + 1], '21600')
        self.assertIn('--allow-long-run', command)
        self.assertEqual(command[-2:], ['--validation-report', '/exact/summary.json'])
        self.assertNotIn('resume', command)
        self.assertNotIn('--allow-dirty-development', command)

    def test_observer_uses_supported_cli_with_fresh_devices_and_exec_identity(self):
        command = runner.observer_command(plan(), Path('/fresh'), {'driver_pid': 123, 'driver_birth': '456'})
        self.assertEqual(command[:7], ['bwrap', '--ro-bind', '/', '/', '--dev', '/dev', '--die-with-parent'])
        self.assertIn('watch', command)
        self.assertEqual(command[command.index('--interval') + 1], '61')
        self.assertNotIn('--unshare-pid', command)
        prefix = next(value for value in command if 'os.execv' in value)
        self.assertNotIn('.sample(', prefix)
        self.assertIn('watch-cli-identity.json', ' '.join(command))

    def test_timeline_keeps_partial_line_and_never_double_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'timeline.jsonl'
            tail = runner.Timeline(path)
            self.assertEqual(tail.read(), [])
            path.write_bytes(b'{"synthetic":')
            self.assertEqual(tail.read(), [])
            with path.open('ab') as stream:
                stream.write(b'true}\n{"logical_point":"unknown"}\n')
            self.assertEqual(tail.read(), [{'synthetic': True}, {'logical_point': 'unknown'}])
            self.assertEqual(tail.read(), [])
            self.assertEqual(tail.pending, b'')

    def test_short_fixture_pipes_hash_stderr_and_drop_unknown_fields(self):
        code = "import json,sys; print(json.dumps({'synthetic':True,'status':'completed','private':'synthetic-hidden'}));sys.stderr.write('synthetic-stderr')"
        child = runner.Pipes([sys.executable, '-B', '-c', code], runner.ROOT)
        child.process.wait(timeout=5)
        result = child.result()
        self.assertEqual(result['response'], {'synthetic': True, 'status': 'completed'})
        self.assertEqual(result['stderr_sha256'], sha256(b'synthetic-stderr').hexdigest())
        self.assertNotIn('synthetic-hidden', json.dumps(result))
        self.assertNotIn('synthetic-stderr', json.dumps(result))
        self.assertGreater(result['identity']['pid'], 0)
        self.assertTrue(result['identity']['birth'].isdecimal())

    def test_stop_refuses_protected_identity_without_reading_or_signalling_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'watch-cli-identity.json').write_text(json.dumps({'pid': 4471, 'birth': 'old'}))
            with patch.object(runner.ro, 'process_identity', side_effect=AssertionError('must not inspect old PID')), \
                 patch.object(runner.os, 'kill', side_effect=AssertionError('must not signal old PID')):
                with self.assertRaisesRegex(ValueError, 'protected_old_process'):
                    runner.request_observer_stop(SimpleNamespace(), root)


if __name__ == '__main__':
    unittest.main()
