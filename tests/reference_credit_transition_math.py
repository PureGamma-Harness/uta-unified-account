"""Independent integer/Fraction oracle; intentionally contains no uta imports."""

from fractions import Fraction
import re


MAGNITUDE = 10 ** 38
I64_MAX = 2 ** 63 - 1
STATE_FIELDS = {"version", "cash_units", "principal_units", "interest_units", "principal_ledger_units",
                "interest_ledger_units", "shard_principal_units", "shard_interest_units", "pool_units",
                "principal_receivable_units", "interest_receivable_units"}
SIGNED = {"cash_units", "principal_ledger_units", "interest_ledger_units"}


class Refusal(ValueError):
    def __init__(self, code="credit_transition_invalid", status=503):
        self.code, self.status = code, status
        super().__init__(code)


def unit(value, signed=False):
    if type(value) is not str or not re.fullmatch(r"0|-?[1-9][0-9]{0,37}", value, re.ASCII):
        raise Refusal()
    number = int(value)
    if abs(number) >= MAGNITUDE or (number < 0 and not signed):
        raise Refusal()
    return number


def snapshot(value, advance=False):
    if type(value) is not dict or set(value) != STATE_FIELDS:
        raise Refusal()
    version = value["version"]
    maximum = I64_MAX - 1 if advance else I64_MAX
    if type(version) is not int or not 0 <= version <= maximum:
        raise Refusal()
    result = {key: unit(item, key in SIGNED) for key, item in value.items() if key != "version"}
    result["version"] = version
    if (result["principal_ledger_units"] + result["principal_units"] != 0
            or result["interest_ledger_units"] + result["interest_units"] != 0):
        raise Refusal()
    if (result["principal_units"] > result["shard_principal_units"]
            or result["interest_units"] > result["shard_interest_units"]
            or result["principal_receivable_units"] != result["shard_principal_units"]
            or result["interest_receivable_units"] != result["shard_interest_units"]):
        raise Refusal()
    for keys in (("principal_units", "interest_units"), ("shard_principal_units", "shard_interest_units")):
        if sum(result[key] for key in keys) >= MAGNITUDE:
            raise Refusal()
    return result


def wire_state(value):
    return {key: number if key == "version" else str(number) for key, number in value.items()}


def base_state(**changes):
    result = {"version": 1, "cash_units": "0", "principal_units": "0", "interest_units": "0",
              "principal_ledger_units": "0", "interest_ledger_units": "0", "shard_principal_units": "0",
              "shard_interest_units": "0", "pool_units": "100000000",
              "principal_receivable_units": "0", "interest_receivable_units": "0"}
    result.update(changes)
    return result


def calculate(*, before, amount_units, quote_units, quantity_step_units, limits,
              declared_allocation_units, account_id="alice", asset="BTC"):
    """Apply a four-owner double-entry movement, then derive state from owners."""
    current = snapshot(before, advance=True)
    if type(limits) is not dict or set(limits) != {"account_limit_units", "local_asset_limit_units"}:
        raise Refusal()
    q, quote, step = (unit(v) for v in (amount_units, quote_units, quantity_step_units))
    account_cap, local_cap = (unit(limits[k]) for k in ("account_limit_units", "local_asset_limit_units"))
    allocation_cap = unit(declared_allocation_units)
    if not q or not step or q % step:
        raise Refusal()
    account_gross = current["principal_units"] + current["interest_units"]
    shard_gross = current["shard_principal_units"] + current["shard_interest_units"]
    if q > quote or account_gross + q > account_cap or shard_gross + q > min(local_cap, allocation_cap):
        raise Refusal("credit_limit", 409)
    if q > current["pool_units"]:
        raise Refusal("credit_pool_empty", 409)
    owner_values = {"customer:" + account_id: current["cash_units"],
                    "liability:principal:" + account_id: current["principal_ledger_units"],
                    "system:credit-pool": current["pool_units"],
                    "system:credit-principal-receivable": current["principal_receivable_units"]}
    delta = {"customer:" + account_id: q, "liability:principal:" + account_id: -q,
             "system:credit-pool": -q, "system:credit-principal-receivable": q}
    if sum(delta.values()) != 0:
        raise AssertionError("independent journal was not balanced")
    resulting = {owner: value + delta[owner] for owner, value in owner_values.items()}
    if any(abs(v) >= MAGNITUDE for v in resulting.values()):
        raise Refusal()
    after = dict(current)
    after.update(cash_units=resulting["customer:" + account_id],
                 principal_ledger_units=resulting["liability:principal:" + account_id],
                 principal_units=-resulting["liability:principal:" + account_id],
                 principal_receivable_units=resulting["system:credit-principal-receivable"],
                 shard_principal_units=resulting["system:credit-principal-receivable"],
                 pool_units=resulting["system:credit-pool"], version=current["version"] + 1)
    postings = [{"ordinal": index, "account": owner, "asset": asset, "units": str(delta[owner])}
                for index, owner in enumerate(sorted(delta))]
    return {"before": wire_state(current), "after": wire_state(after), "postings": postings}


def supplied_tiered_quote():
    """Independent assumed USD100/BTC.65/debt.4 example; not archived quote proof."""
    collateral_btc = Fraction(25) * Fraction(9, 10) + Fraction(40) * Fraction(3, 5)
    collateral = 100 + collateral_btc
    debt = Fraction(2, 5) * 100
    available = collateral - debt - debt / 5
    bounds = (Fraction(10) - Fraction(2, 5), (10000 - debt) / 100,
              (collateral / 2 - debt) / 100, available / 120)
    quote = min(bounds) // Fraction(1, 100) * Fraction(1, 100)
    return {"collateral_USD": str(collateral), "loan_value_USD": str(collateral / 2),
            "debt_USD": str(debt), "pre_step_LTV_quote_BTC": str((collateral / 2 - debt) / 100),
            "supplied_quote_units": str(int(quote * 10 ** 8))}
