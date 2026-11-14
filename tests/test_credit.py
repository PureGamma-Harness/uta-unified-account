from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D, Inexact, localcontext
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from uta.credit import CreditService
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ExchangeService, ServiceError
from uta.storage import Database


class CreditTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "credit.sqlite3"
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.exchange = self.reopen()
        self.exchange.create_account("alice")
        self.exchange.create_account("bob")
        self.exchange.publish_market(self.market())
        self.exchange.set_kill_switch(False)
        self.exchange.deposit("alice", "initial", "USD", D("1000"))
        self.exchange.deposit("bob", "initial", "USD", D("1000"))
        self.credit = CreditService(self.exchange)
        self.credit.configure_asset_limit("BTC", D("100"))
        self.credit.configure_limit("alice", "BTC", D("10"))
        self.credit.configure_limit("bob", "BTC", D("10"))
        self.credit.fund_pool("capital-btc", "BTC", D("50"), source_reference="synthetic:capital:btc")

    def reopen(self):
        return ExchangeService(Database(self.path), {"USD": 8, "BTC": 8, "TINY": 18}, clock=lambda: self.now)

    def market(self, version=1, price="100", *, btc=True):
        assets = {"USD": AssetSpec(D("1"), D("1")), "TINY": AssetSpec(D("1"), D("0.5"))}
        if btc:
            assets["BTC"] = AssetSpec(D(price), D("0.8"))
        return MarketSnapshot(version, self.now, assets,
                              {"BTC-PERP": InstrumentSpec(D("100"), D("0.1"), D("0.05"))})

    def assert_code(self, code, call, *args, **kwargs):
        with self.assertRaises(ServiceError) as rejected:
            call(*args, **kwargs)
        self.assertEqual(rejected.exception.code, code)

    def test_funded_borrow_preserves_gross_assets_and_debt_haircut(self):
        result = self.credit.borrow("alice", "loan", "BTC", D("2"))
        self.assertEqual((result["principal"], result["interest"]), ("2", "0"))
        account = self.exchange.account("alice")
        self.assertEqual(account["balances"]["BTC"], "2")
        self.assertEqual(account["liabilities"]["BTC"], {"principal": "2", "interest": "0", "total": "2"})
        self.assertEqual(self.exchange.risk("alice")["equity"], "960")
        self.assertEqual(self.exchange.ledger.balance("system:credit-pool", "BTC"), D("48"))
        self.assertEqual(self.exchange.ledger.balance("liability:principal:alice", "BTC"), D("-2"))
        self.assertEqual(self.exchange.ledger.balance("system:credit-principal-receivable", "BTC"), D("2"))
        self.assertEqual(self.credit.verify()["nonzero_liabilities"], 1)

    def test_separate_interest_and_repayment_order_have_reconcilable_cashflows(self):
        self.credit.borrow("alice", "loan", "BTC", D("2"))
        self.credit.accrue_interest("alice", "interest", "BTC", D("0.1"))
        self.assertEqual(self.exchange.account("alice")["balances"]["BTC"], "2")
        self.assertEqual(self.exchange.risk("alice")["equity"], "950")
        result = self.credit.repay("alice", "repay", "BTC", D("0.15"))
        self.assertEqual((result["interest_repaid"], result["principal_repaid"]), ("0.1", "0.05"))
        self.assertEqual((result["principal"], result["interest"]), ("1.95", "0"))
        self.assertEqual(self.exchange.account("alice")["balances"]["BTC"], "1.85")
        self.assertEqual(self.exchange.risk("alice")["equity"], "953")
        self.assertEqual(self.exchange.ledger.balance("system:credit-pool", "BTC"), D("48.05"))
        self.assertEqual(self.exchange.ledger.balance("system:credit-interest-cash", "BTC"), D("0.1"))
        self.assertEqual(self.exchange.ledger.balance("system:credit-interest-receivable", "BTC"), D("0"))
        self.assertEqual(self.credit.verify()["nonzero_liabilities"], 1)

    def test_idempotency_survives_restart_and_commands_cannot_change_kind(self):
        original = self.credit.borrow("alice", "loan", "BTC", D("2"))
        self.credit.accrue_interest("alice", "interest", "BTC", D("0.1"))
        self.credit.repay("alice", "repay", "BTC", D("0.1"))
        before = self.exchange.account("alice"), self.exchange.ledger.journal(), self.exchange.events(limit=1000)
        restarted = CreditService(self.reopen())
        self.assertEqual(restarted.borrow("alice", "loan", "BTC", D("2.0000")), original)
        restarted.accrue_interest("alice", "interest", "BTC", D("0.100"))
        restarted.repay("alice", "repay", "BTC", D("0.10"))
        self.assertEqual((self.exchange.account("alice"), self.exchange.ledger.journal(), self.exchange.events(limit=1000)), before)
        self.assert_code("idempotency_conflict", restarted.borrow, "alice", "loan", "BTC", D("3"))
        self.assert_code("idempotency_conflict", restarted.repay, "alice", "loan", "BTC", D("1"))
        self.assert_code("idempotency_conflict", restarted.fund_pool, "capital-btc", "BTC", D("50"), source_reference="different")

    def test_limits_are_required_immutable_and_enforced_against_gross_debt(self):
        self.assert_code("credit_disabled", self.credit.borrow, "alice", "usd-disabled", "USD", D("1"))
        self.assert_code("credit_limit", self.credit.borrow, "alice", "too-large", "BTC", D("11"))
        self.credit.borrow("alice", "loan", "BTC", D("10"))
        self.credit.accrue_interest("alice", "interest", "BTC", D("0.01"))
        self.assert_code("credit_limit", self.credit.borrow, "alice", "more", "BTC", D("0.00000001"))
        # An interest obligation must still be recognized above the borrowing
        # limit; it cannot be silently discarded by an admission policy.
        self.assertEqual(self.exchange.account("alice")["liabilities"]["BTC"]["total"], "10.01")
        self.assert_code("configuration_conflict", self.credit.configure_limit, "alice", "BTC", D("11"))
        self.assert_code("configuration_conflict", self.credit.configure_asset_limit, "BTC", D("101"))
        self.assertEqual(self.credit.configure_limit("alice", "BTC", D("10.0"))["limit"], "10")

    def test_asset_limit_and_pool_liquidity_cannot_be_oversubscribed(self):
        self.credit.configure_asset_limit("USD", D("10"))
        for account in ("alice", "bob"):
            self.credit.configure_limit(account, "USD", D("10"))
        self.credit.fund_pool("capital-usd", "USD", D("20"), source_reference="synthetic:capital:usd")
        peers = [CreditService(self.reopen()) for _ in range(2)]
        def borrow(index):
            try:
                peers[index].borrow(("alice", "bob")[index], "loan-usd", "USD", D("10"))
                return True
            except ServiceError as exc:
                self.assertEqual(exc.code, "credit_limit")
                return False
        with ThreadPoolExecutor(max_workers=2) as executor:
            self.assertEqual(sum(executor.map(borrow, range(2))), 1)
        self.assertEqual(self.exchange.ledger.balance("system:credit-pool", "USD"), D("10"))
        self.credit.configure_asset_limit("TINY", D("100"))
        self.credit.configure_limit("alice", "TINY", D("100"))
        self.assert_code("credit_pool_empty", self.credit.borrow, "alice", "empty", "TINY", D("1"))

    def test_same_command_concurrent_retry_posts_once(self):
        peers = [CreditService(self.reopen()) for _ in range(4)]
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(lambda peer: peer.borrow("alice", "same", "BTC", D("2")), peers))
        self.assertTrue(all(result == results[0] for result in results))
        self.assertEqual(self.exchange.account("alice")["liabilities"]["BTC"]["principal"], "2")
        self.assertEqual(len([event for event in self.exchange.events(limit=1000) if event["event_type"] == "CREDIT_BORROWED"]), 1)

    def test_rejected_post_borrow_risk_rolls_back_cash_debt_journal_and_id(self):
        self.exchange.create_account("poor")
        self.credit.configure_limit("poor", "BTC", D("10"))
        before_journal = self.exchange.ledger.journal()
        before_events = self.exchange.events(limit=1000)
        self.assert_code("insufficient_margin", self.credit.borrow, "poor", "loan", "BTC", D("1"))
        self.assertEqual(self.exchange.account("poor")["balances"]["BTC"], "0")
        self.assertEqual(self.exchange.account("poor")["liabilities"], {})
        self.assertEqual(self.exchange.ledger.journal(), before_journal)
        self.assertEqual(self.exchange.events(limit=1000), before_events)
        self.exchange.deposit("poor", "collateral", "USD", D("20"))
        self.assertEqual(self.credit.borrow("poor", "loan", "BTC", D("1"))["principal"], "1")

    def test_unpriced_stale_halted_or_frozen_account_cannot_borrow(self):
        self.exchange.publish_market(self.market(2, btc=False))
        self.assert_code("market_incomplete", self.credit.borrow, "alice", "unpriced", "BTC", D("1"))
        self.exchange.publish_market(self.market(3))
        self.now += timedelta(seconds=6)
        self.assert_code("market_unavailable", self.credit.borrow, "alice", "stale", "BTC", D("1"))
        self.exchange.publish_market(self.market(4))
        self.exchange.set_kill_switch(True)
        self.assert_code("trading_halted", self.credit.borrow, "alice", "halted", "BTC", D("1"))
        self.exchange.set_kill_switch(False)
        with self.exchange.database.transaction() as connection:
            connection.execute("INSERT INTO uta_liquidation_accounts VALUES ('alice','BLOCKED',1,1,NULL,NULL)")
        self.assert_code("account_frozen", self.credit.borrow, "alice", "frozen", "BTC", D("1"))

    def test_repay_during_halt_or_stale_prices_never_fabricates_a_borrow(self):
        self.credit.borrow("alice", "loan", "BTC", D("1"))
        self.credit.accrue_interest("alice", "interest", "BTC", D("0.1"))
        self.now += timedelta(seconds=20)
        self.exchange.set_kill_switch(True)
        self.assert_code("insufficient_cash", self.credit.repay, "alice", "insufficient", "BTC", D("1.1"))
        self.assertEqual(self.exchange.account("alice")["liabilities"]["BTC"]["total"], "1.1")
        self.credit.repay("alice", "repay", "BTC", D("1"))
        self.assertEqual(self.exchange.account("alice")["liabilities"]["BTC"], {"principal": "0.1", "interest": "0", "total": "0.1"})
        self.assert_code("repayment_exceeds_debt", self.credit.repay, "alice", "overpay", "BTC", D("1"))

    def test_repay_honors_the_shared_available_asset_gate(self):
        self.credit.borrow("alice", "loan", "BTC", D("1"))
        with patch.object(self.exchange, "_available_asset", return_value=D("0.25")):
            self.assert_code("insufficient_cash", self.credit.repay, "alice", "locked", "BTC", D("0.5"))
        self.assertEqual(self.exchange.account("alice")["balances"]["BTC"], "1")

    def test_interest_has_no_invented_rate_clock_or_implicit_compounding(self):
        self.assert_code("no_principal", self.credit.accrue_interest, "alice", "no-loan", "BTC", D("0.1"))
        self.credit.borrow("alice", "loan", "BTC", D("1"))
        self.credit.accrue_interest("alice", "external-interest:period1", "BTC", D("0.00000001"))
        self.assertEqual(self.exchange.account("alice")["liabilities"]["BTC"]["interest"], "0.00000001")
        self.assertEqual(self.exchange.account("alice")["balances"]["BTC"], "1")

    def test_price_updates_include_full_gross_liability_and_cannot_drop_its_asset(self):
        self.credit.borrow("alice", "loan", "BTC", D("1"))
        self.exchange.publish_market(self.market(2, price="150"))
        self.assertEqual(self.exchange.risk("alice")["equity"], "970")
        self.assert_code("market_incomplete", self.exchange.publish_market, self.market(3, btc=False))

    def test_monetary_amounts_use_exact_asset_scale_independent_of_decimal_context(self):
        self.credit.configure_asset_limit("TINY", D("1"))
        self.credit.configure_limit("alice", "TINY", D("1"))
        self.credit.fund_pool("capital-tiny", "TINY", D("1"), source_reference="synthetic:capital:tiny")
        with localcontext() as context:
            context.prec = 1
            context.traps[Inexact] = True
            amount = D("0.000000000000000001")
            self.credit.borrow("alice", "tiny-loan", "TINY", amount)
            self.credit.accrue_interest("alice", "tiny-interest", "TINY", amount)
            self.assertEqual(self.exchange.account("alice")["liabilities"]["TINY"]["total"], "0.000000000000000002")
            self.credit.repay("alice", "tiny-repay", "TINY", amount)
        self.assertEqual(self.credit.verify()["nonzero_liabilities"], 1)
        for amount in (D("0"), D("-1"), D("NaN"), D("0.000000001"), 1.0):
            self.assert_code("invalid_input", self.credit.borrow, "alice", "bad", "BTC", amount)

    def test_failure_after_mutation_rolls_back_every_projection_and_command(self):
        before = self.exchange.account("alice"), self.exchange.ledger.journal(), self.exchange.events(limit=1000)
        original = self.exchange._event
        def injected(connection, kind, account_id, payload):
            if kind == "CREDIT_BORROWED":
                raise RuntimeError("injected credit commit failure")
            return original(connection, kind, account_id, payload)
        with patch.object(self.exchange, "_event", side_effect=injected):
            with self.assertRaisesRegex(RuntimeError, "injected"):
                self.credit.borrow("alice", "loan", "BTC", D("1"))
        self.assertEqual((self.exchange.account("alice"), self.exchange.ledger.journal(), self.exchange.events(limit=1000)), before)
        self.assertEqual(self.credit.borrow("alice", "loan", "BTC", D("1"))["principal"], "1")

    def test_corrupt_debt_projection_is_rejected_before_new_credit_or_startup(self):
        self.credit.borrow("alice", "loan", "BTC", D("1"))
        with self.exchange.database.transaction() as connection:
            connection.execute("UPDATE uta_liabilities SET principal='0' WHERE account_id='alice'")
        self.assert_code("credit_corrupt", self.credit.verify)
        self.assert_code("credit_corrupt", self.credit.borrow, "alice", "more", "BTC", D("1"))
        self.assert_code("credit_corrupt", CreditService, self.exchange)

    def test_unknown_schema_version_blocks_existing_instances_too(self):
        with self.exchange.database.transaction() as connection:
            connection.execute("UPDATE credit_schema SET version=999")
        self.assert_code("credit_schema_version", self.credit.borrow, "alice", "loan", "BTC", D("1"))
        self.assert_code("credit_schema_version", self.credit.configure_limit, "alice", "USD", D("1"))
        self.assert_code("credit_schema_version", self.credit.verify)


if __name__ == "__main__":
    unittest.main()
