"""Single-host, independently fenced process owners for durable shard inboxes.

Commands and outcomes live in each financial SQLite database. Multiprocessing
objects carry only lifecycle signals; no financial command or receipt depends
on a parent process, shared manager, Future, or in-memory transport surviving.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
from .market import MarketSnapshot
from .portfolio import PortfolioRules
from .products import ProductCatalog
from .service import ServiceError, _name, _text
from .sharding import (_BoundShardDatabase, ShardRouter, ShardWorkerView,
                       _json, _open_router_control)
from .writer_fence import WriterFence, WriterFenceError


_TERMINAL = frozenset({"SUCCEEDED", "REJECTED", "QUARANTINED"})


def _options(encoded):
    return {"fee_rate": Decimal(encoded["fee_rate"]),
            "max_price_age": timedelta(microseconds=encoded["max_price_age_us"]),
            "product_catalog": ProductCatalog.from_json(encoded["catalog"]) if encoded["catalog"] else None,
            "portfolio_rules": PortfolioRules.from_json(encoded["portfolio"]) if encoded["portfolio"] else None,
            "reserve_cache_size": encoded["reserve_cache_size"], "market_cache_size": encoded["market_cache_size"]}


def _authority(descriptor, shard):
    return "router:" + sha256(descriptor.encode()).hexdigest() + ":shard:" + str(shard)


def _financial_head(connection):
    head = connection.execute("SELECT sequence,event_hash FROM ledger_events ORDER BY sequence DESC LIMIT 1").fetchone()
    return {"ledger_sequence": head[0] if head else 0, "ledger_hash": head[1] if head else "0" * 64,
            "accounts": connection.execute("SELECT COUNT(*) FROM uta_accounts").fetchone()[0],
            "orders": connection.execute("SELECT COUNT(*) FROM uta_orders").fetchone()[0],
            "positions": connection.execute("SELECT COUNT(*) FROM uta_positions").fetchone()[0]}


def _prepare_config(connection, config):
    connection.execute("CREATE TABLE router_durable_config(singleton INTEGER PRIMARY KEY CHECK(singleton=1),format INTEGER NOT NULL,initialized INTEGER NOT NULL,payload TEXT NOT NULL)")
    connection.execute("INSERT INTO router_durable_config VALUES (1,1,0,?)", (_json(config),))
    connection.execute("CREATE TRIGGER router_durable_config_no_delete BEFORE DELETE ON router_durable_config BEGIN SELECT RAISE(ABORT,'durable configuration is immutable'); END")
    connection.execute("CREATE TRIGGER router_durable_config_seal_only BEFORE UPDATE ON router_durable_config WHEN OLD.initialized!=0 OR NEW.initialized!=1 OR NEW.singleton!=OLD.singleton OR NEW.format!=OLD.format OR NEW.payload!=OLD.payload BEGIN SELECT RAISE(ABORT,'durable configuration is immutable'); END")


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
        _record_process(parent._control, "OWNED", shard, owner_nonce, token.generation,
                        _process_identity(os.getpid()), coordinator)
        view = ShardWorkerView(directory, shard, token, service_options=_options(parent._config["service"]),
                               account_batch=settings["account_batch"], matches_per_symbol=settings["matches_per_symbol"])
        store = parent._queue(shard)
        ready.send({"state": "ready", "shard": shard, "pid": os.getpid(), "generation": token.generation})
        renew_at, background_at = monotonic() + settings["lease_seconds"] / 3, monotonic()
        while not stop.is_set() and os.getppid() == parent_pid:
            now = monotonic()
            if now >= renew_at:
                fence.renew(token, settings["lease_seconds"])
                renew_at = monotonic() + settings["lease_seconds"] / 3
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
                                             backoff_seconds=settings["poll_interval"])
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
                   queue_capacity=1024, cancel_reserve=16, market_capacity=4, **runtime):
        if managed is not True:
            raise ServiceError("managed_opt_in_required", "fresh managed layout initialization requires managed=True", 409)
        path = Path(directory).expanduser().absolute()
        if path.exists() and any(path.iterdir()):
            raise ServiceError("managed_migration_required", "existing layouts require an explicit offline take-over protocol", 409)
        if bootstrap is not None and not callable(bootstrap):
            raise ValueError("bootstrap must be callable")
        router = ShardRouter(path, shard_count, scales, fee_rate=fee_rate, max_price_age=max_price_age,
                             product_catalog=product_catalog, portfolio_rules=portfolio_rules,
                             reserve_cache_size=reserve_cache_size, market_cache_size=market_cache_size)
        if bootstrap is not None:
            bootstrap(router)  # Explicit offline administration before sealing.
        config = {"descriptor": router._descriptor,
                  "service": {"fee_rate": _text(fee_rate),
                              "max_price_age_us": max_price_age // timedelta(microseconds=1),
                              "catalog": product_catalog.to_json() if product_catalog else None,
                              "portfolio": portfolio_rules.to_json() if portfolio_rules else None,
                              "reserve_cache_size": reserve_cache_size, "market_cache_size": market_cache_size},
                  "queue": {"queue_capacity": queue_capacity, "cancel_reserve": cancel_reserve,
                            "market_capacity": market_capacity}}
        router.set_kill_switch(True)
        with router._lock(exclusive=True):
            router._reconcile_funding()
            with router.control.transaction() as connection:
                _prepare_config(connection, config)
            for index, service in enumerate(router._services):
                QueueStore(service.database, initialize=True, **config["queue"])
                WriterFence(service.database).enable(_authority(router._descriptor, index))
            with router.control.transaction() as connection:
                connection.execute("UPDATE router_durable_config SET initialized=1 WHERE singleton=1")
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
                  queue_capacity=1024, cancel_reserve=16, market_capacity=4, **runtime):
        """Explicit, resumable offline sealing of an existing legacy layout.

        Original policy, account mapping, ledger and accepted orders are kept.
        A durable incomplete manifest prevents normal workers from opening until
        every shard is fenced, verified, and recorded. Completion stays halted.
        """
        if managed is not True:
            raise ServiceError("managed_opt_in_required", "take-over requires managed=True", 409)
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
                               "reserve_cache_size": 0, "market_cache_size": 0}
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

    def diagnostics(self):
        state = self._control._state()
        rows = []
        with self._mutex:
            for shard in range(self.layout["shard_count"]):
                lease = WriterFence(self._database(shard)).status()
                rows.append({"shard": shard, "pid": self.worker_pid(shard), "lease_active": lease["active"],
                             "owner_pid": lease.get("owner_pid"), "generation": lease.get("generation"),
                             "report": dict(self._reports.get(shard, {}))})
        return {"state": state, "workers": rows, "managed": True,
                "recovered_orphans": [{key: row[key] for key in ("shard", "pid", "start_ticks", "generation")} for row in self._recovered_orphans],
                "ready": not state["halted"] and not state["publishing"] and all(
                    row["pid"] is not None and row["pid"] == row["owner_pid"] and row["lease_active"] for row in rows)}

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
