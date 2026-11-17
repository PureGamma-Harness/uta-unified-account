"""One tiny-file/fake-I/O batch, no SQL/native/owner/crypto/network."""
from contextlib import ExitStack
import errno
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
source = ROOT / "tools/independent_m0_controller.py"
assert sha256(source.read_bytes()).hexdigest() == "b5dd83d95ddae3708d2d48f2ab20d909747d64fcb8ac9ce7501be74cad810761"
spec = importlib.util.spec_from_file_location("independent_d1_665e", source)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def roots():
    temporary = tempfile.TemporaryDirectory(prefix="uta-d1-665e-independent-")
    private, public = Path(temporary.name) / "private", Path(temporary.name) / "public"
    private.mkdir(mode=0o700)
    public.mkdir(mode=0o700)
    return temporary, private, public


def fail_health(private, public):
    path = private / "B/SYNTHETIC_KEY_NONCE_REQUEST.tmp"
    original = FileNotFoundError(errno.ENOENT, "SYNTHETIC_KEY_NONCE_REQUEST", str(path))
    def check():
        try:
            m._mark_resource_error(original, "PRIVATE_CASE", "ENTRY_LSTAT", path)
            raise original
        except FileNotFoundError:
            m.need(False, "resource_missing_non_aux")
    try:
        m.resource_health_check(private, public, "CASE_B", check)
    except m.ResourceHealthFailure as failure:
        assert str(failure) == "resource_missing_non_aux" and failure.primary_error.__context__ is original
        return failure
    raise AssertionError("primary disappeared")


def prefix_scenario(kind):
    temporary, private, public = roots()
    with temporary:
        (private / "B").mkdir()
        streams = [private / "B/driver.stdout", private / "B/driver.stderr", private / "case-owner-B.stdout", private / "case-owner-B.stderr"]
        for n, p in enumerate(streams): p.write_bytes(b"synthetic-closed-" + bytes([n]))
        before = [p.read_bytes() for p in streams]
        fdopen = m.os.fdopen
        class CloseFailure:
            def __init__(self, *args, **kwargs): self.stream = fdopen(*args, **kwargs)
            def __enter__(self): return self.stream.__enter__()
            def __exit__(self, *args):
                self.stream.__exit__(*args)
                raise OSError(errno.EIO, "synthetic close failure")
        with ExitStack() as stack:
            if kind == "original_triple_failure":
                stack.enter_context(patch.object(m.os, "fsync", side_effect=OSError(errno.EIO, "synthetic fsync failure")))
                stack.enter_context(patch.object(m.os, "rename", side_effect=PermissionError("synthetic quarantine failure")))
                stack.enter_context(patch.object(Path, "unlink", side_effect=PermissionError("synthetic delete failure")))
            elif kind == "close_failure": stack.enter_context(patch.object(m.os, "fdopen", CloseFailure))
            elif kind == "link_failure": stack.enter_context(patch.object(m.os, "link", side_effect=PermissionError("synthetic link failure")))
            elif kind == "alias_cleanup_failure": stack.enter_context(patch.object(Path, "unlink", side_effect=PermissionError("synthetic alias cleanup failure")))
            failure = fail_health(private, public)
        target = public / "resource-diagnostic-CASE_B.json"
        incomplete = private / "resource-diagnostic-incomplete-CASE_B.json"
        committed = kind in ("normal", "alias_cleanup_failure")
        assert target.exists() is committed
        assert failure.diagnostic_status == ("RECORDED" if committed else "UNAVAILABLE")
        assert incomplete.exists() is (kind != "normal")
        data = (target if committed else incomplete).read_bytes()
        value = json.loads(data)
        assert m.validate_resource_diagnostic(value)
        assert value["unknown_relative_path_sha256"] == sha256(b"PRIVATE_ROOT\0B/SYNTHETIC_KEY_NONCE_REQUEST.tmp").hexdigest()
        assert b"SYNTHETIC_KEY_NONCE_REQUEST" not in data and str(private).encode() not in data
        assert [p.read_bytes() for p in streams] == before
        usage = m.resource_usage(private, public)
        assert usage["normal"] == sum(map(len, before))
        assert usage["cleanup"] == len(data) * (2 if kind == "alias_cleanup_failure" else 1)
        if kind == "alias_cleanup_failure":
            assert target.stat().st_ino == incomplete.stat().st_ino
        records = []
        assert m.collect_resource_diagnostics(public, records) == "COMPLETE"
        assert len(records) == (1 if committed else 0)
        if kind == "normal":
            first = target.read_bytes()
            again = fail_health(private, public)
            assert again.diagnostic_status == "ALREADY_RECORDED" and target.read_bytes() == first
        m.public_write(public, "manifest.json", {"files": records, "source_commit": m.SOURCE,
                       "private_authorities_requests_keys_nonces_signatures_streams_not_uploaded": True})
        assert m.verify_public(public)
        return {"name": kind, "status": "PASS", "writer_status": failure.diagnostic_status,
                "public_record_count": len(records), "complete_failed_prefix_private_only": not committed,
                "cleanup_bytes": usage["cleanup"], "record_bytes": len(data),
                "primary_and_four_streams_preserved": True, "public_empty_not_claimed_delivery": not committed,
                "directory_fsync_or_crash_durability_claimed": False}


def value():
    return dict(kind="M0_RESOURCE_DIAGNOSTIC", version=1, phase="CASE_B", scope="PRIVATE_ROOT", operation="ENTRY_LSTAT",
                errno=2, catalogue_label="UNKNOWN", unknown_relative_path_sha256="a" * 64, primary_code="resource_missing_non_aux")


def headroom(extra):
    temporary, private, public = roots()
    with temporary:
        v = value()
        count = len((json.dumps(v, sort_keys=True, separators=(",", ":")) + "\n").encode())
        with patch.object(m, "_diagnostic_cleanup_bytes", return_value=m.CLEANUP_RESERVE - 2 * count + extra):
            try: result = m.write_resource_diagnostic(private, public, v)
            except m.GateError as failure:
                assert extra == 1 and str(failure) == "diagnostic_cleanup_cap"
                assert not list(private.iterdir()) and not list(public.iterdir())
            else:
                assert extra == 0 and result == "RECORDED"
        return {"name": "two_alias_headroom_plus_one" if extra else "two_alias_headroom_equality", "status": "PASS"}


def schema_and_routes():
    denied = 0
    for change in ({"path": "SYNTHETIC"}, {"key": "SYNTHETIC"}, {"nonce": "SYNTHETIC"}, {"errno": True}, {"errno": 2.0}, {"errno": float("nan")}, {"errno": -1}, {"version": True}, {"unknown_relative_path_sha256": "A" * 64}):
        try: m.validate_resource_diagnostic(dict(value(), **change))
        except m.GateError: denied += 1
        else: raise AssertionError("invalid schema accepted")
    try: m.strict_json('{"kind":"x","kind":"y"}')
    except m.GateError: denied += 1
    else: raise AssertionError("duplicate JSON accepted")
    for route in ("resource-diagnostic-incomplete-CASE_B.json", "resource-diagnostic-CASE_B.json.part", "case-B-safe/resource-diagnostic-CASE_B.json"):
        temporary, _private, public = roots()
        with temporary:
            path = public / route
            path.parent.mkdir(mode=0o700, exist_ok=True)
            path.write_text(json.dumps(value()))
            record = dict(name=route, bytes=path.stat().st_size, sha256=m.digest(path))
            m.public_write(public, "manifest.json", {"files": [record], "source_commit": m.SOURCE,
                           "private_authorities_requests_keys_nonces_signatures_streams_not_uploaded": True})
            try: m.verify_public(public)
            except m.GateError: denied += 1
            else: raise AssertionError("invalid public route accepted")
    temporary, private, public = roots()
    with temporary:
        failure = fail_health(private, public)
        records = []
        with patch.object(m, "read_json", side_effect=PermissionError("synthetic collection failure")):
            assert m.collect_resource_diagnostics(public, records) == "UNAVAILABLE" and records == []
        assert str(failure) == "resource_missing_non_aux"
        m.public_write(public, "manifest.json", {"files": records, "source_commit": m.SOURCE,
                       "private_authorities_requests_keys_nonces_signatures_streams_not_uploaded": True})
        try: m.verify_public(public)
        except m.GateError: denied += 1
        else: raise AssertionError("unlisted record after collection failure accepted")
    return {"name": "schema_routes_and_collection", "status": "PASS", "strict_negative_controls": denied,
            "primary_survives_collection_failure": True}


cases = [prefix_scenario(k) for k in ("normal", "original_triple_failure", "close_failure", "link_failure", "alias_cleanup_failure")]
cases.extend([headroom(0), headroom(1), schema_and_routes()])
print(json.dumps({"candidate": "665e178db90dd729954e5cffa7897f9db6958132", "cases": cases,
                  "original_f605_failure_relabelled": False, "failed_prefix_modified_to_malformed": False,
                  "actual_SQL_native_owner_crypto_network_M04_CI": 0}, sort_keys=True))
