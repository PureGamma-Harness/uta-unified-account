"""Create external source-pinned pending preregistration, never a job."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FROZEN = Path('/workspace/uta-credit-v2-py310-candidate')
SOURCE = '909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0'
REPORT = '/workspace/uta-combined-validation/final-909acec/python312/summary.json'
PYTHON = '/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python'
GIB = 1024**3
PREFIX = '20261117-managed-909acec-six-hours-v1'


def raw(value):
    return (json.dumps(value,indent=2)+'\n').encode()


def main():
    old_plan = FROZEN/'benchmarks/plans/20261117-managed-dbc93e5-six-hours-v1-pending.json'
    old_amend = FROZEN/'benchmarks/plans/20261117-managed-dbc93e5-six-hours-v1-observer-amendment.json'
    old_profile = FROZEN/'benchmarks/profiles/managed-dbc93e5-v1-pending.json'
    plan, amendment, profile = (json.loads(path.read_bytes()) for path in (old_plan,old_amend,old_profile))
    now = datetime.now(timezone.utc).isoformat()
    for key in ('source_commit','observer_core_commit','reviewed_observer_and_wrapper_commit'):
        plan[key] = SOURCE
    plan.update(status='PREREGISTERED_V1_PENDING_ACTUAL_QUALIFICATION_NO_EXECUTION',
        source_root=str(FROZEN),python=PYTHON,validation_report=REPORT,preregistered_at_utc=now,
        source_git_tree_oid='cee60bc0b5413551030300e065d0dcaac6a7ff55',
        root_reported_runtime_sha256='ec0fa09e2e2e50557300423ddf6983969c9727816288ed79e9de7a17438c5b2b',
        runtime_sha256_independently_verified=False,execution_authorized=False,service_started=False)
    for key in ('root_reported_source_tree_sha256','root_reported_tree_sha256_independently_verified'):
        plan.pop(key,None)
    plan['qualification'] = dict(status='PENDING_ALL_THREE_LOCAL_EIGHT_CI_AND_NEW_INDEPENDENT_PACKAGE',
        local_full_runs=3,tests_each=None,tests_each_status='PENDING_ACTUAL_ALL_THREE_EXACT_REPORTS',
        ci_runs=[44132222411,44132321549],ci_python_jobs=8,ci_runs_status='ATTEMPT1_IN_PROGRESS_AT_PREREGISTRATION',
        ci_actual_attempt=1,ci_successful_python_jobs=None,ci_failed_python_jobs=None,ci_artifact_count=None,
        package_tracked_files=None,source_tracked_files=5518,runtime_files=62,
        package_evidence='PENDING: fresh909 source/runtime artifacts and independent new package review',
        no_qualification_inherited_from_any_prior_source=True)
    plan['provider_context'] = dict(push_run_id=44132222411,pull_request_run_id=44132321549,
        attempt=1,status_at_preregistration='IN_PROGRESS',pull_request=21,
        pull_request_url='https://github.com/PureGamma-Harness/uta-unified-account/pull/21',
        actual_merge_sha='b221fce79e7709d6f1a36d0aff5c24225a61c084',
        actual_merge_parents=['dbc93e5d50125e6ab8f1154511a537f8b1a8fa1b',SOURCE],
        actual_merge_git_tree_oid='cee60bc0b5413551030300e065d0dcaac6a7ff55',
        metadata_record='/tmp/uta-credit-909-provider-metadata/initial-source-and-runs.json',
        qualifies_source=False)
    plan['resource_policy'].update(status='PENDING_OPERATOR_CONDITIONAL_FLOOR_REVIEW_AND_POST_QA_PACKAGE_PREFLIGHT',
        old_observer_additional_floor_bytes=256*1024**2,old_observer_floor_approved=False,
        old_observer_floor_conditional=True,old_observer_declared_byte_cap=None,
        separate_operator_record=None,separate_operator_record_sha256=None,
        current_free_bytes=None,current_gap_bytes=None,space_reserved=False,
        historical_1656_free_observation_is_not_post_qualification_package_preflight=True,
        source_metadata_maximum_age_seconds=15,actual_original_cohost_pid_birth_required=True)
    plan['previous_candidates'].append(dict(source_commit='dbc93e5d50125e6ab8f1154511a537f8b1a8fa1b',
        status='NO_GO_ACTUAL_TWO_PYTHON310_UNIT_FAILURES',
        immutable_profile='benchmarks/profiles/managed-dbc93e5-v1-pending.json',never_reclassify=True))
    plan['copied_preregistration'] = dict(source_plan_sha256=sha256(old_plan.read_bytes()).hexdigest(),
        source_amendment_sha256=sha256(old_amend.read_bytes()).hexdigest(),
        source_commit='dbc93e5d50125e6ab8f1154511a537f8b1a8fa1b',qualification_inherited=False,
        changed_fields='new exactsource/time/counts/provider pending facts; workload/financial/resource limits unchanged')
    plan['execution_gate'] = 'PREP ONLY. Every phase needs root specific GO after actual complete exact909 full3/CI8/freshpackage/floor review and fresh source/PIDbirth/TTL15/free gate. Pending v1 cannot execute; any failed gate remains NO_GO.'
    plan['independent_new_clock'] = dict(required_actual_active_seconds=21600,
        deadline_basis='this new job actual started_boottime_ns plus21600 seconds',
        old_24h_2136_deadline_applies_to_this_job=False,shorten_to_old_job_deadline_allowed=False,
        resume_or_count_preparation_time_allowed=False)
    profile['qualification'] = dict(status='PENDING',blocked_reason=None,all_three_local_passed=False,
        all_eight_ci_passed=False,independent_new_package_passed=False,actual_executed_tests_each=None,
        original_ci_runs=[44132222411,44132321549],ci_actual_attempt=1,ci_status_at_preregistration='IN_PROGRESS',
        qualification_inherited=False)
    profile['resource_review'].update(old_observer_floor_approved=False,old_observer_floor_conditional=True,
        operator_record=None,operator_record_sha256=None,current_free_bytes=None,current_combined_gap_bytes=None)
    path = ROOT/'benchmarks/plans'/f'{PREFIX}-pending.json'
    amend_path = ROOT/'benchmarks/plans'/f'{PREFIX}-observer-amendment.json'
    amendment.update(amends_plan_file=str(path.relative_to(ROOT)),original_plan_commit='NEW_909_V1_EXTERNAL_IMMUTABLE_PENDING_QUALIFICATION',
        original_plan_sha256=sha256(raw(plan)).hexdigest(),preregistered_at_utc=now)
    profile.update(source_root=str(FROZEN),source_commit=SOURCE,python=PYTHON,validation_report=REPORT,
        plan=str(path),amendment=str(amend_path),plan_sha256=sha256(raw(plan)).hexdigest(),
        amendment_sha256=sha256(raw(amendment)).hexdigest(),preregistered_at_utc=now,
        smoke_scratch='/workspace/uta-managed-observer-runs/909acec-smoke-20261117-01',
        long_scratch='/workspace/uta-managed-observer-runs/909acec-six-hours-20261117',
        execution_authorized=False,service_started=False)
    for key in ('financial_gates','reporting','cohost','known_failed_gate','previous_attempt','producer','observer','smoke'):
        assert plan[key] == json.loads(old_plan.read_bytes())[key]
    assert plan['resource_policy']['combined_conservative_required_bytes'] == 17_448_304_640
    assert profile['qualification']['actual_executed_tests_each'] is None
    for target,value in ((path,plan),(amend_path,amendment),
                         (ROOT/'benchmarks/profiles/managed-909acec-v1-pending.json',profile)):
        with target.open('xb') as stream:
            stream.write(raw(value))
    print(json.dumps(dict(preregistered_at_utc=now,source_commit=SOURCE,tests_each=None,execution_authorized=False,
        plan_sha256=sha256(raw(plan)).hexdigest(),amendment_sha256=sha256(raw(amendment)).hexdigest(),
        profile_sha256=sha256(raw(profile)).hexdigest())))


if __name__ == '__main__':
    main()
