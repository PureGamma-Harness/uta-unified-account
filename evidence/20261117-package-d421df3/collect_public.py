"""Copy an explicit safe allowlist; never publish release/private binaries."""
from datetime import datetime, timezone
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path
import platform
import re
import shutil
import sqlite3
import subprocess
import sys

ROOT = Path("/workspace/uta-package-d421df3")
SOURCE = Path("/workspace/uta-observer-freeze-d421df3")
WORK = Path("/tmp/uta-release-d421df3-yy2hmth8")
COMMIT = "d421df3fc5123e8267f0eecf8bb5efdc37cd0dc6"
DEST = ROOT / "evidence/20261117-package-d421df3"


def identity(path):
    return {"sha256": sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}


def main():
    DEST.mkdir(parents=True, exist_ok=False)
    execution = json.loads((ROOT / "raw/execution.json").read_text())
    manifest = json.loads((WORK / "artifact-manifest.json").read_text())
    strict = json.loads((ROOT / "strict-control-bindings.json").read_text())
    assert manifest["source_commit"] == COMMIT and manifest["passed"] is True and strict["passed"] is True
    mapping = {}
    def add(source, target):
        assert target not in mapping
        assert source.suffix in (".txt", ".json", ".py")
        mapping[target] = source
    for run in execution["runs"]:
        for stream in ("stdout", "stderr"):
            name = run["name"] + "." + stream + ".txt"
            add(ROOT / "raw" / name, "raw/" + name)
    for name in ("execution.json", "commands.txt"):
        add(ROOT / "raw" / name, "raw/" + name)
    for name in ("ci-zip-provenance.json", "tracked-zip-execution.json", "tracked-zip.stdout.txt", "tracked-zip.stderr.txt",
                 "strict-control-bindings.json", "strict-control-bindings.stdout.txt", "strict-control-bindings.stderr.txt",
                 "source-proof.json", "runtime-comparison-bb34b5f.json", "verify_control_bindings.py", "collect_public.py"):
        add(ROOT / name, name)
    for name in ("strict-control-bindings.stdout.txt", "strict-control-bindings.stderr.txt", "verify_control_bindings.py.txt"):
        add(ROOT / "strict-first-attempt" / name, "strict-first-attempt/" + name)
    add(Path("/workspace/run_package_d421df3.py"), "execution-driver.py")
    add(Path("/workspace/uta-package-d421df3-driver.stdout.txt"), "driver.stdout.txt")
    add(Path("/workspace/uta-package-d421df3-driver.stderr.txt"), "driver.stderr.txt")
    add(WORK / "artifact-manifest.json", "artifact-manifest.json")
    for name in ("installed-report.json", "installed-cli-tests.txt"):
        add(WORK / "external/installed" / name, "installed/" + name)
    for command in ("uta-durable---help", "uta-ops---help", "uta-demo", "uta-acceptance", "uta-scenario",
                    "uta-durable-init", "uta-durable-inspect", "uta-durable-status"):
        for stream in ("stdout", "stderr"):
            name = command + "." + stream + ".txt"
            add(WORK / "external/installed" / name, "installed/" + name)
    for name in ("installed-views-report.json", "installed-view-tests.txt"):
        add(WORK / "external/installed-views" / name, "installed-views/" + name)
    for name in ("controls.json", "wheel-report.json", "sdist-report.json", "wheel.stdout.txt", "wheel.stderr.txt",
                 "sdist.stdout.txt", "sdist.stderr.txt"):
        add(WORK / "runtime-omission-controls" / name, "runtime-omission-controls/" + name)
    add(WORK / "tracked-ci-zip-checks/tracked-ci-zips.json", "tracked-ci-zip-checks/tracked-ci-zips.json")
    for index in range(8):
        for suffix in ("-report.json", ".stdout.txt", ".stderr.txt"):
            name = "zip-" + str(index) + suffix
            add(WORK / "tracked-ci-zip-checks" / name, "tracked-ci-zip-checks/" + name)
    forbidden = (rb"-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?(?:PRIVATE KEY|CERTIFICATE)-----",
                 rb"https?://[^\s\"<>]+[?&](?:sig|signature|token|access_token)=",
                 rb"(?im)^Authorization:\s*(?:Bearer|Basic)\s+\S+")
    copied = {}
    for name, original in sorted(mapping.items()):
        data = original.read_bytes()
        data.decode("utf-8")
        assert not any(re.search(pattern, data) for pattern in forbidden), "private material: " + name
        target = DEST / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)
        assert target.read_bytes() == data
        copied[name] = {"original_path": str(original), **identity(target)}
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=SOURCE, text=True).strip()
    status = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=all"], cwd=SOURCE, text=True)
    assert head == COMMIT and status == ""
    environment = {"recorded_utc": datetime.now(timezone.utc).isoformat(), "python": sys.version,
                   "sqlite": sqlite3.sqlite_version, "setuptools": importlib.metadata.version("setuptools"),
                   "wheel": importlib.metadata.version("wheel"), "platform": platform.platform(),
                   "execution_affinity": [2], "cohosted": True, "exclusive_host_or_cpuset": False,
                   "dependency_downloads": 0, "source_commit": head, "final_source_status": status,
                   "source_directory": str(SOURCE), "private_work_directory": str(WORK),
                   "build_source_has_git": (WORK / "build-source/.git").exists(),
                   "unpacked_source_has_git": (WORK / "sdist-unpacked/uta_reference_exchange-0.5.0a1/.git").exists()}
    (DEST / "environment.json").write_text(json.dumps(environment, indent=2, sort_keys=True) + "\n")
    verdict = {"source_commit": COMMIT, "version": manifest["version"], "artifacts": manifest["artifacts"],
               "tracked_source_files_exact": 2753, "dynamic_runtime_files_exact": 52,
               "runtime_tree_sha256": manifest["runtime_tree_sha256"], "positive_archive_complete_seven_checks": manifest["checks"],
               "fresh_installed_tests": {"run": 8, "failures": 0, "errors": 0, "skipped": 0},
               "fresh_console_commands": {"run": 8, "failed": 0},
               "fresh_installed_views": {"run": 3, "failures": 0, "errors": 0, "skipped": 0},
               "no_git_sdist_tests": {"legacy": 7, "archived_profile": 1, "release_verifier": 19, "failed": 0, "skipped": 0},
               "actual_runtime_omission_controls": 2, "actual_tracked_ci_zip_omission_controls": 8,
               "independent_actual_bytes_and_complete_checks_review_passed": strict["passed"],
               "package_scope_passed": True, "historical_bb34_full_QA": "NO_GO",
               "this_report_qualifies_full_QA_or_CI": False, "new_smoke_or_long_run_executed": False,
               "capacity_10000_per_second_qualified": False, "HA_qualified": False,
               "real_funds_qualified": False, "production_approved": False,
               "negative_artifacts_installed": False, "private_binary_material_published": False}
    (DEST / "package-verdict.json").write_text(json.dumps(verdict, indent=2, sort_keys=True) + "\n")
    allowlist = {"source_commit": COMMIT, "copied_files": copied, "copied_original_bytes_unchanged": True,
                 "policy": "explicit text/JSON/Python allowlist; no recursive private-tree copy; release/negative archives, CI ZIP binaries, auth/TLS files and financial databases remain external",
                 "content_screening_passed": True, "production_approved": False}
    (DEST / "public-allowlist.json").write_text(json.dumps(allowlist, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"public_files_copied": len(copied), "destination": str(DEST), "package_scope_passed": True}, sort_keys=True))


if __name__ == "__main__":
    main()
