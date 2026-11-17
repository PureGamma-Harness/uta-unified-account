#!/usr/bin/env python3
"""Independent vectors derived from the author's wire contract, no uta import."""

from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from credit_descriptor_reference import base_descriptor


base, cases = base_descriptor(), []
cert = ["certificate"]
asset = lambda name, field: cert + ["assets", name, field]
alloc = lambda name, shard, field: asset(name, "allocations") + [shard, field]
claim = lambda name, shard, field: alloc(name, shard, "funding_claims") + [0, field]


def m(path, value=None, delete=False):
    return {"path": path, **({"delete": True} if delete else {"value": value})}


def add(name, changes=(), valid=False, category="semantic", **options):
    cases.append({"id": name, "category": category, "mutations": list(changes), "expected_valid": valid, **options})


add("valid_two_assets_complete_certificate", valid=True, category="positive")
add("unassigned_budget_is_allowed", [m(asset("BTC", "global_limit_units"), "200000000")], valid=True, category="positive")
add("opening_interest_boundary", [m(alloc("BTC", 0, "opening_principal_units"), "49999999"), m(alloc("BTC", 0, "opening_interest_units"), "1")], valid=True, category="positive")
add("empty_claims_zero_pool_permitted", [m(alloc("BTC", 0, "funding_claims"), []), m(alloc("BTC", 0, "opening_pool_units"), "0")], valid=True, category="positive")
add("zero_allocation_shard_is_not_omitted", [m(alloc("BTC", 0, "limit_units"), "0")], valid=True, category="positive")
add("zero_global_all_allocations_zero", [m(asset("BTC", "global_limit_units"), "0"), m(alloc("BTC", 0, "limit_units"), "0"), m(alloc("BTC", 1, "limit_units"), "0")], valid=True, category="positive")
add("certificate_version_i64max", [m(cert + ["version"], 2 ** 63 - 1)], valid=True, category="positive")
for value in (2 ** 53 - 1, 2 ** 53 + 1, 2 ** 63 - 1, 2 ** 63, 2 ** 63 + 1, 10 ** 38 - 1):
    add("large_exact_" + str(value), [m(asset("BTC", "global_limit_units"), str(value)), m(alloc("BTC", 0, "limit_units"), str(value)), m(alloc("BTC", 1, "limit_units"), "0"), m(alloc("BTC", 0, "opening_pool_units"), str(value)), m(claim("BTC", 0, "funded_units"), str(value))], valid=True, category="positive_large_units")
add("same_command_id_on_different_shards_is_allowed", [m(claim("BTC", 1, "command_id"), "pool-BTC-0")], valid=True, category="positive")
add("allocations_order_not_semantic_identity", [m(asset("BTC", "allocations"), list(reversed(base["certificate"]["assets"]["BTC"]["allocations"])))], valid=True, category="wire_order_pending")
for key, wrong in (("format", True), ("format", 1.0), ("format", "1"), ("stage", "READY"), ("stage", "ACTIVE"), ("stage", None), ("synthetic", 1), ("synthetic", False), ("shard", True), ("shard", 0.0), ("shard", "0"), ("shard", -1), ("shard", 2), ("layout_hash", "A" * 64), ("layout_hash", "a" * 63), ("authority_id", "")):
    add("descriptor_bad_" + key + "_" + repr(wrong), [m([key], wrong)], category="descriptor_type_identity")
for field in ("format", "shard", "stage", "synthetic", "authority_id", "layout_hash", "credit_policy", "certificate"):
    if field not in ("credit_policy", "certificate"):
        add("descriptor_missing_" + field, [m([field], delete=True)], category="strict_shapes")
add("descriptor_extra_field", [m(["enabled"], True)], category="strict_shapes")
for key, value in (("format", True), ("version", True), ("version", 2), ("name", "OTHER"), ("new_interest_rate", 0), ("new_interest_rate", "0.1"), ("new_borrow_fee_rate", False), ("new_borrow_fee_rate", "0.01"), ("require_managed_inbox", 1), ("require_managed_inbox", False), ("borrow_batch_size", False), ("borrow_batch_size", 1), ("production_approved", 0), ("production_approved", True), ("credit_assets", ["USD", "BTC"]), ("credit_assets", ["BTC", "BTC"]), ("credit_assets", []), ("credit_assets", "BTC")):
    add("policy_bad_" + key + "_" + repr(value), [m(["credit_policy", key], value)], category="policy_invariants", context_overrides={"expected_policy_id": None})
for key, value in (("format", True), ("version", 0), ("version", True), ("version", 1.0), ("version", "1"), ("version", 2 ** 63), ("budget_id", ""), ("layout_hash", "f" * 64)):
    add("certificate_bad_" + key + "_" + repr(value), [m(cert + [key], value)], category="certificate_identity")
for key in ("budget_id", "assets", "authorities"):
    add("certificate_missing_" + key, [m(cert + [key], delete=True)], category="strict_shapes")
add("certificate_extra_field", [m(cert + ["borrow_enabled"], True)], category="strict_shapes")
for value in (None, True, False, 1, 1.0, [], {}, "", "-1", "+1", "01", "1.0", "1e2", " 1", "1 ", "1_0", "١", "１２", "NaN", str(10 ** 38), "9" * 80):
    add("global_units_bad_" + repr(value), [m(asset("BTC", "global_limit_units"), value)], category="strict_units")
for field in ("limit_units", "opening_principal_units", "opening_interest_units", "opening_pool_units"):
    for label, value in (("bool", True), ("float", 1.0), ("negative", "-1"), ("fractional", "0.1"), ("overflow", str(10 ** 38))):
        add(field + "_bad_" + label, [m(alloc("BTC", 0, field), value)], category="strict_units")
for asset_name, field_value in (("BTC", -1), ("BTC", 19), ("BTC", True), ("BTC", 8.0), ("USD", 1), ("USD", 9), ("USD", False)):
    add("scale_bad_" + asset_name + "_" + repr(field_value), [m(asset(asset_name, "scale"), field_value)], category="precision")
add("asset_scale_rehashed_but_external_context_differs", [m(asset("BTC", "scale"), 7)], category="external_binding")
add("asset_set_certificate_does_not_match_policy", [m(cert + ["assets", "USD"], delete=True)], category="asset_set")
add("allocation_sum_exceeded", [m(alloc("BTC", 1, "limit_units"), "50000001")], category="global_cap")
add("allocation_sum_no_i64_or_decimal_overflow", [m(asset("BTC", "global_limit_units"), str(10 ** 38 - 1)), m(alloc("BTC", 0, "limit_units"), str(10 ** 38 - 1)), m(alloc("BTC", 1, "limit_units"), "1")], category="global_cap")
add("interest_makes_opening_gross_exceed", [m(alloc("BTC", 0, "opening_principal_units"), "50000000"), m(alloc("BTC", 0, "opening_interest_units"), "1")], category="opening_gross")
add("opening_gross_addition_cannot_overflow", [m(asset("BTC", "global_limit_units"), str(10 ** 38 - 1)), m(alloc("BTC", 0, "limit_units"), str(10 ** 38 - 1)), m(alloc("BTC", 1, "limit_units"), "0"), m(alloc("BTC", 0, "opening_principal_units"), str(10 ** 38 - 1)), m(alloc("BTC", 0, "opening_interest_units"), "1")], category="opening_gross")
for value, label in (([], "none"), (base["certificate"]["authorities"][:1], "missing"), (base["certificate"]["authorities"] * 2, "duplicate")):
    add("authorities_" + label, [m(cert + ["authorities"], value)], category="full_certificate")
add("authorities_gap", [m(cert + ["authorities", 1, "shard"], 2)], category="full_certificate")
add("authorities_bool_shard", [m(cert + ["authorities", 0, "shard"], False)], category="strict_types")
add("authorities_duplicate_identity", [m(cert + ["authorities", 1, "authority_id"], base["authority_id"])], category="duplicate_identity")
add("allocations_missing_other_shard", [m(asset("BTC", "allocations"), base["certificate"]["assets"]["BTC"]["allocations"][:1])], category="full_certificate")
add("allocations_duplicate_shard", [m(alloc("BTC", 1, "shard"), 0)], category="duplicate_identity")
add("allocation_wrong_authority", [m(alloc("BTC", 0, "authority_id"), base["certificate"]["authorities"][1]["authority_id"])], category="external_binding")
add("duplicate_source_across_shards", [m(claim("BTC", 1, "source_reference"), base["certificate"]["assets"]["BTC"]["allocations"][0]["funding_claims"][0]["source_reference"])], category="funding_uniqueness")
add("duplicate_source_across_assets", [m(claim("USD", 0, "source_reference"), base["certificate"]["assets"]["BTC"]["allocations"][0]["funding_claims"][0]["source_reference"])], category="funding_uniqueness")
add("duplicate_command_same_shard_cross_asset", [m(claim("USD", 0, "command_id"), "pool-BTC-0")], category="funding_uniqueness")
for label, value in (("zero", "0"), ("bool", True), ("float", 1.0), ("negative", "-1"), ("overflow", str(10 ** 38))):
    add("funded_units_bad_" + label, [m(claim("BTC", 0, "funded_units"), value)], category="funding_quantity")
add("pool_exceeds_actual_claim_sum", [m(alloc("BTC", 0, "opening_pool_units"), "100000001")], category="funding_quantity")
add("claims_sum_exceeds_quantity_bound", [m(alloc("BTC", 0, "funding_claims"), [{"source_reference": "reference:BTC:source:0:a", "command_id": "claim-a", "funded_units": str(10 ** 38 - 1)}, {"source_reference": "reference:BTC:source:0:b", "command_id": "claim-b", "funded_units": "1"}])], category="funding_quantity")
add("claims_unsorted", [m(alloc("BTC", 0, "funding_claims"), [{"source_reference": "reference:BTC:z", "command_id": "claim-z", "funded_units": "50000000"}, {"source_reference": "reference:BTC:a", "command_id": "claim-a", "funded_units": "50000000"}])], category="funding_order")
add("hash_certificate_wrong", [m(["certificate_id"], "credit-budget:" + "0" * 64)], category="content_hash", rehash=False)
add("hash_policy_wrong", [m(["credit_policy_id"], "credit-policy:" + "0" * 64)], category="content_hash", rehash=False)
add("hash_policy_reference_wrong", [m(cert + ["credit_policy_id"], "credit-policy:" + "0" * 64)], category="content_hash", rehash=False)
for key, value in (("expected_authority_id", "e" * 64), ("expected_layout_hash", "e" * 64), ("expected_shard", 1), ("expected_shard", False), ("expected_policy_id", "credit-policy:" + "0" * 64), ("expected_certificate_id", "credit-budget:" + "0" * 64), ("expected_asset_scales", {"BTC": 7, "USD": 2}), ("expected_asset_scales", {"BTC": True, "USD": 2}), ("expected_authorities", list(reversed(base["certificate"]["authorities"])))):
    add("external_expected_mismatch_" + key + "_" + repr(value), category="external_binding", context_overrides={key: value})
alternative = [m(alloc("BTC", 0, "limit_units"), "0"), m(alloc("BTC", 1, "limit_units"), "100000000")]
add("alternative_partition_static_only", alternative, valid=True, category="static_history_boundary")
add("unknown_must_not_reallocate_sealed_certificate", alternative, category="static_history_boundary", seal=True)
add("sealed_same_certificate_replay", valid=True, category="static_history_boundary", seal=True)

fixture = {"reference_format": 1, "status": "INDEPENDENT_DESCRIPTOR_ORACLE_FROM_PUBLISHED_INTERFACE_BEFORE_IMPLEMENTATION_READ",
           "base_commit": "aa72a953bcbe5fd809b1b159a751d152afedb5d9", "base_descriptor": base,
           "cases": cases, "ordering_note": "funding claims sort by (source_reference,command_id); allocation-order acceptance kept separately tagged pending exact wire contract",
           "runtime_status": "NO_NATIVE_EXECUTION_NO_OWNER_READY_ACTIVATION_OR_FINANCIAL_SUCCESS_CLAIM"}
(ROOT / "tests/fixtures/credit_descriptor_reference_v1.json").write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n")
print(f"independent descriptor corpus: {len(cases)} cases")
