"""Funded spot limit books, asset locks and atomic two-asset settlement.

The local authority owns admission, matching, settlement and cancellation. It
does not ingest irreversible external trades. No automatic borrowing, market
orders, isolated margin, PM, external routing or replicated matching is implied.
"""
from __future__ import annotations

from decimal import Decimal
from fractions import Fraction
from hashlib import sha256
import json
import sqlite3
from uuid import uuid4

from .ledger import Ledger, LedgerError, Posting
from .products import AccountMode, ProductCatalog, ProductError, ProductKind
from .service import ExchangeService, ServiceError, _amount, _exact, _json, _key, _name, _text


_LIVE = ("OPEN", "PARTIALLY_FILLED")
_TRANSIENT = {"market_unavailable", "invalid_clock", "storage_unavailable", "trading_halted"}


def _immutable_guard_definitions():
    """One official definition for installing and inspecting receipt guards."""
    definitions = {}
    for table, label in (("uta_spot_matches", "receipts"), ("uta_spot_fills", "fills")):
        for action in ("UPDATE", "DELETE"):
            name = table + "_no_" + action.lower()
            definitions[name] = (table, f"CREATE TRIGGER {name} BEFORE {action} ON {table} "
                                f"BEGIN SELECT RAISE(ABORT,'spot {label} are immutable'); END")
    return definitions


def locked_assets(connection, account_id: str) -> dict[str, Decimal]:
    """Derived settled-asset encumbrances, shared with credit and risk gates."""
    if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='uta_spot_orders'").fetchone() is None:
        return {}
    totals: dict[str, Fraction] = {}
    for row in connection.execute("""SELECT reserved_asset,reserved_amount FROM uta_spot_orders
        WHERE account_id=? AND status IN ('OPEN','PARTIALLY_FILLED')""", (account_id,)):
        try:
            amount = Decimal(row["reserved_amount"])
            if not amount.is_finite() or amount < 0:
                raise ValueError
        except (ArithmeticError, ValueError) as exc:
            raise ServiceError("spot_corrupt", "invalid persisted asset lock", 503) from exc
        totals[row["reserved_asset"]] = totals.get(row["reserved_asset"], Fraction(0)) + Fraction(amount)
    return {asset: _exact(amount) for asset, amount in totals.items() if amount}


def locked_asset(connection, account_id: str, asset: str) -> Decimal:
    return locked_assets(connection, account_id).get(asset, Decimal(0))


def cancel_all_spot_orders(exchange: ExchangeService, connection, account_id: str,
                           reason: str = "risk_supervisor") -> list[dict]:
    """Release local spot locks inside the supervisor's existing transaction.

    This is an internal authority hook, not an external cancel acknowledgement.
    No extra connection or commit is opened, and no filled quantity is reversed.
    """
    if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='uta_spot_orders'").fetchone() is None:
        return []
    cancelled = []
    rows = connection.execute("SELECT * FROM uta_spot_orders WHERE account_id=? AND status IN ('OPEN','PARTIALLY_FILLED') ORDER BY sequence", (account_id,)).fetchall()
    for row in rows:
        version = exchange._bump(connection, account_id)
        connection.execute("UPDATE uta_spot_orders SET status='CANCELLED',reserved_amount='0',version=? WHERE sequence=?", (version, row["sequence"]))
        updated = dict(connection.execute("SELECT * FROM uta_spot_orders WHERE sequence=?", (row["sequence"],)).fetchone())
        exchange._event(connection, "SPOT_ORDER_CANCELLED", account_id, dict(updated, reason=reason))
        cancelled.append(updated)
    return cancelled


class SpotExchange:
    """One local database serializes cash locks and real paired spot trades.

    Spot and spot-margin share the funded book: margin clients must explicitly
    borrow through CreditService before submitting an order. The product's tick
    times quantity-step must be representable in quote minor units, so splitting
    a fill never invents cash through notional rounding. Fees use cumulative
    order notional, rounded up once and charged by increment.
    """

    def __init__(self, exchange: ExchangeService, catalog: ProductCatalog, *, initialize: bool = True):
        if not isinstance(exchange, ExchangeService) or not isinstance(catalog, ProductCatalog):
            raise ServiceError("invalid_configuration", "SpotExchange requires an exchange and ProductCatalog")
        if type(initialize) is not bool:
            raise ServiceError("invalid_configuration", "initialize must be a boolean")
        configured = getattr(exchange, "product_catalog", None)
        if configured is not None and configured != catalog:
            raise ServiceError("configuration_conflict", "spot and account product catalogs must match", 409)
        self.exchange, self.catalog = exchange, catalog
        self._codec = Ledger(exchange.scales)
        for product in catalog.products.values():
            if product.kind not in (ProductKind.SPOT, ProductKind.SPOT_MARGIN):
                continue
            if product.multiplier != 1 or product.quote_asset != "USD" or product.settlement_asset != "USD":
                raise ServiceError("spot_product_unsupported", "spot requires unit multiplier and USD quote/settlement")
            if product.underlying == product.quote_asset:
                raise ServiceError("spot_product_unsupported", "base and quote must be different assets")
            self._units(product.underlying, product.quantity_step)
            self._units(product.quote_asset, _exact(Fraction(product.quantity_step) * Fraction(product.price_tick)))
        if not initialize:
            # Verification views must inspect the existing schema and guards,
            # never recreate them before discovering that they were missing.
            return
        with exchange._transaction() as connection:
            for statement in (
                "CREATE TABLE IF NOT EXISTS uta_spot_schema (singleton INTEGER PRIMARY KEY CHECK(singleton=1),version INTEGER NOT NULL)",
                "CREATE TABLE IF NOT EXISTS uta_spot_config (singleton INTEGER PRIMARY KEY CHECK(singleton=1),catalog TEXT NOT NULL,fee_rate TEXT NOT NULL)",
                """CREATE TABLE IF NOT EXISTS uta_spot_orders (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id TEXT NOT NULL REFERENCES uta_accounts(account_id),order_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,base_asset TEXT NOT NULL,quote_asset TEXT NOT NULL,
                    quantity TEXT NOT NULL,limit_price TEXT NOT NULL,filled_quantity TEXT NOT NULL,
                    fee_notional TEXT NOT NULL,charged_fee TEXT NOT NULL,
                    reserved_asset TEXT NOT NULL,reserved_amount TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('OPEN','PARTIALLY_FILLED','FILLED','CANCELLED')),
                    version INTEGER NOT NULL,created_at TEXT NOT NULL,UNIQUE(account_id,order_id))""",
                """CREATE TABLE IF NOT EXISTS uta_spot_matches (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,trade_id TEXT NOT NULL UNIQUE,
                    symbol TEXT NOT NULL,base_asset TEXT NOT NULL,quote_asset TEXT NOT NULL,
                    buy_account_id TEXT NOT NULL,buy_order_id TEXT NOT NULL,
                    sell_account_id TEXT NOT NULL,sell_order_id TEXT NOT NULL,
                    quantity TEXT NOT NULL,price TEXT NOT NULL,notional TEXT NOT NULL,
                    buy_fee TEXT NOT NULL,sell_fee TEXT NOT NULL,
                    journal_event_id TEXT NOT NULL UNIQUE REFERENCES ledger_events(event_id),
                    market_version INTEGER NOT NULL,catalog_version INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(buy_account_id,buy_order_id) REFERENCES uta_spot_orders(account_id,order_id),
                    FOREIGN KEY(sell_account_id,sell_order_id) REFERENCES uta_spot_orders(account_id,order_id))""",
                """CREATE TABLE IF NOT EXISTS uta_spot_fills (
                    trade_id TEXT NOT NULL REFERENCES uta_spot_matches(trade_id),
                    account_id TEXT NOT NULL,order_id TEXT NOT NULL,quantity TEXT NOT NULL,
                    price TEXT NOT NULL,notional TEXT NOT NULL,fee TEXT NOT NULL,
                    PRIMARY KEY(trade_id,account_id),
                    FOREIGN KEY(account_id,order_id) REFERENCES uta_spot_orders(account_id,order_id))""",
                "CREATE INDEX IF NOT EXISTS uta_spot_live ON uta_spot_orders(symbol,status)",
            ):
                connection.execute(statement)
            for _, definition in _immutable_guard_definitions().values():
                connection.execute(definition.replace("CREATE TRIGGER ", "CREATE TRIGGER IF NOT EXISTS ", 1))
            row = connection.execute("SELECT version FROM uta_spot_schema WHERE singleton=1").fetchone()
            if row is None:
                connection.execute("INSERT INTO uta_spot_schema VALUES (1,1)")
            self._check_schema(connection)
            config = connection.execute("SELECT catalog,fee_rate FROM uta_spot_config WHERE singleton=1").fetchone()
            expected = catalog.to_json(), _text(exchange.fee_rate)
            if config is None:
                connection.execute("INSERT INTO uta_spot_config VALUES (1,?,?)", expected)
            elif tuple(config) != expected:
                raise ServiceError("configuration_conflict", "persisted spot catalog or fee policy differs", 409)
            self._verify(connection)

    def _check_schema(self, connection) -> None:
        rows = [tuple(row) for row in connection.execute("SELECT singleton,version FROM uta_spot_schema")]
        if rows != [(1, 1)]:
            raise ServiceError("spot_schema_version", "unsupported spot schema", 503)

    def _check_configuration(self, connection) -> None:
        rows = [tuple(row) for row in connection.execute("SELECT singleton,catalog,fee_rate FROM uta_spot_config")]
        if rows != [(1, self.catalog.to_json(), _text(self.exchange.fee_rate))]:
            raise ServiceError("spot_corrupt", "persisted spot catalog or fee policy differs", 503)

    def _units(self, asset: str, amount: Decimal) -> int:
        try:
            return self._codec._units(asset, amount)
        except LedgerError as exc:
            raise ServiceError("spot_precision", str(exc)) from exc

    def _product(self, symbol: str, *, quantity: Decimal | None = None,
                 price: Decimal | None = None, fill: bool = False):
        try:
            product = self.catalog.require_supported(symbol, mode=AccountMode.CROSS)
            if product.kind not in (ProductKind.SPOT, ProductKind.SPOT_MARGIN) or product.multiplier != 1:
                raise ServiceError("spot_product_unsupported", "this endpoint only accepts unit-multiplier spot products")
            if quantity is not None:
                if fill:
                    if ((Fraction(quantity) / Fraction(product.quantity_step)).denominator != 1
                            or (Fraction(price) / Fraction(product.price_tick)).denominator != 1):
                        raise ServiceError("invalid_fill", "spot fill violates tick or step")
                else:
                    self.catalog.check_order(symbol, quantity, price)
            return product
        except ProductError as exc:
            raise ServiceError("spot_product_rejected", str(exc), 409) from exc

    def _fee(self, notional: Fraction) -> Decimal:
        return self.exchange._rounded(notional * Fraction(self.exchange.fee_rate), ceiling=True)

    def _remaining(self, row) -> Fraction:
        return Fraction(Decimal(row["quantity"])) - Fraction(Decimal(row["filled_quantity"]))

    def _reservation(self, row) -> tuple[str, Decimal]:
        remaining = self._remaining(row)
        if not remaining:
            return row["reserved_asset"], Decimal(0)
        if remaining < 0:
            return row["base_asset"], _exact(-remaining)
        worst_notional = remaining * Fraction(Decimal(row["limit_price"]))
        expected_total_fee = Fraction(self._fee(Fraction(Decimal(row["fee_notional"])) + worst_notional))
        fee_remaining = expected_total_fee - Fraction(Decimal(row["charged_fee"]))
        if fee_remaining < 0:
            raise ServiceError("spot_corrupt", "invalid cumulative fee reserve", 503)
        return row["quote_asset"], _exact(worst_notional + fee_remaining)

    @staticmethod
    def _order(row) -> dict:
        return dict(row)

    def _check_account_risk(self, connection, account_id: str, market) -> None:
        risk = self.exchange._risk(connection, account_id, market)
        if Decimal(risk["available_margin"]) < 0:
            raise ServiceError("insufficient_margin", "spot encumbrance or execution exceeds available cross margin", 409)

    def submit_order(self, account_id: str, order_id: str, symbol: str,
                     quantity: Decimal, limit_price: Decimal) -> dict:
        for value, label in ((account_id, "account_id"), (order_id, "order_id"), (symbol, "symbol")):
            _name(value, label)
        _amount(quantity, "quantity", nonzero=True)
        _amount(limit_price, "limit_price", positive=True)
        qtext, ptext = _text(quantity), _text(limit_price)
        with self.exchange._transaction() as connection:
            self._check_schema(connection)
            self.exchange._require_account(connection, account_id)
            old = connection.execute("SELECT * FROM uta_spot_orders WHERE account_id=? AND order_id=?", (account_id, order_id)).fetchone()
            if old is not None:
                if (old["symbol"], old["quantity"], old["limit_price"]) != (symbol, qtext, ptext):
                    raise ServiceError("idempotency_conflict", "spot order ID reused with different content", 409)
                return self._order(old)
            product = self._product(symbol, quantity=quantity, price=limit_price)
            market = self.exchange._market(connection)
            self.exchange._require_exposure_allowed(connection, account_id)
            if product.underlying not in market.assets or product.quote_asset not in market.assets:
                raise ServiceError("market_incomplete", "spot requires fresh base and quote collateral prices", 503)
            if connection.execute("SELECT COUNT(*) FROM uta_spot_orders WHERE account_id=? AND status IN ('OPEN','PARTIALLY_FILLED')", (account_id,)).fetchone()[0] >= 1000:
                raise ServiceError("order_limit", "too many live spot orders", 409)
            proposed = {"quantity": qtext, "filled_quantity": "0", "limit_price": ptext,
                        "base_asset": product.underlying, "quote_asset": product.quote_asset,
                        "reserved_asset": product.quote_asset if quantity > 0 else product.underlying,
                        "fee_notional": "0", "charged_fee": "0"}
            asset, reserve = self._reservation(proposed)
            self._units(asset, reserve)
            if Fraction(self.exchange._available_asset(connection, account_id, asset)) < Fraction(reserve):
                raise ServiceError("insufficient_cash", "settled cash is already spent or locked", 409)
            version = self.exchange._bump(connection, account_id)
            connection.execute("""INSERT INTO uta_spot_orders (
                account_id,order_id,symbol,base_asset,quote_asset,quantity,limit_price,filled_quantity,
                fee_notional,charged_fee,reserved_asset,reserved_amount,status,version,created_at)
                VALUES (?,?,?,?,?,?,?,'0','0','0',?,?,'OPEN',?,?)""",
                (account_id, order_id, symbol, product.underlying, product.quote_asset, qtext, ptext,
                 asset, _text(reserve), version, self.exchange._now().isoformat()))
            self._check_account_risk(connection, account_id, market)
            result = self._order(connection.execute("SELECT * FROM uta_spot_orders WHERE account_id=? AND order_id=?", (account_id, order_id)).fetchone())
            self.exchange._event(connection, "SPOT_ORDER_ACCEPTED", account_id, result)
            return result

    def _cancel(self, connection, row, reason: str) -> dict:
        if row["status"] in _LIVE:
            version = self.exchange._bump(connection, row["account_id"])
            connection.execute("UPDATE uta_spot_orders SET status='CANCELLED',reserved_amount='0',version=? WHERE sequence=?", (version, row["sequence"]))
            row = connection.execute("SELECT * FROM uta_spot_orders WHERE sequence=?", (row["sequence"],)).fetchone()
            self.exchange._event(connection, "SPOT_ORDER_CANCELLED", row["account_id"], dict(row, reason=reason))
        return self._order(row)

    def cancel_order(self, account_id: str, order_id: str) -> dict:
        _name(account_id, "account_id")
        _name(order_id, "order_id")
        with self.exchange._transaction() as connection:
            self._check_schema(connection)
            self.exchange._require_account(connection, account_id)
            row = connection.execute("SELECT * FROM uta_spot_orders WHERE account_id=? AND order_id=?", (account_id, order_id)).fetchone()
            if row is None:
                raise ServiceError("order_not_found", "unknown spot order", 404)
            return self._cancel(connection, row, "customer_cancel")

    def _advance(self, connection, row, quantity: Decimal, price: Decimal):
        notional = abs(Fraction(quantity)) * Fraction(price)
        cumulative = Fraction(Decimal(row["fee_notional"])) + notional
        total_fee = self._fee(cumulative)
        fee = _exact(Fraction(total_fee) - Fraction(Decimal(row["charged_fee"])))
        filled = _exact(Fraction(Decimal(row["filled_quantity"])) + Fraction(quantity))
        status = "FILLED" if filled == Decimal(row["quantity"]) else "PARTIALLY_FILLED"
        changed = dict(row, filled_quantity=_text(filled), fee_notional=_text(_exact(cumulative)),
                       charged_fee=_text(total_fee))
        asset, reserve = self._reservation(changed) if status != "FILLED" else (row["reserved_asset"], Decimal(0))
        version = self.exchange._bump(connection, row["account_id"])
        connection.execute("""UPDATE uta_spot_orders SET filled_quantity=?,fee_notional=?,charged_fee=?,
            reserved_asset=?,reserved_amount=?,status=?,version=? WHERE sequence=?""",
            (_text(filled), changed["fee_notional"], changed["charged_fee"], asset, _text(reserve), status, version, row["sequence"]))
        return fee

    @staticmethod
    def _identity(symbol, buy, sell, quantity, price):
        values = [symbol, buy["account_id"], buy["order_id"], sell["account_id"], sell["order_id"],
                  buy["filled_quantity"], sell["filled_quantity"], _text(quantity), _text(price)]
        return "spot:" + sha256(_json(values).encode()).hexdigest()

    def match_once(self, symbol: str, max_matches: int = 100) -> dict:
        _name(symbol, "symbol")
        if type(max_matches) is not int or not 1 <= max_matches <= 1000:
            raise ServiceError("invalid_input", "max_matches must be an integer in 1..1000")
        result = {"symbol": symbol, "confirmed_trades": 0, "trades": [], "cancelled_orders": [], "blocked": []}
        with self.exchange._transaction() as connection:
            self._check_schema(connection)
            self._product(symbol)
            try:
                market = self.exchange._market(connection)
            except ServiceError as exc:
                if exc.code not in _TRANSIENT:
                    raise
                result["blocked"].append({"code": exc.code})
                return result
            for _ in range(2 * max_matches + 1):
                if result["confirmed_trades"] >= max_matches:
                    break
                rows = connection.execute("SELECT * FROM uta_spot_orders WHERE symbol=? AND status IN ('OPEN','PARTIALLY_FILLED')", (symbol,)).fetchall()
                buys = sorted((r for r in rows if self._remaining(r) > 0), key=lambda r: (-Fraction(Decimal(r["limit_price"])), r["sequence"]))
                sells = sorted((r for r in rows if self._remaining(r) < 0), key=lambda r: (Fraction(Decimal(r["limit_price"])), r["sequence"]))
                if not buys or not sells or Decimal(buys[0]["limit_price"]) < Decimal(sells[0]["limit_price"]):
                    break
                buy, sell = buys[0], sells[0]
                if buy["account_id"] == sell["account_id"]:
                    taker = max((buy, sell), key=lambda r: r["sequence"])
                    result["cancelled_orders"].append(self._cancel(connection, taker, "self_trade_prevention"))
                    continue
                quantity = _exact(min(self._remaining(buy), -self._remaining(sell)))
                maker = min((buy, sell), key=lambda r: r["sequence"])
                price = Decimal(maker["limit_price"])
                self._product(symbol, quantity=quantity, price=price, fill=True)
                market = self.exchange._market(connection)
                savepoint = "spot_" + uuid4().hex
                connection.execute(f"SAVEPOINT {savepoint}")
                rejected = buy
                try:
                    for row in (buy, sell):
                        rejected = row
                        self.exchange._require_exposure_allowed(connection, row["account_id"])
                    buy_fee = self._advance(connection, buy, quantity, price)
                    sell_fee = self._advance(connection, sell, quantity.copy_negate(), price)
                    notional = _exact(Fraction(quantity) * Fraction(price))
                    buy_cash = _exact(Fraction(notional) + Fraction(buy_fee))
                    for row, asset, debit in ((buy, buy["quote_asset"], buy_cash), (sell, sell["base_asset"], quantity)):
                        rejected = row
                        if Fraction(self.exchange._available_asset(connection, row["account_id"], asset)) < Fraction(debit):
                            raise ServiceError("insufficient_cash", "spot execution would consume another order's cash", 409)
                    trade_id = self._identity(symbol, buy, sell, quantity, price)
                    journal_id = _key("spot-trade", trade_id)
                    postings = self._postings(buy, sell, quantity, notional, buy_fee, sell_fee)
                    self.exchange.ledger.post(journal_id, postings, connection=connection)
                    for row in (buy, sell):
                        rejected = row
                        self._check_account_risk(connection, row["account_id"], market)
                    connection.execute("""INSERT INTO uta_spot_matches (
                        trade_id,symbol,base_asset,quote_asset,buy_account_id,buy_order_id,sell_account_id,
                        sell_order_id,quantity,price,notional,buy_fee,sell_fee,journal_event_id,
                        market_version,catalog_version,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (trade_id, symbol, buy["base_asset"], buy["quote_asset"], buy["account_id"], buy["order_id"],
                         sell["account_id"], sell["order_id"], _text(quantity), _text(price), _text(notional),
                         _text(buy_fee), _text(sell_fee), journal_id, market.version, self.catalog.version,
                         self.exchange._now().isoformat()))
                    for row, signed, fee in ((buy, quantity, buy_fee), (sell, quantity.copy_negate(), sell_fee)):
                        connection.execute("INSERT INTO uta_spot_fills VALUES (?,?,?,?,?,?,?)", (trade_id,
                            row["account_id"], row["order_id"], _text(signed), _text(price), _text(notional), _text(fee)))
                        self.exchange._event(connection, "SPOT_TRADE_CONFIRMED", row["account_id"], {
                            "trade_id": trade_id, "symbol": symbol, "order_id": row["order_id"],
                            "quantity": _text(signed), "price": _text(price), "fee": _text(fee),
                            "market_version": market.version, "catalog_version": self.catalog.version})
                    receipt = dict(connection.execute("SELECT * FROM uta_spot_matches WHERE trade_id=?", (trade_id,)).fetchone())
                    self.exchange._event(connection, "SPOT_MATCH_CONFIRMED", None, receipt)
                    connection.execute(f"RELEASE SAVEPOINT {savepoint}")
                except ServiceError as exc:
                    if connection.in_transaction:
                        connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                        connection.execute(f"RELEASE SAVEPOINT {savepoint}")
                    result["blocked"].append({"code": exc.code, "account_id": rejected["account_id"], "order_id": rejected["order_id"]})
                    if exc.code in _TRANSIENT:
                        break
                    if exc.code not in {"insufficient_cash", "insufficient_margin", "account_frozen"}:
                        raise
                    result["cancelled_orders"].append(self._cancel(connection, rejected, "execution_rejected:" + exc.code))
                    continue
                result["trades"].append(receipt)
                result["confirmed_trades"] += 1
        return result

    def _postings(self, buy, sell, quantity, notional, buy_fee, sell_fee):
        customer = self.exchange._customer
        postings = [Posting(customer(sell["account_id"]), buy["base_asset"], quantity.copy_negate()),
                    Posting(customer(buy["account_id"]), buy["base_asset"], quantity),
                    Posting(customer(buy["account_id"]), buy["quote_asset"], _exact(-Fraction(notional) - Fraction(buy_fee)))]
        proceeds = _exact(Fraction(notional) - Fraction(sell_fee))
        if proceeds:
            postings.append(Posting(customer(sell["account_id"]), buy["quote_asset"], proceeds))
        total_fee = _exact(Fraction(buy_fee) + Fraction(sell_fee))
        if total_fee:
            postings.append(Posting("system:spot-fees", buy["quote_asset"], total_fee))
        return postings

    def orders(self, account_id: str) -> list[dict]:
        _name(account_id, "account_id")
        with self.exchange._transaction() as connection:
            self._check_schema(connection)
            self.exchange._require_account(connection, account_id)
            return [dict(row) for row in connection.execute("SELECT * FROM uta_spot_orders WHERE account_id=? ORDER BY sequence", (account_id,))]

    def trades(self, after: int = 0, limit: int = 100) -> list[dict]:
        if type(after) is not int or not 0 <= after <= 2**63 - 1 or type(limit) is not int or not 1 <= limit <= 1000:
            raise ServiceError("invalid_input", "invalid spot trade cursor or limit")
        with self.exchange._transaction() as connection:
            self._check_schema(connection)
            return [dict(row) for row in connection.execute("SELECT * FROM uta_spot_matches WHERE sequence>? ORDER BY sequence LIMIT ?", (after, limit))]

    def _verify(self, connection) -> dict:
        self._check_schema(connection)
        self._check_configuration(connection)
        ledger_events = self.exchange.ledger.verify(connection=connection)
        installed = {row["name"]: (row["type"], row["tbl_name"], row["sql"])
                     for row in connection.execute("SELECT name,type,tbl_name,sql FROM sqlite_master")}
        for name, (table, definition) in _immutable_guard_definitions().items():
            if installed.get(name) != ("trigger", table, definition):
                raise ServiceError("spot_corrupt", "spot receipt/fill protection differs from its official definition", 503)
        journal = {event.event_id: event for event in self.exchange.ledger.journal(connection=connection)}
        # Reconcile both directions: a missing receipt must not hide its
        # retained confirmation event. Index once rather than rescan all audit
        # rows for each historical match.
        audit = {"SPOT_MATCH_CONFIRMED": {}, "SPOT_TRADE_CONFIRMED": {}}
        def invalid_number(value):
            # The recorded confirmation contract uses strings for money and
            # JSON integers for versions/sequence, never floating point values.
            raise ValueError("floating point confirmation value")
        def unique_object(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate confirmation field")
                result[key] = value
            return result
        for row in connection.execute("SELECT event_type,account_id,payload FROM uta_events WHERE event_type IN ('SPOT_MATCH_CONFIRMED','SPOT_TRADE_CONFIRMED')"):
            try:
                payload = json.loads(row["payload"], parse_float=invalid_number,
                                     parse_constant=invalid_number, object_pairs_hook=unique_object)
            except (ValueError, TypeError) as exc:
                raise ServiceError("spot_corrupt", "spot audit payload is invalid", 503) from exc
            if (not isinstance(payload, dict) or not isinstance(payload.get("trade_id"), str)
                    or not payload["trade_id"]):
                raise ServiceError("spot_corrupt", "spot confirmation event has no valid trade identity", 503)
            audit[row["event_type"]].setdefault(payload["trade_id"], []).append((row["account_id"], payload))
        matches = connection.execute("SELECT * FROM uta_spot_matches ORDER BY sequence").fetchall()
        trade_ids = {row["trade_id"] for row in matches}
        if any(set(events) != trade_ids for events in audit.values()):
            raise ServiceError("spot_corrupt", "spot confirmation events and receipts do not resolve in both directions", 503)
        fills_by_trade, fills_by_order = {}, {}
        for fill in connection.execute("SELECT * FROM uta_spot_fills"):
            if fill["trade_id"] not in trade_ids:
                raise ServiceError("spot_corrupt", "spot fill has no confirmed receipt", 503)
            fills_by_trade.setdefault(fill["trade_id"], []).append(fill)
            fills_by_order.setdefault((fill["account_id"], fill["order_id"]), []).append(fill)
        for trade in matches:
            quantity, notional = Decimal(trade["quantity"]), Decimal(trade["notional"])
            if quantity <= 0 or Decimal(trade["price"]) <= 0 or min(Decimal(trade["buy_fee"]), Decimal(trade["sell_fee"])) < 0:
                raise ServiceError("spot_corrupt", "invalid spot receipt amounts", 503)
            if Fraction(quantity) * Fraction(Decimal(trade["price"])) != Fraction(notional):
                raise ServiceError("spot_corrupt", "receipt notional does not match actual quantity and price", 503)
            fills = fills_by_trade.get(trade["trade_id"], [])
            expected = {
                trade["buy_account_id"]: (trade["buy_order_id"], quantity, Decimal(trade["buy_fee"])),
                trade["sell_account_id"]: (trade["sell_order_id"], quantity.copy_negate(), Decimal(trade["sell_fee"]))}
            if len(expected) != 2 or len(fills) != 2:
                raise ServiceError("spot_corrupt", "a spot receipt must have two distinct confirmed sides", 503)
            for fill in fills:
                if expected.get(fill["account_id"]) != (fill["order_id"], Decimal(fill["quantity"]), Decimal(fill["fee"])):
                    raise ServiceError("spot_corrupt", "spot receipt and fill differ", 503)
                if fill["notional"] != trade["notional"] or fill["price"] != trade["price"]:
                    raise ServiceError("spot_corrupt", "spot fill value differs from receipt", 503)
            buy = {"account_id": trade["buy_account_id"], "base_asset": trade["base_asset"], "quote_asset": trade["quote_asset"]}
            sell = {"account_id": trade["sell_account_id"]}
            expected_postings = self._postings(buy, sell, quantity, notional, Decimal(trade["buy_fee"]), Decimal(trade["sell_fee"]))
            event = journal.get(trade["journal_event_id"])
            key = lambda posting: (posting.account, posting.asset, Fraction(posting.amount))
            if event is None or sorted(event.postings, key=key) != sorted(expected_postings, key=key):
                raise ServiceError("spot_corrupt", "spot receipt does not match its balanced settlement journal", 503)
            global_events = audit["SPOT_MATCH_CONFIRMED"][trade["trade_id"]]
            private_events = audit["SPOT_TRADE_CONFIRMED"][trade["trade_id"]]
            if (len(global_events) != 1 or global_events[0][0] is not None
                    or _json(global_events[0][1]) != _json(dict(trade)) or len(private_events) != 2
                    or {account for account, _ in private_events} != set(expected)):
                raise ServiceError("spot_corrupt", "spot confirmation events differ from committed receipt", 503)
            for account, payload in private_events:
                own = expected.get(account)
                expected_payload = {"trade_id": trade["trade_id"], "symbol": trade["symbol"],
                    "order_id": own[0], "quantity": _text(own[1]), "price": trade["price"],
                    "fee": _text(own[2]), "market_version": trade["market_version"],
                    "catalog_version": trade["catalog_version"]}
                if _json(payload) != _json(expected_payload):
                    raise ServiceError("spot_corrupt", "private spot event differs from confirmed side", 503)
        orders = connection.execute("SELECT * FROM uta_spot_orders").fetchall()
        if not set(fills_by_order) <= {(row["account_id"], row["order_id"]) for row in orders}:
            raise ServiceError("spot_corrupt", "spot fill has no original order", 503)
        for order in orders:
            product = self.catalog.products.get(order["symbol"])
            if (product is None or product.kind not in (ProductKind.SPOT, ProductKind.SPOT_MARGIN)
                    or (order["base_asset"], order["quote_asset"]) != (product.underlying, product.quote_asset)
                    or order["status"] not in (*_LIVE, "FILLED", "CANCELLED")):
                raise ServiceError("spot_corrupt", "spot order product metadata or status differs", 503)
            fills = fills_by_order.get((order["account_id"], order["order_id"]), [])
            quantity = sum((Fraction(Decimal(fill["quantity"])) for fill in fills), Fraction(0))
            notional = sum((Fraction(Decimal(fill["notional"])) for fill in fills), Fraction(0))
            fee = sum((Fraction(Decimal(fill["fee"])) for fill in fills), Fraction(0))
            if (quantity != Fraction(Decimal(order["filled_quantity"])) or notional != Fraction(Decimal(order["fee_notional"]))
                    or fee != Fraction(Decimal(order["charged_fee"])) or fee != Fraction(self._fee(notional))):
                raise ServiceError("spot_corrupt", "spot order aggregate differs from confirmed fills", 503)
            if order["status"] == "FILLED" and quantity != Fraction(Decimal(order["quantity"])):
                raise ServiceError("spot_corrupt", "filled spot order retains unfilled quantity", 503)
            original = Fraction(Decimal(order["quantity"]))
            if (not original or abs(quantity) > abs(original) or quantity and (quantity > 0) != (original > 0)
                    or order["status"] in _LIVE and quantity == original):
                raise ServiceError("spot_corrupt", "spot cumulative fill exceeds its signed order", 503)
            if order["reserved_asset"] != (product.quote_asset if original > 0 else product.underlying):
                raise ServiceError("spot_corrupt", "spot order reservation asset differs from its side", 503)
            expected_asset, expected_amount = self._reservation(order) if order["status"] in _LIVE else (order["reserved_asset"], Decimal(0))
            if (order["reserved_asset"], Decimal(order["reserved_amount"])) != (expected_asset, expected_amount):
                raise ServiceError("spot_corrupt", "spot order lock differs from remaining obligation", 503)
        return {"matches": len(matches), "paired_fills": len(matches) * 2,
                "orders": len(orders), "ledger_events": ledger_events}

    def verify(self, *, connection=None) -> dict:
        """Inspect existing history without installing schema or changing guards."""
        try:
            if connection is None:
                with self.exchange.database.read_transaction() as connection:
                    return self._verify(connection)
            with self.exchange.database._using(connection) as connection:
                return self._verify(connection)
        except LedgerError as exc:
            raise ServiceError("ledger_rejected", str(exc), 409) from exc
        except sqlite3.OperationalError as exc:
            raise ServiceError("storage_unavailable", "storage transaction could not complete", 503) from exc
