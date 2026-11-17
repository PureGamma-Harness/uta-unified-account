#!/usr/bin/env python3
"""Independent pure semantic differential, retaining actual safety REDs."""

from copy import deepcopy
from dataclasses import replace
import argparse
from decimal import Inexact, Rounded, localcontext
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT))
import reference_credit_transition_math as ref
from uta.credit_policy import validate_native_descriptor
from uta.credit_transition import calculate_borrow_transition, compare_borrow_transition


FROZEN = "23efd5f4121ea7509a544741d3e0a2fe98be50ea"
SOURCE_SHA = "8423116055adc885077ac920d0ca135dffeb8738197a059d61fe53c2ef1728e0"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def descriptor_wire(local_limit=50000000, other_limit=50000000):
    ids = ("independent:transition:0", "independent:transition:1")
    layout = hashlib.sha256(b"independent-integer-transition-layout").hexdigest()
    policy = {"format": 1, "name": "SYNTHETIC-CREDIT-ZERO-v1", "version": 1,
              "new_interest_rate": "0", "new_borrow_fee_rate": "0", "require_managed_inbox": True,
              "borrow_batch_size": 0, "production_approved": False, "credit_assets": ["BTC"]}
    policy_id = "credit-policy:" + hashlib.sha256(canonical(policy).encode()).hexdigest()
    cert = {"format": 1, "budget_id": "independent:transition:budget", "version": 1,
            "layout_hash": layout, "credit_policy_id": policy_id,
            "authorities": [{"shard": s, "authority_id": value} for s, value in enumerate(ids)],
            "assets": {"BTC": {"scale": 8, "global_limit_units": str(local_limit + other_limit), "allocations": [
                {"shard": s, "authority_id": value, "limit_units": str((local_limit, other_limit)[s]),
                 "opening_principal_units": "0", "opening_interest_units": "0", "opening_pool_units": "100000000",
                 "funding_claims": [{"source_reference": f"independent:transition:fund:{s}",
                                     "command_id": f"independent-pool-{s}", "funded_units": "100000000"}]}
                for s, value in enumerate(ids)]}}}
    return {"format": 1, "stage": "NATIVE_PREPARED", "synthetic": True, "authority_id": ids[0],
            "shard": 0, "layout_hash": layout, "credit_policy": policy, "credit_policy_id": policy_id,
            "certificate": cert, "certificate_id": "credit-budget:" + hashlib.sha256(canonical(cert).encode()).hexdigest()}


def observe(function, **kwargs):
    try:
        value = function(**kwargs)
        return {"accepted": True, "value": value.wire() if hasattr(value, "wire") else value}, value
    except Exception as error:
        return {"accepted": False, "exception_type": type(error).__module__ + "." + type(error).__name__,
                "code": getattr(error, "code", None), "status": getattr(error, "status", None), "message": str(error)}, None


def default_inputs():
    return {"account_id": "alice", "asset": "BTC", "amount_units": "40000000", "before": ref.base_state(),
            "limits": {"account_limit_units": "50000000", "local_asset_limit_units": "50000000"},
            "quote_units": "50000000", "quantity_step_units": "1000000"}


def cases():
    answer = []
    def add(name, changes=None, local_limit=50000000, other_limit=50000000):
        value = default_inputs()
        value.update(changes or {})
        answer.append({"id": name, "inputs": value, "local_limit": local_limit, "other_limit": other_limit})
    add("golden001_borrow_0_4")
    after001 = ref.base_state(version=2, cash_units="40000000", principal_units="40000000",
        principal_ledger_units="-40000000", shard_principal_units="40000000", principal_receivable_units="40000000", pool_units="60000000")
    add("golden002_then_0_11_refused", {"before": after001, "amount_units": "11000000", "quote_units": "26000000"})
    add("golden003_then_0_1_exact_0_5_boundary", {"before": after001, "amount_units": "10000000", "quote_units": "26000000"})
    add("negative_cash_is_distinct", {"before": ref.base_state(cash_units="-50000000")})
    opening_interest = ref.base_state(cash_units="30000000", principal_units="20000000", interest_units="1000000",
        principal_ledger_units="-20000000", interest_ledger_units="-1000000", shard_principal_units="20000000",
        shard_interest_units="1000000", principal_receivable_units="20000000", interest_receivable_units="1000000")
    add("interest_makes_0_3_exceed_account_gross", {"before": opening_interest, "amount_units": "30000000"})
    add("interest_gross_exact_equality", {"before": opening_interest, "amount_units": "29000000"})
    add("other_account_consumes_shard", {"before": ref.base_state(shard_principal_units="30000000", principal_receivable_units="30000000"), "amount_units": "20000000"})
    add("other_account_one_step_over", {"before": ref.base_state(shard_principal_units="30000000", principal_receivable_units="30000000"), "amount_units": "21000000"})
    add("other_shard_budget_not_transferable", {"amount_units": "1000000"}, local_limit=0, other_limit=100000000)
    add("pool_short_by_one_minor_unit", {"before": ref.base_state(pool_units="39999999")})
    add("quote_input_short_by_one_minor_unit", {"quote_units": "39999999"})
    add("one_minor_unit_is_not_one_quantity_step", {"amount_units": "1"})
    add("cash_positive_overflow", {"before": ref.base_state(cash_units=str(10 ** 38 - 1)), "amount_units": "1", "quantity_step_units": "1"})
    add("cash_negative_magnitude_boundary", {"before": ref.base_state(cash_units=str(-10 ** 38 + 1)), "amount_units": "1", "quantity_step_units": "1"})
    add("version_last_advancable_roundtrip", {"before": ref.base_state(version=2 ** 63 - 2)})
    add("version_cannot_advance_past_i64", {"before": ref.base_state(version=2 ** 63 - 1)})
    for label, amount in (("bool", True), ("float", 1.0), ("integer", 40000000), ("negative_zero", "-0"), ("plus", "+1"), ("leading_zero", "01"), ("exponent", "4e7"), ("unicode", "４０００００００"), ("magnitude", str(10 ** 38))):
        add("amount_bad_" + label, {"amount_units": amount})
    for field in ("cash_units", "principal_units", "interest_units", "principal_ledger_units", "interest_ledger_units",
                  "shard_principal_units", "shard_interest_units", "pool_units", "principal_receivable_units", "interest_receivable_units"):
        add("snapshot_bad_type_" + field, {"before": ref.base_state(**{field: True})})
    for field in ("principal_units", "interest_units", "pool_units", "principal_receivable_units", "shard_interest_units"):
        add("snapshot_negative_" + field, {"before": ref.base_state(**{field: "-1"})})
    for field in ("principal_units", "interest_units", "shard_principal_units", "principal_receivable_units"):
        add("unreconciled_" + field, {"before": ref.base_state(**{field: "1"})})
    add("version_bool", {"before": ref.base_state(version=True)})
    add("zero_step", {"quantity_step_units": "0"})
    add("missing_limits", {"limits": {}})
    add("account_limit_short", {"limits": {"account_limit_units": "39999999", "local_asset_limit_units": "50000000"}})
    add("asset_limit_short", {"limits": {"account_limit_units": "50000000", "local_asset_limit_units": "39999999"}})
    tiered = ref.supplied_tiered_quote()
    tier_state = ref.base_state(cash_units="65000000", principal_units="40000000", principal_ledger_units="-40000000",
        shard_principal_units="40000000", principal_receivable_units="40000000", pool_units="60000000")
    for quantity in ("33000000", "34000000"):
        add("tiered_supplied_quote_request_" + quantity, {"before": tier_state, "amount_units": quantity,
            "quote_units": tiered["supplied_quote_units"], "limits": {"account_limit_units": "100000000", "local_asset_limit_units": "100000000"}}, 100000000, 100000000)
    return answer


def main(output, expected_source_sha=SOURCE_SHA, reviewed_commit=FROZEN):
    if hashlib.sha256((ROOT / "uta/credit_transition.py").read_bytes()).hexdigest() != expected_source_sha:
        raise SystemExit("frozen transition source changed; stop")
    started = time.perf_counter()
    ordinary, failures = [], []
    for case in cases():
        source = case["inputs"]
        try:
            expected = ref.calculate(**source, declared_allocation_units=str(case["local_limit"]))
            reference_error = None
        except ref.Refusal as error:
            expected, reference_error = None, {"code": error.code, "status": error.status}
        raw = descriptor_wire(case["local_limit"], case["other_limit"])
        parsed = validate_native_descriptor(raw, expected_authority_id=raw["authority_id"])
        actual, value = observe(calculate_borrow_transition, descriptor=parsed, **source)
        calculation_matches = (actual["accepted"] == (expected is not None)
            and (all(actual["value"][key] == expected[key] for key in expected) if expected is not None
                 else {"code": actual.get("code"), "status": actual.get("status")} == reference_error))
        comparison = None
        if actual["accepted"]:
            comparison, _ = observe(compare_borrow_transition, expected=value, after=expected["after"], postings=expected["postings"])
        roundtrip_matches = comparison is None or (comparison["accepted"] and comparison["value"]["accounting_matches"] is True
                                                     and comparison["value"]["operation_authorized"] is False)
        if not calculation_matches or not roundtrip_matches:
            failures.append(case["id"])
        ordinary.append({**case, "reference": expected, "reference_error": reference_error, "actual": actual,
                         "calculation_matches": calculation_matches, "actual_compare_to_independent_wire": comparison,
                         "roundtrip_matches": roundtrip_matches})

    raw = descriptor_wire()
    parsed = validate_native_descriptor(raw, expected_authority_id=raw["authority_id"])
    baseline, baseline_value = observe(calculate_borrow_transition, descriptor=parsed, **default_inputs())
    allocation = parsed.assets[0].allocations
    forged_budget = replace(parsed.assets[0], allocations=(replace(allocation[0], limit_units=100000000), replace(allocation[1], limit_units=0)))
    forged_descriptor = replace(parsed, assets=(forged_budget,))
    attack = default_inputs()
    attack.update(amount_units="60000000", quote_units="100000000",
                  limits={"account_limit_units": "100000000", "local_asset_limit_units": "100000000"})
    forged_observed, _ = observe(calculate_borrow_transition, descriptor=forged_descriptor, **attack)
    canonical_control, _ = observe(calculate_borrow_transition, descriptor=parsed, **attack)
    forged_descriptor_record = {"id": "forged_exact_descriptor_immutable_budget_changed", "input": attack,
        "original_descriptor_canonical_payload": parsed.canonical_payload, "descriptor_id_unchanged": forged_descriptor.descriptor_id == parsed.descriptor_id,
        "certificate_id_unchanged": forged_descriptor.certificate_id == parsed.certificate_id,
        "exact_type_unchanged": type(forged_descriptor) is type(parsed),
        "original_local_allocation_units": allocation[0].limit_units,
        "forged_local_allocation_units": forged_descriptor.allocation_for("BTC", 0).limit_units,
        "forged_allocation_sum_still_equals_original_global": sum(a.limit_units for a in forged_budget.allocations) == parsed.assets[0].global_limit_units,
        "reference_expected": {"accepted": False, "code": "credit_limit", "status": 409},
        "actual_forged": forged_observed, "actual_unchanged_canonical_control": canonical_control,
        "safety_assertion_passed": not forged_observed["accepted"]}
    if not forged_descriptor_record["safety_assertion_passed"]:
        failures.append(forged_descriptor_record["id"])

    recorded_postings = [(account, quantity * 2) for account, quantity in baseline_value.postings]
    forged_expected = replace(baseline_value, postings=tuple(recorded_postings))
    forged_wire = forged_expected.wire()
    forged_comparison, _ = observe(compare_borrow_transition, expected=forged_expected,
                                    after=forged_wire["after"], postings=forged_wire["postings"])
    forged_expected_record = {"id": "forged_exact_expected_double_postings_unchanged_delta", "original_expected": baseline["value"],
        "forged_expected": forged_wire, "exact_type_unchanged": type(forged_expected) is type(baseline_value),
        "reference_expected_acceptance": False, "actual": forged_comparison,
        "safety_assertion_passed": not forged_comparison["accepted"]}
    if not forged_expected_record["safety_assertion_passed"]:
        failures.append(forged_expected_record["id"])

    mismatches = []
    for label in ("reordered", "bool_ordinal", "integer_units", "noncanonical_plus", "wrong_customer_balanced", "extra_balanced_pair"):
        postings = deepcopy(baseline["value"]["postings"])
        if label == "reordered":
            postings[0], postings[1] = postings[1], postings[0]
        elif label == "bool_ordinal": postings[0]["ordinal"] = False
        elif label == "integer_units": postings[0]["units"] = 40000000
        elif label == "noncanonical_plus": postings[0]["units"] = "+40000000"
        elif label == "wrong_customer_balanced": postings[0]["account"] = "customer:bob"
        else: postings.extend([{"ordinal": 4, "account": "dummy:a", "asset": "BTC", "units": "1"}, {"ordinal": 5, "account": "dummy:b", "asset": "BTC", "units": "-1"}])
        observed, _ = observe(compare_borrow_transition, expected=baseline_value, after=baseline["value"]["after"], postings=postings)
        safe = not observed["accepted"] and observed.get("status") == 503
        mismatches.append({"id": label, "recorded_postings": postings, "actual": observed, "safety_assertion_passed": safe})
        if not safe: failures.append(label)
    unknown = default_inputs()
    unknown["asset"] = "UNKNOWN"
    unknown_observed, _ = observe(calculate_borrow_transition, descriptor=parsed, **unknown)
    status_contract = {"id": "unknown_asset_transition_error_contract", "reference_expected": {"accepted": False, "code": "credit_transition_invalid", "status": 503},
                       "actual": unknown_observed, "safety_assertion_passed": not unknown_observed["accepted"] and unknown_observed.get("code") == "credit_transition_invalid" and unknown_observed.get("status") == 503}
    if not status_contract["safety_assertion_passed"]:
        failures.append(status_contract["id"])
    with localcontext() as context:
        context.prec = 1
        context.traps[Inexact] = context.traps[Rounded] = True
        low_precision, _ = observe(calculate_borrow_transition, descriptor=parsed, **default_inputs())
    precision_safe = low_precision == baseline
    if not precision_safe: failures.append("decimal_context_changed_transition")
    elapsed = time.perf_counter() - started
    report = {"status": "INDEPENDENT_PURE_SAFETY_RED_IF_ASSERTIONS_FAIL_NO_DB_OR_NATIVE_EXECUTION",
              "frozen_commit": reviewed_commit, "original_reference_base": FROZEN,
              "expected_transition_source_sha256": expected_source_sha,
              "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT / "uta").rglob("*.py"))},
              "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "oracle_sha256": hashlib.sha256((ROOT / "tests/reference_credit_transition_math.py").read_bytes()).hexdigest(),
              "cpu_affinity": sorted(os.sched_getaffinity(0)), "python": platform.python_version(),
              "elapsed_after_imports_seconds": round(elapsed, 6), "ordinary_case_count": len(ordinary), "ordinary_cases": ordinary,
              "tiered_supplied_quote_assumptions_only": ref.supplied_tiered_quote(),
              "forged_descriptor": forged_descriptor_record, "forged_expected": forged_expected_record,
              "posting_negative_controls": mismatches, "status_contract": status_contract,
              "low_decimal_precision_identical": precision_safe, "failed_safety_assertions": failures,
              "scope": "offline arithmetic/caller contracts only; supplied quote is not recomputed from real archives; no source custody/auth/native/public borrow/activation or full audit claim"}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"ordinary_cases": len(ordinary), "failed_safety_assertions": failures, "elapsed_after_imports_seconds": report["elapsed_after_imports_seconds"]}))
    assert elapsed <= 3, "pure calculation window exceeded three seconds"
    assert not failures, "independent pure transition contract failures retained in raw evidence"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, nargs="?", default=ROOT / "evidence/runs/credit-transition-independent/original-red.json")
    parser.add_argument("--expected-source-sha256", default=SOURCE_SHA)
    parser.add_argument("--reviewed-commit", default=FROZEN)
    args = parser.parse_args()
    main(args.output.resolve(), args.expected_source_sha256, args.reviewed_commit)
