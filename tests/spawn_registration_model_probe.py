"""Same-process source identity and strictly model-only regression evidence."""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from tests.stopped_gate_recovery_probe import source_proof
    from tests.test_spawn_registration_recovery import SpawnRegistrationUnitTests
    from uta import durable_process as runtime
    proof = source_proof()
    runtime_path = Path(runtime.__file__).resolve()
    if runtime_path != ROOT / "uta/durable_process.py":
        raise RuntimeError("model imported an unexpected runtime")
    if proof["test_sha256"] != "c0024c905b077a310178cb7d38fffa5a85ae3fe5e28bb9d361e7c21524801080":
        raise RuntimeError("model test bytes differ from reviewed candidate")
    print(json.dumps({"phase": "same_process_pre_test_identity", "pid": os.getpid(),
        "imported_runtime_path": str(runtime_path), "source": proof,
        "probe_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "sql_worker_start_signals_forbidden": True}), flush=True)
    with patch.object(sqlite3, "connect", side_effect=AssertionError("model attempted SQL")), \
            patch.object(runtime.multiprocessing.process.BaseProcess, "start",
                         side_effect=AssertionError("model attempted worker start")), \
            patch.object(os, "kill", side_effect=AssertionError("model attempted signal")):
        result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(SpawnRegistrationUnitTests))
    print(json.dumps({"phase": "same_process_test_result", "pid": os.getpid(),
        "tests_run": result.testsRun, "failures": len(result.failures),
        "errors": len(result.errors), "passed": result.wasSuccessful(),
        "native_executed": False}), flush=True)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
