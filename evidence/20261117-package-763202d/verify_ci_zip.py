"""Check the historical CI ZIP's exact sdist bytes and a real omission control."""
import argparse
from hashlib import sha256
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import zipfile


REFERENCE = "7ae94eb8a783f8e134ac90c11a713df7bb02d5f1"
CI_ZIP_SHA256 = "097dd0d4e266d82a85404c32c9e9c6ec8ea19c7bd8817831b76a6c4b44893bdf"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--sdist", type=Path, required=True)
    parser.add_argument("--unpacked-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    manifest = json.loads(args.manifest.read_text())
    assert manifest["passed"]
    tracked_zips = [name for name in manifest["sdist_required_files"] if name.endswith(".zip")]
    assert tracked_zips == ["evidence/runs/startup-producer-fixture/original-ci/artifact.zip"]
    output.mkdir(parents=True, exist_ok=False)
    records = []
    with tarfile.open(args.sdist) as archive:
        prefix = archive.getmembers()[0].name.split("/")[0] + "/"
        for name in tracked_zips:
            original = (source / name).read_bytes()
            embedded = archive.extractfile(prefix + name).read()
            unpacked = (args.unpacked_source / name).read_bytes()
            assert original == embedded == unpacked
            digest = sha256(original).hexdigest()
            assert digest == CI_ZIP_SHA256
            with zipfile.ZipFile(io.BytesIO(embedded)) as ci:
                assert set(ci.namelist()) == {"summary.json", "unittest.txt", "worker-result.json"}
                members = []
                for member in ci.namelist():
                    data = ci.read(member)
                    assert data == (source / name).parent.joinpath(member).read_bytes()
                    members.append({"name": member, "bytes": len(data),
                                    "sha256": sha256(data).hexdigest(), "raw_sibling_exact": True})
                summary = json.loads(ci.read("summary.json"))
            # The historical CI records a PR merge commit. Verify the recorded
            # source hashes against 7ae separately; never relabel it as 763 HEAD.
            selected = summary["source_sha256"]
            assert selected == summary["source_sha256_after"]
            source_tar = subprocess.check_output(
                ["git", "archive", "--format=tar", REFERENCE, *sorted(selected)], cwd=source)
            with tarfile.open(fileobj=io.BytesIO(source_tar)) as tree:
                expected = {item.name: sha256(tree.extractfile(item).read()).hexdigest()
                            for item in tree.getmembers() if item.isfile()}
            assert selected == expected
            records.append({"tracked_path": name, "bytes": len(original), "sha256": digest,
                "sdist_member": prefix + name, "source_sdist_unpacked_byte_exact": True,
                "members": members, "historical_ci": {key: summary[key] for key in
                    ("code_commit", "tests_run", "failures", "errors", "skipped", "passed")},
                "historical_reference_commit": REFERENCE,
                "recorded_source_hashes_match_reference": True,
                "historical_ci_is_current_package_source": False})
    write_path = output / "zip-inclusion.json"
    write_path.write_text(json.dumps({"source_commit": manifest["source_commit"],
        "scope": "exact tracked historical ZIP bytes in sdist; no CI result requalification",
        "records": records, "passed": True, "production_approved": False}, indent=2, sort_keys=True) + "\n")

    missing = tracked_zips[0]
    negative = output / "negative-missing-ci-zip.tar.gz"
    removed = 0
    with tarfile.open(args.sdist) as original, tarfile.open(negative, "w:gz") as target:
        prefix = original.getmembers()[0].name.split("/")[0] + "/"
        for item in original.getmembers():
            if item.name == prefix + missing:
                removed += 1
            else:
                target.addfile(item, original.extractfile(item) if item.isfile() else None)
    assert removed == 1
    report_path = output / "negative-zip-report.json"
    argv = [sys.executable, str(source / "tools/verify_release_archives.py"), "--source", str(source),
        "--commit", manifest["source_commit"], "--wheel", str(args.wheel.resolve()),
        "--sdist", str(negative), "--output", str(report_path)]
    result = subprocess.run(argv, cwd=Path.cwd(), capture_output=True, text=True)
    (output / "negative-zip.stdout.txt").write_text(result.stdout)
    (output / "negative-zip.stderr.txt").write_text(result.stderr)
    report = json.loads(report_path.read_text())
    passed = (result.returncode == 1 and report["passed"] is False
        and report["sdist_missing"] == [missing]
        and report["checks"]["sdist_required_files_exact"] is False
        and report["checks"]["wheel_runtime_exact"] and report["checks"]["sdist_runtime_exact"])
    control = {"source_commit": manifest["source_commit"], "case": "actual_sdist_missing_ci_zip_rejected",
        "removed_member": missing, "negative_archive_sha256": sha256(negative.read_bytes()).hexdigest(),
        "argv": argv, "cwd": str(Path.cwd()), "returncode": result.returncode,
        "checks": report["checks"], "sdist_missing": report["sdist_missing"],
        "passed": passed, "production_approved": False}
    (output / "zip-omission-control.json").write_text(json.dumps(control, indent=2, sort_keys=True) + "\n")
    assert passed
    print(json.dumps({"source_commit": manifest["source_commit"], "tracked_zip_count": len(records),
        "zip_sha256": records[0]["sha256"], "zip_in_sdist_exact": True,
        "zip_omission_control_passed": passed, "historical_ci_passed": records[0]["historical_ci"]["passed"],
        "production_approved": False}, indent=2))


if __name__ == "__main__":
    main()
