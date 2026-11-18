"""Synthetic funding references. SQL cases require a separate explicit scope.

The first three methods are pure arithmetic; the last three create only new
test-owned authorities. UTA_FUNDING_CASE_ROOT retains those databases for review.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D, Inexact, localcontext
from fractions import Fraction
from hashlib import sha256
import unittest

from uta.perpetual_funding import (FundingError, FundingPolicy, FundingPosition,
                                   plan_funding)


END = datetime(2026, 1, 1, 8, tzinfo=timezone.utc)


def calculate(quantities, rate=".0001", mark="100", scale=2):
    return plan_funding(FundingPolicy(), "BTC-PERP", END, interval_seconds=28800,
        mark=D(mark), rate=D(rate), usd_scale=scale,
        positions=tuple(FundingPosition(account, D(quantity)) for account, quantity in quantities))


class FundingArithmeticTests(unittest.TestCase):
    def test_two_sides_negative_and_zero_rates_use_manual_cash(self):
        expected = ((".0001", {"long": -1, "short": 1}),
                    ("-.0001", {"long": 1, "short": -1}),
                    ("0", {"long": 0, "short": 0}))
        for rate, amounts in expected:
            with self.subTest(rate=rate):
                result = calculate((("long", "1"), ("short", "-1")), rate)
                self.assertEqual({leg.account_id: leg.cash_units for leg in result.legs}, amounts)
                self.assertEqual(result.clearing_units, 0)

    def test_three_accounts_need_real_segregated_rounding_capital(self):
        debit = calculate((("a", ".4"), ("b", ".6"), ("c", "-1")), ".015", "1")
        self.assertEqual([leg.cash_units for leg in debit.legs], [0, 0, 1])
        self.assertEqual(debit.clearing_units, -1)
        self.assertEqual(debit.payload()["required_rounding_capital_units"], "1")
        self.assertEqual([leg.exact_cash for leg in debit.legs],
                         [Fraction(-3, 500), Fraction(-9, 1000), Fraction(3, 200)])
        credit = calculate((("a", "1"), ("b", "-.4"), ("c", "-.6")), ".015", "1")
        self.assertEqual([leg.cash_units for leg in credit.legs], [-1, 0, 0])
        self.assertEqual(credit.clearing_units, 1)
        self.assertEqual(sum(leg.cash_units for leg in credit.legs) + credit.clearing_units, 0)

    def test_invalid_inventory_and_decimal_context_do_not_change_policy(self):
        with localcontext() as context:
            context.prec = 2
            context.traps[Inexact] = True
            result = calculate((("a", "10"), ("b", "-10")), ".0001", "8000", 8)
        self.assertEqual([leg.cash_units for leg in result.legs], [-800000000, 800000000])
        self.assertEqual(result.clearing_units, 0)
        for quantities in ((("a", "1"),), (("a", "1"), ("a", "-1"))):
            with self.subTest(quantities=quantities), self.assertRaises(FundingError):
                calculate(quantities)
        for rate in (".030000000000000001", "NaN", "Infinity"):
            with self.subTest(rate=rate), self.assertRaises(FundingError):
                calculate((("a", "1"), ("b", "-1")), rate)


def fixture(test, label, *, low_margin=False, capital="0"):
    # Imports and database creation are deliberately outside the pure methods.
    from pathlib import Path
    import os
    import tempfile
    from types import SimpleNamespace
    from uta.funding_local import FundingLocal
    from uta.market import MarketSnapshot
    from uta.matching import Matcher
    from uta.models import AssetSpec, InstrumentSpec
    from uta.portfolio import (CollateralRule, CollateralTier, LinearMarginRule,
                               PortfolioRules)
    from uta.products import ProductCatalog, ProductKind, ProductSpec, TradingStatus
    from uta.service import ExchangeService
    from uta.storage import Database
    retained = os.environ.get("UTA_FUNDING_CASE_ROOT")
    if retained:
        root = Path(retained)
        if not root.is_absolute() or root.resolve() != root or not root.is_dir():
            raise AssertionError("retained SQL root must be an existing canonical directory")
        directory = root / label
        directory.mkdir(mode=0o700)
    else:
        temporary = tempfile.TemporaryDirectory(prefix="uta-funding-test-")
        test.addCleanup(temporary.cleanup)
        directory = Path(temporary.name)
    policy = FundingPolicy()
    im, mm = (D(".01"), D(".005")) if low_margin else (D(".1"), D(".05"))
    catalog = ProductCatalog(1, {"BTC-PERP": ProductSpec(
        "BTC-PERP", ProductKind.LINEAR_PERPETUAL, "BTC", "USD", "USD",
        D(".01"), D(".1"), D(".1"), risk_tier="tier-1", funding_interval_seconds=28800,
        status=TradingStatus.ACTIVE)}, settlement_asset="USD")
    rules = PortfolioRules(1, {"USD": CollateralRule("USD", (CollateralTier(None, D(1)),), D(1))},
        {}, {"tier-1": LinearMarginRule("tier-1", im, mm)}, D("1000000"))
    path = directory / "funding.sqlite3"
    clock = {"now": END}
    def reopen():
        return ExchangeService(Database(path), {"USD": 2}, clock=lambda: clock["now"],
                               product_catalog=catalog, portfolio_rules=rules, decision_audit=True)
    service = reopen()
    funding = FundingLocal.install_synthetic_fresh(service, policy,
                    capital_account_id="funding-treasury")
    service.create_account("funding-treasury")
    if D(capital):
        service.deposit("funding-treasury", "authorized-synthetic-capital", "USD", D(capital))
    for account, amount in (("a", "1.04" if low_margin else "1000"), ("b", "1000")):
        service.create_account(account)
        service.deposit(account, "synthetic-deposit", "USD", D(amount))
    market = MarketSnapshot(1, END, {"USD": AssetSpec(D(1), D(1))},
                            {"BTC-PERP": InstrumentSpec(D(100), im, mm)})
    service.publish_market(market)
    service.set_kill_switch(False)
    matcher = Matcher(service)
    service.submit_order("a", "open-a", "BTC-PERP", D(1), D(100))
    service.submit_order("b", "open-b", "BTC-PERP", D(-1), D(100))
    test.assertEqual(matcher.match_once("BTC-PERP")["confirmed_trades"], 1)
    return SimpleNamespace(service=service, funding=funding, policy=policy, matcher=matcher,
        market_id="sha256:" + sha256(market.to_json().encode()).hexdigest(), reopen=reopen, path=path,
        im=im, mm=mm, clock=clock)


class FundingLocalSQLTests(unittest.TestCase):
    def test_fresh_period_retry_reopen_and_period_uniqueness(self):
        from uta.funding_local import FundingLocal
        data = fixture(self, "period")
        args = {"rate": D(".0001"), "market_snapshot_id": data.market_id}
        receipt = data.funding.settle("period-1", "BTC-PERP", END, **args)
        self.assertEqual(receipt["plan"]["legs"][0]["cash"], "-0.01")
        self.assertEqual(receipt["plan"]["legs"][1]["cash"], "0.01")
        self.assertEqual(receipt["rounding_reserve_after"], "0")
        state = data.service.ledger.journal()
        self.assertEqual(data.funding.settle("period-1", "BTC-PERP", END, **args), receipt)
        self.assertEqual(data.service.ledger.journal(), state)
        with self.assertRaisesRegex(FundingError, "command ID reused"):
            data.funding.settle("period-1", "BTC-PERP", END, rate=D(".0002"), market_snapshot_id=data.market_id)
        with self.assertRaisesRegex(FundingError, "only once"):
            data.funding.settle("another-command", "BTC-PERP", END, **args)
        reopened = FundingLocal(data.reopen(), data.policy)
        self.assertEqual(reopened.receipt("period-1"), receipt)
        self.assertEqual(reopened.verify()["periods"], 1)
        self.assertEqual(data.matcher.verify(strict=True)["matches"], 1)
        self.assertEqual(data.service.ledger.balance("customer:a", "USD"), D("999.95"))
        self.assertEqual(data.service.ledger.balance("customer:b", "USD"), D("999.97"))
        from uta import perpetual_funding as funding_module
        from uta.credit_artifact import CreditArtifactError
        funding_module._UNSUPPORTED_FINANCIAL_SENTINEL = object()
        try:
            with self.assertRaises(CreditArtifactError):
                data.funding.settle("bad-loaded-constant", "BTC-PERP", END + timedelta(hours=8), **args)
            self.assertEqual(data.funding.receipt("period-1"), receipt)
        finally:
            del funding_module._UNSUPPORTED_FINANCIAL_SENTINEL

    def test_mandatory_debit_uses_cash_deficit_and_real_risk_state(self):
        from uta.service import ServiceError
        data = fixture(self, "distress", low_margin=True)
        receipt = data.funding.settle("funding-distress", "BTC-PERP", END,
                                     rate=D(".02"), market_snapshot_id=data.market_id)
        self.assertEqual(data.service.ledger.balance("customer:a", "USD"), D("-1"))
        self.assertEqual(receipt["risk_after"]["a"]["cash_deficit_value"], "1")
        self.assertEqual(receipt["risk_after"]["a"]["principal_value"], "0")
        self.assertIn(receipt["risk_actions"]["a"]["state"], ("LIQUIDATING", "BLOCKED"))
        with self.assertRaisesRegex(ServiceError, "frozen"):
            data.service.submit_order("a", "no-new-risk", "BTC-PERP", D(1), D(100))
        self.assertEqual(data.matcher.verify(strict=True)["matches"], 1)
        self.assertEqual(len(data.matcher.trades()), 1)  # Risk planning never fabricates a fill.
        self.assertTrue(data.funding.verify()["funding_reconciled"])

    def test_corrupt_reserved_id_rejects_atomically_and_late_freeze_is_not_backdated(self):
        from uta.funding_local import _key
        from uta.ledger import Posting
        from uta.service import ServiceError
        data = fixture(self, "rollback")
        collision = _key("leg", "BTC-PERP", END.isoformat(), "b")
        # Synthetic fault injection: an orphan but balanced reserved journal ID
        # is corruption, never a supported customer operation or an SQL patch.
        data.service.ledger.post(collision, (
            Posting("system:test-source", "USD", D(-1)), Posting("system:test-sink", "USD", D(1))))
        before = (data.service.ledger.journal(), data.service.accounts(), data.service.events(limit=1000))
        with self.assertRaises((FundingError, ServiceError)):
            data.funding.settle("atomic-failure", "BTC-PERP", END,
                                rate=D(".0001"), market_snapshot_id=data.market_id)
        self.assertEqual((data.service.ledger.journal(), data.service.accounts(), data.service.events(limit=1000)), before)
        self.assertIsNone(data.funding.receipt("atomic-failure"))
        # The current component may reject preflight on the orphan. It does not
        # claim that this injected fault necessarily reached a second posting.
        clean = fixture(self, "late")
        with self.assertRaisesRegex(FundingError, "boundary snapshot"):
            clean.funding.settle("late-period", "BTC-PERP", END - timedelta(hours=8),
                                 rate=D(".0001"), market_snapshot_id=clean.market_id)
        self.assertIsNone(clean.funding.receipt("late-period"))
        # A real three-account book produces a one-cent rounding shortfall.
        # Capital is transferred from a previously deposited treasury balance,
        # never minted by allowing a negative system-capital counterpart.
        from uta.market import MarketSnapshot
        from uta.models import AssetSpec, InstrumentSpec
        capital = fixture(self, "capital", capital="1")
        capital.service.create_account("c")
        capital.service.deposit("c", "synthetic-deposit", "USD", D(1000))
        capital.service.submit_order("a", "redistribute-a", "BTC-PERP", D("-.6"), D(100))
        capital.service.submit_order("c", "redistribute-c", "BTC-PERP", D(".6"), D(100))
        self.assertEqual(capital.matcher.match_once("BTC-PERP")["confirmed_trades"], 1)
        quote = MarketSnapshot(2, END, {"USD": AssetSpec(D(1), D(1))},
                              {"BTC-PERP": InstrumentSpec(D(1), capital.im, capital.mm)})
        capital.service.publish_market(quote)
        quote_id = "sha256:" + sha256(quote.to_json().encode()).hexdigest()
        with self.assertRaisesRegex(FundingError, "confirmed treasury"):
            capital.funding.settle("capital-declined-without-proof", "BTC-PERP", END,
                                    rate=D(".015"), market_snapshot_id=quote_id)
        receipt = capital.funding.settle("capital-period", "BTC-PERP", END, rate=D(".015"),
            market_snapshot_id=quote_id, capital_deposit_reference="authorized-synthetic-capital")
        self.assertEqual(receipt["capital_transfer"]["amount"], "0.01")
        self.assertEqual(capital.service.ledger.balance("customer:funding-treasury", "USD"), D(".99"))
        self.assertEqual(receipt["rounding_reserve_after"], "0")
        self.assertTrue(capital.funding.verify()["funding_reconciled"])
        capital.clock["now"] = END + timedelta(hours=8)
        quote = MarketSnapshot(3, capital.clock["now"], {"USD": AssetSpec(D(1), D(1))},
                              {"BTC-PERP": InstrumentSpec(D(1), capital.im, capital.mm)})
        capital.service.publish_market(quote)
        with self.assertRaisesRegex(FundingError, "already belongs"):
            capital.funding.settle("capital-proof-reuse", "BTC-PERP", capital.clock["now"],
                rate=D(".015"), market_snapshot_id="sha256:" + sha256(quote.to_json().encode()).hexdigest(),
                capital_deposit_reference="authorized-synthetic-capital")


if __name__ == "__main__":
    unittest.main()
