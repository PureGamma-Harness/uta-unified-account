"""Real authenticated HTTP, persisted receipts and independently fenced PIDs."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from http.client import HTTPConnection, HTTPResponse
import json
import multiprocessing
import os
from pathlib import Path
import socket
from tempfile import TemporaryDirectory
from threading import Thread
from time import monotonic, sleep
import unittest
from unittest.mock import patch
from uuid import uuid4

from uta.credit import CreditService
from uta.durable_commands import CommandExecutionError, QueueStore
from uta.durable_gateway import DurableCommandAPI, make_server
from uta.durable_process import DurableProcessRouter
from uta.gateway import Credential
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ExchangeService
from uta.storage import Database, StorageError
from uta.writer_fence import WriterFence


ADMIN, RISK, TRADER, OTHER, READER, FUNDING = (letter * 43 for letter in "AKTBRF")


def _fenced_worker(path, ready, stop, execute, fail_order=None):
    """Actual spawn target. The HTTP parent never receives its WriterToken."""
    database = Database(path)
    fence = WriterFence(database)
    token = fence.acquire("http-worker:" + uuid4().hex, 30)
    try:
        exchange = ExchangeService(database.for_writer(token), {"USD": 2},
                                   max_price_age=timedelta(seconds=30))
        credit = CreditService(exchange)
        with database.read_transaction() as connection:
            row = connection.execute("SELECT queue_capacity,cancel_reserve,market_capacity FROM uta_command_config WHERE singleton=1").fetchone()
            policy = dict(row)
        queue = QueueStore(database, **policy)
        if fail_order:
            original = exchange._event
            def fail_event(connection, kind, account_id, payload):
                if kind == "ORDER_ACCEPTED" and payload["order_id"] == fail_order:
                    raise RuntimeError("synthetic worker failure")
                return original(connection, kind, account_id, payload)
            exchange._event = fail_event
        ready.send({"pid": os.getpid(), "generation": token.generation})
        while not stop.is_set():
            if execute.is_set():
                try:
                    queue.process_one(exchange, credit=credit)
                except CommandExecutionError as error:
                    if error.command_id is None:
                        raise
                    current = queue.status(error.command_id)
                    if current["state"] == "PENDING":
                        queue.record_failure(exchange, error.command_id, max_attempts=1)
            stop.wait(.01)
    finally:
        fence.release(token)
        ready.close()


class HTTPMixin:
    def start_http(self, producer, alice="alice", bob="bob"):
        credentials = (Credential(ADMIN, "admin"), Credential(RISK, "risk"),
            Credential(TRADER, "trader", alice), Credential(OTHER, "trader", bob),
            Credential(READER, "reader", alice), Credential(FUNDING, "funding", alice))
        self.server = make_server(producer, port=0, credentials=credentials, request_timeout=.3)
        self.thread = Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01})
        self.thread.start()

    def stop_http(self):
        if getattr(self, "server", None) is not None:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(3)
            self.server = None

    def request(self, method, path, payload=None, *, token=ADMIN, raw=None, headers=None):
        headers = dict(headers or {})
        if token is not None:
            headers["Authorization"] = "Bearer " + token
        if payload is not None:
            raw = json.dumps(payload)
        if raw is not None:
            headers.setdefault("Content-Type", "application/json")
        connection = HTTPConnection(*self.server.server_address, timeout=3)
        try:
            connection.request(method, path, raw, headers)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def expect(self, status, method, path, payload=None, **options):
        actual, result = self.request(method, path, payload, **options)
        self.assertEqual(actual, status, result)
        return result

    def terminal(self, account_id, command_id, *, token=ADMIN):
        deadline = monotonic() + 6
        while monotonic() < deadline:
            status, result = self.request("GET", f"/v2/accounts/{account_id}/commands/{command_id}", token=token)
            self.assertIn(status, (200, 202), result)
            if result["state"] != "PENDING":
                return result
            self.assertEqual((result["ack"], result["result"]), ("durably_queued", None))
            sleep(.01)
        self.fail("worker did not commit a terminal receipt")


class DurableGatewayTests(HTTPMixin, unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "exchange.sqlite3"
        self.database = Database(self.path)
        bootstrap = ExchangeService(self.database, {"USD": 2}, max_price_age=timedelta(seconds=30))
        bootstrap.publish_market(MarketSnapshot(1, datetime.now(timezone.utc),
            {"USD": AssetSpec(D(1), D(1))}, {"X": InstrumentSpec(D(100), D(".1"), D(".05"))}))
        bootstrap.set_kill_switch(False)
        for account in ("alice", "bob"):
            bootstrap.create_account(account)
            bootstrap.deposit(account, "seed", "USD", D(100))
        credit = CreditService(bootstrap)
        credit.configure_asset_limit("USD", D(100))
        credit.configure_limit("alice", "USD", D(20))
        credit.fund_pool("pool", "USD", D(20), source_reference="synthetic:pool")
        credit.borrow("alice", "seed-loan", "USD", D(5))
        self.policy = {"queue_capacity": 2, "cancel_reserve": 1, "market_capacity": 1}
        self.queue = QueueStore(self.database, initialize=True, **self.policy)
        WriterFence(self.database).enable("http-test-authority")
        self.context = multiprocessing.get_context("spawn")
        self.worker = None
        self.addCleanup(self.stop_worker)
        self.start_http(self.queue)
        self.addCleanup(self.stop_http)

    def start_worker(self, *, fail_order=None):
        self.stop = self.context.Event()
        self.execute = self.context.Event()
        receive, send = self.context.Pipe(duplex=False)
        self.worker = self.context.Process(target=_fenced_worker,
            args=(str(self.path), send, self.stop, self.execute, fail_order))
        self.worker.start()
        send.close()
        self.assertTrue(receive.poll(5), "worker failed to acquire its own lease")
        report = receive.recv()
        receive.close()
        self.assertNotEqual(report["pid"], os.getpid())
        self.assertEqual(report["pid"], self.worker.pid)
        return report

    def stop_worker(self):
        if self.worker is not None:
            self.stop.set()
            self.worker.join(5)
            if self.worker.is_alive():
                self.worker.kill()
                self.worker.join(5)
            self.assertEqual(self.worker.exitcode, 0)
            self.worker = None

    def order(self, command="command", order="order", quantity="1"):
        return {"command_id": command, "order_id": order, "symbol": "X",
                "quantity": quantity, "limit_price": "100"}

    def financial(self):
        with self.database.read_transaction() as connection:
            return {table: [tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY rowid")]
                    for table in ("uta_accounts", "uta_orders", "uta_positions", "uta_events",
                                  "ledger_events", "ledger_postings", "ledger_balances", "uta_liabilities")}

    def test_queue_ack_is_not_admission_then_real_child_commits_order_reject_and_cancel(self):
        before = self.financial()
        queued = self.expect(202, "POST", "/v2/accounts/alice/orders", self.order(), token=TRADER)
        self.assertEqual((queued["state"], queued["ack"], queued["result"]), ("PENDING", "durably_queued", None))
        self.assertEqual(self.financial(), before)
        self.expect(202, "GET", queued["status_url"], token=READER)
        self.start_worker()
        self.execute.set()
        admitted = self.terminal("alice", "command", token=TRADER)
        self.assertEqual((admitted["state"], admitted["ack"], admitted["result"]["reserved_margin"]), ("SUCCEEDED", "terminal_receipt", "10.04"))
        rejected = self.expect(202, "POST", "/v2/accounts/alice/orders", self.order("over", "over", "99"), token=TRADER)
        self.assertIsNone(rejected["result"])
        refusal = self.terminal("alice", "over", token=TRADER)
        self.assertEqual((refusal["state"], refusal["result"], refusal["error"]["code"]), ("REJECTED", None, "insufficient_margin"))
        self.expect(202, "POST", "/v2/accounts/alice/orders/order/cancel", {"command_id": "cancel"}, token=TRADER)
        cancelled = self.terminal("alice", "cancel", token=TRADER)
        self.assertEqual(cancelled["result"]["status"], "CANCELLED")
        # The admission command is an immutable transition receipt; it does not
        # pretend to be the latest mutable order projection after cancellation.
        self.assertEqual(self.expect(200, "POST", "/v2/accounts/alice/orders", self.order(), token=TRADER), admitted)
        self.assertEqual(self.expect(200, "GET", "/v2/accounts/alice/commands/over", token=TRADER), refusal)

    def test_repay_is_funding_scoped_and_terminal_result_is_real_debt_change(self):
        command = {"command_id": "repay", "asset": "USD", "amount": "1"}
        for token in (TRADER, READER, RISK):
            self.expect(403, "POST", "/v2/accounts/alice/repay", command, token=token)
        queued = self.expect(202, "POST", "/v2/accounts/alice/repay", command, token=FUNDING)
        self.assertIsNone(queued["result"])
        self.start_worker()
        self.execute.set()
        receipt = self.terminal("alice", "repay", token=FUNDING)
        self.assertEqual((receipt["state"], receipt["result"]["principal"], receipt["result"]["principal_repaid"]), ("SUCCEEDED", "4", "1"))
        before = self.financial()
        self.assertEqual(self.expect(200, "POST", "/v2/accounts/alice/repay", command, token=FUNDING), receipt)
        self.assertEqual(self.financial(), before)

    def test_scope_stable_ids_unsupported_operations_and_parent_restart_do_not_open_financial_service(self):
        queued = self.expect(202, "POST", "/v2/accounts/alice/orders", self.order(), token=TRADER)
        self.expect(409, "POST", "/v2/accounts/alice/orders", self.order(quantity="2"), token=TRADER)
        self.expect(403, "POST", "/v2/accounts/bob/orders", self.order("foreign"), token=TRADER)
        self.expect(403, "GET", queued["status_url"], token=OTHER)
        self.expect(404, "GET", "/v2/accounts/bob/commands/command", token=OTHER)
        self.expect(404, "GET", "/v2/accounts/alice/commands/unknown", token=READER)
        self.expect(404, "GET", queued["status_url"], token=FUNDING)
        self.expect(403, "POST", "/v2/accounts/alice/orders", self.order("reader"), token=READER)
        for path in ("/v1/accounts/alice/orders", "/risk", "/order-check"):
            self.expect(404, "POST", path, self.order(), token=TRADER)
        self.expect(501, "POST", "/v2/accounts/alice/orders/order/fills", {}, token=ADMIN)
        self.expect(501, "GET", "/v2/accounts/alice/risk", token=READER)
        before = self.financial()
        self.stop_http()
        with patch.object(ExchangeService, "__init__", side_effect=AssertionError("parent financial constructor forbidden")):
            reopened = QueueStore(Database(self.path), **self.policy)
            self.start_http(reopened)
            self.assertEqual(self.expect(202, "GET", queued["status_url"], token=TRADER), queued)
            self.expect(200, "GET", "/v2/worker-health", token=RISK)
        self.assertEqual(self.financial(), before)

    def test_worker_quarantine_is_not_risk_rejection_or_acceptance(self):
        before = self.financial()
        self.expect(202, "POST", "/v2/accounts/alice/orders", self.order("fault", "fault"), token=TRADER)
        self.start_worker(fail_order="fault")
        self.execute.set()
        receipt = self.terminal("alice", "fault", token=TRADER)
        self.assertEqual((receipt["state"], receipt["result"], receipt["error"]["code"]), ("QUARANTINED", None, "command_quarantined"))
        self.assertEqual(self.financial(), before)

    def test_unknown_enqueue_outcome_returns_no_fake_result_and_original_id_recovers(self):
        backend = self.server.service._producer.queue
        original = backend.enqueue_submit
        def commit_then_lose_reply(*args, **kwargs):
            original(*args, **kwargs)
            raise StorageError("synthetic post-commit transport fault")
        with patch.object(backend, "enqueue_submit", side_effect=commit_then_lose_reply):
            result = self.expect(503, "POST", "/v2/accounts/alice/orders", self.order("unknown"), token=TRADER)
            self.assertEqual(result["error"]["code"], "command_outcome_unknown")
            self.assertNotIn("synthetic", json.dumps(result))
        queued = self.expect(202, "GET", "/v2/accounts/alice/commands/unknown", token=TRADER)
        self.assertEqual(self.expect(202, "POST", "/v2/accounts/alice/orders", self.order("unknown"), token=TRADER), queued)

    def test_bounded_inbox_rejects_without_record_but_keeps_cancel_and_control_lanes(self):
        before = self.financial()
        for identifier in ("one", "two"):
            self.expect(202, "POST", "/v2/accounts/alice/orders", self.order(identifier, identifier), token=TRADER)
        overload = self.expect(503, "POST", "/v2/accounts/alice/orders", self.order("overload", "overload"), token=TRADER)
        self.assertEqual(overload["error"]["code"], "durable_queue_overloaded")
        self.assertIsNone(self.queue.status("overload"))
        self.expect(202, "POST", "/v2/accounts/alice/orders/one/cancel", {"command_id": "cancel"}, token=TRADER)
        self.expect(202, "POST", "/v2/control/halt", {"command_id": "halt", "enabled": True}, token=RISK)
        self.assertEqual(self.expect(200, "GET", "/v2/metrics", token=RISK)["durable"]["pending_commands"], 4)
        self.assertEqual(self.financial(), before)

    def test_actual_lost_http_response_is_recovered_with_the_same_command_id(self):
        body = json.dumps(self.order("lost", "lost")).encode()
        with socket.create_connection(self.server.server_address, timeout=2) as client:
            client.sendall(("POST /v2/accounts/alice/orders HTTP/1.1\r\nHost: localhost\r\n"
                f"Authorization: Bearer {TRADER}\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n").encode() + body)
            # Deliberately do not receive the response, including its HTTP code.
        deadline = monotonic() + 3
        while self.queue.status("lost") is None:
            self.assertLess(monotonic(), deadline)
            sleep(.01)
        original = self.expect(202, "GET", "/v2/accounts/alice/commands/lost", token=TRADER)
        self.assertEqual(self.expect(202, "POST", "/v2/accounts/alice/orders", self.order("lost", "lost"), token=TRADER), original)

    def test_strict_json_framing_timeout_auth_and_diagnostics_reuse_existing_http_boundary(self):
        before = self.financial()
        self.expect(401, "GET", "/v2/metrics", token=None)
        self.expect(200, "GET", "/healthz", token=None)
        for token in (TRADER, READER, FUNDING):
            self.expect(403, "GET", "/v2/metrics", token=token)
            self.expect(403, "GET", "/v2/worker-health", token=token)
        health = self.expect(200, "GET", "/v2/worker-health", token=RISK)
        self.assertFalse(health["writer"]["lease_active"])
        self.assertNotIn(str(self.path), json.dumps(health))
        self.assertNotIn("owner_nonce", json.dumps(health))
        self.expect(400, "POST", "/v2/accounts/alice/orders", raw='{"command_id":"one","command_id":"two"}', token=TRADER)
        self.expect(400, "POST", "/v2/accounts/alice/orders", {**self.order(), "quantity": 0.1}, token=TRADER)
        header = ("POST /v2/accounts/alice/orders HTTP/1.1\r\nHost: localhost\r\n"
                  f"Authorization: Bearer {TRADER}\r\nContent-Type: application/json\r\n")
        for extra, expected, eof in (("Content-Length: 2\r\nContent-Length: 2\r\n\r\n{}", 400, True),
                                     ("Transfer-Encoding: chunked\r\nContent-Length: 2\r\n\r\n{}", 400, True),
                                     ("Content-Length: 100\r\n\r\n{}", 408, False)):
            with socket.create_connection(self.server.server_address, timeout=2) as client:
                client.sendall((header + extra).encode())
                if eof:
                    client.shutdown(socket.SHUT_WR)
                response = HTTPResponse(client)
                response.begin()
                self.assertEqual(response.status, expected)
                response.read()
        self.assertIsNone(self.queue.status("one"))
        self.assertEqual(self.financial(), before)

    def test_control_commands_have_durable_ids_and_risk_permissions(self):
        payload = {"command_id": "halt", "enabled": True}
        self.expect(403, "POST", "/v2/control/halt", payload, token=TRADER)
        queued = self.expect(202, "POST", "/v2/control/halt", payload, token=RISK)
        self.assertEqual(queued["result"], None)
        self.expect(409, "POST", "/v2/control/halt", {**payload, "enabled": False}, token=RISK)
        self.start_worker()
        self.execute.set()
        deadline = monotonic() + 5
        while monotonic() < deadline:
            status, receipt = self.request("GET", "/v2/control/commands/halt", token=RISK)
            if status == 200:
                break
            sleep(.01)
        self.assertEqual((receipt["state"], receipt["result"]), ("SUCCEEDED", {"enabled": True}))
        self.expect(404, "GET", "/v2/accounts/alice/commands/halt", token=TRADER)


class DurableRouterGatewayTests(HTTPMixin, unittest.TestCase):
    def test_real_process_router_scopes_same_command_id_by_account_and_parent_reopen(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "managed"
            names = []
            def bootstrap(router):
                for shard in range(2):
                    account = next(f"account-{i}" for i in range(100) if router.shard_for(f"account-{i}") == shard)
                    names.append(account)
                    router.create_account(account)
                    router.deposit(account, "seed", "USD", D(1000))
            router = DurableProcessRouter.initialize(path, 2, {"USD": 8}, managed=True,
                bootstrap=bootstrap, lease_seconds=.6, poll_interval=.01)
            self.addCleanup(router.close)
            router.start()
            router.publish_market(MarketSnapshot(1, datetime.now(timezone.utc),
                {"USD": AssetSpec(D(1), D(1))}, {"X": InstrumentSpec(D(100), D(".1"), D(".05"))}), timeout=6)
            router.set_kill_switch(False, timeout=6)
            router.close()
            self.start_http(router, *names)
            self.addCleanup(self.stop_http)
            for account, token in zip(names, (TRADER, OTHER)):
                result = self.expect(202, "POST", f"/v2/accounts/{account}/orders", {"command_id": "same-id",
                    "order_id": "o", "symbol": "X", "quantity": "1", "limit_price": "100"}, token=token)
                self.assertIsNone(result["result"])
            self.expect(403, "GET", f"/v2/accounts/{names[1]}/commands/same-id", token=TRADER)
            self.stop_http()
            with patch("uta.sharding.ExchangeService", side_effect=AssertionError("parent cannot initialize financial services")):
                reopened = DurableProcessRouter(path, lease_seconds=.6, poll_interval=.01)
                self.start_http(reopened, *names)
            self.addCleanup(reopened.close)
            reopened.start()
            for account in names:
                receipt = self.terminal(account, "same-id")
                self.assertEqual((receipt["state"], receipt["account_id"]), ("SUCCEEDED", account))
            health = self.expect(200, "GET", "/v2/worker-health", token=RISK)
            pids = {item["pid"] for item in health["workers"]}
            self.assertEqual(len(pids), 2)
            self.assertNotIn(os.getpid(), pids)
            # No client-ID control contract exists for router fanout yet.
            with patch.object(reopened, "set_kill_switch", side_effect=AssertionError("sync control fallback forbidden")):
                self.expect(501, "POST", "/v2/control/halt", {"command_id": "h", "enabled": True}, token=RISK)


if __name__ == "__main__":
    unittest.main()
