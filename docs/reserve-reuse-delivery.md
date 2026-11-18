# Exact reserve reuse: bounded legacy matching comparison

This adds benchmark controls and evidence for the existing opt-in ReserveKernel.
It changes no financial runtime, ordinary tests, tools, build, workflow or
production default. Cache capacity remains0 unless explicitly configured.
The measured scope is legacy-reference USD linear matching, not configured
Cross lending or PM. The new Cross Decimal candidate is separate and unmeasured.

Four pure contracts passed once. Independent CODEb25b8ce9 and RAWbd6b1ef6
checked complete economic keys, exact fee arithmetic, LRU and Decimal-context
behavior. Its abbreviated four-dot output is not a per-ID verbose trace.

The unique native pair at73c8aa3 compared capacity0 and128 with32 resting orders,
one matching call and8 matches/16 paired fills in each authority. Independent
RAWd94df7bb verified ledger chains, FIFO, maker price, signed positions/cost,
cash, cumulative fees, nine risk fields, complete before/after reopen state
and one sampled FILL valuation per authority. Only capacity and its canonical
policy ID differ; all other policy fields and runtime artifact match.

Candidate matching observed568 hits, zero misses and zero evictions. A freshly
reopened kernel observed28 hits/4 misses/size4. Both matching batches had the
same SQL trace map and actually ran cProfile plus local LINE observation.
Matching wall was114769067ns versus85834410ns, in a single fixed-order profiled
pair. This is not statistical significance, absence of regression, throughput,
latency percentiles or production acceptance. Counts are authority-qualified;
paired comparison databases reuse business trade IDs.

Actual prefix exit0/reap and both EOFs were observed in9179087059ns. All86
private originals/3788579 bytes and the prelaunch capture source were bound;
full databases, reports, source capsules and bindings remain private. Public
evidence contains finite projections and opaque byte/hash inventories only.
First integrated CI for this delivery is pending.

Deployment is limited to explicit synthetic component runs with new exclusive
namespaces and approved source/plan hashes. Do not reuse sealed paths, alter
TTL, change defaults or transfer these results to a different risk mode.
No schema migration or live authority upgrade is provided. Rollback removes
the benchmark invocation and preserves all first evidence and confirmed
financial history. HA, mixed load,10000/s sustained capacity and real funds
remain NO_GO.
