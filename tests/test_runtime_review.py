"""Independent M1 runtime checks: scheduling, draining and audit immutability."""
from datetime import datetime, timezone
from decimal import Decimal as D
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Event, Thread
import time
import unittest
from unittest.mock import patch
from urllib.request import urlopen

import uta
from uta.examples import synthetic_policy
from uta.market import MarketSnapshot
from uta.matching import Matcher
from uta.models import AssetSpec, InstrumentSpec
from uta.reconciliation import reconcile_exchange
from uta.service import ExchangeService, ServiceError
from uta.storage import Database
from uta.supervisor import ExchangeWorker


NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)
SOURCE = Path(uta.__file__).resolve().parent.parent


class RuntimeReviewTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "exchange.sqlite3"
        self.exchange = ExchangeService(Database(self.path), {"USD": 8}, clock=lambda: NOW)
        self.exchange.publish_market(MarketSnapshot(1, NOW, {"USD": AssetSpec(D(1), D(1))},
            {"X": InstrumentSpec(D(100), D(".1"), D(".05"))}))
        for account in ("alice", "bob"):
            self.exchange.create_account(account)
            self.exchange.deposit(account, "fund", "USD", D(1000))
        self.exchange.set_kill_switch(False)

    def admit_pair(self):
        self.exchange.submit_order("alice", "buy", "X", D(1), D(100))
        self.exchange.submit_order("bob", "sell", "X", D(-1), D(100))

    def snapshot(self):
        with self.exchange.database.transaction() as connection:
            return tuple(connection.iterdump())

    def test_stop_drains_one_real_inflight_match_without_an_extra_tick(self):
        self.admit_pair()
        worker = ExchangeWorker(self.exchange, interval=.01)
        entered, release, stopped = Event(), Event(), Event()
        self.addCleanup(worker.stop)
        self.addCleanup(release.set)
        original = worker.matcher.match_once
        calls = []

        def in_flight(symbol, maximum):
            calls.append(symbol)
            entered.set()
            if not release.wait(timeout=3):
                raise RuntimeError("test did not release the in-flight match")
            return original(symbol, maximum)

        with patch.object(worker.matcher, "match_once", side_effect=in_flight):
            worker.start()
            self.assertTrue(entered.wait(timeout=2), "worker never entered matching")
            stop_thread = Thread(target=lambda: (worker.stop(), stopped.set()))
            stop_thread.start()
            self.assertFalse(stopped.wait(timeout=.05), "stop returned before the authority command drained")
            release.set()
            self.assertTrue(stopped.wait(timeout=3), "drained worker did not stop")
            stop_thread.join(timeout=1)
        self.assertEqual(calls, ["X"])
        self.assertEqual(D(self.exchange.account("alice")["positions"]["X"]["quantity"]), D(1))
        self.assertEqual(D(self.exchange.account("bob")["positions"]["X"]["quantity"]), D(-1))
        self.assertEqual(Matcher(self.exchange, initialize=False).verify(strict=True)["matches"], 1)

    def test_known_account_rejection_advances_durable_cursor_without_global_halt(self):
        worker = ExchangeWorker(self.exchange, account_batch=1)
        original = self.exchange.supervise_account

        def known_rejection(account_id):
            if account_id == "alice":
                raise ServiceError("risk_unavailable", "synthetic account-scoped rejection", 503)
            return original(account_id)

        with patch.object(self.exchange, "supervise_account", side_effect=known_rejection):
            first = worker.run_once()
        self.assertEqual(first["accounts"], 1)
        self.assertEqual(first["blocked"], [{"account_id": "alice", "code": "risk_unavailable"}])
        restarted = ExchangeWorker(self.exchange, account_batch=1)
        self.assertEqual(restarted.run_once()["plans"], [{"account_id": "bob", "state": "NORMAL"}])
        self.assertEqual(restarted.run_once()["plans"], [{"account_id": "alice", "state": "NORMAL"}])
        self.assertFalse(self.exchange.readiness()["halted"])

    def test_unexpected_automation_failure_commits_halt_and_preserves_waiting_orders(self):
        self.admit_pair()
        before = self.exchange.orders("alice"), self.exchange.orders("bob")
        worker = ExchangeWorker(self.exchange, interval=.01)
        self.addCleanup(worker.stop)
        seen = Event()

        def unexpected(account_id):
            seen.set()
            raise RuntimeError("synthetic unexpected failure; never expose this detail")

        with patch.object(self.exchange, "supervise_account", side_effect=unexpected):
            worker.start()
            self.assertTrue(seen.wait(timeout=2))
            deadline = time.monotonic() + 2
            while worker.last_report.get("reason") != "worker_failure" and time.monotonic() < deadline:
                seen.wait(timeout=.01)
                time.sleep(.001)
            worker.stop()
        self.assertEqual(worker.last_report, {"state": "blocked", "reason": "worker_failure",
                                              "emergency_halt_committed": True})
        reopened = ExchangeService(Database(self.path), {"USD": 8}, clock=lambda: NOW)
        self.assertTrue(reopened.readiness()["halted"])
        self.assertEqual((reopened.orders("alice"), reopened.orders("bob")), before)
        self.assertEqual(reopened.account("alice")["positions"], {})
        self.assertEqual(reopened.account("bob")["positions"], {})
        self.assertEqual(len([event for event in reopened.events(limit=1000)
                              if event["event_type"] == "KILL_SWITCH_CHANGED" and event["payload"]["enabled"]]), 1)
        with self.assertRaises(ServiceError):
            reopened.submit_order("alice", "blocked", "X", D(1), D(100))

    def test_reconciliation_neither_mutates_successful_state_nor_repairs_missing_guard(self):
        self.admit_pair()
        self.assertEqual(Matcher(self.exchange).match_once("X")["confirmed_trades"], 1)
        before = self.snapshot()
        self.assertEqual(reconcile_exchange(self.exchange)["matches"], 1)
        self.assertEqual(self.snapshot(), before)
        with self.exchange.database.transaction() as connection:
            connection.execute("DROP TRIGGER uta_matches_no_update")
        before = self.snapshot()
        with self.assertRaises(ServiceError):
            reconcile_exchange(self.exchange)
        self.assertEqual(self.snapshot(), before, "verification must not recreate the missing protection")

    def test_cli_explicit_automation_starts_with_synthetic_policy_and_stops_cleanly(self):
        root = Path(self.directory.name)
        credentials, catalog_path, rules_path = (root / name for name in ("credentials.json", "catalog.json", "rules.json"))
        credentials.write_text(json.dumps([{"token": "A" * 43, "role": "admin"}]), encoding="utf-8")
        credentials.chmod(0o600)
        catalog, rules = synthetic_policy()
        catalog_path.write_text(catalog.to_json(), encoding="utf-8")
        rules_path.write_text(rules.to_json(), encoding="utf-8")
        process = subprocess.Popen(
            [sys.executable, "-m", "uta", "exchange", "--database", str(root / "automated.sqlite3"),
             "--credentials", str(credentials), "--catalog", str(catalog_path), "--risk-rules", str(rules_path),
             "--asset-scale", "USD=8", "--asset-scale", "BTC=8", "--automate", "--port", "0"],
            cwd=root, env={**os.environ, "PYTHONPATH": str(SOURCE)},
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)

        from tests.cli_sigterm_failure_evidence import CliFailureEvidence
        evidence = CliFailureEvidence(process)
        self.addCleanup(evidence.cleanup)
        try:
            evidence.event("startup_wait_before")
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                self.assertTrue(selector.select(timeout=5), "automated CLI did not start")
            evidence.event("startup_wait_return")
            line = process.stdout.readline()
            evidence.banner(line)
            self.assertTrue(line, "automated CLI failed before announcing its local port")
            banner = json.loads(line)
            self.assertTrue(banner["automated"])
            evidence.event("health_before")
            with urlopen("http://127.0.0.1:" + str(banner["port"]) + "/healthz", timeout=3) as response:
                self.assertEqual(json.load(response), {"status": "ok"})
            evidence.event("health_return")
            evidence.event("sigterm_before")
            process.send_signal(signal.SIGTERM)
            evidence.event("sigterm_return")
            evidence.event("exit_wait_before")
            self.assertEqual(process.wait(timeout=5), 0)
            evidence.event("exit_wait_return")
            reopened = ExchangeService(Database(root / "automated.sqlite3"), {"USD": 8, "BTC": 8},
                                       clock=lambda: NOW, product_catalog=catalog, portfolio_rules=rules)
            self.assertEqual(reopened.accounts(), [])
            self.assertFalse(reopened.readiness()["ready"], "the explicit policy must not generate funds or prices")
            evidence.event("post_exit_assertions_return")
        except BaseException as primary:
            try:
                evidence.primary_failure(primary)
            except BaseException:
                pass
            raise


if __name__ == "__main__":
    unittest.main()
