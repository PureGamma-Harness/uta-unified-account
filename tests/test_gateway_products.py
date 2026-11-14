"""Real REST-to-ledger coverage for credit, cash spot and paired matching."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from http.client import HTTPConnection
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from types import SimpleNamespace
import unittest

from uta.credit import CreditService
from uta.gateway import Credential, make_server
from uta.market import MarketSnapshot
from uta.matching import Matcher
from uta.models import AssetSpec, InstrumentSpec
from uta.portfolio import CollateralRule, CollateralTier, LinearMarginRule, PortfolioRules
from uta.products import ProductCatalog, ProductKind, ProductSpec, TradingStatus
from uta.service import ExchangeService
from uta.spot import SpotExchange
from uta.storage import Database


ADMIN, ALICE, BOB, READER, FUNDING, RISK = (letter * 43 for letter in "ABCRFK")


class ProductGatewayTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.now = datetime(2026, 11, 14, tzinfo=timezone.utc)
        self.service = ExchangeService(Database(Path(self.directory.name) / "exchange.sqlite3"),
                                       {"USD": 8, "BTC": 8}, clock=lambda: self.now)
        catalog = ProductCatalog(1, {"BTC-SPOT": ProductSpec(
            "BTC-SPOT", ProductKind.SPOT_MARGIN, "BTC", "USD", "USD", D(".01"),
            D(".01"), D(1), status=TradingStatus.ACTIVE)})
        self.credit = self.service.credit = CreditService(self.service)
        self.matcher = self.service.matcher = Matcher(self.service)
        self.spot = self.service.spot = SpotExchange(self.service, catalog)
        self.service.publish_market(MarketSnapshot(1, self.now,
            {"USD": AssetSpec(D(1), D(1)), "BTC": AssetSpec(D(100), D(".8"))},
            {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))}))
        for account in ("alice", "bob"):
            self.service.create_account(account)
            self.service.deposit(account, "usd", "USD", D(1000))
        self.service.deposit("bob", "btc", "BTC", D(5))
        self.service.set_kill_switch(False)
        self.server = make_server(self.service, port=0, credentials=(
            Credential(ADMIN, "admin"), Credential(ALICE, "trader", "alice"),
            Credential(BOB, "trader", "bob"), Credential(READER, "reader", "alice"),
            Credential(FUNDING, "funding", "alice"), Credential(RISK, "risk")))
        self.thread = Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)

    def request(self, method, path, payload=None, *, token=ADMIN):
        headers = {"Authorization": "Bearer " + token}
        body = None
        if payload is not None:
            body = json.dumps(payload)
            headers["Content-Type"] = "application/json"
        connection = HTTPConnection(*self.server.server_address, timeout=3)
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def expect(self, expected, method, path, payload=None, *, token=ADMIN):
        status, result = self.request(method, path, payload, token=token)
        self.assertEqual(status, expected, result)
        return result

    def financial(self):
        return (self.service.accounts(), self.service.ledger.journal(), self.service.events(limit=1000),
                self.matcher.trades(limit=1000), self.spot.trades(limit=1000),
                self.spot.orders("alice"), self.spot.orders("bob"))

    def test_funded_borrow_interest_and_repayment_are_real_idempotent_journal_operations(self):
        self.expect(200, "PUT", "/v1/credit/asset-limit", {"asset": "BTC", "limit": "10"}, token=RISK)
        self.expect(200, "PUT", "/v1/accounts/alice/credit-limits", {"asset": "BTC", "limit": "5"}, token=RISK)
        funded = self.expect(200, "POST", "/v1/credit/pool", {"command_id": "capital", "asset": "BTC",
                             "amount": "10", "source_reference": "synthetic:capital:1"})
        self.assertEqual(funded["pool_balance"], "10")
        loan = {"command_id": "loan", "asset": "BTC", "amount": "2"}
        borrowed = self.expect(200, "POST", "/v1/accounts/alice/loans", loan, token=FUNDING)
        self.assertEqual((borrowed["principal"], borrowed["interest"]), ("2", "0"))
        self.assertEqual(self.service.account("alice")["balances"]["BTC"], "2")
        self.expect(200, "POST", "/v1/accounts/alice/interest", {"command_id": "interest", "asset": "BTC", "amount": "0.1"})
        repaid = self.expect(200, "POST", "/v1/accounts/alice/repayments", {"command_id": "repay", "asset": "BTC", "amount": "0.1"}, token=FUNDING)
        self.assertEqual((repaid["principal_repaid"], repaid["interest_repaid"]), ("0", "0.1"))
        before = self.financial()
        self.assertEqual(self.expect(200, "POST", "/v1/accounts/alice/loans", loan, token=FUNDING), borrowed)
        self.assertEqual(self.financial(), before)
        error = self.expect(409, "POST", "/v1/accounts/alice/loans", {**loan, "amount": "3"}, token=FUNDING)
        self.assertEqual(error["error"]["code"], "idempotency_conflict")
        self.expect(409, "POST", "/v1/credit/pool", {"command_id": "duplicate-capital", "asset": "BTC",
                    "amount": "10", "source_reference": "synthetic:capital:1"})
        self.assertEqual(self.financial(), before)
        self.assertEqual(self.credit.verify()["nonzero_liabilities"], 1)

    def test_operational_roles_cannot_cross_account_or_use_other_roles_mutations(self):
        command = {"command_id": "x", "asset": "BTC", "amount": "1"}
        cases = [("POST", "/v1/accounts/bob/loans", command, FUNDING),
                 ("POST", "/v1/accounts/alice/loans", command, READER),
                 ("POST", "/v1/accounts/alice/loans", command, ALICE),
                 ("POST", "/v1/accounts/alice/loans", command, RISK),
                 ("POST", "/v1/accounts/alice/interest", command, FUNDING),
                 ("POST", "/v1/accounts/alice/interest", command, RISK),
                 ("PUT", "/v1/accounts/alice/credit-limits", {"asset": "BTC", "limit": "5"}, FUNDING),
                 ("PUT", "/v1/credit/asset-limit", {"asset": "BTC", "limit": "5"}, ALICE),
                 ("POST", "/v1/credit/pool", {**command, "source_reference": "capital"}, RISK),
                 ("POST", "/v1/matching", {"symbol": "BTC-PERP"}, RISK),
                 ("POST", "/v1/spot-matching", {"symbol": "BTC-SPOT"}, ALICE),
                 ("GET", "/v1/trades", None, ALICE),
                 ("GET", "/v1/accounts/bob/spot-orders", None, READER),
                 ("POST", "/v1/accounts/alice/spot-orders", {"order_id": "x", "symbol": "BTC-SPOT", "quantity": "1", "limit_price": "100"}, RISK)]
        before = self.financial()
        for method, path, payload, token in cases:
            with self.subTest(path=path, token=token[0]):
                error = self.expect(403, method, path, payload, token=token)
                self.assertEqual(error["error"]["code"], "forbidden")
        self.assertEqual(self.financial(), before)

    def test_missing_components_fail_explicitly_after_authorization_without_mutation(self):
        before = self.financial()
        for component in ("credit", "spot", "matcher"):
            setattr(self.service, component, None)
        try:
            routes = [("POST", "/v1/accounts/alice/loans", {"command_id": "loan", "asset": "BTC", "amount": "1"}, FUNDING),
                      ("GET", "/v1/accounts/alice/spot-orders", None, READER),
                      ("POST", "/v1/matching", {"symbol": "BTC-PERP"}, ADMIN),
                      ("POST", "/v1/spot-matching", {"symbol": "BTC-SPOT"}, ADMIN),
                      ("GET", "/v1/trades", None, RISK)]
            for method, path, payload, token in routes:
                self.assertEqual(self.expect(501, method, path, payload, token=token)["error"]["code"], "feature_unavailable")
            self.expect(403, "POST", "/v1/accounts/bob/loans", {"command_id": "loan", "asset": "BTC", "amount": "1"}, token=FUNDING)
            self.expect(403, "POST", "/v1/matching", {"symbol": "BTC-PERP"}, token=RISK)
            self.expect(403, "GET", "/v1/accounts/alice/spot-orders", token=FUNDING)
        finally:
            self.service.credit, self.service.spot, self.service.matcher = self.credit, self.spot, self.matcher
        self.assertEqual(self.financial(), before)

    def test_spot_http_orders_match_actual_counterparties_and_release_only_remaining_cash(self):
        buy = {"order_id": "buy", "symbol": "BTC-SPOT", "quantity": "2", "limit_price": "100"}
        sell = {"order_id": "sell", "symbol": "BTC-SPOT", "quantity": "-1", "limit_price": "99"}
        self.expect(201, "POST", "/v1/accounts/alice/spot-orders", buy, token=ALICE)
        self.expect(201, "POST", "/v1/accounts/bob/spot-orders", sell, token=BOB)
        matched = self.expect(200, "POST", "/v1/spot-matching", {"symbol": "BTC-SPOT", "max_matches": 1})
        self.assertEqual(matched["confirmed_trades"], 1)
        receipt = matched["trades"][0]
        self.assertEqual((receipt["buy_account_id"], receipt["sell_account_id"], receipt["quantity"], receipt["price"]), ("alice", "bob", "1", "100"))
        self.assertEqual(self.service.account("alice")["balances"], {"BTC": "1", "USD": "899.96"})
        self.assertEqual(self.service.account("bob")["balances"], {"BTC": "4", "USD": "1099.96"})
        orders = self.expect(200, "GET", "/v1/accounts/alice/spot-orders", token=READER)
        self.assertEqual((orders[0]["status"], orders[0]["reserved_amount"]), ("PARTIALLY_FILLED", "100.04"))
        cancelled = self.expect(200, "POST", "/v1/accounts/alice/spot-orders/buy/cancel", {}, token=ALICE)
        self.assertEqual((cancelled["status"], cancelled["reserved_amount"]), ("CANCELLED", "0"))
        before = self.financial()
        self.assertEqual(self.expect(201, "POST", "/v1/accounts/alice/spot-orders", buy, token=ALICE)["status"], "CANCELLED")
        self.expect(409, "POST", "/v1/accounts/bob/spot-orders", {**sell, "order_id": "oversell", "quantity": "-5"}, token=BOB)
        self.assertEqual(self.financial(), before)
        self.assertEqual(self.spot.verify()["paired_fills"], 2)

    def test_linear_http_matching_produces_a_bounded_global_trade_audit(self):
        for account, token, quantity in (("alice", ALICE, "1"), ("bob", BOB, "-1")):
            self.expect(201, "POST", f"/v1/accounts/{account}/orders", {"order_id": "o", "symbol": "BTC-PERP", "quantity": quantity, "limit_price": "100"}, token=token)
        matched = self.expect(200, "POST", "/v1/matching", {"symbol": "BTC-PERP", "max_matches": 1})
        self.assertEqual(matched["confirmed_trades"], 1)
        receipt = matched["trades"][0]
        self.assertEqual((receipt["buy_account_id"], receipt["sell_account_id"]), ("alice", "bob"))
        audit = self.expect(200, "GET", "/v1/trades?after=0&limit=1", token=RISK)
        self.assertEqual(audit, [receipt])
        self.assertEqual(self.expect(200, "GET", f"/v1/trades?after={receipt['sequence']}&limit=1", token=RISK), [])
        self.assertEqual(self.service.account("alice")["positions"]["BTC-PERP"]["quantity"], "1")
        self.assertEqual(self.service.account("bob")["positions"]["BTC-PERP"]["quantity"], "-1")
        before = self.financial()
        self.assertEqual(self.expect(200, "POST", "/v1/matching", {"symbol": "BTC-PERP"})["confirmed_trades"], 0)
        self.assertEqual(self.financial(), before)
        self.assertEqual(self.matcher.verify(strict=True)["paired_fills"], 2)

    def test_original_order_lookup_survives_stale_market_without_relaxing_scope(self):
        payload = {"order_id": "original", "symbol": "BTC-PERP", "quantity": "1", "limit_price": "100"}
        original = self.expect(201, "POST", "/v1/accounts/alice/orders", payload, token=ALICE)
        self.now += timedelta(seconds=10)
        self.assertEqual(self.expect(200, "GET", "/v1/accounts/alice/orders/original", token=READER), original)
        self.expect(403, "GET", "/v1/accounts/alice/orders/original", token=BOB)
        self.expect(403, "GET", "/v1/accounts/alice/orders/original", token=FUNDING)
        self.expect(404, "GET", "/v1/accounts/alice/orders/missing", token=READER)

    def test_malformed_new_requests_do_not_change_real_financial_state(self):
        before = self.financial()
        cases = [("POST", "/v1/matching", {"symbol": "BTC-PERP", "max_matches": True}),
                 ("POST", "/v1/spot-matching", {"symbol": "BTC-SPOT", "max_matches": 1001}),
                 ("GET", "/v1/trades?limit=1001", None),
                 ("POST", "/v1/accounts/alice/loans", {"command_id": "l", "asset": "BTC", "amount": 1.0}),
                 ("POST", "/v1/accounts/alice/spot-orders", {"order_id": "o", "symbol": "BTC-SPOT", "quantity": "1", "limit_price": "100", "reduce_only": False})]
        for method, path, payload in cases:
            self.expect(400, method, path, payload)
        self.assertEqual(self.financial(), before)

    def test_configured_catalog_rejects_standalone_rest_fill_but_real_paired_match_succeeds(self):
        product = ProductSpec("BTC-PERP", ProductKind.LINEAR_PERPETUAL, "BTC", "USD", "USD",
                              D(".01"), D(".01"), D(1), status=TradingStatus.ACTIVE)
        catalog = ProductCatalog(1, {product.symbol: product})
        rules = PortfolioRules(1, {"USD": CollateralRule("USD", (CollateralTier(None, D(1)),), D(".5"))},
                               {}, {"tier-1": LinearMarginRule("tier-1", D(".1"), D(".05"))}, D(0))
        configured = ExchangeService(Database(Path(self.directory.name) / "configured.sqlite3"),
                                     {"USD": 8}, clock=lambda: self.now,
                                     product_catalog=catalog, portfolio_rules=rules)
        configured.matcher = Matcher(configured)
        configured.publish_market(MarketSnapshot(1, self.now, {"USD": AssetSpec(D(1), D(1))},
            {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))}))
        configured.set_kill_switch(False)
        for account in ("alice", "bob"):
            configured.create_account(account)
            configured.deposit(account, "usd", "USD", D(1000))
        self.server.service = configured
        for account, token, quantity in (("alice", ALICE, "1"), ("bob", BOB, "-1")):
            self.expect(201, "POST", f"/v1/accounts/{account}/orders", {"order_id": "paired", "symbol": "BTC-PERP", "quantity": quantity, "limit_price": "100"}, token=token)
        before = configured.accounts(), configured.ledger.journal(), configured.events(limit=1000)
        fill = {"fill_id": "manual", "quantity": "1", "price": "100"}
        self.expect(403, "POST", "/v1/accounts/alice/orders/paired/fills", fill, token=ALICE)
        rejected = self.expect(409, "POST", "/v1/accounts/alice/orders/paired/fills", fill)
        self.assertEqual(rejected["error"]["code"], "paired_execution_required")
        self.assertEqual((configured.accounts(), configured.ledger.journal(), configured.events(limit=1000)), before)
        self.assertEqual(self.expect(200, "POST", "/v1/matching", {"symbol": "BTC-PERP"})["confirmed_trades"], 1)
        self.assertEqual(configured.matcher.verify(strict=True)["paired_fills"], 2)

    def test_worker_health_does_not_expose_accounts_or_promote_one_account_block_to_outage(self):
        worker = self.service.worker = SimpleNamespace(last_report={"state": "not_started"})
        initial = self.expect(503, "GET", "/readyz", token=ALICE)
        self.assertEqual(initial["worker_reason"], "worker_not_started")
        self.assertEqual(self.expect(200, "GET", "/metrics", token=RISK)["worker"], worker.last_report)
        worker.last_report = {"state": "running", "plans": [{"account_id": "bob", "state": "BLOCKED"}],
                              "blocked": [{"account_id": "bob", "code": "insufficient_margin"}]}
        healthy = self.expect(200, "GET", "/readyz", token=ALICE)
        self.assertNotIn("bob", json.dumps(healthy))
        self.assertEqual(self.expect(200, "GET", "/metrics", token=RISK)["worker"], worker.last_report)
        self.expect(403, "GET", "/metrics", token=READER)
        worker.last_report = {"state": "blocked", "reason": "worker_failure"}
        self.assertEqual(self.expect(503, "GET", "/readyz", token=ALICE)["worker_reason"], "worker_failure")
        self.service.worker = None
        self.assertTrue(self.expect(200, "GET", "/readyz", token=ALICE)["ready"])


if __name__ == "__main__":
    unittest.main()
