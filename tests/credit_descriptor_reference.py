"""Independent semantic oracle for the M3 wire contract supplied by its author.

No uta import. Integer, shape, hash and contextual binding checks are rebuilt
here. This is a reference decision, never a native authority or install permit.
"""

from copy import deepcopy
import hashlib
import json
import re

from credit_certificate_reference import InvalidCertificate, require, units


I64_MAX = 2 ** 63 - 1
TOP = {"format", "stage", "synthetic", "authority_id", "shard", "layout_hash", "credit_policy", "credit_policy_id", "certificate", "certificate_id"}
POLICY = {"format", "name", "version", "new_interest_rate", "new_borrow_fee_rate", "require_managed_inbox", "borrow_batch_size", "production_approved", "credit_assets"}
CERT = {"format", "budget_id", "version", "layout_hash", "credit_policy_id", "authorities", "assets"}
ASSET = {"scale", "global_limit_units", "allocations"}
ALLOCATION = {"shard", "authority_id", "limit_units", "opening_principal_units", "opening_interest_units", "opening_pool_units", "funding_claims"}
CLAIM = {"source_reference", "command_id", "funded_units"}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def refresh(raw):
    result = deepcopy(raw)
    result["credit_policy_id"] = "credit-policy:" + digest(result["credit_policy"])
    result["certificate"]["credit_policy_id"] = result["credit_policy_id"]
    result["certificate_id"] = "credit-budget:" + digest(result["certificate"])
    return result


def shape(value, keys, label):
    require(type(value) is dict and set(value) == keys, label + "_shape")


def integer(value, lo, hi, label):
    require(type(value) is int and lo <= value <= hi, label + "_integer")
    return value


def identity(value, label):
    require(type(value) is str and bool(value) and value.strip() == value, label + "_identity")
    return value


def hash_value(value, label):
    require(type(value) is str and bool(re.fullmatch("[0-9a-f]{64}", value)), label + "_hash")


def validate(raw, context):
    identity(context["expected_authority_id"], "expected_authority")
    if context.get("expected_asset_scales") is not None:
        require(type(context["expected_asset_scales"]) is dict, "expected_scales_type")
        for name, scale in context["expected_asset_scales"].items():
            identity(name, "expected_asset")
            integer(scale, 0, 18, "expected_scale")
    shape(raw, TOP, "descriptor")
    integer(raw["format"], 1, 1, "descriptor_format")
    require(raw["stage"] == "NATIVE_PREPARED", "prepared_stage_only")
    require(raw["synthetic"] is True, "synthetic_only")
    identity(raw["authority_id"], "authority")
    shard = integer(raw["shard"], 0, 255, "local_shard")
    hash_value(raw["layout_hash"], "layout")
    policy, cert = raw["credit_policy"], raw["certificate"]
    shape(policy, POLICY, "policy")
    integer(policy["format"], 1, 1, "policy_format")
    integer(policy["version"], 1, 1, "policy_version")
    require(policy["name"] == "SYNTHETIC-CREDIT-ZERO-v1", "policy_name")
    require(type(policy["new_interest_rate"]) is str and policy["new_interest_rate"] == "0", "zero_interest")
    require(type(policy["new_borrow_fee_rate"]) is str and policy["new_borrow_fee_rate"] == "0", "zero_fee")
    require(policy["require_managed_inbox"] is True and policy["production_approved"] is False, "policy_permissions")
    integer(policy["borrow_batch_size"], 0, 0, "batch_size")
    assets = policy["credit_assets"]
    require(type(assets) is list and bool(assets) and all(type(a) is str for a in assets), "policy_assets_type")
    require(assets == sorted(set(assets)), "policy_assets_sorted_unique")
    require(raw["credit_policy_id"] == "credit-policy:" + digest(policy), "policy_content_id")
    shape(cert, CERT, "certificate")
    integer(cert["format"], 1, 1, "certificate_format")
    integer(cert["version"], 1, I64_MAX, "certificate_version")
    identity(cert["budget_id"], "budget")
    require(cert["layout_hash"] == raw["layout_hash"], "certificate_layout")
    require(cert["credit_policy_id"] == raw["credit_policy_id"], "certificate_policy")
    require(raw["certificate_id"] == "credit-budget:" + digest(cert), "certificate_content_id")
    authorities = cert["authorities"]
    require(type(authorities) is list and 1 <= len(authorities) <= 256, "authorities_count")
    mapping = {}
    for expected_shard, authority in enumerate(authorities):
        shape(authority, {"shard", "authority_id"}, "authority")
        integer(authority["shard"], 0, 255, "authority_shard")
        require(authority["shard"] == expected_shard, "authorities_contiguous")
        value = identity(authority["authority_id"], "authority")
        require(value not in mapping.values(), "authority_duplicate")
        mapping[expected_shard] = value
    require(mapping.get(shard) == raw["authority_id"], "local_authority")
    require(type(cert["assets"]) is dict and set(cert["assets"]) == set(assets), "policy_certificate_asset_set")
    source_refs, funding_commands, totals = set(), set(), {}
    for asset in assets:
        identity(asset, "asset")
        data = cert["assets"][asset]
        shape(data, ASSET, "asset")
        scale = integer(data["scale"], 2 if asset == "USD" else 0, 8 if asset == "USD" else 18, "scale")
        total = units(data["global_limit_units"])
        allocations = data["allocations"]
        require(type(allocations) is list and len(allocations) == len(authorities), "all_shards_required")
        used_shards, allocated, opening, pool = set(), 0, 0, 0
        result_allocations = {}
        for allocation in allocations:
            shape(allocation, ALLOCATION, "allocation")
            s = integer(allocation["shard"], 0, len(authorities) - 1, "allocation_shard")
            require(s not in used_shards, "duplicate_allocation")
            used_shards.add(s)
            require(allocation["authority_id"] == mapping[s], "allocation_authority")
            limit = units(allocation["limit_units"])
            p = units(allocation["opening_principal_units"])
            i = units(allocation["opening_interest_units"])
            cash = units(allocation["opening_pool_units"])
            require(p + i <= limit, "opening_gross_exceeds_allocation")
            claims = allocation["funding_claims"]
            require(type(claims) is list, "funding_claims_type")
            order, funded = [], 0
            for claim in claims:
                shape(claim, CLAIM, "funding_claim")
                ref = identity(claim["source_reference"], "source")
                command = identity(claim["command_id"], "command")
                quantity = units(claim["funded_units"])
                require(quantity > 0, "funded_positive")
                require(ref not in source_refs, "source_reference_global_unique")
                require((s, command) not in funding_commands, "funding_command_cross_asset_unique")
                source_refs.add(ref)
                funding_commands.add((s, command))
                order.append((ref, command))
                funded += quantity
            require(order == sorted(order), "funding_claims_sorted")
            require(funded < 10 ** 38, "funded_sum_range")
            require(cash <= funded, "opening_pool_exceeds_funded")
            result_allocations[str(s)] = {"limit_units": limit, "principal_units": p, "interest_units": i,
                                          "pool_units": cash, "funded_units": funded}
            allocated, opening, pool = allocated + limit, opening + p + i, pool + cash
        require(used_shards == set(mapping), "complete_allocation_set")
        require(allocated <= total, "global_budget_exceeded")
        if context.get("expected_asset_scales") is not None:
            require(context["expected_asset_scales"].get(asset) == scale, "external_asset_scale")
        totals[asset] = {"scale": scale, "global_units": total, "allocated_units": allocated,
                         "opening_gross_units": opening, "pool_units": pool, "allocations": result_allocations}
    for field, key in (("authority_id", "expected_authority_id"), ("layout_hash", "expected_layout_hash"),
                       ("shard", "expected_shard"), ("credit_policy_id", "expected_policy_id"),
                       ("certificate_id", "expected_certificate_id")):
        if context.get(key) is not None:
            # Prevent expected bool0/1 from comparing equal to a shard integer.
            require(type(raw[field]) is type(context[key]) and raw[field] == context[key], "external_" + field)
    if context.get("expected_authorities") is not None:
        require(authorities == context["expected_authorities"], "external_authorities")
    return {"policy_id": raw["credit_policy_id"], "certificate_id": raw["certificate_id"],
            "canonical_payload": canonical(raw), "canonical_payload_sha256": digest(raw), "assets": totals}


def base_descriptor():
    authority_ids = [hashlib.sha256(("independent-authority:" + str(s)).encode()).hexdigest() for s in range(2)]
    policy = {"format": 1, "name": "SYNTHETIC-CREDIT-ZERO-v1", "version": 1,
              "new_interest_rate": "0", "new_borrow_fee_rate": "0", "require_managed_inbox": True,
              "borrow_batch_size": 0, "production_approved": False, "credit_assets": ["BTC", "USD"]}
    layout = hashlib.sha256(b"independent-reference-two-shard-layout").hexdigest()
    asset_data = {}
    for asset, scale, magnitude in (("BTC", 8, 100000000), ("USD", 2, 10000)):
        asset_data[asset] = {"scale": scale, "global_limit_units": str(magnitude), "allocations": [
            {"shard": s, "authority_id": authority_ids[s], "limit_units": str(magnitude // 2),
             "opening_principal_units": "0", "opening_interest_units": "0", "opening_pool_units": str(magnitude),
             "funding_claims": [{"source_reference": f"reference:{asset}:source:{s}", "command_id": f"pool-{asset}-{s}", "funded_units": str(magnitude)}]}
            for s in range(2)]}
    raw = {"format": 1, "stage": "NATIVE_PREPARED", "synthetic": True, "authority_id": authority_ids[0],
           "shard": 0, "layout_hash": layout, "credit_policy": policy, "credit_policy_id": "",
           "certificate": {"format": 1, "budget_id": "independent-reference-budget-1", "version": 1,
                           "layout_hash": layout, "credit_policy_id": "", "authorities": [
                               {"shard": s, "authority_id": value} for s, value in enumerate(authority_ids)], "assets": asset_data},
           "certificate_id": ""}
    return refresh(raw)


def base_context(raw):
    return {"expected_authority_id": raw["authority_id"], "expected_layout_hash": raw["layout_hash"],
            "expected_shard": raw["shard"], "expected_asset_scales": {a: data["scale"] for a, data in raw["certificate"]["assets"].items()},
            "expected_policy_id": raw["credit_policy_id"], "expected_certificate_id": None,
            "expected_authorities": deepcopy(raw["certificate"]["authorities"])}


def materialize(base, case):
    raw = deepcopy(base)
    context = base_context(base)
    for change in case.get("mutations", []):
        current = raw
        for part in change["path"][:-1]:
            current = current[part]
        if change.get("delete"):
            del current[change["path"][-1]]
        else:
            current[change["path"][-1]] = deepcopy(change["value"])
    if case.get("rehash", True):
        raw = refresh(raw)
    if case.get("seal"):
        context["expected_certificate_id"] = base["certificate_id"]
    context.update(deepcopy(case.get("context_overrides", {})))
    return raw, context


def exercise(base, case):
    raw, context = materialize(base, case)
    try:
        result = validate(raw, context)
        valid, error = True, None
    except (InvalidCertificate, KeyError, TypeError, ValueError) as exc:
        valid, result, error = False, None, str(exc)
    return {"id": case["id"], "category": case["category"], "expected_valid": case["expected_valid"],
            "valid": valid, "matches": valid == case["expected_valid"], "error": error, "result": result}
