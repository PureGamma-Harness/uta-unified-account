"""Strict bounded read-only JSON/trace review; no SQLite/imported UTA/processes."""
from datetime import datetime
from decimal import Decimal
from fractions import Fraction
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import signal
import subprocess
from time import monotonic

SOURCE = "3af589415ccfdb65ed84a952184a77030319a3df"
BASE = "d421df3fc5123e8267f0eecf8bb5efdc37cd0dc6"
RAW = Path("/tmp/uta-expired-publication-d421/candidate-3af-once")
ROOT = Path(__file__).resolve().parents[3]
os.sched_setaffinity(0, {3})
signal.alarm(3)
t0 = monotonic()
def load(path):
    blob = Path(path).read_bytes()
    assert len(blob) < 2 * 1024 * 1024
    return json.loads(blob, parse_float=Decimal), {"bytes":len(blob),"sha256":sha256(blob).hexdigest()}
launch, launchhash = load(RAW/"launch.json")
result, resulthash = load(RAW/"worker/result.json")
blob = (RAW/"worker/events.jsonl").read_bytes()
assert len(blob)<2*1024*1024
lines = blob.splitlines()
assert len(lines)==440 and all(len(line)<65536 for line in lines)
rows = [json.loads(line,parse_float=Decimal) for line in lines]
assert all(type(r["monotonic_ns"]) is int for r in rows)
def events(kind):return [r for r in rows if r["kind"]==kind]
def one(kind):
    selected=events(kind);assert len(selected)==1,(kind,len(selected));return selected[0]
def ns(value):return Fraction(str(value))*1000000000
checks = {}
checks["one_case_exact_source"] = (result["source_commit"]==SOURCE and result["base_source"]==BASE and result["tests_run"]==1 and result["failures"]==result["errors"]==0 and result["case_passed"] is True and result["test_failure_observed"] is False)
checks["original_not_reclassified"] = result["historical_original_assertion_reproduced"] is False
checks["logger_and_trace_hash"] = result["logger_failures"]==[] and sha256(blob).hexdigest()==result["trace_sha256"]
checks["exit_no_watchdog"] = launch["exit_code"]==0 and launch["timed_out"] is False and launch["wall_seconds"]<30
checks["CPU_and_runtime"] = one("original_case_start")["affinity"]==[2] and one("original_case_start")["python"].startswith("3.10.")
checks["case_end"] = one("original_case_end")["passed"] is True
case = one("case_observations")["observation"]
binding = case["selected_binding"];pid=binding["pid"]
spawned = {e["identity"]["pid"]:e["identity"] for e in events("spawn_return")}
assert len(spawned)==3
checks["original_PID_birth"] = str(spawned[pid]["start_ticks"])==str(binding["start_ticks"]) and spawned[pid]["pgid"]==launch["worker_identity"]["pid"]
checks["no_forced_cleanup"] = case["cleanup_forced_kill"] is False and all(e["forced_cleanup"] is False for e in launch["owned_children"])
final = events("final_owned_child")
checks["all_original_owned_gone"] = (len(final)==3 and {e["pid"] for e in final}==set(spawned) and all(e["pidfd_exited"] is True and e["identity"].get("present") is False for e in final) and {e["original"]["pid"] for e in launch["owned_children"]}==set(spawned) and all(e["current"].get("present") is False for e in launch["owned_children"]) and all(e.get("present") is False for e in launch["final_owned_identities"]))
old,new,unexpired=case["captured_lease"],case["new_lease"],case["unexpired_control_lease"]
checks["same_unexpired_generation_control"] = (old["active"] is True and unexpired["active"] is True and old["owner_pid"]==unexpired["owner_pid"]==pid and old["generation"]==unexpired["generation"] and old["expires_ns"]==unexpired["expires_ns"] and unexpired["now_ns"]-old["now_ns"]>=100000000 and unexpired["now_ns"]<unexpired["expires_ns"])
checks["new_actual_generation"] = new["active"] is True and new["generation"]>old["generation"] and new["owner_pid"] in spawned and new["owner_pid"]!=pid
attempts=case["capture_attempts"]
checks["bounded_capture"] = 1<=len(attempts)<=8 and all(ns(attempt["at"])-ns(attempts[0]["stop_sent_at"])<5000000000 for attempt in attempts)
for attempt in attempts:
    candidate,retained=attempt["candidate"],attempt["retained_after_stop"]
    assert candidate and retained and candidate==retained
    for record in retained:
        fields=record["kernel_record"].split()
        assert len(fields)==9 and fields[2:5]==["FLOCK","ADVISORY","READ"] and int(fields[5])==pid and fields[7:]==["0","EOF"]
        major,minor,inode=fields[6].split(":")
        assert os.makedev(int(major,16),int(minor,16))==record["device"] and int(inode)==record["inode"]
checks["busy_then_available_retained_SH"] = (len(attempts)==2 and attempts[0]["writer_availability_probe"]=={"available":False,"classification":"sqlite_busy_legacy_builtin","native_errorcode":None} and attempts[1]["writer_availability_probe"]=={"available":True,"classification":"begin_immediate_rolled_back_zero_dml","native_errorcode":None})
checks["original_lease_window"] = all(value["active"] is True and value["owner_pid"]==pid and value["generation"]==old["generation"] and 0<value["expires_ns"]-value["now_ns"]<=250000000 for value in [case["publication_entry_lease"],case["publication_thread_entry_lease"]])
start=ns(case["publication_started_at"]);captured=ns(case["captured_at"])
relative={key:(ns(case[key])-start)/1000000000 for key in ["old_pidfd_exit_observed_at","publication_first_ex_entered_at","new_generation_observed_at","publication_finished_at"]}
checks["three_milestones_original_five"] = all(0<=relative[k]<=5 for k in relative if k!="publication_finished_at") and case["recovery_horizon_seconds"]==5
checks["publication_lifecycle_fifteen"] = 0<=relative["publication_finished_at"]<=15 and case["publication_lifecycle_watchdog_seconds"]==15 and case["api_phase_timeout_seconds"]==5
checks["actual_source_EX_event"] = any(e["exclusive"] is True and e["thread"].startswith("Thread-1") and abs(Fraction(e["monotonic_ns"])-ns(case["publication_first_ex_entered_at"]))<1000000 for e in events("gate_acquired"))
checks["actual_old_exit_event"] = any(e["pid"]==pid and e["monotonic_ns"]>start and e["monotonic_ns"]<start+5000000000 for e in events("kernel_pidfd_exit"))
publication=[e for e in events("publication_return") if e["version"]==2]
assert len(publication)==1
pub=publication[0];digest=case["original_snapshot_sha256"]
expected={str(shard):f"market:3:{shard}:"+digest[:16] for shard in (0,1)}
checks["two_original_publication_CIDs"] = (pub["publishing"] is False and set(pub["receipts"])=={"0","1"} and all(pub["receipts"][s]["command_id"]==expected[s] and pub["receipts"][s]["state"]=="SUCCEEDED" for s in expected) and [pub["receipts"][s]["sequence"] for s in ("0","1")]==[4,3])
checks["original_publication_once"] = len([e for e in events("publication_start") if e["version"]==2])==1
finance=case["finance"]
checks["reported_financial_assertions"] = finance["ledger_and_debt_unchanged"] is True and finance["orders"]==finance["accepted_events"]==0 and finance["schema_versions"]=={"ledger_schema":[[1,1]],"uta_schema":[[3]]} and finance["cache_configuration"]=={"market_cache_size":0,"normal_cache_size":0,"reserve_cache_size":0}
checks["recorded_finance_counts"] = len(events("own_finance_before_cleanup"))==2 and all(e["orders"]==e["accepted"]==0 for e in events("own_finance_before_cleanup"))
log=(RAW/"unittest.txt").read_text()
checks["unittest_original_complete"] = bool(re.search(r"Ran 1 test in [0-9.]+s\s+OK\s*$",log)) and "ResourceWarning:" not in log and "Exception ignored in:" not in log
source_blob=subprocess.check_output(["git","show",SOURCE+":tests/test_durable_faults.py"],cwd=ROOT)
checks["exact_test_source_hash"] = sha256(source_blob).hexdigest()==result["test_source_sha256"]
changed=subprocess.check_output(["git","diff","--name-only",BASE,SOURCE,"--","uta","tools","benchmarks","formal","scripts","config","deploy","pyproject.toml","MANIFEST.in"],cwd=ROOT,text=True).strip()
checks["runtime_packaging_git_bytes_unchanged"] = changed==""
assert all(value is True for value in checks.values()),checks
value={"source_commit":SOURCE,"scope":"independent original trace/JSON review only; no native/SQL rerun", "checks":checks,"strict_component_scope_passed":True,
    "timings_from_publication_start_seconds":{k:float(v) for k,v in relative.items()},
    "timings_from_captured_fault_seconds":{"old_pidfd_exit":float((ns(case["old_pidfd_exit_observed_at"])-captured)/1000000000),"publication_complete":float((ns(case["publication_finished_at"])-captured)/1000000000)},
    "launch_UTC_start":launch["started_at"],"launch_UTC_end":launch["finished_at"],"launch_wall_seconds":float(launch["wall_seconds"]),
    "trace_rows":len(rows),"trace_sha256":sha256(blob).hexdigest(),"test_source_sha256":result["test_source_sha256"],"publication_CIDs":pub["receipts"],"snapshot_sha256":digest,
    "owned_pids":sorted(spawned),"financial_data_independently_reopened":False,
    "financial_limit":"ledger/debt/schema/cache equality are original passed code assertions plus recorded counts; raw before/after financial rows are not present",
    "zero_DML_limit":"BEGIN/ROLLBACK/total_changes equality is a passed source assertion and classification, not independently rerun SQL",
    "business_order_admitted_or_settled":False,"fills_or_performance_proven":False,"five_second_end_to_end_SLO_proven":False,
    "original_d421_qualified":False,"full_QA_CI_package_qualified":False,"production_approved":False,
    "launch_input":launchhash,"result_input":resulthash,"CPU":sorted(os.sched_getaffinity(0)),"pure_review_wall_seconds":monotonic()-t0}
Path(__file__).with_name("result.json").write_text(json.dumps(value,indent=2)+"\n")
signal.alarm(0)
print(json.dumps({k:value[k] for k in ["strict_component_scope_passed","pure_review_wall_seconds","timings_from_publication_start_seconds","timings_from_captured_fault_seconds"]},indent=2))
