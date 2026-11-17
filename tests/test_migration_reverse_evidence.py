"""Independent negative cases for reverse settlement-evidence reconciliation.

Source trades use public synthetic spot APIs. Deletions are explicitly offline
corruption; they are not a supported customer/source workflow. No repair occurs.
"""
from decimal import Decimal as D
import json
import unittest

from tests import test_managed_migration_scope as fixtures
from uta.durable_process import _preflight_managed_spot_sources
from uta.service import ServiceError, ExchangeService
from uta.spot import SpotExchange
from uta.storage import Database


class MigrationReverseEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.source_case = fixtures.ManagedMigrationScopeTests(
            "test_terminal_history_preflight_and_verifier_open_no_financial_constructor_or_writer")
        self.source_case.setUp()
        self.addCleanup(self.source_case.doCleanups)

    def source(self):
        case = self.source_case
        source = case.source()
        exchange, spot = case.add_offline_standalone_spot_extension()
        case.cancel_source_spot(spot)
        return source, exchange, spot

    def remove_receipt_bundle(self, trade_id, *, all_orders=False, one_fill=False):
        """Remove children before parents, then restore exact original guards."""
        case = self.source_case
        with Database(case.path / "shard-0000.sqlite3").transaction() as connection:
            guards = [tuple(row) for row in connection.execute(
                "SELECT name,sql FROM sqlite_master WHERE name IN "
                "('uta_spot_matches_no_delete','uta_spot_fills_no_delete') ORDER BY name")]
            trade = connection.execute("SELECT * FROM uta_spot_matches WHERE trade_id=?", (trade_id,)).fetchone()
            for name, _ in guards:
                connection.execute("DROP TRIGGER " + name)
            if one_fill:
                connection.execute("DELETE FROM uta_spot_fills WHERE trade_id=? AND account_id=?",
                                   (trade_id, trade["buy_account_id"]))
            else:
                connection.execute("DELETE FROM uta_spot_fills WHERE trade_id=?", (trade_id,))
                connection.execute("DELETE FROM uta_spot_matches WHERE trade_id=?", (trade_id,))
                if all_orders:
                    connection.execute("DELETE FROM uta_spot_orders")
                else:
                    for side in ("buy", "sell"):
                        connection.execute("DELETE FROM uta_spot_orders WHERE account_id=? AND order_id=?",
                            (trade[side + "_account_id"], trade[side + "_order_id"]))
            for _, sql in guards:
                connection.execute(sql)
            self.assertEqual(list(connection.execute("PRAGMA foreign_key_check")), [])
            self.assertEqual([tuple(row) for row in connection.execute(
                "SELECT name,sql FROM sqlite_master WHERE name IN "
                "('uta_spot_matches_no_delete','uta_spot_fills_no_delete') ORDER BY name")], guards)

    def reject_missing_bundle(self, *, remaining_trade):
        case = self.source_case
        _, _, spot = self.source()
        first_trade = case.read("SELECT trade_id FROM uta_spot_matches ORDER BY sequence")[0]["trade_id"]
        if remaining_trade:
            spot.submit_order("seller", "later-sell", "BTC-SPOT", D("-.1"), D(100))
            spot.submit_order("buyer", "later-buy", "BTC-SPOT", D(".1"), D(100))
            self.assertEqual(spot.match_once("BTC-SPOT")["confirmed_trades"], 1)
        financial = case.financial_state()
        audit = case.read("SELECT * FROM uta_events WHERE event_type GLOB 'SPOT_*' ORDER BY sequence")
        self.remove_receipt_bundle(first_trade, all_orders=not remaining_trade)
        damaged_spot = case.spot_state()
        verifier_error = migration_error = None
        result = None
        try:
            result = spot.verify()
        except ServiceError as error:
            verifier_error = error
        try:
            case.take_over()
        except ServiceError as error:
            migration_error = error
        manifest_exists = case.read("SELECT name FROM sqlite_master WHERE name='router_durable_config'", control=True)
        manifest = case.read("SELECT initialized FROM router_durable_config", control=True) if manifest_exists else []
        print("reverse-evidence", json.dumps({
            "remaining_valid_trade": remaining_trade, "verifier_result": result,
            "verifier_error": None if verifier_error is None else verifier_error.code,
            "migration_error": None if migration_error is None else migration_error.code,
            "manifest": manifest,
            "retained_spot_events": len(audit),
            "settled_financial_rows_unchanged": case.financial_state() == financial,
            "audit_rows_unchanged": case.read("SELECT * FROM uta_events WHERE event_type GLOB 'SPOT_*' ORDER BY sequence") == audit,
            "remaining_receipts": len(damaged_spot["uta_spot_matches"]),
            "remaining_fills": len(damaged_spot["uta_spot_fills"]),
        }), flush=True)
        self.assertEqual(case.financial_state(), financial)
        self.assertEqual(case.spot_state(), damaged_spot, "verification must not recreate missing history")
        self.assertIsNotNone(verifier_error, "retained confirmation events and settlement require their missing receipt bundle")
        self.assertEqual((verifier_error.code, verifier_error.status), ("spot_corrupt", 503))
        self.assertIsNotNone(migration_error, "unreconciled spot settlement must be rejected before any fence")
        self.assertEqual((migration_error.code, migration_error.status), ("spot_corrupt", 503))
        case.assert_unsealed()

    def test_missing_entire_receipt_bundle_is_not_empty_compatible_history(self):
        self.reject_missing_bundle(remaining_trade=False)

    def test_one_missing_bundle_among_valid_settlements_is_rejected(self):
        self.reject_missing_bundle(remaining_trade=True)

    def test_missing_single_fill_is_already_rejected_without_repair_or_fencing(self):
        case = self.source_case
        _, _, spot = self.source()
        trade_id = case.read("SELECT trade_id FROM uta_spot_matches")[0]["trade_id"]
        financial = case.financial_state()
        self.remove_receipt_bundle(trade_id, one_fill=True)
        damaged_spot = case.spot_state()
        with self.assertRaises(ServiceError) as verify:
            spot.verify()
        self.assertEqual((verify.exception.code, verify.exception.status), ("spot_corrupt", 503))
        with self.assertRaises(ServiceError) as migration:
            case.take_over()
        self.assertEqual((migration.exception.code, migration.exception.status), ("spot_corrupt", 503))
        case.assert_unsealed()
        self.assertEqual(case.financial_state(), financial)
        self.assertEqual(case.spot_state(), damaged_spot)

    def test_unfilled_cancelled_order_events_do_not_imply_a_missing_trade(self):
        case = self.source_case
        source = case.source()
        exchange = ExchangeService(Database(case.path / "shard-0000.sqlite3"), case.scales,
            max_price_age=case.max_age, product_catalog=case.catalog,
            portfolio_rules=case.rules, decision_audit=True)
        spot = SpotExchange(exchange, case.catalog)
        spot.submit_order("buyer", "unfilled", "BTC-SPOT", D(".1"), D(90))
        spot.cancel_order("buyer", "unfilled")
        events = case.read("SELECT event_type,account_id,payload FROM uta_events WHERE event_type GLOB 'SPOT_*' ORDER BY sequence")
        self.assertEqual([row["event_type"] for row in events], ["SPOT_ORDER_ACCEPTED", "SPOT_ORDER_CANCELLED"])
        self.assertEqual(spot.verify()["matches"], 0)
        _preflight_managed_spot_sources(source)
        case.take_over()
        self.assertEqual(case.read("SELECT event_type,account_id,payload FROM uta_events WHERE event_type GLOB 'SPOT_*' ORDER BY sequence"), events)
        self.assertEqual(case.read("SELECT initialized FROM router_durable_config", control=True), [{"initialized": 1}])


if __name__ == "__main__":
    unittest.main()
