"""EXPERIMENTAL single-host account routing, not distributed settlement or HA.

Every account risk group belongs to one immutable SHA-256 shard. All writers
must enter this router: direct ExchangeService writers bypass its global gate.
Host flock coordinates control barriers, not a distributed ownership lease.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import timedelta
from decimal import Decimal
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
from types import MappingProxyType

from .credit import CreditService
from .ledger import Ledger
from .market import MarketSnapshot
from .matching import Matcher
from .service import ExchangeService, ServiceError, _name, _text
from .storage import Database


HASH_VERSION = "sha256-utf8-big-endian-mod-v1"


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


class ShardRouter:
    """Immutable account routing with durable fail-closed publication barriers.

    Local commits retain SQLite WAL/FULL semantics. Acknowledgement is neither
    replication nor a cross-shard commit. A new layout always starts halted;
    successful market fanout remains halted until explicit operator activation.
    """

    def __init__(self, directory, shard_count, scales, *, fee_rate=Decimal(".0004"),
                 max_price_age=timedelta(seconds=5), clock=None,
                 product_catalog=None, portfolio_rules=None):
        if type(shard_count) is not int or not 1 <= shard_count <= 256:
            raise ServiceError("invalid_layout", "shard count must be in 1..256")
        Ledger(scales)  # Validate without creating financial state.
        policy = {"fee_rate": _text(fee_rate), "max_price_age_us": max_price_age // timedelta(microseconds=1),
                  "catalog": None if product_catalog is None else json.loads(product_catalog.to_json()),
                  "portfolio": None if portfolio_rules is None else json.loads(portfolio_rules.to_json())}
        descriptor = {"format": 1, "shard_count": shard_count, "hash_version": HASH_VERSION,
                      "scales": dict(scales), "policy_hash": sha256(_json(policy).encode()).hexdigest()}
        self._descriptor = _json(descriptor)
        self.layout = MappingProxyType({**descriptor, "scales": MappingProxyType(dict(scales))})
        candidate = Path(directory).expanduser().absolute()
        if candidate.is_symlink():
            raise ServiceError("unsafe_directory", "router directory must not be a symbolic link")
        candidate.mkdir(mode=0o700, parents=True, exist_ok=True)
        details = candidate.stat()
        if not stat.S_ISDIR(details.st_mode) or details.st_uid != os.geteuid() or stat.S_IMODE(details.st_mode) & 0o077:
            raise ServiceError("unsafe_directory", "router requires a private service-user-owned directory")
        self.directory = candidate.resolve()
        self.control = Database(self.directory / "router.sqlite3")
        self._lock_path = self.directory / "router.lock"
        self._services = []
        with self._lock(exclusive=True):
            with self.control.transaction() as connection:
                connection.execute("CREATE TABLE IF NOT EXISTS router_layout (singleton INTEGER PRIMARY KEY CHECK(singleton=1), descriptor TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS router_state (singleton INTEGER PRIMARY KEY CHECK(singleton=1), payload TEXT NOT NULL)")
                connection.execute("CREATE TABLE IF NOT EXISTS router_pool_sources (source_reference TEXT PRIMARY KEY, command TEXT NOT NULL)")
                for action in ("UPDATE", "DELETE"):
                    connection.execute(f"CREATE TRIGGER IF NOT EXISTS router_layout_no_{action.lower()} BEFORE {action} ON router_layout BEGIN SELECT RAISE(ABORT,'layout is immutable'); END")
                    connection.execute(f"CREATE TRIGGER IF NOT EXISTS router_pool_sources_no_{action.lower()} BEFORE {action} ON router_pool_sources BEGIN SELECT RAISE(ABORT,'source claims are immutable'); END")
                row = connection.execute("SELECT descriptor FROM router_layout WHERE singleton=1").fetchone()
                fresh = row is None
                if row is not None and row[0] != self._descriptor:
                    raise ServiceError("layout_conflict", "persisted shard layout or policy differs; online re-sharding is unsupported", 409)
                if fresh:
                    if list(self.directory.glob("shard-*.sqlite3")):
                        raise ServiceError("layout_missing", "existing shard files have no trustworthy layout descriptor", 503)
                    connection.execute("INSERT INTO router_layout VALUES (1,?)", (self._descriptor,))
                    connection.execute("INSERT INTO router_state VALUES (1,?)", (_json({
                        "halted": True, "publishing": False, "epoch": 0, "market_version": None,
                        "market_digest": None, "watermarks": {}, "error": None}),))
            if not fresh and any(not self._intact_file(index) for index in range(shard_count)):
                state = self._state()
                self._write_state({**state, "halted": True, "error": "missing_shard"})
                raise ServiceError("shard_unavailable", "a persisted shard is missing; automatic recreation is forbidden", 503)
            try:
                for index in range(shard_count):
                    if not fresh:
                        self._verify_identity(index)
                    service = ExchangeService(Database(self._path(index)), scales, fee_rate=fee_rate,
                        max_price_age=max_price_age, clock=clock, product_catalog=product_catalog,
                        portfolio_rules=portfolio_rules)
                    if fresh:
                        with service.database.transaction() as connection:
                            connection.execute("CREATE TABLE router_shard_identity (singleton INTEGER PRIMARY KEY CHECK(singleton=1), shard INTEGER NOT NULL, layout_hash TEXT NOT NULL)")
                            connection.execute("INSERT INTO router_shard_identity VALUES (1,?,?)", (index, sha256(self._descriptor.encode()).hexdigest()))
                            for action in ("UPDATE", "DELETE"):
                                connection.execute(f"CREATE TRIGGER router_shard_identity_no_{action.lower()} BEFORE {action} ON router_shard_identity BEGIN SELECT RAISE(ABORT,'shard identity is immutable'); END")
                    self._services.append(service)
            except BaseException:
                self._write_state({**self._state(), "halted": True, "error": "shard_initialization_failed"})
                raise

    def _path(self, index):
        return self.directory / f"shard-{index:04d}.sqlite3"

    def _intact_file(self, index):
        try:
            details = self._path(index).stat(follow_symlinks=False)
            return stat.S_ISREG(details.st_mode) and details.st_size > 0
        except OSError:
            return False

    def _verify_identity(self, index):
        connection = sqlite3.connect(self._path(index).as_uri() + "?mode=ro", uri=True)
        try:
            row = connection.execute("SELECT shard,layout_hash FROM router_shard_identity WHERE singleton=1").fetchone()
            if row is None or tuple(row) != (index, sha256(self._descriptor.encode()).hexdigest()):
                raise ServiceError("shard_identity_conflict", "shard database does not belong to this layout and index", 503)
        except sqlite3.DatabaseError as exc:
            raise ServiceError("shard_identity_conflict", "persisted shard identity is missing or invalid", 503) from exc
        finally:
            connection.close()

    @contextmanager
    def _lock(self, *, exclusive=False):
        flags = os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK
        try:
            descriptor = os.open(self._lock_path, flags | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            descriptor = os.open(self._lock_path, flags)
        try:
            details = os.fstat(descriptor)
            if not stat.S_ISREG(details.st_mode) or details.st_uid != os.geteuid() or stat.S_IMODE(details.st_mode) & 0o077:
                raise ServiceError("unsafe_lock", "router lock must be private and owned by the service user")
            fcntl.flock(descriptor, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
            yield
        finally:
            os.close(descriptor)

    def _state(self):
        # A read-only connection avoids taking a global SQLite write lock on
        # every admission; flock protects this snapshot through the shard commit.
        details = os.stat(self.control.path, follow_symlinks=False)
        if not stat.S_ISREG(details.st_mode) or details.st_uid != os.geteuid() or stat.S_IMODE(details.st_mode) & 0o077:
            raise ServiceError("unsafe_control", "router control database must remain private and owned by the service user", 503)
        connection = sqlite3.connect(Path(self.control.path).as_uri() + "?mode=ro", uri=True)
        try:
            connection.execute("PRAGMA query_only=ON")
            row = connection.execute("SELECT descriptor,payload FROM router_layout JOIN router_state USING(singleton) WHERE singleton=1").fetchone()
            if row is None or row[0] != self._descriptor:
                raise ServiceError("layout_corruption", "router layout or control state is unavailable", 503)
            state = json.loads(row[1])
            if (type(state.get("halted")) is not bool or type(state.get("publishing")) is not bool
                or type(state.get("epoch")) is not int or state["epoch"] < 0
                or not isinstance(state.get("watermarks"), dict)):
                raise ServiceError("control_corruption", "router control flags are invalid", 503)
            version, digest = state.get("market_version"), state.get("market_digest")
            if version is not None and (type(version) is not int or version < 0 or
                not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
                raise ServiceError("control_corruption", "router market generation is invalid", 503)
            if not state["halted"] and (state["publishing"] or version is None or
                state["watermarks"] != {str(index): version for index in range(self.layout["shard_count"])}):
                raise ServiceError("control_corruption", "active router has no complete publication barrier", 503)
            return state
        finally:
            connection.close()

    def _write_state(self, state):
        with self.control.transaction() as connection:
            connection.execute("UPDATE router_state SET payload=? WHERE singleton=1", (_json(state),))

    def shard_for(self, account_id):
        _name(account_id, "account_id")
        return int.from_bytes(sha256(account_id.encode("utf-8")).digest(), "big") % self.layout["shard_count"]

    def _index(self, shard):
        if type(shard) is not int or not 0 <= shard < self.layout["shard_count"]:
            raise ServiceError("invalid_shard", "shard index is outside the immutable layout")
        return shard

    def require_same_shard(self, *account_ids):
        shards = {self.shard_for(account) for account in account_ids}
        if len(shards) != 1:
            raise ServiceError("cross_shard_unsupported", "cross-shard paired settlement and transfers are unsupported", 409)
        return shards.pop()

    @contextmanager
    def _gate(self, *, exposure=False):
        with self._lock():
            state = self._state()
            if exposure and (state["halted"] or state["publishing"]):
                raise ServiceError("router_halted", "global control is halted or market publication is incomplete", 503)
            yield

    def create_account(self, account_id):
        with self._gate():
            return self._services[self.shard_for(account_id)].create_account(account_id)

    def deposit(self, account_id, event_id, asset, amount):
        with self._gate():
            return self._services[self.shard_for(account_id)].deposit(account_id, event_id, asset, amount)

    def account(self, account_id):
        with self._gate():
            return self._services[self.shard_for(account_id)].account(account_id)

    def risk(self, account_id):
        with self._gate():
            return self._services[self.shard_for(account_id)].risk(account_id)

    def orders(self, account_id):
        with self._gate():
            return self._services[self.shard_for(account_id)].orders(account_id)

    def submit_order(self, account_id, order_id, symbol, quantity, limit_price, *, reduce_only=False):
        # A partial publication blocks even reductions: the router must not
        # authorize against an incompletely published global market generation.
        with self._gate(exposure=True):
            return self._services[self.shard_for(account_id)].submit_order(
                account_id, order_id, symbol, quantity, limit_price, reduce_only=reduce_only)

    def cancel_order(self, account_id, order_id):
        with self._gate():
            return self._services[self.shard_for(account_id)].cancel_order(account_id, order_id)

    def borrow(self, account_id, command_id, asset, amount):
        with self._gate(exposure=True):
            return CreditService(self._services[self.shard_for(account_id)]).borrow(account_id, command_id, asset, amount)

    def repay(self, account_id, command_id, asset, amount):
        with self._gate():
            return CreditService(self._services[self.shard_for(account_id)]).repay(account_id, command_id, asset, amount)

    def accrue_interest(self, account_id, command_id, asset, amount):
        with self._gate():
            return CreditService(self._services[self.shard_for(account_id)]).accrue_interest(account_id, command_id, asset, amount)

    def configure_credit_limit(self, account_id, asset, limit):
        with self._gate():
            return CreditService(self._services[self.shard_for(account_id)]).configure_limit(account_id, asset, limit)

    def configure_credit_asset_limit(self, shard, asset, limit):
        with self._gate():
            return CreditService(self._services[self._index(shard)]).configure_asset_limit(asset, limit)

    def fund_credit_pool(self, shard, command_id, asset, amount, *, source_reference):
        shard = self._index(shard)
        _name(source_reference, "source_reference")
        _name(command_id, "command_id")
        credit = CreditService(self._services[shard])
        credit._asset(asset)
        units = credit._units(asset, amount)
        command = _json([shard, command_id, asset, _text(credit._value(asset, units))])
        # Reserve the external funding proof durably before changing a shard.
        # A crash leaves it assigned to this exact shard/command; retry only that
        # command. It is never released/reallocated after an ambiguous outcome.
        with self._lock(exclusive=True):
            self._state()
            with self.control.transaction() as connection:
                existing = connection.execute("SELECT command FROM router_pool_sources WHERE source_reference=?", (source_reference,)).fetchone()
                if existing is not None and existing[0] != command:
                    raise ServiceError("funding_source_conflict", "source reference is permanently assigned to a different shard command", 409)
                connection.execute("INSERT OR IGNORE INTO router_pool_sources VALUES (?,?)", (source_reference, command))
            return credit.fund_pool(command_id, asset, amount, source_reference=source_reference)

    def match_once(self, shard, symbol, max_matches=100):
        with self._gate(exposure=True):
            return Matcher(self._services[self._index(shard)]).match_once(symbol, max_matches)

    def transfer(self, source_account, target_account, *args, **kwargs):
        self.require_same_shard(source_account, target_account)
        raise ServiceError("transfer_unsupported", "router transfers are not implemented", 409)

    def events(self, cursor, *, limit=100):
        if not isinstance(cursor, dict) or set(cursor) != {"shard", "sequence"}:
            raise ServiceError("invalid_cursor", "event cursor requires shard and sequence")
        shard = self._index(cursor["shard"])
        with self._gate():
            rows = self._services[shard].events(after=cursor["sequence"], limit=limit)
            return {"events": [{**row, "cursor": {"shard": shard, "sequence": row["sequence"]}} for row in rows],
                    "next_cursor": {"shard": shard, "sequence": rows[-1]["sequence"] if rows else cursor["sequence"]}}

    def publish_market(self, snapshot):
        if not isinstance(snapshot, MarketSnapshot):
            raise ServiceError("invalid_market", "publish a validated MarketSnapshot")
        payload = snapshot.to_json()
        digest = sha256(payload.encode()).hexdigest()
        with self._lock(exclusive=True):
            state = self._state()
            previous = state["market_version"]
            if previous is not None and (snapshot.version < previous or
                snapshot.version == previous and digest != state["market_digest"]):
                raise ServiceError("market_conflict", "global market version regressed or changed content", 409)
            state.update(halted=True, publishing=True, epoch=state["epoch"] + 1,
                         target_version=snapshot.version, target_digest=digest, watermarks={}, error=None)
            self._write_state(state)
            try:
                for index, service in enumerate(self._services):
                    service.set_kill_switch(True)
                for index, service in enumerate(self._services):
                    service.publish_market(snapshot)
                    state["watermarks"][str(index)] = snapshot.version
                    self._write_state(state)
                state.update(publishing=False, market_version=snapshot.version, market_digest=digest)
                self._write_state(state)
            except BaseException:
                state.update(halted=True, publishing=True, error="market_fanout_incomplete")
                self._write_state(state)
                raise
            return dict(state)

    def set_kill_switch(self, enabled):
        if type(enabled) is not bool:
            raise ServiceError("invalid_input", "enabled must be boolean")
        with self._lock(exclusive=True):
            state = self._state()
            if not enabled:
                if state["publishing"] or state["market_version"] is None:
                    raise ServiceError("publication_incomplete", "complete market fanout before activation", 503)
                for service in self._services:
                    with service._transaction() as connection:
                        market = service._market(connection)
                        if market.version != state["market_version"] or sha256(market.to_json().encode()).hexdigest() != state["market_digest"]:
                            raise ServiceError("market_barrier_mismatch", "shard market does not match global barrier", 503)
            # Persist halted first. Only after all shards successfully activate
            # is the global gate opened in its final durable commit.
            state.update(halted=True, error=None)
            self._write_state(state)
            try:
                for service in self._services:
                    service.set_kill_switch(enabled)
                state["halted"] = enabled
                self._write_state(state)
            except BaseException:
                state.update(halted=True, error="halt_fanout_incomplete")
                self._write_state(state)
                raise
            return dict(state)

    def diagnostics(self):
        with self._lock():
            state = self._state()
            shards = []
            for index, service in enumerate(self._services):
                try:
                    readiness = service.readiness()
                    with service._transaction() as connection:
                        sequence = connection.execute("SELECT COALESCE(MAX(sequence),0) FROM uta_events").fetchone()[0]
                    shards.append({"shard": index, "event_sequence": sequence, **readiness})
                except Exception:
                    shards.append({"shard": index, "ready": False, "reason": "shard_unavailable"})
            return {"experimental": True, "state": state, "shards": shards,
                    "ready": not state["halted"] and not state["publishing"] and all(
                        row["ready"] and row.get("market_version") == state["market_version"] for row in shards)}
