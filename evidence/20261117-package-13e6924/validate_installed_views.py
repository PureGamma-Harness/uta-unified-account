"""Run three unchanged frozen read-view tests against an isolated installed wheel.

Fixtures perform explicitly synthetic financial setup. The original read-phase
assertions check financial rows remain unchanged and forbid writer construction.
The HMAC view case uses localhost HTTP; CLI TLS is covered by the separate eight
installed lifecycle/protocol tests. Original fixture and read assertions remain unchanged.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

import uta


SELECTED = (
    ("DurableViewTests", "test_all_read_resources_are_consistent_exact_and_never_initialize_financial_services"),
    ("DurableViewTests", "test_hmac_authenticated_reader_gets_only_its_own_view_without_financial_writes"),
    ("RouterReadTests", "test_existing_router_reads_only_owning_shard_without_financial_constructors"),
)


def installed_modules(site):
    modules = {}
    for name, module in sorted(sys.modules.items()):
        if name == "uta" or name.startswith("uta."):
            path = Path(module.__file__).resolve()
            if not path.is_relative_to(site):
                raise AssertionError(f"noninstalled financial import: {name}: {path}")
            modules[name] = str(path)
    return modules


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--artifact-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    site = Path(uta.__file__).resolve().parent.parent
    if not sys.flags.isolated or os.environ.get("PYTHONPATH"):
        raise AssertionError("invoke with python -I and PYTHONPATH unset")
    if site.is_relative_to(source) or source in map(Path, sys.path):
        raise AssertionError("source checkout must not be an import location")
    manifest = json.loads(args.artifact_manifest.read_text())
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    if commit != manifest["source_commit"]:
        raise AssertionError("source HEAD differs from artifact commit")
    if importlib.metadata.version("uta-reference-exchange") != manifest["version"]:
        raise AssertionError("installed version differs from artifact manifest")
    runtime = {str(path.relative_to(site)): sha256(path.read_bytes()).hexdigest()
               for path in (site / "uta").rglob("*")
               if path.is_file() and path.suffix in (".py", ".html")}
    digest = sha256(json.dumps(runtime, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if runtime != manifest["runtime_files"] or digest != manifest["runtime_tree_sha256"]:
        raise AssertionError("installed runtime differs from artifact manifest")
    original = source / "tests/test_durable_views.py"
    frozen_helper = subprocess.check_output(
        ["git", "show", commit + ":tests/test_durable_views.py"], cwd=source)
    if original.read_bytes() != frozen_helper:
        raise AssertionError("read-view helper differs from frozen source")
    installed_modules(site)
    output.mkdir(parents=True, exist_ok=False)
    copied = output / "frozen_test_durable_views.py"
    shutil.copyfile(original, copied)
    if copied.read_bytes() != frozen_helper:
        raise AssertionError("copied read-view helper differs from frozen source")
    spec = importlib.util.spec_from_file_location("frozen_test_durable_views", copied)
    helper = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = helper
    spec.loader.exec_module(helper)
    suite = unittest.TestSuite(getattr(helper, case)(name) for case, name in SELECTED)
    with (output / "installed-view-tests.txt").open("w") as log:
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    passed = result.wasSuccessful() and result.testsRun == len(SELECTED) and not result.skipped
    report = {
        "source_commit": commit, "scope": "three frozen installed read-view smoke tests",
        "artifacts": manifest["artifacts"], "version": uta.__version__,
        "runtime_tree_sha256": digest, "runtime_file_count": len(runtime),
        "isolated": bool(sys.flags.isolated), "pythonpath": os.environ.get("PYTHONPATH"),
        "interpreter": sys.version, "installed_site": str(site), "sys_path": sys.path,
        "helper_sha256": sha256(original.read_bytes()).hexdigest(),
        "copied_helper_sha256": sha256(copied.read_bytes()).hexdigest(),
        "selected_tests": [case + "." + name for case, name in SELECTED], "expected_tests": len(SELECTED),
        "tests": {"run": result.testsRun, "failures": len(result.failures),
                  "errors": len(result.errors), "skipped": len(result.skipped)},
        "modules": installed_modules(site), "passed": passed,
        "fixture_writes": "synthetic financial setup; read phases assert financial rows unchanged",
        "constructor_tripwires": "unchanged frozen tests reject writer/ledger initialization during reads",
        "hmac_view_transport": "localhost HTTP require_tls=False; auth nonce writes expected",
        "production_approved": False,
    }
    (output / "installed-views-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: report[key] for key in
                     ("source_commit", "runtime_tree_sha256", "tests", "passed", "production_approved")}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
