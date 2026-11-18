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
import re
from time import monotonic
from uuid import uuid4

from .durable_commands import (_CONTROL, _TERMINAL, CANCEL_ORDER, REPAY,
                               SUBMIT_ORDER, _stamp)
from .service import ServiceError, _json, _name
from .failure_diagnostics import capture_failure
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
        # The owning table matters as well as the reserved object name. Native
        # writer guards are legitimate attached triggers, with the same shared
        # compiled definitions used by normal fence installation/verification.
        if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='writer_fence_guard_tables'").fetchone():
            from .writer_fence import _guard_sql
            registered = {row[0]: row[1] for row in connection.execute(
                "SELECT name,actions FROM writer_fence_guard_tables WHERE name IN (?,?)", _TABLES)}
            if registered != {table: "IUD" for table in _TABLES}:
                raise StorageError("batch native protection inventory differs")
            for table in _TABLES:
                for action in "IUD":
                    name, sql = _guard_sql(table, action)
                    expected[name] = ("trigger", table, sql)
        for table in _TABLES:
            expected[f"sqlite_autoindex_{table}_1"] = ("index", table, None)
        actual = {row[0]: tuple(row)[1:] for row in connection.execute(
            "SELECT name,type,tbl_name,sql FROM sqlite_master WHERE name LIKE 'uta_command_batch_%' OR tbl_name IN (?,?)", _TABLES)}
        if actual != expected:
            raise StorageError("batch schema inventory or exact definitions differ; automatic repair is forbidden")

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
            self.startup_unresolved = tuple(self._verify_history(connection))

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
            if set(content) != {"format", "shard", "layout_hash", "owner", "members"} or type(content["format"]) is not int or content["format"] != 1:
                raise ValueError("batch identity fields differ")
            if type(content["shard"]) is not int or content["shard"] != self.shard or content["layout_hash"] != self.layout_hash:
                raise ValueError("batch authority differs")
            owner = content["owner"]
            if (not isinstance(owner, dict) or set(owner) != {"authority_id", "generation", "process_id", "owner_nonce_sha256"}
                    or owner["authority_id"] != self.database.writer_token.authority_id
                    or type(owner["generation"]) is not int or not 1 <= owner["generation"] < 2**63
                    or type(owner["process_id"]) is not int or owner["process_id"] <= 0
                    or type(owner["owner_nonce_sha256"]) is not str or re.fullmatch("[0-9a-f]{64}", owner["owner_nonce_sha256"]) is None):
                raise ValueError("batch owner identity differs")
            members = content["members"]
            if not isinstance(members, list) or not 3 <= len(members) <= 8:
                raise ValueError("batch membership size differs")
            ids = [member["command_id"] for member in members]
            if len(set(ids)) != len(ids):
                raise ValueError("duplicate member")
            account_sequences = {}
            for member in members:
                if set(member) != {"command_id", "sequence", "account_id", "kind", "payload_sha256"}:
                    raise ValueError("batch membership fields differ")
                _name(member["command_id"], "command_id")
                _name(member["account_id"], "account_id")
                if (type(member["sequence"]) is not int or not 1 <= member["sequence"] < 2**63
                        or member["kind"] not in (SUBMIT_ORDER, CANCEL_ORDER, REPAY)
                        or type(member["payload_sha256"]) is not str or re.fullmatch("[0-9a-f]{64}", member["payload_sha256"]) is None):
                    raise ValueError("batch member types differ")
                sequences = account_sequences.setdefault(member["account_id"], [])
                if len(sequences) >= 2 or sequences and member["sequence"] <= sequences[-1]:
                    raise ValueError("batch per-account membership order or bound differs")
                sequences.append(member["sequence"])
            return content
        except (ValueError, TypeError, KeyError, ServiceError) as exc:
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
            return self._verify_history(connection)

    def _verify_history(self, connection):
        unresolved = []
        for manifest in connection.execute("SELECT * FROM uta_command_batch_manifests ORDER BY created_at,attempt_id"):
            content = self._content(manifest)
            rows = self._members(connection, content)
            outcome = connection.execute("SELECT * FROM uta_command_batch_outcomes WHERE attempt_id=?", (manifest["attempt_id"],)).fetchone()
            if outcome is None:
                unresolved.append(manifest["attempt_id"])
            else:
                self._verify_outcome(outcome, content, rows)
        if connection.execute("SELECT 1 FROM uta_command_batch_outcomes o LEFT JOIN uta_command_batch_manifests m USING(attempt_id) WHERE m.attempt_id IS NULL LIMIT 1").fetchone():
            raise BatchRecoveryUnknown("batch outcome has no immutable manifest")
        return unresolved

    def _outcome(self, connection, attempt_id, disposition, rows, executed=()):
        content = {"executed": list(executed), "commands": [{"command_id": row["command_id"], "state": row["state"]} for row in rows]}
        connection.execute("INSERT INTO uta_command_batch_outcomes VALUES(?,?,?,?)",
                           (attempt_id, disposition, _json(content), _stamp(self.queue.clock())))

    def _verify_outcome(self, row, content, current):
        try:
            if row["disposition"] not in ("COMMITTED", "RECOVERED"):
                raise ValueError("unknown disposition")
            value = json.loads(row["content"])
            if _json(value) != row["content"] or set(value) != {"executed", "commands"}:
                raise ValueError("noncanonical disposition")
            ids = [member["command_id"] for member in content["members"]]
            executed, commands = value["executed"], value["commands"]
            if (not isinstance(executed, list) or any(type(cid) is not str for cid in executed)
                    or len(set(executed)) != len(executed) or not set(executed) <= set(ids)
                    or row["disposition"] == "RECOVERED" and executed
                    or not isinstance(commands, list) or len(commands) != len(ids)):
                raise ValueError("invalid disposition membership")
            # The executor visits immutable membership in order, but may skip
            # backoff/preexisting terminals. Its execution list is a subsequence.
            if executed != [cid for cid in ids if cid in executed]:
                raise ValueError("disposition execution order differs from membership")
            for expected, recorded, actual in zip(ids, commands, current):
                if (not isinstance(recorded, dict) or set(recorded) != {"command_id", "state"}
                        or recorded["command_id"] != expected
                        or recorded["state"] not in (*_TERMINAL, "PENDING")
                        or recorded["state"] in _TERMINAL and recorded["state"] != actual["state"]
                        # Technical quarantine is a separate failure-recording
                        # transition; _execute produces only business terminals.
                        or expected in executed and recorded["state"] not in ("SUCCEEDED", "REJECTED")):
                    raise ValueError("disposition contradicts original command state")
            return value
        except (ValueError, TypeError, KeyError) as exc:
            raise BatchRecoveryUnknown("batch disposition cannot be established") from exc

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
                else:
                    self._verify_outcome(existing, content, rows)
                return [self.queue._record(row) for row in rows]
        except BatchRecoveryUnknown:
            raise
        except Exception as exc:
            raise BatchRecoveryUnknown("every original command outcome could not be established") from exc

    def _select(self, connection, size):
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
        return selected

    def prepare(self, *, size=8):
        if type(size) is not int or not 3 <= size <= 8:
            raise ValueError("financial batch size must be an integer in 3..8")
        # Low occupancy creates no attempt and no metadata write transaction.
        with self.database.read_transaction() as connection:
            self._verify_schema(connection)
            if connection.execute("SELECT 1 FROM uta_command_batch_manifests m LEFT JOIN uta_command_batch_outcomes o USING(attempt_id) WHERE o.attempt_id IS NULL LIMIT 1").fetchone():
                raise BatchRecoveryUnknown("resolve the earlier durable attempt before selecting new membership")
            selected = self._select(connection, size)
            if selected is None or len(selected) < 3:
                return None
        attempt_id, progress = "batch:" + uuid4().hex, {"command_ids": ()}
        try:
            return self._prepare_locked(size, attempt_id, progress)
        except Exception as exc:
            raise BatchExecutionError(attempt_id, progress["command_ids"], exc, phase="prepare") from exc

    def _prepare_locked(self, size, attempt_id, progress):
        with self.database._batch_metadata_transaction() as connection:
            self._verify_schema(connection)
            state = WriterFence(self.database).assert_writer(connection)
            if connection.execute("SELECT 1 FROM uta_command_batch_manifests m LEFT JOIN uta_command_batch_outcomes o USING(attempt_id) WHERE o.attempt_id IS NULL LIMIT 1").fetchone():
                raise BatchRecoveryUnknown("resolve the earlier durable attempt before selecting new membership")
            selected = self._select(connection, size)
            if selected is None or len(selected) < 3:
                return None
            members = [self._member(row) for row in selected]
            token = self.database.writer_token
            content = {"format": 1, "shard": self.shard, "layout_hash": self.layout_hash,
                       "owner": {"authority_id": token.authority_id, "generation": token.generation,
                                 "process_id": token.process_id, "owner_nonce_sha256": sha256(token.owner_nonce.encode()).hexdigest()},
                       "members": members}
            encoded = _json(content)
            progress["command_ids"] = tuple(member["command_id"] for member in members)
            connection.execute("INSERT INTO uta_command_batch_manifests VALUES(?,?,?,?)",
                               (attempt_id, encoded, sha256(encoded.encode()).hexdigest(), _stamp(self.queue.clock())))
        return attempt_id

    def resolve_preparation(self, attempt_id):
        with self.database.read_transaction() as connection:
            self._verify_schema(connection)
            present = connection.execute("SELECT 1 FROM uta_command_batch_manifests WHERE attempt_id=?", (attempt_id,)).fetchone()
        return None if present is None else self.recover(attempt_id)

    def record_failure(self, exchange, error):
        """Append bounded internal evidence after query-all; never charge CIDs.

        This is an extra financial diagnostic transaction on a fault path. A
        failed/expired/unavailable write saves nothing; observations are a lower
        bound, never a claim that every process failure was persisted.
        """
        if not isinstance(error, BatchExecutionError):
            raise ValueError("batch failure evidence requires its original typed error")
        self.queue._check_exchange(exchange)
        _name(error.attempt_id, "attempt_id")
        phases = {"prepare", "membership", "execute", "between_commands", "freshness", "disposition", "commit"}
        if type(error.phase) is not str or error.phase not in phases:
            raise ValueError("batch failure phase must be a documented literal")
        token = self.database.writer_token
        with exchange._transaction() as connection:
            self._verify_schema(connection)
            WriterFence(self.database).assert_writer(connection)
            # The unique writer serializes this check and append. Repeat after
            # a lost diagnostic COMMIT reply keeps the original immutable event.
            for row in connection.execute("SELECT payload FROM uta_events WHERE event_type='COMMAND_BATCH_EXECUTION_FAILED' AND account_id IS NULL"):
                existing = json.loads(row[0])
                if existing.get("attempt_id") == error.attempt_id and existing.get("phase") == error.phase and existing.get("recording_generation") == token.generation:
                    return existing
            manifest = connection.execute("SELECT * FROM uta_command_batch_manifests WHERE attempt_id=?", (error.attempt_id,)).fetchone()
            if manifest is not None:
                content = self._content(manifest)
                rows = self._members(connection, content)
                ids = [row["command_id"] for row in rows]
            elif error.phase == "prepare":
                ids = list(error.command_ids)
                if len(ids) > 8:
                    raise ValueError("batch preparation hint exceeds membership budget")
                for cid in ids:
                    _name(cid, "command_id")
            else:
                raise BatchRecoveryUnknown("failure has no durable original attempt")
            payload = {"event_version": 1, "attempt_id": error.attempt_id,
                       "phase": error.phase, "recording_generation": token.generation,
                       "recording_process_id": token.process_id, "authority_id": token.authority_id,
                       "manifest_sha256": manifest["content_sha256"] if manifest is not None else None,
                       "execution_owner": content["owner"] if manifest is not None else None,
                       "membership_source": "durable_manifest" if manifest is not None else "uncommitted_prepare_hint",
                       "command_ids": ids, "executing_id": error.executing_id if error.executing_id in ids else None,
                       "failure": capture_failure(error.cause)}
            exchange._event(connection, "COMMAND_BATCH_EXECUTION_FAILED", None, payload)
        return payload

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
                existing = connection.execute("SELECT * FROM uta_command_batch_outcomes WHERE attempt_id=?", (attempt_id,)).fetchone()
                if existing is not None:
                    self._verify_outcome(existing, content, rows)
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
