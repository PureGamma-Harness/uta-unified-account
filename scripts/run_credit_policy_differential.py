#!/usr/bin/env python3
"""Actual pure-parser differential; independent expected values stay untouched."""

from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
import platform
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT))
import credit_descriptor_reference as reference
from uta import credit_policy as actual


SOURCE_COMMIT = "1d1dd5461f90caba42bef3f38fa4b7a5cb305721"
SOURCE_SHA256 = "18d9aa7e255aa4c0f4969848936a5e149b2a6dbe7acfa120a01d5fadab53c47a"


def context_adapter(context):
    result = deepcopy(context)
    rows = result.get("expected_authorities")
    valid_list = (type(rows) is list and bool(rows)
                  and all(type(row) is dict and set(row) == {"shard", "authority_id"}
                          and type(row["shard"]) is int and row["shard"] == index
                          and type(row["authority_id"]) is str for index, row in enumerate(rows))
                  and len({row["authority_id"] for row in rows}) == len(rows))
    if valid_list:
        result["expected_authorities"] = {row["shard"]: row["authority_id"] for row in rows}
        note = "independently verified complete contiguous list converted to equivalent mapping"
    else:
        # Forward invalid original context to the actual parser; never repair it.
        note = "invalid/non-list context forwarded unchanged; no duplicate/missing normalization"
    return result, note


def observe(raw, context):
    try:
        value = actual.validate_native_descriptor(raw, **context)
    except Exception as exc:
        return {"accepted": False, "exception_type": type(exc).__module__ + "." + type(exc).__name__,
                "typed_policy_error": isinstance(exc, actual.CreditPolicyError),
                "error_code": getattr(exc, "code", None), "error": str(exc)}, None
    allocations = {}
    typed_ints = True
    for asset in value.assets:
        rows = {}
        for row in asset.allocations:
            looked_up = value.allocation_for(asset.asset, row.shard)
            if looked_up != row:
                raise AssertionError("allocation_for returned a different allocation")
            typed_ints = typed_ints and all(type(v) is int for v in (
                row.limit_units, row.opening_principal_units, row.opening_interest_units,
                row.opening_pool_units, row.opening_debt_units))
            rows[str(row.shard)] = {"limit_units": row.limit_units, "principal_units": row.opening_principal_units,
                                   "interest_units": row.opening_interest_units, "pool_units": row.opening_pool_units,
                                   "funded_units": sum(c.funded_units for c in row.funding_claims)}
        allocations[asset.asset] = {"scale": asset.scale, "global_units": asset.global_limit_units,
                                    "allocated_units": sum(r.limit_units for r in asset.allocations),
                                    "opening_gross_units": sum(r.opening_debt_units for r in asset.allocations),
                                    "pool_units": sum(r.opening_pool_units for r in asset.allocations), "allocations": rows}
    return {"accepted": True, "descriptor_id": value.descriptor_id, "certificate_id": value.certificate_id,
            "policy_id": value.credit_policy_id, "canonical_payload": value.canonical_payload,
            "assets": allocations, "all_returned_quantities_exact_int": typed_ints,
            "stage": value.stage}, value


def main():
    source = Path(actual.__file__).resolve()
    if source != ROOT / "uta/credit_policy.py" or hashlib.sha256(source.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise SystemExit("actual parser source differs from pinned production artifact")
    fixture_path = ROOT / "tests/fixtures/credit_descriptor_reference_v1.json"
    fixture = json.loads(fixture_path.read_text())
    records, unexpected, original_differences, clarified = [], [], [], []
    started = time.perf_counter()
    for case in fixture["cases"]:
        raw, context = reference.materialize(fixture["base_descriptor"], case)
        independent = reference.exercise(fixture["base_descriptor"], case)
        actual_context, adapter_note = context_adapter(context)
        observed, _ = observe(raw, actual_context)
        original_match = observed["accepted"] == case["expected_valid"]
        expected_after_wire_clarification = case["expected_valid"]
        classification = "original_reference_matches"
        if case["id"] == "allocations_order_not_semantic_identity":
            expected_after_wire_clarification = False
            classification = "published_wire_clarification_requires_contiguous_sorted_allocations"
            clarified.append(case["id"])
        effective_match = observed["accepted"] == expected_after_wire_clarification
        output_match = None
        if observed["accepted"] and independent["valid"]:
            expected = independent["result"]
            output_match = (observed["assets"] == expected["assets"]
                            and observed["policy_id"] == expected["policy_id"]
                            and observed["certificate_id"] == expected["certificate_id"]
                            and observed["canonical_payload"] == expected["canonical_payload"]
                            and observed["descriptor_id"] == "credit-native:" + expected["canonical_payload_sha256"]
                            and observed["all_returned_quantities_exact_int"])
        if not original_match:
            original_differences.append(case["id"])
        if not effective_match or output_match is False or (not observed["accepted"] and not observed["typed_policy_error"]):
            unexpected.append(case["id"])
        records.append({"id": case["id"], "category": case["category"], "original_expected_valid": case["expected_valid"],
                        "reference_valid": independent["valid"], "reference_error": independent["error"],
                        "expected_after_explicit_wire_clarification": expected_after_wire_clarification,
                        "original_expectation_matches": original_match, "clarified_expectation_matches": effective_match,
                        "output_exactly_matches_independent_oracle": output_match,
                        "classification": classification, "context_adapter": adapter_note,
                        "input_canonical_sha256": reference.digest(raw), "actual": observed})

    # Positive parser output is immutable declared data, not an install/owner permit.
    base = deepcopy(fixture["base_descriptor"])
    context, _ = context_adapter(reference.base_context(base))
    observed, frozen = observe(base, context)
    mutation_results = []
    for obj, field in ((frozen, "authority_id"), (frozen.assets[0], "scale"), (frozen.assets[0].allocations[0], "limit_units")):
        try:
            setattr(obj, field, "MUTATED")
            denied = False
        except FrozenInstanceError:
            denied = True
        mutation_results.append({"object": type(obj).__name__, "field": field, "frozen_mutation_denied": denied})
    original_id = frozen.certificate_id
    base["certificate"]["assets"]["BTC"]["allocations"][0]["limit_units"] = "0"
    raw_alias_safe = frozen.certificate_id == original_id and frozen.allocation_for("BTC", 0).limit_units == 50000000
    elapsed = time.perf_counter() - started
    report = {"status": "ACTUAL_PURE_CERTIFICATE_PARSER_DIFFERENTIAL_ONLY_NATIVE_NOT_EXECUTED",
              "production_source_commit": SOURCE_COMMIT, "production_source_file": str(source), "production_source_sha256": SOURCE_SHA256,
              "preimplementation_reference_commit": "7947d9cb716be2bd6619f2eea73811adbec23986",
              "python": platform.python_version(), "elapsed_seconds": round(elapsed, 6),
              "actual_parser_cases": len(records), "accepted_cases": sum(r["actual"]["accepted"] for r in records),
              "original_reference_differences": original_differences, "explicit_wire_clarifications": clarified,
              "unexpected_differences": unexpected, "records": records,
              "immutable_output_checks": mutation_results, "raw_input_mutation_does_not_alias_result": raw_alias_safe,
              "qualification": "successful parsing is structure/context validation only, never owner/READY/activation/financial success"}
    output = ROOT / "evidence/runs/credit-certificate-reference/production-first-differential.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: report[k] for k in ("actual_parser_cases", "accepted_cases", "original_reference_differences", "unexpected_differences", "elapsed_seconds")}, ensure_ascii=False))
    return bool(unexpected or not raw_alias_safe or not all(m["frozen_mutation_denied"] for m in mutation_results))


if __name__ == "__main__":
    raise SystemExit(main())
