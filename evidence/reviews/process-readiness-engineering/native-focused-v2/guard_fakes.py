"""Nine guard properties; keeps the original six counterexample expectations."""
import ast
from types import SimpleNamespace
import unittest

from fake_support import (TREES, FakeLock, FakeWrites, ProbePath, native_run_tree,
                          run_nodes, selected_common, selected_drain)


class GuardFocusedCases(unittest.TestCase):
    def test_existing_protected_pid_rejects_before_any_proc_read(self):
        namespace = selected_common()
        ProbePath.reads = []
        with self.assertRaises(namespace["ScopeUnknown"]):
            namespace["identity"](4471)
        self.assertEqual(ProbePath.reads, [])

    def test_current_required_protected_pids_reject_before_proc_or_pidfd(self):
        opened = []
        namespace = selected_common(fake_os=SimpleNamespace(pidfd_open=lambda pid: opened.append(pid)))
        required = {4471, 8784, 122905, 122907, 123007, 123009, 310035, 310039, 310266, 310269}
        self.assertEqual(namespace["PROTECTED_PIDS"], required)
        for pid in sorted(required):
            for operation in (lambda: namespace["identity"](pid),
                              lambda: namespace["children_of"](pid),
                              lambda: namespace["BoundChild"](pid, session=900, signal_deadline=40)):
                ProbePath.reads = []
                with self.assertRaises(namespace["ScopeUnknown"]):
                    operation()
                self.assertEqual(ProbePath.reads, [])
        self.assertEqual(opened, [])
        task_reads = []
        class ProtectedTask:
            name = "310035"
            def __truediv__(self, value):
                return self
            def read_text(self):
                task_reads.append("protected-thread-children")
                return ""
        class OwnThreadDirectory:
            def __init__(self, value):
                pass
            def __truediv__(self, value):
                return self
            def iterdir(self):
                return [ProtectedTask()]
        namespace["Path"] = OwnThreadDirectory
        with self.assertRaises(namespace["ScopeUnknown"]):
            namespace["children_of"](999)
        self.assertEqual(task_reads, [])

    def test_outer_signal_subtree_denies_observed_elapsed_after_40s(self):
        calls, clock = [], [40.01]
        namespace = selected_common(clock=clock)
        namespace.update(live=[901], tracked={901: SimpleNamespace(send=lambda *a, **k: calls.append((a, k)))},
            stop=True, elapsed=40.01, signal_deadline=40.0, term_sent=set(), kill_sent=set(),
            journal=SimpleNamespace(append=lambda *a, **k: None),
            signal=SimpleNamespace(SIGTERM=15, SIGKILL=9), unknown=lambda *a, **k: None)
        loops = sorted((node for node in ast.walk(native_run_tree()) if isinstance(node, ast.For)
            and isinstance(node.target, ast.Name) and node.target.id == "pid"
            and isinstance(node.iter, ast.Name) and node.iter.id == "live"), key=lambda node: node.lineno)
        for loop in loops:
            for term_already_attempted in (False, True):
                namespace["term_sent"] = {901} if term_already_attempted else set()
                namespace["kill_sent"], namespace["started"] = set(), 0.0
                run_nodes([loop], namespace, "new-native-outer-signal-subtree")
        self.assertEqual(calls, [])

    def test_signal_guard_rechecks_deadline_after_before_record_fsync(self):
        clock, calls = [39.99], []
        namespace = selected_common(clock=clock, fake_signal=SimpleNamespace(
            pidfd_send_signal=lambda *args: calls.append(args)))
        bound = namespace["BoundChild"].__new__(namespace["BoundChild"])
        bound.fd, bound.birth, bound.sent, bound.signal_deadline = 778, {"pid": 902}, set(), 40.0
        bound.verify = lambda: True
        def append(event, **values):
            if event == "signal_before":
                clock[0] = 40.02
        with self.assertRaises(namespace["ScopeUnknown"]):
            bound.send(15, SimpleNamespace(append=append), reason="synthetic_late_fsync")
        self.assertEqual(calls, [])
        self.assertIn(15, bound.sent)

    def test_journal_cap_counts_successful_write_when_fsync_fails(self):
        writer = FakeWrites()
        namespace = selected_common(fake_os=writer)
        journal = namespace["Journal"].__new__(namespace["Journal"])
        journal.fd, journal.context, journal.failed, journal.lock = 11, {}, False, FakeLock()
        journal.size, journal.sequence = 0, 0
        journal.cap = len(namespace["encode"]({"sequence": 0, "event": "synthetic", "monotonic_ns": 0}))
        with self.assertRaises(OSError):
            journal.append("synthetic")
        with self.assertRaises(namespace["ScopeUnknown"]):
            journal.append("synthetic")
        self.assertLessEqual(writer.bytes, journal.cap)
        self.assertEqual(journal.size, journal.cap)
        self.assertTrue(journal.failed)

    def test_stdio_cap_counts_successful_write_when_fsync_fails(self):
        namespace = selected_common()
        cap = namespace["STDIO_CAP"]
        writer = FakeWrites(initial=cap - 64)
        stream = SimpleNamespace(fileno=lambda: 99)
        key = SimpleNamespace(fileobj=stream, data="stdout")
        namespace.update(os=writer, selector=SimpleNamespace(select=lambda timeout: [(key, None)]),
            output_fds={"stdout": 12}, unknown=lambda *a, **k: None)
        drain, snapshot = selected_drain(namespace, initial=cap - 64)
        with self.assertRaises(OSError):
            drain()
        with self.assertRaises(namespace["ScopeUnknown"]):
            drain()
        self.assertLessEqual(writer.bytes, cap)
        self.assertEqual(snapshot()[:2], (cap, True))

    def test_late_popen_and_gate_boundaries_do_not_start_or_release(self):
        clock, calls = [30.01], []
        namespace = selected_common(clock=clock)
        block = next(node for node in native_run_tree().body if isinstance(node, ast.Try))
        popen = next(index for index, node in enumerate(block.body) if isinstance(node, ast.Assign)
            and any(isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                    and call.func.attr == "Popen" for call in ast.walk(node)))
        namespace.update(native_deadline=30.0, command=[], SOURCE="inert-source", gate_read=7,
            subprocess=SimpleNamespace(Popen=lambda *a, **k: calls.append("Popen"), DEVNULL=-1, PIPE=-1))
        with self.assertRaises(namespace["ScopeUnknown"]):
            run_nodes(block.body[popen - 1:popen + 1], namespace, "new-native-Popen-boundary")
        self.assertEqual(calls, [])
        gate = next(index for index, node in enumerate(block.body)
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute) and node.value.func.attr == "write")
        clock[0] = 29.99
        def append(*args, **kwargs):
            clock[0] = 30.01
        namespace.update(leader=SimpleNamespace(birth={"pid": 903}), journal=SimpleNamespace(append=append),
            gate_write=8, os=SimpleNamespace(write=lambda *a: calls.append("gate")))
        with self.assertRaises(namespace["ScopeUnknown"]):
            run_nodes(block.body[gate - 2:gate + 1], namespace, "new-native-gate-boundary")
        self.assertEqual(calls, [])

    def test_partial_write_and_eof_error_latch_without_more_bytes(self):
        writer = FakeWrites(partial=True)
        namespace = selected_common(fake_os=writer)
        journal = namespace["Journal"].__new__(namespace["Journal"])
        journal.fd, journal.context, journal.failed, journal.lock = 11, {}, False, FakeLock()
        journal.size, journal.sequence = 0, 0
        journal.cap = len(namespace["encode"]({"sequence": 0, "event": "synthetic", "monotonic_ns": 0}))
        with self.assertRaises(OSError):
            journal.append("synthetic")
        written = writer.bytes
        with self.assertRaises(namespace["ScopeUnknown"]):
            journal.append("synthetic")
        self.assertEqual(writer.bytes, written)
        self.assertLessEqual(written, journal.cap)
        def close_error():
            raise OSError("synthetic EOF close failure")
        namespace = selected_common()
        eof_writer = FakeWrites(chunk=b"")
        stream = SimpleNamespace(fileno=lambda: 99, close=close_error)
        key = SimpleNamespace(fileobj=stream, data="stdout")
        namespace.update(os=eof_writer, selector=SimpleNamespace(select=lambda timeout: [(key, None)],
            unregister=lambda fileobj: None), output_fds={"stdout": 12}, unknown=lambda *a, **k: None)
        drain, snapshot = selected_drain(namespace, initial=0)
        with self.assertRaises(OSError):
            drain()
        with self.assertRaises(namespace["ScopeUnknown"]):
            drain()
        self.assertEqual(snapshot()[:2], (0, True))
        self.assertEqual(eof_writer.bytes, 0)

    def test_case_conclusion_and_actual_exit_must_agree(self):
        branch = next(node for node in ast.walk(native_run_tree()) if isinstance(node, ast.If)
            and any(isinstance(value, ast.Constant)
                    and value.value == "case_pass_claim_not_closed_by_first_raw_and_exit"
                    for value in ast.walk(node)))
        for conclusion, exit_status, unknown_expected in (
            ("FAIL", -9, True), ("FAIL", 0, True), ("FAIL", 1, False),
            ("PASS", 1, True), ("PASS", 0, False), ("UNKNOWN", 75, True)):
            with self.subTest(conclusion=conclusion, exit_status=exit_status):
                unknowns = []
                namespace = {"case_result": {"test_result": conclusion},
                    "process": SimpleNamespace(returncode=exit_status),
                    "safe_state": {"failure_evidence_complete": True, "pass_evidence_complete": True},
                    "unknown": lambda value: unknowns.append(value)}
                run_nodes([branch], namespace, "new-native-case-exit-binding")
                self.assertEqual(bool(unknowns), unknown_expected)
        namespace = selected_common()
        roles = next(node for node in TREES["native_once.py"].body
                     if isinstance(node, ast.FunctionDef) and node.name == "reconcile_owned_roles")
        run_nodes([roles], namespace, "new-native-owned-role-binding")
        leader = {"pid": 8000, "start_ticks": 1, "boot_id": "synthetic-boot", "uid": 1000,
                  "session": 8000, "ppid": 7000}
        owned = [{"role": "financial_worker", "name": "uta-shard-" + str(shard),
                  "birth": {**leader, "pid": 9000 + shard, "ppid": 8000, "start_ticks": 2 + shard},
                  "terminal": True, "reaped": True} for shard in (0, 1)]
        owned.append({"role": "multiprocessing.resource_tracker",
            "birth": {**leader, "pid": 8900, "ppid": 8000, "start_ticks": 4},
            "terminal": True, "reaped": True, "wait_status": 0})
        result = {"owned_processes": owned, "remaining_direct_children": [], "helper_cleanup_proven": True}
        observed = [leader, owned[0]["birth"], owned[2]["birth"]]
        self.assertTrue(namespace["reconcile_owned_roles"](result, leader, observed))
        self.assertFalse(namespace["reconcile_owned_roles"](result, leader,
            [*observed, {**leader, "pid": 9900, "ppid": 8000, "start_ticks": 5}]))
        owned[-1]["wait_status"] = 9
        self.assertFalse(namespace["reconcile_owned_roles"](result, leader, observed))
