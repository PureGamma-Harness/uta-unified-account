"""Static design consistency only: no UTA import, SQL, socket, or runtime test."""
from pathlib import Path
from hashlib import sha1, sha256
import base64
from datetime import datetime, timezone
import hmac
import json
import subprocess


ROOT = Path(__file__).resolve().parents[3]
BASE = "a35fd56fc98126b3e5cced8a459bd04ca580e537"
FIXTURE = ROOT / "tests/fixtures/managed_private_stream_v1_contract.json"
data = json.loads(FIXTURE.read_text())
assert data["status"] == "DESIGN_NOT_IMPLEMENTED"
assert data["base_commit"] == BASE
assert data["runtime_tests_executed"] == data["websocket_or_sql_operations_executed"] == 0
assert data["production_approved"] is False
cases = {case["id"]: case for case in data["cases"]}
assert len(cases) == len(data["cases"]) == 30
assert all(case["execution_status"] == "NOT_RUN_REQUIREMENT" for case in cases.values())

# Recompute only public example mathematics, independently of production code.
example = cases["WS-C001"]
raw = example["input"]["raw_http"]
assert raw.endswith("\r\n\r\n")
lines = raw.split("\r\n")
method, target, version = lines[0].split(" ")
headers = dict(line.split(": ", 1) for line in lines[1:] if line)
assert (method, version) == ("GET", "HTTP/1.1")
decoded_key = base64.b64decode(headers["Sec-WebSocket-Key"], validate=True)
assert len(decoded_key) == 16 and target.split("challenge=", 1)[1] == decoded_key.hex()
accept = base64.b64encode(sha1((headers["Sec-WebSocket-Key"] +
    "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()).decode("ascii")
assert accept == example["expected"]["headers"]["Sec-WebSocket-Accept"]
canonical = json.dumps(["UTA-HMAC-SHA256", "1", headers["X-UTA-Tenant"],
    headers["X-UTA-Audience"], headers["X-UTA-Key-Id"], headers["X-UTA-Timestamp-Ms"],
    headers["X-UTA-Nonce"], method, target, sha256(b"").hexdigest()],
    separators=(",", ":"), ensure_ascii=True).encode("ascii")
assert canonical.decode() == example["input"]["canonical_hmac_bytes_ascii"]
assert hmac.new(example["input"]["synthetic_key_ascii"].encode(), canonical,
    sha256).hexdigest() == headers["X-UTA-Signature"]

identity = data["source_stream_identity_example"]
canonical_identity = json.dumps([identity["authority"], identity["path"],
    identity["device"], identity["inode"], identity["account"]],
    sort_keys=True, separators=(",", ":"), ensure_ascii=True)
assert identity["stream_id"] == "account-stream:" + sha256(canonical_identity.encode()).hexdigest()
page = cases["WS-C003"]["input"]["frame"]
assert [row["sequence"] for row in page["events"]] == [407, 413]
assert all(row["sequence"] == row["cursor"] for row in page["events"])
assert page["page"]["next_after"] == page["page"]["until"] == 420
assert cases["WS-C004"]["input"]["frame"]["page"]["next_after"] == 425
assert cases["WS-C028"]["input"]["event_sequence"] == 2**53 + 1

# Literal RFC control examples: XOR arithmetic only, not a frame parser.
ping = bytes.fromhex(cases["WS-C014"]["input"]["client_ping_hex"])
assert ping[:2] == b"\x89\x82"
assert bytes(value ^ ping[2 + index % 4] for index, value in enumerate(ping[6:])) == b"hi"
close = bytes.fromhex(cases["WS-C015"]["input"]["client_close_hex"])
assert bytes(value ^ close[2 + index % 4] for index, value in enumerate(close[6:])) == (1000).to_bytes(2, "big")

source_files = ["uta/durable_gateway.py", "uta/durable_views.py", "uta/request_signing.py",
                "uta/gateway.py", "docs/durable-views.md", "docs/managed-read-client.md",
                "tests/test_durable_views.py", "tests/test_request_signing.py"]
source_hashes = {}
for name in source_files:
    frozen = subprocess.check_output(["git", "show", BASE + ":" + name], cwd=ROOT)
    assert frozen == (ROOT / name).read_bytes(), name
    source_hashes[name] = sha256(frozen).hexdigest()
report = {"checked_at": datetime.now(timezone.utc).isoformat(), "base_commit": BASE,
    "source_hashes": source_hashes, "fixture_sha256": sha256(FIXTURE.read_bytes()).hexdigest(),
    "fixture_cases": len(cases), "static_vector_arithmetic_consistent": True,
    "runtime_tests_executed": 0, "websocket_or_sql_operations_executed": 0,
    "documentation_http_source_fetches": 1, "future_requirements_verified_by_runtime": False, "production_approved": False}
(Path(__file__).parent / "static-checks.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({key: value for key, value in report.items() if key != "source_hashes"}))
