"""Bounded open-loop probes of real managed PID-owned durable admission.

An enqueue ACK never counts as financial success. Only an observed SUCCEEDED
receipt, followed by read-only order/reserve/audit reconciliation, qualifies.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
import cProfile
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from fractions import Fraction
import gzip
from hashlib import sha256
import io
import inspect
import json
import math
import os
from pathlib import Path
import pstats
from queue import Queue
import sqlite3
import sys
from threading import BoundedSemaphore, Event, Lock, Thread
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks.run_benchmark import LatencyHistogram
from benchmarks.run_group_benchmark import _environment, _policy
from uta import durable_process as process_module
from uta.decision_audit import DecisionAudit
from uta.durable_process import DurableProcessRouter
from uta.durable_batches import BatchStore
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec

ORIGINAL_WORKER = process_module._run_worker
TERMINAL = {"SUCCEEDED", "REJECTED", "QUARANTINED"}


def observed_worker(*args):
    """Record actual spawn inputs before calling the unchanged native worker."""
    directory = Path(os.environ["UTA_MANAGED_WORKER_RUNTIME_DIRECTORY"])
    path = directory / f"worker-{os.getpid()}.json"
    path.write_text(json.dumps({"pid": os.getpid(), "received_settings": args[2],
        "observed_utc": datetime.now(timezone.utc).isoformat(),
        "financial_owner_ready": False, "settings_are_not_admission_receipts": True}, indent=2) + "\n")
    if os.environ.get("UTA_MANAGED_WORKER_PROFILE_ENABLED") == "1":
        return profile_worker(*args)
    return ORIGINAL_WORKER(*args)


def profile_worker(*args):
    """Lifecycle-only instrumentation; no financial/guard function is replaced."""
    directory = Path(os.environ["UTA_MANAGED_PROFILE_DIRECTORY"])
    profile = cProfile.Profile()
    try:
        return profile.runcall(ORIGINAL_WORKER, *args)
    finally:
        profile.dump_stats(str(directory / f"worker-{args[1]}-pid-{os.getpid()}.prof"))


@dataclass(frozen=True)
class Configuration:
    duration: float = 10
    rate: float = 20
    accounts: int = 100
    shards: int = 2
    dispatchers: int = 2
    outstanding: int = 256
    inbox_capacity: int = 128
    reject_every: int = 10
    feed_interval: float = 2
    control_timeout: float = 3
    drain_seconds: float = 10
    timeout_ms: float = 1000
    poll_interval: float = .02
    background_interval: float = .1
    profile: bool = False
    normal_cache_size: int = 0
    financial_batch_size: int = 0
    durable_batches: bool = False

    def validate(self):
        for name, lower, upper in (("duration", .05, 10), ("rate", .1, 200),
                ("feed_interval", .1, 2), ("control_timeout", .1, 10),
                ("drain_seconds", .1, 15), ("timeout_ms", 1, 60000),
                ("poll_interval", .005, .2), ("background_interval", .01, 1)):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lower <= value <= upper:
                raise ValueError(f"{name} must be finite in {lower}..{upper}")
        for name, minimum, maximum in (("accounts", 1, 1000), ("shards", 1, 4),
                ("dispatchers", 1, 8), ("outstanding", 1, 4096),
                ("inbox_capacity", 1, 4096), ("reject_every", 0, 1000)):
            if type(getattr(self, name)) is not int or not minimum <= getattr(self, name) <= maximum:
                raise ValueError(f"{name} must be an integer in {minimum}..{maximum}")
        offered = int(self.duration * self.rate)
        if not 1 <= offered <= 2000 or self.shards > self.accounts or math.ceil(offered / self.accounts) > 900:
            raise ValueError("short diagnostic requires 1..2000 arrivals, shards<=accounts, <=900 orders/account")
        if type(self.profile) is not bool:
            raise ValueError("profile must be boolean")
        if type(self.normal_cache_size) is not int or not 0 <= self.normal_cache_size <= 65536:
            raise ValueError("normal_cache_size must be an integer in 0..65536")
        if type(self.financial_batch_size) is not int or self.financial_batch_size not in (0, 3, 4, 5, 6, 7, 8):
            raise ValueError("financial_batch_size must be zero or an integer in 3..8")
        if type(self.durable_batches) is not bool:
            raise ValueError("durable_batches must be boolean")
        if self.financial_batch_size and not self.durable_batches:
            raise ValueError("nonzero financial_batch_size requires durable_batches=True")


@contextmanager
def readonly(path):
    connection = sqlite3.connect(Path(path).absolute().as_uri() + "?mode=ro", uri=True, isolation_level=None, timeout=2)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        yield connection
    finally:
        connection.close()


def market(version):
    return MarketSnapshot(version, datetime.now(timezone.utc), {"USD": AssetSpec(D(1), D(1))},
        {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))})


def terminal_outcome(receipt):
    if receipt["state"] not in TERMINAL:
        raise ValueError("enqueue acknowledgement is not a financial terminal receipt")
    if receipt["state"] == "SUCCEEDED":
        return "financial_succeeded"
    if receipt["state"] == "QUARANTINED":
        return "technical_quarantined"
    error = json.loads(receipt["error"]) if isinstance(receipt["error"], str) else receipt["error"]
    return "business_rejected" if error["status"] < 500 else "control_or_market_rejected"


def command_technical_diagnostics(commands):
    """Count overlapping technical facts from every persisted CID, not outcomes.

    A final rejection or success does not erase earlier internal failures.
    Control/market CIDs are included; terminal_error is not the original cause.
    """
    facts, keys, kinds = [], set(), Counter()
    attempts_total = retried = last_error_count = quarantined = nonterminal = control_failed = 0
    for command in commands:
        key = command["shard"], command["command_id"]
        if key in keys:
            raise ValueError("duplicate persisted command identity in diagnostics")
        keys.add(key)
        attempts = command["attempts"]
        if type(attempts) is not int or attempts < 0:
            raise ValueError("invalid internal execution attempt count")
        kinds[command["kind"]] += 1
        has_last_error = command["last_error"] is not None
        attempts_total += attempts
        retried += bool(attempts)
        last_error_count += has_last_error
        quarantined += command["state"] == "QUARANTINED"
        is_nonterminal = command["state"] not in TERMINAL
        control_not_succeeded = command["kind"] in {"PUBLISH_MARKET", "SET_HALT"} and command["state"] != "SUCCEEDED"
        nonterminal += is_nonterminal
        control_failed += control_not_succeeded
        if attempts or has_last_error or command["state"] == "QUARANTINED" or is_nonterminal or control_not_succeeded:
            terminal_error = command.get("error")
            if isinstance(terminal_error, str):
                terminal_error = json.loads(terminal_error)
            facts.append({"shard": command["shard"], "command_id": command["command_id"],
                "kind": command["kind"], "state": command["state"], "attempts": attempts,
                "last_error": command["last_error"],
                "terminal_error_code": terminal_error.get("code") if terminal_error else None,
                "terminal_error_status": terminal_error.get("status") if terminal_error else None})
    return {"stored_commands": len(keys), "commands_by_kind": dict(kinds),
        "internal_execution_attempts": attempts_total, "commands_with_internal_attempts": retried,
        "commands_with_last_error": last_error_count, "quarantined_commands": quarantined,
        "nonterminal_commands": nonterminal, "control_commands_not_succeeded": control_failed,
        "affected_commands": sorted(facts, key=lambda row: (row["shard"], row["command_id"])),
        "diagnostics_overlap_outcomes": True,
        "original_internal_exception_available": False}


def batch_dispatch_diagnostics(connection):
    """Independent RO record counts; these are not observed COMMIT counts."""
    result = {"prepared_batches": 0, "committed_batches": 0, "recovered_batches": 0,
              "unresolved_batches": 0, "selected_commands": 0, "executed_commands": 0,
              "unique_selected_commands": 0, "unique_executed_commands": 0,
              "zero_executed_batches": 0, "partial_prefix_batches": 0,
              "failure_events": 0, "record_counts_are_not_commit_counts": True}
    phases = ("prepare", "membership", "execute", "between_commands", "freshness", "disposition", "commit")
    result.update({phase + "_failure_events": 0 for phase in phases})
    events = connection.execute("SELECT payload FROM uta_events WHERE event_type='COMMAND_BATCH_EXECUTION_FAILED' AND account_id IS NULL").fetchall()
    for row in events:
        value = json.loads(row[0])
        if (type(value.get("event_version")) is not int or value["event_version"] != 1
                or type(value.get("recording_generation")) is not int or value["recording_generation"] < 1
                or value.get("phase") not in {"prepare", "membership", "execute", "between_commands", "freshness", "disposition", "commit"}):
            raise RuntimeError("invalid stored batch failure diagnostic")
        result[value["phase"] + "_failure_events"] += 1
    result["failure_events"] = len(events)
    names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('uta_command_batch_manifests','uta_command_batch_outcomes','writer_fence_batch_capability')")}
    if not names:
        if events:
            raise RuntimeError("batch failure event appeared without a batch authority")
        return result
    if names != {"uta_command_batch_manifests", "uta_command_batch_outcomes", "writer_fence_batch_capability"}:
        raise RuntimeError("incomplete batch authority in reopened probe")
    manifests = {}
    for row in connection.execute("SELECT attempt_id,content FROM uta_command_batch_manifests"):
        value = json.loads(row[1])
        members = value["members"]
        if not isinstance(members, list) or not 3 <= len(members) <= 8:
            raise RuntimeError("invalid batch membership in reopened probe")
        ids = [member["command_id"] for member in members]
        if len(set(ids)) != len(ids):
            raise RuntimeError("duplicate batch membership in reopened probe")
        manifests[row[0]] = ids
        result["selected_commands"] += len(ids)
    result["prepared_batches"] = len(manifests)
    result["unique_selected_commands"] = len({cid for ids in manifests.values() for cid in ids})
    resolved = set()
    actual_executed = set()
    for row in connection.execute("SELECT attempt_id,disposition,content FROM uta_command_batch_outcomes"):
        if row[0] not in manifests or row[0] in resolved:
            raise RuntimeError("batch disposition lacks unique immutable membership")
        resolved.add(row[0])
        value = json.loads(row[2])
        executed = value["executed"]
        if (not isinstance(executed, list) or len(set(executed)) != len(executed)
                or not set(executed) <= set(manifests[row[0]])):
            raise RuntimeError("invalid batch executed prefix in reopened probe")
        if row[1] == "COMMITTED":
            for cid in executed:
                command = connection.execute("SELECT kind,state FROM uta_command_inbox WHERE command_id=?", (cid,)).fetchone()
                if command is None or command[0] in ("PUBLISH_MARKET", "SET_HALT") or command[1] not in TERMINAL:
                    raise RuntimeError("batch execution diagnostic lacks a terminal financial command")
            actual_executed.update(executed)
            result["committed_batches"] += 1
            result["executed_commands"] += len(executed)
            result["zero_executed_batches"] += not executed
            result["partial_prefix_batches"] += 0 < len(executed) < len(manifests[row[0]])
        elif row[1] == "RECOVERED" and not executed:
            result["recovered_batches"] += 1
        else:
            raise RuntimeError("invalid batch disposition in reopened probe")
    result["unresolved_batches"] = len(set(manifests) - resolved)
    result["unique_executed_commands"] = len(actual_executed)
    return result


def runtime_report(router, configuration):
    settings = dict(router._settings)
    if (settings["normal_cache_size"] != configuration.normal_cache_size
            or settings["financial_batch_size"] != configuration.financial_batch_size
            or router.durable_batches is not configuration.durable_batches):
        raise RuntimeError("requested runtime/capability did not reach the actual router")
    budget = inspect.signature(BatchStore.process).parameters["soft_budget_seconds"].default
    return {"router_settings": settings, "durable_batches_capability": router.durable_batches,
        "decision_audit_required": router.decision_audit_required,
        "financial_batch_soft_budget_seconds": budget,
        "soft_budget_is_not_a_latency_or_commit_deadline": True,
        "transport": "local Python SDK -> durable inbox -> independent spawned owner; no REST/TLS",
        "physical_commit_counts_measured": False,
        "record_counts_are_not_physical_commit_counts": True}


def worker_runtime_diagnostics(directory, expected_settings):
    records = [json.loads(path.read_text()) for path in sorted(directory.glob("worker-*.json"))]
    if not records or len({row["pid"] for row in records}) != len(records):
        raise RuntimeError("actual spawned worker settings were not uniquely recorded")
    for row in records:
        if (type(row["pid"]) is not int or row["pid"] <= 0 or row["pid"] == os.getpid()
                or row["received_settings"] != expected_settings):
            raise RuntimeError("actual spawned worker settings differ from the requested runtime")
    return records


def probe_qualification(summary):
    """Fail closed after preserving evidence; this gate is not production approval."""
    reasons = []
    technical = summary.get("command_technical_diagnostics")
    if technical is None:
        reasons.append("missing_all_cid_technical_diagnostics")
    else:
        if technical["internal_execution_attempts"]:
            reasons.append("internal_execution_attempts")
        if technical["commands_with_last_error"]:
            reasons.append("persisted_last_error")
        if technical["quarantined_commands"]:
            reasons.append("quarantined_command")
        if technical["nonterminal_commands"]:
            reasons.append("persisted_nonterminal_command")
        if technical["control_commands_not_succeeded"]:
            reasons.append("control_command_not_succeeded")
    batches = summary.get("batch_dispatch_diagnostics")
    if batches is None:
        reasons.append("missing_batch_dispatch_diagnostics")
    else:
        for key, reason in (("failure_events", "batch_internal_failure"),
                            ("unresolved_batches", "unresolved_batch"),
                            ("recovered_batches", "recovered_unknown_batch")):
            value = batches.get(key)
            if type(value) is not int or value < 0:
                reasons.append("invalid_batch_dispatch_diagnostics")
                break
            if value:
                reasons.append(reason)
    if summary.get("poll_errors"):
        reasons.append("receipt_poll_error")
    counts = summary["counts"]
    if counts.get("enqueue_technical_errors", 0):
        reasons.append("enqueue_technical_error")
    if counts.get("technical_quarantined", 0):
        reasons.append("observed_quarantined_command")
    if any(value and ("unknown" in name or "timeout" in name) for name, value in counts.items()):
        reasons.append("timeout_or_unknown")
    if any("error" in row for row in summary.get("feed_publications", [])):
        reasons.append("feed_publication_error")
    check = summary["readonly_reconciliation"]
    if not check["reopened_readonly"] or check["pending_count"] or check["unobserved_successes_found_on_reopen"]:
        reasons.append("reconciliation_or_pending_gap")
    return {"passed": not reasons, "stop_remaining_cases": bool(reasons), "reasons": reasons,
            "financial_soft_deadline_passed": counts.get("financial_success_late", 0) == 0,
            "scope": "bounded probe technical stop gate; business/control rejection and overload remain outcomes",
            "production_approved": False, "capacity_10000_per_s_passed": False, "stability_passed": False}


def error_details(error):
    result = {"error_type": type(error).__name__, "error_code": getattr(error, "code", None)}
    stack, seen = [error], set()
    while stack and len(seen) < 16:
        value = stack.pop()
        if value is None or id(value) in seen:
            continue
        seen.add(id(value))
        if getattr(value, "sqlite_errorcode", None) is not None:
            result.update(sqlite_errorcode=value.sqlite_errorcode, sqlite_errorname=value.sqlite_errorname)
            break
        stack.extend((getattr(value, "__cause__", None), getattr(value, "__context__", None)))
    return result


def observe_startup_ready(router, path, *, timeout=5.0, interval=.02):
    """Observe real readiness within one budget; never infer it from activation.

    READY pipe delivery can lag a successful control command. Only that known
    observation race and an exhausted diagnostic read budget permit a retry.
    Full observations survive failed startup without starting client arrivals.
    """
    if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout) or not 0 < timeout <= 5):
        raise ValueError("startup observation timeout must be in (0,5] seconds")
    if (isinstance(interval, bool) or not isinstance(interval, (int, float))
            or not math.isfinite(interval) or not 0 < interval <= .1):
        raise ValueError("startup observation interval must be in (0,.1] seconds")
    started = time.monotonic_ns()
    deadline = started + int(timeout * 1e9)
    metadata = {"budget_seconds": timeout, "interval_seconds": interval,
        "started_monotonic_ns": started, "started_utc": datetime.now(timezone.utc).isoformat(),
        "observations_file": Path(path).name, "observation_count": 0}
    last = None
    with Path(path).open("x") as stream:
        def write(row):
            stream.write(json.dumps(row, separators=(",", ":")) + "\n")
            stream.flush()
        def failed(reason):
            finished = time.monotonic_ns()
            write({"event": "finished", "outcome": reason, **metadata,
                   "finished_monotonic_ns": finished, "elapsed_seconds": (finished - started) / 1e9})
            raise RuntimeError("managed startup readiness " + reason + "; last complete diagnostic: "
                               + json.dumps(last, sort_keys=True))
        write({"event": "started", **metadata})
        while True:
            before = time.monotonic_ns()
            remaining = (deadline - before) / 1e9
            if remaining <= 0:
                failed("deadline_exceeded")
            # Each strict read consumes the same total budget. Neither a new
            # quote nor a longer lease is manufactured while waiting.
            diagnostic_budget = min(1.0, remaining)
            try:
                report = router.diagnostics(timeout=diagnostic_budget)
            except Exception as error:
                write({"event": "diagnostic_exception", "at_monotonic_ns": time.monotonic_ns(),
                       **error_details(error)})
                failed("diagnostic_exception")
            after = time.monotonic_ns()
            last = report
            metadata["observation_count"] += 1
            write({"event": "observation", "index": metadata["observation_count"],
                   "started_monotonic_ns": before, "finished_monotonic_ns": after,
                   "observed_utc": datetime.now(timezone.utc).isoformat(),
                   "elapsed_seconds": (after - started) / 1e9,
                   "diagnostic_budget_seconds": diagnostic_budget, "report": report})
            if report.get("decision_audit_required") is not True:
                failed("required_audit_unavailable")
            # A top-level timeout must not hide a fatal shard/report already
            # observed earlier in that same diagnostic transaction sequence.
            for worker in report.get("workers", []):
                if (worker.get("reason") not in {"ready", "observed", "not_observed", "diagnostic_timeout", "worker_unready"}
                        or worker.get("report", {}).get("state") == "failed"
                        or worker.get("report", {}).get("code")):
                    failed("non_transient_worker_diagnostic")
            if report.get("reason") not in {"ready", "worker_unready", "diagnostic_timeout"}:
                failed("non_transient_diagnostic")
            if after >= deadline:
                failed("deadline_exceeded")
            if report.get("ready") is True and report.get("financial_ready") is True and report.get("reason") == "ready":
                metadata.update(finished_monotonic_ns=after, elapsed_seconds=(after - started) / 1e9)
                write({"event": "finished", "outcome": "ready", **metadata})
                return report, metadata
            if report.get("reason") == "ready" or report.get("ready") is True:
                failed("inconsistent_diagnostic")
            time.sleep(min(interval, max(0, (deadline - time.monotonic_ns()) / 1e9)))


def verify_ledger(connection):
    """Independent integer/posting/hash replay; no production ledger function."""
    balances, previous = {}, "0" * 64
    rows = connection.execute("SELECT * FROM ledger_events ORDER BY sequence").fetchall()
    for index, event in enumerate(rows, 1):
        postings = connection.execute("SELECT * FROM ledger_postings WHERE sequence=? ORDER BY ordinal", (index,)).fetchall()
        if event["sequence"] != index or event["previous_hash"] != previous or event["sealed"] != 1:
            raise RuntimeError("ledger event chain is invalid")
        if [row["ordinal"] for row in postings] != list(range(len(postings))):
            raise RuntimeError("ledger posting sequence is invalid")
        values = [(row["account"], row["asset"], int(row["units"])) for row in postings]
        if values != sorted(values) or len({(a, b) for a, b, _ in values}) != len(values):
            raise RuntimeError("ledger postings are not canonical")
        totals = Counter()
        for account, asset, units in values:
            totals[asset] += units
            balances[account, asset] = balances.get((account, asset), 0) + units
        digest = sha256(json.dumps(values, separators=(",", ":")).encode()).hexdigest()
        content = [index, event["event_id"], previous, digest]
        actual_hash = sha256(json.dumps(content, separators=(",", ":")).encode()).hexdigest()
        if any(totals.values()) or digest != event["fingerprint"] or actual_hash != event["event_hash"]:
            raise RuntimeError("ledger balance or event hash is invalid")
        previous = actual_hash
    stored = {(row["account"], row["asset"]): int(row["units"]) for row in connection.execute("SELECT * FROM ledger_balances")}
    if stored != balances:
        raise RuntimeError("ledger balance projection does not reconcile")
    return len(rows)


def verify(paths, rows, account_shards, *, durable_batches=None):
    """Reopen every store RO after workers stop; verify all original IDs."""
    by_id = {row["command_id"]: row for row in rows}
    committed, pending, stored_commands, reports, all_cid_facts = set(), set(), set(), [], []
    batch_facts = []
    for shard, path in enumerate(paths):
        with readonly(path) as connection:
            marker = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='writer_fence_batch_capability'").fetchone() is not None
            if durable_batches is not None and marker is not durable_batches:
                raise RuntimeError("reopened shard batch capability differs from the requested fresh layout")
            if marker and [tuple(row) for row in connection.execute("SELECT singleton,format FROM writer_fence_batch_capability")] != [(1, 1)]:
                raise RuntimeError("reopened shard batch capability marker is invalid")
            if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise RuntimeError("storage integrity or foreign key failure")
            if connection.execute("PRAGMA journal_mode").fetchone()[0] != "wal":
                raise RuntimeError("managed store did not preserve WAL")
            DecisionAudit.validate(connection)
            if connection.execute("SELECT version FROM uta_schema").fetchone()[0] != 3:
                raise RuntimeError("required decision audit is not enabled")
            batch_facts.append(batch_dispatch_diagnostics(connection))
            persisted = [dict(row) for row in connection.execute("SELECT * FROM uta_command_inbox")]
            all_cid_facts.extend({"shard": shard, **row} for row in persisted)
            commands = {row["command_id"]: row for row in persisted if row["kind"] == "SUBMIT_ORDER"}
            stored_commands.update(commands)
            orders = {(row["account_id"], row["order_id"]): row for row in connection.execute("SELECT * FROM uta_orders")}
            accepted_rows = [json.loads(row[0]) for row in connection.execute("SELECT payload FROM uta_events WHERE event_type='ORDER_ACCEPTED'")]
            accepted = {(event["account_id"], event["order_id"]): event for event in accepted_rows}
            if len(accepted_rows) != len(accepted) or set(orders) != set(accepted):
                raise RuntimeError("orders and acceptance events disagree")
            versions, reserves = {}, Counter()
            success_ids = set()
            for cid, command in commands.items():
                if cid not in by_id:
                    raise RuntimeError("unoffered command appeared in inbox")
                arrival = by_id[cid]
                payload = json.loads(command["payload"])
                if (payload["account_id"], payload["order_id"], payload["symbol"], D(payload["quantity"]), D(payload["limit_price"])) != (
                        arrival["account_id"], arrival["order_id"], "BTC-PERP", D(arrival["quantity"]), D(100)):
                    raise RuntimeError("original command identity or financial terms changed")
                key = payload["account_id"], payload["order_id"]
                if command["state"] != "SUCCEEDED":
                    if key in orders:
                        raise RuntimeError("non-successful command has an order effect")
                    if command["state"] == "PENDING":
                        pending.add(cid)
                    continue
                order = orders.get(key)
                result = json.loads(command["result"])
                if order is None or (order["status"], D(order["quantity"]), D(order["limit_price"]), D(order["filled_quantity"]), order["reduce_only"]) != ("OPEN", D(".001"), D(100), D(0), 0):
                    raise RuntimeError("successful admission lost or modified its live reserve")
                if result["order_id"] != key[1] or result["account_id"] != key[0] or D(result["reserved_margin"]) != D(".01004"):
                    raise RuntimeError("terminal receipt disagrees with independent reserve")
                decision = connection.execute("SELECT * FROM uta_risk_decisions WHERE decision_id=?", (order["admission_decision_id"],)).fetchone()
                if decision is None or (decision["kind"], decision["business_id"], decision["account_id"], decision["post_version"]) != ("ORDER_ACCEPTED", key[1], key[0], order["version"]):
                    raise RuntimeError("required audit decision does not identify this financial commit")
                if decision["post_version"] != decision["pre_version"] + 1:
                    raise RuntimeError("audit account version is inconsistent")
                versions.setdefault(key[0], []).append(order["version"])
                reserves[key[0]] += Fraction(251, 25000)  # Independent .001*100*.1 + ceiling fee.
                success_ids.add(cid)
            if len(orders) != len(success_ids):
                raise RuntimeError("order lacks a unique successful original command")
            for account, index in account_shards.items():
                if index != shard:
                    continue
                sequence = sorted(versions.get(account, []))
                stored = connection.execute("SELECT version FROM uta_accounts WHERE account_id=?", (account,)).fetchone()
                balance = connection.execute("SELECT units FROM ledger_balances WHERE account=? AND asset='USD'", ("customer:" + account,)).fetchone()
                if stored is None or stored[0] != 1 + len(sequence) or sequence != list(range(2, 2 + len(sequence))) or int(balance[0]) != 100000000 * 10**8:
                    raise RuntimeError("account version or synthetic cash differs from actual admission count")
                # Sum each order/event/receipt reserve, without a risk kernel.
                actual = sum((Fraction(D(accepted[key]["reserved_margin"])) for key in orders if key[0] == account), Fraction(0))
                if actual != reserves[account]:
                    raise RuntimeError("live reserve projection does not reconcile")
            matches = connection.execute("SELECT COUNT(*) FROM uta_matches").fetchone()[0]
            if connection.execute("SELECT COUNT(*) FROM uta_positions").fetchone()[0] or connection.execute("SELECT COUNT(*) FROM uta_fills").fetchone()[0] or matches:
                raise RuntimeError("one-sided admission probe unexpectedly produced an execution")
            ledger_events = verify_ledger(connection)
            committed.update(success_ids)
            reports.append({"shard": shard, "commands": len(commands), "unique_orders": len(orders),
                "durable_batches_capability": marker, "confirmed_matches": matches,
                "ledger_events": ledger_events, "audit_required": True, "independent_reserve_account_version_ledger_verified": True})
    observed = {row["command_id"] for row in rows if row["outcome"] == "financial_succeeded"}
    acknowledged = {row["command_id"] for row in rows if row["enqueue_ack_ns"] is not None}
    if not acknowledged <= stored_commands:
        raise RuntimeError("a durable enqueue ACK disappeared after reopening storage")
    if not observed <= committed:
        raise RuntimeError("observed successful financial receipt was lost after reopening")
    return {"shards": reports, "observed_financial_successes": len(observed), "persistent_successes": len(committed),
        "unobserved_successes_found_on_reopen": len(committed - observed), "pending_original_ids": sorted(pending),
        "pending_count": len(pending), "durable_enqueue_acknowledgements_verified": len(acknowledged), "reopened_readonly": True,
        "command_technical_diagnostics": command_technical_diagnostics(all_cid_facts),
        "batch_dispatch_diagnostics": {key: (True if key == "record_counts_are_not_commit_counts" else sum(report[key] for report in batch_facts)) for key in batch_facts[0]}}


def profile_report(directory):
    reports = []
    for path in sorted(directory.glob("*.prof")):
        stream = io.StringIO()
        stats = pstats.Stats(str(path), stream=stream)
        stats.sort_stats("cumulative").print_stats(45)
        path.with_suffix(".txt").write_text(stream.getvalue())
        functions = [{"file": key[0], "line": key[1], "function": key[2], "calls": value[1],
                      "internal_seconds": value[2], "cumulative_seconds": value[3]}
                     for key, value in stats.stats.items()]
        critical = [row for row in functions if Path(row["file"]).name in (
            "writer_fence.py", "decision_audit.py", "durable_commands.py", "storage.py", "sharding.py", "service.py", "supervisor.py")]
        reports.append({"file": path.name, "total_profile_internal_seconds": stats.total_tt,
            "critical_functions": sorted(critical, key=lambda row: row["cumulative_seconds"], reverse=True)[:60]})
    return {"scope": "per-real-PID lifecycle and dispatcher0 cProfile; CPython3.12 permits one cProfile owner/interpreter. All dispatchers retain raw enqueue timing. Profiles include startup, waiting, shutdown; cumulative times overlap and are not CPU percentages", "profiles": reports}


def run(configuration, directory):
    configuration.validate()
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    profiles = directory / "profiles"
    profiles.mkdir()
    workers = directory / "workers"
    workers.mkdir()
    environment = _environment(directory)
    environment.update(generator_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        scope="local independent spawned managed PID owners, WAL/FULL, audit required, no replication; cohosted",
        sqlite_busy_timeout_seconds=10, market_max_age_seconds=5, profile=configuration.profile,
        requested_runtime={"normal_cache_size": configuration.normal_cache_size,
                           "financial_batch_size": configuration.financial_batch_size,
                           "durable_batches": configuration.durable_batches},
        evidence_kind="functional wiring only; not performance evidence" if configuration.duration <= .2 else "short local admission diagnostic; not capacity qualification")
    (directory / "environment.json").write_text(json.dumps(environment, indent=2) + "\n")
    accounts = [f"managed-probe-{index}" for index in range(configuration.accounts)]
    def bootstrap(router):
        for account in accounts:
            router.create_account(account)
            router.deposit(account, "synthetic-funding", "USD", D(100000000))
    router = DurableProcessRouter.initialize(directory / "authority", configuration.shards, {"USD": 8},
        managed=True, bootstrap=bootstrap, **_policy("configured_cross"), max_price_age=timedelta(seconds=5),
        queue_capacity=configuration.inbox_capacity, decision_audit=True,
        background_interval=configuration.background_interval,
        normal_cache_size=configuration.normal_cache_size,
        financial_batch_size=configuration.financial_batch_size, durable_batches=configuration.durable_batches)
    actual_runtime = runtime_report(router, configuration)
    environment["actual_runtime"] = actual_runtime
    (directory / "environment.json").write_text(json.dumps(environment, indent=2) + "\n")
    paths = [router._control._path(shard) for shard in range(configuration.shards)]
    account_shards = {account: router.shard_for(account) for account in accounts}
    old_worker = process_module._run_worker
    old_environ = {key: os.environ.get(key) for key in
        ("UTA_MANAGED_PROFILE_DIRECTORY", "UTA_MANAGED_WORKER_RUNTIME_DIRECTORY", "UTA_MANAGED_WORKER_PROFILE_ENABLED")}
    os.environ["UTA_MANAGED_WORKER_RUNTIME_DIRECTORY"] = str(workers.absolute())
    os.environ["UTA_MANAGED_WORKER_PROFILE_ENABLED"] = "1" if configuration.profile else "0"
    process_module._run_worker = observed_worker
    if configuration.profile:
        os.environ["UTA_MANAGED_PROFILE_DIRECTORY"] = str(profiles.absolute())
    feed_stop, dispatched = Event(), Event()
    feed_rows, poll_errors, telemetry, telemetry_at = [], [], [], {}
    lock, slots = Lock(), BoundedSemaphore(configuration.outstanding)
    pending = Queue(maxsize=configuration.outstanding)
    arrivals, results = {}, []
    offered = int(configuration.duration * configuration.rate)
    started = end_deadline = 0
    raw = (directory / "arrivals.jsonl").open("x")
    def finish(row, outcome, receipt=None):
        with lock:
            if row.get("_final"):
                return
            row["_final"] = True
            output = {key: value for key, value in row.items() if not key.startswith("_")}
            output.update(outcome=outcome, observed_completion_ns=time.monotonic_ns(), receipt=receipt)
            output["latency_ns"] = output["observed_completion_ns"] - output["planned_ns"]
            output["deadline_exceeded"] = output["latency_ns"] > configuration.timeout_ms * 1e6
            results.append(output)
            raw.write(json.dumps(output, separators=(",", ":")) + "\n")
        if row.get("_slot"):
            slots.release()
    def dispatch(index):
        while True:
            row = pending.get()
            if row is None:
                return
            if time.monotonic_ns() >= end_deadline:
                finish(row, "local_not_dispatched_timeout")
                continue
            row["enqueue_started_ns"] = time.monotonic_ns()
            try:
                receipt = router.submit_order(row["account_id"], row["command_id"], row["order_id"], "BTC-PERP", D(row["quantity"]), D(100))
                if receipt["ack"] != "durably_queued" or receipt["command_id"] != row["command_id"]:
                    raise RuntimeError("invalid durable enqueue acknowledgement")
                row["enqueue_ack_ns"] = time.monotonic_ns()
            except Exception as error:
                row["enqueue_error"] = error_details(error)
                row["enqueue_call_finished_ns"] = time.monotonic_ns()
                if getattr(error, "code", None) == "durable_queue_overloaded":
                    finish(row, "durable_queue_full")
                elif getattr(error, "status", 500) < 500:
                    finish(row, "enqueue_business_rejected")
            row["enqueue_call_finished_ns"] = time.monotonic_ns()
            row["_dispatched"] = True
    def dispatch_entry(index):
        if configuration.profile and index == 0:
            profile = cProfile.Profile()
            try:
                profile.runcall(dispatch, index)
            finally:
                profile.dump_stats(str(profiles / f"dispatcher-{index}.prof"))
        else:
            dispatch(index)
    def collect():
        while True:
            snapshot = {}
            for shard, path in enumerate(paths):
                try:
                    with readonly(path) as connection:
                        records = [dict(row) for row in connection.execute("SELECT * FROM uta_command_inbox WHERE kind='SUBMIT_ORDER'")]
                        snapshot.update({row["command_id"]: row for row in records})
                        if time.monotonic_ns() - telemetry_at.get(shard, 0) > 200_000_000:
                            payload = connection.execute("SELECT payload FROM uta_market").fetchone()
                            telemetry.append({"at_ns": time.monotonic_ns(), "shard": shard,
                                "command_states": dict(Counter(row["state"] for row in records)),
                                "market": json.loads(payload[0]) if payload else None})
                            telemetry_at[shard] = telemetry[-1]["at_ns"]
                except Exception as error:
                    poll_errors.append({"at_ns": time.monotonic_ns(), **error_details(error)})
            with lock:
                ready = [row for row in arrivals.values() if row.get("_dispatched") and not row.get("_final")]
            for row in ready:
                receipt = snapshot.get(row["command_id"])
                if receipt and receipt["state"] in TERMINAL:
                    finish(row, terminal_outcome(receipt), receipt)
                elif time.monotonic_ns() >= end_deadline:
                    finish(row, "result_unknown_at_drain_deadline", receipt)
            with lock:
                complete = len(results) == offered
            if dispatched.is_set() and complete:
                return
            time.sleep(configuration.poll_interval)
    def feed():
        version = 1
        while not feed_stop.wait(configuration.feed_interval):
            version += 1
            snapshot = market(version)
            row = {"version": version, "snapshot": json.loads(snapshot.to_json()), "started_ns": time.monotonic_ns()}
            try:
                row["publication"] = router.publish_market(snapshot, timeout=configuration.control_timeout)
                row["activation"] = router.set_kill_switch(False, timeout=configuration.control_timeout)
                if row["publication"]["publishing"] or row["activation"]["halted"]:
                    raise RuntimeError("fresh synthetic publication/activation remained incomplete")
            except Exception as error:
                row["error"] = error_details(error)
                feed_rows.append({**row, "finished_ns": time.monotonic_ns()})
                return  # Never relabel or refresh this old observation.
            feed_rows.append({**row, "finished_ns": time.monotonic_ns()})
    threads = []
    setup_started = time.monotonic_ns()
    try:
        router.start()
        router.publish_market(market(1), timeout=10)
        router.set_kill_switch(False, timeout=10)
        initial, startup_observation = observe_startup_ready(router, directory / "startup-readiness.jsonl")
        pids = {row["pid"] for row in initial["workers"]}
        if None in pids or os.getpid() in pids or len(pids) != configuration.shards:
            raise RuntimeError("benchmark requires distinct real fenced child PIDs")
        setup_seconds = (time.monotonic_ns() - setup_started) / 1e9
        started = time.monotonic_ns()
        end_deadline = started + int((configuration.duration + configuration.drain_seconds) * 1e9)
        (directory / "arrival-window.json").write_text(json.dumps({"configuration": asdict(configuration),
            "planned_start_monotonic_ns": started, "drain_deadline_monotonic_ns": end_deadline,
            "offered": offered, "observed_utc": datetime.now(timezone.utc).isoformat()}, indent=2) + "\n")
        collector = Thread(target=collect, name="managed-receipt-observer")
        feeder = Thread(target=feed, name="managed-real-synthetic-feed")
        threads = [Thread(target=dispatch_entry, args=(index,), name=f"managed-dispatch-{index}") for index in range(configuration.dispatchers)]
        collector.start()
        feeder.start()
        for thread in threads:
            thread.start()
        for sequence in range(offered):
            planned = started + int(sequence * 1e9 / configuration.rate)
            delay = planned - time.monotonic_ns()
            if delay > 0:
                time.sleep(delay / 1e9)
            invalid = bool(configuration.reject_every and sequence % configuration.reject_every == configuration.reject_every - 1)
            account = accounts[sequence % len(accounts)]
            row = {"sequence": sequence, "command_id": f"bench:{sequence}", "order_id": f"order:{sequence}",
                "account_id": account, "shard": account_shards[account], "quantity": ".0005" if invalid else ".001",
                "intended_product_rejection": invalid, "planned_ns": planned, "offered_ns": time.monotonic_ns(),
                "enqueue_started_ns": None, "enqueue_ack_ns": None, "enqueue_call_finished_ns": None}
            with lock:
                arrivals[sequence] = row
            if slots.acquire(blocking=False):
                row["_slot"] = True
                pending.put_nowait(row)
            else:
                finish(row, "local_outstanding_full")
        for _ in threads:
            pending.put(None)
        for thread in threads:
            thread.join()
        dispatched.set()
        collector.join()
        settled = time.monotonic_ns()
        (directory / "measurement-footer.json").write_text(json.dumps({
            "timing_contract_version": 1, "started_monotonic_ns": started,
            "terminal_observation_finished_monotonic_ns": settled,
            "planned_duration_ns": int(configuration.duration * 1e9),
            "setup_and_close_excluded": True}, indent=2) + "\n")
        feed_stop.set()
        feeder.join()
        final_diagnostics = router.diagnostics()
    finally:
        feed_stop.set()
        close_started = time.monotonic_ns()
        router.close()
        close_seconds = (time.monotonic_ns() - close_started) / 1e9
        process_module._run_worker = old_worker
        for key, value in old_environ.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        raw.close()
    if len(results) != offered or len({row["command_id"] for row in results}) != offered:
        raise RuntimeError("offered command IDs were lost or duplicated")
    checks = verify(paths, results, account_shards, durable_batches=configuration.durable_batches)
    worker_inputs = worker_runtime_diagnostics(workers, actual_runtime["router_settings"])
    counts = dict(Counter(row["outcome"] for row in results))
    outcome_counts = dict(counts)  # Exactly one terminal/local outcome per arrival.
    counts["durably_enqueued"] = sum(row["enqueue_ack_ns"] is not None for row in results)
    counts["enqueue_technical_errors"] = sum(bool(row.get("enqueue_error")) for row in results if row["outcome"] not in ("durable_queue_full", "enqueue_business_rejected"))
    counts["financial_success_late"] = sum(row["outcome"] == "financial_succeeded" and row["deadline_exceeded"] for row in results)
    histograms = {name: LatencyHistogram() for name in ("all", "financial_succeeded", "enqueue_ack")}
    for row in results:
        histograms["all"].observe(row["latency_ns"])
        if row["outcome"] == "financial_succeeded":
            histograms["financial_succeeded"].observe(row["latency_ns"])
        if row["enqueue_ack_ns"] is not None:
            histograms["enqueue_ack"].observe(row["enqueue_ack_ns"] - row["planned_ns"])
    elapsed = max(configuration.duration, (settled - started) / 1e9)
    summary = {"configuration": asdict(configuration), "offered": offered, "counts": counts,
        "actual_runtime": actual_runtime, "actual_spawned_worker_inputs": worker_inputs,
        "evidence_kind": environment["evidence_kind"],
        "outcome_counts": outcome_counts,
        "duration_including_terminal_observation_drain": elapsed, "drain_seconds": max(0, elapsed - configuration.duration),
        "close_seconds_excluded": close_seconds, "startup_seconds_excluded": setup_seconds,
        "unique_observed_financial_success_per_s": counts.get("financial_succeeded", 0) / elapsed,
        "enqueue_ack_per_s_not_financial_success": counts["durably_enqueued"] / elapsed,
        "latency_ms": {name: histogram.report() for name, histogram in histograms.items()},
        "initial_real_pid_and_fence": initial, "startup_readiness_observation": startup_observation,
        "final_diagnostics": final_diagnostics,
        "poll_errors": poll_errors, "feed_publications": feed_rows, "readonly_reconciliation": checks,
        "command_technical_diagnostics": checks["command_technical_diagnostics"],
        "batch_dispatch_diagnostics": checks["batch_dispatch_diagnostics"],
        "profile": profile_report(profiles), "environment": environment,
        "production_approved": False, "capacity_10000_per_s_passed": False,
        "scope": "<=10s managed local process inbox admission diagnostic; all successful orders OPEN, no simulated or real fills, no replication; profiling includes instrumentation overhead"}
    summary["execution_classification"] = {
        "durable_metadata_enqueue_acknowledgements": counts["durably_enqueued"],
        "observed_financial_admission_committed_receipts": counts.get("financial_succeeded", 0),
        "business_rejected": counts.get("business_rejected", 0),
        "control_or_market_rejected": counts.get("control_or_market_rejected", 0),
        "control_cids": {kind: checks["command_technical_diagnostics"]["commands_by_kind"].get(kind, 0)
                         for kind in ("PUBLISH_MARKET", "SET_HALT")},
        "batch_selected_memberships": checks["batch_dispatch_diagnostics"]["selected_commands"],
        "batch_executed_memberships_including_rejections": checks["batch_dispatch_diagnostics"]["executed_commands"],
        "internal_command_execution_attempts": checks["command_technical_diagnostics"]["internal_execution_attempts"],
        "batch_failure_events_by_phase": {phase: checks["batch_dispatch_diagnostics"][phase + "_failure_events"]
            for phase in ("prepare", "membership", "execute", "between_commands", "freshness", "disposition", "commit")},
        "physical_metadata_and_financial_commit_counts_measured": False}
    summary["probe_qualification"] = probe_qualification(summary)
    (directory / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    for name, data in (("arrivals", (directory / "arrivals.jsonl").read_bytes()),
                       ("telemetry", ("\n".join(json.dumps(row) for row in telemetry) + "\n").encode())):
        (directory / f"{name}.jsonl.gz").write_bytes(gzip.compress(data, mtime=0))
    (directory / "arrivals.jsonl").unlink()
    (directory / "manifest.json").write_text(json.dumps({"database_files_included": False, "files": {
        str(path.relative_to(directory)): {"bytes": path.stat().st_size, "sha256": sha256(path.read_bytes()).hexdigest()}
        for path in directory.rglob("*") if path.is_file() and (path.parent in (profiles, workers) or path.name in ("summary.json", "environment.json", "arrival-window.json", "measurement-footer.json", "arrivals.jsonl.gz", "telemetry.jsonl.gz", "startup-readiness.jsonl"))}}, indent=2) + "\n")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--duration", type=float, default=10)
    parser.add_argument("--rate", type=float, default=20)
    parser.add_argument("--accounts", type=int, default=100)
    parser.add_argument("--shards", type=int, default=2)
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--normal-cache-size", type=int, default=0)
    parser.add_argument("--financial-batch-size", type=int, default=0)
    parser.add_argument("--durable-batches", action="store_true")
    parser.add_argument("--cpu-limit", type=int, default=2)
    args = parser.parse_args(argv)
    if not 1 <= args.cpu_limit <= 4:
        parser.error("cpu-limit must be 1..4")
    configuration = Configuration(duration=args.duration, rate=args.rate, accounts=args.accounts,
        shards=args.shards, profile=args.profile, normal_cache_size=args.normal_cache_size,
        financial_batch_size=args.financial_batch_size, durable_batches=args.durable_batches)
    try:
        configuration.validate()
    except ValueError as error:
        parser.error(str(error))
    os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:args.cpu_limit])
    result = run(configuration, args.output)
    print(json.dumps(result, indent=2))
    return 0 if result["probe_qualification"]["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
