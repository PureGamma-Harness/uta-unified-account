# CI diagnostic cap correction: bounded deque

CODE_ONLY / NOT_RUN. This new source follows aeb5f239. The original aeb5
source,0ac93bfd plan and the independent finding b0d63ade remain historical.

CI-DIAG-AEB-001 identified a real source-level cap race: main and keeper could
both observe list length63, then append two records. A successful length
check did not reserve a slot. The old64-record assertion was not enforced
under that interleaving. This was static reasoning, not a target execution.

## Structural capacity and conservative status

The timeline is now collections.deque(maxlen=64). No separate length check
authorizes append. The container itself retains at most64 records as its
append-order tail. It does not promise the first64 records or chronological
order across threads. Records are fully constructed before append and are
not subsequently modified.

After an append observes capacity64, capacity_reached is set true and never
reset. Snapshot classification also treats an observed64-record copy as
capacity reached. truncated is conservative: reaching capacity is sufficient
even when no eviction is known, and collection failure also marks truncation
possible. No exact loss or attempted-record count is supplied. Recording
continues at capacity to retain the tail; clock/append observation work can
continue beyond the first64 markers, while stored-record capacity stays64.

No new explicit mutex, financial lock, SQL query, thread or process is added.
The standard deque provides its own bounded-container semantics in the
supported CPython runtimes. This is not a lock-free or hard scheduling claim.

## Snapshot failure preserves the original test outcome

A snapshot copies the deque to a list inside a guarded helper. Concurrent
iteration or another collection exception sets collection_failed and returns
a preallocated finite fallback: empty events, snapshot_failed true, truncated
true and capacity_reached unknown. The fallback does not fabricate a complete
trace or catch/replace the original renewal/test exception. Snapshot fields
are observational samples, not an atomic ownership or finality receipt.

The original renew call remains exactly once with its original return
object or bare-raised exception. The17 stage labels, allowed error kinds/codes
and monotonic signed64-bit validation remain. The0.3 wait,0.08 sleep,0.4 lease,
flags, Event ordering, all original assertions and all runtime financial code
are unchanged. Clock and append operations retain their declared observation
overhead; no zero-impact timing claim is made.

The readiness projection B is byte-identical to aeb5. It uses the same one
existing query and original assertTrue, with the same finite identity-free
message only when ready is false.

## Validation and next gate

Preparation verified source/Git bytes, the preserved original plan and the
patch's whitespace. It did not import, compile or execute target code, start
threads, run SQL, inspect processes or rerun CI. Independent limited CODE
review and root's separate new execution decision remain required.

The original plan is copied byte-for-byte as
diagnostic-CODE-plan-aeb5-NOT_RUN.json. It must not be executed against this
new source. Rollback removes this test-side correction in a new candidate;
preserve both original CI failures and all code-review evidence. No runtime
failure cause, capacity, production or real-funds acceptance follows.
