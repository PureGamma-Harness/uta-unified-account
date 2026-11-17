"""Metadata/JSON-only validation using the exact frozen prepare helper."""
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
FROZEN = Path('/workspace/uta-observer-freeze-91e4ae4')
SOURCE = '91e4ae40b5e9b884c54026406299df5000c9c100'
PROFILE = ROOT/'benchmarks/profiles/managed-91e4ae4-v1-pending.json'
OUT = Path(__file__).resolve().parent


def main():
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(FROZEN))
    spec = importlib.util.spec_from_file_location('exact_frozen_prepare', FROZEN/'tools/prepare_managed_stability.py')
    prepare = importlib.util.module_from_spec(spec)
    with patch.object(subprocess, 'Popen', side_effect=AssertionError('operational process forbidden')):
        spec.loader.exec_module(prepare)
        value = prepare.profile(PROFILE)
        recipes = prepare.commands(value, record='startup-001.json')
        try:
            prepare.authorized(value, PROFILE, prepare.fingerprint(PROFILE))
        except ValueError as error:
            rejection = str(error)
        else:
            raise AssertionError('pending profile was executable')
    from tools import managed_output_budget as budget
    assert Path(prepare.__file__).resolve() == FROZEN/'tools/prepare_managed_stability.py'
    assert Path(budget.__file__).resolve() == FROZEN/'tools/managed_output_budget.py'
    plan = json.loads(Path(value['plan']).read_bytes())
    amendment = json.loads(Path(value['amendment']).read_bytes())
    assert budget.output_budget_bytes(plan) == 2*1024**3
    assert plan['producer']['source_budget_bytes'] == 6*1024**3
    assert plan['qualification']['tests_each'] is None and plan['qualification']['ci_runs'] is None
    assert value['qualification']['actual_executed_tests_each'] is None
    assert not any(value['qualification'][key] for key in ('all_three_local_passed', 'all_eight_ci_passed', 'independent_new_package_passed'))
    assert value['resource_review']['old_observer_floor_approved'] is False
    assert plan['observer']['interval_seconds'] == amendment['observer_interval_seconds_effective'] == 61
    assert rejection == 'full_exact_source_qualification_not_complete'
    assert not Path(value['smoke_scratch']).exists() and not Path(value['long_scratch']).exists()
    for phase, command in recipes.items():
        assert command[0] == value['python']
        assert '91e4ae4' in command[2] and not any(old in ' '.join(command) for old in ('763202d','bb34b5f','d421df3','8b7f544'))
        if phase.startswith('smoke-'):
            assert command[command.index('--commit')+1] == SOURCE
            assert command[command.index('--source')+1] == str(FROZEN)
            assert command[command.index('--report')+1] == value['validation_report']
    source_head = subprocess.check_output(['git','--no-optional-locks','rev-parse','HEAD'],cwd=FROZEN,text=True).strip()
    source_status = subprocess.check_output(['git','--no-optional-locks','status','--porcelain','--untracked-files=all'],cwd=FROZEN,text=True)
    listed = subprocess.check_output(['git','--no-optional-locks','ls-tree','-r','--name-only',SOURCE],cwd=ROOT,text=True).splitlines()
    assert source_head == SOURCE and source_status == '' and len(listed) == 3633
    old_names = [name for name in listed if name.startswith(('benchmarks/plans/','benchmarks/profiles/'))]
    old_hashes = {}
    for name in old_names:
        before = subprocess.check_output(['git','--no-optional-locks','show',f'{SOURCE}:{name}'],cwd=ROOT)
        assert (ROOT/name).read_bytes() == before
        old_hashes[name] = sha256(before).hexdigest()
    (OUT/'static-prepare.json').write_text(json.dumps(dict(
        status='STATIC_PREP_ONLY_NO_EXECUTION', source_commit=SOURCE, commands=recipes,
        selected_cpu=0, default_prepare_not_called=True, cohost_not_sampled=True,
        source_job_sql_executed=False, service_started=False, execution_authorized=False),indent=2)+'\n')
    result = dict(source_commit=SOURCE, source_root=str(FROZEN), frozen_head_matched=True,
        frozen_tracked_and_untracked_clean=True, source_tracked_files=len(listed),
        helper_sha256=sha256(Path(prepare.__file__).read_bytes()).hexdigest(),
        budget_helper_sha256=sha256(Path(budget.__file__).read_bytes()).hexdigest(),
        tests_each=None, ci_run_ids=None, qualification_pending=True, independent_package_passed=False,
        profile_authorization_rejection=rejection, old_observer_floor_approved=False,
        new_conservative_required_bytes=10*1024**3, combined_with_old_and_floor_bytes=17_448_304_640,
        current_free_bytes=None, current_combined_gap_bytes=None, physical_hard_quota_enforced=False,
        original_plan_profile_sha256=old_hashes, source_job_sql_executed=False,
        service_started=False, execution_authorized=False, new_job_directories_created=False,
        default_prepare_or_preflight_or_invoke_called=False)
    (OUT/'verification.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(json.dumps({key:result[key] for key in ('source_commit','source_tracked_files','tests_each',
        'profile_authorization_rejection','combined_with_old_and_floor_bytes','execution_authorized')}))


if __name__ == '__main__':
    main()
