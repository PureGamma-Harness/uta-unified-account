"""Read Git bytes/AST and finite in-memory models; never import product code."""
from collections import deque
from datetime import datetime, timezone
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import time

BASE = 'dbc93e5d50125e6ab8f1154511a537f8b1a8fa1b'
PLAN = '431225d01439cba1a4acce6529e35368eac391df'
PR18 = '01c332375d9a5463ca95d8e743ff5083b121982e'
REPO = Path(__file__).resolve().parents[3]
checks = []
started = datetime.now(timezone.utc).isoformat()
cpu_started = time.process_time_ns()

def git_blob(commit, path):
    return subprocess.check_output(['git', 'show', commit + ':' + path], cwd=REPO)

def check(name, condition):
    if not condition:
        raise AssertionError(name)
    checks.append(name)

def method(module, class_name, method_name):
    cls = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == class_name)
    return next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == method_name)

def calls_named(node, name):
    return [item for item in ast.walk(node) if isinstance(item, ast.Call)
            and isinstance(item.func, ast.Attribute) and item.func.attr == name]

contract = json.loads(git_blob(PLAN, 'docs/contracts/credit-v2-hmac-bridge-v1.json'))
plan_text = git_blob(PLAN, 'docs/credit-v2-hmac-integration-plan.md').decode()
inputs = {}
for commit, key in [(BASE, 'inputs_sha256'), (PR18, 'pr18_inputs_sha256')]:
    for path, expected in contract[key].items():
        data = git_blob(commit, path)
        actual = hashlib.sha256(data).hexdigest()
        check('source:' + commit[:7] + ':' + path, actual == expected)
        inputs[commit[:7] + ':' + path] = actual
check('status-design-only', contract['status'] == 'DESIGN_ONLY_NOT_IMPLEMENTED')
check('no-implemented-connection', contract['implemented_connection'] is False)
for name in ('production_approved', 'public_borrow_enabled', 'general_trading_ready'):
    check(name + '-false', contract[name] is False)
cases = contract['test_plan']
check('thirty-unique-case-ids', len(cases) == len({row['id'] for row in cases}) == 30)
check('all-original-cases-not-run', all(row['execution_status'] == 'NOT_RUN' for row in cases))
check('original-case-execution-needs-root', all(row['requires_separate_root_phase_go'] is True for row in cases))
check('all-phase-execution-unapproved', all(row['execution_authorized'] is False for row in contract['phases']))
check('logical-key-excludes-epoch-kind-hash', contract['canonical_business_key'] ==
      ['domain_id', 'tenant_namespace', 'account_id', 'business_CID'])
check('H0-no-financial-source-or-listener', contract['phases'][0]['new_financial_source'] is False
      and contract['phases'][0]['http_listener'] is False)

auth = ast.parse(git_blob(BASE, 'uta/request_signing.py'))
gateway = ast.parse(git_blob(BASE, 'uta/durable_gateway.py'))
ordinary = ast.parse(git_blob(BASE, 'uta/gateway.py'))
source = ast.parse(git_blob(PR18, 'uta/credit_hmac_source.py'))
authenticate = method(auth, 'RequestAuthenticator', 'authenticate')
consume = method(auth, 'NonceStore', 'consume')
audit = method(auth, 'NonceStore', '_audit')
handler = method(gateway, '_SignedDurableHandler', '_principal')
issue = method(source, 'CreditHmacSource', 'issue')
check('one-existing-authenticate-consume-call', len(calls_named(authenticate, 'consume')) == 1)
check('existing-authenticate-returns-principal', ast.unparse(authenticate).rstrip().endswith('return key.principal()'))
check('existing-consume-no-receipt-return', not any(isinstance(node, ast.Return) and node.value is not None
      for node in ast.walk(consume)))
check('existing-audit-no-sequence-return', not any(isinstance(node, ast.Return) and node.value is not None
      for node in ast.walk(audit)))
check('existing-handler-already-authenticates', len(calls_named(handler, 'authenticate')) == 1)
check('PR18-issue-authenticates-again-if-naively-routed', len(calls_named(issue, 'authenticate')) == 1)
columns = next(node.value for node in auth.body if isinstance(node, ast.Assign)
               and any(isinstance(target, ast.Name) and target.id == '_COLUMNS' for target in node.targets))
columns = ast.literal_eval(columns)
check('old-auth-key-row-has-only-three-fields', columns['auth_keys'] == {'key_id', 'identity', 'revoked'})
check('old-format1-is-explicit', "rows[0]['format'] != 1" in ast.unparse(method(auth, 'NonceStore', '_config')))
check('ordinary-permit-has-admin-bypass', "principal.role != 'admin'" in ast.unparse(method(ordinary, '_Handler', '_permit')))
dicts = [node for node in ast.walk(issue) if isinstance(node, ast.Dict)]
fields = {key.value: value.value for node in dicts for key, value in zip(node.keys, node.values)
          if isinstance(key, ast.Constant) and isinstance(value, ast.Constant)}
for key in ('auth_audit_sequence', 'accepted_profile_revision', 'credential_epoch'):
    check('PR18-original-null:' + key, fields.get(key, 'MISSING') is None)
check('PR18-financial-deny', fields['financial_authorized'] is False and fields['revocation_barrier'] == 'NO_GO')
check('nonce-policy-wording-difference-retained', 'valid-auth nonce may be consumed' in
      next(row['expected_proposed_behavior'] for row in cases if row['id'] == 'HC-04')
      and 'nonce plus denial audit commit' in
      next(row['expected_proposed_behavior'] for row in cases if row['id'] == 'HC-07'))

# Finite logical reservation model, not an implementation or runtime proof.
# Grants 0/1 are initially active; grant 2 is a later regrant. Revoked IDs stay
# tombstoned. The immutable first reservation carries its original grant/payload.
initial = (3, 0, -1, -1)
queue, visited = deque([initial]), {initial}
edges = 0
while queue:
    state = queue.popleft()
    active, revoked, first_grant, first_payload = state
    outcomes = []
    for grant in range(3):
        bit = 1 << grant
        if active & bit:
            outcomes.append(((active & ~bit, revoked | bit, first_grant, first_payload), 'revoke'))
            for payload in range(2):
                target = state if first_grant != -1 else (active, revoked, grant, payload)
                outcomes.append((target, 'submit'))
        if grant == 2 and not active & bit and not revoked & bit:
            outcomes.append(((active | bit, revoked, first_grant, first_payload), 'new-grant'))
    for target, action in outcomes:
        edges += 1
        check('first-identity-preserved-edge-' + str(edges), first_grant == -1 or target[2:] == state[2:])
        check('revoked-id-never-reactivated-edge-' + str(edges), target[0] & target[1] == 0)
        if target not in visited:
            visited.add(target)
            queue.append(target)

# A deliberately unsafe policy rebinds the old reservation to the retry's
# current grant. It is a design counterexample, not an exploit of current code.
counterexample = [
    {'action': 'accept original CID under grant0', 'state': [3, 0, 0, 0]},
    {'action': 'revoke grant0', 'state': [2, 1, 0, 0]},
    {'action': 'same CID/payload retry under active grant1; unsafe rebind', 'state': [2, 1, 1, 0]},
]
check('mutant-changes-first-identity', counterexample[0]['state'][2:] != counterexample[-1]['state'][2:])
check('safe-original-grant-is-revoked', not counterexample[1]['state'][0] & (1 << counterexample[1]['state'][2]))
check('mutant-would-see-new-grant-active', bool(counterexample[-1]['state'][0] & (1 << counterexample[-1]['state'][2])))

atomic_cases = [
    {'case': 'valid-auth-role-denied', 'nonce': 1, 'denial_audit': 1, 'accepted': 0, 'reservation': 0, 'handle': 0},
    {'case': 'accepted-returned', 'nonce': 1, 'denial_audit': 0, 'accepted': 1, 'reservation': 1, 'handle': 1},
    {'case': 'accepted-commit-reply-lost', 'nonce': 1, 'denial_audit': 0, 'accepted': 1, 'reservation': 1, 'handle': 0},
    {'case': 'precommit-rollback', 'nonce': 0, 'denial_audit': 0, 'accepted': 0, 'reservation': 0, 'handle': 0},
]
for row in atomic_cases:
    check('atomic-acceptance:' + row['case'], row['accepted'] == row['reservation'] and
          (not row['handle'] or row['accepted']) and not (row['denial_audit'] and row['accepted']))

result = {'reviewed_plan_commit': PLAN, 'base_source_commit': BASE, 'pr18_commit': PR18,
    'started_at': started, 'finished_at': datetime.now(timezone.utc).isoformat(),
    'process_cpu_ns': time.process_time_ns() - cpu_started,
    'check_count': len(checks), 'checks': checks, 'inputs_sha256': inputs,
    'bounded_model': {'states': len(visited), 'transitions': edges,
        'assumptions': ['finite three grant identities and two payload identities',
            'revoked grant IDs cannot be unrevoked', 'logical reservation never pruned',
            'transitions are idealized atomic logical steps; no SQLite or process execution'],
        'unsafe_rebind_counterexample': counterexample, 'atomic_policy_examples': atomic_cases},
    'implementation_or_dynamic_acceptance': False, 'product_import': False, 'sql_or_database_open': False,
    'production_approved': False, 'result': 'PASS_PURE_STATIC_AND_DECLARED_MODEL_ONLY'}
print(json.dumps(result, indent=2))
