"""Independent, file-only audit. Never imports or executes candidate code.

Run with: taskset -c 3 timeout 3s python .../check_files.py
The author checker is neither imported nor called. No sqlite3/native/process API.
"""
import ast
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import resource
import time

resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
START = time.process_time_ns()
ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "evidence/runs/history-perf-rnd"
RUNTIME = "dd502ae538618c6d17a3bd2eae708e09526e9d4c"
CANDIDATE = "3a48aa4eb27b8c7a61241c7045b25faf24a8737c"
checks = []


def require(condition, description):
    if not condition:
        raise AssertionError(description)
    checks.append(description)


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def dump(node):
    return ast.dump(node, include_attributes=False)


require(sorted(os.sched_getaffinity(0)) == [3], "checker uses CPU3 only")
external = []
for attempt in ("attempt-01", "attempt-02-v2"):
    directory = EVIDENCE / attempt
    manifest = read(directory / "manifest.json")
    for entry in manifest["files"]:
        local = directory / entry["name"]
        require(local.stat().st_size == entry["bytes"] and digest(local) == entry["sha256"],
                attempt + "/" + entry["name"] + " bytes/hash match manifest")
        original = Path(entry["original_path"])
        exists = original.is_file()
        if exists:
            require(local.read_bytes() == original.read_bytes(),
                    attempt + "/" + entry["name"] + " matches original external copy")
        external.append(dict(attempt=attempt, name=entry["name"], original_exists=exists))

old = read(EVIDENCE / "attempt-01/summary.json")
old_launch = read(EVIDENCE / "attempt-01/launch.json")
old_log = (EVIDENCE / "attempt-01/unittest.txt").read_text()
require(old["differential"] == dict(tests=23, failures=4, errors=0, skipped=0), "original 23/4/0/0 remains red")
require(not old["success"] and old["calls"] == [] and old_launch["exit_code"] == 1,
        "original red stopped before profiles, exit one")
require(len(re.findall(r"^FAIL: ", old_log, re.M)) == 4 and "FAILED (failures=4)" in old_log,
        "four original subtest failure bodies retained")

new = read(EVIDENCE / "attempt-02-v2/summary.json")
launch = read(EVIDENCE / "attempt-02-v2/launch.json")
phases = [json.loads(line) for line in (EVIDENCE / "attempt-02-v2/phases.jsonl").read_text().splitlines()]
stdout = read(EVIDENCE / "attempt-02-v2/stdout.txt")
require(new["runtime_commit"] == launch["runtime_commit"] == RUNTIME and launch["candidate"] == CANDIDATE,
        "raw runtime and exact observed candidate identities agree")
require(new["success"] and launch["exit_code"] == 0 and not launch["watchdog"]
        and not launch["forced_cleanup"] and launch["child_reaped"] and launch["child_proc_absent"],
        "V2 raw records normal zero exit, no forced cleanup, owned child reaped")
require(0 < launch["elapsed_ns"] < 15_000_000_000 and launch["cpu_affinity"] == new["affinity"] == [4],
        "V2 recorded sub-15-second CPU4 component")
require(new["before_sources"] == new["after_sources"] and len(new["before_sources"]) == 53,
        "all 53 before/after input hashes agree")
for name, expected in new["before_sources"].items():
    require(digest(ROOT / name) == expected, "current frozen input matches raw: " + name)
for name, expected in launch["before_sha256"].items():
    require(expected == launch["after_sha256"][name] == new["before_sources"][name],
            "outer launch source agrees: " + name)
require(stdout == dict(success=True, differential=new["differential"], calls=4,
                       elapsed_ns=new["elapsed_ns_before_summary_write"]), "stdout agrees with summary")

test_tree = ast.parse((ROOT / "tests/test_history_postings_stream.py").read_text())
methods = sorted(node.name for node in ast.walk(test_tree) if isinstance(node, ast.FunctionDef)
                 and node.name.startswith("test_"))
log = (EVIDENCE / "attempt-02-v2/unittest.txt").read_text()
observed_methods = sorted(re.findall(r"^(test_\w+) \([^\n]+\) \.\.\. ok$", log, re.M))
require(len(methods) == 27 and methods == observed_methods and "Ran 27 tests" in log and log.endswith("OK\n"),
        "all 27 source methods occur as ok in retained V2 log")
require(new["differential"] == dict(tests=27, failures=0, errors=0, skipped=0), "V2 exact test totals agree")

# Independently compose only the declared immutable synthetic fixture in memory.
# No production helper, author reference/checker, SQL or retained financial output
# is used to derive its expected hashes and byte representations.
n, previous, event_bytes, old_payload_bytes, new_payload_bytes, metadata_bytes, reference_bytes = 512, "0" * 64, 0, 0, 0, 0, 0
compact = lambda value: json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode()
fingerprint = sha256(compact([["a", "USD", -1], ["b", "USD", 1]])).hexdigest()
for sequence in range(1, n + 1):
    event_id = "component:" + str(sequence - 1)
    head = sha256(compact([sequence, event_id, previous, fingerprint])).hexdigest()
    event = [sequence, event_id, fingerprint, previous, head, 1]
    payload = [[0, "a", "USD", "-1"], [1, "b", "USD", "1"]]
    event_bytes += len(compact(event))
    old_payload_bytes += sum(len(compact(row)) for row in payload)
    new_payload_bytes += sum(len(compact([sequence] + row)) for row in payload)
    metadata_bytes += len(compact([sequence, 2]))
    reference_bytes += len(compact([event, payload]))
    previous = head
expected_reference = dict(events=n, postings=2*n, balances_units={"a/USD": -n, "b/USD": n},
                          head=previous, logical_event_and_posting_json_bytes=reference_bytes,
                          logical_byte_definition=new["initial_literal_reference"]["logical_byte_definition"])
require(new["initial_literal_reference"] == new["final_default_cold_reference"] == expected_reference,
        "independent fixture composition matches initial/final references and complete head/balances")
require([p["phase"] for p in phases] == ["differential.begin", "differential.end", "fixture.begin",
        "fixture.batch_commit_return", "fixture.batch_commit_return", "fixture.end", "verify.begin", "verify.end",
        "verify.begin", "verify.end", "verify.begin", "verify.end", "verify.begin", "verify.end",
        "final_default_cold_reopen.begin", "final_default_cold_reopen.end", "scratch.cleanup_complete"],
        "phase order includes two committed batches, four calls, default reopen and cleanup")
require([(p["committed_batches"], p["committed_events"]) for p in phases if p["phase"] == "fixture.batch_commit_return"]
        == [(1, 256), (2, 512)], "actual fixture commit-return records agree with scale")
require(all(a["elapsed_ns"] < b["elapsed_ns"] for a, b in zip(phases, phases[1:])), "phase elapsed clocks increase")
for index, call in enumerate(new["calls"]):
    mode = bool(index % 2)
    require(call["index"] == index and call["ordered_postings"] is mode, "call order is default/opt-in/default/opt-in: " + str(index))
    require(call["actual_fetched_row_counts"] == dict(event=n, payload=2*n, group_metadata=n if mode else 0, balance=2),
            "reported complete real fetched-row counts: " + str(index))
    require(call["actual_logical_fetched_row_json_bytes"] == dict(event=event_bytes, payload=new_payload_bytes if mode else old_payload_bytes,
            group_metadata=metadata_bytes if mode else 0, balance=35), "independently reconstructed selected-row JSON bytes: " + str(index))
    require((call["posting_select_statements"], call["sql_statements"], call["posting_group_select_statements"], call["posting_payload_select_statements"])
            == ((2, 13, 1, 1) if mode else (512, 523, 0, 512)), "reported statement class totals: " + str(index))
    require({k: v for k, v in phases[7 + index*2].items() if k not in ("phase", "monotonic_ns", "elapsed_ns", "process_cpu_ns")} == call,
            "phase report exactly matches summary call: " + str(index))
    profile = (EVIDENCE / f"attempt-02-v2/profile-{index}.txt").read_text()
    require(re.search(r"^\s+" + str(2069 if mode else 1557) + r"\s+.*\(counted\)$", profile, re.M) is not None,
            "profile callback count agrees with selected rows plus 19 guard rows: " + str(index))
    require(re.search(r"^\s+" + str(16 if mode else 526) + r"\s+.*method 'execute'", profile, re.M) is not None,
            "profile execute count is trace statement count plus 3 pre-trace connection executes: " + str(index))
    require(not call["physical_cold_io_established"] and call["proc_io_delta"]["read_bytes"] == 0,
            "raw makes no physical cold I/O claim: " + str(index))
require(all(new["calls"][i+1]["wall_ns"] > new["calls"][i]["wall_ns"] for i in (0, 2)), "both measured opt-in calls are slower")

# Check default-path equivalence without executing the verifier. The only
# permitted removals are the exact new option validation/dead stream machinery.
baseline_tree = ast.parse((EVIDENCE / "original-storage.py.txt").read_text())
candidate_tree = ast.parse((ROOT / "uta/storage.py").read_text())
find_verify = lambda tree: next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "verify")
before, after = find_verify(baseline_tree), find_verify(candidate_tree)
specialized = deepcopy(after)
require([arg.arg for arg in specialized.args.kwonlyargs] == ["connection", "ordered_postings"]
        and isinstance(specialized.args.kw_defaults[-1], ast.Constant) and specialized.args.kw_defaults[-1].value is False,
        "ordered_postings is keyword-only with literal false default")
specialized.args.kwonlyargs.pop()
specialized.args.kw_defaults.pop()
require(ast.unparse(specialized.body[1].test) == "type(ordered_postings) is not bool", "exact bool check precedes storage")
specialized.body = specialized.body[2:]
transaction = specialized.body[0]
require(isinstance(transaction, ast.With), "default replay keeps original transaction context")
stream_assignments = {"group_cursor", "following_group", "posting_cursor"}
removed = []
kept = []
for statement in transaction.body:
    if isinstance(statement, ast.Assign) and isinstance(statement.targets[0], ast.Name) and statement.targets[0].id in stream_assignments:
        removed.append(statement.targets[0].id)
    elif isinstance(statement, ast.If) and ast.unparse(statement.test) == "following_group is not None or (posting_cursor is not None and next(posting_cursor, None) is not None)":
        removed.append("residual_stream_check")
    else:
        kept.append(statement)
transaction.body = kept
require(removed == ["group_cursor", "following_group", "posting_cursor", "residual_stream_check"], "only dead stream state/check removed for false specialization")
loop = next(statement for statement in transaction.body if isinstance(statement, ast.For))
branches = [statement for statement in loop.body if isinstance(statement, ast.If) and ast.unparse(statement.test) == "not ordered_postings"]
require(len(branches) == 1, "one ordered-postings branch in event replay")
loop.body[loop.body.index(branches[0]):loop.body.index(branches[0])+1] = branches[0].body
baseline = deepcopy(before)
baseline.body = baseline.body[1:]
require(dump(baseline) == dump(specialized), "specialized false-path AST exactly equals archived original verifier excluding docstring")
before.body = [ast.Pass()]
after.body = [ast.Pass()]
after.args = deepcopy(before.args)
require(dump(baseline_tree) == dump(candidate_tree), "all storage code outside verify and its added argument is unchanged")
require(digest(EVIDENCE / "original-storage.py.txt") == "9eee296159d0b0347feac3fd2f2b99b3216e8247e579e159e5adda8cbcb08a08",
        "original storage baseline hash fixed independently")
non_storage_mentions = [str(path.relative_to(ROOT)) for path in (ROOT / "uta").glob("*.py")
                        if path.name != "storage.py" and "ordered_postings" in path.read_text()]
require(not non_storage_mentions, "no other runtime file mentions/enables ordered_postings")

print(json.dumps(dict(status="FILE_AUDIT_PASS_NO_SQL_EXECUTION", observed_candidate=CANDIDATE, runtime=RUNTIME,
      checks=checks, check_count=len(checks), external_originals=external,
      independent_expected=dict(head=previous, event_json_bytes=event_bytes, old_payload_json_bytes=old_payload_bytes,
          new_payload_json_bytes=new_payload_bytes, metadata_json_bytes=metadata_bytes, common_reference_json_bytes=reference_bytes),
      measured_wall_ns=[call["wall_ns"] for call in new["calls"]],
      paired_opt_in_slowdown_pct=[100*(new["calls"][i+1]["wall_ns"]/new["calls"][i]["wall_ns"]-1) for i in (0, 2)],
      limitations=["source/raw-file audit only; no independent SQL/test/profile execution",
          "reported aggregate SQL/row counts are cross-checked against harness and profiles; full SQL text/row trace was not retained",
          "does not infer production speed, physical cold I/O, quota enforcement or independent dynamic correctness"],
      checker_cpu_ns=time.process_time_ns()-START), indent=2, sort_keys=True))
