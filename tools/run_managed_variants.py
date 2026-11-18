"""Bounded, fail-closed orchestration of the preregistered local admission cases.

Default prepare reads files and prints JSON only: no subprocess, authority,
output directory, affinity change or financial import. Execute requires a
separate immutable registration and exact-source qualification evidence.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from fractions import Fraction
import gzip
from hashlib import sha256
import io
import json
import math
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import sys
import tarfile
import time
import zipfile

PLAN = "benchmarks/plans/20261117-managed-variants.json"
PLAN_HASH = "cfd24bcbde07a5db38a2c93e073be8471fa2fc32206b56f03f00a43d111f8c12"
MiB, GiB = 1024 ** 2, 1024 ** 3
PROTECTED = {4471, 8784}
ARMS = {"A": (0, 0), "B3": (3, 0), "B8": (8, 0), "C8": (0, 8), "C100": (0, 100)}
RESERVES = {"producer": 6 * GiB, "future_clone": 6 * GiB,
            "clone_headroom": GiB, "observer": 128 * MiB, "original_other": GiB}


class GateError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise GateError(message)


def integer(value, low, high, label):
    require(type(value) is int and low <= value <= high, "invalid integer: " + label)
    return value


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def strict_json(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate JSON key: " + key)
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(GateError("nonfinite JSON")))


def read_blob(path, limit=4 * MiB):
    # No symlink following for evidence/heartbeat inputs; no database open.
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), "JSON is not a regular file")
        data = stream.read(limit + 1)
    require(len(data) <= limit, "JSON input exceeds limit")
    return data


def read_json(path, limit=4 * MiB):
    return strict_json(read_blob(path, limit))


def proof(reference):
    require(set(reference) == {"path", "sha256"}, "evidence reference fields")
    path = Path(reference["path"])
    require(path.is_absolute() and re.fullmatch(r"[0-9a-f]{64}", reference["sha256"] or ""), "evidence identity")
    data = read_blob(path)
    require(sha256(data).hexdigest() == reference["sha256"], "evidence hash mismatch: " + str(path))
    return strict_json(data)


@dataclass(frozen=True)
class Case:
    case_id: str
    variant: str
    batch: int
    cache: int

    def validate(self):
        require(type(self.batch) is type(self.cache) is int, "case numeric options must be integers")
        require(self.variant in ARMS and (self.batch, self.cache) == ARMS[self.variant], "case changes multiple/unregistered factors")
        require(re.fullmatch(r"[A-Z0-9-]{1,32}", self.case_id), "case ID")


def schedule():
    cases = []
    for variant in ("B3", "B8", "C8", "C100"):
        for pair, order in enumerate((("A", variant), (variant, "A"), ("A", variant)), 1):
            for side, arm in enumerate(order, 1):
                item = Case(f"{variant}-{pair}-{side}-{arm}", arm, *ARMS[arm])
                item.validate()
                cases.append(item)
    return cases


def base_plan(source):
    path = Path(source) / PLAN
    require(digest(path) == PLAN_HASH, "immutable preregistration changed")
    plan = read_json(path)
    require(plan["execution_authorized"] is False and plan["frozen_commit"] is None, "base plan history changed")
    return plan


def validate_registration(value):
    require(set(value) == {"format", "registration_id", "source_commit", "base_plan_sha256", "execution_go",
        "registered_utc", "output_root", "cpu_ids", "limits", "cohosts", "reserves", "qualification"}, "registration fields")
    require(value["format"] == 1 and type(value["format"]) is int, "registration format")
    require(re.fullmatch(r"[a-z0-9-]{1,64}", value["registration_id"] or ""), "registration ID")
    require(re.fullmatch(r"[0-9a-f]{40}", value["source_commit"] or ""), "exact source SHA required")
    require(value["base_plan_sha256"] == PLAN_HASH, "registration base plan hash")
    require(type(value["execution_go"]) is bool, "GO must be boolean")
    at = datetime.fromisoformat(value["registered_utc"])
    require(at.tzinfo is not None and at.timestamp() <= time.time() + 1, "registration UTC")
    require(Path(value["output_root"]).is_absolute(), "absolute new output root required")
    cpus = value["cpu_ids"]
    require(type(cpus) is list and len(cpus) == 2 and len(set(cpus)) == 2, "two explicit unique CPUs")
    for cpu in cpus:
        integer(cpu, 0, 4095, "CPU ID")
    limits = value["limits"]
    require(set(limits) == {"case_wall_seconds", "grace_seconds", "kill_wait_seconds", "case_bytes", "aggregate_bytes", "cleanup_bytes"}, "limit fields")
    for key, low, high in (("case_wall_seconds", 30, 120), ("grace_seconds", 1, 5), ("kill_wait_seconds", 1, 5),
                           ("case_bytes", MiB, 64 * MiB), ("aggregate_bytes", MiB, 512 * MiB), ("cleanup_bytes", 128 * MiB, GiB)):
        integer(limits[key], low, high, key)
    require(limits["aggregate_bytes"] >= limits["case_bytes"], "aggregate below case cap")
    require(type(value["cohosts"]) is list and len(value["cohosts"]) >= 2, "registered cohosts required")
    ids = set()
    for host in value["cohosts"]:
        require(set(host) == {"pid", "birth_ticks", "heartbeat", "heartbeat_pointer", "alerts_pointer", "work_age_pointer", "source_pointer", "source_commit", "max_age_seconds"}, "cohost fields")
        ids.add(integer(host["pid"], 2, 2 ** 31 - 1, "cohost PID"))
        integer(host["birth_ticks"], 1, 2 ** 63 - 1, "birth ticks")
        integer(host["max_age_seconds"], 1, 120, "heartbeat age")
        require(Path(host["heartbeat"]).is_absolute() and Path(host["heartbeat"]).suffix == ".json", "JSON heartbeat only")
        require(re.fullmatch(r"[0-9a-f]{40}", host["source_commit"] or ""), "cohost source")
        for key in ("heartbeat_pointer", "alerts_pointer", "work_age_pointer", "source_pointer"):
            require(type(host[key]) is list and host[key] and all(type(part) is str for part in host[key]), "JSON pointer")
    require(len(ids) == len(value["cohosts"]) and PROTECTED <= ids, "protect/register original producer and observer")
    require(set(value["reserves"]) == set(RESERVES), "all cohost disk reserves required")
    for name, minimum in RESERVES.items():
        item = value["reserves"][name]
        require(set(item) == {"remaining_bytes", "evidence", "pointer"}, "reservation proof fields")
        integer(item["remaining_bytes"], minimum, 1 << 50, "reserve " + name)
        require(type(item["pointer"]) is list and item["pointer"], "reserve proof pointer")
    require(set(value["qualification"]) == {"expected_tests", "local", "ci", "package"}, "qualification groups")
    integer(value["qualification"]["expected_tests"], 1, 1_000_000, "full suite count")
    return value


def prepare(source, registration=None):
    plan = base_plan(source)
    if registration is not None:
        validate_registration(registration)
    return {"mode": "PREPARE_ONLY", "source_identity_verified": False,
        "execution_authorized_by_prepare": False, "base_plan_sha256": PLAN_HASH,
        "cases": [item.__dict__ for item in schedule()], "planned_arrivals_per_case": plan["fixed_configuration"]["offered_arrivals"],
        "scope": "local SDK admission; no fills/REST/TLS/replication; COMMIT counts and cache hits unmeasured"}


def git(source, *args):
    return subprocess.check_output(["git", *args], cwd=source, text=True).strip()


def source_identity(source, commit):
    require(git(source, "rev-parse", "HEAD") == commit, "source HEAD changed")
    require(not git(source, "status", "--porcelain", "--untracked-files=all"), "source is not clean")
    names = git(source, "ls-tree", "-r", "--name-only", commit).splitlines()
    hashes = {name: digest(Path(source) / name) for name in names}
    require(hashes[PLAN] == PLAN_HASH, "base plan source changed")
    require(hashes.get("tools/run_managed_variants.py") == digest(__file__), "runner is not part of the qualified frozen source")
    require("measurement-footer.json" in (Path(source) / "benchmarks/run_managed_benchmark.py").read_text(), "producer lacks actual observation timing footer")
    return hashes


def artifact_blob(reference):
    require(set(reference) == {"path", "sha256"}, "artifact reference fields")
    path = Path(reference["path"])
    require(path.is_absolute() and re.fullmatch(r"[0-9a-f]{64}", reference["sha256"] or ""), "artifact reference identity")
    data = read_blob(path, 128 * MiB)
    require(sha256(data).hexdigest() == reference["sha256"], "physical artifact SHA mismatch")
    return path, data


def member_tree(data, kind):
    """Read-only logical archive tree, including metadata and bounded payloads."""
    result, total = {}, 0
    def content_hash(stream, size):
        nonlocal total
        integer(size, 0, 64 * MiB, "archive member size")
        total += size
        require(total <= 256 * MiB, "decoded archive bound")
        value, count = sha256(), 0
        while True:
            chunk = stream.read(min(MiB, size - count + 1))
            if not chunk:
                break
            count += len(chunk)
            require(count <= size, "archive member exceeds declared size")
            value.update(chunk)
        require(count == size, "archive member payload truncated")
        return value.hexdigest()
    if kind == "wheel":
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            require(len(entries) <= 20000, "archive member count bound")
            for item in entries:
                require(item.filename not in result, "duplicate archive member")
                with archive.open(item) as stream:
                    hashed = content_hash(stream, item.file_size)
                result[item.filename] = ((item.is_dir(), item.external_attr, item.create_system,
                    item.date_time, item.extra, item.comment, item.compress_type, item.flag_bits,
                    item.internal_attr, item.create_version, item.extract_version), hashed)
    else:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as archive:
            for index, item in enumerate(archive):
                require(index < 20000 and item.name not in result and (item.isfile() or item.isdir()), "invalid/duplicate archive member")
                if item.isfile():
                    with archive.extractfile(item) as stream:
                        hashed = content_hash(stream, item.size)
                else:
                    hashed = None
                result[item.name] = ((item.type, item.mode, item.uid, item.gid, item.uname,
                    item.gname, item.mtime, item.linkname, item.pax_headers), hashed)
    return result


def omission_binding(package, archives, source_hashes, commit, *, source=None):
    """Bind actual original/negative bytes and verifier reports, not labels."""
    require(set(package["artifact_files"]) == {"wheel", "sdist"}
        and set(package["runtime_reports"]) == {"wheel", "sdist"}, "package physical evidence groups")
    originals = {kind: artifact_blob(package["artifact_files"][kind]) for kind in ("wheel", "sdist")}
    require(all(type(item.get("bytes")) is int and item["bytes"] > 0 and isinstance(item.get("sha256"), str)
        and re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) for item in archives["artifacts"].values()), "qualified artifact facts have invalid types")
    positive = {path.name: {"bytes": len(data), "sha256": sha256(data).hexdigest()} for path, data in originals.values()}
    require(len(positive) == 2 and positive == archives["artifacts"], "original wheel/sdist SHA or size differs from qualified manifest")
    verifier, verifier_bytes = artifact_blob(package["verifier"])
    require(sha256(verifier_bytes).hexdigest() == source_hashes["tools/verify_release_archives.py"], "verifier is not qualified source")
    expected_source = Path(source).absolute() if source is not None else verifier.parent.parent
    require(verifier == expected_source / "tools/verify_release_archives.py", "verifier path is not qualified source")
    original_trees = {kind: member_tree(data, kind) for kind, (_, data) in originals.items()}
    controls, zips = proof(package["runtime_controls"]), proof(package["zip_controls"])
    require(controls["source_commit"] == zips["source_commit"] == commit, "omission collector source differs")
    runtime_cases = {item["case"]: item for item in controls["cases"]}
    require(set(runtime_cases) == {kind + "_missing_new_failure_diagnostics_is_rejected" for kind in ("wheel", "sdist")}, "runtime omission directions duplicated/missing")
    tracked_zips = {name for name in source_hashes if name.endswith(".zip")}
    require(set(package["zip_reports"]) == tracked_zips, "all ZIP negative reports required")
    require(len(zips["omission_controls"]) == len(tracked_zips), "ZIP negative controls duplicated/missing")
    cases = [(kind, "uta/failure_diagnostics.py", runtime_cases[kind + "_missing_new_failure_diagnostics_is_rejected"],
              package["runtime_reports"][kind], {"wheel_runtime_exact"} if kind == "wheel" else {"sdist_runtime_exact", "sdist_required_files_exact"})
             for kind in ("wheel", "sdist")]
    cases += [("sdist", item["removed_member"], item, package["zip_reports"][item["removed_member"]], {"sdist_required_files_exact"})
              for item in zips["omission_controls"]]
    for kind, target, item, reference, false_checks in cases:
        report = proof(reference)
        argv = item["argv"]
        require(len(argv) == 12 and argv[1] == str(verifier)
            and argv[2::2] == ["--source", "--commit", "--wheel", "--sdist", "--output"]
            and argv[3] == str(expected_source) and argv[5] == commit, "negative verifier argv/source binding")
        output_path, report_path = Path(argv[11]), Path(reference["path"])
        require(output_path.is_absolute() and report_path.is_absolute()
            and argv[11] == str(output_path.resolve()) and reference["path"] == str(report_path.resolve())
            and output_path == report_path, "negative verifier output is not the pinned canonical report path")
        require(type(item["returncode"]) is int and item["returncode"] == 1 and item["passed"] is True and item["removed_member"] == target
            and type(item["removed_count"]) is int and item["removed_count"] == 1, "negative case identity/actual rejection")
        require(item.get("source_commit", commit) == commit, "negative case source differs")
        checkmap = {name: name not in false_checks for name in archives["checks"]}
        require(item["checks"] == report["checks"] == checkmap and all(type(value) is bool for value in report["checks"].values())
            and all(type(value) is bool for value in item["checks"].values()), "negative full check matrix differs")
        missing = [] if kind == "wheel" else [target]
        require(item["sdist_missing"] == report["sdist_missing"] == missing and report["sdist_mismatched"] == [], "negative exact missing/mismatched paths")
        require(report["source_commit"] == commit and report["passed"] is False, "negative report source/outcome")
        for key in ("runtime_files", "runtime_tree_sha256", "sdist_required_files", "version", "metadata_versions", "entry_points", "cli_helper_sha256", "legacy_fixture_provenance"):
            require(report[key] == archives[key], "negative report changed qualified " + key)
        paths = {"wheel": Path(argv[7]), "sdist": Path(argv[9])}
        require(all(path.is_absolute() for path in paths.values()), "negative input paths must be absolute")
        unchanged = "sdist" if kind == "wheel" else "wheel"
        require(paths[unchanged] == originals[unchanged][0] and paths[kind] != originals[kind][0], "negative changed unmodified positive side/path")
        negative_data = read_blob(paths[kind], 128 * MiB)
        facts = {"bytes": len(negative_data), "sha256": sha256(negative_data).hexdigest()}
        require(item["negative_archive_sha256"] == facts["sha256"], "negative physical SHA differs")
        expected_artifacts = {originals[unchanged][0].name: positive[originals[unchanged][0].name], paths[kind].name: facts}
        require(len(expected_artifacts) == 2 and report["artifacts"] == expected_artifacts, "negative report not bound to actual two input artifacts")
        before, after = original_trees[kind], member_tree(negative_data, kind)
        if kind == "wheel":
            removed = target
        else:
            roots = {name.split("/")[0] for name in before}
            require(len(roots) == 1, "sdist roots differ")
            removed = next(iter(roots)) + "/" + target
        require(removed in before and set(after) == set(before) - {removed}
            and list(after) == [name for name in before if name != removed]
            and all(after[name] == before[name] for name in after), "negative archive differs beyond the single removed target")
    # Reread positive inputs after comparisons, so an input change cannot hide.
    for kind, (path, original) in originals.items():
        require(artifact_blob(package["artifact_files"][kind])[1] == original, "positive artifact changed during omission validation")


def qualification(source_hashes, registration, *, source=None):
    q, commit = registration["qualification"], registration["source_commit"]
    expected = {name: value for name, value in source_hashes.items()
                if (name.split("/")[0] in {"uta", "tests", "formal", "tools", "benchmarks", "scripts"} and name.endswith(".py"))
                or name.startswith("tests/fixtures/") or name in {"pyproject.toml", "MANIFEST.in", "LICENSE"}}
    require(len(q["local"]) == 3 and len(q["ci"]) == 8, "three local and eight CI proofs required")
    seen = set()
    for kind in ("local", "ci"):
        for record in q[kind]:
            wanted = {"python", "summary", "worker", "log"} | ({"run", "job"} if kind == "ci" else set())
            require(set(record) == wanted, "qualification proof fields")
            summary, worker = proof(record["summary"]), proof(record["worker"])
            logpath = Path(record["log"]["path"])
            require(digest(logpath) == record["log"]["sha256"] == summary["test_log_sha256"], "full QA log hash")
            log = logpath.read_text()
            require("ResourceWarning:" not in log and "Exception ignored in:" not in log, "unraisable/resource warning in QA")
            require(re.search(r"Ran " + str(q["expected_tests"]) + r" tests? in [0-9.]+s\s+OK\s*$", log), "full QA log completion")
            for field in ("passed", "unittest_passed", "source_unchanged", "tracked_source_clean_before", "tracked_source_clean_after"):
                require(summary[field] is True, "failed/unknown qualification: " + field)
            for field in ("failures", "errors", "skipped", "expected_failures", "unexpected_successes", "worker_exit_code"):
                require(type(summary[field]) is int and summary[field] == 0, "red qualification: " + field)
            require(summary["tests_run"] == q["expected_tests"], "QA suite count")
            require(len(summary["command_argv"]) == 4 and summary["command_argv"][1].endswith("/tools/run_validation.py")
                and summary["command_argv"][2] == "--output", "not the full-suite validation command")
            require(summary["source_sha256"] == summary["source_sha256_after"] == expected, "QA input source hashes differ")
            worker_fields = {"tests_run", "failures", "errors", "skipped", "expected_failures", "unexpected_successes", "unittest_passed"}
            diagnostic_fields = {"lease_observations", "lease_observations_truncated"}
            require(set(worker) in (worker_fields, worker_fields | diagnostic_fields), "QA worker result fields")
            if set(worker) != worker_fields:
                require(type(worker["lease_observations"]) is list and worker["lease_observations"] == []
                    and worker["lease_observations_truncated"] is False, "QA worker lease diagnostics must be empty and untruncated")
                require(diagnostic_fields <= set(summary), "QA worker differs from summary")
            if diagnostic_fields & set(summary):
                require(diagnostic_fields <= set(summary), "QA summary lease diagnostic fields")
                require(type(summary["lease_observations"]) is list and summary["lease_observations"] == []
                    and summary["lease_observations_truncated"] is False, "QA summary lease diagnostics must be empty and untruncated")
            require(all(type(worker[key]) is type(summary[key]) and worker[key] == summary[key] for key in worker), "QA worker differs from summary")
            require(record["python"] in ("3.10", "3.11", "3.12", "3.13") and summary["python"].startswith(record["python"] + "."), "QA interpreter identity")
            if kind == "local":
                require(summary["code_commit"] == commit, "old local source cannot qualify new source")
                key = (kind, record["python"])
            else:
                run, job = proof(record["run"]), proof(record["job"])
                require(run["event"] in ("push", "pull_request") and run["head_sha"] == commit, "CI is not this source/event")
                require(run["status"] == job["status"] == "completed" and run["conclusion"] == job["conclusion"] == "success", "failed/pending CI cannot authorize execution")
                require(job["run_id"] == run["id"] and record["python"] in job["name"], "CI job/run matrix binding")
                require(str(run["html_url"]).startswith("https://github.com/PureGamma-Harness/uta-unified-account/actions/runs/"), "CI repository identity")
                if run["event"] == "push":
                    require(summary["code_commit"] == commit, "push CI summary source")
                key = (run["event"], record["python"])
            require(key not in seen, "duplicate qualification record")
            seen.add(key)
    require({("local", version) for version in ("3.10", "3.12", "3.13")} <= seen, "local matrix incomplete")
    package = q["package"]
    require(set(package) == {"verdict", "archives", "installed", "views", "runtime_controls", "zip_controls", "artifact_files", "verifier", "runtime_reports", "zip_reports"}, "package evidence groups")
    verdict, archives, installed, views = (proof(package[name]) for name in ("verdict", "archives", "installed", "views"))
    for value in (verdict, archives, installed, views):
        require(value["source_commit"] == commit and value["passed"] is True, "old/failed package evidence")
        require(value.get("artifacts") == archives["artifacts"], "package artifact chain differs")
    require(set(archives["checks"]) == {"version", "wheel_runtime_exact", "sdist_runtime_exact", "sdist_required_files_exact", "legacy_fixture_pinned", "legacy_fixture_licensed", "entry_points"}
        and set(archives["sdist_required_files"]) == set(source_hashes) and all(value is True for value in archives["checks"].values())
        and archives["sdist_missing"] == archives["sdist_mismatched"] == [], "incomplete package archive gate")
    require(archives["runtime_files"] == {name: value for name, value in source_hashes.items() if name.startswith("uta/") and name.endswith((".py", ".html"))}, "package runtime differs")
    require(verdict["no_old_artifacts_or_pass_reused"] is True and verdict["actual_negative_controls"] >= 4, "fresh complete package proof required")
    require(installed["tests"] == {"run": 8, "errors": 0, "failures": 0, "skipped": 0} and len(installed["commands"]) == 8 and all(item["returncode"] == 0 for item in installed["commands"]), "installed CLI qualification")
    require(views["tests"] == {"run": 3, "errors": 0, "failures": 0, "skipped": 0}, "installed RO views qualification")
    for value in (installed, views):
        require(value["isolated"] is True and value["pythonpath"] is None and value["version"] == archives["version"], "package installed isolation/version")
        require(value["runtime_tree_sha256"] == archives["runtime_tree_sha256"], "installed runtime tree differs")
    negative, zips = proof(package["runtime_controls"]), proof(package["zip_controls"])
    require(negative["source_commit"] == zips["source_commit"] == commit and negative["passed"] is zips["passed"] is True, "failed/old omission proof")
    require(len(negative["cases"]) == 2 and all(item["returncode"] == 1 and item["passed"] is True for item in negative["cases"]), "runtime omission did not actually reject")
    tracked_zips = {name for name in source_hashes if name.endswith(".zip")}
    require({item["tracked_path"] for item in zips["inclusions"]} == tracked_zips
        and {item["removed_member"] for item in zips["omission_controls"]} == tracked_zips
        and all(item["returncode"] == 1 and item["passed"] is True for item in zips["omission_controls"]), "tracked ZIP omission coverage")
    require(all(item["sha256"] == source_hashes[item["tracked_path"]] for item in zips["inclusions"]), "ZIP source bytes differ")
    require(verdict["actual_negative_controls"] == len(negative["cases"]) + len(zips["omission_controls"]), "negative control count inflated")
    omission_binding(package, archives, source_hashes, commit, source=source)


def pointer(value, path):
    for key in path:
        value = value[key]
    return value


def process_identity(pid):
    # comm may contain spaces or ')'; fields after its final ')' are fixed.
    fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    return {"pid": pid, "state": fields[0], "parent": int(fields[1]),
            "group": int(fields[2]), "session": int(fields[3]), "birth_ticks": int(fields[19])}


def cohost_observations(hosts):
    result = []
    for host in hosts:
        identity = process_identity(host["pid"])
        require(identity["birth_ticks"] == host["birth_ticks"] and identity["state"] not in ("Z", "X"), "cohost PID changed/dead")
        data = read_blob(host["heartbeat"])
        state = strict_json(data)
        require(pointer(state, host["source_pointer"]) == host["source_commit"], "cohost source changed")
        stamp = pointer(state, host["heartbeat_pointer"])
        require(type(stamp) is str, "heartbeat must be actual ISO UTC string")
        parsed = datetime.fromisoformat(stamp)
        require(parsed.tzinfo is not None, "heartbeat timezone")
        age = time.time() - parsed.timestamp()
        require(-1 <= age <= host["max_age_seconds"], "cohost heartbeat stale/future")
        require(pointer(state, host["alerts_pointer"]) == [], "cohost reports alerts")
        work_age = pointer(state, host["work_age_pointer"])
        require(type(work_age) in (int, float) and math.isfinite(work_age) and work_age >= 0
            and max(0, age) + work_age <= host["max_age_seconds"], "underlying cohost work heartbeat stale/future")
        result.append({"process": identity, "observation_age_seconds": age, "underlying_work_age_at_observation_seconds": work_age,
            "heartbeat_sha256": sha256(data).hexdigest(), "source_commit": host["source_commit"]})
    return result


def tree_bytes(path):
    if not Path(path).exists():
        return 0
    total = 0
    for base, directories, files in os.walk(path, followlinks=False):
        require(not any((Path(base) / name).is_symlink() for name in directories + files), "output contains a symlink")
        total += sum((Path(base) / name).stat().st_size for name in files)
    return total


def resources(registration, root):
    reserved = 0
    for name, item in registration["reserves"].items():
        require(pointer(proof(item["evidence"]), item["pointer"]) == item["remaining_bytes"], "unproven/reduced reserve: " + name)
        reserved += item["remaining_bytes"]
    target = Path(root) if Path(root).exists() else Path(root).parent
    disk = os.statvfs(target)
    free = disk.f_bavail * disk.f_frsize
    needed = reserved + registration["limits"]["cleanup_bytes"] + registration["limits"]["case_bytes"] + 2 * GiB
    require(free >= needed, "cohost reservations plus next-case headroom unavailable")
    used = tree_bytes(root)
    require(used + registration["limits"]["case_bytes"] <= registration["limits"]["aggregate_bytes"], "aggregate output cap would be exceeded")
    return {"free_bytes": free, "required_free_bytes": needed, "retained_cohost_reservations_bytes": reserved, "aggregate_used_bytes": used}


def launcher_affinity_ack(fd, pid, cpu_ids, deadline):
    """Wait for the owned launcher to bind itself, without guessing scheduling."""
    os.set_blocking(fd, False)
    content = bytearray()
    with selectors.DefaultSelector() as ready:
        ready.register(fd, selectors.EVENT_READ)
        while time.monotonic() < deadline:
            if not ready.select(min(.02, max(0, deadline - time.monotonic()))):
                continue
            chunk = os.read(fd, 1025 - len(content))
            require(chunk, "launcher exited without affinity acknowledgement")
            content.extend(chunk)
            require(len(content) <= 1024, "launcher acknowledgement exceeds bound")
            if b"\n" in content:
                require(content.count(b"\n") == 1 and content.endswith(b"\n"), "invalid launcher acknowledgement frame")
                value = strict_json(content)
                require(set(value) == {"pid", "cpu_ids"} and type(value["pid"]) is int
                    and value["pid"] == pid and value["cpu_ids"] == sorted(cpu_ids), "launcher affinity acknowledgement mismatch")
                actual = sorted(os.sched_getaffinity(pid))
                require(actual == sorted(cpu_ids), "kernel affinity differs after launcher acknowledgement")
                return actual
    raise GateError("launcher affinity acknowledgement timed out")


def owned_run(argv, cwd, logs, *, cpu_ids, wall_seconds, grace_seconds,
              kill_wait_seconds, output_cap, protected, health_check=lambda: None):
    """Own a new session; retain an unreaped leader/pidfd through group cleanup.

    Waiting on pidfd does not reap/reuse the leader PID. Even after its exit,
    that retained identity prevents PGID reuse while we clean its own session.
    No existing PID is adopted or signalled. Pipes and file growth are bounded.
    """
    require(hasattr(os, "pidfd_open"), "Linux pidfd support is required")
    require(type(cpu_ids) is list and cpu_ids and all(type(cpu) is int and cpu >= 0 for cpu in cpu_ids), "explicit integer CPU IDs")
    require(set(cpu_ids) <= os.sched_getaffinity(0), "requested CPUs unavailable")
    require(type(output_cap) is int and output_cap > 0, "output cap")
    for value in (wall_seconds, grace_seconds, kill_wait_seconds):
        require(type(value) in (int, float) and math.isfinite(value) and 0 < value <= 120, "watchdog duration")
    paths = [Path(str(logs) + suffix) for suffix in (".stdout", ".stderr")]
    require(all(path.parent.is_dir() and not path.exists() and not path.is_symlink() for path in paths), "new stream paths required before launch")
    ready_read, ready_write = os.pipe()
    launcher = [sys.executable, "-c", "import json,os,sys; os.sched_setaffinity(0," + repr(set(cpu_ids))
        + "); os.write(" + str(ready_write) + ",(json.dumps({'pid':os.getpid(),'cpu_ids':sorted(os.sched_getaffinity(0))})+'\\n').encode()); os.close("
        + str(ready_write) + "); os.execv(sys.argv[1],sys.argv[1:])", *argv]
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    environment.pop("PYTHONPATH", None)
    started = time.monotonic()
    try:
        process = subprocess.Popen(launcher, cwd=cwd, env=environment, start_new_session=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, pass_fds=(ready_write,))
    except BaseException:
        os.close(ready_read)
        os.close(ready_write)
        raise
    os.close(ready_write)
    # Popen.poll/wait are intentionally not used before owned group cleanup.
    files, pidfd, selection = [], None, None
    try:
        identity = process_identity(process.pid)
        require(identity["pid"] not in set(protected) | PROTECTED and identity["session"] == identity["group"] == process.pid, "launched session ownership")
        pidfd = os.pidfd_open(process.pid)
        actual_cpus = launcher_affinity_ack(ready_read, process.pid, cpu_ids, started + min(5, wall_seconds))
        os.close(ready_read)
        ready_read = None
        selection = selectors.DefaultSelector()
        selection.register(pidfd, selectors.EVENT_READ, "exit")
        for path in paths:
            files.append(path.open("xb"))
    except BaseException:
        # This unreaped direct-child PID cannot be reused. Only a successfully
        # observed new private session permits group cleanup; otherwise stop
        # the owned direct child without guessing any process group.
        if ("identity" in locals() and identity["session"] == identity["group"] == process.pid
                and process.pid not in set(protected) | PROTECTED):
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.wait(timeout=kill_wait_seconds)
        process.stdout.close()
        process.stderr.close()
        for stream in files:
            stream.close()
        if selection is not None:
            selection.close()
        if pidfd is not None:
            os.close(pidfd)
        if ready_read is not None:
            os.close(ready_read)
        raise
    hashes, written, seen, truncated = [sha256(), sha256()], [0, 0], [0, 0], False
    reason, exited = None, False
    def signal_own(sig):
        current = process_identity(process.pid)
        require(current["birth_ticks"] == identity["birth_ticks"] and current["group"] == current["session"] == process.pid, "lost owned PID/session identity")
        require(not any(_same_group(pid, process.pid) for pid in set(protected) | PROTECTED), "protected cohost in group; refusing signal")
        os.killpg(process.pid, sig)
    try:
        for index, stream in enumerate((process.stdout, process.stderr)):
            os.set_blocking(stream.fileno(), False)
            selection.register(stream, selectors.EVENT_READ, index)
        write_json(Path(str(logs) + ".owner.json"), {"identity": identity, "pidfd_used": True,
            "owned_session": True, "protected_pids": sorted(set(protected) | PROTECTED),
            "launcher_argv": launcher, "cpu_ids": list(cpu_ids), "observed_child_cpu_ids": actual_cpus, "launcher_affinity_acknowledged": True,
            "observed_utc": datetime.now(timezone.utc).isoformat()})
        while not exited and reason is None:
            try:
                health_check()
            except Exception as error:
                reason = "health_or_resource_gate:" + str(error)
            if time.monotonic() - started >= wall_seconds:
                reason = "wall_deadline_unknown"
            if reason is None:
                for key, _ in selection.select(.02):
                    if key.data == "exit":
                        exited = True
                    else:
                        _capture(key, selection, files, hashes, written, seen, output_cap)
                if sum(seen) > output_cap:
                    reason, truncated = "output_cap_unknown", True
        # The leader is still unreaped, so this exact session cannot be reused.
        # A normally exited leader with surviving children also needs cleanup.
        others = _group_members(process.pid, exclude=process.pid)
        if others and reason is None:
            reason = "live_descendants_after_leader_exit_unknown"
        if reason is not None or others:
            signal_own(signal.SIGTERM)
            deadline = time.monotonic() + grace_seconds
            while time.monotonic() < deadline and (_group_members(process.pid, exclude=process.pid) or not _pidfd_ready(pidfd)):
                _drain(selection, files, hashes, written, seen, output_cap)
                time.sleep(.01)
            if _group_members(process.pid, exclude=process.pid) or not _pidfd_ready(pidfd):
                signal_own(signal.SIGKILL)
        deadline = time.monotonic() + kill_wait_seconds
        while time.monotonic() < deadline and not _pidfd_ready(pidfd):
            _drain(selection, files, hashes, written, seen, output_cap)
        require(_pidfd_ready(pidfd), "owned child did not exit after bounded KILL")
        returncode = process.wait(timeout=kill_wait_seconds)
        # Drain finite kernel pipe contents after every owned producer is dead.
        for _ in range(100):
            if len(selection.get_map()) <= 1:
                break
            _drain(selection, files, hashes, written, seen, output_cap)
        truncated |= sum(seen) > output_cap
        require(not _group_members(process.pid, exclude=process.pid), "owned session still has live descendants")
        return {"argv": argv, "launcher_argv": launcher, "identity": identity, "pidfd_used": True,
            "cpu_ids": list(cpu_ids), "observed_child_cpu_ids": actual_cpus, "launcher_affinity_acknowledged": True, "wall_seconds": time.monotonic() - started,
            "returncode": returncode, "watchdog_reason": reason, "outcome": "UNKNOWN" if reason or truncated else "EXITED",
            "stdout_stderr_complete": not truncated, "leader_reaped": True,
            "streams": [{"path": str(path), "bytes": written[index], "observed_bytes": seen[index],
                         "sha256": hashes[index].hexdigest()} for index, path in enumerate(paths)]}
    finally:
        # Preserve bounded cleanup on Python-level observer failures too.
        if process.returncode is None:
            if not _pidfd_ready(pidfd) or _group_members(process.pid, exclude=process.pid):
                signal_own(signal.SIGKILL)
            process.wait(timeout=kill_wait_seconds)
        for stream in files:
            stream.close()
        process.stdout.close()
        process.stderr.close()
        selection.close()
        os.close(pidfd)


def _same_group(pid, group):
    try:
        return process_identity(pid)["group"] == group
    except FileNotFoundError:
        return False


def _group_members(group, exclude):
    result = []
    for path in Path("/proc").iterdir():
        if path.name.isdigit() and int(path.name) != exclude:
            try:
                identity = process_identity(int(path.name))
                if identity["group"] == group and identity["state"] not in ("Z", "X"):
                    result.append(identity)
            except (FileNotFoundError, ProcessLookupError):
                pass
    return result


def _pidfd_ready(pidfd):
    with selectors.DefaultSelector() as selection:
        selection.register(pidfd, selectors.EVENT_READ)
        return bool(selection.select(0))


def _capture(key, selection, files, hashes, written, seen, limit):
    content = os.read(key.fileobj.fileno(), 65536)
    if not content:
        selection.unregister(key.fileobj)
        return
    index = key.data
    seen[index] += len(content)
    remaining = max(0, limit - sum(written))
    retained = content[:remaining]
    files[index].write(retained)
    files[index].flush()
    hashes[index].update(retained)
    written[index] += len(retained)


def _drain(selection, files, hashes, written, seen, limit):
    for key, _ in selection.select(.01):
        if key.data != "exit":
            _capture(key, selection, files, hashes, written, seen, limit)


def composite_gate(summary):
    gate = summary.get("probe_qualification", {})
    return gate.get("passed") is True and gate.get("financial_soft_deadline_passed") is True


def integer_map(value, label):
    require(type(value) is dict, "counter map required: " + label)
    for key, count in value.items():
        integer(count, 0, 1 << 63, label + "." + key)


def nanoseconds_and_sequences(value, label, *, nullable_ns=()):
    """Reject numeric aliases before set membership, arithmetic or ID formatting."""
    if type(value) is dict:
        for key, item in value.items():
            name = label + "." + key
            if key.endswith("_ns"):
                if item is None:
                    require(key in nullable_ns, "nonnullable nanoseconds: " + name)
                else:
                    integer(item, 0, 1 << 63, name)
            elif key == "sequence":
                integer(item, 0, 1 << 63, name)
            else:
                nanoseconds_and_sequences(item, name, nullable_ns=nullable_ns)
    elif type(value) is list:
        for index, item in enumerate(value):
            nanoseconds_and_sequences(item, label + "[" + str(index) + "]", nullable_ns=nullable_ns)


def consumed_counter_types(summary):
    integer_map(summary["counts"], "counts")
    integer_map(summary["outcome_counts"], "outcome_counts")
    technical = summary["command_technical_diagnostics"]
    for key, value in technical.items():
        if key in ("diagnostics_overlap_outcomes", "original_internal_exception_available"):
            require(type(value) is bool, "technical flag must be boolean")
        elif key == "commands_by_kind":
            integer_map(value, "commands_by_kind")
        elif key == "affected_commands":
            require(type(value) is list, "affected commands must be a list")
            for row in value:
                integer(row["shard"], 0, 1, "affected command shard")
                integer(row["attempts"], 0, 1 << 63, "affected command attempts")
                if row.get("terminal_error_status") is not None:
                    integer(row["terminal_error_status"], 100, 599, "terminal error status")
        else:
            integer(value, 0, 1 << 63, "technical." + key)
    for key, value in summary["batch_dispatch_diagnostics"].items():
        if key == "record_counts_are_not_commit_counts":
            require(value is True, "batch record-count flag")
        else:
            integer(value, 0, 1 << 63, "batch." + key)
    ro = summary["readonly_reconciliation"]
    for key in ("persistent_successes", "observed_financial_successes", "pending_count",
                "unobserved_successes_found_on_reopen", "durable_enqueue_acknowledgements_verified"):
        if key in ro:
            integer(ro[key], 0, 1 << 63, "readonly." + key)
    for shard in ro["shards"]:
        for key in ("shard", "commands", "unique_orders", "confirmed_matches", "ledger_events"):
            if key in shard:
                integer(shard[key], 0, 1 << 63, "readonly shard." + key)


def bounded_arrivals(path, *, maximum_rows=200, maximum_line_bytes=65536, maximum_total_bytes=8 * MiB, compressed=True, partial_tail=False):
    """Bound decompressed bytes before decode/JSON and detect one excess row.

    At most maximum_rows+1 bounded reads occur, including the EOF/excess probe.
    An excess row is rejected before it is parsed or appended.
    """
    integer(maximum_rows, 1, 200, "arrival row bound")
    integer(maximum_line_bytes, 1, 65536, "arrival line bound")
    integer(maximum_total_bytes, 1, 8 * MiB, "arrival total bound")
    rows, total, ignored = [], 0, False
    opener = gzip.open if compressed else open
    with opener(path, "rb") as stream:
        for index in range(maximum_rows + 1):
            content = stream.readline(min(maximum_line_bytes + 1, maximum_total_bytes - total + 1))
            if not content:
                return rows, ignored
            require(type(content) is bytes, "arrival stream must be binary")
            total += len(content)
            require(len(content) <= maximum_line_bytes and total <= maximum_total_bytes, "decompressed arrival byte bound exceeded")
            require(index < maximum_rows, "arrival count exceeds plan")
            try:
                rows.append(strict_json(content))
            except ValueError:
                if partial_tail and not content.endswith(b"\n"):
                    ignored = True
                    break
                raise
    return rows, ignored


def recompute(directory, case, source_hashes, commit):
    """Independent JSON-only oracle; no SQL/financial imports or recalculation."""
    directory = Path(directory)
    manifest = read_json(directory / "manifest.json")
    required = {"summary.json", "arrival-window.json", "measurement-footer.json", "arrivals.jsonl.gz"}
    require(required <= set(manifest["files"]), "consumed originals missing from manifest")
    originals = {}
    for name, item in manifest["files"].items():
        require(not Path(name).is_absolute() and ".." not in Path(name).parts, "manifest path escapes")
        path = directory / name
        integer(item["bytes"], 0, 64 * MiB, "manifest byte count")
        if name in required:
            content = read_blob(path, 64 * MiB if name == "arrivals.jsonl.gz" else 4 * MiB)
            require(len(content) == item["bytes"] and sha256(content).hexdigest() == item["sha256"], "consumed original hash mismatch")
            originals[name] = content
        else:
            require(not path.is_symlink() and path.stat().st_size == item["bytes"] and digest(path) == item["sha256"], "raw artifact hash mismatch")
    summary, window, footer = (strict_json(originals[name]) for name in
        ("summary.json", "arrival-window.json", "measurement-footer.json"))
    rows, _ = bounded_arrivals(io.BytesIO(originals["arrivals.jsonl.gz"]))
    consumed_counter_types(summary)
    nanoseconds_and_sequences(window, "window")
    nanoseconds_and_sequences(footer, "footer")
    config = summary["configuration"]
    expected_config = {"duration": 10, "rate": 20, "accounts": 100, "shards": 2,
        "dispatchers": 2, "outstanding": 256, "inbox_capacity": 128, "reject_every": 10,
        "feed_interval": 2, "control_timeout": 3, "drain_seconds": 10,
        "timeout_ms": 1000, "poll_interval": .02, "background_interval": .1,
        "profile": False, "durable_batches": True, "financial_batch_size": case.batch,
        "normal_cache_size": case.cache}
    for candidate in (config, window["configuration"]):
        for key in ("accounts", "shards", "dispatchers", "outstanding", "inbox_capacity", "reject_every", "financial_batch_size", "normal_cache_size"):
            integer(candidate[key], 0, 1 << 63, "configuration." + key)
        require(type(candidate["profile"]) is type(candidate["durable_batches"]) is bool, "configuration boolean flags")
    require(config == expected_config and window["configuration"] == config, "case configuration differs")
    integer(footer["timing_contract_version"], 1, 1, "timing contract version")
    require(footer["setup_and_close_excluded"] is True, "timing contract")
    start = integer(footer["started_monotonic_ns"], 1, 1 << 63, "start")
    settled = integer(footer["terminal_observation_finished_monotonic_ns"], start, 1 << 63, "settled")
    require(footer["planned_duration_ns"] == 10 ** 10 and window["planned_start_monotonic_ns"] == start, "original timing anchors")
    integer(summary["offered"], 200, 200, "summary offered")
    integer(window["offered"], 200, 200, "window offered")
    require(len(rows) == summary["offered"] == window["offered"] == 200, "arrival loss/duplication")
    for row in rows:
        integer(row["sequence"], 0, 199, "arrival sequence")
        nanoseconds_and_sequences(row, "arrival", nullable_ns=("enqueue_started_ns", "enqueue_ack_ns", "enqueue_call_finished_ns"))
    require({row["sequence"] for row in rows} == set(range(200)), "arrival sequences")
    require(len({row["command_id"] for row in rows}) == len({row["order_id"] for row in rows}) == 200, "business IDs reused")
    counts, values, late = Counter(), {"all": [], "financial_succeeded": [], "enqueue_ack": []}, 0
    for row in rows:
        sequence = row["sequence"]
        require(row["planned_ns"] == start + sequence * 50_000_000, "open-loop schedule changed")
        require(row["command_id"] == f"bench:{sequence}" and row["order_id"] == f"order:{sequence}", "original IDs changed")
        require(row["account_id"] == f"managed-probe-{sequence % 100}", "account distribution changed")
        require(row["offered_ns"] >= row["planned_ns"], "arrival timestamp")
        complete = row["observed_completion_ns"]
        require(row["offered_ns"] <= complete <= settled and row["latency_ns"] == complete - row["planned_ns"], "completion latency/settled timestamp")
        latency = row["latency_ns"]
        require(row["deadline_exceeded"] is (latency > 10 ** 9), "deadline flag")
        values["all"].append(latency)
        ack = row["enqueue_ack_ns"]
        if ack is not None:
            require(row["offered_ns"] <= row["enqueue_started_ns"] <= ack <= row["enqueue_call_finished_ns"] <= complete, "enqueue chronology")
            values["enqueue_ack"].append(ack - row["planned_ns"])
        outcome, receipt = row["outcome"], row["receipt"]
        if receipt is not None:
            require(type(receipt) is dict and receipt["command_id"] == f"bench:{sequence}"
                and receipt["account_id"] == f"managed-probe-{sequence % 100}", "receipt identity for original arrival")
            integer(receipt["attempts"], 0, 1 << 63, "receipt attempts")
        if outcome == "financial_succeeded":
            require(receipt["state"] == "SUCCEEDED" and receipt["attempts"] == 0 and receipt["last_error"] is None and receipt["error"] is None, "invalid success receipt")
            require(receipt["command_id"] == row["command_id"] and receipt["account_id"] == row["account_id"], "receipt identity")
            result = strict_json(receipt["result"]) if isinstance(receipt["result"], str) else receipt["result"]
            require(result["status"] == "OPEN" and Fraction(result["filled_quantity"]) == 0
                and Fraction(result["reserved_margin"]) == Fraction(251, 25000), "success lacks live reserve")
            values[outcome].append(latency)
            late += latency > 10 ** 9
        elif outcome in ("business_rejected", "control_or_market_rejected"):
            require(receipt["state"] == "REJECTED", "rejection lacks terminal")
            error = strict_json(receipt["error"]) if isinstance(receipt["error"], str) else receipt["error"]
            integer(error["status"], 100, 599, "rejection status")
            require((error["status"] < 500) is (outcome == "business_rejected"), "rejection mix changed")
        counts[outcome] += 1
    require(dict(counts) == summary["outcome_counts"], "outcome counts differ from raw")
    require(all(summary["counts"][key] == count for key, count in counts.items()), "summary outcome count")
    require(summary["counts"]["durably_enqueued"] == len(values["enqueue_ack"])
        and summary["counts"]["financial_success_late"] == late, "ACK/late count")
    denominator_ns = max(footer["planned_duration_ns"], settled - start)
    elapsed = denominator_ns / 1e9
    require(math.isclose(summary["duration_including_terminal_observation_drain"], elapsed, rel_tol=1e-12), "observation/drain denominator")
    require(math.isclose(summary["drain_seconds"], max(0, elapsed - 10), abs_tol=1e-12), "drain arithmetic")
    require(math.isclose(summary["unique_observed_financial_success_per_s"], counts["financial_succeeded"] / elapsed, abs_tol=1e-12), "financial rate")
    require(math.isclose(summary["enqueue_ack_per_s_not_financial_success"], len(values["enqueue_ack"]) / elapsed, abs_tol=1e-12), "ACK rate")
    groups = {}
    for name, sample in values.items():
        ordered = sorted(sample)
        exact = {}
        for label, percentile in (("p50", Fraction(1, 2)), ("p95", Fraction(95, 100)), ("p99", Fraction(99, 100)), ("p99_9", Fraction(999, 1000))):
            ns = ordered[max(1, math.ceil(len(ordered) * percentile)) - 1] if ordered else None
            reported = summary["latency_ms"][name][label]
            require((ns is None and reported is None) or (ns is not None and reported is not None
                and ns <= Fraction(str(reported)) * 10 ** 6 <= Fraction(ns + 1) * Fraction(1001, 1000) + 1), "latency histogram understated/changed")
            exact[label] = ns
        groups[name] = {"N": len(sample), "max_ns": max(sample) if sample else None, "nearest_rank_ns": exact}
    environment, runtime = summary["environment"], summary["actual_runtime"]
    require(environment["code_commit"] == commit and environment["working_tree_dirty"] is False, "case not run on clean qualified source")
    require(environment["generator_sha256"] == source_hashes["benchmarks/run_managed_benchmark.py"], "generator source changed")
    require(environment["source_sha256"] == {name.removeprefix("uta/"): value for name, value in source_hashes.items() if name.startswith("uta/") and name.endswith(".py")}, "financial source bytes changed")
    settings = runtime["router_settings"]
    for key in ("account_batch", "matches_per_symbol", "max_attempts", "financial_batch_size", "normal_cache_size"):
        integer(settings[key], 0, 1 << 63, "worker setting." + key)
    require(settings == {"lease_seconds": 5.0, "poll_interval": .02, "background_interval": .1,
        "account_batch": 25, "matches_per_symbol": 10, "max_attempts": 3,
        "financial_batch_size": case.batch, "normal_cache_size": case.cache}, "actual worker settings differ")
    require(runtime["durable_batches_capability"] is runtime["decision_audit_required"] is True
        and runtime["financial_batch_soft_budget_seconds"] == .005 and runtime["physical_commit_counts_measured"] is False, "actual capability/audit/budget contract")
    children = summary["actual_spawned_worker_inputs"]
    for child in children:
        for key in ("account_batch", "matches_per_symbol", "max_attempts", "financial_batch_size", "normal_cache_size"):
            integer(child["received_settings"][key], 0, 1 << 63, "spawned setting." + key)
    for item in children + summary["initial_real_pid_and_fence"]["workers"]:
        integer(item["pid"], 2, (1 << 31) - 1, "worker PID")
        if "owner_pid" in item:
            integer(item["owner_pid"], 2, (1 << 31) - 1, "owner PID")
    require(len(children) == 2 and all(item["received_settings"] == settings for item in children), "spawned settings differ")
    pids = {item["pid"] for item in children}
    require(len(pids) == 2 and pids == {item["pid"] for item in summary["initial_real_pid_and_fence"]["workers"]}, "actual worker PID mismatch")
    require(all(item["pid"] == item["owner_pid"] and item["lease_active"] is True for item in summary["initial_real_pid_and_fence"]["workers"]), "owner fence mismatch")
    ro = summary["readonly_reconciliation"]
    require(ro["reopened_readonly"] is True and ro["persistent_successes"] == counts["financial_succeeded"]
        and ro["pending_count"] == ro["unobserved_successes_found_on_reopen"] == 0, "reopened financial reconciliation")
    require(len(ro["shards"]) == 2 and all(item["confirmed_matches"] == 0 and item["durable_batches_capability"] is True
        and item["audit_required"] is True and item["independent_reserve_account_version_ledger_verified"] is True for item in ro["shards"]), "RO capability/audit/ledger markers")
    reasons = []
    if late:
        reasons.append("raw_financial_success_late")
    if summary["probe_qualification"].get("financial_soft_deadline_passed") is not (late == 0):
        reasons.append("summary_deadline_flag_contradicts_raw")
    if not composite_gate(summary):
        reasons.append("technical_or_financial_soft_deadline_gate_failed")
    technical = summary["command_technical_diagnostics"]
    if not all(technical[key] == 0 for key in ("internal_execution_attempts", "commands_with_last_error", "quarantined_commands", "nonterminal_commands", "control_commands_not_succeeded")):
        reasons.append("internal_retry_unknown_control_failure")
    if summary["poll_errors"] or any("error" in item for item in summary["feed_publications"]):
        reasons.append("poll_feed_failure")
    if any(count and ("unknown" in key or "timeout" in key or "technical" in key) for key, count in summary["counts"].items()):
        reasons.append("technical_unknown_arrival")
    if not all(summary["batch_dispatch_diagnostics"][key] == 0 for key in ("failure_events", "recovered_batches", "unresolved_batches")):
        reasons.append("batch_retry_unknown")
    return {"counts": dict(counts), "financial_success_late": late, "groups": groups,
        "denominator_ns": denominator_ns, "financial_per_second": counts["financial_succeeded"] / elapsed,
        "technical_and_deadline_passed": not reasons, "stop_reasons": reasons, "physical_commit_counts_measured": False,
        "cache_hits_measured": False, "financial_database_reopened_by_this_JSON_checker": False,
        "summary_sha256": sha256(originals["summary.json"]).hexdigest(), "raw_sha256": sha256(originals["arrivals.jsonl.gz"]).hexdigest()}


def case_argv(source, directory, case):
    case.validate()
    return [sys.executable, str(Path(source) / "benchmarks/run_managed_benchmark.py"),
        "--output", str(directory), "--duration", "10", "--rate", "20", "--accounts", "100",
        "--shards", "2", "--cpu-limit", "2", "--durable-batches",
        "--financial-batch-size", str(case.batch), "--normal-cache-size", str(case.cache)]


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def forensic_counts(directory):
    """Retain counts even for failed/partial cases; this never grants a pass."""
    directory = Path(directory)
    path = directory / "arrivals.jsonl.gz"
    compressed = path.exists()
    if not compressed:
        path = directory / "arrivals.jsonl"
    if not path.exists():
        return {"available": False, "financial_verified": False}
    rows, partial_tail = bounded_arrivals(path, compressed=compressed, partial_tail=not compressed)
    groups = {name: [] for name in ("all", "financial_succeeded", "enqueue_ack")}
    for row in rows:
        integer(row["sequence"], 0, 199, "forensic arrival sequence")
        nanoseconds_and_sequences(row, "forensic arrival", nullable_ns=("enqueue_started_ns", "enqueue_ack_ns", "enqueue_call_finished_ns"))
        ns = integer(row["observed_completion_ns"] - row["planned_ns"], 0, 1 << 63, "forensic latency")
        groups["all"].append(ns)
        if row["outcome"] == "financial_succeeded":
            groups["financial_succeeded"].append(ns)
        if row.get("enqueue_ack_ns") is not None:
            groups["enqueue_ack"].append(integer(row["enqueue_ack_ns"] - row["planned_ns"], 0, 1 << 63, "forensic ACK latency"))
    denominator = None
    if (directory / "measurement-footer.json").exists():
        footer = read_json(directory / "measurement-footer.json")
        nanoseconds_and_sequences(footer, "forensic footer")
        beginning = integer(footer["started_monotonic_ns"], 1, 1 << 63, "forensic start")
        ending = integer(footer["terminal_observation_finished_monotonic_ns"], beginning, 1 << 63, "forensic settled")
        denominator = max(footer["planned_duration_ns"], ending - beginning)
        integer(denominator, 1, 1 << 63, "forensic denominator")
    return {"available": True, "financial_verified": False, "complete_compressed_file": compressed,
        "partial_tail_ignored_but_original_retained": partial_tail,
        "counts": dict(Counter(row["outcome"] for row in rows)),
        "groups": {name: {"N": len(sample), "max_ns": max(sample) if sample else None} for name, sample in groups.items()},
        "actual_footer_denominator_ns": denominator, "raw_sha256": digest(path)}


def execute(source, registration, registration_file):
    registration_bytes = read_blob(registration_file)
    require(strict_json(registration_bytes) == registration, "registration changed before validation")
    validate_registration(registration)
    require(registration["execution_go"] is True, "separate execution registration has no GO")
    source = Path(source).absolute()
    base_plan(source)
    snapshot = source_identity(source, registration["source_commit"])
    qualification(snapshot, registration, source=source)
    cpus = registration["cpu_ids"]
    require(set(cpus) <= os.sched_getaffinity(0), "registered CPUs unavailable")
    root = Path(registration["output_root"])
    require(not root.exists() and root.parent.is_dir() and root.resolve() == root, "output must be a new canonical path under an existing parent")
    require(not root.is_relative_to(source) and not source.is_relative_to(root), "output overlaps frozen source")
    require(all(not root.is_relative_to(Path(host["heartbeat"]).parent) for host in registration["cohosts"]), "output overlaps cohost evidence")
    before = {"cohosts": cohost_observations(registration["cohosts"]), "resources": resources(registration, root)}
    # No output directory or financial process exists before all above gates.
    root.mkdir()
    (root / "logs").mkdir()
    (root / "cases").mkdir()
    (root / "registration.json").write_bytes(registration_bytes)
    write_json(root / "preflight.json", {"registration_file_sha256": sha256(registration_bytes).hexdigest(),
        "source_commit": registration["source_commit"], "source_sha256": snapshot,
        "runner_pid": os.getpid(), "runner_process": process_identity(os.getpid()),
        "cpu_ids": cpus, "cohosted_no_cpuset_isolation": True, "before": before})
    os.sched_setaffinity(0, cpus)
    records, failure = [], None
    for case in schedule():
        record = {"case": case.__dict__, "started_utc": datetime.now(timezone.utc).isoformat(), "state": "NOT_STARTED"}
        directory = root / "cases" / case.case_id
        try:
            require(read_blob(registration_file) == registration_bytes, "execution registration changed")
            require(source_identity(source, registration["source_commit"]) == snapshot, "source drift before case")
            record["before"] = {"cohosts": cohost_observations(registration["cohosts"]), "resources": resources(registration, root)}
            last_health = [0.0]
            def health():
                if time.monotonic() - last_health[0] < .2:
                    return
                last_health[0] = time.monotonic()
                cohost_observations(registration["cohosts"])
                resources(registration, root)
                case_size = tree_bytes(directory) + sum(path.stat().st_size for path in (root / "logs").glob(case.case_id + ".*"))
                require(case_size <= registration["limits"]["case_bytes"], "combined financial/log output case cap")
            limits = registration["limits"]
            record["state"] = "START_ATTEMPTED"
            child = owned_run(case_argv(source, directory, case), source, root / "logs" / case.case_id,
                cpu_ids=cpus, wall_seconds=limits["case_wall_seconds"], grace_seconds=limits["grace_seconds"],
                kill_wait_seconds=limits["kill_wait_seconds"], output_cap=limits["case_bytes"],
                protected={host["pid"] for host in registration["cohosts"]}, health_check=health)
            record["child"] = child
            require(child["outcome"] == "EXITED" and child["stdout_stderr_complete"] is True, "child UNKNOWN; preserve original raw")
            last_health[0] = 0.0
            health()
            record["recomputed"] = recompute(directory, case, snapshot, registration["source_commit"])
            require(child["returncode"] == 0 and record["recomputed"]["technical_and_deadline_passed"], "stop after child, technical OR latency gate failure")
            require(source_identity(source, registration["source_commit"]) == snapshot, "source drift after case")
            require(read_blob(registration_file) == registration_bytes, "execution registration changed during case")
            record["after"] = {"cohosts": cohost_observations(registration["cohosts"]), "resources": resources(registration, root)}
            record.update(passed=True, state="VERIFIED_SHORT_CASE")
        except BaseException as error:
            record.update(passed=False, outcome="REFUSED" if record["state"] == "NOT_STARTED" else "FAILED_OR_UNKNOWN",
                          failure_type=type(error).__name__, failure=str(error))
            try:
                record["unqualified_forensic_counts"] = forensic_counts(directory)
            except Exception as forensic_error:
                record["unqualified_forensic_counts"] = {"available": False, "error": str(forensic_error)}
            failure = str(error)
        record["finished_utc"] = datetime.now(timezone.utc).isoformat()
        records.append(record)
        write_json(root / "execution.json", {"registration_id": registration["registration_id"],
            "source_commit": registration["source_commit"], "base_plan_sha256": PLAN_HASH,
            "cases": records, "stopped": failure is not None, "failure": failure,
            "all_short_diagnostics_passed": failure is None and len(records) == len(schedule()),
            "production_approved": False, "capacity_10000_per_s_passed": False,
            "scope": "local SDK admission only; no fills/REST/TLS/replica; physical COMMIT/cache hits unmeasured"})
        if failure is not None:
            break
    return failure is None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--registration", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    try:
        registration = read_json(args.registration) if args.registration else None
        if not args.execute:
            print(json.dumps(prepare(args.source, registration), indent=2))
            return 0
        require(registration is not None, "execute requires an independent registration")
        return 0 if execute(args.source, registration, args.registration) else 2
    except (GateError, KeyError, TypeError, OSError, ValueError, subprocess.SubprocessError, zipfile.BadZipFile, tarfile.TarError) as error:
        print(json.dumps({"mode": "REFUSED", "error": str(error), "production_approved": False}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
