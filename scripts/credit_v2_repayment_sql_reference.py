"""Independent original SQL reopening for retained synthetic REPAY only."""
from contextlib import closing
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import stat


def owned(name):
    spec = importlib.util.spec_from_file_location("owned_"+name, Path(__file__).with_name(name+".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REPAY = owned("credit_v2_repayment_reference")
SQL = owned("credit_v2_original_sql_reference")
need, equal, REF = REPAY.need, REPAY.equal, REPAY.REF


def selected(connection, command_id):
    inbox = SQL.one(connection, "SELECT * FROM uta_command_inbox WHERE command_id=?", (command_id,))
    credit = SQL.one(connection, "SELECT * FROM credit_commands WHERE scope=? AND command_id=?", ("account:"+inbox["account_id"], command_id))
    financial = {table: [dict(row) for row in connection.execute("SELECT * FROM "+table+" ORDER BY rowid")]
                 for table in sorted(REPAY.ROW_TABLES)}
    interest_cash = connection.execute("SELECT units FROM ledger_balances WHERE account='system:credit-interest-cash' AND asset='BTC'").fetchone()
    return {"source": SQL.one(connection, "SELECT * FROM credit_v2_sources WHERE command_id=?", (command_id,)),
        "inbox": inbox, "intent": SQL.one(connection, "SELECT * FROM credit_v2_intents WHERE command_id=?", (command_id,)),
        "expected_postings": [dict(row) for row in connection.execute(
            "SELECT * FROM credit_v2_expected_postings WHERE command_id=? ORDER BY ordinal", (command_id,))],
        "credit": credit, "journal": SQL.journal(connection, credit["journal_event_id"]), "decision_bundle": None,
        "actual_financial_rows": financial, "actual_post_interest_cash_units": "0" if interest_cash is None else interest_cash[0]}


def read_original(path, exported):
    path = Path(path)
    initial, parent = path.lstat(), path.parent.stat()
    need(stat.S_ISREG(initial.st_mode) and initial.st_uid == os.geteuid(), "owned original regular DB required")
    need(parent.st_uid == os.geteuid() and stat.S_IMODE(parent.st_mode) == 0o700, "owned private0700 parent required")
    need(not path.is_symlink(), "original DB symlink forbidden")
    command_id = exported["inbox"]["command_id"]
    started = datetime.now(timezone.utc).isoformat()
    with closing(sqlite3.connect(path.resolve().as_uri()+"?mode=ro", uri=True, timeout=.1, isolation_level=None)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        def readonly(action, first, second, database, context):
            if action in {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION}:
                return sqlite3.SQLITE_OK
            if action == sqlite3.SQLITE_TRANSACTION and first in {"BEGIN", "ROLLBACK"}:
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY
        connection.set_authorizer(readonly)
        connection.execute("BEGIN")
        try:
            current = selected(connection, command_id)
            equal(current, exported, "independently selected original repayment SQL differs from supplied observation")
            content = REPAY.check_repayment(current)
            count = connection.execute("SELECT COUNT(*) FROM uta_credit_decisions WHERE command_id=?", (command_id,)).fetchone()[0]
            need(count == 0, "repayment generated a new borrowing decision")
            fifo = [dict(row) for row in connection.execute("SELECT sequence,account_id,command_id,state FROM uta_command_inbox WHERE account_id=? ORDER BY sequence", (current["inbox"]["account_id"],))]
            sequence = current["inbox"]["sequence"]
            need(not any(row["sequence"] < sequence and row["state"] == "PENDING" for row in fifo), "original final FIFO has unresolved predecessor")
            need(connection.total_changes == 0, "independent repayment reader wrote rows")
        finally:
            connection.rollback()
    final = path.stat()
    need((initial.st_dev, initial.st_ino) == (final.st_dev, final.st_ino), "original file identity changed")
    return {"independent_original_repayment_SQL_reopen_passed": True, "content": content,
        "borrow_decisions_for_original_CID": count, "original_final_account_FIFO": fifo,
        "logical_changes": 0, "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
        "database_path": str(path), "original_file_identity": {"device": initial.st_dev, "inode": initial.st_ino},
        "read_policy": "mode=ro + query_only + select authorizer + one original read snapshot",
        "FIFO_at_execution_source_and_native_COMMIT_atomicity_provenance": "PENDING_SEPARATE_EXECUTION_EVIDENCE",
        "production_approved": False}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--command-id", required=True)
    args = parser.parse_args()
    document = REF.strict_loads(args.observations.read_text())
    cases = [case for case in document["observations"] if case["inbox"]["command_id"] == args.command_id]
    need(len(cases) == 1, "exact original repayment case required")
    print(json.dumps(read_original(args.database, cases[0]), indent=2, sort_keys=True))
