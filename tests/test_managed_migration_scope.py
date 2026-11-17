"""Characterize managed migration scope at af7abab, without changing policy.

The spot-enriched fixtures use public standalone service classes on a quiescent
single shard. Those writes bypass ShardRouter's gate and are outside its routed
API guarantees. They are deliberately not described as a supported router spot
origin. No SQL mutation, fake funding claim, or private source-writer hook is used.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from http.client import HTTPConnection
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from unittest.mock import patch

from uta.durable_gateway import make_server
from uta.durable_process import DurableProcessRouter
from uta.gateway import Credential
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.portfolio import BorrowLimits, CollateralRule, CollateralTier, LinearMarginRule, PortfolioRules
from uta.products import ProductCatalog, ProductKind, ProductSpec, TradingStatus
from uta.service import ExchangeService, ServiceError
from uta.sharding import ShardRouter
from uta.spot import SpotExchange, locked_assets
from uta.storage import Database
from uta.writer_fence import WriterFence, WriterFenceError


ORIGIN_SHA = "af7abab42f421520496c7547abe88378b9db6cdc"
TOKEN = "M" * 43


class ManagedMigrationScopeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "authority"
        self.scales = {"USD": 8, "BTC": 8}
        self.max_age = timedelta(minutes=5)
        self.catalog = ProductCatalog(7, {
            "X": ProductSpec("X", ProductKind.LINEAR_PERPETUAL, "BTC", "USD", "USD",
                             D(".01"), D(".01"), D(1), status=TradingStatus.ACTIVE),
            "BTC-SPOT": ProductSpec("BTC-SPOT", ProductKind.SPOT_MARGIN, "BTC", "USD", "USD",
                                    D(".01"), D(".01"), D(1), status=TradingStatus.ACTIVE),
        })
        self.rules = PortfolioRules(13, {
            asset: CollateralRule(asset, (CollateralTier(None, D(1)),), D(".5"))
            for asset in self.scales
        }, {
            asset: BorrowLimits(asset, D(1000), D(".2"), D(".1"), D(".01"))
            for asset in self.scales
        }, {"tier-1": LinearMarginRule("tier-1", D(".1"), D(".05"))}, D(1000))

    def market(self, version=1):
        return MarketSnapshot(version, datetime.now(timezone.utc),
            {"USD": AssetSpec(D(1), D(1)), "BTC": AssetSpec(D(100), D(1))},
            {"X": InstrumentSpec(D(100), D(".1"), D(".05"))})

    def seed_public_router(self, router):
        """All account, deposit, limit, pool and debt writes enter public router APIs."""
        router.publish_market(self.market())
        router.set_kill_switch(False)
        for account in ("buyer", "seller"):
            router.create_account(account)
            router.deposit(account, "cash", "USD", D(1000))
        for account, asset, amount in (("buyer", "USD", D(20)), ("seller", "BTC", D(2))):
            router.configure_credit_asset_limit(0, asset, D(100))
            router.configure_credit_limit(account, asset, D(100))
            router.fund_credit_pool(0, "pool-" + asset, asset, amount,
                                    source_reference="synthetic:scope:" + asset)
            router.borrow(account, "loan-" + asset, asset, amount)
        router.accrue_interest("buyer", "interest", "USD", D(".25"))
        router.submit_order("buyer", "linear", "X", D(1), D(90))

    def source(self):
        source = ShardRouter(self.path, 1, self.scales, max_price_age=self.max_age,
                             product_catalog=self.catalog, portfolio_rules=self.rules,
                             decision_audit=True)
        self.seed_public_router(source)
        return source

    def add_offline_standalone_spot_extension(self):
        """Explicit scope exception: standalone writes bypass the router gate.

        The source is quiescent, single-shard, and uses identical policy/catalog.
        This is not a public ShardRouter spot endpoint or private writer bypass.
        """
        exchange = ExchangeService(Database(self.path / "shard-0000.sqlite3"), self.scales,
            max_price_age=self.max_age, product_catalog=self.catalog,
            portfolio_rules=self.rules, decision_audit=True)
        spot = SpotExchange(exchange, self.catalog)
        spot.submit_order("seller", "spot-sell", "BTC-SPOT", D(-2), D(100))
        spot.submit_order("buyer", "spot-buy", "BTC-SPOT", D(1), D(100))
        self.assertEqual(spot.match_once("BTC-SPOT")["confirmed_trades"], 1)
        spot.submit_order("buyer", "spot-open", "BTC-SPOT", D(".5"), D(90))
        self.assertEqual(spot.verify()["paired_fills"], 2)
        return exchange, spot

    def read(self, query, parameters=(), *, control=False):
        path = self.path / ("router.sqlite3" if control else "shard-0000.sqlite3")
        with Database(path).read_transaction() as connection:
            return [dict(row) for row in connection.execute(query, parameters)]

    def spot_state(self):
        return {table: self.read(f"SELECT * FROM {table} ORDER BY rowid")
                for table in ("uta_spot_config", "uta_spot_orders", "uta_spot_matches", "uta_spot_fills")}

    def balances_and_debt(self):
        return {table: self.read(f"SELECT * FROM {table} ORDER BY rowid")
                for table in ("ledger_balances", "uta_liabilities")}

    def locks(self, account):
        with Database(self.path / "shard-0000.sqlite3").read_transaction() as connection:
            return locked_assets(connection, account)

    def take_over(self):
        plan = DurableProcessRouter.inspect_takeover(self.path)
        router = DurableProcessRouter.take_over(self.path, managed=True,
            expected_layout_hash=plan["layout_hash"], lease_seconds=1, poll_interval=.01)
        self.addCleanup(router.close)
        return router

    def activate(self, router):
        router.start()
        self.assertFalse(router.publish_market(self.market(2), timeout=10)["publishing"])
        self.assertFalse(router.set_kill_switch(False, timeout=10)["halted"])

    def start_http(self, router):
        server = make_server(router, port=0,
            credentials=(Credential(TOKEN, "admin"),))
        thread = Thread(target=server.serve_forever, kwargs={"poll_interval": .01})
        thread.start()
        def close():
            server.shutdown()
            server.server_close()
            thread.join(3)
        self.addCleanup(close)
        return server

    def request(self, server, path, payload):
        client = HTTPConnection(*server.server_address, timeout=3)
        try:
            client.request("POST", path, json.dumps(payload), {
                "Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"})
            response = client.getresponse()
            return response.status, json.loads(response.read())
        finally:
            client.close()

    def test_public_router_only_source_preserves_linear_orders_and_mixed_liabilities(self):
        source = self.source()
        self.assertFalse(self.read("SELECT name FROM sqlite_master WHERE name='uta_spot_orders'"))
        # Public routed order admission is explicitly a linear endpoint.
        with self.assertRaises(ServiceError) as caught:
            source.submit_order("buyer", "wrong-endpoint", "BTC-SPOT", D(1), D(100))
        self.assertEqual(caught.exception.code, "unsupported_product")
        finances = self.balances_and_debt()
        orders = self.read("SELECT * FROM uta_orders ORDER BY rowid")
        router = self.take_over()
        self.assertEqual(finances, self.balances_and_debt())
        self.assertEqual(orders, self.read("SELECT * FROM uta_orders ORDER BY rowid"))
        self.activate(router)
        router.cancel_order("buyer", "cancel-linear", "linear")
        receipt = router.wait("cancel-linear", account_id="buyer", timeout=10)
        self.assertEqual((receipt["state"], receipt["result"]["status"]), ("SUCCEEDED", "CANCELLED"))
        router.repay("seller", "repay-btc", "BTC", D(1))
        receipt = router.wait("repay-btc", account_id="seller", timeout=10)
        self.assertEqual((receipt["state"], receipt["result"]["principal"]), ("SUCCEEDED", "1"))

    def test_offline_spot_extension_takeover_and_activation_accept_unserviceable_live_orders(self):
        self.source()
        exchange, spot = self.add_offline_standalone_spot_extension()
        before, finances = self.spot_state(), self.balances_and_debt()
        self.assertEqual({row["status"] for row in before["uta_spot_orders"]},
                         {"OPEN", "PARTIALLY_FILLED", "FILLED"})
        self.assertEqual(self.locks("seller"), {"BTC": D(1)})
        self.assertEqual(self.locks("buyer"), {"USD": D("45.018")})
        plan = DurableProcessRouter.inspect_takeover(self.path)
        self.assertEqual(plan["shards"][0]["orders"], 1)  # Only the linear table.
        self.assertNotIn("spot", json.dumps(plan).lower())
        # Observation only: migration and activation do not invoke the existing
        # spot verifier. This mock does not construct source state or alter rows.
        with patch.object(SpotExchange, "_verify", side_effect=AssertionError("spot verification invoked")):
            router = self.take_over()
            self.assertEqual(self.read("SELECT initialized FROM router_durable_config", control=True),
                             [{"initialized": 1}])
            self.assertTrue(WriterFence(Database(self.path / "shard-0000.sqlite3")).status()["managed"])
            self.activate(router)
        self.assertEqual(before, self.spot_state())
        self.assertEqual(finances, self.balances_and_debt())
        with self.assertRaises(WriterFenceError) as caught:
            spot.cancel_order("seller", "spot-sell")
        self.assertEqual(caught.exception.code, "writer_fenced")
        server = self.start_http(router)
        for path in ("/v2/accounts/seller/spot/orders", "/v2/accounts/seller/spot/orders/spot-sell/cancel",
                     "/v2/accounts/seller/spot/match"):
            status, body = self.request(server, path, {})
            self.assertEqual((status, body["error"]["code"]), (501, "unsupported_durable_operation"))
        status, _ = self.request(server, "/v2/accounts/seller/orders/spot-sell/cancel",
                                 {"command_id": "cancel-spot-via-linear"})
        self.assertEqual(status, 202)
        receipt = router.wait("cancel-spot-via-linear", account_id="seller", timeout=10)
        self.assertEqual((receipt["state"], receipt["error"]["code"]), ("REJECTED", "order_not_found"))
        router.repay("seller", "repay-locked-btc", "BTC", D(1))
        receipt = router.wait("repay-locked-btc", account_id="seller", timeout=10)
        self.assertEqual((receipt["state"], receipt["error"]["code"]), ("REJECTED", "insufficient_cash"))
        self.assertEqual(before, self.spot_state())
        self.assertEqual(finances, self.balances_and_debt())
        self.assertEqual(self.locks("seller"), {"BTC": D(1)})

    def test_offline_settled_spot_history_is_preserved_but_not_verified_by_takeover(self):
        self.source()
        exchange, spot = self.add_offline_standalone_spot_extension()
        spot.cancel_order("seller", "spot-sell")
        spot.cancel_order("buyer", "spot-open")
        self.assertEqual(spot.verify()["matches"], 1)
        self.assertEqual(self.locks("buyer"), {})
        self.assertEqual(self.locks("seller"), {})
        before, finances = self.spot_state(), self.balances_and_debt()
        with patch.object(SpotExchange, "_verify", side_effect=AssertionError("spot verification invoked")):
            router = self.take_over()
            self.activate(router)
        self.assertEqual(before, self.spot_state())
        self.assertEqual(finances, self.balances_and_debt())
        # Explicit independent diagnostic: invoke the existing verifier on a
        # guarded READ transaction. This private read-only audit is not a source
        # writer, migration behavior, or a claimed supported customer endpoint.
        with exchange.database.read_transaction() as connection:
            report = spot._verify(connection)
        self.assertEqual((report["orders"], report["matches"], report["paired_fills"]), (3, 1, 2))
        router.repay("seller", "repay-released-btc", "BTC", D(1))
        receipt = router.wait("repay-released-btc", account_id="seller", timeout=10)
        self.assertEqual((receipt["state"], receipt["result"]["principal"]), ("SUCCEEDED", "1"))

    def test_offline_spot_extension_inside_initialize_bootstrap_is_also_sealed(self):
        def bootstrap(source):
            self.seed_public_router(source)
            self.add_offline_standalone_spot_extension()
        router = DurableProcessRouter.initialize(self.path, 1, self.scales, managed=True,
            bootstrap=bootstrap, max_price_age=self.max_age, product_catalog=self.catalog,
            portfolio_rules=self.rules, decision_audit=True, lease_seconds=1, poll_interval=.01)
        self.addCleanup(router.close)
        self.assertTrue(WriterFence(Database(self.path / "shard-0000.sqlite3")).status()["managed"])
        self.assertEqual(self.locks("seller"), {"BTC": D(1)})
        self.assertEqual(self.read("SELECT initialized FROM router_durable_config", control=True),
                         [{"initialized": 1}])


if __name__ == "__main__":
    unittest.main()
