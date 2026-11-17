"""Metadata-only review deployment checks; no product or database import."""
from contextlib import redirect_stdout
from copy import deepcopy
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location('deployment_manifest',
    Path(__file__).resolve().parents[1] / 'tools/check_deployment_manifest.py')
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)


class DeploymentManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory(prefix='uta-deploy-metadata-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.roles = {}
        for name in ('financial', 'auth', 'configuration'):
            path = self.root / name
            path.mkdir(mode=0o700)
            self.roles[name + '_directory'] = path
        for role, parent in (('nonce_database', 'auth'), ('signing_profile', 'configuration'),
                             ('tls_certificate', 'configuration'), ('tls_private_key', 'configuration')):
            path = self.root / parent / role
            path.write_bytes(b'opaque synthetic role fixture, never inspected')
            path.chmod(0o600)
            self.roles[role] = path
        self.wheel = self.root / 'review.whl'
        self.wheel.write_bytes(b'opaque wheel fixture, not a verified package')
        self.wheel.chmod(0o644)
        commit = '9' * 40
        self.value = {'format': 1, 'deployment_id': 'review-synthetic-a', 'purpose': 'review_synthetic',
            'operator_uid': os.getuid(), 'source_commit': commit,
            'artifact': {'kind': 'wheel', 'path': str(self.wheel), 'source_commit': commit,
                         'sha256': 'a' * 64, 'version': '0.1.0'},
            'rules': {'source_commit': commit, 'version': 'UTA-CROSS-LOAN-v1'},
            'storage': {'engine': 'sqlite', 'journal_mode': 'WAL', 'synchronous': 'FULL',
                        'replication': 'none', 'host_scope': 'single_host'},
            'products': {'data_classification': 'synthetic', 'settlement_currency': 'USD',
                         'account_modes': ['Cross'], 'instruments': ['spot', 'linear_perpetual']},
            'paths': {role: str(path) for role, path in self.roles.items()},
            'approval': {'real_funds_requested': False, 'external_approval_reference': None}}

    def refused(self, value, code):
        with self.assertRaisesRegex(CHECK.ManifestError, '^' + code + '$'):
            CHECK.validate_manifest(value)

    def test_consistent_metadata_never_implies_artifact_or_production_acceptance(self):
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('contents forbidden')):
            result = CHECK.validate_manifest(self.value)
        self.assertEqual(result['status'], 'REVIEW_DECLARATION_AND_METADATA_CONSISTENT')
        for field in ('artifact_digest_verified', 'rules_contents_verified', 'actual_storage_settings_verified',
                      'external_approval_verified', 'activation_authorized', 'production_approved', 'snapshot_atomic'):
            self.assertIs(result[field], False)

    def test_unknown_field_cannot_smuggle_an_enable_flag(self):
        for section in (None, 'approval', 'storage', 'products', 'artifact', 'rules', 'paths'):
            with self.subTest(section=section):
                value = deepcopy(self.value)
                (value if section is None else value[section])['production_approved'] = True
                with self.assertRaises(CHECK.ManifestError): CHECK.validate_manifest(value)

    def test_real_funds_and_self_declared_external_approval_are_refused(self):
        value = deepcopy(self.value)
        value['approval']['real_funds_requested'] = True
        self.refused(value, 'real_funds_require_external_release_process')
        value = deepcopy(self.value)
        value['approval']['external_approval_reference'] = 'claimed-approved'
        self.refused(value, 'approval_not_verifiable_offline')

    def test_source_artifact_rule_references_must_agree(self):
        for section in ('artifact', 'rules'):
            value = deepcopy(self.value)
            value[section]['source_commit'] = '8' * 40
            self.refused(value, 'source_reference_mismatch')

    def test_uninitialized_commit_or_digest_placeholder_is_refused(self):
        value = deepcopy(self.value)
        value['source_commit'] = value['artifact']['source_commit'] = value['rules']['source_commit'] = '0' * 40
        self.refused(value, 'source_reference_uninitialized')
        value = deepcopy(self.value)
        value['artifact']['sha256'] = '0' * 64
        self.refused(value, 'artifact_digest_uninitialized')

    def test_bool_is_not_format_or_os_uid(self):
        for field in ('format', 'operator_uid'):
            value = deepcopy(self.value)
            value[field] = True
            self.refused(value, 'manifest_format' if field == 'format' else 'operator_uid')
        value = deepcopy(self.value)
        value['operator_uid'] = 0
        self.refused(value, 'operator_uid')

    def test_unaccepted_products_and_replication_claims_are_refused(self):
        for field, replacement in (('account_modes', ['PM']), ('settlement_currency', 'USDT'),
                                   ('instruments', ['spot', 'linear_perpetual', 'option']),
                                   ('data_classification', 'real_funds')):
            value = deepcopy(self.value)
            value['products'][field] = replacement
            self.refused(value, 'unsupported_product_scope')
        value = deepcopy(self.value)
        value['storage']['replication'] = 'three_az'
        self.refused(value, 'unsupported_storage_claim')

    def test_nonce_and_financial_directories_cannot_overlap(self):
        value = deepcopy(self.value)
        value['paths']['auth_directory'] = str(self.roles['financial_directory'] / 'auth')
        self.refused(value, 'authority_directory_roles_overlap')
        value['paths']['auth_directory'] = str(self.roles['financial_directory'])
        self.refused(value, 'authority_directory_roles_overlap')

    def test_declared_role_cannot_escape_its_directory(self):
        for role in ('nonce_database', 'signing_profile', 'tls_certificate', 'tls_private_key'):
            value = deepcopy(self.value)
            value['paths'][role] = str(self.wheel)
            self.refused(value, 'nonce_outside_auth_directory' if role == 'nonce_database'
                         else 'secret_outside_configuration_directory')

    def test_symlink_file_and_ancestor_are_refused(self):
        link = self.root / 'link'
        link.symlink_to(self.root, target_is_directory=True)
        value = deepcopy(self.value)
        value['artifact']['path'] = str(link / 'review.whl')
        self.refused(value, 'symlink_component_refused')
        profile = self.roles['signing_profile']
        profile.unlink()
        profile.symlink_to(self.roles['tls_private_key'])
        self.refused(self.value, 'symlink_component_refused')

    def test_hardlinked_role_is_refused_without_reading_contents(self):
        profile = self.roles['signing_profile']
        profile.unlink()
        os.link(self.roles['tls_private_key'], profile)
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('contents forbidden')):
            self.refused(self.value, 'private_file_owner_or_hardlinks')

    def test_private_permissions_and_owner_are_not_declaration_only(self):
        self.roles['tls_private_key'].chmod(0o640)
        self.refused(self.value, 'private_file_permissions')
        self.roles['tls_private_key'].chmod(0o600)
        value = deepcopy(self.value)
        value['operator_uid'] += 1
        self.refused(value, 'directory_owner')

    def test_financial_directory_permissions_are_strict(self):
        self.roles['financial_directory'].chmod(0o750)
        self.refused(self.value, 'directory_permissions')

    def test_wheel_metadata_cannot_claim_group_writable_artifact(self):
        self.wheel.chmod(0o664)
        self.refused(self.value, 'artifact_empty_or_mutable_by_group_other')

    def test_changed_metadata_is_refused(self):
        real = CHECK.metadata
        seen = [0]
        def changing(path):
            seen[0] += 1
            if seen[0] == 9:
                self.wheel.write_bytes(b'changed while checking')
            return real(path)
        with patch.object(CHECK, 'metadata', changing):
            self.refused(self.value, 'metadata_changed_during_check')

    def test_noncanonical_paths_are_refused(self):
        for suffix in ('/../financial', '//financial'):
            value = deepcopy(self.value)
            value['paths']['financial_directory'] = str(self.root) + suffix
            self.refused(value, 'normalized_absolute_path_required')
        for suffix, code in (('/bad\x00name', 'path_nul_refused'), ('/bad\ud800name', 'path_utf8_required')):
            value = deepcopy(self.value)
            value['paths']['financial_directory'] = str(self.root) + suffix
            self.refused(value, code)

    def test_duplicate_json_key_and_unknown_error_output_do_not_echo_content(self):
        p = self.root / 'manifest.json'
        p.write_text('{"format":1,"format":1}')
        with self.assertRaisesRegex(CHECK.ManifestError, 'duplicate_json_field'):
            CHECK.load_manifest(p)
        private_marker = 'must-not-appear-in-output'
        p.write_text(private_marker)
        capture = io.StringIO()
        with redirect_stdout(capture):
            code = CHECK.main(['--manifest', str(p)])
        self.assertEqual(code, 2)
        self.assertNotIn(private_marker, capture.getvalue())
        self.assertEqual(json.loads(capture.getvalue())['code'], 'manifest_json_invalid')

    def test_decoder_value_error_returns_stable_refusal(self):
        p = self.root / 'manifest.json'
        p.write_text('{}')
        capture = io.StringIO()
        with patch.object(CHECK.json, 'loads', side_effect=ValueError('private decoder detail')), redirect_stdout(capture):
            code = CHECK.main(['--manifest', str(p)])
        result = json.loads(capture.getvalue())
        self.assertEqual((code, result['status'], result['code']), (2, 'REFUSED', 'manifest_json_invalid'))
        self.assertNotIn('private decoder detail', capture.getvalue())

    def test_real_large_integer_is_refused_without_echo(self):
        p = self.root / 'manifest.json'
        p.write_text('{"format":' + '9' * 4501 + '}')
        capture = io.StringIO()
        with redirect_stdout(capture):
            code = CHECK.main(['--manifest', str(p)])
        result = json.loads(capture.getvalue())
        self.assertEqual((code, result['status']), (2, 'REFUSED'))
        digit_limit = getattr(sys, 'get_int_max_str_digits', lambda: 0)()
        expected = 'manifest_json_invalid' if 0 < digit_limit < 4501 else 'manifest_fields'
        self.assertEqual(result['code'], expected)
        self.assertNotIn('9' * 32, capture.getvalue())

    def test_manifest_argument_encoding_is_typed_before_io(self):
        for path, expected in (('/bad\x00manifest', 'path_nul_refused'),
                               ('/bad\ud800manifest', 'path_utf8_required')):
            capture = io.StringIO()
            with patch.object(Path, 'lstat', side_effect=AssertionError('metadata forbidden')), \
                 patch.object(Path, 'read_bytes', side_effect=AssertionError('contents forbidden')), redirect_stdout(capture):
                code = CHECK.main(['--manifest', path])
            self.assertEqual((code, json.loads(capture.getvalue())['code']), (2, expected))

    def test_json_policy_errors_keep_their_specific_codes(self):
        p = self.root / 'manifest.json'
        for text, expected in (('{"format":1,"format":1}', 'duplicate_json_field'),
                               ('{"format":NaN}', 'nonfinite_json')):
            p.write_text(text)
            capture = io.StringIO()
            with redirect_stdout(capture):
                code = CHECK.main(['--manifest', str(p)])
            self.assertEqual((code, json.loads(capture.getvalue())['code']), (2, expected))


if __name__ == '__main__':
    unittest.main()
