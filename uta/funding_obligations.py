"""Explicit, fresh-authority USD funding obligations; no background activation.

Claims fence this single SQLite obligation executor, not a managed/HA writer.
Trusted immutable code, a trusted nondecreasing observed UTC clock and the
existing native financial transaction are required. No customer endpoint exists.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from fractions import Fraction
from hashlib import sha256
import json
import secrets

from .funding_local import FundingLocal, _parse
from .ledger import Posting
from .market import MarketSnapshot
from .perpetual_funding import (FundingError, FundingPolicy, FundingPosition,
    canonical, decimal_text, name, number, period_time, plan_funding, units_decimal)
from .products import ProductKind
from .portfolio import PortfolioError
from .service import ServiceError


_RESERVE = "system:funding-obligations-reserve"
_CLEARING = "system:funding-obligations-clearing"
_PREFIX = "funding-obligations:"
_STATES = ("SCHEDULED", "DUE", "WAITING_DATA", "WAITING_CAPITAL", "APPLIED", "REVIEW_REQUIRED")
_ARCHIVE_LIMIT = 1024 * 1024
_MAX_OBLIGATIONS = 1000
_MAX_COMMANDS = 10000
_TABLES = (
    "CREATE TABLE funding_obligations_config(singleton INTEGER PRIMARY KEY CHECK(singleton=1),payload TEXT NOT NULL,digest TEXT NOT NULL)",
    "CREATE TABLE funding_obligations_clock(singleton INTEGER PRIMARY KEY CHECK(singleton=1),last_seen TEXT NOT NULL)",
    """CREATE TABLE funding_obligations_tasks(
        obligation_id TEXT PRIMARY KEY,symbol TEXT NOT NULL,period_end TEXT NOT NULL,rate TEXT,
        schedule_command_id TEXT NOT NULL UNIQUE,config_sha TEXT NOT NULL,
        state TEXT NOT NULL CHECK(state IN ('SCHEDULED','DUE','WAITING_DATA','WAITING_CAPITAL','APPLIED','REVIEW_REQUIRED')),
        reason TEXT NOT NULL,revision INTEGER NOT NULL CHECK(revision>=0),generation INTEGER NOT NULL CHECK(generation>=0),
        owner TEXT,nonce TEXT,until_at TEXT,cut_sha TEXT,receipt_sha TEXT,
        UNIQUE(symbol,period_end),CHECK((owner IS NULL AND nonce IS NULL AND until_at IS NULL) OR
        (owner IS NOT NULL AND nonce IS NOT NULL AND until_at IS NOT NULL)))""",
    """CREATE TABLE funding_obligations_commands(command_id TEXT PRIMARY KEY,kind TEXT NOT NULL,
        obligation_id TEXT NOT NULL REFERENCES funding_obligations_tasks(obligation_id),
        request TEXT NOT NULL,result TEXT NOT NULL,result_sha TEXT NOT NULL)""",
    """CREATE TABLE funding_obligations_cuts(obligation_id TEXT PRIMARY KEY REFERENCES funding_obligations_tasks(obligation_id),
        command_id TEXT NOT NULL UNIQUE,payload TEXT NOT NULL,digest TEXT NOT NULL)""",
    """CREATE TABLE funding_obligations_receipts(obligation_id TEXT PRIMARY KEY REFERENCES funding_obligations_tasks(obligation_id),
        command_id TEXT NOT NULL UNIQUE,capital_deposit_reference TEXT UNIQUE,payload TEXT NOT NULL,digest TEXT NOT NULL)""",
    """CREATE TABLE funding_obligations_events(sequence INTEGER PRIMARY KEY AUTOINCREMENT,
        obligation_id TEXT NOT NULL REFERENCES funding_obligations_tasks(obligation_id),
        command_id TEXT NOT NULL UNIQUE REFERENCES funding_obligations_commands(command_id),
        payload TEXT NOT NULL,previous_hash TEXT NOT NULL,event_hash TEXT NOT NULL)""",
)
_IMMUTABLE = ("config", "commands", "cuts", "receipts", "events")
_SCHEMA = _TABLES + tuple(
    "CREATE TRIGGER funding_obligations_" + table + "_no_" + action.lower()
    + " BEFORE " + action + " ON funding_obligations_" + table
    + " BEGIN SELECT RAISE(ABORT,'immutable funding obligation evidence'); END"
    for table in _IMMUTABLE for action in ("UPDATE", "DELETE")) + (
    "CREATE TRIGGER funding_obligations_config_no_replace BEFORE INSERT ON funding_obligations_config WHEN EXISTS(SELECT 1 FROM funding_obligations_config) BEGIN SELECT RAISE(ABORT,'funding config cannot be replaced'); END",
    "CREATE TRIGGER funding_obligations_tasks_identity BEFORE UPDATE OF obligation_id,symbol,period_end,rate,schedule_command_id,config_sha ON funding_obligations_tasks BEGIN SELECT RAISE(ABORT,'funding identity is immutable'); END",
    "CREATE TRIGGER funding_obligations_tasks_no_delete BEFORE DELETE ON funding_obligations_tasks BEGIN SELECT RAISE(ABORT,'funding obligations cannot be discarded'); END",
    "CREATE TRIGGER funding_obligations_tasks_no_replace BEFORE INSERT ON funding_obligations_tasks WHEN EXISTS(SELECT 1 FROM funding_obligations_tasks WHERE obligation_id=NEW.obligation_id OR (symbol=NEW.symbol AND period_end=NEW.period_end)) BEGIN SELECT RAISE(ABORT,'funding obligation cannot be replaced'); END",
    "CREATE TRIGGER funding_obligations_tasks_terminal BEFORE UPDATE ON funding_obligations_tasks WHEN OLD.state='APPLIED' OR (OLD.state='REVIEW_REQUIRED' AND NEW.state!='REVIEW_REQUIRED') BEGIN SELECT RAISE(ABORT,'terminal funding obligation cannot be reopened'); END",
    "CREATE TRIGGER funding_obligations_commands_no_replace BEFORE INSERT ON funding_obligations_commands WHEN EXISTS(SELECT 1 FROM funding_obligations_commands WHERE command_id=NEW.command_id) BEGIN SELECT RAISE(ABORT,'funding command cannot be replaced'); END",
    "CREATE TRIGGER funding_obligations_cuts_no_replace BEFORE INSERT ON funding_obligations_cuts WHEN EXISTS(SELECT 1 FROM funding_obligations_cuts WHERE obligation_id=NEW.obligation_id OR command_id=NEW.command_id) BEGIN SELECT RAISE(ABORT,'funding cut cannot be replaced'); END",
    "CREATE TRIGGER funding_obligations_receipts_no_replace BEFORE INSERT ON funding_obligations_receipts WHEN EXISTS(SELECT 1 FROM funding_obligations_receipts WHERE obligation_id=NEW.obligation_id OR command_id=NEW.command_id OR capital_deposit_reference=NEW.capital_deposit_reference) BEGIN SELECT RAISE(ABORT,'funding receipt cannot be replaced'); END",
    "CREATE TRIGGER funding_obligations_events_no_replace BEFORE INSERT ON funding_obligations_events WHEN EXISTS(SELECT 1 FROM funding_obligations_events WHERE sequence=NEW.sequence OR command_id=NEW.command_id) BEGIN SELECT RAISE(ABORT,'funding event cannot be replaced'); END",
    "CREATE TRIGGER funding_obligations_clock_no_regress BEFORE UPDATE ON funding_obligations_clock WHEN NEW.singleton!=OLD.singleton OR NEW.last_seen<OLD.last_seen BEGIN SELECT RAISE(ABORT,'funding clock cannot regress'); END",
    "CREATE TRIGGER funding_obligations_clock_no_delete BEFORE DELETE ON funding_obligations_clock BEGIN SELECT RAISE(ABORT,'funding clock cannot be deleted'); END",
    "CREATE TRIGGER funding_obligations_clock_no_replace BEFORE INSERT ON funding_obligations_clock WHEN EXISTS(SELECT 1 FROM funding_obligations_clock) BEGIN SELECT RAISE(ABORT,'funding clock cannot be replaced'); END",
)


def _digest(value):
    return sha256(canonical(value).encode()).hexdigest()


def _key(kind, *parts):
    return _PREFIX + kind + ":" + _digest(parts)


def _stamp(value):
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _artifact():
    from .decision_audit import code_artifact
    from .credit_artifact import _MODULES, _loaded_modules
    # Reuse the existing fixed platform closure, including schema helpers and
    # transaction fencing, plus these optional financial modules. Do not alter
    # its exclusions or accept source-file hashes as loaded-function coverage.
    functions, constants = _loaded_modules(_MODULES + ("perpetual_funding", "funding_local", "funding_obligations"))
    return {"format": 1, "core": code_artifact(), "loaded_functions": functions,
            "loaded_constants": constants, "activation": "SYNTHETIC_LOCAL_ONLY", "signed": False}


class FundingObligations:
    """Inactive local slice; pending cash is not an admission/withdrawal hold.

    No whole-authority old-binary fence, production timer, custody or HA claim.
    Claim checks observe the serialized writer clock/generation; they do not
    prove that physical COMMIT/fsync finishes before the lease timestamp.
    """
    def __init__(self, service, policy: FundingPolicy):
        FundingLocal._native(service, policy)
        self.service, self.policy, self.artifact = service, policy, _artifact()
        with service.database.read_transaction() as connection:
            # Status must survive a recorded financial REVIEW rejection. This
            # validates capability/schema/code, not financial health; apply()
            # requires complete verification inside its own writer transaction.
            self._configuration(connection)

    @classmethod
    def install_synthetic_fresh(cls, service, policy: FundingPolicy, *, capital_account_id: str):
        FundingLocal._native(service, policy)
        name(capital_account_id, "declared treasury")
        artifact = _artifact()
        with service._transaction() as connection:
            FundingLocal._unmanaged(connection)
            if connection.execute("SELECT 1 FROM sqlite_master WHERE name GLOB 'funding_local_*' OR name GLOB 'funding_obligations_*' LIMIT 1").fetchone():
                raise FundingError("funding_obligations_migration_required", "old/new funding capability requires offline migration")
            for table in ("uta_accounts", "uta_positions", "uta_orders", "uta_fills", "uta_deposits", "uta_liabilities", "ledger_events", "uta_events"):
                if connection.execute("SELECT 1 FROM " + table + " LIMIT 1").fetchone():
                    raise FundingError("funding_obligations_migration_required", "only never-used synthetic authorities are supported")
            for statement in _SCHEMA:
                connection.execute(statement)
            config = {"format": 1, "policy": policy.payload(), "artifact": artifact,
                      "trading_policy": FundingLocal._trading_policy(service),
                      "capital_account_id": capital_account_id, "usd_scale": service.scales["USD"],
                      "lease_clock": "TRUSTED_UTC_WITH_PERSISTENT_OBSERVED_HIGH_WATERMARK"}
            payload = canonical(config)
            if len(payload.encode()) > _ARCHIVE_LIMIT:
                raise FundingError("funding_archive_limit", "funding capability archive exceeds bound")
            connection.execute("INSERT INTO funding_obligations_config VALUES(1,?,?)", (payload, _digest(config)))
            connection.execute("INSERT INTO funding_obligations_clock VALUES(1,?)", (_stamp(service._now()),))
        return cls(service, policy)

    def _configuration(self, connection):
        from .existing_services import _verify_fixed_schema
        FundingLocal._unmanaged(connection)
        if connection.execute("SELECT 1 FROM sqlite_master WHERE name GLOB 'funding_local_*' LIMIT 1").fetchone():
            raise FundingError("funding_obligations_migration_required", "old prototype cannot coexist with durable obligations")
        _verify_fixed_schema(connection, _SCHEMA)
        row = connection.execute("SELECT payload,digest FROM funding_obligations_config WHERE singleton=1").fetchone()
        if row is None:
            raise FundingError("funding_obligations_configuration", "missing durable capability", 503)
        config = _parse(row["payload"])
        if (set(config) != {"format", "policy", "artifact", "trading_policy", "capital_account_id", "usd_scale", "lease_clock"}
                or row["digest"] != _digest(config) or type(config["format"]) is not int or config["format"] != 1
                or config["policy"] != self.policy.payload() or config["artifact"] != self.artifact
                or config["artifact"] != _artifact() or type(config["usd_scale"]) is not int or config["usd_scale"] != self.service.scales["USD"]
                or config["trading_policy"] != FundingLocal._trading_policy(self.service)
                or config["lease_clock"] != "TRUSTED_UTC_WITH_PERSISTENT_OBSERVED_HIGH_WATERMARK"):
            raise FundingError("funding_obligations_configuration", "code/rules changed; offline migration required", 503)
        return config, row["digest"]

    def _clock(self, connection):
        now = self.service._now().astimezone(timezone.utc)
        previous = connection.execute("SELECT last_seen FROM funding_obligations_clock WHERE singleton=1").fetchone()
        if previous is None or now < datetime.fromisoformat(previous[0]):
            raise FundingError("funding_obligations_clock_regression", "observed UTC regressed; authority requires review", 503)
        connection.execute("UPDATE funding_obligations_clock SET last_seen=? WHERE singleton=1", (_stamp(now),))
        return now

    @staticmethod
    def _task(connection, obligation_id):
        row = connection.execute("SELECT * FROM funding_obligations_tasks WHERE obligation_id=?", (obligation_id,)).fetchone()
        if row is None:
            raise FundingError("funding_obligation_not_found", "no committed obligation", 404)
        return row

    @staticmethod
    def _view(row):
        return {key: row[key] for key in ("obligation_id", "symbol", "period_end", "rate", "schedule_command_id",
                "config_sha", "state", "reason", "revision", "generation", "owner", "until_at", "cut_sha", "receipt_sha")} | {
                    "outstanding": row["state"] != "APPLIED",
                    "nonce_digest": None if row["nonce"] is None else sha256(row["nonce"].encode()).hexdigest()}

    @staticmethod
    def _change(connection, obligation_id, **fields):
        allowed = {"state", "reason", "generation", "owner", "nonce", "until_at", "cut_sha", "receipt_sha"}
        if not fields or not set(fields) <= allowed:
            raise FundingError("funding_internal", "unsupported task mutation", 503)
        connection.execute("UPDATE funding_obligations_tasks SET " + ",".join(key + "=?" for key in fields)
                           + ",revision=revision+1 WHERE obligation_id=?", (*fields.values(), obligation_id))

    @staticmethod
    def _previous(connection, command_id, kind, request):
        name(command_id, "command")
        row = connection.execute("SELECT * FROM funding_obligations_commands WHERE command_id=?", (command_id,)).fetchone()
        if row is None:
            return None
        if row["kind"] != kind or row["request"] != canonical(request):
            raise FundingError("funding_idempotency_conflict", "command ID reused with different content")
        result = _parse(row["result"])
        if _digest(result) != row["result_sha"]:
            raise FundingError("funding_obligation_corrupt", "command result digest differs", 503)
        return result

    def _record(self, connection, command_id, kind, request, obligation_id, result):
        if connection.execute("SELECT COUNT(*) FROM funding_obligations_commands").fetchone()[0] >= _MAX_COMMANDS:
            raise FundingError("funding_obligation_capacity", "command archive requires offline capacity review", 503)
        row = self._task(connection, obligation_id)
        result = {"obligation_id": obligation_id, "state_at_commit": row["state"], **result}
        encoded = canonical(result)
        if len(encoded.encode()) > _ARCHIVE_LIMIT:
            raise FundingError("funding_archive_limit", "command result archive exceeds bound", 503)
        connection.execute("INSERT INTO funding_obligations_commands VALUES(?,?,?,?,?,?)",
                           (command_id, kind, obligation_id, canonical(request), encoded, _digest(result)))
        previous = connection.execute("SELECT event_hash FROM funding_obligations_events ORDER BY sequence DESC LIMIT 1").fetchone()
        previous = previous[0] if previous else "0" * 64
        payload = {"task": self._view(row), "command_result_sha": _digest(result)}
        connection.execute("INSERT INTO funding_obligations_events(obligation_id,command_id,payload,previous_hash,event_hash) VALUES(?,?,?,?,?)",
                           (obligation_id, command_id, canonical(payload), previous,
                            _digest([previous, obligation_id, command_id, payload])))
        self.service._event(connection, "FUNDING_OBLIGATION_STATE", None,
                            {"obligation_id": obligation_id, "command_id": command_id,
                             "state": row["state"], "cut_sha": row["cut_sha"], "receipt_sha": row["receipt_sha"]})
        return result

    def schedule(self, command_id, obligation_id, symbol, period_end, *, rate: Decimal | None):
        name(obligation_id, "obligation"); name(symbol, "symbol")
        end, seconds = period_time(period_end)
        if rate is not None:
            number(rate, "rate", maximum=self.policy.max_abs_rate)
        rate_text = None if rate is None else decimal_text(rate)
        request = {"obligation_id": obligation_id, "symbol": symbol, "period_end": end.isoformat(), "rate": rate_text}
        with self.service._transaction() as connection:
            config, digest = self._configuration(connection)
            previous = self._previous(connection, command_id, "schedule", request)
            if previous is not None:
                return previous
            now = self._clock(connection)
            self._product(symbol, seconds)
            if connection.execute("SELECT 1 FROM funding_obligations_tasks WHERE obligation_id=? OR (symbol=? AND period_end=?)",
                                  (obligation_id, symbol, end.isoformat())).fetchone():
                raise FundingError("funding_period_already_scheduled", "one stable obligation per product/period")
            if connection.execute("SELECT COUNT(*) FROM funding_obligations_tasks").fetchone()[0] >= _MAX_OBLIGATIONS:
                raise FundingError("funding_obligation_capacity", "obligation archive requires offline capacity review", 503)
            state = "SCHEDULED" if now < end else "DUE"
            connection.execute("INSERT INTO funding_obligations_tasks VALUES(?,?,?,?,?,?,?,?,0,0,NULL,NULL,NULL,NULL,NULL)",
                               (obligation_id, symbol, end.isoformat(), rate_text, command_id, digest, state, "registered"))
            return self._record(connection, command_id, "schedule", request, obligation_id, {})

    def due(self, command_id, obligation_id):
        name(obligation_id, "obligation")
        request = {"obligation_id": obligation_id}
        with self.service._transaction() as connection:
            self._configuration(connection)
            previous = self._previous(connection, command_id, "due", request)
            if previous is not None:
                return previous
            row, now = self._task(connection, obligation_id), self._clock(connection)
            if row["state"] == "SCHEDULED" and now >= datetime.fromisoformat(row["period_end"]):
                self._change(connection, obligation_id, state="DUE", reason="scheduled_time_reached")
            return self._record(connection, command_id, "due", request, obligation_id, {})

    def claim(self, command_id, obligation_id, owner, *, lease_ms=1000):
        name(obligation_id, "obligation"); name(owner, "executor")
        if type(lease_ms) is not int or not 100 <= lease_ms <= 5000:
            raise FundingError("funding_claim_input", "claim lease must be100..5000ms", 400)
        request = {"obligation_id": obligation_id, "owner": owner, "lease_ms": lease_ms}
        with self.service._transaction() as connection:
            self._configuration(connection)
            previous = self._previous(connection, command_id, "claim", request)
            if previous is not None:
                return previous
            row, now = self._task(connection, obligation_id), self._clock(connection)
            if row["state"] in ("APPLIED", "REVIEW_REQUIRED"):
                result = {"claimed": False, "reason": "terminal_automation_state"}
            elif row["owner"] is not None and now < datetime.fromisoformat(row["until_at"]):
                result = {"claimed": False, "reason": "busy"}
            else:
                token = {"owner": owner, "generation": row["generation"] + 1,
                         "nonce": secrets.token_hex(16), "until_at": _stamp(now + timedelta(milliseconds=lease_ms))}
                state = "DUE" if row["state"] == "SCHEDULED" and now >= datetime.fromisoformat(row["period_end"]) else row["state"]
                self._change(connection, obligation_id, state=state, reason="claimed", generation=token["generation"],
                             owner=owner, nonce=token["nonce"], until_at=token["until_at"])
                result = {"claimed": True, "token": token}
            return self._record(connection, command_id, "claim", request, obligation_id, result)

    @staticmethod
    def _held(row, token, now):
        return (type(token) is dict and set(token) == {"owner", "generation", "nonce", "until_at"}
                and type(token["generation"]) is int
                and all(token[key] == row[key] for key in token)
                and row["until_at"] is not None and now < datetime.fromisoformat(row["until_at"]))

    @staticmethod
    def _checked_token(token):
        if (type(token) is not dict or set(token) != {"owner", "generation", "nonce", "until_at"}
                or type(token["generation"]) is not int or token["generation"] <= 0
                or type(token["nonce"]) is not str or len(token["nonce"]) != 32
                or any(value not in "0123456789abcdef" for value in token["nonce"])
                or type(token["until_at"]) is not str):
            raise FundingError("funding_claim_input", "native claim token required", 400)
        name(token["owner"], "executor")
        try:
            until = datetime.fromisoformat(token["until_at"])
            if until.tzinfo is None or until.utcoffset() is None or _stamp(until) != token["until_at"]:
                raise ValueError("canonical UTC required")
        except ValueError as error:
            raise FundingError("funding_claim_input", "canonical claim expiry required", 400) from error
        return dict(token)

    def _product(self, symbol, seconds):
        product = self.service.product_catalog.require_risk_supported(symbol)
        if (product.kind is not ProductKind.LINEAR_PERPETUAL or product.multiplier != 1
                or product.quote_asset != "USD" or product.settlement_asset != "USD"
                or product.funding_interval_seconds is None or not 1 <= product.funding_interval_seconds <= 86400
                or seconds % product.funding_interval_seconds):
            raise FundingError("funding_product_unsupported", "only aligned multiplier1 USD linear periods are supported")
        return product

    def _wait(self, connection, obligation_id, state, reason):
        self._change(connection, obligation_id, state=state, reason=reason, owner=None, nonce=None, until_at=None)

    def _require_mark(self, market, symbol):
        product = self.service.product_catalog.require_risk_supported(symbol)
        if (product.kind is not ProductKind.LINEAR_PERPETUAL or product.multiplier != 1
                or product.risk_tier not in self.service.portfolio_rules.linear_margin):
            raise FundingError("funding_current_inventory_unsupported", "required instrument has unsupported product or margin rules")
        if symbol not in market.instruments:
            raise ServiceError("funding_required_quote_unavailable", "required instrument mark is missing", 503)

    def _check_current_quotes(self, connection, account, market):
        # Keep native inventory/rule validation. Only its precise missing-price
        # causes, confirmed against the actual snapshot, become retryable data.
        try:
            self.service._risk(connection, account, market)
        except ServiceError as error:
            cause = error.__cause__
            if error.code == "risk_unavailable" and type(cause) is PortfolioError:
                message = str(cause)
                if message.startswith("missing_instrument_price: "):
                    symbol = message.removeprefix("missing_instrument_price: ")
                    if symbol in self.service._positions(connection, account) and symbol not in market.instruments:
                        self._require_mark(market, symbol)
                if message.startswith("missing_price: "):
                    asset = message.removeprefix("missing_price: ")
                    if asset not in market.assets:
                        balance = self.service.ledger.balance(self.service._customer(account), asset, connection=connection)
                        debt = connection.execute("SELECT principal,interest FROM uta_liabilities WHERE account_id=? AND asset=?", (account, asset)).fetchone()
                        if ((balance > 0 and asset not in self.service.portfolio_rules.collaterals)
                                or debt is not None and (Decimal(debt[0]) or Decimal(debt[1])) and asset not in self.service.portfolio_rules.borrow_limits):
                            raise FundingError("funding_current_inventory_unsupported", "required asset has no collateral/borrowing rule") from error
                        raise ServiceError("funding_required_quote_unavailable", "required current asset quote is missing", 503) from error
            if error.code == "market_incomplete" and type(cause) is KeyError and len(cause.args) == 1:
                symbol = cause.args[0]
                if symbol not in market.instruments and any(order["symbol"] == symbol for order in self.service._live_orders(connection, account)):
                    self._require_mark(market, symbol)
            raise

    def capture(self, command_id, obligation_id, token, *, market_snapshot_id, resolved_rate: Decimal | None = None):
        name(obligation_id, "obligation")
        token = self._checked_token(token)
        if resolved_rate is not None:
            number(resolved_rate, "resolved approved rate", maximum=self.policy.max_abs_rate)
        resolved_text = None if resolved_rate is None else decimal_text(resolved_rate)
        request = {"obligation_id": obligation_id, "token": token, "market_snapshot_id": market_snapshot_id,
                   "resolved_rate": resolved_text}
        with self.service._transaction() as connection:
            config, digest = self._configuration(connection)
            previous = self._previous(connection, command_id, "capture", request)
            if previous is not None:
                return previous
            row, now = self._task(connection, obligation_id), self._clock(connection)
            if not self._held(row, token, now):
                return self._record(connection, command_id, "capture", request, obligation_id, {"fenced": True, "status": 409})
            if row["cut_sha"] is not None:
                return self._record(connection, command_id, "capture", request, obligation_id, {"cut_sha": row["cut_sha"], "already_captured": True})
            end = datetime.fromisoformat(row["period_end"])
            if now < end:
                return self._record(connection, command_id, "capture", request, obligation_id, {"reason": "not_due"})
            if now - end > timedelta(milliseconds=self.policy.trigger_lateness_ms):
                self._wait(connection, obligation_id, "REVIEW_REQUIRED", "trusted_boundary_cut_missing")
                return self._record(connection, command_id, "capture", request, obligation_id, {})
            try:
                if row["rate"] is None and resolved_rate is None:
                    raise ServiceError("funding_rate_unavailable", "approved boundary rate missing", 503)
                if row["rate"] is not None and resolved_text is not None and resolved_text != row["rate"]:
                    raise FundingError("funding_rate_conflict", "scheduled approved rate cannot change")
                rate = resolved_rate if row["rate"] is None else Decimal(row["rate"])
                product = self._product(row["symbol"], period_time(end)[1])
                market = self.service._market(connection)
                self._require_mark(market, row["symbol"])
                if market_snapshot_id != "sha256:" + sha256(market.to_json().encode()).hexdigest():
                    raise ServiceError("market_unavailable", "expected trusted boundary market differs", 503)
                rows = connection.execute("SELECT p.account_id,p.quantity,p.cost_basis,a.version FROM uta_positions p JOIN uta_accounts a ON a.account_id=p.account_id WHERE p.symbol=? ORDER BY p.account_id LIMIT ?",
                                          (row["symbol"], self.policy.max_accounts + 1)).fetchall()
                positions = tuple(FundingPosition(item["account_id"], Decimal(item["quantity"])) for item in rows)
                if config["capital_account_id"] in {position.account_id for position in positions}:
                    raise FundingError("funding_capital_account_exposed", "declared treasury cannot be a participant")
                plan = plan_funding(self.policy, row["symbol"], end, interval_seconds=product.funding_interval_seconds,
                                    mark=market.instruments[row["symbol"]].mark_price, rate=rate,
                                    usd_scale=config["usd_scale"], positions=positions)
                cut = {"obligation_id": obligation_id, "period_end": row["period_end"], "symbol": row["symbol"],
                       "observed_at": _stamp(now), "config_sha": digest, "artifact_sha": _digest(self.artifact),
                       "resolved_rate": resolved_text,
                       "policy": self.policy.payload(), "market_payload": market.to_json(), "market_snapshot_id": market_snapshot_id,
                       "event_watermark": connection.execute("SELECT COALESCE(MAX(sequence),0) FROM uta_events").fetchone()[0],
                       "positions": [{"account_id": item["account_id"], "account_version": item["version"],
                                      "quantity": item["quantity"], "cost_basis": item["cost_basis"]} for item in rows], "plan": plan.payload()}
                if len(canonical(cut).encode()) > _ARCHIVE_LIMIT:
                    raise FundingError("funding_archive_limit", "trusted cut exceeds archive limit")
                if not self._held(row, token, self._clock(connection)):
                    self._wait(connection, obligation_id, "DUE", "claim_expired_before_cut")
                else:
                    connection.execute("INSERT INTO funding_obligations_cuts VALUES(?,?,?,?)", (obligation_id, command_id, canonical(cut), _digest(cut)))
                    self._change(connection, obligation_id, state="DUE", reason="trusted_cut_saved", cut_sha=_digest(cut))
            except ServiceError as error:
                self._wait(connection, obligation_id, "WAITING_DATA", error.code)
            except (FundingError, KeyError, ValueError) as error:
                self._wait(connection, obligation_id, "REVIEW_REQUIRED", getattr(error, "code", "invalid_cut_inventory"))
            return self._record(connection, command_id, "capture", request, obligation_id, {})

    def apply(self, command_id, obligation_id, token, *, capital_deposit_reference=None):
        name(obligation_id, "obligation")
        token = self._checked_token(token)
        if capital_deposit_reference is not None:
            name(capital_deposit_reference, "capital deposit reference")
        request = {"obligation_id": obligation_id, "token": token, "capital_deposit_reference": capital_deposit_reference}
        with self.service._transaction() as connection:
            config, digest = self._configuration(connection)
            previous = self._previous(connection, command_id, "apply", request)
            if previous is not None:
                return previous
            row, now = self._task(connection, obligation_id), self._clock(connection)
            if row["state"] == "APPLIED":
                return self._record(connection, command_id, "apply", request, obligation_id, {"receipt": self._receipt(connection, obligation_id)})
            if row["state"] == "REVIEW_REQUIRED":
                return self._record(connection, command_id, "apply", request, obligation_id, {"reason": "manual_review_required"})
            if not self._held(row, token, now):
                return self._record(connection, command_id, "apply", request, obligation_id, {"fenced": True, "status": 409})
            if row["cut_sha"] is None:
                state = "REVIEW_REQUIRED" if now - datetime.fromisoformat(row["period_end"]) > timedelta(milliseconds=self.policy.trigger_lateness_ms) else "WAITING_DATA"
                self._wait(connection, obligation_id, state, "trusted_boundary_cut_missing")
                return self._record(connection, command_id, "apply", request, obligation_id, {})
            connection.execute("SAVEPOINT funding_obligation_apply")
            try:
                self.verify(connection=connection)
                cut = self._cut(connection, obligation_id)
                receipt = self._cash(connection, row, cut, config, command_id, capital_deposit_reference)
                final_market = self.service._market(connection)
                if receipt["risk_market_payload"] != final_market.to_json():
                    raise ServiceError("market_unavailable", "current risk market changed before confirmation", 503)
                if not self._held(row, token, self._clock(connection)):
                    raise FundingError("funding_claim_expired", "claim expired before application commit")
                if len(canonical(receipt).encode()) > _ARCHIVE_LIMIT:
                    raise FundingError("funding_archive_limit", "funding receipt exceeds archive limit")
                connection.execute("INSERT INTO funding_obligations_receipts VALUES(?,?,?,?,?)",
                    (obligation_id, command_id, capital_deposit_reference, canonical(receipt), _digest(receipt)))
                self._change(connection, obligation_id, state="APPLIED", reason="confirmed_cash_and_current_risk",
                             receipt_sha=_digest(receipt), owner=None, nonce=None, until_at=None)
                connection.execute("RELEASE SAVEPOINT funding_obligation_apply")
                result = {"receipt": receipt}
            except (FundingError, ServiceError, KeyError, ValueError) as error:
                connection.execute("ROLLBACK TO SAVEPOINT funding_obligation_apply")
                connection.execute("RELEASE SAVEPOINT funding_obligation_apply")
                self._clock(connection)
                reason = getattr(error, "code", "funding_application_rejected")
                capital = reason.startswith("funding_capital") or reason == "funding_rounding_capital_insufficient"
                state = "WAITING_CAPITAL" if capital else "WAITING_DATA" if reason in ("market_unavailable", "funding_required_quote_unavailable", "funding_risk_unavailable", "funding_claim_expired") else "REVIEW_REQUIRED"
                self._wait(connection, obligation_id, state, reason)
                result = {"reason": reason, "successful_receipt_emitted": False}
            return self._record(connection, command_id, "apply", request, obligation_id, result)

    def _capital(self, connection, row, config, reference, units):
        if not units:
            if reference is not None:
                raise FundingError("funding_capital_unnecessary", "proof cannot be consumed without a transfer")
            return None
        if reference is None or connection.execute("SELECT 1 FROM funding_obligations_receipts WHERE capital_deposit_reference=?", (reference,)).fetchone():
            raise FundingError("funding_capital_unavailable", "confirmed unused treasury deposit proof required")
        FundingLocal._verify_capital_deposit(self, connection, config, reference, units, config["usd_scale"])
        treasury = config["capital_account_id"]
        self.service._require_unfrozen(connection, treasury)
        for table in ("uta_positions", "uta_liabilities"):
            if connection.execute("SELECT 1 FROM " + table + " WHERE account_id=? LIMIT 1", (treasury,)).fetchone():
                raise FundingError("funding_capital_account_exposed", "treasury has trading/borrowing history")
        amount = units_decimal(units, config["usd_scale"])
        if (self.service._live_orders(connection, treasury) or self.service._locked_assets(connection, treasury)
                or self.service._available_asset(connection, treasury, "USD") < amount):
            raise FundingError("funding_capital_unavailable", "treasury lacks unreserved settled cash")
        event_id = _key("capital", row["obligation_id"])
        previous_version = self.service._require_account(connection, treasury)["version"]
        event = self.service.ledger.post(event_id, (Posting(self.service._customer(treasury), "USD", amount.copy_negate()), Posting(_RESERVE, "USD", amount)), connection=connection)
        self.service._bump(connection, treasury)
        self.service._event(connection, "FUNDING_OBLIGATION_CAPITAL_TRANSFER", treasury,
                            {"obligation_id": row["obligation_id"], "journal_event_id": event_id,
                             "deposit_reference": reference, "amount": decimal_text(amount)})
        return {"source_account_id": treasury, "deposit_reference": reference, "units": str(units),
                "amount": decimal_text(amount), "source_account_pre_version": previous_version,
                "event_id": event_id, "sequence": event.sequence}

    @staticmethod
    def _verify_journal(connection, event_id, sequence, expected):
        return FundingLocal._verify_journal(connection, event_id, sequence, expected)

    def _cash(self, connection, row, cut, config, command_id, capital_reference):
        market = self.service._market(connection)  # Current state, never the historical cut as live risk.
        participants = [leg["account_id"] for leg in cut["plan"]["legs"]]
        for account in participants:
            self._check_current_quotes(connection, account, market)
        before = {account: self.service._audit_state(connection, account) for account in participants}
        reserve = self.service.ledger.balance(_RESERVE, "USD", connection=connection)
        needed = max(Fraction(), -Fraction(reserve) * 10 ** config["usd_scale"] - int(cut["plan"]["clearing_units"]))
        if needed.denominator != 1:
            raise FundingError("funding_reconciliation", "reserve has fractional minor units", 503)
        capital = self._capital(connection, row, config, capital_reference, needed.numerator)
        journals = [] if capital is None else [{key: capital[key] for key in ("event_id", "sequence")}]
        affected = []
        for leg in cut["plan"]["legs"]:
            units = int(leg["cash_units"])
            if not units:
                continue
            amount = units_decimal(units, config["usd_scale"])
            event_id = _key("leg", row["obligation_id"], leg["account_id"])
            event = self.service.ledger.post(event_id, (Posting(self.service._customer(leg["account_id"]), "USD", amount), Posting(_CLEARING, "USD", amount.copy_negate())), connection=connection)
            self.service._bump(connection, leg["account_id"])
            affected.append(leg["account_id"])
            journals.append({"event_id": event_id, "sequence": event.sequence})
        if int(cut["plan"]["clearing_units"]):
            amount = units_decimal(int(cut["plan"]["clearing_units"]), config["usd_scale"])
            event_id = _key("variance", row["obligation_id"])
            event = self.service.ledger.post(event_id, (Posting(_RESERVE, "USD", amount), Posting(_CLEARING, "USD", amount.copy_negate())), connection=connection)
            journals.append({"event_id": event_id, "sequence": event.sequence})
        actions = {}
        for account in affected:
            action = self.service.supervise_account(account, connection=connection)
            stored = connection.execute("SELECT state FROM uta_liquidation_accounts WHERE account_id=?", (account,)).fetchone()
            if stored is None or stored[0] != action["state"] or "persisted_state" in action:
                raise FundingError("funding_risk_unavailable", "risk action did not persist; cash must roll back", 503)
            actions[account] = action
            self.service._event(connection, "FUNDING_OBLIGATION_CASH_APPLIED", account,
                {"obligation_id": row["obligation_id"], "command_id": command_id, "cut_sha": row["cut_sha"]})
        if self.service.ledger.balance(_CLEARING, "USD", connection=connection) != 0:
            raise FundingError("funding_reconciliation", "funding clearing did not return to zero", 503)
        return {"format": 1, "obligation_id": row["obligation_id"], "command_id": command_id,
                "symbol": row["symbol"], "period_end": row["period_end"], "cut_sha": row["cut_sha"],
                "applied_at": _stamp(self.service._now()), "claim_generation": row["generation"],
                "claim_owner": row["owner"], "claim_nonce_digest": sha256(row["nonce"].encode()).hexdigest(),
                "claim_until_at": row["until_at"],
                "config_sha": row["config_sha"], "artifact_sha": _digest(self.artifact),
                "risk_market_payload": market.to_json(), "risk_market_snapshot_id": "sha256:" + sha256(market.to_json().encode()).hexdigest(),
                "account_inputs_before": before,
                "account_inputs_after": {account: self.service._audit_state(connection, account) for account in participants},
                "risk_after": {account: self.service._risk(connection, account, market) for account in participants},
                "risk_actions": actions, "capital_transfer": capital, "journals": journals,
                "reserve_before": decimal_text(reserve), "reserve_after": decimal_text(self.service.ledger.balance(_RESERVE, "USD", connection=connection)),
                "production_approved": False}

    @staticmethod
    def _archived(connection, table, obligation_id):
        row = connection.execute("SELECT payload,digest FROM " + table + " WHERE obligation_id=?", (obligation_id,)).fetchone()
        if row is None:
            return None
        if len(row["payload"].encode()) > _ARCHIVE_LIMIT:
            raise FundingError("funding_obligation_corrupt", "archive exceeds compiled bound", 503)
        value = _parse(row["payload"])
        if _digest(value) != row["digest"]:
            raise FundingError("funding_obligation_corrupt", "immutable archive digest differs", 503)
        return value

    def _cut(self, connection, obligation_id):
        return self._archived(connection, "funding_obligations_cuts", obligation_id)

    def _receipt(self, connection, obligation_id):
        return self._archived(connection, "funding_obligations_receipts", obligation_id)

    def query(self, obligation_id):
        name(obligation_id, "obligation")
        with self.service.database.read_transaction() as connection:
            row = self._task(connection, obligation_id)
            tail = connection.execute("SELECT payload FROM funding_obligations_events WHERE obligation_id=? ORDER BY sequence DESC LIMIT 1", (obligation_id,)).fetchone()
            if tail is None or _parse(tail[0])["task"] != self._view(row):
                raise FundingError("funding_obligation_corrupt", "status differs from durable event tail", 503)
            cut = self._cut(connection, obligation_id)
            receipt = self._receipt(connection, obligation_id)
            if ((cut is None) != (row["cut_sha"] is None) or cut is not None and _digest(cut) != row["cut_sha"]
                    or (receipt is None) != (row["receipt_sha"] is None)
                    or receipt is not None and _digest(receipt) != row["receipt_sha"]):
                raise FundingError("funding_obligation_corrupt", "status archive reference differs", 503)
            return {**self._view(row), "cut": cut, "receipt": receipt}

    def command(self, command_id):
        name(command_id, "command")
        with self.service.database.read_transaction() as connection:
            row = connection.execute("SELECT * FROM funding_obligations_commands WHERE command_id=?", (command_id,)).fetchone()
            return None if row is None else self._previous(connection, command_id, row["kind"], _parse(row["request"]))

    def pending(self, *, after_id=None, limit=100):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise FundingError("funding_input", "pending limit must be1..100", 400)
        if after_id is not None:
            name(after_id, "obligation cursor")
        with self.service.database.read_transaction() as connection:
            rows = connection.execute("SELECT * FROM funding_obligations_tasks WHERE state!='APPLIED' AND obligation_id>? ORDER BY obligation_id LIMIT ?",
                                      ("" if after_id is None else after_id, limit)).fetchall()
            result = []
            for row in rows:
                tail = connection.execute("SELECT payload FROM funding_obligations_events WHERE obligation_id=? ORDER BY sequence DESC LIMIT 1", (row["obligation_id"],)).fetchone()
                if tail is None or _parse(tail[0])["task"] != self._view(row):
                    raise FundingError("funding_obligation_corrupt", "pending task differs from durable tail", 503)
                result.append(self._view(row))
            return result

    def execute_once(self, prefix, obligation_id, owner, *, market_snapshot_id=None, capital_deposit_reference=None, resolved_rate=None):
        name(prefix, "attempt prefix")
        if len(prefix) > 112:
            raise FundingError("funding_input", "attempt prefix exceeds112 characters", 400)
        claimed = self.claim(prefix + "/claim", obligation_id, owner)
        if not claimed["claimed"]:
            return claimed
        if self.query(obligation_id)["cut_sha"] is None:
            captured = self.capture(prefix + "/capture", obligation_id, claimed["token"], market_snapshot_id=market_snapshot_id, resolved_rate=resolved_rate)
            if self.query(obligation_id)["cut_sha"] is None:
                return captured
        return self.apply(prefix + "/apply", obligation_id, claimed["token"], capital_deposit_reference=capital_deposit_reference)

    def verify(self, *, connection=None):
        with self.service.database._using(connection) as current:
            config, config_sha = self._configuration(current)
            self.service.ledger.verify(connection=current)
            clock = current.execute("SELECT last_seen FROM funding_obligations_clock WHERE singleton=1").fetchone()
            if clock is None or _stamp(datetime.fromisoformat(clock[0])) != clock[0]:
                raise FundingError("funding_obligation_corrupt", "persistent clock watermark differs", 503)
            tasks = {row["obligation_id"]: row for row in current.execute("SELECT * FROM funding_obligations_tasks")}
            commands = {row["command_id"]: row for row in current.execute("SELECT * FROM funding_obligations_commands")}
            tails, previous, domain_states = {}, "0" * 64, {}
            for sequence, event in enumerate(current.execute("SELECT * FROM funding_obligations_events ORDER BY sequence"), 1):
                payload = _parse(event["payload"])
                command = commands.get(event["command_id"])
                if (event["sequence"] != sequence or event["previous_hash"] != previous or command is None
                        or event["event_hash"] != _digest([previous, event["obligation_id"], event["command_id"], payload])
                        or command["obligation_id"] != event["obligation_id"]
                        or payload["task"]["obligation_id"] != event["obligation_id"]
                        or _parse(command["result"])["obligation_id"] != event["obligation_id"]
                        or payload["command_result_sha"] != command["result_sha"]
                        or _digest(_parse(command["result"])) != command["result_sha"]):
                    raise FundingError("funding_obligation_corrupt", "command/event chain differs", 503)
                previous, tails[event["obligation_id"]] = event["event_hash"], payload["task"]
                domain_states[event["command_id"]] = {"obligation_id": event["obligation_id"],
                    "command_id": event["command_id"], "state": payload["task"]["state"],
                    "cut_sha": payload["task"]["cut_sha"], "receipt_sha": payload["task"]["receipt_sha"]}
            if len(commands) != current.execute("SELECT COUNT(*) FROM funding_obligations_events").fetchone()[0]:
                raise FundingError("funding_obligation_corrupt", "command/event cardinality differs", 503)
            for identifier, row in tasks.items():
                if tails.get(identifier) != self._view(row) or row["config_sha"] != config_sha:
                    raise FundingError("funding_obligation_corrupt", "task differs from durable transition tail", 503)
                cut = self._cut(current, identifier)
                if (cut is None) != (row["cut_sha"] is None) or cut is not None and _digest(cut) != row["cut_sha"]:
                    raise FundingError("funding_obligation_corrupt", "cut reference differs", 503)
                if cut is not None:
                    cut_row = current.execute("SELECT command_id FROM funding_obligations_cuts WHERE obligation_id=?", (identifier,)).fetchone()
                    if cut_row[0] not in commands or commands[cut_row[0]]["kind"] != "capture":
                        raise FundingError("funding_obligation_corrupt", "cut has no committed capture command", 503)
                    if _parse(commands[cut_row[0]]["request"])["resolved_rate"] != cut["resolved_rate"]:
                        raise FundingError("funding_obligation_corrupt", "approved cut rate has no matching command", 503)
                    self._verify_cut(row, cut, config_sha)
                    if cut["event_watermark"] > current.execute("SELECT COALESCE(MAX(sequence),0) FROM uta_events").fetchone()[0]:
                        raise FundingError("funding_obligation_corrupt", "cut watermark exceeds authoritative event stream", 503)
                schedule = commands.get(row["schedule_command_id"])
                if schedule is None or schedule["kind"] != "schedule" or _parse(schedule["request"]) != {
                        "obligation_id": identifier, "symbol": row["symbol"], "period_end": row["period_end"], "rate": row["rate"]}:
                    raise FundingError("funding_obligation_corrupt", "schedule identity differs", 503)
            reserve, expected_journals, applied = 0, set(), 0
            cash_events, capital_events = [], []
            for stored in current.execute("SELECT * FROM funding_obligations_receipts ORDER BY rowid"):
                applied += 1
                row = tasks[stored["obligation_id"]]
                receipt, cut = self._receipt(current, row["obligation_id"]), self._cut(current, row["obligation_id"])
                applied_command = commands.get(stored["command_id"])
                if (row["state"] != "APPLIED" or row["receipt_sha"] != stored["digest"] or receipt["cut_sha"] != row["cut_sha"]
                        or receipt["obligation_id"] != row["obligation_id"] or receipt["symbol"] != row["symbol"]
                        or receipt["period_end"] != row["period_end"]
                        or receipt["command_id"] != stored["command_id"] or receipt["config_sha"] != config_sha
                        or receipt["artifact_sha"] != _digest(self.artifact)
                        or applied_command is None or applied_command["kind"] != "apply"
                        or _parse(applied_command["request"])["capital_deposit_reference"] != stored["capital_deposit_reference"]
                        or _parse(applied_command["result"]).get("receipt") != receipt
                        or Fraction(Decimal(receipt["reserve_before"])) * 10 ** config["usd_scale"] != reserve):
                    raise FundingError("funding_reconciliation", "applied receipt identity/reserve differs", 503)
                applied_token = _parse(applied_command["request"])["token"]
                if (receipt["claim_generation"] != row["generation"] or applied_token["generation"] != receipt["claim_generation"]
                        or applied_token["owner"] != receipt["claim_owner"]
                        or sha256(applied_token["nonce"].encode()).hexdigest() != receipt["claim_nonce_digest"]
                        or applied_token["until_at"] != receipt["claim_until_at"]
                        or not datetime.fromisoformat(cut["observed_at"]) <= datetime.fromisoformat(receipt["applied_at"]) < datetime.fromisoformat(receipt["claim_until_at"])):
                    raise FundingError("funding_reconciliation", "applied claim/cut time evidence differs", 503)
                journals = {}
                capital = receipt["capital_transfer"]
                if capital is not None:
                    units = int(capital["units"])
                    if (units <= 0 or str(units) != capital["units"] or capital["deposit_reference"] != stored["capital_deposit_reference"]
                            or capital["source_account_id"] != config["capital_account_id"]
                            or capital["event_id"] != _key("capital", row["obligation_id"])
                            or Decimal(capital["amount"]) != units_decimal(units, config["usd_scale"])):
                        raise FundingError("funding_reconciliation", "capital ownership differs", 503)
                    FundingLocal._verify_capital_deposit(self, current, config, capital["deposit_reference"], units, config["usd_scale"])
                    journals[_key("capital", row["obligation_id"])] = {self.service._customer(config["capital_account_id"]): -units, _RESERVE: units}
                    reserve += units
                    capital_events.append({"account_id": config["capital_account_id"], "payload": {
                        "obligation_id": row["obligation_id"], "journal_event_id": capital["event_id"],
                        "deposit_reference": capital["deposit_reference"], "amount": capital["amount"]}})
                elif stored["capital_deposit_reference"] is not None:
                    raise FundingError("funding_reconciliation", "unused capital proof consumed", 503)
                total = 0
                risk_market = MarketSnapshot.from_json(receipt["risk_market_payload"])
                risk_market.validate(now=datetime.fromisoformat(receipt["applied_at"]), max_age=self.service.max_price_age)
                if receipt["risk_market_snapshot_id"] != "sha256:" + sha256(receipt["risk_market_payload"].encode()).hexdigest():
                    raise FundingError("funding_reconciliation", "current risk market identity differs", 503)
                for leg in cut["plan"]["legs"]:
                    units = int(leg["cash_units"]); total += units
                    before = receipt["account_inputs_before"][leg["account_id"]]
                    after = receipt["account_inputs_after"][leg["account_id"]]
                    if (before["positions"] != after["positions"] or before["liabilities"] != after["liabilities"]
                            or {asset: value for asset, value in before["balances"].items() if asset != "USD"}
                            != {asset: value for asset, value in after["balances"].items() if asset != "USD"}
                            or Fraction(Decimal(after["balances"]["USD"])) - Fraction(Decimal(before["balances"]["USD"]))
                            != Fraction(units, 10 ** config["usd_scale"])):
                        raise FundingError("funding_reconciliation", "current-state cash/position/principal movement differs", 503)
                    if units:
                        journals[_key("leg", row["obligation_id"], leg["account_id"])] = {self.service._customer(leg["account_id"]): units, _CLEARING: -units}
                        action = receipt["risk_actions"][leg["account_id"]]
                        if (after["liquidation_state"] is None or action["state"] != after["liquidation_state"]["state"]
                                or "persisted_state" in action or after["version"] <= before["version"]
                                or receipt["risk_after"][leg["account_id"]]["account_version"] != after["version"]):
                            raise FundingError("funding_reconciliation", "confirmed risk action differs", 503)
                        cash_events.append({"account_id": leg["account_id"], "payload": {
                            "obligation_id": row["obligation_id"], "command_id": stored["command_id"], "cut_sha": row["cut_sha"]}})
                if total:
                    journals[_key("variance", row["obligation_id"])] = {_RESERVE: -total, _CLEARING: total}
                reserve -= total
                if reserve < 0 or Fraction(Decimal(receipt["reserve_after"])) * 10 ** config["usd_scale"] != reserve:
                    raise FundingError("funding_reconciliation", "reserve ownership replay differs", 503)
                if len(receipt["journals"]) != len(journals) or {item["event_id"] for item in receipt["journals"]} != set(journals):
                    raise FundingError("funding_reconciliation", "receipt journals differ", 503)
                for journal in receipt["journals"]:
                    self._verify_journal(current, journal["event_id"], journal["sequence"], journals[journal["event_id"]])
                if capital is not None and {"event_id": capital["event_id"], "sequence": capital["sequence"]} not in receipt["journals"]:
                    raise FundingError("funding_reconciliation", "capital sequence differs from receipt journals", 503)
                expected_journals.update(journals)
            if applied != sum(row["state"] == "APPLIED" for row in tasks.values()):
                raise FundingError("funding_reconciliation", "task/receipt terminal cardinality differs", 503)
            actual_states = [_parse(row[0]) for row in current.execute("SELECT payload FROM uta_events WHERE event_type='FUNDING_OBLIGATION_STATE' ORDER BY sequence")]
            if (len(actual_states) != len(domain_states) or sorted(map(canonical, actual_states)) != sorted(map(canonical, domain_states.values()))):
                raise FundingError("funding_obligation_corrupt", "domain command/state events differ", 503)
            for kind, expected_events in (("FUNDING_OBLIGATION_CASH_APPLIED", cash_events), ("FUNDING_OBLIGATION_CAPITAL_TRANSFER", capital_events)):
                actual_events = [{"account_id": row[0], "payload": _parse(row[1])} for row in
                                 current.execute("SELECT account_id,payload FROM uta_events WHERE event_type=?", (kind,))]
                if sorted(map(canonical, actual_events)) != sorted(map(canonical, expected_events)):
                    raise FundingError("funding_reconciliation", "cash/treasury event linkage differs", 503)
            installed = {row[0] for row in current.execute("SELECT event_id FROM ledger_events WHERE event_id LIKE ?", (_PREFIX + "%",))}
            if (installed != expected_journals or self.service.ledger.balance(_CLEARING, "USD", connection=current) != 0
                    or Fraction(self.service.ledger.balance(_RESERVE, "USD", connection=current)) * 10 ** config["usd_scale"] != reserve):
                raise FundingError("funding_reconciliation", "orphan/unowned funding money", 503)
            return {"obligations": len(tasks), "applied": applied, "outstanding": len(tasks) - applied,
                    "commands": len(commands), "financial_journals": len(expected_journals), "reconciled": True,
                    "risk_eligibility_replayed": False, "HA_or_production_approved": False}

    def _verify_cut(self, row, cut, config_sha):
        market = MarketSnapshot.from_json(cut["market_payload"])
        positions = cut["positions"]
        quantities = [[item["account_id"], decimal_text(Decimal(item["quantity"]))] for item in positions]
        plan = cut["plan"]
        at = datetime.fromisoformat(cut["observed_at"])
        end = datetime.fromisoformat(row["period_end"])
        market.validate(now=at, max_age=self.service.max_price_age)
        number(Decimal(plan["rate"]), "archived approved rate", maximum=self.policy.max_abs_rate)
        if (cut["config_sha"] != config_sha or cut["artifact_sha"] != _digest(self.artifact)
                or cut["obligation_id"] != row["obligation_id"] or cut["symbol"] != row["symbol"] or cut["period_end"] != row["period_end"]
                or cut["policy"] != self.policy.payload() or not timedelta() <= at - end <= timedelta(milliseconds=self.policy.trigger_lateness_ms)
                or cut["market_snapshot_id"] != "sha256:" + sha256(cut["market_payload"].encode()).hexdigest()
                or plan["position_digest"] != _digest(quantities) or plan["usd_scale"] != self.service.scales["USD"]
                or plan["symbol"] != row["symbol"] or plan["period_end"] != row["period_end"] or plan["settlement_asset"] != "USD"
                or plan["rate"] != (row["rate"] if row["rate"] is not None else cut["resolved_rate"])
                or Decimal(plan["mark"]) != market.instruments[row["symbol"]].mark_price
                or sum((Fraction(Decimal(item["quantity"])) for item in positions), Fraction())
                or len({item["account_id"] for item in positions}) != len(positions)
                or {leg["account_id"] for leg in plan["legs"]} != {item["account_id"] for item in positions}
                or len(plan["legs"]) != len(positions) or len(positions) > self.policy.max_accounts
                or type(cut["event_watermark"]) is not int or cut["event_watermark"] < 0):
            raise FundingError("funding_obligation_corrupt", "trusted cut identity/boundary/inventory differs", 503)
        total = 0
        for source, leg in zip(positions, plan["legs"]):
            exact = -Fraction(Decimal(source["quantity"])) * Fraction(Decimal(plan["mark"])) * Fraction(Decimal(plan["rate"]))
            scaled = exact * 10 ** plan["usd_scale"]
            units = abs(scaled.numerator) // scaled.denominator * (-1 if scaled < 0 else 1)
            if (source["account_id"] != leg["account_id"] or type(source["account_version"]) is not int or source["account_version"] < 0
                    or Decimal(leg["quantity"]) != Decimal(source["quantity"])
                    or Decimal(leg["cash"]) != units_decimal(units, plan["usd_scale"])
                    or leg["cash_units"] != str(units) or FundingLocal._ratio(leg["exact_cash"]) != exact
                    or FundingLocal._ratio(leg["waived_exact_minus_actual"]) != exact - Fraction(units, 10 ** plan["usd_scale"])):
                raise FundingError("funding_obligation_corrupt", "frozen cash arithmetic differs", 503)
            total += units
        if plan["clearing_units"] != str(-total):
            raise FundingError("funding_obligation_corrupt", "frozen clearing differs", 503)
