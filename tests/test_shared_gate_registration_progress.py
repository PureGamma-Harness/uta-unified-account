"""Conditional actual-method models; no native recovery or CI-cause claim.

These three discovery cases use fresh in-memory objects. A fake registry
conflict advances a virtual clock by its busy budget; native LOCKED/PROTOCOL,
internal SQLite retries, disk I/O and OS scheduling need not obey that model.
"""
from contextlib import contextmanager, ExitStack
import multiprocessing.process
import os
from pathlib import Path
import signal
import sqlite3
import threading
import time
import unittest
from unittest.mock import patch

from tests import shared_gate_registration_candidate_model as focused
from tests import shared_gate_registration_model as model


ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def actual_methods_without_native_effects():
    """Load only selected current source AST, with no runtime module import."""
    guards = [(sqlite3, "connect"), (multiprocessing.process.BaseProcess, "start"),
              (os, "kill"), (os, "waitpid"), (threading.Thread, "start"), (time, "sleep")]
    for owner, name in ((os, "pidfd_open"), (signal, "pidfd_send_signal")):
        if hasattr(owner, name):
            guards.append((owner, name))
    with ExitStack() as stack:
        for owner, name in guards:
            stack.enter_context(patch.object(owner, name, model.forbidden))
        # Discovery can precede this test by many minutes. Scope the helper's
        # finite execution guard to this case rather than its import time.
        stack.enter_context(patch.object(model, "WALL_DEADLINE", time.monotonic() + 5))
        namespace, _ = model.load_actual_methods((ROOT / "uta/durable_process.py").read_bytes())
        yield namespace


class SharedGateRegistrationProgressTests(unittest.TestCase):
    def test_spawned_budget_copy_preserves_shared_database_and_other_events(self):
        with actual_methods_without_native_effects() as namespace:
            for kind in ("SPAWNED", "OWNED", "COORDINATOR", "ORPHAN_KILLED"):
                for original in (10.0, .025):
                    with self.subTest(kind=kind, original_timeout=original):
                        row = focused.direct_record(namespace, kind, original)
                        self.assertEqual(row["connection_busy_budget"],
                                         min(original, .1) if kind == "SPAWNED" else original)
                        self.assertTrue(row["original_unchanged"])
                        self.assertTrue(row["subclass_hook_and_fields_preserved"])
                        self.assertTrue(row["one_append_only"])

    def test_conditional_registry_wait_allows_expired_sibling_scan(self):
        with actual_methods_without_native_effects() as namespace:
            for order, code in (("held_first", 5), ("dead_first", 6), ("retry_first", 15)):
                with self.subTest(order=order, modeled_error_code=code):
                    row = model.scenario(namespace, order=order, error_code=code)
                    self.assertFalse(row["recovery_deadline_missed"])
                    self.assertGreaterEqual(row["old_kill_virtual_seconds"],
                                            row["expiry_virtual_seconds"])

    def test_unknown_registration_preserves_gate_and_cleanup_exclusion(self):
        with actual_methods_without_native_effects() as namespace:
            for lease, stuck in (("unknown", False), ("matching", True)):
                with self.subTest(lease_observation=lease, cleanup_unconfirmed=stuck):
                    # The helper requires UNKNOWN append outcome, no released
                    # failed-child gate or repeated nonce, and pending+blocked
                    # replacement when cleanup is unconfirmed.
                    row = model.scenario(namespace, order="held_first", error_code=5,
                                         lost_reply=True, cleanup_stuck=stuck, lease=lease)
                    self.assertGreater(row["model_append_count"], 0)
                    self.assertFalse(row["recovery_deadline_missed"])
                    if lease == "unknown":
                        self.assertIsNone(row["old_kill_virtual_seconds"])


if __name__ == "__main__":
    unittest.main()
