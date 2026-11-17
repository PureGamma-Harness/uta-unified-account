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
from hashlib import sha256
from threading import RLock, get_ident
import time
from types import MappingProxyType

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


_BASE_NAMES = frozenset({"writer_fence_authority", "writer_fence_lease", "writer_fence_events"})
_GUARD_NAMES = frozenset({"writer_fence_guard_config", "writer_fence_guard_tables"})
_STANDARD_NAMES = _BASE_NAMES | _GUARD_NAMES
_BATCH_NAMES = frozenset({"writer_fence_batch_capability"})
_CREDIT_NAMES = frozenset({"writer_fence_credit_capability"})
_NAMES = _STANDARD_NAMES | _BATCH_NAMES | _CREDIT_NAMES
_INVENTORIES = (_BASE_NAMES, _STANDARD_NAMES, _STANDARD_NAMES | _BATCH_NAMES,
                _STANDARD_NAMES | _CREDIT_NAMES, _NAMES)
_BATCH_TABLES = frozenset({"uta_command_batch_manifests", "uta_command_batch_outcomes"})
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

_CONTROL_TABLE_SQL = MappingProxyType({
    "writer_fence_credit_capability": "CREATE TABLE writer_fence_credit_capability(singleton INTEGER PRIMARY KEY CHECK(singleton=1),format INTEGER NOT NULL CHECK(format=1),state TEXT NOT NULL CHECK(state='NATIVE_PREPARED'),descriptor_id TEXT NOT NULL,payload TEXT NOT NULL)",
    "writer_fence_batch_capability": "CREATE TABLE writer_fence_batch_capability(singleton INTEGER PRIMARY KEY CHECK(singleton=1),format INTEGER NOT NULL CHECK(format=1))",
    "writer_fence_authority": "CREATE TABLE writer_fence_authority (singleton INTEGER PRIMARY KEY CHECK(singleton=1),format INTEGER NOT NULL CHECK(format=1),authority_id TEXT NOT NULL,canonical_path TEXT NOT NULL)",
    "writer_fence_lease": "CREATE TABLE writer_fence_lease (singleton INTEGER PRIMARY KEY CHECK(singleton=1),generation INTEGER NOT NULL CHECK(generation>=0),owner_nonce TEXT,owner_pid INTEGER,boot_id TEXT NOT NULL,expires_ns INTEGER NOT NULL,observed_ns INTEGER NOT NULL)",
    "writer_fence_events": "CREATE TABLE writer_fence_events (sequence INTEGER PRIMARY KEY,kind TEXT NOT NULL,authority_id TEXT NOT NULL,owner_nonce TEXT,generation INTEGER NOT NULL,owner_pid INTEGER,boot_id TEXT NOT NULL,observed_ns INTEGER NOT NULL,expires_ns INTEGER NOT NULL)",
    "writer_fence_guard_config": "CREATE TABLE writer_fence_guard_config(singleton INTEGER PRIMARY KEY CHECK(singleton=1),format INTEGER NOT NULL CHECK(format=1))",
    "writer_fence_guard_tables": "CREATE TABLE writer_fence_guard_tables(name TEXT PRIMARY KEY,actions TEXT NOT NULL)",
})


def _control_trigger_definitions():
    definitions = {}
    for table in ("writer_fence_authority", "writer_fence_events"):
        for action in ("UPDATE", "DELETE"):
            name = f"{table}_no_{action.lower()}"
            definitions[name] = (table, f"CREATE TRIGGER {name} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'fence authority and audit are immutable'); END")
    definitions["writer_fence_lease_no_delete"] = ("writer_fence_lease", "CREATE TRIGGER writer_fence_lease_no_delete BEFORE DELETE ON writer_fence_lease BEGIN SELECT RAISE(ABORT,'managed lease cannot be deleted'); END")
    definitions["writer_fence_lease_monotonic"] = ("writer_fence_lease", "CREATE TRIGGER writer_fence_lease_monotonic BEFORE UPDATE ON writer_fence_lease WHEN NEW.generation<OLD.generation BEGIN SELECT RAISE(ABORT,'fence generation cannot regress'); END")
    for table in _GUARD_NAMES | _BATCH_NAMES | _CREDIT_NAMES:
        for action in ("UPDATE", "DELETE"):
            name = f"{table}_no_{action.lower()}"
            definitions[name] = (table, f"CREATE TRIGGER {name} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'persistent guard metadata is immutable'); END")
    for table in _CREDIT_NAMES:
        name = table + "_no_replace"
        definitions[name] = (table, f"CREATE TRIGGER {name} BEFORE INSERT ON {table} WHEN EXISTS(SELECT 1 FROM {table} WHERE singleton=NEW.singleton) BEGIN SELECT RAISE(ABORT,'native credit capability cannot replace'); END")
    return MappingProxyType(definitions)


_CONTROL_TRIGGER_SQL = _control_trigger_definitions()


def _verify_control_schema(connection, state):
    names = _STANDARD_NAMES if state["guard_format"] == 1 else _BASE_NAMES
    if state.get("batch_format") == 1:
        names |= _BATCH_NAMES
    if state.get("credit_format") == 1:
        names |= _CREDIT_NAMES
    rows = connection.execute("SELECT name,type,tbl_name,sql FROM sqlite_master").fetchall()
    tables = {row[0]: row[3] for row in rows if row[1] == "table" and row[0] in names}
    if tables != {name: _CONTROL_TABLE_SQL[name] for name in names}:
        raise WriterFenceError("fence_control_corrupt", "lease control table definition changed; automatic repair is forbidden")
    expected = {name: (table, sql) for name, (table, sql) in _CONTROL_TRIGGER_SQL.items() if table in names}
    triggers = {row[0]: (row[2], row[3]) for row in rows if row[1] == "trigger" and
        (row[2] in _NAMES or row[0].startswith("writer_fence_") and not row[0].startswith("writer_fence_data_"))}
    if triggers != expected:
        raise WriterFenceError("fence_control_corrupt", "lease control trigger inventory or definition changed; automatic repair is forbidden")
    indexes = {(row[0], row[2], row[3]) for row in rows if row[1] == "index" and row[2] in _NAMES}
    expected_indexes = ({("sqlite_autoindex_writer_fence_guard_tables_1", "writer_fence_guard_tables", None)}
                        if state["guard_format"] == 1 else set())
    if indexes != expected_indexes:
        raise WriterFenceError("fence_control_corrupt", "lease control index inventory changed")


def _create_control_object(connection, name):
    """Execute only a compiled-in schema statement, never caller-supplied SQL."""
    with _REGISTRY_LOCK:
        guard = _REGISTRY.get(id(connection))
    if guard is None or guard.role != "control":
        raise WriterFenceError("unguarded_connection", "lease schema creation requires its internal control transaction")
    if name in _CONTROL_TABLE_SQL:
        sql = _CONTROL_TABLE_SQL[name]
    elif name in _CONTROL_TRIGGER_SQL:
        sql = _CONTROL_TRIGGER_SQL[name][1]
    else:
        raise WriterFenceError("writer_fenced", "unknown lease control schema object")
    with guard.privileged():
        connection.execute(sql)


def _create_credit_object(connection, name):
    """Offline credit installer: a compiled object name, never arbitrary SQL."""
    from .credit_native import OBJECT_SQL
    with _REGISTRY_LOCK:
        guard = _REGISTRY.get(id(connection))
    if guard is None or guard.connection is not connection or guard.role != "control" or name not in OBJECT_SQL:
        raise WriterFenceError("writer_fenced", "unknown or unauthorized native credit schema object")
    with guard.privileged():
        connection.execute(OBJECT_SQL[name])


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
    objects = tuple(connection.execute("SELECT name,type FROM sqlite_master WHERE (type='table' AND name LIKE 'writer_fence_%') OR name LIKE 'credit_native_%'"))
    found = {row[0] for row in objects if row[1] == "table" and row[0].startswith("writer_fence_")}
    native_objects = {row[0] for row in objects if row[0].startswith("credit_native_")}
    if not found:
        if native_objects:
            raise WriterFenceError("credit_native_partial_schema", "native credit objects have no authority capability")
        return None
    if _BASE_NAMES <= found and found not in _INVENTORIES:
        raise WriterFenceError("fence_guard_corrupt", "persistent guard metadata is incomplete; automatic repair is forbidden")
    if found not in _INVENTORIES:
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
        # Preparation has an exact two/three-event history, so checking this
        # fixed prefix does not scan a normal authority's renewal history.
        credit_prefix = tuple(tuple(row) for row in connection.execute(
            "SELECT sequence,kind,authority_id,generation,owner_nonce,owner_pid FROM writer_fence_events WHERE sequence<=3 ORDER BY sequence"))
        credit_event = any(row[1] == "credit_native_prepared_v1" for row in credit_prefix)
        guard_format = 0
        if _STANDARD_NAMES <= found:
            guard = connection.execute("SELECT singleton,format FROM writer_fence_guard_config").fetchall()
            if [tuple(row) for row in guard] != [(1, 1)]:
                raise ValueError("invalid persistent guard format")
            guard_format = 1
        elif connection.execute("SELECT 1 FROM writer_fence_events WHERE kind IN ('enabled_guard_v1','guards_upgraded') LIMIT 1").fetchone() is not None:
            raise WriterFenceError("fence_guard_corrupt", "persistent guard metadata disappeared after activation")
        batch_format = 0
        if _BATCH_NAMES <= found:
            rows = connection.execute("SELECT singleton,format FROM writer_fence_batch_capability").fetchall()
            if [tuple(row) for row in rows] != [(1, 1)] or guard_format != 1:
                raise ValueError("invalid batch capability")
            batch_format = 1
        elif connection.execute("SELECT 1 FROM writer_fence_events WHERE kind='batches_enabled' LIMIT 1").fetchone() is not None:
            raise WriterFenceError("fence_guard_corrupt", "persistent batch capability disappeared")
        credit = {}
        if _CREDIT_NAMES <= found:
            from .credit_native import load_marker
            rows = connection.execute("SELECT singleton,format,state,descriptor_id,payload FROM writer_fence_credit_capability").fetchall()
            expected_prefix = [(1, "enabled_guard_v1", authority[0][2], 0, None, None)]
            if batch_format:
                expected_prefix.append((2, "batches_enabled", authority[0][2], 0, None, None))
            prepared_sequence = len(expected_prefix) + 1
            expected_prefix.append((prepared_sequence, "credit_native_prepared_v1", authority[0][2], 0, None, None))
            last_event = connection.execute("SELECT COALESCE(MAX(sequence),0) FROM writer_fence_events").fetchone()[0]
            if (len(rows) != 1 or guard_format != 1 or credit_prefix != tuple(expected_prefix) or last_event != prepared_sequence
                    or generation != 0 or owner is not None or pid is not None):
                raise WriterFenceError("credit_native_corrupt", "native credit preparation record/event differs")
            record = load_marker(connection, rows[0], authority_id=authority[0][2])
            credit = {"credit_format": 1, "credit_state": "NATIVE_PREPARED", "credit_descriptor_id": record.descriptor_id}
        elif credit_event:
            raise WriterFenceError("credit_native_corrupt", "irreversible native credit capability disappeared")
        elif native_objects:
            raise WriterFenceError("credit_native_partial_schema", "native credit objects have no prepared capability")
        return {"authority_id": authority[0][2], "guard_format": guard_format, "batch_format": batch_format, **credit,
                "canonical_path": authority[0][3], "generation": generation, "owner_nonce": owner,
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
    if state.get("credit_format") == 1:
        raise WriterFenceError("credit_not_active", "native credit preparation cannot authorize a trading writer")
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


def _quote(identifier):
    return '"' + identifier.replace('"', '""') + '"'


def _data_tables(connection):
    return {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
            if not row[0].startswith(("writer_fence_", "sqlite_"))}


def _guard_actions(table):
    # Producer INSERTs use the independently protected queue schema. Terminal
    # UPDATE/DELETE still require a financial token, including in old binaries.
    return "UD" if table in _INBOX_TABLES else "IUD"


def _guard_sql(table, action):
    name = "writer_fence_data_" + sha256(table.encode("utf-8")).hexdigest() + "_" + action.lower()
    operation = {"I": "INSERT", "U": "UPDATE", "D": "DELETE"}[action]
    sql = ("CREATE TRIGGER " + _quote(name) + " BEFORE " + operation + " ON " + _quote(table)
        + " BEGIN SELECT CASE WHEN uta_writer_fence_v1()!=1 THEN RAISE(ABORT,'current writer lease required') END; END")
    return name, sql


def _verify_data_guards(connection, *, allow_new=False):
    registered = {row[0]: row[1] for row in connection.execute("SELECT name,actions FROM writer_fence_guard_tables")}
    actual = _data_tables(connection)
    if not set(registered) <= actual or not allow_new and set(registered) != actual:
        raise WriterFenceError("fence_guard_corrupt", "protected table inventory changed outside a guarded schema transaction")
    triggers = {row[0]: (row[1], row[2]) for row in connection.execute(
        "SELECT name,tbl_name,sql FROM sqlite_master WHERE type='trigger' AND name LIKE 'writer_fence_data_%'")}
    expected = {}
    for table, actions in registered.items():
        if actions != _guard_actions(table):
            raise WriterFenceError("fence_guard_corrupt", "protected table guard policy changed")
        for action in actions:
            name, sql = _guard_sql(table, action)
            expected[name] = (table, sql)
    if triggers != expected:
        raise WriterFenceError("fence_guard_corrupt", "persistent financial guard is missing or changed; automatic repair is forbidden")
    return actual - set(registered)


def _install_table_guards(connection, tables):
    for table in sorted(tables):
        actions = _guard_actions(table)
        for action in actions:
            connection.execute(_guard_sql(table, action)[1])
        connection.execute("INSERT INTO writer_fence_guard_tables VALUES (?,?)", (table, actions))


def _initialize_data_guards(connection):
    with _REGISTRY_LOCK:
        guard = _REGISTRY.get(id(connection))
    if guard is None or guard.role != "control":
        raise WriterFenceError("unguarded_connection", "guard installation requires the explicit lease control transaction")
    for table in sorted(_GUARD_NAMES):
        _create_control_object(connection, table)
    connection.execute("INSERT INTO writer_fence_guard_config VALUES(1,1)")
    for name, (table, sql) in _CONTROL_TRIGGER_SQL.items():
        if table in _GUARD_NAMES:
            _create_control_object(connection, name)
    with guard.privileged():
        _install_table_guards(connection, _data_tables(connection))
    _verify_data_guards(connection)


def _require_guard_format(state):
    if state is not None and state["guard_format"] != 1:
        raise WriterFenceError("fence_upgrade_required", "old managed format requires an explicit offline persistent-guard upgrade")


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
                _require_guard_format(existing)
            else:
                now, boot = _clock(self.database)
                for table in ("writer_fence_authority", "writer_fence_lease", "writer_fence_events"):
                    _create_control_object(connection, table)
                connection.execute("INSERT INTO writer_fence_authority VALUES (1,1,?,?)", (authority_id, self.database.path))
                connection.execute("INSERT INTO writer_fence_lease VALUES (1,0,NULL,NULL,?,?,?)", (boot, now, now))
                for name, (table, sql) in _CONTROL_TRIGGER_SQL.items():
                    if table in _BASE_NAMES:
                        _create_control_object(connection, name)
                _initialize_data_guards(connection)
                self._event(connection, "enabled_guard_v1", _load(connection), now)
        return self.status()

    def enable_batches(self):
        """Irreversible offline capability; existing live leases are rejected.

        Batch tables must already be explicitly installed and exact. Old
        binaries reject the new persistent fence-table inventory.
        """
        from .durable_batches import BatchStore
        with self.database._fence_transaction() as connection:
            state = _load(connection)
            if state is None:
                raise WriterFenceError("fence_not_managed", "batch capability requires a managed authority")
            _require_guard_format(state)
            now, boot = _observed(self.database, state)
            if state["owner_nonce"] is not None and boot == state["boot_id"] and state["expires_ns"] > now:
                raise WriterFenceError("lease_busy", "stop every writer before enabling durable batches")
            BatchStore._verify_schema(connection)
            if state["batch_format"] == 0:
                _create_control_object(connection, "writer_fence_batch_capability")
                connection.execute("INSERT INTO writer_fence_batch_capability VALUES(1,1)")
                for name, (table, sql) in _CONTROL_TRIGGER_SQL.items():
                    if table in _BATCH_NAMES:
                        _create_control_object(connection, name)
                self._event(connection, "batches_enabled", _load(connection), now)
        return self.status()

    def upgrade_guards(self):
        """Explicit offline upgrade of the first managed format, never repair.

        Operators must stop every writer first. An active lease prevents the
        upgrade. Existing persistent guards are verified, never reinstalled.
        """
        with self.database._fence_transaction() as connection:
            state = _load(connection)
            if state is None:
                raise WriterFenceError("fence_not_managed", "enable a managed authority before upgrading it")
            if state["guard_format"] == 1:
                _verify_data_guards(connection)
            else:
                now, boot = _observed(self.database, state)
                if state["owner_nonce"] is not None and boot == state["boot_id"] and state["expires_ns"] > now:
                    raise WriterFenceError("lease_busy", "stop and release or expire every writer before offline guard upgrade")
                if state["generation"] == _MAX_INTEGER:
                    raise WriterFenceError("fence_exhausted", "generation cannot advance for the offline upgrade")
                _initialize_data_guards(connection)
                connection.execute("UPDATE writer_fence_lease SET generation=generation+1,owner_nonce=NULL,owner_pid=NULL,boot_id=?,expires_ns=?,observed_ns=? WHERE singleton=1", (boot, now, now))
                self._event(connection, "guards_upgraded", _load(connection), now)
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
            _require_guard_format(state)
            if state.get("credit_format") == 1:
                raise WriterFenceError("credit_not_active", "native credit preparation cannot acquire a trading writer")
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
            _require_guard_format(state)
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
        _require_guard_format(state)
        _assert_token(self.database, state, self.database.writer_token if token is None else token)
        return state


class _TransactionGuard:
    def __init__(self, database, connection, role):
        if role in ("financial", "batch_metadata"):
            from .startup import _assert_initialization_actor
            _assert_initialization_actor(database)
        self.database, self.connection, self.role = database, connection, role
        self.state = _load(connection)
        self.internal = False
        self.written = False
        self.denied = None
        self.token_error = None
        self.started_at = None
        self._udf_registered = False
        self._credit_udf_registered = False
        self.credit_owner_thread = get_ident()
        if self.state is not None:
            _verify_control_schema(connection, self.state)
        if self.state is not None and self.state["guard_format"] == 1:
            _verify_data_guards(connection)
        if self.state is not None and self.state.get("credit_format") == 1:
            if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
                raise WriterFenceError("credit_foreign_keys_required", "native credit requires actual foreign-key enforcement")
            connection.create_function("uta_credit_operation_v1", 3, self._sql_credit_operation)
            self._credit_udf_registered = True
        if role in ("financial", "batch_metadata") and (self.state is not None or database.writer_token is not None):
            try:
                _require_guard_format(self.state)
                if role == "batch_metadata" and (self.state is None or self.state.get("batch_format") != 1):
                    raise WriterFenceError("batch_capability_required", "batch metadata requires its recorded authority capability")
                self.started_at = _assert_token(database, self.state, database.writer_token)
            except WriterFenceError as exc:
                self.token_error = exc
            else:
                connection.create_function("uta_writer_fence_v1", 0, self._sql_permit)
                self._udf_registered = True
        self.armed = self.state is not None or database.writer_token is not None or role != "financial"
        if self.armed:
            connection.set_authorizer(self._authorize)
        with _REGISTRY_LOCK:
            _REGISTRY[id(connection)] = self

    def _sql_permit(self):
        try:
            if self.role not in ("financial", "batch_metadata") or self.denied is not None:
                return 0
            # BEGIN IMMEDIATE prevents any other connection from changing this
            # persistent lease snapshot. Expiry/PID/boot are checked on every
            # trigger invocation, and the record is reloaded before COMMIT.
            _assert_token(self.database, self.state, self.database.writer_token)
            return 1
        except WriterFenceError as exc:
            self.denied = exc
            return 0
        except BaseException as exc:
            self.denied = WriterFenceError("fence_guard_failed", "persistent writer guard could not establish authority")
            self.denied.__cause__ = exc
            return 0

    def _sql_credit_operation(self, phase, command_id, intent_digest):
        # No positive format is implemented. This registered native operation
        # function is a real denial and poisons a caught attempt; never a test
        # callback which reports a synthetic successful credit authorization.
        self._deny(WriterFenceError("credit_not_active", "native preparation has no authorized credit operation"))
        return 0

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
        if self.state is not None and self.state.get("credit_format") == 1 and self.role != "control":
            # In this prepared-only format all financial/metadata writers and
            # their DDL are excluded immediately, including caught DROP/ALTER.
            return self._deny(WriterFenceError("credit_not_active", "native preparation is not a trading or producer capability"))
        if self.role == "control":
            allowed = first in _NAMES
            if action in _DDL:
                allowed = False
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
        if self.role == "batch_metadata":
            if self.state is None or self.state.get("batch_format") != 1:
                return self._deny(WriterFenceError("batch_capability_required", "batch metadata requires an enabled authority"))
            if action != _ACTIONS["INSERT"] or first not in _BATCH_TABLES:
                return self._deny()
            self.written = True
            return _OK
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
        previous = self.internal
        self.internal = True
        try:
            yield
        finally:
            self.internal = previous

    def before_commit(self):
        if self.denied is not None:
            raise self.denied
        state = _load(self.connection)
        if state is not None:
            _verify_control_schema(self.connection, state)
        if self.written and self.state is not None:
            with self.privileged():
                now, boot = _assert_token(self.database, state, self.database.writer_token)
                if self.started_at is not None and boot == self.started_at[1] and now < self.started_at[0]:
                    raise WriterFenceError("fence_clock_regressed", "lease clock regressed during a financial transaction")
                new_tables = _verify_data_guards(self.connection, allow_new=True)
                _install_table_guards(self.connection, new_tables)
                _verify_data_guards(self.connection)
                self.connection.execute("UPDATE writer_fence_lease SET observed_ns=? WHERE singleton=1", (now,))
        elif self.state is not None and self.state["guard_format"] == 1:
            _verify_data_guards(self.connection)

    def close(self):
        with _REGISTRY_LOCK:
            _REGISTRY.pop(id(self.connection), None)
        if self.armed:
            self.connection.set_authorizer(None)
        if self._udf_registered:
            self.connection.create_function("uta_writer_fence_v1", 0, None)
        if self._credit_udf_registered:
            self.connection.create_function("uta_credit_operation_v1", 3, None)


def _assert_financial_joinable(database, connection):
    """Require an existing financial role; never create or elevate one.

    The legacy ledger join contract below intentionally permits raw unmanaged
    transactions. New composable admission paths use this stricter contract.
    """
    with _REGISTRY_LOCK:
        guard = _REGISTRY.get(id(connection))
    if (guard is not None and guard.connection is connection
            and guard.database.path == database.path
            and guard.database.writer_token == database.writer_token
            and guard.role == "financial"):
        return
    raise WriterFenceError("unguarded_connection", "borrowing requires the existing authority's financial transaction")


def _assert_joinable(database, connection):
    with _REGISTRY_LOCK:
        guard = _REGISTRY.get(id(connection))
    if guard is not None and guard.connection is connection and guard.database.path == database.path:
        return
    if _load(connection) is not None:
        raise WriterFenceError("unguarded_connection", "managed ledger connections must originate in Database.transaction")
