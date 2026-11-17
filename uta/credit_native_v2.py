"""Compiled contract for a future fresh internal synthetic credit authority.

This catalog is not an installer or an authorization capability. Writer fencing
does not recognize this marker yet. There is no positive operation context,
activation, ownership, intake, HTTP or CLI entry point in this schema slice.
Format1 NATIVE_PREPARED is never upgraded. Actual primitive enforcement and
independent positive-chain acceptance must precede any internal execution.
"""
from types import MappingProxyType


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
