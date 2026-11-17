"""File/Git/AST-only review; never import product or sqlite3, or run tests."""
import ast
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess

BASE = "dbc93e5d50125e6ab8f1154511a537f8b1a8fa1b"
FIX = "5ff974d7cf32715452c4d205efa748e4e4b59f23"
ORIGINAL = "653270d9d41b5cbbd910f4a3d7e05899cde0efd7"
REPO = Path("/workspace/uta-ledger-py310-fixture")
ROOT = Path(__file__).resolve().parent
EVIDENCE = "evidence/runs/ledger-python310-authorizer-cleanup/"
FILES = ("tests/test_ledger_main_acceptance.py", "tests/test_ledger_main_schema.py")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=REPO)


def blob(ref, path):
    return git("show", ref + ":" + path)


def digest(data):
    return sha256(data).hexdigest()


def decoded(ref, path):
    return json.loads(blob(ref, path))


def main():
    assert git("rev-parse", "HEAD").decode().strip() == FIX
    assert git("status", "--porcelain", "--untracked-files=all") == b""
    paths = git("ls-tree", "-r", "--name-only", BASE).decode().splitlines()
    runtime = [name for name in paths if name.startswith("uta/") and name.endswith((".py", ".html"))]
    assert len(runtime) == 62
    runtime_hashes = {name: digest(blob(BASE, name)) for name in runtime}
    assert all(blob(FIX, name) == blob(BASE, name) for name in runtime)
    changes = []
    for path in FILES:
        before = ast.parse(blob(BASE, path))
        after = ast.parse(blob(FIX, path))
        replacements = []
        for node in ast.walk(after):
            if isinstance(node, ast.Try):
                for item in node.finalbody:
                    for call in ast.walk(item):
                        if (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                                and call.func.attr == "set_authorizer" and isinstance(call.func.value, ast.Name)
                                and call.func.value.id == "connection" and len(call.args) == 1
                                and isinstance(call.args[0], ast.Lambda)):
                            expected = ast.parse("lambda *_: sqlite3.SQLITE_OK", mode="eval").body
                            assert ast.dump(call.args[0], include_attributes=False) == ast.dump(expected, include_attributes=False)
                            replacements.append(call.lineno)
                            call.args[0] = ast.Constant(value=None)
        assert len(replacements) == 1
        assert ast.dump(before, include_attributes=False) == ast.dump(after, include_attributes=False)
        changes.append({"path": path, "cleanup_line": replacements[0], "single_finally_cleanup_only": True,
                        "whole_module_AST_restored_after_normalizing_cleanup": True,
                        "baseline_sha256": digest(blob(BASE, path)), "candidate_sha256": digest(blob(FIX, path))})
    changed = git("diff", "--name-only", BASE, FIX, "--", "uta", "tests").decode().splitlines()
    assert changed == list(FILES)
    scope = decoded(FIX, EVIDENCE + "scope.json")
    assert {row["path"]: row["sha256"] for row in scope["runtime_files"]} == runtime_hashes
    local = []
    for suffix, errors in (("baseline-python310", 11), ("candidate-python310", 0), ("candidate-python312", 0), ("candidate-python313", 0)):
        metadata = decoded(FIX, EVIDENCE + suffix + ".json")
        raw = blob(FIX, EVIDENCE + suffix + ".txt")
        text = raw.decode()
        assert metadata["exit_code"] == (1 if errors else 0)
        assert re.findall(r"Ran (\d+) tests? in ", text) == ["26"]
        assert len(re.findall(r"^test_.* \(.*\) \.\.\. ", text, re.M)) == 26
        assert (text.rstrip().endswith("FAILED (errors=11)") if errors else text.rstrip().endswith("OK"))
        assert metadata["command"][:3] == ["taskset", "-c", "3"]
        assert metadata["cwd"] == str(REPO)
        assert metadata["wall_seconds"] > 0 and datetime.fromisoformat(metadata["finished_at"]) > datetime.fromisoformat(metadata["started_at"])
        if not errors:
            assert metadata["base_source"] == BASE and metadata["dirty_test_only_patch"] is True
            assert metadata["test_hashes"] == {Path(row["path"]).name: row["candidate_sha256"] for row in changes}
        local.append({"case": suffix, "command": metadata["command"], "cwd": metadata["cwd"],
                      "started_at": metadata["started_at"], "finished_at": metadata["finished_at"],
                      "outer_wall_seconds": metadata["wall_seconds"], "tests": 26, "errors": errors,
                      "exit_code": metadata["exit_code"], "raw_sha256": digest(raw),
                      "executed_dirty_test_patch_bound_by_recorded_hashes": not errors})
    probes = {}
    for version in ("310", "312", "313"):
        record = decoded(FIX, EVIDENCE + "api-probe-" + version + ".json")
        assert record["exit_code"] == 0 and record["stderr"] == ""
        observed = json.loads(record["stdout"])
        assert observed["after_explicit_allow"] == [3]
        if version == "310":
            assert observed["after_none"] == {"type": "DatabaseError", "message": "not authorized", "sqlite_errorcode": None}
        else:
            assert observed["after_none"] == [2]
        ast.parse(record["command"][-1])  # inspect recorded scalar source; never execute it
        probes[version] = observed
    assert probes["310"]["sqlite"] == probes["312"]["sqlite"] == "3.53.1"
    original_index = decoded(ORIGINAL, "evidence/runs/dbc93e5-ci-integrity/priority-python310-errors.json")
    provider_merge = decoded(ORIGINAL, "evidence/runs/dbc93e5-ci-integrity/pr-merge-source.json")
    baseline_tree = git("rev-parse", BASE + "^{tree}").decode().strip()
    assert provider_merge["tree_sha"] == baseline_tree
    assert provider_merge["parents"][1] == BASE
    originals, cache = [], {}
    for run in original_index["original_runs"]:
        prefix = "evidence/runs/dbc93e5-ci-integrity/" + run["raw_directory"] + "/"
        summary = decoded(ORIGINAL, prefix + "summary.json")
        worker = decoded(ORIGINAL, prefix + "worker-result.json")
        log = blob(ORIGINAL, prefix + "unittest.txt")
        assert summary["tests_run"] == 1801 and summary["failures"] == 0 and summary["errors"] == 11 and summary["skipped"] == 0
        assert summary["passed"] is False and summary["unittest_passed"] is False
        assert all(summary[key] == worker[key] for key in worker)
        assert summary["test_log_sha256"] == digest(log) and log.rstrip().endswith(b"FAILED (errors=11)")
        assert len(run["original_errors"]) == 11 and all("sqlite3.DatabaseError: not authorized" in item["traceback"] for item in run["original_errors"])
        for item in run["raw_files"]:
            data = blob(ORIGINAL, "evidence/runs/dbc93e5-ci-integrity/" + item["path"])
            assert len(data) == item["bytes"] and digest(data) == item["sha256"]
        hashes = summary["source_sha256"]
        assert len(hashes) == 348 and hashes == summary["source_sha256_after"]
        for name, value in hashes.items():
            if name not in cache:
                cache[name] = digest(blob(BASE, name))
            assert cache[name] == value
        if summary["code_commit"] == BASE:
            tree_proof = {"kind": "actual_local_Git_tree", "tree_sha1": baseline_tree}
        else:
            assert summary["code_commit"] == provider_merge["sha"]
            tree_proof = {"kind": "retained_provider_tree_metadata_plus_348_actual_input_blob_hashes",
                          "tree_sha1": provider_merge["tree_sha"], "local_PR_merge_object_verified": False}
        originals.append({"run_id": run["run_id"], "original_code_commit": summary["code_commit"], "tests": 1801,
                          "errors": 11, "failures": 0, "passed": False, "exact_348_inputs_match_original_tree": True,
                          "original_log_sha256": digest(log), "tree_proof": tree_proof,
                          "error_headers": [item["header"] for item in run["original_errors"]]})
    report = {"verdict": "ACCEPT_TWO_TEST_CLEANUP_COMPATIBILITY_CHANGES_ONLY", "baseline": BASE, "fix": FIX,
              "original_failure_evidence": ORIGINAL, "changes": changes, "all_original_assertions_and_strict_TEMP_deny_verification_preserved": True,
              "runtime_62_byte_identical": runtime_hashes, "runtime_tree_sha256": digest(json.dumps(runtime_hashes, sort_keys=True, separators=(",", ":")).encode()),
              "original_CI_failures": originals, "local_author_results": local, "recorded_scalar_probes": probes,
              "independent_runtime_rerun": False, "review_SQL_or_product_imports": False, "original_source_or_raw_modified": False,
              "review_scope": "pure AST/Git/raw bytes; no tests or scalar probes executed by reviewer",
              "full_successor_QA_CI_package_acceptance": "PENDING_NEW_EXACT_SOURCE_GATES", "overall": "NO_GO", "production_approved": False}
    path = ROOT / "review.json"
    assert not path.exists()
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: report[key] for key in ("verdict", "fix", "runtime_tree_sha256", "overall", "production_approved")}, indent=2))


if __name__ == "__main__":
    main()
