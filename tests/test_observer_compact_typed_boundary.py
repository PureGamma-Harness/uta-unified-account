"""New focused typed-boundary batch; never run the old author/independent suite."""
from copy import deepcopy
from pathlib import Path
import os
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import managed_observer_report as codec
from tools.managed_observer_coverage import Coverage

PLAN = {"observer": {"blocks": 1, "independent_finance_golden_required_each_1800_second_block": 1,
    "technical_read_unknown_budget": 3, "maximum_consecutive_technical_read_unknown": 2,
    "interval_seconds": 60}, "producer": {"duration_seconds": 1800}}


class Store:
    def __init__(self, budget=10**6):
        self.nodes, self.budget, self.used = {}, budget, 0
    def put(self, identity, raw):
        if identity in self.nodes:
            assert self.nodes[identity] == raw
            return
        if self.used + len(raw) > self.budget:
            raise ValueError("synthetic_writer_quota_exceeded")
        self.nodes[identity] = raw
        self.used += len(raw)
    def get(self, identity):
        return self.nodes[identity]


def full():
    rows = [{"sequence": index, "command_id": "synthetic:" + str(index),
        "state": "SUCCEEDED", "kind": "SUBMIT_ORDER", "control_lane": index == 3,
        "attempts": 0, "last_error_present": False, "last_error_code": None}
        for index in (1, 2, 3)]
    return {"format": 1, "synthetic": True, "logical_point": "stable_boundary",
        "active_rounds": [], "completed_rounds": 1, "unresolved_steps": 0, "unresolved_faults": 0,
        "planned_faults": [], "alerts": [], "finance": {"command_inbox": rows,
            "counts": {"uta_command_inbox": 3}, "retry_alerts": [],
            "watermark": {"format": 2, "sha256": "0" * 64},
            "golden": {"compared": True, "passed": True, "errors": []}}}


def build(value=None, store=None, consume=None):
    value, store = full() if value is None else value, Store() if store is None else store
    coverage = Coverage(PLAN)
    result = codec.consume_and_format(value, consume or coverage.observe,
        job_elapsed_seconds=60, sample_attempt_id=1, report_format="compact-v2", store=store)
    return result, store


class ObserverCompactTypedBoundaryTests(unittest.TestCase):
    def reject_alias(self, mutate):
        compact, store = build()
        mutate(compact)
        with self.assertRaises(ValueError):
            codec.restore(compact, store)

    def test_control_count_integer_to_boolean_is_rejected(self):
        self.reject_alias(lambda value: value["summary"]["commands"].update(control_commands=True))

    def test_protocol_integer_version_to_float_is_rejected(self):
        self.reject_alias(lambda value: value.update(report_version=2.0))

    def test_synthetic_boolean_to_integer_is_rejected(self):
        self.reject_alias(lambda value: value.update(synthetic=1))

    def test_total_integer_to_equal_float_is_rejected(self):
        self.reject_alias(lambda value: value["summary"]["commands"].update(total=3.0))

    def test_legal_typed_roundtrip_preserves_complete_canonical_bytes(self):
        original = full()
        original["typed_example"] = {"int": 1, "float": 1.0, "bool": True, "none": None}
        before = codec.canonical(original)
        compact, store = build(original)
        restored = codec.restore(compact, store)
        self.assertEqual(codec.canonical(restored), before)
        self.assertIs(type(restored["typed_example"]["int"]), int)
        self.assertIs(type(restored["typed_example"]["float"]), float)
        self.assertIs(type(restored["typed_example"]["bool"]), bool)
        self.assertEqual(codec.canonical(original), before)

    def test_duplicate_nonfinite_and_non_JSON_values_are_rejected(self):
        for raw in (b'{"a":1,"a":1}', b'{"a":NaN}', b'{"a":Infinity}'):
            with self.subTest(raw_type="invalid_JSON"):
                with self.assertRaises(ValueError): codec.strict_json(raw)
        for value in (float("nan"), float("inf"), (1, 2), {1: "not_a_JSON_key"}):
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(ValueError): codec.canonical(value)

    def test_full_input_export_domain_rejection_keeps_prior_classification(self):
        value, observed = full(), []
        value["finance"]["command_inbox"][0]["extra"] = "x" * (codec.MAX_ITEM_BYTES + 1)
        coverage = Coverage(PLAN)
        def consume(report, **timing):
            result = coverage.observe(report, **timing)
            observed.append(deepcopy(result))
            return result
        with self.assertRaisesRegex(ValueError, "array_record_budget_exceeded"):
            build(value, consume=consume)
        self.assertEqual(len(observed), 1)
        self.assertEqual(coverage.report(60)["samples_observed"], 1)

    def test_writer_quota_failure_does_not_erase_known_fatal_or_retry_consumer(self):
        value, events = full(), []
        value["finance"]["command_inbox"][0]["state"] = "QUARANTINED"
        coverage = Coverage(PLAN)
        def consume(report, **timing):
            result = coverage.observe(report, **timing)
            self.assertIn("terminal_command_failure", result["fatal_financial_codes"])
            events.append("known_fatal_safety_action_before_output")
            return result
        with self.assertRaisesRegex(ValueError, "synthetic_writer_quota_exceeded"):
            build(value, Store(budget=0), consume)
        self.assertEqual(events, ["known_fatal_safety_action_before_output"])
        self.assertEqual(coverage.report(60)["samples_observed"], 1)


if __name__ == "__main__":
    def deny_native(event, args):
        if event in {"sqlite3.connect", "subprocess.Popen", "os.fork", "os.kill", "os.posix_spawn",
                     "os.link", "os.remove", "os.mkdir", "os.rename", "fcntl.flock"}:
            raise AssertionError("focused pure attempted native effect: " + event)
        if event == "open":
            _, mode, flags = args
            if (mode and any(char in mode for char in "wax+")) or flags & (os.O_WRONLY | os.O_RDWR):
                raise AssertionError("focused pure attempted file mutation")
    sys.addaudithook(deny_native)
    unittest.main()
