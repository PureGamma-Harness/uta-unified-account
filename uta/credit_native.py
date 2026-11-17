"""Fresh-only, irreversible native credit preparation; no trading activation.

Format 1 is deliberately NATIVE_PREPARED. It cannot acquire a writer lease or
authorize credit, orders, repayment, READY or activation. A later separately
reviewed format must supply complete audit, source and replay capabilities.
"""
from contextlib import contextmanager
from decimal import Decimal
from hashlib import sha256
import json
from threading import get_ident
from types import MappingProxyType

from .storage import Database, DurableLedger, StorageError


FORMAT, STAGE = 1, "NATIVE_PREPARED"
TRADING_FORMATS = ()  # No format in this delivery grants financial permission.


class CreditNativeError(StorageError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


TABLE_SQL = MappingProxyType({
    "credit_native_schema": "CREATE TABLE credit_native_schema(singleton INTEGER PRIMARY KEY CHECK(singleton=1),format INTEGER NOT NULL CHECK(format=1),descriptor_id TEXT NOT NULL,opening_ledger_sequence INTEGER NOT NULL CHECK(opening_ledger_sequence>=0),opening_event_sequence INTEGER NOT NULL CHECK(opening_event_sequence>=0),opening_credit_count INTEGER NOT NULL CHECK(opening_credit_count>=0))",
    "credit_native_policies": "CREATE TABLE credit_native_policies(policy_id TEXT PRIMARY KEY NOT NULL,payload TEXT NOT NULL)",
    "credit_native_certificates": "CREATE TABLE credit_native_certificates(certificate_id TEXT PRIMARY KEY NOT NULL,payload TEXT NOT NULL)",
    "credit_native_allocations": "CREATE TABLE credit_native_allocations(allocation_id TEXT PRIMARY KEY NOT NULL,certificate_id TEXT NOT NULL REFERENCES credit_native_certificates(certificate_id),authority_id TEXT NOT NULL,asset TEXT NOT NULL,limit_units TEXT NOT NULL,opening_principal_units TEXT NOT NULL,opening_interest_units TEXT NOT NULL,opening_pool_units TEXT NOT NULL,UNIQUE(allocation_id,authority_id,asset))",
    "credit_native_sources": "CREATE TABLE credit_native_sources(command_id TEXT PRIMARY KEY NOT NULL,source_id TEXT NOT NULL UNIQUE,account_id TEXT NOT NULL,payload_hash TEXT NOT NULL,source_kind TEXT NOT NULL CHECK(source_kind IN ('hmac','synthetic_local')),payload TEXT NOT NULL,UNIQUE(source_id,command_id,account_id,payload_hash))",
    "credit_native_intents": """CREATE TABLE credit_native_intents(
      command_id TEXT PRIMARY KEY NOT NULL,account_id TEXT NOT NULL,scope TEXT NOT NULL,
      operation_kind TEXT NOT NULL CHECK(operation_kind IN ('BORROW','REPAY')),
      inbox_kind TEXT NOT NULL,credit_kind TEXT NOT NULL,asset TEXT NOT NULL,
      amount TEXT NOT NULL,units TEXT NOT NULL,payload_hash TEXT NOT NULL,intent_digest TEXT NOT NULL,
      journal_id TEXT NOT NULL,sealed INTEGER NOT NULL CHECK(typeof(sealed)='integer' AND sealed=1),
      decision_id TEXT,decision_kind TEXT,terminal_state TEXT NOT NULL CHECK(terminal_state='SUCCEEDED'),
      allocation_id TEXT NOT NULL,authority_id TEXT NOT NULL,policy_id TEXT NOT NULL,
      source_id TEXT NOT NULL,expected_postings INTEGER NOT NULL CHECK(expected_postings IN (4,7)),
      old_principal TEXT NOT NULL,old_interest TEXT NOT NULL,new_principal TEXT NOT NULL,new_interest TEXT NOT NULL,
      CHECK(scope='account:'||account_id),
      CHECK((operation_kind='BORROW' AND inbox_kind='BORROW' AND credit_kind='borrowed' AND expected_postings=4
        AND decision_id IS NOT NULL AND decision_kind IS NOT NULL AND decision_kind='CREDIT_BORROWED')
        OR(operation_kind='REPAY' AND inbox_kind='REPAY' AND credit_kind='repaid' AND decision_id IS NULL AND decision_kind IS NULL)),
      FOREIGN KEY(command_id,account_id,inbox_kind,terminal_state) REFERENCES uta_command_inbox(command_id,account_id,kind,state) DEFERRABLE INITIALLY DEFERRED,
      FOREIGN KEY(scope,command_id,credit_kind,asset,amount,journal_id) REFERENCES credit_commands(scope,command_id,kind,asset,amount,journal_event_id) DEFERRABLE INITIALLY DEFERRED,
      FOREIGN KEY(decision_id,decision_kind,account_id,command_id) REFERENCES uta_risk_decisions(decision_id,kind,account_id,business_id) DEFERRABLE INITIALLY DEFERRED,
      FOREIGN KEY(journal_id,sealed) REFERENCES ledger_events(event_id,sealed) DEFERRABLE INITIALLY DEFERRED,
      FOREIGN KEY(allocation_id,authority_id,asset) REFERENCES credit_native_allocations(allocation_id,authority_id,asset) DEFERRABLE INITIALLY DEFERRED,
      FOREIGN KEY(policy_id) REFERENCES credit_native_policies(policy_id) DEFERRABLE INITIALLY DEFERRED,
      FOREIGN KEY(source_id,command_id,account_id,payload_hash) REFERENCES credit_native_sources(source_id,command_id,account_id,payload_hash) DEFERRABLE INITIALLY DEFERRED)""",
    "credit_native_expected_postings": "CREATE TABLE credit_native_expected_postings(command_id TEXT NOT NULL REFERENCES credit_native_intents(command_id) DEFERRABLE INITIALLY DEFERRED,ordinal INTEGER NOT NULL CHECK(ordinal>=0 AND ordinal<7),account TEXT NOT NULL,asset TEXT NOT NULL,units TEXT NOT NULL,PRIMARY KEY(command_id,ordinal))",
    "credit_native_legacy_commands": "CREATE TABLE credit_native_legacy_commands(scope TEXT NOT NULL,command_id TEXT NOT NULL,kind TEXT NOT NULL,asset TEXT NOT NULL,amount TEXT NOT NULL,journal_id TEXT NOT NULL,result_hash TEXT NOT NULL,PRIMARY KEY(scope,command_id))",
})

INDEX_SQL = MappingProxyType({
    "credit_native_inbox_parent": "CREATE UNIQUE INDEX credit_native_inbox_parent ON uta_command_inbox(command_id,account_id,kind,state)",
    "credit_native_command_parent": "CREATE UNIQUE INDEX credit_native_command_parent ON credit_commands(scope,command_id,kind,asset,amount,journal_event_id)",
    "credit_native_decision_parent": "CREATE UNIQUE INDEX credit_native_decision_parent ON uta_risk_decisions(decision_id,kind,account_id,business_id)",
    "credit_native_journal_parent": "CREATE UNIQUE INDEX credit_native_journal_parent ON ledger_events(event_id,sealed)",
})


def _triggers():
    result = {}
    keys = {name: ("singleton",) if name == "credit_native_schema" else
            ("policy_id",) if name == "credit_native_policies" else
            ("certificate_id",) if name == "credit_native_certificates" else
            ("allocation_id",) if name == "credit_native_allocations" else
            ("scope", "command_id") if name == "credit_native_legacy_commands" else
            ("command_id", "ordinal") if name == "credit_native_expected_postings" else ("command_id",)
            for name in TABLE_SQL}
    for table, columns in keys.items():
        for action in ("UPDATE", "DELETE"):
            result[f"{table}_no_{action.lower()}"] = (table,
                f"CREATE TRIGGER {table}_no_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'credit native history is immutable'); END")
        predicate = " AND ".join(f"{column}=NEW.{column}" for column in columns)
        result[table + "_no_replace"] = (table,
            f"CREATE TRIGGER {table}_no_replace BEFORE INSERT ON {table} WHEN EXISTS(SELECT 1 FROM {table} WHERE {predicate}) BEGIN SELECT RAISE(ABORT,'credit native identity cannot replace'); END")
    result["credit_native_intent_gate"] = ("credit_native_intents", """CREATE TRIGGER credit_native_intent_gate BEFORE INSERT ON credit_native_intents BEGIN
      SELECT CASE WHEN uta_credit_operation_v1('INTENT',NEW.command_id,NEW.intent_digest)!=1
        THEN RAISE(ABORT,'authorized credit intent scope required') END; END""")
    for action in ("INSERT", "UPDATE", "DELETE"):
        alias = "OLD" if action == "DELETE" else "NEW"
        result["credit_native_debt_" + action.lower()] = ("uta_liabilities", f"""CREATE TRIGGER credit_native_debt_{action.lower()} BEFORE {action} ON uta_liabilities BEGIN
          SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM credit_native_intents i WHERE i.account_id={alias}.account_id
            AND i.asset={alias}.asset AND uta_credit_operation_v1('DEBT',i.command_id,i.intent_digest)=1)
            THEN RAISE(ABORT,'actual authorized credit debt intent required') END; END""")
    result["credit_native_posting_gate"] = ("ledger_postings", """CREATE TRIGGER credit_native_posting_gate BEFORE INSERT ON ledger_postings
      WHEN NEW.account LIKE 'system:credit-%' OR NEW.account LIKE 'liability:principal:%'
        OR NEW.account LIKE 'liability:interest:%'
        OR EXISTS(SELECT 1 FROM credit_native_intents i JOIN ledger_events e ON e.event_id=i.journal_id WHERE e.sequence=NEW.sequence)
      BEGIN SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM credit_native_intents i JOIN ledger_events e ON e.event_id=i.journal_id
        JOIN credit_native_expected_postings x ON x.command_id=i.command_id WHERE e.sequence=NEW.sequence
        AND x.ordinal=NEW.ordinal AND x.account=NEW.account AND x.asset=NEW.asset AND x.units=NEW.units
        AND uta_credit_operation_v1('POSTING',i.command_id,i.intent_digest)=1)
        THEN RAISE(ABORT,'actual authorized complete credit postings required') END; END""")
    result["credit_native_record_gate"] = ("credit_commands", """CREATE TRIGGER credit_native_record_gate BEFORE INSERT ON credit_commands BEGIN
      SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM credit_native_intents i JOIN ledger_events e ON e.event_id=i.journal_id AND e.sealed=1
        WHERE i.command_id=NEW.command_id AND i.scope=NEW.scope AND i.credit_kind=NEW.kind AND i.asset=NEW.asset
        AND i.amount=NEW.amount AND i.journal_id=NEW.journal_event_id
        AND uta_credit_operation_v1('CREDIT_RECORD',i.command_id,i.intent_digest)=1
        AND (SELECT COUNT(*) FROM credit_native_expected_postings x WHERE x.command_id=i.command_id)=i.expected_postings
        AND (SELECT COUNT(*) FROM ledger_postings p WHERE p.sequence=e.sequence)=i.expected_postings
        AND NOT EXISTS(SELECT 1 FROM credit_native_expected_postings x WHERE x.command_id=i.command_id AND NOT EXISTS(
          SELECT 1 FROM ledger_postings p WHERE p.sequence=e.sequence AND p.ordinal=x.ordinal AND p.account=x.account AND p.asset=x.asset AND p.units=x.units)))
        THEN RAISE(ABORT,'authorized sealed credit closing point required') END; END""")
    return MappingProxyType(result)


TRIGGER_SQL = _triggers()
OBJECT_SQL = MappingProxyType({**TABLE_SQL, **INDEX_SQL,
    **{name: sql for name, (_, sql) in TRIGGER_SQL.items()}})
PROTECTED_TABLES = frozenset(TABLE_SQL) | frozenset({"credit_commands", "uta_liabilities", "ledger_events",
    "ledger_postings", "ledger_balances", "uta_risk_decisions", "uta_market_history", "uta_code_artifacts",
    "uta_risk_policies", "uta_command_inbox"})


def descriptor(raw, *, authority_id, asset_scales=None):
    try:
        from .credit_policy import validate_native_descriptor
    except ImportError as error:
        raise CreditNativeError("credit_policy_unavailable", "native credit policy validator is required") from error
    return validate_native_descriptor(raw, expected_authority_id=authority_id,
                                      expected_asset_scales=asset_scales)


def verify_schema(connection):
    """Exact inventory; never create or repair on a load/read path."""
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
        for action in "IUD":
            name, sql = _guard_sql(table, action)
            expected[name] = ("trigger", table, sql)
    actual = {row[0]: tuple(row)[1:] for row in connection.execute(
        "SELECT name,type,tbl_name,sql FROM sqlite_master WHERE name LIKE 'credit_native_%' OR tbl_name LIKE 'credit_native_%'")}
    # SQLite's implicit parent-key indexes are part of the exact table schema;
    # enumerate their names deterministically from compiled definitions.
    for table in TABLE_SQL:
        for row in connection.execute(f"PRAGMA index_list({table})"):
            if row[1].startswith("sqlite_autoindex_"):
                expected[row[1]] = ("index", table, None)
    if actual != expected:
        raise CreditNativeError("credit_native_schema_corrupt", "native credit object inventory or definitions differ")


def load_marker(connection, row, *, authority_id):
    if len(row) != 5 or tuple(row)[:3] != (1, FORMAT, STAGE):
        raise CreditNativeError("credit_native_corrupt", "unsupported native credit preparation format")
    scales = {item[0]: item[1] for item in connection.execute("SELECT asset,scale FROM ledger_assets")}
    record = descriptor(row[4], authority_id=authority_id, asset_scales=scales)
    if record.descriptor_id != row[3] or record.canonical_payload != row[4]:
        raise CreditNativeError("credit_native_corrupt", "native credit descriptor differs from its canonical identity")
    verify_schema(connection)
    state = connection.execute("SELECT format,descriptor_id FROM credit_native_schema WHERE singleton=1").fetchone()
    if state is None or tuple(state) != (FORMAT, record.descriptor_id):
        raise CreditNativeError("credit_native_corrupt", "native credit schema binding differs")
    policy_id = json.loads(record.canonical_payload)["credit_policy_id"]
    if [tuple(item) for item in connection.execute("SELECT policy_id,payload FROM credit_native_policies")] != [(policy_id, record.policy_payload)]:
        raise CreditNativeError("credit_native_corrupt", "native credit policy archive differs")
    if [tuple(item) for item in connection.execute("SELECT certificate_id,payload FROM credit_native_certificates")] != [(record.certificate_id, record.certificate_payload)]:
        raise CreditNativeError("credit_native_corrupt", "native credit certificate archive differs")
    expected = set()
    for budget in record.assets:
        asset = budget.asset
        allocation = record.allocation_for(asset, record.shard)
        expected.add((allocation.allocation_id, record.certificate_id, record.authority_id, asset,
            str(allocation.limit_units), str(allocation.opening_principal_units),
            str(allocation.opening_interest_units), str(allocation.opening_pool_units)))
    if {tuple(item) for item in connection.execute("SELECT * FROM credit_native_allocations")} != expected:
        raise CreditNativeError("credit_native_corrupt", "native credit allocation archive differs")
    return record


def _insert_preparation(connection, record):
    """Only called by the fixed control installer before marker publication."""
    connection.execute("INSERT INTO credit_native_policies VALUES(?,?)", (json.loads(record.canonical_payload)["credit_policy_id"], record.policy_payload))
    connection.execute("INSERT INTO credit_native_certificates VALUES(?,?)", (record.certificate_id, record.certificate_payload))
    for budget in record.assets:
        asset = budget.asset
        allocation = record.allocation_for(asset, record.shard)
        connection.execute("INSERT INTO credit_native_allocations VALUES(?,?,?,?,?,?,?,?)", (
            allocation.allocation_id, record.certificate_id, record.authority_id, asset,
            str(allocation.limit_units), str(allocation.opening_principal_units),
            str(allocation.opening_interest_units), str(allocation.opening_pool_units)))
    head = connection.execute("SELECT COALESCE(MAX(sequence),0) FROM ledger_events").fetchone()[0]
    event = connection.execute("SELECT COALESCE(MAX(sequence),0) FROM uta_events").fetchone()[0]
    count = connection.execute("SELECT COUNT(*) FROM credit_commands").fetchone()[0]
    connection.execute("INSERT INTO credit_native_schema VALUES(1,1,?,?,?,?)", (record.descriptor_id, head, event, count))
    for row in connection.execute("SELECT scope,command_id,kind,asset,amount,journal_event_id,result FROM credit_commands"):
        connection.execute("INSERT INTO credit_native_legacy_commands VALUES(?,?,?,?,?,?,?)",
            (*tuple(row)[:6], sha256(row[6].encode()).hexdigest()))


def validate_opening(connection, record):
    """Match real shard debt/pool/claims; declarations are not custody proof."""
    from .ledger import Ledger
    scales = {row[0]: row[1] for row in connection.execute("SELECT asset,scale FROM ledger_assets")}
    codec = Ledger(scales)
    for budget in record.assets:
        asset = budget.asset
        allocation = record.allocation_for(asset, record.shard)
        principal = interest = 0
        for row in connection.execute("SELECT principal,interest FROM uta_liabilities WHERE asset=?", (asset,)):
            principal += codec._units(asset, Decimal(row[0]))
            interest += codec._units(asset, Decimal(row[1]))
        pool = connection.execute("SELECT units FROM ledger_balances WHERE account='system:credit-pool' AND asset=?", (asset,)).fetchone()
        pool_units = 0 if pool is None else DurableLedger._stored_units(pool[0])
        if (principal, interest, pool_units) != (allocation.opening_principal_units,
                allocation.opening_interest_units, allocation.opening_pool_units):
            raise CreditNativeError("credit_opening_mismatch", "actual opening debt/pool differs from the allocation")
        actual = {(row[0], row[1], codec._units(asset, Decimal(row[2]))) for row in connection.execute(
            "SELECT source_reference,command_id,amount FROM credit_commands WHERE kind='pool_funded' AND asset=?", (asset,))}
        expected = {(claim.source_reference, claim.command_id, claim.funded_units) for claim in allocation.funding_claims}
        if actual != expected:
            raise CreditNativeError("credit_funding_mismatch", "actual pool funding records differ from the declared claims")


def prepare_credit_native(database, raw_descriptor):
    """Prepare exactly once on generation-zero managed storage; never activate."""
    if not isinstance(database, Database) or database.writer_token is not None:
        raise CreditNativeError("credit_fresh_authority_required", "preparation requires an unbound fresh managed authority")
    from .decision_audit import DecisionAudit
    from .writer_fence import (WriterFence, _load, _observed, _create_credit_object,
                               _create_control_object, _CONTROL_TRIGGER_SQL,
                               _CREDIT_NAMES, _install_table_guards, _REGISTRY_LOCK, _REGISTRY)
    with database._fence_transaction() as connection:
        state = _load(connection)
        if state is None or state["guard_format"] != 1:
            raise CreditNativeError("credit_fresh_authority_required", "native preparation requires current managed writer guards")
        scales = {row[0]: row[1] for row in connection.execute("SELECT asset,scale FROM ledger_assets")}
        record = descriptor(raw_descriptor, authority_id=state["authority_id"], asset_scales=scales)
        if state.get("credit_format") == FORMAT:
            if state["credit_descriptor_id"] != record.descriptor_id:
                raise CreditNativeError("credit_descriptor_conflict", "native credit preparation is immutable")
            return {"stage": STAGE, "descriptor_id": record.descriptor_id, "trading_enabled": False}
        history = tuple(tuple(row) for row in connection.execute("SELECT sequence,kind FROM writer_fence_events ORDER BY sequence LIMIT 3"))
        expected_history = ((1, "enabled_guard_v1"),) + (((2, "batches_enabled"),) if state["batch_format"] else ())
        if state["generation"] != 0 or state["owner_nonce"] is not None or history != expected_history:
            raise CreditNativeError("credit_fresh_authority_required", "a previously owned authority cannot be promoted by this fresh installer")
        if connection.execute("SELECT 1 FROM sqlite_master WHERE name LIKE 'credit_native_%' LIMIT 1").fetchone():
            raise CreditNativeError("credit_native_partial_schema", "partial native credit schema cannot be repaired")
        if connection.execute("SELECT 1 FROM uta_command_inbox LIMIT 1").fetchone():
            raise CreditNativeError("credit_fresh_authority_required", "native preparation requires an unused durable inbox")
        DecisionAudit.validate(connection)
        validate_opening(connection, record)
        for name in OBJECT_SQL:
            _create_credit_object(connection, name)
        with _REGISTRY_LOCK:
            guard = _REGISTRY[id(connection)]
        with guard.privileged():
            _insert_preparation(connection, record)
            _install_table_guards(connection, TABLE_SQL)
        _create_control_object(connection, "writer_fence_credit_capability")
        connection.execute("INSERT INTO writer_fence_credit_capability VALUES(1,1,?,?,?)", (STAGE, record.descriptor_id, record.canonical_payload))
        for name, (table, _) in _CONTROL_TRIGGER_SQL.items():
            if table in _CREDIT_NAMES:
                _create_control_object(connection, name)
        now, _ = _observed(database, state)
        WriterFence(database)._event(connection, "credit_native_prepared_v1", state, now)
    return {"stage": STAGE, "descriptor_id": record.descriptor_id, "trading_enabled": False}


@contextmanager
def operation_scope(database, connection, *, command_id, payload_hash):
    """An intentionally closed production interface until a trading format exists.

    Check actual registry/connection/thread/token before refusing preparation.
    No synthetic scope, activation flag or caller-provided verifier is accepted.
    """
    from .writer_fence import _REGISTRY, _REGISTRY_LOCK
    with _REGISTRY_LOCK:
        guard = _REGISTRY.get(id(connection))
    if (guard is None or guard.connection is not connection or guard.database is not database
            or guard.role != "financial" or guard.credit_owner_thread != get_ident()):
        raise CreditNativeError("credit_operation_context_invalid", "credit operation requires its exact financial transaction")
    if guard.state is None or guard.state.get("credit_format") not in TRADING_FORMATS:
        raise CreditNativeError("credit_not_active", "native preparation has no trading operation capability")
    raise CreditNativeError("credit_not_active", "no credit trading format is implemented")
    yield  # pragma: no cover -- there is deliberately no positive scope yet.
