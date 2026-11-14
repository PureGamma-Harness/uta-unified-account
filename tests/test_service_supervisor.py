from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from pathlib import Path
import tempfile
import unittest

from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ExchangeService, ServiceError
from uta.storage import Database


class ServiceSupervisorTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "risk.sqlite3"
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.service = self.reopen()
        self.service.create_account("alice")
        self.publish()
        self.service.set_kill_switch(False)
        self.service.deposit("alice", "initial", "USD", D(1000))

    def tearDown(self):
        self.directory.cleanup()

    def reopen(self):
        return ExchangeService(Database(self.path), {"USD": 8}, clock=lambda: self.now)

    def publish(self, version=1, mark="100"):
        self.service.publish_market(MarketSnapshot(version, self.now,
                                    {"USD": AssetSpec(D(1), D(1))},
                                    {"BTC-PERP": InstrumentSpec(D(mark), D("0.1"), D("0.05"))}))

    def distress(self):
        self.service.submit_order("alice", "buy", "BTC-PERP", D(90), D(100))
        self.service.apply_fill("alice", "buy", "initialfill", D(90), D(100))
        self.service.submit_order("alice", "spare", "BTC-PERP", D(1), D(100))
        self.publish(2, "90")

    def test_distress_cancels_and_queues_once_across_restarts(self):
        self.distress()
        result = self.service.supervise_account("alice")
        self.assertEqual(result["state"], "LIQUIDATING")
        self.assertEqual(result["cycle"], 1)
        self.assertEqual(result["revision"], 1)
        self.assertEqual([order["order_id"] for order in result["cancelled_orders"]], ["spare"])
        self.assertEqual(result["created_orders"][0]["quantity"], "-90")
        self.assertTrue(result["created_orders"][0]["reduce_only"])
        self.assertEqual(self.service.account("alice")["positions"]["BTC-PERP"]["quantity"], "90")
        before = self.service.events(limit=1000)
        repeated = self.reopen().supervise_account("alice")
        self.assertEqual(repeated["state"], "LIQUIDATING")
        self.assertFalse(repeated["replanned"])
        self.assertEqual(repeated["created_orders"], [])
        self.assertEqual(self.service.events(limit=1000), before)
        with self.assertRaises(ServiceError) as frozen:
            self.service.submit_order("alice", "newrisk", "BTC-PERP", D(1), D(90))
        self.assertEqual(frozen.exception.code, "account_frozen")

    def test_concurrent_cycles_generate_one_plan(self):
        self.distress()
        services = [self.reopen() for _ in range(6)]
        with ThreadPoolExecutor(max_workers=6) as pool:
            cycles = list(pool.map(lambda s: s.supervise_account("alice"), services))
        self.assertEqual(sum(bool(cycle["created_orders"]) for cycle in cycles), 1)
        self.assertEqual(len([order for order in self.service.orders("alice") if order["status"] == "OPEN"]), 1)

    def test_partial_fill_replans_remaining_position_and_market_version(self):
        self.distress()
        first = self.service.supervise_account("alice")
        identifier = first["created_orders"][0]["order_id"]
        self.service.apply_fill("alice", identifier, "partial", D(-45), D(90))
        second = self.service.supervise_account("alice")
        self.assertEqual(second["cycle"], 1)
        self.assertEqual(second["revision"], 2)
        self.assertEqual(second["cancelled_orders"][0]["order_id"], identifier)
        self.assertEqual(second["created_orders"][0]["quantity"], "-45")
        self.publish(3, "89")
        third = self.service.supervise_account("alice")
        self.assertEqual(third["revision"], 3)
        self.assertEqual(third["created_orders"][0]["limit_price"], "89")

    def test_recovery_uses_hysteresis_and_cancels_pending_local_plan(self):
        self.distress()
        self.service.supervise_account("alice")
        self.service.deposit("alice", "near", "USD", D(330))
        self.assertEqual(self.service.supervise_account("alice")["state"], "LIQUIDATING")
        self.service.deposit("alice", "recover", "USD", D(30))
        recovered = self.service.supervise_account("alice")
        self.assertEqual(recovered["state"], "NORMAL")
        self.assertEqual(len(recovered["cancelled_orders"]), 1)
        self.assertEqual(recovered["created_orders"], [])
        self.service.deposit("alice", "initialmargin", "USD", D(500))
        self.service.submit_order("alice", "newrisk", "BTC-PERP", D("0.01"), D(90))

    def test_stale_cycle_preserves_pending_plan_and_persisted_freeze(self):
        self.distress()
        first = self.service.supervise_account("alice")
        before_orders, before_events = self.service.orders("alice"), self.service.events(limit=1000)
        self.now += timedelta(seconds=6)
        blocked = self.service.supervise_account("alice")
        self.assertEqual(blocked["state"], "BLOCKED")
        self.assertEqual(blocked["persisted_state"], "LIQUIDATING")
        self.assertEqual(blocked["revision"], first["revision"])
        self.assertEqual(self.service.orders("alice"), before_orders)
        self.assertEqual(self.service.events(limit=1000), before_events)

    def test_flat_zero_account_is_normal_and_flat_negative_equity_is_bankrupt(self):
        self.service.create_account("empty")
        result = self.service.supervise_account("empty")
        self.assertEqual(result["state"], "NORMAL")
        self.assertEqual(result["created_orders"], [])
        with self.service._transaction() as connection:
            connection.execute("INSERT INTO uta_liabilities VALUES ('empty','USD','1','0')")
        result = self.service.supervise_account("empty")
        self.assertEqual(result["state"], "BANKRUPT")
        self.assertEqual(result["created_orders"], [])
        self.assertEqual(self.service.account("empty")["liabilities"]["USD"]["total"], "1")
        self.assertEqual(self.service.risk("empty")["equity"], "-1")

    def test_unrepresentable_liquidation_mark_blocks_without_creating_any_orders(self):
        self.distress()
        self.publish(3, "90.000000001")
        blocked = self.service.supervise_account("alice")
        self.assertEqual(blocked["state"], "BLOCKED")
        self.assertEqual(blocked["created_orders"], [])
        self.assertEqual(len(blocked["cancelled_orders"]), 1)
        self.assertTrue(all(order["status"] not in ("OPEN", "PARTIALLY_FILLED") for order in self.service.orders("alice")))
        before = self.service.events(limit=1000)
        self.assertFalse(self.service.supervise_account("alice")["replanned"])
        self.assertEqual(self.service.events(limit=1000), before)

    def test_customer_cannot_cancel_or_forge_supervisor_orders_and_damaged_plan_repairs(self):
        self.distress()
        plan = self.service.supervise_account("alice")["created_orders"][0]
        with self.assertRaises(ServiceError) as protected:
            self.service.cancel_order("alice", plan["order_id"])
        self.assertEqual(protected.exception.code, "liquidation_order_protected")
        with self.assertRaises(ServiceError):
            self.service.submit_order("alice", "liq:forged", "BTC-PERP", D(-1), D(90), reduce_only=True)
        # A matching-policy cancellation must be detected even without a new
        # market version or changed position, so a missing plan cannot linger.
        with self.service._transaction() as connection:
            row = connection.execute("SELECT * FROM uta_orders WHERE account_id='alice' AND order_id=?", (plan["order_id"],)).fetchone()
            self.service._cancel_locked(connection, row, "matching_policy")
        repaired = self.service.supervise_account("alice")
        self.assertEqual(repaired["revision"], 2)
        self.assertEqual(len(repaired["created_orders"]), 1)

    def test_account_events_apply_predicate_before_limit(self):
        self.service.create_account("other")
        self.service.deposit("other", "other", "USD", D(1))
        first = self.service.account_events("other", limit=1)
        self.assertEqual(len(first), 1)
        self.assertTrue(all(event["account_id"] == "other" for event in first))
        next_page = self.service.account_events("other", after=first[0]["sequence"], limit=1)
        self.assertEqual(next_page[0]["event_type"], "DEPOSIT_POSTED")


if __name__ == "__main__":
    unittest.main()
