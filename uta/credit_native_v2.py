"""Fresh-only internal synthetic credit primitives and staged SQL obligations.

Importing this module installs nothing and grants no role or authority. Only a
complete explicit fresh synthetic format2 can enter its internal owner/intake/
financial scopes; immutable PREPARED1 is never upgraded. No HTTP/CLI activation
or real-funds permission is supplied. Positive-chain and independent acceptance
remain separate from this implementation's schema/data component tests.
"""
from dataclasses import dataclass
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
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
      policy_id TEXT NOT NULL REFERENCES uta_credit_risk_policies(policy_id),
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


def _create_object(connection, name, catalog):
    """Execute only a fixed native/audit catalog name in actual control role."""
    from .writer_fence import _REGISTRY, _REGISTRY_LOCK
    with _REGISTRY_LOCK:
        guard = _REGISTRY.get(id(connection))
    if (guard is None or guard.connection is not connection or guard.role != "control"
            or name not in catalog):
        raise CreditV2Error("credit_v2_context_invalid", "native schema requires its real control transaction")
    with guard.privileged():
        connection.execute(catalog[name])


def _opening_record(connection):
    return _canonical({"journal_head": _head(connection),
        "debts": [dict(row) for row in connection.execute("SELECT account_id,asset,principal,interest FROM uta_liabilities ORDER BY account_id,asset")],
        "account_limits": [dict(row) for row in connection.execute("SELECT account_id,asset,units FROM credit_account_limits ORDER BY account_id,asset")],
        "asset_limits": [dict(row) for row in connection.execute("SELECT asset,units FROM credit_asset_limits ORDER BY asset")],
        "credit_count": connection.execute("SELECT COUNT(*) FROM credit_commands").fetchone()[0]})


def install_internal_credit_v2(database, exchange, credit, envelope):
    """One fresh synthetic installation; no format1 upgrade or writer grant."""
    from .credit import CreditService
    from .service import ExchangeService
    from .credit_native import _verify_financial_source, validate_opening
    from .decision_audit import DecisionAudit
    from .writer_fence import (WriterFence, _load, _REGISTRY, _REGISTRY_LOCK,
        _create_control_object, _CONTROL_TRIGGER_SQL, _install_table_guards, _observed)
    if (type(exchange) is not ExchangeService or type(credit) is not CreditService
            or credit.exchange is not exchange or exchange.database is not database or credit.database is not database
            or database.writer_token is not None):
        raise CreditV2Error("credit_v2_context_invalid", "fresh installation requires actual unbound initialized source services")
    audit, fifo, _ = _runtime_dependencies()
    with database._fence_transaction() as con:
        state = _load(con)
        if state is None or state["guard_format"] != 1:
            raise CreditV2Error("credit_v2_fresh_required", "fresh installation needs its actual persistent guarded authority")
        if state.get("credit_format") == 1:
            raise CreditV2Error("credit_not_active", "prepared format1 can never become internal format2")
        if state.get("credit_format") == 2:
            current = con.execute("SELECT singleton,format,state,capability_id,payload FROM writer_fence_credit_v2_capability").fetchone()
            value = load_marker(con, current, authority_id=state["authority_id"])
            if type(envelope) is not str or envelope != value.canonical_payload:
                raise CreditV2Error("credit_v2_descriptor_conflict", "existing native capability cannot be replaced")
            return {"stage": STAGE, "capability_id": value.capability_id,
                "descriptor_id": value.static_descriptor.descriptor_id, "writer_acquired": False}
        history = tuple(tuple(row) for row in con.execute("SELECT sequence,kind FROM writer_fence_events ORDER BY sequence"))
        if (state["generation"] != 0 or state["owner_nonce"] is not None or state["batch_format"]
                or history != ((1, "enabled_guard_v1"),)
                or con.execute("SELECT 1 FROM uta_command_inbox LIMIT 1").fetchone()
                or con.execute("SELECT 1 FROM sqlite_master WHERE name LIKE 'credit_v2_%' OR name LIKE 'uta_credit_%' OR name LIKE 'credit_audit_v2_%' OR name LIKE 'uta_command_batch_%' LIMIT 1").fetchone()):
            raise CreditV2Error("credit_v2_fresh_required", "internal credit requires unused unowned fresh-only source state")
        old_queue_sequence = con.execute("SELECT seq FROM sqlite_sequence WHERE name='uta_command_inbox'").fetchone()
        if old_queue_sequence is not None and old_queue_sequence[0] != 0:
            raise CreditV2Error("credit_v2_fresh_required", "a previously used durable inbox cannot become a fresh native queue")
        scales = dict(con.execute("SELECT asset,scale FROM ledger_assets"))
        if scales != {"USD": 8, "BTC": 8} or exchange.audit is None:
            raise CreditV2Error("credit_v2_opening_unsupported", "fresh internal credit requires actual USD8/BTC8 and schema3 audit services")
        DecisionAudit.validate(con)
        _verify_financial_source(database, con, scales)
        for row in con.execute("SELECT asset,principal,interest FROM uta_liabilities"):
            if row[0] != "BTC" and (credit._stored(row[0], row[1]) or credit._stored(row[0], row[2])):
                raise CreditV2Error("credit_v2_opening_unsupported", "unsupported non-BTC opening debt cannot be locked into BTC-only credit")
        fifo.verify_existing_queue(con)
        # This is the real strict declaration. Current code identity is bound
        # below after the dedicated empty audit catalog has been created.
        declared = validate_envelope(envelope, expected_authority_id=state["authority_id"], expected_asset_scales=scales)
        validate_opening(con, declared.static_descriptor)
        opening = _opening_record(con)
        # Catalogs and immutable metadata are prepared before effect triggers;
        # no positive scope UDF is faked for installer metadata writes.
        for name in audit.OBJECT_SQL:
            _create_object(con, name, audit.OBJECT_SQL)
        for name in CATALOG_OBJECT_SQL:
            _create_object(con, name, CATALOG_OBJECT_SQL)
        evidence = audit.CreditAuditV2(exchange, credit).runtime_evidence(con)
        actual = validate_envelope(envelope, expected_authority_id=state["authority_id"],
            expected_artifact_id=evidence["artifact_id"], expected_asset_scales=scales)
        with _REGISTRY_LOCK:
            guard = _REGISTRY[id(con)]
        allocation = actual.static_descriptor.allocation_for("BTC", actual.static_descriptor.shard)
        with guard.privileged():
            con.execute("INSERT INTO uta_credit_code_artifacts VALUES(?,?)", (evidence["artifact_id"], audit.canonical(evidence["manifest"])))
            con.execute("INSERT INTO uta_credit_risk_policies VALUES(?,?)", (evidence["policy_id"], audit.canonical(evidence["policy"])))
            con.execute("INSERT INTO credit_v2_config VALUES(1,2,?,?,?,?,?,?,?,?,?)",
                (actual.capability_id, actual.static_descriptor.descriptor_id, state["authority_id"], evidence["artifact_id"], evidence["policy_id"],
                 json.loads(opening)["journal_head"]["sequence"], json.loads(opening)["credit_count"], opening, actual.canonical_payload))
            con.execute("INSERT INTO credit_v2_allocations VALUES(?,?,?,?,?,?,?,?)",
                (allocation.allocation_id, actual.static_descriptor.descriptor_id, actual.static_descriptor.certificate_id,
                 state["authority_id"], allocation.shard, "BTC", 8, str(allocation.limit_units)))
            for row in con.execute("SELECT scope,command_id,kind,asset,amount,journal_event_id,result FROM credit_commands"):
                con.execute("INSERT INTO credit_v2_legacy_commands VALUES(?,?,?,?,?,?,?)",
                    (*tuple(row)[:6], _digest(row[6])))
        for name in EFFECT_TRIGGER_SQL:
            _create_object(con, name, OBJECT_SQL)
        with guard.privileged():
            _install_table_guards(con, set(TABLE_SQL) | set(audit.TABLE_SQL))
        _create_control_object(con, MARKER_NAME)
        con.execute("INSERT INTO writer_fence_credit_v2_capability VALUES(1,2,?,?,?)",
                    (STAGE, actual.capability_id, actual.canonical_payload))
        for name, (table, _) in _CONTROL_TRIGGER_SQL.items():
            if table == MARKER_NAME:
                _create_control_object(con, name)
        now, _ = _observed(database, state)
        WriterFence(database)._event(con, "credit_internal_enabled_v2", state, now)
    return {"stage": STAGE, "capability_id": actual.capability_id,
        "descriptor_id": actual.static_descriptor.descriptor_id, "writer_acquired": False}


def acquire_credit_v2(database, owner_nonce, ttl_seconds):
    """Explicit internal real acquisition; generic acquire never opts in."""
    _runtime_dependencies()
    from .writer_fence import WriterFence
    return WriterFence(database)._acquire_internal_credit_v2(owner_nonce, ttl_seconds)


def _source_row(source):
    return (source.command_id, source.source_id, source.account_id, source.kind, source.payload_hash,
        "synthetic_local", source.actor_id, source.source_reference, source.authority_id,
        source.command_payload, source.canonical_payload)


def _live_sql_context(guard):
    from .writer_fence import _assert_token
    context = getattr(guard, "credit_v2_context", None)
    if (guard.denied is not None or not getattr(guard, "credit_v2_active", False)
            or type(context) not in (_IntakeContext, _CreditOperation, _MetadataContext, _RejectionContext)
            or context.guard is not guard or context.process_id != os.getpid()
            or context.thread_id != get_ident() or guard.credit_owner_thread != get_ident()
            or not guard.connection.in_transaction or guard.state is None or guard.state.get("credit_format") != 2):
        raise CreditV2Error("credit_v2_context_invalid", "no live actual native scope for protected mutation")
    if type(context) is _IntakeContext:
        if guard.role != "inbox":
            raise CreditV2Error("credit_v2_context_invalid", "source intake has no producer role")
    else:
        if guard.role != "financial" or context.credit.database is not guard.database:
            raise CreditV2Error("credit_v2_context_invalid", "financial scope has no actual service binding")
        _assert_token(guard.database, guard.state, guard.database.writer_token)
    return context


def _sql_gate(guard, phase, *args):
    """Pure NEW/OLD/context checks only; never recursive SQL or seen counters."""
    try:
        context = _live_sql_context(guard)
        if phase == "SOURCE":
            valid = type(context) is _IntakeContext and args == _source_row(context.source)
        elif phase == "INBOX_INSERT":
            valid = (type(context) is _IntakeContext and args == (context.source.command_id, context.source.account_id,
                context.source.kind, context.source.command_payload, "PENDING", None, None, None, 0, None, None))
        elif phase == "INBOX_UPDATE":
            cid, account, kind, payload, state, result, error, completed, old_state = args
            if type(context) is _RejectionContext:
                valid = (cid, account, kind, payload, state, result, error, old_state) == (
                    context.source.command_id, context.source.account_id, context.source.kind,
                    context.source.command_payload, "REJECTED", None, context.error_payload, "PENDING")
            elif type(context) is _CreditOperation:
                valid = (cid, account, kind, state, error, old_state) == (context.view.command_id,
                    context.view.account_id, context.view.operation_kind, "SUCCEEDED", None, "PENDING") and result is not None
            else:
                valid = False
            from .credit_audit_v2 import utc_checkpoint
            if valid:
                source_payload = context.source.canonical_payload if type(context) is _RejectionContext else context.view.source_payload
                if utc_checkpoint(completed) < utc_checkpoint(json.loads(source_payload)["accepted_at"]):
                    raise CreditV2Error("credit_v2_clock_regression", "actual terminal time precedes its original source")
        elif phase in ("CONFIG", "MARKET", "MARKET_HISTORY"):
            valid = type(context) is _MetadataContext
            if phase == "CONFIG":
                valid = valid and context.operation == "SET_HALT" and args[0] == "halted" and args[1] in ("true", "false")
            else:
                valid = valid and context.operation == "PUBLISH_MARKET"
                if phase == "MARKET":
                    valid = valid and args[0] == 1
                else:
                    valid = valid and args[0] == "market:" + _digest(args[2]) and args[1] == _digest(args[2]) and args[3] == "PUBLISHED"
        elif phase == "SERVICE_EVENT":
            event, account, payload, created = args
            from .credit_audit_v2 import utc_checkpoint
            utc_checkpoint(created)
            if type(context) is _MetadataContext:
                valid = account is None and event == ("KILL_SWITCH_CHANGED" if context.operation == "SET_HALT" else "MARKET_PUBLISHED")
            elif type(context) is _CreditOperation:
                item = _document(payload, code="credit_v2_state_invalid")
                valid = (event, account, item.get("command_id")) == ("CREDIT_" + ("BORROWED" if context.view.operation_kind == "BORROW" else "REPAID"),
                    context.view.account_id, context.view.command_id)
            else:
                valid = False
        else:
            valid = type(context) is _CreditOperation and context.generation == guard.state["generation"]
            if not valid:
                raise CreditV2Error("credit_v2_context_invalid", "financial effect requires an actual credit operation")
            if phase == "INTENT":
                valid = args == context.intent_row
            else:
                cid, digest, *values = args
                # EXISTS may evaluate this scalar before its other predicates.
                # Historical intent rows are candidates, not attempted effects
                # belonging to this operation. They grant no permission. Only
                # the final trigger may reject an effect when no current actual
                # staged obligation matches. A wrong digest for the current CID
                # is still a fatal violation below.
                if cid != context.view.command_id:
                    return 0
                valid = (cid, digest) == (context.view.command_id, context.view.intent_digest)
                after = json.loads(context.after_payload)
                before = json.loads(context.view.pre_state_payload)["credit"]
                from .service import _text
                def amount(units):
                    return _text(context.credit._codec._amount(context.view.asset, int(units)))
                if phase == "EXPECTED":
                    ordinal, name, asset, units = values
                    valid = (valid and type(ordinal) is int and 0 <= ordinal < len(context.expected_postings)
                        and (name, asset, units) == tuple((*context.expected_postings[ordinal][:2], str(context.expected_postings[ordinal][2]))))
                elif phase == "POSTING":
                    sequence, ordinal, name, asset, units = values
                    head = json.loads(context.view.pre_state_payload)["journal_head"]
                    valid = (valid and sequence == head["sequence"] + 1 and type(ordinal) is int
                        and 0 <= ordinal < len(context.expected_postings)
                        and (name, asset, units) == (*context.expected_postings[ordinal][:2], str(context.expected_postings[ordinal][2])))
                elif phase.startswith("DEBT_"):
                    account, asset, principal, interest, old_principal, old_interest = values
                    valid = valid and (account, asset, principal, interest) == (context.view.account_id, context.view.asset,
                        amount(after["principal_units"]), amount(after["interest_units"]))
                    if phase == "DEBT_UPDATE":
                        valid = valid and (context.credit._stored(asset, old_principal), context.credit._stored(asset, old_interest)) == (
                            int(before["principal_units"]), int(before["interest_units"]))
                elif phase == "ACCOUNT":
                    valid = valid and tuple(values) == (context.view.account_id, context.view.pre_version, context.view.pre_version + 1)
                elif phase.startswith("JOURNAL_"):
                    from .storage import DurableLedger
                    head = json.loads(context.view.pre_state_payload)["journal_head"]
                    fingerprint = DurableLedger._fingerprint(context.expected_postings)
                    expected = (head["sequence"] + 1, context.view.journal_id, fingerprint, head["event_hash"],
                        DurableLedger._hash(head["sequence"] + 1, context.view.journal_id, head["event_hash"], fingerprint),
                        0 if phase == "JOURNAL_INSERT" else 1)
                    valid = valid and tuple(values) == expected
                elif phase.startswith("BALANCE_"):
                    name, asset, units, old_units = values
                    deltas = {(name, asset): value for name, asset, value in context.expected_postings}
                    previous = {(name, asset): value for name, asset, value in context.ledger_before}
                    valid = valid and (name, asset) in deltas and units == str(previous[name, asset] + deltas[name, asset])
                    if phase == "BALANCE_UPDATE":
                        valid = valid and old_units == str(previous[name, asset])
                elif phase == "RECORD":
                    scope, record_cid, kind, asset, text, source_reference, payload, journal, created = values
                    item = _document(payload, code="credit_v2_state_invalid")
                    valid = (valid and (scope, record_cid, kind, asset, text, source_reference, journal) == (
                        "account:" + context.view.account_id, context.view.command_id,
                        "borrowed" if context.view.operation_kind == "BORROW" else "repaid", context.view.asset,
                        context.view.amount, None, context.view.journal_id)
                        and {key: item.get(key) for key in ("account_id", "command_id", "asset", "amount", "principal", "interest", "total", "account_version", "journal_event_id")} == {
                            "account_id": context.view.account_id, "command_id": context.view.command_id, "asset": context.view.asset,
                            "amount": context.view.amount, "principal": amount(after["principal_units"]),
                            "interest": amount(after["interest_units"]),
                            "total": amount(int(after["principal_units"]) + int(after["interest_units"])),
                            "account_version": context.view.pre_version + 1, "journal_event_id": context.view.journal_id})
                    from .credit_audit_v2 import utc_checkpoint
                    utc_checkpoint(created)
                elif phase == "DECISION":
                    from .credit_audit_v2 import strict_json
                    valid = valid and context.view.operation_kind == "BORROW" and type(strict_json(values[0])) is dict and type(values[1]) is str
                else:
                    valid = False
        if valid:
            return 1
        raise CreditV2Error("credit_v2_state_invalid", "protected row differs from actual native command inputs")
    except BaseException as cause:
        _poison(guard, "actual native credit SQL guard refused a protected mutation", code="credit_v2_sql_guard_failed", cause=cause)
        return 0


def register_guard(guard):
    """Register actual connection-local pure gates, with no positive fixtures."""
    if guard.connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        raise CreditV2Error("credit_v2_foreign_keys_required", "actual native foreign-key enforcement is required")
    guard.credit_v2_baseline = _snapshot_database(guard.connection)
    guard.credit_v2_sequences = dict(guard.connection.execute("SELECT name,seq FROM sqlite_sequence"))
    guard.credit_v2_context = None
    guard.credit_v2_operation = None
    guard.credit_v2_active = False
    guard.connection.create_function("uta_credit_v2_gate", -1, lambda *args: _sql_gate(guard, *args))
    def deny(phase):
        _poison(guard, "actual native credit SQL guard refused a protected mutation", code="credit_v2_sql_guard_failed")
        return 0
    guard.connection.create_function("uta_credit_v2_deny", 1, deny)
    guard._credit_v2_udf_registered = True


def close_guard(guard):
    if getattr(guard, "_credit_v2_udf_registered", False):
        guard.connection.create_function("uta_credit_v2_gate", -1, None)
        guard.connection.create_function("uta_credit_v2_deny", 1, None)


def authorize_write(guard, action, table):
    """DML allowlist inside a real scope; SQL gates still check staged rows."""
    from .writer_fence import _ACTIONS, _OK
    try:
        context = _live_sql_context(guard)
        if type(context) is _IntakeContext:
            allowed = (action == _ACTIONS["INSERT"] and table in ("credit_v2_sources", "uta_command_inbox")
                or table == "sqlite_sequence" and action in (_ACTIONS["INSERT"], _ACTIONS["UPDATE"]))
        elif type(context) is _MetadataContext:
            allowed = (action == _ACTIONS["INSERT"] and table in ("uta_events", "sqlite_sequence")
                or context.operation == "SET_HALT" and table == "uta_config" and action in (_ACTIONS["INSERT"], _ACTIONS["UPDATE"])
                or context.operation == "PUBLISH_MARKET" and table in ("uta_market", "uta_market_history") and action in (_ACTIONS["INSERT"], _ACTIONS["UPDATE"]))
        elif type(context) is _RejectionContext:
            allowed = action == _ACTIONS["UPDATE"] and table == "uta_command_inbox"
        else:
            permitted = {
                "credit_v2_intents": ("INSERT",), "credit_v2_expected_postings": ("INSERT",),
                "ledger_events": ("INSERT", "UPDATE"), "ledger_postings": ("INSERT",),
                "ledger_balances": ("INSERT", "UPDATE"), "uta_liabilities": ("INSERT", "UPDATE"),
                "uta_accounts": ("UPDATE",), "credit_commands": ("INSERT",), "uta_events": ("INSERT",),
                "uta_credit_decisions": ("INSERT",), "uta_credit_code_artifacts": ("INSERT",),
                "uta_credit_risk_policies": ("INSERT",), "uta_command_inbox": ("UPDATE",), "sqlite_sequence": ("INSERT", "UPDATE"),
            }
            allowed = action in tuple(_ACTIONS[name] for name in permitted.get(table, ()))
        if not allowed:
            raise CreditV2Error("credit_v2_context_invalid", "native scope does not authorize this table mutation")
        if guard.role == "financial":
            guard.written = True
        return _OK
    except BaseException as cause:
        return guard._deny(_poison(guard, "internal credit DML requires its actual allowed scope", cause=cause))


def _dict_rows(snapshot, table):
    columns, rows = snapshot[table]
    return [dict(zip(columns, row)) for row in rows]


def _set_rows(snapshot, table, rows):
    columns = snapshot[table][0]
    normalized = tuple(sorted((tuple(row[name] for name in columns) for row in rows),
        key=lambda row: _canonical([_sql_value(value) for value in row])))
    snapshot[table] = (columns, normalized)


def _replace_row(snapshot, table, keys, changed):
    rows = _dict_rows(snapshot, table)
    matches = [row for row in rows if all(row[name] == changed[name] for name in keys)]
    if len(matches) > 1:
        raise CreditV2Error("credit_v2_state_invalid", "ambiguous actual financial row identity")
    if matches:
        rows.remove(matches[0])
    rows.append(changed)
    _set_rows(snapshot, table, rows)


def _assert_snapshot(expected, actual):
    if expected != actual:
        raise CreditV2Error("credit_v2_unexpected_effect", "actual staged financial state differs from its one permitted command")


def _verify_operation(guard, context):
    """Rebuild exact expected DB deltas; all proof comes from actual rows."""
    from .credit_audit_v2 import read_credit_snapshot, journal_record, verify_journal, utc_checkpoint
    from .service import _text
    credit, con, view = context.credit, guard.connection, context.view
    assert_operation_context(credit, con, command_id=view.command_id, account_id=view.account_id,
        asset=view.asset, amount=Decimal(view.amount), operation_kind=view.operation_kind)
    actual = _snapshot_database(con)
    expected = dict(guard.credit_v2_baseline)
    after, _ = read_credit_snapshot(credit.exchange, credit, con, view.account_id, view.asset,
                                   require_limits=False, require_increment=False)
    if _canonical(after) != context.after_payload:
        raise CreditV2Error("credit_v2_unexpected_effect", "actual gross account/shard debt and pool differ from the trusted transition")
    intent = dict(zip(_INTENT_COLUMNS, context.intent_row))
    _replace_row(expected, "credit_v2_intents", ("command_id",), intent)
    rows = _dict_rows(expected, "credit_v2_expected_postings")
    rows.extend({"command_id": view.command_id, "ordinal": n, "account": name, "asset": asset, "units": str(units)}
                for n, (name, asset, units) in enumerate(context.expected_postings))
    _set_rows(expected, "credit_v2_expected_postings", rows)
    account_rows = _dict_rows(expected, "uta_accounts")
    for row in account_rows:
        if row["account_id"] == view.account_id:
            if row["version"] != view.pre_version:
                raise CreditV2Error("credit_v2_state_invalid", "starting account version differs")
            row["version"] += 1
    _set_rows(expected, "uta_accounts", account_rows)
    def amount(units):
        return _text(credit._codec._amount(view.asset, int(units)))
    _replace_row(expected, "uta_liabilities", ("account_id", "asset"), {"account_id": view.account_id,
        "asset": view.asset, "principal": amount(after["principal_units"]), "interest": amount(after["interest_units"])})
    recorded = journal_record(con, view.journal_id)
    legs = [{"ordinal": n, "account": name, "asset": asset, "units": str(units)}
            for n, (name, asset, units) in enumerate(context.expected_postings)]
    prestate = json.loads(view.pre_state_payload)
    verify_journal(recorded, expected_event_id=view.journal_id, expected_postings=legs,
                   journal_head=prestate["journal_head"])
    events = _dict_rows(expected, "ledger_events")
    events.append({name: recorded[name] for name in expected["ledger_events"][0]})
    _set_rows(expected, "ledger_events", events)
    postings = _dict_rows(expected, "ledger_postings")
    postings.extend({"sequence": recorded["sequence"], **row} for row in legs)
    _set_rows(expected, "ledger_postings", postings)
    before_balances = {(name, asset): value for name, asset, value in context.ledger_before}
    for name, asset, units in context.expected_postings:
        _replace_row(expected, "ledger_balances", ("account", "asset"),
                     {"account": name, "asset": asset, "units": str(before_balances[name, asset] + units)})
    records = [row for row in _dict_rows(actual, "credit_commands") if row["scope"] == "account:" + view.account_id and row["command_id"] == view.command_id]
    if len(records) != 1:
        raise CreditV2Error("credit_v2_closing_invalid", "actual original credit receipt is missing or ambiguous")
    record = records[0]
    if (record["kind"], record["asset"], record["amount"], record["source_reference"], record["journal_event_id"]) != (
            "borrowed" if view.operation_kind == "BORROW" else "repaid", view.asset, view.amount, None, view.journal_id):
        raise CreditV2Error("credit_v2_closing_invalid", "actual receipt relational identity differs")
    result = credit._read_result(record)
    basic = credit._result(view.account_id, view.command_id, view.asset, view.amount,
        int(after["principal_units"]), int(after["interest_units"]), view.pre_version + 1, view.journal_id)
    if any(result.get(name) != value for name, value in basic.items()):
        raise CreditV2Error("credit_v2_closing_invalid", "actual original receipt differs from financial transition")
    _replace_row(expected, "credit_commands", ("scope", "command_id"), record)
    terminal_rows = [row for row in _dict_rows(actual, "uta_command_inbox") if row["command_id"] == view.command_id]
    if len(terminal_rows) != 1:
        raise CreditV2Error("credit_v2_closing_invalid", "original command terminal is missing")
    terminal = terminal_rows[0]
    original = next(row for row in _dict_rows(expected, "uta_command_inbox") if row["command_id"] == view.command_id)
    accepted_at = json.loads(view.source_payload)["accepted_at"]
    if original["enqueued_at"] != accepted_at or utc_checkpoint(terminal["completed_at"]) < utc_checkpoint(accepted_at):
        raise CreditV2Error("credit_v2_clock_regression", "actual command time precedes its original immutable source")
    permitted = dict(original)
    permitted.update(state="SUCCEEDED", result=record["result"], error=None,
        completed_at=terminal["completed_at"], next_attempt_at=None)
    if (type(terminal["attempts"]) is not int or terminal["attempts"] not in (original["attempts"], original["attempts"] + 1)
            or terminal["last_error"] not in (original["last_error"], None)):
        raise CreditV2Error("credit_v2_closing_invalid", "terminal retry metadata differs")
    permitted.update(attempts=terminal["attempts"], last_error=terminal["last_error"])
    if terminal != permitted:
        raise CreditV2Error("credit_v2_closing_invalid", "original CID terminal differs from its credit receipt")
    utc_checkpoint(terminal["completed_at"])
    _replace_row(expected, "uta_command_inbox", ("command_id",), permitted)
    service_events = [row for row in _dict_rows(actual, "uta_events") if row not in _dict_rows(expected, "uta_events")]
    if (len(service_events) != 1 or service_events[0]["sequence"] != max((row["sequence"] for row in _dict_rows(expected, "uta_events")), default=0) + 1
            or service_events[0]["event_type"] != "CREDIT_" + ("BORROWED" if view.operation_kind == "BORROW" else "REPAID")
            or service_events[0]["account_id"] != view.account_id or service_events[0]["payload"] != record["result"]):
        raise CreditV2Error("credit_v2_closing_invalid", "credit event does not match the original receipt")
    utc_checkpoint(record["created_at"])
    utc_checkpoint(service_events[0]["created_at"])
    _set_rows(expected, "uta_events", _dict_rows(expected, "uta_events") + service_events)
    if view.operation_kind == "BORROW":
        audit, _, _ = _runtime_dependencies()
        decision = audit.CreditAuditV2(credit.exchange, credit).verify_staged_borrow(con, view.command_id, terminal_required=True)
        if type(decision) is not dict or "decision_id" not in decision:
            raise CreditV2Error("credit_v2_closing_invalid", "actual staged dedicated decision verification is incomplete")
        rows = [row for row in _dict_rows(actual, "uta_credit_decisions") if row["command_id"] == view.command_id]
        if len(rows) != 1 or rows[0]["decision_id"] != decision["decision_id"]:
            raise CreditV2Error("credit_v2_closing_invalid", "actual staged decision identity differs")
        _replace_row(expected, "uta_credit_decisions", ("decision_id",), rows[0])
        if utc_checkpoint(terminal["completed_at"]) < utc_checkpoint(rows[0]["recorded_at"]):
            raise CreditV2Error("credit_v2_clock_regression", "terminal time precedes the actual dedicated decision")
        now = utc_checkpoint(_stamp_actual(credit.exchange))
        if now < utc_checkpoint(rows[0]["recorded_at"]):
            raise CreditV2Error("credit_v2_closing_invalid", "actual final application clock regressed")
        market = credit.exchange._market(con)
        if credit.exchange.audit.market_ref(con, market) != view.market_snapshot_id:
            raise CreditV2Error("credit_v2_closing_invalid", "actual final market identity differs")
        market.validate(now=now, max_age=credit.exchange.max_price_age, max_future_skew=timedelta(seconds=1))
    _assert_snapshot(expected, actual)


def _verify_intake(guard, context):
    actual = _snapshot_database(guard.connection)
    expected = dict(guard.credit_v2_baseline)
    source = read_source(guard.connection, context.source.command_id, expected_authority_id=guard.state["authority_id"])
    if source != context.source:
        raise CreditV2Error("credit_v2_source_invalid", "actual original source changed")
    columns = expected["credit_v2_sources"][0]
    source_row = dict(zip(columns, _source_row(source)))
    _replace_row(expected, "credit_v2_sources", ("command_id",), source_row)
    candidates = [row for row in _dict_rows(actual, "uta_command_inbox") if row["command_id"] == source.command_id]
    if len(candidates) != 1:
        raise CreditV2Error("credit_v2_source_invalid", "actual original pending command is missing")
    row = candidates[0]
    original = _dict_rows(expected, "uta_command_inbox")
    if (row["state"] != "PENDING" or any(row[name] is not None for name in ("result", "error", "completed_at", "last_error", "next_attempt_at"))
            or row["attempts"] != 0 or row["sequence"] != max((item["sequence"] for item in original), default=0) + 1):
        raise CreditV2Error("credit_v2_source_invalid", "native source has an invalid pending command")
    if row["enqueued_at"] != json.loads(source.canonical_payload)["accepted_at"]:
        raise CreditV2Error("credit_v2_source_invalid", "actual pending acceptance time differs from its first source")
    _set_rows(expected, "uta_command_inbox", original + [row])
    _assert_snapshot(expected, actual)


def _verify_rejection(guard, context):
    actual = _snapshot_database(guard.connection)
    expected = dict(guard.credit_v2_baseline)
    cid = context.source.command_id
    original = next(row for row in _dict_rows(expected, "uta_command_inbox") if row["command_id"] == cid)
    candidates = [row for row in _dict_rows(actual, "uta_command_inbox") if row["command_id"] == cid]
    if len(candidates) != 1:
        raise CreditV2Error("credit_v2_closing_invalid", "original rejected command is missing")
    changed = dict(original)
    changed.update(state="REJECTED", result=None, error=context.error_payload,
                   completed_at=candidates[0]["completed_at"], next_attempt_at=None)
    if (type(candidates[0]["attempts"]) is not int or candidates[0]["attempts"] not in (original["attempts"], original["attempts"] + 1)
            or candidates[0]["last_error"] not in (original["last_error"], None)):
        raise CreditV2Error("credit_v2_closing_invalid", "rejection retry metadata differs")
    changed.update(attempts=candidates[0]["attempts"], last_error=candidates[0]["last_error"])
    if candidates[0] != changed:
        raise CreditV2Error("credit_v2_closing_invalid", "business rejection changed its original command identity")
    from .credit_audit_v2 import utc_checkpoint
    utc_checkpoint(changed["completed_at"])
    accepted_at = json.loads(context.source.canonical_payload)["accepted_at"]
    if original["enqueued_at"] != accepted_at or utc_checkpoint(changed["completed_at"]) < utc_checkpoint(accepted_at):
        raise CreditV2Error("credit_v2_clock_regression", "actual rejection time precedes its original accepted source")
    _replace_row(expected, "uta_command_inbox", ("command_id",), changed)
    _assert_snapshot(expected, actual)


def _verify_metadata(guard, context):
    from .credit_audit_v2 import utc_checkpoint
    con = guard.connection
    actual = _snapshot_database(con)
    expected = dict(guard.credit_v2_baseline)
    added_events = [row for row in _dict_rows(actual, "uta_events") if row not in _dict_rows(expected, "uta_events")]
    if context.operation == "SET_HALT":
        original = _dict_rows(expected, "uta_config")
        current = _dict_rows(actual, "uta_config")
        old_halt = next((row for row in original if row["key"] == "halted"), None)
        new_halt = next((row for row in current if row["key"] == "halted"), None)
        if new_halt is None or new_halt["value"] not in ("true", "false"):
            raise CreditV2Error("credit_v2_metadata_invalid", "actual halt metadata is invalid")
        _replace_row(expected, "uta_config", ("key",), new_halt)
        changed = old_halt != new_halt
        event_type = "KILL_SWITCH_CHANGED"
        event_payload = _canonical({"enabled": new_halt["value"] == "true"})
    else:
        from .market import MarketSnapshot
        before = context.market_snapshot
        after = _snapshot_tables(con, ("uta_market", "uta_market_history"))
        rows = _dict_rows(after, "uta_market")
        if len(rows) != 1 or rows[0]["singleton"] != 1:
            raise CreditV2Error("credit_v2_metadata_invalid", "actual market publication is absent")
        market = MarketSnapshot.from_json(rows[0]["payload"])
        market.validate(now=context.credit.exchange._now(), max_age=context.credit.exchange.max_price_age,
                        max_future_skew=timedelta(seconds=1))
        context.credit.exchange._validate_policy_market(market)
        sid = "market:" + _digest(rows[0]["payload"])
        history = _dict_rows(after, "uta_market_history")
        matches = [row for row in history if row["snapshot_id"] == sid]
        if len(matches) != 1 or matches[0]["payload"] != rows[0]["payload"] or matches[0]["content_digest"] != _digest(rows[0]["payload"]):
            raise CreditV2Error("credit_v2_metadata_invalid", "actual market has no complete historical source")
        expected_market = dict(before)
        _set_rows(expected_market, "uta_market", rows)
        old_history = _dict_rows(before, "uta_market_history")
        if not any(row["snapshot_id"] == sid for row in old_history):
            if matches[0]["origin"] != "PUBLISHED":
                raise CreditV2Error("credit_v2_metadata_invalid", "new market origin is invalid")
            utc_checkpoint(matches[0]["recorded_at"])
            old_history.append(matches[0])
        _set_rows(expected_market, "uta_market_history", old_history)
        _assert_snapshot(expected_market, after)
        changed = before["uta_market"] != after["uta_market"]
        event_type = "MARKET_PUBLISHED"
        event_payload = _canonical({"version": market.version, "observed_at": market.observed_at.isoformat(), "market_snapshot_id": sid})
    if len(added_events) != int(changed):
        raise CreditV2Error("credit_v2_metadata_invalid", "metadata event count differs from its actual change")
    if changed:
        event = added_events[0]
        if (event["sequence"] != max((row["sequence"] for row in _dict_rows(expected, "uta_events")), default=0) + 1
                or event["event_type"] != event_type or event["account_id"] is not None or event["payload"] != event_payload):
            raise CreditV2Error("credit_v2_metadata_invalid", "metadata event differs from the actual publication")
        utc_checkpoint(event["created_at"])
    _set_rows(expected, "uta_events", _dict_rows(expected, "uta_events") + added_events)
    _assert_snapshot(expected, actual)


def verify_before_commit(guard):
    """Actual staged-state reconstruction, independent of observed UDF counts."""
    from .credit_native import _verify_financial_source
    context = getattr(guard, "credit_v2_context", None)
    try:
        if guard.denied is not None:
            raise guard.denied
        if getattr(guard, "credit_v2_active", False):
            raise CreditV2Error("credit_v2_context_invalid", "native operation scope did not finish before physical commit")
        # None never means "nothing happened": actual state must equal the
        # actual starting snapshot. This detects lost context with staged rows.
        if context is None:
            _assert_snapshot(guard.credit_v2_baseline, _snapshot_database(guard.connection))
        elif type(context) is _IntakeContext:
            _verify_intake(guard, context)
        elif type(context) is _RejectionContext:
            _verify_rejection(guard, context)
        elif type(context) is _MetadataContext:
            _verify_metadata(guard, context)
        elif type(context) is _CreditOperation:
            _verify_operation(guard, context)
        else:
            raise CreditV2Error("credit_v2_context_invalid", "unexpected native transaction context")
        expected_sequences = dict(guard.credit_v2_sequences)
        for name in ("uta_events", "uta_command_inbox"):
            previous = max((row["sequence"] for row in _dict_rows(guard.credit_v2_baseline, name)), default=0)
            actual_max = guard.connection.execute("SELECT COALESCE(MAX(sequence),0) FROM " + name).fetchone()[0]
            if actual_max != previous:
                expected_sequences[name] = actual_max
        if dict(guard.connection.execute("SELECT name,seq FROM sqlite_sequence")) != expected_sequences:
            raise CreditV2Error("credit_v2_unexpected_effect", "unrelated SQLite allocation state changed")
        # All source/intent/terminal/audit obligations now exist, unlike the
        # in-flight middle of a credit operation. Original global FK/journal
        # verification is meaningful at this point.
        scales = dict(guard.connection.execute("SELECT asset,scale FROM ledger_assets"))
        _verify_financial_source(guard.database, guard.connection, scales)
    except BaseException as cause:
        raise _poison(guard, "actual native before-commit verification failed", cause=cause) from cause

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
    after_payload: str
    ledger_before: tuple


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
    if (type(context) is not _CreditOperation or getattr(guard, "credit_v2_context", None) is not context
            or context.guard is not guard or context.credit is not credit
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
        existing = importlib.import_module("uta.existing_services")
        required = ("operation_scope", "synthetic_intake_scope", "rejection_scope", "metadata_scope",
                    "register_guard", "verify_before_commit", "install_internal_credit_v2")
        if (any(not callable(globals().get(name)) for name in required)
                or getattr(audit, "FORMAT", None) != 2
                or not isinstance(getattr(audit, "CreditAuditV2", None), type)
                or not isinstance(getattr(fifo, "InternalCreditFIFO", None), type)
                or not callable(getattr(fifo, "verify_existing_queue", None))
                or not callable(getattr(fifo, "is_business_rejection", None))
                or not callable(getattr(existing, "open_existing_services", None))
                or not {"credit_native_v2", "credit_audit_v2", "credit_fifo_v2", "credit_transition",
                        "credit_audit_v2_replay", "credit_v2_payload_contract", "existing_services"}
                    <= set(artifact._MODULES)):
            raise ValueError("complete internal credit implementation is absent")
        if not callable(getattr(audit, "verify_stored_policy", None)):
            raise ValueError("actual dedicated policy validator is absent")
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
    stored_policy = audit.verify_stored_policy(connection)
    config = connection.execute("SELECT format,capability_id,descriptor_id,authority_id,artifact_id,policy_id,payload FROM credit_v2_config WHERE singleton=1").fetchall()
    if [tuple(item) for item in config] != [(2, envelope.capability_id, envelope.static_descriptor.descriptor_id,
            authority_id, current_id, stored_policy["policy_id"], envelope.canonical_payload)]:
        raise CreditV2Error("credit_v2_corrupt", "internal credit configuration identity differs")
    retained = connection.execute("SELECT artifact_id,manifest FROM uta_credit_code_artifacts").fetchall()
    if (len(retained) != 1 or retained[0][0] != current_id
            or artifact.parse_credit_artifact(retained[0][1], expected_id=current_id) != current):
        raise CreditV2Error("credit_v2_corrupt", "actual current credit code artifact is not retained")
    allocation = envelope.static_descriptor.allocation_for("BTC", envelope.static_descriptor.shard)
    expected = (allocation.allocation_id, envelope.static_descriptor.descriptor_id,
        envelope.static_descriptor.certificate_id, authority_id, allocation.shard, "BTC", 8, str(allocation.limit_units))
    if [tuple(item) for item in connection.execute("SELECT * FROM credit_v2_allocations")] != [expected]:
        raise CreditV2Error("credit_v2_corrupt", "actual local immutable allocation differs")
    return envelope


@dataclass(frozen=True)
class _IntakeContext:
    guard: object
    process_id: int
    thread_id: int
    source: SyntheticCreditSource


@dataclass(frozen=True)
class _MetadataContext:
    guard: object
    credit: object
    process_id: int
    thread_id: int
    operation: str
    market_snapshot: object


@dataclass(frozen=True)
class _RejectionContext:
    guard: object
    credit: object
    process_id: int
    thread_id: int
    source: SyntheticCreditSource
    error_payload: str


def _poison(guard, message, *, code="credit_v2_guard_failed", cause=None):
    from .writer_fence import WriterFenceError
    error = WriterFenceError(code, message)
    if cause is not None:
        error.__cause__ = cause
    guard._deny(error)
    return error


def _actual_guard(database, connection, role):
    from .writer_fence import _REGISTRY, _REGISTRY_LOCK, _assert_token
    with _REGISTRY_LOCK:
        guard = _REGISTRY.get(id(connection))
    if (guard is None or guard.connection is not connection or guard.database is not database
            or guard.role != role or guard.credit_owner_thread != get_ident()
            or not connection.in_transaction):
        raise CreditV2Error("credit_v2_context_invalid", "internal credit requires its exact guarded transaction role")
    if guard.state is None or guard.state.get("credit_format") != 2:
        raise CreditV2Error("credit_v2_not_active", "this authority has no complete internal credit capability")
    if guard.denied is not None:
        raise guard.denied
    if role == "financial":
        try:
            _assert_token(database, guard.state, database.writer_token)
        except StorageError as cause:
            raise _poison(guard, "actual internal credit token is no longer valid", cause=cause) from cause
    return guard


def _sql_value(value):
    if value is None:
        return ["null", None]
    if type(value) is str:
        return ["text", value]
    if type(value) is int:
        return ["integer", str(value)]
    if type(value) is bytes:
        return ["blob", value.hex()]
    if type(value) is float:
        return ["real", value.hex()]
    raise CreditV2Error("credit_v2_state_invalid", "unsupported actual SQLite value type")


def _snapshot_tables(connection, tables):
    from .writer_fence import _quote
    result = {}
    for table in tables:
        columns = tuple(row[1] for row in connection.execute("PRAGMA table_info(" + _quote(table) + ")"))
        rows = tuple(sorted((tuple(row) for row in connection.execute("SELECT * FROM " + _quote(table))),
            key=lambda row: _canonical([_sql_value(value) for value in row])))
        result[table] = (columns, rows)
    return MappingProxyType(result)


def _snapshot_database(connection):
    """An immutable starting snapshot, never observed-effect counters.

    Raw rows remain private in this transaction. Only nonsecret table hashes
    become persisted isolation evidence. Writer lease state is verified by the
    original fence; SQLite allocation bookkeeping is not financial state.
    """
    tables = tuple(sorted(row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        if not row[0].startswith(("writer_fence_", "sqlite_")) and row[0] not in ("uta_market", "uta_market_history")))
    return _snapshot_tables(connection, tables)


def _isolation_payload(snapshot):
    return _canonical({table: _digest(_canonical({"columns": list(columns),
        "rows": [[_sql_value(value) for value in row] for row in rows]}))
        for table, (columns, rows) in snapshot.items() if not table.startswith("auth_")})


def _fresh_guard(guard):
    if getattr(guard, "credit_v2_context", None) is not None or getattr(guard, "credit_v2_operation", None) is not None:
        raise _poison(guard, "one internal command is permitted per financial transaction")
    if _snapshot_database(guard.connection) != guard.credit_v2_baseline:
        raise _poison(guard, "unscoped staged state precedes the internal command")


def _head(connection):
    row = connection.execute("SELECT sequence,event_hash,sealed FROM ledger_events ORDER BY sequence DESC LIMIT 1").fetchone()
    if row is None:
        return {"sequence": 0, "event_hash": "0" * 64}
    if row[2] != 1 or type(row[0]) is not int or row[0] >= 2**63 - 1:
        raise CreditV2Error("credit_v2_state_invalid", "actual journal head cannot be advanced")
    return {"sequence": row[0], "event_hash": row[1]}


def _stamp_actual(exchange):
    return exchange._now().astimezone(timezone.utc).isoformat(timespec="microseconds")


@contextmanager
def synthetic_intake_scope(database, connection, *, canonical_source):
    """Explicit local synthetic intake only; no financial role or token."""
    guard = _actual_guard(database, connection, "inbox")
    _fresh_guard(guard)
    source = parse_source(canonical_source.canonical_payload if type(canonical_source) is SyntheticCreditSource else canonical_source)
    if source.authority_id != guard.state["authority_id"]:
        raise CreditV2Error("credit_v2_source_invalid", "source authority differs from the actual shard")
    if connection.execute("SELECT 1 FROM credit_commands WHERE command_id=? LIMIT 1", (source.command_id,)).fetchone():
        raise CreditV2Error("credit_v2_legacy_post_unsupported", "legacy receipt cannot be backfilled with a new native source")
    if connection.execute("SELECT 1 FROM uta_accounts WHERE account_id=?", (source.account_id,)).fetchone() is None:
        from .service import ServiceError
        raise ServiceError("account_not_found", "unknown account", 404)
    guard.credit_v2_context = _IntakeContext(guard, os.getpid(), get_ident(), source)
    guard.credit_v2_active = True
    try:
        yield source
    finally:
        guard.credit_v2_active = False


@contextmanager
def metadata_scope(credit, connection, *, operation):
    """Only explicit internal halt/market metadata; never cash or positions."""
    guard = _actual_guard(credit.database, connection, "financial")
    _fresh_guard(guard)
    if operation not in ("SET_HALT", "PUBLISH_MARKET"):
        raise CreditV2Error("credit_v2_metadata_unsupported", "unsupported internal metadata operation")
    market_snapshot = _snapshot_tables(connection, ("uta_market", "uta_market_history")) if operation == "PUBLISH_MARKET" else None
    guard.credit_v2_context = _MetadataContext(guard, credit, os.getpid(), get_ident(), operation, market_snapshot)
    guard.credit_v2_active = True
    try:
        yield
    except BaseException as cause:
        raise _poison(guard, "internal metadata operation failed", cause=cause) from cause
    finally:
        guard.credit_v2_active = False


@contextmanager
def rejection_scope(credit, connection, *, command_id, error):
    """Only business REJECTED after actual SQL rollback, never a money scope."""
    from .service import ServiceError
    guard = _actual_guard(credit.database, connection, "financial")
    if _snapshot_database(connection) != guard.credit_v2_baseline:
        raise _poison(guard, "business rejection requires actual complete savepoint rollback")
    source = read_source(connection, command_id, expected_authority_id=guard.state["authority_id"])
    _, fifo, _ = _runtime_dependencies()
    if type(error) is not ServiceError or not fifo.is_business_rejection(source.kind, error):
        raise _poison(guard, "technical or unknown outcome cannot become a business rejection")
    guard.credit_v2_context = _RejectionContext(guard, credit, os.getpid(), get_ident(), source,
        _canonical({"code": error.code, "message": str(error), "status": error.status}))
    guard.credit_v2_active = True
    try:
        yield
    finally:
        guard.credit_v2_active = False


def _repay_plan(credit, connection, account_id, units, before):
    from .service import ServiceError
    state = {key: (value if key == "version" else int(value)) for key, value in before.items()}
    principal, interest = state["principal_units"], state["interest_units"]
    if units > principal + interest:
        raise ServiceError("repayment_exceeds_debt", "repayment exceeds outstanding principal and interest", 409)
    available = credit.exchange._available_asset(connection, account_id, "BTC")
    if credit._codec._units("BTC", available) < units:
        raise ServiceError("insufficient_cash", "settled available cash is insufficient for repayment", 409)
    paid_interest = min(units, interest)
    paid_principal = units - paid_interest
    after = dict(state)
    for key, change in (("cash_units", -units), ("principal_units", -paid_principal), ("interest_units", -paid_interest),
        ("principal_ledger_units", paid_principal), ("interest_ledger_units", paid_interest),
        ("shard_principal_units", -paid_principal), ("shard_interest_units", -paid_interest),
        ("pool_units", paid_principal), ("principal_receivable_units", -paid_principal), ("interest_receivable_units", -paid_interest)):
        after[key] += change
    after["version"] += 1
    from .credit_transition import _snapshot
    after_wire = {key: (value if key == "version" else str(value)) for key, value in after.items()}
    _snapshot(after_wire, require_increment=False)
    legs = [("customer:" + account_id, "BTC", -units)]
    for paid, cash, liability, receivable in ((paid_interest, "system:credit-interest-cash", "liability:interest:" + account_id, "system:credit-interest-receivable"),
        (paid_principal, "system:credit-pool", "liability:principal:" + account_id, "system:credit-principal-receivable")):
        if paid:
            legs.extend(((cash, "BTC", paid), (liability, "BTC", paid), (receivable, "BTC", -paid)))
    return after_wire, tuple(sorted(legs))


@contextmanager
def operation_scope(credit, connection, *, command_id):
    """Stage trusted actual intent/legs before one original loan or repayment."""
    from .credit import CreditService
    from .credit_audit_v2 import read_credit_snapshot, borrow_operation_id
    from .credit_transition import calculate_borrow_transition, CreditTransitionError
    from .credit_native import _verify_financial_source
    from .service import ServiceError, _key
    if type(credit) is not CreditService:
        raise CreditV2Error("credit_v2_context_invalid", "operation needs its real initialized credit service")
    guard = _actual_guard(credit.database, connection, "financial")
    _fresh_guard(guard)
    _verify_financial_source(credit.database, connection, credit.exchange.scales)
    source = read_source(connection, command_id, expected_authority_id=guard.state["authority_id"])
    inbox = connection.execute("SELECT * FROM uta_command_inbox WHERE command_id=?", (command_id,)).fetchone()
    if inbox is None or inbox["state"] != "PENDING":
        raise CreditV2Error("credit_v2_context_invalid", "native operation requires its original pending command")
    if connection.execute("SELECT 1 FROM uta_command_inbox WHERE state='PENDING' AND account_id=? AND sequence<?",
                          (source.account_id, inbox["sequence"])).fetchone():
        raise CreditV2Error("credit_v2_fifo_conflict", "an earlier account command is still pending")
    command = _document(source.command_payload, code="credit_v2_source_invalid")
    asset, amount = command["asset"], Decimal(command["amount"])
    units, amount_text, scope = credit._prepare(source.account_id, command_id, asset, amount)
    if connection.execute("SELECT 1 FROM credit_commands WHERE scope=? AND command_id=?", (scope, command_id)).fetchone():
        raise CreditV2Error("credit_v2_legacy_post_unsupported", "existing receipt must be queried rather than executed again")
    marker = connection.execute("SELECT singleton,format,state,capability_id,payload FROM writer_fence_credit_v2_capability").fetchone()
    envelope = load_marker(connection, marker, authority_id=guard.state["authority_id"])
    static = envelope.static_descriptor
    before, limits = read_credit_snapshot(credit.exchange, credit, connection, source.account_id, asset,
        require_limits=source.kind == "BORROW", require_increment=True)
    account = credit.exchange._audit_state(connection, source.account_id)
    selected = sid = risk = quote_units = step_units = None
    head = _head(connection)
    if source.kind == "BORROW":
        credit.exchange._require_exposure_allowed(connection, source.account_id)
        market = credit.exchange._market(connection)
        if asset not in market.assets:
            raise ServiceError("market_incomplete", "borrowed asset has no trusted price", 503)
        selected = _stamp_actual(credit.exchange)
        from .credit_audit_v2 import utc_checkpoint
        if utc_checkpoint(selected) < utc_checkpoint(json.loads(source.canonical_payload)["accepted_at"]):
            raise CreditV2Error("credit_v2_clock_regression", "actual borrower clock precedes its original accepted source")
        market.validate(now=utc_checkpoint(selected), max_age=credit.exchange.max_price_age,
                        max_future_skew=timedelta(seconds=1))
        sid = credit.exchange.audit.market_ref(connection, market)
        risk = credit.exchange._risk(connection, source.account_id, market)
        rule = credit.exchange.portfolio_rules.borrow_limits.get(asset)
        if rule is None:
            raise ServiceError("credit_disabled", "asset is not enabled by the versioned borrow policy", 409)
        quotes = risk.get("borrowable")
        if type(quotes) is not dict or asset not in quotes:
            raise ServiceError("credit_policy_unavailable", "versioned risk did not provide a borrow quote", 503)
        quote_units = str(credit._codec._units(asset, Decimal(quotes[asset])))
        step_units = str(credit._codec._units(asset, rule.quantity_step))
        if units % int(step_units):
            raise ServiceError("invalid_input", "borrow amount violates the configured quantity step")
        try:
            transition = calculate_borrow_transition(descriptor=static, account_id=source.account_id,
                asset=asset, amount_units=str(units), before=before, limits=limits,
                quote_units=quote_units, quantity_step_units=step_units)
        except CreditTransitionError as cause:
            if 400 <= cause.status < 500:
                raise ServiceError(cause.code, str(cause), cause.status) from cause
            raise
        after = {key: (value if key == "version" else str(value)) for key, value in transition.after.items()}
        legs = tuple((name, asset, value) for name, value in transition.postings)
    else:
        after, legs = _repay_plan(credit, connection, source.account_id, units, before)
    prestate = _canonical({"account": account, "credit": before, "limits": limits, "selected_at": selected,
        "market_snapshot_id": sid, "risk": risk, "quote_units": quote_units,
        "quantity_step_units": step_units, "journal_head": head})
    isolation = _isolation_payload(guard.credit_v2_baseline)
    allocation = static.allocation_for(asset, static.shard)
    journal_id = _key("credit", scope, command_id)
    values = {"command_id": command_id, "account_id": source.account_id, "scope": scope,
        "operation_kind": source.kind, "inbox_kind": source.kind,
        "credit_kind": "borrowed" if source.kind == "BORROW" else "repaid", "asset": asset,
        "amount": amount_text, "amount_units": str(units), "payload_hash": source.payload_hash,
        "source_id": source.source_id, "authority_id": source.authority_id,
        "allocation_id": allocation.allocation_id, "descriptor_id": static.descriptor_id,
        "intent_digest": "", "journal_id": journal_id, "pre_state_payload": prestate,
        "pre_state_hash": _digest(prestate), "isolation_payload": isolation, "isolation_hash": _digest(isolation),
        "journal_sealed": 1, "terminal_state": "SUCCEEDED", "operation_id": borrow_operation_id(source.account_id, command_id) if source.kind == "BORROW" else None,
        "decision_kind": "CREDIT_BORROWED" if source.kind == "BORROW" else None,
        "market_dependency": "SID" if source.kind == "BORROW" else "NONE", "market_snapshot_id": sid,
        "selected_at": selected, "expected_postings": len(legs),
        "old_principal_units": before["principal_units"], "old_interest_units": before["interest_units"],
        "new_principal_units": after["principal_units"], "new_interest_units": after["interest_units"],
        "pre_version": before["version"], "post_version": after["version"]}
    values["intent_digest"] = "credit-intent:" + _digest(_canonical({key: value for key, value in values.items() if key != "intent_digest"}))
    intent_row = tuple(values[name] for name in _INTENT_COLUMNS)
    view = CreditOperationView(source.kind, source.account_id, command_id, asset, amount_text, units,
        envelope.capability_id, static, allocation.allocation_id, journal_id, source.payload_hash,
        source.source_id, source.actor_id, source.canonical_payload, values["intent_digest"], before["version"],
        prestate, values["pre_state_hash"], selected, sid)
    balances = tuple((name, currency, credit._codec._units(currency, credit.ledger.balance(name, currency, connection=connection)))
                     for name, currency, _ in legs)
    context = _CreditOperation(guard, credit, os.getpid(), get_ident(), guard.state["generation"],
        view, intent_row, legs, _canonical(after), balances)
    guard.credit_v2_operation = context
    guard.credit_v2_context = context
    guard.credit_v2_active = True
    try:
        connection.execute("INSERT INTO credit_v2_intents(" + ",".join(_INTENT_COLUMNS) + ") VALUES(" + ",".join("?" for _ in _INTENT_COLUMNS) + ")", intent_row)
        connection.executemany("INSERT INTO credit_v2_expected_postings VALUES(?,?,?,?,?)",
            ((command_id, ordinal, name, currency, str(value)) for ordinal, (name, currency, value) in enumerate(legs)))
        try:
            yield view
        except ServiceError as cause:
            # The real caller SAVEPOINT must roll back all rows before the
            # separately constrained rejection_scope can record REJECTED.
            _, fifo, _ = _runtime_dependencies()
            if (source.kind == "BORROW" and cause.code in {"market_unavailable", "market_incomplete", "risk_unavailable"}
                    or not fifo.is_business_rejection(source.kind, cause)):
                raise _poison(guard, "late financial validation cannot become a normal rejection", cause=cause) from cause
            raise
        except BaseException as cause:
            raise _poison(guard, "internal financial operation failed", cause=cause) from cause
        try:
            _verify_operation(guard, context)
        except BaseException as cause:
            raise _poison(guard, "actual internal credit closing validation failed", cause=cause) from cause
    finally:
        guard.credit_v2_active = False


def _effect_definitions():
    """Every financial effect checks an actual matching intent plus live scope."""
    result = {}
    def add(name, table, clause, predicate):
        sql = (f"CREATE TRIGGER {name} {clause} ON {table} BEGIN SELECT CASE WHEN ({predicate}) THEN 1 "
            "ELSE CASE WHEN uta_credit_v2_deny('protected_mutation')=0 THEN RAISE(ABORT,'actual native credit scope and staged obligation required') END END; END")
        result[name] = (table, sql)
    def gate(phase, *fields):
        return "uta_credit_v2_gate('" + phase + "'," + ",".join(fields) + ")=1"
    def intent(predicate, phase, *fields):
        return ("EXISTS(SELECT 1 FROM credit_v2_intents i WHERE " + predicate + " AND "
                + gate(phase, "i.command_id", "i.intent_digest", *fields) + ")")
    source_columns = ("command_id", "source_id", "account_id", "kind", "payload_hash", "source_kind",
                      "actor_id", "source_reference", "authority_id", "command_payload", "payload")
    add("credit_v2_gate_source", "credit_v2_sources", "BEFORE INSERT",
        gate("SOURCE", *("NEW." + name for name in source_columns)))
    add("credit_v2_gate_inbox_insert", "uta_command_inbox", "BEFORE INSERT",
        "EXISTS(SELECT 1 FROM credit_v2_sources s WHERE s.command_id=NEW.command_id AND s.account_id=NEW.account_id "
        "AND s.kind=NEW.kind AND s.command_payload=NEW.payload) AND "
        + gate("INBOX_INSERT", *("NEW." + name for name in ("command_id", "account_id", "kind", "payload", "state", "result", "error", "completed_at", "attempts", "last_error", "next_attempt_at"))))
    add("credit_v2_gate_inbox_update", "uta_command_inbox", "BEFORE UPDATE",
        "EXISTS(SELECT 1 FROM credit_v2_sources s WHERE s.command_id=NEW.command_id AND s.account_id=NEW.account_id "
        "AND s.kind=NEW.kind AND s.command_payload=NEW.payload) AND "
        "((NEW.state='SUCCEEDED' AND EXISTS(SELECT 1 FROM credit_v2_intents i JOIN credit_commands c "
        "ON c.scope=i.scope AND c.command_id=i.command_id WHERE i.command_id=NEW.command_id "
        "AND i.account_id=NEW.account_id AND i.inbox_kind=NEW.kind AND i.journal_id=c.journal_event_id AND c.result=NEW.result)) "
        "OR (NEW.state='REJECTED' AND NOT EXISTS(SELECT 1 FROM credit_v2_intents i WHERE i.command_id=NEW.command_id) "
        "AND NOT EXISTS(SELECT 1 FROM credit_commands c WHERE c.scope='account:'||NEW.account_id AND c.command_id=NEW.command_id))) AND "
        + gate("INBOX_UPDATE", *("NEW." + name for name in ("command_id", "account_id", "kind", "payload", "state", "result", "error", "completed_at")), "OLD.state"))
    add("credit_v2_gate_intent", "credit_v2_intents", "BEFORE INSERT",
        "EXISTS(SELECT 1 FROM credit_v2_sources s WHERE s.command_id=NEW.command_id AND s.source_id=NEW.source_id "
        "AND s.account_id=NEW.account_id AND s.kind=NEW.inbox_kind AND s.payload_hash=NEW.payload_hash) AND "
        + gate("INTENT", *("NEW." + name for name in _INTENT_COLUMNS)))
    add("credit_v2_gate_expected", "credit_v2_expected_postings", "BEFORE INSERT",
        intent("i.command_id=NEW.command_id", "EXPECTED", "NEW.ordinal", "NEW.account", "NEW.asset", "NEW.units"))
    for action in ("INSERT", "UPDATE"):
        old = ("NULL", "NULL") if action == "INSERT" else ("OLD.principal", "OLD.interest")
        add("credit_v2_gate_debt_" + action.lower(), "uta_liabilities", "BEFORE " + action,
            intent("i.account_id=NEW.account_id AND i.asset=NEW.asset", "DEBT_" + action,
                   "NEW.account_id", "NEW.asset", "NEW.principal", "NEW.interest", *old))
    add("credit_v2_gate_debt_delete", "uta_liabilities", "BEFORE DELETE", "0")
    add("credit_v2_gate_account", "uta_accounts", "BEFORE UPDATE",
        intent("i.account_id=NEW.account_id", "ACCOUNT", "NEW.account_id", "OLD.version", "NEW.version"))
    for action in ("INSERT", "UPDATE"):
        add("credit_v2_gate_journal_" + action.lower(), "ledger_events", "BEFORE " + action,
            intent("i.journal_id=NEW.event_id", "JOURNAL_" + action,
                   *("NEW." + name for name in ("sequence", "event_id", "fingerprint", "previous_hash", "event_hash", "sealed"))))
        old = "NULL" if action == "INSERT" else "OLD.units"
        add("credit_v2_gate_balance_" + action.lower(), "ledger_balances", "BEFORE " + action,
            intent("EXISTS(SELECT 1 FROM credit_v2_expected_postings x WHERE x.command_id=i.command_id AND x.account=NEW.account AND x.asset=NEW.asset)",
                   "BALANCE_" + action, "NEW.account", "NEW.asset", "NEW.units", old))
    add("credit_v2_gate_posting", "ledger_postings", "BEFORE INSERT",
        intent("EXISTS(SELECT 1 FROM ledger_events e WHERE e.event_id=i.journal_id AND e.sequence=NEW.sequence) "
            "AND EXISTS(SELECT 1 FROM credit_v2_expected_postings x WHERE x.command_id=i.command_id AND x.ordinal=NEW.ordinal "
            "AND x.account=NEW.account AND x.asset=NEW.asset AND x.units=NEW.units)",
            "POSTING", "NEW.sequence", "NEW.ordinal", "NEW.account", "NEW.asset", "NEW.units"))
    closure = ("i.scope=NEW.scope AND i.command_id=NEW.command_id AND i.credit_kind=NEW.kind AND i.asset=NEW.asset "
        "AND i.amount=NEW.amount AND i.journal_id=NEW.journal_event_id "
        "AND EXISTS(SELECT 1 FROM ledger_events e WHERE e.event_id=i.journal_id AND e.sealed=1 "
        "AND (SELECT COUNT(*) FROM ledger_postings p WHERE p.sequence=e.sequence)=i.expected_postings "
        "AND (SELECT COUNT(*) FROM credit_v2_expected_postings x WHERE x.command_id=i.command_id)=i.expected_postings "
        "AND NOT EXISTS(SELECT 1 FROM credit_v2_expected_postings x WHERE x.command_id=i.command_id AND NOT EXISTS(SELECT 1 FROM ledger_postings p "
        "WHERE p.sequence=e.sequence AND p.ordinal=x.ordinal AND p.account=x.account AND p.asset=x.asset AND p.units=x.units))) "
        "AND (i.operation_kind='REPAY' OR EXISTS(SELECT 1 FROM uta_credit_decisions d WHERE d.operation_id=i.operation_id "
        "AND d.kind=i.decision_kind AND d.account_id=i.account_id AND d.command_id=i.command_id AND d.journal_id=i.journal_id "
        "AND d.source_id=i.source_id AND d.descriptor_id=i.descriptor_id AND d.allocation_id=i.allocation_id AND d.market_snapshot_id=i.market_snapshot_id))")
    add("credit_v2_gate_record", "credit_commands", "BEFORE INSERT",
        intent(closure, "RECORD", *("NEW." + name for name in ("scope", "command_id", "kind", "asset", "amount", "source_reference", "result", "journal_event_id", "created_at"))))
    add("credit_v2_gate_decision", "uta_credit_decisions", "BEFORE INSERT",
        intent("i.operation_kind='BORROW' AND i.command_id=NEW.command_id AND i.account_id=NEW.account_id "
            "AND i.operation_id=NEW.operation_id AND i.journal_id=NEW.journal_id AND i.payload_hash=NEW.payload_hash "
            "AND i.source_id=NEW.source_id AND i.descriptor_id=NEW.descriptor_id AND i.allocation_id=NEW.allocation_id "
            "AND i.market_snapshot_id=NEW.market_snapshot_id AND i.pre_version=NEW.pre_version AND i.post_version=NEW.post_version "
            "AND EXISTS(SELECT 1 FROM credit_v2_config c WHERE c.artifact_id=NEW.artifact_id AND c.policy_id=NEW.policy_id)",
            "DECISION", "NEW.payload", "NEW.decision_id"))
    event_gate = gate("SERVICE_EVENT", "NEW.event_type", "NEW.account_id", "NEW.payload", "NEW.created_at")
    add("credit_v2_gate_service_event", "uta_events", "BEFORE INSERT",
        "((NEW.event_type IN ('KILL_SWITCH_CHANGED','MARKET_PUBLISHED')) AND " + event_gate + ") OR "
        "EXISTS(SELECT 1 FROM credit_v2_intents i JOIN credit_commands c ON c.scope=i.scope AND c.command_id=i.command_id "
        "WHERE NEW.account_id=i.account_id AND NEW.event_type='CREDIT_'||upper(i.credit_kind) AND c.result=NEW.payload AND " + event_gate + ")")
    add("credit_v2_gate_config", "uta_config", "BEFORE INSERT", gate("CONFIG", "NEW.key", "NEW.value"))
    add("credit_v2_gate_config_update", "uta_config", "BEFORE UPDATE", gate("CONFIG", "NEW.key", "NEW.value"))
    add("credit_v2_gate_market", "uta_market", "BEFORE INSERT", gate("MARKET", "NEW.singleton", "NEW.payload"))
    add("credit_v2_gate_market_update", "uta_market", "BEFORE UPDATE", gate("MARKET", "NEW.singleton", "NEW.payload"))
    add("credit_v2_gate_market_history", "uta_market_history", "BEFORE INSERT",
        gate("MARKET_HISTORY", "NEW.snapshot_id", "NEW.content_digest", "NEW.payload", "NEW.origin", "NEW.recorded_at"))
    return MappingProxyType(result)


CATALOG_OBJECT_SQL = OBJECT_SQL  # Explicit primitive-only storage test catalog.
EFFECT_TRIGGER_SQL = _effect_definitions()
TRIGGER_SQL = MappingProxyType({**TRIGGER_SQL, **EFFECT_TRIGGER_SQL})
OBJECT_SQL = MappingProxyType({**TABLE_SQL, **INDEX_SQL,
    **{name: sql for name, (_, sql) in TRIGGER_SQL.items()}})
