# Managed admission variant wiring

The benchmark now accepts `--normal-cache-size` (0..65536),
`--financial-batch-size` (0 or 3..8), and `--durable-batches`. The Python
`Configuration` has the same fields. Defaults remain **0 / 0 / False**.
Nonzero batching requires the durable capability. Invalid types, ranges, or
combinations fail before creating an output directory, database, child process,
or changing CLI CPU affinity.

The tool passes these values to the real `DurableProcessRouter.initialize`.
It records the router's settings, each spawned child's received settings and
PID, and checks the immutable capability again with a read-only reopen after
shutdown. Child input observation wraps only worker entry; the original native
worker, guards, SQL fencing, audit, background supervision, freshness checks,
and financial execution remain unchanged. Input observation is not a READY
receipt or evidence that a cache hit occurred. Managed IPC does not currently
export cache hit statistics; configured capacity must not be presented as hits.

## Execution and accounting

The native `BatchStore.process` default is a **5ms soft execution budget**.
The tool records that default from the actual loaded method signature. The
native worker does not override it. The budget is checked between commands
after at least one execution, rather than imposing a hard transaction or
COMMIT deadline. One command may exceed 5ms. Control priority can produce zero
executions; selected size 3 or 8 can produce only one execution. Preparation,
locking, freshness checks, outcome recording, and COMMIT add time. Selection
membership must never be reported as successful or amortized financial work.

Reports distinguish durable enqueue ACKs, observed post-COMMIT financial
SUCCEEDED receipts, product rejection, control/market rejection, all-CID
technical retries and last errors, and batch failure phases. Reopened batch
manifests supply selected/executed membership counts and unique command counts.
A command may appear in several selections; executed membership includes
rejected commands. Prepare metadata and financial outcome are distinct durable
transactions. These record counts **do not measure physical COMMIT counts**.
Control CIDs stay in their single-command lane. The existing stop gate still
rejects internal retries, failed controls, batch failures, unknown results,
poll errors, and reconciliation discrepancies even when an eventual financial
outcome looks safe.

The measurement is local SDK admission through an inbox to independent native
PIDs. It does not measure REST/TLS ingress, matching, liquidation, replication,
or exchange capacity. Successful orders remain OPEN with their reservations;
reopening also requires zero matches, fills, and positions. Admission ACKs and
business rejections do not count as financial throughput.

## Fair comparisons and qualification

The new [preregistration](../benchmarks/plans/20261117-managed-variants.json)
is **PLANNED_NOT_RUN** and needs final source qualification and a quiet-window
GO. No performance cohort was run for this wiring change. Compare batch 0,
3, and 8 using **durable_batches=True for every arm**. Capability-True batch-0
still pays capability validation and recovery costs. The default capability-
False configuration is a compatibility check, not the batch gain baseline.
Cache comparisons hold batch size and capability constant; use the same final
source, arrival schedule, resource limits, fresh synthetic feed, guard policy,
audit requirement, and drain protocol. Preserve negative results and original
errors. Historical unsafe 7a06 and the corrected 720 S1 retry failure are not
gain baselines for this candidate.

## Functional evidence and operation

The evidence under
[`docs/evidence/managed-variant-wiring-20261117`](evidence/managed-variant-wiring-20261117)
contains only tiny functional checks: four fresh authorities, eight synthetic
arrivals each, 0.05s scheduled arrival windows, no profile. They validate option
wiring and read-only reconciliation, **not throughput, tail SLOs, sustained
stability, or production qualification**. Original runtime, hardware, worker
inputs, planned times, receipts, startup observations, manifests and test logs
are retained. Authority databases remain private temporary files.

For a future authorized short diagnostic, start from the final qualified
commit and a fresh output path:

```sh
python benchmarks/run_managed_benchmark.py --output /tmp/unique-samecap-baseline --duration 10 --rate 20 --accounts 100 --shards 2 --cpu-limit 2 --durable-batches --financial-batch-size 0 --normal-cache-size 0
```

Use the preregistration's alternating order and compare individual financial
receipts, all/accepted/ACK latency distributions, drain, rejection mix, and
technical diagnostics. A nonzero exit preserves evidence and stops subsequent
cases. Do not run planned pressure or profiles before the separate GO.

Rolling back batch execution means selecting batch 0 with a **capability-aware
binary** while preserving the durable capability, schema, and pending-attempt
recovery. Capability activation is irreversible for that authority. Do not
drop its marker/schema or roll back to an incapable writer. These benchmark
options initialize fresh synthetic authorities and do not migrate an existing
authority or alter a running stability job.
