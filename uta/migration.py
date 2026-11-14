"""Fail-closed, in-memory classic-account shadow migration.

This is a reconciliation prototype, not a live exchange adapter or cutover.
No orders, balances or liabilities are transferred. Durable transactions and
an exchange-consistent snapshot are required before any real migration.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from threading import RLock
from typing import Any, Mapping

from .models import RiskInputError, _decimal as _validate_risk_decimal


class MigrationError(ValueError):
    """Snapshot or migration violates a safety precondition."""


def _fields(value: Any, expected: set[str], name: str) -> None:
    if not isinstance(value, Mapping) or set(value) != expected:
        raise MigrationError(f"{name} must contain exactly: {', '.join(sorted(expected))}")


def _name(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise MigrationError(f"{name} must be a nonempty trimmed string")
    return value


def _decimal(value: Any, name: str, *, positive: bool = False, signed: bool = False) -> Decimal:
    # Floats and implicit integer coercions can hide loss of exchange precision.
    if not isinstance(value, str) or len(value) > 128:
        raise MigrationError(f"{name} must be a decimal string of at most 128 characters")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise MigrationError(f"{name} is not a decimal") from exc
    try:
        _validate_risk_decimal(name, result, minimum=None if signed else Decimal(0),
                               positive=positive)
    except RiskInputError as exc:
        raise MigrationError(str(exc)) from exc
    return result


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise MigrationError("captured_at must be an ISO-8601 string with timezone")
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MigrationError("invalid captured_at") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise MigrationError("captured_at must have a timezone")
    return timestamp.astimezone(timezone.utc)


@dataclass(frozen=True, order=True)
class Balance:
    compartment: str
    asset: str
    free: Decimal
    locked: Decimal
    borrowed: Decimal
    interest: Decimal


@dataclass(frozen=True, order=True)
class Position:
    symbol: str
    quantity: Decimal  # signed; zero positions are not included
    entry_price: Decimal


@dataclass(frozen=True)
class ShadowAccount:
    """Immutable, lossless projection of one consistent source snapshot."""
    account_id: str
    source_version: int
    captured_at: datetime
    balances: tuple[Balance, ...]
    positions: tuple[Position, ...]
    source_digest: str


def build_shadow(snapshot: Mapping[str, Any], *, now: datetime | None = None,
                 max_age: timedelta = timedelta(seconds=30),
                 max_future_skew: timedelta = timedelta(seconds=2)) -> ShadowAccount:
    """Validate and reconcile all required compartments into a read-only mirror.

    Input must represent one atomic exchange snapshot and include spot, margin,
    and futures, even when a compartment is empty. Completeness is an assertion
    by the adapter; this module cannot establish atomicity across exchange APIs.
    """
    _fields(snapshot, {"account_id", "version", "captured_at", "compartments"}, "snapshot")
    account_id = _name(snapshot["account_id"], "account_id")
    version = snapshot["version"]
    if isinstance(version, bool) or not isinstance(version, int) or version < 0:
        raise MigrationError("version must be a nonnegative integer")
    captured_at = _timestamp(snapshot["captured_at"])
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise MigrationError("now must be timezone-aware")
    if max_age < timedelta(0) or max_future_skew < timedelta(0):
        raise MigrationError("time limits must be nonnegative")
    age = now.astimezone(timezone.utc) - captured_at
    if age > max_age or age < -max_future_skew:
        raise MigrationError("snapshot is stale or from the future")
    compartments = snapshot["compartments"]
    _fields(compartments, {"spot", "margin", "futures"}, "compartments")
    balances: list[Balance] = []
    positions: list[Position] = []
    for compartment in ("spot", "margin", "futures"):
        section = compartments[compartment]
        keys = {"balances", "positions"} if compartment == "futures" else {"balances"}
        _fields(section, keys, compartment)
        if not isinstance(section["balances"], list):
            raise MigrationError(f"{compartment}.balances must be a list")
        seen_assets: set[str] = set()
        for raw in section["balances"]:
            _fields(raw, {"asset", "free", "locked", "borrowed", "interest"}, "balance")
            asset = _name(raw["asset"], "asset")
            if asset in seen_assets:
                raise MigrationError(f"duplicate balance {compartment}/{asset}")
            seen_assets.add(asset)
            balances.append(Balance(compartment, asset, *(
                _decimal(raw[key], key) for key in ("free", "locked", "borrowed", "interest")
            )))
        if compartment == "futures":
            if not isinstance(section["positions"], list):
                raise MigrationError("futures.positions must be a list")
            seen_symbols: set[str] = set()
            for raw in section["positions"]:
                _fields(raw, {"symbol", "quantity", "entry_price"}, "position")
                symbol = _name(raw["symbol"], "symbol")
                if symbol in seen_symbols:
                    raise MigrationError(f"duplicate position {symbol}")
                seen_symbols.add(symbol)
                quantity = _decimal(raw["quantity"], "quantity", signed=True)
                if quantity == 0:
                    raise MigrationError("flat positions must be omitted")
                positions.append(Position(symbol, quantity, _decimal(raw["entry_price"], "entry_price", positive=True)))
    balances_tuple, positions_tuple = tuple(sorted(balances)), tuple(sorted(positions))
    # Canonicalize numeric values as Decimal, not supplied spelling, so equivalent
    # snapshots with 1.0 versus 1.00 can be retried safely.
    def canonical(d: Decimal) -> str:
        if not d:
            return "0"
        text = format(d, "f")
        return text.rstrip("0").rstrip(".") if "." in text else text
    payload = {
        "account_id": account_id, "version": version,
        "captured_at": captured_at.isoformat(),
        "balances": [[b.compartment, b.asset, canonical(b.free), canonical(b.locked),
                      canonical(b.borrowed), canonical(b.interest)] for b in balances_tuple],
        "positions": [[p.symbol, canonical(p.quantity), canonical(p.entry_price)] for p in positions_tuple],
    }
    digest = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return ShadowAccount(account_id, version, captured_at, balances_tuple, positions_tuple, digest)


class ShadowMigrationStore:
    """Process-local atomic mirror; durable version checks require a database.

    Reconciliation preserves every field and source compartment separately.
    It does not assert matching equity, prices, collateral haircuts or margin.
    """
    def __init__(self) -> None:
        self._lock = RLock()
        self._accounts: dict[str, ShadowAccount] = {}
        self._keys: dict[tuple[str, str], ShadowAccount] = {}

    def apply(self, snapshot: Mapping[str, Any], idempotency_key: str, *,
              now: datetime | None = None, max_age: timedelta = timedelta(seconds=30)) -> ShadowAccount:
        key = _name(idempotency_key, "idempotency_key")
        # Validate before changing state, including on idempotent retries.
        candidate = build_shadow(snapshot, now=now, max_age=max_age)
        with self._lock:
            key_id = (candidate.account_id, key)
            previous_key = self._keys.get(key_id)
            if previous_key:
                if previous_key.source_digest != candidate.source_digest:
                    raise MigrationError("idempotency key was reused with different data")
                return previous_key
            previous = self._accounts.get(candidate.account_id)
            if previous and candidate.source_version < previous.source_version:
                raise MigrationError("source version regressed")
            if previous and candidate.source_version == previous.source_version:
                if candidate.source_digest != previous.source_digest:
                    raise MigrationError("source version reused with different data")
                self._keys[key_id] = previous
                return previous
            self._accounts[candidate.account_id] = candidate
            self._keys[key_id] = candidate
            return candidate

    def get(self, account_id: str) -> ShadowAccount | None:
        with self._lock:
            return self._accounts.get(account_id)
