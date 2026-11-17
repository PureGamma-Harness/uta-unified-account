# Durable financial batch implementation plan

Status: implementation in progress; no performance or production approval.
Base: `dd2ffbba31f94f1ccedd55f48d6db5fb29a67db9` in an isolated worktree.
This plan implements the previously reviewed [design](durable-financial-batches-design.md)
under the integration lead's explicit authorization. It does not change the
qualified release or its ongoing tests.

## Scope and compatibility

The first runtime is opt-in on a **fresh synthetic managed layout**, via an
explicit offline `durable_batches=True` capability. The default remains false
and the worker batch size remains zero. Existing authorities are not silently
upgraded; requesting batches without the recorded capability fails before
starting workers. An existing-layout promotion needs its own reviewed offline
migration and is not part of this first slice.

Every shard is fully preflighted under the existing global exclusive gate
before the first irreversible fence/capability change. Preparation is recorded
in the global control authority; incomplete preparation remains halted. Batch
schema consists of exact, append-only manifest and disposition records in the
same database as the financial command inbox. It is never fabricated at restart.
A new compiled-in `writer_fence_batch_capability` control marker is part of the
recognized persistent fence inventory. Old binaries see an unknown fence table
and refuse ownership/writes; a Python-only feature switch is insufficient.
The marker and global capability have immutable identity and bounded format.

The new private batch-metadata role permits only INSERT on the official manifest
and disposition tables. It cannot perform financial writes, terminal inbox
updates, arbitrary DDL or lease updates. It registers the original native writer
UDF and requires the actual current PID, token, generation, nonce, boot, lease,
SQL guards and transaction-end fence. Producer inbox permissions stay unchanged.
All source hashes and decision artifacts change and require fresh qualification.
No v1/v2 financial field or product policy is changed.

## Execution and recovery

1. Select hints outside the financial write transaction. Due control heads take
   the original single-command path. Below three eligible financial members,
   use that path without writing a manifest. Batch size is 3..8, no more than two
   commands per account; each productive batch reserves an oldest normal head
   opportunity, so cancel/repay priority cannot starve normal accounts.
2. Persist one immutable, content-hashed attempt manifest with shard/layout,
   owner identity and every original CID, sequence, owner, kind and stored
   canonical payload digest. It is not a financial acceptance receipt.
3. Hold one router shared gate and use one real financial write transaction.
   Reload all membership and original commands. Execute only currently due FIFO
   account heads and current supported kinds; each command uses the original
   canonical validation, savepoint, guard, full risk and joined financial methods.
   Never copy a batch-start risk allowance across commands.
4. Every original CID's terminal outcome, financial effects, reservation,
   required audit/event and the batch COMMITTED disposition share that COMMIT.
   Check terminal UPDATE rowcount. Return only after COMMIT. A bounded soft work
   budget seals the completed prefix; it is not a hard pause/IO latency bound.
   Control commands never join financial batches.
5. On any exception or restart, query **all** original CIDs from the durable
   manifest and verify immutable membership. Missing/read-failed/contradictory
   results stay UNKNOWN and stop dispatch; never treat them as PENDING.
   Resolved terminal commands are reused. Confirmed PENDING commands may be
   rescheduled under a new normal transaction after recording recovery evidence.
6. An unknown COMMIT or unattributed database/lease error never consumes all
   member command retry budgets. A candidate culprit is isolated through the
   original single-command path; only its own reproducible failure may be
   recorded/quarantined. Background processing and real matching remain unchanged.

## Validation and stop gates

Tests will cover original default behavior; actual transaction count and shared
COMMIT; same-account insufficient-margin and reduce-only accumulation; same and
conflicting order IDs; mixed business rejection/savepoint rollback; repayment
original-ID effects; control priority; backoff FIFO; soft prefix sealing;
pre-COMMIT rollback; lost post-COMMIT reply; query-all read failure; immutable
membership; crash/new generation; old-binary refusal; metadata role denial of
financial/terminal/DDL writes; lease expiry; exact schema guards; and cold reopen
ledger/order/position/event reconciliation. Independent permissions and failure
reviews are required before integration or benchmark GO.

No benchmark gate is changed. No 6/24-hour, 10,000/s, replicated durability or
real-funds claim follows from this implementation. For n commands the initial
normal-path dispatch commits are one manifest metadata plus one financial
commit, versus n financial commits; enqueue durability commits remain n.

## Deployment and rollback

Use a new private synthetic directory and frozen artifact. Preflight and seal
halted, verify all shards and the recorded capability, publish a fresh complete
market snapshot, then explicitly activate. Existing unknown results must be
resolved by original CID before any later operation. On failure, halt and drain;
retain all manifests, original CID watermarks, financial effects and capability
markers. Rollback disables batch scheduling only in a binary that recognizes
and recovers the capability. It does not drop the marker, delete attempts,
recreate the authority, or downgrade to an older unsupported writer.

## First executable integration checkpoint

The runtime now has a fresh-layout `durable_batches=True` capability and
`financial_batch_size=0` (default) or 3..8. CLI `init --durable-batches` is
irreversible; `serve --financial-batch-size 3` selects dispatch only after that
recorded capability exists. A normal layout creates neither batch tables nor
the marker. A capable layout with size zero still recovers old attempts before
worker READY. Existing-layout promotion remains unsupported.

Full batch history is checked read-only while the original owned startup keeper
is live. Metadata recovery runs only after owned startup finishes and exits its
registry; an actual renewal of the same still-live original-TTL token precedes
READY. No metadata role is added to startup write scheduling or upgraded to a
financial role. The background matching/supervision path remains unchanged.

Every selected batch gives the oldest due normal head one opportunity before
prioritizing cancellation/repayment heads. This is deliberately stronger normal
scheduling than the design's one aged opportunity per four productive batches;
it changes cross-account execution order. It does not provide a hard wall-clock
fairness bound. The 5ms soft budget can execute only one of three selected
commands; the remaining commands stay PENDING and may use single dispatch.
Selected membership, executed prefix and actual financial completion are
separate counts. A 3-member manifest is not proof of three effects or fewer
commits than single dispatch.

`COMMAND_BATCH_EXECUTION_FAILED` is a global internal null-account event after
query-all recovery, bound to manifest hash, original membership, phase and
actual recording generation/PID. It uses the existing bounded exception
metadata capture without messages, SQL, paths, locals or raw owner nonce.
Repeated recording in the same generation/phase is idempotent. This is an extra
financial diagnostic commit on a fault path, not part of the two normal dispatch
commits. Lease/database failure can prevent recording; the event count is a
lower bound. Existing account-scoped managed feeds do not expose global events.
A future benchmark/observer must reject these events as internal technical
failures even when all individual CID attempts stay zero. Existing tools do not
yet select batch layouts, and no performance qualification is performed here.

A batch executing_id identifies where failure was observed, not its cause.
After full recovery, single-command isolation is required; in this first slice
only the original stored noncanonical/invalid-payload failures are eligible for
individual poison-attempt accounting. Database/lease/clock/integrity and unknown
runtime failures stop the worker rather than charge batch neighbors.

Actual Python 3.12 checkpoint evidence includes 21 tiny cases in 8.532s, real
spawned partial dispatch and kill-after-manifest recovery, and independent
processes importing exact archived `4608ffe` and `ad3f5b8` source. The former
refuses the new fence inventory and the latter cannot use the native guarded
financial authority. Original test harness failures are retained. This is not
final release qualification. The independently reported extra attached-trigger
schema-inventory gap is still a blocker at this checkpoint and must be fixed
and reviewed before any integration or load GO.

## Exact format and diagnostic-gate follow-up

The next patch closes the independently reported inventory gap by comparing
all SQLite objects in the batch namespace **or attached to either batch table**.
The six legitimate managed native guard triggers are required with their exact
shared `writer_fence._guard_sql` definitions, alongside exact batch SQL and
implicit indexes. Fresh pre-fence schema has no native triggers; managed schema
requires both registered IUD policies. No trigger demonstration is executed by
this follow-up. Normal format tests cover fresh/managed official schema and an
extra index or reserved view being rejected, then restored to the legal format.
Independent review of the final patch remains required.

Reopen benchmark diagnostics now count batch preparations, selected members,
COMMITTED executed prefixes, zero/partial prefixes, RECOVERED/unresolved
attempts and internal batch failure events separately. Counts are explicitly
records, **not observed COMMIT counts or financial throughput**. Any internal
failure, unresolved attempt, recovered unknown attempt, missing diagnostics or
noninteger diagnostic counter blocks technical qualification, even with all
individual CID attempts equal to zero. The existing benchmark still does not
select batch capability, so no batch performance run is implied. Its tiny
existing .1/.2-second real-spawn unit cases verify this reporting contract only.

Final focused checkpoint `ebf8459` executes **105/105 cases on each** of Python
3.10.22/SQLite 3.53.1, Python 3.12.14/SQLite 3.53.1 and Python 3.13.5/SQLite
3.46.1. The actual interval is 2026-11-17 08:21–08:23 UTC; every runtime source
manifest is unchanged, with no ResourceWarning or ignored-exception output.
It includes real batch ownership/restart, both archived binaries, original
single-command/fence/startup behavior, diagnostic stop gates and original native
TLS CLI checks. [Commands, source manifests and actual raw outputs](../evidence/20261117-durable-batches-runtime/targeted-ebf8459/manifest.json)
are retained. This is a focused matrix, not a complete release run, packaging,
capacity test, independent approval or permission to enable real funds.

Additional financial cases use manual amounts and real SQLite effects: under
halted/stale pricing, cancel and USD repay succeed while new risk is rejected;
USD cash is exactly 20.08 + 2 - .5 = 21.58 and principal debt is 1.5, retained
separately. Replaying the original batch does not repay again. A real paired
opening trade creates a 1.5 position; two staged reduce-only orders of -1 cause
the second to reject rather than reserve a reversal. Conflicting order IDs
produce one effect. A deliberately slow first command produces a real 1/3
executed prefix, with the remaining two original CIDs still pending.

The first credit-case fixture had four incorrect assumptions, all retained as
failed raw evidence: missing asset-wide credit limit, expected halt rejection
before the actual stale-market check, wrong liability table name, and treating
the debt's decimal string as minor units. Corrected exact assertions check the
existing documented schema/validation order; runtime was unchanged. This does
not reclassify those earlier runs as passing.

At exact `8ce91d6`, the four new financial cases plus the updated parent external
BUSY fixture pass **5/5 on each** of the same three runtimes, with unchanged
sources and no ResourceWarning/ignored exceptions. Their actual raw outputs and
commands are retained under `targeted-8ce91d6`. The following test-only integration
adaptation moves loan seeding to an explicit pre-seal bootstrap callback, keeping
the original pool/borrow CIDs and all cash, gross debt and six-entry assertions.
This supports credit A2's managed new-borrow rejection; it does not enable managed
borrowing or alter production runtime.
