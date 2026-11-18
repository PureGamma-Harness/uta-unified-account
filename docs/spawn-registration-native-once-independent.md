# Independent read-only review: first four-case instrumented native batch

The first authorized batch records **4/4 PASS**, with a known detached-wrapper
zombie boundary. This accepts the narrow original observations below; it is not
full lifecycle/release/production acceptance, a remote CI reproduction or proof
of the original PR22 cause. No test was rerun and this reviewer made no SQL
connection, signal, process reap, private database read/copy or implementation
change. All first raw outcomes, including the residual wrapper, remain intact.

The runtime code is pinned to ff814d4bcaee079b0e0503ea8072c24e3563c443 and the
instrumented driver to SHA7c60c774c283e43dcd72c36cb357abee42d23bcab09c516de4d7d559b4afbaa8.
Author safe evidence is6b7d473c0fbf92b17c146140c88eb2c25d38dce1. This review checks
its original private-output metadata without using a new experiment to improve
or replace the first result.

## Source and original output integrity

Both pre-execution source proofs are equal. All62 runtime hashes match immutable
ff Git blobs, and a later read-only source check still matches. Tests and driver
match their committed bytes. The helper/original testcase files and storage
FULL/busy-timeout policy remain unchanged; the0.6s lease and4s publication
argument were not widened. These are code-file identities, not an independent
post-test database replay or continuously attested filesystem.

The two original sealed-manifest hashes match the author's reported originals.
Every selected non-database metadata entry matches its manifest byte count/hash,
including native stderr, trace, source proofs and ownership outcomes. The inner
manifest also describes private SQLite/SHM/WAL files; this reviewer deliberately
did not read, hash afresh or copy those payloads. Their entries are author-sealed
metadata only, not independent database reconciliation evidence.

The original inner result has literal four tests, zero failures/errors, PASS,
instrumented_diagnostic=true and original_ci_cause_proven=false. Native stderr
lists the exact three registration cases plus the instrumented kernel case,
then Ran4 tests in4.091s / OK. No framework rerun or discarded failure is hidden.
The recorded executable path is preserved. Actual interpreter version/compiler/
SQLite build stamps are not in these native result/source-proof records, so this
review does not infer that they match CI3.11.18/GCC15.2.0/SQLite3.46.1 merely from
a local executable path.

## Actual lifecycle and clock scopes

| Scope | Original observed result |
| --- | --- |
| Four-case unittest execution | 4PASS,4.091s |
| Inner owned_run leader423075 | EXITED/0, reaped,4.585325783s |
| Outer owned_run driver leader423040 | EXITED/0, reaped,5.166487814s |
| Wrapper-reported total after owned scope/reaping | 5.302555280s, under30=true |

Both owned_run scopes record pidfd use, acknowledged CPU1 affinity, complete
stdout/stderr and no watchdog reason. Their measured leader lifecycles include
the direct child's exit/reaping. Wrapper-reported total is read before its final
passive result write; it is not a separately recorded kernel exit timestamp for
that detached wrapper. No per-case clock is extrapolated into a throughput/SLA.

Original post-cleanup metadata records **wrapper423038 as Z, parent1**, with its
birth8571584, and no live group member. A new read-only /proc metadata check finds
the same wrapper zombie and no live members of the three new groups423038,
423040 and423075. No protected old PID was queried or signaled by that scan.
Both direct leaders were reaped; the observer is not parent of the detached
wrapper and cannot reap it. Therefore strict all-new-PIDs-absent is **false**.
The exited wrapper cannot run a financial command, but its retained PID is a real
harness cleanup boundary, not a claim of complete process disappearance. No signal
or rerun was attempted to hide or repair this original result.

## What the four cases demonstrate

The three one-shard cases use actual gated child processes and actual SQLite
registry state. They cover rejection before INSERT, an actual registry COMMIT
followed by injected reply loss, and a later real monitor/new-PID recovery after
that injection. The injection constructs an OperationalError; it is **not** an
experiment that induced SQLite's native locking-protocol fault. Assertions check
retained original registry evidence, real gated-child pidfd exit, no initial
writer token/generation in failure cases, and a distinct recovered owner at
generation2. The original database assertions ran inside the authorized test;
this reviewer did not independently reopen those databases.

The kernel case is an instrumented subclass using the original setup, not the
unmodified failing CI method. It pins current PID423148/birth8571879/generation1,
checks native active ownership and the exact expected router-lock inode, records
one READ flock before STOP and one retained READ flock after confirmed T state.
The trace records a monitor expiry kill for that PID, an actual expired native
lease witness before it, and active new owner423153/generation2 before return.
The source-controlled publication returns after1.126711011s with publishing=false
and halted=true, within the original4s argument and original5s elapsed criterion.
There is no explicit target pidfd-exit timestamp in this driver's trace. Completed
EX publication/new-owner observations and the later empty live group are narrower
physical witnesses; they must not be relabeled as a separately timed pidfd poll.
Tracing and the stronger holder handshake affect scheduling and cannot establish
the unique cause of the old CI failure.

The440-event trace is complete and not truncated. Its phase lease_status_return
is generated for any selected UTA function named status, including command-status
methods. Of254 such rows, only92 contain the complete owner/generation/active/
expiry/now lease shape;162 are left unclassified, not called native lease reads.
Expected EX contention and caught injected exceptions remain recorded; they are
not counted as additional unittest failures or silently erased.

## Financial READY is not established by this result

The recovery test's READY means a live current child reported ready and the
native fence belongs to its distinct PID/generation2. It does not mean market
publication, global activation, account margin or order acceptance is ready.
Fresh one-shard cases begin without a published market and globally halted.
The kernel case's successful market publication deliberately leaves halted=true.
No final router.financial_ready or public HTTP diagnostic response was sampled
in these native records. Hence financial activation is **not established**;
there is no evidence of actual financial_ready=true or a tested HTTP-ready flow.
Unchanged diagnostic logic would keep a halted state financially unready, but
that implication is distinguished from an observed API result. The pure typed
projection test remains separate model evidence. No matching, liquidation-fill,
account-risk throughput or full account reconciliation claim follows.

The small sparse review archive preserves only the original non-database raw
metadata, both original manifests, selected hashes,22 read-only checks and this
report. Narrow checks are true while strict_all_new_PIDs_absent remains false
and financial/API fields remain explicitly unsampled. The original PR22 CI gate
and overall production status remain NO_GO. Broader exact-source QA and a proper
full-lifecycle launch/reaper design retain their independent acceptance gates.
