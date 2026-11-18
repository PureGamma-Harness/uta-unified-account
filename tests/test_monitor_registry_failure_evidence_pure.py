"""Four inert checks. No real thread, PID, SQL, FD write or financial import."""
import json
import stat
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import monitor_registry_failure_evidence as evidence


class MonitorRegistryFailureEvidenceTests(unittest.TestCase):
    def frame(self, tail=None, *, parent=False):
        class Frame:
            f_lineno = 123
            f_code = SimpleNamespace(co_filename=("/synthetic/tests/test_durable_process.py" if parent
                else "/synthetic/uta/storage.py"), co_name=(
                "test_expired_stopped_owner_holding_shared_gate_is_killed_and_publication_recovers"
                if parent else "_connect"))
            f_back = tail
            @property
            def f_locals(self):
                raise AssertionError("locals must never be inspected")
            @property
            def f_globals(self):
                raise AssertionError("globals must never be inspected")
        return Frame()

    def test_two_owned_threads_have_eight_frames_and_no_arbitrary_payload(self):
        parent = monitor = None
        for _ in range(12):
            parent = self.frame(parent, parent=True)
            monitor = self.frame(monitor)
        thread = object.__new__(evidence.threading.Thread)
        thread.__dict__.update(_ident=1002, _name="uta-process-supervisor")
        router = SimpleNamespace(_monitor=thread)
        snapshots = {1001: parent, 1002: monitor, 1003: object()}
        with patch.object(evidence.sys, "_current_frames", return_value=snapshots), \
                patch.object(evidence.threading, "get_ident", return_value=1001), \
                patch.object(evidence.threading, "_active", {1002: thread}), \
                patch.object(evidence, "_primary", return_value={"chain": []}):
            payload = evidence.build_packet(router, AssertionError("synthetic-not-exported"))
        self.assertEqual(len(payload["threads"]), 2)
        self.assertTrue(all(len(row["frames"]) == 8 and row["frames_truncated"]
                            for row in payload["threads"]))
        self.assertEqual(payload["threads"][1]["ownership"], "matched_unlocked_samples")
        data = evidence.render(payload)
        self.assertLessEqual(len(data), 32768)
        self.assertNotIn(b"synthetic-not-exported", data)
        self.assertNotIn(b"/synthetic/", data)
        self.assertNotIn(b"1001", data)
        self.assertNotIn(b"1002", data)
        self.assertEqual(snapshots, {})

    def test_original_exception_object_survives_diagnostic_failure(self):
        class Primary(AssertionError):
            def __str__(self):
                raise AssertionError("exception message must not be formatted")
            __repr__ = __str__
        primary = Primary("synthetic-unexportable")
        with patch.object(evidence, "build_packet", side_effect=RuntimeError("synthetic collector error")), \
                patch.object(evidence, "write_packet", return_value="collector_failed") as write:
            with self.assertRaises(Primary) as caught:
                try:
                    raise primary
                except BaseException as error:
                    evidence.emit_once(SimpleNamespace(), error)
                    raise
        self.assertIs(caught.exception, primary)
        self.assertEqual(primary.args, ("synthetic-unexportable",))
        self.assertEqual(write.call_count, 1)
        self.assertEqual(write.call_args.args[0], evidence._FALLBACK)

    def test_busy_mutex_and_worker_cache_are_never_acquired_or_read(self):
        class NeverAcquire:
            def acquire(self, *args, **kwargs):
                raise AssertionError("busy router mutex must not be acquired")
        router = SimpleNamespace(_monitor=None, _mutex=NeverAcquire(), _workers=object(),
                                 _spawn_pending_cleanup=object(), _reports=object())
        with patch.object(evidence.sys, "_current_frames", return_value={1001: None}), \
                patch.object(evidence.threading, "get_ident", return_value=1001), \
                patch.object(evidence, "_primary", return_value={"chain": []}):
            payload = evidence.build_packet(router, RuntimeError("synthetic"))
        self.assertEqual(payload["router_mutex"], "not_acquired")
        self.assertEqual(payload["worker_cache"], "not_read")
        self.assertEqual(payload["threads"][1]["ownership"], "unverified")

    def test_quota_or_blocking_sink_denial_never_retries_output(self):
        packet = evidence.render({"synthetic_oversize": "x" * 32768})
        self.assertEqual(packet, evidence._QUOTA)
        self.assertTrue(json.loads(packet[len(evidence.PREFIX):])["quota_denied"])
        with patch.object(evidence.os, "fstat", return_value=SimpleNamespace(st_mode=stat.S_IFIFO)), \
                patch.object(evidence.os, "get_blocking", return_value=True), \
                patch.object(evidence.os, "write") as write:
            self.assertEqual(evidence.write_packet(packet), "blocking_sink_declined")
            write.assert_not_called()
        with patch.object(evidence.os, "fstat", return_value=SimpleNamespace(st_mode=stat.S_IFREG)), \
                patch.object(evidence.os, "write", return_value=1) as write:
            self.assertEqual(evidence.write_packet(packet), "short_write")
            self.assertEqual(write.call_count, 1)
