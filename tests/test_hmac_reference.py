"""Independent defensive protocol checks over actual verified synthetic TLS.

The client builds canonical bytes and MACs itself. No production signing helper,
successful financial response, TLS handshake or nonce acceptance is mocked.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from fractions import Fraction as F
import hashlib
import hmac
from http.client import HTTPResponse, HTTPSConnection
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
from time import monotonic, sleep
import unittest

from uta.durable_commands import QueueStore
from uta.durable_gateway import make_server, producer_binding
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.request_signing import NonceStore, RequestAuthenticator, SigningError, SigningKey, SigningProfile
from uta.service import ExchangeService
from uta.storage import Database
from uta.writer_fence import WriterFence


AUTH_NOW = 1_700_000_000_000


def independent_headers(profile, key_id, *, method, target, body=b'', nonce=None, timestamp=AUTH_NOW):
    nonce = nonce or secrets.token_urlsafe(24)
    key = next(key for key in profile.keys if key.key_id == key_id)
    canonical = json.dumps(['UTA-HMAC-SHA256', '1', profile.tenant_id, profile.audience,
        key_id, str(timestamp), nonce, method, target, hashlib.sha256(body).hexdigest()],
        ensure_ascii=True, separators=(',', ':')).encode('ascii')
    return {'Authorization': 'UTA-HMAC-SHA256', 'X-UTA-Version': '1',
        'X-UTA-Tenant': profile.tenant_id, 'X-UTA-Audience': profile.audience,
        'X-UTA-Key-Id': key_id, 'X-UTA-Timestamp-Ms': str(timestamp), 'X-UTA-Nonce': nonce,
        'X-UTA-Signature': hmac.new(key.secret, canonical, hashlib.sha256).hexdigest()}


def server_context(cert, key):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(cert, key)
    return context


def serve_old_profile(financial, auth_path, profile, cert, key, report, stop):
    queue = QueueStore(Database(financial))
    authenticator = RequestAuthenticator(NonceStore(auth_path), profile, clock_ms=lambda: AUTH_NOW)
    server = make_server(queue, port=0, auth_profile='hmac', authenticator=authenticator,
        tls_context=server_context(cert, key), request_timeout=.5)
    thread = Thread(target=server.serve_forever, kwargs={'poll_interval': .01})
    thread.start()
    try:
        report.send({'pid': os.getpid(), 'address': server.server_address})
        stop.wait(60)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(3)
        report.close()


class IndependentHMACProtocolTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.financial = self.directory / 'financial.sqlite3'
        self.auth_path = self.directory / 'authentication.sqlite3'
        self.database = Database(self.financial)
        bootstrap = ExchangeService(self.database, {'USD': 8}, max_price_age=timedelta(seconds=30))
        bootstrap.create_account('alice')
        bootstrap.create_account('bob')
        bootstrap.deposit('alice', 'synthetic-capital', 'USD', D('10.04'))
        bootstrap.publish_market(MarketSnapshot(1, datetime.now(timezone.utc),
            {'USD': AssetSpec(D(1), D(1))}, {'X': InstrumentSpec(D(100), D('.1'), D('.05'))}))
        bootstrap.set_kill_switch(False)
        self.queue = QueueStore(self.database, initialize=True)
        self.fence = WriterFence(self.database)
        self.fence.enable('independent-hmac-authority')
        self.store = NonceStore.initialize(self.auth_path, tenant_id='tenant-a', producer_binding=producer_binding(self.queue))
        self.keys = (SigningKey('alice', b'A' * 32, 'trader', 'alice', 0, AUTH_NOW + 1_000_000),
                     SigningKey('bob', b'B' * 32, 'trader', 'bob', 0, AUTH_NOW + 1_000_000),
                     SigningKey('reader', b'R' * 32, 'reader', 'alice', 0, AUTH_NOW + 1_000_000),
                     SigningKey('risk', b'K' * 32, 'risk', None, 0, AUTH_NOW + 1_000_000))
        self.profile = SigningProfile('tenant-a', self.store.audience, 1, self.keys)
        self.auth = RequestAuthenticator(self.store, self.profile, clock_ms=lambda: AUTH_NOW)
        executable = shutil.which('openssl')
        self.assertIsNotNone(executable, 'actual TLS verification requires the certificate generator; do not skip')
        self.cert, self.key = self.directory / 'certificate.pem', self.directory / 'tls-private.pem'
        subprocess.run([executable, 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
            '-keyout', str(self.key), '-out', str(self.cert), '-days', '1', '-subj', '/CN=localhost',
            '-addext', 'subjectAltName=DNS:localhost,IP:127.0.0.1'], capture_output=True, check=True, timeout=10)
        self.key.chmod(0o600)
        self.client_context = ssl.create_default_context(cafile=str(self.cert))
        self.assertTrue(self.client_context.check_hostname)
        self.assertEqual(self.client_context.verify_mode, ssl.CERT_REQUIRED)
        self.children = []
        self.server = None
        self.addCleanup(self.cleanup_servers)

    def start_http(self):
        self.server = make_server(self.queue, port=0, auth_profile='hmac', authenticator=self.auth,
            tls_context=server_context(self.cert, self.key), request_timeout=.5)
        self.thread = Thread(target=self.server.serve_forever, kwargs={'poll_interval': .01})
        self.thread.start()
        return self.server.server_address

    def stop_http(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(3)
            self.assertFalse(self.thread.is_alive())
            self.server = None

    def child(self):
        context = multiprocessing.get_context('spawn')
        stop = context.Event()
        receive, send = context.Pipe(duplex=False)
        process = context.Process(target=serve_old_profile, args=(str(self.financial), str(self.auth_path),
            self.profile, str(self.cert), str(self.key), send, stop))
        process.start()
        send.close()
        self.children.append((process, stop))
        self.assertTrue(receive.poll(8), 'actual TLS HTTP child did not become ready')
        report = receive.recv()
        receive.close()
        self.assertNotEqual(report['pid'], os.getpid())
        return process, stop, tuple(report['address'])

    def stop_child(self, process, stop):
        stop.set()
        process.join(5)
        if process.is_alive():
            process.kill()
            process.join(5)
        self.assertEqual(process.exitcode, 0)
        self.children.remove((process, stop))

    def cleanup_servers(self):
        self.stop_http()
        for process, stop in list(self.children):
            self.stop_child(process, stop)

    def body(self, command='command', order='order'):
        return json.dumps(dict(command_id=command, order_id=order, symbol='X', quantity='1', limit_price='100'),
                          separators=(',', ':')).encode()

    def request(self, address, method, target, *, body=b'', headers=None, key='alice', profile=None):
        headers = headers or independent_headers(profile or self.profile, key, method=method, target=target, body=body)
        connection = HTTPSConnection(*address, context=self.client_context, timeout=4)
        try:
            connection.request(method, target, body=body, headers={'Content-Type': 'application/json', **headers})
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def wire(self, address, method, target, body, headers, *, duplicate=None, read=True):
        fields = [('Host', 'localhost'), ('Content-Type', 'application/json'), ('Content-Length', str(len(body))), *headers.items()]
        if duplicate:
            fields.append((duplicate, headers[duplicate] if duplicate in headers else str(len(body))))
        data = (method + ' ' + target + ' HTTP/1.1\r\n' + ''.join(name + ': ' + value + '\r\n' for name, value in fields) + '\r\n').encode('ascii') + body
        with socket.create_connection(address, timeout=4) as raw:
            with self.client_context.wrap_socket(raw, server_hostname='localhost') as client:
                self.assertIn(client.version(), ('TLSv1.2', 'TLSv1.3'))
                client.sendall(data)
                if read:
                    response = HTTPResponse(client)
                    response.begin()
                    return response.status, json.loads(response.read())

    def queued_count(self):
        with self.database.read_transaction() as connection:
            return connection.execute('SELECT COUNT(*) FROM uta_command_inbox').fetchone()[0]

    def test_verified_tls_domain_account_and_role_isolation_never_enqueue_denied_requests(self):
        address = self.start_http()
        target, body = '/v2/accounts/alice/orders', self.body()
        untrusted = HTTPSConnection(*address, context=ssl.create_default_context(), timeout=4)
        try:
            with self.assertRaises(ssl.SSLCertVerificationError):
                untrusted.request('POST', target, body=body)
        finally:
            untrusted.close()
        self.assertEqual(self.queued_count(), 0)
        for changed in (replace(self.profile, tenant_id='tenant-b'), replace(self.profile, audience='uta:wrong-deployment')):
            status, rejected = self.request(address, 'POST', target, body=body, profile=changed)
            self.assertEqual((status, rejected['error']['code']), (401, 'invalid_signature'))
        for other, key in (('/v2/accounts/bob/orders', 'alice'), (target, 'reader')):
            self.assertEqual(self.request(address, 'POST', other, body=body, key=key)[0], 403)
        self.assertEqual(self.queued_count(), 0)
        status, queued = self.request(address, 'POST', target, body=body)
        self.assertEqual((status, queued['state']), (202, 'PENDING'))
        status, denied = self.request(address, 'GET', queued['status_url'], key='bob')
        self.assertEqual(status, 403)
        self.assertNotIn('result', denied)
        self.assertEqual(self.request(address, 'GET', '/v2/metrics', key='alice')[0], 403)
        self.assertEqual(self.queued_count(), 1)

    def test_duplicate_signed_headers_and_framing_are_rejected_over_actual_tls(self):
        address = self.start_http()
        target, body = '/v2/accounts/alice/orders', self.body('duplicate')
        for name in ('Authorization', 'X-UTA-Version', 'X-UTA-Tenant', 'X-UTA-Audience', 'X-UTA-Key-Id',
                     'X-UTA-Timestamp-Ms', 'X-UTA-Nonce', 'X-UTA-Signature'):
            with self.subTest(header=name):
                headers = independent_headers(self.profile, 'alice', method='POST', target=target, body=body)
                status, rejected = self.wire(address, 'POST', target, body, headers, duplicate=name)
                expected = (400, 'duplicate_header') if name == 'Authorization' else (401, 'signature_required')
                self.assertEqual((status, rejected['error']['code']), expected)
        headers = independent_headers(self.profile, 'alice', method='POST', target=target, body=body)
        self.assertEqual(self.wire(address, 'POST', target, body, headers, duplicate='Content-Length')[0], 400)
        self.assertEqual(self.queued_count(), 0)
        with self.store.database.read_transaction() as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM auth_nonces').fetchone()[0], 0)

    def test_exact_body_method_and_raw_target_are_bound_without_consuming_invalid_mac_nonce(self):
        address = self.start_http()
        target, body = '/v2/accounts/alice/orders', self.body('exact-bytes')
        headers = independent_headers(self.profile, 'alice', method='POST', target=target, body=body)
        for method, path, actual in (('POST', target, body + b' '), ('PUT', target, body),
                                     ('POST', '/v2/accounts/bob/orders', body)):
            with self.subTest(method=method, path=path, body_changed=actual != body):
                status, result = self.request(address, method, path, body=actual, headers=headers)
                self.assertEqual((status, result['error']['code']), (401, 'invalid_signature'))
        self.assertEqual(self.queued_count(), 0)
        with self.store.database.read_transaction() as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM auth_nonces').fetchone()[0], 0)
        self.assertEqual(self.request(address, 'POST', target, body=body, headers=headers)[0], 202)
        self.assertEqual(self.queued_count(), 1)

    def test_real_tls_lost_reply_new_nonce_same_command_recovers_after_http_pid_restart_once(self):
        process, stop, address = self.child()
        target, body = '/v2/accounts/alice/orders', self.body('unknown-wire', 'original-order')
        headers = independent_headers(self.profile, 'alice', method='POST', target=target, body=body)
        self.wire(address, 'POST', target, body, headers, read=False)
        deadline = monotonic() + 5
        while self.queue.status('unknown-wire') is None and monotonic() < deadline:
            sleep(.01)
        original = self.queue.status('unknown-wire')
        self.assertIsNotNone(original, 'wire request must actually have durable effects before restart')
        self.assertEqual(original['state'], 'PENDING')
        self.stop_child(process, stop)
        restarted, stop2, address2 = self.child()
        self.assertNotEqual(restarted.pid, process.pid)
        status, replay = self.request(address2, 'POST', target, body=body, headers=headers)
        self.assertEqual((status, replay['error']['code']), (409, 'request_replayed'))
        status, recovered = self.request(address2, 'POST', target, body=body)
        self.assertEqual((status, recovered['command_id'], recovered['sequence']),
                         (202, original['command_id'], original['sequence']))
        self.assertEqual(self.queued_count(), 1)
        token = self.fence.acquire('independent-financial-worker', 30)
        try:
            exchange = ExchangeService(self.database.for_writer(token), {'USD': 8}, max_price_age=timedelta(seconds=30))
            terminal = self.queue.process_one(exchange)
            self.assertEqual(terminal['state'], 'SUCCEEDED')
            self.assertEqual(F(exchange.account('alice')['open_order_margin']), F('10.04'))
            self.assertEqual(self.request(address2, 'POST', target, body=body)[1]['result'], terminal['result'])
            with self.database.read_transaction() as connection:
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM uta_orders').fetchone()[0], 1)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_events WHERE event_type='ORDER_ACCEPTED'").fetchone()[0], 1)
        finally:
            self.fence.release(token)

    def test_revocation_is_seen_by_old_http_process_and_profile_rollback_stays_rejected(self):
        process, stop, address = self.child()
        target = '/v2/accounts/alice/commands/unknown'
        self.assertEqual(self.request(address, 'GET', target)[0], 404)  # Valid auth, absent command.
        revoked = replace(self.profile, revision=2, keys=tuple(key for key in self.keys if key.key_id != 'alice'))
        self.auth.replace_profile(revoked)
        status, result = self.request(address, 'POST', '/v2/accounts/alice/orders', body=self.body('revoked'))
        self.assertEqual((status, result['error']['code']), (401, 'signing_key_inactive'))
        self.assertTrue(process.is_alive())
        with self.assertRaises(ValueError):
            RequestAuthenticator(NonceStore(self.auth_path), self.profile, clock_ms=lambda: AUTH_NOW)
        with self.assertRaises(ValueError):
            self.auth.replace_profile(replace(self.profile, revision=3))
        self.assertEqual(self.queued_count(), 0)
        with self.store.database.read_transaction() as connection:
            self.assertEqual(connection.execute('SELECT revision FROM auth_config').fetchone()[0], 2)
            self.assertEqual(connection.execute("SELECT revoked FROM auth_keys WHERE key_id='alice'").fetchone()[0], 1)

    def test_two_independent_tls_http_processes_can_consume_a_nonce_only_once(self):
        first, _, address = self.child()
        second, _, address2 = self.child()
        self.assertNotEqual(first.pid, second.pid)
        target, body = '/v2/accounts/alice/orders', self.body('cross-process-race')
        headers = independent_headers(self.profile, 'alice', method='POST', target=target, body=body)
        barrier = Barrier(2)
        def attempt(location):
            barrier.wait(timeout=4)
            return self.request(location, 'POST', target, body=body, headers=headers)
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(attempt, (address, address2)))
        self.assertEqual(sorted(status for status, _ in responses), [202, 409])
        self.assertEqual(self.queued_count(), 1)
        with self.store.database.read_transaction() as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM auth_nonces').fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM auth_audit WHERE event='nonce_consumed'").fetchone()[0], 1)

    def test_real_auth_commit_failure_prevents_enqueue_and_rolls_back_nonce(self):
        address = self.start_http()
        with self.store.database.transaction() as connection:
            connection.execute('CREATE TABLE independent_parent(id TEXT PRIMARY KEY)')
            connection.execute('CREATE TABLE independent_guard(id TEXT REFERENCES independent_parent(id) DEFERRABLE INITIALLY DEFERRED)')
            connection.execute("CREATE TRIGGER independent_commit_failure AFTER INSERT ON auth_nonces BEGIN INSERT INTO independent_guard VALUES('missing'); END")
        target, body = '/v2/accounts/alice/orders', self.body('auth-commit')
        headers = independent_headers(self.profile, 'alice', method='POST', target=target, body=body)
        status, result = self.request(address, 'POST', target, body=body, headers=headers)
        self.assertEqual((status, result['error']['code']), (503, 'signing_store_unavailable'))
        self.assertEqual(self.queued_count(), 0)
        with self.store.database.read_transaction() as connection:
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM auth_nonces').fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM auth_audit WHERE event='nonce_consumed'").fetchone()[0], 0)
        with self.store.database.transaction() as connection:
            connection.execute('DROP TRIGGER independent_commit_failure')
        self.assertEqual(self.request(address, 'POST', target, body=body, headers=headers)[0], 202)
        self.assertEqual(self.queued_count(), 1)

    def test_auth_schema_loss_and_missing_database_never_recreate_or_enqueue(self):
        address = self.start_http()
        with self.store.database.transaction() as connection:
            connection.execute('DROP TRIGGER auth_audit_no_update')
        target, body = '/v2/accounts/alice/orders', self.body('broken-schema')
        status, result = self.request(address, 'POST', target, body=body)
        self.assertEqual((status, result['error']['code']), (503, 'signing_store_unavailable'))
        self.assertEqual(self.queued_count(), 0)
        self.auth_path.rename(self.directory / 'retained-auth.sqlite3')
        status, result = self.request(address, 'POST', target, body=self.body('missing-db'))
        self.assertEqual((status, result['error']['code']), (503, 'signing_store_unavailable'))
        self.assertFalse(self.auth_path.exists())
        self.assertEqual(self.queued_count(), 0)

    def test_nonce_exact_expiry_and_clock_highwater_survive_reopened_authenticator(self):
        store = NonceStore.initialize(self.directory / 'boundary.sqlite3', tenant_id='tenant-a',
            producer_binding=producer_binding(self.queue), past_window_ms=100, future_skew_ms=10)
        profile = replace(self.profile, audience=store.audience)
        now = [AUTH_NOW]
        auth = RequestAuthenticator(store, profile, clock_ms=lambda: now[0])
        target, nonce = '/v2/accounts/alice/commands/c', 'independent-fixed-nonce-000000001'
        headers = independent_headers(profile, 'alice', method='GET', target=target, nonce=nonce)
        auth.authenticate(headers, method='GET', request_target=target, body=b'')
        now[0] += 100
        with self.assertRaises(SigningError) as replay:
            auth.authenticate(headers, method='GET', request_target=target, body=b'')
        self.assertEqual(replay.exception.code, 'request_replayed')
        now[0] += 1
        with self.assertRaises(SigningError) as expired:
            auth.authenticate(headers, method='GET', request_target=target, body=b'')
        self.assertEqual(expired.exception.code, 'request_timestamp_out_of_window')
        now[0] -= 1
        reopened = RequestAuthenticator(NonceStore(store.database.path), profile, clock_ms=lambda: now[0])
        with self.assertRaises(SigningError) as regressed:
            reopened.authenticate(headers, method='GET', request_target=target, body=b'')
        self.assertEqual(regressed.exception.code, 'auth_clock_regressed')
        self.assertEqual(self.queued_count(), 0)
