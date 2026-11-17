"""Explicit-source, plan-only generation; exclusive writes, no operational calls."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = '91e4ae40b5e9b884c54026406299df5000c9c100'
FROZEN = '/workspace/uta-observer-freeze-91e4ae4'
REPORT = '/workspace/uta-observer-validation/final-91e4ae4/python312/summary.json'
PYTHON = '/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python'
GIB = 1024**3
PLAN_NAME = '20261117-managed-91e4ae4-six-hours-v1-pending.json'
AMEND_NAME = '20261117-managed-91e4ae4-six-hours-v1-observer-amendment.json'
PROFILE_NAME = 'managed-91e4ae4-v1-pending.json'


def raw(value):
    return (json.dumps(value, indent=2) + '\n').encode()


def write_new(path, value):
    with path.open('xb') as stream:
        stream.write(raw(value))


def main():
    old_plan = ROOT/'benchmarks/plans/20261117-managed-8b7f544-six-hours-v1-pending.json'
    old_amend = ROOT/'benchmarks/plans/20261117-managed-8b7f544-six-hours-v1-observer-amendment.json'
    old_profile = ROOT/'benchmarks/profiles/managed-8b7f544-v1-pending.json'
    plan = json.loads(old_plan.read_bytes())
    amendment = json.loads(old_amend.read_bytes())
    profile = json.loads(old_profile.read_bytes())
    now = datetime.now(timezone.utc).isoformat()
    for field in ('source_commit', 'observer_core_commit', 'reviewed_observer_and_wrapper_commit'):
        plan[field] = SOURCE
    plan.update(source_root=FROZEN, python=PYTHON, validation_report=REPORT, preregistered_at_utc=now)
    plan['qualification'].update(tests_each=None, ci_runs=None, package_tracked_files=None,
        runtime_files=52, source_tracked_files=3633,
        package_evidence='PENDING: fresh exact91e4 source/runtime artifacts, omission controls and independent package review')
    plan['producer']['source_budget_bytes'] = 6 * GIB
    plan['observer'].update(interval_seconds=61, output_budget_bytes=2 * GIB,
        cadence_reason='supported CLI interval61 is coprime with four-second rounds; every actual timestamp retained',
        output_budget_semantics='explicit fullcontrol+observer logical file bytes except validated private clones; periodic threshold, not physical quota; unknown/exceedance requests official owned-driver resource drain and technical NO_GO',
        output_budget_check_period_seconds=30, output_physical_hard_quota_enforced=False,
        output_budget_overshoot_guaranteed_bound_bytes=None)
    plan['copied_preregistration'] = dict(source_plan_sha256=sha256(old_plan.read_bytes()).hexdigest(),
        source_amendment_sha256=sha256(old_amend.read_bytes()).hexdigest(),
        source_commit='8b7f544fcbdfd540d43de1d6560022c6ebbd3799',
        changed_fields='new exactsource/time and PENDING qualification; explicit output2GiB resource policy; base and effective supported interval61')
    plan['previous_candidates'].append(dict(source_commit='8b7f544fcbdfd540d43de1d6560022c6ebbd3799',
        status='NO_GO_ACTUAL_HISTORICAL_REFERENCE_GENERATOR_SOURCE_FOOTER_MISMATCH',
        immutable_blocked_profile='benchmarks/profiles/managed-8b7f544-v2-blocked.json', never_reclassify=True))
    plan['resource_policy'] = dict(status='PENDING_OPERATOR_FLOOR_REVIEW_AND_POST_QUALIFICATION_PREFLIGHT',
        new_source_budget_bytes=6*GIB, source_declaration_bound_to_actual_original_configuration=True,
        new_observer_output_budget_bytes=2*GIB, new_private_clone_admission_estimate_bytes=GIB,
        minimum_free_headroom_bytes=GIB, new_total_bytes=10*GIB,
        old_full_future_reservation_bytes=6*GIB, old_observer_additional_floor_bytes=256*1024**2,
        old_observer_declared_byte_cap=None, floor_is_hard_cap=False, old_observer_floor_approved=False,
        combined_conservative_required_bytes=17_448_304_640, current_free_bytes=None, current_gap_bytes=None,
        space_reserved=False, recheck_after_qualification_and_package_required=True,
        clone_limit_is_input_estimate_not_peak_quota=True, observer_output_is_periodic_threshold_not_os_quota=True,
        output_overshoot_bound_bytes=None, separate_operator_record=None, separate_operator_record_sha256=None)
    plan.update(execution_authorized=False, service_started=False)
    plan_path = ROOT/'benchmarks/plans'/PLAN_NAME
    amendment.update(amends_plan_file='benchmarks/plans/'+PLAN_NAME,
        original_plan_commit='NEW_91E4_V1_EXTERNAL_IMMUTABLE_PENDING_COUNT',
        original_plan_sha256=sha256(raw(plan)).hexdigest(),
        reason='new base already selects supported CLI61; retain exact hashed amendment binding without bypassing CLI minimum',
        observer_interval_seconds_original=61, observer_interval_seconds_effective=61,
        preregistered_at_utc=now)
    amend_path = ROOT/'benchmarks/plans'/AMEND_NAME
    profile.update(source_root=FROZEN, source_commit=SOURCE, python=PYTHON, validation_report=REPORT,
        plan=str(plan_path), amendment=str(amend_path), plan_sha256=sha256(raw(plan)).hexdigest(),
        amendment_sha256=sha256(raw(amendment)).hexdigest(),
        smoke_scratch='/workspace/uta-managed-observer-runs/91e4ae4-smoke-20261117-01',
        long_scratch='/workspace/uta-managed-observer-runs/91e4ae4-six-hours-20261117',
        preregistered_at_utc=now, execution_authorized=False, service_started=False)
    # Copied flags are deliberately PENDING/false/null, never inferred from old QA.
    assert profile['qualification']['actual_executed_tests_each'] is None
    assert profile['resource_review']['old_observer_floor_approved'] is False
    for field in ('financial_gates', 'reporting', 'cohost', 'known_failed_gate', 'previous_attempt'):
        assert plan[field] == json.loads(old_plan.read_bytes())[field]
    for path, value in ((plan_path, plan), (amend_path, amendment),
                        (ROOT/'benchmarks/profiles'/PROFILE_NAME, profile)):
        write_new(path, value)
    print(json.dumps(dict(preregistered_at_utc=now, source_commit=SOURCE,
        plan_sha256=sha256(raw(plan)).hexdigest(), amendment_sha256=sha256(raw(amendment)).hexdigest(),
        profile_sha256=sha256(raw(profile)).hexdigest(), execution_authorized=False)))


if __name__ == '__main__':
    main()
