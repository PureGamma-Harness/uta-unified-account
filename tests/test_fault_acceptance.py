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
from uta.matching import Matcher
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


class _FaultFixture:
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


class FaultAcceptanceTests(_FaultFixture, unittest.TestCase):
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


class MatchingFaultAcceptanceTests(_FaultFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.service.create_account("bob")
        self.service.deposit("bob", "seed", "USD", D(1000))
        self.service.submit_order("alice", "buy", "BTC-PERP", D(1), D(100))
        self.service.submit_order("bob", "sell", "BTC-PERP", D(-1), D(100))
        self.matcher = Matcher(self.service)

    def financial(self):
        accounts = self.service.accounts()
        with self.database.transaction() as connection:
            fills = [tuple(row) for row in connection.execute(
                "SELECT * FROM uta_fills ORDER BY account_id,fill_id")]
        return (accounts, {a["account_id"]: self.service.orders(a["account_id"]) for a in accounts},
                self.service.ledger.journal(), self.service.events(limit=1000),
                self.matcher.trades(limit=1000), fills)

    def test_process_exit_after_second_side_or_receipt_cannot_publish_half_a_trade(self):
        code = r'''
import os, sys
from datetime import datetime
from uta.matching import Matcher
from uta.service import ExchangeService
from uta.storage import Database
s = ExchangeService(Database(sys.argv[1]), {"USD":8}, clock=lambda:datetime.fromisoformat(sys.argv[2]))
matcher = Matcher(s)
original = s._event
def crash(connection, kind, account_id, payload):
    if sys.argv[3] == "second-side" and kind == "FILL_APPLIED" and account_id == "bob":
        os._exit(75)
    if sys.argv[3] == "receipt" and kind == "MATCH_CONFIRMED":
        os._exit(76)
    return original(connection, kind, account_id, payload)
s._event = crash
matcher.match_once("BTC-PERP", max_matches=1)
'''
        for point, exit_code in (("second-side", 75), ("receipt", 76)):
            with self.subTest(crash_point=point):
                before = self.financial()
                result = self.child(code, point)
                self.assertEqual(result.returncode, exit_code, result.stderr)
                self.service = self.reopen(Database(self.path))
                self.matcher = Matcher(self.service)
                self.assertEqual(self.financial(), before)
                self.assertEqual(self.matcher.verify(strict=True)["paired_fills"], 0)
        self.assertEqual(self.matcher.match_once("BTC-PERP")["confirmed_trades"], 1)
        self.assertEqual(self.matcher.verify(strict=True)["paired_fills"], 2)

    def test_receipt_storage_failure_rolls_back_both_legs_and_original_book_remains(self):
        before = self.financial()
        with self.database.transaction() as connection:
            connection.execute("""CREATE TRIGGER injected_receipt_failure BEFORE INSERT ON uta_matches
                BEGIN SELECT RAISE(ABORT,'injected receipt storage failure'); END""")
        with self.assertRaises(sqlite3.IntegrityError):
            self.matcher.match_once("BTC-PERP")
        self.assertEqual(self.financial(), before)
        with self.database.transaction() as connection:
            connection.execute("DROP TRIGGER injected_receipt_failure")
        self.assertEqual(self.matcher.match_once("BTC-PERP")["confirmed_trades"], 1)
        self.assertEqual(self.matcher.verify(strict=True)["matches"], 1)

    def test_response_lost_after_match_commit_recovers_two_sides_without_duplicate_execution(self):
        code = r'''
import os, sys
from datetime import datetime
from uta.matching import Matcher
from uta.service import ExchangeService
from uta.storage import Database
s = ExchangeService(Database(sys.argv[1]), {"USD":8}, clock=lambda:datetime.fromisoformat(sys.argv[2]))
result = Matcher(s).match_once("BTC-PERP", max_matches=1)
if result["confirmed_trades"] != 1:
    os._exit(78)
# Commit succeeded, but the worker dies before emitting a response.
os._exit(77)
'''
        result = self.child(code)
        self.assertEqual(result.returncode, 77, result.stderr)
        self.assertEqual(result.stdout, "")
        self.service = self.reopen(Database(self.path))
        self.matcher = Matcher(self.service)
        before = self.financial()
        self.assertEqual(self.matcher.match_once("BTC-PERP")["confirmed_trades"], 0)
        self.assertEqual(self.financial(), before)
        receipts = self.matcher.trades()
        self.assertEqual(len(receipts), 1)
        receipt = receipts[0]
        self.assertEqual((receipt["quantity"], receipt["price"]), ("1", "100"))
        for account, order_id, sign in (("alice", "buy", 1), ("bob", "sell", -1)):
            actual = self.service.account(account)
            self.assertEqual(D(actual["balances"]["USD"]), D("999.96"))
            self.assertEqual(D(actual["positions"]["BTC-PERP"]["quantity"]), D(sign))
            self.assertEqual(self.service.orders(account)[0]["status"], "FILLED")
            with self.database.transaction() as connection:
                fill_id = receipt["buy_fill_id" if sign > 0 else "sell_fill_id"]
                fill = connection.execute("SELECT * FROM uta_fills WHERE account_id=? AND fill_id=?",
                                          (account, fill_id)).fetchone()
                self.assertEqual(fill["order_id"], order_id)
                self.assertEqual(D(fill["quantity"]), D(sign))
                self.assertEqual(D(fill["fee"]), D(".04"))
        self.assertEqual(self.matcher.verify(strict=True)["paired_fills"], 2)
        # An independent integer projection checks every asset, without using
        # the production ledger's balance or risk calculation as its oracle.
        with self.database.transaction() as connection:
            by_asset = {}
            for row in connection.execute("SELECT asset,units FROM ledger_postings"):
                by_asset[row["asset"]] = by_asset.get(row["asset"], 0) + int(row["units"])
            self.assertEqual(by_asset, {"USD": 0})
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_fills").fetchone()[0], 2)
            events = [json.loads(row[0]) for row in connection.execute(
                "SELECT payload FROM uta_events WHERE event_type='MATCH_CONFIRMED'")]
            self.assertEqual([event["trade_id"] for event in events], [receipt["trade_id"]])


if __name__ == "__main__":
    unittest.main()
