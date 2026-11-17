"""Dedicated internal synthetic credit audit contract, never an activation gate.

Schema definitions are consumed by the future fresh native-v2 installer. Merely
importing this module does not install schema, grant ownership or enable credit.
Format1 NATIVE_PREPARED is not upgraded. Capture/replay and positive dispatch are
separate implementation slices; no incomplete record is a valid credit audit.
"""
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Context, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
from hashlib import sha256
from decimal import Decimal
import json
import re
from types import MappingProxyType

from .storage import StorageError


FORMAT = 2
KIND = "CREDIT_BORROWED"
TABLE_SQL = MappingProxyType({
    "uta_credit_code_artifacts": "CREATE TABLE uta_credit_code_artifacts(artifact_id TEXT PRIMARY KEY NOT NULL,manifest TEXT NOT NULL)",
    "uta_credit_risk_policies": "CREATE TABLE uta_credit_risk_policies(policy_id TEXT PRIMARY KEY NOT NULL,payload TEXT NOT NULL)",
    "uta_credit_decisions": """CREATE TABLE uta_credit_decisions(
      decision_id TEXT PRIMARY KEY NOT NULL,operation_id TEXT NOT NULL UNIQUE,
      format INTEGER NOT NULL CHECK(typeof(format)='integer' AND format=2),
      kind TEXT NOT NULL CHECK(kind='CREDIT_BORROWED'),
      account_id TEXT NOT NULL REFERENCES uta_accounts(account_id),command_id TEXT NOT NULL,
      inbox_kind TEXT NOT NULL CHECK(inbox_kind='BORROW'),terminal_state TEXT NOT NULL CHECK(terminal_state='SUCCEEDED'),
      asset TEXT NOT NULL REFERENCES ledger_assets(asset),amount TEXT NOT NULL,payload_hash TEXT NOT NULL,
      source_id TEXT NOT NULL,market_snapshot_id TEXT NOT NULL REFERENCES uta_market_history(snapshot_id),
      artifact_id TEXT NOT NULL REFERENCES uta_credit_code_artifacts(artifact_id),
      policy_id TEXT NOT NULL REFERENCES uta_credit_risk_policies(policy_id),
      descriptor_id TEXT NOT NULL,allocation_id TEXT NOT NULL,
      journal_id TEXT NOT NULL,journal_sealed INTEGER NOT NULL CHECK(typeof(journal_sealed)='integer' AND journal_sealed=1),
      pre_version INTEGER NOT NULL CHECK(typeof(pre_version)='integer' AND pre_version>=0 AND pre_version<9223372036854775807),
      post_version INTEGER NOT NULL CHECK(typeof(post_version)='integer' AND post_version=pre_version+1),
      selected_at TEXT NOT NULL,last_checked_at TEXT NOT NULL,recorded_at TEXT NOT NULL,payload TEXT NOT NULL,
      UNIQUE(kind,account_id,command_id),
      UNIQUE(operation_id,kind,account_id,command_id,journal_id),
      FOREIGN KEY(command_id,account_id,inbox_kind,terminal_state)
        REFERENCES uta_command_inbox(command_id,account_id,kind,state) DEFERRABLE INITIALLY DEFERRED,
      FOREIGN KEY(journal_id,journal_sealed)
        REFERENCES ledger_events(event_id,sealed) DEFERRABLE INITIALLY DEFERRED)""",
})
INDEX_SQL = MappingProxyType({
    "credit_audit_v2_inbox_parent": "CREATE UNIQUE INDEX credit_audit_v2_inbox_parent ON uta_command_inbox(command_id,account_id,kind,state)",
    "credit_audit_v2_journal_parent": "CREATE UNIQUE INDEX credit_audit_v2_journal_parent ON ledger_events(event_id,sealed)",
})


def _guard_definitions():
    definitions = {}
    for table, key in (("uta_credit_code_artifacts", "artifact_id"),
                       ("uta_credit_risk_policies", "policy_id"),
                       ("uta_credit_decisions", "decision_id")):
        for action in ("UPDATE", "DELETE"):
            name = f"credit_audit_v2_{table}_no_{action.lower()}"
            definitions[name] = (table, f"CREATE TRIGGER {name} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'credit audit history is immutable'); END")
        name = f"credit_audit_v2_{table}_no_replace"
        identity = f"{key}=NEW.{key}"
        if table == "uta_credit_decisions":
            identity += " OR operation_id=NEW.operation_id OR (kind=NEW.kind AND account_id=NEW.account_id AND command_id=NEW.command_id)"
        definitions[name] = (table, f"CREATE TRIGGER {name} BEFORE INSERT ON {table} WHEN EXISTS(SELECT 1 FROM {table} WHERE {identity}) BEGIN SELECT RAISE(ABORT,'credit audit identity cannot replace'); END")
    return MappingProxyType(definitions)


TRIGGER_SQL = _guard_definitions()
OBJECT_SQL = MappingProxyType({**TABLE_SQL, **INDEX_SQL,
    **{name: sql for name, (_, sql) in TRIGGER_SQL.items()}})
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z", re.ASCII)


class CreditAuditError(StorageError):
    def __init__(self, code, message, status=503):
        super().__init__(message)
        self.code, self.status = code, status


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def borrow_operation_id(account_id, command_id):
    """Planned business identity, explicitly distinct from full content ID."""
    if any(type(value) is not str or _IDENTIFIER.fullmatch(value) is None
           for value in (account_id, command_id)):
        raise CreditAuditError("credit_audit_invalid", "credit operation identity requires bounded ASCII identifiers")
    return "credit-operation:" + sha256(canonical(["BORROW", account_id, command_id]).encode()).hexdigest()


def read_credit_snapshot(exchange, credit, connection, account_id, asset, *, require_limits=True, require_increment=True):
    """Read exact current gross credit inputs in one real financial transaction.

    This creates no operation scope or role. Native scope setup may call it
    before an intent exists; therefore it must not depend on a credit context.
    The returned dictionaries are data requiring native pre-state binding.
    """
    from .credit import CreditService
    from .service import ExchangeService, ServiceError
    from .writer_fence import _assert_financial_joinable
    if type(require_limits) is not bool or type(require_increment) is not bool:
        raise CreditAuditError("credit_audit_context_invalid", "credit snapshot limit policy must be explicit")
    if connection is None:
        raise CreditAuditError("credit_audit_context_invalid", "credit snapshot requires an existing financial connection")
    if type(credit) is not CreditService or not isinstance(exchange, ExchangeService) or credit.exchange is not exchange:
        raise CreditAuditError("credit_audit_context_invalid", "credit snapshot requires its actual exchange and credit service")
    with exchange.database._using(connection):
        _assert_financial_joinable(exchange.database, connection)
        account = exchange._require_account(connection, account_id)
        credit._asset(asset)
        principal, interest = credit._debt(connection, account_id, asset)
        shard_principal = shard_interest = 0
        for row in connection.execute("SELECT principal,interest FROM uta_liabilities WHERE asset=?", (asset,)):
            shard_principal += credit._stored(asset, row["principal"])
            shard_interest += credit._stored(asset, row["interest"])
        limits = {} if require_limits else None
        for name, query, params in (() if not require_limits else (
                ("account_limit_units", "SELECT units FROM credit_account_limits WHERE account_id=? AND asset=?", (account_id, asset)),
                ("local_asset_limit_units", "SELECT units FROM credit_asset_limits WHERE asset=?", (asset,)))):
            row = connection.execute(query, params).fetchone()
            if row is None:
                raise ServiceError("credit_disabled", "explicit account and local asset limits are required", 409)
            limits[name] = str(credit._limit(row[0]))
        def balance(name):
            value = exchange.ledger.balance(name, asset, connection=connection)
            return str(credit._codec._units(asset, value))
        snapshot = {"version": account["version"], "cash_units": balance(exchange._customer(account_id)),
            "principal_units": str(principal), "interest_units": str(interest),
            "principal_ledger_units": balance(credit.principal_account(account_id)),
            "interest_ledger_units": balance(credit.interest_account(account_id)),
            "shard_principal_units": str(shard_principal), "shard_interest_units": str(shard_interest),
            "pool_units": balance("system:credit-pool"),
            "principal_receivable_units": balance("system:credit-principal-receivable"),
            "interest_receivable_units": balance("system:credit-interest-receivable")}
        # Validate all exact components, including aggregate receivables, before
        # this data may form a staged native intent. No netting is introduced.
        from .credit_transition import _snapshot
        _snapshot(snapshot, require_increment=require_increment)
        return snapshot, limits


def strict_json(raw, *, max_bytes=16 * 1024 * 1024):
    """Canonical retained primitives only; no imports, code or archive hooks."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise CreditAuditError("credit_audit_invalid", "duplicate retained credit evidence key")
            result[key] = value
        return result
    def integer(value):
        if len(value) > 20:
            raise CreditAuditError("credit_audit_invalid", "retained metadata integer exceeds bounds")
        return int(value)
    def no_number(value):
        raise CreditAuditError("credit_audit_invalid", "retained metadata requires integer numbers")
    try:
        if type(raw) is not str or len(raw.encode("utf-8")) > max_bytes:
            raise CreditAuditError("credit_audit_invalid", "retained credit evidence exceeds bounds")
        value = json.loads(raw, object_pairs_hook=pairs, parse_int=integer,
                           parse_float=no_number, parse_constant=no_number)
        if canonical(value) != raw:
            raise CreditAuditError("credit_audit_invalid", "retained credit evidence is not canonical")
        return value
    except CreditAuditError:
        raise
    except (ValueError, TypeError, UnicodeError, RecursionError) as error:
        raise CreditAuditError("credit_audit_invalid", "invalid retained credit evidence") from error


def utc_checkpoint(value):
    """Actual checkpoints use explicit UTC, with seconds or six microdigits."""
    try:
        if (type(value) is not str or re.fullmatch(
                r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{6})?\+00:00", value) is None):
            raise ValueError("checkpoint is not explicit canonical UTC")
        result = datetime.fromisoformat(value)
        timespec = "microseconds" if "." in value else "seconds"
        if result.utcoffset() != timedelta(0) or result.isoformat(timespec=timespec) != value:
            raise ValueError("checkpoint is not canonical UTC")
        return result
    except (TypeError, ValueError, OverflowError) as error:
        raise CreditAuditError("credit_audit_clock_invalid", "credit evidence requires a real canonical UTC checkpoint") from error


def validate_checkpoints(market, policy, *, selected_at, last_checked_at, recorded_at):
    """Replay recorded freshness, never today's time or physical-COMMIT time."""
    selected, checked, recorded = map(utc_checkpoint, (selected_at, last_checked_at, recorded_at))
    if not selected <= checked <= recorded:
        raise CreditAuditError("credit_audit_clock_regression", "credit transaction checkpoint order regressed")
    try:
        base = policy["base_policy"]
        age, skew = base["max_price_age_us"], policy["max_future_skew_us"]
        if type(age) is not int or type(skew) is not int or age < 0 or skew != 1000000:
            raise ValueError("invalid credit market clock policy")
        for point in (selected, checked, recorded):
            market.validate(now=point, max_age=timedelta(microseconds=age),
                            max_future_skew=timedelta(microseconds=skew))
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise CreditAuditError("credit_audit_market_invalid", "actual recorded credit checkpoints violate market freshness") from error
    return selected, checked, recorded


def audit_policy(exchange, connection):
    """Pin actual runtime rules to the authoritative persisted bootstrap policy."""
    from .decision_audit import DecisionAudit
    from .service import _text
    base = DecisionAudit.policy(exchange)
    base["fee_rate"] = _text(exchange.fee_rate)
    if (base["risk_mode"] != "phase1_cross" or base["catalog"] is None or base["rules"] is None
            or base["scales"] != {"USD": 8, "BTC": 8} or Decimal(base["fee_rate"]) != 0
            or base["execution_options"] != {"reserve_cache_size": 0, "market_cache_size": 0}):
        raise CreditAuditError("credit_audit_policy_unsupported", "internal credit requires zero-fee USD/BTC Cross with caches disabled")
    stored = _persisted_policy(connection)
    if base != stored["base_policy"]:
        raise CreditAuditError("credit_audit_policy_mismatch", "runtime credit rules differ from authoritative persisted policy")
    return stored


def _persisted_policy(connection):
    """Reconstruct the pinned policy from real stored bootstrap configuration."""
    from .portfolio import PortfolioRules
    from .products import ProductCatalog
    stored = {row[0]: row[1] for row in connection.execute(
        "SELECT key,value FROM uta_config WHERE key IN ('policy','risk_policy')")}
    if set(stored) != {"policy", "risk_policy"}:
        raise CreditAuditError("credit_audit_policy_missing", "authoritative trading and risk policy are required")
    policy, risk = strict_json(stored["policy"]), strict_json(stored["risk_policy"])
    _fields(policy, {"fee_rate", "usd_scale", "max_price_age_us", "order_precision"}, "stored trading policy is incomplete")
    _fields(risk, {"mode", "catalog", "rules"}, "stored portfolio policy is incomplete")
    scales = dict(connection.execute("SELECT asset,scale FROM ledger_assets"))
    if (scales != {"USD": 8, "BTC": 8} or _scalar(policy["fee_rate"]) != 0
            or type(policy["usd_scale"]) is not int or policy["usd_scale"] != 8
            or type(policy["order_precision"]) is not int or policy["order_precision"] != 8
            or type(policy["max_price_age_us"]) is not int or not 0 < policy["max_price_age_us"] <= 300000000
            or risk["mode"] != "phase1_cross"):
        raise CreditAuditError("credit_audit_policy_unsupported", "stored policy is outside the fixed internal credit scope")
    catalog = ProductCatalog.from_json(canonical(risk["catalog"]))
    rules = PortfolioRules.from_json(canonical(risk["rules"]))
    if canonical(risk["catalog"]) != catalog.to_json() or canonical(risk["rules"]) != rules.to_json():
        raise CreditAuditError("credit_audit_policy_mismatch", "stored product or risk documents are not canonical")
    base = {"format": 1, "risk_mode": "phase1_cross", "catalog": risk["catalog"], "rules": risk["rules"],
        "scales": scales, "fee_rate": policy["fee_rate"], "max_price_age_us": policy["max_price_age_us"],
        "order_precision": policy["order_precision"], "reserve_formula": "linear-adverse-loss-cumulative-fee-v1",
        "execution_options": {"reserve_cache_size": 0, "market_cache_size": 0}}
    return {"format": FORMAT, "base_policy": base, "max_future_skew_us": 1000000,
        "clock_policy": "actual exchange UTC checkpoints; no physical commit timestamp",
        "physical_commit_time_captured": False}


def verify_stored_policy(connection):
    """A load/acquire cannot accept an absent or extra dedicated risk archive."""
    verify_schema(connection)
    policy = _persisted_policy(connection)
    payload = canonical(policy)
    identity = "credit-risk-policy:"+sha256(payload.encode()).hexdigest()
    actual = [tuple(row) for row in connection.execute("SELECT policy_id,payload FROM uta_credit_risk_policies")]
    if actual != [(identity, payload)]:
        raise CreditAuditError("credit_audit_policy_missing", "actual uniquely pinned credit risk archive is absent or different")
    return {"policy_id": identity, "policy": policy}


def journal_record(connection, event_id):
    row = connection.execute("SELECT * FROM ledger_events WHERE event_id=?", (event_id,)).fetchone()
    if row is None:
        raise CreditAuditError("credit_audit_journal_missing", "actual credit journal is absent")
    return {**dict(row), "postings": [dict(item) for item in connection.execute(
        "SELECT ordinal,account,asset,units FROM ledger_postings WHERE sequence=? ORDER BY ordinal", (row["sequence"],))]}


def verify_journal(record, *, expected_event_id, expected_postings, journal_head=None):
    """Check complete actual legs and local hash link, without a global FK probe.

    In-flight deferred intent/audit/terminal obligations may still be open. Full
    ledger verification is appropriate only after those actual rows all close.
    """
    from .storage import DurableLedger
    from .credit_transition import _units
    if (type(record) is not dict or set(record) != {"sequence", "event_id", "fingerprint", "previous_hash", "event_hash", "sealed", "postings"}
            or record["event_id"] != expected_event_id or type(record["sequence"]) is not int
            or not 1 <= record["sequence"] <= 2**63-1 or type(record["sealed"]) is not int or record["sealed"] != 1
            or record["postings"] != expected_postings):
        raise CreditAuditError("credit_audit_journal_mismatch", "actual sealed credit journal or complete ordered legs differ")
    if any(type(record[field]) is not str or re.fullmatch("[0-9a-f]{64}", record[field]) is None
           for field in ("fingerprint", "previous_hash", "event_hash")):
        raise CreditAuditError("credit_audit_journal_mismatch", "credit journal digest is invalid")
    for postings in (record["postings"], expected_postings):
        if type(postings) is not list or len(postings) not in (2, 4, 7):
            raise CreditAuditError("credit_audit_journal_mismatch", "credit journal requires its complete normalized posting list")
        for ordinal, row in enumerate(postings):
            if (type(row) is not dict or set(row) != {"ordinal", "account", "asset", "units"}
                    or type(row["ordinal"]) is not int or row["ordinal"] != ordinal
                    or type(row["account"]) is not str or type(row["asset"]) is not str):
                raise CreditAuditError("credit_audit_journal_mismatch", "credit journal posting fields or ordinal types differ")
    canonical_legs = tuple((row["account"], row["asset"], _units(row["units"], signed=True)) for row in expected_postings)
    if (canonical_legs != tuple(sorted(canonical_legs))
            or len({(row[0], row[1]) for row in canonical_legs}) != len(canonical_legs)
            or any(row[2] == 0 for row in canonical_legs)):
        raise CreditAuditError("credit_audit_journal_mismatch", "credit journal legs are not normalized distinct nonzero accounts")
    if (record["fingerprint"] != DurableLedger._fingerprint(canonical_legs)
            or record["event_hash"] != DurableLedger._hash(record["sequence"], record["event_id"], record["previous_hash"], record["fingerprint"])):
        raise CreditAuditError("credit_audit_journal_mismatch", "credit journal fingerprint or hash link differs")
    if journal_head is not None:
        if (type(journal_head) is not dict or set(journal_head) != {"sequence", "event_hash"}
                or type(journal_head["sequence"]) is not int or not 0 <= journal_head["sequence"] < 2**63-1
                or type(journal_head["event_hash"]) is not str
                or re.fullmatch("[0-9a-f]{64}", journal_head["event_hash"]) is None
                or record["sequence"] != journal_head["sequence"]+1 or record["previous_hash"] != journal_head["event_hash"]):
            raise CreditAuditError("credit_audit_journal_mismatch", "credit event does not append to its actual pre-transaction head")
    return True


def _fields(value, fields, message):
    if type(value) is not dict or set(value) != fields:
        raise CreditAuditError("credit_audit_invalid", message)


def _scalar(value):
    from .models import _decimal
    from .decision_audit import _text
    try:
        if type(value) is not str or not 1 <= len(value) <= 256 or re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?", value) is None:
            raise ValueError("not a bounded decimal string")
        result = Decimal(value)
        _decimal("credit audit scalar", result)
        if _text(Fraction(result)) != value:
            raise ValueError("not a canonical decimal string")
        return result
    except (ValueError, TypeError) as error:
        raise CreditAuditError("credit_audit_invalid", "credit state monetary scalar is invalid") from error


def gross_components(account):
    """Keep positive assets, cash deficits, principal and interest separate."""
    from .decision_audit import _text
    from .credit_v2_payload_contract import ACCOUNT_FIELDS
    _fields(account, ACCOUNT_FIELDS, "credit account state is incomplete")
    if type(account["balances"]) is not dict or set(account["balances"]) != {"USD", "BTC"} or type(account["liabilities"]) is not list:
        raise CreditAuditError("credit_audit_invalid", "gross account components are outside the supported asset scope")
    positive, deficits = {}, {}
    for asset, raw in account["balances"].items():
        value = _scalar(raw)
        if value > 0: positive[asset] = raw
        elif value < 0: deficits[asset] = _text(-Fraction(value))
    principal, interest, seen = {}, {}, set()
    for row in account["liabilities"]:
        _fields(row, {"asset", "principal", "interest"}, "gross liability row is incomplete")
        if type(row["asset"]) is not str or row["asset"] not in {"USD", "BTC"} or row["asset"] in seen:
            raise CreditAuditError("credit_audit_invalid", "gross liability assets are unknown or duplicated")
        seen.add(row["asset"])
        for target, field in ((principal, "principal"), (interest, "interest")):
            value = _scalar(row[field])
            if value < 0 or row["asset"] in target:
                raise CreditAuditError("credit_audit_invalid", "gross liabilities are negative or duplicated")
            if value: target[row["asset"]] = row[field]
    if [row["asset"] for row in account["liabilities"]] != sorted(seen):
        raise CreditAuditError("credit_audit_invalid", "gross liability rows are not in their actual asset order")
    return {"assets": positive, "cash_deficits": deficits, "principal": principal, "interest": interest}


def replay_risk(account, market, policy, *, now):
    """Dedicated full credit valuation, including conservative native quote.

    This production replay uses the retained production model under matching
    code identity. Independent acceptance uses a separately authored oracle.
    It does not submit an order or read any current financial/account row.
    """
    from .credit_v2_payload_contract import ACCOUNT_FIELDS, BASE_POLICY_FIELDS, ORDER_FIELDS, POLICY_FIELDS
    from .decision_audit import _decimal, _text
    from .portfolio import LinearExposure, LoanAccount, PortfolioRules, calculate_cross_risk
    from .products import AccountMode, ProductCatalog, ProductKind
    from .reserve_kernel import ReserveInputs, calculate_reserve
    _fields(account, ACCOUNT_FIELDS, "credit account state is incomplete")
    _fields(policy, POLICY_FIELDS, "dedicated credit policy is incomplete")
    base = policy["base_policy"]
    _fields(base, BASE_POLICY_FIELDS, "base credit valuation policy is incomplete")
    if (type(policy["format"]) is not int or policy["format"] != FORMAT
            or type(policy["max_future_skew_us"]) is not int or policy["max_future_skew_us"] != 1000000
            or policy["physical_commit_time_captured"] is not False
            or policy["clock_policy"] != "actual exchange UTC checkpoints; no physical commit timestamp"
            or type(base["format"]) is not int or base["format"] != 1
            or type(base["order_precision"]) is not int or base["order_precision"] != 8
            or type(base["max_price_age_us"]) is not int or not 0 < base["max_price_age_us"] <= 300000000
            or base["reserve_formula"] != "linear-adverse-loss-cumulative-fee-v1"
            or type(base["scales"]) is not dict or any(type(value) is not int for value in base["scales"].values())
            or type(base["execution_options"]) is not dict or any(type(value) is not int for value in base["execution_options"].values())
            or type(account["version"]) is not int or not 0 <= account["version"] <= 2**63-1
            or type(account["halted"]) is not bool or base["risk_mode"] != "phase1_cross"
            or base["scales"] != {"USD": 8, "BTC": 8} or _scalar(base["fee_rate"]) != 0
            or base["execution_options"] != {"reserve_cache_size": 0, "market_cache_size": 0}):
        raise CreditAuditError("credit_audit_policy_unsupported", "credit evidence is outside the supported internal Cross policy")
    catalog = ProductCatalog.from_json(canonical(base["catalog"]))
    rules = PortfolioRules.from_json(canonical(base["rules"]))
    reserve = Fraction(0)
    seen = set()
    for order in account["orders"]:
        _fields(order, ORDER_FIELDS, "stored live order evidence is incomplete")
        if (type(order["reduce_only"]) is not int or order["reduce_only"] not in (0, 1)
                or type(order["version"]) is not int or not 0 <= order["version"] <= 2**63-1
                or any(type(order[field]) is not str for field in ("account_id", "order_id", "symbol", "created_at"))
                or order["admission_decision_id"] is not None and type(order["admission_decision_id"]) is not str
                or order["status"] not in ("OPEN", "PARTIALLY_FILLED")
                or (order["account_id"], order["order_id"]) in seen):
            raise CreditAuditError("credit_audit_invalid", "stored live order metadata is invalid or duplicated")
        seen.add((order["account_id"], order["order_id"]))
        product = catalog.require_risk_supported(order["symbol"])
        if product.kind is not ProductKind.LINEAR_PERPETUAL or product.multiplier != 1:
            raise CreditAuditError("credit_audit_policy_unsupported", "stored order has an unsupported contract")
        instrument = market.instruments[order["symbol"]]
        rate = rules.linear_margin[product.risk_tier].initial_margin_rate
        reserve += Fraction(calculate_reserve(ReserveInputs(
            quantity=_scalar(order["quantity"]), filled_quantity=_scalar(order["filled_quantity"]),
            limit_price=_scalar(order["limit_price"]), mark_price=instrument.mark_price,
            reduce_only=bool(order["reduce_only"]), initial_margin_rate=rate,
            fee_notional=_scalar(order["fee_notional"]), charged_fee=_scalar(order["charged_fee"]),
            fee_rate=_scalar(base["fee_rate"]), usd_scale=base["scales"]["USD"])))
    gross = gross_components(account)
    position_map = {}
    for symbol, row in account["positions"].items():
        _fields(row, {"quantity", "cost_basis"}, "stored position is incomplete")
        position_map[symbol] = LinearExposure(symbol, _scalar(row["quantity"]), _scalar(row["cost_basis"]))
    loan = LoanAccount(gross_assets={key: _scalar(raw) for key, raw in gross["assets"].items()},
        cash_deficits={key: _scalar(raw) for key, raw in gross["cash_deficits"].items()},
        principal={key: _scalar(raw) for key, raw in gross["principal"].items()},
        interest={key: _scalar(raw) for key, raw in gross["interest"].items()},
        frozen_assets={key: _scalar(raw) for key, raw in account["frozen_assets"].items()},
        positions=position_map, order_margin=_decimal(reserve), mode=AccountMode.CROSS)
    calculated = calculate_cross_risk(loan, market, catalog, rules, now=now,
        max_age=timedelta(microseconds=base["max_price_age_us"]))
    values = {name: _text(Fraction(getattr(calculated, name))) for name in (
        "accounting_equity", "collateral_value", "risk_equity", "loan_value", "principal_value",
        "interest_value", "cash_deficit_value", "debt_value", "unrealized_pnl", "frozen_value",
        "initial_margin", "maintenance_margin", "available_margin")}
    equity, mm = Fraction(calculated.risk_equity), Fraction(calculated.maintenance_margin)
    with localcontext(Context(prec=34, rounding=ROUND_HALF_EVEN)):
        ratio = _text(Decimal(equity.numerator*mm.denominator) / Decimal(equity.denominator*mm.numerator)) if mm else None
    values.update(account_version=account["version"], equity=values["risk_equity"], open_order_margin=_text(reserve),
        margin_ratio=ratio, market_version=market.version, observed_at=market.observed_at.isoformat(),
        market_id=calculated.market_id, borrowable={asset: _text(Fraction(value)) for asset, value in calculated.borrowable.items()},
        status=calculated.status, risk_mode="phase1_cross", rule_id=rules.rule_id,
        rule_version=rules.version, catalog_version=catalog.version)
    return values


def _after_borrow_account(before, asset, amount, credit_after):
    from .decision_audit import _text
    after = deepcopy(before)
    after["version"] = credit_after["version"]
    after["balances"][asset] = _text(Fraction(_scalar(before["balances"][asset]))+Fraction(amount))
    rows = {row["asset"]: dict(row) for row in before["liabilities"]}
    rows[asset] = {"asset": asset,
        "principal": _text(Fraction(int(credit_after["principal_units"]), 10**8)),
        "interest": _text(Fraction(int(credit_after["interest_units"]), 10**8))}
    after["liabilities"] = [rows[key] for key in sorted(rows)]
    return after


def runtime_manifest():
    """Require the real loaded complete internal engine, not presence flags."""
    from .credit_artifact import credit_artifact_id, credit_code_artifact
    manifest = credit_code_artifact()
    required = {
        "uta.credit_audit_v2.CreditAuditV2.begin_borrow",
        "uta.credit_audit_v2.CreditAuditV2.complete_borrow",
        "uta.credit_audit_v2.CreditAuditV2.verify_staged_borrow",
        "uta.credit_audit_v2_replay.replay_bundle",
        "uta.credit_transition.calculate_borrow_transition",
        "uta.credit_native_v2.assert_operation_context",
        "uta.credit_native_v2.operation_scope",
        "uta.credit_native_v2.synthetic_intake_scope",
        "uta.credit_native_v2.rejection_scope",
        "uta.credit_native_v2.metadata_scope",
        "uta.credit_native_v2.install_internal_credit_v2",
        "uta.credit_native_v2.acquire_credit_v2",
        "uta.credit_fifo_v2.verify_existing_queue",
        "uta.credit_fifo_v2.InternalCreditFIFO.enqueue_borrow",
        "uta.credit_fifo_v2.InternalCreditFIFO.enqueue_repay",
        "uta.credit_fifo_v2.InternalCreditFIFO.process_one",
        "uta.credit_fifo_v2.InternalCreditFIFO.status",
    }
    if not required <= set(manifest["loaded_credit_engine"]):
        raise CreditAuditError("credit_audit_runtime_incomplete", "complete actual internal credit code dependencies are absent")
    return credit_artifact_id(manifest), manifest


def verify_schema(connection):
    """Exact declared audit inventory, without schema creation or repair."""
    expected = {}
    for name, definition in OBJECT_SQL.items():
        if name in TABLE_SQL:
            expected[name] = ("table", name, definition)
        elif name in INDEX_SQL:
            expected[name] = ("index", definition.split(" ON ", 1)[1].split("(", 1)[0], definition)
        else:
            expected[name] = ("trigger", TRIGGER_SQL[name][0], definition)
    for table in TABLE_SQL:
        for row in connection.execute(f"PRAGMA index_list({table})"):
            if row[1].startswith("sqlite_autoindex_"):
                expected[row[1]] = ("index", table, None)
    # Native writer guards on these tables belong to the separately verified
    # native inventory. This helper verifies this module's compiled objects.
    actual = {row[0]: tuple(row)[1:] for row in connection.execute(
        "SELECT name,type,tbl_name,sql FROM sqlite_master WHERE name LIKE 'credit_audit_v2_%' "
        "OR name LIKE 'uta_credit_%' OR name LIKE 'sqlite_autoindex_uta_credit_%'")}
    if actual != expected:
        raise CreditAuditError("credit_audit_schema_corrupt", "credit audit objects or definitions differ; automatic repair is forbidden")


@dataclass(frozen=True)
class BorrowCapture:
    """Immutable observation data; actual native SQL must still bind it."""
    account_id: str
    command_id: str
    asset: str
    amount: str
    payload: str


class CreditAuditV2:
    """Same-connection actual capture and dedicated archive-only replay."""

    def __init__(self, exchange, credit):
        from .credit import CreditService
        from .service import ExchangeService
        if type(credit) is not CreditService or type(exchange) is not ExchangeService or credit.exchange is not exchange:
            raise CreditAuditError("credit_audit_context_invalid", "dedicated credit audit requires its actual exchange and credit service")
        self.exchange, self.credit, self.database = exchange, credit, exchange.database

    def runtime_evidence(self, connection):
        """Real code/configuration evidence; no records, lease or role created."""
        verify_schema(connection)
        artifact_id, manifest = runtime_manifest()
        policy = audit_policy(self.exchange, connection)
        return {"artifact_id": artifact_id, "manifest": manifest,
            "policy_id": "credit-risk-policy:"+sha256(canonical(policy).encode()).hexdigest(), "policy": policy}

    def _require_runtime_archives(self, connection):
        evidence = self.runtime_evidence(connection)
        artifacts = [tuple(row) for row in connection.execute("SELECT artifact_id,manifest FROM uta_credit_code_artifacts")]
        if artifacts != [(evidence["artifact_id"], canonical(evidence["manifest"]))]:
            raise CreditAuditError("credit_audit_artifact_missing", "actual uniquely pinned credit code archive differs")
        if verify_stored_policy(connection) != {"policy_id": evidence["policy_id"], "policy": evidence["policy"]}:
            raise CreditAuditError("credit_audit_policy_missing", "actual uniquely pinned credit risk archive differs")
        return evidence

    def _context(self, connection, account_id, command_id, asset, amount):
        from .credit_native_v2 import assert_operation_context
        return assert_operation_context(self.credit, connection, command_id=command_id,
            account_id=account_id, asset=asset, amount=amount, operation_kind="BORROW")

    @staticmethod
    def _source_row(connection, command_id):
        row = connection.execute("SELECT * FROM credit_v2_sources WHERE command_id=?", (command_id,)).fetchone()
        if row is None:
            raise CreditAuditError("credit_audit_source_missing", "actual original source is absent")
        return dict(row)

    @staticmethod
    def _pool_funding(connection):
        pairs = []
        for row in connection.execute("SELECT * FROM credit_commands WHERE scope='pool' AND kind='pool_funded' AND asset='BTC' ORDER BY command_id"):
            pairs.append({"command": dict(row), "journal": journal_record(connection, row["journal_event_id"])})
        return pairs

    @staticmethod
    def _capability(connection, view):
        from .credit_native_v2 import validate_envelope
        row = connection.execute("SELECT capability_id,payload FROM writer_fence_credit_v2_capability WHERE singleton=1").fetchone()
        if row is None:
            raise CreditAuditError("credit_audit_context_invalid", "actual internal capability marker is absent")
        value = validate_envelope(row[1], expected_authority_id=view.static_descriptor.authority_id,
            expected_asset_scales={"USD": 8, "BTC": 8})
        if row[0] != view.capability_id or value.capability_id != view.capability_id or value.static_descriptor != view.static_descriptor:
            raise CreditAuditError("credit_audit_context_invalid", "actual capability/static declaration differs from native operation")
        return value

    def begin_borrow(self, connection, account_id, command_id, asset, amount):
        """Capture actual staged native prestate; no transferable success flag."""
        from .decision_audit import DecisionAudit
        from .credit_v2_payload_contract import PRE_STATE_FIELDS
        view = self._context(connection, account_id, command_id, asset, amount)
        evidence = self._require_runtime_archives(connection)
        capability = self._capability(connection, view)
        if capability.artifact_id != evidence["artifact_id"]:
            raise CreditAuditError("credit_audit_engine_mismatch", "actual code differs from the immutable internal capability")
        self.exchange._require_exposure_allowed(connection, account_id)
        pre = strict_json(view.pre_state_payload)
        _fields(pre, PRE_STATE_FIELDS, "actual native prestate is incomplete")
        if sha256(view.pre_state_payload.encode()).hexdigest() != view.pre_state_hash:
            raise CreditAuditError("credit_audit_state_mismatch", "actual staged prestate content hash differs")
        market = self.exchange._market(connection)
        sid = DecisionAudit.market_ref(connection, market)
        snapshot, limits = read_credit_snapshot(self.exchange, self.credit, connection, account_id, asset)
        row = connection.execute("SELECT sequence,event_hash FROM ledger_events ORDER BY sequence DESC LIMIT 1").fetchone()
        head = dict(row) if row else {"sequence": 0, "event_hash": "0"*64}
        current = {"account": self.exchange._audit_state(connection, account_id), "credit": snapshot,
            "limits": limits, "market_snapshot_id": sid, "risk": self.exchange._risk(connection, account_id, market),
            "quote_units": str(self.credit._codec._units(asset, Decimal(pre["risk"]["borrowable"][asset]))),
            "quantity_step_units": str(self.credit._codec._units(asset, self.exchange.portfolio_rules.borrow_limits[asset].quantity_step)),
            "selected_at": view.selected_at, "journal_head": head}
        if current != pre or sid != view.market_snapshot_id:
            raise CreditAuditError("credit_audit_state_mismatch", "actual native prestate differs from same-transaction financial rows")
        selected = utc_checkpoint(view.selected_at)
        market.validate(now=selected, max_age=self.exchange.max_price_age, max_future_skew=timedelta(seconds=1))
        if selected > self.exchange._now():
            raise CreditAuditError("credit_audit_clock_regression", "actual exchange clock regressed after native selection")
        if replay_risk(pre["account"], market, evidence["policy"], now=selected) != pre["risk"]:
            raise CreditAuditError("credit_audit_risk_mismatch", "actual native risk/quote does not replay before borrowing")
        source = self._source_row(connection, command_id)
        if source["source_id"] != view.source_id or source["payload"] != view.source_payload:
            raise CreditAuditError("credit_audit_source_mismatch", "actual original source differs from native operation")
        captured = {"pre_state": pre, "capability_payload": capability.canonical_payload,
            "artifact_id": evidence["artifact_id"], "policy_id": evidence["policy_id"],
            "source": source, "pool_funding": self._pool_funding(connection)}
        return BorrowCapture(account_id, command_id, asset, view.amount, canonical(captured))

    @staticmethod
    def _archive(connection, table, identity, payload):
        allowed = {"uta_credit_code_artifacts": ("artifact_id", "manifest"),
                   "uta_credit_risk_policies": ("policy_id", "payload")}
        if table not in allowed:
            raise CreditAuditError("credit_audit_invalid", "unknown compiled credit archive")
        key, body = allowed[table]
        row = connection.execute(f"SELECT {body} FROM {table} WHERE {key}=?", (identity,)).fetchone()
        if row is None:
            connection.execute(f"INSERT INTO {table} VALUES(?,?)", (identity, payload))
        elif row[0] != payload:
            raise CreditAuditError("credit_audit_content_conflict", "existing credit archive has different content")

    def complete_borrow(self, connection, capture, receipt):
        """Write actual complete content-addressed decision before credit closing."""
        from .credit_audit_v2_replay import content_id, replay_bundle
        from .credit_transition import calculate_borrow_transition, compare_borrow_transition
        from .decision_audit import DecisionAudit
        if type(capture) is not BorrowCapture:
            raise CreditAuditError("credit_audit_context_invalid", "original borrow capture is required")
        view = self._context(connection, capture.account_id, capture.command_id, capture.asset, Decimal(capture.amount))
        captured = strict_json(capture.payload)
        _fields(captured, {"pre_state", "capability_payload", "artifact_id", "policy_id", "source", "pool_funding"}, "borrow capture data is incomplete")
        if canonical(captured["pre_state"]) != view.pre_state_payload:
            raise CreditAuditError("credit_audit_state_mismatch", "borrow capture is not the actual original staged prestate")
        evidence = self._require_runtime_archives(connection)
        capability = self._capability(connection, view)
        if (captured["capability_payload"] != capability.canonical_payload
                or captured["artifact_id"] != evidence["artifact_id"] or captured["policy_id"] != evidence["policy_id"]
                or capability.artifact_id != evidence["artifact_id"]
                or captured["source"] != self._source_row(connection, capture.command_id)
                or captured["pool_funding"] != self._pool_funding(connection)):
            raise CreditAuditError("credit_audit_content_conflict", "actual source, funding, rules or code changed during borrowing")
        pre = captured["pre_state"]
        market = self.exchange._market(connection)
        sid = DecisionAudit.market_ref(connection, market)
        if sid != view.market_snapshot_id:
            raise CreditAuditError("credit_audit_market_mismatch", "borrowing changed its actual market snapshot")
        after_credit, after_limits = read_credit_snapshot(self.exchange, self.credit, connection,
            capture.account_id, capture.asset, require_increment=False)
        post = {"account": self.exchange._audit_state(connection, capture.account_id), "credit": after_credit,
            "limits": after_limits, "risk": self.exchange._risk(connection, capture.account_id, market)}
        expected = calculate_borrow_transition(descriptor=view.static_descriptor, account_id=capture.account_id,
            asset=capture.asset, amount_units=str(view.amount_units), before=pre["credit"], limits=pre["limits"],
            quote_units=pre["quote_units"], quantity_step_units=pre["quantity_step_units"])
        journal = journal_record(connection, view.journal_id)
        compare_borrow_transition(expected, after=after_credit, postings=journal["postings"])
        if post["account"] != _after_borrow_account(pre["account"], capture.asset, Decimal(capture.amount), expected.wire()["after"]) or after_limits != pre["limits"]:
            raise CreditAuditError("credit_audit_state_mismatch", "borrow changed unrelated actual account state or limits")
        last_checked_at = self.exchange._now().isoformat()
        market.validate(now=utc_checkpoint(last_checked_at), max_age=self.exchange.max_price_age, max_future_skew=timedelta(seconds=1))
        recorded_at = self.exchange._now().isoformat()
        validate_checkpoints(market, evidence["policy"], selected_at=view.selected_at,
            last_checked_at=last_checked_at, recorded_at=recorded_at)
        payload = {"format": 2, "kind": "CREDIT_BORROWED", "operation_id": borrow_operation_id(capture.account_id, capture.command_id),
            "capability_id": capability.capability_id, "capability_payload": capability.canonical_payload,
            "account_id": capture.account_id, "command_id": capture.command_id, "asset": capture.asset,
            "amount": capture.amount, "amount_units": str(view.amount_units), "payload_hash": view.payload_hash,
            "source_id": view.source_id, "source": captured["source"], "descriptor_id": view.static_descriptor.descriptor_id,
            "static_budget": view.static_descriptor.canonical_payload, "allocation_id": view.allocation_id,
            "market_snapshot_id": sid, "artifact_id": evidence["artifact_id"], "policy_id": evidence["policy_id"],
            "pre_state": pre, "post_state": post, "gross_components": {"before": gross_components(pre["account"]), "after": gross_components(post["account"])},
            "pool_funding": captured["pool_funding"], "journal": journal, "receipt": receipt,
            "selected_at": view.selected_at, "last_checked_at": last_checked_at, "recorded_at": recorded_at, "physical_commit_at": None}
        row = {"decision_id": content_id(payload), "operation_id": payload["operation_id"], "format": 2,
            "kind": "CREDIT_BORROWED", "account_id": capture.account_id, "command_id": capture.command_id,
            "inbox_kind": "BORROW", "terminal_state": "SUCCEEDED", "asset": capture.asset, "amount": capture.amount,
            "payload_hash": view.payload_hash, "source_id": view.source_id, "market_snapshot_id": sid,
            "artifact_id": evidence["artifact_id"], "policy_id": evidence["policy_id"], "descriptor_id": view.static_descriptor.descriptor_id,
            "allocation_id": view.allocation_id, "journal_id": view.journal_id, "journal_sealed": 1,
            "pre_version": pre["account"]["version"], "post_version": post["account"]["version"],
            "selected_at": view.selected_at, "last_checked_at": last_checked_at, "recorded_at": recorded_at, "payload": canonical(payload)}
        market_row = connection.execute("SELECT * FROM uta_market_history WHERE snapshot_id=?", (sid,)).fetchone()
        if market_row is None:
            raise CreditAuditError("credit_audit_market_missing", "actual complete original market history is absent")
        bundle = {"format": 2, "decision": row, "market": dict(market_row),
            "artifact": {"artifact_id": evidence["artifact_id"], "manifest": canonical(evidence["manifest"])},
            "policy": {"policy_id": evidence["policy_id"], "payload": canonical(evidence["policy"])}}
        # This validates the candidate derived from actual SQL. It is not a
        # COMMIT claim; the native receipt/terminal obligations still follow.
        replay_bundle(bundle)
        self._archive(connection, "uta_credit_code_artifacts", evidence["artifact_id"], canonical(evidence["manifest"]))
        self._archive(connection, "uta_credit_risk_policies", evidence["policy_id"], canonical(evidence["policy"]))
        connection.execute("INSERT INTO uta_credit_decisions("+",".join(row)+") VALUES("+",".join("?" for _ in row)+")", tuple(row.values()))
        return row["decision_id"]

    @staticmethod
    def _bundle(connection, row):
        def required(table, column, identity):
            found = connection.execute(f"SELECT * FROM {table} WHERE {column}=?", (identity,)).fetchone()
            if found is None:
                raise CreditAuditError("credit_audit_archive_missing", "complete original credit archive is absent")
            return dict(found)
        return {"format": 2, "decision": dict(row),
            "market": required("uta_market_history", "snapshot_id", row["market_snapshot_id"]),
            "artifact": required("uta_credit_code_artifacts", "artifact_id", row["artifact_id"]),
            "policy": required("uta_credit_risk_policies", "policy_id", row["policy_id"])}

    def verify_staged_borrow(self, connection, command_id, *, terminal_required=True):
        """Re-read actual SQL after effects, including scope-exited commit checks."""
        from .credit_audit_v2_replay import replay_bundle
        from .writer_fence import _assert_financial_joinable
        if connection is None or type(terminal_required) is not bool:
            raise CreditAuditError("credit_audit_context_invalid", "staged credit verification requires an actual financial connection")
        with self.database._using(connection):
            _assert_financial_joinable(self.database, connection)
            identity = connection.execute("SELECT account_id FROM uta_command_inbox WHERE command_id=?", (command_id,)).fetchone()
            if identity is None:
                raise CreditAuditError("credit_audit_source_missing", "actual original inbox is absent")
            row = connection.execute("SELECT * FROM uta_credit_decisions WHERE operation_id=?",
                (borrow_operation_id(identity[0], command_id),)).fetchone()
            if row is None:
                raise CreditAuditError("credit_audit_decision_missing", "actual staged credit decision is absent")
            bundle = self._bundle(connection, row)
            replayed = replay_bundle(bundle)
            payload = strict_json(row["payload"])
            self._require_runtime_archives(connection)
            marker = connection.execute("SELECT capability_id,payload FROM writer_fence_credit_v2_capability WHERE singleton=1").fetchone()
            columns = ("account_id", "operation_kind", "asset", "amount", "amount_units", "payload_hash", "source_id",
                "authority_id", "allocation_id", "descriptor_id", "journal_id", "pre_state_payload", "pre_state_hash",
                "operation_id", "decision_kind", "market_dependency", "market_snapshot_id", "selected_at", "pre_version", "post_version")
            intent = connection.execute("SELECT "+",".join(columns)+" FROM credit_v2_intents WHERE command_id=?", (command_id,)).fetchone()
            expected_intent = (row["account_id"], "BORROW", row["asset"], row["amount"], payload["amount_units"],
                row["payload_hash"], row["source_id"], payload["source"]["authority_id"], row["allocation_id"], row["descriptor_id"],
                row["journal_id"], canonical(payload["pre_state"]), sha256(canonical(payload["pre_state"]).encode()).hexdigest(),
                row["operation_id"], "CREDIT_BORROWED", "SID", row["market_snapshot_id"], row["selected_at"], row["pre_version"], row["post_version"])
            if (marker is None or tuple(marker) != (payload["capability_id"], payload["capability_payload"])
                    or intent is None or tuple(intent) != expected_intent):
                raise CreditAuditError("credit_audit_context_invalid", "actual immutable capability and staged intent differ from the dedicated decision")
            after_credit, limits = read_credit_snapshot(self.exchange, self.credit, connection, row["account_id"], row["asset"], require_increment=False)
            if (payload["post_state"]["account"] != self.exchange._audit_state(connection, row["account_id"])
                    or payload["post_state"]["credit"] != after_credit or payload["post_state"]["limits"] != limits
                    or payload["source"] != self._source_row(connection, command_id)
                    or payload["pool_funding"] != self._pool_funding(connection)):
                raise CreditAuditError("credit_audit_state_mismatch", "actual staged financial rows differ from the complete credit decision")
            if terminal_required:
                credit_row = connection.execute("SELECT result,journal_event_id FROM credit_commands WHERE scope=? AND command_id=?",
                    ("account:"+row["account_id"], command_id)).fetchone()
                inbox = connection.execute("SELECT account_id,kind,state,result FROM uta_command_inbox WHERE command_id=?", (command_id,)).fetchone()
                if (credit_row is None or inbox is None or credit_row[0] != canonical(payload["receipt"])
                        or credit_row[1] != row["journal_id"] or tuple(inbox) != (row["account_id"], "BORROW", "SUCCEEDED", credit_row[0])):
                    raise CreditAuditError("credit_audit_terminal_mismatch", "actual original credit and durable terminal receipts do not close")
            now = self.exchange._now()
            if now < utc_checkpoint(payload["recorded_at"]):
                raise CreditAuditError("credit_audit_clock_regression", "actual pre-COMMIT clock regressed after credit evidence")
            market = self.exchange._market(connection)
            from .decision_audit import DecisionAudit
            if DecisionAudit.market_ref(connection, market) != payload["market_snapshot_id"]:
                raise CreditAuditError("credit_audit_market_mismatch", "actual pre-COMMIT market changed after credit evidence")
            market.validate(now=now, max_age=self.exchange.max_price_age, max_future_skew=timedelta(seconds=1))
            if self._require_runtime_archives(connection)["policy_id"] != payload["policy_id"]:
                raise CreditAuditError("credit_audit_policy_mismatch", "actual pre-COMMIT credit rules changed")
            return {"decision_id": row["decision_id"], "decision": dict(row), "replay": replayed}

    def replay(self, decision_id):
        from .credit_audit_v2_replay import replay_bundle
        with self.database.read_transaction() as connection:
            verify_schema(connection)
            row = connection.execute("SELECT * FROM uta_credit_decisions WHERE decision_id=?", (decision_id,)).fetchone()
            if row is None:
                raise CreditAuditError("credit_audit_not_found", "original credit decision is unavailable")
            bundle = self._bundle(connection, row)
        return replay_bundle(bundle)
