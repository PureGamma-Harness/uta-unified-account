"""One root-authorized synthetic catalogue observation; no default SQL action."""
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
BASE = "4ad58b2169b02f8982a1cbef8722b79d705d60c8"
TABLES = ("ledger_schema", "ledger_assets", "ledger_events", "ledger_postings", "ledger_balances")


def canonical(value):
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def literal_reference():
    previous = "0" * 64
    events = []
    for sequence, identity, postings in (
        (1, "manual:1", [["a", "USD", -1250], ["b", "USD", 1250]]),
        (2, "manual:2", [["b", "USD", -300], ["c", "USD", 300]]),
    ):
        fingerprint = sha256(canonical(postings).encode()).hexdigest()
        event_hash = sha256(canonical([sequence, identity, previous, fingerprint]).encode()).hexdigest()
        events.append([sequence, identity, fingerprint, previous, event_hash, 1])
        previous = event_hash
    return {
        "events": events,
        "postings": [[1, 0, "a", "USD", "-1250"], [1, 1, "b", "USD", "1250"],
                     [2, 0, "b", "USD", "-300"], [2, 1, "c", "USD", "300"]],
        "balances": [["a", "USD", "-1250"], ["b", "USD", "950"], ["c", "USD", "300"]],
    }


def snapshot(path):
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, isolation_level=None)
    try:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        result = {
            "catalogue": [list(r) for r in connection.execute(
                "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name")],
            "tables": {table: [list(r) for r in connection.execute(
                'SELECT * FROM "' + table + '" ORDER BY 1,2')] for table in TABLES},
            "postings_columns": [list(r) for r in connection.execute("PRAGMA table_xinfo(ledger_postings)")],
            "postings_foreign_keys": [list(r) for r in connection.execute("PRAGMA foreign_key_list(ledger_postings)")],
            "integrity_check": [list(r) for r in connection.execute("PRAGMA integrity_check")],
            "foreign_key_check": [list(r) for r in connection.execute("PRAGMA foreign_key_check")],
        }
        connection.rollback()
        return result
    finally:
        connection.close()


def original_outcome(call):
    try:
        return {"returned": call(), "error_type": None, "error_message": None}
    except Exception as error:
        return {"returned": None, "error_type": type(error).__name__, "error_message": str(error)}


def main(output):
    started, beginning = datetime.now(timezone.utc).isoformat(), monotonic()
    os.umask(0o077)
    os.sched_setaffinity(0, {4})
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    assert output.stat().st_mode & 0o777 == 0o700
    reference = literal_reference()
    source_paths = [p for p in subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", BASE, "uta"], cwd=ROOT, text=True).splitlines()]
    source = {}
    for name in source_paths:
        expected = subprocess.check_output(["git", "show", BASE + ":" + name], cwd=ROOT)
        actual = (ROOT / name).read_bytes()
        assert actual == expected, name
        source[name] = sha256(actual).hexdigest()
    assert len(source) == 52
    (output / "source-before.json").write_text(json.dumps(source, indent=2) + "\n")
    report = {"source_base": BASE, "source_commit": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "started_at": started, "runtime": {"python": sys.version, "executable": sys.executable,
            "sqlite": sqlite3.sqlite_version}, "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "reference": reference, "production_approved": False, "reproduced": False}

    def expired(signum, frame):
        raise TimeoutError("predeclared fourteen-second observation alarm")
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, max(.01, 14 - (monotonic() - beginning)))
    try:
        sys.path.insert(0, str(ROOT))
        from uta.ledger import Posting
        from uta.storage import Database, DurableLedger
        path = output / "original-synthetic.sqlite3"
        ledger = DurableLedger(Database(path), {"USD": 2})
        ledger.post("manual:1", [Posting("a", "USD", Decimal("-12.50")), Posting("b", "USD", Decimal("12.50"))])
        ledger.post("manual:2", [Posting("b", "USD", Decimal("-3.00")), Posting("c", "USD", Decimal("3.00"))])
        report["baseline_verifier"] = original_outcome(ledger.verify)
        before = snapshot(path)
        report["before"] = before
        assert report["baseline_verifier"] == {"returned": 2, "error_type": None, "error_message": None}
        assert before["tables"]["ledger_events"] == reference["events"]
        assert before["tables"]["ledger_postings"] == reference["postings"]
        assert before["tables"]["ledger_balances"] == reference["balances"]
        assert len(before["postings_foreign_keys"]) == 2
        triggers = [r[3] for r in before["catalogue"] if r[0] == "trigger" and r[2] == "ledger_postings"]
        assert len(triggers) == 3
        connection = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, isolation_level=None)
        try:
            connection.execute("PRAGMA foreign_keys=OFF")
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("""CREATE TABLE rebuilt_postings (
                sequence INTEGER NOT NULL,
                ordinal INTEGER NOT NULL CHECK (ordinal >= 0), account TEXT NOT NULL,
                asset TEXT NOT NULL REFERENCES ledger_assets(asset), units TEXT NOT NULL,
                PRIMARY KEY (sequence, ordinal))""")
            connection.execute("INSERT INTO rebuilt_postings SELECT * FROM ledger_postings")
            connection.execute("DROP TABLE ledger_postings")
            connection.execute("ALTER TABLE rebuilt_postings RENAME TO ledger_postings")
            for sql in triggers:
                connection.execute(sql)
            connection.execute("INSERT INTO ledger_postings VALUES (99,0,'orphan','USD','1')")
            connection.commit()
        finally:
            connection.close()
        reconstructed = snapshot(path)
        report["reconstructed"] = reconstructed
        assert reconstructed["integrity_check"] == [["ok"]]
        assert reconstructed["foreign_key_check"] == []
        assert reconstructed["postings_columns"] == before["postings_columns"]
        assert len(reconstructed["postings_foreign_keys"]) == 1
        assert reconstructed["postings_foreign_keys"][0][2:5] == ["ledger_assets", "asset", "asset"]
        for table in TABLES:
            expected = reference["postings"] + [[99, 0, "orphan", "USD", "1"]] if table == "ledger_postings" else before["tables"][table]
            assert reconstructed["tables"][table] == expected, table
        def kept_catalogue(value):
            return [r for r in value["catalogue"] if r[1] != "ledger_postings"]
        assert kept_catalogue(reconstructed) == kept_catalogue(before)
        reopened = None
        try:
            reopened = DurableLedger(Database(path), {"USD": 2})
            report["reopened_constructor"] = {"returned": "DurableLedger", "error_type": None, "error_message": None}
        except Exception as error:
            report["reopened_constructor"] = {"returned": None, "error_type": type(error).__name__, "error_message": str(error)}
        report["reopened_default_verifier"] = None if reopened is None else original_outcome(reopened.verify)
        report["after_original_reopen_verify"] = snapshot(path)
        assert report["after_original_reopen_verify"] == reconstructed
        report["reproduced"] = (reopened is not None and report["reopened_default_verifier"] ==
            {"returned": 2, "error_type": None, "error_message": None})
        report["interpretation"] = ("REPRODUCED: original default verifier accepted two declared events while an orphan posting exists and the event foreign key is absent"
            if report["reproduced"] else "NO_REPRO or original refusal; retain the original observation without relabeling")
    except BaseException as error:
        report["observation_error"] = {"type": type(error).__name__, "message": str(error)}
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        actual_after = {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in source}
        report["source_unchanged"] = source == actual_after
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["whole_seconds"] = monotonic() - beginning
        report["whole_budget_met"] = report["whole_seconds"] <= 15
        (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({k: report[k] for k in ("reproduced", "source_unchanged", "whole_seconds", "whole_budget_met")}, indent=2))
    return 0 if report["reproduced"] and report["source_unchanged"] and report["whole_budget_met"] else 2


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "--run":
        raise SystemExit("explicit --run NEW_PRIVATE_OUTPUT required; no default SQL action")
    raise SystemExit(main(Path(sys.argv[2]).resolve()))
