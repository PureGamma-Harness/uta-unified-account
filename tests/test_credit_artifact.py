"""Real source/loaded-code identity; no borrowing, lease or archive execution."""
from copy import deepcopy
from hashlib import sha256
import importlib
from pathlib import Path
import unittest
from unittest.mock import patch

from uta import credit, writer_fence
from uta.credit_artifact import (CreditArtifactError, _json, _loaded_modules,
    assert_current_credit_artifact, credit_artifact_id, credit_code_artifact, parse_credit_artifact)


class CreditArtifactTests(unittest.TestCase):
    def test_complete_actual_engine_includes_credit_native_and_static_sql(self):
        artifact = credit_code_artifact()
        self.assertIn("uta.credit.CreditService._borrow", artifact["loaded_credit_engine"])
        self.assertIn("uta.credit_native.prepare_credit_native", artifact["loaded_credit_engine"])
        self.assertIn("uta.credit_policy.UNIT_LIMIT", artifact["loaded_credit_constants"])
        self.assertIn("uta.credit_native.TRIGGER_SQL", artifact["loaded_credit_constants"])
        self.assertIn("uta.durable_gateway.DurableCommandAPI.call", artifact["loaded_credit_engine"])
        self.assertFalse(artifact["activation_permission"])
        identity = credit_artifact_id(artifact)
        self.assertEqual(parse_credit_artifact(_json(artifact), expected_id=identity), artifact)
        self.assertEqual(assert_current_credit_artifact(artifact), artifact)

    def test_loaded_borrow_patch_changes_identity_with_unchanged_source(self):
        before, _ = _loaded_modules(("credit",))
        source = sha256(Path(credit.__file__).read_bytes()).hexdigest()
        original = credit.CreditService._borrow
        def replacement(*args, **kwargs):
            return original(*args, **kwargs)
        with patch.object(credit.CreditService, "_borrow", replacement):
            after, _ = _loaded_modules(("credit",))
        self.assertEqual(sha256(Path(credit.__file__).read_bytes()).hexdigest(), source)
        self.assertNotEqual(before["uta.credit.CreditService._borrow"], after["uta.credit.CreditService._borrow"])

    def test_changed_keyword_defaults_are_not_hidden_by_equal_bytecode(self):
        function = credit.CreditService._units
        original_code = function.__code__.co_code
        before, _ = _loaded_modules(("credit",))
        with patch.object(function, "__kwdefaults__", {"positive": False}):
            after, _ = _loaded_modules(("credit",))
        self.assertEqual(function.__code__.co_code, original_code)
        self.assertNotEqual(before["uta.credit.CreditService._units"], after["uta.credit.CreditService._units"])

    def test_equal_wrapper_bytecode_with_changed_closure_is_detected(self):
        def make(amount):
            def replacement(*args, **kwargs):
                return amount
            return replacement
        first, second = make(1), make(2)
        self.assertEqual(first.__code__.co_code, second.__code__.co_code)
        with patch.object(credit.CreditService, "_borrow", first):
            before, _ = _loaded_modules(("credit",))
        with patch.object(credit.CreditService, "_borrow", second):
            after, _ = _loaded_modules(("credit",))
        self.assertNotEqual(before["uta.credit.CreditService._borrow"], after["uta.credit.CreditService._borrow"])

    def test_static_pool_binding_is_fingerprinted(self):
        _, before = _loaded_modules(("credit",))
        with patch.object(credit, "_POOL", "system:different-pool"):
            _, after = _loaded_modules(("credit",))
        self.assertNotEqual(before["uta.credit._POOL"], after["uta.credit._POOL"])

    def test_live_registry_is_not_serialized_as_code_or_nonce_evidence(self):
        before = credit_code_artifact()
        with patch.object(writer_fence, "_REGISTRY", {1: {"nonce": "DO_NOT_ARCHIVE_LIVE_NONCE"}}):
            after = credit_code_artifact()
        self.assertEqual(before, after)
        self.assertNotIn("DO_NOT_ARCHIVE_LIVE_NONCE", _json(after))
        self.assertNotIn("uta.writer_fence._REGISTRY", after["loaded_credit_constants"])

    def test_unsupported_live_closure_fails_without_repr_hook(self):
        class Poison:
            def __repr__(self):
                raise AssertionError("untrusted repr hook executed")
        value = Poison()
        def replacement(*args, **kwargs):
            return value
        with patch.object(credit.CreditService, "_borrow", replacement):
            with self.assertRaises(CreditArtifactError) as rejected:
                credit_code_artifact()
        self.assertEqual(rejected.exception.code, "credit_artifact_unavailable")

    def test_changed_source_or_loaded_digest_cannot_claim_current_replay(self):
        artifact = credit_code_artifact()
        artifact["source_files"]["credit.py"] = "f" * 64
        artifact["source_digest"] = sha256(_json(artifact["source_files"]).encode()).hexdigest()
        with self.assertRaises(CreditArtifactError) as rejected:
            assert_current_credit_artifact(artifact)
        self.assertEqual(rejected.exception.code, "credit_replay_engine_mismatch")

    def test_unknown_archive_data_never_selects_imported_code(self):
        artifact = credit_code_artifact()
        artifact["execute"] = "arbitrary.archived.module"
        actual_import = importlib.import_module
        imported = []
        def observe(name, package=None):
            imported.append(name)
            return actual_import(name, package)
        with patch("uta.credit_artifact.importlib.import_module", side_effect=observe):
            with self.assertRaises(CreditArtifactError):
                assert_current_credit_artifact(artifact)
        self.assertNotIn("arbitrary.archived.module", imported)
        self.assertTrue(all(name.startswith("uta.") for name in imported))

    def test_missing_or_unreadable_native_source_is_unavailable(self):
        original = Path.read_bytes
        def deny(path):
            if path.name == "credit_native.py":
                raise OSError("synthetic unavailable source")
            return original(path)
        with patch.object(Path, "read_bytes", deny):
            with self.assertRaises(CreditArtifactError) as rejected:
                credit_code_artifact()
        self.assertEqual(rejected.exception.code, "credit_artifact_unavailable")

    def test_retained_duplicate_nonstandard_number_and_identity_conflicts_reject(self):
        artifact = credit_code_artifact()
        identity, raw = credit_artifact_id(artifact), _json(artifact)
        for invalid in (raw[:-1] + ',"format":1}', raw.replace('"format":1', '"format":1.0', 1),
                        raw.replace('"format":1', '"format":NaN', 1),
                        raw.replace('"format":1', '"format":' + '9' * 1000, 1),
                        " " + raw):
            with self.subTest(kind=invalid[:15]):
                with self.assertRaises(CreditArtifactError):
                    parse_credit_artifact(invalid, expected_id=identity)
        with self.assertRaises(CreditArtifactError):
            parse_credit_artifact(raw, expected_id="credit-artifact:" + "0" * 64)

    def test_incomplete_or_forged_permission_manifest_is_not_an_artifact(self):
        self.assertRaises(CreditArtifactError, credit_artifact_id,
            {"format": 1, "audit_kind": "CREDIT_BORROWED", "activation_permission": False})
        for key, value in (("activation_permission", True), ("signed", True), ("python_optimize", True)):
            manifest = deepcopy(credit_code_artifact())
            manifest[key] = value
            with self.subTest(key=key):
                self.assertRaises(CreditArtifactError, credit_artifact_id, manifest)
