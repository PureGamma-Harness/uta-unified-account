"""Exact one-case child, executable only after a separate final native GO."""
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import multiprocessing.process
import os
from pathlib import Path
import select
import sys
import tempfile
import unittest
from unittest.mock import patch
from weakref import WeakKeyDictionary

sys.path.insert(0, str(Path(__file__).resolve().parent))
from native_once_common import (BoundChild, CASE_JOURNAL_CAP, Journal, PROTECTED_PIDS,
    SELECTOR, ScopeUnknown, binary_info, identity, verify_sources, write_new_json)


def run_case(run_root, gate_fd):
    os.umask(0o077)
    run_root = Path(run_root).resolve()
    source = Path(__file__).resolve().parents[3]
    manifest = json.loads((source / "evidence/reviews/process-readiness-engineering/native-source-manifest.json").read_text())
    preflight = json.loads((run_root / "preflight.json").read_text())
    if os.getpid() in PROTECTED_PIDS or os.getsid(0) != os.getpid():
        raise ScopeUnknown("case_is_not_new_unprotected_session_leader")
    # The controller binds this exact new session birth before releasing it.
    # EOF/timeout exits before binary metadata, UTA import or financial setup.
    try:
        if not select.select([gate_fd], [], [], 5)[0] or os.read(gate_fd, 1) != b"G":
            raise ScopeUnknown("case_start_gate_not_released")
    finally:
        os.close(gate_fd)
    if binary_info() != preflight["binary"]:
        raise ScopeUnknown("case_binary_or_sql_version_changed")
    pins = verify_sources(source, manifest)
    journal = Journal(run_root / "raw/native.jsonl", CASE_JOURNAL_CAP)
    journal.append("case_begin", selector=SELECTOR, birth=identity(os.getpid()),
                   binary=preflight["binary"], sources_sha256=pins,
                   actual_affinity=sorted(os.sched_getaffinity(0)))
    tempfile.tempdir = str(run_root / "business")
    sys.path.insert(0, str(source))
    sys.path.insert(0, str(source / "tests"))
    # Imports below define other fixture classes but run no other method.
    import test_process_readiness
    from uta.durable_process import DurableProcessRouter
    case_class = test_process_readiness.ProcessReadinessTests
    method = "test_malformed_missing_and_oversize_persistent_quotes_fail_closed"
    case = case_class(method)
    bindings, bound_archive = WeakKeyDictionary(), []
    diagnostic_calls, subtests, technical_unknowns = [0], [], []
    original_start = multiprocessing.process.BaseProcess.start
    original_diagnostic = DurableProcessRouter.diagnostics
    original_publish = DurableProcessRouter.publish_market
    original_halt = DurableProcessRouter.set_kill_switch
    original_market = case_class.market
    original_activate = case_class.activate
    original_fault = case_class.offline_fault

    def process_start(process, *args, **kwargs):
        try:
            value = original_start(process, *args, **kwargs)
            bound = BoundChild(process.pid, session=os.getsid(0), parent=os.getpid())
            bindings[process] = bound
            bound_archive.append(bound)
            live = sum(not item.terminal() for item in bound_archive)
            journal.append("owned_worker_started", birth=bound.birth, name=process.name,
                           live_bound_workers=live)
            if live > 2 or process.name not in {"uta-shard-0", "uta-shard-1"}:
                raise ScopeUnknown("unexpected_worker_count_or_name")
            return value
        except BaseException:
            technical_unknowns.append("worker_birth_binding_or_start_failed")
            raise

    def send_for_process(process, signum):
        try:
            bound = bindings.get(process)
            if bound is None or process.pid != bound.birth["pid"]:
                raise ScopeUnknown("runtime_signal_without_birth_binding")
            bound.send(signum, journal, reason="original_runtime_owned_child_cleanup_or_supervision")
        except BaseException:
            technical_unknowns.append("runtime_signal_guard_failed")
            raise

    def diagnostics(router, *args, **kwargs):
        call = diagnostic_calls[0]
        diagnostic_calls[0] += 1
        journal.append("diagnostic_before", call=call, kwargs=kwargs,
                       utc=datetime.now(timezone.utc).isoformat())
        try:
            report = original_diagnostic(router, *args, **kwargs)
        except BaseException as error:
            journal.append("diagnostic_raised", call=call, error_type=type(error).__name__)
            raise
        # Store the original complete report before returning that same object.
        journal.append("diagnostic_after", call=call, report=report,
                       utc=datetime.now(timezone.utc).isoformat())
        return report

    def quote_metadata(snapshot):
        return {"version": snapshot.version, "observed_at": snapshot.observed_at.isoformat(),
                "payload_sha256": hashlib.sha256(snapshot.to_json().encode()).hexdigest()}

    def market(fixture, *args, **kwargs):
        snapshot = original_market(fixture, *args, **kwargs)
        journal.append("original_quote_created", quote=quote_metadata(snapshot))
        return snapshot

    def activate(fixture, snapshot=None):
        journal.append("activate_before", default_quote=snapshot is None,
                       quote=None if snapshot is None else quote_metadata(snapshot))
        result = original_activate(fixture, snapshot)
        journal.append("activate_after", quote=quote_metadata(result),
                       owner_before_quote_evidence=getattr(fixture, "owner_before_quote_evidence", None),
                       readiness_observations=getattr(fixture, "readiness_observations", None))
        return result

    def publish(router, snapshot, *args, **kwargs):
        if (router._config["service"]["max_price_age_us"] != 2000000
                or router._settings["lease_seconds"] != 1 or kwargs.get("timeout") != 8):
            raise ScopeUnknown("original_market_lease_or_publication_threshold_changed")
        journal.append("publish_before", quote=quote_metadata(snapshot), kwargs=kwargs)
        result = original_publish(router, snapshot, *args, **kwargs)
        journal.append("publish_after", result=result)
        return result

    def halt(router, enabled, *args, **kwargs):
        if kwargs.get("timeout") != 8:
            raise ScopeUnknown("original_activation_timeout_changed")
        journal.append("activation_command_before", enabled=enabled, kwargs=kwargs)
        result = original_halt(router, enabled, *args, **kwargs)
        journal.append("activation_command_after", result=result)
        return result

    def fault(fixture, payload):
        encoded = None if payload is None else payload.encode()
        journal.append("original_offline_fault_before", missing=payload is None,
                       payload_bytes=0 if encoded is None else len(encoded),
                       payload_sha256=None if encoded is None else hashlib.sha256(encoded).hexdigest())
        value = original_fault(fixture, payload)
        journal.append("original_offline_fault_after", missing=payload is None)
        return value

    class Result(unittest.TextTestResult):
        def addSubTest(self, test, subtest, error):
            record = {"expected": subtest.params.get("expected"),
                      "missing": subtest.params.get("missing"), "passed": error is None}
            subtests.append(record)
            journal.append("original_subtest", **record)
            super().addSubTest(test, subtest, error)

    import signal
    try:
        with ExitStack() as stack:
            for owner, name, replacement in (
                (multiprocessing.process.BaseProcess, "start", process_start),
                (multiprocessing.process.BaseProcess, "kill", lambda process: send_for_process(process, signal.SIGKILL)),
                (multiprocessing.process.BaseProcess, "terminate", lambda process: send_for_process(process, signal.SIGTERM)),
                (DurableProcessRouter, "diagnostics", diagnostics),
                (DurableProcessRouter, "publish_market", publish),
                (DurableProcessRouter, "set_kill_switch", halt),
                (case_class, "market", market), (case_class, "activate", activate),
                (case_class, "offline_fault", fault)):
                stack.enter_context(patch.object(owner, name, replacement))
            result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2,
                resultclass=Result).run(unittest.TestSuite([case]))
        expected = [("market_invalid", False), ("market_missing", True), ("market_invalid", False)]
        complete_controls = [(item["expected"], item["missing"]) for item in subtests] == expected
        imported_origins = {}
        for name, module in list(sys.modules.items()):
            if name == "uta" or name.startswith("uta."):
                path = Path(module.__file__).resolve()
                relative = str(path.relative_to(source))
                if relative not in pins or hashlib.sha256(path.read_bytes()).hexdigest() != pins[relative]:
                    raise ScopeUnknown("imported_uta_origin_not_in_source_closure")
                imported_origins[name] = relative
        passed = (result.wasSuccessful() and result.testsRun == 1 and not result.skipped
                  and complete_controls and all(item["passed"] for item in subtests)
                  and not technical_unknowns)
        final = {"selector": SELECTOR, "tests_run": result.testsRun,
            "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
            "all_original_negative_controls_reached": complete_controls,
            "subtests": subtests, "test_result": "PASS" if passed else "FAIL",
            "technical_unknowns": technical_unknowns,
            "imported_uta_origins": imported_origins,
            "diagnostic_calls": diagnostic_calls[0], "source_after_sha256": verify_sources(source, manifest),
            "candidate_local_diagnostic_only": True, "original_ci_two_failures_unresolved": True}
        journal.append("case_end", **final)
        write_new_json(run_root / "raw/case-result.json", final)
        return 0 if passed else 1
    finally:
        for bound in bound_archive:
            bound.close()
        journal.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("one private run root and its inherited start-gate FD are required")
    raise SystemExit(run_case(sys.argv[1], int(sys.argv[2])))
