"""Actual HTTP and CLI opt-in controls for pure computation caches."""
from datetime import datetime, timezone
from decimal import Decimal as D
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from unittest.mock import patch

from uta.gateway import Credential, make_server
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ExchangeService
from uta.storage import Database


SOURCE = Path(__file__).resolve().parents[1]
ADMIN, RISK, READER, TRADER, FUNDING = (letter * 43 for letter in "AKRTF")


def request(address, token):
    connection = HTTPConnection(*address, timeout=3)
    try:
        connection.request("GET", "/metrics", headers={"Authorization": "Bearer " + token})
        response = connection.getresponse()
        return response.status, json.loads(response.read())
    finally:
        connection.close()


class KernelGatewayTests(unittest.TestCase):
    def test_metrics_observe_real_cache_work_and_keep_risk_permissions(self):
        with TemporaryDirectory() as directory:
            now = datetime.now(timezone.utc)
            service = ExchangeService(Database(Path(directory) / "exchange.sqlite3"), {"USD": 8},
                                      clock=lambda: now, reserve_cache_size=32, market_cache_size=2)
            service.create_account("alice")
            service.deposit("alice", "fund", "USD", D(1000))
            service.publish_market(MarketSnapshot(1, now, {"USD": AssetSpec(D(1), D(1))},
                {"X": InstrumentSpec(D(100), D(".1"), D(".05"))}))
            service.set_kill_switch(False)
            for order in ("one", "two"):
                service.submit_order("alice", order, "X", D(1), D(100))
            server = make_server(service, port=0, credentials=(Credential(ADMIN, "admin"),
                Credential(RISK, "risk"), Credential(READER, "reader", "alice"),
                Credential(TRADER, "trader", "alice"), Credential(FUNDING, "funding", "alice")))
            thread = Thread(target=server.serve_forever, kwargs={"poll_interval": .01})
            thread.start()
            try:
                status, data = request(server.server_address, RISK)
                self.assertEqual(status, 200, data)
                self.assertEqual(data["risk_cache"]["reserve"]["capacity"], 32)
                self.assertEqual(data["risk_cache"]["market"]["capacity"], 2)
                for name in ("reserve", "market"):
                    self.assertGreater(data["risk_cache"][name]["hits"], 0, data)
                    self.assertLessEqual(data["risk_cache"][name]["size"], data["risk_cache"][name]["capacity"])
                with patch.object(service, "reserve_cache_stats") as reserve_stats, \
                     patch.object(service, "market_cache_stats") as market_stats:
                    for token in (READER, TRADER, FUNDING):
                        self.assertEqual(request(server.server_address, token)[0], 403)
                    self.assertEqual(request(server.server_address, "")[0], 401)
                    reserve_stats.assert_not_called()
                    market_stats.assert_not_called()
                self.assertEqual(request(server.server_address, ADMIN)[0], 200)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(3)
            self.assertEqual(D(service.account("alice")["open_order_margin"]), D("20.08"))

    def test_invalid_cli_cache_bounds_do_not_create_financial_state(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "never-created.sqlite3"
            for flag, value in (("--reserve-cache-size", "-1"), ("--reserve-cache-size", "65537"),
                                ("--market-cache-size", "-1"), ("--market-cache-size", "65")):
                with self.subTest(flag=flag, value=value):
                    result = subprocess.run([sys.executable, "-m", "uta", "exchange", "--database",
                        str(target), "--credentials", str(root / "missing"), flag, value], cwd=root,
                        env={**os.environ, "PYTHONPATH": str(SOURCE)}, capture_output=True, text=True, timeout=5)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertIn("invalid cache bounds", result.stderr)
                    self.assertFalse(target.exists())

    def test_cli_defaults_and_opt_in_are_visible_in_actual_service_metrics(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            credentials = root / "credentials.json"
            credentials.write_text(json.dumps([{"token": ADMIN, "role": "admin"}]))
            credentials.chmod(0o600)
            for reserve, market in ((0, 0), (32, 2)):
                with self.subTest(reserve=reserve, market=market):
                    args = [sys.executable, "-m", "uta", "exchange", "--database",
                        str(root / (str(reserve) + ".sqlite3")), "--credentials", str(credentials), "--port", "0"]
                    if reserve:
                        args += ["--reserve-cache-size", str(reserve), "--market-cache-size", str(market)]
                    process = subprocess.Popen(args, cwd=root, env={**os.environ, "PYTHONPATH": str(SOURCE)},
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    try:
                        with selectors.DefaultSelector() as selector:
                            selector.register(process.stdout, selectors.EVENT_READ)
                            self.assertTrue(selector.select(timeout=5), "service did not announce startup")
                        line = process.stdout.readline()
                        self.assertTrue(line, "service exited before binding")
                        banner = json.loads(line)
                        status, metrics = request(("127.0.0.1", banner["port"]), ADMIN)
                        self.assertEqual(status, 200, metrics)
                        self.assertEqual(metrics["risk_cache"]["reserve"]["capacity"], reserve)
                        self.assertEqual(metrics["risk_cache"]["market"]["capacity"], market)
                        process.send_signal(signal.SIGTERM)
                        self.assertEqual(process.wait(timeout=5), 0)
                    finally:
                        if process.poll() is None:
                            process.kill()
                        process.communicate(timeout=5)
