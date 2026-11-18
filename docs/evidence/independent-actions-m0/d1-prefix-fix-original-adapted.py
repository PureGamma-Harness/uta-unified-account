"""Own tiny files and fake I/O failures; no SQL/process/network/crypto."""
import errno
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "tools/independent_m0_controller.py"
assert sha256(SOURCE.read_bytes()).hexdigest() == "bcb5428091ce5b1888ead3496bb150e00aa3c8124bb32f11f7f818e71b41427d"
spec = importlib.util.spec_from_file_location("independent_d1_3e586", SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def scenario(inject_failure):
    with tempfile.TemporaryDirectory(prefix="uta-d1-prefix-independent-") as temporary:
        private, public = Path(temporary) / "private", Path(temporary) / "public"
        private.mkdir(mode=0o700)
        public.mkdir(mode=0o700)
        (private / "B").mkdir()
        streams = [private / "B/driver.stdout", private / "B/driver.stderr",
                   private / "case-owner-B.stdout", private / "case-owner-B.stderr"]
        for n, path in enumerate(streams):
            path.write_bytes(b"synthetic-closed-" + bytes([n]))
        before = [p.read_bytes() for p in streams]
        missing = private / "B/SYNTHETIC_KEY_NONCE_REQUEST.tmp"

        def check():
            try:
                m._resource_lstat(missing, "PRIVATE_CASE", "ENTRY_LSTAT")
            except FileNotFoundError:
                m.need(False, "resource_missing_non_aux")

        def invoke():
            try:
                m.resource_health_check(private, public, "CASE_B", check)
            except m.ResourceHealthFailure as failure:
                return failure
            raise AssertionError("original health failure was lost")

        if inject_failure:
            with patch.object(m.os, "fsync", side_effect=OSError(errno.EIO, "synthetic fsync failure")), \
                 patch.object(m.os, "rename", side_effect=PermissionError("synthetic quarantine failure")), \
                 patch.object(Path, "unlink", side_effect=PermissionError("synthetic delete failure")):
                failure = invoke()
        else:
            failure = invoke()
        primary_preserved = str(failure) == "resource_missing_non_aux" and isinstance(failure.primary_error.__context__, FileNotFoundError)
        assert primary_preserved
        path = public / "resource-diagnostic-CASE_B.json"
        published = path.exists()
        contents = (path if published else private / "resource-diagnostic-incomplete-CASE_B.json").read_bytes()
        assert b"SYNTHETIC_KEY_NONCE_REQUEST" not in contents
        assert str(private).encode() not in contents
        assert [p.read_bytes() for p in streams] == before
        value = json.loads(contents)
        m.validate_resource_diagnostic(value)
        records = []
        collected = m.collect_resource_diagnostics(public, records)
        m.public_write(public, "manifest.json", {"files": records, "source_commit": m.SOURCE,
                       "private_authorities_requests_keys_nonces_signatures_streams_not_uploaded": True})
        accepted = m.verify_public(public)
        if inject_failure:
            assert not published and records == [] and failure.diagnostic_status == "UNAVAILABLE"
        else:
            assert published and len(records) == 1 and failure.diagnostic_status == "RECORDED"
        red = inject_failure and failure.diagnostic_status == "UNAVAILABLE" and collected == "COMPLETE" and accepted and len(records) == 1
        return {"name": "failed_full_prefix_recollected" if inject_failure else "normal_committed_record",
                "status": "RED" if red else "PASS", "primary_preserved": primary_preserved,
                "write_diagnostic_status": failure.diagnostic_status,
                "leftover_complete_json_prefix": True, "prefix_location": "PUBLIC_COMMITTED" if published else "PRIVATE_INCOMPLETE", "collected_status": collected,
                "manifest_record_count": len(records), "verify_public_accepted": accepted,
                "raw_secret_or_path_copied": False, "four_streams_unchanged": True,
                "modified_prefix_to_malformed_after_write": False}


if __name__ == "__main__":
    cases = [scenario(False), scenario(True)]
    print(json.dumps({"candidate": "3e586f99c4ed750766461d4212cd17d9501cea84", "cases": cases,
                      "financial_primary_outcome_upgraded": False, "SQL_real_owner_crypto_network": 0}, sort_keys=True))
    raise SystemExit(1 if any(case["status"] == "RED" for case in cases) else 0)
