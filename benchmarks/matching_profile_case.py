"""CODE-only synchronous matching profile; execute only under its once-driver.

Synthetic USD perpetuals, two fresh authorities per size, audited WAL/FULL.
No worker, account-mode change, custom clock, native method patch or network.
"""
from collections import Counter
import cProfile
import dis
from datetime import datetime, timezone
from decimal import Decimal
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import pstats
import random
import resource
import sqlite3
import sys
import traceback
from time import perf_counter_ns, process_time_ns

from uta.market import MarketSnapshot
from uta.matching import Matcher
from uta.models import AssetSpec, InstrumentSpec
from uta.reconciliation import reconcile_exchange
from uta.service import ExchangeService
from uta.storage import Database


SIZES = (32, 128)
SCHEDULE = ((32, "scan"), (32, "snapshot"), (128, "snapshot"), (128, "scan"))
BATCH_MATCHES = 8
SEED = 17023
DEPOSIT = Fraction(1000000)
FEE_RATE = Fraction(4, 10000)
TABLES = {
    "ledger_events": "sequence", "ledger_postings": "sequence,ordinal",
    "ledger_balances": "account,asset", "uta_accounts": "account_id",
    "uta_orders": "rowid", "uta_positions": "account_id,symbol",
    "uta_fills": "account_id,fill_id", "uta_matches": "sequence",
    "uta_liabilities": "account_id,asset", "uta_deposits": "account_id,event_id",
    "uta_config": "key", "uta_liquidation_accounts": "account_id",
}


def require(value, message):
    if not value:
        raise AssertionError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()



# Exhaustive native legacy-reference schema, service.py _risk. Configured PM
# schemas are outside this profile and must fail rather than lose new fields.
RISK_FINANCIAL_KEYS = ("account_version", "equity", "initial_margin", "maintenance_margin",
    "open_order_margin", "available_margin", "margin_ratio", "market_version", "risk_mode")


def risk_contract(risks, quote):
    require(type(risks) is dict and set(risks) == {"buyer", "seller"}, "risk accounts changed")
    financial = {}
    for account, risk in risks.items():
        require(type(risk) is dict and set(risk) == set(RISK_FINANCIAL_KEYS) | {"observed_at"},
                "unknown/missing native legacy risk field")
        require(type(risk["account_version"]) is int and risk["account_version"] >= 0
                and type(risk["market_version"]) is int and risk["market_version"] == quote["version"]
                and risk["risk_mode"] == "legacy_reference"
                and type(risk["observed_at"]) is str and risk["observed_at"] == quote["observed_at"],
                "risk version/mode/quote-asof differs")
        for key in ("equity", "initial_margin", "maintenance_margin", "open_order_margin", "available_margin", "margin_ratio"):
            value = risk[key]
            require((key == "margin_ratio" and value is None)
                    or (type(value) is str and Decimal(value).is_finite()), "untyped/nonfinite risk value")
        financial[account] = {key: risk[key] for key in RISK_FINANCIAL_KEYS}
    return financial


def microseconds(delta):
    return (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds


def whole(value):
    require(value.denominator == 1, "expected integral synthetic quantity/price")
    return str(value.numerator)


def workload(size):
    require(size in SIZES and size % 2 == 0, "unsupported fixed book size")
    pairs = list(range(size // 2))
    random.Random(SEED + size).shuffle(pairs)
    rows = []
    for index in pairs:
        quantity = (1, 2, 5)[index % 3]
        for side, account, price in ((1, "buyer", 100 + index % 3),
                                     (-1, "seller", 100 - index % 3)):
            rows.append({"book_sequence": len(rows) + 1, "account_id": account,
                         "order_id": ("b-" if side > 0 else "s-") + str(index).zfill(3),
                         "quantity": str(side * quantity), "limit_price": str(price),
                         "filled_quantity": "0"})
    return rows


def reference_matches(original):
    """Independent complete re-sort for every expected trade, no production helper."""
    rows = [dict(value) for value in original]
    trades = []
    for unused in range(BATCH_MATCHES):
        buys = sorted((row for row in rows if Fraction(row["quantity"]) - Fraction(row["filled_quantity"]) > 0),
                      key=lambda row: (-Fraction(row["limit_price"]), row["book_sequence"]))
        sells = sorted((row for row in rows if Fraction(row["quantity"]) - Fraction(row["filled_quantity"]) < 0),
                       key=lambda row: (Fraction(row["limit_price"]), row["book_sequence"]))
        require(buys and sells, "reference has insufficient paired liquidity")
        buy, sell = buys[0], sells[0]
        require(Fraction(buy["limit_price"]) >= Fraction(sell["limit_price"]), "reference book does not cross")
        quantity = min(Fraction(buy["quantity"]) - Fraction(buy["filled_quantity"]),
                       Fraction(sell["filled_quantity"]) - Fraction(sell["quantity"]))
        maker = buy if buy["book_sequence"] < sell["book_sequence"] else sell
        price = Fraction(maker["limit_price"])
        inputs = ["BTC-PERP", buy["account_id"], buy["order_id"], sell["account_id"], sell["order_id"],
                  buy["filled_quantity"], sell["filled_quantity"], whole(quantity), whole(price)]
        identity = sha256(json.dumps(inputs, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
        trades.append({"trade_id": "match:" + identity, "buy_order_id": buy["order_id"],
                       "sell_order_id": sell["order_id"], "quantity": whole(quantity), "price": whole(price)})
        buy["filled_quantity"] = whole(Fraction(buy["filled_quantity"]) + quantity)
        sell["filled_quantity"] = whole(Fraction(sell["filled_quantity"]) - quantity)
    quantity = sum((Fraction(value["quantity"]) for value in trades), Fraction())
    notional = sum((Fraction(value["quantity"]) * Fraction(value["price"]) for value in trades), Fraction())
    fixed = {32: (Fraction(31), Fraction(3156), Fraction("1.2624")),
             128: (Fraction(40), Fraction(4080), Fraction("1.632"))}[len(original)]
    require((quantity, notional, notional * FEE_RATE) == fixed, "independent reference disagrees with hand case")
    return {"trades": trades, "quantity": quantity, "notional": notional, "fee_per_account": notional * FEE_RATE}


class SqlObserver:
    """Run-owned diagnostic: audit captures, local LINE attaches after connect.

    Only original Database._connect is supported. No native method is replaced.
    Unknown/unattached handles are fatal; observers never own/close connections.
    """
    TOOL_ID = 3
    TOOL_NAME = "uta-matching-sql-observer"
    INSTANCE_SEQUENCE = 0
    MAX_PENDING = 16

    def __init__(self):
        type(self).INSTANCE_SEQUENCE += 1
        self.tool_name = self.TOOL_NAME + ":" + str(type(self).INSTANCE_SEQUENCE)
        self.phase = "setup"
        self.events, self.connections, self.handles, self.attempts, self.lines = (Counter() for unused in range(5))
        self.total_events, self.total_lines = 0, 0
        self.failure, self.monitoring, self.line_event = None, None, None
        self.pending, self.unretained_pending = [], 0
        self.active, self.started, self.closed = False, False, False
        self.tool_owned, self.ever_owned, self.slot_released = False, False, False
        self.connect_code = Database._connect.__code__
        self.first_sql_line = None
        self.line_callback = self._line
        self.cleanup_error = None

    def install(self):
        try:
            require(not self.started and not self.closed, "observer cannot be installed twice")
            self.started = True
            sql_lines = [item.positions.lineno for item in dis.get_instructions(self.connect_code)
                         if item.opname in {"LOAD_METHOD", "LOAD_ATTR"} and item.argval == "execute"
                         and type(item.positions.lineno) is int]
            require(sql_lines, "supported connect code must expose its explicit SQL boundary")
            self.first_sql_line = min(sql_lines)
            self.monitoring = getattr(sys, "monitoring", None)
            require(self.monitoring is not None and all(callable(getattr(self.monitoring, name, None)) for name in
                    ("get_tool", "use_tool_id", "register_callback", "set_local_events", "free_tool_id"))
                    and callable(getattr(sys, "_getframe", None)), "Python3.12 monitoring/frame APIs are required")
            self.line_event = getattr(getattr(self.monitoring, "events", None), "LINE", None)
            require(type(self.line_event) is int and self.line_event > 0, "supported local LINE event is required")
            if self.monitoring.get_tool(self.TOOL_ID) is not None:
                self._first_fault("sqlite_monitor_slot_occupied", "sys.monitoring.use_tool_id")
                raise RuntimeError("observer tool3 is occupied; no foreign tool is changed")
            self.monitoring.use_tool_id(self.TOOL_ID, self.tool_name)
            self.tool_owned = self.ever_owned = True
            self.monitoring.register_callback(self.TOOL_ID, self.line_event, self.line_callback)
            self.monitoring.set_local_events(self.TOOL_ID, self.connect_code, self.line_event)
            sys.addaudithook(self._audit)
            self.active = True
        except BaseException as error:
            self._first_fault("sqlite_monitor_install_failed", "sys.monitoring.install", error)
            self.close()
            self.raise_fault()

    def _audit(self, event, arguments):
        if not self.active or event != "sqlite3.connect/handle":
            return
        try:
            require(type(arguments) is tuple and len(arguments) == 1, "unexpected connection audit shape")
            connection = arguments[0]
            self.handles[self.phase] += 1
            caller = sys._getframe(1)
            if len(self.pending) >= self.MAX_PENDING:
                self.unretained_pending += 1
                self._first_fault("sqlite_pending_capacity_exceeded", event)
                return
            if any(item[0] is connection for item in self.pending):
                self.unretained_pending += 1
                self._first_fault("sqlite_duplicate_pending_handle", event)
                return
            self.pending.append((connection, caller, self.phase))
            if caller.f_code is not self.connect_code or type(connection) is not sqlite3.Connection:
                self._first_fault("sqlite_unknown_connect_callsite", event)
            # This is deliberately capture-only. Connection.__init__ may still
            # be running here; no SQLite method or SQL is invoked by this hook.
        except BaseException as error:
            self._first_fault("sqlite_handle_capture_failed", event, error)

    def _line(self, code, line):
        if not self.active:
            return
        try:
            self.lines[self.phase] += 1
            self.total_lines += 1
            require(code is self.connect_code, "unexpected local monitoring code object")
            if self.total_lines > 1000000:
                self._first_fault("sqlite_monitor_event_budget_exceeded", "sys.monitoring.LINE")
            if self.failure is not None or not self.pending:
                return
            caller = sys._getframe(1)
            require(caller.f_code is code, "local LINE caller code differs")
            require(type(line) is int and line <= self.first_sql_line,
                    "pending connection reached a line after first explicit SQL; reject late attach")
            require(all(item[1] is caller and item[2] == self.phase for item in self.pending),
                    "pending handle belongs to another frame or phase")
            pending, self.pending = self.pending, []
            # A native C connect call cannot deliver a local Python LINE until
            # it has returned. This runs before storage's first explicit PRAGMA.
            for connection, owner, phase in pending:
                self.attempts[phase] += 1
                connection.set_trace_callback(self._trace)
                self.connections[phase] += 1
        except BaseException as error:
            # No retry/replacement: attempts/count mismatch stays fatal.
            self._first_fault("sqlite_trace_install_failed", "post_connect_local_LINE", error)

    def _trace(self, statement):
        if not self.active:
            return
        try:
            beginning = statement[:256].lstrip()
            prefix = beginning.split(None, 1)[0].upper() if beginning else "EMPTY"
            category = prefix if prefix in {"SELECT", "INSERT", "UPDATE", "DELETE", "BEGIN", "COMMIT",
                "ROLLBACK", "SAVEPOINT", "RELEASE", "PRAGMA", "CREATE", "DROP", "ALTER"} else "OTHER"
            self.events[(self.phase, category)] += 1
            self.total_events += 1
            if self.total_events > 1000000:
                self._first_fault("sqlite_trace_event_budget_exceeded", "sqlite_trace_counter_limit")
        except BaseException as error:
            self._first_fault("sqlite_trace_callback_failed", "sqlite_trace_callback", error)

    @staticmethod
    def _bounded(value, limit):
        data = value.encode("utf-8", "backslashreplace")
        return {"text": data[:limit].decode("utf-8", "ignore"), "truncated": len(data) > limit,
                "limit_bytes": limit}

    def _first_fault(self, category, event, error=None):
        if self.failure is not None:
            return
        fault = {"category": category, "phase": self.phase, "event": event,
            "total_trace_events": self.total_events, "connections_in_phase": self.connections[self.phase],
            "handles_in_phase": self.handles[self.phase], "pending_references": len(self.pending),
            "unretained_pending": self.unretained_pending,
            "trace_events_in_phase": {name: count for (phase, name), count in self.events.items() if phase == self.phase},
            "exception": None, "expanded_SQL_statement_copied": False, "first_fault_never_overwritten": True}
        # Latch before formatting so even diagnostics failures cannot erase the
        # incomplete state. All details stay private until an explicit filter.
        self.failure = fault
        if error is not None:
            try:
                fault["exception"] = {"type": self._bounded(type(error).__module__ + "." + type(error).__qualname__, 128),
                                      "message": None, "stack_limit_frames": 6, "stack": []}
                fault["exception"]["message"] = self._bounded(str(error), 512)
                fault["exception"]["stack"] = [{"file": self._bounded(frame.filename, 256),
                    "function": self._bounded(frame.name, 128), "line": frame.lineno}
                    for frame in traceback.extract_tb(error.__traceback__, limit=6)]
            except BaseException as detail_error:
                fault["detail_capture_failed"] = self._bounded(type(detail_error).__name__, 128)

    def raise_fault(self):
        if self.failure is not None:
            raise AssertionError("SQLite trace observation became incomplete; first_fault="
                                 + canonical(self.failure).decode("ascii"))

    def snapshot(self):
        try:
            require(self.active and self.tool_owned and self.monitoring.get_tool(self.TOOL_ID) == self.tool_name,
                    "observer is inactive or monitor tool identity changed")
        except BaseException as error:
            self._first_fault("sqlite_observer_inactive_or_tool_lost", "observer.snapshot", error)
        if self.pending or self.unretained_pending:
            self._first_fault("sqlite_unattached_pending_handle", "observer.snapshot")
        if self.handles != self.connections or self.attempts != self.connections or not self.handles:
            self._first_fault("sqlite_handle_attachment_count_mismatch", "observer.snapshot")
        if self.events[(self.phase, "PRAGMA")] < self.connections[self.phase]:
            self._first_fault("sqlite_connection_setup_trace_incomplete", "observer.snapshot")
        self.raise_fault()
        return {"phase": self.phase, "events": {category: count for (phase, category), count in self.events.items()
                if phase == self.phase}, "connections": self.connections[self.phase],
                "handles_observed": self.handles[self.phase], "attach_attempts": self.attempts[self.phase],
                "pending_handles": 0, "local_LINE_events": self.lines[self.phase],
                "monitor_tool_id": self.TOOL_ID, "monitor_instance_label": self.tool_name,
                "monitor_code_object": "uta.storage.Database._connect",
                "first_explicit_SQL_line_guard": self.first_sql_line,
                "counts_are_trace_events_including_trigger_repeats": True,
                "attach_after_connect_before_first_explicit_SQL": True,
                "uses_local_monitoring_not_legacy_settrace": True,
                "cProfile_coexistence_requires_native_phase_validation": True}

    def close(self):
        self.active = False  # Unremovable old audit hooks become inert first.
        pending_count = len(self.pending) + self.unretained_pending
        if pending_count or self.handles != self.connections or self.attempts != self.connections:
            self._first_fault("sqlite_incomplete_on_close", "observer.close")
        self.pending.clear()  # Drop connection/frame strong references, never close a native connection.
        self.unretained_pending = 0
        if self.tool_owned:
            try:
                require(self.monitoring.get_tool(self.TOOL_ID) == self.tool_name,
                        "owned monitor slot identity changed; do not touch a foreign tool")
                self.monitoring.set_local_events(self.TOOL_ID, self.connect_code, 0)
                self.monitoring.register_callback(self.TOOL_ID, self.line_event, None)
                self.monitoring.free_tool_id(self.TOOL_ID)
                self.tool_owned, self.slot_released = False, True
                require(self.monitoring.get_tool(self.TOOL_ID) is None, "tool slot was not empty after own release")
            except BaseException as error:
                self.cleanup_error = {"type": self._bounded(type(error).__name__, 128),
                                      "message": self._bounded(str(error), 512)}
                self._first_fault("sqlite_monitor_cleanup_failed", "observer.close", error)
        self.closed = True
        return {"active": self.active, "closed": self.closed, "pending_references": len(self.pending),
                "unattached_at_close": pending_count, "monitor_instance_label": self.tool_name,
                "ever_owned_tool": self.ever_owned,
                "owned_tool_released": self.slot_released, "tool_owned_after_close": self.tool_owned,
                "all_handles_attached": self.handles == self.connections and self.attempts == self.connections,
                "handles_by_phase": dict(self.handles), "attachments_by_phase": dict(self.connections),
                "attempts_by_phase": dict(self.attempts), "local_LINE_events_by_phase": dict(self.lines),
                "first_fault": self.failure, "cleanup_error": self.cleanup_error}


def profile_rows(profiler):
    stats = pstats.Stats(profiler)
    rows, groups = [], Counter()
    for (filename, line, function), values in stats.stats.items():
        primitive, calls, internal, cumulative, unused_callers = values
        require(internal >= 0 and cumulative >= 0, "negative profiler time")
        if "sqlite3.Connection" in function:
            group = "sqlite_native_including_execution_and_commit"
        elif filename.endswith("fractions.py"):
            group = "exact_fraction_arithmetic"
        elif filename.endswith(("risk.py", "portfolio.py", "reserve_kernel.py")):
            group = "risk_and_reserve"
        elif "/json/" in filename or "_json" in function:
            group = "json_serialization"
        elif filename.endswith("decision_audit.py"):
            group = "audit_python"
        elif filename.endswith("matching_profile_case.py"):
            group = "profile_sql_counter_instrumentation"
        elif (filename.endswith("matching.py") and function in {"best", "__init__", "_remaining", "<lambda>"}
              or "'sort' of 'list'" in function or "builtins.sorted" in function):
            group = "book_selection_and_ordering"
        elif filename.endswith("matching.py"):
            group = "matching_orchestration_python"
        else:
            group = "other"
        groups[group] += internal
        rows.append({"file": filename, "line": line, "function": function, "primitive_calls": primitive,
                     "total_calls": calls, "self_seconds": internal, "cumulative_seconds": cumulative,
                     "exclusive_self_group": group})
    require(len(rows) <= 4096, "profile function inventory exceeds declared report bound")
    return {"all_functions": sorted(rows, key=lambda row: (-row["cumulative_seconds"], row["file"], row["line"], row["function"])),
            "nonoverlapping_self_seconds_by_group": dict(groups), "profiler_total_self_seconds": stats.total_tt,
            "cumulative_function_times_overlap_do_not_sum": True,
            "observer_wall_cost_includes_audit_SQLtrace_and_local_LINE": True,
            "monitor_callback_time_separately_proven_by_cProfile": False,
            "monitor_callback_time_note": "Runtime profiling can suppress events inside monitoring callbacks; wall includes all overhead but function rows do not prove a separate complete observer duration.",
            "sqlite_commit_seconds": None, "fsync_seconds": None,
            "unidentified_costs": "stdlib cProfile exposes combined Connection.execute C time; trace event counts cannot isolate COMMIT/fsync duration"}


def usage():
    value = resource.getrusage(resource.RUSAGE_SELF)
    return {"user_seconds": value.ru_utime, "system_seconds": value.ru_stime,
            "input_blocks": value.ru_inblock, "output_blocks": value.ru_oublock,
            "voluntary_context_switches": value.ru_nvcsw, "involuntary_context_switches": value.ru_nivcsw}


class Fixture:
    def __init__(self, business, size, mode, checkpoint, observer, *, reserve_cache_size=0):
        require(type(reserve_cache_size) is int and reserve_cache_size in (0, 128), "candidate cache must be exactly 0 or 128")
        self.reserve_cache_size = reserve_cache_size
        self.size, self.mode, self.checkpoint, self.observer = size, mode, checkpoint, observer
        self.case = "book-" + str(size)
        self.path = Path(business) / (self.case + "-" + mode + ".sqlite3")
        require(not self.path.exists(), "authority path must be new")
        self.exchange = ExchangeService(Database(self.path), {"USD": 8}, decision_audit=True,
                                        reserve_cache_size=self.reserve_cache_size)
        self.matcher = (Matcher(self.exchange) if mode == "original-scan"
                        else Matcher(self.exchange, book_selection=mode))
        self.version = 0
        self.actions = []

    def step(self, label, function, *args, **kwargs):
        self.checkpoint(self.case, self.mode, label, "before")
        result = function(*args, **kwargs)
        self.actions.append(label)
        self.checkpoint(self.case, self.mode, label, "after")
        return result

    def quote(self):
        self.version += 1
        return self.step("quote-" + str(self.version), self.exchange.publish_market,
            MarketSnapshot(self.version, datetime.now(timezone.utc), {"USD": AssetSpec(Decimal(1), Decimal(1))},
                           {"BTC-PERP": InstrumentSpec(Decimal(100), Decimal(".1"), Decimal(".05"))}))

    def setup(self, orders):
        self.quote()
        self.step("unhalt", self.exchange.set_kill_switch, False)
        for account in ("buyer", "seller"):
            self.step("create-" + account, self.exchange.create_account, account)
            self.step("fund-" + account, self.exchange.deposit, account, "synthetic-funding", "USD", Decimal(1000000))
        for row in orders:
            self.quote()
            self.step("submit-" + row["order_id"], self.exchange.submit_order, row["account_id"], row["order_id"],
                      "BTC-PERP", Decimal(row["quantity"]), Decimal(row["limit_price"]))

    def capture(self):
        with self.exchange.database.transaction() as connection:
            tables = {table: [dict(row) for row in connection.execute(
                "SELECT " + ("rowid AS book_sequence,*" if table == "uta_orders" else "*") +
                " FROM " + table + " ORDER BY " + ordering)] for table, ordering in TABLES.items()}
            settings = {"journal_mode": connection.execute("PRAGMA journal_mode").fetchone()[0],
                        "synchronous": connection.execute("PRAGMA synchronous").fetchone()[0]}
            ledger_count = self.exchange.ledger.verify(connection=connection)
            market = self.exchange._market(connection)
            risks = {account: self.exchange._risk(connection, account, market) for account in ("buyer", "seller")}
            # Same transaction as native fresh validation/risk; preserve the real
            # current quote bytes and immutable audit reference, not a normalized ID.
            payload = connection.execute("SELECT payload FROM uta_market WHERE singleton=1").fetchone()[0]
            digest = sha256(payload.encode()).hexdigest()
            history = connection.execute("SELECT * FROM uta_market_history WHERE snapshot_id=?", ("market:" + digest,)).fetchone()
            require(history is not None and history["payload"] == payload and history["content_digest"] == digest,
                    "current quote differs from archived quote")
            quote = json.loads(payload)
            require(set(quote) == {"version", "observed_at", "assets", "instruments"}
                    and canonical(quote) == canonical(json.loads(market.to_json())), "quote field/source mismatch")
            validation_clock = self.exchange._now()
            age_us = microseconds(validation_clock - market.observed_at)
            max_age_us = microseconds(self.exchange.max_price_age)
            require(max_age_us == 5000000 and -1000000 <= age_us <= max_age_us,
                    "verification quote stale/future; original TTL, no retry")
            risk_financial = risk_contract(risks, quote)
            market_provenance = {"payload": payload, "sha256": digest, "market_snapshot_id": "market:" + digest,
                "history": dict(history), "observed_at": quote["observed_at"],
                "validation_clock_after_risk": validation_clock.isoformat(), "age_us": age_us,
                "max_age_us": max_age_us, "max_future_skew_us": 1000000,
                "observed_at_semantics": "quote_asof_not_calculation_time"}
            market_financial = {key: quote[key] for key in ("version", "assets", "instruments")}
            decisions = [dict(row) for row in connection.execute(
                "SELECT decision_id,kind,market_snapshot_id FROM uta_risk_decisions ORDER BY decision_id")]
        require(settings == {"journal_mode": "wal", "synchronous": 2}, "WAL/FULL writer settings changed")
        # Only the schema's wall-time fields on these two tables differ across
        # independent fresh authorities. All original values remain in raw tables.
        projection = {table: [{key: value for key, value in row.items()
                        if not (table in {"uta_orders", "uta_matches"} and key == "created_at")}
                       for row in rows] for table, rows in tables.items()}
        accounts = {account: self.exchange.account(account) for account in ("buyer", "seller")}
        return {"tables": tables, "economic_projection": projection, "risks": risks,
                "risk_financial": risk_financial, "market_financial": market_financial, "market_provenance": market_provenance,
                "accounts": accounts, "ledger_count": ledger_count, "settings": settings, "decisions": decisions}

    def verify(self, expected):
        self.quote()
        before = self.step("pre-reopen-financial-capture", self.capture)
        require(len(before["tables"]["uta_matches"]) == BATCH_MATCHES, "unexpected matched count")
        require(len(before["tables"]["uta_fills"]) == 2 * BATCH_MATCHES, "unpaired/missing fill")
        actual = [{key: row[key] for key in ("trade_id", "buy_order_id", "sell_order_id", "quantity", "price")}
                  for row in before["tables"]["uta_matches"]]
        require(actual == expected["trades"], "actual price/time/maker trade sequence differs from independent reference")
        require(len({row["trade_id"] for row in before["tables"]["uta_matches"]}) == BATCH_MATCHES, "duplicate trade ID")
        for account, sign in (("buyer", 1), ("seller", -1)):
            values = before["accounts"][account]
            position = values["positions"]["BTC-PERP"]
            require(Fraction(values["balances"]["USD"]) == DEPOSIT - expected["fee_per_account"], "hand cash fee differs")
            require(Fraction(position["quantity"]) == sign * expected["quantity"], "hand position differs")
            require(Fraction(position["cost_basis"]) == sign * expected["notional"], "hand cost differs")
            fills = [row for row in before["tables"]["uta_fills"] if row["account_id"] == account]
            require(sum((Fraction(row["fee"]) for row in fills), Fraction()) == expected["fee_per_account"], "fill fees differ")
            require(all(Fraction(row["realized_pnl"]) == 0 for row in fills), "opening trade created PnL")
        self.exchange = self.step("reopen-native", ExchangeService, Database(self.path), {"USD": 8}, decision_audit=True,
                                       reserve_cache_size=self.reserve_cache_size)
        self.matcher = (Matcher(self.exchange, initialize=False) if self.mode == "original-scan"
                        else Matcher(self.exchange, initialize=False, book_selection=self.mode))
        after = self.step("post-reopen-financial-capture", self.capture)
        require(canonical(before["economic_projection"]) == canonical(after["economic_projection"]),
                "reopen changed typed economic state")
        strict = self.step("strict-matching-reconcile", self.matcher.verify, strict=True)
        require((strict["matches"], strict["paired_fills"], strict["unpaired_fills"]) == (BATCH_MATCHES, 2 * BATCH_MATCHES, 0),
                "strict matching correspondence failed")
        independent = self.step("independent-cashflow-replay", reconcile_exchange, self.exchange)
        require(independent["status"] == "passed", "independent financial replay failed")
        one = next(value for value in after["decisions"] if value["kind"] == "FILL_CONFIRMED")
        replay = self.step("one-historical-FILL-replay", self.exchange.audit.replay, one["decision_id"])
        require(replay["matches"] is True, "sampled valuation replay differs")
        return {"before_reopen": before, "after_reopen": after, "strict": strict, "independent": independent,
                "sampled_historical_replay": replay, "historical_replay_sample_count": 1}



def _run_observer_setup_observed(business, checkpoint, *, book_size, mode, observer):
    """One fresh authority, setup and snapshot only; never calls run_profile.

    A captured observer fault remains a failed incomplete observation (exit1).
    Non-reproduction exits after setup and grants no matching/profile acceptance.
    """
    require(type(book_size) is int and book_size == 32 and mode == "scan", "setup-only requires exactly32 scan")
    observer.phase = "setup-32-scan"
    wall, cpu = perf_counter_ns(), process_time_ns()
    fixture = Fixture(business, 32, "scan", checkpoint, observer)
    fixture.setup(workload(32))
    observation, snapshot_failure = None, None
    try:
        observation = observer.snapshot()
    except AssertionError as error:
        if observer.failure is None:
            raise
        snapshot_failure = {"type": observer._bounded(type(error).__module__ + "." + type(error).__qualname__, 128),
                            "message": observer._bounded(str(error), 512)}
    captured = observer.failure is not None
    result = {"kind": "SINGLE_AUTHORITY_OBSERVER_SETUP_DIAGNOSTIC_NOT_A_PROFILE", "profile_set": "observer-setup",
        "setup_only": True, "book_sizes": [32], "mode": "scan", "authorities": 1, "setup_orders": 32,
        "diagnostic_outcome": "OBSERVER_FAULT_CAPTURED" if captured else "FAULT_NOT_REPRODUCED",
        "observer_first_fault": observer.failure, "snapshot_failure": snapshot_failure, "observation": observation,
        "exit_status": 1 if captured else 0, "observer_complete": not captured,
        "setup_wall_ns": perf_counter_ns() - wall, "setup_cpu_ns": process_time_ns() - cpu,
        "actions": fixture.actions, "database_path": str(fixture.path),
        "matching_calls": 0, "timed_matching_calls": 0, "old_baseline_calls": 0, "aggregate_calls": 0,
        "warmup": 0, "retries": 0, "historical_H254_cause": "UNKNOWN_UNCHANGED",
        "all_functional_checks_passed": False, "component_profile_passed": False,
        "default_scan_regression_accepted": False, "throughput_capacity_accepted": False,
        "production_approved": False, "visibility": "PRIVATE_LOCAL_NO_AUTOMATIC_PUBLICATION"}
    # There is no next quote, verify, profiler, matching, alternate mode or
    # continuation even when the observer fault is not reproduced.
    return result




def run_reserve_reuse_pair(business, checkpoint, save_report, profiling_window, *, book_size, mode):
    """Experimental existing cache0/128, two fresh identical native scan books.

    This never changes a production default or implements different arithmetic.
    Only current economic inputs can hit the native bounded ReserveKernel.
    """
    require(type(book_size) is int and book_size == 32 and mode == "scan", "reserve pair requires exactly 32 scan")
    observer = SqlObserver()
    results = {}
    try:
        observer.install()
        for label, capacity in (("reference0", 0), ("candidate128", 128)):
            directory = Path(business) / label
            directory.mkdir(mode=0o700)
            observer.phase = "setup-" + label
            wall, cpu = perf_counter_ns(), process_time_ns()
            fixture = Fixture(directory, 32, "scan", checkpoint, observer, reserve_cache_size=capacity)
            fixture.case = "reserve-32-" + label
            fixture.setup(workload(32))
            setup = {"wall_ns": perf_counter_ns() - wall, "cpu_ns": process_time_ns() - cpu,
                     "cache_stats": fixture.exchange.reserve_cache_stats(), "sqlite_observation": observer.snapshot()}
            if capacity:
                require(setup["cache_stats"]["misses"] == setup["cache_stats"]["size"] == 6
                        and setup["cache_stats"]["hits"] > 0 and setup["cache_stats"]["evictions"] == 0,
                        "fixed initial economic-key cardinality differs from manual six-key oracle")
            else:
                require(all(setup["cache_stats"][name] == 0 for name in ("size", "hits", "misses", "evictions")),
                        "reference service must stay on uncached original Fraction path")
            fixture.quote()  # Same one genuine fresh quote before each timed call.
            before_cache = fixture.exchange.reserve_cache_stats()
            observer.phase = "matching-" + label
            checkpoint(fixture.case, "scan", "timed-region", "before")
            profiler = cProfile.Profile()
            profiling_window(True)
            try:
                profiler.enable()
                wall, cpu = perf_counter_ns(), process_time_ns()
                try:
                    matched = fixture.matcher.match_once("BTC-PERP", BATCH_MATCHES)
                finally:
                    matching_wall, matching_cpu = perf_counter_ns() - wall, process_time_ns() - cpu
            finally:
                profiler.disable()
                profiling_window(False)
            checkpoint(fixture.case, "scan", "timed-region", "after")
            require(matched["confirmed_trades"] == 8 and len(matched["trades"]) == 8
                    and not matched["blocked"] and not matched["cancelled_orders"], "incomplete first reserve-reuse sample; no retry")
            after_cache = fixture.exchange.reserve_cache_stats()
            delta = {name: after_cache[name] - before_cache[name] for name in ("hits", "misses", "evictions")}
            if capacity:
                require(delta["hits"] > 0 and 0 <= delta["misses"] <= 16 and delta["evictions"] == 0
                        and after_cache["size"] <= 22, "actual matching cache counts violate fixed workload bounds")
            else:
                require(all(value == 0 for value in delta.values()) and after_cache["size"] == 0,
                        "reference cache unexpectedly changed")
            observation = observer.snapshot()
            require(observation["events"].get("COMMIT", 0) >= 1, "matching financial COMMIT unobserved")
            matching = {"wall_ns_including_commit_and_observer": matching_wall, "cpu_ns": matching_cpu, "result": matched,
                        "cache_before": before_cache, "cache_after": after_cache, "cache_delta": delta,
                        "sqlite_observation": observation, "cprofile": profile_rows(profiler),
                        "timing_has_observer_and_profiler_overhead": True,
                        "not_per_fill_latency_or_open_loop_throughput": True}
            observer.phase = "verification-" + label
            verify_wall, verify_cpu = perf_counter_ns(), process_time_ns()
            verification = fixture.verify(reference_matches(workload(32)))
            policy = fixture.exchange.audit.policy_record(fixture.exchange.audit.policy_id)
            require(set(policy) == {"format", "risk_mode", "catalog", "rules", "scales", "fee_rate", "max_price_age_us",
                    "order_precision", "reserve_formula", "execution_options"}, "unknown/missing audited policy field")
            require(policy["execution_options"] == {"reserve_cache_size": capacity, "market_cache_size": 0},
                    "audited execution options differ from actual fixed candidate")
            verification["audit_policy"] = {"policy_id": fixture.exchange.audit.policy_id, "payload": policy,
                                           "artifact_id": fixture.exchange.audit.artifact_id}
            verification["sqlite_observation"] = observer.snapshot()
            verification["wall_ns"] = perf_counter_ns() - verify_wall
            verification["cpu_ns"] = process_time_ns() - verify_cpu
            verification["cache_stats_after_reopen_and_checks"] = fixture.exchange.reserve_cache_stats()
            require(verification["cache_stats_after_reopen_and_checks"]["capacity"] == capacity,
                    "reopen lost explicit execution option")
            result = {"label": label, "reserve_cache_size": capacity, "market_cache_size": 0,
                      "book_size": 32, "mode": "scan", "setup": setup, "matching": matching,
                      "verification": verification, "actions": fixture.actions,
                      "workload": {"seed": SEED + 32, "orders": workload(32), "deposit_per_account": "1000000",
                           "account_count": 2, "quantity_distribution_units": [1, 2, 5], "audit": True,
                           "fee_rate": ".0004", "USD_scale": 8, "native_clock": True, "market_cache_size": 0},
                      "production_approved": False}
            save_report("reserve-" + label + ".json", result)
            results[label] = result
        for stage in ("before_reopen", "after_reopen"):
            a, b = (results[label]["verification"][stage] for label in ("reference0", "candidate128"))
            for key in ("economic_projection", "risk_financial", "market_financial", "accounts"):
                require(canonical(a[key]) == canonical(b[key]), "reserve option changed typed financial state: " + stage + "/" + key)
        for label in ("reference0", "candidate128"):
            a, b = (results[label]["verification"][stage] for stage in ("before_reopen", "after_reopen"))
            for key in ("economic_projection", "risk_financial", "market_financial", "accounts"):
                require(canonical(a[key]) == canonical(b[key]), "reopen changed typed financial state: " + label + "/" + key)
        pa, pb = (results[label]["verification"]["audit_policy"] for label in ("reference0", "candidate128"))
        require(pa["artifact_id"] == pb["artifact_id"], "paired immutable financial runtime artifacts differ")
        for key in pa["payload"]:
            if key != "execution_options":
                require(canonical(pa["payload"][key]) == canonical(pb["payload"][key]), "economic policy differs: " + key)
        require(pa["policy_id"] != pb["policy_id"], "explicit execution-option policy change was not archived")
    finally:
        lifecycle = observer.close()
        save_report("observer-lifecycle.json", lifecycle)
    observer.raise_fault()
    return {"kind": "EXPERIMENTAL_EXACT_RESERVE_OPTION_PAIR_NOT_PRODUCTION_CAPACITY", "profile_set": "reserve-reuse",
            "authorities": 2, "book_sizes": [32], "mode": "scan", "capacities": [0, 128],
            "financial_fields_exact": True, "all_functional_checks_passed": True,
            "observer_lifecycle": lifecycle, "matching_calls": 2, "confirmed_matches_by_authority": [8, 8],
            "paired_fills_by_authority": [16, 16], "cache_counts_recorded_actual_not_inferred": True,
            "differences_allowed_only": ["execution option/cache diagnostics", "audit policy execution_options and derived policy identity", "existing explicit time provenance"],
            "default_scan_regression_accepted": False, "throughput_capacity_accepted": False,
            "statistical_significance_claimed": False, "production_approved": False}


def run_observer_setup(business, checkpoint, save_report, *, book_size, mode):
    observer = SqlObserver()
    try:
        observer.install()
        result = _run_observer_setup_observed(business, checkpoint, book_size=book_size, mode=mode, observer=observer)
    finally:
        lifecycle = observer.close()
        save_report("observer-lifecycle.json", lifecycle)
    if observer.failure is not None:
        result.update(diagnostic_outcome="OBSERVER_FAULT_CAPTURED", exit_status=1, observer_complete=False,
                      observer_first_fault=observer.failure)
    result["observer_lifecycle"] = lifecycle
    save_report("observer-setup.json", result)
    return result


def run_profile(business, checkpoint, save_report, profiling_window, profile_set):
    observer = SqlObserver()
    try:
        observer.install()
        result = _run_profile_observed(business, checkpoint, save_report, profiling_window, profile_set, observer)
    finally:
        lifecycle = observer.close()
        save_report("observer-lifecycle.json", lifecycle)
    observer.raise_fault()
    result["observer_lifecycle"] = lifecycle
    return result


def _run_profile_observed(business, checkpoint, save_report, profiling_window, profile_set, observer):
    require(profile_set in {"current", "original-scan"}, "unknown exact profile set")
    schedule = SCHEDULE if profile_set == "current" else ((32, "original-scan"), (128, "original-scan"))
    reports = {}
    for size, mode in schedule:
        key = str(size) + "-" + mode
        observer.phase = "setup-" + key
        setup_wall, setup_cpu = perf_counter_ns(), process_time_ns()
        orders = workload(size)
        expected = reference_matches(orders)
        fixture = Fixture(business, size, mode, checkpoint, observer)
        fixture.setup(orders)
        setup = {"wall_ns": perf_counter_ns() - setup_wall, "cpu_ns": process_time_ns() - setup_cpu,
                 "sqlite_observation": observer.snapshot()}
        # Exactly one current real quote before the one matching call. A stale
        # result is retained as an incomplete first sample, never republished
        # until successful or included in the paired result.
        fixture.quote()
        observer.phase = "matching-" + key
        checkpoint(fixture.case, mode, "timed-region", "before")
        profiler = cProfile.Profile()
        profiling_window(True)
        try:
            before_usage = usage()
            profiler.enable()
            wall, cpu = perf_counter_ns(), process_time_ns()
            try:
                matched = fixture.matcher.match_once("BTC-PERP", BATCH_MATCHES)
            finally:
                matching_wall, matching_cpu = perf_counter_ns() - wall, process_time_ns() - cpu
        finally:
            profiler.disable()
            after_usage = usage()
            profiling_window(False)
        checkpoint(fixture.case, mode, "timed-region", "after")
        observation = observer.snapshot()
        require(matched["confirmed_trades"] == BATCH_MATCHES and len(matched["trades"]) == BATCH_MATCHES,
                "first matching sample incomplete (including stale market); no automatic retry")
        require(not matched["blocked"] and not matched["cancelled_orders"], "unexpected block/cancel in fixed profile")
        require(observation["events"].get("COMMIT", 0) >= 1, "no observed matching financial COMMIT event")
        matching = {"wall_ns_including_commit_and_observer": matching_wall, "cpu_ns": matching_cpu,
                    "self_resource_delta": {name: after_usage[name] - before_usage[name] for name in before_usage},
                    "result": matched, "sqlite_observation": observation, "cprofile": profile_rows(profiler),
                    "confirmed_matches": BATCH_MATCHES, "paired_fills": 2 * BATCH_MATCHES,
                    "not_per_fill_latency_or_open_loop_throughput": True}
        observer.phase = "verification-" + key
        verify_wall, verify_cpu = perf_counter_ns(), process_time_ns()
        verified = fixture.verify(expected)
        verification = {"wall_ns": perf_counter_ns() - verify_wall, "cpu_ns": process_time_ns() - verify_cpu,
                        "sqlite_observation": observer.snapshot(), **verified}
        report = {"book_size": size, "mode": mode, "sequence_in_schedule": len(reports) + 1,
                  "workload": {"seed": SEED + size, "orders": orders, "symbol": "BTC-PERP", "mark": "100",
                      "collateral": "synthetic USD", "deposit_per_account": "1000000", "account_count": 2,
                      "quantity_distribution_units": [1, 2, 5], "max_confirmed_matches": BATCH_MATCHES,
                      "fees": "original default .0004, USD8", "clock": "original native default UTC", "audit": True},
                  "independent_expected": {"quantity": str(expected["quantity"]), "notional": str(expected["notional"]),
                      "fee_per_account": str(expected["fee_per_account"]), "trades": expected["trades"]},
                  "setup": setup, "matching": matching, "verification": verification,
                  "profile_overhead_included_symmetrically": True, "actions": fixture.actions,
                  "database_path": str(fixture.path), "production_approved": False}
        save_report("profile-" + key + ".json", report)
        reports[key] = report
    pairs = []
    for size in SIZES if profile_set == "current" else ():
        scan, snapshot = reports[str(size) + "-scan"], reports[str(size) + "-snapshot"]
        a, b = scan["verification"]["after_reopen"], snapshot["verification"]["after_reopen"]
        require(canonical(a["economic_projection"]) == canonical(b["economic_projection"]), "paired financial projection differs")
        require(canonical(a["risk_financial"]) == canonical(b["risk_financial"]), "paired non-temporal risk differs")
        require(canonical(a["market_financial"]) == canonical(b["market_financial"]), "paired quote finance/version differs")
        pairs.append({"book_size": size, "economic_projection_equal": True, "risk_nine_non_temporal_fields_equal": True, "quote_finance_and_version_equal": True,
                      "only_risk_observed_at_is_separate_quote_provenance": True,
                      "scan_matching_wall_ns": scan["matching"]["wall_ns_including_commit_and_observer"],
                      "snapshot_matching_wall_ns": snapshot["matching"]["wall_ns_including_commit_and_observer"],
                      "single_pair_only_no_statistical_significance": True})
    return {"kind": "SINGLE_NODE_SYNCHRONOUS_MATCHING_COMPONENT_PROFILE", "profile_set": profile_set,
            "authorities": len(schedule), "book_sizes": list(SIZES),
            "schedule": [list(value) for value in schedule], "pairs": pairs,
            "per_authority_confirmed_matches": BATCH_MATCHES, "per_authority_paired_fills": 2 * BATCH_MATCHES,
            "business_IDs_repeat_across_paired_authorities_do_not_sum_as_capacity": True,
            "all_functional_checks_passed": True, "all_original_reports_retained_separately": True,
            "read_only_source": True, "queue_network_replication_not_exercised": True,
            "latency_percentiles": None, "open_loop": False, "duration_1800_seconds_met": False,
            "default_scan_regression_accepted": False,
            "default_scan_regression_requires_separate_original_process_and_JSON_aggregate": True,
            "throughput_capacity_accepted": False, "production_approved": False}
