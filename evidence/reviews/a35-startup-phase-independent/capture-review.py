"""Static evidence collection only: git objects, test ASTs and retained CI files."""
import ast
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
BASE = "a35fd56fc98126b3e5cced8a459bd04ca580e537"
SUBJECT = "ed1f1414b3f28aa1ff41b4d7e74b12b565a32c3f"
TEST = "tests/test_owned_startup_reference.py"
POSITIVE = "test_old_inflight_writer_is_drained_before_complete_ro_replay"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def methods(content):
    return {node.name: ast.dump(node, include_attributes=False)
            for cls in ast.parse(content).body if isinstance(cls, ast.ClassDef)
            for node in cls.body if isinstance(node, ast.FunctionDef)}


before = methods(git("show", BASE + ":" + TEST))
after = methods((ROOT / TEST).read_bytes())
original = ROOT / "evidence/runs/a35-startup-phase"
old_summary = json.loads((original / "summary.json").read_text())
inputs = old_summary["source_sha256"]
mismatches = [name for name, digest in inputs.items()
              if sha256(git("show", BASE + ":" + name)).hexdigest() != digest]
archive = Path("/workspace/uta-ci-a35-startup-phase/evidence/runs/a35-startup-phase/original-ci-artifact.zip")
with zipfile.ZipFile(archive) as z:
    archive_matches = {name: z.read(name) == (original / name).read_bytes()
                       for name in ("summary.json", "worker-result.json", "unittest.txt")}
changed = [name for name in before.keys() | after.keys() if before.get(name) != after.get(name)]
scope = ("uta", "tests", "formal", "tools", "benchmarks", "scripts", "pyproject.toml", "MANIFEST.in", "LICENSE")
changed_inputs = git("diff", BASE, SUBJECT, "--name-only", "--", *scope).decode().splitlines()
record = dict(
    reviewed_commit=SUBJECT, baseline_commit=BASE,
    original_ci_commit=old_summary["code_commit"], original_tests_run=old_summary["tests_run"],
    original_errors=old_summary["errors"], original_passed=old_summary["passed"],
    original_source_inputs_checked=len(inputs), original_source_mismatches=mismatches,
    original_source_before_after_match=inputs == old_summary["source_sha256_after"],
    changed_source_inputs=changed_inputs, changed_reference_methods=sorted(changed),
    other_reference_test_methods_unchanged=sum(name.startswith("test_") and name not in changed for name in before),
    unchanged_contention_test_methods=sum(name.startswith("test_") for name in methods(
        (ROOT / "tests/test_startup_write_contention.py").read_bytes())),
    tracked_source_clean_after_tests=not git("diff", "HEAD", "--", *scope),
    external_original_archive=dict(path=str(archive), exists=archive.is_file(),
        sha256=sha256(archive.read_bytes()).hexdigest(), size_bytes=archive.stat().st_size,
        copied_into_this_review=False, original_members_match_committed_evidence=archive_matches),
    retained_evidence_sha256={p.name: sha256(p.read_bytes()).hexdigest() for p in sorted(original.iterdir()) if p.is_file()},
    no_runtime_change=changed_inputs == [TEST],
    only_positive_reference_method_changed=changed == [POSITIVE],
    unique_historical_scheduling_cause_proven=False,
    full_qualification=False, production_approved=False,
)
(OUT / "static-review.json").write_text(json.dumps(record, indent=2) + "\n")
assert not mismatches and all(archive_matches.values())
assert record["no_runtime_change"] and record["only_positive_reference_method_changed"]
print(json.dumps({k: v for k, v in record.items() if k != "retained_evidence_sha256"}, indent=2))
