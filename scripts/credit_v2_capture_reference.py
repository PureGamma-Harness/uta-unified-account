"""Independent content adapter for real synthetic V2 observations.

Only the separately owned integer/Fraction oracle is imported. Passing this
checker never proves that input came from SQL, COMMIT, a native owner or restart.
Those facts require separately retained execution and reopening observations.
"""
from copy import deepcopy
from datetime import datetime
from fractions import Fraction as F
import hashlib
import importlib.util
import json
from pathlib import Path


_SPEC = importlib.util.spec_from_file_location(
    "independent_credit_math", Path(__file__).with_name("credit_v2_financial_reference.py"))
REF = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(REF)
Error = REF.ReferenceInputError

ACCOUNT = {"version", "balances", "frozen_assets", "positions", "liabilities", "orders", "halted", "liquidation_state"}
CREDIT = {"version", "cash_units", "principal_units", "interest_units", "principal_ledger_units",
          "interest_ledger_units", "shard_principal_units", "shard_interest_units", "pool_units",
          "principal_receivable_units", "interest_receivable_units"}
PRE = {"account", "credit", "limits", "market_snapshot_id", "risk", "quote_units",
       "quantity_step_units", "selected_at", "journal_head"}
POST = {"account", "credit", "limits", "risk"}
OBSERVATION = {"source", "inbox", "intent", "expected_postings", "credit", "journal", "decision_bundle"}
PAYLOAD = {"format", "kind", "operation_id", "capability_id", "capability_payload", "account_id", "command_id",
    "asset", "amount", "amount_units", "payload_hash", "source_id", "source", "descriptor_id", "static_budget",
    "allocation_id", "market_snapshot_id", "artifact_id", "policy_id", "pre_state", "post_state", "gross_components",
    "pool_funding", "journal", "receipt", "selected_at", "last_checked_at", "recorded_at", "physical_commit_at"}
RISK_MAP = {key: key for key in ("accounting_equity", "collateral_value", "risk_equity", "loan_value",
    "principal_value", "interest_value", "cash_deficit_value", "debt_value", "unrealized_pnl",
    "frozen_value", "initial_margin", "maintenance_margin", "available_margin")}
RISK_MAP["open_order_margin"] = "order_margin"
RISK = set(RISK_MAP) | {"account_version", "equity", "margin_ratio", "market_version", "observed_at", "market_id",
    "borrowable", "status", "risk_mode", "rule_id", "rule_version", "catalog_version"}


def need(condition, message):
    if not condition:
        raise Error(message)


def equal(left, right, message):
    # Canonical comparison retains the important bool-versus-int distinction.
    need(REF.canonical(left) == REF.canonical(right), message)


def document(text):
    return REF.strict_loads(text, canonical_required=True)


def identity(prefix, value):
    return prefix + hashlib.sha256(REF.canonical(value).encode()).hexdigest()


def decimal_units(text, label):
    number = REF.number(text, label) * REF.SCALE
    need(number.denominator == 1, label + " is off the 8-place grid")
    return REF.integer(number.numerator, label)


def ratio_34_half_even(value):
    """Integer-only 34-significant-digit HALF_EVEN diagnostic ratio."""
    if not value:
        return F(0)
    sign, value = (-1 if value < 0 else 1), abs(value)
    exponent = len(str(value.numerator)) - len(str(value.denominator))
    power = lambda k: F(10**k) if k >= 0 else F(1, 10**(-k))
    if value < power(exponent):
        exponent -= 1
    step = power(exponent-33)
    scaled = value / step
    integer, remainder = divmod(scaled.numerator, scaled.denominator)
    twice = remainder * 2
    if twice > scaled.denominator or twice == scaled.denominator and integer % 2:
        integer += 1
    return sign * integer * step


def retained_state(snapshot, *, account_id, require_limits=True):
    """Map all retained borrow-relevant gross inputs; never net loans/cash."""
    account, credit = snapshot["account"], snapshot["credit"]
    REF.fields(account, ACCOUNT, "retained account")
    REF.fields(credit, CREDIT, "retained credit")
    need(type(require_limits) is bool, "limit mapping policy must be explicit")
    if require_limits:
        REF.fields(snapshot["limits"], ("account_limit_units", "local_asset_limit_units"), "limits")
    else:
        need(snapshot["limits"] is None, "market-NONE repayment must retain null limits")
    REF.fields(account["balances"], ("USD", "BTC"), "gross currency cash")
    result = REF.state(version=REF.integer(account["version"], "account version", nonnegative=True))
    result["balances"] = {asset: decimal_units(value, asset + " cash")
                          for asset, value in account["balances"].items()}
    equal(account["version"], credit["version"], "account/credit versions disagree")
    need(result["balances"]["BTC"] == REF.unit_string(credit["cash_units"], "BTC cash"), "cash representations disagree")
    for key in CREDIT - {"version", "cash_units"}:
        result[key] = REF.unit_string(credit[key], key, nonnegative=not key.endswith("ledger_units"))
    need(type(account["frozen_assets"]) is dict, "frozen object required")
    result["frozen_assets"] = {asset: decimal_units(value, asset + " frozen")
                               for asset, value in account["frozen_assets"].items()}
    need(type(account["liabilities"]) is list, "ordered gross debt rows required")
    seen = set()
    for row in account["liabilities"]:
        REF.fields(row, ("asset", "principal", "interest"), "gross liability")
        need(row["asset"] in {"USD", "BTC"} and row["asset"] not in seen, "duplicate/unsupported loan currency")
        seen.add(row["asset"])
        for name in ("principal", "interest"):
            units = decimal_units(row[name], "gross " + name)
            need(units >= 0, "negative loan component")
            need(units == (result[name+"_units"] if row["asset"] == "BTC" else 0), "gross debt representation mismatch")
    need("BTC" in seen or result["principal_units"] + result["interest_units"] == 0, "missing loan row")
    need(type(account["positions"]) is dict, "positions required")
    positions = {}
    for symbol, position in account["positions"].items():
        REF.fields(position, ("quantity", "cost_basis"), "linear position")
        positions[symbol] = {"quantity_units": decimal_units(position["quantity"], "position quantity"),
                             "cost_basis_usd_units": decimal_units(position["cost_basis"], "position cost")}
    result["positions"] = positions
    need(type(account["orders"]) is list, "orders required")
    orders = []
    for row in account["orders"]:
        need(row.get("account_id") == account_id, "foreign order in retained account")
        need(type(row.get("reduce_only")) is int and row["reduce_only"] in (0, 1), "native reduce-only integer required")
        orders.append({"order_id": row["order_id"], "symbol": row["symbol"],
            "quantity_units": decimal_units(row["quantity"], "order quantity"),
            "filled_units": decimal_units(row["filled_quantity"], "order filled"),
            "limit_price": row["limit_price"], "reduce_only": bool(row["reduce_only"]), "status": row["status"]})
    result["orders"], result["halted"] = orders, account["halted"]
    liquidation = account["liquidation_state"]
    need(liquidation is None or type(liquidation) is dict and liquidation.get("account_id") == account_id,
         "unbound liquidation state")
    result["liquidation_state"] = "NORMAL" if liquidation is None else liquidation["state"]
    # Borrow never touches interest cash; the payload does not retain that
    # balance. This zero is an oracle-neutral placeholder, NOT an observation.
    result["interest_cash_units"] = 0
    return result


def retained_policy(payload, market, policy):
    """Translate published parameters, refusing unsupported product mixtures."""
    base = policy["base_policy"]
    need(base["risk_mode"] == "phase1_cross" and base["scales"] == {"USD": 8, "BTC": 8}, "unsupported mode/scale")
    need(REF.number(base["fee_rate"], "fee") == 0, "nonzero fee unsupported")
    need(base["execution_options"] == {"reserve_cache_size": 0, "market_cache_size": 0}, "cache profile differs")
    rules, catalog = base["rules"], base["catalog"]
    REF.fields(market["assets"], ("USD", "BTC"), "market currencies")
    REF.fields(market["instruments"], ("BTC-PERP",), "market instruments")
    REF.fields(catalog["products"], ("BTC-PERP",), "catalog products")
    product = catalog["products"]["BTC-PERP"]
    need(product["kind"] == "linear_perpetual" and product["settlement_asset"] == "USD"
         and product["quote_asset"] == "USD" and product["underlying"] == "BTC" and product["status"] == "active",
         "unsupported product definition")
    REF.fields(rules["borrow_limits"], ("BTC",), "loan products")
    loan = rules["borrow_limits"]["BTC"]
    margin = rules["linear_margin"][product["risk_tier"]]
    result = deepcopy(REF.POLICY)
    result.update(prices={asset: row["price"] for asset, row in market["assets"].items()},
        tiers={asset: [[tier["up_to"], tier["factor"]] for tier in row["tiers"]]
               for asset, row in rules["collaterals"].items()},
        ltv={asset: row["loan_to_value"] for asset, row in rules["collaterals"].items()},
        borrow_im=loan["initial_margin_rate"], borrow_mm=loan["maintenance_margin_rate"],
        linear_im=margin["initial_margin_rate"], linear_mm=margin["maintenance_margin_rate"],
        mark=market["instruments"]["BTC-PERP"]["mark_price"], multiplier=product["multiplier"],
        step_units=decimal_units(loan["quantity_step"], "borrow step"),
        risk_max_principal_units=decimal_units(loan["max_principal"], "risk principal cap"),
        max_total_debt=rules["max_total_debt"])
    static = document(payload["static_budget"])
    capability = document(payload["capability_payload"])
    need(payload["descriptor_id"] == identity("credit-native:", static), "static descriptor digest differs")
    need(payload["capability_id"] == identity("credit-internal-v2:", capability), "capability content digest differs")
    need(static["credit_policy_id"] == identity("credit-policy:", static["credit_policy"])
         and static["certificate_id"] == identity("credit-budget:", static["certificate"]), "static policy/certificate digest differs")
    equal(capability["static_budget"], static, "static/capability documents disagree")
    need(capability["static_budget_id"] == payload["descriptor_id"] and capability["artifact_id"] == payload["artifact_id"], "capability references differ")
    need(capability["production_approved"] is False and capability["synthetic"] is True
         and capability["stage"] == "SYNTHETIC_INTERNAL", "non-synthetic capability unsupported")
    for key in ("format", "audit_format", "source_format", "fifo_format", "native_format"):
        need(type(capability[key]) is int and capability[key] == 2, "capability format differs: " + key)
    for key in ("batch_size", "reserve_cache_size", "market_cache_size"):
        need(type(capability[key]) is int and capability[key] == 0, "unsupported execution variant: " + key)
    need(static["authority_id"] == payload["source"]["authority_id"] and static["shard"] == capability["shard"], "authority/shard differs")
    REF.fields(static["certificate"]["assets"], ("BTC",), "static credit assets")
    spec = static["certificate"]["assets"]["BTC"]
    need(type(spec["scale"]) is int and spec["scale"] == 8, "static unit scale differs")
    allocations = {}
    for row in spec["allocations"]:
        shard = row["shard"]
        need(type(shard) is int and shard >= 0 and str(shard) not in allocations, "invalid duplicate shard")
        allocations[str(shard)] = REF.unit_string(row["limit_units"], "static allocation", nonnegative=True)
    shard = static["shard"]
    need(type(shard) is int and shard >= 0, "invalid local shard")
    need(payload["allocation_id"] == identity("credit-allocation:",
         [static["certificate_id"], "BTC", shard, static["authority_id"]]), "allocation identity differs")
    result.update(global_budget_units=REF.unit_string(spec["global_limit_units"], "global budget", nonnegative=True),
                  allocations=allocations, local_shard=str(shard),
                  new_fee=static["credit_policy"]["new_borrow_fee_rate"],
                  new_interest=static["credit_policy"]["new_interest_rate"])
    for key in ("account_limit_units", "local_asset_limit_units"):
        result[key] = REF.unit_string(payload["pre_state"]["limits"][key], key, nonnegative=True)
    return result


def funding_content(payload):
    """Check original capital legs and local claims, not a self-reported pool."""
    rows = payload["pool_funding"]
    need(type(rows) is list and bool(rows), "original pool funding missing")
    total, commands, references, claims = 0, [], set(), {}
    for pair in rows:
        REF.fields(pair, ("command", "journal"), "original funding pair")
        receipt, journal = pair["command"], pair["journal"]
        need(receipt["scope"] == "pool" and receipt["kind"] == "pool_funded" and receipt["asset"] == "BTC", "funding kind differs")
        command, reference = receipt["command_id"], receipt["source_reference"]
        need(type(command) is str and command and command not in commands
             and type(reference) is str and reference and reference not in references, "duplicate/empty funding identity")
        commands.append(command)
        references.add(reference)
        amount = decimal_units(receipt["amount"], "original funded capital")
        need(amount > 0, "nonpositive funding amount")
        total += amount
        claims[(command, reference)] = amount
        event_id = identity("credit:", ["pool", command])
        need(journal["event_id"] == receipt["journal_event_id"] == event_id, "original funding event differs")
        need(type(journal["sealed"]) is int and journal["sealed"] == 1, "unsealed original funding")
        sequence = REF.integer(journal["sequence"], "funding sequence", nonnegative=True)
        need(0 < sequence <= payload["pre_state"]["journal_head"]["sequence"], "funding lies after original prestate")
        legs = [{"ordinal": 0, "account": "system:credit-capital", "asset": "BTC", "units": -amount},
                {"ordinal": 1, "account": "system:credit-pool", "asset": "BTC", "units": amount}]
        wire_legs = [{**leg, "units": str(leg["units"])} for leg in legs]
        equal(journal["postings"], wire_legs, "funding capital/pool legs differ")
        fingerprint, event_hash = REF.journal_hashes(sequence, event_id, journal["previous_hash"], legs)
        need(journal["fingerprint"] == fingerprint and journal["event_hash"] == event_hash, "funding journal hash differs")
        result = document(receipt["result"])
        for key in ("command_id", "asset", "amount", "source_reference", "journal_event_id"):
            equal(result[key], receipt[key], "original funding receipt differs: " + key)
    need(commands == sorted(commands), "funding order differs")
    before = payload["pre_state"]["credit"]
    need(total == REF.unit_string(before["pool_units"], "pool", nonnegative=True)
         + REF.unit_string(before["shard_principal_units"], "aggregate principal", nonnegative=True), "funded capital does not reconcile gross pool/principal")
    static = document(payload["static_budget"])
    local = [row for row in static["certificate"]["assets"]["BTC"]["allocations"] if row["shard"] == static["shard"]]
    need(len(local) == 1, "local opening allocation ambiguous")
    local = local[0]
    need(total == REF.unit_string(local["opening_principal_units"], "opening principal", nonnegative=True)
         + REF.unit_string(local["opening_pool_units"], "opening pool", nonnegative=True), "opening capital differs from original funding")
    for claim in local["funding_claims"]:
        need(claims.get((claim["command_id"], claim["source_reference"]))
             == REF.unit_string(claim["funded_units"], "funding claim", nonnegative=True), "static funding claim differs from original journal")
    return total


def compare_risk(observed, policy, state, *, market, base):
    REF.fields(observed, RISK, "risk decomposition")
    expected = REF.risk(policy, state)
    for wire, owned in RISK_MAP.items():
        need(REF.number(observed[wire], wire) == expected[owned], "independent risk mismatch: " + wire)
    need(REF.number(observed["equity"], "equity") == expected["risk_equity"], "equity alias differs")
    need(observed["status"] == expected["status"], "risk status differs")
    equal(observed["account_version"], state["version"], "risk account version differs")
    equal(observed["market_version"], market["version"], "risk market version differs")
    need(observed["observed_at"] == market["observed_at"], "risk observed time differs")
    need(observed["rule_id"] == base["rules"]["rule_id"], "risk rule identity differs")
    equal(observed["rule_version"], base["rules"]["version"], "rule version differs")
    equal(observed["catalog_version"], base["catalog"]["version"], "catalog version differs")
    need(observed["risk_mode"] == "phase1_cross", "risk mode differs")
    need(observed["market_id"] == "market-"+str(market["version"])+"@"+market["observed_at"], "market diagnostic identity differs")
    if not expected["maintenance_margin"]:
        need(observed["margin_ratio"] is None, "zero MM requires null ratio")
    else:
        need(REF.number(observed["margin_ratio"], "margin ratio") == ratio_34_half_even(
            expected["risk_equity"] / expected["maintenance_margin"]), "34-digit risk ratio differs")
    REF.fields(observed["borrowable"], ("BTC",), "conservative quote currencies")
    need(decimal_units(observed["borrowable"]["BTC"], "risk quote") == REF.portfolio_quote(policy, state),
         "independent conservative risk quote differs")
    return expected


def check_observation(observation):
    """Verify retained content; SQL/COMMIT provenance remains separately pending."""
    REF.fields(observation, OBSERVATION, "actual observation export")
    bundle = observation["decision_bundle"]
    REF.fields(bundle, ("format", "decision", "market", "artifact", "policy"), "decision bundle")
    need(type(bundle["format"]) is int and bundle["format"] == 2, "bundle format differs")
    row = bundle["decision"]
    payload = document(row["payload"])
    REF.fields(payload, PAYLOAD, "complete dedicated payload")
    need(payload["kind"] == "CREDIT_BORROWED" and payload["asset"] == "BTC", "unsupported operation")
    need(type(payload["format"]) is int and payload["format"] == 2 and payload["physical_commit_at"] is None,
         "physical COMMIT timestamp cannot be invented")
    need(row["decision_id"] == identity("credit-decision:", payload), "decision content identity differs")
    need(payload["operation_id"] == identity("credit-operation:", ["BORROW", payload["account_id"], payload["command_id"]]), "business operation differs")
    for key in ("operation_id", "account_id", "command_id", "asset", "amount", "payload_hash", "source_id", "market_snapshot_id",
                "artifact_id", "policy_id", "descriptor_id", "allocation_id", "selected_at", "last_checked_at", "recorded_at"):
        equal(row[key], payload[key], "decision row differs: " + key)
    equal(observation["source"], payload["source"], "actual source differs from decision")
    REF.source_contract(observation["source"])
    source = document(observation["source"]["payload"])
    equal(document(source["command_payload"]), {"account_id": payload["account_id"], "asset": "BTC", "amount": payload["amount"]}, "original command differs")
    need(datetime.fromisoformat(source["accepted_at"]) <= datetime.fromisoformat(payload["selected_at"]), "source accepted after selection")
    market_row, policy_row = bundle["market"], bundle["policy"]
    market, policy = document(market_row["payload"]), document(policy_row["payload"])
    need(market_row["snapshot_id"] == payload["market_snapshot_id"], "original SID differs")
    need(hashlib.sha256(market_row["payload"].encode()).hexdigest() == market_row["content_digest"], "market digest differs")
    need(market_row["snapshot_id"] == identity("market:", market), "market content identity differs")
    need(policy_row["policy_id"] == payload["policy_id"] == identity("credit-risk-policy:", policy), "policy digest differs")
    artifact = bundle["artifact"]
    manifest = document(artifact["manifest"])
    need(artifact["artifact_id"] == payload["artifact_id"] == identity("credit-artifact:", manifest), "artifact digest differs")
    need(manifest["signed"] is False and manifest["activation_permission"] is False, "artifact must grant no activation")
    need(manifest["source_digest"] == REF.digest(manifest["source_files"]), "artifact source map digest differs")
    need(manifest["loaded_engine_digest"] == REF.digest({"functions": manifest["loaded_credit_engine"],
         "constants": manifest["loaded_credit_constants"]}), "artifact loaded-engine digest differs")
    REF.checkpoint_contract(market["observed_at"], payload["selected_at"], payload["last_checked_at"],
        payload["market_snapshot_id"], market_row["snapshot_id"], max_age_us=policy["base_policy"]["max_price_age_us"],
        future_us=policy["max_future_skew_us"], recorded=payload["recorded_at"])
    need(datetime.fromisoformat(market_row["recorded_at"]) <= datetime.fromisoformat(payload["selected_at"]), "market published after selection")
    pre, post = payload["pre_state"], payload["post_state"]
    REF.fields(pre, PRE, "prestate")
    REF.fields(post, POST, "poststate")
    need(pre["market_snapshot_id"] == payload["market_snapshot_id"] and pre["selected_at"] == payload["selected_at"], "preselection differs")
    own_policy = retained_policy(payload, market, policy)
    funded_units = funding_content(payload)
    before = retained_state(pre, account_id=payload["account_id"])
    after = retained_state(post, account_id=payload["account_id"])
    amount = REF.unit_string(payload["amount_units"], "borrow amount", nonnegative=True)
    need(amount == decimal_units(payload["amount"], "amount"), "request amount representations differ")
    expected = REF.transition("BORROW", own_policy, before, amount, payload["account_id"])
    equal(after, expected["after"], "independent gross financial poststate differs")
    equal(post["limits"], pre["limits"], "borrow changed limits")
    for field in ("frozen_assets", "positions", "orders", "halted", "liquidation_state"):
        equal(pre["account"][field], post["account"][field], "borrow changed unrelated account field: " + field)
    equal(payload["gross_components"], expected["gross_components"], "gross assets/deficits/principal/interest differ")
    for snapshot, state in ((pre, before), (post, after)):
        compare_risk(snapshot["risk"], own_policy, state, market=market, base=policy["base_policy"])
    need(REF.unit_string(pre["quote_units"], "prequote") == REF.portfolio_quote(own_policy, before), "prequote differs")
    need(REF.unit_string(pre["quantity_step_units"], "step") == own_policy["step_units"], "step differs")
    equal(observation["journal"], payload["journal"], "actual journal differs from decision")
    REF.compare_journal(observation["journal"], pre["journal_head"], "BORROW", own_policy, before, amount, payload["account_id"], payload["command_id"])
    declared = []
    for posting in observation["expected_postings"]:
        need(posting["command_id"] == payload["command_id"], "expected posting CID differs")
        declared.append({"ordinal": posting["ordinal"], "account": posting["account"], "asset": posting["asset"],
                         "units": REF.unit_string(posting["units"], "declared posting")})
    equal(declared, expected["ordered_legs"], "declared obligations differ from independent legs")
    receipt = payload["receipt"]
    for key, value in (("account_id", payload["account_id"]), ("command_id", payload["command_id"]), ("asset", "BTC"),
                       ("journal_event_id", observation["journal"]["event_id"]), ("account_version", after["version"])):
        equal(receipt[key], value, "receipt identity differs: " + key)
    for key, value in (("amount", amount), ("principal", after["principal_units"]), ("interest", after["interest_units"]),
                       ("total", after["principal_units"] + after["interest_units"])):
        need(decimal_units(receipt[key], key) == value, "receipt quantity differs: " + key)
    risk_receipt = receipt["risk_evidence"]
    for field in ("equity", "initial_margin", "maintenance_margin", "open_order_margin", "available_margin"):
        need(REF.number(risk_receipt[field], field) == REF.number(post["risk"][field], field), "receipt risk differs: " + field)
    need(decimal_units(risk_receipt["borrowable_before"], "receipt quote") == REF.portfolio_quote(own_policy, before), "receipt original quote differs")
    need(risk_receipt["market_observed_at"] == market["observed_at"], "receipt market time differs")
    equal(risk_receipt["market_version"], market["version"], "receipt market version differs")
    credit, inbox, intent = observation["credit"], observation["inbox"], observation["intent"]
    equal(document(credit["result"]), receipt, "actual original credit receipt differs")
    equal(document(inbox["result"]), receipt, "actual inbox receipt differs")
    need(credit["scope"] == "account:"+payload["account_id"] and credit["kind"] == "borrowed" and inbox["kind"] == "BORROW"
         and inbox["state"] == "SUCCEEDED" and row["terminal_state"] == "SUCCEEDED", "terminal kind/state differs")
    for record in (credit, inbox, intent):
        need(record["command_id"] == payload["command_id"], "original CID differs")
    need(inbox["account_id"] == intent["account_id"] == payload["account_id"], "original account differs")
    for key in ("source_id", "payload_hash", "allocation_id", "descriptor_id", "operation_id", "market_snapshot_id", "selected_at"):
        equal(intent[key], payload[key], "intent binding differs: " + key)
    need(intent["journal_id"] == credit["journal_event_id"] == row["journal_id"] == observation["journal"]["event_id"], "original journal references differ")
    need(intent["pre_state_payload"] == REF.canonical(pre)
         and intent["pre_state_hash"] == hashlib.sha256(REF.canonical(pre).encode()).hexdigest(), "staged prestate binding differs")
    for key, value in (("pre_version", before["version"]), ("post_version", after["version"])):
        equal(intent[key], value, "intent version differs")
        equal(row[key], value, "decision version differs")
    return {"independent_financial_content_passed": True, "command_id": payload["command_id"],
            "decision_id": row["decision_id"], "source_id": payload["source_id"], "market_snapshot_id": payload["market_snapshot_id"],
            "journal_event_id": observation["journal"]["event_id"], "gross_before": expected["gross_components"]["before"],
            "gross_after": expected["gross_components"]["after"], "authorized_before_units": str(REF.authorized_quote(own_policy, before)),
            "observed_borrow_journal_legs": len(observation["journal"]["postings"]),
            "original_funded_capital_units": str(funded_units),
            "expected_postings_used_as_oracle": False, "interest_cash_balance_observed": False,
            "SQL_COMMIT_native_restart_provenance": "PENDING_SEPARATE_EXECUTION_AND_REOPEN_EVIDENCE",
            "production_approved": False}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("observation", type=Path)
    args = parser.parse_args()
    # This reader is intentionally a file-only offline checker, with no SQL or
    # imports of a production financial module or archived executable code.
    print(json.dumps(check_observation(REF.strict_loads(args.observation.read_text())), indent=2, sort_keys=True))
