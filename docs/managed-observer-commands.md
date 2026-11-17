# Managed observer commands

**Current review correction:** the 4608 preparation examples below are retained
history. A real smoke now waits for the new 7ae94eb full QA and root GO; use
[the pending smoke plan](managed-observer-smoke-plan.md). The stdio/private-clone
corrections at the end supersede the older public-snapshot assumptions.

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

## Reviewed launcher and private-clone boundary

Do not redirect the observer CLI's stdout/stderr directly to regular files.
Inherited file descriptors can bypass a read-only mount, so the CLI deliberately
rejects regular fd0/1/2 before any output. A trusted launcher uses PIPEs and
saves only the known JSON response in its owned external `0700` directory.
For a bounded `watch --once`, the launcher pattern is:

```python
import hashlib, json, os, subprocess, sys
from pathlib import Path

output = Path("/private/NEW_MANAGED_OBSERVER")
output.mkdir(mode=0o700, parents=True, exist_ok=True)
assert output.stat().st_uid == os.geteuid()
assert output.stat().st_mode & 0o777 == 0o700
command = [sys.executable, "-B", "tools/managed_soak_observer.py", "watch", "--once",
    "--job", "/private/NEW_MANAGED_JOB", "--output", str(output),
    "--source", "/workspace/uta-operations-freeze-7ae94eb",
    "--frozen-commit", "7ae94eb8a783f8e134ac90c11a713df7bb02d5f1",
    "--driver-pid", "ACTUAL_DRIVER_PID", "--driver-birth", "ACTUAL_DRIVER_START_TICKS"]
result = subprocess.run(command, cwd="SEPARATELY_FROZEN_OBSERVER_CHECKOUT",
    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    close_fds=True, timeout=45)
response = json.loads(result.stdout) if result.stdout else {"observation_failed_closed": True}
assert response.get("synthetic") is True or response.get("observation_failed_closed") is True
record = {"exit_code": result.returncode, "response": response,
    "stderr_present": bool(result.stderr),
    "stderr_sha256": hashlib.sha256(result.stderr).hexdigest()}
descriptor = os.open(output / "launcher-response.json",
    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
with os.fdopen(descriptor, "w") as stream:
    json.dump(record, stream, sort_keys=True, allow_nan=False)
```

The launcher never prints or archives unknown stderr. A zero CLI exit alone is
not a final pass; inspect the full record, phase, alerts, eligibility and literal
false signoff flags. Keep inherited host PID namespace visibility for birth
checks. Unknown proc permission/format observations are not proof of death.

For explicit producer cold audit, the complete SQLite clone is **private** and
does contain historical writer/control nonces and internal paths. Root chose
this route to preserve complete schema/identity semantics. Only the opaque
private clone is supplied to the actual producer audit; public evidence consists
of the allowlisted redacted receipt/observations. Never recursively archive
`private-audit/`, the producer's `private/`, authentication storage or raw stderr.
Normal cleanup does not guarantee cleanup after an uncatchable kill.

Current defaults are `--max-private-clone-bytes 6442450944`,
`--min-private-free-bytes 1073741824` and
`--max-address-space-bytes 2147483648`. The clone estimate includes main databases,
WAL, allowed log segments and exact validation sidecars. Budget failures remain
unknown/failed, with no new receipt. The address-space ceiling is not a measured
RSS result. Timeline JSONL streams to disk; no full six-hour CID history is held
in memory. Use a new controlled filename for each one-shot launcher response.

After the independent boundary fixes, the bounded suite executed **47 tests in
1.221 seconds, OK**, on one allowed CPU. The actual producer read-only audit was
exercised only on a hand-built temporary SQLite unit fixture, with no service
startup or release-qualification claim. The one-minute real smoke is pending.
