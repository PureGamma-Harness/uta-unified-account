"""Offline review-deployment lint: declarations and lstat only, no authority opens.

Consistent declarations are not verified artifacts or production authorization.
The CLI never reads secrets, wheel contents, SQLite contents or approval files.
"""
import argparse
import json
from pathlib import Path
import re
import stat
import sys


class ManifestError(ValueError):
    pass


def need(condition, code):
    if not condition:
        raise ManifestError(code)


def exact(value, keys, code):
    need(type(value) is dict and set(value) == set(keys), code)


def bounded_text(value, pattern, code):
    need(type(value) is str and re.fullmatch(pattern, value) is not None, code)


def _pairs(items):
    result = {}
    for key, value in items:
        need(key not in result, 'duplicate_json_field')
        result[key] = value
    return result


def load_manifest(path):
    need(path.is_absolute(), 'manifest_absolute_path_required')
    details = path.lstat()
    need(stat.S_ISREG(details.st_mode) and details.st_size <= 32768, 'manifest_regular_bounded_file_required')
    raw = path.read_bytes()
    need(len(raw) <= 32768, 'manifest_size_changed')
    try:
        return json.loads(raw, object_pairs_hook=_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ManifestError('nonfinite_json')))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise ManifestError('manifest_json_invalid') from error


def declared_path(value):
    need(type(value) is str and 0 < len(value) <= 4096, 'path_string_required')
    path = Path(value)
    need(path.is_absolute() and '..' not in path.parts and str(path) == value,
         'normalized_absolute_path_required')
    return path


def metadata(path):
    # Reject a symlink in every currently observed component, including ancestors.
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        details = current.lstat()
        need(not stat.S_ISLNK(details.st_mode), 'symlink_component_refused')
    details = path.lstat()
    return details


def fingerprint(details):
    return tuple(getattr(details, name) for name in
                 ('st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_gid', 'st_nlink',
                  'st_size', 'st_mtime_ns', 'st_ctime_ns'))


def validate_manifest(value):
    exact(value, ('format', 'deployment_id', 'purpose', 'operator_uid', 'source_commit',
                  'artifact', 'rules', 'storage', 'products', 'paths', 'approval'), 'manifest_fields')
    need(type(value['format']) is int and value['format'] == 1, 'manifest_format')
    bounded_text(value['deployment_id'], r'[a-z][a-z0-9-]{0,63}', 'deployment_id')
    need(value['purpose'] == 'review_synthetic', 'review_synthetic_only')
    need(type(value['operator_uid']) is int and 0 < value['operator_uid'] < 2**32, 'operator_uid')
    bounded_text(value['source_commit'], r'[0-9a-f]{40}', 'source_commit')
    need(value['source_commit'] != '0' * 40, 'source_reference_uninitialized')
    exact(value['approval'], ('real_funds_requested', 'external_approval_reference'), 'approval_fields')
    need(value['approval']['real_funds_requested'] is False, 'real_funds_require_external_release_process')
    # A string or boolean in this untrusted declaration cannot authenticate approval.
    need(value['approval']['external_approval_reference'] is None, 'approval_not_verifiable_offline')

    artifact, rules = value['artifact'], value['rules']
    exact(artifact, ('kind', 'path', 'source_commit', 'sha256', 'version'), 'artifact_fields')
    need(artifact['kind'] == 'wheel', 'artifact_kind')
    bounded_text(artifact['sha256'], r'[0-9a-f]{64}', 'artifact_sha256')
    need(artifact['sha256'] != '0' * 64, 'artifact_digest_uninitialized')
    bounded_text(artifact['version'], r'[0-9]+\.[0-9]+\.[0-9]+(?:[a-z0-9.+-]{0,32})', 'artifact_version')
    exact(rules, ('source_commit', 'version'), 'rules_fields')
    need(artifact['source_commit'] == rules['source_commit'] == value['source_commit'], 'source_reference_mismatch')
    need(rules['version'] == 'UTA-CROSS-LOAN-v1', 'unsupported_rules_version')
    exact(value['storage'], ('engine', 'journal_mode', 'synchronous', 'replication', 'host_scope'), 'storage_fields')
    need(value['storage'] == {'engine': 'sqlite', 'journal_mode': 'WAL', 'synchronous': 'FULL',
                              'replication': 'none', 'host_scope': 'single_host'}, 'unsupported_storage_claim')
    exact(value['products'], ('data_classification', 'settlement_currency', 'account_modes', 'instruments'), 'products_fields')
    need(value['products'] == {'data_classification': 'synthetic', 'settlement_currency': 'USD',
                               'account_modes': ['Cross'], 'instruments': ['spot', 'linear_perpetual']},
         'unsupported_product_scope')
    roles = ('financial_directory', 'auth_directory', 'configuration_directory', 'nonce_database',
             'signing_profile', 'tls_certificate', 'tls_private_key')
    exact(value['paths'], roles, 'path_roles')
    paths = {role: declared_path(value['paths'][role]) for role in roles}
    paths['artifact'] = declared_path(artifact['path'])
    roots = [paths[role] for role in roles[:3]]
    for index, first in enumerate(roots):
        for second in roots[index + 1:]:
            need(first != second and first not in second.parents and second not in first.parents,
                 'authority_directory_roles_overlap')
    need(paths['nonce_database'].parent == paths['auth_directory'], 'nonce_outside_auth_directory')
    for role in ('signing_profile', 'tls_certificate', 'tls_private_key'):
        need(paths[role].parent == paths['configuration_directory'], 'secret_outside_configuration_directory')
    need(all(root != paths['artifact'] and root not in paths['artifact'].parents for root in roots),
         'artifact_inside_mutable_authority_or_secret_tree')

    before, identities = {}, {}
    for role, path in paths.items():
        details = metadata(path)
        if role in roles[:3]:
            need(stat.S_ISDIR(details.st_mode), 'directory_role_is_not_directory')
            permitted = (0o700, 0o750) if role == 'configuration_directory' else (0o700,)
            need(stat.S_IMODE(details.st_mode) in permitted, 'directory_permissions')
            need(details.st_uid == value['operator_uid'], 'directory_owner')
        else:
            need(stat.S_ISREG(details.st_mode), 'file_role_is_not_regular')
            if role == 'artifact':
                need(details.st_size > 0 and stat.S_IMODE(details.st_mode) & 0o022 == 0,
                     'artifact_empty_or_mutable_by_group_other')
            else:
                need(stat.S_IMODE(details.st_mode) == 0o600, 'private_file_permissions')
                need(details.st_uid == value['operator_uid'] and details.st_nlink == 1,
                     'private_file_owner_or_hardlinks')
        identity = (details.st_dev, details.st_ino)
        need(identity not in identities, 'path_roles_share_inode')
        identities[identity] = role
        before[role] = fingerprint(details)
    for role, path in paths.items():
        need(fingerprint(metadata(path)) == before[role], 'metadata_changed_during_check')
    return {'format': 1, 'status': 'REVIEW_DECLARATION_AND_METADATA_CONSISTENT',
            'deployment_id': value['deployment_id'], 'source_commit': value['source_commit'],
            'checked_path_roles': sorted(paths), 'private_contents_read': False,
            'sqlite_opened': False, 'artifact_digest_verified': False, 'rules_contents_verified': False,
            'secret_contents_verified': False,
            'actual_storage_settings_verified': False, 'external_approval_verified': False,
            'snapshot_atomic': False, 'activation_authorized': False, 'production_approved': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = validate_manifest(load_manifest(args.manifest))
    except (ManifestError, OSError) as error:
        report = {'status': 'REFUSED', 'code': str(error) if isinstance(error, ManifestError) else 'metadata_unavailable',
                  'activation_authorized': False, 'production_approved': False}
        print(json.dumps(report, sort_keys=True))
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
