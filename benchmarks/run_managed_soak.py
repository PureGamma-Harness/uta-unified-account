"""Low-rate managed process/TLS/HMAC stability probe; no capacity qualification.

Checkpoint commits and financial commits are separate. Original command IDs are
queried before retrying; an unresolved step stops every later round.
"""
from __future__ import annotations

import argparse
import base64
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import fcntl
from fractions import Fraction
import gzip
from hashlib import sha256
from http.client import HTTPException, HTTPSConnection
import json
import math
import os
from pathlib import Path
import re
import secrets
import select
import shutil
import signal
import sqlite3
import ssl
import stat
import subprocess
import sys
from threading import Event
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks.run_soak import _atomic, _pid_identity, environment, readonly
from benchmarks.run_benchmark import LatencyHistogram
from benchmarks.managed_qualification import qualify
from uta.durable_process import DurableProcessRouter
from uta.examples import synthetic_policy
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.request_signing import load_profile, sign_headers
from uta.storage import Database

ACCOUNTS = ("managed-soak-alice", "managed-soak-bob", "managed-soak-credit")
_RESOURCE_DATABASES = ("checkpoint.sqlite3", "managed/router.sqlite3",
                       "managed/shard-0000.sqlite3", "private/auth.sqlite3")
_RESOURCE_TRANSIENTS = {name + suffix for name in _RESOURCE_DATABASES for suffix in ("-wal", "-shm")} | {
    "bootstrap-plan.json.tmp", "job.json.tmp", "progress.json.tmp", "pending-market.json.tmp",
    "log-segments.json.tmp", "private/signing.json.tmp"}
SCALE = 100_000_000
def require_long_run_ready(duration, *, allow_long_run=False, strict_source=True, validation_report=None):
    if duration > 60:
        if allow_long_run is not True or strict_source is not True:
            raise RuntimeError("managed long run requires explicit --allow-long-run and frozen clean source")
        if validation_report is None:
            raise RuntimeError("managed release validation required: supply the exact complete validation report")
    return None if validation_report is None else qualify(validation_report)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _verify_archive_content(connection):
    """Independent exact-byte JSON/content-ID checks, never execute or replay."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    def nonfinite(_):
        raise ValueError("nonfinite JSON value")
    for label, table, identity, content, prefix in (
            ("market", "uta_market_history", "snapshot_id", "payload", "market:"),
            ("artifact", "uta_code_artifacts", "artifact_id", "manifest", "artifact:"),
            ("policy", "uta_risk_policies", "policy_id", "payload", "policy:")):
        seen = set()
        for row in connection.execute(f"SELECT * FROM {table}"):
            key, raw = row[identity], row[content]
            if key in seen:
                raise RuntimeError("ambiguous archived " + label + " content identity")
            seen.add(key)
            try:
                value = json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)
                if not isinstance(raw, str) or not isinstance(value, dict) or canonical(value) != raw:
                    raise ValueError("canonical JSON object required")
            except (ValueError, TypeError, RecursionError) as error:
                raise RuntimeError("archived " + label + " canonical JSON is invalid") from error
            digest = sha256(raw.encode("utf-8")).hexdigest()
            if key != prefix + digest or label == "market" and row["content_digest"] != digest:
                raise RuntimeError("archived " + label + " content digest mismatch")


def snapshot(version):
    return MarketSnapshot(version, datetime.now(timezone.utc),
        {"USD": AssetSpec(D(1), D(1)), "BTC": AssetSpec(D(100), D(".8"))},
        {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))})


def bootstrap(directory, rounds, source_reference):
    """Explicit synthetic offline writer process, followed by managed sealing."""
    catalog, rules = synthetic_policy()
    def seed(router):
        for account in ACCOUNTS:
            router.create_account(account)
            router.deposit(account, "synthetic-initial-usd", "USD", D(1_000_000))
        router.deposit(ACCOUNTS[2], "synthetic-initial-btc", "BTC", D(1))
        router.publish_market(snapshot(1))
        router.set_kill_switch(False)
        router.configure_credit_limit(ACCOUNTS[2], "BTC", D(1))
        router.configure_credit_asset_limit(0, "BTC", D(1))
        router.fund_credit_pool(0, "synthetic-initial-pool", "BTC", D(1), source_reference=source_reference)
        principal = D(2 * rounds) / D(SCALE)
        router.borrow(ACCOUNTS[2], "synthetic-initial-loan", "BTC", principal)
    router = DurableProcessRouter.initialize(directory, 1, {"USD": 8, "BTC": 8},
        managed=True, decision_audit=True, bootstrap=seed, product_catalog=catalog,
        portfolio_rules=rules, max_price_age=timedelta(seconds=30), queue_capacity=32,
        cancel_reserve=8, market_capacity=4)
    try:
        return {"managed": True, "decision_audit_required": router.decision_audit_required,
                "source_reference": source_reference, "initial_principal_satoshi": 2 * rounds,
                "synthetic_only": True, "custody_backing_verified": False}
    finally:
        router.close()


@dataclass(frozen=True)
class Configuration:
    duration: float = 60
    rate: float = .25
    command_timeout: float = 15
    heartbeat_interval: float = 5
    export_interval: float = 60
    worker_every: int = 30
    parent_every: int = 300
    min_free_bytes: int = 1024**3
    max_directory_bytes: int = 6 * 1024**3

    @property
    def rounds(self):
        return math.ceil(self.duration * self.rate)

    def validate(self):
        for name in ("duration", "rate", "command_timeout", "heartbeat_interval", "export_interval"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if not 4 <= self.duration <= 86400 or self.rate != .25:
            raise ValueError("managed soak requires 4..86400 seconds and fixed 0.25 rounds/s")
        if not 1 <= self.command_timeout <= 60 or not .25 <= self.heartbeat_interval <= 60 or not 1 <= self.export_interval <= 3600:
            raise ValueError("bounded command, heartbeat and export intervals required")
        for name in ("worker_every", "parent_every"):
            if type(getattr(self, name)) is not int or not 0 <= getattr(self, name) <= 100000:
                raise ValueError("fault intervals must be bounded nonnegative integers")
        if type(self.min_free_bytes) is not int or self.min_free_bytes < 0 or type(self.max_directory_bytes) is not int or self.max_directory_bytes < 1024**2:
            raise ValueError("invalid disk budgets")


def alive(pid, identity):
    if not pid or _pid_identity(pid) != identity:
        return False
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return False


class ManagedSoak:
    def __init__(self, directory, configuration=None, *, resume=False, strict_source=True,
                 allow_long_run=False, validation_report=None):
        self.directory = Path(directory).absolute()
        if self.directory.is_symlink():
            raise ValueError("job directory must not be a symlink")
        if resume:
            persisted = json.loads((self.directory / "job.json").read_text())
            original_configuration = persisted["configuration"]
            if configuration is not None and asdict(configuration) != original_configuration:
                raise RuntimeError("resume cannot change workload or duration")
            requested = Configuration(**original_configuration)
            if validation_report is None and persisted.get("validation_evidence") is not None:
                validation_report = self.directory / "validation" / "summary.json"
        else:
            requested = configuration or Configuration()
        requested.validate()
        self.validation = require_long_run_ready(requested.duration, allow_long_run=allow_long_run,
            strict_source=strict_source, validation_report=validation_report)
        if resume and persisted.get("validation_evidence") != (None if self.validation is None else self.validation.evidence):
            raise RuntimeError("resume validation evidence differs from the original frozen candidate")
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.directory.stat().st_uid != os.geteuid() or self.directory.stat().st_mode & 0o077:
            raise ValueError("job directory must be private")
        self.lock = os.open(self.directory / "run.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            os.close(self.lock)
            self.lock = None
            raise RuntimeError("another managed soak controller owns this job")
        self.stop = Event()
        self.process = None
        self.listener = None
        self.stderr = None
        self.strict_source = strict_source
        self.configuration = requested
        self.configuration.validate()
        self.authority = self.directory / "managed"
        self.financial = self.authority / "shard-0000.sqlite3"
        self.secrets = self.directory / "private"
        self.checkpoint = Database(self.directory / "checkpoint.sqlite3", timeout=2)
        self.env = environment()
        self.env["source_sha256"]["benchmarks/run_managed_soak.py"] = sha256(Path(__file__).read_bytes()).hexdigest()
        self.env["source_sha256"]["benchmarks/run_benchmark.py"] = sha256((ROOT / "benchmarks/run_benchmark.py").read_bytes()).hexdigest()
        for relative in ("benchmarks/managed_qualification.py", "tools/run_validation.py"):
            self.env["source_sha256"][relative] = sha256((ROOT / relative).read_bytes()).hexdigest()
        self.env["workload_spec_sha256"] = sha256((ROOT / "docs/managed-soak-golden.md").read_bytes()).hexdigest()
        try:
            if strict_source and self.env["tracked_changes"]:
                raise RuntimeError("managed soak requires a clean frozen source checkout")
            self._assert_source()
            if resume:
                self.meta = json.loads((self.directory / "job.json").read_text())
                if configuration is not None and asdict(configuration) != self.meta["configuration"]:
                    raise RuntimeError("resume cannot change workload or duration")
                self.configuration = Configuration(**self.meta["configuration"])
                if strict_source and any(self.env[key] != self.meta["environment"][key] for key in ("commit", "source_sha256", "workload_spec_sha256")):
                    raise RuntimeError("resume source differs from the frozen candidate")
                for path, original in self.meta["file_identities"].items():
                    stat = Path(path).stat()
                    if [stat.st_dev, stat.st_ino] != original:
                        raise RuntimeError("original authority/authentication file is missing or replaced")
                if not Path(self.checkpoint.path).exists():
                    raise RuntimeError("checkpoint is missing; original command IDs must not be reconstructed")
            else:
                if (self.directory / "job.json").exists() or self.authority.exists() or Path(self.checkpoint.path).exists():
                    raise RuntimeError("existing state requires explicit resume; never reset history")
                self._initialize()
            self.profile = load_profile(self.secrets / "signing.json")
            self.tls = ssl.create_default_context(cafile=self.secrets / "cert.pem")
            self.tls.minimum_version = ssl.TLSVersion.TLSv1_2
            if self.tls.verify_mode != ssl.CERT_REQUIRED or not self.tls.check_hostname:
                raise RuntimeError("native verified TLS is required")
            self._event("CONTROLLER_STARTED", {"pid": os.getpid(), "resumed": resume})
            # A dead controller may have left its CLI coordinator alive. Stop
            # only the recorded PID/starttime before starting another owner.
            if resume:
                self._stop_server()
        except BaseException:
            self.close()
            raise

    def _initialize(self):
        if self.validation is not None:
            self.validation.record(self.directory / "validation")
        self.secrets.mkdir(mode=0o700)
        job_id = secrets.token_hex(12)
        proof = "synthetic-managed-soak:" + job_id
        _atomic(self.directory / "bootstrap-plan.json", {"job_id": job_id, "source_reference": proof,
            "configuration": asdict(self.configuration), "environment": self.env,
            "initial_principal_satoshi": 2 * self.configuration.rounds,
            "initialization_is_offline_before_sealing": True})
        seeded = subprocess.run([sys.executable, "-m", "benchmarks.run_managed_soak", "bootstrap",
            "--directory", str(self.authority), "--rounds", str(self.configuration.rounds),
            "--source-reference", proof], cwd=ROOT, text=True, capture_output=True, timeout=30)
        if seeded.returncode:
            raise RuntimeError("offline synthetic bootstrap failed: " + seeded.stderr[-2000:])
        provenance = json.loads(seeded.stdout)
        self._cli("auth-init", "--auth-db", self.secrets / "auth.sqlite3", "--tenant", "synthetic-managed-soak", "--max-nonces", "10000")
        with readonly(self.secrets / "auth.sqlite3") as connection:
            audience = connection.execute("SELECT audience FROM auth_config").fetchone()[0]
        now = time.time_ns() // 1000000
        keys = []
        for key_id, role, account in (("operator", "admin", None), ("alice", "trader", ACCOUNTS[0]),
                                      ("bob", "trader", ACCOUNTS[1]), ("credit", "funding", ACCOUNTS[2])):
            keys.append({"key_id": key_id, "role": role, "account_id": account,
                "secret_b64": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("="),
                "not_before_ms": now - 10000, "expires_at_ms": now + 7 * 86400000, "revoked": False})
        _atomic(self.secrets / "signing.json", {"format": 1, "tenant_id": "synthetic-managed-soak",
            "audience": audience, "revision": 1, "keys": keys})
        self._cli("auth-configure", "--auth-db", self.secrets / "auth.sqlite3", "--signing-profile", self.secrets / "signing.json")
        executable = shutil.which("openssl")
        if executable is None:
            raise RuntimeError("openssl is required for a runtime-private synthetic certificate")
        issued = subprocess.run([executable, "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-keyout", str(self.secrets / "key.pem"), "-out", str(self.secrets / "cert.pem"),
            "-days", "7", "-subj", "/CN=127.0.0.1", "-addext", "subjectAltName=IP:127.0.0.1"], capture_output=True, text=True, timeout=15)
        if issued.returncode:
            raise RuntimeError("synthetic TLS certificate generation failed")
        for name in ("key.pem", "cert.pem"):
            (self.secrets / name).chmod(0o600)
        with self.checkpoint.transaction() as connection:
            connection.execute("CREATE TABLE state(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
            connection.execute("CREATE TABLE rounds(sequence INTEGER PRIMARY KEY,planned_ns INTEGER NOT NULL,state TEXT NOT NULL,completed_ns INTEGER)")
            connection.execute("CREATE TABLE steps(round INTEGER NOT NULL,name TEXT NOT NULL,plan TEXT NOT NULL,state TEXT NOT NULL,receipt TEXT,PRIMARY KEY(round,name))")
            connection.execute("CREATE TABLE faults(round INTEGER NOT NULL,kind TEXT NOT NULL,state TEXT NOT NULL,evidence TEXT NOT NULL,PRIMARY KEY(round,kind))")
            connection.execute("CREATE TABLE events(sequence INTEGER PRIMARY KEY,kind TEXT NOT NULL,payload TEXT NOT NULL,previous_hash TEXT NOT NULL,event_hash TEXT NOT NULL)")
            connection.execute("CREATE TRIGGER event_no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT,'immutable event'); END")
            connection.execute("CREATE TRIGGER event_no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT,'immutable event'); END")
        files = [self.financial, self.authority / "router.sqlite3", self.secrets / "auth.sqlite3", Path(self.checkpoint.path)]
        self.meta = {"format": 1, "job_id": job_id, "configuration": asdict(self.configuration), "environment": self.env,
            "validation_evidence": None if self.validation is None else self.validation.evidence,
            "bootstrap": provenance, "accounts": ACCOUNTS, "planned_rounds": self.configuration.rounds,
            "file_identities": {str(path): [path.stat().st_dev, path.stat().st_ino] for path in files},
            "cross_database_atomicity": False, "production_approved": False, "capacity_10000_per_s_passed": False}
        _atomic(self.directory / "job.json", self.meta)
        self._event("INITIALIZED", {"provenance": provenance, "real_tls_hmac": True})

    def _cli(self, command, *options, allowed=(0,)):
        self._assert_source()
        result = subprocess.run([sys.executable, "-m", "uta.durable_cli", command, "--directory", str(self.authority),
            *map(str, options)], cwd=ROOT, text=True, capture_output=True, timeout=self.configuration.command_timeout + 5)
        if result.returncode not in allowed:
            raise RuntimeError(f"CLI {command} failed ({result.returncode}): {result.stderr[-1500:] or result.stdout[-1500:]}")
        return json.loads(result.stdout)

    def _assert_source(self):
        if not self.strict_source:
            return
        if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() != self.env["commit"]:
            raise RuntimeError("frozen source commit changed during managed soak")
        if subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=all"], cwd=ROOT, text=True).strip():
            raise RuntimeError("frozen source checkout is no longer clean")
        tracked = subprocess.run(["git", "ls-files", "--error-unmatch", *self.env["source_sha256"], "docs/managed-soak-golden.md"], cwd=ROOT, capture_output=True)
        if tracked.returncode:
            raise RuntimeError("frozen runtime and workload files must belong to the recorded commit")
        for relative, digest in self.env["source_sha256"].items():
            if sha256((ROOT / relative).read_bytes()).hexdigest() != digest:
                raise RuntimeError("frozen source bytes changed during managed soak")
        if sha256((ROOT / "docs/managed-soak-golden.md").read_bytes()).hexdigest() != self.env["workload_spec_sha256"]:
            raise RuntimeError("frozen workload specification changed")
        if self.validation is not None and hasattr(self, "meta"):
            self._assert_validation_evidence()

    def _assert_validation_evidence(self):
        if self.validation is None:
            return
        for name, expected in self.validation.evidence["artifact_sha256"].items():
            if sha256((self.directory / "validation" / name).read_bytes()).hexdigest() != expected:
                raise RuntimeError("frozen release validation evidence changed during managed soak")

    @staticmethod
    def _append_event(connection, kind, payload):
        payload = canonical({"at_ns": time.time_ns(), **payload})
        previous = connection.execute("SELECT sequence,event_hash FROM events ORDER BY sequence DESC LIMIT 1").fetchone()
        sequence, digest = (1, "0" * 64) if previous is None else (previous[0] + 1, previous[1])
        fingerprint = sha256(canonical([sequence, kind, payload, digest]).encode()).hexdigest()
        connection.execute("INSERT INTO events VALUES(?,?,?,?,?)", (sequence, kind, payload, digest, fingerprint))

    def _event(self, kind, payload):
        with self.checkpoint.transaction() as connection:
            self._append_event(connection, kind, payload)

    def _state(self, key, value=None):
        with self.checkpoint.transaction() as connection:
            if value is not None:
                connection.execute("INSERT INTO state VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, canonical(value)))
            row = connection.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
            return None if row is None else json.loads(row[0])

    def _start_server(self):
        self._assert_source()
        options = ["--auth-db", str(self.secrets / "auth.sqlite3"), "--signing-profile", str(self.secrets / "signing.json"),
            "--tls-cert", str(self.secrets / "cert.pem"), "--tls-key", str(self.secrets / "key.pem"),
            "--port", "0", "--lease-seconds", ".8", "--poll-interval", ".05",
            "--background-interval", ".2", "--max-attempts", "100", "--request-timeout", "2"]
        self.stderr = (self.directory / "cli.stderr.log").open("ab", buffering=0)
        self.process = subprocess.Popen([sys.executable, "-m", "uta.durable_cli", "serve", "--directory", str(self.authority), *options],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=self.stderr, text=True)
        record = {"pid": self.process.pid, "birth": _pid_identity(self.process.pid), "port": None}
        self._state("listener", record)
        if not select.select([self.process.stdout], [], [], self.configuration.command_timeout)[0]:
            raise RuntimeError("managed CLI listener startup timed out")
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError("managed CLI exited before listener startup; inspect private cli.stderr.log")
        report = json.loads(line)
        if (report.get("event"), report.get("profile"), report.get("tls"), report.get("decision_audit_required")) != ("listening", "hmac-tls", True, True):
            raise RuntimeError("CLI did not start required-audit native TLS/HMAC")
        record["port"] = report["port"]
        self.listener = self._state("listener", record)
        health = self._wait(lambda: self._health_ready(), "worker readiness")
        self._event("CLI_READY", {**record, "workers": health["workers"]})

    def _stop_server(self, *, hard=False):
        record = self.listener or self._state("listener")
        forced = False
        if record and alive(record["pid"], record["birth"]):
            os.kill(record["pid"], signal.SIGKILL if hard else signal.SIGTERM)
            deadline = time.monotonic() + self.configuration.command_timeout
            while alive(record["pid"], record["birth"]) and time.monotonic() < deadline:
                time.sleep(.03)
            if alive(record["pid"], record["birth"]):
                os.kill(record["pid"], signal.SIGKILL)
                forced = True
        if self.process is not None:
            self.process.wait(timeout=5)
            self.process.stdout.close()
            self.process = None
        if self.stderr is not None:
            self.stderr.close()
            self.stderr = None
        self.listener = None
        if forced:
            raise RuntimeError("CLI graceful shutdown exceeded its budget")

    def _request(self, method, target, payload=None, *, key="operator"):
        body = b"" if payload is None else canonical(payload).encode()
        headers = sign_headers(self.profile, key, timestamp_ms=time.time_ns() // 1000000,
            nonce=secrets.token_urlsafe(24), method=method, request_target=target, body=body)
        connection = HTTPSConnection("127.0.0.1", self.listener["port"], context=self.tls, timeout=3)
        try:
            connection.request(method, target, body=body, headers={"Content-Type": "application/json", **headers})
            if connection.sock is None or not connection.sock.getpeercert():
                raise RuntimeError("TLS peer was not verified")
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()
            with self.checkpoint.transaction() as checkpoint:
                row = checkpoint.execute("SELECT value FROM state WHERE key='http_attempts'").fetchone()
                count = 0 if row is None else json.loads(row[0])
                checkpoint.execute("INSERT INTO state VALUES('http_attempts',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (canonical(count + 1),))

    def _health_ready(self):
        try:
            code, report = self._request("GET", "/v2/worker-health")
            return report if code == 200 and report.get("workers") and all(
                item["lease_active"] and item.get("pid") is not None and item["pid"] == item.get("owner_pid")
                for item in report["workers"]) else None
        except (OSError, ValueError, HTTPException):
            return None

    def _wait(self, predicate, reason):
        deadline = time.monotonic() + self.configuration.command_timeout
        while time.monotonic() < deadline:
            result = predicate()
            if result:
                return result
            time.sleep(.05)
        raise TimeoutError(reason + " unresolved; retain original IDs and resume")

    def _plan(self, sequence, name, plan):
        encoded = canonical(plan)
        with self.checkpoint.transaction() as connection:
            previous = connection.execute("SELECT plan,state,receipt FROM steps WHERE round=? AND name=?", (sequence, name)).fetchone()
            if previous is None:
                connection.execute("INSERT INTO steps VALUES(?,?,?,'PLANNED',NULL)", (sequence, name, encoded))
                self._append_event(connection, "STEP_PLANNED", {"round": sequence, "step": name, "plan": plan})
                return "PLANNED", None
            if previous[0] != encoded:
                raise RuntimeError("checkpoint payload/ID differs; never replace an unknown command")
            return previous[1], None if previous[2] is None else json.loads(previous[2])

    def _done(self, sequence, name, receipt):
        with self.checkpoint.transaction() as connection:
            previous = connection.execute("SELECT state,receipt FROM steps WHERE round=? AND name=?", (sequence, name)).fetchone()
            if previous is None:
                raise RuntimeError("a checkpoint confirmation needs its persisted original intent")
            if previous[0] == "DONE":
                if previous[1] != canonical(receipt):
                    raise RuntimeError("checkpoint confirmation cannot change an immutable receipt")
                return
            connection.execute("UPDATE steps SET state='DONE',receipt=? WHERE round=? AND name=?", (canonical(receipt), sequence, name))
            self._append_event(connection, "STEP_CONFIRMED", {"round": sequence, "step": name, "receipt": receipt})

    def _control_state(self):
        with readonly(self.authority / "router.sqlite3") as connection:
            return json.loads(connection.execute("SELECT payload FROM router_state WHERE singleton=1").fetchone()[0])

    def _settle_previous_controls(self, state):
        for field in ("durable_market_commands", "durable_halt_commands"):
            for shard, command_id in state.get(field, {}).items():
                def query():
                    receipt = self._cli("query", "--command-id", command_id, "--shard", shard, allowed=(0, 4))
                    if receipt.get("state") in ("REJECTED", "QUARANTINED"):
                        raise RuntimeError("previous control reached an unsuccessful terminal receipt")
                    return receipt if receipt.get("state") == "SUCCEEDED" else None
                self._wait(query, "original control " + command_id)

    def publish(self, sequence):
        # A full snapshot is checkpointed once. Retry cannot freshen its time.
        with self.checkpoint.read_transaction() as connection:
            previous = connection.execute("SELECT plan,state FROM steps WHERE round=? AND name='feed'", (sequence,)).fetchone()
        if previous is None:
            state = self._control_state()
            quote = snapshot(max(state.get("market_version") or 0, state.get("target_version") or 0) + 1)
            plan = {"snapshot": json.loads(quote.to_json())}
        else:
            plan = json.loads(previous[0])
        status, _ = self._plan(sequence, "feed", plan)
        if status == "DONE":
            return
        payload = canonical(plan["snapshot"])
        digest = sha256(payload.encode()).hexdigest()
        quote_file = self.directory / "pending-market.json"
        _atomic(quote_file, plan["snapshot"])
        state = self._control_state()
        complete = not state["publishing"] and state.get("market_version") == plan["snapshot"]["version"] and state.get("market_digest") == digest
        if not complete:
            try:
                report = self._cli("publish", "--snapshot-file", quote_file, "--timeout", self.configuration.command_timeout, allowed=(0, 3))
            except (OSError, subprocess.TimeoutExpired, RuntimeError):
                state = self._control_state()
                self._event("CONTROL_OUTCOME_UNKNOWN", {"round": sequence, "snapshot_version": plan["snapshot"]["version"]})
                self._settle_previous_controls(state)
                report = state
            state = self._control_state()
            if state["publishing"]:
                # The router protocol reuses its exact persisted market IDs.
                report = self._cli("publish", "--snapshot-file", quote_file, "--timeout", self.configuration.command_timeout, allowed=(0, 3))
                state = self._control_state()
            if state["publishing"] or state.get("market_digest") != digest:
                raise RuntimeError("original fresh-feed publication unresolved")
        self._settle_previous_controls(state)
        if state["halted"]:
            try:
                self._cli("activate", "--timeout", self.configuration.command_timeout, allowed=(0, 3))
            except (OSError, subprocess.TimeoutExpired, RuntimeError):
                original = self._control_state()
                self._settle_previous_controls(original)
                if self._control_state()["halted"]:
                    # A new activation is allowed only after every prior ID is
                    # confirmed terminal; no unknown action is skipped.
                    self._event("ACTIVATION_RETRY_AFTER_QUERY", {"round": sequence, "original_ids": original.get("durable_halt_commands", {})})
                    self._cli("activate", "--timeout", self.configuration.command_timeout)
        state = self._control_state()
        if state["halted"] or state["publishing"] or state.get("market_digest") != digest:
            raise RuntimeError("fresh feed did not reach a complete active barrier")
        self._done(sequence, "feed", {"version": plan["snapshot"]["version"], "digest": digest,
            "observed_at": plan["snapshot"]["observed_at"], "committed_ns": time.time_ns(),
            "market_ids": state.get("durable_market_commands", {}), "activation_ids": state.get("durable_halt_commands", {})})

    def _fault(self, sequence, kind):
        with self.checkpoint.read_transaction() as connection:
            previous = connection.execute("SELECT state,evidence FROM faults WHERE round=? AND kind=?", (sequence, kind)).fetchone()
        if previous is not None and previous[0] == "DONE":
            return
        before = self._health_ready()
        if not before:
            raise RuntimeError("cannot identify a current worker before fault injection")
        worker = before["workers"][0]
        target = (self.listener if kind == "parent" else {"pid": worker["pid"], "birth": _pid_identity(worker["pid"])})
        if previous is not None:
            evidence = json.loads(previous[1])
            target = evidence["target"]
        else:
            evidence = {"target": target, "old_generation": worker["generation"], "signal": "SIGKILL"}
            with self.checkpoint.transaction() as connection:
                connection.execute("INSERT INTO faults VALUES(?,?,'PLANNED',?)", (sequence, kind, canonical(evidence)))
                self._append_event(connection, "FAULT_PLANNED", {"round": sequence, "kind": kind, **evidence})
        if target["pid"] in (None, os.getpid()) or not target["birth"]:
            raise RuntimeError("fault target PID identity is unsafe")
        sent = False
        if alive(target["pid"], target["birth"]):
            os.kill(target["pid"], signal.SIGKILL)
            sent = True
        if kind == "parent" and self.listener and self.listener["pid"] == target["pid"]:
            if self.process is not None:
                self.process.wait(timeout=5)
                self.process.stdout.close()
                self.process = None
            if self.stderr is not None:
                self.stderr.close()
                self.stderr = None
            self.listener = None
            self._start_server()  # Real persisted orphan/fencing recovery.
        def recovered():
            report = self._health_ready()
            return report if report and report["workers"][0]["generation"] > evidence["old_generation"] else None
        recovered_state = self._wait(recovered, "new fencing generation after " + kind + " fault")
        evidence.update(signal_sent=sent, new_generation=recovered_state["workers"][0]["generation"], recovered_ns=time.time_ns())
        with self.checkpoint.transaction() as connection:
            connection.execute("UPDATE faults SET state='DONE',evidence=? WHERE round=? AND kind=?", (canonical(evidence), sequence, kind))
            self._append_event(connection, "FAULT_RECOVERED", {"round": sequence, "kind": kind, **evidence})

    def command(self, sequence, name, account, path, payload, key):
        plan = {"method": "POST", "path": path, "payload": payload, "account": account, "key_id": key,
                "payload_sha256": sha256(canonical(payload).encode()).hexdigest()}
        previous, stored = self._plan(sequence, name, plan)
        target = f"/v2/accounts/{account}/commands/{payload['command_id']}"
        deadline = time.monotonic() + self.configuration.command_timeout
        injected = False
        while time.monotonic() < deadline:
            try:
                code, receipt = self._request("GET", target, key=key)
                if code == 404:
                    if previous == "DONE":
                        raise RuntimeError("checkpoint terminal receipt disappeared from financial storage")
                    code, receipt = self._request("POST", path, payload, key=key)
                    if code not in (200, 202):
                        raise RuntimeError("command enqueue rejected: " + canonical(receipt))
                    if not injected:
                        injected = True
                        if name == "open-buy" and self.configuration.worker_every and sequence % self.configuration.worker_every == 0:
                            self._fault(sequence, "worker")
                        if name == "open-sell" and self.configuration.parent_every and sequence % self.configuration.parent_every == 0:
                            self._fault(sequence, "parent")
                        continue  # Query original ID even if POST looked terminal.
                elif code not in (200, 202):
                    raise RuntimeError("command query rejected: " + canonical(receipt))
                if receipt.get("state") == "SUCCEEDED":
                    if previous == "DONE" and receipt != stored:
                        raise RuntimeError("immutable financial command receipt changed")
                    if previous != "DONE":
                        self._done(sequence, name, receipt)
                    return receipt
                if receipt.get("state") in ("REJECTED", "QUARANTINED"):
                    raise RuntimeError("golden command has unsuccessful terminal result: " + canonical(receipt))
            except (OSError, TimeoutError, ssl.SSLError, HTTPException, json.JSONDecodeError) as error:
                self._event("COMMAND_OUTCOME_UNKNOWN", {"round": sequence, "step": name,
                    "command_id": payload["command_id"], "error_type": type(error).__name__})
            time.sleep(.05)
        raise TimeoutError("original command unresolved; no later step/round may execute: " + payload["command_id"])

    def observe(self, sequence, name, predicate):
        plan = {"observation": name}
        status, receipt = self._plan(sequence, name, plan)
        if status == "DONE":
            return receipt  # A historical partial state can now be cancelled.
        actual = self._wait(predicate, name)
        if status != "DONE":
            self._done(sequence, name, actual)
        return actual

    def roundtrip(self, sequence):
        prefix = f"ms:{self.meta['job_id']}:r{sequence:09d}:"
        a, b, credit = ACCOUNTS
        def order(name, account, quantity, key, reduce_only=False):
            return self.command(sequence, name, account, f"/v2/accounts/{account}/orders",
                {"command_id": prefix + name, "order_id": prefix + name, "symbol": "BTC-PERP",
                 "quantity": quantity, "limit_price": "100", "reduce_only": reduce_only}, key)
        order("open-buy", a, "0.02", "alice")
        order("open-sell", b, "-0.01", "bob")
        def partial():
            with readonly(self.financial) as connection:
                if connection.execute("SELECT 1 FROM sqlite_master WHERE name='uta_matches' AND type='table'").fetchone() is None:
                    return None  # Worker initializes its own matcher after activation.
                row = connection.execute("SELECT quantity,filled_quantity,status FROM uta_orders WHERE account_id=? AND order_id=?", (a, prefix + "open-buy")).fetchone()
                matches = connection.execute("SELECT COUNT(*) FROM uta_matches WHERE buy_order_id=? AND sell_order_id=?", (prefix + "open-buy", prefix + "open-sell")).fetchone()[0]
                if row and D(row[1]) == D(".01") and row[2] == "PARTIALLY_FILLED" and matches == 1:
                    return {"quantity": row[0], "filled_quantity": row[1], "status": row[2], "confirmed_matches": matches}
        self.observe(sequence, "partial-match", partial)
        self.command(sequence, "cancel-partial", a, f"/v2/accounts/{a}/orders/{prefix}open-buy/cancel",
            {"command_id": prefix + "cancel-partial"}, "alice")
        order("close-sell", a, "-0.01", "alice", True)
        order("close-buy", b, "0.01", "bob", True)
        def flat():
            with readonly(self.financial) as connection:
                trades = connection.execute("SELECT COUNT(*) FROM uta_matches WHERE buy_order_id=? AND sell_order_id=?", (prefix + "close-buy", prefix + "close-sell")).fetchone()[0]
                positions = connection.execute("SELECT COUNT(*) FROM uta_positions").fetchone()[0]
                return {"confirmed_close_matches": trades, "positions": positions} if trades == 1 and positions == 0 else None
        self.observe(sequence, "flat-close", flat)
        self.command(sequence, "repay", credit, f"/v2/accounts/{credit}/repay",
            {"command_id": prefix + "repay", "asset": "BTC", "amount": "0.00000002"}, "credit")
        return self.verify(sequence)

    def verify(self, completed, *, full=False):
        """Independent integer cash/debt/quantity oracle; no production risk math."""
        planned = self.configuration.rounds
        if type(completed) is not int or not 0 <= completed <= planned:
            raise RuntimeError("independent completed-round budget is invalid")
        with readonly(self.financial) as connection:
            if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise RuntimeError("financial SQLite integrity failure")
            if {row[0] for row in connection.execute("SELECT account_id FROM uta_accounts")} != set(ACCOUNTS):
                raise RuntimeError("independent fixed-account identity golden mismatch")
            if dict(connection.execute("SELECT asset,scale FROM ledger_assets")) != {"USD": 8, "BTC": 8}:
                raise RuntimeError("independent fixed asset/precision golden mismatch")
            balances = {(row[0], row[1]): int(row[2]) for row in connection.execute("SELECT account,asset,units FROM ledger_balances")}
            remaining = 2 * (planned - completed)
            # Hand-derived closed budget: three USD deposits, one BTC buffer,
            # one funded BTC pool/loan, two equal-price fill sides per trader
            # and a two-satoshi repayment per completed round. Compare every
            # owner/asset, retaining gross debt instead of netting it into cash.
            expected_balances = {
                ("customer:" + ACCOUNTS[0], "USD"): 1_000_000 * SCALE - completed * 80000,
                ("customer:" + ACCOUNTS[1], "USD"): 1_000_000 * SCALE - completed * 80000,
                ("customer:" + ACCOUNTS[2], "USD"): 1_000_000 * SCALE,
                ("customer:" + ACCOUNTS[2], "BTC"): SCALE + remaining,
                ("system:custody", "USD"): -3_000_000 * SCALE,
                ("system:custody", "BTC"): -SCALE,
                ("system:credit-capital", "BTC"): -SCALE,
                ("system:credit-pool", "BTC"): SCALE - remaining,
                ("liability:principal:" + ACCOUNTS[2], "BTC"): -remaining,
                ("system:credit-principal-receivable", "BTC"): remaining,
            }
            if completed:
                expected_balances[("system:fees", "USD")] = completed * 160000
            if balances != expected_balances:
                raise RuntimeError("independent fixed-budget gross cash/debt/ownership golden mismatch")
            debts = {(row[0], row[1]): (Fraction(row[2]) * SCALE, Fraction(row[3]) * SCALE)
                     for row in connection.execute("SELECT account_id,asset,principal,interest FROM uta_liabilities")}
            if debts != {(ACCOUNTS[2], "BTC"): (remaining, 0)}:
                raise RuntimeError("independent gross principal/interest golden mismatch")
            if connection.execute("SELECT COUNT(*) FROM uta_positions").fetchone()[0]:
                raise RuntimeError("completed rounds left positions")
            if connection.execute("SELECT COUNT(*) FROM uta_orders WHERE status IN ('OPEN','PARTIALLY_FILLED')").fetchone()[0]:
                raise RuntimeError("completed rounds left unconfirmed order reserves")
            counts = {}
            if full:
                credit = [tuple(row) for row in connection.execute(
                    "SELECT scope,command_id,kind,asset,amount,source_reference FROM credit_commands")]
                pool = [row for row in credit if row[2] == "pool_funded"]
                loans = [row for row in credit if row[2] == "borrowed"]
                repayments = [row for row in credit if row[2] == "repaid"]
                if (len(credit) != 2 + completed or len(pool) != 1 or len(loans) != 1 or len(repayments) != completed
                        or pool[0][:4] != ("pool", "synthetic-initial-pool", "pool_funded", "BTC")
                        or Fraction(pool[0][4]) != 1 or not pool[0][5]
                        or loans[0][:4] != ("account:" + ACCOUNTS[2], "synthetic-initial-loan", "borrowed", "BTC")
                        or Fraction(loans[0][4]) * SCALE != 2 * planned or loans[0][5] is not None
                        or any(row[0] != "account:" + ACCOUNTS[2] or row[3] != "BTC"
                               or Fraction(row[4]) * SCALE != 2 or row[5] is not None for row in repayments)):
                    raise RuntimeError("independent fixed funding/loan/repayment history golden mismatch")
                for table in ("uta_orders", "uta_fills", "uta_matches", "uta_risk_decisions"):
                    if completed == 0 and table == "uta_matches" and connection.execute("SELECT 1 FROM sqlite_master WHERE name='uta_matches' AND type='table'").fetchone() is None:
                        counts[table] = 0
                    else:
                        counts[table] = connection.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
                expected = {"uta_orders": 4 * completed, "uta_fills": 4 * completed,
                    "uta_matches": 2 * completed, "uta_risk_decisions": 8 * completed}
                if counts != expected:
                    raise RuntimeError("independent business/audit count golden mismatch: " + canonical(counts))
                if connection.execute("SELECT COUNT(*) FROM uta_command_inbox WHERE state!='SUCCEEDED'").fetchone()[0]:
                    raise RuntimeError("financial inbox retains pending/rejected/quarantined commands")
                for table, field in (("uta_orders", "admission_decision_id"), ("uta_fills", "execution_decision_id")):
                    if connection.execute(f"SELECT COUNT(*) FROM {table} x LEFT JOIN uta_risk_decisions d ON x.{field}=d.decision_id WHERE d.decision_id IS NULL").fetchone()[0]:
                        raise RuntimeError("required decision audit link is missing")
                if connection.execute("SELECT COUNT(*) FROM uta_risk_decisions d LEFT JOIN uta_market_history m ON m.snapshot_id=d.market_snapshot_id LEFT JOIN uta_code_artifacts a ON a.artifact_id=d.artifact_id LEFT JOIN uta_risk_policies p ON p.policy_id=d.policy_id WHERE m.snapshot_id IS NULL OR a.artifact_id IS NULL OR p.policy_id IS NULL").fetchone()[0]:
                    raise RuntimeError("required market/code/policy decision reference is missing")
                for row in connection.execute("SELECT quantity,price,fee FROM uta_fills"):
                    if abs(Fraction(row[0])) != Fraction(1, 100) or Fraction(row[1]) != 100 or Fraction(row[2]) != Fraction(4, 10000):
                        raise RuntimeError("independent per-fill quantity/price/fee mismatch")
                _verify_archive_content(connection)
                totals, projections = {}, {}
                for row in connection.execute("SELECT account,asset,units FROM ledger_postings"):
                    key = row[0], row[1]
                    projections[key] = projections.get(key, 0) + int(row[2])
                    totals[row[1]] = totals.get(row[1], 0) + int(row[2])
                if any(totals.values()) or any(projections.get(key, 0) != value for key, value in balances.items()) or any(balances.get(key, 0) != value for key, value in projections.items()):
                    raise RuntimeError("independent per-currency journal conservation/projection mismatch")
                if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
                    raise RuntimeError("financial foreign key mismatch")
                counts["partial_cancelled_orders"] = connection.execute("SELECT COUNT(*) FROM uta_orders WHERE status='CANCELLED' AND filled_quantity!='0'").fetchone()[0]
                if counts["partial_cancelled_orders"] != completed:
                    raise RuntimeError("partial cancellation count mismatch")
                counts["terminal_account_commands"] = connection.execute("SELECT COUNT(*) FROM uta_command_inbox WHERE account_id IS NOT NULL AND state='SUCCEEDED'").fetchone()[0]
                counts["control_commands"] = connection.execute("SELECT COUNT(*) FROM uta_command_inbox WHERE account_id IS NULL").fetchone()[0]
                if counts["terminal_account_commands"] != 6 * completed:
                    raise RuntimeError("terminal account command count mismatch")
                counts["ledger_events"] = connection.execute("SELECT COUNT(*) FROM ledger_events").fetchone()[0]
                if counts["ledger_events"] != 6 + 5 * completed:
                    raise RuntimeError("independent genesis/fill/repayment journal count mismatch")
        return {"golden_passed": True, "completed_rounds": completed, "remaining_principal_satoshi": remaining,
                "financial_counts": counts, "oracle": "independent integer postings/cash/debt and relational audit links"}

    def export(self, segment_size=256):
        manifest_path = self.directory / "log-segments.json"
        manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"segments": []}
        cursor = manifest["segments"][-1]["last"] if manifest["segments"] else 0
        logs = self.directory / "logs"
        logs.mkdir(mode=0o700, exist_ok=True)
        while True:
            with self.checkpoint.read_transaction() as connection:
                rows = [dict(row) for row in connection.execute("SELECT * FROM events WHERE sequence>? ORDER BY sequence LIMIT ?", (cursor, segment_size))]
            if not rows:
                break
            name = f"events-{rows[0]['sequence']:09d}-{rows[-1]['sequence']:09d}.jsonl.gz"
            target = logs / name
            temporary = target.with_suffix(".tmp")
            with temporary.open("wb") as raw:
                with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as output:
                    for row in rows:
                        output.write((canonical(row) + "\n").encode())
                raw.flush()
                os.fsync(raw.fileno())
            os.replace(temporary, target)
            target.chmod(0o600)
            manifest["segments"].append({"file": "logs/" + name, "first": rows[0]["sequence"],
                "last": rows[-1]["sequence"], "sha256": sha256(target.read_bytes()).hexdigest()})
            _atomic(manifest_path, manifest)
            cursor = rows[-1]["sequence"]
        return manifest

    def audit_logs(self):
        manifest = json.loads((self.directory / "log-segments.json").read_text())
        sequence, previous = 0, "0" * 64
        for segment in manifest["segments"]:
            target = self.directory / segment["file"]
            if segment["first"] != sequence + 1 or sha256(target.read_bytes()).hexdigest() != segment["sha256"]:
                raise RuntimeError("log segment checksum or continuity mismatch")
            with gzip.open(target, "rt") as stream:
                for line in stream:
                    row = json.loads(line)
                    sequence += 1
                    digest = sha256(canonical([sequence, row["kind"], row["payload"], previous]).encode()).hexdigest()
                    if row["sequence"] != sequence or row["previous_hash"] != previous or row["event_hash"] != digest:
                        raise RuntimeError("log event chain mismatch")
                    previous = digest
            if segment["last"] != sequence:
                raise RuntimeError("log segment end mismatch")
        with self.checkpoint.read_transaction() as connection:
            row = connection.execute("SELECT sequence,event_hash FROM events ORDER BY sequence DESC LIMIT 1").fetchone()
        if row is None or tuple(row) != (sequence, previous):
            raise RuntimeError("exported logs do not cover every checkpoint event")
        return {"events": sequence, "last_hash": previous, "segments": len(manifest["segments"])}

    def _resources(self):
        # Sizes are observations, not one atomic directory snapshot. A last
        # SQLite close or atomic rename can remove an auxiliary after discovery.
        # Stat once, count every surviving regular file, and never hide main
        # database loss or permission/I/O errors behind an is_file() predicate.
        required = {self.directory / name for name in _RESOURCE_DATABASES}
        def enumeration_error(error):
            raise error  # pathlib's recursive glob can suppress scan errors.
        discovered = (Path(root) / name
            for root, directories, files in os.walk(self.directory, onerror=enumeration_error)
            for name in directories + files)
        paths = dict.fromkeys([*required, *discovered])
        total = 0
        for path in paths:
            try:
                details = path.stat(follow_symlinks=False)
            except FileNotFoundError:
                relative = path.relative_to(self.directory).as_posix()
                if (relative in _RESOURCE_TRANSIENTS or re.fullmatch(
                        r"logs/events-[0-9]{9,}-[0-9]{9,}\.jsonl\.tmp", relative)):
                    continue
                raise
            if stat.S_ISREG(details.st_mode):
                total += details.st_size
            elif path in required:
                raise RuntimeError("required managed database is not a regular file")
        free = shutil.disk_usage(self.directory).free
        return {"directory_bytes": total, "free_bytes": free,
                "budget_exceeded": total > self.configuration.max_directory_bytes or free < self.configuration.min_free_bytes}

    def status(self, status="running", *, final=None, error=None):
        resources = self._resources()
        if status == "running" and resources["budget_exceeded"]:
            raise RuntimeError("managed soak disk budget reached")
        with self.checkpoint.read_transaction() as connection:
            rounds = {row[0]: row[1] for row in connection.execute("SELECT state,COUNT(*) FROM rounds GROUP BY state")}
            latencies = [row[0] for row in connection.execute("SELECT completed_ns-planned_ns FROM rounds WHERE state='DONE'")]
            faults = {"worker": 0, "parent": 0}
            for row in connection.execute("SELECT kind,evidence FROM faults WHERE state='DONE'"):
                if json.loads(row[1]).get("signal_sent"):
                    faults[row[0]] += 1
            unresolved = connection.execute("SELECT COUNT(*) FROM steps WHERE state!='DONE'").fetchone()[0]
            unresolved_faults = connection.execute("SELECT COUNT(*) FROM faults WHERE state!='DONE'").fetchone()[0]
        histogram = LatencyHistogram()
        for value in latencies:
            histogram.observe(value)
        started = self._state("started_boottime_ns")
        elapsed = 0 if started is None else (time.clock_gettime_ns(time.CLOCK_BOOTTIME) - started) / 1e9
        qualified = (status == "completed" and final is not None and final.get("golden_passed")
            and rounds.get("DONE", 0) == self.configuration.rounds and not unresolved and not unresolved_faults
            and self.strict_source and self._state("controller_sessions") == 1
            and all(faults.values()) and self._state("logs_verified") is True and self.validation is not None)
        report = {"status": status, "mode": "managed-process-required-audit-native-tls-hmac",
            "synthetic": True, "planned_rounds": self.configuration.rounds, "rounds": rounds,
            "unresolved_steps": unresolved, "unresolved_faults": unresolved_faults, "elapsed_seconds": elapsed, "fault_signals": faults,
            "round_latency_ms_from_planned_arrival_including_cli_feed_and_recovery": histogram.report(),
            "http_attempts": self._state("http_attempts") or 0, "resources": resources,
            "controller_sessions": self._state("controller_sessions") or 0,
            "verified_tls": self.tls.verify_mode == ssl.CERT_REQUIRED and self.tls.check_hostname,
            "logs_verified": self._state("logs_verified") is True, "final_audit": final, "error": error,
            "long_run_blockers": [] if self.validation is not None else ["exact_full_release_validation_required"],
            "validation_evidence": self.meta.get("validation_evidence"),
            "continuous_6h_stability_passed": bool(qualified and elapsed >= 21600 and self.configuration.duration >= 21600),
            "continuous_24h_stability_passed": bool(qualified and elapsed >= 86400 and self.configuration.duration >= 86400),
            "capacity_10000_per_s_passed": False, "production_approved": False,
            "audit_scope": {"required": ["ORDER_ACCEPTED", "FILL_CONFIRMED"],
                "not_risk_decision_captured": ["cancels", "repayments", "new credit", "business rejects"]},
            "qualification": "new candidate single-host stability only; no endorsement of the earlier 887 job or HA/capacity"}
        _atomic(self.directory / "progress.json", report)
        return report

    def run(self):
        error = final = None
        state = "paused"
        sessions = (self._state("controller_sessions") or 0) + 1
        self._state("controller_sessions", sessions)
        self._state("logs_verified", False)
        try:
            self._start_server()
            with self.checkpoint.read_transaction() as connection:
                pending_faults = [tuple(row) for row in connection.execute("SELECT round,kind FROM faults WHERE state!='DONE' ORDER BY round,kind")]
                unresolved_rounds = connection.execute("SELECT COUNT(*) FROM rounds WHERE state!='DONE'").fetchone()[0]
                completed_rounds = connection.execute("SELECT COUNT(*) FROM rounds WHERE state='DONE'").fetchone()[0]
            for sequence, kind in pending_faults:
                account = ACCOUNTS[0 if kind == "worker" else 1]
                name = "open-buy" if kind == "worker" else "open-sell"
                command_id = f"ms:{self.meta['job_id']}:r{sequence:09d}:{name}"
                code, receipt = self._request("GET", f"/v2/accounts/{account}/commands/{command_id}")
                if code not in (200, 202) or receipt.get("state") not in ("PENDING", "SUCCEEDED"):
                    raise RuntimeError("original fault-associated command cannot be reconciled")
                self._fault(sequence, kind)
            if not unresolved_rounds:
                self.verify(completed_rounds, full=True)
            started = self._state("started_boottime_ns")
            if started is None:
                started = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
                self._state("started_boottime_ns", started)
                self._state("boot_id", Path("/proc/sys/kernel/random/boot_id").read_text().strip())
            if self._state("boot_id") != Path("/proc/sys/kernel/random/boot_id").read_text().strip():
                raise RuntimeError("host boot changed; do not manufacture continuous elapsed time")
            deadline = started + int(self.configuration.duration * 1e9)
            last_heartbeat = last_export = time.monotonic()
            for sequence in range(1, self.configuration.rounds + 1):
                with self.checkpoint.read_transaction() as connection:
                    previous = connection.execute("SELECT state FROM rounds WHERE sequence=?", (sequence,)).fetchone()
                if previous is not None and previous[0] == "DONE":
                    continue
                if self.stop.is_set() or (self.directory / "STOP").exists():
                    break
                planned = started + int((sequence - 1) * 1e9 / self.configuration.rate)
                last_start = self._state("last_round_started_ns") or 0
                eligible = (time.clock_gettime_ns(time.CLOCK_BOOTTIME) if previous is not None
                            else max(planned, last_start + int(1e9 / self.configuration.rate)))
                while time.clock_gettime_ns(time.CLOCK_BOOTTIME) < eligible and not self.stop.is_set():
                    if (self.directory / "STOP").exists():
                        self.stop.set()
                        break
                    if time.monotonic() - last_heartbeat >= self.configuration.heartbeat_interval:
                        self.status()
                        last_heartbeat = time.monotonic()
                    if time.monotonic() - last_export >= self.configuration.export_interval:
                        self.export()
                        last_export = time.monotonic()
                    self.stop.wait(.05)
                if self.stop.is_set():
                    break
                self._assert_source()
                with self.checkpoint.transaction() as connection:
                    connection.execute("INSERT INTO rounds VALUES(?,?,'ACTIVE',NULL) ON CONFLICT(sequence) DO UPDATE SET state='ACTIVE'", (sequence, planned))
                    if previous is None:
                        connection.execute("INSERT INTO state VALUES('last_round_started_ns',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                                           (canonical(time.clock_gettime_ns(time.CLOCK_BOOTTIME)),))
                    self._append_event(connection, "ROUND_STARTED" if previous is None else "ROUND_RECOVERING",
                        {"round": sequence, "planned_ns": planned, "clock": "CLOCK_BOOTTIME"})
                self.publish(sequence)
                proof = self.roundtrip(sequence)
                completed = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
                with self.checkpoint.transaction() as connection:
                    connection.execute("UPDATE rounds SET state='DONE',completed_ns=? WHERE sequence=?", (completed, sequence))
                    self._append_event(connection, "ROUND_DONE", {"round": sequence, "proof": proof, "latency_ns": completed - planned})
                self.status()
            while time.clock_gettime_ns(time.CLOCK_BOOTTIME) < deadline and not self.stop.is_set():
                if (self.directory / "STOP").exists():
                    self.stop.set()
                    break
                self.stop.wait(.1)
            with self.checkpoint.read_transaction() as connection:
                count = connection.execute("SELECT COUNT(*) FROM rounds WHERE state='DONE'").fetchone()[0]
            state = "completed" if count == self.configuration.rounds and not self.stop.is_set() else "paused"
        except BaseException as caught:
            state = "paused" if isinstance(caught, (TimeoutError, OSError, KeyboardInterrupt)) else "failed"
            error = {"type": type(caught).__name__, "message": str(caught)}
            self._event("ROUND_OR_OUTCOME_UNRESOLVED", error)
        finally:
            try:
                self._stop_server()
            except BaseException as caught:
                state, error = "failed", {"type": type(caught).__name__, "message": str(caught)}
        if state == "completed":
            try:
                self._assert_source()
                final = self.verify(self.configuration.rounds, full=True)
            except BaseException as caught:
                state, error = "failed", {"type": type(caught).__name__, "message": str(caught)}
        self._event("CONTROLLER_ENDED", {"status": state, "error": error})
        self.export()
        self.audit_logs()
        self._state("logs_verified", True)
        report = self.status(state, final=final, error=error)
        self.close()
        return report

    def close(self):
        try:
            if getattr(self, "process", None) is not None or getattr(self, "listener", None) is not None:
                self._stop_server()
        finally:
            if getattr(self, "lock", None) is not None:
                os.close(self.lock)
                self.lock = None


def inspect_job(directory):
    """Read-only persisted observation; never starts/stops a coordinator."""
    directory = Path(directory).absolute()
    with readonly(directory / "checkpoint.sqlite3") as connection:
        states = {row[0]: json.loads(row[1]) for row in connection.execute("SELECT key,value FROM state")}
        steps = {row[0]: row[1] for row in connection.execute("SELECT state,COUNT(*) FROM steps GROUP BY state")}
    return {"last_report": json.loads((directory / "progress.json").read_text()),
            "checkpoint_steps": steps, "recorded_listener_alive": bool(states.get("listener") and
                alive(states["listener"]["pid"], states["listener"]["birth"])),
            "observation_only": True, "new_financial_audit_performed": False, "production_approved": False}


def audit_job(directory):
    """Cold read-only verification, with no financial/schema constructor."""
    directory = Path(directory).absolute()
    meta = json.loads((directory / "job.json").read_text())
    report = inspect_job(directory)
    if report["last_report"]["status"] != "completed" or report["recorded_listener_alive"]:
        raise RuntimeError("final audit requires a completed, stopped authority")
    for path, expected in meta["file_identities"].items():
        details = Path(path).stat()
        if [details.st_dev, details.st_ino] != expected:
            raise RuntimeError("job file identity changed before cold audit")
    for relative, expected in meta["environment"]["source_sha256"].items():
        if sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
            raise RuntimeError("audit source differs from the frozen source bytes")
    if meta.get("validation_evidence") is not None:
        for name, expected in meta["validation_evidence"]["artifact_sha256"].items():
            if sha256((directory / "validation" / name).read_bytes()).hexdigest() != expected:
                raise RuntimeError("audit release validation evidence checksum mismatch")
    class CheckpointReader:
        def read_transaction(self):
            return readonly(directory / "checkpoint.sqlite3")
    view = object.__new__(ManagedSoak)
    view.directory, view.financial = directory, directory / "managed/shard-0000.sqlite3"
    view.checkpoint, view.configuration = CheckpointReader(), Configuration(**meta["configuration"])
    return {"status": "audit_passed", "financial": view.verify(view.configuration.rounds, full=True),
            "logs": view.audit_logs(), "cold_read_only": True, "production_approved": False,
            "capacity_10000_per_s_passed": False, "does_not_upgrade_duration_flags": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("run", "resume", "bootstrap", "status", "audit"))
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--duration", type=float, default=60)
    parser.add_argument("--worker-every", type=int, default=30)
    parser.add_argument("--parent-every", type=int, default=300)
    parser.add_argument("--rounds", type=int)
    parser.add_argument("--source-reference")
    parser.add_argument("--min-free-bytes", type=int, default=1024**3)
    parser.add_argument("--allow-dirty-development", action="store_true")
    parser.add_argument("--allow-long-run", action="store_true", help="explicit engineering long-run opt-in; exact full release validation is also required")
    parser.add_argument("--validation-report", type=Path, help="exact clean commit's full run_validation.py summary.json and sidecars")
    args = parser.parse_args(argv)
    if args.operation in ("status", "audit"):
        print(canonical((inspect_job if args.operation == "status" else audit_job)(args.directory)))
        return 0
    duration = (json.loads((args.directory / "job.json").read_text())["configuration"]["duration"]
                if args.operation == "resume" else args.duration)
    if duration > 60 and (not args.allow_long_run or args.allow_dirty_development):
        parser.error("runs longer than 60s require --allow-long-run and frozen clean source")
    if args.operation == "bootstrap":
        if type(args.rounds) is not int or not 1 <= args.rounds <= 21600 or not args.source_reference:
            parser.error("bootstrap requires bounded rounds and a synthetic source reference")
        print(canonical(bootstrap(args.directory, args.rounds, args.source_reference)))
        return 0
    configuration = None if args.operation == "resume" else Configuration(duration=args.duration,
        worker_every=args.worker_every, parent_every=args.parent_every, min_free_bytes=args.min_free_bytes)
    try:
        job = ManagedSoak(args.directory, configuration, resume=args.operation == "resume",
            strict_source=not args.allow_dirty_development, allow_long_run=args.allow_long_run,
            validation_report=args.validation_report)
    except RuntimeError as error:
        parser.error(str(error))
    previous = {}
    for number in (signal.SIGTERM, signal.SIGINT):
        previous[number] = signal.signal(number, lambda signum, frame: job.stop.set())
    try:
        result = job.run()
        print(canonical(result))
        return 0 if result["status"] == "completed" else 2
    finally:
        job.close()
        for number, handler in previous.items():
            signal.signal(number, handler)


if __name__ == "__main__":
    raise SystemExit(main())
