"""Fixed once-only parent FD capture for three local funding SQL methods.

Five new synthetic DBs only; no existing authority or service. The sole target
is an owned timeout/taskset interpreter executing retained approved buffers.
"""
import argparse
import base64
from hashlib import sha256
import json
import os
from pathlib import Path
import selectors
import stat
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
PLAN = "evidence/reviews/perpetual-funding-local/sql-once-plan.json"
INNER = "tools/run_funding_sql_once.py"
RAW_LIMIT, TRAILER_RESERVE = 32768, 512
FILE_LIMIT = 4 * 1024 * 1024
LOGICAL_LIMIT = 8 * 1024 * 1024
CONTROL_RESERVED = 0
INNER_MODE = bool(globals().get("_RETAINED_INNER_MODE", False))
BOOTSTRAP = r'''
import base64, hashlib, json, os, pathlib, stat, sys
path = pathlib.Path(sys.argv[1])
if path.resolve() != path or not stat.S_ISREG(path.lstat().st_mode):
    raise ValueError("nonregular retained capsule")
fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
with os.fdopen(fd, "rb") as handle:
    before = os.fstat(handle.fileno())
    raw = handle.read(4 * 1024 * 1024 + 1)
    after = os.fstat(handle.fileno())
if len(raw) > 4 * 1024 * 1024 or any(getattr(before, k) != getattr(after, k)
        for k in ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")):
    raise ValueError("retained capsule changed")
if hashlib.sha256(raw).hexdigest() != sys.argv[2]:
    raise ValueError("retained capsule SHA differs")
capsule = json.loads(raw)
plan_raw = base64.b64decode(capsule["plan"], validate=True)
if hashlib.sha256(plan_raw).hexdigest() != sys.argv[3]:
    raise ValueError("approved plan SHA differs")
plan = json.loads(plan_raw)
frozen = {name: base64.b64decode(value, validate=True) for name, value in capsule["inputs"].items()}
if set(frozen) != set(plan["input_files"]):
    raise ValueError("retained input set differs")
for name, expected in plan["input_files"].items():
    value = frozen[name]
    if {"bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()} != expected:
        raise ValueError("retained input pin differs")
root = pathlib.Path(capsule["root"])
driver = "tools/run_funding_sql_once.py"
namespace = {"__name__": "funding_retained_inner", "__file__": str(root / driver),
    "_RETAINED_INNER_MODE": True,
    "_PARENT_CAPTURE_CAPSULE": {"plan_raw": plan_raw, "inputs": frozen}}
exec(compile(frozen[driver], str(root / driver), "exec"), namespace)
raise SystemExit(namespace["inner"](["--parent-captured-stdio", "--source-commit", sys.argv[4],
    "--plan-sha256", sys.argv[3], "--private-directory", sys.argv[5]]))
'''


def read_regular(path, limit=FILE_LIMIT):
    if path.resolve() != path or not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError("not a canonical regular file")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as handle:
        before = os.fstat(handle.fileno())
        raw = handle.read(limit + 1)
        after = os.fstat(handle.fileno())
    keys = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_mode")
    if len(raw) > limit or any(getattr(before, key) != getattr(after, key) for key in keys):
        raise ValueError("file exceeded limit or changed during read")
    return raw


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def new_file(path, raw=None):
    global CONTROL_RESERVED
    if raw is not None:
        # The retained child has three fixed control writes, sharing 1MiB.
        # Parent control/capsule bytes reserve that allowance and all raw bytes.
        limit = 1024 * 1024 if INNER_MODE else LOGICAL_LIMIT - 1024 * 1024 - RAW_LIMIT
        if len(raw) > FILE_LIMIT or CONTROL_RESERVED + len(raw) > limit:
            raise ValueError("fixed logical control-file budget exhausted")
        CONTROL_RESERVED += len(raw)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    if raw is None:
        return fd
    with os.fdopen(fd, "wb") as handle:
        if handle.write(raw) != len(raw):
            raise OSError("short control-file write")
        handle.flush()
        os.fsync(handle.fileno())


def git(*arguments, seconds=3):
    result = subprocess.run(["/usr/bin/git", "--no-optional-locks", "-C", str(ROOT), *arguments],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=seconds,
        env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null"})
    if len(result.stdout) > FILE_LIMIT or result.stderr:
        raise ValueError("unexpected Git output")
    return result.stdout


class SharedRaw:
    def __init__(self):
        self.reserved, self.written, self.failed = 0, 0, False

    def payload(self, fd, raw):
        if self.failed:
            return
        if self.reserved + len(raw) > RAW_LIMIT - TRAILER_RESERVE:
            self.failed = True
            return
        self.reserved += len(raw)  # Charged before the only attempted FD write.
        try:
            count = os.write(fd, raw)
            if type(count) is not int or not 0 <= count <= len(raw):
                self.failed = True
                return
            self.written += count
            if count != len(raw):
                self.failed = True  # No refund, continuation, or later payload.
        except BaseException:
            self.failed = True

    def trailer(self, fd, value):
        raw = encoded(value)
        if len(raw) > TRAILER_RESERVE:
            self.failed = True
            return
        try:
            if os.write(fd, raw) != len(raw):
                self.failed = True
        except BaseException:
            self.failed = True


def inner(argv):
    """Run three fixed SQL methods once, then reopen exactly five owned DBs."""
    import _thread
    import dataclasses
    import datetime
    import decimal
    import fractions
    import hashlib
    import importlib.abc
    import importlib.util
    import linecache
    import re
    import resource
    import sqlite3
    import threading
    from types import ModuleType
    import unittest

    parser = argparse.ArgumentParser(description=inner.__doc__)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--private-directory", required=True, type=Path)
    parser.add_argument("--parent-captured-stdio", action="store_true")
    args = parser.parse_args(argv)
    capsule = globals().get("_PARENT_CAPTURE_CAPSULE")
    if not args.parent_captured_stdio or type(capsule) is not dict:
        raise ValueError("retained parent-captured mode is mandatory")
    plan_raw, frozen = capsule["plan_raw"], capsule["inputs"]
    if sha256(plan_raw).hexdigest() != args.plan_sha256:
        raise ValueError("unapproved plan")
    plan = json.loads(plan_raw)
    methods = (
        "test_fresh_period_retry_reopen_and_period_uniqueness",
        "test_mandatory_debit_uses_cash_deficit_and_real_risk_state",
        "test_corrupt_reserved_id_rejects_atomically_and_late_freeze_is_not_backdated",
    )
    labels = ("period", "distress", "rollback", "late", "capital")
    if plan["methods"] != list(methods) or set(frozen) != set(plan["input_files"]):
        raise ValueError("fixed three-method/input scope differs")
    for name, expected in plan["input_files"].items():
        value = frozen[name]
        if type(value) is not bytes or {"bytes": len(value), "sha256": sha256(value).hexdigest()} != expected:
            raise ValueError("retained source pin differs")
        if name.endswith(".py"):
            linecache.cache[str(ROOT / name)] = (
                len(value), None, value.decode("utf-8").splitlines(True), str(ROOT / name))
    oracle = json.loads(frozen["evidence/reviews/perpetual-funding-local/sql-once-oracle.json"])
    if oracle["fixture_order"] != list(labels):
        raise ValueError("fixed five-case oracle differs")
    output = args.private_directory
    if (not output.is_absolute() or output.resolve() != output
            or output.name != "inner" or output.parent.parent != Path("/workspace")):
        raise ValueError("new canonical inner namespace required")
    output.mkdir(mode=0o700)
    dbroot = output / "cases"
    dbroot.mkdir(mode=0o700)
    # Inherited environment never selects an old test authority or temp root.
    os.environ["UTA_FUNDING_CASE_ROOT"] = str(dbroot)
    os.umask(0o077)
    # Per-file native write ceiling; this is explicitly NOT an aggregate quota.
    resource.setrlimit(resource.RLIMIT_FSIZE, (FILE_LIMIT, FILE_LIMIT))
    executable = Path(sys.executable).resolve()
    binary = read_regular(executable, 64 * 1024 * 1024)
    runtime = {"sys_executable": sys.executable, "resolved_executable": str(executable),
        "executable_bytes": len(binary), "executable_sha256": sha256(binary).hexdigest(),
        "sys_version": sys.version, "affinity": sorted(os.sched_getaffinity(0)),
        "flags": {"isolated": sys.flags.isolated, "no_site": sys.flags.no_site,
                  "dont_write_bytecode": sys.flags.dont_write_bytecode}}
    if runtime != plan["expected_runtime"]:
        raise ValueError("actual runtime/CPU differs from plan")
    if any(name == "uta" or name.startswith("uta.") for name in sys.modules):
        raise ValueError("UTA preloaded outside retained source")
    expected_db = {label: dbroot / label / "funding.sqlite3" for label in labels}
    families = {str(path) + suffix for path in expected_db.values()
                for suffix in ("", "-wal", "-shm", "-journal")}
    uris = {path.as_uri() + "?mode=" + mode
            for path in expected_db.values() for mode in ("rw", "ro")}
    new_file(output / "intent.json", encoded({"source_commit": args.source_commit,
        "plan_sha256": args.plan_sha256, "runtime": runtime, "input_files": plan["input_files"],
        "fixed_methods": list(methods), "exact_DB_files": sorted(families),
        "RLIMIT_FSIZE_each_file": resource.getrlimit(resource.RLIMIT_FSIZE),
        "caller_actual_exit_required": True}))
    forbidden, handles, connections = [], [], []
    observations, peak_observed_bytes, peak_observed_files = 0, 0, 0
    disk_problem = None

    def denied(event):
        if len(forbidden) < 16:
            forbidden.append(event)
        raise RuntimeError("funding SQL scope forbids " + event)

    def temp_name(path):
        return (path.parent in {value.parent for value in expected_db.values()}
                and path.name.startswith(".uta-create-"))

    def disk_snapshot():
        nonlocal observations, peak_observed_bytes, peak_observed_files, disk_problem
        facts, total = [], 0
        for path in sorted(dbroot.rglob("*")):
            info = path.lstat()
            if stat.S_ISDIR(info.st_mode):
                if path not in {value.parent for value in expected_db.values()}:
                    disk_problem = "unexpected DB directory"
                    raise ValueError(disk_problem)
                continue
            if (path.resolve() != path or not stat.S_ISREG(info.st_mode)
                    or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077
                    or (str(path) not in families and not temp_name(path))
                    or info.st_size > FILE_LIMIT or temp_name(path) and info.st_size != 0):
                disk_problem = "unexpected/nonprivate/oversize DB resource"
                raise ValueError(disk_problem)
            total += info.st_size
            facts.append({"path": str(path.relative_to(dbroot)), "bytes": info.st_size,
                          "mode": stat.S_IMODE(info.st_mode)})
        observations += 1
        peak_observed_bytes = max(peak_observed_bytes, total)
        peak_observed_files = max(peak_observed_files, len(facts))
        if total > 80 * 1024 * 1024 or len(facts) > 25:
            disk_problem = "DB logical resource bound exceeded"
            raise ValueError(disk_problem)
        return facts

    def audit(event, arguments):
        if event in {"subprocess.Popen", "os.fork", "os.forkpty", "os.exec", "os.posix_spawn",
                     "os.system", "os.kill", "os.killpg", "os.rmdir", "os.truncate",
                     "socket.__new__", "socket.connect", "socket.bind", "socket.getaddrinfo"}:
            denied(event)
        if event == "sqlite3.connect":
            if not arguments or arguments[0] not in uris:
                denied("sqlite3.connect:outside_exact_five")
            disk_snapshot()
            connections.append(arguments[0])
            if len(connections) > 1024:
                denied("sqlite3.connect:count_limit")
        if event == "sqlite3.connect/handle":
            if not arguments or type(arguments[0]) is not sqlite3.Connection:
                denied("sqlite3.connect/handle:not_native_connection")
            handles.append(arguments[0])
        if event == "open" and arguments and isinstance(arguments[0], (str, bytes)):
            path = Path(os.fsdecode(arguments[0]))
            flags = arguments[2] if len(arguments) > 2 else 0
            if str(path).startswith("/proc/"):
                denied("open:proc")
            if str(path).endswith((".sqlite", ".sqlite3", ".db", "-wal", "-shm", "-journal")) and str(path) not in families:
                denied("open:foreign_authority")
            if type(flags) is int and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC):
                controls = {output / name for name in ("intent.json", "execution.json", "oracle-details.json")}
                if path not in controls and not temp_name(path):
                    denied("open:unapproved_write")
        if event in {"os.remove", "os.unlink"}:
            if not arguments or not temp_name(Path(os.fsdecode(arguments[0]))):
                denied("unlink:not_private_empty_publication_temp")
        if event == "os.link":
            if (len(arguments) < 2 or not temp_name(Path(os.fsdecode(arguments[0])))
                    or Path(os.fsdecode(arguments[1])) not in expected_db.values()
                    or Path(os.fsdecode(arguments[0])).parent != Path(os.fsdecode(arguments[1])).parent):
                denied("link:outside_exact_five")
        if event in {"os.rename", "os.symlink"}:
            denied(event)
        if event == "os.mkdir":
            if not arguments or Path(os.fsdecode(arguments[0])) not in {value.parent for value in expected_db.values()}:
                denied("mkdir:outside_exact_five")

    def no_thread(*arguments, **keywords):
        denied("thread_start")

    sys.addaudithook(audit)
    threading.Thread.start = no_thread
    _thread.start_new_thread = no_thread
    if hasattr(threading, "_start_new_thread"):
        threading._start_new_thread = no_thread

    class FrozenLoader(importlib.abc.Loader):
        def __init__(self, relative):
            self.relative = relative
        def create_module(self, spec):
            return None
        def exec_module(self, module):
            exec(compile(frozen[self.relative], str(ROOT / self.relative), "exec"), module.__dict__)

    class FrozenUTA(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname != "uta" and not fullname.startswith("uta."):
                return None
            relative = "uta/__init__.py" if fullname == "uta" else fullname.replace(".", "/") + ".py"
            if relative not in frozen:
                raise ImportError("unretained UTA module: " + fullname)
            return importlib.util.spec_from_file_location(fullname, ROOT / relative,
                loader=FrozenLoader(relative), submodule_search_locations=[] if fullname == "uta" else None)

    def closed_handles():
        open_count = 0
        for handle in handles:
            try:
                handle.in_transaction
            except sqlite3.ProgrammingError as error:
                if str(error) != "Cannot operate on a closed database.":
                    raise
                continue
            open_count += 1
        return {"observed_handles": len(handles), "open_handles_before_cleanup": open_count,
                "all_observed_handles_already_closed": open_count == 0}

    sys.meta_path.insert(0, FrozenUTA())
    fixture = ModuleType("funding_sql_fixture")
    fixture.__file__ = str(ROOT / "tests/test_perpetual_funding_local.py")
    sys.modules[fixture.__name__] = fixture
    print(json.dumps({"event": "FUNDING_SQL_BEGIN", "source_commit": args.source_commit,
        "runtime": runtime, "selected_methods": list(methods), "input_count": len(frozen)}), flush=True)
    started = time.monotonic_ns()
    exec(compile(frozen["tests/test_perpetual_funding_local.py"], fixture.__file__, "exec"), fixture.__dict__)
    original_fixture, owned = fixture.fixture, {}

    def once_fixture(test, label, **keywords):
        if label != labels[len(owned)] or label in owned:
            raise ValueError("fixture repeated, extra, or reordered")
        data = original_fixture(test, label, **keywords)
        owned[label] = data
        if label == "distress":
            data.service.submit_order("a", "synthetic-pending-ro", "BTC-PERP",
                decimal.Decimal("-.1"), decimal.Decimal(100), reduce_only=True)
        disk_snapshot()
        return data

    fixture.fixture = once_fixture  # Declared extra setup; original three method bytes unchanged.
    result = unittest.TextTestRunner(stream=sys.stderr, verbosity=2, failfast=True).run(
        unittest.TestSuite(fixture.FundingLocalSQLTests(name) for name in methods))
    tests_elapsed = time.monotonic_ns() - started
    closure_before = closed_handles()
    details, oracle_passed, oracle_error = {}, False, None
    try:
        if not (result.testsRun == 3 and result.wasSuccessful() and not result.skipped
                and not result.expectedFailures and not result.unexpectedSuccesses):
            raise ValueError("first method failure/unknown stops SQL; no post-SQL oracle")
        if list(owned) != list(labels) or not closure_before["all_observed_handles_already_closed"]:
            raise ValueError("missing cases or live SQL resource before reopen")
        from uta.existing_services import _source_arguments
        from uta.funding_local import FundingError
        from uta.matching import Matcher
        from uta.service import ExchangeService
        from uta.storage import Database
        from uta.decision_audit import _json as audit_json
        from uta.decision_audit import code_artifact
        from fractions import Fraction
        from decimal import Decimal
        totals = {"matches": 0, "paired_fills": 0, "ledger_events": 0, "committed_periods": 0}
        fee_total, custody_total = Fraction(), Fraction()
        for label in labels:
            expected, data = oracle["cases"][label], owned[label]
            database = Database(expected_db[label])
            # Actual new handle, ro URI, guarded read role; no schema repair constructor.
            with database.read_transaction() as connection:
                scales, arguments = _source_arguments(connection)
                service = ExchangeService(database, scales, clock=lambda: data.clock["now"],
                    _existing_connection=connection, **arguments)
                if connection.execute("PRAGMA query_only").fetchone()[0] != 1:
                    raise ValueError("reopen snapshot is not query-only")
                ledger_events = service.ledger.verify(connection=connection)
                if ledger_events != expected["ledger_events"]:
                    raise ValueError("manual journal count differs: " + label)
                for account, amount in expected["customers"].items():
                    if service.ledger.balance("customer:" + account, "USD", connection=connection) != Decimal(amount):
                        raise ValueError("manual customer cash differs: " + label + ":" + account)
                for account, amount in {**expected["system"], "system:perpetual-funding-clearing": "0", "system:funding-rounding-reserve": "0", "system:realized-pnl": "0"}.items():
                    if service.ledger.balance(account, "USD", connection=connection) != Decimal(amount):
                        raise ValueError("manual system cash differs: " + label + ":" + account)
                manual_balances = {"customer:" + account: Fraction(Decimal(amount))
                                   for account, amount in expected["customers"].items()}
                manual_balances.update({account: Fraction(Decimal(amount))
                                        for account, amount in expected["system"].items()})
                actual_balances = {(row["account"], row["asset"]): Fraction(int(row["units"]), 100)
                                   for row in connection.execute("SELECT * FROM ledger_balances")
                                   if int(row["units"])}
                if actual_balances != {(account, "USD"): amount for account, amount in manual_balances.items() if amount}:
                    raise ValueError("unexpected nonzero ledger account or asset")
                if {row[0] for row in connection.execute("SELECT account_id FROM uta_accounts")} != set(expected["customers"]):
                    raise ValueError("unexpected customer inventory")
                positions = {(row["account_id"], row["symbol"]): [Fraction(Decimal(row["quantity"])), Fraction(Decimal(row["cost_basis"]))]
                             for row in connection.execute("SELECT * FROM uta_positions")}
                if positions != {(account, oracle["base"]["symbol"]): [Fraction(Decimal(value)) for value in pair]
                                 for account, pair in expected["positions"].items()}:
                    raise ValueError("manual position inventory/cost differs: " + label)
                if connection.execute("SELECT COUNT(*) FROM uta_liabilities").fetchone()[0] != 0:
                    raise ValueError("cash deficit masqueraded as borrowing")
                matching = Matcher(service, initialize=False).verify(strict=True, connection=connection)
                if (matching["matches"], matching["paired_fills"], matching["unpaired_fills"]) != (expected["matches"], expected["paired_fills"], 0):
                    raise ValueError("manual match/fill count differs: " + label)
                trades = [[Fraction(Decimal(row[0])), Fraction(Decimal(row[1]))] for row in
                          connection.execute("SELECT quantity,price FROM uta_matches ORDER BY sequence")]
                if trades != [[Fraction(1), Fraction(100)]] + ([[Fraction(3, 5), Fraction(100)]] if label == "capital" else []):
                    raise ValueError("manual unique trade size/price differs")
                fills = [(Fraction(Decimal(row[0])), Fraction(Decimal(row[1]))) for row in
                         connection.execute("SELECT fee,realized_pnl FROM uta_fills ORDER BY rowid")]
                if fills != [(Fraction(1, 25), Fraction())] * 2 + ([(Fraction(3, 100), Fraction())] * 2 if label == "capital" else []):
                    raise ValueError("manual per-side fees/PnL differ")
                # These real component verifiers join this new read snapshot;
                # the original funding object retains only its policy/artifact.
                if label == "rollback":
                    try:
                        data.funding.verify(connection=connection)
                    except FundingError as error:
                        if error.code != "funding_reconciliation":
                            raise
                        funding = {"expected_orphan_rejected": True, "code": error.code}
                    else:
                        raise ValueError("deliberate orphan was silently accepted")
                else:
                    funding = data.funding.verify(connection=connection)
                    if not funding["funding_reconciled"] or funding["periods"] != expected["periods"]:
                        raise ValueError("manual period/funding reconciliation differs")
                rows = list(connection.execute("SELECT command_id,receipt FROM funding_local_periods ORDER BY rowid"))
                if len(rows) != expected["periods"]:
                    raise ValueError("unexpected committed period")
                if rows:
                    receipt = json.loads(rows[0]["receipt"])
                    if (rows[0]["command_id"] != expected["command"]
                            or {leg["account_id"]: leg["cash_units"] for leg in receipt["plan"]["legs"]} != expected["funding_cash_units"]
                            or Decimal(receipt["plan"]["rate"]) != Decimal(expected["rate"])
                            or Decimal(receipt["plan"]["mark"]) != Decimal(expected["mark"])
                            or len(receipt["journals"]) != expected["funding_journals"]):
                        raise ValueError("manual funding cash/command/journal differs")
                    if label == "distress":
                        risk, action = receipt["risk_after"]["a"], receipt["risk_actions"]["a"]
                        policy = expected["risk"]
                        for key in ("cash_deficit_value", "principal_value", "equity", "maintenance_margin"):
                            if Decimal(risk[key]) != Decimal(policy[key]):
                                raise ValueError("distress manual risk differs: " + key)
                        if (action["state"], action["cycle"], action["revision"]) != ("LIQUIDATING", 1, 1):
                            raise ValueError("native liquidation state/plan revision differs")
                        old = connection.execute("SELECT * FROM uta_orders WHERE account_id='a' AND order_id='synthetic-pending-ro'").fetchone()
                        live = list(connection.execute("SELECT * FROM uta_orders WHERE account_id='a' AND status IN ('OPEN','PARTIALLY_FILLED')"))
                        if (old is None or old["status"] != "CANCELLED" or old["symbol"] != "BTC-PERP"
                                or Decimal(old["quantity"]) != Decimal("-.1") or Decimal(old["limit_price"]) != 100
                                or old["reduce_only"] != 1 or Decimal(old["filled_quantity"]) != 0
                                or len(live) != 1 or not live[0]["order_id"].startswith("liq:1:1:")
                                or live[0]["symbol"] != "BTC-PERP" or live[0]["reduce_only"] != 1
                                or live[0]["status"] != "OPEN" or Decimal(live[0]["quantity"]) != -1
                                or Decimal(live[0]["limit_price"]) != 100 or Decimal(live[0]["filled_quantity"]) != 0
                                or {row["order_id"] for row in action["cancelled_orders"]} != {old["order_id"]}
                                or [row["order_id"] for row in action["created_orders"]] != [live[0]["order_id"]]):
                            raise ValueError("actual cancelled/replacement RO plan differs")
                        state = connection.execute("SELECT state,cycle,revision FROM uta_liquidation_accounts WHERE account_id='a'").fetchone()
                        if tuple(state) != ("LIQUIDATING", 1, 1):
                            raise ValueError("risk action is not actual persisted state")
                    if label == "capital" and (receipt["capital_transfer"]["deposit_reference"] != expected["capital_reference"]
                            or Decimal(receipt["capital_transfer"]["amount"]) != Decimal(".01")):
                        raise ValueError("real deposited treasury capital proof differs")
                manifests = list(connection.execute("SELECT manifest FROM uta_code_artifacts"))
                if len(manifests) != 1 or manifests[0][0] != audit_json(code_artifact()):
                    raise ValueError("reopened stored base source/runtime artifact differs")
                totals["matches"] += matching["matches"]; totals["paired_fills"] += matching["paired_fills"]
                totals["ledger_events"] += ledger_events; totals["committed_periods"] += len(rows)
                fee_total += Fraction(service.ledger.balance("system:fees", "USD", connection=connection))
                custody_total += Fraction(service.ledger.balance("system:custody", "USD", connection=connection))
                details[label] = {"matching": matching, "ledger_events": ledger_events,
                    "committed_periods": len(rows), "funding": funding,
                    "manual_cash_positions_and_system_accounts_equal": True,
                    "schema_and_current_artifact_verified_without_repair": True,
                    "fresh_ro_snapshot": True}
            disk_snapshot()
        if (totals != {key: oracle["aggregate"][key] for key in totals}
                or fee_total != Fraction(Decimal(oracle["aggregate"]["fees_USD"]))
                or custody_total != Fraction(Decimal(oracle["aggregate"]["custody_USD"]))):
            raise ValueError("manual aggregate match/fill/journal/cash differs")
        oracle_passed = True
    except BaseException as failure:
        oracle_error = type(failure).__name__ + ": " + str(failure)
    closure_after = closed_handles()
    # Never relabel a leak as success: cleanup only handles owned by this run,
    # after recording the pre-cleanup failure; do not touch any foreign DB/PID.
    cleaned = 0
    if not closure_after["all_observed_handles_already_closed"]:
        for handle in handles:
            try:
                handle.in_transaction
            except sqlite3.ProgrammingError as error:
                if str(error) != "Cannot operate on a closed database.":
                    raise
                continue
            handle.close(); cleaned += 1
    facts = disk_snapshot()
    if any(temp_name(dbroot / fact["path"]) for fact in facts):
        oracle_passed, oracle_error = False, "private publication temp remained"
    connection_accounting_ok = (len(connections) == len(handles) and len(handles) > 0
        and len({uri.rsplit("?mode=", 1)[0] for uri in connections}) == 5)
    resources = {"before_reopen": closure_before, "after_reopen_before_cleanup": closure_after,
        "own_leaked_handles_closed_after_failure": cleaned, "connect_count": len(connections),
        "all_observed_handles_closed_after_cleanup": closed_handles()["all_observed_handles_already_closed"],
        "connection_events_and_handles_and_five_paths_match": connection_accounting_ok,
        "exact_distinct_DB_URIs": sorted(set(connections)), "disk_observations": observations,
        "peak_observed_logical_DB_bytes": peak_observed_bytes,
        "peak_observed_DB_files": peak_observed_files, "disk_problem": disk_problem,
        "actual_final_DB_files": len(facts), "actual_final_DB_logical_bytes": sum(fact["bytes"] for fact in facts),
        "observation_is_not_continuous_native_write_monitoring": True,
        "aggregate_quota_claimed": False, "actual_RLIMIT_FSIZE": list(resource.getrlimit(resource.RLIMIT_FSIZE))}
    # Hash DB bytes only after all owned observed connections are closed.
    resources["final_DB_files"] = [{**fact, "sha256": sha256(read_regular(dbroot / fact["path"])).hexdigest()}
                                     for fact in facts]
    new_file(output / "oracle-details.json", encoded({"cases": details, "resources": resources,
        "oracle_passed": oracle_passed, "oracle_error": oracle_error}))
    loaded = sorted(name for name in sys.modules if name == "uta" or name.startswith("uta."))
    required = {"uta", "uta.perpetual_funding", "uta.funding_local", "uta.service", "uta.storage",
                "uta.credit_artifact", "uta.matching", "uta.writer_fence", "uta.existing_services"}
    loaded_ok = required <= set(loaded) and all(
        name == "uta" or name.replace(".", "/") + ".py" in frozen for name in loaded)
    after = {name: read_regular(ROOT / name) for name in frozen}
    unchanged = after == frozen and read_regular(ROOT / PLAN) == plan_raw
    actual_runtime_after = sorted(os.sched_getaffinity(0))
    passed = (result.testsRun == 3 and result.wasSuccessful() and not result.skipped
        and not result.expectedFailures and not result.unexpectedSuccesses
        and not forbidden and unchanged and actual_runtime_after == [1] and loaded_ok
        and oracle_passed and closure_before["all_observed_handles_already_closed"]
        and closure_after["all_observed_handles_already_closed"] and not disk_problem
        and connection_accounting_ok)
    receipt = {"source_commit_invoker_label": args.source_commit, "runtime": runtime,
        "selected_methods": list(methods), "tests_run": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors),
        "skipped": len(result.skipped), "expected_failures": len(result.expectedFailures),
        "unexpected_successes": len(result.unexpectedSuccesses), "tests_elapsed_ns": tests_elapsed,
        "elapsed_ns": time.monotonic_ns() - started, "input_pins_after": plan["input_files"],
        "source_before_after_equal": unchanged, "forbidden_attempts": forbidden,
        "loaded_UTA_modules": loaded, "loaded_UTA_modules_all_retained": loaded_ok,
        "actual_affinity_after": actual_runtime_after, "returncode": 0 if passed else 1,
        "SQL_test_methods_selected": True, "workers_or_server_or_network_authorized": False,
        "oracle_passed": oracle_passed, "oracle_error": oracle_error,
        "oracle_case_count": len(details), "expected_fresh_DBs": 5,
        "expected_matches": 6, "expected_paired_fills": 12,
        "all_owned_handles_closed_before_cleanup": closure_after["all_observed_handles_already_closed"],
        "connection_events_and_handles_and_five_paths_match": connection_accounting_ok,
        "private_DB_and_capsule_export_authorized": False, "production_approved": False}
    new_file(output / "execution.json", encoded(receipt))
    print(json.dumps({"event": "FUNDING_SQL_END", **receipt}), flush=True)
    return 0 if passed else 1


def run(args):
    if not args.execute:
        raise ValueError("explicit once-only execution flag required")
    os.sched_setaffinity(0, {1})
    if sorted(os.sched_getaffinity(0)) != [1]:
        raise ValueError("CPU1 binding failed")
    if git("rev-parse", "HEAD").decode().strip() != args.source_commit:
        raise ValueError("actual source HEAD differs")
    plan_raw = read_regular(ROOT / PLAN)
    if sha256(plan_raw).hexdigest() != args.plan_sha256 or plan_raw != git("show", args.source_commit + ":" + PLAN):
        raise ValueError("plan differs from approved SHA/Git")
    plan = json.loads(plan_raw)
    frozen = {}
    for name, pin in plan["input_files"].items():
        if name.startswith("/") or ".." in Path(name).parts:
            raise ValueError("source path escapes checkout")
        raw = read_regular(ROOT / name)
        if {"bytes": len(raw), "sha256": sha256(raw).hexdigest()} != pin or raw != git("show", args.source_commit + ":" + name):
            raise ValueError("source physical/Git pin differs: " + name)
        frozen[name] = raw
    output = Path(args.output)
    if (not output.is_absolute() or output.resolve() != output
            or output.parent != Path("/workspace")):
        raise ValueError("output is not new canonical absolute namespace")
    output.mkdir(mode=0o700)
    args.output_created = True
    capsule_raw = encoded({"root": str(ROOT), "plan": base64.b64encode(plan_raw).decode(),
        "inputs": {name: base64.b64encode(raw).decode() for name, raw in frozen.items()}})
    if len(capsule_raw) > FILE_LIMIT:
        raise ValueError("capsule exceeds bound")
    capsule = output / "immutable-inputs.json"
    new_file(capsule, capsule_raw)
    command = ["/usr/bin/timeout", "--signal=KILL", "20s", "/usr/bin/taskset", "-c", "1",
        plan["expected_runtime"]["resolved_executable"], "-I", "-S", "-B", "-c", BOOTSTRAP,
        str(capsule), sha256(capsule_raw).hexdigest(), args.plan_sha256, args.source_commit, str(output / "inner")]
    new_file(output / "intent.json", encoded({"source_commit": args.source_commit,
        "plan_sha256": args.plan_sha256, "capsule_sha256": sha256(capsule_raw).hexdigest(),
        "argv": command, "actual_outer_affinity": sorted(os.sched_getaffinity(0)),
        "raw_limit": RAW_LIMIT, "trailer_reserve": TRAILER_RESERVE, "attempt": 1,
        "SQL_exact_five_fresh_authorities_only": True, "worker_authorized": False}))
    out_fd = new_file(output / "first.stdout.txt")
    err_fd = new_file(output / "first.stderr.txt")
    capture, process, host_exit, reaped, eof = SharedRaw(), None, None, False, False
    started = time.monotonic_ns()
    deadline = time.monotonic() + 22
    error, drift = None, None
    try:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, cwd=ROOT, close_fds=True)
        args.host_started = True
        selector = selectors.DefaultSelector()
        for stream, destination in ((process.stdout, out_fd), (process.stderr, err_fd)):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, destination)
        while selector.get_map() and time.monotonic() < deadline:
            for key, unused in selector.select(min(.05, max(0, deadline - time.monotonic()))):
                try:
                    raw = os.read(key.fileobj.fileno(), 65536)
                except BlockingIOError:
                    continue
                if raw:
                    capture.payload(key.data, raw)
                else:
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
        eof = not selector.get_map()
        selector.close()
        host_exit = process.wait(timeout=max(0, deadline - time.monotonic()))
        reaped = True
    except BaseException as failure:
        error = type(failure).__name__
    finally:
        if process is not None:
            for stream in (process.stdout, process.stderr):
                if not stream.closed:
                    stream.close()
            if not reaped:
                try:
                    host_exit = process.wait(timeout=max(0, deadline - time.monotonic()))
                    reaped = True
                except BaseException:
                    pass
        args.host_exit, args.host_reaped = host_exit, reaped
        new_file(output / "actual-host-exit.txt", ("UNKNOWN" if host_exit is None else str(host_exit)).encode() + b"\n")
    finished = time.monotonic_ns()
    try:
        if time.monotonic() >= deadline:
            raise ValueError("outer target/drain deadline exceeded")
        if git("rev-parse", "HEAD", seconds=max(.001, min(1, deadline - time.monotonic()))).decode().strip() != args.source_commit:
            raise ValueError("source HEAD changed")
        for name, expected in frozen.items():
            if read_regular(ROOT / name) != expected:
                raise ValueError("source changed")
        if read_regular(ROOT / PLAN) != plan_raw or time.monotonic() >= deadline:
            raise ValueError("plan changed or outer completion late")
    except BaseException as failure:
        drift = type(failure).__name__
    inner, valid_end = None, False
    try:
        lines = read_regular(output / "first.stdout.txt", RAW_LIMIT).splitlines()
        records = [json.loads(line) for line in lines]
        if len(records) == 2 and records[0]["event"] == "FUNDING_SQL_BEGIN" and records[1]["event"] == "FUNDING_SQL_END":
            inner = json.loads(read_regular(output / "inner/execution.json"))
            valid_end = (records[1] == {"event": "FUNDING_SQL_END", **inner}
                and inner["source_commit_invoker_label"] == args.source_commit
                and inner["input_pins_after"] == plan["input_files"]
                and type(inner["tests_run"]) is int and inner["tests_run"] == 3
                and inner["source_before_after_equal"] is True
                and inner["selected_methods"] == plan["methods"]
                and inner["runtime"] == plan["expected_runtime"]
                and all(type(inner[field]) is int for field in
                    ("returncode", "failures", "errors", "skipped", "expected_failures", "unexpected_successes")))
    except BaseException:
        pass
    complete = valid_end and reaped and eof and error is None and drift is None and not capture.failed
    passed = (complete and host_exit == 0 and inner["returncode"] == 0 and inner["failures"] == 0
              and inner["errors"] == 0 and inner["skipped"] == 0
              and inner["expected_failures"] == 0 and inner["unexpected_successes"] == 0
              and inner["loaded_UTA_modules_all_retained"] is True
              and inner["SQL_test_methods_selected"] is True and inner["forbidden_attempts"] == []
              and inner["oracle_passed"] is True and inner["oracle_case_count"] == 5
              and inner["all_owned_handles_closed_before_cleanup"] is True
              and inner["connection_events_and_handles_and_five_paths_match"] is True)
    classification = "PASS_LIMITED_SQL_ONLY" if passed else "FAIL" if complete and host_exit == 1 else "UNKNOWN"
    status = 0 if passed else 1 if classification == "FAIL" else 125 if capture.failed else 126
    capture.trailer(err_fd, {"event": "FUNDING_SQL_HOST_END", "host_exit": host_exit,
        "reaped": reaped, "EOF": eof, "classification": classification, "status": status,
        "raw_sticky": capture.failed})
    if capture.failed:
        classification, status = "UNKNOWN", 125
    for fd in (out_fd, err_fd):
        os.fsync(fd)
        os.close(fd)
    raw_facts = {}
    for name in ("first.stdout.txt", "first.stderr.txt"):
        raw = read_regular(output / name, RAW_LIMIT)
        raw_facts[name] = {"bytes": len(raw), "sha256": sha256(raw).hexdigest()}
    if sum(item["bytes"] for item in raw_facts.values()) > RAW_LIMIT:
        classification, status = "UNKNOWN", 125
    new_file(output / "execution.json", encoded({"source_commit": args.source_commit,
        "actual_host_exit": host_exit, "actual_host_reaped": reaped, "both_raw_pipes_EOF": eof,
        "monotonic_start_ns": started, "monotonic_end_ns": finished, "elapsed_ns": finished - started,
        "inner": inner, "complete_inner_END": valid_end, "error": error, "source_or_deadline_drift": drift,
        "raw_reserved": capture.reserved, "raw_written": capture.written, "raw_sticky": capture.failed,
        "raw_files": raw_facts, "classification": classification, "outer_return_status": status,
        "production_approved": False}))
    new_file(output / "END.json", encoded({"event": "FUNDING_SQL_ENVELOPE_END", "classification": classification,
        "outer_return_status": status, "actual_host_exit": host_exit, "actual_host_reaped": reaped,
        "complete": bool(complete and not capture.failed), "production_approved": False}))
    # Final publication/fsync is in the same completion guard. An earlier END
    # cannot certify a successful future process exit; caller must observe it.
    tail_ns = time.monotonic_ns()
    late = time.monotonic() >= deadline
    new_file(output / "TAIL.json", encoded({"monotonic_through_final_publication_ns": tail_ns,
        "late": late, "caller_must_observe_actual_outer_exit": True,
        "outer_return_status": 126 if late else status, "production_approved": False}))
    if late or time.monotonic() >= deadline:
        return 126
    return status


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        raise SystemExit(run(args))
    except SystemExit:
        raise
    except BaseException as error:
        if getattr(args, "output_created", False):
            new_file(Path(args.output) / "ENVELOPE_UNKNOWN.json", encoded({"error_type": type(error).__name__,
                "host_started": getattr(args, "host_started", False), "actual_host_exit": getattr(args, "host_exit", None),
                "actual_host_reaped": getattr(args, "host_reaped", False), "complete": False, "status": 126}))
        raise SystemExit(126)
