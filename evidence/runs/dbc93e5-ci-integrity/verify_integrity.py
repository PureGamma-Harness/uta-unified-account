"""Read-only original failed dbc CI integrity; reads Git blobs, not SQL.

This does not run tests or install/execute artifacts. No frozen worktree or
temporary download URL is required. Binary originals remain private.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import zipfile


HERE = Path(__file__).resolve().parent
SOURCE = "dbc93e5d50125e6ab8f1154511a537f8b1a8fa1b"
MERGE = "4c78b658714a6e0b6d235aca987f06966d2226f0"
PARENT = "91e4ae40b5e9b884c54026406299df5000c9c100"
RUNTIME_TREE = "ec0fa09e2e2e50557300423ddf6983969c9727816288ed79e9de7a17438c5b2b"


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def git_source(repo):
    tree = subprocess.check_output(["git", "ls-tree", "-rz", SOURCE], cwd=repo)
    objects = {}
    for line in tree.split(b"\0"):
        if not line:
            continue
        metadata, name = line.split(b"\t", 1)
        mode, kind, oid = metadata.split()
        assert kind == b"blob" and mode in (b"100644", b"100755")
        objects[name.decode()] = oid
    hashes = {}
    cache = {}
    batch = subprocess.Popen(["git", "cat-file", "--batch"], cwd=repo,
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    try:
        for name, oid in objects.items():
            if oid not in cache:
                batch.stdin.write(oid + b"\n")
                batch.stdin.flush()
                actual, kind, size = batch.stdout.readline().split()
                assert actual == oid and kind == b"blob"
                blob = batch.stdout.read(int(size))
                assert len(blob) == int(size) and batch.stdout.read(1) == b"\n"
                cache[oid] = digest(blob)
            hashes[name] = cache[oid]
    finally:
        batch.stdin.close()
        assert batch.wait(timeout=10) == 0
    return hashes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--git-repository", type=Path, required=True)
    parser.add_argument("--original-zip-root", type=Path)
    args = parser.parse_args()
    hashes = git_source(args.git_repository)
    assert len(hashes) == 5159
    runtime = {name: value for name, value in hashes.items() if name.startswith("uta/")}
    assert len(runtime) == 62
    assert digest(json.dumps(runtime, sort_keys=True, separators=(",", ":")).encode()) == RUNTIME_TREE
    manifest = json.loads((HERE / "integrity-manifest.json").read_bytes())
    provider = json.loads((HERE / "provider-artifacts.json").read_bytes())
    originals = {item["id"]: item for item in provider}
    assert len(originals) == len(provider) == 20
    packages = {}
    unit_count = 0
    source_map = None
    for item in manifest["artifacts"]:
        original = originals[item["id"]]
        assert item["provider_bytes"] == original["size_in_bytes"]
        assert item["provider_sha256"] == original["digest"].split(":")[1]
        if item["captured_directory"] is None:
            continue
        folder = HERE / item["captured_directory"]
        for member in item["members"]:
            data = (folder / member["name"]).read_bytes()
            assert len(data) == member["bytes"] and digest(data) == member["sha256"]
        expected_commit = SOURCE if item["run_id"] == 44125869999 else MERGE
        if "unit-validation" in item["name"]:
            summary = json.loads((folder / "summary.json").read_bytes())
            worker = json.loads((folder / "worker-result.json").read_bytes())
            assert summary["code_commit"] == expected_commit
            assert summary["tests_run"] == 1801
            bad = item["name"] == "uta-unit-validation-python-3.10"
            assert summary["failures"] == summary["skipped"] == 0
            assert summary["errors"] == (11 if bad else 0)
            assert summary["worker_exit_code"] == int(bad)
            assert summary["passed"] is (not bad)
            assert summary["unittest_passed"] is (not bad) and summary["source_unchanged"] is True
            assert summary["tracked_source_clean_before"] is True and summary["tracked_source_clean_after"] is True
            assert len(summary["source_sha256"]) == 348
            if source_map is None:
                source_map = summary["source_sha256"]
            assert summary["source_sha256"] == source_map
            assert all(hashes.get(name) == value for name, value in source_map.items())
            for key in ("tests_run", "failures", "errors", "skipped", "unittest_passed"):
                assert worker[key] == summary[key]
            unit_count += 1
        else:
            package = json.loads((folder / "uta-package-artifact-manifest.json").read_bytes())
            installed = json.loads((folder / "uta-installed-validation/installed-report.json").read_bytes())
            assert package["source_commit"] == installed["source_commit"] == expected_commit
            assert package["passed"] is True and installed["passed"] is True
            assert package["production_approved"] is False and installed["production_approved"] is False
            assert len(package["checks"]) == 7 and all(v is True for v in package["checks"].values())
            assert package["sdist_missing"] == package["sdist_mismatched"] == []
            assert set(package["sdist_required_files"]) == set(hashes)
            assert package["runtime_files"] == runtime
            assert package["runtime_tree_sha256"] == installed["runtime_tree_sha256"] == RUNTIME_TREE
            assert package["artifacts"] == installed["artifacts"]
            assert installed["tests"] == {"run": 8, "errors": 0, "failures": 0, "skipped": 0}
            assert installed["isolated"] is True and installed["pythonpath"] is None
            assert len(installed["commands"]) == 8 and all(c["returncode"] == 0 for c in installed["commands"])
            packages[(item["run_id"], item["name"].rsplit("-", 1)[1])] = package
    assert unit_count == 8 and len(packages) == 6
    zip_count = sdist_count = 0
    if args.original_zip_root:
        for item in manifest["artifacts"]:
            path = args.original_zip_root / ("artifact-" + str(item["id"]) + ".zip")
            data = path.read_bytes()
            assert len(data) == item["provider_bytes"] and digest(data) == item["provider_sha256"]
            with zipfile.ZipFile(path) as zipped:
                assert zipped.testzip() is None
                assert len(zipped.namelist()) == len(item["members"])
                assert set(zipped.namelist()) == {m["name"] for m in item["members"]}
                for member in item["members"]:
                    data = zipped.read(member["name"])
                    assert len(data) == member["bytes"] and digest(data) == member["sha256"]
                    if item["captured_directory"] is not None:
                        assert data == (HERE / item["captured_directory"] / member["name"]).read_bytes()
                        continue
                    package = packages[(item["run_id"], item["name"].rsplit("-", 1)[1])]
                    expected = package["artifacts"][member["name"]]
                    assert len(data) == expected["bytes"] and digest(data) == expected["sha256"]
                    if member["name"].endswith(".whl"):
                        with zipfile.ZipFile(io.BytesIO(data)) as wheel:
                            assert wheel.testzip() is None
                            assert all(digest(wheel.read(name)) == value for name, value in runtime.items())
                    else:
                        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as source:
                            contents = {}
                            for entry in source:
                                if entry.isfile():
                                    name = entry.name.split("/", 1)[1]
                                    assert name not in contents
                                    contents[name] = digest(source.extractfile(entry).read())
                            assert all(contents.get(name) == value for name, value in hashes.items())
                        sdist_count += 1
            zip_count += 1
    proof = json.loads((HERE / "pr-merge-source.json").read_bytes())
    assert proof["sha"] == MERGE and proof["parents"] == [PARENT, SOURCE]
    tree = subprocess.check_output(["git", "rev-parse", SOURCE + "^{tree}"], cwd=args.git_repository, text=True).strip()
    assert proof["tree_sha"] == tree
    jobs = [job for run in json.loads((HERE / "provider-jobs.json").read_bytes()) for job in run["jobs"]]
    assert len(jobs) == 8 and all(j["status"] == "completed" for j in jobs)
    assert sum(j["conclusion"] == "success" for j in jobs) == 6
    assert sum(j["conclusion"] == "failure" for j in jobs) == 2
    for job in jobs:
        if job["conclusion"] == "failure":
            assert job["name"] == "test (3.10)"
            failed = [step["name"] for step in job["steps"] if step["conclusion"] == "failure"]
            assert failed == ["Run unit tests"]
    print(json.dumps({"integrity_passed": True, "final_source_ci_passed": False,
                      "source_commit": SOURCE, "unit_artifacts": unit_count,
                      "tests_each": 1801, "input_hashes_each": 348,
                      "package_artifacts": len(packages), "original_zips_verified": zip_count,
                      "sdists_each_5159_tracked_files_verified": sdist_count,
                      "runtime_files": 62, "local_full_three_runs_collected_here": False,
                      "failed_python310_jobs": 2,
                      "overall_acceptance": "NO_GO", "tests_rerun": False,
                      "production_approved": False}, indent=2))


if __name__ == "__main__":
    main()
