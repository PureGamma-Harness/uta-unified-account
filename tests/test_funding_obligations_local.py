"""Fixed synthetic cases; CODE only until an explicit bounded SQL scope exists."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from hashlib import sha256
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from uta.funding_obligations import FundingObligations, _key
from uta.funding_local import FundingLocal
from uta.ledger import Posting
from uta.market import MarketSnapshot
from uta.matching import Matcher
from uta.models import AssetSpec, InstrumentSpec
from uta.perpetual_funding import FundingError, FundingPolicy
from uta.portfolio import CollateralRule, CollateralTier, LinearMarginRule, PortfolioRules
from uta.products import ProductCatalog, ProductKind, ProductSpec, TradingStatus
from uta.service import ExchangeService, ServiceError
from uta.storage import Database


END = datetime(2026, 1, 1, 8, tzinfo=timezone.utc)


def scenario(test, label, *, offset=1, empty=False, old=False, defer_positions=False):
    retained = os.environ.get("UTA_FUNDING_OBLIGATION_CASE_ROOT")
    if retained:
        base = Path(retained)
        if not base.is_absolute() or base.resolve() != base or not base.is_dir():
            raise AssertionError("retained case root must be existing and canonical")
        directory = base / label
        directory.mkdir(mode=0o700)
    else:
        owned = tempfile.TemporaryDirectory(prefix="uta-funding-obligation-")
        test.addCleanup(owned.cleanup)
        directory = Path(owned.name)
    clock = {"now": END - timedelta(seconds=offset)}
    catalog = ProductCatalog(1, {"BTC-PERP": ProductSpec("BTC-PERP", ProductKind.LINEAR_PERPETUAL,
        "BTC", "USD", "USD", D(".01"), D(".1"), D(".1"), risk_tier="tier-1",
        funding_interval_seconds=28800, status=TradingStatus.ACTIVE)}, settlement_asset="USD")
    rules = PortfolioRules(1, {"USD": CollateralRule("USD", (CollateralTier(None, D(1)),), D(1))},
        {}, {"tier-1": LinearMarginRule("tier-1", D(".1"), D(".05"))}, D("1000000"))
    path = directory / "obligations.sqlite3"
    def service():
        return ExchangeService(Database(path), {"USD": 2}, clock=lambda: clock["now"],
            product_catalog=catalog, portfolio_rules=rules, decision_audit=True)
    exchange = service()
    policy = FundingPolicy()
    component = (FundingLocal if old else FundingObligations).install_synthetic_fresh(
        exchange, policy, capital_account_id="treasury")
    data = SimpleNamespace(service=exchange, funding=component, policy=policy, path=path,
                           reopen=service, clock=clock, matcher=None)
    if not empty:
        for account in ("treasury", "a", "b"):
            exchange.create_account(account)
            if account != "treasury":
                exchange.deposit(account, "synthetic-deposit", "USD", D(1000))
        publish(data, 1, None if defer_positions else "100")
        exchange.set_kill_switch(False)
        data.matcher = Matcher(exchange)
        if not defer_positions:
            exchange.submit_order("a", "open-a", "BTC-PERP", D(1), D(100))
            exchange.submit_order("b", "open-b", "BTC-PERP", D(-1), D(100))
            test.assertEqual(data.matcher.match_once("BTC-PERP")["confirmed_trades"], 1)
    return data


def publish(data, version, mark):
    market = MarketSnapshot(version, data.clock["now"], {"USD": AssetSpec(D(1), D(1))},
        {} if mark is None else {"BTC-PERP": InstrumentSpec(D(mark), D(".1"), D(".05"))})
    data.service.publish_market(market)
    return "sha256:" + sha256(market.to_json().encode()).hexdigest()


def prepare(test, data, *, rate=".0001", obligation="btc-end", mark="100"):
    scheduled = data.funding.schedule("schedule", obligation, "BTC-PERP", END, rate=D(rate))
    test.assertEqual(scheduled["state_at_commit"], "SCHEDULED")
    data.clock["now"] = END
    market_id = publish(data, 2, mark)
    data.funding.due("due", obligation)
    token = data.funding.claim("claim", obligation, "executor-a")["token"]
    data.funding.capture("cut", obligation, token, market_snapshot_id=market_id)
    test.assertIsNotNone(data.funding.query(obligation)["cut_sha"])
    return token


class FundingObligationTests(unittest.TestCase):
    def test_schedule_apply_command_queries_and_reopen(self):
        data = scenario(self, "normal")
        token = prepare(self, data)
        result = data.funding.apply("apply", "btc-end", token)
        self.assertEqual(result["state_at_commit"], "APPLIED")
        self.assertEqual(data.service.ledger.balance("customer:a", "USD"), D("999.95"))
        self.assertEqual(data.service.ledger.balance("customer:b", "USD"), D("999.97"))
        before = data.service.ledger.journal()
        restored = FundingObligations(data.reopen(), data.policy)
        self.assertEqual(restored.command("apply"), result)
        self.assertEqual(restored.apply("apply", "btc-end", token), result)
        self.assertEqual(data.service.ledger.journal(), before)
        self.assertFalse(restored.query("btc-end")["outstanding"])
        self.assertEqual(restored.pending(), [])
        with self.assertRaises(FundingError):
            restored.schedule("schedule", "different", "BTC-PERP", END, rate=D(".0001"))
        with self.assertRaises(FundingError):
            restored.schedule("new-command", "different", "BTC-PERP", END, rate=D(".0002"))
        self.assertTrue(restored.verify()["reconciled"])

    def test_missing_data_and_no_backdated_cut(self):
        # Cash-only state permits a USD-only publication through the real API.
        missing = scenario(self, "missing", offset=10, defer_positions=True)
        missing.funding.schedule("schedule", "btc-end", "BTC-PERP", END, rate=None)
        missing.clock["now"] = END
        partial_id = publish(missing, 2, None)
        before_partial = missing.service.ledger.journal()
        token = missing.funding.claim("claim", "btc-end", "a")["token"]
        outcome = missing.funding.capture("cut-missing", "btc-end", token,
            market_snapshot_id=partial_id, resolved_rate=D(".0001"))
        self.assertEqual(outcome["state_at_commit"], "WAITING_DATA")
        self.assertEqual(missing.funding.query("btc-end")["reason"], "funding_required_quote_unavailable")
        self.assertIsNone(missing.funding.query("btc-end")["cut_sha"])
        self.assertEqual(missing.service.ledger.journal(), before_partial)
        # Restore the mark and create exactly the original one paired trade.
        # The independent missing-rate gate still prevents an unsafe cut.
        publish(missing, 3, "100")
        missing.service.submit_order("a", "open-a", "BTC-PERP", D(1), D(100))
        missing.service.submit_order("b", "open-b", "BTC-PERP", D(-1), D(100))
        self.assertEqual(missing.matcher.match_once("BTC-PERP")["confirmed_trades"], 1)
        token = missing.funding.claim("rate-claim", "btc-end", "b")["token"]
        self.assertEqual(missing.funding.capture("rate-missing", "btc-end", token,
            market_snapshot_id=None)["state_at_commit"], "WAITING_DATA")
        self.assertEqual(missing.funding.query("btc-end")["reason"], "funding_rate_unavailable")
        restored = FundingObligations(missing.reopen(), missing.policy)
        self.assertTrue(restored.query("btc-end")["outstanding"])
        self.assertIsNone(restored.query("btc-end")["cut_sha"])
        missing.clock["now"] = END + timedelta(seconds=3)
        token = restored.claim("late-claim", "btc-end", "b")["token"]
        self.assertEqual(restored.capture("late-cut", "btc-end", token, market_snapshot_id=None)["state_at_commit"], "REVIEW_REQUIRED")
        self.assertIsNone(restored.query("btc-end")["receipt"])
        self.assertEqual(restored.pending()[0]["state"], "REVIEW_REQUIRED")
        self.assertEqual(missing.service.ledger.balance("customer:a", "USD"), D("999.96"))
        live = scenario(self, "current-data")
        prepare(self, live)
        live.clock["now"] = END + timedelta(seconds=6)
        token = live.funding.claim("stale-claim", "btc-end", "b")["token"]
        result = live.funding.apply("stale-apply", "btc-end", token)
        self.assertEqual(result["state_at_commit"], "WAITING_DATA")
        self.assertEqual(live.service.ledger.balance("customer:a", "USD"), D("999.96"))
        saved_cut = live.funding.query("btc-end")["cut_sha"]
        before_partial = live.service.ledger.journal()
        partial = MarketSnapshot(3, live.clock["now"], {"USD": AssetSpec(D(1), D(1))}, {})
        # The public publisher correctly rejects removing live BTC coverage.
        with self.assertRaisesRegex(ServiceError, "cannot remove a live instrument"):
            live.service.publish_market(partial)
        # Decision-only negative control in a real read snapshot. No market
        # store/history/guard is patched; durable partial-store recovery is OPEN.
        with live.service.database.read_transaction() as connection:
            with self.assertRaises(ServiceError) as unavailable:
                live.funding._check_current_quotes(connection, "a", partial)
        self.assertEqual(unavailable.exception.code, "funding_required_quote_unavailable")
        self.assertEqual(live.service.ledger.journal(), before_partial)
        self.assertEqual(live.funding.query("btc-end")["cut_sha"], saved_cut)
        self.assertEqual(live.funding.query("btc-end")["state"], "WAITING_DATA")
        market_id = publish(live, 4, "101")
        token = live.funding.claim("fresh-claim", "btc-end", "c")["token"]
        result = live.funding.apply("fresh-apply", "btc-end", token)
        self.assertEqual(result["receipt"]["risk_market_snapshot_id"], market_id)
        self.assertEqual(live.service.ledger.balance("customer:a", "USD"), D("999.95"))
        self.assertEqual(live.funding.command("stale-apply")["state_at_commit"], "WAITING_DATA")

    def test_real_capital_wait_and_unique_proof(self):
        data = scenario(self, "capital")
        data.service.create_account("c")
        data.service.deposit("c", "synthetic-deposit", "USD", D(1000))
        data.service.submit_order("a", "sell-six", "BTC-PERP", D("-.6"), D(100))
        data.service.submit_order("c", "buy-six", "BTC-PERP", D(".6"), D(100))
        self.assertEqual(data.matcher.match_once("BTC-PERP")["confirmed_trades"], 1)
        token = prepare(self, data, rate=".015", mark="1")
        pending = data.funding.apply("no-capital", "btc-end", token)
        self.assertEqual(pending["state_at_commit"], "WAITING_CAPITAL")
        self.assertTrue(data.funding.query("btc-end")["outstanding"])
        data.service.deposit("treasury", "approved-synthetic-capital", "USD", D(1))
        restored = FundingObligations(data.reopen(), data.policy)
        token = restored.claim("funded-claim", "btc-end", "b")["token"]
        result = restored.apply("funded-apply", "btc-end", token, capital_deposit_reference="approved-synthetic-capital")
        self.assertEqual(result["receipt"]["capital_transfer"]["amount"], "0.01")
        self.assertEqual(data.service.ledger.balance("customer:treasury", "USD"), D(".99"))
        self.assertEqual(data.service.ledger.balance("customer:a", "USD"), D("999.93"))
        self.assertEqual(data.service.ledger.balance("customer:b", "USD"), D("999.97"))
        self.assertEqual(data.service.ledger.balance("customer:c", "USD"), D("999.97"))
        later = END + timedelta(hours=8)
        restored.schedule("schedule-next", "next", "BTC-PERP", later, rate=D(".015"))
        data.clock["now"] = later
        quote = publish(data, 3, "1")
        token = restored.claim("next-claim", "next", "c")["token"]
        restored.capture("next-cut", "next", token, market_snapshot_id=quote)
        self.assertEqual(restored.apply("reuse-proof", "next", token, capital_deposit_reference="approved-synthetic-capital")["state_at_commit"], "WAITING_CAPITAL")
        self.assertEqual(restored.verify()["outstanding"], 1)

    def test_competing_executors_expiry_and_clock_regression(self):
        # Future exact GO must authorize these two bounded test threads.
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        data = scenario(self, "competition")
        data.funding.schedule("schedule", "btc-end", "BTC-PERP", END, rate=D(".0001"))
        data.clock["now"] = END
        quote = publish(data, 2, "100")
        peers = {owner: FundingObligations(data.reopen(), data.policy) for owner in ("a", "b")}
        barrier = Barrier(2)
        def contend(owner):
            barrier.wait(timeout=5)
            return peers[owner].claim("claim-" + owner, "btc-end", owner)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = {owner: pool.submit(contend, owner) for owner in peers}
            results = {owner: future.result(timeout=10) for owner, future in futures.items()}
        self.assertEqual(sum(value["claimed"] for value in results.values()), 1)
        winner = next(owner for owner in results if results[owner]["claimed"])
        loser = next(owner for owner in results if not results[owner]["claimed"])
        first = results[winner]["token"]
        peers[winner].capture("cut", "btc-end", first, market_snapshot_id=quote)
        data.clock["now"] = END + timedelta(milliseconds=1001)
        second = peers[loser].claim("reclaim", "btc-end", loser)["token"]
        self.assertEqual(second["generation"], first["generation"] + 1)
        before = data.service.ledger.journal()
        self.assertTrue(peers[winner].apply("old-owner", "btc-end", first)["fenced"])
        self.assertEqual(data.service.ledger.journal(), before)
        self.assertEqual(peers[loser].apply("new-owner", "btc-end", second)["state_at_commit"], "APPLIED")
        self.assertTrue(peers[winner].claim("claim-" + winner, "btc-end", winner)["token"] == first)
        data.clock["now"] = END
        with self.assertRaisesRegex(FundingError, "regressed"):
            peers[loser].due("clock-back", "btc-end")
        self.assertEqual(peers[loser].query("btc-end")["state"], "APPLIED")

    def test_trades_after_cut_and_unknown_response_query(self):
        data = scenario(self, "changed-positions")
        token = prepare(self, data, rate=".01")
        data.clock["now"] = END + timedelta(milliseconds=500)
        publish(data, 3, "101")
        data.service.submit_order("a", "close-a", "BTC-PERP", D(-1), D(101), reduce_only=True)
        data.service.submit_order("b", "close-b", "BTC-PERP", D(1), D(101), reduce_only=True)
        self.assertEqual(data.matcher.match_once("BTC-PERP")["confirmed_trades"], 1)
        self.assertEqual(data.service.ledger.balance("customer:a", "USD"), D("1000.91"))
        self.assertEqual(data.service.ledger.balance("customer:b", "USD"), D("998.91"))
        # Once both real positions are flat, the public publisher legitimately
        # permits USD-only current quotes; historical cut BTC is not live risk.
        cash_only_id = publish(data, 4, None)
        data.funding.apply("lost-response", "btc-end", token)  # Deliberately discard local return, no network fault claimed.
        before = data.service.ledger.journal()
        data.clock["now"] = END + timedelta(seconds=4)
        restored = FundingObligations(data.reopen(), data.policy)
        known = restored.command("lost-response")
        self.assertEqual(known["receipt"]["risk_market_snapshot_id"], cash_only_id)
        self.assertEqual(restored.apply("lost-response", "btc-end", token), known)
        self.assertIsNone(restored.command("not-committed-visible"))
        self.assertEqual(data.service.ledger.journal(), before)
        for account in ("a", "b"):
            self.assertEqual(data.service.account(account)["positions"], {})
            self.assertEqual(data.service.ledger.balance("customer:" + account, "USD"), D("999.91"))
        self.assertEqual(data.service.ledger.balance("system:fees", "USD"), D(".18"))
        self.assertEqual(data.matcher.verify(strict=True)["matches"], 2)
        self.assertTrue(restored.verify()["reconciled"])

    def test_review_rollback_code_binding_and_old_capability_rejection(self):
        fresh = scenario(self, "new-empty", empty=True)
        with self.assertRaisesRegex(FundingError, "old prototype"):
            FundingLocal.install_synthetic_fresh(fresh.service, fresh.policy, capital_account_id="treasury")
        old = scenario(self, "old-empty", empty=True, old=True)
        with self.assertRaises(FundingError):
            FundingObligations.install_synthetic_fresh(old.service, old.policy, capital_account_id="treasury")
        data = scenario(self, "review")
        token = prepare(self, data)
        from uta import funding_obligations as module
        from uta.credit_artifact import CreditArtifactError
        module._UNSUPPORTED_FINANCIAL_SENTINEL = object()
        try:
            with self.assertRaises(CreditArtifactError):
                data.funding.apply("wrong-loaded-code", "btc-end", token)
            self.assertIsNone(data.funding.command("wrong-loaded-code"))
        finally:
            del module._UNSUPPORTED_FINANCIAL_SENTINEL
        data.service.ledger.post(_key("leg", "btc-end", "b"),
            (Posting("system:test-source", "USD", D(-1)), Posting("system:test-sink", "USD", D(1))))
        before = (data.service.ledger.journal(), data.service.accounts())
        result = data.funding.apply("orphan-rejected", "btc-end", token)
        self.assertEqual(result["state_at_commit"], "REVIEW_REQUIRED")
        self.assertFalse(result["successful_receipt_emitted"])
        self.assertEqual((data.service.ledger.journal(), data.service.accounts()), before)
        restored = FundingObligations(data.reopen(), data.policy)
        self.assertTrue(restored.query("btc-end")["outstanding"])
        self.assertEqual(restored.pending()[0]["state"], "REVIEW_REQUIRED")
        self.assertIsNone(restored.query("btc-end")["receipt"])
        self.assertEqual(restored.command("orphan-rejected"), result)
        with self.assertRaises(FundingError):
            restored.verify()  # Readable REVIEW is not a healthy financial authority.
