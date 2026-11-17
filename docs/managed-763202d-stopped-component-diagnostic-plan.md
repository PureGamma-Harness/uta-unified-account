# Stopped 763202d component diagnostic: execution plan, not a result

This plan has not run. No original SQLite connection, private clone, new SQL or
observer sample has been made. Original status stays paused; six-hour,
financial-final, strict producer receipt, production and capacity flags stay
false regardless of component outcomes. Root must review this concrete plan
before execution. It does not introduce a formal `diagnose-stopped` CLI.

Inputs are original job root
`/workspace/uta-managed-observer-runs/763202d-six-hours-20261117/job`, original
producer code `763202df9cb3ce089721e5281371aff3eab58089` at
`/workspace/uta-operations-freeze-763202d`, independent finance/core code from
`ce3045f66456c1592858d0297f90a9552c7500dd` at
`/workspace/uta-managed-observer`, and exact Python
`/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python`
(3.12.14 / SQLite 3.53.1, matching the original report). Code imports use `-B`
and `PYTHONDONTWRITEBYTECODE=1`; frozen roots remain unchanged.

Use a new private directory
`/workspace/uta-managed-observer-runs/763202d-stopped-component-diagnostic-01`,
mode 0700, with `clone/` and raw diagnostic output private (directories 0700,
files 0600). Parent scratch must be private and the chosen directory absent.
Do not use the old control/observer/job output paths. Do not recursively publish
or archive this directory: the complete authority copies contain historical
writer/control nonces and internal control records.

The intended copy boundary is a **complete financial/control/checkpoint
authority**, not a whole authentication-enabled service deployment. Copy all
three main files, with every currently present sibling auxiliary sharing each
database basename prefix: checkpoint.sqlite3, managed/router.sqlite3 and
managed/shard-0000.sqlite3, including WAL, SHM or rollback journals when present.
Never copy main-only while an auxiliary exists. Preserve complete database
bytes/schema/identity records; never drop nonce/control tables or rewrite data.
Copy job.json, progress.json, bootstrap-plan.json, pending-market.json,
log-segments.json, exact validation summary/worker/log sidecars, and all
manifest-listed gzip event segments plus any producer event-segment temporary
already present. Include existing exact public atomic-publication temporaries
in that same boundary. Reject symlinks and unrecognized/nonregular members.

The existing authentication boundary remains explicit: do not read or copy
private/auth.sqlite3, signing.json, key.pem/cert.pem, any HTTP nonce/auth store,
CLI private stderr, argv, environ or pipe streams. They are not inputs to the
independent finance component or to the expected early paused-audit refusal.
Original metadata may reference those original paths; retain that metadata
byte-for-byte privately without following them or rewriting status/identities.
This narrower copy boundary is part of the plan for root review, not a claim to
have copied every file of the service.

Before copying, reread the original public terminal/launch/baseline JSON and
the 25 previously published PID/birth proc metadata. Require no matching live
process and retain zombie/missing distinctions; do not signal/reap anything.
The original final progress and producer result must still agree on paused,
513 DONE, 2072.722098933 active seconds, one session and original start/deadline.
Require the same boot. Then inventory and SHA-256 every selected source file,
including aux existence, type, size, dev/inode and mode. Copy only these stopped
regular files using bounded ordinary filesystem reads, never an original
SQLite connect/SQL, SQLite backup, borrowed SQLite descriptor, `os.open` probe,
live immutable read, or repair. Hash/inventory the originals again immediately
after copying and after all diagnostics. Any change invalidates the diagnostic.
Copied file hashes must match the first source inventory exactly.

Prove the stored lease expired **in the clone before finance diagnosis**: read
only generation, owner_pid, boot_id, expires_ns and observed_ns, omitting nonce;
compare with current same-boot CLOCK_BOOTTIME. Cross-check any copied registry
PID/birth not in the previous 25 against proc metadata. A live/unknown owner,
future/invalid clock or unexpired lease yields UNKNOWN and no financial claim.
The stored lease state has not yet been measured; elapsed wall time alone will
not be called an observed lease-expiry result.

Only clone paths may be passed to SQLite. Use existing-file URI `mode=ro`,
`isolation_level=None`, sqlite3.Row, `PRAGMA query_only=ON`, an explicit BEGIN
and explicit connection close. Clone filesystem is private/writable so SQLite
may legitimately create/recover its auxiliary mapping; query-only forbids
business/schema SQL mutation. Do not set journal mode, instantiate Database,
ExchangeService, CreditService, Matcher or a worker. If SQLite needs main-file
recovery that RO mode cannot perform, retain the actual error; no repair mode
or source fallback is authorized by this plan.

Run the unmodified producer command on the clone in the exact frozen source:

```text
taskset -c 2 <exact-python312> -B benchmarks/run_managed_soak.py audit --directory <private-clone>
cwd=/workspace/uta-operations-freeze-763202d
```

Actual stdout/stderr must be PIPEs, captured privately with bounded output and
close_fds; never publish raw stderr. The original `audit_job()` first calls
`inspect_job()`, whose `benchmarks.run_soak.readonly()` opens the clone
checkpoint mode=ro/query_only/BEGIN and explicitly closes it. That may create
clone WAL/SHM. It then rejects paused before file-identity/source checks or any
financial constructor. Require an actual nonzero exit and the known
`final audit requires a completed, stopped authority` error; record a redacted
refusal code and raw stream hashes. A pass, different failure, missing output or
timeout is an unexpected outcome, never a cold-audit PASS.

For the independent component, import the existing stdlib-only
`tools/managed_observer_finance.py` from frozen ce. Module import defines
constants/functions; it opens no database and imports no production financial
core. `read_financial()` does not connect, commit, close, initialize or repair.
It requires a caller-owned sqlite3.Row/query-only read transaction and executes
fixed SELECT/PRAGMA reads. Invoke it with **planned=5400, completed=513,
compare_golden=True**. Do not change planned to 513: the original bootstrap debt
was 10800 sat and the partial-run oracle must retain expected remaining 9774
sat. Expected (not observed) counts include orders/fills 2052 each, matches
1026, decisions 4104, journal events 2571 and terminal account commands 3078.

Read the private checkpoint's real contiguous DONE prefix, zero ACTIVE/unknown
step/fault conditions, original clocks/session and last event head before and
after each finance transaction. Validate original public progress against it.
Use existing `verify_logs(clone, checkpoint_head)` for every manifest checksum
and complete event-chain coverage; it only reads private JSON/gzip files. Do
not invoke `Observer.sample()`, producer_audit(), short_cold() or their clone
builders: they either require completed state/long eligibility or connect to
the original source, which is forbidden here. A small local clone-only
connection wrapper must enforce path containment and query-only SQL.

Close/reopen the clone connections independently and run the **actual golden,
quick_check and foreign_key_check again**, comparing complete financial digest,
journal/business heads and checkpoint event head. All transactions must cover
the same logical watermark and copied paused boundary. No cross-snapshot
inflight state is compared with the 513-round oracle. Any mismatch, retry,
quarantine, active round, FK error or missing field remains a failed/unknown
component result. Full journal hashes, per-currency conservation, owner/asset
reconstruction and business joins are the measured scope; full business-event
and risk-engine reexecution remain null.

Limits: one CPU (CPU 2), AS 2 GiB, clone bytes hard cap 6 GiB including any
created auxiliaries, at least 1 GiB remaining disk headroom, public diagnostic
output at most 32 MiB, private child stdout/stderr capture at most 4 MiB each.
The earlier terminal resource report was about 52 MiB; that is historical,
not the new preflight measurement. Measure actual selected bytes/free space
before copy and refuse beyond budget. Shared outer wall ceiling 180 seconds;
unmodified audit child at most 30 seconds, each finance/reopen stage at most
45 seconds. Stop only owned diagnostic children on timeout, never old jobs.
No service, long load, three-runtime qualification or restart is part of this
incident diagnostic.

Public exports are allowlisted component counts, golden errors, query/FK/log
results, nonsecret identities/clocks and source/copy/output hashes. Retain raw
complete clones privately and do not call them secret-free. Regardless of
component success, report the original producer audit's real paused refusal,
original six-hour/coverage NO_GO, incomplete faults/duration and unchanged
strict receipt semantics. No strict receipt is written. This is diagnostic
component evidence only and cannot reclassify the original financial-final
gate as PASS.
