"""Exact, inactive-by-default USD perpetual funding reference policy.

This module has no database, account authority, scheduler or client API. Its
rounding convention is a documented local policy, not an exchange replica.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from fractions import Fraction
from hashlib import sha256
import json
import re


class FundingError(ValueError):
    def __init__(self, code: str, message: str, status: int = 409):
        super().__init__(message)
        self.code, self.status = code, status


_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z", re.ASCII)


def name(value: str, field: str) -> str:
    if type(value) is not str or not _NAME.fullmatch(value):
        raise FundingError("funding_input", field + " must be a bounded ASCII identifier", 400)
    return value


def number(value: Decimal, field: str, *, positive=False, fractional=18,
           maximum=Decimal("1000000000000")) -> Decimal:
    if (type(value) is not Decimal or not value.is_finite()
            or len(value.as_tuple().digits) > 32
            or not -fractional <= value.as_tuple().exponent <= 12
            or value.copy_abs() > maximum or positive and value <= 0):
        raise FundingError("funding_input", field + " is outside the declared decimal bounds", 400)
    return value


def decimal_text(value: Decimal) -> str:
    if not value:
        return "0"
    result = format(value, "f")
    return result.rstrip("0").rstrip(".") if "." in result else result


def units_decimal(units: int, scale: int) -> Decimal:
    return Decimal((int(units < 0), tuple(map(int, str(abs(units)))), -scale))


def rational(value: Fraction) -> dict:
    return {"numerator": str(value.numerator), "denominator": str(value.denominator)}


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def period_time(value: datetime) -> tuple[datetime, int]:
    if (type(value) is not datetime or value.tzinfo is None
            or value.utcoffset() is None or value.microsecond):
        raise FundingError("funding_period", "period must be an aware whole-second time", 400)
    value = value.astimezone(timezone.utc)
    delta = value - datetime(1970, 1, 1, tzinfo=timezone.utc)
    seconds = delta.days * 86400 + delta.seconds
    if seconds < 0:
        raise FundingError("funding_period", "pre-epoch periods are unsupported", 400)
    return value, seconds


@dataclass(frozen=True)
class FundingPolicy:
    rule_id: str = "UTA-FUNDING-LOCAL-USD-v1"
    version: int = 1
    max_abs_rate: Decimal = Decimal("0.03")
    trigger_lateness_ms: int = 2000
    max_accounts: int = 1000

    def __post_init__(self):
        name(self.rule_id, "funding rule")
        if type(self.version) is not int or self.version != 1:
            raise FundingError("funding_policy", "only local policy version1 is implemented", 400)
        number(self.max_abs_rate, "funding cap", positive=True, maximum=Decimal(1))
        if (type(self.trigger_lateness_ms) is not int or not 1 <= self.trigger_lateness_ms <= 5000
                or type(self.max_accounts) is not int or not 1 <= self.max_accounts <= 1000):
            raise FundingError("funding_policy", "invalid bounded local policy", 400)

    def payload(self):
        return {"rule_id": self.rule_id, "version": self.version,
                "max_abs_rate": decimal_text(self.max_abs_rate),
                "trigger_lateness_ms": self.trigger_lateness_ms,
                "max_accounts": self.max_accounts,
                "cash_rounding": "TOWARD_ZERO_PER_ACCOUNT",
                "subunit_adjustment": "WAIVED_PER_PERIOD_NOT_AN_UNPAID_CUSTOMER_CLAIM",
                "rounding_ownership": "SEGREGATED_SYNTHETIC_CAPITAL_NOT_REVENUE",
                "activation": "SYNTHETIC_LOCAL_ONLY"}


@dataclass(frozen=True)
class FundingPosition:
    account_id: str
    quantity: Decimal

    def __post_init__(self):
        name(self.account_id, "account")
        number(self.quantity, "position quantity", fractional=8)
        if not self.quantity:
            raise FundingError("funding_position", "flat positions must be omitted", 400)


@dataclass(frozen=True)
class FundingLeg:
    account_id: str
    quantity: Decimal
    exact_cash: Fraction
    cash_units: int

    def payload(self, scale):
        actual = Fraction(self.cash_units, 10 ** scale)
        return {"account_id": self.account_id, "quantity": decimal_text(self.quantity),
                "exact_cash": rational(self.exact_cash), "cash_units": str(self.cash_units),
                "cash": decimal_text(units_decimal(self.cash_units, scale)),
                "waived_exact_minus_actual": rational(self.exact_cash - actual)}


@dataclass(frozen=True)
class FundingPlan:
    symbol: str
    period_end: datetime
    mark: Decimal
    rate: Decimal
    usd_scale: int
    position_digest: str
    legs: tuple[FundingLeg, ...]
    clearing_units: int

    def payload(self):
        return {"symbol": self.symbol, "period_end": self.period_end.isoformat(),
                "mark": decimal_text(self.mark), "rate": decimal_text(self.rate),
                "settlement_asset": "USD", "usd_scale": self.usd_scale,
                "position_digest": self.position_digest,
                "legs": [leg.payload(self.usd_scale) for leg in self.legs],
                "clearing_units": str(self.clearing_units),
                "required_rounding_capital_units": str(max(0, -self.clearing_units))}


def plan_funding(policy: FundingPolicy, symbol: str, period_end: datetime, *,
                 interval_seconds: int, mark: Decimal, rate: Decimal,
                 usd_scale: int, positions: tuple[FundingPosition, ...]) -> FundingPlan:
    if type(policy) is not FundingPolicy:
        raise FundingError("funding_policy", "a native validated funding policy is required", 400)
    name(symbol, "symbol")
    end, seconds = period_time(period_end)
    if (type(interval_seconds) is not int or not 1 <= interval_seconds <= 86400
            or seconds % interval_seconds):
        raise FundingError("funding_period", "period must align with the catalog interval", 400)
    number(mark, "mark", positive=True)
    number(rate, "rate", maximum=policy.max_abs_rate)
    if type(usd_scale) is not int or not 2 <= usd_scale <= 8:
        raise FundingError("funding_scale", "USD scale must be an integer 2..8", 400)
    if type(positions) is not tuple or len(positions) > policy.max_accounts:
        raise FundingError("funding_positions", "positions require a bounded native tuple", 400)
    if any(type(position) is not FundingPosition for position in positions):
        raise FundingError("funding_positions", "invalid position element", 400)
    ordered = tuple(sorted(positions, key=lambda position: position.account_id))
    if len({position.account_id for position in ordered}) != len(ordered):
        raise FundingError("funding_positions", "duplicate funding account", 400)
    if sum((Fraction(position.quantity) for position in ordered), Fraction()):
        raise FundingError("funding_unbalanced_positions", "local authority must contain both complete sides")
    legs = []
    for position in ordered:
        exact = -Fraction(position.quantity) * Fraction(mark) * Fraction(rate)
        scaled = exact * 10 ** usd_scale
        units = (abs(scaled.numerator) // scaled.denominator) * (-1 if scaled < 0 else 1)
        if abs(units) >= 10 ** 38:
            raise FundingError("funding_range", "funding exceeds ledger unit range")
        legs.append(FundingLeg(position.account_id, position.quantity, exact, units))
    digest = sha256(canonical([[position.account_id, decimal_text(position.quantity)]
                              for position in ordered]).encode()).hexdigest()
    return FundingPlan(symbol, end, mark, rate, usd_scale, digest, tuple(legs),
                       -sum(leg.cash_units for leg in legs))
