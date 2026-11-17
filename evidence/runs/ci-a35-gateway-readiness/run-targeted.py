"""One bounded owned test process; diagnostics tracing is call-through only."""
import argparse
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
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
NAMES = ["test_gateway_grouped.GroupedGatewayTests.test_full_original_id_flow_accepts_an_actual_running_unknown_reply",
         "test_readiness_sampling.ReadinessSamplingTests.test_delivered_ready_frames_cannot_override_future_or_stale_market"]


def inputs():
    files = [*sorted((ROOT / "uta").rglob("*.py")), ROOT / "uta/dashboard.html",
             ROOT / "tests/test_gateway_grouped.py", ROOT / "tests/test_readiness_sampling.py",
             ROOT / "tests/test_durable_faults.py", Path(__file__).resolve()]
    return {p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()).hexdigest() for p in files}


def worker(output, names):
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "tests"))
    from uta import durable_process
    original = durable_process.DurableProcessRouter.diagnostics
    observations = []

    def observed(router, *args, **kwargs):
        start = time.monotonic()
        report = original(router, *args, **kwargs)
        entry = {key: report.get(key) for key in ("reason", "state_observed", "workers_alive", "ready", "financial_ready")}
        entry.update(elapsed_seconds=time.monotonic() - start,
                     requested_timeout=kwargs.get("timeout", 1.0), clock_class=durable_process.datetime.__name__)
        entry["workers"] = [{key: row.get(key) for key in (
            "shard", "pid", "alive", "owner_pid", "generation", "lease_active", "owner_ready",
            "market_ready", "funding_registry_ready", "locally_active", "reason", "report")}
            for row in report["workers"]]
        observations.append(entry)
        print("diagnostic-observation " + json.dumps(entry, sort_keys=True), flush=True)
        return report

    with patch.object(durable_process.DurableProcessRouter, "diagnostics", observed):
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(names))
    record = {"tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
              "skipped": len(result.skipped), "passed": result.wasSuccessful(), "observations": observations}
    (output / "worker-result.json").write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
    return 0 if result.wasSuccessful() else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--tests", nargs="+", default=NAMES)
    args = parser.parse_args()
    if args.worker:
        return worker(args.output, args.tests)
    output = args.output.resolve()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    before = inputs()
    command = [sys.executable, "-B", "-W", "error::ResourceWarning", str(Path(__file__).resolve()),
               "--worker", "--output", str(output), "--tests", *args.tests]
    started_wall, started = time.time_ns(), time.monotonic()
    process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, close_fds=True, start_new_session=True)
    timed_out = False
    try:
        raw, _ = process.communicate(timeout=28)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(process.pid, signal.SIGTERM)  # Only the newly created owned group.
        try:
            raw, _ = process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            raw, _ = process.communicate()
    (output / "unittest.txt").write_bytes(raw)
    result_path = output / "worker-result.json"
    result = json.loads(result_path.read_text()) if result_path.exists() else {}
    manifest = {"frozen_base": "a35fd56fc98126b3e5cced8a459bd04ca580e537",
        "actual_source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "command_argv": command, "python": sys.version, "sqlite": sqlite3.sqlite_version,
        "cpu_affinity": sorted(os.sched_getaffinity(0)), "started_wall_ns": started_wall,
        "elapsed_seconds": time.monotonic() - started, "timed_out": timed_out, "worker_exit_code": process.returncode,
        "input_sha256_before": before, "input_sha256_after": inputs(), "source_inputs_unchanged": before == inputs(),
        "log_sha256": sha256(raw).hexdigest(), "tests_run": result.get("tests_run"),
        "failures": result.get("failures"), "errors": result.get("errors"), "passed": result.get("passed", False),
        "original_ci_no_go_preserved": True, "full_release_qualified": False, "production_approved": False}
    (output / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    print(json.dumps({key: manifest[key] for key in ("tests_run", "failures", "errors", "passed", "elapsed_seconds", "timed_out")}))
    return 0 if manifest["passed"] and not timed_out else 1


if __name__ == "__main__":
    raise SystemExit(main())
