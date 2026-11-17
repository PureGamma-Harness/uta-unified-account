"""Financial outcomes and bounded scheduling of opt-in background suppression."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from uta.ledger import Posting
from uta.market import MarketSnapshot
from uta.matching import Matcher
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ExchangeService
from uta.storage import Database, StorageError
from uta.supervisor import ExchangeWorker


class SupervisionCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.now = datetime(2026, 11, 17, tzinfo=timezone.utc)

    def exchange(self, name="db"):
        return ExchangeService(Database(Path(self.tmp.name) / (name + ".sqlite3")),
                               {"USD": 8}, clock=lambda: self.now)

    def market(self, exchange, version=1, mark="100"):
        exchange.publish_market(MarketSnapshot(version, self.now,
            {"USD": AssetSpec(D(1), D(1))},
            {"BTC-PERP": InstrumentSpec(D(mark), D(".1"), D(".05"))}))
        exchange.set_kill_switch(False)

    def fund(self, exchange, account, amount="1000"):
        exchange.create_account(account)
        exchange.deposit(account, "initial", "USD", D(amount))

    def test_default_is_reference_and_enabled_cache_is_bounded_cold_on_restart(self):
        exchange = self.exchange()
        self.market(exchange)
        for account in ("a", "b", "c"):
            self.fund(exchange, account)
        reference = ExchangeWorker(exchange)
        with patch.object(reference, "_dependencies", side_effect=AssertionError("reference must not hash")):
            reference.run_once()
        worker = ExchangeWorker(exchange, normal_cache_size=2, account_batch=1)
        for _ in range(3):
            worker.run_once()
        self.assertEqual(worker.normal_cache_stats()["size"], 2)
        self.assertEqual(worker.normal_cache_stats()["evictions"], 1)
        worker.clear_normal_cache(reset_stats=True)
        self.assertEqual(worker.normal_cache_stats(), dict(capacity=2, size=0, hits=0, misses=0, evictions=0, ineligible=0))
        restarted = ExchangeWorker(self.exchange(), normal_cache_size=2)
        self.assertEqual(restarted.normal_cache_stats()["size"], 0)
        for bad in (-1, 65537, True, 1.0):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                ExchangeWorker(exchange, normal_cache_size=bad)

    def test_same_version_raw_inputs_and_unbumped_journal_change_are_not_hidden(self):
        exchange = self.exchange()
        self.market(exchange)
        self.fund(exchange, "a", "10")
        worker = ExchangeWorker(exchange, normal_cache_size=4)
        worker.run_once()
        self.assertEqual(worker.run_once()["normal_cache"]["skipped"], 1)
        version = exchange.account("a")["version"]
        exchange.ledger.post("external-adjustment", [
            Posting(exchange._customer("a"), "USD", D(-11)),
            Posting("external:synthetic", "USD", D(11))])
        self.assertEqual(exchange.account("a")["version"], version)
        report = worker.run_once()
        self.assertEqual(report["plans"], [{"account_id": "a", "state": "BANKRUPT"}])
        self.assertEqual(report["normal_cache"]["skipped"], 0)
        # Non-NORMAL states never acquire proofs, even with unchanged versions.
        worker.run_once()
        self.assertEqual(worker.normal_cache_stats()["size"], 0)

    def test_same_version_market_payload_and_raw_liability_change_invalidate(self):
        exchange = self.exchange()
        self.market(exchange)
        self.fund(exchange, "a", "10")
        worker = ExchangeWorker(exchange, normal_cache_size=4)
        worker.run_once()
        worker.run_once()
        with exchange._transaction() as conn:
            snapshot = MarketSnapshot(1, self.now, {"USD": AssetSpec(D(1), D(1))},
                {"BTC-PERP": InstrumentSpec(D(99), D(".1"), D(".05"))})
            conn.execute("UPDATE uta_market SET payload=?", (snapshot.to_json(),))
        self.assertEqual(worker.run_once()["normal_cache"]["supervised"], 1)
        with exchange._transaction() as conn:
            conn.execute("INSERT INTO uta_liabilities VALUES ('a','USD','11','0')")
        self.assertEqual(worker.run_once()["plans"], [{"account_id": "a", "state": "BANKRUPT"}])

    def test_after_snapshot_debit_is_detected_on_next_fair_visit_not_claimed_current(self):
        exchange = self.exchange()
        self.market(exchange)
        self.fund(exchange, "a", "10")
        worker = ExchangeWorker(exchange, normal_cache_size=4)
        worker.run_once()
        original = worker._normal_match
        def debit_after_classification(account_id, proof, state):
            hit = original(account_id, proof, state)
            self.assertTrue(hit)
            # A real second SQLite transaction commits AFTER the first RO
            # snapshot was established. WAL permits it without changing t0.
            exchange.ledger.post("after-snapshot", [
                Posting(exchange._customer("a"), "USD", D(-11)),
                Posting("external:synthetic", "USD", D(11))])
            return hit
        with patch.object(worker, "_normal_match", side_effect=debit_after_classification):
            sampled = worker.run_once()
        self.assertEqual(sampled["plans"], [{"account_id": "a", "state": "NORMAL"}])
        self.assertEqual(sampled["normal_cache"]["skipped"], 1)
        self.assertEqual(D(exchange.account("a")["balances"]["USD"]), D(-1))
        self.assertEqual(worker.run_once()["plans"], [{"account_id": "a", "state": "BANKRUPT"}])

    def test_slow_preceding_account_cannot_skip_later_stale_market(self):
        exchange = self.exchange()
        self.market(exchange)
        self.fund(exchange, "a")
        self.fund(exchange, "b")
        worker = ExchangeWorker(exchange, normal_cache_size=4)
        worker.run_once()
        # Invalidate only a without moving the ledger head.
        with exchange._transaction() as conn:
            conn.execute("UPDATE uta_accounts SET version=version+1 WHERE account_id='a'")
        original = exchange.supervise_account
        def slow(account_id, *, connection=None):
            result = original(account_id, connection=connection)
            if account_id == "a":
                self.now += timedelta(seconds=6)
            return result
        with patch.object(exchange, "supervise_account", side_effect=slow):
            report = worker.run_once()
        self.assertEqual(report["normal_cache"]["skipped"], 0)
        self.assertEqual(report["plans"][-1], {"account_id": "b", "state": "BLOCKED"})

    def test_failed_financial_transaction_never_publishes_proof(self):
        exchange = self.exchange()
        self.market(exchange)
        self.fund(exchange, "a")
        worker = ExchangeWorker(exchange, normal_cache_size=4)
        original = exchange._liquidation_state
        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("synthetic failure after state DML")
        with patch.object(exchange, "_liquidation_state", side_effect=fail), self.assertRaises(RuntimeError):
            worker.run_once()
        self.assertEqual(worker.normal_cache_stats()["size"], 0)
        with exchange.database.read_transaction() as conn:
            self.assertIsNone(conn.execute("SELECT * FROM uta_liquidation_accounts").fetchone())

    def test_joined_supervision_rejects_other_database_and_unstarted_connection(self):
        a, b = self.exchange("one"), self.exchange("two")
        for exchange in (a, b):
            self.market(exchange)
            self.fund(exchange, "same")
        with b._transaction() as conn, self.assertRaises(StorageError):
            a.supervise_account("same", connection=conn)

    def _golden(self, capacity):
        exchange = self.exchange(str(capacity))
        self.market(exchange)
        self.fund(exchange, "alice")
        self.fund(exchange, "bob", "100000")
        worker = ExchangeWorker(exchange, normal_cache_size=capacity)
        worker.run_once()
        worker.run_once()
        exchange.submit_order("alice", "open", "BTC-PERP", D(90), D(100))
        exchange.submit_order("bob", "open", "BTC-PERP", D(-90), D(100))
        self.assertEqual(worker.run_once()["linear_trades"], 1)
        self.market(exchange, 2, "90")
        exchange.submit_order("bob", "one", "BTC-PERP", D(45), D(90))
        self.assertEqual(worker.run_once()["linear_trades"], 1)
        self.assertEqual(worker.run_once()["linear_trades"], 0)
        exchange = self.exchange(str(capacity))
        worker = ExchangeWorker(exchange, normal_cache_size=capacity)
        self.assertEqual(worker.normal_cache_stats()["size"], 0)
        exchange.submit_order("bob", "two", "BTC-PERP", D(45), D(90))
        self.assertEqual(worker.run_once()["linear_trades"], 1)
        worker.run_once()
        worker.run_once()
        self.assertEqual(D(exchange.account("alice")["balances"]["USD"]), D("93.16"))
        self.assertEqual(Matcher(exchange).verify(strict=True)["matches"], 3)
        with exchange.database.read_transaction() as conn:
            tables = ("uta_accounts", "uta_orders", "uta_positions", "uta_liabilities",
                      "uta_liquidation_accounts", "uta_events", "uta_fills", "ledger_events",
                      "ledger_postings", "ledger_balances")
            return {table: sorted(tuple(row) for row in conn.execute("SELECT * FROM " + table)) for table in tables}

    def test_reference_and_optimized_real_partial_liquidation_full_financial_replay_match(self):
        self.assertEqual(self._golden(0), self._golden(8))


if __name__ == "__main__":
    unittest.main()
