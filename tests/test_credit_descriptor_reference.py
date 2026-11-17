import json
from pathlib import Path
import unittest

from credit_descriptor_reference import exercise


class DescriptorReferenceTests(unittest.TestCase):
    def test_independently_labelled_published_contract_cases(self):
        fixture = json.loads((Path(__file__).resolve().parent / "fixtures/credit_descriptor_reference_v1.json").read_text())
        for case in fixture["cases"]:
            with self.subTest(case=case["id"]):
                result = exercise(fixture["base_descriptor"], case)
                self.assertTrue(result["matches"], result)


if __name__ == "__main__":
    unittest.main()
