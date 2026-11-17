"""Create new explicit-source preregistration with exclusive writes; no jobs."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = 'dbc93e5d50125e6ab8f1154511a537f8b1a8fa1b'
FROZEN = '/workspace/uta-combined-freeze-dbc93e5'
REPORT = '/workspace/uta-combined-validation/final-dbc93e5/python312/summary.json'
PYTHON = '/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python'
GIB = 1024**3
PREFIX = '20261117-managed-dbc93e5-six-hours-v1'


def raw(value):
    return (json.dumps(value, indent=2)+'\n').encode()


def main():
    old_plan = ROOT/'benchmarks/plans/20261117-managed-91e4ae4-six-hours-v1-pending.json'
    old_amend = ROOT/'benchmarks/plans/20261117-managed-91e4ae4-six-hours-v1-observer-amendment.json'
    old_profile = ROOT/'benchmarks/profiles/managed-91e4ae4-v1-pending.json'
    plan, amendment, profile = (json.loads(path.read_bytes()) for path in (old_plan, old_amend, old_profile))
    now = datetime.now(timezone.utc).isoformat()
    blocked = 'ACTUAL_DBC_CI_NO_GO: push and PR Python3.10 unit steps failed; other six succeeded; cause awaiting raw; source cannot execute'
    for key in ('source_commit','observer_core_commit','reviewed_observer_and_wrapper_commit'):
        plan[key] = SOURCE
    plan.update(status='PREREGISTERED_V1_PENDING_ACTUAL_TEST_COUNT_CI_NO_GO_NO_EXECUTION',
        source_root=FROZEN, python=PYTHON, validation_report=REPORT, preregistered_at_utc=now,
        source_git_tree_oid='9b30f41b9df52efbe8eb56d0c7af958594bcf1f9',
        root_reported_source_tree_sha256='ec0fa09e2e2e50557300423ddf6983969c9727816288ed79e9de7a17438c5b2b',
        root_reported_tree_sha256_independently_verified=False, execution_authorized=False, service_started=False)
    plan['qualification'].update(status='BLOCKED_ACTUAL_CI_NO_GO_OTHER_GATES_PENDING',
        tests_each=None, tests_each_status='PENDING_ALL_THREE_EXACT_REPORTS; never infer from previous source',
        ci_runs=[44125869999,44125881372], ci_runs_status='ACTUAL_NO_GO_TWO_PYTHON310_UNIT_FAILURES',
        ci_successful_python_jobs=6, ci_failed_python_jobs=2, observed_ci_artifact_count=20,
        ci_failure_cause=None, ci_original_raw_archive_pending=True,
        package_tracked_files=None, source_tracked_files=5159, runtime_files=62,
        package_evidence='PENDING: actual fresh dbc93e5 source/runtime artifacts and independent package review',
        no_qualification_inherited_from_any_prior_source=True)
    assert plan['producer']['source_budget_bytes'] == 6*GIB
    assert plan['observer']['output_budget_bytes'] == 2*GIB
    assert plan['observer']['max_private_clone_bytes'] == plan['observer']['clone_headroom_bytes'] == GIB
    plan['resource_policy'].update(current_free_bytes=None, current_gap_bytes=None,
        old_observer_floor_approved=False, separate_operator_record=None, separate_operator_record_sha256=None,
        recheck_after_qualification_and_package_required=True, space_reserved=False)
    plan['previous_candidates'].append(dict(source_commit='91e4ae40b5e9b884c54026406299df5000c9c100',
        status='NO_GO_ACTUAL_PYTHON313_RECOVERY_CI_FAILURE',
        immutable_blocked_profile='benchmarks/profiles/managed-91e4ae4-v2-blocked.json',never_reclassify=True))
    plan['copied_preregistration'] = dict(source_plan_sha256=sha256(old_plan.read_bytes()).hexdigest(),
        source_amendment_sha256=sha256(old_amend.read_bytes()).hexdigest(),
        source_commit='91e4ae40b5e9b884c54026406299df5000c9c100',
        qualification_inherited=False, changed_fields='new exactsource/time/count metadata and known CI NO_GO; workload/finance/resource budgets unchanged')
    plan['execution_gate'] = 'No execution: actual dbc CI NO_GO. Each phase requires separate root GO only after all exact-source QA, independent package/floor review and fresh metadata/free gate; real60s smoke must precede any new long attempt.'
    plan['smoke'] = dict(duration_seconds=60, planned_rounds=15, worker_fault_every_rounds=5,
        parent_fault_every_rounds=10, outer_deadline_seconds=150, real_tls_matching_settlement_restarts=True,
        startup_normal_active_and_fault_unknown_coverage_required=True, same_watermark_final_and_private_cold_required=True,
        strict_long_receipt_must_be_refused=True, missing_phase_is_incomplete=True, automatic_next_phase_allowed=False)
    for name in ('production_approved','capacity_10000_approved','continuous_6h_stability_passed',
                 'continuous_24h_stability_passed','financial_6h_passed','live_coverage_passed'):
        plan[name] = profile[name] = False
    path = ROOT/'benchmarks/plans'/f'{PREFIX}-pending.json'
    amend_path = ROOT/'benchmarks/plans'/f'{PREFIX}-observer-amendment.json'
    amendment.update(amends_plan_file=str(path.relative_to(ROOT)), original_plan_commit='NEW_DBC_V1_EXTERNAL_IMMUTABLE_PENDING_COUNT_CI_NO_GO',
        original_plan_sha256=sha256(raw(plan)).hexdigest(), preregistered_at_utc=now)
    profile.update(source_root=FROZEN, source_commit=SOURCE, python=PYTHON, validation_report=REPORT,
        plan=str(path), amendment=str(amend_path), plan_sha256=sha256(raw(plan)).hexdigest(),
        amendment_sha256=sha256(raw(amendment)).hexdigest(),
        smoke_scratch='/workspace/uta-managed-observer-runs/dbc93e5-smoke-20261117-01',
        long_scratch='/workspace/uta-managed-observer-runs/dbc93e5-six-hours-20261117',
        preregistered_at_utc=now, service_started=False, execution_authorized=False)
    profile['qualification'].update(status='BLOCKED_ACTUAL_CI_OTHER_GATES_PENDING', blocked_reason=blocked,
        actual_executed_tests_each=None, all_three_local_passed=False, all_eight_ci_passed=False,
        independent_new_package_passed=False, original_ci_runs=[44125869999,44125881372],
        ci_failure_cause=None, actual_whole_ci_jobs_successful=6, actual_whole_ci_jobs_failed=2)
    profile['resource_review'].update(old_observer_floor_approved=False, operator_record=None,
        operator_record_sha256=None, current_free_bytes=None,current_combined_gap_bytes=None)
    for key in ('financial_gates','reporting','cohost','known_failed_gate','previous_attempt','producer','observer'):
        assert plan[key] == json.loads(old_plan.read_bytes())[key]
    for target, value in ((path,plan),(amend_path,amendment),
                          (ROOT/'benchmarks/profiles/managed-dbc93e5-v1-pending.json',profile)):
        with target.open('xb') as stream:
            stream.write(raw(value))
    print(json.dumps(dict(preregistered_at_utc=now,source_commit=SOURCE,ci_status='NO_GO',tests_each=None,
        plan_sha256=sha256(raw(plan)).hexdigest(),amendment_sha256=sha256(raw(amendment)).hexdigest(),
        profile_sha256=sha256(raw(profile)).hexdigest(),execution_authorized=False)))


if __name__ == '__main__':
    main()
