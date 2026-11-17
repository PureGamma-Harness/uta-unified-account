"""Explicit one-shot author regression batch; no SQL without --run."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
from time import monotonic
import unittest

ROOT = Path(__file__).resolve().parents[3]
STORAGE_SHA256 = "ddb6ed979bb8e88aefb2a49084829e9bdce3649fb10d6bf93bb0c28298f24a79"


def main(output):
    beginning, started = monotonic(), datetime.now(timezone.utc).isoformat()
    os.umask(0o077)
    os.sched_setaffinity(0, {4})
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    assert output.stat().st_mode & 0o777 == 0o700
    assert sha256((ROOT / "uta/storage.py").read_bytes()).hexdigest() == STORAGE_SHA256
    assert subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True) == ""
    paths = subprocess.check_output(["git", "ls-files", "uta"], cwd=ROOT, text=True).splitlines()
    source = {p: sha256((ROOT / p).read_bytes()).hexdigest() for p in paths}
    assert len(source) == 52
    (output / "source-before.json").write_text(json.dumps(source, indent=2) + "\n")
    report = {"source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "started_at": started, "python": sys.version, "sqlite": sqlite3.sqlite_version,
        "executable": sys.executable, "source_sha256": source, "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "expected_tests": 29, "new_catalogue_controls": 16, "original_storage_regressions": 13,
        "independent_acceptance": "PENDING_OTHER_GROUP", "production_approved": False}
    os.environ["UTA_LEDGER_CATALOGUE_CASES"] = str(output / "cases")
    sys.path.insert(0, str(ROOT))
    def expired(signum, frame):
        (output / "alarm.json").write_text(json.dumps({"alarm_seconds": 14, "scope": "new component process only"}) + "\n")
        os._exit(124)
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, max(.01, 14 - (monotonic() - beginning)))
    try:
        suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromName(
            "tests.test_ledger_postings_catalogue"), unittest.defaultTestLoader.loadTestsFromName(
            "tests.test_storage.StorageTests")])
        with (output / "unittest.txt").open("x") as log:
            result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
        report.update(tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                      skipped=len(result.skipped), tests_passed=result.wasSuccessful())
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        actual = {p: sha256((ROOT / p).read_bytes()).hexdigest() for p in source}
        report.update(source_unchanged=source == actual, finished_at=datetime.now(timezone.utc).isoformat(),
                      whole_seconds=monotonic() - beginning, whole_budget_met=monotonic() - beginning <= 15)
        (output / "source-after.json").write_text(json.dumps(actual, indent=2) + "\n")
        (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({k: report.get(k) for k in ("tests_run", "failures", "errors", "skipped",
            "tests_passed", "source_unchanged", "whole_seconds", "whole_budget_met")}, indent=2))
    return 0 if (report.get("tests_passed") and report.get("tests_run") == 29 and report.get("skipped") == 0
                 and report["source_unchanged"] and report["whole_budget_met"]) else 2


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "--run":
        raise SystemExit("explicit --run NEW_PRIVATE_OUTPUT required; no default SQL action")
    raise SystemExit(main(Path(sys.argv[2]).resolve()))
