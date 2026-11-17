"""Single-host, independently fenced process owners for durable shard inboxes.

Commands and outcomes live in each financial SQLite database. Multiprocessing
objects carry only lifecycle signals; no financial command or receipt depends
on a parent process, shared manager, Future, or in-memory transport surviving.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
from decimal import Decimal
import fcntl
from hashlib import sha256
import json
import math
import multiprocessing
import os
from pathlib import Path
import select
import signal
import sqlite3
import stat
from threading import Event, RLock, Thread, current_thread
from time import monotonic, sleep
from uuid import uuid4

from .durable_commands import CommandExecutionError, QueueStore
from .market import MAX_JSON_BYTES, MarketSnapshot
from .ledger import Ledger, LedgerError
from .models import RiskInputError
from .portfolio import PortfolioRules
from .products import ProductCatalog
from .service import ServiceError, _name, _text
from .sharding import (_BoundShardDatabase, ShardRouter, ShardWorkerView,
                       _json, _open_router_control)
from .writer_fence import (WriterFence, WriterFenceError,
                           _load as _load_writer_lease, _observed as _observe_writer_clock)
from .storage import Database, DurableLedger, StorageError


_TERMINAL = frozenset({"SUCCEEDED", "REJECTED", "QUARANTINED"})


def _diagnostic_remaining(deadline):
    remaining = deadline - monotonic()
    if remaining <= 0:
        raise ServiceError("diagnostic_timeout", "diagnostic read budget expired", 503)
    return remaining


def _diagnostic_code(error, fallback="diagnostic_unavailable"):
    code = error if isinstance(error, str) else getattr(error, "code", None)
    if isinstance(code, str) and code.isascii() and len(code) <= 80 and code.replace("_", "").isalnum():
        return code
    return fallback


def _diagnostic_failure(error, deadline, fallback="diagnostic_unavailable"):
    """Classify only known observation contention; never expose error text.

    Python 3.10 lacks SQLite's native error attributes. Its fallback accepts
    only exact built-in OperationalError instances with canonical lock args.
    A supplied native code takes precedence over text, including fatal codes.
    """
    native = getattr(error, "sqlite_errorcode", None) if isinstance(error, sqlite3.Error) else None
    native = native if type(native) is int and 0 <= native < 2**31 else None
    kind = ("sqlite_operational_error" if isinstance(error, sqlite3.OperationalError) else
            "sqlite_database_error" if isinstance(error, sqlite3.Error) else
            "writer_fence_error" if isinstance(error, WriterFenceError) else
            "service_error" if isinstance(error, ServiceError) else
            "storage_error" if isinstance(error, StorageError) else
            "os_error" if isinstance(error, OSError) else "unexpected_error")
    detail = {"type": kind}
    if isinstance(error, sqlite3.Error):
        detail["sqlite_errorcode"] = native
    exact_operational = type(error) is sqlite3.OperationalError
    lacks_native = exact_operational and not hasattr(error, "sqlite_errorcode")
    canonical_message = (error.args[0] if lacks_native and len(error.args) == 1
                         and type(error.args[0]) is str else None)
    busy = (exact_operational and native is not None and native & 255 in {5, 6}
            or lacks_native and canonical_message in {"database is locked", "database table is locked"})
    interrupted = (exact_operational and native is not None and native & 255 == 9
                   or lacks_native and canonical_message == "interrupted")
    code = _diagnostic_code(error, fallback)
    if busy or monotonic() >= deadline and (interrupted or code == "router_busy"):
        code = "diagnostic_timeout"
    return code, detail


class _DiagnosticDatabase(Database):
    """Existing-file, mode=ro reads with a shared overall SQL/guard deadline."""
    def __init__(self, source, deadline):
        super().__init__(source.path, timeout=_diagnostic_remaining(deadline))
        self._deadline = deadline
        self._identity_check = getattr(source, "_check_read_identity", None)

    def _connect(self):
        _diagnostic_remaining(self._deadline)
        # A raw close of this published inode would release other SQLite
        # connections' POSIX locks in this process. Inspect metadata only.
        before = os.stat(self.path, follow_symlinks=False)
        if (not stat.S_ISREG(before.st_mode) or before.st_size == 0 or
                before.st_uid != os.geteuid() or stat.S_IMODE(before.st_mode) & 0o077):
            raise StorageError("diagnostics require an existing private regular database")
        connection = sqlite3.connect(Path(self.path).as_uri() + "?mode=ro", uri=True,
                                     timeout=_diagnostic_remaining(self._deadline), isolation_level=None)
        try:
            after = os.stat(self.path, follow_symlinks=False)
            if ((before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)
                    or not stat.S_ISREG(after.st_mode) or after.st_size == 0
                    or after.st_uid != os.geteuid() or stat.S_IMODE(after.st_mode) & 0o077):
                raise StorageError("database changed during diagnostic open")
            connection.row_factory = sqlite3.Row
            # Install before Database's persistent-guard validation, not merely
            # after yielding a connection. Many small guard queries are bounded.
            connection.set_progress_handler(lambda: int(monotonic() >= self._deadline), 1)
            connection.execute("PRAGMA query_only=ON")
            connection.execute("PRAGMA foreign_keys=ON")
            # SQLite busy handlers are per-statement; a short contention cap
            # prevents many late statements from each waiting the full budget.
            connection.execute(f"PRAGMA busy_timeout={min(20, int(_diagnostic_remaining(self._deadline) * 1000))}")
            return connection
        except BaseException:
            connection.close()
            raise

    @contextmanager
    def read_transaction(self):
        with super().read_transaction() as connection:
            if self._identity_check is not None:
                self._identity_check(connection)
            _diagnostic_remaining(self._deadline)
            yield connection
            _diagnostic_remaining(self._deadline)


def _diagnostic_state(connection, descriptor, shard_count):
    if [tuple(row) for row in connection.execute("SELECT singleton,kind FROM uta_authority")] != [(1, "router_control")]:
        raise ServiceError("wrong_authority", "diagnostic control authority is invalid", 503)
    row = connection.execute("SELECT descriptor,payload FROM router_layout JOIN router_state USING(singleton) WHERE singleton=1").fetchone()
    if row is None or row[0] != descriptor or len(row[1]) > MAX_JSON_BYTES:
        raise ServiceError("layout_corruption", "diagnostic control descriptor is invalid", 503)
    state = json.loads(row[1])
    if (not isinstance(state, dict) or _json(state) != row[1]
            or type(state.get("halted")) is not bool or type(state.get("publishing")) is not bool
            or type(state.get("epoch")) is not int or state["epoch"] < 0
            or not isinstance(state.get("watermarks"), dict)):
        raise ServiceError("control_corruption", "diagnostic control flags are invalid", 503)
    version, digest = state.get("market_version"), state.get("market_digest")
    if (version is None and digest is not None or version is not None and (
            type(version) is not int or not 0 <= version < 2**63
            or not isinstance(digest, str) or len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest))):
        raise ServiceError("control_corruption", "diagnostic market generation is invalid", 503)
    indices = {str(index) for index in range(shard_count)}
    if any(key not in indices or type(value) is not int or not 0 <= value < 2**63
           for key, value in state["watermarks"].items()):
        raise ServiceError("control_corruption", "diagnostic watermarks are invalid", 503)
    complete = (version is not None and not state["publishing"]
                and set(state["watermarks"]) == indices
                and all(type(value) is int and value == version for value in state["watermarks"].values()))
    return state, complete


def _diagnostic_claims(connection, control, deadline):
    claims, codec = {}, Ledger(control.layout["scales"])
    # Read lengths before texts: legitimate canonical funding commands are tiny;
    # malformed large registry values must not bypass the overall read budget.
    for row in connection.execute("SELECT rowid,length(source_reference),length(command) FROM router_pool_sources"):
        _diagnostic_remaining(deadline)
        if row[1] is None or not 1 <= row[1] <= 128 or row[2] is None or not 1 <= row[2] <= 1024:
            raise ServiceError("funding_registry_conflict", "funding registry command is invalid", 503)
        reference, encoded = connection.execute("SELECT source_reference,command FROM router_pool_sources WHERE rowid=?", (row[0],)).fetchone()
        try:
            _name(reference, "source_reference")
            command = json.loads(encoded)
            if not isinstance(command, list) or len(command) != 4 or type(command[0]) is not int:
                raise ValueError("invalid funding command")
            control._index(command[0])
            _name(command[1], "command_id")
            _name(command[2], "asset")
            if (not isinstance(command[3], str) or codec._units(command[2], Decimal(command[3])) <= 0
                    or encoded != _json(command)):
                raise ValueError("invalid funding command")
        except (ValueError, TypeError, ArithmeticError) as exc:
            raise ServiceError("funding_registry_conflict", "funding registry command is invalid", 503) from exc
        claims[reference] = encoded
    return claims


def _diagnostic_market(connection, state, deadline):
    row = connection.execute("SELECT typeof(payload),length(CAST(payload AS BLOB)) FROM uta_market WHERE singleton=1").fetchone()
    if row is None:
        raise ServiceError("market_missing", "shard market is absent", 503)
    if row[0] != "text" or not 0 < row[1] <= MAX_JSON_BYTES:
        raise ServiceError("market_invalid", "shard market has invalid encoding or size", 503)
    payload = connection.execute("SELECT payload FROM uta_market WHERE singleton=1").fetchone()[0]
    try:
        snapshot = MarketSnapshot.from_json(payload)
    except (RiskInputError, TypeError, UnicodeError) as exc:
        raise ServiceError("market_invalid", "shard market cannot be decoded", 503) from exc
    _diagnostic_remaining(deadline)
    digest = sha256(payload.encode()).hexdigest()
    if (snapshot.version != state["market_version"] or digest != state["market_digest"]
            or sha256(snapshot.to_json().encode()).hexdigest() != digest):
        raise ServiceError("market_barrier_mismatch", "shard market differs from publication", 503)
    usd = snapshot.assets.get("USD")
    if (usd is None or usd.price != 1 or usd.collateral_factor != 1
            or any(spec.initial_margin_rate <= 0 or spec.maintenance_margin_rate <= 0
                   for spec in snapshot.instruments.values())):
        raise ServiceError("market_incomplete", "shard market lacks settlement or margin inputs", 503)
    for symbol, in connection.execute("SELECT DISTINCT symbol FROM uta_positions UNION SELECT DISTINCT symbol FROM uta_orders WHERE status IN ('OPEN','PARTIALLY_FILLED')"):
        if symbol not in snapshot.instruments:
            raise ServiceError("market_incomplete", "live instrument has no market input", 503)
    for asset, units in connection.execute("SELECT asset,units FROM ledger_balances WHERE account LIKE 'customer:%'"):
        if int(units) and asset not in snapshot.assets:
            raise ServiceError("market_incomplete", "funded asset has no market input", 503)
    for asset, principal, interest in connection.execute("SELECT asset,principal,interest FROM uta_liabilities"):
        if (Decimal(principal) != 0 or Decimal(interest) != 0) and asset not in snapshot.assets:
            raise ServiceError("market_incomplete", "liability has no market input", 503)
    _diagnostic_remaining(deadline)
    return snapshot, digest


def _options(encoded):
    return {"fee_rate": Decimal(encoded["fee_rate"]),
            "max_price_age": timedelta(microseconds=encoded["max_price_age_us"]),
            "product_catalog": ProductCatalog.from_json(encoded["catalog"]) if encoded["catalog"] else None,
            "portfolio_rules": PortfolioRules.from_json(encoded["portfolio"]) if encoded["portfolio"] else None,
            "reserve_cache_size": encoded["reserve_cache_size"], "market_cache_size": encoded["market_cache_size"],
            "decision_audit": encoded.get("decision_audit", False)}


def _authority(descriptor, shard):
    return "router:" + sha256(descriptor.encode()).hexdigest() + ":shard:" + str(shard)


def _financial_head(connection):
    head = connection.execute("SELECT sequence,event_hash FROM ledger_events ORDER BY sequence DESC LIMIT 1").fetchone()
    return {"ledger_sequence": head[0] if head else 0, "ledger_hash": head[1] if head else "0" * 64,
            "accounts": connection.execute("SELECT COUNT(*) FROM uta_accounts").fetchone()[0],
            "orders": connection.execute("SELECT COUNT(*) FROM uta_orders").fetchone()[0],
            "positions": connection.execute("SELECT COUNT(*) FROM uta_positions").fetchone()[0]}


def _spot_source_present(connection):
    return (connection.execute("SELECT 1 FROM sqlite_master WHERE name GLOB 'uta_spot_*' LIMIT 1").fetchone() is not None
            or connection.execute("SELECT 1 FROM uta_events WHERE event_type GLOB 'SPOT_*' LIMIT 1").fetchone() is not None)


def _verify_managed_spot_source(connection, database, scales):
    """LOCAL-MANAGED-MIG-001: retain verified history, reject live obligations.

    This joins the caller's read-only preflight or token-owned final snapshot.
    The explicitly limited verification views bypass constructors because both
    ExchangeService and DurableLedger constructors install/repair schema. These
    partial views issue verification queries only and never escape this helper.
    """
    from .service import ExchangeService
    from .spot import SpotExchange

    if not _spot_source_present(connection):
        return
    objects = {row["name"]: row["type"] for row in connection.execute(
        "SELECT name,type FROM sqlite_master WHERE name GLOB 'uta_spot_*'")}
    tables = {name for name, kind in objects.items() if kind == "table"}
    required = {"uta_spot_schema", "uta_spot_config", "uta_spot_orders",
                "uta_spot_matches", "uta_spot_fills"}
    try:
        if tables != required:
            raise ServiceError("spot_corrupt", "spot source schema is incomplete or unsupported; no repair was attempted", 503)
        for row in connection.execute("SELECT status,reserved_amount FROM uta_spot_orders"):
            reservation = Decimal(row["reserved_amount"])
            if not reservation.is_finite() or reservation < 0:
                raise ServiceError("spot_corrupt", "spot source reservation is invalid", 503)
            if row["status"] in ("OPEN", "PARTIALLY_FILLED") or reservation:
                raise ServiceError("managed_spot_state_unsupported",
                    "managed trading cannot service live spot orders or remaining asset locks; "
                    "cancel or settle on the original authority before sealing; after fencing use forward recovery", 409)
            if row["status"] not in ("FILLED", "CANCELLED"):
                raise ServiceError("spot_corrupt", "spot source order status is unsupported", 503)
        policy = json.loads(connection.execute("SELECT value FROM uta_config WHERE key='policy'").fetchone()[0])
        risk = json.loads(connection.execute("SELECT value FROM uta_config WHERE key='risk_policy'").fetchone()[0])
        configured = (ProductCatalog.from_json(_json(risk["catalog"]))
                      if risk["mode"] == "phase1_cross" else None)
        if risk["mode"] not in ("phase1_cross", "legacy_reference"):
            raise ServiceError("spot_corrupt", "spot source account policy is unsupported", 503)
        rows = connection.execute("SELECT singleton,catalog,fee_rate FROM uta_spot_config").fetchall()
        if len(rows) != 1 or rows[0]["singleton"] != 1:
            raise ServiceError("spot_corrupt", "spot source configuration is missing or invalid", 503)
        catalog = ProductCatalog.from_json(rows[0]["catalog"])
        if configured is not None and catalog != configured:
            raise ServiceError("spot_corrupt", "spot source catalog differs from its account policy", 503)
        exchange = ExchangeService.__new__(ExchangeService)
        exchange.database, exchange.scales = database, dict(scales)
        exchange._product_catalog = configured
        exchange.fee_rate = Decimal(policy["fee_rate"])
        if not exchange.fee_rate.is_finite() or not 0 <= exchange.fee_rate <= Decimal(".01"):
            raise ServiceError("spot_corrupt", "spot source fee policy is invalid", 503)
        ledger = DurableLedger.__new__(DurableLedger)
        ledger.database, ledger.scales, ledger._codec = database, dict(scales), Ledger(scales)
        exchange.ledger = ledger
        SpotExchange(exchange, catalog, initialize=False).verify(connection=connection)
    except ServiceError as exc:
        if exc.code == "managed_spot_state_unsupported" or exc.status == 503:
            raise
        raise ServiceError("spot_corrupt", "spot source configuration failed read-only verification", 503) from exc
    except (sqlite3.Error, ArithmeticError, ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        raise ServiceError("spot_corrupt", "spot source history failed read-only verification; no repair was attempted", 503) from exc


def _preflight_managed_spot_sources(control):
    """Check every source before creating pending manifests or any shard fence."""
    layout_hash = sha256(control._descriptor.encode()).hexdigest()
    for index in range(control.layout["shard_count"]):
        database = _BoundShardDatabase(control._path(index), index, layout_hash)
        with database.read_transaction() as connection:
            _verify_managed_spot_source(connection, database, control.layout["scales"])


def _preflight_managed_ledger_sources(control):
    """Offline all-shard journal validation before any irreversible fence.

    This never constructs a financial service or repairs schema. It is not an
    online activation step: full historical replay belongs to offline sealing.
    """
    layout_hash = sha256(control._descriptor.encode()).hexdigest()
    for index in range(control.layout["shard_count"]):
        database = _BoundShardDatabase(control._path(index), index, layout_hash)
        ledger = DurableLedger.__new__(DurableLedger)
        ledger.database, ledger.scales = database, dict(control.layout["scales"])
        ledger._codec = Ledger(ledger.scales)
        try:
            with database.read_transaction() as connection:
                ledger.verify(connection=connection)
        except (LedgerError, sqlite3.Error, StorageError) as exc:
            raise ServiceError("ledger_corrupt", "source journal failed read-only verification; no repair was attempted", 503) from exc


def _prepare_config(connection, config):
    connection.execute("CREATE TABLE router_durable_config(singleton INTEGER PRIMARY KEY CHECK(singleton=1),format INTEGER NOT NULL,initialized INTEGER NOT NULL,payload TEXT NOT NULL)")
    connection.execute("INSERT INTO router_durable_config VALUES (1,1,0,?)", (_json(config),))
    connection.execute("CREATE TRIGGER router_durable_config_no_delete BEFORE DELETE ON router_durable_config BEGIN SELECT RAISE(ABORT,'durable configuration is immutable'); END")
    connection.execute("CREATE TRIGGER router_durable_config_seal_only BEFORE UPDATE ON router_durable_config WHEN OLD.initialized!=0 OR NEW.initialized!=1 OR NEW.singleton!=OLD.singleton OR NEW.format!=OLD.format OR NEW.payload!=OLD.payload BEGIN SELECT RAISE(ABORT,'durable configuration is immutable'); END")


def _audit_capability_payload(control, config):
    return {"format": 1, "target_schema": 3, "required": True,
            "layout_hash": sha256(control._descriptor.encode()).hexdigest(),
            "source_config_hash": sha256(_json(config).encode()).hexdigest()}


def _read_audit_capability(control, config, *, allow_pending=False):
    with control.control.read_transaction() as connection:
        if connection.execute("SELECT 1 FROM sqlite_master WHERE name='router_decision_audit_capability'").fetchone() is None:
            return None
        rows = connection.execute("SELECT singleton,format,state,payload FROM router_decision_audit_capability").fetchall()
        guards = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='router_decision_audit_capability'")}
        if (len(rows) != 1 or tuple(rows[0])[:2] != (1, 1) or rows[0][2] not in ("PREPARED", "READY")
                or rows[0][3] != _json(_audit_capability_payload(control, config))
                or not {"router_audit_capability_no_delete", "router_audit_capability_no_replace", "router_audit_capability_seal_only"} <= guards):
            raise ServiceError("decision_audit_capability_corrupt", "audit promotion manifest is invalid or incomplete", 503)
        if rows[0][2] != "READY" and not allow_pending:
            raise ServiceError("decision_audit_upgrade_incomplete", "explicit audit promotion has not completed every shard", 503)
        return {"state": rows[0][2], "payload": json.loads(rows[0][3])}


def _process_identity(pid):
    details = Path(f"/proc/{pid}").stat()
    tail = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    return {"pid": pid, "start_ticks": int(tail[19]),
            "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(), "uid": details.st_uid,
            "state": tail[0]}


def _registry_schema(connection):
    present = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='router_process_owners'").fetchone()
    if present is None:
        connection.execute("""CREATE TABLE router_process_owners(
            sequence INTEGER PRIMARY KEY,kind TEXT NOT NULL,authority_id TEXT NOT NULL,shard INTEGER,
            nonce TEXT NOT NULL,generation INTEGER NOT NULL,pid INTEGER NOT NULL,start_ticks INTEGER NOT NULL,
            boot_id TEXT NOT NULL,coordinator TEXT NOT NULL,observed_at TEXT NOT NULL)""")
        for action in ("UPDATE", "DELETE"):
            connection.execute(f"CREATE TRIGGER router_process_owners_no_{action.lower()} BEFORE {action} ON router_process_owners BEGIN SELECT RAISE(ABORT,'process ownership evidence is immutable'); END")
    else:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(router_process_owners)")}
        triggers = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='router_process_owners'")}
        if columns != {"sequence", "kind", "authority_id", "shard", "nonce", "generation", "pid", "start_ticks", "boot_id", "coordinator", "observed_at"} or not {"router_process_owners_no_update", "router_process_owners_no_delete"} <= triggers:
            raise ServiceError("process_registry_corrupt", "process birth identity registry is incomplete", 503)


def _record_process(control, kind, shard, nonce, generation, identity, coordinator):
    authority = "layout:" + sha256(control._descriptor.encode()).hexdigest() if shard is None else _authority(control._descriptor, shard)
    with control.control.transaction() as connection:
        connection.execute("""INSERT INTO router_process_owners
            (kind,authority_id,shard,nonce,generation,pid,start_ticks,boot_id,coordinator,observed_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)""", (kind, authority, shard, nonce, generation, identity["pid"],
                identity["start_ticks"], identity["boot_id"], coordinator, datetime.now(timezone.utc).isoformat()))


class _SignalReceiver:
    """FD-backed lifecycle signal; parent death needs no named-semaphore cleanup."""
    def __init__(self, connection):
        self.connection, self.seen = connection, False

    def is_set(self):
        if not self.seen and self.connection.poll():
            try:
                self.connection.recv_bytes()
            except EOFError:
                pass
            self.seen = True
        return self.seen

    def wait(self, timeout):
        if not self.seen:
            self.connection.poll(timeout)
        return self.is_set()


class _SignalSender:
    def __init__(self, connection):
        self.connection, self.sent = connection, False

    def set(self):
        if not self.sent:
            self.sent = True
            try:
                self.connection.send_bytes(b"1")
            except (BrokenPipeError, OSError):
                pass

    def close(self):
        self.connection.close()


def _run_worker(directory, shard, settings, stop, ready, parent_pid, start_gate, owner_nonce, coordinator):
    """Spawn entry point: acquire a PID-bound token only inside this child."""
    fence = token = None
    try:
        while not start_gate.wait(.05):
            if stop.is_set() or os.getppid() != parent_pid:
                return
        if stop.is_set() or os.getppid() != parent_pid:
            return
        parent = DurableProcessRouter(directory, _only_shard=shard, **settings)
        database = parent._database(shard)
        fence = WriterFence(database)
        while not stop.is_set() and os.getppid() == parent_pid:
            try:
                token = fence.acquire(owner_nonce, settings["lease_seconds"])
                break
            except WriterFenceError as exc:
                if exc.code != "lease_busy":
                    raise
                stop.wait(min(settings["poll_interval"], .1))
        if token is None:
            return
        from .startup import _OwnedStartup
        with _OwnedStartup(database.for_writer(token), lease_seconds=settings["lease_seconds"],
                           stop=stop, parent_pid=parent_pid) as initialization:
            _record_process(parent._control, "OWNED", shard, owner_nonce, token.generation,
                            _process_identity(os.getpid()), coordinator)
            view = ShardWorkerView(directory, shard, token, service_options=_options(parent._config["service"]),
                                   account_batch=settings["account_batch"], matches_per_symbol=settings["matches_per_symbol"],
                                   _startup=initialization)
            store = parent._queue(shard)
            with initialization.database.read_transaction() as connection:
                fence.assert_writer(connection, token)
                _verify_managed_spot_source(connection, initialization.database, parent.layout["scales"])
            # A long read sees the original lease row, while the keeper renews
            # the current one. Validate current lifecycle after closing it; the
            # final fresh fenced COMMIT below checks actual ownership/expiry.
            initialization.check()
            initialization.finish()
            # Keep same-PID actor exclusion through READY publication. Transfer
            # the actual renewal start, not the end of slow initialization.
            renew_at = initialization.last_renew_started + settings["lease_seconds"] / 3
            if stop.is_set() or os.getppid() != parent_pid:
                return
            ready.send({"state": "ready", "shard": shard, "pid": os.getpid(), "generation": token.generation})
        background_at = monotonic()
        while not stop.is_set() and os.getppid() == parent_pid:
            now = monotonic()
            if now >= renew_at:
                # Anchor to the start of renewal, not time spent waiting for
                # the database/COMMIT. Slow storage cannot postpone the deadline.
                renew_at = now + settings["lease_seconds"] / 3
                fence.renew(token, settings["lease_seconds"])
            worked = False
            try:
                receipt = view.process_one(store)
                worked = receipt is not None
            except CommandExecutionError as exc:
                cause = exc.cause
                if isinstance(cause, WriterFenceError):
                    raise cause
                if exc.command_id is None:
                    raise
                # Query first: an exception after COMMIT must never overwrite
                # the durable terminal fact or replay financial side effects.
                existing = store.status(exc.command_id)
                if existing is None:
                    raise
                if existing["state"] not in _TERMINAL:
                    with view._control._lock():
                        store.record_failure(view._exchange, exc.command_id,
                                             max_attempts=settings["max_attempts"],
                                             backoff_seconds=settings["poll_interval"],
                                             cause=exc.cause, attempt=exc.attempt)
            if monotonic() >= background_at:
                view.run_background_once()  # Real risk plans and paired trades.
                background_at = monotonic() + settings["background_interval"]
            if not worked:
                stop.wait(settings["poll_interval"])
    except BaseException as exc:
        try:
            ready.send({"state": "failed", "shard": shard, "pid": os.getpid(),
                        "code": getattr(exc, "code", type(exc).__name__)})
        except (BrokenPipeError, EOFError, OSError):
            pass
        # The parent observes actual process exit and may spawn a new owner.
        raise
    finally:
        if fence is not None and token is not None:
            try:
                fence.release(token)
            except Exception:
                pass  # A dead/expired owner cannot release a newer generation.
        ready.close()


class DurableProcessRouter:
    """Durable producer/control surface and supervised spawn workers.

    Reopening reads existing control/queue metadata. It never initializes an
    ExchangeService, ledger, or unrelated managed shard as an unbound writer.
    """

    @classmethod
    def initialize(cls, directory, shard_count, scales, *, managed=False, bootstrap=None,
                   fee_rate=Decimal(".0004"), max_price_age=timedelta(seconds=30),
                   product_catalog=None, portfolio_rules=None,
                   reserve_cache_size=0, market_cache_size=0,
                   queue_capacity=1024, cancel_reserve=16, market_capacity=4,
                   decision_audit=True, **runtime):
        if type(decision_audit) is not bool:
            raise ValueError("decision_audit must be a boolean")
        if managed is not True:
            raise ServiceError("managed_opt_in_required", "fresh managed layout initialization requires managed=True", 409)
        path = Path(directory).expanduser().absolute()
        if path.exists() and any(path.iterdir()):
            raise ServiceError("managed_migration_required", "existing layouts require an explicit offline take-over protocol", 409)
        if bootstrap is not None and not callable(bootstrap):
            raise ValueError("bootstrap must be callable")
        router = ShardRouter(path, shard_count, scales, fee_rate=fee_rate, max_price_age=max_price_age,
                             product_catalog=product_catalog, portfolio_rules=portfolio_rules,
                             reserve_cache_size=reserve_cache_size, market_cache_size=market_cache_size,
                             decision_audit=decision_audit)
        if bootstrap is not None:
            bootstrap(router)  # Explicit offline administration before sealing.
        config = {"descriptor": router._descriptor,
                  "service": {"fee_rate": _text(fee_rate),
                              "max_price_age_us": max_price_age // timedelta(microseconds=1),
                              "catalog": product_catalog.to_json() if product_catalog else None,
                              "portfolio": portfolio_rules.to_json() if portfolio_rules else None,
                              "reserve_cache_size": reserve_cache_size, "market_cache_size": market_cache_size,
                              "decision_audit": decision_audit},
                  "queue": {"queue_capacity": queue_capacity, "cancel_reserve": cancel_reserve,
                            "market_capacity": market_capacity}}
        router.set_kill_switch(True)
        with router._lock(exclusive=True):
            leases = []
            try:
                _preflight_managed_ledger_sources(router)
                _preflight_managed_spot_sources(router)
                router._reconcile_funding()
                with router.control.transaction() as connection:
                    _prepare_config(connection, config)
                for index, service in enumerate(router._services):
                    QueueStore(service.database, initialize=True, **config["queue"])
                    fence = WriterFence(service.database)
                    fence.enable(_authority(router._descriptor, index))
                    # Preserve the fresh no-spot generation-zero contract. Once
                    # fenced, an old standalone writer cannot add a new schema.
                    # Any spot footprint still needs token-owned final checking.
                    with service.database.read_transaction() as connection:
                        if not _spot_source_present(connection):
                            continue
                    token = fence.acquire("initialize:" + uuid4().hex, 60)
                    leases.append((fence, token))
                    database = service.database.for_writer(token)
                    with database.read_transaction() as connection:
                        fence.assert_writer(connection, token)
                        _verify_managed_spot_source(connection, database, router.layout["scales"])
                        fence.assert_writer(connection, token)
                for fence, token in leases:
                    fence.renew(token, 60)
                with router.control.transaction() as connection:
                    connection.execute("UPDATE router_durable_config SET initialized=1 WHERE singleton=1")
            except BaseException as exc:
                router._write_state({**router._state(), "halted": True,
                                     "error": getattr(exc, "code", "managed_bootstrap_incomplete")})
                raise
            finally:
                for fence, token in reversed(leases):
                    try:
                        fence.release(token)
                    except WriterFenceError:
                        pass
        return cls(path, **runtime)

    @classmethod
    def inspect_takeover(cls, directory):
        """Read-only plan, not a cross-shard monetary snapshot or approval."""
        control = _open_router_control(directory)
        shards = []
        with control._lock():
            state = control._state()
            for index in range(control.layout["shard_count"]):
                database = _BoundShardDatabase(control._path(index), index, sha256(control._descriptor.encode()).hexdigest())
                lease = WriterFence(database).status()
                with database.read_transaction() as connection:
                    head = _financial_head(connection)
                    queue = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='uta_command_config'").fetchone() is not None
                shards.append({"shard": index, "managed": lease["managed"], "lease_active": lease["active"],
                               "queue_present": queue, **head})
        return {"layout_hash": sha256(control._descriptor.encode()).hexdigest(),
                "descriptor": json.loads(control._descriptor), "state": state, "shards": shards}

    @classmethod
    def take_over(cls, directory, *, managed=False, expected_layout_hash,
                  queue_capacity=1024, cancel_reserve=16, market_capacity=4,
                  decision_audit=True, **runtime):
        """Explicit, resumable offline sealing of an existing legacy layout.

        Original policy, account mapping, ledger and accepted orders are kept.
        A durable incomplete manifest prevents normal workers from opening until
        every shard is fenced, verified, and recorded. Completion stays halted.
        """
        if managed is not True:
            raise ServiceError("managed_opt_in_required", "take-over requires managed=True", 409)
        if type(decision_audit) is not bool:
            raise ValueError("decision_audit must be a boolean")
        control = _open_router_control(directory)
        layout_hash = sha256(control._descriptor.encode()).hexdigest()
        if expected_layout_hash != layout_hash:
            raise ServiceError("layout_conflict", "reviewed layout hash does not match this authority", 409)
        holder = cls.__new__(cls)
        holder.directory, holder._supervisor_fd = control.directory, None
        holder._claim_supervisor()
        try:
            with control._lock(exclusive=True, timeout=30):
                state = control._state()
                control._write_state({**state, "halted": True, "error": "takeover_in_progress"})
                leases = []
                try:
                    _preflight_managed_ledger_sources(control)
                    _preflight_managed_spot_sources(control)
                    first = _BoundShardDatabase(control._path(0), 0, layout_hash)
                    with first.read_transaction() as connection:
                        policies = dict(connection.execute("SELECT key,value FROM uta_config WHERE key IN ('policy','risk_policy')"))
                    policy, risk = json.loads(policies["policy"]), json.loads(policies["risk_policy"])
                    if risk["mode"] not in ("legacy_reference", "phase1_cross"):
                        raise ServiceError("configuration_corrupt", "unsupported existing risk policy", 503)
                    catalog = _json(risk["catalog"]) if risk["mode"] == "phase1_cross" else None
                    portfolio = _json(risk["rules"]) if risk["mode"] == "phase1_cross" else None
                    service = {"fee_rate": policy["fee_rate"], "max_price_age_us": policy["max_price_age_us"],
                               "catalog": catalog, "portfolio": portfolio,
                               "reserve_cache_size": 0, "market_cache_size": 0,
                               "decision_audit": decision_audit}
                    original_policy = {"fee_rate": service["fee_rate"], "max_price_age_us": service["max_price_age_us"],
                                       "catalog": json.loads(catalog) if catalog else None,
                                       "portfolio": json.loads(portfolio) if portfolio else None}
                    if sha256(_json(original_policy).encode()).hexdigest() != control.layout["policy_hash"]:
                        raise ServiceError("configuration_conflict", "existing financial policy does not match its layout", 503)
                    config = {"descriptor": control._descriptor, "service": service,
                              "queue": dict(queue_capacity=queue_capacity, cancel_reserve=cancel_reserve,
                                            market_capacity=market_capacity)}
                    with control.control.transaction() as connection:
                        existing = connection.execute("SELECT 1 FROM sqlite_master WHERE name='router_durable_config'").fetchone()
                        if existing is None:
                            _prepare_config(connection, config)
                            connection.execute("CREATE TABLE router_durable_takeover_events(sequence INTEGER PRIMARY KEY,stage TEXT NOT NULL,shard INTEGER,payload TEXT NOT NULL,observed_at TEXT NOT NULL)")
                            for action in ("UPDATE", "DELETE"):
                                connection.execute(f"CREATE TRIGGER router_durable_takeover_no_{action.lower()} BEFORE {action} ON router_durable_takeover_events BEGIN SELECT RAISE(ABORT,'take-over audit is immutable'); END")
                            connection.execute("INSERT INTO router_durable_takeover_events(stage,payload,observed_at) VALUES ('PREPARED',?,?)",
                                               (_json({"layout_hash": layout_hash}), datetime.now(timezone.utc).isoformat()))
                        else:
                            row = connection.execute("SELECT format,initialized,payload FROM router_durable_config WHERE singleton=1").fetchone()
                            if row is None or row[0] != 1 or row[1] != 0 or row[2] != _json(config):
                                raise ServiceError("configuration_conflict", "take-over may resume only its exact incomplete configuration", 409)
                            if connection.execute("SELECT 1 FROM sqlite_master WHERE name='router_durable_takeover_events'").fetchone() is None:
                                raise ServiceError("takeover_audit_missing", "incomplete bootstrap is not a recorded take-over", 503)
                    claims = control._batch_funding_claims()
                    for index in range(control.layout["shard_count"]):
                        database = _BoundShardDatabase(control._path(index), index, layout_hash)
                        fence = WriterFence(database)
                        status = fence.status()
                        if not status["managed"]:
                            # Queue creation precedes the irreversible marker;
                            # a resumed managed prefix must already have it.
                            QueueStore(database, initialize=True, **config["queue"])
                            fence.enable(_authority(control._descriptor, index))
                        elif status["authority_id"] != _authority(control._descriptor, index):
                            raise ServiceError("managed_authority_conflict", "existing managed prefix has another identity", 503)
                        QueueStore(database, **config["queue"])
                        token = fence.acquire("takeover:" + uuid4().hex, 60)
                        leases.append((fence, token))
                        from .credit import CreditService
                        from .service import ExchangeService
                        owned = ExchangeService(database.for_writer(token), control.layout["scales"], **_options(service))
                        owned.set_kill_switch(True)
                        CreditService(owned).verify()
                        with owned._transaction() as connection:
                            _verify_managed_spot_source(connection, owned.database, control.layout["scales"])
                            fence.assert_writer(connection, token)
                            control._batch_reconcile_shard(connection, index, claims)
                            for row in connection.execute("SELECT account_id FROM uta_accounts UNION SELECT account_id FROM uta_command_inbox WHERE account_id IS NOT NULL"):
                                if control.shard_for(row[0]) != index:
                                    raise ServiceError("shard_identity_conflict", "existing account or queued command belongs to another shard", 503)
                            head = {**_financial_head(connection), "writer_generation": token.generation}
                        with control.control.transaction() as connection:
                            connection.execute("INSERT INTO router_durable_takeover_events(stage,shard,payload,observed_at) VALUES ('SHARD_FENCED',?,?,?)",
                                               (index, _json(head), datetime.now(timezone.utc).isoformat()))
                    for fence, token in leases:
                        fence.renew(token, 60)  # Every verified shard remains owned through sealing.
                    with control.control.transaction() as connection:
                        connection.execute("INSERT INTO router_durable_takeover_events(stage,payload,observed_at) VALUES ('COMPLETED',?,?)",
                                           (_json({"layout_hash": layout_hash}), datetime.now(timezone.utc).isoformat()))
                        connection.execute("UPDATE router_durable_config SET initialized=1 WHERE singleton=1")
                    control._write_state({**control._state(), "halted": True, "error": None})
                except BaseException as exc:
                    control._write_state({**control._state(), "halted": True,
                                          "error": getattr(exc, "code", "takeover_incomplete")})
                    raise
                finally:
                    for fence, token in reversed(leases):
                        try:
                            fence.release(token)
                        except WriterFenceError:
                            pass
        finally:
            os.close(holder._supervisor_fd)
        return cls(directory, **runtime)

    @classmethod
    def plan_decision_audit_upgrade(cls, directory):
        control = _open_router_control(directory)
        with control.control.read_transaction() as connection:
            row = connection.execute("SELECT initialized,payload FROM router_durable_config WHERE singleton=1").fetchone()
        if row is None or row[0] != 1:
            raise ServiceError("managed_bootstrap_incomplete", "finish managed initialization before planning audit promotion", 503)
        config = json.loads(row[1])
        capability = _read_audit_capability(control, config, allow_pending=True)
        plan = cls.inspect_takeover(directory)
        for shard in plan["shards"]:
            database = _BoundShardDatabase(control._path(shard["shard"]), shard["shard"], plan["layout_hash"])
            with database.read_transaction() as connection:
                shard["trading_schema"] = connection.execute("SELECT version FROM uta_schema").fetchone()[0]
        return {**plan, "target_schema": 3, "source_config_hash": sha256(row[1].encode()).hexdigest(),
                "capability": capability}

    @classmethod
    def upgrade_decision_audit(cls, directory, *, managed=False, expected_layout_hash, **runtime):
        """Explicit offline promotion; never rewrite immutable old configuration."""
        if managed is not True:
            raise ServiceError("managed_opt_in_required", "audit promotion requires managed=True", 409)
        control = _open_router_control(directory)
        layout_hash = sha256(control._descriptor.encode()).hexdigest()
        if expected_layout_hash != layout_hash:
            raise ServiceError("layout_conflict", "reviewed layout hash does not match this authority", 409)
        with control._lock(exclusive=True, timeout=30):
            control._write_state({**control._state(), "halted": True, "error": "decision_audit_upgrade_requested"})
        holder = cls.__new__(cls)
        holder.directory, holder._supervisor_fd = control.directory, None
        holder._claim_supervisor()  # A live coordinator must be stopped first.
        try:
            with control._lock(exclusive=True, timeout=30):
                leases = []
                try:
                    with control.control.read_transaction() as connection:
                        row = connection.execute("SELECT format,initialized,payload FROM router_durable_config WHERE singleton=1").fetchone()
                    if row is None or tuple(row)[:2] != (1, 1):
                        raise ServiceError("managed_bootstrap_incomplete", "managed configuration is not sealed", 503)
                    config = json.loads(row[2])
                    if config["descriptor"] != control._descriptor or _json(config) != row[2]:
                        raise ServiceError("configuration_corrupt", "promotion source configuration is invalid", 503)
                    capability = _read_audit_capability(control, config, allow_pending=True)
                    if capability is None:
                        initial = {"layout_hash": layout_hash, "target_schema": 3,
                                   "source_config_hash": sha256(row[2].encode()).hexdigest(), "shards": []}
                        for index in range(control.layout["shard_count"]):
                            source = _BoundShardDatabase(control._path(index), index, layout_hash)
                            with source.read_transaction() as connection:
                                initial["shards"].append({"shard": index, **_financial_head(connection),
                                    "trading_schema": connection.execute("SELECT version FROM uta_schema").fetchone()[0]})
                        with control.control.transaction() as connection:
                            connection.execute("CREATE TABLE router_decision_audit_capability(singleton INTEGER PRIMARY KEY CHECK(singleton=1),format INTEGER NOT NULL,state TEXT NOT NULL CHECK(state IN ('PREPARED','READY')),payload TEXT NOT NULL)")
                            connection.execute("INSERT INTO router_decision_audit_capability VALUES (1,1,'PREPARED',?)", (_json(_audit_capability_payload(control, config)),))
                            connection.execute("CREATE TRIGGER router_audit_capability_no_delete BEFORE DELETE ON router_decision_audit_capability BEGIN SELECT RAISE(ABORT,'audit requirement is irreversible'); END")
                            connection.execute("CREATE TRIGGER router_audit_capability_no_replace BEFORE INSERT ON router_decision_audit_capability WHEN EXISTS (SELECT 1 FROM router_decision_audit_capability WHERE singleton=NEW.singleton) BEGIN SELECT RAISE(ABORT,'audit requirement cannot be replaced'); END")
                            connection.execute("CREATE TRIGGER router_audit_capability_seal_only BEFORE UPDATE ON router_decision_audit_capability WHEN OLD.state!='PREPARED' OR NEW.state!='READY' OR NEW.singleton!=OLD.singleton OR NEW.format!=OLD.format OR NEW.payload!=OLD.payload BEGIN SELECT RAISE(ABORT,'audit requirement is immutable'); END")
                            connection.execute("CREATE TABLE router_decision_audit_events(sequence INTEGER PRIMARY KEY,stage TEXT NOT NULL,shard INTEGER,payload TEXT NOT NULL,observed_at TEXT NOT NULL)")
                            for action in ("UPDATE", "DELETE"):
                                connection.execute(f"CREATE TRIGGER router_decision_audit_events_no_{action.lower()} BEFORE {action} ON router_decision_audit_events BEGIN SELECT RAISE(ABORT,'audit promotion evidence is immutable'); END")
                            connection.execute("INSERT INTO router_decision_audit_events(stage,payload,observed_at) VALUES ('PREPARED',?,?)",
                                               (_json(initial), datetime.now(timezone.utc).isoformat()))
                    if capability is None or capability["state"] != "READY":
                        options = _options(config["service"])
                        options["decision_audit"] = True
                        claims = control._batch_funding_claims()
                        for index in range(control.layout["shard_count"]):
                            database = _BoundShardDatabase(control._path(index), index, layout_hash)
                            fence = WriterFence(database)
                            status = fence.status()
                            if not status["managed"] or status["authority_id"] != _authority(control._descriptor, index):
                                raise ServiceError("managed_authority_conflict", "promotion shard has another writer authority", 503)
                            with database.read_transaction() as connection:
                                before = _financial_head(connection)
                            token = fence.acquire("audit-upgrade:" + uuid4().hex, 60)
                            leases.append((fence, token))
                            from .credit import CreditService
                            from .service import ExchangeService
                            owned = ExchangeService(database.for_writer(token), control.layout["scales"], **options)
                            owned.set_kill_switch(True)
                            CreditService(owned).verify()
                            with owned._transaction() as connection:
                                control._batch_reconcile_shard(connection, index, claims)
                                after = _financial_head(connection)
                                if before != after:
                                    raise ServiceError("audit_promotion_changed_financial_state", "audit promotion must preserve ledger heads and account/order/position counts", 503)
                                legacy = dict(connection.execute("SELECT * FROM uta_audit_capability WHERE singleton=1").fetchone())
                            with control.control.transaction() as connection:
                                connection.execute("INSERT INTO router_decision_audit_events(stage,shard,payload,observed_at) VALUES ('SHARD_REQUIRED',?,?,?)",
                                                   (index, _json({"before": before, "after": after, "legacy_gap": legacy,
                                                                  "writer_generation": token.generation}), datetime.now(timezone.utc).isoformat()))
                        for fence, token in leases:
                            fence.renew(token, 60)
                        with control.control.transaction() as connection:
                            connection.execute("INSERT INTO router_decision_audit_events(stage,payload,observed_at) VALUES ('READY',?,?)",
                                               (_json({"layout_hash": layout_hash}), datetime.now(timezone.utc).isoformat()))
                            connection.execute("UPDATE router_decision_audit_capability SET state='READY' WHERE singleton=1")
                        control._write_state({**control._state(), "halted": True, "error": None})
                    control._write_state({**control._state(), "halted": True, "error": None})
                except BaseException as exc:
                    control._write_state({**control._state(), "halted": True,
                                          "error": getattr(exc, "code", "decision_audit_upgrade_incomplete")})
                    raise
                finally:
                    for fence, token in reversed(leases):
                        try:
                            fence.release(token)
                        except WriterFenceError:
                            pass
        finally:
            os.close(holder._supervisor_fd)
        return cls(directory, **runtime)

    def __init__(self, directory, *, lease_seconds=5.0, poll_interval=.02,
                 background_interval=.1, account_batch=25, matches_per_symbol=10,
                 max_attempts=3, _only_shard=None):
        for name, value, lower, upper in (("lease_seconds", lease_seconds, .05, 3600),
                                          ("poll_interval", poll_interval, .001, 60),
                                          ("background_interval", background_interval, .01, 60)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lower <= value <= upper:
                raise ValueError(f"{name} is outside its supported range")
        for name, value, upper in (("account_batch", account_batch, 1000), ("matches_per_symbol", matches_per_symbol, 1000), ("max_attempts", max_attempts, 100)):
            if type(value) is not int or not 1 <= value <= upper:
                raise ValueError(f"{name} requires an integer in 1..{upper}")
        self._control = _open_router_control(directory)
        with self._control.control.read_transaction() as connection:
            try:
                row = connection.execute("SELECT format,initialized,payload FROM router_durable_config WHERE singleton=1").fetchone()
            except sqlite3.Error as exc:
                raise ServiceError("managed_layout_required", "layout is not initialized for durable process ownership", 409) from exc
        if row is None or row[0] != 1 or row[1] != 1:
            raise ServiceError("managed_bootstrap_incomplete", "managed layout initialization did not finish; offline recovery is required", 503)
        try:
            self._config = json.loads(row[2])
            if self._config["descriptor"] != self._control._descriptor or _json(self._config) != row[2]:
                raise ValueError("configuration identity differs")
        except (ValueError, TypeError, KeyError) as exc:
            raise ServiceError("configuration_corrupt", "durable process configuration is invalid", 503) from exc
        audit_setting = self._config["service"].get("decision_audit", False)
        if type(audit_setting) is not bool:
            raise ServiceError("configuration_corrupt", "managed audit requirement must be a boolean", 503)
        self.decision_audit_required = audit_setting
        self._explicit_development_profile = "decision_audit" in self._config["service"] and not audit_setting
        capability = _read_audit_capability(self._control, self._config)
        if capability is not None:
            self._config["service"]["decision_audit"] = True
            self.decision_audit_required = True
            self._explicit_development_profile = False
        self.directory, self.layout = self._control.directory, self._control.layout
        self._settings = dict(lease_seconds=lease_seconds, poll_interval=poll_interval,
                              background_interval=background_interval, account_batch=account_batch,
                              matches_per_symbol=matches_per_symbol, max_attempts=max_attempts)
        self._queues, self._workers, self._reports = {}, {}, {}
        self._start_gates = {}
        self._recovered_orphans = []
        self._coordinator = None
        self._mutex, self._stop = RLock(), Event()
        self._monitor = None
        self._supervisor_fd = None
        self._context = multiprocessing.get_context("spawn")
        indices = range(self.layout["shard_count"]) if _only_shard is None else (self._control._index(_only_shard),)
        try:
            for index in indices:
                status = WriterFence(self._database(index)).status()
                if not status["managed"] or status["authority_id"] != _authority(self._control._descriptor, index):
                    raise ServiceError("managed_authority_conflict", "shard is not bound to its expected managed authority", 503)
                if status.get("guard_format") != 1:
                    raise WriterFenceError("fence_upgrade_required", "stop existing writers and explicitly upgrade persistent SQL guards before starting processes")
                with self._database(index).read_transaction() as connection:
                    _verify_managed_spot_source(connection, self._database(index), self.layout["scales"])
                    version = connection.execute("SELECT version FROM uta_schema").fetchone()
                    if self.decision_audit_required:
                        if version is None or version[0] != 3:
                            raise ServiceError("decision_audit_capability_mismatch", "required authority is not schema 3; an old snapshot must not be silently promoted at restart", 503)
                        audit = connection.execute("SELECT format FROM uta_audit_capability WHERE singleton=1").fetchone()
                        if audit is None or audit[0] != 1:
                            raise ServiceError("decision_audit_capability_mismatch", "required shard audit capability is absent", 503)
                    elif version is not None and version[0] == 3:
                        raise ServiceError("decision_audit_configuration_conflict", "schema 3 requires an explicit recorded audit capability", 503)
                self._queue(index)  # Existing queue metadata only; never bootstrap.
        except BaseException as exc:
            with self._control._lock(exclusive=True):
                state = self._control._state()
                self._control._write_state({**state, "halted": True,
                                           "error": getattr(exc, "code", "managed_shard_unavailable")})
            raise

    def _database(self, shard):
        shard = self._control._index(shard)
        return _BoundShardDatabase(self._control._path(shard), shard,
                                   sha256(self._control._descriptor.encode()).hexdigest())

    def _queue(self, shard):
        if shard not in self._queues:
            self._queues[shard] = QueueStore(self._database(shard), **self._config["queue"])
        return self._queues[shard]

    def shard_for(self, account_id):
        return self._control.shard_for(account_id)

    def submit_order(self, account_id, command_id, order_id, symbol, quantity, limit_price, *, reduce_only=False):
        return self._queue(self.shard_for(account_id)).enqueue_submit(account_id, command_id, order_id,
                        symbol, quantity, limit_price, reduce_only=reduce_only)

    def cancel_order(self, account_id, command_id, order_id):
        return self._queue(self.shard_for(account_id)).enqueue_cancel(account_id, command_id, order_id)

    def repay(self, account_id, command_id, asset, amount):
        return self._queue(self.shard_for(account_id)).enqueue_repay(account_id, command_id, asset, amount)

    def status(self, command_id, *, account_id=None, shard=None):
        if account_id is not None:
            index = self.shard_for(account_id)
            if shard is not None and shard != index:
                return None
            return self._queue(index).status(command_id, account_id=account_id)
        if shard is None:
            raise ServiceError("invalid_input", "status requires account_id or explicit shard")
        return self._queue(self._control._index(shard)).status(command_id)

    def wait(self, command_id, *, account_id=None, shard=None, timeout=10):
        if isinstance(timeout, bool) or not isinstance(timeout, (float, int)) or not math.isfinite(timeout) or not 0 <= timeout <= 3600:
            raise ValueError("timeout requires seconds in 0..3600")
        deadline = monotonic() + timeout
        while True:
            receipt = self.status(command_id, account_id=account_id, shard=shard)
            if receipt is None or receipt["state"] in _TERMINAL or monotonic() >= deadline:
                return receipt
            sleep(min(self._settings["poll_interval"], max(0, deadline - monotonic())))

    def _claim_supervisor(self):
        path = self.directory / "router.supervisor.lock"
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
        try:
            details = os.fstat(descriptor)
            if not stat.S_ISREG(details.st_mode) or details.st_uid != os.geteuid() or stat.S_IMODE(details.st_mode) & 0o077:
                raise ServiceError("unsafe_lock", "supervisor lock must remain private", 503)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ServiceError("supervisor_busy", "another parent supervises this layout", 409) from exc
        except BaseException:
            os.close(descriptor)
            raise
        self._supervisor_fd = descriptor

    def _spawn(self, shard):
        stop_read, stop_write = self._context.Pipe(duplex=False)
        gate_read, gate_write = self._context.Pipe(duplex=False)
        stop, start_gate = _SignalSender(stop_write), _SignalSender(gate_write)
        self._start_gates[shard] = start_gate
        nonce = "worker:" + uuid4().hex
        receive, send = self._context.Pipe(duplex=False)
        process = self._context.Process(target=_run_worker,
            args=(str(self.directory), shard, self._settings, _SignalReceiver(stop_read), send, os.getpid(), _SignalReceiver(gate_read), nonce, self._coordinator),
            name=f"uta-shard-{shard}")
        process.start()
        stop_read.close()
        gate_read.close()
        send.close()
        self._workers[shard] = (process, stop, receive)
        # Child cannot acquire or touch a financial authority until its kernel
        # birth identity and intended authority/nonce are durably registered.
        _record_process(self._control, "SPAWNED", shard, nonce, 0,
                        _process_identity(process.pid), self._coordinator)
        start_gate.set()

    def _recover_registered_orphans(self, timeout):
        with self._control.control.read_transaction() as connection:
            if connection.execute("SELECT 1 FROM sqlite_master WHERE name='router_process_owners'").fetchone() is None:
                return
            _registry_schema(connection)  # Present schema must already be intact.
            candidates = [dict(row) for row in connection.execute("SELECT * FROM router_process_owners WHERE kind='SPAWNED' ORDER BY sequence")]
        deadline = monotonic() + timeout
        for candidate in candidates:
            shard, pid = candidate["shard"], candidate["pid"]
            self._control._index(shard)
            if candidate["authority_id"] != _authority(self._control._descriptor, shard) or pid in (1, os.getpid()):
                continue
            try:
                identity = _process_identity(pid)
            except (OSError, ValueError, IndexError):
                continue
            if (identity["uid"] != os.geteuid() or identity["start_ticks"] != candidate["start_ticks"]
                    or identity["boot_id"] != candidate["boot_id"] or identity["state"] == "Z"):
                continue  # No bare-PID killing after reuse or a host reboot.
            if not hasattr(os, "pidfd_open") or not hasattr(signal, "pidfd_send_signal"):
                raise ServiceError("orphan_identity_unavailable", "registered orphan recovery requires Linux pidfd support", 503)
            try:
                pidfd = os.pidfd_open(pid)
            except ProcessLookupError:
                continue
            try:
                # Opening pidfd before the second /proc check anchors the kill
                # to that exact process even if the integer PID is later reused.
                again = _process_identity(pid)
                if (again["start_ticks"], again["boot_id"], again["uid"]) != (identity["start_ticks"], identity["boot_id"], identity["uid"]):
                    continue
                fence = WriterFence(self._database(shard))
                lease = fence.status()
                if lease.get("authority_id") != candidate["authority_id"]:
                    raise ServiceError("managed_authority_conflict", "orphan proof belongs to another authority", 503)
                if lease.get("owner_pid") == pid and lease.get("owner_nonce") != candidate["nonce"]:
                    continue  # Same PID now has another identity; never guess.
                while (lease.get("owner_pid") == pid and lease.get("owner_nonce") == candidate["nonce"] and lease["active"]):
                    if monotonic() >= deadline:
                        raise ServiceError("ownership_recovery_pending", "registered prior owner still has an unexpired lease", 503)
                    sleep(.02)
                    lease = fence.status()
                if lease.get("owner_pid") == pid and lease.get("owner_nonce") != candidate["nonce"]:
                    continue
                # Either this exact owner expired, or the registered old child
                # has no current token (e.g. died while acquiring one). A new
                # coordinator owns the exclusive supervision flock; it never
                # terminates an unregistered external owner.
                signal.pidfd_send_signal(pidfd, signal.SIGKILL)
                exited = select.poll()
                exited.register(pidfd, select.POLLIN)
                if not exited.poll(1000):
                    raise ServiceError("orphan_recovery_pending", "registered orphan has not exited", 503)
                self._recovered_orphans.append({"shard": shard, "pid": pid,
                    "start_ticks": identity["start_ticks"], "boot_id": identity["boot_id"],
                    "nonce": candidate["nonce"], "generation": lease.get("generation", 0),
                    "coordinator": candidate["coordinator"]})
            except (ProcessLookupError, FileNotFoundError):
                pass
            finally:
                os.close(pidfd)

    def start(self, *, recovery_timeout=10):
        if isinstance(recovery_timeout, bool) or not isinstance(recovery_timeout, (float, int)) or not math.isfinite(recovery_timeout) or not 0 <= recovery_timeout <= 3600:
            raise ValueError("recovery_timeout requires seconds in 0..3600")
        with self._mutex:
            if self._supervisor_fd is not None:
                raise ServiceError("supervisor_started", "supervisor is already running", 409)
            self._claim_supervisor()
            self._stop.clear()
            try:
                with self._control.control.read_transaction() as connection:
                    source = json.loads(connection.execute("SELECT payload FROM router_durable_config WHERE singleton=1").fetchone()[0])
                latest = _read_audit_capability(self._control, source)
                required = source["service"].get("decision_audit", False) or latest is not None
                if not required and "decision_audit" not in source["service"]:
                    raise ServiceError("decision_audit_upgrade_required", "unclassified existing managed authority requires an explicit offline audit upgrade", 503)
                if required != self.decision_audit_required:
                    raise ServiceError("configuration_refresh_required", "reopen the parent after an irreversible audit capability promotion", 503)
                self._coordinator = uuid4().hex
                self._recovered_orphans = []
                self._recover_registered_orphans(recovery_timeout)
                with self._control._lock(exclusive=True, timeout=recovery_timeout):
                    with self._control.control.transaction() as connection:
                        _registry_schema(connection)
                    _record_process(self._control, "COORDINATOR", None, self._coordinator, 0,
                                    _process_identity(os.getpid()), self._coordinator)
                    for orphan in self._recovered_orphans:
                        _record_process(self._control, "ORPHAN_KILLED", orphan["shard"], orphan["nonce"],
                            orphan["generation"], orphan, self._coordinator)
                for shard in range(self.layout["shard_count"]):
                    self._spawn(shard)
                self._monitor = Thread(target=self._supervise, name="uta-process-supervisor", daemon=True)
                self._monitor.start()
            except BaseException:
                self.close()
                raise
        return self

    def _supervise(self):
        while not self._stop.wait(.05):
            with self._mutex:
                for shard, (process, stop, pipe) in list(self._workers.items()):
                    try:
                        while pipe.poll():
                            self._reports[shard] = pipe.recv()
                    except (EOFError, OSError):
                        pass
                    if process.is_alive():
                        observer = self._database(shard)
                        observer.timeout = .1
                        try:
                            lease = WriterFence(observer).status()
                        except Exception:
                            lease = None
                        if (lease is not None and lease.get("owner_pid") == process.pid
                                and not lease["active"]):
                            # SIGSTOP can hold a router SH gate indefinitely.
                            # Lease expiry alone fences commits but does not
                            # release flock. Kill only our own unreaped child,
                            # then let the next PID acquire a new generation.
                            process.kill()
                            process.join(timeout=1)
                    if not process.is_alive() and not self._stop.is_set():
                        process.join()
                        pipe.close()
                        stop.close()
                        self._start_gates[shard].close()
                        self._spawn(shard)

    def worker_pid(self, shard):
        with self._mutex:
            worker = self._workers.get(self._control._index(shard))
            return worker[0].pid if worker is not None and worker[0].is_alive() else None

    def terminate_worker(self, shard):
        """Force a real process exit; supervision acquires a new generation."""
        with self._mutex:
            process = self._workers[self._control._index(shard)][0]
            process.kill()
            process.join(timeout=5)

    def diagnostics(self, *, timeout=1.0):
        """Bounded, read-only readiness observation; never financial permission.

        The shared gate covers control/claims and each shard's same-transaction
        lease plus complete market payload. Freshness is rechecked at the end
        using the original observation time. A failed read never means ready.
        """
        if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
                or not math.isfinite(timeout) or not 0 < timeout <= 5):
            raise ValueError("diagnostic timeout requires seconds in (0,5]")
        deadline = monotonic() + timeout
        rows = [{"shard": shard, "pid": None, "alive": False, "lease_active": False,
                 "owner_pid": None, "generation": None, "report": {}, "market_ready": False,
                 "owner_ready": False, "locally_active": False,
                 "funding_registry_ready": False, "reason": "not_observed"}
                for shard in range(self.layout["shard_count"])]
        result = {"state": None, "state_observed": False, "workers": rows, "managed": True,
                  "decision_audit_required": self.decision_audit_required,
                  "profile": "managed_audit_required" if self.decision_audit_required else "managed_development_legacy_gap",
                  "recovered_orphans": [], "workers_alive": False,
                  "financial_ready": False, "ready": False, "reason": "diagnostic_unavailable"}
        acquired = False
        try:
            # Match start/close's mutex-before-router-gate ordering. Both waits
            # consume the same budget, including a concurrent supervisor close.
            acquired = self._mutex.acquire(timeout=_diagnostic_remaining(deadline))
            if not acquired:
                raise ServiceError("diagnostic_timeout", "supervisor observation timed out", 503)
            result["recovered_orphans"] = [
                {key: row[key] for key in ("shard", "pid", "start_ticks", "generation")}
                for row in self._recovered_orphans]
            for row in rows:
                worker = self._workers.get(row["shard"])
                row["alive"] = worker is not None and worker[0].is_alive()
                row["pid"] = worker[0].pid if row["alive"] else None
                report = self._reports.get(row["shard"], {})
                row["report"] = {key: report[key] for key in ("shard", "pid", "generation")
                                 if type(report.get(key)) is int}
                if report.get("state") in {"ready", "failed"}:
                    row["report"]["state"] = report["state"]
                if "code" in report:
                    # Reports are diagnostics only; never expose exception text.
                    row["report"]["code"] = _diagnostic_code(report["code"])
            result["workers_alive"] = all(row["alive"] for row in rows)
            with self._control._lock(timeout=_diagnostic_remaining(deadline)):
                control_reader = _DiagnosticDatabase(self._control.control, deadline)
                with control_reader.read_transaction() as connection:
                    state, complete = _diagnostic_state(connection, self._control._descriptor, len(rows))
                    result["state"] = {key: state[key] for key in (
                        "halted", "publishing", "epoch", "market_version", "market_digest", "watermarks")}
                    result["state"]["error"] = None if state.get("error") is None else _diagnostic_code(state["error"])
                    result["state_observed"] = True
                    claims = _diagnostic_claims(connection, self._control, deadline)
                observed = []
                for row in rows:
                    shard = row["shard"]
                    try:
                        reader = _DiagnosticDatabase(self._database(shard), deadline)
                        with reader.read_transaction() as connection:
                            lease = _load_writer_lease(connection)
                            if (lease is None or lease["authority_id"] != _authority(self._control._descriptor, shard)
                                    or lease["guard_format"] != 1):
                                raise ServiceError("managed_authority_conflict", "shard writer authority is invalid", 503)
                            now_ns, boot = _observe_writer_clock(reader, lease)
                            row.update(owner_pid=lease["owner_pid"], generation=lease["generation"],
                                       lease_active=lease["owner_nonce"] is not None and boot == lease["boot_id"]
                                       and now_ns < lease["expires_ns"])
                            flag = connection.execute("SELECT value FROM uta_config WHERE key='halted'").fetchone()
                            row["locally_active"] = flag is not None and flag[0] == "false"
                            if self.decision_audit_required:
                                schema = connection.execute("SELECT version FROM uta_schema").fetchone()
                                audit = connection.execute("SELECT format FROM uta_audit_capability WHERE singleton=1").fetchone()
                                if schema is None or schema[0] != 3 or audit is None or audit[0] != 1:
                                    raise ServiceError("decision_audit_capability_mismatch", "required shard audit capability is unavailable", 503)
                            self._control._batch_reconcile_shard(connection, shard, claims)
                            snapshot, digest = _diagnostic_market(connection, state, deadline)
                            row.update(market_version=snapshot.version, market_digest=digest,
                                       market_observed_at=snapshot.observed_at.isoformat())
                        # Guard verification at read-transaction exit must also
                        # succeed before this observation can become ready.
                        row["funding_registry_ready"] = True
                        observed.append((row, reader, lease, snapshot))
                        row["reason"] = "observed"
                    except Exception as exc:
                        row["reason"], row["observation_error"] = _diagnostic_failure(
                            exc, deadline, "shard_unavailable")
                # Slow guard/claim checks cannot leave an early-shard quote or
                # lease marked fresh after it expires during this observation.
                for row, reader, lease, snapshot in observed:
                    now_ns, boot = _observe_writer_clock(reader, lease)
                    row["lease_active"] = (row["lease_active"] and boot == lease["boot_id"]
                                           and now_ns < lease["expires_ns"])
                for row in rows:
                    worker = self._workers.get(row["shard"])
                    row["alive"] = row["alive"] and worker is not None and worker[0].is_alive()
                    row["owner_ready"] = (row["alive"] and row["pid"] == row["owner_pid"]
                                          and row["lease_active"] and row["report"].get("state") == "ready"
                                          and row["report"].get("pid") == row["pid"]
                                          and row["report"].get("generation") == row["generation"])
                now = datetime.now(timezone.utc)
                max_age = timedelta(microseconds=self._config["service"]["max_price_age_us"])
                for row, reader, lease, snapshot in observed:
                    try:
                        snapshot.validate(now=now, max_age=max_age)
                    except RiskInputError:
                        row["reason"] = "market_stale" if now - snapshot.observed_at > max_age else "market_future"
                    else:
                        row["market_ready"] = True
                        row["reason"] = "ready"
                result["workers_alive"] = all(row["alive"] for row in rows)
                # A later busy shard/deadline must not hide a known fatal read
                # from an earlier shard and invite another readiness sample.
                fatal_read = next((row["reason"] for row in rows
                                   if row["reason"] not in {"ready", "diagnostic_timeout"}), None)
                if fatal_read is None:
                    _diagnostic_remaining(deadline)
                financial_ready = (complete and not state["halted"] and all(
                    row["owner_ready"] and row["market_ready"] and row.get("locally_active", False)
                    and row["funding_registry_ready"] for row in rows))
                result.update(financial_ready=financial_ready, ready=financial_ready)
                if state["publishing"] or not complete:
                    result["reason"] = "publication_incomplete"
                elif state["halted"]:
                    result["reason"] = "router_halted"
                elif financial_ready:
                    result["reason"] = "ready"
                elif fatal_read is not None:
                    result["reason"] = fatal_read
                else:
                    result["reason"] = next((row["reason"] for row in rows if not row["market_ready"]),
                                            "worker_unready" if not all(row["owner_ready"] for row in rows) else "local_halt")
        except Exception as exc:
            reason, detail = _diagnostic_failure(exc, deadline)
            result.update(financial_ready=False, ready=False, reason=reason, observation_error=detail)
        finally:
            if acquired:
                self._mutex.release()
        return result

    def _receipts(self, commands, timeout):
        deadline = monotonic() + timeout
        results = {}
        for index, command_id in commands.items():
            receipt = self.wait(command_id, shard=int(index), timeout=max(0, deadline - monotonic()))
            results[index] = receipt
        return results

    def publish_market(self, snapshot, *, timeout=10):
        if not isinstance(snapshot, MarketSnapshot):
            raise ServiceError("invalid_market", "publish a validated MarketSnapshot")
        payload, commands = snapshot.to_json(), {}
        digest = sha256(payload.encode()).hexdigest()
        if isinstance(timeout, bool) or not isinstance(timeout, (float, int)) or not math.isfinite(timeout) or not 0 <= timeout <= 3600:
            raise ValueError("timeout requires seconds in 0..3600")
        with self._control._lock(exclusive=True, timeout=timeout):
            state = self._control._state()
            previous = state["market_version"]
            if previous is not None and (snapshot.version < previous or snapshot.version == previous and digest != state["market_digest"]):
                raise ServiceError("market_conflict", "global market version regressed or changed content", 409)
            if state["publishing"] and (snapshot.version < state.get("target_version", snapshot.version)
                    or snapshot.version == state.get("target_version") and digest != state.get("target_digest")):
                raise ServiceError("market_conflict", "cannot regress or change an in-progress market generation", 409)
            # Reuse the exact pending publication after a parent crash.
            if state["publishing"] and state.get("target_digest") == digest:
                commands = state["durable_market_commands"]
            else:
                epoch = state["epoch"] + 1
                commands = {str(index): f"market:{epoch}:{index}:{digest[:16]}" for index in range(self.layout["shard_count"])}
                state.update(halted=True, publishing=True, epoch=epoch, target_version=snapshot.version,
                             target_digest=digest, watermarks={}, durable_market_commands=commands,
                             durable_halt_commands={}, durable_desired_halt=True, error=None)
                self._control._write_state(state)
            for index, command_id in commands.items():
                self._queue(int(index)).enqueue_market(command_id, snapshot)
        receipts = self._receipts(commands, timeout)
        with self._control._lock(exclusive=True, timeout=timeout):
            state = self._control._state()
            if state.get("durable_market_commands") != commands:
                raise ServiceError("control_superseded", "another market publication superseded this request", 409)
            state["watermarks"] = {index: snapshot.version for index, receipt in receipts.items()
                                    if receipt is not None and receipt["state"] == "SUCCEEDED"}
            if len(state["watermarks"]) == self.layout["shard_count"]:
                for index in commands:
                    with self._database(int(index)).read_transaction() as connection:
                        row = connection.execute("SELECT payload FROM uta_market WHERE singleton=1").fetchone()
                        if row is None or sha256(row[0].encode()).hexdigest() != digest:
                            self._control._write_state({**state, "halted": True, "error": "market_barrier_mismatch"})
                            raise ServiceError("market_barrier_mismatch", "published receipts disagree with persisted market", 503)
                state.update(publishing=False, market_version=snapshot.version, market_digest=digest, error=None)
            else:
                state.update(halted=True, publishing=True, error="market_fanout_incomplete")
            self._control._write_state(state)
            return {**state, "receipts": receipts}

    def set_kill_switch(self, enabled, *, timeout=10):
        if type(enabled) is not bool:
            raise ServiceError("invalid_input", "enabled must be a boolean")
        if isinstance(timeout, bool) or not isinstance(timeout, (float, int)) or not math.isfinite(timeout) or not 0 <= timeout <= 3600:
            raise ValueError("timeout requires seconds in 0..3600")
        with self._control._lock(exclusive=True, timeout=timeout):
            state = self._control._state()
            state.update(halted=True)
            self._control._write_state(state)
            if not enabled and (state["publishing"] or state["market_version"] is None):
                raise ServiceError("publication_incomplete", "complete market fanout before activation", 503)
            if not enabled:
                try:
                    _preflight_managed_spot_sources(self._control)
                except ServiceError as exc:
                    self._control._write_state({**state, "halted": True, "error": exc.code})
                    raise
            transition = uuid4().hex
            commands = {str(index): f"halt:{transition}:{index}" for index in range(self.layout["shard_count"])}
            state.update(durable_halt_commands=commands, durable_desired_halt=enabled, error=None)
            self._control._write_state(state)
            for index, command_id in commands.items():
                self._queue(int(index)).enqueue_halt(command_id, enabled)
        receipts = self._receipts(commands, timeout)
        with self._control._lock(exclusive=True, timeout=timeout):
            state = self._control._state()
            if state.get("durable_halt_commands") != commands:
                raise ServiceError("control_superseded", "another halt transition superseded this request", 409)
            complete = all(receipt is not None and receipt["state"] == "SUCCEEDED" for receipt in receipts.values())
            if not enabled and complete:
                # Recheck current data/freshness using read-only parent access;
                # this never opens an unbound financial writer.
                if state["publishing"]:
                    raise ServiceError("publication_incomplete", "publication interrupted the activation", 503)
                claims = self._control._batch_funding_claims()
                for index in commands:
                    with self._database(int(index)).read_transaction() as connection:
                        _verify_managed_spot_source(connection, self._database(int(index)), self.layout["scales"])
                        self._control._batch_reconcile_shard(connection, int(index), claims)
                        local_halt = connection.execute("SELECT value FROM uta_config WHERE key='halted'").fetchone()
                        if local_halt is None or local_halt[0] != "false":
                            raise ServiceError("activation_incomplete", "local halt transition did not remain applied", 503)
                        row = connection.execute("SELECT payload FROM uta_market WHERE singleton=1").fetchone()
                        snapshot = MarketSnapshot.from_json(row[0]) if row is not None else None
                        if snapshot is None or sha256(snapshot.to_json().encode()).hexdigest() != state["market_digest"]:
                            raise ServiceError("market_barrier_mismatch", "activation market is incomplete", 503)
                        from datetime import datetime, timezone
                        snapshot.validate(now=datetime.now(timezone.utc), max_age=timedelta(microseconds=self._config["service"]["max_price_age_us"]))
                state.update(halted=False, error=None)
            elif not complete:
                state.update(halted=True, error="halt_fanout_incomplete")
            self._control._write_state(state)
            return {**state, "receipts": receipts}

    def close(self):
        self._stop.set()
        monitor = self._monitor
        if monitor is not None and monitor is not current_thread():
            monitor.join(timeout=5)
        with self._mutex:
            workers, self._workers = self._workers, {}
            for process, stop, pipe in workers.values():
                stop.set()
            for process, stop, pipe in workers.values():
                process.join(timeout=5)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=5)
                pipe.close()
                stop.close()
            if self._supervisor_fd is not None:
                os.close(self._supervisor_fd)
                self._supervisor_fd = None
            self._monitor = None
            for gate in self._start_gates.values():
                gate.close()
            self._start_gates.clear()

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc, tb):
        self.close()
