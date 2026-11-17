# Managed startup versus journal history

The bounded synthetic probe observed one worker lose its ordinary five-second startup lease at 250,000 valid journal events. The replacement worker completed verification and emitted READY during shutdown, after the six-second observation window. This is evidence of a startup expiry and extra recovery work; it is **not** evidence of perpetual respawning or permanent recovery failure.

No runtime file changed. The tool and first four cohorts were frozen at `7b2f9e8ed60a55cb03a81283a207659ed106f685`; the 250k cohort used `91c7b0a08b9a83ca89367bba5fb1d8daf67970f8`, whose only change raised the harness maximum from 200k to 250k. Both use the runtime from `d08ab2623bf992ee2a8e923531caea3b0d37b579`. Full per-file runtime and tool hashes, exact commands, cwd, UTC timestamps and environment are retained in [the raw archive](../benchmarks/results/20261117-recovery-scaling/analysis.json).

## Composition and measurement

Each cohort created a new private, one-shard authority through `DurableProcessRouter.initialize(managed=True, bootstrap=...)`. Its offline callback created exactly two zero-funded customer accounts. Through the existing service ledger's public `DurableLedger.post(..., connection=connection)` API and a real database transaction, batches of at most 256 events alternated one USD minor unit between `system:recovery:a` and `system:recovery:b`. Both postings balance exactly; even event counts leave both system balances zero. There are no customer deposits, pool funding claims, fills, matched trades, orders or positions. These are synthetic system journal events, **not matched trade history**. Fixed account and funding counts isolate the ledger-history dimension.

After full independent read-only replay, the parent durably enqueued cancellation of an absent order, queried its actual PENDING state, and invoked normal `start()`. The real spawned children acquired PID-bound tokens, ran unchanged constructors and full financial verification, and used the actual supervisor. The successful cohorts returned the actual business rejection `order_not_found`; an ACK alone never counts as completion. No market was published or activation requested, so `financial_ready=false` and `publication_incomplete`/`market_missing` are expected throughout. The measured READY is the worker ownership receipt, not readiness to accept trading.

Call-through wrappers time the whole child router, worker view, exchange, ledger and credit constructors, full ledger verification, credit verification, funding claims, shard reconciliation, acquire and renew. They preserve arguments, return values and exceptions, use actual monotonic/boottime clocks, and add no delay or lease changes. Begin events are flushed before calls so a killed scan remains visible. These wrappers **change the loaded audit code artifact identity**; the retained wrapper source/hash makes that instrumentation explicit. This is not an uninstrumented production benchmark.

Static inspection establishes **one** full ledger replay in managed startup: `ExchangeService.__init__` calls `DurableLedger.verify` once. `DurableLedger.__init__` checks schema/scales; it does not replay. Credit startup verifies separate projections and receipts. Replay includes SQLite integrity/FK checks, every journal row, per-event posting selects, canonical normalization, fingerprints/hash chain and balances. Separate startup dimensions include all accounts, credit receipts, global funding claims, and historical process-owner registrations. No spot history or later spot-origin migration code is included in this runtime/cohort.

## Actual observations

All values below are single runs, seconds. Setup includes the entire public offline initialization and fixture seeding. Total also includes the independent before/after checks, enqueue, observation and cleanup.

| Events | Setup | Child full replay | Parent observed READY/terminal | Total | Final query |
|---:|---:|---:|---:|---:|---|
| 1,000 | 0.196 | 0.035 | 0.344 | 0.620 | REJECTED/order_not_found |
| 10,000 | 0.994 | 0.247 | 0.557 | 1.863 | REJECTED/order_not_found |
| 50,000 | 4.928 | 1.242 | 1.620 | 7.879 | REJECTED/order_not_found |
| 200,000 | 21.719 | 4.847 | 5.174 | 32.479 | REJECTED/order_not_found |
| 250,000 | 24.960 | gen1 interrupted; gen2 4.718 | none in 6s | 41.263 | PENDING, attempts 0 |

At 200k, acquire-to-renew consumed 4.911099 seconds of the five-second lease: only 88.901 ms remained. Worker view construction took 4.902528 seconds, of which full replay took 4.847354 seconds. This establishes full historical replay as the dominant measured initialization work in this fixture. Constructor durations nest and must not be added as independent costs.

The 250k first worker was PID **43617**, generation **1**. Its acquired lease had boottime `observed_ns=30423249085690`, `expires_ns=30428249085690`; full verification began at `30423278911669`. There is no matching verify-end, renew or READY event. At parent elapsed **5.187881s**, a real observation still found this PID alive and the command PENDING, with boottime `30428261286736`, **12.201 ms after its persisted expiry**. The supervisor's unchanged expired-owner path then replaced it. At 5.294333s the worker PID had changed; generation 2 acquired at `30428385251939`, 136.166 ms after the prior expiry. No `failed` pipe report/code was received, and the killed child's exact exit status was not archived; the expiry/alive observation, replacement, persisted generations and partial call trace are the direct evidence.

Generation **2**, PID **43662**, completed full replay in **4.717773s**, renewed its still-live token, and emitted READY at UTC **2026-11-17 05:28:26.715292**, after the parent observation ended and while normal `close()` waited for initialization. It then saw the stop signal and exited without processing the queued command. Its faster completion does not establish the cause of the timing difference. Final PENDING is retained with its original command ID, no error and no attempts; it must not be relabeled a business or technical rejection. This bounded run cannot establish what continued supervision would have done after that READY.

Every cohort passed independent before/after read-only `integrity_check`, `foreign_key_check`, exact integer posting composition, event IDs/sequences, all fingerprints/hash links, balances, fixed customer account versions and zero orders/positions. Heads and projections remained equal. The 250k head is `f7e00648ccf3f0ee30fcdaebf2ad5c21e82aca2788aed2dd87e4362d53734192`. Cleanup left none of the recorded child PIDs present; all authorities remain at their original `/tmp/uta-recovery-20261117-7b2f9e8/<count>/authority` paths, with private-file sizes/hashes archived. They must not be moved: managed authorities bind their canonical paths.

## Reproduction and limits

```bash
python -m unittest discover -s tests -p 'test_recovery_scaling.py' -v
python benchmarks/run_recovery_scaling.py --events 1000 --output /tmp/uta-recovery-new-1000 --observe-seconds 12
python benchmarks/run_recovery_scaling.py --events 10000 --output /tmp/uta-recovery-new-10000 --observe-seconds 12
python benchmarks/run_recovery_scaling.py --events 50000 --output /tmp/uta-recovery-new-50000 --observe-seconds 12
python benchmarks/run_recovery_scaling.py --events 200000 --output /tmp/uta-recovery-new-200000 --observe-seconds 12
python benchmarks/run_recovery_scaling.py --events 250000 --output /tmp/uta-recovery-new-250000 --observe-seconds 6
```

Run one cohort at a time, with a new output directory and a coordinated host slot. The CLI binds itself and descendants to one allowed CPU, limits address space to 1 GiB, individual files to 256 MiB and per-process CPU time to 55 seconds. Seeding and observation check a 45-second work deadline; cleanup and final integrity replay are additional bounded-size work, so this is **not a universal hard 45-second wall-time guarantee** on arbitrary storage. The actual authorized cohorts all completed below 45 seconds, including cleanup; the longest was 41.263 seconds. Do not extend counts or duration without a new resource plan. The largest retained authority is 94.892 MB; all five together occupy about 195.1 MB.

Environment: CPython 3.12.14, SQLite 3.53.1, AMD EPYC 9V74, affinity `[0]`, shared host cgroup quota four CPUs/16 GiB. Existing producer PID4471 and observer PID8784 remained running with their original births and sources. Archived before/intermediate/after progress samples retain original start/deadline, current heartbeat and market age; final sampled heartbeat age was 0.061s and market age 0.981s. Those samples establish observed coexistence, not absence of all interference. No soak source, database or historical start was modified.

Raw JSONL contains every parent query, persisted lease observation, child phase event, and actual READY receipt. Every original exec completed with exit0 and emitted its stdout summary; no stderr text was emitted to the tool transcript. Separate raw stderr files were not redirected, so they are not claimed as archive artifacts. The 33-file manifest checks retained evidence bytes; the authority databases stay outside Git. This is a bounded recovery diagnosis, not an RTO guarantee, matched-trade capacity test, HA proof or production approval. All production/HA/capacity gates remain false.

