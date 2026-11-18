#!/usr/bin/env python3
"""Bounded, offline inspection of explicit source pins; no UTA imports.

This establishes only that selected bytes read from disk match an externally
provided digest and its recognized manifest. It cannot authenticate that digest
or establish what any process has loaded. See docs/deployment/offline-manifest.md.
"""

import argparse
import errno
import hashlib
import hmac
import json
import os
import re
import stat
import sys


MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 16 * 1024 * 1024
MAX_MANIFEST_BYTES = 256 * 1024
MAX_FILES = 128  # Includes the manifest; verification pins are not opened.
MAX_JSON_DEPTH = 12
MAX_JSON_NODES = 4096
MAX_PATH_BYTES = 240
COMBINED_SCHEMA = "funding-hold-v3-combined-source/v1"
FIXTURE_SCHEMA = "offline-deployment-synthetic-source/v1"
_HEX40 = re.compile(r"[0-9a-f]{40}\Z", re.ASCII)
_HEX64 = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_COMPONENT = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*\Z", re.ASCII)

# This version recognizes the frozen V4 inventory, not arbitrary discovered files.
_COMBINED_RUNTIME_PATHS = frozenset(
    "uta/" + name
    for name in (
        "__init__.py", "__main__.py", "acceptance.py", "admission.py", "api.py",
        "bridge.py", "configuration.py", "credit.py", "credit_artifact.py",
        "credit_audit_v2.py", "credit_audit_v2_replay.py", "credit_fifo_v2.py",
        "credit_native.py", "credit_native_v2.py", "credit_policy.py",
        "credit_transition.py", "credit_v2_payload_contract.py",
        "cross_decimal_kernel.py", "cutover.py", "dashboard.html",
        "decision_audit.py", "durable_batches.py", "durable_cli.py",
        "durable_commands.py", "durable_gateway.py", "durable_liquidation.py",
        "durable_process.py", "durable_views.py", "examples.py",
        "existing_services.py", "failure_diagnostics.py", "funding_hold_pure.py",
        "funding_local.py", "funding_obligations.py", "gateway.py", "ledger.py",
        "liquidation.py", "market.py", "market_cache.py", "matching.py",
        "migration.py", "models.py", "ops.py", "perpetual_funding.py",
        "portfolio.py", "private_stream_codec.py", "products.py",
        "reconciliation.py", "request_signing.py", "reservations.py",
        "reserve_kernel.py", "risk.py", "scenario_margin.py", "server.py",
        "service.py", "shadow_adapter.py", "shard_admission.py", "sharding.py",
        "simulator.py", "spot.py", "startup.py", "storage.py", "store.py",
        "supervisor.py", "vertical.py", "worker.py", "writer_fence.py",
    )
)
_CHANGED_PATHS = frozenset(
    ("uta/durable_commands.py", "uta/durable_process.py", "uta/sharding.py")
)
_COMMIT_FIELDS = (
    "code_origin_commit", "base", "market_control_origin", "reference_source",
    "reference_manifest", "reference_review", "target_marshaller_review",
    "driver_review",
)
_TEXT_FIELDS = ("status", "first_CI", "D2", "production")
_INT_FIELDS = (
    "expected_added_test_method_definitions", "expected_tests_if_discovery_unchanged",
    "full_field_cases_defined", "actual_target_reference_generation_import_compile_test_runs",
    "local_financial_SQL_actor_runs",
)
_BOOL_FIELDS = (
    "expected_count_is_execution_evidence", "capacity_claim", "activation_permission",
)
_COMBINED_KEYS = frozenset(
    ("schema", "runtime_files", "runtime_count", "runtime_bytes", "python_count",
     "explicit_inventory", "changed_runtime_files", "unchanged_base_runtime_files",
     "verification_source_pins", "new_test_python_files")
    + _COMMIT_FIELDS + _TEXT_FIELDS + _INT_FIELDS + _BOOL_FIELDS
)
_FIXTURE_KEYS = frozenset(
    ("schema", "purpose", "source_basis", "runtime_files", "runtime_count", "runtime_bytes")
)


class InspectionError(Exception):
    """Contains a fixed public code, never an OS error or caller-supplied text."""


def _require(condition, code):
    if not condition:
        raise InspectionError(code)


def _keys(value, expected):
    _require(type(value) is dict, "SCHEMA_OBJECT_REQUIRED")
    _require(set(value) == expected, "SCHEMA_FIELDS_MISSING_OR_UNKNOWN")


def _integer(value, maximum=MAX_TOTAL_BYTES):
    _require(type(value) is int and 0 <= value <= maximum, "SCHEMA_INTEGER_REQUIRED")


def _text(value):
    _require(
        type(value) is str and 1 <= len(value) <= 120
        and all(32 <= ord(c) <= 126 for c in value),
        "SCHEMA_TEXT_REQUIRED",
    )


def _digest(value, pattern, code):
    _require(type(value) is str and pattern.fullmatch(value) is not None, code)


def _relative_path(value):
    _require(type(value) is str and 1 <= len(value) <= MAX_PATH_BYTES, "INVALID_RELATIVE_PATH")
    pieces = value.split("/")
    _require(
        len(pieces) <= 8 and all(
            piece not in (".", "..") and _COMPONENT.fullmatch(piece) is not None
            for piece in pieces
        ),
        "INVALID_RELATIVE_PATH",
    )
    return value


def _path_list(value):
    _require(type(value) is list and len(value) < MAX_FILES, "SCHEMA_PATH_LIST_REQUIRED")
    paths = [_relative_path(path) for path in value]
    _require(len(set(paths)) == len(paths), "DUPLICATE_PATH")
    return paths


def _pins(value, with_origin):
    _require(type(value) is list and len(value) < MAX_FILES, "SCHEMA_PIN_LIST_REQUIRED")
    expected = {"path", "bytes", "sha256"}
    if with_origin:
        expected.add("origin")
    seen = set()
    for pin in value:
        _keys(pin, expected)
        path = _relative_path(pin["path"])
        _require(path not in seen, "DUPLICATE_PATH")
        seen.add(path)
        _integer(pin["bytes"], MAX_FILE_BYTES)
        _digest(pin["sha256"], _HEX64, "INVALID_PIN_SHA256")
        if with_origin:
            _digest(pin["origin"], _HEX40, "INVALID_ORIGIN_COMMIT")
    return seen


def _unique_pairs(pairs):
    _require(len(pairs) <= 64, "JSON_OBJECT_TOO_LARGE")
    result = {}
    for key, value in pairs:
        _require(len(key) <= 512, "JSON_STRING_TOO_LONG")
        _require(key not in result, "DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _json_integer(token):
    _require(len(token) <= 10, "JSON_INTEGER_TOO_LARGE")
    return int(token)


def _no_float(_token):
    raise InspectionError("JSON_NON_INTEGER_NUMBER")


def _decode_manifest(raw):
    try:
        source = raw.decode("utf-8", errors="strict")
    except UnicodeError:
        raise InspectionError("INVALID_JSON_UTF8") from None
    # Check nesting before json.loads allocates a recursive object graph.
    depth = 0
    quoted = False
    escaped = False
    for character in source:
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
        elif character == '"':
            quoted = True
        elif character in "[{":
            depth += 1
            _require(depth <= MAX_JSON_DEPTH, "JSON_TOO_DEEP")
        elif character in "]}":
            depth -= 1
    try:
        value = json.loads(
            source, object_pairs_hook=_unique_pairs, parse_int=_json_integer,
            parse_float=_no_float, parse_constant=_no_float,
        )
    except (ValueError, RecursionError):
        raise InspectionError("INVALID_JSON") from None
    pending = [value]
    nodes = 0
    while pending:
        item = pending.pop()
        nodes += 1
        _require(nodes <= MAX_JSON_NODES, "JSON_TOO_MANY_NODES")
        if type(item) is dict:
            pending.extend(item.values())
        elif type(item) is list:
            pending.extend(item)
        elif type(item) is str:
            _require(len(item) <= 512, "JSON_STRING_TOO_LONG")
    return value


def _validate_manifest(manifest):
    _require(type(manifest) is dict, "SCHEMA_OBJECT_REQUIRED")
    schema = manifest.get("schema")
    _require(type(schema) is str, "SCHEMA_VERSION_REQUIRED")
    _require(schema in (COMBINED_SCHEMA, FIXTURE_SCHEMA), "UNSUPPORTED_SCHEMA")
    _keys(manifest, _COMBINED_KEYS if schema == COMBINED_SCHEMA else _FIXTURE_KEYS)
    paths = _pins(manifest["runtime_files"], with_origin=True)
    _require(bool(paths), "EMPTY_RUNTIME_INVENTORY")
    _integer(manifest["runtime_count"], MAX_FILES - 1)
    _integer(manifest["runtime_bytes"])
    _require(manifest["runtime_count"] == len(paths), "RUNTIME_COUNT_MISMATCH")
    _require(
        manifest["runtime_bytes"] == sum(pin["bytes"] for pin in manifest["runtime_files"]),
        "RUNTIME_BYTES_MISMATCH",
    )
    if schema == FIXTURE_SCHEMA:
        _require(manifest["purpose"] == "SYNTHETIC_TEST_ONLY", "INVALID_FIXTURE_PURPOSE")
        _digest(manifest["source_basis"], _HEX40, "INVALID_SOURCE_BASIS")
        _require(
            all(pin["origin"] == manifest["source_basis"] for pin in manifest["runtime_files"]),
            "ORIGIN_BASIS_MISMATCH",
        )
        return paths
    _require(paths == _COMBINED_RUNTIME_PATHS and len(paths) == 67, "V4_INVENTORY_MISMATCH")
    for field in _COMMIT_FIELDS:
        _digest(manifest[field], _HEX40, "INVALID_SOURCE_COMMIT")
    for field in _TEXT_FIELDS:
        _text(manifest[field])
    for field in _INT_FIELDS:
        _integer(manifest[field])
    for field in _BOOL_FIELDS:
        _require(type(manifest[field]) is bool, "SCHEMA_BOOLEAN_REQUIRED")
    _integer(manifest["python_count"], MAX_FILES - 1)
    _integer(manifest["unchanged_base_runtime_files"], MAX_FILES - 1)
    _require(manifest["python_count"] == 66, "V4_PYTHON_COUNT_MISMATCH")
    _require(manifest["explicit_inventory"] == "V4 unchanged", "V4_INVENTORY_LABEL_MISMATCH")
    _require(set(_path_list(manifest["changed_runtime_files"])) == _CHANGED_PATHS,
             "CHANGED_RUNTIME_SET_MISMATCH")
    _require(manifest["unchanged_base_runtime_files"] == 64, "BASE_RUNTIME_COUNT_MISMATCH")
    for pin in manifest["runtime_files"]:
        origin = manifest["market_control_origin"] if pin["path"] in _CHANGED_PATHS else manifest["base"]
        _require(pin["origin"] == origin, "ORIGIN_BASIS_MISMATCH")
    verification_paths = _pins(manifest["verification_source_pins"], with_origin=False)
    _require(len(paths) + len(verification_paths) + 1 <= MAX_FILES, "TOO_MANY_EXPLICIT_FILES")
    _require(not paths.intersection(verification_paths), "DUPLICATE_PATH")
    new_tests = _path_list(manifest["new_test_python_files"])
    _require(set(new_tests).issubset(verification_paths), "UNPINNED_NEW_TEST_PATH")
    _require(all(path.startswith("tests/") and path.endswith(".py") for path in verification_paths),
             "INVALID_VERIFICATION_PATH")
    return paths


def _signature(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def _io_error(error):
    if error.errno == errno.ENOENT:
        return InspectionError("MISSING")
    if error.errno in (errno.ELOOP, errno.ENOTDIR):
        return InspectionError("SYMLINK_OR_NOT_DIRECTORY")
    if error.errno in (errno.EACCES, errno.EPERM):
        return InspectionError("ACCESS_DENIED")
    return InspectionError("FILE_IO_REJECTED")


class _Source:
    def __init__(self, source_root):
        for flag in ("O_NOFOLLOW", "O_DIRECTORY", "O_NONBLOCK", "O_CLOEXEC"):
            _require(hasattr(os, flag), "PLATFORM_NOT_SUPPORTED")
        self.directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
        self.ancestors = []
        self.consumed = 0
        self.opened_files = 0
        try:
            absolute = os.path.abspath(source_root)
            components = [part for part in absolute.split("/") if part]
            _require(len(absolute) <= 4096 and len(components) <= 64, "SOURCE_ROOT_TOO_LONG")
            descriptor = os.open("/", self.directory_flags)
            self.ancestors.append((descriptor, _signature(os.fstat(descriptor))))
            for component in components:
                descriptor = os.open(component, self.directory_flags, dir_fd=descriptor)
                self.ancestors.append((descriptor, _signature(os.fstat(descriptor))))
            self.root = descriptor
        except OSError as error:
            self.close()
            raise _io_error(error) from None
        except Exception:
            self.close()
            raise

    def close(self):
        for descriptor, _ in reversed(self.ancestors):
            os.close(descriptor)
        self.ancestors.clear()

    def assert_directories_unchanged(self):
        try:
            _require(all(_signature(os.fstat(fd)) == before for fd, before in self.ancestors),
                     "SOURCE_DIRECTORY_CHANGED_DURING_INSPECTION")
        except OSError as error:
            raise _io_error(error) from None

    def read(self, relative, limit):
        _relative_path(relative)
        _require(self.opened_files < MAX_FILES, "TOO_MANY_EXPLICIT_FILES")
        self.opened_files += 1
        descriptors = []
        try:
            parent = self.root
            for component in relative.split("/")[:-1]:
                parent = os.open(component, self.directory_flags, dir_fd=parent)
                descriptors.append((parent, _signature(os.fstat(parent))))
            leaf = relative.split("/")[-1]
            selected = os.stat(leaf, dir_fd=parent, follow_symlinks=False)
            _require(not stat.S_ISLNK(selected.st_mode), "SYMLINK_OR_NOT_DIRECTORY")
            _require(stat.S_ISREG(selected.st_mode), "NOT_REGULAR_FILE")
            descriptor = os.open(
                leaf,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                dir_fd=parent,
            )
            descriptors.append((descriptor, None))
            before = os.fstat(descriptor)
            _require(stat.S_ISREG(before.st_mode), "NOT_REGULAR_FILE")
            _require(_signature(before) == _signature(selected), "FILE_CHANGED_BEFORE_READ")
            _require(0 <= before.st_size <= limit, "FILE_TOO_LARGE")
            _require(self.consumed + before.st_size <= MAX_TOTAL_BYTES, "TOTAL_READ_BUDGET_EXCEEDED")
            remaining = before.st_size
            chunks = []
            while remaining:
                chunk = os.read(descriptor, min(64 * 1024, remaining))
                _require(bool(chunk), "FILE_CHANGED_DURING_READ")
                self.consumed += len(chunk)
                remaining -= len(chunk)
                chunks.append(chunk)
            _require(_signature(os.fstat(descriptor)) == _signature(before), "FILE_CHANGED_DURING_READ")
            _require(all(_signature(os.fstat(fd)) == previous
                         for fd, previous in descriptors[:-1]), "SOURCE_DIRECTORY_CHANGED_DURING_READ")
            return b"".join(chunks)
        except OSError as error:
            raise _io_error(error) from None
        finally:
            for descriptor, _ in reversed(descriptors):
                os.close(descriptor)


def _result():
    return {
        "result_schema": "offline-deployment-source-inspection/v1",
        "status": "REJECTED",
        "production_approval": "NOT_PRODUCTION_APPROVAL",
        "expected_digest_trust": "NOT_VERIFIED_EXTERNAL_TRUST_REQUIRED",
        "manifest_authentication": "NOT_VERIFIED",
        "unverified": [
            "unlisted_files_and_import_coverage", "verification_source_pin_contents",
            "active_binary_and_loaded_code", "runtime_configuration", "health",
            "financial_authority_and_signatures", "lease_and_fencing",
            "journal_and_replay", "restore_and_RPO", "deployment_and_rollback_readiness",
        ],
        "missing": [], "mismatches": [], "verified_runtime_pins": [],
    }


def inspect(source_root, manifest, expected_manifest_sha256):
    """Read only explicitly selected regular files; return (public result, exit code)."""
    result = _result()
    source = None
    try:
        _digest(expected_manifest_sha256, _HEX64, "EXTERNAL_EXPECTED_SHA256_REQUIRED")
        _relative_path(manifest)
        source = _Source(source_root)
        raw = source.read(manifest, MAX_MANIFEST_BYTES)
        actual = hashlib.sha256(raw).hexdigest()
        result["manifest_sha256"] = actual
        _require(hmac.compare_digest(actual, expected_manifest_sha256), "MANIFEST_DIGEST_MISMATCH")
        result["manifest_digest_comparison"] = "MATCHES_EXTERNALLY_PROVIDED_VALUE"
        metadata = _decode_manifest(raw)
        paths = _validate_manifest(metadata)
        _require(manifest not in paths, "MANIFEST_ALSO_LISTED_AS_RUNTIME")
        result["source_schema"] = metadata["schema"]
        if metadata["schema"] == COMBINED_SCHEMA:
            result["declared_source_basis"] = {field: metadata[field] for field in
                                               ("code_origin_commit", "base", "market_control_origin")}
            result["source_scope"] = "V4_67_EXPLICIT_RUNTIME_PINS"
        else:
            result["declared_source_basis"] = {"synthetic": metadata["source_basis"]}
            result["source_scope"] = "SYNTHETIC_FIXTURE_ONLY"
        for pin in metadata["runtime_files"]:
            try:
                content = source.read(pin["path"], MAX_FILE_BYTES)
            except InspectionError as error:
                group = "missing" if str(error) == "MISSING" else "mismatches"
                result[group].append({"path": pin["path"], "reason": str(error)})
                continue
            digest = hashlib.sha256(content).hexdigest()
            if len(content) != pin["bytes"] or not hmac.compare_digest(digest, pin["sha256"]):
                result["mismatches"].append({
                    "path": pin["path"], "reason": "PIN_BYTES_OR_SHA256_MISMATCH",
                    "expected_bytes": pin["bytes"], "observed_bytes": len(content),
                    "expected_sha256": pin["sha256"], "observed_sha256": digest,
                })
            else:
                result["verified_runtime_pins"].append({
                    "path": pin["path"], "bytes": len(content), "sha256": digest,
                })
        source.assert_directories_unchanged()
        result["counts"] = {
            "declared_runtime_files": metadata["runtime_count"],
            "declared_runtime_bytes": metadata["runtime_bytes"],
            "matched_runtime_files": len(result["verified_runtime_pins"]),
            "missing_runtime_files": len(result["missing"]),
            "mismatched_runtime_files": len(result["mismatches"]),
            "bytes_read_including_manifest": source.consumed,
            "explicit_file_open_attempts": source.opened_files,
        }
        matched = not result["missing"] and not result["mismatches"]
        result["status"] = "STATIC_PIN_MATCH" if matched else "STATIC_PIN_MISMATCH"
        return result, 0 if matched else 1
    except InspectionError as error:
        result["reason"] = str(error)
        return result, 2
    except (OSError, ValueError, TypeError, OverflowError):
        result["reason"] = "INSPECTION_REJECTED"
        return result, 2
    finally:
        if source is not None:
            source.close()


class _Parser(argparse.ArgumentParser):
    def error(self, _message):
        raise InspectionError("INVALID_ARGUMENTS")


def main(argv=None):
    parser = _Parser(prog="inspect_deployment_manifest", description=__doc__)
    parser.add_argument("--source-root", required=True, help="Explicit local source directory")
    parser.add_argument("--manifest", required=True, help="Canonical path relative to source root")
    parser.add_argument("--expected-manifest-sha256", required=True,
                        help="Digest supplied by a separately trusted external source")
    try:
        arguments = parser.parse_args(argv)
        result, code = inspect(arguments.source_root, arguments.manifest,
                               arguments.expected_manifest_sha256)
    except InspectionError:
        result, code = _result(), 2
        result["reason"] = "INVALID_ARGUMENTS"
    print(json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
