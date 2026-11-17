"""Read-only strict AND for this one fixed synthetic component; no UTA import."""
from hashlib import sha256
import json
import math
from pathlib import Path
import sys

COMMIT = "3af589415ccfdb65ed84a952184a77030319a3df"
HELPER = "d3387b91640171fe81fea4bc2ecf0d49f995eb4ce992affc2db9bc5789f3f8b5"
TEST = "03d48b5d34348a617c0a8cfee69abd9f3449a0c8e95a83020d26b14d70ab3105"


def verify(directory):
    directory = Path(directory)
    def read(name):
        return json.loads((directory / name).read_text())
    def integer(value, expected=None):
        return type(value) is int and (expected is None or value == expected)
    def finite(value):
        return type(value) in (int, float) and math.isfinite(value)
    records = read("copies.json")
    hashes = all(integer(r["bytes"]) and (directory / r["name"]).stat().st_size == r["bytes"]
                 and sha256((directory / r["name"]).read_bytes()).hexdigest() == r["sha256"] for r in records)
    launch, worker, before, after = [read(name) for name in
        ("launch.json", "worker-result.json", "preflight.json", "postflight.json")]
    raw = (directory / "unittest.txt").read_text()
    events = [json.loads(line) for line in (directory / "events.jsonl").read_text().splitlines()]
    observations = [e["observation"] for e in events if e["kind"] == "case_observations"]
    if len(observations) != 1:
        raise ValueError("one complete case observation is required")
    obs = observations[0]
    old = obs["selected_binding"]["pid"]
    captured, unexpired, entry, new = [obs[key] for key in
        ("captured_lease", "unexpired_control_lease", "publication_thread_entry_lease", "new_lease")]
    attempts = obs["capture_attempts"]
    successful = [a for a in attempts if a.get("writer_availability_probe", {}).get("available") is True]
    retained = successful[0]["retained_after_stop"] if len(successful) == 1 else []
    kernel = bool(retained) and all(
        r["kernel_record"].split()[2:6] == ["FLOCK", "ADVISORY", "READ", str(old)]
        and integer(r["fd"]) and integer(r["device"]) and integer(r["inode"]) for r in retained)
    probe = len(successful) == 1 and successful[0]["writer_availability_probe"]["classification"] == "begin_immediate_rolled_back_zero_dml"
    publications = [e for e in events if e["kind"] == "publication_return" and e.get("version") == 2]
    starts = [e for e in events if e["kind"] == "publication_start" and e.get("version") == 2]
    publication = publications[0] if len(publications) == 1 else {}
    receipts = publication.get("receipts", {})
    digest = obs["original_snapshot_sha256"]
    receipt_ok = set(receipts) == {"0", "1"} and len(digest) == 64 and all(
        r["state"] == "SUCCEEDED" and integer(r["sequence"]) and r["sequence"] > 0
        and r["command_id"].split(":")[0] == "market"
        and r["command_id"].split(":")[2:] == [shard, digest[:16]] for shard, r in receipts.items())
    command_maps = [e for e in events if e["kind"] == "receipts_start"
                    and e.get("commands") == {s:r["command_id"] for s,r in receipts.items()}]
    started = obs["publication_started_at"]
    delta = {key: obs[key] - started for key in
        ("old_pidfd_exit_observed_at", "publication_first_ex_entered_at", "new_generation_observed_at")}
    lifecycle = obs["publication_finished_at"] - started
    spawned = {e["identity"]["pid"] for e in events if e["kind"] == "spawn_return"}
    final = [e for e in events if e["kind"] == "final_owned_child"]
    exits = [e for e in events if e["kind"] == "kernel_pidfd_exit" and e["pid"] == old]
    finance = obs["finance"]
    checks = {
        "raw_hashes_and_trace": hashes and worker["trace_sha256"] == sha256((directory / "events.jsonl").read_bytes()).hexdigest(),
        "one_exact_case_passed": integer(worker["tests_run"],1) and integer(worker["failures"],0) and integer(worker["errors"],0)
            and worker["case_passed"] is True and raw.rstrip().endswith("OK") and worker["source_commit"] == COMMIT and worker["test_source_sha256"] == TEST,
        "source_and_helper_unchanged": before["source_commit"] == after["source_commit"] == COMMIT
            and before["source_tree_clean"] is True and after["git_tree_clean"] is True
            and before["source_before"] == after["source_after"] and len(before["source_before"]) == 252
            and after["source_unchanged"] is True and before["runtime_matches_d421"] is True
            and before["helper_sha256"] == after["helper_sha256"] == HELPER and after["helper_unchanged"] is True,
        "cpu2_and_no_logger_watchdog": any(e["kind"] == "original_case_start" and e["affinity"] == [2] and e["python"].startswith("3.10.") for e in events)
            and worker["logger_failures"] == [] and launch["timed_out"] is False and integer(launch["exit_code"],0)
            and finite(launch["wall_seconds"]) and 0 < launch["wall_seconds"] <= 30,
        "bound_kernel_sh_and_zero_dml_probe": integer(old) and kernel and probe and 1 <= len(attempts) <= 8,
        "unexpired_owner_not_killed": captured["active"] is True and unexpired["active"] is True
            and captured["owner_pid"] == unexpired["owner_pid"] == old and captured["generation"] == unexpired["generation"]
            and captured["expires_ns"] == unexpired["expires_ns"] and unexpired["now_ns"] - captured["now_ns"] >= 100_000_000,
        "publication_enters_original_unexpired_edge": entry["active"] is True and entry["owner_pid"] == old
            and entry["generation"] == captured["generation"] and entry["expires_ns"] == captured["expires_ns"]
            and 0 < (entry["expires_ns"] - entry["now_ns"]) / 1e9 <= .25,
        "three_separate_five_second_milestones": all(finite(v) and 0 <= v <= 5 for v in delta.values())
            and new["active"] is True and new["generation"] > captured["generation"]
            and new["owner_pid"] != old and new["owner_pid"] in spawned and len(exits) == 1,
        "original_publication_ids_and_snapshot": len(starts) == len(publications) == 1 and starts[0]["timeout"] == 5
            and publication.get("publishing") is False and receipt_ok and len(command_maps) == 1 and command_maps[0]["timeout"] == 5,
        "publication_success_lifecycle_under15": finite(lifecycle) and 0 <= lifecycle <= 15,
        "finance_and_versions_checked": integer(finance["orders"]) and 0 <= finance["orders"] <= 1
            and integer(finance["accepted_events"]) and 0 <= finance["accepted_events"] <= 1
            and finance["ledger_and_debt_unchanged"] is True
            and finance["schema_versions"] == {"uta_schema":[[3]],"ledger_schema":[[1,1]]}
            and finance["cache_configuration"] == {"market_cache_size":0,"reserve_cache_size":0,"normal_cache_size":0},
        "all_owned_children_cleanly_exited": len(final) == len(spawned) == 3
            and {e["pid"] for e in final} == spawned
            and all(e["pidfd_exited"] is True and e["identity"].get("present") is False for e in final)
            and all(r["forced_cleanup"] is False for r in launch["owned_children"])
            and all(r.get("present") is False for r in launch["final_owned_identities"])
            and obs["cleanup_forced_kill"] is False and after["same_session_query"]["remaining_rows"] == []
            and after["same_session_query"]["stderr_empty"] is True,
    }
    return {"scope":"exact3af single synthetic native component; not release qualification",
            "checks":checks,"component_passed":all(v is True for v in checks.values()),
            "seconds_from_publication_start":{**delta,"publication_finished":lifecycle},
            "seconds_from_captured_fault_to_old_exit":obs["old_pidfd_exit_observed_at"]-obs["captured_at"],
            "seconds_from_captured_fault_to_publication_complete":obs["publication_finished_at"]-obs["captured_at"],
            "capture_attempts":len(attempts),"original_snapshot_content_id_derived":"market:"+digest,
            "actual_publication_receipts":receipts,"finance":finance,
            "original_d421_qualified":False,"production_approved":False}


if __name__ == "__main__":
    result = verify(Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).parent)
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result["component_passed"] else 2)
