"""Sparse-plan verification: frozen stdlib helper, source AST and git metadata."""
import ast
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
FROZEN = Path('/workspace/uta-credit-v2-py310-candidate')
SOURCE = '909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0'
PROFILE = ROOT/'benchmarks/profiles/managed-909acec-v1-pending.json'
OUT = Path(__file__).resolve().parent


def git(*args):
    return subprocess.check_output(['git','--no-optional-locks',*args],cwd=FROZEN,text=True).strip()


def main():
    sys.dont_write_bytecode = True
    sys.path.insert(0,str(FROZEN))
    spec = importlib.util.spec_from_file_location('frozen_909_prepare',FROZEN/'tools/prepare_managed_stability.py')
    prepare = importlib.util.module_from_spec(spec)
    with patch.object(subprocess,'Popen',side_effect=AssertionError('operational child forbidden')):
        spec.loader.exec_module(prepare)
        value = prepare.profile(PROFILE)
        recipes = prepare.commands(value,record='startup-001.json')
        try:
            prepare.authorized(value,PROFILE,prepare.fingerprint(PROFILE))
        except ValueError as error:
            rejected = str(error)
        else:
            raise AssertionError('pending source must not execute')
    from tools import managed_output_budget as budget
    assert Path(prepare.__file__).resolve()==FROZEN/'tools/prepare_managed_stability.py'
    assert Path(budget.__file__).resolve()==FROZEN/'tools/managed_output_budget.py'
    plan = json.loads(Path(value['plan']).read_bytes())
    assert budget.output_budget_bytes(plan)==2*1024**3
    assert rejected=='full_exact_source_qualification_not_complete'
    assert plan['qualification']['tests_each'] is None and value['qualification']['actual_executed_tests_each'] is None
    assert plan['qualification']['ci_runs']==[44132222411,44132321549]
    assert value['qualification']['status']=='PENDING'
    assert all(value['qualification'][key] is False for key in ('all_three_local_passed','all_eight_ci_passed','independent_new_package_passed'))
    assert value['resource_review']['old_observer_floor_approved'] is False
    assert not Path(value['smoke_scratch']).exists() and not Path(value['long_scratch']).exists()
    assert git('rev-parse','HEAD')==SOURCE and git('status','--porcelain','--untracked-files=all')==''
    names = git('ls-tree','-r','--name-only','HEAD').splitlines()
    assert len(names)==5518 and sum(name.startswith('uta/') for name in names)==62
    assert git('rev-parse','HEAD^{tree}')==plan['source_git_tree_oid']=='cee60bc0b5413551030300e065d0dcaac6a7ff55'
    configuration = ast.parse((FROZEN/'benchmarks/run_managed_soak.py').read_bytes())
    configuration = next(node for node in configuration.body if isinstance(node,ast.ClassDef) and node.name=='Configuration')
    defaults = {node.target.id:ast.literal_eval(node.value) for node in configuration.body
        if isinstance(node,ast.AnnAssign) and node.target.id in {'rate','worker_every','parent_every'}}
    maxdir = next(node.value for node in configuration.body if isinstance(node,ast.AnnAssign) and node.target.id=='max_directory_bytes')
    assert ast.dump(maxdir)==ast.dump(ast.parse('6 * 1024**3',mode='eval').body)
    assert defaults=={'rate':.25,'worker_every':30,'parent_every':300}
    old_hashes = {}
    for name in names:
        if name.startswith(('benchmarks/plans/','benchmarks/profiles/')):
            assert (ROOT/name).read_bytes()==(FROZEN/name).read_bytes()
            old_hashes[name]=sha256((FROZEN/name).read_bytes()).hexdigest()
    assert all(not (ROOT/name).exists() for name in ('uta','tools','tests','formal'))
    sparse_patterns = subprocess.check_output(['git','sparse-checkout','list'],cwd=ROOT,text=True).splitlines()
    assert all(pattern.startswith(('/benchmarks/plans/','/benchmarks/profiles/','/docs/','/evidence/','/scripts/')) for pattern in sparse_patterns)
    profile_hash = sha256(PROFILE.read_bytes()).hexdigest()
    wrapper = [value['python'],'-B',str(FROZEN/'tools/prepare_managed_stability.py'),
        '--profile',str(PROFILE),'--root-go-profile-sha256',profile_hash]
    phases = [('smoke-produce','smoke-produce','producer.json'),('smoke-startup','smoke-observe','startup-001.json'),
        ('smoke-normal-active','smoke-observe','normal-active-001.json'),
        ('smoke-planned-fault','smoke-observe','planned-fault-001.json'),('smoke-final','smoke-observe','final-001.json'),
        ('smoke-cold','smoke-cold','cold-001.json'),('smoke-strict-negative','smoke-strict-negative','strict-long-negative.json'),
        ('long-preflight','long-preflight','unused.json'),('long-start','long-start','unused.json')]
    review = {label:wrapper+['--invoke',phase,'--record',record] for label,phase,record in phases}
    for phase,command in recipes.items():
        assert command[0]==value['python'] and str(FROZEN) in command[2]
        assert not any(old in ' '.join(command) for old in ('763202d','dbc93e5','91e4ae4','8b7f544','d421df3','bb34b5f'))
        if phase.startswith('smoke-'):
            assert command[command.index('--commit')+1]==SOURCE
            assert command[command.index('--source')+1]==str(FROZEN)
            assert command[command.index('--report')+1]==value['validation_report']
    (OUT/'review-commands.json').write_text(json.dumps(dict(status='PENDING_REVIEW_ONLY_NO_GO',
        source_commit=SOURCE,profile_sha256=profile_hash,execution_authorized=False,
        each_phase_requires_specific_root_GO=True,eligible_successor_profile_required=True,
        wrapper_review_argv=review,frozen_direct_recipes=recipes,
        operator_fresh_free_threshold_for_all_phases_bytes=17_448_304_640,
        frozen_smoke_helper_admission_threshold_bytes=16_642_998_272,
        frozen_long_helper_admission_threshold_bytes=17_448_304_640),indent=2)+'\n')
    result = dict(source_commit=SOURCE,source_git_tree_oid=git('rev-parse','HEAD^{tree}'),
        root_reported_runtime_sha256=plan['root_reported_runtime_sha256'],runtime_sha256_independently_verified=False,
        runtime_git_subtree_oid=git('rev-parse','HEAD:uta'),frozen_head_clean=True,source_tracked_files=5518,runtime_files=62,
        tests_each=None,original_ci_runs=[44132222411,44132321549],ci_status='ROOT_REPORTED_ATTEMPT1_IN_PROGRESS',
        independent_package_passed=False,floor_approved=False,authorization_rejection=rejected,
        old_plan_profile_sha256=old_hashes,sparse_checkout_patterns=sparse_patterns,own_runtime_code_copied=False,
        helper_sha256=sha256(Path(prepare.__file__).read_bytes()).hexdigest(),
        budget_helper_sha256=sha256(Path(budget.__file__).read_bytes()).hexdigest(),
        source_job_sql_executed=False,cohost_sampled=False,default_prepare_or_invoke_called=False,
        services_started=False,new_job_directories_created=False,execution_authorized=False,
        current_free_bytes=None,new_job_clock_uses_own_active_start_plus21600=True,
        truncated_to_old_24h_deadline=False)
    (OUT/'verification.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(json.dumps({key:result[key] for key in ('source_commit','source_tracked_files','runtime_files','tests_each',
        'authorization_rejection','own_runtime_code_copied','execution_authorized')}))


if __name__=='__main__':
    main()
