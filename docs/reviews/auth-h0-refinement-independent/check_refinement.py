"""Git/text/JSON/Fraction and finite quota checks only; no SQL parser/import."""
from pathlib import Path
import hashlib
import itertools
import json
import re
import subprocess

REF = '39cddde7159fb0307aba97c4fa355cd52a807b1b'
ORIGINAL = '431225d01439cba1a4acce6529e35368eac391df'
REVIEW = '6063268d4da26f8b8b229c421775a3f96bb3e303'
ROOT = Path(__file__).resolve().parents[3]
checks = []

def blob(ref, path):
    return subprocess.check_output(['git', 'show', ref + ':' + path], cwd=ROOT)

def check(name, value):
    if not value:
        raise AssertionError(name)
    checks.append(name)

prefix = 'docs/contracts/'
contract_path = prefix + 'credit-hmac-h0-contract-v1.json'
ddl_path = prefix + 'credit-hmac-h0-schema-v2.sql.txt'
contract = json.loads(blob(REF, contract_path))
ddl = blob(REF, ddl_path).decode()
doc = blob(REF, 'docs/credit-hmac-h0-refinement.md').decode()
inputs = {path: hashlib.sha256(blob(REF, path)).hexdigest() for path in
          [contract_path, ddl_path, 'docs/credit-hmac-h0-refinement.md']}
for path, digest in contract['original_plan_files_sha256_must_remain_unchanged'].items():
    check('original-bytes:' + path, blob(REF, path) == blob(ORIGINAL, path))
    check('original-sha:' + path, hashlib.sha256(blob(REF, path)).hexdigest() == digest)
review_paths = subprocess.check_output(['git', 'diff-tree', '--no-commit-id', '--name-only', '-r', REVIEW],
                                     cwd=ROOT, text=True).splitlines()
for path in review_paths:
    check('independent-original-review-bytes:' + path, blob(REF, path) == blob(REVIEW, path))
check('base-refinement-identity', contract['base_plan_commit'] == ORIGINAL and
      contract['independent_required_refinement_commit'] == REVIEW)
check('schema-text-sha', inputs[ddl_path] == contract['schema']['draft_sha256'])
check('fresh-auth-format2-not-financial3', contract['formats']['legacy_auth_database'] == 1 and
      contract['formats']['fresh_h0_auth_database'] == 2 and contract['formats']['h0_financial_format'] is None)
check('no-schema-dynamic-claim', contract['schema']['sqlite_syntax_or_execution_tested'] is False and
      contract['schema']['draft_is_nonexecuted_documentation_text'] is True)
for key in ('runtime_code', 'sql_parse_or_execution', 'database_open', 'product_import',
            'tls_or_listener', 'financial_source_or_pending', 'native_or_financial_execution',
            'whole_qa_package_benchmark', 'push', 'change_frozen_909'):
    check('original-authorization-remains-false:' + key, contract['current_authorization'][key] is False)
check('twelve-cases-not-run', len(contract['planned_h0_cases']) == 12 and
      all(row['execution_status'] == 'NOT_RUN' for row in contract['planned_h0_cases']))
original = json.loads(blob(REF, prefix + 'credit-v2-hmac-bridge-v1.json'))
check('original-thirty-not-run', len(original['test_plan']) == 30 and
      all(row['execution_status'] == 'NOT_RUN' for row in original['test_plan']))
identity = contract['acceptance_identity']
check('immutable-logical-key', identity['business_key'] ==
      ['domain_id', 'tenant_namespace', 'account_id', 'business_CID'])
for key in ('first_row_update_delete_replace', 'first_acceptance_may_be_rebound_after_grant_revocation',
            'source_delivery_or_execution_handle_ever_issued_by_h0'):
    check('first-identity-denial:' + key, identity[key] is False)
check('query-requires-current-read', 'current exact credit.read' in identity['new_nonce_same_cid'])
check('exact-permission-no-admin', contract['permissions']['admin_risk_trader_implicit_permission'] is False)
check('financial-booleans-all-false', contract['observation_fields']['all_authorization_booleans_literal_false'] ==
      ['financial_authorized', 'source_delivery_authorized', 'execution_authorized'])
check('opaque-local-only', contract['observation_fields']['all_handles_local_pid_boot_current_thread_object_registry_bound'] is True)
check('same-auth-transaction', contract['lock_and_single_core']['grant_mutation_and_acceptance'] == 'same AuthDB BEGIN IMMEDIATE')
check('no-cross-db-proof', contract['lock_and_single_core']['h0_proves_cross_database_barrier'] is False)
check('no-caller-authority-injection', contract['lock_and_single_core']['no_caller_supplied_principal_authenticator_sql_callback'] is True)
check('old-return-preserved-and-no-new-subclass', any('Credential unchanged' == row['return']
      and 'not a NonceStore subclass' in row['behavior'] for row in contract['api']))
check('lookup-auth-only', any('lookup(' in row['symbol'] and 'no query and empty body' in row['behavior'] and
      'AuthDB' in row['return'] for row in contract['api']))
check('nonce-business-denial-deterministic', any(row.get('new_nonce_committed') is True and
      row.get('denial_audit_committed') is True and 'malformed business' in row['case']
      for row in contract['nonce_policy']))
check('unknown-not-forged-handle', any('reply loss' in row['case'] and 'no success handle' in row['result']
      for row in contract['nonce_policy']))
check('permanent-records-no-ttl-eviction', contract['capacities']['grants_and_audit_retained_permanently'] is True and
      contract['capacities']['eviction_or_ttl_reset_of_accepted_unknown_identity'] is False)
check('existing-cid-no-new-count', contract['capacities']['existing_cid_and_query_increment_acceptance_count'] is False)

# This is regular-expression text enumeration, not SQL syntax/grammar parsing.
objects = re.findall(r'^CREATE (TABLE|INDEX|TRIGGER) main\.([a-z_]+)', ddl, re.M)
check('34-explicit-named-DDL-objects', len(objects) == 34 and len({name for _, name in objects}) == 34)
tables = [name for kind, name in objects if kind == 'TABLE']
check('seven-main-table-names', tables == contract['schema']['tables'] and len(tables) == 7)
check('all-explicit-create-main-qualified', len(re.findall(r'^CREATE ', ddl, re.M)) == len(objects))
check('format2-ddl-literal', "CHECK(typeof(format)='integer' AND format=2)" in ddl)
check('immutable-business-unique-key', 'UNIQUE(domain_id,tenant,account_id,command_id)' in ddl)
check('actual-audit-key-grant-binding-text', 'auth_credit_acceptances_audit' in ddl and
      'auth_credit_acceptances_active_grant' in ddl and 'auth_credit_acceptances_authority' in ddl)
for table in contract['schema']['tables']:
    check('no-replace-explicit:' + table, any(name == table + '_no_replace' for _, name in objects))
for table in ('auth_audit', 'auth_credit_grants', 'auth_credit_grant_revocations', 'auth_credit_acceptances'):
    for action in ('update', 'delete'):
        check('retained-evidence-guard:' + table + ':' + action,
              any(name == table + '_no_' + action for _, name in objects))
check('strict-prune-boundary-text', 'OLD.expires_ms >= (SELECT highwater FROM main.auth_config' in ddl)
check('existing-key-upsert-implementation-caution', 'auth_keys_no_replace BEFORE INSERT' in ddl)

caps, defaults = contract['capacities'], contract['capacities']['defaults']
check('ordinary-nonce-threshold', caps['ordinary_nonce_limit'] == defaults['max_nonces'] - defaults['query_nonce_reserve'] == 1920)
check('query-nonce-threshold', caps['eligible_query_nonce_limit'] == defaults['max_nonces'] == 2048)
check('ordinary-audit-threshold', caps['ordinary_audit_limit'] == defaults['max_audit'] -
      defaults['query_audit_reserve'] - defaults['control_audit_reserve'] == 7616)
check('query-audit-threshold', caps['eligible_query_audit_limit'] == defaults['max_audit'] -
      defaults['control_audit_reserve'] == 8128)
check('control-audit-threshold', caps['trusted_control_audit_limit'] == defaults['max_audit'] == 8192)
check('ordinary-handle-threshold', caps['ordinary_handle_limit'] == defaults['max_handles'] - defaults['query_handle_reserve'] == 224)
check('query-handle-threshold', caps['eligible_query_handle_limit'] == defaults['max_handles'] == 256)

# Idealized admission classification at boundaries, not a live queue/lock proof.
model_cases = []
for n, a, h, route, read, operation in itertools.product(
        (1919,1920,2047,2048), (7615,7616,8127,8128,8191,8192), (223,224,255,256),
        ('ordinary','lookup','same-cid-retry','conflicting-retry'), (False,True), (False,True)):
    eligible = read and (route == 'lookup' or route == 'same-cid-retry' and operation)
    n_limit = caps['eligible_query_nonce_limit'] if eligible else caps['ordinary_nonce_limit']
    a_limit = caps['eligible_query_audit_limit'] if eligible else caps['ordinary_audit_limit']
    h_limit = caps['eligible_query_handle_limit'] if eligible else caps['ordinary_handle_limit']
    admitted = n < n_limit and a < a_limit and h < h_limit
    check('quota-classification:' + str(len(model_cases)), not admitted or
          eligible or n < 1920 and a < 7616 and h < 224)
    model_cases.append({'n':n, 'a':a, 'h':h, 'route':route, 'read':read, 'operation':operation,
                        'eligible':eligible, 'admitted':admitted})
boundary = [row for row in model_cases if row['n']==1920 and row['a']==7616 and row['h']==224]
check('genuine-query-survives-ordinary-full', any(row['route']=='lookup' and row['read'] and row['admitted'] for row in boundary))
check('unauthorized-query-does-not-use-reserve', not any(row['route']=='lookup' and not row['read'] and row['admitted'] for row in boundary))
check('same-cid-retry-needs-read-and-operation', not any(row['route']=='same-cid-retry' and
      (not row['read'] or not row['operation']) and row['admitted'] for row in boundary))

print(json.dumps({'reviewed_fixed_commit':REF, 'input_sha256':inputs, 'checks':checks,
    'check_count':len(checks), 'explicit_ddl_text_objects':len(objects),
    'explicit_ddl_text_tables':tables, 'sqlite_autoindex_inventory_verified':False,
    'quota_model_cases':len(model_cases), 'quota_boundary_examples':boundary,
    'model_assumptions':['current key/time already validated on the same held AuthDB connection',
        'route/grant/first-CID classification reads authoritative state without granting execution',
        'idealized integer counts, no concurrent SQLite/registry execution'],
    'sql_parsing_or_execution':False, 'product_import':False, 'runtime_acceptance':False,
    'result':'PASS_STATIC_CONTRACT_AND_DECLARED_QUOTA_MODEL_ONLY'}, indent=2))
