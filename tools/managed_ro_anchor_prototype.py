"""Experimental producer-owned idle WAL readers; not connected to any service.

Only owned temporary fixtures may use this prototype until separately reviewed.
It neither implements a consistent snapshot nor establishes financial readiness.
"""
from pathlib import Path
import os
import sqlite3
import stat
from threading import get_ident


WARM_READS = (
    ('checkpoint.sqlite3', 'SELECT key FROM state LIMIT 1'),
    ('managed/router.sqlite3', 'SELECT singleton FROM router_layout LIMIT 1'),
    ('managed/shard-0000.sqlite3', 'SELECT sequence FROM ledger_events LIMIT 1'),
)


def _read(connection, statement):
    cursor = connection.execute(statement)
    try:
        return cursor.fetchall()
    finally:
        cursor.close()


def _identity(path):
    details = path.stat(follow_symlinks=False)
    if (not stat.S_ISREG(details.st_mode) or details.st_uid != os.geteuid()
            or stat.S_IMODE(details.st_mode) & 0o077):
        raise ValueError('existing private direct regular main file required')
    return details.st_dev, details.st_ino


class IdleReadHolders:
    """Single-thread owned, all-or-close prototype with real SQLite connections."""
    def __init__(self, directory):
        self.owner_thread = get_ident()
        self.connections = []
        try:
            for relative, statement in WARM_READS:
                path = Path(directory).absolute() / relative
                identity = _identity(path)
                connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True,
                    timeout=.2, isolation_level=None)
                self.connections.append(connection)
                _read(connection, 'PRAGMA query_only=ON')
                if _read(connection, 'PRAGMA journal_mode') != [('wal',)]:
                    raise ValueError('existing WAL format required; never enable or repair it')
                if not _read(connection, statement):
                    raise ValueError('initialized warm B-tree row required')
                if connection.in_transaction or _read(connection, 'PRAGMA query_only') != [(1,)]:
                    raise ValueError('idle query-only autocommit holder required')
                if _identity(path) != identity:
                    raise ValueError('main identity changed during SQLite open')
        except BaseException:
            self.close()
            raise

    def close(self):
        if get_ident() != self.owner_thread:
            raise RuntimeError('holder cleanup must use its owning thread')
        for connection in reversed(self.connections):
            connection.close()
        self.connections.clear()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
