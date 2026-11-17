# Independent managed soak observer

This delivery prepares an observer for a future synthetic six-hour job on
`4608ffeda0651f8dafd2cd151618a71ed99aa62e`. It starts no job, listener, worker,
background observer, or load generator. The earlier 887/observer experiment,
its source, databases, original timing and PIDs 4471/8784 are outside its scope.
Keep the producer freeze unchanged; freeze this observer in a separate checkout.

`tools/managed_soak_observer.py` and `tools/managed_observer_finance.py` import
only the standard library and each other. The `watch` command does not import or
call managed status, production risk/fee/PnL/credit/replay functions, HTTP,
financial constructors, initialization, repair, service launch or process
signals. The producer's `ManagedSoak.status()` writes progress and is therefore
not used. The observer never opens `private/`, TLS keys, signing profiles, the
authentication/nonce database, private stderr or writer nonce columns. It reads
only explicit public/synthetic JSON, checkpoint, control and financial columns.
Unexpected account/order/command/error labels are hashed or replaced with an
unknown code before publication. It never reads process command lines or
environments. PID evidence is `/proc/PID/stat` state and birth ticks.

The CLI reexecutes itself with Bubblewrap: `/` is mounted read-only and only the
dedicated external observer directory is bound writable. It verifies the
producer job and source mounts are read-only. No filesystem permissions or
producer files are changed. A missing mount capability fails closed. This is
necessary because SQLite `mode=ro` alone can create WAL sidecars, including a
WAL database closed with neither sidecar present. A Python sidecar precheck
alone cannot close the subsequent open race.

Each SQLite connection uses `mode=ro`, `query_only`, an authorizer denying DML,
DDL, ATTACH and write PRAGMAs, an explicit read transaction and explicit SQLite
close. There is no raw open/close of a database inode. Live reads use normal WAL
locking and require existing `-wal` and `-shm`; they wait up to five seconds for
the producer's transient sidecars and otherwise report unknown. The kernel
read-only mount also prevents creation if a sidecar vanishes after that check.
No immutable or nolock shortcut reads a live authority. After an already
observed driver's exact birth identity has exited, persisted progress is
completed and a baseline exists, a no-sidecar database may be read immutable.
Final eligibility additionally requires the listener and worker to be stopped
and the lease inactive. A zombie or reused PID does not count as alive.

The external `baseline.json` pins the original job manifest, source commit and
hashes, observer code hashes, boot/start/deadline, planned budget, file identities
and the launch-recorded driver PID/birth. It cannot reset timing on resume.
Runtime and complete validation source hashes, qualification artifacts and the
golden specification are checked against the original exact candidate. Only
the checkpoint, router and financial inode identities are inspected; the
authentication file is excluded. A changed/missing required field, source,
start/deadline, boot, schema or identity fails closed.

Every observation writes one fsynced `timeline.jsonl` row and atomically replaces
`latest.json`. Temporary files live beside those outputs, outside the job and
source, so they cannot trigger the producer's historical rglob/stat race.
Default cadence is 60 seconds, measured after a sample; a slow sample does not
cause a catch-up burst. Do not run multiple observers into one output directory.
Reserve an independent output/disk budget: retaining every CID every minute
can produce several GB across six hours. Keep that private timeline outside Git
and the producer's directory budget. No large-run RSS, sampling-latency or output
size benchmark has been performed during this preparation.

The record contains actual driver/listener births, worker generation and lease
heartbeat age, quote timestamp/age/future status, publication barrier and
control CID hashes, every account/control CID's state/attempts/last_error
presence/quarantine, financial counts, residual live orders and positions,
gross principal/interest and the full closed owner/asset balance map. Any
internal retry is an alert with cause unknown, including a later SUCCEEDED
receipt. Technical retries are never reported as zero or silently attributed to
a planned fault. REJECTED and QUARANTINED are independently alerted. Live
processes alone never produce a financial-ready claim; that field stays unknown.

Checkpoint transactions bracket financial reads. ACTIVE rounds, unresolved
steps/fault recovery or checkpoint progress mark the result
`inflight_or_unknown`, without comparing a partial round to the previous
completed-round budget. A second financial read and checkpoint bracket must
agree before comparing a stable boundary. Separate read-only snapshots may
advance; that advancement is not labeled corrupt debt.

The independent integer oracle checks three fixed accounts, USD/BTC scales,
the complete gross balance/debt map, fixed credit limits, 80,000 USD minor-unit
fees per trader per completed round, two-satoshi principal repayments, original
funding/loan history, six account commands, four orders/fills, two correctly
paired matches, partial cancellation and eight linked decisions per round. It
also checks per-fill fees, canonical archive content IDs, journal hash chains,
posting projection and per-currency conservation. It uses no production math.

The final business watermark hashes explicit financial/audit/command columns
and includes ledger sequence/hash and business event sequence. It excludes
noisy lease heartbeats/nonces. It is bound to the exact final checkpoint event
sequence/hash and immutable baseline contract. Final logs are independently
checked byte-for-byte, including gzip segment continuity and every checkpoint
event's hash-chain coverage; a claimed `logs_verified` alone is insufficient.

`final_evidence_eligible` requires all 5,400 planned rounds, actual producer
active time of at least 21,600 seconds, the original same-boot deadline, one
continuous controller session, both real fault recoveries, no unknown effect,
no internal retry, final integer/relational reconciliation, genuinely verified
logs and a further independent database reopen at the same watermark. Uptime
after the producer exits does not extend its active time. Cold market/heartbeat
age can naturally become stale and remains visible without inventing a new feed.

The explicit `producer-audit` command is a separate final evidence step. It
refuses to execute before every other six-hour final gate has passed. Because
the producer's older RO helper may create cold WAL sidecars, this command uses
SQLite backup to make an exact stopped public snapshot outside the job,
checks its financial and checkpoint watermarks, then runs the frozen producer's
`audit` CLI against that snapshot. No private/auth/TLS/nonce material is copied.
The temporary public snapshot is removed. Only a redacted receipt with the
audit-output digest, frozen commit and equal before/after final watermarks is
retained. The original authority remains kernel read-only. The subsequent
independent reopen and receipt must match the same watermark; counts alone or
an unbound historical `cold-audit.json` cannot satisfy this gate.

Every long-run, 24-hour, production and 10,000/s flag remains literal false,
including when evidence becomes eligible. The observer is not a formal signoff.
Until the new job actually runs and finishes, there is no six-hour evidence.

Prepared commands and the bounded verification record are in
[managed-observer-commands.md](managed-observer-commands.md).
