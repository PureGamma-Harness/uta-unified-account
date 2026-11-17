"""Bounded local synthetic evidence capture; no service or network calls."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
LABEL, PYTHON, TARGET = sys.argv[1:]
ARGV = ["taskset", "-c", "4", PYTHON] + (
    ["tests/pm_independent_next_oracle.py"] if TARGET == "oracle" else
    ["-m", "unittest", "-v"] + TARGET.split(","))
START = datetime.now(timezone.utc).isoformat()
BEFORE = time.monotonic()
try:
    RUN = subprocess.run(ARGV, cwd=ROOT, capture_output=True, text=True, timeout=30)
    CODE, STDOUT, STDERR = RUN.returncode, RUN.stdout, RUN.stderr
except subprocess.TimeoutExpired as exc:
    CODE, STDOUT, STDERR = 124, exc.stdout or b"", exc.stderr or b""
    STDOUT = STDOUT.decode() if isinstance(STDOUT, bytes) else STDOUT
    STDERR = STDERR.decode() if isinstance(STDERR, bytes) else STDERR
ELAPSED = time.monotonic() - BEFORE
(OUT / (LABEL + ".stdout.txt")).write_text(STDOUT)
(OUT / (LABEL + ".stderr.txt")).write_text(STDERR)
FILES = ["uta/portfolio.py", "uta/products.py", "uta/ledger.py", "uta/risk.py",
         "tests/pm_independent_next_oracle.py", "tests/test_pm_independent_next.py",
         "docs/pm-independent-next-golden.md", "evidence/runs/pm-independent-next/run.py"]
METADATA = {"started_at": START, "argv": ARGV, "timeout_seconds": 30, "exit_code": CODE,
            "elapsed_seconds": ELAPSED, "cpu_affinity_requested": [4], "synthetic_only": True,
            "runner_python": sys.version, "runner_sqlite": sqlite3.sqlite_version,
            "platform": platform.platform(),
            "source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "sut_runtime": subprocess.check_output([PYTHON, "-c", "import os,sys; print(sys.version); print(sorted(os.sched_getaffinity(0)))"], text=True).strip(),
            "file_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                            for name in FILES if (ROOT / name).exists()}}
(OUT / (LABEL + ".json")).write_text(json.dumps(METADATA, indent=2, sort_keys=True) + "\n")
print(json.dumps({"label": LABEL, "exit_code": CODE, "elapsed_seconds": ELAPSED}, sort_keys=True))
raise SystemExit(CODE)
