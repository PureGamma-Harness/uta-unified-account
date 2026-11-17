"""Fresh private AuthDB-only acceptance controls; no listener or finance."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import copy
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import secrets
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread
import time
import unittest
from unittest.mock import patch

from uta.credit_auth_h0 import CreditAuthError, CreditHmacIngressV2, CreditNonceStoreV2
from uta.gateway import Credential
from uta.request_signing import (NonceStore, RequestAuthenticator, SigningError,
    SigningKey, SigningProfile, load_profile, sign_headers)


def _fork_inspect(issuer, handle, sender):
    try:
        issuer.inspect(handle)
        sender.send("UNEXPECTED_SUCCESS")
    except SigningError as error:
        sender.send(error.code)
    finally:
        sender.close()


class CreditAuthH0Tests(unittest.TestCase):
    def setUp(self):
        retained = os.environ.get("UTA_H0_PRIVATE_CASES")
        if retained:
            parent = Path(retained)
            if not parent.is_absolute():raise ValueError("private cases require absolute path")
            self.root = parent/(self._testMethodName+"-"+secrets.token_hex(4))
            self.root.mkdir(mode=0o700, parents=True, exist_ok=False)
        else:
            temporary = TemporaryDirectory(prefix="uta-auth-h0-")
            self.addCleanup(temporary.cleanup)
            self.root = Path(temporary.name)
        now = time.time_ns()//1000000
        self.keys = tuple(SigningKey(name, secrets.token_bytes(32), role, account, 0, now+3600000)
            for name, role, account in (("funding", "funding", "alice"),
                ("reader", "reader", "alice"), ("other-funding", "funding", "alice"),
                ("admin", "admin", None)))
        self.store, self.profile, self.profile_path, self.issuer = self.fixture("main")

    def fixture(self, name, *, limits=None, max_handles=256, query_handle_reserve=32):
        root = self.root/name;root.mkdir(mode=0o700)
        store = CreditNonceStoreV2.initialize(root/"auth.sqlite3", tenant_id="tenant-a",
            producer_binding="5"*64, domain_id="domain-a", account_id="alice", limits=limits)
        profile = SigningProfile("tenant-a", store.audience, 1, self.keys)
        path = root/"profile.json";self.write_profile(path, profile)
        issuer = CreditHmacIngressV2(store.database.path, path, tenant_id="tenant-a",
            producer_binding="5"*64, domain_id="domain-a", domain_epoch=1,
            account_id="alice", enabled=True, max_handles=max_handles,
            query_handle_reserve=query_handle_reserve)
        for number, (key, operation) in enumerate((("funding", "credit.borrow"),
                ("funding", "credit.repay"), ("funding", "credit.read"),
                ("reader", "credit.read"))):
            issuer.store.put_grant("grant-"+str(number), key_id=key, account_id="alice",
                asset="BTC", operation=operation, expected_grant_revision=number)
        return issuer.store, profile, path, issuer

    @staticmethod
    def write_profile(path, profile):
        import base64
        data = {"format": 1, "tenant_id": profile.tenant_id, "audience": profile.audience,
            "revision": profile.revision, "keys": [{"key_id": key.key_id,
            "secret_b64": base64.urlsafe_b64encode(key.secret).decode().rstrip("="),
            "role": key.role, "account_id": key.account_id, "not_before_ms": key.not_before_ms,
            "expires_at_ms": key.expires_at_ms, "revoked": key.revoked} for key in profile.keys]}
        descriptor = os.open(path, os.O_WRONLY|os.O_CREAT|os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w") as stream:json.dump(data, stream)
        os.chmod(path, 0o600)

    def signed(self, cid="cid-a", *, profile=None, key="funding", amount="0.4",
               kind="borrow", lookup=False, body=None):
        profile = profile or self.profile
        method = "GET" if lookup else "POST"
        target = ("/v2/accounts/alice/credit/commands/"+cid if lookup
                  else "/v2/accounts/alice/"+kind)
        if body is None:
            body = b"" if lookup else json.dumps({"command_id": cid, "asset": "BTC", "amount": amount},
                sort_keys=True, separators=(",", ":")).encode()
        headers = sign_headers(profile, key, timestamp_ms=time.time_ns()//1000000,
            nonce=secrets.token_urlsafe(24), method=method, request_target=target, body=body)
        # Exact actual requests are private test evidence, never public stdout.
        # Original072 observations did not retain every header; new batches do.
        import base64
        private = self.root/("private-request-"+secrets.token_hex(12)+".json")
        descriptor = os.open(private, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            json.dump({"headers": headers, "method": method, "request_target": target,
                "body_base64": base64.b64encode(body).decode()}, stream)
        return headers, {"method": method, "request_target": target, "body": body}

    def capture(self, cid="cid-a", *, issuer=None, **options):
        headers, request = self.signed(cid, **options)
        return (issuer or self.issuer).capture(headers, **request)

    def lookup(self, cid="cid-a", *, issuer=None, profile=None, key="reader"):
        headers, request = self.signed(cid, profile=profile, key=key, lookup=True)
        return (issuer or self.issuer).lookup(headers, **request)

    def counts(self, store=None):
        store = store or self.store
        with store._transaction(read=True) as connection:
            return tuple(connection.execute("SELECT COUNT(*) FROM main."+name).fetchone()[0]
                for name in ("auth_nonces", "auth_audit", "auth_credit_acceptances"))

    def revision(self, store=None):
        store = store or self.store
        with store._transaction(read=True) as connection:
            return store._config(connection)["grant_revision"]

    def expect_code(self, code, function, *args, **kwargs):
        with self.assertRaises(SigningError) as caught:function(*args, **kwargs)
        self.assertTrue(caught.exception.code == code)

    def auth_only(self, issuer, handle, kind):
        result = issuer.inspect(handle)
        self.assertTrue(result["receipt_kind"] == kind)
        for name in ("financial_authorized", "source_delivery_authorized", "execution_authorized"):
            self.assertIs(result[name], False)
        return result

    def test_H0_I01_legacy_format1_real_positive_and_return_contract(self):
        store = NonceStore.initialize(self.root/"legacy.sqlite3", tenant_id="tenant-a", producer_binding="6"*64)
        profile = SigningProfile("tenant-a", store.audience, 1, (self.keys[0],))
        path = self.root/"legacy-profile.json";self.write_profile(path, profile)
        authenticator = RequestAuthenticator(store, load_profile(path))
        headers, request = self.signed(profile=profile)
        principal = authenticator.authenticate(headers, **request)
        self.assertIs(type(principal), Credential)
        self.assertTrue(principal.role == "funding" and principal.account_id == "alice")
        self.expect_code("request_replayed", authenticator.authenticate, headers, **request)
        with store.database.read_transaction() as connection:
            self.assertTrue(connection.execute("SELECT COUNT(*) FROM auth_nonces").fetchone()[0] == 1)

    def test_H0_I02_disabled_missing_and_legacy_format_not_repaired(self):
        missing = self.root/"missing.sqlite3"
        self.expect_code("credit_auth_disabled", CreditHmacIngressV2, missing, self.root/"missing-profile",
            tenant_id="tenant-a", producer_binding="5"*64, domain_id="domain-a", domain_epoch=1, account_id="alice")
        self.assertFalse(missing.exists())
        self.expect_code("credit_auth_outcome_unknown", CreditNonceStoreV2, missing)
        self.assertFalse(missing.exists())
        legacy = NonceStore.initialize(self.root/"old.sqlite3", tenant_id="tenant-a", producer_binding="7"*64)
        self.expect_code("credit_auth_outcome_unknown", CreditNonceStoreV2, legacy.database.path)
        self.assertIs(type(NonceStore(legacy.database.path)), NonceStore)

    def test_H0_I03_exact_main_reopen_old_reader_and_bad_foreign_key_refusal(self):
        self.assertIs(type(CreditNonceStoreV2(self.store.database.path)), CreditNonceStoreV2)
        before = self.counts()
        with self.assertRaises(SigningError):NonceStore(self.store.database.path)
        self.assertTrue(self.counts() == before)
        legacy_source = os.environ.get("UTA_H0_LEGACY_SOURCE")
        if legacy_source:
            script = """import sys;sys.path.insert(0,sys.argv[1]);from uta.request_signing import NonceStore,SigningError
try:NonceStore(sys.argv[2])
except SigningError:print('OLD_FORMAT_REJECTED');sys.exit(0)
sys.exit(9)
"""
            run = subprocess.run([sys.executable, "-I", "-B", "-c", script, legacy_source,
                self.store.database.path], capture_output=True, text=True, timeout=5)
            self.assertTrue(run.returncode == 0 and run.stdout == "OLD_FORMAT_REJECTED\n")
            self.assertTrue(self.counts() == before)
        # Real previously initialized legacy object also rejects before DML.
        oldpath = self.root/"legacy-switch.sqlite3"
        old = NonceStore.initialize(oldpath, tenant_id="tenant-a", producer_binding="8"*64)
        profile = SigningProfile("tenant-a", old.audience, 1, (self.keys[0],))
        authenticator = RequestAuthenticator(old, profile)
        oldpath.rename(self.root/"original-v1-retained.sqlite3")
        fresh = CreditNonceStoreV2.initialize(oldpath, tenant_id="tenant-a", producer_binding="8"*64,
            domain_id="domain-test", account_id="alice")
        with self.assertRaises(SigningError):old.configure(profile)
        headers, request = self.signed(profile=profile)
        with self.assertRaises(SigningError):authenticator.authenticate(headers, **request)
        self.assertTrue(self.counts(fresh) == (0, 0, 0))
        # Preserve names/columns and all original triggers but remove its FK.
        connection = sqlite3.connect(self.store.database.path, isolation_level=None)
        try:
            ddl = connection.execute("SELECT sql FROM main.sqlite_master WHERE name='auth_nonces'").fetchone()[0]
            guards = connection.execute("SELECT sql FROM main.sqlite_master WHERE tbl_name='auth_nonces' AND type IN ('index','trigger') AND sql IS NOT NULL").fetchall()
            connection.execute("PRAGMA foreign_keys=OFF")
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DROP TABLE main.auth_nonces")
            connection.execute(ddl.replace(" REFERENCES auth_keys(key_id)", "", 1))
            for row in guards:connection.execute(row[0])
            connection.commit()
        finally:connection.close()
        self.expect_code("credit_auth_outcome_unknown", CreditNonceStoreV2, self.store.database.path)

    def test_H0_I04_valid_mac_business_role_denials_consume_once_and_bad_mac_does_not(self):
        headers, request = self.signed(body=b'{"command_id":false}')
        self.expect_code("credit_auth_input_invalid", self.issuer.capture, headers, **request)
        self.expect_code("request_replayed", self.issuer.capture, headers, **request)
        self.assertTrue(self.counts()[0] == 1 and self.counts()[2] == 0)
        headers, request = self.signed(key="admin")
        self.expect_code("credit_auth_forbidden", self.issuer.capture, headers, **request)
        before = self.counts()
        headers, request = self.signed()
        headers["X-UTA-Signature"] = "0"*64
        self.expect_code("invalid_signature", self.issuer.capture, headers, **request)
        self.assertTrue(self.counts() == before)
        with self.store._transaction(read=True) as connection:
            outcomes = [r[0] for r in connection.execute("SELECT outcome FROM auth_audit WHERE event='nonce_consumed'")]
        self.assertTrue(outcomes == ["INPUT_REJECTED", "PERMISSION_REJECTED"])

    def test_H0_I05_actual_commit_reply_loss_then_current_authorized_lookup(self):
        original = self.store.database.transaction
        @contextmanager
        def lose_reply():
            with original() as connection:yield connection
            raise OSError("synthetic response loss")
        with patch.object(self.store.database, "transaction", lose_reply):
            self.expect_code("credit_auth_outcome_unknown", self.capture)
        self.assertTrue(self.counts()[2] == 1)
        self.assertTrue(len(self.issuer._handles) == 0 and len(self.issuer._slots) == 0)
        restarted = CreditHmacIngressV2(self.store.database.path, self.profile_path,
            tenant_id="tenant-a", producer_binding="5"*64, domain_id="domain-a", domain_epoch=1,
            account_id="alice", enabled=True)
        handle = self.lookup(issuer=restarted)
        result = self.auth_only(restarted, handle, "auth_query_only")
        first = json.loads(result["first_acceptance_payload_or_null"])
        self.assertTrue(first["key_id"] == "funding" and first["grant_id"] == "grant-0")
        self.assertTrue(self.counts()[2] == 1)

    def test_H0_I06_canonical_retry_kind_payload_conflict_and_first_immutability(self):
        first = self.auth_only(self.issuer, self.capture(amount="0.400"), "auth_first_observation")
        retry = self.auth_only(self.issuer, self.capture(amount="0.4"), "auth_query_only")
        self.assertTrue(first["first_acceptance_id"] == retry["first_acceptance_id"])
        self.assertTrue(first["first_acceptance_payload_or_null"] == retry["first_acceptance_payload_or_null"])
        self.expect_code("idempotency_conflict", self.capture, amount="0.5")
        self.expect_code("idempotency_conflict", self.capture, kind="repay")
        self.assertTrue(self.counts()[2] == 1)

    def test_H0_I07_revoked_original_grant_not_rebound_to_new_key_or_epoch(self):
        first = self.auth_only(self.issuer, self.capture(), "auth_first_observation")
        self.store.revoke_grant("grant-0", expected_grant_revision=self.revision())
        self.expect_code("credit_auth_forbidden", self.capture)
        for grant, operation in (("other-borrow", "credit.borrow"), ("other-read", "credit.read")):
            self.store.put_grant(grant, key_id="other-funding", account_id="alice", asset="BTC",
                operation=operation, expected_grant_revision=self.revision())
        retry = self.auth_only(self.issuer, self.capture(key="other-funding"), "auth_query_only")
        self.assertTrue(retry["first_acceptance_payload_or_null"] == first["first_acceptance_payload_or_null"])
        original = json.loads(retry["first_acceptance_payload_or_null"])
        self.assertTrue(original["key_id"] == "funding" and original["grant_id"] == "grant-0")
        self.assertTrue(self.counts()[2] == 1)

    def test_H0_I08_real_concurrent_first_cid_and_grant_revoke_are_atomic(self):
        def submit(cid):
            try:
                handle = self.capture(cid)
                result = dict(self.issuer.inspect(handle));self.issuer.release(handle)
                return result["receipt_kind"], result["first_acceptance_id"]
            except SigningError as error:return error.code, None
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(submit, ["concurrent", "concurrent"]))
        self.assertTrue(sorted(r[0] for r in results) == ["auth_first_observation", "auth_query_only"])
        self.assertTrue(results[0][1] == results[1][1] and self.counts()[2] == 1)
        revision = self.revision()
        with ThreadPoolExecutor(max_workers=2) as pool:
            accepted = pool.submit(submit, "revoke-race")
            revoked = pool.submit(self.store.revoke_grant, "grant-0", expected_grant_revision=revision)
            outcome = accepted.result();revoked.result()
        self.assertTrue(outcome[0] in ("auth_first_observation", "credit_auth_forbidden"))
        with self.store._transaction(read=True) as connection:
            row = connection.execute("SELECT * FROM auth_credit_acceptances WHERE command_id='revoke-race'").fetchone()
            revoke_audit = connection.execute("SELECT audit_sequence FROM auth_credit_grant_revocations WHERE grant_id='grant-0'").fetchone()[0]
            if row is not None:
                self.assertTrue(row["auth_audit_sequence"] < revoke_audit and row["grant_epoch"] == 1 and row["grant_revision"] == revision)

    def test_H0_I09_strict_nonce_expiry_never_prunes_first_acceptance(self):
        store, profile, _, issuer = self.fixture("short-ttl", limits={"past_window": 20, "future_skew": 0})
        first = self.auth_only(issuer, self.capture(issuer=issuer, profile=profile), "auth_first_observation")
        with store.database.transaction() as connection:
            expiry = connection.execute("SELECT expires_ms FROM auth_nonces").fetchone()[0]
            connection.execute("UPDATE auth_config SET highwater=?", (expiry,))
            with self.assertRaises(sqlite3.IntegrityError):connection.execute("DELETE FROM auth_nonces")
            self.assertTrue(connection.execute("SELECT COUNT(*) FROM auth_nonces").fetchone()[0] == 1)
        time.sleep(.05)
        result = self.auth_only(issuer, self.lookup(issuer=issuer, profile=profile), "auth_query_only")
        self.assertTrue(result["first_acceptance_payload_or_null"] == first["first_acceptance_payload_or_null"])
        self.assertTrue(self.counts(store)[0] == 1 and self.counts(store)[2] == 1)

    def test_H0_I10_query_reserves_quota_and_unknown_audit_without_eviction(self):
        store, profile, _, issuer = self.fixture("handles", max_handles=2, query_handle_reserve=1)
        ordinary = self.capture(issuer=issuer, profile=profile)
        before = len(issuer._slots)
        self.expect_code("credit_auth_forbidden", self.lookup, issuer=issuer, profile=profile, key="admin")
        self.assertTrue(len(issuer._slots) == before)
        query = self.lookup(issuer=issuer, profile=profile)
        self.auth_only(issuer, query, "auth_query_only")
        self.assertTrue(len(issuer._slots) == 2)
        issuer.release(query);issuer.release(ordinary)
        store, profile, _, issuer = self.fixture("nonces", limits={"max_nonces": 4, "query_nonce_reserve": 1})
        for n in range(3):issuer.release(self.capture("nonce-"+str(n), issuer=issuer, profile=profile))
        self.expect_code("signing_capacity_exhausted", self.capture, "nonce-over", issuer=issuer, profile=profile)
        handle = self.lookup("nonce-0", issuer=issuer, profile=profile)
        self.auth_only(issuer, handle, "auth_query_only")
        self.assertTrue(self.counts(store)[0] == 4 and self.counts(store)[2] == 3)
        store, profile, _, issuer = self.fixture("acceptances", limits={"max_acceptances": 1})
        issuer.release(self.capture(issuer=issuer, profile=profile))
        issuer.release(self.capture(issuer=issuer, profile=profile))
        self.expect_code("credit_auth_reservation_capacity", self.capture, "new-cid", issuer=issuer, profile=profile)
        self.assertTrue(self.counts(store)[2] == 1)
        store, profile, _, issuer = self.fixture("audit", limits={"max_audit": 12,
            "query_audit_reserve": 3, "control_audit_reserve": 2})
        for cid in ("audit-a", "audit-b"):issuer.release(self.capture(cid, issuer=issuer, profile=profile))
        before = self.counts(store)
        self.expect_code("credit_auth_outcome_unknown", self.capture, "audit-over", issuer=issuer, profile=profile)
        self.assertTrue(self.counts(store) == before)
        issuer.release(self.lookup("audit-a", issuer=issuer, profile=profile))
        self.assertTrue(self.counts(store)[2] == 2)

    def test_H0_I11_actual_rollback_missing_private_authority_never_issues_handle(self):
        original = self.store.database.transaction
        @contextmanager
        def fail_before_commit():
            with original() as connection:
                yield connection
                raise OSError("synthetic precommit failure")
        before = self.counts()
        with patch.object(self.store.database, "transaction", fail_before_commit):
            self.expect_code("credit_auth_outcome_unknown", self.capture)
        self.assertTrue(self.counts() == before and len(self.issuer._handles) == 0)
        Path(self.store.database.path).rename(self.root/"retained-missing-authority.sqlite3")
        self.expect_code("credit_auth_outcome_unknown", self.lookup)
        self.assertFalse(Path(self.store.database.path).exists())

    def test_H0_I12_opaque_observation_thread_copy_fork_and_registry_isolation(self):
        handle = self.capture()
        self.auth_only(self.issuer, handle, "auth_first_observation")
        self.expect_code("credit_auth_handle_invalid", self.issuer.inspect, object())
        with self.assertRaises(TypeError):copy.copy(handle)
        other = CreditHmacIngressV2(self.store.database.path, self.profile_path, tenant_id="tenant-a",
            producer_binding="5"*64, domain_id="domain-a", domain_epoch=1, account_id="alice", enabled=True)
        self.expect_code("credit_auth_handle_invalid", other.inspect, handle)
        observed = []
        def inspect_thread():
            try:self.issuer.inspect(handle)
            except SigningError as error:observed.append(error.code)
        thread = Thread(target=inspect_thread);thread.start();thread.join(2)
        self.assertTrue(not thread.is_alive() and observed == ["credit_auth_thread_mismatch"])
        context = multiprocessing.get_context("fork")
        receiver, sender = context.Pipe(duplex=False)
        process = context.Process(target=_fork_inspect, args=(self.issuer, handle, sender))
        self.issuer._lock.acquire()
        try:
            process.start();sender.close()
            self.assertTrue(receiver.poll(2))
            self.assertTrue(receiver.recv() == "credit_auth_process_mismatch")
        finally:
            self.issuer._lock.release();receiver.close();process.join(2)
            if process.is_alive():process.terminate();process.join(2)
        self.assertTrue(process.exitcode == 0)
        self.issuer.release(handle)
        self.assertTrue(len(self.issuer._slots) == 0)


if __name__ == "__main__":unittest.main()
