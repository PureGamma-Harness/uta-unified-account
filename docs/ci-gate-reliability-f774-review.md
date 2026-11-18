# PR52 corrected-source gate failures: read-only review

Reviewed immutable source `f7747c100a68c88a894b5aded73f12717ad54064`.
The two selected failure logs were read with O_NOATIME and verified against
the sealed collection. No target code, SQL, process inspection, thread, worker
or CI rerun was executed. This review identifies evidence gaps; it does not
establish either failure's root cause.

## Startup renewal failure

The PR Python3.13 log fails at test_startup_write_contention.py:74. Its existing
diagnostic records entered, constructed, writer_held and renewal_requested as
true, finished as false. Both the keeper and the final error chain report
lease_expired; the final error is startup_keeper_failed. No SQLite error code
is present in that exception chain.

The fixture retains the0.4s lease. The financial writer holds the common
initialization RLock from before connection setup through COMMIT and close.
It then waits up to0.3s for an observation event and sleeps0.08s before leaving
the transaction. The event is emitted before the keeper invokes the original
renew function. The keeper still needs the same RLock and a real control
transaction before a renewal can commit.

Consequently,0.08s is not an upper bound on actual write-gate holding time,
and0.4s is not the measured lease time remaining when that interval began.
The log does not identify the last successful renewal, gate acquisition,
transaction-return stage, or the source of delay. The recorded expiry
rejection prevents renewal of an expired token; changing that rule would
weaken ownership enforcement.

A useful next diagnostic is a bounded monotonic-only record in the existing
test observer: renew request, renew return or error, main writer-body entry,
requested wait return, sleep return, transaction return, and finish entry/
return. Preserve the original one call, exception and thresholds. A finite
event buffer must mark truncation and must not acquire a new lock or inspect
a database. Instrumentation adds clock and bookkeeping overhead, so a later
run still needs explicit scope and original timing semantics.

## Partial fanout readiness failure

The push Python3.12 log fails at test_process_readiness.py:196 with only
False is not true. The final diagnostics result is discarded. Its reason and
individual predicates are absent.

The exact original snapshot is created before partial publication with a
blocked shard. The snapshot is reused after the blocker is released. The
activate helper completes publication and activation and then successfully
waits for readiness. Line196 makes another live diagnostics query.

The fixture's market age limit is2s and worker lease is1s. Each diagnostics
query has a1s default shared budget and independently validates control,
owner/liveness/lease, local activation, funding registry and market freshness.
Its final checks can reject an earlier observation that ages or expires
during the query. Earlier readiness therefore does not guarantee the next
query remains ready. This source behavior is a conditional explanation,
not evidence that any particular predicate caused this failure.

The smallest useful diagnostic retains that same one query in a variable
and adds a finite identity-free projection to the unchanged assertion:
top-level reasons/control booleans, counts of worker reasons and counts of
true gate booleans. Do not copy PID, owner, nonce, generation, shard identity,
market digest, path, full worker report or exception message. Do not add a
second query, new snapshot, refresh, retry or larger deadline.

## Scope and next decision

The nine inspected test/control source files are pinned in the companion JSON.
They equal the PR46 base versions; that fact cannot exclude indirect effects
of the corrected policy or different host conditions.

No runtime change or diagnostic patch is supplied. Parent coordination is
pending on the narrow diagnostic proposals. Existing first failures, expiry
rules, readiness predicates, thresholds and assertions remain intact.
Production, capacity and real-funds acceptance remain open.
