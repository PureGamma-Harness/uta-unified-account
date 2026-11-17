# Actual native late boundaries, first run

Test-only source `33e9c13d83027264a80f1bf4ff7c89ae8ec64d1e` ran on CPU4 at
2026-11-17 14:58:46.862801–14:58:57.469899 UTC, 10.612 seconds. The raw
unittest exit **1** is preserved in `evidence/runs/credit-v2-native-late-boundaries/attempt-01/`.

Each fault followed real original `_borrow`, complete content-addressed credit
decision, sealed journal, original credit receipt and original command
`SUCCEEDED` staged in the same actual financial transaction. Four subcases
completed their assertions: losing the context after normal scope closing,
expiring the fixture's synthetic market clock before closing, expiring it after
closing before physical COMMIT, and attempting an unrelated Bob account write.
Every outer commit was refused, actual financial tables equalled the initial
snapshot after reopening a read transaction, and the original command remained
`PENDING`. The clock faults use only this disposable fixture's synthetic clock;
they do not establish wall-clock or live-UTC behavior.

The fifth subcase, losing the operation reference before closing, also actually
refused physical COMMIT, but the test expected only `WriterFenceError`. The
actual first latched exception is the correctly typed `CreditV2Error`
(`credit_v2_context_invalid`, a `StorageError`) from the orphan actual-intent
check. The harness therefore errored before executing its post-rollback
assertions for that subcase. This is not a successful commit or evidence of a
runtime bypass, and those unexecuted assertions are not claimed as passing.
The narrow harness correction and rerun will be recorded separately; no runtime
permission or financial function is changed to make this test pass.

Fault injection sets actual registered guard references to `None` only for
negative cases. No successful UDF, invented context, grant, or decision was
supplied. All data came from a new disposable synthetic database, with temporary
directory cleanup registered. Retained oracle/live databases were not opened.

## Narrow harness correction and rerun

Test-only commit `943d8b74ed0f93d49680a0cd1c882b07549e8a6c` retains the
original exception and checks its exact code. Losing the operation reference
has its own case; the four previously passing subcases remain a separate case.
No `uta/` runtime file changed. Only the new orphan-intent case was rerun.

CPU4 ran that one case at 15:00:06.780643–15:00:10.482456 UTC (3.704 seconds),
exit 0. It observed the actual `credit_v2_context_invalid` first-latched failure
at physical COMMIT after full real financial staging. All selected financial
tables equalled their original snapshot, and the original command was still
`PENDING`. The other four subcases were not repeated or relabeled as one
combined new green run. Their first-run evidence and the original first-run
exit 1 remain unchanged. New raw is under `attempt-02/`.

This is native failure containment evidence for synthetic internal credit.
It neither tests live-UTC freshness nor approves production trading, HTTP/CLI
enablement, real funds, interest scheduling, or dynamic cross-shard budgets.
