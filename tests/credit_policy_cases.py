"""Public synthetic wire fixtures; no production serializer or financial oracle."""
from hashlib import sha256
import json


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def reseal(doc):
    doc["credit_policy_id"] = "credit-policy:" + sha256(canonical(doc["credit_policy"]).encode()).hexdigest()
    doc["certificate"]["credit_policy_id"] = doc["credit_policy_id"]
    doc["certificate_id"] = "credit-budget:" + sha256(canonical(doc["certificate"]).encode()).hexdigest()
    return doc


def descriptor(authority_id="credit:shard0", *, shard=0):
    authorities = ["credit:shard0", "credit:shard1"]
    authorities[shard] = authority_id
    if authorities[0] == authorities[1]:
        authorities[1 - shard] = "credit:other-shard"
    policy = {"format": 1, "name": "SYNTHETIC-CREDIT-ZERO-v1", "version": 1,
        "new_interest_rate": "0", "new_borrow_fee_rate": "0", "require_managed_inbox": True,
        "borrow_batch_size": 0, "production_approved": False, "credit_assets": ["BTC"]}
    allocations = [{"shard": index, "authority_id": authority, "limit_units": "50000000",
        "opening_principal_units": "0", "opening_interest_units": "0", "opening_pool_units": "100000000",
        "funding_claims": [{"source_reference": "synthetic:credit-pool:" + str(index),
            "command_id": "pool:" + str(index), "funded_units": "100000000"}]}
        for index, authority in enumerate(authorities)]
    return reseal({"format": 1, "stage": "NATIVE_PREPARED", "synthetic": True,
        "authority_id": authority_id, "shard": shard, "layout_hash": "a" * 64,
        "credit_policy": policy, "credit_policy_id": "filled-by-fixture",
        "certificate": {"format": 1, "budget_id": "synthetic:budget:1", "version": 1,
            "layout_hash": "a" * 64, "credit_policy_id": "filled-by-fixture",
            "authorities": [{"shard": index, "authority_id": authority}
                            for index, authority in enumerate(authorities)],
            "assets": {"BTC": {"scale": 8, "global_limit_units": "100000000", "allocations": allocations}}},
        "certificate_id": "filled-by-fixture"})
