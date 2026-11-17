"""Independent NORMAL supervision cache equivalence and transaction proofs.

All data are synthetic. Expected cash/fees/state transitions are hand computed;
no production risk function is used to generate financial expected values.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from threading import Event, Thread
import unittest
from unittest.mock import patch

from uta.credit import CreditService
from uta.ledger import Posting
from uta.market import MarketSnapshot
from uta.matching import Matcher
from uta.models import AssetSpec, InstrumentSpec
from uta.products import ProductCatalog, ProductKind, ProductSpec, TradingStatus
from uta.service import ExchangeService, ServiceError
from uta.storage import Database, DurableLedger, StorageError
from uta.spot import SpotExchange
from uta.supervisor import ExchangeWorker


NOW = datetime(2026, 11, 17, tzinfo=timezone.utc)

# Full business-row checkpoints from a real isolated git-archive 5c53f92 run,
# not from the candidate's cache-disabled branch. Provenance is in the report.
ORIGINAL_CHECKPOINTS = (
    "c7e8b3634b965f381a1b4ebc6b4bb1acabe39fed0f8c475b3860bae9679f385c",
    "c7e8b3634b965f381a1b4ebc6b4bb1acabe39fed0f8c475b3860bae9679f385c",
    "c7e8b3634b965f381a1b4ebc6b4bb1acabe39fed0f8c475b3860bae9679f385c",
    "8555af8880f2f9bffc5eb89b0e4650638c775eb3f06c5a22f95cadd90f4894c8",
    "245968f0026553a73c4e3ae912d26a070c9bd34e9612d68b7fe051ff8e1d6087",
    "0b851b35010be2db3c2cc569c5b230cadcd809c41507c2830115b0005884775b",
    "52fe5c38fa9b27b085942d53044de90fa19b5e2edf9b0d3db31f7371be21234f",
    "52fe5c38fa9b27b085942d53044de90fa19b5e2edf9b0d3db31f7371be21234f",
    "52fe5c38fa9b27b085942d53044de90fa19b5e2edf9b0d3db31f7371be21234f",
    "352c45bb021766b09274c7185b631a1e5c3fd5072de99de28e82af31efd2778c",
)


def business_state(service):
    with service.database.read_transaction() as connection:
        names = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {name: sorted((tuple(row) for row in connection.execute('SELECT * FROM "' + name + '"')), key=repr)
                for name in names}


class CommitInterleavingDatabase(Database):
    proof_connection = None
    after_proof_commit = None

    @contextmanager
    def transaction(self):
        selected = False
        with super().transaction() as connection:
            yield connection
            selected = connection is self.proof_connection
        if selected and self.after_proof_commit is not None:
            callback, self.after_proof_commit = self.after_proof_commit, None
            callback()


class SupervisionCacheValidationTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.now = NOW

    def service(self, name="service", funds=None, database_class=Database):
        database = database_class(self.directory / (name + ".sqlite3"))
        service = ExchangeService(database, {"USD": 8, "BTC": 8}, clock=lambda: self.now)
        service.publish_market(self.market())
        service.set_kill_switch(False)
        for account, value in (funds or {"alice": "1000", "bob": "100000"}).items():
            service.create_account(account)
            if D(value):
                service.deposit(account, "seed", "USD", D(value))
        return service

    def market(self, version=1, mark="100"):
        return MarketSnapshot(version, self.now,
            {"USD": AssetSpec(D(1), D(1)), "BTC": AssetSpec(D(mark), D(".8"))},
            {"BTC-PERP": InstrumentSpec(D(mark), D(".1"), D(".05"))})

    @staticmethod
    def worker(service, capacity=8, **kwargs):
        return ExchangeWorker(service, normal_cache_size=capacity, **kwargs)

    @staticmethod
    def debit_without_account_version(service, account, reference, amount):
        return service.ledger.post(reference, [Posting("customer:" + account, "USD", -D(amount)),
            Posting("system:independent-adjustment", "USD", D(amount))])

    def test_enabled_cache_and_original_path_replay_identical_financial_liquidation_and_event_state(self):
        baseline, optimized = self.service("baseline"), self.service("optimized")
        workers = [self.worker(baseline, 0), self.worker(optimized, 8)]
        services = (baseline, optimized)
        checkpoints = []
        def round_both():
            reports = [worker.run_once() for worker in workers]
            self.assertEqual(reports[0]["linear_trades"], reports[1]["linear_trades"])
            reference, actual = business_state(baseline), business_state(optimized)
            self.assertEqual(reference, actual)
            digest = sha256(json.dumps(actual, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
            self.assertEqual(digest, ORIGINAL_CHECKPOINTS[len(checkpoints)])
            checkpoints.append(digest)
            return reports
        for service in services:
            service.submit_order("alice", "open-long", "BTC-PERP", D(90), D(100))
            service.submit_order("bob", "open-short", "BTC-PERP", D(-90), D(100))
        self.assertEqual(round_both()[0]["linear_trades"], 1)
        self.assertEqual(baseline.account("alice")["balances"]["USD"], "996.4")
        round_both()
        round_both()
        self.assertGreater(workers[1].normal_cache_stats()["hits"], 0)
        for service in services:
            service.publish_market(self.market(2, "90"))
        round_both()  # no opposing liquidity: only a real reduction order exists
        self.assertEqual(baseline.account("alice")["positions"]["BTC-PERP"]["quantity"], "90")
        with baseline.database.read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT state FROM uta_liquidation_accounts WHERE account_id='alice'").fetchone()[0], "LIQUIDATING")
        for service in services:
            service.submit_order("bob", "partial-liquidity", "BTC-PERP", D(45), D(90))
        self.assertEqual(round_both()[0]["linear_trades"], 1)
        self.assertEqual(baseline.account("alice")["balances"]["USD"], "544.78")
        self.assertEqual(baseline.account("alice")["positions"]["BTC-PERP"]["quantity"], "45")
        round_both()
        for service in services:
            service.deposit("alice", "rescue", "USD", D(1000))
        round_both()
        round_both()
        round_both()
        for service in services:
            credit = CreditService(service)
            credit.configure_asset_limit("USD", D(100))
            credit.configure_limit("alice", "USD", D(100))
            credit.fund_pool("pool", "USD", D(50), source_reference="synthetic:cache:capital")
            credit.borrow("alice", "loan", "USD", D(5))
            credit.accrue_interest("alice", "interest", "USD", D(1))
            credit.repay("alice", "repayment", "USD", D(2))
        round_both()
        self.assertEqual(tuple(checkpoints), ORIGINAL_CHECKPOINTS)
        self.assertEqual(baseline.account("alice")["liabilities"]["USD"], {"principal": "4", "interest": "0", "total": "4"})
        for service in services:
            service.ledger.verify()
            Matcher(service).verify(strict=True)

    def test_real_ledger_write_without_account_version_invalidates_normal_proof(self):
        service = self.service(funds={"alice": "10"})
        worker = self.worker(service)
        worker.run_once()
        worker.run_once()
        self.assertGreater(worker.normal_cache_stats()["hits"], 0)
        version = service.account("alice")["version"]
        self.debit_without_account_version(service, "alice", "direct-ledger-debit", "11")
        self.assertEqual(service.account("alice")["version"], version)
        report = worker.run_once()
        self.assertIn({"account_id": "alice", "state": "BANKRUPT"}, report["plans"])
        self.assertEqual(service.account("alice")["balances"]["USD"], "-1")
        service.ledger.verify()

    def test_market_bytes_and_full_config_changes_invalidate_even_when_versions_do_not(self):
        service = self.service()
        service.submit_order("alice", "long", "BTC-PERP", D(90), D(100))
        service.submit_order("bob", "short", "BTC-PERP", D(-90), D(100))
        Matcher(service).match_once("BTC-PERP")
        worker = self.worker(service)
        worker.run_once()
        worker.run_once()
        original, calls = service.supervise_account, []
        def observed(account_id, *, connection=None):
            calls.append(account_id)
            return original(account_id, connection=connection)
        # Fault injection models a projection/control writer that did not bump
        # account or market versions. It is not a supported publication API.
        with service.database.transaction() as connection:
            connection.execute("INSERT INTO uta_config VALUES ('independent_config_marker','changed')")
        with patch.object(service, "supervise_account", side_effect=observed):
            worker.run_once()
        self.assertCountEqual(calls, ["alice", "bob"])
        worker.run_once()
        with service.database.transaction() as connection:
            connection.execute("UPDATE uta_market SET payload=? WHERE singleton=1", (self.market(1, "90").to_json(),))
        report = worker.run_once()
        self.assertIn({"account_id": "alice", "state": "LIQUIDATING"}, report["plans"])
        self.assertEqual(service.account("alice")["positions"]["BTC-PERP"]["quantity"], "90")

    def test_live_spot_economics_without_account_version_are_part_of_the_key(self):
        service = self.service(funds={"alice": "1000"})
        catalog = ProductCatalog(1, {"BTC-SPOT": ProductSpec("BTC-SPOT", ProductKind.SPOT_MARGIN,
            "BTC", "USD", "USD", D(".01"), D(".01"), D(1), status=TradingStatus.ACTIVE)})
        service.spot = SpotExchange(service, catalog)
        service.spot.submit_order("alice", "buy-spot", "BTC-SPOT", D(1), D(100))
        worker = self.worker(service)
        worker.run_once()
        worker.run_once()
        version = service.account("alice")["version"]
        head = service.ledger.journal()
        # Valid monetary row values emulate a legacy projection update that
        # omitted account versioning; the public spot amend API is not implied.
        with service.database.transaction() as connection:
            connection.execute("UPDATE uta_spot_orders SET quantity='2',reserved_amount='200.08' WHERE account_id='alice'")
        original, calls = service.supervise_account, []
        def observed(account_id, *, connection=None):
            calls.append(account_id)
            return original(account_id, connection=connection)
        with patch.object(service, "supervise_account", side_effect=observed):
            worker.run_once()
        self.assertEqual(calls, ["alice"])
        self.assertEqual(service.account("alice")["version"], version)
        self.assertEqual(service.ledger.journal(), head)
        self.assertEqual(service.risk("alice")["equity"], "799.92")

    def test_unversioned_position_and_gross_debt_projection_changes_cannot_reuse_normal(self):
        for component, expected in (("position", "LIQUIDATING"), ("debt", "BANKRUPT")):
            with self.subTest(component=component):
                service = self.service(component, funds={"alice": "10"})
                worker = self.worker(service)
                worker.run_once()
                worker.run_once()
                version, journal = service.account("alice")["version"], service.ledger.journal()
                # Deliberate legacy-projection fault injection, not a supported
                # cash/debt/position adjustment or migration API.
                with service.database.transaction() as connection:
                    if component == "position":
                        connection.execute("INSERT INTO uta_positions VALUES ('alice','BTC-PERP','1','120')")
                    else:
                        connection.execute("INSERT INTO uta_liabilities VALUES ('alice','USD','11','0')")
                self.assertEqual(service.account("alice")["version"], version)
                self.assertEqual(service.ledger.journal(), journal)
                report = worker.run_once()
                self.assertIn({"account_id": "alice", "state": expected}, report["plans"])

    def test_normal_with_actual_spot_cancellation_is_ineligible_until_a_stable_proof(self):
        service = self.service(funds={"alice": "1000.4"})
        catalog = ProductCatalog(1, {"BTC-SPOT": ProductSpec("BTC-SPOT", ProductKind.SPOT_MARGIN,
            "BTC", "USD", "USD", D(".01"), D(".01"), D(1), status=TradingStatus.ACTIVE)})
        service.spot = SpotExchange(service, catalog)
        service.spot.submit_order("alice", "all-cash", "BTC-SPOT", D(10), D(100))
        worker = self.worker(service)
        worker.run_once()
        self.assertEqual(service.spot.orders("alice")[0]["status"], "CANCELLED")
        self.assertEqual(worker.normal_cache_stats()["size"], 0)
        self.assertGreater(worker.normal_cache_stats()["ineligible"], 0)
        worker.run_once()
        worker.run_once()
        self.assertGreater(worker.normal_cache_stats()["hits"], 0)
        self.assertEqual(service.account("alice")["balances"]["USD"], "1000.4")

    def test_proof_is_bound_to_financial_transaction_not_a_later_read_only_key(self):
        service = self.service(funds={"alice": "10"}, database_class=CommitInterleavingDatabase)
        database = service.database
        outside = DurableLedger(Database(database.path), service.scales)
        worker = self.worker(service)
        original = service.supervise_account
        attempted, completed, failures = Event(), Event(), []
        def writer():
            attempted.set()
            try:
                outside.post("after-normal-proof", [Posting("customer:alice", "USD", D(-11)),
                    Posting("system:independent-adjustment", "USD", D(11))])
            except BaseException as error:
                failures.append(error)
            finally:
                completed.set()
        thread = Thread(target=writer)
        def supervise(account_id, *, connection=None):
            self.assertIsNotNone(connection, "optimized miss must supply its own financial authority transaction")
            self.assertTrue(connection.in_transaction)
            result = original(account_id, connection=connection)
            database.proof_connection = connection
            thread.start()
            self.assertTrue(attempted.wait(2))
            self.assertFalse(completed.wait(.03), "another writer committed inside the supposed NORMAL proof transaction")
            return result
        def after_commit():
            self.assertTrue(completed.wait(3), "outside write failed to commit after proof transaction ended")
        database.after_proof_commit = after_commit
        try:
            with patch.object(service, "supervise_account", side_effect=supervise):
                worker.run_once()
        finally:
            if thread.ident is not None:
                thread.join(5)
        self.assertEqual(failures, [])
        self.assertTrue(completed.is_set())
        self.assertEqual(service.account("alice")["balances"]["USD"], "-1")
        report = worker.run_once()
        self.assertIn({"account_id": "alice", "state": "BANKRUPT"}, report["plans"],
                      "a post-COMMIT read must never label changed bankrupt economics with an earlier NORMAL result")

    def test_same_connection_join_rejects_a_different_database_authority(self):
        service = self.service("owner", funds={"alice": "10"})
        other = self.service("other", funds={"alice": "20"})
        before = business_state(service), business_state(other)
        with other.database.transaction() as connection:
            with self.assertRaises(StorageError):
                service.supervise_account("alice", connection=connection)
        self.assertEqual((business_state(service), business_state(other)), before)

    def test_failed_or_unknown_proof_commit_does_not_publish_a_cache_entry(self):
        for outcome in ("constraint_failure", "lost_response"):
            with self.subTest(outcome=outcome):
                service = self.service(outcome, funds={"alice": "10"}, database_class=CommitInterleavingDatabase)
                self.worker(service, 0).run_once()  # persisted NORMAL, no proof cache
                with service.database.transaction() as connection:
                    connection.execute("CREATE TABLE cache_fault_parent (id INTEGER PRIMARY KEY)")
                    connection.execute("CREATE TABLE cache_fault_child (id INTEGER REFERENCES cache_fault_parent(id) DEFERRABLE INITIALLY DEFERRED)")
                worker = self.worker(service)
                original = service.supervise_account
                def observe(account_id, *, connection=None):
                    result = original(account_id, connection=connection)
                    service.database.proof_connection = connection
                    if outcome == "constraint_failure":
                        connection.execute("INSERT INTO cache_fault_child VALUES (999)")
                    return result
                def response_lost():
                    raise ConnectionError("synthetic proof response lost after real COMMIT")
                if outcome == "lost_response":
                    service.database.after_proof_commit = response_lost
                before = business_state(service)
                with patch.object(service, "supervise_account", side_effect=observe):
                    with self.assertRaises(sqlite3.IntegrityError if outcome == "constraint_failure" else ConnectionError):
                        worker.run_once()
                self.assertEqual(worker.normal_cache_stats()["size"], 0)
                self.assertEqual(business_state(service), before)
                worker.run_once()
                self.assertEqual(worker.normal_cache_stats()["size"], 1)

    def test_expiry_between_snapshot_and_cached_account_never_reports_fresh_normal(self):
        service = self.service()
        worker = self.worker(service)
        worker.run_once()
        worker.run_once()
        service.create_account("aaron")  # no journal movement, existing cached keys stay eligible
        original = service.supervise_account
        def slow_first(account_id, *, connection=None):
            result = original(account_id, connection=connection)
            if account_id == "aaron":
                self.now += timedelta(seconds=6)
            return result
        with patch.object(service, "supervise_account", side_effect=slow_first):
            report = worker.run_once()
        plans = {row["account_id"]: row["state"] for row in report["plans"]}
        blocked = {row.get("account_id"): row["code"] for row in report["blocked"]}
        for account in ("alice", "bob"):
            self.assertTrue(plans.get(account) == "BLOCKED" or blocked.get(account) == "market_unavailable", repr(report))
        with self.assertRaises(ServiceError) as caught:
            service.submit_order("alice", "stale-new-risk", "BTC-PERP", D(1), D(100))
        self.assertEqual(caught.exception.code, "market_unavailable")
        service.publish_market(self.market(2))
        refreshed = worker.run_once()
        self.assertIn({"account_id": "alice", "state": "NORMAL"}, refreshed["plans"])

    def test_fair_cursor_advances_on_cache_hits_and_bankrupt_account_is_never_skipped(self):
        service = self.service(funds={"alice": "10", "bob": "10", "charlie": "10", "zeta": "10"})
        self.debit_without_account_version(service, "zeta", "zeta-distress", "11")
        worker = self.worker(service, account_batch=1)
        original, calls, visited = service.supervise_account, [], []
        def observed(account_id, *, connection=None):
            calls.append(account_id)
            return original(account_id, connection=connection)
        with patch.object(service, "supervise_account", side_effect=observed):
            for _ in range(12):
                report = worker.run_once()
                self.assertEqual(report["accounts"], 1)
                with service.database.read_transaction() as connection:
                    visited.append(connection.execute("SELECT last_account FROM uta_supervisor_schedule").fetchone()[0])
        self.assertEqual(visited, ["alice", "bob", "charlie", "zeta"] * 3)
        self.assertEqual(calls.count("zeta"), 3)
        self.assertGreater(worker.normal_cache_stats()["hits"], 0)
        self.assertEqual(service.account("zeta")["balances"]["USD"], "-1")

    def test_liquidating_and_loan_blocked_accounts_are_supervised_on_every_unchanged_visit(self):
        for state in ("LIQUIDATING", "BLOCKED"):
            with self.subTest(state=state):
                service = self.service(state)
                if state == "LIQUIDATING":
                    service.submit_order("alice", "long", "BTC-PERP", D(90), D(100))
                    service.submit_order("bob", "short", "BTC-PERP", D(-90), D(100))
                    Matcher(service).match_once("BTC-PERP")
                    service.publish_market(self.market(2, "90"))
                else:
                    credit = CreditService(service)
                    credit.configure_asset_limit("USD", D(100))
                    credit.configure_limit("alice", "USD", D(100))
                    credit.fund_pool("pool", "USD", D(50), source_reference="synthetic:blocked")
                    credit.borrow("alice", "loan", "USD", D(10))
                    credit.accrue_interest("alice", "interest", "USD", D(1000))
                worker = self.worker(service)
                original, calls = service.supervise_account, []
                def observed(account_id, *, connection=None):
                    calls.append(account_id)
                    return original(account_id, connection=connection)
                with patch.object(service, "supervise_account", side_effect=observed):
                    for _ in range(3):
                        report = worker.run_once()
                        self.assertIn({"account_id": "alice", "state": state}, report["plans"])
                self.assertEqual(calls.count("alice"), 3)

    def test_bounded_capacity_clear_and_cold_restart_are_not_persistent_risk_authority(self):
        service = self.service(funds={"alice": "10", "bob": "10", "charlie": "10"})
        worker = self.worker(service, capacity=2)
        worker.run_once()
        stats = worker.normal_cache_stats()
        self.assertLessEqual(stats["size"], 2)
        self.assertGreater(stats["evictions"], 0)
        before = business_state(service)
        worker.clear_normal_cache()
        self.assertEqual(worker.normal_cache_stats()["size"], 0)
        self.assertEqual(business_state(service), before)
        cold = ExchangeService(Database(service.database.path), service.scales, clock=lambda: self.now)
        restarted = self.worker(cold, capacity=2)
        self.assertEqual(restarted.normal_cache_stats()["size"], 0)
        restarted.run_once()
        self.assertEqual(business_state(service), before)

    def test_default_zero_is_reference_path_and_cache_settings_reject_boolean_or_unbounded_values(self):
        service = self.service()
        reference = ExchangeWorker(service)
        self.assertEqual(reference.normal_cache_stats()["capacity"], 0)
        for value in (True, -1, 65537, 1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.worker(service, value)


if __name__ == "__main__":
    unittest.main()
