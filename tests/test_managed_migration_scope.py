"""Enforce LOCAL-MANAGED-MIG-001 after the independent af7abab review.

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
from uta.durable_process import DurableProcessRouter, _preflight_managed_spot_sources
from uta.gateway import Credential
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.portfolio import BorrowLimits, CollateralRule, CollateralTier, LinearMarginRule, PortfolioRules
from uta.products import ProductCatalog, ProductKind, ProductSpec, TradingStatus
from uta.service import ExchangeService, ServiceError
from uta.sharding import ShardRouter
from uta.spot import SpotExchange, locked_assets
from uta.storage import Database, DurableLedger
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

    def source(self, *, legacy=False):
        source = ShardRouter(self.path, 1, self.scales, max_price_age=self.max_age,
                             product_catalog=None if legacy else self.catalog,
                             portfolio_rules=None if legacy else self.rules,
                             decision_audit=True)
        self.seed_public_router(source)
        return source

    def add_offline_standalone_spot_extension(self, *, legacy=False):
        """Explicit scope exception: standalone writes bypass the router gate.

        The source is quiescent, single-shard, and uses identical policy/catalog.
        This is not a public ShardRouter spot endpoint or private writer bypass.
        """
        exchange = ExchangeService(Database(self.path / "shard-0000.sqlite3"), self.scales,
            max_price_age=self.max_age, product_catalog=None if legacy else self.catalog,
            portfolio_rules=None if legacy else self.rules, decision_audit=True)
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

    def financial_state(self):
        # Halting appends its own operational audit event; it never overwrites
        # prior events or changes the financial projections compared here.
        return {table: self.read(f"SELECT * FROM {table}" +
                    (" WHERE event_type!='KILL_SWITCH_CHANGED'" if table == "uta_events" else "") + " ORDER BY rowid")
                for table in ("uta_accounts", "uta_orders", "uta_positions", "uta_liabilities", "uta_events",
                              "ledger_events", "ledger_postings", "ledger_balances")}

    def assert_unsealed(self, shard_count=1):
        self.assertFalse(self.read("SELECT name FROM sqlite_master WHERE name IN "
            "('router_durable_config','router_durable_takeover_events')", control=True))
        for index in range(shard_count):
            database = Database(self.path / f"shard-{index:04d}.sqlite3")
            self.assertFalse(WriterFence(database).status()["managed"])
            with database.read_transaction() as connection:
                self.assertIsNone(connection.execute(
                    "SELECT name FROM sqlite_master WHERE name='uta_command_config'").fetchone())

    def cancel_source_spot(self, spot):
        spot.cancel_order("seller", "spot-sell")
        spot.cancel_order("buyer", "spot-open")

    def damage_source(self, statement):
        """Explicit negative-test corruption; never a claimed public source origin."""
        with Database(self.path / "shard-0000.sqlite3").transaction() as connection:
            connection.execute(statement)

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

    def test_offline_spot_extension_is_rejected_before_sealing_without_releasing_locks(self):
        self.source()
        _, spot = self.add_offline_standalone_spot_extension()
        before, finances = self.spot_state(), self.financial_state()
        self.assertEqual({row["status"] for row in before["uta_spot_orders"]},
                         {"OPEN", "PARTIALLY_FILLED", "FILLED"})
        self.assertEqual(self.locks("seller"), {"BTC": D(1)})
        self.assertEqual(self.locks("buyer"), {"USD": D("45.018")})
        plan = DurableProcessRouter.inspect_takeover(self.path)
        self.assertEqual(plan["shards"][0]["orders"], 1)  # Only the linear table.
        self.assertNotIn("spot", json.dumps(plan).lower())
        with patch.object(ExchangeService, "__init__", side_effect=AssertionError("financial constructor")), \
                patch.object(DurableLedger, "__init__", side_effect=AssertionError("ledger constructor")):
            with self.assertRaises(ServiceError) as caught:
                self.take_over()
        self.assertEqual((caught.exception.code, caught.exception.status), ("managed_spot_state_unsupported", 409))
        self.assertIn("original authority", str(caught.exception))
        self.assert_unsealed()
        self.assertEqual(before, self.spot_state())
        self.assertEqual(finances, self.financial_state())
        self.assertEqual(self.locks("seller"), {"BTC": D(1)})
        # Original authority remains usable for cancellation. A fresh takeover
        # succeeds after actual old-authority cancellation, without deleting it.
        self.cancel_source_spot(spot)
        self.assertEqual(self.locks("buyer"), {})
        self.assertEqual(self.locks("seller"), {})
        self.take_over()

    def test_offline_settled_spot_history_is_verified_and_preserved_through_activation(self):
        self.source()
        exchange, spot = self.add_offline_standalone_spot_extension()
        self.cancel_source_spot(spot)
        self.assertEqual(spot.verify()["matches"], 1)
        self.assertEqual(self.locks("buyer"), {})
        self.assertEqual(self.locks("seller"), {})
        before, finances = self.spot_state(), self.balances_and_debt()
        original = SpotExchange._verify
        with patch.object(SpotExchange, "_verify", autospec=True, side_effect=original) as verification:
            router = self.take_over()
            self.assertGreaterEqual(verification.call_count, 2)  # Preflight and token-owned final check.
            self.activate(router)
        self.assertEqual(before, self.spot_state())
        self.assertEqual(finances, self.balances_and_debt())
        # The public verifier now joins an explicitly guarded read transaction.
        with exchange.database.read_transaction() as connection:
            report = spot.verify(connection=connection)
        self.assertEqual((report["orders"], report["matches"], report["paired_fills"]), (3, 1, 2))
        router.repay("seller", "repay-released-btc", "BTC", D(1))
        receipt = router.wait("repay-released-btc", account_id="seller", timeout=10)
        self.assertEqual((receipt["state"], receipt["result"]["principal"]), ("SUCCEEDED", "1"))
        server = self.start_http(router)
        for path in ("/v2/accounts/seller/spot/orders", "/v2/accounts/seller/spot/orders/spot-sell/cancel",
                     "/v2/accounts/seller/spot/match"):
            status, body = self.request(server, path, {})
            self.assertEqual((status, body["error"]["code"]), (501, "unsupported_durable_operation"))

    def test_offline_spot_bootstrap_rejection_preserves_committed_source_unsealed_and_halted(self):
        facts = {}
        def bootstrap(source):
            self.seed_public_router(source)
            _, facts["spot"] = self.add_offline_standalone_spot_extension()
            facts["financial"], facts["orders"] = self.financial_state(), self.spot_state()
        with self.assertRaises(ServiceError) as caught:
            DurableProcessRouter.initialize(self.path, 1, self.scales, managed=True,
                bootstrap=bootstrap, max_price_age=self.max_age, product_catalog=self.catalog,
                portfolio_rules=self.rules, decision_audit=True, lease_seconds=1, poll_interval=.01)
        self.assertEqual((caught.exception.code, caught.exception.status), ("managed_spot_state_unsupported", 409))
        self.assert_unsealed()
        self.assertEqual(facts["financial"], self.financial_state())
        self.assertEqual(facts["orders"], self.spot_state())
        self.assertEqual(self.locks("seller"), {"BTC": D(1)})
        state = DurableProcessRouter.inspect_takeover(self.path)["state"]
        self.assertTrue(state["halted"])
        self.assertEqual(state["error"], "managed_spot_state_unsupported")
        self.assertEqual(self.read("SELECT value FROM uta_config WHERE key='halted'"), [{"value": "true"}])
        self.cancel_source_spot(facts["spot"])
        self.take_over()  # Existing bootstrap facts require explicit takeover, not initialize retry.

    def test_terminal_history_preflight_and_verifier_open_no_financial_constructor_or_writer(self):
        source = self.source()
        exchange, spot = self.add_offline_standalone_spot_extension()
        self.cancel_source_spot(spot)
        before, finances = self.spot_state(), self.financial_state()
        with patch.object(ExchangeService, "__init__", side_effect=AssertionError("financial constructor")), \
                patch.object(DurableLedger, "__init__", side_effect=AssertionError("ledger constructor")), \
                patch.object(ExchangeService, "_transaction", side_effect=AssertionError("financial transaction")):
            inspection = SpotExchange(exchange, self.catalog, initialize=False)
            self.assertEqual(inspection.verify()["matches"], 1)
            _preflight_managed_spot_sources(source)
        self.assert_unsealed()
        self.assertEqual(before, self.spot_state())
        self.assertEqual(finances, self.financial_state())

    def test_live_spot_on_last_shard_does_not_seal_any_earlier_shard(self):
        source = ShardRouter(self.path, 2, self.scales, max_price_age=self.max_age,
            product_catalog=self.catalog, portfolio_rules=self.rules, decision_audit=True)
        source.publish_market(self.market())
        source.set_kill_switch(False)
        account = next(f"last-{i}" for i in range(100) if source.shard_for(f"last-{i}") == 1)
        source.create_account(account)
        source.deposit(account, "cash", "USD", D(1000))
        source.deposit(account, "btc", "BTC", D(1))
        exchange = ExchangeService(Database(self.path / "shard-0001.sqlite3"), self.scales,
            max_price_age=self.max_age, product_catalog=self.catalog, portfolio_rules=self.rules, decision_audit=True)
        spot = SpotExchange(exchange, self.catalog)
        before = spot.submit_order(account, "live", "BTC-SPOT", D(-1), D(100))
        with self.assertRaises(ServiceError) as caught:
            self.take_over()
        self.assertEqual((caught.exception.code, caught.exception.status), ("managed_spot_state_unsupported", 409))
        self.assert_unsealed(shard_count=2)
        self.assertEqual(spot.orders(account), [before])
        self.assertEqual(spot.cancel_order(account, "live")["status"], "CANCELLED")

    def test_corrupt_terminal_history_is_rejected_before_sealing_without_schema_repair(self):
        self.source()
        _, spot = self.add_offline_standalone_spot_extension()
        self.cancel_source_spot(spot)
        before = self.spot_state()
        self.damage_source("DROP TRIGGER uta_spot_matches_no_update")
        with self.assertRaises(ServiceError) as caught:
            self.take_over()
        self.assertEqual((caught.exception.code, caught.exception.status), ("spot_corrupt", 503))
        self.assert_unsealed()
        self.assertEqual(before, self.spot_state())
        self.assertFalse(self.read("SELECT name FROM sqlite_master WHERE name='uta_spot_matches_no_update'"))

    def test_terminal_order_with_residual_lock_is_rejected_without_unlocking(self):
        self.source()
        _, spot = self.add_offline_standalone_spot_extension()
        self.cancel_source_spot(spot)
        self.damage_source("UPDATE uta_spot_orders SET reserved_amount='1' WHERE order_id='spot-sell'")
        before = self.spot_state()
        with self.assertRaises(ServiceError) as caught:
            self.take_over()
        self.assertEqual((caught.exception.code, caught.exception.status), ("managed_spot_state_unsupported", 409))
        self.assert_unsealed()
        self.assertEqual(before, self.spot_state())

    def test_post_preflight_spot_writer_violation_leaves_fenced_incomplete_forward_recovery(self):
        self.source()
        exchange, spot = self.add_offline_standalone_spot_extension()
        self.cancel_source_spot(spot)
        original = WriterFence.enable
        facts = {}
        def race(fence, authority):
            # Deterministic forbidden-quiescence interleaving: a real public
            # standalone writer acts after preflight and before its shard seal.
            spot.submit_order("buyer", "raced", "BTC-SPOT", D(".1"), D(80))
            facts["spot"], facts["financial"] = self.spot_state(), self.financial_state()
            return original(fence, authority)
        with patch.object(WriterFence, "enable", autospec=True, side_effect=race):
            with self.assertRaises(ServiceError) as caught:
                self.take_over()
        self.assertEqual((caught.exception.code, caught.exception.status), ("managed_spot_state_unsupported", 409))
        self.assertEqual(self.read("SELECT initialized FROM router_durable_config", control=True), [{"initialized": 0}])
        self.assertTrue(WriterFence(exchange.database).status()["managed"])
        self.assertEqual(facts["spot"], self.spot_state())
        self.assertEqual(facts["financial"], self.financial_state())
        self.assertTrue(DurableProcessRouter.inspect_takeover(self.path)["state"]["halted"])
        with self.assertRaises(WriterFenceError):
            spot.cancel_order("buyer", "raced")
        with self.assertRaises(ServiceError) as reopening:
            DurableProcessRouter(self.path)
        self.assertEqual(reopening.exception.code, "managed_bootstrap_incomplete")

    def test_invalid_terminal_schema_configuration_and_receipts_reject_without_repair(self):
        faults = {
            "schema": ("UPDATE uta_spot_schema SET version=99", "spot_schema_version"),
            "partial-schema": ("DROP TABLE uta_spot_fills", "spot_corrupt"),
            "missing-config": ("DELETE FROM uta_spot_config", "spot_corrupt"),
            "fee-policy": ("UPDATE uta_spot_config SET fee_rate='.002'", "spot_corrupt"),
            "nonfinite-lock": ("UPDATE uta_spot_orders SET reserved_amount='NaN' WHERE order_id='spot-sell'", "spot_corrupt"),
            "negative-lock": ("UPDATE uta_spot_orders SET reserved_amount='-1' WHERE order_id='spot-sell'", "spot_corrupt"),
            "receipt-aggregate": ("UPDATE uta_spot_orders SET filled_quantity='.5' WHERE order_id='spot-buy'", "spot_corrupt"),
            "product-asset": ("UPDATE uta_spot_orders SET base_asset='USD' WHERE order_id='spot-buy'", "spot_corrupt"),
            "catalog-policy": ("UPDATE uta_spot_config SET catalog=replace(catalog, '\"version\":7', '\"version\":8')", "spot_corrupt"),
        }
        for name, (statement, expected_code) in faults.items():
            with self.subTest(fault=name):
                self.path = Path(self.temporary.name) / name
                self.source()
                _, spot = self.add_offline_standalone_spot_extension()
                self.cancel_source_spot(spot)
                self.damage_source(statement)
                schema = self.read("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY name")
                finances = self.financial_state()
                with self.assertRaises(ServiceError) as caught:
                    self.take_over()
                self.assertEqual((caught.exception.code, caught.exception.status), (expected_code, 503))
                self.assert_unsealed()
                self.assertEqual(schema, self.read("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY name"))
                self.assertEqual(finances, self.financial_state())

    def test_terminal_legacy_reference_history_uses_its_persisted_spot_catalog(self):
        self.source(legacy=True)
        _, spot = self.add_offline_standalone_spot_extension(legacy=True)
        self.cancel_source_spot(spot)
        before = self.spot_state()
        self.take_over()
        self.assertEqual(before, self.spot_state())

    def test_settled_spot_bootstrap_can_be_verified_then_sealed_and_activated(self):
        facts = {}
        def bootstrap(source):
            self.seed_public_router(source)
            _, spot = self.add_offline_standalone_spot_extension()
            self.cancel_source_spot(spot)
            facts["spot"], facts["balances"] = self.spot_state(), self.balances_and_debt()
        router = DurableProcessRouter.initialize(self.path, 1, self.scales, managed=True,
            bootstrap=bootstrap, max_price_age=self.max_age, product_catalog=self.catalog,
            portfolio_rules=self.rules, decision_audit=True, lease_seconds=1, poll_interval=.01)
        self.addCleanup(router.close)
        self.activate(router)
        self.assertEqual(facts["spot"], self.spot_state())
        self.assertEqual(facts["balances"], self.balances_and_debt())

    def test_post_preflight_initializer_writer_violation_keeps_fence_and_incomplete_manifest(self):
        facts = {}
        def bootstrap(source):
            self.seed_public_router(source)
            facts["exchange"], facts["spot"] = self.add_offline_standalone_spot_extension()
            self.cancel_source_spot(facts["spot"])
        original = WriterFence.enable
        def race(fence, authority):
            # Deliberately violate offline quiescence through the old public
            # standalone API after initialization has already halted it.
            facts["exchange"].set_kill_switch(False)
            facts["spot"].submit_order("buyer", "raced", "BTC-SPOT", D(".1"), D(80))
            facts["orders"], facts["financial"] = self.spot_state(), self.financial_state()
            return original(fence, authority)
        with patch.object(WriterFence, "enable", autospec=True, side_effect=race):
            with self.assertRaises(ServiceError) as caught:
                DurableProcessRouter.initialize(self.path, 1, self.scales, managed=True,
                    bootstrap=bootstrap, max_price_age=self.max_age, product_catalog=self.catalog,
                    portfolio_rules=self.rules, decision_audit=True)
        self.assertEqual((caught.exception.code, caught.exception.status), ("managed_spot_state_unsupported", 409))
        self.assertTrue(WriterFence(facts["exchange"].database).status()["managed"])
        self.assertEqual(self.read("SELECT initialized FROM router_durable_config", control=True), [{"initialized": 0}])
        self.assertEqual(facts["orders"], self.spot_state())
        self.assertEqual(facts["financial"], self.financial_state())
        self.assertTrue(DurableProcessRouter.inspect_takeover(self.path)["state"]["halted"])

    def test_token_owned_final_check_rejects_terminal_receipt_damage_after_preflight(self):
        self.source()
        _, spot = self.add_offline_standalone_spot_extension()
        self.cancel_source_spot(spot)
        original = WriterFence.enable
        def corrupt_between_preflight_and_fence(fence, authority):
            # Explicit fault injection into a legitimate terminal source; this
            # damage is not presented as an ordinary public order API operation.
            self.damage_source("UPDATE uta_spot_orders SET filled_quantity='.5' WHERE order_id='spot-buy'")
            return original(fence, authority)
        with patch.object(WriterFence, "enable", autospec=True, side_effect=corrupt_between_preflight_and_fence):
            with self.assertRaises(ServiceError) as caught:
                self.take_over()
        self.assertEqual((caught.exception.code, caught.exception.status), ("spot_corrupt", 503))
        self.assertTrue(WriterFence(Database(self.path / "shard-0000.sqlite3")).status()["managed"])
        self.assertEqual(self.read("SELECT initialized FROM router_durable_config", control=True), [{"initialized": 0}])
        self.assertEqual(self.read("SELECT filled_quantity FROM uta_spot_orders WHERE order_id='spot-buy'"),
                         [{"filled_quantity": ".5"}])
        self.assertTrue(DurableProcessRouter.inspect_takeover(self.path)["state"]["halted"])

    def test_missing_all_spot_tables_with_audit_history_is_rejected_without_recreation(self):
        self.source()
        _, spot = self.add_offline_standalone_spot_extension()
        self.cancel_source_spot(spot)
        for table in ("uta_spot_fills", "uta_spot_matches", "uta_spot_orders", "uta_spot_config", "uta_spot_schema"):
            self.damage_source("DROP TABLE " + table)
        self.assertFalse(self.read("SELECT name FROM sqlite_master WHERE name GLOB 'uta_spot_*'"))
        self.assertTrue(self.read("SELECT sequence FROM uta_events WHERE event_type='SPOT_MATCH_CONFIRMED'"))
        with self.assertRaises(ServiceError) as caught:
            self.take_over()
        self.assertEqual((caught.exception.code, caught.exception.status), ("spot_corrupt", 503))
        self.assert_unsealed()
        self.assertFalse(self.read("SELECT name FROM sqlite_master WHERE name GLOB 'uta_spot_*'"))


if __name__ == "__main__":
    unittest.main()
