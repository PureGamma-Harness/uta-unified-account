"""Run only the independent manual standards; never import a candidate."""
import argparse
import builtins
from fractions import Fraction
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import platform
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
REFERENCE = Path(__file__).with_name("reference.py")
CASES = ROOT / "docs/reviews/interest-accrual-independent/manual-cases-v1.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("new unique result required")
    os.sched_setaffinity(0, {3})
    inputs = {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest()
              for p in (REFERENCE, CASES, Path(__file__))}
    original_import = builtins.__import__

    def pure_import(name, *arguments, **keywords):
        if name.split(".", 1)[0] in {"uta", "sqlite3", "_sqlite3", "subprocess", "multiprocessing"}:
            raise AssertionError("prohibited import in independent standard selfcheck")
        return original_import(name, *arguments, **keywords)

    builtins.__import__ = pure_import
    begin = time.monotonic_ns()
    records = []
    try:
        spec = importlib.util.spec_from_file_location("independent_interest_reference", REFERENCE)
        reference = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = reference
        spec.loader.exec_module(reference)
        cases = json.loads(CASES.read_bytes())
        for case in cases["cases"]:
            actual = reference.observe(case["segments"], prior_fraction=Fraction(case["initial_carry"]))
            passed = (actual.exact_total_units == Fraction(case["expected_total"])
                      and actual.booked_units == case["expected_booked"]
                      and actual.remaining_fraction == Fraction(case["expected_remaining"])
                      and actual.extra_risk_reserve_units == case["expected_risk_reserve"])
            records.append({"case": case["id"], "passed": passed,
                            "observed_exact_total": str(actual.exact_total_units)})
        for label, bad in (("bool_principal", [(True, 1, 1)]),
                           ("string_principal", [("1", 1, 1)]),
                           ("negative_rate", [(1, -1, 1)]),
                           ("excessive_rate", [(1, 10**9 + 1, 1)]),
                           ("zero_duration", [(1, 1, 0)]),
                           ("excessive_duration", [(1, 1, 366 * reference.DAY_NS + 1)])):
            try:
                reference.observe(bad)
            except reference.ReferenceRefusal:
                accepted = False
            else:
                accepted = True
            records.append({"case": label, "passed": not accepted})
        unsplit = reference.observe([(1, 10**9, reference.YEAR_NS)])
        split = reference.observe([(1, 10**9, reference.DAY_NS)] * 365)
        records.append({"case": "365_day_split_equals_year", "passed": unsplit == split})
        try:
            reference.observe([], prior_booked=10**38 - 1, prior_fraction=Fraction(1, 2))
        except reference.ReferenceRefusal:
            accepted = False
        else:
            accepted = True
        records.append({"case": "initial_risk_bound_even_without_new_segment", "passed": not accepted})
    finally:
        builtins.__import__ = original_import
    elapsed = time.monotonic_ns() - begin
    after = {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest()
             for p in (REFERENCE, CASES, Path(__file__))}
    result = {"status": "PASS" if all(x["passed"] for x in records) and elapsed <= 10**10 and inputs == after else "FAIL",
              "scope": "independent manual standard selfcheck only; no candidate imported",
              "pid": os.getpid(), "cpu_ids": sorted(os.sched_getaffinity(0)),
              "python": sys.version, "platform": platform.platform(),
              "elapsed_ns_before_result_write": elapsed, "budget_ns": 10**10,
              "reference_import_path": str(REFERENCE), "source_sha256": inputs,
              "source_sha256_after": after, "checks": records,
              "production_SQL_process_or_financial_import_permitted": False,
              "production_approved": False}
    with args.output.open("x") as output:
        json.dump(result, output, indent=2)
        output.write("\n")
    print(json.dumps({"status": result["status"], "checks": len(records), "elapsed_ns": elapsed,
                      "candidate_imported": False, "production_approved": False}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
