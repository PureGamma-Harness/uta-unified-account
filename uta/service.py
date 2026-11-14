"""Durable, serialized UTA admission and settlement for linear USD contracts.

This is an internal order authority, not a venue adapter or matching engine.
Cancellation is final locally; it must not be interpreted as confirmation that
an order at an external venue was cancelled. Deposit and fill ingestion require
a trusted caller which has independently reconciled their external evidence.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal, Context, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
from hashlib import sha256
import json
import re
import sqlite3
from typing import Callable, Mapping

from .ledger import LedgerError, Posting
from .market import MarketSnapshot
from .models import RiskInputError
from .storage import Database, DurableLedger


class ServiceError(ValueError):
    """A rejected operation with a stable API error code and HTTP status."""

    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code, self.status = code, status


_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z", re.ASCII)
_ZERO = Decimal(0)
_MAX_INPUT = Decimal("1000000000000")
_LIVE = ("OPEN", "PARTIALLY_FILLED")


def _name(value: str, field: str) -> str:
    if not isinstance(value, str) or not _NAME.fullmatch(value):
        raise ServiceError("invalid_input", f"{field} must be a bounded ASCII identifier")
    return value


def _amount(value: Decimal, field: str, *, positive: bool = False,
            nonzero: bool = False) -> Decimal:
    if (not isinstance(value, Decimal) or not value.is_finite()
            or len(value.as_tuple().digits) > 32
            or not -8 <= value.as_tuple().exponent <= 12
            or value.copy_abs() > _MAX_INPUT):
        raise ServiceError("invalid_input", f"{field} requires a finite Decimal, at most 8 fractional digits and magnitude 1e12")
    if positive and value <= 0 or nonzero and value == 0:
        raise ServiceError("invalid_input", f"{field} must be {'positive' if positive else 'nonzero'}")
    return value


def _text(value: Decimal) -> str:
    if not value:
        return "0"
    result = format(value, "f")
    return result.rstrip("0").rstrip(".") if "." in result else result


def _exact(value: Fraction | int) -> Decimal:
    value = Fraction(value)
    denominator, twos, fives = value.denominator, 0, 0
    while denominator % 2 == 0:
        denominator //= 2
        twos += 1
    while denominator % 5 == 0:
        denominator //= 5
        fives += 1
    if denominator != 1:
        raise ServiceError("precision_error", "financial amount is not a terminating decimal", 409)
    scale = max(twos, fives)
    coefficient = value.numerator * 2 ** (scale - twos) * 5 ** (scale - fives)
    return Decimal((int(coefficient < 0), tuple(map(int, str(abs(coefficient)))), -scale))


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _key(kind: str, *parts: str) -> str:
    return kind + ":" + sha256(_json(parts).encode()).hexdigest()


class ExchangeService:
    """Single-database transaction boundary for accounts, orders and ledger.

    All writers, including independently constructed service instances, acquire
    SQLite's write lock before observing risk. The database is a single-node
    authority and must live on a local filesystem. It is not an HA consensus
    system. The global halt starts enabled and survives process restarts.
    """

    def __init__(self, database: Database, scales: Mapping[str, int], *,
                 max_price_age: timedelta = timedelta(seconds=5),
                 clock: Callable[[], datetime] | None = None,
                 fee_rate: Decimal = Decimal("0.0004")):
        if "USD" not in scales or type(scales["USD"]) is not int or not 2 <= scales["USD"] <= 8:
            raise ServiceError("invalid_configuration", "USD scale must be an integer from 2 through 8")
        if (not isinstance(max_price_age, timedelta) or max_price_age <= timedelta(0)
                or max_price_age > timedelta(minutes=5)):
            raise ServiceError("invalid_configuration", "max_price_age must be positive and at most five minutes")
        _amount(fee_rate, "fee_rate")
        if not _ZERO <= fee_rate <= Decimal("0.01"):
            raise ServiceError("invalid_configuration", "fee_rate must be between zero and 0.01")
        self.database = database
        self.scales = dict(scales)
        self.ledger = DurableLedger(database, scales)
        self.max_price_age, self.fee_rate = max_price_age, fee_rate
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        with database.transaction() as connection:
            self._schema(connection)
            # Verify before admitting any command after startup. Checking only
            # SQLite pages would miss a corrupted balance projection.
            self.ledger.verify(connection=connection)
            policy = _json({"fee_rate": _text(fee_rate), "usd_scale": scales["USD"],
                            "max_price_age_us": max_price_age // timedelta(microseconds=1),
                            "order_precision": 8})
            previous = connection.execute("SELECT value FROM uta_config WHERE key='policy'").fetchone()
            if previous is not None and previous["value"] != policy:
                raise ServiceError("configuration_conflict", "persisted trading policy differs from configured policy", 409)
            connection.execute("INSERT OR IGNORE INTO uta_config VALUES ('policy',?)", (policy,))
            connection.execute("INSERT OR IGNORE INTO uta_config VALUES ('halted','true')")

    @staticmethod
    def _schema(connection: sqlite3.Connection) -> None:
        statements = (
            "CREATE TABLE IF NOT EXISTS uta_schema (version INTEGER NOT NULL)",
            "CREATE TABLE IF NOT EXISTS uta_config (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
            "CREATE TABLE IF NOT EXISTS uta_accounts (account_id TEXT PRIMARY KEY, version INTEGER NOT NULL CHECK(version >= 0))",
            "CREATE TABLE IF NOT EXISTS uta_market (singleton INTEGER PRIMARY KEY CHECK(singleton=1), payload TEXT NOT NULL)",
            """CREATE TABLE IF NOT EXISTS uta_positions (
                account_id TEXT NOT NULL REFERENCES uta_accounts(account_id), symbol TEXT NOT NULL,
                quantity TEXT NOT NULL, cost_basis TEXT NOT NULL,
                PRIMARY KEY (account_id,symbol))""",
            """CREATE TABLE IF NOT EXISTS uta_orders (
                account_id TEXT NOT NULL REFERENCES uta_accounts(account_id), order_id TEXT NOT NULL,
                symbol TEXT NOT NULL, quantity TEXT NOT NULL, limit_price TEXT NOT NULL,
                reduce_only INTEGER NOT NULL CHECK(reduce_only IN (0,1)),
                filled_quantity TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('OPEN','PARTIALLY_FILLED','FILLED','CANCELLED')),
                version INTEGER NOT NULL, created_at TEXT NOT NULL,
                PRIMARY KEY(account_id,order_id))""",
            """CREATE TABLE IF NOT EXISTS uta_deposits (
                account_id TEXT NOT NULL REFERENCES uta_accounts(account_id), event_id TEXT NOT NULL,
                asset TEXT NOT NULL, amount TEXT NOT NULL, PRIMARY KEY(account_id,event_id))""",
            """CREATE TABLE IF NOT EXISTS uta_fills (
                account_id TEXT NOT NULL, fill_id TEXT NOT NULL, order_id TEXT NOT NULL,
                quantity TEXT NOT NULL, price TEXT NOT NULL, realized_pnl TEXT NOT NULL, fee TEXT NOT NULL,
                PRIMARY KEY(account_id,fill_id), FOREIGN KEY(account_id,order_id) REFERENCES uta_orders(account_id,order_id))""",
            """CREATE TABLE IF NOT EXISTS uta_events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL,
                account_id TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL)""",
            "CREATE INDEX IF NOT EXISTS uta_orders_live ON uta_orders(account_id,status)",
            "CREATE TRIGGER IF NOT EXISTS uta_events_no_update BEFORE UPDATE ON uta_events BEGIN SELECT RAISE(ABORT,'events are immutable'); END",
            "CREATE TRIGGER IF NOT EXISTS uta_events_no_delete BEFORE DELETE ON uta_events BEGIN SELECT RAISE(ABORT,'events are immutable'); END",
        )
        for statement in statements:
            connection.execute(statement)
        rows = connection.execute("SELECT version FROM uta_schema").fetchall()
        if not rows:
            connection.execute("INSERT INTO uta_schema VALUES (1)")
        elif len(rows) != 1 or rows[0]["version"] != 1:
            raise ServiceError("schema_version", "unsupported trading schema version", 503)

    @contextmanager
    def _transaction(self):
        try:
            with self.database.transaction() as connection:
                yield connection
        except LedgerError as exc:
            raise ServiceError("ledger_rejected", str(exc), 409) from exc
        except sqlite3.OperationalError as exc:
            raise ServiceError("storage_unavailable", "storage transaction could not complete", 503) from exc

    def _now(self) -> datetime:
        value = self.clock()
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ServiceError("invalid_clock", "service clock must return a timezone-aware datetime", 503)
        return value.astimezone(timezone.utc)

    def _event(self, connection, kind: str, account_id: str | None, payload: dict) -> None:
        connection.execute("INSERT INTO uta_events(event_type,account_id,payload,created_at) VALUES (?,?,?,?)",
                           (kind, account_id, _json(payload), self._now().isoformat()))

    @staticmethod
    def _customer(account_id: str) -> str:
        return "customer:" + account_id

    @staticmethod
    def _require_account(connection, account_id: str):
        row = connection.execute("SELECT * FROM uta_accounts WHERE account_id=?", (account_id,)).fetchone()
        if row is None:
            raise ServiceError("account_not_found", "unknown account", 404)
        return row

    @staticmethod
    def _bump(connection, account_id: str) -> int:
        connection.execute("UPDATE uta_accounts SET version=version+1 WHERE account_id=?", (account_id,))
        return connection.execute("SELECT version FROM uta_accounts WHERE account_id=?", (account_id,)).fetchone()["version"]

    def _market(self, connection, *, fresh: bool = True) -> MarketSnapshot:
        row = connection.execute("SELECT payload FROM uta_market WHERE singleton=1").fetchone()
        if row is None:
            raise ServiceError("market_unavailable", "no trusted market snapshot has been published", 503)
        try:
            snapshot = MarketSnapshot.from_json(row["payload"])
            if fresh:
                snapshot.validate(now=self._now(), max_age=self.max_price_age)
            return snapshot
        except RiskInputError as exc:
            raise ServiceError("market_unavailable", "trusted market snapshot is invalid or stale", 503) from exc

    def _rounded(self, value: Fraction, *, ceiling: bool = False) -> Decimal:
        units = value * 10 ** self.scales["USD"]
        integer = -((-units.numerator) // units.denominator) if ceiling else units.numerator // units.denominator
        return Decimal((int(integer < 0), tuple(map(int, str(abs(integer)))), -self.scales["USD"]))

    def _fee(self, quantity: Decimal, price: Decimal) -> Decimal:
        return self._rounded(abs(Fraction(quantity)) * Fraction(price) * Fraction(self.fee_rate), ceiling=True)

    def _fill_fee(self, connection, account_id: str, order_id: str,
                  quantity: Decimal, price: Decimal) -> Decimal:
        notional = abs(Fraction(quantity)) * Fraction(price)
        charged = Fraction(0)
        for fill in connection.execute("SELECT quantity,price,fee FROM uta_fills WHERE account_id=? AND order_id=?", (account_id, order_id)):
            notional += abs(Fraction(Decimal(fill["quantity"]))) * Fraction(Decimal(fill["price"]))
            charged += Fraction(Decimal(fill["fee"]))
        # Rounding applies to cumulative order notional, making the total fee
        # invariant to fragmentation into microscopic partial executions.
        return _exact(Fraction(self._rounded(notional * Fraction(self.fee_rate), ceiling=True)) - charged)

    def _positions(self, connection, account_id: str) -> dict:
        return {row["symbol"]: (Decimal(row["quantity"]), Decimal(row["cost_basis"]))
                for row in connection.execute("SELECT * FROM uta_positions WHERE account_id=? ORDER BY symbol", (account_id,))}

    @staticmethod
    def _live_orders(connection, account_id: str):
        return connection.execute("SELECT * FROM uta_orders WHERE account_id=? AND status IN ('OPEN','PARTIALLY_FILLED') ORDER BY rowid", (account_id,)).fetchall()

    def _reserve(self, order, market: MarketSnapshot) -> Decimal:
        remaining = Fraction(Decimal(order["quantity"])) - Fraction(Decimal(order["filled_quantity"]))
        try:
            spec = market.instruments[order["symbol"]]
        except KeyError as exc:
            raise ServiceError("market_incomplete", "missing instrument for an outstanding order", 503) from exc
        mark, limit = Fraction(spec.mark_price), Fraction(Decimal(order["limit_price"]))
        loss = max(Fraction(0), remaining * (limit - mark))
        im = Fraction(0) if order["reduce_only"] else abs(remaining) * max(mark, limit) * Fraction(spec.initial_margin_rate)
        # ceil(total fee)-already charged is <= ceil(remaining worst fee).
        fee = Fraction(self._fee(_exact(remaining), Decimal(order["limit_price"])))
        return _exact(im + loss + fee)

    def _risk(self, connection, account_id: str, market: MarketSnapshot, *,
              positions: dict | None = None, balance_delta: Decimal = _ZERO,
              reserve_exclude: str | None = None) -> dict:
        balances = {asset: self.ledger.balance(self._customer(account_id), asset, connection=connection)
                    for asset in self.scales}
        balances["USD"] = _exact(Fraction(balances["USD"]) + Fraction(balance_delta))
        equity = Fraction(0)
        for asset, balance in balances.items():
            if not balance:
                continue
            if asset not in market.assets:
                raise ServiceError("market_incomplete", "missing collateral specification for account balance", 503)
            spec = market.assets[asset]
            equity += Fraction(balance) * Fraction(spec.price) * (Fraction(spec.collateral_factor) if balance > 0 else 1)
        im, mm = Fraction(0), Fraction(0)
        for symbol, (quantity, cost) in (self._positions(connection, account_id) if positions is None else positions).items():
            if symbol not in market.instruments:
                raise ServiceError("market_incomplete", "missing instrument specification for account position", 503)
            spec = market.instruments[symbol]
            equity += Fraction(quantity) * Fraction(spec.mark_price) - Fraction(cost)
            notional = abs(Fraction(quantity)) * Fraction(spec.mark_price)
            im += notional * Fraction(spec.initial_margin_rate)
            mm += notional * Fraction(spec.maintenance_margin_rate)
        reserve = sum((Fraction(self._reserve(order, market)) for order in self._live_orders(connection, account_id)
                       if order["order_id"] != reserve_exclude), Fraction(0))
        with localcontext(Context(prec=34, rounding=ROUND_HALF_EVEN)):
            ratio = _text(Decimal(equity.numerator * mm.denominator) / Decimal(equity.denominator * mm.numerator)) if mm else None
        account_version = self._require_account(connection, account_id)["version"]
        return {"account_version": account_version, "equity": _text(_exact(equity)), "initial_margin": _text(_exact(im)),
                "maintenance_margin": _text(_exact(mm)), "open_order_margin": _text(_exact(reserve)),
                "available_margin": _text(_exact(equity - im - reserve)), "margin_ratio": ratio,
                "market_version": market.version, "observed_at": market.observed_at.isoformat()}

    def _order(self, row, market: MarketSnapshot | None = None) -> dict:
        result = {key: row[key] for key in ("account_id", "order_id", "symbol", "quantity", "limit_price",
                                           "filled_quantity", "status", "version", "created_at")}
        result["reduce_only"] = bool(row["reduce_only"])
        result["reserved_margin"] = _text(self._reserve(row, market)) if market is not None and row["status"] in _LIVE else "0"
        return result

    def _account(self, connection, account_id: str) -> dict:
        row = self._require_account(connection, account_id)
        balances = {asset: _text(self.ledger.balance(self._customer(account_id), asset, connection=connection)) for asset in sorted(self.scales)}
        positions = {}
        for symbol, (quantity, cost) in self._positions(connection, account_id).items():
            with localcontext(Context(prec=34, rounding=ROUND_HALF_EVEN)):
                entry = cost / quantity
            positions[symbol] = {"quantity": _text(quantity), "entry_price": _text(entry), "cost_basis": _text(cost)}
        reserve = Fraction(0)
        if self._live_orders(connection, account_id):
            market = self._market(connection, fresh=False)
            reserve = sum((Fraction(self._reserve(order, market)) for order in self._live_orders(connection, account_id)), Fraction(0))
        return {"account_id": account_id, "version": row["version"], "balances": balances,
                "positions": positions, "open_order_margin": _text(_exact(reserve))}

    def create_account(self, account_id: str) -> dict:
        _name(account_id, "account_id")
        with self._transaction() as connection:
            if connection.execute("SELECT 1 FROM uta_accounts WHERE account_id=?", (account_id,)).fetchone() is None:
                connection.execute("INSERT INTO uta_accounts VALUES (?,0)", (account_id,))
                self._event(connection, "ACCOUNT_CREATED", account_id, {"account_id": account_id})
            return self._account(connection, account_id)

    def publish_market(self, snapshot: MarketSnapshot) -> dict:
        if not isinstance(snapshot, MarketSnapshot):
            raise ServiceError("invalid_input", "market must be a MarketSnapshot")
        try:
            snapshot.validate(now=self._now(), max_age=self.max_price_age)
        except RiskInputError as exc:
            raise ServiceError("invalid_market", str(exc)) from exc
        usd = snapshot.assets.get("USD")
        if usd is None or usd.price != 1 or usd.collateral_factor != 1:
            raise ServiceError("invalid_market", "USD settlement requires price and collateral_factor equal to one")
        if any(spec.maintenance_margin_rate <= 0 or spec.initial_margin_rate <= 0
               for spec in snapshot.instruments.values()):
            raise ServiceError("invalid_market", "trading instruments require strictly positive maintenance and initial margin rates")
        payload = snapshot.to_json()
        with self._transaction() as connection:
            # A queued publisher may have waited for another writer; freshness
            # is a commit-time admission condition, not just a parse-time one.
            try:
                snapshot.validate(now=self._now(), max_age=self.max_price_age)
            except RiskInputError as exc:
                raise ServiceError("invalid_market", str(exc)) from exc
            previous_row = connection.execute("SELECT payload FROM uta_market WHERE singleton=1").fetchone()
            if previous_row is not None:
                previous = MarketSnapshot.from_json(previous_row["payload"])
                if snapshot.version < previous.version or snapshot.observed_at < previous.observed_at:
                    raise ServiceError("market_regression", "market version or timestamp regressed", 409)
                if snapshot.version == previous.version:
                    if payload != previous_row["payload"]:
                        raise ServiceError("market_conflict", "market version reused with different content", 409)
                    return {"version": snapshot.version, "observed_at": snapshot.observed_at.isoformat()}
            for row in connection.execute("SELECT DISTINCT symbol FROM uta_positions UNION SELECT DISTINCT symbol FROM uta_orders WHERE status IN ('OPEN','PARTIALLY_FILLED')"):
                if row["symbol"] not in snapshot.instruments:
                    raise ServiceError("market_incomplete", "cannot remove a live instrument specification", 409)
            # Positive funded assets need pricing even when no positions exist.
            for account in connection.execute("SELECT account_id FROM uta_accounts"):
                for asset in self.scales:
                    if (asset not in snapshot.assets and
                            self.ledger.balance(self._customer(account["account_id"]), asset, connection=connection)):
                        raise ServiceError("market_incomplete", "cannot remove funded collateral specification", 409)
            connection.execute("INSERT INTO uta_market VALUES (1,?) ON CONFLICT(singleton) DO UPDATE SET payload=excluded.payload", (payload,))
            result = {"version": snapshot.version, "observed_at": snapshot.observed_at.isoformat()}
            self._event(connection, "MARKET_PUBLISHED", None, result)
            return result

    def deposit(self, account_id: str, event_id: str, asset: str, amount: Decimal) -> dict:
        for value, field in ((account_id, "account_id"), (event_id, "event_id"), (asset, "asset")):
            _name(value, field)
        _amount(amount, "amount", positive=True)
        if asset not in self.scales:
            raise ServiceError("unknown_asset", "asset is not configured")
        amount_text = _text(amount)
        with self._transaction() as connection:
            self._require_account(connection, account_id)
            previous = connection.execute("SELECT * FROM uta_deposits WHERE account_id=? AND event_id=?", (account_id, event_id)).fetchone()
            if previous:
                if previous["asset"] != asset or previous["amount"] != amount_text:
                    raise ServiceError("idempotency_conflict", "deposit ID was reused with different content", 409)
                return self._account(connection, account_id)
            self.ledger.post(_key("deposit", account_id, event_id),
                             [Posting(self._customer(account_id), asset, amount),
                              Posting("system:custody", asset, _exact(-Fraction(amount)))], connection=connection)
            connection.execute("INSERT INTO uta_deposits VALUES (?,?,?,?)", (account_id, event_id, asset, amount_text))
            version = self._bump(connection, account_id)
            self._event(connection, "DEPOSIT_POSTED", account_id,
                        {"event_id": event_id, "asset": asset, "amount": amount_text, "version": version})
            return self._account(connection, account_id)

    def account(self, account_id: str) -> dict:
        _name(account_id, "account_id")
        with self._transaction() as connection:
            return self._account(connection, account_id)

    def accounts(self) -> list[dict]:
        """Return one transactionally consistent local supervisor account list."""
        with self._transaction() as connection:
            return [self._account(connection, row["account_id"])
                    for row in connection.execute("SELECT account_id FROM uta_accounts ORDER BY account_id").fetchall()]

    def risk(self, account_id: str) -> dict:
        _name(account_id, "account_id")
        with self._transaction() as connection:
            self._require_account(connection, account_id)
            return self._risk(connection, account_id, self._market(connection))

    def submit_order(self, account_id: str, order_id: str, symbol: str,
                     quantity: Decimal, limit_price: Decimal, *, reduce_only: bool = False) -> dict:
        for value, field in ((account_id, "account_id"), (order_id, "order_id"), (symbol, "symbol")):
            _name(value, field)
        _amount(quantity, "quantity", nonzero=True)
        _amount(limit_price, "limit_price", positive=True)
        if type(reduce_only) is not bool:
            raise ServiceError("invalid_input", "reduce_only must be a boolean")
        quantity_text, price_text = _text(quantity), _text(limit_price)
        with self._transaction() as connection:
            self._require_account(connection, account_id)
            previous = connection.execute("SELECT * FROM uta_orders WHERE account_id=? AND order_id=?", (account_id, order_id)).fetchone()
            if previous:
                if (previous["symbol"], previous["quantity"], previous["limit_price"], bool(previous["reduce_only"])) != (symbol, quantity_text, price_text, reduce_only):
                    raise ServiceError("idempotency_conflict", "order ID was reused with different content", 409)
                return self._order(previous, self._market(connection, fresh=False))
            market = self._market(connection)
            if symbol not in market.instruments:
                raise ServiceError("unknown_instrument", "instrument is not in the trusted market snapshot")
            halted = connection.execute("SELECT value FROM uta_config WHERE key='halted'").fetchone()["value"] == "true"
            if halted and not reduce_only:
                raise ServiceError("trading_halted", "new exposure is halted", 409)
            live = self._live_orders(connection, account_id)
            if len(live) >= 1000:
                raise ServiceError("order_limit", "account has too many outstanding orders", 409)
            proposed = {"symbol": symbol, "quantity": quantity_text, "filled_quantity": "0",
                        "limit_price": price_text, "reduce_only": reduce_only}
            reserve = self._reserve(proposed, market)
            current = self._risk(connection, account_id, market)
            positions = self._positions(connection, account_id)
            old_quantity = positions.get(symbol, (_ZERO, _ZERO))[0]
            if reduce_only:
                held = sum((abs(Fraction(Decimal(order["quantity"])) - Fraction(Decimal(order["filled_quantity"])))
                            for order in live if order["symbol"] == symbol and order["reduce_only"]), Fraction(0))
                if not old_quantity or (quantity > 0) == (old_quantity > 0) or held + abs(Fraction(quantity)) > abs(Fraction(old_quantity)):
                    raise ServiceError("reduce_only_violation", "reduce-only quantity exceeds unreserved position", 409)
                next_positions, pnl = self._project_fill(positions, symbol, quantity, limit_price)
                fee = self._fee(quantity, limit_price)
                projected = self._risk(connection, account_id, market, positions=next_positions,
                                       balance_delta=_exact(Fraction(pnl) - Fraction(fee)))
                self._check_reduction_surplus(current, projected)
            elif Fraction(Decimal(current["available_margin"])) < Fraction(reserve):
                raise ServiceError("insufficient_margin", "insufficient available margin for order and fee reserve", 409)
            version = self._bump(connection, account_id)
            connection.execute("INSERT INTO uta_orders VALUES (?,?,?,?,?,?,?,'OPEN',?,?)",
                               (account_id, order_id, symbol, quantity_text, price_text, int(reduce_only), "0", version, self._now().isoformat()))
            result = self._order(connection.execute("SELECT * FROM uta_orders WHERE account_id=? AND order_id=?", (account_id, order_id)).fetchone(), market)
            self._event(connection, "ORDER_ACCEPTED", account_id, result)
            return result

    @staticmethod
    def _check_reduction_surplus(current: dict, projected: dict) -> None:
        before = Fraction(Decimal(current["equity"])) - Fraction(Decimal(current["maintenance_margin"]))
        after = Fraction(Decimal(projected["equity"])) - Fraction(Decimal(projected["maintenance_margin"]))
        if after < before:
            raise ServiceError("unsafe_reduction", "reduce-only execution would worsen maintenance margin surplus", 409)

    def cancel_order(self, account_id: str, order_id: str) -> dict:
        _name(account_id, "account_id")
        _name(order_id, "order_id")
        with self._transaction() as connection:
            self._require_account(connection, account_id)
            row = connection.execute("SELECT * FROM uta_orders WHERE account_id=? AND order_id=?", (account_id, order_id)).fetchone()
            if row is None:
                raise ServiceError("order_not_found", "unknown order", 404)
            if row["status"] in _LIVE:
                version = self._bump(connection, account_id)
                connection.execute("UPDATE uta_orders SET status='CANCELLED',version=? WHERE account_id=? AND order_id=?", (version, account_id, order_id))
                row = connection.execute("SELECT * FROM uta_orders WHERE account_id=? AND order_id=?", (account_id, order_id)).fetchone()
                self._event(connection, "ORDER_CANCELLED", account_id, self._order(row))
            return self._order(row)

    def _project_fill(self, positions: dict, symbol: str, quantity: Decimal, price: Decimal) -> tuple[dict, Decimal]:
        result = dict(positions)
        old_quantity, old_cost = result.get(symbol, (_ZERO, _ZERO))
        old, fill, execution = Fraction(old_quantity), Fraction(quantity), Fraction(price)
        next_quantity, pnl = old + fill, Fraction(0)
        if abs(next_quantity) > Fraction(_MAX_INPUT):
            raise ServiceError("position_limit", "position magnitude exceeds supported limit", 409)
        if not old or (old > 0) == (fill > 0):
            cost = Fraction(old_cost) + fill * execution
        else:
            sign = 1 if old > 0 else -1
            closed = min(abs(old), abs(fill))
            # A tiny surviving basis can cross zero when settlement dust is
            # carried forward; its sign must be preserved on the next close.
            exact_pnl = sign * closed * execution - Fraction(old_cost) * closed / abs(old)
            pnl = Fraction(self._rounded(exact_pnl))
            if abs(fill) < abs(old):
                # Keep settlement rounding dust in the surviving cost basis.
                cost = Fraction(old_cost) - sign * closed * execution + pnl
            elif next_quantity:
                cost = next_quantity * execution
            else:
                cost = Fraction(0)
        if next_quantity:
            result[symbol] = (_exact(next_quantity), _exact(cost))
        else:
            result.pop(symbol, None)
        return result, _exact(pnl)

    def apply_fill(self, account_id: str, order_id: str, fill_id: str,
                   quantity: Decimal, price: Decimal) -> dict:
        """Authorize and settle a local execution atomically.

        This is not an ingestion endpoint for an execution already made at an
        external venue: local terminal-order and reduce-only checks can reject
        the command. External execution must never precede this authorization.
        """
        for value, field in ((account_id, "account_id"), (order_id, "order_id"), (fill_id, "fill_id")):
            _name(value, field)
        _amount(quantity, "quantity", nonzero=True)
        _amount(price, "price", positive=True)
        qtext, ptext = _text(quantity), _text(price)
        with self._transaction() as connection:
            self._require_account(connection, account_id)
            row = connection.execute("SELECT * FROM uta_orders WHERE account_id=? AND order_id=?", (account_id, order_id)).fetchone()
            if row is None:
                raise ServiceError("order_not_found", "unknown order", 404)
            previous = connection.execute("SELECT * FROM uta_fills WHERE account_id=? AND fill_id=?", (account_id, fill_id)).fetchone()
            if previous:
                if (previous["order_id"], previous["quantity"], previous["price"]) != (order_id, qtext, ptext):
                    raise ServiceError("idempotency_conflict", "fill ID was reused with different content", 409)
                return self._order(row, self._market(connection, fresh=False))
            if row["status"] not in _LIVE:
                raise ServiceError("order_closed", "cannot fill a terminal order", 409)
            remaining = Fraction(Decimal(row["quantity"])) - Fraction(Decimal(row["filled_quantity"]))
            if (quantity > 0) != (remaining > 0) or abs(Fraction(quantity)) > abs(remaining):
                raise ServiceError("invalid_fill", "fill quantity has wrong sign or exceeds remaining order", 409)
            limit = Decimal(row["limit_price"])
            if quantity > 0 and price > limit or quantity < 0 and price < limit:
                raise ServiceError("invalid_fill", "fill price violates order limit", 409)
            positions = self._positions(connection, account_id)
            next_positions, pnl = self._project_fill(positions, row["symbol"], quantity, price)
            fee = self._fill_fee(connection, account_id, order_id, quantity, price)
            market = self._market(connection, fresh=bool(row["reduce_only"]))
            if row["reduce_only"]:
                old_quantity = positions.get(row["symbol"], (_ZERO, _ZERO))[0]
                if not old_quantity or (quantity > 0) == (old_quantity > 0) or abs(Fraction(quantity)) > abs(Fraction(old_quantity)):
                    raise ServiceError("reduce_only_violation", "fill would increase or reverse reduce-only position", 409)
                current = self._risk(connection, account_id, market)
                projected = self._risk(connection, account_id, market, positions=next_positions,
                                       balance_delta=_exact(Fraction(pnl) - Fraction(fee)))
                self._check_reduction_surplus(current, projected)
            postings = []
            if pnl:
                postings.extend((Posting(self._customer(account_id), "USD", pnl),
                                 Posting("system:realized-pnl", "USD", _exact(-Fraction(pnl)))))
            if fee:
                postings.extend((Posting(self._customer(account_id), "USD", _exact(-Fraction(fee))),
                                 Posting("system:fees", "USD", fee)))
            if postings:
                self.ledger.post(_key("fill", account_id, fill_id), postings, connection=connection)
            connection.execute("DELETE FROM uta_positions WHERE account_id=? AND symbol=?", (account_id, row["symbol"]))
            if row["symbol"] in next_positions:
                q, cost = next_positions[row["symbol"]]
                connection.execute("INSERT INTO uta_positions VALUES (?,?,?,?)", (account_id, row["symbol"], _text(q), _text(cost)))
            filled = _exact(Fraction(Decimal(row["filled_quantity"])) + Fraction(quantity))
            status = "FILLED" if filled == Decimal(row["quantity"]) else "PARTIALLY_FILLED"
            version = self._bump(connection, account_id)
            connection.execute("UPDATE uta_orders SET filled_quantity=?,status=?,version=? WHERE account_id=? AND order_id=?",
                               (_text(filled), status, version, account_id, order_id))
            connection.execute("INSERT INTO uta_fills VALUES (?,?,?,?,?,?,?)", (account_id, fill_id, order_id, qtext, ptext, _text(pnl), _text(fee)))
            updated = connection.execute("SELECT * FROM uta_orders WHERE account_id=? AND order_id=?", (account_id, order_id)).fetchone()
            result = self._order(updated, market)
            self._event(connection, "FILL_APPLIED", account_id,
                        {"fill_id": fill_id, "quantity": qtext, "price": ptext,
                         "realized_pnl": _text(pnl), "fee": _text(fee), "order": result})
            self._invalidate_reductions(connection, account_id, next_positions)
            return result

    def _invalidate_reductions(self, connection, account_id: str, positions: dict) -> None:
        used: dict[str, Fraction] = {}
        for row in self._live_orders(connection, account_id):
            if not row["reduce_only"]:
                continue
            symbol = row["symbol"]
            quantity = Fraction(Decimal(row["quantity"])) - Fraction(Decimal(row["filled_quantity"]))
            position = Fraction(positions.get(symbol, (_ZERO, _ZERO))[0])
            held = used.get(symbol, Fraction(0)) + abs(quantity)
            if not position or (position > 0) == (quantity > 0) or held > abs(position):
                version = self._bump(connection, account_id)
                connection.execute("UPDATE uta_orders SET status='CANCELLED',version=? WHERE account_id=? AND order_id=?", (version, account_id, row["order_id"]))
                event = self._order(connection.execute("SELECT * FROM uta_orders WHERE account_id=? AND order_id=?", (account_id, row["order_id"])).fetchone())
                event["reason"] = "position_changed"
                self._event(connection, "ORDER_CANCELLED", account_id, event)
            else:
                used[symbol] = held

    def orders(self, account_id: str) -> list[dict]:
        _name(account_id, "account_id")
        with self._transaction() as connection:
            self._require_account(connection, account_id)
            rows = connection.execute("SELECT * FROM uta_orders WHERE account_id=? ORDER BY rowid", (account_id,)).fetchall()
            market = self._market(connection, fresh=False) if rows else None
            return [self._order(row, market) for row in rows]

    def events(self, after: int = 0, limit: int = 100) -> list[dict]:
        if type(after) is not int or after < 0 or after > 2 ** 63 - 1 or type(limit) is not int or not 1 <= limit <= 1000:
            raise ServiceError("invalid_input", "event cursor must be nonnegative and limit must be 1..1000")
        with self._transaction() as connection:
            return [{"sequence": row["sequence"], "event_type": row["event_type"],
                     "account_id": row["account_id"], "payload": json.loads(row["payload"]),
                     "created_at": row["created_at"]} for row in connection.execute("SELECT * FROM uta_events WHERE sequence>? ORDER BY sequence LIMIT ?", (after, limit))]

    def set_kill_switch(self, enabled: bool) -> dict:
        if type(enabled) is not bool:
            raise ServiceError("invalid_input", "enabled must be a boolean")
        value = "true" if enabled else "false"
        with self._transaction() as connection:
            old = connection.execute("SELECT value FROM uta_config WHERE key='halted'").fetchone()["value"]
            if old != value:
                connection.execute("UPDATE uta_config SET value=? WHERE key='halted'", (value,))
                self._event(connection, "KILL_SWITCH_CHANGED", None, {"enabled": enabled})
            return {"enabled": enabled}

    def readiness(self) -> dict:
        try:
            with self._transaction() as connection:
                halted = connection.execute("SELECT value FROM uta_config WHERE key='halted'").fetchone()["value"] == "true"
                market = self._market(connection)
                return {"ready": not halted, "halted": halted, "market_version": market.version,
                        "reason": "trading_halted" if halted else "ready"}
        except (ServiceError, sqlite3.DatabaseError, LedgerError):
            return {"ready": False, "reason": "storage_or_market_unavailable"}
