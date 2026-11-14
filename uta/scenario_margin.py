"""Versioned scenario margin for a USD, BTC and ETH simulation portfolio.

IM is the greater of the gross IM floor and the maximum nonnegative stress
loss. MM is the greater of the gross MM floor and 80% of that same loss.
Stress loss is measured from current haircut-adjusted equity. Every scenario
reprices gross collateral, liabilities and marked positions together, so only
offsets that survive the scenario set receive margin benefit. USD settles at
par in each scenario. Limits and coefficients are illustrative model choices.
"""
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from typing import Mapping

from .models import Account, AssetSpec, InstrumentSpec, RiskInputError
from .risk import RiskSnapshot, _decimal_exact, _ratio, calculate_risk


MODEL_VERSION = "linear-pm-v1"
_ASSETS = ("USD", "BTC", "ETH")
_INSTRUMENTS = ("BTC-PERP", "ETH-PERP")
_MM_STRESS_SHARE = Fraction(4, 5)


@dataclass(frozen=True)
class _Scenario:
    name: str
    asset_shocks: tuple[Fraction, ...]
    mark_shocks: tuple[Fraction, ...]


def _scenario(name: str, btc_spot: int, eth_spot: int, btc_mark: int,
              eth_mark: int) -> _Scenario:
    return _Scenario(name, (Fraction(0), Fraction(btc_spot, 100), Fraction(eth_spot, 100)),
                     (Fraction(btc_mark, 100), Fraction(eth_mark, 100)))


_SCENARIOS = (
    _scenario("market_down", -15, -20, -15, -20),
    _scenario("market_up", 15, 20, 15, 20),
    _scenario("btc_down_eth_up", -12, 12, -12, 12),
    _scenario("btc_up_eth_down", 12, -12, 12, -12),
    _scenario("collateral_gap_down", -18, -25, 8, 12),
    _scenario("collateral_gap_up", 18, 25, -8, -12),
)


@dataclass(frozen=True)
class ScenarioResult:
    name: str
    equity: Decimal
    loss: Decimal  # Gains are represented by negative loss.
    collateral_change: Decimal
    liability_change: Decimal  # Signed effect of liabilities on equity.
    position_change: Decimal
    asset_shocks: dict[str, Decimal]
    mark_shocks: dict[str, Decimal]


@dataclass(frozen=True)
class PortfolioRisk(RiskSnapshot):
    model_version: str
    stress_loss: Decimal
    worst_scenario: str | None
    initial_margin_floor: Decimal
    maintenance_margin_floor: Decimal
    scenarios: tuple[ScenarioResult, ...]


def position_im_bound(symbol: str, instrument: InstrumentSpec) -> Decimal:
    """Bound absolute IM change per unit of signed quantity at current marks.

    The gross floor changes by at most mark × rate × |delta quantity|.
    Each stress loss changes by at most mark × |scenario shock| × |delta quantity|.
    Taking a maximum preserves the largest of these bounds. The same bound
    therefore applies sequentially to any subset of resting fills at fixed
    marks. Execution cost and fees are equity changes and are reserved apart.
    """
    if symbol not in _INSTRUMENTS or not isinstance(instrument, InstrumentSpec):
        raise RiskInputError("unsupported portfolio instrument")
    index = _INSTRUMENTS.index(symbol)
    max_mark_shock = max(abs(scenario.mark_shocks[index]) for scenario in _SCENARIOS)
    rate = max(Fraction(instrument.initial_margin_rate), max_mark_shock)
    return _decimal_exact(Fraction(instrument.mark_price) * rate)


def calculate_portfolio(account: Account, assets: Mapping[str, AssetSpec],
                        instruments: Mapping[str, InstrumentSpec]) -> PortfolioRisk:
    """Calculate a same-snapshot margin requirement using named joint shocks."""
    unsupported_assets = (set(assets) | set(account.balances) | set(account.liabilities)) - set(_ASSETS)
    if unsupported_assets:
        raise RiskInputError("unsupported portfolio asset")
    if (set(instruments) | set(account.positions)) - set(_INSTRUMENTS):
        raise RiskInputError("unsupported portfolio instrument")
    if any(not isinstance(spec, AssetSpec) for spec in assets.values()):
        raise RiskInputError("invalid portfolio asset specification")
    if any(not isinstance(spec, InstrumentSpec) for spec in instruments.values()):
        raise RiskInputError("invalid portfolio instrument specification")
    if "USD" in assets:
        usd = assets["USD"]
        if usd.price != 1 or usd.collateral_factor != 1:
            raise RiskInputError("USD portfolio settlement requires price and collateral factor equal to 1")
    base = calculate_risk(account, assets, instruments)
    equity = Fraction(base.equity)
    collateral = {}
    liabilities = {}
    for asset in _ASSETS:
        if asset not in assets:
            continue
        amount = Fraction(account.balances.get(asset, 0))
        price = Fraction(assets[asset].price)
        collateral[asset] = max(0, amount) * price * Fraction(assets[asset].collateral_factor)
        liabilities[asset] = (Fraction(account.liabilities.get(asset, 0)) + max(0, -amount)) * price
    positions = {symbol: Fraction(position.quantity) * Fraction(instruments[symbol].mark_price)
                 for symbol, position in account.positions.items()}

    results = []
    stress_loss = Fraction(0)
    worst_scenario = None
    for scenario in _SCENARIOS:
        asset_shocks = dict(zip(_ASSETS, scenario.asset_shocks))
        mark_shocks = dict(zip(_INSTRUMENTS, scenario.mark_shocks))
        collateral_change = sum(value * asset_shocks[asset] for asset, value in collateral.items())
        liability_change = -sum(value * asset_shocks[asset] for asset, value in liabilities.items())
        position_change = sum(value * mark_shocks[symbol] for symbol, value in positions.items())
        change = collateral_change + liability_change + position_change
        if -change > stress_loss:
            stress_loss = -change
            worst_scenario = scenario.name
        results.append(ScenarioResult(
            name=scenario.name,
            equity=_decimal_exact(equity + change),
            loss=_decimal_exact(-change),
            collateral_change=_decimal_exact(collateral_change),
            liability_change=_decimal_exact(liability_change),
            position_change=_decimal_exact(position_change),
            asset_shocks={asset: _decimal_exact(shock) for asset, shock in asset_shocks.items()},
            mark_shocks={symbol: _decimal_exact(shock) for symbol, shock in mark_shocks.items()},
        ))

    initial = max(Fraction(base.initial_margin), stress_loss)
    maintenance = max(Fraction(base.maintenance_margin), stress_loss * _MM_STRESS_SHARE)
    return PortfolioRisk(
        equity=base.equity,
        initial_margin=_decimal_exact(initial),
        maintenance_margin=_decimal_exact(maintenance),
        open_order_margin=base.open_order_margin,
        available_margin=_decimal_exact(equity - initial - Fraction(base.open_order_margin)),
        margin_ratio=_ratio(equity, maintenance) if maintenance else None,
        model_version=MODEL_VERSION,
        stress_loss=_decimal_exact(stress_loss),
        worst_scenario=worst_scenario,
        initial_margin_floor=base.initial_margin,
        maintenance_margin_floor=base.maintenance_margin,
        scenarios=tuple(results),
    )
