"""Allowlist-only export from private first raw; never edits a raw record."""
from datetime import datetime
import hashlib
import json

from native_once_common import BIRTH_FIELDS, CASE_JOURNAL_CAP, SAFE_EXPORT_CAP, SELECTOR, write_new_json


def code(value):
    return (value if isinstance(value, str) and value.isascii() and len(value) <= 80
            and value.replace("_", "").isalnum() else "redacted")


def number(value):
    return value if type(value) is int and 0 <= value < 2**63 else None


def sha(value):
    return (value if isinstance(value, str) and len(value) == 64
            and all(character in "0123456789abcdef" for character in value) else None)


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.isoformat() if parsed.tzinfo is not None else None
    except (ValueError, TypeError):
        return None


def safe_report(report):
    report = report if isinstance(report, dict) else {}
    exported = {}
    for name in ("state_observed", "ready", "financial_ready", "supervisor_alive", "workers_alive",
                 "managed", "decision_audit_required"):
        exported[name] = report.get(name) if type(report.get(name)) is bool else None
    exported["reason"] = code(report.get("reason"))
    exported["profile"] = code(report.get("profile"))
    if isinstance(report.get("observation_error"), dict):
        detail = report["observation_error"]
        exported["observation_error"] = {"type": code(detail.get("type")),
                                        "sqlite_errorcode": number(detail.get("sqlite_errorcode"))}
    state = report.get("state")
    if isinstance(state, dict):
        watermarks = state.get("watermarks")
        watermarks = watermarks if isinstance(watermarks, dict) else {}
        exported["state"] = {name: state.get(name) if type(state.get(name)) is bool else None
                             for name in ("halted", "publishing")}
        exported["state"].update(epoch=number(state.get("epoch")), market_version=number(state.get("market_version")),
            market_digest=sha(state.get("market_digest")),
            watermarks={name: number(value) for name, value in watermarks.items()
                        if name in {"0", "1"}},
            error=None if state.get("error") is None else code(state["error"]))
    else:
        exported["state"] = None
    exported["workers"] = []
    workers = report.get("workers")
    for row in (workers if isinstance(workers, list) else [])[:2]:
        if not isinstance(row, dict):
            continue
        worker = {name: number(row.get(name)) for name in ("shard", "pid", "owner_pid", "generation", "market_version")}
        worker.update({name: row.get(name) if type(row.get(name)) is bool else None
                       for name in ("alive", "lease_active", "owner_ready", "locally_active",
                                    "market_ready", "funding_registry_ready")})
        worker.update(reason=code(row.get("reason")), market_digest=sha(row.get("market_digest")),
                      market_observed_at=timestamp(row.get("market_observed_at")))
        frame = row.get("report")
        frame = frame if isinstance(frame, dict) else {}
        worker["report"] = {name: number(frame.get(name)) for name in ("shard", "pid", "generation")}
        worker["report"]["state"] = code(frame.get("state"))
        if "code" in frame:
            worker["report"]["code"] = code(frame["code"])
        if isinstance(row.get("observation_error"), dict):
            detail = row["observation_error"]
            worker["observation_error"] = {"type": code(detail.get("type")),
                "sqlite_errorcode": number(detail.get("sqlite_errorcode"))}
        exported["workers"].append(worker)
    return exported


def fault_spec(index):
    payload = b"{broken" if index == 0 else None if index == 1 else b" " * (1024 * 1024 + 1)
    return {"missing": payload is None, "payload_bytes": 0 if payload is None else len(payload),
            "payload_sha256": None if payload is None else hashlib.sha256(payload).hexdigest()}


def matches_trace(value, expected):
    if not isinstance(value, dict) or not isinstance(expected, dict):
        return False
    if any(value.get(key) != expected.get(key) for key in
           ("case_id", "selector", "source_commit", "sources_sha256", "binary")):
        return False
    birth, wanted = value.get("birth"), expected.get("birth")
    return (sha(expected.get("case_id")) is not None and expected.get("selector") == SELECTOR
            and isinstance(birth, dict) and isinstance(wanted, dict)
            and all(key in birth and key in wanted and birth[key] == wanted[key] for key in BIRTH_FIELDS))


def unknown_owner_row(report, row):
    if not isinstance(row, dict) or row.get("reason") in {"diagnostic_timeout", "shard_unavailable", "not_observed"}:
        return True
    if "observation_error" not in row:
        return False
    state, detail = report.get("state"), row.get("observation_error")
    # The reviewed initial owner witness can legitimately precede the first
    # market row. This specific native service error is known missing data.
    return not (isinstance(state, dict) and state.get("market_version") is None
                and row.get("reason") == "market_missing" and isinstance(detail, dict)
                and detail.get("type") == "service_error" and detail.get("sqlite_errorcode") is None)


def owner_witness(report, born_by_shard):
    """Evidence check aligned with readiness_before_quote's unchanged witness."""
    rows, state = report.get("workers"), report.get("state")
    if (report.get("state_observed") is not True or "observation_error" in report
            or report.get("reason") not in {"publication_incomplete", "router_halted", "ready", "local_halt"}
            or report.get("supervisor_alive") is not True or report.get("workers_alive") is not True
            or not isinstance(state, dict) or not isinstance(rows, list) or len(rows) != 2
            or any(not isinstance(row, dict) for row in rows) or [row.get("shard") for row in rows] != [0, 1]):
        return False
    for row in rows:
        frame, shard, pid, generation = row.get("report"), row.get("shard"), row.get("pid"), row.get("generation")
        born = born_by_shard.get(shard)
        expected_missing = row.get("reason") == "market_missing" and state.get("market_version") is None
        if (row.get("reason") != "ready" and not expected_missing or unknown_owner_row(report, row)
                or type(shard) is not int or type(pid) is not int or pid <= 0
                or type(generation) is not int or generation <= 0
                or row.get("alive") is not True or row.get("lease_active") is not True or row.get("owner_ready") is not True
                or type(row.get("owner_pid")) is not int or row["owner_pid"] != pid
                or not isinstance(frame, dict) or frame.get("state") != "ready"
                or type(frame.get("shard")) is not int or frame["shard"] != shard
                or type(frame.get("pid")) is not int or frame["pid"] != pid
                or type(frame.get("generation")) is not int or frame["generation"] != generation
                or not isinstance(born, dict) or born.get("pid") != pid):
            return False
    return True


def export_safe(root, expected_trace):
    """Check one ordered session against the controller's independently bound scope.

    Header/footer and raw case-result must agree with that scope and with event
    counts. Complete failing test evidence may stop before the corrupt loop;
    passing evidence must contain all three attributable original controls.
    """
    path = root / "raw/native.jsonl"
    records, parsed, quotes, issues = [], [], [], []
    complete, before_quote, before_quote_unknown = True, False, False
    pending, calls, completed, control_calls, open_pairs = {}, [], [], {}, {}
    faults, subtests, active_control, test_events = [], [], None, []
    failures = errors = skips = 0
    activation_success = publication_success = command_success = 0
    activation_entries, activation_quotes, initial_quotes = [], [], []
    publish_entries, publish_results, command_entries, command_results = [], [], [], []
    diagnostic_raised = guard_denied = False
    worker_births, signal_pairs = set(), {}
    worker_names, born_by_shard, before_quote_witnesses = set(), {}, []
    control_reports = {}
    workers_started, workers_terminal, helpers_started, helpers_reaped = {}, {}, {}, {}
    helper_stops, helper_completed, cleanup_observations = set(), set(), []
    helpers_during_test = set()

    def invalid(reason):
        nonlocal complete
        complete = False
        if reason not in issues:
            issues.append(reason)

    expected_trace = expected_trace if isinstance(expected_trace, dict) else {}
    expected_birth = expected_trace.get("birth")
    expected_birth = expected_birth if isinstance(expected_birth, dict) else {}
    context = {"case_id": expected_trace.get("case_id"),
               "case_pid": expected_birth.get("pid"), "case_session": expected_birth.get("session")}
    if not matches_trace(expected_trace, expected_trace):
        invalid("expected_scope_incomplete")
    if not path.is_file():
        invalid("native_journal_missing")
        lines = []
    else:
        data = path.read_bytes()
        if len(data) > CASE_JOURNAL_CAP:
            invalid("native_journal_cap_exceeded")
        lines = data.splitlines(keepends=True)
    previous_ns = -1
    for raw in lines:
        if not raw.endswith(b"\n"):
            invalid("partial_native_record")
            break
        try:
            record = json.loads(raw)
        except (ValueError, UnicodeError):
            invalid("invalid_native_record")
            break
        if not isinstance(record, dict):
            invalid("native_record_is_not_object")
            break
        if type(record.get("sequence")) is not int or record["sequence"] != len(parsed):
            invalid("native_sequence_gap_or_duplicate")
        moment = record.get("monotonic_ns")
        if type(moment) is not int or moment < previous_ns:
            invalid("native_clock_order_invalid")
        else:
            previous_ns = moment
        if any(record.get(key) != value for key, value in context.items()):
            invalid("native_session_context_mismatch")
        parsed.append(record)
        event = record.get("event")
        if event == "case_begin":
            if len(parsed) != 1 or not matches_trace(record, expected_trace):
                invalid("native_header_mismatch")
            continue
        if event == "case_end":
            continue
        if event == "original_test_start":
            if test_events or record.get("selector") != SELECTOR or record.get("exact_selected_case") is not True:
                invalid("selected_test_start_mismatch")
            test_events.append("start")
            continue
        if event == "original_test_stop":
            if test_events != ["start"] or record.get("selector") != SELECTOR or record.get("exact_selected_case") is not True:
                invalid("selected_test_stop_mismatch")
            test_events.append("stop")
            continue
        cleanup_events = {"owned_worker_terminal", "helper_stop_before", "helper_reaped", "helper_stop_after",
                          "helper_stop_failed", "case_owned_cleanup_observation", "owned_helper_started"}
        if test_events != ["start"] and not (test_events == ["start", "stop"] and event in cleanup_events):
            invalid("native_event_outside_selected_test")
        if event in {"original_test_failure", "original_test_error", "original_test_skip"}:
            if record.get("selector") != SELECTOR:
                invalid("selected_test_outcome_mismatch")
            failures += event == "original_test_failure"
            errors += event == "original_test_error"
            skips += event == "original_test_skip"
        elif event == "activate_before":
            if "activate" in open_pairs:
                invalid("duplicate_activate_before")
            open_pairs["activate"] = record
            activation_entries.append(record)
            before_quote = record.get("default_quote") is True
        elif event in {"activate_after", "activate_raised"}:
            if open_pairs.pop("activate", None) is None:
                invalid("activate_terminal_without_before")
            activation_success += event == "activate_after"
            if event == "activate_after":
                activation_quotes.append(record.get("quote"))
            before_quote = False
        elif event == "original_quote_created":
            quote = record.get("quote")
            if (not isinstance(quote, dict) or number(quote.get("version")) is None
                    or timestamp(quote.get("observed_at")) is None or sha(quote.get("payload_sha256")) is None):
                invalid("quote_metadata_incomplete")
            else:
                if record.get("control_index") is None:
                    initial_quotes.append(quote)
                quotes.append({"sequence": number(record.get("sequence")),
                    "control_index": number(record.get("control_index")),
                    "quote": {"version": number(quote["version"]), "observed_at": timestamp(quote["observed_at"]),
                              "payload_sha256": sha(quote["payload_sha256"])}})
            before_quote = False
        elif event in {"publish_before", "activation_command_before"}:
            kind = event.removesuffix("_before")
            if kind in open_pairs:
                invalid("duplicate_native_operation_before")
            open_pairs[kind] = record
            (publish_entries if kind == "publish" else command_entries).append(record)
        elif event in {"publish_after", "publish_raised", "activation_command_after", "activation_command_raised"}:
            kind = event.rsplit("_", 1)[0]
            entry = open_pairs.pop(kind, None)
            if entry is None:
                invalid("native_operation_terminal_without_before")
            publication_success += event == "publish_after"
            command_success += event == "activation_command_after"
            if event == "publish_after":
                publish_results.append(record.get("result"))
            elif event == "activation_command_after":
                command_results.append(record.get("result"))
        elif event == "original_offline_fault_before":
            index = record.get("control_index")
            if type(index) is not int or index != len(faults) or index >= 3 or active_control is not None:
                invalid("original_control_start_order_mismatch")
            else:
                if any(record.get(key) != value for key, value in fault_spec(index).items()):
                    invalid("original_control_payload_mismatch")
                active_control = index
                faults.append(False)
                open_pairs["fault"] = index
        elif event in {"original_offline_fault_after", "original_offline_fault_raised"}:
            index = record.get("control_index")
            if type(index) is not int or index != active_control or open_pairs.pop("fault", None) != index:
                invalid("original_control_fault_terminal_mismatch")
            elif event == "original_offline_fault_after":
                faults[index] = True
        elif event == "diagnostic_before":
            call, control = record.get("call"), record.get("control_index")
            phase = "before_quote" if before_quote else "later_independent_observation"
            if (type(call) is not int or call != len(calls) or call in pending or call in completed
                    or control != active_control or record.get("phase") != phase):
                invalid("diagnostic_before_order_or_scope_mismatch")
            else:
                calls.append(call)
                pending[call] = (control, phase)
        elif event in {"diagnostic_after", "diagnostic_raised"}:
            call, control = record.get("call"), record.get("control_index")
            entry = pending.pop(call, None) if type(call) is int else None
            if entry is None or call in completed or entry != (control, record.get("phase")):
                invalid("diagnostic_terminal_duplicate_or_without_before")
            else:
                completed.append(call)
                if control is not None:
                    if type(control) is not int or control >= len(faults) or not faults[control]:
                        invalid("control_diagnostic_precedes_fault_completion")
                    control_calls.setdefault(control, []).append(call)
            if event == "diagnostic_raised":
                diagnostic_raised = True
            else:
                report = record.get("report")
                if not isinstance(report, dict):
                    invalid("native_report_is_not_object")
                    report = {}
                workers = report.get("workers")
                workers = workers if isinstance(workers, list) else []
                unknown = (report.get("reason") in {"diagnostic_timeout", "diagnostic_unavailable"}
                    or "observation_error" in report
                    or any(unknown_owner_row(report, row) for row in workers))
                before_quote_unknown = before_quote_unknown or record.get("phase") == "before_quote" and unknown
                if record.get("phase") == "before_quote":
                    before_quote_witnesses.append(owner_witness(report, born_by_shard))
                if type(control) is int and 0 <= control < 3 and entry is not None:
                    control_reports[control] = report
                records.append({"sequence": number(record.get("sequence")), "call": number(call),
                    "control_index": number(control), "phase": record.get("phase"), "report": safe_report(report)})
        elif event == "original_subtest":
            index = record.get("control_index")
            expected = ("market_invalid", "market_missing", "market_invalid")
            if (type(index) is not int or index != len(subtests) or index != active_control or index >= 3
                    or record.get("expected") != expected[index] or type(record.get("missing")) is not bool
                    or record["missing"] != (index == 1) or type(record.get("passed")) is not bool
                    or record.get("diagnostic_calls") != control_calls.get(index, [])):
                invalid("original_subtest_scope_or_count_mismatch")
            kind = record.get("error_kind")
            if kind not in (None, "failure", "error") or (kind is None) != (record.get("passed") is True):
                invalid("original_subtest_outcome_mismatch")
            if record.get("passed") is True and type(index) is int and 0 <= index < 3:
                observed = control_reports.get(index, {})
                workers = observed.get("workers")
                if (observed.get("ready") is not False or not isinstance(workers, list) or not workers
                        or not isinstance(workers[0], dict) or workers[0].get("reason") != expected[index]):
                    invalid("control_pass_without_original_diagnostic")
            failures += kind == "failure"
            errors += kind == "error"
            subtests.append({key: record.get(key) for key in
                            ("control_index", "expected", "missing", "passed", "error_kind", "diagnostic_calls")})
            active_control = None
        elif event == "worker_start_denied":
            guard_denied = True
        elif event == "owned_worker_started":
            worker = record.get("birth")
            if (not isinstance(worker, dict) or any(key not in worker for key in BIRTH_FIELDS)
                    or worker.get("session") != expected_birth.get("session")
                    or worker.get("uid") != expected_birth.get("uid")
                    or record.get("name") not in {"uta-shard-0", "uta-shard-1"}
                    or type(record.get("live_bound_workers")) is not int
                    or not 1 <= record["live_bound_workers"] <= 2):
                invalid("owned_worker_birth_evidence_invalid")
            else:
                key = tuple(worker[name] for name in BIRTH_FIELDS)
                if key in worker_births:
                    invalid("duplicate_owned_worker_birth")
                worker_births.add(key)
                workers_started[key] = record
                worker_names.add(record["name"])
                born_by_shard[int(record["name"].rsplit("-", 1)[1])] = worker
        elif event in {"owned_helper_started", "owned_worker_terminal", "helper_stop_before", "helper_reaped", "helper_stop_after"}:
            owned_birth = record.get("birth")
            if (not isinstance(owned_birth, dict) or any(key not in owned_birth for key in BIRTH_FIELDS)
                    or owned_birth.get("session") != expected_birth.get("session")
                    or owned_birth.get("uid") != expected_birth.get("uid")):
                invalid("owned_cleanup_birth_mismatch")
                continue
            key = tuple(owned_birth[name] for name in BIRTH_FIELDS)
            if event == "owned_helper_started":
                if (record.get("role") != "multiprocessing.resource_tracker" or key in helpers_started
                        or key in worker_births or helpers_started):
                    invalid("unexpected_or_duplicate_owned_helper")
                helpers_started[key] = record
                if test_events == ["start"]:
                    helpers_during_test.add(key)
            elif event == "owned_worker_terminal":
                if key not in workers_started or key in workers_terminal:
                    invalid("worker_terminal_without_unique_birth")
                workers_terminal[key] = record
            elif key not in helpers_started:
                invalid("helper_cleanup_without_owned_birth")
            elif event == "helper_stop_before":
                if key in helper_stops or key in helper_completed:
                    invalid("duplicate_helper_stop")
                helper_stops.add(key)
            elif event == "helper_reaped":
                if (key not in helper_stops or key in helpers_reaped or type(record.get("wait_pid")) is not int
                        or record["wait_pid"] != owned_birth["pid"] or type(record.get("wait_status")) is not int
                        or record["wait_status"] != 0):
                    invalid("helper_normal_reap_receipt_unproven")
                helpers_reaped[key] = record
            elif event == "helper_stop_after":
                if key not in helper_stops or key not in helpers_reaped or record.get("normal_exit") is not True:
                    invalid("helper_stop_without_normal_reap")
                helper_stops.discard(key)
                helper_completed.add(key)
        elif event == "helper_stop_failed":
            invalid("helper_cleanup_failed")
        elif event == "case_owned_cleanup_observation":
            remaining = record.get("remaining_direct_children")
            if not isinstance(remaining, list) or any(type(pid) is not int for pid in remaining):
                invalid("owned_child_cleanup_observation_invalid")
            cleanup_observations.append(remaining)
        elif event in {"signal_before", "signal_after", "signal_unneeded_terminal"}:
            worker = record.get("birth")
            if not isinstance(worker, dict) or any(key not in worker for key in BIRTH_FIELDS):
                invalid("signal_birth_evidence_incomplete")
            else:
                key = tuple(worker[name] for name in BIRTH_FIELDS)
                signum = record.get("signal")
                if key not in worker_births or type(signum) is not int or signum not in (9, 15):
                    invalid("signal_without_owned_worker_evidence")
                elif event == "signal_before":
                    if (key, signum) in signal_pairs:
                        invalid("duplicate_signal_before")
                    signal_pairs[key, signum] = record.get("reason")
                elif event == "signal_after":
                    if signal_pairs.pop((key, signum), None) != record.get("reason"):
                        invalid("signal_terminal_without_matching_before")
        else:
            invalid("unrecognized_native_event")
    if (not parsed or parsed[0].get("event") != "case_begin" or parsed[-1].get("event") != "case_end"
            or sum(row.get("event") == "case_begin" for row in parsed) != 1
            or sum(row.get("event") == "case_end" for row in parsed) != 1):
        invalid("native_session_boundaries_incomplete")
    if pending or open_pairs or signal_pairs or calls != sorted(completed) or active_control is not None:
        invalid("native_operation_pairs_incomplete")
    if test_events != ["start", "stop"]:
        invalid("selected_test_lifecycle_incomplete")
    result_path = root / "raw/case-result.json"
    try:
        case_result = json.loads(result_path.read_text()) if result_path.is_file() else None
    except (ValueError, OSError, UnicodeError):
        case_result = None
    footer = parsed[-1] if parsed else {}
    result_matches = (matches_trace(case_result, expected_trace) and matches_trace(footer, expected_trace)
        and all(footer.get(key) == value for key, value in case_result.items()))
    expected_counts = {"tests_run": 1, "failures": failures, "errors": errors, "skipped": skips,
        "diagnostic_calls": len(calls), "controls_reached": len(subtests),
        "controls_passed": sum(item["passed"] is True for item in subtests),
        "faults_started": len(faults), "faults_completed": sum(faults), "journal_records": len(parsed)}
    if (not isinstance(case_result, dict) or any(type(case_result.get(key)) is not int or case_result[key] != value
            for key, value in expected_counts.items()) or case_result.get("subtests") != subtests
            or case_result.get("test_events") != test_events
            or case_result.get("source_after_sha256") != expected_trace.get("sources_sha256")):
        result_matches = False
    if not result_matches:
        invalid("case_result_does_not_match_ordered_trace")
    expected_owned = []
    for key, row in workers_started.items():
        terminal = workers_terminal.get(key, {})
        expected_owned.append({"role": "financial_worker", "name": row["name"], "birth": row["birth"],
                               "terminal": terminal.get("terminal"), "reaped": terminal.get("reaped")})
    for key, row in helpers_started.items():
        expected_owned.append({"role": "multiprocessing.resource_tracker", "birth": row["birth"],
            "terminal": key in helper_completed, "reaped": key in helpers_reaped,
            "wait_status": helpers_reaped.get(key, {}).get("wait_status")})
    owned_closed = (not helper_stops and cleanup_observations == [[]]
        and len(workers_terminal) == len(workers_started)
        and (not workers_started or len(helpers_started) == 1)
        and helpers_during_test == set(helpers_started)
        and len(helpers_started) == len(helper_completed) == len(helpers_reaped)
        and all(item["terminal"] is True and item["reaped"] is True for item in expected_owned))
    if (not isinstance(case_result, dict) or case_result.get("owned_processes") != expected_owned
            or case_result.get("remaining_direct_children") != []
            or case_result.get("helper_cleanup_proven") is not True or not owned_closed):
        invalid("owned_process_cleanup_evidence_incomplete")
    complete_controls = (len(subtests) == 3 and faults == [True, True, True]
                         and all(control_calls.get(index) for index in range(3)))
    if isinstance(case_result, dict) and case_result.get("all_original_negative_controls_reached") is not (len(subtests) == 3):
        invalid("original_control_completion_flag_mismatch")
    clean = (complete and result_matches and not diagnostic_raised and not guard_denied
             and isinstance(case_result.get("technical_unknowns"), list) and not case_result["technical_unknowns"]
             and errors == 0 and skips == 0)
    pass_evidence = (clean and case_result.get("test_result") == "PASS" and failures == 0
        and complete_controls and all(item["passed"] for item in subtests) and not before_quote_unknown
        and worker_names == {"uta-shard-0", "uta-shard-1"} and before_quote_witnesses == [True]
        and len(helpers_started) == 1
        and all(row["sequence"] < next(item["sequence"] for item in records if item["phase"] == "before_quote")
                for row in helpers_started.values())
        and activation_success == publication_success == command_success == 1
        and len(activation_entries) == len(initial_quotes) == len(publish_entries) == len(command_entries) == 1
        and activation_entries[0].get("default_quote") is True and initial_quotes[0].get("version") == 1
        and activation_quotes == initial_quotes and publish_entries[0].get("quote") == initial_quotes[0]
        and publish_entries[0].get("kwargs") == {"timeout": 8}
        and command_entries[0].get("kwargs") == {"timeout": 8} and command_entries[0].get("enabled") is False
        and isinstance(publish_results[0], dict) and publish_results[0].get("publishing") is False
        and isinstance(command_results[0], dict) and command_results[0].get("halted") is False
        and any(row["phase"] == "before_quote" for row in records)
        and any(row["control_index"] is None and row["phase"] == "later_independent_observation"
                and row["report"].get("ready") is True and row["report"].get("financial_ready") is True
                for row in records))
    failure_evidence = (clean and case_result.get("test_result") == "FAIL" and failures > 0
        and len(faults) == len(subtests) and all(faults)
        and all(control_calls.get(index) for index in range(len(subtests))))
    value = {"schema": 2, "journal_complete": complete, "before_quote_unknown": bool(before_quote_unknown),
        "case_result_matches_trace": bool(result_matches), "pass_evidence_complete": bool(pass_evidence),
        "failure_evidence_complete": bool(failure_evidence), "trace_errors": issues,
        "controls_reached": len(subtests), "controls_passed": expected_counts["controls_passed"],
        "owned_processes": [{"role": item["role"] if item["role"] in {"financial_worker", "multiprocessing.resource_tracker"} else "redacted",
            "name": item.get("name") if item.get("name") in {"uta-shard-0", "uta-shard-1"} else None,
            "pid": number(item["birth"].get("pid")), "session": number(item["birth"].get("session")),
            "terminal": item["terminal"] if type(item["terminal"]) is bool else None,
            "reaped": item["reaped"] if type(item["reaped"]) is bool else None,
            "wait_status": number(item.get("wait_status"))} for item in expected_owned],
        "diagnostics": records, "quotes": quotes, "candidate_local_diagnostic_only": True,
        "original_ci_two_failures_unresolved": True}
    write_new_json(root / "safe/diagnostics.json", value, cap=SAFE_EXPORT_CAP)
    return {key: value[key] for key in ("journal_complete", "before_quote_unknown", "case_result_matches_trace",
                                      "pass_evidence_complete", "failure_evidence_complete")}
