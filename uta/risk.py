"""Conservative reference risk calculation; not an exchange PM model.

The model uses linear position risk, fixed per-instrument rates, independent
asset haircuts, and full liability value. It does not model scenario offsets,
options, tiers, funding, interest, stale feeds, insurance funds or ADL. Prices,
positions and order reserves must be an atomic, fresh caller-provided snapshot.
"""
from dataclasses import dataclass
from decimal import Decimal, Context, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
from typing import Mapping

from .models import Account, AssetSpec, InstrumentSpec, RiskInputError, _decimal


def _decimal_exact(value: Fraction) -> Decimal:
    """Convert a terminating rational to Decimal without caller context rounding.

    Risk arithmetic starts with finite decimals and only uses +, - and *, so
    all non-ratio outputs terminate. Explicit denominator checks avoid silent
    precision loss if a future change introduces a non-terminating operation.
    """
    denominator = value.denominator
    twos = fives = 0
    while denominator % 2 == 0:
        denominator //= 2
        twos += 1
    while denominator % 5 == 0:
        denominator //= 5
        fives += 1
    if denominator != 1:
        raise RiskInputError("non-terminating financial amount")
    scale = max(twos, fives)
    coefficient = value.numerator * 2 ** (scale - twos) * 5 ** (scale - fives)
    digits = tuple(int(digit) for digit in str(abs(coefficient)))
    return Decimal((int(coefficient < 0), digits, -scale))


def _ratio(numerator: Fraction, denominator: Fraction) -> Decimal:
    """The display ratio is rounded to 34 significant digits, half-even."""
    result = numerator / denominator
    with localcontext(Context(prec=34, rounding=ROUND_HALF_EVEN)):
        return Decimal(result.numerator) / Decimal(result.denominator)


@dataclass(frozen=True)
class RiskSnapshot:
    equity: Decimal
    initial_margin: Decimal
    maintenance_margin: Decimal
    open_order_margin: Decimal
    available_margin: Decimal
    margin_ratio: Decimal | None


@dataclass(frozen=True)
class OrderCheck:
    accepted: bool
    projected_equity: Decimal
    projected_initial_margin: Decimal
    projected_available_margin: Decimal
    reason: str


def calculate_risk(account: Account, asset_specs: Mapping[str, AssetSpec],
                   instrument_specs: Mapping[str, InstrumentSpec]) -> RiskSnapshot:
    collateral = Fraction(0)
    for asset, amount in account.balances.items():
        try:
            spec = asset_specs[asset]
        except KeyError as exc:
            raise RiskInputError(f"missing asset specification: {asset}") from exc
        if not isinstance(spec, AssetSpec):
            raise RiskInputError(f"invalid asset specification: {asset}")
        collateral += Fraction(amount) * Fraction(spec.price) * Fraction(spec.collateral_factor if amount > 0 else Decimal(1))

    for asset, amount in account.liabilities.items():
        try:
            spec = asset_specs[asset]
        except KeyError as exc:
            raise RiskInputError(f"missing liability asset specification: {asset}") from exc
        if not isinstance(spec, AssetSpec):
            raise RiskInputError(f"invalid asset specification: {asset}")
        collateral -= Fraction(amount) * Fraction(spec.price)

    pnl = Fraction(0)
    initial_margin = Fraction(0)
    maintenance_margin = Fraction(0)
    for symbol, position in account.positions.items():
        try:
            spec = instrument_specs[symbol]
        except KeyError as exc:
            raise RiskInputError(f"missing instrument specification: {symbol}") from exc
        if not isinstance(spec, InstrumentSpec):
            raise RiskInputError(f"invalid instrument specification: {symbol}")
        pnl += Fraction(position.quantity) * (Fraction(spec.mark_price) - Fraction(position.entry_price))
        notional = abs(Fraction(position.quantity)) * Fraction(spec.mark_price)
        initial_margin += notional * Fraction(spec.initial_margin_rate)
        maintenance_margin += notional * Fraction(spec.maintenance_margin_rate)
    equity = collateral + pnl
    return RiskSnapshot(
        equity=_decimal_exact(equity),
        initial_margin=_decimal_exact(initial_margin),
        maintenance_margin=_decimal_exact(maintenance_margin),
        open_order_margin=account.open_order_margin,
        available_margin=_decimal_exact(equity - initial_margin - Fraction(account.open_order_margin)),
        margin_ratio=_ratio(equity, maintenance_margin) if maintenance_margin else None,
    )


def check_order(account: Account, asset_specs: Mapping[str, AssetSpec],
                instrument_specs: Mapping[str, InstrumentSpec], *, symbol: str,
                quantity: Decimal, execution_price: Decimal,
                fee_rate: Decimal = Decimal(0)) -> OrderCheck:
    """Check an immediately filled signed order against projected initial margin.

    Caller must serialize checks with order reservations/fills, supply a
    conservative execution price and reserve all other outstanding orders. This
    calculation alone is not an atomic order acceptance or execution service.
    It counts existing order reserves in full, even for risk-reducing orders.
    """
    _decimal("order quantity", quantity)
    if quantity == 0:
        raise RiskInputError("order quantity must be nonzero")
    _decimal("execution price", execution_price, positive=True)
    _decimal("fee rate", fee_rate, minimum=Decimal(0), maximum=Decimal(1))
    try:
        spec = instrument_specs[symbol]
    except KeyError as exc:
        raise RiskInputError(f"missing instrument specification: {symbol}") from exc
    if not isinstance(spec, InstrumentSpec):
        raise RiskInputError(f"invalid instrument specification: {symbol}")
    snapshot = calculate_risk(account, asset_specs, instrument_specs)
    old_quantity = Fraction(account.positions[symbol].quantity if symbol in account.positions else Decimal(0))
    quantity_f, mark, execution, fee = map(Fraction, (quantity, spec.mark_price, execution_price, fee_rate))
    old_im = abs(old_quantity) * mark * Fraction(spec.initial_margin_rate)
    new_im = abs(old_quantity + quantity_f) * mark * Fraction(spec.initial_margin_rate)
    projected_im = Fraction(snapshot.initial_margin) - old_im + new_im
    # Changing a linear position at execution price affects marked equity by
    # quantity * (mark - execution), even when reducing or reversing a position.
    projected_equity = (Fraction(snapshot.equity) + quantity_f * (mark - execution)
                        - abs(quantity_f) * execution * fee)
    available = projected_equity - projected_im - Fraction(account.open_order_margin)
    accepted = available >= 0
    return OrderCheck(accepted, _decimal_exact(projected_equity), _decimal_exact(projected_im), _decimal_exact(available),
                      "sufficient initial margin" if accepted else "insufficient initial margin")
