"""Real private-keyfile/authDB tests; no financial source or endpoint wiring."""
import base64
import copy
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import pickle
import secrets
from tempfile import TemporaryDirectory
import time
import unittest

from uta.credit_hmac_source import CreditHmacSource, CreditSourceError
from uta.request_signing import (NonceStore, SigningError, SigningKey, SigningProfile,
                                 canonical_request, sign_headers)


def _fork_check(issuer, receipt, options, report):
    try:
        issuer.inspect(receipt, **options)
        report.send("unexpected_acceptance")
    except CreditSourceError as error:
        report.send(error.code)
    finally:
        report.close()


class CreditHmacSourceTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory(prefix="uta-credit-hmac-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.assertEqual(self.root.stat().st_mode & 0o777, 0o700)
        self.database = self.root / "auth.sqlite3"
        self.store = NonceStore.initialize(self.database, tenant_id="tenant-a",
            producer_binding="1" * 64, past_window_ms=5000, future_skew_ms=500)
        now = time.time_ns() // 1_000_000
        self.keys = tuple(SigningKey(key, secrets.token_bytes(32), role, account, now - 60000, now + 120000)
            for key, role, account in (("funding-alice", "funding", "alice"),
                ("funding-bob", "funding", "bob"), ("reader-alice", "reader", "alice"),
                ("trader-alice", "trader", "alice"), ("admin", "admin", None), ("risk", "risk", None)))
        self.profile = SigningProfile("tenant-a", self.store.audience, 1, self.keys)
        self.path = self.root / "keys.json"
        self.write_profile(self.profile)
        self.issuer = self.make_issuer()

    def write_profile(self, profile):
        document = {"format": 1, "tenant_id": profile.tenant_id, "audience": profile.audience,
            "revision": profile.revision, "keys": [{"key_id": key.key_id,
                "secret_b64": base64.urlsafe_b64encode(key.secret).decode("ascii").rstrip("="),
                "role": key.role, "account_id": key.account_id, "not_before_ms": key.not_before_ms,
                "expires_at_ms": key.expires_at_ms, "revoked": key.revoked} for key in profile.keys]}
        # Secrets exist only in this private temporary directory and process.
        descriptor = os.open(self.path, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w") as destination:
            json.dump(document, destination)

    def make_issuer(self, **changes):
        options = {"tenant_id": "tenant-a", "producer_binding": "1" * 64, "enabled": True,
            "grants": tuple((key.key_id, account) for key in self.keys for account in ("alice", "bob"))}
        options.update(changes)
        return CreditHmacSource(self.database, self.path, **options)

    def request(self, *, command_id="c1", amount="1.00", account="alice", key_id="funding-alice",
                profile=None, timestamp=None, nonce=None, method="POST", target=None, body=None):
        body = body if body is not None else json.dumps({"command_id": command_id,
            "asset": "BTC", "amount": amount}, separators=(",", ":")).encode("utf-8")
        target = target or f"/v2/accounts/{account}/borrow"
        headers = sign_headers(profile or self.profile, key_id,
            timestamp_ms=time.time_ns() // 1_000_000 if timestamp is None else timestamp,
            nonce=nonce or secrets.token_urlsafe(24), method=method, request_target=target, body=body)
        return headers, {"method": method, "request_target": target, "body": body}

    def issue(self, issuer=None, **options):
        headers, request = self.request(**options)
        return (issuer or self.issuer).issue(headers, **request)

    @staticmethod
    def identity(command_id="c1", amount="1", account="alice"):
        return {"account_id": account, "command_id": command_id,
            "command_payload": json.dumps({"account_id": account, "asset": "BTC", "amount": amount},
                                          sort_keys=True, separators=(",", ":"))}

    def code(self, expected, operation):
        with self.assertRaises((CreditSourceError, SigningError)) as raised:
            operation()
        self.assertEqual(raised.exception.code, expected)

    def test_public_canonical_vector_is_fixed_and_contains_no_signing_key_or_signature(self):
        vector = json.loads((Path(__file__).parent / "vectors/credit-hmac-source-v1.json").read_text())
        fields = {name: vector[name] for name in ("tenant_id", "audience", "key_id", "timestamp_ms",
                                                 "nonce", "method", "request_target")}
        canonical = canonical_request(**fields, body=vector["body_utf8"].encode("utf-8"))
        self.assertEqual(canonical.decode("ascii"), vector["canonical_request_ascii"])
        self.assertEqual(hashlib.sha256(canonical).hexdigest(), vector["canonical_request_sha256"])
        self.assertEqual(hashlib.sha256(vector["body_utf8"].encode()).hexdigest(), vector["body_sha256"])
        self.assertEqual(hashlib.sha256(vector["command_payload"].encode()).hexdigest(), vector["payload_sha256"])
        self.assertFalse(any("secret" in name or "signature" in name for name in vector))

    def test_disabled_default_does_not_create_an_auth_database(self):
        absent = self.root / "must-not-create.sqlite3"
        self.code("credit_source_disabled", lambda: CreditHmacSource(absent, self.path,
            tenant_id="tenant-a", producer_binding="1" * 64))
        self.assertFalse(absent.exists())

    def test_actual_verification_and_audit_bind_first_candidate_without_financial_permission(self):
        headers, request = self.request()
        receipt = self.issuer.issue(headers, **request)
        evidence = self.issuer.inspect(receipt, **self.identity())
        self.assertEqual((evidence["key_id"], evidence["role"], evidence["key_account_id"]),
                         ("funding-alice", "funding", "alice"))
        self.assertEqual(evidence["body_hash"], hashlib.sha256(request["body"]).hexdigest())
        self.assertFalse(evidence["financial_authorized"])
        self.assertEqual(evidence["revocation_barrier"], "NO_GO")
        self.assertIsNone(evidence["credential_epoch"])
        self.assertIsNone(evidence["auth_audit_sequence"])
        self.assertIsNone(evidence["accepted_profile_revision"])
        with self.store.database.read_transaction() as connection:
            row = connection.execute("SELECT request_hash,nonce_hash,event FROM auth_audit ORDER BY sequence DESC LIMIT 1").fetchone()
            self.assertEqual(tuple(row), (evidence["request_hash"], evidence["nonce_hash"], "nonce_consumed"))
            names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertFalse(any("credit" in name or "inbox" in name for name in names))
        encoded = json.dumps(dict(evidence))
        sensitive = [str(self.path), str(self.database), headers["X-UTA-Nonce"], headers["X-UTA-Signature"],
            request["body"].decode(), *(base64.urlsafe_b64encode(key.secret).decode().rstrip("=") for key in self.keys)]
        self.assertTrue(all(value not in encoded for value in sensitive), "candidate exports only permitted evidence")
        with self.assertRaises(TypeError):
            evidence["financial_authorized"] = True

    def test_real_roles_and_account_grants_are_both_required(self):
        for key in ("reader-alice", "trader-alice", "risk", "admin"):
            with self.subTest(key=key):
                self.code("credit_source_forbidden", lambda: self.issue(key_id=key))
        self.code("credit_source_forbidden", lambda: self.issue(account="bob"))
        restricted = self.make_issuer(grants=(("funding-bob", "bob"),))
        self.code("credit_source_forbidden", lambda: self.issue(issuer=restricted))
        bob = self.issue(issuer=restricted, account="bob", key_id="funding-bob")
        self.assertEqual(restricted.inspect(bob, **self.identity(account="bob"))["account_id"], "bob")

    def test_tenant_audience_and_local_producer_binding_reject(self):
        for profile in (replace(self.profile, tenant_id="tenant-b"), replace(self.profile, audience="uta:elsewhere")):
            self.code("invalid_signature", lambda: self.issue(profile=profile))
        for options in ({"tenant_id": "tenant-b"}, {"producer_binding": "2" * 64}):
            with self.assertRaises(ValueError):
                self.make_issuer(**options)

    def test_wrong_exact_body_method_path_and_mac_do_not_issue(self):
        headers, request = self.request()
        for change in ({"body": request["body"] + b" "}, {"method": "PUT"},
                       {"request_target": "/v2/accounts/bob/borrow"}):
            self.code("invalid_signature", lambda: self.issuer.issue(headers, **{**request, **change}))
        bad = {**headers, "X-UTA-Signature": "0" * 64}
        self.code("invalid_signature", lambda: self.issuer.issue(bad, **request))
        self.assertEqual(len(self.issuer._receipts), 0)
        with self.store.database.read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM auth_nonces").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM auth_audit WHERE event='nonce_consumed'").fetchone()[0], 0)

    def test_role_denial_keeps_real_nonce_commit_but_never_mints_a_candidate(self):
        headers, request = self.request(key_id="trader-alice")
        self.code("credit_source_forbidden", lambda: self.issuer.issue(headers, **request))
        self.code("request_replayed", lambda: self.issuer.issue(headers, **request))
        self.assertEqual(len(self.issuer._receipts), 0)
        self.assertEqual(len(self.issuer._commands), 0)
        with self.store.database.read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM auth_nonces").fetchone()[0], 1)

    def test_real_nonce_replay_timestamp_window_and_duplicate_headers_reject(self):
        headers, request = self.request()
        self.issuer.issue(headers, **request)
        self.code("request_replayed", lambda: self.issuer.issue(headers, **request))
        self.code("request_timestamp_out_of_window", lambda: self.issue(timestamp=time.time_ns() // 1_000_000 - 6000))
        self.code("request_timestamp_out_of_window", lambda: self.issue(timestamp=time.time_ns() // 1_000_000 + 1000))
        from email.message import Message
        duplicate = Message()
        for name, value in self.request()[0].items():
            duplicate[name] = value
        duplicate["X-UTA-Key-Id"] = "funding-alice"
        self.code("signature_required", lambda: self.issuer.issue(duplicate, **request))

    def test_signed_bad_json_and_unsupported_route_never_become_receipts(self):
        bodies = (b'{"command_id":"c","asset":"BTC","amount":"1","amount":"2"}',
            b'{"command_id":"c","asset":"BTC","amount":1}',
            b'{"command_id":"c","asset":"BTC","amount":"1","role":"funding"}',
            b'{"command_id":"c","asset":"BTC","amount":"0"}',
            b'{"command_id":"c","asset":"BTC","amount":"1.000000001"}',
            b'{"command_id":"c","asset":"BTC","amount":"01"}',
            b'{"command_id":"c","asset":"BTC","amount":"1e2"}',
            b'{"command_id":"c","asset":"USD","amount":"1"}')
        for body in bodies:
            self.code("credit_source_input_invalid", lambda: self.issue(body=body))
        self.code("credit_source_input_invalid", lambda: self.issue(target="/v2/accounts/alice/borrow?x=1"))
        self.code("credit_source_input_invalid", lambda: self.issue(method="GET"))

    def test_normalized_same_cid_retry_keeps_original_candidate_and_rejects_business_conflict(self):
        first = self.issuer.inspect(self.issue(), **self.identity())
        retried = self.issuer.inspect(self.issue(amount="1.000"), **self.identity())
        self.assertIs(first, retried)
        self.code("idempotency_conflict", lambda: self.issue(amount="2"))
        self.code("idempotency_conflict", lambda: self.issue(account="bob", key_id="funding-bob"))
        self.assertEqual(len(self.issuer._commands), 1)

    def test_opaque_objects_json_copies_foreign_boot_and_wrong_identity_do_not_validate(self):
        receipt = self.issue()
        options = self.identity()
        exported = dict(self.issuer.inspect(receipt, **options))
        forged = object.__new__(type(receipt))
        for value in (exported, json.loads(json.dumps(exported)), forged, object()):
            self.code("credit_source_receipt_invalid", lambda: self.issuer.inspect(value, **options))
        for operation in (copy.copy, copy.deepcopy, pickle.dumps):
            with self.assertRaises(TypeError):
                operation(receipt)
        with self.assertRaises(TypeError):
            type(receipt)()
        other = self.make_issuer()
        self.code("credit_source_receipt_invalid", lambda: other.inspect(receipt, **options))
        for changes in ({"account_id": "bob"}, {"command_id": "other"}, {"command_payload": "{}"}):
            self.code("credit_source_receipt_mismatch", lambda: self.issuer.inspect(receipt, **{**options, **changes}))
        self.issuer.release(receipt)
        self.code("credit_source_receipt_invalid", lambda: self.issuer.inspect(receipt, **options))

    def test_receipt_cannot_cross_real_thread_or_forked_process(self):
        receipt = self.issue()
        options = self.identity()
        with ThreadPoolExecutor(max_workers=1) as worker:
            future = worker.submit(self.issuer.inspect, receipt, **options)
            self.code("credit_source_thread_mismatch", future.result)
        context = multiprocessing.get_context("fork")
        parent, child = context.Pipe(duplex=False)
        process = context.Process(target=_fork_check, args=(self.issuer, receipt, options, child))
        process.start()
        child.close()
        try:
            self.assertTrue(parent.poll(3), "fork isolation returned a bounded result")
            self.assertEqual(parent.recv(), "credit_source_process_mismatch")
            process.join(3)
            self.assertEqual(process.exitcode, 0)
        finally:
            parent.close()
            if process.is_alive():
                process.terminate()
                process.join(3)
            process.close()

    def test_new_thread_gets_own_handle_to_same_candidate_but_new_boot_has_no_durable_source_claim(self):
        first = dict(self.issuer.inspect(self.issue(), **self.identity()))
        def retry():
            receipt = self.issue(amount="1.0000")
            return receipt, dict(self.issuer.inspect(receipt, **self.identity()))
        with ThreadPoolExecutor(max_workers=1) as worker:
            receipt, evidence = worker.submit(retry).result()
        self.assertEqual(first, evidence)
        self.code("credit_source_thread_mismatch", lambda: self.issuer.inspect(receipt, **self.identity()))
        restarted = self.make_issuer()
        fresh = restarted.inspect(self.issue(issuer=restarted), **self.identity())
        self.assertNotEqual(first["issuer_boot"], fresh["issuer_boot"])
        self.assertNotEqual(first["source_reference"], fresh["source_reference"])
        self.assertFalse(fresh["financial_authorized"])

    def test_rotation_and_durable_revocation_reject_stale_profile_without_erasing_history(self):
        receipt = self.issue()
        stale = self.make_issuer()
        new_key = replace(self.keys[0], key_id="funding-new", secret=secrets.token_bytes(32))
        both = replace(self.profile, revision=2, keys=(*self.keys, new_key))
        self.write_profile(both)
        current = self.make_issuer(grants=(("funding-new", "alice"),))
        new_receipt = self.issue(issuer=current, key_id="funding-new", profile=both)
        self.assertEqual(current.inspect(new_receipt, **self.identity())["key_id"], "funding-new")
        only_new = replace(both, revision=3, keys=(new_key,))
        self.write_profile(only_new)
        current.replace_profile(self.path)
        self.code("signing_key_inactive", lambda: self.issue(issuer=stale, command_id="c2"))
        self.assertFalse(self.issuer.inspect(receipt, **self.identity())["financial_authorized"])
        self.write_profile(self.profile)
        with self.assertRaises(ValueError):
            stale.replace_profile(self.path)

    def test_actual_key_expiry_private_file_and_lost_database_fail_closed(self):
        now = time.time_ns() // 1_000_000
        expired = replace(self.keys[0], key_id="expired", not_before_ms=now - 20000, expires_at_ms=now - 10000)
        profile = replace(self.profile, revision=2, keys=(expired,))
        self.write_profile(profile)
        issuer = self.make_issuer(grants=(("expired", "alice"),))
        self.code("signing_key_inactive", lambda: self.issue(issuer=issuer, profile=profile, key_id="expired"))
        self.path.chmod(0o640)
        with self.assertRaises(ValueError):
            self.make_issuer()
        self.path.chmod(0o600)
        self.database.unlink()
        self.code("signing_store_unavailable", lambda: self.issue())
        self.assertFalse(self.database.exists())

    def test_bounded_registry_never_evicts_original_candidate_identity(self):
        issuer = self.make_issuer(max_commands=1, max_receipts=1)
        receipt = self.issue(issuer=issuer)
        self.code("credit_source_capacity", lambda: self.issue(issuer=issuer))
        original = issuer.inspect(receipt, **self.identity())
        issuer.release(receipt)
        self.code("credit_source_capacity", lambda: self.issue(issuer=issuer, command_id="c2"))
        self.assertIs(issuer.inspect(self.issue(issuer=issuer), **self.identity()), original)


if __name__ == "__main__":
    unittest.main()
