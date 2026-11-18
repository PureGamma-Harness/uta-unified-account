"""Bounded offline CI ZIP/text inspection; never imports or executes UTA."""
import binascii
import hashlib
import io
import json
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
    "signed_url": r"https?://[^\s\"'<>]*[?&](?:sig|signature|token|x-amz-signature|x-goog-signature|se)=",
}
SELECTED = [
    "test_readiness_before_quote_reference.BeforeQuoteReferenceTests." + name for name in (
        "test_first_unknown_is_retained_without_a_second_observation_or_quote",
        "test_complete_owner_witness_precedes_factory_without_promoting_financial_ready",
        "test_stale_generation_and_inactive_owner_are_not_a_complete_witness",
        "test_unknown_after_owner_fields_were_read_still_fails_the_single_attempt",
        "test_unconsumed_current_ready_frame_cannot_trigger_diagnostic_or_quote",
        "test_late_native_return_retains_report_without_quote_or_second_observation",
        "test_identity_equality_requires_native_integer_types",
    )
] + [
    "test_process_readiness.ProcessReadinessTests.test_malformed_missing_and_oversize_persistent_quotes_fail_closed",
    "test_process_readiness.ProcessReadinessTests.test_same_version_changed_persistent_content_is_not_reused",
]


def scan(text):
    return {name: len(re.findall(pattern, text, flags=re.I)) for name, pattern in PATTERNS.items()}


def main():
    mode, source, destination = sys.argv[1:]
    if mode not in {"unit", "package", "joblog"}:
        raise ValueError("unknown inspection mode")
    source, destination = Path(source), Path(destination)
    details = source.stat(follow_symlinks=False)
    limit = 1024 * 1024 if mode == "package" else 2 * 1024 * 1024
    if not stat.S_ISREG(details.st_mode) or details.st_size >= limit:
        raise ValueError("regular input must be strictly below capture cap")
    data = source.read_bytes()
    report = {"mode": mode, "source_name": source.name, "source_bytes": len(data),
              "source_sha256": hashlib.sha256(data).hexdigest(), "members": []}
    payloads = {}
    if mode == "joblog":
        payloads["job.log"] = data
    else:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if not 1 <= len(entries) <= 64 or len({item.filename for item in entries}) != len(entries):
                raise ValueError("duplicate or excessive ZIP entries")
            if sum(item.file_size for item in entries) >= limit:
                raise ValueError("expanded ZIP cap")
            for item in entries:
                name, part = item.filename, PurePosixPath(item.filename)
                if (part.is_absolute() or ".." in part.parts or str(part) != name
                        or "\\" in name or ":" in name or item.is_dir()
                        or item.flag_bits & 1 or len(name) > 512
                        or stat.S_IFMT(item.external_attr >> 16) not in {0, stat.S_IFREG}):
                    raise ValueError("unsupported ZIP entry")
                if mode == "unit" and name not in {"summary.json", "worker-result.json", "unittest.txt"}:
                    raise ValueError("unknown unit evidence member")
                package_member = name.removeprefix("uta-installed-validation/")
                if mode == "package" and not (
                        name == "uta-package-artifact-manifest.json"
                        or name.startswith("uta-installed-validation/") and (
                            package_member in {"installed-report.json", "installed-cli-tests.txt"}
                            or re.fullmatch(r"uta[A-Za-z0-9_.-]*\.(?:stdout|stderr)\.txt", package_member))):
                    raise ValueError("unknown package report member")
                payload = archive.read(item)
                crc = binascii.crc32(payload) & 0xffffffff
                if len(payload) != item.file_size or crc != item.CRC:
                    raise ValueError("ZIP length or CRC mismatch")
                payloads[name] = payload
                report["members"].append({"name": name, "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(), "crc32": format(crc, "08x"),
                    "CRC_matches": True, "compressed_bytes": item.compress_size})
            if mode == "unit" and set(payloads) != {"summary.json", "worker-result.json", "unittest.txt"}:
                raise ValueError("incomplete unit evidence inventory")
    texts = {name: value.decode("utf-8") for name, value in payloads.items()}
    report["bounded_sensitive_scan"] = {name: scan(text) for name, text in texts.items()}
    report["sensitive_scan_clear"] = not any(
        count for checks in report["bounded_sensitive_scan"].values() for count in checks.values())
    report["json_keys"] = {name: sorted(json.loads(text.lstrip("\ufeff")))
                          for name, text in texts.items() if name.endswith(".json")}
    if "unittest.txt" in texts:
        text = texts["unittest.txt"]
        observed = re.findall(r"^test_\w+ \(([^)\r\n]+)\) \.\.\. (ok|FAIL|ERROR|skipped[^\r\n]*)$", text, re.M)
        report["selected_test_outcomes"] = [
            {"test": name, "raw_statuses": [status for found, status in observed if found == name]}
            for name in SELECTED]
        report["failure_headers"] = [
            {"kind": kind, "method": method, "qualified": qualified}
            for kind, method, qualified in re.findall(r"^(FAIL|ERROR): (\w+) \(([^)]+)\)$", text, re.M)]
        report["unittest_totals"] = re.findall(r"^Ran (\d+) tests? in ([0-9.]+)s$", text, re.M)
        report["unittest_result_lines"] = re.findall(r"^(?:FAILED \([^\r\n]*\)|OK(?: \([^\r\n]*\))?)$", text, re.M)
    destination.mkdir(mode=0o700)
    for name, payload in payloads.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with target.open("xb") as stream:
            stream.write(payload)
    with (destination / "inspection.json").open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"source_name": source.name, "source_bytes": len(data),
        "source_sha256": report["source_sha256"], "members": len(report["members"]),
        "sensitive_scan_clear": report["sensitive_scan_clear"],
        "selected_test_outcomes": report.get("selected_test_outcomes"),
        "failure_headers": report.get("failure_headers"),
        "unittest_totals": report.get("unittest_totals"),
        "unittest_result_lines": report.get("unittest_result_lines")}, sort_keys=True))


if __name__ == "__main__":
    main()
