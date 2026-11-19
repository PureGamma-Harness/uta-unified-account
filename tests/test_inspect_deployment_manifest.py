"""Offline checker test DEFINITIONS. No test or checker execution in this change.

All sources here are synthetic text; these tests never import UTA. Digests made
by the test helper belong to intentionally authored test inputs, not a procedure
for establishing the trust of a deployment manifest.
"""

import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock


_REPOSITORY = Path(__file__).resolve().parents[1]
_FIXTURE = _REPOSITORY / "tests" / "fixtures" / "deployment_manifest_inspector"
_FIXTURE_SHA256 = "8942ab3d487b46b66a7cc568cf44edb3a4e3171185d18af6966525efae63ca78"
_SPEC = importlib.util.spec_from_file_location(
    "offline_deployment_inspector", _REPOSITORY / "tools" / "inspect_deployment_manifest.py"
)
inspector = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(inspector)


@unittest.skipUnless(hasattr(os, "O_NOFOLLOW"), "requires no-follow descriptor operations")
class OfflineDeploymentManifestTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "source-root"
        shutil.copytree(_FIXTURE, self.root)
        self.document = json.loads((self.root / "manifest.json").read_text(encoding="utf-8"))

    def inspect(self, expected=_FIXTURE_SHA256, manifest="manifest.json"):
        return inspector.inspect(str(self.root), manifest, expected)

    def authored_manifest(self, document):
        raw = (json.dumps(document, indent=2) + "\n").encode("utf-8")
        (self.root / "manifest.json").write_bytes(raw)
        return hashlib.sha256(raw).hexdigest()

    def assert_rejected(self, document, reason):
        result, code = self.inspect(self.authored_manifest(document))
        self.assertEqual(2, code)
        self.assertEqual("REJECTED", result["status"])
        self.assertEqual(reason, result["reason"])
        self.assertEqual([], result["verified_runtime_pins"])

    def test_hand_calculated_three_bytes_and_empty_file(self):
        result, code = self.inspect()
        self.assertEqual(0, code)
        self.assertEqual("STATIC_PIN_MATCH", result["status"])
        self.assertEqual("SYNTHETIC_FIXTURE_ONLY", result["source_scope"])
        self.assertEqual(2, result["counts"]["matched_runtime_files"])
        self.assertEqual(3, result["counts"]["declared_runtime_bytes"])
        self.assertEqual(3, result["counts"]["explicit_file_open_attempts"])
        self.assertEqual("NOT_PRODUCTION_APPROVAL", result["production_approval"])
        self.assertEqual("NOT_VERIFIED_EXTERNAL_TRUST_REQUIRED", result["expected_digest_trust"])
        self.assertEqual("NOT_VERIFIED", result["manifest_authentication"])
        self.assertIn("active_binary_and_loaded_code", result["unverified"])
        self.assertIn("journal_and_replay", result["unverified"])

    def test_same_size_source_change_is_detected(self):
        (self.root / "source" / "abc.txt").write_bytes(b"abd")
        result, code = self.inspect()
        self.assertEqual(1, code)
        self.assertEqual("STATIC_PIN_MISMATCH", result["status"])
        self.assertEqual(1, result["counts"]["mismatched_runtime_files"])
        self.assertEqual("source/abc.txt", result["mismatches"][0]["path"])

    def test_missing_source_is_reported(self):
        (self.root / "source" / "abc.txt").unlink()
        result, code = self.inspect()
        self.assertEqual(1, code)
        self.assertEqual([{"path": "source/abc.txt", "reason": "MISSING"}], result["missing"])

    def test_actual_unlisted_file_is_not_read_or_claimed_covered(self):
        (self.root / "source" / "unlisted-secret.txt").write_bytes(b"NEVER_RETURN_THIS_CONTENT")
        result, code = self.inspect()
        self.assertEqual(0, code)
        self.assertEqual(3, result["counts"]["explicit_file_open_attempts"])
        self.assertIn("unlisted_files_and_import_coverage", result["unverified"])
        self.assertNotIn("NEVER_RETURN_THIS_CONTENT", json.dumps(result))

    def test_extra_pin_without_updated_count_rejected(self):
        extra = copy.deepcopy(self.document["runtime_files"][1])
        extra["path"] = "source/extra.txt"
        self.document["runtime_files"].append(extra)
        self.assert_rejected(self.document, "RUNTIME_COUNT_MISMATCH")

    def test_native_boolean_cannot_be_file_byte_count(self):
        self.document["runtime_files"][0]["bytes"] = True
        self.assert_rejected(self.document, "SCHEMA_INTEGER_REQUIRED")

    def test_native_boolean_cannot_be_runtime_count(self):
        self.document["runtime_count"] = True
        self.assert_rejected(self.document, "SCHEMA_INTEGER_REQUIRED")

    def test_unknown_top_level_field_is_rejected(self):
        self.document["extensions"] = {"future": "ignored would be unsafe"}
        self.assert_rejected(self.document, "SCHEMA_FIELDS_MISSING_OR_UNKNOWN")

    def test_coin_precision_field_is_rejected_not_financially_interpreted(self):
        self.document["runtime_files"][0]["same_coin_precision"] = 8
        self.assert_rejected(self.document, "SCHEMA_FIELDS_MISSING_OR_UNKNOWN")

    def test_required_source_basis_is_not_inferred(self):
        del self.document["source_basis"]
        self.assert_rejected(self.document, "SCHEMA_FIELDS_MISSING_OR_UNKNOWN")

    def test_unknown_schema_version_is_rejected(self):
        self.document["schema"] = "offline-deployment-synthetic-source/v2"
        self.assert_rejected(self.document, "UNSUPPORTED_SCHEMA")

    def test_duplicate_pin_is_rejected(self):
        self.document["runtime_files"][1] = copy.deepcopy(self.document["runtime_files"][0])
        self.assert_rejected(self.document, "DUPLICATE_PATH")

    def test_noncanonical_and_escaping_paths_are_rejected(self):
        for path in ("../outside", "/etc/passwd", "source/../outside", "source//abc.txt",
                     "./source/abc.txt", "source\\abc.txt", "source/./abc.txt", "source/a\u0000b"):
            with self.subTest(path=path):
                document = copy.deepcopy(self.document)
                document["runtime_files"][0]["path"] = path
                self.assert_rejected(document, "INVALID_RELATIVE_PATH")

    def test_manifest_path_is_relative_and_canonical(self):
        for path in ("../manifest.json", str(self.root / "manifest.json"), "./manifest.json"):
            with self.subTest(path=path):
                result, code = self.inspect(manifest=path)
                self.assertEqual(2, code)
                self.assertEqual("INVALID_RELATIVE_PATH", result["reason"])

    def test_digest_mismatch_precedes_parsing_and_source_reads(self):
        (self.root / "manifest.json").write_bytes(b"{not json")
        result, code = self.inspect()
        self.assertEqual(2, code)
        self.assertEqual("MANIFEST_DIGEST_MISMATCH", result["reason"])
        self.assertEqual([], result["verified_runtime_pins"])

    def test_missing_external_digest_cannot_be_replaced_by_sidecar(self):
        (self.root / "manifest.sha256").write_text(_FIXTURE_SHA256, encoding="ascii")
        result, code = self.inspect(expected="")
        self.assertEqual(2, code)
        self.assertEqual("EXTERNAL_EXPECTED_SHA256_REQUIRED", result["reason"])

    def test_duplicate_json_key_is_rejected_even_with_matching_digest(self):
        raw = (self.root / "manifest.json").read_bytes().replace(
            b'"runtime_count": 2', b'"runtime_count": 2, "runtime_count": 2'
        )
        (self.root / "manifest.json").write_bytes(raw)
        result, code = self.inspect(hashlib.sha256(raw).hexdigest())
        self.assertEqual((2, "DUPLICATE_JSON_KEY"), (code, result["reason"]))

    def test_floats_nan_and_large_integer_are_rejected(self):
        for token, reason in ((b"3.0", "JSON_NON_INTEGER_NUMBER"),
                              (b"NaN", "JSON_NON_INTEGER_NUMBER"),
                              (b"999999999999999", "JSON_INTEGER_TOO_LARGE")):
            with self.subTest(token=token):
                raw = json.dumps(self.document).encode("utf-8").replace(b'"bytes": 3', b'"bytes": ' + token)
                (self.root / "manifest.json").write_bytes(raw)
                result, code = self.inspect(hashlib.sha256(raw).hexdigest())
                self.assertEqual((2, reason), (code, result["reason"]))

    def test_oversized_and_deep_manifests_are_rejected(self):
        (self.root / "manifest.json").write_bytes(b" " * (inspector.MAX_MANIFEST_BYTES + 1))
        result, code = self.inspect()
        self.assertEqual((2, "FILE_TOO_LARGE"), (code, result["reason"]))
        raw = ("[" * (inspector.MAX_JSON_DEPTH + 1) + "]" * (inspector.MAX_JSON_DEPTH + 1)).encode("ascii")
        (self.root / "manifest.json").write_bytes(raw)
        result, code = self.inspect(hashlib.sha256(raw).hexdigest())
        self.assertEqual((2, "JSON_TOO_DEEP"), (code, result["reason"]))

    def test_manifest_plus_runtime_share_total_stream_budget(self):
        budget = (self.root / "manifest.json").stat().st_size + 2
        with mock.patch.object(inspector, "MAX_TOTAL_BYTES", budget):
            result, code = self.inspect()
        self.assertEqual(1, code)
        self.assertEqual("TOTAL_READ_BUDGET_EXCEEDED", result["mismatches"][0]["reason"])
        self.assertLessEqual(result["counts"]["bytes_read_including_manifest"], budget)

    def test_oversized_runtime_is_never_streamed(self):
        (self.root / "source" / "abc.txt").write_bytes(b"x" * (inspector.MAX_FILE_BYTES + 1))
        result, code = self.inspect()
        self.assertEqual(1, code)
        self.assertEqual("FILE_TOO_LARGE", result["mismatches"][0]["reason"])

    def test_file_and_directory_symlinks_are_rejected(self):
        outside = Path(self.temporary.name) / "outside.txt"
        outside.write_bytes(b"abc")
        pinned = self.root / "source" / "abc.txt"
        pinned.unlink()
        pinned.symlink_to(outside)
        result, code = self.inspect()
        self.assertEqual(1, code)
        self.assertEqual("SYMLINK_OR_NOT_DIRECTORY", result["mismatches"][0]["reason"])
        pinned.unlink()
        pinned.write_bytes(b"abc")
        original = self.root / "source"
        original.rename(self.root / "real-source")
        original.symlink_to("real-source", target_is_directory=True)
        result, code = self.inspect()
        self.assertEqual(1, code)
        self.assertEqual(2, result["counts"]["mismatched_runtime_files"])

    def test_manifest_and_source_root_symlinks_are_rejected(self):
        manifest = self.root / "manifest.json"
        manifest.rename(self.root / "real-manifest.json")
        manifest.symlink_to("real-manifest.json")
        result, code = self.inspect()
        self.assertEqual((2, "SYMLINK_OR_NOT_DIRECTORY"), (code, result["reason"]))
        alias = Path(self.temporary.name) / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        result, code = inspector.inspect(str(alias), "real-manifest.json", _FIXTURE_SHA256)
        self.assertEqual((2, "SYMLINK_OR_NOT_DIRECTORY"), (code, result["reason"]))

    @unittest.skipUnless(hasattr(os, "mkfifo"), "requires FIFO support")
    def test_nonregular_fifo_is_rejected_without_waiting_for_writer(self):
        pinned = self.root / "source" / "abc.txt"
        pinned.unlink()
        os.mkfifo(pinned)
        result, code = self.inspect()
        self.assertEqual(1, code)
        self.assertEqual("NOT_REGULAR_FILE", result["mismatches"][0]["reason"])

    def test_file_changed_between_fstat_checks_is_rejected(self):
        original_read = inspector.os.read
        altered = False

        def changed_read(descriptor, size):
            nonlocal altered
            data = original_read(descriptor, size)
            if data == b"abc" and not altered:
                altered = True
                (self.root / "source" / "abc.txt").write_bytes(b"abcd")
            return data

        with mock.patch.object(inspector.os, "read", side_effect=changed_read):
            result, code = self.inspect()
        self.assertTrue(altered)
        self.assertEqual(1, code)
        self.assertEqual("FILE_CHANGED_DURING_READ", result["mismatches"][0]["reason"])

    def test_missing_cli_option_does_not_echo_private_arguments(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            code = inspector.main(["--source-root", "/private/DO_NOT_ECHO", "--unknown", "PRIVATE_KEY"])
        self.assertEqual(2, code)
        self.assertNotIn("DO_NOT_ECHO", output.getvalue())
        self.assertNotIn("PRIVATE_KEY", output.getvalue())
        self.assertEqual("INVALID_ARGUMENTS", json.loads(output.getvalue())["reason"])

    def test_v4_inventory_cannot_be_replaced_with_small_synthetic_set(self):
        self.document["schema"] = inspector.COMBINED_SCHEMA
        self.assert_rejected(self.document, "SCHEMA_FIELDS_MISSING_OR_UNKNOWN")

    def test_complete_combined_schema_requires_the_exact_67_paths(self):
        # Structural schema exercise only: zero-byte synthetic pins, no UTA reads.
        base, overlay = "0" * 40, "1" * 40
        document = {
            "schema": inspector.COMBINED_SCHEMA,
            "runtime_files": [
                {"path": path, "bytes": 0,
                 "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                 "origin": overlay if path in inspector._CHANGED_PATHS else base}
                for path in sorted(inspector._COMBINED_RUNTIME_PATHS)
            ],
            "runtime_count": 67, "runtime_bytes": 0, "python_count": 66,
            "explicit_inventory": "V4 unchanged", "unchanged_base_runtime_files": 64,
            "changed_runtime_files": sorted(inspector._CHANGED_PATHS),
            "verification_source_pins": [], "new_test_python_files": [],
        }
        document.update({field: base for field in inspector._COMMIT_FIELDS})
        document["market_control_origin"] = overlay
        document.update({field: "DECLARED_ONLY" for field in inspector._TEXT_FIELDS})
        document.update({field: 0 for field in inspector._INT_FIELDS})
        document.update({field: False for field in inspector._BOOL_FIELDS})
        self.assertEqual(67, len(inspector._validate_manifest(document)))
        document["runtime_files"][0]["path"] = "uta/unrecognized.py"
        with self.assertRaisesRegex(inspector.InspectionError, "V4_INVENTORY_MISMATCH"):
            inspector._validate_manifest(document)

    def test_file_limit_counts_manifest_too(self):
        empty = self.document["runtime_files"][1]
        self.document["runtime_files"] = [dict(empty, path="source/file%d.txt" % number)
                                          for number in range(inspector.MAX_FILES)]
        self.document["runtime_count"] = inspector.MAX_FILES
        self.document["runtime_bytes"] = 0
        self.assert_rejected(self.document, "SCHEMA_PIN_LIST_REQUIRED")
