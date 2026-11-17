"""Managed read snapshots, scoped pages and real authenticated HTTP."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D, Inexact, Rounded, localcontext
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import secrets
import shutil
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from unittest.mock import patch

from uta.credit import CreditService
from uta.durable_commands import QueueStore
from uta.durable_gateway import make_server, producer_binding
from uta.durable_process import DurableProcessRouter
from uta.durable_views import ManagedAccountViews
from uta.gateway import Credential
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.request_signing import NonceStore, RequestAuthenticator, SigningKey, SigningProfile, sign_headers
from uta.service import ExchangeService, ServiceError
from uta.storage import Database, DurableLedger
from uta.writer_fence import WriterFence


ADMIN, RISK, READER, TRADER, OTHER, FUNDING = (letter * 43 for letter in "AKRTBF")


class DurableViewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.database = Database(self.root / "financial.sqlite3")
        self.now = datetime.now(timezone.utc)
        bootstrap = ExchangeService(self.database, {"USD": 8, "BTC": 8}, clock=lambda: self.now, decision_audit=True)
        bootstrap.publish_market(self.market())
        bootstrap.set_kill_switch(False)
        for account, funds in (("alice", "1000"), ("bob", "777")):
            bootstrap.create_account(account)
            bootstrap.deposit(account, "fund", "USD", D(funds))
        self.order = bootstrap.submit_order("alice", "one", "X", D(1), D(100))
        bootstrap.submit_order("bob", "bob-one", "X", D(1), D(100))
        bootstrap.apply_fill("alice", "one", "fill", D(".5"), D(100))
        bootstrap.supervise_account("alice")
        self.queue = QueueStore(self.database, initialize=True)
        self.fence = WriterFence(self.database)
        self.fence.enable("view-fixture")
        self.token = self.fence.acquire("view-writer", 30)
        self.addCleanup(self.fence.release, self.token)
        self.writer = ExchangeService(self.database.for_writer(self.token), {"USD": 8, "BTC": 8},
                                      clock=lambda: self.now, decision_audit=True)
        self.views = ManagedAccountViews(self.database, clock=lambda: self.now)
        self.server, self.thread = self.start_server(self.queue)

    def market(self, version=1):
        return MarketSnapshot(version, self.now, {"USD": AssetSpec(D(1), D(1)), "BTC": AssetSpec(D(100), D(".8"))},
                              {"X": InstrumentSpec(D(100), D(".1"), D(".05"))})

    def start_server(self, producer, **options):
        default = {"credentials": (Credential(ADMIN, "admin"), Credential(RISK, "risk"),
            Credential(READER, "reader", "alice"), Credential(TRADER, "trader", "alice"),
            Credential(OTHER, "trader", "bob"), Credential(FUNDING, "funding", "alice"))}
        server = make_server(producer, port=0, **({**default, **options} if "auth_profile" not in options else options))
        thread = Thread(target=server.serve_forever, kwargs={"poll_interval": .01})
        thread.start()
        def close():
            server.shutdown(); server.server_close(); thread.join(3)
        self.addCleanup(close)
        return server, thread

    def request(self, path, *, method="GET", payload=None, token=READER, server=None, raw_body=None, headers=None):
        connection = HTTPConnection(*(server or self.server).server_address, timeout=3)
        try:
            options = {"Authorization": "Bearer " + token} if token is not None else {}
            options.update(headers or {})
            body = raw_body
            if payload is not None:
                body = json.dumps(payload).encode()
            if body is not None:
                options["Content-Type"] = "application/json"
            connection.request(method, path, body, options)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def expect(self, status, path, **options):
        actual, result = self.request(path, **options)
        self.assertEqual(actual, status, result)
        return result

    def financial(self):
        with self.database.read_transaction() as connection:
            tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
            return {table: [tuple(row) for row in connection.execute('SELECT * FROM "' + table + '" ORDER BY rowid')] for table in tables}

    def test_all_read_resources_are_consistent_exact_and_never_initialize_financial_services(self):
        before = self.financial()
        with patch.object(ExchangeService, "__init__", side_effect=AssertionError("no financial constructor")), \
             patch.object(DurableLedger, "__init__", side_effect=AssertionError("no ledger constructor")):
            for path in ("", "/orders", "/orders/one", "/positions", "/ledger", "/events", "/liquidation",
                         "/decisions/" + self.order["decision_id"]):
                result = self.expect(200, "/v2/accounts/alice" + path)
                basis = result["snapshot"]
                self.assertEqual(basis["account_id"], "alice")
                self.assertEqual(basis["market_snapshot_id"], "market:" + __import__("hashlib").sha256(self.market().to_json().encode()).hexdigest())
                self.assertTrue(basis["policy_ref"]["id"].startswith("config:"))
                self.assertIsNone(basis["policy_ref"]["archived_policy_id"])
                self.assertEqual(basis["risk"]["status"], "unsupported")
        self.assertEqual(self.financial(), before)
        with localcontext() as context:
            context.prec = 1
            context.traps[Inexact] = context.traps[Rounded] = True
            account = self.views.read("alice")["account"]
        self.assertEqual(account["balances"]["USD"], {"balance": "999.98", "scale": 8, "unit": "asset_units"})
        position = self.views.read("alice", "positions")["positions"][0]
        self.assertEqual((position["quantity"], position["cost_basis"], position["cost_basis_unit"]), ("0.5", "50", "USD"))
        self.assertIsNone(self.views.read("alice", "orders")["orders"][0]["reserved_margin"])
        self.expect(501, "/v2/accounts/alice/risk")

    def test_writer_commit_between_metadata_and_rows_cannot_split_a_view_snapshot(self):
        old = self.views.read("alice")
        writer_errors = []
        def write():
            try:
                self.writer.deposit("alice", "concurrent", "USD", D(1))
                self.writer.publish_market(self.market(2))
            except Exception as error:
                writer_errors.append(error)
        class PausedView(ManagedAccountViews):
            def _context(inner, connection, account_id):
                result = super()._context(connection, account_id)
                worker = Thread(target=write)
                worker.start(); worker.join(3)
                self.assertFalse(worker.is_alive(), "WAL reader must not block the independent writer")
                return result
        observed = PausedView(self.database, clock=lambda: self.now).read("alice")
        self.assertEqual(writer_errors, [])
        for key in ("account_version", "events_watermark", "market_snapshot_id", "policy_ref"):
            self.assertEqual(observed["snapshot"][key], old["snapshot"][key])
        self.assertEqual(observed["account"], old["account"])
        fresh = self.views.read("alice")
        self.assertEqual(fresh["snapshot"]["account_version"], old["snapshot"]["account_version"] + 1)
        self.assertEqual(fresh["account"]["balances"]["USD"]["balance"], "1000.98")
        self.assertNotEqual(fresh["snapshot"]["market_snapshot_id"], old["snapshot"]["market_snapshot_id"])

    def test_event_pages_filter_before_limit_preserve_gaps_and_resume_at_the_watermark(self):
        first = self.views.read("alice", "events", limit=1)
        stream, until = first["snapshot"]["stream_id"], first["page"]["until"]
        items, response = [], first
        while True:
            items += response["events"]
            if not response["page"]["has_more"]:
                break
            response = self.views.read("alice", "events", after=response["page"]["next_after"],
                                       until=until, limit=1, stream_id=stream)
        sequences = [item["sequence"] for item in items]
        with self.database.read_transaction() as connection:
            expected = [row[0] for row in connection.execute("SELECT sequence FROM uta_events WHERE account_id='alice' AND sequence<=? ORDER BY sequence", (until,))]
        self.assertEqual(sequences, expected)
        self.assertEqual(len(sequences), len(set(sequences)))
        self.assertTrue(any(b - a > 1 for a, b in zip(sequences, sequences[1:])))
        self.assertTrue(all(item["account_id"] == "alice" for item in items))
        self.assertEqual(response["page"]["next_after"], until)
        self.writer.deposit("alice", "after-page", "USD", D(1))
        new = self.views.read("alice", "events", after=until, stream_id=stream)
        self.assertEqual(len(new["events"]), 1)
        self.assertGreater(new["events"][0]["sequence"], until)

    def test_ledger_only_exposes_the_requested_customers_postings(self):
        result = self.expect(200, "/v2/accounts/alice/ledger?limit=1")
        rows = []
        until = result["page"]["until"]
        while True:
            rows += result["ledger"]
            if not result["page"]["has_more"]:
                break
            result = self.views.read("alice", "ledger", after=result["page"]["next_after"], until=until, limit=1)
        self.assertEqual(sum(D(post["amount"]) for row in rows for post in row["postings"] if post["asset"] == "USD"), D("999.98"))
        self.assertNotIn("customer:bob", json.dumps(rows))
        self.assertNotIn("system:", json.dumps(rows))
        self.assertTrue(all(row["projection"] == "customer_postings_only" for row in rows))

    def test_stream_and_account_version_mismatch_require_rebuild_not_cursor_reset(self):
        initial = self.views.read("alice", "orders", limit=1)
        version, stream = initial["snapshot"]["account_version"], initial["snapshot"]["stream_id"]
        self.writer.submit_order("alice", "new", "X", D(".1"), D(100))
        with self.assertRaises(ServiceError) as error:
            self.views.read("alice", "orders", at_version=version)
        self.assertEqual(error.exception.code, "view_version_changed")
        self.expect(409, "/v2/accounts/alice/events?after=9223372036854775807")
        self.expect(409, "/v2/accounts/alice/events?stream_id=account-stream:" + "0" * 64)
        replacement = self.root / "replacement.sqlite3"
        shutil.copy2(self.database.path, replacement)
        os.replace(replacement, self.database.path)
        with self.assertRaises(ServiceError) as changed:
            self.views.read("alice", "events", stream_id=stream)
        self.assertEqual(changed.exception.code, "view_stream_changed")

    def test_historical_decision_keeps_its_own_market_and_policy_after_current_market_changes(self):
        original = self.views.read("alice", "decisions", identity=self.order["decision_id"])
        self.writer.publish_market(self.market(2))
        result = self.expect(200, "/v2/accounts/alice/decisions/" + self.order["decision_id"])
        self.assertNotEqual(result["snapshot"]["market_snapshot_id"], result["decision"]["market_snapshot_id"])
        self.assertEqual(result["decision"], original["decision"])
        self.assertEqual(result["decision"]["pre_version"], result["decision"]["inputs"]["before"]["version"])
        self.assertFalse(result["decision"]["artifact"]["signed"])
        with self.database.read_transaction() as connection:
            other = connection.execute("SELECT decision_id FROM uta_risk_decisions WHERE account_id='bob' LIMIT 1").fetchone()[0]
        self.expect(404, "/v2/accounts/alice/decisions/" + other)

    def test_stale_future_and_unevaluated_states_do_not_claim_risk_readiness(self):
        stale = ManagedAccountViews(self.database, clock=lambda: self.now + timedelta(seconds=6)).read("alice")
        future = ManagedAccountViews(self.database, clock=lambda: self.now - timedelta(seconds=2)).read("alice")
        self.assertEqual(stale["snapshot"]["market"]["freshness"], "stale")
        self.assertEqual(future["snapshot"]["market"]["freshness"], "future")
        self.assertEqual(stale["snapshot"]["risk"]["status"], "unsupported")
        self.assertNotIn("trading_ready", stale["snapshot"])
        state = self.views.read("bob", "liquidation")["liquidation"]
        self.assertEqual((state["status"], state["stored_state"]), ("not_evaluated", None))

    def test_roles_are_checked_before_any_view_query_and_command_receipts_stay_compatible(self):
        with patch.object(self.server.service._producer, "read_view", side_effect=AssertionError("scope checked too late")):
            self.expect(401, "/v2/accounts/alice", token=None)
            self.expect(403, "/v2/accounts/bob", token=READER)
            self.expect(403, "/v2/accounts/alice", token=FUNDING)
        self.expect(200, "/v2/accounts/bob", token=RISK)
        self.expect(200, "/v2/accounts/bob", token=ADMIN)
        queued = self.expect(202, "/v2/accounts/alice/orders", method="POST", token=TRADER,
            payload={"command_id": "pending", "order_id": "pending", "symbol": "X", "quantity": "1", "limit_price": "100"})
        self.assertEqual(self.expect(202, queued["status_url"], token=TRADER), queued)
        self.assertEqual(self.expect(200, "/v2/accounts/alice/orders/one")["order"]["order_id"], "one")
        for query in ("limit=201", "limit=0", "after=-1", "limit=1&limit=2", "unknown=1", "at_version=true", "until=0&after=1"):
            self.expect(400, "/v2/accounts/alice/events?" + query)
        self.expect(400, "/v2/accounts/alice?limit=1")
        self.expect(400, "/v2/accounts/alice/commands/pending?after=0", token=TRADER)

    def test_hmac_authenticated_reader_gets_only_its_own_view_without_financial_writes(self):
        store = NonceStore.initialize(self.root / "auth.sqlite3", tenant_id="views", producer_binding=producer_binding(self.queue))
        epoch = int(self.now.timestamp() * 1000)
        profile = SigningProfile("views", store.audience, 1, (SigningKey("reader", b"synthetic-read-view-secret-32bytes!", "reader", "alice", epoch - 1000, epoch + 60000),))
        auth = RequestAuthenticator(store, profile, clock_ms=lambda: epoch)
        signed, _ = self.start_server(self.queue, auth_profile="hmac", authenticator=auth, require_tls=False)
        before = self.financial()
        for path, expected in (("/v2/accounts/alice/events?limit=1", 200), ("/v2/accounts/bob/events", 403)):
            headers = sign_headers(profile, "reader", timestamp_ms=epoch, nonce=secrets.token_urlsafe(24), method="GET", request_target=path)
            self.expect(expected, path, token=None, server=signed, headers=headers)
        self.assertEqual(self.financial(), before)

    def test_missing_file_or_audit_guard_is_not_created_or_repaired(self):
        missing = self.root / "missing.sqlite3"
        with self.assertRaises(ServiceError) as error:
            ManagedAccountViews(Database(missing)).read("alice")
        self.assertEqual(error.exception.status, 503)
        self.assertFalse(missing.exists())
        with self.writer.database.transaction() as connection:
            connection.execute("DROP TRIGGER audit_order_requires_decision")
        self.expect(503, "/v2/accounts/alice")
        with self.database.read_transaction() as connection:
            self.assertIsNone(connection.execute("SELECT name FROM sqlite_master WHERE name='audit_order_requires_decision'").fetchone())

    def test_read_preflight_never_raw_opens_or_closes_a_financial_inode(self):
        before = self.financial()
        with patch("uta.durable_views.os.open", side_effect=AssertionError("raw inode open forbidden")), \
             patch("uta.durable_views.os.close", side_effect=AssertionError("raw inode close forbidden")), \
             patch("uta.durable_views.os.fstat", side_effect=AssertionError("raw fd validation forbidden")):
            result = self.views.read("alice")
        self.assertEqual(result["account"]["balances"]["USD"]["balance"], "999.98")
        self.assertEqual(self.financial(), before)
        empty = self.root / "empty.sqlite3"
        empty.touch(mode=0o600)
        with self.assertRaises(ServiceError) as error:
            ManagedAccountViews(Database(empty)).read("alice")
        self.assertEqual(error.exception.status, 503)
        self.assertEqual(empty.stat().st_size, 0)
        self.assertFalse(Path(str(empty) + "-wal").exists())
        self.assertFalse(Path(str(empty) + "-shm").exists())

    def test_legacy_evidence_is_an_explicit_gap_and_never_backfilled_by_a_read(self):
        database = Database(self.root / "legacy.sqlite3")
        legacy = ExchangeService(database, {"USD": 8}, clock=lambda: self.now)
        legacy.create_account("legacy")
        legacy.publish_market(self.market())
        WriterFence(database).enable("legacy-view")
        view = ManagedAccountViews(database, clock=lambda: self.now)
        result = view.read("legacy")
        self.assertIsNone(result["snapshot"]["market_snapshot_id"])
        self.assertEqual(result["snapshot"]["market"]["evidence"], "legacy_unarchived")
        with self.assertRaises(ServiceError) as unavailable:
            view.read("legacy", "decisions", identity="decision:" + "0" * 64)
        self.assertEqual(unavailable.exception.status, 501)
        with database.read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT version FROM uta_schema").fetchone()[0], 2)
            self.assertIsNone(connection.execute("SELECT name FROM sqlite_master WHERE name='uta_market_history'").fetchone())

    def test_asset_balances_and_gross_principal_interest_are_not_netted_or_priced(self):
        database = Database(self.root / "loan-view.sqlite3")
        source = ExchangeService(database, {"USD": 8, "BTC": 8}, clock=lambda: self.now, decision_audit=True)
        source.create_account("alice")
        source.deposit("alice", "collateral", "USD", D(1000))
        source.publish_market(self.market())
        source.set_kill_switch(False)
        credit = CreditService(source)
        credit.configure_asset_limit("BTC", D(10))
        credit.configure_limit("alice", "BTC", D(5))
        credit.fund_pool("capital", "BTC", D(10), source_reference="synthetic:capital")
        credit.borrow("alice", "loan", "BTC", D(1))
        credit.accrue_interest("alice", "interest", "BTC", D(".01"))
        QueueStore(database, initialize=True)
        WriterFence(database).enable("loan-view")
        result = ManagedAccountViews(database, clock=lambda: self.now).read("alice")
        self.assertEqual(result["account"]["balances"]["BTC"]["balance"], "1")
        self.assertEqual(result["account"]["liabilities"], [{"asset": "BTC", "principal": "1", "interest": "0.01", "scale": 8, "unit": "asset_units"}])
        self.assertEqual(result["snapshot"]["risk"]["status"], "unsupported")
        self.assertNotIn("equity", result["account"])

    def test_nonstandard_monetary_strings_fail_closed_over_http_without_repair(self):
        with self.writer.database.transaction() as connection:
            connection.execute("INSERT INTO uta_liabilities VALUES ('alice','BTC','1','0')")
        fields = (("uta_liabilities", "principal", "account", ""),
                  ("uta_liabilities", "interest", "account", ""),
                  ("uta_positions", "cost_basis", "positions", "/positions"),
                  ("uta_orders", "limit_price", "orders", "/orders/one"))
        for table, field, resource, suffix in fields:
            with self.writer.database.read_transaction() as connection:
                original = connection.execute(f"SELECT {field} FROM {table} WHERE account_id='alice'").fetchone()[0]
            for malformed in ("1_0", " 1 ", "١", "NaN", "1E999999999999999999999999"):
                with self.subTest(table=table, field=field, malformed=malformed):
                    with self.writer.database.transaction() as connection:
                        connection.execute(f"UPDATE {table} SET {field}=? WHERE account_id='alice'", (malformed,))
                    before = self.financial()
                    with self.assertRaises(ServiceError) as error:
                        self.views.read("alice", resource)
                    self.assertEqual((error.exception.status, error.exception.code), (503, "view_data_invalid"))
                    result = self.expect(503, "/v2/accounts/alice" + suffix)
                    self.assertEqual(result["error"]["code"], "view_data_invalid")
                    self.assertNotIn(malformed, result["error"]["message"])
                    self.assertNotIn(str(self.root), json.dumps(result))
                    self.assertEqual(self.financial(), before)
            with self.writer.database.transaction() as connection:
                connection.execute(f"UPDATE {table} SET {field}=? WHERE account_id='alice'", (original,))

    def test_liabilities_reject_fractional_minor_units_negatives_and_ledger_overflow(self):
        with self.writer.database.transaction() as connection:
            connection.execute("INSERT INTO uta_liabilities VALUES ('alice','BTC','0','0')")
        invalid = ("0.000000001", "1E-9", "-0.00000001", "-1", "1E30",
                   "1" + "0" * 38 + "E-38", "0E-39", "0E39")
        for field in ("principal", "interest"):
            for amount in invalid:
                with self.subTest(field=field, amount=amount):
                    with self.writer.database.transaction() as connection:
                        connection.execute(f"UPDATE uta_liabilities SET {field}=? WHERE account_id='alice'", (amount,))
                    with localcontext() as context:
                        context.prec = 1
                        for signal in context.traps:
                            context.traps[signal] = True
                        with self.assertRaises(ServiceError) as error:
                            self.views.read("alice")
                    self.assertEqual((error.exception.status, error.exception.code), (503, "view_data_invalid"))
            with self.writer.database.transaction() as connection:
                connection.execute(f"UPDATE uta_liabilities SET {field}='0' WHERE account_id='alice'")

    def test_exact_scientific_liabilities_and_redundant_zeros_ignore_decimal_context(self):
        with self.writer.database.transaction() as connection:
            connection.execute("INSERT INTO uta_liabilities VALUES ('alice','BTC','0','0')")
        valid = ("1E-8", "1.0E-8", "+0.000000010", "0E-38", "-0", "0E38", "1E29",
                 "999999999999999999999999999999.99999999")
        for field in ("principal", "interest"):
            for amount in valid:
                with self.subTest(field=field, amount=amount):
                    with self.writer.database.transaction() as connection:
                        connection.execute("UPDATE uta_liabilities SET principal='0',interest='0' WHERE account_id='alice'")
                        connection.execute(f"UPDATE uta_liabilities SET {field}=? WHERE account_id='alice'", (amount,))
                    with localcontext() as context:
                        context.prec, context.Emax, context.Emin = 1, 1, -1
                        for signal in context.traps:
                            context.traps[signal] = True
                        debt = self.views.read("alice")["account"]["liabilities"][0]
                    self.assertEqual((debt[field], debt["scale"]), (amount, 8))
        with self.writer.database.transaction() as connection:
            connection.execute("UPDATE uta_liabilities SET principal='1.0E-8',interest='1E-8' WHERE account_id='alice'")
        self.assertEqual(self.expect(200, "/v2/accounts/alice")["account"]["liabilities"][0]["principal"], "1.0E-8")


class RouterReadTests(unittest.TestCase):
    def test_existing_router_reads_only_owning_shard_without_financial_constructors(self):
        with TemporaryDirectory() as directory:
            names = []
            def bootstrap(router):
                for shard in range(2):
                    account = next(f"a-{i}" for i in range(100) if router.shard_for(f"a-{i}") == shard)
                    names.append(account)
                    router.create_account(account)
                    router.deposit(account, "seed", "USD", D(100 + shard))
            router = DurableProcessRouter.initialize(Path(directory) / "managed", 2, {"USD": 8}, managed=True, bootstrap=bootstrap)
            try:
                with patch.object(ExchangeService, "__init__", side_effect=AssertionError("parent read constructed writer")), \
                     patch.object(DurableLedger, "__init__", side_effect=AssertionError("parent read constructed ledger")):
                    server = make_server(router, port=0, credentials=(Credential(READER, "reader", names[0]), Credential(RISK, "risk")))
                    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": .01}); thread.start()
                    try:
                        for shard, account in enumerate(names):
                            connection = HTTPConnection(*server.server_address, timeout=3)
                            try:
                                connection.request("GET", "/v2/accounts/" + account, headers={"Authorization": "Bearer " + RISK})
                                response = connection.getresponse(); result = json.loads(response.read())
                                self.assertEqual(response.status, 200, result)
                                self.assertEqual(result["snapshot"]["shard"], shard)
                                self.assertEqual(result["account"]["balances"]["USD"]["balance"], str(100 + shard))
                            finally:
                                connection.close()
                    finally:
                        server.shutdown(); server.server_close(); thread.join(3)
            finally:
                router.close()


if __name__ == "__main__":
    unittest.main()
