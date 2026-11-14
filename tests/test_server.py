from datetime import datetime, timezone
from http.client import HTTPConnection
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Thread
import unittest

from uta.server import MAX_BATCH_ITEMS, MAX_BODY, make_server
from uta.simulator import Simulator


class SimulatorHttpTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = str(Path(directory.name, "lab.sqlite3"))
        self.server = make_server(Simulator(self.path))
        self.addCleanup(self.server.server_close)
        self.thread = Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.02})
        self.thread.start()
        self.addCleanup(self._stop_server)

    def _stop_server(self):
        self.server.shutdown()
        self.thread.join(timeout=2)

    def request(self, method, path, body=None, **overrides):
        headers = {}
        if body is not None:
            headers["Content-Type"] = "application/json"
            if not isinstance(body, bytes):
                body = json.dumps(body).encode("utf-8")
        headers.update(overrides)
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=2)
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def test_order_and_fill_persist_with_an_idempotent_receipt(self):
        status, created = self.request("POST", "/v1/bootstrap", {"account_id": "demo"})
        self.assertEqual(status, 200)
        self.assertEqual(created["state"]["version"], 0)
        path = "/v1/accounts/demo/commands"
        status, placed = self.request("POST", path, {
            "command_id": "order-1", "expected_version": 0, "command": {
                "type": "place_order", "symbol": "BTC-PERP", "quantity": "0.01",
                "limit_price": "60000", "fee_rate": "0.001",
            },
        })
        self.assertEqual(status, 200)
        self.assertEqual(placed["version"], 1)
        fill = {
            "command_id": "fill-1", "expected_version": 1, "command": {
                "type": "fill_order", "order_id": "order-1", "quantity": "0.01", "price": "60000",
            },
        }
        status, filled = self.request("POST", path, fill)
        self.assertEqual(status, 200)
        self.assertEqual(self.request("POST", path, fill), (200, filled))
        self.assertEqual(filled["version"], 2)
        self.assertEqual(filled["fills"][0]["fee"], "0.6")
        self.assertEqual(self.request("POST", path, dict(fill, command_id="new-id"))[0], 409)
        status, retrieved = self.request("GET", "/v1/accounts/demo")
        self.assertEqual(status, 200)
        self.assertEqual(retrieved["state"]["orders"]["order-1"]["status"], "FILLED")
        status, audit = self.request("GET", "/v1/accounts/demo/events")
        self.assertEqual(status, 200)
        self.assertEqual([entry["version"] for entry in audit["events"]], [0, 1, 2])
        self.assertEqual(self.request("GET", "/v1/accounts/demo/replay"), (
            200, {"account_id": "demo", "version": 2, "events_verified": 3},
        ))
        self.assertEqual(Simulator(self.path).view("demo")["state"], retrieved["state"])

    def test_import_and_guard_reject_ambiguous_or_external_requests(self):
        endpoint = "/v1/import-classic"
        snapshot = {
            "account_id": "classic",
            "version": 7,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "compartments": {
                "spot": {"balances": [{"asset": "USD", "free": "500", "locked": "0",
                                       "borrowed": "0", "interest": "0"}]},
                "margin": {"balances": []},
                "futures": {"balances": [], "positions": []},
            },
        }
        body = {"account_id": "imported", "snapshot": snapshot}
        self.assertEqual(self.request("POST", endpoint, body, Host="other.invalid")[0], 403)
        self.assertEqual(self.request("POST", endpoint, body, Origin="https://other.invalid")[0], 403)
        self.assertEqual(self.request("POST", endpoint, body, **{"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.request("POST", endpoint, body, **{"Sec-Fetch-Site": "cross-site"})[0], 403)
        duplicate = b'{"account_id":"demo","snapshot":{"version":7,"version":8}}'
        self.assertEqual(self.request("POST", endpoint, duplicate)[0], 400)
        self.assertEqual(self.request("POST", endpoint, b"x" * (MAX_BODY + 1))[0], 413)
        self.assertEqual(self.request("GET", "/v1/accounts/imported")[0], 404)
        origin = f"http://127.0.0.1:{self.server.server_port}"
        status, result = self.request("POST", endpoint, body, Origin=origin)
        self.assertEqual(status, 201)
        self.assertEqual(result["state"]["source"]["version"], 7)
        self.assertEqual(result["state"]["balances"]["USD"], "500")

    def test_batch_keeps_input_order_and_isolates_command_rejections(self):
        for account_id in ("demo", "other"):
            self.assertEqual(self.request("POST", "/v1/bootstrap", {"account_id": account_id})[0], 200)
        endpoint = "/v1/commands/batch"
        for invalid in ([], {}, [None] * (MAX_BATCH_ITEMS + 1)):
            self.assertEqual(self.request("POST", endpoint, {"items": invalid})[0], 400)
        first = {
            "account_id": "demo", "command_id": "open", "expected_version": 0,
            "command": {"type": "place_order", "symbol": "BTC-PERP", "quantity": "0.01",
                        "limit_price": "60000", "fee_rate": "0"},
        }
        stale = dict(first, command_id="stale")
        missing_order = {
            "account_id": "other", "command_id": "bad-cancel", "expected_version": 0,
            "command": {"type": "cancel_order", "order_id": "missing"},
        }
        second = dict(first, account_id="other")
        status, response = self.request("POST", endpoint, {"items": [first, stale, missing_order, second]})
        self.assertEqual(status, 200)
        placed, rejected, invalid, other_placed = response["results"]
        self.assertTrue(placed["ok"])
        self.assertEqual(placed["receipt"]["version"], 1)
        self.assertFalse(rejected["ok"])
        self.assertEqual(rejected["status"], 409)
        self.assertFalse(invalid["ok"])
        self.assertEqual(invalid["status"], 400)
        self.assertTrue(other_placed["ok"])
        self.assertEqual(other_placed["receipt"]["version"], 1)
        for account_id in ("demo", "other"):
            _, audit = self.request("GET", f"/v1/accounts/{account_id}/events")
            self.assertEqual([event["version"] for event in audit["events"]], [0, 1])


class AdmissionTests(unittest.TestCase):
    def test_full_worker_pool_rejects_overload_and_remains_responsive(self):
        entered = Event()
        release = Event()

        class SlowSimulator:
            def view(self, account_id):
                entered.set()
                if not release.wait(timeout=3):
                    raise RuntimeError("test did not release the first worker")
                return {"account_id": account_id}

        with make_server(SlowSimulator(), max_active=1) as server:
            loop = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02})
            loop.start()
            first = HTTPConnection("127.0.0.1", server.server_port, timeout=2)
            second = HTTPConnection("127.0.0.1", server.server_port, timeout=2)
            try:
                first.request("GET", "/v1/accounts/demo")
                self.assertTrue(entered.wait(timeout=2))
                second.request("GET", "/v1/accounts/demo")
                response = second.getresponse()
                self.assertEqual(response.status, 503)
                self.assertEqual(response.getheader("Retry-After"), "1")
                self.assertEqual(json.loads(response.read()), {"error": "too many concurrent requests"})
                release.set()
                response = first.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(response.read()), {"account_id": "demo"})
            finally:
                release.set()
                first.close()
                second.close()
                server.shutdown()
                loop.join(timeout=2)
