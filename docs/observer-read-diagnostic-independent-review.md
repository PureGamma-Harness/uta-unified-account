# Independent static review of the bounded observer diagnostic

Reviewed commit: `8db6e9b1786e2e8d16438a2aa26fd93b79b9aee5`.
This review reads committed source and archived JSON only. It runs no service,
SQL, diagnostic, live sample, test suite or producer/observer command and does
not access an active run directory. The independent review is separate from
the batch/cache release review and does not change either source candidate.

**Verdict: no scoped blocker for retaining this diagnostic evidence.** It is
not continuous-observation eligibility or a fix to the active run. The
existing live coverage NO_GO remains; no financial, duration, capacity,
recovery or production approval follows.

## Read-only boundary

The delivered and actually executed scripts use `bwrap --ro-bind / / --dev
/dev`, with only a newly created external output directory writable. Live
arguments require the existing job/source and original driver PID/birth; the
original helper's `cold=False` is enforced and other database roles rejected.
The original sample is invoked once, in its original order. The wrapper calls
through the unmodified original SQLite read context rather than substituting
financial results. The copied original observer/finance module bytes match
their recorded frozen hashes.

Metadata-only sidecar `stat` cannot drop the original SQLite POSIX locks.
There is no live database raw open/close, immutable shortcut, mixed live file
copy, sidecar deletion, repair, schema mutation, writer construction, signal,
restart or retry loop. Plain SQLite `mode=ro` outside the helper is restricted
to the freshly generated disposable cold fixture. The namespace blocks that
read from creating its missing sidecars. The original observer may write a
baseline only into the fresh private diagnostic output, not the continuous
observer's output, timeline, coverage or controls.

The child enforces read-only mounts and nonregular standard descriptors;
subprocess launch closes other inherited descriptors and uses pipes. The
delivered script additionally rejects regular standard descriptors before
outer output creation. The actually executed script predates this outer check,
and the archive explicitly retains that exact executed script and its hash.
The delivered/executed difference is limited to this outer descriptor check
and sanitized outer entry-error envelope; the live evidence is not relabeled
as execution of the later script.

## Bounds and redaction

Child setup selects a 512 MiB address-space limit, eight-second CPU limit and
eight-second wall alarm. The launcher supplies a 9.5-second subprocess timeout
and `--die-with-parent`; no original producer/observer process is a timeout
target. These are configured diagnostic child bounds, not a hard filesystem
RTO proof: launcher setup, cleanup and final output persistence are outside the
subprocess timeout, and no injected timeout/cleanup failure was rerun here.
Recorded actual live and synthetic elapsed times are below ten seconds.

The archived result schema retains only role/phase, sidecar booleans, durations,
bounded allowlisted module/function/line frames, exception type, message digest
and typed native SQLite code/name. It drops financial payloads and command
IDs, stores no exception message/SQL/path/key/nonce, and hashes captured child
stderr instead of publishing it. The public live, synthetic and initial entry
failure JSON are separate, with false eligibility and production flags.

## Interpretation of actual evidence

The metadata path failure precedes any database event and is retained as an
entry failure, not a successful or failed database read. The one actual live
sample records checkpoint/router/shard/checkpoint reads and returns
`inflight_or_unknown`; it records no exception or native live error code.
Checkpoint sidecar absence/presence changes are observations of availability,
not attribution of a particular producer operation or proof of a prior cause.

The synthetic closed-WAL ordinary mode=ro read records native
`14 / SQLITE_CANTOPEN` and the same generic digest previously observed in the
continuous observer. The report correctly limits this to a compatible
mechanism. An identical generic error-message digest cannot uniquely identify
an earlier uninstrumented sample's native code, database, phase or cause. No
earlier UNKNOWN is backfilled, removed or promoted to a stable golden sample.
The isolated live diagnostic also cannot fill a continuous-coverage block.

The proposed persistent producer connection or atomic snapshot export is
explicitly future work, requiring a different frozen source and independent
WAL, shutdown, consistency and fencing validation. It is not implemented or
enabled by this diagnostic. Retaining the current active run and all its
original NO_GO evidence is consistent with this scoped verdict.

The [static source and archive checks](../evidence/20261117-observer-read-diagnostic-review/static-checks.json)
bind this review to the exact reviewed files. They parse syntax and JSON,
check archived hashes and compare unchanged observer module bytes; runtime
tests executed by this reviewer: **zero**.
