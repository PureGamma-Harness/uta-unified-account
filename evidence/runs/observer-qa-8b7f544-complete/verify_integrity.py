"""Read-only integrity verification of the failed 8b qualification evidence.

No test rerun, SQL connection, credentials, or temporary download URL is used.
The optional original ZIP directory is private local transport evidence; the
committed raw members remain sufficient for source/result verification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile


SOURCE = "8b7f544fcbdfd540d43de1d6560022c6ebbd3799"
MERGE = "5cdc9b5abbd6ad86fb031512890d7b685219f8a6"
MEMBERS = {"summary.json", "worker-result.json", "unittest.txt"}
HERE = Path(__file__).resolve().parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


def checked_summary(folder, frozen, expected_commit, expected_errors):
    summary = json.loads((folder / "summary.json").read_bytes())
    worker = json.loads((folder / "worker-result.json").read_bytes())
    assert summary["code_commit"] == expected_commit
    for key, expected in (("tests_run", 1472), ("failures", 1),
                          ("errors", expected_errors), ("skipped", 0),
                          ("passed", False), ("unittest_passed", False),
                          ("worker_exit_code", 1), ("source_unchanged", True),
                          ("tracked_source_clean_before", True),
                          ("tracked_source_clean_after", True)):
        assert summary[key] == expected, (folder, key)
    for key in ("tests_run", "failures", "errors", "skipped", "unittest_passed"):
        assert worker[key] == summary[key], (folder, key)
    hashes = summary["source_sha256"]
    assert len(hashes) == 263
    for relative, expected in hashes.items():
        path = Path(relative)
        assert not path.is_absolute() and ".." not in path.parts
        assert digest((frozen / path).read_bytes()) == expected, relative
    log = (folder / "unittest.txt").read_text()
    assert "FAILED (failures=1" in log
    assert "test_all_original_microcases_recompute_without_runtime_import" in log
    assert "assert environment['generator_sha256']==file_digest(ROOT/'benchmarks/run_managed_benchmark.py')" in log
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen-source", type=Path, required=True)
    parser.add_argument("--original-zip-root", type=Path)
    args = parser.parse_args()
    frozen = args.frozen_source.resolve()
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=frozen, text=True).strip() == SOURCE
    assert subprocess.check_output(["git", "status", "--porcelain"], cwd=frozen, text=True) == ""
    manifest = json.loads((HERE / "integrity-manifest.json").read_bytes())
    source_map = None
    for artifact in manifest["artifacts"]:
        folder = HERE / artifact["captured_directory"]
        summary = checked_summary(folder, frozen, artifact["recorded_code_commit"], artifact["errors"])
        if source_map is None:
            source_map = summary["source_sha256"]
        assert summary["source_sha256"] == source_map
        for member in artifact["members"]:
            data = (folder / member["name"]).read_bytes()
            assert len(data) == member["bytes"] and digest(data) == member["sha256"]
        if args.original_zip_root:
            archive = args.original_zip_root / ("artifact-" + str(artifact["id"]) + ".zip")
            data = archive.read_bytes()
            assert len(data) == artifact["provider_bytes"]
            assert digest(data) == artifact["provider_sha256"]
            with zipfile.ZipFile(archive) as zipped:
                assert zipped.testzip() is None
                assert set(zipped.namelist()) == MEMBERS and len(zipped.namelist()) == 3
                for name in MEMBERS:
                    assert zipped.read(name) == (folder / name).read_bytes()
    for item in manifest["local_runs"]:
        folder = HERE / item["captured_directory"]
        summary = checked_summary(folder, frozen, SOURCE, item["errors"])
        assert summary["source_sha256"] == source_map
    for item in manifest["captured_files"]:
        data = (HERE / item["path"]).read_bytes()
        assert len(data) == item["bytes"] and digest(data) == item["sha256"]
    merge = json.loads((HERE / "pr-merge-source.json").read_bytes())
    assert merge["sha"] == MERGE
    assert merge["parents"] == ["87e9f17359d5e67fd898abc31272ba5508a2c64d", SOURCE]
    tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=frozen, text=True).strip()
    assert merge["tree_sha"] == tree
    matrix = json.loads((HERE / "local/matrix-summary.json").read_bytes())
    assert matrix["source_commit"] == SOURCE
    assert matrix["source_clean_after"] and not matrix["all_exit_zero"]
    assert len(matrix["records"]) == 3 and all(x["exit_code"] == 1 for x in matrix["records"])
    assert digest((HERE / "local/execution-driver.py").read_bytes()) == matrix["launcher_sha256"]
    print(json.dumps({"integrity_passed": True, "ci_artifacts": 8,
                      "local_complete_runs": 3, "input_hashes_each": 263,
                      "original_zips_verified": args.original_zip_root is not None,
                      "qualification": "NO_GO", "tests_rerun": False,
                      "production_approved": False}, indent=2))


if __name__ == "__main__":
    main()
