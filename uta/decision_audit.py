"""Append-only market, code/configuration and linear-risk decision evidence.

Hashes identify unsigned local evidence. Source files must remain immutable for
the process lifetime; this is not a signature, release repository or OS boundary.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import platform
import sqlite3
import sys

from . import __version__
from .market import MarketSnapshot
from .portfolio import (LinearExposure, LoanAccount, PortfolioRules,
                        calculate_cross_risk)
from .products import AccountMode, ProductCatalog
from .reserve_kernel import ReserveInputs, calculate_reserve
from .storage import Database, StorageError


FORMAT = 1
TRADING_SCHEMA = 3
_TABLES = {"uta_audit_capability", "uta_market_history", "uta_code_artifacts",
           "uta_risk_policies", "uta_risk_decisions"}
_GUARDS = {f"audit_{table}_{action}" for table in _TABLES
           for action in ("no_update", "no_delete", "no_replace")}
_GUARDS |= {"audit_order_requires_decision", "audit_fill_requires_decision",
            "audit_market_insert_requires_history", "audit_market_update_requires_history"}


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


def code_artifact():
    """Fingerprint the deployed Python sources and execution runtime once.

    No Git checkout is required: installed source wheels are fingerprintable.
    Release source bytes must be retained separately to run that exact release.
    """
    directory = Path(__file__).resolve().parent
    sources = {path.name: sha256(path.read_bytes()).hexdigest()
               for path in sorted(directory.glob("*.py"))}
    if not sources or "service.py" not in sources or "decision_audit.py" not in sources:
        raise DecisionAuditError("audit_artifact_unavailable", "deployed Python source manifest is incomplete")
    return {"format": FORMAT, "signed": False, "app_version": __version__,
            "python_implementation": platform.python_implementation(),
            "python_version": sys.version, "sqlite_version": sqlite3.sqlite_version,
            "source_files": sources, "source_digest": _digest(_json(sources)),
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
                "order_precision": 8, "reserve_formula": "linear-adverse-loss-cumulative-fee-v1"}

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
            for table in sorted(_TABLES):
                key = {"uta_audit_capability": "singleton", "uta_market_history": "snapshot_id",
                       "uta_code_artifacts": "artifact_id", "uta_risk_policies": "policy_id",
                       "uta_risk_decisions": "decision_id"}[table]
                for action in ("UPDATE", "DELETE"):
                    connection.execute(f"CREATE TRIGGER audit_{table}_no_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'audit archive is immutable'); END")
                connection.execute(f"CREATE TRIGGER audit_{table}_no_replace BEFORE INSERT ON {table} WHEN EXISTS (SELECT 1 FROM {table} WHERE {key}=NEW.{key}) BEGIN SELECT RAISE(ABORT,'audit identity cannot be replaced'); END")
            connection.execute("CREATE TRIGGER audit_order_requires_decision BEFORE INSERT ON uta_orders WHEN NEW.admission_decision_id IS NULL BEGIN SELECT RAISE(ABORT,'audit decision required for new order'); END")
            connection.execute("CREATE TRIGGER audit_fill_requires_decision BEFORE INSERT ON uta_fills WHEN NEW.execution_decision_id IS NULL BEGIN SELECT RAISE(ABORT,'audit decision required for new fill'); END")
            for operation in ("INSERT", "UPDATE"):
                connection.execute(f"CREATE TRIGGER audit_market_{operation.lower()}_requires_history BEFORE {operation} ON uta_market WHEN NOT EXISTS (SELECT 1 FROM uta_market_history WHERE payload=NEW.payload) BEGIN SELECT RAISE(ABORT,'full market history is required'); END")
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
        expected = {**{name: "table" for name in _TABLES}, **{name: "trigger" for name in _GUARDS}}
        actual = {row[0]: row[1] for row in connection.execute("SELECT name,type FROM sqlite_master WHERE name IN (" + ",".join("?" for _ in expected) + ")", tuple(expected))}
        if actual != expected:
            raise DecisionAuditError("audit_schema_corrupt", "required audit tables or guards are missing; automatic repair is forbidden")
        row = connection.execute("SELECT format FROM uta_audit_capability WHERE singleton=1").fetchone()
        if row is None or row[0] != FORMAT:
            raise DecisionAuditError("audit_schema_version", "unsupported audit capability version")
        for table, column in (("uta_orders", "admission_decision_id"), ("uta_fills", "execution_decision_id")):
            if column not in {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}:
                raise DecisionAuditError("audit_schema_corrupt", "required financial decision link is missing")

    @staticmethod
    def archive_market(connection, payload, *, origin, recorded_at):
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
        connection.execute("INSERT INTO uta_risk_decisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (decision_id, kind, account_id, business_id, market_id, self.artifact_id, self.policy_id,
             before["version"], after["version"], recorded_at,
             _json({"operation": operation, "before": before, "after": after}), _json(summary)))

    def _read(self, table, column, identity):
        with self.database.read_transaction() as connection:
            row = connection.execute(f"SELECT * FROM {table} WHERE {column}=?", (identity,)).fetchone()
            if row is None:
                raise DecisionAuditError("audit_not_found", "requested historical evidence is unavailable")
            return dict(row)

    def decision(self, identity):
        row = self._read("uta_risk_decisions", "decision_id", identity)
        row["inputs"] = json.loads(row.pop("input_payload"))
        row["summary"] = json.loads(row.pop("summary_payload"))
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

    def replay(self, identity):
        """Recompute archived numerical values; refuse a different code/runtime.

        Does not rerun matching, admission eligibility, lease ownership or clock
        freshness. It is a valuation replay, not a historical command resubmit.
        """
        record = self.decision(identity)
        manifest = self.artifact(record["artifact_id"])
        if _json(manifest) != _json(self.manifest):
            raise DecisionAuditError("audit_artifact_mismatch", "use the recorded source and runtime release for exact replay")
        market = MarketSnapshot.from_json(self.market(record["market_snapshot_id"])["payload"])
        policy = self.policy_record(record["policy_id"])
        replayed = {side: self._replay_state(record["inputs"][side], market, policy) for side in ("before", "after")}
        differences = {}
        for side, values in replayed.items():
            expected = record["summary"]["risk_" + side]
            for field, value in values.items():
                if value != expected[field]:
                    differences[f"{side}.{field}"] = {"recorded": expected[field], "replayed": value}
        return {"decision_id": identity, "market_snapshot_id": record["market_snapshot_id"],
                "artifact_id": record["artifact_id"], "policy_id": record["policy_id"],
                "values": replayed, "differences": differences, "matches": not differences,
                "scope": "numerical valuation; no historical re-execution or live freshness claim"}
