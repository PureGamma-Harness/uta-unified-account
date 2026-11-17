"""Small literal financial standards; no production calculation generates expectations."""
from datetime import datetime, timezone
from decimal import Decimal as D, Inexact, Rounded, localcontext
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from uta.credit import CreditService
from uta.ledger import Ledger, LedgerError, Posting
from uta.market import MarketSnapshot
from uta.models import Account, AssetSpec, InstrumentSpec, Position, RiskInputError
from uta.risk import calculate_risk
from uta.service import ExchangeService, ServiceError, _amount, _exact
from uta.storage import Database, DurableLedger


class NumericContractReferenceTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name)
        self.now = datetime(2026, 11, 17, tzinfo=timezone.utc)

    def exchange(self, name="financial.sqlite3", *, fee="0", scales=None):
        service = ExchangeService(Database(self.path / name), scales or {"USD": 2},
                                  clock=lambda: self.now, fee_rate=D(fee))
        service.publish_market(MarketSnapshot(1, self.now,
            {"USD": AssetSpec(D(1), D(1)), "ATOM": AssetSpec(D(1), D(".5"))},
            {"X-PERP": InstrumentSpec(D(1), D(".1"), D(".05"))}))
        service.set_kill_switch(False)
        return service

    @staticmethod
    def postings(asset, value):
        return [Posting("customer", asset, value), Posting("external", asset, value.copy_negate())]

    def test_asset_minimum_units_are_exact_and_subunits_are_atomic_rejections(self):
        # Each tuple is a separately hand-specified currency contract.
        cases = ((0, "1", ".1"), (2, ".01", ".001"),
                 (8, ".00000001", ".000000001"),
                 (18, ".000000000000000001", ".0000000000000000001"))
        for scale, atom, subatom in cases:
            with self.subTest(scale=scale):
                ledger = DurableLedger(Database(self.path / f"scale{scale}.sqlite3"), {"UNIT": scale})
                ledger.post("one", self.postings("UNIT", D(atom)))
                before = ledger.journal()
                with self.assertRaises(LedgerError):
                    ledger.post("retry", self.postings("UNIT", D(subatom)))
                self.assertEqual(ledger.journal(), before)
                ledger.post("retry", self.postings("UNIT", D(atom).copy_negate()))
                self.assertEqual(ledger.balance("customer", "UNIT"), D(0))
                self.assertEqual(ledger.balance("external", "UNIT"), D(0))
                self.assertEqual(ledger.verify(), 2)

    def test_38_digit_unit_boundary_is_strict_and_overflow_preserves_id(self):
        # 38 decimal digits are only a 127-bit integer, not a resource stress case.
        largest = D("99999999999999999999.999999999999999999")
        atom = D(".000000000000000001")
        for kind in ("memory", "durable"):
            with self.subTest(kind=kind):
                ledger = (Ledger({"UNIT": 18}) if kind == "memory" else
                          DurableLedger(Database(self.path / "limit.sqlite3"), {"UNIT": 18}))
                ledger.post("largest", self.postings("UNIT", largest))
                before = ledger.journal()
                with self.assertRaises(LedgerError):
                    ledger.post("reusable", self.postings("UNIT", atom))
                self.assertEqual(ledger.journal(), before)
                self.assertEqual(ledger.balance("customer", "UNIT"), largest)
                ledger.post("reusable", self.postings("UNIT", atom.copy_negate()))
                self.assertEqual(ledger.balance("customer", "UNIT"),
                                 D("99999999999999999999.999999999999999998"))

    def test_ledger_representation_envelope_is_separate_from_numeric_equality(self):
        codec = Ledger({"UNIT": 0})
        self.assertEqual(codec._units("UNIT", D("1E+37")), 10**37)
        self.assertEqual(codec._units("UNIT", D("0E-38")), 0)
        for value in (D("1E+38"), D("0E-39"), D("1." + "0" * 38)):
            with self.subTest(value=str(value)), self.assertRaises(LedgerError):
                codec._units("UNIT", value)
        with self.assertRaises(LedgerError):
            codec.post("zero", self.postings("UNIT", D("-0")))
        self.assertEqual(codec.journal(), ())

    def test_trading_input_envelope_is_stricter_than_the_asset_codec(self):
        for value in (D(".00000001"), D("1000000000000"), D("1")):
            self.assertEqual(_amount(value, "quantity", positive=True), value)
        for value in (D(".000000001"), D("1000000000000.00000001"),
                      D("1.000000000"), D("NaN"), D("Infinity"), D("-0"), True, 1.0):
            with self.subTest(value=str(value)), self.assertRaises(ServiceError) as rejected:
                _amount(value, "quantity", positive=True)
            self.assertEqual(rejected.exception.code, "invalid_input")

    def test_18_place_credit_and_8_place_deposit_are_distinct_existing_contracts(self):
        service = self.exchange(scales={"USD": 2, "ATOM": 18})
        service.create_account("a")
        service.deposit("a", "usd", "USD", D(100))
        with self.assertRaises(ServiceError) as rejected:
            service.deposit("a", "subdeposit", "ATOM", D(".000000000000000001"))
        self.assertEqual(rejected.exception.code, "invalid_input")
        credit = CreditService(service)
        credit.configure_asset_limit("ATOM", D(".000000000000000010"))
        credit.configure_limit("a", "ATOM", D(".000000000000000010"))
        credit.fund_pool("pool", "ATOM", D(".000000000000000010"),
                         source_reference="synthetic:numeric-contract:atom")
        with localcontext() as context:
            context.prec = 1
            context.Emax, context.Emin = 2, -2
            context.traps[Inexact] = context.traps[Rounded] = True
            credit.borrow("a", "borrow", "ATOM", D(".000000000000000002"))
            credit.repay("a", "repay", "ATOM", D(".000000000000000001"))
        self.assertEqual(service.account("a")["balances"]["ATOM"], "0.000000000000000001")
        self.assertEqual(service.account("a")["liabilities"]["ATOM"]["principal"], "0.000000000000000001")
        self.assertEqual(service.ledger.balance("system:credit-pool", "ATOM"), D(".000000000000000009"))
        self.assertEqual(credit.verify()["nonzero_liabilities"], 1)

    def test_market_precision_is_bounded_and_does_not_adopt_trading_input_limits(self):
        for value in (D("1E+100"), D("1E-100"), D("9" * 80 + "E-79")):
            self.assertEqual(AssetSpec(value, D(1)).price, value)
        for value in (D("1E+101"), D("1E-101"), D("1." + "0" * 80), D("NaN")):
            with self.subTest(value=str(value)), self.assertRaises(RiskInputError):
                AssetSpec(value, D(1))

    def test_settlement_floor_and_fee_ceiling_ignore_caller_context(self):
        service = self.exchange()
        cases = ((Fraction(1, 1000), "0", ".01"),
                 (Fraction(-1, 1000), "-.01", "0"),
                 (Fraction(11, 1000), ".01", ".02"),
                 (Fraction(-11, 1000), "-.02", "-.01"))
        with localcontext() as context:
            context.prec = 1
            context.Emax, context.Emin = 2, -2
            context.traps[Inexact] = context.traps[Rounded] = True
            for exact, floor, ceiling in cases:
                self.assertEqual(service._rounded(exact), D(floor))
                self.assertEqual(service._rounded(exact, ceiling=True), D(ceiling))
            self.assertEqual(_exact(Fraction(1, 8)), D(".125"))
            with self.assertRaises(ServiceError) as rejected:
                _exact(Fraction(1, 3))
            self.assertEqual((rejected.exception.code, rejected.exception.status), ("precision_error", 409))

    def test_cumulative_fee_partition_keeps_one_cent_not_three(self):
        service = self.exchange(fee=".0004")
        for account in ("whole", "split"):
            service.create_account(account)
            service.deposit(account, "usd", "USD", D(100))
            service.submit_order(account, "buy", "X-PERP", D(3), D(1))
        service.apply_fill("whole", "buy", "whole", D(3), D(1))
        for index in range(3):
            service.apply_fill("split", "buy", str(index), D(1), D(1))
        fees = [row["payload"]["fee"] for row in service.events(limit=1000)
                if row["event_type"] == "FILL_APPLIED" and row["account_id"] == "split"]
        self.assertEqual(fees, ["0.01", "0", "0"])
        self.assertEqual(service.account("whole")["balances"]["USD"], "99.99")
        self.assertEqual(service.account("split")["balances"]["USD"], "99.99")
        self.assertEqual(service.ledger.balance("system:fees", "USD"), D(".02"))
        self.assertEqual(service.ledger.verify(), 4)

    def test_partial_close_carries_rounding_dust_into_remaining_cost(self):
        cases = (("gain", "1.006", ["0", "0", ".01"], "100.01", "-.02"),
                 ("loss", ".994", ["-.01", "-.01", "0"], "99.98", ".04"))
        for name, close, expected, cash, counterpart in cases:
            with self.subTest(name=name):
                service = self.exchange(name + ".sqlite3")
                for account in ("whole", "split"):
                    service.create_account(account)
                    service.deposit(account, "usd", "USD", D(100))
                    service.submit_order(account, "open", "X-PERP", D(3), D(1))
                    service.apply_fill(account, "open", "open", D(3), D(1))
                    service.submit_order(account, "close", "X-PERP", D(-3), D(close), reduce_only=True)
                service.apply_fill("whole", "close", "close", D(-3), D(close))
                for index in range(3):
                    service.apply_fill("split", "close", "close" + str(index), D(-1), D(close))
                realized = [D(row["payload"]["realized_pnl"]) for row in service.events(limit=1000)
                            if row["event_type"] == "FILL_APPLIED" and row["account_id"] == "split"
                            and row["payload"]["order"]["order_id"] == "close"]
                self.assertEqual(realized, list(map(D, expected)))
                for account in ("whole", "split"):
                    self.assertEqual(service.account(account)["balances"]["USD"], cash)
                    self.assertEqual(service.account(account)["positions"], {})
                self.assertEqual(service.ledger.balance("system:realized-pnl", "USD"), D(counterpart))
                service.ledger.verify()

    def test_display_ratio_can_equal_one_while_exact_amounts_are_above_mm(self):
        almost = D("1.0000000000000000000000000000000000000001")
        snapshot = calculate_risk(Account(balances={"USD": almost},
            positions={"X": Position("X", D(1), D(1))}),
            {"USD": AssetSpec(D(1), D(1))}, {"X": InstrumentSpec(D(1), D(1), D(1))})
        self.assertEqual(snapshot.margin_ratio, D(1))  # Display-only half-even34.
        self.assertEqual(snapshot.available_margin, D("1E-40"))
        self.assertEqual(Fraction(snapshot.equity) - Fraction(snapshot.maintenance_margin), Fraction(1, 10**40))
        for equity in (D(0), D(-1)):
            zero_mm = calculate_risk(Account(balances={"USD": equity}),
                                     {"USD": AssetSpec(D(1), D(1))}, {})
            self.assertIsNone(zero_mm.margin_ratio)
            self.assertEqual(zero_mm.equity, equity)


if __name__ == "__main__":
    unittest.main()
