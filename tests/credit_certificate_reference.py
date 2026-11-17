"""Independent stdlib semantic oracle, frozen before production API delivery.

The envelope is the published design JSON shape, NOT a proposed production API.
An eventual adapter must preserve these meanings, not import validation helpers.
"""

from copy import deepcopy
import hashlib
import json
import re


MAX_UNITS_EXCLUSIVE = 10 ** 38
PREFIXES = {"layout": "layout", "credit_policy": "credit-policy", "global_budget": "credit-budget"}


class InvalidCertificate(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise InvalidCertificate(reason)


def units(value):
    require(type(value) is str, "units_type")
    require(bool(re.fullmatch(r"0|[1-9][0-9]*", value, flags=re.ASCII)), "units_syntax")
    # Check length before int(), including Python's configurable digit limit.
    require(len(value) <= 38, "units_range")
    number = int(value)
    require(0 <= number < MAX_UNITS_EXCLUSIVE, "units_range")
    return number


def integer(value, minimum, maximum, label):
    require(type(value) is int, label + "_type")
    require(minimum <= value <= maximum, label + "_range")
    return value


def identifier(value, label):
    require(type(value) is str and bool(value) and value == value.strip(), label + "_identity")
    return value


def canonical(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def envelope(name, payload):
    text = canonical(payload)
    return {"id": PREFIXES[name] + ":" + hashlib.sha256(text.encode()).hexdigest(),
            "payload": deepcopy(payload), "canonical_payload": text}


def verify_envelope(name, record):
    require(type(record) is dict and set(record) == {"id", "payload", "canonical_payload"}, "document_shape")
    require(type(record["payload"]) is dict, "payload_type")
    expected = envelope(name, record["payload"])
    require(type(record["id"]) is str and record["id"] == expected["id"], "content_hash")
    require(type(record["canonical_payload"]) is str and record["canonical_payload"] == expected["canonical_payload"], "canonical_bytes")
    return record["payload"]


def strict_loads(text):
    def pairs(entries):
        result = {}
        for key, value in entries:
            require(key not in result, "duplicate_json_key")
            result[key] = value
        return result

    def constant(value):
        raise InvalidCertificate("nonfinite_json_constant:" + value)

    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def trusted_context(documents):
    """Test's external expected identity, not inferred from a mutated candidate."""
    layout = documents["layout"]["payload"]
    budget = documents["global_budget"]["payload"]
    return {"layout_id": documents["layout"]["id"],
            "credit_policy_id": documents["credit_policy"]["id"],
            "budget_business_id": budget["budget_business_id"], "budget_version": budget["version"],
            "asset": budget["asset"], "asset_scale": budget["asset_scale"],
            "shard_count": layout["shard_count"], "authorities": deepcopy(layout["authorities"]),
            "funding_references": {a["shard"]: a["funding_reference"] for a in budget["allocations"]}}


def validate(documents, context, sealed_budget_id=None):
    require(type(documents) is dict and set(documents) == set(PREFIXES), "documents_shape")
    layout = verify_envelope("layout", documents["layout"])
    policy = verify_envelope("credit_policy", documents["credit_policy"])
    budget = verify_envelope("global_budget", documents["global_budget"])
    require(documents["layout"]["id"] == context["layout_id"], "external_layout_identity")
    require(documents["credit_policy"]["id"] == context["credit_policy_id"], "external_policy_identity")
    if sealed_budget_id is not None:
        require(documents["global_budget"]["id"] == sealed_budget_id, "sealed_certificate_changed")
    integer(layout["format"], 1, 1, "layout_format")
    count = integer(layout["shard_count"], 1, context["shard_count"], "shard_count")
    require(count == context["shard_count"], "external_shard_count")
    require(type(layout["authorities"]) is dict and layout["authorities"] == context["authorities"], "external_authorities")
    require(set(layout["authorities"]) == {str(s) for s in range(count)}, "complete_authorities")
    require(len(set(layout["authorities"].values())) == count, "duplicate_authority")
    require(type(layout["asset_scales"]) is dict, "asset_scales_type")
    for asset, scale in layout["asset_scales"].items():
        identifier(asset, "asset")
        integer(scale, 0, 38, "scale")
    integer(policy["format"], 1, 1, "policy_format")
    require(policy["new_interest_rate"] == "0" and type(policy["new_interest_rate"]) is str, "new_interest_policy")
    require(policy["new_borrow_fee_rate"] == "0" and type(policy["new_borrow_fee_rate"]) is str, "fee_policy")
    require(policy["allow_new_interest_accrual"] is False, "interest_accrual_disabled")
    require(policy["allow_post_cap_pool_funding"] is False, "post_cap_funding_disabled")
    require(policy["cash_deficits_in_credit_quantity_budget"] is False, "budget_scope")
    require(policy["budget_scope"] == "borrow_principal_plus_interest_in_native_asset", "budget_scope")
    integer(policy["batch_size_required"], 0, 0, "batch_size")
    integer(budget["format"], 1, 1, "budget_format")
    integer(budget["version"], 1, context["budget_version"], "budget_version")
    require(budget["version"] == context["budget_version"], "external_budget_version")
    require(identifier(budget["budget_business_id"], "budget") == context["budget_business_id"], "external_budget_identity")
    require(budget["layout_id"] == context["layout_id"], "budget_layout_reference")
    require(budget["credit_policy_id"] == context["credit_policy_id"], "budget_policy_reference")
    require(budget["asset"] == context["asset"], "asset_identity")
    scale = integer(budget["asset_scale"], 0, 38, "asset_scale")
    require(scale == context["asset_scale"] == layout["asset_scales"][budget["asset"]], "asset_scale_identity")
    global_units = units(budget["global_limit_units"])
    require(type(budget["allocations"]) is list, "allocations_type")
    require(len(budget["allocations"]) == count, "complete_allocation_count")
    shards, authorities, sources = set(), set(), set()
    allocated = opening = pool_total = 0
    per_shard = {}
    for allocation in budget["allocations"]:
        require(type(allocation) is dict, "allocation_type")
        shard = integer(allocation["shard"], 0, count - 1, "shard")
        require(shard not in shards, "duplicate_shard")
        shards.add(shard)
        authority = identifier(allocation["authority_id"], "authority")
        require(authority == context["authorities"][str(shard)], "authority_identity")
        require(authority not in authorities, "duplicate_authority")
        authorities.add(authority)
        source = identifier(allocation["funding_reference"], "funding")
        require(source not in sources, "duplicate_funding_reference")
        sources.add(source)
        require(source == context["funding_references"][shard], "external_funding_identity")
        require(allocation["funding_proof_kind"] == "SYNTHETIC_FIXTURE_NOT_EXTERNAL_CONFIRMATION", "funding_kind")
        limit = units(allocation["limit_units"])
        principal = units(allocation["opening_principal_units"])
        interest = units(allocation["opening_interest_units"])
        pool = units(allocation["pool_opening_units"])
        debt = principal + interest
        require(debt <= limit, "opening_gross_exceeds_allocation")
        allocated += limit
        opening += debt
        pool_total += pool
        per_shard[str(shard)] = {"allocation_units": limit, "opening_gross_units": debt,
                                "headroom_units": limit - debt, "pool_units": pool}
    require(shards == set(range(count)), "complete_shard_set")
    require(allocated <= global_units, "allocation_sum_exceeds_global")
    return {"allocated_units": allocated, "global_units": global_units, "opening_gross_units": opening,
            "unassigned_global_units": global_units - allocated, "pool_units": pool_total,
            "per_shard": per_shard, "budget_id": documents["global_budget"]["id"]}


def refresh(documents):
    """Rehash EVERY dependent reference; negative cases must survive rehashing."""
    result = deepcopy(documents)
    for name in ("layout", "credit_policy"):
        result[name] = envelope(name, result[name]["payload"])
    result["global_budget"]["payload"]["layout_id"] = result["layout"]["id"]
    result["global_budget"]["payload"]["credit_policy_id"] = result["credit_policy"]["id"]
    result["global_budget"] = envelope("global_budget", result["global_budget"]["payload"])
    return result


def exercise_case(base, context, case):
    candidate = deepcopy(base)
    for mutation in case.get("mutations", []):
        target = candidate
        for component in mutation["path"][:-1]:
            target = target[component]
        if mutation.get("delete"):
            del target[mutation["path"][-1]]
        else:
            target[mutation["path"][-1]] = deepcopy(mutation["value"])
    if case.get("refresh", True) == "budget_only":
        candidate["global_budget"] = envelope("global_budget", candidate["global_budget"]["payload"])
    elif case.get("refresh", True):
        candidate = refresh(candidate)
    try:
        result = validate(candidate, context, base["global_budget"]["id"] if case.get("sealed") else None)
        valid, error = True, None
    except (InvalidCertificate, KeyError, TypeError, ValueError) as exc:
        result, valid, error = None, False, str(exc)
    return {"id": case["id"], "expected_valid": case["expected_valid"], "valid": valid,
            "matches": valid == case["expected_valid"], "error": error, "result": result,
            "rehash_all_references": case.get("refresh", True), "category": case["category"],
            "wire_status": case.get("wire_status", "NORMATIVE_SEMANTIC")}
