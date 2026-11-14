"""Independent accounting and admission checks for the persistent UTA path."""
import os
import random
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D, Inexact, ROUND_UP, localcontext
from fractions import Fraction

from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ExchangeService, ServiceError
from uta.storage import Database, DurableLedger


NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)


class ExchangeAccountingInvariants(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = os.path.join(self.directory.name, "exchange.sqlite3")
        self.scales = {"USD": 8}
        self.now = NOW
        self.service = self.make_service()
        self.market_version = 0
        self.publish("100")
        self.service.set_kill_switch(False)
        self.service.create_account("alice")
        self.service.deposit("alice", "initial-funding", "USD", D("1000"))

    def make_service(self, *, fee_rate=D("0.0004")):
        return ExchangeService(Database(self.path), self.scales,
                               clock=lambda: self.now, fee_rate=fee_rate)

    def publish(self, mark):
        self.market_version += 1
        self.service.publish_market(MarketSnapshot(
            self.market_version, self.now,
            {"USD": AssetSpec(D("1"), D("1"))},
            {"BTC-PERP": InstrumentSpec(D(mark), D("0.1"), D("0.05"))}))

    def execute(self, order_id, quantity, price, *, account_id="alice"):
        self.service.submit_order(account_id, order_id, "BTC-PERP", D(quantity), D(price))
        return self.service.apply_fill(account_id, order_id, "fill-" + order_id,
                                       D(quantity), D(price))

    def test_hand_computed_partial_close_reverse_and_restart(self):
        # Four executions realise 10 USD and charge 0.228 USD total fees.
        self.execute("buy", "2", "100")
        self.now += timedelta(seconds=1); self.publish("110")
        self.execute("partial-close", "-1", "110")
        self.now += timedelta(seconds=1); self.publish("90")
        self.execute("reverse", "-2", "90")
        self.assertEqual(self.service.account("alice")["positions"]["BTC-PERP"]["quantity"], "-1")
        self.now += timedelta(seconds=1); self.publish("80")
        self.execute("close-short", "1", "80")
        expected = self.service.account("alice")
        self.assertEqual(D(expected["balances"]["USD"]), D("1009.772"))
        self.assertEqual(expected["positions"], {})
        self.assertEqual(D(expected["open_order_margin"]), D("0"))
        self.assertEqual(self.make_service().account("alice"), expected)
        journal = DurableLedger(Database(self.path), self.scales)
        self.assertGreaterEqual(journal.verify(), 5)
        for event in journal.journal():
            totals = {}
            for posting in event.postings:
                totals[posting.asset] = totals.get(posting.asset, Fraction(0)) + Fraction(posting.amount)
            self.assertTrue(all(total == 0 for total in totals.values()))

    def test_successful_fill_retry_survives_stale_market_and_global_halt(self):
        self.service.submit_order("alice", "executed", "BTC-PERP", D("1"), D("100"))
        self.service.apply_fill("alice", "executed", "confirmed", D("1"), D("100"))
        self.service.submit_order("alice", "unexecuted", "BTC-PERP", D("1"), D("100"))
        self.service.set_kill_switch(True)
        self.now += timedelta(minutes=1)
        before = self.service.account("alice")
        events = self.service.events(limit=1000)
        self.assertEqual(self.make_service().apply_fill("alice", "executed", "confirmed",
                                                       D("1.00"), D("100.00"))["status"], "FILLED")
        for operation in (
            lambda: self.service.apply_fill("alice", "unexecuted", "new", D("1"), D("100")),
            lambda: self.service.submit_order("alice", "new-risk", "BTC-PERP", D("1"), D("100")),
        ):
            with self.assertRaises(ServiceError):
                operation()
            self.assertEqual(self.service.account("alice"), before)
            self.assertEqual(self.service.events(limit=1000), events)

    def test_process_exit_before_commit_recovers_entire_fill_atomically(self):
        self.service.submit_order("alice", "crash", "BTC-PERP", D("1"), D("100"))
        before = self.service.account("alice")
        orders = self.service.orders("alice")
        journal = self.service.ledger.journal()
        events = self.service.events(limit=1000)
        code = r"""
import os, sys
from datetime import datetime
from decimal import Decimal as D
from uta.service import ExchangeService
from uta.storage import Database
service = ExchangeService(Database(sys.argv[1]), {"USD":8}, clock=lambda: datetime.fromisoformat(sys.argv[2]))
original = service._event

def exit_before_commit(connection, kind, account_id, payload):
    if kind == "FILL_APPLIED":
        os._exit(77)
    original(connection, kind, account_id, payload)

service._event = exit_before_commit
service.apply_fill("alice", "crash", "crash-fill", D("1"), D("100"))
"""
        import uta.service
        package_root = str(Path(uta.service.__file__).resolve().parent.parent)
        result = subprocess.run([sys.executable, "-c", code, self.path, self.now.isoformat()],
                                cwd=package_root, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 77, result.stderr)
        restarted = self.make_service()
        self.assertEqual(restarted.account("alice"), before)
        self.assertEqual(restarted.orders("alice"), orders)
        self.assertEqual(restarted.ledger.journal(), journal)
        self.assertEqual(restarted.events(limit=1000), events)
        restarted.apply_fill("alice", "crash", "crash-fill", D("1"), D("100"))
        self.assertEqual(D(restarted.account("alice")["balances"]["USD"]), D("999.96"))

    def test_rejected_fill_and_conflicting_retry_leave_no_partial_state(self):
        self.service.submit_order("alice", "order", "BTC-PERP", D("1"), D("100"))
        before = self.service.account("alice")
        events = self.service.events(limit=1000)
        for quantity, price in (("2", "100"), ("-1", "100"), ("1", "100.01")):
            with self.subTest(quantity=quantity, price=price), self.assertRaises(ServiceError):
                self.service.apply_fill("alice", "order", "bad", D(quantity), D(price))
            self.assertEqual(self.service.account("alice"), before)
            self.assertEqual(self.service.events(limit=1000), events)
        self.service.apply_fill("alice", "order", "fill", D("1"), D("100"))
        after = self.service.account("alice")
        events = self.service.events(limit=1000)
        with self.assertRaises(ServiceError):
            self.service.apply_fill("alice", "order", "fill", D("1"), D("99"))
        self.assertEqual(self.service.account("alice"), after)
        self.assertEqual(self.service.events(limit=1000), events)

    def test_current_market_revalues_outstanding_order_reservations(self):
        self.service.create_account("limited")
        self.service.deposit("limited", "fund", "USD", D("20"))
        self.service.submit_order("limited", "old", "BTC-PERP", D("1"), D("100"))
        self.now += timedelta(seconds=1); self.publish("1000")
        risk = self.service.risk("limited")
        self.assertGreaterEqual(D(risk["open_order_margin"]), D("100"))
        self.assertLess(D(risk["available_margin"]), D("0"))
        with self.assertRaises(ServiceError):
            self.service.submit_order("limited", "next", "BTC-PERP", D("0.01"), D("1000"))

    def test_independent_service_instances_serialize_admission(self):
        self.service.create_account("limited")
        self.service.deposit("limited", "fund", "USD", D("25"))
        peers = [self.make_service() for _ in range(8)]

        def admit(index):
            try:
                peers[index].submit_order("limited", "order-" + str(index), "BTC-PERP", D("1"), D("100"))
                return True
            except ServiceError as exc:
                self.assertEqual(exc.code, "insufficient_margin")
                return False

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(admit, range(8)))
        self.assertEqual(sum(results), 2)
        self.assertEqual(len(self.service.orders("limited")), 2)
        self.assertGreaterEqual(D(self.service.risk("limited")["available_margin"]), D("0"))

    def test_admission_and_settlement_ignore_ambient_decimal_context(self):
        with localcontext() as context:
            context.prec = 1
            context.rounding = ROUND_UP
            context.Emax = 2
            context.traps[Inexact] = True
            self.execute("context", "1.23456789", "100")
        account = self.service.account("alice")
        self.assertEqual(D(account["balances"]["USD"]), D("999.95061728"))
        self.assertEqual(D(account["positions"]["BTC-PERP"]["quantity"]), D("1.23456789"))

    def test_per_order_fee_is_independent_of_fill_splitting(self):
        # A split must not exhaust collateral through repeated cent ceilings.
        with tempfile.TemporaryDirectory() as directory:
            service = ExchangeService(Database(os.path.join(directory, "split.sqlite3")), {"USD": 2},
                                      clock=lambda: NOW)
            service.publish_market(MarketSnapshot(1, NOW, {"USD": AssetSpec(D(1), D(1))},
                                                   {"ONE": InstrumentSpec(D(1), D("0.1"), D("0.05"))}))
            service.set_kill_switch(False)
            for account in ("single", "split"):
                service.create_account(account)
                service.deposit(account, "fund", "USD", D("1.01"))
                service.submit_order(account, "order", "ONE", D("10"), D("1"))
            service.apply_fill("single", "order", "fill", D("10"), D("1"))
            for index in range(10):
                service.apply_fill("split", "order", str(index), D("1"), D("1"))
            for account in ("single", "split"):
                self.assertEqual(D(service.account(account)["balances"]["USD"]), D("1.00"))
                self.assertGreaterEqual(D(service.risk(account)["available_margin"]), D("0"))

    def test_seeded_round_trips_match_independent_cashflow_calculator(self):
        # No average-entry formula is reused: once flat, PnL is the net cashflow
        # from all executions in that position cycle. Partial-close dust must
        # therefore settle to the same final floor, regardless of the split.
        generator = random.Random(438216)
        expected = Fraction(1000)
        quantum = 10 ** self.scales["USD"]
        order_number = 0
        for cycle in range(24):
            direction = 1 if cycle % 2 == 0 else -1
            open_parts = [generator.randint(1, 5) for _ in range(generator.randint(2, 4))]
            remaining = sum(open_parts)
            close_parts = []
            while remaining:
                part = generator.randint(1, remaining)
                close_parts.append(part)
                remaining -= part
            cashflow = Fraction(0)
            fees = Fraction(0)
            for signed_part in ([direction * part for part in open_parts] +
                                [-direction * part for part in close_parts]):
                order_number += 1
                quantity = D(signed_part) / D("100")
                price = D(generator.randint(80, 120)) + D(generator.randint(1, 9)) / D("100000000")
                self.publish(str(price))
                self.execute("random-" + str(order_number), str(quantity), str(price))
                cashflow -= Fraction(quantity) * Fraction(price)
                raw_fee_units = abs(Fraction(quantity)) * Fraction(price) * Fraction("0.0004") * quantum
                fees += Fraction(-((-raw_fee_units.numerator) // raw_fee_units.denominator), quantum)
            pnl_units = cashflow * quantum
            expected += Fraction(pnl_units.numerator // pnl_units.denominator, quantum) - fees
            current = self.service.account("alice")
            self.assertEqual(current["positions"], {}, "cycle must end flat")
            self.assertEqual(Fraction(D(current["balances"]["USD"])), expected,
                             "round-trip cashflow disagrees at cycle " + str(cycle))
        DurableLedger(Database(self.path), self.scales).verify()

    def test_signed_cost_basis_dust_cannot_create_an_extra_rounding_loss(self):
        # The first close carries sub-cent realised gain into signed basis.
        # A later close must use that sign, even when the effective basis is <0.
        with tempfile.TemporaryDirectory() as directory:
            service = ExchangeService(Database(os.path.join(directory, "dust.sqlite3")), {"USD": 2},
                                      clock=lambda: NOW, fee_rate=D("0"))
            service.set_kill_switch(False)
            service.create_account("dust")
            service.deposit("dust", "fund", "USD", D("1"))
            for index, quantity, price in ((1, "0.03", "0.01"), (2, "-0.01", "0.04"), (3, "-0.02", "1")):
                service.publish_market(MarketSnapshot(index, NOW, {"USD": AssetSpec(D(1), D(1))},
                                                       {"ONE": InstrumentSpec(D(price), D("0.1"), D("0.05"))}))
                service.submit_order("dust", str(index), "ONE", D(quantity), D(price))
                service.apply_fill("dust", str(index), str(index), D(quantity), D(price))
            self.assertEqual(service.account("dust")["positions"], {})
            self.assertEqual(D(service.account("dust")["balances"]["USD"]), D("1.02"))


if __name__ == "__main__":
    unittest.main()
