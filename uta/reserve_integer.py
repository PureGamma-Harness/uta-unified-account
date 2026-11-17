"""Experimental decimal-integer reserve arithmetic, without financial authority.

The service and ReserveKernel still use the original Fraction implementation.
This alternative has a deliberately small fast domain and delegates every other
input to that unchanged implementation. Neither path checks product admission,
market freshness, account balances, order direction or durable reservations.
"""
from decimal import Decimal

from .reserve_kernel import ReserveInputs, calculate_reserve


_FIELDS = ("quantity", "filled_quantity", "limit_price", "mark_price",
           "initial_margin_rate", "fee_notional", "charged_fee", "fee_rate")
MAX_DIGITS = 38
MAX_EXPONENT = 18


def _parts(value):
    if type(value) is not Decimal or not value.is_finite():
        return None
    sign, digits, exponent = value.as_tuple()
    if len(digits) > MAX_DIGITS or abs(exponent) > MAX_EXPONENT:
        return None
    coefficient = 0
    for digit in digits:
        coefficient = coefficient * 10 + digit
    if sign:
        coefficient = -coefficient
    if exponent > 0:
        return coefficient * 10**exponent, 0
    return coefficient, -exponent


def _at(value, scale):
    coefficient, original_scale = value
    return coefficient * 10**(scale - original_scale)


def _decimal(coefficient, scale):
    # Match the reduced terminating-Fraction representation, including zero's
    # exponent; Decimal.normalize() would consult the ambient precision.
    while scale and coefficient % 10 == 0:
        coefficient //= 10
        scale -= 1
    return Decimal((int(coefficient < 0), tuple(map(int, str(abs(coefficient)))), -scale))


def calculate_integer_reserve(inputs: ReserveInputs) -> Decimal:
    """Evaluate the reference expression with integer decimal coefficients.

    Finite, exact Decimal inputs have at most38 coefficient digits and exponents
    in[-18,18]; the settlement scale is an exact int in[0,18]. Other inputs take
    the reference path, preserving its values and exception behavior. All
    arithmetic remains exact: signed adverse loss, non-reduce-only IM and the
    unpaid cumulative fee ceiling are aggregated before decimal conversion.
    """
    if not isinstance(inputs, ReserveInputs):
        # Preserve duck-typed callers of the original standalone expression.
        return calculate_reserve(inputs)
    if type(inputs.usd_scale) is not int or not 0 <= inputs.usd_scale <= 18:
        return calculate_reserve(inputs)
    parts = [_parts(getattr(inputs, name)) for name in _FIELDS]
    if any(value is None for value in parts):
        return calculate_reserve(inputs)
    quantity, filled, limit, mark, margin_rate, fee_notional, charged, fee_rate = parts
    quantity_scale, price_scale = max(quantity[1], filled[1]), max(limit[1], mark[1])
    remaining = _at(quantity, quantity_scale) - _at(filled, quantity_scale)
    limit_units, mark_units = _at(limit, price_scale), _at(mark, price_scale)
    notional_scale = quantity_scale + price_scale
    loss = max(0, remaining * (limit_units - mark_units))
    margin = (0 if inputs.reduce_only else
              abs(remaining) * max(mark_units, limit_units) * margin_rate[0])
    margin_scale = notional_scale + margin_rate[1]
    fee_base_scale = max(fee_notional[1], notional_scale)
    fee_base = (_at(fee_notional, fee_base_scale)
                + abs(remaining) * limit_units * 10**(fee_base_scale - notional_scale))
    fee_numerator = fee_base * fee_rate[0] * 10**inputs.usd_scale
    fee_denominator = 10**(fee_base_scale + fee_rate[1])
    fee_units = -(-fee_numerator // fee_denominator)
    scale = max(notional_scale, margin_scale, inputs.usd_scale, charged[1])
    total = (loss * 10**(scale - notional_scale)
             + margin * 10**(scale - margin_scale)
             + fee_units * 10**(scale - inputs.usd_scale)
             - _at(charged, scale))
    return _decimal(total, scale)
