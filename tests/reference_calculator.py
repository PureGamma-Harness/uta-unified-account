"""Independent, exact-rational oracle for the *documented toy model* only.

This deliberately does not import the implementation or use Decimal.  An
immediate fill is evaluated by recomputing the portfolio, with realised PnL
and new entry price, rather than applying the engine's incremental equation.
It is not an oracle for any exchange's proprietary portfolio-margin rules.
"""
from fractions import Fraction as F


def value(account, assets, instruments):
    equity = F(0)
    for asset, amount in account['balances'].items():
        amount = F(amount)
        price, factor = map(F, assets[asset])
        equity += amount * price * (factor if amount > 0 else F(1))
    for asset, amount in account.get('liabilities', {}).items():
        equity -= F(amount) * F(assets[asset][0])
    initial = maintenance = F(0)
    for symbol, (qty, entry) in account['positions'].items():
        qty, entry = F(qty), F(entry)
        mark, im, mm = map(F, instruments[symbol])
        equity += qty * (mark - entry)
        initial += abs(qty) * mark * im
        maintenance += abs(qty) * mark * mm
    reserve = F(account['reserve'])
    return equity, initial, maintenance, equity - initial - reserve


def fill(account, assets, instruments, symbol, order_qty, execution, fee_rate):
    """Realize the closed leg, rebuild position entry, then revalue all legs."""
    q, execution, fee_rate = F(order_qty), F(execution), F(fee_rate)
    old_q, entry = map(F, account['positions'].get(symbol, ('0', '1')))
    new_q = old_q + q
    realised = F(0)
    if old_q and old_q * q < 0:
        close = min(abs(old_q), abs(q))
        realised = close * (execution - entry) * (1 if old_q > 0 else -1)
    if not new_q:
        new_entry = execution
    elif not old_q or old_q * new_q < 0:
        new_entry = execution
    elif old_q * q > 0:
        new_entry = (abs(old_q) * entry + abs(q) * execution) / abs(new_q)
    else:
        new_entry = entry
    updated = {'balances': account['balances'],
               'liabilities': account.get('liabilities', {}),
               'positions': dict(account['positions']), 'reserve': account['reserve']}
    updated['positions'][symbol] = (new_q, new_entry)
    equity, initial, maintenance, available = value(updated, assets, instruments)
    adjustment = realised - abs(q) * execution * fee_rate
    return equity + adjustment, initial, available + adjustment
