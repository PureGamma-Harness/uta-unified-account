"""Pure JSON/command/gate checks; no SQLite or operational CLI is invoked."""
from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('stability_prepare', ROOT / 'tools/prepare_managed_stability.py')
prepare = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prepare)
PROFILE = ROOT / 'benchmarks/profiles/managed-d421df3-pending.json'


class ManagedStabilityPrepareTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.profiles = {}
        for source in (ROOT / 'benchmarks/profiles').glob('*.json'):
            value = json.loads(source.read_text())
            for field in ('plan', 'amendment'):
                original = ROOT / 'benchmarks/plans' / Path(value[field]).name
                target = root / original.name
                if not target.exists():
                    target.write_bytes(original.read_bytes())
                value[field] = str(target)
            target = root / source.name
            target.write_text(json.dumps(value))
            self.profiles[source.name] = target
        self.profile = self.profiles[PROFILE.name]

    def test_commands_bind_explicit_new_source_report_and_no_default_763(self):
        value = prepare.profile(self.profile)
        commands = prepare.commands(value, record='startup.json')
        for phase, command in commands.items():
            self.assertNotIn('763202d', ' '.join(command))
            self.assertEqual(command[0], value['python'])
            if phase.startswith('smoke-'):
                self.assertEqual(command[command.index('--source')+1], value['source_root'])
                self.assertEqual(command[command.index('--commit')+1], value['source_commit'])
                self.assertEqual(command[command.index('--report')+1], value['validation_report'])
            else:
                self.assertEqual(command[command.index('--plan')+1], value['plan'])
                self.assertEqual(command[command.index('--amendment')+1], value['amendment'])
                self.assertEqual(command[command.index('--scratch')+1], value['long_scratch'])

    def test_blocked_and_pending_profiles_cannot_import_transport_or_start_child(self):
        for name in ('managed-bb34b5f-blocked.json', 'managed-d421df3-pending.json', 'managed-d421df3-blocked.json'):
            path = self.profiles[name]
            with self.subTest(name=name), patch.object(prepare.importlib, 'import_module') as module, \
                    patch.object(prepare.subprocess, 'Popen') as child, \
                    patch.object(prepare.os, 'pidfd_open') as pidfd, \
                    patch.object(prepare.signal, 'pidfd_send_signal') as send, \
                    patch.object(Path, 'mkdir') as mkdir:
                with self.assertRaisesRegex(ValueError, 'qualification_not_complete'):
                    prepare.invoke(path, 'smoke-produce', prepare.fingerprint(path))
                module.assert_not_called()
                child.assert_not_called()
                pidfd.assert_not_called()
                send.assert_not_called()
                mkdir.assert_not_called()

    def test_root_go_must_match_exact_profile_and_true_literal_gates(self):
        value = prepare.profile(self.profile)
        value['qualification'] = dict(status='COMPLETE_ALL_GATES_PASSED', blocked_reason=None,
            all_three_local_passed=True, all_eight_ci_passed=True, independent_new_package_passed=True)
        with self.assertRaisesRegex(ValueError, 'root_GO'):
            prepare.authorized(value, self.profile, 'wrong hash')
        value['qualification']['all_eight_ci_passed'] = 1
        with self.assertRaisesRegex(ValueError, 'qualification_not_complete'):
            prepare.authorized(value, self.profile, prepare.fingerprint(self.profile))

    def test_modified_plan_or_target_mismatch_is_rejected(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'profile.json'
            value = prepare.profile(self.profile)
            value['source_commit'] = 'f' * 40
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, 'disagree'):
                prepare.profile(path)
            value = prepare.profile(self.profile)
            value['plan_sha256'] = '0' * 64
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, 'hash_changed'):
                prepare.profile(path)

    def test_existing_frozen_supervisor_worker_and_interval_contract_is_not_relaxed(self):
        value = prepare.profile(self.profile)
        with TemporaryDirectory() as directory:
            root = Path(directory)
            plan, amendment = prepare.load(value['plan']), prepare.load(value['amendment'])
            plan['producer']['worker_fault_every_rounds'] = 5
            (root/'plan.json').write_text(json.dumps(plan))
            value['plan'], value['plan_sha256'] = str(root/'plan.json'), prepare.fingerprint(root/'plan.json')
            amendment['original_plan_sha256'] = value['plan_sha256']
            (root/'amendment.json').write_text(json.dumps(amendment))
            value['amendment'], value['amendment_sha256'] = str(root/'amendment.json'), prepare.fingerprint(root/'amendment.json')
            (root/'profile.json').write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, 'supervisor_contract'):
                prepare.profile(root/'profile.json')

    def test_record_path_cannot_escape_observer_output(self):
        with self.assertRaises(ValueError):
            prepare.commands(prepare.profile(self.profile), record='../job/bad.json')


if __name__ == '__main__':
    unittest.main()
