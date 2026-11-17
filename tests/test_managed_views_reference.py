"""Independent statement/reference checks; expected money is integer arithmetic.

No production risk, reserve, fee, cost-basis or amount-formatting helper generates
an expected value. The synthetic accounts execute real public credit and paired
Matcher operations, then the unbound reader/HTTP server observes their commits.
"""
from contextlib import closing
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D, Inexact, Rounded, ROUND_CEILING, ROUND_FLOOR, localcontext
import fcntl
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from unittest.mock import patch

from uta.credit import CreditService
from uta.durable_commands import QueueStore
from uta.durable_gateway import make_server
from uta.durable_process import DurableProcessRouter
from uta.durable_views import ManagedAccountViews
from uta.gateway import Credential
from uta.ledger import Posting
from uta.market import MarketSnapshot
from uta.matching import Matcher
from uta.models import AssetSpec, InstrumentSpec
from uta.portfolio import BorrowLimits, CollateralRule, CollateralTier, LinearMarginRule, PortfolioRules
from uta.products import ProductCatalog, ProductKind, ProductSpec, TradingStatus
from uta.service import ExchangeService, ServiceError
from uta.storage import Database, DurableLedger
from uta.writer_fence import WriterFence


ALICE, BOB = "statement-owner", "secret-contra-customer"
READER, FUNDING, RISK, TRADER = (letter * 43 for letter in "RFKT")


def integer_units(text, scale):
    """Independent plain-decimal parser, deliberately not Decimal/Fraction."""
    negative = text.startswith("-")
    whole, dot, fraction = text.removeprefix("-").partition(".")
    if not whole.isdigit() or dot and not fraction.isdigit() or len(fraction) > scale:
        raise AssertionError("response is not an exact plain asset-unit amount")
    result = int(whole + fraction.ljust(scale, "0"))
    return -result if negative else result


class ManagedViewReferenceTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.database = Database(self.root / "statement.sqlite3")
        self.now = datetime.now(timezone.utc)
        scales = {"USD": 8, "BTC": 8, "ATOM": 18, "WHOLE": 0}
        source = ExchangeService(self.database, scales, clock=lambda: self.now, decision_audit=True)
        source.publish_market(self.market())
        source.set_kill_switch(False)
        source.create_account(ALICE)
        source.create_account(BOB)
        source.deposit(ALICE, "seed", "USD", D("100.00000003"))
        source.deposit(BOB, "other-secret-seed", "USD", D(500))
        source.deposit(ALICE, "whole-seed", "WHOLE", D(7))
        credit = CreditService(source)
        credit.configure_asset_limit("BTC", D(2))
        credit.configure_limit(ALICE, "BTC", D(1))
        credit.fund_pool("synthetic-capital", "BTC", D(2), source_reference="synthetic:statement-capital")
        credit.borrow(ALICE, "loan", "BTC", D(".1"))
        credit.accrue_interest(ALICE, "interest", "BTC", D(".00000001"))
        credit.repay(ALICE, "repay", "BTC", D(".00000002"))
        matcher = Matcher(source)
        for index, quantity, price in ((1, ".3", "100"), (2, "-.1", "103"), (3, "-.3", "99")):
            source.submit_order(ALICE, f"own-{index}", "X", D(quantity), D(price))
            source.submit_order(BOB, f"private-other-{index}", "X", D(quantity).copy_negate(), D(price))
            result = matcher.match_once("X", max_matches=1)
            self.assertEqual(result["confirmed_trades"], 1)
        # A synthetic stored negative asset balance tests reporting only. This
        # balanced journal is not a withdrawal API or a permission to spend.
        source.ledger.post("synthetic:negative-statement", [
            Posting("customer:" + ALICE, "ATOM", D("-.000000000000000003")),
            Posting("system:synthetic-statement", "ATOM", D(".000000000000000003"))])
        self.queue = QueueStore(self.database, initialize=True)
        self.fence = WriterFence(self.database)
        self.fence.enable("independent-statement-reference")
        self.token = self.fence.acquire("reference-writer", 60)
        self.addCleanup(self.fence.release, self.token)
        self.writer = ExchangeService(self.database.for_writer(self.token), scales,
                                      clock=lambda: self.now, decision_audit=True)
        self.views = ManagedAccountViews(self.database, clock=lambda: self.now)
        self.server = make_server(self.queue, port=0, credentials=(
            Credential(READER, "reader", ALICE), Credential(TRADER, "trader", ALICE),
            Credential(FUNDING, "funding", ALICE), Credential(RISK, "risk")))
        thread = Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01})
        thread.start()
        def shutdown():
            self.server.shutdown()
            self.server.server_close()
            thread.join(3)
        self.addCleanup(shutdown)

    def market(self, version=1):
        assets = {asset: AssetSpec(D(price), D(factor)) for asset, price, factor in (
            ("USD", "1", "1"), ("BTC", "100", ".8"), ("ATOM", "1", "1"), ("WHOLE", "1", "1"))}
        return MarketSnapshot(version, self.now, assets, {"X": InstrumentSpec(D(100), D(".1"), D(".05"))})

    def request(self, suffix="", *, account=ALICE, token=READER):
        connection = HTTPConnection(*self.server.server_address, timeout=3)
        try:
            connection.request("GET", "/v2/accounts/" + account + suffix,
                               headers={"Authorization": "Bearer " + token})
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def error(self, code, function, *args, **kwargs):
        with self.assertRaises(ServiceError) as caught:
            function(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def all_rows(self):
        with self.database.read_transaction() as connection:
            return {name: [tuple(row) for row in connection.execute('SELECT * FROM "' + name + '" ORDER BY rowid')]
                    for name, in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")}

    def drain(self, resource, *, first=None, **options):
        response = first or self.views.read(ALICE, resource, limit=1, **options)
        until, stream = response["page"]["until"], response["snapshot"]["stream_id"]
        rows = []
        while True:
            rows.extend(response[resource])
            if not response["page"]["has_more"]:
                self.assertEqual(response["page"]["next_after"], until)
                return rows
            after = response["page"]["next_after"]
            self.assertLess(after, until)
            response = self.views.read(ALICE, resource, after=after, until=until,
                                       limit=1, stream_id=stream, **options)

    def test_real_partial_close_flip_and_interest_first_repay_have_hand_cash_and_cost(self):
        status, response = self.request()
        self.assertEqual(status, 200, response)
        balances = response["account"]["balances"]
        # 100.00000003 + .1*(103-100) + .2*(99-100)
        # - (.3*100 + .1*103 + .3*99)*.0004 = 100.07200003.
        self.assertEqual(balances["USD"], {"balance": "100.07200003", "scale": 8, "unit": "asset_units"})
        self.assertEqual(integer_units(balances["USD"]["balance"], 8), 10_007_200_003)
        self.assertEqual(balances["ATOM"]["balance"], "-0.000000000000000003")
        self.assertEqual(balances["WHOLE"]["balance"], "7")
        self.assertEqual(balances["BTC"]["balance"], "0.09999998")
        self.assertEqual(response["account"]["liabilities"], [
            {"asset": "BTC", "principal": "0.09999999", "interest": "0", "scale": 8, "unit": "asset_units"}])
        position = self.views.read(ALICE, "positions")["positions"]
        self.assertEqual(len(position), 1)
        self.assertEqual((position[0]["quantity"], position[0]["cost_basis"]), ("-0.1", "-9.9"))
        self.assertEqual((position[0]["quantity_unit"], position[0]["cost_basis_unit"]), ("base_units", "USD"))
        with self.database.read_transaction() as connection:
            units = connection.execute("SELECT units FROM ledger_balances WHERE account=? AND asset='USD'", ("customer:" + ALICE,)).fetchone()[0]
            self.assertEqual(int(units), 10_007_200_003)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_matches").fetchone()[0], 3)
            totals = {}
            for asset, units in connection.execute("SELECT asset,units FROM ledger_balances"):
                totals[asset] = totals.get(asset, 0) + int(units)
            self.assertEqual(totals, {"USD": 0, "BTC": 0, "ATOM": 0, "WHOLE": 0})
        self.assertEqual(response["snapshot"]["risk"]["status"], "unsupported")
        self.assertEqual(self.request("/risk")[0], 501)

    def test_all_money_remains_exact_under_both_hostile_decimal_roundings(self):
        baseline = {resource: self.views.read(ALICE, resource) for resource in ("account", "positions", "orders", "ledger")}
        for rounding in (ROUND_FLOOR, ROUND_CEILING):
            with self.subTest(rounding=rounding), localcontext() as context:
                context.prec, context.rounding = 1, rounding
                context.traps[Inexact] = context.traps[Rounded] = True
                for resource, expected in baseline.items():
                    self.assertEqual(self.views.read(ALICE, resource), expected)

    def test_configured_cross_policy_and_owned_decision_are_read_without_live_risk(self):
        database = Database(self.root / "configured-cross.sqlite3")
        catalog = ProductCatalog(11, {"X": ProductSpec("X", ProductKind.LINEAR_PERPETUAL,
            underlying="BTC", quote_asset="USD", settlement_asset="USD", price_tick=D(".01"),
            quantity_step=D(".01"), min_notional=D(1), status=TradingStatus.ACTIVE)})
        rules = PortfolioRules(13,
            {"USD": CollateralRule("USD", (CollateralTier(None, D(1)),), D(".5")),
             "BTC": CollateralRule("BTC", (CollateralTier(None, D(".8")),), D(".5"))},
            {"BTC": BorrowLimits("BTC", D(1), D(".2"), D(".1"))},
            {"tier-1": LinearMarginRule("tier-1", D(".1"), D(".05"))}, D(100))
        source = ExchangeService(database, {"USD": 8, "BTC": 8}, clock=lambda: self.now,
                                 product_catalog=catalog, portfolio_rules=rules, decision_audit=True)
        source.publish_market(MarketSnapshot(1, self.now,
            {"USD": AssetSpec(D(1), D(1)), "BTC": AssetSpec(D(100), D(".8"))},
            {"X": InstrumentSpec(D(100), D(".1"), D(".05"))}))
        source.create_account(ALICE)
        source.deposit(ALICE, "seed", "USD", D("100.00000003"))
        source.set_kill_switch(False)
        credit = CreditService(source)
        credit.configure_asset_limit("BTC", D(2))
        credit.configure_limit(ALICE, "BTC", D(1))
        credit.fund_pool("cross-synthetic", "BTC", D(2), source_reference="synthetic:cross-capital")
        credit.borrow(ALICE, "cross-loan", "BTC", D(".1"))
        credit.accrue_interest(ALICE, "cross-interest", "BTC", D(".00000001"))
        credit.repay(ALICE, "cross-repay", "BTC", D(".00000002"))
        order = source.submit_order(ALICE, "cross-order", "X", D(".01"), D(100))
        source.apply_fill(ALICE, "cross-order", "cross-fill", D(".01"), D(100))
        QueueStore(database, initialize=True)
        WriterFence(database).enable("cross-statement-reference")
        with patch.object(ExchangeService, "__init__", side_effect=AssertionError("read initialized service")), \
             patch.object(ExchangeService, "risk", side_effect=AssertionError("read recomputed risk")):
            reader = ManagedAccountViews(database, clock=lambda: self.now)
            result = reader.read(ALICE)
            decision = reader.read(ALICE, "decisions", identity=order["decision_id"])["decision"]
        self.assertEqual(result["snapshot"]["policy_ref"]["risk_mode"], "phase1_cross")
        self.assertIsNone(result["snapshot"]["policy_ref"]["archived_policy_id"])
        self.assertEqual(result["snapshot"]["risk"]["status"], "unsupported")
        self.assertEqual(integer_units(result["account"]["balances"]["USD"]["balance"], 8), 9_999_960_003)
        self.assertEqual(result["account"]["liabilities"][0]["principal"], "0.09999999")
        self.assertEqual(decision["policy"]["catalog"]["version"], 11)
        self.assertEqual(decision["policy"]["rules"]["version"], 13)

    def test_paginated_customer_statement_sums_exact_minor_units_and_never_contra(self):
        rows = self.drain("ledger")
        totals = {}
        for event in rows:
            self.assertEqual(event["projection"], "customer_postings_only")
            for posting in event["postings"]:
                self.assertEqual(integer_units(posting["amount"], posting["scale"]), int(posting["units"]))
                totals[posting["asset"]] = totals.get(posting["asset"], 0) + int(posting["units"])
        self.assertEqual(totals, {"USD": 10_007_200_003, "BTC": 9_999_998, "ATOM": -3, "WHOLE": 7})
        self.assertEqual(len({row["cursor"] for row in rows}), len(rows))
        text = json.dumps(rows)
        for private in (BOB, "private-other", "system:", "customer:", "synthetic:statement-capital"):
            self.assertNotIn(private, text)

    def test_private_event_gaps_and_new_global_writes_do_not_skip_or_duplicate(self):
        first = self.views.read(ALICE, "events", limit=1)
        until = first["page"]["until"]
        with self.database.read_transaction() as connection:
            expected = [row[0] for row in connection.execute("SELECT sequence FROM uta_events WHERE account_id=? AND sequence<=? ORDER BY sequence", (ALICE, until))]
        self.writer.deposit(BOB, "secret-other-write", "USD", D(1))
        self.writer.publish_market(self.market(2))
        rows = self.drain("events", first=first)
        self.assertEqual([row["sequence"] for row in rows], expected)
        self.assertTrue(any(second - first > 1 for first, second in zip(expected, expected[1:])))
        self.assertEqual(sum(row["event_type"] == "TRADE_CONFIRMED" for row in rows), 3)
        self.assertTrue(all(row["account_id"] == ALICE for row in rows))
        response = self.views.read(ALICE, "events", after=until, stream_id=first["snapshot"]["stream_id"])
        self.assertEqual(response["events"], [])
        self.assertGreater(response["page"]["next_after"], until)
        self.assertNotIn(BOB, json.dumps(rows))

    def test_order_and_position_reconstruction_detects_account_version_change(self):
        first = self.views.read(ALICE, "orders", limit=1)
        self.writer.submit_order(ALICE, "resting", "X", D(".01"), D(90))
        for resource in ("orders", "positions"):
            self.error("view_version_changed", self.views.read, ALICE, resource,
                       stream_id=first["snapshot"]["stream_id"], at_version=first["snapshot"]["account_version"])
        unchanged_range = self.views.read(ALICE, "events", until=first["snapshot"]["events_watermark"])
        self.assertLess(unchanged_range["page"]["until"], unchanged_range["snapshot"]["events_watermark"])
        rebuilt = self.views.read(ALICE, "orders")
        self.assertEqual({row["order_id"] for row in rebuilt["orders"]}, {"own-1", "own-2", "own-3", "resting"})

    def test_consistent_file_replacement_changes_stream_and_requires_rebuild(self):
        original = self.views.read(ALICE, "events")
        replacement = self.root / "replacement.sqlite3"
        with closing(sqlite3.connect(self.database.path)) as source, closing(sqlite3.connect(replacement)) as destination:
            source.backup(destination)
        os.chmod(replacement, 0o600)
        os.replace(replacement, self.database.path)
        self.error("view_stream_changed", self.views.read, ALICE, "events",
                   stream_id=original["snapshot"]["stream_id"], after=0)
        rebuilt = self.views.read(ALICE, "events")
        self.assertNotEqual(rebuilt["snapshot"]["stream_id"], original["snapshot"]["stream_id"])
        self.assertEqual(rebuilt["events"], original["events"])

    def test_one_wal_snapshot_cannot_mix_a_later_real_partial_fill_into_old_ledger(self):
        self.writer.submit_order(ALICE, "next-partial", "X", D(".02"), D(100))
        original = self.views.read(ALICE, "ledger")
        failures = []
        def fill():
            try:
                self.writer.apply_fill(ALICE, "next-partial", "concurrent-real-fill", D(".01"), D(100))
            except Exception as error:
                failures.append(error)
        outer = self
        class ConcurrentView(ManagedAccountViews):
            def _context(self, connection, account_id):
                result = super()._context(connection, account_id)
                thread = Thread(target=fill)
                thread.start()
                thread.join(3)
                outer.assertFalse(thread.is_alive(), "a WAL snapshot must allow the financial commit")
                return result
        observed = ConcurrentView(self.database, clock=lambda: self.now).read(ALICE, "ledger")
        self.assertEqual(failures, [])
        self.assertEqual(observed, original)
        after = self.views.read(ALICE)
        self.assertEqual(after["snapshot"]["account_version"], original["snapshot"]["account_version"] + 1)
        self.assertEqual(after["snapshot"]["ledger_watermark"], original["snapshot"]["ledger_watermark"] + 1)
        self.assertEqual(integer_units(after["account"]["balances"]["USD"]["balance"], 8), 10_006_160_003)
        position = self.views.read(ALICE, "positions")["positions"][0]
        self.assertEqual((position["quantity"], position["cost_basis"]), ("-0.09", "-8.91"))

    def test_account_scope_precedes_queries_and_owned_decisions_do_not_leak(self):
        with patch.object(self.server.service._producer, "read_view", side_effect=AssertionError("query before authorization")):
            for suffix in ("", "/positions", "/ledger", "/events", "/orders/own-1"):
                self.assertEqual(self.request(suffix, account=BOB)[0], 403)
                self.assertEqual(self.request(suffix, token=FUNDING)[0], 403)
        status, own_order = self.request("/orders/own-1")
        self.assertEqual(status, 200)
        self.assertEqual(self.request("/orders/private-other-1")[0], 404)
        with self.database.read_transaction() as connection:
            other_decision = connection.execute("SELECT decision_id FROM uta_risk_decisions WHERE account_id=? LIMIT 1", (BOB,)).fetchone()[0]
        self.assertEqual(self.request("/decisions/" + other_decision)[0], 404)
        own_decision = own_order["order"]["decision_id"]
        self.assertEqual(self.request("/decisions/" + own_decision)[0], 200)
        for suffix in ("/events", "/ledger", "/positions", "/orders", "/decisions/" + own_decision):
            status, response = self.request(suffix)
            self.assertEqual(status, 200)
            self.assertNotIn(BOB, json.dumps(response))
            self.assertNotIn("private-other", json.dumps(response))
            self.assertNotIn(str(self.root), json.dumps(response))

    def test_every_read_and_denial_is_financially_unchanged_and_never_initializes(self):
        before = self.all_rows()
        with patch.object(ExchangeService, "__init__", side_effect=AssertionError("financial constructor")), \
             patch.object(DurableLedger, "__init__", side_effect=AssertionError("ledger constructor")), \
             patch.object(WriterFence, "acquire", side_effect=AssertionError("reader acquired writer")):
            for suffix in ("", "/orders", "/positions", "/ledger", "/events", "/liquidation", "/orders/absent"):
                self.assertIn(self.request(suffix)[0], (200, 404))
            self.assertEqual(self.request("/risk")[0], 501)
            self.assertEqual(self.request("/events?limit=0")[0], 400)
            self.assertEqual(self.request("/events", account=BOB)[0], 403)
        self.assertEqual(self.all_rows(), before)

    def test_no_quote_empty_or_missing_file_cannot_initialize_financial_state(self):
        for name, make in (("absent.sqlite3", False), ("empty.sqlite3", True)):
            path = self.root / name
            if make:
                path.touch(mode=0o600)
            self.error("view_unavailable", ManagedAccountViews(Database(path)).read, ALICE)
            self.assertEqual(path.exists(), make)
            if make:
                self.assertEqual(path.stat().st_size, 0)
            self.assertFalse(Path(str(path) + "-wal").exists())
            self.assertFalse(Path(str(path) + "-shm").exists())

    def test_missing_current_quote_is_explicit_and_cannot_be_replaced_with_old_archive(self):
        with self.writer.database.transaction() as connection:
            connection.execute("DELETE FROM uta_market WHERE singleton=1")
        result = self.views.read(ALICE)
        self.assertEqual(result["snapshot"]["market"]["freshness"], "missing")
        self.assertIsNone(result["snapshot"]["market_snapshot_id"])
        self.assertIsNone(result["snapshot"]["market"]["version"])
        self.assertEqual(result["snapshot"]["risk"]["status"], "unsupported")
        self.assertEqual(integer_units(result["account"]["balances"]["USD"]["balance"], 8), 10_007_200_003)

    def test_nonstandard_stored_decimal_strings_fail_closed_instead_of_python_extensions(self):
        for table, field, original, resource in (("uta_liabilities", "principal", "0.09999999", "account"),
                                                  ("uta_liabilities", "interest", "0", "account"),
                                                  ("uta_positions", "cost_basis", "-9.9", "positions")):
            for value in ("1_0", " 1 ", "١"):
                with self.subTest(table=table, field=field, value=value):
                    with self.writer.database.transaction() as connection:
                        connection.execute(f"UPDATE {table} SET {field}=? WHERE account_id=?", (value, ALICE))
                    try:
                        self.error("view_data_invalid", self.views.read, ALICE, resource)
                    finally:
                        with self.writer.database.transaction() as connection:
                            connection.execute(f"UPDATE {table} SET {field}=? WHERE account_id=?", (original, ALICE))

    def test_liability_scale_is_exact_and_redundant_decimal_zeros_are_valid(self):
        for field, original in (("principal", "0.09999999"), ("interest", "0")):
            for value in ("0.000000001", "1E-9"):
                with self.subTest(field=field, value=value):
                    with self.writer.database.transaction() as connection:
                        connection.execute(f"UPDATE uta_liabilities SET {field}=? WHERE account_id=?", (value, ALICE))
                    try:
                        self.error("view_data_invalid", self.views.read, ALICE)
                    finally:
                        with self.writer.database.transaction() as connection:
                            connection.execute(f"UPDATE uta_liabilities SET {field}=? WHERE account_id=?", (original, ALICE))
        with self.writer.database.transaction() as connection:
            connection.execute("UPDATE uta_liabilities SET principal='1.0E-8' WHERE account_id=?", (ALICE,))
        self.assertEqual(self.views.read(ALICE)["account"]["liabilities"][0]["principal"], "1.0E-8")

    def test_json_exponent_overflow_is_invalid_data_not_a_nonfinite_response_or_500(self):
        for value in ("1e999", "-1e999"):
            with self.subTest(value=value):
                with self.writer.database.transaction() as connection:
                    cursor = connection.execute("INSERT INTO uta_events(event_type,account_id,payload,created_at) VALUES (?,?,?,?)",
                        ("SYNTHETIC_BAD_NUMBER", ALICE, '{"amount":' + value + '}', self.now.isoformat())).lastrowid
                before = self.all_rows()
                self.error("view_data_invalid", self.views.read, ALICE, "events", after=cursor - 1)
                status, response = self.request("/events?after=" + str(cursor - 1))
                self.assertEqual(status, 503, response)
                self.assertEqual(response["error"]["code"], "view_data_invalid")
                self.assertEqual(self.all_rows(), before)

    def test_existing_delete_journal_authority_bytes_are_not_rewritten_by_a_view(self):
        with closing(sqlite3.connect(self.database.path)) as connection:
            self.assertEqual(connection.execute("PRAGMA journal_mode=DELETE").fetchone()[0], "delete")
        original = Path(self.database.path).read_bytes()
        result = self.views.read(ALICE)
        self.assertEqual(integer_units(result["account"]["balances"]["USD"]["balance"], 8), 10_007_200_003)
        self.assertEqual(Path(self.database.path).read_bytes(), original)
        self.assertFalse(Path(self.database.path + "-wal").exists())
        self.assertFalse(Path(self.database.path + "-shm").exists())

    def test_market_age_boundaries_preserve_original_observation_and_never_claim_ready(self):
        for seconds, expected in ((-2, "future"), (-1, "fresh_as_of_read"), (5, "fresh_as_of_read"), (5.000001, "stale")):
            response = ManagedAccountViews(self.database, clock=lambda: self.now + timedelta(seconds=seconds)).read(ALICE)
            self.assertEqual(response["snapshot"]["market"]["freshness"], expected)
            self.assertEqual(response["snapshot"]["market"]["observed_at"], self.now.isoformat())
            self.assertEqual(response["snapshot"]["risk"]["status"], "unsupported")
            for unsupported in ("ready", "financial_ready", "trading_ready", "equity", "available_margin"):
                self.assertNotIn(unsupported, response["snapshot"])

    def test_same_pid_reader_preserves_actual_kernel_file_lock_of_open_snapshot(self):
        program = ("import fcntl,os,sys\nfd=os.open(sys.argv[1],os.O_RDWR)\n"
                   "try: fcntl.lockf(fd,fcntl.LOCK_EX|fcntl.LOCK_NB,1,4096,os.SEEK_SET)\n"
                   "except BlockingIOError: sys.exit(7)\n")
        def observed_lock():
            return subprocess.run([sys.executable, "-c", program, self.database.path],
                                  capture_output=True, timeout=3, check=False).returncode
        with self.database.read_transaction() as connection:
            connection.execute("SELECT COUNT(*) FROM uta_accounts").fetchone()
            descriptor = os.open(self.database.path, os.O_RDWR)
            try:
                fcntl.lockf(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB, 1, 4096, os.SEEK_SET)
                self.assertEqual(observed_lock(), 7)
                self.views.read(ALICE)
                self.assertEqual(observed_lock(), 7, "reader raw-close dropped this PID's kernel lock")
            finally:
                os.close(descriptor)


class ManagedRouterReadReferenceTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.phase_evidence = []
        self.accounts = []
        def bootstrap(router):
            for shard in range(2):
                name = next(f"read-owner-{index}" for index in range(100) if router.shard_for(f"read-owner-{index}") == shard)
                self.accounts.append(name)
                router.create_account(name)
                router.deposit(name, "synthetic-bootstrap", "USD", D(100))
        self.router = DurableProcessRouter.initialize(self.root / "router", 2, {"USD": 8}, managed=True,
            bootstrap=bootstrap, max_price_age=timedelta(seconds=2), lease_seconds=3,
            poll_interval=.01, background_interval=.03)
        self.addCleanup(self.router.close)
        self.server = make_server(self.router, port=0, credentials=(Credential(RISK, "risk"),
            Credential(READER, "reader", self.accounts[0])))
        thread = Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01})
        thread.start()
        def shutdown():
            self.server.shutdown()
            self.server.server_close()
            thread.join(3)
        self.addCleanup(shutdown)

    def market(self, version=1):
        return MarketSnapshot(version, datetime.now(timezone.utc), {"USD": AssetSpec(D(1), D(1))},
                              {"X": InstrumentSpec(D(100), D(".1"), D(".05"))})

    def get(self, path, token=RISK):
        connection = HTTPConnection(*self.server.server_address, timeout=4)
        try:
            connection.request("GET", path, headers={"Authorization": "Bearer " + token})
            response = connection.getresponse()
            data = json.loads(response.read())
            self.assertEqual(response.status, 200, data)
            return data
        finally:
            connection.close()

    def record_phase(self, phase, **observations):
        shards = []
        for index in range(2):
            with self.router._database(index).read_transaction() as connection:
                market = connection.execute("SELECT payload FROM uta_market WHERE singleton=1").fetchone()
                commands = [dict(row) for row in connection.execute(
                    "SELECT command_id,state,result,error FROM uta_command_inbox "
                    "WHERE kind='PUBLISH_MARKET' ORDER BY sequence")]
            shards.append({"shard": index, "market_payload": None if market is None else market[0],
                           "publication_commands": commands})
        row = {"phase": phase, "observed_utc": datetime.now(timezone.utc).isoformat(),
               "control": self.router._control._state(), "shards": shards, **observations}
        self.phase_evidence.append(row)
        output = os.environ.get("UTA_READVIEW_PHASE_EVIDENCE")
        if output:
            target = Path(output) / self._testMethodName
            target.mkdir(parents=True, exist_ok=True)
            (target / (str(len(self.phase_evidence)) + "-" + phase + ".json")).write_text(
                json.dumps(row, sort_keys=True, indent=2) + "\n")
        return row

    def await_owner_ready(self, shard, timeout=2):
        """Prepare a real owner before stamping the test's first market tick."""
        from time import monotonic, sleep
        deadline = monotonic() + timeout
        last = None
        while monotonic() < deadline:
            last = self.get("/v2/worker-health")
            worker = next(row for row in last["workers"] if row["shard"] == shard)
            if worker.get("owner_ready") is True and monotonic() < deadline:
                self.assertTrue(worker["alive"] and worker["lease_active"], last)
                self.assertEqual(worker["pid"], worker["owner_pid"], last)
                self.assertNotEqual(worker["pid"], os.getpid(), last)
                self.record_phase("owner-ready-before-market", health=last)
                return last
            sleep(.02)
        observed = self.record_phase("owner-ready-deadline", health=last)
        self.fail("real owner did not become ready within the fixture budget: " + json.dumps(observed, sort_keys=True))

    def await_local_publication(self, publication, snapshot, *, shard=0, timeout=1):
        """Query the original CID; partial fanout is not a local COMMIT ACK."""
        from hashlib import sha256
        command_id = publication["durable_market_commands"][str(shard)]
        receipt = self.router.wait(command_id, shard=shard, timeout=timeout)
        if receipt is None or receipt["state"] != "SUCCEEDED":
            observed = self.record_phase("local-publication-deadline", publication=publication,
                                         original_command_id=command_id, receipt=receipt)
            self.fail("original publication did not commit within the fixture budget: " + json.dumps(observed, sort_keys=True))
        self.assertEqual(receipt["command_id"], command_id)
        self.assertEqual(receipt["kind"], "PUBLISH_MARKET")
        account = self.get("/v2/accounts/" + self.accounts[shard], token=READER)
        observed = self.record_phase("local-publication-committed", publication=publication,
                                     original_command_id=command_id, receipt=receipt, account=account)
        expected_digest = sha256(snapshot.to_json().encode()).hexdigest()
        basis = account["snapshot"]
        self.assertEqual(basis["market"]["freshness"], "fresh_as_of_read", observed)
        self.assertEqual(basis["market"]["version"], snapshot.version, observed)
        self.assertEqual(basis["market"]["observed_at"], snapshot.observed_at.isoformat(), observed)
        self.assertEqual(basis["market"]["payload_digest"], expected_digest, observed)
        self.assertEqual(basis["market_snapshot_id"], "market:" + expected_digest, observed)
        self.assertEqual(observed["shards"][shard]["market_payload"], snapshot.to_json(), observed)
        return account

    def activate(self, snapshot):
        self.assertFalse(self.router.publish_market(snapshot, timeout=8)["publishing"])
        self.assertFalse(self.router.set_kill_switch(False, timeout=8)["halted"])
        from time import monotonic, sleep
        deadline = monotonic() + 5
        while monotonic() < deadline:
            health = self.get("/v2/worker-health")
            if health["financial_ready"]:
                return health
            sleep(.02)
        self.fail("real child handshakes did not become financially ready")

    def test_real_partial_fanout_stale_and_recovery_remain_explicit_through_http(self):
        fence = WriterFence(self.router._database(1))
        token = fence.acquire("independent:hold-shard", 5)
        try:
            self.router.start()
            self.await_owner_ready(0)
            snapshot = self.market()
            publication = self.router.publish_market(snapshot, timeout=.25)
            self.assertTrue(publication["publishing"])
            health = self.get("/v2/worker-health")
            self.assertFalse(health["financial_ready"])
            self.assertFalse(health["dispatch_available"])
            self.assertTrue(health["control"]["publishing"])
            observed = self.await_local_publication(publication, snapshot)
            pending = self.router.status(publication["durable_market_commands"]["1"], shard=1)
            self.assertEqual(pending["state"], "PENDING", pending)
            self.assertTrue(self.router._control._state()["halted"])
            self.assertTrue(self.router._control._state()["publishing"])
            self.assertEqual(observed["snapshot"]["market"]["freshness"], "fresh_as_of_read")
            self.assertTrue(observed["snapshot"]["local_halt_observed"])
            self.assertEqual(observed["snapshot"]["risk"]["status"], "unsupported")
            self.assertNotIn("financial_ready", observed["snapshot"])
        finally:
            fence.release(token)
        self.assertTrue(self.activate(snapshot)["financial_ready"])
        from time import sleep
        wait = (snapshot.observed_at + timedelta(seconds=2) - datetime.now(timezone.utc)).total_seconds()
        sleep(max(0, wait) + .04)
        health = self.get("/v2/worker-health")
        self.assertTrue(health["workers_alive"])
        self.assertFalse(health["financial_ready"])
        self.assertFalse(health["ready"])
        observed = self.get("/v2/accounts/" + self.accounts[0], token=READER)
        self.assertEqual(observed["snapshot"]["market"]["freshness"], "stale")
        self.assertEqual(observed["snapshot"]["risk"]["status"], "unsupported")
        self.assertTrue(self.activate(self.market(2))["financial_ready"])
        self.assertEqual(self.get("/v2/accounts/" + self.accounts[0], token=READER)["snapshot"]["market"]["version"], 2)

    def test_pending_partial_publication_does_not_claim_a_local_market_commit(self):
        held = {}
        try:
            for shard in range(2):
                fence = WriterFence(self.router._database(shard))
                held[shard] = (fence, fence.acquire("independent:phase-hold-" + str(shard), 5))
            self.router.start()
            snapshot = self.market()
            publication = self.router.publish_market(snapshot, timeout=.25)
            health = self.get("/v2/worker-health")
            account = self.get("/v2/accounts/" + self.accounts[0], token=READER)
            phase = self.record_phase("partial-before-local-owner", publication=publication,
                                      health=health, account=account)
            self.assertTrue(publication["publishing"], phase)
            self.assertEqual(publication["watermarks"], {}, phase)
            self.assertTrue(all(row["state"] == "PENDING" for row in publication["receipts"].values()), phase)
            self.assertFalse(health["financial_ready"], phase)
            self.assertEqual(account["snapshot"]["market"]["freshness"], "missing", phase)
            self.assertIsNone(phase["shards"][0]["market_payload"], phase)
            fence, token = held.pop(0)
            fence.release(token)
            self.await_local_publication(publication, snapshot)
            resumed = self.router.publish_market(snapshot, timeout=.05)
            self.assertEqual(resumed["durable_market_commands"], publication["durable_market_commands"])
            self.assertEqual(resumed["receipts"]["0"]["state"], "SUCCEEDED", resumed)
            self.assertEqual(resumed["receipts"]["1"]["state"], "PENDING", resumed)
            self.assertEqual(resumed["watermarks"], {"0": snapshot.version}, resumed)
            self.assertTrue(resumed["halted"] and resumed["publishing"], resumed)
            self.record_phase("same-original-publication-still-partial", publication=resumed)
        finally:
            for fence, token in held.values():
                fence.release(token)
        # Complete the same publication; never retimestamp or replace the tick
        # to manufacture success after waiting for a pending original command.
        self.assertTrue(self.activate(snapshot)["financial_ready"])

    def test_actual_control_gate_timeout_returns_unknown_control_over_http(self):
        self.router.start()
        self.activate(self.market())
        with self.router._control._lock(exclusive=True):
            result = self.get("/v2/worker-health")
        self.assertIsNone(result["control"])
        self.assertFalse(result["control_observed"])
        self.assertFalse(result["financial_ready"])
        self.assertFalse(result["dispatch_available"])
        self.assertEqual(result["reason"], "diagnostic_timeout")
        self.assertNotIn(str(self.root), json.dumps(result))


if __name__ == "__main__":
    unittest.main()
