"""Owned, synthetic policy vectors; this module imports no ``uta`` code.

Run directly before comparing the SUT. Every expected amount below is a manual
golden, checked with Fraction arithmetic from raw strings rather than SUT models.
The fixed bands and permission table describe this repository's phase-one policy.
"""
from copy import deepcopy
from fractions import Fraction as Q
import json


PRICES = {"USD": "1", "BTC": "100", "ETH": "50"}
RATES = {"USD": ("0.1", "0.05"), "BTC": ("0.2", "0.1"), "ETH": ("0.1", "0.05")}
LTV = {"USD": "1", "BTC": "0.5", "ETH": "0.5"}
ZERO = Q(0)


def account(gross, principal=None, interest=None, frozen=None, positions=None,
            order="0", deficits=None):
    return {"gross": gross, "principal": principal or {}, "interest": interest or {},
            "frozen": frozen or {}, "positions": positions or {}, "order": order,
            "deficits": deficits or {}}


GROSS_DEBT = account({"USD": "50", "BTC": "2", "ETH": "2"},
                     {"BTC": "0.5", "ETH": "0.2"}, {"BTC": "0.1", "ETH": "0.1"},
                     {"BTC": "1"}, order="1.25", deficits={"USD": "3"})
HEDGE = account({"USD": "100", "BTC": "1"}, {"BTC": "0.5"}, {"BTC": "0.1"},
                positions={"X": ("1", "100"), "Y": ("-1", "-100")})
TIER_SHOCKS = {"down": ({"BTC": "-0.1", "ETH": "-0.2"}, {}),
               "up": ({"BTC": "0.1", "ETH": "0.2"}, {})}
HEDGE_SHOCKS = {"down": ({"BTC": "-0.2"}, {"X": "-0.2", "Y": "-0.2"}),
                "up": ({"BTC": "0.2"}, {"X": "0.2", "Y": "0.2"})}


def discounted(asset, value):
    """Closed form for the published two-band manual table, in USD notional."""
    if asset == "USD":
        return value
    threshold, first, rest = ((Q(100), Q(4, 5), Q(1, 2)) if asset == "BTC"
                              else (Q(50), Q(9, 10), Q(3, 5)))
    return min(value, threshold) * first + max(ZERO, value - threshold) * rest


def cross(raw, *, zero_rates=False, full_ltv=False):
    """Independent cashflow valuation; no production helpers or outputs enter."""
    gross = frozen = collateral = loan = principal = interest = deficit = ZERO
    borrow_im = borrow_mm = ZERO
    for asset, price_text in PRICES.items():
        price = Q(price_text)
        total = Q(raw["gross"].get(asset, "0")) * price
        held = Q(raw["frozen"].get(asset, "0")) * price
        value = discounted(asset, total - held)
        gross += total
        frozen += held
        collateral += value
        loan += value * (1 if full_ltv else Q(LTV[asset]))
        p = Q(raw["principal"].get(asset, "0")) * price
        i = Q(raw["interest"].get(asset, "0")) * price
        principal += p
        interest += i
        deficit += Q(raw["deficits"].get(asset, "0")) * price
        if not zero_rates:
            borrow_im += (p + i) * Q(RATES[asset][0])
            borrow_mm += (p + i) * Q(RATES[asset][1])
    pnl = linear_im = linear_mm = ZERO
    for quantity, cost in raw["positions"].values():
        marked = Q(quantity) * 100
        pnl += marked - Q(cost)
        linear_im += abs(marked) / 10
        linear_mm += abs(marked) / 20
    debt = principal + interest + deficit
    equity = collateral - debt + pnl
    im, mm = borrow_im + linear_im, borrow_mm + linear_mm
    available = equity - im - Q(raw["order"])
    return {"accounting_equity": gross - debt + pnl, "collateral_value": collateral,
            "risk_equity": equity, "loan_value": loan, "principal_value": principal,
            "interest_value": interest, "cash_deficit_value": deficit, "debt_value": debt,
            "frozen_value": frozen, "unrealized_pnl": pnl, "initial_margin": im,
            "maintenance_margin": mm, "order_margin": Q(raw["order"]),
            "available_margin": available,
            "status": "LIQUIDATION" if equity <= mm else "MARGIN_CALL" if available < 0 else "HEALTHY"}


def stress(raw, shocks, *, floor="0", liquidity="0", credit="0"):
    """Revalue the manual bands, then keep losses of each distinct unit."""
    losses, units = {}, {}
    for name, (assets, instruments) in shocks.items():
        unit = {}
        for asset, text in PRICES.items():
            price = Q(text)
            free = Q(raw["gross"].get(asset, "0")) - Q(raw["frozen"].get(asset, "0"))
            debt = sum((Q(raw[field].get(asset, "0")) for field in
                        ("principal", "interest", "deficits")), ZERO)
            shocked = price * (1 + Q(assets.get(asset, "0")))
            before = discounted(asset, free * price) - debt * price
            after = discounted(asset, free * shocked) - debt * shocked
            unit[asset] = max(ZERO, before - after)
        for symbol, (quantity, _) in raw["positions"].items():
            unit[symbol] = max(ZERO, -Q(quantity) * 100 * Q(instruments.get(symbol, "0")))
        units[name] = unit
        losses[name] = sum(unit.values(), ZERO)
    requirement = max(max(losses.values()), Q(floor)) + Q(liquidity) + Q(credit)
    return {"losses": losses, "units": units, "requirement": requirement}


def feasible_extra_loan(raw, asset, quantity, *, zero_rates=False, full_ltv=False):
    """Resulting balance-sheet feasibility, checked independently of cap formulas."""
    state = cross(raw, zero_rates=zero_rates, full_ltv=full_ltv)
    value = Q(quantity) * Q(PRICES[asset])
    initial, maintenance = (ZERO, ZERO) if zero_rates else map(Q, RATES[asset])
    debt = state["debt_value"] + value
    equity = state["risk_equity"] - value  # Policy: new proceeds leave collateral.
    return (Q(raw["principal"].get(asset, "0")) + Q(quantity) <= 1000
            and debt <= 10000 and debt <= state["loan_value"]
            and equity - state["initial_margin"] - value * initial - Q(raw["order"]) >= 0
            and equity > state["maintenance_margin"] + value * maintenance)


def without_leg(symbol):
    result = deepcopy(HEDGE)
    del result["positions"][symbol]
    return result


def boundary(gross):
    return account({"USD": gross}, {"USD": "10"}, order="1" if gross == "12" else "0")


def zero_boundary(usd):
    return account({"USD": usd, "BTC": "2"}, {"BTC": "1"}, {"BTC": "0.0025"}, {"BTC": "1"})


def rejection(mode="cross", quote="USD", settlement="USD", catalog_settlement="USD", hedges=()):
    """Phase-one permissions table. PM/Isolated and hedge eligibility are disabled."""
    if mode != "cross":
        return "phase1_account_mode_unsupported"
    if any(unit != "USD" for unit in (quote, settlement, catalog_settlement)):
        return "phase1_settlement_unsupported"
    return "phase1_hedge_offsets_disabled" if hedges else None


def self_check():
    checks = []

    def expect(name, actual, expected):
        for field, value in expected.items():
            wanted = value if field == "status" else Q(value)
            assert actual[field] == wanted, (name, field, actual[field], wanted)
        checks.append(name)

    expect("V1 gross/debt/frozen/multicurrency", cross(GROSS_DEBT), {
        "accounting_equity": "272", "collateral_value": "205", "loan_value": "127.5",
        "principal_value": "60", "interest_value": "15", "cash_deficit_value": "3",
        "debt_value": "78", "risk_equity": "127", "frozen_value": "100",
        "initial_margin": "13.5", "maintenance_margin": "6.75", "available_margin": "112.25",
        "status": "HEALTHY"})
    result = stress(GROSS_DEBT, TIER_SHOCKS, floor="8", liquidity="2", credit="1")
    assert result["losses"] == {"down": Q(11), "up": Q(1)}
    assert result["units"]["down"] == {"USD": Q(0), "BTC": Q(2), "ETH": Q(9)}
    assert result["units"]["up"] == {"USD": Q(0), "BTC": Q(1), "ETH": Q(0)}
    assert result["requirement"] == 14
    checks.append("V2 stressed tier crossing: BTC loses in both directions")
    for name, raw, im, mm, available, requirement in (
            ("both", HEDGE, "32", "16", "88", "24"),
            ("remove-long", without_leg("X"), "22", "11", "98", "22"),
            ("remove-short", without_leg("Y"), "22", "11", "98", "24")):
        expect("V3 " + name, cross(raw), {"risk_equity": "120", "initial_margin": im,
               "maintenance_margin": mm, "available_margin": available})
        assert stress(raw, HEDGE_SHOCKS)["requirement"] == Q(requirement)
    for gross, equity, available, status in (("10.5", "0.5", "-0.5", "LIQUIDATION"),
                                           ("10.51", "0.51", "-0.49", "MARGIN_CALL"),
                                           ("12", "2", "0", "HEALTHY")):
        raw = boundary(gross)
        expect("V4 " + gross, cross(raw), {"risk_equity": equity, "initial_margin": "1",
               "maintenance_margin": "0.5", "available_margin": available, "status": status})
        assert not feasible_extra_loan(raw, "USD", "0.25")
    for usd, equity, status in (("0.25", "-20", "LIQUIDATION"),
                                ("20.25", "0", "LIQUIDATION"), ("20.5", "0.25", "HEALTHY")):
        expect("V5 " + usd, cross(zero_boundary(usd), zero_rates=True, full_ltv=True), {
            "risk_equity": equity, "initial_margin": "0", "maintenance_margin": "0", "status": status})
    raw = zero_boundary("20.5")
    assert feasible_extra_loan(raw, "BTC", "0.002", zero_rates=True, full_ltv=True)
    assert not feasible_extra_loan(raw, "BTC", "0.003", zero_rates=True, full_ltv=True)
    assert not feasible_extra_loan(raw, "USD", "0.25", zero_rates=True, full_ltv=True)
    assert rejection() is None
    assert rejection(mode="portfolio_margin") == rejection(mode="isolated") == "phase1_account_mode_unsupported"
    assert rejection(settlement="BTC") == rejection(quote="EUR") == "phase1_settlement_unsupported"
    assert rejection(hedges=("Y",)) == "phase1_hedge_offsets_disabled"
    checks.append("V6 mode/quote/settlement/hedge permissions table")
    return {"synthetic_only": True, "policy": "UTA-CROSS-LOAN-v1 / UTA-PRODUCT-GATE-v1",
            "oracle_imports_uta": False, "vector_groups": 6, "manual_checks": checks, "all_match": True}


if __name__ == "__main__":
    print(json.dumps(self_check(), ensure_ascii=False, sort_keys=True, indent=2))
