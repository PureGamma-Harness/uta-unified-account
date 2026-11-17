"""One authorized independent component; imports no product code before --run."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from time import monotonic

ROOT = Path(__file__).resolve().parents[3]
EXPECTED_STORAGE = "ddb6ed979bb8e88aefb2a49084829e9bdce3649fb10d6bf93bb0c28298f24a79"
EXPECTED_TESTS = 18


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def source_map():
    paths = subprocess.check_output(["git", "ls-files", "uta"], cwd=ROOT, text=True).splitlines()
    assert len(paths) == 52
    return {path: sha256((ROOT / path).read_bytes()).hexdigest() for path in paths}


def worker(output):
    import sqlite3
    import unittest
    start = monotonic()
    result = None
    def expired(signum, frame):
        write(output / "child-alarm.json", {"seconds": 13, "owned_component_only": True})
        os._exit(124)
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, 13)
    os.environ["UTA_LEDGER_ACCEPTANCE_CASES"] = str(output / "cases")
    sys.path.insert(0, str(ROOT))
    report = {"python": sys.version, "executable": sys.executable, "sqlite": sqlite3.sqlite_version,
              "affinity": sorted(os.sched_getaffinity(0)), "expected_tests": EXPECTED_TESTS,
              "production_approved": False, "independent_acceptance": "ROOT_REVIEW_REQUIRED"}
    try:
        suite = unittest.defaultTestLoader.loadTestsFromName("tests.test_ledger_catalogue_acceptance")
        with (output / "unittest.txt").open("x") as stream:
            result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
        report.update(tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                      skips=len(result.skipped), passed=result.wasSuccessful())
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        report["seconds"] = monotonic() - start
        report["private_db_sha256"] = {str(path.relative_to(output)): sha256(path.read_bytes()).hexdigest()
            for path in sorted((output / "cases").rglob("*.sqlite3"))}
        write(output / "child-result.json", report)
    return 0 if result is not None and result.wasSuccessful() and result.testsRun == EXPECTED_TESTS and not result.skipped else 2


def run(output):
    start, actual_start = monotonic(), datetime.now(timezone.utc).isoformat()
    os.umask(0o077)
    os.sched_setaffinity(0, {4})
    assert sys.version_info[:2] == (3, 12)
    assert output.is_absolute()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    assert output.stat().st_mode & 0o777 == 0o700
    assert subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True) == ""
    before = source_map()
    assert before["uta/storage.py"] == EXPECTED_STORAGE
    write(output / "source-before.json", before)
    write(output / "BEGIN.json", {"actual_start": actual_start, "affinity": sorted(os.sched_getaffinity(0)),
          "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
          "scope": "18 independent fresh-scratch synthetic tests, one component only", "seconds_budget": 15})
    timed_out = False
    with (output / "stdout.txt").open("x") as stdout, (output / "stderr.txt").open("x") as stderr:
        child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--worker", str(output)],
                                 cwd=ROOT, stdout=stdout, stderr=stderr, start_new_session=True, close_fds=True)
        child_pid = child.pid
        try:
            child.wait(timeout=max(.01, 14 - (monotonic() - start)))
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(child.pid, signal.SIGKILL)  # Only this newly created owned child group.
            child.wait(timeout=1)
    after = source_map()
    write(output / "source-after.json", after)
    whole = monotonic() - start
    report = {"actual_start": actual_start, "actual_end": datetime.now(timezone.utc).isoformat(),
              "whole_seconds": whole, "budget_met": whole <= 15, "outer_watchdog": timed_out,
              "child_pid_pgid_sid": child_pid, "child_reaped": child.returncode is not None,
              "child_exit": child.returncode, "source52_unchanged": before == after,
              "production_approved": False, "independent_acceptance": "ROOT_REVIEW_REQUIRED"}
    write(output / "END.json", report)
    print(json.dumps(report, indent=2))
    return 0 if child.returncode == 0 and not timed_out and before == after and whole <= 15 else 2


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("--run", "--worker"):
        raise SystemExit("explicit --run NEW_PRIVATE_OUTPUT required; default performs no SQL")
    raise SystemExit((run if sys.argv[1] == "--run" else worker)(Path(sys.argv[2]).resolve()))
