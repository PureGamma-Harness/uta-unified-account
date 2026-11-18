"""PR62 first-CI data readers. No repository target code is imported or executed."""
from __future__ import annotations

import ast
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import zipfile
import urllib.request

SOURCE = "72dd3a17d7a8e363d95854ee8c4f361e0a24d901"
SOURCE_TREE = "0714e6a0c3cfe6a0cfc52ca31121c819e6575590"
RAW_CAP = 128 * 1024 * 1024
FILE_CAP = 256
ARCHIVE_CAP = 64 * 1024 * 1024
OUTER_CAP = 64 * 1024 * 1024
SMALL_EXPANSION_CAP = 8 * 1024 * 1024


def download_from_response(response_path, destination, expected_size, expected_digest, raw_root):
    """Download a private File Service reference without logging its signed URL."""
    value = json.loads(Path(response_path).read_text())["structuredContent"]
    reference = value["file_uri"]
    url = reference["download_url"]
    assert url.startswith("https://")
    current = inventory(raw_root)
    assert len(current) + 1 <= FILE_CAP
    assert 0 <= expected_size <= ARCHIVE_CAP
    assert sum(item["bytes"] for item in current) + expected_size <= RAW_CAP
    digest = sha256()
    amount = 0
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as output, urllib.request.urlopen(url, timeout=30) as response:
        length = response.headers.get("Content-Length")
        assert length is None or int(length) == expected_size
        while True:
            data = response.read(min(65536, expected_size - amount + 1))
            amount += len(data)
            assert amount <= expected_size
            if not data:
                break
            output.write(data)
            digest.update(data)
    assert amount == expected_size
    assert digest.hexdigest() == expected_digest.removeprefix("sha256:")
    return {"artifact_id": value["artifact_id"], "bytes": amount,
            "sha256": digest.hexdigest(), "provider_size_and_digest_match": True}


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(data)


def provider_data(path):
    value = json.loads(Path(path).read_text())
    assert not value.get("isError"), "provider returned an error"
    data = value.get("structuredContent", {})
    if isinstance(data.get("content"), str):
        return json.loads(data["content"])
    return data


def inventory(root):
    result = []
    for path in sorted(Path(root).rglob("*")):
        assert not path.is_symlink()
        if path.is_file():
            digest = sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(65536), b""):
                    digest.update(chunk)
            result.append({"opaque_id": len(result) + 1,
                           "relative_private_path": path.relative_to(root).as_posix(),
                           "bytes": path.stat().st_size,
                           "sha256": digest.hexdigest(),
                           "mode": oct(stat.S_IMODE(path.stat().st_mode))})
    assert len(result) <= FILE_CAP
    assert sum(item["bytes"] for item in result) <= RAW_CAP
    return result


def read_small_zip(archive, destination, ledger):
    """One bounded read per member; original raw bytes and complete CRC are retained."""
    archive, destination = Path(archive), Path(destination)
    assert archive.stat().st_size <= ARCHIVE_CAP
    with zipfile.ZipFile(archive) as source:
        entries = source.infolist()
        assert len(entries) <= 16000
        names = set()
        for member in entries:
            name = member.filename
            path = PurePosixPath(name)
            assert name and not path.is_absolute() and ".." not in path.parts
            assert "\\" not in name and name not in names
            assert not stat.S_ISLNK(member.external_attr >> 16)
            names.add(name)
            if member.is_dir():
                continue
            assert member.file_size <= SMALL_EXPANSION_CAP
            assert ledger["small_member_output_bytes"] + member.file_size <= SMALL_EXPANSION_CAP
            assert ledger["outer_member_output_bytes"] + member.file_size <= OUTER_CAP
            output = destination.joinpath(*path.parts)
            output.parent.mkdir(parents=True, exist_ok=True)
            digest = sha256()
            amount = 0
            fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as target, source.open(member) as stream:
                while True:
                    remaining = member.file_size - amount
                    chunk = stream.read(min(65536, remaining + 1))
                    ledger["outer_member_output_bytes"] += len(chunk)
                    ledger["small_member_output_bytes"] += len(chunk)
                    assert ledger["outer_member_output_bytes"] <= OUTER_CAP
                    assert ledger["small_member_output_bytes"] <= SMALL_EXPANSION_CAP
                    amount += len(chunk)
                    assert amount <= member.file_size
                    if not chunk:
                        break
                    target.write(chunk)
                    digest.update(chunk)
            assert amount == member.file_size
            ledger["reads"].append({"archive": archive.name, "member": name,
                                    "bytes": amount, "sha256": digest.hexdigest(),
                                    "crc32": f"{member.CRC:08x}", "CRC_verified": True,
                                    "read_ordinal": 1})
    return names


def git_bytes(worktree, path):
    return subprocess.check_output(["git", "show", SOURCE + ":" + path], cwd=worktree)


def unit_projection(directory, event, worktree):
    files = {path.name: path for path in Path(directory).rglob("*") if path.is_file()}
    assert set(files) == {"summary.json", "worker-result.json", "unittest.txt"}
    summary = json.loads(files["summary.json"].read_text())
    worker = json.loads(files["worker-result.json"].read_text())
    log = files["unittest.txt"].read_bytes()
    assert sha256(log).hexdigest() == summary["test_log_sha256"]
    before = summary["source_sha256"]
    after = summary["source_sha256_after"]
    bindings = []
    assert before == after
    for path, expected in sorted(before.items()):
        blob = git_bytes(worktree, path)
        actual = sha256(blob).hexdigest()
        assert actual == expected
        blob_id = subprocess.check_output(["git", "rev-parse", SOURCE + ":" + path], cwd=worktree, text=True).strip()
        bindings.append({"path": path, "bytes": len(blob), "git_blob": blob_id, "sha256": actual})
    allowed = ("code_commit", "python", "sqlite", "tests_run", "failures", "errors", "skipped",
               "expected_failures", "unexpected_successes", "unittest_passed", "worker_exit_code",
               "passed", "source_unchanged", "tracked_source_clean_before", "tracked_source_clean_after")
    projection = {key: summary.get(key) for key in allowed}
    projection.update({"event": event, "test_log_bytes": len(log),
                       "test_log_sha256": sha256(log).hexdigest(),
                       "source_files": len(before), "all_source_hashes_match_fixed_git": True,
                       "worker_summary_fields_match": all(summary.get(k) == worker.get(k)
                           for k in ("tests_run", "failures", "errors", "skipped", "unittest_passed")),
                       "production_approved": False})
    # Only identifiers already present in the public tracked source may leave private storage.
    expected_methods = set()
    component = {}
    for name in ("tests/test_market_transition_pending.py", "tests/test_market_transition_activation_failures.py"):
        tree = ast.parse(git_bytes(worktree, name), filename=name)
        component[name] = sorted(node.name for node in ast.walk(tree)
                                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                                 and node.name.startswith("test_"))
    for methods in component.values():
        expected_methods.update(methods)
    observed = []
    for line in log.decode("utf-8").splitlines():
        match = re.match(r"^(test_[A-Za-z0-9_]+) \(([^()]+)\) \.\.\. ok$", line)
        if match and match.group(1) in expected_methods:
            observed.append({"method": match.group(1), "test_id": match.group(2), "result": "plain_ok"})
    projection["component_explicit_plain_ok_observations"] = observed
    projection["component_source_method_counts"] = {path: len(methods) for path, methods in component.items()}
    projection["complete_log_plain_ok_count"] = sum(bool(re.match(r"^test_[A-Za-z0-9_]+ \([^()]+\) \.\.\. ok$", line))
                                                    for line in log.decode("utf-8").splitlines())
    projection["custom_component_receipt_capture"] = "NOT_RUN"
    return projection, bindings


def job_unit_summary(path):
    original = json.loads(Path(path).read_text())["structuredContent"]["content"]
    text = "\n".join(re.sub(r"^\S+Z ?", "", line) for line in original.splitlines())
    values = []
    decoder = json.JSONDecoder()
    for position, character in enumerate(text):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[position:])
        except ValueError:
            continue
        if isinstance(value, dict) and "tests_run" in value:
            values.append(value)
    assert len(values) == 1
    allowed = ("code_commit", "tests_run", "failures", "errors", "skipped", "passed",
               "worker_exit_code", "unittest_passed", "source_unchanged",
               "tracked_source_clean_before", "tracked_source_clean_after")
    return {key: values[0].get(key) for key in allowed}


def failure_projection(directory, worktree):
    """Whitelist test/source identifiers; do not copy runtime binding values or raw tails."""
    log = next(Path(directory).rglob("unittest.txt")).read_text()
    public_paths = set(subprocess.check_output(["git", "ls-tree", "-r", "--name-only", SOURCE],
                                               cwd=worktree, text=True).splitlines())
    public_literals = set()
    for name in ("uta/sharding.py", "tests/native_sh_capture_fixture.py", "tests/test_durable_faults.py"):
        public_literals.update(node.value for node in ast.walk(ast.parse(git_bytes(worktree, name)))
                               if isinstance(node, ast.Constant) and isinstance(node.value, str))
    parts = re.split(r"(?m)^(?=(?:ERROR|FAIL): )", log)
    observations = []
    for part in parts[1:]:
        lines = part.splitlines()
        match = re.match(r"^(ERROR|FAIL): (test_[A-Za-z0-9_]+) \(([A-Za-z0-9_.]+)\)", lines[0])
        assert match
        record = {"kind": match[1], "method": match[2], "test_id": match[3],
                  "frames": [], "exception_type": None, "public_literal_message": None}
        for line in lines[1:]:
            frame = re.search(r'/(tests|uta|tools)/([A-Za-z0-9_./-]+\.py)", line ([0-9]+), in ([A-Za-z0-9_]+)', line)
            if frame:
                name = frame[1] + "/" + frame[2]
                assert name in public_paths
                record["frames"].append({"path": name, "line": int(frame[3]), "function": frame[4]})
            error = re.match(r"^([A-Za-z_.]+(?:Error|Mismatch|Lost|Violation|Timeout|Failure)):\s*(.*)$", line)
            if error:
                record["exception_type"] = error[1]
                if error[2] in public_literals:
                    record["public_literal_message"] = error[2]
            if line.startswith("Ran "):
                break
        observations.append(record)
    summary = json.loads(next(Path(directory).rglob("summary.json")).read_text())
    return {"observations": observations, "first_failure_cause": "UNDETERMINED",
            "lease_observation_count": len(summary.get("lease_observations", [])),
            "lease_observations_truncated": summary.get("lease_observations_truncated"),
            "raw_failure_tracebacks_retained_privately": True}
