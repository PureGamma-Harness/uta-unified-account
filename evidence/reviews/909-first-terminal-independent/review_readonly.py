"""Independent metadata/Git review; never imports or executes product code."""
import ast
import datetime
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import time

BASE = "d243f8c5a12b4a0c8c2f593813b621317a774013"
SOURCE = "909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0"
REPO = Path(__file__).resolve().parents[3]
RUN = Path("/workspace/uta-managed-observer-runs/909acec-six-hours-20261117")
PREFIX = "evidence/909-first-terminal-20261118/"
SMALL = {
    "progress": "job/progress.json",
    "producer": "control/producer-result.json",
    "cold": "control/strict-producer-cold-result.json",
    "errors": "control/collection-errors.jsonl",
    "final": "control/final-summary.json",
    "coverage": "control/live-coverage.json",
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(*args):
    return subprocess.check_output(
        ["git", "--no-optional-locks", *args], cwd=REPO,
        stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def exact_json(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("duplicate_key")
            value[key] = item
        return value
    def bad_constant(value):
        raise ValueError("nonfinite_json")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=bad_constant)


def public(relative):
    return git("show", BASE + ":" + PREFIX + relative)


def small_original(relative):
    # Open exactly six fixed metadata files. No glob, directory traversal,
    # observer invocation, SQLite import, raw response, timeline, or clone.
    fd = os.open(RUN / relative, os.O_RDONLY | os.O_NOFOLLOW | os.O_NOATIME)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        assert stat.S_ISREG(before.st_mode) and before.st_size <= 1048576
        raw = stream.read(1048577)
        after = os.fstat(stream.fileno())
    signature = lambda value: (value.st_dev, value.st_ino, value.st_size,
                                value.st_mtime_ns, value.st_ctime_ns)
    assert len(raw) == before.st_size and signature(before) == signature(after)
    return raw, {"relative": relative, "bytes": len(raw), "sha256": sha(raw),
                 "stable_during_read": True, "nofollow_noatime": True}


def main():
    started = time.monotonic_ns()
    report = {
        "schema": "uta.909-first-terminal.independent-metadata.v1",
        "reviewed_commit": BASE, "source_commit": SOURCE,
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "read_only_metadata_review": True,
        "original_large_responses_read": False,
        "timeline_database_clone_key_or_quarantine_read": False,
        "product_observer_sql_audit_replay_restart_signal_executed": False,
        "production_approved": False, "financial_acceptance_granted": False,
    }
    assert git("rev-parse", BASE + "^").decode().strip() == SOURCE
    assert git("rev-parse", BASE + ":uta") == git("rev-parse", SOURCE + ":uta")
    changed = git("diff-tree", "--no-commit-id", "--name-status", "-r", SOURCE, BASE).decode().splitlines()
    assert len(changed) == 9 and all(line.startswith("A\t") for line in changed)
    report["patch"] = {"added_files": 9, "runtime_tree_unchanged": True,
                       "sole_parent_is_frozen_source": True}
    manifest = exact_json(public("manifest.json"))
    hashes = {}
    for name, expected in manifest["public_files"].items():
        raw = public(name)
        assert len(raw) == expected["bytes"] and sha(raw) == expected["sha256"]
        hashes[name] = {"bytes": len(raw), "sha256": sha(raw), "matches_manifest": True}
    report["public_manifest"] = hashes
    observed = exact_json(public("safe-first-observation.json"))
    interpretation = exact_json(public("safe-source-bound-interpretation.json"))
    records, originals = {}, {}
    for label, relative in SMALL.items():
        raw, info = small_original(relative)
        inventory_key = "collection_errors" if label == "errors" else label
        expected = observed["inventory"][inventory_key]
        assert info["bytes"] == expected["bytes"] and info["sha256"] == expected["sha256"]
        info["matches_first_seal"] = True
        originals[label] = info
        records[label] = ([exact_json(row) for row in raw.splitlines() if row]
                          if label == "errors" else exact_json(raw))
    report["six_small_originals"] = originals
    progress, producer = records["progress"], records["producer"]
    assert progress["status"] == producer["response"]["status"] == "paused"
    assert progress["elapsed_seconds"] == producer["response"]["elapsed_seconds"] == 19443.305304647
    assert progress["planned_rounds"] == 5400 and progress["rounds"] == {"DONE": 4357}
    assert progress["final_audit"] is None and producer["exit_code"] == 2
    assert producer["stdout_complete"] is True
    errors = records["errors"]
    assert len(errors) == 1
    event = errors[0]
    assert event["code"] == "observer_output_budget_exceeded"
    assert event["action"] == "RESOURCE_NO_GO_OFFICIAL_DRIVER_DRAIN"
    assert event["signal_sent"] is True and event["financial_corruption_inferred"] is False
    assert event["measurement_scope"] == "control_and_observer_except_validated_private_clones"
    assert event["measured_output_bytes"] == 2157259397 and event["output_budget_bytes"] == 2147483648
    report["terminal"] = {
        "status": "paused", "elapsed_seconds": progress["elapsed_seconds"],
        "done_rounds": 4357, "planned_rounds": 5400,
        "active_seconds_shortfall": str(21600 - progress["elapsed_seconds"]),
        "source_of_stop": event["code"], "action": event["action"],
        "measurement_scope": event["measurement_scope"],
        "measured_output_bytes": event["measured_output_bytes"],
        "output_budget_bytes": event["output_budget_bytes"],
        "excess_bytes": 9775749, "financial_corruption_inferred": False,
    }
    observer_raw = git("show", SOURCE + ":tools/managed_soak_observer.py")
    observer_ast = ast.parse(observer_raw)
    cold = records["cold"]
    assert cold["exit_code"] == 1 and cold["stdout_complete"] is True
    response = cold["response"]
    assert response["error_type"] == "ValueError" and response["final_evidence_eligible"] is False
    literal = "producer_audit_requires_other_final_checks_passed"
    locations = [node.lineno for node in ast.walk(observer_ast)
                 if isinstance(node, ast.Constant) and node.value == literal]
    assert locations == [704] and sha(literal.encode()) == response["error_digest"]
    assert sha(observer_raw) == interpretation["observer_source_sha256"]
    digest_lines = [node.lineno for node in ast.walk(observer_ast)
                    if isinstance(node, ast.Call)
                    and ast.unparse(node) == "sha256(str(error).encode()).hexdigest()"]
    assert sorted(digest_lines) == [878, 894]
    report["cold_error_source_binding"] = {
        "observer_sha256": sha(observer_raw), "error_type": response["error_type"],
        "error_digest": response["error_digest"], "exact_literal": literal,
        "unique_literal_lines": locations, "digest_expression_lines": sorted(digest_lines),
        "method": "static_AST_and_message_hash_only_not_executed_audit",
    }
    supervisor_raw = git("show", SOURCE + ":tools/run_managed_long.py")
    supervisor_ast = ast.parse(supervisor_raw)
    line_cap = next(node for node in supervisor_ast.body if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == "LINE_CAP" for target in node.targets))
    assert ast.unparse(line_cap.value) == "64 * 1024 ** 2"
    final_once = next(node for node in supervisor_ast.body if isinstance(node, ast.FunctionDef) and node.name == "final_once")
    pipes = [node for node in ast.walk(final_once) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name) and node.func.id == "Pipes"]
    assert len(pipes) == 1
    assert any(keyword.arg == "stdout_limit" and isinstance(keyword.value, ast.Name)
               and keyword.value.id == "LINE_CAP" for keyword in pipes[0].keywords)
    final_reports = {}
    for label in ("before", "after"):
        result = observed["results"][label]
        assert result["outer"]["stdout_complete"] is True and result["response_present"] is True
        observation = result["observation"]
        assert observation["observer"]["logical_point"] == "stable_boundary"
        assert observation["observer"]["completed_rounds"] == 4357
        assert observation["observer"]["final_evidence_eligible"] is False
        assert observation["financial_golden"]["compared"] is True and observation["financial_golden"]["passed"] is True
        assert observation["financial_golden"]["completed_rounds"] == 4357
        assert observation["financial_golden_errors"]["known_format_codes"] == []
        assert observation["final_reconciliation"] == {} and observation["log_verification"] == {}
        final_reports[label] = {
            "evidence_source": "first_seal_public_projection_only_original_large_JSON_not_reread",
            "original_bytes": observed["inventory"][label]["bytes"],
            "stdout_complete": True, "response_present": True,
            "stable_prefix_rounds": 4357, "golden_compared_passed": True,
            "final_evidence_eligible": False, "independent_final_reconciliation_proven": False,
        }
    report["final_observation_cap"] = {
        "source_sha256": sha(supervisor_raw), "line_cap_expression": ast.unparse(line_cap.value),
        "final_once_pipes_stdout_limit": "LINE_CAP", "effective_bytes": 67108864,
        "four_mib_truncation_claim_supported": False, "projections": final_reports,
    }
    final, coverage = records["final"], records["coverage"]
    assert final["financial_final_evidence_eligible"] is False
    assert final["overall_engineering_evidence_within_gates"] is False
    assert final["status"] == "COLLECTION_FINISHED" and final["fault_schedule_complete"] is False
    assert coverage["coverage_status"] == "NO_GO" and coverage["samples_observed"] == 321
    assert coverage["financial_golden_counts"] == {"stable_compared_passed": 16, "not_compared_inflight_or_unproven": 305}
    assert observed["inventory"]["cold_receipt"]["state"] == "MISSING"
    report["conclusion"] = {
        "metadata_source_binding_review": "PASS_WITH_EXPLICIT_SCOPE_LIMITS",
        "original_six_hour_run": "NO_GO_NOT_RECLASSIFIED",
        "completed_prefix": "EXISTING_OBSERVER_GOLDEN_ONLY_4357_ROUNDS",
        "final_cold_reopen_full_replay_or_financial_acceptance": "NOT_PROVEN",
        "original_missing_receipt_independently_rechecked": False,
        "cause_of_resource_growth_or_coverage_gaps_established_here": False,
        "production_approved": False,
    }
    report["elapsed_ns"] = time.monotonic_ns() - started
    print(json.dumps(report, sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
