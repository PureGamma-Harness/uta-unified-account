# Managed observer commands

These are reviewed command templates, not evidence of a started/completed job.
Do not run a long job or observer as part of this preparation. The producer
candidate remains the separate unchanged
`/workspace/uta-operations-freeze-4608ffe` checkout at
`4608ffeda0651f8dafd2cd151618a71ed99aa62e`; it needs its own complete exact-SHA
release validation. Observer changes do not belong in that freeze.

After the separately reviewed real job starts, retain the launcher's actual
driver PID and `/proc/PID/stat` birth ticks immediately. Do not infer driver
identity from a surviving CLI/worker PID or recreate it from an old job later.
Choose an allowed observer CPU and new dedicated output directory outside both
the job and every source checkout. Run from the separately frozen observer
checkout. Replace the uppercase values with that actual job's records:

```sh
taskset --cpu-list OBSERVER_CPU python -B tools/managed_soak_observer.py watch \
  --job /private/NEW_MANAGED_JOB \
  --output /private/NEW_MANAGED_OBSERVER \
  --source /workspace/uta-operations-freeze-4608ffe \
  --frozen-commit 4608ffeda0651f8dafd2cd151618a71ed99aa62e \
  --driver-pid ACTUAL_DRIVER_PID --driver-birth ACTUAL_DRIVER_START_TICKS
```

The CLI creates no listener or worker. It requires Bubblewrap to establish
kernel read-only mounts, or an already equivalently read-only job/source mount.
`--once` takes one bounded observation. The default cadence is 60 seconds.
SIGTERM stops only the observer; it sends no signal to the producer.

After the same actual job has completed at least 21,600 active seconds and all
5,400 rounds, stopped every authority process and verified all final logs, use
the original baseline/output and identities for the explicit producer cold audit.
This cannot upgrade a short or resumed run:

```sh
taskset --cpu-list OBSERVER_CPU python -B tools/managed_soak_observer.py producer-audit \
  --job /private/NEW_MANAGED_JOB \
  --output /private/NEW_MANAGED_OBSERVER \
  --source /workspace/uta-operations-freeze-4608ffe \
  --frozen-commit 4608ffeda0651f8dafd2cd151618a71ed99aa62e \
  --driver-pid ACTUAL_DRIVER_PID --driver-birth ACTUAL_DRIVER_START_TICKS \
  --python EXACT_VALIDATED_PYTHON
```

Then take an independent final observation with the emitted receipt:

```sh
taskset --cpu-list OBSERVER_CPU python -B tools/managed_soak_observer.py watch --once \
  --job /private/NEW_MANAGED_JOB \
  --output /private/NEW_MANAGED_OBSERVER \
  --source /workspace/uta-operations-freeze-4608ffe \
  --frozen-commit 4608ffeda0651f8dafd2cd151618a71ed99aa62e \
  --driver-pid ACTUAL_DRIVER_PID --driver-birth ACTUAL_DRIVER_START_TICKS \
  --producer-receipt /private/NEW_MANAGED_OBSERVER/producer-cold-audit-receipt.json
```

These commands leave all qualification/signoff flags false. Inspect eligibility,
alerts and complete watermarks; observing a process alone does not establish
financial readiness.

During preparation only tiny temporary SQLite fixtures and short namespace
capability probes were run, with the test runner pinned to one allowed CPU.
No managed smoke, throughput case, long run, listener or worker was started.
The repeatable test command from the observer checkout is:

```sh
python -B -c 'import os, unittest; os.sched_setaffinity(0, {min(os.sched_getaffinity(0))}); unittest.main(module=None, argv=["unittest", "tests.test_managed_soak_observer", "tests.test_managed_observer_finance", "-v"])'
```

The tests cover real temporary mode=ro SQLite, closed WAL/no-sidecar creation,
kernel mount protection, no new DDL/files/main-DB mtime changes, explicit close,
valid progress between read snapshots, PID birth/zombie/missing identity,
inflight rounds/faults, clocks and stale/future quotes, immutable source/start/
deadline, full/partial/final budget errors, unknown internal retries, quarantine
and control lanes, missing fields, same-watermark final eligibility with all
flags false, unbound/mismatched cold audit evidence and atomic outputs outside
the job. Tests do not import production risk/ledger/replay services.

The final preparation run executed **37 tests in 0.988 seconds, OK**, pinned to
one allowed CPU. This is a tiny-fixture test result, not a managed soak,
six-hour result or production approval.
