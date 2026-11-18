"""Read existing synthetic adapter artifacts; never run target/native code.

Independent JSON/CAS interpretation and arithmetic only. Git reads and the
explicit new once02 synthetic directory are the complete input allowlist.
No production codec, Coverage, probe, emitter, SQL, /proc, key or old job read.
"""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import time

REPO = Path(__file__).resolve().parents[3]
TIP = "eeaa9558df6a435f1bb2753d3d2c4390f850dfc2"
PREFIX = "evidence/observer-compact-report-v2/adapter-second-once02/"
COPIES = PREFIX + "probe-first-originals/"
ACTUAL = Path("/workspace/uta-observer-v2-adapter-runs/read1-c076b0d-once02")
DOMAIN = b"uta-managed-observer-report-node-v2\0"
ARRAY = "$managed_observer_array_v2"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def unique_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate-json-key")
            result[key] = value
        return result
    def invalid(value):
        raise ValueError("nonfinite-json")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def git(*args):
    return subprocess.check_output(["git", "--no-optional-locks", *args], cwd=REPO,
        stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def blob(path, commit=TIP):
    return git("show", commit + ":" + path)


def object_value(path):
    return unique_json(blob(PREFIX + path))


def integer(value, expected):
    assert type(value) is int and value == expected


def manual_report(index):
    # Literal schema/workload arithmetic; no target report() or codec call.
    return {"format": 1, "synthetic": True, "sample_wall_ns": index, "active_elapsed_seconds": index * 60.0,
        "logical_point": "stable_boundary", "active_rounds": [], "completed_rounds": 3,
        "unresolved_steps": 0, "unresolved_faults": 0, "planned_faults": [], "alerts": [],
        "final_evidence_eligible": False, "finance": {"counts": {"uta_command_inbox": 3},
            "command_inbox": [{"sequence": number, "command_id": "synthetic-adapter:" + str(number),
                "state": "SUCCEEDED", "kind": "SUBMIT_ORDER", "control_lane": False,
                "attempts": 0, "last_error_present": False, "last_error_code": None} for number in (1, 2, 3)],
            "retry_alerts": [], "watermark": {"format": 2, "sha256": "0" * 64},
            "golden": {"compared": True, "passed": True, "errors": []}}}


def restore_independently(envelope, nodes, visited):
    """Independent bounded protocol walk; never imports target helpers."""
    visits = 0
    def node(identity):
        nonlocal visits
        visits += 1
        assert visits <= 200 and type(identity) is str and len(identity) == 64
        raw = nodes[identity]
        assert digest(DOMAIN + raw) == identity
        value = unique_json(raw)
        assert canonical(value) == raw
        visited.add(identity)
        return value
    publication = node(envelope["publication_sha256"])
    assert canonical(publication) == canonical({key: value for key, value in envelope.items() if key != "publication_sha256"})
    assert type(publication["report_version"]) is int and publication["report_version"] == 2

    def tree(identity, depth):
        if identity is None:
            return []
        assert depth <= 64
        value = node(identity)
        assert set(value) == {"kind", "version", "anchor", "value", "left", "right", "count"}
        assert value["kind"] == "array_item" and type(value["version"]) is int and value["version"] == 2
        assert len(canonical(value)) <= 4096 and len(canonical(value["value"])) <= 2048
        record = value["value"]
        anchor = [["sequence", "command_id"], [record["sequence"], record["command_id"]]]
        assert value["anchor"] == digest(b"observer-array-anchor-v2\0" + canonical(anchor) + b"\0" + b"0")
        for child in (value["left"], value["right"]):
            if child is not None:
                assert node(child)["anchor"] >= value["anchor"]
        records = tree(value["left"], depth + 1) + [record] + tree(value["right"], depth + 1)
        integer(value["count"], len(records))
        return records

    def decode(value):
        if not isinstance(value, dict):
            return value
        if ARRAY in value:
            assert set(value) == {ARRAY} and set(value[ARRAY]) == {"root", "count"}
            ref = value[ARRAY]
            records = tree(ref["root"], 1)
            integer(ref["count"], len(records))
            return records
        return {key: decode(item) for key, item in value.items()}

    reference = publication["full_reference"]
    root = node(reference["root"])
    assert set(root) == {"kind", "version", "value"} and root["kind"] == "full_reference"
    assert type(root["version"]) is int and root["version"] == 2
    complete = decode(root["value"])
    raw = canonical(complete)
    integer(reference["canonical_bytes"], len(raw))
    assert reference["sha256"] == digest(raw)
    return complete


def current_synthetic_inventory():
    """Only the two approved new synthetic roots; no process/kernel reads."""
    result, entries = {}, 0
    def visit(directory, relative, depth):
        nonlocal entries
        assert depth <= 6
        with os.scandir(directory) as scan:
            for entry in scan:
                entries += 1
                assert entries <= 64
                details = entry.stat(follow_symlinks=False)
                path = relative + "/" + entry.name
                if stat.S_ISDIR(details.st_mode):
                    visit(Path(entry.path), path, depth + 1)
                else:
                    assert stat.S_ISREG(details.st_mode)
                    result[path] = details
    for name in ("control", "observer"):
        visit(ACTUAL / name, name, 1)
    return result


def main():
    started = time.monotonic_ns()
    execution, intent = object_value("execution.json"), object_value("intent.json")
    assert execution["source"] == intent["source"]
    assert execution["inputs_before"] == execution["inputs_after"] == intent["inputs_before"]
    integer(execution["exit"], 0); integer(execution["elapsed_ns"], 219154705)
    integer(intent["metadata_preflight_attempt"], 2)
    integer(intent["original_actual_probe_budget"], 1); integer(intent["new_actual_probe_budget_added"], 0)
    proof = {"schema": "uta.actual-adapter-once02.independent-readonly.v1", "reviewed_commit": TIP,
        "source": execution["source"], "reader_scope": "GIT_AND_NEW_SYNTHETIC_FILES_ONLY",
        "target_native_business_SQL_network_or_process_inspection": "NOT_RUN",
        "production_approved": False, "source_bindings": {}, "original_file_bindings": {}}
    assert len(execution["inputs_before"]) == 8
    for path, expected in execution["inputs_before"].items():
        raw = blob(path, execution["source"])
        integer(expected["bytes"], len(raw))
        assert digest(raw) == expected["sha256"] and raw == blob(path)
        proof["source_bindings"][path] = expected
    for name, expected in execution["raw"].items():
        raw = blob(PREFIX + name)
        integer(expected["bytes"], len(raw)); assert digest(raw) == expected["sha256"]
    assert execution["raw"]["stdout.txt"]["bytes"] == 214 and execution["raw"]["stderr.txt"]["bytes"] == 0
    actual_files = current_synthetic_inventory()
    assert set(actual_files) == set(execution["probe_artifacts"]) and len(actual_files) == 24
    copies, original_bytes = {}, 0
    signature = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
    for relative, expected in execution["probe_artifacts"].items():
        details = actual_files[relative]
        assert details.st_uid == os.geteuid() and stat.S_IMODE(details.st_mode) == 0o600 and details.st_size <= 131072
        fd = os.open(ACTUAL / relative, os.O_RDONLY | os.O_NOFOLLOW | os.O_NOATIME)
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno()); raw = stream.read(131073); after = os.fstat(stream.fileno())
        assert signature(details) == signature(before) == signature(after)
        integer(expected["bytes"], len(raw)); assert digest(raw) == expected["sha256"]
        assert raw == blob(COPIES + relative)
        copies[relative] = raw; original_bytes += len(raw)
        proof["original_file_bindings"][relative] = {"bytes": len(raw), "sha256": digest(raw),
            "Git_copy_and_current_original_equal": True, "stable_during_NOFOLLOW_NOATIME_read": True}
    integer(original_bytes, 30330); assert original_bytes <= 131072
    nodes = {Path(path).stem: raw for path, raw in copies.items() if path.startswith("observer/report-v2-nodes/")}
    assert len(nodes) == 11 and sum(map(len, nodes.values())) == 11515
    for key, raw in nodes.items():
        assert digest(DOMAIN + raw) == key and canonical(unique_json(raw)) == raw
    timeline_raw = copies["observer/timeline.jsonl"]
    assert timeline_raw.endswith(b"\n")
    timeline = [unique_json(line) for line in timeline_raw.splitlines()]
    assert len(timeline) == 4 and unique_json(copies["observer/latest.json"]) == timeline[-1]
    visited, frames, reconstructions = set(), [], []
    for index, envelope in enumerate(timeline, 1):
        assert len(canonical(envelope)) <= 16384
        receipt = copies["observer/report-v2-publications/" + str(index) + ".json"]
        assert canonical(envelope) == receipt
        complete = restore_independently(envelope, nodes, visited)
        assert canonical(complete) == canonical(manual_report(index))
        expected_coverage = {"coverage_status": "PENDING", "credited_block": 0, "fatal_financial_codes": [],
            "financial_golden_state": "stable_compared_passed", "planned_fault_inflight_unknown": False,
            "sample_attempt_id": index, "technical_read_unknown": False}
        assert canonical(envelope["coverage_observation"]) == canonical(expected_coverage)
        commands = envelope["summary"]["commands"]
        integer(commands["total"], 3); integer(commands["account_commands"], 3); integer(commands["control_commands"], 0)
        integer(commands["state_counts"]["SUCCEEDED"], 3); integer(commands["kind_counts"]["SUBMIT_ORDER"], 3)
        for field in ("production_approved", "continuous_6h_stability_passed", "continuous_24h_stability_passed", "capacity_10000_per_s_passed"):
            assert envelope[field] is False
        frame = canonical({"wire_schema": "uta.managed_observer.full-input.v2", "sequence": index,
            "report": complete, "reference_sha256": digest(canonical(complete))}) + b"\n"
        frames.append(frame)
        reconstructions.append({"sample": index, "full_canonical_bytes": len(canonical(complete)),
            "full_sha256": digest(canonical(complete)), "expected_wire_frame_bytes": len(frame),
            "receipt_timeline_and_independent_expansion_match": True})
    assert visited == set(nodes)
    receipt_bytes = sum(len(copies["observer/report-v2-publications/" + str(index) + ".json"]) for index in range(1, 5))
    integer(receipt_bytes, 7096)
    live = unique_json(copies["control/first-frame-live.json"])
    queue = unique_json(copies["control/backpressure.json"])
    cleanup = unique_json(copies["control/cleanup.json"])
    provisional = unique_json(copies["control/result.json"])
    assert live["actual_stdout_reader_type"] == "BufferedReader" and live["identity"]["alive"] is True
    assert live["identity"]["identity_matches"] is True and live["stdout_EOF_observed"] is False
    integer(live["complete_first_frame_bytes"], len(frames[0])); integer(len(frames[0]), 1184)
    assert live["classified_monotonic_ns"] < queue["observed_monotonic_ns"]
    assert cleanup["owned_child"] == {key: live["identity"][key] for key in ("pid", "birth")}
    for field in ("Pipes_constructor_completed", "Pipes_identity_binding_matches", "birth_identity_established", "child_was_registered", "no_process_signal_used"):
        assert cleanup[field] is True
    integer(cleanup["child_exit"], 0); integer(cleanup["threads_created"], 2)
    assert cleanup["owned_threads_alive"] is False and cleanup["constructor_fallback"] == {}
    assert provisional["data_only_child"]["pid"] == cleanup["owned_child"]["pid"]
    assert provisional["data_only_child"]["birth"] == cleanup["owned_child"]["birth"]
    assert provisional["data_only_child"]["started_boottime_ns"] < live["classified_monotonic_ns"]
    assert execution["owned_child_after_exit"]["pid"] == cleanup["owned_child"]["pid"]
    assert execution["owned_child_after_exit"]["observed"] is False
    assert unique_json(copies["control/release.json"])["released_after_first_classification"] is True
    outer = unique_json(blob(PREFIX + "stdout.txt"))
    assert outer["adapter_scope_passed"] is True
    integer(outer["frames"], 4)
    assert execution["source_error"] is None and execution["unexpected_special_files"] == []
    integer(queue["pipe_state"]["queued_raw_frames"], 2); integer(queue["pipe_state"]["queue_raw_frame_cap"], 2)
    assert provisional["batch_sizes"] == [1, 2, 1]
    state = provisional["pipe_state"]
    assert state["frames_complete"] is True and state["stdout_read_to_EOF"] is True and state["stdout_fully_retained"] is False
    integer(state["next_decode_sequence"], 5); integer(state["queued_raw_frames"], 0)
    assert state["protocol_failed"] is False
    integer(original_bytes, provisional["measured_control_and_observer_bytes_before_result"] + len(copies["control/result.json"]) + len(copies["control/cleanup.json"]))
    proof["independent_reconstruction"] = {"graphs": reconstructions, "all_11_CAS_nodes_hash_verified_and_visited": True,
        "four_FIFO_reports_match_manual_schema_and_canonical_values": True, "manual_consumer_receipts_match": True,
        "expected_wire_sha256_from_reconstructed_reports_only": digest(b"".join(frames)),
        "observed_kernel_wire_digest_hex_available": False,
        "kernel_wire_hash_comparison": "SOURCE_CONDITIONED_SUCCESS_GUARD_NOT_FRESH_KERNEL_REPLAY"}
    proof["budgets"] = {"regular_files": 24, "logical_scope_bytes": original_bytes, "cap_bytes": 131072,
        "CAS_files": 11, "CAS_bytes": 11515, "publication_receipt_bytes": receipt_bytes,
        "outer_raw_bytes_separate": 214, "delivery_copy_bytes_separate": 30330,
        "physical_allocation_power_loss_or_long_run_budget_proven": False}
    proof["phase_and_lifecycle"] = {"first_frame_bytes": 1184, "captured_first_identity": cleanup["owned_child"],
        "captured_live_first_frame_before_EOF_release": True, "raw_queue_occupancy_observed": 2,
        "child_exit_at_queue_observation": queue["child_exit"], "kernel_pipe_writer_block_proven": False,
        "captured_Popen_wait_return_exit_and_two_threads_dead": True,
        "fresh_past_PID_inspection_or_wait_reexecution": False,
        "history_depends_on_frozen_source_and_original_captured_metadata": True}
    proof["source_conditioned_transient_checks"] = {"Popen_reap_and_stream_close": "frozen_source_wait_and_drainer_finally_plus_original_exit_zero",
        "reopen_and_idempotent_put_receipt_query": "current_graph_unique_receipts_plus_source_exit_guards_no_target_reexecution",
        "negative_zero_quota_consumer_once": "captured_provisional_flags_and_frozen_source_guard_no_reexecution"}
    preserved = {}
    for reference in ("c9a0a12", "22e3f9a", "fce1213"):
        commit = git("rev-parse", reference).decode().strip()
        paths = git("diff-tree", "--no-commit-id", "--name-only", "-r", commit + "^", commit).decode().splitlines()
        for path in paths:
            assert blob(path, commit) == blob(path)
        preserved[commit] = {"added_files_unchanged": len(paths)}
    proof["preserved_prior_records"] = preserved
    proof["conclusion"] = "SCOPED_ACTUAL_ADAPTER_EVIDENCE_PASS_WITH_EXPLICIT_LIMITS"
    proof["elapsed_ns"] = time.monotonic_ns() - started
    print(json.dumps(proof, sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
