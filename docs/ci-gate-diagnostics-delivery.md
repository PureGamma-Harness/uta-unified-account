# Bounded startup and live-readiness failure timelines

This test-only patch records missing evidence for two existing PR52 CI failures.
The short-writer test holds the real write gate while waiting up to0.3s for a
renewal request, then sleeps0.08s. A request is observed before the original
renewal acquires the gate. The old log has no remaining-lease/queue/return
timeline, so it cannot prove the held interval fit within the remaining0.4s.
The other test's earlier wait_ready success does not guarantee a later
independent live diagnostics call remains ready. Neither log proves a cause
or excludes indirect effects of other changes.

The startup observer records17 fixed stage labels and finite monotonic_ns/
exception kind-code values. It calls the original renewal exactly once,
returns the same object or re-raises the same exception. It retains the
original thresholds, phase flags, assertions and business sequence, adding
no SQL, locks, processes, threads or PID inspection. Recording inside a gate
adds observation overhead; these timestamps are not lease-clock or physical
commit timestamps.

Initial candidateaeb5f239 used a non-atomic len/append pair. Independent
b0d63ade found a two-producer interleaving allowing65 records despite a64 cap.
The revised candidatebf75056c uses deque(maxlen64), retaining append-order
tail records. Reaching capacity conservatively marks possible truncation;
no exact eviction count, first64 or cross-thread time ordering is promised.
Concurrent snapshot failure returns a fixed finite empty fallback without
replacing the original failure or assertion.

The partial-fanout assertion retains exactly its original final diagnostics
call. Only when False, it reports fixed anonymous reason/ready flags and
aggregated true/false/unknown counts for at most2 workers and6 gate fields.
It emits no PID, generation, shard, nonce, digest, private path, arbitrary
object string or exception text. It does not refresh a quote or retry a query.

Independent delta813448b6 closed the capacity finding and verified the
original observer/business/assertion text and unchanged readiness projection.
All10 selected physical source inputs remain unchanged after integration;
all61 UTA modules and CI/build files are identical to PR52e7fa6e41.
No local target or fake-thread execution has occurred. First normal CI of
this new instrumented test source is pending and is a separate observation,
not a same-source replay of the old failure.

Run only normal new synthetic fixtures; no account/data/policy migration.
Rollback removes these diagnostics while retaining old failures and timing
records. Do not extend a lease, relax a deadline, suppress an assertion or
relabel a quote to make these tests pass. Live root causes, runtime safety/
liveness fixes, capacity, HA and production/real-funds acceptance remain OPEN.

## First normal CI and independent RAW acceptance

First push44314535158 and PR44315430535 attempt1 completed all eight jobs and all200 steps successfully. The two fixed Python3.13 unit logs each report2070 tests with no failures/errors/skips. Both target methods are plain-ok in each log. The376-entry source maps bind to the tested source93c6d572.

Collector f0fb9689 and independent RAW c78ce98f verify48 originals2961714B, three ZIPs261782B/25CRC and the finite package report. No target failure trace was emitted: the17-stage and64-entry timeline limits remain source contracts, with actual failure-event/cap behavior NOT_OBSERVED. These results do not establish that either historical root cause was fixed. Runtime, tests, tools, benchmarks and CI configuration are unchanged by this evidence integration. The independent administrative reader corrected a canonical-hash newline assumption, recorded separately from target/CI execution. Production/HA/capacity remain NO_GO.
