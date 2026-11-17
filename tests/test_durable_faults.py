"""Independent managed-writer and durable-command failures; synthetic funds only."""
from __future__ import annotations

from contextlib import closing, contextmanager
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import fcntl
import hashlib
import json
import os
from pathlib import Path
import select
import shutil
import signal
import sqlite3
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory
from threading import Event, Thread, current_thread
from time import monotonic, sleep
import unittest
from unittest.mock import patch

from uta.credit import CreditService
from uta.durable_commands import CommandExecutionError, QueueStore
from uta.ledger import Posting
from uta.market import MarketSnapshot
from uta.matching import Matcher
from uta.models import AssetSpec, InstrumentSpec
from uta.service import ExchangeService, ServiceError
from uta.storage import Database, StorageError
from uta.writer_fence import WriterFence, WriterFenceError, WriterToken


NOW = datetime(2026, 11, 16, tzinfo=timezone.utc)
FINANCIAL_TABLES = (
    "uta_accounts", "uta_orders", "uta_positions", "uta_fills", "uta_events",
    "uta_deposits", "uta_liabilities", "ledger_events", "ledger_postings",
    "ledger_balances", "uta_matches", "credit_commands",
)


def chain(error):
    pending, seen = [error], set()
    while pending:
        value = pending.pop()
        if value is None or id(value) in seen:
            continue
        seen.add(id(value))
        yield value
        pending.extend((value.__cause__, value.__context__))


def financial_snapshot(path):
    """Observe committed authority without constructing/migrating a service."""
    with closing(sqlite3.connect(Path(path).as_uri() + "?mode=ro", uri=True)) as connection:
        existing = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        return {name: sorted(connection.execute("SELECT * FROM " + name).fetchall(), key=repr)
                for name in FINANCIAL_TABLES if name in existing}


def bound_router_shared_flocks(pid, identity, path, file_identity):
    """Read kernel evidence for this exact child's own router-lock FD only.

    No UTA worker function is replaced. A read/stop race is handled by the
    caller checking this evidence again after the bound pidfd is stopped.
    """
    from uta.durable_process import _process_identity
    def require_binding():
        current = _process_identity(pid)
        if any(current[key] != identity[key] for key in ("pid", "start_ticks", "boot_id", "uid")):
            raise AssertionError("selected worker birth identity changed")
        return current
    require_binding()
    current = path.stat(follow_symlinks=False)
    if (current.st_dev, current.st_ino) != file_identity:
        raise AssertionError("router lock file identity changed")
    records = []
    for entry in Path(f"/proc/{pid}/fdinfo").iterdir():
        descriptor = Path(f"/proc/{pid}/fd") / entry.name
        try:
            if os.readlink(descriptor) != str(path):
                continue
            details = descriptor.stat()
            if (details.st_dev, details.st_ino) != file_identity:
                raise AssertionError("worker lock descriptor targets a different inode")
            content = entry.read_text()
        except FileNotFoundError:
            continue  # A live worker may close this particular FD meanwhile.
        for line in content.splitlines():
            fields = line.split()
            if (len(fields) == 9 and fields[0] == "lock:"
                    and fields[2:5] == ["FLOCK", "ADVISORY", "READ"]
                    and fields[5] == str(pid) and fields[7:] == ["0", "EOF"]):
                device = fields[6].split(":")
                if (len(device) != 3 or int(device[0], 16) != os.major(current.st_dev)
                        or int(device[1], 16) != os.minor(current.st_dev)
                        or int(device[2]) != current.st_ino):
                    raise AssertionError("kernel lock record differs from router lock identity")
                records.append({"fd": int(entry.name), "kernel_record": line,
                                "device": current.st_dev, "inode": current.st_ino})
    require_binding()
    return records


def router_writer_available_without_dml(path):
    """Probe real SQLite writer availability; do not install an owner or write.

    The stopped child must hold SH before its financial write transaction, or
    the subsequent durable enqueue could itself wait for lease recovery.
    """
    with closing(sqlite3.connect(Path(path).as_uri() + "?mode=rw", uri=True,
                                 timeout=0, isolation_level=None)) as connection:
        changes = connection.total_changes
        try:
            connection.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as error:
            code = getattr(error, "sqlite_errorcode", None)
            if type(code) is int and code & 255 == 5:  # Native SQLITE_BUSY.
                return {"available": False, "classification": "sqlite_busy", "native_errorcode": code}
            if (not hasattr(error, "sqlite_errorcode") and type(error) is sqlite3.OperationalError
                    and error.args == ("database is locked",)):
                return {"available": False, "classification": "sqlite_busy_legacy_builtin", "native_errorcode": None}
            raise
        assert connection.in_transaction
        connection.rollback()
        assert not connection.in_transaction and connection.total_changes == changes
        return {"available": True, "classification": "begin_immediate_rolled_back_zero_dml",
                "native_errorcode": None}


class DurableFaultFixture(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.path = self.directory / "exchange.sqlite3"
        self.database = Database(self.path)
        self.service = self.open_service(self.database)
        for account in ("alice", "bob"):
            self.service.create_account(account)
            self.service.deposit(account, "seed", "USD", D(1000))
        self.service.publish_market(MarketSnapshot(1, NOW,
            {"USD": AssetSpec(D(1), D(1))},
            {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))}))
        self.service.set_kill_switch(False)
        self.matcher = Matcher(self.service)

    @staticmethod
    def open_service(database):
        return ExchangeService(database, {"USD": 8}, clock=lambda: NOW)

    def managed(self, owner="writer-A", ttl=30, database=None):
        database = database or self.database
        fence = WriterFence(database)
        fence.enable("synthetic-authority")
        token = fence.acquire(owner, ttl)
        return fence, token, self.open_service(database.for_writer(token))

    def fenced(self, function, *args, **kwargs):
        with self.assertRaises(Exception) as caught:
            function(*args, **kwargs)
        self.assertTrue(any(isinstance(error, WriterFenceError) for error in chain(caught.exception)),
                        f"expected a storage fencing cause, got {caught.exception!r}")
        return caught.exception

    def child(self, code, *arguments, timeout=15):
        import uta.service
        root = Path(uta.service.__file__).resolve().parent.parent
        return subprocess.run([sys.executable, "-c", code, str(self.path), NOW.isoformat(),
                               *map(str, arguments)], cwd=root, text=True,
                              capture_output=True, timeout=timeout)

    def wait_file(self, path, process, timeout=8):
        deadline = monotonic() + timeout
        while not path.exists() and process.poll() is None and monotonic() < deadline:
            sleep(.01)
        self.assertTrue(path.exists(), f"child exited or timed out before publishing {path.name}")

    @staticmethod
    def cleanup_child(process):
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=5)


class StorageFencingFaultTests(DurableFaultFixture):
    def test_enabling_managed_mode_fences_existing_service_matcher_ledger_and_plain_database(self):
        self.service.submit_order("alice", "buy", "BTC-PERP", D(1), D(100))
        self.service.submit_order("bob", "sell", "BTC-PERP", D(-1), D(100))
        credit = CreditService(self.service)
        credit.configure_asset_limit("USD", D(100))
        credit.configure_limit("alice", "USD", D(100))
        credit.fund_pool("fund", "USD", D(100), source_reference="synthetic:pool")
        credit.borrow("alice", "borrow", "USD", D(10))
        _, _, current = self.managed()
        before = financial_snapshot(self.path)
        self.fenced(self.service.deposit, "alice", "legacy-deposit", "USD", D(1))
        self.fenced(self.service.submit_order, "alice", "legacy-buy", "BTC-PERP", D(1), D(100))
        self.fenced(self.matcher.match_once, "BTC-PERP")
        self.fenced(self.service.ledger.post, "legacy-post", [
            Posting("customer:alice", "USD", D(1)), Posting("system:custody", "USD", D(-1))])
        self.fenced(credit.repay, "alice", "legacy-repay", "USD", D(1))
        def plain_database_write():
            with Database(self.path).transaction() as connection:
                connection.execute("UPDATE ledger_balances SET units='0'")
        self.fenced(plain_database_write)
        self.assertEqual(financial_snapshot(self.path), before)
        # Ordinary reads stay available; the current fenced writer can settle.
        self.assertEqual(self.service.account("alice")["balances"]["USD"], "1010")
        Matcher(current).match_once("BTC-PERP")
        self.assertEqual(len(Matcher(current).trades()), 1)
        self.assertEqual(current.account("alice")["positions"]["BTC-PERP"]["quantity"], "1")
        self.assertEqual(current.account("bob")["positions"]["BTC-PERP"]["quantity"], "-1")
        current.ledger.verify()

    def test_managed_ledger_rejects_a_raw_unguarded_sqlite_transaction(self):
        self.managed()
        before = financial_snapshot(self.path)
        with closing(sqlite3.connect(self.path, isolation_level=None)) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                self.fenced(self.service.ledger.post, "unguarded-post", [
                    Posting("customer:alice", "USD", D(1)),
                    Posting("system:custody", "USD", D(-1))], connection=connection)
            finally:
                connection.rollback()
        self.assertEqual(financial_snapshot(self.path), before)

    def test_token_bound_writer_cannot_fall_back_to_legacy_after_restoring_pre_enable_database(self):
        backup = self.directory / "pre-enable.sqlite3"
        with closing(sqlite3.connect(self.path)) as source, closing(sqlite3.connect(backup)) as target:
            source.backup(target)
        _, _, current = self.managed()
        shutil.copyfile(backup, self.path)
        before = financial_snapshot(self.path)
        self.fenced(current.deposit, "alice", "after-inconsistent-restore", "USD", D(1))
        self.assertEqual(financial_snapshot(self.path), before)


class ActualLegacyBinaryFaultTests(DurableFaultFixture):
    """Run the immutable pre-fencing package in an isolated real interpreter."""
    LEGACY_COMMIT = "ad3f5b894f96ed6857a061b71290047ae1d4d0e7"
    LEGACY_ARCHIVE_SHA256 = "af1ffcbdb78d4f2c789f049cb4f3c61e75724a10a1f8f55d0d1ed09af1cda265"
    LEGACY_SOURCES = {
        "storage": "ad0c34e97be43fa3a0ba648a84664f37a9944524dd4ab2802f20bdf0686c8feb",
        "service": "980dddc853f23dd12625a112ae1d9f192473e1fd213db985462f209d160d6397",
    }

    LEGACY_PROGRAM = r'''
import hashlib, json, sys, time
from datetime import datetime
from decimal import Decimal as D
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import uta.storage, uta.service
from uta.ledger import Posting
from uta.matching import Matcher
from uta.service import ExchangeService
from uta.storage import Database
root = Path(sys.argv[1]).resolve()
sources = {}
for name, module in (("storage", uta.storage), ("service", uta.service)):
    path = Path(module.__file__).resolve()
    assert root in path.parents, (name, str(path), str(root))
    sources[name] = {"path":str(path), "sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
assert not hasattr(Database, "for_writer"), "current Database accidentally substituted for the actual legacy binary"
def describe(error):
    import sqlite3
    pending, seen, values = [error], set(), []
    while pending:
        value = pending.pop()
        if value is None or id(value) in seen: continue
        seen.add(id(value))
        values.append({"type":type(value).__name__, "message":str(value),
                       "code":getattr(value,"code",None), "sqlite":isinstance(value,sqlite3.Error)})
        pending.extend((value.__cause__,value.__context__))
    return values
try:
    service = ExchangeService(Database(sys.argv[2]), {"USD":8}, clock=lambda:datetime.fromisoformat(sys.argv[3]))
    matcher, ledger = Matcher(service), service.ledger
except Exception as error:
    if sys.argv[4] == "waiting": raise
    print(json.dumps({"sources":sources,"stage":"startup_blocked","errors":describe(error)}),flush=True)
    raise SystemExit(0)
if sys.argv[4] == "waiting":
    Path(sys.argv[5]).write_text(json.dumps({"sources":sources,"stage":"ready"}))
    deadline = time.monotonic()+15
    while not Path(sys.argv[6]).exists():
        if time.monotonic()>deadline: raise RuntimeError("legacy binary was not released")
        time.sleep(.01)
operations = (
    ("deposit",lambda:service.deposit("alice","actual-legacy-deposit","USD",D(1))),
    ("order",lambda:service.submit_order("alice","actual-legacy-order","BTC-PERP",D(1),D(100))),
    ("ledger",lambda:ledger.post("actual-legacy-post",[
        Posting("customer:alice","USD",D(1)),Posting("system:custody","USD",D(-1))])),
    ("match",lambda:matcher.match_once("BTC-PERP")),
)
outcomes = []
for name, operation in operations:
    try:
        operation()
    except Exception as error:
        outcomes.append({"operation":name,"state":"blocked","errors":describe(error)})
    else:
        outcomes.append({"operation":name,"state":"wrote"})
print(json.dumps({"sources":sources,"stage":"executed","outcomes":outcomes}),flush=True)
'''

    def setUp(self):
        super().setUp()
        self.service.submit_order("alice", "legacy-resting-buy", "BTC-PERP", D(1), D(100))
        self.service.submit_order("bob", "legacy-resting-sell", "BTC-PERP", D(-1), D(100))
        self.legacy = self.directory / "actual-legacy"
        self.legacy.mkdir()
        archive_path = self.directory / "legacy.tar"
        import uta.service
        repository = Path(uta.service.__file__).resolve().parent.parent
        available = subprocess.run(["git", "cat-file", "-e", self.LEGACY_COMMIT + "^{commit}"],
                                   cwd=repository, capture_output=True, text=True, timeout=10)
        if available.returncode == 0:
            archived = subprocess.run(["git", "archive", "--format=tar", "--output=" + str(archive_path),
                                       self.LEGACY_COMMIT, "uta", "LICENSE"], cwd=repository,
                                      capture_output=True, text=True, timeout=10)
            self.assertEqual(archived.returncode, 0, archived.stderr)
        else:
            # Shallow CI checkouts may lack this ancestor. Only the immutable,
            # independently checksummed git-archive fixture may substitute.
            fixture = repository / "tests" / "fixtures" / "legacy_ad3f5b8_uta.tar.gz"
            self.assertTrue(fixture.is_file(), "legacy git object and pinned archive fixture are both unavailable")
            self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest(), self.LEGACY_ARCHIVE_SHA256)
            metadata = json.loads(fixture.with_name("legacy_ad3f5b8_provenance.json").read_text())
            self.assertEqual(metadata["commit"], self.LEGACY_COMMIT)
            self.assertEqual(metadata["archive_sha256"], self.LEGACY_ARCHIVE_SHA256)
            archive_path = fixture
        with tarfile.open(archive_path) as archive:
            for member in archive.getmembers():
                name = Path(member.name)
                self.assertFalse(name.is_absolute() or ".." in name.parts)
                self.assertTrue(name.parts[0] == "uta" or member.name == "LICENSE")
                target = self.legacy / name
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    self.assertTrue(member.isfile(), "legacy archive must not introduce links or devices")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.extractfile(member) as contents:
                        target.write_bytes(contents.read())
        self.assertTrue((self.legacy / "LICENSE").is_file())

    def assert_actual_sources(self, report):
        for name in ("storage", "service"):
            source = self.legacy / "uta" / (name + ".py")
            self.assertEqual(Path(report["sources"][name]["path"]), source)
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            self.assertEqual(digest, self.LEGACY_SOURCES[name])
            self.assertEqual(report["sources"][name]["sha256"], digest)

    def assert_legacy_blocked(self, report):
        self.assert_actual_sources(report)
        self.assertFalse(report["financial_changed"], repr(report))
        if report["stage"] == "startup_blocked":
            self.assertTrue(any(error["sqlite"] for error in report["errors"]), repr(report))
        else:
            self.assertEqual([row["operation"] for row in report["outcomes"]], ["deposit", "order", "ledger", "match"])
            self.assertTrue(all(row["state"] == "blocked" for row in report["outcomes"]), repr(report))
            self.assertTrue(all(any(error["sqlite"] for error in row["errors"]) for row in report["outcomes"]), repr(report))

    def test_actual_ad3_binary_initialized_before_enable_cannot_deposit_order_post_or_match_afterwards(self):
        ready, release = self.directory / "actual-ready.json", self.directory / "actual-release"
        child = subprocess.Popen([sys.executable, "-I", "-c", self.LEGACY_PROGRAM,
            str(self.legacy), str(self.path), NOW.isoformat(), "waiting", str(ready), str(release)],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(self.cleanup_child, child)
        self.wait_file(ready, child)
        self.assert_actual_sources(json.loads(ready.read_text()))
        self.managed()
        before = financial_snapshot(self.path)
        release.touch()
        output, errors = child.communicate(timeout=15)
        self.assertEqual(child.returncode, 0, errors)
        report = json.loads(output)
        report["financial_changed"] = financial_snapshot(self.path) != before
        self.assert_legacy_blocked(report)
        self.assertEqual(financial_snapshot(self.path), before)

    def test_actual_ad3_binary_started_after_enable_cannot_write_or_reinitialize_authority(self):
        self.managed()
        before = financial_snapshot(self.path)
        child = subprocess.run([sys.executable, "-I", "-c", self.LEGACY_PROGRAM,
            str(self.legacy), str(self.path), NOW.isoformat(), "after-enable"],
            text=True, capture_output=True, timeout=15)
        self.assertEqual(child.returncode, 0, child.stderr)
        report = json.loads(child.stdout)
        report["financial_changed"] = financial_snapshot(self.path) != before
        self.assert_legacy_blocked(report)
        self.assertEqual(financial_snapshot(self.path), before)


class ShallowLegacyFixtureFaultTests(unittest.TestCase):
    def test_isolated_empty_git_checkout_runs_the_same_real_legacy_binary_assertions(self):
        """Exercise the pinned archive fallback without mocking Git or storage."""
        import uta.service
        repository = Path(uta.service.__file__).resolve().parent.parent
        with TemporaryDirectory() as temporary:
            shallow = Path(temporary)
            shutil.copytree(repository / "uta", shallow / "uta", ignore=shutil.ignore_patterns("__pycache__"))
            tests = shallow / "tests"
            fixtures = tests / "fixtures"
            fixtures.mkdir(parents=True)
            shutil.copyfile(__file__, tests / "test_durable_faults.py")
            for name in ("legacy_ad3f5b8_uta.tar.gz", "legacy_ad3f5b8_provenance.json"):
                shutil.copyfile(repository / "tests" / "fixtures" / name, fixtures / name)
            initialized = subprocess.run(["git", "init", "--quiet", str(shallow)], capture_output=True, text=True, timeout=10)
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            missing = subprocess.run(["git", "cat-file", "-e", ActualLegacyBinaryFaultTests.LEGACY_COMMIT],
                                     cwd=shallow, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(missing.returncode, 0, "isolated fixture unexpectedly contains the ancestor object")
            program = "import sys,unittest; sys.path[:0]=[sys.argv[1],sys.argv[1]+'/tests']; suite=unittest.defaultTestLoader.loadTestsFromName('test_durable_faults.ActualLegacyBinaryFaultTests'); result=unittest.TextTestRunner(verbosity=2).run(suite); raise SystemExit(not result.wasSuccessful())"
            child = subprocess.run([sys.executable, "-I", "-c", program, str(shallow)],
                                   capture_output=True, text=True, timeout=30)
            self.assertEqual(child.returncode, 0, child.stdout + child.stderr)
            self.assertIn("Ran 2 tests", child.stderr)


class LegacyManagedFormatUpgradeFaultTests(DurableFaultFixture):
    def old_managed(self, *, active=False):
        """Independent format-0 fixture, using the schema published in c05e10f.

        The controlled lease clock isolates schema migration from host timing;
        actual PID/expiry behavior is covered by the real-process tests above.
        """
        self.database = Database(self.path, fence_clock_ns=lambda: 1_000_000_000,
                                 fence_boot_id="legacy-managed-boot")
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("CREATE TABLE writer_fence_authority (singleton INTEGER PRIMARY KEY CHECK(singleton=1),format INTEGER NOT NULL CHECK(format=1),authority_id TEXT NOT NULL,canonical_path TEXT NOT NULL)")
            connection.execute("CREATE TABLE writer_fence_lease (singleton INTEGER PRIMARY KEY CHECK(singleton=1),generation INTEGER NOT NULL CHECK(generation>=0),owner_nonce TEXT,owner_pid INTEGER,boot_id TEXT NOT NULL,expires_ns INTEGER NOT NULL,observed_ns INTEGER NOT NULL)")
            connection.execute("CREATE TABLE writer_fence_events (sequence INTEGER PRIMARY KEY,kind TEXT NOT NULL,authority_id TEXT NOT NULL,owner_nonce TEXT,generation INTEGER NOT NULL,owner_pid INTEGER,boot_id TEXT NOT NULL,observed_ns INTEGER NOT NULL,expires_ns INTEGER NOT NULL)")
            connection.execute("INSERT INTO writer_fence_authority VALUES (1,1,?,?)", ("synthetic-authority", str(self.path)))
            connection.execute("INSERT INTO writer_fence_lease VALUES (1,?,?,?,?,?,?)",
                (1 if active else 0, "previous-writer" if active else None, os.getpid() if active else None,
                 "legacy-managed-boot", 31_000_000_000 if active else 1_000_000_000, 1_000_000_000))
            connection.execute("INSERT INTO writer_fence_events VALUES (1,'enabled','synthetic-authority',NULL,0,NULL,'legacy-managed-boot',1000000000,1000000000)")
            if active:
                connection.execute("INSERT INTO writer_fence_events VALUES (2,'acquired','synthetic-authority','previous-writer',1,?,'legacy-managed-boot',1000000000,31000000000)", (os.getpid(),))
            for table in ("writer_fence_authority", "writer_fence_events"):
                for action in ("UPDATE", "DELETE"):
                    connection.execute(f"CREATE TRIGGER {table}_no_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'fence authority and audit are immutable'); END")
            connection.execute("CREATE TRIGGER writer_fence_lease_no_delete BEFORE DELETE ON writer_fence_lease BEGIN SELECT RAISE(ABORT,'managed lease cannot be deleted'); END")
            connection.execute("CREATE TRIGGER writer_fence_lease_monotonic BEFORE UPDATE ON writer_fence_lease WHEN NEW.generation<OLD.generation BEGIN SELECT RAISE(ABORT,'fence generation cannot regress'); END")
        return WriterFence(self.database)

    def test_old_managed_format_requires_explicit_offline_upgrade_before_writing(self):
        fence = self.old_managed()
        before = financial_snapshot(self.path)
        self.assertEqual(fence.status()["guard_format"], 0)
        with self.assertRaises(WriterFenceError) as caught:
            fence.acquire("new-writer", 10)
        self.assertEqual(caught.exception.code, "fence_upgrade_required")
        self.assertEqual(fence.status()["guard_format"], 0)
        self.assertEqual(financial_snapshot(self.path), before)
        fence.upgrade_guards()
        self.assertEqual(fence.status()["guard_format"], 1)
        self.assertEqual(financial_snapshot(self.path), before)
        token = fence.acquire("after-explicit-upgrade", 10)
        current = self.open_service(self.database.for_writer(token))
        current.deposit("alice", "after-upgrade", "USD", D(1))
        self.assertEqual(current.account("alice")["balances"]["USD"], "1001")
        current.ledger.verify()

    def test_persistent_guard_upgrade_refuses_live_old_lease_until_explicit_release(self):
        fence = self.old_managed(active=True)
        before = financial_snapshot(self.path)
        self.assertTrue(fence.status()["active"])
        with self.assertRaises(WriterFenceError) as caught:
            fence.upgrade_guards()
        self.assertEqual(caught.exception.code, "lease_busy")
        self.assertEqual(fence.status()["guard_format"], 0)
        self.assertEqual(financial_snapshot(self.path), before)
        fence.release(WriterToken("synthetic-authority", "previous-writer", 1))
        fence.upgrade_guards()
        self.assertEqual(fence.status()["guard_format"], 1)
        self.assertEqual(financial_snapshot(self.path), before)


class PersistentGuardFaultTests(DurableFaultFixture):
    def setUp(self):
        super().setUp()
        self.fence, self.token, self.current = self.managed()

    def guard(self):
        with closing(sqlite3.connect(self.path)) as connection:
            row = connection.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' "
                "AND name LIKE 'writer_fence_data_%' AND tbl_name='ledger_balances' ORDER BY name LIMIT 1").fetchone()
        self.assertIsNotNone(row, "managed activation did not create persistent financial triggers")
        return row

    def assert_corruption_rejects_without_repair(self, missing_name=None):
        before = financial_snapshot(self.path)
        error = self.fenced(self.current.deposit, "alice", "after-guard-corruption", "USD", D(1))
        self.assertTrue(any(getattr(value, "code", None) == "fence_guard_corrupt" for value in chain(error)))
        self.fenced(self.open_service, self.database.for_writer(self.token))
        self.fenced(self.fence.enable, "synthetic-authority")
        self.assertEqual(financial_snapshot(self.path), before)
        if missing_name is not None:
            with closing(sqlite3.connect(self.path)) as connection:
                self.assertIsNone(connection.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name=?", (missing_name,)).fetchone())

    def test_missing_persistent_guard_blocks_current_writer_and_reopen_without_automatic_repair(self):
        name, _ = self.guard()
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute('DROP TRIGGER "' + name + '"')
        self.assert_corruption_rejects_without_repair(name)

    def test_same_name_weakened_persistent_guard_sql_is_rejected_without_financial_change(self):
        name, sql = self.guard()
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute('DROP TRIGGER "' + name + '"')
            connection.execute(sql[:sql.index(" BEGIN")] + " BEGIN SELECT 1; END")
        self.assert_corruption_rejects_without_repair()
        with closing(sqlite3.connect(self.path)) as connection:
            stored, = connection.execute("SELECT sql FROM sqlite_master WHERE name=?", (name,)).fetchone()
            self.assertNotEqual(stored, sql, "reopen silently replaced the damaged guard")

    def test_missing_both_guard_metadata_tables_cannot_downgrade_or_silently_upgrade_again(self):
        before = financial_snapshot(self.path)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("DROP TABLE writer_fence_guard_tables")
            connection.execute("DROP TABLE writer_fence_guard_config")
        for action in (self.fence.status, self.fence.upgrade_guards,
                       lambda: self.fence.enable("synthetic-authority"),
                       lambda: self.current.deposit("alice", "after-lost-manifest", "USD", D(1))):
            with self.subTest(action=repr(action)):
                error = self.fenced(action)
                self.assertTrue(any(getattr(value, "code", None) == "fence_guard_corrupt" for value in chain(error)))
                self.assertEqual(financial_snapshot(self.path), before)
        with closing(sqlite3.connect(self.path)) as connection:
            self.assertEqual(connection.execute("SELECT name FROM sqlite_master WHERE type='table' "
                "AND name IN ('writer_fence_guard_config','writer_fence_guard_tables')").fetchall(), [])

    def test_new_financial_table_is_guarded_on_commit_and_raw_legacy_connections_cannot_insert(self):
        with self.current.database.transaction() as connection:
            connection.execute("CREATE TABLE independently_added_financial (id INTEGER PRIMARY KEY,value TEXT NOT NULL)")
            connection.execute("INSERT INTO independently_added_financial VALUES (1,'authorized')")
        with closing(sqlite3.connect(self.path)) as connection, connection:
            guards = connection.execute("SELECT name FROM sqlite_master WHERE type='trigger' "
                "AND name LIKE 'writer_fence_data_%' AND tbl_name='independently_added_financial'").fetchall()
            self.assertEqual(len(guards), 3)
            with self.assertRaises(sqlite3.OperationalError) as caught:
                connection.execute("INSERT INTO independently_added_financial VALUES (2,'legacy')")
            self.assertIn("uta_writer_fence_v1", str(caught.exception))
            self.assertEqual(connection.execute("SELECT * FROM independently_added_financial").fetchall(), [(1, "authorized")])
        with self.current.database.transaction() as connection:
            connection.execute("INSERT INTO independently_added_financial VALUES (3,'authorized-again')")


class DurableCommandFaultTests(DurableFaultFixture):
    def setUp(self):
        super().setUp()
        self.queue_now = NOW
        self.queue = QueueStore(self.database, queue_capacity=4, cancel_reserve=2,
                                market_capacity=2, clock=lambda: self.queue_now, initialize=True)

    def enqueue(self, command="command-one", order="order-one", account="alice"):
        return self.queue.enqueue_submit(account, command, order, "BTC-PERP", D(1), D(100))

    def assert_one_admission(self, current, command="command-one", order="order-one"):
        receipt = self.queue.status(command, account_id="alice")
        self.assertEqual(receipt["state"], "SUCCEEDED")
        self.assertEqual(receipt["result"]["order_id"], order)
        self.assertEqual([row["order_id"] for row in current.orders("alice")], [order])
        self.assertEqual(D(current.account("alice")["open_order_margin"]), D("10.04"))
        self.assertEqual(len(current.ledger.journal()), 2)
        accepted = [row for row in current.events(limit=1000) if row["event_type"] == "ORDER_ACCEPTED"]
        self.assertEqual(len(accepted), 1)
        current.ledger.verify()

    def reacquire(self, owner="recovered", timeout=5):
        fence, deadline = WriterFence(self.database), monotonic() + timeout
        while True:
            try:
                return fence.acquire(owner, 30)
            except WriterFenceError as error:
                if error.code != "lease_busy" or monotonic() > deadline:
                    raise
                sleep(.01)

    def test_enqueue_ack_survives_real_process_exit_and_never_claims_risk_acceptance(self):
        WriterFence(self.database).enable("synthetic-authority")
        before = financial_snapshot(self.path)
        code = r'''
from datetime import datetime
from decimal import Decimal as D
import json, os, sys
from uta.durable_commands import QueueStore
from uta.storage import Database
queue = QueueStore(Database(sys.argv[1]), queue_capacity=4, cancel_reserve=2, market_capacity=2,
                   clock=lambda:datetime.fromisoformat(sys.argv[2]))
receipt = queue.enqueue_submit("alice", "command-one", "order-one", "BTC-PERP", D(1), D(100))
print(json.dumps(receipt), flush=True)
os._exit(61)
'''
        child = self.child(code)
        self.assertEqual(child.returncode, 61, child.stderr)
        receipt = json.loads(child.stdout)
        self.assertEqual((receipt["ack"], receipt["state"], receipt["result"]),
                         ("durably_queued", "PENDING", None))
        self.assertEqual(financial_snapshot(self.path), before)
        self.assertEqual(self.queue.status("command-one")["sequence"], receipt["sequence"])
        token = self.reacquire()
        current = self.open_service(self.database.for_writer(token))
        self.queue.process_one(current)
        self.assert_one_admission(current)

    def test_enqueue_ack_is_not_published_before_actual_metadata_commit(self):
        original = self.database.inbox_transaction
        at_commit, release, returned = Event(), Event(), Event()
        receipts, failures = [], []
        @contextmanager
        def pause_commit():
            with original() as connection:
                yield connection
                at_commit.set()
                if not release.wait(5):
                    raise RuntimeError("test did not release metadata COMMIT")
        def enqueue():
            try:
                receipts.append(self.enqueue())
            except BaseException as error:
                failures.append(error)
            finally:
                returned.set()
        before = financial_snapshot(self.path)
        with patch.object(self.database, "inbox_transaction", side_effect=pause_commit):
            thread = Thread(target=enqueue)
            thread.start()
            try:
                self.assertTrue(at_commit.wait(5))
                self.assertFalse(returned.is_set(), "producer acknowledged an uncommitted queue entry")
                self.assertIsNone(self.queue.status("command-one"))
                self.assertEqual(financial_snapshot(self.path), before)
            finally:
                release.set()
            thread.join(5)
            self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(receipts[0]["ack"], "durably_queued")
        self.assertEqual(self.queue.status("command-one")["state"], "PENDING")

    def test_real_worker_exit_after_dml_before_commit_and_after_commit_retries_original_id_once(self):
        code = r'''
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal as D
import os, sys
from uta.durable_commands import QueueStore
from uta.service import ExchangeService
from uta.storage import Database
from uta.writer_fence import WriterFence
database = Database(sys.argv[1])
token = WriterFence(database).acquire("crashing-worker", .5)
service = ExchangeService(database.for_writer(token), {"USD":8}, clock=lambda:datetime.fromisoformat(sys.argv[2]))
queue = QueueStore(database, queue_capacity=4, cancel_reserve=2, market_capacity=2,
                   clock=lambda:datetime.fromisoformat(sys.argv[2]))
stage = sys.argv[3]
if stage == "dml":
    original = service._admit_order
    def die_after_dml(*args, **kwargs):
        original(*args, **kwargs)
        os._exit(62)
    service._admit_order = die_after_dml
else:
    original = service.database.transaction
    @contextmanager
    def die_at_boundary():
        with original() as connection:
            yield connection
            if stage == "before": os._exit(63)
        os._exit(64)
    service.database.transaction = die_at_boundary
queue.process_one(service)
raise AssertionError("worker did not reach injected crash boundary")
'''
        for stage, expected_exit, expected_state in (("dml", 62, "PENDING"),
                                                     ("before", 63, "PENDING"),
                                                     ("after", 64, "SUCCEEDED")):
            with self.subTest(stage=stage):
                # Each crash stage has its own authority and queue, never a
                # mutated prior stage or restored partial database.
                stage_path = self.directory / (stage + ".sqlite3")
                with closing(sqlite3.connect(self.path)) as source, closing(sqlite3.connect(stage_path)) as target:
                    source.backup(target)
                stage_path.chmod(0o600)
                database = Database(stage_path)
                queue = QueueStore(database, queue_capacity=4, cancel_reserve=2,
                                   market_capacity=2, clock=lambda: NOW)
                receipt = queue.enqueue_submit("alice", "command-one", "order-one", "BTC-PERP", D(1), D(100))
                WriterFence(database).enable("synthetic-authority")
                original_path = self.path
                self.path = stage_path
                try:
                    child = self.child(code, stage)
                finally:
                    self.path = original_path
                self.assertEqual(child.returncode, expected_exit, child.stderr)
                self.assertEqual(queue.status("command-one")["state"], expected_state)
                self.assertEqual(len(financial_snapshot(stage_path)["uta_orders"]), int(stage == "after"))
                fence, deadline = WriterFence(database), monotonic() + 5
                while True:
                    try:
                        token = fence.acquire("restart-worker", 30)
                        break
                    except WriterFenceError as error:
                        if error.code != "lease_busy" or monotonic() > deadline:
                            raise
                        sleep(.01)
                current = self.open_service(database.for_writer(token))
                self.assertEqual(queue.enqueue_submit("alice", "command-one", "order-one", "BTC-PERP", D(1), D(100))["sequence"], receipt["sequence"])
                queue.process_one(current)
                before = financial_snapshot(stage_path)
                self.assertEqual(queue.status("command-one")["state"], "SUCCEEDED")
                self.assertIsNone(queue.process_one(current))
                self.assertEqual(financial_snapshot(stage_path), before)
                self.assertEqual(D(current.account("alice")["open_order_margin"]), D("10.04"))
                self.assertEqual(len(current.ledger.journal()), 2)
                current.ledger.verify()

    def test_lost_commit_response_cannot_be_overwritten_as_retry_or_business_rejection(self):
        self.enqueue()
        _, _, current = self.managed()
        original = current.database.transaction
        armed = [True]
        @contextmanager
        def lose_after_commit():
            with original() as connection:
                yield connection
            if armed[0]:
                armed[0] = False
                raise ConnectionError("synthetic response lost after actual SQLite COMMIT")
        with patch.object(current.database, "transaction", side_effect=lose_after_commit):
            with self.assertRaises(CommandExecutionError):
                self.queue.process_one(current)
        before = financial_snapshot(self.path)
        receipt = self.queue.record_failure(current, "command-one", max_attempts=1)
        self.assertEqual(receipt["state"], "SUCCEEDED")
        self.assertIsNone(self.queue.process_one(current))
        self.assertEqual(financial_snapshot(self.path), before)
        self.assert_one_admission(current)

    def test_real_sqlite_full_after_financial_dml_leaves_pending_then_recovers_once(self):
        with self.database.transaction() as connection:
            connection.execute("CREATE TABLE fault_blob (value BLOB)")
            max_pages = connection.execute("PRAGMA page_count").fetchone()[0]
        self.enqueue()
        _, _, current = self.managed()
        before = financial_snapshot(self.path)
        connect, admit = current.database._connect, current._admit_order
        def full_connection():
            connection = connect()
            connection.execute("PRAGMA max_page_count=" + str(max_pages))
            return connection
        def exhaust_after_dml(connection, *args, **kwargs):
            result = admit(connection, *args, **kwargs)
            connection.execute("INSERT INTO fault_blob VALUES (zeroblob(65536))")
            return result
        with patch.object(current.database, "_connect", side_effect=full_connection), \
                patch.object(current, "_admit_order", side_effect=exhaust_after_dml):
            with self.assertRaises(CommandExecutionError) as caught:
                self.queue.process_one(current)
        self.assertTrue(any(isinstance(error, sqlite3.Error) and (
            getattr(error, "sqlite_errorcode", None) == getattr(sqlite3, "SQLITE_FULL", 13) or
            "database or disk is full" in str(error)) for error in chain(caught.exception)))
        self.assertEqual(self.queue.status("command-one")["state"], "PENDING")
        self.assertEqual(financial_snapshot(self.path), before)
        self.queue.process_one(current)
        self.assert_one_admission(current)

    def test_real_deferred_constraint_commit_failure_rolls_back_financial_and_terminal_receipt(self):
        with self.database.transaction() as connection:
            connection.execute("CREATE TABLE fault_parent (id INTEGER PRIMARY KEY)")
            connection.execute("CREATE TABLE fault_child (id INTEGER REFERENCES fault_parent(id) DEFERRABLE INITIALLY DEFERRED)")
        self.enqueue()
        _, _, current = self.managed()
        before = financial_snapshot(self.path)
        original = current._admit_order
        def violate_at_commit(connection, *args, **kwargs):
            result = original(connection, *args, **kwargs)
            connection.execute("INSERT INTO fault_child VALUES (999)")
            return result
        with patch.object(current, "_admit_order", side_effect=violate_at_commit):
            with self.assertRaises(CommandExecutionError) as caught:
                self.queue.process_one(current)
        self.assertTrue(any(isinstance(error, sqlite3.IntegrityError) for error in chain(caught.exception)))
        self.assertEqual(self.queue.status("command-one")["state"], "PENDING")
        self.assertEqual(financial_snapshot(self.path), before)
        self.queue.process_one(current)
        self.assert_one_admission(current)

    def test_unavailable_database_cannot_ack_more_work_or_lose_existing_ack(self):
        receipt = self.enqueue()
        _, _, current = self.managed()
        before = financial_snapshot(self.path)
        offline = self.path.with_name("offline.sqlite3")
        self.path.rename(offline)
        self.path.mkdir()
        try:
            with self.assertRaises(Exception):
                self.queue.process_one(current)
            with self.assertRaises(Exception):
                self.enqueue("not-acknowledged", "not-accepted")
            self.assertEqual(financial_snapshot(offline), before)
        finally:
            self.path.rmdir()
            offline.rename(self.path)
        self.assertEqual(self.queue.status("command-one")["sequence"], receipt["sequence"])
        self.assertIsNone(self.queue.status("not-acknowledged"))
        self.queue.process_one(current)
        self.assert_one_admission(current)

    def test_poison_is_bounded_other_accounts_progress_and_same_account_cancel_waits_for_quarantine(self):
        self.service.submit_order("alice", "old", "BTC-PERP", D(1), D(100))
        self.enqueue("poison", "poison-order")
        self.queue.enqueue_cancel("alice", "cancel-old", "old")
        self.enqueue("bob-work", "bob-order", "bob")
        _, _, current = self.managed()
        original = current._admit_order
        def poison(connection, account, identifier, *args, **kwargs):
            if identifier == "poison-order":
                raise RuntimeError("synthetic deterministic poison")
            return original(connection, account, identifier, *args, **kwargs)
        with patch.object(current, "_admit_order", side_effect=poison):
            with self.assertRaises(CommandExecutionError):
                self.queue.process_one(current)
            first = self.queue.record_failure(current, "poison", max_attempts=2, backoff_seconds=1)
            self.assertEqual((first["state"], first["attempts"]), ("PENDING", 1))
            self.assertEqual(self.queue.process_one(current)["command_id"], "bob-work")
            self.assertIsNone(self.queue.process_one(current))
            self.assertEqual(current.order("alice", "old")["status"], "OPEN")
            self.queue_now += timedelta(seconds=2)
            with self.assertRaises(CommandExecutionError):
                self.queue.process_one(current)
            terminal = self.queue.record_failure(current, "poison", max_attempts=2)
            self.assertEqual((terminal["state"], terminal["attempts"]), ("QUARANTINED", 2))
            self.assertEqual(self.queue.process_one(current)["command_id"], "cancel-old")
            self.assertIsNone(self.queue.process_one(current))
        self.assertEqual(current.order("alice", "old")["status"], "CANCELLED")
        self.assertEqual([row["order_id"] for row in current.orders("alice")], ["old"])
        self.assertEqual(self.queue.status("poison")["state"], "QUARANTINED")
        self.assertEqual(self.queue.status("cancel-old")["state"], "SUCCEEDED")
        current.ledger.verify()

    def test_unsupported_commands_and_capacity_are_explicit_and_never_fall_back_to_sync(self):
        before = financial_snapshot(self.path)
        with self.assertRaises(ServiceError) as caught:
            self.queue.enqueue("WITHDRAW", "unsupported-withdraw", {"account_id": "alice", "amount": "1", "asset": "USD"})
        self.assertEqual(caught.exception.code, "unsupported_durable_command")
        self.assertIsNone(self.queue.status("unsupported-withdraw"))
        for index in range(4):
            self.enqueue(f"normal-{index}", f"order-{index}")
        with self.assertRaises(ServiceError) as caught:
            self.enqueue("overflow", "overflow")
        self.assertEqual(caught.exception.code, "durable_queue_overloaded")
        for index in range(2):
            self.queue.enqueue_cancel("alice", f"cancel-{index}", f"order-{index}")
        with self.assertRaises(ServiceError) as caught:
            self.queue.enqueue_cancel("alice", "cancel-overflow", "order-0")
        self.assertEqual(caught.exception.code, "durable_queue_overloaded")
        self.assertEqual(financial_snapshot(self.path), before)

    def test_producer_metadata_role_cannot_forge_replace_or_update_terminal_receipts(self):
        self.enqueue()
        _, _, current = self.managed()
        self.queue.process_one(current)
        before = self.queue.status("command-one")
        financial = financial_snapshot(self.path)
        statements = (
            "INSERT INTO uta_command_inbox(command_id,account_id,kind,payload,state,result,enqueued_at,completed_at) "
            "VALUES ('forged','alice','SUBMIT_ORDER','{}','SUCCEEDED','{}','2026-11-16','2026-11-16')",
            "UPDATE uta_command_inbox SET state='PENDING',result=NULL WHERE command_id='command-one'",
            "INSERT OR REPLACE INTO uta_command_inbox(sequence,command_id,account_id,kind,payload,state,enqueued_at) "
            "SELECT sequence,command_id,account_id,kind,payload,'PENDING',enqueued_at FROM uta_command_inbox WHERE command_id='command-one'",
            "INSERT OR REPLACE INTO uta_command_config VALUES (1,1,1,0,1)",
        )
        for statement in statements:
            with self.subTest(statement=statement.split()[0:3]):
                def producer_write():
                    with self.database.inbox_transaction() as connection:
                        connection.execute(statement)
                # SQL schema guards may reject INSERT/REPLACE before the
                # role authorizer does. Either is a storage-layer rejection.
                with self.assertRaises((WriterFenceError, sqlite3.IntegrityError)):
                    producer_write()
                self.assertEqual(self.queue.status("command-one"), before)
                self.assertIsNone(self.queue.status("forged"))
                self.assertEqual(financial_snapshot(self.path), financial)

    def test_restart_with_missing_inbox_or_guard_refuses_to_recreate_history(self):
        self.enqueue()
        for missing in ("inbox", "guard"):
            with self.subTest(missing=missing):
                path = self.directory / ("missing-" + missing + ".sqlite3")
                with closing(sqlite3.connect(self.path)) as source, closing(sqlite3.connect(path)) as target:
                    source.backup(target)
                path.chmod(0o600)
                with closing(sqlite3.connect(path)) as connection, connection:
                    if missing == "inbox":
                        name, kind = "uta_command_inbox", "table"
                        connection.execute("DROP TABLE uta_command_inbox")
                    else:
                        name, = connection.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='uta_command_inbox' ORDER BY name LIMIT 1").fetchone()
                        kind = "trigger"
                        connection.execute('DROP TRIGGER "' + name + '"')
                before = financial_snapshot(path)
                with self.assertRaises(StorageError):
                    QueueStore(Database(path), queue_capacity=4, cancel_reserve=2, market_capacity=2,
                               clock=lambda: NOW)
                with closing(sqlite3.connect(path)) as connection:
                    self.assertIsNone(connection.execute("SELECT name FROM sqlite_master WHERE type=? AND name=?", (kind, name)).fetchone())
                self.assertEqual(financial_snapshot(path), before)


class StorageLeaseFaultTests(DurableFaultFixture):
    def test_two_real_processes_cannot_share_live_lease_and_expired_owner_cannot_resume_writes(self):
        WriterFence(self.database).enable("synthetic-authority")
        ready, release, acquired = (self.directory / name for name in ("old-ready", "old-release", "new-token"))
        code = r'''
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal as D
import json, sys, time
from pathlib import Path
from uta.service import ExchangeService
from uta.storage import Database
from uta.writer_fence import WriterFence, WriterFenceError
database = Database(sys.argv[1])
fence = WriterFence(database)
if sys.argv[3] == "old":
    token = fence.acquire("process-old", 2)
    service = ExchangeService(database.for_writer(token), {"USD":8}, clock=lambda:datetime.fromisoformat(sys.argv[2]))
    Path(sys.argv[4]).write_text(json.dumps(asdict(token)))
    deadline = time.monotonic() + 10
    while not Path(sys.argv[5]).exists():
        if time.monotonic() > deadline: raise RuntimeError("old writer was not released")
        time.sleep(.01)
    try:
        service.deposit("alice", "stale-writer-deposit", "USD", D(1))
    except Exception as error:
        values, pending = [], [error]
        while pending:
            value = pending.pop()
            if value is None: continue
            values.append(getattr(value, "code", type(value).__name__))
            pending.append(value.__cause__)
        print(json.dumps({"fenced":values}), flush=True)
    else: raise AssertionError("expired writer mutated funds")
else:
    try:
        fence.acquire("process-new", 10)
    except WriterFenceError as error:
        assert error.code == "lease_busy", error.code
    else: raise AssertionError("second process acquired an unexpired lease")
    deadline = time.monotonic() + 8
    while True:
        try:
            token = fence.acquire("process-new", 10)
            break
        except WriterFenceError as error:
            if error.code != "lease_busy" or time.monotonic() > deadline: raise
            time.sleep(.01)
    Path(sys.argv[4]).write_text(json.dumps(asdict(token)))
    print(json.dumps(asdict(token)), flush=True)
    fence.release(token)
'''
        import uta.service
        root = Path(uta.service.__file__).resolve().parent.parent
        args = [sys.executable, "-c", code, str(self.path), NOW.isoformat()]
        old = subprocess.Popen(args + ["old", str(ready), str(release)], cwd=root,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(self.cleanup_child, old)
        self.wait_file(ready, old)
        new = subprocess.Popen(args + ["new", str(acquired)], cwd=root,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(self.cleanup_child, new)
        try:
            output, errors = new.communicate(timeout=12)
            self.assertEqual(new.returncode, 0, errors)
            new_token = json.loads(output)
            old_token = json.loads(ready.read_text())
            self.assertGreater(new_token["generation"], old_token["generation"])
            before = financial_snapshot(self.path)
        finally:
            release.touch()
        output, errors = old.communicate(timeout=8)
        self.assertEqual(old.returncode, 0, errors)
        self.assertTrue({"writer_fenced", "lease_expired"} & set(json.loads(output)["fenced"]))
        self.assertEqual(financial_snapshot(self.path), before)
        token = WriterFence(self.database).acquire("parent-recovery", 10)
        self.assertGreater(token.generation, new_token["generation"])
        current = self.open_service(self.database.for_writer(token))
        current.deposit("alice", "new-writer-deposit", "USD", D(1))
        self.assertEqual(current.account("alice")["balances"]["USD"], "1001")
        current.ledger.verify()

    def test_lease_expiring_after_financial_dml_rolls_back_at_commit_checkpoint(self):
        tick = [1_000_000_000]
        database = Database(self.path, fence_clock_ns=lambda: tick[0], fence_boot_id="synthetic-boot")
        _, token, _ = self.managed(database=database, ttl=1)
        writer = database.for_writer(token)
        before = financial_snapshot(self.path)
        with self.assertRaises(WriterFenceError) as caught:
            with writer.transaction() as connection:
                connection.execute("UPDATE uta_accounts SET version=version+1 WHERE account_id='alice'")
                tick[0] += 1_000_000_000
        self.assertEqual(caught.exception.code, "lease_expired")
        self.assertEqual(financial_snapshot(self.path), before)

    def test_same_owner_nonce_cannot_reuse_released_generation_and_pid_bound_token_cannot_transfer(self):
        fence, token, _ = self.managed()
        fence.release(token)
        newer = fence.acquire(token.owner_nonce, 30)
        self.assertGreater(newer.generation, token.generation)
        stale = self.database.for_writer(token)
        before = financial_snapshot(self.path)
        self.fenced(self.open_service, stale)
        self.assertEqual(financial_snapshot(self.path), before)
        code = r'''
from datetime import datetime
from decimal import Decimal as D
import json, sys
from uta.service import ExchangeService
from uta.storage import Database
from uta.writer_fence import WriterToken
token = WriterToken(**json.loads(sys.argv[3]))
try:
    service = ExchangeService(Database(sys.argv[1]).for_writer(token), {"USD":8}, clock=lambda:datetime.fromisoformat(sys.argv[2]))
    service.deposit("alice", "transferred-token", "USD", D(1))
except Exception as error:
    pending, codes = [error], []
    while pending:
        value = pending.pop()
        if value is None: continue
        codes.append(getattr(value, "code", type(value).__name__))
        pending.append(value.__cause__)
    print(json.dumps(codes), flush=True)
else: raise AssertionError("a different PID used a transferred writer token")
'''
        child = self.child(code, json.dumps(asdict(newer)))
        self.assertEqual(child.returncode, 0, child.stderr)
        self.assertIn("writer_fenced", json.loads(child.stdout))
        self.assertEqual(financial_snapshot(self.path), before)


class DurableRepaymentFaultTests(DurableFaultFixture):
    def setUp(self):
        super().setUp()
        credit = CreditService(self.service)
        credit.configure_asset_limit("USD", D(100))
        credit.configure_limit("alice", "USD", D(100))
        credit.fund_pool("loan-capital", "USD", D(50), source_reference="synthetic:repayment:capital")
        credit.borrow("alice", "loan", "USD", D(10))
        credit.accrue_interest("alice", "interest", "USD", D(1))
        self.queue = QueueStore(self.database, queue_capacity=4, cancel_reserve=2,
                                market_capacity=2, clock=lambda: NOW, initialize=True)
        _, _, self.current = self.managed()
        self.credit = CreditService(self.current)

    def enqueue_repay(self):
        return self.queue.enqueue_repay("alice", "repayment", "USD", D(4))

    def assert_repaid_once(self):
        receipt = self.queue.status("repayment")
        self.assertEqual(receipt["state"], "SUCCEEDED")
        self.assertEqual((receipt["result"]["interest_repaid"], receipt["result"]["principal_repaid"]), ("1", "3"))
        account = self.current.account("alice")
        self.assertEqual(account["balances"]["USD"], "1006")
        self.assertEqual(account["liabilities"]["USD"], {"principal": "7", "interest": "0", "total": "7"})
        for name, amount in (("system:credit-pool", "43"), ("system:credit-interest-cash", "1"),
                             ("system:credit-interest-receivable", "0"),
                             ("system:credit-principal-receivable", "7"),
                             ("liability:principal:alice", "-7"), ("liability:interest:alice", "0")):
            self.assertEqual(self.current.ledger.balance(name, "USD"), D(amount))
        self.current.ledger.verify()
        self.credit.verify()

    def test_same_asset_repayment_is_available_during_halt_and_complete_quote_outage(self):
        self.current.set_kill_switch(True)
        with self.current.database.transaction() as connection:
            connection.execute("DELETE FROM uta_market")
        self.enqueue_repay()
        self.queue.process_one(self.current, credit=self.credit)
        self.assert_repaid_once()
        before = financial_snapshot(self.path)
        self.assertEqual(self.enqueue_repay()["state"], "SUCCEEDED")
        self.assertIsNone(self.queue.process_one(self.current, credit=self.credit))
        self.assertEqual(financial_snapshot(self.path), before)

    def test_repayment_postings_debt_cash_and_terminal_receipt_share_actual_commit(self):
        with self.current.database.transaction() as connection:
            connection.execute("CREATE TABLE repayment_parent (id INTEGER PRIMARY KEY)")
            connection.execute("CREATE TABLE repayment_child (id INTEGER REFERENCES repayment_parent(id) DEFERRABLE INITIALLY DEFERRED)")
        self.enqueue_repay()
        before = financial_snapshot(self.path)
        original = self.credit._repay
        def fail_commit(connection, *args, **kwargs):
            result = original(connection, *args, **kwargs)
            connection.execute("INSERT INTO repayment_child VALUES (999)")
            return result
        with patch.object(self.credit, "_repay", side_effect=fail_commit):
            with self.assertRaises(CommandExecutionError) as caught:
                self.queue.process_one(self.current, credit=self.credit)
        self.assertTrue(any(isinstance(value, sqlite3.IntegrityError) for value in chain(caught.exception)))
        self.assertEqual(self.queue.status("repayment")["state"], "PENDING")
        self.assertEqual(financial_snapshot(self.path), before)
        self.queue.process_one(self.current, credit=self.credit)
        self.assert_repaid_once()

    def test_missing_initialized_credit_is_technical_pending_and_never_fake_success(self):
        self.enqueue_repay()
        before = financial_snapshot(self.path)
        with self.assertRaises(CommandExecutionError) as caught:
            self.queue.process_one(self.current)
        self.assertTrue(any(isinstance(value, StorageError) for value in chain(caught.exception)))
        self.assertEqual(self.queue.status("repayment")["state"], "PENDING")
        self.assertEqual(financial_snapshot(self.path), before)
        self.queue.process_one(self.current, credit=self.credit)
        self.assert_repaid_once()

    def test_same_account_poison_quarantine_unblocks_repayment_without_funding_or_quote_dependency(self):
        self.queue.enqueue_submit("alice", "poison", "poison-order", "BTC-PERP", D(1), D(100))
        self.enqueue_repay()
        self.current.set_kill_switch(True)
        with self.current.database.transaction() as connection:
            connection.execute("DELETE FROM uta_market")
        with patch.object(self.current, "_admit_order", side_effect=RuntimeError("synthetic poison")):
            with self.assertRaises(CommandExecutionError):
                self.queue.process_one(self.current, credit=self.credit)
            isolated = self.queue.record_failure(self.current, "poison", max_attempts=1)
            self.assertEqual(isolated["state"], "QUARANTINED")
            self.assertEqual(self.queue.process_one(self.current, credit=self.credit)["command_id"], "repayment")
        self.assert_repaid_once()
        self.assertEqual(self.current.orders("alice"), [])


class ManagedProcessFaultTests(unittest.TestCase):
    def setUp(self):
        from uta.durable_process import DurableProcessRouter
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "router"
        self.accounts = []
        def bootstrap(router):
            self.accounts = [next(f"process-user-{index}" for index in range(1000)
                                  if router.shard_for(f"process-user-{index}") == shard)
                             for shard in range(2)]
            for account in self.accounts:
                router.create_account(account)
                router.deposit(account, "seed", "USD", D(1000))
            router.fund_credit_pool(1, "fund", "USD", D(50), source_reference="synthetic:process:fund")
            router.fund_credit_pool(0, "repay-fund", "USD", D(50), source_reference="synthetic:process:repay-fund")
            router.configure_credit_asset_limit(0, "USD", D(100))
            router.configure_credit_limit(self.accounts[0], "USD", D(100))
            router.publish_market(MarketSnapshot(0, datetime.now(timezone.utc),
                {"USD": AssetSpec(D(1), D(1))},
                {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))}))
            router.set_kill_switch(False)
            router.borrow(self.accounts[0], "loan", "USD", D(10))
            router.accrue_interest(self.accounts[0], "interest", "USD", D(1))
        # Only the native SH-holder fixture needs setup headroom. This is the
        # real production-default lease from first initialization, not a renewal
        # of an expired token; every other case retains its one-second lease.
        fixture_lease = (5 if self._testMethodName ==
            "test_expired_sigstopped_shared_gate_owner_is_killed_so_publication_can_recover" else 1)
        self.router = DurableProcessRouter.initialize(self.path, 2, {"USD": 8},
            managed=True, bootstrap=bootstrap, max_price_age=timedelta(minutes=1),
            lease_seconds=fixture_lease, poll_interval=.01, background_interval=.05,
            account_batch=1, matches_per_symbol=1, max_attempts=2)
        self.addCleanup(self.router.close)

    def shard_path(self, shard):
        return self.path / f"shard-{shard:04d}.sqlite3"

    def market(self, version=1, mark="100"):
        return MarketSnapshot(version, datetime.now(timezone.utc),
            {"USD": AssetSpec(D(1), D(1))},
            {"BTC-PERP": InstrumentSpec(D(mark), D(".1"), D(".05"))})

    def control_state(self):
        with closing(sqlite3.connect(self.path / "router.sqlite3")) as connection:
            return json.loads(connection.execute("SELECT payload FROM router_state WHERE singleton=1").fetchone()[0])

    def active(self):
        self.router.start()
        result = self.router.publish_market(self.market(), timeout=10)
        self.assertFalse(result["publishing"])
        result = self.router.set_kill_switch(False, timeout=10)
        self.assertFalse(result["halted"])
        # Control commits can precede the parent's next READY-pipe observation.
        # Retry only explained observation transients, never stale/partial or
        # another failed financial condition. Business waits and leases above
        # retain their existing limits.
        deadline, observation = monotonic() + 10, None
        while True:
            remaining = deadline - monotonic()
            if remaining <= 0:
                break
            observation = self.router.diagnostics(timeout=min(1, remaining))
            if observation["ready"]:
                break
            if observation.get("reason") not in {"worker_unready", "diagnostic_timeout"}:
                self.fail("non-transient readiness failure: " + json.dumps(observation, sort_keys=True))
            sleep(min(.01, max(0, deadline - monotonic())))
        message = json.dumps(observation, sort_keys=True)
        self.assertIsNotNone(observation, message)
        self.assertTrue(observation["ready"], message)
        self.assertTrue(observation["financial_ready"], message)
        self.assertTrue(all(row["owner_ready"] and row["market_ready"]
                            for row in observation["workers"]), message)

    def submit(self, command, order=None, shard=0):
        return self.router.submit_order(self.accounts[shard], command, order or command,
                                        "BTC-PERP", D(1), D(100))

    def wait(self, command, shard=0, state="SUCCEEDED"):
        receipt = self.router.wait(command, account_id=self.accounts[shard], timeout=10)
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt["state"], state, repr(receipt))
        return receipt

    def suspend_outside_transaction(self, shard):
        """Stop a worker only after both its gate and SQLite writer are free.

        Pausing a live lock holder is a separate recovery fault, not a way to
        create a stalled consumer for the partial-publication scenario.
        """
        pid = self.router.worker_pid(shard)
        descriptor = os.open(self.path / "router.lock", os.O_RDWR)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            with closing(sqlite3.connect(self.shard_path(shard), timeout=5, isolation_level=None)) as connection:
                connection.execute("BEGIN IMMEDIATE")
                try:
                    os.kill(pid, signal.SIGSTOP)
                finally:
                    connection.rollback()
        finally:
            os.close(descriptor)
        return pid

    def test_without_live_worker_ack_is_only_pending_and_has_no_financial_effect(self):
        before = financial_snapshot(self.shard_path(0))
        receipt = self.submit("no-worker")
        self.assertEqual((receipt["ack"], receipt["state"], receipt["result"]),
                         ("durably_queued", "PENDING", None))
        self.assertEqual(self.router.wait("no-worker", account_id=self.accounts[0], timeout=.05)["state"], "PENDING")
        repayment = self.router.repay(self.accounts[0], "no-worker-repayment", "USD", D(4))
        self.assertEqual((repayment["state"], repayment["result"]), ("PENDING", None))
        self.assertEqual(self.router.wait("no-worker-repayment", account_id=self.accounts[0], timeout=.05)["state"], "PENDING")
        self.assertTrue(all(worker["pid"] is None for worker in self.router.diagnostics()["workers"]))
        self.assertEqual(financial_snapshot(self.shard_path(0)), before)

    def test_ack_before_real_worker_kill_is_recovered_by_new_pid_and_generation_once(self):
        self.active()
        pid = self.suspend_outside_transaction(0)
        old_generation = self.router.diagnostics()["workers"][0]["generation"]
        receipt = self.submit("recover-after-kill")
        self.assertEqual(receipt["state"], "PENDING")
        self.assertEqual(financial_snapshot(self.shard_path(0))["uta_orders"], [])
        self.router.terminate_worker(0)
        terminal = self.wait("recover-after-kill")
        self.assertEqual(terminal["sequence"], receipt["sequence"])
        self.assertNotEqual(self.router.worker_pid(0), pid)
        self.assertGreater(self.router.diagnostics()["workers"][0]["generation"], old_generation)
        before = financial_snapshot(self.shard_path(0))
        replay = self.submit("recover-after-kill")
        self.assertEqual(replay, terminal)
        self.assertEqual(financial_snapshot(self.shard_path(0)), before)
        self.assertEqual(len(before["uta_orders"]), 1)
        self.assertEqual(len([row for row in before["uta_events"] if row[1] == "ORDER_ACCEPTED"]), 1)

    def test_expired_sigstopped_shared_gate_owner_is_killed_so_publication_can_recover(self):
        from uta.durable_process import _process_identity
        self.active()
        before = financial_snapshot(self.shard_path(0))
        cache_configuration = {key: self.router._config["service"].get(key)
                               for key in ("reserve_cache_size", "market_cache_size")}
        cache_configuration["normal_cache_size"] = self.router._settings.get("normal_cache_size")
        def schema_versions():
            with self.router._database(0).read_transaction() as connection:
                return {name: [tuple(row) for row in connection.execute("SELECT * FROM " + name)]
                        for name in ("uta_schema", "ledger_schema")}
        versions = schema_versions()
        observer = self.router._database(0)
        observer.timeout = .1
        def lease():
            value = WriterFence(observer).status()
            # Retain no raw nonce/token material in test observations.
            return {key: value[key] for key in
                    ("owner_pid", "generation", "active", "expires_ns", "now_ns")}
        with self.router._mutex:
            process = self.router._workers[0][0]
            self.assertTrue(process.is_alive())
            pid = process.pid
            identity = _process_identity(pid)
            pidfd = os.pidfd_open(pid)
        exited = select.poll()
        exited.register(pidfd, select.POLLIN)
        lock_path = self.path / "router.lock"
        details = lock_path.stat(follow_symlinks=False)
        file_identity = (details.st_dev, details.st_ino)
        observation = self._expired_gate_observation = {
            "selected_binding": identity, "fixture_lease_seconds": 5,
            "capture_horizon_seconds": 5, "recovery_horizon_seconds": 5,
            "api_phase_timeout_seconds": 5, "publication_lifecycle_watchdog_seconds": 15,
            "capture_attempts": [], "cleanup_forced_kill": False}
        stopped, captured, thread = False, False, None
        done, gate_entered, results, errors = Event(), Event(), [], []
        publication_started = None
        try:
            capture_deadline = monotonic() + 5
            for _ in range(8):
                # Both the finite capture horizon and the original live binding
                # constrain every signal. No business command is retried here.
                while monotonic() < capture_deadline:
                    self.assertFalse(exited.poll(0), "selected owner exited before SH capture")
                    current = lease()
                    self.assertEqual(current["owner_pid"], pid)
                    self.assertTrue(current["active"], "selected owner expired during SH capture")
                    candidate = bound_router_shared_flocks(pid, identity, lock_path, file_identity)
                    if candidate:
                        break
                    sleep(.001)
                else:
                    self.fail("no bound native router SH descriptor within capture horizon")
                stop_sent_at = monotonic()
                signal.pidfd_send_signal(pidfd, signal.SIGSTOP)
                stopped = True
                stop_deadline = min(capture_deadline, monotonic() + .2)
                while monotonic() < stop_deadline and _process_identity(pid)["state"] != "T":
                    self.assertFalse(exited.poll(0))
                    sleep(.001)
                self.assertEqual(_process_identity(pid)["state"], "T")
                retained = bound_router_shared_flocks(pid, identity, lock_path, file_identity)
                observation["capture_attempts"].append({"at": monotonic(), "stop_sent_at": stop_sent_at,
                                                        "candidate": candidate,
                                                        "retained_after_stop": retained})
                if retained:
                    writer_probe = router_writer_available_without_dml(self.shard_path(0))
                    observation["capture_attempts"][-1]["writer_availability_probe"] = writer_probe
                if retained and writer_probe["available"]:
                    descriptor = os.open(lock_path, os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW)
                    try:
                        opened = os.fstat(descriptor)
                        self.assertEqual((opened.st_dev, opened.st_ino), file_identity)
                        try:
                            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        except BlockingIOError:
                            captured = True
                        else:
                            fcntl.flock(descriptor, fcntl.LOCK_UN)
                    finally:
                        os.close(descriptor)
                    if captured:
                        observation["captured_at"] = monotonic()
                        break
                current = lease()
                self.assertTrue(current["active"] and current["owner_pid"] == pid,
                                "lost capture cannot resume an expired or different owner")
                self.assertFalse(exited.poll(0))
                signal.pidfd_send_signal(pidfd, signal.SIGCONT)
                stopped = False
            self.assertTrue(captured, "read/stop races exhausted the bounded SH capture attempts")
            old = lease()
            old_generation = old["generation"]
            self.assertEqual(old["owner_pid"], pid)
            self.assertTrue(old["active"])
            self.assertGreater(old["expires_ns"] - old["now_ns"], 350_000_000)
            observation["captured_lease"] = old
            with observer.read_transaction() as connection:
                acquired = connection.execute(
                    "SELECT expires_ns-observed_ns FROM writer_fence_events WHERE kind='acquired' AND owner_pid=? AND generation=?",
                    (pid, old_generation)).fetchall()
            self.assertEqual([row[0] for row in acquired], [5_000_000_000])
            # An unexpired held-SH owner must not be killed early.
            self.assertEqual(exited.poll(100), [])
            current = lease()
            self.assertTrue(current["active"] and current["owner_pid"] == pid)
            self.assertEqual(current["generation"], old_generation)
            self.assertTrue(bound_router_shared_flocks(pid, identity, lock_path, file_identity))
            observation["unexpired_control_lease"] = current
            queued = self.submit("held-gate-command")
            self.assertEqual((queued["ack"], queued["state"]), ("durably_queued", "PENDING"))
            snapshot = self.market(2, "110")
            original_payload = snapshot.to_json()
            observation["original_snapshot_sha256"] = hashlib.sha256(original_payload.encode()).hexdigest()
            # Wait for real native time; never alter or renew the paused token.
            while True:
                self.assertFalse(exited.poll(0), "unexpired binding was killed before publication")
                current = lease()
                self.assertTrue(current["active"] and current["owner_pid"] == pid)
                self.assertEqual(current["generation"], old_generation)
                remaining = (current["expires_ns"] - current["now_ns"]) / 1e9
                if remaining <= .25:
                    break
                sleep(min(.05, remaining - .25))
            observation["publication_entry_lease"] = current
            original_lock = self.router._control._lock
            @contextmanager
            def observed_gate(*, exclusive=False, timeout=None):
                with original_lock(exclusive=exclusive, timeout=timeout):
                    if exclusive and current_thread() is thread and not gate_entered.is_set():
                        observation["publication_first_ex_entered_at"] = monotonic()
                        gate_entered.set()
                    yield
            def publish():
                try:
                    entry = lease()
                    observation["publication_thread_entry_lease"] = entry
                    self.assertTrue(entry["active"] and entry["owner_pid"] == pid)
                    self.assertEqual(entry["generation"], old_generation)
                    self.assertLessEqual((entry["expires_ns"] - entry["now_ns"]) / 1e9, .25)
                    observation["publication_called_api_at"] = monotonic()
                    results.append(self.router.publish_market(snapshot, timeout=5))
                except BaseException as error:
                    errors.append(error)
                finally:
                    observation["publication_finished_at"] = monotonic()
                    done.set()
            thread = Thread(target=publish, daemon=True)
            publication_started = monotonic()
            observation["publication_started_at"] = publication_started
            recovery_deadline = publication_started + 5
            lifecycle_deadline = publication_started + 15
            with patch.object(self.router._control, "_lock", observed_gate):
                thread.start()
                self.assertTrue(exited.poll(max(0, int((recovery_deadline - monotonic()) * 1000))),
                                "original bound PID did not exit within the unchanged five-second recovery horizon")
                observation["old_pidfd_exit_observed_at"] = monotonic()
                self.assertLessEqual(observation["old_pidfd_exit_observed_at"], recovery_deadline)
                stopped = False
                while monotonic() < recovery_deadline:
                    current = lease()
                    if current["active"] and current["generation"] > old_generation and current["owner_pid"] != pid:
                        observation["new_generation_observed_at"] = monotonic()
                        self.assertLessEqual(observation["new_generation_observed_at"], recovery_deadline)
                        observation["new_lease"] = current
                        break
                    sleep(.005)
                else:
                    self.fail("no actual new-generation lease within the unchanged recovery horizon")
                self.assertTrue(gate_entered.wait(max(0, recovery_deadline - monotonic())),
                                "original publication did not actually enter EX after the held-SH owner exited")
                self.assertLessEqual(observation["publication_first_ex_entered_at"], recovery_deadline)
                # This is a thread lifecycle bound for three separate API wait
                # phases, not a replacement or increase of the recovery horizon.
                self.assertTrue(done.wait(max(0, lifecycle_deadline - monotonic())),
                                "publication exceeded its explicitly separate phase lifecycle watchdog")
                thread.join(max(0, lifecycle_deadline - monotonic()))
            self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual(len(results), 1)
            result = results[0]
            self.assertFalse(result["publishing"])
            self.assertEqual(result["market_version"], 2)
            self.assertEqual(snapshot.to_json(), original_payload)
            self.assertEqual(result["market_digest"], hashlib.sha256(original_payload.encode()).hexdigest())
            self.assertEqual(set(result["receipts"]), {"0", "1"})
            for shard, receipt in result["receipts"].items():
                self.assertEqual(receipt["state"], "SUCCEEDED")
                self.assertEqual(receipt["command_id"], result["durable_market_commands"][shard])
                self.assertEqual(self.router._queue(int(shard)).status(receipt["command_id"]), receipt)
                with self.router._database(int(shard)).read_transaction() as connection:
                    self.assertEqual(connection.execute("SELECT payload FROM uta_market WHERE singleton=1").fetchone()[0], original_payload)
            self.assertNotEqual(self.router.worker_pid(0), pid)
            self.assertGreater(lease()["generation"], old_generation)
            after = financial_snapshot(self.shard_path(0))
            self.assertLessEqual(len(after["uta_orders"]), 1)
            accepted = [row for row in after["uta_events"] if row[1] == "ORDER_ACCEPTED"]
            self.assertLessEqual(len(accepted), 1)
            if after["uta_orders"]:
                self.assertEqual(after["uta_orders"][0][:2], (self.accounts[0], "held-gate-command"))
            for table in ("ledger_events", "ledger_postings", "ledger_balances", "uta_liabilities",
                          "uta_fills", "uta_positions", "uta_matches"):
                self.assertEqual(after[table], before[table], table)
            self.assertEqual(schema_versions(), versions)
            after_cache = {key: self.router._config["service"].get(key)
                           for key in ("reserve_cache_size", "market_cache_size")}
            after_cache["normal_cache_size"] = self.router._settings.get("normal_cache_size")
            self.assertEqual(after_cache, cache_configuration)
            observation["finance"] = {"orders": len(after["uta_orders"]), "accepted_events": len(accepted),
                                      "ledger_and_debt_unchanged": True, "schema_versions": versions,
                                      "cache_configuration": cache_configuration}
        finally:
            if thread is not None and thread.is_alive():
                if not exited.poll(0):
                    observation["cleanup_forced_kill"] = True
                    signal.pidfd_send_signal(pidfd, signal.SIGKILL)
                thread.join(8)
            elif stopped and not exited.poll(0):
                current = lease()
                if current["active"] and current["owner_pid"] == pid:
                    signal.pidfd_send_signal(pidfd, signal.SIGCONT)
            os.close(pidfd)

    def test_partial_publication_stays_halted_until_exact_publication_replay_completes(self):
        self.active()
        self.suspend_outside_transaction(1)
        snapshot = self.market(2, "110")
        try:
            partial = self.router.publish_market(snapshot, timeout=.15)
            self.assertTrue(partial["publishing"])
            self.assertTrue(partial["halted"])
            self.assertTrue(self.control_state()["publishing"])
            self.submit("during-partial")
            rejected = self.wait("during-partial", state="REJECTED")
            self.assertEqual(rejected["error"]["code"], "router_halted")
            self.assertEqual(financial_snapshot(self.shard_path(0))["uta_orders"], [])
        finally:
            self.router.terminate_worker(1)
        repaired = self.router.publish_market(snapshot, timeout=10)
        self.assertFalse(repaired["publishing"])
        self.assertTrue(repaired["halted"])
        self.assertFalse(self.router.set_kill_switch(False, timeout=10)["halted"])
        self.submit("after-complete-publication")
        self.wait("after-complete-publication")

    def test_real_worker_quarantines_persisted_poison_and_then_processes_same_account_cancel(self):
        self.active()
        self.submit("old-order")
        self.wait("old-order")
        pid = self.suspend_outside_transaction(0)
        try:
            # A legal append role cannot fake terminal status, but damaged
            # pending input still needs bounded handling by the actual worker.
            with Database(self.shard_path(0)).inbox_transaction() as connection:
                connection.execute("INSERT INTO uta_command_inbox(command_id,account_id,kind,payload,state,enqueued_at) "
                    "VALUES (?,?,?,'{}','PENDING',?)", ("persisted-poison", self.accounts[0],
                    "UNRECOGNIZED_KIND", datetime.now(timezone.utc).isoformat()))
            self.router.cancel_order(self.accounts[0], "cancel-after-poison", "old-order")
        finally:
            os.kill(pid, signal.SIGCONT)
        terminal = self.wait("persisted-poison", state="QUARANTINED")
        self.assertEqual(terminal["attempts"], 2)
        self.assertEqual(terminal["error"]["code"], "command_quarantined")
        self.assertEqual(self.wait("cancel-after-poison")["result"]["status"], "CANCELLED")
        snapshot = financial_snapshot(self.shard_path(0))
        self.assertEqual(len(snapshot["uta_orders"]), 1)
        self.assertEqual(len([row for row in snapshot["uta_events"] if row[1] == "ORDER_ACCEPTED"]), 1)
        diagnostics = [row for row in snapshot["uta_events"] if row[1] == "COMMAND_EXECUTION_FAILED"]
        self.assertEqual(len(diagnostics), 2)
        payloads = [json.loads(row[3]) for row in diagnostics]
        self.assertTrue(all(row[2] is None for row in diagnostics))
        self.assertEqual([payload["attempt"] for payload in payloads], [1, 2])
        self.assertTrue(all(payload["command_id"] == "persisted-poison" for payload in payloads))
        self.assertTrue(all([node["type"] for node in payload["diagnostic"]["chain"]] ==
                            ["uta.storage.StorageError", "uta.service.ServiceError"] for payload in payloads))

    def test_real_worker_quarantines_predecessor_then_repays_during_halt_without_quotes(self):
        self.active()
        self.assertTrue(self.router.set_kill_switch(True, timeout=10)["halted"])
        # Persistent SQL guards intentionally block unbound raw DELETE now.
        # Inject the quote outage through a real, exclusive fenced owner while
        # workers are stopped; never forge its UDF or weaken any guard.
        self.router.close()
        database = Database(self.shard_path(0))
        fence = WriterFence(database)
        token = fence.acquire("independent-outage-injector", 10)
        try:
            with database.for_writer(token).transaction() as connection:
                connection.execute("DELETE FROM uta_market")
        finally:
            fence.release(token)
        self.router.start()
        deadline = monotonic() + 5
        while self.router.worker_pid(0) is None and monotonic() < deadline:
            sleep(.01)
        pid = self.suspend_outside_transaction(0)
        try:
            with Database(self.shard_path(0)).inbox_transaction() as connection:
                connection.execute("INSERT INTO uta_command_inbox(command_id,account_id,kind,payload,state,enqueued_at) "
                    "VALUES (?,?,?,'{}','PENDING',?)", ("repayment-poison", self.accounts[0],
                    "UNRECOGNIZED_KIND", datetime.now(timezone.utc).isoformat()))
            self.router.repay(self.accounts[0], "process-repayment", "USD", D(4))
        finally:
            try:
                os.kill(pid, signal.SIGCONT)
            except ProcessLookupError:
                pass
        self.assertEqual(self.wait("repayment-poison", state="QUARANTINED")["attempts"], 2)
        repayment = self.wait("process-repayment")
        self.assertEqual((repayment["result"]["interest_repaid"], repayment["result"]["principal_repaid"]), ("1", "3"))
        with closing(sqlite3.connect(self.shard_path(0))) as connection:
            principal, interest = connection.execute("SELECT principal,interest FROM uta_liabilities WHERE account_id=? AND asset='USD'", (self.accounts[0],)).fetchone()
            self.assertEqual((principal, interest), ("7", "0"))
            balance, = connection.execute("SELECT units FROM ledger_balances WHERE account=? AND asset='USD'", ("customer:" + self.accounts[0],)).fetchone()
            self.assertEqual(D(balance) / D(10**8), D(1006))
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM credit_commands WHERE command_id='process-repayment' AND kind='repaid'").fetchone()[0], 1)
        before = financial_snapshot(self.shard_path(0))
        self.assertEqual(self.router.repay(self.accounts[0], "process-repayment", "USD", D(4)), repayment)
        self.assertEqual(financial_snapshot(self.shard_path(0)), before)

    def test_missing_managed_shard_is_not_recreated_and_persists_global_halt(self):
        from uta.durable_process import DurableProcessRouter
        self.active()
        self.router.close()
        self.shard_path(1).unlink()
        with self.assertRaises((ServiceError, WriterFenceError, StorageError)):
            DurableProcessRouter(self.path)
        self.assertFalse(self.shard_path(1).exists(), "startup silently recreated a missing financial shard")
        self.assertTrue(self.control_state()["halted"])
        self.assertEqual(financial_snapshot(self.shard_path(0))["uta_orders"], [])

    def test_startup_with_missing_funding_claim_halts_instead_of_restarting_into_new_risk(self):
        from uta.durable_process import DurableProcessRouter
        self.active()
        self.router.close()
        # Deliberate uncooperative control restore, preserving its schema guards
        # while emulating a missing historical claim. Financial state is intact.
        with closing(sqlite3.connect(self.path / "router.sqlite3")) as connection, connection:
            connection.execute("DROP TRIGGER router_pool_sources_no_delete")
            connection.execute("DELETE FROM router_pool_sources WHERE source_reference='synthetic:process:fund'")
            connection.execute("CREATE TRIGGER router_pool_sources_no_delete BEFORE DELETE ON router_pool_sources BEGIN SELECT RAISE(ABORT,'source claims are immutable'); END")
        try:
            recovered = DurableProcessRouter(self.path, lease_seconds=1, poll_interval=.01)
        except ServiceError as error:
            self.assertEqual(error.code, "funding_registry_conflict")
        else:
            self.addCleanup(recovered.close)
            recovered.start()
            deadline = monotonic() + 8
            while not self.control_state()["halted"] and monotonic() < deadline:
                sleep(.01)
        self.assertTrue(self.control_state()["halted"])
        self.assertEqual(self.control_state()["error"], "funding_registry_conflict")
        for shard in range(2):
            self.assertEqual(financial_snapshot(self.shard_path(shard))["uta_orders"], [])


if __name__ == "__main__":
    unittest.main()
