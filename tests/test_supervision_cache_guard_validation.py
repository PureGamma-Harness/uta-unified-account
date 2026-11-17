"""Independent warm-proof SQL authority tests, all isolated synthetic data.

The spawned owner uses real leases, persistent SQL guards, required audit and
ExchangeWorker. A command pipe controls fault ordering, not financial decisions.
This is a single-authority fault harness, not a process-router throughput test.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from hashlib import sha256
import json
import inspect
import multiprocessing
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from time import monotonic, sleep
import unittest

from uta.decision_audit import DecisionAudit
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.portfolio import CollateralRule, CollateralTier, LinearMarginRule, PortfolioRules
from uta.products import ProductCatalog, ProductKind, ProductSpec, TradingStatus
from uta.service import ExchangeService
from uta.storage import Database
from uta.supervisor import ExchangeWorker
from uta.writer_fence import WriterFence


def policy():
    return dict(product_catalog=ProductCatalog(1, {"BTC-PERP": ProductSpec("BTC-PERP",
        ProductKind.LINEAR_PERPETUAL, "BTC", "USD", "USD", D(".01"), D(".001"), D(".01"),
        status=TradingStatus.ACTIVE)}),
        portfolio_rules=PortfolioRules(1,
            {"USD": CollateralRule("USD", (CollateralTier(None, D(1)),), D(1))}, {},
            {"tier-1": LinearMarginRule("tier-1", D(".1"), D(".05"))}, D(0)),
        decision_audit=True, max_price_age=timedelta(seconds=60))


def error_codes(error):
    seen, codes, stack = set(), [], [error]
    while stack:
        item = stack.pop()
        if item is None or id(item) in seen:
            continue
        seen.add(id(item))
        if getattr(item, "code", None) is not None:
            codes.append(item.code)
        stack.extend((getattr(item, "__cause__", None), getattr(item, "__context__", None)))
    return codes


class ProofCommitFaultDatabase(Database):
    """One real COMMIT fault; no alteration of the cache or supervisor logic."""
    fault_mode = None

    @contextmanager
    def transaction(self):
        mode, self.fault_mode = self.fault_mode, None
        with super().transaction() as connection:
            yield connection
            if mode == "deferred_constraint":
                connection.execute("INSERT INTO cache_fault_child VALUES(999)")
        if mode == "response_lost":
            raise ConnectionError("synthetic lost response after actual proof COMMIT")


def cache_owner(path, channel):
    """Real independent PID; immutable original token retained after revocation."""
    worker = None
    try:
        database = ProofCommitFaultDatabase(path)
        fence = WriterFence(database)
        token = fence.acquire("cache-fault-owner", 30)
        exchange = ExchangeService(database.for_writer(token), {"USD": 8}, **policy())
        worker = ExchangeWorker(exchange, normal_cache_size=4, account_batch=1, interval=.02)
        worker.run_once()
        worker.run_once()
        channel.send({"ok": True, "pid": os.getpid(), "generation": token.generation,
                      "stats": worker.normal_cache_stats(), "report": worker.last_report})
        while True:
            command = channel.recv()
            operation = command["operation"]
            if operation == "stop":
                return
            try:
                if operation == "round":
                    result = worker.run_once()
                elif operation == "deposit":
                    result = exchange.deposit("alice", command["id"], "USD", D(1))
                elif operation == "submit":
                    result = exchange.submit_order("alice", command["id"], "BTC-PERP", D(".001"), D(100))
                elif operation == "release":
                    result = fence.release(token)
                elif operation == "renew":
                    fence.renew(token, command.get("ttl", 30))
                    result = {"renewed": True}
                elif operation == "raw_update":
                    # No UDF, authorizer bypass or fabricated token is installed.
                    with sqlite3.connect(path) as raw:
                        raw.execute("UPDATE ledger_balances SET units='9999999999' WHERE account='customer:alice'")
                    result = {"unexpected_raw_write": True}
                elif operation == "risk_revision":
                    with exchange._transaction() as connection:
                        connection.execute("UPDATE uta_liquidation_accounts SET revision=revision+1 WHERE account_id='alice'")
                    result = {"changed": True}
                elif operation == "table_definition":
                    with exchange._transaction() as connection:
                        connection.execute("ALTER TABLE uta_positions ADD COLUMN cache_schema_probe TEXT")
                    result = {"changed": True}
                elif operation == "delete_risk_row":
                    with exchange._transaction() as connection:
                        connection.execute("DELETE FROM uta_liquidation_accounts WHERE account_id='alice'")
                    result = {"deleted": True}
                elif operation == "arm_proof_fault":
                    exchange.database.fault_mode = command["mode"]
                    result = {"armed": command["mode"]}
                elif operation == "background_failure":
                    worker.start()
                    deadline = monotonic() + 2
                    while monotonic() < deadline and worker.last_report.get("reason") != "worker_failure":
                        sleep(.005)
                    worker.stop()
                    result = worker.last_report
                else:
                    raise ValueError("unknown test operation")
                channel.send({"ok": True, "result": result, "stats": worker.normal_cache_stats()})
            except Exception as error:
                channel.send({"ok": False, "error_type": type(error).__name__, "codes": error_codes(error),
                              "error_message": str(error)[:500],
                              "sqlite_errorcode": getattr(error, "sqlite_errorcode", None),
                              "sqlite_errorname": getattr(error, "sqlite_errorname", None),
                              "stats": worker.normal_cache_stats()})
    except BaseException as error:
        channel.send({"ok": False, "error_type": type(error).__name__, "codes": error_codes(error)})
    finally:
        if worker is not None:
            worker.stop()
        channel.close()


@contextmanager
def raw_read(path):
    connection = sqlite3.connect(Path(path).absolute().as_uri() + "?mode=ro", uri=True, isolation_level=None)
    try:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        yield connection
    finally:
        connection.close()


def facts(path):
    """Read facts even after guard corruption, without repairing the authority."""
    with raw_read(path) as connection:
        schema = connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name").fetchall()
        tables = {name: sorted(connection.execute('SELECT * FROM "' + name + '"').fetchall(), key=repr)
                  for kind, name, _, _ in schema if kind == "table" and not name.startswith("writer_fence_")}
        control = {name: connection.execute('SELECT * FROM "' + name + '"').fetchall()
                   for name in ("writer_fence_authority", "writer_fence_lease", "writer_fence_events")}
        return {"tables": tables, "schema": schema, "control": control}


class WarmCacheGuardValidationTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.path = self.directory / "synthetic.sqlite3"
        output = os.environ.get("UTA_CACHE_GUARD_EVIDENCE")
        self.evidence = Path(output) / self._testMethodName if output else self.directory / "evidence"
        self.evidence.mkdir(parents=True, exist_ok=False)
        exchange = ExchangeService(Database(self.path), {"USD": 8}, **policy())
        exchange.create_account("alice")
        exchange.deposit("alice", "seed", "USD", D(1000))
        with exchange._transaction() as connection:
            connection.execute("CREATE TABLE cache_fault_parent(id INTEGER PRIMARY KEY)")
            connection.execute("CREATE TABLE cache_fault_child(id INTEGER REFERENCES cache_fault_parent(id) DEFERRABLE INITIALLY DEFERRED)")
        exchange.publish_market(MarketSnapshot(1, datetime.now(timezone.utc),
            {"USD": AssetSpec(D(1), D(1))}, {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))}))
        exchange.set_kill_switch(False)
        self.fence = WriterFence(Database(self.path))
        self.fence.enable("independent-cache-guard")
        context = multiprocessing.get_context("spawn")
        self.channel, child = context.Pipe()
        self.process = context.Process(target=cache_owner, args=(str(self.path), child))
        self.process.start()
        child.close()
        self.addCleanup(self.close_owner)
        self.assertTrue(self.channel.poll(8), "real cache owner did not initialize")
        self.ready = self.channel.recv()
        self.assertTrue(self.ready["ok"], self.ready)
        self.assertNotEqual(self.ready["pid"], os.getpid())
        self.assertEqual(self.ready["pid"], self.process.pid)
        self.assertGreater(self.ready["stats"]["hits"], 0, "must prove a real omitted NORMAL supervision")
        self.assertEqual(self.ready["report"]["normal_cache"]["skipped"], 1)
        self.assertEqual(self.fence.status()["owner_pid"], self.process.pid)
        source_files = [Path(inspect.getfile(value)) for value in
                        (ExchangeService, ExchangeWorker, WriterFence, Database, DecisionAudit)]
        source_files.append(Path(__file__))
        self.record("before-manifest", {"facts": facts(self.path), "owner": self.ready,
                    "cache_capacity": 4, "decision_audit_required": True,
                    "source_sha256": {path.name: sha256(path.read_bytes()).hexdigest() for path in source_files}})

    def close_owner(self):
        if self.process.is_alive():
            try:
                self.channel.send({"operation": "stop"})
                self.process.join(2)
            except (BrokenPipeError, EOFError, OSError):
                pass
        if self.process.is_alive():
            self.process.kill()
            self.process.join(2)
        self.channel.close()

    def record(self, label, value):
        payload = json.dumps(value, sort_keys=True, indent=2) + "\n"
        (self.evidence / (label + ".json")).write_text(payload)
        return sha256(payload.encode()).hexdigest()

    def request(self, operation, **arguments):
        self.channel.send({"operation": operation, **arguments})
        self.assertTrue(self.channel.poll(8), "owner request did not complete: " + operation)
        result = self.channel.recv()
        self.record(f"request-{len(list(self.evidence.glob('request-*.json'))):03}-{operation}", result)
        return result

    def assert_fenced(self, operation, expected, **arguments):
        result = self.request(operation, **arguments)
        self.assertFalse(result["ok"], result)
        self.assertTrue(set(expected) & set(result["codes"]), result)
        return result

    def test_warm_old_owner_cannot_write_after_release_and_new_pid_takeover(self):
        accepted = self.request("submit", id="healthy-order")
        self.assertTrue(accepted["ok"], accepted)
        self.assertTrue(self.request("round")["ok"])
        warmed_with_order = self.request("round")
        self.assertTrue(warmed_with_order["ok"], warmed_with_order)
        self.assertEqual(warmed_with_order["result"]["normal_cache"]["skipped"], 1)
        self.assertGreater(warmed_with_order["stats"]["hits"], self.ready["stats"]["hits"])
        with raw_read(self.path) as connection:
            row = connection.execute("SELECT status,admission_decision_id FROM uta_orders").fetchone()
            self.assertEqual(row[0], "OPEN")
            self.assertIsNotNone(row[1])
            self.assertEqual(D(accepted["result"]["reserved_margin"]), D(".01004"))
            event = json.loads(connection.execute("SELECT payload FROM uta_events WHERE event_type='ORDER_ACCEPTED'").fetchone()[0])
            self.assertEqual(D(event["reserved_margin"]), D(".01004"))
            DecisionAudit.validate(connection)
        self.assertTrue(self.request("release")["ok"])
        new_token = self.fence.acquire("independent-new-owner", 30)
        self.assertEqual(new_token.generation, self.ready["generation"] + 1)
        self.assertEqual(new_token.process_id, os.getpid())
        before = facts(self.path)
        for operation, arguments in (("round", {}), ("deposit", {"id": "forbidden-old-funding"}),
                                     ("submit", {"id": "forbidden-old-order"}), ("renew", {})):
            self.assert_fenced(operation, {"writer_fenced"}, **arguments)
        raw = self.request("raw_update")
        self.assertFalse(raw["ok"], raw)
        self.assertEqual(raw["error_type"], "OperationalError")
        self.assertIn("no such function: uta_writer_fence_v1", raw["error_message"])
        after = facts(self.path)
        self.record("after-fault", after)
        self.assertEqual(before["tables"], after["tables"])
        current = ExchangeService(Database(self.path).for_writer(new_token), {"USD": 8}, **policy())
        current.deposit("alice", "new-owner-legitimate-funding", "USD", D(1))
        with raw_read(self.path) as connection:
            self.assertEqual(connection.execute("SELECT units FROM ledger_balances WHERE account='customer:alice' AND asset='USD'").fetchone()[0], "100100000000")
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_orders").fetchone()[0], 1)
        self.record("new-owner-positive-control", facts(self.path))

    def test_warm_proof_cannot_renew_an_actually_expired_lease_or_commit(self):
        self.assertTrue(self.request("renew", ttl=.05)["ok"])
        deadline = monotonic() + 2
        while self.fence.status()["active"] and monotonic() < deadline:
            sleep(.005)
        expired = self.fence.status()
        self.assertFalse(expired["active"])
        self.assertEqual(expired["generation"], self.ready["generation"])
        before = facts(self.path)
        for operation, arguments in (("renew", {}), ("round", {}), ("deposit", {"id": "expired-funding"}),
                                     ("submit", {"id": "expired-order"})):
            self.assert_fenced(operation, {"lease_expired"}, **arguments)
        after = facts(self.path)
        self.record("after-fault", after)
        self.assertEqual(before, after)
        self.assertEqual(self.fence.status()["expires_ns"], expired["expires_ns"])

    def corrupt_trigger(self, kind):
        with sqlite3.connect(self.path) as connection:
            if kind == "audit":
                name = "audit_order_requires_decision"
                sql = connection.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?", (name,)).fetchone()[0]
            else:
                prefix = "writer_fence_data_%" if kind != "control" else "writer_fence_%"
                table = "ledger_balances" if kind != "control" else "writer_fence_lease"
                name, sql = connection.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' AND tbl_name=? AND name LIKE ? ORDER BY name LIMIT 1", (table, prefix)).fetchone()
            connection.execute('DROP TRIGGER "' + name + '"')
            if kind == "weakened":
                connection.execute(sql[:sql.index(" BEGIN")] + " BEGIN SELECT 1; END")
        return name, sql

    def check_corruption(self, kind, code):
        before = facts(self.path)
        name, original_sql = self.corrupt_trigger(kind)
        corrupted = facts(self.path)
        self.record("injected-corruption", {"name": name, "original_sql": original_sql, "facts": corrupted})
        self.assertEqual(before["tables"], corrupted["tables"])
        failed = self.assert_fenced("round", {code})
        self.assertEqual(failed["stats"]["hits"], self.ready["stats"]["hits"])
        self.assert_fenced("submit", {code}, id="after-corrupt-order")
        if kind != "audit":
            self.assert_fenced("deposit", {code}, id="after-corrupt-funding")
            background = self.request("background_failure")
            self.assertTrue(background["ok"], background)
            self.assertEqual(background["result"], {"state": "blocked", "reason": "worker_failure", "emergency_halt_committed": False})
        after = facts(self.path)
        self.record("after-fault", after)
        self.assertEqual(corrupted, after, "fault must not be repaired or financial state mutated")
        with raw_read(self.path) as connection:
            row = connection.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?", (name,)).fetchone()
            self.assertTrue(row is None or row[0] != original_sql)

    def test_warm_hit_does_not_mask_missing_persistent_financial_guard(self):
        self.check_corruption("missing", "fence_guard_corrupt")

    def test_warm_hit_does_not_mask_weakened_same_name_financial_guard(self):
        self.check_corruption("weakened", "fence_guard_corrupt")

    def test_warm_hit_does_not_mask_fence_control_guard_corruption(self):
        self.check_corruption("control", "fence_control_corrupt")

    def test_warm_hit_still_validates_required_audit_guards(self):
        self.check_corruption("audit", "audit_schema_corrupt")

    def test_full_risk_row_and_model_table_definition_invalidate_without_account_version(self):
        with raw_read(self.path) as connection:
            original_version = connection.execute("SELECT version FROM uta_accounts WHERE account_id='alice'").fetchone()[0]
        for operation in ("risk_revision", "table_definition"):
            with self.subTest(operation=operation):
                self.assertTrue(self.request(operation)["ok"])
                recomputed = self.request("round")
                self.assertTrue(recomputed["ok"], recomputed)
                self.assertEqual(recomputed["result"]["normal_cache"]["skipped"], 0)
                self.assertEqual(recomputed["result"]["normal_cache"]["supervised"], 1)
                self.assertEqual(self.request("round")["result"]["normal_cache"]["skipped"], 1)
                with raw_read(self.path) as connection:
                    self.assertEqual(connection.execute("SELECT version FROM uta_accounts WHERE account_id='alice'").fetchone()[0], original_version)
        self.record("after-metadata-probes", facts(self.path))

    def test_warm_miss_with_failed_or_unknown_commit_cannot_publish_new_proof(self):
        for mode in ("deferred_constraint", "response_lost"):
            with self.subTest(mode=mode):
                self.assertTrue(self.request("delete_risk_row")["ok"])
                before = facts(self.path)
                self.assertTrue(self.request("arm_proof_fault", mode=mode)["ok"])
                result = self.request("round")
                self.assertFalse(result["ok"], result)
                self.assertEqual(result["error_type"], "IntegrityError" if mode == "deferred_constraint" else "ConnectionError")
                self.assertEqual(result["stats"]["size"], 0)
                actual = facts(self.path)  # Query the original persisted obligation BEFORE retrying.
                self.record("after-" + mode, actual)
                if mode == "deferred_constraint":
                    self.assertEqual(before, actual)
                else:
                    self.assertEqual(len(actual["tables"]["uta_liquidation_accounts"]), 1)
                    self.assertEqual(actual["tables"]["uta_liquidation_accounts"][0][1], "NORMAL")
                for table in ("ledger_events", "ledger_postings", "ledger_balances", "uta_accounts", "uta_orders", "uta_fills", "uta_events"):
                    self.assertEqual(before["tables"][table], actual["tables"][table], table)
                fresh = self.request("round")
                self.assertTrue(fresh["ok"], fresh)
                self.assertEqual(fresh["stats"]["size"], 1)
                self.assertEqual(fresh["result"]["normal_cache"]["supervised"], 1)
                self.assertEqual(self.request("round")["result"]["normal_cache"]["skipped"], 1)


if __name__ == "__main__":
    unittest.main()
