# Live 24-hour job start evidence

This is an early live snapshot, not a completed 24-hour acceptance result.

- Frozen runtime and driver: `69ce43bcda7d44ba9e2f82ec647ef08abfb0c6b0` (baseline `ad3f5b8`).
- Actual original start: `2026-11-16T21:28:34.484473+00:00`.
- Original deadline: `2026-11-17T21:28:34.484473+00:00`.
- Detached process PID at launch: `3968`; verify process identity and heartbeat dynamically rather than trusting this historical PID.
- Continuing private authority: `/workspace/uta-soak-runs/baseline-20261116T212834Z-69ce43b/authority.sqlite3`.
- Immutable source checkout: `/workspace/uta-soak-source-69ce43b`.

The recorded early snapshot has 17 completed roundtrips, 34 real matches and 68 paired fill legs; actual golden checks agree, positions are zero, the synthetic feed has reached version65, and heartbeat/market age are recorded. The job remains running with 21,600 planned rounds. None of these numbers claim future completion.

The original financial database is never reset or committed to Git. `early-log-sample` is only the exported prefix available at collection; all subsequent evidence remains in the same live database and its private segmented logs. The selfcheck files retain an actual 12-test run on the frozen checkout, including receipt-loss recovery, partial matching, credit replay, bounded overload, fencing, disk limits, read-only validation and export-cursor recovery. Temporary unit-test databases are separate from the continuing financial authority and are not counted as soak duration.

Other engineers and tests may share the host. This job is a low-rate, single-host, cache0 baseline stability experiment, not 10k/s capacity, replicated durability, managed-module acceptance or real-funds approval. Final checks are pending until at least the actual deadline.

Query current state:

```bash
python /workspace/uta-soak-source-69ce43b/benchmarks/run_soak.py status --directory /workspace/uta-soak-runs/baseline-20261116T212834Z-69ce43b
```

Stop and retain unfinished obligations with action `stop`; recover on the same frozen source with action `resume`. Original time and IDs remain unchanged, and any interruption is recorded. Never delete the authority or change started_at to claim a new duration.
