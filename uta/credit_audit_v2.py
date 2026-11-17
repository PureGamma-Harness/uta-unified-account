"""Dedicated internal synthetic credit audit contract, never an activation gate.

Schema definitions are consumed by the future fresh native-v2 installer. Merely
importing this module does not install schema, grant ownership or enable credit.
Format1 NATIVE_PREPARED is not upgraded. Capture/replay and positive dispatch are
separate implementation slices; no incomplete record is a valid credit audit.
"""
from hashlib import sha256
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
        definitions[name] = (table, f"CREATE TRIGGER {name} BEFORE INSERT ON {table} WHEN EXISTS(SELECT 1 FROM {table} WHERE {key}=NEW.{key}) BEGIN SELECT RAISE(ABORT,'credit audit identity cannot replace'); END")
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
