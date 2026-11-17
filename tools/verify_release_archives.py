"""Compare release archives with an exact clean Git runtime tree, without install."""
from __future__ import annotations

import argparse
import ast
import configparser
from email.parser import BytesParser
from email.policy import compat32
from hashlib import sha256
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import zipfile


def digest(data):
    return sha256(data).hexdigest()


def declared_version(project_source, init_source):
    """Read this repository's controlled static declarations without execution.

    Python 3.10 has no tomllib. Accept canonical bare table/key names and one
    unescaped ASCII project.version string. Dynamic, duplicate, quoted/dotted
    keys and multiline TOML strings need an explicitly reviewed format change.
    The current package initializer contains only its docstring and version.
    """
    table, tables, keys, version = None, set(), set(), None
    literal = r"(?P<quote>['\"])(?P<version>[0-9][0-9A-Za-z.!+_-]{0,63})(?P=quote)"
    for raw in project_source.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if '"""' in line or "'''" in line:
            raise AssertionError("project.version requires controlled static TOML; multiline strings are unsupported")
        if line.startswith("["):
            header = re.fullmatch(r"\[([A-Za-z0-9_.-]+)\]\s*(?:#.*)?", line)
            if header is None:
                raise AssertionError("project.version requires canonical unquoted TOML tables")
            table = header[1]
            if table in tables:
                raise AssertionError("duplicate TOML table declaration")
            if table.split(".")[:2] in (["project", "version"], ["project", "dynamic"]):
                raise AssertionError("project.version must be one static string")
            tables.add(table)
            continue
        if table is None:
            raise AssertionError("project.version requires a canonical [project] table")
        if table != "project" or "=" not in line:
            continue
        assignment = re.match(r"([A-Za-z0-9_-]+)\s*=", line)
        if assignment is None:
            raise AssertionError("project.version requires unquoted bare project keys")
        key = assignment[1]
        if key in keys:
            raise AssertionError("duplicate project key declaration")
        keys.add(key)
        if key == "dynamic":
            raise AssertionError("project.version must be static; project.dynamic is unsupported")
        if key == "version":
            match = re.fullmatch(r"version\s*=\s*" + literal + r"\s*(?:#.*)?", line)
            if match is None:
                raise AssertionError("project.version must be one static ASCII string")
            version = match["version"]
    if "project" not in tables or version is None:
        raise AssertionError("frozen source must declare one static project.version")
    body = ast.parse(init_source, filename="uta/__init__.py").body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body = body[1:]
    if (len(body) != 1 or not isinstance(body[0], ast.Assign) or len(body[0].targets) != 1
            or not isinstance(body[0].targets[0], ast.Name) or body[0].targets[0].id != "__version__"
            or not isinstance(body[0].value, ast.Constant) or not isinstance(body[0].value.value, str)):
        raise AssertionError("uta.__version__ must be one static literal assignment")
    if body[0].value.value != version:
        raise AssertionError("frozen uta.__version__ differs from project.version")
    return version


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
    if not {"pyproject.toml", "uta/__init__.py"} <= set(paths):
        raise AssertionError("frozen source must track both release version declarations")
    if git("ls-files", "--others", "--exclude-standard"):
        raise AssertionError("release checkout contains untracked source files")
    project_source, init_source = (subprocess.check_output(
        ["git", "show", commit + ":" + name], cwd=root, text=True)
        for name in ("pyproject.toml", "uta/__init__.py"))
    version = declared_version(project_source, init_source)
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
        metadata_names = [name for name in wheel_names if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise AssertionError("wheel must contain exactly one METADATA file")
        metadata_name = metadata_names[0]
        metadata = BytesParser(policy=compat32).parsebytes(wheel.read(metadata_name), headersonly=True)
        metadata_versions = metadata.get_all("Version", [])
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
    checks = {"version": len(metadata_versions) == 1 and metadata_versions[0] == version,
        "wheel_runtime_exact": installed == runtime, "sdist_runtime_exact": source_runtime == runtime,
        "sdist_required_files_exact": not missing and not mismatched,
        "legacy_fixture_pinned": digest(fixture) == provenance["archive_sha256"],
        "legacy_fixture_licensed": licensed,
        "entry_points": dict(parsed_entries["console_scripts"]) == expected_entries}
    report = {"source_commit": commit, "version": version,
        "metadata_versions": metadata_versions, "runtime_files": runtime,
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
