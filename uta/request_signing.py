"""HMAC authentication with a durable, deployment-bound replay window.

Nonce acceptance is a separate WAL/FULL commit before command ingress. It is
neither an authorization for financial execution nor a financial receipt.
"""
from __future__ import annotations

import base64
from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
from threading import RLock
import time
from uuid import uuid4

from .gateway import Credential, _decode_json
from .storage import Database, StorageError, _FILE_CHECK_LOCK


_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z", re.ASCII)
_NONCE = re.compile(r"[A-Za-z0-9_-]{22,128}\Z", re.ASCII)
_HEX = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_MAX_INT = 2**63 - 1
_AUTH_HEADER = "UTA-HMAC-SHA256"
_TABLES = {"auth_config", "auth_keys", "auth_nonces", "auth_audit"}
_COLUMNS = {
    "auth_config": {"singleton", "format", "canonical_path", "tenant", "audience", "producer_binding", "past_window", "future_skew", "max_nonces", "highwater", "revision", "fingerprint"},
    "auth_keys": {"key_id", "identity", "revoked"},
    "auth_nonces": {"key_id", "nonce_hash", "expires_ms"},
    "auth_audit": {"sequence", "event", "key_id", "nonce_hash", "request_hash", "request_ms", "server_ms", "revision"},
}
_TRIGGERS = {"auth_config_monotonic", "auth_keys_immutable", "auth_nonces_immutable", "auth_nonces_window",
             "auth_audit_no_update", "auth_audit_no_delete"}


class SigningError(ValueError):
    def __init__(self, code, message, status=401):
        super().__init__(message)
        self.code, self.status = code, status


def _id(value, name):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError(f"{name} requires a bounded ASCII identifier")


def _integer(value, name, minimum=0, maximum=_MAX_INT):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{name} requires a bounded integer")


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class SigningKey:
    key_id: str
    secret: bytes = field(repr=False)
    role: str
    account_id: str | None
    not_before_ms: int
    expires_at_ms: int
    revoked: bool = False

    def __post_init__(self):
        _id(self.key_id, "key_id")
        if type(self.secret) is not bytes or not 32 <= len(self.secret) <= 128:
            raise ValueError("signing secrets require 32..128 random bytes")
        self.principal()  # Reuse exactly the existing role/account validator.
        _integer(self.not_before_ms, "not_before_ms")
        _integer(self.expires_at_ms, "expires_at_ms", self.not_before_ms + 1)
        if type(self.revoked) is not bool:
            raise ValueError("revoked must be a bool")

    def principal(self):
        # This placeholder is only a role validator. The HMAC handler never
        # consults or accepts any Bearer credential, including this value.
        return Credential("HMAC_ROLE_VALIDATION_ONLY_NOT_A_BEARER_KEY", self.role, self.account_id)

    def identity(self):
        return hashlib.sha256(_json({"key_id": self.key_id, "secret_hash": hashlib.sha256(self.secret).hexdigest(),
            "role": self.role, "account_id": self.account_id, "not_before_ms": self.not_before_ms,
            "expires_at_ms": self.expires_at_ms}).encode()).hexdigest()


@dataclass(frozen=True)
class SigningProfile:
    tenant_id: str
    audience: str
    revision: int
    keys: tuple[SigningKey, ...]

    def __post_init__(self):
        _id(self.tenant_id, "tenant_id")
        _id(self.audience, "audience")
        _integer(self.revision, "revision", 1)
        if (type(self.keys) is not tuple or not 1 <= len(self.keys) <= 256
                or any(not isinstance(key, SigningKey) for key in self.keys)
                or len({key.key_id for key in self.keys}) != len(self.keys)):
            raise ValueError("profile requires 1..256 distinct signing keys")

    def fingerprint(self):
        return hashlib.sha256(_json({"tenant": self.tenant_id, "audience": self.audience,
            "keys": sorted((key.key_id, key.identity(), key.revoked) for key in self.keys)}).encode()).hexdigest()


def load_profile(path) -> SigningProfile:
    """Load a private, service-user-owned JSON file; never echo secret data."""
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise ValueError("signing profile requires a private regular service-user-owned file")
        body = source.read(65537)
    try:
        if len(body) > 65536:
            raise ValueError("oversized profile")
        data = _decode_json(body)
        if not isinstance(data, dict) or set(data) != {"format", "tenant_id", "audience", "revision", "keys"} or type(data["format"]) is not int or data["format"] != 1:
            raise ValueError("invalid profile format")
        if not isinstance(data["keys"], list):
            raise ValueError("invalid keys")
        keys = []
        fields = {"key_id", "secret_b64", "role", "account_id", "not_before_ms", "expires_at_ms", "revoked"}
        for item in data["keys"]:
            if not isinstance(item, dict) or set(item) != fields or not isinstance(item["secret_b64"], str):
                raise ValueError("invalid key fields")
            encoded = item["secret_b64"]
            secret = base64.b64decode(encoded + "=" * (-len(encoded) % 4), altchars=b"-_", validate=True)
            if base64.urlsafe_b64encode(secret).decode().rstrip("=") != encoded:
                raise ValueError("noncanonical key encoding")
            keys.append(SigningKey(**{k: v for k, v in item.items() if k != "secret_b64"}, secret=secret))
        return SigningProfile(data["tenant_id"], data["audience"], data["revision"], tuple(keys))
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ValueError("invalid signing profile configuration") from None


def canonical_request(*, tenant_id, audience, key_id, timestamp_ms, nonce, method, request_target, body):
    """Version 1: compact JSON array, ASCII encoded, no newline or normalization."""
    for name, value in (("tenant_id", tenant_id), ("audience", audience), ("key_id", key_id)):
        _id(value, name)
    _integer(timestamp_ms, "timestamp_ms")
    if not isinstance(nonce, str) or not _NONCE.fullmatch(nonce):
        raise ValueError("nonce requires 22..128 URL-safe ASCII characters")
    if not isinstance(method, str) or not re.fullmatch(r"[A-Z]{1,16}", method, re.ASCII):
        raise ValueError("invalid method")
    if (not isinstance(request_target, str) or not 1 <= len(request_target) <= 2048
            or not request_target.startswith("/") or any(ord(ch) < 33 or ord(ch) > 126 for ch in request_target)
            or "#" in request_target):
        raise ValueError("request target requires bounded raw ASCII origin-form")
    if type(body) is not bytes or len(body) > 65536:
        raise ValueError("body requires at most 64 KiB of exact bytes")
    return json.dumps(["UTA-HMAC-SHA256", "1", tenant_id, audience, key_id, str(timestamp_ms),
        nonce, method, request_target, hashlib.sha256(body).hexdigest()], separators=(",", ":"), ensure_ascii=True).encode("ascii")


def sign_headers(profile: SigningProfile, key_id: str, *, timestamp_ms, nonce, method, request_target, body=b""):
    """Client helper; sign the exact bytes later sent on the wire."""
    key = next((key for key in profile.keys if key.key_id == key_id), None)
    if key is None:
        raise ValueError("unknown signing key")
    canonical = canonical_request(tenant_id=profile.tenant_id, audience=profile.audience, key_id=key_id,
        timestamp_ms=timestamp_ms, nonce=nonce, method=method, request_target=request_target, body=body)
    return {"Authorization": _AUTH_HEADER, "X-UTA-Version": "1", "X-UTA-Tenant": profile.tenant_id,
        "X-UTA-Audience": profile.audience, "X-UTA-Key-Id": key_id, "X-UTA-Timestamp-Ms": str(timestamp_ms),
        "X-UTA-Nonce": nonce, "X-UTA-Signature": hmac.new(key.secret, canonical, hashlib.sha256).hexdigest()}


class _ExistingAuthDatabase(Database):
    def _private_file(self):
        with _FILE_CHECK_LOCK:
            try:
                info = os.stat(self.path, follow_symlinks=False)
            except OSError as exc:
                raise StorageError("existing authentication database unavailable; automatic recreation is forbidden") from exc
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
                raise StorageError("authentication database must remain private and service-user-owned")
            return info.st_dev, info.st_ino


class NonceStore:
    """Existing authentication authority. No constructor silently creates one."""
    @classmethod
    def initialize(cls, path, *, tenant_id, producer_binding, past_window_ms=30000,
                   future_skew_ms=5000, max_nonces=100000):
        _id(tenant_id, "tenant_id")
        if not isinstance(producer_binding, str) or not _HEX.fullmatch(producer_binding):
            raise ValueError("producer_binding must identify the actual authority")
        _integer(past_window_ms, "past_window_ms", 1, 300000)
        _integer(future_skew_ms, "future_skew_ms", 0, 30000)
        _integer(max_nonces, "max_nonces", 1, 1000000)
        db = _ExistingAuthDatabase(path)
        with _FILE_CHECK_LOCK:
            descriptor = os.open(db.path, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
            os.close(descriptor)
        audience = "uta:" + uuid4().hex
        with db.transaction() as connection:
            connection.execute("CREATE TABLE auth_config(singleton INTEGER PRIMARY KEY CHECK(singleton=1),format INTEGER NOT NULL,canonical_path TEXT NOT NULL,tenant TEXT NOT NULL,audience TEXT NOT NULL,producer_binding TEXT NOT NULL,past_window INTEGER NOT NULL,future_skew INTEGER NOT NULL,max_nonces INTEGER NOT NULL,highwater INTEGER NOT NULL,revision INTEGER NOT NULL,fingerprint TEXT NOT NULL)")
            connection.execute("INSERT INTO auth_config VALUES(1,1,?,?,?,?,?,?,?,0,0,'')", (db.path, tenant_id, audience, producer_binding, past_window_ms, future_skew_ms, max_nonces))
            connection.execute("CREATE TABLE auth_keys(key_id TEXT PRIMARY KEY,identity TEXT NOT NULL,revoked INTEGER NOT NULL CHECK(revoked IN(0,1)))")
            connection.execute("CREATE TABLE auth_nonces(key_id TEXT NOT NULL REFERENCES auth_keys(key_id),nonce_hash TEXT NOT NULL,expires_ms INTEGER NOT NULL,PRIMARY KEY(key_id,nonce_hash))")
            connection.execute("CREATE INDEX auth_nonce_expiry ON auth_nonces(expires_ms)")
            connection.execute("CREATE TABLE auth_audit(sequence INTEGER PRIMARY KEY,event TEXT NOT NULL,key_id TEXT,nonce_hash TEXT,request_hash TEXT,request_ms INTEGER,server_ms INTEGER,revision INTEGER NOT NULL)")
            connection.execute("CREATE TRIGGER auth_config_monotonic BEFORE UPDATE ON auth_config WHEN NEW.singleton!=OLD.singleton OR NEW.format!=OLD.format OR NEW.canonical_path!=OLD.canonical_path OR NEW.tenant!=OLD.tenant OR NEW.audience!=OLD.audience OR NEW.producer_binding!=OLD.producer_binding OR NEW.past_window!=OLD.past_window OR NEW.future_skew!=OLD.future_skew OR NEW.max_nonces!=OLD.max_nonces OR NEW.highwater<OLD.highwater OR NEW.revision<OLD.revision BEGIN SELECT RAISE(ABORT,'authentication identity and clock are immutable or monotonic'); END")
            connection.execute("CREATE TRIGGER auth_keys_immutable BEFORE UPDATE ON auth_keys WHEN NEW.key_id!=OLD.key_id OR NEW.identity!=OLD.identity OR NEW.revoked<OLD.revoked BEGIN SELECT RAISE(ABORT,'key identity cannot be reassigned or unrevoked'); END")
            connection.execute("CREATE TRIGGER auth_nonces_immutable BEFORE UPDATE ON auth_nonces BEGIN SELECT RAISE(ABORT,'consumed nonce is immutable'); END")
            connection.execute("CREATE TRIGGER auth_nonces_window BEFORE DELETE ON auth_nonces WHEN OLD.expires_ms >= (SELECT highwater FROM auth_config WHERE singleton=1) BEGIN SELECT RAISE(ABORT,'nonce still within replay window'); END")
            for action in ("UPDATE", "DELETE"):
                connection.execute(f"CREATE TRIGGER auth_audit_no_{action.lower()} BEFORE {action} ON auth_audit BEGIN SELECT RAISE(ABORT,'authentication audit is append-only'); END")
        return cls(path)

    def __init__(self, path):
        self.database = _ExistingAuthDatabase(path)
        with self._transaction(read=True) as connection:
            row = self._config(connection)
        self.tenant_id, self.audience, self.producer_binding = row["tenant"], row["audience"], row["producer_binding"]

    @contextmanager
    def _transaction(self, read=False):
        try:
            with (self.database.read_transaction() if read else self.database.transaction()) as connection:
                yield connection
        except (StorageError, sqlite3.Error, OSError) as exc:
            raise SigningError("signing_store_unavailable", "persistent authentication authority unavailable; no fallback", 503) from exc

    def _config(self, connection):
        names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type IN('table','trigger')")}
        if not _TABLES | _TRIGGERS <= names:
            raise StorageError("authentication schema or integrity guards are missing")
        for table, expected in _COLUMNS.items():
            if {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")} != expected:
                raise StorageError("authentication schema columns differ from the supported format")
        rows = connection.execute("SELECT * FROM auth_config").fetchall()
        if len(rows) != 1 or rows[0]["format"] != 1 or rows[0]["canonical_path"] != self.database.path:
            raise StorageError("authentication identity is invalid or was moved")
        if hasattr(self, "audience") and (rows[0]["tenant"], rows[0]["audience"], rows[0]["producer_binding"]) != (self.tenant_id, self.audience, self.producer_binding):
            raise StorageError("authentication deployment identity changed")
        row = rows[0]
        try:
            _id(row["tenant"], "tenant")
            _id(row["audience"], "audience")
            _integer(row["highwater"], "highwater")
            _integer(row["revision"], "revision")
            _integer(row["past_window"], "past_window", 1, 300000)
            _integer(row["future_skew"], "future_skew", 0, 30000)
            _integer(row["max_nonces"], "max_nonces", 1, 1000000)
            if not _HEX.fullmatch(row["producer_binding"]) or (row["revision"] and not _HEX.fullmatch(row["fingerprint"])):
                raise ValueError("invalid authentication binding")
        except (ValueError, TypeError):
            raise StorageError("authentication configuration is malformed") from None
        return rows[0]

    @staticmethod
    def _audit(connection, event, *, key_id=None, nonce_hash=None, request_hash=None, request_ms=None, server_ms=None):
        connection.execute("INSERT INTO auth_audit(event,key_id,nonce_hash,request_hash,request_ms,server_ms,revision) VALUES(?,?,?,?,?,?,(SELECT revision FROM auth_config WHERE singleton=1))",
                           (event, key_id, nonce_hash, request_hash, request_ms, server_ms))

    def configure(self, profile: SigningProfile):
        if (profile.tenant_id, profile.audience) != (self.tenant_id, self.audience):
            raise ValueError("signing profile belongs to another tenant or deployment")
        with self._transaction() as connection:
            row = self._config(connection)
            if profile.revision < row["revision"] or profile.revision == row["revision"] and profile.fingerprint() != row["fingerprint"]:
                raise ValueError("stale or conflicting signing profile revision")
            if profile.revision == row["revision"]:
                return
            current = {item["key_id"]: item for item in connection.execute("SELECT * FROM auth_keys")}
            for key in profile.keys:
                previous = current.get(key.key_id)
                if previous is not None and (previous["identity"] != key.identity() or previous["revoked"] and not key.revoked):
                    raise ValueError("key IDs cannot be reassigned or unrevoked; rotate with a new ID")
            active = {key.key_id for key in profile.keys if not key.revoked}
            for key_id in current:
                if key_id not in active:
                    connection.execute("UPDATE auth_keys SET revoked=1 WHERE key_id=?", (key_id,))
            for key in profile.keys:
                connection.execute("INSERT INTO auth_keys VALUES(?,?,?) ON CONFLICT(key_id) DO UPDATE SET revoked=excluded.revoked",
                                   (key.key_id, key.identity(), int(key.revoked)))
            connection.execute("UPDATE auth_config SET revision=?,fingerprint=? WHERE singleton=1", (profile.revision, profile.fingerprint()))
            self._audit(connection, "profile_configured")

    def consume(self, key, *, timestamp_ms, nonce, request_hash, clock_ms):
        nonce_hash = hashlib.sha256(nonce.encode("ascii")).hexdigest()
        error = None
        with self._transaction() as connection:
            config = self._config(connection)
            # Sample after acquiring BEGIN IMMEDIATE. Concurrent callers must
            # not present stale pre-lock samples as a fictitious clock rollback.
            try:
                server_ms = clock_ms()
                _integer(server_ms, "server clock")
            except Exception:
                raise SigningError("auth_clock_unavailable", "trusted server authentication clock unavailable", 503) from None
            if server_ms < config["highwater"]:
                error = SigningError("auth_clock_regressed", "server wall clock is behind durable authentication highwater", 503)
            else:
                connection.execute("UPDATE auth_config SET highwater=? WHERE singleton=1", (server_ms,))
                # Strict '<': a timestamp at the oldest allowed boundary is
                # still replayable and its nonce must remain present.
                connection.execute("DELETE FROM auth_nonces WHERE expires_ms < ?", (server_ms,))
                stored = connection.execute("SELECT * FROM auth_keys WHERE key_id=?", (key.key_id,)).fetchone()
                if stored is None or stored["revoked"] or stored["identity"] != key.identity() or key.revoked:
                    error = SigningError("signing_key_inactive", "signing key is not active")
                elif not key.not_before_ms <= server_ms < key.expires_at_ms or not key.not_before_ms <= timestamp_ms < key.expires_at_ms:
                    error = SigningError("signing_key_inactive", "signing key is outside its validity period")
                elif not -config["future_skew"] <= server_ms - timestamp_ms <= config["past_window"] or timestamp_ms > _MAX_INT - config["past_window"]:
                    error = SigningError("request_timestamp_out_of_window", "request timestamp is outside the accepted window")
                elif connection.execute("SELECT 1 FROM auth_nonces WHERE key_id=? AND nonce_hash=?", (key.key_id, nonce_hash)).fetchone():
                    error = SigningError("request_replayed", "request nonce was already consumed", 409)
                elif connection.execute("SELECT COUNT(*) FROM auth_nonces").fetchone()[0] >= config["max_nonces"]:
                    error = SigningError("signing_capacity_exhausted", "replay protection capacity exhausted; no unsafe eviction", 503)
                else:
                    connection.execute("INSERT INTO auth_nonces VALUES(?,?,?)", (key.key_id, nonce_hash, timestamp_ms + config["past_window"]))
            self._audit(connection, error.code if error else "nonce_consumed", key_id=key.key_id,
                        nonce_hash=nonce_hash, request_hash=request_hash, request_ms=timestamp_ms, server_ms=server_ms)
        # Both success and authenticated-denial audit commit before returning.
        if error:
            raise error


class RequestAuthenticator:
    def __init__(self, store: NonceStore, profile: SigningProfile, *, clock_ms=None):
        if not isinstance(store, NonceStore) or not isinstance(profile, SigningProfile):
            raise ValueError("validated nonce store and signing profile are required")
        if clock_ms is not None and not callable(clock_ms):
            raise ValueError("clock_ms must be callable")
        self.store, self._profile = store, profile
        self._lock = RLock()
        self.clock_ms = clock_ms or (lambda: time.time_ns() // 1000000)
        self.store.configure(profile)

    def replace_profile(self, profile):
        if not isinstance(profile, SigningProfile):
            raise ValueError("validated signing profile required")
        with self._lock:
            self.store.configure(profile)
            self._profile = profile

    def authenticate(self, headers, *, method, request_target, body):
        names = ("Authorization", "X-UTA-Version", "X-UTA-Tenant", "X-UTA-Audience", "X-UTA-Key-Id",
                 "X-UTA-Timestamp-Ms", "X-UTA-Nonce", "X-UTA-Signature")
        values = {}
        try:
            for name in names:
                found = headers.get_all(name, []) if hasattr(headers, "get_all") else ([headers[name]] if name in headers else [])
                if len(found) != 1 or not isinstance(found[0], str) or len(found[0]) > 256:
                    raise ValueError("missing or duplicate signing header")
                values[name] = found[0]
            if values["Authorization"].lower() != _AUTH_HEADER.lower() or values["X-UTA-Version"] != "1":
                raise ValueError("unsupported authentication profile")
            timestamp = values["X-UTA-Timestamp-Ms"]
            if not re.fullmatch(r"0|[1-9][0-9]{0,18}", timestamp, re.ASCII) or not _HEX.fullmatch(values["X-UTA-Signature"]):
                raise ValueError("invalid signing field")
            timestamp = int(timestamp)
            with self._lock:
                profile = self._profile
                key = next((key for key in profile.keys if key.key_id == values["X-UTA-Key-Id"]), None)
            canonical = canonical_request(tenant_id=values["X-UTA-Tenant"], audience=values["X-UTA-Audience"],
                key_id=values["X-UTA-Key-Id"], timestamp_ms=timestamp, nonce=values["X-UTA-Nonce"],
                method=method, request_target=request_target, body=body)
        except (ValueError, TypeError, KeyError):
            raise SigningError("signature_required", "valid HMAC request authentication is required") from None
        expected = hmac.new(key.secret if key is not None else b"\0" * 32, canonical, hashlib.sha256).hexdigest()
        matched = hmac.compare_digest(expected, values["X-UTA-Signature"])
        if not matched or key is None or (values["X-UTA-Tenant"], values["X-UTA-Audience"]) != (profile.tenant_id, profile.audience):
            raise SigningError("invalid_signature", "request signature is invalid")
        self.store.consume(key, timestamp_ms=timestamp, nonce=values["X-UTA-Nonce"],
                           request_hash=hashlib.sha256(canonical).hexdigest(), clock_ms=self.clock_ms)
        return key.principal()
