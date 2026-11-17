"""Bounded, restartable scheduling of local risk plans and real order matching.

No synthetic fill or external side effect is generated. Every risk mutation and
paired settlement is committed by its authority, so competing workers can retry
without inventing a second plan or trade. This is not a replicated scheduler.
"""
from __future__ import annotations

from collections import OrderedDict
from hashlib import sha256
import json
from threading import Event, RLock, Thread
from time import monotonic_ns

from .decision_audit import DecisionAudit
from .matching import Matcher
from .models import RiskInputError
from .products import ProductKind
from .service import ExchangeService, ServiceError


class ExchangeWorker:
    def __init__(self, exchange: ExchangeService, *, account_batch: int = 100,
                 matches_per_symbol: int = 25, interval: float = .25,
                 normal_cache_size: int = 0):
        if type(account_batch) is not int or not 1 <= account_batch <= 1000:
            raise ValueError("account_batch must be an integer in 1..1000")
        if type(matches_per_symbol) is not int or not 1 <= matches_per_symbol <= 1000:
            raise ValueError("matches_per_symbol must be an integer in 1..1000")
        if isinstance(interval, bool) or not isinstance(interval, (float, int)) or not .01 <= interval <= 60:
            raise ValueError("interval must be finite and in .01..60 seconds")
        if type(normal_cache_size) is not int or not 0 <= normal_cache_size <= 65536:
            raise ValueError("normal_cache_size must be an integer in 0..65536")
        self.exchange = exchange
        self.matcher = getattr(exchange, "matcher", None) or Matcher(exchange)
        self.spot = getattr(exchange, "spot", None)
        self.account_batch, self.matches_per_symbol, self.interval = account_batch, matches_per_symbol, interval
        self._stop = Event()
        self._thread = None
        self._normal_capacity = normal_cache_size
        self._normal_cache = OrderedDict()
        self._normal_lock = RLock()
        self._normal_counts = dict(hits=0, misses=0, evictions=0, ineligible=0)
        self.last_report: dict = {"state": "not_started"}
        with exchange._transaction() as conn:
            conn.execute(self._schedule_schema())
            conn.execute("INSERT OR IGNORE INTO uta_supervisor_schedule VALUES (1,'')")

    @staticmethod
    def _schedule_schema() -> str:
        return """CREATE TABLE IF NOT EXISTS uta_supervisor_schedule (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1), last_account TEXT NOT NULL)"""

    def normal_cache_stats(self) -> dict:
        """Diagnostics only; no balance, financial acceptance or readiness proof."""
        with self._normal_lock:
            return dict(capacity=self._normal_capacity, size=len(self._normal_cache), **self._normal_counts)

    def clear_normal_cache(self, *, reset_stats: bool = False) -> None:
        with self._normal_lock:
            self._normal_cache.clear()
            if reset_stats:
                self._normal_counts = dict(hits=0, misses=0, evictions=0, ineligible=0)

    @staticmethod
    def _digest(value) -> str:
        return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                 ensure_ascii=True, allow_nan=False).encode()).hexdigest()

    @staticmethod
    def _rows(connection, sql, parameters=()):
        return [dict(row) for row in connection.execute(sql, parameters)]

    def _common_dependencies(self, connection) -> tuple[str, bool]:
        # Full bytes/rows, never versions alone. A journal append invalidates all
        # accounts, including legitimate Ledger.post calls without an account bump.
        tables = ("uta_schema", "uta_config", "uta_market", "ledger_schema", "ledger_assets",
                  "ledger_balances", "ledger_events", "uta_accounts", "uta_positions",
                  "uta_liabilities", "uta_orders", "uta_liquidation_accounts", "uta_spot_orders",
                  "uta_spot_schema", "uta_spot_config")
        schema = self._rows(connection,
            "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE tbl_name IN (" +
            ",".join("?" for _ in tables) + ") OR tbl_name GLOB 'uta_spot_*' ORDER BY type,name,tbl_name,sql", tables)
        spot_exists = any(row["type"] == "table" and row["name"] == "uta_spot_orders" for row in schema)
        values = dict(schema=schema,
            market=self._rows(connection, "SELECT * FROM uta_market ORDER BY singleton"),
            config=self._rows(connection, "SELECT * FROM uta_config ORDER BY key"),
            version=self._rows(connection, "SELECT * FROM uta_schema"),
            ledger_version=self._rows(connection, "SELECT * FROM ledger_schema ORDER BY singleton"),
            assets=self._rows(connection, "SELECT * FROM ledger_assets ORDER BY asset"),
            ledger_head=self._rows(connection, "SELECT * FROM ledger_events ORDER BY sequence DESC LIMIT 1"),
            spot_version=self._rows(connection, "SELECT * FROM uta_spot_schema ORDER BY singleton") if spot_exists else [],
            spot_configuration=self._rows(connection, "SELECT * FROM uta_spot_config ORDER BY singleton") if spot_exists else [],
            runtime=DecisionAudit.policy(self.exchange))
        return self._digest(values), spot_exists

    def _dependencies(self, connection, account_id, common=None):
        common_digest, spot_exists = common or self._common_dependencies(connection)
        economic = dict(common=common_digest,
            account=self._rows(connection, "SELECT * FROM uta_accounts WHERE account_id=?", (account_id,)),
            balances=self._rows(connection, "SELECT * FROM ledger_balances WHERE account=? ORDER BY asset",
                                (self.exchange._customer(account_id),)),
            positions=self._rows(connection, "SELECT * FROM uta_positions WHERE account_id=? ORDER BY symbol", (account_id,)),
            liabilities=self._rows(connection, "SELECT * FROM uta_liabilities WHERE account_id=? ORDER BY asset", (account_id,)),
            orders=self._rows(connection, "SELECT * FROM uta_orders WHERE account_id=? AND status IN ('OPEN','PARTIALLY_FILLED') ORDER BY order_id", (account_id,)),
            spot_orders=self._rows(connection, "SELECT * FROM uta_spot_orders WHERE account_id=? AND status IN ('OPEN','PARTIALLY_FILLED') ORDER BY order_id", (account_id,)) if spot_exists else [])
        risk = self._rows(connection, "SELECT * FROM uta_liquidation_accounts WHERE account_id=?", (account_id,))
        economic_digest = self._digest(economic)
        return self._digest([economic_digest, risk]), economic_digest, risk[0]["state"] if risk else None

    def _normal_match(self, account_id, proof, state):
        with self._normal_lock:
            matched = state == "NORMAL" and self._normal_cache.get(account_id) == proof
            if matched:
                self._normal_cache.move_to_end(account_id)
            else:
                self._normal_counts["misses"] += 1
                self._normal_cache.pop(account_id, None)
            return matched

    def _supervise_and_prove(self, account_id):
        # The NORMAL result and BOTH input observations belong to the actual
        # financial transaction. Post-COMMIT reads would allow concurrent-write
        # and ABA counterexamples. Never publish a proof before COMMIT returns.
        with self.exchange._transaction() as connection:
            _, before_economic, before_state = self._dependencies(connection, account_id)
            result = self.exchange.supervise_account(account_id, connection=connection)
            proof, after_economic, after_state = self._dependencies(connection, account_id)
            eligible = (result["state"] == after_state == "NORMAL"
                        and before_state in (None, "NORMAL") and before_economic == after_economic)
        with self._normal_lock:
            if eligible:
                self._normal_cache[account_id] = proof
                self._normal_cache.move_to_end(account_id)
                if len(self._normal_cache) > self._normal_capacity:
                    self._normal_cache.popitem(last=False)
                    self._normal_counts["evictions"] += 1
            else:
                self._normal_cache.pop(account_id, None)
                self._normal_counts["ineligible"] += 1
        return result

    def run_once(self) -> dict:
        report = {"state": "running", "accounts": 0, "plans": [], "linear_trades": 0,
                  "spot_trades": 0, "blocked": []}
        # A cursor is scheduling fairness, never the authoritative risk state.
        # A crash before its update safely revisits idempotent account commands.
        cached = set()
        snapshot_started = monotonic_ns()
        context = (self.exchange.database.read_transaction() if self._normal_capacity
                   else self.exchange._transaction())
        with context as conn:
            try:
                market = self.exchange._market(conn)
            except ServiceError as exc:
                report.update(state="blocked", blocked=[{"code": exc.code}])
                self.last_report = report
                return report
            cursor = conn.execute("SELECT last_account FROM uta_supervisor_schedule WHERE singleton=1").fetchone()[0]
            accounts = conn.execute("SELECT account_id FROM uta_accounts WHERE account_id>? ORDER BY account_id LIMIT ?",
                                    (cursor, self.account_batch)).fetchall()
            if not accounts:
                accounts = conn.execute("SELECT account_id FROM uta_accounts ORDER BY account_id LIMIT ?",
                                        (self.account_batch,)).fetchall()
            if self._normal_capacity:
                common = self._common_dependencies(conn)
                for row in accounts:
                    proof, _, state = self._dependencies(conn, row["account_id"], common)
                    if self._normal_match(row["account_id"], proof, state):
                        cached.add(row["account_id"])
                count = conn.execute("SELECT COUNT(*) FROM uta_accounts").fetchone()[0]
                report["normal_cache"] = dict(snapshot_started_ns=snapshot_started,
                    snapshot_completed_ns=monotonic_ns(), accounts_total=count,
                    market_version=market.version,
                    # For a fixed account set, conservative bound from ANY cursor.
                    revisit_round_bound=(count + self.account_batch - 1) // self.account_batch + 1,
                    skipped=0, supervised=0)
        last = None
        for row in accounts:
            if self._stop.is_set():
                break
            account_id = row["account_id"]
            try:
                hit = account_id in cached
                if hit:
                    # The financial input comparison linearized in the RO
                    # snapshot above. Clock freshness must still hold NOW after
                    # any earlier slow account; otherwise run the original gate.
                    try:
                        market.validate(now=self.exchange._now(), max_age=self.exchange.max_price_age)
                    except RiskInputError:
                        hit = False
                if hit:
                    plan = {"state": "NORMAL"}
                    with self._normal_lock:
                        self._normal_counts["hits"] += 1
                    report["normal_cache"]["skipped"] += 1
                elif self._normal_capacity:
                    report["normal_cache"]["supervised"] += 1
                    plan = self._supervise_and_prove(account_id)
                else:
                    plan = self.exchange.supervise_account(account_id)
                report["plans"].append({"account_id": account_id, "state": plan["state"]})
            except ServiceError as exc:
                report["blocked"].append({"account_id": account_id, "code": exc.code})
            last = account_id
            report["accounts"] += 1
        if last is not None:
            with self.exchange._transaction() as conn:
                conn.execute("UPDATE uta_supervisor_schedule SET last_account=? WHERE singleton=1", (last,))
        # Each matcher revalidates the CURRENT market inside its own transaction;
        # the earlier snapshot is used only to enumerate this bounded work set.
        for symbol in market.instruments:
            if self._stop.is_set():
                break
            try:
                outcome = self.matcher.match_once(symbol, self.matches_per_symbol)
                report["linear_trades"] += outcome["confirmed_trades"]
                report["blocked"].extend({"symbol": symbol, "code": item["code"]} for item in outcome["blocked"])
            except ServiceError as exc:
                report["blocked"].append({"symbol": symbol, "code": exc.code})
        if self.spot is not None:
            for symbol, product in self.spot.catalog.products.items():
                if self._stop.is_set():
                    break
                if product.kind not in (ProductKind.SPOT, ProductKind.SPOT_MARGIN):
                    continue
                try:
                    outcome = self.spot.match_once(symbol, self.matches_per_symbol)
                    report["spot_trades"] += outcome["confirmed_trades"]
                    report["blocked"].extend({"symbol": symbol, "code": item["code"]} for item in outcome["blocked"])
                except ServiceError as exc:
                    report["blocked"].append({"symbol": symbol, "code": exc.code})
        self.last_report = report
        if self._normal_capacity:
            report["normal_cache"]["completed_ns"] = monotonic_ns()
        return report

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("worker may only be started once")
        self._thread = Thread(target=self._run, name="uta-risk-matching", daemon=False)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.run_once()
            except Exception:
                # Do not leak balances, credentials or raw requests into logs.
                # Mutations themselves fail/rollback at their authority boundary.
                # Unexpected loss of automation requires an explicit operator
                # recovery; do not keep authorizing new exposure indefinitely.
                halted = False
                try:
                    self.exchange.set_kill_switch(True)
                    halted = True
                except Exception:
                    # Unavailable storage cannot acknowledge a halt. Readiness
                    # still fails and the original commands cannot falsely commit.
                    pass
                self.last_report = {"state": "blocked", "reason": "worker_failure",
                                    "emergency_halt_committed": halted}
            self._stop.wait(self.interval)

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join()
