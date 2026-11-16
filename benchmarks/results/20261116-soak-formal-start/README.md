# Corrected-source live 24-hour job: pending

- Producer SHA: `88755a9f2ba3bb672ca5d354b3037796f00c6611`.
- Immutable checkout: `/workspace/uta-soak-source-88755a9`.
- Actual original start: **2026-11-16T21:36:13.820942+00:00**.
- Actual deadline: **2026-11-17T21:36:13.820942+00:00**.
- Detached PID at launch: **4471**, with process-start identity and heartbeat recorded.
- Private continuing authority: `/workspace/uta-soak-runs/formal-20261116T213613Z-88755a9/authority.sqlite3`.

The early live snapshot is 121 seconds after the new actual start: 31 completed rounds, 62 real matching receipts, 124 paired fill legs, 130 orders and 10 actual cancellations (4 partially filled). Live orders and positions are zero at this snapshot; golden checks agree. Market version122 has actual age0.226s. All 24h/capacity/production acceptance fields remain false. This is an early observation, never a completed long-run result.

The 13 retained short selfchecks run on this exact immutable checkout. In particular, a real queued fault test commits the first round's buy order and loses its result while two later rounds are durably queued: later rounds create no financial state until ordered recovery, and original IDs subsequently yield exactly six real paired matches. This closes the preliminary driver's queue-causality gap. Unit-test temporary databases are not counted as live soak time.

The prior 69ce43b job was gracefully stopped only after the corrected job was observed healthy. It is preserved as **INTERRUPTED_KNOWN_ISSUE**, with original database, original start/deadline, all logs, 119 completed rounds, 238 matches, 476 fill legs, no live orders/positions, successful final log audit and false stability approval. Its 472.216639 confirmed active seconds are not carried into this new job. Its raw status reports a retained /proc identity as process_alive; the separately retained ps output establishes oldPID3968 is a non-running zombie underPID1, while newPID4471 is an active process. No old production source or historical time was edited.

`early-log-sample` is only the exported early prefix. All subsequent original evidence remains in the same private authority and segmented logs, bounded by the documented 4GiB financial/6GiB total/free1GiB guards. No financial DB is committed. The run is low-rate, co-hosted, single-host cache0 baseline stability; it does not accept the later managed modules or 10k/s capacity.

Query current state rather than treating this snapshot as live:

```bash
python /workspace/uta-soak-source-88755a9/benchmarks/run_soak.py status --directory /workspace/uta-soak-runs/formal-20261116T213613Z-88755a9
```

Actions `stop` and `resume` retain original time and business IDs. Never overwrite this directory, reset its financial database, change its started_at, or combine the preliminary elapsed time with this candidate. A completed 24-hour report is still pending.
