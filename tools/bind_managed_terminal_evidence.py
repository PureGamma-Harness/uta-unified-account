"""Bind sealed terminal JSON metadata. No SQL, process access or audit execution.

An externally reviewed manifest digest is mandatory. This candidate is not
authorized for the live run until independent review and a separate root GO.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

from extract_managed_terminal_evidence import SOURCE, read_record

REVIEW_AUTHORIZED = False
MAX_INTEGER = (1 << 63) - 1
MAX_SECONDS = 86400
BOOT = "6339d4fc-a9e7-4c10-a591-1e70a14322ff"
START = 80871129103044
DEADLINE = 102471129103044
DRIVER = (310039, "8086955")
SCOPE = "private_complete_sqlite_clone_of_stopped_authority"
FILES = {
    "job": ("job/job.json", 1048576),
    "progress": ("job/progress.json", 131072),
    "baseline": ("observer/baseline.json", 1048576),
    "launch": ("control/launch.json", 131072),
    "producer": ("control/producer-result.json", 131072),
    "before": ("control/final-before-cold.json", 64 * 1024**2),
    "cold": ("control/strict-producer-cold-result.json", 1048576),
    "receipt": ("observer/producer-cold-audit-receipt.json", 1048576),
    "after": ("control/final-after-cold.json", 64 * 1024**2),
    "final": ("control/final-summary.json", 1048576),
    "coverage": ("control/live-coverage.json", 1048576),
}
FAULTS = {"worker": 180, "parent": 18}
COUNTS = {"uta_orders": 21600, "uta_fills": 21600, "uta_matches": 10800,
          "uta_risk_decisions": 43200, "ledger_events": 27006,
          "partial_cancelled_orders": 5400, "terminal_account_commands": 32400}
OBSERVER_CODE = {"managed_soak_observer.py": "6d2aa9bdaafc905dbdd192f024fc0d25d3b814ceddd2a165c65585d19a2fc7e1",
                 "managed_observer_finance.py": "bf9138431c1d691b5a423a22ecd43683dfcf258402813c264cf31de612295dd7"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def hex64(value):
    return isinstance(value, str) and re.fullmatch("[0-9a-f]{64}", value) is not None


def integer(value, minimum=0, maximum=MAX_INTEGER):
    return type(value) is int and minimum <= value <= maximum


def number(value, minimum=0, maximum=MAX_SECONDS):
    # Comparing an int to the bound happens before any float operation. An
    # arbitrarily large JSON int must never reach math.isfinite's int cast.
    if type(value) is int:
        return minimum <= value <= maximum
    return type(value) is float and minimum <= value <= maximum and math.isfinite(value)


def exact_integer(value, expected):
    return integer(value) and value == expected


def count_map(value, expected):
    return (isinstance(value, dict) and set(value) == set(expected)
            and all(exact_integer(value[k], expected[k]) for k in expected))


def birth_token(value):
    return (isinstance(value, str) and 1 <= len(value) <= 19 and value.isascii()
            and value.isdecimal() and 0 < int(value) <= MAX_INTEGER
            and value == str(int(value)))


def strict_equal(left, right):
    """JSON structure/value equality with exact types at every depth.

    Python's ordinary container equality admits int/float and bool/int aliases.
    Do not use it to bind two independently observed financial projections.
    """
    pending = [(left, right)]
    while pending:
        first, second = pending.pop()
        if type(first) is not type(second):
            return False
        if isinstance(first, dict):
            if set(first) != set(second):
                return False
            pending.extend((first[k], second[k]) for k in first)
        elif isinstance(first, list):
            if len(first) != len(second):
                return False
            pending.extend(zip(first, second))
        elif type(first) not in (str, int, float, bool, type(None)) or first != second:
            return False
    return True


def financial_watermark_valid(value):
    return (isinstance(value, dict)
            and set(value) == {"format", "sha256", "ledger_sequence", "ledger_hash", "business_event_sequence"}
            and exact_integer(value.get("format"), 2)
            and hex64(value.get("sha256")) and hex64(value.get("ledger_hash"))
            and integer(value.get("ledger_sequence"), 1)
            and integer(value.get("business_event_sequence"), 1))


def watermark_valid(value, contract):
    checkpoint = object_at(value, "checkpoint")
    return (isinstance(value, dict) and set(value) == {"checkpoint", "financial", "contract_sha256"}
            and value.get("contract_sha256") == contract
            and set(checkpoint) == {"sequence", "hash"} and integer(checkpoint.get("sequence"), 1)
            and hex64(checkpoint.get("hash")) and financial_watermark_valid(value.get("financial")))


def numeric_tree_bounded(value):
    """Reject out-of-range metadata numbers before hashing or float operations.

    The range is an evidence contract, not a change to trading arithmetic.
    Booleans remain legal JSON flags; count/clock paths validate exact int types.
    """
    pending = [value]
    while pending:
        item = pending.pop()
        if type(item) is int and not -MAX_INTEGER <= item <= MAX_INTEGER:
            return False
        if type(item) is float and (not -MAX_INTEGER <= item <= MAX_INTEGER or not math.isfinite(item)):
            return False
        if isinstance(item, dict):
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    return True


def coverage_counts_valid(value):
    """The actual Coverage.report schema, with the registered 12-block budget."""
    counters = ("counts", "logical_point_counts", "financial_golden_counts", "technical_error_types",
                "technical_error_digests", "alert_counts", "fatal_financial_code_counts")
    if not all(isinstance(value.get(k), dict) and all(integer(v) for v in value[k].values()) for k in counters):
        return False
    if not (value.get("measurement_status") == "OBSERVED" and integer(value.get("samples_observed"), 1)
            and integer(value.get("last_sample_attempt_id"), 1)
            and number(value.get("actual_completed_active_seconds")) and value["actual_completed_active_seconds"] >= 21600
            and exact_integer(value.get("preregistered_duration_seconds"), 21600)
            and exact_integer(value.get("preregistered_interval_seconds"), 61)
            and exact_integer(value.get("technical_read_unknown_budget"), 3)
            and integer(value.get("consecutive_technical_read_unknown"), 0, 1)
            and integer(value.get("maximum_observed_consecutive_technical_read_unknown"), 0, 1)
            and exact_integer(value.get("maximum_allowed_consecutive_technical_read_unknown"), 1)
            and integer(value["counts"].get("technical_read_unknown_samples"), 0, 3)):
        return False
    blocks = value.get("blocks")
    return (isinstance(blocks, list) and len(blocks) == 12
            and all(isinstance(block, dict) and exact_integer(block.get("index"), i)
                    and exact_integer(block.get("start_active_seconds"), i * 1800)
                    and exact_integer(block.get("end_active_seconds"), (i + 1) * 1800)
                    and exact_integer(block.get("required_stable_golden_samples"), 1)
                    and integer(block.get("stable_golden_samples"), 1) and block.get("state") == "SATISFIED"
                    for i, block in enumerate(blocks)))


def object_at(value, key):
    child = value.get(key) if isinstance(value, dict) else None
    return child if isinstance(child, dict) else {}


def successful_child(value):
    identity = object_at(value, "identity")
    return (type(value.get("exit_code")) is int and value["exit_code"] == 0
            and value.get("stdout_complete") is True and hex64(value.get("stdout_sha256"))
            and hex64(value.get("stderr_sha256")) and type(value.get("stderr_present")) is bool
            and integer(identity.get("pid"), 1, (1 << 31) - 1) and birth_token(identity.get("birth"))
            and integer(identity.get("started_wall_ns"), 1)
            and integer(identity.get("started_boottime_ns"), 1)
            and integer(value.get("ended_wall_ns"), identity["started_wall_ns"])
            and isinstance(value.get("response"), dict))


def stopped(value):
    if (not isinstance(value, dict) or not integer(value.get("pid"), 1, (1 << 31) - 1)
            or value.get("alive") is not False or value.get("known_stopped") is not True):
        return False
    if value.get("visibility") == "absent":
        return value.get("state") == "missing" and value.get("birth") is None
    return (value.get("visibility") == "observed" and birth_token(value.get("birth"))
            and (value.get("state") in ("Z", "X", "x")
            or value.get("identity_matches") is False))


def fault_schedule(value):
    if not isinstance(value, list) or len(value) != 198:
        return False
    expected = {(kind, r) for kind, step in (("worker", 30), ("parent", 300)) for r in range(step, 5401, step)}
    found = []
    for item in value:
        if not isinstance(item, dict):
            return False
        if (item.get("state") != "DONE" or item.get("signal_sent") is not True
                or item.get("kind") not in ("worker", "parent")
                or not integer(item.get("round"), 1) or not integer(item.get("old_generation"), 1)
                or not integer(item.get("new_generation"), item["old_generation"] + 1)):
            return False
        found.append((item.get("kind"), item["round"]))
    return len(set(found)) == len(found) and set(found) == expected


def bind_records(records, *, all_file_pins_verified=False):
    if not isinstance(records, dict) or not numeric_tree_bounded(records):
        return binding_result(["metadata_numeric_range_or_root_type_invalid"])
    errors = []
    def check(condition, code):
        if not condition:
            errors.append(code)
    def get(label):
        value = records.get(label)
        check(isinstance(value, dict), "missing_or_invalid_" + label)
        return value if isinstance(value, dict) else {}
    job, p, baseline, launch = (get(x) for x in ("job", "progress", "baseline", "launch"))
    producer, before, cold, receipt, after = (get(x) for x in ("producer", "before", "cold", "receipt", "after"))
    final, coverage = get("final"), get("coverage")
    check(all_file_pins_verified is True, "externally_pinned_complete_bundle_required")
    check(records.get("supervisor_failure_absent") is True, "supervisor_failure_absence_unproven")
    env, config = object_at(job, "environment"), object_at(job, "configuration")
    check(env.get("commit") == SOURCE and env.get("synthetic") is True, "job_source_or_synthetic_mismatch")
    check(number(config.get("duration")) and config["duration"] == 21600
          and number(config.get("rate")) and config["rate"] == .25
          and exact_integer(job.get("planned_rounds"), 5400),
          "original_workload_not_21600_5400")
    check(strict_equal(job.get("accounts"), ["managed-soak-alice", "managed-soak-bob", "managed-soak-credit"])
          and object_at(job, "bootstrap").get("synthetic_only") is True
          and exact_integer(object_at(job, "bootstrap").get("initial_principal_satoshi"), 10800),
          "original_synthetic_bootstrap_mismatch")
    check(baseline.get("frozen_commit") == SOURCE and baseline.get("boot_id") == BOOT
          and exact_integer(baseline.get("started_boottime_ns"), START)
          and exact_integer(baseline.get("deadline_boottime_ns"), DEADLINE)
          and number(baseline.get("duration_seconds")) and baseline["duration_seconds"] == 21600
          and exact_integer(baseline.get("planned_rounds"), 5400)
          and exact_integer(baseline.get("driver_pid"), DRIVER[0]) and baseline.get("driver_birth") == DRIVER[1],
          "original_contract_identity_or_clock_mismatch")
    check(baseline.get("job_manifest_sha256") == digest(job)
          and baseline.get("job_id_sha256") == digest(job.get("job_id"))
          and strict_equal(baseline.get("source_sha256"), env.get("source_sha256"))
          and baseline.get("workload_spec_sha256") == env.get("workload_spec_sha256")
          and baseline.get("file_identities_sha256") == digest(job.get("file_identities")),
          "baseline_job_binding_mismatch")
    identities = object_at(job, "file_identities")
    check(bool(identities) and all(isinstance(pair, list) and len(pair) == 2
          and integer(pair[0]) and integer(pair[1], 1) for pair in identities.values()),
          "original_file_identity_numeric_contract_invalid")
    check(strict_equal(baseline.get("observer_code_sha256"), OBSERVER_CODE)
          and isinstance(env.get("source_sha256"), dict) and bool(env["source_sha256"])
          and all(isinstance(k, str) and hex64(v) for k,v in env["source_sha256"].items())
          and hex64(env.get("workload_spec_sha256"))
          and isinstance(env.get("python"), str) and isinstance(env.get("sqlite"), str),
          "frozen_model_source_or_runtime_binding_incomplete")
    qualification = object_at(job, "validation_evidence")
    check(qualification.get("code_commit") == SOURCE and qualification.get("engineering_test_qualified") is True
          and qualification.get("production_approved") is False
          and qualification.get("python") == env.get("python") and qualification.get("sqlite") == env.get("sqlite")
          and integer(qualification.get("tests_run"), 1)
          and set(object_at(qualification, "artifact_sha256")) == {"summary.json", "worker-result.json", "unittest.txt"}
          and all(hex64(v) for v in object_at(qualification, "artifact_sha256").values()),
          "original_engineering_qualification_binding_incomplete")
    contract = digest(baseline)
    check(exact_integer(launch.get("driver_pid"), DRIVER[0]) and launch.get("driver_birth") == DRIVER[1]
          and integer(launch.get("launched_wall_ns"), 1) and integer(launch.get("launched_boottime_ns"), 1),
          "launch_driver_identity_mismatch")
    check(p.get("status") == "completed" and number(p.get("elapsed_seconds")) and p["elapsed_seconds"] >= 21600
          and count_map(p.get("rounds"), {"DONE": 5400})
          and exact_integer(p.get("planned_rounds"), 5400), "producer_not_complete_original_duration_and_rounds")
    check(exact_integer(p.get("controller_sessions"), 1)
          and exact_integer(p.get("unresolved_steps"), 0) and exact_integer(p.get("unresolved_faults"), 0)
          and "error" in p and p["error"] is None and p.get("verified_tls") is True
          and p.get("logs_verified") is True and object_at(p, "final_audit").get("golden_passed") is True,
          "producer_session_transport_or_reconciliation_incomplete")
    check(count_map(p.get("fault_signals"), FAULTS),
          "producer_fault_count_mismatch")
    for label, child in (("producer", producer), ("before", before), ("cold", cold), ("after", after)):
        check(successful_child(child), label + "_child_receipt_unsuccessful_or_incomplete")
    pairs = [(object_at(child, "identity").get("pid"), object_at(child, "identity").get("birth"))
             for child in (producer, before, cold, after)]
    # PID reuse with a different birth is valid; an identical lifetime cannot
    # be both the original producer and a newly spawned final/audit child.
    check(all(integer(pid, 1, (1 << 31) - 1) and birth_token(birth) for pid, birth in pairs)
          and all(pairs[i] != pairs[j] for i in range(4) for j in range(i+1, 4)),
          "terminal_child_lifetime_identity_reused_or_invalid")
    identity = object_at(producer, "identity")
    check(exact_integer(identity.get("pid"), DRIVER[0]) and identity.get("birth") == DRIVER[1]
          and strict_equal(identity.get("started_wall_ns"), launch.get("launched_wall_ns"))
          and strict_equal(identity.get("started_boottime_ns"), launch.get("launched_boottime_ns")),
          "producer_launch_receipt_identity_mismatch")
    fields = ("status", "planned_rounds", "rounds", "unresolved_steps", "unresolved_faults", "elapsed_seconds",
              "fault_signals", "logs_verified", "final_audit", "verified_tls", "controller_sessions")
    check(all(k in p and strict_equal(object_at(producer, "response").get(k), p[k]) for k in fields),
          "producer_response_progress_mismatch")
    envelopes = (producer, before, cold, after)
    check(all(integer(v.get("ended_wall_ns"), 1) and integer(object_at(v, "identity").get("started_wall_ns"), 1)
              for v in envelopes)
          and all(envelopes[i]["ended_wall_ns"] <= object_at(envelopes[i+1], "identity")["started_wall_ns"]
                  for i in range(3)), "terminal_collection_order_unproven")
    wmarks = []
    for label, envelope in (("before", before), ("after", after)):
        response = object_at(envelope, "response")
        rec, finance = object_at(response, "final_reconciliation"), object_at(response, "finance")
        wm = object_at(rec, "watermark");wmarks.append(wm)
        check(response.get("frozen_commit") == SOURCE and response.get("contract_sha256") == contract
              and exact_integer(response.get("original_start_boottime_ns"), START)
              and exact_integer(response.get("original_deadline_boottime_ns"), DEADLINE)
              and exact_integer(response.get("planned_rounds"), 5400)
              and exact_integer(response.get("completed_rounds"), 5400)
              and response.get("active_rounds") == [] and response.get("logical_point") == "stable_boundary"
              and exact_integer(response.get("unresolved_steps"), 0)
              and exact_integer(response.get("unresolved_faults"), 0)
              and number(response.get("active_elapsed_seconds")) and response["active_elapsed_seconds"] >= 21600
              and number(p.get("elapsed_seconds")) and response["active_elapsed_seconds"] <= p["elapsed_seconds"],
              label + "_original_terminal_snapshot_mismatch")
        driver = object_at(response, "driver");worker = object_at(response, "worker")
        check(exact_integer(driver.get("pid"), DRIVER[0]) and stopped(driver) and stopped(response.get("listener"))
              and stopped(worker.get("process")) and worker.get("lease_active") is False,
              label + "_stopped_authority_unproven")
        check(fault_schedule(response.get("planned_faults")), label + "_fault_schedule_incomplete")
        # Informational stale market/heartbeat alerts can occur after authority
        # shutdown. The original final reconciliation and fatal-code policy own
        # their meaning; do not turn every post-stop alert into a new gate.
        check(isinstance(response.get("alerts"), list) and finance.get("retry_alerts") == []
              and object_at(finance, "golden").get("compared") is True
              and object_at(finance, "golden").get("passed") is True
              and object_at(finance, "golden").get("errors") == []
              and all(exact_integer(object_at(finance, "counts").get(k), v) for k, v in COUNTS.items())
              and all(integer(v) for v in object_at(finance, "counts").values())
              and exact_integer(object_at(finance, "residuals").get("live_orders"), 0)
              and object_at(finance, "residuals").get("positions") == [],
              label + "_financial_observations_incomplete")
        check(watermark_valid(wm, contract) and financial_watermark_valid(finance.get("watermark"))
              and strict_equal(wm.get("financial"), finance.get("watermark"))
              and object_at(rec, "logs").get("verified") is True
              and integer(object_at(rec, "logs").get("events"), 1)
              and object_at(rec, "logs").get("last_hash") == object_at(wm, "checkpoint").get("hash")
              and strict_equal(object_at(rec, "logs").get("events"), object_at(wm, "checkpoint").get("sequence"))
              and rec.get("independent_reopen_same_watermark") is True
              and rec.get("independent_reopen_reconciliation_passed") is True,
              label + "_watermark_reopen_or_logs_unbound")
        expected_errors = ["producer_cold_audit_same_watermark_missing"] if label == "before" else []
        check(rec.get("errors") == expected_errors and rec.get("eligible") is (label == "after")
              and response.get("final_evidence_eligible") is (label == "after"),
              label + "_final_eligibility_invalid")
    check(bool(wmarks[0]) and strict_equal(wmarks[0], wmarks[1]), "before_after_watermark_mismatch")
    cold_response = object_at(cold, "response")
    check(exact_integer(receipt.get("format"), 1) and receipt.get("producer_cold_audit_passed") is True
          and receipt.get("frozen_commit") == SOURCE and receipt.get("producer_audit_scope") == SCOPE
          and strict_equal(receipt.get("producer_audit_runtime"), {key:env.get(key) for key in ("python", "sqlite")})
          and hex64(receipt.get("audit_sha256")) and strict_equal(receipt.get("watermark_before"), wmarks[0])
          and strict_equal(receipt.get("watermark_after"), wmarks[0])
          and all(strict_equal(cold_response.get(k), receipt.get(k)) for k in ("producer_cold_audit_passed", "frozen_commit",
                 "producer_audit_scope", "producer_audit_runtime", "audit_sha256", "watermark_before", "watermark_after"))
          and object_at(object_at(after, "response"), "final_reconciliation").get("producer_audit_sha256") == receipt.get("audit_sha256"),
          "cold_audit_receipt_binding_mismatch")
    check(integer(receipt.get("private_clone_estimated_bytes"), 1)
          and exact_integer(receipt.get("private_clone_max_bytes"), 1073741824)
          and receipt["private_clone_estimated_bytes"] <= receipt["private_clone_max_bytes"],
          "original_private_clone_budget_receipt_incomplete")
    check(final.get("status") == "COLLECTION_FINISHED" and final.get("financial_final_evidence_eligible") is True
          and final.get("overall_engineering_evidence_within_gates") is True
          and final.get("collection_errors") == [] and final.get("historical_financial_alert_codes") == []
          and final.get("official_driver_drain_requested") is False
          and count_map(final.get("expected_fault_signals"), FAULTS)
          and count_map(final.get("actual_fault_signals"), FAULTS) and final.get("fault_schedule_complete") is True
          and final.get("no_automatic_resume_or_next_job") is True,
          "summary_facts_or_collection_errors_invalid")
    check(strict_equal(final.get("live_coverage"), coverage) and coverage.get("coverage_status") == "COMPLETE_WITHIN_COVERAGE_BUDGET"
          and coverage.get("coverage_no_go_reasons") == [] and coverage.get("fatal_financial_code_counts") == {},
          "coverage_binding_incomplete")
    check(coverage_counts_valid(coverage), "coverage_numeric_or_registered_budget_contract_invalid")
    return binding_result(errors)


def binding_result(errors):
    errors = sorted(set(errors))
    return {"format": 1, "synthetic": True, "observation_only": True,
            "metadata_chain_bound": not errors,
            "binder_review_authorized": REVIEW_AUTHORIZED,
            "candidate_for_independent_terminal_review": not errors and REVIEW_AUTHORIZED,
            "missing_or_mismatched_evidence_codes": errors,
            "terminal_binding_status": "BOUND_PENDING_REVIEW_AUTHORIZATION" if not errors else "INCOMPLETE_OR_MISMATCHED",
            "financial_6h_passed": False, "continuous_6h_stability_passed": False,
            "continuous_24h_stability_passed": False, "capacity_10000_per_s_passed": False,
            "production_approved": False, "full_risk_engine_reexecution_passed": False,
            "whole_business_event_reexecution_passed": False,
            "scope": "sealed JSON metadata consistency only; no new financial verification or process observation"}


def verify_bundle(root, manifest_path, expected_manifest_sha256):
    manifest, seen = read_record(manifest_path, 1048576)
    valid_manifest = (hex64(expected_manifest_sha256) and seen.get("sha256") == expected_manifest_sha256
                      and isinstance(manifest, dict) and manifest.get("schema") == "uta-terminal-json-pins-v1"
                      and manifest.get("source_commit") == SOURCE and isinstance(manifest.get("files"), dict)
                      and set(manifest["files"]) == {path for path, _ in FILES.values()})
    records, observations = {}, {}
    all_pins = valid_manifest
    for label, (relative, cap) in FILES.items():
        records[label], observations[label] = read_record(root / relative, cap)
        expected = manifest["files"].get(relative) if valid_manifest else None
        all_pins = all_pins and hex64(expected) and observations[label].get("sha256") == expected
    failure, failure_observed = read_record(root / "control/supervisor-failure.json", 131072)
    records["supervisor_failure_absent"] = failure_observed.get("state") == "MISSING"
    result = bind_records(records, all_file_pins_verified=bool(all_pins))
    result["record_states"] = {label: value["state"] for label,value in observations.items()}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", type=Path, required=True)
    parser.add_argument("--reviewed-manifest", type=Path, required=True)
    parser.add_argument("--reviewed-manifest-sha256", required=True)
    args = parser.parse_args()
    result = verify_bundle(args.bundle_root, args.reviewed_manifest, args.reviewed_manifest_sha256)
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0 if result["metadata_chain_bound"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
