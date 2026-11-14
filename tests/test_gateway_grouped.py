"""Real HTTP grouped-admission results, scopes and graceful process draining."""
from datetime import datetime, timezone
from decimal import Decimal as D
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import selectors
import signal
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Event, Thread
import time
import unittest
from unittest.mock import patch

import uta
from uta.admission import AdmissionBatcher
from uta.gateway import Credential, make_server
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ExchangeService, ServiceError
from uta.storage import Database


ADMIN, ALICE, BOB, READER = (letter * 43 for letter in "ABCR")
SOURCE = Path(uta.__file__).resolve().parent.parent


def request_at(address, method, path, payload=None, token=ADMIN):
    body = None if payload is None else json.dumps(payload)
    headers = {"Authorization": "Bearer " + token}
    if body is not None:
        headers["Content-Type"] = "application/json"
    connection = HTTPConnection(*address, timeout=4)
    try:
        connection.request(method, path, body, headers)
        response = connection.getresponse()
        return response.status, json.loads(response.read())
    finally:
        connection.close()


class GroupedGatewayTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "exchange.sqlite3"
        self.now = datetime(2026, 11, 14, tzinfo=timezone.utc)
        self.exchange = ExchangeService(Database(self.path), {"USD": 8}, clock=lambda: self.now)
        self.exchange.publish_market(MarketSnapshot(1, self.now, {"USD": AssetSpec(D(1), D(1))},
            {"X": InstrumentSpec(D(100), D(".1"), D(".05"))}))
        for account in ("alice", "bob"):
            self.exchange.create_account(account)
            self.exchange.deposit(account, "fund", "USD", D(1000))
        self.exchange.set_kill_switch(False)
        self.admission = self.exchange.admission = AdmissionBatcher(self.exchange,
            max_batch_size=8, max_delay_ms=2, queue_capacity=1)
        self.addCleanup(self.admission.close)
        self.server = make_server(self.exchange, port=0, admission_timeout=.05,
            credentials=(Credential(ADMIN, "admin"), Credential(ALICE, "trader", "alice"),
                         Credential(BOB, "trader", "bob"), Credential(READER, "reader", "alice")))
        self.thread = Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self):
        if self.thread.is_alive():
            self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)

    def request(self, method, path, payload=None, *, token=ALICE):
        return request_at(self.server.server_address, method, path, payload, token)

    def order(self, identifier="order", **changes):
        return {"order_id": identifier, "symbol": "X", "quantity": "1", "limit_price": "100", **changes}

    def test_real_submit_cancel_and_response_loss_retry_preserve_one_business_effect(self):
        command = self.order()
        status, admitted = self.request("POST", "/v1/accounts/alice/orders", command)
        self.assertEqual(status, 201, admitted)
        events = self.exchange.events(limit=1000)
        status, retried = self.request("POST", "/v1/accounts/alice/orders", command)
        self.assertEqual((status, retried), (201, admitted))
        self.assertEqual(self.exchange.events(limit=1000), events)
        status, queried = self.request("GET", "/v1/accounts/alice/orders/order")
        self.assertEqual((status, queried), (200, admitted))
        status, cancelled = self.request("POST", "/v1/accounts/alice/orders/order/cancel", {})
        self.assertEqual(status, 200, cancelled)
        self.assertEqual(cancelled["status"], "CANCELLED")
        self.assertEqual(cancelled["reserved_margin"], "0")
        self.assertEqual(self.exchange.account("alice")["open_order_margin"], "0")
        self.admission.close()
        reopened = ExchangeService(Database(self.path), {"USD": 8}, clock=lambda: self.now)
        self.assertEqual(reopened.order("alice", "order")["status"], "CANCELLED")
        self.assertEqual(len([event for event in reopened.events(limit=1000)
                              if event["event_type"] == "ORDER_ACCEPTED"]), 1)

    def test_scope_and_input_rejections_never_enter_the_admission_queue(self):
        with patch.object(self.admission, "submit_order", wraps=self.admission.submit_order) as submit:
            cases = [("/v1/accounts/bob/orders", self.order(), ALICE, 403),
                     ("/v1/accounts/alice/orders", self.order(), READER, 403),
                     ("/v1/accounts/alice/orders", self.order(quantity=1), ALICE, 400),
                     ("/v1/accounts/alice/orders", self.order(reduce_only="false"), ALICE, 400)]
            for path, command, token, expected in cases:
                with self.subTest(path=path, token=token[:1]):
                    status, result = self.request("POST", path, command, token=token)
                    self.assertEqual(status, expected, result)
            self.assertEqual(submit.call_count, 0)
        self.assertEqual(self.exchange.orders("alice"), [])
        self.assertEqual(self.exchange.orders("bob"), [])

    def test_configured_catalog_and_margin_gates_are_preserved_through_grouped_http(self):
        from uta.examples import synthetic_policy
        catalog, rules = synthetic_policy()
        self.stop_server()
        self.admission.close()
        self.exchange = ExchangeService(Database(self.path.with_name("configured.sqlite3")),
            {"USD": 8, "BTC": 8}, clock=lambda: self.now, product_catalog=catalog, portfolio_rules=rules)
        self.exchange.create_account("alice")
        self.exchange.deposit("alice", "fund", "USD", D(1000))
        self.exchange.publish_market(MarketSnapshot(1, self.now,
            {"USD": AssetSpec(D(1), D(1)), "BTC": AssetSpec(D(100), D(".8"))},
            {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))}))
        self.exchange.set_kill_switch(False)
        self.admission = self.exchange.admission = AdmissionBatcher(self.exchange)
        self.addCleanup(self.admission.close)
        self.server = make_server(self.exchange, port=0, credentials=(Credential(ALICE, "trader", "alice"),))
        self.thread = Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        self.thread.start()
        invalid = self.order("tick-invalid", symbol="BTC-PERP", quantity="0.001")
        status, result = self.request("POST", "/v1/accounts/alice/orders", invalid)
        self.assertEqual(status, 409, result)
        self.assertEqual(self.exchange.orders("alice"), [])
        status, result = self.request("POST", "/v1/accounts/alice/orders", self.order("configured", symbol="BTC-PERP"))
        self.assertEqual(status, 201, result)
        risk = self.exchange.risk("alice")
        self.assertEqual((risk["rule_version"], risk["catalog_version"]), (rules.version, catalog.version))
        self.assertGreater(D(risk["open_order_margin"]), 0)

    def test_business_rejection_keeps_its_status_and_does_not_create_an_order(self):
        status, result = self.request("POST", "/v1/accounts/alice/orders", self.order(quantity="1000"))
        self.assertEqual(status, 409, result)
        self.assertEqual(result["error"]["code"], "insufficient_margin")
        self.assertEqual(self.exchange.orders("alice"), [])

    def block_admission(self, identifier):
        entered, release = Event(), Event()
        self.addCleanup(release.set)
        original = self.exchange._admit_order
        def blocked(connection, account_id, order_id, *args, **kwargs):
            if order_id == identifier:
                entered.set()
                if not release.wait(3):
                    raise RuntimeError("test failed to release admission")
            return original(connection, account_id, order_id, *args, **kwargs)
        return entered, release, patch.object(self.exchange, "_admit_order", side_effect=blocked)

    def test_wait_timeout_cancels_only_a_still_queued_command(self):
        entered, release, hold = self.block_admission("holding")
        with hold:
            first = self.admission.submit_order("alice", "holding", "X", D(1), D(100))
            self.assertTrue(entered.wait(2))
            status, result = self.request("POST", "/v1/accounts/alice/orders", self.order("queued"))
            self.assertEqual(status, 503, result)
            self.assertEqual(result["error"]["code"], "admission_queue_timeout")
            release.set()
            self.assertEqual(first.result(timeout=3)["order_id"], "holding")
        self.admission.close()
        self.assertEqual([row["order_id"] for row in self.exchange.orders("alice")], ["holding"])

    def test_running_timeout_reports_unknown_and_original_id_recovers_exactly_once(self):
        entered, release, hold = self.block_admission("running")
        with hold:
            status, result = self.request("POST", "/v1/accounts/alice/orders", self.order("running"))
            self.assertTrue(entered.is_set())
            self.assertEqual(status, 503, result)
            self.assertEqual(result["error"]["code"], "command_result_unknown")
            metrics_status, metrics = self.request("GET", "/metrics", token=ADMIN)
            self.assertEqual(metrics_status, 200, metrics)
            self.assertEqual(metrics["server_errors"], 1, "an unknown 503 outcome must remain visible as a server error")
            release.set()
            # Acquiring the authority transaction also waits for any in-flight
            # command's COMMIT. A timeout response is not a rejection receipt.
            admitted = self.exchange.order("alice", "running")
        status, retried = self.request("POST", "/v1/accounts/alice/orders", self.order("running"))
        self.assertEqual((status, retried), (201, admitted))
        self.assertEqual(len([event for event in self.exchange.events(limit=1000)
                              if event["event_type"] == "ORDER_ACCEPTED"]), 1)

    def test_queue_overload_is_explicit_and_has_no_business_effect(self):
        entered, release, hold = self.block_admission("holding")
        with hold:
            first = self.admission.submit_order("alice", "holding", "X", D(1), D(100))
            self.assertTrue(entered.wait(2))
            second = self.admission.submit_order("alice", "waiting", "X", D(1), D(100))
            status, result = self.request("POST", "/v1/accounts/alice/orders", self.order("overloaded"))
            self.assertEqual(status, 503, result)
            self.assertEqual(result["error"]["code"], "admission_overloaded")
            release.set()
            first.result(timeout=3)
            second.result(timeout=3)
        self.assertEqual({row["order_id"] for row in self.exchange.orders("alice")}, {"holding", "waiting"})

    def test_cancellation_keeps_its_reserved_capacity_when_the_submit_queue_is_full(self):
        self.exchange.submit_order("alice", "cancel-me", "X", D(1), D(100))
        self.server.admission_timeout = 2
        entered, release, hold = self.block_admission("holding")
        response = []
        with hold:
            first = self.admission.submit_order("alice", "holding", "X", D(1), D(100))
            self.assertTrue(entered.wait(2))
            second = self.admission.submit_order("alice", "waiting", "X", D(1), D(100))
            thread = Thread(target=lambda: response.append(self.request(
                "POST", "/v1/accounts/alice/orders/cancel-me/cancel", {})))
            thread.start()
            deadline = time.monotonic() + 1
            while self.admission.stats()["queued"] < 2 and time.monotonic() < deadline:
                time.sleep(.005)
            self.assertEqual(self.admission.stats()["queued"], 2,
                             "cancel was refused instead of using its bounded reserved slot")
            status, result = self.request("POST", "/v1/accounts/alice/orders", self.order("overloaded"))
            self.assertEqual((status, result["error"]["code"]), (503, "admission_overloaded"))
            release.set()
            first.result(timeout=3)
            second.result(timeout=3)
            thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(response[0][0], 200, response)
        self.assertEqual(response[0][1]["status"], "CANCELLED")
        self.assertEqual(self.exchange.order("alice", "cancel-me")["reserved_margin"], "0")

    def test_metrics_and_readiness_reflect_the_actual_batch_worker(self):
        status, ready = self.request("GET", "/readyz")
        self.assertEqual((status, ready["ready"]), (200, True))
        status, result = self.request("GET", "/metrics", token=ADMIN)
        self.assertEqual(status, 200, result)
        self.assertIs(result["admission"]["worker_alive"], True)
        self.assertEqual(self.request("GET", "/metrics", token=ALICE)[0], 403)
        self.admission.close()
        status, ready = self.request("GET", "/readyz")
        self.assertEqual(status, 503, ready)
        self.assertEqual(ready["admission_reason"], "admission_unavailable")

    def test_cleanup_still_closes_http_and_group_worker_if_risk_worker_stop_fails(self):
        from uta.__main__ import _drain_exchange
        class FailingWorker:
            def stop(self):
                raise RuntimeError("synthetic stop failure")
        future = self.admission.submit_order("alice", "before-stop", "X", D(1), D(100))
        self.server.shutdown()
        self.thread.join(2)
        with self.assertRaisesRegex(RuntimeError, "synthetic stop failure"):
            _drain_exchange(self.server, FailingWorker(), self.admission)
        self.assertEqual(self.server.fileno(), -1)
        self.assertFalse(self.admission.stats()["worker_alive"])
        self.assertFalse(self.admission.stats()["accepting"])
        self.assertEqual(future.result(timeout=1)["order_id"], "before-stop")


class GroupedCLITests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_invalid_grouping_bounds_fail_before_creating_financial_state(self):
        database = self.root / "never-created.sqlite3"
        for flag, value in (("--admission-batch-size", "0"), ("--admission-delay-ms", "nan"),
                            ("--admission-queue-capacity", "65537"), ("--admission-cancel-reserve", "4097"),
                            ("--admission-timeout", "inf")):
            with self.subTest(flag=flag):
                process = subprocess.run([sys.executable, "-m", "uta", "exchange", "--batch-admission",
                    "--database", str(database), "--credentials", str(self.root / "missing"), flag, value],
                    cwd=self.root, env={**os.environ, "PYTHONPATH": str(SOURCE)},
                    text=True, capture_output=True, timeout=5)
                self.assertEqual(process.returncode, 2, process.stderr)
                self.assertFalse(database.exists())

    def test_sigterm_drains_a_real_grouped_order_before_clean_exit(self):
        path = self.root / "exchange.sqlite3"
        exchange = ExchangeService(Database(path), {"USD": 8})
        exchange.create_account("alice")
        exchange.deposit("alice", "fund", "USD", D(1000))
        exchange.set_kill_switch(False)
        credentials = self.root / "credentials.json"
        credentials.write_text(json.dumps([{"token": ADMIN, "role": "admin"}]))
        credentials.chmod(0o600)
        process = subprocess.Popen([sys.executable, "-m", "uta", "exchange", "--batch-admission",
            "--admission-timeout", "10", "--database", str(path), "--credentials", str(credentials), "--port", "0"],
            cwd=self.root, env={**os.environ, "PYTHONPATH": str(SOURCE)},
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        def cleanup():
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)
        self.addCleanup(cleanup)
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            self.assertTrue(selector.select(timeout=5), "grouped CLI did not announce startup")
        line = process.stdout.readline()
        self.assertTrue(line, "startup failed before binding")
        banner = json.loads(line)
        self.assertTrue(banner["batch_admission"])
        address = ("127.0.0.1", banner["port"])
        market = MarketSnapshot(1, datetime.now(timezone.utc), {"USD": AssetSpec(D(1), D(1))},
                                {"X": InstrumentSpec(D(100), D(".1"), D(".05"))})
        self.assertEqual(request_at(address, "PUT", "/v1/market", json.loads(market.to_json()))[0], 200)
        connection = sqlite3.connect(path, isolation_level=None)
        self.addCleanup(connection.close)
        connection.execute("BEGIN IMMEDIATE")
        response, completed = [], Event()
        command = {"order_id": "sigterm", "symbol": "X", "quantity": "1", "limit_price": "100"}
        def send():
            try:
                response.append(request_at(address, "POST", "/v1/accounts/alice/orders", command))
            finally:
                completed.set()
        thread = Thread(target=send)
        self.addCleanup(lambda: (connection.rollback(), thread.join(5)))
        thread.start()
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            status, metrics = request_at(address, "GET", "/metrics")
            self.assertEqual(status, 200, metrics)
            if metrics["admission"]["running"]:
                break
            time.sleep(.005)
        else:
            self.fail("command never entered grouped execution")
        process.send_signal(signal.SIGTERM)
        with self.assertRaises(subprocess.TimeoutExpired):
            process.wait(timeout=.1)
        connection.commit()
        self.assertTrue(completed.wait(3), "in-flight grouped response was lost during drain")
        thread.join(1)
        self.assertEqual(response[0][0], 201, response)
        self.assertEqual(process.wait(timeout=5), 0)
        reopened = ExchangeService(Database(path), {"USD": 8})
        self.assertEqual(reopened.order("alice", "sigterm")["status"], "OPEN")
        self.assertEqual(len([event for event in reopened.events(limit=1000)
                              if event["event_type"] == "ORDER_ACCEPTED"]), 1)


if __name__ == "__main__":
    unittest.main()
