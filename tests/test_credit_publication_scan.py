from hashlib import sha256
import json
import unittest

from scripts.credit_publication_scan import inspect_bytes


class CreditPublicationScanTests(unittest.TestCase):
    def test_nested_canonical_data_and_raw_log_nonce_are_flagged_without_leaking_value(self):
        marker = "synthetic-private-value-for-scanner-check"
        document = json.dumps({"retained": json.dumps({"owner_nonce": marker})}).encode()
        for path, data in (("observation.json", document), ("raw.txt", repr({"nonce": marker}).encode())):
            result = inspect_bytes(path, data)
            self.assertTrue(result)
            self.assertNotIn(marker, json.dumps(result))
            self.assertIn(sha256(marker.encode()).hexdigest(), json.dumps(result))

    def test_null_field_and_public_hash_are_not_credentials(self):
        self.assertEqual(inspect_bytes("manifest.json", json.dumps({"owner_nonce": None,
            "source_sha256": "a"*64, "nonce_sha256": "b"*64}).encode()), [])

    def test_database_and_runtime_generated_private_material_are_detected(self):
        key_marker = b"-----"+b"BEGIN PRIVATE KEY"+b"-----"
        self.assertEqual(inspect_bytes("source.py", key_marker)[0]["category"], "private_key_or_tls_material")
        self.assertEqual(inspect_bytes("renamed.txt", b"SQLite format 3\x00synthetic")[0]["category"], "database_bytes")


if __name__ == "__main__":
    unittest.main()
