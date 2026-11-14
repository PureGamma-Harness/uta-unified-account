"""Independent failure tests; no live funds, venues or privileged filesystem I/O."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from time import perf_counter
import unittest

from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ExchangeService, ServiceError
from uta.storage import Database


NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)


class CappedDatabase(Database):
    """Inject SQLite's real database-full condition without filling the host disk."""

    max_pages: int | None = None

    def _connect(self):
        connection = super()._connect()
        if self.max_pages is not None:
            connection.execute("PRAGMA max_page_count=" + str(self.max_pages))
        return connection


def _exceptions(error):
    pending, seen = [error], set()
    while pending:
        current = pending.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        yield current
        pending.extend((current.__cause__, current.__context__))


class FaultAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "exchange.sqlite3"
        self.now = NOW
        self.database = CappedDatabase(self.path)
        self.service = self.reopen()
        self.service.create_account("alice")
        self.service.publish_market(MarketSnapshot(
            1, self.now, {"USD": AssetSpec(D(1), D(1))},
            {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))}))
        self.service.set_kill_switch(False)
        self.service.deposit("alice", "seed", "USD", D(1000))

    def reopen(self, database=None):
        return ExchangeService(database or self.database, {"USD": 8}, clock=lambda: self.now)

    def state(self):
        return (self.service.account("alice"), self.service.orders("alice"),
                self.service.ledger.journal(), self.service.events(limit=1000))

    def child(self, code, *arguments):
        import uta.service
        package_root = Path(uta.service.__file__).resolve().parent.parent
        return subprocess.run([sys.executable, "-c", code, str(self.path), self.now.isoformat(),
                               *arguments], cwd=package_root, capture_output=True,
                              text=True, timeout=20)

    def test_sqlite_full_rolls_back_every_projection_and_same_id_can_retry(self):
        with self.database.transaction() as connection:
            self.database.max_pages = connection.execute("PRAGMA page_count").fetchone()[0]
        failed_id = None
        for index in range(200):
            command_id = "full-" + str(index) + "x" * 110
            before = self.state()
            try:
                self.service.deposit("alice", command_id, "USD", D(1))
            except ServiceError as error:
                self.assertEqual(error.code, "storage_unavailable")
                errors = list(_exceptions(error))
                # sqlite_errorcode is available on supported newer CPython
                # versions; Python 3.10 retains SQLite's exact diagnostic.
                full = [e for e in errors if isinstance(e, sqlite3.OperationalError)
                        and (getattr(e, "sqlite_errorcode", None) == 13
                             or str(e) == "database or disk is full")]
                self.assertTrue(full, [(type(e).__name__, str(e)) for e in errors])
                self.assertEqual(self.state(), before)
                failed_id = command_id
                break
        self.assertIsNotNone(failed_id, "fixture must actually reach SQLITE_FULL")
        self.database.max_pages = None
        restarted = self.reopen(Database(self.path))
        balance = D(restarted.account("alice")["balances"]["USD"])
        restarted.deposit("alice", failed_id, "USD", D(1))
        once = restarted.account("alice")
        self.assertEqual(D(once["balances"]["USD"]), balance + 1)
        restarted.deposit("alice", failed_id, "USD", D("1.0"))
        self.assertEqual(restarted.account("alice"), once)
        self.assertEqual(restarted.ledger.verify(), len(restarted.ledger.journal()))

    def test_writer_lock_timeout_never_returns_an_admission_receipt(self):
        contender = self.reopen(Database(self.path, timeout=.05))
        before = self.state()
        with self.database.transaction():
            started = perf_counter()
            with self.assertRaises(ServiceError) as failure:
                contender.submit_order("alice", "busy", "BTC-PERP", D(1), D(100))
            elapsed = perf_counter() - started
            self.assertEqual(failure.exception.code, "storage_unavailable")
            self.assertEqual(failure.exception.status, 503)
            self.assertLess(elapsed, 3, "configured busy timeout must bound a local lock wait")
        self.assertEqual(self.state(), before)
        accepted = contender.submit_order("alice", "busy", "BTC-PERP", D(1), D(100))
        self.assertEqual(accepted["status"], "OPEN")
        self.assertEqual(len(contender.orders("alice")), 1)

    def test_unacknowledged_process_exit_before_commit_has_no_financial_effect(self):
        before = self.state()
        code = r'''
import os, sys
from datetime import datetime
from decimal import Decimal as D
from uta.service import ExchangeService
from uta.storage import Database
s = ExchangeService(Database(sys.argv[1]), {"USD":8}, clock=lambda:datetime.fromisoformat(sys.argv[2]))
original = s._event
def crash(connection, kind, account_id, payload):
    if kind == "DEPOSIT_POSTED" and payload["event_id"] == "unknown-outcome":
        os._exit(73)
    return original(connection, kind, account_id, payload)
s._event = crash
s.deposit("alice", "unknown-outcome", "USD", D(7))
'''
        result = self.child(code)
        self.assertEqual(result.returncode, 73, result.stderr)
        restarted = self.reopen(Database(self.path))
        self.service = restarted
        self.assertEqual(self.state(), before)
        restarted.deposit("alice", "unknown-outcome", "USD", D(7))
        self.assertEqual(D(restarted.account("alice")["balances"]["USD"]), D(1007))
        self.assertEqual(restarted.ledger.verify(), 2)

    def test_confirmed_and_response_lost_commits_survive_abrupt_exit_exactly_once(self):
        code = r'''
import json, os, sys
from datetime import datetime
from decimal import Decimal as D
from uta.service import ExchangeService
from uta.storage import Database
s = ExchangeService(Database(sys.argv[1]), {"USD":8}, clock=lambda:datetime.fromisoformat(sys.argv[2]))
result = s.deposit("alice", sys.argv[3], "USD", D(7))
if sys.argv[4] == "acknowledged":
    print(json.dumps({"command_id":sys.argv[3],"version":result["version"]}), flush=True)
os._exit(74)
'''
        for command_id, outcome in (("confirmed", "acknowledged"), ("lost-response", "unknown")):
            result = self.child(code, command_id, outcome)
            self.assertEqual(result.returncode, 74, result.stderr)
            if outcome == "acknowledged":
                self.assertEqual(json.loads(result.stdout)["command_id"], command_id)
            else:
                self.assertEqual(result.stdout, "")
            started = perf_counter()
            restarted = self.reopen(Database(self.path))
            verified_events = restarted.ledger.verify()
            recovered = restarted.account("alice")
            recovery_ms = (perf_counter() - started) * 1000
            journal, events = restarted.ledger.journal(), restarted.events(limit=1000)
            restarted.deposit("alice", command_id, "USD", D("7.00"))
            self.assertEqual(restarted.account("alice"), recovered)
            self.assertEqual(restarted.ledger.journal(), journal)
            self.assertEqual(restarted.events(limit=1000), events)
            print("FAULT_EVIDENCE " + json.dumps({
                "fixture": "single-node-process-exit", "outcome": outcome,
                "recovery_ms": round(recovery_ms, 3), "verified_journal_events": verified_events,
                "lost_confirmed_commands": 0, "duplicate_business_effects": 0,
                "scope": "local WAL/FULL; no power-loss, AZ-loss or replicated-commit claim"}))
        self.assertEqual(D(restarted.account("alice")["balances"]["USD"]), D(1014))

    def test_stale_market_distinguishes_cancel_replay_and_new_execution(self):
        self.service.submit_order("alice", "confirmed", "BTC-PERP", D(1), D(100))
        self.service.apply_fill("alice", "confirmed", "committed", D(1), D(100))
        self.service.submit_order("alice", "pending", "BTC-PERP", D(1), D(100))
        self.now += timedelta(minutes=1)
        self.service.set_kill_switch(True)
        before = self.state()
        with self.assertRaises(ServiceError) as rejected:
            self.service.apply_fill("alice", "pending", "not-executed", D(1), D(100))
        self.assertEqual(rejected.exception.code, "market_unavailable")
        self.assertEqual(self.state(), before)
        self.assertEqual(self.service.apply_fill("alice", "confirmed", "committed",
                                                D(1), D(100))["status"], "FILLED")
        self.assertEqual(self.state(), before)
        self.assertEqual(self.service.cancel_order("alice", "pending")["status"], "CANCELLED")
        self.assertEqual(self.service.account("alice")["open_order_margin"], "0")
        self.assertFalse(self.service.readiness()["ready"])

    def test_bounded_settlement_model_and_deliberately_unsafe_mutants(self):
        import uta.service
        repository = Path(uta.service.__file__).resolve().parent.parent
        script = repository / "formal" / "explore_settlement.py"
        result = subprocess.run([sys.executable, str(script)], capture_output=True,
                                text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["safe"]["result"], "invariants_hold")
        self.assertGreater(report["safe"]["reachable_states"], 10)
        self.assertEqual(report["unsafe_split_commit"]["result"], "counterexample")
        self.assertEqual(report["unsafe_duplicate_retry"]["result"], "counterexample")
        self.assertEqual(report["unsafe_cross_asset_netting"]["result"], "counterexample")


if __name__ == "__main__":
    unittest.main()
