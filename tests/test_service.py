from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D, localcontext, Inexact
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ExchangeService, ServiceError
from uta.storage import Database


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "exchange.sqlite3"
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.service = self.reopen()
        self.service.create_account("alice")
        self.service.publish_market(self.market())
        self.service.set_kill_switch(False)
        self.service.deposit("alice", "initial", "USD", D("1000"))

    def tearDown(self):
        self.directory.cleanup()

    def reopen(self, **kwargs):
        return ExchangeService(Database(self.path), {"USD": 8, "BTC": 8},
                               clock=lambda: self.now, **kwargs)

    def market(self, version=1, mark="100", im="0.1", mm="0.05"):
        return MarketSnapshot(version, self.now,
                              {"USD": AssetSpec(D(1), D(1)), "BTC": AssetSpec(D("100"), D("0.8"))},
                              {"BTC-PERP": InstrumentSpec(D(mark), D(im), D(mm))})

    def order(self, order_id="buy", quantity="2", price="100", **kwargs):
        return self.service.submit_order("alice", order_id, "BTC-PERP", D(quantity), D(price), **kwargs)

    def fill(self, order_id="buy", fill_id="f1", quantity="2", price="100"):
        return self.service.apply_fill("alice", order_id, fill_id, D(quantity), D(price))

    def assert_code(self, code, call, *args, **kwargs):
        with self.assertRaises(ServiceError) as rejected:
            call(*args, **kwargs)
        self.assertEqual(rejected.exception.code, code)

    def test_restart_idempotency_and_closed_ids_never_reopen(self):
        self.order()
        self.fill()
        account = self.service.account("alice")
        events = self.service.events(limit=1000)
        restarted = self.reopen()
        self.assertEqual(restarted.account("alice"), account)
        self.assertEqual(restarted.submit_order("alice", "buy", "BTC-PERP", D("2.00"), D("100.0"))["status"], "FILLED")
        restarted.apply_fill("alice", "buy", "f1", D("2.0"), D("100.00"))
        restarted.deposit("alice", "initial", "USD", D("1000.0"))
        self.assertEqual(restarted.account("alice"), account)
        self.assertEqual(restarted.events(limit=1000), events)
        self.assertEqual(restarted.ledger.verify(), 2)
        self.assert_code("idempotency_conflict", restarted.submit_order,
                         "alice", "buy", "BTC-PERP", D("3"), D("100"))
        self.assert_code("idempotency_conflict", restarted.apply_fill,
                         "alice", "buy", "f1", D("1"), D("100"))
        self.assert_code("idempotency_conflict", restarted.deposit,
                         "alice", "initial", "USD", D("999"))

    def test_roundtrip_partial_close_reverse_and_exact_fees(self):
        self.order()
        self.fill()
        self.order("reduce", "-1", "110")
        self.fill("reduce", "f2", "-1", "110")
        self.order("reverse", "-2", "90")
        self.fill("reverse", "f3", "-2", "90")
        self.assertEqual(self.service.account("alice")["positions"]["BTC-PERP"]["quantity"], "-1")
        self.order("close", "1", "80")
        self.fill("close", "f4", "1", "80")
        account = self.service.account("alice")
        self.assertEqual(account["positions"], {})
        self.assertEqual(account["balances"]["USD"], "1009.772")
        self.assertEqual(account["open_order_margin"], "0")
        self.assertEqual(self.service.risk("alice")["equity"], "1009.772")

    def test_competing_connections_cannot_oversubscribe(self):
        self.service.create_account("small")
        self.service.deposit("small", "initial", "USD", D("10.04"))
        services = [self.reopen() for _ in range(8)]
        def admit(index):
            try:
                services[index].submit_order("small", f"o{index}", "BTC-PERP", D(1), D(100))
                return True
            except ServiceError as exc:
                self.assertEqual(exc.code, "insufficient_margin")
                return False
        with ThreadPoolExecutor(max_workers=8) as pool:
            admitted = list(pool.map(admit, range(8)))
        self.assertEqual(sum(admitted), 1)
        self.assertEqual(self.service.risk("small")["available_margin"], "0")

    def test_same_order_concurrent_retry_is_one_transition(self):
        services = [self.reopen() for _ in range(8)]
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda s: s.submit_order("alice", "same", "BTC-PERP", D(1), D(100)), services))
        self.assertTrue(all(result == results[0] for result in results))
        self.assertEqual(len([e for e in self.service.events(limit=1000) if e["event_type"] == "ORDER_ACCEPTED"]), 1)

    def test_failed_transition_rolls_back_ledger_positions_order_and_event(self):
        self.order()
        before_account, before_orders = self.service.account("alice"), self.service.orders("alice")
        before_journal, before_events = self.service.ledger.journal(), self.service.events(limit=1000)
        original = self.service._event
        def fail_after_mutation(connection, kind, account_id, payload):
            if kind == "FILL_APPLIED":
                raise RuntimeError("injected before commit")
            original(connection, kind, account_id, payload)
        with patch.object(self.service, "_event", side_effect=fail_after_mutation):
            with self.assertRaisesRegex(RuntimeError, "injected"):
                self.fill()
        self.assertEqual(self.service.account("alice"), before_account)
        self.assertEqual(self.service.orders("alice"), before_orders)
        self.assertEqual(self.service.ledger.journal(), before_journal)
        self.assertEqual(self.service.events(limit=1000), before_events)
        self.fill()
        self.assertEqual(self.service.account("alice")["positions"]["BTC-PERP"]["quantity"], "2")

    def test_market_monotonicity_expiry_repricing_and_retry(self):
        accepted = self.order(quantity="10")
        self.assertEqual(accepted["reserved_margin"], "100.4")
        self.service.publish_market(self.market(2, mark="200"))
        self.assertEqual(self.service.account("alice")["open_order_margin"], "200.4")
        self.assert_code("market_regression", self.service.publish_market, self.market(1))
        self.assert_code("market_conflict", self.service.publish_market, self.market(2, mark="201"))
        self.now += timedelta(seconds=6)
        self.assertFalse(self.service.readiness()["ready"])
        self.assert_code("market_unavailable", self.order, "new")
        self.assertEqual(self.order(quantity="10")["order_id"], "buy")
        # Existing ordinary local orders can settle during market outage.
        self.fill(quantity="10")
        self.assertEqual(self.service.account("alice")["positions"]["BTC-PERP"]["quantity"], "10")
        self.assertEqual(self.service.cancel_order("alice", "buy")["status"], "FILLED")

    def test_halt_persists_and_cancels_do_not_require_market(self):
        self.order()
        self.service.set_kill_switch(True)
        restarted = self.reopen()
        self.assertFalse(restarted.readiness()["ready"])
        self.assert_code("trading_halted", restarted.submit_order, "alice", "blocked", "BTC-PERP", D(1), D(100))
        self.now += timedelta(seconds=10)
        cancelled = restarted.cancel_order("alice", "buy")
        self.assertEqual(cancelled["status"], "CANCELLED")
        self.assertEqual(restarted.account("alice")["open_order_margin"], "0")
        self.assert_code("order_closed", self.fill)
        self.assertEqual(restarted.cancel_order("alice", "buy"), cancelled)

    def test_invalid_fills_leave_all_state_unchanged(self):
        self.order()
        before = self.service.events(limit=1000)
        for quantity, price in (("-1", "100"), ("3", "100"), ("1", "101"), ("0", "100")):
            with self.assertRaises(ServiceError):
                self.fill(quantity=quantity, price=price)
        self.assertEqual(self.service.events(limit=1000), before)
        self.assertEqual(self.service.account("alice")["positions"], {})
        self.assertEqual(self.service.ledger.verify(), 1)

    def test_reduce_only_quantity_allocation_and_position_change_cancellation(self):
        self.order()
        self.fill()
        self.order("reduce1", "-1", "100", reduce_only=True)
        self.order("reduce2", "-1", "100", reduce_only=True)
        self.assert_code("reduce_only_violation", self.order, "over", "-0.1", "100", reduce_only=True)
        self.order("ordinaryclose", "-2", "100")
        self.fill("ordinaryclose", "f2", "-2", "100")
        self.assertEqual([o["status"] for o in self.service.orders("alice") if o["reduce_only"]], ["CANCELLED", "CANCELLED"])
        self.assertEqual(self.service.account("alice")["positions"], {})
        self.assert_code("order_closed", self.fill, "reduce1", "f3", "-1", "100")

    def test_reduction_allowed_under_deficit_and_halt_but_not_equity_destruction(self):
        self.order(quantity="90")
        self.fill(quantity="90")
        self.service.publish_market(self.market(2, mark="90"))
        self.service.set_kill_switch(True)
        self.assertLess(D(self.service.risk("alice")["available_margin"]), 0)
        self.assert_code("unsafe_reduction", self.order, "badclose", "-90", "1", reduce_only=True)
        self.order("safeclose", "-90", "90", reduce_only=True)
        self.fill("safeclose", "f2", "-90", "90")
        self.assertEqual(self.service.account("alice")["positions"], {})
        self.assertEqual(self.service.account("alice")["balances"]["USD"], "93.16")

    def test_fee_is_invariant_to_microscopic_fill_partition(self):
        self.service.publish_market(self.market(2, mark="0.00000001"))
        self.order("micro", "0.00000003", "0.00000001")
        for index in range(3):
            self.fill("micro", f"micro{index}", "0.00000001", "0.00000001")
        fees = [D(event["payload"]["fee"]) for event in self.service.events(limit=1000)
                if event["event_type"] == "FILL_APPLIED"]
        self.assertEqual(fees, [D("0.00000001"), D(0), D(0)])
        self.assertEqual(self.service.account("alice")["balances"]["USD"], "999.99999999")

    def test_cost_basis_dust_preserves_sign_across_tiny_remaining_position(self):
        # Use an independent zero-fee database to isolate partial-close dust.
        other_path = Path(self.directory.name) / "zero.sqlite3"
        service = ExchangeService(Database(other_path), {"USD": 8}, clock=lambda: self.now, fee_rate=D(0))
        service.create_account("a")
        service.publish_market(self.market(mark="1"))
        service.set_kill_switch(False)
        service.deposit("a", "d", "USD", D(10))
        for index, (q, p) in enumerate((("1", "0.00000001"), ("0.00000001", "0.00000002"), ("-1", "1"), ("-0.00000001", "1"))):
            service.submit_order("a", str(index), "BTC-PERP", D(q), D(p))
            service.apply_fill("a", str(index), str(index), D(q), D(p))
        self.assertEqual(service.account("a")["balances"]["USD"], "10.99999999")
        self.assertEqual(service.account("a")["positions"], {})

    def test_low_decimal_context_and_traps_do_not_change_financial_results(self):
        with localcontext() as context:
            context.prec = 1
            context.traps[Inexact] = True
            self.order()
            self.fill(quantity="1")
            self.fill(fill_id="f2", quantity="1")
            self.assertEqual(self.service.risk("alice")["equity"], "999.92")
            self.assert_code("invalid_input", self.order, "huge", "1000000000000.00000001")

    def test_policy_conflict_missing_specs_and_input_limits(self):
        self.assert_code("configuration_conflict", self.reopen, fee_rate=D("0.001"))
        self.assert_code("invalid_input", self.order, "boolean", reduce_only=1)
        self.assert_code("invalid_input", self.service.submit_order, "alice", "number", "BTC-PERP", 1.0, D(100))
        self.assert_code("invalid_input", self.service.deposit, "alice", "subscale", "USD", D("0.000000001"))
        self.service.deposit("alice", "btc", "BTC", D("1"))
        incomplete = MarketSnapshot(2, self.now, {"USD": AssetSpec(D(1), D(1))}, self.market().instruments)
        self.assert_code("market_incomplete", self.service.publish_market, incomplete)


if __name__ == "__main__":
    unittest.main()
