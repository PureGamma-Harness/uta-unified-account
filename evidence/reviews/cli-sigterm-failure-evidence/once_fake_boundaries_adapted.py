"""Fake process/identity/clock only, tiny own artifacts, no SQL or signal."""
from hashlib import sha256
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
source = ROOT / "tests/cli_sigterm_failure_evidence.py"
assert sha256(source.read_bytes()).hexdigest() == "6baec73b84ac4f73521c362e1d8fc7c5ff63d09c5aa4c869e1e8e5ae2b831f1d"
spec = importlib.util.spec_from_file_location("independent_cli_evidence_1ef", source)
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
SENTINEL = "SYNTHETIC_PRIVATE_NONCE_NOT_A_REAL_SECRET"


def identity(pid):
    return dict(observed=True, pid=pid, start_ticks=101, boot_id="11111111-2222-3333-4444-555555555555", uid=123, parent=456, state="S")


class Process:
    def __init__(self, outcome="normal", exited=False):
        self.pid = 700001
        self.args = ["python", "-m", "uta", "--credentials", "/synthetic/private/credentials"]
        self.returncode = 0 if exited else None
        self.calls, self.kills = [], 0
        self.outcome = outcome
        self.suffix = b"S" * 41001 + b"\x00\xff-END"
        self.stderr = b"E" * 41007
    def poll(self): return self.returncode
    def kill(self): self.kills += 1
    def communicate(self, *, timeout):
        self.calls.append(timeout)
        if self.outcome == "timeout":
            raise subprocess.TimeoutExpired(self.args, timeout, output=b"PART-OUT", stderr=b"PART-ERR")
        if self.outcome == "cleanup_error": raise OSError(SENTINEL)
        self.returncode = 0 if self.returncode == 0 else -9
        return self.suffix, self.stderr


def scenario(name, reader=identity):
    with tempfile.TemporaryDirectory(prefix="uta-cli-independent-") as directory:
        root = Path(directory)
        process = Process(name if name in {"timeout", "cleanup_error"} else "normal", exited=name == "success")
        notice = io.StringIO()
        ticks = iter(range(1000, 200000, 10))
        try:
            evidence = h.CliFailureEvidence(process, artifact_root=root, clock=lambda: next(ticks), identity_reader=reader, notice_stream=notice)
        except BaseException as error:
            return {"name": name, "status": "RED", "constructor_escaped_on_invalid_identity": type(error).__name__, "real_process_created": False}
        if name == "success":
            evidence.cleanup()
            assert evidence.directory is None and list(root.iterdir()) == [] and notice.getvalue() == ""
            return {"name": name, "status": "PASS", "archive_created": False}
        prefix = b"\x00\xff-banner-prefix\n"
        evidence.banner(prefix)
        primary = subprocess.TimeoutExpired(process.args, 5)
        observed = None
        try:
            try: raise primary
            except BaseException as error:
                if name == "archive_error":
                    with patch.object(evidence, "_write", side_effect=OSError(SENTINEL)): evidence.primary_failure(error)
                else: evidence.primary_failure(error)
                raise
            finally:
                if name == "archive_error":
                    with patch.object(evidence, "_write", side_effect=OSError(SENTINEL)): evidence.cleanup()
                else: evidence.cleanup()
        except BaseException as error: observed = error
        assert observed is primary
        raw_notice = notice.getvalue()
        row = evidence.packet()
        raw_leak = SENTINEL in raw_notice
        invalid_same_birth = name == "missing_birth_fields" and any(p["same_child_birth"] for p in row["phases"])
        red = raw_leak or invalid_same_birth
        if name != "archive_error":
            assert evidence.directory.stat().st_mode & 0o777 == 0o700
            assert all(p.stat().st_mode & 0o777 == 0o600 for p in evidence.directory.iterdir())
            expected_out = prefix + (b"PART-OUT" if name == "timeout" else b"" if name == "cleanup_error" else process.suffix)
            expected_err = b"PART-ERR" if name == "timeout" else b"" if name == "cleanup_error" else process.stderr
            assert (evidence.directory / "stdout.bin").read_bytes() == expected_out
            assert (evidence.directory / "stderr.bin").read_bytes() == expected_err
            before = {p.name: p.read_bytes() for p in evidence.directory.iterdir()}
            evidence.cleanup()
            assert before == {p.name: p.read_bytes() for p in evidence.directory.iterdir()}
        if name in {"timeout", "cleanup_error"}:
            assert row["cleanup"] == "UNKNOWN" and row["streams_complete"] is False and row["child_exit_and_reap_confirmed"] is False
        if name == "archive_error":
            assert '"archive_retained": false' in raw_notice and SENTINEL not in raw_notice
        assert process.calls == [5]
        return {"name": name, "status": "RED" if red else "PASS", "primary_object_preserved": True,
                "prefix_plus_suffix_exact_without_loss_or_duplication": name != "archive_error",
                "same_child_birth_claimed_for_missing_fields": invalid_same_birth,
                "raw_extra_identity_sentinel_copied_to_public_notice": raw_leak,
                "streams_complete": row["streams_complete"], "cleanup": row["cleanup"],
                "communicate_calls": process.calls, "real_process_created": False}


cases = [scenario("prefix_roundtrip"), scenario("timeout"), scenario("cleanup_error"), scenario("archive_error"), scenario("success"),
         scenario("missing_birth_fields", lambda pid: dict(observed=True, pid=pid)),
         scenario("extra_identity_fields", lambda pid: dict(identity(pid), nonce=SENTINEL, path="/synthetic/private/path")),
         scenario("nonmapping_identity", lambda _pid: None)]
print(json.dumps({"candidate": "1ef63c8eb994eeb3e6b83ba730f31fc9421278d0", "cases": cases,
                  "invalid_identity_readers_are_fault_injection_not_observed_default_proc_leaks": True,
                  "SQL_real_Popen_CLI_worker_signal_H1AuthDB_childbootstrap": 0}, sort_keys=True))
raise SystemExit(1 if any(c["status"] == "RED" for c in cases) else 0)
