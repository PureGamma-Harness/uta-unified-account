"""Refresh first-party documentation evidence; never accesses customer APIs.

Run from the repository: python tools/collect_sources.py --output NEW_FILE.json
Only short excerpts and hashes are retained. A document changing its bytes is a
new observation, not permission to silently change a financial rule.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
from html import unescape
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

MANIFEST = Path(__file__).resolve().parents[1] / "evidence/sources/official-20261114.json"


def collect(records):
    observations = []
    for source in records:
        record = {key: source[key] for key in ("source_id", "requested_url", "marker")}
        record.update(retrieved_at=datetime.now(timezone.utc).isoformat(),
                      authorization="public documentation; no account credentials")
        try:
            request = Request(record["requested_url"], headers={"User-Agent": "UTA-Research/0.2"})
            with urlopen(request, timeout=20) as response:
                raw = response.read(4 * 1024 * 1024 + 1)
                if len(raw) > 4 * 1024 * 1024:
                    raise ValueError("document exceeds collection limit")
                record.update(status=response.status, resolved_url=response.url)
            html = raw.decode("utf-8", "replace")
            html = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
            text = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html))).strip()
            position = text.lower().find(record["marker"].lower())
            record.update(sha256=sha256(raw).hexdigest(), bytes=len(raw),
                          marker_found=position >= 0,
                          excerpt=" ".join(text[max(0, position - 30):].split()[:55]) if position >= 0 else "",
                          scope="Document observation only; not proprietary risk-parameter replication")
        except Exception as exc:
            record.update(status="unavailable", error=str(exc))
        observations.append(record)
    return observations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="new evidence file; never overwrites")
    args = parser.parse_args()
    sources = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if args.output.exists():
        parser.error("output already exists; preserve the previous observation")
    observations = collect(sources)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(observations, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return int(any(row["status"] != 200 or not row.get("marker_found") for row in observations))


if __name__ == "__main__":
    raise SystemExit(main())
