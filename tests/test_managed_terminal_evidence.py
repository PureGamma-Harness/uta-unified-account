import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


spec = importlib.util.spec_from_file_location("terminal_extract", Path(__file__).parents[1] / "tools/extract_managed_terminal_evidence.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def records():
    return {
        "progress": {"status": "completed", "elapsed_seconds": 21600.0,
                     "planned_rounds": 5400, "rounds": {"DONE": 5400},
                     "unresolved_steps": 0, "unresolved_faults": 0,
                     "controller_sessions": 1, "verified_tls": True,
                     "logs_verified": True, "error": None,
                     "final_audit": {"golden_passed": True},
                     "fault_signals": {"worker": 180, "parent": 18},
                     "validation_evidence": {"code_commit": module.SOURCE}},
        "final": {"status": "COLLECTION_FINISHED", "financial_final_evidence_eligible": True,
                  "overall_engineering_evidence_within_gates": True},
        "coverage": {"coverage_status": "COMPLETE_WITHIN_COVERAGE_BUDGET"},
    }


def observations():
    return {name: {"state": "MISSING" if name == "failure" else "OBSERVED"} for name in module.FILES}


class ExtractionTests(unittest.TestCase):
    def test_complete_metadata_only_requests_review_never_grants_pass(self):
        result = module.summarize(records(), observations())
        self.assertTrue(result["candidate_for_independent_terminal_review"])
        for name in ("financial_6h_passed", "continuous_6h_stability_passed",
                     "continuous_24h_stability_passed", "full_risk_engine_reexecution_passed",
                     "whole_business_event_reexecution_passed", "capacity_10000_per_s_passed", "production_approved"):
            self.assertIs(result[name], False)

    def test_each_required_observation_blocks_when_missing(self):
        baseline = records()
        for record, fields in (("progress", list(baseline["progress"])),
                               ("final", list(baseline["final"])),
                               ("coverage", list(baseline["coverage"]))):
            for field in fields:
                with self.subTest(record=record, field=field):
                    value = copy.deepcopy(baseline)
                    del value[record][field]
                    self.assertFalse(module.summarize(value, observations())["candidate_for_independent_terminal_review"])

    def test_no_clock_epsilon_or_observer_wait_credit(self):
        for elapsed in (21599.999999, -1, True, float("nan"), float("inf")):
            value = records()
            value["progress"]["elapsed_seconds"] = elapsed
            self.assertFalse(module.summarize(value, observations())["candidate_for_independent_terminal_review"])

    def test_wrong_source_resume_or_boolean_counts_never_qualify(self):
        for field, value in (("controller_sessions", 2), ("unresolved_steps", False),
                             ("planned_rounds", True), ("rounds", {"DONE": 5400, "INFLIGHT": 0}),
                             ("fault_signals", {"worker": 179, "parent": 18}),
                             ("validation_evidence", {"code_commit": "old-source"})):
            data = records()
            data["progress"][field] = value
            self.assertFalse(module.summarize(data, observations())["candidate_for_independent_terminal_review"])

    def test_each_missing_required_record_blocks_review_candidate(self):
        for label in module.FILES:
            if label == "failure":
                continue
            seen = observations()
            seen[label] = {"state": "MISSING"}
            self.assertFalse(module.summarize(records(), seen)["candidate_for_independent_terminal_review"])

    def test_supervisor_failure_unreadable_is_not_absent(self):
        for state in ("OBSERVED", "UNREADABLE", "INVALID_JSON", "OVERSIZE"):
            self.assertFalse(module.summarize(records(), {"failure": {"state": state}})["candidate_for_independent_terminal_review"])

    def test_output_does_not_echo_unknown_fields_or_error_text(self):
        value = records()
        sentinel = "PRIVATE-NONCE-AND-PATH-SENTINEL"
        value["progress"]["secret"] = sentinel
        value["progress"]["error"] = sentinel
        self.assertNotIn(sentinel, json.dumps(module.summarize(value, {})))

    def test_missing_tree_is_unknown_not_pass(self):
        with tempfile.TemporaryDirectory() as name:
            value = module.extract(Path(name))
        self.assertEqual(value["producer_status"], "UNKNOWN")
        self.assertFalse(value["candidate_for_independent_terminal_review"])

    def test_bounded_reader_rejects_duplicate_keys_nonfinite_and_nonobject(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "record.json"
            for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'[]', b'\xff'):
                path.write_bytes(raw)
                value, report = module.read_record(path, 128)
                self.assertIsNone(value)
                self.assertEqual(report["state"], "INVALID_JSON")
            path.write_bytes(b" " * 129)
            self.assertEqual(module.read_record(path, 128)[1]["state"], "OVERSIZE")

    def test_reader_rejects_symlink_and_directory(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            path = root / "record.json"
            path.symlink_to(root / "missing")
            self.assertIsNone(module.read_record(path, 128)[0])
            self.assertIsNone(module.read_record(root, 128)[0])


if __name__ == "__main__":
    unittest.main()
