"""Independent rational reserve specification; no production imports/functions.

This is a mathematical compatibility oracle, not an order-admission rule.
Signed prices/rates/overcharges remain visible rather than being clamped away.
"""
from decimal import Context, Decimal, localcontext
from fractions import Fraction


def fraction(literal):
    return Fraction(Decimal(literal))


def independent_terms(values):
    remaining = fraction(values["quantity"]) - fraction(values["filled_quantity"])
    limit, mark = fraction(values["limit_price"]), fraction(values["mark_price"])
    adverse = remaining * (limit - mark)
    if adverse < 0:
        adverse = Fraction(0)
    margin = Fraction(0)
    if not values["reduce_only"]:
        margin = abs(remaining) * (mark if mark >= limit else limit)
        margin *= fraction(values["initial_margin_rate"])
    cumulative_fee = fraction(values["fee_notional"]) + abs(remaining) * limit
    cumulative_fee *= fraction(values["fee_rate"])
    quantum_denominator = 10 ** values["usd_scale"]
    scaled = cumulative_fee * quantum_denominator
    floor, remainder = divmod(scaled.numerator, scaled.denominator)
    fee_target = Fraction(floor + int(remainder != 0), quantum_denominator)
    unpaid = fee_target - fraction(values["charged_fee"])
    return {"remaining": remaining, "margin": margin, "adverse": adverse,
            "fee_target": fee_target, "unpaid": unpaid,
            "total": margin + adverse + unpaid}


def independent_wire(value):
    if value == 0:
        return "0"
    # Exact finite input decimals and decimal fee quantization produce a
    # terminating rational. A private large context isolates ambient precision.
    required = len(str(abs(value.numerator))) + len(str(value.denominator)) + 10
    with localcontext(Context(prec=max(200, required), Emin=-999999, Emax=999999)):
        text = format(Decimal(value.numerator) / Decimal(value.denominator), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text
