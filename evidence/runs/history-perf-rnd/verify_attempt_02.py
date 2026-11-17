"""Author's pure-data check of retained V2 raw; no UTA import, SQL or rerun.

This is not an independent acceptance signature. Another group must review.
"""
from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def main():
    raw = HERE / "attempt-02-v2"
    launch = json.loads((raw / "launch.json").read_text())
    summary = json.loads((raw / "summary.json").read_text())
    phases = [json.loads(line) for line in (raw / "phases.jsonl").read_text().splitlines()]
    manifest = json.loads((raw / "manifest.json").read_text())
    inputs = {
        "uta/storage.py": "da519ff4c2f30ddae57d4994278dd193168637ce18b83abadb4187e94a7824a6",
        "tests/test_history_postings_stream.py": "79042a89658d7270b83aa2cbe87a79f8214691fafffd5d9dff104fff07c5f1da",
        "evidence/runs/history-perf-rnd/run_component_v2.py": "ebd866d5781c817ceb7336900a9698fa81b4b44a27086ca53473858cc7380585",
    }
    checks = {
        "all_retained_raw_hashes_match": all(sha256((raw / item["name"]).read_bytes()).hexdigest() == item["sha256"] for item in manifest["files"]),
        "exact_candidate": launch["candidate"] == "3a48aa4eb27b8c7a61241c7045b25faf24a8737c",
        "exact_runtime": launch["runtime_commit"] == summary["runtime_commit"] == "dd502ae538618c6d17a3bd2eae708e09526e9d4c",
        "exact_runtime_test_harness_input_hashes": launch["before_sha256"] == launch["after_sha256"] == inputs and all(summary["before_sources"].get(name) == digest for name, digest in inputs.items()),
        "all_53_source_hashes_unchanged": summary["before_sources"] == summary["after_sources"] and len(summary["before_sources"]) == 53,
        "normal_exit_no_watchdog_or_forced_cleanup": launch["exit_code"] == 0 and launch["watchdog"] is False and launch["forced_cleanup"] is False,
        "owned_pid_reaped_and_gone": launch["child_reaped"] is True and launch["child_proc_absent"] is True,
        "cpu4_whole_under_15_seconds": launch["cpu_affinity"] == summary["affinity"] == [4] and type(launch["elapsed_ns"]) is int and 0 < launch["elapsed_ns"] < 15_000_000_000,
        "no_internal_timeout_or_other_failure_reported": summary["success"] is True and "error" not in summary and summary["elapsed_ns_before_summary_write"] < 14_000_000_000,
        "all_27_differentials_pass_no_skip": summary["differential"] == dict(tests=27, failures=0, errors=0, skipped=0),
        "two_confirmed_256_event_fixture_commits": [(p["committed_batches"], p["committed_events"]) for p in phases if p["phase"] == "fixture.batch_commit_return"] == [(1,256), (2,512)],
        "four_ordered_measurements": len(summary["calls"]) == 4 and [p["ordered_postings"] for p in summary["calls"]] == [False,True,False,True],
        "final_default_full_reopen_phase_completed": [p["phase"] for p in phases][-3:] == ["final_default_cold_reopen.begin", "final_default_cold_reopen.end", "scratch.cleanup_complete"],
        "literal_initial_and_final_references_equal": summary["initial_literal_reference"] == summary["final_default_cold_reference"],
        "reference_manual_counts_balances_head": summary["initial_literal_reference"]["events"] == 512 and summary["initial_literal_reference"]["postings"] == 1024 and summary["initial_literal_reference"]["balances_units"] == {"a/USD":-512,"b/USD":512} and summary["initial_literal_reference"]["head"] == "5a02b906bca3dc227c15b5be57632d2fa5f54b50089d0823151c0d96f1b47049",
        "physical_cold_io_not_claimed": all(call["physical_cold_io_established"] is False for call in summary["calls"]),
    }
    for index, call in enumerate(summary["calls"]):
        mode = index % 2 == 1
        checks["call_" + str(index) + "_complete_counts_and_statement_classes"] = (
            call["index"] == index and call["returned_events"] == call["selected_events"] == 512
            and call["selected_postings"] == 1024
            and call["actual_fetched_row_counts"] == dict(event=512,payload=1024,balance=2,group_metadata=512 if mode else 0)
            and call["posting_select_statements"] == (2 if mode else 512)
            and call["posting_group_select_statements"] == int(mode)
            and call["posting_payload_select_statements"] == (1 if mode else 512)
            and call["sql_statements"] == (13 if mode else 523))
    original = HERE / "attempt-01"
    old_manifest = json.loads((original / "manifest.json").read_text())
    checks["original_red_raw_retained_unchanged"] = all(sha256((original / item["name"]).read_bytes()).hexdigest() == item["sha256"] for item in old_manifest["files"])
    assert all(checks.values()), checks
    print(json.dumps({"checks": checks, "all_checks_true": True,
        "author_component_correctness_scope": "PASS", "independent_acceptance": "PENDING_OTHER_GROUP",
        "wall_ns_old_new_old_new": [call["wall_ns"] for call in summary["calls"]],
        "speedup_established": False, "production_qualified": False,
        "source_or_workload_rerun": False}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
