"""Observe exact original MAIN-vs-TEMP verification; no default SQL action."""
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
from time import monotonic

ROOT = Path(__file__).resolve().parents[3]
TABLES = ("ledger_schema", "ledger_assets", "ledger_events", "ledger_postings", "ledger_balances")
SOURCES = {
    "baseline": {"path": Path("/workspace/uta-observer-freeze-91e4ae4"),
                 "financial_ref": "91e4ae40b5e9b884c54026406299df5000c9c100",
                 "also_equals_ref": "4ad58b2169b02f8982a1cbef8722b79d705d60c8"},
    "f01_candidate": {"path": ROOT,
                      "financial_ref": "8003ef6c3e0cf98b4891efea7885ffa141a68fdc"},
}
EXPECTED_BALANCES = [["a", "USD", "-1250"], ["b", "USD", "950"], ["c", "USD", "300"]]
EXPECTED_EVENT_HASHES = ["f0201ec2d6f7eaa23b3872bb381810108b5e4a4ef0ac1eae07d7573a534deab6",
                         "afe93ccca88c18e947e5bb4c62d8422da53bff3445986888a3a772ec82137d8c"]


def source_guard(label):
    spec = SOURCES[label]
    source, reference = spec["path"], spec["financial_ref"]
    assert subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=all"],
                                   cwd=source, text=True) == ""
    paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", reference, "uta"],
                                    cwd=source, text=True).splitlines()
    assert len(paths) == 52
    recorded = {}
    for name in paths:
        actual = (source / name).read_bytes()
        assert actual == subprocess.check_output(["git", "show", reference + ":" + name], cwd=source), name
        if spec.get("also_equals_ref"):
            assert actual == subprocess.check_output(["git", "show", spec["also_equals_ref"] + ":" + name], cwd=source), name
        recorded[name] = sha256(actual).hexdigest()
    return {"financial_ref": reference, "also_equals_ref": spec.get("also_equals_ref"),
            "actual_checkout_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip(),
            "source_root": str(source), "runtime_sha256": recorded}


def snapshot(connection, schema):
    assert schema in ("main", "temp")
    return {"tables": {name: [list(row) for row in connection.execute(
                'SELECT * FROM ' + schema + '."' + name + '" ORDER BY 1,2')] for name in TABLES},
            "catalogue": [list(row) for row in connection.execute(
                'SELECT type,name,tbl_name,sql FROM ' + schema + '.sqlite_master ORDER BY type,name')]}


def outcome(call):
    try:
        return {"returned": call(), "error_type": None, "error_message": None}
    except Exception as error:
        return {"returned": None, "error_type": type(error).__name__, "error_message": str(error)}


def observe_case(output, kind, Database, DurableLedger, Posting):
    output.mkdir(mode=0o700, exist_ok=False)
    path = output / "main.sqlite3"
    ledger = DurableLedger(Database(path), {"USD": 2})
    ledger.post("manual:1", [Posting("a", "USD", Decimal("-12.50")), Posting("b", "USD", Decimal("12.50"))])
    ledger.post("manual:2", [Posting("b", "USD", Decimal("-3.00")), Posting("c", "USD", Decimal("3.00"))])
    assert ledger.verify() == 2
    shadow = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, isolation_level=None)
    try:
        shadow.execute("PRAGMA foreign_keys=ON")
        shadow.execute("BEGIN")
        good = snapshot(shadow, "main")
        assert good["tables"]["ledger_balances"] == EXPECTED_BALANCES
        assert [row[4] for row in good["tables"]["ledger_events"]] == EXPECTED_EVENT_HASHES
        for name in TABLES:
            shadow.execute('CREATE TEMP TABLE "' + name + '" AS SELECT * FROM main."' + name + '"')
        good_temp = snapshot(shadow, "temp")
        assert good_temp["tables"] == good["tables"]
        shadow.commit()
        assert not shadow.in_transaction
        offline = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, isolation_level=None)
        try:
            offline.execute("PRAGMA foreign_keys=ON")
            offline.execute("BEGIN IMMEDIATE")
            if kind == "event_hash":
                trigger = next(row[3] for row in good["catalogue"] if row[1] == "ledger_events_seal_only")
                offline.execute("DROP TRIGGER main.ledger_events_seal_only")
                offline.execute("UPDATE main.ledger_events SET event_hash=? WHERE sequence=1", ("f" * 64,))
                offline.execute(trigger)
                expected_error = "journal event hash changed"
            elif kind == "balance":
                offline.execute("UPDATE main.ledger_balances SET units='951' WHERE account='b' AND asset='USD'")
                expected_error = "materialized balances differ from journal replay"
            else:
                raise AssertionError("unknown fixed case")
            offline.commit()
        finally:
            offline.close()
        bad_main = snapshot(shadow, "main")
        assert bad_main["catalogue"] == good["catalogue"]
        expected = json.loads(json.dumps(good["tables"]))
        if kind == "event_hash":
            expected["ledger_events"][0][4] = "f" * 64
        else:
            expected["ledger_balances"][1][2] = "951"
        assert bad_main["tables"] == expected
        direct = outcome(ledger.verify)
        assert direct == {"returned": None, "error_type": "LedgerError", "error_message": expected_error}
        assert snapshot(shadow, "main") == bad_main
        assert snapshot(shadow, "temp") == good_temp
        shadow.execute("PRAGMA query_only=ON")
        shadow.execute("BEGIN")
        db_list = [list(row) for row in shadow.execute("PRAGMA database_list")]
        assert Path(next(row[2] for row in db_list if row[1] == "main")).resolve() == path.resolve()
        before_main, before_temp = snapshot(shadow, "main"), snapshot(shadow, "temp")
        joined = outcome(lambda: ledger.verify(connection=shadow))
        transaction_remained_active = shadow.in_transaction
        after_main, after_temp = snapshot(shadow, "main"), snapshot(shadow, "temp")
        assert before_main == after_main == bad_main
        assert before_temp == after_temp == good_temp
        assert transaction_remained_active
        shadow.rollback()
        assert snapshot(shadow, "main") == bad_main
        reproduced = joined == {"returned": 2, "error_type": None, "error_message": None}
        report = {"kind": kind, "main_path": str(path), "good_main_before_corruption": good,
            "genuine_good_temp_copy": good_temp, "bad_main": bad_main, "direct_original_verify": direct,
            "raw_connection_database_list": db_list, "joined_original_verify": joined,
            "caller_transaction_remained_active": transaction_remained_active,
            "main_unchanged_across_verify": True, "temp_unchanged_across_verify": True,
            "reproduced": reproduced, "production_approved": False}
        (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
        return report
    finally:
        if shadow.in_transaction:
            shadow.rollback()
        shadow.close()


def worker(label, output):
    started, beginning = datetime.now(timezone.utc).isoformat(), monotonic()
    os.umask(0o077)
    os.sched_setaffinity(0, {4})
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    def expired(signum, frame):
        (output / "alarm.json").write_text('{"alarm_seconds":6}\n')
        os._exit(124)
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, 6)
    before = source_guard(label)
    sys.path.insert(0, str(SOURCES[label]["path"]))
    from uta import storage
    from uta.ledger import Posting
    assert Path(storage.__file__).resolve() == SOURCES[label]["path"] / "uta/storage.py"
    results = [observe_case(output / kind, kind, storage.Database, storage.DurableLedger, Posting)
               for kind in ("event_hash", "balance")]
    after = source_guard(label)
    signal.setitimer(signal.ITIMER_REAL, 0)
    report = {"source_label": label, "source_before": before, "source_after": after,
        "source_unchanged": before == after, "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(), "whole_seconds": monotonic() - beginning,
        "loaded_storage_file": storage.__file__, "runtime": {"python": sys.version,
            "sqlite": sqlite3.sqlite_version, "executable": sys.executable},
        "cases_complete": len(results), "reproduced_cases": [r["kind"] for r in results if r["reproduced"]],
        "production_approved": False}
    (output / "source-result.json").write_text(json.dumps(report, indent=2) + "\n")
    return 0 if report["source_unchanged"] else 2


def launch(output):
    beginning, started = monotonic(), datetime.now(timezone.utc).isoformat()
    os.umask(0o077)
    os.sched_setaffinity(0, {4})
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    records = []
    for label in ("baseline", "f01_candidate"):
        command = [sys.executable, str(Path(__file__).resolve()), "--worker", label, str(output / label)]
        with (output / (label + ".stdout.txt")).open("x") as out, (output / (label + ".stderr.txt")).open("x") as err:
            process = subprocess.Popen(command, cwd=ROOT, stdout=out, stderr=err)
            timed_out = False
            try:
                code = process.wait(timeout=min(6.5, max(.01, 14 - (monotonic() - beginning))))
            except subprocess.TimeoutExpired:
                timed_out = True
                process.kill()
                code = process.wait(timeout=.25)
        record = {"label": label, "command": command, "worker_pid": process.pid,
                  "exit_code": code, "timed_out": timed_out, "forced_cleanup": timed_out}
        records.append(record)
        if timed_out or code != 0:
            break
    results = []
    for record in records:
        result_path = output / record["label"] / "source-result.json"
        if result_path.exists():
            results.append(json.loads(result_path.read_bytes()))
    checkout = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    report = {"started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
        "whole_seconds": monotonic() - beginning, "whole_budget_met": monotonic() - beginning <= 15,
        "source_checkout": checkout,
        "driver_sha256": sha256(Path(__file__).read_bytes()).hexdigest(), "records": records,
        "observations_complete": len(results) == 2 and all(r["cases_complete"] == 2 and r["source_unchanged"] for r in results),
        "all_four_reproduced": len(results) == 2 and all(len(r["reproduced_cases"]) == 2 for r in results),
        "interpretation": "The original results are retained independently of reproduction. No fix or production acceptance is implemented.",
        "production_approved": False}
    (output / "launch.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["observations_complete"] and report["whole_budget_met"] else 2


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--run":
        raise SystemExit(launch(Path(sys.argv[2]).resolve()))
    if len(sys.argv) == 4 and sys.argv[1] == "--worker" and sys.argv[2] in SOURCES:
        raise SystemExit(worker(sys.argv[2], Path(sys.argv[3]).resolve()))
    raise SystemExit("explicit --run NEW_PRIVATE_OUTPUT required; no default SQL action")
