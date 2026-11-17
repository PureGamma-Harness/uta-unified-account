"""No managed services: tiny PIPE processes and pure short-gate fixtures only."""
import copy
from contextlib import redirect_stdout
from hashlib import sha256
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import managed_observer_smoke as smoke


class PipeAndShortGateTests(unittest.TestCase):
    def test_real_pipe_capture_drops_unknown_stdout_and_never_copies_stderr(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = "import json,sys; print(json.dumps({'synthetic':True,'status':'completed','secret_b64':'synthetic-hidden'})); sys.stderr.write('synthetic-stderr-hidden')"
            result = smoke.captured([sys.executable, "-B", "-c", script], cwd=root,
                                    launch=root / "launch.json")
            self.assertEqual(result["exit_code"], 0)
            self.assertEqual(result["response"], {"synthetic": True, "status": "completed"})
            raw = smoke.ro.canonical(result)
            self.assertNotIn("synthetic-hidden", raw)
            self.assertNotIn("synthetic-stderr-hidden", raw)
            self.assertEqual(result["stderr_sha256"], sha256(b"synthetic-stderr-hidden").hexdigest())
            launch = smoke.ro.load_json(root / "launch.json")
            self.assertTrue(launch["driver_birth"].isdecimal())
            self.assertGreater(launch["launched_wall_ns"], 0)
            self.assertEqual(launch["driver_pid"] == 4471 or launch["driver_pid"] == 8784, False)

    def test_default_prepare_does_not_create_job_or_launch_child(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, report = root / "source", root / "summary.json"
            source.mkdir()
            report.write_text("{}")
            identity = {"tests_run": 1110, "command_argv": ["exact-test-python"]}
            stdout = io.StringIO()
            with patch.object(smoke, "identity_report", return_value=identity), \
                 patch.object(smoke, "captured", side_effect=AssertionError("must not launch")), redirect_stdout(stdout):
                code = smoke.main(["--source", str(source), "--report", str(report),
                                   "--job", str(root / "job"), "--output", str(root / "observer")])
            self.assertEqual(code, 0)
            value = json.loads(stdout.getvalue())
            self.assertTrue(value["prepared_only"])
            self.assertFalse(value["service_started"])
            self.assertFalse(value["execution_authorized"])
            self.assertFalse((root / "job").exists())
            self.assertFalse((root / "observer").exists())

    def test_short_gate_never_treats_unknown_or_failed_final_as_smoke_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "job.json").write_text(json.dumps({"configuration": {"duration": 60, "rate": .25}}))
            value = {"planned_rounds": 15, "completed_rounds": 15, "active_rounds": [],
                "active_elapsed_seconds": 60, "logical_point": "stable_boundary", "final_evidence_eligible": False,
                "final_reconciliation": {"errors": sorted(smoke.EXPECTED_SHORT_BLOCKERS),
                    "independent_reopen_reconciliation_passed": True, "independent_reopen_same_watermark": True}, **smoke.ro.FLAGS}
            observer = SimpleNamespace(job=root, sample=lambda: copy.deepcopy(value))
            self.assertEqual(smoke.short_state(observer)["completed_rounds"], 15)
            for mutate in (lambda v: v.update(active_rounds=[15]),
                           lambda v: v.update(logical_point="inflight_or_unknown"),
                           lambda v: v.update(final_evidence_eligible=True),
                           lambda v: v["final_reconciliation"]["errors"].append("independent_reopen_golden_failed"),
                           lambda v: v.update(continuous_6h_stability_passed=True)):
                changed = copy.deepcopy(value)
                mutate(changed)
                observer.sample = lambda changed=changed: changed
                with self.assertRaisesRegex(ValueError, "short_smoke_not_cold_and_reconciled"):
                    smoke.short_state(observer)


if __name__ == "__main__":
    unittest.main()
