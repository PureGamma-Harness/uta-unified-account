"""Independent numerical/lifecycle differential check of one fixed pure kernel."""
import argparse
import builtins
from dataclasses import asdict, replace
from fractions import Fraction
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import random
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[2]
MODULE = Path('/workspace/uta-interest-accrual-kernel/uta/interest_accrual.py')
CODE_COMMIT = 'c507e0b458f24d2434ed2c24df597ba171113d3c'
CODE_SHA = '2d85c6112a9c908cae8d1609ffdb873f6a4d6ee9f373a414e637eea4f3a5843c'
REFERENCE = Path(__file__).with_name('reference.py')
CASES = ROOT / 'docs/reviews/interest-accrual-independent/manual-cases-v1.json'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('new unique result required')
    os.sched_setaffinity(0, {3})
    paths = (MODULE, REFERENCE, CASES, Path(__file__))
    before = {str(p): sha256(p.read_bytes()).hexdigest() for p in paths}
    assert before[str(MODULE)] == CODE_SHA
    original_import = builtins.__import__

    def pure_import(name, *arguments, **keywords):
        if name.split('.', 1)[0] in {'uta', 'sqlite3', '_sqlite3', 'subprocess', 'multiprocessing'}:
            raise AssertionError('prohibited import in pure kernel check')
        return original_import(name, *arguments, **keywords)

    builtins.__import__ = pure_import
    begin = time.monotonic_ns()
    checks, exception = [], None
    try:
        oracle = load('independent_exact_interest', REFERENCE)
        candidate = load('pinned_interest_candidate', MODULE)
        cases = json.loads(CASES.read_bytes())

        def book(principal=365, **kwargs):
            return candidate.AccrualBook(loan_id='synthetic-loan', account_id='synthetic-account',
                asset='BTC', scale=8, principal_units=principal, as_of_ns=0, **kwargs)

        def rate(ppb=10**9, *, version=1, start=0, end=oracle.MAX_TIMESTAMP, asset='BTC', scale=8):
            return candidate.RateVersion('synthetic-rate', version, asset, scale, ppb, start, end)

        def command(b, ref, duration, *, r=None, start=None, principal=None):
            s = b.state
            return candidate.AccrualCommand(ref, s.cursor_ns if start is None else start,
                (s.cursor_ns if start is None else start) + duration,
                s.principal_units if principal is None else principal, r or rate(),
                s.sequence, s.state_hash)

        def good(name, assertion):
            checks.append({'case': name, 'passed': bool(assertion)})

        def refused_unchanged(name, b, action, expected_code=None):
            initial = b.state
            try:
                action()
            except candidate.AccrualError as err:
                passed = b.state == initial and (expected_code is None or err.code == expected_code)
                checks.append({'case': name, 'passed': passed, 'observed_code': err.code})
            else:
                checks.append({'case': name, 'passed': False, 'observed_code': 'UNEXPECTED_ACCEPTANCE'})

        for case in cases['cases']:
            carry = oracle.carry_as_native_numerator(Fraction(case['initial_carry']))
            b = book(case['segments'][0][0], carry_numerator=carry)
            total_deltas = 0
            for index, (principal, ppb, duration) in enumerate(case['segments']):
                if b.state.principal_units != principal:
                    s = b.state
                    b.change_principal(candidate.PrincipalCommand('manual-principal:' + str(index),
                        s.cursor_ns, principal, s.sequence, s.state_hash))
                receipt = b.accrue(command(b, 'manual:' + str(index), duration,
                    r=rate(ppb, version=index + 1)))
                total_deltas += receipt.booked_delta_units
            expected = oracle.observe(case['segments'], prior_fraction=Fraction(case['initial_carry']))
            s = b.state
            good(case['id'], s.cumulative_booked_units == case['expected_booked'] == expected.booked_units
                 and total_deltas == expected.booked_units
                 and Fraction(s.carry_numerator, oracle.DENOMINATOR) == expected.remaining_fraction
                 and s.unbooked_risk_reserve_units == case['expected_risk_reserve'] == expected.extra_risk_reserve_units)

        # Deterministic random interval partitions: expected values use only
        # Fraction principal/rate/time multiplication in the independent oracle.
        rng = random.Random(20261117)
        for group in range(32):
            principal, ppb = rng.randrange(1, 10**15), rng.randrange(0, 10**9 + 1)
            elapsed = rng.randrange(32, oracle.YEAR_NS)
            cuts = sorted({0, elapsed, *(rng.randrange(1, elapsed) for _ in range(7))})
            durations = [right - left for left, right in zip(cuts, cuts[1:])]
            b = book(principal)
            r = rate(ppb)
            for index, duration in enumerate(durations):
                b.accrue(command(b, 'partition:%s:%s' % (group, index), duration, r=r))
            expected = oracle.observe([(principal, ppb, elapsed)])
            good('partition-exact-%02d' % group,
                 b.state.cumulative_booked_units == expected.booked_units
                 and Fraction(b.state.carry_numerator, oracle.DENOMINATOR) == expected.remaining_fraction)

        b = book()
        original = command(b, 'first', oracle.DAY_NS)
        first_receipt = b.accrue(original)
        b.accrue(command(b, 'second', oracle.DAY_NS))
        later = b.state
        replay = b.accrue(original)
        good('historical-replay-preserves-current-state', replay == first_receipt and b.state == later)
        refused_unchanged('same-reference-changed-payload', b,
            lambda: b.accrue(replace(original, end_ns=original.end_ns + 1)), 'reference_conflict')
        refused_unchanged('stale-checkpoint-new-reference', b,
            lambda: b.accrue(replace(original, reference='new-stale')), 'checkpoint_conflict')
        refused_unchanged('interval-gap', b,
            lambda: b.accrue(command(b, 'gap', 1, start=b.state.cursor_ns + 1)), 'interval_gap_or_overlap')
        refused_unchanged('interval-overlap', b,
            lambda: b.accrue(command(b, 'overlap', 1, start=b.state.cursor_ns - 1)), 'interval_gap_or_overlap')
        refused_unchanged('principal-mismatch', b,
            lambda: b.accrue(command(b, 'principal-bad', 1, principal=364)), 'principal_checkpoint_mismatch')
        refused_unchanged('zero-duration', b,
            lambda: b.accrue(command(b, 'zero-time', 0)), 'interval_invalid')
        refused_unchanged('excess-duration', b,
            lambda: b.accrue(command(b, 'long-time', 366 * oracle.DAY_NS + 1)), 'interval_invalid')
        refused_unchanged('rate-version-payload-change', b,
            lambda: b.accrue(command(b, 'rate-change-bad', 1, r=rate(5))), 'rate_version_conflict')
        refused_unchanged('rate-asset-mismatch', b,
            lambda: b.accrue(command(b, 'wrong-asset', 1, r=rate(asset='USD'))), 'rate_currency_mismatch')
        refused_unchanged('rate-scale-mismatch', b,
            lambda: b.accrue(command(b, 'wrong-scale', 1, r=rate(scale=7))), 'rate_currency_mismatch')
        refused_unchanged('rate-not-yet-effective', b,
            lambda: b.accrue(command(b, 'future-rate', 1, r=rate(version=2, start=b.state.cursor_ns + 1))),
            'rate_not_effective')
        refused_unchanged('rate-expired', b,
            lambda: b.accrue(command(b, 'old-rate', 1, r=rate(version=2, end=b.state.cursor_ns))),
            'rate_not_effective')
        b.accrue(command(b, 'after-refusals', 1))
        good('rejected-rate-does-not-poison-original-version', b.state.sequence == later.sequence + 1)

        b = book(1)
        b.accrue(command(b, 'fractional', oracle.DAY_NS))
        prior = b.state
        refused_unchanged('principal-change-must-be-at-cursor', b,
            lambda: b.change_principal(candidate.PrincipalCommand('bad-principal-time',
                prior.cursor_ns + 1, 0, prior.sequence, prior.state_hash)), 'principal_requires_accrued_boundary')
        principal_change = candidate.PrincipalCommand('principal-zero', prior.cursor_ns, 0,
            prior.sequence, prior.state_hash)
        b.change_principal(principal_change)
        zero_receipt = b.accrue(command(b, 'zero-principal-interval', oracle.DAY_NS))
        later = b.state
        b.change_principal(principal_change)
        good('zero-principal-retains-fraction-and-historical-replay',
             zero_receipt.booked_delta_units == 0 and b.state == later
             and later.carry_numerator == prior.carry_numerator and later.unbooked_risk_reserve_units == 1)

        near = book(cumulative_booked_units=10**38 - 2, carry_numerator=oracle.DENOMINATOR - 1)
        refused_unchanged('risk-bound-overflow-is-atomic', near,
            lambda: near.accrue(command(near, 'risk-overflow', oracle.DAY_NS)), 'risk_units_overflow')
        for label, bad in [('bool-principal', True), ('float-principal', 1.0),
                           ('string-principal', '1'), ('negative-principal', -1),
                           ('exclusive-principal-bound', 10**38)]:
            refused_unchanged(label, b, lambda bad=bad: b.accrue(command(b, label, 1, principal=bad)), 'principal_invalid')

        cap = book(0)
        original_cap = command(cap, 'capacity:0', 1, r=rate(0))
        cap_first = cap.accrue(original_cap)
        for index in range(1, 4096):
            cap.accrue(command(cap, 'capacity:' + str(index), 1, r=rate(0)))
        last = cap.state
        refused_unchanged('new-reference-at-capacity', cap,
            lambda: cap.accrue(command(cap, 'capacity:4096', 1, r=rate(0))), 'receipt_capacity')
        good('old-replay-allowed-at-capacity-without-rewind',
             cap.accrue(original_cap) == cap_first and cap.state == last and cap.state.sequence == 4096)
    except BaseException as err:
        exception = {'type': type(err).__name__, 'traceback': traceback.format_exc()}
    finally:
        builtins.__import__ = original_import
    elapsed = time.monotonic_ns() - begin
    after = {str(p): sha256(p.read_bytes()).hexdigest() for p in paths}
    result = {'status': 'PASS' if exception is None and checks and all(x['passed'] for x in checks)
              and elapsed <= 10**10 and before == after else 'FAIL',
              'candidate_commit': CODE_COMMIT, 'candidate_module_sha256': CODE_SHA,
              'candidate_import_path': str(MODULE), 'reference_import_path': str(REFERENCE),
              'pid': os.getpid(), 'cpu_ids': sorted(os.sched_getaffinity(0)), 'python': sys.version,
              'elapsed_ns_before_result_write': elapsed, 'budget_ns': 10**10,
              'source_sha256': before, 'source_sha256_after': after, 'checks': checks,
              'exception': exception, 'candidate_core_used_for_expected_values': False,
              'database_or_worker_or_financial_source_created': False,
              'scheduler_or_current_V2_policy_modified': False, 'production_approved': False}
    with args.output.open('x') as output:
        json.dump(result, output, indent=2)
        output.write('\n')
    print(json.dumps({'status': result['status'], 'checks': len(checks),
                      'failed_checks': [x['case'] for x in checks if not x['passed']],
                      'exception_type': exception['type'] if exception else None,
                      'elapsed_ns': elapsed, 'production_approved': False}))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
