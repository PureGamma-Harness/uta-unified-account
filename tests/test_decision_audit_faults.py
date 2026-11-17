"""Independent real-storage failures of historical decision evidence."""
from __future__ import annotations

from contextlib import closing, contextmanager
from datetime import datetime, timezone
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory
from time import monotonic, sleep
import unittest
from unittest.mock import patch

from uta.decision_audit import DecisionAudit, DecisionAuditError
from uta.market import MarketSnapshot
from uta.matching import Matcher
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ExchangeService, ServiceError
from uta.storage import Database


NOW = datetime(2026, 11, 16, tzinfo=timezone.utc)


class AuditFaultDatabase(Database):
    lose_commit_response = False

    @contextmanager
    def transaction(self):
        with super().transaction() as connection:
            yield connection
        if self.lose_commit_response:
            self.lose_commit_response = False
            raise ConnectionError("synthetic audit transaction response lost after actual SQLite COMMIT")


def snapshot(path):
    with closing(sqlite3.connect(Path(path).as_uri() + "?mode=ro", uri=True)) as connection:
        schema = connection.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
        tables = [row[1] for row in schema if row[0] == "table"]
        return schema, {name: sorted(connection.execute('SELECT * FROM "' + name.replace('"', '""') + '"').fetchall(), key=repr)
                        for name in tables}


class DecisionAuditFaultTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.path = self.directory / "audit.sqlite3"
        self.database = AuditFaultDatabase(self.path)
        self.legacy = self.open(audited=False)
        for account in ("alice", "bob"):
            self.legacy.create_account(account)
            self.legacy.deposit(account, "seed", "USD", D(1000))
        self.legacy.publish_market(self.market())
        self.legacy.set_kill_switch(False)
        self.matcher = Matcher(self.legacy)

    def open(self, *, audited=True):
        return ExchangeService(self.database, {"USD": 8}, clock=lambda: NOW, decision_audit=audited)

    @staticmethod
    def market(version=1, mark="100"):
        return MarketSnapshot(version, NOW, {"USD": AssetSpec(D(1), D(1))},
                              {"BTC-PERP": InstrumentSpec(D(mark), D(".1"), D(".05"))})

    def deferred_failure(self):
        with self.database.transaction() as connection:
            connection.execute("CREATE TABLE audit_fault_parent (id INTEGER PRIMARY KEY)")
            connection.execute("CREATE TABLE audit_fault_child (id INTEGER REFERENCES audit_fault_parent(id) DEFERRABLE INITIALLY DEFERRED)")

    def paired(self, service):
        service.submit_order("alice", "buy", "BTC-PERP", D(2), D(100))
        service.submit_order("bob", "sell", "BTC-PERP", D(-1), D(100))
        return Matcher(service)

    def test_failed_explicit_upgrade_rolls_back_schema_columns_archives_and_capability(self):
        self.deferred_failure()
        before = snapshot(self.path)
        original = DecisionAudit.install
        def fail_at_commit(audit, connection, **kwargs):
            original(audit, connection, **kwargs)
            connection.execute("INSERT INTO audit_fault_child VALUES (999)")
        with patch.object(DecisionAudit, "install", new=fail_at_commit):
            with self.assertRaises(sqlite3.IntegrityError):
                self.open()
        self.assertEqual(snapshot(self.path), before)
        with self.database.read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT version FROM uta_schema").fetchone()[0], 2)
            self.assertNotIn("admission_decision_id", {row[1] for row in connection.execute("PRAGMA table_info(uta_orders)")})
        current = self.open()
        self.assertIsNotNone(current.audit)
        with self.assertRaises(ServiceError) as caught:
            self.open(audited=False)
        self.assertEqual(caught.exception.code, "schema_version")

    def test_partial_audit_metadata_does_not_trigger_automatic_upgrade_or_repair(self):
        with self.database.transaction() as connection:
            connection.execute("CREATE TABLE uta_code_artifacts (artifact_id TEXT PRIMARY KEY,manifest TEXT NOT NULL)")
        before = snapshot(self.path)
        with self.assertRaises(DecisionAuditError) as caught:
            self.open()
        self.assertEqual(caught.exception.code, "audit_partial_schema")
        self.assertEqual(snapshot(self.path), before)

    def test_real_commit_failure_rolls_back_order_and_decision_then_original_id_converges_once(self):
        self.deferred_failure()
        current = self.open()
        before = snapshot(self.path)
        original = current.audit.record
        def fail_at_commit(connection, **kwargs):
            original(connection, **kwargs)
            connection.execute("INSERT INTO audit_fault_child VALUES (999)")
        with patch.object(current.audit, "record", side_effect=fail_at_commit):
            with self.assertRaises(sqlite3.IntegrityError):
                current.submit_order("alice", "one", "BTC-PERP", D(1), D(100))
        self.assertEqual(snapshot(self.path), before)
        accepted = current.submit_order("alice", "one", "BTC-PERP", D(1), D(100))
        self.assertEqual(D(accepted["reserved_margin"]), D("10.04"))
        after = snapshot(self.path)
        self.assertEqual(current.submit_order("alice", "one", "BTC-PERP", D(1), D(100)), accepted)
        self.assertEqual(snapshot(self.path), after)
        self.assertEqual(len(after[1]["uta_risk_decisions"]), 1)

    def test_paired_match_commit_failure_rolls_back_two_sides_ledger_and_all_decision_refs(self):
        self.deferred_failure()
        current = self.open()
        matcher = self.paired(current)
        before = snapshot(self.path)
        original = current.audit.record
        def fail_at_commit(connection, **kwargs):
            original(connection, **kwargs)
            if kwargs["kind"] == "FILL_CONFIRMED" and kwargs["account_id"] == "bob":
                connection.execute("INSERT INTO audit_fault_child VALUES (999)")
        with patch.object(current.audit, "record", side_effect=fail_at_commit):
            with self.assertRaises(sqlite3.IntegrityError):
                matcher.match_once("BTC-PERP")
        self.assertEqual(snapshot(self.path), before)
        matcher.match_once("BTC-PERP")
        self.assertEqual(len(matcher.trades()), 1)
        self.assertEqual(current.account("alice")["balances"]["USD"], "999.96")
        self.assertEqual(current.account("bob")["balances"]["USD"], "999.96")
        with self.database.read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_risk_decisions").fetchone()[0], 4)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_fills WHERE execution_decision_id IS NULL").fetchone()[0], 0)
        current.ledger.verify()
        matcher.verify(strict=True)

    def test_match_commit_response_loss_reopens_with_exact_receipts_and_no_duplicate_audit_or_cash(self):
        current = self.open()
        matcher = self.paired(current)
        self.database.lose_commit_response = True
        with self.assertRaises(ConnectionError):
            matcher.match_once("BTC-PERP")
        committed = snapshot(self.path)
        cold = self.open()
        recovered = Matcher(cold)
        trades = recovered.trades()
        self.assertEqual(len(trades), 1)
        trade = trades[0]
        for account, order, fill, quantity in (("alice", "buy", trade["buy_fill_id"], D(1)),
                                               ("bob", "sell", trade["sell_fill_id"], D(-1))):
            receipt = cold.apply_fill(account, order, fill, quantity, D(100))
            self.assertIsNotNone(receipt["execution_decision_id"])
        recovered.match_once("BTC-PERP")
        self.assertEqual(snapshot(self.path), committed)
        recovered.verify(strict=True)

    def test_market_publication_commit_failure_rolls_back_full_history_current_quote_and_event(self):
        self.deferred_failure()
        current = self.open()
        before = snapshot(self.path)
        original = current._publish_market
        def fail_at_commit(connection, market, **kwargs):
            result = original(connection, market, **kwargs)
            connection.execute("INSERT INTO audit_fault_child VALUES (999)")
            return result
        with patch.object(current, "_publish_market", side_effect=fail_at_commit):
            with self.assertRaises(sqlite3.IntegrityError):
                current.publish_market(self.market(2, "200"))
        self.assertEqual(snapshot(self.path), before)
        current.publish_market(self.market(2, "200"))
        with self.database.read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_market_history").fetchone()[0], 2)

    def test_valid_names_with_weakened_required_reference_guard_fail_closed_without_repair(self):
        self.open()
        with self.database.transaction() as connection:
            connection.execute("DROP TRIGGER audit_order_requires_decision")
            connection.execute("CREATE TRIGGER audit_order_requires_decision BEFORE INSERT ON uta_orders BEGIN SELECT 1; END")
        before = snapshot(self.path)
        with self.assertRaises(DecisionAuditError) as caught:
            self.open()
        self.assertEqual(caught.exception.code, "audit_schema_corrupt")
        self.assertEqual(snapshot(self.path), before)

    def test_historical_market_code_and_policy_body_corruption_never_returns_replay_matches(self):
        current = self.open()
        accepted = current.submit_order("alice", "one", "BTC-PERP", D(1), D(100))
        evidence = current.audit.decision(accepted["decision_id"])
        cases = (("uta_market_history", "payload", "snapshot_id", evidence["market_snapshot_id"]),
                 ("uta_code_artifacts", "manifest", "artifact_id", evidence["artifact_id"]),
                 ("uta_risk_policies", "payload", "policy_id", evidence["policy_id"]))
        for table, body, key, identity in cases:
            with self.subTest(table=table):
                with self.database.read_transaction() as connection:
                    original = connection.execute(f"SELECT {body} FROM {table} WHERE {key}=?", (identity,)).fetchone()[0]
                    guard_sql = connection.execute("SELECT sql FROM sqlite_master WHERE name=?", (f"audit_{table}_no_update",)).fetchone()[0]
                # Deliberate offline corruption of stored bytes. Restore the
                # exact guard definition before exercising the reader.
                with self.database.transaction() as connection:
                    connection.execute(f"DROP TRIGGER audit_{table}_no_update")
                    connection.execute(f"UPDATE {table} SET {body}=? WHERE {key}=?", (original + " ", identity))
                    connection.execute(guard_sql)
                with self.assertRaises(DecisionAuditError) as caught:
                    current.audit.replay(accepted["decision_id"])
                self.assertIn(caught.exception.code, {"audit_content_conflict", "replay_artifact_unavailable"})
                with self.database.transaction() as connection:
                    connection.execute(f"DROP TRIGGER audit_{table}_no_update")
                    connection.execute(f"UPDATE {table} SET {body}=? WHERE {key}=?", (original, identity))
                    connection.execute(guard_sql)

    def test_real_sqlite_full_after_decision_insert_never_commits_an_order_without_its_audit(self):
        with self.database.transaction() as connection:
            connection.execute("CREATE TABLE audit_fault_blob (value BLOB)")
        current = self.open()
        with self.database.read_transaction() as connection:
            page_limit = connection.execute("PRAGMA page_count").fetchone()[0] + 16
            allocation = connection.execute("PRAGMA page_size").fetchone()[0] * 64
        before = snapshot(self.path)
        connect, record = self.database._connect, current.audit.record
        inserted = []
        def limited_connect():
            connection = connect()
            connection.execute("PRAGMA max_page_count=" + str(page_limit))
            return connection
        def full_after_record(connection, **kwargs):
            record(connection, **kwargs)
            inserted.append(kwargs["decision_id"])
            connection.execute("INSERT INTO audit_fault_blob VALUES (zeroblob(?))", (allocation,))
        with patch.object(self.database, "_connect", side_effect=limited_connect), \
                patch.object(current.audit, "record", side_effect=full_after_record):
            with self.assertRaises(ServiceError) as caught:
                current.submit_order("alice", "full", "BTC-PERP", D(1), D(100))
        self.assertEqual(caught.exception.code, "storage_unavailable")
        self.assertTrue(inserted, "SQLite FULL must occur after the actual audit insert")
        pending, seen, actual_full = [caught.exception], set(), False
        while pending:
            error = pending.pop()
            if error is None or id(error) in seen:
                continue
            seen.add(id(error))
            actual_full |= isinstance(error, sqlite3.Error) and (
                getattr(error, "sqlite_errorcode", None) == getattr(sqlite3, "SQLITE_FULL", 13)
                or "database or disk is full" in str(error))
            pending.extend((error.__cause__, error.__context__))
        self.assertTrue(actual_full)
        self.assertEqual(snapshot(self.path), before)
        current.submit_order("alice", "full", "BTC-PERP", D(1), D(100))
        with self.database.read_transaction() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_risk_decisions").fetchone()[0], 1)

    def isolated_replay(self, source, identity, *, optimize=False):
        program = r'''
import json, sys
sys.path.insert(0,sys.argv[1])
from uta.decision_audit import DecisionAudit, DecisionAuditError
from uta.storage import Database
audit = DecisionAudit(Database(sys.argv[2]))
try:
    result = audit.replay(sys.argv[3])
except DecisionAuditError as error:
    print(json.dumps({"code":error.code,"calculated":False}),flush=True)
else:
    print(json.dumps({"calculated":True,"result":result}),flush=True)
'''
        command = [sys.executable, "-I"] + (["-O"] if optimize else [])
        child = subprocess.run(command + ["-c", program, str(source), str(self.path), identity],
                               capture_output=True, text=True, timeout=15)
        self.assertEqual(child.returncode, 0, child.stderr)
        result = json.loads(child.stdout)
        self.assertEqual(result, {"code": "replay_engine_mismatch", "calculated": False})

    def test_identical_math_from_a_different_real_source_release_is_not_an_authoritative_replay(self):
        current = self.open()
        accepted = current.submit_order("alice", "one", "BTC-PERP", D(1), D(100))
        import uta.service
        source = Path(uta.service.__file__).resolve().parent.parent
        variant = self.directory / "different-release"
        shutil.copytree(source / "uta", variant / "uta", ignore=shutil.ignore_patterns("__pycache__"))
        with (variant / "uta" / "service.py").open("a") as output:
            output.write("\n# Independent release variant; mathematical expressions are unchanged.\n")
        before = snapshot(self.path)
        self.isolated_replay(variant, accepted["decision_id"])
        self.assertEqual(snapshot(self.path), before)

    def test_same_source_under_an_actual_optimized_interpreter_cannot_replay_unoptimized_artifact(self):
        current = self.open()
        accepted = current.submit_order("alice", "one", "BTC-PERP", D(1), D(100))
        import uta.service
        self.isolated_replay(Path(uta.service.__file__).resolve().parent.parent,
                             accepted["decision_id"], optimize=True)

    def test_actual_ad3_process_held_before_upgrade_cannot_insert_orders_or_fills_without_required_refs(self):
        self.legacy.submit_order("alice", "old-buy", "BTC-PERP", D(2), D(100))
        self.legacy.submit_order("bob", "old-sell", "BTC-PERP", D(-1), D(100))
        import uta.service
        repository = Path(uta.service.__file__).resolve().parent.parent
        archive = repository / "tests" / "fixtures" / "legacy_ad3f5b8_uta.tar.gz"
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(),
                         "af1ffcbdb78d4f2c789f049cb4f3c61e75724a10a1f8f55d0d1ed09af1cda265")
        legacy = self.directory / "actual-ad3"
        legacy.mkdir()
        with tarfile.open(archive) as package:
            for member in package.getmembers():
                name = Path(member.name)
                self.assertFalse(name.is_absolute() or ".." in name.parts)
                self.assertTrue(member.isdir() or member.isfile())
                destination = legacy / name
                if member.isdir():
                    destination.mkdir(parents=True, exist_ok=True)
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with package.extractfile(member) as content:
                        destination.write_bytes(content.read())
        ready, release = self.directory / "legacy-ready", self.directory / "legacy-release"
        program = r'''
import hashlib,json,sys,time,sqlite3
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime
sys.path.insert(0,sys.argv[1])
import uta.storage
from uta.service import ExchangeService
from uta.storage import Database
from uta.matching import Matcher
assert not hasattr(Database,"for_writer")
assert hashlib.sha256(Path(uta.storage.__file__).read_bytes()).hexdigest()=="ad0c34e97be43fa3a0ba648a84664f37a9944524dd4ab2802f20bdf0686c8feb"
service=ExchangeService(Database(sys.argv[2]),{"USD":8},clock=lambda:datetime.fromisoformat(sys.argv[3]))
matcher=Matcher(service)
Path(sys.argv[4]).touch()
deadline=time.monotonic()+10
while not Path(sys.argv[5]).exists():
    if time.monotonic()>deadline: raise RuntimeError("legacy release timed out")
    time.sleep(.01)
outcomes=[]
for name,operation in (("order",lambda:service.submit_order("alice","unaudited","BTC-PERP",D(1),D(100))),
                       ("fill",lambda:service.apply_fill("alice","old-buy","unaudited-fill",D(1),D(100))),
                       ("match",lambda:matcher.match_once("BTC-PERP"))):
    try: operation()
    except Exception as error:
        pending,seen,sql_errors=[error],set(),[]
        while pending:
            value=pending.pop()
            if value is None or id(value) in seen: continue
            seen.add(id(value))
            if isinstance(value,sqlite3.Error): sql_errors.append(str(value))
            pending.extend((value.__cause__,value.__context__))
        if not sql_errors: raise
        outcomes.append([name,"blocked",sql_errors])
    else: outcomes.append([name,"wrote"])
print(json.dumps(outcomes),flush=True)
'''
        child = subprocess.Popen([sys.executable, "-I", "-c", program, str(legacy), str(self.path),
                                  NOW.isoformat(), str(ready), str(release)],
                                 text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = monotonic() + 10
            while not ready.exists() and child.poll() is None and monotonic() < deadline:
                sleep(.01)
            self.assertTrue(ready.exists())
            current = self.open()
            before = snapshot(self.path)
            release.touch()
            output, errors = child.communicate(timeout=10)
            self.assertEqual(child.returncode, 0, errors)
            outcomes = json.loads(output)
            self.assertEqual([row[:2] for row in outcomes], [["order", "blocked"], ["fill", "blocked"], ["match", "blocked"]])
            self.assertIn("audit decision required", outcomes[0][2][0])
            self.assertTrue(all(row[2] for row in outcomes), "legacy refusal must have an actual SQLite cause")
            self.assertEqual(snapshot(self.path), before)
            current.ledger.verify()
        finally:
            if child.poll() is None:
                child.kill()
            child.communicate(timeout=5)


if __name__ == "__main__":
    unittest.main()
