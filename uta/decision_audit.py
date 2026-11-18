"""Append-only market, code/configuration and linear-risk decision evidence.

Hashes identify unsigned local evidence. Source files must remain immutable for
the process lifetime; this is not a signature, release repository or OS boundary.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from fractions import Fraction
from hashlib import sha256
import importlib
import inspect
import json
from pathlib import Path
import platform
import sqlite3
import sys
from types import CodeType

from . import __version__
from .market import MarketSnapshot
from .portfolio import (LinearExposure, LoanAccount, PortfolioRules,
                        calculate_cross_risk)
from .products import AccountMode, ProductCatalog
from .reserve_kernel import ReserveInputs, calculate_reserve
from .storage import Database, StorageError


FORMAT = 1
TRADING_SCHEMA = 3
ADMISSION_CONTRACT = "UTA-LINEAR-ADMISSION-v1"
_TABLES = {"uta_audit_capability", "uta_market_history", "uta_code_artifacts",
           "uta_risk_policies", "uta_risk_decisions"}


def _guard_definitions():
    """The complete definitions, shared by explicit install and validation."""
    definitions = {}
    for table in sorted(_TABLES):
        key = {"uta_audit_capability": "singleton", "uta_market_history": "snapshot_id",
               "uta_code_artifacts": "artifact_id", "uta_risk_policies": "policy_id",
               "uta_risk_decisions": "decision_id"}[table]
        for action in ("UPDATE", "DELETE"):
            name = f"audit_{table}_no_{action.lower()}"
            definitions[name] = (table, f"CREATE TRIGGER {name} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'audit archive is immutable'); END")
        name = f"audit_{table}_no_replace"
        definitions[name] = (table, f"CREATE TRIGGER {name} BEFORE INSERT ON {table} WHEN EXISTS (SELECT 1 FROM {table} WHERE {key}=NEW.{key}) BEGIN SELECT RAISE(ABORT,'audit identity cannot be replaced'); END")
    definitions["audit_order_requires_decision"] = ("uta_orders", "CREATE TRIGGER audit_order_requires_decision BEFORE INSERT ON uta_orders WHEN NEW.admission_decision_id IS NULL BEGIN SELECT RAISE(ABORT,'audit decision required for new order'); END")
    definitions["audit_fill_requires_decision"] = ("uta_fills", "CREATE TRIGGER audit_fill_requires_decision BEFORE INSERT ON uta_fills WHEN NEW.execution_decision_id IS NULL BEGIN SELECT RAISE(ABORT,'audit decision required for new fill'); END")
    for operation in ("INSERT", "UPDATE"):
        name = f"audit_market_{operation.lower()}_requires_history"
        definitions[name] = ("uta_market", f"CREATE TRIGGER {name} BEFORE {operation} ON uta_market WHEN NOT EXISTS (SELECT 1 FROM uta_market_history WHERE payload=NEW.payload) BEGIN SELECT RAISE(ABORT,'full market history is required'); END")
    return definitions


class DecisionAuditError(StorageError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value):
    return sha256(value.encode("utf-8")).hexdigest()


def _decimal(value):
    value = Fraction(value)
    denominator, twos, fives = value.denominator, 0, 0
    while denominator % 2 == 0:
        denominator //= 2
        twos += 1
    while denominator % 5 == 0:
        denominator //= 5
        fives += 1
    if denominator != 1:
        raise DecisionAuditError("audit_replay_precision", "replayed amount is not a terminating decimal")
    scale = max(twos, fives)
    number = value.numerator * 2 ** (scale - twos) * 5 ** (scale - fives)
    return Decimal((int(number < 0), tuple(map(int, str(abs(number)))), -scale))


def _text(value):
    result = format(_decimal(value), "f")
    return (result.rstrip("0").rstrip(".") if "." in result else result) if value else "0"


def _code_value(value):
    """Deterministic code constants, without deployment paths or hash seed."""
    if isinstance(value, CodeType):
        return {"code": value.co_code.hex(), "name": value.co_name,
                "args": [value.co_argcount, value.co_posonlyargcount, value.co_kwonlyargcount],
                "locals": value.co_nlocals, "stack": value.co_stacksize, "flags": value.co_flags,
                "names": value.co_names, "variables": value.co_varnames,
                "free": value.co_freevars, "cells": value.co_cellvars,
                "constants": [_code_value(item) for item in value.co_consts],
                "first_line": value.co_firstlineno,
                "lines": value.co_linetable.hex(),
                "exceptions": getattr(value, "co_exceptiontable", b"").hex()}
    if value is None or type(value) in (bool, int, str):
        return value
    if isinstance(value, tuple):
        return {"tuple": [_code_value(item) for item in value]}
    if isinstance(value, frozenset):
        return {"frozenset": sorted((_code_value(item) for item in value), key=_json)}
    if isinstance(value, bytes):
        return {"bytes": value.hex()}
    if isinstance(value, float):
        return {"float": value.hex()}
    if isinstance(value, complex):
        return {"complex": [value.real.hex(), value.imag.hex()]}
    if value is Ellipsis:
        return {"ellipsis": True}
    raise DecisionAuditError("audit_artifact_unavailable", "unsupported loaded code constant in risk engine")


def _loaded_engine():
    """Fingerprint current financial/replay functions, including wrapped bodies.

    Only fixed installed modules are imported. No archive content is imported,
    compiled or executed. Runtime object mutation is not a hostile-code boundary.
    """
    result = {}
    modules = ("service", "decision_audit", "reserve_kernel", "portfolio", "products",
               "models", "market", "ledger", "storage")
    for name in modules:
        module = importlib.import_module("uta." + name)
        functions = {}
        for attribute, value in vars(module).items():
            if inspect.isfunction(value):
                functions[attribute] = value
            elif inspect.isclass(value) and value.__module__ == module.__name__:
                for member_name, member in vars(value).items():
                    if isinstance(member, (staticmethod, classmethod)):
                        member = member.__func__
                    if isinstance(member, property):
                        for accessor in ("fget", "fset", "fdel"):
                            function = getattr(member, accessor)
                            if function is not None:
                                functions[f"{attribute}.{member_name}.{accessor}"] = function
                    elif inspect.isfunction(member):
                        functions[f"{attribute}.{member_name}"] = member
        for attribute, function in functions.items():
            result[f"{module.__name__}.{attribute}"] = _digest(_json({
                "function": _code_value(function.__code__),
                "unwrapped": _code_value(inspect.unwrap(function).__code__)}))
    return result


def code_artifact():
    """Fingerprint deployed sources, loaded financial code and runtime.

    No Git checkout is required: installed source wheels are fingerprintable.
    Release source bytes must be retained separately to run that exact release.
    """
    directory = Path(__file__).resolve().parent
    sources = {path.relative_to(directory).as_posix(): sha256(path.read_bytes()).hexdigest()
               for path in sorted(directory.rglob("*.py"))}
    if not sources or "service.py" not in sources or "decision_audit.py" not in sources:
        raise DecisionAuditError("audit_artifact_unavailable", "deployed Python source manifest is incomplete")
    return {"format": FORMAT, "signed": False, "app_version": __version__,
            "python_implementation": platform.python_implementation(),
            "python_version": sys.version, "sqlite_version": sqlite3.sqlite_version,
            "source_files": sources, "source_digest": _digest(_json(sources)),
            "loaded_engine": _loaded_engine(), "python_optimize": sys.flags.optimize,
            "deployment_assumption": "immutable source files for the process lifetime"}


class DecisionAudit:
    """Same-connection writer helpers and read-only archive/replay queries."""

    def __init__(self, database: Database):
        self.database = database
        self.manifest = code_artifact()
        self.artifact_id = "artifact:" + _digest(_json(self.manifest))
        self.policy_id = None

    @staticmethod
    def policy(exchange):
        return {"format": FORMAT, "risk_mode": "legacy_reference" if exchange.product_catalog is None else "phase1_cross",
                "catalog": None if exchange.product_catalog is None else json.loads(exchange.product_catalog.to_json()),
                "rules": None if exchange.portfolio_rules is None else json.loads(exchange.portfolio_rules.to_json()),
                "scales": dict(exchange.scales), "fee_rate": str(exchange.fee_rate),
                "max_price_age_us": exchange.max_price_age // timedelta(microseconds=1),
                "order_precision": 8, "reserve_formula": "linear-adverse-loss-cumulative-fee-v1",
                "admission_contract": ADMISSION_CONTRACT,
                "execution_options": {"reserve_cache_size": exchange._reserve_kernel.capacity,
                                      "market_cache_size": exchange._market_decode_cache.capacity}}

    @staticmethod
    def _insert(connection, table, id_column, identity, payload_column, payload):
        row = connection.execute(f"SELECT {payload_column} FROM {table} WHERE {id_column}=?", (identity,)).fetchone()
        if row is None:
            connection.execute(f"INSERT INTO {table}({id_column},{payload_column}) VALUES (?,?)", (identity, payload))
        elif row[0] != payload:
            raise DecisionAuditError("audit_content_conflict", "content-addressed archive has conflicting bytes")

    def install(self, connection, *, policy, recorded_at):
        """Explicit, transactional schema-2 upgrade; existing version 3 is strict."""
        version = connection.execute("SELECT version FROM uta_schema").fetchone()[0]
        if version == TRADING_SCHEMA:
            self.validate(connection)
        else:
            if version != 2:
                raise DecisionAuditError("audit_schema_version", "audit upgrade requires trading schema 2")
            existing = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE name IN (" + ",".join("?" for _ in _TABLES) + ")", tuple(_TABLES))}
            if existing:
                raise DecisionAuditError("audit_partial_schema", "partial audit schema cannot be automatically repaired")
            statements = (
                "CREATE TABLE uta_audit_capability (singleton INTEGER PRIMARY KEY CHECK(singleton=1),format INTEGER NOT NULL,enabled_at TEXT NOT NULL,legacy_event_watermark INTEGER NOT NULL,legacy_order_count INTEGER NOT NULL,legacy_fill_count INTEGER NOT NULL,gaps TEXT NOT NULL)",
                "CREATE TABLE uta_market_history (snapshot_id TEXT PRIMARY KEY,content_digest TEXT NOT NULL UNIQUE,payload TEXT NOT NULL,origin TEXT NOT NULL,recorded_at TEXT NOT NULL)",
                "CREATE TABLE uta_code_artifacts (artifact_id TEXT PRIMARY KEY,manifest TEXT NOT NULL)",
                "CREATE TABLE uta_risk_policies (policy_id TEXT PRIMARY KEY,payload TEXT NOT NULL)",
                """CREATE TABLE uta_risk_decisions (decision_id TEXT PRIMARY KEY,kind TEXT NOT NULL,
                    account_id TEXT NOT NULL REFERENCES uta_accounts(account_id),business_id TEXT NOT NULL,
                    market_snapshot_id TEXT NOT NULL REFERENCES uta_market_history(snapshot_id),
                    artifact_id TEXT NOT NULL REFERENCES uta_code_artifacts(artifact_id),
                    policy_id TEXT NOT NULL REFERENCES uta_risk_policies(policy_id),pre_version INTEGER NOT NULL,
                    post_version INTEGER NOT NULL,recorded_at TEXT NOT NULL,input_payload TEXT NOT NULL,
                    summary_payload TEXT NOT NULL,UNIQUE(kind,account_id,business_id))""",
                "ALTER TABLE uta_orders ADD COLUMN admission_decision_id TEXT REFERENCES uta_risk_decisions(decision_id) DEFERRABLE INITIALLY DEFERRED",
                "ALTER TABLE uta_fills ADD COLUMN execution_decision_id TEXT REFERENCES uta_risk_decisions(decision_id) DEFERRABLE INITIALLY DEFERRED",
            )
            for statement in statements:
                connection.execute(statement)
            for _, definition in _guard_definitions().values():
                connection.execute(definition)
            gaps = {"before_upgrade": "historical decisions and replaced markets are unavailable; no backfill inferred",
                    "supported_decisions": ["ORDER_ACCEPTED", "FILL_CONFIRMED"],
                    "not_captured": ["business rejections", "spot decisions", "new credit decisions", "risk-reducing cancels and repayments"]}
            connection.execute("INSERT INTO uta_audit_capability VALUES (1,?,?,?,?,?,?)",
                (FORMAT, recorded_at, connection.execute("SELECT COALESCE(MAX(sequence),0) FROM uta_events").fetchone()[0],
                 connection.execute("SELECT COUNT(*) FROM uta_orders").fetchone()[0],
                 connection.execute("SELECT COUNT(*) FROM uta_fills").fetchone()[0], _json(gaps)))
            current = connection.execute("SELECT payload FROM uta_market WHERE singleton=1").fetchone()
            if current is not None:
                self.archive_market(connection, current[0], origin="UPGRADE_OBSERVED", recorded_at=recorded_at)
            connection.execute("UPDATE uta_schema SET version=?", (TRADING_SCHEMA,))
        self._insert(connection, "uta_code_artifacts", "artifact_id", self.artifact_id, "manifest", _json(self.manifest))
        encoded = _json(policy)
        self.policy_id = "policy:" + _digest(encoded)
        self._insert(connection, "uta_risk_policies", "policy_id", self.policy_id, "payload", encoded)

    @staticmethod
    def validate(connection):
        guards = _guard_definitions()
        expected = {**{name: "table" for name in _TABLES}, **{name: "trigger" for name in guards}}
        actual = {row[0]: row[1] for row in connection.execute("SELECT name,type FROM sqlite_master WHERE name IN (" + ",".join("?" for _ in expected) + ")", tuple(expected))}
        if actual != expected:
            raise DecisionAuditError("audit_schema_corrupt", "required audit tables or guards are missing; automatic repair is forbidden")
        actual_guards = {row[0]: (row[1], row[2]) for row in connection.execute(
            "SELECT name,tbl_name,sql FROM sqlite_master WHERE type='trigger' AND name GLOB 'audit_*'")}
        if actual_guards != guards:
            raise DecisionAuditError("audit_schema_corrupt", "audit guard definitions or inventory differ; automatic repair is forbidden")
        row = connection.execute("SELECT format FROM uta_audit_capability WHERE singleton=1").fetchone()
        if row is None or row[0] != FORMAT:
            raise DecisionAuditError("audit_schema_version", "unsupported audit capability version")
        for table, column in (("uta_orders", "admission_decision_id"), ("uta_fills", "execution_decision_id")):
            if column not in {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}:
                raise DecisionAuditError("audit_schema_corrupt", "required financial decision link is missing")

    @staticmethod
    def archive_market(connection, payload, *, origin, recorded_at):
        DecisionAudit.validate(connection)
        MarketSnapshot.from_json(payload)
        digest = _digest(payload)
        identity = "market:" + digest
        row = connection.execute("SELECT payload,content_digest FROM uta_market_history WHERE snapshot_id=?", (identity,)).fetchone()
        if row is None:
            connection.execute("INSERT INTO uta_market_history VALUES (?,?,?,?,?)", (identity, digest, payload, origin, recorded_at))
        elif tuple(row) != (payload, digest):
            raise DecisionAuditError("audit_content_conflict", "market archive content is inconsistent")
        return identity

    @staticmethod
    def market_ref(connection, market):
        DecisionAudit.validate(connection)
        row = connection.execute("SELECT payload FROM uta_market WHERE singleton=1").fetchone()
        if row is None or MarketSnapshot.from_json(row[0]).to_json() != market.to_json():
            raise DecisionAuditError("audit_market_mismatch", "decision market differs from authoritative snapshot")
        identity = "market:" + _digest(row[0])
        found = connection.execute("SELECT payload FROM uta_market_history WHERE snapshot_id=?", (identity,)).fetchone()
        if found is None or found[0] != row[0]:
            raise DecisionAuditError("audit_market_missing", "current market has no complete historical evidence")
        return identity

    def decision_id(self, kind, account_id, business_id):
        return "decision:" + _digest(_json([kind, account_id, business_id]))

    def record(self, connection, *, decision_id, kind, account_id, business_id, market_id,
               before, after, operation, summary, recorded_at):
        self.validate(connection)
        connection.execute("INSERT INTO uta_risk_decisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (decision_id, kind, account_id, business_id, market_id, self.artifact_id, self.policy_id,
             before["version"], after["version"], recorded_at,
             _json({"operation": operation, "before": before, "after": after}), _json(summary)))

    def _read(self, table, column, identity):
        with self.database.read_transaction() as connection:
            self.validate(connection)
            row = connection.execute(f"SELECT * FROM {table} WHERE {column}=?", (identity,)).fetchone()
            if row is None:
                raise DecisionAuditError("audit_not_found", "requested historical evidence is unavailable")
            return dict(row)

    def decision(self, identity):
        row = self._read("uta_risk_decisions", "decision_id", identity)
        row["inputs"] = json.loads(row.pop("input_payload"))
        row["summary"] = json.loads(row.pop("summary_payload"))
        if (identity != self.decision_id(row["kind"], row["account_id"], row["business_id"])
                or row["pre_version"] != row["inputs"]["before"]["version"]
                or row["post_version"] != row["inputs"]["after"]["version"]):
            raise DecisionAuditError("audit_content_conflict", "decision identity or account-version evidence is inconsistent")
        return row

    def market(self, identity):
        row = self._read("uta_market_history", "snapshot_id", identity)
        if row["snapshot_id"] != "market:" + _digest(row["payload"]) or row["content_digest"] != _digest(row["payload"]):
            raise DecisionAuditError("audit_content_conflict", "historical market content digest is invalid")
        return row

    def artifact(self, identity):
        row = self._read("uta_code_artifacts", "artifact_id", identity)
        if identity != "artifact:" + _digest(row["manifest"]):
            raise DecisionAuditError("audit_content_conflict", "historical artifact content digest is invalid")
        return json.loads(row["manifest"])

    def policy_record(self, identity):
        row = self._read("uta_risk_policies", "policy_id", identity)
        if identity != "policy:" + _digest(row["payload"]):
            raise DecisionAuditError("audit_content_conflict", "historical risk policy digest is invalid")
        return json.loads(row["payload"])

    @staticmethod
    def _replay_state(state, market, policy):
        """Numerical replay from archived inputs, without current account rows."""
        reserve = Fraction(0)
        catalog = ProductCatalog.from_json(_json(policy["catalog"])) if policy["catalog"] is not None else None
        rules = PortfolioRules.from_json(_json(policy["rules"])) if policy["rules"] is not None else None
        for order in state["orders"]:
            spec = market.instruments[order["symbol"]]
            rate = spec.initial_margin_rate
            if catalog is not None:
                product = catalog.require_risk_supported(order["symbol"])
                rate = rules.linear_margin[product.risk_tier].initial_margin_rate
            reserve += Fraction(calculate_reserve(ReserveInputs(
                quantity=Decimal(order["quantity"]), filled_quantity=Decimal(order["filled_quantity"]),
                limit_price=Decimal(order["limit_price"]), mark_price=spec.mark_price,
                reduce_only=bool(order["reduce_only"]), initial_margin_rate=rate,
                fee_notional=Decimal(order["fee_notional"]), charged_fee=Decimal(order["charged_fee"]),
                fee_rate=Decimal(policy["fee_rate"]), usd_scale=policy["scales"]["USD"])))
        balances = {asset: Decimal(value) for asset, value in state["balances"].items()}
        frozen = {asset: Decimal(value) for asset, value in state["frozen_assets"].items()}
        positions = state["positions"]
        if catalog is not None:
            account = LoanAccount(
                gross_assets={asset: value for asset, value in balances.items() if value > 0},
                cash_deficits={asset: value.copy_abs() for asset, value in balances.items() if value < 0},
                principal={row["asset"]: Decimal(row["principal"]) for row in state["liabilities"] if Decimal(row["principal"])},
                interest={row["asset"]: Decimal(row["interest"]) for row in state["liabilities"] if Decimal(row["interest"])},
                frozen_assets=frozen, positions={symbol: LinearExposure(symbol, Decimal(row["quantity"]), Decimal(row["cost_basis"])) for symbol, row in positions.items()},
                order_margin=_decimal(reserve), mode=AccountMode.CROSS)
            # This offline check reconstructs financial values. Historical
            # freshness is evidence in the timestamp/market record, not a live
            # validation against today's clock.
            calculated = calculate_cross_risk(account, market, catalog, rules,
                now=market.observed_at, max_age=timedelta(microseconds=policy["max_price_age_us"]))
            names = ("accounting_equity", "collateral_value", "risk_equity", "loan_value", "principal_value",
                     "interest_value", "cash_deficit_value", "debt_value", "unrealized_pnl", "frozen_value",
                     "initial_margin", "maintenance_margin", "available_margin")
            result = {name: _text(Fraction(getattr(calculated, name))) for name in names}
            result.update(equity=result["risk_equity"], open_order_margin=_text(reserve))
            return result
        equity = Fraction(0)
        for asset, balance in balances.items():
            if balance:
                spec = market.assets[asset]
                equity += Fraction(balance) * Fraction(spec.price) * (Fraction(spec.collateral_factor) if balance > 0 else 1)
        for asset, amount in frozen.items():
            spec = market.assets[asset]
            equity -= Fraction(amount) * Fraction(spec.price) * Fraction(spec.collateral_factor)
        for debt in state["liabilities"]:
            total = Fraction(Decimal(debt["principal"])) + Fraction(Decimal(debt["interest"]))
            if total:
                equity -= total * Fraction(market.assets[debt["asset"]].price)
        im, mm = Fraction(0), Fraction(0)
        for symbol, position in positions.items():
            spec = market.instruments[symbol]
            quantity, cost = Fraction(Decimal(position["quantity"])), Fraction(Decimal(position["cost_basis"]))
            equity += quantity * Fraction(spec.mark_price) - cost
            im += abs(quantity) * Fraction(spec.mark_price) * Fraction(spec.initial_margin_rate)
            mm += abs(quantity) * Fraction(spec.mark_price) * Fraction(spec.maintenance_margin_rate)
        return {"equity": _text(equity), "initial_margin": _text(im), "maintenance_margin": _text(mm),
                "open_order_margin": _text(reserve), "available_margin": _text(equity - im - reserve)}

    @staticmethod
    def _admission_projection(state, request, policy):
        """Separate exact settlement derivation; never calls service helpers.

        The projection retains the original outstanding orders. Admission tests
        their current reserve before separately testing the proposed reserve.
        Realized loss rounds down; a new order's full fee rounds up in USD units.
        """
        projected = json.loads(_json(state))
        symbol = request["symbol"]
        quantity = Fraction(Decimal(request["quantity"]))
        price = Fraction(Decimal(request["limit_price"]))
        prior = state["positions"].get(symbol, {"quantity": "0", "cost_basis": "0"})
        old, cost = Fraction(Decimal(prior["quantity"])), Fraction(Decimal(prior["cost_basis"]))
        remaining, pnl = old + quantity, Fraction(0)
        unit = 10 ** policy["scales"]["USD"]
        if not old or (old > 0) == (quantity > 0):
            basis = cost + quantity * price
        else:
            close = min(abs(old), abs(quantity))
            direction = 1 if old > 0 else -1
            exact = close * (direction * price - cost / abs(old))
            pnl = Fraction((exact * unit).numerator // (exact * unit).denominator, unit)
            if abs(quantity) < abs(old):
                # The rounded settlement remainder belongs to surviving cost.
                basis = cost + pnl - direction * close * price
            else:
                basis = remaining * price
        if remaining:
            projected["positions"][symbol] = {"quantity": _text(remaining), "cost_basis": _text(basis)}
        else:
            projected["positions"].pop(symbol, None)
        exact_fee = abs(quantity) * price * Fraction(Decimal(policy["fee_rate"])) * unit
        fee = Fraction(-(-exact_fee.numerator // exact_fee.denominator), unit)
        projected["balances"]["USD"] = _text(Fraction(Decimal(state["balances"]["USD"])) + pnl - fee)
        return projected, pnl, fee

    @staticmethod
    def _replay_admission(record, market, policy, values, operation):
        """Check the recorded v1 linear financial predicates, not resubmit.

        Settlement and predicates here do not call ExchangeService admission or
        settlement helpers. Risk valuation below uses the existing numerical
        replay engine; this is not an independent reference for that engine.
        """
        result = {"status": "UNSUPPORTED", "eligible": None, "matches": None,
                  "checks": {}, "differences": {},
                  "scope": "recorded linear financial admission predicates",
                  "excluded": ["historical clock freshness", "writer ownership", "API authorization",
                               "matching or command re-execution", "business rejection archive",
                               "concurrent orders under arbitrary partial-fill sequences"]}
        evidence = record["summary"].get("admission")
        if record["kind"] != "ORDER_ACCEPTED":
            result["reason"] = "decision_kind_not_supported"
            return result
        if evidence is None:
            result["reason"] = "historical_admission_evidence_missing"
            return result
        if (not isinstance(evidence, dict) or type(evidence.get("format")) is not int
                or evidence["format"] != 1 or policy.get("admission_contract") != ADMISSION_CONTRACT
                or evidence.get("contract") != ADMISSION_CONTRACT):
            result["reason"] = "admission_contract_not_supported"
            return result
        try:
            before, after = record["inputs"]["before"], record["inputs"]["after"]
            request = record["inputs"]["operation"]
            if any(type(request[name]) is not str or len(request[name]) > 64
                   for name in ("quantity", "limit_price")):
                raise ValueError("bounded native order amounts required")
            quantity, price = Decimal(request["quantity"]), Decimal(request["limit_price"])
            ro = request["reduce_only"]
            bounds = (type(ro) is bool and quantity != 0 and price > 0 and
                all(value.is_finite() and len(value.as_tuple().digits) <= 32
                    and -8 <= value.as_tuple().exponent <= 12 and value.copy_abs() <= Decimal("1000000000000")
                    for value in (quantity, price)))
            result["checks"]["request_bounds"] = bounds
            if not bounds:
                result.update(status="FAILED", eligible=False, matches=False, reason="native_order_bounds")
                return result
            q, p = Fraction(quantity), Fraction(price)
            projected, pnl, fee = DecisionAudit._admission_projection(before, request, policy)
            risk = DecisionAudit._replay_state(projected, market, policy)
            recorded = record["summary"]["projected_execution"]
            differences = result["differences"]
            for name, actual in risk.items():
                if actual != recorded.get(name):
                    differences["projected_execution." + name] = {"recorded": recorded.get(name), "replayed": actual}
            for name, actual in (("projected_realized_pnl", _text(pnl)), ("projected_fee", _text(fee))):
                if evidence.get(name) != actual:
                    differences[name] = {"recorded": evidence.get(name), "replayed": actual}
            checks = result["checks"]
            # The production admission path validates the stored control row
            # even for RO orders. Halted=True permits RO; corrupt types do not.
            checks["control_state_valid"] = type(before["halted"]) is bool and type(after["halted"]) is bool
            checks["valuation_evidence_consistent"] = (all(
                record["summary"]["risk_" + side].get(name) == value
                for side in ("before", "after") for name, value in values[side].items())
                and record["summary"]["reserved_margin"] == operation["reserved_margin"])
            checks["position_limit"] = abs(q + Fraction(Decimal(before["positions"].get(
                request["symbol"], {"quantity": "0"})["quantity"]))) <= 10**12
            checks["order_limit"] = len(before["orders"]) < 1000
            checks["account_version_step"] = (type(before["version"]) is int and
                type(after["version"]) is int and after["version"] == before["version"] + 1)
            checks["unrelated_state_unchanged"] = all(before[name] == after[name] for name in
                ("balances", "frozen_assets", "positions", "liabilities", "halted", "liquidation_state"))
            orders = after["orders"]
            checks["prior_live_orders_unchanged"] = orders[:-1] == before["orders"] and len(orders) == len(before["orders"]) + 1
            new = orders[-1] if orders else {}
            checks["new_order_identity"] = (request["order_id"] == record["business_id"]
                and not any(row["order_id"] == request["order_id"] for row in before["orders"])
                and all(new.get(name) == request[name] for name in ("order_id", "symbol", "quantity", "limit_price"))
                and new.get("account_id") == record["account_id"]
                and type(new.get("reduce_only")) is int and new["reduce_only"] == int(ro)
                and new.get("filled_quantity") == "0" and new.get("status") == "OPEN"
                and type(new.get("version")) is int and new["version"] == after["version"] and new.get("fee_notional") == "0"
                and new.get("charged_fee") == "0" and new.get("admission_decision_id") == record["decision_id"])
            expected_meta = {"account_version": before["version"], "market_version": market.version,
                             "observed_at": market.observed_at.isoformat(), "risk_mode": policy["risk_mode"]}
            if policy["catalog"] is not None:
                catalog, rules = policy["catalog"], policy["rules"]
                product = catalog["products"][request["symbol"]]
                checks["product_eligibility"] = (catalog["settlement_asset"] == "USD"
                    and product["kind"] == "linear_perpetual" and product["quote_asset"] == "USD"
                    and product["settlement_asset"] == "USD" and Fraction(Decimal(product["multiplier"])) == 1
                    and not product["eligible_hedges"] and (product["status"] == "active" or
                        (ro and product["status"] == "reduce_only"))
                    and (q / Fraction(Decimal(product["quantity_step"]))).denominator == 1
                    and (p / Fraction(Decimal(product["price_tick"]))).denominator == 1
                    and abs(q) * p >= Fraction(Decimal(product["min_notional"])))
                expected_meta.update(rule_id=rules["rule_id"], rule_version=rules["version"], catalog_version=catalog["version"])
            else:
                checks["product_eligibility"] = request["symbol"] in market.instruments
            checks["version_provenance"] = all(type(recorded.get(key)) is type(value) and recorded[key] == value
                                               for key, value in expected_meta.items())
            current_surplus = Fraction(Decimal(values["before"]["equity"])) - Fraction(Decimal(values["before"]["maintenance_margin"]))
            projected_surplus = Fraction(Decimal(risk["equity"])) - Fraction(Decimal(risk["maintenance_margin"]))
            if ro:
                old = Fraction(Decimal(before["positions"].get(request["symbol"], {"quantity": "0"})["quantity"]))
                held = sum((abs(Fraction(Decimal(row["quantity"])) - Fraction(Decimal(row["filled_quantity"])))
                    for row in before["orders"] if row["symbol"] == request["symbol"] and row["reduce_only"]), Fraction(0))
                checks["reduce_only_quantity"] = bool(old) and (q > 0) != (old > 0) and held + abs(q) <= abs(old)
                checks["reduce_only_surplus"] = projected_surplus >= current_surplus
            else:
                checks["new_exposure_control"] = before["halted"] is False and (before["liquidation_state"] is None
                    or before["liquidation_state"]["state"] == "NORMAL")
                checks["initial_margin_reservation"] = Fraction(Decimal(values["before"]["available_margin"])) >= Fraction(Decimal(operation["reserved_margin"]))
                checks["strict_maintenance_surplus"] = projected_surplus > 0
            result.update(status="VERIFIED" if all(checks.values()) and not differences else "FAILED",
                          eligible=all(checks.values()), matches=all(checks.values()) and not differences,
                          projected_values=risk, projected_realized_pnl=_text(pnl), projected_fee=_text(fee))
        except (KeyError, TypeError, ValueError, ArithmeticError, AttributeError):
            result.update(status="FAILED", eligible=None, matches=False, reason="admission_evidence_invalid")
        return result

    def replay(self, identity):
        """Recompute archived numerical values; refuse a different code/runtime.

        Separately checks supported archived admission predicates. Neither
        result reruns matching, lease ownership or historical clock freshness.
        `matches` remains the numerical result for compatibility.
        """
        record = self.decision(identity)
        try:
            manifest = self.artifact(record["artifact_id"])
            current = code_artifact()
        except (OSError, DecisionAuditError) as exc:
            raise DecisionAuditError("replay_artifact_unavailable", "matching Git/wheel source and runtime artifact is unavailable; replay was not calculated") from exc
        if _json(manifest) != _json(current) or _json(self.manifest) != _json(current):
            raise DecisionAuditError("replay_engine_mismatch", "load the matching Git/wheel artifact and Python/SQLite runtime; current engine cannot authoritatively replay this decision")
        market = MarketSnapshot.from_json(self.market(record["market_snapshot_id"])["payload"])
        policy = self.policy_record(record["policy_id"])
        replayed = {side: self._replay_state(record["inputs"][side], market, policy) for side in ("before", "after")}
        differences = {}
        for side, values in replayed.items():
            expected = record["summary"]["risk_" + side]
            for field, value in values.items():
                if value != expected[field]:
                    differences[f"{side}.{field}"] = {"recorded": expected[field], "replayed": value}
        operation = {}
        if record["kind"] == "ORDER_ACCEPTED":
            request = record["inputs"]["operation"]
            spec = market.instruments[request["symbol"]]
            rate = spec.initial_margin_rate
            if policy["catalog"] is not None:
                catalog = ProductCatalog.from_json(_json(policy["catalog"]))
                rules = PortfolioRules.from_json(_json(policy["rules"]))
                rate = rules.linear_margin[catalog.require_risk_supported(request["symbol"]).risk_tier].initial_margin_rate
            reserve = calculate_reserve(ReserveInputs(
                quantity=Decimal(request["quantity"]), filled_quantity=Decimal(0),
                limit_price=Decimal(request["limit_price"]), mark_price=spec.mark_price,
                reduce_only=request["reduce_only"], initial_margin_rate=rate,
                fee_notional=Decimal(0), charged_fee=Decimal(0), fee_rate=Decimal(policy["fee_rate"]),
                usd_scale=policy["scales"]["USD"]))
            operation["reserved_margin"] = _text(Fraction(reserve))
            if operation["reserved_margin"] != record["summary"]["reserved_margin"]:
                differences["operation.reserved_margin"] = {"recorded": record["summary"]["reserved_margin"],
                                                           "replayed": operation["reserved_margin"]}
        admission = self._replay_admission(record, market, policy, replayed, operation)
        return {"decision_id": identity, "market_snapshot_id": record["market_snapshot_id"],
                "artifact_id": record["artifact_id"], "policy_id": record["policy_id"],
                "values": replayed, "operation": operation, "differences": differences, "matches": not differences,
                "valuation_matches": not differences, "admission": admission,
                "scope": "numerical valuation plus separately scoped admission predicates; no historical re-execution or live freshness claim"}
