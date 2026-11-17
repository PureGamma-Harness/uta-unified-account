"""Author's pure retained-file/rational check; no harness/UTA/SQL import.

Not independent acceptance. Never reruns or filters a timed proof.
"""
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import re


HERE = Path(__file__).resolve().parent
RAW = HERE / "attempt-03-uninstrumented"
load = lambda name: json.loads((RAW / name).read_text())
summary, launch, manifest = load("summary.json"), load("launch.json"), load("manifest.json")
samples = [json.loads(line) for line in (RAW / "samples.jsonl").read_text().splitlines()]
phases = [json.loads(line) for line in (RAW / "phases.jsonl").read_text().splitlines()]
checks = []


def require(condition, label):
    assert condition, label
    checks.append(label)


def rational(value):
    return {"numerator":value.numerator,"denominator":value.denominator}


require(all(sha256((RAW / item["name"]).read_bytes()).hexdigest() == item["sha256"]
    and (RAW / item["name"]).stat().st_size == item["bytes"] for item in manifest["files"]), "all raw lengths and hashes match")
require(launch["candidate"] == "53b3ba47bbfd2921b407995e8bd5961562655cfa", "exact approved ABBA candidate")
require(summary["runtime_commit"] == launch["runtime_commit"] == "dd502ae538618c6d17a3bd2eae708e09526e9d4c", "reviewed runtime unchanged")
require(launch["before_sha256"] == launch["after_sha256"] and launch["before_sha256"]["evidence/runs/history-perf-rnd/run_uninstrumented_abba.py"] == "caf46cdf706000c2bb73bb921999be6ea82a04b15c2e836cd67422b6cfc14adb", "exact harness and outer before/after hashes")
require(summary["before_sources"] == summary["after_sources"] and len(summary["before_sources"]) == 53, "all 53 measured source inputs unchanged")
require(launch["cpu_affinity"] == summary["affinity"] == [4] and 0 < launch["elapsed_ns"] < 15_000_000_000, "recorded CPU4 completion inside outside cap")
require(launch["exit_code"] == 0 and launch["watchdog"] is False and launch["forced_cleanup"] is False,
        "normal exit without watchdog or forced cleanup")
require(launch["child_reaped"] is True and launch["child_proc_absent"] is True, "owned PID reaped and absent")
require(summary["success"] is True and "error" not in summary and summary["elapsed_ns_before_summary_write"] < 14_000_000_000,
        "normal harness result without internal alarm failure")
require(summary["correctness_controls"] == dict(tests=27,failures=0,errors=0,skipped=0), "all 27 separate controls pass")
log = (RAW / "unittest.txt").read_text()
require(len(re.findall(r"^test_\w+ .* \.\.\. ok$",log,re.M)) == 27 and log.endswith("OK\n"), "full control log contains 27 ok methods")
require([s["events"] for s in summary["scales"]] == [512,4096] and len(samples) == 24, "fixed scale order and all 24 timed samples")
require(phases[-1]["phase"] == "scratch.cleanup_complete" and len(phases) == 93, "complete expected phase count and scratch cleanup")
require(all(a["elapsed_ns"] < b["elapsed_ns"] for a,b in zip(phases,phases[1:])), "phase elapsed clocks increase")
require([sample for scale in summary["scales"] for sample in scale["samples"]] == samples,
        "raw sample order exactly equals summary, no dropped slow sample")
computed = []
for scale in summary["scales"]:
    n = scale["events"]
    commits = [p for p in phases if p["phase"] == "fixture.batch_commit_return" and p["events"] == n]
    require([(p["committed_batches"],p["committed_events"]) for p in commits] ==
            [(i,i*256) for i in range(1,n//256+1)], "all public 256-event commit returns at N"+str(n))
    require([p["ordered_postings"] for p in phases if p["phase"] == "untimed_warmup.complete" and p["events"] == n] == [False,True], "one declared A then B warmup at N"+str(n))
    previous = "0"*64
    compact = lambda value: json.dumps(value,ensure_ascii=True,separators=(",",":")).encode()
    fingerprint = sha256(compact([["a","USD",-1],["b","USD",1]])).hexdigest()
    for sequence in range(1,n+1):
        previous = sha256(compact([sequence,"component:"+str(sequence-1),previous,fingerprint])).hexdigest()
    expected_ref = dict(events=n,postings=2*n,head=previous,balances_units={"a/USD":-n,"b/USD":n})
    require(scale["initial_reference"] == scale["final_reference"] == expected_ref,
            "literal initial/final complete head and balances at N"+str(n))
    require(len(scale["samples"]) == 12 and len(scale["blocks"]) == 3, "exactly three complete blocks at N"+str(n))
    ratios = {metric:[] for metric in ("wall_ns","cpu_ns")}
    for block in range(3):
        selected = scale["samples"][4*block:4*(block+1)]
        require([(s["block"],s["slot"],s["ordered_postings"],s["returned_events"]) for s in selected]
                == [(block,i,mode,n) for i,mode in enumerate((False,True,True,False))],
                "unchanged ABBA order/counts N"+str(n)+" block"+str(block))
        for metric in ("wall_ns","cpu_ns"):
            require(all(type(s[metric]) is int and s[metric] > 0 for s in selected), "positive exact ns "+metric+" N"+str(n)+" block"+str(block))
            a = selected[0][metric] + selected[3][metric]
            b = selected[1][metric] + selected[2][metric]
            expected = dict(a_mean=rational(Fraction(a,2)), b_mean=rational(Fraction(b,2)),
                b_over_a=rational(Fraction(b,a)), b_minus_a_mean=rational(Fraction(b-a,2)))
            require(scale["blocks"][block][metric] == expected, "recomputed every rational "+metric+" N"+str(n)+" block"+str(block))
            ratios[metric].append(Fraction(b,a))
        computed.append(dict(events=n,block=block,**scale["blocks"][block]))
    require(scale["median_block_ratios"] == {metric:rational(sorted(values)[1]) for metric,values in ratios.items()},
            "exact three-block medians N"+str(n))
    require(len([p for p in phases if p["phase"] == "final_default_reopen.end" and p["events"] == n]) == 1,
            "default full reopen completed N"+str(n))
for sample in samples:
    starts = [p for p in phases if p["phase"] == "timed_verify.begin" and
        (p["events"],p["block"],p["slot"]) == (sample["scale_events"],sample["block"],sample["slot"])]
    ends = [p for p in phases if p["phase"] == "timed_verify.end" and
        (p["scale_events"],p["block"],p["slot"]) == (sample["scale_events"],sample["block"],sample["slot"])]
    require(len(starts) == len(ends) == 1 and sample["wall_ns"] <= ends[0]["monotonic_ns"]-starts[0]["monotonic_ns"],
            "one explicit begin/end bounds complete call "+str((sample["scale_events"],sample["block"],sample["slot"])))
for attempt in ("attempt-01","attempt-02-v2"):
    directory = HERE / attempt
    old = json.loads((directory / "manifest.json").read_text())
    require(all(sha256((directory/item["name"]).read_bytes()).hexdigest() == item["sha256"] for item in old["files"]),
            "original red/slower raw unchanged: "+attempt)
print(json.dumps(dict(status="AUTHOR_FILE_AND_RATIONAL_CHECK_ONLY",checks=checks,
    check_count=len(checks),all_checks_true=True,blocks=computed,
    SQL_or_harness_rerun=False,per_call_row_counts_measured=False,
    physical_cold_io=False,independent_acceptance=False,production_qualified=False),indent=2,sort_keys=True))
