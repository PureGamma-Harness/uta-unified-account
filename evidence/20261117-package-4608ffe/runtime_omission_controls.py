"""Copy actual release archives and prove a new runtime omission is rejected.

Only independent negative archives are written. They are never installed and no
financial test is executed. Keep the complete positive artifacts unchanged.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--sdist", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    manifest = json.loads(args.manifest.read_text())
    missing = "uta/failure_diagnostics.py"
    assert manifest["passed"] and missing in manifest["runtime_files"]
    output.mkdir(parents=True, exist_ok=False)
    cases = []
    for kind in ("wheel", "sdist"):
        negative = output / ("missing-failure-diagnostics.whl" if kind == "wheel"
                             else "missing-failure-diagnostics.tar.gz")
        removed = 0
        if kind == "wheel":
            with zipfile.ZipFile(args.wheel) as original, zipfile.ZipFile(negative, "w") as target:
                for item in original.infolist():
                    if item.filename == missing:
                        removed += 1
                    else:
                        target.writestr(item, original.read(item.filename))
        else:
            with tarfile.open(args.sdist) as original, tarfile.open(negative, "w:gz") as target:
                prefix = original.getmembers()[0].name.split("/")[0] + "/"
                for item in original.getmembers():
                    if item.name == prefix + missing:
                        removed += 1
                    else:
                        target.addfile(item, original.extractfile(item) if item.isfile() else None)
        assert removed == 1
        report_path = output / (kind + "-report.json")
        argv = [sys.executable, str(source / "tools/verify_release_archives.py"),
            "--source", str(source), "--commit", manifest["source_commit"],
            "--wheel", str(negative if kind == "wheel" else args.wheel.resolve()),
            "--sdist", str(negative if kind == "sdist" else args.sdist.resolve()),
            "--output", str(report_path)]
        result = subprocess.run(argv, cwd=Path.cwd(), capture_output=True, text=True)
        (output / (kind + ".stdout.txt")).write_text(result.stdout)
        (output / (kind + ".stderr.txt")).write_text(result.stderr)
        report = json.loads(report_path.read_text())
        expected = (report["checks"]["wheel_runtime_exact"] is False) if kind == "wheel" else (
            report["checks"]["sdist_runtime_exact"] is False
            and report["checks"]["sdist_required_files_exact"] is False
            and report["sdist_missing"] == [missing])
        passed = result.returncode == 1 and report["passed"] is False and expected
        cases.append({"case": kind + "_missing_new_failure_diagnostics_is_rejected",
            "source_commit": manifest["source_commit"], "removed_member": missing,
            "removed_count": removed, "negative_archive_sha256": sha256(negative.read_bytes()).hexdigest(),
            "argv": argv, "cwd": str(Path.cwd()), "returncode": result.returncode,
            "checks": report["checks"], "sdist_missing": report["sdist_missing"], "passed": passed})
        assert passed
    controls = {"cases": cases, "source_commit": manifest["source_commit"],
        "scope": "actual new runtime omission controls only", "functional_tests_executed": 0,
        "negative_artifacts_installed": False, "passed": all(case["passed"] for case in cases),
        "production_approved": False}
    (output / "controls.json").write_text(json.dumps(controls, indent=2, sort_keys=True) + "\n")
    print(json.dumps(controls, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
