# Uninstrumented attempt 03: complete ABBA evidence, keep default off

Exact approved harness candidate `53b3ba47bbfd2921b407995e8bd5961562655cfa`, SHA256 `caf46cdf706000c2bb73bb921999be6ea82a04b15c2e836cd67422b6cfc14adb`; unchanged runtime `dd502ae538618c6d17a3bd2eae708e09526e9d4c`. This is a new author-run synthetic R&D observation after explicit root approval and CPU4 release. It does not relabel the [original four failures](history-postings-stream-attempt-01.md), replace the [slower instrumented observations](history-postings-stream-attempt-02-v2.md), or add the separately reviewed default-catalogue patch. The author cannot sign independent acceptance.

Actual Python 3.12.14/CPU4 outer interval: 2026-11-17 **15:50:59.166930–15:51:01.590101 UTC**, **2.423153440s**. This covers child import/main return, summary/sample/phase/stdout/stderr output closing and source/output hashing; final outer metadata serialization follows the recorded endpoint. Exit 0, watchdog false, forced cleanup false; owned PID 243400 reaped and `/proc` entry absent. All 53 measured runtime/control/harness source hashes match before/after. The harness returned normally before its 14s alarm and outside 15s budget; that is observed completion, not an OS hard-quota guarantee. CPU4 was released immediately after completion; there was no retry.

The separate correctness suite completed **27 methods, 0 failures/errors/skips** in 0.351s, outside timed intervals. The measurement authorities used ordinary `Database` and original `sqlite3.Row`, with no cProfile, row callback/JSON serialization, SQL trace or memory tracing installed. Each interval contains only clocks and the complete real `verify` call, including connection/native SQL/guard/transaction/commit/close. Phase and sample serialization occurs after the clocks stop, inside the total budget.

Scale order was fixed at N512 then N4096. Actual public-post COMMIT-return records reached exactly 2 and 16 batches of 256 events, respectively. Each scale ran the declared untimed A then B warm-up, then exactly three ABBA blocks. All **24 samples** remain in original order in [samples.jsonl](../evidence/runs/history-perf-rnd/attempt-03-uninstrumented/samples.jsonl); no slow sample was removed. A is the candidate's false/default path; B is the explicit opt-in, not a different historical binary. The repeated warm proofs establish no physical cold-I/O state.

| N | Block | A wall mean ms | B wall mean ms | B/A wall | B/A CPU |
| --- | --- | --- | --- | --- | --- |
| 512 | 0 | 11.556821 | 9.826832 | 0.850305806 | 0.852040742 |
| 512 | 1 | 9.987654 | 9.628920 | 0.964082306 | 0.964087770 |
| 512 | 2 | 10.834884 | 10.273389 | 0.948177110 | 0.950060992 |
| 4096 | 0 | 75.102606 | 74.800262 | 0.995974254 | 0.996200951 |
| 4096 | 1 | 81.483228 | 79.662382 | 0.977653733 | 0.978198483 |
| 4096 | 2 | 76.739975 | 78.411778 | **1.021785302** | **1.021281013** |

Table decimals are rounded displays; raw summary contains exact rational means, B/A ratios and signed B-minus-A mean deltas. The median of three block ratios is N512 wall **0.948177110**, CPU **0.950060992**; N4096 wall **0.995974254**, CPU **0.996200951**. N512's observed block means are lower for B; N4096 is mixed and its median is near parity, including one explicitly slower block. This is a small fixed-order, single-process/platform exploratory comparison, without a confidence interval or production speed estimate. It does not justify enabling the option. The earlier instrumented +2.18%/+18.43% results remain their original actual outcomes.

No per-call fetched-row or SQL-statement instrumentation ran here. The 512/4096 values in timing samples are returned verified-event counts, with before/after complete reference checks. They are not new empirical per-call row or statement measurements. The prior instrumented evidence remains separately labelled; fewer statement dispatches do not establish lower physical reads, scalable throughput or constant-memory full-history replay. Event `fetchall(N)` and the complete projected-balance map remain.

At each scale the final freshly reopened handle ran the **default full verifier** and the independent literal reference. Initial/final references match exactly:

* N512/P1024, `a/USD=-512`, `b/USD=512`, head `5a02b906bca3dc227c15b5be57632d2fa5f54b50089d0823151c0d96f1b47049`.
* N4096/P8192, `a/USD=-4096`, `b/USD=4096`, head `6daa8de0688665419fb0a2a96c069c9bd0b61688e90f5f9a1dce7be1323a4927`.

All 93 phases, including original controls, 18 commit returns, four warm-ups, 24 explicit timed begin/end pairs, both final default-reopen/reference completions and scratch cleanup, are retained. No customer orders, fills, risk/loan/repayment execution, worker/service, registered load variant or old-job authority was used.

## Retention and decision

The [raw directory](../evidence/runs/history-perf-rnd/attempt-03-uninstrumented) contains seven byte-identical original launch/stdout/stderr/summary/sample/phase/unittest files and a SHA256 manifest. External originals remain under `/workspace/uta-history-perf-evidence/attempt-03-uninstrumented` and `/tmp/uta-history-postings-abba-53b3-once`. Only synthetic JSON/JSONL/text is archived; no DB, binary profile, credentials, captured nonce or TLS material. The [author's pure file/rational checker](../evidence/runs/history-perf-rnd/verify_abba_attempt.py) independently recomputes all reported arithmetic from every raw sample and preserves the original red/slower hashes: 83 checks passed, no harness/SQL rerun. Another group must independently review the exact source/raw before a scope decision.

Keep `ordered_postings=False` and Draft PR #20 as R&D. Rollback is leaving the option false or omitting the branch; no data migration is involved. No new run, automatic enablement, ready transition, main merge, 10k/s, sustained capacity, 250k recovery RTO, HA or production approval follows from this result.
