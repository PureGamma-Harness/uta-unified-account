"""Local WAL/FULL command inbox, distinct from financial risk acceptance.

Enqueue and query use restricted metadata transactions. Only a managed, fenced
writer can execute: business changes and the terminal receipt share one commit.
"""
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import json
import math
from typing import Mapping

from .admission import _business_rejection
from .credit import CreditService
from .failure_diagnostics import capture_failure
from .ledger import Ledger, LedgerError
from .market import MarketSnapshot
from .models import RiskInputError
from .service import ExchangeService, ServiceError, _amount, _json, _name, _text
from .storage import Database, StorageError


SUBMIT_ORDER = "SUBMIT_ORDER"
CANCEL_ORDER = "CANCEL_ORDER"
PUBLISH_MARKET = "PUBLISH_MARKET"
SET_HALT = "SET_HALT"
REPAY = "REPAY"
_CONTROL = (PUBLISH_MARKET, SET_HALT)
_TERMINAL = ("SUCCEEDED", "REJECTED", "QUARANTINED")
_FIELDS = {
    SUBMIT_ORDER: {"account_id", "order_id", "symbol", "quantity", "limit_price", "reduce_only"},
    CANCEL_ORDER: {"account_id", "order_id"},
    PUBLISH_MARKET: {"snapshot"}, SET_HALT: {"enabled"},
    REPAY: {"account_id", "asset", "amount"},
}
_TRIGGER_NAMES = {
    "uta_command_config_no_replace", "uta_command_config_no_update", "uta_command_config_no_delete",
    "uta_command_inbox_pending_insert", "uta_command_inbox_no_replace",
    "uta_command_inbox_identity_immutable", "uta_command_inbox_terminal_immutable", "uta_command_inbox_no_delete",
}
_TABLE_COLUMNS = {
    "uta_command_config": {"singleton", "format", "queue_capacity", "cancel_reserve", "market_capacity"},
    "uta_command_inbox": {"sequence", "command_id", "account_id", "kind", "payload", "state", "result", "error",
                          "enqueued_at", "completed_at", "attempts", "last_error", "next_attempt_at"},
}


class CommandExecutionError(RuntimeError):
    """No terminal receipt was observed; query the original command ID first."""

    def __init__(self, command_id, sequence, cause, *, attempt=None):
        super().__init__("command execution receipt unavailable; query the original command ID")
        self.command_id, self.sequence, self.cause = command_id, sequence, cause
        self.attempt = attempt


def _stamp(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ServiceError("invalid_clock", "inbox clock must return an aware datetime", 503)
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _payload_digest(text):
    digest = sha256()
    for start in range(0, len(text), 8192):
        digest.update(text[start:start + 8192].encode("utf-8"))
    return digest.hexdigest()


def _canonical(kind, payload):
    if not isinstance(kind, str) or kind not in _FIELDS:
        raise ServiceError("unsupported_durable_command", "operation is not supported by the durable command protocol", 409)
    if not isinstance(payload, Mapping) or set(payload) != _FIELDS[kind]:
        raise ServiceError("invalid_input", "durable command requires exactly the documented payload fields")
    value = dict(payload)
    if kind == SUBMIT_ORDER:
        for field in ("quantity", "limit_price"):
            raw = value[field]
            if not isinstance(raw, (str, Decimal)):
                raise ServiceError("invalid_input", "command amounts require Decimal or decimal strings")
            try:
                value[field] = Decimal(raw)
            except Exception as exc:
                raise ServiceError("invalid_input", "command amount is invalid") from exc
        ExchangeService._validate_order_command(value["account_id"], value["order_id"], value["symbol"],
            value["quantity"], value["limit_price"], reduce_only=value["reduce_only"])
        for field in ("quantity", "limit_price"):
            value[field] = _text(value[field])
    elif kind == CANCEL_ORDER:
        ExchangeService._validate_cancel_command(value["account_id"], value["order_id"])
    elif kind == PUBLISH_MARKET:
        snapshot = value["snapshot"]
        if isinstance(snapshot, str):
            try:
                snapshot = MarketSnapshot.from_json(snapshot)
            except RiskInputError as exc:
                raise ServiceError("invalid_input", "snapshot JSON is invalid") from exc
        if not isinstance(snapshot, MarketSnapshot):
            raise ServiceError("invalid_input", "snapshot must be a MarketSnapshot or lossless market JSON")
        value["snapshot"] = snapshot.to_json()
    elif kind == REPAY:
        _name(value["account_id"], "account_id")
        _name(value["asset"], "asset")
        if not isinstance(value["amount"], (str, Decimal)):
            raise ServiceError("invalid_input", "repayment amount requires Decimal or a decimal string")
        try:
            amount = Decimal(value["amount"])
        except Exception as exc:
            raise ServiceError("invalid_input", "repayment amount is invalid") from exc
        _amount(amount, "amount", positive=True)
        value["amount"] = _text(amount)
    elif type(value["enabled"]) is not bool:
        raise ServiceError("invalid_input", "enabled must be a boolean")
    return value


class QueueStore:
    """Bounded durable metadata with per-account FIFO and a control lane.

    Capacity bounds PENDING commands, not retained history or database bytes.
    Terminal records are retained for stable idempotency; retention is offline.
    """

    def __init__(self, database: Database, *, queue_capacity=1024, cancel_reserve=16,
                 market_capacity=4, clock=None, initialize=False):
        if not isinstance(database, Database):
            raise ValueError("database must be a Database")
        for name, value, minimum, maximum in (
            ("queue_capacity", queue_capacity, 1, 65536),
            ("cancel_reserve", cancel_reserve, 0, 4096),
            ("market_capacity", market_capacity, 1, 64),
        ):
            if type(value) is not int or not minimum <= value <= maximum:
                raise ValueError(f"{name} requires an integer from {minimum} through {maximum}")
        if clock is not None and not callable(clock):
            raise ValueError("clock must be callable")
        if type(initialize) is not bool:
            raise ValueError("initialize must be a bool")
        self.database = database
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.queue_capacity, self.cancel_reserve, self.market_capacity = queue_capacity, cancel_reserve, market_capacity
        with database.read_transaction() as connection:
            present = self._existing(connection)
            if present:
                self._validate_existing(connection)
                return
            if not initialize:
                raise StorageError("durable inbox is not initialized; explicit offline bootstrap is required")
        with database.inbox_transaction() as connection:
            # Concurrent initializers serialize before this second check.
            if self._existing(connection):
                self._validate_existing(connection)
                return
            connection.execute("""CREATE TABLE IF NOT EXISTS uta_command_config (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1), format INTEGER NOT NULL,
                queue_capacity INTEGER NOT NULL, cancel_reserve INTEGER NOT NULL, market_capacity INTEGER NOT NULL)""")
            connection.execute("""CREATE TABLE IF NOT EXISTS uta_command_inbox (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT, command_id TEXT NOT NULL UNIQUE,
                account_id TEXT, kind TEXT NOT NULL, payload TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('PENDING','SUCCEEDED','REJECTED','QUARANTINED')),
                result TEXT, error TEXT, enqueued_at TEXT NOT NULL, completed_at TEXT,
                attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT, next_attempt_at TEXT)""")
            connection.execute("CREATE INDEX IF NOT EXISTS uta_command_pending ON uta_command_inbox(state,sequence)")
            connection.execute("CREATE INDEX IF NOT EXISTS uta_command_account_pending ON uta_command_inbox(account_id,state,sequence)")
            triggers = (
                ("uta_command_config_no_replace", "BEFORE INSERT ON uta_command_config WHEN EXISTS (SELECT 1 FROM uta_command_config WHERE singleton=NEW.singleton)", "inbox config cannot be replaced"),
                ("uta_command_config_no_update", "BEFORE UPDATE ON uta_command_config", "inbox config is immutable"),
                ("uta_command_config_no_delete", "BEFORE DELETE ON uta_command_config", "inbox config is immutable"),
                ("uta_command_inbox_pending_insert", "BEFORE INSERT ON uta_command_inbox WHEN NEW.state!='PENDING' OR NEW.result IS NOT NULL OR NEW.error IS NOT NULL OR NEW.completed_at IS NOT NULL", "new commands must be pending without a terminal receipt"),
                ("uta_command_inbox_no_replace", "BEFORE INSERT ON uta_command_inbox WHEN EXISTS (SELECT 1 FROM uta_command_inbox WHERE command_id=NEW.command_id OR sequence=NEW.sequence)", "command identity cannot be replaced"),
                ("uta_command_inbox_identity_immutable", "BEFORE UPDATE ON uta_command_inbox WHEN NEW.sequence!=OLD.sequence OR NEW.command_id!=OLD.command_id OR NEW.account_id IS NOT OLD.account_id OR NEW.kind!=OLD.kind OR NEW.payload!=OLD.payload OR NEW.enqueued_at!=OLD.enqueued_at", "command identity is immutable"),
                ("uta_command_inbox_terminal_immutable", "BEFORE UPDATE ON uta_command_inbox WHEN OLD.state!='PENDING'", "terminal command receipt is immutable"),
                ("uta_command_inbox_no_delete", "BEFORE DELETE ON uta_command_inbox", "command history is retained"),
            )
            for name, clause, message in triggers:
                connection.execute(f"CREATE TRIGGER IF NOT EXISTS {name} {clause} BEGIN SELECT RAISE(ABORT,'{message}'); END")
            policy = (1, queue_capacity, cancel_reserve, market_capacity)
            existing = connection.execute("SELECT format,queue_capacity,cancel_reserve,market_capacity FROM uta_command_config WHERE singleton=1").fetchone()
            if existing is not None and tuple(existing) != policy:
                raise ServiceError("configuration_conflict", "persisted inbox capacity differs from configured policy", 409)
            if existing is None:
                connection.execute("INSERT INTO uta_command_config VALUES (1,?,?,?,?)", policy)

    @staticmethod
    def _existing(connection):
        authority = connection.execute("SELECT kind FROM uta_authority WHERE singleton=1").fetchone()
        if authority is None or authority[0] != "exchange":
            raise StorageError("durable inbox requires an existing exchange authority")
        present = {row["name"] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE name IN ('uta_command_config','uta_command_inbox')")}
        if present and present != set(_TABLE_COLUMNS):
            raise StorageError("durable inbox is incomplete; automatic history reconstruction is forbidden")
        if not present and connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name LIKE 'writer_fence_%' LIMIT 1").fetchone():
            raise StorageError("managed inbox history is missing; automatic reconstruction is forbidden")
        return bool(present)

    def _validate_existing(self, connection):
        expected = {**{name: "table" for name in _TABLE_COLUMNS},
                    **{name: "trigger" for name in _TRIGGER_NAMES},
                    "uta_command_pending": "index", "uta_command_account_pending": "index"}
        names = tuple(expected)
        actual = {row["name"]: row["type"] for row in connection.execute(
            "SELECT name,type FROM sqlite_master WHERE name IN (" + ",".join("?" for _ in names) + ")", names)}
        if actual != expected:
            raise StorageError("durable inbox schema or integrity guards are missing; automatic repair is forbidden")
        for table, columns in _TABLE_COLUMNS.items():
            found = {item[0] for item in connection.execute(f"SELECT * FROM {table} LIMIT 0").description}
            if found != columns:
                raise StorageError("unsupported durable inbox columns")
        rows = connection.execute("SELECT singleton,format,queue_capacity,cancel_reserve,market_capacity FROM uta_command_config").fetchall()
        if len(rows) != 1 or tuple(rows[0]) != (1, 1, self.queue_capacity, self.cancel_reserve, self.market_capacity):
            raise ServiceError("configuration_conflict", "persisted inbox capacity differs or config is incomplete", 409)

    @staticmethod
    def _record(row):
        if row is None:
            return None
        return {"command_id": row["command_id"], "sequence": row["sequence"],
                "account_id": row["account_id"], "kind": row["kind"], "state": row["state"],
                "ack": "durably_queued", "result": json.loads(row["result"]) if row["result"] else None,
                "error": json.loads(row["error"]) if row["error"] else None,
                "attempts": row["attempts"], "last_error": row["last_error"],
                "enqueued_at": row["enqueued_at"], "completed_at": row["completed_at"],
                "next_attempt_at": row["next_attempt_at"]}

    def enqueue_submit(self, account_id, command_id, order_id, symbol, quantity, limit_price, *, reduce_only=False):
        return self.enqueue(SUBMIT_ORDER, command_id, dict(account_id=account_id, order_id=order_id,
            symbol=symbol, quantity=quantity, limit_price=limit_price, reduce_only=reduce_only))

    def enqueue_cancel(self, account_id, command_id, order_id):
        return self.enqueue(CANCEL_ORDER, command_id, dict(account_id=account_id, order_id=order_id))

    def enqueue_market(self, command_id, snapshot):
        return self.enqueue(PUBLISH_MARKET, command_id, dict(snapshot=snapshot))

    def enqueue_halt(self, command_id, enabled):
        return self.enqueue(SET_HALT, command_id, dict(enabled=enabled))

    def enqueue_repay(self, account_id, command_id, asset, amount):
        return self.enqueue(REPAY, command_id, dict(account_id=account_id, asset=asset, amount=amount))

    def enqueue(self, kind, command_id, payload):
        _name(command_id, "command_id")
        canonical = _canonical(kind, payload)
        encoded, account_id = _json(canonical), canonical.get("account_id")
        with self.database.inbox_transaction() as connection:
            row = connection.execute("SELECT * FROM uta_command_inbox WHERE command_id=?", (command_id,)).fetchone()
            if row is not None:
                if (row["kind"], row["account_id"], row["payload"]) != (kind, account_id, encoded):
                    raise ServiceError("idempotency_conflict", "command ID was reused with different canonical content", 409)
                result = self._record(row)
            else:
                if kind == REPAY:
                    asset = canonical["asset"]
                    scale = connection.execute("SELECT scale FROM ledger_assets WHERE asset=?", (asset,)).fetchone()
                    if scale is None:
                        raise ServiceError("unknown_asset", "repayment asset is not configured")
                    try:
                        codec = Ledger({asset: scale[0]})
                    except LedgerError as exc:
                        raise StorageError("invalid persisted repayment asset scale") from exc
                    try:
                        codec._units(asset, Decimal(canonical["amount"]))
                    except LedgerError as exc:
                        raise ServiceError("invalid_input", str(exc)) from exc
                control = kind in _CONTROL
                count = connection.execute("SELECT COUNT(*) FROM uta_command_inbox WHERE state='PENDING' AND "
                    + ("kind IN ('PUBLISH_MARKET','SET_HALT')" if control else "kind NOT IN ('PUBLISH_MARKET','SET_HALT')")).fetchone()[0]
                limit = (self.market_capacity if control else self.queue_capacity
                         + (self.cancel_reserve if kind in (CANCEL_ORDER, REPAY) else 0))
                if count >= limit:
                    raise ServiceError("durable_queue_overloaded", "durable pending command capacity is exhausted", 503)
                connection.execute("INSERT INTO uta_command_inbox(command_id,account_id,kind,payload,state,enqueued_at) VALUES (?,?,?,?,'PENDING',?)",
                                   (command_id, account_id, kind, encoded, _stamp(self.clock())))
                result = self._record(connection.execute("SELECT * FROM uta_command_inbox WHERE command_id=?", (command_id,)).fetchone())
        # Do not publish an ACK before the metadata transaction COMMIT returns.
        return result

    def status(self, command_id, *, account_id=None):
        _name(command_id, "command_id")
        if account_id is not None:
            _name(account_id, "account_id")
        with self.database.read_transaction() as connection:
            row = connection.execute("SELECT * FROM uta_command_inbox WHERE command_id=?", (command_id,)).fetchone()
            if row is not None and account_id is not None and row["account_id"] != account_id:
                return None
            return self._record(row)

    def _check_exchange(self, exchange):
        if not isinstance(exchange, ExchangeService) or exchange.database.path != self.database.path:
            raise ValueError("worker exchange and inbox must share the same financial database")

    @staticmethod
    def _assert_writer(exchange, connection):
        from .writer_fence import WriterFence
        WriterFence(exchange.database).assert_writer(connection)

    @staticmethod
    def _business(kind, error):
        if _business_rejection(error, extra_unavailable_codes=frozenset({"router_halted"})):
            return True
        if kind in _CONTROL and error.code == "control_superseded" and error.status == 409:
            mapped = ServiceError("invalid_input", str(error), 400)
            mapped.__cause__ = error
            return _business_rejection(mapped)
        if kind == REPAY and error.code in {"repayment_exceeds_debt", "insufficient_cash", "unknown_asset", "credit_limit"} and 400 <= error.status < 500:
            mapped = ServiceError("invalid_input", str(error), 400)
            mapped.__cause__ = error
            return _business_rejection(mapped)
        if kind == PUBLISH_MARKET and error.code in {"invalid_market", "market_regression", "market_conflict", "market_incomplete"} and 400 <= error.status < 500:
            mapped = ServiceError("invalid_input", str(error), 400)
            mapped.__cause__ = error
            return _business_rejection(mapped)
        return False

    def process_one(self, exchange, *, guard=None, credit=None):
        """Execute one eligible account head; return only after outer COMMIT.

        Router users must supply its guard and hold its outer publication lock
        through this call. A technical exception leaves the command PENDING.
        """
        self._check_exchange(exchange)
        command_id = sequence = attempt = None
        try:
            with exchange._transaction() as connection:
                self._assert_writer(exchange, connection)
                now = _stamp(self.clock())
                row = connection.execute("""SELECT c.* FROM uta_command_inbox c
                    WHERE c.state='PENDING' AND (c.next_attempt_at IS NULL OR c.next_attempt_at<=?)
                    AND NOT EXISTS (SELECT 1 FROM uta_command_inbox p WHERE p.state='PENDING'
                        AND p.sequence<c.sequence AND (p.account_id=c.account_id OR
                            (p.account_id IS NULL AND c.account_id IS NULL)))
                    ORDER BY CASE WHEN c.kind IN ('PUBLISH_MARKET','SET_HALT') THEN 0 ELSE 1 END,c.sequence LIMIT 1""", (now,)).fetchone()
                if row is None:
                    return None
                command_id, sequence = row["command_id"], row["sequence"]
                attempt = row["attempts"] + 1
                try:
                    payload = _canonical(row["kind"], json.loads(row["payload"]))
                except Exception as exc:
                    raise StorageError("persisted command payload is invalid") from exc
                if _json(payload) != row["payload"] or payload.get("account_id") != row["account_id"]:
                    raise StorageError("persisted command content is not canonical or has inconsistent ownership")
                command = {**self._record(row), "payload": payload}
                connection.execute("SAVEPOINT durable_command")
                result, error, new_order = None, None, False
                try:
                    with (guard(connection, command) if guard else nullcontext()):
                        changes = connection.total_changes
                        if row["kind"] == SUBMIT_ORDER:
                            result = exchange._admit_order(connection, payload["account_id"], payload["order_id"], payload["symbol"],
                                Decimal(payload["quantity"]), Decimal(payload["limit_price"]), reduce_only=payload["reduce_only"])
                            new_order = connection.total_changes > changes
                        elif row["kind"] == CANCEL_ORDER:
                            result = exchange._cancel_order(connection, payload["account_id"], payload["order_id"])
                        elif row["kind"] == PUBLISH_MARKET:
                            result = exchange._publish_market(connection, MarketSnapshot.from_json(payload["snapshot"]))
                        elif row["kind"] == REPAY:
                            if not isinstance(credit, CreditService) or credit.exchange is not exchange:
                                raise StorageError("repayment requires the worker's initialized credit service")
                            result = credit._repay(connection, payload["account_id"], command_id,
                                                   payload["asset"], Decimal(payload["amount"]))
                        else:
                            result = exchange._set_kill_switch(connection, payload["enabled"])
                except ServiceError as exc:
                    if not connection.in_transaction or not self._business(row["kind"], exc):
                        raise
                    connection.execute("ROLLBACK TO durable_command")
                    error = {"code": exc.code, "message": str(exc), "status": exc.status}
                    result = None
                    new_order = False
                connection.execute("RELEASE durable_command")
                connection.execute("UPDATE uta_command_inbox SET state=?,result=?,error=?,completed_at=?,next_attempt_at=NULL WHERE command_id=? AND state='PENDING'",
                    ("REJECTED" if error else "SUCCEEDED", _json(result) if result is not None else None,
                     _json(error) if error else None, _stamp(self.clock()), command_id))
                if new_order:
                    exchange._market(connection)
                receipt = self._record(connection.execute("SELECT * FROM uta_command_inbox WHERE command_id=?", (command_id,)).fetchone())
            return receipt
        except Exception as exc:
            raise CommandExecutionError(command_id, sequence, exc, attempt=attempt) from exc

    def record_failure(self, exchange, command_id, *, max_attempts=3, backoff_seconds=0,
                       cause=None, attempt=None):
        """Query durable outcome before recording a bounded technical retry.

        This explicit worker policy never rewrites a committed terminal receipt.
        Quarantine is a technical terminal outcome with no accepted order result.
        Optional attempt identifies the observed execution for idempotent recovery
        after a lost failure-recording COMMIT reply. Legacy callers may omit it.
        The internal global event and retry metadata share this financial COMMIT;
        an exception here does not claim either was saved. Query the original ID.
        """
        self._check_exchange(exchange)
        _name(command_id, "command_id")
        if type(max_attempts) is not int or not 1 <= max_attempts <= 100:
            raise ValueError("max_attempts must be an integer from 1 through 100")
        if isinstance(backoff_seconds, bool) or not isinstance(backoff_seconds, (int, float)) or not math.isfinite(backoff_seconds) or not 0 <= backoff_seconds <= 3600:
            raise ValueError("backoff_seconds must be finite from 0 through 3600")
        if attempt is not None and (type(attempt) is not int or not 1 <= attempt <= 100):
            raise ValueError("attempt must be an integer from 1 through 100 or None")
        with exchange._transaction() as connection:
            self._assert_writer(exchange, connection)
            row = connection.execute("SELECT * FROM uta_command_inbox WHERE command_id=?", (command_id,)).fetchone()
            if row is None:
                raise ServiceError("command_not_found", "unknown command", 404)
            if row["state"] in _TERMINAL:
                return self._record(row)
            if attempt is not None:
                if attempt <= row["attempts"]:
                    return self._record(row)
                if attempt != row["attempts"] + 1:
                    raise ValueError("attempt must identify the next observed execution")
            attempts = row["attempts"] + 1
            quarantined = attempts >= max_attempts
            error = {"code": "command_quarantined", "message": "technical execution failure requires investigation; no risk acceptance receipt", "status": 503}
            connection.execute("UPDATE uta_command_inbox SET state=?,attempts=?,last_error=?,error=?,completed_at=?,next_attempt_at=? WHERE command_id=? AND state='PENDING'",
                ("QUARANTINED" if quarantined else "PENDING", attempts, "technical_execution_failure",
                 _json(error) if quarantined else None, _stamp(self.clock()) if quarantined else None,
                 None if quarantined else _stamp(self.clock() + timedelta(seconds=backoff_seconds)), command_id))
            exchange._event(connection, "COMMAND_EXECUTION_FAILED", None, {
                "event_version": 1, "command_id": command_id, "command_sequence": row["sequence"],
                "command_kind": row["kind"] if len(row["kind"]) <= 32 and row["kind"] in _FIELDS else None,
                "command_kind_sha256": _payload_digest(row["kind"]), "attempt": attempts,
                "canonical_payload_sha256": _payload_digest(row["payload"]),
                "failure_class": "technical_execution_failure",
                "receipt_state": "QUARANTINED" if quarantined else "PENDING",
                "diagnostic": capture_failure(cause),
            })
            receipt = self._record(connection.execute("SELECT * FROM uta_command_inbox WHERE command_id=?", (command_id,)).fetchone())
        return receipt
