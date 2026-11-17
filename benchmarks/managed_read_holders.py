"""Producer-owned idle WAL readers; never a financial snapshot/readiness proof."""
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
_UNSPECIFIED = object()


def _canonical_main(path):
    # Match Database's parent resolution without following the final main.
    return path.parent.resolve() / path.name


def _normalized_identities(metadata):
    if type(metadata) is not dict:
        raise ValueError('original identity metadata must be a path mapping')
    normalized = {}
    for name, identity in metadata.items():
        if (type(name) is not str or not name or '\0' in name
                or not Path(name).is_absolute()):
            raise ValueError('original identity metadata path must be absolute text')
        if (type(identity) is not list or len(identity) != 2
                or any(type(value) is not int or value < 0 for value in identity)
                or identity[1] == 0):
            raise ValueError('original identity metadata requires integer device/inode pairs')
        key = str(_canonical_main(Path(name)))
        if key in normalized:
            raise ValueError('ambiguous original identity metadata paths')
        normalized[key] = tuple(identity)
    return normalized


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
    """Single-thread owned, all-or-close existing-file SQLite connections."""
    def __init__(self, directory, *, expected_identities=_UNSPECIFIED):
        self.owner_thread = get_ident()
        self.connections = []
        try:
            expected = (None if expected_identities is _UNSPECIFIED
                        else _normalized_identities(expected_identities))
            paths = [(_canonical_main(Path(directory).absolute() / relative), statement)
                     for relative, statement in WARM_READS]
            if expected is not None and any(str(path) not in expected for path, _ in paths):
                raise ValueError('original identity metadata missing required main')
            for path, statement in paths:
                identity = _identity(path)
                if expected is not None and identity != expected[str(path)]:
                    raise ValueError('main identity differs from original job metadata')
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
