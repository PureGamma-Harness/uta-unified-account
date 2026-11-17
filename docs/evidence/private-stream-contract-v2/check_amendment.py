"""Pure V2 design arithmetic; no transport, auth, SQL, or UTA execution."""
from pathlib import Path
from hashlib import sha1, sha256
import base64
from datetime import datetime, timezone
import json
import subprocess

ROOT = Path(__file__).resolve().parents[3]
ORIGINAL = "c68aabe82ce78ab10a3c886894ce8dc9952302d1"
REVIEW = "f7a86b5a7a53476fb277272b0d5cb7c679d73540"
fixture_path = ROOT / "tests/fixtures/managed_private_stream_v2_contract.json"
data = json.loads(fixture_path.read_text())
assert data["status"] == "DESIGN_NOT_IMPLEMENTED"
assert data["amends_design_commit"] == ORIGINAL and data["review_commit"] == REVIEW
assert data["runtime_tests_executed"] == data["websocket_or_sql_operations_executed"] == 0
cases = {row["id"]: row for row in data["cases"]}
assert len(cases) == len(data["cases"]) == 28
assert all(row["execution_status"] == "NOT_RUN_REQUIREMENT" for row in cases.values())

original_names = subprocess.check_output(["git", "diff-tree", "--no-commit-id",
    "--name-only", "-r", ORIGINAL], cwd=ROOT, text=True).splitlines()
assert len(original_names) == 5
original_hashes = {}
for name in original_names:
    original = subprocess.check_output(["git", "show", ORIGINAL + ":" + name], cwd=ROOT)
    assert (ROOT / name).read_bytes() == original, name
    original_hashes[name] = sha256(original).hexdigest()
old_cases = json.loads((ROOT / "tests/fixtures/managed_private_stream_v1_contract.json").read_text())["cases"]
assert len(old_cases) == 30 and all(row["execution_status"] == "NOT_RUN_REQUIREMENT" for row in old_cases)

row = cases["WS-V2-C031"]
n = row["input"]["codepoint_count"]
wrapper = len('{"x":""}')
assert wrapper + n == row["expected"]["python_character_count"]
assert wrapper + n * len("汉".encode()) == row["expected"]["utf8_byte_count"]
assert wrapper + n < row["input"]["old_python_character_limit"] < wrapper + n * 3

alias = cases["WS-V2-C036"]
canonical, alternate = (alias["input"][name] for name in ("canonical_key", "alias_key"))
decoded = base64.b64decode(canonical, validate=True)
assert len(decoded) == 16 and decoded == base64.b64decode(alternate, validate=True)
assert decoded.hex() == alias["input"]["signed_challenge_hex"]
assert base64.b64encode(decoded).decode() == canonical != alternate
for key, field in ((canonical, "canonical_accept"), (alternate, "alias_accept")):
    actual = base64.b64encode(sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
    assert actual == alias["expected"][field]

# Verify only finite literal header/length arithmetic, not a protocol parser.
for number, expected_plain in ((37, (1004).to_bytes(2, "big")),
                               (38, (1010).to_bytes(2, "big")), (40, b"\x03")):
    row = cases[f"WS-V2-C{number:03d}"]
    frame = bytes.fromhex(row["input"]["client_frame_hex"])
    assert bytes(value ^ frame[2 + i % 4] for i, value in enumerate(frame[6:])) == expected_plain
for number in range(43, 49):
    row = cases[f"WS-V2-C{number:03d}"]
    n = row["input"]["json_utf8_payload_bytes"]
    header = 2 if n <= 125 else 4 if n <= 65535 else 10
    assert header == row["expected"]["RFC_header_bytes"]
    assert n + header == row["expected"]["whole_wire_frame_bytes"]
    assert (n + header <= 262144) is row["expected"]["may_enqueue"]
budget = cases["WS-V2-C049"]
assert sum(budget["input"]["application_frames_wire_bytes"]) == 524288
assert 524288 + budget["input"]["additional_being_encoded_wire_bytes"] == 786432
assert 786432 + sum(budget["input"]["control_reserve_frames_wire_bytes"]) == 786686
for number, start_name, budget_name, expected in (
    (51, "first_frame_byte_monotonic_ms", "configured_header_budget_ms", "header_absolute_deadline_ms"),
    (52, "first_frame_byte_monotonic_ms", "configured_frame_budget_ms", "frame_absolute_deadline_ms"),
    (53, "accepted_monotonic_ms", "configured_total_budget_ms", "handshake_absolute_deadline_ms")):
    row = cases[f"WS-V2-C{number:03d}"]
    assert row["input"][start_name] + row["input"][budget_name] == row["expected"][expected]

registry = json.loads((Path(__file__).parent / "iana-close-codes.json").read_text())
assert any(row["value"] == "1010" for row in registry["close_code_records"])
assert any(row["value"] == "4000-4999" for row in registry["close_code_records"])
report = {"checked_at": datetime.now(timezone.utc).isoformat(),
    "original_design_commit": ORIGINAL, "review_commit": REVIEW,
    "original_five_files_byte_identical": True, "original_sha256": original_hashes,
    "original_requirements": 30, "additional_requirements": len(cases),
    "fixture_sha256": sha256(fixture_path.read_bytes()).hexdigest(),
    "static_vector_arithmetic_consistent": True, "runtime_tests_executed": 0,
    "websocket_or_sql_operations_executed": 0,
    "documentation_http_source_fetches_this_amendment": 1,
    "timelines_are_requirements_not_scheduling_measurements": True,
    "future_requirements_verified_by_runtime": False, "production_approved": False}
(Path(__file__).parent / "static-checks.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({key: value for key, value in report.items() if key != "original_sha256"}))
