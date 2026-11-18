"""Narrow independent literal workflow/ref review; no Actions/workload execution."""
import ast
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from types import ModuleType
from unittest.mock import patch

C = "e466b67faba5fb586d68f8bd35fb7f9c7a63336e"
OLD = "5a72b6abd07c5030604b596cc74e19b18ffee23e"
SOURCE = "909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0"
ACTION = "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683"
REPO = Path(__file__).resolve().parents[3]


def workload(text):
    """Only this reviewed plain layout; no claim of general YAML parsing."""
    steps = []; current = None; in_with = False
    for line in text.splitlines():
        if line.startswith("      - "):
            current = dict(uses=[], values={}, lines=[line]); steps.append(current); in_with = False
            continue
        if current is None: continue
        current["lines"].append(line)
        if line.startswith("        uses: "): current["uses"].append(line[len("        uses: "):])
        if line == "        with:": in_with = True; continue
        if line.startswith("        ") and not line.startswith("         "): in_with = False
        if in_with and line.startswith("          ") and not line.startswith("           "):
            content = line[10:]
            if ": " in content:
                name, value = content.split(": ", 1)
                if name in current["values"]: raise ValueError("duplicate with key")
                current["values"][name] = value
    selected = [step for step in steps if step["values"].get("path") == "workload"]
    if len(selected) != 1: raise ValueError("exactly one workload step")
    step = selected[0]
    if step["uses"] != [ACTION]: raise ValueError("exact reviewed checkout action pin")
    if set(step["values"]) != {"path", "ref", "persist-credentials"}: raise ValueError("literal workload with fields")
    if step["values"]["persist-credentials"] != "false": raise ValueError("persist credentials")
    ref = step["values"]["ref"]
    if re.fullmatch("[0-9a-f]{40}", ref) is None or ref != SOURCE: raise ValueError("actual workload ref != exact SOURCE40")
    return "\n".join(step["lines"]), ref


def main():
    began = time.monotonic_ns(); started = datetime.now(timezone.utc).isoformat()
    paths = ["tools/independent_m0_controller.py", "tools/m0_stream_escrow.py", ".github/workflows/independent-m0-once.yml",
             ".github/workflows/independent-m0.yml", "docs/evidence/independent-actions-m0/once-registration-template.json"]
    raw = {path: subprocess.check_output(["git", "show", C + ":" + path], cwd=REPO) for path in paths}
    old_controller = subprocess.check_output(["git", "show", OLD + ":tools/independent_m0_controller.py"], cwd=REPO)
    old_crypto = subprocess.check_output(["git", "show", OLD + ":tools/m0_stream_escrow.py"], cwd=REPO)
    assert raw["tools/m0_stream_escrow.py"] == old_crypto
    old_functions = {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(old_controller).body if isinstance(n, ast.FunctionDef)}
    new_functions = {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(raw[paths[0]]).body if isinstance(n, ast.FunctionDef)}
    assert set(old_functions) == set(new_functions)
    assert [name for name in old_functions if old_functions[name] != new_functions[name]] == ["validate_once_manifest"]
    observations = []
    for path in paths[2:4]:
        text = raw[path].decode(); block, ref = workload(text)
        observations.append(dict(case="positive_" + path, observed="ACCEPT", actual_ref=ref, exact_action=ACTION))
        wrongs = ["909acecd153e2e89dfe2238e3ed3a3d3c9f0", "f" * 40, "main"]
        for wrong in wrongs:
            changed_block = block.replace("          ref: " + SOURCE, "          ref: " + wrong, 1)
            changed = text.replace(block, changed_block, 1)
            assert changed != text
            if path.endswith("-once.yml"):
                assert "assert value['source_commit'] == '" + SOURCE + "'" in changed
                assert SOURCE in changed
            try: workload(changed); raise AssertionError("ref mutation accepted")
            except ValueError as error: observations.append(dict(case="ref_only_" + path + "_" + wrong, observed="REJECT", reason=str(error), source_assert_unchanged=path.endswith("-once.yml")))
        for name, changed in [("duplicate", text + "\n" + block), ("missing", text.replace("          path: workload", "          path: unrelated")),
                              ("other_action40", text.replace(block, block.replace(ACTION, "actions/checkout@" + "f" * 40), 1))]:
            try: workload(changed); raise AssertionError("structural mutation accepted")
            except ValueError as error: observations.append(dict(case=name + "_" + path, observed="REJECT", reason=str(error)))
    m = ModuleType("fixed_once02_pure_policy"); m.__file__ = "/synthetic/control/tools/independent_m0_controller.py"
    calls = []
    def forbidden(*args, **kwargs): calls.append("process-entry"); raise AssertionError("actual execution prohibited")
    with patch.object(subprocess, "Popen", forbidden), patch.object(subprocess, "run", forbidden), patch.object(subprocess, "check_output", forbidden):
        exec(compile(raw[paths[0]], m.__file__, "exec"), m.__dict__)
        value = json.loads(raw[paths[4]])
        assert value["execution_authorized"] is False and value["control_commit"] == "0" * 40
        assert value["branch"] == m.APPROVED_BRANCH == "refs/heads/perf/approved-m0-20261117-02"
        assert value["registration_id"] == m.REGISTRATION_ID == "independent-m0-20261117-02"
        assert value["source_commit"] == m.SOURCE == SOURCE
        assert value["budgets"] == m.budget_spec() and value["command_spec"] == m.command_spec()
        synthetic = deepcopy(value); synthetic.update(execution_authorized=True, control_commit=C)
        event_commit = "d" * 40
        environment = dict(GITHUB_REF=m.APPROVED_BRANCH, GITHUB_EVENT_NAME="push", GITHUB_RUN_ATTEMPT="1", GITHUB_SHA=event_commit)
        event = dict(ref=m.APPROVED_BRANCH, created=True, deleted=False, forced=False, before="0" * 40, after=event_commit)
        relation = dict(execution_commit=event_commit, parents=[C], changed_paths=[m.APPROVAL_PATH], changed_status=["A"])
        assert m.validate_once_manifest(synthetic, environment, event, relation)
        observations.append(dict(case="new02_synthetic_policy_only", observed="ACCEPT", actual_M_created=False))
        for field, wrong in [("registration_id", "independent-m0-20261117-once"), ("branch", "refs/heads/perf/approved-m0-20261117-once")]:
            altered = deepcopy(synthetic); altered[field] = wrong
            try: m.validate_once_manifest(altered, environment, event, relation); raise AssertionError("old policy accepted")
            except m.GateError as error: observations.append(dict(case="old_" + field + "_not_reused", observed="REJECT", reason=str(error)))
        assert not calls and not any(name == "uta" or name.startswith("uta.") or name == "sqlite3" for name in sys.modules)
    print(json.dumps(dict(control_commit=C, started_at_utc=started, finished_at_utc=datetime.now(timezone.utc).isoformat(),
                          elapsed_monotonic_ns=time.monotonic_ns() - began, input_sha256={path: sha256(data).hexdigest() for path, data in raw.items()},
                          crypto_bytes_unchanged=True, other_controller_function_AST_unchanged=True, cases=observations, red_count=0,
                          actual_native_SQL_crypto_M_Actions_push=False, execution_authorized=False, production_approved=False), indent=2))


if __name__ == "__main__": main()
