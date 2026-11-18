# Instrumented SH capture candidate — CODE only

Status: NOT_RUN. No test, trace capability probe, worker, PID/proc inspection,
SQLite connection, signal, native flock, CI operation or original authority was
executed. No native budget remains implied by an older attempt. The next pure
batch and any later native evaluation require distinct concrete root GO.

Source base is PR35 `9b61e5f35dd2196ef2fdddfa03559eca3f1322ec`. Its `uta/`
runtime is unchanged from 6010 and has durable-process SHA256
`46905e06af8e6ee12e16b71ad6ebce50847a7d77c03c1e7fb3e73fd165897219`.
It does **not** include PR37's SPAWNED registration budget source f209. No
`uta/` file, financial algorithm, schema, public API, lease duration or business
timeout is changed by this candidate.

## Distinct observed phases

| Original location | What the assertion establishes | What remains unproved |
| --- | --- | --- |
| L1456 | After an unsuccessful capture, own SIGSTOP was undone, but the parent did not observe matching live birth without SH before capture deadline | Whether SH never left, was missed/reacquired, or native probe/scheduling consumed the window; recovery publication has not started |
| L1461 | All bounded read/stop capture attempts failed their kernel/writer preconditions | Five-second expired-owner recovery, new owner, publication and finance have not been exercised |
| L1525 | Native capture/lease controls passed and original publication started; original pidfd did not report exit within the original five-second recovery horizon | Why kill/exit was delayed; subsequent generation/EX/ACK/finance assertions have not passed |

PR39 push310 is L1461 and merge313 L1456. PR40 exact-head push310 is L1461.
PR37's prior 310/311/312 setup failures remain distinct from its runtime change.
PR41 exact-head push311 is a real L1525 recovery FAIL, while merge311 remains
L1456. These first outcomes are not combined into one cause or treated as
expected-green results.

The already retained PR41 safe push log includes a diagnostic with captured
active lease/generation, expiry 328598484296 ns, publication start
328.353302652, original API call 328.356510568, and finish 333.356772587. Publisher
error is `router_busy`; monitor is alive in `_connect:147 -> _record_process:419
-> _spawn:1127 -> _supervise:1356`. This is a concrete registration/WAL-setup
snapshot, consistent with the independently modeled synchronous-monitor risk.
It lacks monitor shard/PID, operation start/end and native return evidence;
the unique actual cause and effectiveness of the PR37 cap remain UNKNOWN.
The merge log independently records one retained-SH capture, one undo and
unavailable writer probe code15, before publication. It cannot diagnose the push.

No evidence was redownloaded. Read-only input hashes are retained in the source
closure JSON; original logs and first failed archives remain in their independent
safe evidence trees. Protected process identities were never inspected.

## Deterministic development profile

`tests/native_sh_capture_fixture.py` is a test-only helper; import has no native
side effect and its constructor defaults OFF. The exact named test explicitly
opts in only after its existing TemporaryDirectory-based router initialization,
before any child exists. It requires the original five-second lease, no durable
batch capability and the single-command role. It is absent from the customer
API and the installed `uta` package; there is no production environment switch
or persistent failpoint in the financial runtime.

A context proxy changes only the first shard-zero spawn **target** to a top-level
test helper. It delegates real Pipe/Process creation and returns the real Process
handle to original supervision. Sibling and replacement targets remain the
original `_run_worker`. No UTA function, class, `__code__`, signature, fingerprint,
manifest, verifier or loaded-engine check is replaced or suppressed.

Inside that one fresh child, the helper checks exact installed runtime bytes and
compares the loaded `_run_worker` CodeType with compilation of those exact
bytes. It resolves the unique original `view.process_one` callsite and traces
only that exact worker code object and line. The pinned source puts that line
after `_OwnedStartup.__exit__` and keeper drain. Another trace owner, role or
code/source mismatch fails setup. Existing full code-bound and loaded-engine
checks still run unchanged; a refusal is a failure, never bypassed.

The parent sends one ARM containing only PID/birth/UID/boot/generation and the
original capture deadline. At the reviewed boundary the child verifies that
binding and that only its main thread remains, acquires actual SH on the same
router inode through the original lock implementation, sends ENTERED, and waits
on a private bounded pipe while holding SH. It owns no SQLite connection at this
point and performs no renewal, command, schema or financial operation.

That SH descriptor is **additional test instrumentation held inside the real
lease owner PID**, not a claim that it is the financial critical section's native
descriptor. The test proves the intended recovery property only if a real
stopped lease owner holding the actual kernel gate is reclaimed by original
supervision and the unchanged publication/finance tail passes. It does not
measure the uninstrumented engine or any performance property. Profile and
runtime source digests are emitted as explicit instrumentation metadata, never
as READY, an active lease or a success receipt.

The original parent still independently checks birth, pinned pidfd, stopped
state, inode-specific kernel READ flock, EX exclusion, the unchanged native
zero-DML writer probe, real acquisition TTL, no early kill, actual expiry,
original five-second PID exit/new generation/EX deadlines, real READY/control
and exact publication/financial/schema/cache assertions. All original assertion
expressions and the complete original recovery/cleanup body remain in source.
The existing frozen module AST guard removes only exact enumerated scheduling
additions and still compares against its unchanged original reference.

On a failed native capture predicate, the parent sends one RELEASE before the
original undo SIGCONT. The child releases SH, acknowledges RELEASED, then parks
outside SH and never executes original financial SQL again. Original undo/birth/
lease checks remain; the new explicit refusal ends the test before a recapture.
Cleanup sends ABORT and closes its own two pipe endpoints. Success does not send
RELEASE: the original supervisor must kill the stopped exact owner and release
its kernel gate. No lease/capture/recovery interval is extended, no sample is
skipped and no business command or test is retried.

## Proposed first pure batch, not yet authorized or run

- Exact entry: `tests/test_native_sh_capture_protocol_pure.py`, eight methods.
- Proposed CPU: 1, exclusively coordinated by root; maximum wall budget 10 s.
- Finite scope: below 64 small traces, below the 128 limit. It enumerates all
  24 protocol permutations, four changed-binding/rearm controls, actual callback
  with fake gate/wire/clock, role/keeper mismatches, exact source/code/callsite,
  malformed bounded messages, initial/sibling/replacement target selection,
  one-shot cleanup, and the actual existing full-original-AST guard.
- No native test discovery and no actual `sys.settrace`. The standalone entry
  rejects SQLite connect, worker start, process wait/signal/pidfd, thread start,
  flock, sleep and trace installation. Code objects are constructed/compared,
  not invoked as workers. Fake SH and virtual deadlines are explicit assumptions.
- Run once only after CODE review and root GO, freezing source/driver hashes
  first. Preserve first stdout/stderr/exit even on failure; no rerun or skip.
  This batch cannot prove native code-object equivalence across another runtime,
  actual pipe scheduling, kernel SH, SQLite availability, READY or recovery.

## New-authority rollout and rollback boundary

| Stage | Required scope | Rollback/rejection behavior |
| --- | --- | --- |
| Current CODE | New sparse checkout at the stated PR35 base | Revert only these test/profile changes; preserve every first raw result |
| Future pure GO | Exact source closure; fake objects only | A first failure stays failed; no native escalation or implicit retry |
| Future native GO | Separately approved fresh private synthetic directory, exact source/profile/runtime/interpreter/SQLite, owned-child cleanup and bounded output | Preserve original failure and source/authority identity; no old authority or protected PID is a target |
| PR37 cap comparison | Another separately frozen source/profile accepting f209 runtime and a different fresh authority/first record | Do not reuse this source's authority or attribute before/after results to old CI; cap is a conditional improvement until measured |
| Production | No rollout authorized by this fixture | Never directly switch an original authority's binary or erase/rewrite CIDs, ownership/lease metadata, terminal receipts, ledger history or confirmed trades |

The old natural-sampling code and first failures remain retained in the fixed
base and evidence history. This instrumented scheduling profile narrows the
fault precondition to a lease-owner-held kernel SH gate; it does not cover a
stopped SQLite writer/schema holder. Native SQLite internal WAL/protocol retries
and OS blocking remain outside hard busy-timeout guarantees. A deterministic
capture alone cannot close the independently observed L1525 recovery failure.
