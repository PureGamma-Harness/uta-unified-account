Draft title: Bound supervisor SPAWNED registration busy waits

The only supervisor registers replacement children synchronously with a control
database whose default SQLite busy timeout is ten seconds. Under a registry
conflict that delay can hold up another shard's expired-owner scan. SPAWNED
registration now uses a shallow database copy with `timeout=min(original, .1)`;
the shared database, other registry events, single INSERT, UNKNOWN append
outcome, gated-child cleanup and new-child backoff keep their existing behavior.
The runtime diff is limited to ten lines in `uta/durable_process.py`.

The first fixed-base conditional model preserved a RED witness in fourteen of
sixteen finite schedules. The first candidate model passed twenty-four finite
scenarios on CPU 1, including smaller pre-existing timeouts, unchanged other
events, preserved copy fields/hooks, lost replies and unconfirmed cleanup.
Both first results and their exact source closure are retained. Three new
unittest-discoverable pure regressions cover the same boundaries; they have not
been manually run and await their first new CI execution. Static independent
review found no new blocker in the runtime diff.

Three literal `MANIFEST.in` includes preserve the existing `.sha256` provenance
originals, which the prior extension selectors omitted. Package inclusion has
only been checked statically in this preparation; the next built sdist still
needs CI verification. The runbook limits evaluation to fresh synthetic,
source-bound authorities and preserves original CID/metadata/confirmed trades
through any separately reviewed transition or rollback.

This remains a Draft conditional progress repair. PR 35's original L1525 failure
is open and its actual cause remains UNKNOWN. No native recovery case, worker,
SQLite connection or signal was executed for this change. Busy timeout is not a
hard function-duration bound: native LOCKED/PROTOCOL behavior, internal WAL
retry/backoff, disk I/O and OS scheduling remain unbounded here. Actual bound
kernel SH release, five-second recovery, new READY, market ACK and financial
reconciliation have not been verified. No original-authority binary replacement
or production approval is claimed.
