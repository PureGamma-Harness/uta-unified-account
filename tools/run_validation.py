"""Record a reproducible full unittest run without third-party test dependencies."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="new result directory")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    started = datetime.now(timezone.utc).isoformat()
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    sources = {str(path.relative_to(ROOT)): sha256(path.read_bytes()).hexdigest()
               for folder in ("uta", "tests", "formal", "tools")
               for path in sorted((ROOT / folder).glob("*.py"))}
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    beginning = time.perf_counter()
    with (args.output / "unittest.txt").open("x", encoding="utf-8") as log:
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    elapsed = time.perf_counter() - beginning
    report = {"code_commit": sha, "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
              "command": "python tools/run_validation.py --output " + str(args.output),
              "python": sys.version, "platform": platform.platform(), "sqlite": sqlite3.sqlite_version,
              "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
              "skipped": len(result.skipped), "expected_failures": len(result.expectedFailures),
              "unexpected_successes": len(result.unexpectedSuccesses), "duration_seconds": elapsed,
              "passed": result.wasSuccessful(), "source_sha256": sources,
              "test_log_sha256": sha256((args.output / "unittest.txt").read_bytes()).hexdigest(),
              "production_approved": False}
    (args.output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "source_sha256"}, indent=2))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
