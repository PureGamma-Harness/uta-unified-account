# V2 attempt 02: component controls pass, no measured speedup

Exact frozen candidate `3a48aa4eb27b8c7a61241c7045b25faf24a8737c`, runtime `dd502ae538618c6d17a3bd2eae708e09526e9d4c`. This is one root-approved author-run Python 3.12.14/CPU4 component, after the native and repayment-oracle groups explicitly released CPU4. It is not independent acceptance. The [original four failures](history-postings-stream-attempt-01.md) and original runtime/harness/raw bytes remain unchanged; the V2 observation is a separate result.

Actual outer interval 2026-11-17 15:13:35.560026–15:13:36.529503 UTC: **0.969458393s**, exit 0, no watchdog or forced cleanup, owned PID 234158 reaped and `/proc` entry absent. The harness completed before its source-configured 14s internal alarm and the outside 15s cap; no timeout exception was reported. This is an observed normal completion, not proof of OS quota enforcement. All 53 runtime/test/harness input hashes match before/after, including the three exact root-approved SHA256 values.

All **27 differential methods passed, 0 failures/errors/skips**, including the original four same/future-group UTF-8 first-error controls and the new missing-first-group/later-chain/no-earlier-fault/empty-history controls. The fixture then confirmed two real public-post batch transaction returns at 256 and 512 events. No order, matching, fill, risk, loan or customer-command workload occurred.

| Call in actual order | Path | Complete fetched event / payload / metadata / balance rows | Posting SELECTs / all SQL | Wall ms | CPU ms |
| --- | --- | --- | --- | --- | --- |
| 0 | Original, first measured after fixture/reference | 512 / 1024 / 0 / 2 | 512 / 523 | 40.863752 | 40.863768 |
| 1 | V2, repeated | 512 / 1024 / 512 / 2 | 2 / 13 | 41.753702 | 41.698892 |
| 2 | Original, repeated | 512 / 1024 / 0 / 2 | 512 / 523 | 38.272587 | 38.221859 |
| 3 | V2, repeated | 512 / 1024 / 512 / 2 | 2 / 13 | 45.326611 | 45.253971 |

V2 reduced statement dispatch but **both measured V2 calls were slower than their preceding original calls**. This fixed-order, small, instrumented observation establishes no speedup, production regression estimate, statistical confidence or large-history improvement. The new path additionally scans group keys, selects the sequence column with payloads and executes 512 extra measurement row callbacks. Source code safety and lower statement count do not establish faster execution.

Actual logical event-row JSON bytes were 114470 on each call. Original payload JSON bytes were 17920; V2 payload JSON bytes were 21800 (it includes sequence), plus 3476 metadata bytes. Both fetched 35 balance-row JSON bytes. The separate common literal-reference dataset representation is 135462 bytes. These are different precisely defined logical representations, not physical storage byte counts. All four process `/proc/self/io` deltas reported `read_bytes=0`, `rchar=209118`, `syscr=54`; the counters include the process's harness/log activity and kernel page-cache effects. They do not prove fewer physical reads or cold-disk performance. Row serialization, tracing and cProfile overhead are included in the instrumented measurements.

The final **default** verifier used a freshly reopened handle and completed a full uncached financial proof. Independent literal initial/final references match N=512, P=1024, balances `a/USD=-512`, `b/USD=512`, and head `5a02b906bca3dc227c15b5be57632d2fa5f54b50089d0823151c0d96f1b47049`. “Cold” refers to a fresh handle/default complete proof, never an OS cache flush. Scratch cleanup completed normally.

## Retention, review and rollback

The [retained raw directory](../evidence/runs/history-perf-rnd/attempt-02-v2) contains byte-identical copies of launch/stdout/stderr, summary, all phases, full unittest log and four exported profile texts with SHA256 manifest. Original external copies remain at `/workspace/uta-history-perf-evidence/attempt-02-v2` and `/tmp/uta-history-postings-v2-3a48-once`. No binary pstats/pickle, database, auth or TLS material is published. The pure [author verifier](../evidence/runs/history-perf-rnd/verify_attempt_02.py) opens only these retained files and checks exact source, all row/statement counts, normal cleanup, reference equality and original-red hashes. Its result does not replace independent review.

Keep `ordered_postings=False`. There is no configuration/startup wiring, schema migration or financial authority change. Rollback is to omit this separate R&D branch or leave the original default. Another group must review the actual candidate/evidence before any integration; the author does not independently sign off. No additional run is authorized by this report, and no 10k/s, physical cold I/O, sustained capacity, 250k recovery RTO, HA or production claim follows.
