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
into success. The scoped case passed on CPython 3.10 in 0.107 seconds; its raw
output is `/tmp/uta-startup-binding-scoped-py310.txt`. The independent actual
writer-contention case still fails on the unchanged runtime and remains a
separate availability gate.
