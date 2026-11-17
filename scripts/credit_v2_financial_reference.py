"""Independent integer/Fraction reference for the synthetic V2 credit contract.

No production modules are imported. Inputs are an owned observation schema,
not an asserted production payload format. Actual capture/SQL closure is PENDING.
"""
from copy import deepcopy
from datetime import datetime
from fractions import Fraction as F
import hashlib
import json
import re


SCALE = 100_000_000
LIMIT = 10 ** 38
ZERO = F(0)
RUNTIME_STATUS = "PENDING_ACTUAL_CANONICAL_PAYLOAD_AND_CAPTURE"


class ReferenceInputError(ValueError):
    pass


class ReferenceRefusal(ValueError):
    pass


def units(text):
    value = F(text) * SCALE
    if value.denominator != 1:
        raise ReferenceInputError("manual amount is off the eight-place grid")
    return value.numerator


def integer(value, name, *, nonnegative=False):
    if type(value) is not int or abs(value) >= LIMIT or (nonnegative and value < 0):
        raise ReferenceInputError("invalid integer units: " + name)
    return value


def unit_string(value, name, *, nonnegative=False):
    """Published 52207b6 wire units; never Decimal, float, Unicode or bool."""
    if (not isinstance(value, str) or len(value) > 39
            or not re.fullmatch(r"(?:0|-[1-9][0-9]*|[1-9][0-9]*)", value)):
        raise ReferenceInputError("noncanonical unit string: " + name)
    return integer(int(value), name, nonnegative=nonnegative)


def number(value, name, *, positive=False):
    if (not isinstance(value, str) or len(value) > 128
            or not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", value)):
        raise ReferenceInputError("bounded decimal string required: " + name)
    parts = re.split("[eE]", value)
    if len(re.sub("[^0-9]", "", parts[0])) > 80 or (len(parts) == 2 and abs(int(parts[1])) > 100):
        raise ReferenceInputError("decimal range exceeded: " + name)
    result = F(value)
    if abs(result) > 10 ** 100 or (positive and result <= 0):
        raise ReferenceInputError("invalid decimal value: " + name)
    return result


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def strict_loads(text, *, canonical_required=False):
    if not isinstance(text, str):
        raise ReferenceInputError("oversized/nontext reference document")
    try:
        size = len(text.encode("utf-8"))
    except UnicodeError as exc:
        raise ReferenceInputError("invalid UTF-8 reference document") from exc
    if size > 1024 * 1024:
        raise ReferenceInputError("oversized/nontext reference document")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ReferenceInputError("duplicate field: " + key)
            result[key] = value
        return result

    def reject(value):
        raise ReferenceInputError("float or nonfinite token forbidden: " + value)

    try:
        value = json.loads(text, object_pairs_hook=pairs, parse_float=reject, parse_constant=reject)
    except (ValueError, RecursionError) as exc:
        raise ReferenceInputError("invalid reference JSON: " + str(exc)) from exc
    if canonical_required and canonical(value) != text:
        raise ReferenceInputError("noncanonical reference bytes")
    return value


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def fields(value, names, label):
    if type(value) is not dict or set(value) != set(names):
        raise ReferenceInputError("exact fields required: " + label)


POLICY = {
    "prices": {"USD": "1", "BTC": "100"},
    "tiers": {"USD": [[None, "1"]], "BTC": [[None, "0.8"]]},
    "ltv": {"USD": "0.5", "BTC": "0.5"},
    "borrow_im": "0.2", "borrow_mm": "0.1", "linear_im": "0.1", "linear_mm": "0.05",
    "mark": "100", "multiplier": "1", "new_fee": "0", "new_interest": "0",
    "step_units": units("0.01"), "risk_max_principal_units": units("10"), "max_total_debt": "10000",
    "account_limit_units": units("10"),
    "local_asset_limit_units": units("100"), "global_budget_units": units("1"),
    "allocations": {"0": units("0.5"), "1": units("0.5")}, "local_shard": "0",
}
STATE_FIELDS = ("version", "balances", "frozen_assets", "principal_units", "interest_units",
                "principal_ledger_units", "interest_ledger_units",
                "pool_units", "principal_receivable_units", "interest_receivable_units", "interest_cash_units",
                "shard_principal_units", "shard_interest_units", "positions", "orders", "halted", "liquidation_state")
ORDER_FIELDS = ("order_id", "symbol", "quantity_units", "filled_units", "limit_price", "reduce_only", "status")


def state(usd="100", btc="0", principal="0", interest="0", pool="1", *, version=1,
          frozen=None, positions=None, orders=None):
    return {"version": version, "balances": {"USD": units(usd), "BTC": units(btc)},
            "frozen_assets": frozen or {}, "principal_units": units(principal), "interest_units": units(interest),
            "principal_ledger_units": -units(principal), "interest_ledger_units": -units(interest),
            "pool_units": units(pool), "principal_receivable_units": units(principal),
            "interest_receivable_units": units(interest), "interest_cash_units": 0,
            "shard_principal_units": units(principal), "shard_interest_units": units(interest),
            "positions": positions or {}, "orders": orders or [], "halted": False, "liquidation_state": "NORMAL"}


def validate(policy, before):
    fields(policy, POLICY, "owned policy")
    fields(before, STATE_FIELDS, "owned before state")
    for key in ("version", "principal_units", "interest_units", "pool_units", "principal_receivable_units",
                "interest_receivable_units", "interest_cash_units", "shard_principal_units", "shard_interest_units"):
        integer(before[key], key, nonnegative=True)
    if before["version"] >= 2 ** 63 - 1:
        raise ReferenceInputError("account version cannot advance")
    for liability, ledger in (("principal_units", "principal_ledger_units"), ("interest_units", "interest_ledger_units")):
        integer(before[ledger], ledger)
        if before[ledger] != -before[liability]:
            raise ReferenceInputError("liability ledger disagrees with gross debt")
    if (before["principal_receivable_units"] != before["shard_principal_units"]
            or before["interest_receivable_units"] != before["shard_interest_units"]):
        raise ReferenceInputError("gross receivable disagrees with shard credit")
    if type(before["halted"]) is not bool or not isinstance(before["liquidation_state"], str):
        raise ReferenceInputError("invalid status fields")
    fields(before["balances"], ("USD", "BTC"), "balances")
    for asset, value in before["balances"].items():
        integer(value, asset + " cash")
    if type(before["frozen_assets"]) is not dict or set(before["frozen_assets"]) - {"USD", "BTC"}:
        raise ReferenceInputError("invalid frozen assets")
    for asset, value in before["frozen_assets"].items():
        integer(value, asset + " frozen", nonnegative=True)
        if value > max(0, before["balances"][asset]):
            raise ReferenceInputError("freeze exceeds positive gross")
    for key in ("step_units", "risk_max_principal_units", "account_limit_units",
                "local_asset_limit_units", "global_budget_units"):
        integer(policy[key], key, nonnegative=True)
    if policy["step_units"] <= 0:
        raise ReferenceInputError("step must be positive")
    if type(policy["allocations"]) is not dict or policy["local_shard"] not in policy["allocations"]:
        raise ReferenceInputError("unknown static shard allocation")
    for shard, allocation in policy["allocations"].items():
        if not isinstance(shard, str) or not shard.isdigit():
            raise ReferenceInputError("invalid shard key")
        integer(allocation, "allocation", nonnegative=True)
    if sum(policy["allocations"].values()) > policy["global_budget_units"]:
        raise ReferenceInputError("static allocations exceed global budget")
    fields(policy["prices"], ("USD", "BTC"), "prices")
    fields(policy["ltv"], ("USD", "BTC"), "ltv")
    fields(policy["tiers"], ("USD", "BTC"), "tiers")
    for value in policy["prices"].values():
        number(value, "asset price", positive=True)
    for key in ("borrow_im", "borrow_mm", "linear_im", "linear_mm", "mark", "multiplier", "max_total_debt", "new_fee", "new_interest"):
        number(policy[key], key)
    if policy["prices"]["USD"] != "1" or F(policy["new_fee"]) or F(policy["new_interest"]):
        raise ReferenceInputError("first profile requires USD1 and zero new fee/interest")
    for key in ("borrow_im", "borrow_mm", "linear_im", "linear_mm"):
        if not 0 <= F(policy[key]) <= 1:
            raise ReferenceInputError("invalid margin rate")
    if F(policy["borrow_mm"]) > F(policy["borrow_im"]) or F(policy["linear_mm"]) > F(policy["linear_im"]):
        raise ReferenceInputError("MM exceeds IM")
    if F(policy["mark"]) <= 0 or F(policy["multiplier"]) != 1:
        raise ReferenceInputError("first profile requires mark>0 and multiplier1")
    if F(policy["max_total_debt"]) < 0 or F(policy["linear_im"]) <= 0:
        raise ReferenceInputError("invalid debt limit or linear IM")
    for asset, bands in policy["tiers"].items():
        if type(bands) is not list or not bands or len(bands) > 64:
            raise ReferenceInputError("invalid marginal tiers")
        lower, factor = ZERO, F(1)
        for index, band in enumerate(bands):
            if type(band) is not list or len(band) != 2:
                raise ReferenceInputError("invalid tier shape")
            cap, haircut = band
            rate = number(haircut, "tier factor")
            if not 0 <= rate <= factor:
                raise ReferenceInputError("increasing/invalid factor")
            factor = rate
            if cap is None:
                if index != len(bands) - 1:
                    raise ReferenceInputError("unbounded nonfinal tier")
            else:
                upper = number(cap, "tier upper", positive=True)
                if upper <= lower:
                    raise ReferenceInputError("nonincreasing marginal threshold")
                lower = upper
        if bands[-1][0] is not None or not 0 <= number(policy["ltv"][asset], "ltv") <= 1:
            raise ReferenceInputError("invalid terminal tier or LTV")
        if asset == "USD" and any(F(band[1]) != 1 for band in bands):
            raise ReferenceInputError("USD haircut unsupported")
    if type(before["positions"]) is not dict or set(before["positions"]) - {"BTC-PERP"}:
        raise ReferenceInputError("unsupported position")
    for position in before["positions"].values():
        fields(position, ("quantity_units", "cost_basis_usd_units"), "position")
        for key, value in position.items():
            integer(value, key)
        if not position["quantity_units"]:
            raise ReferenceInputError("flat position must be omitted")
    if type(before["orders"]) is not list:
        raise ReferenceInputError("orders must be a list")
    seen = set()
    for order in before["orders"]:
        fields(order, ORDER_FIELDS, "order")
        if (not isinstance(order["order_id"], str) or not order["order_id"] or order["order_id"] in seen
                or order["symbol"] != "BTC-PERP" or type(order["reduce_only"]) is not bool
                or order["status"] not in ("OPEN", "PARTIALLY_FILLED", "FILLED", "CANCELLED")):
            raise ReferenceInputError("invalid order identity/status")
        seen.add(order["order_id"])
        q = integer(order["quantity_units"], "order quantity")
        f = integer(order["filled_units"], "filled quantity")
        if not q or abs(f) > abs(q) or (f and (f > 0) != (q > 0)):
            raise ReferenceInputError("invalid signed order fill")
        number(order["limit_price"], "order price", positive=True)
    if before["shard_principal_units"] < before["principal_units"] or before["shard_interest_units"] < before["interest_units"]:
        raise ReferenceInputError("shard credit cannot omit this account")


def marginal(value, bands):
    total, lower = ZERO, ZERO
    for cap, factor in bands:
        upper = value if cap is None else F(cap)
        total += max(ZERO, min(value, upper) - lower) * F(factor)
        lower = upper
    return total


def risk(policy, before):
    validate(policy, before)
    gross = collateral = loan_value = frozen = deficit = ZERO
    for asset, amount in before["balances"].items():
        price = F(policy["prices"][asset])
        positive, negative = max(0, amount), max(0, -amount)
        held = before["frozen_assets"].get(asset, 0)
        value = marginal(F(positive - held, SCALE) * price, policy["tiers"][asset])
        gross += F(positive, SCALE) * price
        deficit += F(negative, SCALE) * price
        frozen += F(held, SCALE) * price
        collateral += value
        loan_value += value * F(policy["ltv"][asset])
    principal = F(before["principal_units"], SCALE) * F(policy["prices"]["BTC"])
    interest = F(before["interest_units"], SCALE) * F(policy["prices"]["BTC"])
    borrow_debt = principal + interest
    pnl = linear_notional = ZERO
    mark = F(policy["mark"])
    for position in before["positions"].values():
        marked = F(position["quantity_units"], SCALE) * mark
        pnl += marked - F(position["cost_basis_usd_units"], SCALE)
        linear_notional += abs(marked)
    reserve = ZERO
    for order in before["orders"]:
        if order["status"] not in ("OPEN", "PARTIALLY_FILLED"):
            continue
        q = F(order["quantity_units"] - order["filled_units"], SCALE)
        price = F(order["limit_price"])
        reserve += max(ZERO, q * (price - mark))
        if not order["reduce_only"]:
            reserve += abs(q) * max(mark, price) * F(policy["linear_im"])
    debt = borrow_debt + deficit
    equity = collateral - debt + pnl
    im = borrow_debt * F(policy["borrow_im"]) + linear_notional * F(policy["linear_im"])
    mm = borrow_debt * F(policy["borrow_mm"]) + linear_notional * F(policy["linear_mm"])
    usable = equity - im - reserve
    return {"gross_asset_value": gross, "cash_deficit_value": deficit, "frozen_value": frozen,
            "principal_value": principal, "interest_value": interest, "debt_value": debt,
            "collateral_value": collateral, "loan_value": loan_value, "unrealized_pnl": pnl,
            "accounting_equity": gross - debt + pnl, "risk_equity": equity,
            "initial_margin": im, "maintenance_margin": mm, "order_margin": reserve,
            "available_margin": usable,
            "status": "LIQUIDATION" if equity <= mm else "MARGIN_CALL" if usable < 0 else "HEALTHY"}


def portfolio_quote(policy, before):
    base = risk(policy, before)
    price, step = F(policy["prices"]["BTC"]), policy["step_units"]

    def feasible(count):
        amount = F(count * step, SCALE) * price
        debt = base["debt_value"] + amount
        equity = base["risk_equity"] - amount
        return (debt <= F(policy["max_total_debt"]) and debt <= base["loan_value"]
                and equity - base["initial_margin"] - amount * F(policy["borrow_im"]) - base["order_margin"] >= 0
                and equity > base["maintenance_margin"] + amount * F(policy["borrow_mm"]))

    if not feasible(0):
        return 0
    low, high = 0, max(0, (policy["risk_max_principal_units"] - before["principal_units"]) // step)
    while low < high:
        middle = (low + high + 1) // 2
        if feasible(middle):
            low = middle
        else:
            high = middle - 1
    return low * step


def authorized_quote(policy, before):
    step = policy["step_units"]
    gross = before["principal_units"] + before["interest_units"]
    shard_gross = before["shard_principal_units"] + before["shard_interest_units"]
    caps = (portfolio_quote(policy, before), before["pool_units"],
            policy["account_limit_units"] - gross,
            policy["local_asset_limit_units"] - shard_gross,
            policy["allocations"][policy["local_shard"]] - shard_gross)
    return max(0, min(caps)) // step * step


def amount_text(value):
    value = integer(value, "formatted amount")
    whole, decimal = divmod(abs(value), SCALE)
    result = str(whole) + (("." + str(decimal).rjust(8, "0").rstrip("0")) if decimal else "")
    return "-" + result if value < 0 else result


def gross_components(before):
    return {"assets": {asset: amount_text(value) for asset, value in before["balances"].items() if value > 0},
            "cash_deficits": {asset: amount_text(-value) for asset, value in before["balances"].items() if value < 0},
            "principal": {"BTC": amount_text(before["principal_units"])} if before["principal_units"] else {},
            "interest": {"BTC": amount_text(before["interest_units"])} if before["interest_units"] else {}}


def transition(kind, policy, before, amount_units, account_id="alice"):
    validate(policy, before)
    amount = integer(amount_units, "request amount", nonnegative=True)
    if amount <= 0:
        raise ReferenceRefusal("nonpositive_amount")
    after, postings = deepcopy(before), [("customer:" + account_id, -amount)]
    if kind == "BORROW":
        if before["halted"] or before["liquidation_state"] != "NORMAL":
            raise ReferenceRefusal("account_not_normal")
        if amount % policy["step_units"]:
            raise ReferenceRefusal("quantity_step")
        if amount > authorized_quote(policy, before):
            raise ReferenceRefusal("quote_or_limit_or_pool_or_static_allocation")
        after["balances"]["BTC"] += amount
        after["principal_units"] += amount
        after["principal_ledger_units"] -= amount
        after["shard_principal_units"] += amount
        after["principal_receivable_units"] += amount
        after["pool_units"] -= amount
        postings = [("customer:" + account_id, amount), ("liability:principal:" + account_id, -amount),
                    ("system:credit-pool", -amount), ("system:credit-principal-receivable", amount)]
    elif kind == "REPAY":
        if amount > before["principal_units"] + before["interest_units"]:
            raise ReferenceRefusal("repay_exceeds_debt")
        if amount > before["balances"]["BTC"] - before["frozen_assets"].get("BTC", 0):
            raise ReferenceRefusal("insufficient_unfrozen_cash")
        interest = min(amount, before["interest_units"])
        principal = amount - interest
        after["balances"]["BTC"] -= amount
        for key in ("interest_units", "shard_interest_units", "interest_receivable_units"):
            after[key] -= interest
        for key in ("principal_units", "shard_principal_units", "principal_receivable_units"):
            after[key] -= principal
        after["principal_ledger_units"] += principal
        after["interest_ledger_units"] += interest
        after["pool_units"] += principal
        after["interest_cash_units"] += interest
        if interest:
            postings += [("liability:interest:" + account_id, interest),
                         ("system:credit-interest-receivable", -interest), ("system:credit-interest-cash", interest)]
        if principal:
            postings += [("liability:principal:" + account_id, principal),
                         ("system:credit-principal-receivable", -principal), ("system:credit-pool", principal)]
    else:
        raise ReferenceInputError("unsupported operation")
    after["version"] += 1
    validate(policy, after)
    legs = [{"ordinal": ordinal, "account": name, "asset": "BTC", "units": value}
            for ordinal, (name, value) in enumerate(sorted(postings))]
    assert sum(leg["units"] for leg in legs) == 0
    return {"after": after, "ordered_legs": legs,
            "gross_components": {"before": gross_components(before), "after": gross_components(after)},
            "market_dependency": "SNAPSHOT" if kind == "BORROW" else "NONE",
            "new_borrow_decision_count": 1 if kind == "BORROW" else 0}


def checkpoint_contract(observed, selected, final, first_sid, final_sid, *, max_age_us=5_000_000, future_us=1_000_000, recorded=None):
    integer(max_age_us, "max_age_us", nonnegative=True)
    integer(future_us, "max_future_skew_us", nonnegative=True)
    def utc(text):
        if not isinstance(text, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{6})?\+00:00", text):
            raise ReferenceInputError("real UTC timestamp string required")
        try:
            return datetime.fromisoformat(text)
        except ValueError as exc:
            raise ReferenceInputError("invalid UTC date/time") from exc
    seen, first, last = map(utc, (observed, selected, final))
    if not isinstance(first_sid, str) or not first_sid or first_sid != final_sid or last < first:
        raise ReferenceRefusal("SID_changed_or_clock_backwards")
    if recorded is not None and utc(recorded) < last:
        raise ReferenceRefusal("recorded_before_final_check")
    for time in (first, last):
        delta = time - seen
        age = (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds
        if not -future_us <= age <= max_age_us:
            raise ReferenceRefusal("stale_or_future_market")
    return True  # Predicate only; this cannot prove the timestamps were captured.


SOURCE_FIELDS = ("command_id", "source_id", "account_id", "kind", "payload_hash", "source_kind", "actor_id",
                 "source_reference", "authority_id", "command_payload", "payload")
SOURCE_RECEIPT_FIELDS = ("format", "source_kind", "actor_id", "source_reference", "authority_id", "account_id",
                         "command_id", "kind", "payload_hash", "command_payload", "accepted_at")


def source_contract(source):
    """Only published content/identity checks; never authenticates a real source."""
    fields(source, SOURCE_FIELDS, "published source row")
    receipt = strict_loads(source["payload"], canonical_required=True)
    fields(receipt, SOURCE_RECEIPT_FIELDS, "published source receipt")
    if type(receipt["format"]) is not int or receipt["format"] != 2 or receipt["source_kind"] != "synthetic_local":
        raise ReferenceInputError("unsupported source format/kind")
    if receipt["kind"] not in ("BORROW", "REPAY"):
        raise ReferenceInputError("unsupported source operation")
    for field in SOURCE_FIELDS:
        if field not in ("source_id", "payload") and source[field] != receipt[field]:
            raise ReferenceInputError("source relational identity mismatch: " + field)
    for field in ("account_id", "command_id", "actor_id", "source_reference", "authority_id"):
        if not isinstance(receipt[field], str) or not receipt[field]:
            raise ReferenceInputError("source identity must be text")
    command = strict_loads(receipt["command_payload"], canonical_required=True)
    if type(command) is not dict:
        raise ReferenceInputError("canonical command object required")
    expected = hashlib.sha256(receipt["command_payload"].encode()).hexdigest()
    if expected != source["payload_hash"]:
        raise ReferenceInputError("original command hash mismatch")
    if source["source_id"] != "credit-source:" + hashlib.sha256(source["payload"].encode()).hexdigest():
        raise ReferenceInputError("source content identity mismatch")
    accepted = receipt["accepted_at"]
    if not isinstance(accepted, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}\+00:00", accepted):
        raise ReferenceInputError("producer UTC checkpoint needs six microsecond digits")
    checkpoint_contract(accepted, accepted, accepted, "synthetic-content-only", "synthetic-content-only")
    return {"content_identity_matches": True, "source_authenticity": "PENDING_ACTUAL_SOURCE_AND_INBOX_ROWS"}


JOURNAL_FIELDS = ("sequence", "event_id", "fingerprint", "previous_hash", "event_hash", "sealed", "postings")
POSTING_FIELDS = ("ordinal", "account", "asset", "units")


def event_identity(account_id, command_id):
    return "credit:" + digest(["account:" + account_id, command_id])


def journal_hashes(sequence, event_id, previous_hash, legs):
    """b510d18 published integer wire algorithm, independently implemented."""
    fingerprint = digest([[leg["account"], leg["asset"], leg["units"]] for leg in legs])
    return fingerprint, digest([sequence, event_id, previous_hash, fingerprint])


def compare_journal(observed, prior_head, kind, policy, before, amount_units, account_id, command_id):
    """Compare supplied original rows with operation-derived legs, not expected-legs data.

    The caller must later supply the original receipt's actual SQL journal rows.
    Content comparison cannot prove SQL/COMMIT/reopen provenance by itself.
    """
    fields(observed, JOURNAL_FIELDS, "published actual journal")
    fields(prior_head, ("sequence", "event_hash"), "original journal head")
    prior = integer(prior_head["sequence"], "prior sequence", nonnegative=True)
    sequence = integer(observed["sequence"], "journal sequence", nonnegative=True)
    if sequence >= 2 ** 63 or sequence != prior + 1:
        raise ReferenceInputError("journal sequence is not original head plus one")
    if type(observed["sealed"]) is not int or observed["sealed"] != 1:
        raise ReferenceInputError("journal is not sealed integer1")
    for text in (prior_head["event_hash"], observed["previous_hash"], observed["event_hash"], observed["fingerprint"]):
        if not isinstance(text, str) or not re.fullmatch(r"[0-9a-f]{64}", text):
            raise ReferenceInputError("canonical journal digest required")
    if observed["previous_hash"] != prior_head["event_hash"] or observed["event_id"] != event_identity(account_id, command_id):
        raise ReferenceInputError("original journal identity/head mismatch")
    if type(observed["postings"]) is not list:
        raise ReferenceInputError("actual ordinal postings must be a list")
    legs = []
    for ordinal, row in enumerate(observed["postings"]):
        fields(row, POSTING_FIELDS, "posting")
        if type(row["ordinal"]) is not int or row["ordinal"] != ordinal:
            raise ReferenceInputError("posting ordinal must be contiguous integer")
        if not isinstance(row["account"], str) or not row["account"] or row["asset"] != "BTC":
            raise ReferenceInputError("unexpected journal account/asset")
        value = unit_string(row["units"], "posting units")
        if not value:
            raise ReferenceInputError("zero journal leg forbidden")
        legs.append({"ordinal": ordinal, "account": row["account"], "asset": "BTC", "units": value})
    expected = transition(kind, policy, before, amount_units, account_id)["ordered_legs"]
    if legs != expected:
        raise ReferenceInputError("journal legs disagree with independent financial transition")
    fingerprint, event_hash = journal_hashes(sequence, observed["event_id"], observed["previous_hash"], legs)
    if observed["fingerprint"] != fingerprint or observed["event_hash"] != event_hash:
        raise ReferenceInputError("original journal content hash mismatch")
    return {"independent_legs_and_hashes_match": True, "actual_SQL_and_COMMIT_provenance": "PENDING"}


def fifo_contract(rows, account_id, command_id):
    if type(rows) is not list:
        raise ReferenceInputError("actual FIFO rows required")
    candidates, selected, sequences, commands = [], None, set(), set()
    for row in rows:
        fields(row, ("sequence", "account", "CID", "state"), "FIFO row")
        integer(row["sequence"], "FIFO sequence", nonnegative=True)
        if (not isinstance(row["account"], str) or not isinstance(row["CID"], str)
                or row["sequence"] in sequences or row["CID"] in commands
                or row["state"] not in ("PENDING", "SUCCEEDED", "REJECTED", "QUARANTINED")):
            raise ReferenceInputError("invalid/duplicate FIFO identity or unknown state")
        sequences.add(row["sequence"])
        commands.add(row["CID"])
        if row["account"] == account_id and row["state"] == "PENDING":
            candidates.append(row["sequence"])
            if row["CID"] == command_id:
                if selected is not None:
                    raise ReferenceInputError("duplicate selected CID")
                selected = row["sequence"]
    if selected is None or selected != min(candidates):
        raise ReferenceRefusal("not_original_account_FIFO_head")
    return True


def manual_vectors():
    order = {"order_id": "manual-eight", "symbol": "BTC-PERP", "quantity_units": units("8"),
             "filled_units": 0, "limit_price": "100", "reduce_only": False, "status": "OPEN"}
    special = deepcopy(POLICY)
    special["tiers"]["BTC"] = [["50", "0.8"], [None, "0.5"]]
    partial = {**order, "order_id": "partial", "quantity_units": units("2"), "filled_units": units("0.5"),
               "limit_price": "105", "status": "PARTIALLY_FILLED"}
    reduce = {**order, "order_id": "reduce", "quantity_units": units("-0.1"), "limit_price": "90", "reduce_only": True}
    return [
        ("M1_BASE_BORROW", "BORROW", POLICY, state(), "0.4"),
        ("M2_OPEN_ORDER_BORROW", "BORROW", POLICY, state(btc="0.4", principal="0.4", pool="0.6", version=3, orders=[order]), "0.03"),
        ("M3_CASH_DEFICIT_BORROW", "BORROW", POLICY, state(usd="-1", btc="1", principal="0.1", interest="0.01", pool="0.9", version=7), "0.1"),
        ("M4_OPENING_INTEREST_BORROW", "BORROW", POLICY, state(btc="0.4", principal="0.4", interest="0.05", pool="0.6", version=3), "0.05"),
        ("M5_MIXED_REPAY", "REPAY", POLICY, state(btc="0.5", principal="0.4", interest="0.05", pool="0.6", version=4), "0.1"),
        ("M6_TIER_FREEZE_POSITION_PARTIAL_ORDER", "BORROW", special,
         state(btc="1.2", principal="0.2", interest="0.01", pool="0.8", version=9,
               frozen={"BTC": units("0.2")}, positions={"BTC-PERP": {"quantity_units": units("0.3"), "cost_basis_usd_units": units("27")}},
               orders=[partial, reduce]), "0.01"),
        ("M7_PRINCIPAL_ONLY_REPAY", "REPAY", POLICY, state(btc="0.4", principal="0.4", pool="0.6", version=4), "0.1"),
        ("M8_INTEREST_ONLY_REPAY", "REPAY", POLICY, state(btc="0.5", principal="0.4", interest="0.05", pool="0.6", version=4), "0.02"),
    ]


def self_check():
    # Hand constants frozen before reading the future production capture code.
    hand = {
        "M1_BASE_BORROW": ("132", "40", "100", "92", "8", "4", "0", "84", "0.26", "0.1", 4),
        "M2_OPEN_ORDER_BORROW": ("134.4", "43", "100", "91.4", "8.6", "4.3", "80", "2.8", "0.02", "0.02", 4),
        "M3_CASH_DEFICIT_BORROW": ("88", "22", "88", "66", "4.2", "2.1", "0", "61.8", "0.22", "0.22", 4),
        "M4_OPENING_INTEREST_BORROW": ("136", "50", "95", "86", "10", "5", "0", "76", "0.18", "0", 4),
        "M5_MIXED_REPAY": ("132", "35", "105", "97", "7", "3.5", "0", "90", "0.31", "0.15", 7),
        "M6_TIER_FREEZE_POSITION_PARTIAL_ORDER": ("165.5", "22", "202", "146.5", "7.4", "3.7", "24.25", "114.85", "0.6", "0.28", 4),
        "M7_PRINCIPAL_ONLY_REPAY": ("124", "30", "100", "94", "6", "3", "0", "88", "0.32", "0.2", 4),
        "M8_INTEREST_ONLY_REPAY": ("138.4", "43", "105", "95.4", "8.6", "4.3", "0", "86.8", "0.26", "0.07", 4),
    }
    results = []
    names = ("collateral_value", "debt_value", "accounting_equity", "risk_equity", "initial_margin", "maintenance_margin", "order_margin", "available_margin")
    for name, kind, policy, before, amount in manual_vectors():
        result = transition(kind, policy, before, units(amount))
        after_risk = risk(policy, result["after"])
        expected = hand[name]
        for field, wanted in zip(names, expected[:8]):
            assert after_risk[field] == F(wanted), (name, field, after_risk[field], wanted)
        assert portfolio_quote(policy, result["after"]) == units(expected[8]), (name, "next portfolio quote")
        assert authorized_quote(policy, result["after"]) == units(expected[9]), (name, "next authorized quote")
        assert len(result["ordered_legs"]) == expected[10]
        assert result["after"]["version"] == before["version"] + 1
        results.append({"id": name, "operation": kind, "before": before, "policy": policy,
                        "amount_units": units(amount), "expected_transition": result,
                        "before_risk": risk(policy, before), "after_risk": after_risk,
                        "before_portfolio_quote_units": portfolio_quote(policy, before),
                        "before_authorized_quote_units": authorized_quote(policy, before),
                        "after_portfolio_quote_units": portfolio_quote(policy, result["after"]),
                        "after_authorized_quote_units": authorized_quote(policy, result["after"]),
                        "actual_capture": None, "source_id": None, "original_CID": None,
                        "original_SID": None, "selected_at": None, "last_checked_at": None,
                        "journal_event_hash": None, "producer_commit": None, "financial_commit": None})
    return {"schema": "independent-credit-observation-v1", "runtime_status": RUNTIME_STATUS,
            "synthetic_only": True, "reference_manual_self_check": "PASS", "vectors": results}


def json_value(value):
    if isinstance(value, F):
        return str(value)
    raise TypeError(type(value).__name__)


if __name__ == "__main__":
    print(json.dumps(self_check(), default=json_value, sort_keys=True, indent=2))
