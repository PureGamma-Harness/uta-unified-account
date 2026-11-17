"""Independent file-only package audit. Never import uta or execute its tools."""
import ast
import configparser
from datetime import datetime
from email.parser import BytesParser
from hashlib import sha1, sha256
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile
import tomllib
import zipfile

PIN = "dbc93e5d50125e6ab8f1154511a537f8b1a8fa1b"
SOURCE = Path("/workspace/uta-combined-freeze-dbc93e5")
AUTHOR = Path("/workspace/uta-package-dbc93e5/evidence/20261117-package-dbc93e5")
WORK = Path("/tmp/uta-release-dbc93e5-oor3dlj4")
OUT = Path(__file__).resolve().parent
KEYS = {"version", "wheel_runtime_exact", "sdist_runtime_exact", "sdist_required_files_exact",
        "legacy_fixture_pinned", "legacy_fixture_licensed", "entry_points"}


def sha(data):
    return sha256(data).hexdigest()


def identity(path):
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": sha(data)}


def read(path):
    return json.loads(path.read_text())


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=SOURCE)


def tar_members(path):
    items = {}
    with tarfile.open(path) as archive:
        for item in archive:
            assert item.name not in items
            assert item.isfile() or item.isdir()
            assert not item.name.startswith("/") and ".." not in Path(item.name).parts
            metadata = item.get_info()
            metadata["type"] = metadata["type"].hex()
            metadata["pax_headers"] = item.pax_headers
            metadata["sparse"] = item.sparse
            data = archive.extractfile(item).read() if item.isfile() else None
            items[item.name] = {"metadata": metadata, "sha256": sha(data) if data is not None else None}
    return items


def wheel_members(path):
    items = {}
    fields = ("date_time", "compress_type", "comment", "extra", "create_system", "create_version",
              "extract_version", "reserved", "flag_bits", "volume", "internal_attr", "external_attr",
              "CRC", "file_size", "compress_size")
    with zipfile.ZipFile(path) as archive:
        comment = archive.comment.hex()
        for item in archive.infolist():
            assert item.filename not in items
            metadata = {name: getattr(item, name) for name in fields}
            for name in ("comment", "extra"):
                metadata[name] = metadata[name].hex()
            items[item.filename] = {"metadata": metadata, "sha256": sha(archive.read(item))}
    return items, comment


def pure_omission(positive, negative, target):
    assert set(positive) - set(negative) == {target}
    assert not set(negative) - set(positive)
    assert list(negative) == [name for name in positive if name != target]
    assert all(positive[name] == negative[name] for name in negative)
    return {"removed_only": target, "remaining_members_exact": len(negative),
            "content_metadata_order_preserved": True, "added": [], "changed": []}


def source_and_artifacts():
    assert git("rev-parse", "HEAD").decode().strip() == PIN
    assert git("status", "--porcelain", "--untracked-files=all") == b""
    tree = git("ls-tree", "-r", "-z", PIN).split(b"\0")
    hashes = {}
    for entry in filter(None, tree):
        header, name = entry.split(b"\t", 1)
        mode, kind, object_id = header.split()
        assert mode in (b"100644", b"100755") and kind == b"blob"
        name = name.decode()
        data = (SOURCE / name).read_bytes()
        assert sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() == object_id.decode()
        hashes[name] = sha(data)
    assert len(hashes) == 5159
    runtime = {name: value for name, value in hashes.items() if name.startswith("uta/") and name.endswith((".py", ".html"))}
    assert len(runtime) == 62
    manifest = read(WORK / "artifact-manifest.json")
    assert manifest["source_commit"] == PIN and manifest["passed"] is True and manifest["production_approved"] is False
    assert set(manifest["checks"]) == KEYS and all(value is True for value in manifest["checks"].values())
    assert manifest["sdist_required_files"] == list(hashes)
    assert manifest["runtime_files"] == runtime and manifest["runtime_tree_sha256"] == sha(canonical(runtime))
    assert manifest["sdist_missing"] == manifest["sdist_mismatched"] == []
    wheel = WORK / "artifacts/uta_reference_exchange-0.5.0a1-py3-none-any.whl"
    sdist = WORK / "artifacts/uta_reference_exchange-0.5.0a1.tar.gz"
    artifacts = {path.name: identity(path) for path in (wheel, sdist)}
    assert manifest["artifacts"] == artifacts
    wi, comment = wheel_members(wheel)
    ti = tar_members(sdist)
    prefix = next(iter(ti)).split("/")[0] + "/"
    assert {name: value["sha256"] for name, value in wi.items() if name.startswith("uta/") and name.endswith((".py", ".html"))} == runtime
    assert {name: ti[prefix + name]["sha256"] for name in hashes} == hashes
    ga = tar_members(WORK / "frozen-source.tar.gz")
    assert {name: ga[name]["sha256"] for name in hashes} == hashes
    for path in (WORK / "build-source", WORK / "sdist-unpacked/uta_reference_exchange-0.5.0a1"):
        assert not (path / ".git").exists()
        assert {name: sha((path / name).read_bytes()) for name in hashes} == hashes
    project = tomllib.loads((SOURCE / "pyproject.toml").read_text())["project"]
    init = ast.parse((SOURCE / "uta/__init__.py").read_text())
    version = next(node.value.value for node in init.body if isinstance(node, ast.Assign))
    assert version == project["version"] == manifest["version"] == "0.5.0a1"
    with zipfile.ZipFile(wheel) as archive:
        metadata_name = next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
        metadata = BytesParser().parsebytes(archive.read(metadata_name))
        assert metadata.get_all("Version") == [version]
        entries = configparser.ConfigParser(interpolation=None)
        entries.read_string(archive.read(metadata_name.removesuffix("METADATA") + "entry_points.txt").decode())
        assert dict(entries["console_scripts"]) == project["scripts"]
    with tarfile.open(sdist) as archive:
        fixture = archive.extractfile(prefix + "tests/fixtures/legacy_ad3f5b8_uta.tar.gz").read()
        provenance = json.loads(archive.extractfile(prefix + "tests/fixtures/legacy_ad3f5b8_provenance.json").read())
        assert sha(fixture) == provenance["archive_sha256"]
        with tarfile.open(fileobj=io.BytesIO(fixture)) as historical:
            assert "LICENSE" in historical.getnames()
    return manifest, hashes, runtime, artifacts, wheel, sdist, wi, comment, ti, prefix


def execution_and_installed(manifest, runtime, artifacts):
    phases = {}
    for phase in ("core", "zip", "strict", "v2"):
        path = WORK / "raw" / ("execution.json" if phase == "core" else phase + "-execution.json")
        info = read(path)
        assert info["source_commit"] == PIN and info["source_directory"] == str(SOURCE)
        assert info["work_directory"] == str(WORK) and info["affinity"] == [2]
        assert info["environment"] == {"PYTHONPATH": None, "PYTHONDONTWRITEBYTECODE": "1"}
        assert info["driver_sha256"] == identity(AUTHOR / "execution_driver.py")["sha256"]
        for run in info["runs"]:
            assert run["returncode"] == 0 and not run.get("timed_out", False)
            assert run["seconds"] == (run["finished_monotonic_ns"] - run["started_monotonic_ns"]) / 1e9
            assert 0 <= run["seconds"] <= run["timeout_seconds"]
            assert datetime.fromisoformat(run["finished_utc"]) >= datetime.fromisoformat(run["started_utc"])
            for stream in ("stdout", "stderr"):
                record = run[stream]
                assert identity(Path(record["path"])) == {"bytes": record["bytes"], "sha256": record["sha256"]}
        phases[phase] = {"raw_execution": identity(path), "runs": info["runs"]}
    by_name = {run["name"]: run for data in phases.values() for run in data["runs"]}
    for name in ("installed-run", "installed-views-run", "installed-internal-v2"):
        argv = by_name[name]["argv"]
        assert argv[:2] == [str(WORK / "venv/bin/python"), "-I"]
        assert by_name[name]["cwd"] == str(WORK / "external")
        assert by_name[name]["seconds"] <= 60
    assert by_name["build"]["cwd"] == str(WORK / "build-source")
    assert by_name["install"]["argv"][-3:] == ["--no-deps", "--no-index", str(WORK / "artifacts/uta_reference_exchange-0.5.0a1-py3-none-any.whl")]
    installed = {}
    for label, rel, count in (("cli", "external/installed/installed-report.json", 8), ("views", "external/installed-views/installed-views-report.json", 3)):
        data = read(WORK / rel)
        assert data["tests"] == {"run": count, "failures": 0, "errors": 0, "skipped": 0}
        assert data["passed"] is True and data["production_approved"] is False
        assert data["source_commit"] == PIN and data["artifacts"] == artifacts
        assert data["runtime_tree_sha256"] == manifest["runtime_tree_sha256"]
        assert data["isolated"] is True and data["pythonpath"] is None
        site = Path(data["installed_site"])
        assert site == WORK / "venv/lib/python3.12/site-packages"
        assert all(Path(path).resolve().is_relative_to(site) for path in data["modules"].values())
        assert str(SOURCE) not in data["sys_path"] and str(WORK / "build-source") not in data["sys_path"]
        actual = {str(path.relative_to(site)): sha(path.read_bytes()) for path in (site / "uta").rglob("*")
                  if path.is_file() and path.suffix in (".py", ".html")}
        assert actual == runtime
        assert data["helper_sha256"] == data["copied_helper_sha256"]
        if label == "cli":
            assert len(data["commands"]) == 8 and all(x["returncode"] == 0 for x in data["commands"])
            assert data["helper_root_override"] == str(site)
            original, copied = SOURCE / "tests/test_durable_cli.py", WORK / "external/installed/frozen_test_durable_cli.py"
            assert sha(original.read_bytes()) == manifest["cli_helper_sha256"]
            for item in data["commands"]:
                assert Path(item["argv"][0]).parent == WORK / "venv/bin"
                parts = [Path(item["argv"][0]).name, *item["argv"][1:]]
                name = "-".join(parts[:2]) if parts[1] in ("init", "inspect", "status") else "-".join(parts)
                stdout = WORK / "external/installed" / (name + ".stdout.txt")
                stderr = WORK / "external/installed" / (name + ".stderr.txt")
                assert stdout.is_file() and stderr.is_file()
                if parts[:2] == ["uta", "acceptance"]:
                    acceptance = read(stdout)
                    assert acceptance["status"] == "passed" and acceptance["production_approved"] is False
        else:
            original, copied = SOURCE / "tests/test_durable_views.py", WORK / "external/installed-views/frozen_test_durable_views.py"
        assert original.read_bytes() == copied.read_bytes()
        assert data["helper_sha256"] == sha(original.read_bytes())
        installed[label] = {"tests": data["tests"], "all_loaded_module_paths_installed": True,
                            "loaded_modules": data["modules"], "all_62_runtime_bytes_exact": True}
        log = WORK / ("external/installed/installed-cli-tests.txt" if label == "cli" else "external/installed-views/installed-view-tests.txt")
        text = log.read_text()
        assert re.findall(r"Ran (\d+) tests? in ", text) == [str(count)] and text.rstrip().endswith("OK")
        if label == "cli":
            installed[label]["console_commands"] = data["commands"]
            installed[label]["console_cwd_from_frozen_helper"] = str(WORK / "external/installed")
            installed[label]["individual_console_walls_recorded"] = False
    counts = {"sdist-legacy-tests": 7, "sdist-archival-tests": 1, "sdist-release-verifier-tests": 19, "history-reference": 10}
    for name, count in counts.items():
        run = by_name[name]
        assert run["cwd"] == str(WORK / "sdist-unpacked/uta_reference_exchange-0.5.0a1")
        log = Path(run["stderr"]["path"]).read_text()
        assert re.findall(r"Ran (\d+) tests? in ", log) == [str(count)] and log.rstrip().endswith("OK")
        assert "skipped=" not in log and "FAILED" not in log
    return phases, installed, counts


def negative_controls(manifest, runtime, artifacts, wheel, sdist, wi, wheel_comment, ti, prefix):
    runtime_records = read(WORK / "runtime-omission-controls/controls.json")
    zip_records = read(WORK / "tracked-ci-zip-checks/tracked-ci-zips.json")
    provenance = read(AUTHOR / "ci-zip-provenance.json")
    tracked_zips = [name for name in manifest["sdist_required_files"] if name.endswith(".zip")]
    assert len(tracked_zips) == len(provenance) == len(zip_records["inclusions"]) == len(zip_records["omission_controls"]) == 11
    assert sorted(provenance) == tracked_zips and len(runtime_records["cases"]) == 2
    descriptions, history, cache = [], [], {}
    for kind, false in (("wheel", {"wheel_runtime_exact"}), ("sdist", {"sdist_runtime_exact", "sdist_required_files_exact"})):
        directory = WORK / "runtime-omission-controls"
        archive = directory / ("missing-failure-diagnostics.whl" if kind == "wheel" else "missing-failure-diagnostics.tar.gz")
        record = next(case for case in runtime_records["cases"] if case["case"].startswith(kind + "_"))
        descriptions.append((kind, "uta/failure_diagnostics.py", archive, directory / (kind + "-report.json"), false, record))
    for index, target in enumerate(tracked_zips):
        assert sha((SOURCE / target).read_bytes()) == provenance[target]["sha256"]
        with zipfile.ZipFile(SOURCE / target) as archived:
            summary = json.loads(archived.read("summary.json"))
            worker = json.loads(archived.read("worker-result.json"))
            log = archived.read("unittest.txt")
            assert summary["code_commit"] == provenance[target]["recorded_code_commit"]
            assert summary["passed"] is False and summary["unittest_passed"] is False
            assert summary["test_log_sha256"] == sha(log) and b"FAILED" in log
            assert all(summary[key] == worker[key] for key in worker)
            assert summary["source_sha256"] == summary["source_sha256_after"]
            for name, digest in summary["source_sha256"].items():
                key = (provenance[target]["reference_commit"], name)
                if key not in cache:
                    cache[key] = sha(git("show", key[0] + ":" + name))
                assert cache[key] == digest
            history.append({"path": target, "original_code_commit": summary["code_commit"],
                            "reference_commit": provenance[target]["reference_commit"], "source_hash_count": len(summary["source_sha256"]),
                            "source_hashes_match_reference": True, "tests_run": summary["tests_run"],
                            "failures": summary["failures"], "errors": summary["errors"], "passed": False,
                            "original_test_log_sha256": sha(log), "original_failure_retained": True})
        record = zip_records["omission_controls"][index]
        assert record["removed_member"] == target
        directory = WORK / "tracked-ci-zip-checks"
        descriptions.append(("sdist", target, directory / ("zip-" + str(index) + "-omitted.tar.gz"),
                             directory / ("zip-" + str(index) + "-report.json"), {"sdist_required_files_exact"}, record))
    result = []
    for kind, target, archive, report_path, false, record in descriptions:
        report = read(report_path)
        expected = {name: name not in false for name in KEYS}
        assert report["source_commit"] == PIN and report["checks"] == expected and record["checks"] == expected
        assert report["passed"] is False and report["production_approved"] is False
        assert record["returncode"] == 1 and record["passed"] is True and record["removed_count"] == 1
        assert report["runtime_files"] == runtime and report["runtime_tree_sha256"] == manifest["runtime_tree_sha256"]
        for field in ("version", "metadata_versions", "cli_helper_sha256", "legacy_fixture_provenance", "entry_points"):
            assert report[field] == manifest[field]
        assert report["sdist_required_files"] == manifest["sdist_required_files"] and report["sdist_mismatched"] == []
        assert report["sdist_missing"] == ([] if kind == "wheel" else [target])
        other = sdist if kind == "wheel" else wheel
        assert report["artifacts"] == {archive.name: identity(archive), other.name: artifacts[other.name]}
        assert identity(other) == artifacts[other.name]
        assert record["negative_archive_sha256"] == identity(archive)["sha256"]
        argv = record["argv"]
        assert argv[1] == str(SOURCE / "tools/verify_release_archives.py")
        for key, value in (("--source", SOURCE), ("--commit", PIN), ("--output", report_path), ("--" + kind, archive),
                           ("--" + ("sdist" if kind == "wheel" else "wheel"), other)):
            assert argv[argv.index(key) + 1] == str(value)
        stdout = read(report_path.with_name(report_path.name.removesuffix("-report.json") + ".stdout.txt"))
        assert stdout == {key: report[key] for key in ("source_commit", "runtime_tree_sha256", "checks", "sdist_missing", "passed")}
        if kind == "wheel":
            index, comment = wheel_members(archive)
            assert comment == wheel_comment
            delta = pure_omission(wi, index, target)
        else:
            delta = pure_omission(ti, tar_members(archive), prefix + target)
        result.append({"kind": kind, "target": target, "archive": identity(archive), "report": identity(report_path),
                       "primary_exit": 1, "checks": report["checks"], "only_expected_false_keys": sorted(false),
                       "difference": delta, "other_positive_unchanged": True})
    return result, history


def v2_and_public(manifest, runtime):
    result = read(WORK / "installed-internal-v2.json")
    raw = (WORK / "raw/installed-internal-v2.stdout.txt").read_text().splitlines()
    begin, end = map(json.loads, raw)
    assert begin["phase"] == "BEGIN" and end == result
    assert result["phase"] == "END" and result["passed"] is True and result["status"] == "PASS"
    assert result["production_approved"] is False and result["flags"]["production_approved"] is False
    assert result["actual"] == {"counts": {"credit_v2_sources": 2, "credit_v2_intents": 2, "uta_credit_decisions": 1, "ledger_events": 4},
              "debt": ["0.3", "0"], "ledger_btc_units": {"customer:alice": "30000000", "liability:principal:alice": "-30000000",
              "system:credit-pool": "70000000", "system:credit-principal-receivable": "30000000"}, "foreign_key_check": []}
    assert result["public_new_borrow"] == {"code": "unsupported_credit_operation", "status": 501}
    assert result["readiness"]["ready"] is False and result["readiness"]["reason"] == "internal_credit_authority_not_trading"
    assert result["readonly_reopen"] == {"separate_unbound_database": True, "query_only": True, "existing_source_full_validation": True,
                                           "ledger_verify_events": 4, "nonzero_liabilities": 1}
    assert result["clock_scope"] == "static public synthetic financial fixture clock; no live TTL freshness claim"
    assert len(result["borrow_ledger_legs"]) == len(result["repay_ledger_legs"]) == 4
    assert [x["units"] for x in result["borrow_ledger_legs"]] == ["40000000", "-40000000", "-40000000", "40000000"]
    assert [x["units"] for x in result["repay_ledger_legs"]] == ["-10000000", "10000000", "10000000", "-10000000"]
    site = WORK / "venv/lib/python3.12/site-packages"
    for path in result["runtime"]["uta_paths"].values():
        path = Path(path).resolve()
        assert path.is_relative_to(site) and not path.is_relative_to(WORK / "sdist-unpacked")
        name = str(path.relative_to(site))
        assert sha(path.read_bytes()) == runtime[name]
    for item in result["fixture_sources"].values():
        path = Path(item["path"])
        assert path.is_relative_to(WORK / "sdist-unpacked/uta_reference_exchange-0.5.0a1/tests")
        assert sha(path.read_bytes()) == item["sha256"]
    assert begin["isolated"] == 1 and begin["no_git"] is True
    assert begin["driver_sha256"] == identity(AUTHOR / "installed_v2_smoke.py")["sha256"]
    allowlist = read(AUTHOR / "public-allowlist.json")
    for name, record in allowlist["copied_files"].items():
        assert (AUTHOR / name).read_bytes() == Path(record["original_path"]).read_bytes()
        assert identity(AUTHOR / name) == {key: record[key] for key in ("bytes", "sha256")}
    return {"actual": result["actual"], "borrow_legs": result["borrow_ledger_legs"], "repay_legs": result["repay_ledger_legs"],
            "original_cid_replay": result["original_cid_replay"], "readonly_reopen": result["readonly_reopen"],
            "all_loaded_module_paths_installed": True, "loaded_module_count": len(result["runtime"]["uta_paths"]),
            "clock_scope": result["clock_scope"], "live_TTL_verified": False, "public_new_borrow": result["public_new_borrow"],
            "ready": False, "public_safe_files_byte_identical": len(allowlist["copied_files"])}


def main():
    manifest, hashes, runtime, artifacts, wheel, sdist, wi, comment, ti, prefix = source_and_artifacts()
    phases, installed, counts = execution_and_installed(manifest, runtime, artifacts)
    controls, history = negative_controls(manifest, runtime, artifacts, wheel, sdist, wi, comment, ti, prefix)
    v2 = v2_and_public(manifest, runtime)
    assert manifest["artifacts"] == {path.name: identity(path) for path in (wheel, sdist)}
    assert git("status", "--porcelain", "--untracked-files=all") == b""
    report = {"verdict": "ACCEPT_DBC93E5_PACKAGE_SCOPE_ONLY", "source_commit": PIN, "artifacts": artifacts,
              "tracked_file_count": len(hashes), "runtime_file_count": len(runtime), "runtime_tree_sha256": manifest["runtime_tree_sha256"],
              "tracked_file_sha256": hashes, "phases": phases, "installed": installed, "no_git_test_counts": counts,
              "negative_controls": controls, "historical_ZIP_failure_and_source_proof": history, "installed_v2": v2,
              "timing_scope": "All outer driver commands have actual UTC/monotonic walls; nested console and individual primary-negative records retain argv/cwd/exit/streams but do not record separate per-command walls. No derived individual durations are claimed.",
              "review_product_imports": False, "review_SQL_executed": False, "review_build_install_or_functional_reruns": False,
              "negative_archives_installed": False, "historical_CI_is_current_qualification": False,
              "overall_candidate_status": "NO_GO_PENDING_FULL_CURRENT_QA_CI_PACKAGE_GATES", "production_approved": False}
    output = OUT / "review.json"
    assert not output.exists()
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: report[key] for key in ("verdict", "source_commit", "artifacts", "tracked_file_count", "runtime_file_count",
                      "runtime_tree_sha256", "no_git_test_counts", "overall_candidate_status", "production_approved")}, indent=2))


if __name__ == "__main__":
    main()
