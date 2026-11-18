"""Prepare/check SQL6 metadata by parsing source AST; never execute target code.

No target import, bytecode compilation, eval, exec, SQL, worker or PID access.
The AST whitelist covers all17 original command items. Exact equality includes
the first LF in the raw BOOTSTRAP string; no normalization is permitted.
"""
import argparse
import ast
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import subprocess


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = "evidence/reviews/funding-obligations-local"
PLAN = DIRECTORY + "/sql6-once-plan.json"
CALLER_PLAN = DIRECTORY + "/sql6-caller-plan.json"
FREEZE = DIRECTORY + "/sql6-CODE-freeze.json"
ENTRY = "tools/run_funding_obligations_sql6_once.py"
CALLER = "tools/run_funding_obligations_sql6_caller_once.py"
SELF = "tools/check_funding_obligations_sql6_intent_static.py"
DOC = "docs/funding-obligations-sql6-intent-v2.md"
ORIGINAL = "9171e8e5e8d16b99a8a46f2f6ec1563754f55811"
OUTPUT = "/workspace/uta-funding-obligations-sql6-intent-v2-once01"
HOST_OUTPUT = "/workspace/uta-funding-obligations-sql6-intent-v2-host-once01"
OLD_PLAN_SHA = "02f57cfb7d55498c436ed61243f7180d1ba51995209e3b5c09b8d49b28761ea1"
OLD_CALLER_SHA = "155950087c7d9a6785b9b76d55df43d8b5b959427088ec4347a6898a3f34d6c4"


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def read(path):
    if path.resolve() != path or not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError("canonical regular source required")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        raw = stream.read(2 * 1024 * 1024 + 1)
        after = os.fstat(stream.fileno())
    if len(raw) > 2 * 1024 * 1024 or any(getattr(before, k) != getattr(after, k)
            for k in ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")):
        raise ValueError("source oversized or changed while reading")
    return raw


def pin(raw):
    return {"bytes": len(raw), "sha256": sha256(raw).hexdigest()}


def git(*arguments):
    result = subprocess.run(["/usr/bin/git", "--no-optional-locks", "-C", str(ROOT), *arguments],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=3,
        env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null"})
    if result.stderr or len(result.stdout) > 2 * 1024 * 1024:
        raise ValueError("unexpected metadata Git output")
    return result.stdout


def target_template(source, executable):
    tree = ast.parse(source, filename=ENTRY, mode="exec")  # AST only, no code object.
    values = [node.value for node in tree.body if isinstance(node, ast.Assign)
              and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
              and node.targets[0].id == "BOOTSTRAP"]
    if len(values) != 1 or not isinstance(values[0], ast.Constant) or type(values[0].value) is not str:
        raise ValueError("BOOTSTRAP must be one direct string literal")
    bootstrap = values[0].value
    runs = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "run"]
    if len(runs) != 1:
        raise ValueError("one original run function required")
    commands = [node.value for node in ast.walk(runs[0]) if isinstance(node, ast.Assign)
                and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "command"]
    if len(commands) != 1 or not isinstance(commands[0], ast.List) or len(commands[0].elts) != 17:
        raise ValueError("one exact17-item original command required")
    symbolic = {
        'plan["expected_runtime"]["resolved_executable"]': executable,
        "BOOTSTRAP": bootstrap,
        "str(capsule)": "<CAPSULE>",
        "sha256(capsule_raw).hexdigest()": "<CAPSULE_SHA256>",
        "args.plan_sha256": "<FUNDING_OBLIGATIONS_SQL6_PLAN_SHA256>",
        "args.source_commit": "<FINAL_SOURCE_HEAD>",
        'str(output / "inner")': "<INNER_OUTPUT>",
    }
    shapes = {ast.dump(ast.parse(text, mode="eval").body, include_attributes=False): value
              for text, value in symbolic.items()}
    actual = []
    for node in commands[0].elts:
        if isinstance(node, ast.Constant) and type(node.value) is str:
            actual.append(node.value)
        else:
            shape = ast.dump(node, include_attributes=False)
            if shape not in shapes:
                raise ValueError("unreviewed original command AST item")
            actual.append(shapes[shape])
    expected = ["/usr/bin/timeout", "--signal=KILL", "45s", "/usr/bin/taskset", "-c", "1",
                executable, "-I", "-S", "-B", "-c", bootstrap, "<CAPSULE>", "<CAPSULE_SHA256>",
                "<FUNDING_OBLIGATIONS_SQL6_PLAN_SHA256>", "<FINAL_SOURCE_HEAD>", "<INNER_OUTPUT>"]
    if actual != expected or not bootstrap.startswith("\n"):
        raise ValueError("full original17-item command or retained LF differs")
    return actual


def validate(plan, control, frozen):
    if set(frozen) != set(plan["input_files"]) or len(frozen) != 69:
        raise ValueError("original69 target inputs required")
    if {k: pin(v) for k, v in frozen.items()} != plan["input_files"]:
        raise ValueError("target input pins differ")
    if control["caller_control_pin"] != pin(read(ROOT / CALLER)):
        raise ValueError("original caller pin differs")
    actual = target_template(frozen[ENTRY], plan["expected_runtime"]["resolved_executable"])
    if actual != control["inner_argv_template"]:
        raise ValueError("strict original/template17-item equality failed")
    if control["target_plan_sha256"] != sha256(encode(plan)).hexdigest():
        raise ValueError("caller/target plan pin differs")
    argv = control["literal_caller_argv_template"]
    expected_caller = [plan["expected_runtime"]["resolved_executable"], "-I", "-S", "-B",
        "<CHECKOUT>/tools/run_funding_obligations_sql6_caller_once.py", "--execute", "--source-commit",
        "<FINAL_SOURCE_HEAD>", "--plan-sha256", control["target_plan_sha256"], "--caller-plan-sha256",
        "<CALLER_PLAN_SHA256>", "--output", OUTPUT, "--caller-output", HOST_OUTPUT]
    if argv != expected_caller:
        raise ValueError("exact new caller invocation or namespace differs")
    return {"AST_only_no_target_import_or_bytecode": True, "full17_target_argv_equal": True,
            "full_literal_caller_argv_equal": True, "bootstrap": pin(actual[11].encode()),
            "leading_LF_retained": actual[11].startswith("\n"), "normalization_used": False,
            "target69_bytes_unchanged": True, "first_UNKNOWN_preserved": True}


def prepare(source):
    if git("rev-parse", "HEAD").decode().strip() != source:
        raise ValueError("preparation source HEAD differs")
    original_raw = {name: git("show", ORIGINAL + ":" + name) for name in (PLAN, CALLER_PLAN, FREEZE)}
    if sha256(original_raw[PLAN]).hexdigest() != OLD_PLAN_SHA or sha256(original_raw[CALLER_PLAN]).hexdigest() != OLD_CALLER_SHA:
        raise ValueError("historical plan identity differs")
    plan, control = json.loads(original_raw[PLAN]), json.loads(original_raw[CALLER_PLAN])
    frozen = {name: read(ROOT / name) for name in plan["input_files"]}
    for name, raw in frozen.items():
        if raw != git("show", ORIGINAL + ":" + name) or raw != git("show", source + ":" + name):
            raise ValueError("target69 changed from first execution")
    if (read(ROOT / CALLER) != git("show", ORIGINAL + ":" + CALLER)
            or read(ROOT / CALLER) != git("show", source + ":" + CALLER)):
        raise ValueError("runtime caller bytes changed")
    control_inputs = {name: read(ROOT / name) for name in (SELF, DOC)}
    if any(raw != git("show", source + ":" + name) for name, raw in control_inputs.items()):
        raise ValueError("static preparation control differs from source Git")
    plan.update(source_origin_commit=source, CODE_delta_parent=ORIGINAL,
        scope_id="SQL6_INTENT_V2_CODE_ONLY",
        control_input_files={name: pin(raw) for name, raw in control_inputs.items()},
        control_pins_are_static_preparation_not_extra_target_loaded_inputs=True,
        historical_first_UNKNOWN={"source": ORIGINAL, "caller_exit": 126,
            "SAFE": "caea35102e0d4c77ca348597da429bbabafda106",
            "independent_RAW": "b5fbbf464b3e436d87d7e09ea848e0aee2ad7ecf",
            "target_plan_sha256": OLD_PLAN_SHA, "caller_plan_sha256": OLD_CALLER_SHA},
        independent_ENTRY_CALLER_CODE="PENDING_INTENT_V2_LIMITED_CODE_REVIEW")
    control.update(source_origin_commit=source, CODE_delta_parent=ORIGINAL,
        target_plan_sha256=sha256(encode(plan)).hexdigest(),
        inner_argv_template=target_template(frozen[ENTRY], plan["expected_runtime"]["resolved_executable"]),
        independent_CODE="PENDING_INTENT_V2_LIMITED_CODE_REVIEW")
    argv = control["literal_caller_argv_template"]
    argv[argv.index("--plan-sha256") + 1] = control["target_plan_sha256"]
    argv[argv.index("--output") + 1], argv[argv.index("--caller-output") + 1] = OUTPUT, HOST_OUTPUT
    proof = validate(plan, control, frozen)  # All checks precede any new plan write.
    archive = ROOT / DIRECTORY / "sql6-9171-FIRST_UNKNOWN"
    archive.mkdir()
    for name, raw in original_raw.items():
        with (archive / Path(name).name).open("xb") as stream:
            stream.write(raw)
    for name, raw in ((PLAN, encode(plan)), (CALLER_PLAN, encode(control))):
        (ROOT / name).write_bytes(raw)
    freeze = {"source_origin_commit": source, "plan_sha256": sha256(encode(plan)).hexdigest(),
        "caller_plan_sha256": sha256(encode(control)).hexdigest(), "input_count": 69,
        "input_bytes": plan["input_bytes"], "control_input_files": plan["control_input_files"],
        "static_intent_preflight": proof, "target_attempts": 0,
        "historical_first_UNKNOWN_is_not_changed": True}
    (ROOT / FREEZE).write_bytes(encode(freeze))
    print(json.dumps(freeze, sort_keys=True))


def check(source):
    if git("rev-parse", "HEAD").decode().strip() != source:
        raise ValueError("checking source HEAD differs")
    plan_raw, caller_raw = read(ROOT / PLAN), read(ROOT / CALLER_PLAN)
    plan, control = json.loads(plan_raw), json.loads(caller_raw)
    if plan_raw != encode(plan) or caller_raw != encode(control):
        raise ValueError("canonical plan bytes required")
    if plan_raw != git("show", source + ":" + PLAN) or caller_raw != git("show", source + ":" + CALLER_PLAN):
        raise ValueError("current plan Git bytes differ")
    frozen = {name: read(ROOT / name) for name in plan["input_files"]}
    if any(raw != git("show", source + ":" + name) for name, raw in frozen.items()):
        raise ValueError("target source Git mismatch")
    if any(raw != git("show", ORIGINAL + ":" + name) for name, raw in frozen.items()):
        raise ValueError("historical69 target inputs changed")
    if read(ROOT / CALLER) != git("show", source + ":" + CALLER) or read(ROOT / CALLER) != git("show", ORIGINAL + ":" + CALLER):
        raise ValueError("runtime caller Git/original bytes differ")
    for name, expected in plan["control_input_files"].items():
        raw = read(ROOT / name)
        if pin(raw) != expected or raw != git("show", source + ":" + name):
            raise ValueError("static preparation control pin differs")
    print(json.dumps(validate(plan, control, frozen), sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-commit", required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--prepare", action="store_true")
    action.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.prepare:
        prepare(args.source_commit)
    else:
        check(args.source_commit)
