# Owned startup write contention investigation

Base: `4608ffe`. The original full CPython 3.10 run retains its unmodified
failure at `/workspace/uta-operations-validation/4608ffe/python310/unittest.txt`:
the ledger substitution test expected `startup_not_verified` but received
`startup_keeper_failed`. That old output contains no keeper cause or proof that
construction and substitution completed; its exact underlying exception cannot
be recovered from the assertion text alone.

An independent small test reproduces a real reachable availability failure on
the same unmodified runtime. It first enters and constructs a genuine owned
context, checks it is healthy, then holds an actual financial `BEGIN IMMEDIATE`
transaction. A call-through observer confirms the actual keeper requests its
next `WriterFence.renew`. Holding the writer for 80 ms exceeds the unchanged
`.4 / 12` SQLite busy wait but remains below the unchanged .4-second lease. The
real renewal raises `sqlite3.OperationalError: database is locked`; the keeper
poisons the context, and finishing fails without READY. No SQLite error, clock
or verification result is mocked and no business effect is fabricated.

The original red test output is `/tmp/uta-startup-binding-4608-red-py310.txt`.
Both the original keeper exception and its causal wrapper are recorded, with
phase flags confirming entry, completed construction, real held writer and a
requested renewal; finish remained false. CPython 3.10 does not expose the later
SQLite exception code/name attributes in this environment, so those fields are
explicitly null. This proves the self-contention mechanism, not that it was the
only possible cause of the old full-suite failure.

A companion negative case holds a real producer-role writer. Its genuine busy
error must continue to poison initialization. Actual renewal errors, including
responses lost after COMMIT, must never be retried into a fabricated success.

The proposed minimal runtime change is a separate per-initializer write gate.
The initializer's financial transactions and its keeper share it from before
connection opening through COMMIT/rollback and close. It is not the registry or
metadata lock. Lookup releases the registry lock before waiting; read snapshots
never hold this gate, so full verification and lease renewal still overlap.
After waiting, lifecycle, identity and the actual persistent lease are checked
again. Waiting before SQL is local scheduling, not retrying a failed renewal.
Writers in other processes and producer-only transactions retain their original
SQLite/fencing semantics. No TTL, busy wait, financial formula or unknown-result
policy is relaxed. A financial transaction that outlasts its real lease must
still fail, and an expired keeper cannot revive its generation.

The object-binding test must separately establish successful construction and a
healthy, drained renewal lifecycle before substitution, then assert only the
intended finish call's exact `startup_not_verified`. It must preserve the cause
of setup failures and clean an unfinished context explicitly; catching the
expected exception inside a normal `with` exit would otherwise introduce
`startup_not_finished`. Cross-TTL, expiry, unknown-COMMIT and invalidation cases
remain independent gates.

The binding fixture now completes context entry and construction outside its
rejection assertion, checks the genuine lifecycle, drains the keeper and obtains
one actual synchronous renewal with the same .4-second TTL. Only then does it
substitute and prove the ledger object changed. Only `finish()` is inside the
exact `startup_not_verified` assertion. An unfinished context is explicitly
cleaned without claiming a successful exit. Existing keeper failures are checked
before that synchronous call, so this cannot wash an earlier unknown renewal
into success. The scoped case passed on CPython 3.10 in 0.103 seconds; its raw
output is `/tmp/uta-startup-binding-scoped-py310.txt`. The independent actual
writer-contention case still fails on the unchanged runtime and remains a
separate availability gate.

## Implemented scheduling boundary

Runtime commit `4cce708` adds the independent gate outside the existing
`Database._role_transaction` implementation. An active authority's financial
and fence-control roles acquire it before `_connect` (including WAL setup) and
retain it through the existing transaction, rollback/COMMIT and connection close.
Only an active matching inode/canonical path participates. An unrelated new
authority follows its existing creation and financial path. No schema, token,
business formula, SQL busy timeout or TTL changes.

The gate serializes all this scope's fence-control operations, not only keeper
renewal. Their SQL permissions and actual token/expiry checks remain unchanged.
Financial actor checks run before waiting, after acquiring the gate, and again
at the original post-BEGIN guard; COMMIT fencing remains original. No registry
or metadata lock is held during the gate wait. Local waiting checks stop,
deadline, identity and already recorded failure. It is bounded by the original
lease budget and deadline; timeout rechecks any existing failure before returning
a new scheduling error. A long owned transaction still expires and rolls back.

Read verification and producer-role transactions do not acquire this gate. This
preserves actual renewal during long RO replay and leaves genuine external
SQLite contention visible as a technical failure. The SQL operation is invoked
once. There is no retry of BUSY, expired-token or lost-COMMIT responses. The
`last_renew_started` diagnostic remains request-start, now including local gate
waiting. Its scheduling anchor is conservative: waiting can cause an earlier
subsequent renewal; it cannot postpone expiry or establish an exact SQL-BEGIN
timestamp.

## Red/green evidence and delivery limits

The final source and test bytes passed 67 targeted cases sequentially on CPU 0:

| Runtime | SQLite | Tests | unittest elapsed |
| --- | --- | ---: | ---: |
| CPython 3.10.22 | 3.53.1 | 67 | 10.892 s |
| CPython 3.12.14 | 3.53.1 | 67 | 11.125 s |
| CPython 3.13.5 | 3.46.1 | 67 | 12.321 s |

The selection includes all owned-startup, independent owned reference,
original expiry, storage and writer-fence cases. The new real-lock tests cover
self-writer success, producer BUSY poison with the original SQLite cause,
unchanged-TTL COMMIT rejection and rollback, and an unrelated authority's real
deposit. The original unknown-COMMIT and expired-renewal tests remain unchanged.
All three final logs report `OK` without skips. This is a component/regression
result, not a complete repository or production qualification.

Original evidence remains unmodified:

- Full historical failure: `/workspace/uta-operations-validation/4608ffe/python310/unittest.txt`.
- Genuine self-contention red: `/tmp/uta-startup-binding-4608-red-py310.txt`.
- Narrow binding assertion: `/tmp/uta-startup-binding-scoped-py310.txt`.
- Final source/test hashes, exact commands, environments, UTC times and combined
  stdout/stderr: `/tmp/uta-startup-binding-4cce708-final/manifest.json` and its
  three `python3*-targeted.txt` logs.
- Re-runnable driver: `/tmp/uta-startup-binding-final.py`.

The exact runtime diff received independent read-only review with no blocking
finding; that reviewer did not claim an independent test rerun. The old full-run
cause remains unknown because its original output did not preserve the keeper
cause or substitution phase. The deterministic red proves a reachable mechanism
and the green proves its isolation; neither retroactively recovers missing data.

Deploy as an immutable reviewed source release, draining/stopping the old
coordinator before normal owner startup. No database migration, flag or stored
receipt rewrite is required. Reverting only the runtime commit restores the
prior scheduling behavior and its known self-contention availability gap;
financial fencing remains in either version. Keep exact scoped assertion tests,
and retain the red test as evidence of that regression. Root integration,
complete-suite/remote CI and the other independently tracked diagnostic/grouped
timing issues remain separate gates. No large history, long load, root/frozen
workspace or original long-running authority was changed in this investigation.
