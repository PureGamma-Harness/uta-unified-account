"""File/Git/ZIP checks only. No product import, SQL, decrypt, or execution."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

SOURCE = "909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0"
CONTROL = "e466b67faba5fb586d68f8bd35fb7f9c7a63336e"
MARKER = "07c3dc6c3d8a6cbd239e3463b55f8904cac99340"
RUN = 44172126501
ARTIFACT = 14366519733
ZIP_SHA = "1ae12dfbdb8f7798b6579de4d6988bb0628a481320f7d7e04e98b000d3f290d4"
ROOT_OBSERVATION_SHA = "9305ed86655f66004cddf83ad4721d4d44a88070baf15d2da5d1cb1c69dcb9e6"
STREAMS = {"driver.stdout", "driver.stderr", "case-owner.stdout", "case-owner.stderr"}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args])


def check(evidence, archive):
    def raw(name):
        return (evidence / name).read_bytes()

    def record(name):
        return json.loads(raw(name))

    provider = record("jobs-artifacts-provider-safe.json")
    run = record("run-provider-safe.json")
    assert (run["id"], run["run_attempt"], run["head_sha"], run["conclusion"]) == (RUN, 1, MARKER, "failure")
    assert run["event"] == "push"
    assert len(provider["artifacts"]) == len(provider["jobs"]) == 1
    artifact = provider["artifacts"][0]
    assert (artifact["id"], artifact["size_in_bytes"], artifact["digest"]) == (ARTIFACT, 228850, "sha256:" + ZIP_SHA)
    assert artifact["workflow_run"]["head_sha"] == MARKER
    assert artifact["workflow_run"]["id"] == RUN
    job = provider["jobs"][0]
    assert (job["id"], job["run_id"], job["conclusion"]) == (134353729679, RUN, "failure")
    steps = {s["number"]: s for s in job["steps"]}
    assert all(steps[n]["conclusion"] == "success" for n in range(1, 8))
    assert steps[8]["conclusion"] == "failure"
    assert all(steps[n]["conclusion"] == "success" for n in (9, 10))
    assert archive.stat().st_size == 228850 and sha(archive.read_bytes()) == ZIP_SHA
    manifest = record("manifest.json")
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        names = z.namelist()
        assert len(names) == len(set(names)) == 12
        assert set(names) == {r["name"] for r in manifest["files"]} | {"manifest.json"}
        for item in manifest["files"]:
            content = z.read(item["name"])
            assert len(content) == item["bytes"] and sha(content) == item["sha256"]
            if item["name"].endswith(".json"):
                assert content == raw(item["name"])
        assert z.read("manifest.json") == raw("manifest.json")
    control = record("control.json")
    assert control["control_commit"] == CONTROL and control["source_commit"] == SOURCE
    registration = control["registration"]
    assert registration["registration_commit"] == MARKER
    assert registration["manifest_parent_commit"] == CONTROL
    assert registration["branch"] == "refs/heads/perf/approved-m0-20261117-02"
    assert git("show", "-s", "--format=%P", MARKER).decode().strip() == CONTROL
    assert git("diff-tree", "--no-commit-id", "--name-status", "-r", MARKER).decode().strip() == "A\tconfig/independent-m0-approved.json"
    assert sha(git("show", MARKER + ":config/independent-m0-approved.json")) == registration["manifest_sha256"]
    assert sha(git("show", CONTROL + ":tools/independent_m0_controller.py")) == control["controller_sha256"]
    assert sha(git("show", CONTROL + ":tools/m0_stream_escrow.py")) == control["escrow_tool_sha256"]
    snapshot = record("source-manifest.json")
    assert snapshot["source_commit"] == SOURCE
    assert git("rev-parse", SOURCE + "^{tree}").decode().strip() == snapshot["source_tree"]
    tree = git("ls-tree", "-r", "-z", SOURCE)
    objects = {}
    for entry in tree.split(b"\0"):
        if entry:
            info, path = entry.split(b"\t", 1)
            mode, kind, oid = info.decode().split()
            assert kind == "blob" and mode in ("100644", "100755")
            objects[path.decode()] = oid
    assert set(objects) == set(snapshot["files"]) and len(objects) == 5518
    # Stream one object at a time: no checkout, database, or native import.
    batch = subprocess.Popen(["git", "cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    checked = 0
    try:
        for path, oid in objects.items():
            batch.stdin.write((oid + "\n").encode())
            batch.stdin.flush()
            header = batch.stdout.readline().decode().split()
            assert header[:2] == [oid, "blob"]
            size = int(header[2])
            content = batch.stdout.read(size)
            assert len(content) == size and batch.stdout.read(1) == b"\n"
            assert snapshot["files"][path] == {"bytes": size, "sha256": sha(content)}
            checked += 1
    finally:
        batch.stdin.close()
        assert batch.wait(timeout=5) == 0
    result = record("result.json")
    assert result["status"] == "UNKNOWN_OR_NO_GO"
    b, p = result["cases"]
    assert (b["case"], b["status"], b["error_type"], b["error_code"]) == ("B", "UNKNOWN", "GateError", "whole_case_unknown")
    owner = b["owner_cleanup"]
    assert owner["outcome"] == "UNKNOWN" and owner["returncode"] == -15
    assert owner["leader_reaped"] and owner["stdout_stderr_complete"]
    assert owner["watchdog_reason"].startswith("health_or_resource_gate:[Errno 2]")
    assert owner["watchdog_reason"].endswith("/B/workload/authority/shard-0000.sqlite3-shm'")
    assert b["complete_outer_monotonic_ns"] == 1173100276
    assert b["pipeline_owner_pid"] == 2606 and b["pipeline_owner_birth_ticks"] == 9324
    assert (p["case"], p["status"]) == ("P", "NOT_RUN")
    assert b["stream_escrow"]["status"] == "PASS"
    assert b["stream_escrow"]["four_closed_streams_retained"]
    runtime = record("runtime.json")
    assert runtime["journal_mode"] == "wal" and runtime["synchronous"] == 2 and runtime["replication"] is False
    observation = record("root-public-decryption-observation.json")
    assert sha(raw("root-public-decryption-observation.json")) == ROOT_OBSERVATION_SHA
    assert (observation["run_id"], observation["attempt"], observation["provider_artifact_id"]) == (RUN, 1, ARTIFACT)
    assert (observation["control_commit"], observation["marker_commit"], observation["source_commit"]) == (CONTROL, MARKER, SOURCE)
    assert observation["helper_sha256"] == control["escrow_tool_sha256"]
    assert observation["all_four_valid"] and not observation["plaintext_published"] and not observation["production_approved"]
    by_name = {r["name"]: r for r in manifest["files"]}
    observations = observation["stream_observations"]
    assert len(observations) == 4 and {r["stream"] for r in observations} == STREAMS
    for stream in observations:
        item = by_name["escrow-B-safe/" + stream["stream"] + ".cms"]
        assert (stream["cipher_sha256"], stream["cipher_bytes"]) == (item["sha256"], item["bytes"])
        assert stream["status"] == "AUTHENTICATED_CONTAINER_VALID"
        assert stream["authenticated_decrypt_exit_zero"] and stream["binding_valid"]
        assert stream["bytes"] == 0 and stream["sha256"] == sha(b"")
        assert stream["protocol"]["protocol_verified"] and not stream["plaintext_published"]
    assert observation["certificate"]["public_spki_der_sha256"] == b["stream_escrow"]["recipient_spki_sha256"]
    return {"status": "PASS_READ_ONLY_FIRST_FAILURE_CLOSURE", "source_files_verified": checked,
            "provider_zip_sha256": ZIP_SHA, "provider_zip_crc_pass": True,
            "run_attempt": 1, "run_conclusion": "failure", "B": "UNKNOWN", "P": "NOT_RUN",
            "four_root_attested_authenticated_stream_bytes": [0, 0, 0, 0],
            "root_attestation_binding_crosschecked": True, "independently_decrypted_here": False,
            "financial_driver_start_or_settlement_inferred": False, "production_approved": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(check(Path(__file__).resolve().parent, args.zip), sort_keys=True))
