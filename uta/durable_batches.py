"""Opt-in append-only durable financial batch attempts, not admission receipts.

The manifest and original command inbox share a SQLite authority. Metadata
preparation is a separate fenced commit; original effects and terminal receipts
remain in the financial commit. Default managed layouts do not create this
module or select its dispatcher.
"""
from contextlib import nullcontext
from datetime import datetime, timezone
from hashlib import sha256
import json
from time import monotonic
from uuid import uuid4

from .durable_commands import (_CONTROL, _TERMINAL, CANCEL_ORDER, REPAY,
                               SUBMIT_ORDER, _stamp)
from .service import ServiceError, _json
from .storage import Database, StorageError
from .writer_fence import WriterFence, WriterFenceError


_TABLES = ("uta_command_batch_manifests", "uta_command_batch_outcomes")
_SCHEMA = (
    "CREATE TABLE uta_command_batch_manifests(attempt_id TEXT PRIMARY KEY,content TEXT NOT NULL,content_sha256 TEXT NOT NULL,created_at TEXT NOT NULL)",
    "CREATE TABLE uta_command_batch_outcomes(attempt_id TEXT PRIMARY KEY REFERENCES uta_command_batch_manifests(attempt_id),disposition TEXT NOT NULL CHECK(disposition IN ('COMMITTED','RECOVERED')),content TEXT NOT NULL,completed_at TEXT NOT NULL)",
) + tuple(
    f"CREATE TRIGGER {table}_no_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'batch attempts are immutable'); END"
    for table in _TABLES for action in ("UPDATE", "DELETE")
) + tuple(
    f"CREATE TRIGGER {table}_no_replace BEFORE INSERT ON {table} WHEN EXISTS (SELECT 1 FROM {table} WHERE attempt_id=NEW.attempt_id) BEGIN SELECT RAISE(ABORT,'batch identity cannot be replaced'); END"
    for table in _TABLES
)


class BatchExecutionError(RuntimeError):
    """A durable attempt must be fully resolved before further dispatch."""
    def __init__(self, attempt_id, command_ids, cause, *, executing_id=None, phase="financial"):
        super().__init__("batch receipt unavailable; resolve every original command ID")
        self.attempt_id, self.command_ids, self.cause = attempt_id, tuple(command_ids), cause
        self.executing_id, self.phase = executing_id, phase


class BatchRecoveryUnknown(StorageError):
    code = "batch_recovery_unknown"


class BatchStore:
    """Owner-only attempts. No producer API gains permission to these tables."""
    @staticmethod
    def _verify_schema(connection):
        expected = {}
        for sql in _SCHEMA:
            fields = sql.split()
            name = fields[2].split("(", 1)[0]
            table = name if fields[1] == "TABLE" else sql.split(" ON ", 1)[1].split()[0]
            expected[name] = (fields[1].lower(), table, sql)
        actual = {row[0]: tuple(row)[1:] for row in connection.execute(
            "SELECT name,type,tbl_name,sql FROM sqlite_master WHERE name LIKE 'uta_command_batch_%' AND type IN ('table','trigger')")}
        if actual != expected:
            raise StorageError("batch schema inventory or exact definitions differ; automatic repair is forbidden")
        indexes = {tuple(row) for row in connection.execute(
            "SELECT name,tbl_name,sql FROM sqlite_master WHERE type='index' AND tbl_name IN (?,?)", _TABLES)}
        if indexes != {(f"sqlite_autoindex_{table}_1", table, None) for table in _TABLES}:
            raise StorageError("batch index inventory differs")

    @classmethod
    def initialize(cls, database):
        """Fresh offline creation only, before persistent writer fencing."""
        if not isinstance(database, Database):
            raise ValueError("batch initialization requires a Database")
        with database.transaction() as connection:
            found = connection.execute("SELECT 1 FROM sqlite_master WHERE name LIKE 'uta_command_batch_%' LIMIT 1").fetchone()
            if found is not None:
                cls._verify_schema(connection)
                return
            if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name LIKE 'writer_fence_%' LIMIT 1").fetchone():
                raise ServiceError("batch_offline_migration_required", "existing managed authorities cannot auto-create batch history", 409)
            for sql in _SCHEMA:
                connection.execute(sql)
            cls._verify_schema(connection)

    def __init__(self, database, queue, *, shard, layout_hash):
        if not isinstance(database, Database) or database.path != queue.database.path:
            raise ValueError("batch, queue and exchange must share the financial authority")
        if type(shard) is not int or shard < 0 or not isinstance(layout_hash, str) or len(layout_hash) != 64:
            raise ValueError("batch shard and layout identity are required")
        self.database, self.queue, self.shard, self.layout_hash = database, queue, shard, layout_hash
        with database.read_transaction() as connection:
            self._verify_schema(connection)
            state = WriterFence(database).assert_writer(connection)
            if state["batch_format"] != 1:
                raise WriterFenceError("batch_capability_required", "authority has no durable batch capability")

    @staticmethod
    def _member(row):
        if type(row["payload"]) is not str or type(row["kind"]) is not str:
            # Corrupt rows retain the original single-command isolation path.
            raise StorageError("batch candidate has a non-text stored identity")
        return {"command_id": row["command_id"], "sequence": row["sequence"],
                "account_id": row["account_id"], "kind": row["kind"],
                "payload_sha256": sha256(row["payload"].encode()).hexdigest()}

    def _content(self, row):
        try:
            content = json.loads(row["content"])
            if _json(content) != row["content"] or sha256(row["content"].encode()).hexdigest() != row["content_sha256"]:
                raise ValueError("batch content differs")
            if set(content) != {"format", "shard", "layout_hash", "owner", "members"} or content["format"] != 1:
                raise ValueError("batch identity fields differ")
            if content["shard"] != self.shard or content["layout_hash"] != self.layout_hash:
                raise ValueError("batch authority differs")
            members = content["members"]
            if not isinstance(members, list) or not 3 <= len(members) <= 8:
                raise ValueError("batch membership size differs")
            ids = [member["command_id"] for member in members]
            if len(set(ids)) != len(ids):
                raise ValueError("duplicate member")
            for member in members:
                if set(member) != {"command_id", "sequence", "account_id", "kind", "payload_sha256"}:
                    raise ValueError("batch membership fields differ")
            return content
        except (ValueError, TypeError, KeyError) as exc:
            raise BatchRecoveryUnknown("batch membership cannot be established") from exc

    def _members(self, connection, content):
        rows = []
        for member in content["members"]:
            row = connection.execute("SELECT * FROM uta_command_inbox WHERE command_id=?", (member["command_id"],)).fetchone()
            if row is None or self._member(row) != member:
                raise BatchRecoveryUnknown("an original command is absent or differs from immutable membership")
            rows.append(row)
        return rows

    def unresolved(self):
        with self.database.read_transaction() as connection:
            self._verify_schema(connection)
            return [row[0] for row in connection.execute("SELECT m.attempt_id FROM uta_command_batch_manifests m LEFT JOIN uta_command_batch_outcomes o USING(attempt_id) WHERE o.attempt_id IS NULL ORDER BY m.created_at,m.attempt_id")]

    def _outcome(self, connection, attempt_id, disposition, rows, executed=()):
        content = {"executed": list(executed), "commands": [{"command_id": row["command_id"], "state": row["state"]} for row in rows]}
        connection.execute("INSERT INTO uta_command_batch_outcomes VALUES(?,?,?,?)",
                           (attempt_id, disposition, _json(content), _stamp(self.queue.clock())))

    def recover(self, attempt_id):
        """Query all in one RO snapshot, then recheck all in a fenced metadata txn.

        Any read failure leaves the immutable manifest unresolved. No command
        attempt is charged here, and no financial effect is replayed here.
        """
        try:
            with self.database.read_transaction() as connection:
                self._verify_schema(connection)
                row = connection.execute("SELECT * FROM uta_command_batch_manifests WHERE attempt_id=?", (attempt_id,)).fetchone()
                if row is None:
                    raise BatchRecoveryUnknown("batch manifest is missing")
                content = self._content(row)
                rows = self._members(connection, content)  # All original CIDs; no early terminal shortcut.
                if any(row["state"] not in (*_TERMINAL, "PENDING") for row in rows):
                    raise BatchRecoveryUnknown("unsupported original command state")
            with self.database._batch_metadata_transaction() as connection:
                self._verify_schema(connection)
                WriterFence(self.database).assert_writer(connection)
                existing = connection.execute("SELECT * FROM uta_command_batch_outcomes WHERE attempt_id=?", (attempt_id,)).fetchone()
                rows = self._members(connection, content)
                if existing is None:
                    self._outcome(connection, attempt_id, "RECOVERED", rows)
                return [self.queue._record(row) for row in rows]
        except BatchRecoveryUnknown:
            raise
        except Exception as exc:
            raise BatchRecoveryUnknown("every original command outcome could not be established") from exc

    def prepare(self, *, size=8):
        if type(size) is not int or not 3 <= size <= 8:
            raise ValueError("financial batch size must be an integer in 3..8")
        with self.database._batch_metadata_transaction() as connection:
            self._verify_schema(connection)
            state = WriterFence(self.database).assert_writer(connection)
            if connection.execute("SELECT 1 FROM uta_command_batch_manifests m LEFT JOIN uta_command_batch_outcomes o USING(attempt_id) WHERE o.attempt_id IS NULL LIMIT 1").fetchone():
                raise BatchRecoveryUnknown("resolve the earlier durable attempt before selecting new membership")
            now = _stamp(self.queue.clock())
            rows = connection.execute("SELECT * FROM uta_command_inbox WHERE state='PENDING' ORDER BY sequence").fetchall()
            by_account = {}
            for row in rows:
                by_account.setdefault(row["account_id"], []).append(row)
            controls = by_account.get(None, ())
            if controls and (controls[0]["next_attempt_at"] is None or controls[0]["next_attempt_at"] <= now):
                return None
            heads, successors = [], {}
            for account, pending in by_account.items():
                if account is None:
                    continue
                eligible = []
                for row in pending[:2]:
                    if row["kind"] not in (SUBMIT_ORDER, CANCEL_ORDER, REPAY) or row["next_attempt_at"] is not None and row["next_attempt_at"] > now:
                        break
                    eligible.append(row)
                if eligible:
                    heads.append(eligible[0])
                    if len(eligible) > 1:
                        successors[account] = eligible[1]
            normal = sorted((r for r in heads if r["kind"] == SUBMIT_ORDER), key=lambda r: r["sequence"])
            selected = [normal[0]] if normal else []
            remaining = sorted((r for r in heads if not selected or r["command_id"] != selected[0]["command_id"]),
                               key=lambda r: (r["kind"] == SUBMIT_ORDER, r["sequence"]))
            selected.extend(remaining[:size - len(selected)])
            if len(selected) < size:
                for head in tuple(selected):
                    if head["account_id"] in successors:
                        selected.append(successors[head["account_id"]])
                        if len(selected) == size:
                            break
            if len(selected) < 3:
                return None
            members = [self._member(row) for row in selected]
            token = self.database.writer_token
            content = {"format": 1, "shard": self.shard, "layout_hash": self.layout_hash,
                       "owner": {"authority_id": token.authority_id, "generation": token.generation,
                                 "process_id": token.process_id, "owner_nonce_sha256": sha256(token.owner_nonce.encode()).hexdigest()},
                       "members": members}
            encoded, attempt_id = _json(content), "batch:" + uuid4().hex
            connection.execute("INSERT INTO uta_command_batch_manifests VALUES(?,?,?,?)",
                               (attempt_id, encoded, sha256(encoded.encode()).hexdigest(), now))
        return attempt_id

    def process(self, exchange, attempt_id, *, guard=None, credit=None, soft_budget_seconds=.005):
        """Execute an immutable attempt in one financial transaction, under SH."""
        if (isinstance(soft_budget_seconds, bool) or not isinstance(soft_budget_seconds, (int, float))
                or not 0 < soft_budget_seconds <= .1):
            raise ValueError("batch soft budget must be in (0,.1] seconds")
        self.queue._check_exchange(exchange)
        ids, executing, phase = (), None, "membership"
        try:
            with exchange._transaction() as connection:
                self._verify_schema(connection)
                WriterFence(self.database).assert_writer(connection)
                manifest = connection.execute("SELECT * FROM uta_command_batch_manifests WHERE attempt_id=?", (attempt_id,)).fetchone()
                if manifest is None:
                    raise BatchRecoveryUnknown("batch manifest is absent")
                content = self._content(manifest)
                ids = tuple(member["command_id"] for member in content["members"])
                token = self.database.writer_token
                owner = {"authority_id": token.authority_id, "generation": token.generation,
                         "process_id": token.process_id, "owner_nonce_sha256": sha256(token.owner_nonce.encode()).hexdigest()}
                if content["owner"] != owner:
                    raise BatchRecoveryUnknown("new owners must resolve previous attempts before selecting new work")
                rows = self._members(connection, content)
                if connection.execute("SELECT 1 FROM uta_command_batch_outcomes WHERE attempt_id=?", (attempt_id,)).fetchone():
                    return [self.queue._record(row) for row in rows]
                executed, receipts, changed_market = [], [], False
                started = monotonic()
                for member in content["members"]:
                    if executed and monotonic() - started >= soft_budget_seconds:
                        break
                    now = _stamp(self.queue.clock())
                    # A newly queued due control keeps its single-command lane.
                    if connection.execute("SELECT 1 FROM uta_command_inbox c WHERE c.state='PENDING' AND c.account_id IS NULL AND (c.next_attempt_at IS NULL OR c.next_attempt_at<=?) AND NOT EXISTS(SELECT 1 FROM uta_command_inbox p WHERE p.state='PENDING' AND p.account_id IS NULL AND p.sequence<c.sequence) LIMIT 1", (now,)).fetchone():
                        break
                    row = connection.execute("SELECT * FROM uta_command_inbox WHERE command_id=?", (member["command_id"],)).fetchone()
                    if row is None or self._member(row) != member:
                        raise BatchRecoveryUnknown("original command membership changed")
                    if row["state"] in _TERMINAL:
                        receipts.append(self.queue._record(row))
                        continue
                    if row["state"] != "PENDING":
                        raise BatchRecoveryUnknown("unsupported original command state")
                    if row["kind"] in _CONTROL or row["account_id"] is None:
                        raise BatchRecoveryUnknown("financial batch contains a control command")
                    if row["next_attempt_at"] is not None and row["next_attempt_at"] > now:
                        continue
                    if connection.execute("SELECT 1 FROM uta_command_inbox WHERE state='PENDING' AND account_id=? AND sequence<? LIMIT 1", (row["account_id"], row["sequence"])).fetchone():
                        continue
                    executing, phase = row["command_id"], "execute"
                    receipt, new_order = self.queue._execute(exchange, connection, row, guard=guard, credit=credit)
                    executed.append(executing)
                    receipts.append(receipt)
                    changed_market |= new_order
                    executing, phase = None, "between_commands"
                phase = "freshness"
                if changed_market:
                    exchange._market(connection)
                phase = "disposition"
                rows = self._members(connection, content)
                self._outcome(connection, attempt_id, "COMMITTED", rows, executed)
                phase = "commit"
            return receipts
        except Exception as exc:
            raise BatchExecutionError(attempt_id, ids, exc, executing_id=executing, phase=phase) from exc
