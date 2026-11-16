"""Actual CLI processes, native TLS/HMAC and restart; synthetic, unfunded data."""
import base64
from datetime import datetime, timezone
from decimal import Decimal as D
from http.client import HTTPSConnection
import json
import os
from pathlib import Path
import secrets
import select
import shutil
import signal
import socket
import ssl
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import monotonic, sleep, time_ns
import unittest

from uta.durable_commands import QueueStore
from uta.durable_process import DurableProcessRouter
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.request_signing import load_profile, sign_headers
from uta.storage import Database


ROOT = Path(__file__).resolve().parents[1]


class DurableCLITests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.directory = self.root / "managed"

    def command(self, operation, *options, expected=0, directory=None):
        result = subprocess.run([sys.executable, "-m", "uta.durable_cli", operation,
            "--directory", str(directory or self.directory), *map(str, options)],
            cwd=ROOT, text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, expected, result.stderr)
        output = result.stdout if expected in (0, 3, 4) else result.stderr
        return json.loads(output) if output.strip().startswith("{") else output

    def initialize(self):
        return self.command("init", "--asset-scale", "USD=2", "--max-price-age", "60")

    def tls_and_auth(self):
        executable = shutil.which("openssl")
        self.assertIsNotNone(executable, "native TLS lifecycle acceptance requires openssl")
        self.cert, self.key = self.root / "cert.pem", self.root / "key.pem"
        generated = subprocess.run([executable, "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-keyout", str(self.key), "-out", str(self.cert), "-days", "1", "-subj", "/CN=127.0.0.1",
            "-addext", "subjectAltName=IP:127.0.0.1"], capture_output=True, text=True, timeout=15)
        self.assertEqual(generated.returncode, 0, generated.stderr)
        self.cert.chmod(0o600)
        self.key.chmod(0o600)
        self.auth_db = self.root / "auth.sqlite3"
        initialized = self.command("auth-init", "--auth-db", self.auth_db, "--tenant", "synthetic-cli",
                                   "--past-window-ms", "300000")
        self.assertFalse(initialized["secret_generated"])
        with Database(self.auth_db).read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM auth_keys").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM auth_nonces").fetchone()[0], 0)
        now = time_ns() // 1000000
        keys = []
        for key_id, role, account, secret in (
            ("trader", "trader", "alice", b"synthetic-cli-trader-key-material-32!"),
            ("operator", "admin", None, b"synthetic-cli-operator-key-material!"),
        ):
            keys.append({"key_id": key_id, "role": role, "account_id": account,
                "secret_b64": base64.urlsafe_b64encode(secret).decode().rstrip("="),
                "not_before_ms": now - 10000, "expires_at_ms": now + 600000, "revoked": False})
        self.profile_path = self.root / "signing.json"
        self.profile_path.write_text(json.dumps({"format": 1, "tenant_id": "synthetic-cli",
            "audience": initialized["audience"], "revision": 1, "keys": keys}))
        self.profile_path.chmod(0o600)
        self.command("auth-configure", "--auth-db", self.auth_db, "--signing-profile", self.profile_path)
        self.profile = load_profile(self.profile_path)

    def serve_options(self):
        return ["--auth-db", str(self.auth_db), "--signing-profile", str(self.profile_path),
            "--tls-cert", str(self.cert), "--tls-key", str(self.key), "--port", "0",
            "--lease-seconds", ".6", "--poll-interval", ".01", "--background-interval", ".03",
            "--request-timeout", ".3"]

    def start(self):
        process = subprocess.Popen([sys.executable, "-m", "uta.durable_cli", "serve",
            "--directory", str(self.directory), *self.serve_options()], cwd=ROOT,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        def cleanup():
            if process.poll() is None:
                process.send_signal(signal.SIGTERM)
                try:
                    process.communicate(timeout=12)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate(timeout=5)
            else:
                process.communicate()
        self.addCleanup(cleanup)
        self.assertTrue(select.select([process.stdout], [], [], 12)[0], "CLI did not report listener binding")
        line = process.stdout.readline()
        if not line:
            self.fail(process.communicate(timeout=5)[1])
        observed = json.loads(line)
        self.assertEqual((observed["event"], observed["profile"], observed["tls"]), ("listening", "hmac-tls", True))
        self.assertEqual(observed["pid"], process.pid)
        self.assertNotEqual(process.pid, os.getpid())
        return process, observed["port"]

    def request(self, port, method, target, payload=None, *, key="operator", headers=None):
        body = b"" if payload is None else json.dumps(payload, separators=(",", ":")).encode()
        headers = headers or sign_headers(self.profile, key, timestamp_ms=time_ns() // 1000000,
            nonce=secrets.token_urlsafe(24), method=method, request_target=target, body=body)
        connection = HTTPSConnection("127.0.0.1", port, context=ssl.create_default_context(cafile=self.cert), timeout=4)
        try:
            connection.request(method, target, body=body, headers={"Content-Type": "application/json", **headers})
            response = connection.getresponse()
            return response.status, json.loads(response.read()), headers
        finally:
            connection.close()

    def eventually(self, check):
        deadline = monotonic() + 10
        while monotonic() < deadline:
            result = check()
            if result:
                return result
            sleep(.03)
        self.fail("real CLI/worker receipt did not reach the expected state")

    def test_init_is_empty_required_audit_and_inspect_is_not_a_writer(self):
        result = self.initialize()
        self.assertTrue(result["decision_audit_required"])
        shard = result["inspection"]["shards"][0]
        self.assertEqual([shard[key] for key in ("accounts", "orders", "positions", "ledger_sequence")], [0, 0, 0, 0])
        self.assertFalse(shard["lease_active"])
        plan = self.command("inspect")
        self.assertTrue(plan["state"]["halted"])
        self.assertEqual(plan["layout_hash"], result["inspection"]["layout_hash"])
        self.command("takeover", "--expected-layout-hash", "0" * 64, expected=2)
        self.assertEqual(self.command("inspect"), plan)
        self.assertEqual(self.command("query", "--command-id", "missing", "--account-id", "alice", expected=4)["error"]["code"], "command_not_found")

    def test_startup_validation_does_not_initialize_missing_authorities_or_auth(self):
        self.command("serve", expected=2)
        self.assertFalse(self.directory.exists())
        self.command("serve", "--profile", "bearer-development", expected=2)
        self.assertFalse(self.directory.exists())
        auth = self.root / "missing-auth.sqlite3"
        self.command("auth-configure", "--auth-db", auth, "--signing-profile", self.root / "missing-profile", expected=2)
        self.assertFalse(auth.exists())
        self.assertFalse(self.directory.exists())
        for option in (("--fee-rate", "NaN"), ("--asset-scale", "USD=1")):
            self.command("init", *option, expected=2)
            self.assertFalse(self.directory.exists())

    def test_failed_bind_preserves_nonce_state_and_never_starts_workers(self):
        self.initialize()
        self.tls_and_auth()
        with Database(self.auth_db).read_transaction() as connection:
            before = [tuple(row) for row in connection.execute("SELECT * FROM auth_audit")]
        with socket.socket() as blocker:
            blocker.bind(("127.0.0.1", 0))
            blocker.listen()
            options = self.serve_options()
            options[options.index("--port") + 1] = str(blocker.getsockname()[1])
            self.command("serve", *options, expected=2)
        with Database(self.auth_db).read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM auth_nonces").fetchone()[0], 0)
            self.assertEqual([tuple(row) for row in connection.execute("SELECT * FROM auth_audit")], before)
        report = self.command("inspect")
        self.assertFalse(report["shards"][0]["lease_active"])
        router = DurableProcessRouter(self.directory)
        self.addCleanup(router.close)
        with router._control.control.read_transaction() as connection:
            self.assertIsNone(connection.execute("SELECT 1 FROM sqlite_master WHERE name='router_process_owners'").fetchone())

    def test_actual_tls_hmac_sigterm_and_new_parent_preserve_pending_and_nonce(self):
        self.initialize()
        self.tls_and_auth()
        first, port = self.start()
        def health():
            status, body, headers = self.request(port, "GET", "/v2/worker-health")
            if status == 200 and body["workers"][0]["lease_active"]:
                return body, headers
        observed, replay_headers = self.eventually(health)
        code, rejected, _ = self.request(port, "GET", "/v2/worker-health",
            headers={"Authorization": "Bearer " + "development-token-is-not-a-hmac-key"})
        self.assertEqual((code, rejected["error"]["code"]), (401, "signature_required"))
        old_worker = observed["workers"][0]
        self.assertNotIn(old_worker["owner_pid"], (None, first.pid, os.getpid()))
        snapshot = MarketSnapshot(1, datetime.now(timezone.utc), {"USD": AssetSpec(D(1), D(1))},
            {"X": InstrumentSpec(D(100), D(".1"), D(".05"))})
        snapshot_file = self.root / "market.json"
        snapshot_file.write_text(snapshot.to_json())
        self.assertFalse(self.command("publish", "--snapshot-file", snapshot_file)["publishing"])
        self.assertFalse(self.command("activate")["halted"])
        code, queued, _ = self.request(port, "POST", "/v2/accounts/alice/orders",
            {"command_id": "client-order", "order_id": "order", "symbol": "X", "quantity": "1", "limit_price": "100"}, key="trader")
        self.assertEqual(code, 202)
        self.assertEqual(queued["ack"], "durably_queued")
        def terminal():
            status, result, _ = self.request(port, "GET", "/v2/accounts/alice/commands/client-order", key="trader")
            return result if status == 200 else None
        receipt = self.eventually(terminal)
        self.assertEqual((receipt["state"], receipt["error"]["code"]), ("REJECTED", "account_not_found"))
        first.send_signal(signal.SIGTERM)
        _, errors = first.communicate(timeout=12)
        self.assertEqual(first.returncode, 0, errors)
        router = DurableProcessRouter(self.directory)
        self.addCleanup(router.close)
        queue = router._queue(0)
        pending = queue.enqueue_cancel("alice", "offline-pending", "missing")
        self.assertEqual(pending["state"], "PENDING")
        second, second_port = self.start()
        self.assertNotEqual(first.pid, second.pid)
        def restarted():
            status, result, _ = self.request(second_port, "GET", "/v2/accounts/alice/commands/offline-pending", key="trader")
            return result if status == 200 else None
        self.assertEqual(self.eventually(restarted)["state"], "REJECTED")
        code, error, _ = self.request(second_port, "GET", "/v2/worker-health", headers=replay_headers)
        self.assertEqual((code, error["error"]["code"]), (409, "request_replayed"))
        after, _ = self.eventually(lambda: health_after(self, second_port))
        self.assertGreater(after["workers"][0]["generation"], old_worker["generation"])
        self.assertEqual(self.command("query", "--command-id", "client-order", "--account-id", "alice")["state"], "REJECTED")
        self.assertTrue(self.command("halt")["halted"])
        with router._database(0).read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT payload FROM uta_market").fetchone()[0], snapshot.to_json())
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_accounts").fetchone()[0], 0)
        second.send_signal(signal.SIGTERM)
        _, errors = second.communicate(timeout=12)
        self.assertEqual(second.returncode, 0, errors)


def health_after(case, port):
    status, body, headers = case.request(port, "GET", "/v2/worker-health")
    return (body, headers) if status == 200 and body["workers"][0]["lease_active"] else None


if __name__ == "__main__":
    unittest.main()
