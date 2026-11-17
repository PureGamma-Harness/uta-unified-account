"""Real worker READY after a slow original spot compatibility helper in owned RO.

Only the process-control helper is delayed. No ledger/risk/credit function or
audit engine identity is replaced, and the original helper always executes.
"""
from hashlib import sha256
import json
import multiprocessing
import os
from time import CLOCK_BOOTTIME, clock_gettime_ns
import unittest

from tests import test_managed_migration_scope as fixtures
from uta.writer_fence import WriterFence


SUBJECT = "21aa6510bafcce8383fc24ac2c35e671074b9baf"


def schema_digest(connection):
    rows = [tuple(row) for row in connection.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name,tbl_name,sql")]
    return sha256(json.dumps(rows, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def slow_owned_spot_worker(directory, settings, stop, ready, parent_pid, gate, witness):
    import uta.durable_process as runtime
    original = runtime._verify_managed_spot_source
    calls = {"pre_acquire": 0, "owned": 0}
    def controlled(connection, database, scales):
        if database.writer_token is None:
            calls["pre_acquire"] += 1
            return original(connection, database, scales)
        calls["owned"] += 1
        state = WriterFence(database).assert_writer(connection)
        initial_schema = schema_digest(connection)
        initial_expiry = state["expires_ns"]
        started = clock_gettime_ns(CLOCK_BOOTTIME)
        ddl = []
        connection.set_trace_callback(lambda sql: ddl.append(sql) if sql.lstrip().upper().startswith(
            ("CREATE", "ALTER", "DROP", "REINDEX")) else None)
        try:
            # Keep the actual owned read open past its original persisted TTL.
            # The keeper must renew through a separate restricted connection.
            stop.wait(settings["lease_seconds"] * 1.5)
            result = original(connection, database, scales)
        finally:
            connection.set_trace_callback(None)
        ended = clock_gettime_ns(CLOCK_BOOTTIME)
        current = WriterFence(database).status()  # Fresh snapshot, not the old lease row.
        witness.send({"pid": os.getpid(), "calls": dict(calls), "query_only": connection.execute(
            "PRAGMA query_only").fetchone()[0], "started_ns": started, "ended_ns": ended,
            "old_expiry_ns": initial_expiry, "entry_generation": state["generation"],
            "fresh_generation": current["generation"], "fresh_active": current["active"],
            "schema_digest": initial_schema, "helper_ddl": ddl,
            "original_helper_completed": True})
        return result
    runtime._verify_managed_spot_source = controlled
    try:
        runtime._run_worker(directory, 0, settings, stop, ready, parent_pid, gate,
                            "slow-spot-integration-owner", "owned-spot-integration")
    finally:
        runtime._verify_managed_spot_source = original
        witness.close()


class OwnedSpotStartupIntegrationTests(unittest.TestCase):
    def test_original_spot_helper_crosses_ttl_with_same_generation_and_actual_worker_ready(self):
        case = fixtures.ManagedMigrationScopeTests(
            "test_terminal_history_preflight_and_verifier_open_no_financial_constructor_or_writer")
        case.setUp()
        self.addCleanup(case.doCleanups)
        case.source()
        _, spot = case.add_offline_standalone_spot_extension()
        case.cancel_source_spot(spot)
        router = case.take_over()
        before, spot_before = case.financial_state(), case.spot_state()
        settings = {**router._settings, "lease_seconds": .6, "poll_interval": .01, "background_interval": 1}
        from uta.durable_process import _registry_schema
        with router._control.control.transaction() as connection:
            _registry_schema(connection)
        context = multiprocessing.get_context("spawn")
        receive, send = context.Pipe(duplex=False)
        evidence, witness = context.Pipe(duplex=False)
        stop, gate = context.Event(), context.Event()
        child = context.Process(target=slow_owned_spot_worker,
            args=(str(case.path), settings, stop, send, os.getpid(), gate, witness))
        child.start()
        send.close()
        witness.close()
        gate.set()
        try:
            self.assertTrue(receive.poll(6), "real worker did not resolve startup")
            ready = receive.recv()  # Actual _run_worker sends this; no substitute receipt.
            self.assertEqual(ready["state"], "ready", ready)
            self.assertTrue(evidence.poll(1), "slow helper supplied no actual observation")
            observed = evidence.recv()
            self.assertEqual((ready["pid"], observed["pid"]), (child.pid, child.pid))
            self.assertNotEqual(child.pid, os.getpid())
            self.assertEqual(observed["calls"], {"pre_acquire": 1, "owned": 1})
            self.assertTrue(observed["original_helper_completed"])
            self.assertEqual(observed["query_only"], 1)
            self.assertGreater(observed["ended_ns"], observed["old_expiry_ns"])
            self.assertGreater((observed["ended_ns"] - observed["started_ns"]) / 1e9, settings["lease_seconds"])
            self.assertEqual((observed["entry_generation"], observed["fresh_generation"]),
                             (ready["generation"], ready["generation"]))
            self.assertTrue(observed["fresh_active"])
            self.assertEqual(observed["helper_ddl"], [])
            current = WriterFence(router._database(0)).status()
            self.assertEqual((current["generation"], current["owner_pid"]), (ready["generation"], child.pid))
            self.assertTrue(current["active"])
            with router._database(0).read_transaction() as connection:
                self.assertEqual(schema_digest(connection), observed["schema_digest"])
                rows = [tuple(row) for row in connection.execute("SELECT kind,generation FROM writer_fence_events "
                    "WHERE owner_nonce='slow-spot-integration-owner'")]
            self.assertEqual(sum(kind == "acquired" for kind, _ in rows), 1)
            self.assertGreaterEqual(sum(kind == "renewed" for kind, _ in rows), 4)
            self.assertEqual({generation for _, generation in rows}, {ready["generation"]})
            self.assertEqual(case.financial_state(), before)
            self.assertEqual(case.spot_state(), spot_before)
            print("owned-spot-ready", json.dumps({
                "pid": child.pid, "generation": ready["generation"],
                "configured_ttl_seconds": settings["lease_seconds"],
                "owned_read_seconds": (observed["ended_ns"] - observed["started_ns"]) / 1e9,
                "crossed_original_expiry": observed["ended_ns"] > observed["old_expiry_ns"],
                "helper_calls": observed["calls"], "real_renewals": sum(kind == "renewed" for kind, _ in rows),
                "actual_worker_ready": True, "same_generation": True, "schema_unchanged": True,
                "helper_ddl": observed["helper_ddl"], "financial_and_spot_rows_unchanged": True,
                "pre_acquire_scan_is_outside_owned_budget": True,
            }), flush=True)
        finally:
            stop.set()
            child.join(5)
            if child.is_alive():
                child.kill()
                child.join(5)
            receive.close()
            evidence.close()
            router.close()
        self.assertEqual(child.exitcode, 0)


if __name__ == "__main__":
    unittest.main()
