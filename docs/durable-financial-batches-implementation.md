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
