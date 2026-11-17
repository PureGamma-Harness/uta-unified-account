"""P2: prepared default total-handle boundary characterization, NOT YET RUN.

The actual first32 admissions are retained prefix evidence, never warmup.
No query availability is promised through exhausted global intake or DB failure.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import time

spec = importlib.util.spec_from_file_location('independent_p2p3_support', Path(__file__).with_name('support.py'))
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)

PLANNED_INVOCATIONS = 262


def run(args, api):
    start, begin = s.utc(), time.monotonic_ns()
    status, completed, ordinary, queries = 'PASS', [], [], []
    progress = {'ordinary_accepted': 0, 'query_accepted': 0, 'expected_refusals': 0,
                'planned_invocations': PLANNED_INVOCATIONS, 'actual_invocations': 0}
    fixture = None
    cleanup = []

    def budget():
        if time.monotonic_ns() - begin >= 25 * 10**9:
            raise s.NotCompleted('25s work budget exhausted; target remains262')

    def invoke(cid, *, lookup=False, key='funding'):
        budget()
        progress['actual_invocations'] += 1
        try:
            return fixture.call(cid, lookup=lookup, key=key)
        except api.SigningError as error:
            if error.status == 503:
                raise s.TechnicalUnknown('unplanned technical503') from error
            raise

    def refusal(cid, *, lookup, key, status_code, code, outcome):
        budget()
        before = s.snapshot(fixture.path)
        progress['actual_invocations'] += 1
        try:
            handle = fixture.call(cid, lookup=lookup, key=key)
        except api.SigningError as error:
            if (error.status, error.code) != (status_code, code):
                if error.status == 503:
                    raise s.TechnicalUnknown('unexpected technical503') from error
                raise AssertionError('typed refusal differs from planned boundary') from error
        else:
            s.observe(fixture.issuer, handle, release=True)
            raise AssertionError('request crossed a required handle/permission boundary')
        after = s.snapshot(fixture.path)
        assert after['auth_credit_acceptances'] == before['auth_credit_acceptances']
        assert len(after['auth_nonces']) == len(before['auth_nonces']) + 1
        extra = [row for row in after['auth_audit'] if row not in before['auth_audit']]
        assert len(extra) == 1 and extra[0]['outcome'] == outcome
        progress['expected_refusals'] += 1

    try:
        fixture = s.Fixture(api, args.private / 'default-limits')
        initial = None
        samples = []
        for index in range(224):
            call_begin = time.monotonic_ns()
            handle = invoke('normal-' + str(index))
            ordinary.append(handle)
            observed = s.observe(fixture.issuer, handle)
            assert observed['receipt_kind'] == 'auth_first_observation' and observed['found'] is True
            if index == 0:
                initial = observed['first_acceptance_payload_or_null']
            samples.append(time.monotonic_ns() - call_begin)
            progress['ordinary_accepted'] += 1
            if index == 31:
                elapsed = (time.monotonic_ns() - begin) / 1e9
                # _config scans growing history: conservatively extrapolate with
                # both setup-inclusive quadratic total and final8 marginal cost.
                projected = max(elapsed * (PLANNED_INVOCATIONS / 32) ** 2,
                    elapsed + 2 * sum(samples[-8:]) / 8 / 1e9 * (PLANNED_INVOCATIONS - 32)) + 1
                s.save(args.private / 'actual-prefix32.json', {
                    'prefix_is_part_of_fixed224_target': True, 'discarded_warmup': False,
                    'actual_accepted_and_retained': 32, 'actual_elapsed_seconds': elapsed,
                    'conservative_projected_seconds': projected, 'projection_is_not_measured_final_duration': True,
                    'budget_seconds': 25, 'planned_invocations': PLANNED_INVOCATIONS})
                if projected > 25:
                    raise s.NotCompleted('prefix projection exceeds25s; no target reduction')
        assert len(s.snapshot(fixture.path)['auth_credit_acceptances']) == 224
        completed.append('retain224_ordinary_actual_default_handles')
        refusal('normal-225th', lookup=False, key='funding', status_code=503,
                code='credit_auth_handle_capacity', outcome='HANDLE_CAPACITY')
        completed.append('ordinary225th_refused_without_acceptance')
        refusal('normal-0', lookup=True, key='ungranted', status_code=403,
                code='credit_auth_forbidden', outcome='PERMISSION_REJECTED')
        completed.append('valid_mac_without_read_grant_cannot_use_query_reserve')
        for _ in range(32):
            handle = invoke('normal-0', lookup=True, key='reader')
            queries.append(handle)
            observed = s.observe(fixture.issuer, handle)
            assert observed['receipt_kind'] == 'auth_query_only'
            assert observed['first_acceptance_payload_or_null'] == initial
            progress['query_accepted'] += 1
        completed.append('32_current_read_queries_reach_total256_preserving_first_identity')
        refusal('normal-0', lookup=True, key='reader', status_code=503,
                code='credit_auth_handle_capacity', outcome='HANDLE_CAPACITY')
        completed.append('query33rd_refused_at_total256')
        fixture.issuer.release(ordinary.pop())
        refusal('normal-after-release-at255', lookup=False, key='funding', status_code=503,
                code='credit_auth_handle_capacity', outcome='HANDLE_CAPACITY')
        for _ in range(31):
            fixture.issuer.release(queries.pop())
        refusal('normal-after-release-at224', lookup=False, key='funding', status_code=503,
                code='credit_auth_handle_capacity', outcome='HANDLE_CAPACITY')
        completed.append('ordinary_still_refused_at_total255_and224')
        fixture.issuer.release(queries.pop())
        assert len(ordinary) == 223 and len(queries) == 0
        handle = invoke('normal-after-release-at223')
        ordinary.append(handle)
        observed = s.observe(fixture.issuer, handle)
        assert observed['receipt_kind'] == 'auth_first_observation'
        final = s.snapshot(fixture.path)
        assert len(final['auth_credit_acceptances']) == 225
        assert len(final['auth_nonces']) == PLANNED_INVOCATIONS
        assert sum(row['outcome'] == 'HANDLE_CAPACITY' for row in final['auth_audit']) == 4
        assert sum(row['outcome'] == 'QUERY_ORIGINAL' for row in final['auth_audit']) == 32
        assert progress['actual_invocations'] == PLANNED_INVOCATIONS
        completed.append('normal_readmitted_only_below_total224_not_independent_class_counters')
    except s.NotCompleted:
        status = 'NOT_COMPLETED'
    except s.TechnicalUnknown:
        status = 'UNKNOWN'
    except BaseException as error:
        known_failure = isinstance(error, AssertionError) or (
            isinstance(error, api.SigningError) and error.status != 503)
        status = 'FAIL' if known_failure else 'UNKNOWN'
        progress['first_exception_type'] = type(error).__name__
    finally:
        if fixture is not None:
            for handle in ordinary + queries:
                try:
                    fixture.issuer.release(handle)
                    cleanup.append(True)
                except BaseException:
                    cleanup.append(False)
            if not all(cleanup) and status == 'PASS':
                status = 'UNKNOWN'
    report = s.report_base(args.source, api, start, begin)
    report.update({'probe': 'P2', 'status': status, 'completed_steps': completed,
        'completed_step_count': len(completed), 'planned_step_count': 7, 'progress': progress,
        'all_retained_own_thread_handles_released': all(cleanup),
        'scope': 'default retained registry thresholds with intake and DB available; not DoS availability',
        'all_observed_authorization_flags_false': True if status == 'PASS' else None})
    s.save(args.result, report)
    print(json.dumps({key: value for key, value in report.items() if key != 'runtime_hashes_before'}), flush=True)
    return 0 if status == 'PASS' and len(completed) == 7 and report['source_unchanged'] else 2


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    for name in ('source', 'private', 'result'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    assert all(path.is_absolute() for path in (args.source, args.private, args.result))
    assert not args.private.exists() and not args.result.exists()
    args.private.mkdir(mode=0o700)
    api = s.bind_source(args.source)
    return run(args, api)


if __name__ == '__main__':
    raise SystemExit(main())
