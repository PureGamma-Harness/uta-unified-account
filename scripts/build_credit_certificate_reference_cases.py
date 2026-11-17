#!/usr/bin/env python3
"""Freeze independent test vectors before the production certificate API exists."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "tests/fixtures/managed_credit_v1_canonical_example.json"
design = json.loads(source.read_text())
base = {name: deepcopy(design["documents"][name]) for name in ("layout", "credit_policy", "global_budget")}
cases = []


def mutation(path, value=None, delete=False):
    return {"path": path, **({"delete": True} if delete else {"value": value})}


def add(name, mutations=(), valid=False, category="semantic", **options):
    cases.append({"id": name, "category": category, "mutations": list(mutations), "expected_valid": valid, **options})


budget = ["global_budget", "payload"]
allocation = lambda shard, field: budget + ["allocations", shard, field]
add("baseline_full_design_certificate", valid=True, category="positive")
add("unallocated_global_headroom_is_allowed", [mutation(budget + ["global_limit_units"], "200000000")], valid=True, category="positive")
add("opening_interest_exactly_reaches_allocation", [mutation(allocation(0, "opening_principal_units"), "49000000"), mutation(allocation(0, "opening_interest_units"), "1000000")], valid=True, category="positive")
add("zero_allocation_shard_still_in_complete_certificate", [mutation(allocation(1, "limit_units"), "0")], valid=True, category="positive", wire_status="ZERO_ALLOCATION_POLICY_PENDING_API")
add("zero_global_disables_new_borrow_but_is_mathematically_consistent", [mutation(budget + ["global_limit_units"], "0"), mutation(allocation(0, "limit_units"), "0"), mutation(allocation(1, "limit_units"), "0")], valid=True, category="positive", wire_status="ZERO_GLOBAL_POLICY_PENDING_API")
for n in (2 ** 53 - 1, 2 ** 53 + 1, 2 ** 63 - 1, 2 ** 63, 2 ** 63 + 1, 10 ** 38 - 1):
    add("exact_large_units_" + str(n), [mutation(budget + ["global_limit_units"], str(n)), mutation(allocation(0, "limit_units"), str(n)), mutation(allocation(0, "pool_opening_units"), str(n)), mutation(allocation(1, "limit_units"), "0")], valid=True, category="positive_exact_integer", wire_status="DECLARED_38_MINOR_UNIT_DIGITS_PENDING_API")

bad_units = [None, True, False, 1, 1.0, [], {}, "", "-1", "+1", "01", "00", "1.0", "1e2", " 1", "1 ", "1_0", "١", "１２", "NaN", "Infinity", "1\u0000", str(10 ** 38), "9" * 80]
for index, value in enumerate(bad_units):
    add("global_units_bad_" + str(index), [mutation(budget + ["global_limit_units"], value)], category="units_lexical_type_range")
for field in ("limit_units", "opening_principal_units", "opening_interest_units", "pool_opening_units"):
    for label, value in (("bool", True), ("float", 1.0), ("negative", "-1"), ("fractional", "0.1"), ("overflow", str(10 ** 38))):
        add(field + "_bad_" + label, [mutation(allocation(0, field), value)], category="allocation_units_type_range")
    add(field + "_missing", [mutation(allocation(0, field), delete=True)], category="completeness")
for field in ("format", "version", "asset_scale"):
    for label, value in (("bool", True), ("float", 1.0), ("string", "1"), ("null", None), ("negative", -1)):
        add("budget_" + field + "_bad_" + label, [mutation(budget + [field], value)], category="strict_integer_types")
for label, value in (("bool", True), ("float", 0.0), ("string", "0"), ("negative", -1), ("unknown", 2)):
    add("shard_bad_" + label, [mutation(allocation(0, "shard"), value)], category="strict_shard_identity")
add("allocation_sum_one_unit_over_global", [mutation(allocation(1, "limit_units"), "50000001")], category="global_cap")
add("legal_components_sum_beyond_quantity_bound", [mutation(budget + ["global_limit_units"], str(10 ** 38 - 1)), mutation(allocation(0, "limit_units"), str(10 ** 38 - 1)), mutation(allocation(1, "limit_units"), "1")], category="global_cap_no_overflow")
add("principal_alone_fits_but_interest_over_cap", [mutation(allocation(0, "opening_principal_units"), "50000000"), mutation(allocation(0, "opening_interest_units"), "1")], category="opening_gross")
add("opening_addition_beyond_quantity_bound", [mutation(budget + ["global_limit_units"], str(10 ** 38 - 1)), mutation(allocation(0, "limit_units"), str(10 ** 38 - 1)), mutation(allocation(1, "limit_units"), "0"), mutation(allocation(0, "opening_principal_units"), str(10 ** 38 - 1)), mutation(allocation(0, "opening_interest_units"), "1")], category="opening_gross_no_overflow")
add("pool_does_not_net_away_opening_debt", [mutation(allocation(0, "opening_principal_units"), "50000001"), mutation(allocation(0, "pool_opening_units"), "99999999")], category="gross_not_net")
add("only_local_shard_is_not_full_certificate", [mutation(budget + ["allocations"], base["global_budget"]["payload"]["allocations"][:1])], category="completeness")
add("no_allocations", [mutation(budget + ["allocations"], [])], category="completeness")
add("allocations_not_list", [mutation(budget + ["allocations"], {})], category="strict_types")
add("duplicate_shard_cannot_be_dict_overwritten", [mutation(allocation(1, "shard"), 0)], category="duplicate_identity")
add("duplicate_authority", [mutation(allocation(1, "authority_id"), "fixture:shard0")], category="duplicate_identity")
add("duplicate_funding_reference", [mutation(allocation(1, "funding_reference"), "fixture:pool-source:0")], category="duplicate_identity")
for field, value in (("authority_id", "other-authority"), ("funding_reference", "other-source"), ("funding_proof_kind", "CONFIRMED_REAL_FUNDS")):
    add("rehash_still_wrong_" + field, [mutation(allocation(0, field), value)], category="external_identity_after_rehash")
for field, value in (("asset", "USD"), ("asset", "UNKNOWN"), ("asset_scale", 7), ("version", 2), ("budget_business_id", "new-budget")):
    add("rehash_still_wrong_budget_" + field + "_" + str(value), [mutation(budget + [field], value)], category="external_identity_after_rehash")
for field, value in (("layout_id", "layout:" + "0" * 64), ("credit_policy_id", "credit-policy:" + "0" * 64)):
    add("rehash_wrong_cross_reference_" + field, [mutation(budget + [field], value)], category="reference_identity", refresh="budget_only")
add("rehash_changed_layout_name_all_references_updated", [mutation(["layout", "payload", "fixture_layout_name"], "another-layout")], category="external_identity_after_rehash")
add("rehash_changed_policy_all_references_updated", [mutation(["credit_policy", "payload", "new_interest_rate"], "0.01")], category="external_identity_after_rehash")
add("rehash_changed_policy_boolean_type", [mutation(["credit_policy", "payload", "allow_new_interest_accrual"], 0)], category="external_identity_after_rehash")
add("hash_changed_without_payload", [mutation(["global_budget", "id"], "credit-budget:" + "0" * 64)], category="hash_bytes", refresh=False)
add("canonical_bytes_whitespace_not_exact", [mutation(["global_budget", "canonical_payload"], " " + base["global_budget"]["canonical_payload"])], category="hash_bytes", refresh=False)
alternative = [mutation(allocation(0, "limit_units"), "0"), mutation(allocation(1, "limit_units"), "100000000")]
add("alternative_partition_is_statically_consistent_before_seal", alternative, valid=True, category="static_vs_history_boundary")
add("sealed_unknown_partition_must_not_change_even_after_rehash", alternative, category="sealed_identity", sealed=True)
add("sealed_certificate_replay_unchanged_is_allowed", valid=True, category="sealed_identity", sealed=True)

result = {"reference_format": 1, "status": "INDEPENDENT_REFERENCE_BEFORE_PRODUCTION_API_NO_NATIVE_EXECUTION",
          "base_commit": "aa72a953bcbe5fd809b1b159a751d152afedb5d9",
          "design_fixture_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
          "unit_contract": "nonnegative canonical ASCII integer strings, each <10^38 minor units; no float/SQLite CAST",
          "wire_choices_pending_api": ["zero global/allocation acceptance", "38 minor-unit-digit bound versus explicit narrower documented contract", "serialized JSON/unknown fields/identifier grammar and versioning; do not treat wire differences as proven vulnerabilities"],
          "documents": base, "cases": cases,
          "raw_json_decoder_cases": [
              {"id": "duplicate_json_key", "raw": "{\"asset\":\"BTC\",\"asset\":\"USD\"}", "expected_valid": False},
              {"id": "nan_json_constant", "raw": "{\"units\":NaN}", "expected_valid": False},
              {"id": "infinity_json_constant", "raw": "{\"units\":Infinity}", "expected_valid": False},
              {"id": "ordinary_json_zero", "raw": "{\"units\":\"0\"}", "expected_valid": True}],
          "runtime_not_executed": ["NATIVE_PREPARED owner acquire/READY/activation/new financial success rejection", "actual native amount-units canonical legs and persisted semantic identity", "no-cap base/batch regression", "sealed identity enforcement at real install/load including UNKNOWN", "real audit/source/artifact replay qualification"]}
target = ROOT / "tests/fixtures/credit_certificate_reference_v1.json"
target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(f"reference corpus: {len(cases)} certificate cases + {len(result['raw_json_decoder_cases'])} raw JSON cases")
