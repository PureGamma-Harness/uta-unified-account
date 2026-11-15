# Experimental local router admission groups

`uta.shard_admission.RouterAdmissionBatcher` connects grouped order admission to
`ShardRouter` on one trusted host. It has no HTTP or CLI entry point. It neither
adds products nor qualifies this repository for production acceptance, 10,000/s
capacity, distributed ownership, replication, or HA. The existing synchronous
router and default HTTP paths retain their existing behavior.

```python
from decimal import Decimal
from uta.sharding import ShardRouter
from uta.shard_admission import RouterAdmissionBatcher

router = ShardRouter("/private/router", 2, {"USD": 8})
# The normal router bootstrap, funding, market fanout, and explicit activation
# must already have completed; a new router always starts halted.
with RouterAdmissionBatcher(router, worker_count=2) as admission:
    future = admission.submit_order(
        "alice", "client-order-17", "BTC-PERP", Decimal("1"), Decimal("100"))
    receipt = future.result(timeout=2)
```

Only the existing validated `submit_order` and `cancel_order` commands are
supported. There is no atomic client bulk, multi-leg instruction, cross-shard
matching, transfer, liquidation, borrowing, or settlement entry point in this
adapter. Other operations continue through their existing router interfaces.
Use the router for reads, matching, funding, market publication, and control.
Never open a shard with a standalone service or run direct database writers.

## Scheduling and bounds

The constructor starts non-daemon workers. `worker_count` defaults to
`min(shard_count, 4)` and must be an integer in `1..min(shard_count, 32)`.
`max_batch_size` is `1..256` (default 32); `max_delay_ms` is finite `0..1000`
(default 2); `queue_capacity` is `1..65536` (default 1024); `cancel_reserve` is
`0..4096` (default 16). Booleans are rejected as numeric settings.

There is one bounded pending deque. New orders are admitted to that queue only
while its total length is less than `queue_capacity`. Cancellations may use up
to `cancel_reserve` additional pending slots, preserving order within the shard.
A full queue immediately returns a failed Future with `admission_overloaded`
503. Invalid input and a closed adapter also return already failed Futures;
these commands never entered the financial transaction.

A worker selects the oldest queued command whose shard has no in-flight group.
It reserves that shard, collects up to `max_batch_size` commands for it, and
executes one commit group. Collection waits at most `max_delay_ms`; closing
skips that wait. There is at most one in-flight group per shard **in this adapter**.
Per-shard and therefore per-account enqueue order is preserved. Other shards
can proceed and finish independently; there is no global completion order.
Synchronous router callers and separate adapter instances still serialize via
SQLite, but are not included in this adapter's FIFO guarantee.

`stats()` exposes pending `queued`, assigned `inflight` (including collection),
executing `running`, `active_shards`, worker liveness, and outcome counts.
At all times:

- `queued <= queue_capacity + cancel_reserve`;
- `inflight <= worker_count * max_batch_size`;
- `queued + inflight <= max_outstanding`, where `max_outstanding` is the sum of
  those two bounds.

Completed callbacks can briefly remain included in `inflight` until their group
returns. The bounds describe adapter-owned commands, not unbounded client-held
completed Futures. Cancellation does not immediately remove a pending queue
entry: the worker removes it and increments `cancelled_pending`. Callbacks must
be nonblocking. Submitting or closing from this pool's worker callbacks is
rejected; waiting on an unfinished pool Future from any of its workers raises
`RuntimeError` to prevent dependency deadlocks.

## The financial and market boundary

The adapter never obtains a private service and starts bare batch writers.
Its only transaction entry point is the controlled router method
`_admit_order_batch(shard, commands)`, which revalidates inputs and routing.
The router retains its shared host `flock` from control validation through the
entire shard transaction and SQLite COMMIT. Market publication, funding source
assignment, and halt/activation use the exclusive lock and cannot interleave
inside that boundary, including calls from another router process on this host.

Every group validates the control authority, immutable layout, publication
flags, and global funding claim syntax. Within the actual shard transaction,
`_BoundShardDatabase` validates the immutable shard identity and initialization
seal, and the router checks every local pool funding receipt against the exact
unique global claim. A pending claim with no local receipt remains permissible.
This group checks the selected shard's receipts. Other shards' receipts are
checked when those shards execute, and across all shards during startup and
activation. It does not claim a full cross-shard audit on each group.

Each order admission also checks that the shard's market version and complete
snapshot digest match the router publication barrier. All submit commands,
including reduce-only and idempotent replay, are rejected with `router_halted`
503 while global control is halted or publishing. Valid cancellations may
continue in the same group, with control, identity, and funding integrity still
required. These router halt policies are stricter than standalone admission.

Commands execute sequentially with individual SAVEPOINTs. The existing explicit
`admission._business_rejection` allowlist isolates expected business/market
rejections; the explicit router halt rejection is also isolated. Storage,
configuration, identity, funding, market barrier, and unexpected failures abort
the group. Integrity failures also persist a global halt after releasing the
shared gate. A final fresh-market check runs before COMMIT whenever the group
created a new admission. It cannot bound a subsequent OS pause or fsync delay.

Successful results and queued business rejections become observable only after
the router transaction has committed and released its gate. A Future is a
process-local delivery mechanism, not the durable receipt. The actual receipt
is the persisted order, reservation, account version, and event. Persistence
retains SQLite WAL/FULL local semantics; no remote acknowledgment is added.

## Timeout, restart, shutdown, and rollback

`Future.result(timeout=...)` timing out does not cancel execution. Call
`future.cancel()` explicitly. `True` means the pending command will be skipped
without financial effects. `False` means execution has started or finished;
query the order through `router.orders(account_id)` or retry its original ID
and unchanged content. Never assign a new ID to a command with unknown outcome.
`admission_batch_failed` 503 means no reliable batch receipt was delivered. Its
cause is available for local diagnosis; COMMIT may already have succeeded
before a wrapper or delivery error, so this response does not prove rollback.

`close(wait=False)` atomically stops new enqueueing and requests draining.
`close(wait=True)` (the default, and context-manager exit) also joins all workers.
It is idempotent. Shutdown should first stop producers, call `close()` to drain,
then terminate the process. Constructor failure closes and joins workers already
started. No daemon workers are left to silently disappear on normal shutdown.

Pending commands are memory-only and can be lost on a process crash. Running
commands may have committed without a delivered Future. On restart create the
router with the exact same layout/policy, reconcile durable state, then start a
new adapter. Clients recover through original command IDs; never automatically
replay a reconstructed queue with new IDs. The router refuses missing, empty,
unsealed, or exchanged shards and conflicting funding claims. No restore,
automatic unhalt, or lost-state reconstruction is performed by this module.

An offline restore must preserve a mutually consistent control database, all
shards, WAL state, identities, and funding registry. Stop all writers and drain
before any authorized restore. A live replacement is unsupported; detected
identity/claim/barrier disagreement fails the group and persists the global
halt. A trusted OS owner can replace all state consistently with an older copy;
this adapter supplies no external rollback witness or distributed fencing token.
`flock` is a local cooperation barrier, not a lease, fencing epoch, cross-host
filesystem protocol, or HA leader election. The wider router recovery rules
still apply.

To roll back this feature, stop its producers, drain and close the adapter, then
use the original synchronous router APIs. The adapter adds no database schema
or financial format migration. Do not roll back or discard already committed
orders. If draining is interrupted, reconcile/query original IDs before retry.

## Reproducible validation

```sh
python -m unittest discover -s tests -p 'test_shard_admission*.py' -v
python -m unittest discover -s tests -p 'test_sharding*.py' -v
python -m unittest discover -s tests -p 'test_admission*.py' -v
```

The primary adapter tests exercise business SAVEPOINT isolation, pending versus
running cancellation, cancellation capacity, shutdown draining, per-shard
serialization and cross-shard progress, COMMIT receipt timing, a second router's
exclusive market barrier, final freshness rollback, original-ID recovery,
callback failures, and actual matcher settlement followed by reopening storage.
These are correctness tests, not sustained performance or multi-node acceptance.
The independent fault suite adds injected integrity and ambiguous commit failures.
