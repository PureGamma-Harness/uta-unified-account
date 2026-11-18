"""Opt-in exact decimal-coefficient Cross candidate, never an admission authority.

The existing Fraction calculator stays the service default. This module reuses
validated model types and public market/product capability gates, not reference
valuation or collateral/rounding arithmetic. No SQL, process or mutable global
cache is used. See docs/cross-decimal-kernel-candidate.md for the supported domain.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from .market import MarketSnapshot
from .models import AssetSpec, InstrumentSpec
from .portfolio import (BorrowLimits, CollateralRule, CollateralTier, CrossRisk,
                        LinearExposure, LinearMarginRule, LoanAccount,
                        PortfolioError, PortfolioRules)
from .products import AccountMode, ProductCatalog, ProductKind, ProductSpec, UnsupportedProduct


class DecimalKernelUnsupported(UnsupportedProduct):
    """Explicit reference selection is required; no automatic fallback occurs."""


# Amounts denote coefficient * 10**exponent, without ambient Decimal arithmetic.
Amount = tuple[int, int]
_ZERO: Amount = (0, 0)
_ONE: Amount = (1, 0)
_MAX_POWER = 1000
_MAX_SCALAR_CACHE = 2048


def _exact_type(value, expected, name: str) -> None:
    if type(value) is not expected:
        raise DecimalKernelUnsupported(f"decimal_kernel_model_unsupported: {name} requires exact {expected.__name__}")


class _Arithmetic:
    """Call-local bounded memoization of immutable scalar conversions/powers."""
    __slots__ = ("powers", "scalars")

    def __init__(self) -> None:
        self.powers = {0: 1}
        self.scalars: dict[Decimal, Amount] = {}

    def power(self, exponent: int) -> int:
        if not 0 <= exponent <= _MAX_POWER:
            raise DecimalKernelUnsupported("decimal_kernel_scale_unsupported")
        result = self.powers.get(exponent)
        if result is None:
            result = 10 ** exponent
            self.powers[exponent] = result
        return result

    def read(self, value: Decimal, name: str) -> Amount:
        if type(value) is not Decimal:
            if isinstance(value, Decimal):
                raise DecimalKernelUnsupported("decimal_kernel_decimal_subclass_unsupported")
            raise PortfolioError(f"{name} must be a finite Decimal")
        if not value.is_finite():
            raise PortfolioError(f"{name} must be a finite Decimal")
        sign, digits, exponent = value.as_tuple()
        if (len(digits) > 80 or abs(exponent) > 100
                or (value and abs(value.adjusted()) > 100)):
            raise PortfolioError(f"{name} exceeds supported decimal precision or exponent")
        cached = self.scalars.get(value)
        if cached is not None:
            return cached
        coefficient = 0
        for digit in digits:
            coefficient = coefficient * 10 + digit
        if not coefficient:
            result = _ZERO
        else:
            while coefficient % 10 == 0:
                coefficient //= 10
                exponent += 1
            result = (-coefficient if sign else coefficient, exponent)
        if len(self.scalars) < _MAX_SCALAR_CACHE:
            self.scalars[value] = result
        return result

    def nonnegative(self, value: Decimal, name: str) -> Amount:
        result = self.read(value, name)
        if result[0] < 0:
            raise PortfolioError(f"{name} must be >= 0")
        return result

    def positive(self, value: Decimal, name: str) -> Amount:
        result = self.read(value, name)
        if result[0] <= 0:
            raise PortfolioError(f"{name} must be positive")
        return result

    def rate(self, value: Decimal, name: str) -> Amount:
        result = self.nonnegative(value, name)
        if self.compare(result, _ONE) > 0:
            raise PortfolioError(f"{name} must be <= 1")
        return result

    @staticmethod
    def negative(value: Amount) -> Amount:
        return (-value[0], value[1]) if value[0] else _ZERO

    @staticmethod
    def absolute(value: Amount) -> Amount:
        return (abs(value[0]), value[1]) if value[0] else _ZERO

    def add(self, left: Amount, right: Amount) -> Amount:
        if not left[0]:
            return right
        if not right[0]:
            return left
        exponent = min(left[1], right[1])
        coefficient = (left[0] * self.power(left[1] - exponent)
                       + right[0] * self.power(right[1] - exponent))
        return (coefficient, exponent) if coefficient else _ZERO

    def subtract(self, left: Amount, right: Amount) -> Amount:
        return self.add(left, self.negative(right))

    @staticmethod
    def multiply(left: Amount, right: Amount) -> Amount:
        if not left[0] or not right[0]:
            return _ZERO
        return (left[0] * right[0], left[1] + right[1])

    def compare(self, left: Amount, right: Amount) -> int:
        difference = self.subtract(left, right)[0]
        return (difference > 0) - (difference < 0)

    def floor_ratio(self, numerator: Amount, denominator: Amount) -> int:
        if denominator[0] <= 0:
            raise PortfolioError("decimal kernel requires a positive denominator")
        shift = numerator[1] - denominator[1]
        if shift >= 0:
            return numerator[0] * self.power(shift) // denominator[0]
        return numerator[0] // (denominator[0] * self.power(-shift))

    def ceiling_ratio(self, numerator: Amount, denominator: Amount) -> int:
        return -self.floor_ratio(self.negative(numerator), denominator)

    def decimal(self, value: Amount) -> Decimal:
        coefficient, exponent = value
        if not coefficient:
            return Decimal(0)
        if exponent > 0:
            coefficient *= self.power(exponent)
            exponent = 0
        while exponent < 0 and coefficient % 10 == 0:
            coefficient //= 10
            exponent += 1
        return Decimal((int(coefficient < 0), tuple(map(int, str(abs(coefficient)))), exponent))


def _discounted(arithmetic: _Arithmetic, rule: CollateralRule, notional: Amount) -> Amount:
    _exact_type(rule, CollateralRule, "collateral rule")
    if notional[0] < 0:
        raise PortfolioError("gross collateral notional cannot be negative")
    remaining, lower, result = notional, _ZERO, _ZERO
    for tier in rule.tiers:
        _exact_type(tier, CollateralTier, "collateral tier")
        factor = arithmetic.rate(tier.factor, "collateral factor")
        if tier.up_to is None:
            band = remaining
        else:
            upper = arithmetic.positive(tier.up_to, "tier upper notional")
            width = arithmetic.subtract(upper, lower)
            band = remaining if arithmetic.compare(remaining, width) <= 0 else width
        result = arithmetic.add(result, arithmetic.multiply(band, factor))
        remaining = arithmetic.subtract(remaining, band)
        if not remaining[0]:
            break
        if tier.up_to is not None:
            lower = upper
    return result


def calculate_cross_risk_decimal(account: LoanAccount, market: MarketSnapshot,
                                 catalog: ProductCatalog, rules: PortfolioRules, *,
                                 now: datetime, max_age: timedelta = timedelta(seconds=5)) -> CrossRisk:
    """Exact pure Cross quote candidate; never mutate or authorize an account.

    Exact classes/finite bounded Decimal models are the explicit specialization.
    Unsupported specializations raise; there is no automatic reference fallback.
    """
    for value, expected, name in ((account, LoanAccount, "account"),
                                  (market, MarketSnapshot, "market"),
                                  (catalog, ProductCatalog, "catalog"),
                                  (rules, PortfolioRules, "rules")):
        _exact_type(value, expected, name)
    if account.mode is not AccountMode.CROSS:
        raise UnsupportedProduct("phase1_account_mode_unsupported: Isolated and PM are disabled")
    market.validate(now=now, max_age=max_age)
    arithmetic = _Arithmetic()
    usd = market.assets.get("USD")
    if usd is not None:
        _exact_type(usd, AssetSpec, "USD price")
    if (catalog.settlement_asset != "USD" or usd is None
            or arithmetic.compare(arithmetic.positive(usd.price, "USD price"), _ONE) != 0
            or arithmetic.compare(arithmetic.rate(usd.collateral_factor, "USD collateral factor"), _ONE) != 0):
        raise UnsupportedProduct("phase1_settlement_unsupported: USD must be worth one USD without haircut")
    usd_rule = rules.collaterals.get("USD")
    if usd_rule is None:
        raise UnsupportedProduct("phase1_settlement_unsupported: USD collateral tiers must all have factor one")
    _exact_type(usd_rule, CollateralRule, "USD collateral rule")
    for tier in usd_rule.tiers:
        _exact_type(tier, CollateralTier, "USD collateral tier")
        if arithmetic.compare(arithmetic.rate(tier.factor, "USD collateral factor"), _ONE) != 0:
            raise UnsupportedProduct("phase1_settlement_unsupported: USD collateral tiers must all have factor one")
    assets = (set(account.gross_assets) | set(account.principal) | set(account.interest)
              | set(account.frozen_assets) | set(account.cash_deficits))
    prices = {}
    for asset in sorted(assets | set(rules.borrow_limits)):
        spec = market.assets.get(asset)
        if spec is None:
            raise PortfolioError(f"missing_price: {asset}")
        _exact_type(spec, AssetSpec, "asset price")
        prices[asset] = arithmetic.positive(spec.price, "asset price")
    accounting_assets = collateral = loan_value = frozen_value = _ZERO
    principal_value = interest_value = cash_deficit_value = spot_im = spot_mm = _ZERO
    for asset in sorted(assets):
        price = prices[asset]
        gross = arithmetic.nonnegative(account.gross_assets.get(asset, Decimal(0)), "gross assets")
        frozen = arithmetic.nonnegative(account.frozen_assets.get(asset, Decimal(0)), "frozen assets")
        accounting_assets = arithmetic.add(accounting_assets, arithmetic.multiply(gross, price))
        frozen_value = arithmetic.add(frozen_value, arithmetic.multiply(frozen, price))
        if gross[0]:
            rule = rules.collaterals.get(asset)
            if rule is None:
                raise PortfolioError(f"missing_collateral_rule: {asset}")
            discounted = _discounted(arithmetic, rule, arithmetic.multiply(arithmetic.subtract(gross, frozen), price))
            collateral = arithmetic.add(collateral, discounted)
            loan_value = arithmetic.add(loan_value, arithmetic.multiply(discounted, arithmetic.rate(rule.loan_to_value, "loan-to-value")))
        principal = arithmetic.multiply(arithmetic.nonnegative(account.principal.get(asset, Decimal(0)), "principal"), price)
        interest = arithmetic.multiply(arithmetic.nonnegative(account.interest.get(asset, Decimal(0)), "interest"), price)
        principal_value = arithmetic.add(principal_value, principal)
        interest_value = arithmetic.add(interest_value, interest)
        cash_deficit_value = arithmetic.add(cash_deficit_value, arithmetic.multiply(
            arithmetic.nonnegative(account.cash_deficits.get(asset, Decimal(0)), "cash deficit"), price))
        if principal[0] or interest[0]:
            limit = rules.borrow_limits.get(asset)
            if limit is None:
                raise PortfolioError(f"missing_borrow_rule: {asset}")
            _exact_type(limit, BorrowLimits, "borrow rule")
            liability = arithmetic.add(principal, interest)
            spot_im = arithmetic.add(spot_im, arithmetic.multiply(liability, arithmetic.rate(limit.initial_margin_rate, "borrow IM rate")))
            spot_mm = arithmetic.add(spot_mm, arithmetic.multiply(liability, arithmetic.rate(limit.maintenance_margin_rate, "borrow MM rate")))

    pnl = linear_im = linear_mm = _ZERO
    for symbol, exposure in account.positions.items():
        _exact_type(exposure, LinearExposure, "linear exposure")
        product = catalog.require_risk_supported(symbol, mode=account.mode)
        _exact_type(product, ProductSpec, "product")
        if product.kind is not ProductKind.LINEAR_PERPETUAL:
            raise UnsupportedProduct("position_kind_unsupported: only linear exposures belong in positions")
        instrument = market.instruments.get(symbol)
        if instrument is None:
            raise PortfolioError(f"missing_instrument_price: {symbol}")
        _exact_type(instrument, InstrumentSpec, "instrument")
        margin = rules.linear_margin.get(product.risk_tier)
        if margin is None:
            raise PortfolioError(f"missing_linear_margin_rule: {product.risk_tier}")
        _exact_type(margin, LinearMarginRule, "linear margin rule")
        marked = arithmetic.multiply(arithmetic.multiply(arithmetic.read(exposure.quantity, "position quantity"),
                    arithmetic.positive(product.multiplier, "contract multiplier")),
                    arithmetic.positive(instrument.mark_price, "mark price"))
        pnl = arithmetic.add(pnl, arithmetic.subtract(marked, arithmetic.read(exposure.cost_basis, "position cost basis")))
        notional = arithmetic.absolute(marked)
        linear_im = arithmetic.add(linear_im, arithmetic.multiply(notional, arithmetic.rate(margin.initial_margin_rate, "linear IM rate")))
        linear_mm = arithmetic.add(linear_mm, arithmetic.multiply(notional, arithmetic.rate(margin.maintenance_margin_rate, "linear MM rate")))

    debt = arithmetic.add(arithmetic.add(principal_value, interest_value), cash_deficit_value)
    accounting_equity = arithmetic.add(arithmetic.subtract(accounting_assets, debt), pnl)
    risk_equity = arithmetic.add(arithmetic.subtract(collateral, debt), pnl)
    im, mm = arithmetic.add(spot_im, linear_im), arithmetic.add(spot_mm, linear_mm)
    order_margin = arithmetic.nonnegative(account.order_margin, "order margin")
    available = arithmetic.subtract(arithmetic.subtract(risk_equity, im), order_margin)
    total_debt_limit = arithmetic.nonnegative(rules.max_total_debt, "max total debt")
    borrowable = {}
    for asset, limit in rules.borrow_limits.items():
        _exact_type(limit, BorrowLimits, "borrow rule")
        price = prices[asset]
        step = arithmetic.positive(limit.quantity_step, "borrow quantity step")
        im_rate = arithmetic.rate(limit.initial_margin_rate, "borrow IM rate")
        mm_rate = arithmetic.rate(limit.maintenance_margin_rate, "borrow MM rate")
        denominator = arithmetic.multiply(price, step)
        units = max(0, min(
            arithmetic.floor_ratio(arithmetic.subtract(arithmetic.nonnegative(limit.max_principal, "max principal"),
                arithmetic.nonnegative(account.principal.get(asset, Decimal(0)), "principal")), step),
            arithmetic.floor_ratio(arithmetic.subtract(total_debt_limit, debt), denominator),
            arithmetic.floor_ratio(arithmetic.subtract(loan_value, debt), denominator),
            arithmetic.floor_ratio(available, arithmetic.multiply(denominator, arithmetic.add(_ONE, im_rate))),
        ))
        quote = arithmetic.multiply((units, 0), step)
        quote_value = arithmetic.multiply(quote, price)
        if quote[0] and arithmetic.compare(arithmetic.subtract(risk_equity, quote_value),
                arithmetic.add(mm, arithmetic.multiply(quote_value, mm_rate))) <= 0:
            strict_units = max(0, arithmetic.ceiling_ratio(arithmetic.subtract(risk_equity, mm),
                arithmetic.multiply(denominator, arithmetic.add(_ONE, mm_rate))) - 1)
            units = min(units, strict_units)
            quote = arithmetic.multiply((units, 0), step)
        borrowable[asset] = arithmetic.decimal(quote if arithmetic.compare(risk_equity, mm) > 0 else _ZERO)
    status = ("LIQUIDATION" if arithmetic.compare(risk_equity, mm) <= 0 else
              "MARGIN_CALL" if available[0] < 0 else "HEALTHY")
    values = (accounting_equity, collateral, risk_equity, loan_value, principal_value,
              interest_value, debt, pnl, frozen_value, im, mm, order_margin, available)
    return CrossRisk(*(arithmetic.decimal(value) for value in values), borrowable, status,
        rules.rule_id, rules.version, catalog.version, market.version,
        f"market-{market.version}@{market.observed_at.isoformat()}", arithmetic.decimal(cash_deficit_value))
