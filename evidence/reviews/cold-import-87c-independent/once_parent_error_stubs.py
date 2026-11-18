"""Only parent wait/output fake objects, no interpreter/process/SQL execution."""
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
HELPER = ROOT / "tools/cold_import_contract.py"
assert sha256(HELPER.read_bytes()).hexdigest() == "91c4a813e4147bcdfb68cc28b3d0f0604e9ec5c6f0a94dac28f23972675223c5"
spec = importlib.util.spec_from_file_location("independent_cold_parent_only", HELPER)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
assert os.sched_getaffinity(0) == {3}
forbidden = []


def deny(event, args):
    if event in {"subprocess.Popen", "os.fork", "os.kill", "os.posix_spawn", "sqlite3.connect",
                 "socket.connect", "socket.bind", "fcntl.flock", "signal.pidfd_send_signal"}:
        forbidden.append(event)
        raise AssertionError("forbidden actual execution")


sys.addaudithook(deny)


def run(kind, malformed=None):
    calls = []
    with TemporaryDirectory(prefix="uta-cold-fake-parent-") as directory:
        root = Path(directory)
        (root / "tools").mkdir()
        # This is hash input only. The fake never executes this or CHILD_CODE.
        target = root / "tools/independent_m0_controller.py"
        target.write_bytes(b"# synthetic hash input; never compiled or run\n")
        proof = dict(kind="COLD_IMPORT_PROOF", version=1, mode="controller", status="PASS_IMPORT_COLD",
                     isolated=True, no_site=True, sitecustomize_loaded=False, guard_events=[],
                     blocked_cache_count=0, target_sha256=sha256(target.read_bytes()).hexdigest())
        payload = json.dumps(proof).encode()
        if malformed == "extra":
            proof["private_path"] = "SYNTHETIC_PRIVATE_SENTINEL"
            payload = json.dumps(proof).encode()
        elif malformed == "duplicate":
            payload = payload[:-1] + b',"mode":"controller"}'
        elif malformed == "not_json":
            payload = b"SYNTHETIC_PRIVATE_SENTINEL"

        class Fake:
            returncode = None

            def __init__(self, argv, **kwargs):
                assert argv[1:3] == ["-I", "-S"]
                assert argv[3] == "-c" and argv[4] == m.CHILD_CODE
                kwargs["stdout"].write(payload)

            def wait(self, timeout):
                calls.append(["wait", timeout])
                if kind == "wait_OSerror" and len(calls) == 1:
                    raise OSError("SYNTHETIC_PRIVATE_SENTINEL")
                if kind == "unreaped" or kind == "timeout" and len(calls) == 1:
                    raise m.subprocess.TimeoutExpired("SYNTHETIC_PRIVATE_SENTINEL", timeout)
                self.returncode = 0
                return 0

            def kill(self):
                calls.append(["kill", None])

        with patch.object(m.subprocess, "Popen", Fake):
            result = m.probe_import("controller", root)
        expected_code = {"wait_OSerror": "CHILD_OS_ERROR", "timeout": "CHILD_TIMEOUT",
                         "unreaped": "CHILD_REAP_UNKNOWN", "malformed": "CHILD_PROOF_INVALID"}[kind]
        expected_calls = [["wait", 1]] if kind == "malformed" else [["wait", 1], ["kill", None], ["wait", 1]]
        safe = "SYNTHETIC_PRIVATE_SENTINEL" not in json.dumps(result)
        matched = (result["status"] == "UNKNOWN" and result["code"] == expected_code
                   and result["proof"] is None and safe and calls == expected_calls
                   and result["child_reaped"] is (kind != "unreaped"))
        if kind in {"wait_OSerror", "timeout"}:
            matched = matched and result["returncode"] == 0 and result["killed"] is True
        return {"kind": kind, "malformed_variant": malformed, "status": "PASS" if matched else "RED",
                "result": result, "calls": calls, "fake_valid_proof_after_error_not_accepted": kind in {"wait_OSerror", "timeout"},
                "raw_sentinel_not_public": safe, "actual_child_executed": False}


cases = [run("wait_OSerror"), run("timeout"), run("unreaped")]
cases.extend(run("malformed", variant) for variant in ("extra", "duplicate", "not_json"))
value = {"fixed_commit": "87c9675d9852d709782d7f461661c66f2e0ba80d",
         "helper_sha256": sha256(HELPER.read_bytes()).hexdigest(), "affinity": sorted(os.sched_getaffinity(0)),
         "cases": cases, "case_count": len(cases), "forbidden_events": forbidden,
         "SQL_uta_modules": sorted(n for n in sys.modules if n in {"sqlite3", "_sqlite3", "uta"} or n.startswith("uta.")),
         "real_child_processes_SQL_native_crypto_network_signals_CI": 0,
         "author_four_real_children_and_old8_rerun": False}
print(json.dumps(value, sort_keys=True))
raise SystemExit(1 if forbidden or value["SQL_uta_modules"] or any(c["status"] != "PASS" for c in cases) else 0)
