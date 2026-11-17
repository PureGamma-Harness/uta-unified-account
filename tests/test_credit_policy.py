"""Certificate arithmetic and context binding, not activation or custody proof."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256
import json
import unittest

from tests.credit_policy_cases import canonical, descriptor, reseal
from uta.credit_policy import CreditPolicyError, validate_native_descriptor


class NativeCreditPolicyTests(unittest.TestCase):
    def parse(self, doc, **context):
        return validate_native_descriptor(doc, expected_authority_id="credit:shard0", **context)

    def rejected(self, doc, **context):
        with self.assertRaises(CreditPolicyError):
            self.parse(doc, **context)

    def test_canonical_typed_global_certificate_and_allocations(self):
        doc = descriptor()
        value = self.parse(json.dumps(doc, indent=4), expected_shard=0,
            expected_layout_hash="a" * 64, expected_asset_scales={"USD": 8, "BTC": 8},
            expected_authorities={0: "credit:shard0", 1: "credit:shard1"},
            expected_policy_id=doc["credit_policy_id"], expected_certificate_id=doc["certificate_id"])
        self.assertEqual(value.canonical_payload, canonical(doc))
        self.assertEqual(value.descriptor_id, "credit-native:" + sha256(canonical(doc).encode()).hexdigest())
        allocation = value.allocation_for("BTC", 0)
        self.assertEqual((allocation.limit_units, allocation.opening_pool_units), (50000000, 100000000))
        self.assertEqual(allocation.funding_claims[0].funded_units, 100000000)
        self.assertEqual(allocation.allocation_id, "credit-allocation:" + sha256(canonical(
            [doc["certificate_id"], "BTC", 0, "credit:shard0"]).encode()).hexdigest())
        self.assertEqual(value.stage, "NATIVE_PREPARED")
        self.assertFalse(hasattr(value, "ready"))
        with self.assertRaises(FrozenInstanceError):
            value.authority_id = "forged"

    def test_beyond_int64_values_remain_exact_bounded_minor_units(self):
        doc = descriptor()
        budget = doc["certificate"]["assets"]["BTC"]
        budget["global_limit_units"] = str(2**71)
        for entry in budget["allocations"]:
            entry["limit_units"] = str(2**70)
            entry["opening_principal_units"] = str(2**69)
            entry["opening_pool_units"] = str(2**70)
            entry["funding_claims"][0]["funded_units"] = str(2**70)
        value = self.parse(reseal(doc))
        self.assertEqual(value.assets[0].global_limit_units, 2**71)
        self.assertEqual(value.allocation_for("BTC", 1).opening_debt_units, 2**69)

    def test_zero_or_unassigned_budget_does_not_invent_funding_equality(self):
        doc = descriptor()
        for entry in doc["certificate"]["assets"]["BTC"]["allocations"]:
            entry["limit_units"] = "0"
        self.assertEqual(self.parse(reseal(doc)).assets[0].global_limit_units, 100000000)
        doc["certificate"]["assets"]["BTC"]["global_limit_units"] = "0"
        self.assertEqual(self.parse(reseal(doc)).assets[0].global_limit_units, 0)

    def test_rehashed_unreachable_shard_cannot_change_a_sealed_certificate(self):
        doc = descriptor()
        original = doc["certificate_id"]
        allocations = doc["certificate"]["assets"]["BTC"]["allocations"]
        allocations[0]["limit_units"], allocations[1]["limit_units"] = "0", "100000000"
        changed = reseal(doc)
        # A stateless structure validator cannot itself know a prior seal.
        self.assertNotEqual(self.parse(changed).certificate_id, original)
        self.rejected(changed, expected_certificate_id=original)

    def test_rehashed_external_layout_authority_policy_and_scale_mismatch(self):
        for context in ({"expected_layout_hash": "b" * 64}, {"expected_shard": 1},
                {"expected_authorities": {0: "other:authority", 1: "credit:shard1"}},
                {"expected_asset_scales": {"BTC": 9}},
                {"expected_policy_id": "credit-policy:" + "c" * 64}):
            with self.subTest(context=context):
                self.rejected(descriptor(), **context)
        doc = descriptor()
        doc["certificate"]["layout_hash"] = "b" * 64
        self.rejected(reseal(doc))

    def test_rehashed_overallocation_and_opening_interest_fail(self):
        doc = descriptor()
        allocation = doc["certificate"]["assets"]["BTC"]["allocations"][0]
        allocation["limit_units"] = "50000001"
        self.rejected(reseal(doc))
        doc = descriptor()
        allocation = doc["certificate"]["assets"]["BTC"]["allocations"][0]
        allocation["opening_principal_units"], allocation["opening_interest_units"] = "50000000", "1"
        self.rejected(reseal(doc))

    def test_rehashed_duplicate_sources_commands_and_missing_shard_fail(self):
        for mutation in ("source", "command", "missing", "authority", "order"):
            doc = descriptor()
            allocations = doc["certificate"]["assets"]["BTC"]["allocations"]
            if mutation == "source":
                allocations[1]["funding_claims"][0]["source_reference"] = allocations[0]["funding_claims"][0]["source_reference"]
            elif mutation == "command":
                allocations[0]["funding_claims"].append({"source_reference": "synthetic:other", "command_id": "pool:0", "funded_units": "1"})
            elif mutation == "missing":
                allocations.pop()
            elif mutation == "authority":
                allocations[1]["authority_id"] = "other:authority"
            else:
                allocations.reverse()
            with self.subTest(mutation=mutation):
                self.rejected(reseal(doc))

    def test_units_never_coerce_float_bool_sign_unicode_or_overflow(self):
        for amount in (1.0, True, 1, "-0", "-1", "+1", "01", "1.0", "1e8", "１", str(10**38)):
            doc = descriptor()
            doc["certificate"]["assets"]["BTC"]["allocations"][0]["limit_units"] = amount
            with self.subTest(amount=amount):
                self.rejected(reseal(doc))
        for key, value in (("format", True), ("shard", False), ("synthetic", 1),
                            ("stage", "ACTIVE"), ("verified", True)):
            doc = descriptor()
            doc[key] = value
            with self.subTest(key=key):
                self.rejected(reseal(doc))

    def test_disabled_policy_fields_cannot_be_rehashed_into_authorization(self):
        for key, value in (("new_interest_rate", "0.1"), ("new_borrow_fee_rate", "0.01"),
                           ("borrow_batch_size", True), ("borrow_batch_size", 1),
                           ("production_approved", True), ("require_managed_inbox", 1)):
            doc = descriptor()
            doc["credit_policy"][key] = value
            with self.subTest(key=key, value=value):
                self.rejected(reseal(doc))

    def test_duplicate_json_and_nonstandard_numbers_do_not_normalize_away(self):
        raw = canonical(descriptor())
        for invalid in (raw[:-1] + ',"format":1}', raw.replace('"format":1', '"format":1.0', 1),
                        raw.replace('"format":1', '"format":NaN', 1),
                        raw.replace('"format":1', '"format":' + '9' * 1000, 1)):
            self.rejected(invalid)

    def test_foreign_objects_and_recursive_payloads_do_not_execute_hooks(self):
        class Poison:
            def __str__(self):
                raise AssertionError("untrusted object hook executed")
        doc = descriptor()
        doc["unknown"] = Poison()
        self.rejected(doc)
        doc = descriptor()
        doc["unknown"] = doc
        self.rejected(doc)
        self.rejected(" " * (1024 * 1024 + 1))

    def test_missing_allocation_lookup_is_not_zero_credit(self):
        parsed = self.parse(descriptor())
        with self.assertRaises(CreditPolicyError) as error:
            parsed.allocation_for("USD", 0)
        self.assertEqual(error.exception.code, "credit_allocation_missing")
