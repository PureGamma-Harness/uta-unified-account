"""Managed account projections read from one existing SQLite snapshot.

No ExchangeService/Ledger constructors, schema installation, risk admission or
financial mutations are used here. Missing data is never reconstructed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
from threading import local

from .decision_audit import DecisionAudit
from .market import MarketSnapshot
from .models import RiskInputError
from .service import ServiceError
from .storage import Database, StorageError


_MAX_JSON = 4 * 1024 * 1024
_MAX_PAGE = 200
_MAX_INT = 2**63 - 1
_DECIMAL = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", re.ASCII)
_DEBT_DIGITS = 38  # Existing durable ledger/credit codec contract, not a display precision.
_REQUIRED = {"uta_authority", "uta_schema", "uta_config", "uta_accounts", "uta_market",
             "uta_orders", "uta_positions", "uta_liabilities", "uta_events", "uta_liquidation_accounts",
             "ledger_schema", "ledger_assets", "ledger_balances", "ledger_events", "ledger_postings",
             "writer_fence_authority", "writer_fence_lease", "writer_fence_events"}


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value):
    return sha256(value.encode("utf-8")).hexdigest()


def _object(value):
    if not isinstance(value, str) or len(value) > _MAX_JSON:
        raise ServiceError("view_data_invalid", "stored view data is oversized or malformed", 503)
    try:
        def pairs(items):
            result = {}
            for key, item in items:
                if key in result:
                    raise ValueError("duplicate key")
                result[key] = item
            return result
        def constant(_):
            raise ValueError("nonstandard number")
        result = json.loads(value, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, TypeError, RecursionError):
        raise ServiceError("view_data_invalid", "stored JSON is invalid", 503) from None
    if not isinstance(result, dict):
        raise ServiceError("view_data_invalid", "stored JSON object is required", 503)
    return result


def _decimal_text(value):
    if not isinstance(value, str) or len(value) > 512 or _DECIMAL.fullmatch(value) is None:
        raise ServiceError("view_data_invalid", "stored monetary string is invalid", 503)
    try:
        parsed = Decimal(value)
    except Exception:
        raise ServiceError("view_data_invalid", "stored monetary string is invalid", 503) from None
    if not parsed.is_finite() or abs(parsed.as_tuple().exponent) > 512:
        raise ServiceError("view_data_invalid", "stored monetary string is outside supported view bounds", 503)
    return value


def _liability_text(value, scale):
    text = _decimal_text(value)
    parts = Decimal(text).as_tuple()
    if len(text) > 80 or len(parts.digits) > _DEBT_DIGITS or not -38 <= parts.exponent <= 38:
        raise ServiceError("view_data_invalid", "stored gross liability exceeds supported precision", 503)
    # Tuple/integer conversion is exact even with hostile Decimal precision,
    # exponent limits or rounding traps. Extra fractional zeros are harmless.
    coefficient = int("".join(str(digit) for digit in parts.digits))
    shift = parts.exponent + scale
    if shift >= 0:
        units, remainder = coefficient * 10 ** shift, 0
    else:
        units, remainder = divmod(coefficient, 10 ** -shift)
    if remainder or units >= 10 ** _DEBT_DIGITS or (parts.sign and coefficient != 0):
        raise ServiceError("view_data_invalid", "stored gross liability is outside its asset minor-unit range", 503)
    return text


def _amount(units, scale):
    if (not isinstance(units, str) or not re.fullmatch(r"-?(?:0|[1-9][0-9]{0,511})", units, re.ASCII)
            or type(scale) is not int or not 0 <= scale <= 18):
        raise ServiceError("view_data_invalid", "stored minor units or asset scale is invalid", 503)
    integer = int(units)
    value = Decimal((int(integer < 0), tuple(int(ch) for ch in str(abs(integer))), -scale))
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


class _ExistingViewDatabase(Database):
    def __init__(self, path, *, timeout):
        super().__init__(path, timeout=timeout)
        self._reader_identity = local()

    def _private_file(self):
        try:
            info = os.stat(self.path, follow_symlinks=False)
        except OSError as exc:
            raise StorageError("existing view authority unavailable; creation is forbidden") from exc
        self._validate_info(info)
        identity = info.st_dev, info.st_ino
        self._reader_identity.value = identity
        return identity

    @staticmethod
    def _validate_info(info):
        if (not stat.S_ISREG(info.st_mode) or info.st_size <= 0 or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) & 0o077):
            raise StorageError("view authority must remain an existing nonempty private service-user-owned file")

    def _connect(self):
        # Raw open/fstat/close of this inode would release this process's OTHER
        # SQLite fcntl locks. Only SQLite may open/close the published DB here.
        identity = self._private_file()
        connection = sqlite3.connect(Path(self.path).as_uri() + "?mode=ro", uri=True,
                                     timeout=self.timeout, isolation_level=None)
        try:
            info = os.stat(self.path, follow_symlinks=False)
            self._validate_info(info)
            if (info.st_dev, info.st_ino) != identity:
                raise StorageError("view authority changed during open")
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA query_only=ON")
            connection.execute(f"PRAGMA busy_timeout={int(self.timeout * 1000)}")
            return connection
        except BaseException:
            connection.close()
            raise


class ManagedAccountViews:
    def __init__(self, database: Database, *, shard=None, layout_hash=None, clock=None):
        if not isinstance(database, Database) or database.writer_token is not None:
            raise ValueError("views require an unbound existing database")
        if clock is not None and not callable(clock):
            raise ValueError("clock must be callable")
        self.database = _ExistingViewDatabase(database.path, timeout=database.timeout)
        self.shard, self.layout_hash = shard, layout_hash
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def _context(self, connection, account_id):
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not _REQUIRED <= tables:
            raise ServiceError("view_schema_unavailable", "managed view tables are missing; no repair is attempted", 503)
        account = connection.execute("SELECT version FROM uta_accounts WHERE account_id=?", (account_id,)).fetchone()
        if account is None:
            raise ServiceError("account_not_found", "unknown account", 404)
        if type(account["version"]) is not int or not 0 <= account["version"] <= _MAX_INT:
            raise ServiceError("view_data_invalid", "stored account version is invalid", 503)
        authority_kind = connection.execute("SELECT kind FROM uta_authority WHERE singleton=1").fetchone()
        if authority_kind is None or authority_kind[0] != "exchange":
            raise ServiceError("view_authority_invalid", "view source is not an exchange authority", 503)
        versions = connection.execute("SELECT version FROM uta_schema").fetchall()
        if len(versions) != 1 or versions[0][0] not in (2, 3):
            raise ServiceError("view_format_unsupported", "unsupported trading view schema", 501)
        ledger_version = connection.execute("SELECT version FROM ledger_schema WHERE singleton=1").fetchone()
        if ledger_version is None or ledger_version[0] != 1:
            raise ServiceError("view_format_unsupported", "unsupported ledger view schema", 501)
        if self.shard is not None:
            identity = connection.execute("SELECT shard,layout_hash,initialized FROM router_shard_identity WHERE singleton=1").fetchone()
            if identity is None or tuple(identity) != (self.shard, self.layout_hash, 1):
                raise ServiceError("view_authority_invalid", "shard view identity differs from the configured layout", 503)
        audited = versions[0][0] == 3
        if audited:
            DecisionAudit.validate(connection)
        authority = connection.execute("SELECT authority_id,canonical_path FROM writer_fence_authority WHERE singleton=1").fetchone()
        if authority is None or authority["canonical_path"] != self.database.path:
            raise ServiceError("view_authority_invalid", "managed view authority identity is invalid", 503)
        now = self.clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ServiceError("view_clock_unavailable", "view freshness clock is unavailable", 503)
        config = {row["key"]: row["value"] for row in connection.execute("SELECT key,value FROM uta_config WHERE key IN ('policy','risk_policy','halted')")}
        if set(config) != {"policy", "risk_policy", "halted"} or config["halted"] not in ("true", "false"):
            raise ServiceError("view_policy_unavailable", "stored financial policy is incomplete", 503)
        policy, risk_policy = _object(config["policy"]), _object(config["risk_policy"])
        if risk_policy.get("mode") not in ("legacy_reference", "phase1_cross"):
            raise ServiceError("view_format_unsupported", "unsupported financial policy mode", 501)
        age = policy.get("max_price_age_us")
        if type(age) is not int or not 0 < age <= 300000000:
            raise ServiceError("view_policy_unavailable", "stored market age policy is invalid", 503)
        policy_ref = {"kind": "persisted_financial_config", "id": "config:" + _digest(_encoded({"policy": policy, "risk_policy": risk_policy})),
                      "risk_mode": risk_policy.get("mode"), "archived_policy_id": None}
        market_row = connection.execute("SELECT payload FROM uta_market WHERE singleton=1").fetchone()
        market_info = {"freshness": "missing", "version": None, "observed_at": None,
                       "payload_digest": None, "evidence": "unavailable"}
        market_id = None
        if market_row is not None:
            raw = market_row[0]
            try:
                market = MarketSnapshot.from_json(raw)
            except RiskInputError:
                raise ServiceError("view_market_invalid", "stored market is malformed", 503) from None
            delta = now.astimezone(timezone.utc) - market.observed_at
            freshness = "future" if delta < -timedelta(seconds=1) else "stale" if delta > timedelta(microseconds=age) else "fresh_as_of_read"
            market_info = {"freshness": freshness, "version": market.version, "observed_at": market.observed_at.isoformat(),
                           "payload_digest": _digest(raw), "evidence": "legacy_unarchived"}
            if audited:
                candidate = "market:" + _digest(raw)
                archive = connection.execute("SELECT payload,content_digest FROM uta_market_history WHERE snapshot_id=?", (candidate,)).fetchone()
                if archive is None or tuple(archive) != (raw, _digest(raw)):
                    raise ServiceError("view_evidence_unavailable", "current market archive is missing or inconsistent", 503)
                market_id, market_info["evidence"] = candidate, "recorded"
        event_watermark = connection.execute("SELECT COALESCE(MAX(sequence),0) FROM uta_events").fetchone()[0]
        account_watermark = connection.execute("SELECT COALESCE(MAX(sequence),0) FROM uta_events WHERE account_id=?", (account_id,)).fetchone()[0]
        ledger_watermark = connection.execute("SELECT COALESCE(MAX(sequence),0) FROM ledger_events WHERE sealed=1").fetchone()[0]
        device, inode = self.database._reader_identity.value
        stream_id = "account-stream:" + _digest(_encoded([authority["authority_id"], self.database.path, device, inode, account_id]))
        context = {"account_id": account_id, "account_version": account["version"], "authority_id": authority["authority_id"],
                   "shard": self.shard, "stream_id": stream_id, "trading_schema": versions[0][0],
                   "market_snapshot_id": market_id, "market": market_info, "policy_ref": policy_ref,
                   "events_watermark": event_watermark, "account_events_watermark": account_watermark,
                   "ledger_watermark": ledger_watermark, "checked_at": now.astimezone(timezone.utc).isoformat(),
                   "reporting_currency": "USD", "local_halt_observed": config["halted"] == "true",
                   "risk": {"status": "unsupported", "reason": "live_risk_recomputation_not_enabled"}}
        return context, audited

    @staticmethod
    def _bounds(options, context, watermark):
        after, limit = options.get("after", 0), options.get("limit", 100)
        until = options.get("until", watermark)
        for value in (after, until):
            if type(value) is not int or not 0 <= value <= _MAX_INT:
                raise ServiceError("invalid_query", "cursor must be a bounded nonnegative integer")
        if type(limit) is not int or not 1 <= limit <= _MAX_PAGE:
            raise ServiceError("invalid_query", "limit must be 1..200")
        if after > watermark or until > watermark:
            raise ServiceError("view_cursor_ahead", "cursor exceeds the current watermark; rebuild from a new snapshot", 409)
        if until < after:
            raise ServiceError("invalid_query", "until must not precede after")
        return after, until, limit

    @staticmethod
    def _page(rows, after, until, limit):
        more = len(rows) > limit
        selected = rows[:limit]
        return selected, {"after": after, "until": until, "limit": limit, "has_more": more,
                          "next_after": selected[-1]["cursor"] if more else until}

    def read(self, account_id, resource="account", *, identity=None, **options):
        if resource not in {"account", "orders", "positions", "ledger", "events", "liquidation", "decisions"}:
            raise ServiceError("view_unsupported", "requested financial projection is not supported", 501)
        pageable = resource in {"orders", "positions", "ledger", "events"} and identity is None
        if set(options) - ({"at_version", "stream_id", "after", "until", "limit"} if pageable else {"at_version", "stream_id"}):
            raise ServiceError("invalid_query", "unsupported view query field")
        try:
            with self.database.read_transaction() as connection:
                context, audited = self._context(connection, account_id)
                if options.get("stream_id", context["stream_id"]) != context["stream_id"]:
                    raise ServiceError("view_stream_changed", "stream identity changed; discard the old cursor and rebuild", 409)
                if "at_version" in options and (type(options["at_version"]) is not int or not 0 <= options["at_version"] <= _MAX_INT):
                    raise ServiceError("invalid_query", "at_version must be a nonnegative integer")
                if options.get("at_version", context["account_version"]) != context["account_version"]:
                    raise ServiceError("view_version_changed", "account changed while paging; rebuild from a new snapshot", 409)
                result = {"snapshot": context}
                if resource == "account":
                    assets = connection.execute("SELECT asset,scale FROM ledger_assets ORDER BY asset").fetchall()
                    if len(assets) > 4096:
                        raise ServiceError("view_capacity_exceeded", "account asset projection exceeds supported bounds", 503)
                    if any(type(row["scale"]) is not int or not 0 <= row["scale"] <= 18 for row in assets):
                        raise ServiceError("view_data_invalid", "stored asset scale is invalid", 503)
                    balances = {row["asset"]: {"balance": "0", "scale": row["scale"], "unit": "asset_units"} for row in assets}
                    for row in connection.execute("SELECT asset,units FROM ledger_balances WHERE account=?", ("customer:" + account_id,)):
                        if row["asset"] not in balances:
                            raise ServiceError("view_data_invalid", "balance references an unknown ledger asset", 503)
                        balances[row["asset"]]["balance"] = _amount(row["units"], balances[row["asset"]]["scale"])
                    debts = []
                    for row in connection.execute("SELECT asset,principal,interest FROM uta_liabilities WHERE account_id=? ORDER BY asset LIMIT 4097", (account_id,)):
                        if row["asset"] not in balances:
                            raise ServiceError("view_data_invalid", "stored gross liability is invalid", 503)
                        scale = balances[row["asset"]]["scale"]
                        principal, interest = (_liability_text(row[field], scale) for field in ("principal", "interest"))
                        debts.append({"asset": row["asset"], "principal": principal, "interest": interest,
                                      "scale": scale, "unit": "asset_units"})
                    if len(debts) > 4096:
                        raise ServiceError("view_capacity_exceeded", "liability projection exceeds supported bounds", 503)
                    result["account"] = {"balances": balances, "liabilities": debts,
                        "position_count": connection.execute("SELECT COUNT(*) FROM uta_positions WHERE account_id=?", (account_id,)).fetchone()[0],
                        "order_count": connection.execute("SELECT COUNT(*) FROM uta_orders WHERE account_id=?", (account_id,)).fetchone()[0],
                        "encumbrances": {"status": "not_recomputed"}}
                elif resource in ("orders", "positions"):
                    table = "uta_orders" if resource == "orders" else "uta_positions"
                    watermark = connection.execute(f"SELECT COALESCE(MAX(rowid),0) FROM {table}").fetchone()[0]
                    after, until, limit = self._bounds(options, context, watermark)
                    rows = connection.execute(f"SELECT rowid AS cursor,* FROM {table} WHERE account_id=? AND rowid>? AND rowid<=? ORDER BY rowid LIMIT ?", (account_id, after, until, limit + 1)).fetchall()
                    selected, result["page"] = self._page(rows, after, until, limit)
                    data = []
                    for row in selected:
                        record = dict(row)
                        for field in (("quantity", "limit_price", "filled_quantity", "fee_notional", "charged_fee") if resource == "orders" else ("quantity", "cost_basis")):
                            if field in record:
                                _decimal_text(record[field])
                        if resource == "orders":
                            record["reduce_only"] = bool(record["reduce_only"])
                            record["decision_id"] = record.pop("admission_decision_id", None)
                            record["decision_evidence"] = "recorded" if record["decision_id"] else "legacy_missing"
                            record["reserved_margin"] = None
                            record["reserve_status"] = "not_recomputed"
                        else:
                            record["quantity_unit"], record["cost_basis_unit"] = "base_units", "USD"
                        data.append(record)
                    if identity is not None:
                        if resource != "orders":
                            raise ServiceError("view_unsupported", "single-resource view is not supported", 501)
                        row = connection.execute("SELECT rowid AS cursor,* FROM uta_orders WHERE account_id=? AND order_id=?", (account_id, identity)).fetchone()
                        if row is None:
                            raise ServiceError("order_not_found", "unknown order", 404)
                        record = dict(row)
                        for field in ("quantity", "limit_price", "filled_quantity", "fee_notional", "charged_fee"):
                            if field in record:
                                _decimal_text(record[field])
                        record["reduce_only"] = bool(record["reduce_only"])
                        record["decision_id"] = record.pop("admission_decision_id", None)
                        record.update(decision_evidence="recorded" if record["decision_id"] else "legacy_missing", reserved_margin=None, reserve_status="not_recomputed")
                        result["order"] = record
                        result.pop("page")
                    else:
                        result[resource] = data
                elif resource == "events":
                    after, until, limit = self._bounds(options, context, context["events_watermark"])
                    rows = connection.execute("SELECT sequence AS cursor,* FROM uta_events WHERE account_id=? AND sequence>? AND sequence<=? ORDER BY sequence LIMIT ?", (account_id, after, until, limit + 1)).fetchall()
                    selected, result["page"] = self._page(rows, after, until, limit)
                    result["events"] = [{**dict(row), "payload": _object(row["payload"])} for row in selected]
                elif resource == "ledger":
                    after, until, limit = self._bounds(options, context, context["ledger_watermark"])
                    customer = "customer:" + account_id
                    rows = connection.execute("SELECT sequence AS cursor,event_id,event_hash FROM ledger_events e WHERE sealed=1 AND sequence>? AND sequence<=? AND EXISTS(SELECT 1 FROM ledger_postings p WHERE p.sequence=e.sequence AND p.account=?) ORDER BY sequence LIMIT ?", (after, until, customer, limit + 1)).fetchall()
                    selected, result["page"] = self._page(rows, after, until, limit)
                    result["ledger"] = []
                    for row in selected:
                        postings = connection.execute("SELECT p.ordinal,p.asset,p.units,a.scale FROM ledger_postings p JOIN ledger_assets a ON a.asset=p.asset WHERE p.sequence=? AND p.account=? ORDER BY p.ordinal", (row["cursor"], customer)).fetchall()
                        if len(postings) > 4096:
                            raise ServiceError("view_capacity_exceeded", "ledger projection exceeds supported bounds", 503)
                        result["ledger"].append({**dict(row), "postings": [{**dict(p), "amount": _amount(p["units"], p["scale"]), "unit": "asset_units"} for p in postings], "projection": "customer_postings_only"})
                elif resource == "liquidation":
                    row = connection.execute("SELECT * FROM uta_liquidation_accounts WHERE account_id=?", (account_id,)).fetchone()
                    result["liquidation"] = {"status": "recorded" if row is not None else "not_evaluated", "stored_state": dict(row) if row is not None else None,
                                             "meaning": "stored_supervisor_state_not_live_risk_assessment"}
                else:
                    if not audited:
                        raise ServiceError("decision_evidence_unsupported", "legacy authority has no decision archive capability", 501)
                    result["decision"] = self._decision(connection, account_id, identity)
                return result
        except (StorageError, sqlite3.Error, OSError) as exc:
            raise ServiceError("view_unavailable", "consistent managed view is unavailable; no repair or fallback", 503) from exc

    @staticmethod
    def _decision(connection, account_id, identity):
        row = connection.execute("SELECT * FROM uta_risk_decisions WHERE decision_id=? AND account_id=?", (identity, account_id)).fetchone()
        if row is None:
            raise ServiceError("decision_not_found", "decision not found in the permitted account scope", 404)
        record = dict(row)
        inputs, summary = _object(record.pop("input_payload")), _object(record.pop("summary_payload"))
        expected = "decision:" + _digest(_encoded([record["kind"], account_id, record["business_id"]]))
        if (identity != expected or not isinstance(inputs.get("before"), dict) or not isinstance(inputs.get("after"), dict)
                or inputs["before"].get("version") != record["pre_version"] or inputs["after"].get("version") != record["post_version"]):
            raise ServiceError("view_evidence_invalid", "decision identity or version evidence is inconsistent", 503)
        market = connection.execute("SELECT * FROM uta_market_history WHERE snapshot_id=?", (record["market_snapshot_id"],)).fetchone()
        policy = connection.execute("SELECT payload FROM uta_risk_policies WHERE policy_id=?", (record["policy_id"],)).fetchone()
        artifact = connection.execute("SELECT manifest FROM uta_code_artifacts WHERE artifact_id=?", (record["artifact_id"],)).fetchone()
        if (market is None or policy is None or artifact is None
                or market["snapshot_id"] != "market:" + _digest(market["payload"])
                or market["content_digest"] != _digest(market["payload"])
                or record["policy_id"] != "policy:" + _digest(policy[0])
                or record["artifact_id"] != "artifact:" + _digest(artifact[0])):
            raise ServiceError("view_evidence_invalid", "decision archive links or digests are inconsistent", 503)
        manifest = _object(artifact[0])
        return {**record, "inputs": inputs, "summary": summary,
                "market": {**dict(market), "payload": _object(market["payload"])}, "policy": _object(policy[0]),
                "artifact": {key: manifest.get(key) for key in ("app_version", "python_implementation", "python_version", "sqlite_version", "source_digest", "signed")},
                "verification": "archived_content_ids_and_versions_only; not live risk or replay approval"}
