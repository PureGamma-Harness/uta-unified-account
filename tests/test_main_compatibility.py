"""Compatibility contracts between the research lab and durable exchange core."""
from contextlib import closing
from decimal import Decimal as D, Inexact, localcontext
import json
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from uta.ledger import Ledger, LedgerError, Posting
from uta.models import Account, AssetSpec, InstrumentSpec, Position, RiskInputError
from uta.risk import calculate_risk, check_order
from uta.storage import Database, DurableLedger


class MainCompatibilityTests(unittest.TestCase):
    def test_research_wide_units_do_not_change_durable_default_range(self):
        amount = D("1" + "0" * 50)
        postings = (Posting("a", "USD", amount), Posting("b", "USD", amount.copy_negate()))
        wide = Ledger({"USD": 0}, unit_digits=60)
        wide.post("research-only", postings)
        self.assertEqual(wide.balance("a", "USD"), amount)
        self.assertEqual(Ledger._LIMIT, 10 ** 38)
        with self.assertRaises(LedgerError):
            Ledger({"USD": 0}).post("out-of-default-range", postings)
        with TemporaryDirectory() as directory:
            durable = DurableLedger(Database(Path(directory) / "exchange.sqlite3"), {"USD": 0})
            with self.assertRaises(LedgerError):
                durable.post("out-of-durable-range", postings)
            self.assertEqual(durable.verify(), 0)
            durable.post("bounded", (Posting("a", "USD", D("7")), Posting("b", "USD", D("-7"))))
            self.assertEqual(durable.verify(), 1)

    def test_authoritative_entry_notional_preserves_exact_fifo_cost(self):
        balances = {"USD": D("1000")}
        positions = {"X": Position("X", D("3"), D("33.3333333"), D("100"))}
        account = Account(balances, positions)
        balances["USD"] = D("0")
        positions.clear()
        assets = {"USD": AssetSpec(D("1"), D("1"))}
        instruments = {"X": InstrumentSpec(D("40"), D("0.1"), D("0.05"))}
        with localcontext() as context:
            context.prec = 2
            context.traps[Inexact] = True
            risk = calculate_risk(account, assets, instruments)
            self.assertEqual((risk.equity, risk.initial_margin), (D("1020"), D("12")))
            checked = check_order(account, assets, instruments, symbol="X", quantity=D("1"), execution_price=D("40"))
            self.assertEqual((checked.projected_equity, checked.projected_initial_margin), (D("1020"), D("16")))
        with self.assertRaises(TypeError):
            account.balances["USD"] = D("999")

    def test_entry_notional_and_decimal_bounds_still_reject_malformed_research_inputs(self):
        for quantity, cost in ((D("0"), D("1")), (D("1"), D("-1")), (D("-1"), D("1"))):
            with self.assertRaises(RiskInputError):
                Position("X", quantity, D("1"), cost)
        with self.assertRaises(RiskInputError):
            Position("X", D("1"), D("1"), D("1e101"))

    def test_json_serialization_handles_immutable_account_mappings(self):
        from uta.api import json_value
        account = Account({"USD": D("10.25")}, {"X": Position("X", D("1"), D("7"), D("7"))})
        encoded = json_value(account)
        self.assertEqual(encoded["balances"], {"USD": "10.25"})
        self.assertEqual(encoded["positions"]["X"]["entry_notional"], "7")
        self.assertEqual(json.loads(json.dumps(encoded)), encoded)
        self.assertEqual(account.balances["USD"], D("10.25"))

    @staticmethod
    def logical_dump(path):
        with closing(sqlite3.connect(path)) as connection, connection:
            return tuple(connection.iterdump())

    def test_research_database_cannot_be_opened_as_exchange_and_remains_unchanged(self):
        from uta.service import ExchangeService, ServiceError
        from uta.store import Store
        with TemporaryDirectory() as directory:
            path = Path(directory) / "lab.sqlite3"
            store = Store(path)
            store.create("alice", {"units": 1000})
            # Exchange state files must also satisfy the OS permission policy;
            # exercise the separate authority check after that boundary passes.
            os.chmod(path, 0o600)
            before = self.logical_dump(path)
            with self.assertRaises(ServiceError) as rejected:
                ExchangeService(Database(path), {"USD": 8})
            self.assertEqual(rejected.exception.code, "wrong_authority")
            self.assertEqual(self.logical_dump(path), before)
            self.assertEqual(Store(path).read("alice"), {"units": 1000, "version": 0})

    def test_exchange_database_cannot_be_opened_as_research_and_remains_unchanged(self):
        from uta.credit import CreditService
        from uta.service import ExchangeService
        from uta.store import Store, StoreConflict
        with TemporaryDirectory() as directory:
            path = Path(directory) / "exchange.sqlite3"
            exchange = ExchangeService(Database(path), {"USD": 8})
            exchange.create_account("alice")
            exchange.deposit("alice", "synthetic-deposit", "USD", D("10"))
            credit = CreditService(exchange)
            credit.fund_pool("fund", "USD", D("5"), source_reference="synthetic:compat:fund")
            before = self.logical_dump(path)
            with self.assertRaises(StoreConflict):
                Store(path)
            self.assertEqual(self.logical_dump(path), before)
            self.assertEqual(exchange.account("alice")["balances"]["USD"], "10")
            self.assertEqual(credit.verify()["nonzero_liabilities"], 0)

    def test_existing_research_schema_without_marker_is_reopened_losslessly(self):
        from uta.store import Store
        with TemporaryDirectory() as directory:
            path = Path(directory) / "legacy-lab.sqlite3"
            original = Store(path)
            original.create("alice", {"units": 17})
            events = original.events("alice")
            with closing(sqlite3.connect(path)) as connection, connection:
                connection.execute("DROP TABLE uta_authority")
            reopened = Store(path)
            self.assertEqual(reopened.read("alice"), {"units": 17, "version": 0})
            self.assertEqual(reopened.events("alice"), events)

    def test_existing_exchange_schema_without_marker_is_reopened_losslessly(self):
        from uta.service import ExchangeService
        with TemporaryDirectory() as directory:
            path = Path(directory) / "legacy-exchange.sqlite3"
            original = ExchangeService(Database(path), {"USD": 8})
            original.create_account("alice")
            original.deposit("alice", "deposit", "USD", D("17"))
            account, events = original.account("alice"), original.events()
            with closing(sqlite3.connect(path)) as connection, connection:
                connection.execute("DROP TABLE uta_authority")
            reopened = ExchangeService(Database(path), {"USD": 8})
            self.assertEqual(reopened.account("alice"), account)
            self.assertEqual(reopened.events(), events)


if __name__ == "__main__":
    unittest.main()
