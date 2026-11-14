"""Immutable market snapshots supplied by an authenticated pricing authority.

This module checks a snapshot's shape and clock bounds. It does not establish
that a feed is independent, correct, or manipulation resistant; feed selection
and instrument parameters remain an operator responsibility. A durable service
must also reject a regressing version or observation time across snapshots.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
import re
from types import MappingProxyType
from typing import Mapping

from .models import AssetSpec, InstrumentSpec, RiskInputError, _decimal, _identifier, _mapping


MAX_JSON_BYTES = 1024 * 1024


def _aware(value: datetime, name: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise RiskInputError(f"{name} must be a timezone-aware datetime")


def _canonical(value: Decimal) -> str:
    """Normalize equal values without Decimal.normalize's context rounding."""
    if not value:
        return "0"
    sign, digits, exponent = value.as_tuple()
    digits = list(digits)
    while digits[-1] == 0:
        digits.pop()
        exponent += 1
    return str(Decimal((sign, tuple(digits), exponent)))


def _strict_fields(value, fields: set[str], name: str) -> None:
    if not isinstance(value, dict) or set(value) != fields:
        raise RiskInputError(f"{name} must contain exactly {', '.join(sorted(fields))}")


def _number(value, name: str) -> Decimal:
    if (not isinstance(value, str) or not 1 <= len(value) <= 256
            or not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", value)):
        raise RiskInputError(f"{name} must be a decimal string of at most 256 characters")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise RiskInputError(f"invalid decimal for {name}") from exc
    _decimal(name, result)
    return result


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise RiskInputError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant(value):
    raise RiskInputError(f"nonstandard JSON constant: {value}")


def _json_size(value: str) -> None:
    if not isinstance(value, str):
        raise RiskInputError("market JSON must be a string of at most 1 MiB")
    try:
        size = len(value.encode("utf-8"))
    except UnicodeError as exc:
        raise RiskInputError("market JSON must be valid UTF-8") from exc
    if size > MAX_JSON_BYTES:
        raise RiskInputError("market snapshot exceeds JSON size limit")


@dataclass(frozen=True)
class MarketSnapshot:
    """One versioned price-and-parameter set, in the risk engine's USD unit.

    ``assets`` must contain at least one asset. ``instruments`` may be empty for
    a cash-only deployment. Neither map can change after validation, even when
    the caller subsequently edits its original dictionaries. Versions fit the
    signed 64-bit integer range used by the durable service.
    """
    version: int
    observed_at: datetime
    assets: Mapping[str, AssetSpec]
    instruments: Mapping[str, InstrumentSpec]

    def __post_init__(self) -> None:
        if type(self.version) is not int or not 0 <= self.version <= 2**63 - 1:
            raise RiskInputError("market version must be an integer in 0..2^63-1")
        _aware(self.observed_at, "observed_at")
        assets = _mapping("market assets", self.assets)
        instruments = _mapping("market instruments", self.instruments)
        if not assets:
            raise RiskInputError("market requires at least one asset specification")
        for symbol, spec in assets.items():
            _identifier("market asset", symbol)
            if not isinstance(spec, AssetSpec):
                raise RiskInputError(f"invalid asset specification: {symbol}")
        for symbol, spec in instruments.items():
            _identifier("market instrument", symbol)
            if not isinstance(spec, InstrumentSpec):
                raise RiskInputError(f"invalid instrument specification: {symbol}")
        try:
            observed_at = self.observed_at.astimezone(timezone.utc)
        except (ValueError, OverflowError) as exc:
            raise RiskInputError("observed_at is outside the supported UTC range") from exc
        object.__setattr__(self, "observed_at", observed_at)
        object.__setattr__(self, "assets", MappingProxyType(assets))
        object.__setattr__(self, "instruments", MappingProxyType(instruments))

    def validate(self, *, now: datetime, max_age: timedelta = timedelta(seconds=5),
                 max_future_skew: timedelta = timedelta(seconds=1)) -> None:
        """Fail closed on stale/future observations and malformed clock policy."""
        _aware(now, "now")
        for name, value in (("max_age", max_age), ("max_future_skew", max_future_skew)):
            if not isinstance(value, timedelta) or value < timedelta(0):
                raise RiskInputError(f"{name} must be a nonnegative timedelta")
        try:
            age = now.astimezone(timezone.utc) - self.observed_at
        except (ValueError, OverflowError) as exc:
            raise RiskInputError("now is outside the supported UTC range") from exc
        if age > max_age:
            raise RiskInputError("market snapshot is stale")
        if age < -max_future_skew:
            raise RiskInputError("market snapshot is from the future")

    def to_json(self) -> str:
        """Stable, lossless JSON suitable for persistence and retry comparison."""
        payload = {
            "version": self.version,
            "observed_at": self.observed_at.isoformat(),
            "assets": {symbol: {"price": _canonical(spec.price),
                                "collateral_factor": _canonical(spec.collateral_factor)}
                       for symbol, spec in self.assets.items()},
            "instruments": {
                symbol: {"mark_price": _canonical(spec.mark_price),
                         "initial_margin_rate": _canonical(spec.initial_margin_rate),
                         "maintenance_margin_rate": _canonical(spec.maintenance_margin_rate)}
                for symbol, spec in self.instruments.items()},
        }
        result = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        _json_size(result)
        return result

    @classmethod
    def from_json(cls, value: str) -> MarketSnapshot:
        """Decode only the documented schema, never JSON monetary numbers."""
        _json_size(value)
        try:
            payload = json.loads(value, object_pairs_hook=_pairs, parse_constant=_constant)
        except (ValueError, RecursionError) as exc:
            raise RiskInputError("invalid market JSON") from exc
        _strict_fields(payload, {"version", "observed_at", "assets", "instruments"}, "market")
        if not isinstance(payload["observed_at"], str) or len(payload["observed_at"]) > 64:
            raise RiskInputError("observed_at must be an ISO-8601 timestamp")
        try:
            observed_at = datetime.fromisoformat(payload["observed_at"].replace("Z", "+00:00"))
        except ValueError as exc:
            raise RiskInputError("invalid observed_at timestamp") from exc
        raw_assets = _mapping("market assets", payload["assets"])
        raw_instruments = _mapping("market instruments", payload["instruments"])
        assets = {}
        instruments = {}
        for symbol, spec in raw_assets.items():
            _strict_fields(spec, {"price", "collateral_factor"}, f"asset {symbol}")
            assets[symbol] = AssetSpec(_number(spec["price"], "price"),
                                      _number(spec["collateral_factor"], "collateral_factor"))
        for symbol, spec in raw_instruments.items():
            _strict_fields(spec, {"mark_price", "initial_margin_rate", "maintenance_margin_rate"},
                           f"instrument {symbol}")
            instruments[symbol] = InstrumentSpec(
                _number(spec["mark_price"], "mark_price"),
                _number(spec["initial_margin_rate"], "initial_margin_rate"),
                _number(spec["maintenance_margin_rate"], "maintenance_margin_rate"))
        return cls(payload["version"], observed_at, assets, instruments)
