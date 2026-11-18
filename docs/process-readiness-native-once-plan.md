# Readiness native once: revised CODE/SPEC only

**Not executed. No preflight or native GO has been granted by this record.**
This proposal is based on `4179debef89bbc71f533be7756b12683969051e5`.
The initial native CODE freeze `0fbf6797` was not run as a native module or
case. Independent selected-AST fake evaluations retained **guard1PASS/5RED
with actual affinity[4]** and **terminal1PASS/7RED with actual affinity[3]**.
Each used one allowed CPU. Both complete first records,
fixtures and unchanged expectations are retained in the independent review
directories. This revision addresses those findings; it has no new execution
result until a separately frozen focused fixture receives root's once budget.
It preserves the frozen `cb35a277` first pure result: seven methods passed
once, actual affinity `[0]`, Python3.12.14. The raw files and source pins are
unchanged. Affinity `[0]` means one allowed CPU with ID0; it is not a CPU1
measurement, a `taskset -c1` result, or a performance comparison.

The two original PR34 CI failures remain separate and unresolved. Original
failed PR job134512043520 ran Python3.12.16 / SQLite3.46.1. This local candidate
is a new diagnostic, not a reproduction or proof of either original cause.
Actual local binary and SQLite values are deliberately pending the new scoped
preflight; the prior pure run imported no SQLite.

## Exact case and retained assertions

Exactly one invocation selects:

`test_process_readiness.ProcessReadinessTests.test_malformed_missing_and_oversize_persistent_quotes_fail_closed`

The original test method remains unchanged. Its normal `setUp()` and
`development_fault_profile()` construct fresh synthetic authority directories;
only the development authority starts real workers. At most two new financial
workers may be alive concurrently. The case uses the original valid offline
fault owner and all three original payloads/checks, in order:

| Payload | Required original diagnostic | Original subtest metadata |
| --- | --- | --- |
| `{broken` | `market_invalid` | missing=False |
| singleton deleted | `market_missing` | missing=True |
| 1,048,577 spaces | `market_invalid` | missing=False |

All three negative controls must be reached and pass for a candidate PASS.
An initial activation failure is a failure before those controls, not evidence
they passed. No other method, full suite, warmup run or retry is selected.
The same-version recovery method is expressly excluded and needs another scope.

Real UTC and native writer clocks remain untouched. Market TTL2s, lease1s,
publish8s and activation8s are unchanged; the wrapper verifies those settings
on publication/activation. The existing one-second readiness sampler remains
unchanged. Default quote creation still follows the reviewed single native
owner witness; its first unknown fails immediately and its report is retained.
Explicit snapshots retain their exact SID/version, timestamp and bytes. The
runner does not create a substitute quote, relabel a SID, renew a lease,
republish until success, or change a financial predicate.

## Source and binary boundary

`native-source-manifest.json` pins every `uta/*.py`, the four test/helper inputs
(`test_process_readiness`, `test_readiness_sampling`, `test_durable_faults`,
`readiness_before_quote`), and the four native harness modules. Importing
`test_readiness_sampling` also imports `test_durable_faults`; its other test
methods and embedded subprocess scripts are definitions, not selected work.
No legacy fixture archive or external package data is used by this case.

The preflight copies only these declared sources plus the manifest into a new
private snapshot, verifies them, and makes the snapshot files0400/directories0500.
Actual execution uses that snapshot. `-I -B -X pycache_prefix=NEW_EMPTY_DIRECTORY`
keeps application imports on these declared sources without writing or using
an existing application bytecode cache. The child records its loaded UTA
module origins and verifies them against the manifest. Source hashes are
checked before and after, in both child and controller.

A Git blob's existence is not evidence that a sparse worktree file exists.
Before either the revised20-method fake batch or any actual preflight, prepare
only the explicit declared inputs and necessary runner/plan paths from the
approved Git source, after checking that restoration would overwrite no WIP.
Seal a separate materialization record for every input: regular nonsymlink
file, exact length/SHA256/stat, Git mode/blob identity and Git-blob byte hash.
Verify the old7 and both independent first raw sets byte-for-byte before and
after. Runtime source verification also checks regular materialization and the
declared byte lengths before reading. A missing input is a preparation block,
not a native-case FAIL, an executed test, or evidence of unchanged source.

The metadata preflight records the resolved Python executable and SHA256,
`sys.version`, `_sqlite3` extension path and SHA256, SQLite version constant,
and loaded `libsqlite3` library hashes from its own maps. It opens no database
and issues no SQL. Actual execution requires an exact match to the reviewed
preflight, not merely the same Python major/minor. This is a declared source
and relevant binary boundary, not a hash of every standard-library/runtime file.

The revised preflight also hashes ten relevant multiprocessing stdlib sources.
The [static spawn audit](../evidence/reviews/process-readiness-engineering/stdlib-spawn-static.json)
read these files without importing or probing them. `SpawnProcess` invokes
`popen_spawn_posix`, which calls `resource_tracker.getfd()` even though this
UTA path uses Pipes instead of multiprocessing Events/SemLocks. The tracker
starts through `util.spawnv_passfds`, outside `BaseProcess.start`. Forkserver
and Manager paths are not selected by this explicit spawn context.
Those ten hashes are metadata/supply-chain records, not capability validation.

## Two review gates before any native action

First, root or an independent group reviews these four unexecuted modules,
this plan, manifest, and the existing seven-method first raw result. No new
Python compilation, import, fixture, preflight or native case has run here.

After that review, root may authorize exactly one metadata/file-preparation
preflight, separately from native execution. The proposed scope is CPU1 /10s,
new absolute directory below `/workspace`, source copy at most8MiB, no child,
UTA import, router, worker, database connection, SQL, signal or network action:

```sh
python -I -B evidence/reviews/process-readiness-engineering/native_once.py preflight --run-root /workspace/readiness-native-once-FROZEN_SOURCE-first --source-commit FROZEN_NATIVE_SOURCE
```

The exact frozen40-hex commit replaces both source placeholders after this
CODE freeze. The new directory must not exist. Capture that command's first
stdout/stderr/exit; any failed preflight is retained and not retried under this
scope. It pins itself to one CPU from its own allowed affinity and records
the actual number, which the earlier pure run observed as0.

The preflight requires free disk at least128MiB, physical/cgroup memory
headroom at least384MiB where the cgroup limit is exposed, and cgroup PID
headroom at least12 where exposed. It records own resource limits and reads
only resource metadata, its own birth/affinity/maps, and declared source files.
It exercises `pidfd_open` on itself without sending a signal. Its10s Python-line
guard exits only that metadata interpreter on expiry. Partial preparation is
retained; no directory is silently reused.

Root must then inspect the actual preflight bytes/SHA256, source/binary/SQLite
pins, resource headroom and proposed new directory. Only a distinct explicit
**final native GO** authorizes this once command from the source snapshot:

```sh
APPROVED_PYTHON -I -B /workspace/readiness-native-once-FROZEN_SOURCE-first/source/evidence/reviews/process-readiness-engineering/native_once.py run --run-root /workspace/readiness-native-once-FROZEN_SOURCE-first --source-commit FROZEN_NATIVE_SOURCE --approved-preflight-sha256 REVIEWED_PREFLIGHT_SHA256
```

The final command must also retain its outer stdout/stderr and actual process
exit status in the same private scope. Binary path, source commit and preflight
hash become concrete at that review. A `preflight.json`, CLI flag, passing pure
fixture, metadata self-report or this plan does not itself supply native GO.

## Process ownership and time/resource stops

The controller starts with no children, becomes a subreaper for its own future
subtree, and creates one new case session. Before the case may import UTA or
initialize business data, the controller binds and fsync-records its new PID,
start ticks, boot ID, UID, session and pidfd, then releases an inherited pipe
gate. An unreleased/closed gate exits without financial setup.

Only direct children of this controller, or descendants reached through
already-bound owned parents/threads, are inspected. There is no global `/proc`
process enumeration. All threads' own `children` files are included because
the real monitor may spawn a replacement. Reparented owned descendants are
reaped by the controller. PID-number reuse requires a new owned birth and
makes this result UNKNOWN.

Protected PIDs **4471, 8784, 122905, 122907, 123007, 123009** are never inspected
or signaled, together with **310035, 310039, 310266, 310269**: the same union
of ten is used by every native harness PID/proc/pidfd guard and manifest.
No process-group or unbound PID signal is used. Every signal is
sent through a held pidfd after confirming the same birth/session/UID, with
append+fsync records before and after. A failed identity check denies that
action. The original runtime's `BaseProcess.kill/terminate` are wrapped solely
to deliver their own requested signals through this guard; admission, leases,
READY, market data and execution methods remain unchanged.

The original registered-orphan path also uses direct process identity, pidfd
open and signal primitives. Case-only forwarding guards limit those accesses
to this case or already-bound births, skip terminal historical births without
reading a possibly reused PID, and route registered pidfd signals through the
same held-birth/deadline guard. They do not replace orphan recovery, SQL,
lease or financial predicates. Every denial is sticky and recorded as UNKNOWN.

The allowed normal roles are one controller, one case session leader, up to
two financial workers, and one `multiprocessing.resource_tracker`: at most
five live processes in this scope. The helper has its own bound birth and
archive; it never consumes or evades a financial-worker slot. An additional,
unrecorded, mismatched or surviving helper makes the result UNKNOWN. After
the original test's own cleanup, the case uses the pinned stdlib's normal
tracker stop path and records its actual guarded `waitpid(pid,0)` receipt.
Normal helper cleanup requires status0, terminal proof and reaping; `_pid=None`
alone is insufficient. Worker cleanup also checks held terminal pidfds and
absence from this case's own kernel child lists. The outer controller compares
all observed descendants against these closed role records. A forced outer
cleanup of a descendant surviving the case cannot be called PASS.

Interpreter exit is also part of the boundary. The case CLI flushes its first
raw streams and exits only itself with `os._exit(status)` after the explicit
test/helper cleanup above. All PASS/FAIL/UNKNOWN paths avoid re-entering
`multiprocessing.util._exit_function`, daemon cleanup or tracker `__del__`
after the journal/pidfds close and method hooks restore. This does not replace
normal reaping: PASS still requires the recorded complete cleanup beforehand;
UNKNOWN residuals remain owned by the outer subreaper and its same absolute
deadline. The selected UTA worker target and tracker create no child processes.
The controller does not import multiprocessing, and its pinned/current
`Popen.__del__` source polls/registers children rather than signaling them.

The controller passes its absolute native-action30s and signal40s deadlines
to the case; neither child nor emergency cleanup starts a new relative budget.
The signal guard checks again immediately before the actual pidfd signal,
including after the before-record's fsync. Observing expiry forbids the action.
Popen and case-gate release also check the original native-action deadline
immediately before proceeding, including after prior hash/journal work.
Signal attempts are reserved before uncertain I/O so an exception cannot
silently cause a duplicate attempt.

Worker name/live-slot checks occur before the original `Process.start`, under
one reservation lock, and are checked again after binding. An illegal name,
occupied slot, third live worker or expired native deadline cannot start a
new worker. Every denial is sticky in the case result, including denials
caught by a background thread; it cannot be turned into a later PASS.

| Controller elapsed | Policy |
| --- | --- |
| under30s | Run the one exact case, while checking resources and preserving first raw |
| stop/unknown or30s | TERM each still-live bound owned process once |
|35s | KILL each still-live bound owned process once |
|40s | End new signals; reserve final drain/reap/result work |
|42s | End final drain wait; unproved cleanup/EOF becomes UNKNOWN |
|45s | Outer budget including finalizers; expiry or exit/completion mismatch is UNKNOWN |

Each authority temporary directory is contained below the new private
`business/` directory via `tempfile.tempdir`; the original fixture owns its
normal cleanup. Business data has a monitored64MiB stop threshold. This is
not a filesystem hard quota: samples can observe an overshoot, which stops
the case as UNKNOWN. Logs have hard per-writer caps: native journal4MiB,
combined child stdout/stderr2MiB, controller journal512KiB, safe export512KiB,
and bounded JSON results/metadata, staying below the8MiB log budget. A cap
retains the first raw prefix and records UNKNOWN; it never claims a complete
successful raw capture after truncation.
Writers conservatively reserve bytes before their first write and latch
failure after partial write or failed fsync. Written bytes are never removed
from cap accounting by an exception, and a failed writer cannot append a
trailer or recovery record through the same writer.

The wall policies are checked in the controller loop and after its finalizers.
They cannot bound an uninterruptible kernel/fsync call or arbitrary scheduling
pause. A late/missing completion, unproved reaping, surviving bound process,
partial journal or outer exit mismatch cannot be PASS. Residual owned births
are retained for a separately reviewed cleanup scope; there is no fallback
signal to a protected/unbound PID and no new native attempt. These limits must
be accepted explicitly at final scope review rather than called hard kernel
quotas or hard real-time guarantees.

## First raw, safe export, and result protocol

Private0600 files retain controller stdout/stderr, the original child
stdout/stderr, ordered controller actions, every original diagnostics call
before/after (including the complete original returned object), original quote
creation identities/times, publication/activation receipts, fault byte lengths
and hashes, original subtest outcomes, source/binary metadata and actual exits.
Each raw journal append and stdout/stderr chunk is fsynced. The diagnostics
wrapper returns the exact original object and never rewrites a result. Missing
after-records or partial lines are UNKNOWN. Instrumentation's fsync can itself
delay an observation; a local failure is not proof of the original CI cause.

Journal closure requires continuous sequence numbers, a unique first
`case_begin` and unique final `case_end`, unique complete diagnostic calls
numbered from zero, one case/session identity, and exact source/binary and
independent case-result/count/hash association. Fault and subtest indices
bind the three original controls to this exact selected test. Deleting an
entire diagnostic pair or retaining only a paired prefix cannot close the
trace. Structural completeness and control completion are separate fields:
an honestly closed assertion FAIL before the fault loop may report0/3 controls;
a separate case-result claiming PASS without all three controls is UNKNOWN.

Only `safe/diagnostics.json` is eligible for public review/export: ordered
diagnostics with explicit phase, allowlisted native booleans/integers,
shard/PID/generation, safe codes, canonical quote timestamps, SHA256 digests,
watermarks and bounded report/error metadata. It excludes authority paths,
nonces, arbitrary exception text, database contents and raw payloads. It
includes the first unknown and all later recorded observations in order.
The raw directory, preflight paths and business databases are not published.

- **PASS** requires actual outer exit0 matching completion, the exact one
  test with all three original controls reached/passed, no source/binary
  mismatch, no technical/budget/cleanup uncertainty, complete raw pairs/EOF,
  and all owned descendants exited/reaped.
- **FAIL** records the exact original case's observed assertion failure;
  failures before the corrupt loop are identified as such. Its first raw
  report is retained and never replaced by a rerun.
- **UNKNOWN** (exit75, or budget exit124) covers a technical error, first
  before-quote unknown, output/data/time limit, incomplete first raw/result,
  source/binary mismatch, unproved identity/reaping, or completion/exit
  disagreement. Preserve the attempt and stop. No blind re-observation,
  native retry, quote refresh or silent acceptance follows.

Even a new PASS is only this candidate's local diagnostic result. The original
two CI FAIL, second case's missing diagnostic/cause, full integrated CI and
production/capacity acceptance remain open.
