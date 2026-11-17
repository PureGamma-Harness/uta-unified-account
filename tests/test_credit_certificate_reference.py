"""Pure reference checks only; production differential tests arrive separately."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from credit_certificate_reference import exercise_case, strict_loads, trusted_context, units, validate


FIXTURE = Path(__file__).resolve().parent / "fixtures/credit_certificate_reference_v1.json"


class CertificateReferenceTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(FIXTURE.read_text())
        self.base = self.fixture["documents"]
        self.context = trusted_context(self.base)

    def test_independently_labelled_semantic_corpus(self):
        for case in self.fixture["cases"]:
            with self.subTest(case=case["id"]):
                result = exercise_case(self.base, self.context, case)
                self.assertTrue(result["matches"], result)

    def test_strict_json_layer_is_distinct_from_already_decoded_objects(self):
        for case in self.fixture["raw_json_decoder_cases"]:
            with self.subTest(case=case["id"]):
                try:
                    strict_loads(case["raw"])
                    valid = True
                except ValueError:
                    valid = False
                self.assertEqual(valid, case["expected_valid"])

    def test_native_64_bit_range_is_not_the_economic_integer_range(self):
        self.assertEqual(units("9223372036854775809"), 2 ** 63 + 1)
        self.assertEqual(units(str(10 ** 38 - 1)), 10 ** 38 - 1)
        self.assertEqual(units("0"), 0)

    def test_reference_context_is_external_and_not_mutated(self):
        before = deepcopy(self.base)
        case = next(c for c in self.fixture["cases"] if c["id"] == "rehash_changed_policy_all_references_updated")
        result = exercise_case(self.base, self.context, case)
        self.assertFalse(result["valid"])
        self.assertEqual(self.base, before)
        self.assertEqual(self.context["credit_policy_id"], before["credit_policy"]["id"])

    def test_pool_and_loan_quantity_budget_are_distinct(self):
        result = validate(self.base, self.context)
        self.assertEqual(result["pool_units"], 200000000)
        self.assertEqual(result["global_units"], 100000000)
        self.assertNotEqual(result["pool_units"], result["global_units"])


if __name__ == "__main__":
    unittest.main()
