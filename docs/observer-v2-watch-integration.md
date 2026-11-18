# Opt-in watch/collector integration: source contract before execution

Component reference seal: `00989ce23bd0db5d03485626ea6fa9693fc4e508`.
Status: **SPEC/CODE PREPARATION, NOT_RUN; root must separately authorize the
next exact-source pure batch. No native or long-run authorization exists.**

The authorized first new pipeline pure batch is now sealed separately under
`pipeline-first-once01`: source
`a7c9d0f8daf014efdab45d35e4cd94f2d0041cb9`,12/12 PASS,0FAIL/0ERROR,
0.377s unittest time,517639602ns outer launcher time, exit0. Stdout is0B;
stderr is2241B, SHA256
`09ebeb0345ac7abf6f7929406410fda4c070ec7a965ced69b89855a6495b9a5d`.
Intent, stdout/stderr and execution/owned process identities were created
O_EXCL. Ten input files matched Git before/after. The stricter48KiB-per-file
output cap bounded the combined raw streams below100KiB; no output was near
that cap. Original source-budget allowed_runs0 is an immutable proposal record;
the separate intent records root's one-run authorization.

This pass covers SQL-free actual-method mocks and synthetic in-memory stores,
not real filesystem adapters, real process pipes/watch, SQL, native workers,
long-run recovery, capacity or production approval. No older author/independent
batch or superseded twelve-method source was run. The original paused six-hour
job and every first result remain unchanged. Any next adapter test requires a
new exact-source plan and separate GO.

Implementation CODE pins: `bbf0bf49c30e6a84f4eaaf56b655ba7d16c1156e`
(observer/controller/transport integration) and
`b4cf801e9e48602670bf13527286dc505f7f0c53` (read-only CAS reopening).
Unrun fixture source: `655afbd3b10122546caa679eaac6b7c4464a9235`.
No whole-pipeline test or adapter has been executed at these sources.

Latest pre-execution runtime source is
`1a0998c2f7fdd93fbf49dccfa9a44d7fb80d42de`, with unrun fixture source
`5283abef25aa3f4aa54497e0c95f7342d6451e0a`. Earlier proposal sources remain
unrun. Root's bounded-collection finding was addressed at8f43db4/9cd7091:
one read processes at most two FIFO frames, including bounded counted draining
after a latched protocol failure. A continuously refilling fake queue is part
of the new fixture. The original single180s shutdown deadline is checked both
before and after pumping; native blocking is not thereby proven interruptible.

Independent CODE record `b79d6dffee233164ab804f9fc4372ed6130bc027` preserves
PIPE-CODE-01 on the earlier source: using the watch-only wire option to bind
baseline identity made cold audit produce a different contract. Source1a0998c
separates common `--report-protocol compact-v2` from watch-only
`--collector-input-v2`. Watch, final and audit bind the same code SHA inventory;
audit still emits the original JSON receipt. The actual baseline comparison
and producer-audit verifier are not loosened. New SQL-free fixtures execute
the real contract/command methods with fake source bytes, compare all three
roles, and execute the real pre-baseline mismatch rejection with fake read
helpers. Independent CODE closure is pending; no actual cold audit was run.

## Effective cut point

Legacy remains selected when `plan.observer.report_format` is absent or is
`legacy`. Its original full observer publication and parent timeline reader
remain the compatibility path. `compact-v2` requires the existing explicit
aggregate output-budget policy, including the same registered2GiB value; the
new mode never changes or exempts that value.

Opt-in changes the actual watch writer, rather than converting an already
written full timeline. The observer computes the same complete financial
sample, then sends a newline-delimited `uta.managed_observer.full-input.v2`
frame on stdout and **does not call legacy Observer.publish**. Sequence starts
at1 and increases within that exact CLI process. This transient full input is
bounded by the existing64MiB LINE_CAP; it is not retained as a full stdout or
history file. Stderr remains bounded/hash-only as before.

The parent drains a bounded two-frame queue. For every full frame it runs the
same original `classify_safely` rollback and Coverage observation, applies
`financial_drain_before_log` for an already known fatal finding, and retains
the original classification evidence. Only then does it store all full-report
dependencies and publish compact timeline/latest. The source ordering must
prove no CAS/summary failure can suppress the earlier financial drain.

The queue contains at most two **raw** frames,128MiB at the64MiB line cap.
One enqueue-in-flight frame and the partial line/read block are additional
bounded raw buffers; the read block is65536B. Parsing occurs after dequeue,
one full sample at a time. JSON object expansion and the reference tree add
memory beyond the raw queue bound: neither this code nor the pure proposal
claims a measured RSS bound or changes the producer's memory limit. Actual
peak memory/address-space and backpressure remain native acceptance gates.

Decode, sequence, size, reconstruction or export failure is a distinct
transport/export UNKNOWN and resource NO_GO. It must not overwrite the
financial classification, retry its attempt, grant coverage or infer financial
corruption. It uses the existing official-drain path before error logging.
A bounded failure-only private full input may be retained when possible; it
is counted in the same budget and its loss is reported, never called complete.

## Persistence, replay and external verification

CAS nodes live under `observer/report-v2-nodes`; publication receipts/index,
compact timeline/latest and failure records stay under `control` or `observer`.
The unchanged recursive budget measurement includes all of them. No new clone
exclusion or larger outer cap is allowed. The CAS256MiB bound is additional.
Measured logical bytes are not a physical hard quota; filesystem allocation
and the original disk-headroom guard remain separate requirements.

Identical content-addressed puts must not add a second node. A completed
publication is identified by its immutable attempt and content hash. An exact
repeat can query that receipt without consuming coverage again; different
content for the same attempt is a conflict. Duplicated, skipped or reordered
wire frames are rejected before another Coverage observation. No automatic
controller or six-hour-job resume is introduced. Partial receipt/index/log
writes remain UNKNOWN and require explicit reconciliation, not blind reappend.

External v2 consumers must verify each dependency and hydrate a complete legacy
report before independently invoking their original Coverage calculator. A v2
summary cannot be passed as an empty command list or stand in for a full proof.
The independent reference expander is owned by a different workgroup and must
not import the production codec. Missing, corrupted, wrong-count or type-aliased
data fail closed. The independently reported type-alias finding on e497 remains
OPEN until a distinct new source and authorized evidence close it.

The known four alias failures have since received their distinct typed CODE
fix at `1c7b836a51dd4387013fdbf7186491e408be9f25`, a new focused8-method
PASS, and independent CODE-only OWN
`0b16d227fc46ca3f072b02c354b3431d213513ab`. Those records do not transfer a
pass to this unrun watch pipeline or filesystem path. Original e497 and its
first four RED remain unchanged.

## Final observations and shutdown

The original final-once path has64MiB stdout retention, separate from Pipes'
4MiB default. In opt-in mode final observers also avoid legacy full publication.
The parent consumes their complete wire response once and stores compact
responses in control records, while retaining the full object in memory for
the original final eligibility logic. Wire hash scope is explicit. A final
observation must not be counted both through stdout and a timeline side effect.

In streaming results `stdout_complete=false` means the full stdout bytes were
not retained. Independent fields state read-to-EOF, partial bytes, queue count,
discarded failed-protocol frames and stdout frame completeness. They do not
assert stderr or owned-process cleanup. In final-once, in-memory full means
the unchanged legacy `RESULT_FIELDS` projection, not every wire field. Its CAS
fingerprint covers only that projected report. The separate stdout digest
covers the original framed wire bytes; those bytes cannot be reconstructed
merely by restoring the projected report.

During bounded observer shutdown the parent must continue pumping its queue;
otherwise a full queue can block pipe writes and prevent the observer from
exiting. This changes no existing180s observer stop or financial/business
deadline. The legacy shutdown path remains unchanged.
Stopping also records separate stdout EOF/queue/protocol state. Incomplete
framing or queued/unproven EOF keeps collection NO_GO, even after process exit.

## Exact proposed next pure budget

One process, CPU1, external KILL watchdog10s, stdout/stderr together below100KiB;
no SQL, native subprocess, worker, observer, actual signal, real filesystem
adapter, key/crypto operation, network, CI or old-run data access. Only synthetic
in-memory pipes/queues/stores/writers and extracted immutable source are used.

Frozen fixture scope:12 new test methods (within root's14-method maximum) and fewer than64 small frame cases,
maximum512 synthetic command records in two partitions. Check legacy emission
bytes, v2 suppression of full disk publication, split/coalesced frames,
duplicate/gap/oversize/incomplete rejection, complete Coverage plus fatal-drain
ordering before writes, rollback/classification preservation, exact canonical
hydrate, count/missing/corrupt dependencies, same-scope miniature quota failure,
idempotent receipt query/conflict and final-once single consumption. Include
independent frozen legacy traces and strict JSON type comparisons; do not reuse
the production expander as the only reference. Existing first8 PASS and the
independent first alias RED must remain untouched.

The exact new source commit, test file SHA, argv and fixed fixture counts must
be delivered to root before GO. This document is a proposal, not execution
approval. Filesystem/crash/native/6h validation remains a subsequent gate even
if the proposed pure batch passes. Rollback selects legacy and reverts the
isolated integration commits while retaining every first result and private log.
