# PR25 first-push failure: independent timing and SQLite evidence

**NO_GO; cause undetermined.** This review preserves the original push run
`44184136107`, attempt 1, Python 3.11 result of **1830 tests / 1 FAIL / 0 ERROR**.
It does not supersede that result with the passing PR run, diagnose a native
SQLite defect, or qualify the exchange for production. It contains no runtime,
test, timeout, configuration or financial-data change.

The reviewed source is `6010e920a168b35fccfc9ef9ee34e030b28b11d9`; the original
safe diagnostic is bound to evidence commit
`6c9082c9d40e5ef5569b826f0fed4cb5528742d6`. Its SHA256 is
`e159850926833bd88828e16bc338ff02903d06dda120172b0942f5d86d4ee05e`.
The original evidence seal is [ci-6010e92-first-failure.md](ci-6010e92-first-failure.md).
Six reviewed source files have independent Git-blob, SHA256 and byte-count
bindings in [timing-and-source-facts.json](../evidence/reviews/ci-6010e92-sqlite-protocol-timing/timing-and-source-facts.json).

## What failed and what the record establishes

The assertion is `tests/test_durable_faults.py:1456`: the fixture did not observe
the selected child leave router SH after undoing its own stop within the
original capture horizon. This is before the successful-capture assertions and
the publication/recovery validation that follow them. The record has one
capture attempt, one injection undo, one retained SH binding, and a writer probe
with `available=false`, native error code `15`.

The monitor snapshot is alive, stop=false, inside the status/read path ending
at `writer_fence._load:179`. One sampled stack does not establish how long it
had been there or that the thread was dead, blocked indefinitely, healthy, or
making progress. `_supervise` already catches exceptions from `status()` and
treats the result as unknown; this record does not demonstrate an uncaught
exception from that call. The publisher's `alive=null`, empty frames and empty
error list do not establish startup, health or successful publication.

This failure is a different observed path from PR22's earlier uncaught
spawn-registration exception. A shared numeric SQLite code is insufficient to
establish a common cause.

## Time bounds without mixing clock domains

`stop_sent_at` and capture `at` come from `time.monotonic()`; the diagnostic
records `time.monotonic_ns()`. Decimal differences below preserve the serialized
values; their displayed digits do not imply nanosecond measurement accuracy.

| Recorded point or same-domain difference | Seconds |
|---|---:|
| Immediately before sending SIGSTOP | 165.771680791 |
| After stopped-state check and retained-SH scan | 165.772040087 |
| Diagnostic clock, before original cleanup | 175.737757356 |
| Stop-send record to retained-SH observation | 0.000359296 |
| Retained-SH observation to diagnostic | 9.965717269 |
| Stop-send record to diagnostic | 9.966076565 |

The first difference includes the signal call, stopped-state polling and SH
inspection; it is not the exact signal-delivery latency or full stopped
duration. The source sets `capture_deadline = monotonic() + 5` before sending
SIGSTOP. Consequently, its latest possible deadline is at most
`170.771680791`, and the diagnostic clock is at least `4.966076565` seconds
beyond that upper bound. The actual start and deadline were not retained.
This proves an elapsed interval beyond the nominal capture horizon, not which
operation consumed it. There is no retained probe entry/exit, SIGCONT timestamp,
post-undo sample history, or separate assertion timestamp. Scheduling delay and
the interval before diagnostic collection are also unmeasured.

Lease `now_ns` and `expires_ns` use **CLOCK_BOOTTIME**, via
`writer_fence._clock`, rather than the capture's monotonic clock. The last
retained lease observation has `now_ns=165770244191`,
`expires_ns=170650649375`, active=true: its remaining duration at that
observation is `4,880,405,184 ns`. That retained row is not a fresh lease read
at failure. The diagnostic's separately sampled BOOTTIME and monotonic values
differ by `1,021 ns`; this single observation does not establish their earlier
offset or exclude suspend. No lease-to-stop difference or inferred expiry at
failure is used here.

The diagnostic phase is **before_original_cleanup**. Its zero cleanup-error
count and false forced-kill flag describe that snapshot, not successful final
cleanup or later `addCleanup(router.close)`. One undo was counted; its action
detail is omitted by the safe projection and the helper records no undo time. Source control
flow reaches line 1456 only after the undo helper returned true; that helper
returns true after its bound-pidfd SIGCONT call returns. This supports that an
undo call completed in the normal source path, without supplying a kernel
resume-completion timestamp or proving later progress.

## Capture logic and the remaining budget

The writer-availability helper at lines 108–143 opens its own existing-database
connection with `timeout=0`, attempts `BEGIN IMMEDIATE`, and rolls back on
success, checking zero DML changes. Under its explicit own-stop context it
classifies primary code 15 as unavailable/technical unknown, without granting
authority. The original diagnostic projects out that classification text.

The helper receives neither the outer deadline nor its remaining duration.
The outer loop checks the five-second deadline before capture and after undo;
those checks do not interrupt time spent inside connection setup, the native
transaction-start call, closing, filesystem inspection or signal handling.
In particular, `timeout=0` is not evidence of a zero wall-clock duration for
the complete helper. This is a source-level budget gap, not a measurement that
the probe itself consumed the observed 9.965717269 seconds.

After undo, progress requires both a sampled non-stopped/non-exited process
state and an SH scan returning no matching record. The scan reads individual
`/proc/<pid>/fdinfo` entries, tolerates an FD disappearing during inspection,
and is not an atomic lock-history observation. The loop sleeps 1 ms between
attempts. A release followed by reacquisition could be missed; a sampled SH
absence also does not prove a financial transaction, lease renewal or completed
business command. The failure does not distinguish an exhausted budget before
the first sample, missed short release intervals, a continuously held SH, or
other unobserved delay. No post-undo sample count/history was preserved.

## Official SQLite material and its limits

Two official pages were fetched once each on 2026-11-17, with HTTP status 200.
Full bodies and response headers remain in a separate directory with mode
0700, files 0600; they are not committed. Public retrieval time, final URL,
length, SHA256 and short exact quotations (18 and 9 words respectively) are
in [sqlite-official-documents.json](../evidence/reviews/ci-6010e92-sqlite-protocol-timing/sqlite-official-documents.json).

| Official page | Body bytes | SHA256 |
|---|---:|---|
| [Result codes: protocol](https://www.sqlite.org/rescode.html#protocol) | 73030 | `05ce13c1b04b1c7ea074f2155e979482512946634590dfe86f99af5e36e93b23` |
| [WAL: concurrency](https://www.sqlite.org/wal.html#concurrency) | 42143 | `f3467b530b883d4a00574fe1a898b3d121ed72764ae28cf66941080ac0badb9e` |

The result-code page identifies primary code 15 as a file-locking protocol
problem associated with starting transactions in WAL mode. Its documented
explanation includes a race between connections, internal backoff and repeated
losses across multiple seconds before returning the code. That makes a
multi-second native call a concrete hypothesis despite the helper's zero busy
timeout. The WAL page explains concurrent reading/writing while retaining one
writer, and separately documents some query paths that can return BUSY.
Router `flock` SH is an application gate, not proof that a separate SQLite
connection can acquire its transaction locks.

These are current public documents, not a version-pinned source inspection of
the failing SQLite **3.46.1** build. No native library hash/source binding,
locking backoff trace, child stack or relevant version-specific fix has been
verified here. The documents do not prove the fault's cause, database
corruption, a particular SQLite bug, actual intense writer contention, or a
causal link between the sampled monitor stack and the assertion. Unrelated WAL
issues appearing in the current documentation are not attributed to this run.

## Concrete next hypotheses and acceptance conditions

| Hypothesis | Evidence needed to distinguish it |
|---|---|
| The stopped-child writer probe consumes the remaining capture budget before undo/polling. | Bounded failure-only timestamps around connect, transaction start, close, undo and the existing deadline; retain native code and phase. Distinguish native-call time from scheduling. |
| SH is released/reacquired, but the absence sampler misses it. | A bounded count and first/last sample times, sampled state/SH outcomes and, if necessary, a reviewed deterministic fixture rendezvous outside SQLite while the real gate is held. SH absence alone must not become authority. |
| A status call or another operation delays supervision while the fixture is paused. | Status-call entry/exit timing and child/monitor progress evidence, without inferring duration from one stack. Do not assume the prior spawn-registration exception recurred. |

These are proposals for a separately reviewed change and a specifically scoped
verification, not executions performed or authorized by this evidence commit.
Preserve the original five-second capture/recovery/API limits, 15-second
publication lifecycle bound, exact child identity, native writer-availability
condition, zero-DML probe, no unknown-state financial grant, first-failure
artifact and distinct PR22 evidence. A future execution must identify its
source and result separately; retrying until green cannot erase this failure.

## Review, deployment and rollback

Only documentation and derived safe evidence are added. Verification consists
of reading the retained diagnostic, decimal arithmetic, six Git source/blob
bindings, and validating the two retrieved body digests and quote counts.
No SQL, project import, tests, fault-process creation, signals, CI retry or
production action occurred. The runtime remains the original source; its
`uta/` closure is 61 Python files plus `dashboard.html`, not native C.

Deploy by retaining this report with the first-failure seal; there is no data
migration, API change or service rollout. Roll back the report by reverting
this evidence-only commit. Preserve private originals and their hashes even if
the report is reverted. Independent review and the unresolved CI failure keep
the delivery gate **NO_GO**.
