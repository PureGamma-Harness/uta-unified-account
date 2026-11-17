"""Dedicated internal synthetic credit audit contract, never an activation gate.

Schema definitions are consumed by the future fresh native-v2 installer. Merely
importing this module does not install schema, grant ownership or enable credit.
Format1 NATIVE_PREPARED is not upgraded. Capture/replay and positive dispatch are
separate implementation slices; no incomplete record is a valid credit audit.
"""
from datetime import datetime, timedelta
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
    if (base["risk_mode"] != "phase1_cross" or base["catalog"] is None or base["rules"] is None
            or base["scales"] != {"USD": 8, "BTC": 8} or Decimal(base["fee_rate"]) != 0
            or base["execution_options"] != {"reserve_cache_size": 0, "market_cache_size": 0}):
        raise CreditAuditError("credit_audit_policy_unsupported", "internal credit requires zero-fee USD/BTC Cross with caches disabled")
    actual = {row[0]: row[1] for row in connection.execute(
        "SELECT key,value FROM uta_config WHERE key IN ('policy','risk_policy')")}
    expected_policy = {"fee_rate": _text(exchange.fee_rate), "usd_scale": exchange.scales["USD"],
        "max_price_age_us": base["max_price_age_us"], "order_precision": base["order_precision"]}
    expected_risk = {"mode": "phase1_cross", "catalog": base["catalog"], "rules": base["rules"]}
    if actual != {"policy": canonical(expected_policy), "risk_policy": canonical(expected_risk)}:
        raise CreditAuditError("credit_audit_policy_mismatch", "runtime credit rules differ from authoritative persisted policy")
    return {"format": FORMAT, "base_policy": base, "max_future_skew_us": 1000000,
        "clock_policy": "actual exchange UTC checkpoints; no physical commit timestamp",
        "physical_commit_time_captured": False}


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
