# Independent batch recovery and financial contract review

The implementation under review is fixed at `6730f444106bb816ef0d97596030ed3de1b45559`.
This review uses a separate worktree and changes no `uta` runtime file. Its
independent test definition is `b008da287464d64deb9736f64b0a9a3d1b676c6b`.
The scope is small synthetic single-database recovery, not throughput,
replication, arbitrary fault interleavings or production approval.

No blocking defect was observed in the reviewed recovery paths. The new cases
use real SQLite transactions and real writer generations. Exceptions described
as lost replies occur only after the original transaction has really committed.
The unavailable-last-read wrapper exercises fail-closed recovery; it does not
fabricate financial outcomes. No live authority, old soak process or schema
demonstration was accessed.

| Independent case | Required observed fact |
| --- | --- |
| Actual deferred foreign-key failure at financial COMMIT | Every staged order, terminal receipt, batch outcome and invalid child row rolls back; original commands remain PENDING with no added attempts |
| Lost preparation reply, then last original CID unreadable | The durable original attempt remains discoverable; no disposition or new attempt is created until all members can be read |
| Lost financial reply, then last terminal unreadable | Earlier successful terminals cannot shortcut query-all; subsequent recovery and same-CID replay retain exactly one order/event per account |
| Control command arrives after preparation | A zero-execution COMMITTED disposition reports three PENDING members; it creates no financial acceptance; control still precedes those original IDs |
| Real 10ms first-command work exceeds the unchanged 5ms soft budget | Only one command is recorded as executed; two remain PENDING and continue once under a genuinely newer writer generation |
| One terminal and two PENDING members at owner replacement | Recovery records all original members with their distinct states, without reexecuting the prior terminal |
| Account head is in backoff after preparation | Its successor stays PENDING; another account can progress, and no neighbor receives the head's technical attempt charge |

The numerical oracle is independent of the production risk core. Each order is
one unit at USD100 with 10% IM and 0.04% fee, so its required reserve is exactly
1004 cents. Each of the three owners starts with 2008 cents; the complete owner
map is `customer:{alice,bob,carol}=2008` and `system:custody=-6024`. Admissions
cannot change that map or the three original journal events. SQL orders/events,
original CID state, exact owner balances and foreign keys are checked together.
The legacy ledger verifier is used only as an additional check in the backoff
case; it is not the source of these expected values.

Static control-flow review also confirms that a capability-aware worker with
batch size zero still verifies batch history, exits the owned startup scope,
recovers unresolved attempts, really renews the same still-live token and only
then sends READY. Low occupancy creates no new manifest. These ordering facts
are consistent with the implementation group's process cases; this independent
review does not claim an additional process-kill or large-history run.

## Actual results

The clean test commit `b008da2` ran seven cases on each of:

| Runtime | SQLite | Actual process duration | Result |
| --- | --- | ---: | --- |
| Python 3.12.14 | 3.53.1 | 1.344s | 7/7 OK |
| Python 3.10.22 | 3.53.1 | 1.293s | 7/7 OK |
| Python 3.13.5 | 3.46.1 | 1.281s | 7/7 OK |

Every run was pinned to one allowed CPU and used `-W error::ResourceWarning`.
All runtime and test source hashes were unchanged and Git was clean before
and after. No skips or ResourceWarning output appeared. The original three
pre-seal-loan repayment fixtures also passed against this integrated source
on Python 3.12, 3/3 in 0.334s. Their amounts, original IDs, interest-first
repayment and rollback assertions remain active.

An exploratory precommit run passed 7/7 before the closed-owner assertion was
strengthened to exact map equality. Its original log and test hash remain
separately labelled; it is not presented as the clean-commit matrix.
[Original logs, commands, hashes and source manifests](../evidence/runs/batch-recovery-independent/matrix.json)
and the [copied-file inventory](../evidence/runs/batch-recovery-independent/copies.json)
are retained without editing their recorded commits.

## Limits and rollout decision

Batch manifests, selected membership, executed prefixes and account successes
are different counts. These cases establish neither fewer actual COMMITs in a
one-command prefix nor a latency or throughput bound. The 5ms work budget is
soft. Current process-kill coverage is the implementation group's evidence,
not an independent multi-node RPO/RTO claim.

The joined borrow helper requires the caller to roll back a failed action or
its real SAVEPOINT; it does not provide its own savepoint. New borrowing in
managed state remains code-level 501, with historical original-ID replay and
repayment preserved. No SQL operation-specific old-binary borrowing gate or
cross-shard global borrowing budget was added by this review.

The result permits continuing synthetic integration checks only. A full frozen
matrix, actual package checks, separate process/fault review and measured
capacity are still required. `production_approved=false`.
