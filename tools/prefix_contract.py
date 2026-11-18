"""Independent synthetic completed-prefix contract/reference verifier.

No UTA, SQLite, filesystem reads, subprocesses, network or cryptographic calls.
This validates a synthetic projection, never authenticates a real snapshot or
issues an original strict-cold/stability/production qualification.
"""
from collections import Counter, defaultdict
import json
import re

SOURCE = "909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0"
MAX_INT = (1 << 63) - 1
SCALE = 100000000
ACCOUNTS = ("managed-soak-alice", "managed-soak-bob", "managed-soak-credit")
STEPS = ("open-buy", "open-sell", "cancel-partial", "close-sell", "close-buy", "repay")
QUALIFICATION = {name: False for name in ("complete_original_job", "continuous_6h_stability_passed",
    "continuous_24h_stability_passed", "financial_6h_passed", "capacity_10000_per_s_passed",
    "full_risk_engine_reexecution_passed", "whole_business_event_reexecution_passed", "production_approved")}
CHECKS = ("source_manifest_verified", "quiescence_verified", "coherent_private_snapshot_verified",
    "original_prefix_boundary_verified", "all_commands_and_controls_resolved", "segmented_logs_verified",
    "financial_journal_and_positions_reconciled", "independent_reopen_same_watermark")
LIMITATIONS_V1 = {"ORIGINAL_JOB_INCOMPLETE", "NOT_FULL_DURATION_ACCEPTANCE", "NO_FULL_RISK_REEXECUTION",
    "NO_WHOLE_BUSINESS_EVENT_REEXECUTION", "NO_PRODUCTION_APPROVAL", "SOURCE_OR_BOUNDARY_UNPROVEN",
    "UNRESOLVED_OBLIGATION", "PRIVATE_SNAPSHOT_NOT_CREATED", "AUDIT_NOT_EXECUTED", "METHOD_NOT_INDEPENDENTLY_APPROVED"}
RECORD_FIELDS = {
    "rounds": {"sequence", "state"},
    "commands": {"command_id", "round", "step", "account", "state", "result_known"},
    "controls": {"control_id", "round", "kind", "origin", "state", "result_known", "asset_impact"},
    "orders": {"order_id", "account", "round", "step", "quantity_satoshi", "filled_satoshi", "status", "reduce_only"},
    "fills": {"fill_id", "order_id", "account", "quantity_satoshi", "price_usd_minor_per_btc", "fee_usd_minor", "realized_pnl_usd_minor"},
    "matches": {"trade_id", "round", "phase", "buy_fill_id", "sell_fill_id", "quantity_satoshi", "price_usd_minor_per_btc"},
    "decisions": {"decision_id", "kind", "business_id", "account", "round"},
    "credit_events": {"command_id", "kind", "amount_satoshi", "journal_event_id"},
    "ledger_events": {"sequence", "event_id", "kind", "business_id"},
    "postings": {"event_id", "ordinal", "owner", "asset", "units"},
    "balances": {"owner", "asset", "units"},
    "logs": {"sequence", "previous_sequence", "kind", "round", "status", "business_id"},
}


def integer(value, minimum=0, maximum=MAX_INT):
    return type(value) is int and minimum <= value <= maximum


def strict_equal(left, right):
    pending = [(left, right)]
    while pending:
        a, b = pending.pop()
        if type(a) is not type(b):
            return False
        if isinstance(a, dict):
            if set(a) != set(b):
                return False
            pending.extend((a[k], b[k]) for k in a)
        elif isinstance(a, list):
            if len(a) != len(b):
                return False
            pending.extend(zip(a, b))
        elif type(a) not in (str, int, bool, type(None)) or a != b:
            return False
    return True


def tree_valid(value):
    stack, nodes = [(value, 0)], 0
    while stack:
        item, depth = stack.pop();nodes += 1
        if depth > 32 or nodes > 1000000:
            return False
        if isinstance(item, dict):
            if not all(type(k) is str for k in item):
                return False
            stack.extend((v, depth + 1) for v in item.values())
        elif isinstance(item, list):
            stack.extend((v, depth + 1) for v in item)
        elif type(item) is int:
            if not -MAX_INT <= item <= MAX_INT:
                return False
        elif type(item) not in (str, bool, type(None)):
            return False
    return True


def exact_object(value, fields):
    return isinstance(value, dict) and set(value) == set(fields)


def identifier(value):
    return type(value) is str and re.fullmatch(r"[A-Za-z0-9:_-]{1,160}", value) is not None


def canonical_birth(value):
    return (type(value) is str and re.fullmatch(r"[1-9][0-9]{0,18}", value) is not None
            and int(value) <= MAX_INT)


def command_id(job, round_number, step):
    return f"ms:{job}:r{round_number:09d}:{step}"


def expected_budget(planned, completed):
    """Hand-derived independent gross integer budget; no production oracle."""
    if not integer(planned, 2, 21600) or not integer(completed, 1, planned - 1):
        raise ValueError("invalid_prefix_budget")
    remaining = 2 * (planned - completed)
    balances = {
        ("customer:" + ACCOUNTS[0], "USD"): 1000000 * SCALE - 80000 * completed,
        ("customer:" + ACCOUNTS[1], "USD"): 1000000 * SCALE - 80000 * completed,
        ("customer:" + ACCOUNTS[2], "USD"): 1000000 * SCALE,
        ("system:fees", "USD"): 160000 * completed,
        ("system:custody", "USD"): -3000000 * SCALE,
        ("customer:" + ACCOUNTS[2], "BTC"): SCALE + remaining,
        ("system:credit-pool", "BTC"): SCALE - remaining,
        ("liability:principal:" + ACCOUNTS[2], "BTC"): -remaining,
        ("system:credit-principal-receivable", "BTC"): remaining,
        ("system:custody", "BTC"): -SCALE,
        ("system:credit-capital", "BTC"): -SCALE,
    }
    return {"remaining_principal_satoshi": remaining, "balances": balances,
            "counts": {"rounds": completed, "commands": 6 * completed, "controls": 2 * completed, "orders": 4 * completed,
                       "fills": 4 * completed, "matches": 2 * completed, "decisions": 8 * completed,
                       "credit_events": 2 + completed, "ledger_events": 6 + 5 * completed}}


def result(errors):
    return {"schema": "uta.synthetic_prefix_contract_result.v1", "scope": "synthetic_json_contract_only",
            "contract_consistent": not errors, "errors": sorted(set(errors)),
            "qualification": dict(QUALIFICATION), "forensic_audit_performed": False,
            "real_quiescence_verified": False, "cryptographic_log_chain_verified": False,
            "raw_source_or_manifest_authenticated": False, "sql_or_original_data_read": False}


def validate(value):
    try:
        return _validate(value)
    except (ValueError, TypeError, KeyError, RecursionError, OverflowError):
        return result(["malformed_or_unsupported_projection"])


def _validate(value):
    if not isinstance(value, dict) or not tree_valid(value):
        return result(["invalid_json_types_or_resource_bound"])
    top = {"schema", "scope", "profile", "original", "source", "quiescence", "boundary", "unknown_actions",
           "positions", "remaining_principal_satoshi", "receipt", *RECORD_FIELDS}
    if not exact_object(value, top):
        return result(["input_full_schema_required"])
    errors = []
    def require(condition, code):
        if not condition:
            errors.append(code)
    require(value["schema"] == "uta.synthetic_prefix_contract_input.v1"
            and value["scope"] == "synthetic_json_contract_only"
            and value["profile"] == "909-three-account-usd-btc8-linear-synthetic", "unsupported_version_or_profile")
    original = value["original"]
    if not exact_object(original, {"job_id", "source_commit", "status", "planned_rounds", "completed_prefix_rounds"}):
        return result(["original_full_schema_required"])
    n, k, job = original["planned_rounds"], original["completed_prefix_rounds"], original["job_id"]
    if not integer(n, 2, 21600) or not integer(k, 1, n - 1) or not identifier(job):
        return result(["strict_prefix_integer_boundary_required"])
    require(original["status"] == "paused" and original["source_commit"] == SOURCE, "original_state_or_source_invalid")
    budget = expected_budget(n, k)
    source = value["source"]
    require(exact_object(source, {"synthetic_only", "model_version", "asset_scales", "manifest_claimed_verified"})
            and source.get("synthetic_only") is True and source.get("model_version") == 1
            and type(source.get("model_version")) is int
            and strict_equal(source.get("asset_scales"), {"USD": 8, "BTC": 8})
            and source.get("manifest_claimed_verified") is True, "source_projection_contract_invalid")
    quiet = value["quiescence"]
    require(exact_object(quiet, {"synthetic_declaration_only", "writers"})
            and quiet.get("synthetic_declaration_only") is True, "quiescence_declaration_schema_invalid")
    writers = quiet.get("writers") if isinstance(quiet, dict) else None
    pairs = []
    if not isinstance(writers, list) or not writers:
        require(False, "quiescence_writers_missing")
    else:
        for row in writers:
            if not (exact_object(row, {"pid", "birth", "known_stopped"})
                    and integer(row.get("pid"), 1, (1 << 31) - 1)
                    and canonical_birth(row.get("birth")) and row.get("known_stopped") is True):
                require(False, "quiescence_writer_identity_invalid");continue
            pairs.append((row["pid"], row["birth"]))
        require(len(pairs) == len(set(pairs)), "duplicate_writer_lifetime")
    boundary = value["boundary"]
    require(exact_object(boundary, {"controller_sessions", "unresolved_steps", "unresolved_faults", "active_rounds", "ended_status"})
            and strict_equal(boundary, {"controller_sessions": 1, "unresolved_steps": 0,
                "unresolved_faults": 0, "active_rounds": [], "ended_status": "paused"}), "boundary_not_quiescent_complete_prefix")
    require(value["unknown_actions"] == [] and type(value["unknown_actions"]) is list, "unknown_action_present")
    require(value["positions"] == [] and type(value["positions"]) is list, "residual_position_present")
    require(integer(value["remaining_principal_satoshi"]) and value["remaining_principal_satoshi"] == budget["remaining_principal_satoshi"], "gross_debt_mismatch")
    for name, fields in RECORD_FIELDS.items():
        rows = value[name]
        if not isinstance(rows, list) or not all(exact_object(row, fields) for row in rows):
            return result(errors + ["record_full_schema_required_" + name])
        if name in budget["counts"]:
            require(len(rows) == budget["counts"][name], "count_mismatch_" + name)
    require(strict_equal(value["rounds"], [{"sequence": r, "state": "DONE"} for r in range(1, k + 1)]), "round_gap_duplicate_or_unfinished")
    owner_for = {"open-buy": ACCOUNTS[0], "open-sell": ACCOUNTS[1], "cancel-partial": ACCOUNTS[0],
                 "close-sell": ACCOUNTS[0], "close-buy": ACCOUNTS[1], "repay": ACCOUNTS[2]}
    expected_commands = {command_id(job,r,s): (r,s,owner_for[s]) for r in range(1,k+1) for s in STEPS}
    commands = {}
    for row in value["commands"]:
        cid = row["command_id"]
        if not identifier(cid) or cid in commands:
            require(False,"duplicate_or_invalid_command_id");continue
        commands[cid] = row
        expected = expected_commands.get(cid)
        require(expected is not None and integer(row["round"],1,k)
                and strict_equal([row["round"],row["step"],row["account"]],list(expected))
                and row["state"] == "SUCCEEDED" and row["result_known"] is True, "unresolved_or_foreign_command")
    require(set(commands) == set(expected_commands), "command_identity_gap_or_extra")
    expected_controls = {f"ctl:{job}:r{r:09d}:{suffix}": (r, kind, origin)
        for r in range(1,k+1) for suffix,kind,origin in (("market","PUBLISH_MARKET","ROUND_FEED"),
                                                       ("activate","SET_HALT","ROUND_ACTIVATION"))}
    control_ids=set()
    for row in value["controls"]:
        cid=row["control_id"]
        if not identifier(cid) or cid in control_ids:
            require(False,"duplicate_or_invalid_control_identity");continue
        control_ids.add(cid);expected=expected_controls.get(cid)
        require(expected is not None and strict_equal([row["round"],row["kind"],row["origin"]],list(expected))
                and row["state"]=="SUCCEEDED" and row["result_known"] is True and row["asset_impact"] is False,
                "control_origin_effect_or_outcome_unproven")
    require(control_ids==set(expected_controls),"control_identity_gap_or_extra")
    order_specs = {"open-buy": (ACCOUNTS[0],2000000,1000000,"CANCELLED",False),
                   "open-sell": (ACCOUNTS[1],-1000000,-1000000,"FILLED",False),
                   "close-sell": (ACCOUNTS[0],-1000000,-1000000,"FILLED",True),
                   "close-buy": (ACCOUNTS[1],1000000,1000000,"FILLED",True)}
    orders, fills, decisions = {}, {}, {}
    for row in value["orders"]:
        oid = row["order_id"]
        if not identifier(oid) or oid in orders:
            require(False,"duplicate_or_invalid_order_id");continue
        orders[oid] = row;spec = order_specs.get(row["step"])
        require(spec is not None and integer(row["round"],1,k)
                and oid == command_id(job,row["round"],row["step"])
                and strict_equal([row["account"],row["quantity_satoshi"],row["filled_satoshi"],row["status"],row["reduce_only"]],list(spec)), "order_shape_or_direction_mismatch")
    expected_order_ids = {command_id(job,r,s) for r in range(1,k+1) for s in order_specs}
    require(set(orders) == expected_order_ids, "order_identity_gap_or_extra")
    for row in value["fills"]:
        fid, oid = row["fill_id"], row["order_id"]
        if not identifier(fid) or fid in fills:
            require(False,"duplicate_or_invalid_fill_id");continue
        fills[fid] = row;order = orders.get(oid) if identifier(oid) else None
        require(order is not None and fid == "f:"+oid
                and strict_equal([row["account"],row["quantity_satoshi"],row["price_usd_minor_per_btc"],row["fee_usd_minor"],row["realized_pnl_usd_minor"]],
                    [order["account"],order["filled_satoshi"],100*SCALE,40000,0]), "fill_order_price_fee_mismatch")
    require(set(fills) == {"f:"+oid for oid in orders}, "fill_identity_gap_or_extra")
    match_ids, paired = set(), Counter()
    for row in value["matches"]:
        tid = row["trade_id"];r,phase = row["round"],row["phase"]
        if not identifier(tid) or tid in match_ids:
            require(False,"duplicate_or_invalid_trade_id");continue
        match_ids.add(tid)
        valid = integer(r,1,k) and phase in ("open","close")
        buy_step,sell_step = ("open-buy","open-sell") if phase == "open" else ("close-buy","close-sell")
        require(valid and tid == f"m:{job}:{r}:{phase}"
                and strict_equal([row["buy_fill_id"],row["sell_fill_id"],row["quantity_satoshi"],row["price_usd_minor_per_btc"]],
                    ["f:"+command_id(job,r,buy_step),"f:"+command_id(job,r,sell_step),1000000,100*SCALE]), "match_two_sided_join_mismatch")
        for side in ("buy_fill_id","sell_fill_id"):
            if identifier(row[side]):paired[row[side]] += 1
            else:require(False,"invalid_match_fill_identity")
    require(set(paired)==set(fills) and all(c==1 for c in paired.values()), "fill_sides_not_uniquely_paired")
    for row in value["decisions"]:
        did,bid = row["decision_id"],row["business_id"]
        if not identifier(did) or did in decisions:
            require(False,"duplicate_or_invalid_decision_id");continue
        decisions[did]=row
        target = orders.get(bid) if identifier(bid) and row["kind"]=="ORDER_ACCEPTED" else fills.get(bid) if identifier(bid) else None
        target_order=target if row["kind"]=="ORDER_ACCEPTED" else orders.get(target["order_id"]) if target is not None else None
        require(target is not None and target_order is not None and row["kind"] in ("ORDER_ACCEPTED","FILL_CONFIRMED")
                and row["account"]==target["account"] and integer(row["round"],1,k)
                and row["round"]==target_order["round"], "decision_business_join_mismatch")
    require(Counter((r["kind"],r["business_id"]) for r in decisions.values()) == Counter(
        [("ORDER_ACCEPTED",oid) for oid in orders]+[("FILL_CONFIRMED",fid) for fid in fills]), "decision_coverage_gap_or_extra")
    _journal(value, budget, errors)
    _logs(value["logs"], job, k, errors)
    _receipt(value["receipt"], n, k, errors)
    return result(errors)


def _journal(value, budget, errors):
    def require(condition,code):
        if not condition:errors.append(code)
    events, business, postings = {}, {}, defaultdict(list)
    for index,row in enumerate(value["ledger_events"],1):
        eid=row["event_id"]
        require(integer(row["sequence"],1) and row["sequence"]==index,"ledger_sequence_gap_or_duplicate")
        if not identifier(eid) or eid in events:
            require(False,"duplicate_or_invalid_journal_event_id");continue
        events[eid]=row
        require(identifier(row["business_id"]) and row["business_id"] not in business,"duplicate_or_invalid_journal_business_id")
        if identifier(row["business_id"]):business[row["business_id"]]=row
    for row in value["postings"]:
        if not identifier(row["event_id"]) or row["event_id"] not in events:
            require(False,"orphan_posting");continue
        require(integer(row["ordinal"]) and type(row["units"]) is int and row["units"]!=0
                and row["asset"] in ("USD","BTC") and identifier(row["owner"]),"posting_type_or_asset_invalid")
        postings[row["event_id"]].append(row)
    job=value["original"]["job_id"];n=value["original"]["planned_rounds"]
    expected_events={}
    for account,asset,amount,business_id in ((ACCOUNTS[0],"USD",1000000*SCALE,"deposit-alice-usd"),
            (ACCOUNTS[1],"USD",1000000*SCALE,"deposit-bob-usd"),
            (ACCOUNTS[2],"USD",1000000*SCALE,"deposit-credit-usd"),
            (ACCOUNTS[2],"BTC",SCALE,"deposit-credit-btc")):
        expected_events[business_id]=("DEPOSIT",[("customer:"+account,asset,amount),("system:custody",asset,-amount)])
    expected_events["initial-pool"]=("POOL_FUNDED",[("system:credit-pool","BTC",SCALE),("system:credit-capital","BTC",-SCALE)])
    expected_events["initial-loan"]=("BORROWED",[("customer:"+ACCOUNTS[2],"BTC",2*n),("system:credit-pool","BTC",-2*n),
        ("liability:principal:"+ACCOUNTS[2],"BTC",-2*n),("system:credit-principal-receivable","BTC",2*n)])
    for fill in value["fills"]:
        if identifier(fill["fill_id"]) and type(fill["account"]) is str:
            expected_events[fill["fill_id"]] = ("FILL_FEE",[("customer:"+fill["account"],"USD",-40000),("system:fees","USD",40000)])
    for r in range(1,value["original"]["completed_prefix_rounds"]+1):
        expected_events[command_id(job,r,"repay")]=("REPAID",[("customer:"+ACCOUNTS[2],"BTC",-2),("system:credit-pool","BTC",2),
            ("liability:principal:"+ACCOUNTS[2],"BTC",2),("system:credit-principal-receivable","BTC",-2)])
    require(set(business)==set(expected_events),"journal_business_coverage_gap_or_extra")
    projected=defaultdict(int)
    bootstrap={"deposit-alice-usd","deposit-bob-usd","deposit-credit-usd","deposit-credit-btc","initial-pool","initial-loan"}
    bootstrap_seen=set();round_fills=set();current_round=1
    fill_stage={"f:"+command_id(job,r,step):(r,phase)
        for r in range(1,value["original"]["completed_prefix_rounds"]+1)
        for phase,steps in (("open",("open-buy","open-sell")),("close",("close-buy","close-sell"))) for step in steps}
    repayment_rounds={command_id(job,r,"repay"):r for r in range(1,value["original"]["completed_prefix_rounds"]+1)}
    for eid,event in events.items():
        rows=postings[eid];totals=defaultdict(int)
        require(len(rows)>=2 and strict_equal([r["ordinal"] for r in rows],list(range(len(rows)))),"posting_ordinal_gap_or_duplicate")
        for row in rows:
            if type(row["units"]) is int and type(row["asset"]) is str and type(row["owner"]) is str:
                totals[row["asset"]]+=row["units"];projected[(row["owner"],row["asset"])]+=row["units"]
        require(all(v==0 for v in totals.values()),"per_event_currency_not_conserved")
        expected=expected_events.get(event["business_id"]) if identifier(event["business_id"]) else None
        primitives=all(type(r["owner"]) is str and type(r["asset"]) is str and type(r["units"]) is int for r in rows)
        require(expected is not None and event["kind"]==expected[0] and primitives
                and Counter((r["owner"],r["asset"],r["units"]) for r in rows)==Counter(expected[1]),
                "per_business_posting_shape_or_amount_mismatch")
        # This profile has zero genesis: every asset and debt is introduced by
        # an explicit bootstrap event. Existing-debt snapshots need a different
        # version, not a universal rule forbidding repayment before new credit.
        principal=-projected.get(("liability:principal:"+ACCOUNTS[2],"BTC"),0)
        receivable=projected.get(("system:credit-principal-receivable","BTC"),0)
        require(principal>=0 and receivable>=0 and principal==receivable,
                "intermediate_principal_or_receivable_invalid")
        require(projected.get(("system:credit-pool","BTC"),0)>=0
                and all(projected.get(("customer:"+account,asset),0)>=0
                        for account in ACCOUNTS for asset in ("USD","BTC")),
                "intermediate_customer_or_pool_asset_negative")
        bid=event["business_id"]
        if identifier(bid) and bid in bootstrap:
            require(current_round==1 and not round_fills,"bootstrap_after_round_business")
            bootstrap_seen.add(bid)
        elif identifier(bid) and bid in fill_stage:
            round_number,phase=fill_stage[bid]
            require(bootstrap_seen==bootstrap and round_number==current_round,"round_before_bootstrap_or_prior_round_complete")
            opens={"f:"+command_id(job,current_round,step) for step in ("open-buy","open-sell")}
            closes={"f:"+command_id(job,current_round,step) for step in ("close-buy","close-sell")}
            require((phase=="open" and not (round_fills & closes))
                    or (phase=="close" and opens<=round_fills),"close_before_open_pair_or_open_after_close")
            round_fills.add(bid)
        elif identifier(bid) and bid in repayment_rounds:
            expected_fills={"f:"+command_id(job,current_round,step) for step in ("open-buy","open-sell","close-buy","close-sell")}
            require(bootstrap_seen==bootstrap and repayment_rounds[bid]==current_round and round_fills==expected_fills,
                    "repayment_before_complete_round_or_out_of_order")
            current_round+=1;round_fills=set()
    require(bootstrap_seen==bootstrap and current_round==value["original"]["completed_prefix_rounds"]+1
            and not round_fills,"journal_causal_prefix_incomplete")
    actual={}
    for row in value["balances"]:
        key=(row["owner"],row["asset"])
        if not all(type(x) is str for x in key) or key in actual:
            require(False,"duplicate_or_invalid_gross_balance_key");continue
        actual[key]=row["units"]
        require(type(row["units"]) is int,"balance_units_not_exact_integer")
    require(actual==budget["balances"] and all(type(v) is int for v in actual.values()),"gross_owner_asset_budget_mismatch")
    require(dict(projected)==actual,"complete_journal_projection_mismatch")
    for fill in value["fills"]:
        event=business.get(fill["fill_id"]) if identifier(fill["fill_id"]) else None
        require(event is not None and event["kind"]=="FILL_FEE","fill_journal_link_missing")
    credit_ids=set()
    for row in value["credit_events"]:
        cid=row["command_id"];eid=row["journal_event_id"]
        if not identifier(cid) or cid in credit_ids:
            require(False,"duplicate_or_invalid_credit_command");continue
        credit_ids.add(cid);event=events.get(eid) if identifier(eid) else None
        require(event is not None and event["business_id"]==cid and event["kind"]==row["kind"],"credit_journal_link_missing")
        require(integer(row["amount_satoshi"],1),"credit_amount_not_integer")
        if row["kind"]=="POOL_FUNDED":require(cid=="initial-pool" and row["amount_satoshi"]==SCALE,"pool_budget_mismatch")
        elif row["kind"]=="BORROWED":require(cid=="initial-loan" and row["amount_satoshi"]==2*value["original"]["planned_rounds"],"original_borrow_budget_mismatch")
        elif row["kind"]=="REPAID":require(cid in repayment_rounds and row["amount_satoshi"]==2,"repayment_budget_mismatch")
        else:require(False,"unknown_credit_kind")
    require(Counter(r["kind"] for r in value["credit_events"])==Counter({"POOL_FUNDED":1,"BORROWED":1,"REPAID":value["original"]["completed_prefix_rounds"]}),"credit_kind_coverage_mismatch")


def _logs(rows, job, k, errors):
    expected = [("INITIALIZED",None,None,None),("CONTROLLER_STARTED",None,None,None)]
    for r in range(1,k+1):
        expected.extend([("ROUND_STARTED",r,None,None),
            ("CONTROL_MARKET_TERMINAL",r,None,f"ctl:{job}:r{r:09d}:market"),
            ("CONTROL_ACTIVATION_TERMINAL",r,None,f"ctl:{job}:r{r:09d}:activate"),("ROUND_DONE",r,None,None)])
    expected += [("CONTROLLER_ENDED",None,"paused",None)]
    if not strict_equal(rows,[{"sequence":i,"previous_sequence":i-1,"kind":kind,"round":r,"status":state,"business_id":bid}
                              for i,(kind,r,state,bid) in enumerate(expected,1)]):
        errors.append("synthetic_milestone_log_gap_or_unknown_event")


def _receipt(value, n, k, errors):
    fields={"schema","mode","scope","execution_status","audit_authorization","original_source_commit","original_job_status",
        "planned_rounds","completed_prefix_rounds","reviewed_manifest_sha256","checks","qualification","limitations",
        "new_original_data_write","receipt_is_original_strict_cold"}
    if not exact_object(value,fields):errors.append("receipt_full_schema_required");return
    expected={"schema":"uta.completed_prefix_forensic_receipt.v1","mode":"completed_prefix_forensic",
        "scope":"quiescent_completed_prefix_only_original_job_incomplete","execution_status":"PREFIX_VERIFIED",
        "audit_authorization":"GRANTED","original_source_commit":SOURCE,"original_job_status":"paused",
        "planned_rounds":n,"completed_prefix_rounds":k,"checks":{x:True for x in CHECKS},"qualification":QUALIFICATION,
        "new_original_data_write":False,"receipt_is_original_strict_cold":False}
    if not all(strict_equal(value[x],v) for x,v in expected.items()):errors.append("receipt_scope_or_qualification_invalid")
    if not (type(value["reviewed_manifest_sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}",value["reviewed_manifest_sha256"])):
        errors.append("receipt_manifest_claim_missing")
    limitations=value["limitations"]
    if not (type(limitations) is list and all(type(x) is str for x in limitations)
            and len(limitations)==len(set(limitations)) and {"ORIGINAL_JOB_INCOMPLETE","NO_PRODUCTION_APPROVAL"}<=set(limitations)):
        errors.append("receipt_required_limitations_missing")
    elif not set(limitations)<=LIMITATIONS_V1:
        errors.append("receipt_unknown_limitation_for_version")


def parse_and_validate(raw):
    if type(raw) not in (bytes,str) or len(raw)>32*1024**2:
        return result(["input_byte_budget_or_type_invalid"])
    def pairs(items):
        obj={}
        for key,value in items:
            if key in obj:raise ValueError("duplicate_key")
            obj[key]=value
        return obj
    def invalid(_):raise ValueError("nonfinite")
    try:
        value=json.loads(raw,object_pairs_hook=pairs,parse_constant=invalid)
        return validate(value)
    except (ValueError,TypeError,UnicodeDecodeError,RecursionError,OverflowError):
        return result(["malformed_or_unsupported_json"])
