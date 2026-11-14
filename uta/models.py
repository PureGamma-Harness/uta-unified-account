"""Small, explicit data model for the reference UTA risk engine.

Amounts are Decimal, quote-denominated risk is in a single USD reporting unit.
The caller is responsible for supplying trusted, current prices and rates.
"""
from dataclasses import dataclass, field
from decimal import Decimal
import re
from types import MappingProxyType
from typing import Mapping


class RiskInputError(ValueError):
    """Missing, malformed, or economically invalid risk input."""


def _identifier(name: str, value: str) -> None:
    """Bound identifiers before they become database keys or audit fields."""
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}", value):
        raise RiskInputError(f"{name} must be a valid identifier of 1..128 ASCII characters")


def _mapping(name: str, value: Mapping) -> dict:
    if not isinstance(value, Mapping) or len(value) > 4096:
        raise RiskInputError(f"{name} must be a mapping with at most 4096 entries")
    return dict(value)


def _decimal(name: str, value: Decimal, *, minimum: Decimal | None = None,
             maximum: Decimal | None = None, positive: bool = False) -> None:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise RiskInputError(f"{name} must be a finite Decimal")
    if (len(value.as_tuple().digits) > 80 or abs(value.as_tuple().exponent) > 100
            or (value and abs(value.adjusted()) > 100)):
        raise RiskInputError(f"{name} exceeds supported decimal precision or exponent")
    if positive and value <= 0:
        raise RiskInputError(f"{name} must be positive")
    if minimum is not None and value < minimum:
        raise RiskInputError(f"{name} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise RiskInputError(f"{name} must be <= {maximum}")


@dataclass(frozen=True)
class AssetSpec:
    """USD mark and collateral factor. Borrowed assets are never haircutted."""
    price: Decimal
    collateral_factor: Decimal

    def __post_init__(self) -> None:
        _decimal("asset price", self.price, positive=True)
        _decimal("collateral factor", self.collateral_factor,
                 minimum=Decimal(0), maximum=Decimal(1))


@dataclass(frozen=True)
class InstrumentSpec:
    """Linear USD-settled perpetual: mark price, IM and MM rates."""
    mark_price: Decimal
    initial_margin_rate: Decimal
    maintenance_margin_rate: Decimal

    def __post_init__(self) -> None:
        _decimal("mark price", self.mark_price, positive=True)
        _decimal("initial margin rate", self.initial_margin_rate,
                 minimum=Decimal(0), maximum=Decimal(1))
        _decimal("maintenance margin rate", self.maintenance_margin_rate,
                 minimum=Decimal(0), maximum=Decimal(1))
        if self.maintenance_margin_rate > self.initial_margin_rate:
            raise RiskInputError("maintenance margin rate exceeds initial margin rate")


@dataclass(frozen=True)
class Position:
    """Signed base units and average entry price for a linear instrument."""
    symbol: str
    quantity: Decimal
    entry_price: Decimal

    def __post_init__(self) -> None:
        _identifier("position symbol", self.symbol)
        _decimal("position quantity", self.quantity)
        _decimal("entry price", self.entry_price, positive=True)


@dataclass(frozen=True)
class Account:
    """Balances, separate gross liabilities, net positions and order reserves.

    Positive balances are gross collateral assets. Negative balances are a legacy
    liability shorthand. ``liabilities`` contains additional gross nonnegative
    borrow/interest amounts; a given asset cannot use negative balance and a
    positive explicit liability together because that input is ambiguous.
    Separate liabilities allow same-asset asset/borrow exposure without netting
    before the collateral haircut. Positions are keyed by symbol.
    """
    balances: Mapping[str, Decimal] = field(default_factory=dict)
    positions: Mapping[str, Position] = field(default_factory=dict)
    open_order_margin: Decimal = Decimal(0)
    liabilities: Mapping[str, Decimal] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _decimal("open order margin", self.open_order_margin, minimum=Decimal(0))
        balances = _mapping("balances", self.balances)
        liabilities = _mapping("liabilities", self.liabilities)
        positions = _mapping("positions", self.positions)
        for asset, amount in balances.items():
            _identifier("asset", asset)
            _decimal(f"balance for {asset}", amount)
        for asset, amount in liabilities.items():
            _identifier("liability asset", asset)
            _decimal(f"liability for {asset}", amount, minimum=Decimal(0))
            if amount > 0 and balances.get(asset, Decimal(0)) < 0:
                raise RiskInputError(f"ambiguous duplicate liability for {asset}")
        for symbol, position in positions.items():
            _identifier("position key", symbol)
            if not isinstance(position, Position) or symbol != position.symbol:
                raise RiskInputError(f"position key mismatch: {symbol}")
        # frozen=True protects attributes, but does not freeze a supplied dict.
        # Copy first so callers cannot mutate a validated risk snapshot later.
        object.__setattr__(self, "balances", MappingProxyType(balances))
        object.__setattr__(self, "liabilities", MappingProxyType(liabilities))
        object.__setattr__(self, "positions", MappingProxyType(positions))
