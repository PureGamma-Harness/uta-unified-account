"""Durable, serialized liquidation planning; this module never routes orders.

Every evaluation reloads the complete controller state under the database write
lock. Pending actions and acknowledgement deduplication survive restarts. An
action ID must still be reconciled with the execution venue before acknowledging
success: database durability cannot make an external order exactly-once.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Context, Decimal, InvalidOperation, localcontext
from hashlib import sha256
import json
import sqlite3
from typing import Any

from .liquidation import (Action, ActionType, LiquidationController, Phase,
                          PositionReduction, TimedRisk)
from .models import RiskInputError, _decimal
from .storage import Database


class LiquidationStateError(ValueError):
    """Persisted liquidation state or its configured policy is inconsistent."""


_VERSION = 1
_FIELDS = {"phase", "active_phase", "cycle", "sequence", "pending", "completed",
           "last_ack_at", "last_observed_at", "can_trade", "last_evaluated_at"}
_ACTION_FIELDS = {"action_id", "kind", "symbol", "side", "quantity", "reduce_only"}


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise LiquidationStateError("duplicate field in liquidation state")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise LiquidationStateError("nonfinite JSON value in liquidation state")


def _time(value: datetime | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise LiquidationStateError("liquidation timestamps must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _parse_time(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise LiquidationStateError("corrupt liquidation timestamp")
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise LiquidationStateError("corrupt liquidation timestamp") from exc
    if _time(result) != value:
        raise LiquidationStateError("liquidation timestamps must use canonical UTC format")
    return result


def _decimal_text(value: Decimal) -> str:
    # Strip coefficient zeros without Decimal.normalize(), which would apply
    # the ambient context. Preserve scientific notation for bounded inputs such
    # as 1E+100 rather than expanding them into 101 significant digits.
    parts = value.as_tuple()
    digits, exponent = list(parts.digits), parts.exponent
    while len(digits) > 1 and digits[-1] == 0:
        digits.pop()
        exponent += 1
    return str(Decimal((parts.sign, tuple(digits), exponent)))


def _parse_decimal(value: Any, name: str) -> Decimal:
    if not isinstance(value, str) or len(value) > 256:
        raise LiquidationStateError(f"corrupt {name}")
    try:
        result = Decimal(value)
        _decimal(name, result, positive=True)
    except (InvalidOperation, RiskInputError) as exc:
        raise LiquidationStateError(f"corrupt {name}") from exc
    if _decimal_text(result) != value:
        raise LiquidationStateError(f"noncanonical {name}")
    return result


def _action_json(action: Action | None) -> dict[str, Any] | None:
    if action is None:
        return None
    return {"action_id": action.action_id, "kind": action.kind.value,
            "symbol": action.symbol, "side": action.side,
            "quantity": _decimal_text(action.quantity) if action.quantity is not None else None,
            "reduce_only": action.reduce_only}


class DurableLiquidationController:
    """Persist the reference liquidation state machine for a single account.

    Configuration is fixed on first creation; another instance must provide the
    same policy. ``status()['trading_allowed']`` describes the last evaluation,
    not permission to trade now. Before each order, independently obtain fresh,
    complete account/market data and run the trading service's atomic risk gate.
    This wrapper does not fetch market data, settle trades, or acknowledge actions
    automatically. Database file ownership remains a trusted boundary.
    """

    def __init__(self, database: Database, account_id: str, *,
                 max_age: timedelta = timedelta(seconds=10),
                 recovery_buffer: Decimal = Decimal("1.10")):
        if not isinstance(database, Database):
            raise ValueError("database must be a Database")
        controller = LiquidationController(account_id, max_age=max_age, recovery_buffer=recovery_buffer)
        self.database = database
        self.account_id = account_id
        self.max_age = max_age
        self.recovery_buffer = recovery_buffer
        self._age_text = str((max_age.days * 86400 + max_age.seconds) * 1000000 + max_age.microseconds)
        self._buffer_text = _decimal_text(recovery_buffer)
        with database.transaction() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS durable_liquidation_schema (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1), version INTEGER NOT NULL)""")
            row = connection.execute("SELECT version FROM durable_liquidation_schema WHERE singleton = 1").fetchone()
            if row is None:
                connection.execute("INSERT INTO durable_liquidation_schema VALUES (1, ?)", (_VERSION,))
            elif row[0] != _VERSION:
                raise LiquidationStateError("unsupported durable liquidation schema version")
            connection.execute("""CREATE TABLE IF NOT EXISTS durable_liquidation_controllers (
                account_id TEXT PRIMARY KEY, max_age_us TEXT NOT NULL, recovery_buffer TEXT NOT NULL,
                revision INTEGER NOT NULL CHECK (revision >= 0), state TEXT NOT NULL, digest TEXT NOT NULL)""")
            connection.execute("""CREATE TRIGGER IF NOT EXISTS durable_liquidation_no_delete
                BEFORE DELETE ON durable_liquidation_controllers
                BEGIN SELECT RAISE(ABORT, 'liquidation history cannot be deleted'); END""")
            connection.execute("""CREATE TRIGGER IF NOT EXISTS durable_liquidation_fixed_policy
                BEFORE UPDATE OF account_id, max_age_us, recovery_buffer ON durable_liquidation_controllers
                BEGIN SELECT RAISE(ABORT, 'liquidation policy is immutable'); END""")
            exists = connection.execute("SELECT 1 FROM durable_liquidation_controllers WHERE account_id = ?",
                                        (account_id,)).fetchone()
            if exists is None:
                state = _json(self._encode(controller, None))
                connection.execute("INSERT INTO durable_liquidation_controllers VALUES (?, ?, ?, 0, ?, ?)",
                                   (account_id, self._age_text, self._buffer_text, state, self._digest(0, state)))
            else:
                self._load(connection)

    def _digest(self, revision: int, state: str) -> str:
        value = [self.account_id, self._age_text, self._buffer_text, revision, state]
        return sha256(_json(value).encode()).hexdigest()

    @staticmethod
    def _encode(controller: LiquidationController, evaluated_at: datetime | None) -> dict[str, Any]:
        return {"phase": controller.phase.value, "active_phase": controller._active_phase.value,
                "cycle": controller._cycle, "sequence": controller._sequence,
                "pending": _action_json(controller._pending), "completed": sorted(controller._completed),
                "last_ack_at": _time(controller._last_ack_at),
                "last_observed_at": _time(controller._last_observed_at),
                "can_trade": controller._can_trade, "last_evaluated_at": _time(evaluated_at)}

    def _action_identity(self, action_id: Any) -> tuple[int, int]:
        if not isinstance(action_id, str):
            raise LiquidationStateError("corrupt liquidation action ID")
        parts = action_id.rsplit(":", 2)
        if (len(parts) != 3 or parts[0] != self.account_id
                or not parts[1].isascii() or not parts[1].isdigit()
                or not parts[2].isascii() or not parts[2].isdigit()
                or len(parts[1]) > 20 or len(parts[2]) > 20):
            raise LiquidationStateError("corrupt liquidation action ID")
        cycle, sequence = int(parts[1]), int(parts[2])
        if cycle <= 0 or sequence <= 0 or parts[1] != str(cycle) or parts[2] != str(sequence):
            raise LiquidationStateError("corrupt liquidation action ID")
        return cycle, sequence

    def _decode(self, state: dict[str, Any]) -> tuple[LiquidationController, datetime | None]:
        if not isinstance(state, dict) or set(state) != _FIELDS:
            raise LiquidationStateError("invalid fields in liquidation state")
        controller = LiquidationController(self.account_id, max_age=self.max_age,
                                           recovery_buffer=self.recovery_buffer)
        try:
            controller.phase = Phase(state["phase"])
            controller._active_phase = Phase(state["active_phase"])
        except (TypeError, ValueError) as exc:
            raise LiquidationStateError("invalid persisted liquidation phase") from exc
        if controller._active_phase == Phase.BLOCKED:
            raise LiquidationStateError("blocked cannot be an active liquidation phase")
        for field in ("cycle", "sequence"):
            value = state[field]
            if type(value) is not int or not 0 <= value < 2 ** 63:
                raise LiquidationStateError("invalid liquidation counter")
            setattr(controller, "_" + field, value)
        if (type(state["can_trade"]) is not bool or not isinstance(state["completed"], list)
                or controller._cycle > controller._sequence):
            raise LiquidationStateError("invalid liquidation flags or action counters")
        controller._can_trade = state["can_trade"]
        controller._last_ack_at = _parse_time(state["last_ack_at"])
        controller._last_observed_at = _parse_time(state["last_observed_at"])
        evaluated_at = _parse_time(state["last_evaluated_at"])
        identities = [self._action_identity(value) for value in state["completed"]]
        if (any(cycle > controller._cycle or sequence > controller._sequence for cycle, sequence in identities)
                or len({sequence for _, sequence in identities}) != len(identities)):
            raise LiquidationStateError("invalid completed liquidation actions")
        controller._completed = set(state["completed"])
        if len(controller._completed) != len(state["completed"]):
            raise LiquidationStateError("duplicate completed liquidation action")
        if state["completed"] != sorted(controller._completed):
            raise LiquidationStateError("completed liquidation actions are not canonical")
        pending = state["pending"]
        if pending is not None:
            if not isinstance(pending, dict) or set(pending) != _ACTION_FIELDS:
                raise LiquidationStateError("invalid pending liquidation action fields")
            cycle, sequence = self._action_identity(pending["action_id"])
            if (cycle != controller._cycle or sequence != controller._sequence
                    or pending["action_id"] in controller._completed):
                raise LiquidationStateError("pending action does not match liquidation counters")
            try:
                kind = ActionType(pending["kind"])
            except (TypeError, ValueError) as exc:
                raise LiquidationStateError("invalid pending liquidation action kind") from exc
            if type(pending["reduce_only"]) is not bool:
                raise LiquidationStateError("reduce_only must be a boolean")
            quantity = None
            if kind == ActionType.CANCEL_ALL_ORDERS:
                if (any(pending[field] is not None for field in ("symbol", "side", "quantity"))
                        or pending["reduce_only"] or controller._active_phase != Phase.CANCEL_ORDERS):
                    raise LiquidationStateError("invalid pending cancel action")
            else:
                if (not isinstance(pending["symbol"], str) or not pending["symbol"].strip()
                        or len(pending["symbol"]) > 128 or pending["side"] not in ("buy", "sell")
                        or pending["reduce_only"] is not True or controller._active_phase != Phase.REDUCE_EXPOSURE):
                    raise LiquidationStateError("invalid pending reduction action")
                quantity = _parse_decimal(pending["quantity"], "reduction quantity")
            controller._pending = Action(pending["action_id"], kind, pending["symbol"],
                                         pending["side"], quantity, pending["reduce_only"])
        if (len(controller._completed) + int(controller._pending is not None) != controller._sequence
                or bool(controller._completed) != (controller._last_ack_at is not None)
                or (controller._sequence > 0 and controller._last_observed_at is None)):
            raise LiquidationStateError("liquidation action history is incomplete")
        if (controller._active_phase in (Phase.CANCEL_ORDERS, Phase.REDUCE_EXPOSURE, Phase.RECOVERED)
                and controller._cycle == 0):
            raise LiquidationStateError("liquidation phase lacks a liquidation cycle")
        if controller._active_phase == Phase.CANCEL_ORDERS and controller._pending is None:
            raise LiquidationStateError("cancel phase lacks its pending action")
        if (controller._pending is not None and controller._last_ack_at is not None
                and controller._last_observed_at <= controller._last_ack_at):
            raise LiquidationStateError("pending action predates the last acknowledgement")
        if controller.phase != Phase.BLOCKED and controller.phase != controller._active_phase:
            raise LiquidationStateError("liquidation phase differs from active phase")
        if controller._can_trade != (controller.phase in (Phase.NORMAL, Phase.RECOVERED)):
            raise LiquidationStateError("liquidation trading flag contradicts phase")
        if controller._can_trade:
            observed = controller._last_observed_at
            if (controller._pending is not None or observed is None or evaluated_at is None
                    or observed > evaluated_at or evaluated_at - observed > self.max_age
                    or (controller._last_ack_at is not None and observed <= controller._last_ack_at)):
                raise LiquidationStateError("trading flag lacks a valid last risk evaluation")
        return controller, evaluated_at

    def _load(self, connection: sqlite3.Connection) -> tuple[LiquidationController, int, datetime | None]:
        version = connection.execute("SELECT version FROM durable_liquidation_schema WHERE singleton = 1").fetchone()
        if version is None or version[0] != _VERSION:
            raise LiquidationStateError("unsupported durable liquidation schema version")
        row = connection.execute("SELECT max_age_us, recovery_buffer, revision, state, digest "
                                 "FROM durable_liquidation_controllers WHERE account_id = ?",
                                 (self.account_id,)).fetchone()
        if row is None:
            raise LiquidationStateError("persisted liquidation controller is missing")
        age, buffer, revision, encoded, digest = tuple(row)
        if age != self._age_text or buffer != self._buffer_text:
            raise LiquidationStateError("liquidation policy differs from persisted configuration")
        if (type(revision) is not int or not 0 <= revision < 2 ** 63
                or not isinstance(encoded, str) or not isinstance(digest, str)
                or digest != self._digest(revision, encoded)):
            raise LiquidationStateError("liquidation state checksum failed")
        try:
            state = json.loads(encoded, object_pairs_hook=_unique_object,
                               parse_constant=_reject_constant)
        except (json.JSONDecodeError, RecursionError) as exc:
            raise LiquidationStateError("invalid JSON in liquidation state") from exc
        controller, evaluated_at = self._decode(state)
        if _json(state) != encoded:
            raise LiquidationStateError("liquidation state is not canonical JSON")
        return controller, revision, evaluated_at

    def _save(self, connection: sqlite3.Connection, controller: LiquidationController,
              revision: int, evaluated_at: datetime | None) -> None:
        state = self._encode(controller, evaluated_at)
        # Validate states produced by the underlying controller as well as reads;
        # a future incompatible state-machine change cannot silently persist.
        self._decode(state)
        encoded = _json(state)
        previous = connection.execute("SELECT state FROM durable_liquidation_controllers WHERE account_id = ?",
                                      (self.account_id,)).fetchone()
        if previous is None:
            raise LiquidationStateError("persisted liquidation controller is missing")
        if previous[0] == encoded:
            return
        revision += 1
        connection.execute("UPDATE durable_liquidation_controllers SET revision = ?, state = ?, digest = ? "
                           "WHERE account_id = ?", (revision, encoded, self._digest(revision, encoded), self.account_id))

    def next_action(self, snapshot: TimedRisk | None, *, now: datetime,
                    reduction: PositionReduction | None = None) -> Action | None:
        """Atomically evaluate current risk and retain any proposed action ID."""
        with self.database.transaction() as connection, localcontext(Context(prec=256)):
            controller, revision, _ = self._load(connection)
            action = controller.next_action(snapshot, now=now, reduction=reduction)
            evaluated_at = now if (isinstance(now, datetime) and now.tzinfo is not None
                                   and now.utcoffset() is not None) else None
            self._save(connection, controller, revision, evaluated_at)
            return action

    def acknowledge(self, action_id: str, *, success: bool, now: datetime) -> bool:
        """Record only caller-confirmed outcomes; repeated successful IDs are inert."""
        if type(success) is not bool:
            raise ValueError("success must be a boolean")
        _time(now)
        if now is None:
            raise ValueError("acknowledgement time is required")
        with self.database.transaction() as connection, localcontext(Context(prec=256)):
            controller, revision, evaluated_at = self._load(connection)
            result = controller.acknowledge(action_id, success=success, now=now)
            self._save(connection, controller, revision, evaluated_at)
            return result

    def status(self) -> dict[str, Any]:
        """Return JSON-safe historical state; this is not a current trading gate."""
        with self.database.transaction() as connection:
            controller, revision, evaluated_at = self._load(connection)
            return {"account_id": self.account_id, "revision": revision,
                    "phase": controller.phase.value, "trading_allowed": controller.trading_allowed,
                    "pending_action": _action_json(controller.pending_action),
                    "last_evaluated_at": _time(evaluated_at),
                    "last_observed_at": _time(controller._last_observed_at),
                    "last_ack_at": _time(controller._last_ack_at),
                    "completed_action_count": len(controller._completed)}
