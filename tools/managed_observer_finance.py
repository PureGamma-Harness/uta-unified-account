"""Independent read-only, synthetic managed-soak financial observations.

Only stdlib is imported. The caller supplies an existing query-only SQLite read
transaction and owns its close. No service, replay, financial calculator, DB
constructor, process control, or secret-bearing writer lease is used here.
The golden comparison is valid only at a caller-established stable round boundary.
"""
from collections import Counter, defaultdict
from fractions import Fraction
from hashlib import sha256
import json
import re
import sqlite3

ACCOUNTS = ("managed-soak-alice", "managed-soak-bob", "managed-soak-credit")
SCALE = 100_000_000
# Explicit column lists are also the watermark contract. No writer nonce,
# authentication material, absolute authority paths, or private files are read.
COLUMNS = {
    "uta_schema": "version",
    "ledger_assets": "asset,scale",
    "uta_accounts": "account_id,version",
    "ledger_events": "sequence,event_id,fingerprint,previous_hash,event_hash,sealed",
    "ledger_postings": "sequence,ordinal,account,asset,units",
    "ledger_balances": "account,asset,units",
    "uta_orders": "account_id,order_id,symbol,quantity,limit_price,reduce_only,filled_quantity,status,version,created_at,admission_decision_id,charged_fee,fee_notional",
    "uta_fills": "account_id,fill_id,order_id,quantity,price,realized_pnl,fee,execution_decision_id",
    "uta_positions": "account_id,symbol,quantity,cost_basis",
    "uta_liabilities": "account_id,asset,principal,interest",
    "uta_matches": "sequence,trade_id,symbol,buy_account_id,buy_order_id,buy_fill_id,sell_account_id,sell_order_id,sell_fill_id,buy_filled_before,sell_filled_before,quantity,price,market_version,buy_version,sell_version,created_at",
    "uta_command_inbox": "sequence,command_id,account_id,kind,payload,state,result,error,enqueued_at,completed_at,attempts,last_error,next_attempt_at",
    "uta_events": "sequence,event_type,account_id,payload,created_at",
    "credit_commands": "scope,command_id,kind,asset,amount,source_reference,result,journal_event_id,created_at",
    "credit_asset_limits": "asset,units",
    "credit_account_limits": "account_id,asset,units",
    "uta_audit_capability": "singleton,format,enabled_at,legacy_event_watermark,legacy_order_count,legacy_fill_count,gaps",
    "uta_market_history": "snapshot_id,content_digest,payload,origin,recorded_at",
    "uta_code_artifacts": "artifact_id,manifest",
    "uta_risk_policies": "policy_id,payload",
    "uta_risk_decisions": "decision_id,kind,account_id,business_id,market_snapshot_id,artifact_id,policy_id,pre_version,post_version,recorded_at,input_payload,summary_payload",
}
_COMMAND = re.compile(r"ms:[a-f0-9]{24}:r([0-9]{9}):(open-buy|open-sell|cancel-partial|close-sell|close-buy|repay)\Z")
_KINDS = {"SUBMIT_ORDER", "CANCEL_ORDER", "REPAY", "PUBLISH_MARKET", "SET_HALT"}
_OWNERS = {"customer:" + a for a in ACCOUNTS} | {
    "system:custody", "system:credit-capital", "system:credit-pool",
    "system:credit-principal-receivable", "system:fees", "liability:principal:" + ACCOUNTS[2]}


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value):
    return sha256(_canonical(value).encode()).hexdigest()


def _business_digest(tables):
    """Order-independent rows without retaining a second copy of all payloads.

    A table envelope gives the table name and row count. Sorted fixed-size row
    digests retain duplicate multiplicity, and avoid one giant manifest JSON or
    UTF-8 allocation. Domain/version separation makes the byte framing explicit.
    """
    aggregate = sha256(b"managed-observer-financial-watermark-v2\0")
    for table in sorted(tables):
        rows = tables[table]
        aggregate.update(_canonical([table, len(rows)]).encode())
        aggregate.update(b"\0")
        for fingerprint in sorted(sha256(_canonical(row).encode()).digest() for row in rows):
            aggregate.update(fingerprint)
    return aggregate.hexdigest()


def _label(value, permitted):
    return value if value in permitted else "sha256:" + _digest(value)


def _command(value):
    return value if isinstance(value, str) and _COMMAND.fullmatch(value) else "sha256:" + _digest(value)


def _strict_object(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate archive JSON key")
            result[key] = value
        return result
    def invalid(_):
        raise ValueError("nonfinite archive JSON")
    result = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    if not isinstance(raw, str) or not isinstance(result, dict) or _canonical(result) != raw:
        raise ValueError("archive must contain a canonical JSON object")
    return result


def _integer(value):
    if type(value) is int:
        return value
    if not isinstance(value, str) or not re.fullmatch(r"-?(0|[1-9][0-9]*)", value):
        raise ValueError("invalid stored integer minor units")
    return int(value)


def _minor(value):
    result = Fraction(value) * SCALE
    if result.denominator != 1:
        raise ValueError("amount does not have exact eight-digit precision")
    return result.numerator


def _rows(connection):
    result = {}
    for table, columns in COLUMNS.items():
        # uta_matches is initialized by the worker, and is legitimately absent
        # before the first round. All other missing schemas fail closed.
        if table == "uta_matches" and connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='uta_matches'").fetchone() is None:
            result[table] = []
        else:
            result[table] = [dict(row) for row in connection.execute("SELECT " + columns + " FROM " + table)]
    return result


def _expected_balances(planned, completed):
    remaining = 2 * (planned - completed)
    result = {
        ("customer:" + ACCOUNTS[0], "USD"): 1_000_000 * SCALE - 80_000 * completed,
        ("customer:" + ACCOUNTS[1], "USD"): 1_000_000 * SCALE - 80_000 * completed,
        ("customer:" + ACCOUNTS[2], "USD"): 1_000_000 * SCALE,
        ("customer:" + ACCOUNTS[2], "BTC"): SCALE + remaining,
        ("system:custody", "USD"): -3_000_000 * SCALE,
        ("system:custody", "BTC"): -SCALE,
        ("system:credit-capital", "BTC"): -SCALE,
        ("system:credit-pool", "BTC"): SCALE - remaining,
        ("liability:principal:" + ACCOUNTS[2], "BTC"): -remaining,
        ("system:credit-principal-receivable", "BTC"): remaining,
    }
    if completed:
        result[("system:fees", "USD")] = 160_000 * completed
    return result


def _golden(tables, planned, completed):
    errors = []
    def check(condition, code):
        if not condition:
            errors.append(code)
    rows = tables
    remaining = 2 * (planned - completed)
    check([r["version"] for r in rows["uta_schema"]] == [3], "required_schema_3")
    check({r["account_id"] for r in rows["uta_accounts"]} == set(ACCOUNTS)
          and len(rows["uta_accounts"]) == 3, "fixed_three_accounts")
    check({r["asset"]: r["scale"] for r in rows["ledger_assets"]} == {"USD": 8, "BTC": 8}
          and len(rows["ledger_assets"]) == 2, "asset_scales")
    balances = {(r["account"], r["asset"]): _integer(r["units"]) for r in rows["ledger_balances"]}
    check(balances == _expected_balances(planned, completed) and len(balances) == len(rows["ledger_balances"]),
          "complete_gross_owner_asset_budget")
    check({r["asset"]: _integer(r["units"]) for r in rows["credit_asset_limits"]} == {"BTC": SCALE}
          and len(rows["credit_asset_limits"]) == 1, "fixed_pool_asset_limit")
    check({(r["account_id"], r["asset"]): _integer(r["units"]) for r in rows["credit_account_limits"]}
          == {(ACCOUNTS[2], "BTC"): SCALE} and len(rows["credit_account_limits"]) == 1,
          "fixed_account_credit_limit")
    debts = {(r["account_id"], r["asset"]): (_minor(r["principal"]), _minor(r["interest"]))
             for r in rows["uta_liabilities"]}
    check(debts == {(ACCOUNTS[2], "BTC"): (remaining, 0)} and len(rows["uta_liabilities"]) == 1,
          "gross_principal_interest")
    check(not rows["uta_positions"], "residual_positions")
    check(not any(r["status"] in ("OPEN", "PARTIALLY_FILLED") for r in rows["uta_orders"]), "residual_orders")
    for table, count in (("uta_orders", 4 * completed), ("uta_fills", 4 * completed),
                         ("uta_matches", 2 * completed), ("uta_risk_decisions", 8 * completed),
                         ("ledger_events", 6 + 5 * completed)):
        check(len(rows[table]) == count, "count_" + table)
    check(sum(r["status"] == "CANCELLED" and Fraction(r["filled_quantity"]) != 0
              for r in rows["uta_orders"]) == completed, "partial_cancellation_count")
    inbox = rows["uta_command_inbox"]
    check(all(r["state"] == "SUCCEEDED" for r in inbox), "non_succeeded_inbox")
    check(sum(r["account_id"] is not None for r in inbox) == 6 * completed, "account_command_count")
    check(all(r["attempts"] == 0 and r["last_error"] is None for r in inbox), "internal_retry_observed")
    account_commands = [r for r in inbox if r["account_id"] is not None]
    command_by_id = {r["command_id"]: r for r in account_commands}
    check(len(command_by_id) == len(account_commands), "duplicate_account_command_identity")
    expected_command_owners = {"open-buy": ACCOUNTS[0], "open-sell": ACCOUNTS[1],
        "cancel-partial": ACCOUNTS[0], "close-sell": ACCOUNTS[0], "close-buy": ACCOUNTS[1], "repay": ACCOUNTS[2]}
    command_rounds = Counter()
    command_jobs = set()
    for row in account_commands:
        match = _COMMAND.fullmatch(row["command_id"])
        if not match or not 1 <= int(match[1]) <= completed or row["account_id"] != expected_command_owners[match[2]]:
            check(False, "original_command_identity")
        else:
            command_rounds[(int(match[1]), match[2])] += 1
            command_jobs.add(row["command_id"].split(":")[1])
    check(all(command_rounds[(r, name)] == 1 for r in range(1, completed + 1)
              for name in expected_command_owners), "original_command_round_coverage")
    check(len(command_jobs) == (1 if completed else 0), "single_original_job_identity")
    decisions = {r["decision_id"]: r for r in rows["uta_risk_decisions"]}
    check(len(decisions) == len(rows["uta_risk_decisions"]), "duplicate_decision_identity")
    check(Counter(r["kind"] for r in decisions.values()) ==
          Counter({"ORDER_ACCEPTED": 4 * completed, "FILL_CONFIRMED": 4 * completed}), "decision_kind_counts")
    for table, link, kind, business in (("uta_orders", "admission_decision_id", "ORDER_ACCEPTED", "order_id"),
                                      ("uta_fills", "execution_decision_id", "FILL_CONFIRMED", "fill_id")):
        for row in rows[table]:
            decision = decisions.get(row[link])
            check(decision is not None and decision["kind"] == kind
                  and decision["account_id"] == row["account_id"] and decision["business_id"] == row[business],
                  "decision_business_link")
    archives = {}
    for table, identity, content, prefix in (("uta_market_history", "snapshot_id", "payload", "market:"),
            ("uta_code_artifacts", "artifact_id", "manifest", "artifact:"),
            ("uta_risk_policies", "policy_id", "payload", "policy:")):
        archives[table] = {r[identity] for r in rows[table]}
        check(len(archives[table]) == len(rows[table]), "duplicate_archive_identity")
        for row in rows[table]:
            try:
                _strict_object(row[content])
                digest = sha256(row[content].encode()).hexdigest()
                check(row[identity] == prefix + digest and
                      (table != "uta_market_history" or row["content_digest"] == digest), "archive_content_id")
            except (ValueError, TypeError, RecursionError):
                check(False, "archive_canonical_content")
    for decision in decisions.values():
        check(decision["market_snapshot_id"] in archives["uta_market_history"]
              and decision["artifact_id"] in archives["uta_code_artifacts"]
              and decision["policy_id"] in archives["uta_risk_policies"], "decision_archive_reference")
    capability = rows["uta_audit_capability"]
    check(len(capability) == 1 and capability[0]["format"] == 1
          and all(capability[0][k] == 0 for k in ("legacy_event_watermark", "legacy_order_count", "legacy_fill_count")),
          "required_audit_capability")
    orders = {(r["account_id"], r["order_id"]): r for r in rows["uta_orders"]}
    fills = {(r["account_id"], r["fill_id"]): r for r in rows["uta_fills"]}
    check(len(orders) == len(rows["uta_orders"]) and len(fills) == len(rows["uta_fills"]), "duplicate_order_fill_identity")
    order_steps = {"open-buy": (ACCOUNTS[0], Fraction(2, 100), "CANCELLED", 0),
                   "open-sell": (ACCOUNTS[1], Fraction(-1, 100), "FILLED", 0),
                   "close-sell": (ACCOUNTS[0], Fraction(-1, 100), "FILLED", 1),
                   "close-buy": (ACCOUNTS[1], Fraction(1, 100), "FILLED", 1)}
    for row in orders.values():
        match = _COMMAND.fullmatch(row["order_id"])
        spec = order_steps.get(match[2]) if match else None
        check(spec is not None and 1 <= int(match[1]) <= completed and row["account_id"] == spec[0]
              and Fraction(row["quantity"]) == spec[1] and row["status"] == spec[2]
              and row["reduce_only"] == spec[3] and row["symbol"] == "BTC-PERP"
              and Fraction(row["limit_price"]) == 100
              and abs(Fraction(row["filled_quantity"])) == Fraction(1, 100)
              and _minor(row["charged_fee"]) == 40_000 and Fraction(row["fee_notional"]) == 1,
              "per_order_golden")
    for row in fills.values():
        check(abs(Fraction(row["quantity"])) == Fraction(1, 100) and Fraction(row["price"]) == 100
              and _minor(row["fee"]) == 40_000 and Fraction(row["realized_pnl"]) == 0
              and (row["account_id"], row["order_id"]) in orders, "per_fill_golden")
    paired_fills, pair_rounds, trade_ids = Counter(), Counter(), set()
    for row in rows["uta_matches"]:
        buy, sell = _COMMAND.fullmatch(row["buy_order_id"]), _COMMAND.fullmatch(row["sell_order_id"])
        phase = "open" if buy and buy[2] == "open-buy" else "close"
        check(buy is not None and sell is not None and buy[1] == sell[1]
              and row["buy_order_id"].rsplit(":", 1)[0] == row["sell_order_id"].rsplit(":", 1)[0]
              and ((buy[2], sell[2], row["buy_account_id"], row["sell_account_id"]) in
                   (("open-buy", "open-sell", ACCOUNTS[0], ACCOUNTS[1]),
                    ("close-buy", "close-sell", ACCOUNTS[1], ACCOUNTS[0])))
              and Fraction(row["quantity"]) == Fraction(1, 100) and Fraction(row["price"]) == 100
              and row["symbol"] == "BTC-PERP", "per_round_match_pair")
        if buy:
            pair_rounds[(int(buy[1]), phase)] += 1
        check(row["trade_id"] not in trade_ids, "duplicate_trade_id")
        trade_ids.add(row["trade_id"])
        for side in ("buy", "sell"):
            key = (row[side + "_account_id"], row[side + "_fill_id"])
            paired_fills[key] += 1
            fill = fills.get(key)
            check(fill is not None and fill["order_id"] == row[side + "_order_id"], "match_fill_join")
    check(set(paired_fills) == set(fills) and all(v == 1 for v in paired_fills.values()), "all_fill_sides_paired")
    check(all(pair_rounds[(r, phase)] == 1 for r in range(1, completed + 1) for phase in ("open", "close")),
          "paired_round_coverage")
    credit = rows["credit_commands"]
    pools, loans, repayments = ([r for r in credit if r["kind"] == kind]
                               for kind in ("pool_funded", "borrowed", "repaid"))
    check(len(credit) == 2 + completed and len(pools) == len(loans) == 1 and len(repayments) == completed,
          "credit_history_counts")
    if len(pools) == 1:
        row = pools[0]
        check((row["scope"], row["command_id"], row["asset"]) == ("pool", "synthetic-initial-pool", "BTC")
              and _minor(row["amount"]) == SCALE and bool(row["source_reference"]), "original_pool_funding")
    if len(loans) == 1:
        row = loans[0]
        check((row["scope"], row["command_id"], row["asset"]) ==
              ("account:" + ACCOUNTS[2], "synthetic-initial-loan", "BTC")
              and _minor(row["amount"]) == 2 * planned and row["source_reference"] is None, "original_loan_budget")
    for row in repayments:
        original = command_by_id.get(row["command_id"])
        check(row["scope"] == "account:" + ACCOUNTS[2] and row["asset"] == "BTC"
              and _minor(row["amount"]) == 2 and row["source_reference"] is None
              and original is not None and original["account_id"] == ACCOUNTS[2]
              and original["kind"] == "REPAY", "two_satoshi_repayment")
        try:
            result = _strict_object(row["result"])
            command = _COMMAND.fullmatch(row["command_id"])
            check(command is not None and command[2] == "repay"
                  and result["account_id"] == ACCOUNTS[2] and result["command_id"] == row["command_id"]
                  and result["asset"] == "BTC" and _minor(result["amount"]) == 2
                  and _minor(result["principal_repaid"]) == 2 and _minor(result["interest_repaid"]) == 0
                  and _minor(result["principal"]) == 2 * (planned - int(command[1]))
                  and _minor(result["interest"]) == 0
                  and result["journal_event_id"] == row["journal_event_id"], "repayment_principal_receipt")
            check(original is not None and original["result"] == row["result"], "repayment_inbox_credit_receipt")
        except (ValueError, KeyError, TypeError, RecursionError):
            check(False, "repayment_principal_receipt")
    event_ids = {r["event_id"] for r in rows["ledger_events"]}
    check(all(r["journal_event_id"] in event_ids for r in credit), "credit_journal_link")
    totals, projections, per_event = defaultdict(int), defaultdict(int), defaultdict(list)
    for row in rows["ledger_postings"]:
        units = _integer(row["units"])
        totals[row["asset"]] += units
        projections[(row["account"], row["asset"])] += units
        per_event[row["sequence"]].append((row["ordinal"], row["account"], row["asset"], units))
    check(not any(totals.values()) and dict(projections) == balances, "journal_conservation_projection")
    previous = "0" * 64
    for expected, row in enumerate(sorted(rows["ledger_events"], key=lambda r: r["sequence"]), 1):
        postings = sorted(per_event.pop(row["sequence"], []))
        triples = [(p[1], p[2], p[3]) for p in postings]
        event_totals = defaultdict(int)
        for _, _, asset, units in postings:
            event_totals[asset] += units
        fingerprint = _digest(triples)
        check(row["sequence"] == expected and row["sealed"] == 1 and row["previous_hash"] == previous
              and [p[0] for p in postings] == list(range(len(postings))) and len(postings) >= 2
              and triples == sorted(triples) and all(p[3] != 0 for p in postings) and not any(event_totals.values())
              and row["fingerprint"] == fingerprint
              and row["event_hash"] == _digest([expected, row["event_id"], previous, fingerprint]), "journal_hash_chain")
        previous = row["event_hash"]
    check(not per_event, "orphan_postings")
    return {"compared": True, "passed": not errors, "errors": sorted(set(errors)),
            "completed_rounds": completed, "remaining_principal_satoshi": remaining}


def read_financial(connection, planned, completed, *, compare_golden=False):
    """Read one already-open SQLite snapshot; never connect, commit, or close.

    The supplied connection must use sqlite3.Row and have an active query_only
    transaction. Missing fields raise, while invalid final business state is
    returned as golden.passed=false. A caller must never compare an ACTIVE round
    against a previous checkpoint count from another logical point.
    """
    if type(planned) is not int or type(completed) is not int or not 0 <= completed <= planned:
        raise ValueError("invalid immutable planned/completed budget")
    if not connection.in_transaction or connection.execute("PRAGMA query_only").fetchone()[0] != 1:
        raise ValueError("explicit query-only read transaction required")
    tables = _rows(connection)
    business_digest = _business_digest(tables)
    events = sorted(tables["ledger_events"], key=lambda r: r["sequence"])
    uta_events = sorted(tables["uta_events"], key=lambda r: r["sequence"])
    counts = {table: len(rows) for table, rows in tables.items()}
    counts["terminal_account_commands"] = sum(r["account_id"] is not None and r["state"] == "SUCCEEDED"
                                              for r in tables["uta_command_inbox"])
    counts["control_commands"] = sum(r["account_id"] is None for r in tables["uta_command_inbox"])
    counts["partial_cancelled_orders"] = sum(r["status"] == "CANCELLED" and Fraction(r["filled_quantity"]) != 0
                                             for r in tables["uta_orders"])
    commands, retries = [], []
    for row in sorted(tables["uta_command_inbox"], key=lambda r: r["sequence"]):
        if type(row["attempts"]) is not int or row["attempts"] < 0:
            raise ValueError("invalid durable execution attempt count")
        entry = {"sequence": row["sequence"], "command_id": _command(row["command_id"]),
            "account": None if row["account_id"] is None else _label(row["account_id"], set(ACCOUNTS)),
            "kind": _label(row["kind"], _KINDS), "state": _label(row["state"], {"PENDING", "SUCCEEDED", "REJECTED", "QUARANTINED"}),
            "attempts": row["attempts"], "last_error_present": row["last_error"] is not None,
            "last_error_code": "technical_execution_failure" if row["last_error"] == "technical_execution_failure" else
                ("unknown_redacted" if row["last_error"] is not None else None),
            "quarantined": row["state"] == "QUARANTINED", "control_lane": row["account_id"] is None,
            "payload_sha256": sha256(row["payload"].encode()).hexdigest(), "error_present": row["error"] is not None}
        commands.append(entry)
        if row["attempts"] > 0 or row["last_error"] is not None:
            retries.append({"command_id": entry["command_id"], "attempts": row["attempts"],
                            "cause": "unknown", "last_error_present": entry["last_error_present"]})
    golden = _golden(tables, planned, completed) if compare_golden else {
        "compared": False, "passed": False, "errors": [], "reason": "inflight_or_logical_point_unproven"}
    if compare_golden:
        for statement, code, expected in (
                ("PRAGMA quick_check", "sqlite_quick_check_failed", "ok"),
                ("PRAGMA foreign_key_check", "sqlite_foreign_key_check_failed", None)):
            try:
                finding = connection.execute(statement).fetchone()
                valid = finding is None if expected is None else finding is not None and finding[0] == expected
                if not valid:
                    golden["errors"].append(code)
            except sqlite3.Error:
                golden["errors"].append(code + "_unavailable")
        golden["errors"] = sorted(set(golden["errors"]))
        golden["passed"] = not golden["errors"]
    return {"synthetic": True, "redacted": True, "snapshot_scope": "one_query_only_sqlite_transaction",
        "watermark": {"format": 2, "sha256": business_digest,
            "ledger_sequence": events[-1]["sequence"] if events else 0,
            "ledger_hash": events[-1]["event_hash"] if events else "0" * 64,
            "business_event_sequence": uta_events[-1]["sequence"] if uta_events else 0},
        "counts": counts, "command_inbox": commands, "retry_alerts": retries,
        "residuals": {"live_orders": sum(r["status"] in ("OPEN", "PARTIALLY_FILLED") for r in tables["uta_orders"]),
            "positions": [{"account": _label(r["account_id"], set(ACCOUNTS)),
                "symbol": _label(r["symbol"], {"BTC-PERP"}), "quantity_satoshi": _minor(r["quantity"]),
                "cost_basis_minor": _minor(r["cost_basis"])} for r in tables["uta_positions"]]},
        "gross_debt": [{"account": _label(r["account_id"], set(ACCOUNTS)),
            "asset": _label(r["asset"], {"USD", "BTC"}), "principal_minor": _minor(r["principal"]),
            "interest_minor": _minor(r["interest"])} for r in tables["uta_liabilities"]],
        "balances": [{"owner": _label(r["account"], _OWNERS), "asset": _label(r["asset"], {"USD", "BTC"}),
            "minor_units": _integer(r["units"])} for r in tables["ledger_balances"]],
        "golden": golden}
