"""Independent small finite-JSON oracle; no candidate decoder/core reuse.

Only memory-store candidate codec calls are permitted. No FS adapter, SQL,
observer, subprocess, network, crypto service, or original run data is used.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "tools/managed_observer_report.py"
PINNED_SOURCE_SHA256 = '9d8a92928ac0aa6dca0c18579f48f499edf05e46cbb230cf6b2dfe6f5a6ae693'
DOMAIN = b"uta-managed-observer-report-node-v2\0"
MARKER = "$managed_observer_array_v2"


def wire(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def load_unique(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError("oracle_duplicate_key")
            out[key] = value
        return out
    def invalid(value):
        raise ValueError("oracle_nonfinite_json")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def identity(raw):
    return hashlib.sha256(DOMAIN + raw).hexdigest()


class Memory:
    def __init__(self):
        self.nodes = {}

    def put(self, key, raw):
        if identity(raw) != key:
            raise ValueError("fixture_bad_identity")
        if key in self.nodes and self.nodes[key] != raw:
            raise ValueError("fixture_overwrite")
        self.nodes[key] = raw

    def get(self, key):
        return self.nodes[key]


def expand_independently(envelope, memory):
    """Protocol interpreter implemented without importing candidate functions."""
    visits = 0

    def node(key):
        nonlocal visits
        visits += 1
        if visits > 200:
            raise ValueError("oracle_small_fixture_budget")
        raw = memory.nodes[key]
        if identity(raw) != key:
            raise ValueError("oracle_hash_mismatch")
        value = load_unique(raw)
        if wire(value) != raw:
            raise ValueError("oracle_noncanonical_node")
        return value

    publication = node(envelope["publication_sha256"])
    presented = {key: value for key, value in envelope.items() if key != "publication_sha256"}
    # Canonical finite JSON bytes retain integer/bool/float distinctions.
    if wire(publication) != wire(presented):
        raise ValueError("oracle_visible_payload_changed")

    def tree(key, depth=1):
        if key is None:
            return []
        if depth > 64:
            raise ValueError("oracle_depth")
        value = node(key)
        if set(value) != {"kind", "version", "anchor", "value", "left", "right", "count"}:
            raise ValueError("oracle_tree_schema")
        if value["kind"] != "array_item" or type(value["version"]) is not int or value["version"] != 2:
            raise ValueError("oracle_tree_version")
        records = tree(value["left"], depth + 1) + [value["value"]] + tree(value["right"], depth + 1)
        if type(value["count"]) is not int or value["count"] != len(records):
            raise ValueError("oracle_tree_count")
        return records

    def decode(value):
        if not isinstance(value, dict):
            return value
        if MARKER in value:
            if set(value) != {MARKER} or set(value[MARKER]) != {"root", "count"}:
                raise ValueError("oracle_reference_schema")
            reference = value[MARKER]
            records = tree(reference["root"])
            if type(reference["count"]) is not int or reference["count"] != len(records):
                raise ValueError("oracle_reference_count")
            return records
        return {key: decode(item) for key, item in value.items()}

    reference = publication["full_reference"]
    root = node(reference["root"])
    if set(root) != {"kind", "version", "value"} or root["kind"] != "full_reference" or root["version"] != 2:
        raise ValueError("oracle_full_reference_schema")
    complete = decode(root["value"])
    raw = wire(complete)
    if type(reference["canonical_bytes"]) is not int or reference["canonical_bytes"] != len(raw):
        raise ValueError("oracle_complete_size")
    if reference["sha256"] != hashlib.sha256(raw).hexdigest():
        raise ValueError("oracle_complete_hash")
    return complete


def manual_report():
    return {
        "synthetic": True, "redacted": True, "logical_point": "stable_boundary",
        "completed_rounds": 2, "active_rounds": [], "unresolved_steps": 0,
        "unresolved_faults": 0, "planned_faults": [], "alerts": [],
        "final_evidence_eligible": False,
        "finance": {
            "command_inbox": [
                {"shard": 0, "sequence": 11, "command_id": "synthetic:A", "state": "SUCCEEDED", "kind": "SUBMIT_ORDER", "control_lane": False},
                {"shard": 0, "sequence": 12, "command_id": "synthetic:B", "state": "QUARANTINED", "kind": "CANCEL_ORDER", "control_lane": False, "attempts": 2, "last_error_present": True},
                {"shard": 1, "sequence": 1, "command_id": "synthetic:C", "state": "PENDING", "kind": "SET_HALT", "control_lane": True},
            ],
            "counts": {"uta_command_inbox": 3}, "watermark": {"sequence": 14},
            "golden": {"compared": True, "passed": True, "errors": []},
            "retry_alerts": [], "arbitrary_original_field": {"complete": ["keep", "all"]},
        },
        "extra_original_field": {"nested": {"number": 0, "truth": False}},
    }


def produced(report=None):
    report = manual_report() if report is None else report
    store = Memory()
    calls = []
    def full_consumer(value, **kwargs):
        rows = value["finance"]["command_inbox"]
        calls.append((len(rows), value is report))
        return {"complete_rows_inspected": len(rows), "manual_fatal": ["internal_execution_retry", "terminal_command_failure"]}
    envelope = candidate.consume_and_format(report, full_consumer, job_elapsed_seconds=60,
        sample_attempt_id=1, report_format="compact-v2", store=store)
    return report, envelope, store, calls


class IndependentSmallJsonTests(unittest.TestCase):
    def test_manual_full_reference_and_extra_fields_expand_without_candidate_decoder(self):
        full, envelope, store, calls = produced()
        self.assertEqual(wire(expand_independently(envelope, store)), wire(full))
        self.assertEqual(calls, [(3, True)])
        self.assertEqual(envelope["summary"]["commands"]["state_counts"],
            {"PENDING": 1, "SUCCEEDED": 1, "REJECTED": 0, "QUARANTINED": 1, "OTHER": 0})
        self.assertEqual(envelope["summary"]["commands"]["account_commands"], 2)
        self.assertEqual(envelope["summary"]["commands"]["control_commands"], 1)

    def check_alias(self, path, replacement):
        _, envelope, store, _ = produced()
        changed = copy.deepcopy(envelope)
        target = changed
        for key in path[:-1]:
            target = target[key]
        original = target[path[-1]]
        target[path[-1]] = replacement
        self.assertEqual(original, replacement)  # Python equality is intentionally insufficient.
        self.assertNotEqual(wire(original), wire(replacement))
        with self.assertRaisesRegex(ValueError, "oracle_visible_payload_changed"):
            expand_independently(changed, store)
        with self.assertRaises(ValueError):
            candidate.restore(changed, store)

    def test_alias_total_integer_three_to_float_is_rejected(self):
        self.check_alias(("summary", "commands", "total"), 3.0)

    def test_alias_control_integer_one_to_true_is_rejected(self):
        self.check_alias(("summary", "commands", "control_commands"), True)

    def test_alias_report_version_two_to_float_is_rejected(self):
        self.check_alias(("report_version",), 2.0)

    def test_alias_synthetic_true_to_integer_one_is_rejected(self):
        self.check_alias(("synthetic",), 1)

    def test_missing_or_corrupt_dependency_never_expands(self):
        _, envelope, store, _ = produced()
        key = envelope["full_reference"]["root"]
        raw = store.nodes.pop(key)
        with self.assertRaises(KeyError):
            expand_independently(envelope, store)
        with self.assertRaises(KeyError):
            candidate.restore(envelope, store)
        store.nodes[key] = raw + b" "
        with self.assertRaisesRegex(ValueError, "oracle_hash_mismatch"):
            expand_independently(envelope, store)
        with self.assertRaises(ValueError):
            candidate.restore(envelope, store)

    def test_new_item_export_limit_does_not_skip_complete_consumer(self):
        report = manual_report()
        report["finance"]["command_inbox"][0]["extra"] = "x" * 2048
        inspected = []
        def consume(full, **kwargs):
            inspected.append((len(full["finance"]["command_inbox"]), "known_fatal_already_observed"))
            return {"fatal": "known_fatal_already_observed"}
        with self.assertRaisesRegex(ValueError, "array_record_budget_exceeded"):
            candidate.consume_and_format(report, consume, job_elapsed_seconds=60,
                sample_attempt_id=1, report_format="compact-v2", store=Memory())
        self.assertEqual(inspected, [(3, "known_fatal_already_observed")])

    def test_oracle_parser_rejects_duplicate_keys_and_nonfinite_json(self):
        for raw in (b'{"same":1,"same":2}', b'{"value":NaN}', b'{"value":Infinity}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                load_unique(raw)


def deny_effects(event, args):
    if event in {"sqlite3.connect", "subprocess.Popen", "os.fork", "os.posix_spawn", "os.kill",
                 "socket.__new__", "socket.connect", "os.mkdir", "os.link", "os.remove", "os.rename"}:
        raise AssertionError("independent pure test attempted native effect")
    if event == "open":
        _, mode, flags = args
        import os
        if (mode and any(value in mode for value in "wax+")) or flags & (os.O_WRONLY | os.O_RDWR):
            raise AssertionError("independent pure test attempted write")


if __name__ == "__main__":
    raw = SOURCE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PINNED_SOURCE_SHA256
    spec = importlib.util.spec_from_file_location("frozen_compact_candidate", SOURCE)
    candidate = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True
    sys.addaudithook(deny_effects)
    spec.loader.exec_module(candidate)
    unittest.main()
