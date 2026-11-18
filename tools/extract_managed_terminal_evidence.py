"""Extract bounded JSON evidence; never import UTA, open SQL, or run an audit.

This deliberately grants no acceptance. Missing, inflight, and failed receipts
remain separate from evidence observed as true. The supervisor owns its original
terminal collection; do not start a second observer with this tool.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import stat
from pathlib import Path

SOURCE = "909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0"
# Presence and local booleans cannot authenticate or bind a terminal chain.
# Keep this list fixed until a separately reviewed binding implementation exists.
UNVERIFIED_TERMINAL_BINDINGS = (
    "producer_and_cold_child_successful_exit_complete_stdout_and_original_identity",
    "original_job_boot_start_deadline_source_and_contract_binding",
    "final_before_after_process_identity_and_collection_order",
    "same_checkpoint_business_and_ledger_watermark_across_cold_reopen",
    "cold_audit_digest_runtime_scope_and_receipt_binding",
    "summary_progress_fault_counts_and_coverage_cross_consistency",
    "raw_event_matching_position_and_per_currency_ledger_reconciliation",
)
FILES = {
    "progress": ("job/progress.json", 131072),
    "final": ("control/final-summary.json", 1048576),
    "producer": ("control/producer-result.json", 131072),
    "cold": ("control/strict-producer-cold-result.json", 131072),
    "coverage": ("control/live-coverage.json", 1048576),
    "failure": ("control/supervisor-failure.json", 131072),
}


def unique_object(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def read_record(path, limit):
    # One bounded read, no retries or symlink traversal. Only JSON metadata is
    # opened; it may change concurrently. This is not a consistent DB snapshot.
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                return None, {"state": "REJECTED_NOT_REGULAR"}
            raw = stream.read(limit + 1)
    except FileNotFoundError:
        return None, {"state": "MISSING"}
    except OSError:
        return None, {"state": "UNREADABLE"}
    digest = hashlib.sha256(raw).hexdigest()
    if len(raw) > limit:
        return None, {"state": "OVERSIZE", "read_prefix_sha256": digest}
    try:
        value = json.loads(raw, object_pairs_hook=unique_object,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
        if not isinstance(value, dict):
            raise ValueError("object required")
    except (UnicodeDecodeError, ValueError):
        return None, {"state": "INVALID_JSON", "sha256": digest, "bytes": len(raw)}
    return value, {"state": "OBSERVED", "sha256": digest, "bytes": len(raw)}


def exact_count(value, expected):
    return type(value) is int and value == expected


def summarize(records, observations):
    p = records.get("progress") or {}
    f = records.get("final") or {}
    c = records.get("coverage") or {}
    elapsed = p.get("elapsed_seconds")
    elapsed_valid = type(elapsed) in (int, float) and math.isfinite(elapsed) and elapsed >= 0
    rounds = p.get("rounds")
    planned = p.get("planned_rounds")
    validation = p.get("validation_evidence")
    source_matches = isinstance(validation, dict) and validation.get("code_commit") == SOURCE
    errors = p.get("error")
    gates = {
        "all_required_metadata_records_observed": all(observations.get(label, {}).get("state") == "OBSERVED"
            for label in FILES if label != "failure"),
        "frozen_source_observed": source_matches,
        "producer_completed_observed": p.get("status") == "completed",
        "producer_actual_21600_seconds_observed": elapsed_valid and elapsed >= 21600,
        "exact_5400_rounds_observed": exact_count(planned, 5400) and isinstance(rounds, dict)
            and set(rounds) == {"DONE"} and exact_count(rounds["DONE"], 5400),
        "no_unresolved_effects_observed": exact_count(p.get("unresolved_steps"), 0)
            and exact_count(p.get("unresolved_faults"), 0),
        "single_controller_observed": exact_count(p.get("controller_sessions"), 1),
        "verified_tls_observed": p.get("verified_tls") is True,
        "producer_logs_verified_observed": p.get("logs_verified") is True,
        "producer_golden_observed": isinstance(p.get("final_audit"), dict)
            and p["final_audit"].get("golden_passed") is True,
        "exact_fault_schedule_observed": p.get("fault_signals") == {"worker": 180, "parent": 18}
            and all(type(v) is int for v in (p.get("fault_signals") or {}).values()),
        "producer_error_absent_observed": "error" in p and errors is None,
        "supervisor_collection_finished_observed": f.get("status") == "COLLECTION_FINISHED",
        "independent_final_eligible_observed": f.get("financial_final_evidence_eligible") is True,
        "supervisor_engineering_gates_observed": f.get("overall_engineering_evidence_within_gates") is True,
        "coverage_complete_observed": c.get("coverage_status") == "COMPLETE_WITHIN_COVERAGE_BUDGET",
        "supervisor_failure_record_absent_observed": observations.get("failure", {}).get("state") == "MISSING",
    }
    completed = rounds.get("DONE") if isinstance(rounds, dict) else None
    if type(completed) is not int or completed < 0:
        completed = None
    return {
        "format": 1, "synthetic": True, "observation_only": True,
        "source_expected": SOURCE,
        "producer_status": p.get("status") if p.get("status") in ("running", "completed", "paused", "failed") else "UNKNOWN",
        "actual_elapsed_seconds_observed": elapsed if elapsed_valid else None,
        "completed_rounds_observed": completed,
        "producer_error_present": errors is not None if "error" in p else None,
        "record_observations": observations,
        "gates_observed": gates,
        # Independent counterexamples showed empty/failed child receipts and
        # contradictory snapshot metadata could pass all local gates. There is
        # deliberately no code path which grants candidate status. A future
        # terminal-chain binder needs its own schema-bound review and evidence.
        "local_metadata_predicates_observed": all(gates.values()),
        "terminal_binding_status": "NOT_IMPLEMENTED_FAIL_CLOSED",
        "terminal_bindings_unverified": list(UNVERIFIED_TERMINAL_BINDINGS),
        "candidate_for_independent_terminal_review": False,
        "financial_6h_passed": False,
        "continuous_6h_stability_passed": False,
        "continuous_24h_stability_passed": False,
        "full_risk_engine_reexecution_passed": False,
        "whole_business_event_reexecution_passed": False,
        "capacity_10000_per_s_passed": False,
        "production_approved": False,
        "scope": "local low-rate synthetic evidence; root and independent review required",
        "not_performed": ["SQL reads", "new observer", "new cold audit", "full risk reexecution", "full business event reexecution"],
    }


def extract(root):
    records, observations = {}, {}
    for label, (relative, limit) in FILES.items():
        records[label], observations[label] = read_record(root / relative, limit)
    return summarize(records, observations)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(extract(args.run_root), sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
