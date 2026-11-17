"""Run one recorded, CPU2 archive-only or read-only package phase."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import time

root = Path("/workspace/uta-package-8b7f544")
source = Path("/workspace/uta-observer-freeze-8b7f544")
work = Path("/workspace/uta-package-8b7f544-work.txt").read_text().strip()
work = Path(work)
phase = sys.argv[1]
os.sched_setaffinity(0, {2})
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
env.pop("PYTHONPATH", None)
if phase == "zip":
    name = "tracked-zip"
    argv = [sys.executable, str(source / "evidence/20261117-package-a35fd56/verify_tracked_ci_zips.py"),
            "--source", str(source), "--manifest", str(work / "artifact-manifest.json"),
            "--wheel", str(work / "artifacts/uta_reference_exchange-0.5.0a1-py3-none-any.whl"),
            "--sdist", str(work / "artifacts/uta_reference_exchange-0.5.0a1.tar.gz"),
            "--unpacked-source", str(work / "sdist-unpacked/uta_reference_exchange-0.5.0a1"),
            "--provenance", str(root / "ci-zip-provenance.json"), "--output", str(work / "tracked-ci-zip-checks")]
elif phase == "strict":
    name = "strict-control-bindings"
    argv = [sys.executable, str(root / "verify_control_bindings.py"), "--source", str(source),
            "--work", str(work), "--records", str(root), "--provenance", str(root / "ci-zip-provenance.json"),
            "--output", str(root / "strict-control-bindings.json")]
else:
    raise SystemExit("phase must be zip or strict")
stdout, stderr = (root / (name + "." + stream + ".txt") for stream in ("stdout", "stderr"))
execution = root / ("tracked-zip-execution.json" if phase == "zip" else "strict-execution.json")
assert not any(path.exists() for path in (stdout, stderr, execution)), "retain existing phase evidence"
started = datetime.now(timezone.utc).isoformat()
at = time.monotonic_ns()
with stdout.open("wb") as out, stderr.open("wb") as err:
    result = subprocess.run(argv, cwd=root, env=env, stdout=out, stderr=err)
record = {"source_commit": "8b7f544fcbdfd540d43de1d6560022c6ebbd3799", "phase": phase,
          "argv": argv, "cwd": str(root), "affinity": sorted(os.sched_getaffinity(0)),
          "cohosted": True, "exclusive_cpu_or_cpuset": False,
          "started_utc": started, "finished_utc": datetime.now(timezone.utc).isoformat(),
          "started_monotonic_ns": at, "finished_monotonic_ns": time.monotonic_ns(),
          "returncode": result.returncode, "expected_returncode": 0,
          "helper_sha256": sha256(Path(argv[1]).read_bytes()).hexdigest(),
          "financial_workload_executed": False, "environment": {"PYTHONPATH": None, "PYTHONDONTWRITEBYTECODE": "1"}}
record["seconds"] = (record["finished_monotonic_ns"] - at) / 1_000_000_000
execution.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
print(json.dumps({key: record[key] for key in ("phase", "seconds", "returncode")}), flush=True)
raise SystemExit(result.returncode)
