"""Immutable Git blobs / AST only; no target import or test execution."""
import ast
import fnmatch
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess

C = "a365f37e23e1c0ce75e403062344a5f482c9a3cf"
FS = "3cc254db1d59f805a6d64825d75360a7f31aad41"
BASE = "6010e920a168b35fccfc9ef9ee34e030b28b11d9"
WORKLOAD = "909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0"


def git(*args):
    return subprocess.check_output(["git", *args])


def blob(ref, path):
    return git("show", ref + ":" + path)


def functions(raw):
    return {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(raw).body
            if isinstance(n, (ast.FunctionDef, ast.ClassDef))}


def parse_sparse(raw):
    lines = raw.decode().splitlines()
    result = []
    for index, line in enumerate(lines):
        if line.strip() == "sparse-checkout: |":
            selected = []
            for following in lines[index + 1:]:
                if not following.startswith("            "):
                    break
                selected.append(following.strip().lstrip("/"))
            result.append(selected)
    return result


controller = blob(C, "tools/independent_m0_controller.py")
expected = blob(FS, "tools/independent_m0_controller.py").replace(
    b"APPROVED_BRANCH = 'refs/heads/perf/approved-m0-20261117-04'",
    b"APPROVED_BRANCH = 'refs/heads/perf/approved-m0-20261117-05'").replace(
    b"REGISTRATION_ID = 'independent-m0-20261117-04'",
    b"REGISTRATION_ID = 'independent-m0-20261117-05'")
assert controller == expected
assert functions(controller) == functions(blob(FS, "tools/independent_m0_controller.py"))
tree = ast.parse(controller)
manifest_function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "validate_once_manifest")
schema = ast.literal_eval(manifest_function.body[0].value)
template_path = "evidence/preparations/m05-control-integration/once05-registration-template.json"
policy_path = "evidence/preparations/m05-control-integration/policy.json"
template = json.loads(blob(C, template_path))
policy = json.loads(blob(C, policy_path))
assert set(template) == schema and len(schema) == 19
assert template["execution_authorized"] is False and template["control_commit"] == "0" * 40
assert policy["next_run_permitted"] is False and policy["all_component_CODE_reviews_closed"] is False
assert policy["combined_new_tree_PURE"] == "NOT_RUN_REQUIRES_SEPARATE_ROOT_BUDGET"
assert template["source_commit"] == WORKLOAD and template["source_tree"] == git("rev-parse", WORKLOAD + "^{tree}").decode().strip()
assert template["controller_sha256"] == sha256(controller).hexdigest()
old_template = json.loads(blob(FS, "docs/evidence/independent-actions-m0/once04-registration-template.json"))
assert template["budgets"] == old_template["budgets"] and template["command_spec"] == old_template["command_spec"]
assert git("ls-tree", C, "config/independent-m0-approved.json") == b""
assert git("log", "--format=", "--name-status", WORKLOAD + ".." + C, "--", "config/independent-m0-approved.json").strip() == b""
assert git("diff", "--name-only", BASE, C, "--", "uta") == b""
files = git("ls-tree", "-r", "--name-only", C, "tests").decode().splitlines()
tests = sorted(p for p in files if fnmatch.fnmatch(Path(p).name, "test_independent_m0_*.py"))
assert len(tests) == 9
test_asts = {p: ast.parse(blob(C, p)) for p in tests}
checkout = test_asts["tests/test_independent_m0_checkout_ref.py"]
workflows_method = next(n for n in ast.walk(checkout) if isinstance(n, ast.FunctionDef) and n.name == "workflows")
reads_both = any(isinstance(n, ast.Tuple) and [getattr(e, "value", None) for e in n.elts] ==
                 ["independent-m0-once.yml", "independent-m0.yml"] for n in ast.walk(workflows_method))
assert reads_both
deps = tests + ["tools/independent_m0_controller.py", "tools/m0_stream_escrow.py", "tools/cold_import_contract.py",
                "config/m0-stream-recipient-public.pem", "config/m0-stream-recipient-public-metadata.json",
                ".github/workflows/independent-m0-once.yml", ".github/workflows/independent-m0.yml"]
workflows = {}
for path in (".github/workflows/independent-m0-once.yml", ".github/workflows/independent-m0.yml"):
    raw = blob(C, path)
    sparse_sets = parse_sparse(raw)
    control = next(s for s in sparse_sets if "tools/independent_m0_controller.py" in s)
    blocks = re.split(r"(?m)^      - ", raw.decode())[1:]
    target = [b for b in blocks if re.search(r"(?m)^          path: workload$", b)]
    assert len(target) == 1
    refs = re.findall(r"(?m)^          ref: (.*)$", target[0])
    assert refs == [WORKLOAD]
    workflows[path] = {"sha256": sha256(raw).hexdigest(), "control_sparse_paths": control,
                       "matched_test_count": sum(p in control for p in tests),
                       "missing_dependencies": sorted(set(deps) - set(control)),
                       "workload_ref": refs[0], "discovery_command": next(l.strip() for l in raw.decode().splitlines() if "python -m unittest discover" in l)}
assert workflows[".github/workflows/independent-m0-once.yml"]["missing_dependencies"] == []
assert workflows[".github/workflows/independent-m0.yml"]["missing_dependencies"] == [".github/workflows/independent-m0-once.yml"]
for name, path in (("workflow_sha256", ".github/workflows/independent-m0-once.yml"),
                   ("escrow_tool_sha256", "tools/m0_stream_escrow.py"),
                   ("recipient_certificate_sha256", "config/m0-stream-recipient-public.pem")):
    assert template[name] == sha256(blob(C, path)).hexdigest()
result = {"review": "CODE_ONLY_STATIC_NO_TARGET_IMPORT", "preview": C,
          "preview_parent": git("rev-list", "--parents", "-n", "1", C).decode().split()[1:],
          "controller_sha256": sha256(controller).hexdigest(), "controller_only_two_namespace_literals_changed": True,
          "equal_top_level_class_and_function_AST_count": len(functions(controller)),
          "FS_CODE_closed_by_separate_OWN": "837bd0ac8c43550590d8637000dea18db746d3ff",
          "pending_preview_policy_not_rewritten": True,
          "template": {"fields": len(schema), "sha256": sha256(blob(C, template_path)).hexdigest(), "execution_authorized": False},
          "policy_sha256": sha256(blob(C, policy_path)).hexdigest(),
          "workload_tree": template["source_tree"], "workload_tracked_blobs": len(git("ls-tree", "-r", "--name-only", WORKLOAD).splitlines()),
          "control_runtime_tree": git("rev-parse", C + ":uta").decode().strip(),
          "base6010_runtime_tree": git("rev-parse", BASE + ":uta").decode().strip(),
          "delivered_ff814_runtime_tree": git("rev-parse", "ff814d4bcaee079b0e0503ea8072c24e3563c443:uta").decode().strip(),
          "actual_marker_absent_in_tree_and_since909_ancestry": True,
          "spent01_02_03_04_remain_spent_policy": policy["spent_registrations"],
          "test_dependencies": {p: {"sha256": sha256(blob(C, p)).hexdigest()} for p in tests},
          "workflow_dependencies": workflows,
          "finding": {"kind": "STATIC_DISPATCH_DRAFT_MISSING_REQUIRED_WORKFLOW", "actual_test_executed": False,
                      "source_test_reads_both_YAML": True, "planned_once_M05_dependency_gap": False},
          "combined_new_tree_tests_or_build_run_by_reviewer": False, "root_final_GO": False,
          "actual_M05_marker_ref_push_SQL_native_crypto_CI": False}
print(json.dumps(result, sort_keys=True, indent=2))
