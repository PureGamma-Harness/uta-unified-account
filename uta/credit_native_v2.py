"""Compiled contract for a future fresh internal synthetic credit authority.

This catalog is not an installer or an authorization capability. Writer fencing
recognizes its reserved namespace but refuses incomplete capabilities. There is
no positive operation context,
activation, ownership, intake, HTTP or CLI entry point in this schema slice.
Format1 NATIVE_PREPARED is never upgraded. Actual primitive enforcement and
independent positive-chain acceptance must precede any internal execution.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
import re
import sqlite3
import importlib
from threading import get_ident
from types import MappingProxyType

from .credit_policy import validate_native_descriptor
from .storage import StorageError


FORMAT = 2
STAGE = "SYNTHETIC_INTERNAL"
MARKER_NAME = "writer_fence_credit_v2_capability"
MARKER_SQL = ("CREATE TABLE writer_fence_credit_v2_capability("
    "singleton INTEGER PRIMARY KEY CHECK(singleton=1),"
    "format INTEGER NOT NULL CHECK(typeof(format)='integer' AND format=2),"
    "state TEXT NOT NULL CHECK(state='SYNTHETIC_INTERNAL'),"
    "capability_id TEXT NOT NULL,payload TEXT NOT NULL)")

# No CAST or SQLite REAL arithmetic is used for 38-digit money. These checks
# describe canonical storage only; actual financial meaning still needs the
# typed native context, independent transition and final staged-row verifier.
_UNSIGNED = "({0}='0' OR (length({0}) BETWEEN 1 AND 38 AND {0} GLOB '[1-9]*' AND {0} NOT GLOB '*[^0-9]*'))"
_SIGNED = "({0}='0' OR (length({0}) BETWEEN 1 AND 38 AND {0} GLOB '[1-9]*' AND {0} NOT GLOB '*[^0-9]*') OR ({0} LIKE '-%' AND length(substr({0},2)) BETWEEN 1 AND 38 AND substr({0},2) GLOB '[1-9]*' AND substr({0},2) NOT GLOB '*[^0-9]*'))"


def _units_column(name, *, signed=False, positive=False):
    check = (_SIGNED if signed else _UNSIGNED).format(name)
    return (name + " TEXT NOT NULL CHECK(typeof(" + name + ")='text' AND " + check
            + (" AND " + name + "!='0'" if positive else "") + ")")


TABLE_SQL = MappingProxyType({
    "credit_v2_config": """CREATE TABLE credit_v2_config(
      singleton INTEGER PRIMARY KEY CHECK(singleton=1),
      format INTEGER NOT NULL CHECK(typeof(format)='integer' AND format=2),
      capability_id TEXT NOT NULL,descriptor_id TEXT NOT NULL,authority_id TEXT NOT NULL,
      artifact_id TEXT NOT NULL REFERENCES uta_credit_code_artifacts(artifact_id),
      opening_ledger_sequence INTEGER NOT NULL CHECK(typeof(opening_ledger_sequence)='integer' AND opening_ledger_sequence>=0),
      opening_credit_count INTEGER NOT NULL CHECK(typeof(opening_credit_count)='integer' AND opening_credit_count>=0),
      opening_payload TEXT NOT NULL,payload TEXT NOT NULL)""",
    "credit_v2_allocations": """CREATE TABLE credit_v2_allocations(
      allocation_id TEXT PRIMARY KEY NOT NULL,descriptor_id TEXT NOT NULL,certificate_id TEXT NOT NULL,
      authority_id TEXT NOT NULL,shard INTEGER NOT NULL CHECK(typeof(shard)='integer' AND shard>=0 AND shard<256),
      asset TEXT NOT NULL CHECK(asset='BTC'),scale INTEGER NOT NULL CHECK(typeof(scale)='integer' AND scale=8),
      """ + _units_column("limit_units") + ",UNIQUE(allocation_id,authority_id,asset,descriptor_id))",
    "credit_v2_sources": """CREATE TABLE credit_v2_sources(
      command_id TEXT PRIMARY KEY NOT NULL,source_id TEXT NOT NULL UNIQUE,
      account_id TEXT NOT NULL REFERENCES uta_accounts(account_id),
      kind TEXT NOT NULL CHECK(kind IN ('BORROW','REPAY')),
      payload_hash TEXT NOT NULL,source_kind TEXT NOT NULL CHECK(source_kind='synthetic_local'),
      actor_id TEXT NOT NULL,source_reference TEXT NOT NULL UNIQUE,authority_id TEXT NOT NULL,
      command_payload TEXT NOT NULL,payload TEXT NOT NULL,
      UNIQUE(command_id,source_id,account_id,kind,payload_hash,authority_id),
      FOREIGN KEY(command_id,account_id,kind,command_payload)
        REFERENCES uta_command_inbox(command_id,account_id,kind,payload) DEFERRABLE INITIALLY DEFERRED)""",
    "credit_v2_intents": """CREATE TABLE credit_v2_intents(
      command_id TEXT PRIMARY KEY NOT NULL,account_id TEXT NOT NULL REFERENCES uta_accounts(account_id),
      scope TEXT NOT NULL CHECK(scope='account:'||account_id),
      operation_kind TEXT NOT NULL CHECK(operation_kind IN ('BORROW','REPAY')),
      inbox_kind TEXT NOT NULL,credit_kind TEXT NOT NULL,asset TEXT NOT NULL CHECK(asset='BTC'),
      amount TEXT NOT NULL,""" + _units_column("amount_units", positive=True) + """,
      payload_hash TEXT NOT NULL,source_id TEXT NOT NULL,authority_id TEXT NOT NULL,
      allocation_id TEXT NOT NULL,descriptor_id TEXT NOT NULL,intent_digest TEXT NOT NULL,journal_id TEXT NOT NULL UNIQUE,
      pre_state_payload TEXT NOT NULL,pre_state_hash TEXT NOT NULL,isolation_payload TEXT NOT NULL,isolation_hash TEXT NOT NULL,
      journal_sealed INTEGER NOT NULL CHECK(typeof(journal_sealed)='integer' AND journal_sealed=1),
      terminal_state TEXT NOT NULL CHECK(terminal_state='SUCCEEDED'),
      operation_id TEXT UNIQUE,decision_kind TEXT,market_dependency TEXT NOT NULL,market_snapshot_id TEXT,selected_at TEXT,
      expected_postings INTEGER NOT NULL CHECK(typeof(expected_postings)='integer' AND expected_postings IN (4,7)),
      """ + ",".join(_units_column(name) for name in
        ("old_principal_units", "old_interest_units", "new_principal_units", "new_interest_units")) + """,
      pre_version INTEGER NOT NULL CHECK(typeof(pre_version)='integer' AND pre_version>=0 AND pre_version<9223372036854775807),
      post_version INTEGER NOT NULL CHECK(typeof(post_version)='integer' AND post_version=pre_version+1),
      CHECK((operation_kind='BORROW' AND inbox_kind='BORROW' AND credit_kind='borrowed' AND expected_postings=4
        AND operation_id IS NOT NULL AND decision_kind IS NOT NULL AND decision_kind='CREDIT_BORROWED'
        AND market_dependency='SID' AND market_snapshot_id IS NOT NULL AND selected_at IS NOT NULL)
        OR(operation_kind='REPAY' AND inbox_kind='REPAY' AND credit_kind='repaid'
        AND operation_id IS NULL AND decision_kind IS NULL AND market_dependency='NONE' AND market_snapshot_id IS NULL AND selected_at IS NULL)),
      FOREIGN KEY(command_id,account_id,inbox_kind,terminal_state)
        REFERENCES uta_command_inbox(command_id,account_id,kind,state) DEFERRABLE INITIALLY DEFERRED,
      FOREIGN KEY(scope,command_id,credit_kind,asset,amount,journal_id)
        REFERENCES credit_commands(scope,command_id,kind,asset,amount,journal_event_id) DEFERRABLE INITIALLY DEFERRED,
      FOREIGN KEY(operation_id,decision_kind,account_id,command_id,journal_id)
        REFERENCES uta_credit_decisions(operation_id,kind,account_id,command_id,journal_id) DEFERRABLE INITIALLY DEFERRED,
      FOREIGN KEY(journal_id,journal_sealed)
        REFERENCES ledger_events(event_id,sealed) DEFERRABLE INITIALLY DEFERRED,
      FOREIGN KEY(allocation_id,authority_id,asset,descriptor_id)
        REFERENCES credit_v2_allocations(allocation_id,authority_id,asset,descriptor_id) DEFERRABLE INITIALLY DEFERRED,
      FOREIGN KEY(command_id,source_id,account_id,inbox_kind,payload_hash,authority_id)
        REFERENCES credit_v2_sources(command_id,source_id,account_id,kind,payload_hash,authority_id) DEFERRABLE INITIALLY DEFERRED,
      FOREIGN KEY(market_snapshot_id) REFERENCES uta_market_history(snapshot_id) DEFERRABLE INITIALLY DEFERRED)""",
    "credit_v2_expected_postings": """CREATE TABLE credit_v2_expected_postings(
      command_id TEXT NOT NULL REFERENCES credit_v2_intents(command_id) DEFERRABLE INITIALLY DEFERRED,
      ordinal INTEGER NOT NULL CHECK(typeof(ordinal)='integer' AND ordinal>=0 AND ordinal<7),
      account TEXT NOT NULL,asset TEXT NOT NULL CHECK(asset='BTC'),""" + _units_column("units", signed=True) + ",PRIMARY KEY(command_id,ordinal))",
    "credit_v2_legacy_commands": """CREATE TABLE credit_v2_legacy_commands(
      scope TEXT NOT NULL,command_id TEXT NOT NULL,kind TEXT NOT NULL,asset TEXT NOT NULL,
      amount TEXT NOT NULL,journal_id TEXT NOT NULL,result_hash TEXT NOT NULL,PRIMARY KEY(scope,command_id))""",
})

INDEX_SQL = MappingProxyType({
    "credit_v2_inbox_identity_parent": "CREATE UNIQUE INDEX credit_v2_inbox_identity_parent ON uta_command_inbox(command_id,account_id,kind,payload)",
    "credit_v2_command_parent": "CREATE UNIQUE INDEX credit_v2_command_parent ON credit_commands(scope,command_id,kind,asset,amount,journal_event_id)",
})

_PRIMARY_KEYS = MappingProxyType({
    "credit_v2_config": ("singleton",), "credit_v2_allocations": ("allocation_id",),
    "credit_v2_sources": ("command_id",), "credit_v2_intents": ("command_id",),
    "credit_v2_expected_postings": ("command_id", "ordinal"),
    "credit_v2_legacy_commands": ("scope", "command_id"),
})
_REPLACE_IDENTITIES = MappingProxyType({
    **{table: (keys,) for table, keys in _PRIMARY_KEYS.items()},
    "credit_v2_sources": (("command_id",), ("source_id",), ("source_reference",)),
    "credit_v2_intents": (("command_id",), ("journal_id",), ("operation_id",)),
})


def _immutable_definitions():
    result = {}
    for table, keys in _PRIMARY_KEYS.items():
        for action in ("UPDATE", "DELETE"):
            name = table + "_no_" + action.lower()
            result[name] = (table, f"CREATE TRIGGER {name} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'credit v2 history is immutable'); END")
        name = table + "_no_replace"
        # REPLACE can conflict on another UNIQUE key with a different PK. The
        # default recursive_triggers=OFF does not run DELETE triggers for that
        # implicit deletion, so protect every independent unique identity.
        predicate = " OR ".join("(" + " AND ".join(key + "=NEW." + key for key in identity) + ")"
                                for identity in _REPLACE_IDENTITIES[table])
        result[name] = (table, f"CREATE TRIGGER {name} BEFORE INSERT ON {table} WHEN EXISTS(SELECT 1 FROM {table} WHERE {predicate}) BEGIN SELECT RAISE(ABORT,'credit v2 identity cannot replace'); END")
    return MappingProxyType(result)


# Effect/intent/source authorization triggers are intentionally not invented as
# successful placeholders. This catalog has no positive scope UDF or installer;
# those real constraints form the next separately reviewed primitive slice.
TRIGGER_SQL = _immutable_definitions()
OBJECT_SQL = MappingProxyType({**TABLE_SQL, **INDEX_SQL,
    **{name: sql for name, (_, sql) in TRIGGER_SQL.items()}})

MAX_DOCUMENT_BYTES = 1024 * 1024
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z", re.ASCII)
_ARTIFACT_ID = re.compile(r"credit-artifact:[0-9a-f]{64}\Z", re.ASCII)
_AMOUNT = re.compile(r"(?:0|[1-9][0-9]{0,31})(?:\.[0-9]{0,7}[1-9])?\Z", re.ASCII)
_ENVELOPE_FIELDS = frozenset({"format", "stage", "synthetic", "authority_id", "shard",
    "static_budget", "static_budget_id", "audit_format", "source_format", "fifo_format",
    "native_format", "artifact_id", "settlement_asset", "borrow_asset", "batch_size",
    "reserve_cache_size", "market_cache_size", "production_approved"})
_SOURCE_FIELDS = frozenset({"format", "source_kind", "actor_id", "source_reference", "authority_id",
    "account_id", "command_id", "kind", "payload_hash", "command_payload", "accepted_at"})


class CreditV2Error(StorageError):
    def __init__(self, code, message, status=503):
        super().__init__(message)
        self.code, self.status = code, status


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(text):
    return sha256(text.encode("utf-8")).hexdigest()


def _document(raw, *, code):
    """Parse only canonical data; never retained symbols or Python objects."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate field")
            result[key] = value
        return result
    def integer(value):
        if len(value) > 20:
            raise ValueError("unbounded metadata integer")
        return int(value)
    def no_number(value):
        raise ValueError("noninteger metadata")
    try:
        if type(raw) is not str or len(raw.encode("utf-8")) > MAX_DOCUMENT_BYTES:
            raise ValueError("invalid document size")
        result = json.loads(raw, object_pairs_hook=pairs, parse_int=integer,
                            parse_float=no_number, parse_constant=no_number)
        if type(result) is not dict or _canonical(result) != raw:
            raise ValueError("noncanonical document")
        return result
    except (TypeError, ValueError, UnicodeError, RecursionError) as error:
        raise CreditV2Error(code, "invalid canonical internal credit document") from error


def _name(value):
    return type(value) is str and _IDENTIFIER.fullmatch(value) is not None


@dataclass(frozen=True)
class CreditV2Envelope:
    """Validated declarations, not ownership or activation permission."""
    capability_id: str
    canonical_payload: str
    static_descriptor: object
    artifact_id: str


def validate_envelope(raw, *, expected_authority_id, expected_artifact_id=None,
                      expected_asset_scales=None):
    record = _document(raw, code="credit_v2_descriptor_invalid")
    try:
        if set(record) != _ENVELOPE_FIELDS or not _name(expected_authority_id):
            raise ValueError("unknown descriptor fields or authority")
        if expected_artifact_id is not None and type(expected_artifact_id) is not str:
            raise ValueError("invalid expected artifact identity")
        for name in ("format", "audit_format", "source_format", "fifo_format", "native_format"):
            if type(record[name]) is not int or record[name] != 2:
                raise ValueError("unsupported format")
        for name in ("batch_size", "reserve_cache_size", "market_cache_size"):
            if type(record[name]) is not int or record[name] != 0:
                raise ValueError("unsupported execution variant")
        if (record["stage"] != STAGE or record["synthetic"] is not True
                or record["production_approved"] is not False
                or record["settlement_asset"] != "USD" or record["borrow_asset"] != "BTC"
                or record["authority_id"] != expected_authority_id
                or type(record["shard"]) is not int or not 0 <= record["shard"] < 256
                or type(record["artifact_id"]) is not str or _ARTIFACT_ID.fullmatch(record["artifact_id"]) is None
                or expected_artifact_id is not None and record["artifact_id"] != expected_artifact_id):
            raise ValueError("unsupported descriptor scope")
        static = validate_native_descriptor(record["static_budget"], expected_authority_id=expected_authority_id,
            expected_shard=record["shard"], expected_asset_scales=expected_asset_scales)
        if (record["static_budget_id"] != static.descriptor_id
                or tuple((asset.asset, asset.scale) for asset in static.assets) != (("BTC", 8),)):
            raise ValueError("unsupported or mismatched static budget")
        return CreditV2Envelope("credit-internal-v2:" + _digest(raw), raw, static, record["artifact_id"])
    except (StorageError, TypeError, ValueError, AttributeError) as error:
        raise CreditV2Error("credit_v2_descriptor_invalid", "internal credit descriptor does not match its declared authority and scope") from error


def _source_payload(raw):
    record = _document(raw, code="credit_v2_source_invalid")
    try:
        if (set(record) != _SOURCE_FIELDS or type(record["format"]) is not int or record["format"] != 2
                or record["source_kind"] != "synthetic_local" or record["kind"] not in ("BORROW", "REPAY")
                or any(not _name(record[name]) for name in
                       ("actor_id", "source_reference", "authority_id", "account_id", "command_id"))):
            raise ValueError("invalid source identity")
        command = _document(record["command_payload"], code="credit_v2_source_invalid")
        if (set(command) != {"account_id", "asset", "amount"} or command["account_id"] != record["account_id"]
                or command["asset"] != "BTC" or type(command["amount"]) is not str
                or _AMOUNT.fullmatch(command["amount"]) is None or command["amount"] == "0"
                or record["payload_hash"] != _digest(record["command_payload"])):
            raise ValueError("source business payload differs")
        stamp = datetime.fromisoformat(record["accepted_at"])
        if stamp.tzinfo is None or stamp.astimezone(timezone.utc).isoformat(timespec="microseconds") != record["accepted_at"]:
            raise ValueError("source time is not canonical UTC")
        return record
    except (TypeError, ValueError, AttributeError) as error:
        raise CreditV2Error("credit_v2_source_invalid", "internal source receipt does not match its canonical business identity") from error


@dataclass(frozen=True)
class SyntheticCreditSource:
    """Immutable source evidence, explicitly not HMAC or financial authority."""
    source_id: str
    canonical_payload: str
    command_id: str
    account_id: str
    kind: str
    payload_hash: str
    command_payload: str
    actor_id: str
    source_reference: str
    authority_id: str


def parse_source(raw):
    record = _source_payload(raw)
    return SyntheticCreditSource("credit-source:" + _digest(raw), raw,
        *(record[name] for name in ("command_id", "account_id", "kind", "payload_hash",
            "command_payload", "actor_id", "source_reference", "authority_id")))


def source_receipt(*, authority_id, account_id, command_id, kind, actor_id,
                   source_reference, command_payload, accepted_at):
    """Construct data only; an actual native inbox scope is still required."""
    try:
        if (type(accepted_at) is not datetime or accepted_at.tzinfo is not timezone.utc
                or type(command_payload) is not str):
            raise ValueError("trusted producer time/payload type required")
        payload = _canonical({"format": 2, "source_kind": "synthetic_local", "actor_id": actor_id,
            "source_reference": source_reference, "authority_id": authority_id, "account_id": account_id,
            "command_id": command_id, "kind": kind, "payload_hash": _digest(command_payload),
            "command_payload": command_payload, "accepted_at": accepted_at.isoformat(timespec="microseconds")})
    except (TypeError, ValueError, UnicodeError, RecursionError) as error:
        raise CreditV2Error("credit_v2_source_invalid", "cannot construct canonical synthetic source evidence") from error
    return parse_source(payload)


def read_source(connection, command_id, *, expected_authority_id):
    """Verify actual stored source/inbox bytes; this reader grants no role."""
    try:
        if not _name(command_id) or not _name(expected_authority_id):
            raise ValueError("invalid source lookup identity")
        row = connection.execute("SELECT source_id,command_id,account_id,kind,payload_hash,source_kind,actor_id,source_reference,authority_id,command_payload,payload FROM credit_v2_sources WHERE command_id=?",
                                 (command_id,)).fetchone()
        if row is None:
            raise CreditV2Error("credit_v2_source_missing", "original internal credit source is absent")
        source = parse_source(row[10])
        expected = (source.source_id, source.command_id, source.account_id, source.kind, source.payload_hash,
                    "synthetic_local", source.actor_id, source.source_reference, source.authority_id,
                    source.command_payload, source.canonical_payload)
        if tuple(row) != expected or source.command_id != command_id or source.authority_id != expected_authority_id:
            raise ValueError("source relational identity differs")
        inbox = connection.execute("SELECT account_id,kind,payload FROM uta_command_inbox WHERE command_id=?",
                                   (command_id,)).fetchone()
        if inbox is None or tuple(inbox) != (source.account_id, source.kind, source.command_payload):
            raise ValueError("source has no actual matching inbox")
        return source
    except CreditV2Error:
        raise
    except (sqlite3.Error, TypeError, ValueError, AttributeError, IndexError) as error:
        raise CreditV2Error("credit_v2_source_invalid", "stored source and original inbox identity cannot be verified") from error


@dataclass(frozen=True)
class CreditOperationView:
    """Safe audit inputs; constructing this class never binds an operation."""
    operation_kind: str
    account_id: str
    command_id: str
    asset: str
    amount: str
    amount_units: int
    capability_id: str
    static_descriptor: object
    allocation_id: str
    journal_id: str
    payload_hash: str
    source_id: str
    actor_id: str
    source_payload: str
    intent_digest: str
    pre_version: int
    pre_state_payload: str
    pre_state_hash: str
    selected_at: object
    market_snapshot_id: object


@dataclass(frozen=True)
class _CreditOperation:
    # This private structure is not itself a capability either. Its actual
    # transaction registry binding and staged SQL intent must both validate.
    guard: object
    credit: object
    process_id: int
    thread_id: int
    generation: int
    view: CreditOperationView
    intent_row: tuple
    expected_postings: tuple


_INTENT_COLUMNS = ("command_id", "account_id", "scope", "operation_kind", "inbox_kind", "credit_kind",
    "asset", "amount", "amount_units", "payload_hash", "source_id", "authority_id", "allocation_id",
    "descriptor_id", "intent_digest", "journal_id", "pre_state_payload", "pre_state_hash",
    "isolation_payload", "isolation_hash", "journal_sealed", "terminal_state", "operation_id",
    "decision_kind", "market_dependency", "market_snapshot_id", "selected_at", "expected_postings",
    "old_principal_units", "old_interest_units", "new_principal_units", "new_interest_units", "pre_version", "post_version")


def assert_operation_context(credit, connection, *, command_id, account_id, asset, amount,
                             operation_kind="BORROW"):
    """Require actual registry/token/scope and actual staged SQL intent.

    There is no positive scope constructor/installer in this primitive slice.
    A fabricated frozen capture/view, object flag or detached connection cannot
    satisfy this interface. It grants no role and opens no transaction.
    """
    from .credit import CreditService
    from .service import _text
    from .writer_fence import _REGISTRY, _REGISTRY_LOCK, _assert_token
    if type(credit) is not CreditService or connection is None:
        raise CreditV2Error("credit_v2_context_invalid", "credit operation requires its actual initialized service and transaction")
    with _REGISTRY_LOCK:
        guard = _REGISTRY.get(id(connection))
    if (guard is None or guard.connection is not connection or guard.database is not credit.database
            or guard.role != "financial" or guard.credit_owner_thread != get_ident()
            or not connection.in_transaction):
        raise CreditV2Error("credit_v2_context_invalid", "credit operation requires its exact financial transaction")
    if guard.state is None or guard.state.get("credit_format") != 2:
        raise CreditV2Error("credit_v2_not_active", "this authority has no internal credit v2 capability")
    try:
        _assert_token(guard.database, guard.state, guard.database.writer_token)
    except StorageError as error:
        guard._deny(error)
        raise
    context = getattr(guard, "credit_v2_operation", None)
    if context is None:
        try:
            orphan = connection.execute("SELECT 1 FROM credit_v2_intents WHERE command_id=?", (command_id,)).fetchone()
        except sqlite3.Error as cause:
            error = CreditV2Error("credit_v2_context_invalid", "actual native intent inventory cannot be verified")
            guard._deny(error)
            raise error from cause
        if orphan is not None:
            error = CreditV2Error("credit_v2_context_invalid", "actual intent exists without its transaction operation context")
            guard._deny(error)
            raise error
        raise CreditV2Error("credit_v2_scope_missing", "internal credit v2 requires its actual operation scope")
    if (type(context) is not _CreditOperation or context.guard is not guard or context.credit is not credit
            or context.process_id != os.getpid() or context.thread_id != get_ident()
            or context.generation != guard.state["generation"] or guard.denied is not None):
        error = CreditV2Error("credit_v2_context_invalid", "no actual native operation is bound to this transaction")
        guard._deny(error)
        raise error
    try:
        view = context.view
        if (type(view) is not CreditOperationView
                or (view.operation_kind, view.command_id, view.account_id, view.asset, view.amount)
                   != (operation_kind, command_id, account_id, asset, _text(amount))):
            raise ValueError("operation identity differs")
        row = connection.execute("SELECT " + ",".join(_INTENT_COLUMNS)
                                 + " FROM credit_v2_intents WHERE command_id=?", (command_id,)).fetchone()
        if row is None or tuple(row) != context.intent_row:
            raise ValueError("actual staged intent is absent or different")
        bindings = dict(zip(_INTENT_COLUMNS, tuple(row)))
        actual_values = {"command_id": view.command_id, "account_id": view.account_id,
            "operation_kind": view.operation_kind, "asset": view.asset, "amount": view.amount,
            "amount_units": str(view.amount_units), "allocation_id": view.allocation_id,
            "journal_id": view.journal_id, "payload_hash": view.payload_hash, "source_id": view.source_id,
            "intent_digest": view.intent_digest, "pre_version": view.pre_version,
            "pre_state_payload": view.pre_state_payload, "pre_state_hash": view.pre_state_hash,
            "selected_at": view.selected_at, "market_snapshot_id": view.market_snapshot_id}
        if (type(view.pre_version) is not int or type(view.amount_units) is not int or view.amount_units <= 0
                or any(bindings[name] != value for name, value in actual_values.items())
                or view.pre_state_hash != _digest(view.pre_state_payload)
                or view.capability_id != guard.state["credit_capability_id"]):
            raise ValueError("actual operation prestate is not bound")
        static = validate_native_descriptor(view.static_descriptor.canonical_payload,
            expected_authority_id=guard.state["authority_id"])
        if static != view.static_descriptor or static.descriptor_id != bindings["descriptor_id"]:
            raise ValueError("actual static declaration differs")
        original_source = read_source(connection, command_id, expected_authority_id=guard.state["authority_id"])
        if (view.source_id, view.actor_id, view.source_payload) != (original_source.source_id,
                original_source.actor_id, original_source.canonical_payload):
            raise ValueError("actual first source differs")
        return view
    except (StorageError, sqlite3.Error, TypeError, ValueError, AttributeError, IndexError, KeyError) as cause:
        error = CreditV2Error("credit_v2_context_invalid", "operation context does not match actual staged identity")
        guard._deny(error)
        raise error from cause


def _runtime_dependencies():
    """Fixed real implementation dependencies, never archive-chosen imports.

    This is an additional fail-closed check, not proof by method presence: a
    real loader also validates exact SQL, current code and actual persisted
    state. Missing runtime pieces cannot publish or acquire a marker.
    """
    try:
        audit = importlib.import_module("uta.credit_audit_v2")
        fifo = importlib.import_module("uta.credit_fifo_v2")
        artifact = importlib.import_module("uta.credit_artifact")
        required = ("operation_scope", "synthetic_intake_scope", "rejection_scope", "metadata_scope",
                    "register_guard", "verify_before_commit", "install_internal_credit_v2")
        if (any(not callable(globals().get(name)) for name in required)
                or getattr(audit, "FORMAT", None) != 2
                or not isinstance(getattr(audit, "CreditAuditV2", None), type)
                or not isinstance(getattr(fifo, "InternalCreditFIFO", None), type)
                or not callable(getattr(fifo, "verify_existing_queue", None))
                or not {"credit_native_v2", "credit_audit_v2", "credit_fifo_v2", "credit_transition",
                        "credit_audit_v2_replay", "credit_v2_payload_contract"}
                    <= set(artifact._MODULES)):
            raise ValueError("complete internal credit implementation is absent")
        for name in ("runtime_evidence", "begin_borrow", "complete_borrow", "verify_staged_borrow", "replay"):
            if not callable(getattr(audit.CreditAuditV2, name, None)):
                raise ValueError("actual credit audit entry point is absent")
        for name in ("enqueue_borrow", "enqueue_repay", "process_one", "status"):
            if not callable(getattr(fifo.InternalCreditFIFO, name, None)):
                raise ValueError("actual internal credit FIFO entry point is absent")
        return audit, fifo, artifact
    except (ImportError, AttributeError, TypeError, ValueError) as error:
        raise CreditV2Error("credit_v2_runtime_incomplete", "complete native credit, audit, source, FIFO and code identity are required") from error


def verify_schema(connection):
    """Exact catalog plus real writer guards; never install or repair on read."""
    from .writer_fence import _guard_sql
    expected = {}
    for name, sql in OBJECT_SQL.items():
        if name in TABLE_SQL:
            expected[name] = ("table", name, sql)
        elif name in INDEX_SQL:
            expected[name] = ("index", sql.split(" ON ", 1)[1].split("(", 1)[0], sql)
        else:
            expected[name] = ("trigger", TRIGGER_SQL[name][0], sql)
    for table in TABLE_SQL:
        actions = "UD" if table == "credit_v2_sources" else "IUD"
        for action in actions:
            name, sql = _guard_sql(table, action)
            expected[name] = ("trigger", table, sql)
        for row in connection.execute(f"PRAGMA index_list({table})"):
            if row[1].startswith("sqlite_autoindex_"):
                expected[row[1]] = ("index", table, None)
    actual = {row[0]: tuple(row)[1:] for row in connection.execute(
        "SELECT name,type,tbl_name,sql FROM sqlite_master WHERE name LIKE 'credit_v2_%' OR tbl_name LIKE 'credit_v2_%'")}
    if actual != expected:
        raise CreditV2Error("credit_v2_schema_corrupt", "internal credit objects or writer guards differ; automatic repair is forbidden")


def load_marker(connection, row, *, authority_id):
    """A complete persisted format2, never promotion of prepared format1."""
    audit, fifo, artifact = _runtime_dependencies()
    if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        raise CreditV2Error("credit_v2_foreign_keys_required", "internal credit requires actual foreign-key enforcement")
    if len(row) != 5 or tuple(row)[:3] != (1, FORMAT, STAGE):
        raise CreditV2Error("credit_v2_corrupt", "unsupported internal credit marker")
    current = artifact.credit_code_artifact()
    current_id = artifact.credit_artifact_id(current)
    scales = dict(connection.execute("SELECT asset,scale FROM ledger_assets"))
    if scales != {"USD": 8, "BTC": 8}:
        raise CreditV2Error("credit_v2_corrupt", "internal credit requires the explicit USD8/BTC8 catalog")
    envelope = validate_envelope(row[4], expected_authority_id=authority_id,
        expected_artifact_id=current_id, expected_asset_scales=scales)
    if row[3] != envelope.capability_id:
        raise CreditV2Error("credit_v2_corrupt", "internal credit marker differs from its full content identity")
    verify_schema(connection)
    audit.verify_schema(connection)
    fifo.verify_existing_queue(connection)
    config = connection.execute("SELECT format,capability_id,descriptor_id,authority_id,artifact_id,payload FROM credit_v2_config WHERE singleton=1").fetchall()
    if [tuple(item) for item in config] != [(2, envelope.capability_id, envelope.static_descriptor.descriptor_id,
            authority_id, current_id, envelope.canonical_payload)]:
        raise CreditV2Error("credit_v2_corrupt", "internal credit configuration identity differs")
    retained = connection.execute("SELECT manifest FROM uta_credit_code_artifacts WHERE artifact_id=?", (current_id,)).fetchone()
    if retained is None or artifact.parse_credit_artifact(retained[0], expected_id=current_id) != current:
        raise CreditV2Error("credit_v2_corrupt", "actual current credit code artifact is not retained")
    allocation = envelope.static_descriptor.allocation_for("BTC", envelope.static_descriptor.shard)
    expected = (allocation.allocation_id, envelope.static_descriptor.descriptor_id,
        envelope.static_descriptor.certificate_id, authority_id, allocation.shard, "BTC", 8, str(allocation.limit_units))
    if [tuple(item) for item in connection.execute("SELECT * FROM credit_v2_allocations")] != [expected]:
        raise CreditV2Error("credit_v2_corrupt", "actual local immutable allocation differs")
    return envelope
