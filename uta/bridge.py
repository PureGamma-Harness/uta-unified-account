"""Read-only bridge from reconciled classic snapshots to the reference risk model.

The classic schema does not contain order details. The caller must explicitly
supply all order/other encumbrance margin in the USD reporting unit. This bridge
does not import funds or positions into the durable exchange's authoritative book.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from fractions import Fraction

from .market import MarketSnapshot
from .migration import MigrationError, ShadowAccount, build_shadow
from .models import Account, Position, RiskInputError, _decimal
from .risk import RiskSnapshot, _decimal_exact, calculate_risk


def shadow_to_account(shadow: ShadowAccount, *, open_order_margin: Decimal,
                      now: datetime | None = None,
                      max_age: timedelta = timedelta(seconds=30)) -> Account:
    """Aggregate gross assets and liabilities separately without haircut netting.

    Source digest and freshness are rechecked at use time. The explicit reserve
    argument has no default because a missing source order book is not evidence
    of zero outstanding risk. Source compartments remain in the original shadow.
    """
    if not isinstance(shadow, ShadowAccount):
        raise MigrationError("a reconciled ShadowAccount is required")
    if not isinstance(shadow.captured_at, datetime):
        raise MigrationError("shadow captured_at must be a datetime")
    now = datetime.now(timezone.utc) if now is None else now
    raw = {"account_id": shadow.account_id, "version": shadow.source_version,
           "captured_at": shadow.captured_at.isoformat(),
           "compartments": {"spot": {"balances": []}, "margin": {"balances": []},
                            "futures": {"balances": [], "positions": []}}}
    try:
        for balance in shadow.balances:
            values = {}
            for field in ("free", "locked", "borrowed", "interest"):
                value = getattr(balance, field)
                _decimal(field, value, minimum=Decimal(0))
                values[field] = str(value)
            raw["compartments"][balance.compartment]["balances"].append(
                {"asset": balance.asset, **values})
        for position in shadow.positions:
            _decimal("position quantity", position.quantity)
            _decimal("entry price", position.entry_price, positive=True)
            raw["compartments"]["futures"]["positions"].append(
                {"symbol": position.symbol, "quantity": str(position.quantity),
                 "entry_price": str(position.entry_price)})
        rebuilt = build_shadow(raw, now=now, max_age=max_age)
    except (KeyError, AttributeError, TypeError, RiskInputError) as exc:
        raise MigrationError("invalid shadow contents") from exc
    if rebuilt != shadow:
        raise MigrationError("shadow does not match its reconciled digest or canonical contents")
    assets: dict[str, Fraction] = {}
    liabilities: dict[str, Fraction] = {}
    for balance in rebuilt.balances:
        asset = balance.asset
        assets[asset] = assets.get(asset, Fraction(0)) + Fraction(balance.free) + Fraction(balance.locked)
        liabilities[asset] = (liabilities.get(asset, Fraction(0))
                              + Fraction(balance.borrowed) + Fraction(balance.interest))
    return Account(
        balances={asset: _decimal_exact(amount) for asset, amount in assets.items()},
        liabilities={asset: _decimal_exact(amount) for asset, amount in liabilities.items()},
        positions={position.symbol: Position(position.symbol, position.quantity, position.entry_price)
                   for position in rebuilt.positions},
        open_order_margin=open_order_margin,
    )


def calculate_shadow_risk(shadow: ShadowAccount, market: MarketSnapshot, *,
                          open_order_margin: Decimal, now: datetime | None = None,
                          max_source_age: timedelta = timedelta(seconds=30),
                          max_price_age: timedelta = timedelta(seconds=5)) -> RiskSnapshot:
    """Evaluate the mirror with fresh prices; make no live-account safety claim."""
    if not isinstance(market, MarketSnapshot):
        raise RiskInputError("a MarketSnapshot is required")
    now = datetime.now(timezone.utc) if now is None else now
    market.validate(now=now, max_age=max_price_age)
    account = shadow_to_account(shadow, open_order_margin=open_order_margin,
                                now=now, max_age=max_source_age)
    return calculate_risk(account, market.assets, market.instruments)
