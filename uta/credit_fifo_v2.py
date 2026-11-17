"""Explicit synthetic-only credit intake and one-command durable execution.

There is no public route, CLI switch or generic QueueStore BORROW command.
Objects returned by the producer are observations, not execution grants. The
actual native guard, immutable source, FIFO intent and terminal SQL obligations
remain necessary for every financial COMMIT.
"""
from decimal import Decimal
import sqlite3

from .admission import _business_rejection
from .credit import CreditService
from .credit_audit_v2 import canonical, strict_json
from .credit_transition import CreditTransitionError
from .durable_commands import CommandExecutionError, QueueStore, _stamp
from .ledger import LedgerError
from .service import ExchangeService, ServiceError, _name
from .storage import StorageError


_KINDS = frozenset({"BORROW", "REPAY"})
_TABLE_SQL = {
    "uta_command_config": """CREATE TABLE uta_command_config (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1), format INTEGER NOT NULL,
                queue_capacity INTEGER NOT NULL, cancel_reserve INTEGER NOT NULL, market_capacity INTEGER NOT NULL)""",
    "uta_command_inbox": """CREATE TABLE uta_command_inbox (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT, command_id TEXT NOT NULL UNIQUE,
                account_id TEXT, kind TEXT NOT NULL, payload TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('PENDING','SUCCEEDED','REJECTED','QUARANTINED')),
                result TEXT, error TEXT, enqueued_at TEXT NOT NULL, completed_at TEXT,
                attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT, next_attempt_at TEXT)""",
}
_INDEX_SQL = {
    "uta_command_pending": "CREATE INDEX uta_command_pending ON uta_command_inbox(state,sequence)",
    "uta_command_account_pending": "CREATE INDEX uta_command_account_pending ON uta_command_inbox(account_id,state,sequence)",
}
_TRIGGERS = (
    ("uta_command_config_no_replace", "BEFORE INSERT ON uta_command_config WHEN EXISTS (SELECT 1 FROM uta_command_config WHERE singleton=NEW.singleton)", "inbox config cannot be replaced"),
    ("uta_command_config_no_update", "BEFORE UPDATE ON uta_command_config", "inbox config is immutable"),
    ("uta_command_config_no_delete", "BEFORE DELETE ON uta_command_config", "inbox config is immutable"),
    ("uta_command_inbox_pending_insert", "BEFORE INSERT ON uta_command_inbox WHEN NEW.state!='PENDING' OR NEW.result IS NOT NULL OR NEW.error IS NOT NULL OR NEW.completed_at IS NOT NULL", "new commands must be pending without a terminal receipt"),
    ("uta_command_inbox_no_replace", "BEFORE INSERT ON uta_command_inbox WHEN EXISTS (SELECT 1 FROM uta_command_inbox WHERE command_id=NEW.command_id OR sequence=NEW.sequence)", "command identity cannot be replaced"),
    ("uta_command_inbox_identity_immutable", "BEFORE UPDATE ON uta_command_inbox WHEN NEW.sequence!=OLD.sequence OR NEW.command_id!=OLD.command_id OR NEW.account_id IS NOT OLD.account_id OR NEW.kind!=OLD.kind OR NEW.payload!=OLD.payload OR NEW.enqueued_at!=OLD.enqueued_at", "command identity is immutable"),
    ("uta_command_inbox_terminal_immutable", "BEFORE UPDATE ON uta_command_inbox WHEN OLD.state!='PENDING'", "terminal command receipt is immutable"),
    ("uta_command_inbox_no_delete", "BEFORE DELETE ON uta_command_inbox", "command history is retained"),
)


def verify_existing_queue(connection):
    """Verify the actual fixed queue catalog, without opening or repairing it.

    The duplicated base definitions are intentionally compared to real installed
    SQL. An incompatible QueueStore schema change must update this version's
    contract and tests; the loader must not silently accept it by column names.
    Additional native constraints must come from exact compiled inventories.
    """
    from .credit_audit_v2 import OBJECT_SQL as audit_objects
    from .credit_native_v2 import OBJECT_SQL as native_objects
    from .existing_services import _tokens, _column_names, _fixed_definition
    from .writer_fence import _guard_actions, _guard_sql
    expected = {}
    for statement in (*_TABLE_SQL.values(), *_INDEX_SQL.values(),
            *(f"CREATE TRIGGER {name} {clause} BEGIN SELECT RAISE(ABORT,'{message}'); END"
              for name, clause, message in _TRIGGERS)):
        name, item = _fixed_definition(statement)
        expected[name] = item
    complete = connection.execute("SELECT 1 FROM sqlite_master WHERE name='writer_fence_credit_v2_capability'").fetchone() is not None
    existing_names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
    for statement in (*native_objects.values(), *audit_objects.values()):
        name, item = _fixed_definition(statement)
        if item[1] in _TABLE_SQL and (complete or name in existing_names):
            expected[name] = item
    for table in _TABLE_SQL:
        for action in _guard_actions(table):
            name, statement = _guard_sql(table, action)
            # _guard_sql quotes identifiers; the inventory identity is fixed.
            expected[name] = ("trigger", table, statement)
    installed = {row[0]: tuple(row[1:]) for row in connection.execute(
        "SELECT name,type,tbl_name,sql FROM sqlite_master WHERE tbl_name IN ('uta_command_config','uta_command_inbox')")}
    # Before publication an ordinary initialized queue has no native writer
    # guards. A native loader independently requires its complete guard table.
    for name in tuple(expected):
        if name not in installed and name.startswith("writer_fence_data_"):
            del expected[name]
    automatic = {name: value for name, value in installed.items()
                 if name.startswith("sqlite_autoindex_") and value[0] == "index" and value[2] is None}
    expected.update(automatic)
    if set(installed) != set(expected):
        raise StorageError("internal credit durable queue has missing or unexpected fixed constraints")
    for name, (kind, table, statement) in expected.items():
        actual = installed[name]
        if actual[:2] != (kind, table) or (statement is None) != (actual[2] is None):
            raise StorageError("internal credit queue object identity differs")
        if statement is not None and _tokens(statement) != _tokens(actual[2]):
            raise StorageError("internal credit queue fixed SQL differs: "+name)
    for table, statement in _TABLE_SQL.items():
        columns = list(connection.execute('PRAGMA table_xinfo("'+table+'")'))
        if tuple(row[1] for row in columns) != _column_names(statement) or any(row[6] for row in columns):
            raise StorageError("internal credit queue columns differ")
    rows = connection.execute("SELECT singleton,format,queue_capacity,cancel_reserve,market_capacity FROM uta_command_config").fetchall()
    if (len(rows) != 1 or tuple(rows[0])[:2] != (1, 1)
            or any(type(value) is not int for value in rows[0])
            or not 1 <= rows[0][2] <= 65536 or not 0 <= rows[0][3] <= 4096
            or not 1 <= rows[0][4] <= 64):
        raise StorageError("internal credit queue capacity policy is incomplete or invalid")
    return {"queue_capacity": rows[0][2], "cancel_reserve": rows[0][3], "market_capacity": rows[0][4]}


def is_business_rejection(kind, error):
    """Known refusal after SQL rollback, retaining hidden-failure detection."""
    if kind not in _KINDS or type(error) is not ServiceError:
        return False
    pending, seen = [error], set()
    while pending:
        current = pending.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        # These exact pure-integer quota errors are typed StorageErrors for the
        # offline calculator API. They are the only explicit exception; their
        # entire cause/context chains are still examined for real SQL failures.
        pure_quota = (type(current) is CreditTransitionError and current.status == 409
                      and current.code in {"credit_limit", "credit_pool_empty"})
        if isinstance(current, (sqlite3.Error, LedgerError, StorageError)) and not pure_quota:
            return False
        pending.extend((current.__cause__, current.__context__))
    if _business_rejection(error):
        return True
    codes = {"credit_limit", "credit_pool_empty", "credit_disabled"} if kind == "BORROW" else {
        "repayment_exceeds_debt", "insufficient_cash", "unknown_asset", "credit_limit"}
    return error.code in codes and 400 <= error.status < 500


class InternalCreditFIFO:
    """Explicit trusted synthetic producer and single financial command worker."""

    def __init__(self, exchange, credit):
        if type(exchange) is not ExchangeService or type(credit) is not CreditService or credit.exchange is not exchange:
            raise StorageError("internal credit FIFO requires its real initialized services")
        if credit.database is not exchange.database:
            raise StorageError("internal credit services must share their actual Database object")
        self.exchange, self.credit, self.database = exchange, credit, exchange.database
        with self.database.read_transaction() as connection:
            self._require_capability(connection)
            verify_existing_queue(connection)

    @staticmethod
    def _require_capability(connection):
        from .writer_fence import _load
        state = _load(connection)
        if state is None or state.get("credit_format") != 2:
            raise ServiceError("unsupported_credit_operation", "explicit complete synthetic credit capability is required", 501)
        return state

    def enqueue_borrow(self, account_id, command_id, asset, amount, *, actor_id, source_reference):
        return self._enqueue("BORROW", account_id, command_id, asset, amount,
                             actor_id=actor_id, source_reference=source_reference)

    def enqueue_repay(self, account_id, command_id, asset, amount, *, actor_id, source_reference):
        return self._enqueue("REPAY", account_id, command_id, asset, amount,
                             actor_id=actor_id, source_reference=source_reference)

    def _enqueue(self, kind, account_id, command_id, asset, amount, *, actor_id, source_reference):
        from .credit_native_v2 import read_source, source_receipt, synthetic_intake_scope
        _name(command_id, "command_id")
        if type(amount) is str:
            try:
                amount = Decimal(amount)
            except Exception as error:
                raise ServiceError("invalid_input", "credit amount is invalid") from error
        units, text, scope = self.credit._prepare(account_id, command_id, asset, amount)
        if asset != "BTC":
            raise ServiceError("unsupported_credit_asset", "internal synthetic credit supports BTC only", 409)
        _name(actor_id, "actor_id")
        _name(source_reference, "source_reference")
        payload = canonical({"account_id": account_id, "asset": asset, "amount": text})
        with self.database.inbox_transaction() as connection:
            state = self._require_capability(connection)
            policy = verify_existing_queue(connection)
            row = connection.execute("SELECT * FROM uta_command_inbox WHERE command_id=?", (command_id,)).fetchone()
            if row is not None:
                source = read_source(connection, command_id, expected_authority_id=state["authority_id"])
                if ((row["kind"], row["account_id"], row["payload"]) != (kind, account_id, payload)
                        or (source.actor_id, source.source_reference) != (actor_id, source_reference)):
                    raise ServiceError("idempotency_conflict", "original credit command or source identity differs", 409)
                receipt = QueueStore._record(row)
            else:
                original = self.credit._replay(connection, scope, command_id,
                    "borrowed" if kind == "BORROW" else "repaid", asset, text)
                if original is not None:
                    # A legacy original receipt is returned without minting a
                    # nonexistent historical source, intent, audit or inbox row.
                    receipt = {"command_id": command_id, "account_id": account_id, "kind": kind,
                        "state": "LEGACY_RECEIPT", "ack": "original_credit_receipt", "result": original}
                else:
                    count = connection.execute("SELECT COUNT(*) FROM uta_command_inbox WHERE state='PENDING' AND kind NOT IN ('PUBLISH_MARKET','SET_HALT')").fetchone()[0]
                    limit = policy["queue_capacity"]+(policy["cancel_reserve"] if kind == "REPAY" else 0)
                    if count >= limit:
                        raise ServiceError("durable_queue_overloaded", "durable pending command capacity is exhausted", 503)
                    source = source_receipt(authority_id=state["authority_id"], account_id=account_id,
                        command_id=command_id, kind=kind, actor_id=actor_id, source_reference=source_reference,
                        command_payload=payload, accepted_at=self.exchange._now())
                    with synthetic_intake_scope(self.database, connection, canonical_source=source):
                        connection.execute("INSERT INTO credit_v2_sources VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                            (source.command_id, source.source_id, source.account_id, source.kind, source.payload_hash,
                             "synthetic_local", source.actor_id, source.source_reference, source.authority_id,
                             source.command_payload, source.canonical_payload))
                        accepted_at = strict_json(source.canonical_payload)["accepted_at"]
                        connection.execute("INSERT INTO uta_command_inbox(command_id,account_id,kind,payload,state,enqueued_at) VALUES(?,?,?,?,'PENDING',?)",
                            (command_id, account_id, kind, payload, accepted_at))
                    receipt = QueueStore._record(connection.execute("SELECT * FROM uta_command_inbox WHERE command_id=?", (command_id,)).fetchone())
        return receipt  # Producer COMMIT has returned; this is not risk acceptance.

    def status(self, command_id, *, account_id=None):
        _name(command_id, "command_id")
        if account_id is not None:
            _name(account_id, "account_id")
        with self.database.read_transaction() as connection:
            self._require_capability(connection)
            row = connection.execute("SELECT * FROM uta_command_inbox WHERE command_id=?", (command_id,)).fetchone()
            if row is None or row["kind"] not in _KINDS or (account_id is not None and row["account_id"] != account_id):
                return None
            return QueueStore._record(row)

    def process_one(self):
        """Return one receipt only after financial COMMIT; unknown stays queried."""
        from .credit_native_v2 import operation_scope, rejection_scope, read_source
        command_id = sequence = attempt = None
        try:
            with self.exchange._transaction() as connection:
                state = self._require_capability(connection)
                from .writer_fence import WriterFence
                WriterFence(self.database).assert_writer(connection)
                row = connection.execute("""SELECT c.* FROM uta_command_inbox c
                    WHERE c.state='PENDING' AND c.kind IN ('BORROW','REPAY')
                    AND (c.next_attempt_at IS NULL OR c.next_attempt_at<=?)
                    AND NOT EXISTS (SELECT 1 FROM uta_command_inbox p WHERE p.state='PENDING'
                        AND p.account_id=c.account_id AND p.sequence<c.sequence)
                    ORDER BY c.sequence LIMIT 1""", (_stamp(self.exchange._now()),)).fetchone()
                if row is None:
                    return None
                command_id, sequence, attempt = row["command_id"], row["sequence"], row["attempts"]+1
                source = read_source(connection, command_id, expected_authority_id=state["authority_id"])
                payload = strict_json(source.command_payload)
                connection.execute("SAVEPOINT credit_command_v2")
                try:
                    with operation_scope(self.credit, connection, command_id=command_id):
                        action = self.credit._borrow if source.kind == "BORROW" else self.credit._repay
                        result = action(connection, source.account_id, command_id, payload["asset"], Decimal(payload["amount"]))
                        self._terminal(connection, command_id, result=result)
                except ServiceError as error:
                    if not connection.in_transaction or not is_business_rejection(source.kind, error):
                        raise
                    connection.execute("ROLLBACK TO credit_command_v2")
                    with rejection_scope(self.credit, connection, command_id=command_id, error=error):
                        self._terminal(connection, command_id, error=error)
                connection.execute("RELEASE credit_command_v2")
                receipt = QueueStore._record(connection.execute("SELECT * FROM uta_command_inbox WHERE command_id=?", (command_id,)).fetchone())
            return receipt
        except Exception as error:
            raise CommandExecutionError(command_id, sequence, error, attempt=attempt) from error

    def _terminal(self, connection, command_id, *, result=None, error=None):
        encoded_error = None if error is None else canonical({"code": error.code, "message": str(error), "status": error.status})
        changed = connection.execute("UPDATE uta_command_inbox SET state=?,result=?,error=?,completed_at=?,next_attempt_at=NULL WHERE command_id=? AND state='PENDING'",
            ("REJECTED" if error is not None else "SUCCEEDED", canonical(result) if result is not None else None,
             encoded_error, _stamp(self.exchange._now()), command_id))
        if changed.rowcount != 1:
            raise StorageError("original pending credit command terminal transition did not update exactly one row")
