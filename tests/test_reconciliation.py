from datetime import datetime, timezone
from decimal import Decimal as D, Inexact, localcontext
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from uta.credit import CreditService
from uta.cutover import ClassicImporter
from uta.market import MarketSnapshot
from uta.matching import Matcher
from uta.migration import build_shadow
from uta.models import AssetSpec, InstrumentSpec
from uta.reconciliation import reconcile_exchange
from uta.service import ExchangeService, ServiceError
from uta.storage import Database


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "exchange.sqlite3"
        self.now = datetime(2026, 11, 14, tzinfo=timezone.utc)
        self.exchange = self.reopen()
        self.exchange.publish_market(MarketSnapshot(1, self.now,
            {"USD": AssetSpec(D(1), D(1))},
            {"BTC": InstrumentSpec(D(100), D(".1"), D(".05"))}))
        self.exchange.set_kill_switch(False)
        self.matcher = Matcher(self.exchange)
        for account in ("alice", "bob"):
            self.exchange.create_account(account)
            self.exchange.deposit(account, "funding", "USD", D(1000))

    def reopen(self):
        return ExchangeService(Database(self.path), {"USD": 8}, clock=lambda: self.now)

    def pair(self, buy="alice", sell="bob", quantity="1", identifier="initial"):
        self.exchange.submit_order(buy, identifier + "-buy", "BTC", D(quantity), D(100))
        self.exchange.submit_order(sell, identifier + "-sell", "BTC", D(quantity).copy_negate(), D(100))
        self.assertEqual(self.matcher.match_once("BTC")["confirmed_trades"], 1)

    def source(self, quantity="2", account="classic"):
        return build_shadow({"account_id": account, "version": 1, "captured_at": self.now.isoformat(),
            "compartments": {
                "spot": {"balances": [{"asset": "USD", "free": "1000", "locked": "0", "borrowed": "0", "interest": "0"}]},
                "margin": {"balances": []},
                "futures": {"balances": [], "positions": [{"symbol": "BTC", "quantity": quantity, "entry_price": "90"}]}}}, now=self.now)

    def import_it(self):
        importer = ClassicImporter(self.exchange)
        importer.import_shadow(self.source(), "import-1", source_fence_reference="synthetic:fenced",
                               open_orders=[], conditional_orders=[], pending_settlements=[], transfers_in_flight=[])
        return importer

    def test_matches_orders_position_cost_cashflow_and_restart_reconcile(self):
        self.pair(quantity="1.12345678")
        self.pair(buy="bob", sell="alice", quantity=".12345678", identifier="partial-close")
        result = reconcile_exchange(self.exchange)
        self.assertEqual((result["matches"], result["fills"], result["positions"]), (2, 4, 2))
        self.assertEqual(result, reconcile_exchange(self.reopen()))

    def test_mutated_position_quantity_and_cost_are_detected_beyond_old_match_verification(self):
        self.pair()
        for column, wrong, original in (("quantity", "2", "1"), ("cost_basis", "101", "100")):
            with self.subTest(column=column):
                with self.exchange._transaction() as connection:
                    connection.execute(f"UPDATE uta_positions SET {column}=? WHERE account_id='alice'", (wrong,))
                # Old receipt verification alone passes: full replay must catch it.
                self.assertEqual(self.matcher.verify(strict=True)["matches"], 1)
                with self.assertRaises(ServiceError) as caught:
                    reconcile_exchange(self.exchange)
                self.assertEqual(caught.exception.code, "reconciliation_failed")
                with self.exchange._transaction() as connection:
                    connection.execute(f"UPDATE uta_positions SET {column}=? WHERE account_id='alice'", (original,))
        self.assertEqual(reconcile_exchange(self.exchange)["status"], "passed")

    def test_mutated_order_fill_and_fee_metadata_are_detected(self):
        self.pair()
        for column, wrong, correct in (("filled_quantity", ".5", "1"),
                                       ("fee_notional", "101", "100"),
                                       ("charged_fee", ".05", ".04")):
            with self.subTest(column=column):
                with self.exchange._transaction() as connection:
                    connection.execute(f"UPDATE uta_orders SET {column}=? WHERE account_id='alice'", (wrong,))
                with self.assertRaises(ServiceError):
                    reconcile_exchange(self.exchange)
                with self.exchange._transaction() as connection:
                    connection.execute(f"UPDATE uta_orders SET {column}=? WHERE account_id='alice'", (correct,))
        self.assertEqual(reconcile_exchange(self.exchange)["status"], "passed")

    def test_standalone_execution_requires_explicit_nonmatching_inspection(self):
        self.exchange.submit_order("alice", "manual", "BTC", D(1), D(100))
        self.exchange.apply_fill("alice", "manual", "manual-fill", D(1), D(100))
        with self.assertRaises(ServiceError) as unpaired:
            reconcile_exchange(self.exchange)
        self.assertEqual(unpaired.exception.code, "unpaired_execution")
        result = reconcile_exchange(self.exchange, matching_only=False)
        self.assertEqual(result["unpaired_fills"], 1)

    def test_source_genesis_position_can_close_and_reverse_using_real_matches(self):
        self.import_it()
        self.exchange.supervise_account("classic")
        self.pair(buy="alice", sell="classic", quantity="3", identifier="reverse-source-long")
        result = reconcile_exchange(self.exchange)
        self.assertEqual(result["active_imports"], 1)
        self.assertEqual(self.exchange.account("classic")["positions"]["BTC"]["quantity"], "-1")
        self.assertEqual(self.exchange.account("classic")["positions"]["BTC"]["cost_basis"], "-100")
        self.assertEqual(result["matches"], 1)

    def test_reversed_import_does_not_remain_as_position_genesis(self):
        importer = self.import_it()
        importer.reverse_import("import-1", "reverse-1", source_handback_reference="synthetic:handback")
        result = reconcile_exchange(self.exchange)
        self.assertEqual(result["active_imports"], 0)
        self.assertEqual(result["positions"], 0)

    def test_unknown_external_position_origin_is_never_assumed_flat(self):
        with self.exchange._transaction() as connection:
            connection.execute("INSERT INTO uta_positions VALUES ('alice','BTC','1','100')")
        with self.assertRaises(ServiceError) as caught:
            reconcile_exchange(self.exchange)
        self.assertIn("origin", str(caught.exception))

    def test_credit_projection_is_checked_in_same_snapshot(self):
        credit = CreditService(self.exchange)
        credit.configure_asset_limit("USD", D(1000))
        credit.configure_limit("alice", "USD", D(500))
        credit.fund_pool("pool", "USD", D(1000), source_reference="synthetic:funding")
        credit.borrow("alice", "borrow", "USD", D(100))
        credit.accrue_interest("alice", "interest", "USD", D(".1"))
        self.assertEqual(reconcile_exchange(self.exchange)["nonzero_liabilities"], 1)
        with self.exchange._transaction() as connection:
            connection.execute("UPDATE uta_liabilities SET principal='101' WHERE account_id='alice'")
        with self.assertRaises(ServiceError):
            reconcile_exchange(self.exchange)

    def test_checker_never_repairs_missing_matching_or_migration_guard(self):
        self.pair()
        with self.exchange._transaction() as connection:
            connection.execute("DROP TRIGGER uta_matches_no_delete")
        with self.assertRaises(ServiceError):
            reconcile_exchange(self.exchange)
        with self.exchange._transaction() as connection:
            self.assertIsNone(connection.execute("SELECT 1 FROM sqlite_master WHERE name='uta_matches_no_delete'").fetchone())

    def test_source_receipt_checksum_is_rechecked_after_schema_guards(self):
        self.import_it()
        with self.exchange._transaction() as connection:
            connection.execute("DROP TRIGGER migration_imports_no_update")
            connection.execute("UPDATE migration_imports SET receipt='{}'")
            connection.execute("""CREATE TRIGGER migration_imports_no_update BEFORE UPDATE ON migration_imports
                BEGIN SELECT RAISE(ABORT,'immutable'); END""")
        with self.assertRaises(ServiceError) as caught:
            reconcile_exchange(self.exchange)
        self.assertIn("checksum", str(caught.exception))

    def test_low_context_and_production_projection_replacement_cannot_change_reference_replay(self):
        self.pair(quantity="1.23456789")
        self.pair(buy="bob", sell="alice", quantity=".23456789", identifier="partial")
        with patch.object(self.exchange, "_project_fill", side_effect=AssertionError("production formula reused")):
            with localcontext() as context:
                context.prec = 1
                context.Emax = 1
                context.traps[Inexact] = True
                self.assertEqual(reconcile_exchange(self.exchange)["status"], "passed")

    def test_full_checker_uses_one_transaction_and_does_not_mutate_or_nest_begin(self):
        self.pair()
        before = self.exchange.events(limit=1000), self.exchange.ledger.journal()
        original = self.exchange.database._connect
        statements = []
        def traced():
            connection = original()
            connection.set_trace_callback(statements.append)
            return connection
        with patch.object(self.exchange.database, "_connect", traced):
            reconcile_exchange(self.exchange)
        self.assertEqual(sum(sql == "BEGIN IMMEDIATE" for sql in statements), 1)
        self.assertFalse(any(sql.startswith(("UPDATE ", "INSERT ", "DELETE ", "CREATE ")) for sql in statements))
        self.assertEqual((self.exchange.events(limit=1000), self.exchange.ledger.journal()), before)


if __name__ == "__main__":
    unittest.main()
