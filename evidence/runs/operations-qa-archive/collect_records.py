"""Read-only collection of historical QA records; never rerun or relabel QA.

The Git archive reads below hash recorded source bytes in memory. They do not
build a release, execute project code, open an authority, or alter input files.
"""
import argparse
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile
import zipfile


COMMITS = {
    "13e6924": "13e6924377f031bb3da7ec94aa88df25ed7612ec",
    "24ac06b": "24ac06bc7b9662e1bd215a85ce1b5231e03e37e6",
    "4608ffe": "4608ffeda0651f8dafd2cd151618a71ed99aa62e",
}
RUNTIMES = ("python310", "python312", "python313-sqlite346")
RAW_FILES = ("summary.json", "unittest.txt", "worker-result.json")
SOURCE_DIRS = {"uta", "tests", "formal", "tools", "benchmarks", "scripts"}
SOURCE_ROOTS = {"pyproject.toml", "MANIFEST.in", "LICENSE"}
PATTERNS = {
    "query_url": r"https?://[^\s\"']+\?[^\s\"']+",
    "bearer_value": r"Bearer\s+[A-Za-z0-9._~+/=-]{20,}",
    "private_key_block": r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "quoted_secret_value": r"(?i)[\"'](?:nonce|secret|secret_b64|token|api_key|signing_key|private_key|x-uta-nonce|x-uta-signature)[\"']\s*:\s*[\"'][^\"']{16,}[\"']",
    "assigned_secret_value": r"(?i)\b(?:nonce|secret|secret_b64|token|api_key|signing_key|private_key|x-uta-nonce|x-uta-signature)\s*[=:]\s*[\"']?[A-Za-z0-9_+/=-]{20,}",
}


def digest(data):
    return sha256(data).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-root", type=Path, required=True)
    parser.add_argument("--ci-root", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    original_hashes, copied_hashes, privacy, runs, source_cache = {}, {}, {}, [], {}

    def git_source(commit):
        if commit not in source_cache:
            paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", commit],
                cwd=args.repo, text=True).splitlines()
            selected = {name for name in paths if (
                name.endswith(".py") and name.split("/")[0] in SOURCE_DIRS
                or name.startswith("tests/fixtures/") or name in SOURCE_ROOTS)}
            data = subprocess.check_output(["git", "archive", "--format=tar", commit, *sorted(selected)],
                cwd=args.repo)
            with tarfile.open(fileobj=io.BytesIO(data)) as archive:
                source_cache[commit] = {item.name: digest(archive.extractfile(item).read())
                    for item in archive.getmembers() if item.isfile()}
            assert set(source_cache[commit]) == selected
        return source_cache[commit]

    def collect(original, relative, commit, origin):
        destination = output / relative
        destination.mkdir(parents=True)
        data = {name: (original / name).read_bytes() for name in RAW_FILES}
        for name, content in data.items():
            counts = {label: len(re.findall(pattern, content.decode("utf-8")))
                      for label, pattern in PATTERNS.items()}
            privacy[str(relative / name)] = counts
            if any(counts.values()):
                raise ValueError("potential sensitive value; original retained privately: " + str(original / name))
            before = digest(content)
            original_hashes[str(original / name)] = before
            (destination / name).write_bytes(content)
            copied_hashes[str(relative / name)] = {"sha256": before, "bytes": len(content),
                "original_path": str(original / name), "raw_bytes_unchanged": True}
        summary, worker = json.loads(data["summary.json"]), json.loads(data["worker-result.json"])
        assert summary["code_commit"] == commit
        assert digest(data["unittest.txt"]) == summary["test_log_sha256"]
        for key, value in worker.items():
            assert summary[key] == value
        before, after = summary["source_sha256"], summary["source_sha256_after"]
        expected = git_source(commit)
        assert before == after == expected
        assert summary["source_unchanged"] and summary["tracked_source_clean_before"] and summary["tracked_source_clean_after"]
        log = data["unittest.txt"].decode("utf-8")
        failures, errors = re.findall(r"^FAIL: (.+)$", log, re.M), re.findall(r"^ERROR: (.+)$", log, re.M)
        footer = re.findall(r"^Ran (\d+) tests? in ([0-9.]+)s$", log, re.M)[-1]
        assert int(footer[0]) == summary["tests_run"]
        assert len(failures) == summary["failures"] and len(errors) == summary["errors"]
        expected_pass = (worker["unittest_passed"] and summary["worker_exit_code"] == 0
            and summary["source_unchanged"] and summary["tracked_source_clean_before"]
            and summary["tracked_source_clean_after"])
        assert summary["passed"] is expected_pass
        # Raw original manifests stay in summary.json. These sidecars are
        # explicitly derived value copies with new serialization, not raw files.
        for stage, field in (("before", "source_sha256"), ("after", "source_sha256_after")):
            write_json(destination / ("source-manifest-" + stage + ".json"), {
                "derived": True, "source_commit": commit,
                "original_summary": "summary.json", "json_pointer": "/" + field,
                "source_sha256": summary[field]})
        runs.append({"origin": origin, "source_commit": commit, "original_directory": str(original),
            "archived_directory": str(relative), "python": summary["python"], "sqlite": summary["sqlite"],
            "command_argv": summary["command_argv"], "tests_run": summary["tests_run"],
            "failures": summary["failures"], "errors": summary["errors"], "skipped": summary["skipped"],
            "worker_exit_code": summary["worker_exit_code"], "recorded_qa_passed": summary["passed"],
            "qa_disposition": "PASS" if summary["passed"] else "NO-GO",
            "duration_seconds": summary["duration_seconds"], "raw_unittest_seconds": float(footer[1]),
            "failed_tests": failures, "error_tests": errors,
            "source_manifest_count": len(before), "source_manifests_equal_and_match_git": True,
            "raw_log_sha256_matches_summary": True, "worker_matches_summary": True,
            "production_approved": False})

    for label, commit in COMMITS.items():
        for runtime in RUNTIMES:
            collect(args.local_root / label / runtime, Path("local") / label / runtime,
                    commit, "local_full_unittest")
    collect(args.ci_root, Path("ci") / "4608ffe-push-python310", COMMITS["4608ffe"], "ci_push_artifact")
    archive_path = args.ci_root / "artifact.zip"
    archive_data = archive_path.read_bytes()
    original_hashes[str(archive_path)] = digest(archive_data)
    members = []
    with zipfile.ZipFile(io.BytesIO(archive_data)) as archive:
        assert set(archive.namelist()) == set(RAW_FILES) and len(archive.namelist()) == len(RAW_FILES)
        for name in archive.namelist():
            content = archive.read(name)
            assert content == (args.ci_root / name).read_bytes()
            members.append({"name": name, "bytes": len(content), "sha256": digest(content),
                            "matches_archived_raw_bytes": True})
    zip_record = {"original_path": str(archive_path), "bytes": len(archive_data),
        "sha256": digest(archive_data), "members": members, "zip_binary_committed": False,
        "reason": "all three exact original members are archived separately; original ZIP retained at its existing path"}
    write_json(output / "ci-artifact-digest.json", zip_record)
    original_unchanged = all(digest(Path(name).read_bytes()) == value for name, value in original_hashes.items())
    copied_exact = all(digest((output / name).read_bytes()) == value["sha256"]
                       for name, value in copied_hashes.items())
    assert original_unchanged and copied_exact
    sources = {commit: {"local_matrix_passed": all(run["recorded_qa_passed"] for run in runs
                            if run["source_commit"] == commit and run["origin"] == "local_full_unittest"),
                        "all_archived_qa_passed": all(run["recorded_qa_passed"] for run in runs if run["source_commit"] == commit),
                        "qa_disposition": "PASS" if all(run["recorded_qa_passed"] for run in runs if run["source_commit"] == commit) else "NO-GO",
                        "production_approved": False} for commit in COMMITS.values()}
    write_json(output / "index.json", {"scope": "historical local full-QA records plus original CI failure artifact",
        "runs": runs, "sources": sources, "raw_files": copied_hashes,
        "package_pass_used_as_qa": False, "qa_failures_reinterpreted": False,
        "qa_4608ffe": "NO-GO", "production_approved": False})
    write_json(output / "privacy-check.json", {"scope": "named secret/value and query-URL pattern review of raw files; no download metadata included",
        "files": privacy, "matching_values_published": False, "all_counts_zero": True})
    write_json(output / "integrity-check.json", {"scope": "archive integrity only; this is not a QA rerun or product qualification",
        "raw_file_count": len(copied_hashes), "local_run_count": 9, "ci_run_count": 1,
        "derived_source_manifest_count": 2 * len(runs), "original_files_unchanged": original_unchanged,
        "raw_copies_byte_exact": copied_exact, "source_manifests_match_each_frozen_git_tree": True,
        "summary_worker_and_raw_log_agree": True, "zip_members_match_raw_files": True,
        "zip_binary_committed": False, "qa_rerun": False, "passed": True, "production_approved": False})
    print(json.dumps({"raw_files_archived": len(copied_hashes), "runs": len(runs),
        "original_files_unchanged": original_unchanged, "qa_4608ffe": "NO-GO",
        "archive_integrity_passed": True, "qa_rerun": False, "production_approved": False}, indent=2))


if __name__ == "__main__":
    main()
