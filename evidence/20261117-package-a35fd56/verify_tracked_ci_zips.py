"""Verify every tracked CI ZIP with explicit provenance and actual omissions.

The provenance map describes historical evidence, never the current release's
QA result. Missing new provenance fails closed. Negative archives remain
outside the report tree and are never installed.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "manifest", "wheel", "sdist", "unpacked-source", "provenance", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    manifest = json.loads(args.manifest.read_text())
    provenance = json.loads(args.provenance.read_text())
    assert manifest["passed"] and output != source
    tracked = sorted(name for name in manifest["sdist_required_files"] if name.endswith(".zip"))
    assert tracked and tracked == sorted(provenance), "every tracked ZIP requires explicit historical provenance"
    output.mkdir(parents=True, exist_ok=False)
    positive_hashes = {str(path): sha256(path.read_bytes()).hexdigest() for path in (args.wheel, args.sdist)}
    inclusions, controls = [], []
    with tarfile.open(args.sdist) as archive:
        prefix = archive.getmembers()[0].name.split("/")[0] + "/"
        for name in tracked:
            expected = provenance[name]
            original = (source / name).read_bytes()
            assert original == archive.extractfile(prefix + name).read() == (args.unpacked_source / name).read_bytes()
            assert sha256(original).hexdigest() == expected["sha256"]
            with zipfile.ZipFile(io.BytesIO(original)) as ci:
                assert len(ci.namelist()) == len(set(ci.namelist())) == 3
                assert set(ci.namelist()) == {"summary.json", "unittest.txt", "worker-result.json"}
                data = {member: ci.read(member) for member in ci.namelist()}
            summary = json.loads(data["summary.json"])
            worker = json.loads(data["worker-result.json"])
            assert summary["code_commit"] == expected["recorded_code_commit"]
            assert summary["source_sha256"] == summary["source_sha256_after"]
            assert summary["source_sha256"] and summary["source_unchanged"]
            assert sha256(data["unittest.txt"]).hexdigest() == summary["test_log_sha256"]
            for key in ("tests_run", "failures", "errors", "skipped", "unittest_passed"):
                assert worker[key] == summary[key]
            selected = summary["source_sha256"]
            frozen = subprocess.check_output(["git", "archive", "--format=tar",
                expected["reference_commit"], *sorted(selected)], cwd=source)
            with tarfile.open(fileobj=io.BytesIO(frozen)) as reference:
                actual = {item.name: sha256(reference.extractfile(item).read()).hexdigest()
                          for item in reference.getmembers() if item.isfile()}
            assert actual == selected
            members = []
            for member, content in sorted(data.items()):
                sibling = (source / name).parent / member
                if sibling.exists():
                    assert sibling.read_bytes() == content
                members.append({"name": member, "bytes": len(content), "sha256": sha256(content).hexdigest(),
                                "tracked_raw_sibling_present_and_exact": sibling.exists()})
            inclusions.append({"tracked_path": name, "sha256": sha256(original).hexdigest(),
                "bytes": len(original), "source_sdist_unpacked_byte_exact": True, "members": members,
                "provenance": expected, "recorded_source_file_count": len(selected),
                "source_hashes_match_reference_commit": True,
                "historical_ci": {key: summary[key] for key in
                    ("code_commit", "tests_run", "failures", "errors", "skipped", "passed")},
                "historical_ci_is_current_release_qualification": False})
    for index, name in enumerate(tracked):
        case = "zip-" + str(index)
        negative = output / (case + "-omitted.tar.gz")
        removed = 0
        with tarfile.open(args.sdist) as original, tarfile.open(negative, "w:gz") as target:
            prefix = original.getmembers()[0].name.split("/")[0] + "/"
            for member in original.getmembers():
                if member.name == prefix + name:
                    removed += 1
                else:
                    target.addfile(member, original.extractfile(member) if member.isfile() else None)
        assert removed == 1
        path = output / (case + "-report.json")
        argv = [sys.executable, str(source / "tools/verify_release_archives.py"),
            "--source", str(source), "--commit", manifest["source_commit"],
            "--wheel", str(args.wheel.resolve()), "--sdist", str(negative), "--output", str(path)]
        completed = subprocess.run(argv, cwd=Path.cwd(), capture_output=True, text=True)
        (output / (case + ".stdout.txt")).write_text(completed.stdout)
        (output / (case + ".stderr.txt")).write_text(completed.stderr)
        report = json.loads(path.read_text())
        passed = (completed.returncode == 1 and report["passed"] is False
            and report["sdist_missing"] == [name] and report["sdist_mismatched"] == []
            and report["checks"]["sdist_required_files_exact"] is False
            and all(value for key, value in report["checks"].items() if key != "sdist_required_files_exact")
            and report["runtime_files"] == manifest["runtime_files"])
        controls.append({"removed_member": name, "removed_count": removed,
            "negative_archive_sha256": sha256(negative.read_bytes()).hexdigest(),
            "argv": argv, "cwd": str(Path.cwd()), "returncode": completed.returncode,
            "checks": report["checks"], "sdist_missing": report["sdist_missing"],
            "unchanged_positive_wheel_and_runtime_maps": True, "passed": passed})
        assert passed
    assert positive_hashes == {str(path): sha256(path.read_bytes()).hexdigest() for path in (args.wheel, args.sdist)}
    report = {"source_commit": manifest["source_commit"], "scope": "all tracked historical CI ZIPs; new actual artifact inclusion and omission checks",
        "inclusions": inclusions, "omission_controls": controls,
        "provenance_sha256": sha256(args.provenance.read_bytes()).hexdigest(),
        "helper_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "historical_results_preserved": True, "positive_artifacts_unchanged": True,
        "negative_artifacts_installed": False, "passed": True, "production_approved": False}
    (output / "tracked-ci-zips.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"tracked_zips": len(tracked), "actual_omission_controls": len(controls),
        "historical_ci_passed": [item["historical_ci"]["passed"] for item in inclusions],
        "passed": True, "production_approved": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
