# Independent review of the a35 test contract correction

Reviewed branch head: `f6d3d541a5762325113c61c07f55bcd033aa94ad`.
Frozen base: `a35fd56fc98126b3e5cced8a459bd04ca580e537`.

**Scoped verdict: no blocker identified for integrating this test-only branch.**
The whole seven-commit branch history should be retained, including its red
controls and cleanup failure. This is a static cross-group review, not full
validation or permission to publish a qualified release. All runtime files
under `uta/` are byte-identical to the base; exactly two test files changed.
No service, SQL, test, diagnostic, live observation, process signal or original
job access was executed by this reviewer.

## Same-identity HTTP retry

The helper in `tests/test_gateway_grouped.py` adds only
`admission_overloaded` to the existing explicit 503 allowlist containing
`command_result_unknown` and `admission_queue_timeout`. It preserves the
original method, path and payload on every call and never regards a 503 as
business success. Other 503 codes fail at their first observation. The original
50 ms server observation setting, five-millisecond backoff and three-second
client observation budget are unchanged. As before, this budget is checked
after a completed HTTP request; it is not a new hard end-to-end network RTO.

The actual-overload control fills the real bounded admission queue and releases
the holder only after a real HTTP `503 admission_overloaded`. It requires a
201 result for the original order ID, identical submitted operations, exactly
one matching ORDER_ACCEPTED event, the exact three expected orders and
unchanged account cash. The closed-admission negative control requires one
request, immediate failure, no order and unchanged cash. The original full
submit/retry/cancel/reopen flow and its unique events, reservations and ledger
checks remain. No broad retry, new business ID or response substitution is
introduced.

## Unknown observation and actual owner rejection

The new `observe_market_rejection()` in
`tests/test_readiness_sampling.py` requires each sampled top-level `ready` and
`financial_ready` to be literal false. An unknown generation requires literal
false `owner_ready` and `lease_active`; it is never promoted using a cached
READY frame. A known inactive native lease fails before the retry decision.
For every known generation the current process must be alive and match the
owner PID, while the actual READY frame must match state, PID and generation.
Those mismatches fail at the first observation.

Incomplete observations are resampled only when the top-level reason is
`diagnostic_timeout`, or the requested market rejection is already known on
one shard while another explicitly reports `diagnostic_timeout`. The helper
retains its one-second total observation budget, at-most-100-ms diagnostic
requests bounded by remaining time and the existing finite sampling cadence.
It accepts only a new complete observation with owner/funding readiness,
active leases and the exact expected future/stale market reason on both
shards. Persistent unknown exhausts the budget and fails. Known nontransient
failure is not retried to seek a different owner or market state.

The parent-clock offsets in the original future/stale case remain -2 and +61
seconds. They do not replace the native lease clock or alter production market
age, TTL, control publication, diagnostics or readiness predicates. Restoring
the original clock still requires an actual subsequent ready observation.
The actual control-lock timeout and persistent-timeout controls distinguish
unknown from genuine complete market rejection without writing true values
into the original reports.

## Owned paused-worker cleanup

The negative control selects its new temporary fixture's worker, rejects the
protected historical job PIDs, checks that worker is alive, records its birth
and opens a pidfd. Before SIGSTOP it again requires the same router worker PID
and birth while holding its own router gate and an empty SQLite writer
transaction. Both SIGSTOP and any SIGCONT use that bound pidfd; no numeric-PID
fallback is present.

The unchanged supervisor may kill and replace the expired child. Cleanup first
polls the original pidfd for POLLIN. Proven exit records the old owner's
terminal state and sends no resume. If it has not exited, cleanup checks the
same original birth before signaling that same pidfd. A missing proc entry or
ProcessLookupError requires terminal proof from the bound pidfd; unproven
absence, a different birth or other error fails. PID reuse cannot redirect
SIGCONT to the replacement. The original fixture cleanup still closes its
current children, independently of whether the old paused owner was reaped.

This static assessment applies to the temporary test fixture and observed
control code. It does not authorize signaling or resuming any historical
producer/observer process and does not describe current live-job status.

## Evidence integrity and remaining gates

The original ZIP's three files match the retained extracted bytes. The actual
original CI remains **1243 tests / 2 FAIL / 0 ERROR / NO_GO**. Its readiness
report was not retained, so a unique historical readiness cause remains
unproven. The new deterministic control-timeout mechanism is compatible
evidence, not reconstruction of that original sample.

RUN-A's original two cases passed locally once and are labeled
NOT_REPRODUCED. RUN-B remains five cases with **2 FAIL / 2 PASS / 1 ERROR**;
the error during proc-based cleanup is retained without retroactive pidfd
terminal proof. RUN-C's seven cases passed once on each of Python 3.12 /
SQLite 3.53.1 and Python 3.13 / SQLite 3.46.1, with the new bound-owner terminal
cleanup. Two runtime runs are not fourteen distinct cases or original CI host
reproduction. Their original input-before/input-after hashes, actual source
commits, raw logs and counters agree with the report. No old result is
overwritten by the later scoped passes.

[Static review checks](../evidence/runs/ci-a35-independent-review/static-checks.json)
verify the 27-entry delivery hash manifest, preserved ZIP members, exact
archived A/B/C outcome counters and logs, unchanged measured inputs, syntax
and empty runtime diff. They do not execute those tests again. Final
integration still needs a clean frozen source, the complete local and push/PR
CI matrices, actual package acceptance and any independently authorized
capacity/incident validation. This review grants no long-duration, recovery,
HA, real-funds or production qualification.

Rollback consists of reverting the test correction while retaining all
evidence. It requires no financial migration and must not modify authority
data, leases, original CIDs or previously confirmed effects.
