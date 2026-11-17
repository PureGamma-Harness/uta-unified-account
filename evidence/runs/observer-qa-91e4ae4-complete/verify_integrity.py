"""Read-only original CI/source/package integrity checks; no acceptance rerun."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import zipfile


HERE = Path(__file__).resolve().parent
SOURCE = "91e4ae40b5e9b884c54026406299df5000c9c100"
MERGE = "d7f23cac215ede34a4aa8e20014ecfc418912830"
RUNTIME = "e6e06e44c1f7bb6e36fc614a5f03a679ba3b21efd1ba9a712584c6730f14a792"


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen-source", type=Path, required=True)
    parser.add_argument("--original-zip-root", type=Path)
    args = parser.parse_args()
    frozen = args.frozen_source.resolve()
    git = lambda *v: subprocess.check_output(["git", *v], cwd=frozen).decode().strip()
    assert git("rev-parse", "HEAD") == SOURCE and git("status", "--porcelain") == ""
    tracked = git("ls-files").splitlines()
    assert len(tracked) == 3633
    source_hashes = {name: sha((frozen / name).read_bytes()) for name in tracked}
    manifest = json.loads((HERE / "integrity-manifest.json").read_bytes())
    provider = json.loads((HERE / "provider-artifacts.json").read_bytes())
    provider_map = {a["id"]: a for a in provider}
    assert len(provider_map) == len(provider) == 22
    package_maps = {}
    input_map = None
    failed_jobs = 0
    for item in manifest["artifacts"]:
        original = provider_map[item["id"]]
        assert item["provider_bytes"] == original["size_in_bytes"]
        assert item["provider_sha256"] == original["digest"].split(":")[1]
        if item["captured_directory"] is None:
            continue
        folder = HERE / item["captured_directory"]
        for member in item["members"]:
            blob = (folder / member["name"]).read_bytes()
            assert len(blob) == member["bytes"] and sha(blob) == member["sha256"]
        expected_commit = SOURCE if item["run_id"] == 44104161669 else MERGE
        if "unit-validation" in item["name"]:
            summary = json.loads((folder / "summary.json").read_bytes())
            worker = json.loads((folder / "worker-result.json").read_bytes())
            assert summary["code_commit"] == expected_commit
            assert summary["tests_run"] == 1512 and summary["skipped"] == 0
            assert summary["source_unchanged"] is True
            assert summary["tracked_source_clean_before"] is True
            assert summary["tracked_source_clean_after"] is True
            assert len(summary["source_sha256"]) == 266
            if input_map is None:
                input_map = summary["source_sha256"]
            assert summary["source_sha256"] == input_map
            for path, expected in input_map.items():
                assert source_hashes[path] == expected
            expected_failure = item["id"] == 14337038689
            assert summary["failures"] == int(expected_failure) and summary["errors"] == 0
            assert summary["passed"] is (not expected_failure)
            assert summary["unittest_passed"] is (not expected_failure)
            assert summary["worker_exit_code"] == int(expected_failure)
            for key in ("tests_run", "failures", "errors", "skipped", "unittest_passed"):
                assert worker[key] == summary[key]
            failed_jobs += int(expected_failure)
            if expected_failure:
                log = (folder / "unittest.txt").read_text()
                assert "original bound PID did not exit within the unchanged five-second recovery horizon" in log
                assert "FAILED (failures=1)" in log
        elif "package-validation" in item["name"]:
            package = json.loads((folder / "uta-package-artifact-manifest.json").read_bytes())
            installed = json.loads((folder / "uta-installed-validation/installed-report.json").read_bytes())
            assert package["source_commit"] == installed["source_commit"] == expected_commit
            assert package["passed"] is True and installed["passed"] is True
            assert package["production_approved"] is False and installed["production_approved"] is False
            assert all(value is True for value in package["checks"].values())
            assert len(package["checks"]) == 7
            assert package["sdist_missing"] == package["sdist_mismatched"] == []
            assert set(package["sdist_required_files"]) == set(tracked)
            assert len(package["runtime_files"]) == 52
            assert package["runtime_tree_sha256"] == installed["runtime_tree_sha256"] == RUNTIME
            for path, expected in package["runtime_files"].items():
                assert source_hashes[path] == expected
            assert installed["tests"] == {"run": 8, "errors": 0, "failures": 0, "skipped": 0}
            assert installed["isolated"] is True and installed["pythonpath"] is None
            assert len(installed["commands"]) == 8
            assert all(command["returncode"] == 0 for command in installed["commands"])
            assert package["artifacts"] == installed["artifacts"]
            package_maps[(item["run_id"], item["name"].rsplit("-", 1)[1])] = package
    assert failed_jobs == 1 and len(package_maps) == 7
    verified_zip_count = 0
    verified_sdist_count = 0
    if args.original_zip_root:
        for item in manifest["artifacts"]:
            archive = args.original_zip_root / ("artifact-" + str(item["id"]) + ".zip")
            data = archive.read_bytes()
            assert len(data) == item["provider_bytes"] and sha(data) == item["provider_sha256"]
            with zipfile.ZipFile(archive) as zipped:
                assert zipped.testzip() is None
                assert len(zipped.namelist()) == len(item["members"])
                assert set(zipped.namelist()) == {m["name"] for m in item["members"]}
                for member in item["members"]:
                    blob = zipped.read(member["name"])
                    assert len(blob) == member["bytes"] and sha(blob) == member["sha256"]
                    if item["captured_directory"] is not None:
                        assert blob == (HERE / item["captured_directory"] / member["name"]).read_bytes()
                    else:
                        package = package_maps[(item["run_id"], item["name"].rsplit("-", 1)[1])]
                        expected = package["artifacts"][member["name"]]
                        assert len(blob) == expected["bytes"] and sha(blob) == expected["sha256"]
                        if member["name"].endswith(".whl"):
                            with zipfile.ZipFile(io.BytesIO(blob)) as wheel:
                                assert wheel.testzip() is None
                                for path, expected_hash in package["runtime_files"].items():
                                    assert sha(wheel.read(path)) == expected_hash
                        else:
                            with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as source:
                                files = {}
                                for entry in source:
                                    if entry.isfile():
                                        name = entry.name.split("/", 1)[1]
                                        assert name not in files
                                        files[name] = sha(source.extractfile(entry).read())
                                assert all(files.get(name) == digest for name, digest in source_hashes.items())
                            verified_sdist_count += 1
            verified_zip_count += 1
    proof = json.loads((HERE / "pr-merge-source.json").read_bytes())
    assert proof["sha"] == MERGE
    assert proof["parents"] == ["87e9f17359d5e67fd898abc31272ba5508a2c64d", SOURCE]
    assert proof["tree_sha"] == git("rev-parse", "HEAD^{tree}")
    jobs = [j for run in json.loads((HERE / "provider-jobs.json").read_bytes()) for j in run["jobs"]]
    assert len(jobs) == 8 and all(j["status"] == "completed" for j in jobs)
    assert sum(j["conclusion"] == "failure" for j in jobs) == 1
    assert sum(j["conclusion"] == "success" for j in jobs) == 7
    local_count = 0
    if manifest["local_status"] == "COMPLETE_ORIGINAL_MATRIX":
        matrix = json.loads((HERE / "local/matrix-summary.json").read_bytes())
        assert matrix["source_commit"] == SOURCE and matrix["source_clean_after"] is True
        assert [r["label"] for r in matrix["records"]] == ["python312", "python310", "python313-sqlite346"]
        assert len(manifest["local_runs"]) == 3
        assert sha((HERE / "local/execution-driver.py").read_bytes()) == matrix["launcher_sha256"]
        for item in manifest["local_runs"]:
            folder = HERE / "local" / item["label"]
            summary = json.loads((folder / "summary.json").read_bytes())
            worker = json.loads((folder / "worker-result.json").read_bytes())
            assert summary["code_commit"] == SOURCE
            assert summary["source_sha256"] == input_map
            assert summary["tests_run"] == 1512 and summary["skipped"] == 0
            assert summary["source_unchanged"] is True
            assert summary["tracked_source_clean_before"] is True
            assert summary["tracked_source_clean_after"] is True
            for key in ("tests_run", "failures", "errors", "skipped", "unittest_passed"):
                assert worker[key] == summary[key]
            for key in ("tests_run", "failures", "errors", "skipped", "passed", "worker_exit_code"):
                assert summary[key] == item[key]
            original = next(r for r in matrix["records"] if r["label"] == item["label"])
            assert original["exit_code"] == summary["worker_exit_code"]
            local_count += 1
        for item in manifest["local_files"]:
            data = (HERE / item["path"]).read_bytes()
            assert len(data) == item["bytes"] and sha(data) == item["sha256"]
    print(json.dumps({"integrity_passed": True, "unit_artifacts": 8,
                      "package_artifacts": 7, "wheel_artifacts": 7,
                      "original_zips_verified": verified_zip_count,
                      "sdists_each_3633_tracked_files_verified": verified_sdist_count,
                      "unit_input_hashes_each": 266,
                      "local_complete_runs": local_count,
                      "qualification": "NO_GO", "tests_rerun": False,
                      "production_approved": False}, indent=2))


if __name__ == "__main__":
    main()
