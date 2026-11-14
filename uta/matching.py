"""Price/time matching and atomic two-sided settlement on the local authority.

Only accepted opposing limit orders can produce a trade. No execution is
fabricated from a mark. Selection, both authorization/settlement legs, the match
receipt and committed events share one SQLite transaction. This is a single-node
reference matching service, not a replicated matching engine or venue adapter.
"""
from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal
from fractions import Fraction
from hashlib import sha256
import json
import sqlite3
import time
from uuid import uuid4

from .service import ExchangeService, ServiceError, _exact, _key, _name, _text


_LIVE = ("OPEN", "PARTIALLY_FILLED")
_TRANSIENT = {"market_unavailable", "invalid_clock", "storage_unavailable", "trading_halted"}
_CANCEL_REJECTIONS = {"account_frozen", "insufficient_margin", "reduce_only_violation",
                      "unsafe_reduction", "position_limit", "order_closed", "invalid_fill"}


class Matcher:
    """Durable linear USD limit book sharing the ExchangeService authority.

    ``match_once`` is a bounded batch. The database write lock serializes book
    selection across workers and all account writers. Price/time priority uses
    numeric Decimal prices and the authority's insertion sequence (SQLite rowid),
    never a caller timestamp. No cross-database or multi-shard atomicity is claimed.
    """

    def __init__(self, exchange: ExchangeService, *, initialize: bool = True):
        if not isinstance(exchange, ExchangeService):
            raise ValueError("exchange must be an ExchangeService")
        if type(initialize) is not bool:
            raise ValueError("initialize must be boolean")
        self.exchange = exchange
        if not initialize:
            # Reconciliation must never recreate missing guards before checking
            # them, or its attempt to inspect corruption could mask the problem.
            return
        with exchange._transaction() as connection:
            for statement in (
                "CREATE TABLE IF NOT EXISTS uta_matching_schema (singleton INTEGER PRIMARY KEY CHECK(singleton=1),version INTEGER NOT NULL)",
                """CREATE TABLE IF NOT EXISTS uta_matches (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, trade_id TEXT NOT NULL UNIQUE,
                    symbol TEXT NOT NULL, buy_account_id TEXT NOT NULL, buy_order_id TEXT NOT NULL,
                    buy_fill_id TEXT NOT NULL, sell_account_id TEXT NOT NULL, sell_order_id TEXT NOT NULL,
                    sell_fill_id TEXT NOT NULL, buy_filled_before TEXT NOT NULL,
                    sell_filled_before TEXT NOT NULL, quantity TEXT NOT NULL, price TEXT NOT NULL,
                    market_version INTEGER NOT NULL, buy_version INTEGER NOT NULL,
                    sell_version INTEGER NOT NULL, created_at TEXT NOT NULL,
                    UNIQUE(buy_account_id,buy_fill_id), UNIQUE(sell_account_id,sell_fill_id),
                    FOREIGN KEY(buy_account_id,buy_fill_id) REFERENCES uta_fills(account_id,fill_id),
                    FOREIGN KEY(sell_account_id,sell_fill_id) REFERENCES uta_fills(account_id,fill_id))""",
                """CREATE TRIGGER IF NOT EXISTS uta_matches_no_update BEFORE UPDATE ON uta_matches
                    BEGIN SELECT RAISE(ABORT,'match receipts are immutable'); END""",
                """CREATE TRIGGER IF NOT EXISTS uta_matches_no_delete BEFORE DELETE ON uta_matches
                    BEGIN SELECT RAISE(ABORT,'match receipts are immutable'); END""",
                "CREATE INDEX IF NOT EXISTS uta_matches_symbol ON uta_matches(symbol,sequence)",
            ):
                connection.execute(statement)
            row = connection.execute("SELECT version FROM uta_matching_schema WHERE singleton=1").fetchone()
            if row is None:
                connection.execute("INSERT INTO uta_matching_schema VALUES (1,1)")
            elif row["version"] != 1:
                raise ServiceError("matching_schema_version", "unsupported matching schema", 503)

    @staticmethod
    def _remaining(row) -> Fraction:
        return Fraction(Decimal(row["quantity"])) - Fraction(Decimal(row["filled_quantity"]))

    @staticmethod
    def _identity(symbol: str, buy, sell, quantity: Decimal, price: Decimal) -> str:
        values = [symbol, buy["account_id"], buy["order_id"], sell["account_id"], sell["order_id"],
                  buy["filled_quantity"], sell["filled_quantity"], _text(quantity), _text(price)]
        return sha256(json.dumps(values, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()

    @staticmethod
    def _receipt(row) -> dict:
        return dict(row)

    def match_once(self, symbol: str, max_matches: int = 100) -> dict:
        """Settle up to ``max_matches`` unique two-sided trades.

        A transient halt or stale market preserves queued orders. A per-account
        execution rejection rolls back both legs and cancels only the rejected
        order with an audit reason. Self-trade prevention cancels the newer order.
        Unexpected storage/logic failures abort the whole batch; no false success
        receipt is returned. Orders are not externally sent before this commit.
        """
        _name(symbol, "symbol")
        if type(max_matches) is not int or not 1 <= max_matches <= 1000:
            raise ServiceError("invalid_input", "max_matches must be an integer in 1..1000")
        result = {"symbol": symbol, "trades": [], "confirmed_trades": 0,
                  "cancelled_orders": [], "blocked": [], "market_version": None,
                  "attempts": 0, "batch_exhausted": False}
        with self.exchange._transaction() as connection:
            try:
                market = self.exchange._market(connection)
            except ServiceError as exc:
                if exc.code not in _TRANSIENT:
                    raise
                result["blocked"].append({"code": exc.code})
                return result
            if symbol not in market.instruments:
                raise ServiceError("unknown_instrument", "instrument is not in the trusted market snapshot")
            result["market_version"] = market.version
            # An adversarial book full of invalid/self-crossing orders must not
            # hold the global write authority indefinitely.
            budget = max_matches * 2 + 1
            while result["confirmed_trades"] < max_matches and result["attempts"] < budget:
                rows = connection.execute("""SELECT rowid AS book_sequence,* FROM uta_orders
                    WHERE symbol=? AND status IN ('OPEN','PARTIALLY_FILLED')""", (symbol,)).fetchall()
                buys = sorted((row for row in rows if self._remaining(row) > 0),
                              key=lambda row: (-Fraction(Decimal(row["limit_price"])), row["book_sequence"]))
                sells = sorted((row for row in rows if self._remaining(row) < 0),
                               key=lambda row: (Fraction(Decimal(row["limit_price"])), row["book_sequence"]))
                if not buys or not sells:
                    break
                buy, sell = buys[0], sells[0]
                if Decimal(buy["limit_price"]) < Decimal(sell["limit_price"]):
                    break
                result["attempts"] += 1
                if buy["account_id"] == sell["account_id"]:
                    taker = buy if buy["book_sequence"] > sell["book_sequence"] else sell
                    cancelled = self.exchange._cancel_locked(connection, taker, "self_trade_prevention")
                    result["cancelled_orders"].append(dict(cancelled, reason="self_trade_prevention"))
                    continue
                quantity = _exact(min(self._remaining(buy), -self._remaining(sell)))
                maker = buy if buy["book_sequence"] < sell["book_sequence"] else sell
                price = Decimal(maker["limit_price"])
                identity = self._identity(symbol, buy, sell, quantity, price)
                trade_id, buy_fill_id, sell_fill_id = "match:" + identity, "match:" + identity + ":b", "match:" + identity + ":s"
                if connection.execute("SELECT 1 FROM uta_matches WHERE trade_id=?", (trade_id,)).fetchone():
                    raise ServiceError("matching_corruption", "committed trade still has an unconsumed order state", 503)
                savepoint = "matching_" + uuid4().hex
                connection.execute(f"SAVEPOINT {savepoint}")
                rejected = buy
                try:
                    buy_order = self.exchange._apply_fill(connection, buy["account_id"], buy["order_id"],
                                                           buy_fill_id, quantity, price)
                    rejected = sell
                    sell_order = self.exchange._apply_fill(connection, sell["account_id"], sell["order_id"],
                                                            sell_fill_id, quantity.copy_negate(), price)
                    connection.execute("""INSERT INTO uta_matches (
                        trade_id,symbol,buy_account_id,buy_order_id,buy_fill_id,
                        sell_account_id,sell_order_id,sell_fill_id,buy_filled_before,sell_filled_before,
                        quantity,price,market_version,buy_version,sell_version,created_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (trade_id, symbol, buy["account_id"], buy["order_id"], buy_fill_id,
                         sell["account_id"], sell["order_id"], sell_fill_id, buy["filled_quantity"],
                         sell["filled_quantity"], _text(quantity), _text(price), market.version,
                         buy_order["version"], sell_order["version"], self.exchange._now().isoformat()))
                    receipt = self._receipt(connection.execute("SELECT * FROM uta_matches WHERE trade_id=?", (trade_id,)).fetchone())
                    self.exchange._event(connection, "MATCH_CONFIRMED", None, receipt)
                    for side, order, fill_id in (("buy", buy_order, buy_fill_id), ("sell", sell_order, sell_fill_id)):
                        # Private events identify the customer's own order; the
                        # counterparty account identity stays in operator audit.
                        self.exchange._event(connection, "TRADE_CONFIRMED", order["account_id"],
                                             {"trade_id": trade_id, "symbol": symbol, "side": side,
                                              "order_id": order["order_id"], "fill_id": fill_id,
                                              "quantity": _text(quantity), "price": _text(price),
                                              "market_version": market.version})
                    connection.execute(f"RELEASE SAVEPOINT {savepoint}")
                except ServiceError as exc:
                    connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                    connection.execute(f"RELEASE SAVEPOINT {savepoint}")
                    detail = {"code": exc.code, "account_id": rejected["account_id"],
                              "order_id": rejected["order_id"]}
                    result["blocked"].append(detail)
                    if exc.code in _TRANSIENT:
                        break
                    if exc.code not in _CANCEL_REJECTIONS:
                        raise
                    reason = "matching_rejected:" + exc.code
                    cancelled = self.exchange._cancel_locked(connection, rejected, reason)
                    result["cancelled_orders"].append(dict(cancelled, reason=reason))
                    continue
                # Other exceptions intentionally propagate so the encompassing
                # transaction rolls back all legs and any earlier batch trades.
                result["trades"].append(receipt)
                result["confirmed_trades"] += 1
            result["batch_exhausted"] = (result["confirmed_trades"] == max_matches
                                           or result["attempts"] == budget)
        return result

    def trades(self, after: int = 0, limit: int = 100) -> list[dict]:
        if (type(after) is not int or not 0 <= after <= 2**63 - 1
                or type(limit) is not int or not 1 <= limit <= 1000):
            raise ServiceError("invalid_input", "trade cursor must be nonnegative and limit in 1..1000")
        with self.exchange._transaction() as connection:
            return [self._receipt(row) for row in connection.execute(
                "SELECT * FROM uta_matches WHERE sequence>? ORDER BY sequence LIMIT ?", (after, limit))]

    def verify(self, *, strict: bool = False, connection: sqlite3.Connection | None = None) -> dict:
        """Reconcile receipts, both fills, orders, journals and match audit events.

        ``strict=True`` also rejects standalone manually authorized fills. This
        is useful for a matching-only acceptance database. Imported genesis
        positions are outside this check and need source-to-ledger reconciliation.
        """
        if type(strict) is not bool:
            raise ValueError("strict must be boolean")
        with self.exchange.database._using(connection) as connection:
            ledger_events = self.exchange.ledger.verify(connection=connection)
            schema = connection.execute("SELECT version FROM uta_matching_schema WHERE singleton=1").fetchone()
            if schema is None or schema["version"] != 1:
                raise ServiceError("matching_corruption", "matching schema version is invalid", 503)
            triggers = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
            if not {"uta_matches_no_update", "uta_matches_no_delete"} <= triggers:
                raise ServiceError("matching_corruption", "match receipt protection is missing", 503)
            rows = connection.execute("SELECT * FROM uta_matches ORDER BY sequence").fetchall()
            paired = set()
            events = connection.execute("SELECT payload FROM uta_events WHERE event_type='MATCH_CONFIRMED'").fetchall()
            try:
                event_payloads = [json.loads(row["payload"]) for row in events]
                event_ids = [payload["trade_id"] for payload in event_payloads]
                event_counts = Counter(event_ids)
                audit = {payload["trade_id"]: payload for payload in event_payloads}
                private = {}
                for row in connection.execute("SELECT account_id,payload FROM uta_events WHERE event_type='TRADE_CONFIRMED'"):
                    payload = json.loads(row["payload"])
                    key = row["account_id"], payload["fill_id"]
                    if key in private:
                        raise ValueError("duplicate private trade confirmation")
                    private[key] = payload
            except (ValueError, KeyError, TypeError) as exc:
                raise ServiceError("matching_corruption", "match audit payload is invalid", 503) from exc
            journal = {event.event_id: event for event in self.exchange.ledger.journal(connection=connection)}
            for expected, match in enumerate(rows, 1):
                quantity, price = Decimal(match["quantity"]), Decimal(match["price"])
                if (match["sequence"] != expected or quantity <= 0 or price <= 0
                        or match["buy_account_id"] == match["sell_account_id"]
                        or event_counts[match["trade_id"]] != 1
                        or audit[match["trade_id"]] != dict(match)):
                    raise ServiceError("matching_corruption", "match sequence, quantity or audit correspondence failed", 503)
                original_buy = {"account_id": match["buy_account_id"], "order_id": match["buy_order_id"],
                                "filled_quantity": match["buy_filled_before"]}
                original_sell = {"account_id": match["sell_account_id"], "order_id": match["sell_order_id"],
                                 "filled_quantity": match["sell_filled_before"]}
                identity = self._identity(match["symbol"], original_buy, original_sell, quantity, price)
                if (match["trade_id"] != "match:" + identity or match["buy_fill_id"] != "match:" + identity + ":b"
                        or match["sell_fill_id"] != "match:" + identity + ":s"):
                    raise ServiceError("matching_corruption", "match business identifiers disagree with their canonical inputs", 503)
                for side, signed in (("buy", quantity), ("sell", quantity.copy_negate())):
                    account_id, order_id, fill_id = (match[side + "_account_id"], match[side + "_order_id"], match[side + "_fill_id"])
                    fill = connection.execute("SELECT * FROM uta_fills WHERE account_id=? AND fill_id=?", (account_id, fill_id)).fetchone()
                    order = connection.execute("SELECT * FROM uta_orders WHERE account_id=? AND order_id=?", (account_id, order_id)).fetchone()
                    if (fill is None or order is None or fill["order_id"] != order_id or order["symbol"] != match["symbol"]
                            or Decimal(fill["quantity"]) != signed or Decimal(fill["price"]) != price
                            or (side == "buy" and price > Decimal(order["limit_price"]))
                            or (side == "sell" and price < Decimal(order["limit_price"]))):
                        raise ServiceError("matching_corruption", "match does not correspond to both order/fill sides", 503)
                    if (account_id, fill_id) in paired:
                        raise ServiceError("matching_corruption", "one fill belongs to more than one match", 503)
                    paired.add((account_id, fill_id))
                    expected_private = {"trade_id": match["trade_id"], "symbol": match["symbol"], "side": side,
                                        "order_id": order_id, "fill_id": fill_id, "quantity": match["quantity"],
                                        "price": match["price"], "market_version": match["market_version"]}
                    if private.get((account_id, fill_id)) != expected_private:
                        raise ServiceError("matching_corruption", "private trade confirmation differs from its match", 503)
                    pnl, fee = Decimal(fill["realized_pnl"]), Decimal(fill["fee"])
                    event = journal.get(_key("fill", account_id, fill_id))
                    expected_postings = []
                    if pnl:
                        expected_postings += [(self.exchange._customer(account_id), "USD", Fraction(pnl)),
                                              ("system:realized-pnl", "USD", -Fraction(pnl))]
                    if fee:
                        expected_postings += [(self.exchange._customer(account_id), "USD", -Fraction(fee)),
                                              ("system:fees", "USD", Fraction(fee))]
                    actual = sorted((posting.account, posting.asset, Fraction(posting.amount)) for posting in event.postings) if event else []
                    if actual != sorted(expected_postings):
                        raise ServiceError("matching_corruption", "match fill and journal postings disagree", 503)
            if set(event_ids) != {row["trade_id"] for row in rows}:
                raise ServiceError("matching_corruption", "orphaned match audit event", 503)
            if set(private) != paired:
                raise ServiceError("matching_corruption", "orphaned private trade confirmation", 503)
            total_fills = connection.execute("SELECT COUNT(*) FROM uta_fills").fetchone()[0]
            unpaired = total_fills - len(paired)
            if strict and unpaired:
                raise ServiceError("unpaired_execution", "standalone fills exist outside the paired matching authority", 503)
            return {"matches": len(rows), "paired_fills": len(paired), "unpaired_fills": unpaired,
                    "ledger_events": ledger_events}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local durable linear matching authority; no venue connection")
    parser.add_argument("--database", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--asset-scale", action="append", default=[], metavar="ASSET=DIGITS")
    parser.add_argument("--catalog", help="same persisted product catalog as the account authority")
    parser.add_argument("--risk-rules", help="same persisted Cross policy as the account authority")
    parser.add_argument("--max-matches", type=int, default=100)
    parser.add_argument("--loop", action="store_true", help="poll the local book until interrupted")
    parser.add_argument("--interval", type=float, default=.1)
    args = parser.parse_args(argv)
    from .__main__ import _scales
    from .storage import Database, StorageError
    from .configuration import load_policy
    try:
        if not .01 <= args.interval <= 60:
            raise ValueError("interval must be in .01..60 seconds")
        matcher = Matcher(ExchangeService(Database(args.database), _scales(args.asset_scale),
                                         **load_policy(args.catalog, args.risk_rules)))
        while True:
            print(json.dumps(matcher.match_once(args.symbol, args.max_matches), separators=(",", ":")), flush=True)
            if not args.loop:
                return 0
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0
    except (ValueError, StorageError, OSError, sqlite3.Error) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
