"""Reproducible bounded synthetic oracle matrix; not a capacity benchmark.

Run from a source checkout: python tools/check_admission_oracle.py
Uses existing rational cash/reserve oracle; no network or real accounts.
"""
from decimal import Decimal
from pathlib import Path
import json
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
import test_admission_invariants as fixture  # noqa: E402

SEEDS = (0, 1, 2, 42, 20261115, 872511)
BATCH_SIZES = (1, 2, 8, 32)
TEST = "test_seeded_fifo_trace_matches_independent_cash_and_reserve_book"


def run_case(seed, batch_size):
    case = fixture.AdmissionInvariants(TEST)
    original_batcher = case.batcher

    def batcher(*args, **kwargs):
        kwargs["max_batch_size"] = batch_size
        return original_batcher(*args, **kwargs)

    case.batcher = batcher
    rng = fixture.random.Random(seed)
    result = unittest.TestResult()
    with patch.object(fixture.random, "Random", return_value=rng):
        case.run(result)
    return result


def details(result):
    return {"passed": (result.testsRun == 1 and not result.skipped
                       and not result.expectedFailures and result.wasSuccessful()),
            "tests_run": result.testsRun, "skipped": len(result.skipped),
            "expected_failures": len(result.expectedFailures),
            "failures": [trace for _, trace in result.failures],
            "errors": [trace for _, trace in result.errors]}


def main():
    cases = []
    for seed in SEEDS:
        for batch_size in BATCH_SIZES:
            result = run_case(seed, batch_size)
            cases.append({"seed": seed, "batch_size": batch_size, **details(result)})
    # Alter only a temporary in-process mock, not source or production state.
    original = fixture.ExchangeService._reserve
    with patch.object(fixture.ExchangeService, "_reserve",
                      lambda self, *a, **kw: original(self, *a, **kw) * Decimal("1.1")):
        negative = run_case(872511, 16)
    # Reject false positives from unrelated harness errors: this mutant must
    # fail at an order expected to succeed because it now rejects margin.
    negative_detected = (negative.testsRun == 1 and not negative.skipped
                         and len(negative.errors) == 1 and not negative.failures
                         and "insufficient available margin for order and fee reserve"
                         in negative.errors[0][1]
                         and 'future.result(timeout=10)["status"]' in negative.errors[0][1])
    ok = all(case["passed"] for case in cases) and negative_detected
    print(json.dumps({"synthetic_only": True, "capacity_acceptance": False,
                      "all_passed": ok, "cases": len(cases),
                      "positive_commands": 160 * len(cases), "results": cases,
                      "negative_control": {"mutation": "reservation increased 10 percent",
                                           "expected_failure_detected": negative_detected,
                                           **details(negative)}}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
