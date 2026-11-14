"""Exercise operator entry points and a real service process lifecycle."""
import json
import os
from pathlib import Path
import selectors
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.request import Request, urlopen

import uta
from uta.__main__ import _scales


SOURCE = Path(uta.__file__).resolve().parent.parent


class CLITests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.environment = dict(os.environ, PYTHONPATH=str(SOURCE))

    def run_cli(self, *arguments):
        return subprocess.run([sys.executable, "-m", "uta", *arguments],
                              cwd=self.root, env=self.environment, capture_output=True,
                              text=True, timeout=15)

    def test_default_and_explicit_asset_scales(self):
        self.assertEqual(_scales(None), {"USD": 8})
        self.assertEqual(_scales([]), {"USD": 8})
        self.assertEqual(_scales(["USD=0", "BTC=18"]), {"USD": 0, "BTC": 18})
        for entries in (["USD=8", "USD=8"], ["BTC=8"], ["USD=-1"], ["USD=19"],
                        ["USD=８"], ["USD=8=1"], ["USD"], ["USD="], ["=8"],
                        [" USD=8"], ["USD=8", " bad=8"], ["USD=8", "bad/asset=8"]):
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                _scales(entries)

    def test_help_and_demo_work_outside_repository(self):
        help_result = self.run_cli("--help")
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("exchange", help_result.stdout)
        self.assertIn("acceptance", help_result.stdout)
        demo = self.run_cli("demo")
        self.assertEqual(demo.returncode, 0, demo.stderr)
        document = json.loads(demo.stdout)
        self.assertEqual(document["risk"]["equity"], "1100")

    def test_acceptance_is_repeatable_without_network_or_persistent_customer_state(self):
        for _ in range(2):
            result = self.run_cli("acceptance")
            self.assertEqual(result.returncode, 0, result.stderr)
            document = json.loads(result.stdout)
            self.assertEqual(document["status"], "passed")
            self.assertGreater(document["ledger_events"], 0)
            self.assertGreater(document["outbox_events"], 0)
            self.assertTrue(document["checks"])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_invalid_cli_configuration_does_not_create_financial_database(self):
        database = self.root / "state.sqlite3"
        for arguments in (
            ("exchange", "--database", str(database)),
            ("exchange", "--database", str(database), "--credentials", str(self.root / "missing")),
            ("exchange", "--database", str(database), "--credentials", str(self.root / "missing"),
             "--asset-scale", "USD=19"),
            ("demo", "--port", "65536"),
        ):
            with self.subTest(arguments=arguments):
                result = self.run_cli(*arguments)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertFalse(database.exists())

    @unittest.skipUnless(os.name == "posix", "POSIX service signal lifecycle")
    def test_sigterm_drains_an_admitted_http_request_before_clean_exit(self):
        secret = "A" * 43
        credentials = self.root / "credentials.json"
        credentials.write_text(json.dumps([{"token": secret, "role": "admin"}]), encoding="utf-8")
        credentials.chmod(0o600)
        process = subprocess.Popen(
            [sys.executable, "-m", "uta", "exchange", "--database", str(self.root / "state.sqlite3"),
             "--credentials", str(credentials), "--port", "0"],
            cwd=self.root, env=self.environment, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True,
        )

        def cleanup():
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)

        self.addCleanup(cleanup)
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            self.assertTrue(selector.select(timeout=5), "exchange did not report startup within 5 seconds")
        line = process.stdout.readline()
        if not line:
            process.wait(timeout=5)
            self.fail("exchange startup failed: " + process.stderr.read())
        port = json.loads(line)["port"]
        connection = socket.create_connection(("127.0.0.1", port), timeout=2)
        self.addCleanup(connection.close)
        connection.sendall((
            "POST /v1/accounts HTTP/1.1\r\nHost: localhost\r\n"
            f"Authorization: Bearer {secret}\r\n"
            "Content-Type: application/json\r\nContent-Length: 2\r\n\r\n"
        ).encode("ascii"))
        # Ensure the handler has admitted the incomplete body. This metrics
        # request itself accounts for one request, the stalled POST for another.
        deadline = time.monotonic() + 2
        while True:
            request = Request(f"http://127.0.0.1:{port}/metrics",
                              headers={"Authorization": f"Bearer {secret}"})
            with urlopen(request, timeout=2) as response:
                metrics = json.load(response)
            if metrics["requests"] >= 2:
                break
            if time.monotonic() >= deadline:
                self.fail("HTTP request was not admitted before SIGTERM")
            time.sleep(0.01)
        process.send_signal(signal.SIGTERM)
        with self.assertRaises(subprocess.TimeoutExpired):
            process.wait(timeout=0.1)
        # Let the admitted handler finish; its invalid business payload returns
        # 400, and the server must then drain it and exit normally, not -SIGTERM.
        connection.sendall(b"{}")
        response = connection.recv(4096)
        self.assertIn(b"400", response.split(b"\r\n", 1)[0])
        self.assertEqual(process.wait(timeout=5), 0)


if __name__ == "__main__":
    unittest.main()
