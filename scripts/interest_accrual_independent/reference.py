"""Independent exact simple-interest oracle, not a financial scheduler.

Expected values come from the accompanying manually authored rational cases.
This module imports no production module and uses Fraction rates/time ratios,
rather than the candidate's fixed-denominator integer transition function.
"""
from dataclasses import dataclass
from fractions import Fraction


RATE_SCALE = 10**9
DAY_NS = 86_400 * 10**9
YEAR_NS = 365 * DAY_NS
DENOMINATOR = YEAR_NS * RATE_SCALE
MAX_UNITS_EXCLUSIVE = 10**38
MAX_TIMESTAMP = 2**63 - 1


class ReferenceRefusal(ValueError):
    pass


def exact_integer(value, name, lower, upper):
    if type(value) is not int or not lower <= value <= upper:
        raise ReferenceRefusal(name)


@dataclass(frozen=True)
class Observation:
    exact_total_units: Fraction
    booked_units: int
    remaining_fraction: Fraction
    extra_risk_reserve_units: int


def observe(segments, *, prior_booked=0, prior_fraction=Fraction(0)):
    """Sum noncompounding principal/rate/time segments in minimum asset units.

    Segment tuples are (principal_units, annual_ppb, duration_ns). This oracle
    intentionally omits command-ID/CAS storage and authoritative event timing.
    """
    exact_integer(prior_booked, "booked", 0, MAX_UNITS_EXCLUSIVE - 1)
    if type(prior_fraction) is not Fraction or not 0 <= prior_fraction < 1:
        raise ReferenceRefusal("carry_fraction")
    total = Fraction(prior_booked) + prior_fraction
    if prior_booked + int(prior_fraction > 0) >= MAX_UNITS_EXCLUSIVE:
        raise ReferenceRefusal("units_limit")
    for principal, ppb, elapsed in segments:
        exact_integer(principal, "principal", 0, MAX_UNITS_EXCLUSIVE - 1)
        exact_integer(ppb, "annual_rate", 0, RATE_SCALE)
        exact_integer(elapsed, "duration", 1, 366 * DAY_NS)
        interest = Fraction(principal) * Fraction(ppb, RATE_SCALE) * Fraction(elapsed, YEAR_NS)
        total += interest
        # The public integer and risk representations have exclusive limits;
        # exact arithmetic itself is not permission to exceed those bounds.
        floor = total.numerator // total.denominator
        fraction = total - floor
        if floor + int(fraction > 0) >= MAX_UNITS_EXCLUSIVE:
            raise ReferenceRefusal("units_limit")
    booked = total.numerator // total.denominator
    remaining = total - booked
    return Observation(total, booked, remaining, int(remaining > 0))


def carry_as_native_numerator(fraction):
    """Convert an independent result to the specified common denominator."""
    scaled = fraction * DENOMINATOR
    if scaled.denominator != 1:
        raise ReferenceRefusal("carry_not_representable")
    return scaled.numerator
