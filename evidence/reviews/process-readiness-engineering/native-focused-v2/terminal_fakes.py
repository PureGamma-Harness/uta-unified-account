"""Eleven finite AST properties; no native module, IO or process is exercised.

The separately authorized runner must pin source bytes before filling TREES.
The original eight properties remain; new cases cover honest FAIL and guards.
"""
import ast
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from types import SimpleNamespace
import unittest

from fake_support import FakeLock, TREES, run_nodes, selected_common


SELECTOR = "test_process_readiness.ProcessReadinessTests.test_malformed_missing_and_oversize_persistent_quotes_fail_closed"
CONTROLS = (("market_invalid", False), ("market_missing", True), ("market_invalid", False))


class MemoryPath:
    def __init__(self, files, path=""):
        self.files, self.path = files, path

    def __truediv__(self, value):
        return MemoryPath(self.files, self.path + "/" + str(value))

    def is_file(self):
        return self.path in self.files

    def read_bytes(self):
        return self.files[self.path]

    def read_text(self):
        return self.read_bytes().decode()


def model_birth(pid, *, session=8000):
    return {"pid": pid, "start_ticks": pid + 1, "boot_id": "model-boot", "uid": 1000,
            "session": session, "ppid": 8000, "pgrp": session, "state": "S"}


def expected_trace():
    return {"case_id": "a" * 64, "selector": SELECTOR, "source_commit": "b" * 40,
            "sources_sha256": {"uta/synthetic.py": "c" * 64}, "birth": model_birth(8000),
            "binary": {"executable_sha256": "d" * 64}}


def native_report(reason="ready", *, before_quote=False):
    report = {"state_observed": True, "supervisor_alive": True, "workers_alive": True,
        "ready": reason == "ready", "financial_ready": reason == "ready", "managed": True,
        "decision_audit_required": False, "profile": "managed_development_legacy_gap", "reason": reason,
        "state": {"halted": False, "publishing": False, "epoch": 2, "market_version": 1,
                  "market_digest": "e" * 64, "watermarks": {"0": 1, "1": 1}, "error": None},
        "workers": [{"shard": shard, "pid": 9000 + shard, "owner_pid": 9000 + shard,
            "generation": 2, "alive": True, "lease_active": True, "owner_ready": True,
            "market_ready": reason == "ready", "funding_registry_ready": reason == "ready", "reason": reason,
            "report": {"state": "ready", "shard": shard, "pid": 9000 + shard, "generation": 2}}
            for shard in (0, 1)]}
    if before_quote:
        report.update(ready=False, financial_ready=False, reason="publication_incomplete")
        report["state"]["market_version"] = None
        for row in report["workers"]:
            row.update(reason="market_missing", market_ready=False,
                       observation_error={"type": "service_error"})
    return report


def exporter_namespace():
    namespace = selected_common()
    namespace.update(datetime=datetime, hashlib=hashlib, SELECTOR=SELECTOR,
                     CASE_JOURNAL_CAP=4 * 1024 * 1024, SAFE_EXPORT_CAP=512 * 1024)
    definitions = [node for node in TREES["native_safe_export.py"].body if isinstance(node, ast.FunctionDef)]
    run_nodes(definitions, namespace, "new-exporter-memory-selected-AST")
    return namespace


def fixture(*, early_fail=False):
    trace, rows = expected_trace(), []
    context = {"case_id": trace["case_id"], "case_pid": 8000, "case_session": 8000}

    def add(event, **fields):
        rows.append({**context, **fields, "sequence": len(rows), "event": event,
                     "monotonic_ns": len(rows) + 1})

    add("case_begin", **trace)
    add("original_test_start", selector=SELECTOR, exact_selected_case=True)
    subtests = []
    if early_fail:
        add("original_test_failure", selector=SELECTOR, error_type="AssertionError")
    else:
        for shard in (0, 1):
            add("owned_worker_started", birth=model_birth(9000 + shard), name="uta-shard-" + str(shard),
                live_bound_workers=shard + 1)
        add("owned_helper_started", role="multiprocessing.resource_tracker", birth=model_birth(9500))
        add("activate_before", default_quote=True, quote=None)
        add("diagnostic_before", call=0, control_index=None, phase="before_quote")
        add("diagnostic_after", call=0, control_index=None, phase="before_quote", report=native_report(before_quote=True))
        quote = {"version": 1, "observed_at": "2026-11-18T00:00:00+00:00", "payload_sha256": "f" * 64}
        add("original_quote_created", control_index=None, quote=quote)
        add("publish_before", quote=quote, kwargs={"timeout": 8})
        add("publish_after", result={"publishing": False})
        add("activation_command_before", enabled=False, kwargs={"timeout": 8})
        add("activation_command_after", result={"halted": False})
        add("diagnostic_before", call=1, control_index=None, phase="later_independent_observation")
        add("diagnostic_after", call=1, control_index=None, phase="later_independent_observation", report=native_report())
        add("activate_after", quote=quote)
        namespace = exporter_namespace()
        for index, (reason, missing) in enumerate(CONTROLS):
            call = index + 2
            add("original_offline_fault_before", control_index=index, **namespace["fault_spec"](index))
            add("original_offline_fault_after", control_index=index, missing=missing)
            add("diagnostic_before", call=call, control_index=index, phase="later_independent_observation")
            add("diagnostic_after", call=call, control_index=index, phase="later_independent_observation", report=native_report(reason))
            subtest = {"control_index": index, "expected": reason, "missing": missing, "passed": True,
                       "error_kind": None, "diagnostic_calls": [call]}
            subtests.append(subtest)
            add("original_subtest", **subtest)
    add("original_test_stop", selector=SELECTOR, exact_selected_case=True)
    owned = []
    if not early_fail:
        add("helper_stop_before", birth=model_birth(9500))
        add("helper_reaped", birth=model_birth(9500), wait_pid=9500, wait_status=0)
        add("helper_stop_after", birth=model_birth(9500), normal_exit=True)
        for shard in (0, 1):
            add("owned_worker_terminal", birth=model_birth(9000 + shard), terminal=True, reaped=True)
            owned.append({"role": "financial_worker", "name": "uta-shard-" + str(shard),
                          "birth": model_birth(9000 + shard), "terminal": True, "reaped": True})
        owned.append({"role": "multiprocessing.resource_tracker", "birth": model_birth(9500),
                      "terminal": True, "reaped": True, "wait_status": 0})
    add("case_owned_cleanup_observation", remaining_direct_children=[])
    result = {**trace, "tests_run": 1, "failures": int(early_fail), "errors": 0, "skipped": 0,
        "diagnostic_calls": 0 if early_fail else 5, "controls_reached": len(subtests),
        "controls_passed": len(subtests), "faults_started": len(subtests), "faults_completed": len(subtests),
        "subtests": subtests, "test_events": ["start", "stop"], "technical_unknowns": [],
        "all_original_negative_controls_reached": not early_fail, "test_result": "FAIL" if early_fail else "PASS",
        "source_after_sha256": trace["sources_sha256"], "journal_records": len(rows) + 1}
    result.update(owned_processes=owned, remaining_direct_children=[], helper_cleanup_proven=True)
    add("case_end", **result)
    return rows, result, trace


def exported(rows, result, trace):
    raw = b"".join((json.dumps(row, sort_keys=True) + "\n").encode() for row in rows)
    if len(raw) >= 64 * 1024:
        raise AssertionError("finite memory fixture exceeded64KiB")
    files = {"/raw/native.jsonl": raw, "/raw/case-result.json": json.dumps(result).encode()}
    writes, namespace = {}, exporter_namespace()

    def write(path, value, *, cap):
        if len(json.dumps(value).encode()) > cap:
            raise AssertionError("memory safe-export cap exceeded")
        writes[path.path] = deepcopy(value)

    namespace["write_new_json"] = write
    state = namespace["export_safe"](MemoryPath(files), trace)
    return state, writes["/safe/diagnostics.json"]


def reindex(rows):
    for index, row in enumerate(rows):
        row["sequence"] = index


class FakeBound:
    def __init__(self, pid, *, terminal=False):
        self.birth, self.exited, self.signals = model_birth(pid), terminal, []

    def terminal(self):
        return self.exited

    def verify(self):
        return not self.exited

    def send(self, signum, journal, *, reason):
        self.signals.append((signum, reason))


def case_namespace():
    clock, starts, reads, opens, closes = [0.0], [], [], [], []
    namespace = selected_common(clock=clock)
    journal_rows = []

    def original_identity(pid):
        reads.append(pid)
        return model_birth(pid)

    def original_start(process, *args, **kwargs):
        starts.append(process.pid)
        return "inert_started"

    def open_pidfd(pid, flags):
        opens.append((pid, flags))
        return 44

    def waitpid(pid, options):
        for bound in namespace["helper_archive"]:
            if bound.birth["pid"] == pid:
                bound.exited = True
        return pid, 0

    tracker = SimpleNamespace(_pid=9500, _lock=FakeLock())

    def stop_locked(*, waitpid):
        waitpid(tracker._pid, 0)
        tracker._pid = None

    tracker._stop_locked = stop_locked

    namespace.update(guard_lock=FakeLock(), start_denied=[False], technical_unknowns=[],
        native_deadline=30.0, signal_deadline=40.0, birth=model_birth(8000),
        bound_archive=[], bindings={}, bound_names={}, starting_names=set(), starting_count=[0], runtime_pidfds={},
        helper_archive=[], helper_result={"pid": None, "reaped": False, "status": None},
        sys=SimpleNamespace(modules={"multiprocessing.resource_tracker": SimpleNamespace(_resource_tracker=tracker)}),
        identity=model_birth, children_of=lambda pid: [],
        original_start=original_start, original_identity=original_identity,
        original_os=SimpleNamespace(pidfd_open=open_pidfd, close=lambda fd: closes.append(fd), waitpid=waitpid),
        original_signal=SimpleNamespace(SIGTERM=15, SIGKILL=9), signal=SimpleNamespace(SIGTERM=15, SIGKILL=9),
        BoundChild=lambda pid, **kwargs: FakeBound(pid),
        journal=SimpleNamespace(append=lambda *args, **kwargs: journal_rows.append((args, kwargs))))
    names = {"uncertain", "bind_helper", "stop_helper", "collect_owned_processes", "owned_bound", "runtime_identity",
             "RuntimeOS", "RuntimeSignal", "process_start"}
    outer = next(node for node in TREES["native_case_once.py"].body
                 if isinstance(node, ast.FunctionDef) and node.name == "run_case")
    definitions = [node for node in outer.body if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names]
    if len(definitions) != len(names):
        raise AssertionError("case selected definition inventory changed")
    run_nodes(definitions, namespace, "new-case-guard-selected-AST")
    namespace.update(model_clock=clock, start_spy=starts, identity_spy=reads, open_spy=opens, close_spy=closes)
    return namespace


class TerminalFocusedCases(unittest.TestCase):
    def assert_incomplete(self, rows, result, trace):
        state, _ = exported(rows, result, trace)
        self.assertIs(state["journal_complete"], False)
        self.assertIs(state["pass_evidence_complete"], False)

    def test_complete_manual_session_is_eligible_without_promoting_owner_witness(self):
        rows, result, trace = fixture()
        state, safe = exported(rows, result, trace)
        self.assertTrue(state["journal_complete"])
        self.assertTrue(state["case_result_matches_trace"])
        self.assertTrue(state["pass_evidence_complete"])
        self.assertFalse(state["before_quote_unknown"])
        self.assertEqual(len(safe["diagnostics"]), 5)
        self.assertFalse(safe["diagnostics"][0]["report"]["financial_ready"])
        for mutation in ("wrong_owner_pid", "missing_worker_name", "control_report_does_not_assert_expected", "helper_nonzero_reap", "late_helper"):
            with self.subTest(mutation=mutation):
                altered = deepcopy(rows)
                if mutation == "wrong_owner_pid":
                    next(row for row in altered if row["event"] == "diagnostic_after")["report"]["workers"][0]["pid"] = 9999
                elif mutation == "missing_worker_name":
                    next(row for row in altered if row["event"] == "owned_worker_started")["name"] = "uta-shard-1"
                elif mutation == "control_report_does_not_assert_expected":
                    next(row for row in altered if row["event"] == "diagnostic_after" and row["call"] == 2)["report"]["ready"] = True
                elif mutation == "helper_nonzero_reap":
                    next(row for row in altered if row["event"] == "helper_reaped")["wait_status"] = 9
                else:
                    helper = next(row for row in altered if row["event"] == "owned_helper_started")
                    altered.remove(helper)
                    stop = next(index for index, row in enumerate(altered) if row["event"] == "original_test_stop")
                    altered.insert(stop + 1, helper)
                    reindex(altered)
                    for index, row in enumerate(altered):
                        row["monotonic_ns"] = index + 1
                self.assertFalse(exported(altered, result, trace)[0]["pass_evidence_complete"])

    def test_deleted_whole_diagnostic_pair_cannot_be_complete_against_case_count(self):
        rows, result, trace = fixture()
        rows = [row for row in rows if not (row["event"] in {"diagnostic_before", "diagnostic_after"} and row.get("call") == 2)]
        reindex(rows)
        self.assert_incomplete(rows, result, trace)

    def test_paired_prefix_with_separate_pass_result_is_incomplete(self):
        rows, result, trace = fixture()
        end = next(index for index, row in enumerate(rows) if row["event"] == "diagnostic_after") + 1
        self.assert_incomplete(rows[:end], result, trace)

    def test_duplicate_sequence_and_missing_sequence_are_incomplete(self):
        rows, result, trace = fixture()
        for mutation in ("sequence", "duplicate_call", "foreign_context", "foreign_source"):
            with self.subTest(mutation=mutation):
                altered = deepcopy(rows)
                if mutation == "sequence":
                    altered[4]["sequence"] = altered[2]["sequence"]
                elif mutation == "duplicate_call":
                    next(row for row in altered if row["event"] == "diagnostic_after" and row["call"] == 2)["call"] = 1
                elif mutation == "foreign_context":
                    altered[4]["case_id"] = "0" * 64
                else:
                    altered[0]["source_commit"] = "0" * 40
                self.assert_incomplete(altered, result, trace)

    def test_missing_case_end_is_not_complete(self):
        rows, result, trace = fixture()
        self.assert_incomplete(rows[:-1], result, trace)

    def test_missing_original_subtest_evidence_is_incomplete_even_if_case_passes(self):
        rows, result, trace = fixture()
        for mutation in ("removed", "foreign_control"):
            with self.subTest(mutation=mutation):
                altered = deepcopy(rows)
                target = next(row for row in altered if row["event"] == "original_subtest")
                if mutation == "removed":
                    altered.remove(target)
                else:
                    target["control_index"] = 1
                reindex(altered)
                self.assert_incomplete(altered, result, trace)

    def test_third_live_worker_must_be_denied_before_start_spy(self):
        for name in ("uta-shard-0", "unexpected-worker"):
            with self.subTest(name=name):
                namespace = case_namespace()
                for shard in (0, 1):
                    bound = FakeBound(9000 + shard)
                    namespace["bound_archive"].append(bound)
                    namespace["bound_names"][bound] = "uta-shard-" + str(shard)
                with self.assertRaises(namespace["ScopeUnknown"]):
                    namespace["process_start"](SimpleNamespace(pid=9003, name=name))
                self.assertEqual(namespace["start_spy"], [])
                self.assertTrue(namespace["start_denied"][0])

    def test_top_level_observation_error_is_safely_preserved(self):
        report = native_report("diagnostic_timeout")
        report["observation_error"] = {"type": "service_error", "sqlite_errorcode": 5,
                                       "message": "private-input-must-not-be-exported"}
        safe = exporter_namespace()["safe_report"](report)
        self.assertEqual(safe["observation_error"], {"type": "service_error", "sqlite_errorcode": 5})
        self.assertNotIn("private-input-must-not-be-exported", json.dumps(safe))

    def test_honest_early_assertion_failure_retains_complete_zero_control_fail(self):
        rows, result, trace = fixture(early_fail=True)
        state, safe = exported(rows, result, trace)
        self.assertTrue(state["journal_complete"])
        self.assertTrue(state["case_result_matches_trace"])
        self.assertTrue(state["failure_evidence_complete"])
        self.assertFalse(state["pass_evidence_complete"])
        self.assertEqual((safe["controls_reached"], safe["controls_passed"]), (0, 0))

    def test_sticky_and_inflight_denial_cannot_return_start_permission(self):
        class ProcessStandin:
            # BaseProcess keys have object identity equality/hash and support
            # weak references. Mutable pid/name fields do not define equality.
            def __init__(self, pid, name):
                self.pid, self.name = pid, name

        namespace = case_namespace()
        namespace["start_denied"][0] = True
        with self.assertRaises(namespace["ScopeUnknown"]):
            namespace["process_start"](ProcessStandin(9000, "uta-shard-0"))
        self.assertEqual(namespace["start_spy"], [])
        for mutation in ("swallowed_reentrant_denial", "post_start_name_changed", "post_start_slot_overflow"):
            with self.subTest(mutation=mutation):
                namespace = case_namespace()
                calls = []

                def start(process, *args, **kwargs):
                    calls.append(process.pid)
                    if mutation == "swallowed_reentrant_denial":
                        try:
                            namespace["process_start"](ProcessStandin(9001, process.name))
                        except namespace["ScopeUnknown"]:
                            pass
                    elif mutation == "post_start_name_changed":
                        process.name = "unexpected-worker"
                    else:
                        namespace["bound_archive"].extend([FakeBound(9010), FakeBound(9011)])
                    return "inert_started"

                namespace["original_start"] = start
                with self.assertRaises(namespace["ScopeUnknown"]):
                    namespace["process_start"](ProcessStandin(9000, "uta-shard-0"))
                self.assertEqual(calls, [9000])
                self.assertTrue(namespace["start_denied"][0])
                self.assertEqual(namespace["starting_count"], [0])

    def test_runtime_proxy_denies_unbound_protected_terminal_and_unregistered_signal(self):
        for pid in (310035, 9100):
            with self.subTest(pid=pid):
                namespace = case_namespace()
                for operation in (lambda: namespace["runtime_identity"](pid),
                                  lambda: namespace["RuntimeOS"]().pidfd_open(pid)):
                    with self.assertRaises(namespace["ScopeUnknown"]):
                        operation()
                self.assertEqual(namespace["identity_spy"], [])
                self.assertEqual(namespace["open_spy"], [])
        namespace = case_namespace()
        old = FakeBound(9000, terminal=True)
        namespace["bound_archive"].append(old)
        with self.assertRaises(ProcessLookupError):
            namespace["runtime_identity"](9000)
        self.assertEqual(namespace["identity_spy"], [])
        namespace = case_namespace()
        bound = FakeBound(9000)
        namespace["bound_archive"].append(bound)
        self.assertEqual(namespace["runtime_identity"](9000)["pid"], 9000)
        proxy_os, proxy_signal = namespace["RuntimeOS"](), namespace["RuntimeSignal"]()
        fd = proxy_os.pidfd_open(9000)
        proxy_signal.pidfd_send_signal(fd, 15)
        self.assertEqual(bound.signals, [(15, "original_registered_orphan_recovery")])
        proxy_os.close(fd)
        with self.assertRaises(namespace["ScopeUnknown"]):
            proxy_signal.pidfd_send_signal(fd, 15)
        self.assertEqual(len(bound.signals), 1)
        self.assertEqual(namespace["close_spy"], [44])
        namespace = case_namespace()
        helper = namespace["bind_helper"]()
        self.assertEqual(helper.birth["pid"], 9500)
        self.assertTrue(namespace["stop_helper"]())
        self.assertEqual(namespace["helper_result"], {"pid": 9500, "reaped": True, "status": 0})
        for malformed in ("second_helper", "protected_helper", "helper_reap_not_proven"):
            with self.subTest(helper=malformed):
                namespace = case_namespace()
                if malformed != "protected_helper":
                    namespace["bind_helper"]()
                tracker = namespace["sys"].modules["multiprocessing.resource_tracker"]._resource_tracker
                if malformed == "second_helper":
                    tracker._pid = 9501
                    with self.assertRaises(namespace["ScopeUnknown"]):
                        namespace["bind_helper"]()
                    self.assertEqual(len(namespace["helper_archive"]), 2)
                elif malformed == "protected_helper":
                    tracker._pid = 310035
                    with self.assertRaises(namespace["ScopeUnknown"]):
                        namespace["bind_helper"]()
                    self.assertEqual(namespace["helper_archive"], [])
                else:
                    tracker._stop_locked = lambda **kwargs: None
                    self.assertFalse(namespace["stop_helper"]())
                    self.assertTrue(namespace["start_denied"][0])
        finish = next(node for node in TREES["native_case_once.py"].body
                      if isinstance(node, ast.FunctionDef) and node.name == "finish_case")

        class ImmediateExit(BaseException):
            pass

        for flush_failure in (None, "stdout", "stderr"):
            with self.subTest(finish_flush_failure=flush_failure):
                flushes, exits, late_callbacks = [], [], []

                def flush(name):
                    flushes.append(name)
                    if name == flush_failure:
                        raise OSError("synthetic flush error")

                def immediate_exit(status):
                    exits.append(status)
                    raise ImmediateExit

                namespace = {"sys": SimpleNamespace(stdout=SimpleNamespace(flush=lambda: flush("stdout")),
                                                    stderr=SimpleNamespace(flush=lambda: flush("stderr"))),
                             "os": SimpleNamespace(_exit=immediate_exit)}
                run_nodes([finish], namespace, "new-case-immediate-exit-selected-AST")
                with self.assertRaises(ImmediateExit):
                    namespace["finish_case"](0)
                    late_callbacks.append("unguarded_late_cleanup")
                self.assertEqual(exits, [0 if flush_failure is None else 75])
                self.assertEqual(flushes, ["stdout", "stderr"])
                self.assertEqual(late_callbacks, [])

