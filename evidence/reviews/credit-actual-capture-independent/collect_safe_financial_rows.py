"""Explicit small synthetic original rows only; no authority/auth tables."""
from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import stat

QUERIES = {
    "ledger_assets": "SELECT asset,scale FROM ledger_assets ORDER BY asset",
    "ledger_events": "SELECT sequence,event_id,fingerprint,previous_hash,event_hash,sealed FROM ledger_events ORDER BY sequence",
    "ledger_postings": "SELECT sequence,ordinal,account,asset,units FROM ledger_postings ORDER BY sequence,ordinal",
    "ledger_balances": "SELECT account,asset,units FROM ledger_balances ORDER BY account,asset",
    "uta_accounts": "SELECT account_id,version FROM uta_accounts ORDER BY account_id",
    "uta_liabilities": "SELECT account_id,asset,principal,interest FROM uta_liabilities ORDER BY account_id,asset",
    "uta_positions": "SELECT account_id,symbol,quantity,cost_basis FROM uta_positions ORDER BY account_id,symbol",
    "credit_asset_limits": "SELECT asset,units FROM credit_asset_limits ORDER BY asset",
    "credit_account_limits": "SELECT account_id,asset,units FROM credit_account_limits ORDER BY account_id,asset",
}


def collect(path):
    details, parent = path.lstat(), path.parent.stat()
    if (not stat.S_ISREG(details.st_mode) or details.st_uid != os.geteuid()
            or stat.S_IMODE(parent.st_mode) != 0o700 or parent.st_uid != os.geteuid()):
        raise ValueError("original owned regular DB in private synthetic0700 scratch required")
    started = datetime.now(timezone.utc).isoformat()
    with closing(sqlite3.connect(path.resolve().as_uri()+"?mode=ro", uri=True, timeout=.1, isolation_level=None)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        def readonly(action, first, second, database, context):
            if action in {sqlite3.SQLITE_READ, sqlite3.SQLITE_SELECT, sqlite3.SQLITE_FUNCTION}:
                return sqlite3.SQLITE_OK
            if action == sqlite3.SQLITE_TRANSACTION and first in {"BEGIN", "ROLLBACK"}:
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY
        connection.set_authorizer(readonly)
        connection.execute("BEGIN")
        try:
            tables = {}
            for name, query in QUERIES.items():
                rows = connection.execute(query).fetchmany(1001)
                if len(rows) > 1000:
                    raise ValueError("small synthetic row cap exceeded")
                tables[name] = [dict(row) for row in rows]
            if connection.total_changes != 0:
                raise ValueError("safe original collector wrote rows")
        finally:
            connection.rollback()
    return {"scope": "original synthetic SQL rows from fixed allowlist only", "tables": tables,
        "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
        "logical_changes": 0, "auth_fence_nonce_tables_read": False,
        "collector_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "native_execution_or_production_approval": False}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    args = parser.parse_args()
    print(json.dumps(collect(args.database), indent=2, sort_keys=True))
