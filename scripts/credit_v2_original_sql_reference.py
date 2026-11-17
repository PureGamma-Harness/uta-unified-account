"""Independent read-only reopening of ONE retained synthetic credit database.

No production class/exporter/calculator is imported. Only new private synthetic
scratch is eligible; this is never a reader for a running soak or real account.
"""
from collections import defaultdict
from contextlib import closing
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import stat


_SPEC = importlib.util.spec_from_file_location("owned_capture_reference", Path(__file__).with_name("credit_v2_capture_reference.py"))
CAPTURE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(CAPTURE)
REF = CAPTURE.REF
need, equal = CAPTURE.need, CAPTURE.equal


def one(connection, sql, params=()):
    rows = connection.execute(sql, params).fetchall()
    need(len(rows) == 1, "exactly one original SQL row required: "+sql)
    return dict(rows[0])


def journal(connection, event_id):
    result = one(connection, "SELECT * FROM ledger_events WHERE event_id=?", (event_id,))
    result["postings"] = [dict(row) for row in connection.execute(
        "SELECT ordinal,account,asset,units FROM ledger_postings WHERE sequence=? ORDER BY ordinal", (result["sequence"],))]
    return result


def observation(connection, command_id):
    inbox = one(connection, "SELECT * FROM uta_command_inbox WHERE command_id=?", (command_id,))
    account = inbox["account_id"]
    credit = one(connection, "SELECT * FROM credit_commands WHERE scope=? AND command_id=?", ("account:"+account, command_id))
    decision = one(connection, "SELECT * FROM uta_credit_decisions WHERE command_id=? AND account_id=?", (command_id, account))
    bundle = {"format": 2, "decision": decision,
        "market": one(connection, "SELECT * FROM uta_market_history WHERE snapshot_id=?", (decision["market_snapshot_id"],)),
        "artifact": one(connection, "SELECT * FROM uta_credit_code_artifacts WHERE artifact_id=?", (decision["artifact_id"],)),
        "policy": one(connection, "SELECT * FROM uta_credit_risk_policies WHERE policy_id=?", (decision["policy_id"],))}
    return {"source": one(connection, "SELECT * FROM credit_v2_sources WHERE command_id=?", (command_id,)),
        "inbox": inbox, "intent": one(connection, "SELECT * FROM credit_v2_intents WHERE command_id=?", (command_id,)),
        "expected_postings": [dict(row) for row in connection.execute(
            "SELECT * FROM credit_v2_expected_postings WHERE command_id=? ORDER BY ordinal", (command_id,))],
        "credit": credit, "journal": journal(connection, credit["journal_event_id"]), "decision_bundle": bundle}


def replay_original_journal(connection, *, pre_head):
    """Rebuild every balance from ordered sealed rows with per-asset zero sum."""
    assets = {row["asset"]: row["scale"] for row in connection.execute("SELECT asset,scale FROM ledger_assets")}
    equal(assets, {"USD": 8, "BTC": 8}, "original ledger unit catalog differs")
    balances = defaultdict(int)
    prior, sequence, before = "0"*64, 0, None
    if pre_head["sequence"] == 0:
        equal(pre_head, {"sequence": 0, "event_hash": prior}, "non-genesis empty prehead")
        before = {}
    events = connection.execute("SELECT * FROM ledger_events ORDER BY sequence").fetchall()
    need(len(events) <= 10000, "small synthetic independent replay bound exceeded")
    for row in events:
        entry = dict(row)
        equal(entry["sequence"], sequence+1, "original journal gap")
        need(entry["previous_hash"] == prior and type(entry["sealed"]) is int and entry["sealed"] == 1,
             "journal is not a sealed original chain")
        legs, currency = [], defaultdict(int)
        for ordinal, posting in enumerate(connection.execute(
                "SELECT ordinal,account,asset,units FROM ledger_postings WHERE sequence=? ORDER BY ordinal", (entry["sequence"],))):
            posting = dict(posting)
            equal(posting["ordinal"], ordinal, "original journal ordinal gap")
            need(posting["asset"] in assets and type(posting["account"]) is str and posting["account"], "unsupported journal account/currency")
            units = REF.unit_string(posting["units"], "actual SQL posting")
            need(units != 0, "zero actual SQL posting")
            currency[posting["asset"]] += units
            balances[(posting["account"], posting["asset"])] += units
            legs.append({**posting, "units": units})
        need(bool(legs) and all(total == 0 for total in currency.values()), "original event is not balanced per currency")
        fingerprint, event_hash = REF.journal_hashes(entry["sequence"], entry["event_id"], prior, legs)
        need(entry["fingerprint"] == fingerprint and entry["event_hash"] == event_hash, "original event hash differs from actual rows")
        prior, sequence = event_hash, entry["sequence"]
        if sequence == pre_head["sequence"]:
            need(event_hash == pre_head["event_hash"], "retained prehead differs from original chain")
            before = dict(balances)
    need(before is not None, "retained prehead not found in original chain")
    current = {}
    for row in connection.execute("SELECT account,asset,units FROM ledger_balances ORDER BY account,asset"):
        current[(row["account"], row["asset"])] = REF.unit_string(row["units"], "actual SQL balance")
    equal(sorted([*key, value] for key, value in current.items()), sorted([*key, value] for key, value in balances.items()),
          "replayed original postings differ from materialized balances")
    return before, dict(balances), {"events": sequence, "journal_head": prior, "currencies": sorted(assets),
        "every_event_balanced_per_currency": True, "replayed_all_actual_balances_equal": True}


def compare_ledger_snapshot(expected, balances, account_id, *, label):
    account, credit = expected["account"], expected["credit"]
    for asset in ("USD", "BTC"):
        need(balances.get(("customer:"+account_id, asset), 0) == CAPTURE.decimal_units(account["balances"][asset], asset),
             label+" customer cash differs from original journal replay")
    names = {"principal_ledger_units": "liability:principal:"+account_id, "interest_ledger_units": "liability:interest:"+account_id,
        "pool_units": "system:credit-pool", "principal_receivable_units": "system:credit-principal-receivable",
        "interest_receivable_units": "system:credit-interest-receivable"}
    for field, name in names.items():
        need(balances.get((name, "BTC"), 0) == REF.unit_string(credit[field], field), label+" gross ledger component differs: "+field)


def check_original(connection, command_id, *, exported=None):
    current = observation(connection, command_id)
    if exported is not None:
        equal(current, exported, "independently selected original SQL differs from supplied export")
    content = CAPTURE.check_observation(current)
    payload = CAPTURE.document(current["decision_bundle"]["decision"]["payload"])
    account_id = payload["account_id"]
    before, balances, journal_report = replay_original_journal(connection, pre_head=payload["pre_state"]["journal_head"])
    compare_ledger_snapshot(payload["pre_state"], before, account_id, label="prehead")
    compare_ledger_snapshot(payload["post_state"], balances, account_id, label="post-COMMIT")
    post = payload["post_state"]
    equal(one(connection, "SELECT version FROM uta_accounts WHERE account_id=?", (account_id,))["version"], post["account"]["version"], "post account version differs")
    liabilities = [dict(row) for row in connection.execute(
        "SELECT asset,principal,interest FROM uta_liabilities WHERE account_id=? ORDER BY asset", (account_id,))]
    equal(liabilities, post["account"]["liabilities"], "actual gross liability rows differ")
    positions = {row["symbol"]: {"quantity": row["quantity"], "cost_basis": row["cost_basis"]} for row in connection.execute(
        "SELECT symbol,quantity,cost_basis FROM uta_positions WHERE account_id=? ORDER BY symbol", (account_id,))}
    equal(positions, post["account"]["positions"], "actual position rows differ")
    orders = [dict(row) for row in connection.execute(
        "SELECT * FROM uta_orders WHERE account_id=? AND status IN ('OPEN','PARTIALLY_FILLED') ORDER BY order_id", (account_id,))]
    equal(orders, post["account"]["orders"], "actual live order rows differ")
    for field, table, where, params in (
            ("account_limit_units", "credit_account_limits", "account_id=? AND asset=?", (account_id, "BTC")),
            ("local_asset_limit_units", "credit_asset_limits", "asset=?", ("BTC",))):
        equal(one(connection, "SELECT units FROM "+table+" WHERE "+where, params)["units"], post["limits"][field], "actual limit differs")
    total_p = total_i = 0
    for row in connection.execute("SELECT principal,interest FROM uta_liabilities WHERE asset='BTC'"):
        total_p += CAPTURE.decimal_units(row["principal"], "actual aggregate principal")
        total_i += CAPTURE.decimal_units(row["interest"], "actual aggregate interest")
    need(str(total_p) == post["credit"]["shard_principal_units"] and str(total_i) == post["credit"]["shard_interest_units"], "actual aggregate debt differs")
    # Interest cash is queried here even though the borrowed-decision payload
    # omits it. Borrow must leave that actual prehead ledger balance unchanged.
    interest_cash = ("system:credit-interest-cash", "BTC")
    need(before.get(interest_cash, 0) == balances.get(interest_cash, 0), "borrow changed actual interest cash")
    need(connection.total_changes == 0, "independent reader wrote logical rows")
    return {"independent_original_SQL_reopen_passed": True, "content": content, "journal": journal_report,
        "actual_prehead_gross_ledger_equals_retained_prestate": True,
        "actual_post_gross_ledger_and_liabilities_equal_retained_poststate": True,
        "actual_interest_cash_unchanged_units": str(balances.get(interest_cash, 0)),
        "SQL_selected_without_production_exporter": True, "logical_changes": connection.total_changes,
        "producer_COMMIT_native_owner_FIFO_crash_and_replication_provenance": "PENDING_SEPARATE_EXECUTION_EVIDENCE",
        "production_approved": False}


def read_private_original(path, command_id, *, exported=None):
    path = Path(path)
    original = path.lstat()
    parent = path.parent.stat()
    need(stat.S_ISREG(original.st_mode) and original.st_uid == os.geteuid(), "owned original regular database required")
    need(parent.st_uid == os.geteuid() and stat.S_IMODE(parent.st_mode) == 0o700, "owned private0700 scratch parent required")
    need(not path.is_symlink(), "original database cannot be a symlink")
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
            result = check_original(connection, command_id, exported=exported)
        finally:
            connection.rollback()
    after = path.stat()
    need((original.st_dev, original.st_ino) == (after.st_dev, after.st_ino), "original file identity changed")
    result.update(started_at=started, finished_at=datetime.now(timezone.utc).isoformat(), database_path=str(path),
        original_file_identity={"device": original.st_dev, "inode": original.st_ino},
        read_policy="mode=ro + query_only + select-only authorizer + one read snapshot")
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--command-id", required=True)
    parser.add_argument("--exported-observation", type=Path)
    args = parser.parse_args()
    exported = REF.strict_loads(args.exported_observation.read_text()) if args.exported_observation else None
    print(json.dumps(read_private_original(args.database, args.command_id, exported=exported), indent=2, sort_keys=True))
