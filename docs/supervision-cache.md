# Optional NORMAL background supervision suppression

This experiment targets repeated `ExchangeWorker` supervision observed in a
previous profile (1,371 calls for 171 accepted commands). That profile came from
an older revision and is motivation only. It is not a safe performance baseline
or evidence of this feature's benefit. No throughput improvement is claimed by
the implementation or its correctness tests. Production approval remains NO-GO.

`normal_cache_size=0` is the default at the worker, managed process router and
CLI (`serve --normal-cache-size 0`). It retains the original scheduling and
supervision path, including its original transactions. Explicit opt-in accepts
an integer from 0 through 65,536. It changes no schema, margin formula, product
eligibility, admission receipt, fencing rule or financial configuration. It is
a per-process scheduler option, not a persisted financial risk parameter.

## Decision and sampling contract

An entry is a bounded digest of inputs to a **committed NORMAL supervision**.
It is never an acceptance, executable trade, liquidation completion or readiness
proof. Only a persisted NORMAL risk row is eligible for a hit. LIQUIDATING,
BLOCKED and BANKRUPT accounts always run the original supervisor. All matching
runs every selected round with its original current-market transaction gates.
All new orders, repayments, cancellation, settlement and commit checks remain
independent of these entries.

An enabled round uses one read-only SQLite snapshot to select the existing
fair cursor's bounded account batch and compare every candidate's dependencies.
Each hit is decided at that snapshot's logical time **t0**. The reported
`snapshot_started_ns` and `snapshot_completed_ns` bracket observation of t0;
they are local monotonic diagnostics, not an exchange timestamp or a distributed
sequence. The selected market version is also reported.

| Reference scheduling | Enabled scheduling |
| --- | --- |
| Each account is supervised in its own later financial transaction. | Misses use the same financial supervisor; all eligible hits are sampled at t0. |
| A change committed before that account's transaction can be observed this round. | A change committed after t0 can be observed at the next selection of that account. |
| Stale market blocks the original supervisor. | Immediately before consuming each hit, the snapshot is validated against the current clock again. If stale, the account runs the original supervisor and reports BLOCKED. |

The scheduler does **not** assert that cash remains unchanged when a previously
classified hit is later consumed. It does not compare old keys and call them a
new financial guard. A mutation after t0 invalidates the next round's comparison.
This sampling contract has an explicit difference from the reference's later
per-account sampling time; operators must accept that background detection delay
before opt-in. Financial authorization is never sampled this way.

The persisted account cursor advances for both hits and misses. For a fixed
account set of N and batch B, `ceil(N/B)+1` is a conservative maximum number of
rounds to revisit any account from any starting cursor. `normal_cache` in
`ExchangeWorker.last_report` reports account count, that bound, snapshot and
completion times, and executed/skipped counts. There is no fixed wall-clock
revisit SLO: storage contention, execution time, process pauses or growth of the
account set can delay a round. These diagnostics are local; the current managed
parent pipe publishes ready/failure reports, not these background counters.

## Proof and dependency inventory

A miss takes one financial transaction, reads the economic inputs, calls
`supervise_account(account_id, connection=connection)`, and reads the inputs
again **inside that same transaction**. A proof is eligible only if the result
and final persisted risk state are NORMAL, the previous state was absent or
NORMAL, and the economic inputs did not change. Initial NORMAL metadata may be
created, but its full final row is part of the proof. Cancelling recovered
liquidation orders or releasing spot locks changes inputs and therefore does
not publish an immediate proof. Publication occurs after the outer COMMIT
successfully returns. Any failed or unknown commit produces no new entry.

Reading an input key after COMMIT would certify an intervening debit with the
earlier healthy result. Two independent pre/post snapshots also allow an ABA
counterexample. Neither construction is used. Supplied connections use
`Database._using`, which checks an active transaction and canonical registered
database identity, rather than a bare context wrapper. The financial transaction's
authorizer, persistent SQL guards and COMMIT fence retain role/token enforcement.

Digest inputs include raw bytes/rows rather than trusting version increments:

| Dependency | Included data / reason |
| --- | --- |
| Market | Complete authoritative payload, including prices, rates, timestamps and version. The original market freshness/policy/audit validation also runs every round. |
| Policy | All persisted UTA config rows and trading schema; actual validated runtime catalog, rules, scales, fee rate, maximum price age and precision policy. |
| Ledger | Complete ledger-schema row, latest journal event, asset scales and the account's actual customer balance projection. Any normal journal append invalidates every account, including direct `Ledger.post` without an account-version bump. |
| Account | Complete account/version row, all positions and gross principal/interest rows. |
| Orders | Complete rows of every live linear order, including quantities, partial fills, fee accumulators, reduce-only and prices. Terminal history is not a supervision input. |
| Spot locks | Presence/schema, raw spot-schema/configuration rows and every complete live spot order row, including reserved asset and amount. |
| Risk state | Full liquidation row: state, cycle, revision and plan identifiers. |
| SQL definitions | Table/index/trigger definitions belonging to these authorities and optional spot objects, including optional-table presence. |

Public deposits and external journal adjustments change ledger head/balances;
borrow, interest and repayment also change gross liabilities; linear fills
change positions, orders, fees, ledger and versions; submit/cancel change live
orders/versions; spot submit/cancel/fill change live locks, versions and/or
ledger; account creation changes selection; market and kill-switch updates
change complete payload/config; supervision changes risk rows and any cancelled
orders. Credit limits and pool balances are not read by current supervision,
and terminal orders, fills and event history are not numerical inputs. Their
economic effects are represented by the above projections and journal head.

This is not a whole-journal integrity accelerator. Normal ledger verification,
managed writer guards and audit validation remain in force. Arbitrary privileged
out-of-band corruption of the journal is outside this cache's proof model and
must not be treated as an authorized update. Actual balance or liability changes
are still caught even when their version is not bumped. SHA-256 collision
resistance is assumed. Runtime configuration and loaded code are immutable for
a worker lifetime: concurrent attribute/code monkey-patching is unsupported;
deploy a new process for a new policy or release.

## Bounds, deployment and rollback

The per-worker LRU stores account identifiers and fixed-size digests only.
Capacity is bounded; eviction causes a full supervision on next visit. Cold
restart, a new worker owner and `clear_normal_cache()` start with no proofs.
`normal_cache_stats()` returns capacity, size, hits, misses, evictions and
ineligible results; `clear_normal_cache(reset_stats=True)` also resets counters.
Misses count unmatched snapshot comparisons, hits count actual omitted calls.
Stale candidate hits execute the original path and are not counted as hits.

Before deployment, compare the same safe source revision with size 0 and the
chosen enabled size, using identical open-loop workloads and separately retained
raw results. Measure dependency scans/serialization, supervisor and matching
costs, CPU, latency, liquidation detection delay and storage contention. Full
payload scans can cost more than recalculation, particularly with many live
orders, small accounts, frequent ledger appends or a cache smaller than the
working set. Preserve negative results. Do not relax dependency checks to obtain
a speedup. No long load test was run for this change.

Deploy by explicitly passing the selected runtime setting to the managed CLI
or router and checking the new worker owner. Roll back by gracefully draining
HTTP and closing workers, then restart with size 0. No migration, journal edit,
receipt rewrite or cache recovery is needed. Existing pending commands continue
through the same inbox and fencing protocols.

## Validation

Run `python -m unittest tests.test_supervision_cache tests.test_automation
tests.test_runtime_review -v`. The new suite compares reference and enabled
paths through actual 90-contract opening, two 45-contract liquidation fills,
no-liquidity waiting and restart. It verifies 93.16 final cash and compares the
complete account, order, position, liability, liquidation, event, fill and ledger
tables. Other cases cover unbumped journal adjustments, same-version market/raw
liability changes, stale hits after a slow preceding miss, transaction failure,
cross-database join rejection, bounded eviction and cold restart. Independent
concurrency/fault tests and same-source performance measurements remain separate
acceptance gates.
