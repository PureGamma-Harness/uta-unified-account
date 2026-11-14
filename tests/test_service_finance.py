"""Public-service financial invariants, checked against exact cash flows.

These cases deliberately include tiny residual positions and split executions;
ordinary average-entry examples do not expose settlement-rounding mistakes.
"""
from datetime import datetime, timezone
from decimal import Decimal as D, Inexact, Rounded, localcontext
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ExchangeService, ServiceError
from uta.storage import Database


class ServiceFinanceTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.now = datetime(2026, 11, 14, 12, tzinfo=timezone.utc)

    def service(self, *, scale=8, fee="0", mark="1", funds="10000"):
        path = Path(self.directory.name) / f"service-{len(list(Path(self.directory.name).glob('*.db')))}.db"
        service = ExchangeService(Database(path), {"USD": scale}, clock=lambda: self.now, fee_rate=D(fee))
        service.publish_market(MarketSnapshot(1, self.now, {"USD": AssetSpec(D("1"), D("1"))},
                                              {"X": InstrumentSpec(D(mark), D("0.1"), D("0.05"))}))
        service.create_account("alice")
        service.deposit("alice", "initial", "USD", D(funds))
        service.set_kill_switch(False)
        return service

    @staticmethod
    def execute(service, index, quantity, price):
        order = f"order-{index}"
        service.submit_order("alice", order, "X", D(quantity), D(price))
        service.apply_fill("alice", order, f"fill-{index}", D(quantity), D(price))

    def assert_flat_cash_conservation(self, fills):
        service = self.service()
        exact_pnl = Fraction(0)
        for index, (quantity, price) in enumerate(fills):
            self.execute(service, index, quantity, price)
            exact_pnl -= Fraction(quantity) * Fraction(price)
        account = service.account("alice")
        self.assertEqual(account["positions"], {})
        booked_pnl = Fraction(D(account["balances"]["USD"])) - 10000
        # The final close may transfer less than one minor unit of residual dust
        # to the exchange, but splitting a close must not multiply that dust.
        self.assertGreaterEqual(exact_pnl - booked_pnl, 0)
        self.assertLess(exact_pnl - booked_pnl, Fraction(1, 10**8))
        self.assertEqual(service.risk("alice")["equity"], account["balances"]["USD"])
        service.ledger.verify()

    def test_tiny_long_residual_preserves_signed_cost_rounding_dust(self):
        self.assert_flat_cash_conservation([
            ("1", "0.00000001"), ("0.00000001", "0.00000002"),
            ("-1", "1"), ("-0.00000001", "1"),
        ])

    def test_partial_average_and_position_flip_conserve_cash(self):
        # Average entry starts at 5/3, then a partial reduction and a flip.
        self.assert_flat_cash_conservation([
            ("1", "1"), ("2", "2"), ("-0.5", "3"),
            ("-3.5", "2"), ("1", "1"),
        ])

    def test_short_average_and_partial_reductions_conserve_cash(self):
        self.assert_flat_cash_conservation([
            ("-1", "1"), ("-2", "2"), ("0.5", "3"),
            ("1.5", "2"), ("1", "1"),
        ])

    def test_split_fills_cannot_multiply_reserved_fee(self):
        service = self.service(scale=2, fee="0.0004", funds="0.11")
        accepted = service.submit_order("alice", "split", "X", D("1"), D("1"))
        self.assertEqual(D(accepted["reserved_margin"]), D("0.11"))
        for index in range(100):
            service.apply_fill("alice", "split", f"split-{index}", D("0.01"), D("1"))
        account = service.account("alice")
        self.assertEqual(D(account["balances"]["USD"]), D("0.10"))
        self.assertGreaterEqual(D(service.risk("alice")["available_margin"]), 0)
        self.assertEqual(sum((D(event["payload"]["fee"]) for event in service.events(limit=1000)
                              if event["event_type"] == "FILL_APPLIED"), D("0")), D("0.01"))

    def test_opposite_queued_orders_never_net_margin_reservations(self):
        service = self.service(funds="0.15")
        service.submit_order("alice", "buy", "X", D("1"), D("1"))
        with self.assertRaises(ServiceError) as rejected:
            service.submit_order("alice", "sell", "X", D("-1"), D("1"))
        self.assertEqual(rejected.exception.code, "insufficient_margin")
        self.assertEqual(len(service.orders("alice")), 1)
        self.assertEqual(D(service.risk("alice")["open_order_margin"]), D("0.1"))

    def test_market_advance_revalues_pending_orders_before_admission(self):
        service = self.service(funds="0.15")
        service.submit_order("alice", "buy", "X", D("1"), D("1"))
        service.publish_market(MarketSnapshot(2, self.now, {"USD": AssetSpec(D("1"), D("1"))},
                                              {"X": InstrumentSpec(D("2"), D("0.1"), D("0.05"))}))
        self.assertEqual(D(service.risk("alice")["open_order_margin"]), D("0.2"))
        with self.assertRaises(ServiceError) as rejected:
            service.submit_order("alice", "second", "X", D("0.01"), D("2"))
        self.assertEqual(rejected.exception.code, "insufficient_margin")

    def test_low_decimal_context_cannot_change_money_or_input_limits(self):
        service = self.service()
        with localcontext() as context:
            context.prec = 2
            context.traps[Inexact] = True
            context.traps[Rounded] = True
            self.execute(service, 1, "0.12345678", "1.23456789")
            with self.assertRaises(ServiceError) as rejected:
                service.deposit("alice", "oversize", "USD", D("1000000000000.01"))
            self.assertEqual(rejected.exception.code, "invalid_input")
        account = service.account("alice")
        self.assertEqual(D(account["positions"]["X"]["quantity"]), D("0.12345678"))
        expected_cost = Fraction("0.12345678") * Fraction("1.23456789")
        self.assertEqual(Fraction(account["positions"]["X"]["cost_basis"]), expected_cost)


if __name__ == "__main__":
    unittest.main()
