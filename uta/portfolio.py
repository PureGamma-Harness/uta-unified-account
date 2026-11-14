"""First-batch Cross collateral, gross loans and linear-contract margin policy.

PM and Isolated are deliberately unavailable. Stress results are a reference
calculation, never an activation switch or an order-admission authority. All
financial amounts are exact Fractions internally; only borrow quotes are rounded
down to their configured quantity step, and display ratios are half-even.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from fractions import Fraction
import json
from types import MappingProxyType
from typing import Mapping

from .market import MarketSnapshot
from .models import RiskInputError, _decimal, _identifier, _mapping
from .products import (AccountMode, ProductCatalog, ProductKind, ProductError,
                       UnsupportedProduct, _number, _object, _version, load_document)
from .products import decimal_text
from .risk import _decimal_exact


class PortfolioError(RiskInputError):
    pass


def _rate(name: str, value: Decimal) -> None:
    _decimal(name, value, minimum=Decimal(0), maximum=Decimal(1))


@dataclass(frozen=True)
class CollateralTier:
    """Marginal USD notional band; the last band must have no upper bound."""
    up_to: Decimal | None
    factor: Decimal

    def __post_init__(self) -> None:
        if self.up_to is not None:
            _decimal("tier upper notional", self.up_to, positive=True)
        _rate("collateral factor", self.factor)


@dataclass(frozen=True)
class CollateralRule:
    asset: str
    tiers: tuple[CollateralTier, ...]
    loan_to_value: Decimal

    def __post_init__(self) -> None:
        _identifier("collateral asset", self.asset)
        _rate("loan-to-value", self.loan_to_value)
        if not isinstance(self.tiers, (list, tuple)) or not 1 <= len(self.tiers) <= 64:
            raise PortfolioError("collateral requires 1..64 marginal tiers")
        previous, previous_factor = Decimal(0), Decimal(1)
        for index, tier in enumerate(self.tiers):
            if not isinstance(tier, CollateralTier):
                raise PortfolioError("invalid collateral tier")
            if tier.factor > previous_factor:
                raise PortfolioError("collateral factors must not increase across tiers")
            if tier.up_to is None:
                if index != len(self.tiers) - 1:
                    raise PortfolioError("only the final tier can be unbounded")
            elif tier.up_to <= previous:
                raise PortfolioError("tier upper bounds must strictly increase")
            else:
                previous = tier.up_to
            previous_factor = tier.factor
        if self.tiers[-1].up_to is not None:
            raise PortfolioError("final collateral tier must be unbounded")
        object.__setattr__(self, "tiers", tuple(self.tiers))

    def discounted(self, usd_notional: Fraction) -> Fraction:
        if usd_notional < 0:
            raise PortfolioError("gross collateral notional cannot be negative")
        remaining, lower, result = usd_notional, Fraction(0), Fraction(0)
        for tier in self.tiers:
            band = remaining if tier.up_to is None else min(remaining, Fraction(tier.up_to) - lower)
            result += band * Fraction(tier.factor)
            remaining -= band
            if not remaining:
                break
            lower = Fraction(tier.up_to)
        return result


@dataclass(frozen=True)
class BorrowLimits:
    asset: str
    max_principal: Decimal
    initial_margin_rate: Decimal
    maintenance_margin_rate: Decimal
    quantity_step: Decimal = Decimal("0.00000001")

    def __post_init__(self) -> None:
        _identifier("borrow asset", self.asset)
        _decimal("max principal", self.max_principal, minimum=Decimal(0))
        _decimal("borrow quantity step", self.quantity_step, positive=True)
        _rate("borrow IM rate", self.initial_margin_rate)
        _rate("borrow MM rate", self.maintenance_margin_rate)
        if self.maintenance_margin_rate > self.initial_margin_rate:
            raise PortfolioError("borrow MM rate cannot exceed IM rate")


@dataclass(frozen=True)
class LinearMarginRule:
    risk_tier: str
    initial_margin_rate: Decimal
    maintenance_margin_rate: Decimal

    def __post_init__(self) -> None:
        _identifier("risk tier", self.risk_tier)
        _rate("linear IM rate", self.initial_margin_rate)
        _rate("linear MM rate", self.maintenance_margin_rate)
        if self.initial_margin_rate <= 0 or self.maintenance_margin_rate > self.initial_margin_rate:
            raise PortfolioError("linear margin requires 0 <= MM <= IM and IM > 0")


@dataclass(frozen=True)
class LinearExposure:
    symbol: str
    quantity: Decimal
    cost_basis: Decimal  # Signed USD cost for the whole position, multiplier included.

    def __post_init__(self) -> None:
        _identifier("linear symbol", self.symbol)
        _decimal("position quantity", self.quantity)
        _decimal("position cost basis", self.cost_basis)
        if not self.quantity:
            raise PortfolioError("flat positions must be omitted")


@dataclass(frozen=True)
class LoanAccount:
    gross_assets: Mapping[str, Decimal] = field(default_factory=dict)
    principal: Mapping[str, Decimal] = field(default_factory=dict)
    interest: Mapping[str, Decimal] = field(default_factory=dict)
    frozen_assets: Mapping[str, Decimal] = field(default_factory=dict)
    positions: Mapping[str, LinearExposure] = field(default_factory=dict)
    order_margin: Decimal = Decimal(0)
    mode: AccountMode = AccountMode.CROSS

    def __post_init__(self) -> None:
        if not isinstance(self.mode, AccountMode):
            raise PortfolioError("mode must be an AccountMode")
        _decimal("order margin", self.order_margin, minimum=Decimal(0))
        for field_name in ("gross_assets", "principal", "interest", "frozen_assets"):
            amounts = _mapping(field_name, getattr(self, field_name))
            for asset, amount in amounts.items():
                _identifier("asset", asset)
                _decimal(field_name, amount, minimum=Decimal(0))
            object.__setattr__(self, field_name, MappingProxyType(amounts))
        for asset, frozen in self.frozen_assets.items():
            if frozen > self.gross_assets.get(asset, Decimal(0)):
                raise PortfolioError("frozen amount exceeds gross assets")
        positions = _mapping("positions", self.positions)
        for symbol, position in positions.items():
            if not isinstance(position, LinearExposure) or symbol != position.symbol:
                raise PortfolioError("position key must match a LinearExposure")
        object.__setattr__(self, "positions", MappingProxyType(positions))


@dataclass(frozen=True)
class PortfolioRules:
    version: int
    collaterals: Mapping[str, CollateralRule]
    borrow_limits: Mapping[str, BorrowLimits]
    linear_margin: Mapping[str, LinearMarginRule]
    max_total_debt: Decimal
    rule_id: str = "UTA-CROSS-LOAN-v1"

    def __post_init__(self) -> None:
        _version(self.version)
        _identifier("rule id", self.rule_id)
        _decimal("max total debt", self.max_total_debt, minimum=Decimal(0))
        for field_name, cls, key_name in (("collaterals", CollateralRule, "asset"),
                                          ("borrow_limits", BorrowLimits, "asset"),
                                          ("linear_margin", LinearMarginRule, "risk_tier")):
            values = _mapping(field_name, getattr(self, field_name))
            for key, value in values.items():
                if not isinstance(value, cls) or key != getattr(value, key_name):
                    raise PortfolioError(f"invalid {field_name} key/value")
            object.__setattr__(self, field_name, MappingProxyType(values))

    def to_json(self) -> str:
        return json.dumps({
            "version": self.version, "rule_id": self.rule_id, "max_total_debt": decimal_text(self.max_total_debt),
            "collaterals": {asset: {"loan_to_value": decimal_text(rule.loan_to_value),
                                     "tiers": [{"up_to": decimal_text(t.up_to) if t.up_to is not None else None,
                                                "factor": decimal_text(t.factor)} for t in rule.tiers]}
                            for asset, rule in self.collaterals.items()},
            "borrow_limits": {asset: {"max_principal": decimal_text(rule.max_principal),
                                       "initial_margin_rate": decimal_text(rule.initial_margin_rate),
                                       "maintenance_margin_rate": decimal_text(rule.maintenance_margin_rate),
                                       "quantity_step": decimal_text(rule.quantity_step)}
                              for asset, rule in self.borrow_limits.items()},
            "linear_margin": {tier: {"initial_margin_rate": decimal_text(rule.initial_margin_rate),
                                      "maintenance_margin_rate": decimal_text(rule.maintenance_margin_rate)}
                              for tier, rule in self.linear_margin.items()},
        }, sort_keys=True, separators=(",", ":"), allow_nan=False)

    @classmethod
    def from_json(cls, value: str) -> PortfolioRules:
        doc = _object(load_document(value), {"version", "rule_id", "max_total_debt", "collaterals", "borrow_limits", "linear_margin"}, "portfolio rules")
        collaterals, borrow_limits, margins = {}, {}, {}
        for asset, raw in _mapping("collaterals", doc["collaterals"]).items():
            raw = _object(raw, {"loan_to_value", "tiers"}, "collateral rule")
            if not isinstance(raw["tiers"], list) or len(raw["tiers"]) > 64:
                raise PortfolioError("tiers must be a bounded list")
            tiers = []
            for tier in raw["tiers"]:
                tier = _object(tier, {"up_to", "factor"}, "collateral tier")
                tiers.append(CollateralTier(_number(tier["up_to"], "up_to") if tier["up_to"] is not None else None,
                                            _number(tier["factor"], "factor")))
            collaterals[asset] = CollateralRule(asset, tuple(tiers), _number(raw["loan_to_value"], "loan_to_value"))
        for asset, raw in _mapping("borrow limits", doc["borrow_limits"]).items():
            raw = _object(raw, {"max_principal", "initial_margin_rate", "maintenance_margin_rate", "quantity_step"}, "borrow rule")
            borrow_limits[asset] = BorrowLimits(asset, *(_number(raw[name], name) for name in
                                                       ("max_principal", "initial_margin_rate", "maintenance_margin_rate", "quantity_step")))
        for tier, raw in _mapping("linear margin", doc["linear_margin"]).items():
            raw = _object(raw, {"initial_margin_rate", "maintenance_margin_rate"}, "linear rule")
            margins[tier] = LinearMarginRule(tier, _number(raw["initial_margin_rate"], "initial_margin_rate"),
                                             _number(raw["maintenance_margin_rate"], "maintenance_margin_rate"))
        return cls(doc["version"], collaterals, borrow_limits, margins,
                   _number(doc["max_total_debt"], "max_total_debt"), doc["rule_id"])


@dataclass(frozen=True)
class CrossRisk:
    accounting_equity: Decimal
    collateral_value: Decimal
    risk_equity: Decimal
    loan_value: Decimal
    principal_value: Decimal
    interest_value: Decimal
    debt_value: Decimal
    unrealized_pnl: Decimal
    frozen_value: Decimal
    initial_margin: Decimal
    maintenance_margin: Decimal
    order_margin: Decimal
    available_margin: Decimal
    borrowable: Mapping[str, Decimal]
    status: str
    rule_id: str
    rule_version: int
    catalog_version: int
    market_version: int
    market_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "borrowable", MappingProxyType(dict(self.borrowable)))


def _inputs(account: LoanAccount, market: MarketSnapshot, catalog: ProductCatalog,
            rules: PortfolioRules, now: datetime) -> None:
    if not isinstance(account, LoanAccount) or not isinstance(market, MarketSnapshot) or not isinstance(catalog, ProductCatalog) or not isinstance(rules, PortfolioRules):
        raise PortfolioError("risk inputs require their validated model types")
    if account.mode is not AccountMode.CROSS:
        raise UnsupportedProduct("phase1_account_mode_unsupported: Isolated and PM are disabled")
    market.validate(now=now)
    usd = market.assets.get("USD")
    if catalog.settlement_asset != "USD" or usd is None or usd.price != 1 or usd.collateral_factor != 1:
        raise UnsupportedProduct("phase1_settlement_unsupported: USD must be worth one USD without haircut")
    usd_rule = rules.collaterals.get("USD")
    if usd_rule is None or any(tier.factor != 1 for tier in usd_rule.tiers):
        raise UnsupportedProduct("phase1_settlement_unsupported: USD collateral tiers must all have factor one")


def calculate_cross_risk(account: LoanAccount, market: MarketSnapshot, catalog: ProductCatalog,
                         rules: PortfolioRules, *, now: datetime) -> CrossRisk:
    """Quote loans as if proceeds leave collateral immediately (conservative).

    This calculator has no mutation, borrowing, settlement, or order side effect.
    The service must evaluate it within the same transaction as a financial
    mutation. A quote is not authorization to borrow or withdraw.
    """
    _inputs(account, market, catalog, rules, now)
    accounting_assets = collateral = loan_value = frozen_value = Fraction(0)
    principal_value = interest_value = spot_im = spot_mm = Fraction(0)
    assets = set(account.gross_assets) | set(account.principal) | set(account.interest) | set(account.frozen_assets)
    prices = {}
    for asset in assets | set(rules.borrow_limits):
        if asset not in market.assets:
            raise PortfolioError(f"missing_price: {asset}")
        prices[asset] = Fraction(market.assets[asset].price)
    for asset in assets:
        price = prices[asset]
        gross = Fraction(account.gross_assets.get(asset, Decimal(0)))
        frozen = Fraction(account.frozen_assets.get(asset, Decimal(0)))
        accounting_assets += gross * price
        frozen_value += frozen * price
        if gross:
            rule = rules.collaterals.get(asset)
            if rule is None:
                raise PortfolioError(f"missing_collateral_rule: {asset}")
            discounted = rule.discounted((gross - frozen) * price)
            collateral += discounted
            loan_value += discounted * Fraction(rule.loan_to_value)
        principal = Fraction(account.principal.get(asset, Decimal(0))) * price
        interest = Fraction(account.interest.get(asset, Decimal(0))) * price
        principal_value += principal
        interest_value += interest
        if principal or interest:
            limit = rules.borrow_limits.get(asset)
            if limit is None:
                raise PortfolioError(f"missing_borrow_rule: {asset}")
            spot_im += (principal + interest) * Fraction(limit.initial_margin_rate)
            spot_mm += (principal + interest) * Fraction(limit.maintenance_margin_rate)
    pnl = linear_im = linear_mm = Fraction(0)
    for symbol, exposure in account.positions.items():
        product = catalog.require_risk_supported(symbol, mode=account.mode)
        if product.kind is not ProductKind.LINEAR_PERPETUAL:
            raise UnsupportedProduct("position_kind_unsupported: only linear exposures belong in positions")
        if symbol not in market.instruments:
            raise PortfolioError(f"missing_instrument_price: {symbol}")
        margin = rules.linear_margin.get(product.risk_tier)
        if margin is None:
            raise PortfolioError(f"missing_linear_margin_rule: {product.risk_tier}")
        mark = Fraction(market.instruments[symbol].mark_price)
        marked = Fraction(exposure.quantity) * Fraction(product.multiplier) * mark
        pnl += marked - Fraction(exposure.cost_basis)
        linear_im += abs(marked) * Fraction(margin.initial_margin_rate)
        linear_mm += abs(marked) * Fraction(margin.maintenance_margin_rate)
    debt = principal_value + interest_value
    accounting_equity = accounting_assets - debt + pnl
    risk_equity = collateral - debt + pnl
    im, mm = spot_im + linear_im, spot_mm + linear_mm
    available = risk_equity - im - Fraction(account.order_margin)
    borrowable = {}
    for asset, limit in rules.borrow_limits.items():
        price = prices[asset]
        maximum = max(Fraction(0), min(
            Fraction(limit.max_principal) - Fraction(account.principal.get(asset, Decimal(0))),
            (Fraction(rules.max_total_debt) - debt) / price,
            (loan_value - debt) / price,
            available / (price * (1 + Fraction(limit.initial_margin_rate))),
        ))
        step = Fraction(limit.quantity_step)
        units = maximum // step
        quote = units * step
        # IM equality can coincide with MM equality when rates are identical;
        # maintenance equality is unsafe, even for MM=0 and equity=0.
        if quote and risk_equity - quote * price <= mm + quote * price * Fraction(limit.maintenance_margin_rate):
            maintenance_cap = (risk_equity - mm) / (price * (1 + Fraction(limit.maintenance_margin_rate)))
            units = max(0, -((-maintenance_cap) // step) - 1)
            quote = min(quote, units * step)
        borrowable[asset] = _decimal_exact(quote if risk_equity > mm else Fraction(0))
    status = "LIQUIDATION" if risk_equity <= mm else "MARGIN_CALL" if available < 0 else "HEALTHY"
    return CrossRisk(*map(_decimal_exact, (accounting_equity, collateral, risk_equity, loan_value,
                                          principal_value, interest_value, debt, pnl, frozen_value, im, mm,
                                          Fraction(account.order_margin), available)),
                     borrowable, status, rules.rule_id, rules.version, catalog.version, market.version,
                     f"market-{market.version}@{market.observed_at.isoformat()}")


@dataclass(frozen=True)
class StressScenario:
    scenario_id: str
    asset_shocks: Mapping[str, Decimal]
    instrument_shocks: Mapping[str, Decimal]

    def __post_init__(self) -> None:
        _identifier("scenario id", self.scenario_id)
        for field_name in ("asset_shocks", "instrument_shocks"):
            values = _mapping(field_name, getattr(self, field_name))
            for symbol, shock in values.items():
                _identifier("shock symbol", symbol)
                _decimal("relative shock", shock, minimum=Decimal(-1), maximum=Decimal(10))
            object.__setattr__(self, field_name, MappingProxyType(values))


@dataclass(frozen=True)
class ScenarioReference:
    worst_scenario: str
    worst_loss: Decimal
    scenario_losses: Mapping[str, Decimal]
    minimum_floor: Decimal
    liquidity_addon: Decimal
    credit_addon: Decimal
    reference_requirement: Decimal
    rule_id: str
    rule_version: int
    unit_losses: Mapping[str, Mapping[str, Decimal]]
    pm_activatable: bool = field(default=False, init=False)


def scenario_reference(account: LoanAccount, market: MarketSnapshot, catalog: ProductCatalog,
                       rules: PortfolioRules, scenarios: tuple[StressScenario, ...], *, now: datetime,
                       minimum_floor: Decimal = Decimal(0), liquidity_addon: Decimal = Decimal(0),
                       credit_addon: Decimal = Decimal(0)) -> ScenarioReference:
    """Spot/depeg and linear price stress without cross-product hedge offsets.

    Volatility, term structure, inverse/option revaluation, basis, correlation
    calibration, and insurance/ADL require later-batch models and validation.
    The single reference requirement is not an IM/MM or PM implementation.
    """
    calculate_cross_risk(account, market, catalog, rules, now=now)
    if not isinstance(scenarios, (tuple, list)) or not 1 <= len(scenarios) <= 1024:
        raise PortfolioError("require 1..1024 explicit stress scenarios")
    for name, value in (("minimum floor", minimum_floor), ("liquidity addon", liquidity_addon), ("credit addon", credit_addon)):
        _decimal(name, value, minimum=Decimal(0))
    losses, unit_losses = {}, {}
    for scenario in scenarios:
        if not isinstance(scenario, StressScenario) or scenario.scenario_id in losses:
            raise PortfolioError("scenario IDs must be unique validated scenarios")
        if set(scenario.asset_shocks) - set(market.assets) or set(scenario.instrument_shocks) - set(market.instruments):
            raise PortfolioError("scenario contains an unpriced risk factor")
        if scenario.asset_shocks.get("USD", Decimal(0)) != 0:
            raise UnsupportedProduct("reporting_unit_shock_unsupported: USD is the fixed reporting unit; settlement depeg is a later-batch model")
        loss = Fraction(0)
        units = {}
        for asset in set(account.gross_assets) | set(account.principal) | set(account.interest):
            price = Fraction(market.assets[asset].price)
            shock = Fraction(scenario.asset_shocks.get(asset, Decimal(0)))
            gross = Fraction(account.gross_assets.get(asset, Decimal(0))) - Fraction(account.frozen_assets.get(asset, Decimal(0)))
            liability = Fraction(account.principal.get(asset, Decimal(0))) + Fraction(account.interest.get(asset, Decimal(0)))
            rule = rules.collaterals.get(asset)
            base = (rule.discounted(gross * price) if rule else 0) - liability * price
            stressed = (rule.discounted(gross * price * (1 + shock)) if rule else 0) - liability * price * (1 + shock)
            unit_loss = max(Fraction(0), base - stressed)
            loss += unit_loss
            units[f"collateral:{asset}"] = _decimal_exact(unit_loss)
        for symbol, position in account.positions.items():
            product = catalog.require_risk_supported(symbol)
            shock = Fraction(scenario.instrument_shocks.get(symbol, Decimal(0)))
            change = Fraction(position.quantity) * Fraction(product.multiplier) * Fraction(market.instruments[symbol].mark_price) * shock
            # Gains in other risk units do not finance this loss. Phase one has
            # no eligible-hedge policy and therefore no spot/perp PM offsets.
            unit_loss = max(Fraction(0), -change)
            loss += unit_loss
            units["linear:" + "|".join(product.risk_unit)] = _decimal_exact(unit_loss)
        losses[scenario.scenario_id] = _decimal_exact(loss)
        unit_losses[scenario.scenario_id] = MappingProxyType(units)
    worst_id = max(losses, key=lambda key: (losses[key], key))
    worst = losses[worst_id]
    requirement = _decimal_exact(max(Fraction(worst), Fraction(minimum_floor)) + Fraction(liquidity_addon) + Fraction(credit_addon))
    return ScenarioReference(worst_id, worst, MappingProxyType(losses), minimum_floor, liquidity_addon,
                             credit_addon, requirement, rules.rule_id, rules.version, MappingProxyType(unit_losses))
