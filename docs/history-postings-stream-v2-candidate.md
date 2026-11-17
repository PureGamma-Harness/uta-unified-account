# Two-cursor postings replay: V2 implementation, NOT_RUN

V2 is on separate branch `perf/history-postings-stream-v2`, based on immutable original red archive `d77edb4`. Original runtime `56de743`, exact observed candidate `52d2a4cc6edfe5b8f11146b6472274746135a6e3`, original measurement harness and all attempt-01 raw files are unchanged and remain recoverable in Git. Four original failures are not relabelled passes. No actual V2 SQL/test/profile has been authorized or run at this milestone.

## Repair and preserved boundary

The default `ordered_postings=False` still issues the old per-event query. V2 changes only the explicit opt-in branch:

* One ordered metadata cursor selects `(sequence, COUNT(*))`; it cannot decode account/asset/units text. One group metadata row is kept as lookahead.
* The payload cursor is opened only after the first applicable event's existing sequence/sealed/prior-chain check. For each matched metadata group, the verifier reads exactly that count of payload rows and checks each payload sequence. It never fetches a later group's payload to discover the current boundary.
* The original per-event ordinal, canonical integer, normalization, fingerprint, hash, cumulative signed balance and final materialized-balance checks remain in their original order. A missing current metadata group produces the same empty-postings error without fetching a later group's payload. Residual metadata/payload or count/sequence disagreement fails closed.

The metadata query adds another posting-key traversal. This is **N to 2 statements for a nonempty valid journal**, not a reduction in complete financial coverage or asymptotic O(N+P) proof. Empty history issues one metadata query and opens no payload cursor; the default issues zero posting queries. SQL statement counts do not measure SQLite internal index operations.

Event rows still use `fetchall(N)` and projected balances remain a complete balance map. Only the posting group and metadata lookahead are bounded by one group plus one row; there is no constant-memory full-history claim. There is no persistent/cross-call/cross-PID cache, new index, schema migration, guard bypass, timeout adjustment or startup/configuration wiring. Original integrity/FK/version/scales/trigger and writer/identity checks remain. Default final cold replay stays on the original path.

Exact financial first-error semantics are required for the original supported catalogue under the declared corruptions, including invalid UTF-8 TEXT. This does not promise identical resource-failure timing under OOM or unreadable storage. The separately documented removed-FK catalogue gap is owned by another group; V2's stricter rejection of unmatched inventory does not repair the default path or impersonate that group's acceptance.

## Tests and measurements pending

All original 23 test methods remain; the statement-count assertion explicitly changes from one to two opt-in SELECTs. Four new methods cover missing-first-group before future invalid UTF-8, later-chain failure before that group's invalid UTF-8, an actual decode error with no earlier financial fault, and the empty-history/no-payload boundary. Source AST parsing finds 27 methods; **none has run against V2**.

The new V2 harness must have its own identity and output directory, never overwrite attempt-01, and observe actual fetched event/payload/group rows as well as statement counts. The expected nonempty full component is N=512/P=1024/group rows=512, with all payload rows and original full guards retained. Additional row-factory counting and cProfile overhead belong to the instrumented measurement. First/repeated page-cache states remain uncontrolled; logical selected bytes and `/proc/self/io` counters do not prove physical cold disk I/O.

Root and another group must review the exact runtime/harness SHA before a new single total-15-second CPU4 component is considered. CPU4 is queued after the separately approved native and repayment-oracle work; this branch does not claim the slot or execute SQL while waiting. Any red stops profiling and is preserved. Author signoff is insufficient for independent acceptance.

Rollback remains leaving the option false or omitting this separate R&D patch. No data migration or authority rollback is needed. V2 currently has no correctness or performance acceptance, and no throughput, large-history RTO, sustained-capacity or production claim.
