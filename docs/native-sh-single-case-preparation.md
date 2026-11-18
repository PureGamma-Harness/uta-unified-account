# Proposed first native baseline case — preparation only

Status: CODE/static plan, NOT_RUN, zero native attempts. There is no native GO
and no launchable native controller in this commit. No metadata/capability
probe, PID/proc observation, SQLite connection, signal, trace or worker was run
to prepare it. This plan must first be reviewed, then its narrow controller and
resource enforcement must be frozen before root can give an exact once GO.

The baseline code is f434389 over PR35@9b61, runtime durable-process SHA
`46905e06af8e6ee12e16b71ad6ebce50847a7d77c03c1e7fb3e73fd165897219`.
Its first selected-AST pure result is sealed at bdf291fa and independently RAW
reviewed at d68ad18b; that evidence is not native qualification. This scope uses
no PR37 .1-second registration cap. A future f209-cap case requires another
source/profile closure accepting exactly that runtime, a different fresh
authority and its own first raw record. No two-runtime allowlist or reuse of
this baseline's authority/result is proposed. Earlier ee225 native scopes and
their outcomes are neither a dependency nor a credited attempt here.

The sole eventual case is the existing
`test_durable_faults.ManagedProcessFaultTests.test_expired_sigstopped_shared_gate_owner_is_killed_so_publication_can_recover`,
run exactly once through TestCase.run so original setUp, assertion body and
addCleanup remain active. No discovery, copied financial predicate, business
retry, expected-failure wrapper or skip is allowed. Source bytes, loaded engine
and exact worker callsite checks remain active. Initializing a new authority
with the native profile is required; replacing an original authority's binary
is outside this scope.

## Exact original topology

`tests/test_durable_faults.py:1200-1237` creates a new TemporaryDirectory, two
shards and both per-shard accounts, funding/credit/bootstrap facts. It selects
the original five-second lease for this method and keeps the original polling,
background, batch, cache, price-age and business settings. A future controller
must set TMPDIR to a new private authority-tmp directory before importing the
case in its new interpreter; it must verify the resulting router is beneath
that new root. There is no supplied existing database path.

`DurableProcessRouter.start:1303-1304` spawns one worker for each of the two
layout shards. The first shard0 target uses the explicit capture instrumentation;
shard1 and replacements use the unchanged original worker. `_supervise:1348-1356`
joins, closes and removes a dead slot before replacing it. `_spawn:1108` and
registration cleanup block another spawn if prior cleanup is uncertain. Thus
at most two **live financial worker processes** are supported by the original
two-slot topology. An old exited child/retained pidfd is not another live writer.
The case must not stop shard1 or reduce the layout to meet a resource target.

The normal successful path has three cumulative financial births: initial
shard0, initial shard1, then replacement shard0. Three is not a source-enforced
maximum: failures on either shard can produce additional replacements. The
original monitor has no fixed lifetime birth counter. The proposed external
budget is 64 cumulative financial births; exhausting that budget makes the
whole scope UNKNOWN and ends it, rather than changing the writer topology or
crediting a partial PASS. The spawn implementation can also create a CPython
resource-tracker support process. It is a separate role, not hidden as a writer;
its birth and final wait/exit must be retained too. The controller and test
parent are separate declared roles.

## New-scope ownership and protected-PID boundary

The future controller must own a new session and record each newly created
leader, worker and support birth before using that identity. An explicit ledger
retains role, parent/creation receipt, PID/start-ticks/boot/UID, pinned pidfd and
confirmed terminal wait/exit state. The original `_spawn` start gate must remain
closed until its real registration succeeds. Actual Process handles and original
supervision remain in use; metadata must never manufacture READY or a receipt.
All ledger writes are bounded. Raw owner nonce/token material stays private and
out of exported reports.

Protected numbers are exactly 4471, 8784, 122905, 122907, 123007, 123009,
310035, 310039, 310266, 310269. Check that denylist before any PID/proc/pidfd/
signal operation. No liveness/health/group-membership query of those processes
is allowed. No blanket `/proc` scan or adoption of an existing authority is
allowed. Descendant discovery, if needed for short-lived support roles, must be
limited to the newly created positive-ownership subtree, with deny-before-open.
An unknown birth/role or missing terminal evidence is UNKNOWN, never absence.

The existing `tools/run_managed_variants.py::owned_run` cannot be reused unchanged:
its `_group_members` scans all /proc and `signal_own` reads each protected PID via
`_same_group`. Its known code is useful as review material, not an approved new
closure. New cleanup must use only exact newly owned pidfds; no group signal or
old-cohost scan may be used to infer safety. A new-child adoption/reap mechanism
must be explicitly scoped to this fresh subtree and frozen before native GO.

## Capture and real recovery evidence

Pre-stop capture is the new owned birth/pidfd plus active native lease, exact
ARM/ENTERED and the actual bound inode-specific kernel SH record. The trace-owned
FD is an additional test-held FD inside the real lease-owner PID, not the original
financial critical-section FD. It owns the same kernel router gate and no SQL
transaction. Only after these pre-stop facts may the one pidfd SIGSTOP target
that exact new binding. Full retained capture then still requires actual T state,
post-stop kernel SH, blocked nonblocking EX and the original zero-DML writer
probe. A marker alone proves none of those facts.

Original five-second capture/lease/recovery, >350ms headroom, actual five-billion
nanosecond acquisition event, unexpired no-early-kill control, 15s publication
thread lifecycle watchdog, snapshot/digest/receipts and all finance/schema/cache
assertions remain unchanged. A failed capture is one-shot failure, with original
undo checks and no recapture. The outer case watchdog is not a new recovery
horizon and must not be used to turn L1525 or cleanup SIGKILL into recovery PASS.

Retain the selected owner binding, both kernel-record observations, lease
timestamps/generation, signal entry/result, original pidfd-exit and EX-entry
times, real replacement birth/generation, and a real READY report for that new
PID/generation from the unchanged worker pipe or already consumed parent report.
No stale initial READY, financial receipt inference, fake dictionary or sample
until-green is accepted. A single post-case observation can be UNKNOWN; it may
not trigger another publication/capture. The original financial predicates must
pass in full. Each new child, including any failed registration/replacement and
support process, then needs confirmed terminal evidence and bounded cleanup.

## Proposed finite budget for review

| Resource | Proposed limit or handling |
| --- | --- |
| CPU | CPU1 only for controller, case parent and descendants; actual affinity recorded; no fallback CPU |
| Live roles | Original two live financial workers; at most one live tracker, one case parent and one outer controller |
| Cumulative roles | 64 financial births, two support births, one case parent; limit breach is UNKNOWN, not topology reduction |
| Case wall watchdog | 45 seconds for the single case including normal original cleanup |
| External cleanup | 1s cooperative cancellation, 2s own-pidfd KILL/exit wait, 2s actual reaps, 1s final drain; envelope max51s after native launch |
| Raw stdout+stderr | Shared256KiB, including independently held512B trailer; reserve before FD write, sticky125 on quota/short write |
| Event metadata | At most512 entries and2MiB, including all birth/terminal records; exhausted capture is UNKNOWN |
| Retained evidence | At most8MiB excluding private authority files; first streams/exit/source/bindings remain unchanged |
| Private authority | Proposed32MiB data allotment with4MiB cleanup headroom; hard enforcement primitive must be supplied/reviewed before GO, not claimed from periodic size samples |
| File descriptors | Proposed own-process soft limit256, with explicit retained-pidfd inventory and closure |

`close:1629-1643` can itself wait5s for monitor and5s plus possible KILL/5s per
worker, and the mutex/native storage wait is not a hard real-time bound. The
external watchdog therefore must own positive-identity cleanup even if original
cleanup stalls. Any watchdog use or incomplete reap is UNKNOWN. A killability
or storage-limit failure cannot be treated as green. Native SQLite protocol
backoff and OS blocking remain outside a claimed per-call busy-timeout bound.

The controller must record exact source/driver/authority/runtime identities,
actual host argv/start/end/exit/reaps, original first raw files and before/after
source/authority evidence. Expected Python/SQLite identity is an explicit future
GO input; it is not probed now or silently substituted. Only typed safe metadata
and source snapshots may enter Git; private synthetic databases and tokens remain
in the owned directory. Neither result from ee225 nor pure8/8 substitutes for
that new first record.

Rollback reverts this test/controller profile for a newly planned evaluation.
It preserves every first log and the fresh authority's queued/terminal CIDs,
ownership/lease metadata, ledger and confirmed trades; it does not reset an old
lease, replay a confirmed operation or delete evidence. No production rollout,
CI, push or original-authority transition is authorized by this draft.
