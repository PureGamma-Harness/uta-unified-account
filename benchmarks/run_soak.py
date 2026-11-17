"""Recoverable, bounded, low-rate soak of one real synthetic UTA authority.

The same database, accounts and immutable business IDs survive the entire job.
This co-hosted stability experiment cannot approve 10k/s capacity or real funds.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
import copy
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import fcntl
import gzip
from hashlib import sha256
import json
import math
import os
from pathlib import Path
from queue import Empty, Queue
import resource
import shutil
import signal
import sqlite3
import stat
import subprocess
import sys
from threading import BoundedSemaphore, Event, Thread
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks.run_benchmark import LatencyHistogram
from uta.credit import CreditService
from uta.examples import synthetic_policy
from uta.market import MarketSnapshot
from uta.matching import Matcher
from uta.models import AssetSpec, InstrumentSpec
from uta.reconciliation import reconcile_exchange
from uta.service import ExchangeService
from uta.storage import Database


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _pid_identity(pid):
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
    except (OSError, IndexError):
        return None


def _atomic(path, value):
    temporary = path.with_name(path.name + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(json.dumps(value, indent=2) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _observed_file_bytes(paths):
    """Sample regular-file sizes without racing an is_file/stat pair.

    SQLite sidecars and atomic-publication temporaries may disappear after
    directory discovery. Required files and other I/O failures remain fatal.
    """
    total = 0
    for path in paths:
        try:
            details = path.stat()
        except FileNotFoundError:
            if path.name in {"authority.sqlite3-wal", "authority.sqlite3-shm"} or path.name.endswith(".tmp"):
                continue
            raise
        if stat.S_ISREG(details.st_mode):
            total += details.st_size
    return total


@dataclass(frozen=True)
class Configuration:
    duration: float = 86400
    rate: float = .25
    queue_capacity: int = 32
    feed_interval: float = 1
    heartbeat_interval: float = 5
    export_interval: float = 60
    verify_interval: float = 900
    max_database_bytes: int = 4 * 1024**3
    max_directory_bytes: int = 6 * 1024**3
    min_free_bytes: int = 1024**3

    def validate(self):
        for name in ("duration", "rate", "feed_interval", "heartbeat_interval", "export_interval", "verify_interval"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        if not 0 < self.duration <= 172800 or not .01 <= self.rate <= 2:
            raise ValueError("bounded soak requires duration<=172800 and .01<=rate<=2")
        if not .05 <= self.feed_interval <= 2 or not .1 <= self.heartbeat_interval <= 60 or self.verify_interval < .1:
            raise ValueError("feed .05..2s, heartbeat .1..60s and verify>=.1s required")
        if type(self.queue_capacity) is not int or not 1 <= self.queue_capacity <= 128:
            raise ValueError("queue_capacity must be 1..128")
        for name in ("max_database_bytes", "max_directory_bytes", "min_free_bytes"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 0:
                raise ValueError("disk budgets must be nonnegative integer bytes")
        if self.max_database_bytes < 1024**2 or self.max_directory_bytes < self.max_database_bytes:
            raise ValueError("database budget>=1MiB and directory budget>=database budget required")
        if int(self.duration * self.rate) < 1:
            raise ValueError("at least one planned round is required")


def environment():
    def git(*args):
        return subprocess.check_output(("git", *args), cwd=ROOT, text=True).strip()
    return {"commit": git("rev-parse", "HEAD"),
            "tracked_changes": git("status", "--porcelain", "--untracked-files=no"),
            "source_sha256": {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest()
                for p in sorted([*(ROOT / "uta").glob("*.py"), Path(__file__)])},
            "python": sys.version, "sqlite": sqlite3.sqlite_version,
            "affinity": sorted(os.sched_getaffinity(0)),
            "cgroup": {name: (Path("/sys/fs/cgroup") / name).read_text().strip()
                for name in ("cpu.max", "memory.max") if (Path("/sys/fs/cgroup") / name).exists()},
            "cohost": "Other engineering and CI jobs may run concurrently; this is not isolated capacity testing",
            "synthetic": True, "replication": "none; single-host WAL/FULL"}


def service(path):
    catalog, rules = synthetic_policy()
    return ExchangeService(Database(path, timeout=2), {"USD": 8, "BTC": 8},
        max_price_age=timedelta(seconds=5), product_catalog=catalog, portfolio_rules=rules,
        reserve_cache_size=0, market_cache_size=0)


@contextmanager
def readonly(path):
    connection = sqlite3.connect(Path(path).absolute().as_uri() + "?mode=ro", uri=True, timeout=2,
                                 isolation_level=None)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        yield connection
    finally:
        connection.close()


class ReadOnlyDatabase:
    def __init__(self, original):
        self.original, self.path = original, original.path

    def transaction(self):
        return readonly(self.path)

    def _using(self, connection=None):
        return self.original._using(connection) if connection is not None else self.transaction()


def schema_digest(connection):
    return sha256(_json([tuple(row) for row in connection.execute(
        "SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name")]).encode()).hexdigest()


class Soak:
    def __init__(self, directory, configuration=None, *, resume=False, strict_source=True):
        self.directory = Path(directory).absolute()
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.directory, 0o700)
        self.lock = os.open(self.directory / "run.lock", os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            os.close(self.lock)
            raise RuntimeError("another soak writer owns this job")
        self.stop = Event()
        self.resumed, self.resume_at_ns = resume, time.time_ns()
        self.configuration = configuration or Configuration()
        self.configuration.validate()
        self.path = self.directory / "authority.sqlite3"
        self.env = environment()
        self.strict_source = strict_source
        try:
            if strict_source and self.env["tracked_changes"]:
                raise RuntimeError("soak must run from an immutable clean checkout")
            if resume:
                original = json.loads((self.directory / "job.json").read_text())
                if configuration is not None and asdict(configuration) != original["configuration"]:
                    raise RuntimeError("resume cannot alter the original duration or workload")
                self.configuration = Configuration(**original["configuration"])
                self.configuration.validate()
                if strict_source and any(self.env[key] != original["environment"][key] for key in ("commit", "source_sha256")):
                    raise RuntimeError("resume source differs; start a distinct candidate job")
                if not self.path.exists() or self.path.stat().st_ino != original["database_inode"]:
                    raise RuntimeError("original financial database is missing or replaced")
                with readonly(self.path) as connection:
                    if schema_digest(connection) != original["schema_digest"]:
                        raise RuntimeError("authority schema changed; refusing constructor repair")
                    if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                        raise RuntimeError("authority integrity check failed")
                self.meta = original
            else:
                if self.path.exists() or (self.directory / "job.json").exists():
                    raise RuntimeError("existing job requires resume; financial state must not be reset")
            self.exchange = service(self.path)
            self.matcher = Matcher(self.exchange)
            self.credit = CreditService(self.exchange)
            self.database = self.exchange.database
            if not resume:
                self._initialize()
            self.session = uuid4().hex
            self.last_active = time.monotonic_ns()
            self.last_verify = time.monotonic()
            with self.database.transaction() as connection:
                connection.execute("UPDATE soak_sessions SET status='interrupted',ended_ns=heartbeat_ns WHERE status='running'")
                connection.execute("INSERT INTO soak_sessions VALUES (?,?,?,?,?,?,?,?)",
                    (self.session, os.getpid(), time.time_ns(), time.time_ns(), None, 0, "running", _pid_identity(os.getpid())))
                connection.execute("UPDATE soak_meta SET value='false' WHERE key='logs_verified'")
                self._event(connection, "SESSION_STARTED", {"session": self.session, "pid": os.getpid(), "resumed": resume})
            (self.directory / "STOP").unlink(missing_ok=True)
            self._validate(full=True)
        except BaseException:
            self.close()
            raise

    def _initialize(self):
        for account in ("soak-alice", "soak-bob", "soak-credit"):
            self.exchange.create_account(account)
            self.exchange.deposit(account, "synthetic-initial-usd", "USD", D(1000000))
        self.exchange.deposit("soak-credit", "synthetic-interest-buffer", "BTC", D(1))
        self.credit.configure_asset_limit("BTC", D(1))
        self.credit.configure_limit("soak-credit", "BTC", D(1))
        self.credit.fund_pool("synthetic-pool", "BTC", D(1), source_reference="synthetic:soak:pool")
        self.tick()
        self.exchange.set_kill_switch(False)
        with self.database.transaction() as connection:
            for statement in (
                "CREATE TABLE soak_meta (key TEXT PRIMARY KEY,value TEXT NOT NULL)",
                "CREATE TABLE soak_arrivals (sequence INTEGER PRIMARY KEY,planned_ns INTEGER NOT NULL,status TEXT NOT NULL,started_ns INTEGER,completed_ns INTEGER,error TEXT)",
                "CREATE TABLE soak_steps (round INTEGER NOT NULL,step TEXT NOT NULL,status TEXT NOT NULL,result TEXT,receipt_sequence INTEGER,PRIMARY KEY(round,step))",
                "CREATE TABLE soak_evidence (sequence INTEGER PRIMARY KEY AUTOINCREMENT,at_ns INTEGER NOT NULL,kind TEXT NOT NULL,payload TEXT NOT NULL)",
                "CREATE TABLE soak_exports (first_sequence INTEGER PRIMARY KEY,last_sequence INTEGER NOT NULL,filename TEXT NOT NULL,digest TEXT)",
                "CREATE TRIGGER soak_evidence_no_update BEFORE UPDATE ON soak_evidence BEGIN SELECT RAISE(ABORT,'immutable soak evidence'); END",
                "CREATE TRIGGER soak_evidence_no_delete BEFORE DELETE ON soak_evidence BEGIN SELECT RAISE(ABORT,'immutable soak evidence'); END",
                "CREATE TABLE soak_sessions (id TEXT PRIMARY KEY,pid INTEGER,started_ns INTEGER,heartbeat_ns INTEGER,ended_ns INTEGER,active_ns INTEGER,status TEXT,process_identity TEXT)",
            ):
                connection.execute(statement)
            start = time.time_ns()
            connection.execute("INSERT INTO soak_meta VALUES ('export_cursor','0')")
            connection.execute("INSERT INTO soak_meta VALUES ('status','initialized')")
            connection.execute("INSERT INTO soak_meta VALUES ('logs_verified','false')")
            self.meta = {"configuration": asdict(self.configuration), "environment": self.env,
                "started_ns": start, "started_utc": datetime.fromtimestamp(start / 1e9, timezone.utc).isoformat(),
                "deadline_ns": start + int(self.configuration.duration * 1e9),
                "planned_rounds": int(self.configuration.duration * self.configuration.rate),
                "database_inode": self.path.stat().st_ino, "schema_digest": schema_digest(connection),
                "production_approved": False}
        _atomic(self.directory / "job.json", self.meta)

    @staticmethod
    def _event(connection, kind, payload):
        return connection.execute("INSERT INTO soak_evidence(at_ns,kind,payload) VALUES (?,?,?)", (time.time_ns(), kind, _json(payload))).lastrowid

    @staticmethod
    def _prove_step(connection, previous):
        result = json.loads(previous["result"])
        event = connection.execute("SELECT * FROM soak_evidence WHERE sequence=?", (previous["receipt_sequence"],)).fetchone()
        expected = {"round": previous["round"], "step": previous["step"], "result": result}
        if event is None or event["kind"] != "STEP_CONFIRMED" or json.loads(event["payload"]) != expected:
            raise RuntimeError("step checkpoint lacks its immutable confirmation")
        if "order_id" in result:
            order = connection.execute("SELECT * FROM uta_orders WHERE account_id=? AND order_id=?",
                (result["account_id"], result["order_id"])).fetchone()
            if (order is None or any(D(order[key]) != D(result[key]) for key in ("quantity", "limit_price"))
                    or bool(order["reduce_only"]) != result["reduce_only"]
                    or ("cancel" in previous["step"] and order["status"] != "CANCELLED")):
                raise RuntimeError("step checkpoint disagrees with its real order")
        elif "trade_ids" in result:
            matches = [connection.execute("SELECT quantity FROM uta_matches WHERE trade_id=?", (trade,)).fetchone()
                       for trade in result["trade_ids"]]
            if not matches or any(row is None for row in matches) or sum((D(row[0]) for row in matches), D(0)) != D(result["confirmed_quantity"]):
                raise RuntimeError("step checkpoint lacks its real confirmed match quantity")
        elif "journal_event_id" in result:
            command = connection.execute("SELECT result FROM credit_commands WHERE journal_event_id=?", (result["journal_event_id"],)).fetchone()
            if command is None or json.loads(command[0]) != result:
                raise RuntimeError("step checkpoint lacks its original credit command")
        elif result.get("confirmed_trades", 0) != 0:
            raise RuntimeError("no-liquidity checkpoint unexpectedly contains a trade")
        return result

    def tick(self):
        with self.exchange._transaction() as connection:
            row = connection.execute("SELECT payload FROM uta_market WHERE singleton=1").fetchone()
            version = json.loads(row[0])["version"] + 1 if row else 1
        # This is a real publish through the authority, with a fresh actual UTC
        # observation on every tick. Mark moves by valid .01 increments.
        mark = D(100) + D(version % 5) / 100
        snapshot = MarketSnapshot(version, datetime.now(timezone.utc),
            {"USD": AssetSpec(D(1), D(1)), "BTC": AssetSpec(mark, D(".8"))},
            {"BTC-PERP": InstrumentSpec(mark, D(".1"), D(".05"))})
        self.exchange.publish_market(snapshot)
        with self.exchange._transaction() as connection:
            if connection.execute("SELECT 1 FROM sqlite_master WHERE name='soak_evidence'").fetchone():
                self._event(connection, "FEED_TICK", {"snapshot": json.loads(snapshot.to_json()),
                    "published_ns": time.time_ns(), "synthetic": True})

    def _step(self, sequence, name, operation):
        with self.database.transaction() as connection:
            previous = connection.execute("SELECT * FROM soak_steps WHERE round=? AND step=?", (sequence, name)).fetchone()
            if previous is not None and previous["status"] == "done":
                return self._prove_step(connection, previous)
            connection.execute("INSERT OR IGNORE INTO soak_steps VALUES (?,?,'pending',NULL,NULL)", (sequence, name))
            self._event(connection, "STEP_ATTEMPT", {"round": sequence, "step": name})
        # Business effects and this tool's checkpoint use separate commits.
        # Every operation below re-queries or replays the SAME immutable ID.
        result = operation()
        with self.database.transaction() as connection:
            receipt = self._event(connection, "STEP_CONFIRMED", {"round": sequence, "step": name, "result": result})
            connection.execute("UPDATE soak_steps SET status='done',result=?,receipt_sequence=? WHERE round=? AND step=?", (_json(result), receipt, sequence, name))
        return result

    def _matched(self, buy_account, buy_id, sell_account, sell_id, quantity):
        def confirmed():
            with readonly(self.path) as connection:
                matches = [dict(row) for row in connection.execute(
                    "SELECT * FROM uta_matches WHERE buy_account_id=? AND buy_order_id=? AND sell_account_id=? AND sell_order_id=?",
                    (buy_account, buy_id, sell_account, sell_id))]
            total = sum((D(row["quantity"]) for row in matches), D(0))
            if total > quantity:
                raise RuntimeError("round matching obligation overfilled")
            return matches, total
        matches, total = confirmed()
        if total < quantity:
            self.matcher.match_once("BTC-PERP", max_matches=2)
            matches, total = confirmed()
        if total != quantity:
            raise RuntimeError("round awaits real matching liquidity; no synthetic completion")
        return {"trade_ids": [row["trade_id"] for row in matches], "confirmed_quantity": str(total)}

    def roundtrip(self, sequence):
        prefix = f"soak:{sequence}:"
        a, b, symbol = "soak-alice", "soak-bob", "BTC-PERP"
        step = lambda name, operation: self._step(sequence, name, operation)
        if sequence % 10 == 5:
            step("dry-buy", lambda: self.exchange.submit_order(a, prefix + "dry-buy", symbol, D(".02"), D(99)))
            step("dry-sell", lambda: self.exchange.submit_order(b, prefix + "dry-sell", symbol, D("-.02"), D(101)))
            def no_liquidity():
                result = self.matcher.match_once(symbol, 2)
                if result["confirmed_trades"] or result["blocked"]:
                    raise RuntimeError("noncrossing book did not remain unfilled")
                return result
            step("no-liquidity", no_liquidity)
            step("dry-cancel-buy", lambda: self.exchange.cancel_order(a, prefix + "dry-buy"))
            step("dry-cancel-sell", lambda: self.exchange.cancel_order(b, prefix + "dry-sell"))
        quantity = D(".01") if sequence % 10 == 0 else D(".02")
        step("open-buy", lambda: self.exchange.submit_order(a, prefix + "open-buy", symbol, D(".02"), D(100)))
        step("open-sell", lambda: self.exchange.submit_order(b, prefix + "open-sell", symbol, -quantity, D(100)))
        step("open-match", lambda: self._matched(a, prefix + "open-buy", b, prefix + "open-sell", quantity))
        if quantity < D(".02"):
            def cancel_partial():
                order = self.exchange.order(a, prefix + "open-buy")
                if D(order["filled_quantity"]) != quantity:
                    raise RuntimeError("partial fill confirmation is missing")
                return self.exchange.cancel_order(a, prefix + "open-buy")
            step("cancel-partial", cancel_partial)
        step("close-sell", lambda: self.exchange.submit_order(a, prefix + "close-sell", symbol, -quantity, D(100), reduce_only=True))
        step("close-buy", lambda: self.exchange.submit_order(b, prefix + "close-buy", symbol, quantity, D(100), reduce_only=True))
        step("close-match", lambda: self._matched(b, prefix + "close-buy", a, prefix + "close-sell", quantity))
        if sequence % 60 == 0:
            step("borrow", lambda: self.credit.borrow("soak-credit", prefix + "borrow", "BTC", D(".01")))
            step("interest", lambda: self.credit.accrue_interest("soak-credit", prefix + "interest", "BTC", D(".00000001")))
            step("repay", lambda: self.credit.repay("soak-credit", prefix + "repay", "BTC", D(".01000001")))

    def _validate(self, *, full=False):
        began = time.monotonic_ns()
        with readonly(self.path) as connection:
            if schema_digest(connection) != self.meta["schema_digest"]:
                raise RuntimeError("schema changed during soak")
            if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise RuntimeError("SQLite quick_check failed")
            counts = {table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                      for table in ("uta_orders", "uta_fills", "uta_matches", "ledger_events")}
            if counts["uta_fills"] != 2 * counts["uta_matches"]:
                raise RuntimeError("paired fill count does not reconcile")
        if full:
            # Reopen through read-only connections. No constructor/schema repair
            # is allowed to precede the independent accounting replay.
            view = copy.copy(self.exchange)
            view.database = ReadOnlyDatabase(self.database)
            view.ledger = copy.copy(self.exchange.ledger)
            view.ledger.database = view.database
            counts["independent_reconciliation"] = reconcile_exchange(view, matching_only=True)
        with self.database.transaction() as connection:
            self._event(connection, "VERIFIED", {"full": full, "counts": counts,
                "elapsed_ns": time.monotonic_ns() - began, "read_only_reopen": True})
        return counts

    def export(self, segment_size=1000):
        log_directory = self.directory / "logs"
        log_directory.mkdir(exist_ok=True, mode=0o700)
        manifest_path = log_directory / "manifest.json"
        manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"segments": {}}
        while True:
            with self.database.transaction() as connection:
                cursor = int(connection.execute("SELECT value FROM soak_meta WHERE key='export_cursor'").fetchone()[0])
                plan = connection.execute("SELECT * FROM soak_exports WHERE first_sequence=?", (cursor + 1,)).fetchone()
                if plan is None:
                    sequences = [row[0] for row in connection.execute("SELECT sequence FROM soak_evidence WHERE sequence>? ORDER BY sequence LIMIT ?", (cursor, segment_size))]
                    if not sequences:
                        break
                    name = f"events-{sequences[0]:09d}-{sequences[-1]:09d}.jsonl.gz"
                    connection.execute("INSERT INTO soak_exports VALUES (?,?,?,NULL)", (sequences[0], sequences[-1], name))
                    first, last = sequences[0], sequences[-1]
                else:
                    first, last, name = plan["first_sequence"], plan["last_sequence"], plan["filename"]
            with readonly(self.path) as connection:
                rows = [dict(row) for row in connection.execute("SELECT * FROM soak_evidence WHERE sequence BETWEEN ? AND ? ORDER BY sequence", (first, last))]
            if [row["sequence"] for row in rows] != list(range(first, last + 1)):
                raise RuntimeError("durable evidence export range has a gap")
            data = gzip.compress(("\n".join(_json(row) for row in rows) + "\n").encode(), mtime=0)
            path = log_directory / name
            if path.exists() and path.read_bytes() != data:
                raise RuntimeError("existing evidence segment differs from durable source")
            temporary = path.with_name(path.name + ".tmp")
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            manifest["segments"][name] = {"first": rows[0]["sequence"], "last": rows[-1]["sequence"],
                "rows": len(rows), "sha256": sha256(data).hexdigest(), "bytes": len(data)}
            _atomic(manifest_path, manifest)
            with self.database.transaction() as connection:
                connection.execute("UPDATE soak_exports SET digest=? WHERE first_sequence=?", (sha256(data).hexdigest(), first))
                connection.execute("UPDATE soak_meta SET value=? WHERE key='export_cursor'", (str(rows[-1]["sequence"]),))

    def heartbeat(self, status="running"):
        now = time.monotonic_ns()
        delta, self.last_active = now - self.last_active, now
        with self.database.transaction() as connection:
            connection.execute("UPDATE soak_sessions SET heartbeat_ns=?,active_ns=active_ns+? WHERE id=?", (time.time_ns(), delta, self.session))
            connection.execute("UPDATE soak_meta SET value=? WHERE key='status'", (status,))
        report = read_status(self.directory)
        report["rss_max_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        _atomic(self.directory / "progress.json", report)
        with self.database.transaction() as connection:
            self._event(connection, "HEARTBEAT", {"counts": report["counts"],
                "financial_counts": report["financial_counts"], "market_version": report["market_version"],
                "market_age_seconds": report["market_age_seconds"], "directory_bytes": report["directory_bytes"],
                "free_disk_bytes": report["free_disk_bytes"], "rss_max_kib": report["rss_max_kib"],
                "confirmed_active_seconds": report["confirmed_active_seconds"], "status": status})
        size = report["directory_bytes"]
        database_size = _observed_file_bytes(self.directory.glob("authority.sqlite3*"))
        if (size > self.configuration.max_directory_bytes or database_size > self.configuration.max_database_bytes
                or report["free_disk_bytes"] < self.configuration.min_free_bytes):
            raise RuntimeError("disk resource budget exhausted; job incomplete")
        return report

    def audit_logs(self):
        manifest = json.loads((self.directory / "logs/manifest.json").read_text())
        expected = 1
        for name, proof in sorted(manifest["segments"].items()):
            data = (self.directory / "logs" / name).read_bytes()
            if sha256(data).hexdigest() != proof["sha256"] or len(data) != proof["bytes"]:
                raise RuntimeError("exported evidence checksum mismatch")
            sequences = [json.loads(line)["sequence"] for line in gzip.decompress(data).splitlines()]
            if proof["first"] != expected or sequences != list(range(expected, proof["last"] + 1)):
                raise RuntimeError("exported evidence sequence gap or duplicate")
            expected = proof["last"] + 1
        with readonly(self.path) as connection:
            cursor = int(connection.execute("SELECT value FROM soak_meta WHERE key='export_cursor'").fetchone()[0])
            last = connection.execute("SELECT MAX(sequence) FROM soak_evidence").fetchone()[0]
        if expected - 1 != cursor or cursor != last:
            raise RuntimeError("exported evidence does not cover the durable checkpoint")
        return {"rows": cursor, "segments": len(manifest["segments"])}

    def run(self):
        pending = Queue(maxsize=self.configuration.queue_capacity)
        slots = BoundedSemaphore(self.configuration.queue_capacity)
        errors = []
        feed_stop = Event()
        def fail(error):
            errors.append({"type": type(error).__name__, "message": str(error),
                "code": getattr(error, "code", None), "sqlite_errorcode": getattr(error, "sqlite_errorcode", None)})
            self.stop.set()
        def feed():
            try:
                while not feed_stop.wait(self.configuration.feed_interval):
                    self.tick()
            except BaseException as error:
                fail(error)
        def work():
            while True:
                sequence = pending.get()
                if sequence is None:
                    return
                try:
                    # Preserve account/book causality after an unknown earlier
                    # round. Later obligations remain durably queued for an
                    # ordered resume; executing them could consume its book.
                    if errors:
                        continue
                    with self.database.transaction() as connection:
                        connection.execute("UPDATE soak_arrivals SET status='active',started_ns=COALESCE(started_ns,?) WHERE sequence=?", (time.time_ns(), sequence))
                    self.roundtrip(sequence)
                    with self.database.transaction() as connection:
                        completed_ns = time.time_ns()
                        connection.execute("UPDATE soak_arrivals SET status='done',completed_ns=? WHERE sequence=?", (completed_ns, sequence))
                        arrival = dict(connection.execute("SELECT * FROM soak_arrivals WHERE sequence=?", (sequence,)).fetchone())
                        self._event(connection, "ROUND_COMMITTED", {**arrival,
                            "latency_ns": completed_ns - arrival["planned_ns"]})
                    if time.monotonic() - self.last_verify >= self.configuration.verify_interval:
                        self._validate(full=True)
                        self.last_verify = time.monotonic()
                except BaseException as error:
                    try:
                        with self.database.transaction() as connection:
                            connection.execute("UPDATE soak_arrivals SET status='pending',error=? WHERE sequence=?", (str(error), sequence))
                            self._event(connection, "ROUND_UNKNOWN_OR_FAILED", {"round": sequence, "error": str(error)})
                    finally:
                        fail(error)
                finally:
                    slots.release()
        feeder = Thread(target=feed, name="soak-live-market")
        worker = Thread(target=work, name="soak-settlement")
        # Recover accepted obligations first, using their original IDs.
        with readonly(self.path) as connection:
            recovery = [row[0] for row in connection.execute("SELECT sequence FROM soak_arrivals WHERE status IN ('queued','active','pending') ORDER BY sequence")]
            row = connection.execute("SELECT MAX(sequence) FROM soak_arrivals").fetchone()
            next_sequence = row[0] + 1 if row[0] is not None else 0
        self.tick()
        feeder.start()
        worker.start()
        last_heartbeat = last_light = last_export = time.monotonic()
        try:
            for sequence in recovery:
                slots.acquire()
                pending.put(sequence)
            while (time.time_ns() < self.meta["deadline_ns"] or next_sequence < self.meta["planned_rounds"]) and not self.stop.is_set():
                if (self.directory / "STOP").exists():
                    self.stop.set()
                    break
                now = time.time_ns()
                if next_sequence < self.meta["planned_rounds"]:
                    planned = self.meta["started_ns"] + int(next_sequence * 1e9 / self.configuration.rate)
                    if now >= planned:
                        acquired = slots.acquire(blocking=False)
                        state = "queued" if acquired else "overload"
                        # A restart does not fabricate continuous arrivals for
                        # the interval where no generator was running.
                        if (self.resumed and planned < self.resume_at_ns) or now >= self.meta["deadline_ns"]:
                            if acquired:
                                slots.release()
                            acquired, state = False, "missed_downtime" if self.resumed else "missed_deadline"
                        with self.database.transaction() as connection:
                            connection.execute("INSERT INTO soak_arrivals VALUES (?,?,?,NULL,?,NULL)",
                                (next_sequence, planned, state, None if acquired else now))
                            self._event(connection, "ARRIVAL", {"round": next_sequence, "planned_ns": planned, "observed_ns": now, "outcome": state, "queue": pending.qsize()})
                        if acquired:
                            pending.put_nowait(next_sequence)
                        next_sequence += 1
                        continue
                if time.monotonic() - last_heartbeat >= self.configuration.heartbeat_interval:
                    self.heartbeat()
                    last_heartbeat = time.monotonic()
                if time.monotonic() - last_export >= self.configuration.export_interval:
                    self.export()
                    last_export = time.monotonic()
                if time.monotonic() - last_light >= 60:
                    self._validate()
                    last_light = time.monotonic()
                self.stop.wait(.05)
        except BaseException as error:
            fail(error)
        finally:
            pending.put(None)
            worker.join()
            self.stop.set()
            feed_stop.set()
            feeder.join()
        status = "failed" if errors else ("paused" if time.time_ns() < self.meta["deadline_ns"] else "completed")
        try:
            self._validate(full=True)
            self.heartbeat(status)
        except BaseException as error:
            errors.append({"type": type(error).__name__, "message": str(error)})
            status = "failed"
        with self.database.transaction() as connection:
            connection.execute("UPDATE soak_sessions SET ended_ns=?,status=? WHERE id=?", (time.time_ns(), status, self.session))
            connection.execute("UPDATE soak_meta SET value=? WHERE key='status'", (status,))
            self._event(connection, "SESSION_ENDED", {"session": self.session, "status": status, "errors": errors})
        self.export()
        try:
            self.audit_logs()
            with self.database.transaction() as connection:
                connection.execute("UPDATE soak_meta SET value='true' WHERE key='logs_verified'")
        except BaseException as error:
            errors.append({"type": type(error).__name__, "message": str(error)})
            with self.database.transaction() as connection:
                connection.execute("UPDATE soak_meta SET value='failed' WHERE key='status'")
        report = read_status(self.directory)
        report["errors"] = errors
        _atomic(self.directory / "progress.json", report)
        self.close()
        return report

    def close(self):
        if getattr(self, "lock", None) is not None:
            os.close(self.lock)
            self.lock = None


def read_status(directory):
    directory = Path(directory)
    meta = json.loads((directory / "job.json").read_text())
    with readonly(directory / "authority.sqlite3") as connection:
        counts = dict(connection.execute("SELECT status,COUNT(*) FROM soak_arrivals GROUP BY status"))
        sessions = [dict(row) for row in connection.execute("SELECT * FROM soak_sessions ORDER BY started_ns")]
        status = connection.execute("SELECT value FROM soak_meta WHERE key='status'").fetchone()[0]
        logs_verified = connection.execute("SELECT value FROM soak_meta WHERE key='logs_verified'").fetchone()[0] == "true"
        market = json.loads(connection.execute("SELECT payload FROM uta_market WHERE singleton=1").fetchone()[0])
        totals = {table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                  for table in ("uta_orders", "uta_fills", "uta_matches", "ledger_events", "soak_evidence")}
        totals["cancelled_orders"] = connection.execute("SELECT COUNT(*) FROM uta_orders WHERE status='CANCELLED'").fetchone()[0]
        totals["partial_cancelled_orders"] = sum(D(row[0]) != 0 for row in connection.execute("SELECT filled_quantity FROM uta_orders WHERE status='CANCELLED'"))
        totals["live_orders"] = connection.execute("SELECT COUNT(*) FROM uta_orders WHERE status IN ('OPEN','PARTIALLY_FILLED')").fetchone()[0]
        totals["positions"] = connection.execute("SELECT COUNT(*) FROM uta_positions").fetchone()[0]
        totals["credit_commands"] = dict(connection.execute("SELECT kind,COUNT(*) FROM credit_commands GROUP BY kind"))
        done_sequences = [row[0] for row in connection.execute("SELECT sequence FROM soak_arrivals WHERE status='done'")]
        golden = {"matches": 2 * len(done_sequences), "fill_legs": 4 * len(done_sequences),
            "orders": 4 * len(done_sequences) + 2 * sum(sequence % 10 == 5 for sequence in done_sequences),
            "cancelled_orders": sum(sequence % 10 == 0 for sequence in done_sequences) + 2 * sum(sequence % 10 == 5 for sequence in done_sequences),
            "partial_cancelled_orders": sum(sequence % 10 == 0 for sequence in done_sequences),
            "borrow_interest_repay_cycles": sum(sequence % 60 == 0 for sequence in done_sequences)}
        histogram = LatencyHistogram()
        for row in connection.execute("SELECT planned_ns,completed_ns FROM soak_arrivals WHERE status='done'"):
            histogram.observe(max(0, row["completed_ns"] - row["planned_ns"]))
    active = sum(row["active_ns"] for row in sessions)
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(market["observed_at"])).total_seconds()
    stored_status = status
    latest = sessions[-1] if sessions else None
    alive = bool(latest and latest["process_identity"] is not None and _pid_identity(latest["pid"]) == latest["process_identity"])
    heartbeat_age = (time.time_ns() - latest["heartbeat_ns"]) / 1e9 if latest else None
    if status in ("running", "initialized") and not alive:
        status = "interrupted_pending"
    elif status == "running" and heartbeat_age > max(30, 3 * meta["configuration"]["heartbeat_interval"]):
        status = "stalled_pending"
    golden_ok = (totals["uta_matches"] == golden["matches"] and totals["uta_fills"] == golden["fill_legs"]
                 and totals["uta_orders"] == golden["orders"] and totals["cancelled_orders"] == golden["cancelled_orders"]
                 and totals["partial_cancelled_orders"] == golden["partial_cancelled_orders"]
                 and totals["live_orders"] == 0 and totals["positions"] == 0
                 and all(totals["credit_commands"].get(kind, 0) == golden["borrow_interest_repay_cycles"]
                         for kind in ("borrowed", "interest_accrued", "repaid")))
    workload_completed = status == "completed" and counts == {"done": meta["planned_rounds"]} and golden_ok and logs_verified
    passed = (workload_completed and meta["configuration"]["duration"] >= 86400
              and active >= int(meta["configuration"]["duration"] * 1e9)
              and len(sessions) == 1 and sessions[0]["status"] == "completed")
    return {"status": status, "stored_status": stored_status, "process_alive": alive,
        "heartbeat_age_seconds": heartbeat_age, "source_commit": meta["environment"]["commit"], "started_utc": meta["started_utc"],
        "original_started_ns": meta["started_ns"], "deadline_ns": meta["deadline_ns"], "observed_ns": time.time_ns(),
        "planned_rounds": meta["planned_rounds"], "counts": counts, "financial_counts": totals,
        "golden_for_completed_rounds": golden,
        "completed_round_golden_matches_financial_state": golden_ok,
        "logs_verified": logs_verified, "configured_workload_completed": workload_completed,
        "sessions": sessions, "confirmed_active_seconds": active / 1e9,
        "wall_seconds_since_original_start": (time.time_ns() - meta["started_ns"]) / 1e9,
        "market_version": market["version"], "market_age_seconds": age,
        "roundtrip_latency_ms": histogram.report(),
        "directory_bytes": _observed_file_bytes(directory.rglob("*")),
        "free_disk_bytes": shutil.disk_usage(directory).free,
        "stability_target_passed": passed, "production_approved": False,
        "capacity_10000_per_s_passed": False, "cohosted": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "resume", "status", "stop"))
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--duration", type=float, default=86400)
    parser.add_argument("--rate", type=float, default=.25)
    args = parser.parse_args(argv)
    try:
        if args.action == "status":
            print(json.dumps(read_status(args.directory), indent=2))
            return 0
        if args.action == "stop":
            if not (args.directory / "job.json").exists():
                raise ValueError("not an initialized soak job")
            (args.directory / "STOP").touch(mode=0o600)
            return 0
        job = Soak(args.directory, Configuration(duration=args.duration, rate=args.rate) if args.action == "start" else None,
                   resume=args.action == "resume")
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda signum, frame: job.stop.set())
        report = job.run()
        print(json.dumps(report, indent=2))
        return 0 if report["status"] == "completed" else 2
    except (ValueError, RuntimeError, OSError, sqlite3.Error) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
