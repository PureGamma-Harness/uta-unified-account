"""Synthetic, in-memory identity/telemetry contracts; never opens a database."""
import ast
from enum import Enum
from hashlib import sha256
import json
import os
import stat
from pathlib import Path
import sys
from types import MappingProxyType, ModuleType
import unittest
from unittest.mock import patch

from uta import credit, writer_fence
from uta.credit_artifact import (CreditArtifactError, _hash, _loaded_modules,
                                 _static, credit_artifact_id, credit_code_artifact)


# Versioned test inventory: byte expectations come from the current immutable
# deployment, while frozen runs must still supply their exact retained pins.
_SOURCE_INVENTORY_V2 = (
    '__init__.py',
    '__main__.py',
    'acceptance.py',
    'admission.py',
    'api.py',
    'bridge.py',
    'configuration.py',
    'credit.py',
    'credit_artifact.py',
    'credit_audit_v2.py',
    'credit_audit_v2_replay.py',
    'credit_fifo_v2.py',
    'credit_native.py',
    'credit_native_v2.py',
    'credit_policy.py',
    'credit_transition.py',
    'credit_v2_payload_contract.py',
    'cross_decimal_kernel.py',
    'cutover.py',
    'decision_audit.py',
    'durable_batches.py',
    'durable_cli.py',
    'durable_commands.py',
    'durable_gateway.py',
    'durable_liquidation.py',
    'durable_process.py',
    'durable_views.py',
    'examples.py',
    'existing_services.py',
    'failure_diagnostics.py',
    'gateway.py',
    'ledger.py',
    'liquidation.py',
    'market.py',
    'market_cache.py',
    'matching.py',
    'migration.py',
    'models.py',
    'ops.py',
    'portfolio.py',
    'private_stream_codec.py',
    'products.py',
    'reconciliation.py',
    'request_signing.py',
    'reservations.py',
    'reserve_kernel.py',
    'risk.py',
    'scenario_margin.py',
    'server.py',
    'service.py',
    'shadow_adapter.py',
    'shard_admission.py',
    'sharding.py',
    'simulator.py',
    'spot.py',
    'startup.py',
    'storage.py',
    'store.py',
    'supervisor.py',
    'vertical.py',
    'worker.py',
    'writer_fence.py',
)

# Consolidated deployment inventory.  V2 remains an explicit historical list;
# frozen executions retain the test bytes and pins from their original source.
# Never derive this allowlist from the files being checked.
_SOURCE_INVENTORY_V3 = tuple(sorted(_SOURCE_INVENTORY_V2 + (
    'funding_local.py',
    'funding_obligations.py',
    'perpetual_funding.py',
)))


def current_source_snapshot():
    """Independent test read; never call production artifact source helpers."""
    root = Path(writer_fence.__file__).resolve().parent
    names = tuple(sorted(path.relative_to(root).as_posix()
                         for path in root.rglob("*.py")))
    if names != _SOURCE_INVENTORY_V3:
        raise AssertionError("current source inventory differs from test inventory v3")
    hashes, metadata = {}, {}
    fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    for name in names:
        path = root / name
        if path.resolve() != path or not stat.S_ISREG(path.lstat().st_mode):
            raise AssertionError("source must be canonical regular and not a symlink")
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as stream:
            before = os.fstat(stream.fileno())
            raw = stream.read(2 * 1024 * 1024 + 1)
            after = os.fstat(stream.fileno())
        observed = tuple(getattr(before, field) for field in fields)
        if (not stat.S_ISREG(before.st_mode) or len(raw) > 2 * 1024 * 1024
                or observed != tuple(getattr(after, field) for field in fields)):
            raise AssertionError("source changed during bounded test read")
        hashes[name] = sha256(raw).hexdigest()
        metadata[name] = observed
    return hashes, metadata


def collector():
    """Use actual publication predicates, without importing its process runner."""
    source = globals().get("_FROZEN_VALIDATION_SOURCE")
    path = Path(__file__).resolve().parents[1] / "tools/run_validation.py"
    if source is None:
        source = path.read_bytes()
    names = {"_LEASE_CAPTURE_INTS", "_LEASE_CAPTURE_BOOLS", "_LEASE_CAPTURE_ENUMS",
             "_lease_error_fields", "_lease_capture_fields"}
    nodes = []
    for node in ast.parse(source, filename=str(path)).body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            nodes.append(node)
        elif isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id in names for target in node.targets):
            nodes.append(node)
    namespace = {"sys": sys, "json": json, "ModuleType": ModuleType,
                 "MappingProxyType": MappingProxyType}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


class LeaseObservationTagArtifactTests(unittest.TestCase):
    def test_complete_artifact_includes_tag_member_and_loaded_class_code(self):
        retained = globals().get("_RETAINED_UTA_SOURCE_PINS")
        ordinary_snapshot = None
        if retained is None:
            retained, ordinary_snapshot = current_source_snapshot()
        artifact = credit_code_artifact()
        if ordinary_snapshot is not None:
            self.assertEqual((retained, ordinary_snapshot), current_source_snapshot())
        self.assertEqual(len(retained), 65)
        self.assertEqual(tuple(sorted(retained)), _SOURCE_INVENTORY_V3)
        self.assertEqual(artifact["source_files"], retained)
        with self.assertRaises(AssertionError):
            self.assertEqual({**artifact["source_files"], "unreviewed.py": "0" * 64}, retained)
        incomplete = dict(artifact["source_files"])
        incomplete.pop("writer_fence.py")
        with self.assertRaises(AssertionError):
            self.assertEqual(incomplete, retained)
        tag = writer_fence._LEASE_OBSERVATION_TAG
        expected = {"enum": "uta.writer_fence._LeaseObservationTag", "name": "V1",
                    "value": "uta_lease_observation_v1"}
        self.assertEqual(_static(tag), expected)
        self.assertEqual(artifact["loaded_credit_constants"]["uta.writer_fence._LEASE_OBSERVATION_TAG"],
                         _hash(expected))
        self.assertEqual(artifact["loaded_credit_constants"]["uta.writer_fence._LeaseObservationTag.V1"],
                         _hash(expected))
        self.assertIn("uta.writer_fence._LeaseObservationTag.__new__", artifact["loaded_credit_engine"])
        self.assertIn("uta.writer_fence._lease_annotation", artifact["loaded_credit_engine"])
        self.assertEqual(artifact["source_files"]["writer_fence.py"],
                         sha256(Path(writer_fence.__file__).read_bytes()).hexdigest())
        self.assertEqual(artifact["runtime_state_excluded"], ["_ACTIVE", "_ACTIVE_LOCK",
                         "_CONTROL_DDL_OVERRIDE", "_EXISTING_ONLY_OPEN", "_REGISTRY", "_REGISTRY_LOCK"])
        self.assertFalse(artifact["activation_permission"])
        self.assertTrue(credit_artifact_id(artifact).startswith("credit-artifact:"))

    def test_unsupported_objects_and_financial_code_constants_still_reject(self):
        with self.assertRaises(CreditArtifactError):
            _static(object())
        with patch.object(writer_fence, "_LEASE_OBSERVATION_TAG", object()):
            with self.assertRaisesRegex(CreditArtifactError, "unsupported loaded financial constant type"):
                _loaded_modules(("writer_fence",))
        with patch.object(writer_fence, "_UNREVIEWED_DIAGNOSTIC_IDENTITY", object(), create=True):
            with self.assertRaisesRegex(CreditArtifactError, "unsupported loaded financial constant type"):
                _loaded_modules(("writer_fence",))
        original = credit.CreditService._borrow.__code__
        try:
            credit.CreditService._borrow.__code__ = original.replace(co_consts=original.co_consts + (object(),))
            with self.assertRaises(CreditArtifactError) as rejected:
                _loaded_modules(("credit",))
            self.assertEqual(rejected.exception.code, "credit_artifact_unavailable")
        finally:
            credit.CreditService._borrow.__code__ = original

    def test_enum_value_and_same_value_other_type_change_loaded_identity(self):
        key = "uta.writer_fence._LEASE_OBSERVATION_TAG"
        unused, before = _loaded_modules(("writer_fence",))
        tag = writer_fence._LEASE_OBSERVATION_TAG
        with patch.object(tag, "_value_", "uta_lease_observation_v2"):
            unused, changed_value = _loaded_modules(("writer_fence",))
        class OtherTag(Enum):
            V1 = "uta_lease_observation_v1"
        with patch.object(writer_fence, "_LEASE_OBSERVATION_TAG", OtherTag.V1):
            unused, changed_type = _loaded_modules(("writer_fence",))
        self.assertNotEqual(before[key], changed_value[key])
        self.assertNotEqual(before[key], changed_type[key])
        self.assertIs(writer_fence._LEASE_OBSERVATION_TAG, tag)
        self.assertEqual(tag.value, "uta_lease_observation_v1")

    def test_unknown_existing_payload_sources_are_never_upgraded_or_published(self):
        class OtherTag(Enum):
            V1 = "uta_lease_observation_v1"
        class TupleAlias(tuple):
            pass
        tag = writer_fence._LEASE_OBSERVATION_TAG
        fields = MappingProxyType({"version": 1})
        invalid = ((object(), fields), (tag.value, fields), (OtherTag.V1, fields),
                   TupleAlias((tag, fields)), (tag, {"version": 1}), (tag,))
        capture = collector()["_lease_error_fields"]
        for payload in invalid:
            with self.subTest(payload_type=type(payload).__name__):
                error = writer_fence.WriterFenceError("lease_expired", "synthetic original")
                setattr(error, "_uta_lease_observation_v1", payload)
                writer_fence._lease_annotation(error, {"version": 1, "assert_generation": 99})
                self.assertIs(getattr(error, "_uta_lease_observation_v1"), payload)
                self.assertIsNone(capture(error))

    def test_original_error_and_native_typed_observation_filter_are_preserved(self):
        error = writer_fence.WriterFenceError("lease_expired", "synthetic original")
        cause = ValueError("synthetic cause")
        error.__cause__ = cause
        identity, args, code = id(error), error.args, error.code
        writer_fence._lease_annotation(error, {
            "version": 1, "assert_generation": 2, "snapshot_time_known": False,
            "phase": "renew", "owner_nonce": "SYNTHETIC_MUST_NOT_BE_PUBLISHED",
            "renew_observed_ns": True, "renew_expires_ns": -1, "identity_matches": 1,
            "renew_known_commit": False, "last_known_renew_same_token": True,
        })
        expected = {"version": 1, "assert_generation": 2, "snapshot_time_known": False,
                    "phase": "renew", "renew_known_commit": False, "last_known_renew_same_token": True}
        payload = error.__dict__["_uta_lease_observation_v1"]
        self.assertIs(type(payload), tuple)
        self.assertIs(payload[0], writer_fence._LEASE_OBSERVATION_TAG)
        self.assertIs(type(payload[1]), MappingProxyType)
        self.assertEqual(dict(payload[1]), expected)
        self.assertEqual(collector()["_lease_error_fields"](error), expected)
        self.assertEqual((id(error), error.args, error.code), (identity, args, code))
        self.assertIs(error.__cause__, cause)

    def test_publication_filter_keeps_original_rejection_of_aliases_and_unknown_fields(self):
        capture = collector()["_lease_capture_fields"]
        invalid = ({"assert_generation": True}, {"snapshot_time_known": True},
                   {"owner_nonce": "SYNTHETIC_MUST_NOT_BE_PUBLISHED"}, {"renew_expires_ns": -1},
                   {"renew_known_commit": 0}, {"phase": "unreviewed_phase"})
        for extra in invalid:
            with self.subTest(field=next(iter(extra))):
                self.assertEqual(capture({"version": 1, **extra}), {"version": 1})


if __name__ == "__main__":
    unittest.main()
