# Independent retained-file acceptance: smoke02

Verdict: **ACCEPT for this one synthetic seven-stage smoke component**. The original smoke01 remains NO_GO. This review neither authorizes a new long run nor establishes six-hour stability, 10,000/s capacity, HA, or readiness for real funds.

The immutable product is `909acecd153e2e89dfe2238e3ed3a3d9a3d3c9f0`, tree `cee60bc0b5413551030300e065d0dcaac6a7ff55`. Product Git status was clean. Controller preparation is `f2ad840f91a41bc098fedadc3ffc30c590f38bc6`; actual safe evidence is `a97483d89fed2d440cc36bdf850be34e179d1cb1` with append-only timing correction `bf8492534d69a64ad2e859b9423c63473d16eb88`.

The reviewer performed no SQL, DB open, product import, observer/capture invocation, service, new job, or signal. The only process inspection was `/proc/<known new pid>/stat` metadata after completion. The original runtime, receipts, private streams, first-smoke result, and timestamps were untouched.

## Independent checks and actual behavior

[The original checker](evidence/managed-909acec-v3-independent/actual-smoke02/review_files.py) implements file, JSON, integer/Fraction and metadata assertions without importing the author's verifier or controller. [Its result](evidence/managed-909acec-v3-independent/actual-smoke02/result.json) records **396 passing assertions**, 115 hashed input paths, and the selected aggregate facts. It verifies all 48 entries of the original public manifest, 45 exact metadata copies against original bytes, and all 16 private stdout/stderr files against their retained hashes and lengths. Each stage stream is complete, within its 4 MiB cap, and has no stderr. Private raw, DBs, keys, TLS material and nonce values are not republished here.

| Stage | Actual retained evidence |
| --- | --- |
| produce | One controller session, 15 DONE rounds, 60.145987524 active seconds, worker signals 3 and parent signal 1, zero unresolved steps/faults; recorded TLS and log checks pass. |
| startup / normal-live | Normal is a real stable boundary after round 1, zero fault signals, and compared/passing golden balances. The normal worker is PID 293932, birth 7829070, generation 1. |
| fault-live | The recorded pidfd death witness identifies that same worker/generation. The sample is within five seconds of death, has four completed rounds and active round 5, worker-fault count 1, parent-fault count 0. The round remains in flight; the replacement worker can already be running. No claim is made that the worker remained down or that in-flight financial golden comparison passed. |
| final | Stable after 15 rounds; all four planned signal actions are DONE; golden comparison passes; no alerts, live orders, positions, or debt remain. |
| cold | Actual direct receipt, complete private clone, successful recorded independent full reopen, and exactly equal pre/post/final compound watermarks. This is a short-smoke receipt, with no long receipt issued. |
| strict-negative | Both retained exit-code layers are integer 1, timeout is literally false, and the ValueError digest is exactly SHA-256 of `producer_audit_requires_other_final_checks_passed`; final eligibility is false. Ordinary stages have integer-zero layers and literal-false timeout, with the distinct direct cold shape handled explicitly. |

Final recorded financial counts are 81 journal events / 194 postings, 60 orders, 30 matches, 60 fill rows, 15 partial cancellations, 90 terminal account commands and 120 risk decisions. The reviewer independently sums the retained final balance snapshot to **zero separately for BTC and USD**, and checks 120 distinct command IDs and sequences, all SUCCEEDED and unquarantined. These counts are the synthetic workload's actual row denominators, not a throughput benchmark. The review does not independently reopen the database or re-execute order/fill/posting reconciliation; it verifies the source-bound records of the actual golden and reopen checks.

## Every-stage admission and budget

All seven commands are exactly those enumerated in the approved envelope. All snapshot/profile/command/phase hashes, per-stage delegated GO records, and the external root approval hash agree. The exact profile/controller/envelope SHAs are `0d4beaaf…`, `e88a575e…`, and `17902f46…`; the external root record is `a283afbe…`. A matching profile alone is not used as authorization.

At each recorded identity timestamp **after Popen**, both wall and BOOTTIME validity windows still hold. Original progress and latest heartbeat ages, mtimes, and effective heartbeat budgets were recomputed using the retained source timestamps, rather than a newly timestamped observation. Minimum remaining lifetime is 7,333,052,370 ns. Protected old process identities 4471/210004 and 8784/412799 remain identical in each before/after capture; old observer f96, interval 60, default software threshold 64 MiB, and no-alert requirement are bound.

All seven captures meet the separately required **17,448,304,640-byte** free-space floor; the lowest observed margin is **75,644,928 bytes**. This is a historical admission check, not reserved capacity or a current free-space assertion. The 256 MiB old-observer contingency, 1 GiB clone input estimate, and periodic output thresholds remain engineering assumptions; none is an OS quota or a proof of maximum disk usage.

All seven Popen records retain first BOOTTIME `78289089259839` and deadline `78439089259839`, without reset. The recorded root endpoint is 64.379813724 seconds from that first Popen; its separate launch interval including initial admission wait is 91.83230681 seconds. The endpoint covers controller exit, closed/fsynced outer streams, raw reads/parse, and first-Popen metadata read. It also follows the controller's business-stage raw hashes. **Root's own auxiliary stdout/stderr hash calculations and final attestation serialization follow this endpoint.** Their complete finalization latency has no post-hash BOOTTIME measurement. The original numeric value and field name remain unmodified; the separately retained erratum documents this limit. No milliseconds were estimated or backfilled.

All **21 known retained new PIDs** were absent from `/proc` at review. This covers the controller, seven wrappers, nested CLIs, actual driver, and workers/listeners known in the retained samples. It does not prove the lifecycle of unrecorded intermediate descendants, or constitute a general leak/HA qualification. Neither old protected PID was inspected for control or signalled.

## Remaining gates and recovery

The final reconciliation deliberately retains the three short-run blockers: actual six hours / 5,400 rounds required, active duration incomplete, and no qualified long producer cold-audit receipt. The short cold audit does not turn these into a six-hour signoff. New Credit V2/H0 qualification is outside this standard managed smoke.

Before a future long run, review a newly versioned exact plan/profile/commands and the smoke02 independent commit binding; retain all 21,600 seconds, 5,400 planned rounds, 12 half-hour golden blocks and original observation/fault/unknown budgets. Obtain a **new per-phase** resource/heartbeat/clock snapshot and explicit root scope for preflight, then start. None is granted here, and no historical snapshot is reusable as fresh admission.

This commit changes only review evidence and documents. Rollback is removal/revert of these review files; it performs no product migration, configuration enablement, job resume, or runtime rollback. Reproduction of the checker requires the retained private raw files and public author archive; the public hash index supports provenance inspection without publishing those streams.

```sh
python docs/evidence/managed-909acec-v3-independent/actual-smoke02/review_files.py
```
