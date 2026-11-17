"""Wire-only correction to the frozen independent mathematical oracle.

The Fraction value and expected Decimal tuple are unchanged. Decimal.__str__
uses scientific notation for sufficiently small adjusted exponents. Fixed-point
formatting is an exact value description, but is not that existing wire rule.
No production conversion function is imported or called here.
"""
from decimal import Decimal


def canonical_wire_from_expected_tuple(expected_tuple):
    return str(Decimal(expected_tuple))
