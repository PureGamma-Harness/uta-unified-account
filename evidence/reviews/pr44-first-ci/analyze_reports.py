"""Selected CI reports to bounded public metadata, without target execution."""
from pathlib import Path
import hashlib
import json
import os
import re
import zipfile

PRIVATE = Path("/workspace/pr44-ci-first-private")
SAFE = Path("/workspace/uta-pr44-first-ci-evidence/evidence/reviews/pr44-first-ci")


def write_new(path, value):
    data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        while data:
            n = os.write(fd, data)
            if n <= 0:
                raise OSError("short metadata write")
            data = data[n:]
        os.fsync(fd)
    finally:
        os.close(fd)


def main():
    spec = json.loads((PRIVATE / "parser/package-analysis-input.json").read_text())
    tracked = (PRIVATE / "parser/exact-C-tracked-paths.txt").read_text().splitlines()
    package_root = PRIVATE / "parser/package-14409875235-first"
    package = json.loads((package_root / "uta-package-artifact-manifest.json").read_text())
    installed = json.loads((package_root / "uta-installed-validation/installed-report.json").read_text())
    unit_root = PRIVATE / "parser/unit-14408608768-first"
    summary = json.loads((unit_root / "summary.json").read_text())
    unit_text = (unit_root / "unittest.txt").read_text()
    required = package["sdist_required_files"]
    if package["source_commit"] != spec["C"] or installed["source_commit"] != spec["C"]:
        raise ValueError("package source")
    if len(required) != len(set(required)) or set(required) != set(tracked):
        raise ValueError("package tracked set")
    if len(package["checks"]) != 7 or any(v is not True for v in package["checks"].values()):
        raise ValueError("seven checks")
    if package["runtime_files"] != spec["expected_runtime"]:
        raise ValueError("package runtime files")
    digest = hashlib.sha256(json.dumps(spec["expected_runtime"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if package["runtime_tree_sha256"] != digest or installed["runtime_tree_sha256"] != digest:
        raise ValueError("runtime tree digest")
    if installed["tests"] != {"run": 8, "failures": 0, "errors": 0, "skipped": 0} or installed["expected_tests"] != 8 or installed["passed"] is not True:
        raise ValueError("installed8")
    if len(installed["commands"]) != 8 or any(v["returncode"] != 0 for v in installed["commands"]):
        raise ValueError("installed commands")
    rows = [{"path": p, **spec["new_expected"][p], "listed": p in required} for p in spec["changed32"]]
    write_new(SAFE / "package-selection.json", {
        "schema": 1, "source_commit": spec["C"], "run_id": 44263248587, "job_id": 134661484927,
        "artifact_id": 14409875235, "artifact_bytes": 60686,
        "artifact_sha256": "45ff29857d3fdd32b7b8e19259150bb80f20f948b3a1cd1dae22a32058b15954",
        "seven_CI_report_checks": package["checks"], "all_checks_true": True,
        "required_tracked_files": len(required), "required_set_equals_exact_C_Git": True,
        "sdist_missing": package["sdist_missing"], "sdist_mismatched": package["sdist_mismatched"],
        "changed32": rows, "all32_selected": all(v["listed"] for v in rows),
        "runtime_files": 62, "runtime_map_matches_exact_C": True, "runtime_tree_sha256": digest,
        "unit_CI_captured_UTA_Python_sources": 61, "dashboard_HTML_separately_bound_to_Git": True,
        "installed": {"tests": installed["tests"], "expected_tests": 8, "passed": installed["passed"],
            "commands": installed["commands"], "interpreter": installed["interpreter"], "sqlite": installed["sqlite"],
            "isolated": installed["isolated"], "pythonpath": installed["pythonpath"]},
        "large_wheel_sdist_downloaded": False, "independent_binary_seal_claimed": False,
        "complete_managed_qualification_result": None, "production_approved": False,
        "limit": "One successful exact-push report only; seven report checks do not constitute a new local binary seal or full qualification invocation."})
    prior = json.loads((PRIVATE / "metadata/pr42-CI-classification.json").read_text())
    old_ids = prior["same_25_unique_ERROR_IDs_observed_each_job"]
    statuses = re.findall(r"^test_\w+ \(([^)\r\n]+)\) \.\.\. (ok|FAIL|ERROR|skipped[^\r\n]*)$", unit_text, re.M)
    observed = [{"old_error_id": name, "selected_new_statuses": [s for test, s in statuses if test == name]} for name in old_ids]
    sh = prior["extra_single_push313_FAIL"]
    if len(observed) != 25 or any(v["selected_new_statuses"] != ["ok"] for v in observed):
        raise ValueError("old25 per-ID evidence mismatch")
    sh_statuses = [s for name, s in statuses if name == sh]
    if sh_statuses != ["ok"]:
        raise ValueError("oldSH per-ID evidence mismatch")
    write_new(SAFE / "historical-comparison.json", {
        "schema": 1, "selected_new_run": 44263248587, "selected_new_job": 134661484927,
        "new_source": spec["C"], "new_counts": {k: summary[k] for k in ("tests_run", "failures", "errors", "skipped")},
        "old_source": prior["source_head"], "old25_error_ids": observed, "old_SH_id": sh,
        "new_selected_SH_statuses": sh_statuses, "old_eight_times_25_errors_and_SH_failure_preserved": True,
        "old_specific_unsupported_attribute": "NOT_OBSERVED", "old_specific_cause": "UNDETERMINED",
        "retroactive_Enum_attribution": False,
        "limit": "Per-ID comparison in one new success unit, separate from eight job terminal metadata. No old attribute or cause is recovered; other seven unit ZIPs were not acquired."})
    patterns = {"UUID": r"(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
                "standalone_32hex": r"(?i)(?<![0-9a-f])[0-9a-f]{32}(?![0-9a-f])"}
    scans = []
    for ident in (14408608768, 14409875235):
        archive_path = PRIVATE / "downloads" / ("artifact-" + str(ident) + ".zip")
        raw = archive_path.read_bytes()
        container = {k: len(re.findall(p, raw.decode("latin1"))) for k, p in patterns.items()}
        with zipfile.ZipFile(archive_path) as archive:
            members = {info.filename: {k: len(re.findall(p, archive.read(info).decode("utf-8"))) for k, p in patterns.items()} for info in archive.infolist()}
        scans.append({"artifact_id": ident, "archive_sha256": hashlib.sha256(raw).hexdigest(),
            "container": container, "members": members,
            "clear": not any(container.values()) and not any(n for row in members.values() for n in row.values())})
    write_new(SAFE / "additional-nonce-review.json", {"schema": 1, "patterns": list(patterns),
        "archives": scans, "limit": "Directed UUID/standalone32hex review in addition to primary secret/nonce/DB-binary checks, not arbitrary-secret attestation."})
    print(json.dumps({"package7": True, "installed8": installed["tests"], "all32_selected": all(v["listed"] for v in rows),
        "tracked": len(required), "old25_each_new_single_ok": True, "oldSH_new_single_ok": True,
        "old_attribute_NOT_OBSERVED_preserved": True, "additional_nonce_reviews_clear": [v["clear"] for v in scans]}))


if __name__ == "__main__":
    main()
