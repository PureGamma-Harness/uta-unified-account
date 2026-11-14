"""Initialize a simulated unified account from a validated classic shadow."""
from collections import defaultdict
from decimal import Decimal
from fractions import Fraction
from typing import Mapping

from .migration import MigrationError, ShadowAccount
from .models import AssetSpec, InstrumentSpec, RiskInputError, _decimal
from .risk import _decimal_exact


def _amount(name: str, value: Decimal, *, minimum: Decimal | None = None,
            positive: bool = False) -> Decimal:
    try:
        _decimal(name, value, minimum=minimum, positive=positive)
    except RiskInputError as exc:
        raise MigrationError(str(exc)) from exc
    return value


def _totals(rows: Mapping[str, Fraction]) -> dict[str, str]:
    return {asset: format(_amount(asset, _decimal_exact(quantity)), "f")
            for asset, quantity in rows.items() if quantity}


def convert_shadow(shadow: ShadowAccount, *, asset_config: Mapping[str, AssetSpec],
                   instruments: Mapping[str, InstrumentSpec]) -> dict:
    """Map a validated classic snapshot to a JSON-ready simulator seed.

    Aggregate compatible compartments by asset while keeping owned amounts
    and obligations separate. Locked balances require source order details
    that the classic snapshot schema does not carry. Reject those snapshots
    before they can become spendable simulator collateral.

    The resulting empty order book belongs to the new simulator account.
    A zero locked balance does not establish that the classic account has
    no open orders.
    """
    for asset, spec in asset_config.items():
        if not isinstance(spec, AssetSpec):
            raise MigrationError(f"invalid asset configuration: {asset}")
    for symbol, spec in instruments.items():
        if not isinstance(spec, InstrumentSpec):
            raise MigrationError(f"invalid instrument configuration: {symbol}")

    balances: dict[str, Fraction] = defaultdict(Fraction)
    liabilities: dict[str, Fraction] = defaultdict(Fraction)
    seen: set[tuple[str, str]] = set()
    for balance in shadow.balances:
        asset = balance.asset
        if asset not in asset_config:
            raise MigrationError(f"unsupported classic asset: {asset}")
        key = (balance.compartment, asset)
        if key in seen:
            raise MigrationError(f"duplicate classic balance: {balance.compartment}/{asset}")
        seen.add(key)
        if _amount(f"{asset}.locked", balance.locked, minimum=Decimal(0)):
            raise MigrationError(f"unreconciled locked balance: {balance.compartment}/{asset}")
        balances[asset] += Fraction(_amount(f"{asset}.free", balance.free, minimum=Decimal(0)))
        liabilities[asset] += Fraction(_amount(f"{asset}.borrowed", balance.borrowed,
                                              minimum=Decimal(0)))
        liabilities[asset] += Fraction(_amount(f"{asset}.interest", balance.interest,
                                              minimum=Decimal(0)))

    positions = {}
    for position in shadow.positions:
        symbol = position.symbol
        if symbol not in instruments:
            raise MigrationError(f"unsupported classic instrument: {symbol}")
        if symbol in positions:
            raise MigrationError(f"multiple classic positions for instrument: {symbol}")
        quantity = _amount(f"{symbol}.quantity", position.quantity)
        if quantity == 0:
            raise MigrationError(f"classic position is flat: {symbol}")
        entry_price = _amount(f"{symbol}.entry_price", position.entry_price, positive=True)
        positions[symbol] = {
            "quantity": format(_decimal_exact(Fraction(quantity)), "f"),
            "entry_price": format(_decimal_exact(Fraction(entry_price)), "f"),
        }

    return {
        "as_of": shadow.captured_at.isoformat(),
        "balances": _totals(balances),
        "liabilities": _totals(liabilities),
        "positions": positions,
        "orders": {},
        "prices": {asset: str(spec.price) for asset, spec in asset_config.items()},
        "marks": {symbol: str(spec.mark_price) for symbol, spec in instruments.items()},
        "asset_factors": {asset: str(spec.collateral_factor) for asset, spec in asset_config.items()},
        "instruments": {
            symbol: {
                "initial_margin_rate": str(spec.initial_margin_rate),
                "maintenance_margin_rate": str(spec.maintenance_margin_rate),
            }
            for symbol, spec in instruments.items()
        },
        "source": {
            "account_id": shadow.account_id,
            "version": shadow.source_version,
            "digest": shadow.source_digest,
        },
    }
