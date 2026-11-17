"""Exact-source qualification for engineering long runs, never fund activation.

The local OS owner and the validation runner are trusted. These checks detect
missing, contradictory or stale evidence; they are not a report-signing service.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FOLDERS = ("uta", "tests", "formal", "tools", "benchmarks", "scripts")
SOURCE_FILES = ("pyproject.toml", "MANIFEST.in", "LICENSE")
COUNTS = ("failures", "errors", "skipped", "expected_failures", "unexpected_successes")
FLAGS = ("passed", "unittest_passed", "source_unchanged", "tracked_source_clean_before", "tracked_source_clean_after")
ARTIFACTS = ("summary.json", "worker-result.json", "unittest.txt")


def _fail(message):
    raise RuntimeError("managed release validation required: " + message)


def source_manifest(root):
    """Match the complete run_validation.py input set, including binary fixtures."""
    root = Path(root)
    paths = {path for folder in SOURCE_FOLDERS for path in (root / folder).rglob("*.py")}
    paths.update(path for path in (root / "tests/fixtures").rglob("*") if path.is_file())
    paths.update(root / name for name in SOURCE_FILES if (root / name).exists())
    return {path.relative_to(root).as_posix(): sha256(path.read_bytes()).hexdigest() for path in sorted(paths)}


def _git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def _clean_commit(root):
    if _git(root, "status", "--porcelain", "--untracked-files=all"):
        _fail("the entire source checkout must be clean, including documentation and untracked files")
    return _git(root, "rev-parse", "HEAD")


def _json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                _fail("duplicate JSON key")
            result[key] = value
        return result
    def invalid(value):
        _fail("nonfinite JSON value")
    result = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    if not isinstance(result, dict):
        _fail("report objects must be dictionaries")
    return result


@dataclass(frozen=True)
class Qualification:
    evidence: dict
    artifacts: dict

    def record(self, destination):
        destination = Path(destination)
        destination.mkdir(mode=0o700, parents=True, exist_ok=False)
        for name, raw in self.artifacts.items():
            with (destination / name).open("xb") as output:
                output.write(raw)
                output.flush()
                os.fsync(output.fileno())
        descriptor = os.open(destination, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        return self.evidence


def qualify(report_path, *, root=ROOT):
    """Read-only validation; call before creating a job directory or lock file."""
    try:
        root = Path(root).resolve()
        commit = _clean_commit(root)
        path = Path(report_path)
        if path.name != "summary.json":
            _fail("supply the complete runner's summary.json with its original sidecars")
        raw = {name: (path.parent / name).read_bytes() for name in ARTIFACTS}
        report, worker = _json(raw["summary.json"]), _json(raw["worker-result.json"])
        if report.get("code_commit") != commit:
            _fail("report code_commit differs from the exact current Git HEAD")
        if any(report.get(key) is not True for key in FLAGS) or worker.get("unittest_passed") is not True:
            _fail("full validation success and unchanged/clean source are required")
        if report.get("production_approved") is not False:
            _fail("engineering validation cannot grant production approval")
        if type(report.get("tests_run")) is not int or report["tests_run"] <= 0:
            _fail("full validation must execute tests")
        for key in ("tests_run", *COUNTS, "unittest_passed"):
            if worker.get(key) != report.get(key) or type(worker.get(key)) is not type(report.get(key)):
                _fail("worker result and summary disagree")
        for key in (*COUNTS, "worker_exit_code"):
            if type(report.get(key)) is not int or report[key] != 0:
                _fail("errors, failures, skips, expected/unexpected outcomes and worker exit must all be integer zero")
        if report.get("python") != sys.version or report.get("sqlite") != sqlite3.sqlite_version:
            _fail("the validation Python and SQLite versions must match this execution environment")
        argv = report.get("command_argv")
        if (not isinstance(argv, list) or len(argv) != 4 or not all(isinstance(x, str) for x in argv)
                or Path(argv[1]).parts[-2:] != ("tools", "run_validation.py") or argv[2] != "--output"):
            _fail("report is not the complete tools/run_validation.py command")
        if report.get("test_log_sha256") != sha256(raw["unittest.txt"]).hexdigest():
            _fail("raw unittest log checksum mismatch")
        log = raw["unittest.txt"].decode("utf-8")
        if not re.search(r"^Ran " + str(report["tests_run"]) + r" tests? in .+\n\nOK\s*\Z", log, re.MULTILINE):
            _fail("raw log does not end in the reported successful unittest run")
        manifest = source_manifest(root)
        required = {"tools/run_validation.py", "benchmarks/run_managed_soak.py", "benchmarks/managed_qualification.py",
                    "benchmarks/run_soak.py", "benchmarks/run_benchmark.py"}
        if not required <= manifest.keys() or not any(name.startswith("uta/") for name in manifest):
            _fail("the complete runtime and long-run dependency sources are required")
        if report.get("source_sha256") != manifest or report.get("source_sha256_after") != manifest:
            _fail("complete source manifests before/after/current must match exactly")
        tracked = set(_git(root, "ls-files", "-z").split("\0"))
        if not manifest.keys() <= tracked:
            _fail("every source and fixture must belong to the recorded commit")
        if _clean_commit(root) != commit or source_manifest(root) != manifest:
            _fail("source changed during qualification")
        return Qualification({"code_commit": commit, "tests_run": report["tests_run"],
            "python": report["python"], "sqlite": report["sqlite"],
            "artifact_sha256": {name: sha256(value).hexdigest() for name, value in raw.items()},
            "engineering_test_qualified": True, "production_approved": False,
            "continuous_6h_stability_passed": False, "continuous_24h_stability_passed": False}, raw)
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as error:
        _fail("missing or invalid evidence/source: " + str(error))
