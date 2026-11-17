"""Capture a bounded pure reference run; never connects to a database."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
LABEL = sys.argv[1]
COMMAND = ["taskset", "-c", "4", sys.executable, "scripts/credit_v2_financial_reference.py"]
START = datetime.now(timezone.utc).isoformat()
BEFORE = time.monotonic()
RUN = subprocess.run(COMMAND, cwd=ROOT, text=True, capture_output=True, timeout=30)
(OUT / (LABEL + ".stdout.json")).write_text(RUN.stdout)
(OUT / (LABEL + ".stderr.txt")).write_text(RUN.stderr)
META = {"argv": COMMAND, "start": START, "end": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": time.monotonic() - BEFORE, "exit_code": RUN.returncode, "timeout_seconds": 30,
        "runtime_status": "PENDING_ACTUAL_CANONICAL_PAYLOAD_AND_CAPTURE", "synthetic_only": True,
        "python": sys.version, "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "file_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in
                        ("scripts/credit_v2_financial_reference.py", "docs/credit-v2-independent-financial-oracle.md",
                         "evidence/runs/credit-v2-independent-oracle/run_reference.py")}}
(OUT / (LABEL + ".metadata.json")).write_text(json.dumps(META, indent=2, sort_keys=True) + "\n")
print(json.dumps({"label": LABEL, "exit_code": RUN.returncode, "elapsed_seconds": META["elapsed_seconds"]}))
raise SystemExit(RUN.returncode)
