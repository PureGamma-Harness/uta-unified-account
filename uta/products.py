"""Versioned product metadata and explicit first-batch capability gates.

These are this project's policies, not a reproduction of an exchange's rules.
Listing a future product in a catalog never activates its execution capability.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from fractions import Fraction
import json
import re
from types import MappingProxyType
from typing import Mapping

from .models import RiskInputError, _decimal, _identifier, _mapping


class ProductError(RiskInputError):
    pass


class UnsupportedProduct(ProductError):
    pass


class AccountMode(str, Enum):
    ISOLATED = "isolated"
    CROSS = "cross"
    PM = "portfolio_margin"


class ProductKind(str, Enum):
    SPOT = "spot"
    SPOT_MARGIN = "spot_margin"
    LINEAR_PERPETUAL = "linear_perpetual"
    INVERSE_PERPETUAL = "inverse_perpetual"
    DATED_FUTURE = "dated_future"
    OPTION = "option"


class TradingStatus(str, Enum):
    ACTIVE = "active"
    HALTED = "halted"
    CANCEL_ONLY = "cancel_only"
    REDUCE_ONLY = "reduce_only"
    DELISTED = "delisted"
    DISABLED = "disabled"


def _version(value: int) -> None:
    if type(value) is not int or not 0 <= value <= 2**63 - 1:
        raise ProductError("version must be an integer in 0..2^63-1")


def _object(value, fields: set[str], name: str) -> dict:
    if not isinstance(value, dict) or set(value) != fields:
        raise ProductError(f"{name} fields must be exactly {', '.join(sorted(fields))}")
    return value


def _number(value, name: str) -> Decimal:
    if (not isinstance(value, str) or not 1 <= len(value) <= 128
            or not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", value)):
        raise ProductError(f"{name} must be a bounded decimal string")
    try:
        result = Decimal(value)
    except ArithmeticError as exc:
        raise ProductError(f"invalid {name}") from exc
    _decimal(name, result)
    return result


def decimal_text(value: Decimal) -> str:
    """Canonical numeric spelling without caller-context rounding."""
    if not value:
        return "0"
    sign, digits, exponent = value.as_tuple()
    digits = list(digits)
    while digits[-1] == 0:
        digits.pop()
        exponent += 1
    return str(Decimal((sign, tuple(digits), exponent)))


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProductError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def load_document(value: str):
    if not isinstance(value, str) or len(value) > 1024 * 1024:
        raise ProductError("document must be a JSON string of at most 1 MiB")
    def reject_constant(_):
        raise ProductError("nonstandard JSON constants are forbidden")
    try:
        return json.loads(value, object_pairs_hook=_pairs, parse_constant=reject_constant)
    except (ValueError, RecursionError) as exc:
        raise ProductError("invalid JSON document") from exc


@dataclass(frozen=True)
class ProductSpec:
    symbol: str
    kind: ProductKind
    underlying: str
    quote_asset: str
    settlement_asset: str
    price_tick: Decimal
    quantity_step: Decimal
    min_notional: Decimal
    multiplier: Decimal = Decimal(1)
    risk_tier: str = "tier-1"
    expiry: datetime | None = None
    funding_interval_seconds: int | None = None
    status: TradingStatus = TradingStatus.DISABLED
    eligible_hedges: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("symbol", "underlying", "quote_asset", "settlement_asset", "risk_tier"):
            _identifier(name, getattr(self, name))
        if not isinstance(self.kind, ProductKind) or not isinstance(self.status, TradingStatus):
            raise ProductError("kind and status require their explicit enums")
        for name in ("price_tick", "quantity_step", "multiplier"):
            _decimal(name, getattr(self, name), positive=True)
        _decimal("min_notional", self.min_notional, minimum=Decimal(0))
        if self.expiry is not None:
            if not isinstance(self.expiry, datetime) or self.expiry.tzinfo is None or self.expiry.utcoffset() is None:
                raise ProductError("expiry must be timezone-aware")
            object.__setattr__(self, "expiry", self.expiry.astimezone(timezone.utc))
        if self.kind in (ProductKind.DATED_FUTURE, ProductKind.OPTION) and self.expiry is None:
            raise ProductError("dated products require expiry metadata")
        if self.kind not in (ProductKind.DATED_FUTURE, ProductKind.OPTION) and self.expiry is not None:
            raise ProductError("undated products cannot have an expiry")
        if (self.funding_interval_seconds is not None and
                (type(self.funding_interval_seconds) is not int or not 1 <= self.funding_interval_seconds <= 604800)):
            raise ProductError("funding interval must be an integer in 1..604800 seconds")
        if self.funding_interval_seconds is not None and self.kind not in (ProductKind.LINEAR_PERPETUAL, ProductKind.INVERSE_PERPETUAL):
            raise ProductError("only perpetual products can have a funding interval")
        if not isinstance(self.eligible_hedges, (tuple, list)) or len(self.eligible_hedges) > 64:
            raise ProductError("eligible_hedges must be a bounded sequence")
        for symbol in self.eligible_hedges:
            _identifier("eligible hedge", symbol)
        if len(set(self.eligible_hedges)) != len(self.eligible_hedges):
            raise ProductError("duplicate eligible hedge")
        object.__setattr__(self, "eligible_hedges", tuple(self.eligible_hedges))

    @property
    def risk_unit(self) -> tuple[str, ...]:
        # Symbols remain separate until a separately validated hedge policy is
        # activated. Shared underlying alone never grants an offset.
        return (self.underlying, self.kind.value,
                self.expiry.isoformat() if self.expiry else "perpetual-or-spot",
                self.settlement_asset, self.symbol)


@dataclass(frozen=True)
class ProductCatalog:
    version: int
    products: Mapping[str, ProductSpec]
    settlement_asset: str = "USD"

    def __post_init__(self) -> None:
        _version(self.version)
        _identifier("settlement asset", self.settlement_asset)
        products = _mapping("catalog products", self.products)
        if not products:
            raise ProductError("catalog requires at least one product")
        for symbol, product in products.items():
            if not isinstance(product, ProductSpec) or symbol != product.symbol:
                raise ProductError("catalog key must match a ProductSpec symbol")
        object.__setattr__(self, "products", MappingProxyType(products))

    def require_supported(self, symbol: str, *, mode: AccountMode = AccountMode.CROSS,
                          reduce_only: bool = False) -> ProductSpec:
        product = self.require_risk_supported(symbol, mode=mode)
        if type(reduce_only) is not bool:
            raise ProductError("reduce_only must be a boolean")
        if product.status is TradingStatus.REDUCE_ONLY and reduce_only:
            return product
        if product.status is not TradingStatus.ACTIVE:
            raise UnsupportedProduct(f"product_not_active: {product.status.value}")
        return product

    def require_risk_supported(self, symbol: str, *, mode: AccountMode = AccountMode.CROSS) -> ProductSpec:
        """Value an existing supported exposure even when trading is halted."""
        if mode is not AccountMode.CROSS:
            raise UnsupportedProduct("phase1_account_mode_unsupported: only Cross is enabled; Isolated and PM are disabled")
        _identifier("symbol", symbol)
        product = self.products.get(symbol)
        if product is None:
            raise UnsupportedProduct("product_not_listed")
        if product.kind not in (ProductKind.SPOT, ProductKind.SPOT_MARGIN, ProductKind.LINEAR_PERPETUAL):
            raise UnsupportedProduct(f"phase1_product_unsupported: {product.kind.value}")
        if self.settlement_asset != "USD" or product.settlement_asset != "USD" or product.quote_asset != "USD":
            raise UnsupportedProduct("phase1_settlement_unsupported: quote and settlement must both be USD")
        if product.eligible_hedges:
            raise UnsupportedProduct("phase1_hedge_offsets_disabled")
        return product

    def check_order(self, symbol: str, quantity: Decimal, price: Decimal, *,
                    mode: AccountMode = AccountMode.CROSS, reduce_only: bool = False) -> ProductSpec:
        product = self.require_supported(symbol, mode=mode, reduce_only=reduce_only)
        _decimal("quantity", quantity)
        _decimal("price", price, positive=True)
        if not quantity:
            raise ProductError("quantity must be nonzero")
        if (Fraction(quantity) / Fraction(product.quantity_step)).denominator != 1:
            raise ProductError("quantity_step_violation")
        if (Fraction(price) / Fraction(product.price_tick)).denominator != 1:
            raise ProductError("price_tick_violation")
        if abs(Fraction(quantity)) * Fraction(price) * Fraction(product.multiplier) < Fraction(product.min_notional):
            raise ProductError("minimum_notional_violation")
        return product

    def to_json(self) -> str:
        products = {}
        for symbol, p in self.products.items():
            products[symbol] = {
                "kind": p.kind.value, "underlying": p.underlying, "quote_asset": p.quote_asset,
                "settlement_asset": p.settlement_asset, "price_tick": decimal_text(p.price_tick),
                "quantity_step": decimal_text(p.quantity_step), "min_notional": decimal_text(p.min_notional),
                "multiplier": decimal_text(p.multiplier), "risk_tier": p.risk_tier,
                "expiry": p.expiry.isoformat() if p.expiry else None,
                "funding_interval_seconds": p.funding_interval_seconds,
                "status": p.status.value, "eligible_hedges": list(p.eligible_hedges),
            }
        return json.dumps({"version": self.version, "settlement_asset": self.settlement_asset,
                           "products": products}, sort_keys=True, separators=(",", ":"), allow_nan=False)

    @classmethod
    def from_json(cls, value: str) -> ProductCatalog:
        doc = _object(load_document(value), {"version", "settlement_asset", "products"}, "catalog")
        products = {}
        for symbol, raw in _mapping("catalog products", doc["products"]).items():
            p = _object(raw, {"kind", "underlying", "quote_asset", "settlement_asset", "price_tick",
                              "quantity_step", "min_notional", "multiplier", "risk_tier", "expiry",
                              "funding_interval_seconds", "status", "eligible_hedges"}, "product")
            try:
                kind, status = ProductKind(p["kind"]), TradingStatus(p["status"])
                expiry = datetime.fromisoformat(p["expiry"].replace("Z", "+00:00")) if isinstance(p["expiry"], str) else None
            except (ValueError, TypeError) as exc:
                raise ProductError("invalid product enum or expiry") from exc
            if p["expiry"] is not None and not isinstance(p["expiry"], str):
                raise ProductError("expiry must be a timestamp string or null")
            products[symbol] = ProductSpec(symbol, kind, p["underlying"], p["quote_asset"], p["settlement_asset"],
                                           _number(p["price_tick"], "price_tick"), _number(p["quantity_step"], "quantity_step"),
                                           _number(p["min_notional"], "min_notional"), _number(p["multiplier"], "multiplier"),
                                           p["risk_tier"], expiry, p["funding_interval_seconds"], status, p["eligible_hedges"])
        return cls(doc["version"], products, doc["settlement_asset"])
