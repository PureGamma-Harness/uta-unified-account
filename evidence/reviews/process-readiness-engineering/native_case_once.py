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
import traceback
from threading import RLock
from time import monotonic
import unittest
from unittest.mock import patch
from weakref import WeakKeyDictionary

sys.path.insert(0, str(Path(__file__).resolve().parent))
from native_once_common import (BoundChild, CASE_JOURNAL_CAP, Journal,
    SELECTOR, ScopeUnknown, binary_info, children_of, digest, identity, require_before,
    require_unprotected_pid, same_birth, verify_sources, write_new_json)


def run_case(run_root, gate_fd, native_deadline, signal_deadline):
    os.umask(0o077)
    run_root = Path(run_root).resolve()
    source = Path(__file__).resolve().parents[3]
    manifest = json.loads((source / "evidence/reviews/process-readiness-engineering/native-source-manifest.json").read_text())
    preflight = json.loads((run_root / "preflight.json").read_text())
    require_unprotected_pid(os.getpid())
    require_before(native_deadline, "case_started_after_native_deadline")
    require_before(signal_deadline, "case_started_after_signal_deadline")
    if signal_deadline <= native_deadline or os.getsid(0) != os.getpid():
        raise ScopeUnknown("case_is_not_new_unprotected_session_leader")
    # The controller binds this exact new session birth before releasing it.
    # EOF/timeout exits before binary metadata, UTA import or financial setup.
    try:
        if (not select.select([gate_fd], [], [], min(5, max(0, native_deadline - monotonic())))[0]
                or os.read(gate_fd, 1) != b"G"):
            raise ScopeUnknown("case_start_gate_not_released")
    finally:
        os.close(gate_fd)
    require_before(native_deadline, "case_gate_returned_after_native_deadline")
    if binary_info() != preflight["binary"]:
        raise ScopeUnknown("case_binary_or_sql_version_changed")
    pins = verify_sources(source, manifest)
    birth = identity(os.getpid())
    trace = {"case_id": digest(run_root / "preflight.json"), "selector": SELECTOR,
             "source_commit": preflight["source_commit"], "birth": birth,
             "binary": preflight["binary"], "sources_sha256": pins}
    journal = Journal(run_root / "raw/native.jsonl", CASE_JOURNAL_CAP,
        context={"case_id": trace["case_id"], "case_pid": birth["pid"], "case_session": birth["session"]})
    journal.append("case_begin", **trace,
                   actual_affinity=sorted(os.sched_getaffinity(0)))
    require_before(native_deadline, "case_metadata_returned_after_native_deadline")
    tempfile.tempdir = str(run_root / "business")
    sys.path.insert(0, str(source))
    sys.path.insert(0, str(source / "tests"))
    # Imports below define other fixture classes but run no other method.
    import test_process_readiness
    from uta import durable_process as runtime
    from uta.durable_process import DurableProcessRouter
    case_class = test_process_readiness.ProcessReadinessTests
    method = "test_malformed_missing_and_oversize_persistent_quotes_fail_closed"
    case = case_class(method)
    bindings, bound_archive = WeakKeyDictionary(), []
    diagnostic_calls, subtests, technical_unknowns = [0], [], []
    guard_lock, start_denied, current_control, before_quote = RLock(), [False], [None], [False]
    faults, control_calls, test_events, runtime_pidfds = [], {}, [], {}
    bound_names, starting_names, starting_count = {}, set(), [0]
    helper_archive, helper_result = [], {"pid": None, "reaped": False, "status": None}
    original_start = multiprocessing.process.BaseProcess.start
    original_diagnostic = DurableProcessRouter.diagnostics
    original_publish = DurableProcessRouter.publish_market
    original_halt = DurableProcessRouter.set_kill_switch
    original_market = case_class.market
    original_activate = case_class.activate
    original_fault = case_class.offline_fault
    original_identity, original_os, original_signal = runtime._process_identity, runtime.os, runtime.signal

    def uncertain(code):
        with guard_lock:
            start_denied[0] = True
            if code not in technical_unknowns:
                technical_unknowns.append(code)

    def bind_helper():
        try:
            module = sys.modules.get("multiprocessing.resource_tracker")
            tracker = getattr(module, "_resource_tracker", None)
            pid = getattr(tracker, "_pid", None)
            require_unprotected_pid(pid)
            if any(item.birth["pid"] == pid for item in bound_archive):
                raise ScopeUnknown("helper_pid_aliases_financial_worker")
            for bound in helper_archive:
                if bound.birth["pid"] == pid:
                    if not bound.verify():
                        raise ScopeUnknown("owned_helper_exited_before_case_completion")
                    return bound
            bound = BoundChild(pid, session=birth["session"], parent=birth["pid"],
                               signal_deadline=signal_deadline)
            helper_archive.append(bound)  # Retain even an unexpected helper for cleanup evidence.
            journal.append("owned_helper_started", role="multiprocessing.resource_tracker", birth=bound.birth)
            if len(helper_archive) != 1:
                raise ScopeUnknown("unexpected_additional_resource_tracker")
            return bound
        except BaseException:
            uncertain("resource_tracker_birth_binding_failed")
            raise

    def stop_helper():
        try:
            if len(helper_archive) != 1:
                raise ScopeUnknown("single_owned_resource_tracker_unproven")
            bound = helper_archive[0]
            module = sys.modules.get("multiprocessing.resource_tracker")
            tracker = getattr(module, "_resource_tracker", None)
            if tracker is None or tracker._pid != bound.birth["pid"]:
                raise ScopeUnknown("resource_tracker_reference_changed")

            def guarded_waitpid(pid, options):
                require_unprotected_pid(pid)
                require_before(signal_deadline, "helper_reap_after_cleanup_deadline")
                if pid != bound.birth["pid"] or options != 0 or not same_birth(identity(pid), bound.birth):
                    raise ScopeUnknown("helper_waitpid_without_matching_birth")
                receipt = original_os.waitpid(pid, options)
                journal.append("helper_reaped", birth=bound.birth, wait_pid=receipt[0], wait_status=receipt[1])
                if (type(receipt[0]) is not int or type(receipt[1]) is not int
                        or receipt != (pid, 0)):
                    raise ScopeUnknown("helper_normal_exit_unproven")
                helper_result.update(pid=pid, reaped=True, status=receipt[1])
                return receipt

            journal.append("helper_stop_before", birth=bound.birth)
            require_before(signal_deadline, "helper_stop_after_cleanup_deadline")
            # Use the pinned stdlib's normal close-alive-pipe/EOF/wait path;
            # retain its actual waitpid receipt instead of assuming _pid=None.
            with tracker._lock:
                tracker._stop_locked(waitpid=guarded_waitpid)
            clean = helper_result["reaped"] and helper_result["status"] == 0 and bound.terminal()
            if not clean:
                raise ScopeUnknown("helper_stop_without_normal_reap")
            journal.append("helper_stop_after", birth=bound.birth, normal_exit=True)
            return True
        except BaseException as error:
            uncertain("resource_tracker_cleanup_unproven")
            journal.append("helper_stop_failed", error_type=type(error).__name__)
            return False

    def collect_owned_processes():
        module = sys.modules.get("multiprocessing.resource_tracker")
        tracker = getattr(module, "_resource_tracker", None)
        if not helper_archive and getattr(tracker, "_pid", None) is not None:
            try:
                bind_helper()  # A failed worker start can still have launched its helper.
            except BaseException:
                uncertain("late_resource_tracker_binding_unproven")
        helper_clean = stop_helper() if helper_archive or bound_archive else True
        remaining = children_of(birth["pid"])
        owned = []
        for bound in bound_archive:
            terminal = bound.terminal()
            reaped = terminal and bound.birth["pid"] not in remaining
            journal.append("owned_worker_terminal", birth=bound.birth, terminal=terminal, reaped=reaped)
            owned.append({"role": "financial_worker", "name": bound_names.get(bound),
                          "birth": bound.birth, "terminal": terminal, "reaped": reaped})
        for bound in helper_archive:
            owned.append({"role": "multiprocessing.resource_tracker", "birth": bound.birth,
                          "terminal": bound.terminal(),
                          "reaped": helper_result["pid"] == bound.birth["pid"] and helper_result["reaped"],
                          "wait_status": helper_result["status"] if helper_result["pid"] == bound.birth["pid"] else None})
        journal.append("case_owned_cleanup_observation", remaining_direct_children=remaining)
        if (not helper_clean or remaining
                or any(not item["terminal"] or not item["reaped"] for item in owned)):
            uncertain("owned_process_exit_or_reap_unproven")
        return owned, remaining, helper_clean

    def owned_bound(pid):
        require_unprotected_pid(pid)
        with guard_lock:
            matches = [item for item in bound_archive if item.birth["pid"] == pid]
            if not matches:
                uncertain("runtime_unbound_process_access_denied")
                raise ScopeUnknown("runtime_unbound_process_access_denied")
            bound = matches[-1]
            # A historical registry row cannot authorize inspecting a reused PID.
            if bound.terminal() or not bound.verify():
                raise ProcessLookupError("original owned birth has exited")
            return bound

    def runtime_identity(pid):
        try:
            require_unprotected_pid(pid)
            require_before(signal_deadline, "runtime_identity_after_scope_deadline")
            bound = None if pid == birth["pid"] else owned_bound(pid)
            value = original_identity(pid)
            expected = birth if bound is None else bound.birth
            if any(value[key] != expected[key] for key in ("pid", "start_ticks", "boot_id", "uid")):
                raise ScopeUnknown("runtime_identity_birth_mismatch")
            return value
        except ProcessLookupError:
            raise  # Expected skip for the original registry's exited old children.
        except BaseException:
            uncertain("runtime_identity_guard_failed")
            raise

    class RuntimeOS:
        def __getattr__(self, name):
            return getattr(original_os, name)

        def pidfd_open(self, pid, flags=0):
            try:
                bound = owned_bound(pid)
                require_before(signal_deadline, "runtime_pidfd_after_scope_deadline")
                fd = original_os.pidfd_open(pid, flags)
                runtime_pidfds[fd] = bound
                return fd
            except ProcessLookupError:
                raise
            except BaseException:
                uncertain("runtime_pidfd_guard_failed")
                raise

        def close(self, fd):
            runtime_pidfds.pop(fd, None)
            return original_os.close(fd)

    class RuntimeSignal:
        def __getattr__(self, name):
            return getattr(original_signal, name)

        def pidfd_send_signal(self, fd, signum, siginfo=None, flags=0):
            try:
                bound = runtime_pidfds.get(fd)
                if bound is None or siginfo is not None or flags != 0 or signum not in (signal.SIGTERM, signal.SIGKILL):
                    raise ScopeUnknown("runtime_signal_without_registered_pidfd")
                return bound.send(signum, journal, reason="original_registered_orphan_recovery")
            except BaseException:
                uncertain("runtime_direct_signal_guard_failed")
                raise

    def process_start(process, *args, **kwargs):
        try:
            # Serialize reservation through binding: a concurrent monitor cannot
            # pass the same two-slot check while another start is in flight.
            with guard_lock:
                reserved_name = None
                try:
                    require_before(native_deadline, "worker_start_after_native_deadline")
                    live = [item for item in bound_archive if not item.terminal()]
                    name = process.name
                    if (start_denied[0] or name not in {"uta-shard-0", "uta-shard-1"}
                            or len(live) + starting_count[0] >= 2 or name in starting_names
                            or any(bound_names.get(item) == name for item in live)):
                        uncertain("worker_start_admission_denied")
                        journal.append("worker_start_denied", name=name)
                        raise ScopeUnknown("worker_start_admission_denied")
                    # RLock also permits nested calls: reserve before invoking
                    # the original method so reentrancy cannot consume this slot.
                    reserved_name = name
                    starting_names.add(name)
                    starting_count[0] += 1
                    require_before(native_deadline, "worker_start_admission_returned_late")
                    value = original_start(process, *args, **kwargs)
                    require_unprotected_pid(process.pid)
                    bound = BoundChild(process.pid, session=birth["session"], parent=birth["pid"],
                                       signal_deadline=signal_deadline)
                    bindings[process] = bound
                    bound_archive.append(bound)
                    if any(item is not bound and item.birth["pid"] == bound.birth["pid"] for item in bound_archive):
                        raise ScopeUnknown("owned_worker_pid_number_reused")
                    live = [item for item in bound_archive if not item.terminal()]
                    if (start_denied[0] or process.name != name or process.name not in {"uta-shard-0", "uta-shard-1"}
                            or len(live) > 2 or any(item is not bound and bound_names.get(item) == name for item in live)):
                        raise ScopeUnknown("worker_post_start_admission_mismatch")
                    bound_names[bound] = name
                    journal.append("owned_worker_started", birth=bound.birth, name=name,
                                   live_bound_workers=len(live))
                    bind_helper()
                    require_before(native_deadline, "worker_start_binding_returned_late")
                    return value
                finally:
                    if reserved_name is not None:
                        starting_names.discard(reserved_name)
                        starting_count[0] -= 1
        except BaseException:
            uncertain("worker_birth_binding_or_start_failed")
            raise

    def send_for_process(process, signum):
        try:
            bound = bindings.get(process)
            if bound is None or process.pid != bound.birth["pid"]:
                raise ScopeUnknown("runtime_signal_without_birth_binding")
            bound.send(signum, journal, reason="original_runtime_owned_child_cleanup_or_supervision")
        except BaseException:
            uncertain("runtime_signal_guard_failed")
            raise

    def diagnostics(router, *args, **kwargs):
        with guard_lock:
            call = diagnostic_calls[0]
            diagnostic_calls[0] += 1
            control = current_control[0]
            phase = "before_quote" if before_quote[0] else "later_independent_observation"
            if control is not None:
                control_calls.setdefault(control, []).append(call)
        journal.append("diagnostic_before", call=call, control_index=control, phase=phase, kwargs=kwargs,
                       utc=datetime.now(timezone.utc).isoformat())
        try:
            report = original_diagnostic(router, *args, **kwargs)
        except BaseException as error:
            uncertain("original_diagnostic_raised")
            journal.append("diagnostic_raised", call=call, control_index=control, phase=phase,
                           error_type=type(error).__name__)
            raise
        # Store the original complete report before returning that same object.
        journal.append("diagnostic_after", call=call, control_index=control, phase=phase, report=report,
                       utc=datetime.now(timezone.utc).isoformat())
        return report

    def quote_metadata(snapshot):
        return {"version": snapshot.version, "observed_at": snapshot.observed_at.isoformat(),
                "payload_sha256": hashlib.sha256(snapshot.to_json().encode()).hexdigest()}

    def market(fixture, *args, **kwargs):
        snapshot = original_market(fixture, *args, **kwargs)
        journal.append("original_quote_created", quote=quote_metadata(snapshot), control_index=current_control[0])
        before_quote[0] = False
        return snapshot

    def activate(fixture, snapshot=None):
        journal.append("activate_before", default_quote=snapshot is None,
                       quote=None if snapshot is None else quote_metadata(snapshot))
        before_quote[0] = snapshot is None
        try:
            result = original_activate(fixture, snapshot)
        except BaseException as error:
            journal.append("activate_raised", error_type=type(error).__name__)
            raise
        finally:
            before_quote[0] = False
        journal.append("activate_after", quote=quote_metadata(result),
                       owner_before_quote_evidence=getattr(fixture, "owner_before_quote_evidence", None),
                       readiness_observations=getattr(fixture, "readiness_observations", None))
        return result

    def publish(router, snapshot, *args, **kwargs):
        if (router._config["service"]["max_price_age_us"] != 2000000
                or router._settings["lease_seconds"] != 1 or kwargs.get("timeout") != 8):
            raise ScopeUnknown("original_market_lease_or_publication_threshold_changed")
        journal.append("publish_before", quote=quote_metadata(snapshot), kwargs=kwargs)
        try:
            result = original_publish(router, snapshot, *args, **kwargs)
        except BaseException as error:
            journal.append("publish_raised", error_type=type(error).__name__)
            raise
        journal.append("publish_after", result=result)
        return result

    def halt(router, enabled, *args, **kwargs):
        if kwargs.get("timeout") != 8:
            raise ScopeUnknown("original_activation_timeout_changed")
        journal.append("activation_command_before", enabled=enabled, kwargs=kwargs)
        try:
            result = original_halt(router, enabled, *args, **kwargs)
        except BaseException as error:
            journal.append("activation_command_raised", error_type=type(error).__name__)
            raise
        journal.append("activation_command_after", result=result)
        return result

    def fault(fixture, payload):
        encoded = None if payload is None else payload.encode()
        control = len(faults)
        if current_control[0] is not None or control >= 3:
            uncertain("unexpected_original_fault_order")
            raise ScopeUnknown("unexpected_original_fault_order")
        current_control[0] = control
        faults.append(False)
        journal.append("original_offline_fault_before", control_index=control, missing=payload is None,
                       payload_bytes=0 if encoded is None else len(encoded),
                       payload_sha256=None if encoded is None else hashlib.sha256(encoded).hexdigest())
        try:
            value = original_fault(fixture, payload)
        except BaseException as error:
            journal.append("original_offline_fault_raised", control_index=control, error_type=type(error).__name__)
            raise
        faults[control] = True
        journal.append("original_offline_fault_after", control_index=control, missing=payload is None)
        return value

    class Result(unittest.TextTestResult):
        def startTest(self, test):
            test_events.append("start")
            journal.append("original_test_start", selector=SELECTOR, exact_selected_case=test is case)
            super().startTest(test)

        def stopTest(self, test):
            test_events.append("stop")
            journal.append("original_test_stop", selector=SELECTOR, exact_selected_case=test is case)
            super().stopTest(test)

        def addFailure(self, test, error):
            journal.append("original_test_failure", selector=SELECTOR, error_type=error[0].__name__)
            super().addFailure(test, error)

        def addError(self, test, error):
            uncertain("original_test_error")
            journal.append("original_test_error", selector=SELECTOR, error_type=error[0].__name__)
            super().addError(test, error)

        def addSkip(self, test, reason):
            uncertain("original_test_skipped")
            journal.append("original_test_skip", selector=SELECTOR)
            super().addSkip(test, reason)

        def addSubTest(self, test, subtest, error):
            control = current_control[0]
            record = {"control_index": control, "expected": subtest.params.get("expected"),
                      "missing": subtest.params.get("missing"), "passed": error is None,
                      "error_kind": None if error is None else "failure" if issubclass(error[0], test.failureException) else "error",
                      "diagnostic_calls": list(control_calls.get(control, []))}
            if control != len(subtests) or test is not case:
                uncertain("original_subtest_attribution_failed")
            subtests.append(record)
            journal.append("original_subtest", **record)
            current_control[0] = None
            super().addSubTest(test, subtest, error)

    import signal
    try:
        with ExitStack() as stack:
            for owner, name, replacement in (
                (multiprocessing.process.BaseProcess, "start", process_start),
                (multiprocessing.process.BaseProcess, "kill", lambda process: send_for_process(process, signal.SIGKILL)),
                (multiprocessing.process.BaseProcess, "terminate", lambda process: send_for_process(process, signal.SIGTERM)),
                (runtime, "_process_identity", runtime_identity),
                (runtime, "os", RuntimeOS()), (runtime, "signal", RuntimeSignal()),
                (DurableProcessRouter, "diagnostics", diagnostics),
                (DurableProcessRouter, "publish_market", publish),
                (DurableProcessRouter, "set_kill_switch", halt),
                (case_class, "market", market), (case_class, "activate", activate),
                (case_class, "offline_fault", fault)):
                stack.enter_context(patch.object(owner, name, replacement))
            result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2,
                resultclass=Result).run(unittest.TestSuite([case]))
        owned_processes, remaining_children, helper_clean = collect_owned_processes()
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
                  and faults == [True, True, True] and test_events == ["start", "stop"]
                  and not technical_unknowns)
        status = "UNKNOWN" if technical_unknowns or result.errors or result.skipped else "PASS" if passed else "FAIL"
        final = {**trace, "tests_run": result.testsRun,
            "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
            "all_original_negative_controls_reached": complete_controls,
            "subtests": subtests, "test_result": status,
            "controls_reached": len(subtests), "controls_passed": sum(item["passed"] for item in subtests),
            "faults_started": len(faults), "faults_completed": sum(faults), "test_events": test_events,
            "owned_processes": owned_processes, "remaining_direct_children": remaining_children,
            "helper_cleanup_proven": helper_clean,
            "technical_unknowns": technical_unknowns,
            "imported_uta_origins": imported_origins,
            "diagnostic_calls": diagnostic_calls[0], "source_after_sha256": verify_sources(source, manifest),
            "journal_records": journal.sequence + 1,
            "candidate_local_diagnostic_only": True, "original_ci_two_failures_unresolved": True}
        journal.append("case_end", **final)
        write_new_json(run_root / "raw/case-result.json", final)
        return 0 if status == "PASS" else 1 if status == "FAIL" else 75
    finally:
        for bound in [*bound_archive, *helper_archive]:
            bound.close()
        journal.close()


def finish_case(status):
    # Native/fixture cleanup and the explicit tracker stop already ran. Bypass
    # multiprocessing's later atexit/daemon termination and tracker destructors;
    # residual owned births belong to the outer controller's bounded cleanup.
    try:
        try:
            sys.stdout.flush()
        except BaseException:
            status = 75
        try:
            sys.stderr.flush()
        except BaseException:
            status = 75
    finally:
        os._exit(status)


if __name__ == "__main__":
    status = 75
    try:
        if len(sys.argv) != 5:
            raise ScopeUnknown("one private run root, inherited gate FD and two shared absolute deadlines are required")
        status = run_case(sys.argv[1], int(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]))
    except BaseException:
        try:
            traceback.print_exc(file=sys.stderr)
        except BaseException:
            pass
    finally:
        finish_case(status)
