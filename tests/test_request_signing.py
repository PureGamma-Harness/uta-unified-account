"""Synthetic HMAC keys, durable nonce races and actual HTTP/TLS requests."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal as D
from http.client import HTTPConnection, HTTPSConnection
import base64
import hashlib
import hmac
import json
import multiprocessing
import os
from pathlib import Path
import secrets
import shutil
import socket
import ssl
import sqlite3
import subprocess
from tempfile import TemporaryDirectory
from threading import Barrier, Thread
from time import monotonic, sleep, time_ns
import unittest

from uta.durable_commands import QueueStore
from uta.durable_gateway import make_server, producer_binding
from uta.gateway import Credential
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.request_signing import (NonceStore, RequestAuthenticator, SigningError, SigningKey,
                                 SigningProfile, canonical_request, load_profile, sign_headers)
from uta.service import ExchangeService
from uta.storage import Database
from uta.writer_fence import WriterFence


NOW = 1000000
SECRET = b"synthetic-signing-key-material-32bytes!"


def _request(address, method, target, body=b"", headers=None, tls=False):
    connection = (HTTPSConnection(*address, context=ssl._create_unverified_context(), timeout=3)
                  if tls else HTTPConnection(*address, timeout=3))
    try:
        options = {"Content-Type": "application/json", **(headers or {})}
        connection.request(method, target, body=body, headers=options)
        response = connection.getresponse()
        return response.status, json.loads(response.read())
    finally:
        connection.close()


def _signed_http_child(financial_path, auth_path, profile, report, stop):
    queue = QueueStore(Database(financial_path))
    authenticator = RequestAuthenticator(NonceStore(auth_path), profile, clock_ms=lambda: NOW)
    server = make_server(queue, port=0, auth_profile="hmac", authenticator=authenticator, require_tls=False)
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": .01})
    thread.start()
    try:
        report.send({"pid": os.getpid(), "port": server.server_port})
        stop.wait(10)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(3)
        report.close()


class SigningStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.store = NonceStore.initialize(self.root / "auth.sqlite3", tenant_id="tenant-a",
            producer_binding="1" * 64, past_window_ms=100, future_skew_ms=10)
        self.key = SigningKey("alice-v1", SECRET, "trader", "alice", 0, NOW + 10000)
        self.profile = SigningProfile("tenant-a", self.store.audience, 1, (self.key,))
        self.now = NOW
        self.auth = RequestAuthenticator(self.store, self.profile, clock_ms=lambda: self.now)

    def signed(self, *, profile=None, key_id="alice-v1", nonce=None, timestamp=None, target="/v2/accounts/alice/commands/c", method="GET", body=b""):
        return sign_headers(profile or self.profile, key_id, timestamp_ms=self.now if timestamp is None else timestamp,
                            nonce=nonce or secrets.token_urlsafe(24), method=method, request_target=target, body=body)

    def authenticate(self, headers, *, auth=None, target="/v2/accounts/alice/commands/c", method="GET", body=b""):
        return (auth or self.auth).authenticate(headers, method=method, request_target=target, body=body)

    def code(self, expected, headers, **options):
        with self.assertRaises(SigningError) as raised:
            self.authenticate(headers, **options)
        self.assertEqual(raised.exception.code, expected)

    def test_canonical_vector_covers_version_key_domain_time_nonce_method_raw_target_and_exact_body(self):
        body = b'{"quantity":"1.00"}'
        fields = dict(tenant_id="tenant-a", audience=self.store.audience, key_id="alice-v1",
            timestamp_ms=NOW, nonce="n" * 32, method="POST", request_target="/v2/accounts/alice/orders?b=2&a=1", body=body)
        expected = json.dumps(["UTA-HMAC-SHA256", "1", "tenant-a", self.store.audience, "alice-v1", str(NOW),
            "n" * 32, "POST", "/v2/accounts/alice/orders?b=2&a=1", hashlib.sha256(body).hexdigest()], separators=(",", ":")).encode()
        self.assertEqual(canonical_request(**fields), expected)
        header = self.signed(nonce="n" * 32, method="POST", target=fields["request_target"], body=body)
        self.assertEqual(header["X-UTA-Signature"], hmac.new(SECRET, expected, hashlib.sha256).hexdigest())
        for changed in ({"method": "PUT"}, {"target": "/v2/accounts/alice/orders?a=1&b=2"}, {"body": body + b" "}):
            self.code("invalid_signature", header, method=changed.get("method", "POST"), target=changed.get("target", fields["request_target"]), body=changed.get("body", body))
        for name, value in (("X-UTA-Version", "2"), ("X-UTA-Key-Id", "other"),
                            ("X-UTA-Timestamp-Ms", str(NOW + 1)), ("X-UTA-Nonce", "z" * 32),
                            ("X-UTA-Audience", "different"), ("X-UTA-Tenant", "tenant-b")):
            with self.assertRaises(SigningError):
                self.authenticate({**header, name: value}, method="POST", target=fields["request_target"], body=body)

    def test_nonce_survives_restart_and_cannot_be_pruned_at_exact_replay_boundary(self):
        header = self.signed(nonce="a" * 32)
        self.authenticate(header)
        restarted = RequestAuthenticator(NonceStore(self.root / "auth.sqlite3"), self.profile, clock_ms=lambda: self.now)
        self.code("request_replayed", header, auth=restarted)
        self.now += 100
        self.code("request_replayed", header)
        self.now += 1
        self.authenticate(self.signed())
        with self.store.database.read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM auth_nonces").fetchone()[0], 1)
        self.now = NOW
        self.code("auth_clock_regressed", header, auth=restarted)
        again = RequestAuthenticator(NonceStore(self.root / "auth.sqlite3"), self.profile, clock_ms=lambda: self.now)
        self.code("auth_clock_regressed", header, auth=again)

    def test_future_timestamp_keeps_nonce_for_its_full_window_and_rejects_skew(self):
        self.code("request_timestamp_out_of_window", self.signed(timestamp=NOW + 11))
        self.code("request_timestamp_out_of_window", self.signed(timestamp=NOW - 101))
        header = self.signed(timestamp=NOW + 10)
        self.authenticate(header)
        self.now = NOW + 110
        self.code("request_replayed", header)

    def test_rotation_revocation_expiry_and_tenant_domains_are_durable(self):
        old_process = RequestAuthenticator(NonceStore(self.root / "auth.sqlite3"), self.profile, clock_ms=lambda: self.now)
        second = SigningKey("alice-v2", b"other-synthetic-key-material-32-bytes", "trader", "alice", 0, NOW + 10000)
        both = replace(self.profile, revision=2, keys=(self.key, second))
        self.auth.replace_profile(both)
        self.authenticate(self.signed(profile=both, key_id=second.key_id))
        self.authenticate(self.signed(), auth=old_process)
        revoked = replace(both, revision=3, keys=(second,))
        self.auth.replace_profile(revoked)
        self.code("signing_key_inactive", self.signed(), auth=old_process)
        with self.assertRaises(ValueError):
            old_process.replace_profile(self.profile)
        with self.assertRaises(ValueError):
            self.auth.replace_profile(replace(revoked, revision=4, keys=(self.key, second)))
        with self.assertRaises(ValueError):
            self.auth.replace_profile(replace(revoked, revision=4, tenant_id="tenant-b"))
        self.now = second.expires_at_ms
        self.code("signing_key_inactive", self.signed(profile=revoked, key_id=second.key_id))

    def test_capacity_and_lost_database_fail_closed_without_memory_fallback(self):
        tiny = NonceStore.initialize(self.root / "tiny.sqlite3", tenant_id="tenant-a", producer_binding="1" * 64,
                                    past_window_ms=100, future_skew_ms=10, max_nonces=1)
        profile = replace(self.profile, audience=tiny.audience)
        auth = RequestAuthenticator(tiny, profile, clock_ms=lambda: self.now)
        first = self.signed(profile=profile)
        self.authenticate(first, auth=auth)
        self.code("signing_capacity_exhausted", self.signed(profile=profile), auth=auth)
        self.code("request_replayed", first, auth=auth)
        self.now += 101
        self.authenticate(self.signed(profile=profile), auth=auth)
        Path(tiny.database.path).rename(self.root / "lost.sqlite3")
        self.code("signing_store_unavailable", self.signed(profile=profile), auth=auth)
        self.assertFalse(Path(tiny.database.path).exists())

    def test_private_keyfile_and_audit_do_not_contain_secret_signature_body_or_raw_nonce(self):
        secret_text = base64.urlsafe_b64encode(SECRET).decode().rstrip("=")
        data = {"format": 1, "tenant_id": "tenant-a", "audience": self.store.audience, "revision": 1,
                "keys": [{"key_id": self.key.key_id, "secret_b64": secret_text, "role": "trader", "account_id": "alice",
                          "not_before_ms": 0, "expires_at_ms": self.key.expires_at_ms, "revoked": False}]}
        path = self.root / "keys.json"
        path.write_text(json.dumps(data)); path.chmod(0o600)
        self.assertEqual(load_profile(path), self.profile)
        self.assertNotIn(SECRET.decode(), repr(self.profile))
        path.chmod(0o640)
        with self.assertRaises(ValueError):
            load_profile(path)
        path.chmod(0o600)
        link = self.root / "link.json"; link.symlink_to(path)
        with self.assertRaises(OSError):
            load_profile(link)
        nonce, body = "nonce-never-store-plaintext-00000000", b"private-payload-marker"
        header = self.signed(nonce=nonce, method="POST", body=body)
        self.authenticate(header, method="POST", body=body)
        with self.store.database.read_transaction() as connection:
            persisted = repr([tuple(row) for table in ("auth_keys", "auth_nonces", "auth_audit") for row in connection.execute("SELECT * FROM " + table)])
        for sensitive in (SECRET.decode(), secret_text, nonce, body.decode(), header["X-UTA-Signature"]):
            self.assertNotIn(sensitive, persisted)

    def test_fresh_audiences_are_unique_and_copied_auth_authorities_fail_closed(self):
        second = NonceStore.initialize(self.root / "second.sqlite3", tenant_id="tenant-a", producer_binding="1" * 64)
        self.assertNotEqual(second.audience, self.store.audience)
        self.assertEqual(NonceStore(self.root / "auth.sqlite3").audience, self.store.audience)
        shutil.copy2(self.root / "auth.sqlite3", self.root / "copy.sqlite3")
        with self.assertRaises(SigningError) as raised:
            NonceStore(self.root / "copy.sqlite3")
        self.assertEqual(raised.exception.status, 503)
        # Even a correctly recomputed MAC for another tenant/deployment is not
        # valid here; this checks domain isolation beyond accidental tampering.
        foreign = replace(self.profile, tenant_id="tenant-b", audience=second.audience)
        self.code("invalid_signature", self.signed(profile=foreign))

    def test_duplicate_signature_headers_and_corrupt_store_are_rejected(self):
        from email.message import Message
        headers = self.signed()
        duplicate = Message()
        for name, value in headers.items():
            duplicate[name] = value
        duplicate["X-UTA-Nonce"] = headers["X-UTA-Nonce"]
        self.code("signature_required", duplicate)
        with sqlite3.connect(self.root / "auth.sqlite3") as connection:
            connection.execute("ALTER TABLE auth_audit RENAME COLUMN event TO unsupported_event")
        self.code("signing_store_unavailable", self.signed())

    def test_default_real_clock_serializes_concurrent_distinct_nonces_without_false_regression(self):
        store = NonceStore.initialize(self.root / "real-clock.sqlite3", tenant_id="tenant-a", producer_binding="1" * 64)
        observed = time_ns() // 1000000
        key = replace(self.key, not_before_ms=observed - 1000, expires_at_ms=observed + 60000)
        profile = SigningProfile("tenant-a", store.audience, 1, (key,))
        auth = RequestAuthenticator(store, profile)
        def authenticate(_):
            header = sign_headers(profile, key.key_id, timestamp_ms=time_ns() // 1000000,
                nonce=secrets.token_urlsafe(24), method="GET", request_target="/v2/accounts/alice/commands/c")
            return auth.authenticate(header, method="GET", request_target="/v2/accounts/alice/commands/c", body=b"")
        with ThreadPoolExecutor(max_workers=8) as workers:
            results = list(workers.map(authenticate, range(24)))
        self.assertTrue(all(result.account_id == "alice" for result in results))
        with store.database.read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM auth_nonces").fetchone()[0], 24)


class SignedHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.path = self.root / "financial.sqlite3"
        database = Database(self.path)
        exchange = ExchangeService(database, {"USD": 8})
        exchange.create_account("alice"); exchange.create_account("bob")
        exchange.deposit("alice", "fund", "USD", D(1000))
        exchange.publish_market(MarketSnapshot(1, datetime.now(timezone.utc), {"USD": AssetSpec(D(1), D(1))},
            {"X": InstrumentSpec(D(100), D(".1"), D(".05"))}))
        self.queue = QueueStore(database, initialize=True)
        WriterFence(database).enable("synthetic-signed-http")
        self.auth_path = self.root / "auth.sqlite3"
        self.store = NonceStore.initialize(self.auth_path, tenant_id="tenant-a", producer_binding=producer_binding(self.queue))
        self.keys = (SigningKey("alice", SECRET, "trader", "alice", 0, NOW + 10000),
                     SigningKey("reader", b"reader-synthetic-secret-material-32", "reader", "alice", 0, NOW + 10000),
                     SigningKey("risk", b"risk-synthetic-secret-material-32bytes", "risk", None, 0, NOW + 10000))
        self.profile = SigningProfile("tenant-a", self.store.audience, 1, self.keys)
        self.auth = RequestAuthenticator(self.store, self.profile, clock_ms=lambda: NOW)
        self.server = None
        self.children = []
        self.addCleanup(self.stop)

    def start(self, **options):
        self.server = make_server(self.queue, port=0, auth_profile="hmac", authenticator=self.auth,
                                  **({"require_tls": False} if not options else options))
        self.thread = Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01})
        self.thread.start()

    def stop(self):
        if self.server is not None:
            self.server.shutdown(); self.server.server_close(); self.thread.join(3)
            self.server = None
        for process, stop in self.children:
            stop.set(); process.join(5)
            if process.is_alive():
                process.kill(); process.join(5)
            self.assertEqual(process.exitcode, 0)
        self.children = []

    def headers(self, method, target, body=b"", *, key="alice", nonce=None):
        return sign_headers(self.profile, key, timestamp_ms=NOW, nonce=nonce or secrets.token_urlsafe(24),
                            method=method, request_target=target, body=body)

    def test_nonce_commit_precedes_enqueue_and_hmac_never_falls_back_to_bearer(self):
        self.start()
        target = "/v2/accounts/alice/orders"
        body = json.dumps({"command_id": "same-command", "order_id": "o", "symbol": "X", "quantity": "1", "limit_price": "100"}).encode()
        headers = self.headers("POST", target, body)
        status, queued = _request(self.server.server_address, "POST", target, body, headers)
        self.assertEqual((status, queued["state"], queued["ack"]), (202, "PENDING", "durably_queued"))
        self.assertEqual(_request(self.server.server_address, "POST", target, body, headers)[0], 409)
        # Lost-response recovery deliberately uses a NEW nonce with the SAME
        # durable command identity. Signature nonce and command ID differ.
        again = _request(self.server.server_address, "POST", target, body, self.headers("POST", target, body))[1]
        self.assertEqual(again, queued)
        self.assertEqual(_request(self.server.server_address, "GET", queued["status_url"], headers=self.headers("GET", queued["status_url"]))[0], 202)
        self.assertEqual(self.server.credentials, ())
        self.server.replace_credentials((Credential("B" * 43, "admin"),))
        self.assertEqual(_request(self.server.server_address, "GET", queued["status_url"], headers={"Authorization": "Bearer " + "B" * 43})[0], 401)
        connection = HTTPConnection(*self.server.server_address, timeout=3)
        try:
            connection.request("GET", queued["status_url"], headers={"Authorization": "Bearer " + "B" * 43})
            response = connection.getresponse()
            self.assertEqual(response.getheader("WWW-Authenticate"), 'UTA-HMAC-SHA256 realm="uta-v2"')
            response.read()
        finally:
            connection.close()
        self.assertEqual(_request(self.server.server_address, "POST", "/v2/accounts/bob/orders", body,
            self.headers("POST", "/v2/accounts/bob/orders", body))[0], 403)
        self.assertEqual(_request(self.server.server_address, "POST", target, body, self.headers("POST", target, body, key="reader"))[0], 403)
        with self.queue.database.read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_command_inbox").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_orders").fetchone()[0], 0)

    def test_auth_database_failure_prevents_enqueue_and_does_not_recreate_it(self):
        self.start()
        self.auth_path.rename(self.root / "removed.sqlite3")
        target = "/v2/accounts/alice/orders"
        body = json.dumps({"command_id": "never-enqueued", "order_id": "o", "symbol": "X", "quantity": "1", "limit_price": "100"}).encode()
        status, result = _request(self.server.server_address, "POST", target, body, self.headers("POST", target, body))
        self.assertEqual((status, result["error"]["code"]), (503, "signing_store_unavailable"))
        self.assertIsNone(self.queue.status("never-enqueued"))
        self.assertFalse(self.auth_path.exists())

    def test_real_lost_signed_response_and_http_restart_recover_with_new_nonce_same_command(self):
        self.start()
        target = "/v2/accounts/alice/orders"
        body = json.dumps({"command_id": "lost-response", "order_id": "lost", "symbol": "X", "quantity": "1", "limit_price": "100"}).encode()
        headers = self.headers("POST", target, body)
        request = ("POST " + target + " HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\n"
                   + f"Content-Length: {len(body)}\r\n" + "".join(name + ": " + value + "\r\n" for name, value in headers.items()) + "\r\n").encode() + body
        with socket.create_connection(self.server.server_address, timeout=3) as client:
            client.sendall(request)  # Close without reading any response.
        deadline = monotonic() + 3
        while self.queue.status("lost-response") is None:
            self.assertLess(monotonic(), deadline)
            sleep(.01)
        self.assertEqual(_request(self.server.server_address, "POST", target, body, headers)[0], 409)
        self.stop()
        self.auth = RequestAuthenticator(NonceStore(self.auth_path), self.profile, clock_ms=lambda: NOW)
        self.start()
        status_url = "/v2/accounts/alice/commands/lost-response"
        status, receipt = _request(self.server.server_address, "GET", status_url, headers=self.headers("GET", status_url))
        self.assertEqual(status, 202)
        self.assertEqual(_request(self.server.server_address, "POST", target, body, self.headers("POST", target, body))[1], receipt)
        with self.queue.database.read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_command_inbox").fetchone()[0], 1)

    def test_two_real_http_processes_compete_for_one_persistent_nonce(self):
        context = multiprocessing.get_context("spawn")
        addresses = []
        for _ in range(2):
            stop = context.Event()
            receive, send = context.Pipe(duplex=False)
            process = context.Process(target=_signed_http_child, args=(str(self.path), str(self.auth_path), self.profile, send, stop))
            process.start(); send.close()
            self.children.append((process, stop))
            self.assertTrue(receive.poll(5))
            report = receive.recv(); receive.close()
            self.assertNotEqual(report["pid"], os.getpid())
            addresses.append(("127.0.0.1", report["port"]))
        target = "/v2/accounts/alice/orders"
        body = json.dumps({"command_id": "raced", "order_id": "raced", "symbol": "X", "quantity": "1", "limit_price": "100"}).encode()
        headers = self.headers("POST", target, body)
        barrier = Barrier(2)
        def send(address):
            barrier.wait(timeout=3)
            return _request(address, "POST", target, body, headers)
        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(send, addresses))
        self.assertEqual(sorted(status for status, _ in responses), [202, 409])
        with self.store.database.read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM auth_nonces").fetchone()[0], 1)
        self.assertIsNotNone(self.queue.status("raced"))

    @unittest.skipUnless(shutil.which("openssl"), "synthetic TLS certificate generator")
    def test_hmac_production_factory_requires_tls_and_real_tls_request_succeeds(self):
        with self.assertRaises(ValueError):
            make_server(self.queue, port=0, auth_profile="hmac", authenticator=self.auth)
        other = NonceStore.initialize(self.root / "other-auth.sqlite3", tenant_id="tenant-a", producer_binding="2" * 64)
        wrong = RequestAuthenticator(other, replace(self.profile, audience=other.audience), clock_ms=lambda: NOW)
        with self.assertRaises(ValueError):
            make_server(self.queue, port=0, auth_profile="hmac", authenticator=wrong, require_tls=False)
        cert, key = self.root / "synthetic.crt", self.root / "synthetic.key"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(key),
                        "-out", str(cert), "-days", "1", "-subj", "/CN=synthetic.local"], capture_output=True, check=True)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert, key)
        self.start(tls_context=context)
        target = "/v2/worker-health"
        # A TCP client that never sends a TLS ClientHello must occupy only one
        # bounded worker, never stall SSL accept and every other connection.
        with socket.create_connection(self.server.server_address, timeout=3):
            status, observed = _request(self.server.server_address, "GET", target, headers=self.headers("GET", target, key="risk"), tls=True)
        self.assertEqual(status, 200)
        self.assertFalse(observed["writer"]["lease_active"])


if __name__ == "__main__":
    unittest.main()
