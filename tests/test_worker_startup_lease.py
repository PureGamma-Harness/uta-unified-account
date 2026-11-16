"""A real spawn owner whose valid initialization consumes most of its lease."""
import multiprocessing
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic, sleep, CLOCK_BOOTTIME, clock_gettime_ns
import unittest

from uta.durable_process import DurableProcessRouter
from uta.writer_fence import WriterFence


def _delayed_owner(directory, settings, stop, ready, parent_pid, gate, expire=False):
    import uta.durable_process as runtime
    original = runtime.ShardWorkerView
    class DelayedView(original):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # Only this test child is delayed. Production has no test hooks.
            state = WriterFence(self._exchange.database).status()
            remaining = (state["expires_ns"] - clock_gettime_ns(CLOCK_BOOTTIME)) / 1e9
            sleep(max(0, remaining + .02 if expire else remaining - settings["lease_seconds"] / 8))
    runtime.ShardWorkerView = DelayedView
    try:
        runtime._run_worker(directory, 0, settings, stop, ready, parent_pid, gate,
                            "delayed-startup-owner", "startup-regression")
    finally:
        runtime.ShardWorkerView = original


class StartupLeaseTests(unittest.TestCase):
    def test_initialization_near_expiry_renews_before_ready_and_executes_commands(self):
        with TemporaryDirectory() as temporary:
            directory = Path(temporary) / "managed"
            router = DurableProcessRouter.initialize(directory, 1, {"USD": 2}, managed=True,
                lease_seconds=.6, poll_interval=.01, background_interval=1)
            context = multiprocessing.get_context("spawn")
            receive, send = context.Pipe(duplex=False)
            stop, gate = context.Event(), context.Event()
            with router._control.control.transaction() as connection:
                from uta.durable_process import _registry_schema
                _registry_schema(connection)
            child = context.Process(target=_delayed_owner,
                args=(str(directory), router._settings, stop, send, os.getpid(), gate))
            child.start()
            send.close()
            gate.set()
            try:
                self.assertTrue(receive.poll(5), "worker did not finish bounded delayed startup")
                ready = receive.recv()
                self.assertEqual(ready["state"], "ready", ready)
                state = WriterFence(router._database(0)).status()
                remaining_at_ready = (state["expires_ns"] - state["now_ns"]) / 1e9
                # Old scheduling waited another TTL/3 after startup and expired
                # first. Do not enlarge the configured TTL or business timeout.
                stop.wait(.3)
                queue = router._queue(0)
                queue.enqueue_cancel("missing-account", "after-startup", "missing-order")
                deadline = monotonic() + 2
                receipt = queue.status("after-startup")
                while receipt["state"] == "PENDING" and monotonic() < deadline:
                    sleep(.01)
                    receipt = queue.status("after-startup")
                self.assertEqual(receipt["state"], "REJECTED",
                    {"receipt": receipt, "remaining_at_ready": remaining_at_ready, "child_alive": child.is_alive()})
                self.assertEqual(receipt["error"]["code"], "account_not_found")
                self.assertGreater(remaining_at_ready, .3)
            finally:
                stop.set()
                child.join(5)
                if child.is_alive():
                    child.kill()
                    child.join(5)
                receive.close()
                router.close()

    def test_initialization_past_expiry_fails_without_ready_or_reviving_generation(self):
        with TemporaryDirectory() as temporary:
            directory = Path(temporary) / "managed"
            router = DurableProcessRouter.initialize(directory, 1, {"USD": 2}, managed=True,
                lease_seconds=.6, poll_interval=.01, background_interval=1)
            context = multiprocessing.get_context("spawn")
            receive, send = context.Pipe(duplex=False)
            stop, gate = context.Event(), context.Event()
            with router._control.control.transaction() as connection:
                from uta.durable_process import _registry_schema
                _registry_schema(connection)
            child = context.Process(target=_delayed_owner,
                args=(str(directory), router._settings, stop, send, os.getpid(), gate, True))
            child.start()
            send.close()
            gate.set()
            try:
                self.assertTrue(receive.poll(5))
                report = receive.recv()
                self.assertEqual((report["state"], report["code"]), ("failed", "lease_expired"))
                child.join(5)
                self.assertFalse(child.is_alive())
                state = WriterFence(router._database(0)).status()
                self.assertEqual(state["generation"], 1)
                self.assertFalse(state["active"])
                with router._database(0).read_transaction() as connection:
                    self.assertEqual(connection.execute("SELECT COUNT(*) FROM writer_fence_events WHERE kind='renewed'").fetchone()[0], 0)
            finally:
                stop.set()
                child.join(5)
                if child.is_alive():
                    child.kill()
                    child.join(5)
                receive.close()
                router.close()
