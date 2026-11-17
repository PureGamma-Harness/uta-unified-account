"""Check the retained first-party document bytes; no HTTP or runtime probe."""
from hashlib import sha256
import json
from pathlib import Path

source = Path("/workspace/uta-ledger-py310-fixture-raw")
metadata = json.loads((source / "python311-sqlite3-official-source.json").read_text())
data = (source / "python311-sqlite3-official.html").read_bytes()
assert len(data) == metadata["bytes"] == 271807
assert sha256(data).hexdigest() == metadata["sha256"] == "d85840c64dce31026a463e64234e4d395bfaa71fadc3475a9d3eec50f9fba61a"
assert metadata["status"] == 200 and metadata["section_excerpt_html"] in data.decode()
assert "Changed in version 3.11:" in metadata["section_excerpt_html"]
assert "Added support for disabling the authorizer using" in metadata["section_excerpt_html"]
result = {"url": metadata["url"], "root_original_fetch_at": metadata["fetched_at"], "recorded_HTTP_status": 200,
          "actual_HTML_bytes": len(data), "actual_HTML_sha256": sha256(data).hexdigest(),
          "exact_section_is_in_actual_HTML": True,
          "quote": "Changed in version 3.11: Added support for disabling the authorizer using None.",
          "review_action": "file/hash/section check only; no HTTP request or scalar execution"}
output = Path(__file__).resolve().parent / "official-source-review.json"
assert not output.exists()
output.write_text(json.dumps(result, indent=2) + "\n")
