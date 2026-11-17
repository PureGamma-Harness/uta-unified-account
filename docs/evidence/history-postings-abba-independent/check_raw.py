"""Independent raw-file/Fraction audit; no harness/core imports or SQL execution."""
import ast
from decimal import Decimal, localcontext
from fractions import Fraction
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import resource
from statistics import median
import time

resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
started = time.process_time_ns()
root = Path(__file__).resolve().parents[3]
evidence = root / "evidence/runs/history-perf-rnd"
raw = evidence / "attempt-03-uninstrumented"
checks = []


def check(value, label):
    if not value:
        raise AssertionError(label)
    checks.append(label)


def load(path):
    return json.loads(path.read_text())


def hash_file(path):
    return sha256(path.read_bytes()).hexdigest()


def rational(value):
    return Fraction(value["numerator"], value["denominator"])


def record(value):
    value = Fraction(value)
    with localcontext() as ctx:
        ctx.prec = 30
        decimal = str(Decimal(value.numerator) / Decimal(value.denominator))
    return dict(numerator=value.numerator, denominator=value.denominator, decimal=decimal)


check(sorted(os.sched_getaffinity(0)) == [3], "independent file checker uses CPU3")
harness = root / "evidence/runs/history-perf-rnd/run_uninstrumented_abba.py"
check(hash_file(harness) == "caf46cdf706000c2bb73bb921999be6ea82a04b15c2e836cd67422b6cfc14adb", "exact approved harness SHA256")
for attempt in ("attempt-01", "attempt-02-v2", "attempt-03-uninstrumented"):
    directory = evidence / attempt
    manifest = load(directory / "manifest.json")
    for item in manifest["files"]:
        path = directory / item["name"]
        check(path.stat().st_size == item["bytes"] and hash_file(path) == item["sha256"], attempt + "/" + item["name"] + " manifest bytes/hash")
        original = Path(item["original_path"])
        check(original.is_file() and path.read_bytes() == original.read_bytes(), attempt + "/" + item["name"] + " exact original external copy")

summary, launch = load(raw / "summary.json"), load(raw / "launch.json")
samples = [json.loads(line) for line in (raw / "samples.jsonl").read_text().splitlines()]
phases = [json.loads(line) for line in (raw / "phases.jsonl").read_text().splitlines()]
check(launch["candidate"] == "53b3ba47bbfd2921b407995e8bd5961562655cfa"
      and launch["runtime_commit"] == summary["runtime_commit"] == "dd502ae538618c6d17a3bd2eae708e09526e9d4c", "observed candidate and runtime identities")
check(summary["success"] and launch["exit_code"] == 0 and not launch["watchdog"] and not launch["forced_cleanup"]
      and launch["child_reaped"] and launch["child_proc_absent"], "normal successful exit and retained reaping record")
check(launch["elapsed_ns"] == 2423153440 and 0 < summary["elapsed_ns_before_summary_write"] < launch["elapsed_ns"] < 15_000_000_000,
      "recorded outer interval below cap with child summary endpoint inside")
check(summary["affinity"] == launch["cpu_affinity"] == [4] and summary["python"].startswith("3.12.14 "), "recorded Python312 and CPU4")
check(summary["before_sources"] == summary["after_sources"] and len(summary["before_sources"]) == 53, "53 source hashes equal before/after")
prior = load(evidence / "attempt-02-v2/summary.json")
for name, expected in summary["before_sources"].items():
    check(hash_file(root / name) == expected, "frozen source SHA matches actual: " + name)
    if name.startswith("uta/") or name == "tests/test_history_postings_stream.py":
        check(prior["before_sources"][name] == expected, "runtime/control source unchanged from attempt02: " + name)
for name, expected in launch["before_sha256"].items():
    check(launch["after_sha256"][name] == expected == summary["before_sources"][name], "outer critical source binding: " + name)
for name, identity in launch["child_output_files"].items():
    check((raw / name).stat().st_size == identity["bytes"] and hash_file(raw / name) == identity["sha256"], "outer child output binding: " + name)
check(load(raw / "stdout.txt") == dict(success=True, samples=24, elapsed_ns=summary["elapsed_ns_before_summary_write"]), "stdout matches summary")
check(not summary["independent_acceptance"] and not summary["production_qualified"] and not summary["physical_cold_io_established"], "raw qualification/cold flags remain false")
controls = dict(tests=27, failures=0, errors=0, skipped=0)
check(summary["correctness_controls"] == controls, "27 correctness controls no failures/errors/skips")
test_tree = ast.parse((root / "tests/test_history_postings_stream.py").read_text())
expected_names = sorted(node.name for node in ast.walk(test_tree) if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"))
test_log = (raw / "unittest.txt").read_text()
check(sorted(re.findall(r"^(test_\w+) \([^\n]+\) \.\.\. ok$", test_log, re.M)) == expected_names and len(expected_names) == 27
      and "Ran 27 tests" in test_log and test_log.endswith("OK\n"), "all 27 actual log method names match frozen controls")
check(load(evidence / "attempt-01/summary.json")["differential"] == dict(tests=23, failures=4, errors=0, skipped=0), "old four red controls preserved")
check([call["wall_ns"] for call in prior["calls"]] == [40863752,41753702,38272587,45326611], "old two slower instrumented comparisons preserved")

# Inspect, do not execute, the exact clock-bounded statements.
tree = ast.parse(harness.read_text())
main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
slot_loop = next(node for node in ast.walk(main) if isinstance(node, ast.For) and ast.unparse(node.iter) == "enumerate(ORDER)")
clock_start = next(i for i, node in enumerate(slot_loop.body) if isinstance(node, ast.Assign) and ast.unparse(node.targets[0]) == "wall_start")
window = [ast.unparse(node) for node in slot_loop.body[clock_start:clock_start+5]]
check(window == ["wall_start = time.monotonic_ns()", "cpu_start = time.process_time_ns()", "returned = ledger.verify(ordered_postings=mode)",
                 "cpu_end = time.process_time_ns()", "wall_end = time.monotonic_ns()"], "timed source window contains only clocks and complete verifier")
imports = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
check(not imports.intersection({"cProfile","profile","tracemalloc"}) and not any(isinstance(node, ast.Attribute) and node.attr in {"set_trace_callback","setprofile","settrace","row_factory"} for node in ast.walk(tree)), "harness installs no profiler/SQL trace/custom row factory")
constants = {node.targets[0].id: ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
             and isinstance(node.targets[0], ast.Name) and node.targets[0].id in {"SCALES","BLOCKS","ORDER"}}
check(constants == dict(SCALES=(512,4096), BLOCKS=3, ORDER=(False,True,True,False)), "source fixes two scales and three ABBA blocks")
check(not any("ordered_postings" in path.read_text() for path in (root / "uta").glob("*.py") if path.name != "storage.py"), "no runtime flag enabling outside storage")
storage = ast.parse((root / "uta/storage.py").read_text())
verify = next(node for node in ast.walk(storage) if isinstance(node, ast.FunctionDef) and node.name == "verify")
check(verify.args.kwonlyargs[-1].arg == "ordered_postings" and ast.literal_eval(verify.args.kw_defaults[-1]) is False, "runtime default remains false")

check(len(samples) == 24 and [scale["events"] for scale in summary["scales"]] == [512,4096], "all 24 samples and fixed scale order retained")
check([sample for scale in summary["scales"] for sample in scale["samples"]] == samples, "summary samples equal raw JSONL in original order")
check(len(phases) == 93 and all(a["elapsed_ns"] < b["elapsed_ns"] for a,b in zip(phases, phases[1:])), "93 phases with increasing elapsed clocks")
check(phases[0]["phase"] == "correctness_controls.begin" and phases[0]["outside_timed_intervals"] is True
      and phases[1]["phase"] == "correctness_controls.end" and all(phases[1][key] == value for key,value in controls.items())
      and phases[-1]["phase"] == "scratch.cleanup_complete", "controls before measurement, cleanup last")
recomputed = []
compact = lambda value: json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode()
fingerprint = sha256(compact([["a","USD",-1],["b","USD",1]])).hexdigest()
for offset, scale in enumerate(summary["scales"]):
    count = scale["events"]
    data = samples[offset*12:(offset+1)*12]
    check([(s["block"],s["slot"],s["ordered_postings"],s["scale_events"],s["returned_events"]) for s in data]
          == [(block,slot,mode,count,count) for block in range(3) for slot,mode in enumerate((False,True,True,False))], "all original ABBA sample identities at N" + str(count))
    previous = "0"*64
    for sequence in range(1,count+1):
        previous = sha256(compact([sequence,"component:"+str(sequence-1),previous,fingerprint])).hexdigest()
    reference = dict(events=count,postings=2*count,head=previous,balances_units={"a/USD":-count,"b/USD":count})
    check(scale["initial_reference"] == scale["final_reference"] == reference, "independently composed initial/final complete fixture reference N" + str(count))
    relevant = [p for p in phases if p.get("events",p.get("scale_events")) == count]
    commits = [p for p in relevant if p["phase"] == "fixture.batch_commit_return"]
    check([(p["committed_batches"],p["committed_events"]) for p in commits] == [(i,256*i) for i in range(1,count//256+1)], "actual 256-event commit-return sequence N" + str(count))
    check([p["ordered_postings"] for p in relevant if p["phase"] == "untimed_warmup.complete"] == [False,True], "exactly A then B untimed warmups N" + str(count))
    check([p["reference"] for p in relevant if p["phase"] in {"initial_reference.complete","final_default_reopen.end"}] == [reference,reference], "phase initial/default-final references match N" + str(count))
    starts = [p for p in relevant if p["phase"] == "timed_verify.begin"]
    ends = [p for p in relevant if p["phase"] == "timed_verify.end"]
    check(len(starts) == len(ends) == 12, "twelve original timed begin/end pairs N" + str(count))
    for sample,begin,end in zip(data,starts,ends):
        check({k:v for k,v in end.items() if k not in {"phase","monotonic_ns","elapsed_ns"}} == sample
              and (begin["block"],begin["slot"],begin["ordered_postings"]) == (sample["block"],sample["slot"],sample["ordered_postings"])
              and 0 < sample["cpu_ns"] <= sample["wall_ns"] < end["elapsed_ns"]-begin["elapsed_ns"], "sample/phase identity and timing bracket N"+str(count)+" block"+str(sample["block"])+" slot"+str(sample["slot"]))
    reports, metrics = [], {}
    for block in range(3):
        group = data[block*4:block*4+4]
        report = {}
        for metric in ("wall_ns","cpu_ns"):
            a = Fraction(group[0][metric]+group[3][metric],2)
            b = Fraction(group[1][metric]+group[2][metric],2)
            values = dict(a_mean=a,b_mean=b,b_minus_a_mean=b-a,b_over_a=b/a)
            check(all(rational(scale["blocks"][block][metric][name]) == value for name,value in values.items()), "exact means/delta/ratio N"+str(count)+" block"+str(block)+" "+metric)
            report[metric] = {name:record(value) for name,value in values.items()}
        reports.append(report)
    for metric in ("wall_ns","cpu_ns"):
        block_ratios = [rational(report[metric]["b_over_a"]) for report in reports]
        check(rational(scale["median_block_ratios"][metric]) == median(block_ratios), "exact median block ratio N"+str(count)+" "+metric)
        metrics[metric] = dict(median_block_ratio=record(median(block_ratios)),
            min_block_ratio=record(min(block_ratios)),max_block_ratio=record(max(block_ratios)),
            sample_descriptive={label:dict(min=record(min(s[metric] for s in data if s["ordered_postings"] is mode)),
                median=record(median(s[metric] for s in data if s["ordered_postings"] is mode)),
                max=record(max(s[metric] for s in data if s["ordered_postings"] is mode))) for label,mode in (("A",False),("B",True))})
    recomputed.append(dict(events=count,reference=reference,blocks=reports,metrics=metrics))
check(rational(recomputed[1]["blocks"][2]["wall_ns"]["b_over_a"]) > 1 and rational(recomputed[1]["blocks"][2]["cpu_ns"]["b_over_a"]) > 1,
      "4096 third block remains slower in wall and CPU")
check(all(rational(report["wall_ns"]["b_over_a"]) < 1 for report in recomputed[0]["blocks"]), "512 observed wall block means all lower for B")
print(json.dumps(dict(status="INDEPENDENT_FILE_ARITHMETIC_PASS_NO_RERUN",author_artifact="b2051d268f65f443d17dabd83f49aff91cd3c4ab",
      observed_candidate=launch["candidate"],checks=checks,check_count=len(checks),recomputed=recomputed,
      old_red_and_slower_evidence_preserved=True,outer_elapsed_ns=launch["elapsed_ns"],
      limitations=["No SQL, tests, native workload or performance loop executed by reviewer", "No author harness/reference/checker imported as oracle",
          "Primary metric is median of block ratios; sample medians/maxima are separately labelled descriptions",
          "Fixed order, one process/platform and three blocks/scale do not establish confidence or production performance"],
      checker_cpu_ns=time.process_time_ns()-started),indent=2,sort_keys=True))
