"""Read-only Git/AST/evidence binding audit; does not import/run the controller."""
import ast
from hashlib import sha256
import json
from pathlib import Path
import subprocess

ROOT = Path('/workspace/uta-spawn-full3-clean')
FINAL = '7ec6f31abacd9c2eeb6bda52a2b69cffabeed8c8'
BASE = '6b7d473c0fbf92b17c146140c88eb2c25d38dce1'
FIXED = 'ff814d4bcaee079b0e0503ea8072c24e3563c443'
EXPECTED = '084a9aa9b1fa357c0f485ea92a19b9185948361f7740aeff16c5f84966b7dabd'
PREFIX = 'evidence/plans/spawn-recovery-full3/'
def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)
def blob(name):
    return git('show', FINAL + ':' + name)
source = blob('tools/run_spawn_recovery_full3.py')
tree = ast.parse(source)
values = {node.targets[0].id: ast.literal_eval(node.value) for node in tree.body
          if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
          and node.targets[0].id in {'COMMIT', 'CPU', 'RUNTIME_SECONDS', 'MATRIX_SECONDS',
                                   'EXPECTED_TESTS', 'EXPECTED_RUNTIME', 'LOADER_OVERRIDES'}}
plan = json.loads(blob(PREFIX + 'full-input-pin-end-receipt-fixed.json'))
builds = json.loads(blob(PREFIX + 'original-runtime-build-provenance.json'))
raw = blob(PREFIX + 'controller-end-receipt-fixed-first.txt')
prepare = json.loads(blob(PREFIX + 'prepare-end-receipt-fixed.txt'))
doc = blob('docs/spawn-recovery-full3-plan.md').decode()
changes = git('diff', '--name-status', BASE, FINAL).decode().splitlines()
functions = {node.name: ast.get_source_segment(source.decode(), node)
             for node in tree.body if isinstance(node, ast.FunctionDef)}
checks = {
    'final_checkout_exact_and_clean': git('rev-parse', 'HEAD').decode().strip() == FINAL
        and not git('status', '--porcelain', '--untracked-files=all'),
    'controller_git_and_materialized_hash_exact': sha256(source).hexdigest() == EXPECTED
        == sha256((ROOT / 'tools/run_spawn_recovery_full3.py').read_bytes()).hexdigest(),
    'fixed_source_and_original_budgets_bound': values['COMMIT'] == BASE
        and values['CPU'] == 4 and values['RUNTIME_SECONDS'] == 900
        and values['MATRIX_SECONDS'] == 2730 and values['EXPECTED_TESTS'] == 1813,
    'financial_runtime_blobs_unchanged_from_fixed': git('ls-tree', '-r', FIXED, '--', 'uta')
        == git('ls-tree', '-r', BASE, '--', 'uta'),
    'plan_only_adds_files_over_frozen_source': len(changes) == 21
        and all(line.startswith('A\t') for line in changes),
    'retained_prepare_binds_final_controller': plan['supervisor_sha256'] == EXPECTED
        == prepare['supervisor_sha256'] and prepare['prepare_only'] is True,
    'retained_source_maps_and_counts_consistent': len(plan['source']['standard_runner_source_sha256'])
        == prepare['selected_input_count'] == 351
        and len(plan['source']['all_tracked_QA_input_sha256'])
        == prepare['all_QA_input_count'] == 874 and plan['source']['commit'] == BASE,
    'actual_runtime_expected_values_equal_retained_provenance': values['EXPECTED_RUNTIME']
        == {label: {key: row[key] for key in ('python', 'sqlite')} for label, row in builds.items()}
        == plan['expected_runtime_builds'],
    'loader_overrides_rejected_at_admission_supervisor_and_runtime': all(
        'reject_loader_overrides(' in functions[name] for name in ('plan', 'supervise', 'run_one'))
        and set(values['LOADER_OVERRIDES']) == {'PYTHONHOME', 'LD_LIBRARY_PATH', 'LD_PRELOAD',
                                              'PYTHONUSERBASE', 'PYTHONSTARTUP'},
    'actual_runtime_report_compares_expected_build': 'EXPECTED_RUNTIME[label].items()'
        in functions['validate_report'],
    'unknown_go_marked_before_write': functions['launch_detached'].index('may_have_delivered = True')
        < functions['launch_detached'].index('os.write(write_fd, b"G")')
        and 'process is not None and not may_have_delivered' in functions['launch_detached'],
    'new_adopted_live_children_checked_before_reaper_exit': 'baseline = direct_children()'
        in functions['run_one'] and 'LIVE_ADOPTED_OTHER_SESSION_UNKNOWN' in functions['run_one']
        and 'adopted_before_reaper_exit' in functions['run_one'],
    'whole_clock_checks_after_end_and_post_end': 'matrix-end.json' in functions['finish_matrix']
        and 'matrix-post-end.json' in functions['finish_matrix']
        and 'FINALIZATION_EXCEEDED_MATRIX_BUDGET' in functions['finish_matrix']
        and 'POST_END_RECORD_EXCEEDED_MATRIX_BUDGET' in functions['finish_matrix'],
    'acceptance_requires_actual_normal_supervisor_exit': 'actual normal final supervisor exit with status zero'
        in doc and 'completion stays UNKNOWN' in doc,
    'author_original_pure_log_reports_sixteen_passes': raw.count(b') ... ok\n') == 16
        and b'Ran 16 tests in 0.008s\n\nOK\n' in raw,
}
print(json.dumps({'reviewed_commit': FINAL, 'controller_sha256': EXPECTED,
    'scope': 'read-only Git/AST/hash; original author pure log only, not independently rerun',
    'checks': checks, 'all_checks': all(checks.values()),
    'author_evidence_sha256': {name: sha256(blob(PREFIX + name)).hexdigest() for name in (
        'controller-end-receipt-fixed-first.txt', 'prepare-end-receipt-fixed.txt',
        'full-input-pin-end-receipt-fixed.json', 'original-runtime-build-provenance.json')},
    'runtime_provenance_limit': 'Retained provenance fields/hash references verified; original H0 summaries not reopened.',
    'no_new_qa_sql_native_or_test_execution': True,
    'production_approved': False, 'original_ci_cause_proven': False}, indent=2, sort_keys=True))
assert all(checks.values())
