"""Only inspect the input-closure revision and retained materialization metadata."""
import ast
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess

ROOT = Path('/workspace/uta-spawn-full3-closure-plan')
FINAL = 'e41861d582b73610342164a76e3fb6104f023717'
OLD = '8ad9bf67e8890489b5276a319b7e41845a5c4b7b'
SOURCE = '6b7d473c0fbf92b17c146140c88eb2c25d38dce1'
PREFIX = 'evidence/plans/spawn-recovery-full3/'
NEW = PREFIX + 'full-tracked-closure-preparation/'
def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)
def blob(name, revision=FINAL):
    return git('show', revision + ':' + name)
def load(name):
    return json.loads(blob(NEW + name))
current = blob('tools/run_spawn_recovery_full3.py')
old = blob('tools/run_spawn_recovery_full3.py', OLD)
new_ast, old_ast = ast.parse(current), ast.parse(old)
functions = lambda tree: {node.name: ast.dump(node, include_attributes=False)
                         for node in tree.body if isinstance(node, ast.FunctionDef)}
nf, of = functions(new_ast), functions(old_ast)
plan = load('full-tracked-closure-prepare-first.json')
previous = json.loads(blob(PREFIX + 'first-execution-no-go/admission.json', OLD))
complete = load('all-tracked-materialization-complete.json')
allocation = load('all-tracked-materialization-closure-allocation.json')
admission = load('all-tracked-fresh-materialization-admission.json')
manifest = load('manifest.json')
baseline_path = Path('/workspace/uta-spawn-full3-preparation-6b7-20261117/all-tracked-existing-input-baseline.json')
before = baseline_path.stat()
fd = os.open(baseline_path, os.O_RDONLY | os.O_NOATIME | os.O_NOFOLLOW)
try:
    with os.fdopen(fd, 'rb', closefd=False) as stream:
        baseline_data = stream.read()
finally:
    os.close(fd)
baseline = json.loads(baseline_data)
stat_keys = ('st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_atime_ns')
baseline_stat_unchanged = all(getattr(before, key) == getattr(baseline_path.stat(), key) for key in stat_keys)
tracked = {}
for line in git('ls-tree', '-l', '-r', SOURCE).decode().splitlines():
    header, name = line.split('\t', 1)
    mode, kind, oid, size = header.split()
    tracked[name] = {'mode': mode, 'git_blob': oid, 'bytes': int(size)}
full = plan['source']['all_tracked_source_sha256']
rows = allocation['all_tracked']
new_output = '/workspace/uta-spawn-full3-validation/6b7d473-tracked-closure-once02'
checks = {
    'reviewed_controller_exact': sha256(current).hexdigest() == 'b66632ccf60e61ceecd23394fc6cf41eaeeb0bb413df039d28fc74c2ffc9a594'
        == plan['supervisor_sha256'],
    'all_other_functions_unchanged': set(nf) == set(of) and all(nf[name] == of[name]
        for name in nf if name not in {'source_pin', 'main'}),
    'source_pin_queries_entire_git_tree_and_checks_each_blob': 'git("ls-tree", "-r", COMMIT).splitlines()'
        in current.decode() and 'all_tracked_source_sha256' in current.decode(),
    'full_map_contains_every_tracked_path': len(full) == len(tracked) == 6162 and set(full) == set(tracked),
    'separate_standard_map_exactly_unchanged': len(plan['source']['standard_runner_source_sha256']) == 351
        and plan['source']['standard_runner_source_sha256'] == previous['source']['standard_runner_source_sha256'],
    'materialization_hash_map_matches_prepare_full_map': complete['all_tracked_sha256'] == full
        and complete['all_match_Git'] is True and complete['source'] == SOURCE,
    'allocation_full_inventory_matches_exact_git_objects_and_sizes': len(rows) == 6162
        and all({key: row[key] for key in ('mode', 'git_blob', 'bytes')} == tracked[row['name']] for row in rows)
        and sum(row['bytes'] for row in rows) == allocation['tracked_bytes'] == 169680991,
    'only_missing_inventory_was_approved': sum(not row['materialized'] for row in rows) == 5285
        == admission['missing_count'] and set(baseline) == {row['name'] for row in rows if row['materialized']},
    'baseline_private_hash_and_atime_preserved': sha256(baseline_data).hexdigest()
        == manifest['existing_877_baseline_private_sha256'] and baseline_stat_unchanged,
    'all_877_before_byte_hashes_equal_after_map': len(baseline) == complete['prior_existing_input_count'] == 877
        and all(row['sha256'] == full[name] for name, row in baseline.items()),
    'author_reports_zero_existing_stat_or_byte_changes': complete['prior_existing_byte_and_stat_changed'] == []
        and complete['original_874_map_preserved'] is True and complete['source_HEAD_unchanged'] is True,
    'fresh_storage_gate_and_post_materialization_reserve_hold': admission['free_before']
        >= admission['required_floor_reserve_allocation'] == plan['floor_bytes'] + plan['reserve_bytes']
        + allocation['new_materialization_conservative_bytes']
        and complete['free_after'] >= plan['floor_bytes'] + plan['reserve_bytes'],
    'new_output_and_original_fixed_budgets': all(argv[-1].startswith(new_output + '/') for argv in plan['commands'])
        and plan['per_runtime_seconds'] == 900 and plan['matrix_seconds'] == 2730 and plan['cpu'] == 4
        and not Path(new_output).exists(),
    'previous_failed_evidence_git_subtree_unchanged': not git('diff', '--name-only', OLD, FINAL, '--',
        PREFIX + 'first-execution-no-go'),
    'all_six_preparation_files_match_manifest': all(len(blob(NEW + name)) == row['bytes']
        and sha256(blob(NEW + name)).hexdigest() == row['sha256'] for name, row in manifest['files'].items()),
    'no_new_qa_claim_in_materialization_records': complete['new_QA_executed'] is False
        and manifest['new_QA_executed'] is False and manifest['new_QA_execution_authorized'] is False,
}
print(json.dumps({'reviewed_commit': FINAL, 'source_commit': SOURCE, 'checks': checks,
    'all_checks': all(checks.values()), 'source_files_reopened': 0,
    'scope': 'Git/AST/materialization-metadata only; no pure suite, prepare, QA, SQL or signal execution.',
    'stat_validation_limit': '877 before hashes independently match retained after map. Zero after-stat changes are author observation; no separately retained full after-stat table was available.',
    'new_output': new_output, 'production_approved': False}, indent=2, sort_keys=True))
assert all(checks.values())
