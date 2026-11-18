"""Fresh-authority, opt-in local funding prototype; no REST/worker integration.

Installation on a used or managed authority is deliberately unsupported. This
is not a migration, production scheduler, operator-authentication or HA layer.
"""
from datetime import datetime
from decimal import Decimal
from fractions import Fraction
from hashlib import sha256
import json

from .perpetual_funding import (FundingError, FundingPolicy, FundingPosition,
    canonical, decimal_text, name, number, period_time, plan_funding, units_decimal)
from .ledger import Posting
from .products import ProductKind
from .service import ExchangeService, _key as _service_key
from .storage import Database


_RESERVE = "system:funding-rounding-reserve"
_CLEARING = "system:perpetual-funding-clearing"
_PREFIX = "funding-local:"
_SCHEMA = (
    "CREATE TABLE funding_local_config(singleton INTEGER PRIMARY KEY CHECK(singleton=1),payload TEXT NOT NULL)",
    "CREATE TABLE funding_local_periods(symbol TEXT NOT NULL,period_end TEXT NOT NULL,command_id TEXT NOT NULL UNIQUE,capital_deposit_reference TEXT UNIQUE,request TEXT NOT NULL,receipt TEXT NOT NULL,receipt_sha256 TEXT NOT NULL,PRIMARY KEY(symbol,period_end))",
    "CREATE TRIGGER funding_local_config_no_update BEFORE UPDATE ON funding_local_config BEGIN SELECT RAISE(ABORT,'funding config is immutable'); END",
    "CREATE TRIGGER funding_local_config_no_delete BEFORE DELETE ON funding_local_config BEGIN SELECT RAISE(ABORT,'funding config is immutable'); END",
    "CREATE TRIGGER funding_local_config_no_replace BEFORE INSERT ON funding_local_config WHEN EXISTS(SELECT 1 FROM funding_local_config WHERE singleton=NEW.singleton) BEGIN SELECT RAISE(ABORT,'funding config cannot be replaced'); END",
    "CREATE TRIGGER funding_local_periods_no_update BEFORE UPDATE ON funding_local_periods BEGIN SELECT RAISE(ABORT,'funding receipt is immutable'); END",
    "CREATE TRIGGER funding_local_periods_no_delete BEFORE DELETE ON funding_local_periods BEGIN SELECT RAISE(ABORT,'funding receipt is immutable'); END",
    "CREATE TRIGGER funding_local_periods_no_replace BEFORE INSERT ON funding_local_periods WHEN EXISTS(SELECT 1 FROM funding_local_periods WHERE (symbol=NEW.symbol AND period_end=NEW.period_end) OR command_id=NEW.command_id OR capital_deposit_reference=NEW.capital_deposit_reference) BEGIN SELECT RAISE(ABORT,'funding period cannot be replaced'); END",
)


def _key(kind, *parts):
    return _PREFIX + kind + ":" + sha256(canonical(parts).encode()).hexdigest()


def _parse(raw):
    try:
        result = json.loads(raw)
        if canonical(result) != raw:
            raise ValueError("noncanonical data")
        return result
    except (TypeError, ValueError) as error:
        raise FundingError("funding_corrupt", "stored funding JSON is not canonical", 503) from error


def _artifact():
    """Include the existing core artifact and this optional component's code.

    Hashes describe trusted immutable local code; they are not signatures or a
    hostile-Python-process boundary. No stored code is imported or executed.
    """
    from .decision_audit import code_artifact
    from .credit_artifact import _loaded_modules
    # This is a fixed compiled extension for this component's own archive. It
    # does not mutate credit_artifact._MODULES, formats or live-state exclusions.
    # Defaults, closures, class/module constants and unknown-type rejection use
    # the existing strict contract, including its exact dataclass repr handling.
    functions, constants = _loaded_modules(("perpetual_funding", "funding_local"))
    return {"core": code_artifact(), "funding_loaded_functions": functions,
            "funding_loaded_constants": constants,
            "signed": False, "activation": "SYNTHETIC_LOCAL_ONLY"}


class FundingLocal:
    """Trusted in-process operator boundary for one complete local authority.

    No customer endpoint, arbitrary account/amount settlement, retry worker or
    activation switch is registered. Real authorization remains an open gate.
    """

    def __init__(self, service: ExchangeService, policy: FundingPolicy):
        self._native(service, policy)
        self.service, self.policy = service, policy
        self.artifact = _artifact()
        with service._transaction() as connection:
            self.verify(connection=connection)

    @staticmethod
    def _native(service, policy):
        if (type(service) is not ExchangeService or type(service.database) is not Database
                or service.database.writer_token is not None or type(policy) is not FundingPolicy):
            raise FundingError("funding_authority_unsupported", "native unbound local service and policy required")
        if service.product_catalog is None or service.portfolio_rules is None:
            raise FundingError("funding_mode_unsupported", "configured Cross USD mode is required")

    @staticmethod
    def _trading_policy(service):
        return {"catalog": json.loads(service.product_catalog.to_json()),
                "portfolio_rules": json.loads(service.portfolio_rules.to_json()),
                "fee_rate": decimal_text(service.fee_rate), "asset_scales": dict(service.scales),
                "max_price_age_us": service.max_price_age.days * 86400000000
                    + service.max_price_age.seconds * 1000000 + service.max_price_age.microseconds}

    @classmethod
    def install_synthetic_fresh(cls, service: ExchangeService, policy: FundingPolicy, *,
                                capital_account_id: str):
        cls._native(service, policy)
        name(capital_account_id, "declared operator treasury")
        artifact = _artifact()
        scale = service.scales["USD"]
        with service._transaction() as connection:
            cls._unmanaged(connection)
            if connection.execute("SELECT 1 FROM sqlite_master WHERE name GLOB 'funding_local_*' LIMIT 1").fetchone():
                raise FundingError("funding_install_conflict", "funding storage already exists; open without repair")
            for table in ("uta_accounts", "uta_positions", "uta_orders", "uta_fills", "uta_deposits",
                          "uta_liabilities", "ledger_events", "uta_events"):
                if connection.execute("SELECT 1 FROM " + table + " LIMIT 1").fetchone():
                    raise FundingError("funding_migration_required", "installation requires a never-used authority")
            for statement in _SCHEMA:
                connection.execute(statement)
            config = {"format": 1, "policy": policy.payload(), "artifact": artifact,
                      "usd_scale": scale, "capital_account_id": capital_account_id,
                      "trading_policy": cls._trading_policy(service)}
            payload = canonical(config)
            if len(payload.encode()) > 1024 * 1024:
                raise FundingError("funding_archive_limit", "funding configuration exceeds the prototype archive limit")
            connection.execute("INSERT INTO funding_local_config VALUES(1,?)", (payload,))
        return cls(service, policy)

    @staticmethod
    def _unmanaged(connection):
        if connection.execute("SELECT 1 FROM sqlite_master WHERE name GLOB 'writer_fence_*' LIMIT 1").fetchone():
            raise FundingError("funding_managed_unsupported", "managed/code-bound funding upgrade is not implemented")

    def _configuration(self, connection):
        from .existing_services import _verify_fixed_schema
        self._unmanaged(connection)
        _verify_fixed_schema(connection, _SCHEMA)
        rows = connection.execute("SELECT singleton,payload FROM funding_local_config").fetchall()
        if len(rows) != 1 or rows[0]["singleton"] != 1:
            raise FundingError("funding_configuration", "missing funding capability", 503)
        config = _parse(rows[0]["payload"])
        if (set(config) != {"format", "policy", "artifact", "usd_scale", "capital_account_id", "trading_policy"}
                or type(config["format"]) is not int or config["format"] != 1
                or canonical(config["policy"]) != canonical(self.policy.payload())
                or canonical(config["artifact"]) != canonical(self.artifact)
                or canonical(config["artifact"]) != canonical(_artifact())
                or type(config["usd_scale"]) is not int or config["usd_scale"] != self.service.scales["USD"]
                or canonical(config["trading_policy"]) != canonical(self._trading_policy(self.service))):
            raise FundingError("funding_configuration", "funding policy/code changed; offline migration required", 503)
        return config

    def _receipt(self, row):
        if sha256(row["receipt"].encode()).hexdigest() != row["receipt_sha256"]:
            raise FundingError("funding_corrupt", "funding receipt digest differs", 503)
        receipt = _parse(row["receipt"])
        if (type(receipt.get("format")) is not int or receipt["format"] != 1
                or receipt.get("command_id") != row["command_id"]
                or receipt.get("symbol") != row["symbol"]
                or receipt.get("period_end") != row["period_end"]
                or receipt.get("capital_deposit_reference") != row["capital_deposit_reference"]):
            raise FundingError("funding_corrupt", "receipt identity differs", 503)
        return receipt

    def receipt(self, command_id: str):
        name(command_id, "command")
        with self.service.database.read_transaction() as connection:
            row = connection.execute("SELECT * FROM funding_local_periods WHERE command_id=?", (command_id,)).fetchone()
            return None if row is None else self._receipt(row)

    def settle(self, command_id: str, symbol: str, period_end: datetime, *,
               rate: Decimal, market_snapshot_id: str, capital_deposit_reference: str | None = None):
        name(command_id, "command")
        name(symbol, "symbol")
        end, seconds = period_time(period_end)
        number(rate, "rate", maximum=self.policy.max_abs_rate)
        if capital_deposit_reference is not None:
            name(capital_deposit_reference, "capital deposit reference")
        if type(market_snapshot_id) is not str or not market_snapshot_id.startswith("sha256:") or len(market_snapshot_id) != 71:
            raise FundingError("funding_market", "full expected market snapshot SHA required", 400)
        request = canonical({"command_id": command_id, "symbol": symbol, "period_end": end.isoformat(),
                             "rate": decimal_text(rate), "market_snapshot_id": market_snapshot_id,
                             "capital_deposit_reference": capital_deposit_reference,
                             "policy": self.policy.payload()})
        with self.service._transaction() as connection:
            config = self._configuration(connection)
            previous = connection.execute("SELECT * FROM funding_local_periods WHERE command_id=?", (command_id,)).fetchone()
            if previous is not None:
                if previous["request"] != request:
                    raise FundingError("funding_idempotency_conflict", "command ID reused with different content")
                return self._receipt(previous)
            if connection.execute("SELECT 1 FROM funding_local_periods WHERE symbol=? AND period_end=?",
                                  (symbol, end.isoformat())).fetchone():
                raise FundingError("funding_period_already_settled", "a product/period can settle only once")
            self.verify(connection=connection)
            now = self.service._now()
            delta = now - end
            late_us = (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds
            if not 0 <= late_us <= self.policy.trigger_lateness_ms * 1000:
                error = FundingError("funding_boundary_unavailable", "late/future period has no trusted boundary snapshot")
                error.unsettled_obligation = {"command_id": command_id, "symbol": symbol,
                    "period_end": end.isoformat(), "successful_receipt_emitted": False,
                    "state": "UNSETTLED_REQUIRES_OPERATOR_RECORD",
                    "historical_current_position_backfill_permitted": False}
                raise error
            market = self.service._market(connection)
            actual_id = "sha256:" + sha256(market.to_json().encode()).hexdigest()
            if actual_id != market_snapshot_id:
                raise FundingError("funding_market_conflict", "funding must reference the trusted current snapshot")
            try:
                product = self.service.product_catalog.require_risk_supported(symbol)
                spec = market.instruments[symbol]
            except (KeyError, ValueError) as error:
                raise FundingError("funding_product_unsupported", "missing eligible product/mark") from error
            if (product.kind is not ProductKind.LINEAR_PERPETUAL or product.multiplier != 1
                    or product.settlement_asset != "USD" or product.quote_asset != "USD"
                    or product.funding_interval_seconds is None):
                raise FundingError("funding_product_unsupported", "only multiplier1 USD linear perpetuals are implemented")
            rows = connection.execute("SELECT p.account_id,p.quantity,p.cost_basis,a.version FROM uta_positions p JOIN uta_accounts a ON a.account_id=p.account_id WHERE p.symbol=? ORDER BY p.account_id LIMIT ?",
                                      (symbol, self.policy.max_accounts + 1)).fetchall()
            positions = tuple(FundingPosition(row["account_id"], Decimal(row["quantity"])) for row in rows)
            plan = plan_funding(self.policy, symbol, end, interval_seconds=product.funding_interval_seconds,
                                mark=spec.mark_price, rate=rate, usd_scale=self.service.scales["USD"], positions=positions)
            frozen = [{"account_id": row["account_id"], "account_version": row["version"],
                       "quantity": row["quantity"], "cost_basis": row["cost_basis"]} for row in rows]
            watermark = connection.execute("SELECT COALESCE(MAX(sequence),0) FROM uta_events").fetchone()[0]
            account_before = {row["account_id"]: self.service._audit_state(connection, row["account_id"]) for row in rows}
            before = {row["account_id"]: self.service._risk(connection, row["account_id"], market) for row in rows}
            reserve_before = self.service.ledger.balance(_RESERVE, "USD", connection=connection)
            if config["capital_account_id"] in {position.account_id for position in positions}:
                raise FundingError("funding_capital_account_exposed", "declared treasury must not be a funding participant")
            journals, affected = [], []
            deficit = max(Fraction(0), -Fraction(reserve_before) * 10 ** plan.usd_scale - plan.clearing_units)
            if deficit.denominator != 1:
                raise FundingError("funding_reconciliation", "reserve is not a whole minor-unit balance", 503)
            topup = self._capital_transfer(connection, config, symbol, end, capital_deposit_reference,
                                            deficit.numerator, plan.usd_scale)
            if topup is not None:
                journals.append({"event_id": topup["event_id"], "sequence": topup["sequence"]})
            for leg in plan.legs:
                if not leg.cash_units:
                    continue
                amount = units_decimal(leg.cash_units, plan.usd_scale)
                event_id = _key("leg", symbol, end.isoformat(), leg.account_id)
                event = self.service.ledger.post(event_id, (
                    Posting(self.service._customer(leg.account_id), "USD", amount),
                    Posting(_CLEARING, "USD", amount.copy_negate())), connection=connection)
                journals.append({"event_id": event_id, "sequence": event.sequence})
                self.service._bump(connection, leg.account_id)
                affected.append(leg.account_id)
            if plan.clearing_units:
                amount = units_decimal(plan.clearing_units, plan.usd_scale)
                event_id = _key("variance", symbol, end.isoformat())
                event = self.service.ledger.post(event_id, (
                    Posting(_RESERVE, "USD", amount), Posting(_CLEARING, "USD", amount.copy_negate())), connection=connection)
                journals.append({"event_id": event_id, "sequence": event.sequence})
            actions = {}
            for account_id in affected:
                action = self.service.supervise_account(account_id, connection=connection)
                state = connection.execute("SELECT state FROM uta_liquidation_accounts WHERE account_id=?", (account_id,)).fetchone()
                if state is None or state["state"] != action["state"] or "persisted_state" in action:
                    error = FundingError("funding_risk_unavailable", "risk action did not persist; rollback funding period", 503)
                    error.unsettled_obligation = {"command_id": command_id, "symbol": symbol,
                        "period_end": end.isoformat(), "successful_receipt_emitted": False,
                        "state": "UNSETTLED_QUERY_ORIGINAL_ID_AND_RECORD",
                        "historical_current_position_backfill_permitted": False}
                    raise error
                actions[account_id] = action
            after = {row["account_id"]: self.service._risk(connection, row["account_id"], market) for row in rows}
            account_after = {row["account_id"]: self.service._audit_state(connection, row["account_id"]) for row in rows}
            if self.service.ledger.balance(_CLEARING, "USD", connection=connection) != 0:
                raise FundingError("funding_reconciliation", "funding clearing account did not settle to zero", 503)
            receipt = {"format": 1, "command_id": command_id, "symbol": symbol, "period_end": end.isoformat(),
                       "freeze_observed_at": now.isoformat(), "freeze_event_watermark": watermark,
                       "freeze_positions": frozen, "market_snapshot_id": actual_id,
                       "capital_deposit_reference": capital_deposit_reference, "capital_transfer": topup,
                       "market_payload": market.to_json(), "policy": self.policy.payload(),
                       "artifact_digest": sha256(canonical(self.artifact).encode()).hexdigest(),
                       "plan": plan.payload(), "journals": journals, "risk_before": before,
                       "risk_after": after, "risk_actions": actions,
                       "account_inputs_before": account_before, "account_inputs_after": account_after,
                       "rounding_reserve_before": decimal_text(reserve_before),
                       "rounding_reserve_after": decimal_text(self.service.ledger.balance(_RESERVE, "USD", connection=connection)),
                       "real_funds_approved": False, "managed_or_HA_approved": False}
            raw = canonical(receipt)
            if len(raw.encode()) > 4 * 1024 * 1024:
                raise FundingError("funding_archive_limit", "period receipt exceeds the prototype archive limit")
            connection.execute("INSERT INTO funding_local_periods VALUES(?,?,?,?,?,?,?)",
                               (symbol, end.isoformat(), command_id, capital_deposit_reference,
                                request, raw, sha256(raw.encode()).hexdigest()))
            self.service._event(connection, "FUNDING_PERIOD_SETTLED", None,
                                {"symbol": symbol, "period_end": end.isoformat(), "command_id": command_id,
                                 "receipt_sha256": sha256(raw.encode()).hexdigest(), "journal_count": len(journals)})
            # Returning through the context manager requires actual COMMIT. A
            # COMMIT exception is not a receipt and must be queried by this ID.
            return receipt

    def verify(self, *, connection=None):
        with self.service.database._using(connection) as current:
            config = self._configuration(current)
            self.service.ledger.verify(connection=current)
            expected = set()
            reserve_units = 0
            # Immutable row insertion order is the local serialized commit
            # order; sorting by symbol/time would mis-replay a shared reserve.
            periods = current.execute("SELECT * FROM funding_local_periods ORDER BY rowid")
            period_count = 0
            for row in periods:
                period_count += 1
                receipt = self._receipt(row)
                plan = receipt["plan"]
                request = _parse(row["request"])
                if (request.get("command_id") != row["command_id"] or request.get("symbol") != row["symbol"]
                        or request.get("period_end") != row["period_end"] or request.get("rate") != plan["rate"]
                        or request.get("market_snapshot_id") != receipt["market_snapshot_id"]
                        or request.get("capital_deposit_reference") != row["capital_deposit_reference"]
                        or canonical(request.get("policy")) != canonical(self.policy.payload())):
                    raise FundingError("funding_reconciliation", "funding request and receipt differ", 503)
                self._verify_plan(receipt)
                if Fraction(Decimal(receipt["rounding_reserve_before"])) * 10 ** self.service.scales["USD"] != reserve_units:
                    raise FundingError("funding_reconciliation", "period reserve starting ownership differs", 503)
                total = 0
                period_expected = {}
                topup = receipt["capital_transfer"]
                if topup is not None:
                    units = int(topup["units"])
                    if (str(units) != topup["units"] or units <= 0
                            or topup["source_account_id"] != config["capital_account_id"]
                            or topup["deposit_reference"] != row["capital_deposit_reference"]
                            or topup["event_id"] != _key("capital", row["symbol"], row["period_end"])):
                        raise FundingError("funding_reconciliation", "invalid capital ownership reference", 503)
                    self._verify_capital_deposit(current, config, topup["deposit_reference"], units,
                                                  self.service.scales["USD"])
                    period_expected[topup["event_id"]] = {
                        self.service._customer(config["capital_account_id"]): -units, _RESERVE: units}
                    self._verify_journal(current, topup["event_id"], topup["sequence"],
                                         period_expected[topup["event_id"]])
                    reserve_units += units
                elif row["capital_deposit_reference"] is not None:
                    raise FundingError("funding_reconciliation", "unused capital proof was consumed", 503)
                for leg in plan["legs"]:
                    units = int(leg["cash_units"])
                    if str(units) != leg["cash_units"]:
                        raise FundingError("funding_corrupt", "noncanonical funding units", 503)
                    total += units
                    if units:
                        event_id = _key("leg", row["symbol"], row["period_end"], leg["account_id"])
                        period_expected[event_id] = {self.service._customer(leg["account_id"]): units,
                                                     _CLEARING: -units}
                if -total != int(plan["clearing_units"]):
                    raise FundingError("funding_reconciliation", "funding cash/clearing totals disagree", 503)
                if total:
                    event_id = _key("variance", row["symbol"], row["period_end"])
                    period_expected[event_id] = {_RESERVE: -total, _CLEARING: total}
                reserve_units -= total
                if (reserve_units < 0 or Fraction(Decimal(receipt["rounding_reserve_after"]))
                        * 10 ** self.service.scales["USD"] != reserve_units):
                    raise FundingError("funding_reconciliation", "period reserve ending ownership differs", 503)
                if (len(receipt["journals"]) != len(period_expected)
                        or {item["event_id"] for item in receipt["journals"]} != set(period_expected)):
                    raise FundingError("funding_reconciliation", "receipt journal references disagree", 503)
                for item in receipt["journals"]:
                    self._verify_journal(current, item["event_id"], item["sequence"],
                                         period_expected[item["event_id"]])
                expected.update(period_expected)
            installed = {row[0] for row in current.execute("SELECT event_id FROM ledger_events WHERE event_id LIKE ?", (_PREFIX + "%",))}
            if installed != expected or self.service.ledger.balance(_CLEARING, "USD", connection=current) != 0:
                raise FundingError("funding_reconciliation", "orphan funding journal or unsettled clearing balance", 503)
            if (Fraction(self.service.ledger.balance(_RESERVE, "USD", connection=current))
                    * 10 ** self.service.scales["USD"] != reserve_units):
                raise FundingError("funding_reconciliation", "rounding reserve differs from its declared ownership", 503)
            return {"periods": period_count, "journal_references": len(expected),
                    "ledger_verified": True, "funding_reconciled": True,
                    "risk_eligibility_replayed": False,
                    "production_approved": False}

    @staticmethod
    def _ratio(value):
        if (type(value) is not dict or set(value) != {"numerator", "denominator"}
                or any(type(item) is not str or len(item) > 128 for item in value.values())):
            raise FundingError("funding_corrupt", "invalid exact funding ratio", 503)
        try:
            ratio = Fraction(int(value["numerator"]), int(value["denominator"]))
        except (ValueError, ZeroDivisionError) as error:
            raise FundingError("funding_corrupt", "invalid exact funding ratio", 503) from error
        if str(ratio.numerator) != value["numerator"] or str(ratio.denominator) != value["denominator"]:
            raise FundingError("funding_corrupt", "noncanonical exact funding ratio", 503)
        return ratio

    def _verify_plan(self, receipt):
        """Revalue recorded funding inputs without invoking the plan calculator.

        This is internal arithmetic reconciliation. It is not the independent
        verification group's reference model or an admission-eligibility replay.
        """
        from .market import MarketSnapshot
        market = MarketSnapshot.from_json(receipt["market_payload"])
        plan = receipt["plan"]
        if (receipt["market_snapshot_id"] != "sha256:" + sha256(receipt["market_payload"].encode()).hexdigest()
                or plan["symbol"] != receipt["symbol"] or plan["period_end"] != receipt["period_end"]
                or type(plan["usd_scale"]) is not int or plan["usd_scale"] != self.service.scales["USD"]
                or plan["settlement_asset"] != "USD"
                or Decimal(plan["mark"]) != market.instruments[receipt["symbol"]].mark_price):
            raise FundingError("funding_reconciliation", "recorded funding market/policy identity differs", 503)
        number(Decimal(plan["rate"]), "stored rate", maximum=self.policy.max_abs_rate)
        frozen = receipt["freeze_positions"]
        positions = {item["account_id"]: item for item in frozen}
        if len(positions) != len(frozen) or len(plan["legs"]) != len(frozen):
            raise FundingError("funding_reconciliation", "recorded funding position inventory differs", 503)
        quantities = [[account, decimal_text(Decimal(item["quantity"]))] for account, item in sorted(positions.items())]
        if (sum((Fraction(Decimal(quantity)) for _, quantity in quantities), Fraction())
                or sha256(canonical(quantities).encode()).hexdigest() != plan["position_digest"]
                or {leg["account_id"] for leg in plan["legs"]} != set(positions)):
            raise FundingError("funding_reconciliation", "recorded funding positions are incomplete", 503)
        for leg in plan["legs"]:
            source = positions[leg["account_id"]]
            account = receipt["account_inputs_before"][leg["account_id"]]
            native_position = account["positions"][receipt["symbol"]]
            if (type(source["account_version"]) is not int or source["account_version"] != account["version"]
                    or Fraction(Decimal(source["quantity"])) != Fraction(Decimal(native_position["quantity"]))
                    or Fraction(Decimal(source["cost_basis"])) != Fraction(Decimal(native_position["cost_basis"]))
                    or Decimal(leg["quantity"]) != Decimal(source["quantity"])):
                raise FundingError("funding_reconciliation", "funding leg differs from the frozen account", 503)
            exact = -Fraction(Decimal(leg["quantity"])) * Fraction(Decimal(plan["mark"])) * Fraction(Decimal(plan["rate"]))
            scaled = exact * 10 ** plan["usd_scale"]
            units = abs(scaled.numerator) // scaled.denominator * (-1 if scaled < 0 else 1)
            if (leg["cash_units"] != str(units) or self._ratio(leg["exact_cash"]) != exact
                    or Decimal(leg["cash"]) != units_decimal(units, plan["usd_scale"])
                    or self._ratio(leg["waived_exact_minus_actual"]) != exact - Fraction(units, 10 ** plan["usd_scale"])):
                raise FundingError("funding_reconciliation", "funding quote/cash/rounding arithmetic differs", 503)

    def _verify_capital_deposit(self, connection, config, reference, required_units, scale):
        treasury = config["capital_account_id"]
        row = connection.execute("SELECT asset,amount FROM uta_deposits WHERE account_id=? AND event_id=?",
                                 (treasury, reference)).fetchone()
        if row is None or row["asset"] != "USD":
            raise FundingError("funding_capital_unconfirmed", "declared treasury has no confirmed USD deposit proof")
        units = Fraction(Decimal(row["amount"])) * 10 ** scale
        if units.denominator != 1 or units < required_units:
            raise FundingError("funding_capital_unconfirmed", "deposit proof is smaller than the actual capital transfer")
        self._verify_journal(connection, _service_key("deposit", treasury, reference), None,
                             {self.service._customer(treasury): units.numerator,
                              "system:custody": -units.numerator})

    def _capital_transfer(self, connection, config, symbol, end, reference, units, scale):
        if not units:
            if reference is not None:
                raise FundingError("funding_capital_unnecessary", "no capital proof is consumed without a transfer")
            return None
        if reference is None:
            raise FundingError("funding_rounding_capital_insufficient", "rounding variance needs confirmed treasury capital")
        if connection.execute("SELECT 1 FROM funding_local_periods WHERE capital_deposit_reference=?", (reference,)).fetchone():
            raise FundingError("funding_capital_reference_reused", "capital deposit proof already belongs to another period")
        self._verify_capital_deposit(connection, config, reference, units, scale)
        treasury = config["capital_account_id"]
        self.service._require_unfrozen(connection, treasury)
        for table in ("uta_positions", "uta_liabilities"):
            if connection.execute("SELECT 1 FROM " + table + " WHERE account_id=? LIMIT 1", (treasury,)).fetchone():
                raise FundingError("funding_capital_account_exposed", "treasury must have no positions or borrowing history")
        if self.service._live_orders(connection, treasury) or self.service._locked_assets(connection, treasury):
            raise FundingError("funding_capital_account_exposed", "treasury cash is reserved by trading")
        amount = units_decimal(units, scale)
        if self.service._available_asset(connection, treasury, "USD") < amount:
            raise FundingError("funding_rounding_capital_insufficient", "treasury has insufficient settled available cash")
        previous_version = self.service._require_account(connection, treasury)["version"]
        event_id = _key("capital", symbol, end.isoformat())
        event = self.service.ledger.post(event_id, (
            Posting(self.service._customer(treasury), "USD", amount.copy_negate()),
            Posting(_RESERVE, "USD", amount)), connection=connection)
        self.service._bump(connection, treasury)
        self.service._event(connection, "FUNDING_ROUNDING_CAPITAL_LOCKED", treasury,
                            {"symbol": symbol, "period_end": end.isoformat(), "amount": decimal_text(amount),
                             "deposit_reference": reference, "journal_event_id": event_id})
        return {"source_account_id": treasury, "deposit_reference": reference,
                "source_account_pre_version": previous_version, "units": str(units),
                "amount": decimal_text(amount), "event_id": event_id, "sequence": event.sequence}

    @staticmethod
    def _verify_journal(connection, event_id, sequence, expected):
        if sequence is not None and (type(sequence) is not int or sequence <= 0):
            raise FundingError("funding_reconciliation", "journal sequence must be a native positive integer", 503)
        row = connection.execute("SELECT sequence,sealed FROM ledger_events WHERE event_id=?", (event_id,)).fetchone()
        if row is None or row["sealed"] != 1 or sequence is not None and row["sequence"] != sequence:
            raise FundingError("funding_reconciliation", "missing committed funding journal", 503)
        postings = list(connection.execute("SELECT account,asset,units FROM ledger_postings WHERE sequence=? ORDER BY ordinal",
                                           (row["sequence"],)))
        actual = sorted(tuple(item) for item in postings)
        required = sorted((account, "USD", str(units)) for account, units in expected.items())
        if actual != required:
            raise FundingError("funding_reconciliation", "funding journal postings differ from the receipt", 503)
