"""One synthetic-only batch: no SQL, application import, process or file store."""
import ast
from copy import deepcopy
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import managed_observer_report as codec
from tools.managed_observer_coverage import Coverage, fatal_financial_codes

REFERENCE = ROOT / "tests/fixtures/managed_observer_coverage_909.py"
spec = importlib.util.spec_from_file_location("frozen_observer_coverage_909", REFERENCE)
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)
PLAN = {"observer": {"blocks": 1, "independent_finance_golden_required_each_1800_second_block": 1,
        "technical_read_unknown_budget": 3, "maximum_consecutive_technical_read_unknown": 2,
        "interval_seconds": 60}, "producer": {"duration_seconds": 1800}}


class MemoryStore:
    def __init__(self):
        self.nodes = {}
        self.new_bytes = 0

    def put(self, identity, raw):
        assert codec.node_hash(raw) == identity
        if identity in self.nodes:
            assert self.nodes[identity] == raw
        else:
            self.nodes[identity] = raw
            self.new_bytes += len(raw)

    def get(self, identity):
        return self.nodes[identity]


def command(sequence, shard=0, **updates):
    value = {"shard": shard, "sequence": sequence, "command_id": f"synthetic:{shard}:{sequence}",
        "state": "SUCCEEDED", "kind": "SUBMIT_ORDER", "control_lane": False,
        "attempts": 0, "last_error_present": False, "last_error_code": None, "quarantined": False}
    value.update(updates)
    return value


def sample(rows):
    return {"format": 1, "synthetic": True, "redacted": True, "logical_point": "stable_boundary",
        "active_rounds": [], "completed_rounds": len(rows), "unresolved_steps": 0,
        "unresolved_faults": 0, "planned_faults": [], "alerts": [], "final_evidence_eligible": False,
        "finance": {"counts": {"uta_command_inbox": len(rows)}, "command_inbox": rows,
            "retry_alerts": [], "golden": {"compared": True, "passed": True, "errors": []},
            "watermark": {"format": 2, "sha256": "0" * 64, "ledger_hash": "0" * 64,
                          "ledger_sequence": len(rows), "business_event_sequence": len(rows)},
            "balances": [], "gross_debt": [], "residuals": {"live_orders": 0, "positions": []}}}


def project(value, coverage=None, store=None, attempt=1):
    coverage = coverage or Coverage(PLAN)
    store = store or MemoryStore()
    result = codec.consume_and_format(value, coverage.observe, job_elapsed_seconds=60 * attempt,
        sample_attempt_id=attempt, report_format="compact-v2", store=store)
    return result, coverage, store


class ObserverCompactReportPureTests(unittest.TestCase):
    def test_frozen_reference_and_full_coverage_body_unchanged(self):
        self.assertEqual(sha256(REFERENCE.read_bytes()).hexdigest(),
                         "15e4f97c1d3541c2ee076e618b19ce5442f42290b3ffefd63e29985942485699")
        original = ast.parse(REFERENCE.read_bytes())
        candidate = ast.parse((ROOT / "tools/managed_observer_coverage.py").read_bytes())
        removed = 0
        for function in [node for node in ast.walk(candidate) if isinstance(node, ast.FunctionDef)
                         and node.name in {"fatal_financial_codes", "observe"}]:
            matches = [node for node in function.body if isinstance(node, ast.If)
                       and ast.unparse(node.test) ==
                       "isinstance(sample, Mapping) and sample.get('report_schema') == 'uta.managed_observer.compact.v2'"]
            self.assertEqual(len(matches), 1)
            function.body.remove(matches[0])
            removed += 1
        self.assertEqual(removed, 2)
        self.assertEqual(ast.dump(candidate, include_attributes=False), ast.dump(original, include_attributes=False))

    def test_manual_three_command_risk_and_canonical_example(self):
        value = sample([command(1), command(2, state="QUARANTINED", attempts=2,
            quarantined=True, last_error_present=True), command(3, state="PENDING",
            control_lane=True, last_error_code="unknown_redacted")])
        original = deepcopy(value)
        expected = legacy.Coverage(PLAN).observe(value, job_elapsed_seconds=60, sample_attempt_id=1)
        compact, _, store = project(value)
        self.assertEqual(value, original)
        summary = compact["summary"]["commands"]
        self.assertEqual((summary["total"], summary["account_commands"], summary["control_commands"]), (3, 2, 1))
        self.assertEqual(summary["state_counts"], {"PENDING": 1, "SUCCEEDED": 1, "REJECTED": 0, "QUARANTINED": 1, "OTHER": 0})
        self.assertEqual(expected["fatal_financial_codes"], ["internal_execution_retry", "terminal_command_failure"])
        self.assertEqual(compact["coverage_observation"], expected)
        self.assertEqual(codec.restore(compact, store), original)
        raw = json.dumps(original, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        self.assertEqual(compact["full_reference"]["sha256"], sha256(raw).hexdigest())
        self.assertEqual(compact["full_reference"]["canonical_bytes"], len(raw))

    def test_full_consumed_before_first_dependency_write(self):
        full = sample([command(1)])
        events = []
        actual = Coverage(PLAN)
        class SpyCoverage:
            def observe(_, report, **kwargs):
                self.assertIs(report, full)
                self.assertEqual(len(report["finance"]["command_inbox"]), 1)
                events.append("complete_coverage")
                return actual.observe(report, **kwargs)
        class SpyStore(MemoryStore):
            def put(_, identity, raw):
                self.assertTrue(events and events[0] == "complete_coverage")
                events.append("dependency_write")
                super().put(identity, raw)
        project(full, SpyCoverage(), SpyStore())

    def test_differential_verdict_counts_and_size_with_growing_histories(self):
        reference, candidate, store = legacy.Coverage(PLAN), Coverage(PLAN), MemoryStore()
        metrics = []
        for attempt, count in enumerate((0, 3, 64, 257, 1024), 1):
            full = sample([command(index) for index in range(count)])
            expected = reference.observe(full, job_elapsed_seconds=60 * attempt, sample_attempt_id=attempt)
            compact, _, _ = project(full, candidate, store, attempt)
            self.assertEqual(compact["coverage_observation"], expected)
            self.assertEqual(codec.restore(compact, store), full)
            self.assertEqual(candidate.report(60 * attempt), reference.report(60 * attempt))
            size = len(codec.canonical(compact))
            self.assertLessEqual(size, codec.MAX_REPORT_BYTES)
            metrics.append({"records": count, "compact_bytes": size,
                            "full_bytes": compact["full_reference"]["canonical_bytes"]})
        print(json.dumps({"synthetic_size_metrics": metrics}, sort_keys=True))

    def test_first_partition_insert_append_and_old_state_update_reuse_subtrees(self):
        rows = [command(index, shard) for shard in (0, 1) for index in range(1, 257)]
        store, coverage, reference = MemoryStore(), Coverage(PLAN), legacy.Coverage(PLAN)
        snapshots = [rows, rows[:256] + [command(257, 0)] + rows[256:]]
        interior = deepcopy(snapshots[-1])
        interior.insert(32, command(1000, 0))
        interior[0]["state"] = "REJECTED"
        snapshots.append(interior)
        old_nodes = set()
        metrics = []
        for attempt, records in enumerate(snapshots, 1):
            full = sample(deepcopy(records))
            expected = reference.observe(full, job_elapsed_seconds=60 * attempt, sample_attempt_id=attempt)
            compact, _, _ = project(full, coverage, store, attempt)
            self.assertEqual(codec.restore(compact, store), full)
            self.assertEqual(compact["coverage_observation"], expected)
            self.assertEqual(coverage.report(60 * attempt), reference.report(60 * attempt))
            added = set(store.nodes) - old_nodes
            if attempt > 1:
                self.assertLessEqual(len(added), 4 * codec.MAX_TREE_DEPTH + 5)
                self.assertLess(len(added), len(records) // 2)
            metrics.append({"records": len(records), "new_distinct_nodes": len(added)})
            old_nodes = set(store.nodes)
        print(json.dumps({"synthetic_partition_edit_metrics": metrics}, sort_keys=True))

    def test_negative_hash_missing_dependency_and_summary_mutation(self):
        compact, _, store = project(sample([command(1)]))
        changed = deepcopy(compact)
        changed["summary"]["commands"]["total"] += 1
        with self.assertRaisesRegex(ValueError, "published_summary_or_receipt_changed"):
            codec.restore(changed, store)
        identity = compact["full_reference"]["root"]
        original = store.nodes.pop(identity)
        with self.assertRaises(KeyError):
            codec.restore(compact, store)
        store.nodes[identity] = original + b" "
        with self.assertRaisesRegex(ValueError, "dependency_hash_or_size_mismatch"):
            codec.restore(compact, store)

    def test_legacy_default_exact_and_compact_rejected_before_counter_mutation(self):
        full, coverage = sample([command(1)]), Coverage(PLAN)
        self.assertIs(codec.consume_and_format(full, coverage.observe, job_elapsed_seconds=60, sample_attempt_id=1), full)
        compact, _, _ = project(full)
        before = deepcopy(coverage.report(60))
        with self.assertRaisesRegex(ValueError, "complete_legacy_report_required"):
            coverage.observe(compact, job_elapsed_seconds=120, sample_attempt_id=2)
        self.assertEqual(coverage.report(60), before)
        with self.assertRaisesRegex(ValueError, "complete_legacy_report_required"):
            fatal_financial_codes(compact)
        # Frozen old consumer also cannot credit the display-only envelope.
        observed = legacy.Coverage(PLAN).observe(compact, job_elapsed_seconds=60, sample_attempt_id=1)
        self.assertIsNone(observed["credited_block"])

    def test_financial_negative_mutations_keep_original_classification(self):
        for mutation in ("retry", "quarantine", "unavailable_check", "inflight", "technical_unknown"):
            with self.subTest(mutation=mutation):
                full = sample([command(1)])
                if mutation == "retry": full["finance"]["command_inbox"][0]["attempts"] = 1
                elif mutation == "quarantine": full["finance"]["command_inbox"][0]["state"] = "QUARANTINED"
                elif mutation == "unavailable_check":
                    full["finance"]["golden"].update(passed=False, errors=["sqlite_quick_check_failed_unavailable"])
                elif mutation == "inflight":
                    full.update(logical_point="inflight_or_unknown", active_rounds=[2])
                    full["finance"]["golden"].update(compared=False, passed=False)
                else:
                    del full["finance"]
                    full.update(logical_point="unknown", alerts=["observation_failed_closed"])
                expected = legacy.Coverage(PLAN).observe(full, job_elapsed_seconds=60, sample_attempt_id=1)
                compact, _, store = project(full)
                self.assertEqual(compact["coverage_observation"], expected)
                self.assertEqual(codec.restore(compact, store), full)


if __name__ == "__main__":
    def deny_native(event, args):
        if event in {"sqlite3.connect", "subprocess.Popen", "os.fork", "os.kill", "os.posix_spawn",
                     "os.link", "os.remove", "os.mkdir", "os.rename", "fcntl.flock"}:
            raise AssertionError("pure batch attempted native effect: " + event)
        if event == "open":
            _, mode, flags = args
            if (mode and any(value in mode for value in "wax+")) or flags & (os.O_WRONLY | os.O_RDWR):
                raise AssertionError("pure batch attempted file mutation")
    sys.addaudithook(deny_native)
    unittest.main()
