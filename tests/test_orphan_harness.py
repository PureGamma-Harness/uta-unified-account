"""Real supervisor evidence for the historical-PID fault-injection race."""
import os
import multiprocessing
from pathlib import Path
import select
import signal
import sqlite3
from tempfile import TemporaryDirectory
from time import monotonic, sleep
import unittest

from uta.durable_process import DurableProcessRouter, _process_identity
from uta.writer_fence import WriterFence
from test_durable_process import _orphan_reaper, _pin_birth, _same_birth


def _existing_child(report):
    """An unrelated child already owned by the test before reaper scope."""
    report.send(_process_identity(os.getpid()))
    report.close()
    while True:
        signal.pause()


def _unregistered_stopped_child():
    signal.raise_signal(signal.SIGSTOP)
    while True:
        signal.pause()


def _exit_before_registering_child(report):
    """Real spawn followed by parent death before any registry write."""
    child = multiprocessing.get_context("spawn").Process(target=_unregistered_stopped_child)
    child.start()
    deadline = monotonic() + 5
    while monotonic() < deadline:
        identity = _process_identity(child.pid)
        if identity["state"] == "T":
            report.send(identity)
            report.close()
            # Deliberately bypass multiprocessing's graceful child join, just
            # as abrupt coordinator death can in process.start -> SPAWNED.
            os._exit(0)
        sleep(.01)
    raise AssertionError("unregistered child did not enter its stopped state")


class HarnessRaceTests(unittest.TestCase):
    def eventually(self, predicate, timeout=8):
        deadline = monotonic() + timeout
        while monotonic() < deadline:
            result = predicate()
            if result:
                return result
            sleep(.01)
        self.fail("timed out waiting for the real supervisor/worker fact")

    def ready_owner(self, router):
        """Read one current, ready owner while excluding monitor replacement."""
        with router._mutex:
            process = router._workers[0][0]
            report = router._reports.get(0, {})
            lease = WriterFence(router._database(0)).status()
            if (not process.is_alive() or report.get("state") != "ready"
                    or report.get("pid") != process.pid or not lease["active"]
                    or lease["owner_pid"] != process.pid):
                return None
            identity = _process_identity(process.pid)
            with router._control.control.read_transaction() as connection:
                records = [dict(row) for row in connection.execute(
                    "SELECT * FROM router_process_owners WHERE shard=0 AND pid=? "
                    "AND nonce=? AND kind IN ('SPAWNED','OWNED') ORDER BY sequence",
                    (process.pid, lease["owner_nonce"]))]
            self.assertEqual([row["kind"] for row in records], ["SPAWNED", "OWNED"])
            for row in records:
                self.assertEqual(row["authority_id"], lease["authority_id"])
                self.assertEqual(row["start_ticks"], identity["start_ticks"])
                self.assertEqual(row["boot_id"], identity["boot_id"])
                self.assertEqual(row["coordinator"], router._coordinator)
            self.assertEqual(records[1]["generation"], lease["generation"])
            self.assertEqual(report["generation"], lease["generation"])
            return {"process": process, "identity": identity,
                    "lease": lease, "records": records}

    def test_supervisor_reaps_reported_owner_before_later_fault_injection(self):
        with TemporaryDirectory() as temporary:
            router = DurableProcessRouter.initialize(
                Path(temporary) / "managed", 1, {"USD": 8}, managed=True,
                lease_seconds=.6, poll_interval=.01, background_interval=.03)
            try:
                router.start()
                prior = self.eventually(lambda: self.ready_owner(router))
                process = prior["process"]
                # This is the same kind of PID snapshot the old orphan helper
                # sent. Anchor it before injecting a stop; never signal that
                # historical integer after the monitor can replace its owner.
                with router._mutex:
                    self.assertIs(router._workers[0][0], process)
                    self.assertTrue(process.is_alive())
                    pidfd = os.pidfd_open(process.pid)
                    try:
                        again = _process_identity(process.pid)
                        for field in ("pid", "start_ticks", "boot_id", "uid"):
                            self.assertEqual(again[field], prior["identity"][field])
                        # Stop outside both the router gate and a SQLite write
                        # transaction. A random instruction-level stop could
                        # instead obstruct the supervisor's lease observation.
                        with router._control._lock(exclusive=True, timeout=3):
                            connection = sqlite3.connect(
                                router._database(0).path, isolation_level=None, timeout=3)
                            try:
                                connection.execute("BEGIN IMMEDIATE")
                                signal.pidfd_send_signal(pidfd, signal.SIGSTOP)
                                stopped = self.eventually(lambda: (
                                    identity if (identity := _process_identity(process.pid))["state"] == "T"
                                    else None))
                            finally:
                                connection.rollback()
                                connection.close()
                        self.assertEqual(stopped["start_ticks"], prior["identity"]["start_ticks"])
                        self.assertEqual(stopped["boot_id"], prior["identity"]["boot_id"])
                    except BaseException:
                        os.close(pidfd)
                        raise
                try:
                    exited = select.poll()
                    exited.register(pidfd, select.POLLIN)
                    self.assertTrue(exited.poll(8000), "supervisor did not kill the stopped owner")
                    current = self.eventually(lambda: (
                        owner if (owner := self.ready_owner(router)) is not None
                        and owner["process"] is not process else None))
                    self.assertEqual(process.exitcode, -signal.SIGKILL)
                    self.assertFalse(process.is_alive())
                    self.assertNotEqual(current["process"].pid, process.pid)
                    self.assertGreater(current["lease"]["generation"], prior["lease"]["generation"])
                    self.assertNotEqual(
                        (current["identity"]["pid"], current["identity"]["start_ticks"]),
                        (prior["identity"]["pid"], prior["identity"]["start_ticks"]))
                    with router._control.control.read_transaction() as connection:
                        historical = [dict(row) for row in connection.execute(
                            "SELECT * FROM router_process_owners WHERE shard=0 AND pid=? "
                            "AND nonce=? AND kind IN ('SPAWNED','OWNED') ORDER BY sequence",
                            (process.pid, prior["lease"]["owner_nonce"]))]
                        self.assertEqual(historical, prior["records"])
                        self.assertEqual(connection.execute(
                            "SELECT COUNT(*) FROM router_process_owners WHERE kind='ORPHAN_KILLED'"
                        ).fetchone()[0], 0)
                finally:
                    os.close(pidfd)
            finally:
                # Normal production close owns and reaps every current child,
                # including the failure path after the intentional SIGSTOP.
                router.close()

    def test_reaper_cleans_unregistered_adopted_child_and_preserves_existing_child(self):
        context = multiprocessing.get_context("spawn")
        baseline_receive, baseline_send = context.Pipe(duplex=False)
        baseline = context.Process(target=_existing_child, args=(baseline_send,))
        receive, send = context.Pipe(duplex=False)
        coordinator = context.Process(target=_exit_before_registering_child, args=(send,))
        baseline_pidfd = child_pidfd = None
        try:
            baseline.start()
            baseline_send.close()
            self.assertTrue(baseline_receive.poll(8), "existing child did not start")
            baseline_identity = baseline_receive.recv()
            baseline_pidfd = _pin_birth(baseline_identity)
            with _orphan_reaper():
                coordinator.start()
                send.close()
                self.assertTrue(receive.poll(8), "coordinator did not confirm its stopped child")
                unregistered = receive.recv()
                child_pidfd = _pin_birth(unregistered)
                coordinator.join(timeout=3)
                self.assertEqual(coordinator.exitcode, 0)
                current = _process_identity(unregistered["pid"])
                self.assertTrue(_same_birth(current, unregistered))
                self.assertEqual(current["state"], "T")
                stat = Path(f"/proc/{unregistered['pid']}/stat").read_text().rsplit(")", 1)[1].split()
                self.assertEqual(int(stat[1]), os.getpid(), "child was not adopted by this subreaper")
                # No registry row or explicit adopted-list entry exists. The
                # reaper must discover this new descendant from the real OS.
            exited = select.poll()
            exited.register(child_pidfd, select.POLLIN)
            self.assertTrue(exited.poll(0), "newly adopted child survived reaper scope")
            with self.assertRaises(ChildProcessError):
                os.waitpid(unregistered["pid"], os.WNOHANG)
            self.assertTrue(baseline.is_alive(), "reaper killed a pre-existing own child")
            self.assertTrue(_same_birth(_process_identity(baseline.pid), baseline_identity))
            preserved = select.poll()
            preserved.register(baseline_pidfd, select.POLLIN)
            self.assertFalse(preserved.poll(0))
        finally:
            # These are our unreaped Process handles, never historical PIDs.
            if coordinator.pid is not None:
                if coordinator.is_alive():
                    coordinator.kill()
                coordinator.join(timeout=3)
                coordinator.close()
            if baseline.pid is not None:
                if baseline.is_alive():
                    baseline.kill()
                baseline.join(timeout=3)
                baseline.close()
            for descriptor in (baseline_pidfd, child_pidfd):
                if descriptor is not None:
                    os.close(descriptor)
            baseline_receive.close()
            baseline_send.close()
            receive.close()
            send.close()


if __name__ == "__main__":
    unittest.main()
