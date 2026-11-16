"""Persistent, single-host writer leases enforced by Database transactions.

This is a cooperative application boundary on a trusted local SQLite host, not
an OS-owner security boundary, replicated lease, or cross-AZ leader election.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import math
import os
from pathlib import Path
import re
import sqlite3
from threading import RLock
import time

from .storage import Database, StorageError


class WriterFenceError(StorageError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class WriterToken:
    authority_id: str
    owner_nonce: str
    generation: int
    process_id: int = field(default_factory=os.getpid)


_NAMES = frozenset({"writer_fence_authority", "writer_fence_lease", "writer_fence_events"})
_INBOX_TABLES = frozenset({"uta_command_config", "uta_command_inbox"})
_INBOX_INDEXES = frozenset({"uta_command_pending", "uta_command_account_pending"})
_INBOX_TRIGGERS = frozenset({"uta_command_config_no_replace", "uta_command_config_no_update",
    "uta_command_config_no_delete", "uta_command_inbox_pending_insert", "uta_command_inbox_no_replace",
    "uta_command_inbox_identity_immutable", "uta_command_inbox_terminal_immutable", "uta_command_inbox_no_delete"})
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z", re.ASCII)
_MAX_INTEGER = 2**63 - 1
_REGISTRY = {}
_REGISTRY_LOCK = RLock()

# Authorizer numbers are part of SQLite's stable C API. Several are not exposed
# by CPython 3.10, so do not depend on the interpreter exporting every constant.
_ACTIONS = {name: getattr(sqlite3, "SQLITE_" + name, number) for name, number in (
    ("CREATE_INDEX", 1), ("CREATE_TABLE", 2), ("CREATE_TEMP_INDEX", 3),
    ("CREATE_TEMP_TABLE", 4), ("CREATE_TEMP_TRIGGER", 5), ("CREATE_TEMP_VIEW", 6),
    ("CREATE_TRIGGER", 7), ("CREATE_VIEW", 8), ("DELETE", 9), ("DROP_INDEX", 10),
    ("DROP_TABLE", 11), ("DROP_TEMP_INDEX", 12), ("DROP_TEMP_TABLE", 13),
    ("DROP_TEMP_TRIGGER", 14), ("DROP_TEMP_VIEW", 15), ("DROP_TRIGGER", 16),
    ("DROP_VIEW", 17), ("INSERT", 18), ("PRAGMA", 19), ("TRANSACTION", 22),
    ("UPDATE", 23), ("ATTACH", 24), ("DETACH", 25), ("ALTER_TABLE", 26),
    ("REINDEX", 27), ("ANALYZE", 28), ("CREATE_VTABLE", 29),
    ("DROP_VTABLE", 30), ("FUNCTION", 31))}
_DML = {_ACTIONS[name] for name in ("INSERT", "UPDATE", "DELETE")}
_DDL = {_ACTIONS[name] for name in _ACTIONS if name.startswith(("CREATE_", "DROP_"))
        or name in {"ALTER_TABLE", "REINDEX", "ANALYZE"}}
_OK, _DENY = getattr(sqlite3, "SQLITE_OK", 0), getattr(sqlite3, "SQLITE_DENY", 1)


def _clock(database):
    clock = database._fence_clock_ns
    if clock is None:
        if not hasattr(time, "CLOCK_BOOTTIME"):
            raise WriterFenceError("fence_clock_unavailable", "managed authorities require Linux CLOCK_BOOTTIME")
        value = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
    else:
        value = clock()
    boot = database._fence_boot_id
    if boot is None:
        try:
            boot = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
        except OSError as exc:
            raise WriterFenceError("fence_clock_unavailable", "cannot establish the local boot identity") from exc
    if type(value) is not int or not 0 <= value <= _MAX_INTEGER or not isinstance(boot, str) or not _NAME.fullmatch(boot):
        raise WriterFenceError("fence_clock_invalid", "fence clock requires bounded nonnegative nanoseconds and a boot identity")
    return value, boot


def _load(connection):
    found = {row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'writer_fence_%'")}
    if not found:
        return None
    if found != _NAMES:
        raise WriterFenceError("fence_corrupt", "managed authority schema is incomplete")
    try:
        authority = connection.execute("SELECT singleton,format,authority_id,canonical_path FROM writer_fence_authority").fetchall()
        lease = connection.execute("SELECT singleton,generation,owner_nonce,owner_pid,boot_id,expires_ns,observed_ns FROM writer_fence_lease").fetchall()
        if len(authority) != 1 or tuple(authority[0])[:2] != (1, 1) or not _NAME.fullmatch(authority[0][2]):
            raise ValueError("invalid authority")
        current_path = next(row[2] for row in connection.execute("PRAGMA database_list") if row[1] == "main")
        if authority[0][3] != current_path:
            raise WriterFenceError("authority_path_conflict", "managed authority was copied or moved from its canonical path")
        if len(lease) != 1:
            raise ValueError("missing lease")
        singleton, generation, owner, pid, boot, expires, observed = tuple(lease[0])
        if (singleton != 1 or type(generation) is not int or not 0 <= generation <= _MAX_INTEGER
                or type(expires) is not int or not 0 <= expires <= _MAX_INTEGER
                or type(observed) is not int or not 0 <= observed <= _MAX_INTEGER
                or not isinstance(boot, str) or not _NAME.fullmatch(boot)
                or owner is not None and (not isinstance(owner, str) or not _NAME.fullmatch(owner))
                or owner is None and pid is not None or owner is not None and (type(pid) is not int or pid <= 0)):
            raise ValueError("invalid lease")
        return {"authority_id": authority[0][2], "canonical_path": authority[0][3], "generation": generation, "owner_nonce": owner,
                "owner_pid": pid, "boot_id": boot, "expires_ns": expires, "observed_ns": observed}
    except (sqlite3.Error, ValueError, TypeError) as exc:
        raise WriterFenceError("fence_corrupt", "managed authority record is invalid") from exc


def _observed(database, state):
    now, boot = _clock(database)
    if boot == state["boot_id"] and now < state["observed_ns"]:
        raise WriterFenceError("fence_clock_regressed", "local lease clock regressed behind its durable high watermark")
    return now, boot


def _assert_token(database, state, token):
    if state is None:
        raise WriterFenceError("fence_not_managed", "enable managed authority before starting a fenced writer")
    now, boot = _observed(database, state)
    if (not isinstance(token, WriterToken) or token.authority_id != state["authority_id"]
            or token.owner_nonce != state["owner_nonce"] or type(token.generation) is not int
            or token.generation != state["generation"] or type(token.process_id) is not int
            or token.process_id != os.getpid() or token.process_id != state["owner_pid"]
            or boot != state["boot_id"]):
        raise WriterFenceError("writer_fenced", "transaction does not own the current authority generation in this process")
    if state["expires_ns"] <= now:
        raise WriterFenceError("lease_expired", "writer lease expired; renew cannot revive it")
    return now, boot


def _ttl(value):
    if (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
            or not .001 <= value <= 3600):
        raise ValueError("ttl_seconds must be finite and in .001..3600")
    return int(value * 1_000_000_000)


class WriterFence:
    """Control lease state without acquiring permission to write financial data."""
    def __init__(self, database: Database):
        if not isinstance(database, Database):
            raise ValueError("database must be a Database")
        self.database = database

    def enable(self, authority_id: str):
        if not isinstance(authority_id, str) or not _NAME.fullmatch(authority_id):
            raise ValueError("authority_id must be a bounded ASCII identifier")
        with self.database._fence_transaction() as connection:
            existing = _load(connection)
            if existing is not None:
                if existing["authority_id"] != authority_id:
                    raise WriterFenceError("authority_conflict", "managed authority identity is immutable")
            else:
                now, boot = _clock(self.database)
                connection.execute("CREATE TABLE writer_fence_authority (singleton INTEGER PRIMARY KEY CHECK(singleton=1),format INTEGER NOT NULL CHECK(format=1),authority_id TEXT NOT NULL,canonical_path TEXT NOT NULL)")
                connection.execute("CREATE TABLE writer_fence_lease (singleton INTEGER PRIMARY KEY CHECK(singleton=1),generation INTEGER NOT NULL CHECK(generation>=0),owner_nonce TEXT,owner_pid INTEGER,boot_id TEXT NOT NULL,expires_ns INTEGER NOT NULL,observed_ns INTEGER NOT NULL)")
                connection.execute("CREATE TABLE writer_fence_events (sequence INTEGER PRIMARY KEY,kind TEXT NOT NULL,authority_id TEXT NOT NULL,owner_nonce TEXT,generation INTEGER NOT NULL,owner_pid INTEGER,boot_id TEXT NOT NULL,observed_ns INTEGER NOT NULL,expires_ns INTEGER NOT NULL)")
                connection.execute("INSERT INTO writer_fence_authority VALUES (1,1,?,?)", (authority_id, self.database.path))
                connection.execute("INSERT INTO writer_fence_lease VALUES (1,0,NULL,NULL,?,?,?)", (boot, now, now))
                for table in ("writer_fence_authority", "writer_fence_events"):
                    for action in ("UPDATE", "DELETE"):
                        connection.execute(f"CREATE TRIGGER {table}_no_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'fence authority and audit are immutable'); END")
                connection.execute("CREATE TRIGGER writer_fence_lease_no_delete BEFORE DELETE ON writer_fence_lease BEGIN SELECT RAISE(ABORT,'managed lease cannot be deleted'); END")
                connection.execute("CREATE TRIGGER writer_fence_lease_monotonic BEFORE UPDATE ON writer_fence_lease WHEN NEW.generation<OLD.generation BEGIN SELECT RAISE(ABORT,'fence generation cannot regress'); END")
                self._event(connection, "enabled", _load(connection), now)
        return self.status()

    def _event(self, connection, kind, state, now):
        connection.execute("INSERT INTO writer_fence_events(kind,authority_id,owner_nonce,generation,owner_pid,boot_id,observed_ns,expires_ns) VALUES (?,?,?,?,?,?,?,?)",
            (kind, state["authority_id"], state["owner_nonce"], state["generation"], state["owner_pid"], state["boot_id"], now, state["expires_ns"]))

    def acquire(self, owner_nonce: str, ttl_seconds: float) -> WriterToken:
        if not isinstance(owner_nonce, str) or not _NAME.fullmatch(owner_nonce):
            raise ValueError("owner_nonce must be a bounded ASCII identifier")
        duration = _ttl(ttl_seconds)
        with self.database._fence_transaction() as connection:
            state = _load(connection)
            if state is None:
                raise WriterFenceError("fence_not_managed", "enable the managed authority before acquiring a lease")
            now, boot = _observed(self.database, state)
            if state["owner_nonce"] is not None and boot == state["boot_id"] and state["expires_ns"] > now:
                raise WriterFenceError("lease_busy", "another live owner holds the authority lease")
            if state["generation"] == _MAX_INTEGER or now + duration > _MAX_INTEGER:
                raise WriterFenceError("fence_exhausted", "fence generation or lease clock exhausted its range")
            token = WriterToken(state["authority_id"], owner_nonce, state["generation"] + 1)
            connection.execute("UPDATE writer_fence_lease SET generation=?,owner_nonce=?,owner_pid=?,boot_id=?,expires_ns=?,observed_ns=? WHERE singleton=1",
                (token.generation, owner_nonce, token.process_id, boot, now + duration, now))
            self._event(connection, "acquired", _load(connection), now)
        return token

    def renew(self, token: WriterToken, ttl_seconds: float) -> WriterToken:
        duration = _ttl(ttl_seconds)
        with self.database._fence_transaction() as connection:
            state = _load(connection)
            now, boot = _assert_token(self.database, state, token)
            if now + duration > _MAX_INTEGER:
                raise WriterFenceError("fence_exhausted", "lease clock exhausted its range")
            connection.execute("UPDATE writer_fence_lease SET expires_ns=?,observed_ns=? WHERE singleton=1", (now + duration, now))
            self._event(connection, "renewed", _load(connection), now)
        return token

    def release(self, token: WriterToken):
        with self.database._fence_transaction() as connection:
            state = _load(connection)
            now, boot = _assert_token(self.database, state, token)
            connection.execute("UPDATE writer_fence_lease SET owner_nonce=NULL,owner_pid=NULL,expires_ns=?,observed_ns=? WHERE singleton=1", (now, now))
            self._event(connection, "released", _load(connection), now)
        return self.status()

    def status(self):
        with self.database.read_transaction() as connection:
            state = _load(connection)
            if state is None:
                return {"managed": False, "active": False}
            now, boot = _observed(self.database, state)
            return {"managed": True, **state, "now_ns": now,
                    "active": state["owner_nonce"] is not None and boot == state["boot_id"] and state["expires_ns"] > now}

    def assert_writer(self, connection, token=None):
        if not isinstance(connection, sqlite3.Connection) or not connection.in_transaction:
            raise WriterFenceError("unguarded_connection", "writer assertion requires an active Database transaction")
        _assert_joinable(self.database, connection)
        state = _load(connection)
        _assert_token(self.database, state, self.database.writer_token if token is None else token)
        return state


class _TransactionGuard:
    def __init__(self, database, connection, role):
        self.database, self.connection, self.role = database, connection, role
        self.state = _load(connection)
        self.internal = False
        self.written = False
        self.denied = None
        self.token_error = None
        self.started_at = None
        if role == "financial" and (self.state is not None or database.writer_token is not None):
            try:
                self.started_at = _assert_token(database, self.state, database.writer_token)
            except WriterFenceError as exc:
                self.token_error = exc
        self.armed = self.state is not None or database.writer_token is not None or role != "financial"
        if self.armed:
            connection.set_authorizer(self._authorize)
        with _REGISTRY_LOCK:
            _REGISTRY[id(connection)] = self

    def _deny(self, error=None):
        if self.denied is None:
            self.denied = error or WriterFenceError("writer_fenced", "transaction role cannot write this protected authority object")
        return _DENY

    def _authorize(self, action, first, second, database_name, source):
        if self.internal:
            return _OK
        if action == _ACTIONS["TRANSACTION"]:
            return self._deny(WriterFenceError("transaction_control_forbidden", "Database owns COMMIT and ROLLBACK"))
        if action in {_ACTIONS["ATTACH"], _ACTIONS["DETACH"]}:
            return self._deny()
        if action == _ACTIONS["FUNCTION"] and (second or "").lower() == "load_extension":
            return self._deny()
        if action == _ACTIONS["PRAGMA"]:
            safe = {"table_info", "table_xinfo", "index_info", "index_xinfo", "index_list", "foreign_key_list", "database_list", "integrity_check", "quick_check", "page_count", "freelist_count", "compile_options"}
            if (first or "").lower() not in safe and second is not None:
                return self._deny()
            return _OK
        if action not in _DML and action not in _DDL:
            return _OK
        if database_name not in {None, "main"}:
            return self._deny()
        if self.role == "read":
            return self._deny(WriterFenceError("read_only_transaction", "read transactions cannot modify authority state"))
        if self.role == "control":
            allowed = first in _NAMES or (first or "").startswith("writer_fence_")
            if action in _DDL:
                allowed = action in {_ACTIONS["CREATE_TABLE"], _ACTIONS["CREATE_TRIGGER"]} and allowed
            if action in _DML and first in {"sqlite_master", "sqlite_schema"}:
                allowed = True
            return _OK if allowed else self._deny()
        if self.role == "inbox":
            if action == _ACTIONS["CREATE_TABLE"]:
                # AUTOINCREMENT creates SQLite's reserved sequence table;
                # UNIQUE creates an implicit reserved-name index. User SQL
                # cannot create sqlite_* objects to obtain broader DDL access.
                allowed = first in _INBOX_TABLES or first == "sqlite_sequence"
            elif action == _ACTIONS["CREATE_INDEX"]:
                allowed = (second in _INBOX_TABLES and
                    (first in _INBOX_INDEXES or (first or "").startswith("sqlite_autoindex_" + second + "_")))
            elif action == _ACTIONS["CREATE_TRIGGER"]:
                allowed = first in _INBOX_TRIGGERS and second in _INBOX_TABLES
            elif action == _ACTIONS["REINDEX"]:
                # Building a declared index also emits SQLITE_REINDEX.
                allowed = first in _INBOX_INDEXES or any((first or "").startswith(
                    "sqlite_autoindex_" + table + "_") for table in _INBOX_TABLES)
            elif action in _DDL:
                allowed = False
            else:
                allowed = (action == _ACTIONS["INSERT"] and first in _INBOX_TABLES
                    or first == "sqlite_sequence" or first in {"sqlite_master", "sqlite_schema"})
            return _OK if allowed else self._deny()
        if self.token_error is not None:
            return self._deny(self.token_error)
        if self.state is None:
            # Preserve un-managed legacy transaction behavior, except that
            # reserved lease state can only be initialized through its control API.
            return self._deny() if (first or "").startswith("writer_fence_") else _OK
        if ((first or "").startswith("writer_fence_") or (second or "").startswith("writer_fence_")):
            return self._deny()
        self.written = True
        return _OK

    @contextmanager
    def privileged(self):
        self.internal = True
        try:
            yield
        finally:
            self.internal = False

    def before_commit(self):
        if self.denied is not None:
            raise self.denied
        if self.written and self.state is not None:
            with self.privileged():
                state = _load(self.connection)
                now, boot = _assert_token(self.database, state, self.database.writer_token)
                if self.started_at is not None and boot == self.started_at[1] and now < self.started_at[0]:
                    raise WriterFenceError("fence_clock_regressed", "lease clock regressed during a financial transaction")
                self.connection.execute("UPDATE writer_fence_lease SET observed_ns=? WHERE singleton=1", (now,))

    def close(self):
        with _REGISTRY_LOCK:
            _REGISTRY.pop(id(self.connection), None)
        if self.armed:
            self.connection.set_authorizer(None)


def _assert_joinable(database, connection):
    with _REGISTRY_LOCK:
        guard = _REGISTRY.get(id(connection))
    if guard is not None and guard.connection is connection and guard.database.path == database.path:
        return
    if _load(connection) is not None:
        raise WriterFenceError("unguarded_connection", "managed ledger connections must originate in Database.transaction")
