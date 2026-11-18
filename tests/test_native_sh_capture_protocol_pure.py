"""CODE candidate only; run solely after a separate bounded pure-test GO.

No actual trace, worker, PID access, SQLite connection, flock or signal occurs.
Fake SH state and virtual time are assumptions, never kernel recovery evidence.
"""
import ast
from contextlib import contextmanager
import hashlib
import itertools
import json
from pathlib import Path
from types import CodeType, FunctionType, SimpleNamespace
import unittest
from unittest.mock import patch

import native_sh_capture_fixture as fixture


ROOT = Path(__file__).resolve().parents[1]
OWNER = {"pid": 900001, "start_ticks": 7, "boot_id": "model-boot", "uid": 1000, "generation": 3}


class Wire:
    def __init__(self, messages, events):
        self.messages = [json.dumps(message).encode() for message in messages]
        self.sent, self.events = [], events

    def poll(self, timeout=0):
        self.events.append(("poll", timeout))
        return bool(self.messages)

    def recv_bytes(self, maximum):
        value = self.messages.pop(0)
        if len(value) > maximum:
            raise OSError("modeled message bound")
        return value

    def send_bytes(self, value):
        message = json.loads(value)
        self.sent.append(message)
        self.events.append(("send", message["kind"]))

    def close(self):
        self.events.append(("wire", "closed"))


class NativeSHCaptureProtocolPureTests(unittest.TestCase):
    def test_all_twenty_four_protocol_orders_and_changed_binding_reject(self):
        accepted = []
        for order in itertools.permutations(("ARM", "ENTERED", "RELEASE", "ABORT")):
            protocol = fixture.Protocol()
            try:
                for kind in order:
                    if kind == "ARM":
                        protocol.arm(fixture.packet(kind, OWNER, 5))
                    elif kind == "ENTERED":
                        protocol.entered(OWNER)
                    elif kind == "RELEASE":
                        protocol.release(fixture.packet(kind, OWNER, 5))
                    else:
                        protocol.abort(fixture.packet(kind, OWNER, 5))
            except fixture.CaptureFixtureError:
                continue
            accepted.append(order)
        self.assertEqual(accepted, [("ARM", "ENTERED", "RELEASE", "ABORT")])
        for field in ("pid", "start_ticks", "uid", "generation"):
            protocol = fixture.Protocol()
            protocol.arm(fixture.packet("ARM", OWNER, 5))
            changed = dict(OWNER, **{field: OWNER[field] + 1})
            with self.assertRaises(fixture.CaptureFixtureError):
                protocol.entered(changed)
            with self.assertRaises(fixture.CaptureFixtureError):
                protocol.arm(fixture.packet("ARM", OWNER, 5))

    def test_actual_boundary_wait_owns_fake_sh_then_releases_before_ack(self):
        events, state = [], {"held": False}
        @contextmanager
        def gate(**options):
            self.assertEqual(options, {"timeout": 5})
            state["held"] = True
            events.append(("gate", "enter"))
            try:
                yield
            finally:
                state["held"] = False
                events.append(("gate", "exit"))
        wire = Wire([fixture.packet(kind, OWNER, 5) for kind in ("ARM", "RELEASE", "ABORT")], events)
        original_send = wire.send_bytes
        def send(value):
            kind = json.loads(value)["kind"]
            self.assertEqual(state["held"], kind == "ENTERED")
            original_send(value)
        wire.send_bytes = send
        view = SimpleNamespace(shard=0, _control=SimpleNamespace(_lock=gate),
            database=SimpleNamespace(writer_token=SimpleNamespace(generation=3, process_id=900001)))
        protocol = fixture.Protocol()
        with self.assertRaisesRegex(fixture.CaptureFixtureError, "original SQL is forbidden"):
            fixture.hold_at_boundary(view, wire, protocol, lambda: OWNER,
                                     clean_threads=lambda: True, clock=lambda: 0)
        self.assertEqual(protocol.state, "CLOSED")
        self.assertEqual([message["kind"] for message in wire.sent], ["ENTERED", "RELEASED"])
        self.assertLess(events.index(("gate", "exit")), events.index(("send", "RELEASED")))
        self.assertFalse(state["held"])

    def test_mismatch_keeper_or_wrong_role_never_enters_gate(self):
        for shard, clean, pid in ((1, True, 900001), (0, False, 900001), (0, True, 900002)):
            view = SimpleNamespace(shard=shard,
                _control=SimpleNamespace(_lock=lambda **kw: self.fail("entered gate after failed role")),
                database=SimpleNamespace(writer_token=SimpleNamespace(generation=3, process_id=pid)))
            wire = Wire([fixture.packet("ARM", OWNER, 5)], [])
            with self.assertRaises(fixture.CaptureFixtureError):
                fixture.hold_at_boundary(view, wire, fixture.Protocol(), lambda: OWNER,
                                         clean_threads=lambda: clean, clock=lambda: 0)
            self.assertEqual(wire.sent, [])

    def test_exact_original_source_codeobject_and_unique_callsite_required(self):
        source = (ROOT / "uta/durable_process.py").read_bytes()
        self.assertEqual(fixture.RUNTIME_BINDING_REVISION, 2)
        self.assertEqual(hashlib.sha256(source).hexdigest(), fixture.RUNTIME_SHA256)
        self.assertNotEqual(fixture.RUNTIME_SHA256, fixture.PREVIOUS_RUNTIME_SHA256)
        code = compile(source, str(ROOT / "uta/durable_process.py"), "exec", dont_inherit=True)
        original = next(value for value in code.co_consts if isinstance(value, CodeType)
                        and value.co_name == "_run_worker")
        worker = FunctionType(original, {})  # Construct code only; never invoke.
        line = fixture.exact_worker_boundary(worker, source)
        tree = ast.parse(source)
        self.assertTrue(any(isinstance(node, ast.Call) and node.lineno == line
                            and isinstance(node.func, ast.Attribute) and node.func.attr == "process_one"
                            for node in ast.walk(tree)))
        with self.assertRaises(fixture.CaptureFixtureError):
            fixture.exact_worker_boundary(lambda: None, source)
        with self.assertRaises(fixture.CaptureFixtureError):
            fixture.exact_worker_boundary(worker, source + b"\n")

    def test_private_wire_rejects_extra_fields_bad_types_and_oversize(self):
        valid = fixture.packet("ARM", OWNER, 5)
        mutations = [dict(valid, extra=True), dict(valid, version=True), dict(valid, kind="READY"),
                     dict(valid, binding=dict(OWNER, generation=True))]
        for value in mutations:
            with self.assertRaises((fixture.CaptureFixtureError, OSError)):
                fixture.receive(Wire([value], []), timeout=0)
        with self.assertRaises(fixture.CaptureFixtureError):
            fixture.send(Wire([], []), {"padding": "x" * 3000})

    def test_context_changes_only_initial_target_and_never_worker_code(self):
        calls = []
        def worker(*args):
            self.fail("model target must not execute")
        worker.__module__, worker.__name__ = "uta.durable_process", "_run_worker"
        original_code = worker.__code__
        real = SimpleNamespace(Process=lambda **values: calls.append(values))
        channel = object()
        context = fixture.CaptureContext(real, channel)
        context.Process(target=worker, args=("model", 0, {}), name="first")
        context.Process(target=worker, args=("model", 1, {}), name="sibling")
        context.Process(target=worker, args=("model", 0, {}), name="replacement")
        self.assertIs(calls[0]["target"], fixture.capture_worker)
        self.assertIs(calls[0]["args"][-1], channel)
        self.assertIs(calls[1]["target"], worker)
        self.assertIs(calls[2]["target"], worker)
        self.assertIs(worker.__code__, original_code)
        with self.assertRaises(fixture.CaptureFixtureError):
            fixture.NativeSHCapture(SimpleNamespace())  # Default is OFF.

    def test_parent_release_and_close_are_one_shot_without_duplicate_messages(self):
        profile = fixture.NativeSHCapture.__new__(fixture.NativeSHCapture)
        profile.parent, profile.child = Wire([], []), Wire([], [])
        profile.context, profile.real_context = object(), object()
        profile.router = SimpleNamespace(_context=profile.context)
        profile.owner, profile.deadline, profile.acknowledged = OWNER, 5, True
        profile.closed, profile.release_sent = False, False
        profile.release(OWNER, 3)
        with self.assertRaises(fixture.CaptureFixtureError):
            profile.release(OWNER, 3)
        profile.close()
        profile.close()
        self.assertEqual([message["kind"] for message in profile.parent.sent], ["RELEASE", "ABORT"])
        self.assertIs(profile.router._context, profile.real_context)

    def test_capture_failure_is_one_shot_and_original_recovery_ast_is_untouched(self):
        source = (ROOT / "tests/test_durable_faults.py").read_text()
        tree = ast.parse(source)
        method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == fixture.CASE)
        refusals = [node for node in ast.walk(method) if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute) and node.func.attr == "fail"
                    and node.args and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value == "one-shot deterministic capture rejected native preconditions; no recapture"]
        self.assertEqual(len(refusals), 1)
        # The complete-module guard still uses the unchanged original reference;
        # one explicitly hashed ordinary-case delta permits the reviewed pending
        # oracle while every recovery/capture/cleanup node remains protected.
        audit_source = (ROOT / "tests/test_expired_gate_failure_evidence.py").read_text()
        audit_tree = ast.parse(audit_source)
        helpers = [node for node in audit_tree.body if isinstance(node, ast.FunctionDef)
                   and node.name in {"canonical", "ast_sha"}]
        audit_owner = next(node for node in audit_tree.body if isinstance(node, ast.ClassDef)
                           and node.name == "FailureDiagnosticTests")
        audit_method = next(node for node in audit_owner.body if isinstance(node, ast.FunctionDef)
                            and node.name == "test_complete_original_ast_is_preserved_except_exact_failure_hook")
        actual = ast.ClassDef(name="ActualASTGuard", bases=[ast.Attribute(value=ast.Name(id="unittest", ctx=ast.Load()),
            attr="TestCase", ctx=ast.Load())], keywords=[], body=[audit_method], decorator_list=[])
        namespace = {"ast": ast, "json": json, "hashlib": hashlib, "unittest": unittest,
                     "ROOT": ROOT, "METHOD": fixture.CASE}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[*helpers, actual], type_ignores=[])),
                     "<actual-existing-original-AST-guard>", "exec"), namespace)
        namespace["ActualASTGuard"]().test_complete_original_ast_is_preserved_except_exact_failure_hook()
        fixture_tree = ast.parse((ROOT / "tests/native_sh_capture_fixture.py").read_text())
        self.assertFalse(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                             and node.func.id in {"setattr", "patch"} for node in ast.walk(fixture_tree)))


if __name__ == "__main__":
    # A future separately authorized run must select this file, not native
    # unittest discovery. Fail immediately on any accidental native capability.
    import fcntl
    import multiprocessing.process
    import os
    import signal
    import sqlite3
    import threading
    import time
    from contextlib import ExitStack
    def forbidden(*args, **kwargs):
        raise AssertionError("pure protocol attempted native capability")
    with ExitStack() as guards:
        for owner, name in ((sqlite3, "connect"), (multiprocessing.process.BaseProcess, "start"),
                            (os, "kill"), (os, "waitpid"), (fcntl, "flock"),
                            (threading.Thread, "start"), (time, "sleep"), (fixture.sys, "settrace")):
            guards.enter_context(patch.object(owner, name, forbidden))
        for owner, name in ((os, "pidfd_open"), (signal, "pidfd_send_signal")):
            if hasattr(owner, name):
                guards.enter_context(patch.object(owner, name, forbidden))
        unittest.main()
