"""Read existing Git/files and Decimal arithmetic; never import project code."""
import ast
from decimal import Decimal
import hashlib
import html
import json
from pathlib import Path
import re
import subprocess

CANDIDATE = "a78cbb4fa4f887e1561e7b8772020af5bc448c17"
PREFIX = "evidence/reviews/ci-6010e92-sqlite-protocol-timing/"


def git(*args):
    return subprocess.check_output(["git", *args])


def blob(commit, path):
    return git("show", commit + ":" + path)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def record(name):
    return json.loads(blob(CANDIDATE, PREFIX + name))


facts = record("timing-and-source-facts.json")
consistency = record("read-only-consistency.json")
official = record("sqlite-official-documents.json")
assert git("show", "-s", "--format=%P", CANDIDATE).decode().strip() == "6c9082c9d40e5ef5569b826f0fed4cb5528742d6"
for path, expected in consistency["files"].items():
    raw = blob(CANDIDATE, path)
    assert len(raw) == expected["bytes"] and sha(raw) == expected["sha256"]
diag = facts["original_diagnostic"]
raw = blob(facts["original_evidence_commit"], diag["path"])
assert len(raw) == diag["bytes"] == 3952 and sha(raw) == diag["sha256"]
observation = json.loads(raw, parse_float=Decimal)
same = facts["same_monotonic_domain"]
stop = observation["observation"]["last_capture"]["stop_sent_at"]
retained = observation["observation"]["last_capture"]["at"]
diagnostic = Decimal(observation["monotonic_ns"]) / Decimal(10**9)
assert stop == Decimal(same["stop_sent_at_seconds"]) == Decimal("165.771680791")
assert retained == Decimal(same["retained_observation_at_seconds"])
assert diagnostic == Decimal(same["diagnostic_at_seconds"])
assert retained - stop == Decimal(same["stop_to_retained_observation_seconds"]) == Decimal("0.000359296")
assert diagnostic - retained == Decimal(same["retained_observation_to_diagnostic_seconds"]) == Decimal("9.965717269")
assert diagnostic - stop == Decimal(same["stop_to_diagnostic_seconds"]) == Decimal("9.966076565")
assert stop + Decimal(5) == Decimal(same["latest_capture_deadline_upper_bound_seconds"])
assert diagnostic - (stop + Decimal(5)) == Decimal(same["diagnostic_past_latest_capture_deadline_lower_bound_seconds"]) == Decimal("4.966076565")
lease = observation["observation"]["lease_reads_tail"][-1]["value"]
assert lease["expires_ns"] - lease["now_ns"] == facts["distinct_boottime_domain"]["known_last_observed_remaining_ns"] == 4880405184
assert observation["boottime_ns"] - observation["monotonic_ns"] == facts["distinct_boottime_domain"]["diagnostic_boottime_minus_monotonic_ns"] == 1021
assert facts["distinct_boottime_domain"]["no_cross_clock_subtraction_for_stop_or_capture"]
assert facts["original_diagnostic"]["phase"] == "before_original_cleanup"
source = facts["source_commit"]
assert len(facts["source_files"]) == 6
for path, expected in facts["source_files"].items():
    content = blob(source, path)
    assert git("rev-parse", source + ":" + path).decode().strip() == expected["git_blob_oid"]
    assert sha(content) == expected["sha256"] and len(content) == expected["bytes"]
faults = blob(source, "tests/test_durable_faults.py").decode()
nodes = {n.name: n for n in ast.parse(faults).body if isinstance(n, ast.FunctionDef)}
probe = nodes["router_writer_available_without_dml"]
assert [a.arg for a in probe.args.args] == ["path"]
assert [a.arg for a in probe.args.kwonlyargs] == ["own_injected_stop"]
probe_text = ast.get_source_segment(faults, probe)
assert "timeout=0" in probe_text and 'connection.execute("BEGIN IMMEDIATE")' in probe_text
assert "connection.rollback()" in probe_text and "connection.total_changes == changes" in probe_text
assert faults.index("capture_deadline = monotonic() + 5") < faults.index("stop_sent_at = monotonic()")
undo = ast.get_source_segment(faults, nodes["undo_owned_test_stop"])
assert "signal.pidfd_send_signal(pidfd, action)" in undo and "return action == signal.SIGCONT" in undo
fence = blob(source, "uta/writer_fence.py").decode()
clock = next(n for n in ast.parse(fence).body if isinstance(n, ast.FunctionDef) and n.name == "_clock")
assert "time.clock_gettime_ns(time.CLOCK_BOOTTIME)" in ast.get_source_segment(fence, clock)
owned = blob(source, "uta/durable_process.py").decode()
assert "lease = WriterFence(observer).status()\n                        except Exception:\n                            lease = None" in owned
assert official["documents_are_current_public_docs_not_a_verified_3461_native_source_binding"]
assert len(official["documents"]) == 2
documents = []
for item in official["documents"]:
    path = Path(item["private_original_path"])
    body = path.read_bytes()
    assert len(body) == item["bytes"] and sha(body) == item["sha256"]
    assert path.stat().st_mode & 0o777 == 0o600 and path.parent.stat().st_mode & 0o777 == 0o700
    plain = " ".join(html.unescape(re.sub("<[^>]+>", " ", body.decode())).split())
    assert item["exact_quote"] in plain
    assert len(item["exact_quote"].split()) == item["quoted_words_whitespace"]
    documents.append({"name": path.name, "bytes": len(body), "sha256": sha(body), "quote_words": item["quoted_words_whitespace"]})
assert facts["verdict"] == "NO_GO_CAUSE_UNDETERMINED"
print(json.dumps({"reviewed_commit": CANDIDATE, "status": "PASS_SCOPED_READ_ONLY_DOCUMENT_REVIEW",
                  "original_diag_hash_verified": True, "six_source_bindings_verified": True,
                  "same_monotonic_stop_to_diag_seconds": str(diagnostic - stop),
                  "diagnostic_past_latest_capture_deadline_lower_bound_seconds": str(diagnostic - stop - Decimal(5)),
                  "phase_costs_attributed": False, "probe_overrun_or_root_cause_proven": False,
                  "boottime_not_used_for_stop_or_capture_difference": True,
                  "sqlite_3461_native_source_bound": False, "official_existing_bodies": documents,
                  "cleanup_terminal_success_proven": False, "system_qualification": "NO_GO",
                  "network_requests_SQL_project_imports_tests_signals_loads_CI_binary_reads": 0}, sort_keys=True))
