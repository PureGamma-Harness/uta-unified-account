"""Independent bounded small-fixture review; no service or qualification run."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
TARGETS = ["tests.test_owned_startup_reference", "tests.test_startup_write_contention"]
RUNTIMES = {
    "python310": "/tmp/uta-python310/cpython-3.10.22-linux-x86_64-gnu/bin/python3.10",
    "python312": "/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python",
    "python313": "/usr/bin/python3.13",
}


def utc():
    return datetime.now(timezone.utc).isoformat()


def sources():
    paths = {path for folder in ("uta", "tests", "formal", "tools", "benchmarks", "scripts")
             for path in (ROOT / folder).rglob("*.py")}
    paths.update(path for path in (ROOT / "tests" / "fixtures").rglob("*") if path.is_file())
    paths.update(ROOT / name for name in ("pyproject.toml", "MANIFEST.in", "LICENSE")
                 if (ROOT / name).exists())
    return {path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest()
            for path in sorted(paths)}


def worker(result_path):
    sys.path.insert(0, str(ROOT))
    suite = unittest.defaultTestLoader.loadTestsFromNames(TARGETS)
    count = suite.countTestCases()
    started = utc()
    beginning = time.monotonic()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    record = dict(python=sys.version, executable=sys.executable, sqlite=sqlite3.sqlite_version,
                  affinity=sorted(os.sched_getaffinity(0)), planned_cases=count,
                  started_at=started, finished_at=utc(), duration_seconds=time.monotonic()-beginning,
                  tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                  skipped=len(result.skipped), expected_failures=len(result.expectedFailures),
                  unexpected_successes=len(result.unexpectedSuccesses),
                  unittest_passed=result.wasSuccessful())
    result_path.write_text(json.dumps(record, indent=2) + "\n")
    return 0 if result.wasSuccessful() and count == 17 else 1


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        return worker(Path(sys.argv[2]))
    before = sources()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    started, beginning = utc(), time.monotonic()
    deadline = beginning + 55  # Five seconds below the parent-authorized total test ceiling.
    runs = []
    for name, executable in RUNTIMES.items():
        command = ["taskset", "-c", "2", executable, "-B", "-W", "error::ResourceWarning",
                   str(Path(__file__).resolve()), "--worker", str(OUT / (name + "-result.json"))]
        run = dict(name=name, command_argv=command, started_at=utc(), timed_out=False)
        with (OUT / (name + "-unittest.txt")).open("x") as log:
            child = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL,
                                     stdout=log, stderr=subprocess.STDOUT,
                                     close_fds=True, start_new_session=True)
            try:
                run["exit_code"] = child.wait(timeout=max(.001, deadline-time.monotonic()))
            except subprocess.TimeoutExpired:
                run["timed_out"] = True
                os.killpg(child.pid, signal.SIGKILL)
                run["exit_code"] = child.wait()
        run["finished_at"] = utc()
        runs.append(run)
        print(json.dumps(run), flush=True)
        if run["timed_out"] or run["exit_code"] != 0:
            break  # Report first genuine failure; never loosen code or timing gates.
    after = sources()
    report = dict(code_commit=head, targets=TARGETS, cpu=2, started_at=started, finished_at=utc(),
                  duration_seconds=time.monotonic()-beginning, hard_test_budget_seconds=55,
                  parent_total_ceiling_seconds=60, runs=runs,
                  source_sha256=before, source_sha256_after=after, source_unchanged=before == after,
                  runner_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
                  full_qualification=False, service_started=False, production_approved=False)
    report["focused_passed"] = (len(runs) == 3 and before == after
                                and all(run["exit_code"] == 0 and not run["timed_out"] for run in runs))
    (OUT / "focused-summary.json").write_text(json.dumps(report, indent=2) + "\n")
    return 0 if report["focused_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
