"""Immutable file/Git/ZIP evidence checks only; no financial code or SQL."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

SOURCE = "6010e920a168b35fccfc9ef9ee34e030b28b11d9"
MERGE = "98d161640972627c3c39e55baf92a2eaf1406b59"
BASE = "e4396b4b1fd9c2e3a138e48a045feffe158705cc"
CORE = "ff814d4bcaee079b0e0503ea8072c24e3563c443"
TEST = "test_expired_sigstopped_shared_gate_owner_is_killed_so_publication_can_recover"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args])


def check(evidence, private):
    def record(name):
        return json.loads((evidence / name).read_bytes())

    provider = record("provider-jobs-artifacts-pr-safe.json")
    push_jobs, pr_jobs = provider["push_jobs"], provider["pr_jobs"]
    assert len(push_jobs) == len(pr_jobs) == 4
    assert sum(j["conclusion"] == "failure" for j in push_jobs) == 1
    assert all(j["conclusion"] == "success" for j in pr_jobs)
    failed = next(j for j in push_jobs if j["id"] == 134395997553)
    assert failed["name"] == "test (3.11)" and failed["conclusion"] == "failure"
    steps = {s["number"]: s for s in failed["steps"]}
    assert steps[5]["conclusion"] == "failure" and steps[6]["conclusion"] == "success"
    assert all(steps[n]["conclusion"] == "skipped" for n in range(7, 21))
    assert len(provider["push_artifacts"]) == 10 and len(provider["pr_artifacts"]) == 12
    assert not any("3.11" in a["name"] and "unit" not in a["name"] for a in provider["push_artifacts"])
    actual = {a["id"]: a for a in provider["push_artifacts"] + provider["pr_artifacts"]}
    reports = {}
    archive_results = []
    for artifact, prefix in ((14373841721, "push311"), (14374011525, "pr311")):
        path = private / ("artifact-" + str(artifact) + ".zip")
        data = path.read_bytes()
        assert len(data) == actual[artifact]["size_in_bytes"]
        assert "sha256:" + sha(data) == actual[artifact]["digest"]
        assert path.stat().st_mode & 0o777 == 0o600
        with zipfile.ZipFile(path) as z:
            assert z.testzip() is None and len(z.namelist()) == 3
            assert set(z.namelist()) == {"summary.json", "worker-result.json", "unittest.txt"}
            for name in ("summary.json", "worker-result.json"):
                assert z.read(name) == (evidence / (prefix + "-" + name)).read_bytes()
            summary = json.loads(z.read("summary.json"))
            assert sha(z.read("unittest.txt")) == summary["test_log_sha256"]
            if prefix == "push311":
                assert z.read("unittest.txt") == (evidence / "push311-unittest.txt").read_bytes()
        reports[prefix] = summary
        archive_results.append({"artifact_id": artifact, "bytes": len(data), "sha256": sha(data), "crc_pass": True})
    push, pr = reports["push311"], reports["pr311"]
    assert (push["code_commit"], push["tests_run"], push["failures"], push["errors"], push["skipped"], push["passed"]) == (SOURCE, 1830, 1, 0, 0, False)
    assert (pr["code_commit"], pr["tests_run"], pr["failures"], pr["errors"], pr["skipped"], pr["passed"]) == (MERGE, 1830, 0, 0, 0, True)
    assert push["source_unchanged"] and pr["source_unchanged"]
    assert push["source_sha256"] == push["source_sha256_after"] == pr["source_sha256"] == pr["source_sha256_after"]
    assert len(push["source_sha256"]) == 353
    for path, expected in push["source_sha256"].items():
        assert sha(git("show", SOURCE + ":" + path)) == expected
    identity = record("source-merge-commits-provider-safe.json")
    assert identity[MERGE]["parents"] == [BASE, SOURCE]
    assert identity[SOURCE]["tree_sha"] == identity[MERGE]["tree_sha"] == git("rev-parse", SOURCE + "^{tree}").decode().strip()
    runtime = git("ls-tree", "-r", SOURCE, "uta")
    assert runtime == git("ls-tree", "-r", CORE, "uta")
    runtime_count = sum(row.endswith(b".py") for row in runtime.splitlines())
    assert runtime_count == 61
    text = (evidence / "push311-unittest.txt").read_bytes()
    marker = b"UTA_EXPIRED_GATE_FAILURE_DIAGNOSTIC "
    assert text.count(marker) == 1
    start = text.index(marker) + len(marker)
    payload = text[start:text.index(b"\n", start)]
    assert payload == (evidence / "push311-failure-diagnostic.original-json-subsequence.json").read_bytes()
    diagnosis = json.loads(payload)
    assert diagnosis["phase"] == "before_original_cleanup"
    assert diagnosis["primary"][0]["type"] == "AssertionError"
    frames = diagnosis["primary"][0]["frames"]
    assert any(f["file"] == "tests.test_durable_faults" and f["function"] == TEST and f["line"] == 1456 for f in frames)
    assert diagnosis["observation"]["capture_attempts_count"] == diagnosis["observation"]["injection_undos_count"] == 1
    assert diagnosis["observation"]["last_capture"]["writer_availability_probe"] == {"available": False, "native_errorcode": 15}
    assert diagnosis["threads"]["monitor"]["alive"] is True and diagnosis["threads"]["monitor_stop"] is False
    assert diagnosis["threads"]["publisher"]["alive"] is None
    assert diagnosis["publisher_errors"] == []
    assert b"AssertionError: bound child did not leave SH after undo within original capture horizon" in text
    runs = record("runs-provider-safe.json")
    assert runs["44184136107"]["run_attempt"] == runs["44184574093"]["run_attempt"] == 1
    assert runs["44184136107"]["conclusion"] == "failure" and runs["44184574093"]["conclusion"] == "success"
    assert private.stat().st_mode & 0o777 == 0o700
    return {"status": "PASS_READ_ONLY_FIRST_FAILURE_EVIDENCE", "source": SOURCE, "actual_pr_merge": MERGE,
            "source_inputs_git_verified": 353, "runtime_files_identical_to_core_ff814": runtime_count,
            "original_archives_verified": archive_results, "provider_artifacts_metadata_only_total": 22,
            "all_22_binary_artifacts_verified": False, "push311": "1830/1FAIL/0ERROR", "pr311": "1830/PASS",
            "adjacent_safe_diagnostic_thread_stack_present": True, "root_cause_determined": False,
            "SQL_native_QA_reruns": 0, "production_approved": False, "overall": "NO_GO"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--private", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(check(Path(__file__).resolve().parent, args.private), sort_keys=True))
