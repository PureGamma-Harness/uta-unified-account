# Independent CI diagnostic cap-v2 CODE review

**CODE_CLOSED_LIMITED_DELTA** for
bf75056cb238112dfa2a67595f2abaf12f5569ae. Target executions: zero. No
execution GO is granted.

The original aeb5f239 source, its0ac93bfd plan and finding
CI-DIAG-AEB-001/b0d63ade remain historical. This review closes that finding
only for the new declared append-tail/conservative-truncation contract.

The ten canonical regular physical/Git source pins total324,768 bytes and
match plan8bcc2030. The old4,034-byte plan archive equals its parent Git
bytes exactly. The complete observe function, main business try segment and
original assertions are text-identical to aeb5; readiness projection B is
byte-identical. All61 UTA Python Git blobs and CI configuration are unchanged.
This does not imply61 physical runtime inputs were materialized.

- **CAP-V2-001**: collections.deque(maxlen=64) provides the storage bound instead of a separate length check authorizing append. The former two-producer63->65 list interleaving now evicts an old element and retains at most64 records.

- **CAP-V2-002**: capacity_reached is only changed fromFalse toTrue. A snapshot's own64-record copy also reports capacity reached. At-capacity status is explicitly possible truncation, not an exact attempted-record or eviction count, and may conservatively beTrue without proven eviction.

- **CAP-V2-003**: The deque retains an append-order tail; it no longer promises the first64 records or cross-thread timestamp order. Complete finite item dictionaries are constructed before append and not subsequently modified.

- **CAP-V2-004**: list(timeline) and snapshot construction run inside a BaseException guard. Concurrent-iteration or collection failure sets collection_failed and returns the preallocated fixed fallback with empty events, capacityNone, truncatedTrue and snapshot_failedTrue.

- **CAP-V2-005**: Fallback does not call financial, clock, query, renewal or retry paths and does not assign the original failure. The original captured renew call remains exactly once with identical return object/bare raise; original main try/flags/thresholds/assertions remain.

- **CAP-V2-006**: Readiness B is byte-identical to reviewed aeb5. Its one existing final diagnostics query, original ready-bool assertion, bounded two-row/six-gate anonymous projection and fixed projection-failure message are unchanged.

- **CAP-V2-007**: Ten source pins and the new plan match physical canonical regular files/Git blobs; the old plan is archived exactly. All61 UTA Python Git blobs and CI configuration remain unchanged.

The former check-before-append race no longer authorizes storage growth.
Two producers appending at capacity may evict old records, but the deque's
maxlen remains64. Neither the document nor plan claims the first64 events,
an exact loss count or chronological ordering between threads.

A marker that reaches capacity sets the flag only true, and a copied snapshot
of64 records independently implies possible truncation. Concurrent-copy
failure cannot be presented as a complete trace: the preallocated fallback
reports empty events, unknown capacity, possible truncation and failed
snapshot/collection. It does not catch or replace the original test failure.

Remaining limits:

- Deque append capacity is structural under the supported standard CPython container semantics; no lock-free, zero-overhead or hard scheduling claim is supplied.

- Recording/clock work continues at capacity to retain the tail, so unlike the old early-return design observation overhead may continue. The source and plan disclose this.

- A snapshot is an observational copy, not an atomic finality or ownership receipt. Events and sticky flags can be sampled at slightly different instants; no precise drop count or final timeline completeness is claimed.

- The deque and snapshot each contain at most64 events; this is not a process RSS or aggregate transient-allocation bound.

- The existing describe_error message/chain behavior is unchanged and outside the new finite timeline-field classification.

- This review is static only: no target import, compilation, test, SQL, thread, native/probe/PID operation, CI rerun or failure reproduction was performed.

- The original f774 CI causes remain unresolved. A later instrumented result must be identified by its actual source and cannot retroactively replace first failures.

- Runtime correctness, capacity, HA, production and real funds remain OPEN/NO_GO.

No newly confirmed blocker remains within this limited delta. Root must
separately select an exact new execution/CI scope, retain its first result
and obtain independent RAW review. No prior runtime result is reclassified.

Only administrative standard-library text/byte hashing and Git reads were
performed. A verified-new review-only worktree/index and these two SAFE
reports are the only writes; no source, primary index or authority was changed.
