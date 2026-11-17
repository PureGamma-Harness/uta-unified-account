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
    parser.add_argument("--_worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args._worker:
        # Parent redirects the actual OS descriptors. Spawned processes and
        # native-library stderr therefore belong to the same raw log as tests.
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
        result = unittest.TextTestRunner(stream=sys.stderr, verbosity=2).run(suite)
        (args.output / "worker-result.json").write_text(json.dumps({
            "tests_run": result.testsRun, "failures": len(result.failures),
            "errors": len(result.errors), "skipped": len(result.skipped),
            "expected_failures": len(result.expectedFailures),
            "unexpected_successes": len(result.unexpectedSuccesses),
            "unittest_passed": result.wasSuccessful()}, indent=2) + "\n")
        return 0 if result.wasSuccessful() else 1
    args.output = args.output.expanduser().absolute()
    args.output.mkdir(parents=True, exist_ok=False)
    started = datetime.now(timezone.utc).isoformat()
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    def sources():
        paths = {path for folder in ("uta", "tests", "formal", "tools", "benchmarks", "scripts")
                 for path in (ROOT / folder).rglob("*.py")}
        paths.update(path for path in (ROOT / "tests" / "fixtures").rglob("*") if path.is_file())
        paths.update(ROOT / name for name in ("pyproject.toml", "MANIFEST.in", "LICENSE") if (ROOT / name).exists())
        return {path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest()
                for path in sorted(paths)}
    def clean(manifest):
        paths = ("uta", "tests", "formal", "tools", "benchmarks", "scripts", "pyproject.toml", "MANIFEST.in", "LICENSE")
        tracked = set(subprocess.check_output(["git", "ls-files", "-z", "--", *paths], cwd=ROOT).decode().split("\0"))
        return set(manifest) <= tracked and subprocess.run(
            ["git", "diff", "--quiet", "HEAD", "--", *paths], cwd=ROOT).returncode == 0
    before = sources()
    clean_before = clean(before)
    beginning = time.perf_counter()
    with (args.output / "unittest.txt").open("x", encoding="utf-8") as log:
        completed = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--_worker",
                                    "--output", str(args.output)], cwd=ROOT,
                                   stdout=log, stderr=subprocess.STDOUT)
    elapsed = time.perf_counter() - beginning
    after = sources()
    clean_after = clean(after)
    result_path = args.output / "worker-result.json"
    result = json.loads(result_path.read_text()) if result_path.exists() else {
        "tests_run": None, "failures": None, "errors": None, "skipped": None,
        "expected_failures": None, "unexpected_successes": None, "unittest_passed": False}
    unchanged = before == after
    report = {"code_commit": sha, "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
              "command_argv": [sys.executable, str(Path(__file__).resolve()), "--output", str(args.output)],
              "python": sys.version, "platform": platform.platform(), "sqlite": sqlite3.sqlite_version,
              **result, "duration_seconds": elapsed, "worker_exit_code": completed.returncode,
              "passed": result["unittest_passed"] and completed.returncode == 0 and unchanged and clean_before and clean_after,
              "source_unchanged": unchanged, "tracked_source_clean_before": clean_before,
              "tracked_source_clean_after": clean_after,
              "source_sha256": before, "source_sha256_after": after,
              "test_log_sha256": sha256((args.output / "unittest.txt").read_bytes()).hexdigest(),
              "production_approved": False}
    (args.output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if not key.startswith("source_sha256")}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
