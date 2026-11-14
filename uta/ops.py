"""Offline checks and consistent SQLite backups; no exchange mutations.

The backup API takes a consistent SQLite snapshot, including committed WAL
transactions. Never back up a running database by copying its main file alone.
Checks here cover SQLite structure and foreign keys, not business reconciliation.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import tempfile
import time
from typing import Iterator


class OperationsError(ValueError):
    """The requested storage operation could not be safely completed."""


def _source(path: str | Path) -> Path:
    candidate = Path(path).expanduser()
    if candidate.is_symlink():
        raise OperationsError("source must not be a symbolic link")
    try:
        details = candidate.stat()
    except OSError as exc:
        raise OperationsError("source database does not exist or is not accessible") from exc
    if not stat.S_ISREG(details.st_mode) or details.st_size == 0:
        raise OperationsError("source must be a nonempty regular SQLite database")
    return candidate.resolve()


def _timeout(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OperationsError("timeout must be between 0 and 3600 seconds")
    if not 0 < value <= 3600:
        raise OperationsError("timeout must be between 0 and 3600 seconds")
    return float(value)


@contextmanager
def _readonly(path: Path, timeout: float) -> Iterator[sqlite3.Connection]:
    # as_uri() quotes '#'/'?' and other filename characters before appending URI
    # parameters. mode=ro cannot silently create a new empty source database.
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=timeout)
    try:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("PRAGMA trusted_schema=OFF")
        deadline = time.monotonic() + timeout
        connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
        yield connection
    finally:
        connection.close()


def _check(connection: sqlite3.Connection) -> dict:
    results = [row[0] for row in connection.execute("PRAGMA integrity_check")]
    if results != ["ok"]:
        raise OperationsError("SQLite integrity check failed")
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise OperationsError("SQLite foreign key check failed")
    tables = [row[0] for row in connection.execute(
        "SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )]
    if not tables:
        raise OperationsError("database has no application tables")
    return {
        "integrity": "ok",
        "foreign_keys": "ok",
        "tables": tables,
        "page_count": connection.execute("PRAGMA page_count").fetchone()[0],
        "page_size": connection.execute("PRAGMA page_size").fetchone()[0],
    }


def check_database(database: str | Path, *, timeout: float = 30) -> dict:
    """Check one read transaction without creating or updating database state.

    The result does not assert external balances, order truth, or ledger replay.
    A live WAL file may legitimately change immediately after this snapshot.
    """
    limit = _timeout(timeout)
    path = _source(database)
    try:
        with _readonly(path, limit) as connection:
            connection.execute("BEGIN")
            result = _check(connection)
        return {"database": str(path), **result}
    except sqlite3.Error as exc:
        raise OperationsError("database could not be checked as valid SQLite") from exc


def _destination(path: str | Path) -> Path:
    candidate = Path(path).expanduser()
    # Resolve the parent only: resolving an existing destination symlink would
    # conceal it. lexists also catches a dangling destination symlink.
    try:
        parent = candidate.parent.resolve(strict=True)
    except OSError as exc:
        raise OperationsError("destination parent directory must already exist") from exc
    if not parent.is_dir() or not candidate.name:
        raise OperationsError("destination parent must be a directory")
    destination = parent / candidate.name
    for item in (destination, *(Path(str(destination) + suffix)
                                  for suffix in ("-wal", "-shm", "-journal"))):
        if os.path.lexists(item):
            raise OperationsError("destination and SQLite sidecar paths must not exist")
    return destination


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def backup_database(database: str | Path, output: str | Path, *, timeout: float = 30) -> dict:
    """Publish an exclusive, fsynced, mode-0600 consistent snapshot.

    Source WAL transactions are included by sqlite3.Connection.backup(). A
    temporary file in the destination directory prevents incomplete backups
    from appearing at the final path. An existing destination is never replaced.
    A continuously busy or corrupt source fails without a published partial file.
    """
    limit = _timeout(timeout)
    source = _source(database)
    destination = _destination(output)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".uta-snapshot-", dir=destination.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    deadline = time.monotonic() + limit

    def progress(status: int, remaining: int, total: int) -> None:
        if time.monotonic() > deadline:
            raise OperationsError("backup timed out before a consistent snapshot completed")

    try:
        with _readonly(source, limit) as reader:
            writer = sqlite3.connect(temporary, timeout=limit)
            try:
                writer.execute("PRAGMA synchronous=FULL")
                reader.backup(writer, pages=256, progress=progress, sleep=0.01)
                # Make a standalone DELETE-mode artifact; its consumers need no
                # WAL or SHM files. The original database remains untouched.
                writer.execute("PRAGMA journal_mode=DELETE")
                writer.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
                result = _check(writer)
            finally:
                writer.close()
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        digest = _sha256(temporary)
        # Hard-link publication is atomic and exclusive even if another process
        # creates the destination after our preflight check. Both files are on
        # the same filesystem because mkstemp used the destination directory.
        os.link(temporary, destination)
        _fsync_directory(destination.parent)
        return {
            "database": str(source), "output": str(destination),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "sha256": digest, "bytes": destination.stat().st_size,
            **result,
        }
    except sqlite3.Error as exc:
        raise OperationsError("backup failed SQLite validation or could not complete") from exc
    except OSError as exc:
        raise OperationsError("backup could not be safely written to its destination") from exc
    finally:
        temporary.unlink(missing_ok=True)
        for suffix in ("-wal", "-shm", "-journal"):
            Path(str(temporary) + suffix).unlink(missing_ok=True)


def restore_database(backup: str | Path, database: str | Path, *, timeout: float = 30) -> dict:
    """Create an offline restore at an unused path; never replace a live DB.

    Stop the exchange before selecting a restored database. The operator must
    reconcile events/fills after the backup watermark before re-enabling orders.
    """
    result = backup_database(backup, database, timeout=timeout)
    return {**result, "operation": "restore", "requires_reconciliation": True}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Consistent UTA SQLite backup and offline checks")
    subcommands = parser.add_subparsers(dest="command", required=True)
    check = subcommands.add_parser("check", help="Check SQLite integrity and foreign keys")
    check.add_argument("--database", required=True)
    check.add_argument("--timeout", type=float, default=30)
    backup = subcommands.add_parser("backup", help="Create a consistent backup at a new path")
    backup.add_argument("--database", required=True)
    backup.add_argument("--output", required=True)
    backup.add_argument("--timeout", type=float, default=30)
    restore = subcommands.add_parser("restore", help="Restore to an unused database path")
    restore.add_argument("--backup", required=True)
    restore.add_argument("--database", required=True)
    restore.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            result = check_database(args.database, timeout=args.timeout)
        elif args.command == "backup":
            result = backup_database(args.database, args.output, timeout=args.timeout)
        else:
            result = restore_database(args.backup, args.database, timeout=args.timeout)
    except (OperationsError, OSError) as exc:
        parser.exit(1, f"uta-ops: {exc}\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
