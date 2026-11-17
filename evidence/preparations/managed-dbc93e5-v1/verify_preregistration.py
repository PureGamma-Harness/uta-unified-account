"""Read-only source metadata/AST and pure profile parsing; never an invocation."""
import ast
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
FROZEN = Path('/workspace/uta-combined-freeze-dbc93e5')
SOURCE = 'dbc93e5d50125e6ab8f1154511a537f8b1a8fa1b'
PROFILE = ROOT/'benchmarks/profiles/managed-dbc93e5-v1-pending.json'
OUT = Path(__file__).resolve().parent


def git(*args):
    return subprocess.check_output(['git','--no-optional-locks',*args],cwd=FROZEN,text=True).strip()


def main():
    sys.dont_write_bytecode = True
    sys.path.insert(0,str(FROZEN))
    spec = importlib.util.spec_from_file_location('frozen_dbc_prepare', FROZEN/'tools/prepare_managed_stability.py')
    prepare = importlib.util.module_from_spec(spec)
    with patch.object(subprocess,'Popen',side_effect=AssertionError('no operational subprocess')):
        spec.loader.exec_module(prepare)
        value = prepare.profile(PROFILE)
        recipes = prepare.commands(value,record='startup-001.json')
        try:
            prepare.authorized(value,PROFILE,prepare.fingerprint(PROFILE))
        except ValueError as error:
            rejected = str(error)
        else:
            raise AssertionError('CI-blocked v1 must not execute')
    from tools import managed_output_budget as budget
    assert Path(prepare.__file__).resolve() == FROZEN/'tools/prepare_managed_stability.py'
    assert Path(budget.__file__).resolve() == FROZEN/'tools/managed_output_budget.py'
    plan = json.loads(Path(value['plan']).read_bytes())
    assert budget.output_budget_bytes(plan) == 2*1024**3
    assert rejected == 'full_exact_source_qualification_not_complete'
    assert plan['qualification']['tests_each'] is None
    assert plan['qualification']['ci_runs'] == [44125869999,44125881372]
    assert plan['qualification']['ci_failed_python_jobs'] == 2 and plan['qualification']['ci_failure_cause'] is None
    assert value['qualification']['actual_executed_tests_each'] is None
    assert all(value['qualification'][key] is False for key in ('all_three_local_passed','all_eight_ci_passed','independent_new_package_passed'))
    assert value['resource_review']['old_observer_floor_approved'] is False
    assert not Path(value['smoke_scratch']).exists() and not Path(value['long_scratch']).exists()
    assert git('rev-parse','HEAD') == SOURCE and git('status','--porcelain','--untracked-files=all') == ''
    names = git('ls-tree','-r','--name-only','HEAD').splitlines()
    assert len(names) == 5159 and sum(name.startswith('uta/') for name in names) == 62
    assert git('rev-parse','HEAD^{tree}') == plan['source_git_tree_oid']
    configuration = ast.parse((FROZEN/'benchmarks/run_managed_soak.py').read_bytes())
    configuration = next(node for node in configuration.body if isinstance(node,ast.ClassDef) and node.name=='Configuration')
    defaults = {node.target.id:ast.literal_eval(node.value) for node in configuration.body
        if isinstance(node,ast.AnnAssign) and node.target.id in {'rate','worker_every','parent_every'}}
    maxdir = next(node.value for node in configuration.body if isinstance(node,ast.AnnAssign) and node.target.id=='max_directory_bytes')
    assert isinstance(maxdir,ast.BinOp) and ast.dump(maxdir)==ast.dump(ast.parse('6 * 1024**3',mode='eval').body)
    assert defaults == {'rate':.25,'worker_every':30,'parent_every':300}
    smoke_ast = ast.parse((FROZEN/'tools/managed_observer_smoke.py').read_bytes())
    smoke_producer = next(node.value for node in ast.walk(smoke_ast) if isinstance(node,ast.Assign)
        and any(isinstance(t,ast.Name) and t.id=='producer' for t in node.targets))
    smoke_literals = [node.value for node in smoke_producer.elts if isinstance(node,ast.Constant)]
    for flag, expected in (('--duration','60'),('--worker-every','5'),('--parent-every','10')):
        assert smoke_literals[smoke_literals.index(flag)+1] == expected
    profile_hash = sha256(PROFILE.read_bytes()).hexdigest()
    wrapper_base = [value['python'],'-B',str(FROZEN/'tools/prepare_managed_stability.py'),
        '--profile',str(PROFILE),'--root-go-profile-sha256',profile_hash]
    review = {}
    for label,phase,record in (
        ('smoke-produce','smoke-produce','producer.json'),
        ('smoke-startup','smoke-observe','startup-001.json'),
        ('smoke-normal-active','smoke-observe','normal-active-001.json'),
        ('smoke-planned-fault','smoke-observe','planned-fault-001.json'),
        ('smoke-final','smoke-observe','final-001.json'),
        ('smoke-cold','smoke-cold','cold-001.json'),
        ('smoke-strict-long-negative','smoke-strict-negative','strict-long-negative.json'),
        ('long-preflight','long-preflight','unused.json'),('long-start','long-start','unused.json')):
        review[label] = wrapper_base+['--invoke',phase,'--record',record]
    for phase,command in recipes.items():
        assert command[0] == value['python'] and str(FROZEN) in command[2]
        assert not any(old in ' '.join(command) for old in ('763202d','91e4ae4','8b7f544','d421df3','bb34b5f'))
        if phase.startswith('smoke-'):
            assert command[command.index('--commit')+1] == SOURCE
            assert command[command.index('--source')+1] == str(FROZEN)
            assert command[command.index('--report')+1] == value['validation_report']
    old_hashes = {}
    for name in names:
        if name.startswith(('benchmarks/plans/','benchmarks/profiles/')):
            old = subprocess.check_output(['git','--no-optional-locks','show',f'{SOURCE}:{name}'],cwd=FROZEN)
            assert (ROOT/name).read_bytes() == old
            old_hashes[name] = sha256(old).hexdigest()
    payload = dict(status='REVIEW_ONLY_CURRENT_V1_CI_NO_GO',source_commit=SOURCE,
        qualification_complete=False, execution_authorized=False, service_started=False,
        future_eligible_profile_must_be_separately_versioned=True, no_automatic_phase_sequence=True,
        root_phase_GO_required=True, profile_sha256=profile_hash, frozen_direct_recipes=recipes,
        trusted_wrapper_review_argv=review, blocked_command_execution_permitted=False)
    (OUT/'review-commands.json').write_text(json.dumps(payload,indent=2)+'\n')
    checked = dict(source_commit=SOURCE,source_git_tree_oid=git('rev-parse','HEAD^{tree}'),
        root_reported_source_tree_sha256=plan['root_reported_source_tree_sha256'],root_reported_tree_sha256_independently_verified=False,
        source_head_and_clean_status_verified=True,source_tracked_files=len(names),runtime_files=62,
        tests_each=None,ci_status='ACTUAL_NO_GO_TWO_PYTHON310_UNIT_FAILURES',ci_failure_cause=None,
        package_passed=False,floor_approved=False,authorization_rejection=rejected,
        original_configuration_defaults=defaults,original_source_budget_bytes=6*1024**3,
        explicit_output_budget_bytes=2*1024**3,new_resource_reservation_bytes=10*1024**3,
        combined_fresh_free_threshold_bytes=17_448_304_640,current_free_bytes=None,
        current_gap_bytes=None,original_plan_profile_sha256=old_hashes,
        helper_sha256=sha256(Path(prepare.__file__).read_bytes()).hexdigest(),
        budget_helper_sha256=sha256(Path(budget.__file__).read_bytes()).hexdigest(),
        source_job_sql_executed=False,cohost_sampled=False,default_prepare_or_invoke_called=False,
        services_started=False,new_job_directories_created=False,execution_authorized=False)
    (OUT/'verification.json').write_text(json.dumps(checked,sort_keys=True,indent=2)+'\n')
    print(json.dumps({key:checked[key] for key in ('source_commit','source_tracked_files','runtime_files',
        'tests_each','ci_status','authorization_rejection','execution_authorized')}))


if __name__ == '__main__':
    main()
