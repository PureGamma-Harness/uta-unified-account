"""Default-disabled, fresh AuthDB-only credit authentication observations.

No financial source, inbox, loan, native writer, endpoint or READY transition is
implemented here. All opaque observations explicitly deny financial permission.
The service binary and OS owner are trusted; remote JSON cannot mint a handle.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
import re
import secrets
import sqlite3
from threading import BoundedSemaphore, RLock, current_thread
import time
from types import MappingProxyType
from uuid import uuid4

from .credit_auth_h0_schema import SCHEMA_SQL, OBJECTS, COLUMNS, INDEXES, FOREIGN_KEYS
from .request_signing import (SigningError, _ExistingAuthDatabase, _HEX, _ID,
    _MAX_INT, _id, _integer, _json, _nonce_precheck, _nonce_finish, _verify_request,
    load_profile)
from .storage import StorageError, _publish_private_database


_DEFAULTS = MappingProxyType({"past_window": 30000, "future_skew": 5000,
    "max_nonces": 2048, "query_nonce_reserve": 128, "max_audit": 8192,
    "query_audit_reserve": 512, "control_audit_reserve": 64,
    "max_acceptances": 256, "max_grants": 64})
_QUERY = re.compile(r"/v2/accounts/([A-Za-z0-9][A-Za-z0-9_.:-]{0,127})/credit/commands/([A-Za-z0-9][A-Za-z0-9_.:-]{0,127})\Z", re.ASCII)
_CAPTURE = re.compile(r"/v2/accounts/([A-Za-z0-9][A-Za-z0-9_.:-]{0,127})/(borrow|repay)\Z", re.ASCII)
_AMOUNT = re.compile(r"(0|[1-9][0-9]{0,29})(?:\.([0-9]{1,8}))?\Z", re.ASCII)
_FALSE = {"financial_authorized": False, "source_delivery_authorized": False,
          "execution_authorized": False}
_SEAL = object()


class CreditAuthError(SigningError):
    pass


def _error(code, status=403):
    # No request bytes, keys, nonce values or authority paths enter messages.
    return CreditAuthError(code, "credit authentication observation refused", status)


def _digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _document(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate field")
            result[key] = value
        return result
    if type(raw) is not str or len(raw.encode("utf-8")) > 65536:
        raise StorageError("invalid retained authentication document")
    try:
        def integer(value):
            if len(value) > 20:raise ValueError()
            result = int(value)
            if not -_MAX_INT <= result <= _MAX_INT:raise ValueError()
            return result
        def no_number(_):raise ValueError()
        value = json.loads(raw, object_pairs_hook=pairs, parse_int=integer,
                           parse_float=no_number, parse_constant=no_number)
        if type(value) is not dict or _json(value) != raw:
            raise ValueError()
        return value
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise StorageError("invalid retained authentication document") from None


def _limits(values):
    if values is not None and (type(values) is not dict or set(values)-set(_DEFAULTS)):
        raise ValueError("unsupported auth limit configuration")
    result = {**_DEFAULTS, **(values or {})}
    for name, value in result.items():
        _integer(value, name, 0 if name == "future_skew" else 1, 1000000)
    if (result["past_window"] > 300000 or result["future_skew"] > 30000
            or result["query_nonce_reserve"] >= result["max_nonces"]
            or result["query_audit_reserve"] + result["control_audit_reserve"] >= result["max_audit"]
            or result["max_acceptances"] > 10000 or result["max_grants"] > 10000):
        raise ValueError("invalid authentication admission limits")
    return result


def _verify_schema(connection):
    actual = {row[0]: tuple(row[1:]) for row in connection.execute(
        "SELECT name,type,tbl_name,sql FROM main.sqlite_master")}
    if actual != OBJECTS:
        raise StorageError("fresh authentication MAIN object definitions changed")
    if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        raise StorageError("authentication foreign keys must remain enabled")
    for table, columns in COLUMNS.items():
        observed = tuple(tuple(row) for row in connection.execute(
            'PRAGMA main.table_xinfo("'+table+'")'))
        if observed != columns:
            raise StorageError("fresh authentication MAIN columns changed")
        observed_fk = tuple(sorted((r[2], r[3], r[4], r[1], r[5], r[6], r[7])
            for r in connection.execute('PRAGMA main.foreign_key_list("'+table+'")')))
        if observed_fk != FOREIGN_KEYS[table]:
            raise StorageError("fresh authentication foreign-key definition changed")
        actual_indexes = {r[1]: (r[2], r[3], r[4]) for r in connection.execute(
            'PRAGMA main.index_list("'+table+'")')}
        expected = {n: (v[2], v[3], 0) for n, v in INDEXES.items() if v[0] == table}
        if actual_indexes != expected:
            raise StorageError("fresh authentication index inventory changed")
    for name, (_, columns, _, _) in INDEXES.items():
        if tuple(r[2] for r in connection.execute('PRAGMA main.index_info("'+name+'")')) != columns:
            raise StorageError("fresh authentication index identity changed")
    if connection.execute("PRAGMA main.foreign_key_check").fetchone() is not None:
        raise StorageError("fresh authentication foreign keys are inconsistent")


class _PinnedAuthDatabase(_ExistingAuthDatabase):
    def __init__(self, path):
        super().__init__(path, timeout=1)
        self._auth_identity = super()._private_file()

    def _private_file(self):
        identity = super()._private_file()
        if identity != self._auth_identity:
            raise StorageError("authentication authority inode changed")
        return identity


class CreditNonceStoreV2:
    """Exact fresh format2, deliberately not a legacy NonceStore subclass."""
    @classmethod
    def initialize(cls, path, *, tenant_id, producer_binding, domain_id,
                   domain_epoch=1, account_id, limits=None):
        for name, value in (("tenant_id", tenant_id), ("domain_id", domain_id),
                            ("account_id", account_id)):
            _id(value, name)
        if type(producer_binding) is not str or not _HEX.fullmatch(producer_binding):
            raise ValueError("exact producer identity is required")
        if type(domain_epoch) is not int or domain_epoch != 1:
            raise ValueError("only a fresh first auth domain epoch is supported")
        limit = _limits(limits)
        database = _ExistingAuthDatabase(path, timeout=1)
        _publish_private_database(database.path)
        with database.transaction() as connection:
            for statement in SCHEMA_SQL:
                connection.execute(statement)
            record = {"singleton": 1, "format": 2, "canonical_path": database.path,
                "auth_authority_id": "auth:"+uuid4().hex, "tenant": tenant_id,
                "audience": "uta:"+uuid4().hex, "producer_binding": producer_binding,
                "domain_id": domain_id, "domain_epoch": domain_epoch,
                "account_id": account_id, **limit, "highwater": 0,
                "revision": 0, "grant_revision": 0, "fingerprint": ""}
            names = tuple(record)
            connection.execute("INSERT INTO main.auth_config("+",".join(names)+") VALUES("+
                ",".join("?" for _ in names)+")", tuple(record[n] for n in names))
            _verify_schema(connection)
        return cls(path)

    def __init__(self, path):
        try:
            self.database = _PinnedAuthDatabase(path)
        except (StorageError, sqlite3.Error, OSError) as cause:
            raise _error("credit_auth_outcome_unknown", 503) from cause
        self._scope = None
        with self._transaction(read=True) as connection:
            config = self._config(connection)
        self._scope = tuple(config[n] for n in ("auth_authority_id", "tenant", "audience",
            "producer_binding", "domain_id", "domain_epoch", "account_id"))
        self.tenant_id, self.audience, self.producer_binding = config["tenant"], config["audience"], config["producer_binding"]

    @contextmanager
    def _transaction(self, read=False):
        try:
            with (self.database.read_transaction() if read else self.database.transaction()) as connection:
                yield connection
        except (StorageError, sqlite3.Error, OSError) as cause:
            raise _error("credit_auth_outcome_unknown", 503) from cause

    def _config(self, connection):
        _verify_schema(connection)
        rows = connection.execute("SELECT * FROM main.auth_config").fetchall()
        if len(rows) != 1:
            raise StorageError("fresh authentication config is incomplete")
        config = dict(rows[0])
        if config["format"] != 2 or config["canonical_path"] != self.database.path:
            raise StorageError("authentication authority was moved or has an unknown format")
        for name in ("auth_authority_id", "tenant", "audience", "domain_id", "account_id"):
            _id(config[name], name)
        if type(config["producer_binding"]) is not str or not _HEX.fullmatch(config["producer_binding"]):
            raise StorageError("invalid authentication producer identity")
        _limits({n: config[n] for n in _DEFAULTS})
        for name in ("highwater", "revision", "grant_revision"):
            _integer(config[name], name)
        if config["domain_epoch"] != 1 or (config["revision"] and not _HEX.fullmatch(config["fingerprint"])):
            raise StorageError("invalid authentication revision")
        scope = tuple(config[n] for n in ("auth_authority_id", "tenant", "audience",
            "producer_binding", "domain_id", "domain_epoch", "account_id"))
        if self._scope is not None and self._scope != scope:
            raise StorageError("authentication logical authority changed")
        self._verify_grant_data(connection, config)
        return config

    @staticmethod
    def _verify_grant_data(connection, config):
        """Check retained descriptors against actual immutable control history.

        Structured columns alone are not the whole persisted grant contract.
        This runs on every supported load/use before any request/control DML.
        It neither repairs old rows nor infers historical evidence from a key's
        currently loaded profile.
        """
        expected_sequences = set()
        profiles = tuple(connection.execute(
            "SELECT sequence,revision FROM main.auth_audit WHERE event='profile_configured' AND outcome='CONTROL' AND request_kind='CONTROL'"))
        previous_epoch = previous_sequence = 0
        for row in connection.execute("SELECT * FROM main.auth_credit_grants ORDER BY grant_epoch"):
            expected = {name: row[name] for name in row.keys() if name != "payload"}
            try:
                document = _document(row["payload"])
            except StorageError as cause:
                raise StorageError("retained authentication grant payload is not canonical") from cause
            if (set(document) != set(expected) or any(type(document[name]) is not type(value)
                    or document[name] != value for name, value in expected.items())):
                raise StorageError("retained authentication grant payload differs from columns")
            if (any(type(row[name]) is not str or not _ID.fullmatch(row[name])
                    for name in ("grant_id", "key_id", "account_id"))
                    or row["account_id"] != config["account_id"] or row["asset"] != "BTC"
                    or row["operation"] not in ("credit.borrow", "credit.repay", "credit.read")
                    or not previous_epoch < row["grant_epoch"] <= config["grant_revision"]
                    or not previous_sequence < row["audit_sequence"] <= _MAX_INT):
                raise StorageError("retained authentication grant identity is inconsistent")
            key = connection.execute("SELECT * FROM main.auth_keys WHERE key_id=?", (row["key_id"],)).fetchone()
            audit = connection.execute("SELECT * FROM main.auth_audit WHERE sequence=?", (row["audit_sequence"],)).fetchone()
            allowed_roles = ("reader", "funding") if row["operation"] == "credit.read" else ("funding",)
            if (key is None or key["account_id"] != row["account_id"] or key["role"] not in allowed_roles
                    or audit is None or audit["event"] != "grant_created" or audit["outcome"] != "CONTROL"
                    or audit["request_kind"] != "CONTROL" or audit["grant_id"] != row["grant_id"]
                    or audit["key_id"] != row["key_id"] or audit["key_identity"] != key["identity"]
                    or audit["grant_revision"] != row["grant_epoch"]
                    or not 1 <= audit["revision"] <= config["revision"]
                    or not any(p[0] < audit["sequence"] and p[1] == audit["revision"] for p in profiles)
                    or type(audit["server_ms"]) is not int
                    or not key["not_before_ms"] <= audit["server_ms"] < key["expires_at_ms"]
                    or audit["server_ms"] > config["highwater"]
                    or any(audit[name] is not None for name in
                        ("nonce_hash", "request_hash", "request_ms", "business_key", "original_acceptance_id"))):
                raise StorageError("retained authentication grant differs from original control audit")
            expected_sequences.add(row["audit_sequence"])
            previous_epoch, previous_sequence = row["grant_epoch"], row["audit_sequence"]
        actual_sequences = {row[0] for row in connection.execute(
            "SELECT sequence FROM main.auth_audit WHERE event='grant_created'")}
        if actual_sequences != expected_sequences:
            raise StorageError("retained authentication grant audit has missing or orphan evidence")
        revocation_sequences = set()
        epochs = [row[0] for row in connection.execute(
            "SELECT grant_epoch FROM main.auth_credit_grants")]
        for row in connection.execute("SELECT * FROM main.auth_credit_grant_revocations ORDER BY revocation_revision"):
            expected = {name: row[name] for name in row.keys() if name != "payload"}
            try:
                document = _document(row["payload"])
            except StorageError as cause:
                raise StorageError("retained authentication revocation payload is not canonical") from cause
            if (set(document) != set(expected) or any(type(document[name]) is not type(value)
                    or document[name] != value for name, value in expected.items())):
                raise StorageError("retained authentication revocation payload differs from columns")
            grant = connection.execute("SELECT * FROM main.auth_credit_grants WHERE grant_id=?", (row["grant_id"],)).fetchone()
            audit = connection.execute("SELECT * FROM main.auth_audit WHERE sequence=?", (row["audit_sequence"],)).fetchone()
            original = (connection.execute("SELECT server_ms FROM main.auth_audit WHERE sequence=?",
                (grant["audit_sequence"],)).fetchone() if grant is not None else None)
            if (grant is None or not grant["grant_epoch"] < row["revocation_revision"] <= config["grant_revision"]
                    or not grant["audit_sequence"] < row["audit_sequence"] <= _MAX_INT
                    or audit is None or audit["event"] != "grant_revoked" or audit["outcome"] != "CONTROL"
                    or audit["request_kind"] != "CONTROL" or audit["grant_id"] != row["grant_id"]
                    or audit["grant_revision"] != row["revocation_revision"]
                    or not 1 <= audit["revision"] <= config["revision"]
                    or not any(p[0] < audit["sequence"] and p[1] == audit["revision"] for p in profiles)
                    or original is None or type(audit["server_ms"]) is not int
                    or not original[0] <= audit["server_ms"] <= config["highwater"]
                    or any(audit[name] is not None for name in
                        ("key_id", "key_identity", "nonce_hash", "request_hash", "request_ms",
                         "business_key", "original_acceptance_id"))):
                raise StorageError("retained authentication revocation differs from original control audit")
            revocation_sequences.add(row["audit_sequence"])
            epochs.append(row["revocation_revision"])
        actual_revocations = {row[0] for row in connection.execute(
            "SELECT sequence FROM main.auth_audit WHERE event='grant_revoked'")}
        if actual_revocations != revocation_sequences:
            raise StorageError("retained authentication revocation audit has missing or orphan evidence")
        if sorted(epochs) != list(range(1, len(epochs)+1)) or config["grant_revision"] != len(epochs):
            raise StorageError("retained authentication grant revision differs from complete history")

    @staticmethod
    def _stamp(connection, config):
        now = time.time_ns()//1000000
        _integer(now, "actual authentication clock")
        if now < config["highwater"]:
            raise _error("auth_clock_regressed", 503)
        connection.execute("UPDATE main.auth_config SET highwater=? WHERE singleton=1", (now,))
        return now

    @staticmethod
    def _audit(connection, config, *, event, outcome, request_kind,
               key_id=None, key_identity=None, nonce_hash=None, request_hash=None,
               request_ms=None, server_ms=None, business_key=None, grant_id=None,
               original_acceptance_id=None, query=False, control=False):
        limit = config["max_audit"]
        if not control:
            limit -= config["control_audit_reserve"]
            if not query:
                limit -= config["query_audit_reserve"]
        if connection.execute("SELECT COUNT(*) FROM main.auth_audit").fetchone()[0] >= limit:
            raise _error("credit_auth_outcome_unknown", 503)
        cursor = connection.execute("""INSERT INTO main.auth_audit(
            event,outcome,request_kind,key_id,key_identity,nonce_hash,request_hash,
            request_ms,server_ms,revision,grant_revision,business_key,grant_id,original_acceptance_id)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (event, outcome, request_kind, key_id, key_identity, nonce_hash, request_hash,
             request_ms, server_ms, config["revision"], config["grant_revision"],
             business_key, grant_id, original_acceptance_id))
        return cursor.lastrowid

    def configure(self, profile):
        if (profile.tenant_id, profile.audience) != (self.tenant_id, self.audience):
            raise ValueError("profile belongs to another authentication authority")
        with self._transaction() as connection:
            config = self._config(connection)
            if (profile.revision < config["revision"] or profile.revision == config["revision"]
                    and profile.fingerprint() != config["fingerprint"]):
                raise ValueError("stale or conflicting signing profile")
            if profile.revision == config["revision"]:
                return
            current = {r["key_id"]: r for r in connection.execute("SELECT * FROM main.auth_keys")}
            if len(set(current) | {k.key_id for k in profile.keys}) > 1024:
                raise _error("credit_auth_key_history_capacity", 503)
            for key in profile.keys:
                previous = current.get(key.key_id)
                if previous is not None and (previous["identity"] != key.identity()
                        or previous["revoked"] and not key.revoked):
                    raise ValueError("key identity cannot be reassigned or unrevoked")
            active = {k.key_id for k in profile.keys if not k.revoked}
            for key_id in current:
                if key_id not in active:
                    connection.execute("UPDATE main.auth_keys SET revoked=1 WHERE key_id=?", (key_id,))
            for key in profile.keys:
                # BEFORE INSERT no-replace runs before UPSERT. Existing rows
                # therefore use explicit UPDATE after the actual locked SELECT.
                if key.key_id in current:
                    connection.execute("UPDATE main.auth_keys SET revoked=? WHERE key_id=?",
                                       (int(key.revoked), key.key_id))
                else:
                    connection.execute("INSERT INTO main.auth_keys VALUES(?,?,?,?,?,?,?)",
                        (key.key_id, key.identity(), key.role, key.account_id,
                         key.not_before_ms, key.expires_at_ms, int(key.revoked)))
            connection.execute("UPDATE main.auth_config SET revision=?,fingerprint=? WHERE singleton=1",
                               (profile.revision, profile.fingerprint()))
            config.update(revision=profile.revision, fingerprint=profile.fingerprint())
            self._audit(connection, config, event="profile_configured", outcome="CONTROL",
                        request_kind="CONTROL", server_ms=self._stamp(connection, config), control=True)

    @staticmethod
    def _grant(connection, key_id, account, operation):
        rows = connection.execute("""SELECT g.* FROM main.auth_credit_grants g
            JOIN main.auth_keys k ON k.key_id=g.key_id
            WHERE g.key_id=? AND g.account_id=? AND g.asset='BTC' AND g.operation=?
            AND k.revoked=0 AND k.account_id=g.account_id
            AND ((g.operation='credit.read' AND k.role IN ('reader','funding'))
                 OR (g.operation!='credit.read' AND k.role='funding'))
            AND NOT EXISTS (SELECT 1 FROM main.auth_credit_grant_revocations r WHERE r.grant_id=g.grant_id)""",
            (key_id, account, operation)).fetchall()
        if len(rows) > 1:
            raise StorageError("ambiguous current exact grant")
        return dict(rows[0]) if rows else None

    def put_grant(self, grant_id, *, key_id, account_id, asset, operation,
                  expected_grant_revision):
        for name, value in (("grant_id", grant_id), ("key_id", key_id), ("account_id", account_id)):
            _id(value, name)
        _integer(expected_grant_revision, "expected_grant_revision")
        if asset != "BTC" or operation not in ("credit.borrow", "credit.repay", "credit.read"):
            raise ValueError("unsupported exact authentication grant")
        with self._transaction() as connection:
            config = self._config(connection)
            existing = connection.execute("SELECT * FROM main.auth_credit_grants WHERE grant_id=?", (grant_id,)).fetchone()
            binding = (key_id, account_id, asset, operation)
            if existing is not None:
                if tuple(existing[n] for n in ("key_id", "account_id", "asset", "operation")) != binding:
                    raise _error("grant_identity_conflict", 409)
                return {"grant_id": grant_id, "grant_epoch": existing["grant_epoch"], **_FALSE}
            if config["grant_revision"] != expected_grant_revision:
                raise _error("grant_revision_conflict", 409)
            key = connection.execute("SELECT * FROM main.auth_keys WHERE key_id=?", (key_id,)).fetchone()
            now = self._stamp(connection, config)
            if (key is None or key["revoked"] or account_id != config["account_id"]
                    or key["account_id"] != account_id or not key["not_before_ms"] <= now < key["expires_at_ms"]
                    or key["role"] not in (("reader", "funding") if operation == "credit.read" else ("funding",))):
                raise _error("credit_grant_forbidden")
            if self._grant(connection, key_id, account_id, operation) is not None:
                raise _error("grant_identity_conflict", 409)
            if connection.execute("SELECT COUNT(*) FROM main.auth_credit_grants").fetchone()[0] >= config["max_grants"]:
                raise _error("credit_auth_grant_capacity", 503)
            epoch = config["grant_revision"] + 1
            _integer(epoch, "grant epoch", 1)
            connection.execute("UPDATE main.auth_config SET grant_revision=? WHERE singleton=1", (epoch,))
            config["grant_revision"] = epoch
            sequence = self._audit(connection, config, event="grant_created", outcome="CONTROL",
                request_kind="CONTROL", key_id=key_id, key_identity=key["identity"], server_ms=now,
                grant_id=grant_id, control=True)
            payload = _json({"grant_id": grant_id, "key_id": key_id, "account_id": account_id,
                "asset": asset, "operation": operation, "grant_epoch": epoch, "audit_sequence": sequence})
            connection.execute("INSERT INTO main.auth_credit_grants VALUES(?,?,?,?,?,?,?,?)",
                (grant_id, key_id, account_id, asset, operation, epoch, sequence, payload))
            result = {"grant_id": grant_id, "grant_epoch": epoch, **_FALSE}
        return result

    def revoke_grant(self, grant_id, *, expected_grant_revision):
        _id(grant_id, "grant_id")
        _integer(expected_grant_revision, "expected_grant_revision")
        with self._transaction() as connection:
            config = self._config(connection)
            old = connection.execute("SELECT * FROM main.auth_credit_grant_revocations WHERE grant_id=?", (grant_id,)).fetchone()
            if old is not None:
                return {"grant_id": grant_id, "revocation_revision": old["revocation_revision"], **_FALSE}
            grant = connection.execute("SELECT * FROM main.auth_credit_grants WHERE grant_id=?", (grant_id,)).fetchone()
            if grant is None:
                raise _error("grant_not_found", 404)
            if config["grant_revision"] != expected_grant_revision:
                raise _error("grant_revision_conflict", 409)
            revision = config["grant_revision"] + 1
            _integer(revision, "grant revision", 1)
            connection.execute("UPDATE main.auth_config SET grant_revision=? WHERE singleton=1", (revision,))
            config["grant_revision"] = revision
            now = self._stamp(connection, config)
            sequence = self._audit(connection, config, event="grant_revoked", outcome="CONTROL",
                request_kind="CONTROL", server_ms=now, grant_id=grant_id, control=True)
            payload = _json({"grant_id": grant_id, "revocation_revision": revision,
                             "audit_sequence": sequence})
            connection.execute("INSERT INTO main.auth_credit_grant_revocations VALUES(?,?,?,?)",
                               (grant_id, revision, sequence, payload))
            result = {"grant_id": grant_id, "revocation_revision": revision, **_FALSE}
        return result

    @staticmethod
    def _first(connection, config, command_id):
        row = connection.execute("""SELECT * FROM main.auth_credit_acceptances
            WHERE domain_id=? AND tenant=? AND account_id=? AND command_id=?""",
            (config["domain_id"], config["tenant"], config["account_id"], command_id)).fetchone()
        if row is None:
            return None
        record = dict(row)
        evidence = _document(record["payload"])
        if (record["acceptance_id"] != "auth-acceptance:"+_digest(record["payload"])
                or type(evidence.get("format")) is not int or evidence.get("format") != 1 or evidence.get("receipt_kind") != "auth_first_observation"
                or any(evidence.get(n) is not False for n in _FALSE)):
            raise StorageError("first authentication acceptance is inconsistent")
        expected_fields = {"format", "receipt_kind", "auth_authority_id", "domain_id", "domain_epoch",
            "tenant_id", "audience", "producer_binding", "account_id", "command_id", "kind",
            "command_payload", "payload_hash", "key_id", "key_identity", "grant_id", "grant_epoch",
            "profile_revision", "grant_revision", "auth_audit_sequence", "request_hash", "body_hash",
            "nonce_hash", "request_ms", "auth_checked_server_ms", *_FALSE}
        if set(evidence) != expected_fields or any(evidence[n] != config[c] for n, c in
                (("auth_authority_id", "auth_authority_id"), ("audience", "audience"),
                 ("producer_binding", "producer_binding"))):
            raise StorageError("first authentication field or authority binding changed")
        for n in ("domain_epoch", "grant_epoch", "profile_revision", "grant_revision",
                  "auth_audit_sequence", "request_ms", "auth_checked_server_ms"):
            if type(evidence[n]) is not int or not 0 <= evidence[n] <= _MAX_INT:
                raise StorageError("first authentication integer is noncanonical")
        for n in ("payload_hash", "key_identity", "request_hash", "body_hash", "nonce_hash"):
            if type(evidence[n]) is not str or not _HEX.fullmatch(evidence[n]):
                raise StorageError("first authentication digest is invalid")
        if _digest(record["command_payload"]) != record["payload_hash"]:
            raise StorageError("first authentication business payload changed")
        mapping = {"tenant": "tenant_id", "profile_revision": "profile_revision"}
        for name in record:
            if name not in ("payload", "acceptance_id") and evidence.get(mapping.get(name, name)) != record[name]:
                raise StorageError("first authentication identity differs from payload")
        audit = connection.execute("SELECT * FROM main.auth_audit WHERE sequence=?", (record["auth_audit_sequence"],)).fetchone()
        if audit is None or audit["event"] != "nonce_consumed" or audit["outcome"] != "FIRST_ACCEPTED":
            raise StorageError("first authentication acceptance lacks its original nonce audit")
        compare = {"key_id": "key_id", "key_identity": "key_identity", "grant_id": "grant_id",
                   "request_hash": "request_hash", "nonce_hash": "nonce_hash", "request_ms": "request_ms",
                   "server_ms": "auth_checked_server_ms", "revision": "profile_revision",
                   "grant_revision": "grant_revision", "request_kind": "kind"}
        if any(audit[k] != record[v] for k, v in compare.items()):
            raise StorageError("first authentication audit binding changed")
        return record


@dataclass(frozen=True)
class _Decision:
    kind: str
    command_id: str | None
    payload: str | None
    operation_grant: object
    query_grant: object
    first: object
    query: bool
    error: object
    outcome: str


def _business(method, target, body, lookup):
    try:
        if lookup:
            match = _QUERY.fullmatch(target) if type(target) is str else None
            if method != "GET" or match is None or body != b"":
                raise ValueError()
            return "AUTH_QUERY", match[1], match[2], None
        match = _CAPTURE.fullmatch(target) if type(target) is str else None
        if method != "POST" or match is None:
            raise ValueError()
        def pairs(items):
            result = {}
            for k, v in items:
                if k in result:raise ValueError()
                result[k] = v
            return result
        def no_number(_):raise ValueError()
        data = json.loads(body.decode("utf-8"), object_pairs_hook=pairs,
                          parse_int=no_number, parse_float=no_number, parse_constant=no_number)
        if type(data) is not dict or set(data) != {"command_id", "asset", "amount"}:
            raise ValueError()
        if type(data["command_id"]) is not str or not _ID.fullmatch(data["command_id"]) or data["asset"] != "BTC" or type(data["amount"]) is not str:
            raise ValueError()
        amount = _AMOUNT.fullmatch(data["amount"])
        if amount is None:raise ValueError()
        units = int(amount[1])*100000000+int((amount[2] or "").ljust(8, "0"))
        if not 0 < units < 10**38:raise ValueError()
        whole, fraction = divmod(units, 100000000)
        normalized = str(whole)+(("."+f"{fraction:08d}".rstrip("0")) if fraction else "")
        return match[2].upper(), match[1], data["command_id"], _json({"account_id": match[1], "asset": "BTC", "amount": normalized})
    except (TypeError, ValueError, UnicodeError, RecursionError, AttributeError):
        raise _error("credit_auth_input_invalid", 400) from None


class _Observation:
    __slots__ = ()
    def __init__(self, seal):
        if seal is not _SEAL:
            raise TypeError("authentication observations are issued locally")
    def __reduce_ex__(self, _):
        raise TypeError("authentication observations cannot be copied or serialized")


class CreditHmacIngressV2:
    def __init__(self, auth_database, profile_path, *, tenant_id, producer_binding,
                 domain_id, domain_epoch, account_id, enabled=False,
                 max_handles=256, query_handle_reserve=32):
        if enabled is not True:
            raise _error("credit_auth_disabled", 501)
        _integer(max_handles, "max_handles", 2, 10000)
        _integer(query_handle_reserve, "query_handle_reserve", 1, max_handles-1)
        _integer(domain_epoch, "domain_epoch", 1, 1)
        self._pid = os.getpid()
        self._boot = secrets.token_hex(32)
        self._lock, self._profile_lock = RLock(), RLock()
        self._intake = BoundedSemaphore(max_handles)
        self._slots, self._handles = {}, {}
        self._max, self._query_reserve = max_handles, query_handle_reserve
        self.store = CreditNonceStoreV2(auth_database)
        with self.store._transaction(read=True) as connection:
            config = self.store._config(connection)
        if (tenant_id, producer_binding, domain_id, domain_epoch, account_id) != tuple(config[n]
                for n in ("tenant", "producer_binding", "domain_id", "domain_epoch", "account_id")):
            raise ValueError("trusted authentication scope does not match actual authority")
        self._profile = load_profile(profile_path)
        self.store.configure(self._profile)

    def _process(self):
        if os.getpid() != self._pid:
            raise _error("credit_auth_process_mismatch")

    def replace_profile(self, profile_path):
        self._process()
        profile = load_profile(profile_path)
        with self._profile_lock:
            self.store.configure(profile)
            self._profile = profile

    def _reserve(self, query):
        # No holder of this short registry lock waits for a DB/profile lock.
        with self._lock:
            limit = self._max if query else self._max-self._query_reserve
            if len(self._slots) >= limit:
                return None
            token = object()
            self._slots[token] = (current_thread(), query)
            return token

    def _classify(self, connection, config, verified, method, target, body, lookup):
        try:
            kind, account, cid, payload = _business(method, target, body, lookup)
        except CreditAuthError as error:
            return _Decision("AUTH_QUERY" if lookup else "AUTH_OTHER", None, None, None, None, None, False, error, "INPUT_REJECTED")
        key = verified.key
        stored = connection.execute("SELECT * FROM main.auth_keys WHERE key_id=?", (key.key_id,)).fetchone()
        if stored is None or tuple(stored[n] for n in ("identity", "role", "account_id", "not_before_ms", "expires_at_ms")) != (key.identity(), key.role, key.account_id, key.not_before_ms, key.expires_at_ms):
            raise StorageError("actual stored authentication key metadata differs")
        if account != config["account_id"] or key.account_id != account:
            return _Decision(kind, cid, payload, None, None, None, False, _error("credit_auth_forbidden"), "PERMISSION_REJECTED")
        read = self.store._grant(connection, key.key_id, account, "credit.read")
        if lookup:
            if key.role not in ("reader", "funding") or read is None:
                return _Decision(kind, cid, payload, None, None, None, False, _error("credit_auth_forbidden"), "PERMISSION_REJECTED")
            first = self.store._first(connection, config, cid)
            return _Decision(kind, cid, None, read, read, first, True, None,
                             "QUERY_ORIGINAL" if first else "QUERY_MISS")
        operation = "credit.borrow" if kind == "BORROW" else "credit.repay"
        grant = self.store._grant(connection, key.key_id, account, operation)
        if key.role != "funding" or grant is None:
            return _Decision(kind, cid, payload, None, read, None, False, _error("credit_auth_forbidden"), "PERMISSION_REJECTED")
        first = self.store._first(connection, config, cid)
        if first is not None:
            if (first["kind"], first["command_payload"]) != (kind, payload):
                return _Decision(kind, cid, payload, grant, read, first, False, _error("idempotency_conflict", 409), "CID_CONFLICT")
            if read is None:
                return _Decision(kind, cid, payload, grant, None, first, False, _error("credit_auth_forbidden"), "PERMISSION_REJECTED")
            return _Decision(kind, cid, payload, read, read, first, True, None, "QUERY_ORIGINAL")
        return _Decision(kind, cid, payload, grant, read, None, False, None, "FIRST_ACCEPTED")

    def _request(self, headers, *, method, request_target, body, lookup):
        self._process()
        if not self._intake.acquire(blocking=False):
            raise _error("credit_auth_intake_capacity", 503)
        slot = None
        try:
            with self._profile_lock:
                profile = self._profile
            verified = _verify_request(profile, headers, method=method,
                                       request_target=request_target, body=body)
            error = None
            with self.store._transaction() as connection:
                config = self.store._config(connection)
                checked = _nonce_precheck(connection, config, verified.key,
                    timestamp_ms=verified.timestamp_ms, nonce=verified.nonce,
                    clock_ms=lambda: time.time_ns()//1000000)
                decision = (self._classify(connection, config, verified, method,
                    request_target, body, lookup) if checked.error is None else None)
                query = decision is not None and decision.query
                limit = config["max_nonces"]-(0 if query else config["query_nonce_reserve"])
                core_error = _nonce_finish(connection, checked, key_id=verified.key.key_id, limit=limit)
                error = core_error
                if error is None:
                    error = decision.error
                    if error is None and not query and connection.execute(
                            "SELECT COUNT(*) FROM main.auth_credit_acceptances").fetchone()[0] >= config["max_acceptances"]:
                        error = _error("credit_auth_reservation_capacity", 503)
                        decision = _Decision(decision.kind, decision.command_id, decision.payload,
                            decision.operation_grant, decision.query_grant, decision.first, False,
                            error, "RESERVATION_CAPACITY")
                    if error is None:
                        slot = self._reserve(query)
                        if slot is None:
                            error = _error("credit_auth_handle_capacity", 503)
                original = decision.first if decision is not None else None
                grant = decision.operation_grant if decision is not None else None
                business_key = (_json([config["domain_id"], config["tenant"], config["account_id"], decision.command_id])
                    if decision is not None and decision.command_id is not None else None)
                known_key = (verified.key.identity() if checked.error is None else None)
                sequence = self.store._audit(connection, config,
                    event=core_error.code if core_error is not None else "nonce_consumed",
                    outcome=("AUTH_DENIED" if core_error is not None else "HANDLE_CAPACITY" if error is not None and decision.error is None else decision.outcome),
                    request_kind=decision.kind if decision else "AUTH_OTHER",
                    key_id=verified.key.key_id, key_identity=known_key,
                    nonce_hash=checked.nonce_hash, request_hash=verified.request_hash,
                    request_ms=verified.timestamp_ms, server_ms=checked.server_ms,
                    business_key=business_key, grant_id=grant["grant_id"] if grant else None,
                    original_acceptance_id=original["acceptance_id"] if original else None,
                    query=query and core_error is None)
                if error is None and not query:
                    evidence = {"format": 1, "receipt_kind": "auth_first_observation",
                        "auth_authority_id": config["auth_authority_id"], "domain_id": config["domain_id"],
                        "domain_epoch": config["domain_epoch"], "tenant_id": config["tenant"],
                        "audience": config["audience"], "producer_binding": config["producer_binding"],
                        "account_id": config["account_id"], "command_id": decision.command_id,
                        "kind": decision.kind, "command_payload": decision.payload,
                        "payload_hash": _digest(decision.payload), "key_id": verified.key.key_id,
                        "key_identity": verified.key.identity(), "grant_id": grant["grant_id"],
                        "grant_epoch": grant["grant_epoch"], "profile_revision": config["revision"],
                        "grant_revision": config["grant_revision"], "auth_audit_sequence": sequence,
                        "request_hash": verified.request_hash, "body_hash": verified.body_hash,
                        "nonce_hash": checked.nonce_hash, "request_ms": verified.timestamp_ms,
                        "auth_checked_server_ms": checked.server_ms, **_FALSE}
                    payload = _json(evidence)
                    original = {"acceptance_id": "auth-acceptance:"+_digest(payload), "payload": payload}
                    row = {"acceptance_id": original["acceptance_id"], "domain_id": config["domain_id"],
                        "tenant": config["tenant"], "account_id": config["account_id"], "command_id": decision.command_id,
                        "kind": decision.kind, "command_payload": decision.payload, "payload_hash": _digest(decision.payload),
                        "auth_audit_sequence": sequence, "key_id": verified.key.key_id, "key_identity": verified.key.identity(),
                        "grant_id": grant["grant_id"], "grant_epoch": grant["grant_epoch"],
                        "profile_revision": config["revision"], "grant_revision": config["grant_revision"],
                        "domain_epoch": config["domain_epoch"], "request_hash": verified.request_hash,
                        "body_hash": verified.body_hash, "nonce_hash": checked.nonce_hash,
                        "request_ms": verified.timestamp_ms, "auth_checked_server_ms": checked.server_ms,
                        "payload": payload}
                    names = tuple(row)
                    connection.execute("INSERT INTO main.auth_credit_acceptances("+",".join(names)+") VALUES("+
                        ",".join("?" for _ in names)+")", tuple(row[n] for n in names))
                observation = {"format": 1,
                    "receipt_kind": "auth_query_only" if query else "auth_first_observation",
                    "auth_authority_id": config["auth_authority_id"], "domain_id": config["domain_id"],
                    "domain_epoch": config["domain_epoch"], "tenant_id": config["tenant"],
                    "account_id": config["account_id"], "command_id": decision.command_id if decision else None,
                    "found": original is not None, "first_acceptance_id": original["acceptance_id"] if original else None,
                    "first_acceptance_payload_or_null": original["payload"] if original else None,
                    "query_audit_sequence": sequence if query else None,
                    "queried_by_key_id": verified.key.key_id if query else None,
                    "query_grant_id": grant["grant_id"] if query and grant else None,
                    "auth_checked_server_ms": checked.server_ms, **_FALSE}
            if error is not None:
                raise error
            # This point is after the real AuthDB COMMIT returned normally.
            with self._lock:
                if slot not in self._slots:
                    raise _error("credit_auth_outcome_unknown", 503)
                handle = _Observation(_SEAL)
                self._handles[handle] = (slot, current_thread(), MappingProxyType(observation))
                slot = None
                return handle
        finally:
            if slot is not None:
                with self._lock:
                    self._slots.pop(slot, None)
            self._intake.release()

    def capture(self, headers, *, method, request_target, body):
        return self._request(headers, method=method, request_target=request_target, body=body, lookup=False)

    def lookup(self, headers, *, method, request_target, body=b""):
        return self._request(headers, method=method, request_target=request_target, body=body, lookup=True)

    def inspect(self, handle):
        self._process()
        with self._lock:
            if type(handle) is not _Observation or handle not in self._handles:
                raise _error("credit_auth_handle_invalid")
            _, thread, observation = self._handles[handle]
            if thread is not current_thread():
                raise _error("credit_auth_thread_mismatch")
            return observation

    def release(self, handle):
        self.inspect(handle)
        with self._lock:
            slot, _, _ = self._handles.pop(handle)
            del self._slots[slot]
