"""Review immutable workflow blobs only: YAML, AST and bash -n, never build."""
import ast
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess

import yaml

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).resolve().parent
COMMIT = "1eaefb89e0e161033abcd41b8538a7284657f20f"
FILES = [".github/workflows/ci.yml", "docs/automated-package-gates.md",
         "tools/verify_release_archives.py", "tools/validate_installed_release.py",
         "tests/test_durable_cli.py", ".gitignore"]


def git(*args):
    return subprocess.check_output(["git", "--no-optional-locks", *args], cwd=ROOT,
        stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)


blobs = {name: git("show", COMMIT + ":" + name) for name in FILES}
workflow = yaml.load(blobs[".github/workflows/ci.yml"], Loader=yaml.BaseLoader)
assert set(workflow["on"]) == {"push", "pull_request"}
job = workflow["jobs"]["test"]
assert job["runs-on"] == "ubuntu-latest"
assert job["strategy"]["matrix"]["python-version"] == ["3.10", "3.11", "3.12", "3.13"]
steps = job["steps"]
assert steps[0]["uses"] == "actions/checkout@v4"
assert "ref" not in steps[0].get("with", {})
assert not any("continue-on-error" in step for step in steps)
bash_results = []
python_heredocs = 0
for step in steps:
    if "run" not in step:
        continue
    script = step["run"]
    assert "${{" not in script, "GitHub expressions need an explicit substitution review"
    parsed = subprocess.run(["bash", "--noprofile", "--norc", "-n"], input=script.encode(),
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True,
        env={"PATH": "/usr/bin:/bin"}, timeout=5)
    assert parsed.returncode == 0, step["name"]
    bash_results.append({"step": step["name"], "exit_code": parsed.returncode,
        "stderr_bytes": len(parsed.stderr), "stderr_sha256": sha256(parsed.stderr).hexdigest()})
    for body in re.findall(r"python - <<'PY'\n(.*?)\nPY(?:\n|$)", script, re.DOTALL):
        ast.parse(body)
        python_heredocs += 1

named = {step.get("name"): (index, step) for index, step in enumerate(steps) if "name" in step}
names = ["Build installable wheel", "Build and verify exact source distribution and wheel",
         "Verify installed package outside source tree", "Preserve exact package and installed validation evidence",
         "Retain installable review artifact"]
indices = [named[name][0] for name in names]
assert indices == sorted(indices) and len(set(indices)) == len(indices)
archive = named[names[1]][1]
installed = named[names[2]][1]
evidence = named[names[3]][1]
review = named[names[4]][1]
assert '--commit "$GITHUB_SHA"' in archive["run"]
assert "github.event.pull_request.head.sha" not in blobs[".github/workflows/ci.yml"].decode()
assert '--wheel dist/*.whl --sdist dist/*.tar.gz' in archive["run"]
assert 'cd "$RUNNER_TEMP"' in installed["run"]
assert 'env -u PYTHONPATH "$RUNNER_TEMP/uta-smoke/bin/python" -I' in installed["run"]
assert "--identity-only" not in installed["run"]
assert "if" not in archive and "if" not in installed
assert evidence["if"] == "always()"
assert evidence["uses"] == review["uses"] == "actions/upload-artifact@v4"
allowlist = evidence["with"]["path"].splitlines()
expected = ["${{ runner.temp }}/uta-package-artifact-manifest.json",
            "${{ runner.temp }}/uta-installed-validation/installed-report.json",
            "${{ runner.temp }}/uta-installed-validation/installed-cli-tests.txt",
            "${{ runner.temp }}/uta-installed-validation/uta*.stdout.txt",
            "${{ runner.temp }}/uta-installed-validation/uta*.stderr.txt"]
assert allowlist == expected
assert review["with"]["path"].splitlines() == ["dist/*.whl", "dist/*.tar.gz"]
assert review["with"]["if-no-files-found"] == "error"


def uploaded(candidate):
    # A single * in an immediate filename does not cross a path separator.
    return any(re.fullmatch(re.escape(pattern).replace(r"\*", "[^/]*"), candidate) for pattern in allowlist)


private = ["${{ runner.temp }}/uta-installed-validation/empty-cli-authority/router.sqlite3",
           "${{ runner.temp }}/uta-installed-validation/empty-cli-authority/shard-0000.sqlite3-wal",
           "${{ runner.temp }}/uta-installed-validation/cert.pem",
           "${{ runner.temp }}/uta-installed-validation/key.pem",
           "${{ runner.temp }}/uta-installed-validation/signing.json",
           "${{ runner.temp }}/uta-managed-installed/router.sqlite3"]
assert not any(uploaded(path) for path in private)
assert uploaded("${{ runner.temp }}/uta-installed-validation/uta-demo.stdout.txt")
assert not any("**" in pattern for pattern in allowlist)
helper_tree = ast.parse(blobs["tests/test_durable_cli.py"])
case = next(node for node in helper_tree.body if isinstance(node, ast.ClassDef) and node.name == "DurableCLITests")
helper_tests = [node.name for node in case.body if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")]
assert len(helper_tests) == 7
checker = blobs["tools/validate_installed_release.py"].decode()
assert "result.testsRun == 8 and not result.skipped" in checker
assert 'FinancialProtocolCase("test_success_unknown_reply_and_offline_pending_survive_new_parent")' in checker
assert 'directory = output / "empty-cli-authority"' in checker
changed = git("diff-tree", "--no-commit-id", "--name-only", "-r", COMMIT).decode().splitlines()
assert changed == [".github/workflows/ci.yml", "docs/automated-package-gates.md"]
report = {"reviewed_commit": COMMIT, "scope": "independent_static_ci_package_contract_review",
    "file_sha256": {name: sha256(raw).hexdigest() for name, raw in blobs.items()},
    "changed_paths": changed, "yaml_parser": "PyYAML BaseLoader", "yaml_parser_version": yaml.__version__,
    "bash_syntax_checks": bash_results, "python_heredocs_syntax_checked": python_heredocs,
    "ordered_package_steps": names, "matrix_python_versions": job["strategy"]["matrix"]["python-version"],
    "artifact_report_allowlist": allowlist, "private_artifact_examples_matched": 0,
    "wheel_sdist_review_patterns": review["with"]["path"].splitlines(),
    "default_pr_checkout_and_actual_github_sha_preserved": True,
    "functional_checker_configured_without_identity_only": True,
    "static_expected_functional_cases": len(helper_tests) + 1,
    "runtime_or_database_migration_changes": False, "scoped_static_blockers": [],
    "builds_executed": 0, "workflow_runs_executed": 0, "services_started": 0,
    "sql_executed": 0, "runtime_tests_executed": 0,
    "package_result_proven": False, "production_approved": False}
(OUTPUT / "static-checks.json").write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
print(json.dumps({key: report[key] for key in ("reviewed_commit", "scoped_static_blockers", "builds_executed",
    "sql_executed", "runtime_tests_executed", "package_result_proven")}))
