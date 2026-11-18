"""Three newly approved synthetic JSON cases; no actual task/data observation.

The author's existing builder supplies a schema-shaped chain. Only mutations,
expected outcomes and per-case byte-pinned bundle construction are independent.
The author's tests and prior 18-case challenge are not executed.
"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import bind_managed_terminal_evidence as binder

spec = importlib.util.spec_from_file_location("author_synthetic_fixture_only",
                                            ROOT / "tests/test_managed_terminal_binding.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
assert os.sched_getaffinity(0) == {4}


def mutate(records, name):
    if name == "same_numeric_birth_with_leading_zero":
        records["cold"]["identity"].update(pid=records["before"]["identity"]["pid"], birth="02")
        assert records["before"]["identity"]["birth"] == "2"
    elif name == "finance_watermark_float_alias":
        expected = records["after"]["response"]["final_reconciliation"]["watermark"]["financial"]
        observed = copy.deepcopy(expected)
        observed["ledger_sequence"] = float(observed["ledger_sequence"])
        records["after"]["response"]["finance"]["watermark"] = observed
        assert type(expected["ledger_sequence"]) is int
        assert type(observed["ledger_sequence"]) is float
    elif name == "same_pid_new_numeric_birth_is_legal":
        records["cold"]["identity"].update(pid=records["before"]["identity"]["pid"], birth="3")
    else:
        raise AssertionError("unregistered synthetic mutation")


def sealed_bundle_result(records):
    with tempfile.TemporaryDirectory(prefix="uta-terminal-synthetic-alias-") as directory:
        root = Path(directory)
        pins = {}
        for label, (relative, _) in binder.FILES.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            raw = json.dumps(records[label], sort_keys=True, allow_nan=False).encode()
            path.write_bytes(raw)
            pins[relative] = hashlib.sha256(raw).hexdigest()
        manifest = {"schema": "uta-terminal-json-pins-v1", "source_commit": binder.SOURCE, "files": pins}
        raw = json.dumps(manifest, sort_keys=True, allow_nan=False).encode()
        manifest_path = root / "synthetic-reviewed-manifest.json"
        manifest_path.write_bytes(raw)
        checksum = hashlib.sha256(raw).hexdigest()
        # Self-generated manifest pins are appropriate only for this synthetic
        # consistency fixture; they establish no authenticity for real records.
        return binder.verify_bundle(root, manifest_path, checksum), checksum, pins


expected = (("same_numeric_birth_with_leading_zero", False),
            ("finance_watermark_float_alias", False),
            ("same_pid_new_numeric_birth_is_legal", True))
cases = []
for name, should_bind in expected:
    records = fixture.synthetic_chain()
    mutate(records, name)
    result, manifest_sha, pins = sealed_bundle_result(records)
    flags = ("candidate_for_independent_terminal_review", "financial_6h_passed",
             "continuous_6h_stability_passed", "continuous_24h_stability_passed",
             "capacity_10000_per_s_passed", "production_approved",
             "full_risk_engine_reexecution_passed", "whole_business_event_reexecution_passed")
    flag_safety = all(result.get(key) is False for key in flags)
    cases.append({"name": name, "expected_metadata_chain_bound": should_bind,
                  "passed": result.get("metadata_chain_bound") is should_bind and flag_safety,
                  "all_candidate_financial_production_flags_false": flag_safety,
                  "synthetic_manifest_sha256": manifest_sha, "synthetic_file_pins": pins,
                  "result": result})
print(json.dumps({"schema": "uta.terminal_binder_alias_additional_challenge.v1",
                  "source_commit": "15b61fd90ee0af6ee28cbba42a79a8484910d2d7",
                  "core_commit": "98e41f50256a6d2d01332c20826dd0033b9efc3a",
                  "cases": cases, "total_cases": len(cases),
                  "passed_cases": sum(case["passed"] for case in cases),
                  "red_cases": sum(not case["passed"] for case in cases),
                  "passed": all(case["passed"] for case in cases),
                  "original18_not_rerun_or_superseded": True,
                  "real_task_sql_observer_audit_signals": "NOT_RUN",
                  "production_approved": False}, sort_keys=True))
raise SystemExit(int(not all(case["passed"] for case in cases)))
