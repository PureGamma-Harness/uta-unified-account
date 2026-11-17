"""Registration lifecycle regressions; native cases use fresh synthetic state.

Direct execution defaults to model-only cases. Normal unittest discovery also
includes the explicitly named NativeSpawnRegistrationTests for release QA.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import select
import sqlite3
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from uta import durable_process as runtime
from uta.durable_process import DurableProcessRouter
from uta.writer_fence import WriterFence


class _Wire:
    def __init__(self):
        self.messages = []


class _Connection:
    def __init__(self, wire):
        self.wire, self.closed = wire, False

    def send_bytes(self, value):
        self.wire.messages.append(value)

    def recv_bytes(self):
        return self.wire.messages.pop(0)

    def poll(self, timeout=0):
        return bool(self.wire.messages)

    def close(self):
        self.closed = True


class _Process:
    def __init__(self, context, args):
        self.context, self.args = context, args
        self.pid, self.alive, self.closed = None, False, False

    def start(self):
        self.pid = 900_000 + len(self.context.processes)
        self.alive = True

    def is_alive(self):
        return self.alive

    def join(self, timeout=None):
        if not self.alive:
            return
        if not self.context.stuck and self.args[3].is_set():
            self.alive = False

    def kill(self):
        if not self.context.stuck:
            self.alive = False

    def close(self):
        if self.alive:
            raise ValueError("cannot close running model process")
        self.closed = True


class _Context:
    def __init__(self, *, stuck=False):
        self.pipes, self.processes, self.stuck = [], [], stuck

    def Pipe(self, duplex=False):
        wire = _Wire()
        pair = (_Connection(wire), _Connection(wire))
        self.pipes.append(pair)
        return pair

    def Process(self, *, target, args, name):
        result = _Process(self, args)
        self.processes.append(result)
        return result


def _model_router(context):
    router = DurableProcessRouter.__new__(DurableProcessRouter)
    router.directory = Path("/synthetic-model-not-created")
    router._context, router._settings = context, {}
    router._control, router._coordinator = SimpleNamespace(), "model-coordinator"
    router._workers, router._start_gates, router._reports = {}, {}, {}
    router._spawn_retry_at, router._spawn_failures, router._spawn_blocked = {}, {}, set()
    from threading import RLock
    router._mutex = RLock()
    router._database = lambda shard: SimpleNamespace(timeout=10)
    return router


class SpawnRegistrationUnitTests(unittest.TestCase):
    """No SQLite connections, process creation, signals or sleeps."""
    def run_failure(self, *, stuck=False, append_first=False, message="locking protocol"):
        context = _Context(stuck=stuck)
        router = _model_router(context)
        records = []
        def record(*args):
            if append_first:
                records.append(sha256(args[3].encode()).hexdigest())
            raise sqlite3.OperationalError(message)
        with patch.object(runtime, "_record_process", record), patch.object(
                runtime, "_process_identity", lambda pid: {"pid": pid}):
            with self.assertRaises(Exception) as caught:
                router._spawn(0)
        return router, context, records, caught.exception

    def test_registration_failure_never_releases_gate_and_reaps_its_model_child(self):
        router, context, _, error = self.run_failure()
        process = context.processes[0]
        self.assertFalse(process.alive)
        self.assertTrue(process.closed)
        self.assertEqual(context.pipes[1][0].wire.messages, [])
        self.assertEqual(router._workers, {})
        self.assertEqual(router._start_gates, {})
        self.assertEqual(getattr(error, "code", None), "worker_registration_failed")
        self.assertEqual(router._spawn_failures[0]["registration_outcome"], "UNKNOWN")
        self.assertTrue(router._spawn_failures[0]["cleanup_complete"])

    def test_modeled_append_then_lost_reply_is_retained_and_not_replayed(self):
        router, context, records, _ = self.run_failure(append_first=True)
        self.assertEqual(len(records), 1)  # Model append, not a claimed real COMMIT.
        self.assertFalse(context.processes[0].alive)
        self.assertEqual(context.pipes[1][0].wire.messages, [])
        self.assertEqual(router._spawn_failures[0]["registration_outcome"], "UNKNOWN")
        with patch.object(runtime, "_record_process", lambda *args: records.append(
                sha256(args[3].encode()).hexdigest())), patch.object(
                runtime, "_process_identity", lambda pid: {"pid": pid}):
            router._spawn(0)
        self.assertEqual(len(records), 2)
        self.assertEqual(len(set(records)), 2)
        self.assertTrue(router._spawn_failures[0]["recovered"])
        self.assertNotEqual(context.processes[0].pid, context.processes[1].pid)

    def test_unconfirmed_model_cleanup_blocks_new_children(self):
        router, context, _, _ = self.run_failure(stuck=True)
        self.assertTrue(context.processes[0].alive)
        self.assertIn(0, router._spawn_blocked)
        self.assertNotIn(0, router._spawn_retry_at)
        self.assertFalse(router._spawn_failures[0]["cleanup_complete"])
        self.assertFalse(router._spawn_failures[0]["retryable_new_child"])

    def test_unknown_error_is_not_retried_or_exposed(self):
        secret = "private path or nonce must never become a diagnostic"
        router, _, _, _ = self.run_failure(message=secret)
        self.assertIn(0, router._spawn_blocked)
        self.assertNotIn(secret, json.dumps(router._spawn_failures))
        self.assertFalse(router._spawn_failures[0]["retryable_new_child"])

    def test_monitor_survives_one_modeled_registry_failure_and_creates_new_identity(self):
        context, clock = _Context(), SimpleNamespace(now=0.0)
        router = _model_router(context)
        calls = []
        def record(*args):
            calls.append(sha256(args[3].encode()).hexdigest())
            if len(calls) == 1:
                raise sqlite3.OperationalError("locking protocol")
        class Stop:
            turns = 0
            def wait(self, timeout):
                self.turns += 1
                clock.now = self.turns / 10
                return self.turns > 2
            def is_set(self):
                return False
        router._stop = Stop()
        # An already exited model child exercises the actual monitor branch.
        dead = _Process(context, (None,) * 9)
        dead.pid = 899_999
        router._workers[0] = (dead, SimpleNamespace(close=lambda: None), _Connection(_Wire()))
        router._start_gates[0] = SimpleNamespace(close=lambda: None)
        with patch.object(runtime, "monotonic", lambda: clock.now), patch.object(
                runtime, "_process_identity", lambda pid: {"pid": pid}), patch.object(
                runtime, "_record_process", record), patch.object(runtime, "WriterFence", lambda db:
                    SimpleNamespace(status=lambda: {"owner_pid": context.processes[-1].pid, "active": True})):
            router._supervise()
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(set(calls)), 2)
        self.assertEqual(len(context.processes), 2)
        self.assertFalse(context.processes[0].alive)
        self.assertTrue(context.processes[1].alive)
        self.assertTrue(router._spawn_failures[0]["recovered"])


class NativeSpawnRegistrationTests(unittest.TestCase):
    """Fresh one-shard synthetic authorities; requires separate native-test GO."""
    def setUp(self):
        self.tmp = TemporaryDirectory(prefix="uta-registration-recovery-")
        self.addCleanup(self.tmp.cleanup)
        self.router = DurableProcessRouter.initialize(Path(self.tmp.name) / "managed", 1,
            {"USD": 2}, managed=True, lease_seconds=.6, poll_interval=.01, background_interval=.03)
        self.addCleanup(self.router.close)
        self.pidfds = []
        self.addCleanup(lambda: [os.close(fd) for fd in self.pidfds])

    def pin_new(self, identity):
        fd = os.pidfd_open(identity["pid"])
        self.pidfds.append(fd)
        current = runtime._process_identity(identity["pid"])
        self.assertTrue(all(current[k] == identity[k] for k in ("pid", "start_ticks", "boot_id", "uid")))
        return fd

    def reaped(self, fd):
        poll = select.poll()
        poll.register(fd, select.POLLIN)
        self.assertTrue(poll.poll(1000), "new gated child did not exit")

    def rows(self):
        with self.router._control.control.read_transaction() as connection:
            return [tuple(row) for row in connection.execute(
                "SELECT kind,pid,generation FROM router_process_owners ORDER BY sequence")]

    def test_failure_before_registry_insert_cleans_actual_gated_child(self):
        original, captured = runtime._record_process, []
        def fail(control, kind, shard, nonce, generation, identity, coordinator):
            if kind == "SPAWNED":
                captured.append((identity["pid"], self.pin_new(identity)))
                raise sqlite3.OperationalError("locking protocol")
            return original(control, kind, shard, nonce, generation, identity, coordinator)
        with patch.object(runtime, "_record_process", fail), self.assertRaises(Exception) as caught:
            self.router.start()
        self.assertEqual(getattr(caught.exception, "code", None), "worker_registration_failed")
        self.assertEqual(len(captured), 1)
        self.reaped(captured[0][1])
        self.assertFalse(any(kind == "SPAWNED" for kind, _, _ in self.rows()))
        self.assertEqual(WriterFence(self.router._database(0)).status()["generation"], 0)
        self.assertEqual(self.router._workers, {})

    def test_registry_commit_then_reply_loss_retains_original_audit_and_no_child_token(self):
        original, captured = runtime._record_process, []
        def lose(control, kind, shard, nonce, generation, identity, coordinator):
            original(control, kind, shard, nonce, generation, identity, coordinator)
            if kind == "SPAWNED":
                captured.append((identity["pid"], self.pin_new(identity)))
                raise sqlite3.OperationalError("locking protocol")  # Fault AFTER actual COMMIT.
        with patch.object(runtime, "_record_process", lose), self.assertRaises(Exception) as caught:
            self.router.start()
        self.assertEqual(getattr(caught.exception, "code", None), "worker_registration_failed")
        self.assertEqual(len(captured), 1)
        self.reaped(captured[0][1])
        self.assertEqual([row for row in self.rows() if row[0] == "SPAWNED"],
                         [("SPAWNED", captured[0][0], 0)])
        lease = WriterFence(self.router._database(0)).status()
        self.assertEqual(lease["generation"], 0)
        self.assertFalse(lease["active"])
        self.assertEqual(self.router._spawn_failures[0]["registration_outcome"], "UNKNOWN")

    def test_monitor_recovery_after_actual_registry_commit_and_lost_reply(self):
        from time import monotonic, sleep
        self.router.start()
        def ready_within(timeout, excluded=()):
            deadline = monotonic() + timeout
            while monotonic() < deadline:
                with self.router._mutex:
                    report = dict(self.router._reports.get(0, {}))
                    process = self.router._workers.get(0, (None,))[0]
                    if (process is not None and process.is_alive() and report.get("state") == "ready"
                            and report.get("pid") == process.pid and process.pid not in excluded):
                        return process.pid
                sleep(.01)
            self.fail("native registration recovery did not reach actual READY within unchanged 4s")
        first = ready_within(4)
        original, failed = runtime._record_process, []
        def lose_once(control, kind, shard, nonce, generation, identity, coordinator):
            original(control, kind, shard, nonce, generation, identity, coordinator)
            if kind == "SPAWNED" and not failed:
                failed.append((identity["pid"], self.pin_new(identity)))
                raise sqlite3.OperationalError("locking protocol")  # Confirmed real registry row exists.
        with patch.object(runtime, "_record_process", lose_once):
            self.router.terminate_worker(0)  # Only this fresh router's own unreaped child.
            current = ready_within(4, (first,))
        self.assertEqual(len(failed), 1)
        self.reaped(failed[0][1])
        self.assertNotIn(current, (first, failed[0][0]))
        self.assertTrue(self.router._monitor.is_alive())
        self.assertTrue(self.router._spawn_failures[0]["recovered"])
        self.assertEqual(len([r for r in self.rows() if r[0] == "SPAWNED"]), 3)
        lease = WriterFence(self.router._database(0)).status()
        self.assertEqual((lease["owner_pid"], lease["generation"]), (current, 2))


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SpawnRegistrationUnitTests)
    if "--include-native" in sys.argv:
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(NativeSpawnRegistrationTests))
    if "--include-native" in sys.argv:
        passed = unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful()
    else:
        # Make accidental SQL/process/signal activity a failing pure model.
        with patch.object(sqlite3, "connect", side_effect=AssertionError("model attempted SQL")), \
                patch.object(runtime.multiprocessing.process.BaseProcess, "start",
                             side_effect=AssertionError("model attempted process start")), \
                patch.object(os, "kill", side_effect=AssertionError("model attempted signal")):
            passed = unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful()
    raise SystemExit(not passed)
