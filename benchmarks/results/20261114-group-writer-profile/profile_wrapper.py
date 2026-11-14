"""Writer-only diagnostic profile; not part of the capacity comparison."""
from pathlib import Path
import cProfile
from datetime import datetime, timezone
import gzip
from hashlib import sha256
import json
import pstats
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import uta.admission as admission
from benchmarks.run_group_benchmark import Configuration, run

OUT = Path(__file__).resolve().parent
Original = admission.AdmissionBatcher


class ProfiledBatcher(Original):
    def _run(self):
        profiler = cProfile.Profile()
        try:
            return profiler.runcall(super()._run)
        finally:
            profiler.dump_stats(str(OUT / "writer.prof"))


admission.AdmissionBatcher = ProfiledBatcher
started = datetime.now(timezone.utc).isoformat()
summary = run(Configuration(mode="batch", duration=1, rate=1000, accounts=100, workers=4,
                            queue_capacity=512, batch_size=64), OUT / "probe")
finished = datetime.now(timezone.utc).isoformat()
with (OUT / "profile.txt").open("w") as log:
    pstats.Stats(str(OUT / "writer.prof"), stream=log).sort_stats("cumulative").print_stats(45)
raw = OUT / "writer.prof"
(OUT / "writer.prof.gz").write_bytes(gzip.compress(raw.read_bytes(), mtime=0))
raw.unlink()
metadata = {"purpose": "writer-only cProfile diagnostic, excluded from capacity table",
            "instrumentation": "AdmissionBatcher subclass wraps only writer _run in cProfile; runtime source unchanged",
            "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "wrapper_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
            "started_at": started, "finished_at": finished,
            "unique_orders": summary["counts"].get("durable_accepted", 0),
            "production_approved": False}
(OUT / "profile-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
files = [OUT / "profile_wrapper.py", OUT / "profile.txt", OUT / "writer.prof.gz", OUT / "profile-metadata.json"]
(OUT / "manifest.json").write_text(json.dumps({"files": {p.name: {"sha256": sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size} for p in files}}, indent=2) + "\n")
print(json.dumps(metadata, indent=2))
