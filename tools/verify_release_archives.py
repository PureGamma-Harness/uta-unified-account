"""Compare release archives with an exact clean Git runtime tree, without install."""
from __future__ import annotations

import argparse
import configparser
from hashlib import sha256
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
import zipfile


def digest(data):
    return sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--sdist", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.source.resolve()
    def git(*command):
        return subprocess.check_output(["git", *command], cwd=root, text=True).strip()
    commit = git("rev-parse", args.commit)
    if git("rev-parse", "HEAD") != commit or git("diff", "--name-only", commit, "--"):
        raise AssertionError("release checkout HEAD/runtime/manifest differs from the frozen commit")
    paths = git("ls-tree", "-r", "--name-only", commit).splitlines()
    runtime = {name: digest((root / name).read_bytes()) for name in paths
               if name.startswith("uta/") and name.endswith((".py", ".html"))}
    # The release contract includes every tracked source/evidence path. New
    # suffixes must become an explicit packaging choice rather than disappear.
    required = paths
    with zipfile.ZipFile(args.wheel) as wheel:
        wheel_names = wheel.namelist()
        if len(wheel_names) != len(set(wheel_names)):
            raise AssertionError("duplicate wheel archive member")
        wheel_runtime_names = {name for name in wheel_names
                               if name.startswith("uta/") and name.endswith((".py", ".html"))}
        if wheel_runtime_names - runtime.keys():
            raise AssertionError("unexpected wheel runtime file")
        installed = {name: digest(wheel.read(name)) for name in wheel.namelist()
                     if name.startswith("uta/") and name.endswith((".py", ".html"))}
        metadata_name = next(name for name in wheel.namelist() if name.endswith(".dist-info/METADATA"))
        metadata = wheel.read(metadata_name).decode()
        entry_points = wheel.read(metadata_name.removesuffix("METADATA") + "entry_points.txt").decode()
    parsed_entries = configparser.ConfigParser(interpolation=None)
    parsed_entries.read_string(entry_points)
    expected_entries = {"uta": "uta.__main__:main", "uta-ops": "uta.ops:main", "uta-durable": "uta.durable_cli:main"}
    with tarfile.open(args.sdist) as source:
        archive_members = source.getmembers()
        names = [item.name for item in archive_members]
        if len(names) != len(set(names)):
            raise AssertionError("duplicate source distribution member")
        for item in archive_members:
            if PurePosixPath(item.name).is_absolute() or ".." in PurePosixPath(item.name).parts or not (item.isdir() or item.isfile()):
                raise AssertionError("unsafe source distribution member")
        prefix = archive_members[0].name.split("/")[0] + "/"
        if any(item.name != prefix.rstrip("/") and not item.name.startswith(prefix) for item in archive_members):
            raise AssertionError("source distribution members must share one root directory")
        members = {item.name.removeprefix(prefix): item for item in archive_members if item.isfile()}
        source_runtime_names = {name for name in members
                                if name.startswith("uta/") and name.endswith((".py", ".html"))}
        if source_runtime_names - runtime.keys():
            raise AssertionError("unexpected source distribution runtime file")
        missing = sorted(set(required) - members.keys())
        mismatched = [name for name in required if name in members and source.extractfile(members[name]).read() != (root / name).read_bytes()]
        source_runtime = {name: digest(source.extractfile(item).read()) for name, item in members.items()
                          if name.startswith("uta/") and name.endswith((".py", ".html"))}
        fixture = source.extractfile(members["tests/fixtures/legacy_ad3f5b8_uta.tar.gz"]).read()
        provenance = json.loads(source.extractfile(members["tests/fixtures/legacy_ad3f5b8_provenance.json"]).read())
        with tarfile.open(fileobj=io.BytesIO(fixture), mode="r:gz") as original:
            licensed = "LICENSE" in original.getnames()
    checks = {"version": "Version: 0.4.0a1\n" in metadata,
        "wheel_runtime_exact": installed == runtime, "sdist_runtime_exact": source_runtime == runtime,
        "sdist_required_files_exact": not missing and not mismatched,
        "legacy_fixture_pinned": digest(fixture) == provenance["archive_sha256"],
        "legacy_fixture_licensed": licensed,
        "entry_points": dict(parsed_entries["console_scripts"]) == expected_entries}
    report = {"source_commit": commit, "version": "0.4.0a1", "runtime_files": runtime,
        "runtime_tree_sha256": digest(json.dumps(runtime, sort_keys=True, separators=(",", ":")).encode()),
        "sdist_required_files": required, "sdist_missing": missing, "sdist_mismatched": mismatched,
        "sdist_member_count": len(members), "legacy_fixture_provenance": provenance, "entry_points": entry_points,
        "cli_helper_sha256": digest((root / "tests/test_durable_cli.py").read_bytes()),
        "checks": checks, "passed": all(checks.values()), "production_approved": False,
        "artifacts": {path.name: {"sha256": digest(path.read_bytes()), "bytes": path.stat().st_size}
                      for path in (args.wheel, args.sdist)}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({name: report[name] for name in ("source_commit", "runtime_tree_sha256", "checks", "sdist_missing", "passed")}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
