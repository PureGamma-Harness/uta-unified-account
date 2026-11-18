"""Offline bounded PR44 CI archive inspection; no target import or execution."""
import binascii
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import zipfile

PATTERNS = {
    "private_key": r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----",
    "github_token": r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b",
    "aws_access_key": r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b",
    "bearer": r"\bBearer\s+[A-Za-z0-9._~+/-]{20,}",
    "signed_url": r"https?://[^\s\x22\x27<>]*[?&](?:sig|signature|token|x-amz-signature|x-goog-signature|se)=",
    "nonce_or_secret_value": r"[\x22\x27]?(?:owner_nonce|lease_nonce|writer_nonce|broker_nonce|nonce|api[_-]?key|secret|password|authorization)[\x22\x27]?\s*[:=]\s*(?:[\x22\x27][^\x22\x27\r\n]{1,4096}[\x22\x27]|[0-9a-f]{16,256})",
    "SQLite_binary_magic_or_repr": r"SQLite format 3(?:\x00|\\x00)",
}
METHODS = (
    "test_complete_artifact_includes_tag_member_and_loaded_class_code",
    "test_unsupported_objects_and_financial_code_constants_still_reject",
    "test_enum_value_and_same_value_other_type_change_loaded_identity",
    "test_unknown_existing_payload_sources_are_never_upgraded_or_published",
    "test_original_error_and_native_typed_observation_filter_are_preserved",
    "test_publication_filter_keeps_original_rejection_of_aliases_and_unknown_fields",
)
LEGACY7 = {"tests_run", "failures", "errors", "skipped", "expected_failures",
           "unexpected_successes", "unittest_passed"}
PAIR = {"lease_observations", "lease_observations_truncated"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def scan(text):
    return {name: len(re.findall(pattern, text, flags=re.I)) for name, pattern in PATTERNS.items()}


def fresh_write(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        pending = data
        while pending:
            count = os.write(fd, pending)
            if count <= 0:
                raise OSError("short private decode write")
            pending = pending[count:]
        os.fsync(fd)
    finally:
        os.close(fd)


def main():
    mode, source_name, output_name, expected_sha = sys.argv[1:]
    if mode not in {"unit", "package"}:
        raise ValueError("unsupported evidence mode")
    source, output = Path(source_name), Path(output_name)
    size_limit = (2 if mode == "unit" else 1) * 1024 * 1024
    info = source.stat(follow_symlinks=False)
    if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size < size_limit:
        raise ValueError("input cap or file type")
    raw = source.read_bytes()
    if digest(raw) != expected_sha:
        raise ValueError("provider digest mismatch")
    payloads, members = {}, []
    report = {"mode": mode, "archive_bytes": len(raw), "archive_sha256": digest(raw),
              "provider_digest_matches": True, "container_scan": scan(raw.decode("latin1"))}
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        if not 1 <= len(entries) <= 64 or len({item.filename for item in entries}) != len(entries):
            raise ValueError("ZIP inventory")
        if sum(item.file_size for item in entries) >= size_limit:
            raise ValueError("expanded byte cap")
        report["archive_comment_bytes"] = len(archive.comment)
        report["member_comment_bytes"] = sum(len(item.comment) for item in entries)
        for item in entries:
            name, part = item.filename, PurePosixPath(item.filename)
            if (part.is_absolute() or ".." in part.parts or str(part) != name or "\\" in name
                    or ":" in name or item.is_dir() or item.flag_bits & 1
                    or stat.S_IFMT(item.external_attr >> 16) not in {0, stat.S_IFREG}):
                raise ValueError("unsafe archive member")
            if mode == "unit" and name not in {"summary.json", "worker-result.json", "unittest.txt"}:
                raise ValueError("unexpected unit member")
            package_name = name.removeprefix("uta-installed-validation/")
            if mode == "package" and not (name == "uta-package-artifact-manifest.json"
                    or name.startswith("uta-installed-validation/") and (
                        package_name in {"installed-report.json", "installed-cli-tests.txt"}
                        or re.fullmatch(r"uta[A-Za-z0-9_.-]*\.(?:stdout|stderr)\.txt", package_name))):
                raise ValueError("unexpected package report member")
            data = archive.read(item)
            crc = binascii.crc32(data) & 0xffffffff
            if crc != item.CRC or len(data) != item.file_size:
                raise ValueError("CRC or length")
            payloads[name] = data
            members.append({"name": name, "bytes": len(data), "sha256": digest(data),
                            "crc32": format(crc, "08x"), "CRC_matches": True})
    texts = {name: data.decode("utf-8") for name, data in payloads.items()}
    report["members"] = members
    report["member_sensitive_scans"] = {name: scan(text) for name, text in texts.items()}
    report["all_CRC_match"] = True
    report["public_original_archive_allowed"] = (
        not any(report["container_scan"].values()) and not report["archive_comment_bytes"]
        and not report["member_comment_bytes"] and not any(
            count for checks in report["member_sensitive_scans"].values() for count in checks.values()))
    if mode == "unit":
        if set(payloads) != {"summary.json", "worker-result.json", "unittest.txt"}:
            raise ValueError("incomplete unit evidence")
        summary, worker = (json.loads(texts[name]) for name in ("summary.json", "worker-result.json"))
        if summary["test_log_sha256"] != digest(payloads["unittest.txt"]):
            raise ValueError("summary log digest mismatch")
        statuses = re.findall(r"^test_\w+ \(([^)\r\n]+)\) \.\.\. (ok|FAIL|ERROR|skipped[^\r\n]*)$", texts["unittest.txt"], re.M)
        report["selected_new6"] = [{"test": "test_credit_lease_observation_tag.LeaseObservationTagArtifactTests." + method,
            "statuses": [status for name, status in statuses if name == "test_credit_lease_observation_tag.LeaseObservationTagArtifactTests." + method]}
            for method in METHODS]
        report["failure_or_error_headers"] = [{"kind": kind, "method": method, "qualified_id": qualified}
            for kind, method, qualified in re.findall(r"^(FAIL|ERROR): (\w+) \(([^)]+)\)$", texts["unittest.txt"], re.M)]
        report["actual_unit"] = {key: summary[key] for key in (
            "code_commit", "python", "platform", "sqlite", "tests_run", "failures", "errors",
            "skipped", "expected_failures", "unexpected_successes", "worker_exit_code", "passed",
            "unittest_passed", "source_unchanged", "tracked_source_clean_before", "tracked_source_clean_after")}
        report["worker_summary_shape"] = {
            "worker_keys": sorted(worker), "worker_key_count": len(worker),
            "exact_W9_keys": set(worker) == LEGACY7 | PAIR,
            "W_lease_observations_native_list": type(worker.get("lease_observations")) is list,
            "W_lease_observations_empty": worker.get("lease_observations") == [],
            "W_truncation_native_bool": type(worker.get("lease_observations_truncated")) is bool,
            "W_truncation_is_literal_False": worker.get("lease_observations_truncated") is False,
            "S_both_reserved_keys": PAIR <= set(summary),
            "S_lease_observations_native_list": type(summary.get("lease_observations")) is list,
            "S_lease_observations_empty": summary.get("lease_observations") == [],
            "S_truncation_native_bool": type(summary.get("lease_observations_truncated")) is bool,
            "S_truncation_is_literal_False": summary.get("lease_observations_truncated") is False,
            "all9_native_types_and_values_match": set(worker) == LEGACY7 | PAIR and all(
                type(worker[key]) is type(summary.get(key)) and worker[key] == summary.get(key) for key in worker),
            "standalone_full_qualification_claimed": False,
        }
    output.mkdir(mode=0o700)
    for name, data in payloads.items():
        target = output / name
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fresh_write(target, data)
    fresh_write(output / "inspection.json", (json.dumps(report, sort_keys=True, indent=2) + "\n").encode())
    print(json.dumps({key: report.get(key) for key in (
        "mode", "archive_bytes", "archive_sha256", "all_CRC_match", "public_original_archive_allowed",
        "actual_unit", "selected_new6", "worker_summary_shape")}, sort_keys=True))


if __name__ == "__main__":
    main()
