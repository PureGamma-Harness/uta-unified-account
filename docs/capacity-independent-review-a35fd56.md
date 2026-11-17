# Independent managed admission measurement review

Reviewed source: `a35fd56fc98126b3e5cced8a459bd04ca580e537`.
This review reads code, the immutable preregistration and existing JSON/gzip
artifacts only. It opens no SQLite database, starts no service or worker, and
runs no load/profile. It supplies no production or capacity authorization.

**Verdict: no counting discrepancy found in the 136 existing micro-arrivals.
The intended short diagnostic comparison needs an execution amendment before
GO.** Its technical stop result and its latency stop result must both pass.
The unchanged preregistration still has `execution_authorized=false` and no
frozen execution commit. Full source, CI, package and quiet-window approvals
remain the integration owner's separate prerequisites.

## Independent raw checks

The [pure checker](../evidence/runs/capacity-independent-review/recompute.py)
imports no production financial, SQLite or profiling module. Its only executed
source function is the explicitly isolated, frozen **pure technical gate** AST
for the counterexample below; no financial calculation is reused. The data
checks independently derive counts, schedule timestamps, rates and percentiles.
[Complete derived results](../evidence/runs/capacity-independent-review/recomputed.json)
bind eight inspected source inputs and every original arrival/summary digest.

All 148 outer-manifest files and the 17 original per-run manifests match their
recorded bytes/hashes. The original archive contains 17 authorities with eight
orders each: **136 unique arrivals in their respective authority namespaces**,
including the initial, final three-runtime and direct CLI functional examples.
The dirty-parent identity of those development runs is retained. Their exact
generator and UTA bytes match the reviewed frozen source; the whole old Git
checkout is not relabelled as a clean a35 run.

For every raw row the checker verifies the original schedule from sequence and
rate; offered, enqueue-start, ACK and terminal-observation ordering; exact
nanosecond latency; the deadline flag; unique CID/order; original SUCCEEDED
receipt and OPEN/unfilled result; and the independent `251/25000 = .01004 USD`
reserve. These assertions check preserved receipt data, **not a new independent
reopen or reexecution of financial storage**. The earlier producer's RO ledger,
audit, version and capability findings are retained as reported evidence.

The recomputed arrival and outcome counts, admission/ACK numerators, elapsed
observation-plus-drain denominator, actual router/child settings, capability
observations, zero retry/fill facts and batch record classifications agree.
For all/financial/ACK groups the exact nearest-rank percentiles lie below the
reported histogram upper bounds and within the documented 0.1% bin plus integer
rounding. The independent output includes each group's N, exact maximum and
exact rank; the current summary itself supplies only the four percentile
fields. A future comparison must publish N/max from its new raw rows too.

The five [pure tests](../tests/test_capacity_review_data_reference.py) check the
archive and reject an understated tail, inflated financial rate, ACKs added as
financial outcomes and invented zero latency for an empty group. They passed
in 0.071 seconds with ResourceWarning treated as error. They are not a new
repository full-suite result or new performance evidence.

## Contracts that preserve the intended comparison

The plan holds `durable_batches=True` for A, B3, B8, C8 and C100. A is batch 0,
cache 0; each other arm changes only one numeric setting. AB/BA/AB ordering,
fresh authority, cold cache, 200 scheduled arrivals at 20/s for ten seconds,
100 accounts, two shards and identical synthetic price/product rules are
explicit. Capability-false default behavior remains a compatibility check,
not the financial batching gain baseline.

The actual child-entry observation checks received settings before invoking
the unchanged native worker. Router settings, spawned PID metadata and reopened
capability reports agree in the original microcases. This proves configuration
wiring, not that any cache hit occurred. Native managed IPC exports no hit
counter. Configuration capacity and a normal state are not hit evidence.

`BatchStore.process` defaults to `.005` seconds, and the native worker does not
override it. It checks between commands after an execution; control priority
can stop before any execution. Locking, one slow command, preparation,
disposition and COMMIT are outside a hard five-millisecond bound. Executed IDs
are an ordered subset of selected IDs: already-terminal, deferred or blocked
members may be skipped. The count called `partial_prefix_batches` only tests
`0 < executed_count < selected_count`; it is not a proof of a contiguous prefix.
Use actual ordered selected/executed IDs if that distinction matters.

Metadata manifests are separate transactions from the financial disposition.
Executed membership includes rejections, and a CID can be selected again in a
later attempt. Unique `(shard, CID)` admission receipts, recorded memberships
and physical COMMIT counts are distinct. The tool correctly marks the latter
unmeasured; no prepared/COMMITTED record count is a measured fsync/COMMIT count.
The 136 micro-orders are all success and some examples change batch and cache
together. They cannot establish the planned single-factor gain.

## Required execution amendment

1. **Combine the two gates.** `probe_qualification.passed` is deliberately the
   technical gate. Setting only `counts.financial_success_late=1` in a copied
   valid summary returns `passed=true`, `stop_remaining_cases=false`, but
   `financial_soft_deadline_passed=false`. The CLI consequently can exit zero.
   The existing `test_safe_business_rejection_is_separate_from_technical_gate_and_latency`
   explicitly records this separation. The pure counterexample is synthetic
   summary data, not a new observed timeout. The external runner must stop on
   either `passed != true` **or** `financial_soft_deadline_passed != true`, as
   well as the plan's other guards. Do not loosen or silently reinterpret the
   frozen function. Preserve any completed late-success case as failed SLO
   evidence rather than rerunning it away.
2. **Pin the actual run.** Append an execution record referencing the immutable
   plan hash, exact a35 source, actual interpreter/SQLite, all configuration,
   pair order and explicit allowed CPU IDs. Recheck clean source, actual commit,
   generator/runtime hashes and actual numeric worker settings before and after
   each case; merely recording a dirty environment cannot satisfy this gate.
   The tool records CPU count, not
   the complete affinity set. `--cpu-limit 2` chooses the first two currently
   allowed CPUs; coordinate the parent affinity externally so it does not
   silently select a running stability job's CPU. No cpuset or dedicated-host
   claim follows from affinity. Record disk headroom and the two cohost jobs'
   allowed JSON/proc-only health observations.
3. **Bound the outer case.** Internal dispatcher/collector `join()` calls and
   busy timeout are not a hard wall-clock or drain guarantee under OS/I/O
   failure. Register an external wall deadline and grace/owned PID-birth cleanup
   before starting each case. It must retain private authorities, all original
   CIDs and raw errors on timeout, mark outcome UNKNOWN, and stop later cases.
   Never target a preexisting stability process. A stale quote/control failure
   remains failed evidence; no timestamp refresh or source edit repairs it.
4. **Preserve the cohost disk reserve.** The variant plan's two-GiB minimum
   free-space check does not preserve the concurrent six-hour plan's future
   private-clone budget (six GiB plus one GiB clone headroom), producer budget
   (six GiB), observer outputs and the original job's other reservations.
   Twenty-four potential cases at 250 MiB each also need an aggregate cap.
   The external execution amendment must carry forward those existing cohost
   reservations, and require free space beyond outstanding reservations plus
   the next case cap and cleanup overhead. If it cannot prove that headroom,
   stop new diagnostic cases; do not delete original authorities or lower an
   existing long-run budget. This finding uses the recorded plans only; the
   review has not inspected live directories or measured their current size.
5. **Publish the denominator and rejection mix.** Derive fresh group N/max and
   exact quantiles from planned arrival time; label the histogram approximation.
   The throughput denominator includes terminal observation/drain and excludes
   initialization/close. The observed financial rate is not the configured
   20/s arrival rate. The workload is unsaturated and has no matching liquidity,
   fills, liquidation or network/TLS ingress. Control publication can change
   the success/rejection mix across arms; a higher success count alone is not
   a pure risk-kernel speedup. Compare counts, all/success/ACK tails and control
   time, and report zero-success/overloaded cases without a gain conclusion.

These are execution conditions for an explicitly bounded component diagnostic.
No frozen runtime change is requested by this review. A new, separately pinned
external orchestration/report script can enforce them after the remaining
release gates pass. They do not make this tool suitable for the requested
30-minute 10,000/s admission or unique liquidation-fill acceptance: its
configuration explicitly caps duration at ten seconds and arrival rate at
200/s, and every successful order remains OPEN.

This review adds evidence and pure tests only. No account migration or deploy
occurs. Rollback can stop using this review checker in future evidence work;
existing raw results and the original failed/UNKNOWN gates must remain. PM,
Isolated, real settlement assets, replication/AZ recovery and real funds remain
outside this reviewed scope.
