# Independent cache and routed admission fault acceptance

These tests use synthetic balances, prices and funding references. The
verification group owns the tests; it does not import the production reserve
formula, cache arithmetic or admission implementation to calculate expected
financial outcomes. The implementation groups own implementation fixes.

## Scope and reproducibility

Candidate base: `92086bd`; implementation dependencies in this checkout:

- `ec56058`: opt-in, per-service pure reserve cache.
- `4a0e9f569ac805b5c64b17a9c0a8e538c5a54393`: market payload decoder cache.
- `a4aae6c`: service integration with independent freshness/policy checks.
- `f03ef130a4586c40a32ca33b1128a3c3172118da`: bounded router admission groups.
- `b82828f5c52bb2f70ed70df9c2d2e3e41eb5e2d6`: classify missing/invalid
  published shard market as a publication-integrity failure.

The kernel fixture explicitly enables `reserve_cache_size=32` and
`market_cache_size=4`. The router fixture exercises the public
`RouterAdmissionBatcher` path, including the router-controlled transaction,
identity, control and funding-claim checks. Private method patches inject
failures or pauses; they do not submit financial commands around the router.

Run from the repository root:

```sh
python -m unittest discover -s tests -p test_kernel_faults.py -v
python -m unittest discover -s tests -p test_shard_admission_faults.py -v
```

Final independent execution on 2026-11-15 UTC, Python 3.12.14:

```text
test_kernel_faults.py:          Ran 14 tests in 1.252s — OK
test_shard_admission_faults.py: Ran 11 tests in 1.633s — OK
```

These durations are correctness-test runtimes, not performance measurements.
Both runs execute actual SQLite transactions on local temporary files. No case
is skipped, replaced with a dummy implementation, or marked as an expected
failure.

## Financial oracles and kernel fault matrix

The manual examples use USD 8 decimal places, a 0.04% trading fee and a 10%
linear initial margin. One unit ordered at both mark and limit 100 reserves
`10 + 0.04 = 10.04`; two independent live orders reserve `20.08`. Changing mark
to 200 and IM to 20% changes that unit's reserve to `40 + 0.04 = 40.04`.
Balances, orders, event counts and the ledger are checked separately. Admission
does not create a cash journal entry. The ledger verifier also runs after
reconciliation.

| Test suffix in `test_kernel_faults.py` | Fault / independent acceptance |
| --- | --- |
| `enabled_caches_cannot_publish_success_or_business_rejection_before_real_commit` | Pause before actual COMMIT with populated caches. Neither the valid receipt nor the queued business rejection is published early, and a separate reader observes no staged order. |
| `real_sqlite_full_rolls_back_cached_admissions_and_original_ids_can_recover` | Cap actual SQLite pages and allocate a blob after the second admission. Require a genuine `SQLITE_FULL` in the exception chain, complete group rollback, and successful original-ID recovery after removing the cap. |
| `savepoint_rollback_cannot_leave_a_ghost_order_or_cached_account_reserve` | Inject a declared business rejection after DML; only that savepoint disappears, later valid work commits, margin is exactly 20.08 and only two acceptance events remain. |
| `whole_batch_rollback_and_worker_restart_do_not_preserve_mutated_state` | Inject a storage failure after the second command changes state; the whole group rolls back, the worker is replaced and original IDs reserve only once. |
| `real_commit_constraint_failure_does_not_turn_warm_cache_into_committed_reserve` | Create an actual deferred foreign-key violation; SQLite COMMIT fails, neither Future succeeds and no order/reserve/event survives. Warm pure cache entries may remain without authority. |
| `post_commit_unknown_is_reconciled_by_original_ids_after_cold_restart` | Raise after real COMMIT; both Futures report technical unknown, both durable orders remain, and retry after a cold service restart changes no version, event or cash record. |
| `two_cached_instances_cannot_spend_the_same_accounts_last_margin` | Two separate service/batcher instances contend for one account holding exactly 10.04. Exactly one order commits and the other receives insufficient margin. |
| `same_account_and_market_version_in_distinct_databases_have_no_cache_alias` | Reuse account ID, order ID and market version across databases with different marks/IM; reserves remain independently 10.04 and 40.04. |
| `same_version_changed_valid_payload_is_decoded_before_each_decision` | Deliberately replace stored bytes without changing version. Repricing changes the existing reservation to 20.04, so a second order cannot use the old cached margin. |
| `same_version_corrupt_payload_cannot_hit_prior_valid_decode_or_poison_repair` | Replace valid stored bytes by invalid numeric text at the same version. New admission fails; replacing the original bytes repairs the path and no negative cache masks it. |
| `cached_decode_never_caches_freshness_and_stale_cancel_remains_available` | Advance the clock beyond five seconds after warm reads. New admission is rejected, cancellation commits and replay of the original terminal ID remains available. |
| `warm_decoding_still_rechecks_freshness_at_group_commit` | Expire the snapshot after admission but before the group checkpoint; both admission and cancellation roll back to the original state. |
| `partial_fill_fee_rounding_and_reprice_are_not_reused_from_old_order` | USD cents: reserve .11 initially; after a .01 fill pays the first cent, remaining .99 units reserve .099 with no duplicate fee ceiling; mark 2 gives .198; a further .49 fill leaves .1. A duplicate fill changes nothing. |
| `process_exit_with_warm_caches_reopens_only_durable_orders_and_retries_once` | A subprocess warms both caches and executes `os._exit` before or after the actual group COMMIT. Reopening sees only durable orders, and original-ID retry ends with exactly three orders, margin 30.12 and one seed cash journal. |

Raw market replacement is deliberate fault injection, not an authorized
publication workflow. The local decoder cache does not establish publisher
authenticity, detect every semantically valid tampering attempt, or replace the
service's monotonic publication contract.

## Router fault matrix

| Test suffix in `test_shard_admission_faults.py` | Fault / independent acceptance |
| --- | --- |
| `shared_router_gate_covers_actual_commit_and_exclusive_halt_waits` | Pause immediately before actual COMMIT. A competing exclusive halt cannot cross the shared gate, the Future stays unresolved and a separate SQLite reader sees no staged order. After release the receipt commits, halt completes, new risk is refused and cancellation remains available. |
| `pending_group_rechecks_halt_when_it_enters_gate_and_still_cancels` | Pause a selected group outside the gate, halt, then release it. The earlier-enqueued order is refused under the current authority while an existing order cancellation commits. |
| `runtime_identity_swap_cannot_use_prequeued_routing_to_write_wrong_shard` | Replace a shard with another valid shard database at runtime. The public batch fails with the original identity-conflict cause, global halt is durable and no new order is written. |
| `detected_same_version_wrong_payload_persists_global_halt_for_other_shards` | Put a decodable wrong-price payload in a shard using the published version. Digest mismatch rejects the group and persists global halt; another shard cannot add new risk after detection. |
| `missing_published_shard_market_is_integrity_failure_and_persists_halt` | Remove a previously published shard market. The batch fails as a publication-integrity fault, persists halt and blocks other-shard new risk. |
| `invalid_published_shard_payload_is_integrity_failure_and_persists_halt` | Replace a published shard payload by invalid schema. The batch fails as a publication-integrity fault, persists halt and writes no order. |
| `ordinary_stale_publication_refuses_new_risk_without_halt_and_cancels` | Clock expiry alone rejects new admission and allows cancellation in the same group, without incorrectly persisting publication-integrity halt. |
| `restored_control_missing_funding_claim_halts_before_routed_batch_dml` | Restore a pre-funding control backup while retaining the newer local funding receipt. The next batch on that shard detects the absent exact global claim, halts before DML and startup also rejects the inconsistent restore. |
| `post_commit_response_loss_and_cold_router_original_id_retry_are_exactly_once` | Lose the group response after actual COMMIT, reopen the complete router and replay original IDs. Orders, account version, events, cash journal and reservation remain unchanged. |
| `queue_cancel_reserved_capacity_and_shutdown_preserve_every_running_promise` | Hold a running command, cancel a pending Future, exhaust normal/reserved cancellation slots and close intake. Running cancellation is refused, overflow/closed requests fail explicitly, close drains accepted work and no canceled pending order becomes durable. |
| `duplicate_ids_inside_one_group_reserve_once_and_conflict_has_no_effect` | Same ID/same content returns one receipt and consumes one reservation. Same ID/different content is a business conflict with no extra event, version or cash journal. |

The funding check validates the full global claim registry format and exact
receipts on the batch's own shard. It does not acquire other shards' write locks
while holding its own. A missing claim for another shard is detected by that
shard's next batch or the full startup/activation/funding reconciliation; the
tests do not claim full all-shard reconciliation on every batch.

Static review raised the need to persist halt for a detected market barrier
mismatch. The implementation owner included it in `f03ef130`; the independent
cross-shard halt assertion above verifies that final candidate behavior.
The same review distinguished an invalid/missing payload from ordinary clock
expiry. The implementation owner fixed the former in `b82828f`; three additional
independent tests verify missing data, invalid schema and the stale boundary.

## Failure handling, deployment and rollback

Caches remain explicitly opt-in; their default capacities are zero. Roll out
cache capacities to a bounded synthetic/canary cohort, compare authoritative
receipts and risk decomposition, then restart with capacity zero to roll back
the optimization. Cache removal needs no financial data migration or reservation
release because cache entries are not authority. Reconcile durable state before
restoring intake after a technical failure.

Router admission is an experimental single-host in-process queue. Deploy behind
the router's authority boundary and keep customer HTTP traffic on its existing
documented route unless a separately reviewed integration enables the adapter.
For rollback, stop new submissions, call `close(wait=True)`, resolve every running
or unknown result by its original account/order ID, reconcile receipts/events
and resume the synchronous public router path. Do not restart unresolved work
using fresh IDs or restore only the control database. A detected claim, identity
or publication-barrier inconsistency requires durable halt and operator repair
from a coherent restore set before explicit activation.

The covered storage model is a single atomic SQLite writer per database on a
local filesystem with WAL and `synchronous=FULL`. Subprocess termination checks
process-crash recovery; post-COMMIT exceptions model response loss. The tests do
not establish replication, HA ownership/fencing, hardware power-loss guarantees,
cross-shard atomic execution, persistent queuing, unbounded scheduling fairness,
or production throughput/RPO/RTO acceptance. Direct private service writers and
uncooperative external execution are outside the router protocol assumptions.
