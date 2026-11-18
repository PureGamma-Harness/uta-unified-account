# Stopped shared-gate owner recovery: static design

Status: source analysis and a first sealed pure-model baseline. No worker, SQLite
connection, native fault injection, signal, original authority, or protected PID
was used for this analysis. This document does not establish the cause of the
PR 35 failure and does not establish production readiness.

## Fixed source and failure

- Runtime base: `6010e920a168b35fccfc9ef9ee34e030b28b11d9`.
- PR 35 source: `f6ef89b213ac76813ad31687aa4ff825d9d72585`; runtime is unchanged.
- Failed PR run: `44220725630`, Python 3.11, actual checkout
  `e71b6e1ac6dc0b0c7fa60bfbfb49822d12328eea`.
- Existing independently collected evidence: `e75fb301017af16be7c6f296e6c25b795fa89885`,
  `evidence/pr35-first-ci/failed-pr311-unit/unittest.txt:483` and
  `unique-failure-tail.txt`. No new network retrieval was performed.
- Original test failure: `tests/test_durable_faults.py:1525`, an empty result
  from polling the original bound pidfd within the unchanged five-second
  recovery horizon. The run reports 2049 tests, one failure, zero errors.

The existing diagnostic was emitted before original cleanup. It records the
selected PID 2917, retained kernel SH evidence, an available zero-DML writer
probe, generation 1, original expiry 273940462697 ns, publication start
273.698945467 monotonic seconds, publication API entry 273.702336757, and no
publication error at diagnostic time. At the failure snapshot, the monitor is
alive in `_supervise:1356 -> _spawn:1127 -> _record_process:419 ->
Database._connect:147`, while the publisher is alive in the first exclusive
`flock` attempt at `sharding.py:263`. The snapshot carries no monitor local
shard/PID and no native return value for that blocked call. It cannot prove
whether the selected original owner received a kill, which other owner exited,
what held any SQLite lock, or whether that call occupied the full recovery
interval. Later child output and cleanup are not recovery success evidence.

This is distinct from the earlier capture/undo failure at line 1456; no common
cause is asserted.

## Actual source path

1. Original fixture (`test_durable_faults.py:1365-1479`) binds PID/birth/UID,
   opens its pidfd, captures that child's own `router.lock` SH descriptor,
   confirms state T and retained inode-specific kernel SH, proves EX blocked,
   proves a zero-DML SQLite writer probe available, and checks its real lease.
   The fixture may undo only its own failed capture before taking one fresh
   lease observation. The original capture budget and actual five-second
   acquisition event remain requirements.
2. The stopped real worker cannot reach its next renewal
   (`durable_process.py:528-534`) or exit/finally release. Expiry fences financial
   commits (`writer_fence.py:282-295`) but does not release its SH flock.
3. The same parent uses `_supervise` (`1312-1358`), not new-coordinator
   `_recover_registered_orphans` (`1211-1271`). Each monitor turn reads each
   live child's lease through a dedicated observer with timeout .1. A failed
   read becomes unknown and authorizes no kill. An observed expired lease with
   matching owner PID authorizes killing only its own unreaped Process handle,
   then a bounded join. The second `is_alive` test confirms exit before cleanup
   and new spawn. No lease-row revocation write precedes this kill.
4. `_spawn` starts a child behind an FD start gate, records SPAWNED birth and
   nonce, then opens the gate (`1107-1150`). A registration error leaves the
   append outcome UNKNOWN, closes/reaps that exact gated child, and allows only
   a new child after identified transient failure and confirmed cleanup.
   Failed cleanup or an unclassified error forbids a new child. The prior
   uncertain INSERT and nonce are never retried.
5. New child acquires a real PID-bound higher-generation lease, completes owned
   initialization and fenced validation, records OWNED, and sends READY
   (`462-525`). Financial commands remain under their actual router SH gate and
   fenced transaction (`sharding.py:841-848`).
6. The original publication first obtains EX after old SH release, durably sets
   the publication barrier and enqueues exact market commands, releases EX,
   awaits command receipts, then obtains EX to reconcile all durable payload
   digests before final publication state (`1525-1570`). A READY report alone
   is not market publication, and a new lease alone is not financial readiness.
7. Original assertions require old pidfd exit, new active higher generation,
   and first EX entry within the same original five seconds. Separately, they
   require the one original publication's receipts, exact payload/digest,
   absence of duplicate financial effects, unchanged schemas and caches. The
   fifteen-second thread lifecycle watchdog does not enlarge recovery time.

The test-only `_orphan_worker` (`test_durable_process.py:32-50`) instead creates
its own SH scope before `SIGSTOP`. That fixture provides deterministic scheduling
but is not evidence about this original stopped real `process_one` boundary.

## Independent static defect and minimal candidate

The only monitor calls `_spawn` synchronously both before its lease-scan loop
and from within that loop. `_record_process` uses `control.control.transaction`.
The control database comes from `ShardRouter` with the `Database` default
ten-second timeout (`sharding.py:149`, `storage.py:65`). Connection setup sets
that native busy timeout before its `PRAGMA journal_mode=WAL`
(`storage.py:145-147`); BEGIN IMMEDIATE, INSERT and COMMIT also occur on that
connection. An admissible blocking registry operation can therefore keep the
only supervisor away from another child's expiry scan longer than the required
five-second recovery horizon. This is a source-level progress defect even
without attributing the observed CI failure to it.

Proposed smallest runtime change: for `kind == "SPAWNED"` only,
`_record_process` uses a shallow copy of the existing control database with
`timeout=min(original.timeout, .1)`. All SQL, registry identity, append handling,
gate ordering, original database settings, financial database settings and
lease duration remain unchanged. Existing registration cleanup and bounded
new-child backoff handle a native timeout. Other registry event kinds retain
their existing behavior. A per-native-operation busy budget is not a hard wall
clock bound for disk I/O, process startup, OS scheduling, or arbitrary shard
counts; it specifically removes the ten-second SQLite busy wait from this
registration boundary.

In particular, SQLITE_LOCKED and SQLITE_PROTOCOL need not obey the ordinary
SQLITE_BUSY handler budget. SQLite internal WAL protocol retries/backoff and
kernel blocking are not bounded by this parameter. A fake conflict that advances
exactly `timeout` is a conditional model, even when that fake exception carries
a LOCKED or PROTOCOL code; it is not a native latency claim for those errors.

## Pure-model specification

Use the actual `_supervise`, `_spawn`, `_record_process`, registration failure
classification and cleanup methods. Construct the router with `__new__` and
replace all process, pipe, mutex, stop-event, database, lease-observation and
clock dependencies with finite in-memory objects. No router constructor,
authority setup or native connection is used.

The fake control database's transaction records its timeout. An injected
registry conflict advances a virtual clock by that timeout and raises a typed
SQLite exception without connecting to SQLite. The fake Process models only
its own start gate, alive/exit facts, joins, kill receipt and close behavior.
Its identifiers are synthetic integers and never used with any OS API. A fake
lease source returns active until the selected expiry event and matching-PID
inactive thereafter, or an explicitly unknown observation. A fake stop source
advances a finite number of monitor turns; it never sleeps or starts a thread.

Finite scenarios should cover:

- Held-SH owner before/after a dead sibling in insertion order, and retry-queue
  registration before the next lease scan.
- Registry contention beginning while the selected owner is active, and after
  expiry, with native BUSY, LOCKED or PROTOCOL classification.
- Modeled registration append followed by a lost reply, plus known nonappend
  failure. Both remain UNKNOWN; no retry of that append/nonce is allowed.
- Cleanup confirmed versus model child refusing to exit; the latter blocks
  replacement and retains handles. Terminal errors do not become retryable.
- Live matching lease, expired matching lease, mismatched owner, and failed
  observation. Only expired matching ownership permits the model kill.
- Original shared database timeout is unchanged; a smaller original timeout is
  never increased; non-SPAWNED event timeouts are unchanged.

Required red witness: on the unchanged base a sibling registry busy interval
using timeout 10 leaves the held-SH owner alive beyond the five-second virtual
recovery deadline. Required candidate witness: the same schedule times out the
bounded SPAWNED registry call, cleans up that gated model child, then observes
the actual expiry before killing the selected model child within that original
deadline. No assertion may rely on native pidfd behavior, real SH release,
actual COMMIT, READY, market receipts, or financial recovery: those facts are
outside this model and remain future native validation requirements.

Before running, hard-fail guards should cover `sqlite3.connect`, all
`BaseProcess.start`, `os.kill`, `signal.pidfd_send_signal`, `Thread.start`, and
real sleep. The script must be explicit model-only, finite and single-process;
it must not import or discover native test cases. Its output must mark
`native_executed=false`, `original_ci_cause_proven=false`, and
`production_approved=false`.

### Sealed first baseline

The one authorized baseline execution used CPU 1 and 16 finite scenarios, took
0.046 seconds in the shell tool, and produced the explicit result
`RED_CONDITIONAL_LIVENESS_WITNESS`. Fourteen scenarios with known expired matching
ownership missed the unchanged five-second virtual deadline; the selected kill
occurred at 10.05, 10.1 or 20.1 virtual seconds. Unknown and mismatched ownership
caused no kill. The 20.1 witness includes a second registration retry before the
next lease scan, as the actual supervisor does. No result was rerun or replaced.

The driver SHA256 is
`58134735a8a25d84fbb566316ff4b163fa3e9f4013d56c4d1d55738a8d3df3b3`;
the pinned base `durable_process.py` SHA256 is
`46905e06af8e6ee12e16b71ad6ebce50847a7d77c03c1e7fb3e73fd165897219`.
First stdout, empty stderr, exit status and hashes are retained in
`evidence/shared-gate-recovery/baseline-first/`. Exit status 0 means that the
harness found and preserved its required baseline RED witness and passed its
model assertions. It does not mean that base recovery passed. Its output also
records the actual extracted function AST digests and all finite event traces.

Only this baseline has been executed at this point. Candidate execution requires
a separately authorized pure budget after independent source review.

## Evidence still needed to distinguish native causes

| Hypothesis | Distinguishing evidence absent from original diagnostic |
| --- | --- |
| Monitor delayed by registry operation | Bounded phase entry/return times with shard and gated child PID, native error code, selected owner's expiry and last scan time |
| Kill not attempted despite readable expired lease | Exact same-child lease observation, kill-call entry/return or error, supervisor phase and monotonic time |
| Kill attempted but task has not exited | Pinned pidfd poll at deadline and bound birth/state, signal syscall result, retained SH evidence |
| Child exited but reap or observation delayed | Original pidfd events distinct from multiprocessing sentinel/exitcode/join events; timestamps before cleanup |
| SQLite blocked observation | Exact operation/authority role and native classification; unknown reads remain no authority |
| Unrelated sibling failure | Shard and PID associated with each READY/failed/exit/replacement/registration phase |
| Scheduling delayed the original poll | Before/after poll timestamps and registered fd identity; no inferred success from cleanup |
| New writer or market recovery failed later | Higher-generation lease plus READY identity, original EX entry, exact command receipts, persisted payload digest and reconciliation |

Any future diagnostic must retain the original real kernel SH capture and
original five-second capture/lease/recovery bounds. It must not pause a SQLite
writer, substitute the fault with a test-owned gate, weaken assertions, blind
retry a failed test, or skip an uncooperative sample. Failure remains failure.
