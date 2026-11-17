"""Independent synthetic REPAY content/SQL reference, no production imports."""
from collections import defaultdict
import importlib.util
import json
from pathlib import Path


def owned(name):
    spec = importlib.util.spec_from_file_location("independent_"+name, Path(__file__).with_name(name+".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CAPTURE = owned("credit_v2_capture_reference")
REF = CAPTURE.REF
need, equal = CAPTURE.need, CAPTURE.equal
FIELDS = {"source", "inbox", "intent", "expected_postings", "credit", "journal", "decision_bundle",
          "actual_financial_rows", "actual_post_interest_cash_units"}
ROW_TABLES = {"ledger_events", "ledger_postings", "ledger_balances", "uta_accounts", "uta_liabilities"}
RECEIPT = {"account_id", "account_version", "amount", "asset", "command_id", "interest", "interest_repaid",
           "journal_event_id", "principal", "principal_repaid", "total"}


def replay_rows(tables, prehead):
    """Full original rows: derive balances without trusting materialized values."""
    REF.fields(tables, ROW_TABLES, "original five financial tables")
    need(all(type(rows) is list and len(rows) <= 10000 for rows in tables.values()), "small financial row bound exceeded")
    postings, used = defaultdict(list), set()
    for leg in tables["ledger_postings"]:
        REF.fields(leg, ("sequence", "ordinal", "account", "asset", "units"), "original posting")
        REF.integer(leg["sequence"], "posting sequence", nonnegative=True)
        postings[leg["sequence"]].append(leg)
    balances, sequence, prior, before = defaultdict(int), 0, "0"*64, None
    for event in tables["ledger_events"]:
        REF.fields(event, ("sequence", "event_id", "fingerprint", "previous_hash", "event_hash", "sealed"), "original event")
        equal(event["sequence"], sequence+1, "original sequence gap")
        need(event["previous_hash"] == prior and type(event["sealed"]) is int and event["sealed"] == 1, "unsealed/broken original chain")
        actual, sums = [], defaultdict(int)
        for ordinal, leg in enumerate(postings[event["sequence"]]):
            equal(leg["ordinal"], ordinal, "original ordinal gap")
            need(leg["asset"] in {"USD", "BTC"} and type(leg["account"]) is str and leg["account"], "unsupported original posting")
            units = REF.unit_string(leg["units"], "actual posting")
            need(units != 0, "zero actual posting")
            sums[leg["asset"]] += units
            balances[(leg["account"], leg["asset"])] += units
            actual.append({key: leg[key] for key in ("ordinal", "account", "asset")} | {"units": units})
        need(actual and all(value == 0 for value in sums.values()), "original event not balanced per currency")
        fp, digest = REF.journal_hashes(event["sequence"], event["event_id"], prior, actual)
        need(fp == event["fingerprint"] and digest == event["event_hash"], "original event hash differs")
        sequence, prior = event["sequence"], digest
        used.add(sequence)
        if sequence == prehead["sequence"]:
            need(prior == prehead["event_hash"], "original prehead differs")
            before = dict(balances)
    need(before is not None and set(postings) == used, "missing prehead or orphan posting")
    materialized = {}
    for row in tables["ledger_balances"]:
        REF.fields(row, ("account", "asset", "units"), "materialized balance")
        key = (row["account"], row["asset"])
        need(key not in materialized, "duplicate materialized balance")
        materialized[key] = REF.unit_string(row["units"], "materialized units")
    equal(sorted([*k, v] for k, v in materialized.items()), sorted([*k, v] for k, v in balances.items()), "full ledger balances differ from original replay")
    return before, dict(balances), sequence


def compare_balances(state, balances, account_id, *, label):
    for asset in ("USD", "BTC"):
        need(balances.get(("customer:"+account_id, asset), 0) == state["balances"][asset], label+" cash differs")
    for key, account in {"principal_ledger_units": "liability:principal:"+account_id,
        "interest_ledger_units": "liability:interest:"+account_id, "pool_units": "system:credit-pool",
        "principal_receivable_units": "system:credit-principal-receivable", "interest_receivable_units": "system:credit-interest-receivable",
        "interest_cash_units": "system:credit-interest-cash"}.items():
        need(balances.get((account, "BTC"), 0) == state[key], label+" gross component differs: "+key)


def check_repayment(observation):
    REF.fields(observation, FIELDS, "actual repayment observation")
    source, inbox, intent = observation["source"], observation["inbox"], observation["intent"]
    account, command = source["account_id"], source["command_id"]
    REF.source_contract(source)
    need(source["kind"] == inbox["kind"] == intent["operation_kind"] == intent["inbox_kind"] == "REPAY", "repayment operation differs")
    need(inbox["state"] == intent["terminal_state"] == "SUCCEEDED" and intent["credit_kind"] == "repaid", "terminal differs")
    need(inbox["error"] is None and REF.integer(inbox["sequence"], "original FIFO sequence", nonnegative=True) > 0, "invalid original terminal/FIFO sequence")
    need(type(intent["journal_sealed"]) is int and intent["journal_sealed"] == 1, "unsealed native journal declaration")
    need(observation["decision_bundle"] is None and intent["market_dependency"] == "NONE", "repayment must not create a borrow decision")
    for key in ("market_snapshot_id", "selected_at", "operation_id", "decision_kind"):
        need(intent[key] is None, "market/borrow dependency in repayment: "+key)
    for record in (inbox, intent):
        need(record["command_id"] == command and record["account_id"] == account, "original repayment CID/account differs")
    need(intent["source_id"] == source["source_id"] and intent["payload_hash"] == source["payload_hash"], "original source binding differs")
    need(intent["authority_id"] == source["authority_id"], "original source authority differs")
    equal(REF.strict_loads(source["command_payload"], canonical_required=True),
          {"account_id": account, "asset": "BTC", "amount": intent["amount"]}, "original repayment payload differs")
    need(inbox["payload"] == source["command_payload"], "original inbox payload differs")
    pre = REF.strict_loads(intent["pre_state_payload"], canonical_required=True)
    REF.fields(pre, CAPTURE.PRE, "complete original repayment prestate")
    need(REF.digest(pre) == intent["pre_state_hash"], "repayment prestate digest differs")
    for field in ("limits", "market_snapshot_id", "risk", "quote_units", "quantity_step_units", "selected_at"):
        need(pre[field] is None, "repayment must not require borrow input: "+field)
    before = CAPTURE.retained_state(pre, account_id=account, require_limits=False)
    ledger_before, ledger_after, event_count = replay_rows(observation["actual_financial_rows"], pre["journal_head"])
    before["interest_cash_units"] = ledger_before.get(("system:credit-interest-cash", "BTC"), 0)
    compare_balances(before, ledger_before, account, label="actual original prehead")
    amount = REF.unit_string(intent["amount_units"], "repayment quantity", nonnegative=True)
    need(amount == CAPTURE.decimal_units(intent["amount"], "repayment amount"), "quantity representation differs")
    # Fixed owned policy supplies only the independent reference's input schema;
    # REPAY does not query risk, quote, borrow limits, static budget or market.
    expected = REF.transition("REPAY", REF.POLICY, before, amount, account)
    after = expected["after"]
    compare_balances(after, ledger_after, account, label="actual original post")
    need(str(after["interest_cash_units"]) == observation["actual_post_interest_cash_units"], "actual interest cash differs")
    REF.compare_journal(observation["journal"], pre["journal_head"], "REPAY", REF.POLICY, before, amount, account, command)
    need(event_count == observation["journal"]["sequence"], "original DB has later financial events")
    paid_interest = min(amount, before["interest_units"])
    paid_principal = amount-paid_interest
    for key, value in (("old_principal_units", before["principal_units"]), ("old_interest_units", before["interest_units"]),
        ("new_principal_units", after["principal_units"]), ("new_interest_units", after["interest_units"])):
        need(REF.unit_string(intent[key], key, nonnegative=True) == value, "native retained debt differs: "+key)
    for key, value in (("pre_version", before["version"]), ("post_version", after["version"]),
                       ("expected_postings", len(expected["ordered_legs"]))):
        equal(intent[key], value, "native retained integer differs: "+key)
    declared = []
    for leg in observation["expected_postings"]:
        need(leg["command_id"] == command, "declared repayment CID differs")
        declared.append({key: leg[key] for key in ("ordinal", "account", "asset")} | {"units": REF.unit_string(leg["units"], "declared units")})
    equal(declared, expected["ordered_legs"], "declared repayment obligations differ from independent legs")
    credit = observation["credit"]
    need(credit["kind"] == "repaid" and credit["command_id"] == command and credit["scope"] == "account:"+account, "original repayment receipt differs")
    receipt = REF.strict_loads(credit["result"], canonical_required=True)
    REF.fields(receipt, RECEIPT, "original repayment receipt")
    equal(REF.strict_loads(inbox["result"], canonical_required=True), receipt, "inbox/credit receipt differ")
    for key, value in (("account_id", account), ("command_id", command), ("asset", "BTC"),
        ("account_version", after["version"]), ("journal_event_id", observation["journal"]["event_id"])):
        equal(receipt[key], value, "repayment receipt identity differs: "+key)
    need(intent["journal_id"] == credit["journal_event_id"] == receipt["journal_event_id"], "original journal references differ")
    for key, value in (("amount", amount), ("principal_repaid", paid_principal), ("interest_repaid", paid_interest),
        ("principal", after["principal_units"]), ("interest", after["interest_units"]), ("total", after["principal_units"]+after["interest_units"])):
        need(CAPTURE.decimal_units(receipt[key], key) == value, "repayment receipt amount differs: "+key)
    rows = observation["actual_financial_rows"]
    accounts = [row for row in rows["uta_accounts"] if row["account_id"] == account]
    need(len(accounts) == 1, "original account missing/duplicate")
    equal(accounts[0]["version"], after["version"], "actual post account version differs")
    p = i = target_rows = 0
    for debt in rows["uta_liabilities"]:
        need(debt["asset"] == "BTC", "unsupported original loan currency")
        principal, interest = CAPTURE.decimal_units(debt["principal"], "actual principal"), CAPTURE.decimal_units(debt["interest"], "actual interest")
        p += principal
        i += interest
        if debt["account_id"] == account:
            target_rows += 1
            need(principal == after["principal_units"] and interest == after["interest_units"], "actual target debt row differs")
    need(target_rows == 1, "actual original debt row missing/duplicate")
    need(p == after["shard_principal_units"] and i == after["shard_interest_units"], "actual aggregate debt differs")
    return {"independent_repayment_financial_content_passed": True, "command_id": command,
        "principal_repaid_units": str(paid_principal), "interest_repaid_units": str(paid_interest),
        "post_cash_units": str(after["balances"]["BTC"]), "post_pool_units": str(after["pool_units"]),
        "post_interest_cash_units": str(after["interest_cash_units"]), "journal_legs": len(expected["ordered_legs"]),
        "original_events_replayed": event_count, "market_dependency": "NONE", "borrow_decisions": 0,
        "risk_or_quote_or_limits_used_for_admission": False,
        "SQL_origin_FIFO_timing_and_native_COMMIT_provenance": "PENDING_SEPARATE_ORIGINAL_SQL_AND_EXECUTION_EVIDENCE",
        "production_approved": False}


def check_file(path):
    document = REF.strict_loads(Path(path).read_text())
    REF.fields(document, ("scope", "observations"), "repayment evidence container")
    need(type(document["observations"]) is list and bool(document["observations"]), "actual repayment observations missing")
    return {"cases": [check_repayment(case) for case in document["observations"]], "production_approved": False}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("observations", type=Path)
    args = parser.parse_args()
    print(json.dumps(check_file(args.observations), indent=2, sort_keys=True))
