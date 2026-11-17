"""Bounded JSON-only accounting for a preregistered observer's live coverage.

The caller persists every raw sample/attempt. This module keeps no sample or CID
history, opens no files, and never controls the producer. A coverage NO_GO must
not stop financial collection. Explicit financial failures are returned
separately for the trusted launcher's safe-drain policy.
"""
from collections import Counter
import math
from collections.abc import Mapping
import re


FLAGS = {"continuous_6h_stability_passed": False, "continuous_24h_stability_passed": False,
         "financial_6h_passed": False, "live_coverage_passed": False,
         "production_approved": False, "capacity_10000_per_s_passed": False,
         "capacity_10000_approved": False}
BLOCK_SECONDS = 1800

def _is_unavailable(error):
    return isinstance(error, str) and error.endswith("_unavailable")


def _integer(value, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError("nonnegative_integer_required")
    return value


def _elapsed(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        return None
    return float(value)


def _label(value):
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", value):
        return value
    return "unknown_redacted"


def _digest_label(value):
    return value if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) else "unknown"


def _bounded_count(counter, key, limit=32):
    if key not in counter and len(counter) >= limit:
        key = "other_unclassified"
    counter[key] += 1


def _finance(sample):
    value = sample.get("finance")
    return value if isinstance(value, Mapping) else None


def _golden(sample):
    finance = _finance(sample)
    value = None if finance is None else finance.get("golden")
    return value if isinstance(value, Mapping) else None


def _stable_boundary_proof(sample):
    return (sample.get("logical_point") == "stable_boundary" and sample.get("active_rounds") == []
        and type(sample.get("unresolved_steps")) is int and sample["unresolved_steps"] == 0
        and type(sample.get("unresolved_faults")) is int and sample["unresolved_faults"] == 0)


def _unavailable_verification(sample):
    golden = _golden(sample)
    errors = None if golden is None else golden.get("errors")
    return isinstance(errors, list) and any(_is_unavailable(error) for error in errors)


def fatal_financial_codes(sample):
    """Identify explicit financial evidence, never turn a read exception into debt.

    Unavailable quick/FK checks are technical UNKNOWNs. Actual failed checks or
    business/journal errors in a compared stable snapshot are financial alerts.
    An in-flight, deliberately un-compared golden is never an invariant failure.
    """
    if not isinstance(sample, Mapping):
        return []
    result = set()
    alerts = sample.get("alerts", [])
    alerts = alerts if isinstance(alerts, list) else []
    finance, golden = _finance(sample), _golden(sample)
    if _stable_boundary_proof(sample) and golden is not None and golden.get("compared") is True:
        errors = golden.get("errors", [])
        valid_errors = isinstance(errors, list) and all(isinstance(error, str) for error in errors)
        real_errors = [error for error in errors if not _is_unavailable(error)] if valid_errors else []
        if real_errors or valid_errors and golden.get("passed") is False and not errors:
            result.add("stable_financial_golden_failed")
    if "internal_execution_retry_cause_unknown" in alerts:
        result.add("internal_execution_retry")
    if "terminal_rejection_or_quarantine_observed" in alerts:
        result.add("terminal_command_failure")
    if finance is not None:
        if finance.get("retry_alerts"):
            result.add("internal_execution_retry")
        commands = finance.get("command_inbox", [])
        if isinstance(commands, list):
            for command in commands:
                if not isinstance(command, Mapping):
                    continue
                state = command.get("state")
                if isinstance(state, str) and state in {"REJECTED", "QUARANTINED"} or command.get("quarantined") is True:
                    result.add("terminal_command_failure")
                attempts = command.get("attempts")
                if (type(attempts) is int and attempts > 0 or command.get("last_error_present") is True
                        or command.get("last_error_code") is not None):
                    result.add("internal_execution_retry")
    return sorted(result)


class Coverage:
    def __init__(self, plan):
        observer, producer = plan["observer"], plan["producer"]
        self.blocks = _integer(observer["blocks"], 1)
        if self.blocks > 48:
            raise ValueError("bounded_block_inventory_required")
        self.required = _integer(observer["independent_finance_golden_required_each_1800_second_block"], 1)
        self.technical_budget = _integer(observer["technical_read_unknown_budget"])
        self.streak_budget = _integer(observer["maximum_consecutive_technical_read_unknown"])
        self.duration = _integer(producer["duration_seconds"], 1)
        if self.duration != self.blocks * BLOCK_SECONDS:
            raise ValueError("whole_preregistered_blocks_required")
        interval = observer.get("interval_seconds")
        self.interval = None if interval is None else _integer(interval, 1)
        self._samples = 0
        self._last_attempt = 0
        self._closed = 0
        self._goldens = [0] * self.blocks
        self._counts = Counter()
        self._logical = Counter()
        self._finance_states = Counter()
        self._types, self._digests, self._alerts, self._fatal = Counter(), Counter(), Counter(), Counter()
        self._streak = self._max_streak = 0
        self._reasons = set()

    def _close_blocks(self, active_seconds):
        value = _elapsed(active_seconds)
        if value is not None:
            self._closed = max(self._closed, min(self.blocks, int(value // BLOCK_SECONDS)))
        for index in range(self._closed):
            if self._goldens[index] < self.required:
                self._reasons.add("closed_block_" + str(index) + "_missing_stable_golden")

    def observe(self, sample, *, job_elapsed_seconds, sample_attempt_id):
        attempt = _integer(sample_attempt_id, 1)
        if attempt <= self._last_attempt:
            raise ValueError("attempt_id_must_increase_no_double_count")
        if attempt != self._last_attempt + 1:
            self._reasons.add("sample_attempt_sequence_gap")
        self._last_attempt = attempt
        self._samples += 1
        if not isinstance(sample, Mapping):
            sample = {}
            self._reasons.add("invalid_sample_record")
        logical = sample.get("logical_point")
        logical = logical if isinstance(logical, str) and logical in {"stable_boundary", "inflight_or_unknown", "unknown"} else "missing_or_invalid"
        self._logical[logical] += 1
        alerts = sample.get("alerts", [])
        if not isinstance(alerts, list):
            alerts = []
            self._reasons.add("invalid_alert_inventory")
        if alerts:
            self._counts["alerted_samples"] += 1
        for alert in alerts:
            _bounded_count(self._alerts, _label(alert))
        finance, golden = _finance(sample), _golden(sample)
        unavailable = _unavailable_verification(sample)
        valid_golden_contract = (golden is not None and type(golden.get("compared")) is bool
            and type(golden.get("passed")) is bool and isinstance(golden.get("errors"), list)
            and all(isinstance(error, str) for error in golden["errors"]))
        inconsistent_boundary = logical == "stable_boundary" and not _stable_boundary_proof(sample)
        technical = ("observation_failed_closed" in alerts or unavailable or finance is None
                     or not valid_golden_contract or inconsistent_boundary)
        if inconsistent_boundary:
            self._counts["inconsistent_stable_boundary_samples"] += 1
            self._reasons.add("inconsistent_stable_boundary_proof")
        if golden is not None and not valid_golden_contract:
            self._reasons.add("invalid_golden_contract")
        if technical:
            self._counts["technical_read_unknown_samples"] += 1
            self._streak += 1
            self._max_streak = max(self._max_streak, self._streak)
            _bounded_count(self._types, _label(sample.get("error_type", "not_reported")))
            _bounded_count(self._digests, _digest_label(sample.get("error_digest")), limit=64)
        else:
            self._streak = 0
        if self._counts["technical_read_unknown_samples"] > self.technical_budget:
            self._reasons.add("technical_read_unknown_budget_exceeded")
        if self._max_streak > self.streak_budget:
            self._reasons.add("consecutive_technical_read_unknown_budget_exceeded")
        faults = sample.get("planned_faults", [])
        pending_fault = (isinstance(faults, list) and any(isinstance(fault, Mapping)
            and fault.get("state") == "PLANNED" for fault in faults))
        unresolved = sample.get("unresolved_faults")
        pending_fault = pending_fault or type(unresolved) is int and unresolved > 0
        inflight = logical == "inflight_or_unknown"
        active = bool(sample.get("active_rounds"))
        if inflight and pending_fault:
            self._counts["planned_fault_inflight_unknown_samples"] += 1
        if inflight and active:
            self._counts["active_round_inflight_unknown_samples"] += 1
        if inflight and not active and not pending_fault:
            self._counts["unproven_logical_point_samples"] += 1

        elapsed = _elapsed(job_elapsed_seconds)
        span_start = span_end = elapsed
        span_fields = ("observation_attempt_started_elapsed_seconds", "observation_attempt_ended_elapsed_seconds")
        if any(key in sample for key in span_fields):
            span_start, span_end = (_elapsed(sample.get(key)) for key in span_fields)
        valid_span = span_start is not None and span_end is not None and span_end >= span_start
        credited = None
        fatal = fatal_financial_codes(sample)
        if inconsistent_boundary:
            state = "inconsistent_stable_boundary"
        elif logical == "stable_boundary" and golden is not None and golden.get("compared") is True:
            if golden.get("passed") is True and golden.get("errors") == [] and not technical and not fatal:
                state = "stable_compared_passed"
                if valid_span and span_start < self.duration and span_end < self.duration:
                    start_block, end_block = int(span_start // BLOCK_SECONDS), int(span_end // BLOCK_SECONDS)
                    if start_block == end_block:
                        credited = start_block
                        self._goldens[credited] += 1
                    else:
                        self._counts["stable_golden_cross_block_samples"] += 1
                else:
                    self._counts["stable_golden_uncredited_timing_samples"] += 1
            elif valid_golden_contract and unavailable and not [error for error in golden.get("errors", []) if not _is_unavailable(error)]:
                state = "unavailable_verification"
            elif not valid_golden_contract:
                state = "invalid_golden_contract"
            elif golden.get("passed") is False or fatal:
                state = "stable_compared_failed"
            else:
                state = "invalid_golden_contract"
                self._reasons.add("invalid_golden_contract")
        elif technical:
            state = "unavailable_read_error"
        elif inflight:
            state = "not_compared_inflight_or_unproven"
        else:
            state = "invalid_or_missing_finance_proof"
            self._reasons.add("invalid_or_missing_finance_proof")
        self._finance_states[state] += 1
        if state != "stable_compared_passed":
            self._counts["financial_unknown_or_failed_samples"] += 1
        if not valid_span:
            self._counts["elapsed_or_span_unavailable_samples"] += 1
        if fatal:
            self._counts["fatal_financial_samples"] += 1
            for code in fatal:
                self._fatal[code] += 1
        self._close_blocks(span_end if span_end is not None else elapsed)
        return {"sample_attempt_id": attempt, "technical_read_unknown": technical,
            "planned_fault_inflight_unknown": inflight and pending_fault,
            "financial_golden_state": state, "credited_block": credited,
            "fatal_financial_codes": fatal, "coverage_status": "NO_GO" if self._reasons else "PENDING"}

    def report(self, completed_active_seconds=None, final=False):
        actual = _elapsed(completed_active_seconds)
        self._close_blocks(actual)
        reasons = set(self._reasons)
        if final:
            if actual is None or actual < self.duration:
                reasons.add("actual_active_duration_incomplete_or_unknown")
            for index, count in enumerate(self._goldens):
                if count < self.required:
                    reasons.add("final_block_" + str(index) + "_missing_stable_golden")
            if not self._samples:
                reasons.add("no_samples_observed")
            self._reasons.update(reasons)
        started = self._samples > 0
        if reasons:
            status = "NO_GO"
        elif final:
            status = "COMPLETE_WITHIN_COVERAGE_BUDGET"
        else:
            status = "PENDING" if started else "NOT_STARTED"
        counts = {key: self._counts[key] for key in (
            "technical_read_unknown_samples", "planned_fault_inflight_unknown_samples",
            "active_round_inflight_unknown_samples", "unproven_logical_point_samples",
            "financial_unknown_or_failed_samples", "elapsed_or_span_unavailable_samples",
            "stable_golden_cross_block_samples", "stable_golden_uncredited_timing_samples",
            "inconsistent_stable_boundary_samples", "alerted_samples", "fatal_financial_samples")} if started else None
        blocks = [{"index": index, "start_active_seconds": index * BLOCK_SECONDS,
            "end_active_seconds": (index + 1) * BLOCK_SECONDS, "stable_golden_samples": count if started else None,
            "required_stable_golden_samples": self.required,
            "state": ("SATISFIED" if count >= self.required else "MISSING") if index < self._closed
                     else ("UNOBSERVED_FINAL" if final else "PENDING")} for index, count in enumerate(self._goldens)]
        return {"synthetic": True, "redacted": True, "observation_only": True,
            "observer_is_formal_signoff": False, "measurement_status": "OBSERVED" if started else "NOT_STARTED",
            "coverage_status": status, "coverage_no_go_reasons": sorted(reasons),
            "coverage_budget_requests_stop": False, "samples_observed": self._samples if started else None,
            "last_sample_attempt_id": self._last_attempt if started else None,
            "actual_completed_active_seconds": actual, "preregistered_duration_seconds": self.duration,
            "preregistered_interval_seconds": self.interval, "counts": counts,
            "logical_point_counts": dict(self._logical) if started else None,
            "financial_golden_counts": dict(self._finance_states) if started else None,
            "technical_read_unknown_budget": self.technical_budget,
            "consecutive_technical_read_unknown": self._streak if started else None,
            "maximum_observed_consecutive_technical_read_unknown": self._max_streak if started else None,
            "maximum_allowed_consecutive_technical_read_unknown": self.streak_budget,
            "technical_error_types": dict(self._types) if started else None,
            "technical_error_digests": dict(self._digests) if started else None,
            "technical_error_cause": "unknown_unless_separately_evidenced",
            "alert_counts": dict(self._alerts) if started else None,
            "fatal_financial_code_counts": dict(self._fatal) if started else None,
            "counter_categories_can_overlap": True, "alerts_are_not_financial_evidence": True,
            "raw_samples_preserved_by": "caller_append_only_jsonl", "blocks": blocks, **FLAGS}
