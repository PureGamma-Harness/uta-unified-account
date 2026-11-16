"""File-backed transactions and an exact, replay-verifiable double-entry ledger.

SQLite WAL with FULL synchronous writes is a single-host durability foundation,
not a replicated exchange database. All writers of financial state must use the
same database transaction. The operating system and database file owner remain
trusted; journal hashes detect accidental edits but are not external audit seals.
"""
from __future__ import annotations

from contextlib import contextmanager, nullcontext
from copy import copy
from decimal import Decimal
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import sqlite3
import stat
from threading import RLock
from types import MappingProxyType
from typing import Iterator, Mapping, Sequence
from uuid import uuid4

from .ledger import JournalEvent, Ledger, LedgerError, Posting


# Serialize first-file creation with other in-process path checks. Once a file
# is visible, no peer may open SQLite before its creation descriptor is closed.
_FILE_CHECK_LOCK = RLock()


class StorageError(RuntimeError):
    """The persistent store cannot satisfy its transaction contract."""


class Database:
    """Open a new, independently owned SQLite connection for every transaction.

    ``transaction`` acquires the write lock before any reads (BEGIN IMMEDIATE),
    preventing read/check/write races across service instances and processes.
    Callers must not commit or roll back the yielded connection themselves.
    File-backed databases are required so every connection sees the same state.
    """

    def __init__(self, path: str | Path, *, timeout: float = 10.0,
                 writer_token=None, fence_clock_ns=None, fence_boot_id=None):
        if (not isinstance(path, (str, Path)) or not str(path).strip()
                or str(path) == ":memory:" or str(path).startswith("file:")):
            raise StorageError("a filesystem database path is required; memory/URI databases are unsupported")
        if (isinstance(timeout, bool) or not isinstance(timeout, (float, int))
                or not math.isfinite(timeout) or not 0 < timeout <= 300):
            raise StorageError("timeout must be a finite positive number of at most 300 seconds")
        candidate = Path(path).expanduser().absolute()
        # Resolve the parent only: resolving the final component would silently
        # follow a database symlink before it can be rejected below.
        self.path = str(candidate.parent.resolve() / candidate.name)
        self.timeout = float(timeout)
        if fence_clock_ns is not None and not callable(fence_clock_ns):
            raise StorageError("fence_clock_ns must be callable")
        if fence_boot_id is not None and not isinstance(fence_boot_id, str):
            raise StorageError("fence_boot_id must be a string")
        self._writer_token = writer_token
        self._fence_clock_ns, self._fence_boot_id = fence_clock_ns, fence_boot_id

    @property
    def writer_token(self):
        return self._writer_token

    def for_writer(self, token):
        """Bind a new database object, preserving subclass identity checks.

        Existing services keep their original unbound/stale object. Binding a
        token never transfers permission to old services sharing this object.
        """
        from .writer_fence import WriterToken
        if not isinstance(token, WriterToken):
            raise StorageError("writer token must be a WriterToken")
        bound = copy(self)
        bound._writer_token = token
        return bound

    def _private_file(self) -> tuple[int, int]:
        """Create private state independently of umask and reject unsafe reuse.

        State must be kept in an operator-controlled directory. File checks
        protect accidental exposure/replacement; the service OS user is trusted.
        """
        with _FILE_CHECK_LOCK:
            try:
                info = os.stat(self.path, follow_symlinks=False)
            except FileNotFoundError:
                flags = os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
                try:
                    descriptor = os.open(self.path, flags | os.O_CREAT | os.O_EXCL, 0o600)
                except FileExistsError:
                    info = os.stat(self.path, follow_symlinks=False)
                except OSError as exc:
                    raise StorageError("database path cannot be opened safely") from exc
                else:
                    try:
                        info = os.fstat(descriptor)
                    finally:
                        os.close(descriptor)
            # Never open/close an existing SQLite file outside SQLite. POSIX
            # close() drops every record lock held by this process on that file,
            # including locks owned by another live Database connection.
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                    or stat.S_IMODE(info.st_mode) & 0o077):
                raise StorageError("database must be a private regular file owned by the service user")
            return info.st_dev, info.st_ino

    def _connect(self) -> sqlite3.Connection:
        identity = self._private_file()
        connection = sqlite3.connect(self.path, timeout=self.timeout, isolation_level=None)
        try:
            info = os.stat(self.path, follow_symlinks=False)
            if (info.st_dev, info.st_ino) != identity or not stat.S_ISREG(info.st_mode):
                raise StorageError("database path changed while opening")
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(f"PRAGMA busy_timeout = {int(self.timeout * 1000)}")
            mode = connection.execute("PRAGMA journal_mode = WAL").fetchone()[0]
            if mode.lower() != "wal":
                raise StorageError("the database filesystem does not support WAL mode")
            connection.execute("PRAGMA synchronous = FULL")
            return connection
        except BaseException:
            connection.close()
            raise

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Commit all changes together, or roll them all back on any exception."""
        with self._role_transaction("financial") as connection:
            yield connection

    @contextmanager
    def read_transaction(self) -> Iterator[sqlite3.Connection]:
        """Read a consistent snapshot; financial and control writes are denied."""
        with self._role_transaction("read") as connection:
            yield connection

    @contextmanager
    def inbox_transaction(self) -> Iterator[sqlite3.Connection]:
        """Create/enqueue in the fixed inbox only; no terminal or financial DML."""
        with self._role_transaction("inbox") as connection:
            yield connection

    @contextmanager
    def _fence_transaction(self) -> Iterator[sqlite3.Connection]:
        """Internal lease control role; never grants financial write access."""
        with self._role_transaction("control") as connection:
            yield connection

    @contextmanager
    def _role_transaction(self, role) -> Iterator[sqlite3.Connection]:
        from .writer_fence import _TransactionGuard, WriterFenceError
        connection = self._connect()
        guard = None
        try:
            if role == "read":
                connection.execute("PRAGMA query_only=ON")
            connection.execute("BEGIN" if role == "read" else "BEGIN IMMEDIATE")
            guard = _TransactionGuard(self, connection, role)
            yield connection
            if not connection.in_transaction:
                raise StorageError("caller ended the managed transaction")
            guard.before_commit()
            with guard.privileged():
                connection.commit()
        except BaseException as exc:
            if connection.in_transaction:
                with guard.privileged() if guard is not None else nullcontext():
                    connection.rollback()
            if guard is not None and guard.denied is not None and not isinstance(exc, WriterFenceError):
                if guard.denied.__cause__ is not None:
                    raise guard.denied
                raise guard.denied from exc
            raise
        finally:
            if guard is not None:
                guard.close()
            connection.close()

    @contextmanager
    def _using(self, connection: sqlite3.Connection | None) -> Iterator[sqlite3.Connection]:
        if connection is None:
            with self.transaction() as owned:
                yield owned
            return
        if not isinstance(connection, sqlite3.Connection) or not connection.in_transaction:
            raise StorageError("a supplied connection must have an active transaction")
        files = connection.execute("PRAGMA database_list").fetchall()
        main_path = next((row[2] for row in files if row[1] == "main"), None)
        if main_path is None or str(Path(main_path).resolve()) != self.path:
            raise StorageError("the supplied connection belongs to another database")
        from .writer_fence import _assert_joinable
        _assert_joinable(self, connection)
        yield connection


_SCHEMA_VERSION = 1
_GENESIS = "0" * 64
_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS ledger_schema (
        singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
        version INTEGER NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS ledger_assets (
        asset TEXT PRIMARY KEY, scale INTEGER NOT NULL CHECK (scale BETWEEN 0 AND 18))""",
    """CREATE TABLE IF NOT EXISTS ledger_events (
        sequence INTEGER PRIMARY KEY, event_id TEXT NOT NULL UNIQUE,
        fingerprint TEXT NOT NULL, previous_hash TEXT NOT NULL,
        event_hash TEXT NOT NULL, sealed INTEGER NOT NULL CHECK (sealed IN (0, 1)))""",
    """CREATE TABLE IF NOT EXISTS ledger_postings (
        sequence INTEGER NOT NULL REFERENCES ledger_events(sequence),
        ordinal INTEGER NOT NULL CHECK (ordinal >= 0), account TEXT NOT NULL,
        asset TEXT NOT NULL REFERENCES ledger_assets(asset), units TEXT NOT NULL,
        PRIMARY KEY (sequence, ordinal))""",
    """CREATE TABLE IF NOT EXISTS ledger_balances (
        account TEXT NOT NULL, asset TEXT NOT NULL REFERENCES ledger_assets(asset),
        units TEXT NOT NULL, PRIMARY KEY (account, asset))""",
    """CREATE TRIGGER IF NOT EXISTS ledger_events_no_delete
        BEFORE DELETE ON ledger_events BEGIN SELECT RAISE(ABORT, 'journal is append-only'); END""",
    """CREATE TRIGGER IF NOT EXISTS ledger_events_seal_only
        BEFORE UPDATE ON ledger_events
        WHEN OLD.sealed != 0 OR NEW.sealed != 1 OR NEW.sequence != OLD.sequence
          OR NEW.event_id != OLD.event_id OR NEW.fingerprint != OLD.fingerprint
          OR NEW.previous_hash != OLD.previous_hash OR NEW.event_hash != OLD.event_hash
        BEGIN SELECT RAISE(ABORT, 'journal is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS ledger_postings_no_update
        BEFORE UPDATE ON ledger_postings BEGIN SELECT RAISE(ABORT, 'journal is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS ledger_postings_no_delete
        BEFORE DELETE ON ledger_postings BEGIN SELECT RAISE(ABORT, 'journal is immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS ledger_postings_unsealed_only
        BEFORE INSERT ON ledger_postings
        WHEN (SELECT sealed FROM ledger_events WHERE sequence = NEW.sequence) != 0
        BEGIN SELECT RAISE(ABORT, 'journal is sealed'); END""",
    """CREATE TRIGGER IF NOT EXISTS ledger_assets_no_update
        BEFORE UPDATE ON ledger_assets BEGIN SELECT RAISE(ABORT, 'asset scales are immutable'); END""",
    """CREATE TRIGGER IF NOT EXISTS ledger_assets_no_delete
        BEFORE DELETE ON ledger_assets BEGIN SELECT RAISE(ABORT, 'asset scales are immutable'); END""",
)


class DurableLedger:
    """Persistent double-entry journal with exact integer minor-unit balances.

    Negative balances are allowed: credit and margin policy belong to the trading
    service. Event IDs are global to this ledger, retained across restarts, and
    cannot be reused with different postings. Passing ``connection`` joins an
    existing Database transaction without committing it. A failed post rolls
    back its own savepoint without discarding the caller's other changes.
    """

    def __init__(self, database: Database, scales: Mapping[str, int]):
        if not isinstance(database, Database):
            raise StorageError("database must be a Database")
        # The existing ledger is the common codec/range validator. Its private
        # exact conversions do not use the ambient decimal arithmetic context.
        self._codec = Ledger(scales)
        self.database = database
        self.scales = MappingProxyType(dict(scales))
        with database.transaction() as connection:
            for statement in _SCHEMA:
                connection.execute(statement)
            version = connection.execute("SELECT version FROM ledger_schema WHERE singleton = 1").fetchone()
            if version is None:
                connection.execute("INSERT INTO ledger_schema VALUES (1, ?)", (_SCHEMA_VERSION,))
            elif version[0] != _SCHEMA_VERSION:
                raise StorageError(f"unsupported ledger schema version: {version[0]}")
            stored = dict(connection.execute("SELECT asset, scale FROM ledger_assets"))
            if not stored:
                connection.executemany("INSERT INTO ledger_assets VALUES (?, ?)", sorted(self.scales.items()))
            elif stored != self.scales:
                raise LedgerError("configured asset scales differ from the persistent ledger")

    def _normalize(self, event_id: str, postings: Sequence[Posting]) -> tuple[tuple[str, str, int], ...]:
        if not isinstance(event_id, str) or not event_id.strip() or len(event_id) > 256:
            raise LedgerError("event_id must be a nonempty string of at most 256 characters")
        if not isinstance(postings, (list, tuple)) or len(postings) < 2:
            raise LedgerError("at least two postings are required")
        normalized = []
        totals: dict[str, int] = {}
        for posting in postings:
            if (not isinstance(posting, Posting) or not isinstance(posting.account, str)
                    or not posting.account.strip() or len(posting.account) > 256):
                raise LedgerError("each posting requires an account of at most 256 characters")
            if not isinstance(posting.asset, str):
                raise LedgerError("asset must be a string")
            units = self._codec._units(posting.asset, posting.amount)
            if not units:
                raise LedgerError("zero postings are not allowed")
            normalized.append((posting.account, posting.asset, units))
            totals[posting.asset] = totals.get(posting.asset, 0) + units
        if any(totals.values()):
            raise LedgerError("event must balance independently for every asset")
        return tuple(sorted(normalized))

    @staticmethod
    def _fingerprint(canonical: tuple[tuple[str, str, int], ...]) -> str:
        return sha256(json.dumps(canonical, ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()

    @staticmethod
    def _hash(sequence: int, event_id: str, previous_hash: str, fingerprint: str) -> str:
        content = json.dumps([sequence, event_id, previous_hash, fingerprint], ensure_ascii=True,
                             separators=(",", ":")).encode()
        return sha256(content).hexdigest()

    def _event(self, connection: sqlite3.Connection, sequence: int, event_id: str) -> JournalEvent:
        rows = connection.execute(
            "SELECT account, asset, units FROM ledger_postings WHERE sequence = ? ORDER BY ordinal",
            (sequence,)).fetchall()
        return JournalEvent(event_id, sequence, tuple(
            Posting(row[0], row[1], self._codec._amount(row[1], self._stored_units(row[2])))
            for row in rows))

    @staticmethod
    def _stored_units(value: str) -> int:
        if not isinstance(value, str) or len(value) > 39:
            raise LedgerError("corrupt ledger integer")
        try:
            units = int(value)
        except ValueError as exc:
            raise LedgerError("corrupt ledger integer") from exc
        if str(units) != value or abs(units) >= Ledger._LIMIT:
            raise LedgerError("corrupt or out-of-range ledger integer")
        return units

    def post(self, event_id: str, postings: Sequence[Posting], *,
             connection: sqlite3.Connection | None = None) -> JournalEvent:
        canonical = self._normalize(event_id, postings)
        fingerprint = self._fingerprint(canonical)
        with self.database._using(connection) as current:
            existing = current.execute(
                "SELECT sequence, fingerprint, sealed FROM ledger_events WHERE event_id = ?", (event_id,)).fetchone()
            if existing is not None:
                event = self._event(current, existing[0], event_id)
                if existing[2] != 1 or existing[1] != self._fingerprint(self._normalize(event_id, event.postings)):
                    raise LedgerError("corrupt existing journal event")
                if existing[1] != fingerprint or self._normalize(event_id, event.postings) != canonical:
                    raise LedgerError("event ID reused with different postings")
                return event
            previous = current.execute(
                "SELECT sequence, event_hash, sealed FROM ledger_events ORDER BY sequence DESC LIMIT 1").fetchone()
            if previous is not None and previous[2] != 1:
                raise LedgerError("unsealed journal event")
            sequence, previous_hash = (previous[0] + 1, previous[1]) if previous else (1, _GENESIS)
            deltas: dict[tuple[str, str], int] = {}
            for account, asset, units in canonical:
                key = (account, asset)
                deltas[key] = deltas.get(key, 0) + units
            changes = []
            for (account, asset), delta in sorted(deltas.items()):
                row = current.execute(
                    "SELECT units FROM ledger_balances WHERE account = ? AND asset = ?", (account, asset)).fetchone()
                balance = (self._stored_units(row[0]) if row else 0) + delta
                if abs(balance) >= Ledger._LIMIT:
                    raise LedgerError("balance exceeds supported range")
                changes.append((account, asset, str(balance)))
            # A savepoint makes this operation atomic even if a caller catches
            # an INSERT/trigger failure and continues its surrounding transaction.
            savepoint = "ledger_" + uuid4().hex
            current.execute(f"SAVEPOINT {savepoint}")
            try:
                current.execute("INSERT INTO ledger_events VALUES (?, ?, ?, ?, ?, 0)",
                                (sequence, event_id, fingerprint, previous_hash,
                                 self._hash(sequence, event_id, previous_hash, fingerprint)))
                current.executemany("INSERT INTO ledger_postings VALUES (?, ?, ?, ?, ?)",
                                    [(sequence, ordinal, account, asset, str(units))
                                     for ordinal, (account, asset, units) in enumerate(canonical)])
                current.executemany(
                    "INSERT INTO ledger_balances VALUES (?, ?, ?) "
                    "ON CONFLICT(account, asset) DO UPDATE SET units = excluded.units", changes)
                current.execute("UPDATE ledger_events SET sealed = 1 WHERE sequence = ?", (sequence,))
                current.execute(f"RELEASE SAVEPOINT {savepoint}")
            except BaseException:
                # SQLITE_FULL/IOERR may automatically roll back the entire
                # transaction, including its savepoints. Preserve that failure
                # instead of replacing it with "no such savepoint".
                if current.in_transaction:
                    current.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                    current.execute(f"RELEASE SAVEPOINT {savepoint}")
                raise
            return JournalEvent(event_id, sequence, tuple(
                Posting(account, asset, self._codec._amount(asset, units))
                for account, asset, units in canonical))

    def balance(self, account: str, asset: str, *,
                connection: sqlite3.Connection | None = None) -> Decimal:
        if asset not in self.scales:
            raise LedgerError(f"unknown asset: {asset}")
        if not isinstance(account, str) or not account.strip():
            raise LedgerError("account is required")
        with self.database._using(connection) as current:
            row = current.execute("SELECT units FROM ledger_balances WHERE account = ? AND asset = ?",
                                  (account, asset)).fetchone()
            return self._codec._amount(asset, self._stored_units(row[0]) if row else 0)

    def journal(self, *, connection: sqlite3.Connection | None = None) -> tuple[JournalEvent, ...]:
        with self.database._using(connection) as current:
            rows = current.execute("SELECT sequence, event_id, sealed FROM ledger_events ORDER BY sequence").fetchall()
            if any(row[2] != 1 for row in rows):
                raise LedgerError("unsealed journal event")
            return tuple(self._event(current, row[0], row[1]) for row in rows)

    def verify(self, *, connection: sqlite3.Connection | None = None) -> int:
        """Independently replay the journal and compare its hashes and balances.

        Returns the count of verified events. Raises LedgerError on corruption.
        Verification holds a transaction, so it sees one consistent state.
        """
        with self.database._using(connection) as current:
            if [row[0] for row in current.execute("PRAGMA integrity_check")] != ["ok"]:
                raise LedgerError("database integrity check failed")
            if current.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise LedgerError("database foreign-key check failed")
            version = current.execute("SELECT version FROM ledger_schema WHERE singleton = 1").fetchone()
            if version is None or version[0] != _SCHEMA_VERSION:
                raise LedgerError("ledger schema version changed")
            if dict(current.execute("SELECT asset, scale FROM ledger_assets")) != self.scales:
                raise LedgerError("ledger asset scales changed")
            expected_triggers = {statement.split("EXISTS ", 1)[1].split()[0]
                                 for statement in _SCHEMA if statement.startswith("CREATE TRIGGER")}
            installed = {row[0] for row in current.execute("SELECT name FROM sqlite_master WHERE type = 'trigger'")}
            if not expected_triggers <= installed:
                raise LedgerError("journal protection trigger is missing")
            projected: dict[tuple[str, str], int] = {}
            previous_hash = _GENESIS
            rows = current.execute("SELECT sequence, event_id, fingerprint, previous_hash, event_hash, sealed "
                                   "FROM ledger_events ORDER BY sequence").fetchall()
            for expected_sequence, row in enumerate(rows, 1):
                sequence, event_id, fingerprint, prior, event_hash, sealed = tuple(row)
                if sequence != expected_sequence or sealed != 1 or prior != previous_hash:
                    raise LedgerError("journal sequence or hash chain is broken")
                postings = current.execute("SELECT ordinal, account, asset, units FROM ledger_postings "
                                           "WHERE sequence = ? ORDER BY ordinal", (sequence,)).fetchall()
                if [posting[0] for posting in postings] != list(range(len(postings))):
                    raise LedgerError("journal posting sequence is broken")
                canonical = tuple((posting[1], posting[2], self._stored_units(posting[3])) for posting in postings)
                normalized = self._normalize(event_id, [
                    Posting(account, asset, self._codec._amount(asset, units)) for account, asset, units in canonical])
                if canonical != normalized or fingerprint != self._fingerprint(normalized):
                    raise LedgerError("journal event fingerprint changed")
                if event_hash != self._hash(sequence, event_id, prior, fingerprint):
                    raise LedgerError("journal event hash changed")
                deltas: dict[tuple[str, str], int] = {}
                for account, asset, units in canonical:
                    key = (account, asset)
                    deltas[key] = deltas.get(key, 0) + units
                for key, delta in deltas.items():
                    projected[key] = projected.get(key, 0) + delta
                    if abs(projected[key]) >= Ledger._LIMIT:
                        raise LedgerError("replayed balance exceeds supported range")
                previous_hash = event_hash
            stored = {(row[0], row[1]): self._stored_units(row[2]) for row in current.execute(
                "SELECT account, asset, units FROM ledger_balances")}
            if stored != projected:
                raise LedgerError("materialized balances differ from journal replay")
            return len(rows)
