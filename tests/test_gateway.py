"""Transport tests exercise actual sockets, including malformed HTTP framing."""
from contextlib import closing
from decimal import Decimal
from http.client import HTTPConnection, HTTPResponse
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

from uta.gateway import Credential, load_credentials, make_server


ADMIN = "A" * 43
ALICE = "B" * 43
BOB = "C" * 43
CREDENTIALS = (Credential(ADMIN, "admin"), Credential(ALICE, "trader", "alice"),
               Credential(BOB, "trader", "bob"))


class FakeService:
    def __init__(self):
        self.calls = []
        self.ready = True

    def _record(self, name, *args, **kwargs):
        self.calls.append((name, args, kwargs))
        return {"operation": name}

    def readiness(self):
        return {"ready": self.ready, "reason": "ok" if self.ready else "stale_market"}

    def account(self, account_id):
        if account_id == "explode":
            raise RuntimeError("secret database password and private path")
        return self._record("account", account_id)

    def risk(self, account_id):
        return self._record("risk", account_id)

    def orders(self, account_id):
        return self._record("orders", account_id)

    def create_account(self, account_id):
        return self._record("create_account", account_id)

    def deposit(self, account_id, event_id, asset, amount):
        return self._record("deposit", account_id, event_id, asset, amount)

    def submit_order(self, account_id, order_id, symbol, quantity, limit_price, *, reduce_only=False):
        return self._record("submit_order", account_id, order_id, symbol, quantity,
                            limit_price, reduce_only=reduce_only)

    def cancel_order(self, account_id, order_id):
        return self._record("cancel_order", account_id, order_id)

    def apply_fill(self, account_id, order_id, fill_id, quantity, price):
        return self._record("apply_fill", account_id, order_id, fill_id, quantity, price)

    def publish_market(self, snapshot):
        return self._record("publish_market", snapshot)

    def set_kill_switch(self, enabled):
        return self._record("set_kill_switch", enabled)

    def events(self, *, after, limit):
        return self._record("events", after=after, limit=limit)


class CredentialTests(unittest.TestCase):
    def test_file_permissions_scope_and_secret_repr(self):
        self.assertNotIn(ADMIN, repr(CREDENTIALS[0]))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "credentials.json"
            path.write_text(json.dumps([{"token": ADMIN, "role": "admin"},
                                        {"token": ALICE, "role": "trader", "account_id": "alice"}]))
            path.chmod(0o600)
            self.assertEqual(load_credentials(path), CREDENTIALS[:2])
            path.chmod(0o640)
            with self.assertRaises(ValueError):
                load_credentials(path)
            path.chmod(0o600)
            link = Path(directory) / "link.json"
            link.symlink_to(path)
            with self.assertRaises(OSError):
                load_credentials(link)

    def test_invalid_configuration_never_echoes_tokens(self):
        invalid = [[], [{"token": "short", "role": "admin"}],
                   [{"token": ADMIN, "role": "trader"}],
                   [{"token": ADMIN, "role": "admin", "account_id": "alice"}],
                   [{"token": ADMIN, "role": "admin", "extra": "no"}],
                   [{"token": ADMIN, "role": "admin"}, {"token": ADMIN, "role": "admin"}]]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "credentials.json"
            for data in invalid:
                path.write_text(json.dumps(data))
                path.chmod(0o600)
                with self.assertRaises(ValueError) as caught:
                    load_credentials(path)
                self.assertNotIn(ADMIN, str(caught.exception))
            path.write_text('{"token":"' + ADMIN + '","token":"' + ALICE + '"}')
            with self.assertRaises(ValueError):
                load_credentials(path)
        for values in ((ADMIN, "owner", None), (ADMIN, "trader", "../alice"),
                       ("é" * 43, "admin", None)):
            with self.assertRaises(ValueError):
                Credential(*values)

    def test_bind_and_limits_fail_closed_before_socket_creation(self):
        for kwargs in ({"host": "0.0.0.0"}, {"host": "example.com"},
                       {"max_workers": 0}, {"request_timeout": float("nan")},
                       {"port": True}, {"credentials": ()},
                       {"credentials": (CREDENTIALS[0], CREDENTIALS[0])}):
            options = {"credentials": CREDENTIALS, **kwargs}
            with self.assertRaises(ValueError):
                make_server(FakeService(), **options)


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.service = FakeService()
        self.server = make_server(self.service, port=0, credentials=CREDENTIALS,
                                  request_timeout=0.3)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.thread.join, 2)
        self.addCleanup(self.server.shutdown)

    def request(self, method, path, payload=None, *, token=ADMIN, raw=None, headers=None):
        options = dict(headers or {})
        if token is not None:
            options["Authorization"] = "Bearer " + token
        if payload is not None:
            raw = json.dumps(payload)
        if raw is not None:
            options.setdefault("Content-Type", "application/json")
        with closing(HTTPConnection("127.0.0.1", self.server.server_port, timeout=2)) as connection:
            connection.request(method, path, body=raw, headers=options)
            response = connection.getresponse()
            body = response.read()
            return response.status, json.loads(body), dict(response.getheaders())

    def raw_request(self, data: bytes, *, eof=True):
        with socket.create_connection(("127.0.0.1", self.server.server_port), timeout=2) as client:
            client.sendall(data)
            if eof:
                client.shutdown(socket.SHUT_WR)
            response = HTTPResponse(client)
            response.begin()
            return response.status, json.loads(response.read())

    def test_liveness_is_public_and_all_account_access_requires_authentication(self):
        status, body, headers = self.request("GET", "/healthz", token=None)
        self.assertEqual((status, body), (200, {"status": "ok"}))
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["Connection"], "close")
        for token in (None, "invalid", "D" * 43):
            status, body, _ = self.request("GET", "/v1/accounts/alice", token=token)
            self.assertEqual(status, 401)
            self.assertNotIn(str(token), json.dumps(body))
        self.assertEqual(self.service.calls, [])

    def test_account_scopes_apply_to_reads_orders_and_cancellations(self):
        for suffix in ("", "/risk", "/orders"):
            self.assertEqual(self.request("GET", "/v1/accounts/alice" + suffix, token=ALICE)[0], 200)
            before = len(self.service.calls)
            self.assertEqual(self.request("GET", "/v1/accounts/bob" + suffix, token=ALICE)[0], 403)
            self.assertEqual(len(self.service.calls), before)
        payload = {"order_id": "o1", "symbol": "BTC-PERP", "quantity": "-0.125",
                   "limit_price": "21000.01", "reduce_only": True}
        self.assertEqual(self.request("POST", "/v1/accounts/alice/orders", payload, token=ALICE)[0], 201)
        self.assertEqual(self.service.calls[-1], ("submit_order", ("alice", "o1", "BTC-PERP",
                         Decimal("-0.125"), Decimal("21000.01")), {"reduce_only": True}))
        self.assertEqual(self.request("POST", "/v1/accounts/alice/orders/o1/cancel", {}, token=ALICE)[0], 200)
        self.assertEqual(self.request("POST", "/v1/accounts/bob/orders/o1/cancel", {}, token=ALICE)[0], 403)
        payload["symbol"] = "BTC/USD"
        self.assertEqual(self.request("POST", "/v1/accounts/alice/orders", payload, token=ALICE)[0], 201)
        self.assertEqual(self.service.calls[-1][1][2], "BTC/USD")

    def test_traders_cannot_mutate_cash_market_fills_or_admin_controls(self):
        routes = [("POST", "/v1/accounts", {"account_id": "alice"}),
                  ("POST", "/v1/accounts/alice/deposits", {"event_id": "d", "asset": "USD", "amount": "10"}),
                  ("POST", "/v1/accounts/alice/orders/o/fills", {"fill_id": "f", "quantity": "1", "price": "1"}),
                  ("PUT", "/v1/market", {}), ("PUT", "/v1/kill-switch", {"enabled": True}),
                  ("GET", "/v1/events", None), ("GET", "/metrics", None)]
        for method, path, payload in routes:
            with self.subTest(path=path):
                self.assertEqual(self.request(method, path, payload, token=ALICE)[0], 403)
        self.assertEqual(self.service.calls, [])

    def test_admin_cash_fills_halt_and_bounded_audit_cursor(self):
        self.assertEqual(self.request("POST", "/v1/accounts", {"account_id": "alice"})[0], 201)
        self.assertEqual(self.request("POST", "/v1/accounts/alice/deposits",
                         {"event_id": "d1", "asset": "USD", "amount": "1.25"})[0], 200)
        self.assertEqual(self.service.calls[-1][1], ("alice", "d1", "USD", Decimal("1.25")))
        self.assertEqual(self.request("POST", "/v1/accounts/alice/orders/o1/fills",
                         {"fill_id": "f1", "quantity": "-0.5", "price": "20000"})[0], 200)
        self.assertEqual(self.service.calls[-1][1], ("alice", "o1", "f1", Decimal("-0.5"), Decimal("20000")))
        self.assertEqual(self.request("PUT", "/v1/kill-switch", {"enabled": True})[0], 200)
        self.assertEqual(self.service.calls[-1], ("set_kill_switch", (True,), {}))
        self.assertEqual(self.request("GET", "/v1/events?after=12&limit=10")[0], 200)
        self.assertEqual(self.service.calls[-1], ("events", (), {"after": 12, "limit": 10}))
        for query in ("after=-1", "limit=1001", "limit=0", "limit=2&limit=3", "unknown=1", "after", "after=1&limit=2&x=3"):
            self.assertEqual(self.request("GET", "/v1/events?" + query)[0], 400)
        self.assertEqual(self.request("GET", "/metrics")[0], 200)

    def test_readiness_is_authenticated_and_reflects_closed_gate(self):
        self.assertEqual(self.request("GET", "/readyz", token=None)[0], 401)
        self.assertEqual(self.request("GET", "/readyz", token=ALICE)[0], 200)
        self.service.ready = False
        status, body, _ = self.request("GET", "/readyz")
        self.assertEqual((status, body["ready"]), (503, False))
        with patch.object(self.service, "readiness", side_effect=RuntimeError("secret")):
            status, body, _ = self.request("GET", "/readyz")
            self.assertEqual(status, 503)
            self.assertNotIn("secret", str(body))

    def test_only_admin_can_publish_a_typed_market_snapshot(self):
        market = {"version": 7, "observed_at": "2026-11-14T14:00:00+00:00",
                  "assets": {"USD": {"price": "1", "collateral_factor": "1"}},
                  "instruments": {"BTC/USD": {"mark_price": "21000", "initial_margin_rate": "0.1",
                                                "maintenance_margin_rate": "0.05"}}}
        self.assertEqual(self.request("PUT", "/v1/market", market, token=ALICE)[0], 403)
        self.assertEqual(self.service.calls, [])
        self.assertEqual(self.request("PUT", "/v1/market", market)[0], 200)
        published = self.service.calls[-1][1][0]
        self.assertEqual(published.version, 7)
        self.assertEqual(published.instruments["BTC/USD"].mark_price, Decimal("21000"))
        for invalid in ({**market, "version": True}, {**market, "assets": {"USD": {"price": 1, "collateral_factor": "1"}}}):
            self.assertEqual(self.request("PUT", "/v1/market", invalid)[0], 400)

    def test_strict_json_and_financial_types_reject_before_service_call(self):
        valid = {"order_id": "o", "symbol": "BTC-PERP", "quantity": "1", "limit_price": "21000"}
        invalid = [{**valid, "quantity": 0.1}, {**valid, "quantity": "NaN"},
                   {**valid, "quantity": "1e9999"}, {**valid, "quantity": "1_000"},
                   {**valid, "reduce_only": 1}, {**valid, "balances": {"USD": "1e9"}},
                   {**valid, "order_id": "../o"}, {**valid, "limit_price": " 1 "},
                   [], None]
        for data in invalid:
            self.assertEqual(self.request("POST", "/v1/accounts/alice/orders", raw=json.dumps(data))[0], 400)
        malformed = [b'{"quantity":"1","quantity":"2"}', b'{"a":NaN}',
                     b'{"a":Infinity}', b'{"a":"\xff"}', b'{} {}', b'[[[[']
        for data in malformed:
            self.assertEqual(self.request("POST", "/v1/accounts/alice/orders", raw=data)[0], 400)
        self.assertEqual(self.service.calls, [])
        self.assertEqual(self.request("POST", "/v1/accounts/alice/orders/o/cancel", {"unexpected": True})[0], 400)
        self.assertEqual(self.request("PUT", "/v1/kill-switch", {"enabled": "false"})[0], 400)

    def test_duplicate_lengths_transfer_encodings_and_truncated_body_fail_closed(self):
        base = b"POST /v1/accounts HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer " + ADMIN.encode() + b"\r\nContent-Type: application/json\r\n"
        cases = [(b"Content-Length: 2\r\nContent-Length: 2\r\n\r\n{}", 400),
                 (b"Content-Length: 2\r\nTransfer-Encoding: chunked\r\n\r\n{}", 400),
                 (b"Content-Length: -1\r\n\r\n", 400),
                 (b"Content-Length: 999999\r\n\r\n", 413),
                 (b"\r\n", 411),
                 (b"Content-Length: 10\r\n\r\n{}", 400),
                 (b"Content-Length: 2\r\nAuthorization: Bearer " + ALICE.encode() + b"\r\n\r\n{}", 400)]
        for framing, expected in cases:
            with self.subTest(framing=framing):
                self.assertEqual(self.raw_request(base + framing)[0], expected)
        self.assertEqual(self.service.calls, [])

    def test_slow_body_timeout_content_type_and_unknown_paths(self):
        base = b"POST /v1/accounts HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer " + ADMIN.encode()
        self.assertEqual(self.raw_request(base + b"\r\nContent-Type: application/json\r\nContent-Length: 10\r\n\r\n{}", eof=False)[0], 408)
        self.assertEqual(self.request("POST", "/v1/accounts", raw="{}", headers={"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.request("GET", "/v1/accounts/%61lice")[0], 400)
        self.assertEqual(self.request("GET", "/v1/accounts/alice?account_id=bob")[0], 400)
        self.assertEqual(self.request("GET", "/does-not-exist")[0], 404)
        status, body, _ = self.request("DELETE", "/v1/accounts/alice")
        self.assertEqual(status, 501)
        self.assertNotIn("DELETE", str(body))

    def test_unexpected_exceptions_do_not_expose_internal_details(self):
        status, body, _ = self.request("GET", "/v1/accounts/explode")
        self.assertEqual(status, 500)
        self.assertEqual(body, {"error": {"code": "internal_error", "message": "internal service error"}})
        self.assertNotIn("secret", str(body))

    def test_explicit_business_errors_keep_their_status(self):
        class BusinessError(Exception):
            code = "insufficient_margin"
            status = 409
        module = types.ModuleType("uta.service")
        module.ServiceError = BusinessError
        with patch.dict(sys.modules, {"uta.service": module}):
            with patch.object(self.service, "account", side_effect=BusinessError("insufficient margin")):
                status, body, _ = self.request("GET", "/v1/accounts/alice")
        self.assertEqual(status, 409)
        self.assertEqual(body["error"]["code"], "insufficient_margin")

    def test_worker_limit_returns_503_instead_of_spawning_unbounded_threads(self):
        entered, release = threading.Event(), threading.Event()
        service = FakeService()

        def block(_):
            entered.set()
            if not release.wait(2):
                raise RuntimeError("test worker was not released")
            return {"ok": True}

        service.account = block
        server = make_server(service, port=0, credentials=CREDENTIALS, max_workers=1)
        serving = threading.Thread(target=server.serve_forever, daemon=True)
        serving.start()
        first = HTTPConnection("127.0.0.1", server.server_port, timeout=2)
        try:
            first.request("GET", "/v1/accounts/alice", headers={"Authorization": "Bearer " + ALICE})
            self.assertTrue(entered.wait(1))
            with closing(HTTPConnection("127.0.0.1", server.server_port, timeout=2)) as second:
                second.request("GET", "/healthz")
                response = second.getresponse()
                self.assertEqual(response.status, 503)
                response.read()
            release.set()
            response = first.getresponse()
            self.assertEqual(response.status, 200)
            response.read()
            self.assertEqual(server.counters()["rejected_connections"], 1)
        finally:
            release.set()
            first.close()
            server.shutdown()
            serving.join(2)
            server.server_close()


if __name__ == "__main__":
    unittest.main()
