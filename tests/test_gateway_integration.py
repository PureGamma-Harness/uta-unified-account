"""Real HTTP acceptance checks spanning authentication, risk and persistence."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from http.client import HTTPConnection
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest

from uta.gateway import Credential, make_server
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ExchangeService
from uta.storage import Database


NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)
ADMIN = "A" * 40
ALICE = "B" * 40
BOB = "C" * 40


class GatewayExchangeAcceptance(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / "exchange.sqlite3"
        self.now = NOW
        self.service = ExchangeService(Database(self.database), {"USD": 8}, clock=lambda: self.now)
        self.server = None
        self.thread = None
        self.start_server()
        self.addCleanup(self.stop_server)
        self.assert_status(201, "POST", "/v1/accounts", {"account_id": "alice"})
        self.assert_status(201, "POST", "/v1/accounts", {"account_id": "bob"})
        self.assert_status(200, "PUT", "/v1/market", self.market_payload())
        self.assert_status(200, "POST", "/v1/accounts/alice/deposits",
                           {"event_id": "fund", "asset": "USD", "amount": "1000"})
        self.assert_status(200, "PUT", "/v1/kill-switch", {"enabled": False})

    def start_server(self):
        self.server = make_server(self.service, port=0, credentials=(
            Credential(ADMIN, "admin"), Credential(ALICE, "trader", "alice"),
            Credential(BOB, "trader", "bob")))
        self.thread = Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        self.thread.start()

    def stop_server(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=5)
            self.server = None
            self.thread = None

    def market_payload(self, version=1, mark="100"):
        return json.loads(MarketSnapshot(
            version, self.now, {"USD": AssetSpec(D("1"), D("1"))},
            {"BTC-PERP": InstrumentSpec(D(mark), D("0.1"), D("0.05"))}).to_json())

    def request(self, method, path, payload=None, *, token=ADMIN):
        headers = {}
        if token is not None:
            headers["Authorization"] = "Bearer " + token
        body = None
        if payload is not None:
            body = json.dumps(payload, separators=(",", ":")).encode()
            headers["Content-Type"] = "application/json"
        connection = HTTPConnection(*self.server.server_address, timeout=5)
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            result = json.loads(response.read())
            return response.status, result
        finally:
            connection.close()

    def assert_status(self, expected, method, path, payload=None, *, token=ADMIN):
        status, result = self.request(method, path, payload, token=token)
        self.assertEqual(status, expected, result)
        return result

    def order(self, order_id="buy", quantity="2", price="100"):
        return self.assert_status(201, "POST", "/v1/accounts/alice/orders",
                                  {"order_id": order_id, "symbol": "BTC-PERP", "quantity": quantity,
                                   "limit_price": price}, token=ALICE)

    def test_authenticated_partial_execution_retry_cancel_and_restart(self):
        accepted = self.order()
        self.assertEqual(D(accepted["reserved_margin"]), D("20.08"))
        fill = {"fill_id": "f1", "quantity": "1", "price": "100"}
        execution = self.assert_status(200, "POST", "/v1/accounts/alice/orders/buy/fills", fill)
        self.assertEqual(execution["status"], "PARTIALLY_FILLED")
        account = self.assert_status(200, "GET", "/v1/accounts/alice", token=ALICE)
        self.assertEqual(D(account["balances"]["USD"]), D("999.96"))
        self.assertEqual(D(account["positions"]["BTC-PERP"]["quantity"]), D("1"))
        events = self.assert_status(200, "GET", "/v1/events?after=0&limit=1000")
        self.assert_status(200, "POST", "/v1/accounts/alice/orders/buy/fills", fill)
        self.assertEqual(self.assert_status(200, "GET", "/v1/events?after=0&limit=1000"), events)
        self.assert_status(409, "POST", "/v1/accounts/alice/orders/buy/fills",
                           {"fill_id": "f1", "quantity": "1", "price": "99"})
        cancelled = self.assert_status(200, "POST", "/v1/accounts/alice/orders/buy/cancel", {}, token=ALICE)
        self.assertEqual(cancelled["status"], "CANCELLED")
        account = self.assert_status(200, "GET", "/v1/accounts/alice", token=ALICE)
        self.assertEqual(account["open_order_margin"], "0")
        self.stop_server()
        self.service = ExchangeService(Database(self.database), {"USD": 8}, clock=lambda: self.now)
        self.start_server()
        self.assertEqual(self.assert_status(200, "GET", "/v1/accounts/alice", token=ALICE), account)
        self.assertEqual(self.order()["status"], "CANCELLED", "a terminal ID must never reopen")
        self.service.ledger.verify()

    def test_role_and_account_boundaries_protect_real_state(self):
        before = self.service.account("alice")
        events = self.service.events(limit=1000)
        for method, path, payload, token in (
            ("GET", "/v1/accounts/alice", None, BOB),
            ("GET", "/v1/accounts/bob", None, ALICE),
            ("POST", "/v1/accounts/bob/orders", {"order_id": "attack", "symbol": "BTC-PERP", "quantity": "1", "limit_price": "100"}, ALICE),
            ("POST", "/v1/accounts/alice/deposits", {"event_id": "attack", "asset": "USD", "amount": "1000000"}, ALICE),
            ("PUT", "/v1/market", self.market_payload(2, "1"), ALICE),
            ("PUT", "/v1/kill-switch", {"enabled": False}, ALICE),
            ("GET", "/v1/events", None, ALICE),
        ):
            with self.subTest(method=method, path=path):
                self.assert_status(403, method, path, payload, token=token)
        self.assert_status(401, "GET", "/v1/accounts/alice", token=None)
        self.assertEqual(self.service.account("alice"), before)
        self.assertEqual(self.service.events(limit=1000), events)
        self.order()
        before = self.service.account("alice")
        self.assert_status(403, "POST", "/v1/accounts/alice/orders/buy/fills",
                           {"fill_id": "attack", "quantity": "1", "price": "100"}, token=ALICE)
        self.assertEqual(self.service.account("alice"), before)

    def test_stale_market_errors_leave_ready_liveness_and_cancellation_distinct(self):
        self.order()
        self.now += timedelta(seconds=6)
        self.assertEqual(self.assert_status(200, "GET", "/healthz", token=None), {"status": "ok"})
        readiness = self.assert_status(503, "GET", "/readyz", token=ALICE)
        self.assertFalse(readiness["ready"])
        before = self.service.account("alice")
        self.assert_status(503, "POST", "/v1/accounts/alice/orders",
                           {"order_id": "new", "symbol": "BTC-PERP", "quantity": "1", "limit_price": "100"}, token=ALICE)
        self.assert_status(503, "POST", "/v1/accounts/alice/orders/buy/fills",
                           {"fill_id": "stale", "quantity": "1", "price": "100"})
        self.assertEqual(self.service.account("alice"), before)
        self.assertEqual(self.assert_status(200, "POST", "/v1/accounts/alice/orders/buy/cancel", {}, token=ALICE)["status"], "CANCELLED")
        self.assert_status(200, "PUT", "/v1/market", self.market_payload(2))
        self.assertTrue(self.assert_status(200, "GET", "/readyz", token=ALICE)["ready"])


if __name__ == "__main__":
    unittest.main()
