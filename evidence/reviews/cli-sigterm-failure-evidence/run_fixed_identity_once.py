"""One fake-only regression batch; no real Popen/SQL/worker/signal operation."""
from contextlib import redirect_stdout
from hashlib import sha256
import importlib.util
import io
import json
import os
from pathlib import Path
import runpy
import sqlite3
import subprocess
import sys
from threading import Thread
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
EXPECTED_HELPER = "6baec73b84ac4f73521c362e1d8fc7c5ff63d09c5aa4c869e1e8e5ae2b831f1d"


def main():
    started = time.monotonic_ns()
    assert sorted(os.sched_getaffinity(0)) == [1]
    source = ROOT / "tests/cli_sigterm_failure_evidence.py"
    assert sha256(source.read_bytes()).hexdigest() == EXPECTED_HELPER
    adapted = Path(__file__).with_name("once_fake_boundaries_adapted.py")
    original_output = io.StringIO()
    with patch.object(subprocess, "Popen", side_effect=AssertionError("pure attempted Popen")), \
            patch.object(sqlite3, "connect", side_effect=AssertionError("pure attempted SQL")), \
            patch.object(os, "kill", side_effect=AssertionError("pure attempted signal")), \
            patch.object(Thread, "start", side_effect=AssertionError("pure attempted thread")):
        with redirect_stdout(original_output):
            try:
                runpy.run_path(str(adapted), run_name="__adapted_original_eight__")
            except SystemExit as result:
                eight_exit = result.code
        eight = json.loads(original_output.getvalue())
        assert len(eight["cases"]) == 8
        specification = importlib.util.spec_from_file_location("cli_identity_fixed_pure", ROOT / "tests/test_cli_sigterm_failure_evidence.py")
        model = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(model)
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(model.CliIdentityBoundaryPureTests)
        suite.addTest(model.CliFailureEvidencePureTests("test_original_business_case_is_preserved_except_documented_observation"))
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    passed = eight_exit == 0 and all(row["status"] == "PASS" for row in eight["cases"]) and result.wasSuccessful()
    print(json.dumps({"actual_source_commit_from_invoker": sys.argv[1],
        "actual_helper_sha256": EXPECTED_HELPER, "in_process_cpu_ids": sorted(os.sched_getaffinity(0)),
        "adapted_original_eight_script_sha256": sha256(adapted.read_bytes()).hexdigest(),
        "historical_candidate_field_in_original_script_is_not_actual_new_source": True,
        "adapted_original_eight_exit": eight_exit, "adapted_original_eight": eight,
        "additional_tests_run": result.testsRun, "additional_failures": len(result.failures),
        "additional_errors": len(result.errors), "all_passed": passed,
        "elapsed_ns": time.monotonic_ns() - started,
        "real_Popen_SQL_CLI_workers_signals_H1AuthDB_childbootstrap": False}, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
