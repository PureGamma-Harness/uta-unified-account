"""Read-only, independent replay of authoritative trading and source genesis.

All inspections join one database transaction. The replay uses rational cashflow
and signed cost accounting, not the service's production projection helper.
Missing evidence is an error, never a zero-balance/flat-position assumption.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from hashlib import sha256
import json

from .credit import CreditService
from .ledger import Ledger
from .matching import Matcher
from .service import ExchangeService, ServiceError


def _fail(message: str) -> None:
    raise ServiceError("reconciliation_failed", message, 503)


def _number(value) -> Fraction:
    if not isinstance(value, str) or not 1 <= len(value) <= 256:
        _fail("financial evidence must be a bounded decimal string")
    try:
        decimal = Decimal(value)
    except InvalidOperation:
        _fail("financial evidence is not a decimal")
    if (not decimal.is_finite() or len(decimal.as_tuple().digits) > 128
            or abs(decimal.as_tuple().exponent) > 100):
        _fail("financial evidence exceeds supported bounds")
    return Fraction(decimal)


def _json_object(text: str) -> dict:
    try:
        value = json.loads(text)
    except (ValueError, TypeError, RecursionError):
        _fail("audit evidence is not valid JSON")
    if not isinstance(value, dict):
        _fail("audit evidence must be an object")
    return value


def _checksum(row) -> dict:
    if (not isinstance(row["receipt"], str)
            or sha256(row["receipt"].encode()).hexdigest() != row["receipt_hash"]):
        _fail("source handover receipt checksum failed")
    return _json_object(row["receipt"])


def _journal_key(kind: str, *parts: str) -> str:
    encoded = json.dumps(parts, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return kind + ":" + sha256(encoded.encode()).hexdigest()


def _money(value: Fraction, scale: int, *, ceiling: bool = False) -> Fraction:
    scaled = value * 10**scale
    units = -((-scaled.numerator) // scaled.denominator) if ceiling else scaled.numerator // scaled.denominator
    return Fraction(units, 10**scale)


def _step(quantity: Fraction, basis: Fraction, fill: Fraction, price: Fraction,
          scale: int) -> tuple[Fraction, Fraction, Fraction]:
    """Independent signed-cost reference, including conservative settlement dust."""
    next_quantity = quantity + fill
    if not quantity or (quantity > 0) == (fill > 0):
        return next_quantity, basis + fill * price, Fraction(0)
    closed = min(abs(quantity), abs(fill))
    proceeds = closed * price * (1 if quantity > 0 else -1)
    allocated_basis = basis * closed / abs(quantity)
    settled_pnl = _money(proceeds - allocated_basis, scale)
    if abs(fill) < abs(quantity):
        next_basis = basis - proceeds + settled_pnl
    elif next_quantity:
        next_basis = next_quantity * price
    else:
        next_basis = Fraction(0)
    return next_quantity, next_basis, settled_pnl


def _journal_postings(journal: dict, event_id: str | None) -> list[tuple]:
    if event_id is None:
        return []
    if event_id not in journal:
        _fail("business evidence references a missing journal event")
    return sorted((posting.account, posting.asset, Fraction(posting.amount))
                  for posting in journal[event_id].postings)


def _source_genesis(connection, tables: set[str], journal: dict) -> tuple[dict, dict, int]:
    genesis = {}
    active_import_sequence = {}
    if "migration_imports" not in tables:
        if "migration_reversals" in tables:
            _fail("source reversals exist without their original imports")
        return genesis, active_import_sequence, 0
    if "migration_reversals" not in tables:
        _fail("source handover reversal schema is incomplete")
    guards = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
    if not {"migration_imports_no_update", "migration_imports_no_delete",
            "migration_reversals_no_update", "migration_reversals_no_delete"} <= guards:
        _fail("source handover receipt protection is missing")
    imported = set()
    count = 0
    for row in connection.execute("SELECT * FROM migration_imports"):
        receipt = _checksum(row)
        account = receipt.get("account_id")
        if (row["command_id"] != receipt.get("command_id") or row["source_account_id"] != account
                or account in imported):
            _fail("source handover identity is inconsistent")
        imported.add(account)
        request = {"source_digest": receipt.get("source_digest"),
                   "source_fence_reference": receipt.get("source_fence_reference"),
                   "empty_in_flight_policy": 1}
        expected_digest = sha256(json.dumps(request, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        if expected_digest != row["request_digest"]:
            _fail("source handover request digest is inconsistent")
        postings = receipt.get("journal_postings")
        if not isinstance(postings, list):
            _fail("source handover lacks journal evidence")
        expected = sorted((posting["account"], posting["asset"], _number(posting["amount"])) for posting in postings)
        if _journal_postings(journal, receipt.get("ledger_event_id")) != expected:
            _fail("source handover differs from its journal")
        reversed_row = connection.execute("SELECT * FROM migration_reversals WHERE command_id=?", (row["command_id"],)).fetchone()
        if reversed_row is not None:
            reverse = _checksum(reversed_row)
            if (reverse.get("command_id") != row["command_id"] or reverse.get("account_id") != account
                    or reverse.get("reversal_id") != reversed_row["reversal_id"]):
                _fail("source handback identity is inconsistent")
            if _journal_postings(journal, reverse.get("ledger_event_id")) != sorted((a, b, -v) for a, b, v in expected):
                _fail("source handback is not an exact compensating journal")
            continue
        positions = receipt.get("positions")
        if not isinstance(positions, dict):
            _fail("source handover lacks position genesis")
        for symbol, position in positions.items():
            quantity, basis = _number(position["quantity"]), _number(position["cost_basis"])
            if not quantity or quantity * basis <= 0:
                _fail("source position genesis is invalid")
            genesis[(account, symbol)] = (quantity, basis)
        active_import_sequence[account] = row["command_id"]
        count += 1
    return genesis, active_import_sequence, count


def reconcile_exchange(exchange: ExchangeService, *, matching_only: bool = True) -> dict:
    """Reconcile orders, fills, positions, journals, matching and gross debt.

    No constructor is permitted to repair schema while this checker runs. Manual
    execution records can be inspected with ``matching_only=False``; the default
    rejects fills without an actual paired matching receipt. This function does
    not assert external custody backing, an external source fence, or HA safety.
    """
    if not isinstance(exchange, ExchangeService) or type(matching_only) is not bool:
        raise ValueError("ExchangeService and a boolean matching_only are required")
    with exchange._transaction() as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        ledger_events = exchange.ledger.verify(connection=connection)
        journal = {event.event_id: event for event in exchange.ledger.journal(connection=connection)}
        genesis, active_sources, active_imports = _source_genesis(connection, tables, journal)
        positions = dict(genesis)
        fills = {(row["account_id"], row["fill_id"]): row for row in connection.execute("SELECT * FROM uta_fills")}
        orders = {(row["account_id"], row["order_id"]): row for row in connection.execute("SELECT * FROM uta_orders")}
        fill_events = []
        imported_events = {}
        for event in connection.execute("SELECT * FROM uta_events ORDER BY sequence"):
            if event["event_type"] == "MIGRATION_IMPORTED":
                payload = _json_object(event["payload"])
                imported_events[(event["account_id"], payload.get("command_id"))] = event["sequence"]
            elif event["event_type"] == "FILL_APPLIED":
                fill_events.append((event, _json_object(event["payload"])))
        if any((account, command) not in imported_events for account, command in active_sources.items()):
            _fail("active source genesis lacks its committed handover audit event")
        seen_fills = set()
        totals = defaultdict(Fraction)
        notionals = defaultdict(Fraction)
        charges = defaultdict(Fraction)
        by_symbol = defaultdict(Fraction)
        scale, rate = exchange.scales["USD"], Fraction(exchange.fee_rate)
        for event, payload in fill_events:
            key = (event["account_id"], payload.get("fill_id"))
            if key not in fills or key in seen_fills:
                _fail("execution audit has an orphan or duplicated fill")
            seen_fills.add(key)
            fill = fills[key]
            order_key = (fill["account_id"], fill["order_id"])
            if order_key not in orders:
                _fail("execution has no authoritative order")
            order = orders[order_key]
            account = fill["account_id"]
            if account in active_sources:
                source_sequence = imported_events.get((account, active_sources[account]))
                if source_sequence is None or event["sequence"] <= source_sequence:
                    _fail("execution predates or lacks its source handover boundary")
            amount, price = _number(fill["quantity"]), _number(fill["price"])
            original = _number(order["quantity"])
            if not amount or price <= 0 or (amount > 0) != (original > 0):
                _fail("execution sign or price violates its order")
            limit = _number(order["limit_price"])
            if (amount > 0 and price > limit) or (amount < 0 and price < limit):
                _fail("execution violates its order limit")
            totals[order_key] += amount
            if abs(totals[order_key]) > abs(original):
                _fail("cumulative executions exceed order quantity")
            notionals[order_key] += abs(amount) * price
            cumulative_fee = _money(notionals[order_key] * rate, scale, ceiling=True)
            expected_fee = cumulative_fee - charges[order_key]
            charges[order_key] = cumulative_fee
            position_key = (account, order["symbol"])
            quantity, basis = positions.get(position_key, (Fraction(0), Fraction(0)))
            next_quantity, next_basis, pnl = _step(quantity, basis, amount, price, scale)
            if _number(fill["realized_pnl"]) != pnl or _number(fill["fee"]) != expected_fee:
                _fail("independent cashflow replay disagrees with realized PnL or cumulative fee")
            if next_quantity:
                positions[position_key] = next_quantity, next_basis
            else:
                positions.pop(position_key, None)
            by_symbol[order["symbol"]] += amount
            own_order = payload.get("order")
            if (not isinstance(own_order, dict) or own_order.get("order_id") != fill["order_id"]
                    or own_order.get("account_id") != account or own_order.get("symbol") != order["symbol"]
                    or _number(own_order.get("filled_quantity")) != totals[order_key]
                    or _number(payload.get("quantity")) != amount or _number(payload.get("price")) != price
                    or _number(payload.get("realized_pnl")) != pnl or _number(payload.get("fee")) != expected_fee):
                _fail("execution audit and authoritative cumulative order disagree")
            if own_order.get("status") != ("FILLED" if totals[order_key] == original else "PARTIALLY_FILLED"):
                _fail("execution audit has an inconsistent cumulative order status")
            postings = []
            if pnl:
                postings += [("customer:" + account, "USD", pnl), ("system:realized-pnl", "USD", -pnl)]
            if expected_fee:
                postings += [("customer:" + account, "USD", -expected_fee), ("system:fees", "USD", expected_fee)]
            event_id = _journal_key("fill", account, fill["fill_id"])
            actual = _journal_postings(journal, event_id) if event_id in journal else []
            if actual != sorted(postings):
                _fail("independently replayed execution cashflow differs from journal")
        if seen_fills != set(fills):
            _fail("an authoritative fill lacks a unique committed execution audit event")
        for key, order in orders.items():
            quantity, filled = _number(order["quantity"]), _number(order["filled_quantity"])
            if not quantity or filled != totals[key]:
                _fail("order filled quantity differs from its execution sum")
            expected_status = "FILLED" if filled == quantity else "PARTIALLY_FILLED" if filled else "OPEN"
            if order["status"] != expected_status and not (order["status"] == "CANCELLED" and abs(filled) < abs(quantity)):
                _fail("order status is inconsistent with cumulative execution quantity")
            if (_number(order["fee_notional"]) != notionals[key]
                    or _number(order["charged_fee"]) != charges[key]):
                _fail("order cumulative fee metadata differs from independent replay")
        actual_positions = {(row["account_id"], row["symbol"]): (_number(row["quantity"]), _number(row["cost_basis"]))
                            for row in connection.execute("SELECT * FROM uta_positions")}
        if actual_positions != positions:
            if set(actual_positions) - set(positions):
                _fail("position has no valid execution or active source-genesis origin")
            _fail("position quantity or signed cost basis differs from independent replay")
        if "uta_matches" in tables:
            matching = Matcher(exchange, initialize=False).verify(strict=matching_only, connection=connection)
        elif matching_only and fills:
            _fail("confirmed fills exist without a paired matching authority")
        else:
            matching = {"matches": 0, "paired_fills": 0, "unpaired_fills": len(fills)}
        if matching_only and any(by_symbol.values()):
            _fail("actual paired execution quantities do not net to zero by instrument")
        accounts = {row[0] for row in connection.execute("SELECT account_id FROM uta_accounts")}
        for row in connection.execute("SELECT account_id,asset FROM uta_liabilities"):
            if row["account_id"] not in accounts or row["asset"] not in exchange.scales:
                _fail("gross liability projection names an unknown account or asset")
        for row in connection.execute("SELECT account,asset,units FROM ledger_balances WHERE account LIKE 'liability:%'"):
            if int(row["units"]):
                prefix, separator, account = row["account"].partition(":principal:")
                if not separator:
                    prefix, separator, account = row["account"].partition(":interest:")
                if prefix != "liability" or not separator or account not in accounts or row["asset"] not in exchange.scales:
                    _fail("journal liability lacks an authoritative customer/asset origin")
        if "credit_schema" in tables:
            # A verification view intentionally bypasses __init__: initializing
            # the module would recreate guards or open a nested write transaction.
            credit = CreditService.__new__(CreditService)
            credit.exchange, credit.database, credit.ledger = exchange, exchange.database, exchange.ledger
            credit._codec = Ledger(exchange.scales)
            nonzero_liabilities = credit._verify(connection)
        else:
            nonzero_liabilities = 0
            debts = {(row["account_id"], row["asset"]): row for row in connection.execute("SELECT * FROM uta_liabilities")}
            for account in connection.execute("SELECT account_id FROM uta_accounts"):
                for asset in exchange.scales:
                    row = debts.get((account["account_id"], asset))
                    principal = _number(row["principal"]) if row else Fraction(0)
                    interest = _number(row["interest"]) if row else Fraction(0)
                    if principal < 0 or interest < 0:
                        _fail("gross debt cannot be negative")
                    nonzero_liabilities += int(bool(principal or interest))
                    for kind, amount in (("principal", principal), ("interest", interest)):
                        balance = exchange.ledger.balance("liability:" + kind + ":" + account["account_id"], asset, connection=connection)
                        if Fraction(balance) != -amount:
                            _fail("gross liability projection differs from its journal")
        return {"status": "passed", "matching_only": matching_only,
                "accounts": connection.execute("SELECT COUNT(*) FROM uta_accounts").fetchone()[0],
                "orders": len(orders), "fills": len(fills), "positions": len(positions),
                "active_imports": active_imports, "ledger_events": ledger_events,
                "matches": matching["matches"], "paired_fills": matching["paired_fills"],
                "unpaired_fills": matching["unpaired_fills"], "nonzero_liabilities": nonzero_liabilities}
