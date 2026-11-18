# Serial monitor / registry contention: finite failure observation

Status: CODE_ONLY, NOT_RUN. Base is public PR49
`7665253ced0888e8204b9806b63c4163f2cafe42`. This branch implements the small
failure-observation alternative, not a native baseline/candidate experiment.
It does not identify the cause of PR47's first CI error or certify availability.
Independent investigator `8000f6fc8182f7b6ff967ac25364b63ee051731e` and its
source conditions are inputs, not substituted native evidence.

## Exact source condition and conditional synthetic schedule

PR49 still has the serial `_supervise` loop: pending spawn retries first,
then a snapshot of `_workers.items()` under its one parent RLock. For each
dead worker it joins, closes its handles, removes it and calls `_spawn` before
checking the next shard. `_spawn` starts a new gated child and synchronously
registers SPAWNED via `_record_process`. The control Database default timeout
is10s. Successful registration is required before opening that child's gate.
The existing lease observation on each visited live child uses a separate
shard Database with timeout0.1s; status errors become lease=None and skip the
expired-owner kill condition. The publisher does not acquire the parent mutex:
it is waiting for EX on the distinct router flock.

The historical cap source is `748990bce104920237867755c4571c35467e1cee`.
Its only functional change shallow-copies the control Database for kind
SPAWNED and sets timeout=min(existing,0.1). It retains the transaction/INSERT,
child registration gate and failure cleanup/backoff. It is absent from this
PR49 base and is not applied by this diagnostic branch. A SQLite busy-handler
budget is not a universal0.1s wall-clock bound: WAL setup, PROTOCOL/internal
retry, filesystem stalls, scheduling and cleanup can take other time.

A source-consistent future synthetic setup would select shard1 as the stopped
SH owner, while initial insertion order is0 then1. PR47's original selected
shard is0; this deliberately different synthetic order cannot be presented as
a replay of that CI failure. Required future observations are:

1. Start two fresh synthetic authorities under a new reviewed host; prove
   original shard0 is healthy and selected shard1's exact bound worker is
   actually stopped while retaining its own SH descriptor. The existing SH
   fixture hardcodes shard0, so it cannot be borrowed unchanged for this proof.
   Rebind any new fixture to PR49's61 runtime sources and actual worker9 shape.
2. With the parent monitor excluded only during setup, let selected1's
   unmodified lease expire. Do not renew it or lengthen the original TTL. Use
   only a newly owned coordinator/registry database write transaction as the
   jammer; no AuthDB, H1 probe or existing authority is involved. Kill only
   the explicitly bound, fresh healthy0 child so the next source-order scan
   must encounter dead0 and its replacement registration before selected1.
3. Record actual monitor entry into that SPAWNED registration, its shard/phase,
   connection/transaction wait and exact original timeout. Prove it precedes
   selected1's kill; an arbitrary connect audit event or one frame alone is
   insufficient. Every new birth must remain gated until its own registration
   succeeds, with held-pidfd ownership, protected-value denial and teardown
   enforcement consistently applied to workers, supervision and jammer.
4. Start the original4s publication. Keep jammer release tied to selected1's
   **actual bound pidfd terminal event**, or to preservation of the baseline's
   first original publication error/deadline. Use a bounded independent release
   mechanism in either case. Do not wait for publication to complete before
   releasing the coordinator write lock: it also blocks the publisher's later
   state write and would confound the candidate comparison. WAL read success
   must not be confused with state-write availability.

For a hand schedule only, call the already-expired selected1 injection time
t=0. Assume monitor enters new0 registration at0.01, while the publisher starts
at0.02 and its first-EX deadline is4.02. With the original10s busy budget and
jammer held until that first error, monitor cannot reach selected1 during the
four-second interval. The baseline's first router_busy remains a failed raw
result; releasing the jammer after recording it permits recovery without
erasing the failure. With the proposed0.1 cap, suppose native registration
fails at0.11 and existing gated-child cleanup completes at0.25; selected1 can
then be observed expired and killed at0.26. Its terminal event releases the
jammer, allowing the original EX/state-write/fanout path to proceed. Those
numbers are assumptions for a reproducible fixture specification, **not
measurements or guarantees**. Each phase and actual error must be observed;
a different first result stays preserved and may refute the setup.

If registration begins after selected1's kill/join, it cannot explain that
dead child's retained SH. An additional reader or different holder would be
required. A stack showing `_record_process` at failure does not reveal the
shard or establish this temporal relationship; this distinction remains OPEN.
Baseline and cap would each require one independent fresh case, separate
source/manifest/host CODE review and root execution GO. Neither was built or
executed here. There is no catch-and-retry, TTL change, or increased4/5s limit.

## Implemented diagnostic hook

Only the exact original stopped-owner test's publication/assertion tail is
wrapped. On its original exception, the test calls `emit_once` once before
original cleanup, ignores observation failure and uses bare raise. Successful
tests emit nothing. The original bootstrap, two shards, clocks, lease0.6,
STOP injection,4s call,5s assertion and subsequent assertions are unchanged.
The original capture's holder/stop evidence gaps are not repaired by this hook.
No new PID lookup, child, signal, gate or recovery action is introduced.

The helper projects at most the current case-parent and its cached exact
`uta-process-supervisor` Thread, each with eight frame metadata records. It
does not call is_alive, join, diagnostics or threading.enumerate, read worker
or registration caches, acquire the router mutex or a Python stream lock,
read live-frame locals/globals, format exceptions, query SQL/proc/PIDs, or
change FD flags.
Only allowlisted module/function labels and bounded line numbers leave frames;
actual paths, thread IDs, process bindings, nonces, messages and payloads do not.
The unlocked Thread identity samples are explicitly racy observations, not a
native process/owner proof. Unverified or changed monitor ownership discards
its frames. The temporary CPython all-thread frame dictionary is indexed only
for the two selected IDs, never enumerated, and released after projection.

The already-loaded, unchanged `uta.failure_diagnostics.capture_failure`
supplies its established bounded primary-chain contract; no failure-path import
is needed. That existing helper reads bounded traceback-module `__name__`
metadata from globals, never locals; this projection additionally allowlists
the resulting module labels. No arbitrary global value is exported. This test
projection retains at most two causes/eight frames each
and finite type/code/native SQLite fields, without messages. Python3.10's
missing native SQLite metadata remains null. An unavailable helper produces a
fixed collector-failed packet instead of importing or querying another source.

One ASCII packet, including prefix/newline, is capped at32KiB. Oversize becomes
a fixed quota-denied packet. CI already redirects actual child stdout/stderr
to its existing regular `unittest.txt`; the hook uses one unbuffered os.write
to that existing regular FD, avoiding Python stream locks. A blocking pipe or
TTY is declined without writing; nonblocking sinks may short-write, which is
not retried or accepted as complete evidence. Regular-file I/O and CPython's
snapshot implementation are not a hard wall-time guarantee or an OS sandbox.
No new thread or workaround watchdog is introduced. Partial/missing packets
are inconclusive; absence of a packet is not proof the diagnostic did not fail.

## Review, evidence and rollout gates

Four inert proposed tests cover finite two-thread frame projection; exact
primary-exception preservation when diagnostics fail; a busy mutex/cache that
must never be touched; and quota/blocking-sink/short-write denial. All are
NOT_RUN. They use fake frames, a never-started Thread placeholder, fake metadata
and writes, and no financial imports, PID reads, SQL or actual signal/FD write.
They do not establish native recovery or a registry-contention cause.

The new manifest binds this PR49 source, all61 financial modules and the
unchanged validation worker's nine output fields. No old H48/69-pin closure,
seven-field worker or prior native PASS is reused. Physical source closure and
any bounded local test/host remain separate prelaunch OPEN gates. No manual
native case, suite, CI run, source import/compile or artifact request was
performed. A future ordinary CI run must be independently reviewed and root
authorized on its exact new source. Its first result is preserved regardless
of whether this diagnostic prints anything.

Original CI logs can contain other tests' private bindings. Keep complete
originals private and publish only independently cleared finite projections;
this packet does not make an entire unit ZIP safe to publish. No financial
fingerprint exclusion, format relaxation, parameter change, production deploy
or real-funds enablement is included. Rollback reverts the test-only import,
exception wrapper and new helper/tests, retaining every first failure/packet.
There is no schema migration, ledger rewrite or reversal. Production, HA and
capacity acceptance remain NO_GO.
