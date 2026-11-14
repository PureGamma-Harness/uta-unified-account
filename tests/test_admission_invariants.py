"""Independent command-state checks for the grouped admission authority.

The reference below uses only rational quantities and a cash/reserve book. It
does not call the production risk calculator, reserve helper or admission path
to generate expected results.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D, Inexact, Rounded, localcontext
from fractions import Fraction as F
import json
from pathlib import Path
import random
import sqlite3
import tempfile
from threading import Barrier, Event
import unittest
from unittest.mock import patch

from uta.admission import AdmissionBatcher
from uta.examples import synthetic_policy
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ExchangeService, ServiceError
from uta.storage import Database


def reserve(quantity, limit):
    quantity, limit, mark = F(quantity), F(limit), F(100)
    fee_units = abs(quantity) * limit * F(4, 10000) * 10**8
    fee = F(-(-fee_units.numerator // fee_units.denominator), 10**8)
    return abs(quantity) * max(mark, limit) / 10 + max(F(0), quantity * (limit - mark)) + fee


class CashReserveReference:
    def __init__(self, capacity):
        self.capacity = dict(capacity)
        self.orders = {}
        self.accepted = 0
        self.cancelled = 0

    def held(self, account):
        return sum((entry["reserve"] for (owner, _), entry in self.orders.items()
                    if owner == account and entry["active"]), F(0))

    def command(self, kind, account, identifier, quantity=None, price=None):
        key = account, identifier
        previous = self.orders.get(key)
        if kind == "cancel":
            if previous is None:
                return "order_not_found", None
            if previous["active"]:
                previous["active"] = False
                self.cancelled += 1
            return None, "CANCELLED"
        payload = F(quantity), F(price)
        if previous is not None:
            if previous["payload"] != payload:
                return "idempotency_conflict", None
            return None, "OPEN" if previous["active"] else "CANCELLED"
        amount = reserve(*payload)
        if amount > self.capacity[account] - self.held(account):
            return "insufficient_margin", None
        self.orders[key] = {"payload": payload, "reserve": amount, "active": True}
        self.accepted += 1
        return None, "OPEN"


class CommitGateDatabase(Database):
    """Pause after business writes, before the real outer commit."""
    enabled = False

    def __init__(self, path):
        super().__init__(path)
        self.before_commit = Event()
        self.allow_commit = Event()

    @contextmanager
    def transaction(self):
        with super().transaction() as conn:
            yield conn
            if self.enabled:
                self.before_commit.set()
                if not self.allow_commit.wait(5):
                    raise RuntimeError("test did not release commit gate")


class AdmissionInvariants(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "group.sqlite3"
        self.now = datetime(2026, 11, 14, tzinfo=timezone.utc)
        self.service = self.reopen()
        self.service.publish_market(self.market())
        self.service.set_kill_switch(False)

    def reopen(self, *, path=None, database=None, configured=False):
        kwargs = {}
        if configured:
            catalog, rules = synthetic_policy()
            kwargs = {"product_catalog": catalog, "portfolio_rules": rules}
        return ExchangeService(database or Database(path or self.path), {"USD": 8, "BTC": 8},
                               clock=lambda: self.now, **kwargs)

    def market(self, version=1):
        return MarketSnapshot(version, self.now,
            {"USD": AssetSpec(D(1), D(1)), "BTC": AssetSpec(D(100), D(".8"))},
            {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))})

    def fund(self, name, amount, service=None):
        service = service or self.service
        service.create_account(name)
        service.deposit(name, "funding", "USD", D(amount))

    def batcher(self, service=None, **kwargs):
        batcher = AdmissionBatcher(service or self.service, **kwargs)
        self.addCleanup(batcher.close)
        return batcher

    def assert_error(self, future, expected):
        with self.assertRaises(ServiceError) as error:
            future.result(timeout=10)
        self.assertEqual(error.exception.code, expected)

    def test_seeded_fifo_trace_matches_independent_cash_and_reserve_book(self):
        cash = {"alice": "20.08", "bob": "11.25", "carol": "3.14"}
        capacities = {account: F(amount) for account, amount in cash.items()}
        for account, amount in cash.items():
            self.fund(account, amount)
        model = CashReserveReference(capacities)
        batcher = self.batcher(max_batch_size=16, max_delay_ms=20)
        rng = random.Random(872511)
        futures = []
        for index in range(160):
            account = rng.choice(tuple(capacities))
            identifier = "order-" + str(rng.randrange(14))
            if rng.randrange(4) == 0:
                expected = model.command("cancel", account, identifier)
                future = batcher.cancel_order(account, identifier)
            else:
                quantity = rng.choice((".1", "-.1", ".25", "-.25", ".5", "-.5", "1", "-1"))
                price = rng.choice(("99", "100", "101"))
                expected = model.command("submit", account, identifier, quantity, price)
                future = batcher.submit_order(account, identifier, "BTC-PERP", D(quantity), D(price))
            futures.append((future, expected))
        for future, (code, status) in futures:
            if code:
                self.assert_error(future, code)
            else:
                self.assertEqual(future.result(timeout=10)["status"], status)
        batcher.close()
        reopened = self.reopen()
        for account, capacity in capacities.items():
            actual = reopened.account(account)
            self.assertEqual(F(actual["balances"]["USD"]), capacity)
            self.assertEqual(F(actual["open_order_margin"]), model.held(account))
            self.assertEqual(F(reopened.risk(account)["available_margin"]), capacity - model.held(account))
            self.assertFalse(actual["positions"])
        events = reopened.events(limit=1000)
        self.assertEqual(sum(e["event_type"] == "ORDER_ACCEPTED" for e in events), model.accepted)
        self.assertEqual(sum(e["event_type"] == "ORDER_CANCELLED" for e in events), model.cancelled)
        self.assertEqual(reopened.ledger.verify(), len(capacities))

    def test_distinct_batchers_and_synchronous_writer_cannot_duplicate_capacity(self):
        self.fund("contended", "30.12")
        batchers = [self.batcher(self.reopen(), max_batch_size=8, max_delay_ms=5) for _ in range(2)]
        synchronous = self.reopen()
        barrier = Barrier(18)
        def compete(index):
            barrier.wait(timeout=10)
            try:
                if index % 3 == 2:
                    synchronous.submit_order("contended", f"race-{index}", "BTC-PERP", D(1), D(100))
                else:
                    batchers[index % 3].submit_order("contended", f"race-{index}", "BTC-PERP", D(1), D(100)).result(timeout=10)
                return True
            except ServiceError as exc:
                self.assertEqual(exc.code, "insufficient_margin")
                return False
        with ThreadPoolExecutor(max_workers=18) as pool:
            results = list(pool.map(compete, range(18)))
        self.assertEqual(sum(results), 3)
        self.assertEqual(F(self.service.account("contended")["open_order_margin"]), F("30.12"))
        self.assertEqual(F(self.service.risk("contended")["available_margin"]), 0)

    def test_conflicting_retries_and_lost_success_reply_do_not_repeat_reserve(self):
        self.fund("alice", "1000")
        one, two = self.batcher(max_delay_ms=20), self.batcher(self.reopen(), max_delay_ms=20)
        futures = [one.submit_order("alice", "same", "BTC-PERP", D(1), D(100)),
                   two.submit_order("alice", "same", "BTC-PERP", D("1.00"), D("100.0")),
                   one.submit_order("alice", "same", "BTC-PERP", D(2), D(100))]
        self.assertEqual(futures[0].result(timeout=10), futures[1].result(timeout=10))
        self.assert_error(futures[2], "idempotency_conflict")
        # Treat the success response as lost, close both writers, and retry on a
        # new service and worker. IDs are backed by the database, not this queue.
        one.close(); two.close()
        before = self.service.account("alice"), self.service.events(limit=1000)
        restarted = self.batcher(self.reopen())
        self.assertEqual(restarted.submit_order("alice", "same", "BTC-PERP", D(1), D(100)).result(timeout=10)["order_id"], "same")
        self.assertEqual((self.service.account("alice"), self.service.events(limit=1000)), before)

    def test_low_decimal_context_cannot_change_reserve_or_input_limits(self):
        self.fund("alice", "1000")
        batcher = self.batcher(max_delay_ms=5)
        with localcontext() as context:
            context.prec = 1
            context.Emax = 2
            context.Emin = -2
            context.traps[Inexact] = True
            context.traps[Rounded] = True
            future = batcher.submit_order("alice", "precise", "BTC-PERP", D("1.23456789"), D("100.00000001"))
            invalid = batcher.submit_order("alice", "too-large", "BTC-PERP", D("1000000000000.1"), D(100))
        result = future.result(timeout=10)
        self.assertEqual(F(result["reserved_margin"]), reserve("1.23456789", "100.00000001"))
        self.assert_error(invalid, "invalid_input")

    def test_reduce_only_total_quantity_and_reserved_liquidation_ids_are_protected(self):
        self.fund("alice", "1000")
        self.service.submit_order("alice", "open", "BTC-PERP", D(2), D(100))
        self.service.apply_fill("alice", "open", "initial-fill", D(2), D(100))
        batcher = self.batcher(max_delay_ms=15)
        first = batcher.submit_order("alice", "reduce-one", "BTC-PERP", D("-.75"), D(100), reduce_only=True)
        second = batcher.submit_order("alice", "reduce-two", "BTC-PERP", D("-1.25"), D(100), reduce_only=True)
        over = batcher.submit_order("alice", "over-reduce", "BTC-PERP", D("-.01"), D(100), reduce_only=True)
        self.assertEqual(first.result(timeout=10)["status"], "OPEN")
        self.assertEqual(second.result(timeout=10)["status"], "OPEN")
        self.assert_error(over, "reduce_only_violation")
        self.assert_error(batcher.submit_order("alice", "liq:forged", "BTC-PERP", D(-1), D(100), reduce_only=True), "invalid_input")
        self.assert_error(batcher.cancel_order("alice", "liq:forged"), "liquidation_order_protected")
        batcher.cancel_order("alice", "reduce-one").result(timeout=10)
        batcher.submit_order("alice", "replacement", "BTC-PERP", D("-.75"), D(100), reduce_only=True).result(timeout=10)
        # A normal authoritative close invalidates the remaining reduce-only
        # orders. Replaying a terminal ID must not reopen it on the flat book.
        self.service.submit_order("alice", "ordinary-close", "BTC-PERP", D(-2), D(100))
        self.service.apply_fill("alice", "ordinary-close", "closing-fill", D(-2), D(100))
        self.assertEqual(batcher.submit_order("alice", "reduce-two", "BTC-PERP", D("-1.25"), D(100), reduce_only=True).result(timeout=10)["status"], "CANCELLED")
        self.assertEqual(self.service.account("alice")["open_order_margin"], "0")
        self.assertFalse(self.service.account("alice")["positions"])

    def test_configured_cross_catalog_tick_step_and_product_type_cannot_be_bypassed(self):
        path = self.path.with_name("configured.sqlite3")
        service = self.reopen(path=path, configured=True)
        service.publish_market(self.market())
        service.set_kill_switch(False)
        self.fund("alice", "1000", service)
        batcher = self.batcher(service, max_delay_ms=15)
        for identifier, symbol, quantity, price, code in (("spot", "BTC-USD", "1", "100", "unsupported_product"),
                ("unknown", "OPT", "1", "100", "product_rejected"), ("step", "BTC-PERP", ".001", "100", "product_rejected"),
                ("tick", "BTC-PERP", "1", "100.001", "product_rejected")):
            self.assert_error(batcher.submit_order("alice", identifier, symbol, D(quantity), D(price)), code)
        accepted = batcher.submit_order("alice", "valid", "BTC-PERP", D(".01"), D(100)).result(timeout=10)
        self.assertEqual(accepted["order_id"], "valid")
        self.assertEqual(len(service.orders("alice")), 1)
        self.assertEqual(F(service.account("alice")["open_order_margin"]), reserve(".01", "100"))
        self.assertEqual((service.risk("alice")["rule_version"], service.risk("alice")["catalog_version"]), (1, 1))

    def test_business_rejection_and_success_are_not_published_before_outer_commit(self):
        database = CommitGateDatabase(self.path.with_name("commit.sqlite3"))
        service = self.reopen(database=database)
        service.publish_market(self.market())
        service.set_kill_switch(False)
        self.fund("alice", "10.04", service)
        database.enabled = True
        batcher = self.batcher(service, max_batch_size=2, max_delay_ms=50)
        try:
            success = batcher.submit_order("alice", "fits", "BTC-PERP", D(1), D(100))
            rejected = batcher.submit_order("alice", "cannot-fit", "BTC-PERP", D(1), D(100))
            self.assertTrue(database.before_commit.wait(5))
            self.assertFalse(success.done())
            self.assertFalse(rejected.done())
            with closing(sqlite3.connect(database.path)) as observer, observer:
                self.assertEqual(observer.execute("SELECT COUNT(*) FROM uta_orders").fetchone()[0], 0)
        finally:
            database.allow_commit.set()
        self.assertEqual(success.result(timeout=10)["status"], "OPEN")
        self.assert_error(rejected, "insufficient_margin")

    def test_market_error_and_halt_reject_new_risk_but_cancel_still_commits(self):
        self.fund("alice", "1000")
        self.service.submit_order("alice", "old", "BTC-PERP", D(1), D(100))
        batcher = self.batcher(max_delay_ms=20)
        with self.service.database.transaction() as conn:
            future = batcher.submit_order("alice", "queued-before-halt", "BTC-PERP", D(1), D(100))
            conn.execute("UPDATE uta_config SET value='true' WHERE key='halted'")
        self.assert_error(future, "trading_halted")
        self.service.set_kill_switch(False)
        self.now += timedelta(seconds=6)
        stale = batcher.submit_order("alice", "stale", "BTC-PERP", D(1), D(100))
        cancel = batcher.cancel_order("alice", "old")
        self.assert_error(stale, "market_unavailable")
        self.assertEqual(cancel.result(timeout=10)["status"], "CANCELLED")
        self.assertEqual(self.service.account("alice")["open_order_margin"], "0")

    def test_rejection_after_business_writes_releases_only_that_commands_reserve(self):
        self.fund("alice", "20.08")
        original = self.service._event
        def late_rejection(conn, kind, account, payload):
            original(conn, kind, account, payload)
            if kind == "ORDER_ACCEPTED" and payload["order_id"] == "rejected-late":
                raise ServiceError("insufficient_margin", "rejected after attempted writes", 409)
        batcher = self.batcher(max_batch_size=3, max_delay_ms=100)
        with patch.object(self.service, "_event", side_effect=late_rejection):
            first = batcher.submit_order("alice", "first", "BTC-PERP", D(1), D(100))
            rejected = batcher.submit_order("alice", "rejected-late", "BTC-PERP", D(1), D(100))
            second = batcher.submit_order("alice", "second", "BTC-PERP", D(1), D(100))
            self.assertEqual(first.result(timeout=10)["status"], "OPEN")
            self.assert_error(rejected, "insufficient_margin")
            self.assertEqual(second.result(timeout=10)["status"], "OPEN")
        self.assertEqual({row["order_id"] for row in self.service.orders("alice")}, {"first", "second"})
        self.assertEqual(F(self.service.account("alice")["open_order_margin"]), F("20.08"))
        accepted = [e for e in self.service.events(limit=1000) if e["event_type"] == "ORDER_ACCEPTED"]
        self.assertEqual({e["payload"]["order_id"] for e in accepted}, {"first", "second"})
        self.assertEqual(self.service.account("alice")["version"], 3)  # funding + exactly two admissions

    def test_corrupt_persisted_margin_rules_are_technical_not_business_rejection(self):
        service = self.reopen(path=self.path.with_name("corrupt-policy.sqlite3"), configured=True)
        service.publish_market(self.market())
        service.set_kill_switch(False)
        self.fund("alice", "1000", service)
        service.submit_order("alice", "existing", "BTC-PERP", D(1), D(100))
        with service.database.transaction() as conn:
            stored = json.loads(conn.execute("SELECT payload FROM uta_market").fetchone()[0])
            stored["instruments"]["BTC-PERP"]["initial_margin_rate"] = ".2"
            conn.execute("UPDATE uta_market SET payload=?", (json.dumps(stored),))
        def financial_rows():
            with service.database.transaction() as conn:
                return {name: [tuple(row) for row in conn.execute("SELECT * FROM " + name)]
                        for name in ("uta_orders", "uta_accounts", "uta_events", "ledger_events", "ledger_balances")}
        before = financial_rows()
        batcher = self.batcher(service, max_batch_size=2, max_delay_ms=1000)
        cancellation = batcher.cancel_order("alice", "existing")
        new_order = batcher.submit_order("alice", "new", "BTC-PERP", D(1), D(100))
        self.assert_error(cancellation, "admission_batch_failed")
        self.assert_error(new_order, "admission_batch_failed")
        self.assertEqual(financial_rows(), before)
        self.assertEqual(batcher.stats()["business_rejected"], 0)

    def test_unknown_409_after_mutation_is_not_a_declared_business_rejection(self):
        self.fund("alice", "1000")
        original = self.service._event
        def unknown_error(conn, kind, account, payload):
            original(conn, kind, account, payload)
            if kind == "ORDER_ACCEPTED" and payload["order_id"] == "unexpected":
                raise ServiceError("unregistered_policy_guard", "unknown implementation failure", 409)
        before = self.service.account("alice"), self.service.events(limit=1000)
        batcher = self.batcher(max_batch_size=2, max_delay_ms=1000)
        with patch.object(self.service, "_event", side_effect=unknown_error):
            first = batcher.submit_order("alice", "first", "BTC-PERP", D(1), D(100))
            unknown = batcher.submit_order("alice", "unexpected", "BTC-PERP", D(1), D(100))
            self.assert_error(first, "admission_batch_failed")
            self.assert_error(unknown, "admission_batch_failed")
        self.assertEqual((self.service.account("alice"), self.service.events(limit=1000)), before)
        self.assertEqual(batcher.stats()["business_rejected"], 0)

    def test_market_that_expires_during_group_rolls_back_before_publication(self):
        self.fund("alice", "1000")
        self.service.submit_order("alice", "old", "BTC-PERP", D(1), D(100))
        before = self.service.account("alice"), self.service.events(limit=1000)
        original = self.service._cancel_order
        def slow_cancel(conn, account, identifier):
            result = original(conn, account, identifier)
            self.now += timedelta(seconds=6)
            return result
        batcher = self.batcher(max_batch_size=2, max_delay_ms=1000)
        with patch.object(self.service, "_cancel_order", side_effect=slow_cancel):
            new = batcher.submit_order("alice", "new", "BTC-PERP", D(1), D(100))
            cancel = batcher.cancel_order("alice", "old")
            self.assert_error(new, "admission_batch_failed")
            self.assert_error(cancel, "admission_batch_failed")
        self.assertEqual((self.service.account("alice"), self.service.events(limit=1000)), before)
        self.service.publish_market(self.market(2))
        retry = batcher.submit_order("alice", "new", "BTC-PERP", D(1), D(100))
        cancel = batcher.cancel_order("alice", "old")
        self.assertEqual(retry.result(timeout=10)["status"], "OPEN")
        self.assertEqual(cancel.result(timeout=10)["status"], "CANCELLED")
        self.assertEqual(F(self.service.account("alice")["open_order_margin"]), reserve(1, 100))


if __name__ == "__main__":
    unittest.main()
