"""Bounded, restartable scheduling of local risk plans and real order matching.

No synthetic fill or external side effect is generated. Every risk mutation and
paired settlement is committed by its authority, so competing workers can retry
without inventing a second plan or trade. This is not a replicated scheduler.
"""
from __future__ import annotations

from threading import Event, Thread

from .matching import Matcher
from .products import ProductKind
from .service import ExchangeService, ServiceError


class ExchangeWorker:
    def __init__(self, exchange: ExchangeService, *, account_batch: int = 100,
                 matches_per_symbol: int = 25, interval: float = .25):
        if type(account_batch) is not int or not 1 <= account_batch <= 1000:
            raise ValueError("account_batch must be an integer in 1..1000")
        if type(matches_per_symbol) is not int or not 1 <= matches_per_symbol <= 1000:
            raise ValueError("matches_per_symbol must be an integer in 1..1000")
        if isinstance(interval, bool) or not isinstance(interval, (float, int)) or not .01 <= interval <= 60:
            raise ValueError("interval must be finite and in .01..60 seconds")
        self.exchange = exchange
        self.matcher = getattr(exchange, "matcher", None) or Matcher(exchange)
        self.spot = getattr(exchange, "spot", None)
        self.account_batch, self.matches_per_symbol, self.interval = account_batch, matches_per_symbol, interval
        self._stop = Event()
        self._thread = None
        self.last_report: dict = {"state": "not_started"}
        with exchange._transaction() as conn:
            conn.execute(self._schedule_schema())
            conn.execute("INSERT OR IGNORE INTO uta_supervisor_schedule VALUES (1,'')")

    @staticmethod
    def _schedule_schema() -> str:
        return """CREATE TABLE IF NOT EXISTS uta_supervisor_schedule (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1), last_account TEXT NOT NULL)"""

    def run_once(self) -> dict:
        report = {"state": "running", "accounts": 0, "plans": [], "linear_trades": 0,
                  "spot_trades": 0, "blocked": []}
        # A cursor is scheduling fairness, never the authoritative risk state.
        # A crash before its update safely revisits idempotent account commands.
        with self.exchange._transaction() as conn:
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
        last = None
        for row in accounts:
            if self._stop.is_set():
                break
            account_id = row["account_id"]
            try:
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
